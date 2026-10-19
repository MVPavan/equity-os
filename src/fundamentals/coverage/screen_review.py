"""Screen review items, the owner's dispositions and one other-vendor read per item (plan
D7-screen-export S5).

The items are ``eqos.screen_review_items``; an item is pending until its one disposition. A
member's values are its row of the run's results capture, never a copy. After an export commits,
each pending bound item whose NSE symbol names a watchlist stock with verified other-vendor ids
gets one identity-gated page of the other vendor, retained as a capture; every other pending item
records why it has none. A Tijori read keeps the identifiers it was gated on and replays against
them, never today's watchlist. Values print as vendor text side by side, never compared or stored.
Bound Tijori members without a verified slug are listed: their binding is registry membership,
not vendor identity verification.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import LiteralString

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import StockConfig
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.review_queue import DispositionKind
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.contracts.source_catalog import SCREENER_PAGE, TIJORI_OVERVIEW
from fundamentals.entity.discovery import OK, Capture, Request, Response, store_captures
from fundamentals.evidence.capture_retention import read_retained
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ingest.http_session import RequestPacer
from fundamentals.ingest.screen_export import ScreenVendor, result_rows
from fundamentals.ingest.screener_company_discovery import top_ratios_list
from fundamentals.ingest.screener_company_fragments import read_quick_ratios
from fundamentals.ingest.screener_company_models import Binding
from fundamentals.ingest.screener_company_parts import PAGE_QUICK_RATIOS_DOCUMENT_ID
from fundamentals.ingest.screener_financials_models import IdentityStrength
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    BasisTopology,
    PageOutcome,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import parse_document
from fundamentals.ingest.tijori_overview_models import (
    TijoriCompanyDetailsSection,
    TijoriOverviewSection,
)
from fundamentals.ingest.tijori_screen_fetch import fetch_overview_bytes
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriError
from fundamentals.store.snapshot_store import SnapshotStore

FIELD_NOT_EXPOSED = "FIELD_NOT_EXPOSED"
READ_NOT_RECORDED = "READ_NOT_RECORDED"
GATE_NOT_RECORDED = "GATE_NOT_RECORDED"
SLUG_NOT_VERIFIED = "SLUG_NOT_VERIFIED"
DISPOSITION_KINDS = (
    DispositionKind.ACCEPTED_AS_DEFINITION,
    DispositionKind.MAPPING_FIX,
    DispositionKind.DISMISSED,
)
# S5's fixed correspondences: the member's column verbatim -> the other vendor's field.
CORRESPONDENCES = {
    ScreenVendor.SCREENER: {
        "Market Capitalization": "market_cap",
        "Price to Earning": "price_earnings",
        "PEG Ratio": "price_earnings_growth",
    },
    ScreenVendor.TIJORI: {"<span>latest</span>Mcap<span>Cr</span>": "Market Cap"},
}
# Each pending item, its member's row locator, its read (both null while none is recorded) and
# its bound ISIN with that ISIN's current BSE codes.
_PENDING: LiteralString = (
    "SELECT p.member_id, p.vendor, p.status, p.reason, p.nse_code, p.candidate_member_ids, "
    "m.row_number, r.capture_ref_id AS results_ref, o.capture_ref_id AS read_ref, o.gap, "
    "o.tijori_slug, o.tijori_company_id, m.isin, ARRAY(SELECT v.exchange_token "
    "FROM eqos.registry_view v WHERE v.status = 'LISTED' AND v.segment = 'BSE_EQ' "
    "AND v.isin = m.isin) AS bse_codes "
    "FROM eqos.screen_review_pending p JOIN eqos.screen_members m ON m.id = p.member_id "
    "JOIN eqos.screen_runs r ON r.id = m.screen_run_id "
    "LEFT JOIN eqos.screen_other_vendor_reads o "
    "ON (o.pair_id, o.member_id) = (p.pair_id, p.member_id) "
    "WHERE p.pair_id = %s ORDER BY p.member_id"
)
_INSERT_DISPOSITION: LiteralString = (
    "INSERT INTO eqos.screen_member_dispositions (pair_id, member_id, kind, reason, "
    "evidence_ref) VALUES (%s, %s, %s, %s, %s)"
)
_INSERT_READ: LiteralString = (
    "INSERT INTO eqos.screen_other_vendor_reads (pair_id, member_id, capture_ref_id, gap, "
    "tijori_slug, tijori_company_id) VALUES (%s, %s, %s, %s, %s, %s)"
)
_UNVERIFIED: LiteralString = (
    "SELECT m.id FROM eqos.screen_run_pairs p JOIN eqos.screen_members m "
    "ON m.screen_run_id = p.tijori_run_id WHERE p.id = %s AND NOT m.slug_verified ORDER BY m.id"
)


class ItemStatus(StrEnum):
    """Why a member is a review item (S5)."""

    UNRESOLVED = "UNRESOLVED"
    ABSENT = "ABSENT"
    NOT_PROVEN = "NOT_PROVEN"


class ReadGap(StrEnum):
    """Why a pending item has no other-vendor read."""

    MEMBER_UNRESOLVED = "MEMBER_UNRESOLVED"
    NOT_VERIFIED = "NOT_VERIFIED"
    READ_REFUSED = "READ_REFUSED"


class ReviewItem(BaseModel):
    """One pending item of a pair, its member's row locator and its read (a capture ref id, a
    gap, or ``None`` while none is recorded) with a Tijori read's gate identifiers, and the
    member's bound ISIN with its current BSE codes."""

    model_config = ConfigDict(frozen=True)

    pair_id: int
    member_id: int
    vendor: ScreenVendor
    status: ItemStatus
    reason: str | None
    nse_code: str | None
    candidate_member_ids: tuple[int, ...]
    row_number: int
    results_ref: int
    read: int | ReadGap | None
    tijori_slug: str | None = None
    tijori_company_id: int | None = None
    isin: str | None = None
    bse_codes: tuple[str, ...] = ()


def pending_items(pool: ConnectionPool, pair_id: int) -> tuple[ReviewItem, ...]:
    """The pair's items without a disposition, by member."""
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        found = cursor.execute(_PENDING, (pair_id,)).fetchall()
    return tuple(
        ReviewItem.model_validate(row | {"pair_id": pair_id, "read": row["gap"] or row["read_ref"]})
        for row in found
    )


def slug_not_verified(pool: ConnectionPool, pair_id: int) -> tuple[int, ...]:
    """The pair's bound Tijori members whose slug is not a verified one."""
    with pool.connection() as conn:
        return tuple(member for (member,) in conn.execute(_UNVERIFIED, (pair_id,)))


def dispose(
    pool: ConnectionPool,
    pair_id: int,
    member_id: int,
    kind: DispositionKind,
    reason: str,
    evidence_ref: str,
) -> None:
    """Append the owner's one disposition of an item; the database refuses anything else."""
    with pool.connection() as conn:
        conn.execute(_INSERT_DISPOSITION, (pair_id, member_id, kind.value, reason, evidence_ref))


def read_other_vendor(
    item: ReviewItem,
    stock: StockConfig | None,
    tijori: TijoriSource,
    tijori_pacer: RequestPacer,
    screener: ScreenerSessionSource,
) -> Capture | ReadGap:
    """One identity-gated page of the other vendor for a bound item, or why there is none. The
    watchlist stock must be the member's issuer: its BSE scrip one of the bound ISIN's listings
    and its ISIN, if configured, that ISIN (an NSE symbol can be reused)."""
    if item.status is ItemStatus.UNRESOLVED:
        return ReadGap.MEMBER_UNRESOLVED
    ids = None if stock is None else stock.identifiers
    if ids is None or ids.isin not in (None, item.isin) or ids.bse_scrip not in item.bse_codes:
        return ReadGap.NOT_VERIFIED
    if item.vendor is ScreenVendor.SCREENER:
        if ids.unverified_tijori_fields():
            return ReadGap.NOT_VERIFIED
        tijori_pacer.wait_for_slot()
        try:
            body = fetch_overview_bytes(tijori, ids.tijori_slug)
            _company_details(body, ids.tijori_slug, ids.nse_symbol, ids.tijori_company_id)
        except TijoriError:
            return ReadGap.READ_REFUSED
        url = tijori.config.overview_url_template.format(
            base=tijori.config.base_url, slug=ids.tijori_slug
        )
        return _capture(VerificationUnit.TIJORI, TIJORI_OVERVIEW, url, body, datetime.now(UTC))
    if ids.unverified_screener_fields():
        return ReadGap.NOT_VERIFIED
    consolidated = ids.screener_warehouse_id_consolidated is not None
    try:
        page = screener.fetch_company_page(
            symbol=ids.nse_symbol,
            slug=ids.screener_slug,
            basis=Basis.CONSOLIDATED if consolidated else Basis.STANDALONE,
            expected_company_id=ids.screener_company_id,
            topology=BasisTopology(
                consolidated_warehouse_id=ids.screener_warehouse_id_consolidated,
                standalone_warehouse_id=ids.screener_warehouse_id_standalone,
            ),
        )
    except ScreenerSessionError:
        return ReadGap.READ_REFUSED
    if page.metadata.outcome is not PageOutcome.OK:
        return ReadGap.READ_REFUSED
    meta = page.metadata
    return _capture(
        VerificationUnit.SCREENER, SCREENER_PAGE, meta.source_url, page.raw_body, meta.fetched_at
    )


def record_read(
    pool: ConnectionPool,
    snapshots: SnapshotStore,
    item: ReviewItem,
    read: Capture | ReadGap,
    stock: StockConfig | None,
) -> None:
    """Retain a read's bytes and record it against the item with the Tijori identifiers it was
    gated on (``stock``'s), or record the item's gap."""
    ref, gap = None, read if isinstance(read, ReadGap) else None
    gate: tuple[str | None, int | None] = (None, None)
    if isinstance(read, Capture):
        with snapshots.prepare_ordinary_output():
            ((_, stored),) = store_captures(snapshots, EvidenceRepository(pool), [read])
        ref = stored.capture_ref_id
        if item.vendor is ScreenVendor.SCREENER and stock is not None:
            gate = (stock.identifiers.tijori_slug, stock.identifiers.tijori_company_id)
    with pool.connection() as conn:
        conn.execute(_INSERT_READ, (item.pair_id, item.member_id, ref, gap, *gate))


def side_by_side(
    pool: ConnectionPool,
    snapshots: SnapshotStore,
    items: tuple[ReviewItem, ...],
) -> Iterator[tuple[ReviewItem, list[tuple[str, str, str]]]]:
    """Each item with every column of its member's row (hydrated verbatim from its run's
    results capture, each capture read once) beside the other vendor's corresponding field,
    ``FIELD_NOT_EXPOSED``, the item's gap, or ``READ_NOT_RECORDED``."""
    results: dict[int, tuple[dict[str, str], ...]] = {}
    for item in items:
        if item.results_ref not in results:
            body = _retained(pool, snapshots, item.results_ref)[1]
            results[item.results_ref] = result_rows(item.vendor, body)
        other = _other_values(pool, snapshots, item)
        row = results[item.results_ref][item.row_number - 1]
        shown = dict.fromkeys(row, other) if isinstance(other, str) else other
        yield (
            item,
            [(column, own, shown.get(column, FIELD_NOT_EXPOSED)) for column, own in row.items()],
        )


def _other_values(
    pool: ConnectionPool, snapshots: SnapshotStore, item: ReviewItem
) -> dict[str, str] | str:
    """The other vendor's field text per corresponding member column, re-read from the retained
    page with the reader and identifiers that gated it, or why there is none."""
    if item.read is None:
        return READ_NOT_RECORDED
    if isinstance(item.read, ReadGap):
        return item.read.value
    record, body = _retained(pool, snapshots, item.read)
    fields = CORRESPONDENCES[item.vendor]
    if item.vendor is ScreenVendor.SCREENER:
        if item.tijori_slug is None or item.tijori_company_id is None or item.nse_code is None:
            return GATE_NOT_RECORDED
        details = _company_details(body, item.tijori_slug, item.nse_code, item.tijori_company_id)
        return {column: getattr(details, field).raw_text for column, field in fields.items()}
    block = top_ratios_list(parse_document(body.decode("utf-8", errors="replace")))
    ratios = (
        ()
        if block is None
        else read_quick_ratios(
            None,
            element=block,
            url=None,
            document_id=PAGE_QUICK_RATIOS_DOCUMENT_ID,
            body_sha256=hashlib.sha256(body).hexdigest(),
            source_id=record.request.source_id,
            retrieved_at=record.retrieved_at,
            parse=parse_document,
            configured_by_account=False,
            identity_strength=IdentityStrength.PAGE_ASSERTED,
            binding=Binding.PAGE_ASSERTED,
        ).ratios
    )
    texts = {ratio.name: ratio.raw_text for ratio in ratios}
    return {column: texts.get(field, FIELD_NOT_EXPOSED) for column, field in fields.items()}


def _company_details(
    body: bytes, slug: str, symbol: str, company_id: int
) -> TijoriCompanyDetailsSection:
    """The overview's company details section alone, after its identity gate against the
    given Tijori identifiers."""
    sections = TijoriSource.parse_overview_bytes(
        body,
        slug=slug,
        expected_symbol=symbol,
        expected_company_id=company_id,
        section=TijoriOverviewSection.COMPANY_DETAILS,
    )
    (details,) = [s for s in sections if isinstance(s, TijoriCompanyDetailsSection)]
    return details


def _capture(
    unit: VerificationUnit, surface: tuple[str, str], url: str, body: bytes, at: datetime
) -> Capture:
    """A read response ready for ``store_captures``."""
    source_id, name = surface
    return Capture(
        request=Request(unit=unit, source_id=source_id, surface=name, url=url),
        response=Response(outcome=OK, body=body, retrieved_at=at),
    )


def _retained(
    pool: ConnectionPool, snapshots: SnapshotStore, capture_ref_id: int
) -> tuple[CaptureRecord, bytes]:
    """A registered capture's record and verified bytes; an expired or purging one refuses."""
    (ref,) = EvidenceRepository(pool).get_capture_refs([capture_ref_id])
    return read_retained(pool, snapshots, ref)
