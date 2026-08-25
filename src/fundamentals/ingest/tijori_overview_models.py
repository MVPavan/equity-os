"""Typed contracts for the data islands of Tijori's company overview page.

The overview surface (``/company/<slug>/``) is one Django template carrying ~22
``json_script`` islands. Ten of them are data: corporate actions, the ratio
strip, the custom-financial (operational KPI) blocks, market-share charts, the
peer table, price returns, the intraday tick series, the daily price series, the
price-chart peer list, and the company-details header. The rest are UI or plan
metadata and are handled as metadata, never as data.

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


# Islands deliberately excluded: ``metrics`` (a stock-independent chart-metric
# catalogue), ``user_prefs``, ``pagesremain``, ``timestamp``, ``is_landing_page``
# and ``alerts_limit_exceeded`` are UI configuration carrying no issuer data.
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


class TijoriSeriesPoint(BaseModel):
    """One ``[timestamp, value]`` point of a price or market-share series.

    Series points carry no per-point provenance: a 4,400-point daily chart would
    otherwise serialize more anchor than data. The series that owns them carries
    one anchor, and every point keeps its source lexemes, so a point is still
    traceable by its index within that anchored series. A point whose shape is
    not ``[timestamp, value]`` is kept with null readings rather than dropped.
    """

    model_config = ConfigDict(frozen=True)

    timestamp_ms: int | None
    timestamp_raw_text: str
    timestamp_iso: datetime | None
    value: Decimal | None
    raw_value_text: str


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
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriOverviewSection
    island_id: str
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


class TijoriPriceReturn(BaseModel):
    """One trailing-window price return, keyed by Tijori's window label."""

    model_config = ConfigDict(frozen=True)

    window: str
    amount: TijoriOverviewNumber


class TijoriPriceReturnsSection(TijoriOverviewSectionBase):
    """Trailing price returns in published window order."""

    returns: tuple[TijoriPriceReturn, ...]

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
