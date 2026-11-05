"""Stage 4 D1.3 filing rules over NSE listing rows: the filing window (shared by the held-out
draw checks and the Stage 4 manifest oracle) and the XBRL prefilter."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any, cast

from lxml import etree  # type: ignore[import-untyped]

from equity_os.companies.onboarding.verification import VERIFIED, instance_state
from equity_os.contracts.companies.onboarding import ONBOARDING_VERSIONS
from equity_os.extraction.xbrl.xbrl_adapter import parse_instance
from equity_os.extraction.xbrl.xbrl_parser import RawXbrlInstance
from equity_os.normalisation.dictionary.dictionary import load_dictionary
from equity_os.normalisation.mapping.mapping import (
    MappingSet,
    UnsupportedSchemaError,
    load_mapping_set,
)

CONFIG = Path(__file__).resolve().parents[3] / "config"
FINANCIALS, CONSOLIDATED = "Integrated Filing- Financials", "Consolidated"
DAY, MOMENT, WINDOW = "%d-%b-%Y", "%d-%b-%Y %H:%M:%S", 6
# Frozen D6 attempt-3 admission rule, restated from 4351e2c
# (src/fundamentals/evidence/member_identity.py:35-52,179-196,245-281,
# entity/verification.py:74-81,153-166, extract/pdf_header_text.py:55-57); never the production
# rule, which later extractor versions may change.
HISTORICAL_PHRASES = (
    "prepared in accordance with Indian Accounting Standard",
    "prepared in accordance with the Indian Accounting Standards",
)
HISTORICAL_SCHEMA_PREFIX, HISTORICAL_TEXT_BLOCK = "Ind-AS_entry_point", "TextBlock"
HISTORICAL_SECTOR_PREFIX = "in-capmkt-ent-"
HISTORICAL_SECTOR_NAMESPACE = re.compile(
    rb"^http://www\.sebi\.gov\.in/xbrl/IntegratedFinance_IndAS/\d{4}-\d{2}-\d{2}"
    rb"/in-capmkt/in-capmkt-ent$"
)
_SCHEMA_REF = "{http://www.xbrl.org/2003/linkbase}schemaRef"
_HREF = "{http://www.w3.org/1999/xlink}href"


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
    dictionary = load_dictionary(
        CONFIG / "normalisation/dictionary", ONBOARDING_VERSIONS.dictionary
    )
    return load_mapping_set(
        CONFIG / "normalisation/mappings", ONBOARDING_VERSIONS.mapping_set, dictionary=dictionary
    )


def _tokens(text: str) -> list[str]:
    """The historical tokenisation: lowercase alphanumeric runs."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def _has_run(haystack: list[str], needle: list[str]) -> bool:
    """Whether ``needle`` occurs as a contiguous token run in ``haystack``."""
    width = len(needle)
    return any(haystack[i : i + width] == needle for i in range(len(haystack) - width + 1))


def historical_sector_rule(body: bytes) -> bool:
    """Frozen attempt-3 sector rule: in-capmkt-ent schemaRefs only and the root declaring the
    IntegratedFinance_IndAS entry-point namespace (no competing-form clause)."""
    try:
        root = etree.fromstring(body)
    except etree.XMLSyntaxError:
        return False
    refs = [ref.get(_HREF) or "" for ref in root.iter(_SCHEMA_REF)]
    return (
        bool(refs)
        and all(ref.rsplit("/", 1)[-1].startswith(HISTORICAL_SECTOR_PREFIX) for ref in refs)
        and any(
            HISTORICAL_SECTOR_NAMESPACE.match(uri.encode()) for uri in root.nsmap.values() if uri
        )
    )


def historical_framework(instance: RawXbrlInstance) -> bool:
    """Frozen attempt-3 framework rule: Ind AS iff an ``Ind-AS_entry_point`` schemaRef or an
    own-taxonomy non-numeric text-block fact carrying a declaration phrase declares it."""
    if any(
        href.rsplit("/", 1)[-1].startswith(HISTORICAL_SCHEMA_PREFIX)
        for href in instance.schema_refs
    ):
        return True
    phrases = [_tokens(phrase) for phrase in HISTORICAL_PHRASES]
    return any(
        _has_run(_tokens(fact.raw_text or ""), phrase)
        for fact in instance.facts
        if fact.namespace_uri == instance.taxonomy.namespace
        and not fact.is_numeric
        and fact.concept_qname.endswith(HISTORICAL_TEXT_BLOCK)
        for phrase in phrases
    )


def xbrl_admitted(instances: Iterable[tuple[bytes, date]]) -> bool:
    """The D1.3 XBRL prefilter over a candidate's ``(instance, period end)`` pairs, discovery's
    issuer-independent XBRL gates as of attempt 3, in its order (D4.2 steps 3-4): every
    historical sector rule before any instance is parsed, the onboarding mapping set's schema,
    then each instance's scope and period (``instance_state``) and the historical framework
    rule. Issuer identity, name and report-nature declarations are left to discovery."""
    pairs = list(instances)
    if not all(historical_sector_rule(body) for body, _ in pairs):
        return False
    try:
        parsed = [
            (parse_instance(body, mapping_set=onboarding_mapping_set()), end) for body, end in pairs
        ]
    except UnsupportedSchemaError:
        return False
    return all(
        instance_state(instance, end) == VERIFIED and historical_framework(instance)
        for instance, end in parsed
    )
