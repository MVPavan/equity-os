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
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fundamentals.ingest.upstox_instruments import read_instrument_catalog
from fundamentals.ingest.upstox_source import (
    DEFAULT_ROUTE_KEY,
    AcquisitionOutcome,
    UpstoxCapture,
    UpstoxFetch,
    UpstoxRoute,
    UpstoxSurface,
    route_for,
)

FIXTURE_STAMP = datetime(2026, 9, 4, 6, 30, tzinfo=UTC)

# Four megabytes: far above any synthetic body here and far below the ~55 MB the
# real file expands to, so a fixture can never pass by riding the production cap.
MAX_DECOMPRESSED_BYTES = 4 * 1024 * 1024
PARSED_CATALOG_FILENAME = "upstox_instruments.parsed.json"

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
        "qty_multiplier": 1.0,
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
        "qty_multiplier": 1.0,
    }
    row.update(overrides)
    return row


def trade_to_trade_row(**overrides: Any) -> dict[str, Any]:
    """One company in NSE series ``BE`` — trade-to-trade, and still a company.

    Two of ten pinned watchlist stocks look exactly like this. A filter on
    ``instrument_type`` dropped them.
    """
    return nse_equity_row(instrument_type="BE", **overrides)


def etf_row(**overrides: Any) -> dict[str, Any]:
    """One ETF sitting in ``NSE_EQ``/``EQ`` — an ``INF`` issuer, not a company.

    176 of these ride in the same segment and instrument_type as real equities,
    which is why the trading series cannot be the discriminator.
    """
    return nse_equity_row(isin="INF999Z1A012", instrument_key="NSE_EQ|INF999Z1A012", **overrides)


def debenture_row(**overrides: Any) -> dict[str, Any]:
    """One company debenture — an ``INE`` issuer, but issue-type ``07``."""
    return nse_equity_row(isin="INE999Z07016", instrument_key="NSE_EQ|INE999Z07016", **overrides)


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


def write_parsed_catalog(directory: Path, *rows: dict[str, Any]) -> Path:
    """Write a parsed instrument catalog artifact into ``directory`` and return its path.

    Shared by every test that reads a catalog off disk, so the two consumers
    cannot drift on the filename or the decompression cap they exercise.
    """
    catalog = read_instrument_catalog(
        instruments_fetch(list(rows)), max_decompressed_bytes=MAX_DECOMPRESSED_BYTES
    )
    path = directory / PARSED_CATALOG_FILENAME
    path.write_text(catalog.model_dump_json(), encoding="utf-8")
    return path


def statement_fetch(body: dict[str, Any], *, surface: UpstoxSurface) -> UpstoxFetch:
    """A Lane B fundamentals fetch over a synthetic JSON body."""
    return fetch_of(
        json.dumps(body).encode("utf-8"),
        route_key=DEFAULT_ROUTE_KEY,
        surface=surface,
        media_type="application/json",
    )


def _history(values: list[tuple[str, float]], *, changes: bool = True) -> list[dict[str, Any]]:
    """A summary history, most-recent-first, with ``change`` absent on the oldest.

    The absence is not tidiness: the live probe found ``change`` missing on the
    oldest period of every one of the 18 observed series.
    """
    points: list[dict[str, Any]] = []
    for index, (period, value) in enumerate(values):
        point: dict[str, Any] = {"value": value, "period": period}
        if changes and index < len(values) - 1:
            point["change"] = "+10.0%"
        points.append(point)
    return points


def _particular(name: str, values: list[tuple[str, float]]) -> dict[str, Any]:
    """One ``full_statement`` row — no ``change`` key on any period."""
    return {
        "particular": name,
        "history": [{"value": value, "period": period} for period, value in values],
    }


ANNUAL_PERIODS = ["Mar 2026", "Mar 2025"]
QUARTERLY_PERIODS = ["Jun 2026", "Mar 2026"]


def income_statement_body(
    *,
    time_period: str = "yearly",
    basis: str = "standalone",
    summary_periods: list[str] | None = None,
    full_statement: list[dict[str, Any]] | None = None,
    revenue: tuple[float, float] = (200.0, 150.0),
    operating_profit: tuple[float, float] = (40.0, 30.0),
    net_profit: tuple[float, float] = (30.0, 22.0),
) -> dict[str, Any]:
    """An ``income-statement`` body in the verified live shape."""
    periods = summary_periods or ANNUAL_PERIODS
    rows = [
        {"category": "revenue", "history": _history(list(zip(periods, revenue, strict=True)))},
        {
            "category": "operating_profit",
            "history": _history(list(zip(periods, operating_profit, strict=True))),
        },
        {
            "category": "net_profit",
            "history": _history(list(zip(periods, net_profit, strict=True))),
        },
    ]
    if full_statement is None:
        full_statement = [
            _particular("Revenue", list(zip(ANNUAL_PERIODS, (190.0, 142.0), strict=True))),
            _particular("Other Income", list(zip(ANNUAL_PERIODS, (10.0, 8.0), strict=True))),
            _particular("Total Revenue", list(zip(ANNUAL_PERIODS, revenue, strict=True))),
            _particular("Total Expenses", list(zip(ANNUAL_PERIODS, (160.0, 120.0), strict=True))),
            _particular(
                "Profit Before Tax", list(zip(ANNUAL_PERIODS, operating_profit, strict=True))
            ),
            _particular("Tax", list(zip(ANNUAL_PERIODS, (10.0, 8.0), strict=True))),
            _particular("Profit After Tax", list(zip(ANNUAL_PERIODS, net_profit, strict=True))),
            _particular("EPS - Basic", list(zip(ANNUAL_PERIODS, (3.0, 2.2), strict=True))),
            _particular("EPS - Diluted", list(zip(ANNUAL_PERIODS, (2.9, 2.1), strict=True))),
        ]
    return {
        "status": "success",
        "data": {
            "type": basis,
            "time_period": time_period,
            "units_in": "crore",
            "income_statement": rows,
            "full_statement": full_statement,
        },
    }


def balance_sheet_body(*, basis: str = "standalone") -> dict[str, Any]:
    """A ``balance-sheet`` body — note the singular summary keys."""
    return {
        "status": "success",
        "data": {
            "type": basis,
            "time_period": "yearly",
            "units_in": "crore",
            "history": [
                {"total_asset": 600.0, "total_liability": 440.0, "period": "Mar 2026"},
                {"total_asset": 500.0, "total_liability": 380.0, "period": "Mar 2025"},
            ],
            "full_statement": [
                _particular("Non-Current Assets", [("Mar 2026", 300.0), ("Mar 2025", 250.0)]),
                _particular("Current Assets", [("Mar 2026", 300.0), ("Mar 2025", 250.0)]),
                _particular("Total Assets", [("Mar 2026", 600.0), ("Mar 2025", 500.0)]),
            ],
        },
    }


def cash_flow_body(*, basis: str = "standalone") -> dict[str, Any]:
    """A ``cash-flow`` body — three categories, signed values, optional ``change``."""
    return {
        "status": "success",
        "data": {
            "type": basis,
            "time_period": "yearly",
            "units_in": "crore",
            "cash_flow": [
                {
                    "category": "operating",
                    "history": _history([("Mar 2026", 55.0), ("Mar 2025", 40.0)]),
                },
                {
                    "category": "investing",
                    "history": _history([("Mar 2026", -30.0), ("Mar 2025", -25.0)]),
                },
                {
                    "category": "financing",
                    "history": _history([("Mar 2026", -12.0), ("Mar 2025", -9.0)]),
                },
            ],
            "full_statement": [
                _particular("Profit before tax", [("Mar 2026", 40.0), ("Mar 2025", 30.0)]),
                _particular("Total Cash Flow", [("Mar 2026", 13.0), ("Mar 2025", 6.0)]),
            ],
        },
    }


def key_ratios_body(*, include_quick_ratio: bool = True) -> dict[str, Any]:
    """A ``key-ratios`` body — a bare array of string values, some percentages.

    ``Quick Ratio`` is optional because it genuinely is: one of the three live
    issuers returned six rows without it while the other two returned seven.
    """
    rows: list[dict[str, Any]] = [
        {"name": "P/E", "company_value": "76.45", "sector_value": "78.35"},
        {"name": "P/B", "company_value": "28.04", "sector_value": "3.18"},
        {"name": "ROA", "company_value": "9.51%", "sector_value": "15.57%"},
        {"name": "ROE", "company_value": "32.31%", "sector_value": "9.7%"},
        {"name": "ROCE", "company_value": "24.83%", "sector_value": "11.24%"},
    ]
    if include_quick_ratio:
        rows.append({"name": "Quick Ratio", "company_value": "0.2", "sector_value": "1.22"})
    rows.append({"name": "EV/EBITDA", "company_value": "48.35", "sector_value": "-9.01"})
    return {"status": "success", "data": rows}


# The three Lane B statement surfaces, in the order the crosscheck asks for them.
STATEMENT_SURFACES: tuple[UpstoxSurface, ...] = (
    UpstoxSurface.INCOME_STATEMENT,
    UpstoxSurface.BALANCE_SHEET,
    UpstoxSurface.CASH_FLOW,
)

SCREENER_PERIODS: tuple[str, ...] = ("Mar 2026", "Mar 2025")

# The Screener side of the crosscheck fixture: the row labels the name map reads
# and values that agree with the bodies above. Held here rather than inside a
# section writer so a test can build the same sections in memory.
SCREENER_SECTION_ROWS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "profit-loss": (
        ("Sales", ("190", "142")),
        ("Other Income", ("10", "8")),
        ("Profit before tax", ("40", "30")),
        ("Net Profit", ("30", "22")),
    ),
    "balance-sheet": (
        ("Total Assets", ("600", "500")),
        ("Total Liabilities", ("440", "380")),
    ),
    "cash-flow": (
        ("Cash from Operating Activity", ("55", "40")),
        ("Cash from Investing Activity", ("-30", "-25")),
        ("Cash from Financing Activity", ("-12", "-9")),
    ),
}


class StubSource:
    """A transport that answers from a body table and records what was asked."""

    def __init__(self, bodies: Mapping[UpstoxSurface, dict[str, Any]]) -> None:
        self.bodies = bodies
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        self.calls.append((route.surface.value, query))
        return statement_fetch(self.bodies[route.surface], surface=route.surface)

    def redact(self, text: str) -> str:
        return text


def statement_bodies(basis: str = "standalone") -> dict[UpstoxSurface, dict[str, Any]]:
    """The three statement bodies one company answers with on one basis."""
    return {
        UpstoxSurface.INCOME_STATEMENT: income_statement_body(basis=basis),
        UpstoxSurface.BALANCE_SHEET: balance_sheet_body(basis=basis),
        UpstoxSurface.CASH_FLOW: cash_flow_body(basis=basis),
    }


def screener_section_payload(section: str) -> dict[str, Any]:
    """One ``section_*.json`` body, as the crosscheck's narrow model reads it."""
    return {
        "section": section,
        "table_id": f"{section}-table",
        "outcome": "ok",
        "unit_statement": "Consolidated Figures in Rs. Crores",
        "periods": [
            {"index": index, "label": label, "kind": "date"}
            for index, label in enumerate(SCREENER_PERIODS)
        ],
        "rows": [
            {
                "position": position,
                "label": label,
                "status": "modeled",
                "unit": "rs_crore",
                "cells": [
                    {
                        "period_index": index,
                        "value": text,
                        "raw_text": text,
                        "published": True,
                        "provenance": {
                            "source_id": "screener",
                            "file_sha256": "0" * 64,
                            "anchor_type": "HTML_TABLE",
                            "table_id": f"{section}-table",
                            "row_path": label,
                            "column_index": index,
                            "column_label": SCREENER_PERIODS[index],
                            "retrieved_at": "2026-09-04T06:30:00Z",
                        },
                    }
                    for index, text in enumerate(texts)
                ],
            }
            for position, (label, texts) in enumerate(SCREENER_SECTION_ROWS[section])
        ],
    }


def screener_root(tmp_path: Path, symbol: str, basis: str = "standalone") -> Path:
    """A Screener financials tree holding the three sections the map reads."""
    root = tmp_path / "screener"
    directory = root / symbol / basis
    directory.mkdir(parents=True, exist_ok=True)
    for section in SCREENER_SECTION_ROWS:
        (directory / f"section_{section}.json").write_text(
            json.dumps(screener_section_payload(section)), encoding="utf-8"
        )
    return root
