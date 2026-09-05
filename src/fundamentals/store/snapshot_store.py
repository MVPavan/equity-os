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

import errno
import hashlib
import os
import tempfile
from pathlib import Path

import structlog

from fundamentals.contracts.snapshot import (
    RELATIVE_COMPONENTS,
    BlobRef,
    CaptureConflictError,
    CaptureRecord,
    IntegrityError,
    MissingSnapshotError,
    RequestIdentity,
    SnapshotIOError,
    UnsafePathError,
    canonical_json,
)
from fundamentals.store import no_clobber

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

    def put_capture(self, record: CaptureRecord, body: bytes | None) -> CaptureRecord:
        """Publish one capture, returning the record that is on disk afterwards.

        Republishing an identical record is idempotent; the same ``capture_id``
        carrying a different record is a conflict and nothing is touched.
        """
        payload = self._verified_payload(record, body)
        route = self._ensure_route(record.request)
        final_dir = self._child(route, record.capture_id)
        published = self._published_record(final_dir)
        if published is not None:
            if published.record_sha256 != record.record_sha256:
                raise CaptureConflictError(
                    CAPTURE_ALREADY_PUBLISHED.format(capture_id=record.capture_id)
                )
            _LOGGER.info(CAPTURE_REPUBLISHED, capture_id=record.capture_id)
            return published

        blob_path = None if payload is None else self._store_blob(*payload)
        staging = self._stage_capture(record, blob_path)
        self._publish(staging, final_dir, route)
        _LOGGER.info(
            CAPTURE_PUBLISHED,
            capture_id=record.capture_id,
            source_id=record.request.source_id,
            surface=record.request.surface,
            byte_count=0 if record.body is None else record.body.byte_count,
        )
        return record

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

    def _store_blob(self, reference: BlobRef, payload: bytes) -> Path:
        """Create the content-addressed blob, or verify the one already there."""
        blob_dir = self._ensure_child(
            self._ensure_child(self._ensure_child(self._root, BLOBS_DIRNAME), reference.source_id),
            reference.content_sha256[:BLOB_PREFIX_LENGTH],
        )
        blob_path = self._child(blob_dir, reference.content_sha256)
        if not blob_path.exists():
            no_clobber.write_bytes_no_clobber(blob_path, payload)
            no_clobber.fsync_directory(blob_dir)
        self._read_verified(blob_path, reference)
        return blob_path

    def _stage_capture(self, record: CaptureRecord, blob_path: Path | None) -> Path:
        """Assemble the capture directory out of sight, record written last."""
        staging_root = self._ensure_child(self._root, STAGING_DIRNAME)
        staging = Path(tempfile.mkdtemp(dir=staging_root, prefix=f"{record.capture_id}-"))
        if blob_path is not None:
            os.link(blob_path, staging / body_filename(record), follow_symlinks=False)
        document = canonical_json(record.model_dump(mode="json")) + "\n"
        no_clobber.write_bytes_no_clobber(staging / RECORD_FILENAME, document.encode("utf-8"))
        no_clobber.fsync_directory(staging)
        return staging

    def _publish(self, staging: Path, final_dir: Path, route: Path) -> None:
        """Move one assembled capture into place, atomically."""
        try:
            os.rename(staging, final_dir)
        except FileExistsError as error:
            raise CaptureConflictError(
                CAPTURE_ALREADY_PUBLISHED.format(capture_id=final_dir.name)
            ) from error
        except OSError as error:
            if error.errno == errno.ENOTEMPTY:
                raise CaptureConflictError(
                    CAPTURE_ALREADY_PUBLISHED.format(capture_id=final_dir.name)
                ) from error
            raise
        no_clobber.fsync_directory(route)

    def _published_record(self, capture_dir: Path) -> CaptureRecord | None:
        """The record already published at this capture directory, if any."""
        record_path = self._child(capture_dir, RECORD_FILENAME)
        if not record_path.is_file():
            return None
        return self._parse_record(record_path)

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

    def _ensure_route(self, request: RequestIdentity) -> Path:
        """The route directory, created component by component."""
        return self._ensure_child(
            self._ensure_child(self._ensure_child(self._root, request.source_id), request.surface),
            request.request_key,
        )

    def _ensure_child(self, parent: Path, name: str) -> Path:
        """One plain child directory, created if it is absent."""
        _check_component(name)
        return no_clobber.safe_subdirectory(parent, name)

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
