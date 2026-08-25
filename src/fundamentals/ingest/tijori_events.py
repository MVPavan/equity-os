"""Builders for Tijori's site-level and timeline event surfaces.

Each builder turns one raw response into its typed contract from
:mod:`fundamentals.ingest.tijori_events_models`. The rendered-HTML reduction
lives in :mod:`fundamentals.ingest.tijori_events_html`, the shared element
helpers and the family's anchor convention in
:mod:`fundamentals.ingest.tijori_events_common`, and transport plus the
per-surface entry point in :mod:`fundamentals.ingest.tijori_source`, which
imports this module. Dependency flow is one-way.

Four rules hold across every builder, matching the committed Tijori families:

* addressing is position-led — nothing in these documents guarantees a unique
  company or row label within a listing, so the index leads the path and the
  name follows it;
* an element with no readable address is fatal, because an unaddressable element
  makes every downstream selection on it ambiguous;
* anything published but not modeled is preserved verbatim and drift-logged,
  never dropped, and a modeled key published unreadably is retained separately;
* a numeric lexeme reads through the shared Tijori cell rule, so the source text
  survives beside its ``Decimal | None`` reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import structlog

from fundamentals.ingest.tijori_events_common import (
    PATH_SEPARATOR,
    EventsContext,
    as_list,
    as_object,
    column_label,
    company_ref,
    invalid_values_json,
    island_absent,
    island_cell,
    optional_bool,
    reject_duplicate_anchors,
    table_cell,
    unmodeled,
)
from fundamentals.ingest.tijori_events_company import build_company_timeline
from fundamentals.ingest.tijori_events_html import (
    RawResultItem,
    collect_quarterly_results,
    collect_upcoming,
)
from fundamentals.ingest.tijori_events_models import (
    COMPANY_TIMELINE_NEEDS_STOCK,
    CONCALL_NOT_STATIC_REASON,
    EMPTY_LISTING_NOTE,
    EVENT_TYPES_ISLAND_ID,
    IS_AUTH_ISLAND_ID,
    IS_LANDING_PAGE_ISLAND_ID,
    MARKET_AUTH_BASIS,
    MARKET_IDENTITY_BASIS,
    MAX_EVENT_TYPE_DEPTH,
    NOT_STATIC_SURFACES,
    PLAN_ID_FIELD,
    PLAN_NAME_FIELD,
    PLAN_TIER_FIELD,
    PORTFOLIOS_ISLAND_ID,
    SECTORS_ISLAND_ID,
    SURFACE_PAGE_LABELS,
    SURFACE_REQUIRED_AUTH_ISLANDS,
    TIMELINE_SCALAR_ISLAND_IDS,
    WATCHLISTS_ISLAND_ID,
    TijoriCapabilityOutcome,
    TijoriEventsArtifactBase,
    TijoriEventsAuthError,
    TijoriEventsCapabilityState,
    TijoriEventsCell,
    TijoriEventsIdentityStrength,
    TijoriEventsMetadata,
    TijoriEventsOutcome,
    TijoriEventsSchemaError,
    TijoriEventsScope,
    TijoriEventsSurface,
    TijoriEventsSurfaceError,
    TijoriEventType,
    TijoriIslandScalar,
    TijoriListingRow,
    TijoriMetricPair,
    TijoriNamedRef,
    TijoriQuarterlyResults,
    TijoriResultItem,
    TijoriResultRow,
    TijoriSiteTimeline,
    TijoriUpcomingEvents,
    capabilities_of,
)
from fundamentals.ingest.tijori_page import collect_islands, decode_document
from fundamentals.ingest.tijori_tables import (
    PLAN_DETAILS_ISLAND_ID,
    build_page_access,
    raw_json,
)

_LOGGER = structlog.get_logger(__name__)

_UPCOMING_TABLE_ID = "html:upcoming-events/results"
_QUARTERLY_TABLE_ID = "html:quarterly-results"
_EVENT_TYPES_TABLE_KEY = "event_types"
_ISLAND_SCALAR_TABLE_KEY = "island"
_ISLAND_VALUE_LABEL = "value"
_ISLAND_ID_LABEL = "id"
_METRIC_COLUMN_LABEL = "metric"
_HEADER_ROW_SEGMENT = "header"
_COMPANY_COLUMN_LABEL = "company"
_DATE_COLUMN_LABEL = "date"
_LINK_COLUMN_LABEL = "link"
# Rendered position of each primary fact in a result item's header row.
_COMPANY_COLUMN = 0
_DATE_COLUMN = 1
_LINK_COLUMN = 2

_ID_FIELD = "id"
_NAME_FIELD = "name"
_GROUP_FIELD = "group"
_EVENTS_FIELD = "events"
_IS_CHECKED_FIELD = "is_checked"

_GROUP_FIELDS = frozenset({_GROUP_FIELD, _EVENTS_FIELD, _IS_CHECKED_FIELD})
_LEAF_FIELDS = frozenset({_ID_FIELD, _NAME_FIELD, _IS_CHECKED_FIELD})
_NAMED_REF_FIELDS = frozenset({_ID_FIELD, _NAME_FIELD})

_MARKET_OPTIONAL_ISLANDS = (IS_AUTH_ISLAND_ID,)
_TIMELINE_OPTIONAL_ISLANDS = (
    EVENT_TYPES_ISLAND_ID,
    WATCHLISTS_ISLAND_ID,
    PORTFOLIOS_ISLAND_ID,
    SECTORS_ISLAND_ID,
) + TIMELINE_SCALAR_ISLAND_IDS


def _is_plan_object(plan: Any) -> bool:
    """True when ``plan_details`` carries a shape every capture actually published.

    Accepting any non-empty object would let an unrelated island — or an
    error envelope that happens to be a dict — satisfy the auth gate. The
    observed plan object always carries ``plan_tier``, and always carries ``id``
    and ``name`` beside it, so either shape is proof and nothing else is.
    """
    if not isinstance(plan, dict):
        return False
    tier = plan.get(PLAN_TIER_FIELD)
    if isinstance(tier, str) and tier.strip():
        return True
    name = plan.get(PLAN_NAME_FIELD)
    return PLAN_ID_FIELD in plan and isinstance(name, str) and bool(name.strip())


def _verified_market_islands(
    document: str, *, surface: TijoriEventsSurface, optional_islands: tuple[str, ...] = ()
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Prove one market page was served to a subscribed session, or refuse it.

    AUTH FACT (owner premium capture, 2026-08-25): these pages carry no
    ``company_details`` island, so the per-company identity gate has nothing to
    check. What they DO carry is ``plan_details`` — the subscriber's plan
    object — beside ``is_landing_page``, which an authenticated response renders
    as an empty string, and, on ``/in/timeline``, ``is_auth: true``.

    The markers each surface must publish come from
    :data:`SURFACE_REQUIRED_AUTH_ISLANDS`, not from what a given response happens
    to contain. A marker checked only when present is a gate that opens the
    moment the marker disappears, so ``/in/timeline`` REQUIRES ``is_auth``: a
    response that dropped it would otherwise pass on the strength of two markers
    an expired session can still render.
    """
    required = SURFACE_REQUIRED_AUTH_ISLANDS[surface]
    islands = collect_islands(
        document,
        required_islands=required,
        optional_islands=tuple(
            island_id
            for island_id in _MARKET_OPTIONAL_ISLANDS + optional_islands
            if island_id not in required
        ),
    )
    landing = islands[IS_LANDING_PAGE_ISLAND_ID]
    if landing:
        raise TijoriEventsAuthError(
            f"tijori event page published {IS_LANDING_PAGE_ISLAND_ID}={raw_json(landing)}: "
            "this is the anonymous landing page, not a subscriber response"
        )
    if not _is_plan_object(islands[PLAN_DETAILS_ISLAND_ID]):
        raise TijoriEventsAuthError(
            f"tijori event page published no usable {PLAN_DETAILS_ISLAND_ID} object "
            f"(expected {PLAN_TIER_FIELD!r}, or {PLAN_ID_FIELD!r} with {PLAN_NAME_FIELD!r}); "
            "the response does not prove a subscribed session"
        )
    markers = [IS_LANDING_PAGE_ISLAND_ID, PLAN_DETAILS_ISLAND_ID]
    if IS_AUTH_ISLAND_ID in islands:
        if islands[IS_AUTH_ISLAND_ID] is not True:
            raise TijoriEventsAuthError("tijori event page response is not authenticated")
        markers.append(IS_AUTH_ISLAND_ID)
    return islands, tuple(markers)


def _market_metadata(
    islands: dict[str, Any], markers: tuple[str, ...], context: EventsContext
) -> TijoriEventsMetadata:
    """Assemble the metadata one market-wide artifact carries."""
    return TijoriEventsMetadata(
        surface=context.surface,
        scope=TijoriEventsScope.MARKET_WIDE,
        source_url=context.source_url,
        file_sha256=context.content_sha256,
        retrieved_at=context.retrieved_at,
        identity_basis=MARKET_IDENTITY_BASIS,
        identity_strength=TijoriEventsIdentityStrength.NO_COMPANY_IDENTITY,
        auth_basis=MARKET_AUTH_BASIS,
        auth_marker_islands=markers,
        access=build_page_access(
            financials_locks=None, plan_details=islands.get(PLAN_DETAILS_ISLAND_ID)
        ),
    )


def _row_address(name: str, slug: str | None, *, surface: str, position: int) -> str:
    """Address one listing row by position and by whichever identifier it rendered."""
    identifier = slug or name
    if not identifier.strip():
        raise TijoriEventsSchemaError(
            f"tijori {surface} row {position} carries neither a slug nor a company name"
        )
    return f"{position}{PATH_SEPARATOR}{identifier}"


def build_upcoming(document: str, context: EventsContext) -> TijoriUpcomingEvents:
    """Build the default listing of upcoming corporate events."""
    islands, markers = _verified_market_islands(document, surface=context.surface)
    listing = collect_upcoming(document)
    rows: list[TijoriListingRow] = []
    for index, raw_row in enumerate(listing.rows):
        row_path = _row_address(
            raw_row.company.name,
            raw_row.company.slug,
            surface=context.surface.value,
            position=index,
        )
        aligned = len(raw_row.cell_texts) == len(listing.column_labels)
        rows.append(
            TijoriListingRow(
                position=index,
                company=company_ref(raw_row.company, context),
                cells=(
                    tuple(
                        table_cell(
                            text,
                            context,
                            table_id=_UPCOMING_TABLE_ID,
                            row_path=row_path,
                            column_index=column_index,
                            column_label=column_label(listing.column_labels, column_index),
                        )
                        for column_index, text in enumerate(raw_row.cell_texts)
                    )
                    if aligned
                    else ()
                ),
                alternate_texts=raw_row.alternate_texts,
                unaligned_raw_values=() if aligned else raw_row.cell_texts,
            )
        )
    return TijoriUpcomingEvents(
        surface=context.surface,
        metadata=_market_metadata(islands, markers, context),
        column_labels=listing.column_labels,
        rows=tuple(rows),
        declared_shown=listing.pagination.shown,
        declared_total=listing.pagination.total,
        lazy_tables=listing.lazy_tables,
        malformed_rows=listing.malformed_rows,
    )


def _header_cell(
    text: str, context: EventsContext, *, table_id: str, column_index: int, label: str
) -> TijoriEventsCell:
    """Anchor one primary fact printed in a result item's header.

    An item's company, date, and detail link are source claims exactly as its
    numbers are, so they are addressed the same way rather than carried as bare
    strings that nothing can re-find. The header row is addressed separately from
    the metric pairs, which sit below it at ``header/{index}/{label}``.
    """
    return table_cell(
        text,
        context,
        table_id=table_id,
        row_path=_HEADER_ROW_SEGMENT,
        column_index=column_index,
        column_label=label,
    )


def _headline_metrics(
    raw_item: RawResultItem, context: EventsContext, *, table_id: str
) -> tuple[TijoriMetricPair, ...]:
    """Read the labelled metrics printed beside one result item's header.

    Labels and values render as two sibling span lists, so a count disagreement
    means the pairing is not determinable from the markup. The metrics are then
    omitted rather than paired by guess, and the drift is logged.
    """
    labels = raw_item.metric_labels
    values = raw_item.metric_values
    if len(labels) != len(values):
        _LOGGER.warning(
            "tijori_events_metric_pairs_unaligned",
            surface=context.surface.value,
            table=table_id,
            labels=len(labels),
            values=len(values),
        )
        return ()
    return tuple(
        TijoriMetricPair(
            label=label,
            cell=table_cell(
                value,
                context,
                table_id=table_id,
                row_path=f"{_HEADER_ROW_SEGMENT}{PATH_SEPARATOR}{index}{PATH_SEPARATOR}{label}",
                column_index=index,
                column_label=_METRIC_COLUMN_LABEL,
            ),
        )
        for index, (label, value) in enumerate(zip(labels, values, strict=True))
    )


def _result_rows(
    raw_item: RawResultItem, context: EventsContext, *, table_id: str
) -> tuple[TijoriResultRow, ...]:
    """Build one result item's line items, aligned to its period columns."""
    value_labels = raw_item.table.column_labels[1:]
    rows: list[TijoriResultRow] = []
    for row_index, (label, values) in enumerate(
        zip(raw_item.table.row_labels, raw_item.table.row_values, strict=True)
    ):
        row_path = f"{row_index}{PATH_SEPARATOR}{label}"
        aligned = len(values) == len(value_labels)
        rows.append(
            TijoriResultRow(
                position=row_index,
                label=label,
                cells=(
                    tuple(
                        table_cell(
                            text,
                            context,
                            table_id=table_id,
                            row_path=row_path,
                            column_index=column_index,
                            column_label=column_label(value_labels, column_index),
                        )
                        for column_index, text in enumerate(values)
                    )
                    if aligned
                    else ()
                ),
                unaligned_raw_values=() if aligned else values,
            )
        )
    return tuple(rows)


def build_quarterly_results(document: str, context: EventsContext) -> TijoriQuarterlyResults:
    """Build the market-wide listing of freshly-announced quarterly results."""
    islands, markers = _verified_market_islands(document, surface=context.surface)
    page = collect_quarterly_results(document)
    items: list[TijoriResultItem] = []
    for index, raw_item in enumerate(page.items):
        address = _row_address(
            raw_item.company.name,
            raw_item.company.slug,
            surface=context.surface.value,
            position=index,
        )
        table_id = f"{_QUARTERLY_TABLE_ID}{PATH_SEPARATOR}{address}"
        items.append(
            TijoriResultItem(
                position=index,
                company=company_ref(raw_item.company, context),
                company_cell=_header_cell(
                    raw_item.company.name,
                    context,
                    table_id=table_id,
                    column_index=_COMPANY_COLUMN,
                    label=_COMPANY_COLUMN_LABEL,
                ),
                announced=_header_cell(
                    raw_item.announced_text,
                    context,
                    table_id=table_id,
                    column_index=_DATE_COLUMN,
                    label=_DATE_COLUMN_LABEL,
                ),
                headline_metrics=_headline_metrics(raw_item, context, table_id=table_id),
                column_labels=raw_item.table.column_labels,
                rows=_result_rows(raw_item, context, table_id=table_id),
                detail_link=(
                    None
                    if raw_item.detail_href is None
                    else _header_cell(
                        raw_item.detail_href,
                        context,
                        table_id=table_id,
                        column_index=_LINK_COLUMN,
                        label=_LINK_COLUMN_LABEL,
                    )
                ),
            )
        )
    return TijoriQuarterlyResults(
        surface=context.surface,
        metadata=_market_metadata(islands, markers, context),
        items=tuple(items),
        declared_shown=page.pagination.shown,
        declared_total=page.pagination.total,
        lazy_tables=page.lazy_tables,
    )


def _event_types(
    raw_nodes: Any, context: EventsContext, *, label: str, prefix: str = "", depth: int = 0
) -> tuple[TijoriEventType, ...]:
    """Build the taxonomy of event types the timeline filter offers.

    Position leads every address: two groups legitimately share a display name
    ('Others' appears under several parents), and a node with no readable name is
    fatal because an unaddressable node makes every selection below it ambiguous.

    Nesting is bounded for the same reason the element tree is: this walks
    untrusted JSON recursively, and the live taxonomy is three levels deep, so a
    document deeper than :data:`MAX_EVENT_TYPE_DEPTH` is drift to refuse rather
    than a stack to exhaust.
    """
    if depth > MAX_EVENT_TYPE_DEPTH:
        raise TijoriEventsSchemaError(
            f"tijori events {label} nests event types more than {MAX_EVENT_TYPE_DEPTH} deep; "
            "refusing to walk a taxonomy this adapter cannot bound"
        )
    built: list[TijoriEventType] = []
    for index, raw_node in enumerate(as_list(raw_nodes, label)):
        node = as_object(raw_node, f"{label} entry {index}")
        name = node.get(_GROUP_FIELD) or node.get(_NAME_FIELD)
        if not isinstance(name, str) or not name.strip():
            raise TijoriEventsSchemaError(
                f"tijori events {label} entry {index} publishes neither a readable "
                f"{_GROUP_FIELD!r} nor a readable {_NAME_FIELD!r}"
            )
        path = f"{prefix}{index}{PATH_SEPARATOR}{name}"
        is_group = _EVENTS_FIELD in node
        built.append(
            TijoriEventType(
                path=path,
                name=name,
                event_id=(
                    None
                    if is_group
                    else island_cell(
                        node.get(_ID_FIELD),
                        context,
                        island_id=EVENT_TYPES_ISLAND_ID,
                        table_key=_EVENT_TYPES_TABLE_KEY,
                        row_label=path,
                        column_label=_ISLAND_ID_LABEL,
                    )
                ),
                is_checked=optional_bool(node, _IS_CHECKED_FIELD),
                children=(
                    _event_types(
                        node[_EVENTS_FIELD],
                        context,
                        label=f"{label} {name} events",
                        prefix=f"{path}{PATH_SEPARATOR}",
                        depth=depth + 1,
                    )
                    if is_group
                    else ()
                ),
                unmodeled_fields_json=unmodeled(
                    node, _GROUP_FIELDS if is_group else _LEAF_FIELDS, context=context, element=path
                ),
                invalid_fields_json=invalid_values_json(
                    node, context=context, element=path, booleans=(_IS_CHECKED_FIELD,)
                ),
            )
        )
    return tuple(built)


def _named_refs(
    raw_refs: Any, context: EventsContext, *, island_id: str
) -> tuple[TijoriNamedRef, ...]:
    """Build one of the timeline page's id/name reference lists."""
    built: list[TijoriNamedRef] = []
    for index, raw_ref in enumerate(as_list(raw_refs, f"island {island_id}")):
        ref = as_object(raw_ref, f"island {island_id} entry {index}")
        name = ref.get(_NAME_FIELD)
        if not isinstance(name, str) or not name.strip():
            raise TijoriEventsSchemaError(
                f"tijori events island {island_id!r} entry {index} publishes no readable "
                f"{_NAME_FIELD!r}"
            )
        element = f"{index}{PATH_SEPARATOR}{name}"
        built.append(
            TijoriNamedRef(
                position=index,
                entity_id=island_cell(
                    ref.get(_ID_FIELD),
                    context,
                    island_id=island_id,
                    table_key=island_id,
                    row_label=element,
                    column_label=_ISLAND_ID_LABEL,
                ),
                name=name,
                unmodeled_fields_json=unmodeled(
                    ref, _NAMED_REF_FIELDS, context=context, element=f"{island_id}/{element}"
                ),
                invalid_fields_json=invalid_values_json(
                    ref, context=context, element=f"{island_id}/{element}"
                ),
            )
        )
    return tuple(built)


def _optional_refs(
    islands: dict[str, Any], island_id: str, context: EventsContext
) -> tuple[TijoriNamedRef, ...]:
    """Build one optional reference list, treating an absent island as empty."""
    if island_absent(islands, island_id):
        return ()
    return _named_refs(islands[island_id], context, island_id=island_id)


def build_site_timeline(document: str, context: EventsContext) -> TijoriSiteTimeline:
    """Build what the initial ``/in/timeline`` document actually publishes."""
    islands, markers = _verified_market_islands(
        document, surface=context.surface, optional_islands=_TIMELINE_OPTIONAL_ISLANDS
    )
    return TijoriSiteTimeline(
        surface=context.surface,
        metadata=_market_metadata(islands, markers, context),
        event_types=(
            ()
            if island_absent(islands, EVENT_TYPES_ISLAND_ID)
            else _event_types(
                islands[EVENT_TYPES_ISLAND_ID], context, label=f"island {EVENT_TYPES_ISLAND_ID}"
            )
        ),
        watchlists=_optional_refs(islands, WATCHLISTS_ISLAND_ID, context),
        portfolios=_optional_refs(islands, PORTFOLIOS_ISLAND_ID, context),
        sectors=_optional_refs(islands, SECTORS_ISLAND_ID, context),
        scalars=tuple(
            TijoriIslandScalar(
                island_id=island_id,
                cell=island_cell(
                    islands[island_id],
                    context,
                    island_id=island_id,
                    table_key=_ISLAND_SCALAR_TABLE_KEY,
                    row_label=island_id,
                    column_label=_ISLAND_VALUE_LABEL,
                ),
            )
            for island_id in TIMELINE_SCALAR_ISLAND_IDS
            if not island_absent(islands, island_id)
        ),
    )


def _capability_outcomes(built: TijoriEventsArtifactBase) -> tuple[TijoriCapabilityOutcome, ...]:
    """Report what this run got from each capability the surface offers.

    A count belongs to a capability, never to a page. The timeline page serves a
    filter taxonomy and withholds its event feed, so an artifact that reported
    only "timeline: 15" would invite reading fifteen filter types as fifteen
    market events. Each capability therefore carries its own state and only the
    acquired one carries a count.
    """
    return tuple(
        TijoriCapabilityOutcome(
            capability=declaration.capability,
            surface=declaration.surface,
            state=declaration.state,
            element_count=(
                built.element_count
                if declaration.state is TijoriEventsCapabilityState.ACQUIRED
                else None
            ),
            note=declaration.note,
        )
        for declaration in capabilities_of(built.surface)
    )


def _with_outcome(built: TijoriEventsArtifactBase) -> TijoriEventsArtifactBase:
    """Stamp the outcome and the per-capability report, from one place.

    Emptiness is decided by the element count AND by what the artifact had to
    quarantine. A zero count that its own quarantined rows explain is schema
    drift: the surface DID render rows and this adapter could not address them,
    so calling that "empty" would publish a parse failure as a fact about the
    market. Every other failure mode reached this point as an exception.
    """
    capabilities = _capability_outcomes(built)
    if built.element_count:
        return built.model_copy(
            update={
                "outcome": TijoriEventsOutcome.OK,
                "note": None,
                "capabilities": capabilities,
            }
        )
    quarantined = built.quarantined_rows
    if quarantined:
        raise TijoriEventsSchemaError(
            f"tijori events surface {built.surface.value!r} addressed none of the "
            f"{len(quarantined)} row(s) it rendered, so its zero count is drift rather than "
            f"an empty surface: {'; '.join(quarantined)}"
        )
    return built.model_copy(
        update={
            "outcome": TijoriEventsOutcome.OK_EMPTY,
            "note": EMPTY_LISTING_NOTE,
            "capabilities": capabilities,
        }
    )


def build_tijori_events(
    raw: bytes,
    *,
    surface: TijoriEventsSurface,
    source_url: str,
    content_sha256: str,
    retrieved_at: datetime,
    watchlist_slugs: Mapping[str, str] | None = None,
    slug: str | None = None,
    symbol: str | None = None,
    company_id: int | None = None,
) -> TijoriEventsArtifactBase:
    """Build one typed event artifact from one raw response body."""
    if surface in NOT_STATIC_SURFACES:
        raise TijoriEventsSurfaceError(
            f"tijori surface {surface.value!r} is not acquirable: {CONCALL_NOT_STATIC_REASON}"
        )
    document = decode_document(raw, page_label=SURFACE_PAGE_LABELS[surface])
    context = EventsContext(
        surface=surface,
        source_url=source_url,
        content_sha256=content_sha256,
        retrieved_at=retrieved_at,
        watchlist_slugs=dict(watchlist_slugs or {}),
    )
    built: TijoriEventsArtifactBase
    if surface is TijoriEventsSurface.UPCOMING:
        built = build_upcoming(document, context)
    elif surface is TijoriEventsSurface.QUARTERLY_RESULTS:
        built = build_quarterly_results(document, context)
    elif surface is TijoriEventsSurface.TIMELINE:
        built = build_site_timeline(document, context)
    else:
        if company_id is None or slug is None or symbol is None:
            raise TijoriEventsSurfaceError(COMPANY_TIMELINE_NEEDS_STOCK)
        built = build_company_timeline(
            document, context, slug=slug, symbol=symbol, company_id=company_id
        )
    stamped = _with_outcome(built)
    reject_duplicate_anchors(stamped)
    _LOGGER.info(
        "tijori_events_parsed",
        surface=surface.value,
        scope=stamped.metadata.scope.value,
        outcome=stamped.outcome.value,
        elements=stamped.element_count,
        auth_markers=list(stamped.metadata.auth_marker_islands),
    )
    return stamped
