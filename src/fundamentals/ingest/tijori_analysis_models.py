"""Typed contracts for Tijori's ancillary company-analysis JSON APIs.

Four session-cookie GET endpoints back the analysis widgets beside the
financials page. Unlike every other Tijori surface this repo reads, these are
standalone JSON documents rather than ``json_script`` islands inside a rendered
page, and they are anchored with :attr:`SourceAnchorType.API_DOCUMENT` for that
reason.

IDENTITY FACT (owner capture, TITAN / company_id 81, 2026-08-25): none of the
four responses carries an identity field — no symbol, no company id, no slug.
The only binding between a response and an issuer is the ``company_id`` in the
request URL, which comes from the verified watchlist. Every artifact therefore
records :data:`URL_IDENTITY_BASIS` as its identity basis, and the ``symbol`` in
its metadata is the CONFIGURED symbol, never one the response asserted. No
page-level symbol assertion is possible here; claiming otherwise would be a
fabricated check.

Two retention slots exist and never serialize alike, matching the overview
family: ``unmodeled_fields_json`` holds keys this contract does not model at
all, while ``invalid_fields_json`` holds keys it DOES model that the document
published in an unreadable shape. Numeric lexemes follow the shared Tijori cell
rule: ``Decimal | None`` beside the preserved source lexeme.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.tijori_series import TijoriSeriesPoint
from fundamentals.ingest.tijori_tables import TijoriParseError

URL_IDENTITY_BASIS = (
    "company_id in the request URL (verified watchlist identifier); the response "
    "body carries no identity field to assert against"
)
EMPTY_DOCUMENT_NOTE = "the API published no data for this company"

METRIC_ID_PLACEHOLDER = "{metric_id}"
COMPANY_ID_PLACEHOLDER = "{company_id}"

# Trailing-slash matters: the same path without it answers 301, which the
# transport refuses rather than following.
FUND_FLOW_PATH = "/api/v1/ind/fund_flow_analysis_data/{company_id}/"
BALANCE_SHEET_SNAPSHOT_PATH = "/api/v1/ind/balance_sheet_snap_shot/{company_id}/"
CASH_FLOW_WATERFALL_PATH = "/api/v1/ind/cash_flow_waterfall/{company_id}/"
OP_METRICS_PATH = "/api/v1/ind/company_op_metrics/{company_id}/{metric_id}/"


class TijoriAnalysisSection(StrEnum):
    """The analysis APIs this adapter models, named for their path segment."""

    FUND_FLOW = "fund_flow"
    BALANCE_SHEET_SNAPSHOT = "balance_sheet_snapshot"
    CASH_FLOW_WATERFALL = "cash_flow_waterfall"
    OP_METRICS = "op_metrics"


# Deliberately excluded: ``/timeline/company/<company_id>/`` is live-verified to
# return an HTML fragment, not JSON, so it needs a different reader and is
# formally scoped to Slice D rather than modeled here.
SECTION_PATHS: dict[TijoriAnalysisSection, str] = {
    TijoriAnalysisSection.FUND_FLOW: FUND_FLOW_PATH,
    TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT: BALANCE_SHEET_SNAPSHOT_PATH,
    TijoriAnalysisSection.CASH_FLOW_WATERFALL: CASH_FLOW_WATERFALL_PATH,
    TijoriAnalysisSection.OP_METRICS: OP_METRICS_PATH,
}

# The anchor's ``document_id`` names the API, not one company's response, so a
# value stays locatable when the company id changes.
SECTION_DOCUMENT_IDS: dict[TijoriAnalysisSection, str] = {
    TijoriAnalysisSection.FUND_FLOW: "api:fund_flow_analysis_data",
    TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT: "api:balance_sheet_snap_shot",
    TijoriAnalysisSection.CASH_FLOW_WATERFALL: "api:cash_flow_waterfall",
    TijoriAnalysisSection.OP_METRICS: "api:company_op_metrics",
}

# The only section whose URL needs a second path parameter, and therefore the
# only one a breadth run cannot acquire without being told which metric to ask
# for. See ``METRIC_ID_REQUIRED`` for why no artifact supplies these ids.
METRIC_SECTIONS = frozenset({TijoriAnalysisSection.OP_METRICS})

# LIVE FACT (TITAN overview capture, 2026-08-25): ``custom_fin_table`` sub-rows
# publish only ``name`` and ``value``, and the ``metrics`` island publishes
# string chart keys ('value', 'ltp'), so neither carries the integer op-metric id
# this endpoint needs. The id is therefore caller-supplied until a source that
# publishes it is found.
METRIC_ID_REQUIRED = (
    "op_metrics needs --metric-id: no acquired Tijori artifact publishes the "
    "integer op-metric id this endpoint takes"
)

# Windows Tijori published on the live capture. An unrecognized key is kept in
# full and named in ``unknown_windows``; it is drift to record, never data to
# drop.
KNOWN_WINDOWS: tuple[str, ...] = ("1yr", "3yr", "5yr", "7yr", "10yr")


class TijoriAnalysisOutcome(StrEnum):
    """Acquisition outcome of one analysis document.

    Only successful outcomes are enumerated: drift, a non-success body status,
    and an unaddressable shape are refusals raised as typed errors, never an
    outcome an artifact can be written with. ``OK_EMPTY`` therefore always means
    "the API answered, and its answer contains no elements" — a fact about the
    company, never a fact about a broken read.
    """

    OK = "ok"
    OK_EMPTY = "ok_empty"


class TijoriIdentityStrength(StrEnum):
    """How strongly an artifact's issuer identity is actually established.

    ``VERIFIED_RESPONSE`` is what the page surfaces earn: the response itself
    publishes a symbol and company id that the adapter matched against the
    watchlist. ``CONFIGURED_URL_ONLY`` is all these APIs can offer, because their
    bodies assert no identity at all. Recording the difference keeps a consumer
    from treating the two as interchangeable evidence.
    """

    VERIFIED_RESPONSE = "verified_response"
    CONFIGURED_URL_ONLY = "configured_url_only"


class TijoriAnalysisError(TijoriParseError):
    """An analysis API response does not satisfy its typed shape."""


class TijoriAnalysisSchemaError(TijoriAnalysisError):
    """A raw analysis document is shaped in a way this contract cannot address."""


class TijoriAnalysisMetricIdError(TijoriAnalysisError):
    """A metric-keyed section was requested without a usable metric id."""


class TijoriAnalysisResponseStatusError(TijoriAnalysisError):
    """The document's own status field is malformed or reports a non-success response."""


def parse_analysis_section(name: str) -> TijoriAnalysisSection:
    """Validate one caller-supplied section name against the modeled set."""
    try:
        return TijoriAnalysisSection(name)
    except ValueError as error:
        supported = ", ".join(section.value for section in TijoriAnalysisSection)
        raise TijoriAnalysisError(
            f"unsupported Tijori analysis section {name!r}; supported sections: {supported}"
        ) from error


class TijoriAnalysisAmount(BaseModel):
    """One addressable API scalar: its lexeme plus its numeric reading."""

    model_config = ConfigDict(frozen=True)

    value: Decimal | None
    raw_text: str
    provenance: Provenance


class TijoriAnalysisMetadata(BaseModel):
    """Request identity and acquisition metadata for one analysis document.

    ``symbol`` is the CONFIGURED watchlist symbol: the response asserts no
    identity of its own, and ``identity_basis`` records exactly that.
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriAnalysisSection
    document_id: str
    slug: str
    symbol: str
    company_id: int
    metric_id: int | None
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    identity_basis: str = URL_IDENTITY_BASIS
    identity_strength: TijoriIdentityStrength = TijoriIdentityStrength.CONFIGURED_URL_ONLY
    response_status: int | None = None


class TijoriAnalysisSectionBase(BaseModel):
    """Shared shape of every typed analysis artifact.

    ``outcome`` and ``note`` are set in exactly one place, from exactly one
    condition — ``element_count == 0`` — after the builder returns. No builder
    infers emptiness from whether a container happened to be present, because a
    document that omitted its payload entirely would satisfy such a heuristic
    and be written out as a successful empty result.
    """

    model_config = ConfigDict(frozen=True)

    section: TijoriAnalysisSection
    document_id: str
    metadata: TijoriAnalysisMetadata
    outcome: TijoriAnalysisOutcome = TijoriAnalysisOutcome.OK
    note: str | None = None
    unmodeled_fields_json: str | None = None

    @property
    def element_count(self) -> int:
        """Number of addressable elements this artifact carries."""
        raise NotImplementedError


class TijoriAnalysisFetch(BaseModel):
    """One acquired analysis document beside the exact bytes it was built from.

    The artifact records a ``file_sha256`` over the response body; carrying the
    body itself out of the adapter is what lets the caller put those bytes on
    disk, so the recorded hash can actually be checked against something.
    """

    model_config = ConfigDict(frozen=True)

    document: TijoriAnalysisSectionBase
    raw_body: bytes


class TijoriSumDerivation(StrEnum):
    """How a total row's ``derived_value`` was arrived at, if at all.

    ``NONE`` is every ordinary item: nothing was derived and ``derived_value``
    is null. ``CUMULATIVE_SUM_OF_PRIOR_ITEMS`` is the one evidenced derivation —
    see :func:`fundamentals.ingest.tijori_analysis._window_items` for the
    rendered verification behind it and for the sections it is applied to.
    """

    NONE = "none"
    CUMULATIVE_SUM_OF_PRIOR_ITEMS = "cumulative_sum_of_prior_items"


class TijoriFlowItem(BaseModel):
    """One item of a fund-flow group window or a cash-flow waterfall window.

    ``amount_published`` is False when the document omitted ``y`` entirely,
    which the waterfall does for its derived total rows. ``amount`` keeps a null
    reading for those rows rather than a fabricated sum: this adapter never
    presents a computed number as something the source stated.

    ``derived_value`` is the separate, explicitly-labelled slot for a number
    this adapter computed itself. It is populated only for ``is_sum`` rows of a
    section whose derivation rule is rendered-verified, and ``derivation`` names
    the rule that produced it. A consumer that wants only source-stated numbers
    reads ``amount``; one that wants the total the page displays reads
    ``derived_value`` and can see exactly how it was obtained.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    amount: TijoriAnalysisAmount
    amount_published: bool
    is_sum: bool
    derived_value: Decimal | None = None
    derivation: TijoriSumDerivation = TijoriSumDerivation.NONE
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriAnalysisWindow(BaseModel):
    """One trailing window, keyed exactly as the API published it."""

    model_config = ConfigDict(frozen=True)

    window: str
    items: tuple[TijoriFlowItem, ...]


class TijoriFundFlowGroup(BaseModel):
    """One fund-flow group ('sources' or 'uses') across its published windows."""

    model_config = ConfigDict(frozen=True)

    name: str
    windows: tuple[TijoriAnalysisWindow, ...]
    unknown_windows: tuple[str, ...] = ()
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriFundFlowSection(TijoriAnalysisSectionBase):
    """Sources and uses of funds over each trailing window."""

    groups: tuple[TijoriFundFlowGroup, ...]

    @property
    def element_count(self) -> int:
        """Number of published flow items across every group and window."""
        return sum(len(window.items) for group in self.groups for window in group.windows)


class TijoriSnapshotEntry(BaseModel):
    """One line of the balance-sheet snapshot, on one side of the sheet."""

    model_config = ConfigDict(frozen=True)

    name: str
    amount: TijoriAnalysisAmount
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriSnapshotSide(BaseModel):
    """One side of the balance-sheet snapshot, addressed by its field name."""

    model_config = ConfigDict(frozen=True)

    field_name: str
    entries: tuple[TijoriSnapshotEntry, ...]
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriBalanceSheetSnapshotSection(TijoriAnalysisSectionBase):
    """The latest balance sheet reduced to its published snapshot lines."""

    sides: tuple[TijoriSnapshotSide, ...]

    @property
    def element_count(self) -> int:
        """Number of published snapshot lines across both sides."""
        return sum(len(side.entries) for side in self.sides)


class TijoriCashFlowWaterfallSection(TijoriAnalysisSectionBase):
    """The cash-flow waterfall for each trailing window."""

    windows: tuple[TijoriAnalysisWindow, ...]
    unknown_windows: tuple[str, ...] = ()

    @property
    def element_count(self) -> int:
        """Number of published waterfall steps across every window."""
        return sum(len(window.items) for window in self.windows)


class TijoriOpMetricsSection(TijoriAnalysisSectionBase):
    """One operational metric's history for the requested metric id.

    The point shape is the repo's existing ``[timestamp, value]`` series
    contract, so a point here compares directly with an overview price series.
    Points carry no per-point provenance; ``series_provenance`` anchors the
    whole series and a point stays traceable by its index within it.
    """

    metric_id: int
    points: tuple[TijoriSeriesPoint, ...]
    malformed_point_count: int = 0
    peer_count: int = 0
    peers_json: str | None = None
    series_provenance: Provenance

    @property
    def element_count(self) -> int:
        """Number of series points published for this metric."""
        return len(self.points)
