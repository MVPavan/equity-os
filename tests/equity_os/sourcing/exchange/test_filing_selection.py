"""VENDOR-1 P1 closing review, findings 2 and 4: which NSE listing rows decide the basis and
which row fallback fetches (spec 2026-11-06-vendor-first §6.2, §6.8). All rows are SYNTHETIC."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from equity_os.contracts.measurement.canonical import Basis
from equity_os.sourcing.exchange.nse_filings import (
    ListingRow,
    filing_for,
    filing_window,
    listing_rows,
)

JUN, MAR = date(2026, 6, 30), date(2026, 3, 31)


def _integrated(end: str, basis: str, at: str | None, xbrl: str) -> dict[str, Any]:
    return {
        "qe_Date": end,
        "consolidated": basis,
        "broadcast_Date": at,
        "type": "Integrated Filing- Financials",
        "xbrl": xbrl,
    }


def _legacy(end: str, basis: str, at: str | None, xbrl: str) -> dict[str, Any]:
    return {"toDate": end, "consolidated": basis, "broadCastDate": at, "xbrl": xbrl}


def _rows(integrated: list[dict[str, Any]], legacy: list[dict[str, Any]]) -> list[ListingRow]:
    return listing_rows(json.dumps(legacy).encode(), json.dumps({"data": integrated}).encode())


def test_a_consolidated_row_without_a_broadcast_keeps_the_consolidated_path() -> None:
    """§6.2: any consolidated row in the window keeps the consolidated basis, even when its
    missing broadcast leaves no usable consolidated filing; the two good standalone filings must
    not make the issuer standalone-only (onboarding then refuses for too few filings)."""
    window = filing_window(
        _rows(
            [
                _integrated("30-JUN-2026", "Standalone", "30-Jul-2026 17:00:00", "s1.xml"),
                _integrated("31-MAR-2026", "Standalone", "07-May-2026 19:00:00", "s2.xml"),
                _integrated("30-JUN-2026", "Consolidated", None, "c1.xml"),
            ],
            [],
        ),
        date(2026, 8, 1),
    )
    assert window.basis is Basis.CONSOLIDATED and window.consolidated and window.standalone
    assert window.filings == ()


def test_fallback_selects_from_both_listings_by_latest_broadcast() -> None:
    """§6.8: the requested period and basis from either listing, collapsed to the latest
    broadcast; a legacy-only filing is found, a newer legacy revision supersedes an older
    integrated row, and a tie or a missing broadcast selects nothing."""
    legacy_only = _rows([], [_legacy("30-Jun-2026", "Consolidated", "30-Jul-2026 17:00:00", "l")])
    assert _xbrl(filing_for(legacy_only, JUN, "Consolidated")) == "l"
    standalone = _rows(
        [], [_legacy("30-Jun-2026", "Non-Consolidated", "30-Jul-2026 17:00:00", "n")]
    )
    assert _xbrl(filing_for(standalone, JUN, "Standalone")) == "n"
    assert filing_for(standalone, JUN, "Consolidated") is None
    revised = _rows(
        [_integrated("30-JUN-2026", "Consolidated", "30-Jul-2026 17:00:00", "old")],
        [_legacy("30-Jun-2026", "Consolidated", "02-Aug-2026 10:00:00", "new")],
    )
    assert _xbrl(filing_for(revised, JUN, "Consolidated")) == "new"
    assert filing_for(revised, MAR, "Consolidated") is None
    mixed = _rows(
        [_integrated("30-JUN-2026", "Standalone", "30-Jul-2026 17:00:00", "old")],
        [_legacy("30-Jun-2026", "Non-Consolidated", "02-Aug-2026 10:00:00", "new")],
    )
    assert _xbrl(filing_for(mixed, JUN, "Standalone")) == "new"
    tied = _rows(
        [_integrated("30-JUN-2026", "Consolidated", "30-Jul-2026 17:00:00", "a")],
        [_legacy("30-Jun-2026", "Consolidated", "30-Jul-2026 17:00:00", "b")],
    )
    assert filing_for(tied, JUN, "Consolidated") is None
    unbroadcast = _rows(
        [_integrated("30-JUN-2026", "Consolidated", "30-Jul-2026 17:00:00", "a")],
        [_legacy("30-Jun-2026", "Consolidated", None, "b")],
    )
    assert filing_for(unbroadcast, JUN, "Consolidated") is None


def _xbrl(row: ListingRow | None) -> str | None:
    return None if row is None else row.xbrl_url
