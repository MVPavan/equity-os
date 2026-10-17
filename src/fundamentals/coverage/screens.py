"""Screens, screen runs and capture batches (plan D7 Task 2).

A screen's only input is an owner-exported CSV: the system never requests a Screener screen. The
CSV is registered as a ``SCREEN_EXPORT`` capture; each row resolves against the registry's
current attributes (NSE code, else BSE code alone) or is ``UNRESOLVED`` with a reason. A batch
declares the chosen members once; each member's terminal result and the completion are
recorded here, while the orchestration over onboarding and comparison lives in the CLI.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, LiteralString

import psycopg
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.onboarding import OnboardingOutcome, VerificationUnit
from fundamentals.contracts.source_catalog import SCREEN_EXPORT
from fundamentals.entity.discovery import OK, Capture, Request, Response, store_captures
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.store.snapshot_store import SnapshotStore

NAME_COLUMN, BSE_COLUMN, NSE_COLUMN = "Name", "BSE Code", "NSE Code"
NSE_SEGMENT, BSE_SEGMENT = "NSE_EQ", "BSE_EQ"
_NOT_MEMBERS = "not resolved NSE members of screen run {run}: {symbols}"
_INSERT_SCREEN: LiteralString = (
    "INSERT INTO eqos.screens (text_sha256, screen_text) VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
_SCREEN_ID: LiteralString = "SELECT id FROM eqos.screens WHERE text_sha256 = %s"
_INSERT_RUN: LiteralString = (
    "INSERT INTO eqos.screen_runs (screen_id, capture_ref_id) VALUES (%s, %s) RETURNING id"
)
_INSERT_MEMBER: LiteralString = (
    "INSERT INTO eqos.screen_members (screen_run_id, row_number, name, nse_code, bse_code, "
    "listing_id, reason) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
# Current attributes only: a listing absent from the latest load is not resolvable.
_MATCH: LiteralString = (
    "SELECT listing_id, isin FROM eqos.registry_view WHERE status = 'LISTED' AND segment = %s "
    "AND (CASE WHEN segment = 'NSE_EQ' THEN trading_symbol ELSE exchange_token END) = %s"
)
_BATCH_MEMBERS: LiteralString = (
    "SELECT v.trading_symbol, m.id FROM eqos.screen_members m "
    "JOIN eqos.registry_view v ON v.listing_id = m.listing_id "
    "WHERE m.screen_run_id = %s AND v.segment = 'NSE_EQ' AND v.trading_symbol = ANY (%s)"
)
_INSERT_BATCH: LiteralString = (
    "INSERT INTO eqos.capture_batches (screen_run_id, member_ids) VALUES (%s, %s) RETURNING id"
)
_INSERT_RESULT: LiteralString = (
    "INSERT INTO eqos.batch_member_results (batch_id, member_id, outcome, entity_id, "
    "onboarding_record_id, run_id, exit_code) VALUES (%s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_COMPLETION: LiteralString = "INSERT INTO eqos.batch_completions (batch_id) VALUES (%s)"


class UnresolvedReason(StrEnum):
    """Why a screen row resolved to no listing."""

    UNKNOWN_NSE_CODE = "UNKNOWN_NSE_CODE"
    UNKNOWN_BSE_CODE = "UNKNOWN_BSE_CODE"
    CONFLICTING_CODES = "CONFLICTING_CODES"
    AMBIGUOUS_CODE = "AMBIGUOUS_CODE"
    NO_CODE = "NO_CODE"


class ScreenMember(BaseModel):
    """One CSV row: its resolved listing, or the reason it has none."""

    model_config = ConfigDict(frozen=True)

    member_id: int
    name: str
    nse_code: str | None
    bse_code: str | None
    listing_id: int | None
    reason: UnresolvedReason | None


class ScreenRun(BaseModel):
    """A recorded screen run and its members in CSV order."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    members: tuple[ScreenMember, ...]


class Batch(BaseModel):
    """A declared batch: its id and each chosen symbol's screen-member id."""

    model_config = ConfigDict(frozen=True)

    batch_id: int
    members: dict[str, int]


def record_screen_run(
    pool: ConnectionPool, screen_text: str, export: Path, snapshots: SnapshotStore
) -> ScreenRun:
    """Store the screen once, register the exported CSV as a capture and resolve each row."""
    body = export.read_bytes()
    exported_at = datetime.fromtimestamp(export.stat().st_mtime, UTC)
    source_id, surface = SCREEN_EXPORT
    request = Request(
        unit=VerificationUnit.SCREENER, source_id=source_id, surface=surface, url=export.name
    )
    response = Response(outcome=OK, body=body, retrieved_at=exported_at)
    with snapshots.prepare_ordinary_output():
        ((_, ref),) = store_captures(
            snapshots, EvidenceRepository(pool), [Capture(request=request, response=response)]
        )
    text_sha256 = hashlib.sha256(screen_text.encode()).hexdigest()
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    with pool.connection() as conn, conn.transaction():
        conn.execute(_INSERT_SCREEN, (text_sha256, screen_text))
        (screen_id,) = conn.execute(_SCREEN_ID, (text_sha256,)).fetchone() or (0,)
        (run_id,) = conn.execute(_INSERT_RUN, (screen_id, ref.capture_ref_id)).fetchone() or (0,)
        members = []
        for number, row in enumerate(rows, start=1):
            name, nse, bse = (
                (row.get(column) or "").strip() or None
                for column in (NAME_COLUMN, NSE_COLUMN, BSE_COLUMN)
            )
            listing_id, reason = _resolve(conn, nse, bse)
            values = (run_id, number, name or "", nse, bse, listing_id, reason)
            (member_id,) = conn.execute(_INSERT_MEMBER, values).fetchone() or (0,)
            members.append(
                ScreenMember(
                    member_id=member_id,
                    name=name or "",
                    nse_code=nse,
                    bse_code=bse,
                    listing_id=listing_id,
                    reason=reason,
                )
            )
    return ScreenRun(run_id=run_id, members=tuple(members))


def _resolve(
    conn: psycopg.Connection[Any], nse: str | None, bse: str | None
) -> tuple[int | None, UnresolvedReason | None]:
    """Both codes must each resolve and agree on ISIN; an NSE code never falls back to BSE."""
    nse_hits = conn.execute(_MATCH, (NSE_SEGMENT, nse)).fetchall() if nse else []
    bse_hits = conn.execute(_MATCH, (BSE_SEGMENT, bse)).fetchall() if bse else []
    if nse and not nse_hits:
        return None, UnresolvedReason.UNKNOWN_NSE_CODE
    hits = nse_hits or bse_hits
    if not hits:
        return None, UnresolvedReason.UNKNOWN_BSE_CODE if bse else UnresolvedReason.NO_CODE
    if len(nse_hits) > 1 or len(bse_hits) > 1:
        return None, UnresolvedReason.AMBIGUOUS_CODE
    if nse and bse and (not bse_hits or bse_hits[0][1] != nse_hits[0][1]):
        return None, UnresolvedReason.CONFLICTING_CODES
    return int(hits[0][0]), None


def declare_batch(pool: ConnectionPool, screen_run_id: int, symbols: Sequence[str]) -> Batch:
    """Declare a batch over resolved NSE members named by current symbol; refuse any other
    symbol before writing anything."""
    with pool.connection() as conn, conn.transaction():
        found = conn.execute(_BATCH_MEMBERS, (screen_run_id, list(symbols))).fetchall()
        members = {str(symbol): int(member) for symbol, member in found}
        missing = [symbol for symbol in symbols if symbol not in members]
        if missing:
            raise ValueError(_NOT_MEMBERS.format(run=screen_run_id, symbols=missing))
        members = {symbol: members[symbol] for symbol in symbols}
        values = (screen_run_id, list(members.values()))
        (batch_id,) = conn.execute(_INSERT_BATCH, values).fetchone() or (0,)
    return Batch(batch_id=batch_id, members=members)


def record_member_result(
    pool: ConnectionPool,
    batch_id: int,
    member_id: int,
    *,
    outcome: OnboardingOutcome,
    entity_id: int | None,
    onboarding_record_id: int,
    run_id: int | None,
    exit_code: int,
) -> None:
    """One member's terminal result; the database refuses a run, record or ISIN of another
    entity."""
    values = (
        batch_id,
        member_id,
        outcome.value,
        entity_id,
        onboarding_record_id,
        run_id,
        exit_code,
    )
    with pool.connection() as conn:
        conn.execute(_INSERT_RESULT, values)


def complete_batch(pool: ConnectionPool, batch_id: int) -> None:
    """Append the completion; refused while a declared member has no result."""
    with pool.connection() as conn:
        conn.execute(_INSERT_COMPLETION, (batch_id,))
