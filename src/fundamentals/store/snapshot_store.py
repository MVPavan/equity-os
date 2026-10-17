"""The filesystem home of retained captures, and the only writer of that tree.

The tree is evidence, so the store is built around three rules.

*The record is published last.* A capture directory is assembled under
``.staging`` and moved into place by one rename, so a crash leaves at worst an
orphan blob — bytes nobody claims — never a directory holding a body with no
sealed outcome beside it. A staging directory left by a crash is deliberately
not removed: it is the remnant readers already ignore, and its presence is the
evidence that a write died.

*Bytes are verified, never trusted.* Every body is content-addressed under
``blobs/`` and read back after it is written; every read re-hashes what it found
before handing it to a caller. Otherwise a truncated file would be handed to a
reconciler as the vendor's answer, and the mismatch blamed on the vendor.

*Paths are refused, not repaired.* Directory names come from vendor-shaped
strings, so a component that is a symlink, a separator or a relative name is an
error — sanitising it would file a capture under an identity nobody asked for.

Layout under the root::

    <root>/<source_id>/<surface>/<request_key>/<capture_id>/record.json
    <root>/<source_id>/<surface>/<request_key>/<capture_id>/body<ext>
    <root>/blobs/<source_id>/<sha256[:2]>/<sha256>
    <root>/.staging/...
    <root>/.retention/licence-ended/<source_id>

Retention (plan D9 RP4, RP5) adds the only operations that remove or restore bytes: a blob and
its registered body links are deleted, or a verified body is linked back, under the writer lock
and never touching ``record.json``. A licence-ended marker closes a source to every reader and
writer except :meth:`SnapshotStore.read_record`, which checks the registered record digest.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path

import structlog

from fundamentals.contracts.retention import BlobDeletion, BlobEntry, LicenceEndedError
from fundamentals.contracts.snapshot import (
    BlobRef,
    BodyCompleteness,
    CaptureConflictError,
    CaptureRecord,
    IncompleteSnapshotError,
    IntegrityError,
    MissingSnapshotError,
    RequestIdentity,
    SnapshotIOError,
    UnsafePathError,
    canonical_json,
)
from fundamentals.store.descriptor_tree import (
    LOCK_FILENAME as LOCK_FILENAME,
)
from fundamentals.store.descriptor_tree import (
    MAX_METADATA_BYTES as MAX_METADATA_BYTES,
)
from fundamentals.store.descriptor_tree import (
    READ_BUDGET_SECONDS as READ_BUDGET_SECONDS,
)
from fundamentals.store.descriptor_tree import (
    UNSAFE_COMPONENT as UNSAFE_COMPONENT,
)
from fundamentals.store.descriptor_tree import (
    DescriptorTree as DescriptorTree,
)
from fundamentals.store.descriptor_tree import (
    DirectoryAnchor as DirectoryAnchor,
)
from fundamentals.store.descriptor_tree import (
    _check_component,
    _identity,
)

_LOGGER = structlog.get_logger(__name__)

BLOBS_DIRNAME = "blobs"
STAGING_DIRNAME = ".staging"
RETENTION_DIRNAME = ".retention"
LICENCE_ENDED_DIRNAME = "licence-ended"
LICENCE_MARKER = b"licence ended\n"
RECORD_FILENAME = "record.json"
BODY_STEM = "body"
BLOB_PREFIX_LENGTH = 2
MAX_BODY_BYTES = 32 * 1024 * 1024

GZIP_ENCODING = "gzip"
GZIP_EXTENSION = ".gz"
DEFAULT_EXTENSION = ".bin"
MEDIA_TYPE_EXTENSIONS = {
    "application/json": ".json",
    "text/html": ".html",
    "text/csv": ".csv",
}

CAPTURE_PUBLISHED = "snapshot.capture_published"
CAPTURE_REPUBLISHED = "snapshot.capture_republished"

BODY_DISAGREES_WITH_RECORD = "capture {capture_id} states a body the caller did not supply"
BODY_DIGEST_MISMATCH = "capture {capture_id} body does not match the digest it states"
BODY_SIZE_MISMATCH = "capture {capture_id} body is {found} bytes, not the {stated} it states"
BLOB_CORRUPT = "retained blob {path} no longer matches its own digest"
CAPTURE_ALREADY_PUBLISHED = "capture {capture_id} is already published with a different record"
NO_RETAINED_BODY = "capture {capture_id} retained no body"
NO_SUCH_CAPTURE = "no capture at {path}"
UNREADABLE = "cannot read {path}"
UNSAFE_SYMLINK = "refusing to follow a symlinked path component: {path}"
LICENCE_ENDED = "the {source_id} licence has ended; its captures are closed"
RECORD_DIGEST_MISMATCH = "record of capture {capture_id} does not match its registered digest"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class SnapshotStore:
    """One retained-capture tree, rooted at a directory this store owns."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._anchor: DirectoryAnchor | None = None
        self._held = False

    @contextmanager
    def prepare_ordinary_output(self) -> Iterator[None]:
        """Bootstrap an operator-declared output, never an intake registration anchor."""
        root = self._root.absolute()
        for name in root.parts[1:]:
            _check_component(name)
        ancestor = root.parent
        while True:
            try:
                ancestor.lstat()
                break
            except FileNotFoundError:
                ancestor = ancestor.parent
            except OSError as error:
                raise UnsafePathError("unsafe ordinary output ancestry") from error
        with DescriptorTree(DirectoryAnchor(ancestor)) as tree:
            try:
                tree.descend(root.relative_to(ancestor).parts, create=True)
                tree.flush()
            except OSError as error:
                raise SnapshotIOError("cannot prepare ordinary output store") from error
            anchor = DirectoryAnchor(root)
            if anchor.identities != tuple(_identity(os.fstat(fd)) for fd in tree.fds):
                raise UnsafePathError("substituted ordinary output store")
            if self._anchor is not None and self._anchor.identities != anchor.identities:
                raise UnsafePathError("substituted pinned output store")
            self._anchor = anchor
            tree.verify()
            yield
            tree.verify()

    def put_capture(self, record: CaptureRecord, body: bytes | None) -> CaptureRecord:
        """Publish one capture, returning the record that is on disk afterwards.

        Republishing an identical record is idempotent; the same ``capture_id``
        carrying a different record is a conflict and nothing is touched.
        """
        payload = self._verified_payload(record, body)
        with self._tree(create=True) as tree, tree.writer_lock():
            self._refuse_ended(record.request.source_id)
            route = tree.descend(
                (record.request.source_id, record.request.surface, record.request.request_key),
                create=True,
            )
            if tree.exists(route, record.capture_id):
                published, retained = self._read_from_tree(
                    tree,
                    record.request.source_id,
                    record.request.surface,
                    record.request.request_key,
                    record.capture_id,
                    MAX_BODY_BYTES,
                    evidence=True,
                )
                if published.record_sha256 != record.record_sha256:
                    raise CaptureConflictError(
                        CAPTURE_ALREADY_PUBLISHED.format(capture_id=record.capture_id)
                    )
                if body is not None and retained != body:
                    raise IntegrityError(BODY_DIGEST_MISMATCH.format(capture_id=record.capture_id))
                if tree.exists(tree.root, STAGING_DIRNAME):
                    tree.child(tree.root, STAGING_DIRNAME)
                tree.flush()
                tree.verify()
                return published
            blob_dir = None
            if payload is not None:
                reference, data = payload
                blob_dir = tree.descend(
                    (
                        BLOBS_DIRNAME,
                        reference.source_id,
                        reference.content_sha256[:BLOB_PREFIX_LENGTH],
                    ),
                    create=True,
                )
                tree.publish_file(blob_dir, reference.content_sha256, data)
                self._verify_bytes(
                    tree.read(blob_dir, reference.content_sha256, MAX_BODY_BYTES), reference
                )
            staging_root = tree.descend((STAGING_DIRNAME,), create=True)
            staging_name = record.capture_id + "-" + uuid.uuid4().hex
            staging = tree.child(staging_root, staging_name, create=True)
            if payload is not None and blob_dir is not None:
                os.link(
                    payload[0].content_sha256,
                    body_filename(record),
                    src_dir_fd=blob_dir,
                    dst_dir_fd=staging,
                    follow_symlinks=False,
                )
                os.fsync(staging)
            tree.publish_file(
                staging,
                RECORD_FILENAME,
                (canonical_json(record.model_dump(mode="json")) + "\n").encode(),
            )
            tree.flush()
            tree.verify()
            if tree.exists(route, record.capture_id):
                raise CaptureConflictError(
                    CAPTURE_ALREADY_PUBLISHED.format(capture_id=record.capture_id)
                )
            os.rename(staging_name, record.capture_id, src_dir_fd=staging_root, dst_dir_fd=route)
            tree.relocate(staging, route, record.capture_id)
            os.fsync(route)
            os.fsync(staging_root)
            published, retained = self._read_from_tree(
                tree,
                record.request.source_id,
                record.request.surface,
                record.request.request_key,
                record.capture_id,
                MAX_BODY_BYTES,
                evidence=True,
            )
            if published.record_sha256 != record.record_sha256 or retained != (body or b""):
                raise IntegrityError("capture publication changed")
            tree.flush()
            tree.verify()
            _LOGGER.info(
                CAPTURE_PUBLISHED,
                capture_id=record.capture_id,
                source_id=record.request.source_id,
                surface=record.request.surface,
                byte_count=0 if record.body is None else record.body.byte_count,
            )
            return published

    @contextmanager
    def writer_held(self) -> Iterator[None]:
        """Hold the writer lock across this instance's ``delete_blob`` and ``blob_inventory``
        calls, which then do not take it again (RP4b; a flock is per open file description)."""
        with self._tree() as tree, tree.writer_lock():
            self._held = True
            try:
                yield
            finally:
                self._held = False

    @contextmanager
    def _writer(self) -> Iterator[DescriptorTree]:
        """A tree under the writer lock: the one this instance holds, or taken for the call."""
        with self._tree() as tree, nullcontext() if self._held else tree.writer_lock():
            yield tree

    @contextmanager
    def _tree(self, *, create: bool = False) -> Iterator[DescriptorTree]:
        if self._anchor is None:
            if create:
                ensure_root(self._root)
            self._anchor = DirectoryAnchor(self._root)
        with DescriptorTree(self._anchor) as tree:
            yield tree

    def read_capture_verified(
        self,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        *,
        max_bytes: int = 32 * 1024 * 1024,
    ) -> tuple[CaptureRecord, bytes]:
        """Pin, bound and verify the exact record, body and content-addressed blob."""
        if not 0 < max_bytes <= MAX_BODY_BYTES:
            raise IntegrityError("body read limit exceeds producer bound")
        self._refuse_ended(source_id)
        with self._tree() as tree:
            result = self._read_from_tree(
                tree, source_id, surface, request_key, capture_id, max_bytes
            )
            tree.verify()
            return result

    def _read_from_tree(
        self,
        tree: DescriptorTree,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        max_bytes: int,
        *,
        evidence: bool = False,
    ) -> tuple[CaptureRecord, bytes]:
        directory = tree.descend((source_id, surface, request_key, capture_id))
        try:
            record = CaptureRecord.model_validate_json(
                tree.read(directory, RECORD_FILENAME, MAX_METADATA_BYTES)
            )
        except ValueError as error:
            raise IntegrityError("invalid retained capture record") from error
        if (
            record.request.source_id,
            record.request.surface,
            record.request.request_key,
            record.capture_id,
        ) != (source_id, surface, request_key, capture_id):
            raise IntegrityError("record identity differs from retained route")
        if not evidence and record.effective_body_completeness is BodyCompleteness.PARTIAL:
            raise IncompleteSnapshotError(capture_id, BodyCompleteness.PARTIAL)
        if record.body is None:
            if evidence:
                return record, b""
            raise MissingSnapshotError(NO_RETAINED_BODY.format(capture_id=capture_id))
        if record.body.source_id != source_id:
            raise IntegrityError("body source differs from retained route")
        data = tree.read(directory, body_filename(record), max_bytes)
        self._verify_bytes(data, record.body)
        blob_dir = tree.descend(
            (BLOBS_DIRNAME, source_id, record.body.content_sha256[:BLOB_PREFIX_LENGTH])
        )
        blob = tree.read(blob_dir, record.body.content_sha256, max_bytes)
        self._verify_bytes(blob, record.body)
        if data != blob:
            raise IntegrityError("body differs from retained blob")
        return record, data

    @staticmethod
    def _verify_bytes(data: bytes, reference: BlobRef) -> None:
        if (
            len(data) != reference.byte_count
            or hashlib.sha256(data).hexdigest() != reference.content_sha256
        ):
            raise IntegrityError("retained body no longer matches its digest/size")

    def get_capture(
        self, source_id: str, surface: str, request_key: str, capture_id: str
    ) -> CaptureRecord:
        """The published record of one capture."""
        self._refuse_ended(source_id)
        capture_dir = self._child(self._route(source_id, surface, request_key), capture_id)
        record_path = self._child(capture_dir, RECORD_FILENAME)
        if not record_path.is_file():
            raise MissingSnapshotError(NO_SUCH_CAPTURE.format(path=capture_dir))
        return self._parse_record(record_path)

    def list_captures(
        self, source_id: str, surface: str, request_key: str
    ) -> tuple[CaptureRecord, ...]:
        """Every published capture of one route, oldest first.

        A directory with no ``record.json`` is a crash remnant and ``.staging``
        is work in progress; neither is a capture a reader may see.
        """
        route = self._route(source_id, surface, request_key)
        if not route.is_dir():
            return ()
        records = []
        for entry in route.iterdir():
            if entry.name == STAGING_DIRNAME or entry.is_symlink() or not entry.is_dir():
                continue
            record_path = entry / RECORD_FILENAME
            if record_path.is_symlink() or not record_path.is_file():
                continue
            records.append(self._parse_record(record_path))
        return tuple(sorted(records, key=lambda record: record.capture_id))

    def read_body(self, record: CaptureRecord) -> bytes:
        """The retained bytes of one capture, re-verified against its record."""
        if record.effective_body_completeness is BodyCompleteness.PARTIAL:
            raise IncompleteSnapshotError(record.capture_id, record.effective_body_completeness)
        if record.effective_body_completeness is BodyCompleteness.ABSENT:
            raise MissingSnapshotError(NO_RETAINED_BODY.format(capture_id=record.capture_id))
        return self.read_evidence_body(record)

    def read_evidence_body(self, record: CaptureRecord) -> bytes:
        """Verify retained bytes for inspection, without granting replay eligibility."""
        if record.body is None:
            raise MissingSnapshotError(NO_RETAINED_BODY.format(capture_id=record.capture_id))
        capture_dir = self._child(self._route_of(record.request), record.capture_id)
        body_path = self._child(capture_dir, body_filename(record))
        if not body_path.is_file():
            raise MissingSnapshotError(NO_SUCH_CAPTURE.format(path=body_path))
        return self._read_verified(body_path, record.body)

    def mark_licence_ended(self, source_id: str) -> None:
        """Close ``source_id`` to the store's readers and writers (RP4a); idempotent."""
        with self._tree(create=True) as tree, tree.writer_lock():
            markers = tree.descend((RETENTION_DIRNAME, LICENCE_ENDED_DIRNAME), create=True)
            tree.publish_file(markers, source_id, LICENCE_MARKER)
            tree.flush()

    def read_record(
        self, source_id: str, surface: str, request_key: str, capture_id: str, expected_sha256: str
    ) -> bytes:
        """The ``record.json`` bytes of one capture, refused unless they hash to its registered
        digest; open after a licence end (RP4a)."""
        with self._tree() as tree:
            directory = tree.descend((source_id, surface, request_key, capture_id))
            data = tree.read(directory, RECORD_FILENAME, MAX_METADATA_BYTES)
            tree.verify()
        if _record_sha256(data) != expected_sha256:
            raise IntegrityError(RECORD_DIGEST_MISMATCH.format(capture_id=capture_id))
        return data

    def put_record(self, record_bytes: bytes, expected_sha256: str) -> None:
        """Publish one capture's ``record.json`` alone (an expired capture keeps no body)."""
        record = CaptureRecord.model_validate_json(record_bytes)
        if _record_sha256(record_bytes) != expected_sha256:
            raise IntegrityError(RECORD_DIGEST_MISMATCH.format(capture_id=record.capture_id))
        request = record.request
        with self._tree(create=True) as tree, tree.writer_lock():
            directory = tree.descend(
                (request.source_id, request.surface, request.request_key, record.capture_id),
                create=True,
            )
            tree.publish_file(directory, RECORD_FILENAME, record_bytes)
            tree.flush()

    def relink(self, record: CaptureRecord, body: bytes) -> CaptureRecord:
        """Link verified bytes back as a published capture's body; ``record.json`` must already
        be the registered one and is never written (R10)."""
        payload = self._verified_payload(record, body)
        if payload is None:
            raise IntegrityError(NO_RETAINED_BODY.format(capture_id=record.capture_id))
        reference, data = payload
        request = record.request
        identity = (request.source_id, request.surface, request.request_key, record.capture_id)
        with self._tree() as tree, tree.writer_lock():
            self._refuse_ended(request.source_id)
            directory = tree.descend(identity)
            published = tree.read(directory, RECORD_FILENAME, MAX_METADATA_BYTES)
            if _record_sha256(published) != record.record_sha256:
                raise CaptureConflictError(
                    CAPTURE_ALREADY_PUBLISHED.format(capture_id=record.capture_id)
                )
            sha = reference.content_sha256
            blob_dir = tree.descend(
                (BLOBS_DIRNAME, request.source_id, sha[:BLOB_PREFIX_LENGTH]), create=True
            )
            tree.publish_file(blob_dir, sha, data)
            name = body_filename(record)
            if not tree.exists(directory, name):
                os.link(sha, name, src_dir_fd=blob_dir, dst_dir_fd=directory, follow_symlinks=False)
                os.fsync(directory)
            restored, _ = self._read_from_tree(tree, *identity, MAX_BODY_BYTES)
            tree.flush()
            return restored

    def delete_blob(
        self,
        source_id: str,
        blob_sha256: str,
        links: tuple[tuple[str, str, str], ...],
        checkpoint: Callable[[], None],
    ) -> BlobDeletion:
        """Unlink each registered body link ``(surface, request_key, capture_id)``, then the
        blob, fsyncing parents and calling ``checkpoint`` after each unlink. A blob with a link
        not named here keeps every byte (``UNKNOWN_LINK``); missing files count as deleted."""
        with self._writer() as tree:
            blob_dir = _find_dir(tree, (BLOBS_DIRNAME, source_id, blob_sha256[:BLOB_PREFIX_LENGTH]))
            blob = None
            if blob_dir is not None and tree.exists(blob_dir, blob_sha256):
                blob = os.stat(blob_sha256, dir_fd=blob_dir, follow_symlinks=False)
            bodies, linked = [], 0
            for surface, request_key, capture_id in links:
                directory = tree.descend((source_id, surface, request_key, capture_id))
                record = CaptureRecord.model_validate_json(
                    tree.read(directory, RECORD_FILENAME, MAX_METADATA_BYTES)
                )
                name = body_filename(record)
                if record.body is None or not tree.exists(directory, name):
                    continue
                bodies.append((directory, name))
                found = os.stat(name, dir_fd=directory, follow_symlinks=False)
                linked += blob is not None and _identity(found) == _identity(blob)
            if blob is not None and blob.st_nlink > 1 + linked:
                return BlobDeletion.UNKNOWN_LINK
            for directory, name in bodies:
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
                checkpoint()
            if blob is not None and blob_dir is not None:
                os.unlink(blob_sha256, dir_fd=blob_dir)
                os.fsync(blob_dir)
                checkpoint()
            return BlobDeletion.DELETED

    def blob_inventory(self) -> tuple[BlobEntry, ...]:
        """Every stored blob and its link count, listed under the writer lock (RP5)."""
        with self._writer():
            blobs = self._root / BLOBS_DIRNAME
            return tuple(
                BlobEntry(source_id=source.name, blob_sha256=path.name, links=info.st_nlink)
                for source in _plain_dirs(blobs)
                for prefix in _plain_dirs(source)
                for path in sorted(prefix.iterdir())
                if _SHA256.fullmatch(path.name) and not path.is_symlink()
                for info in (path.lstat(),)
            )

    def _refuse_ended(self, source_id: str) -> None:
        """Raise when ``source_id`` carries a licence-ended marker."""
        _check_component(source_id)
        if (self._root / RETENTION_DIRNAME / LICENCE_ENDED_DIRNAME / source_id).exists():
            raise LicenceEndedError(LICENCE_ENDED.format(source_id=source_id))

    def _verified_payload(
        self, record: CaptureRecord, body: bytes | None
    ) -> tuple[BlobRef, bytes] | None:
        """Pair a body with the reference that describes it, or refuse both."""
        if record.body is None or body is None:
            if record.body is not None or body is not None:
                raise IntegrityError(
                    BODY_DISAGREES_WITH_RECORD.format(capture_id=record.capture_id)
                )
            return None
        if len(body) > MAX_BODY_BYTES:
            raise IntegrityError("body exceeds producer read/write bound")
        if hashlib.sha256(body).hexdigest() != record.body.content_sha256:
            raise IntegrityError(BODY_DIGEST_MISMATCH.format(capture_id=record.capture_id))
        if len(body) != record.body.byte_count:
            raise IntegrityError(
                BODY_SIZE_MISMATCH.format(
                    capture_id=record.capture_id,
                    found=len(body),
                    stated=record.body.byte_count,
                )
            )
        return record.body, body

    def _parse_record(self, record_path: Path) -> CaptureRecord:
        """One record document, read without following a symlink."""
        return CaptureRecord.model_validate_json(self._read_file(record_path))

    def _read_verified(self, path: Path, reference: BlobRef) -> bytes:
        """Bytes that still match the digest and size the reference states."""
        found = self._read_file(path)
        if hashlib.sha256(found).hexdigest() != reference.content_sha256:
            raise IntegrityError(BLOB_CORRUPT.format(path=path))
        if len(found) != reference.byte_count:
            raise IntegrityError(BLOB_CORRUPT.format(path=path))
        return found

    def _read_file(self, path: Path) -> bytes:
        """Read one file, refusing to follow a symlink into it."""
        if path.is_symlink():
            raise UnsafePathError(UNSAFE_SYMLINK.format(path=path))
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError as error:
            raise MissingSnapshotError(NO_SUCH_CAPTURE.format(path=path)) from error
        except OSError as error:
            raise SnapshotIOError(UNREADABLE.format(path=path)) from error
        with os.fdopen(descriptor, "rb") as handle:
            return handle.read()

    def _route_of(self, request: RequestIdentity) -> Path:
        """The route directory one request identity names."""
        return self._route(request.source_id, request.surface, request.request_key)

    def _route(self, source_id: str, surface: str, request_key: str) -> Path:
        """The route directory, checked component by component and not created."""
        return self._child(self._child(self._child(self._root, source_id), surface), request_key)

    def _child(self, parent: Path, name: str) -> Path:
        """One plain child path, refused if it is a symlink."""
        _check_component(name)
        path = parent / name
        if path.is_symlink():
            raise UnsafePathError(UNSAFE_SYMLINK.format(path=path))
        return path


def body_filename(record: CaptureRecord) -> str:
    """The body file name of one capture: the encoding wins over the media type."""
    if record.content_encoding == GZIP_ENCODING:
        return f"{BODY_STEM}{GZIP_EXTENSION}"
    extension = MEDIA_TYPE_EXTENSIONS.get(record.media_type or "", DEFAULT_EXTENSION)
    return f"{BODY_STEM}{extension}"


def _record_sha256(record_bytes: bytes) -> str:
    """The registered digest of a ``record.json`` file: its canonical JSON, newline dropped."""
    return hashlib.sha256(record_bytes.removesuffix(b"\n")).hexdigest()


def _find_dir(tree: DescriptorTree, names: tuple[str, ...]) -> int | None:
    """The descriptor of an existing directory path under the root, ``None`` if absent."""
    fd = tree.root
    for name in names:
        if not tree.exists(fd, name):
            return None
        fd = tree.child(fd, name)
    return fd


def _plain_dirs(path: Path) -> list[Path]:
    """The non-symlink subdirectories of ``path``, sorted; none if it is absent."""
    if not path.is_dir() or path.is_symlink():
        return []
    return sorted(c for c in path.iterdir() if c.is_dir() and not c.is_symlink())


def ensure_root(path: Path) -> None:
    """Create the ordinary store root through its pinned existing parent."""
    if path.is_symlink():
        raise UnsafePathError(f"symlinked store root: {path}")
    if path.exists():
        return
    with DescriptorTree(DirectoryAnchor(path.absolute().parent)) as tree:
        tree.child(tree.root, path.name, create=True)
        tree.flush()
        tree.verify()
