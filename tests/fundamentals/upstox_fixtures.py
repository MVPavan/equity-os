"""Synthetic Upstox wire bodies and captures, shared by the Upstox test modules.

Every value here is invented. The ISINs use a ``999Z`` issuer block that no real
issuer holds and carry correct ISO 6166 check digits, so the entity map accepts
them for the reason a real ISIN would rather than by accident. The names are
placeholders — nothing captured from the owner's licensed account is committed
to this repository.

Bodies are built rather than stored so a test can state the exact shape it is
pinning: a BSE row without ``security_type``, a row carrying ``cas_eligible``
only when true, a vendor key nobody modelled yet.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxFetch,
    UpstoxSurface,
    route_for,
)

FIXTURE_STAMP = datetime(2026, 9, 4, 6, 30, tzinfo=UTC)

NSE_ISIN = "INE999Z01012"
BSE_ISIN = "INE999Z01020"
DUAL_ISIN = "INE999Z01038"

NSE_SYMBOL = "FIXTURECO"
BSE_SCRIP = "590999"


def nse_equity_row(**overrides: Any) -> dict[str, Any]:
    """One ``NSE_EQ``/``EQ`` record with every always-present field."""
    row: dict[str, Any] = {
        "segment": "NSE_EQ",
        "exchange": "NSE",
        "name": "FIXTURE COMPANY LIMITED",
        "isin": NSE_ISIN,
        "instrument_type": "EQ",
        "instrument_key": f"NSE_EQ|{NSE_ISIN}",
        "trading_symbol": NSE_SYMBOL,
        "exchange_token": "10001",
        "lot_size": 1,
        "freeze_quantity": 100000.0,
        "tick_size": 5.0,
        "short_name": "FIXTURE",
        "security_type": "NORMAL",
    }
    row.update(overrides)
    return row


def bse_equity_row(**overrides: Any) -> dict[str, Any]:
    """One ``BSE_EQ``/``A`` record — which never carries ``security_type``."""
    row: dict[str, Any] = {
        "segment": "BSE_EQ",
        "exchange": "BSE",
        "name": "FIXTURE COMPANY LIMITED",
        "isin": BSE_ISIN,
        "instrument_type": "A",
        "instrument_key": f"BSE_EQ|{BSE_ISIN}",
        "trading_symbol": "FIXTURECO",
        "exchange_token": BSE_SCRIP,
        "lot_size": 1,
        "freeze_quantity": 100000.0,
        "tick_size": 1.0,
    }
    row.update(overrides)
    return row


def derivative_row(**overrides: Any) -> dict[str, Any]:
    """One non-equity record, which the equity filter must drop before validation."""
    row: dict[str, Any] = {
        "segment": "NSE_FO",
        "exchange": "NSE",
        "name": "FIXTURE COMPANY LIMITED",
        "instrument_type": "FUT",
        "instrument_key": "NSE_FO|36708",
        "trading_symbol": "FIXTURECO FUT 25 SEP 26",
        "exchange_token": "36708",
        "lot_size": 500,
        "freeze_quantity": 50000.0,
        "tick_size": 5.0,
        "expiry": 1790000000000,
    }
    row.update(overrides)
    return row


def suspended_row(**overrides: Any) -> dict[str, Any]:
    """One suspended record — twelve fields, all required, nothing optional."""
    row: dict[str, Any] = {
        "segment": "NSE_EQ",
        "exchange": "NSE",
        "name": "FIXTURE DELISTED LIMITED",
        "isin": "INE999Z01046",
        "instrument_type": "BE",
        "instrument_key": "NSE_EQ|INE999Z01046",
        "trading_symbol": "FIXTUREOLD",
        "exchange_token": "10009",
        "lot_size": 1,
        "freeze_quantity": 100000.0,
        "tick_size": 1.0,
        "qty_multiplier": 1.0,
    }
    row.update(overrides)
    return row


def gzip_body(rows: list[dict[str, Any]]) -> bytes:
    """Gzip one JSON array exactly as the vendor's static files carry it."""
    return gzip.compress(json.dumps(rows).encode("utf-8"), mtime=0)


def fetch_of(
    payload: bytes,
    *,
    route_key: str = "complete",
    surface: UpstoxSurface = UpstoxSurface.INSTRUMENTS,
    media_type: str | None = "application/gzip",
    retrieved_at: datetime = FIXTURE_STAMP,
) -> UpstoxFetch:
    """Wrap raw bytes in the capture a real fetch would have produced."""
    route = route_for(surface, route_key)
    return UpstoxFetch(
        raw_body=payload,
        capture=UpstoxCapture(
            surface=surface,
            route_key=route_key,
            request_url=f"{route.origin}{route.path_template}",
            http_status=200,
            media_type=media_type,
            byte_count=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            outcome=AcquisitionOutcome.OK,
            retrieved_at=retrieved_at,
        ),
    )


def instruments_fetch(rows: list[dict[str, Any]]) -> UpstoxFetch:
    """A complete-instruments fetch over synthetic rows."""
    return fetch_of(gzip_body(rows))


def suspended_fetch(rows: list[dict[str, Any]]) -> UpstoxFetch:
    """A suspended-instruments fetch over synthetic rows."""
    return fetch_of(gzip_body(rows), route_key="suspended")
