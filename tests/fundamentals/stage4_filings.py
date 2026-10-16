"""Stage 4 D1.3 filing rules over NSE listing rows: the filing window (shared by the held-out
draw checks and the Stage 4 manifest oracle) and the XBRL prefilter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any, cast

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.contracts.onboarding import ONBOARDING_VERSIONS
from fundamentals.entity.verification import (
    VERIFIED,
    financial_rule,
    framework_state,
    instance_state,
)
from fundamentals.evidence.mapping import MappingSet, UnsupportedSchemaError, load_mapping_set
from fundamentals.evidence.xbrl_adapter import parse_instance

CONFIG = Path(__file__).resolve().parents[2] / "config"
FINANCIALS, CONSOLIDATED = "Integrated Filing- Financials", "Consolidated"
DAY, MOMENT, WINDOW = "%d-%b-%Y", "%d-%b-%Y %H:%M:%S", 6


def period_end(row: dict[str, Any]) -> date:
    """A listing row's period end (integrated ``qe_Date``, legacy ``toDate``)."""
    return datetime.strptime(row["qe_Date"] if "qe_Date" in row else row["toDate"], DAY).date()


def quarter_ends(as_of: date) -> set[date]:
    """The six latest calendar quarter-ends on or before ``as_of``."""
    ends = [
        date(year, month, day)
        for year in range(as_of.year - 2, as_of.year + 1)
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31))
    ]
    return set([end for end in ends if end <= as_of][-WINDOW:])


def qualifying_periods(rows: Iterable[dict[str, Any]], as_of: date) -> int | None:
    """The number of distinct qualifying period ends (``qualifying_filings``)."""
    filings = qualifying_filings(rows, as_of)
    return None if filings is None else len(filings)


def qualifying_filings(
    rows: Iterable[dict[str, Any]], as_of: date
) -> dict[date, str | None] | None:
    """D1.3 filing-window rule over rows of both NSE listings: collapse each (period_end, basis)
    to its latest broadcast; each distinct period end of a collapsed consolidated in-capmkt row
    with that row's XBRL link; None when a group's latest broadcast is tied. Broadcast is the
    listing's own field only: a group with a row that has none (missing, empty or blank) cannot
    be ordered and yields no qualifying period. Rows equal on the parsed fields (period end,
    basis, broadcast, listing, type, XBRL link) are one filing; any other field, e.g. ``seq_Id``,
    is ignored."""
    window = quarter_ends(as_of)
    groups: dict[tuple[date, str], list[tuple[datetime | None, bool, str | None]]]
    groups = defaultdict(list)
    parsed = {}
    for row in rows:
        integrated = "qe_Date" in row
        text = (row.get("broadcast_Date" if integrated else "broadCastDate") or "").strip()
        when = datetime.strptime(text, MOMENT) if text else None
        xbrl = (row.get("xbrl") or "").strip() or None
        key = (period_end(row), row.get("consolidated"), when, integrated, row.get("type"), xbrl)
        parsed[key] = None
    for end, basis, when, integrated, kind, xbrl in parsed:
        if end in window and basis:
            qualifies = integrated and kind == FINANCIALS and basis == CONSOLIDATED
            groups[end, basis].append((when, qualifies, xbrl))
    periods = {}
    for (end, _), filings in groups.items():
        times = [when for when, *_ in filings]
        if None in times:
            continue
        latest = max(cast(list[datetime], times))
        top = [(qualifies, xbrl) for when, qualifies, xbrl in filings if when == latest]
        if len(top) > 1:
            return None
        if top[0][0]:
            periods[end] = top[0][1]
    return periods


@cache
def onboarding_mapping_set() -> MappingSet:
    """The mapping set discovery parses instances under (``ONBOARDING_VERSIONS``)."""
    dictionary = load_dictionary(CONFIG / "dictionary", ONBOARDING_VERSIONS.dictionary)
    return load_mapping_set(
        CONFIG / "mappings", ONBOARDING_VERSIONS.mapping_set, dictionary=dictionary
    )


def xbrl_admitted(instances: Iterable[tuple[bytes, date]]) -> bool:
    """The D1.3 XBRL prefilter over a candidate's ``(instance, period end)`` pairs, discovery's
    issuer-independent XBRL gates in its order (D4.2 steps 3-4): every financial rule before any
    instance is parsed, the onboarding mapping set's schema, then each instance's scope and
    period (``instance_state``) and ingest's framework predicate (``framework_state``). Issuer
    identity, name and report-nature declarations are left to discovery."""
    pairs = list(instances)
    if not all(financial_rule(body) for body, _ in pairs):
        return False
    try:
        parsed = [
            (parse_instance(body, mapping_set=onboarding_mapping_set()), end) for body, end in pairs
        ]
    except UnsupportedSchemaError:
        return False
    return all(
        instance_state(instance, end) == VERIFIED == framework_state(instance)
        for instance, end in parsed
    )
