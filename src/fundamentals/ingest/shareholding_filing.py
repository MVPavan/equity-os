"""Shareholding-pattern acquisition authority (plan D8): which origin each surface may use."""

from __future__ import annotations

from urllib.parse import urlsplit

from fundamentals.contracts.source_catalog import (
    SCREENER_DOCS,
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    SEBI_REGULATION,
    SHP_LISTING,
    SHP_TAXONOMY,
    SHP_XBRL,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
    SurfaceAuthority,
    SurfaceNotAuthorisedError,
    surface_authority,
)
from fundamentals.entity.discovery import Request

_HTTPS = "https"
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
