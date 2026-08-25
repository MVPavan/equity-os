"""Element-level helpers shared by the Tijori event-surface builders.

This module exists to be imported by :mod:`fundamentals.ingest.tijori_events`,
whose four builders address, anchor, and read raw values the same way. Names here
are public for that reason — they are this family's internal API, not a
page-level one. Dependency flow is one-way: ``common`` knows nothing about the
builders or the gates.

ANCHOR CONVENTION for this family, stated once because these surfaces mix both
retrieval procedures inside a single document:

* :func:`anchor_table` issues ``HTML_TABLE`` for every value read out of rendered
  markup. Its ``table_id`` names the surface and the table within it, its
  ``row_path`` is position-led (``index/label``) so two rows sharing a display
  name stay distinct, and ``column_index`` carries the rendered position beside
  the column's label.
* :func:`anchor_island` issues ``JSON_ISLAND`` for every value read out of a
  ``json_script`` island.
* ``API_DOCUMENT`` is deliberately NOT used here, including for the company
  timeline. That fragment is retrieved by a documented GET, which is API-like,
  but its values are table cells and island payloads: addressing them below a
  ``document_id`` would assert a JSON-document retrieval procedure that does not
  apply to them. The fragment's URL is recorded in ``metadata.source_url`` and in
  every anchor's ``context_ref``, so the request that produced a value stays
  recoverable without lying about how it is re-found.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_events_html import RawCompanyLink
from fundamentals.ingest.tijori_events_models import (
    TijoriCompanyRef,
    TijoriEventsArtifactBase,
    TijoriEventsCell,
    TijoriEventsSchemaError,
    TijoriEventsSurface,
)
from fundamentals.ingest.tijori_tables import (
    TIJORI_SOURCE_ID,
    TijoriUnparseableIsland,
    cell_reading,
    raw_json,
)

_LOGGER = structlog.get_logger(__name__)

PATH_SEPARATOR = "/"
COLUMN_ANCHOR_SEGMENT = "col"


class EventsContext(BaseModel):
    """Invariant inputs shared by every element built from one event response."""

    model_config = ConfigDict(frozen=True)

    surface: TijoriEventsSurface
    source_url: str
    content_sha256: str
    retrieved_at: datetime
    watchlist_slugs: Mapping[str, str]


def anchor_table(
    context: EventsContext, *, table_id: str, row_path: str, column_index: int, column_label: str
) -> Provenance:
    """Anchor one rendered cell to its table, its row, and its rendered column."""
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=context.content_sha256,
        anchor_type=SourceAnchorType.HTML_TABLE,
        context_ref=f"{context.source_url}#{table_id}/{row_path}/{column_index}/{column_label}",
        table_id=table_id,
        row_path=row_path,
        column_index=column_index,
        column_label=column_label,
        retrieved_at=context.retrieved_at,
        first_seen_at=context.retrieved_at,
    )


def anchor_island(
    context: EventsContext, *, island_id: str, table_key: str, row_label: str, column_label: str
) -> Provenance:
    """Anchor one island value to the named island it was read from."""
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=context.content_sha256,
        anchor_type=SourceAnchorType.JSON_ISLAND,
        context_ref=f"{context.source_url}#{island_id}/{table_key}/{row_label}/{column_label}",
        island_id=island_id,
        table_key=table_key,
        row_label=row_label,
        column_label=column_label,
        retrieved_at=context.retrieved_at,
        first_seen_at=context.retrieved_at,
    )


def table_cell(
    raw_text: str,
    context: EventsContext,
    *,
    table_id: str,
    row_path: str,
    column_index: int,
    column_label: str,
) -> TijoriEventsCell:
    """Read one rendered lexeme through the shared Tijori cell rule."""
    value, text = cell_reading(raw_text)
    return TijoriEventsCell(
        value=value,
        raw_text=text,
        provenance=anchor_table(
            context,
            table_id=table_id,
            row_path=row_path,
            column_index=column_index,
            column_label=column_label,
        ),
    )


def island_cell(
    raw_value: Any,
    context: EventsContext,
    *,
    island_id: str,
    table_key: str,
    row_label: str,
    column_label: str,
) -> TijoriEventsCell:
    """Read one island lexeme through the shared Tijori cell rule."""
    value, text = cell_reading(raw_value)
    return TijoriEventsCell(
        value=value,
        raw_text=text,
        provenance=anchor_island(
            context,
            island_id=island_id,
            table_key=table_key,
            row_label=row_label,
            column_label=column_label,
        ),
    )


def column_label(labels: tuple[str, ...], index: int) -> str:
    """Name one rendered column, falling back to its position when unlabelled."""
    if index < len(labels) and labels[index].strip():
        return labels[index]
    return f"{COLUMN_ANCHOR_SEGMENT}{index}"


def company_ref(link: RawCompanyLink, context: EventsContext) -> TijoriCompanyRef:
    """Cross-link one listed company to the watchlist by slug, recording the miss.

    A market-wide listing names companies this repo does not track. That is
    ordinary market data, so a slug with no watchlist entry is recorded as a
    non-match and never raised.
    """
    matched = None if link.slug is None else context.watchlist_slugs.get(link.slug)
    if link.slug is not None and matched is None:
        _LOGGER.debug(
            "tijori_events_company_off_watchlist",
            surface=context.surface.value,
            slug=link.slug,
        )
    return TijoriCompanyRef(
        name=link.name,
        href=link.href,
        slug=link.slug,
        symbol_text=link.symbol_text,
        watchlist_symbol=matched,
        on_watchlist=matched is not None,
    )


def as_list(value: Any, label: str) -> list[Any]:
    """Require an untrusted JSON array with a named failure reason."""
    if not isinstance(value, list):
        raise TijoriEventsSchemaError(f"tijori events {label} must be a list")
    return value


def as_object(value: Any, label: str) -> dict[str, Any]:
    """Require an untrusted JSON object with a named failure reason."""
    if not isinstance(value, dict):
        raise TijoriEventsSchemaError(f"tijori events {label} must be an object")
    return value


def optional_bool(entry: dict[str, Any], field: str) -> bool | None:
    """Read one optional boolean field, treating any other shape as absent."""
    value = entry.get(field)
    return value if isinstance(value, bool) else None


def unmodeled(
    entry: dict[str, Any], known_fields: frozenset[str], *, context: EventsContext, element: str
) -> str | None:
    """Preserve and log every published key this contract does not model."""
    extra = {key: value for key, value in entry.items() if key not in known_fields}
    if not extra:
        return None
    _LOGGER.warning(
        "tijori_events_field_drift",
        surface=context.surface.value,
        element=element,
        unmodeled_fields=sorted(str(key) for key in extra),
    )
    return raw_json(extra)


def invalid_values_json(
    entry: dict[str, Any],
    *,
    context: EventsContext,
    element: str,
    strings: tuple[str, ...] = (),
    booleans: tuple[str, ...] = (),
) -> str | None:
    """Retain verbatim any modeled key of one element published unreadably.

    An absent or JSON-null key is not invalid — it was simply not published. A
    key that IS published with the wrong kind of value is, because reading it as
    ``None`` would present a source claim as missing data.
    """
    invalid: dict[str, Any] = {}
    for field in strings:
        value = entry.get(field)
        if field in entry and value is not None and not isinstance(value, str):
            invalid[field] = value
    for field in booleans:
        value = entry.get(field)
        if field in entry and value is not None and not isinstance(value, bool):
            invalid[field] = value
    if not invalid:
        return None
    _LOGGER.warning(
        "tijori_events_field_unreadable",
        surface=context.surface.value,
        element=element,
        unreadable_fields=sorted(str(key) for key in invalid),
    )
    return raw_json(invalid)


def island_absent(islands: dict[str, Any], island_id: str) -> bool:
    """True when an optional island was missing, null, or unparseable."""
    if island_id not in islands:
        return True
    island = islands[island_id]
    if isinstance(island, TijoriUnparseableIsland):
        _LOGGER.warning("tijori_events_island_unparseable", island=island_id, error=island.error)
        return True
    return island is None


def _collect_anchors(value: Any, found: list[Provenance]) -> None:
    """Walk one built artifact, collecting every provenance it carries."""
    if isinstance(value, Provenance):
        found.append(value)
    elif isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            _collect_anchors(getattr(value, field_name), found)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _collect_anchors(item, found)


def reject_duplicate_anchors(built: TijoriEventsArtifactBase) -> None:
    """Fail loudly when two elements of one artifact share a complete anchor.

    One artifact here spans many tables and several islands, and the two anchor
    kinds address values with different fields, so the comparison is the whole
    addressing tuple. Comparing less would report a row label repeated across two
    result items as a collision; comparing within one table would miss a future
    addressing change that collapses two tables onto one id.
    """
    anchors: list[Provenance] = []
    _collect_anchors(built, anchors)
    collisions = sorted(
        str(address)
        for address, count in Counter(
            (
                found.anchor_type,
                found.island_id,
                found.table_key,
                found.table_id,
                found.row_path,
                found.row_label,
                found.column_label,
                found.column_index,
            )
            for found in anchors
        ).items()
        if count > 1
    )
    if collisions:
        raise TijoriEventsSchemaError(
            f"tijori events surface {built.surface.value!r} anchors two elements identically: "
            f"{', '.join(collisions)}"
        )
