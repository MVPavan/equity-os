"""Capture registration with its retention facts, and retained byte reads (plan D9 R2, R14,
RP1, RP6, RP7).

Every non-vendor intake registers through :func:`capture_registration`: one READ COMMITTED
transaction that takes the retention lock shared first, in which the ``capture_refs`` trigger
writes the class row and the intake's address is recorded once, with the capture's first
registration. Byte readers go through :func:`read_retained`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.retention import CaptureState, OriginalExpiredError
from fundamentals.contracts.snapshot import CaptureRecord, IntegrityError, MissingSnapshotError
from fundamentals.evidence import repository_rows as rows_sql
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
_GONE = frozenset({CaptureState.EXPIRED, CaptureState.PURGE_PENDING})


class Registration:
    """Capture lookups and inserts inside one registration transaction."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def find(self, source_id: str, surface: str, *, blob_sha256: str) -> CaptureReference | None:
        """The first retained registration of these bytes from this source and surface."""
        found = self._rows(_FIND_RETAINED, (source_id, surface, blob_sha256))
        return rows_sql.capture_of(found[0]) if found else None

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
    """A capture's verified record and bytes: an expired or purging capture raises
    :class:`OriginalExpiredError`; a retained one missing its body is corruption (RP7)."""
    with pool.connection() as conn:
        row = conn.execute(_STATE, (ref.capture_ref_id,)).fetchone()
    assert row is not None
    if CaptureState(row[0]) in _GONE:
        raise OriginalExpiredError(f"capture {ref.capture_ref_id} is {row[0]}")
    try:
        return store.read_capture_verified(
            ref.source_id, ref.surface, ref.request_key, ref.capture_id
        )
    except MissingSnapshotError as error:
        raise IntegrityError(f"retained capture {ref.capture_ref_id} lost its body") from error
