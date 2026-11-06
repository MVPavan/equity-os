"""Approved origins and request URL templates for the onboarding discovery surfaces."""

from __future__ import annotations

from urllib.parse import urlencode

from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.sourcing.source_catalog import (
    BSE_PEER_SEARCH,
    DOCUMENT_LISTINGS,
    DOCUMENT_ORIGINS,
    NSE_GROUNDING_PDF,
    NSE_GROUNDING_XBRL,
    NSE_INTEGRATED_LISTING,
    NSE_MASTER,
    NSE_RESULTS_LISTING,
    NSE_XBRL_INSTANCE,
    NSE_XBRL_STANDALONE,
    SCREENER_PAGE,
    SCREENER_SEARCH,
    TIJORI_DOCUMENT_SURFACES,
    TIJORI_OVERVIEW,
    TIJORI_PAGE,
    TIJORI_SEARCH,
    UPSTOX_INSTRUMENTS,
    UPSTOX_STATEMENT,
)

_NSE_WWW, _NSE_ARCHIVES = "www.nseindia.com", "nsearchives.nseindia.com"
_SCREENER, _TIJORI = "www.screener.in", "www.tijorifinance.com"
# The only origin each surface may be requested from (https, exact host): a listing's XBRL link
# or any other evidenced URL cannot send an authorised request elsewhere.
ORIGINS = {
    NSE_MASTER: _NSE_ARCHIVES,
    NSE_RESULTS_LISTING: _NSE_WWW,
    NSE_INTEGRATED_LISTING: _NSE_WWW,
    NSE_XBRL_INSTANCE: _NSE_ARCHIVES,
    NSE_XBRL_STANDALONE: _NSE_ARCHIVES,
    NSE_GROUNDING_XBRL: _NSE_ARCHIVES,
    NSE_GROUNDING_PDF: _NSE_ARCHIVES,
    BSE_PEER_SEARCH: "api.bseindia.com",
    SCREENER_SEARCH: _SCREENER,
    SCREENER_PAGE: _SCREENER,
    TIJORI_SEARCH: _TIJORI,
    TIJORI_PAGE: _TIJORI,
    TIJORI_OVERVIEW: _TIJORI,
    **dict.fromkeys(TIJORI_DOCUMENT_SURFACES, "files.tijorifinance.com"),
    UPSTOX_INSTRUMENTS: "assets.upstox.com",
    UPSTOX_STATEMENT: "api.upstox.com",
}
ORIGINS |= DOCUMENT_ORIGINS | {("nse", surface): _NSE_WWW for surface in DOCUMENT_LISTINGS}
BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text={isin}"
SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/?{query}"
SCREENER_PAGE_URL = "https://www.screener.in/company/{symbol}/{path}"
TIJORI_SEARCH_URL = "https://www.tijorifinance.com/api/v1/ind/company_search/?q={isin}"
TIJORI_PAGE_URL = "https://www.tijorifinance.com/company/{slug}/financials/"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
STATEMENT_URL = (
    "https://api.upstox.com/v2/fundamentals/{isin}/income-statement"
    "?fs=true&time_period=quarterly&type={basis}"
)
_SCREENER_PATH = {Basis.CONSOLIDATED: "consolidated/", Basis.STANDALONE: ""}


def screener_search_url(symbol: str) -> str:
    """The Screener search request for ``symbol``, its query URL-encoded (``M&M`` is one value)."""
    return SCREENER_SEARCH_URL.format(query=urlencode({"q": symbol, "v": 3, "fts": 1}))


def screener_page_url(symbol: str, basis: Basis) -> str:
    """The Screener company page of one basis (a standalone page has no path suffix)."""
    return SCREENER_PAGE_URL.format(symbol=symbol, path=_SCREENER_PATH[basis])


def statement_url(isin: str, basis: Basis) -> str:
    """The Upstox quarterly income statement of one basis."""
    return STATEMENT_URL.format(isin=isin, basis=basis.value.lower())
