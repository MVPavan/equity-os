"""Builders for the modeled data sections of Tijori's overview page.

Each builder turns one raw JSON island into its typed section contract from
:mod:`fundamentals.ingest.tijori_overview_models`, using the shared element
helpers in :mod:`fundamentals.ingest.tijori_overview_common`. The page-level
concerns — island collection, the identity gate, absence semantics, and metadata
— live in :mod:`fundamentals.ingest.tijori_overview`, which owns the
orchestration; the company-details header and its forensic checklist live in
:mod:`fundamentals.ingest.tijori_overview_company`.

Three rules hold across every builder:

* an element with no stable address (no name, no column) is fatal, because every
  downstream selection on it would be ambiguous;
* anything published but not modeled is preserved verbatim and drift-logged,
  never dropped;
* a numeric lexeme reads through the shared Tijori cell rule, so the source text
  always survives beside its ``Decimal | None`` reading.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from fundamentals.ingest.tijori_overview_common import (
    DATA_FIELD,
    NAME_FIELD,
    PATH_SEPARATOR,
    SERIES_FIELD_LABEL,
    SLUG_FIELD,
    SYMBOL_FIELD,
    SectionContext,
    anchor,
    as_list,
    as_object,
    invalid_known_values,
    invalid_values_json,
    iso_date,
    iso_datetime,
    number,
    optional_int,
    optional_string,
    reject_duplicates,
    required_name,
    retained_invalid_json,
    series,
    unmodeled,
)
from fundamentals.ingest.tijori_overview_company import build_company_details
from fundamentals.ingest.tijori_overview_models import (
    TijoriCorporateAction,
    TijoriCorporateActionsSection,
    TijoriCustomFinancialBlock,
    TijoriCustomFinancialRow,
    TijoriCustomFinancialsSection,
    TijoriMarketShareChart,
    TijoriMarketShareSection,
    TijoriOverviewSchemaError,
    TijoriOverviewSection,
    TijoriOverviewSectionBase,
    TijoriPeerColumn,
    TijoriPeerRow,
    TijoriPeersSection,
    TijoriPriceChartPeer,
    TijoriPriceChartPeersSection,
    TijoriPriceReturn,
    TijoriPriceReturnsSection,
    TijoriPriceSeriesSection,
    TijoriQuarantinedAction,
    TijoriRatio,
    TijoriRatiosSection,
)
from fundamentals.ingest.tijori_overview_revenue_mix import build_revenue_mix
from fundamentals.ingest.tijori_tables import cell_reading, raw_json

_LOGGER = structlog.get_logger(__name__)

_EX_DATE_FIELD = "ex_date"
_EVENT_DETAILS_FIELD = "event_details"
_EVENT_DATE_FIELD = "event_date"
_CORPORATE_ACTION_FIELDS = frozenset({_EX_DATE_FIELD, _EVENT_DETAILS_FIELD, _EVENT_DATE_FIELD})
_CORPORATE_ACTION_STRING_FIELDS = (_EX_DATE_FIELD, _EVENT_DETAILS_FIELD, _EVENT_DATE_FIELD)
# An action is identified by its dates; ``event_details`` is payload, so an
# unreadable one is retained beside the action rather than quarantining it.
_CORPORATE_ACTION_IDENTITY_FIELDS = (_EX_DATE_FIELD, _EVENT_DATE_FIELD)

_SHORT_NAME_FIELD = "short_name"
_DISPLAY_NAME_FIELD = "display_name"
_UNIT_FIELD = "unit"
_VALUE_FIELD = "value"
_ID_FIELD = "id"
_RATIO_FIELDS = frozenset(
    {NAME_FIELD, _SHORT_NAME_FIELD, _DISPLAY_NAME_FIELD, _UNIT_FIELD, _VALUE_FIELD, _ID_FIELD}
)

_COLUMN_FIELD = "column"
_REPORT_DATES_FIELD = "report_dates"
_SUB_ROWS_FIELD = "sub_rows"
_CUSTOM_BLOCK_FIELDS = frozenset({DATA_FIELD, _COLUMN_FIELD, _REPORT_DATES_FIELD})
_CUSTOM_ROW_FIELDS = frozenset({NAME_FIELD, _VALUE_FIELD})

_SAMPLE_SIZE_FIELD = "sample_size"
_METHODOLOGY_FIELD = "methodology"
_LATEST_VALUE_FIELD = "latest_value"
_LATEST_DATE_FIELD = "latest_date"
_SOURCE_FIELD = "source"
_MARKET_SHARE_FIELDS = frozenset(
    {
        NAME_FIELD,
        _ID_FIELD,
        _SAMPLE_SIZE_FIELD,
        _METHODOLOGY_FIELD,
        DATA_FIELD,
        _LATEST_VALUE_FIELD,
        _UNIT_FIELD,
        _LATEST_DATE_FIELD,
        _SOURCE_FIELD,
    }
)

_COLUMNS_FIELD = "columns"

_TYPE_FIELD = "type"
_PRICE_CHART_PEER_FIELDS = frozenset({NAME_FIELD, _ID_FIELD, _TYPE_FIELD, SYMBOL_FIELD})


def build_corporate_actions(island: Any, context: SectionContext) -> TijoriCorporateActionsSection:
    """Build the bonus/dividend/rights/split history grouped by action type."""
    grouped = as_object(island, context.island_id)
    actions: list[TijoriCorporateAction] = []
    action_types: list[str] = []
    empty_types: list[str] = []
    quarantined: list[TijoriQuarantinedAction] = []
    unmodeled_entries: dict[str, Any] = {}
    for action_type, raw_events in grouped.items():
        action_types.append(action_type)
        if not isinstance(raw_events, list):
            unmodeled_entries[action_type] = raw_events
            continue
        if not raw_events:
            empty_types.append(action_type)
            continue
        for index, raw_event in enumerate(raw_events):
            element_path = f"{action_type}{PATH_SEPARATOR}{index}"
            if not isinstance(raw_event, dict):
                unmodeled_entries[element_path] = raw_event
                continue
            invalid = invalid_known_values(raw_event, strings=_CORPORATE_ACTION_STRING_FIELDS)
            unreadable_identity = tuple(
                field for field in _CORPORATE_ACTION_IDENTITY_FIELDS if field in invalid
            )
            if unreadable_identity:
                # An action whose dates cannot be read has no usable identity;
                # emitting it as a blank action would misreport the history.
                _LOGGER.warning(
                    "tijori_overview_corporate_action_quarantined",
                    island=context.island_id,
                    element=element_path,
                    unreadable_fields=list(unreadable_identity),
                )
                quarantined.append(
                    TijoriQuarantinedAction(
                        action_type=action_type,
                        element_path=element_path,
                        reason=(f"unreadable date identity: {', '.join(unreadable_identity)}"),
                        raw_json=raw_json(raw_event),
                    )
                )
                continue
            ex_date = optional_string(raw_event, _EX_DATE_FIELD) or ""
            event_date = optional_string(raw_event, _EVENT_DATE_FIELD) or ""
            actions.append(
                TijoriCorporateAction(
                    action_type=action_type,
                    ex_date=ex_date,
                    ex_date_iso=iso_date(ex_date) if ex_date else None,
                    event_details=optional_string(raw_event, _EVENT_DETAILS_FIELD) or "",
                    event_date=event_date,
                    event_date_iso=iso_datetime(event_date) if event_date else None,
                    provenance=anchor(
                        context, element_path=element_path, field_label=_EVENT_DETAILS_FIELD
                    ),
                    unmodeled_fields_json=unmodeled(
                        raw_event, _CORPORATE_ACTION_FIELDS, context=context, element=element_path
                    ),
                    invalid_fields_json=retained_invalid_json(
                        invalid, context=context, element=element_path
                    ),
                )
            )
    if unmodeled_entries:
        _LOGGER.warning(
            "tijori_overview_corporate_actions_unmodeled",
            elements=sorted(unmodeled_entries),
        )
    return TijoriCorporateActionsSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        actions=tuple(actions),
        action_types=tuple(action_types),
        empty_action_types=tuple(empty_types),
        quarantined_actions=tuple(quarantined),
        unmodeled_fields_json=raw_json(unmodeled_entries) if unmodeled_entries else None,
    )


def build_ratios(island: Any, context: SectionContext) -> TijoriRatiosSection:
    """Build the overview ratio strip, addressed by Tijori's metric names."""
    ratios: list[TijoriRatio] = []
    for entry in as_list(island, context.island_id):
        ratio = as_object(entry, f"{context.island_id} entry")
        name = required_name(ratio, context.island_id)
        ratios.append(
            TijoriRatio(
                name=name,
                short_name=optional_string(ratio, _SHORT_NAME_FIELD),
                display_name=optional_string(ratio, _DISPLAY_NAME_FIELD),
                unit=optional_string(ratio, _UNIT_FIELD),
                source_metric_id=optional_int(ratio, _ID_FIELD),
                amount=number(
                    ratio.get(_VALUE_FIELD),
                    context,
                    element_path=name,
                    field_label=_VALUE_FIELD,
                ),
                unmodeled_fields_json=unmodeled(
                    ratio, _RATIO_FIELDS, context=context, element=name
                ),
                invalid_fields_json=invalid_values_json(
                    ratio,
                    context=context,
                    element=name,
                    strings=(_SHORT_NAME_FIELD, _DISPLAY_NAME_FIELD, _UNIT_FIELD),
                    integers=(_ID_FIELD,),
                ),
            )
        )
    reject_duplicates(tuple(ratio.name for ratio in ratios), context)
    return TijoriRatiosSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        ratios=tuple(ratios),
    )


def _custom_financial_row(
    raw_row: Any, context: SectionContext, *, column: str, report_dates: tuple[str, ...]
) -> TijoriCustomFinancialRow:
    """Build one operational-KPI row, quarantining it when it cannot be aligned."""
    row = as_object(raw_row, f"{context.island_id} {column} sub_row")
    label = required_name(row, f"{context.island_id} {column} sub_row")
    element_path = f"{column}{PATH_SEPARATOR}{label}"
    raw_values = as_list(row.get(_VALUE_FIELD), f"{context.island_id} {element_path} value")
    unmodeled_json = unmodeled(row, _CUSTOM_ROW_FIELDS, context=context, element=element_path)
    if len(raw_values) != len(report_dates):
        _LOGGER.warning(
            "tijori_overview_custom_financial_cardinality_mismatch",
            column=column,
            row=label,
            got=len(raw_values),
            expected=len(report_dates),
        )
        return TijoriCustomFinancialRow(
            label=label,
            cells=(),
            unaligned_raw_values=tuple(cell_reading(value)[1] for value in raw_values),
            unmodeled_fields_json=unmodeled_json,
        )
    return TijoriCustomFinancialRow(
        label=label,
        cells=tuple(
            number(
                raw_value,
                context,
                element_path=element_path,
                field_label=f"{index}{PATH_SEPARATOR}{report_date}",
            )
            for index, (report_date, raw_value) in enumerate(
                zip(report_dates, raw_values, strict=True)
            )
        ),
        unmodeled_fields_json=unmodeled_json,
    )


def build_custom_financials(island: Any, context: SectionContext) -> TijoriCustomFinancialsSection:
    """Build the operational-KPI blocks, one per statement column Tijori mirrors."""
    blocks: list[TijoriCustomFinancialBlock] = []
    for entry in as_list(island, context.island_id):
        block = as_object(entry, f"{context.island_id} block")
        column = required_name(block, f"{context.island_id} block", _COLUMN_FIELD)
        report_dates = tuple(
            as_list(block.get(_REPORT_DATES_FIELD), f"{context.island_id} {column} report_dates")
        )
        if not all(isinstance(label, str) and label.strip() for label in report_dates):
            raise TijoriOverviewSchemaError(
                f"tijori overview {context.island_id} {column} report_dates must be non-empty "
                f"strings"
            )
        data = as_object(block.get(DATA_FIELD), f"{context.island_id} {column} data")
        rows = tuple(
            _custom_financial_row(
                raw_row, context, column=column, report_dates=tuple(str(x) for x in report_dates)
            )
            for raw_row in as_list(
                data.get(_SUB_ROWS_FIELD), f"{context.island_id} {column} sub_rows"
            )
        )
        reject_duplicates(tuple(f"{column}{PATH_SEPARATOR}{row.label}" for row in rows), context)
        blocks.append(
            TijoriCustomFinancialBlock(
                column=column,
                report_dates=tuple(str(label) for label in report_dates),
                rows=rows,
                cardinality_mismatch_rows=tuple(
                    row.label for row in rows if row.unaligned_raw_values
                ),
                unmodeled_fields_json=unmodeled(
                    block, _CUSTOM_BLOCK_FIELDS, context=context, element=column
                ),
            )
        )
    reject_duplicates(tuple(block.column for block in blocks), context)
    return TijoriCustomFinancialsSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        blocks=tuple(blocks),
    )


def build_market_share(island: Any, context: SectionContext) -> TijoriMarketShareSection:
    """Build the segment market-share charts and their full published series."""
    charts: list[TijoriMarketShareChart] = []
    for entry in as_list(island, context.island_id):
        chart = as_object(entry, f"{context.island_id} chart")
        name = required_name(chart, f"{context.island_id} chart")
        chart_series, malformed = series(
            chart.get(DATA_FIELD, []), label=f"{context.island_id}{PATH_SEPARATOR}{name}"
        )
        charts.append(
            TijoriMarketShareChart(
                name=name,
                chart_id=optional_int(chart, _ID_FIELD),
                unit=optional_string(chart, _UNIT_FIELD),
                latest_date=optional_string(chart, _LATEST_DATE_FIELD),
                source_url=optional_string(chart, _SOURCE_FIELD),
                sample_size_json=(
                    None
                    if chart.get(_SAMPLE_SIZE_FIELD) is None
                    else raw_json(chart[_SAMPLE_SIZE_FIELD])
                ),
                methodology_json=(
                    None
                    if chart.get(_METHODOLOGY_FIELD) is None
                    else raw_json(chart[_METHODOLOGY_FIELD])
                ),
                latest_value=number(
                    chart.get(_LATEST_VALUE_FIELD),
                    context,
                    element_path=name,
                    field_label=_LATEST_VALUE_FIELD,
                ),
                series=chart_series,
                malformed_point_count=malformed,
                series_provenance=anchor(
                    context, element_path=name, field_label=SERIES_FIELD_LABEL
                ),
                unmodeled_fields_json=unmodeled(
                    chart, _MARKET_SHARE_FIELDS, context=context, element=name
                ),
                invalid_fields_json=invalid_values_json(
                    chart,
                    context=context,
                    element=name,
                    strings=(_UNIT_FIELD, _LATEST_DATE_FIELD, _SOURCE_FIELD),
                    integers=(_ID_FIELD,),
                    lists=(DATA_FIELD,),
                ),
            )
        )
    reject_duplicates(tuple(chart.name for chart in charts), context)
    return TijoriMarketShareSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        charts=tuple(charts),
    )


def _peer_parts(island: Any, context: SectionContext) -> tuple[list[Any], list[Any], str | None]:
    """Split the peer island into its column block and its row block.

    The island is a two-element list whose members are told apart by the key each
    carries, never by position: assuming the order would silently swap columns
    for rows the day Tijori reorders them.
    """
    entries = as_list(island, context.island_id)
    columns: list[list[Any]] = []
    rows: list[list[Any]] = []
    unmodeled: list[Any] = []
    for entry in entries:
        if isinstance(entry, dict) and _COLUMNS_FIELD in entry:
            columns.append(as_list(entry[_COLUMNS_FIELD], f"{context.island_id} columns"))
        elif isinstance(entry, dict) and DATA_FIELD in entry:
            rows.append(as_list(entry[DATA_FIELD], f"{context.island_id} data"))
        else:
            unmodeled.append(entry)
    if len(columns) != 1 or len(rows) != 1:
        raise TijoriOverviewSchemaError(
            f"tijori overview {context.island_id} must publish exactly one 'columns' block and "
            f"one 'data' block; found {len(columns)} and {len(rows)}"
        )
    if unmodeled:
        _LOGGER.warning(
            "tijori_overview_peers_block_unmodeled", island=context.island_id, count=len(unmodeled)
        )
    return columns[0], rows[0], raw_json(unmodeled) if unmodeled else None


def _peer_column(raw_column: dict[str, Any], context: SectionContext) -> TijoriPeerColumn:
    """Build one peer-table column header, retaining any unreadable modeled field."""
    name = required_name(raw_column, f"{context.island_id} column")
    return TijoriPeerColumn(
        name=name,
        short_name=optional_string(raw_column, _SHORT_NAME_FIELD),
        unit=optional_string(raw_column, _UNIT_FIELD),
        invalid_fields_json=invalid_values_json(
            raw_column,
            context=context,
            element=name,
            strings=(_SHORT_NAME_FIELD, _UNIT_FIELD),
        ),
    )


def build_peers(island: Any, context: SectionContext) -> TijoriPeersSection:
    """Build the peer comparison table from its declared columns and rows."""
    raw_columns, raw_rows, unmodeled_blocks = _peer_parts(island, context)
    columns = tuple(
        _peer_column(as_object(entry, f"{context.island_id} column"), context)
        for entry in raw_columns
    )
    reject_duplicates(tuple(column.name for column in columns), context)
    known_row_fields = frozenset({NAME_FIELD, SLUG_FIELD}) | {column.name for column in columns}
    rows: list[TijoriPeerRow] = []
    for entry in raw_rows:
        raw_row = as_object(entry, f"{context.island_id} row")
        name = required_name(raw_row, f"{context.island_id} row")
        rows.append(
            TijoriPeerRow(
                name=name,
                slug=optional_string(raw_row, SLUG_FIELD),
                cells=tuple(
                    number(
                        raw_row.get(column.name),
                        context,
                        element_path=name,
                        field_label=column.name,
                    )
                    for column in columns
                ),
                missing_columns=tuple(
                    column.name for column in columns if column.name not in raw_row
                ),
                unmodeled_fields_json=unmodeled(
                    raw_row, frozenset(known_row_fields), context=context, element=name
                ),
                invalid_fields_json=invalid_values_json(
                    raw_row, context=context, element=name, strings=(SLUG_FIELD,)
                ),
            )
        )
    reject_duplicates(tuple(row.name for row in rows), context)
    return TijoriPeersSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        columns=columns,
        rows=tuple(rows),
        unmodeled_fields_json=unmodeled_blocks,
    )


def build_price_returns(island: Any, context: SectionContext) -> TijoriPriceReturnsSection:
    """Build the trailing price returns, addressed by Tijori's window labels."""
    windows = as_object(island, context.island_id)
    returns = tuple(
        TijoriPriceReturn(
            window=window,
            amount=number(raw_value, context, element_path=window, field_label=_VALUE_FIELD),
        )
        for window, raw_value in windows.items()
    )
    return TijoriPriceReturnsSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        returns=returns,
    )


def build_price_series(island: Any, context: SectionContext) -> TijoriPriceSeriesSection:
    """Build one price series (intraday ticks or the daily price chart)."""
    points, malformed = series(island, label=context.island_id)
    return TijoriPriceSeriesSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        points=points,
        malformed_point_count=malformed,
        series_provenance=anchor(
            context, element_path=context.section.value, field_label=SERIES_FIELD_LABEL
        ),
    )


def build_price_chart_peers(island: Any, context: SectionContext) -> TijoriPriceChartPeersSection:
    """Build the comparison entities offered beside the price chart."""
    peers: list[TijoriPriceChartPeer] = []
    for index, entry in enumerate(as_list(island, context.island_id)):
        peer = as_object(entry, f"{context.island_id} entry")
        name = required_name(peer, context.island_id)
        # Nothing in this island guarantees a unique peer name — two entries may
        # legitimately share one display name — so position leads the address.
        element_path = f"{index}{PATH_SEPARATOR}{name}"
        peers.append(
            TijoriPriceChartPeer(
                name=name,
                peer_id=optional_int(peer, _ID_FIELD),
                peer_type=optional_string(peer, _TYPE_FIELD),
                symbol=optional_string(peer, SYMBOL_FIELD),
                provenance=anchor(context, element_path=element_path, field_label=_TYPE_FIELD),
                unmodeled_fields_json=unmodeled(
                    peer, _PRICE_CHART_PEER_FIELDS, context=context, element=element_path
                ),
                invalid_fields_json=invalid_values_json(
                    peer,
                    context=context,
                    element=element_path,
                    strings=(_TYPE_FIELD, SYMBOL_FIELD),
                    integers=(_ID_FIELD,),
                ),
            )
        )
    return TijoriPriceChartPeersSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        peers=tuple(peers),
    )


SECTION_BUILDERS: dict[
    TijoriOverviewSection, Callable[[Any, SectionContext], TijoriOverviewSectionBase]
] = {
    TijoriOverviewSection.CORPORATE_ACTIONS: build_corporate_actions,
    TijoriOverviewSection.RATIOS: build_ratios,
    TijoriOverviewSection.CUSTOM_FINANCIALS: build_custom_financials,
    TijoriOverviewSection.MARKET_SHARE: build_market_share,
    TijoriOverviewSection.PEERS: build_peers,
    TijoriOverviewSection.PRICE_RETURNS: build_price_returns,
    TijoriOverviewSection.INTRADAY_PRICE: build_price_series,
    TijoriOverviewSection.PRICE_CHART: build_price_series,
    TijoriOverviewSection.PRICE_CHART_PEERS: build_price_chart_peers,
    TijoriOverviewSection.COMPANY_DETAILS: build_company_details,
    # The one builder whose payload is collected off the rendered markup rather
    # than decoded from a JSON island; it takes the same (payload, context) pair.
    TijoriOverviewSection.REVENUE_MIX: build_revenue_mix,
}
