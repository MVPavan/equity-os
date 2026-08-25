"""Element-level helpers shared by the Tijori overview section builders.

This module exists to be imported by its siblings: the per-section builders in
:mod:`fundamentals.ingest.tijori_overview_sections` and the company-details
builder in :mod:`fundamentals.ingest.tijori_overview_company` both address,
anchor, and read raw island values the same way. Names here are public for that
reason — they are the overview family's internal API, not a page-level one.

Dependency flow is one-way: ``common`` knows nothing about the builders.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewMetadata,
    TijoriOverviewNumber,
    TijoriOverviewSchemaError,
    TijoriOverviewSection,
    TijoriSeriesPoint,
)
from fundamentals.ingest.tijori_tables import TIJORI_SOURCE_ID, cell_reading, raw_json

_LOGGER = structlog.get_logger(__name__)

PATH_SEPARATOR = "/"
SERIES_FIELD_LABEL = "series"

NAME_FIELD = "name"
DATA_FIELD = "data"
SLUG_FIELD = "slug"
SYMBOL_FIELD = "symbol"

_UTC_SUFFIX = "Z"
_UTC_OFFSET = "+00:00"
_MILLISECONDS_PER_SECOND = 1000
_POINT_LENGTH = 2


class SectionContext(BaseModel):
    """Invariant inputs shared by every element built for one section."""

    model_config = ConfigDict(frozen=True)

    section: TijoriOverviewSection
    island_id: str
    source_url: str
    content_sha256: str
    retrieved_at: datetime
    metadata: TijoriOverviewMetadata


def anchor(context: SectionContext, *, element_path: str, field_label: str) -> Provenance:
    """Anchor one overview element to the island and section it was read from."""
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=context.content_sha256,
        anchor_type=SourceAnchorType.JSON_ISLAND,
        context_ref=(
            f"{context.source_url}#{context.island_id}/{context.section.value}/"
            f"{element_path}/{field_label}"
        ),
        island_id=context.island_id,
        table_key=context.section.value,
        row_label=element_path,
        column_label=field_label,
        retrieved_at=context.retrieved_at,
        first_seen_at=context.retrieved_at,
    )


def number(
    raw_value: Any, context: SectionContext, *, element_path: str, field_label: str
) -> TijoriOverviewNumber:
    """Read one anchored numeric lexeme through the shared Tijori cell rule."""
    value, raw_text = cell_reading(raw_value)
    return TijoriOverviewNumber(
        value=value,
        raw_text=raw_text,
        provenance=anchor(context, element_path=element_path, field_label=field_label),
    )


def as_object(value: Any, label: str) -> dict[str, Any]:
    """Require an untrusted JSON object with a named failure reason."""
    if not isinstance(value, dict):
        raise TijoriOverviewSchemaError(f"tijori overview {label} must be an object")
    return value


def as_list(value: Any, label: str) -> list[Any]:
    """Require an untrusted JSON array with a named failure reason."""
    if not isinstance(value, list):
        raise TijoriOverviewSchemaError(f"tijori overview {label} must be a list")
    return value


def required_name(entry: dict[str, Any], label: str, field: str = NAME_FIELD) -> str:
    """Require the address of one element; an unaddressable element is fatal."""
    name = entry.get(field)
    if not isinstance(name, str) or not name.strip():
        raise TijoriOverviewSchemaError(
            f"tijori overview {label} {field} must be a non-empty string"
        )
    return name


def optional_string(entry: dict[str, Any], field: str) -> str | None:
    """Read one optional string field, treating any other shape as absent."""
    value = entry.get(field)
    return value if isinstance(value, str) else None


def optional_int(entry: dict[str, Any], field: str) -> int | None:
    """Read one optional integer field, rejecting booleans as integers."""
    value = entry.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def optional_bool(entry: dict[str, Any], field: str) -> bool | None:
    """Read one optional boolean field, treating any other shape as absent."""
    value = entry.get(field)
    return value if isinstance(value, bool) else None


def unmodeled(
    entry: dict[str, Any], known_fields: frozenset[str], *, context: SectionContext, element: str
) -> str | None:
    """Preserve and log every published key this contract does not model."""
    extra = {key: value for key, value in entry.items() if key not in known_fields}
    if not extra:
        return None
    _LOGGER.warning(
        "tijori_overview_field_drift",
        section=context.section.value,
        island=context.island_id,
        element=element,
        unmodeled_fields=sorted(str(key) for key in extra),
    )
    return raw_json(extra)


def invalid_known_values(
    entry: dict[str, Any],
    *,
    strings: tuple[str, ...] = (),
    integers: tuple[str, ...] = (),
    booleans: tuple[str, ...] = (),
    lists: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Collect modeled keys the island published with an unreadable shape.

    An absent key and a JSON-null key are NOT invalid — they are simply not
    published, and the optional readers are right to return ``None`` for them. A
    key that IS published but carries the wrong kind of value is invalid, because
    reading it as ``None`` would present a source claim as missing data.
    """
    invalid: dict[str, Any] = {}
    for field in strings:
        value = entry.get(field)
        if field in entry and value is not None and not isinstance(value, str):
            invalid[field] = value
    for field in integers:
        value = entry.get(field)
        if field in entry and value is not None and not _is_integer(value):
            invalid[field] = value
    for field in booleans:
        value = entry.get(field)
        if field in entry and value is not None and not isinstance(value, bool):
            invalid[field] = value
    for field in lists:
        value = entry.get(field)
        if field in entry and value is not None and not isinstance(value, list):
            invalid[field] = value
    return invalid


def _is_integer(value: Any) -> bool:
    """True when a raw JSON value reads as an integer (never a boolean)."""
    return isinstance(value, int) and not isinstance(value, bool)


def retained_invalid_json(
    invalid: dict[str, Any], *, context: SectionContext, element: str
) -> str | None:
    """Preserve and log every modeled value that could not be read as published."""
    if not invalid:
        return None
    _LOGGER.warning(
        "tijori_overview_field_unreadable",
        section=context.section.value,
        island=context.island_id,
        element=element,
        unreadable_fields=sorted(str(key) for key in invalid),
    )
    return raw_json(invalid)


def invalid_values_json(
    entry: dict[str, Any],
    *,
    context: SectionContext,
    element: str,
    strings: tuple[str, ...] = (),
    integers: tuple[str, ...] = (),
    booleans: tuple[str, ...] = (),
    lists: tuple[str, ...] = (),
) -> str | None:
    """Retain verbatim any modeled key of one element that was unreadable."""
    return retained_invalid_json(
        invalid_known_values(
            entry, strings=strings, integers=integers, booleans=booleans, lists=lists
        ),
        context=context,
        element=element,
    )


def _collect_anchors(value: Any, found: list[Provenance]) -> None:
    """Walk one built section, collecting every provenance it carries."""
    if isinstance(value, Provenance):
        found.append(value)
    elif isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            _collect_anchors(getattr(value, field_name), found)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _collect_anchors(item, found)


def reject_duplicate_anchors(section: BaseModel, context_label: str) -> None:
    """Fail loudly when two elements of one section share a complete anchor.

    Element paths are built per section, so this is a backstop rather than the
    primary defence: it makes any future addressing change that collapses two
    distinct elements onto one anchor fatal instead of silent, the same way
    duplicate row keys are fatal in the financial tables.
    """
    anchors: list[Provenance] = []
    _collect_anchors(section, anchors)
    collisions = sorted(
        f"{row_label}/{column_label}"
        for (row_label, column_label), count in Counter(
            (found.row_label, found.column_label) for found in anchors
        ).items()
        if count > 1
    )
    if collisions:
        raise TijoriOverviewSchemaError(
            f"tijori overview section {context_label!r} anchors two elements identically: "
            f"{', '.join(collisions)}"
        )


def reject_duplicates(paths: tuple[str, ...], context: SectionContext) -> None:
    """Fail loudly when two elements of one section would share an address."""
    collisions = sorted(path for path, count in Counter(paths).items() if count > 1)
    if collisions:
        raise TijoriOverviewSchemaError(
            f"tijori overview section {context.section.value!r} has duplicate element paths: "
            f"{', '.join(collisions)}"
        )


def iso_date(text: str) -> date | None:
    """Derive a calendar date from one of Tijori's ISO date lexemes."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def iso_datetime(text: str) -> datetime | None:
    """Derive an instant from one of Tijori's ISO timestamp lexemes."""
    candidate = text.strip()
    if candidate.endswith(_UTC_SUFFIX):
        candidate = f"{candidate[:-1]}{_UTC_OFFSET}"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _epoch_iso(milliseconds: int) -> datetime | None:
    """Derive a UTC instant from an epoch-millisecond source value."""
    try:
        return datetime.fromtimestamp(milliseconds / _MILLISECONDS_PER_SECOND, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _epoch_milliseconds(raw_value: Any) -> int | None:
    """Read an epoch-millisecond stamp published as an integer or a whole float."""
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value
    if (
        isinstance(raw_value, Decimal)
        and raw_value.is_finite()
        and raw_value == raw_value.to_integral_value()
    ):
        return int(raw_value)
    return None


def _series_point(raw_point: Any) -> tuple[TijoriSeriesPoint, bool]:
    """Read one ``[timestamp, value]`` point, keeping a malformed one verbatim."""
    if not isinstance(raw_point, list) or len(raw_point) != _POINT_LENGTH:
        return (
            TijoriSeriesPoint(
                timestamp_ms=None,
                timestamp_raw_text=raw_json(raw_point),
                timestamp_iso=None,
                value=None,
                raw_value_text=raw_json(raw_point),
            ),
            True,
        )
    raw_timestamp, raw_value = raw_point
    milliseconds = _epoch_milliseconds(raw_timestamp)
    value, raw_value_text = cell_reading(raw_value)
    return (
        TijoriSeriesPoint(
            timestamp_ms=milliseconds,
            timestamp_raw_text=cell_reading(raw_timestamp)[1],
            timestamp_iso=None if milliseconds is None else _epoch_iso(milliseconds),
            value=value,
            raw_value_text=raw_value_text,
        ),
        milliseconds is None,
    )


def series(raw_points: Any, *, label: str) -> tuple[tuple[TijoriSeriesPoint, ...], int]:
    """Read a whole point series, counting the points whose shape was not modeled."""
    points: list[TijoriSeriesPoint] = []
    malformed = 0
    for raw_point in as_list(raw_points, label):
        point, is_malformed = _series_point(raw_point)
        points.append(point)
        malformed += int(is_malformed)
    if malformed:
        _LOGGER.warning("tijori_overview_series_points_unmodeled", label=label, count=malformed)
    return tuple(points), malformed
