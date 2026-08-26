"""Typed vocabulary for the Screener subscriber financial sections and schedules.

Slice 1 of the Screener build. It sits on the Slice 0 session adapter
(:mod:`fundamentals.ingest.screener_session`) and adds the *reading* of what
that adapter fetched: the five ``data-table`` financial sections, the four
``ranges-table`` growth blocks, and the per-row schedule sub-tables the page
loads on demand. This module owns only the vocabulary — enums, typed refusals,
frozen artifacts, and the two URL builders; the parsers live beside it.

Two facts about this source are load-bearing enough to state here.

**The schedules API selects basis by the PRESENCE of the ``consolidated`` key,
not by its value.** Verified 2026-08-26 against TITAN: ``?…&consolidated=``,
``?…&consolidated=true`` and ``?…&consolidated=false`` return byte-identical
consolidated bodies, while omitting the key entirely returns the standalone
one. A caller who "turns consolidated off" by sending ``consolidated=false``
therefore gets consolidated figures. :func:`schedule_url` is the only place
that decides this, and it decides it by emitting or omitting the key.

**A schedule's sub-rows are not always addends.** Some families expand into
components that sum to the row they hang off (``Borrowings`` →
long/short/lease/other); others expand into *analysis* of that row — percent
rows (``Sales`` → ``YOY Sales Growth %``), alternative measures of the same
figure (``Net Profit`` → ``Profit for PE``, ``Profit for EPS``), or a nested
hierarchy the site marks with its own subtotals (``Fixed Assets`` →
``Gross Block``). Summing the second kind produces a number that means nothing.
:class:`ScheduleClassification` records which kind a family turned out to be,
and only the summable kind is held to the reconciliation gate.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    Basis,
    ScreenerSessionError,
)

SCHEDULES_PATH_TEMPLATE = "/api/company/{company_id}/schedules/"

# The query key whose mere presence selects consolidated figures; its value is
# read by nobody. Emitted empty so the request says as little as it means.
CONSOLIDATED_QUERY_KEY = "consolidated"
CONSOLIDATED_QUERY_VALUE = ""
PARENT_QUERY_KEY = "parent"
SECTION_QUERY_KEY = "section"

# Reserved key inside a schedule sub-row map: it carries presentation attributes
# for the row, not a period. Screener uses it to mark a row ``strong`` — its own
# signal that the row is a subtotal over the rows above it rather than a
# component of the parent (verified on ``Gross Block``, ``Profit from
# operations``, ``Working capital changes``).
SET_ATTRIBUTES_KEY = "setAttributes"
# A sub-row that is itself expandable carries the ``showSchedule`` call for its
# own nested schedule under this key. Its value is a *string*, so unlike
# ``setAttributes`` it reads exactly like a period whose label is
# "isExpandable" — which is how it went unnoticed until the alignment check
# started refusing sub-row periods the page header does not carry (observed on
# ``Trade receivables`` and ``Material Cost %``, TITAN/NETWEB/HFCL).
IS_EXPANDABLE_KEY = "isExpandable"
RESERVED_SUB_ROW_KEYS = frozenset({SET_ATTRIBUTES_KEY, IS_EXPANDABLE_KEY})
EMPHASIS_CLASS = "strong"
CLASS_ATTRIBUTE = "class"

PERCENT_SUFFIX = "%"
TTM_DATE_KEY = "TTM"

# Screener rounds both the page row and every schedule sub-row to whole crores
# independently, so a correct family still misses an exact sum. Worst-case
# rounding error over ``n`` addends plus the rounded total is ``(n + 1) / 2``.
ROUNDING_HALF_UNIT = Decimal("0.5")


class Section(StrEnum):
    """One acquirable block of the company page.

    The first five are the page's own ``<section>`` ids and each holds exactly
    one ``data-table``. ``GROWTH`` is ours: the four ``ranges-table`` blocks
    Screener renders inside ``#profit-loss`` have no section id of their own,
    but they are a different shape (window → percent, no period columns) and
    would corrupt the P&L table if folded into it.
    """

    QUARTERS = "quarters"
    PROFIT_LOSS = "profit-loss"
    BALANCE_SHEET = "balance-sheet"
    CASH_FLOW = "cash-flow"
    RATIOS = "ratios"
    GROWTH = "growth"


DATA_TABLE_SECTIONS = (
    Section.QUARTERS,
    Section.PROFIT_LOSS,
    Section.BALANCE_SHEET,
    Section.CASH_FLOW,
    Section.RATIOS,
)

# Sections whose unit statement ("… Figures in Rs. Crores") actually describes
# their rows. ``ratios`` carries the same note but its rows are day counts and
# ratios, so applying the note there would publish a confident wrong unit.
AMOUNT_SECTIONS = frozenset(
    {Section.QUARTERS, Section.PROFIT_LOSS, Section.BALANCE_SHEET, Section.CASH_FLOW}
)

# Row labels observed live (TITAN, both bases, 2026-08-26). This is a *known*
# set, never a closed one: a row that is not here is retained as
# ``RowStatus.UNMODELED`` with its lexemes, and a row that is here but reads as
# nothing is flagged ``RowStatus.INVALID``. Neither is fatal.
KNOWN_SECTION_ROWS: dict[Section, frozenset[str]] = {
    Section.QUARTERS: frozenset(
        {
            "Sales",
            "Expenses",
            "Operating Profit",
            "OPM %",
            "Other Income",
            "Interest",
            "Depreciation",
            "Profit before tax",
            "Tax %",
            "Net Profit",
            "EPS in Rs",
            "Raw PDF",
        }
    ),
    Section.PROFIT_LOSS: frozenset(
        {
            "Sales",
            "Expenses",
            "Operating Profit",
            "OPM %",
            "Other Income",
            "Interest",
            "Depreciation",
            "Profit before tax",
            "Tax %",
            "Net Profit",
            "EPS in Rs",
            "Dividend Payout %",
        }
    ),
    Section.BALANCE_SHEET: frozenset(
        {
            "Equity Capital",
            "Reserves",
            "Borrowings",
            "Other Liabilities",
            "Total Liabilities",
            "Fixed Assets",
            "CWIP",
            "Investments",
            "Other Assets",
            "Total Assets",
        }
    ),
    Section.CASH_FLOW: frozenset(
        {
            "Cash from Operating Activity",
            "Cash from Investing Activity",
            "Cash from Financing Activity",
            "Net Cash Flow",
            "Free Cash Flow",
            "CFO/OP",
        }
    ),
    Section.RATIOS: frozenset(
        {
            "Debtor Days",
            "Inventory Days",
            "Days Payable",
            "Cash Conversion Cycle",
            "Working Capital Days",
            "ROCE %",
        }
    ),
}

# The 15 ``(section, parent)`` families observed live. The runtime list is
# always derived from the page's own ``showSchedule`` buttons — this constant is
# a test expectation and a drift signal, never the source of truth.
KNOWN_SCHEDULE_FAMILIES = (
    (Section.QUARTERS, "Sales"),
    (Section.QUARTERS, "Expenses"),
    (Section.QUARTERS, "Other Income"),
    (Section.QUARTERS, "Net Profit"),
    (Section.PROFIT_LOSS, "Sales"),
    (Section.PROFIT_LOSS, "Expenses"),
    (Section.PROFIT_LOSS, "Other Income"),
    (Section.PROFIT_LOSS, "Net Profit"),
    (Section.BALANCE_SHEET, "Borrowings"),
    (Section.BALANCE_SHEET, "Other Liabilities"),
    (Section.BALANCE_SHEET, "Fixed Assets"),
    (Section.BALANCE_SHEET, "Other Assets"),
    (Section.CASH_FLOW, "Cash from Operating Activity"),
    (Section.CASH_FLOW, "Cash from Investing Activity"),
    (Section.CASH_FLOW, "Cash from Financing Activity"),
)


class PeriodKind(StrEnum):
    """What one table column is addressed by.

    ``TTM`` is a typed column, not a date: Screener stamps that header
    ``data-date-key="TTM"``. Coercing it into a date would invent a period end
    the site never published, so it keeps its own kind and a null date.
    """

    DATE = "date"
    TTM = "ttm"
    UNTYPED = "untyped"


class RowStatus(StrEnum):
    """How much of a page row this contract actually understood."""

    MODELED = "modeled"
    UNMODELED = "unmodeled"
    INVALID = "invalid"


class Unit(StrEnum):
    """The unit one row's numbers are in, as the page states it.

    ``UNKNOWN`` is a real answer and the default when the row declares no unit
    of its own and its section's note does not describe it.

    ``COUNT``, ``RATIO`` and ``MIXED`` were added for the company sub-documents
    of Slice 2: the shareholding tables carry a "No. of Shareholders" row of
    integers under a "Numbers in percentages" note, and a header quick-ratio may
    render a bare multiple ("P/E 77.7") or two numbers in different notations
    inside one value ("High / Low").
    """

    RS_CRORE = "rs_crore"
    RUPEES = "rupees"
    PERCENT = "percent"
    DAYS = "days"
    COUNT = "count"
    RATIO = "ratio"
    MIXED = "mixed"
    DOCUMENT_LINK = "document_link"
    UNKNOWN = "unknown"


class SectionOutcome(StrEnum):
    """Whether one acquired section carried rows, proven positively.

    ``OK_EMPTY`` is claimed only for a section that rendered its table with no
    period columns and no rows — never for a section that failed to parse.
    """

    OK = "ok"
    OK_EMPTY = "ok_empty"


class SubRowKind(StrEnum):
    """What one schedule sub-row is, as the response itself presents it.

    ``SUBTOTAL`` is Screener's own ``setAttributes: {"class": "strong"}`` marking:
    a row that totals the rows above it rather than standing beside them.
    """

    AMOUNT = "amount"
    PERCENT = "percent"
    SUBTOTAL = "subtotal"


class ScheduleStrategy(StrEnum):
    """How one family's sub-rows relate to the page row they expand.

    This is resolved against a registry of shapes observed live, not guessed
    from the body. An earlier design inferred it: any percent or subtotal row
    made the whole family "analytical" and exempt from reconciliation. That is
    an escape hatch — a wrong-basis amount breakdown carrying one informational
    percent row would skip the gate entirely and exit zero. So novelty now fails
    closed instead:

    * ``FLAT_SUM`` — every sub-row is a plain amount. The sum is meaningful, so
      the family is reconciled against its page row.
    * ``ALL_PERCENT`` — every sub-row is a percent. There is nothing to add.
    * ``KNOWN_MIXED`` — one of the families whose mixed shape is registered in
      :data:`MIXED_FAMILY_SHAPES`, and whose body carries every required row
      and nothing outside the allowed set.
    * ``HIERARCHICAL`` — a registered family whose page row is arithmetically
      derivable from two of its sub-rows, so it is *proven* rather than
      exempted.
    * ``UNVERIFIED`` — anything else: an unregistered family with a mixed shape,
      or a registered one carrying a label or kind its signature does not cover.
      Evidence is retained, the artifact is marked, and the CLI exits non-zero.
    """

    FLAT_SUM = "flat_sum"
    ALL_PERCENT = "all_percent"
    KNOWN_MIXED = "known_mixed"
    HIERARCHICAL = "hierarchical"
    UNVERIFIED = "unverified"


# The four families whose sub-rows are neither all amounts nor all percentages,
# with every ``(label, kind)`` pair observed across the live captures of TITAN
# (consolidated), NETWEB (standalone) and HFCL (consolidated), 2026-08-26.
#
# An observed body must be a SUBSET of its family's signature. Subset, not
# equality, because companies genuinely carry different rows: NETWEB's quarterly
# Net Profit has four sub-rows where TITAN's has six and HFCL's five. A row
# outside the signature is drift and is refused rather than absorbed.
#
# None of these four may be summed. Each expands into alternative measures of
# the same figure (``Profit for PE``, ``Profit for EPS``) or into a nested
# hierarchy with its own subtotals (``Gross Block``; ``Working capital
# changes``), so a flat sum double-counts or restates rather than decomposes.
MIXED_FAMILY_SIGNATURES: dict[tuple[Section, str], frozenset[tuple[str, SubRowKind]]] = {
    (Section.QUARTERS, "Net Profit"): frozenset(
        {
            ("Minority share", SubRowKind.AMOUNT),
            ("Exceptional items AT", SubRowKind.AMOUNT),
            ("Profit excl Excep", SubRowKind.AMOUNT),
            ("Profit for PE", SubRowKind.AMOUNT),
            ("Profit for EPS", SubRowKind.AMOUNT),
            ("YOY Profit Growth %", SubRowKind.PERCENT),
        }
    ),
    (Section.PROFIT_LOSS, "Net Profit"): frozenset(
        {
            ("Profit from Associates", SubRowKind.AMOUNT),
            ("Minority share", SubRowKind.AMOUNT),
            ("Exceptional items AT", SubRowKind.AMOUNT),
            ("Profit excl Excep", SubRowKind.AMOUNT),
            ("Profit for PE", SubRowKind.AMOUNT),
            ("Profit for EPS", SubRowKind.AMOUNT),
            ("Profit Growth %", SubRowKind.PERCENT),
        }
    ),
    (Section.BALANCE_SHEET, "Fixed Assets"): frozenset(
        {
            ("Land", SubRowKind.AMOUNT),
            ("Building", SubRowKind.AMOUNT),
            ("Plant Machinery", SubRowKind.AMOUNT),
            ("Equipments", SubRowKind.AMOUNT),
            ("Computers", SubRowKind.AMOUNT),
            ("Furniture n fittings", SubRowKind.AMOUNT),
            ("Vehicles", SubRowKind.AMOUNT),
            ("Intangible Assets", SubRowKind.AMOUNT),
            ("Other fixed assets", SubRowKind.AMOUNT),
            ("Gross Block", SubRowKind.SUBTOTAL),
            ("Accumulated Depreciation", SubRowKind.AMOUNT),
        }
    ),
    (Section.CASH_FLOW, "Cash from Operating Activity"): frozenset(
        {
            ("Profit from operations", SubRowKind.SUBTOTAL),
            ("Receivables", SubRowKind.AMOUNT),
            ("Inventory", SubRowKind.AMOUNT),
            ("Payables", SubRowKind.AMOUNT),
            ("Loans Advances", SubRowKind.AMOUNT),
            ("Operating borrowings", SubRowKind.AMOUNT),
            ("Other WC items", SubRowKind.AMOUNT),
            ("Working capital changes", SubRowKind.SUBTOTAL),
            ("Direct taxes", SubRowKind.AMOUNT),
            ("Other operating items", SubRowKind.AMOUNT),
        }
    ),
}


class ReconciliationStatus(StrEnum):
    """Result of the sub-row-sum-versus-page-row gate for one family.

    Only ``RECONCILED`` is a positive result, and it is claimed only when every
    published sub-row period aligned to a page column and every comparison held.
    The rest are kept apart because they mean different things:

    * ``NOT_APPLICABLE`` — a registered shape a sum would not describe;
    * ``NOT_COMPARABLE`` — a summable family whose page row published no
      readable value to compare against;
    * ``UNVERIFIED`` — the shape, the periods, or the structure was not
      something this contract has seen; the gate never ran;
    * ``UNVERIFIED_EMPTY`` — the response was ``{}``. None of the fifteen live
      families is ever empty, and an empty HTTP 200 carries no session, issuer
      or basis marker, so it is indistinguishable from an expired-cookie or
      soft-blocked response. It stays unverified until an empty response is
      captured live with positive proof that it means "no breakdown".
    """

    RECONCILED = "reconciled"
    NOT_APPLICABLE = "not_applicable"
    NOT_COMPARABLE = "not_comparable"
    UNVERIFIED = "unverified"
    UNVERIFIED_EMPTY = "unverified_empty"


# The only two outcomes that count as the gate having run and held. Everything
# else means it did not run, and one shared definition is what keeps the
# artifact's ``verified`` flag from disagreeing with the CLI's exit code.
PROVEN_RECONCILIATIONS = frozenset(
    {ReconciliationStatus.RECONCILED, ReconciliationStatus.NOT_APPLICABLE}
)


def reconciliation_is_proven(status: ReconciliationStatus) -> bool:
    """True when this family's reconciliation actually ran and held."""
    return status in PROVEN_RECONCILIATIONS


class IdentityStrength(StrEnum):
    """How strongly one artifact's issuer identity is actually established.

    The company page proves its own identity (Slice 0 matches ``#company-info``
    against the watchlist), so page-derived tables are ``PAGE_ASSERTED``. A
    schedule response is a bare ``{row: {period: value}}`` map that asserts
    nothing about whose company it describes; the request URL is the entire
    binding, exactly as for the Tijori analysis APIs.
    """

    PAGE_ASSERTED = "page_asserted"
    CONFIGURED_URL_ONLY = "configured_url_only"


class ScreenerFinancialsError(ScreenerSessionError):
    """Base for every typed refusal raised while reading financial sections."""


class SectionUnreadableError(ScreenerFinancialsError):
    """A requested section is absent, or does not hold exactly one data table.

    Ambiguity is refused rather than resolved by document order: a second
    ``data-table`` inside a section would make "the section's numbers" depend on
    which one is read first, and the page carries bare ``data-table`` elements
    (the peer comparison) outside the sections that must never be mistaken for
    one.
    """


class AmbiguousStructureError(ScreenerFinancialsError):
    """Two elements of the page would answer to the same address.

    Refused rather than resolved by document order. A table with two columns
    labelled "Mar 2026", two expander buttons for one family, or two rows
    claiming the same schedule parent all make "the value for X" depend on which
    one is read first — and the one read first is not necessarily the one a
    reconciliation compared against.
    """


class ScheduleBodyError(ScreenerFinancialsError):
    """A schedule response is not the ``{sub_row: {period: value}}`` shape."""


class ScheduleReconciliationError(ScreenerFinancialsError):
    """A summable family's sub-rows do not add up to the row they expand.

    This is the gate that catches the basis trap: standalone and consolidated
    schedule bodies are the same shape and differ only in their numbers, so a
    URL built with the wrong ``consolidated`` key presence yields a body that
    parses perfectly and reconciles against nothing.
    """


class DuplicateAnchorError(ScreenerFinancialsError):
    """Two values in one artifact would be addressed by the same anchor."""


def schedule_path(company_id: int, *, parent: str, section: Section, basis: Basis) -> str:
    """Build the schedules request path and query for one family on one basis.

    Basis is expressed by the *presence* of the ``consolidated`` key: present
    (with an empty value) for consolidated, absent for standalone. Nothing else
    in this repo may encode that decision.

    Returns the path with its query, which is also the ``document_id`` recorded
    on every value read out of the response.
    """
    query: list[tuple[str, str]] = [
        (PARENT_QUERY_KEY, parent),
        (SECTION_QUERY_KEY, section.value),
    ]
    if basis is Basis.CONSOLIDATED:
        query.append((CONSOLIDATED_QUERY_KEY, CONSOLIDATED_QUERY_VALUE))
    path = SCHEDULES_PATH_TEMPLATE.format(company_id=company_id)
    return f"{path}?{urlencode(query)}"


def schedule_url(company_id: int, *, parent: str, section: Section, basis: Basis) -> str:
    """The absolute schedules URL on the pinned Screener origin."""
    return SCREENER_ORIGIN + schedule_path(company_id, parent=parent, section=section, basis=basis)


class Period(BaseModel):
    """One column of a section table, addressed as the page addresses it."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    label: str
    kind: PeriodKind
    date_key: str | None = None
    period_end: date | None = None


class Cell(BaseModel):
    """One value in a section table: what it reads as, and what it said.

    ``published`` is false for a cell the page rendered blank. It is not the
    same as ``value is None``: an unreadable lexeme was published and must not
    be confused with a period the company did not report.
    """

    model_config = ConfigDict(frozen=True)

    period_index: int = Field(ge=0)
    value: Decimal | None
    raw_text: str
    published: bool
    provenance: Provenance


class RowLink(BaseModel):
    """One outbound document link a row carries, retained and never followed.

    The ``Raw PDF`` row addresses a BSE-hosted filing through a Screener
    redirect. The href is evidence of where the quarter's numbers came from; it
    is recorded, not fetched.
    """

    model_config = ConfigDict(frozen=True)

    period_index: int = Field(ge=0)
    href: str


class TableRow(BaseModel):
    """One parsed row of a section table."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    status: RowStatus
    unit: Unit
    cells: tuple[Cell, ...] = ()
    links: tuple[RowLink, ...] = ()
    schedule_parent: str | None = None


class QuarantinedRow(BaseModel):
    """A row that could not be aligned to the header, kept with its lexemes.

    Retained rather than dropped: a row whose cell count no longer matches the
    header is the shape drift takes, and discarding it would make the artifact
    look complete while a row silently vanished.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    reason: str
    raw_cells: tuple[str, ...]


class GrowthRow(BaseModel):
    """One ``<window>: <pct>`` line of a growth ranges-table."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    window: str
    value: Decimal | None
    raw_text: str
    unit: Unit
    provenance: Provenance


class GrowthTable(BaseModel):
    """One ``ranges-table`` block, titled by its own header cell."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    title: str
    rows: tuple[GrowthRow, ...] = ()


class ScheduleSubRow(BaseModel):
    """One sub-row of an expanded schedule family.

    ``kind`` is the shape fact the strategy resolution turns on, and it is
    recorded per row so an artifact shows why its family was classified the way
    it was. ``percent`` and ``emphasis`` are kept as the raw observations the
    kind was derived from.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    kind: SubRowKind
    percent: bool
    emphasis: bool
    cells: tuple[Cell, ...] = ()
    unmatched_periods: tuple[str, ...] = ()
    nested_schedule_call: str | None = None


class PeriodReconciliation(BaseModel):
    """The sub-row sum against the page row, for one period of one family."""

    model_config = ConfigDict(frozen=True)

    period_label: str
    sub_row_total: Decimal
    page_row_value: Decimal
    difference: Decimal
    tolerance: Decimal
    within_tolerance: bool


class ScheduleFamily(BaseModel):
    """One expandable page row and the schedule that expands it."""

    model_config = ConfigDict(frozen=True)

    section: Section
    parent: str
    basis: Basis
    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    strategy: ScheduleStrategy
    reconciliation: ReconciliationStatus
    reconciliation_note: str
    periods: tuple[Period, ...] = ()
    sub_rows: tuple[ScheduleSubRow, ...] = ()
    comparisons: tuple[PeriodReconciliation, ...] = ()
    unaligned_periods: tuple[str, ...] = ()


class ScheduleFailure(BaseModel):
    """A family whose response was retained but could not be admitted.

    Recorded rather than only raised. The body that fails the reconciliation
    gate is the most useful evidence this adapter ever produces — it is what a
    wrong basis, or a change in what a row means, actually looks like — so it is
    named in the artifact beside the retained bytes rather than existing only in
    a traceback.
    """

    model_config = ConfigDict(frozen=True)

    section: Section
    parent: str
    basis: Basis
    url: str
    document_id: str
    body_sha256: str
    refusal: str
    detail: str


class SectionTable(BaseModel):
    """One financial section: its periods, rows, and what it could not align."""

    model_config = ConfigDict(frozen=True)

    section: Section
    table_id: str
    outcome: SectionOutcome
    unit_statement: str | None
    identity_strength: IdentityStrength = IdentityStrength.PAGE_ASSERTED
    periods: tuple[Period, ...] = ()
    rows: tuple[TableRow, ...] = ()
    quarantined: tuple[QuarantinedRow, ...] = ()
    growth_tables: tuple[GrowthTable, ...] = ()
    schedules: tuple[ScheduleFamily, ...] = ()


class FinancialsMetadata(BaseModel):
    """Provenance record for one financial-sections acquisition."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    symbol: str
    slug: str
    basis: Basis
    company_id: int
    page_url: str
    page_sha256: str
    sections_requested: tuple[Section, ...]
    schedule_families_requested: tuple[str, ...]
    schedule_families_fetched: tuple[str, ...]
    schedule_families_refused: tuple[str, ...]
    schedule_families_unverified: tuple[str, ...]
    complete: bool
    verified: bool
    incomplete_reason: str | None
    fetched_at: datetime


class FinancialsArtifact(BaseModel):
    """Every section read from one page on one basis, with its schedules.

    ``metadata.complete`` is false when the run stopped early (a rate limit mid
    schedule sweep). The sections already read are still here and still true;
    what is not here is named rather than implied.
    """

    model_config = ConfigDict(frozen=True)

    metadata: FinancialsMetadata
    sections: tuple[SectionTable, ...] = ()
    failures: tuple[ScheduleFailure, ...] = ()
