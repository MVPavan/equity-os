"""Primitives every Tijori surface shares: value reading and page access state.

Two concerns live here because every Tijori adapter needs both and neither
depends on any one surface's shape:

* **value reading** — ``raw_json`` retains an unmodeled fragment verbatim,
  ``decimal_from_text`` and ``cell_reading`` implement the one numeric-lexeme
  rule the whole family reads through (a ``Decimal | None`` beside the preserved
  source text);
* **page access state** — the plan and capability islands Tijori renders beside
  its data. Access state is metadata carried beside a payload; it never decides
  whether data is parsed, and it is never interpreted as a table key.

Dependency flow is one-way: this module knows nothing about tables, overview
sections, shareholding, or the analysis APIs.
:mod:`fundamentals.ingest.tijori_tables` re-exports every public name here, so
importing either module reaches the same objects.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

_LOGGER = structlog.get_logger(__name__)

TIJORI_SOURCE_ID = "tijori"
FINANCIALS_LOCKS_ISLAND_ID = "financials_locks"
PLAN_DETAILS_ISLAND_ID = "plan_details"

_PLAN_NAME_FIELD = "name"
_PLAN_TIER_FIELD = "plan_tier"

_THOUSANDS_SEPARATOR = ","
_PLAIN_DECIMAL = re.compile(r"^[+-]?\d+(\.\d+)?$")
_NULL_CELL_TEXT = ""


class TijoriCapabilityFlag(BaseModel):
    """One boolean capability flag Tijori reports for a page feature."""

    model_config = ConfigDict(frozen=True)

    name: str
    enabled: bool


class TijoriFeatureLock(BaseModel):
    """Capability flags for one page feature (``rdcf``, ``qtly_results``, ...).

    Feature names are a UI capability namespace, not table keys. An unrecognized
    value shape is preserved verbatim in ``raw_value_json`` instead of failing.
    """

    model_config = ConfigDict(frozen=True)

    feature: str
    flags: tuple[TijoriCapabilityFlag, ...] = ()
    raw_value_json: str | None = None


class TijoriIslandStatus(StrEnum):
    """Acquisition state of one optional metadata island."""

    PRESENT = "present"
    ABSENT = "absent"
    UNPARSEABLE = "unparseable"


class TijoriUnparseableIsland(BaseModel):
    """An optional island that was on the page but could not be decoded."""

    model_config = ConfigDict(frozen=True)

    island_id: str
    error: str


class TijoriTableAccessMetadata(BaseModel):
    """Plan and capability state observed on the page; never gates parsing.

    Each optional island carries its own status so an absent island, an
    undecodable one, and a genuinely empty one never serialize alike. An island
    id is recorded only when that island was actually present.
    """

    model_config = ConfigDict(frozen=True)

    plan_name: str | None = None
    plan_tier: str | None = None
    feature_locks: tuple[TijoriFeatureLock, ...] = ()
    financials_locks_status: TijoriIslandStatus = TijoriIslandStatus.ABSENT
    plan_details_status: TijoriIslandStatus = TijoriIslandStatus.ABSENT
    financials_locks_error: str | None = None
    plan_details_error: str | None = None
    locks_island_id: str | None = None
    plan_island_id: str | None = None


def raw_json(value: Any) -> str:
    """Render an unmodeled JSON fragment as stable text for verbatim retention."""
    return json.dumps(value, sort_keys=True, default=str)


def decimal_from_text(text: str) -> Decimal | None:
    """Read a plain decimal lexeme, tolerating thousands commas only.

    ``"1,234"`` reads as ``Decimal("1234")``. Percent signs, currency symbols,
    placeholders such as ``"-"``, and every other decoration read as ``None``;
    the lexeme itself always survives beside the reading.
    """
    candidate = text.strip().replace(_THOUSANDS_SEPARATOR, "")
    if not _PLAIN_DECIMAL.match(candidate):
        return None
    try:
        parsed = Decimal(candidate)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def cell_reading(raw_value: Any) -> tuple[Decimal | None, str]:
    """Return one cell's numeric reading and its preserved source lexeme."""
    if raw_value is None:
        return None, _NULL_CELL_TEXT
    if isinstance(raw_value, bool):
        return None, raw_json(raw_value)
    if isinstance(raw_value, Decimal):
        return (raw_value if raw_value.is_finite() else None), str(raw_value)
    if isinstance(raw_value, int):
        return Decimal(raw_value), str(raw_value)
    if isinstance(raw_value, str):
        return decimal_from_text(raw_value), raw_value
    return None, raw_json(raw_value)


def label_number_pairs(parsed: Any) -> tuple[tuple[str, Decimal], ...] | str:
    """Read an already-decoded chart payload as ``[label, number]`` pairs.

    Returns the pairs, or a sentence naming why the payload is not that shape.
    Tijori publishes its pie/donut charts as such pair arrays in two different
    encodings — a JSON attribute on the overview page, a JavaScript array
    literal on the shareholding page — so the DECODING differs per surface while
    this shape gate is shared.

    The gate is whole-or-nothing on purpose. Each of these charts is a split of
    one total, so keeping the rows that happen to conform and discarding the
    rest would publish a breakdown that does not add up. Booleans are refused as
    numbers, matching the rest of this family's readers.
    """
    if not isinstance(parsed, list) or not parsed:
        return "it is not a non-empty list"
    pairs: list[tuple[str, Decimal]] = []
    for index, row in enumerate(parsed):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            return f"row {index} is not a 2-element pair"
        label, value = row
        if not isinstance(label, str) or not label.strip():
            return f"row {index} has no readable label"
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            return f"row {index} value is not a number"
        reading = value if isinstance(value, Decimal) else Decimal(str(value))
        if not reading.is_finite():
            return f"row {index} value is not finite"
        pairs.append((label, reading))
    return tuple(pairs)


def _feature_locks(value: Any) -> tuple[TijoriFeatureLock, ...]:
    """Model ``financials_locks`` as a feature-capability map, never as table keys."""
    if value is None:
        return ()
    if not isinstance(value, dict):
        _LOGGER.warning("tijori_financials_locks_unmodeled", raw=raw_json(value))
        return ()
    locks: list[TijoriFeatureLock] = []
    for feature, raw_flags in value.items():
        if not isinstance(feature, str):
            _LOGGER.warning("tijori_financials_locks_non_string_feature", raw=raw_json(feature))
            continue
        if isinstance(raw_flags, dict) and all(
            isinstance(flag, str) and isinstance(enabled, bool)
            for flag, enabled in raw_flags.items()
        ):
            locks.append(
                TijoriFeatureLock(
                    feature=feature,
                    flags=tuple(
                        TijoriCapabilityFlag(name=flag, enabled=enabled)
                        for flag, enabled in sorted(raw_flags.items())
                    ),
                )
            )
            continue
        _LOGGER.warning(
            "tijori_financials_locks_feature_unmodeled",
            feature=feature,
            raw=raw_json(raw_flags),
        )
        locks.append(TijoriFeatureLock(feature=feature, raw_value_json=raw_json(raw_flags)))
    return tuple(locks)


def _plan_string(plan: dict[str, Any], field: str) -> str | None:
    """Read one optional plan-details string without failing on drift."""
    raw = plan.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        _LOGGER.warning("tijori_plan_details_field_unmodeled", field=field, raw=raw_json(raw))
        return None
    return raw


def _island_state(island: Any) -> tuple[TijoriIslandStatus, str | None]:
    """Classify one optional island as present, absent, or undecodable."""
    if island is None:
        return TijoriIslandStatus.ABSENT, None
    if isinstance(island, TijoriUnparseableIsland):
        return TijoriIslandStatus.UNPARSEABLE, island.error
    return TijoriIslandStatus.PRESENT, None


def build_page_access(
    *, financials_locks: Any, plan_details: Any, locks_island_id: str = FINANCIALS_LOCKS_ISLAND_ID
) -> TijoriTableAccessMetadata:
    """Parse the plan and capability islands once per page, naming the locks island."""
    locks_status, locks_error = _island_state(financials_locks)
    plan_status, plan_error = _island_state(plan_details)
    if plan_status is TijoriIslandStatus.PRESENT and not isinstance(plan_details, dict):
        _LOGGER.warning("tijori_plan_details_unmodeled", raw=raw_json(plan_details))
        plan: dict[str, Any] = {}
    elif plan_status is TijoriIslandStatus.PRESENT:
        plan = plan_details
    else:
        plan = {}
    return TijoriTableAccessMetadata(
        plan_name=_plan_string(plan, _PLAN_NAME_FIELD),
        plan_tier=_plan_string(plan, _PLAN_TIER_FIELD),
        feature_locks=(
            _feature_locks(financials_locks) if locks_status is TijoriIslandStatus.PRESENT else ()
        ),
        financials_locks_status=locks_status,
        plan_details_status=plan_status,
        financials_locks_error=locks_error,
        plan_details_error=plan_error,
        locks_island_id=(locks_island_id if locks_status is TijoriIslandStatus.PRESENT else None),
        plan_island_id=(
            PLAN_DETAILS_ISLAND_ID if plan_status is TijoriIslandStatus.PRESENT else None
        ),
    )
