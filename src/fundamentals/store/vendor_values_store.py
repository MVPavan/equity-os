"""Append-only vendor observations, registered before parsing and written atomically."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from enum import StrEnum
from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.evidence.capture_retention import capture_registration
from fundamentals.ingest.vendor_surface_fetch import Fetched


class OutcomeStatus(StrEnum):
    """Parse usability, independent of the capture's HTTP outcome."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    UNUSABLE = "UNUSABLE"
    KEPT = "KEPT"


USABLE = frozenset(
    {OutcomeStatus.OK, OutcomeStatus.PARTIAL, OutcomeStatus.EMPTY, OutcomeStatus.KEPT}
)
VENDOR_TABLES = frozenset(
    {"vendor_parser_versions", "vendor_outcomes", "vendor_values", "vendor_basis_bindings"}
    | {"vendor_label_proposals", "vendor_text_claims"}
)


class VendorValue(BaseModel):
    """One code-read cell, identified by position rather than its mutable labels."""

    model_config = ConfigDict(frozen=True)
    table_key: str
    row_index: int
    column_index: int
    locator: str
    row_label: str
    column_label: str
    raw_text: str
    value: Decimal | None
    unit: str | None = None
    basis: str | None = None
    link: str | None = None
    padded: bool = False
    expected_numeric: bool = False


class Outcome(BaseModel):
    """An atomic parse result for one logical surface and version."""

    model_config = ConfigDict(frozen=True)
    surface: str
    parser_version: str
    parser_sha256: str
    status: OutcomeStatus
    symbol: str | None
    detail: str | None
    values: tuple[VendorValue, ...] = ()
    rejected_count: int | None = None
    traversal_key: str | None = None
    traversal_page: int | None = None
    traversal_done: bool = False


class ParserVersionDrift(Exception):  # noqa: N818 - plan interface
    """A pinned version was reused for changed parser source."""


def register(pool: ConnectionPool, fetched: Fetched) -> CaptureReference:
    """Register a stored response and its URL under the store's clock."""
    record = fetched.record
    with capture_registration(pool) as registration:
        now = registration.store_clock()
        return registration.insert(
            CaptureReference(
                capture_ref_id=None,
                source_id=record.request.source_id,
                surface=record.request.surface,
                request_key=record.request.request_key,
                capture_id=record.capture_id,
                blob_sha256=record.body.content_sha256
                if record.body
                else hashlib.sha256(b"").hexdigest(),
                record_sha256=record.record_sha256,
                registered_at=now,
                first_seen_at=now,
            ),
            url=fetched.url,
            location=fetched.location,
        )


class VendorValuesStore:
    """The transaction boundary for an outcome and all of its cells."""

    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def has_outcome(self, capture_ref_id: int, surface: str, parser_version: str) -> bool:
        """Whether this exact parser already processed this capture and surface."""
        with self.pool.connection() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM eqos.vendor_outcomes "
                    "WHERE capture_ref_id=%s AND surface=%s AND parser_version=%s",
                    (capture_ref_id, surface, parser_version),
                ).fetchone()
                is not None
            )

    def record(
        self,
        ref: CaptureReference,
        outcome: Outcome,
        *,
        row_count: int,
        conn: Connection[Any] | None = None,
    ) -> int:
        """Write once, joining a caller's transaction when provided."""
        if outcome.values and row_count != len(outcome.values):
            raise ValueError("row_count differs from values")
        if conn is None:
            with self.pool.connection() as owned, owned.transaction():
                return self.record(ref, outcome, row_count=row_count, conn=owned)
        with conn.transaction():
            conn.execute(
                "INSERT INTO eqos.vendor_parser_versions VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (outcome.parser_version, outcome.parser_sha256),
            )
            pinned = conn.execute(
                "SELECT parser_sha256 FROM eqos.vendor_parser_versions WHERE parser_version=%s",
                (outcome.parser_version,),
            ).fetchone()
            assert pinned is not None
            if pinned[0] != outcome.parser_sha256:
                raise ParserVersionDrift(outcome.parser_version)
            row = conn.execute(
                """INSERT INTO eqos.vendor_outcomes (capture_ref_id,surface,parser_version,
                symbol,status,row_count,rejected_count,detail,traversal_key,traversal_page,traversal_done)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    ref.capture_ref_id,
                    outcome.surface,
                    outcome.parser_version,
                    outcome.symbol,
                    outcome.status,
                    row_count,
                    outcome.rejected_count,
                    outcome.detail,
                    outcome.traversal_key,
                    outcome.traversal_page,
                    outcome.traversal_done,
                ),
            ).fetchone()
            assert row is not None
            identifier = int(row[0])
            with conn.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO eqos.vendor_values (outcome_id,capture_ref_id,
                    table_key,row_index,column_index,locator,row_label,column_label,raw_text,value,
                    unit,basis,link,padded,expected_numeric)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [
                        (identifier, ref.capture_ref_id, *value.model_dump().values())
                        for value in outcome.values
                    ],
                )
            return identifier
