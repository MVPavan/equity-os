"""Typed contracts for the data islands of Tijori's company overview page.

The overview surface (``/company/<slug>/``) is one Django template carrying ~22
``json_script`` islands. Ten of them are data: corporate actions, the ratio
strip, the custom-financial (operational KPI) blocks, market-share charts, the
peer table, price returns, the intraday tick series, the daily price series, the
price-chart peer list, and the company-details header. The rest are UI or plan
metadata and are handled as metadata, never as data. The reverse-DCF widget is
deliberately not among them: its numbers are computed in the browser rather than
published, so it is documented as an exclusion in ``REVERSE_DCF_EXCLUSION``
instead of being modeled.

Schema authority is the owner's structure-only capture of TITAN's live overview
page (2026-08-25). That capture is depth-capped in places — notably inside
``company_details_data``, whose byte count is far larger than the keys it shows —
so every model here keeps the verbatim JSON of anything it does not model rather
than guessing a shape. Unknown keys are recorded and logged, never dropped and
never fatal.

Two retention slots exist and never serialize alike: ``unmodeled_fields_json``
holds keys this contract does not model at all, while ``invalid_fields_json``
holds keys it DOES model that the island published in an unreadable shape —
reading those as ``None`` would present a source claim as missing data.

Numeric lexemes follow the shared Tijori cell rule: ``Decimal | None`` plus the
preserved source lexeme. Timestamps keep their source value (epoch milliseconds,
or Tijori's ISO date strings) and carry a derived reading beside it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance

# The point shape is shared with the analysis APIs, so it lives in the neutral
# series module; it is re-exported here to keep this family's imports stable.
from fundamentals.ingest.tijori_series import TijoriSeriesPoint as TijoriSeriesPoint
from fundamentals.ingest.tijori_tables import (
    TijoriIslandStatus,
    TijoriParseError,
    TijoriTableAccessMetadata,
)

OVERVIEW_PAGE_LABEL = "overview"

IS_AUTH_ISLAND_ID = "is_auth"
COMPANY_DETAILS_DATA_ISLAND_ID = "company_details_data"
COMPANY_ID_ISLAND_ID = "companyId"
OVERVIEW_LOCKS_ISLAND_ID = "overview_locks"
COMPANY_STATUS_ISLAND_ID = "company_status"
IS_BANKING_ISLAND_ID = "is_banking"


class TijoriOverviewSection(StrEnum):
    """The overview data sections this adapter models.

    Section names are ours; the island each one reads is
    :data:`SECTION_ISLAND_IDS`. Keeping them separate means a provenance anchor
    can name both the island Tijori published and the section we built from it.
    """

    CORPORATE_ACTIONS = "corporate_actions"
    RATIOS = "ratios"
    CUSTOM_FINANCIALS = "custom_financials"
    MARKET_SHARE = "market_share"
    PEERS = "peers"
    PRICE_RETURNS = "price_returns"
    INTRADAY_PRICE = "intraday_price"
    PRICE_CHART = "price_chart"
    PRICE_CHART_PEERS = "price_chart_peers"
    COMPANY_DETAILS = "company_details"
    REVENUE_MIX = "revenue_mix"


class TijoriOverviewSourceKind(StrEnum):
    """Where on the page a section's payload was read from.

    Nearly every overview section is a ``json_script`` island, but the
    revenue-mix break-ups are server-rendered markup carrying their data in an
    element attribute. The two are re-found by different procedures, so a
    consumer reading ``island_id`` needs to know which kind of location that
    string names — an island id or a DOM element id.
    """

    JSON_ISLAND = "json_island"
    RENDERED_HTML = "rendered_html"


# Islands deliberately excluded: ``metrics`` (a stock-independent chart-metric
# catalogue), ``user_prefs``, ``pagesremain``, ``timestamp``, ``is_landing_page``
# and ``alerts_limit_exceeded`` are UI configuration carrying no issuer data.
#
# The reverse-DCF section is excluded on different grounds — see
# REVERSE_DCF_EXCLUSION below. It is not absent from the page and not unmodeled
# drift: its numbers are computed in the browser, so there is nothing on this
# surface to acquire.
SECTION_ISLAND_IDS: dict[TijoriOverviewSection, str] = {
    TijoriOverviewSection.CORPORATE_ACTIONS: "corporate_actions",
    TijoriOverviewSection.RATIOS: "ratios_table",
    TijoriOverviewSection.CUSTOM_FINANCIALS: "custom_fin_table",
    TijoriOverviewSection.MARKET_SHARE: "ms-charts",
    TijoriOverviewSection.PEERS: "peers_table_data",
    TijoriOverviewSection.PRICE_RETURNS: "price_returns",
    TijoriOverviewSection.INTRADAY_PRICE: "intraday_price",
    TijoriOverviewSection.PRICE_CHART: "price_chart",
    TijoriOverviewSection.PRICE_CHART_PEERS: "price_chart_peers",
    TijoriOverviewSection.COMPANY_DETAILS: COMPANY_DETAILS_DATA_ISLAND_ID,
}

REVENUE_MIX_ELEMENT_ID = "revenuemix"

# Sections read from rendered markup rather than from a JSON island. The value
# is the DOM element id that locates the payload, which is what the section's
# ``island_id`` records — see :class:`TijoriOverviewSourceKind`.
DOM_SECTION_ELEMENT_IDS: dict[TijoriOverviewSection, str] = {
    TijoriOverviewSection.REVENUE_MIX: REVENUE_MIX_ELEMENT_ID,
}

SECTION_SOURCE_IDS: dict[TijoriOverviewSection, str] = {
    **SECTION_ISLAND_IDS,
    **DOM_SECTION_ELEMENT_IDS,
}


REVERSE_DCF_EXCLUSION = (
    "The reverse-DCF widget is NOT an acquisition surface. VERIFIED (owner "
    "capture, 2026-08-25): its figures are computed client-side by the static "
    "asset /static/javascript/reverse-dcf.js, which derives earnings as "
    "mcap/PE and the implied growth rate from user-adjustable discount and "
    "terminal-value inputs. The page carries no reverse-DCF data island and no "
    "API backs it, so every number it displays is arithmetic over inputs the "
    "viewer chose — including the implied-growth percentages an audit may read "
    "off the rendered page. Acquiring them would record a reader's slider "
    "positions as an issuer fact."
)


class TijoriOverviewIdentityError(TijoriParseError):
    """The overview page's identity islands are missing, unusable, or disagree."""


class TijoriOverviewSectionAbsentError(TijoriParseError):
    """An explicitly requested overview section is not published on the page."""


class TijoriOverviewSectionsAbsentError(TijoriParseError):
    """The overview page carries no modeled data section at all."""


class TijoriOverviewSchemaError(TijoriParseError):
    """A raw overview island does not satisfy its typed shape."""


def parse_section(name: str) -> TijoriOverviewSection:
    """Validate one caller-supplied section name against the modeled set."""
    try:
        return TijoriOverviewSection(name)
    except ValueError as error:
        supported = ", ".join(section.value for section in TijoriOverviewSection)
        raise TijoriOverviewSectionAbsentError(
            f"unsupported Tijori overview section {name!r}; supported sections: {supported}"
        ) from error


class TijoriOverviewNumber(BaseModel):
    """One addressable overview scalar: its lexeme plus its numeric reading."""

    model_config = ConfigDict(frozen=True)

    value: Decimal | None
    raw_text: str
    provenance: Provenance


class TijoriOverviewSectionOutcome(BaseModel):
    """Acquisition state of one overview section on the fetched page.

    ``ABSENT`` is a recorded outcome, not an error: Tijori omits an island for a
    company that has no such data, and ``overview_locks`` may explain it.
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriOverviewSection
    island_id: str
    status: TijoriIslandStatus
    detail: str | None = None
    source_kind: TijoriOverviewSourceKind = TijoriOverviewSourceKind.JSON_ISLAND


class TijoriOverviewMetadata(BaseModel):
    """Response identity and acquisition metadata for one overview page.

    ``identity_island_ids`` names every island that actually corroborated the
    configured identity. ``access`` reuses the shared plan/lock contract; on this
    page the lock island is ``overview_locks`` rather than ``financials_locks``,
    and ``access.locks_island_id`` records which one was read.
    """

    model_config = ConfigDict(frozen=True)

    slug: str
    symbol: str
    company_id: int
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    identity_island_ids: tuple[str, ...]
    section_outcomes: tuple[TijoriOverviewSectionOutcome, ...]
    company_status: str | None = None
    is_banking: bool | None = None
    access: TijoriTableAccessMetadata


class TijoriOverviewSectionBase(BaseModel):
    """Shared shape of every typed overview section artifact.

    ``unmodeled_fields_json`` preserves verbatim any key the island published
    that this contract does not model, so drift is recorded rather than lost.

    ``island_id`` names the page location the section was read from, and
    ``source_kind`` says what kind of location that is: a ``json_script`` id for
    an island section, a DOM element id for a rendered-HTML one.
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriOverviewSection
    island_id: str
    source_kind: TijoriOverviewSourceKind = TijoriOverviewSourceKind.JSON_ISLAND
    unmodeled_fields_json: str | None = None
    metadata: TijoriOverviewMetadata

    @property
    def element_count(self) -> int:
        """Number of addressable elements this section carries."""
        raise NotImplementedError


class TijoriCorporateAction(BaseModel):
    """One corporate action (bonus, dividend, rights, or split) as published."""

    model_config = ConfigDict(frozen=True)

    action_type: str
    ex_date: str
    ex_date_iso: date | None
    event_details: str
    event_date: str
    event_date_iso: datetime | None
    provenance: Provenance
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriQuarantinedAction(BaseModel):
    """One corporate action whose date identity could not be read as published.

    Quarantine keeps such a record out of ``actions`` — a blank-but-counted
    action would misreport the issuer's history — while retaining the source
    entry verbatim, the same trade the financial tables make for a row whose
    cardinality cannot be aligned.
    """

    model_config = ConfigDict(frozen=True)

    action_type: str
    element_path: str
    reason: str
    raw_json: str


class TijoriCorporateActionsSection(TijoriOverviewSectionBase):
    """Corporate actions grouped by Tijori's action-type keys.

    ``empty_action_types`` names the types the island published as empty lists —
    a company with no bonus history — which is data, not absence of the section.
    ``quarantined_actions`` holds entries excluded from ``actions`` because their
    date identity was published unreadably; they are retained, never counted.
    """

    actions: tuple[TijoriCorporateAction, ...]
    action_types: tuple[str, ...]
    empty_action_types: tuple[str, ...] = ()
    quarantined_actions: tuple[TijoriQuarantinedAction, ...] = ()

    @property
    def element_count(self) -> int:
        """Number of published corporate actions."""
        return len(self.actions)


class TijoriRatio(BaseModel):
    """One entry of the overview ratio strip (market cap, PE, ...)."""

    model_config = ConfigDict(frozen=True)

    name: str
    short_name: str | None
    display_name: str | None
    unit: str | None
    source_metric_id: int | None
    amount: TijoriOverviewNumber
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriRatiosSection(TijoriOverviewSectionBase):
    """The overview ratio strip in published order."""

    ratios: tuple[TijoriRatio, ...]

    @property
    def element_count(self) -> int:
        """Number of published ratio entries."""
        return len(self.ratios)


class TijoriCustomFinancialRow(BaseModel):
    """One operational-KPI row aligned to its block's report dates.

    A row whose value count disagrees with the block's report-date count cannot
    be aligned to periods, so it yields no cells and keeps its raw lexemes — the
    same quarantine rule the financial tables use.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    cells: tuple[TijoriOverviewNumber, ...]
    unaligned_raw_values: tuple[str, ...] = ()
    unmodeled_fields_json: str | None = None


class TijoriCustomFinancialBlock(BaseModel):
    """One custom-financial block, addressed by the statement column it mirrors."""

    model_config = ConfigDict(frozen=True)

    column: str
    report_dates: tuple[str, ...]
    rows: tuple[TijoriCustomFinancialRow, ...]
    cardinality_mismatch_rows: tuple[str, ...] = ()
    unmodeled_fields_json: str | None = None


class TijoriCustomFinancialsSection(TijoriOverviewSectionBase):
    """Operational KPI blocks in published order."""

    blocks: tuple[TijoriCustomFinancialBlock, ...]

    @property
    def element_count(self) -> int:
        """Number of published custom-financial blocks."""
        return len(self.blocks)


class TijoriMarketShareChart(BaseModel):
    """One market-share chart: its latest reading plus its full series."""

    model_config = ConfigDict(frozen=True)

    name: str
    chart_id: int | None
    unit: str | None
    latest_date: str | None
    source_url: str | None
    sample_size_json: str | None
    methodology_json: str | None
    latest_value: TijoriOverviewNumber
    series: tuple[TijoriSeriesPoint, ...]
    malformed_point_count: int = 0
    series_provenance: Provenance
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriMarketShareSection(TijoriOverviewSectionBase):
    """Segment market-share charts in published order."""

    charts: tuple[TijoriMarketShareChart, ...]

    @property
    def element_count(self) -> int:
        """Number of published market-share charts."""
        return len(self.charts)


class TijoriPeerColumn(BaseModel):
    """One column header of the peer comparison table."""

    model_config = ConfigDict(frozen=True)

    name: str
    short_name: str | None
    unit: str | None
    invalid_fields_json: str | None = None


class TijoriPeerRow(BaseModel):
    """One peer's row, aligned to the declared column order.

    ``missing_columns`` names columns the row simply did not publish, so an
    absent metric never reads as a null value it was never given.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    slug: str | None
    cells: tuple[TijoriOverviewNumber, ...]
    missing_columns: tuple[str, ...] = ()
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriPeersSection(TijoriOverviewSectionBase):
    """The peer comparison table: declared columns plus one row per peer."""

    columns: tuple[TijoriPeerColumn, ...]
    rows: tuple[TijoriPeerRow, ...]

    @property
    def element_count(self) -> int:
        """Number of published peer rows."""
        return len(self.rows)


PRICE_RETURNS_SEMANTICS = (
    "Server-computed as of retrieval: these are the values the price_returns "
    "island carried in the fetched response, fixed at metadata.retrieved_at. "
    "The percentage in the page's own quote header is a DIFFERENT number — the "
    "browser recomputes it from the live tick — so it drifts from this one "
    "through the session and can even carry the opposite sign intraday. A "
    "comparison against a rendered header is therefore not a check on this "
    "value unless both were read at the same instant."
)


class TijoriPriceReturn(BaseModel):
    """One trailing-window price return, keyed by Tijori's window label.

    VERIFIED (same-response capture, 2026-08-25): the island's readings match
    this adapter's artifact exactly. See :data:`PRICE_RETURNS_SEMANTICS` for why
    the page header's percentage may not.
    """

    model_config = ConfigDict(frozen=True)

    window: str
    amount: TijoriOverviewNumber


class TijoriPriceReturnsSection(TijoriOverviewSectionBase):
    """Trailing price returns in published window order.

    ``semantics_note`` travels with the artifact rather than living only in this
    docstring, because the consumer most likely to mis-compare these values
    against a live page header is reading the written JSON, not this module.
    """

    returns: tuple[TijoriPriceReturn, ...]
    semantics_note: str = PRICE_RETURNS_SEMANTICS

    @property
    def element_count(self) -> int:
        """Number of published return windows."""
        return len(self.returns)


class TijoriPriceSeriesSection(TijoriOverviewSectionBase):
    """One price series — the intraday tick series or the daily price chart.

    ``malformed_point_count`` counts points whose source shape was not
    ``[timestamp, value]``; those points are retained with null readings.
    """

    points: tuple[TijoriSeriesPoint, ...]
    malformed_point_count: int = 0
    series_provenance: Provenance

    @property
    def element_count(self) -> int:
        """Number of series points."""
        return len(self.points)


class TijoriPriceChartPeer(BaseModel):
    """One entry of the price-chart peer selector."""

    model_config = ConfigDict(frozen=True)

    name: str
    peer_id: int | None
    peer_type: str | None
    symbol: str | None
    provenance: Provenance
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriPriceChartPeersSection(TijoriOverviewSectionBase):
    """The comparison entities offered beside the price chart."""

    peers: tuple[TijoriPriceChartPeer, ...]

    @property
    def element_count(self) -> int:
        """Number of published price-chart peers."""
        return len(self.peers)


class TijoriRevenueMixEntry(BaseModel):
    """One slice of a revenue-mix break-up: its label and its published share."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: Decimal
    raw_text: str
    provenance: Provenance


class TijoriRevenueMixBreakUp(BaseModel):
    """One break-up chart of the revenue-mix section, addressed by its chart id.

    LIVE FACT (owner capture, 2026-08-25): the section renders one
    ``div.rmix_graph_block`` per break-up — product-wise, location-wise,
    operating-profit, asset — each carrying its title in an ``h4`` and its data
    in a ``chart-data`` attribute holding an HTML-entity-encoded JSON array of
    ``[label, number]`` pairs. This is attribute-embedded tabular data: the
    values are re-found by fetching the page and reading a named attribute of a
    named element, so slices anchor as ``HTML_TABLE`` against
    ``table_id="rmix:<chart-id>"``.

    ``status`` is ``PRESENT`` only for a block that satisfied that whole shape.
    A block shaped differently — a historic wrapper beside the current ones, a
    drifted attribute — is kept with ``UNPARSEABLE``, a ``detail`` naming why,
    and its attributes retained verbatim in ``raw_block_json``.

    ``company_id_attribute`` is the block's ``company-id`` attribute, retained
    as source data under a name that records a MISNOMER. LIVE FACT (TITAN,
    company 81, 2026-08-25): it duplicates the block's ``chart-id`` — both read
    ``4280`` — and is not the issuer at all. It must never be read as identity
    or checked against the page's company id; the island gate established
    identity before this section was built.
    """

    model_config = ConfigDict(frozen=True)

    title: str | None
    chart_id: str | None
    table_id: str | None
    status: TijoriIslandStatus
    entries: tuple[TijoriRevenueMixEntry, ...] = ()
    detail: str | None = None
    company_id_attribute: str | None = None
    raw_block_json: str | None = None

    @property
    def entry_count(self) -> int:
        """Number of readable slices this break-up carries."""
        return len(self.entries)


class TijoriRevenueMixSection(TijoriOverviewSectionBase):
    """The revenue-mix break-ups in rendered order.

    ``element_count`` counts readable slices rather than blocks, so a section of
    four break-ups that this adapter could not read never reports as if it had
    acquired four things.
    """

    break_ups: tuple[TijoriRevenueMixBreakUp, ...]

    @property
    def element_count(self) -> int:
        """Number of readable slices across every published break-up."""
        return sum(break_up.entry_count for break_up in self.break_ups)


class TijoriQuickLookFlag(BaseModel):
    """One ``quick_look`` forensic flag, as published inside its category.

    The owner's structure capture is depth-capped inside ``company_details_data``,
    so the flag key names below are modeled optimistically and every entry keeps
    its verbatim ``raw_json``. A flag whose keys drift therefore loses nothing.
    """

    model_config = ConfigDict(frozen=True)

    name: str | None
    sentence: str | None
    explanation: str | None
    flag: str | None
    raw_json: str
    provenance: Provenance


class TijoriQuickLookCounts(BaseModel):
    """The flag tally Tijori publishes beside its forensic checklist.

    A colour Tijori adds later lands in ``unmodeled_counts_json`` rather than
    being dropped, so a new tally key is recorded the day it appears.
    """

    model_config = ConfigDict(frozen=True)

    green: int | None = None
    red: int | None = None
    neutral: int | None = None
    gray: int | None = None
    total: int | None = None
    unmodeled_counts_json: str | None = None


class TijoriQuickLookCategory(BaseModel):
    """One named group of forensic flags (Tijori names its members ``factories``)."""

    model_config = ConfigDict(frozen=True)

    name: str
    flags: tuple[TijoriQuickLookFlag, ...]
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriQuickLook(BaseModel):
    """Tijori's forensic checklist: tallies, categorized flags, and the rest.

    LIVE FACT (TITAN, 2026-08-25): ``quick_look`` is an object keyed
    ``count`` / ``data`` / ``table_data``; ``data`` holds category objects whose
    ``factories`` are the flags. ``table_data``'s content is not yet known, so it
    is preserved verbatim rather than modeled.

    This subtree is retention-first, not fail-fast: the structure capture was
    depth-capped here and the modeled shape was already wrong once, so an
    unexpected shape is recorded in ``note`` plus verbatim JSON and never fails
    the company-details section around it.
    """

    model_config = ConfigDict(frozen=True)

    counts: TijoriQuickLookCounts | None = None
    categories: tuple[TijoriQuickLookCategory, ...] = ()
    table_data_json: str | None = None
    unmodeled_fields_json: str | None = None
    note: str | None = None

    @property
    def flag_count(self) -> int:
        """Number of forensic flags across every published category."""
        return sum(len(category.flags) for category in self.categories)


class TijoriCompanyDetailsSection(TijoriOverviewSectionBase):
    """The overview header: identity, headline valuation, and forensic flags.

    Identity fields are repeated here as published; they are also the page's
    identity gate, which has already run against the configured watchlist values
    by the time this section is built.
    """

    company: str | None
    company_id: int
    symbol: str
    short_name: str | None
    slug: str | None
    industry_code: int | None
    is_banking: bool | None
    market_cap_display: str | None
    market_cap: TijoriOverviewNumber
    price_earnings: TijoriOverviewNumber
    price_earnings_growth: TijoriOverviewNumber
    has_price_earnings_growth: bool | None
    quick_look: TijoriQuickLook
    invalid_fields_json: str | None = None

    @property
    def element_count(self) -> int:
        """Number of forensic flags carried beside the header identity."""
        return self.quick_look.flag_count
