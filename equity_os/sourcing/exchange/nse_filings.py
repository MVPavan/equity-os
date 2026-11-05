"""NSE filing listings and the filing-window rule (plan D6 D1.3, D2, D4.2 step 2).

Both listings are requested raw for every basis: the legacy ``corporates-financial-results``
and the ``integrated-filing-results`` listing. The filing-window rule, shared in reading with
selection and the holdout checker (D1.3 and its 2026-10-16 clarification): the window is the
six latest calendar quarter-ends on or before ``as_of``; rows of both listings with a basis and
a period end in the window, identical parsed rows counted once, collapse to the latest broadcast
per ``(period_end, basis)``; a group holding a row with a missing or empty broadcast time is left
out; a tie on the latest broadcast is reported.
Qualifying filings are collapsed integrated ``Financials`` rows on the consolidated basis.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict

NSE_API = "https://www.nseindia.com/api"
EQUITY_MASTER_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
LEGACY_LISTING = ("corporates-financial-results", "quarterly")
INTEGRATED_LISTING = ("integrated-filing-results", "Quarterly")
WINDOW_QUARTERS = 6
CONSOLIDATED = "Consolidated"
FINANCIALS = "Integrated Filing- Financials"
_DAY = "%d-%b-%Y"
_MOMENT = "%d-%b-%Y %H:%M:%S"
_DATA = "data"
_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))


class ListingRow(BaseModel):
    """One listing row with a basis: its period end, broadcast time and XBRL link."""

    model_config = ConfigDict(frozen=True)

    period_end: date
    basis: str
    broadcast: datetime | None
    integrated: bool
    kind: str | None
    xbrl_url: str | None

    @property
    def qualifies(self) -> bool:
        """An integrated Financials row on the consolidated basis."""
        return self.integrated and self.kind == FINANCIALS and self.basis == CONSOLIDATED


class FilingWindow(BaseModel):
    """The collapsed window: qualifying filings (latest period first) and bases present."""

    model_config = ConfigDict(frozen=True)

    filings: tuple[ListingRow, ...]
    consolidated: bool
    standalone: bool
    tied: bool


def listing_url(path: str, symbol: str, period: str) -> str:
    """One NSE listing request for every basis of the symbol."""
    query = urlencode({"index": "equities", "period": period, "symbol": symbol})
    return f"{NSE_API}/{path}?{query}"


def listing_rows(legacy: bytes, integrated: bytes) -> list[ListingRow]:
    """Rows with a basis from both listings (legacy: ``toDate``; integrated: ``qe_Date``)."""
    found = []
    for body, is_integrated in ((legacy, False), (integrated, True)):
        for row in _items(json.loads(body)):
            basis = row.get("consolidated")
            end = row.get("qe_Date" if is_integrated else "toDate")
            if not basis or not end:
                continue
            when = (row.get("broadcast_Date" if is_integrated else "broadCastDate") or "").strip()
            found.append(
                ListingRow(
                    period_end=datetime.strptime(end, _DAY).date(),
                    basis=basis,
                    broadcast=datetime.strptime(when, _MOMENT) if when else None,
                    integrated=is_integrated,
                    kind=row.get("type"),
                    xbrl_url=(row.get("xbrl") or "").strip() or None,
                )
            )
    return found


def filing_window(rows: Sequence[ListingRow], as_of: date) -> FilingWindow:
    """Collapse the rows in the window and keep the qualifying ones (D1.3)."""
    window = quarter_ends(as_of)
    groups: dict[tuple[date, str], list[ListingRow]] = defaultdict(list)
    for row in dict.fromkeys(rows):  # an identical row listed twice is one filing
        if row.period_end in window:
            groups[row.period_end, row.basis].append(row)
    latest: list[ListingRow] = []
    tied = False
    for group in groups.values():
        times = [row.broadcast for row in group]
        if any(when is None for when in times):
            continue
        top = [row for row in group if row.broadcast == max(t for t in times if t)]
        tied = tied or len(top) > 1
        latest.append(top[0])
    return FilingWindow(
        filings=tuple(
            sorted((r for r in latest if r.qualifies), key=lambda r: r.period_end, reverse=True)
        ),
        consolidated=any(row.basis == CONSOLIDATED for row in latest),
        standalone=any(row.basis != CONSOLIDATED for row in latest),
        tied=tied,
    )


def quarter_ends(as_of: date) -> set[date]:
    """The six latest calendar quarter-ends on or before ``as_of``."""
    ends = [
        date(year, month, day)
        for year in range(as_of.year - 2, as_of.year + 1)
        for month, day in _QUARTER_ENDS
    ]
    return set([end for end in ends if end <= as_of][-WINDOW_QUARTERS:])


def _items(payload: Any) -> list[dict[str, Any]]:
    """A listing's rows, whether served as a list or under ``data``."""
    items = payload.get(_DATA) if isinstance(payload, dict) else payload
    return [row for row in items or [] if isinstance(row, dict)]
