"""Builders for Tijori's ancillary company-analysis JSON APIs.

Each builder turns one raw API response into its typed contract from
:mod:`fundamentals.ingest.tijori_analysis_models`. Transport, credentials, and
the per-surface entry point live in :mod:`fundamentals.ingest.tijori_source`,
which imports this module; dependency flow is one-way.

Four rules hold across every builder, matching the page-island families:

* addressing is position-led — nothing in these documents guarantees a unique
  item name within a window, so the index leads the element path and the name
  follows it;
* an element with no readable name is fatal, because an unaddressable element
  makes every downstream selection on it ambiguous;
* anything published but not modeled is preserved verbatim and drift-logged,
  never dropped, and a modeled key published unreadably is retained separately;
* a numeric lexeme reads through the shared Tijori cell rule, so the source text
  survives beside its ``Decimal | None`` reading — and an omitted value stays
  omitted in ``amount`` rather than being computed. Where a total's derivation
  is rendered-verified it is computed into the separate ``derived_value`` slot,
  labelled with the rule that produced it, so a derived number is never mistaken
  for a published one.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_analysis_models import (
    EMPTY_DOCUMENT_NOTE,
    KNOWN_WINDOWS,
    METRIC_ID_REQUIRED,
    METRIC_SECTIONS,
    SECTION_DOCUMENT_IDS,
    TijoriAnalysisAmount,
    TijoriAnalysisMetadata,
    TijoriAnalysisMetricIdError,
    TijoriAnalysisOutcome,
    TijoriAnalysisResponseStatusError,
    TijoriAnalysisSchemaError,
    TijoriAnalysisSection,
    TijoriAnalysisSectionBase,
    TijoriAnalysisWindow,
    TijoriBalanceSheetSnapshotSection,
    TijoriCashFlowWaterfallSection,
    TijoriFlowItem,
    TijoriFundFlowGroup,
    TijoriFundFlowSection,
    TijoriOpMetricsSection,
    TijoriSnapshotEntry,
    TijoriSnapshotSide,
    TijoriSumDerivation,
)
from fundamentals.ingest.tijori_series import read_series
from fundamentals.ingest.tijori_tables import TIJORI_SOURCE_ID, cell_reading, raw_json

_LOGGER = structlog.get_logger(__name__)

PATH_SEPARATOR = "/"

_DATA_FIELD = "data"
_STATUS_FIELD = "status"
_PEERS_FIELD = "peers"
_NAME_FIELD = "name"
_FIELD_NAME_FIELD = "field_name"
_VALUE_FIELD = "value"
_Y_FIELD = "y"
_IS_SUM_FIELD = "isSum"
_SERIES_FIELD_LABEL = "data"
_SERIES_ELEMENT_PATH = "series"
_SUCCESS_STATUS_RANGE = (200, 300)

_ENVELOPE_FIELDS = frozenset({_DATA_FIELD, _STATUS_FIELD})
_OP_METRICS_ENVELOPE_FIELDS = frozenset({_DATA_FIELD, _PEERS_FIELD})
_FLOW_ITEM_FIELDS = frozenset({_NAME_FIELD, _Y_FIELD, _IS_SUM_FIELD})
_FLOW_GROUP_FIELDS = frozenset({_NAME_FIELD, _DATA_FIELD})
_SNAPSHOT_SIDE_FIELDS = frozenset({_FIELD_NAME_FIELD, _DATA_FIELD})
_SNAPSHOT_ENTRY_FIELDS = frozenset({_NAME_FIELD, _VALUE_FIELD})


class AnalysisContext(BaseModel):
    """Invariant inputs shared by every element built from one API document."""

    model_config = ConfigDict(frozen=True)

    section: TijoriAnalysisSection
    document_id: str
    source_url: str
    content_sha256: str
    retrieved_at: datetime
    metadata: TijoriAnalysisMetadata


def _anchor(
    context: AnalysisContext, *, table_key: str, element_path: str, field_label: str
) -> Provenance:
    """Anchor one element to the API document and the sub-document it came from."""
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=context.content_sha256,
        anchor_type=SourceAnchorType.API_DOCUMENT,
        context_ref=(
            f"{context.source_url}#{context.document_id}/{table_key}/{element_path}/{field_label}"
        ),
        document_id=context.document_id,
        table_key=table_key,
        row_label=element_path,
        column_label=field_label,
        retrieved_at=context.retrieved_at,
        first_seen_at=context.retrieved_at,
    )


def _amount(
    raw_value: Any,
    context: AnalysisContext,
    *,
    table_key: str,
    element_path: str,
    field_label: str,
) -> TijoriAnalysisAmount:
    """Read one anchored numeric lexeme through the shared Tijori cell rule."""
    value, raw_text = cell_reading(raw_value)
    return TijoriAnalysisAmount(
        value=value,
        raw_text=raw_text,
        provenance=_anchor(
            context, table_key=table_key, element_path=element_path, field_label=field_label
        ),
    )


def _as_object(value: Any, label: str) -> dict[str, Any]:
    """Require an untrusted JSON object with a named failure reason."""
    if not isinstance(value, dict):
        raise TijoriAnalysisSchemaError(f"tijori analysis {label} must be an object")
    return value


def _as_list(value: Any, label: str) -> list[Any]:
    """Require an untrusted JSON array with a named failure reason."""
    if not isinstance(value, list):
        raise TijoriAnalysisSchemaError(f"tijori analysis {label} must be a list")
    return value


def _required_name(entry: dict[str, Any], label: str, field: str = _NAME_FIELD) -> str:
    """Require the name of one element; an unnameable element is fatal."""
    name = entry.get(field)
    if not isinstance(name, str) or not name.strip():
        raise TijoriAnalysisSchemaError(
            f"tijori analysis {label} {field} must be a non-empty string"
        )
    return name


def _unmodeled(
    entry: dict[str, Any], known_fields: frozenset[str], *, context: AnalysisContext, element: str
) -> str | None:
    """Preserve and log every published key this contract does not model."""
    extra = {key: value for key, value in entry.items() if key not in known_fields}
    if not extra:
        return None
    _LOGGER.warning(
        "tijori_analysis_field_drift",
        section=context.section.value,
        document=context.document_id,
        element=element,
        unmodeled_fields=sorted(str(key) for key in extra),
    )
    return raw_json(extra)


def _invalid_values_json(
    entry: dict[str, Any],
    *,
    context: AnalysisContext,
    element: str,
    strings: tuple[str, ...] = (),
    booleans: tuple[str, ...] = (),
) -> str | None:
    """Retain verbatim any modeled key of one element that was unreadable.

    An absent key and a JSON-null key are not invalid — they were simply not
    published. A key that IS published but carries the wrong kind of value is
    invalid, because reading it as ``None`` would present a source claim as
    missing data. Numeric keys are excluded by design: the shared cell rule
    already keeps an unreadable number's lexeme beside a null reading.
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
        "tijori_analysis_field_unreadable",
        section=context.section.value,
        document=context.document_id,
        element=element,
        unreadable_fields=sorted(str(key) for key in invalid),
    )
    return raw_json(invalid)


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


def reject_duplicate_anchors(built: TijoriAnalysisSectionBase) -> None:
    """Fail loudly when two elements of one artifact share a complete anchor.

    One analysis artifact spans several sub-documents (a window, a balance-sheet
    side), so the comparison is the full ``table_key``/``row_label``/
    ``column_label`` triple: comparing less would report the same item in two
    windows as a collision, and comparing only within a window would miss a
    future addressing change that collapses two windows onto one key.
    """
    anchors: list[Provenance] = []
    _collect_anchors(built, anchors)
    collisions = sorted(
        f"{table_key}/{row_label}/{column_label}"
        for (table_key, row_label, column_label), count in Counter(
            (found.table_key, found.row_label, found.column_label) for found in anchors
        ).items()
        if count > 1
    )
    if collisions:
        raise TijoriAnalysisSchemaError(
            f"tijori analysis document {built.document_id!r} anchors two elements identically: "
            f"{', '.join(collisions)}"
        )


def _unknown_windows(windows: dict[str, Any]) -> tuple[str, ...]:
    """Name the window keys this contract has not seen live, keeping their data."""
    unknown = tuple(window for window in windows if window not in KNOWN_WINDOWS)
    if unknown:
        _LOGGER.warning("tijori_analysis_unknown_windows", windows=sorted(unknown))
    return unknown


def _flow_item(
    raw_item: Any,
    context: AnalysisContext,
    *,
    table_key: str,
    prefix: str,
    index: int,
) -> TijoriFlowItem:
    """Build one flow item, keeping an omitted derived total omitted."""
    item = _as_object(raw_item, f"{context.document_id} {table_key} item")
    name = _required_name(item, f"{context.document_id} {table_key} item")
    element_path = f"{prefix}{index}{PATH_SEPARATOR}{name}"
    is_sum = item.get(_IS_SUM_FIELD)
    return TijoriFlowItem(
        name=name,
        amount=_amount(
            item.get(_Y_FIELD),
            context,
            table_key=table_key,
            element_path=element_path,
            field_label=_Y_FIELD,
        ),
        amount_published=_Y_FIELD in item,
        is_sum=is_sum is True,
        unmodeled_fields_json=_unmodeled(
            item, _FLOW_ITEM_FIELDS, context=context, element=element_path
        ),
        invalid_fields_json=_invalid_values_json(
            item, context=context, element=element_path, booleans=(_IS_SUM_FIELD,)
        ),
    )


def _window_items(
    raw_items: Any,
    context: AnalysisContext,
    *,
    label: str,
    window: str,
    prefix: str,
    derive_sums: bool,
) -> tuple[TijoriFlowItem, ...]:
    """Build one window's items, deriving its total rows when the rule is evidenced.

    RENDERED VERIFICATION (TITAN cash-flow waterfall, owner capture 2026-08-25):
    every ``isSum`` row the page displays equals the cumulative sum of ALL prior
    non-sum items in the same window — prior sum rows are never re-added. On the
    1yr window that rule reproduces each displayed total exactly: CFO 5590,
    FCFF 4688, FCFE 1056, Core 80, Net Cash 497.

    The derivation is applied only where it was verified (``derive_sums``), never
    to a section whose totals were not checked against a rendering. It is never
    partial: if any prior item in the window carries a null reading — the source
    omitted or published it unreadably — the sum cannot be completed and
    ``derived_value`` stays None rather than silently reporting the total of the
    items that happened to parse. A sum row with no prior items derives nothing,
    because the sum of nothing is an assumption, not an observation.
    """
    items: list[TijoriFlowItem] = []
    running_total: Decimal | None = Decimal(0)
    prior_items = 0
    for index, raw_item in enumerate(_as_list(raw_items, f"{label} {window}")):
        item = _flow_item(raw_item, context, table_key=window, prefix=prefix, index=index)
        if item.is_sum:
            if derive_sums:
                item = item.model_copy(
                    update={
                        "derived_value": running_total if prior_items else None,
                        "derivation": TijoriSumDerivation.CUMULATIVE_SUM_OF_PRIOR_ITEMS,
                    }
                )
        else:
            prior_items += 1
            value = item.amount.value
            running_total = (
                None if running_total is None or value is None else running_total + value
            )
        items.append(item)
    return tuple(items)


def _windows(
    raw_windows: Any,
    context: AnalysisContext,
    *,
    label: str,
    prefix: str = "",
    derive_sums: bool = False,
) -> tuple[tuple[TijoriAnalysisWindow, ...], tuple[str, ...]]:
    """Build every published window, keeping its source key exactly as given."""
    windows = _as_object(raw_windows, label)
    built = tuple(
        TijoriAnalysisWindow(
            window=window,
            items=_window_items(
                raw_items,
                context,
                label=label,
                window=window,
                prefix=prefix,
                derive_sums=derive_sums,
            ),
        )
        for window, raw_items in windows.items()
    )
    return built, _unknown_windows(windows)


def build_fund_flow(document: dict[str, Any], context: AnalysisContext) -> TijoriFundFlowSection:
    """Build the sources-and-uses groups across every published window."""
    groups: list[TijoriFundFlowGroup] = []
    for index, raw_group in enumerate(
        _as_list(_required_data(document, context), f"{context.document_id} data")
    ):
        group = _as_object(raw_group, f"{context.document_id} group")
        name = _required_name(group, f"{context.document_id} group")
        # Two groups may legitimately share a display name, so position leads
        # the address here exactly as it does inside a window.
        prefix = f"{index}{PATH_SEPARATOR}{name}{PATH_SEPARATOR}"
        windows, unknown = _windows(
            _required_data(group, context, element=f"{index}/{name}"),
            context,
            label=f"{context.document_id} {name} data",
            prefix=prefix,
        )
        groups.append(
            TijoriFundFlowGroup(
                name=name,
                windows=windows,
                unknown_windows=unknown,
                unmodeled_fields_json=_unmodeled(
                    group, _FLOW_GROUP_FIELDS, context=context, element=f"{index}/{name}"
                ),
                invalid_fields_json=_invalid_values_json(
                    group, context=context, element=f"{index}/{name}"
                ),
            )
        )
    return TijoriFundFlowSection(
        section=context.section,
        document_id=context.document_id,
        metadata=context.metadata,
        groups=tuple(groups),
        unmodeled_fields_json=_unmodeled(
            document, _ENVELOPE_FIELDS, context=context, element=context.document_id
        ),
    )


def build_balance_sheet_snapshot(
    document: dict[str, Any], context: AnalysisContext
) -> TijoriBalanceSheetSnapshotSection:
    """Build both sides of the balance-sheet snapshot in published order."""
    sides: list[TijoriSnapshotSide] = []
    for side_index, raw_side in enumerate(
        _as_list(_required_data(document, context), f"{context.document_id} data")
    ):
        side = _as_object(raw_side, f"{context.document_id} side")
        field_name = _required_name(side, f"{context.document_id} side", _FIELD_NAME_FIELD)
        table_key = f"{side_index}{PATH_SEPARATOR}{field_name}"
        entries: list[TijoriSnapshotEntry] = []
        for index, raw_entry in enumerate(
            _as_list(side.get(_DATA_FIELD), f"{context.document_id} {field_name} data")
        ):
            entry = _as_object(raw_entry, f"{context.document_id} {field_name} entry")
            name = _required_name(entry, f"{context.document_id} {field_name} entry")
            element_path = f"{index}{PATH_SEPARATOR}{name}"
            entries.append(
                TijoriSnapshotEntry(
                    name=name,
                    amount=_amount(
                        entry.get(_VALUE_FIELD),
                        context,
                        table_key=table_key,
                        element_path=element_path,
                        field_label=_VALUE_FIELD,
                    ),
                    unmodeled_fields_json=_unmodeled(
                        entry, _SNAPSHOT_ENTRY_FIELDS, context=context, element=element_path
                    ),
                    invalid_fields_json=_invalid_values_json(
                        entry, context=context, element=element_path
                    ),
                )
            )
        sides.append(
            TijoriSnapshotSide(
                field_name=field_name,
                entries=tuple(entries),
                unmodeled_fields_json=_unmodeled(
                    side, _SNAPSHOT_SIDE_FIELDS, context=context, element=table_key
                ),
                invalid_fields_json=_invalid_values_json(side, context=context, element=table_key),
            )
        )
    return TijoriBalanceSheetSnapshotSection(
        section=context.section,
        document_id=context.document_id,
        metadata=context.metadata,
        sides=tuple(sides),
        unmodeled_fields_json=_unmodeled(
            document, _ENVELOPE_FIELDS, context=context, element=context.document_id
        ),
    )


def build_cash_flow_waterfall(
    document: dict[str, Any], context: AnalysisContext
) -> TijoriCashFlowWaterfallSection:
    """Build the cash-flow waterfall steps for every published window.

    This is the one section whose ``isSum`` derivation is rendered-verified, so
    it is the only one that asks for derived totals; see :func:`_window_items`.
    """
    windows, unknown = _windows(
        _required_data(document, context),
        context,
        label=f"{context.document_id} data",
        derive_sums=True,
    )
    return TijoriCashFlowWaterfallSection(
        section=context.section,
        document_id=context.document_id,
        metadata=context.metadata,
        windows=windows,
        unknown_windows=unknown,
        unmodeled_fields_json=_unmodeled(
            document, _ENVELOPE_FIELDS, context=context, element=context.document_id
        ),
    )


def build_op_metrics(document: dict[str, Any], context: AnalysisContext) -> TijoriOpMetricsSection:
    """Build one operational metric's published history."""
    metric_id = context.metadata.metric_id
    if metric_id is None:
        raise TijoriAnalysisMetricIdError(METRIC_ID_REQUIRED)
    points, malformed = read_series(
        _as_list(_required_data(document, context), f"{context.document_id} data"),
        label=f"{context.document_id}/metric:{metric_id}",
        drift_event="tijori_analysis_series_points_unmodeled",
        document=context.document_id,
        metric_id=metric_id,
    )
    peers = document.get(_PEERS_FIELD)
    return TijoriOpMetricsSection(
        section=context.section,
        document_id=context.document_id,
        metadata=context.metadata,
        metric_id=metric_id,
        points=tuple(points),
        malformed_point_count=malformed,
        peer_count=len(peers) if isinstance(peers, list) else 0,
        peers_json=None if peers in (None, []) else raw_json(peers),
        series_provenance=_anchor(
            context,
            table_key=f"metric:{metric_id}",
            element_path=_SERIES_ELEMENT_PATH,
            field_label=_SERIES_FIELD_LABEL,
        ),
        unmodeled_fields_json=_unmodeled(
            document, _OP_METRICS_ENVELOPE_FIELDS, context=context, element=context.document_id
        ),
    )


def _required_data(
    entry: dict[str, Any], context: AnalysisContext, *, element: str | None = None
) -> Any:
    """Require the payload key; an absent one is drift, never an empty result.

    A response that omitted ``data`` altogether — an error envelope, a shape
    change — would otherwise build a structurally valid artifact with no
    elements and be reported as a successful empty acquisition. The same holds
    one level down: a group that omits its payload is drift, not a group that
    happens to have no windows.
    """
    if _DATA_FIELD not in entry:
        located = context.document_id if element is None else f"{context.document_id} {element}"
        raise TijoriAnalysisSchemaError(
            f"tijori analysis document {located!r} published no "
            f"{_DATA_FIELD!r} key; an absent payload is drift, not an empty result"
        )
    return entry[_DATA_FIELD]


def _response_status(document: dict[str, Any], document_id: str) -> int | None:
    """Validate the body's own status field, which three of the four APIs publish.

    Tijori answers some failures with HTTP 200 and a failing status in the body,
    so an unchecked status field would let an error envelope through the
    transport gate and be read as data.
    """
    if _STATUS_FIELD not in document:
        return None
    status = document[_STATUS_FIELD]
    if not isinstance(status, int) or isinstance(status, bool):
        raise TijoriAnalysisResponseStatusError(
            f"tijori analysis document {document_id!r} published a non-integer "
            f"{_STATUS_FIELD!r}: {raw_json(status)}"
        )
    if not _SUCCESS_STATUS_RANGE[0] <= status < _SUCCESS_STATUS_RANGE[1]:
        raise TijoriAnalysisResponseStatusError(
            f"tijori analysis document {document_id!r} reports {_STATUS_FIELD} {status}, "
            "which is not a success status"
        )
    return status


def build_tijori_analysis(
    raw: bytes,
    *,
    section: TijoriAnalysisSection,
    slug: str,
    symbol: str,
    company_id: int,
    source_url: str,
    content_sha256: str,
    retrieved_at: datetime,
    metric_id: int | None = None,
) -> TijoriAnalysisSectionBase:
    """Build one typed analysis artifact from one raw API response body."""
    if not slug.strip():
        raise TijoriAnalysisSchemaError("tijori requested slug is empty")
    if not symbol.strip():
        raise TijoriAnalysisSchemaError("tijori configured symbol is empty")
    if section in METRIC_SECTIONS and metric_id is None:
        raise TijoriAnalysisMetricIdError(METRIC_ID_REQUIRED)
    document_id = SECTION_DOCUMENT_IDS[section]
    try:
        decoded = json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TijoriAnalysisSchemaError(
            f"tijori analysis document {document_id!r} is not decodable JSON"
        ) from error
    document = _as_object(decoded, f"document {document_id!r}")
    context = AnalysisContext(
        section=section,
        document_id=document_id,
        source_url=source_url,
        content_sha256=content_sha256,
        retrieved_at=retrieved_at,
        metadata=TijoriAnalysisMetadata(
            section=section,
            document_id=document_id,
            slug=slug,
            symbol=symbol.strip(),
            company_id=company_id,
            metric_id=metric_id,
            source_url=source_url,
            file_sha256=content_sha256,
            retrieved_at=retrieved_at,
            response_status=_response_status(document, document_id),
        ),
    )
    built = _with_outcome(_SECTION_BUILDERS[section](document, context))
    reject_duplicate_anchors(built)
    _LOGGER.info(
        "tijori_analysis_parsed",
        section=section.value,
        document=document_id,
        slug=slug,
        company_id=company_id,
        metric_id=metric_id,
        outcome=built.outcome.value,
        elements=built.element_count,
    )
    return built


def _with_outcome(built: TijoriAnalysisSectionBase) -> TijoriAnalysisSectionBase:
    """Stamp the one successful outcome an artifact can carry, from one condition.

    Emptiness is decided by the element count and nothing else. Every other
    failure mode reached this point as an exception, so an artifact that exists
    at all is either OK or genuinely, verifiably empty.
    """
    if built.element_count:
        return built.model_copy(update={"outcome": TijoriAnalysisOutcome.OK, "note": None})
    return built.model_copy(
        update={"outcome": TijoriAnalysisOutcome.OK_EMPTY, "note": EMPTY_DOCUMENT_NOTE}
    )


_SECTION_BUILDERS: dict[
    TijoriAnalysisSection,
    Callable[[dict[str, Any], AnalysisContext], TijoriAnalysisSectionBase],
] = {
    TijoriAnalysisSection.FUND_FLOW: build_fund_flow,
    TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT: build_balance_sheet_snapshot,
    TijoriAnalysisSection.CASH_FLOW_WATERFALL: build_cash_flow_waterfall,
    TijoriAnalysisSection.OP_METRICS: build_op_metrics,
}
