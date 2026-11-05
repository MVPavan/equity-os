"""Screens, screen runs and capture batches (plan D7 Task 2; D7-screen-export S3, S4).

A screen run is one vendor's automated export of a configured formula (``ingest.screen_export``):
the definition and results responses are captures (one capture for Tijori, whose results echo the
formula), the formula is the screen text, and each row of the results capture binds to a registry
listing or is ``UNRESOLVED`` with a reason. Binding is registry membership only, never a vendor
identity verification: Screener rows bind by ISIN, Tijori rows by their current NSE symbol. One
export's captures, two runs and pair are written in one transaction. A batch declares the chosen
members once; each member's terminal result and the completion are recorded here, while the
orchestration over onboarding and comparison lives in the CLI.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, LiteralString

import psycopg
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from equity_os.companies.onboarding.discovery import (
    OK,
    Capture,
    Request,
    Response,
    register_capture,
)
from equity_os.contracts.companies.onboarding import OnboardingOutcome, VerificationUnit
from equity_os.contracts.sourcing.source_catalog import (
    SCREEN_EXPORT,
    SCREENER_SCREEN_PAGE,
    TIJORI_SCREEN,
)
from equity_os.coverage.screens.screen_export import ScreenVendor, VendorExport, result_rows
from equity_os.coverage.universe.registry import REGISTRY_LOCK
from equity_os.storage.raw_files.capture_retention import Registration
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

NAME_COLUMN, BSE_COLUMN, NSE_COLUMN, ISIN_COLUMN = "Name", "BSE Code", "NSE Code", "ISIN Code"
TIJORI_NAME, TIJORI_NSE, TIJORI_BSE, TIJORI_SLUG = "name", "nse symbol", "scripcode", "slug"
NSE_SEGMENT, BSE_SEGMENT = "NSE_EQ", "BSE_EQ"
AUTOMATED_EXPORT = "AUTOMATED_EXPORT"
_NO_SCRIPCODE = ("", "0")
_SURFACES = {
    ScreenVendor.SCREENER: (SCREENER_SCREEN_PAGE, SCREEN_EXPORT),
    ScreenVendor.TIJORI: (TIJORI_SCREEN, TIJORI_SCREEN),
}
_UNITS = {
    ScreenVendor.SCREENER: VerificationUnit.SCREENER,
    ScreenVendor.TIJORI: VerificationUnit.TIJORI,
}
_NOT_MEMBERS = "not resolved NSE members of screen run {run}: {symbols}"
_RETENTION_SHARED: LiteralString = "SELECT eqos.retention_shared()"
_INSERT_SCREEN: LiteralString = (
    "INSERT INTO eqos.screens (text_sha256, screen_text) "
    "VALUES (encode(sha256(convert_to(%(text)s, 'UTF8')), 'hex'), %(text)s) ON CONFLICT DO NOTHING"
)
_INSERT_RUN: LiteralString = (
    "INSERT INTO eqos.screen_runs (screen_id, capture_ref_id, vendor, provenance, "
    "definition_capture_ref_id) SELECT id, %(results)s, %(vendor)s, 'AUTOMATED_EXPORT', "
    "%(definition)s FROM eqos.screens "
    "WHERE text_sha256 = encode(sha256(convert_to(%(text)s, 'UTF8')), 'hex') RETURNING id"
)
_INSERT_MEMBER: LiteralString = (
    "INSERT INTO eqos.screen_members (screen_run_id, row_number, name, nse_code, bse_code, "
    "listing_id, reason, isin, slug, slug_verified) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_INSERT_PAIR: LiteralString = (
    "INSERT INTO eqos.screen_run_pairs (screener_run_id, tijori_run_id) VALUES (%s, %s) "
    "RETURNING id"
)
# Current attributes only: a listing absent from the latest load is not resolvable.
_MATCH: LiteralString = (
    "SELECT listing_id, isin FROM eqos.registry_view WHERE status = 'LISTED' AND segment = %s "
    "AND (CASE WHEN segment = 'NSE_EQ' THEN trading_symbol ELSE exchange_token END) = %s"
)
_BY_ISIN: LiteralString = (
    "SELECT listing_id, segment, CASE WHEN segment = 'NSE_EQ' THEN trading_symbol "
    "ELSE exchange_token END FROM eqos.registry_view WHERE status = 'LISTED' AND isin = %s"
)
# The slugs of the Tijori pages a VERIFIED Tijori unit of the ISIN's entity was read from.
_VERIFIED_SLUGS: LiteralString = (
    "SELECT DISTINCT substring(a.url FROM '/company/([^/]+)/') FROM eqos.securities s "
    "JOIN eqos.onboarding_records o ON o.entity_id = s.entity_id "
    "JOIN eqos.namespace_verifications v ON v.onboarding_record_id = o.id "
    "AND v.unit = 'TIJORI' AND v.state = 'VERIFIED' "
    "JOIN eqos.evidence_input_captures c ON c.evidence_input_id = v.evidence_input_id "
    "JOIN eqos.capture_refs r ON r.id = c.capture_ref_id "
    "AND r.source_id = 'tijori' AND r.surface = 'financials' "
    "JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id WHERE s.isin = %s"
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
    UNKNOWN_ISIN = "UNKNOWN_ISIN"
    CONFLICTING_CODES = "CONFLICTING_CODES"
    AMBIGUOUS_CODE = "AMBIGUOUS_CODE"
    NO_CODE = "NO_CODE"


class ScreenMember(BaseModel):
    """One exported row: its resolved listing, or the reason it has none."""

    model_config = ConfigDict(frozen=True)

    member_id: int
    name: str
    nse_code: str | None
    bse_code: str | None
    isin: str | None
    slug: str | None
    listing_id: int | None
    reason: UnresolvedReason | None
    slug_verified: bool | None = None


class ScreenRun(BaseModel):
    """A recorded screen run and its members in export order."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    vendor: ScreenVendor
    members: tuple[ScreenMember, ...]


class ExportResult(BaseModel):
    """One export's two runs and the pair linking them."""

    model_config = ConfigDict(frozen=True)

    screener: ScreenRun
    tijori: ScreenRun
    pair_id: int


class Batch(BaseModel):
    """A declared batch: its id and each chosen symbol's screen-member id."""

    model_config = ConfigDict(frozen=True)

    batch_id: int
    members: dict[str, int]


def record_screen_run(
    pool: ConnectionPool, screener: VendorExport, tijori: VendorExport, snapshots: SnapshotStore
) -> ExportResult:
    """Register each export's responses as captures and write both runs, their members and the
    pair, all in one transaction under the shared retention lock: a refusal leaves nothing. The
    registry load lock, taken first as a load takes it, binds every row against one registry
    state."""
    with snapshots.prepare_ordinary_output(), pool.connection() as conn, conn.transaction():
        conn.execute(REGISTRY_LOCK)
        conn.execute(_RETENTION_SHARED)
        registration = Registration(conn)
        runs = [
            _record(conn, export, *_store(registration, export, snapshots))
            for export in (screener, tijori)
        ]
        (pair_id,) = conn.execute(_INSERT_PAIR, (runs[0].run_id, runs[1].run_id)).fetchone() or (0,)
    return ExportResult(screener=runs[0], tijori=runs[1], pair_id=pair_id)


def _store(
    registration: Registration, export: VendorExport, snapshots: SnapshotStore
) -> tuple[int, int]:
    """Register the definition and results responses (once if they are one); their capture ref
    ids, definition first."""
    pairs = list(zip(_SURFACES[export.vendor], (export.definition, export.results), strict=True))
    if export.definition == export.results:
        pairs = pairs[1:]
    refs = [
        register_capture(
            snapshots,
            registration,
            Capture(
                request=Request(
                    unit=_UNITS[export.vendor], source_id=source, surface=surface, url=fetch.url
                ),
                response=Response(outcome=OK, body=fetch.body, retrieved_at=fetch.retrieved_at),
            ),
        )[1].capture_ref_id
        or 0
        for (source, surface), fetch in pairs
    ]
    return refs[0], refs[-1]


def _record(
    conn: psycopg.Connection[Any], export: VendorExport, definition: int, results: int
) -> ScreenRun:
    """One run: its screen (stored once by text hash) and each row bound per the vendor's rule."""
    keys: dict[str, object] = {"text": export.screen_text, "vendor": export.vendor.value}
    conn.execute(_INSERT_SCREEN, keys)
    keys |= {"definition": definition, "results": results}
    (run_id,) = conn.execute(_INSERT_RUN, keys).fetchone() or (0,)
    bind = _bind_screener if export.vendor is ScreenVendor.SCREENER else _bind_tijori
    members = []
    for number, row in enumerate(result_rows(export.vendor, export.results.body), start=1):
        member = bind(conn, {key: value.strip() for key, value in row.items()})
        values = (
            run_id, number, member.name, member.nse_code, member.bse_code, member.listing_id,
            member.reason, member.isin, member.slug, member.slug_verified,
        )  # fmt: skip
        (member_id,) = conn.execute(_INSERT_MEMBER, values).fetchone() or (0,)
        members.append(member.model_copy(update={"member_id": member_id}))
    return ScreenRun(run_id=run_id, vendor=export.vendor, members=tuple(members))


def _bind_screener(conn: psycopg.Connection[Any], row: dict[str, str]) -> ScreenMember:
    """By ISIN to its LISTED listing, NSE if present else BSE; a supplied code must name it."""
    isin, nse, bse = row.get(ISIN_COLUMN) or None, row.get(NSE_COLUMN) or None, row.get(BSE_COLUMN)
    found = conn.execute(_BY_ISIN, (isin,)).fetchall() if isin else []
    listings: dict[str, list[tuple[int, str]]] = {}
    for listing_id, segment, code in found:
        listings.setdefault(segment, []).append((int(listing_id), code))
    supplied = {NSE_SEGMENT: nse, BSE_SEGMENT: bse or None}
    reason = None
    if not isin:
        reason = UnresolvedReason.NO_CODE
    elif not listings:
        reason = UnresolvedReason.UNKNOWN_ISIN
    elif any(len(hits) > 1 for hits in listings.values()):
        reason = UnresolvedReason.AMBIGUOUS_CODE
    elif any(
        code and [code] != [held for _, held in listings.get(segment, [])]
        for segment, code in supplied.items()
    ):
        reason = UnresolvedReason.CONFLICTING_CODES
    chosen = None if reason else (listings.get(NSE_SEGMENT) or listings[BSE_SEGMENT])[0][0]
    return _member(row.get(NAME_COLUMN, ""), nse, bse or None, isin, None, chosen, reason)


def _bind_tijori(conn: psycopg.Connection[Any], row: dict[str, str]) -> ScreenMember:
    """By the unique current NSE symbol; a supplied scripcode must name the same listing and a
    verified Tijori slug of the ISIN's entity vetoes a different one. A bound member records
    whether its slug is verified."""
    nse, slug = row.get(TIJORI_NSE) or None, row.get(TIJORI_SLUG) or None
    scrip = None if row.get(TIJORI_BSE, "") in _NO_SCRIPCODE else row[TIJORI_BSE]
    hits = conn.execute(_MATCH, (NSE_SEGMENT, nse)).fetchall() if nse else []
    isin = str(hits[0][1]) if len(hits) == 1 else None
    reason, verified = None, set[str]()
    if not nse:
        reason = UnresolvedReason.NO_CODE
    elif not hits:
        reason = UnresolvedReason.UNKNOWN_NSE_CODE
    elif len(hits) > 1:
        reason = UnresolvedReason.AMBIGUOUS_CODE
    elif scrip and [hit[1] for hit in conn.execute(_MATCH, (BSE_SEGMENT, scrip))] != [isin]:
        reason = UnresolvedReason.CONFLICTING_CODES
    elif (verified := {s for (s,) in conn.execute(_VERIFIED_SLUGS, (isin,))}) and (
        slug not in verified
    ):
        reason = UnresolvedReason.CONFLICTING_CODES
    listing = None if reason else int(hits[0][0])
    member = _member(row.get(TIJORI_NAME, ""), nse, scrip, isin, slug, listing, reason)
    return member if reason else member.model_copy(update={"slug_verified": bool(verified)})


def _member(
    name: str,
    nse: str | None,
    bse: str | None,
    isin: str | None,
    slug: str | None,
    listing_id: int | None,
    reason: UnresolvedReason | None,
) -> ScreenMember:
    """A member before its row is written (id 0)."""
    return ScreenMember(
        member_id=0, name=name, nse_code=nse, bse_code=bse, isin=isin, slug=slug,
        listing_id=listing_id, reason=reason,
    )  # fmt: skip


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
