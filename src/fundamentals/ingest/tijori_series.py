"""The shared Tijori ``[timestamp, value]`` point-series reader.

Tijori publishes the same series shape from two unrelated surfaces: the overview
page's price and market-share islands, and the ancillary ``company_op_metrics``
API. One reader serves both so a point read from a page and a point read from an
API cannot drift apart in how their timestamps or values are interpreted.

This module is deliberately surface-neutral: it knows nothing about islands,
APIs, sections, or their error types. The caller supplies the log event name and
the label to log under, so a drift warning still names the surface it came from,
and the caller decides what an unreadable container means for its own contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.tijori_tables import cell_reading, raw_json

_LOGGER = structlog.get_logger(__name__)

_MILLISECONDS_PER_SECOND = 1000
_POINT_LENGTH = 2


class TijoriSeriesPoint(BaseModel):
    """One ``[timestamp, value]`` point of any Tijori series.

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


def epoch_milliseconds(raw_value: Any) -> int | None:
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


def epoch_iso(milliseconds: int) -> datetime | None:
    """Derive a UTC instant from an epoch-millisecond source value."""
    try:
        return datetime.fromtimestamp(milliseconds / _MILLISECONDS_PER_SECOND, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def series_point(raw_point: Any) -> tuple[TijoriSeriesPoint, bool]:
    """Read one ``[timestamp, value]`` point, keeping a malformed one verbatim.

    The second element is True when the point's shape was not modeled. Such a
    point is retained with null readings rather than dropped, because a dropped
    point would silently shorten a history.
    """
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
    milliseconds = epoch_milliseconds(raw_timestamp)
    value, raw_value_text = cell_reading(raw_value)
    return (
        TijoriSeriesPoint(
            timestamp_ms=milliseconds,
            timestamp_raw_text=cell_reading(raw_timestamp)[1],
            timestamp_iso=None if milliseconds is None else epoch_iso(milliseconds),
            value=value,
            raw_value_text=raw_value_text,
        ),
        milliseconds is None,
    )


def read_series(
    raw_points: list[Any], *, label: str, drift_event: str, **log_context: Any
) -> tuple[tuple[TijoriSeriesPoint, ...], int]:
    """Read a whole point series, counting the points whose shape was not modeled.

    ``raw_points`` must already be a list: whether a non-list container is a
    section-level failure or a recorded absence is the caller's contract, not
    this reader's. ``drift_event`` and ``log_context`` let the calling surface
    name itself in the warning.
    """
    points: list[TijoriSeriesPoint] = []
    malformed = 0
    for raw_point in raw_points:
        point, is_malformed = series_point(raw_point)
        points.append(point)
        malformed += int(is_malformed)
    if malformed:
        _LOGGER.warning(drift_event, label=label, count=malformed, **log_context)
    return tuple(points), malformed
