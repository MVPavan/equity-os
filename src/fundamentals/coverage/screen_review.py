"""Screen review items, the owner's dispositions and one other-vendor read per item (plan
D7-screen-export S5).

The items are ``eqos.screen_review_items``; an item is pending until its one disposition. A
member's values are its row of the run's results capture, never a copy. After an export commits,
each pending bound item whose NSE symbol names a watchlist stock with verified other-vendor ids
gets one identity-gated page of the other vendor, retained as a capture; every other pending item
records why it has none. Values print as vendor text side by side, never compared or stored.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import LiteralString

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import SourceIdentifiers, StockConfig
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.review_queue import DispositionKind
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.contracts.source_catalog import SCREENER_PAGE, TIJORI_OVERVIEW
from fundamentals.entity.discovery import OK, Capture, Request, Response, store_captures
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
from fundamentals.ingest.tijori_overview_models import TijoriCompanyDetailsSection
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriError
from fundamentals.store.snapshot_store import SnapshotStore

FIELD_NOT_EXPOSED = "FIELD_NOT_EXPOSED"
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
_PENDING: LiteralString = (
    "SELECT member_id, vendor, status, reason, nse_code, candidate_member_ids "
    "FROM eqos.screen_review_pending WHERE pair_id = %s ORDER BY member_id"
)
_INSERT_DISPOSITION: LiteralString = (
    "INSERT INTO eqos.screen_member_dispositions (pair_id, member_id, kind, reason, "
    "evidence_ref) VALUES (%s, %s, %s, %s, %s)"
)
_INSERT_READ: LiteralString = (
    "INSERT INTO eqos.screen_other_vendor_reads (pair_id, member_id, capture_ref_id, gap) "
    "VALUES (%s, %s, %s, %s)"
)
_CAPTURE_OF: LiteralString = (
    "SELECT c.source_id, c.surface, c.request_key, c.capture_id FROM eqos.capture_refs c "
    "WHERE c.id = %s"
)
_ROW_OF: LiteralString = (
    "SELECT m.row_number, r.capture_ref_id FROM eqos.screen_members m "
    "JOIN eqos.screen_runs r ON r.id = m.screen_run_id WHERE m.id = %s"
)
_NO_READ = "pair {pair} member {member} has no other-vendor read recorded"
_NO_STOCK = "{symbol} has a retained read but is no longer a watchlist stock"
_READ_OF: LiteralString = (
    "SELECT capture_ref_id, gap FROM eqos.screen_other_vendor_reads "
    "WHERE pair_id = %s AND member_id = %s"
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
    """One pending item of a pair."""

    model_config = ConfigDict(frozen=True)

    pair_id: int
    member_id: int
    vendor: ScreenVendor
    status: ItemStatus
    reason: str | None
    nse_code: str | None
    candidate_member_ids: tuple[int, ...]


def pending_items(pool: ConnectionPool, pair_id: int) -> tuple[ReviewItem, ...]:
    """The pair's items without a disposition, by member."""
    with pool.connection() as conn:
        found = conn.execute(_PENDING, (pair_id,)).fetchall()
    return tuple(
        ReviewItem(
            pair_id=pair_id,
            member_id=member,
            vendor=vendor,
            status=status,
            reason=reason,
            nse_code=nse,
            candidate_member_ids=tuple(candidates),
        )
        for member, vendor, status, reason, nse, candidates in found
    )


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
    """One identity-gated page of the other vendor for a bound item, or why there is none."""
    if item.status is ItemStatus.UNRESOLVED:
        return ReadGap.MEMBER_UNRESOLVED
    ids = None if stock is None else stock.identifiers
    if item.vendor is ScreenVendor.SCREENER:
        if ids is None or ids.unverified_tijori_fields():
            return ReadGap.NOT_VERIFIED
        tijori_pacer.wait_for_slot()
        try:
            body = tijori.fetch_overview_bytes(ids.tijori_slug)
            _overview(body, ids)
        except TijoriError:
            return ReadGap.READ_REFUSED
        url = tijori.config.overview_url_template.format(
            base=tijori.config.base_url, slug=ids.tijori_slug
        )
        return _capture(VerificationUnit.TIJORI, TIJORI_OVERVIEW, url, body, datetime.now(UTC))
    if ids is None or ids.unverified_screener_fields():
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
    pool: ConnectionPool, snapshots: SnapshotStore, item: ReviewItem, read: Capture | ReadGap
) -> None:
    """Retain a read's bytes and record it against the item, or record the item's gap."""
    ref, gap = None, read if isinstance(read, ReadGap) else None
    if isinstance(read, Capture):
        with snapshots.prepare_ordinary_output():
            ((_, stored),) = store_captures(snapshots, EvidenceRepository(pool), [read])
        ref = stored.capture_ref_id
    with pool.connection() as conn:
        conn.execute(_INSERT_READ, (item.pair_id, item.member_id, ref, gap))


def member_row(pool: ConnectionPool, snapshots: SnapshotStore, item: ReviewItem) -> dict[str, str]:
    """The member's row, hydrated verbatim from its run's results capture."""
    with pool.connection() as conn:
        ((number, capture_ref_id),) = conn.execute(_ROW_OF, (item.member_id,)).fetchall()
    rows = result_rows(item.vendor, _capture_bytes(pool, snapshots, capture_ref_id)[1])
    return rows[int(number) - 1]


def other_values(
    pool: ConnectionPool, snapshots: SnapshotStore, item: ReviewItem, stock: StockConfig | None
) -> dict[str, str] | ReadGap:
    """The other vendor's corresponding fields as text, re-read from the retained page with the
    reader that gated it, or the item's gap."""
    with pool.connection() as conn:
        found = conn.execute(_READ_OF, (item.pair_id, item.member_id)).fetchone()
    if found is None:
        raise ValueError(_NO_READ.format(pair=item.pair_id, member=item.member_id))
    capture_ref_id, gap = found
    if gap is not None:
        return ReadGap(gap)
    if stock is None:
        raise ValueError(_NO_STOCK.format(symbol=item.nse_code))
    record, body = _capture_bytes(pool, snapshots, capture_ref_id)
    fields = CORRESPONDENCES[item.vendor].values()
    if item.vendor is ScreenVendor.SCREENER:
        details = _overview(body, stock.identifiers)
        return {field: getattr(details, field).raw_text for field in fields}
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
    return {field: texts.get(field, FIELD_NOT_EXPOSED) for field in fields}


def _overview(body: bytes, ids: SourceIdentifiers) -> TijoriCompanyDetailsSection:
    """The overview's company details, after its identity gate against the watchlist ids."""
    sections = TijoriSource.parse_overview_bytes(
        body,
        slug=ids.tijori_slug,
        expected_symbol=ids.nse_symbol,
        expected_company_id=ids.tijori_company_id,
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


def _capture_bytes(
    pool: ConnectionPool, snapshots: SnapshotStore, capture_ref_id: int
) -> tuple[CaptureRecord, bytes]:
    """A registered capture's record and verified bytes."""
    with pool.connection() as conn:
        (ref,) = conn.execute(_CAPTURE_OF, (capture_ref_id,)).fetchall()
    return snapshots.read_capture_verified(*ref)
