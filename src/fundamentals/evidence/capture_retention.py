"""Capture registration with its retention facts, and retained byte reads (plan D9 R2, R14,
RP1, RP6, RP7).

Every non-vendor intake registers through :func:`capture_registration`: one READ COMMITTED
transaction that takes the retention lock shared first, in which the ``capture_refs`` trigger
writes the class row and the intake's address is recorded once, with the capture's first
registration. Byte readers go through :func:`retained_capture`; vendor intake goes through
:func:`ingest_vendor_retained`, which leaves the pinned ``ingest_vendor`` source unchanged (R13).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row, tuple_row
from psycopg_pool import ConnectionPool

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.retention import CaptureState, OriginalExpiredError
from fundamentals.contracts.snapshot import (
    CaptureRecord,
    IntegrityError,
    MissingSnapshotError,
    UnsafePathError,
)
from fundamentals.evidence import repository_rows as rows_sql
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_ingest import (
    VendorIngestReport,
    VendorIngestRequest,
    ingest_vendor,
)
from fundamentals.store.snapshot_store import SnapshotStore

_INSERT_ADDRESS: LiteralString = (
    "INSERT INTO eqos.capture_addresses (capture_ref_id, url) VALUES (%s, %s)"
)
_RETENTION_SHARED: LiteralString = "SELECT eqos.retention_shared()"
_STATE: LiteralString = "SELECT eqos.capture_state(%s)"
# RP6: reuse matches a retained capture only; equal bytes after expiry are a new capture.
_FIND_RETAINED: LiteralString = (
    "SELECT " + rows_sql.CAPTURE_COLUMNS + " FROM eqos.capture_refs "
    "WHERE source_id = %s AND surface = %s AND blob_sha256 = %s "
    "AND eqos.capture_state(id) IN ('RETAINED', 'RESTORED') ORDER BY id LIMIT 1"
)
_STATE_OF: LiteralString = (
    "SELECT id, eqos.capture_state(id) FROM eqos.capture_refs "
    "WHERE source_id = %s AND surface = %s AND request_key = %s AND capture_id = %s"
)
# Message of the UnsafePathError a purge unlinking a body mid-read raises (descriptor_tree.verify).
DETACHED_FILE = "detached file"
_GONE = frozenset({CaptureState.EXPIRED, CaptureState.PURGE_PENDING})


class Registration:
    """Capture lookups and inserts inside one registration transaction."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def find(self, source_id: str, surface: str, *, blob_sha256: str) -> CaptureReference | None:
        """The first retained registration of these bytes from this source and surface."""
        found = self._rows(_FIND_RETAINED, (source_id, surface, blob_sha256))
        return rows_sql.capture_of(found[0]) if found else None

    def store_clock(self) -> datetime:
        """The store clock in UTC, read on this registration's connection (no second checkout)."""
        clock: datetime = self._rows(rows_sql.STORE_CLOCK, ())[0]["now"]
        return clock.astimezone(UTC)

    def insert(self, ref: CaptureReference, *, url: str | None) -> CaptureReference:
        """Register a capture (an existing registration wins), recording ``url`` with a new one."""
        inserted = self._rows(
            rows_sql.INSERT_CAPTURE_REF + " RETURNING id", rows_sql.capture_params(ref)
        )
        if inserted and url is not None:
            self._conn.execute(_INSERT_ADDRESS, (inserted[0]["id"], url))
        identity = (ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        return rows_sql.capture_of(self._rows(rows_sql.SELECT_CAPTURE_REF, identity)[0])

    def _rows(self, query: LiteralString, params: tuple[object, ...]) -> list[dict[str, Any]]:
        """One parameterised statement's rows as column dicts."""
        with self._conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


@contextmanager
def capture_registration(pool: ConnectionPool) -> Iterator[Registration]:
    """One registration transaction on a pooled connection, under the shared retention lock."""
    with pool.connection() as conn, conn.transaction():
        conn.execute(_RETENTION_SHARED)
        yield Registration(conn)


def read_retained(
    pool: ConnectionPool, store: SnapshotStore, ref: CaptureReference
) -> tuple[CaptureRecord, bytes]:
    """:func:`retained_capture` on a pooled connection."""
    with pool.connection() as conn:
        return retained_capture(conn, store, ref)


def retained_capture(
    conn: psycopg.Connection[Any], store: SnapshotStore, ref: CaptureReference
) -> tuple[CaptureRecord, bytes]:
    """A capture's verified record and bytes: an expired or purging capture raises
    :class:`OriginalExpiredError`; a retained one missing its body is corruption (RP7). Purge
    commits ``PURGE_PENDING`` before it unlinks, so a READ COMMITTED recheck after a missing
    body (or a file detached mid-read) tells a concurrent purge from corruption."""

    def refuse_gone() -> None:
        with conn.cursor(row_factory=tuple_row) as cursor:
            row = cursor.execute(_STATE, (ref.capture_ref_id,)).fetchone()
        assert row is not None
        if CaptureState(row[0]) in _GONE:
            raise OriginalExpiredError(
                f"ORIGINAL_EXPIRED: capture {ref.capture_ref_id} is {row[0]}"
            )

    refuse_gone()
    try:
        return store.read_capture_verified(
            ref.source_id, ref.surface, ref.request_key, ref.capture_id
        )
    except MissingSnapshotError as error:
        refuse_gone()
        raise IntegrityError(f"retained capture {ref.capture_ref_id} lost its body") from error
    except UnsafePathError as error:
        if DETACHED_FILE not in str(error):
            raise
        refuse_gone()
        raise


def ingest_vendor_retained(
    request: VendorIngestRequest, *, repository: EvidenceRepository, **options: Any
) -> VendorIngestReport:
    """``ingest_vendor``, refused before it writes anything (no attempt) when the capture is
    registered and expired or being purged (R13)."""
    identity = (request.source_id, request.surface, request.request_key, request.capture_id)
    with repository._pool.connection() as conn:
        row = conn.execute(_STATE_OF, identity).fetchone()
    if row is not None and CaptureState(row[1]) in _GONE:
        raise OriginalExpiredError(f"ORIGINAL_EXPIRED: capture {row[0]} is {row[1]}")
    return ingest_vendor(request, repository=repository, **options)
