"""Shareholding-pattern acquisition (plan D8): which origin each surface may use, and the
request sequence one generation makes (Task 4; probe §1, §13.1)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from urllib.parse import urlsplit

from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import (
    NSE_MASTER,
    SCREENER_DOCS,
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    SEBI_REGULATION,
    SHP_LISTING,
    SHP_TAXONOMY,
    SHP_XBRL,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
    VENDOR_SURFACES,
    SurfaceAuthority,
    SurfaceNotAuthorisedError,
    surface_authority,
)
from fundamentals.entity import discovery
from fundamentals.entity.discovery import Capture, Fetch, Request
from fundamentals.entity.verification import master_rows
from fundamentals.ingest.nse_filings import EQUITY_MASTER_URL
from fundamentals.ingest.screener_company_models import Periodicity
from fundamentals.ingest.screener_session_page import parse_document, read_identity
from fundamentals.ingest.screener_shareholding import read_shareholding_table

_HTTPS = "https"
LISTING_URL = (
    "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={symbol}"
)
SCREENER_URL = "https://www.screener.in/company/{symbol}/consolidated/"
INVESTORS_URL = "https://www.screener.in/api/3/{company_id}/investors/{bucket}/{periodicity}/"
TIJORI_URL = "https://www.tijorifinance.com/company/{slug}/shareholding/"
UPSTOX_URL = "https://api.upstox.com/v2/fundamentals/{isin}/share-holdings"
LISTING_DATE = "%d-%b-%Y"
# The only origin each D8 surface may be requested from (https, exact host).
SHP_ORIGINS = {
    SHP_LISTING: "www.nseindia.com",
    SHP_XBRL: "nsearchives.nseindia.com",
    SCREENER_SHAREHOLDING: "www.screener.in",
    TIJORI_SHAREHOLDING: "www.tijorifinance.com",
    UPSTOX_SHAREHOLDING: "api.upstox.com",
    SHP_TAXONOMY: "nsearchives.nseindia.com",
    SEBI_REGULATION: "www.sebi.gov.in",
    SCREENER_DOCS: "www.screener.in",
    SCREENER_INVESTORS: "www.screener.in",
}


def authorised(request: Request, table: tuple[SurfaceAuthority, ...]) -> bool:
    """The surface is registered in ``table`` and the URL is on its approved https origin."""
    pair = (request.source_id, request.surface)
    try:
        surface_authority(*pair, table=table)
    except SurfaceNotAuthorisedError:
        return False
    parts = urlsplit(request.url)
    return parts.scheme == _HTTPS and parts.netloc == SHP_ORIGINS.get(pair)


def listing_date(text: object) -> date | None:
    """A listing row's ``DD-MON-YYYY`` shareholding date, or ``None`` when unreadable."""
    try:
        return datetime.strptime(str(text).strip().title(), LISTING_DATE).date()
    except ValueError:
        return None


def acquire(symbol: str, instant: date, fetch: Fetch, *, tijori_slug: str) -> list[Capture]:
    """One generation's requests, in order: the NSE master (``as_of`` and the ISIN), the
    listing, every SHP instance it dates at ``instant`` (revisions included), the Screener page
    and each drill-down hook of its quarterly then yearly table, the Tijori page, and Upstox
    by the master's single EQ ISIN. Each request carries its own authority decision."""
    captures: list[Capture] = []

    def get(unit: VerificationUnit, pair: tuple[str, str], url: str) -> bytes | None:
        request = Request(unit=unit, source_id=pair[0], surface=pair[1], url=url)
        check = discovery.authorised if pair == NSE_MASTER else authorised
        response = fetch(request, check(request, VENDOR_SURFACES))
        captures.append(Capture(request=request, response=response))
        return response.body

    master = get(VerificationUnit.EXCHANGE, NSE_MASTER, EQUITY_MASTER_URL)
    isins = master_rows(master, symbol) if master else []
    listing = get(VerificationUnit.EXCHANGE, SHP_LISTING, LISTING_URL.format(symbol=symbol))
    for row in json.loads(listing) if listing else []:
        link = str(row.get("xbrl", ""))
        if listing_date(row.get("date")) == instant and link.startswith(f"{_HTTPS}://"):
            get(VerificationUnit.XBRL_ENTITY, SHP_XBRL, link)
    page = get(VerificationUnit.SCREENER, SCREENER_SHAREHOLDING, SCREENER_URL.format(symbol=symbol))
    if page is not None:
        root = parse_document(page.decode("utf-8"))
        company_id = read_identity(root)[0]
        retrieved_at = captures[-1].response.retrieved_at
        sha256 = hashlib.sha256(page).hexdigest()
        for periodicity in (Periodicity.QUARTERLY, Periodicity.YEARLY):
            table = read_shareholding_table(
                root,
                periodicity,
                source_id=SCREENER_SHAREHOLDING[0],
                file_sha256=sha256,
                retrieved_at=retrieved_at,
            )
            for row in table.rows if table is not None else ():
                if row.bucket is not None:
                    url = INVESTORS_URL.format(
                        company_id=company_id, bucket=row.bucket, periodicity=periodicity.value
                    )
                    get(VerificationUnit.SCREENER, SCREENER_INVESTORS, url)
    get(VerificationUnit.TIJORI, TIJORI_SHAREHOLDING, TIJORI_URL.format(slug=tijori_slug))
    if len(isins) == 1:
        get(VerificationUnit.UPSTOX, UPSTOX_SHAREHOLDING, UPSTOX_URL.format(isin=isins[0][1]))
    return captures
