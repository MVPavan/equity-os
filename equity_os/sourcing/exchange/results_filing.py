"""One period's NSE results filing for the fallback workflow (spec 2026-11-06-vendor-first §6.8):
both results listings of the named issuer, the requested period's XBRL instance on its basis,
and the results PDF its announcements carry from the period end to seven days after the XBRL
broadcast. Every body is retained and registered; nothing else is requested."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, cast

import psycopg
from pydantic import BaseModel, ConfigDict

from equity_os.companies.onboarding.derived_settings import Filing
from equity_os.companies.onboarding.discovery import (
    OK,
    XBRL_SOURCES,
    Capture,
    Fetch,
    Request,
    Response,
    authorised,
    register_capture,
)
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.sourcing.source_catalog import (
    NSE_INTEGRATED_LISTING,
    NSE_RESULTS_LISTING,
    VENDOR_SURFACES,
    DocumentKind,
)
from equity_os.interface.commands.sourcing.documents_cli import announcement_documents
from equity_os.interface.commands.sourcing.shareholding_cli import PAUSE_SECONDS
from equity_os.sourcing.documents.first_party_documents import (
    ANNOUNCEMENTS,
    DocumentLink,
    document_request,
    nse_listing_url,
    observed_link,
)
from equity_os.sourcing.documents.first_party_documents import listing_rows as announcement_rows
from equity_os.sourcing.exchange.nse_filings import (
    INTEGRATED_LISTING,
    LEGACY_LISTING,
    LISTING_BASIS,
    filing_for,
    listing_rows,
    listing_url,
)
from equity_os.storage.raw_files.capture_retention import Registration
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.document_intake import RETENTION_SHARED

PDF_DAYS = timedelta(days=7)


class ResultsFiling(BaseModel):
    """The acquired filing: its XBRL instance and the earliest results PDF of its span."""

    model_config = ConfigDict(frozen=True)

    xbrl: Filing
    pdf: Filing | None


def acquire_results(
    conn: psycopg.Connection[Any],
    store: SnapshotStore,
    fetch: Fetch,
    *,
    entity_id: int,
    symbol: str,
    isin: str,
    period_end: date,
    basis: Basis,
) -> ResultsFiling | None:
    """The results filing of one period end and basis; ``None`` when no single filing with an
    instance is acquirable (a tie, a missing broadcast or a failed fetch)."""
    legacy, integrated = (
        retain(conn, store, fetch, VerificationUnit.EXCHANGE, pair, listing_url(path, symbol, p))
        for pair, (path, p) in (
            (NSE_RESULTS_LISTING, LEGACY_LISTING),
            (NSE_INTEGRATED_LISTING, INTEGRATED_LISTING),
        )
    )
    if legacy is None or integrated is None:
        return None
    rows = listing_rows(cast(bytes, legacy.body), cast(bytes, integrated.body))
    row = filing_for(rows, period_end, LISTING_BASIS[basis])
    if row is None or row.xbrl_url is None:
        return None
    unit, source = VerificationUnit.XBRL_ENTITY, XBRL_SOURCES[basis]
    instance = retain(conn, store, fetch, unit, source, row.xbrl_url)
    if instance is None:
        return None
    filed = cast(Any, row.broadcast)
    span = (period_end, filed.date() + PDF_DAYS)
    documents = announcement_documents(
        conn, store, fetch, entity_id=entity_id, symbol=symbol, isin=isin, span=span
    )
    pdf = None
    if documents:
        link, record = documents[0]
        pdf = Filing(
            period_end=period_end,
            filed_at=cast(Any, link.filed_at),
            url=link.url,
            body=store.read_body(record),
            retrieved_at=record.retrieved_at,
        )
    xbrl = Filing(
        period_end=period_end,
        filed_at=filed,
        url=row.xbrl_url,
        body=cast(bytes, instance.body),
        retrieved_at=instance.retrieved_at,
    )
    return ResultsFiling(xbrl=xbrl, pdf=pdf)


def results_pdfs(
    conn: psycopg.Connection[Any],
    store: SnapshotStore,
    fetch: Fetch,
    symbol: str,
    span: tuple[date, date],
    pair: tuple[str, str],
) -> list[tuple[DocumentLink, Response]]:
    """Every results-category PDF the symbol's announcements listing files in ``span``, each
    retained on ``pair`` (entity-free, none chosen): its link and response, listing order."""
    url = nse_listing_url(ANNOUNCEMENTS, symbol, *span)
    listing = retain(conn, store, fetch, VerificationUnit.EXCHANGE, ("nse", ANNOUNCEMENTS), url)
    if listing is None:
        return []
    links: dict[str, DocumentLink] = {}
    for _, payload in announcement_rows(ANNOUNCEMENTS, cast(bytes, listing.body)):
        link = observed_link(ANNOUNCEMENTS, payload)
        request = document_request(link) if link else None
        if link and request and link.kind is DocumentKind.RESULTS:
            if span[0] <= cast(datetime, link.filed_at).date() <= span[1]:
                links.setdefault(request.url, link)
    found = (
        (link, retain(conn, store, fetch, VerificationUnit.EXCHANGE, pair, url))
        for url, link in links.items()
    )
    return [(link, response) for link, response in found if response is not None]


def retain(
    conn: psycopg.Connection[Any],
    store: SnapshotStore,
    fetch: Fetch,
    unit: VerificationUnit,
    pair: tuple[str, str],
    url: str,
) -> Response | None:
    """One polite fetch on a pinned surface, its OK body retained and registered."""
    request = Request(unit=unit, source_id=pair[0], surface=pair[1], url=url)
    time.sleep(PAUSE_SECONDS)
    response = fetch(request, authorised(request, VENDOR_SURFACES))
    if response.outcome != OK:
        return None
    with conn.transaction():
        conn.execute(RETENTION_SHARED)
        register_capture(store, Registration(conn), Capture(request=request, response=response))
    return response
