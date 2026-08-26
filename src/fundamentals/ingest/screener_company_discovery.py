"""What one company page offers to expand, read only from the page itself.

Pure and deterministic: page HTML in, hooks out, or a typed refusal. Nothing
here fetches, and nothing here builds a URL from a template plus an assumption.

The rule this module exists to enforce is that **the page decides what exists**.
Every sub-document of Slice 2 is reachable only because the page rendered a
control pointing at it — a ``showShareholders`` button, a ``showSegment``
button, a ``data-url`` on a modal button, or the ``data-warehouse-id`` Slice 0
already matched against config. A part whose control is absent while its section
is present is *positive proof of absence*: NETWEB genuinely has no Product
Segments, and probing ``/api/segments/…`` for it would spend a rate-limited
request to learn that from a shell response instead of from the page.

Bucket and tab sets vary per company and are never assumed: TITAN offers six
investor buckets, NETWEB four (no government, no others), ETERNAL five (no
promoters, because it has no promoter holding at all). Segment ``type`` is
recorded verbatim from the button; only ``'1'`` has ever been offered and this
module will not synthesise the geographic ``'2'`` that exists server-side.

Structure verified 2026-08-26 against captured pages for all ten watchlist
companies on both bases (private captures, not committed).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from fundamentals.ingest.screener_company_models import (
    DiscoveryAmbiguousError,
    InvestorHook,
    PageHooks,
    Periodicity,
    SegmentHook,
)
from fundamentals.ingest.screener_financials_tables import normalize_text
from fundamentals.ingest.screener_session_page import (
    COMPANY_INFO_XPATH,
    WAREHOUSE_ID_ATTRIBUTE,
)

SHAREHOLDING_SECTION_ID = "shareholding"
QUARTERS_SECTION_ID = "quarters"
PROFIT_LOSS_SECTION_ID = "profit-loss"
BALANCE_SHEET_SECTION_ID = "balance-sheet"
TOP_RATIOS_ID = "top-ratios"
IDENTITY_ID = "company-info"

# Every section whose presence a part depends on. Recorded per page so a part
# can tell "the section rendered without its control" — a fact about the
# company — from "the section is gone" — the page changing shape under us.
TRACKED_SECTION_IDS = (
    SHAREHOLDING_SECTION_ID,
    QUARTERS_SECTION_ID,
    PROFIT_LOSS_SECTION_ID,
    BALANCE_SHEET_SECTION_ID,
    IDENTITY_ID,
)

# The two ``<div>`` ids that wrap the Shareholding Pattern tables. They are div
# ids, not table ids: each wraps one bare ``table.data-table``, so the table is
# addressed through its container and never by a class-wide search (the page
# carries other ``data-table`` elements, including the peer comparison).
QUARTERLY_SHP_ID = "quarterly-shp"
YEARLY_SHP_ID = "yearly-shp"
SHAREHOLDING_TABLE_IDS: dict[Periodicity, str] = {
    Periodicity.QUARTERLY: QUARTERLY_SHP_ID,
    Periodicity.YEARLY: YEARLY_SHP_ID,
}

RELATED_PARTY_URL_PREFIX = "/results/rpt/"
CORPORATE_ACTIONS_URL_PREFIX = "/company/actions/"

DATA_URL_ATTRIBUTE = "data-url"
DATA_TABLE_XPATH = ".//table[contains(concat(' ', normalize-space(@class), ' '), ' data-table ')]"

_SHOW_SHAREHOLDERS_XPATH = ".//button[contains(@onclick, 'showShareholders')]"
_SHOW_SEGMENT_XPATH = ".//button[contains(@onclick, 'showSegment')]"

# ``Company.showShareholders('<bucket>', '<quarterly|yearly>', this)`` — the
# first argument is the exact API bucket key, which is why it is read from the
# call and never derived from the row's rendered label ("FIIs" is
# ``foreign_institutions``).
_SHOW_SHAREHOLDERS = re.compile(
    r"showShareholders\(\s*(['\"])(?P<bucket>.*?)\1\s*,\s*(['\"])(?P<periodicity>.*?)\3"
)
# ``Segment.showSegment('<section>', '<type>')``.
_SHOW_SEGMENT = re.compile(
    r"showSegment\(\s*(['\"])(?P<section>.*?)\1\s*,\s*(['\"])(?P<segment_type>.*?)\3"
)

_EXPAND_MARKER = "+"

_DUPLICATE_HOOK = (
    "screener page offers {count} {kind} controls for {target}; one of them would be "
    "requested and the other silently dropped, and nothing says the two name the same "
    "document"
)
_CONFLICTING_URL = (
    "screener {section!r} section carries {count} distinct {kind} targets ({targets}); "
    "which one is 'the' document would depend on which element is read first"
)
_AMBIGUOUS_TABLE = (
    "screener {container!r} block holds {count} data tables; exactly one is required so "
    "the table's numbers cannot depend on document order"
)


def read_page_hooks(root: Any) -> PageHooks:
    """Read every sub-document control the page renders, refusing ambiguity.

    ``sections_present`` is gathered alongside the controls rather than derived
    later: whether a section exists and whether it carried a control are two
    different observations, and only the page can answer both.
    """
    return PageHooks(
        investors=investor_hooks(root),
        segments=segment_hooks(root),
        related_party_url=modal_url(root, PROFIT_LOSS_SECTION_ID, RELATED_PARTY_URL_PREFIX),
        corporate_actions_url=modal_url(
            root, BALANCE_SHEET_SECTION_ID, CORPORATE_ACTIONS_URL_PREFIX
        ),
        warehouse_id=page_warehouse_id(root),
        sections_present=sections_present(root),
    )


def sections_present(root: Any) -> frozenset[str]:
    """Which of the sections a part can depend on this page actually rendered."""
    return frozenset(
        section_id
        for section_id in TRACKED_SECTION_IDS
        if _element_by_id(root, section_id) is not None
    )


def investor_hooks(root: Any) -> tuple[InvestorHook, ...]:
    """Every ``(bucket, periodicity)`` drill-down the Shareholding section offers.

    Scoped to ``#shareholding`` rather than searched page-wide: the buttons are
    the only statement of which buckets this company has, and a control that
    appeared elsewhere on the page would not be one of them.
    """
    section = _section(root, SHAREHOLDING_SECTION_ID)
    if section is None:
        return ()
    hooks: list[InvestorHook] = []
    for button in section.xpath(_SHOW_SHAREHOLDERS_XPATH):
        match = _SHOW_SHAREHOLDERS.search(button.get("onclick") or "")
        if match is None:
            continue
        try:
            periodicity = Periodicity(match.group("periodicity"))
        except ValueError:
            continue
        hooks.append(
            InvestorHook(
                bucket=match.group("bucket"),
                periodicity=periodicity,
                row_label=_button_label(button),
            )
        )
    _refuse_repeats(
        ((hook.bucket, hook.periodicity.value) for hook in hooks), kind="shareholding drill-down"
    )
    return tuple(hooks)


def segment_hooks(root: Any) -> tuple[SegmentHook, ...]:
    """Every Product Segments table the page offers, one per page section.

    Two ``showSegment`` calls naming one section with different types would make
    "the segments table for this section" depend on document order, so that is
    refused; the same section offered twice with the same type is deduplicated,
    because the two would build one identical request.
    """
    hooks: list[SegmentHook] = []
    for section_id in (QUARTERS_SECTION_ID, PROFIT_LOSS_SECTION_ID):
        section = _section(root, section_id)
        if section is None:
            continue
        found: list[SegmentHook] = []
        for button in section.xpath(_SHOW_SEGMENT_XPATH):
            match = _SHOW_SEGMENT.search(button.get("onclick") or "")
            if match is None:
                continue
            found.append(
                SegmentHook(
                    section=match.group("section"),
                    segment_type=match.group("segment_type"),
                )
            )
        distinct = tuple(dict.fromkeys(found))
        if len(distinct) > 1:
            raise DiscoveryAmbiguousError(
                _CONFLICTING_URL.format(
                    section=section_id,
                    count=len(distinct),
                    kind="segments",
                    targets=", ".join(f"{hook.section}/{hook.segment_type}" for hook in distinct),
                )
            )
        hooks.extend(distinct)
    _refuse_repeats(((hook.section, hook.segment_type) for hook in hooks), kind="segments")
    return tuple(hooks)


def modal_url(root: Any, section_id: str, prefix: str) -> str | None:
    """The single ``data-url`` candidate one section offers for one part.

    Candidates are identified by **role and claim**, then validated — never
    filtered by whether they already look valid. A ``data-url`` is
    page-controlled input that becomes an authenticated request carrying the
    owner's session cookie, so a value that names this part and points somewhere
    else is the most important thing in the section, not something to skip past.

    Round 3 fixed exactly that inversion. The old rule kept only values *starting
    with* the part's prefix, so ``https://evil.example/results/rpt/991001/`` was
    dropped as "not this part" and the part reported that the company publishes
    no Related Party — a hostile hook turning into a clean exit zero. A candidate
    now claims the part when the part's own path prefix appears **anywhere** in
    the value, which an off-site URL, a protocol-relative one and a traversal all
    do, and every claimant is then handed to
    :func:`~fundamentals.ingest.screener_company_models.assert_document_path` at
    the part boundary. Only a section that offers no claimant at all is absent.

    The attribute is otherwise used verbatim, including whether it carries the
    ``consolidated/`` suffix: the page decides that, and rebuilding the path here
    would mean re-deciding a basis rule the proven page has already decided.
    """
    section = _section(root, section_id)
    if section is None:
        return None
    targets = tuple(
        dict.fromkeys(
            value
            for element in section.xpath(f".//*[@{DATA_URL_ATTRIBUTE}]")
            if prefix in (value := element.get(DATA_URL_ATTRIBUTE, ""))
        )
    )
    if len(targets) > 1:
        raise DiscoveryAmbiguousError(
            _CONFLICTING_URL.format(
                section=section_id,
                count=len(targets),
                kind=prefix,
                targets=", ".join(targets),
            )
        )
    return targets[0] if targets else None


def page_warehouse_id(root: Any) -> int | None:
    """The basis-scoped warehouse id from the page's one identity element.

    Slice 0 has already required exactly one ``#company-info`` and matched this
    id against config, so this is a read of an established fact rather than a
    second, weaker identity check.
    """
    for element in root.xpath(COMPANY_INFO_XPATH):
        raw = element.get(WAREHOUSE_ID_ATTRIBUTE)
        if raw is not None and raw.strip():
            return int(raw.strip())
    return None


def shareholding_table(root: Any, periodicity: Periodicity) -> Any | None:
    """The one ``data-table`` inside a Shareholding Pattern tab, or ``None``."""
    container = _element_by_id(root, SHAREHOLDING_TABLE_IDS[periodicity])
    if container is None:
        return None
    return one_data_table(container, container_name=SHAREHOLDING_TABLE_IDS[periodicity])


def top_ratios_list(root: Any) -> Any | None:
    """The page's own header-ratio block, which shares the API list's markup."""
    return _element_by_id(root, TOP_RATIOS_ID)


def one_data_table(container: Any, *, container_name: str) -> Any:
    """Return a container's single ``data-table``, refusing zero or several."""
    tables = container.xpath(DATA_TABLE_XPATH)
    if len(tables) != 1:
        raise DiscoveryAmbiguousError(
            _AMBIGUOUS_TABLE.format(container=container_name, count=len(tables))
        )
    return tables[0]


def _section(root: Any, section_id: str) -> Any | None:
    """One page section by id, or ``None`` when the page does not render it."""
    return _element_by_id(root, section_id)


def _element_by_id(root: Any, element_id: str) -> Any | None:
    """One element by id, refusing a page that carries the id twice.

    A repeated id makes every lookup below it order-dependent, which is exactly
    the failure mode a decoy element would exploit.
    """
    elements = root.xpath(f"//*[@id={element_id!r}]")
    if len(elements) > 1:
        raise DiscoveryAmbiguousError(
            _DUPLICATE_HOOK.format(count=len(elements), kind="id", target=element_id)
        )
    return elements[0] if elements else None


def _button_label(button: Any) -> str:
    """The drill-down button's visible label, without its expander ``+``."""
    text = normalize_text(button.text_content())
    if text.endswith(_EXPAND_MARKER):
        text = text[: -len(_EXPAND_MARKER)].strip()
    return text


def _refuse_repeats(targets: Any, *, kind: str) -> None:
    """Refuse a page that offers one target through two identical controls."""
    repeated = sorted("/".join(target) for target, count in Counter(targets).items() if count > 1)
    if repeated:
        raise DiscoveryAmbiguousError(
            _DUPLICATE_HOOK.format(count=2, kind=kind, target=", ".join(repeated))
        )
