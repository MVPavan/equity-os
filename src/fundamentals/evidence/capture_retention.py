"""Capture registration with its retention facts (plan D9 R2, R14, RP6).

Every non-vendor intake registers through :func:`capture_registration`: one READ COMMITTED
transaction in which the ``capture_refs`` trigger writes the class row and the intake's address
is recorded once, with the capture's first registration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.evidence import repository_rows as rows_sql

_INSERT_ADDRESS: LiteralString = (
    "INSERT INTO eqos.capture_addresses (capture_ref_id, url) VALUES (%s, %s)"
)


class Registration:
    """Capture lookups and inserts inside one registration transaction."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self._conn = conn

    def find(self, source_id: str, surface: str, *, blob_sha256: str) -> CaptureReference | None:
        """The first registration of these bytes from this source and surface (reuse)."""
        found = self._rows(rows_sql.FIND_CAPTURE_REF, (source_id, surface, blob_sha256))
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
    """One registration transaction on a pooled connection."""
    with pool.connection() as conn, conn.transaction():
        yield Registration(conn)
