"""Stage one pinned local original as a sealed capture (D1a design decision 12).

The read, content-pin check, ``CaptureRecord.make`` and ``put_capture`` core shared by
``equity_os.interface.commands.sourcing.source_intake.stage_local_source`` and the first-party
evidence intake.
Authority is the caller's decision; this function only refuses a path outside the
operator-pinned directory or bytes that differ from their pin.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from equity_os.contracts.sourcing.acquisition_outcome import OutcomeCode, OutcomeRecord
from equity_os.contracts.sourcing.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    RequestMethod,
    SnapshotRights,
)
from equity_os.contracts.sourcing.source_registration import SourceRegistrationError, require_utc
from equity_os.storage.raw_files.snapshot_store import (
    MAX_BODY_BYTES,
    DescriptorTree,
    DirectoryAnchor,
    SnapshotStore,
)

LOCAL_READ_NATIVE_KIND = "LOCAL_READ"
LOCAL_READ_NATIVE_VALUE = "complete"
_NOT_RELATIVE = "input must be relative to the operator-pinned directory"
_PIN_MISMATCH = "local original differs from approved content pin"


def _utc_now() -> datetime:
    """The store clock."""
    return datetime.now(UTC)


def capture_local_original(
    store: SnapshotStore,
    *,
    input_anchor: DirectoryAnchor,
    source_id: str,
    surface: str,
    request_key: str,
    expected_sha256: str,
    media_type: str,
    rights: SnapshotRights,
    path: Path,
    clock: Callable[[], datetime] = _utc_now,
) -> CaptureRecord:
    """Read one bounded local original, check its pin, and publish its capture record.

    Raises :class:`SourceRegistrationError` for a path outside the pinned directory or
    bytes that differ from ``expected_sha256``; store and filesystem errors propagate.
    """
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise SourceRegistrationError(_NOT_RELATIVE)
    with DescriptorTree(input_anchor) as tree:
        parent = tree.descend(tuple(path.parts[:-1]))
        body = tree.read(parent, path.name, MAX_BODY_BYTES)
        if not body or hashlib.sha256(body).hexdigest() != expected_sha256:
            raise SourceRegistrationError(_PIN_MISMATCH)
        completed = require_utc(clock())
        tree.verify()
    request = RequestIdentity(
        source_id=source_id,
        surface=surface,
        request_key=request_key,
        method=RequestMethod.LOCAL_READ,
        parameters=(),
    )
    record = CaptureRecord.make(
        request=request,
        retrieved_at=completed,
        http_status=None,
        media_type=media_type,
        content_encoding=None,
        body=BlobRef(source_id=source_id, content_sha256=expected_sha256, byte_count=len(body)),
        outcome=OutcomeRecord(
            code=OutcomeCode.OK,
            native_kind=LOCAL_READ_NATIVE_KIND,
            native_value=LOCAL_READ_NATIVE_VALUE,
        ),
        rights=rights,
        schema_version=CAPTURE_SCHEMA_VERSION,
        body_completeness=BodyCompleteness.COMPLETE,
        body_read_issue=None,
    )
    return store.put_capture(record, body)
