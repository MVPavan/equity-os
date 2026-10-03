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
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import structlog

from fundamentals.contracts.snapshot import (
    RELATIVE_COMPONENTS,
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

_LOGGER = structlog.get_logger(__name__)

BLOBS_DIRNAME = "blobs"
STAGING_DIRNAME = ".staging"
RECORD_FILENAME = "record.json"
BODY_STEM = "body"
BLOB_PREFIX_LENGTH = 2

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
UNSAFE_COMPONENT = "refusing a path component that is not one plain directory name: {name}"
UNSAFE_SYMLINK = "refusing to follow a symlinked path component: {path}"


class SnapshotStore:
    """One retained-capture tree, rooted at a directory this store owns."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._anchor: DirectoryAnchor | None = None

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


def _check_component(name: str) -> None:
    """Refuse a name that is anything other than one plain directory entry."""
    if not name or name in RELATIVE_COMPONENTS or "/" in name or os.sep in name:
        raise UnsafePathError(UNSAFE_COMPONENT.format(name=name))


def body_filename(record: CaptureRecord) -> str:
    """The body file name of one capture: the encoding wins over the media type."""
    if record.content_encoding == GZIP_ENCODING:
        return f"{BODY_STEM}{GZIP_EXTENSION}"
    extension = MEDIA_TYPE_EXTENSIONS.get(record.media_type or "", DEFAULT_EXTENSION)
    return f"{BODY_STEM}{extension}"


MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
READ_BUDGET_SECONDS = 5.0
LOCK_FILENAME = ".snapshot-writer.lock"


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _protected(info: os.stat_result, label: str, *, private: bool = False) -> None:
    forbidden = 0o077 if private else 0o022
    if info.st_uid != os.getuid() or info.st_mode & forbidden:
        raise UnsafePathError(f"unsafe ownership or permissions: {label}")


@dataclass(frozen=True)
class DirectoryAnchor:
    """Operator-pinned directory and ancestry; never imported from source JSON.

    This detects substitution, not malicious same-account administrator rewrites.
    """

    path: Path
    identities: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        path = self.path.absolute()
        if self.identities:
            raise UnsafePathError("directory identities must be observed locally")
        fds = [os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
        identities = [_identity(os.fstat(fds[0]))]
        try:
            for name in path.parts[1:]:
                _check_component(name)
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1])
                fds.append(fd)
                identities.append(_identity(os.fstat(fd)))
            for fd in fds[-2:]:
                _protected(os.fstat(fd), str(path))
        except OSError as error:
            raise UnsafePathError(f"unsafe directory anchor: {path}") from error
        finally:
            for fd in reversed(fds):
                os.close(fd)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "identities", tuple(identities))


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


class DescriptorTree:
    """Short-lived descriptors for one anchored operation, including durability."""

    def __init__(self, anchor: DirectoryAnchor) -> None:
        self.anchor = anchor
        self.fds: list[int] = []
        self.edges: list[tuple[int, str, int]] = []
        self.files: list[int] = []
        self.read_files: list[tuple[int, str, int, os.stat_result]] = []
        self.root = -1

    def __enter__(self) -> DescriptorTree:
        try:
            fd = os.open(self.anchor.path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.fds.append(fd)
            for index, name in enumerate(self.anchor.path.parts[1:], 1):
                parent = fd
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                self.fds.append(fd)
                self.edges.append((parent, name, fd))
                if _identity(os.fstat(fd)) != self.anchor.identities[index]:
                    raise UnsafePathError(f"substituted anchor: {self.anchor.path}")
            self.root = fd
            for protected_fd in self.fds[-2:]:
                _protected(os.fstat(protected_fd), str(self.anchor.path))
            self.verify()
            return self
        except OSError as error:
            self.close()
            raise UnsafePathError(f"cannot open protected anchor: {self.anchor.path}") from error
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        for fd in reversed(self.files + self.fds):
            os.close(fd)
        self.files.clear()
        self.fds.clear()

    def verify(self) -> None:
        for parent, name, fd in self.edges:
            try:
                found = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise UnsafePathError(f"detached directory: {name}") from error
            if not stat.S_ISDIR(found.st_mode) or _identity(found) != _identity(os.fstat(fd)):
                raise UnsafePathError(f"substituted directory: {name}")
        for parent, name, fd, before in self.read_files:
            try:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise UnsafePathError(f"detached file: {name}") from error
            opened = os.fstat(fd)
            if (
                not stat.S_ISREG(current.st_mode)
                or _identity(current) != _identity(before)
                or opened.st_mtime_ns != before.st_mtime_ns
                or opened.st_size != before.st_size
            ):
                raise IntegrityError(f"file changed during operation: {name}")
        root_index = self.fds.index(self.root)
        for fd in self.fds[max(0, root_index - 1) :]:
            _protected(os.fstat(fd), "store directory")

    def flush(self) -> None:
        self.verify()
        for fd in self.files:
            os.fsync(fd)
        # Flush authoritative children and all parent entries through the anchor's parent.
        root_index = self.fds.index(self.root)
        for fd in reversed(self.fds[max(0, root_index - 1) :]):
            os.fsync(fd)
        self.verify()

    def exists(self, parent: int, name: str) -> bool:
        _check_component(name)
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def child(self, parent: int, name: str, *, create: bool = False, private: bool = False) -> int:
        _check_component(name)
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
        try:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError as error:
            raise MissingSnapshotError(f"missing directory: {name}") from error
        except OSError as error:
            raise UnsafePathError(f"unsafe directory: {name}") from error
        self.fds.append(fd)
        self.edges.append((parent, name, fd))
        _protected(os.fstat(fd), name, private=private)
        if create:
            os.fsync(fd)
            os.fsync(parent)
        self.verify()
        return fd

    def descend(
        self, names: tuple[str, ...], *, create: bool = False, private: bool = False
    ) -> int:
        fd = self.root
        for name in names:
            fd = self.child(fd, name, create=create, private=private)
        return fd

    def relocate(self, fd: int, parent: int, name: str) -> None:
        self.edges = [(p, n, child) for p, n, child in self.edges if child != fd]
        self.edges.append((parent, name, fd))

    def read(self, parent: int, name: str, cap: int, *, private: bool = False) -> bytes:
        _check_component(name)
        deadline = time.monotonic() + READ_BUDGET_SECONDS
        try:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise UnsafePathError(f"nonregular file: {name}")
            _protected(before, name, private=private)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            self.files.append(fd)
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
                raise UnsafePathError(f"substituted/nonregular file: {name}")
            _protected(opened, name, private=private)
            self.read_files.append((parent, name, fd, opened))
            if opened.st_size > cap:
                raise IntegrityError(f"oversize file: {name}")
            data = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise SnapshotIOError(f"read budget exceeded: {name}")
                chunk = os.read(fd, min(64 * 1024, cap + 1 - len(data)))
                if time.monotonic() > deadline:
                    raise SnapshotIOError(f"read budget exceeded: {name}")
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > cap:
                    raise IntegrityError(f"oversize/growing file: {name}")
            after = os.fstat(fd)
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                _identity(current) != _identity(opened)
                or after.st_size != len(data)
                or opened.st_mtime_ns != after.st_mtime_ns
                or opened.st_ctime_ns != after.st_ctime_ns
            ):
                raise IntegrityError(f"file changed during read: {name}")
            self.verify()
            return bytes(data)
        except FileNotFoundError as error:
            raise MissingSnapshotError(f"missing file: {name}") from error
        except OSError as error:
            raise SnapshotIOError(f"cannot read file: {name}") from error

    def publish_file(self, parent: int, name: str, data: bytes) -> None:
        _check_component(name)
        if self.exists(parent, name):
            if self.read(parent, name, max(len(data), 1)) != data:
                raise CaptureConflictError(f"conflicting publication: {name}")
            os.fsync(parent)
            return
        temporary = ".tmp-" + uuid.uuid4().hex
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        self.files.append(fd)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise SnapshotIOError("short publication write")
            view = view[written:]
        os.fsync(fd)
        self.verify()
        written_info = os.fstat(fd)
        temp_info = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(temp_info.st_mode) or _identity(temp_info) != _identity(written_info):
            raise UnsafePathError(f"substituted temporary publication: {name}")
        try:
            os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError as error:
            raise CaptureConflictError(f"publication already exists: {name}") from error
        installed_info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(installed_info.st_mode) or _identity(installed_info) != _identity(
            written_info
        ):
            raise UnsafePathError(f"substituted final publication: {name}")
        self.read_files.append((parent, name, fd, written_info))
        os.fsync(parent)
        os.unlink(temporary, dir_fd=parent)
        os.fsync(parent)
        self.verify()

    @contextmanager
    def writer_lock(self) -> Iterator[None]:
        if not self.exists(self.root, LOCK_FILENAME):
            try:
                self.publish_file(self.root, LOCK_FILENAME, b"local snapshot writer\n")
            except CaptureConflictError:
                pass
        self.read(self.root, LOCK_FILENAME, MAX_METADATA_BYTES, private=True)
        fd = self.files[-1]
        deadline = time.monotonic() + READ_BUDGET_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise SnapshotIOError("store writer lock deadline exceeded") from error
                time.sleep(0.01)
        try:
            self.verify()
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
