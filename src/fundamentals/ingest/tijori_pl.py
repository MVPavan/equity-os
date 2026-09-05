"""Derived quarterly P&L selection from Tijori's verified financials islands.

This module owns everything specific to the derived-P&L cross-check surface:
the concept mapping, the fiscal-quarter column selection, and the mapping of a
selected row onto an :class:`Observation`. Transport, the page-level
authentication and identity gates, and the per-surface entry points stay in
:mod:`fundamentals.ingest.tijori_source`, which imports this module.

Dependency flow is one-way: this module knows nothing about the fetcher.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_page import as_object
from fundamentals.ingest.tijori_tables import (
    FINANCIALS_ISLAND_ID,
    TIJORI_SOURCE_ID,
    TijoriParseError,
)

_LOGGER = structlog.get_logger(__name__)

ENTITY_SCHEME = "tijori-slug"
SCOPE_ASSUMED_NOTE = "scope_assumed=True; Tijori does not disclose statement scope"

_CURRENCY_INR = "INR"
_INR_CRORE_UNIT = "INR crore"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7
_QUARTERLY_CONSOLIDATED_TABLE = "qt_c"
_MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_QUARTER_BOUNDS: dict[int, tuple[int, int]] = {
    3: (1, 31),
    6: (4, 30),
    9: (7, 30),
    12: (10, 31),
}


class TijoriConcept(StrEnum):
    """The derived P&L concepts supported by the verified Tijori DOM."""

    SALES = "tijori:sales"
    PBT = "tijori:pbt"
    NET_PROFIT = "tijori:net_profit"


_ROW_TO_CONCEPT: dict[str, TijoriConcept] = {
    "Net Sales": TijoriConcept.SALES,
    "Profit Before Tax": TijoriConcept.PBT,
    "Net Profit": TijoriConcept.NET_PROFIT,
}


class TijoriRow(BaseModel):
    """One selected P&L value in the requested quarterly consolidated table."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: Decimal | int


class TijoriPlPayload(BaseModel):
    """Validated selected quarterly P&L data from the JSON islands."""

    model_config = ConfigDict(frozen=True)

    slug: str
    company_id: int
    symbol: str
    url: str
    period_label: str
    period_start: date
    period_end: date
    rows: tuple[TijoriRow, ...]


def is_tijori_derived(observation: Observation) -> bool:
    """True when the observation is a Tijori-derived cross-check value."""
    return (
        observation.provenance.source_id == TIJORI_SOURCE_ID
        and observation.accounting_basis is AccountingFramework.UNKNOWN
    )


def _expected_label(period_end: date) -> str:
    """Return the verified ``Mon YYYY`` DOM label for a configured quarter end."""
    quarter = _QUARTER_BOUNDS.get(period_end.month)
    if quarter is None or period_end.day != quarter[1]:
        raise TijoriParseError(f"configured period end is not a fiscal quarter end: {period_end}")
    return f"{_MONTH_LABELS[period_end.month - 1]} {period_end.year}"


def _quarter_start(period_end: date) -> date:
    """Return the start date of the configured Indian fiscal quarter."""
    start_month, _ = _QUARTER_BOUNDS[period_end.month]
    start_year = period_end.year if start_month <= period_end.month else period_end.year - 1
    return date(start_year, start_month, 1)


def _as_string_list(value: Any, label: str) -> tuple[str, ...]:
    """Require non-empty source labels without normalizing their exact text."""
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TijoriParseError(f"tijori {label} must be a list of non-empty strings")
    return tuple(value)


def _selected_rows(
    table: dict[str, Any], report_dates: tuple[str, ...], column: int
) -> tuple[TijoriRow, ...]:
    """Select and validate the three required P&L rows at one exact column."""
    raw_rows = table.get("data")
    if not isinstance(raw_rows, list):
        raise TijoriParseError("tijori qt_c.data must be a list")
    selected: dict[str, TijoriRow] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise TijoriParseError("tijori qt_c.data contains a non-object row")
        label = raw_row.get("name")
        if not isinstance(label, str):
            raise TijoriParseError("tijori qt_c.data row name must be a string")
        if label not in _ROW_TO_CONCEPT:
            continue
        if label in selected:
            raise TijoriParseError(f"tijori qt_c.data contains duplicate row {label!r}")
        values = raw_row.get("value")
        if not isinstance(values, list) or len(values) != len(report_dates):
            raise TijoriParseError(
                f"tijori row {label!r} has invalid values for {len(report_dates)} columns"
            )
        raw_value = values[column]
        if (
            isinstance(raw_value, bool)
            or not isinstance(raw_value, (Decimal, int))
            or isinstance(raw_value, Decimal)
            and not raw_value.is_finite()
        ):
            raise TijoriParseError(
                f"tijori row {label!r} has a non-numeric value for the requested quarter"
            )
        selected[label] = TijoriRow(label=label, value=raw_value)
    missing = tuple(label for label in _ROW_TO_CONCEPT if label not in selected)
    if missing:
        raise TijoriParseError(f"tijori qt_c.data is missing required rows: {', '.join(missing)}")
    return tuple(selected[label] for label in _ROW_TO_CONCEPT)


def build_pl_payload(
    islands: dict[str, Any],
    *,
    slug: str,
    company_id: int,
    symbol: str,
    period_end: date,
    source_url: str,
) -> TijoriPlPayload:
    """Select the configured fiscal quarter out of the verified financials island."""
    financials = as_object(islands[FINANCIALS_ISLAND_ID], FINANCIALS_ISLAND_ID)
    table = as_object(financials.get(_QUARTERLY_CONSOLIDATED_TABLE), _QUARTERLY_CONSOLIDATED_TABLE)
    report_dates = _as_string_list(table.get("report_dates"), "qt_c.report_dates")
    expected_label = _expected_label(period_end)
    matching_columns = tuple(
        index for index, label in enumerate(report_dates) if label == expected_label
    )
    if not matching_columns:
        available = ", ".join(report_dates)
        raise TijoriParseError(
            f"tijori requested quarter {expected_label!r} is absent; available labels: {available}"
        )
    if len(matching_columns) > 1:
        available = ", ".join(report_dates)
        raise TijoriParseError(
            f"tijori requested quarter {expected_label!r} is ambiguous; "
            f"available labels: {available}"
        )
    return TijoriPlPayload(
        slug=slug,
        company_id=company_id,
        symbol=symbol,
        url=source_url,
        period_label=expected_label,
        period_start=_quarter_start(period_end),
        period_end=period_end,
        rows=_selected_rows(table, report_dates, matching_columns[0]),
    )


def _to_observation(
    *,
    payload: TijoriPlPayload,
    concept: TijoriConcept,
    row_label: str,
    raw_value: Decimal | int,
    content_sha256: str,
    retrieved_at: datetime,
) -> Observation:
    """Build one derived observation from a verified JSON numeric value."""
    # Tijori's only EPS is adjusted EPS (adj_eps_abs), so it is deliberately unmapped.
    normalized_value = raw_value if isinstance(raw_value, Decimal) else Decimal(raw_value)
    context_ref = (
        f"{payload.url}#{FINANCIALS_ISLAND_ID}/{_QUARTERLY_CONSOLIDATED_TABLE}/"
        f"{payload.period_label}/{concept.value}"
    )
    provenance = Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=content_sha256,
        anchor_type=SourceAnchorType.JSON_ISLAND,
        context_ref=context_ref,
        island_id=FINANCIALS_ISLAND_ID,
        table_key=_QUARTERLY_CONSOLIDATED_TABLE,
        row_label=row_label,
        column_label=payload.period_label,
        retrieved_at=retrieved_at,
        first_seen_at=retrieved_at,
    )
    return Observation(
        concept_qname=concept.value,
        raw_value=str(raw_value),
        normalized_value=normalized_value,
        normalized_unit=_INR_CRORE_UNIT,
        context_ref=context_ref,
        entity_scheme=ENTITY_SCHEME,
        entity_id=payload.slug,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.UNKNOWN,
        period_type=PeriodType.DURATION,
        period_start=payload.period_start,
        period_end=payload.period_end,
        currency=_CURRENCY_INR,
        scale=_CRORE_SCALE,
        decimals=_CRORE_DECIMALS,
        provenance=provenance,
    )


def pl_observations(
    payload: TijoriPlPayload, *, content_sha256: str, retrieved_at: datetime | None = None
) -> tuple[Observation, ...]:
    """Map the selected consolidated P&L rows to derived observations.

    ``retrieved_at`` is the instant the bytes were acquired; a replay passes the
    retained capture's own instant so re-deriving evidence cannot restamp it.
    """
    stamped_at = retrieved_at if retrieved_at is not None else datetime.now(tz=UTC)
    observations = tuple(
        _to_observation(
            payload=payload,
            concept=_ROW_TO_CONCEPT[row.label],
            row_label=row.label,
            raw_value=row.value,
            content_sha256=content_sha256,
            retrieved_at=stamped_at,
        )
        for row in payload.rows
    )
    _LOGGER.info(
        "tijori_quarterly_observations_parsed",
        count=len(observations),
        slug=payload.slug,
    )
    return observations
