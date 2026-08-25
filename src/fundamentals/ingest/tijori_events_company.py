"""Builder for Tijori's per-company timeline fragment.

Split from :mod:`fundamentals.ingest.tijori_events` because this one surface
carries concerns none of the market-wide surfaces have: a per-row identity gate,
a structural authentication gate with no islands to lean on, and verbatim
retention of the third-party payloads its events embed.

IDENTITY FACT (owner capture, TITAN / company_id 81, 2026-08-25): the fragment
publishes no identity island, but its ROWS do carry identity markers — each row
links its company as ``/company/<slug>`` and each content cell carries a
``company-id`` attribute. Those markers are checked against the configured
watchlist identifiers row by row. A row that disagrees is quarantined rather than
counted, and a fragment in which rows disagree and NONE agree is the wrong
company's page, which is a refusal. The artifact still records
``CONFIGURED_URL_ONLY``: agreeing rows corroborate the request, they do not
constitute an independent assertion of identity by the document.
"""

from __future__ import annotations

import json

import structlog

from fundamentals.ingest.tijori_events_common import (
    PATH_SEPARATOR,
    EventsContext,
    anchor_island,
    column_label,
    company_ref,
    table_cell,
)
from fundamentals.ingest.tijori_events_html import RawTimelineEvent, collect_company_timeline
from fundamentals.ingest.tijori_events_models import (
    FRAGMENT_AUTH_BASIS,
    FRAGMENT_IDENTITY_BASIS,
    FRAGMENT_NO_EVENT_ROWS,
    TijoriCompanyTimeline,
    TijoriEventDetailRow,
    TijoriEventDetailTable,
    TijoriEventsAuthError,
    TijoriEventsCell,
    TijoriEventsIdentityError,
    TijoriEventsIdentityStrength,
    TijoriEventsMetadata,
    TijoriEventsSchemaError,
    TijoriEventsScope,
    TijoriRetainedIsland,
    TijoriTimelineEvent,
)
from fundamentals.ingest.tijori_page import JsonScriptCollector

_LOGGER = structlog.get_logger(__name__)

_TABLE_ID = "html:company-timeline"
_EVENT_ROW_PATH = "event"
_EVENT_PAYLOAD_ROW_LABEL = "payload"
_EVENT_PAYLOAD_LABEL = "json"

_COMPANY_LABEL = "company"
_EVENT_LABEL = "event"
_DATE_LABEL = "date"
_CONTENT_LABEL = "content"
_LINK_LABEL = "link"

# Rendered position of each primary fact within one event row. Links follow the
# fixed fields, so a row with three links addresses them at 4, 5, and 6.
_COMPANY_COLUMN = 0
_EVENT_COLUMN = 1
_DATE_COLUMN = 2
_CONTENT_COLUMN = 3
_FIRST_LINK_COLUMN = 4


def _row_identity_failure(raw_event: RawTimelineEvent, *, slug: str, company_id: int) -> str | None:
    """Name the identity marker on one row that disagrees with the request.

    A row publishing neither marker is not a mismatch — it is a row Tijori
    rendered without them, and it passes through recorded. Only a marker that IS
    published and DISAGREES condemns the row.
    """
    if raw_event.company.slug is not None and raw_event.company.slug != slug:
        return f"slug {raw_event.company.slug!r} != requested {slug!r}"
    declared = (raw_event.event_company_id_text or "").strip()
    if declared and declared != str(company_id):
        return f"company-id {declared!r} != requested {company_id}"
    return None


def _row_identity_matched(raw_event: RawTimelineEvent, *, slug: str, company_id: int) -> bool:
    """True when a row published an identity marker that agrees with the request."""
    if raw_event.company.slug == slug:
        return True
    return (raw_event.event_company_id_text or "").strip() == str(company_id)


def _detail_tables(
    raw_event: RawTimelineEvent, context: EventsContext
) -> tuple[TijoriEventDetailTable, ...]:
    """Build every detail table one timeline event rendered.

    No label column is assumed: a ``dict-table`` renders its title as a
    row-spanning cell of the header row, so its value row carries no title at
    all. Every rendered cell is kept as a cell and the row's first lexeme leads
    its address.
    """
    tables: list[TijoriEventDetailTable] = []
    for table_index, raw_table in enumerate(raw_event.detail_tables):
        table_id = (
            f"{_TABLE_ID}{PATH_SEPARATOR}{raw_event.row_id}{PATH_SEPARATOR}table:{table_index}"
        )
        rows: list[TijoriEventDetailRow] = []
        for row_index, values in enumerate(raw_table.row_values):
            label = values[0] if values else ""
            row_path = f"{row_index}{PATH_SEPARATOR}{label}"
            rows.append(
                TijoriEventDetailRow(
                    position=row_index,
                    label=label,
                    cells=tuple(
                        table_cell(
                            text,
                            context,
                            table_id=table_id,
                            row_path=row_path,
                            column_index=column_index,
                            column_label=column_label(raw_table.column_labels, column_index),
                        )
                        for column_index, text in enumerate(values)
                    ),
                )
            )
        tables.append(
            TijoriEventDetailTable(
                position=table_index,
                table_class=raw_table.table_class,
                column_labels=raw_table.column_labels,
                rows=tuple(rows),
            )
        )
    return tuple(tables)


def _event_islands(
    raw_event: RawTimelineEvent, bodies: dict[str, str], context: EventsContext
) -> tuple[TijoriRetainedIsland, ...]:
    """Retain each island one timeline event embeds, byte-for-byte and anchored.

    The rendered body is kept exactly as published. Decoding and re-serializing
    would silently rewrite the source: ``1.25`` would return as a float, key
    order would change, and a body that is not valid JSON would have nothing left
    to retain at all. The parse here is only a CHECK — its failure is recorded
    beside the bytes, never in place of them.
    """
    retained: list[TijoriRetainedIsland] = []
    for island_id in raw_event.island_ids:
        body = bodies.get(island_id)
        if body is None:
            continue
        decode_error: str | None = None
        try:
            json.loads(body)
        except json.JSONDecodeError as error:
            decode_error = str(error)
            _LOGGER.warning(
                "tijori_events_island_unparseable", island=island_id, error=decode_error
            )
        retained.append(
            TijoriRetainedIsland(
                island_id=island_id,
                payload_json=body,
                decode_error=decode_error,
                provenance=anchor_island(
                    context,
                    island_id=island_id,
                    table_key=f"event:{raw_event.row_id}",
                    row_label=_EVENT_PAYLOAD_ROW_LABEL,
                    column_label=_EVENT_PAYLOAD_LABEL,
                ),
            )
        )
    return tuple(retained)


def _island_bodies(document: str, island_ids: tuple[str, ...]) -> dict[str, str]:
    """Collect the exact rendered body of each named island.

    The committed island collector is used rather than the decoding loader
    because what this surface retains is the source text, not a reading of it.
    A repeated id whose bodies disagree is unresolvable ambiguity, exactly as it
    is for the page families, and is refused rather than resolved by position.
    """
    if not island_ids:
        return {}
    collector = JsonScriptCollector(island_ids)
    collector.feed(document)
    collector.close()
    if collector.divergent_duplicates:
        raise TijoriEventsSchemaError(
            "tijori company-timeline renders these event islands more than once with "
            f"differing bodies: {', '.join(sorted(collector.divergent_duplicates))}"
        )
    return dict(collector.islands)


def _event_cell(
    text: str, context: EventsContext, *, row_id: str, column_index: int, label: str
) -> TijoriEventsCell:
    """Anchor one primary fact of an event row to that row and its field."""
    return table_cell(
        text,
        context,
        table_id=f"{_TABLE_ID}{PATH_SEPARATOR}{row_id}",
        row_path=_EVENT_ROW_PATH,
        column_index=column_index,
        column_label=label,
    )


def _build_event(
    raw_event: RawTimelineEvent, context: EventsContext, *, position: int, bodies: dict[str, str]
) -> TijoriTimelineEvent:
    """Build one timeline event with every primary fact anchored."""
    row_id = raw_event.row_id
    return TijoriTimelineEvent(
        position=position,
        row_id=row_id,
        group_id=raw_event.group_id,
        is_grouped_child=raw_event.is_grouped_child,
        company=company_ref(raw_event.company, context),
        company_cell=_event_cell(
            raw_event.company.name,
            context,
            row_id=row_id,
            column_index=_COMPANY_COLUMN,
            label=_COMPANY_LABEL,
        ),
        event_name=raw_event.event_name,
        event_cell=_event_cell(
            raw_event.event_name,
            context,
            row_id=row_id,
            column_index=_EVENT_COLUMN,
            label=_EVENT_LABEL,
        ),
        event_company_id_text=raw_event.event_company_id_text,
        announced=(
            None
            if raw_event.announced_text is None
            else _event_cell(
                raw_event.announced_text,
                context,
                row_id=row_id,
                column_index=_DATE_COLUMN,
                label=_DATE_LABEL,
            )
        ),
        detail_tables=_detail_tables(raw_event, context),
        islands=_event_islands(raw_event, bodies, context),
        link_cells=tuple(
            _event_cell(
                href,
                context,
                row_id=row_id,
                column_index=_FIRST_LINK_COLUMN + index,
                label=_LINK_LABEL,
            )
            for index, href in enumerate(raw_event.links)
        ),
        content_cell=_event_cell(
            raw_event.content_text,
            context,
            row_id=row_id,
            column_index=_CONTENT_COLUMN,
            label=_CONTENT_LABEL,
        ),
    )


def build_company_timeline(
    document: str, context: EventsContext, *, slug: str, symbol: str, company_id: int
) -> TijoriCompanyTimeline:
    """Build the per-company timeline fragment's events for the requested issuer."""
    fragment = collect_company_timeline(document)
    if fragment.page_shell:
        raise TijoriEventsAuthError(
            "tijori company-timeline response is a whole HTML document, not the bare "
            "fragment this endpoint returns to a subscribed session"
        )
    if fragment.row_count == 0:
        raise TijoriEventsSchemaError(FRAGMENT_NO_EVENT_ROWS)

    kept: list[RawTimelineEvent] = []
    mismatched: list[str] = []
    matched = 0
    for raw_event in fragment.events:
        failure = _row_identity_failure(raw_event, slug=slug, company_id=company_id)
        if failure is not None:
            _LOGGER.warning(
                "tijori_events_row_identity_mismatch",
                row_id=raw_event.row_id,
                detail=failure,
                requested_symbol=symbol,
            )
            mismatched.append(f"{raw_event.row_id!r} ({failure})")
            continue
        matched += int(_row_identity_matched(raw_event, slug=slug, company_id=company_id))
        kept.append(raw_event)
    if mismatched and matched == 0:
        raise TijoriEventsIdentityError(
            f"tijori company-timeline for {symbol} (company_id {company_id}) carries no row "
            f"matching the requested company and {len(mismatched)} row(s) that name another: "
            f"{', '.join(mismatched)}"
        )

    bodies = _island_bodies(
        document,
        tuple(island_id for raw_event in kept for island_id in raw_event.island_ids),
    )
    return TijoriCompanyTimeline(
        surface=context.surface,
        metadata=TijoriEventsMetadata(
            surface=context.surface,
            scope=TijoriEventsScope.COMPANY,
            source_url=context.source_url,
            file_sha256=context.content_sha256,
            retrieved_at=context.retrieved_at,
            identity_basis=FRAGMENT_IDENTITY_BASIS,
            identity_strength=TijoriEventsIdentityStrength.CONFIGURED_URL_ONLY,
            auth_basis=FRAGMENT_AUTH_BASIS,
            slug=slug,
            symbol=symbol,
            company_id=company_id,
        ),
        events=tuple(
            _build_event(raw_event, context, position=index, bodies=bodies)
            for index, raw_event in enumerate(kept)
        ),
        malformed_rows=fragment.malformed_rows,
        identity_mismatch_rows=tuple(mismatched),
    )
