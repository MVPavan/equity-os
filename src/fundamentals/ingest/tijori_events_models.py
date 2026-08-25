"""Typed contracts for Tijori's site-level and timeline event surfaces.

Five surfaces sit outside the per-company page family: three market-wide pages
(`/results/upcoming-events/`, `/results/quarterly-results/`, `/in/timeline`), the
per-company timeline FRAGMENT (`/timeline/company/`), and the concall monitor,
which is modeled here only so a run can report why it is never fetched.

SCOPE FACT (owner premium capture, 2026-08-25): the three market-wide pages carry
no company identity of their own. Every company they name is DATA on a row, not
the issuer the document is about, so those artifacts record
``scope=MARKET_WIDE`` and ``identity_strength=NO_COMPANY_IDENTITY``. Each row's
company reference is cross-linked to the watchlist BY SLUG and the match is
recorded; a company that is not on the watchlist is normal market data and never
a failure. The company timeline is the mirror image: a page-less fragment whose
only issuer binding is the ``company_id`` this adapter put in the URL, exactly
like the analysis APIs, so it records ``scope=COMPANY`` and
``identity_strength=CONFIGURED_URL_ONLY``.

AUTH FACT (same capture): the market pages publish no ``company_details``, so the
per-company identity gate cannot apply. What they DO publish is
``plan_details`` — the subscriber's plan object — beside ``is_landing_page``,
which an authenticated response renders as an empty string. ``/in/timeline``
additionally publishes ``is_auth: true`` and ``userId``. The gate is therefore:
``plan_details`` must be a non-empty object, ``is_landing_page`` must be falsy,
and ``is_auth`` — when the page publishes it — must be exactly ``True``. The
fragment publishes none of these; its auth basis is structural (see
:data:`FRAGMENT_AUTH_BASIS`) plus the transport's standing refusal to follow the
login redirect an anonymous session would receive.

Retention follows the committed families: ``unmodeled_fields_json`` holds keys
this contract does not model, ``invalid_fields_json`` holds modeled keys the
source published unreadably, and numeric lexemes read through the shared Tijori
cell rule so a ``Decimal | None`` reading always sits beside its source text.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.tijori_overview_models import IS_AUTH_ISLAND_ID as IS_AUTH_ISLAND_ID
from fundamentals.ingest.tijori_tables import (
    PLAN_DETAILS_ISLAND_ID,
    TijoriParseError,
    TijoriTableAccessMetadata,
)

COMPANY_ID_PLACEHOLDER = "{company_id}"

# Paths as captured. ``/in/timeline`` is the path the authenticated session is
# served; the page's own ``rel=canonical`` names ``/timeline``, which is the
# marketing URL and is deliberately not used for acquisition.
UPCOMING_PATH = "/results/upcoming-events/"
QUARTERLY_RESULTS_PATH = "/results/quarterly-results/"
TIMELINE_PATH = "/in/timeline"
COMPANY_TIMELINE_PATH = "/timeline/company/?company_id={company_id}&timestamp=0"
CONCALL_MONITOR_PATH = "/results/concall-monitor/"

# Islands the market pages publish. ``IS_AUTH_ISLAND_ID`` is imported rather than
# redeclared: it names the same Django island the company pages carry.
IS_LANDING_PAGE_ISLAND_ID = "is_landing_page"
EVENT_TYPES_ISLAND_ID = "eventsList"
PORTFOLIOS_ISLAND_ID = "portfoliosList"
# The timeline page also renders a ``watchlists`` island whose body is identical
# to ``watchlistsList``. It is deliberately not collected: reading the same list
# twice would double every element and its anchor without adding a fact.
WATCHLISTS_ISLAND_ID = "watchlistsList"
SECTORS_ISLAND_ID = "sectors"
START_DATE_ISLAND_ID = "startDate"
MCAP_START_ISLAND_ID = "mcapStart"
NO_COMPANY_ISLAND_ID = "no_company"
USER_ID_ISLAND_ID = "userId"
TIMESTAMP_ISLAND_ID = "timestamp"
PAGES_REMAIN_ISLAND_ID = "pagesremain"

# Single-valued timeline islands, read as anchored scalars in published order.
TIMELINE_SCALAR_ISLAND_IDS: tuple[str, ...] = (
    TIMESTAMP_ISLAND_ID,
    START_DATE_ISLAND_ID,
    MCAP_START_ISLAND_ID,
    NO_COMPANY_ISLAND_ID,
    USER_ID_ISLAND_ID,
    PAGES_REMAIN_ISLAND_ID,
)

MARKET_IDENTITY_BASIS = (
    "none: this is a market-wide listing, so each row's company reference is "
    "data on that row, not an issuer identity for the document"
)
FRAGMENT_IDENTITY_BASIS = (
    "company_id in the request URL (verified watchlist identifier); the fragment "
    "carries no identity island to assert against"
)
MARKET_AUTH_BASIS = (
    "plan_details published as a non-empty object, is_landing_page published "
    "falsy, and is_auth (where the page publishes it) published true"
)
FRAGMENT_AUTH_BASIS = (
    "the response is a bare timeline fragment — no <html>/<body> shell and no "
    "login markup — which an anonymous session cannot obtain: it is answered "
    "with a login redirect, which the transport refuses rather than follows"
)

# Every verdict below is dated: a capability Tijori does not serve statically
# today may be served tomorrow, and an undated claim would read as permanent.
CAPTURE_DATE = "2026-08-25"

EMPTY_LISTING_NOTE = "the surface answered, and its listing carries no rows"
TIMELINE_FEED_NOT_IN_DOCUMENT = (
    f"as captured {CAPTURE_DATE}: the initial /in/timeline document carries the "
    "event-type taxonomy and the viewer's own lists, not the event feed — the "
    "feed table renders as an empty table-loader shell filled by a later XHR"
)
UPCOMING_CONCALLS_NOT_IN_DOCUMENT = (
    f"as captured {CAPTURE_DATE}: the upcoming-events page renders its concall "
    "tab as an empty #concalls container beside a hidden "
    "upcoming_concalls_loader shell; only the results tab is served statically"
)
UPCOMING_RESULTS_ACQUIRED = (
    f"as captured {CAPTURE_DATE}: the default results listing is server-rendered "
    "into the #results container; rows beyond the first page load by XHR and are "
    "reported through declared_shown/declared_total"
)
QUARTERLY_RESULTS_ACQUIRED = (
    f"as captured {CAPTURE_DATE}: every announced result on the first page is "
    "server-rendered; later pages load by XHR and are reported through "
    "declared_shown/declared_total"
)
TIMELINE_TAXONOMY_ACQUIRED = (
    f"as captured {CAPTURE_DATE}: the event-type taxonomy, the viewer's lists, "
    "and the page's scalar islands are server-rendered"
)
COMPANY_TIMELINE_ACQUIRED = (
    f"as captured {CAPTURE_DATE}: the fragment server-renders one row per event "
    "for the requested company"
)
CONCALL_NOT_STATIC_REASON = (
    f"as captured {CAPTURE_DATE}: the concall-monitor document carries no tables, "
    "no data islands, and no event markup — only a promotional panel linking out "
    "to a separate product (tijoristack.ai); there is nothing in it to acquire"
)
COMPANY_TIMELINE_NEEDS_STOCK = (
    "company-timeline needs --stock: the fragment is addressed by a verified "
    "watchlist company id, which a market-wide run does not have"
)
# FACT (owner capture, 2026-08-25): the fragment renders no empty-state markup of
# any kind — no 'no events' node, no placeholder row. A fragment with zero event
# rows is therefore indistinguishable from a login page, a wrong-endpoint
# response, or a template change, so it can never be reported as a verified
# empty result. The site timeline's ``li.no-res`` belongs to the company-search
# dropdown, not the feed, and is not a marker for this surface.
FRAGMENT_NO_EVENT_ROWS = (
    "tijori company-timeline fragment carries no tr[data-id] event row and no "
    "empty-state marker this adapter can recognize; an empty rendering has never "
    "been observed, so zero rows cannot be distinguished from a broken read"
)

# Deepest nesting observed across all five captures is 15 elements. The cap sits
# far above that so real markup never trips it, mirroring the bounded-depth rule
# the financial tables already enforce with MAX_SUB_SECTION_DEPTH.
MAX_ELEMENT_DEPTH = 64
MAX_EVENT_TYPE_DEPTH = 16


class TijoriEventsSurface(StrEnum):
    """The event surfaces this adapter knows, named for their CLI selector."""

    UPCOMING = "upcoming"
    QUARTERLY_RESULTS = "quarterly-results"
    TIMELINE = "timeline"
    COMPANY_TIMELINE = "company-timeline"
    CONCALL_MONITOR = "concall-monitor"


SURFACE_PATHS: dict[TijoriEventsSurface, str] = {
    TijoriEventsSurface.UPCOMING: UPCOMING_PATH,
    TijoriEventsSurface.QUARTERLY_RESULTS: QUARTERLY_RESULTS_PATH,
    TijoriEventsSurface.TIMELINE: TIMELINE_PATH,
    TijoriEventsSurface.COMPANY_TIMELINE: COMPANY_TIMELINE_PATH,
    TijoriEventsSurface.CONCALL_MONITOR: CONCALL_MONITOR_PATH,
}

# The surface whose document verifiably carries nothing to parse. It is named in
# every run summary and never fetched; chasing its XHRs is a separate slice.
NOT_STATIC_SURFACES = frozenset({TijoriEventsSurface.CONCALL_MONITOR})

# The surface that needs a company id, and therefore a named watchlist stock.
COMPANY_SURFACES = frozenset({TijoriEventsSurface.COMPANY_TIMELINE})

# What a run with no ``--surface`` acquires: every market-wide surface.
BREADTH_SURFACES: tuple[TijoriEventsSurface, ...] = tuple(
    surface
    for surface in TijoriEventsSurface
    if surface not in NOT_STATIC_SURFACES and surface not in COMPANY_SURFACES
)

SURFACE_PAGE_LABELS: dict[TijoriEventsSurface, str] = {
    TijoriEventsSurface.UPCOMING: "upcoming-events",
    TijoriEventsSurface.QUARTERLY_RESULTS: "quarterly-results",
    TijoriEventsSurface.TIMELINE: "timeline",
    TijoriEventsSurface.COMPANY_TIMELINE: "company-timeline fragment",
    TijoriEventsSurface.CONCALL_MONITOR: "concall-monitor",
}


# Auth markers each surface MUST publish, per surface rather than per family.
# Checking a marker only when it happens to be present is a gate that passes
# whenever the marker disappears, so ``/in/timeline`` — the one surface observed
# to publish ``is_auth`` — requires it.
SURFACE_REQUIRED_AUTH_ISLANDS: dict[TijoriEventsSurface, tuple[str, ...]] = {
    TijoriEventsSurface.UPCOMING: (IS_LANDING_PAGE_ISLAND_ID, PLAN_DETAILS_ISLAND_ID),
    TijoriEventsSurface.QUARTERLY_RESULTS: (IS_LANDING_PAGE_ISLAND_ID, PLAN_DETAILS_ISLAND_ID),
    TijoriEventsSurface.TIMELINE: (
        IS_LANDING_PAGE_ISLAND_ID,
        PLAN_DETAILS_ISLAND_ID,
        IS_AUTH_ISLAND_ID,
    ),
}

# Keys ``plan_details`` carried on every capture. A plan object that satisfies
# neither shape is not a plan: treating any non-empty dict as proof of a
# subscription would let an unrelated island through the auth gate.
PLAN_TIER_FIELD = "plan_tier"
PLAN_ID_FIELD = "id"
PLAN_NAME_FIELD = "name"


class TijoriEventsScope(StrEnum):
    """Whether an artifact is about one issuer or about the whole market."""

    MARKET_WIDE = "market_wide"
    COMPANY = "company"


class TijoriEventsCapabilityState(StrEnum):
    """What this adapter can actually acquire from one capability, as captured.

    A surface is a page; a capability is one dataset that page offers. The two
    are not the same, and reporting only surfaces overstates acquisition: the
    upcoming-events page serves its results tab statically while its concall tab
    is an empty shell, and the timeline page serves a filter taxonomy while its
    event feed arrives by XHR. Every state below is a DATED observation, never a
    standing claim about Tijori.
    """

    ACQUIRED = "acquired"
    XHR_NOT_ACQUIRED = "xhr_not_acquired"
    EXTERNAL_PRODUCT_AT_CAPTURE = "external_product_at_capture"


class TijoriEventsCapability(StrEnum):
    """One named dataset an event surface offers, acquirable or not."""

    UPCOMING_RESULTS = "upcoming-results"
    UPCOMING_CONCALLS_FEED = "upcoming-concalls-feed"
    QUARTERLY_RESULTS_LISTING = "quarterly-results-listing"
    TIMELINE_TAXONOMY = "timeline-taxonomy"
    TIMELINE_FEED = "timeline-feed"
    COMPANY_TIMELINE_EVENTS = "company-timeline-events"
    CONCALL_MONITOR = "concall-monitor"


class TijoriCapabilityDeclaration(BaseModel):
    """What one capability is, which surface serves it, and what it yields."""

    model_config = ConfigDict(frozen=True)

    capability: TijoriEventsCapability
    surface: TijoriEventsSurface
    state: TijoriEventsCapabilityState
    note: str


CAPABILITY_DECLARATIONS: tuple[TijoriCapabilityDeclaration, ...] = (
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.UPCOMING_RESULTS,
        surface=TijoriEventsSurface.UPCOMING,
        state=TijoriEventsCapabilityState.ACQUIRED,
        note=UPCOMING_RESULTS_ACQUIRED,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.UPCOMING_CONCALLS_FEED,
        surface=TijoriEventsSurface.UPCOMING,
        state=TijoriEventsCapabilityState.XHR_NOT_ACQUIRED,
        note=UPCOMING_CONCALLS_NOT_IN_DOCUMENT,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.QUARTERLY_RESULTS_LISTING,
        surface=TijoriEventsSurface.QUARTERLY_RESULTS,
        state=TijoriEventsCapabilityState.ACQUIRED,
        note=QUARTERLY_RESULTS_ACQUIRED,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.TIMELINE_TAXONOMY,
        surface=TijoriEventsSurface.TIMELINE,
        state=TijoriEventsCapabilityState.ACQUIRED,
        note=TIMELINE_TAXONOMY_ACQUIRED,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.TIMELINE_FEED,
        surface=TijoriEventsSurface.TIMELINE,
        state=TijoriEventsCapabilityState.XHR_NOT_ACQUIRED,
        note=TIMELINE_FEED_NOT_IN_DOCUMENT,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.COMPANY_TIMELINE_EVENTS,
        surface=TijoriEventsSurface.COMPANY_TIMELINE,
        state=TijoriEventsCapabilityState.ACQUIRED,
        note=COMPANY_TIMELINE_ACQUIRED,
    ),
    TijoriCapabilityDeclaration(
        capability=TijoriEventsCapability.CONCALL_MONITOR,
        surface=TijoriEventsSurface.CONCALL_MONITOR,
        state=TijoriEventsCapabilityState.EXTERNAL_PRODUCT_AT_CAPTURE,
        note=CONCALL_NOT_STATIC_REASON,
    ),
)


def capabilities_of(surface: TijoriEventsSurface) -> tuple[TijoriCapabilityDeclaration, ...]:
    """Every capability one surface offers, in declaration order."""
    return tuple(
        declaration for declaration in CAPABILITY_DECLARATIONS if declaration.surface is surface
    )


class TijoriCapabilityOutcome(BaseModel):
    """What one run actually got from one capability.

    ``element_count`` is populated only for an ACQUIRED capability, and it counts
    that capability's own elements. Attaching counts to capabilities rather than
    to pages is the point: a timeline artifact reporting 15 elements must not be
    readable as 15 market events when those 15 are filter types and viewer lists
    and the event feed was never served.
    """

    model_config = ConfigDict(frozen=True)

    capability: TijoriEventsCapability
    surface: TijoriEventsSurface
    state: TijoriEventsCapabilityState
    element_count: int | None = None
    note: str


class TijoriEventsOutcome(StrEnum):
    """Acquisition outcome of one event surface.

    ``OK`` and ``OK_EMPTY`` are the only outcomes an artifact can be written
    with; every other failure mode is a typed refusal. The last two are run-level
    verdicts rather than artifact outcomes, and they are deliberately distinct:
    ``NOT_STATIC`` means the surface's document verifiably carries nothing to
    parse, while ``SKIPPED`` means this run declined to attempt an acquirable
    surface. Reporting the second as the first would record a fact about Tijori
    that this repo has not established.
    """

    OK = "ok"
    OK_EMPTY = "ok_empty"
    NOT_STATIC = "not_static"
    SKIPPED = "skipped"


class TijoriEventsIdentityStrength(StrEnum):
    """How strongly one event artifact's issuer identity is established.

    ``CONFIGURED_URL_ONLY`` carries the same meaning and the same serialized
    value as :class:`~fundamentals.ingest.tijori_analysis_models.TijoriIdentityStrength`'s
    member of that name. It is restated here rather than imported because a
    ``StrEnum`` cannot be extended, and this family needs a case that per-company
    surfaces have no word for: a document that is about no issuer at all.
    """

    NO_COMPANY_IDENTITY = "no_company_identity"
    CONFIGURED_URL_ONLY = "configured_url_only"


class TijoriEventsError(TijoriParseError):
    """An event surface does not satisfy its typed shape."""


class TijoriEventsSchemaError(TijoriEventsError):
    """A raw event document is shaped in a way this contract cannot address."""


class TijoriEventsAuthError(TijoriEventsError):
    """An event document does not prove it was served to a subscribed session."""


class TijoriEventsSurfaceError(TijoriEventsError):
    """A surface was requested that this adapter will not acquire."""


class TijoriEventsIdentityError(TijoriEventsError):
    """A company-scoped response is about an issuer other than the one requested."""


def parse_events_surface(name: str) -> TijoriEventsSurface:
    """Validate one caller-supplied surface name against the modeled set."""
    try:
        return TijoriEventsSurface(name)
    except ValueError as error:
        supported = ", ".join(surface.value for surface in TijoriEventsSurface)
        raise TijoriEventsSurfaceError(
            f"unsupported Tijori event surface {name!r}; supported surfaces: {supported}"
        ) from error


class TijoriEventsCell(BaseModel):
    """One addressable event-surface scalar: its lexeme plus its numeric reading."""

    model_config = ConfigDict(frozen=True)

    value: Decimal | None
    raw_text: str
    provenance: Provenance


class TijoriCompanyRef(BaseModel):
    """One company a market-wide listing names, as data on the row it appeared on.

    ``watchlist_symbol`` is populated only when ``slug`` matches a verified
    watchlist entry. A row for a company the watchlist does not track is ordinary
    market data: the miss is recorded, never raised.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    href: str | None = None
    slug: str | None = None
    symbol_text: str | None = None
    watchlist_symbol: str | None = None
    on_watchlist: bool = False


class TijoriEventsMetadata(BaseModel):
    """Scope, identity, auth basis, and acquisition metadata for one surface."""

    model_config = ConfigDict(frozen=True)

    surface: TijoriEventsSurface
    scope: TijoriEventsScope
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    identity_basis: str
    identity_strength: TijoriEventsIdentityStrength
    auth_basis: str
    auth_marker_islands: tuple[str, ...] = ()
    access: TijoriTableAccessMetadata | None = None
    slug: str | None = None
    symbol: str | None = None
    company_id: int | None = None


class TijoriEventsArtifactBase(BaseModel):
    """Shared shape of every typed event artifact.

    ``outcome``, ``note``, and ``capabilities`` are stamped in one place after
    the builder returns. Emptiness is decided by ``element_count`` AND by
    ``quarantined_rows``: a zero count that is explained by rows this adapter
    could not address is schema drift, not an empty surface, and reporting it as
    ``OK_EMPTY`` would turn a parse failure into a claim about the market.
    """

    model_config = ConfigDict(frozen=True)

    surface: TijoriEventsSurface
    metadata: TijoriEventsMetadata
    outcome: TijoriEventsOutcome = TijoriEventsOutcome.OK
    note: str | None = None
    capabilities: tuple[TijoriCapabilityOutcome, ...] = ()
    unmodeled_fields_json: str | None = None

    @property
    def element_count(self) -> int:
        """Number of top-level data elements this artifact carries."""
        raise NotImplementedError

    @property
    def quarantined_rows(self) -> tuple[str, ...]:
        """Rows this artifact could not address, and therefore did not count."""
        return ()


class TijoriEventsFetch(BaseModel):
    """One acquired event surface beside the exact bytes it was built from."""

    model_config = ConfigDict(frozen=True)

    artifact: TijoriEventsArtifactBase
    raw_body: bytes


class TijoriListingRow(BaseModel):
    """One row of a market-wide listing table, aligned to its column labels."""

    model_config = ConfigDict(frozen=True)

    position: int
    company: TijoriCompanyRef
    cells: tuple[TijoriEventsCell, ...]
    alternate_texts: tuple[str, ...] = ()
    unaligned_raw_values: tuple[str, ...] = ()


class TijoriUpcomingEvents(TijoriEventsArtifactBase):
    """The default listing of upcoming corporate events.

    ``lazy_tables`` names the hidden ``*_loader`` shells the page also renders.
    They carry no data — they are pagination placeholders — and are recorded so
    that a future run finding data in them is visibly a change, not a surprise.
    """

    column_labels: tuple[str, ...]
    rows: tuple[TijoriListingRow, ...]
    declared_shown: int | None = None
    declared_total: int | None = None
    lazy_tables: tuple[str, ...] = ()
    malformed_rows: tuple[str, ...] = ()

    @property
    def element_count(self) -> int:
        """Number of listed upcoming events."""
        return len(self.rows)

    @property
    def quarantined_rows(self) -> tuple[str, ...]:
        """Listing rows that rendered without their machine-readable slug."""
        return self.malformed_rows


class TijoriMetricPair(BaseModel):
    """One labelled headline metric printed beside a result item's header."""

    model_config = ConfigDict(frozen=True)

    label: str
    cell: TijoriEventsCell


class TijoriResultRow(BaseModel):
    """One line item of a freshly-announced result, aligned to its periods.

    A row whose value count disagrees with the column count yields no cells and
    keeps its lexemes in ``unaligned_raw_values`` instead: which end is missing
    is not determinable from the markup, so alignment is never guessed.
    """

    model_config = ConfigDict(frozen=True)

    position: int
    label: str
    cells: tuple[TijoriEventsCell, ...]
    unaligned_raw_values: tuple[str, ...] = ()


class TijoriResultItem(BaseModel):
    """One announced result: its company, its date, and its comparison table.

    The item's primary facts are anchored values, not bare strings: ``company``
    describes the reference, while ``company_cell``, ``announced``, and
    ``detail_link`` carry the lexeme AND the anchor that re-finds it. The header
    of a result item is as much a source claim as a number in its table, so it is
    addressed the same way and the duplicate-anchor backstop sees it.
    """

    model_config = ConfigDict(frozen=True)

    position: int
    company: TijoriCompanyRef
    company_cell: TijoriEventsCell
    announced: TijoriEventsCell
    headline_metrics: tuple[TijoriMetricPair, ...] = ()
    column_labels: tuple[str, ...] = ()
    rows: tuple[TijoriResultRow, ...] = ()
    detail_link: TijoriEventsCell | None = None


class TijoriQuarterlyResults(TijoriEventsArtifactBase):
    """The market-wide listing of freshly-announced quarterly results."""

    items: tuple[TijoriResultItem, ...]
    declared_shown: int | None = None
    declared_total: int | None = None
    lazy_tables: tuple[str, ...] = ()

    @property
    def element_count(self) -> int:
        """Number of announced results this listing carries."""
        return len(self.items)


class TijoriEventType(BaseModel):
    """One node of the timeline's event-type taxonomy.

    A leaf carries the integer ``event_id`` the filter posts back; a group
    carries children and no id. ``path`` is the position-led address of the node
    within the taxonomy, so two siblings sharing a display name stay distinct.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    event_id: TijoriEventsCell | None = None
    is_checked: bool | None = None
    children: tuple[TijoriEventType, ...] = ()
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None

    @property
    def leaf_count(self) -> int:
        """Number of selectable event types at or below this node."""
        if not self.children:
            return 1
        return sum(child.leaf_count for child in self.children)


class TijoriNamedRef(BaseModel):
    """One id/name reference the timeline page publishes for the viewer."""

    model_config = ConfigDict(frozen=True)

    position: int
    entity_id: TijoriEventsCell | None
    name: str
    unmodeled_fields_json: str | None = None
    invalid_fields_json: str | None = None


class TijoriIslandScalar(BaseModel):
    """One single-valued timeline island, anchored to the island it came from."""

    model_config = ConfigDict(frozen=True)

    island_id: str
    cell: TijoriEventsCell


class TijoriSiteTimeline(TijoriEventsArtifactBase):
    """What the initial ``/in/timeline`` document actually publishes.

    FACT (owner capture, 2026-08-25): the ``eventsList`` island is the taxonomy
    of event TYPES the filter panel offers — nested groups whose leaves carry an
    id, a name, and a default checked state — not a feed of occurred events. The
    feed table on this page renders as an empty loader shell. Naming the taxonomy
    "the events" would misreport a filter catalogue as market activity, so the
    absence of a feed is recorded explicitly in ``feed_status``.
    """

    event_types: tuple[TijoriEventType, ...] = ()
    watchlists: tuple[TijoriNamedRef, ...] = ()
    portfolios: tuple[TijoriNamedRef, ...] = ()
    sectors: tuple[TijoriNamedRef, ...] = ()
    scalars: tuple[TijoriIslandScalar, ...] = ()
    feed_status: str = TIMELINE_FEED_NOT_IN_DOCUMENT

    @property
    def element_count(self) -> int:
        """Number of addressable elements: event types, references, and scalars."""
        return (
            sum(node.leaf_count for node in self.event_types)
            + len(self.watchlists)
            + len(self.portfolios)
            + len(self.sectors)
            + len(self.scalars)
        )


class TijoriEventDetailRow(BaseModel):
    """One row of a detail table rendered inside a timeline event."""

    model_config = ConfigDict(frozen=True)

    position: int
    label: str
    cells: tuple[TijoriEventsCell, ...]
    unaligned_raw_values: tuple[str, ...] = ()


class TijoriEventDetailTable(BaseModel):
    """One table rendered inside a timeline event's content cell.

    Tijori renders these as ``dict-table`` and as ``inner-table``; the rendered
    class is preserved rather than used to select, because the addressing and the
    reading are identical either way.
    """

    model_config = ConfigDict(frozen=True)

    position: int
    table_class: str | None
    column_labels: tuple[str, ...] = ()
    rows: tuple[TijoriEventDetailRow, ...] = ()


class TijoriRetainedIsland(BaseModel):
    """One JSON island retained verbatim beside its anchor.

    A timeline event embeds its source payload — a tweet, a filing envelope — as
    an island keyed by the numeric EVENT id. The payload is kept as published
    rather than modeled: this adapter does not know the shape of every third
    party Tijori embeds, and inventing one would drop what it guessed wrong.

    ``payload_json`` is the island's EXACT rendered body, never a decode and
    re-serialize of it. Round-tripping through a parser is lossy in ways that
    matter for a retained source: ``1.25`` would come back as a float, key order
    would change, and an unparseable body would have nothing left to retain. An
    island whose body is not valid JSON keeps its bytes and records why in
    ``decode_error`` — the retention is the point, and the parse is only a check.
    """

    model_config = ConfigDict(frozen=True)

    island_id: str
    payload_json: str
    decode_error: str | None = None
    provenance: Provenance


class TijoriTimelineEvent(BaseModel):
    """One event row of the per-company timeline fragment.

    ``group_id`` and ``is_grouped_child`` preserve the fragment's own grouping:
    Tijori renders a parent row plus collapsed sibling rows sharing one
    ``data-grp``. A collapsed child publishes no timestamp of its own, and none
    is inferred for it — ``announced`` is then ``None`` rather than borrowed
    from the parent.

    Every primary fact of the row is an anchored value: the company, the event
    name, the date, the rendered content, and each outbound link. ``event_name``
    is kept as a plain string beside ``event_cell`` because it is the row's
    address, the same way a table row keeps its label beside its cells.
    """

    model_config = ConfigDict(frozen=True)

    position: int
    row_id: str
    group_id: str | None = None
    is_grouped_child: bool = False
    company: TijoriCompanyRef
    company_cell: TijoriEventsCell
    event_name: str
    event_cell: TijoriEventsCell
    event_company_id_text: str | None = None
    announced: TijoriEventsCell | None = None
    detail_tables: tuple[TijoriEventDetailTable, ...] = ()
    islands: tuple[TijoriRetainedIsland, ...] = ()
    link_cells: tuple[TijoriEventsCell, ...] = ()
    content_cell: TijoriEventsCell


class TijoriCompanyTimeline(TijoriEventsArtifactBase):
    """The per-company timeline fragment's events, in rendered order.

    ``identity_mismatch_rows`` retains, verbatim, every rendered row whose own
    slug or ``company-id`` disagreed with the company this run asked for. Such a
    row is never counted as an event: the fragment is addressed by company id, so
    a row about a different issuer is either drift or the wrong page, and
    silently keeping it would attribute one company's events to another.
    """

    events: tuple[TijoriTimelineEvent, ...] = ()
    malformed_rows: tuple[str, ...] = ()
    identity_mismatch_rows: tuple[str, ...] = ()

    @property
    def element_count(self) -> int:
        """Number of timeline events the fragment rendered for this company."""
        return len(self.events)

    @property
    def quarantined_rows(self) -> tuple[str, ...]:
        """Rows excluded as unaddressable or as belonging to another issuer."""
        return self.malformed_rows + self.identity_mismatch_rows
