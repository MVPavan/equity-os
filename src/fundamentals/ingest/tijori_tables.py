"""Typed raw-table contracts for Tijori financial JSON islands.

Acquisition contract: a table is parsed whenever its raw data exists in the
``fin_tables_data`` island. Plan and capability state (``financials_locks``,
``plan_details``) is metadata carried beside the table — it never decides whether
data is parsed, and it is never interpreted as a table key.

The cross-surface primitives this module is built on — the numeric-lexeme rule,
verbatim retention, and the plan/capability contract — live in
:mod:`fundamentals.ingest.tijori_common` and are re-exported here so every
existing importer of this module reaches them unchanged.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_common import (
    FINANCIALS_LOCKS_ISLAND_ID as FINANCIALS_LOCKS_ISLAND_ID,
)
from fundamentals.ingest.tijori_common import (
    PLAN_DETAILS_ISLAND_ID as PLAN_DETAILS_ISLAND_ID,
)
from fundamentals.ingest.tijori_common import (
    TIJORI_SOURCE_ID as TIJORI_SOURCE_ID,
)
from fundamentals.ingest.tijori_common import (
    TijoriCapabilityFlag as TijoriCapabilityFlag,
)
from fundamentals.ingest.tijori_common import (
    TijoriFeatureLock as TijoriFeatureLock,
)
from fundamentals.ingest.tijori_common import (
    TijoriIslandStatus as TijoriIslandStatus,
)
from fundamentals.ingest.tijori_common import (
    TijoriTableAccessMetadata as TijoriTableAccessMetadata,
)
from fundamentals.ingest.tijori_common import (
    TijoriUnparseableIsland as TijoriUnparseableIsland,
)
from fundamentals.ingest.tijori_common import (
    build_page_access as build_page_access,
)
from fundamentals.ingest.tijori_common import (
    cell_reading as cell_reading,
)
from fundamentals.ingest.tijori_common import (
    decimal_from_text as decimal_from_text,
)
from fundamentals.ingest.tijori_common import (
    raw_json as raw_json,
)

_LOGGER = structlog.get_logger(__name__)

FINANCIALS_ISLAND_ID = "fin_tables_data"

MAX_SUB_SECTION_DEPTH = 8
ROW_KEY_SEPARATOR = "/"
# Cell anchors carry the positional column index, so provenance stays unique even
# when a page repeats a period label.
_COLUMN_ANCHOR_SEGMENT = "col"

_REPORT_DATES_FIELD = "report_dates"
_REPORT_DATES_YOY_FIELD = "report_dates_yoy"
_SKIP_REPORT_DATES_FIELD = "skip_report_dates"
_TABLE_FOOTER_FIELD = "table_footer"
_DATA_FIELD = "data"
_ROW_LABEL_FIELD = "name"
_ROW_VALUES_FIELD = "value"
_ROW_FIELD_ID_FIELD = "field"
_SUB_SECTION_FIELD = "sub_section"

_KNOWN_TABLE_FIELDS = frozenset(
    {
        _REPORT_DATES_FIELD,
        _REPORT_DATES_YOY_FIELD,
        _SKIP_REPORT_DATES_FIELD,
        _TABLE_FOOTER_FIELD,
        _DATA_FIELD,
    }
)

# Detailed statements (bs_*_d, pl_*_d) ship every row with field="NA": a sentinel
# for "no machine id", not an identifier. Empty ids mean the same thing.
_ABSENT_FIELD_IDS = frozenset({"", "NA"})
# Leaf rows report no children as either an empty list or an empty string.
_LEAF_SUB_SECTIONS: tuple[Any, ...] = ("", [])


class TijoriError(Exception):
    """Base class for Tijori adapter failures."""


class TijoriCredentialsError(TijoriError):
    """No credentials injected — skippable so the pipeline never hard-fails."""


class TijoriFetchError(TijoriError):
    """Terminal fetch/transport failure (never a partial result)."""


class TijoriParseError(TijoriError):
    """The Tijori page was malformed or internally inconsistent."""


class TijoriTableKeyError(TijoriParseError):
    """The caller requested a table key outside the supported island schema."""


class TijoriTableAbsentError(TijoriParseError):
    """A supported requested table key has no data in the financials island."""


class TijoriTablesAbsentError(TijoriParseError):
    """The financials island carries no supported table at all."""


class TijoriTableSchemaError(TijoriParseError):
    """A raw Tijori table does not satisfy its typed shape."""


class TijoriTableDepthError(TijoriTableSchemaError):
    """Row nesting exceeded the supported ``sub_section`` recursion bound."""


class TijoriRowSelectionError(TijoriParseError):
    """A row selector matched no row, or matched more than one row."""


class TijoriTableKey(StrEnum):
    """The table keys Tijori's financial island actually publishes.

    Family prefix is the statement (``bs``/``pl``/``qt``/``cf``/``fr``); the
    segment after it is the statement scope (``c``/``s``); a trailing ``s``/``d``
    on balance-sheet and P&L keys is the summary/detailed presentation.
    """

    BALANCE_SHEET_CONSOLIDATED_DETAILED = "bs_c_d"
    BALANCE_SHEET_CONSOLIDATED_SUMMARY = "bs_c_s"
    BALANCE_SHEET_STANDALONE_DETAILED = "bs_s_d"
    BALANCE_SHEET_STANDALONE_SUMMARY = "bs_s_s"
    CASH_FLOW_CONSOLIDATED = "cf_c"
    CASH_FLOW_STANDALONE = "cf_s"
    RATIOS_CONSOLIDATED = "fr_c"
    RATIOS_STANDALONE = "fr_s"
    GROWTH = "growth"
    PROFIT_LOSS_CONSOLIDATED_DETAILED = "pl_c_d"
    PROFIT_LOSS_CONSOLIDATED_SUMMARY = "pl_c_s"
    PROFIT_LOSS_STANDALONE_DETAILED = "pl_s_d"
    PROFIT_LOSS_STANDALONE_SUMMARY = "pl_s_s"
    QUARTERLY_CONSOLIDATED = "qt_c"
    QUARTERLY_STANDALONE = "qt_s"


class TijoriTableScope(StrEnum):
    """Statement scope encoded by a supported Tijori table key."""

    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"
    UNKNOWN = "unknown"


_TABLE_SCOPES: dict[TijoriTableKey, TijoriTableScope] = {
    TijoriTableKey.BALANCE_SHEET_CONSOLIDATED_DETAILED: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.BALANCE_SHEET_CONSOLIDATED_SUMMARY: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.BALANCE_SHEET_STANDALONE_DETAILED: TijoriTableScope.STANDALONE,
    TijoriTableKey.BALANCE_SHEET_STANDALONE_SUMMARY: TijoriTableScope.STANDALONE,
    TijoriTableKey.CASH_FLOW_CONSOLIDATED: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.CASH_FLOW_STANDALONE: TijoriTableScope.STANDALONE,
    TijoriTableKey.RATIOS_CONSOLIDATED: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.RATIOS_STANDALONE: TijoriTableScope.STANDALONE,
    TijoriTableKey.GROWTH: TijoriTableScope.UNKNOWN,
    TijoriTableKey.PROFIT_LOSS_CONSOLIDATED_DETAILED: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.PROFIT_LOSS_CONSOLIDATED_SUMMARY: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.PROFIT_LOSS_STANDALONE_DETAILED: TijoriTableScope.STANDALONE,
    TijoriTableKey.PROFIT_LOSS_STANDALONE_SUMMARY: TijoriTableScope.STANDALONE,
    TijoriTableKey.QUARTERLY_CONSOLIDATED: TijoriTableScope.CONSOLIDATED,
    TijoriTableKey.QUARTERLY_STANDALONE: TijoriTableScope.STANDALONE,
}


# Table keys where the left-anchor rule for a short row is EVIDENCED, and
# therefore the only keys it is applied to.
#
# Evidence scope (owner captures, 2026-08-25): the rendered proof is the P&L
# family and nothing else. ``pl_s_s`` is DOM-verified directly — NETWEB's
# 'Others' row publishes 6 values against 10 columns and the site renders them
# in the FIRST six columns with em-dashes after. The other three P&L keys carry
# the identical ``fs_name='rm'`` derived sub-rows, observed live across the
# 10-stock smokes: same row source, same structure, so the same rule holds.
#
# Every other family — balance sheet, cash flow, ratios, growth, quarterly — has
# NO such observation, so a short row there keeps the original quarantine. A
# short row is only alignable where something actually showed which end is
# missing; extending this set needs new rendered evidence, not the assumption
# that one family's layout generalizes.
LEFT_ANCHOR_EVIDENCED_TABLES = frozenset(
    {
        TijoriTableKey.PROFIT_LOSS_CONSOLIDATED_DETAILED,
        TijoriTableKey.PROFIT_LOSS_CONSOLIDATED_SUMMARY,
        TijoriTableKey.PROFIT_LOSS_STANDALONE_DETAILED,
        TijoriTableKey.PROFIT_LOSS_STANDALONE_SUMMARY,
    }
)


class TijoriRowAlignment(StrEnum):
    """How one row's published values were mapped onto the table's columns.

    ``EXACT`` is the ordinary case: the row published one value per column.
    ``LEFT_ANCHORED_TRAILING_MISSING`` is the evidenced rule for a row that
    published FEWER values than the table has columns, and applies only to the
    tables in :data:`LEFT_ANCHOR_EVIDENCED_TABLES` — see :func:`_row_payload`
    for the rendered evidence and its scope.
    """

    EXACT = "exact"
    LEFT_ANCHORED_TRAILING_MISSING = "left_anchored_trailing_missing"


class TijoriTableCell(BaseModel):
    """One raw table cell: the source lexeme plus its numeric reading, if any.

    ``published`` is False for a trailing cell the row did not publish at all,
    which only happens under
    :attr:`TijoriRowAlignment.LEFT_ANCHORED_TRAILING_MISSING`. Such a cell reads
    the same as a published null (``value`` None, empty ``raw_text``), so the
    flag is what keeps "the source stated nothing here" from serializing
    identically to "the source stated null here".
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal | None
    raw_text: str
    provenance: Provenance
    published: bool = True


class TijoriTableRow(BaseModel):
    """One row addressed by its parent-qualified label path.

    ``row_key`` is always the label path, because Tijori's ``field`` ids are not
    table-unique: ``fr_c`` publishes ``ebit`` under two derivation contexts.
    ``field_id`` is therefore source metadata, never the address.

    A row with FEWER values than columns is aligned left onto the report dates
    by the evidenced rule in :func:`_row_payload` and marked
    ``LEFT_ANCHORED_TRAILING_MISSING``. A row with MORE values than columns is
    quarantined: ``cells`` is empty and the raw lexemes survive in
    ``unaligned_raw_values``. An empty ``cells`` with no unaligned values is the
    ordinary section-header case.
    """

    model_config = ConfigDict(frozen=True)

    row_key: str
    label: str
    field_id: str | None
    parent_labels: tuple[str, ...]
    depth: int
    alignment: TijoriRowAlignment = TijoriRowAlignment.EXACT
    cells: tuple[TijoriTableCell, ...]
    unaligned_raw_values: tuple[str, ...] = ()


class TijoriTableMetadata(BaseModel):
    """Response identity and acquisition metadata shared by all table outcomes."""

    model_config = ConfigDict(frozen=True)

    slug: str
    symbol: str
    company_id: int
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    island_id: str = FINANCIALS_ISLAND_ID
    access: TijoriTableAccessMetadata
    observed_unknown_table_keys: tuple[str, ...] = ()
    null_table_keys: tuple[str, ...] = ()


class TijoriTable(BaseModel):
    """One immutable raw Tijori financial table in source row order.

    The two row-level exception lists never overlap and must not be read alike:
    ``cardinality_mismatch_rows`` names rows that could not be aligned at all
    and hold no cells, while ``left_anchored_rows`` names rows that WERE aligned
    — by the evidenced left-anchor rule, not by the source's own cardinality —
    and do hold cells. A consumer that treats an inferred alignment as a
    published one needs the second list to tell them apart.
    """

    model_config = ConfigDict(frozen=True)

    key: TijoriTableKey
    scope: TijoriTableScope
    column_period_labels: tuple[str, ...]
    comparative_period_labels: tuple[str, ...] = ()
    skipped_period_labels: tuple[str, ...] = ()
    table_footer_json: str | None = None
    rows: tuple[TijoriTableRow, ...]
    cardinality_mismatch_rows: tuple[str, ...] = ()
    left_anchored_rows: tuple[str, ...] = ()
    metadata: TijoriTableMetadata

    def row(self, selector: str) -> TijoriTableRow:
        """Select one row by its row key, or by field id as a convenience.

        Row keys are parent-qualified label paths and address exactly one row.
        Field ids are source metadata and are NOT table-unique — Tijori repeats
        one id under several parents — so a field-id lookup that matches more
        than one row is reported as ambiguous rather than resolved by position.
        """
        matches = tuple(row for row in self.rows if row.row_key == selector) or tuple(
            row for row in self.rows if row.field_id == selector
        )
        if not matches:
            raise TijoriRowSelectionError(
                f"tijori table {self.key.value!r} has no row matching {selector!r}"
            )
        if len(matches) > 1:
            candidates = ", ".join(row.row_key for row in matches)
            raise TijoriRowSelectionError(
                f"tijori table {self.key.value!r} row selector {selector!r} is ambiguous; "
                f"candidates: {candidates}"
            )
        return matches[0]


class _RowBuildContext(BaseModel):
    """Invariant inputs shared by every row built for one table."""

    model_config = ConfigDict(frozen=True)

    key: TijoriTableKey
    column_labels: tuple[str, ...]
    content_sha256: str
    source_url: str
    retrieved_at: datetime


def parse_table_key(key: str) -> TijoriTableKey:
    """Validate one caller-supplied table key against the published key set."""
    try:
        return TijoriTableKey(key)
    except ValueError as error:
        supported = ", ".join(table_key.value for table_key in TijoriTableKey)
        raise TijoriTableKeyError(
            f"unsupported Tijori financial table key {key!r}; supported keys: {supported}"
        ) from error


def _as_object(value: Any, label: str) -> dict[str, Any]:
    """Require an untrusted JSON object for raw-table parsing."""
    if not isinstance(value, dict):
        raise TijoriTableSchemaError(f"tijori JSON island {label!r} must contain an object")
    return value


def _field_id(raw_field_id: Any) -> str | None:
    """Read Tijori's row identifier, rejecting its no-id sentinels.

    Detailed statements set ``field`` to ``"NA"`` on every row, so treating that
    as an identifier would collapse each row onto one key.
    """
    if not isinstance(raw_field_id, str) or raw_field_id.strip() in _ABSENT_FIELD_IDS:
        return None
    return raw_field_id


def _period_labels(value: Any, key: TijoriTableKey) -> tuple[str, ...]:
    """Validate column labels while preserving their exact source text."""
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(label, str) and label.strip() for label in value)
    ):
        raise TijoriTableSchemaError(
            f"tijori table {key.value!r} report_dates must be a non-empty string list"
        )
    labels: tuple[str, ...] = tuple(value)
    if len(set(labels)) != len(labels):
        _LOGGER.warning(
            "tijori_table_duplicate_column_labels",
            table=key.value,
            labels=labels,
        )
    return labels


def _optional_labels(value: Any, *, key: TijoriTableKey, field: str) -> tuple[str, ...]:
    """Preserve an optional label list; drift in its shape is metadata-only."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(label, str) for label in value):
        _LOGGER.warning(
            "tijori_table_optional_labels_unmodeled",
            table=key.value,
            field=field,
            raw=raw_json(value),
        )
        return ()
    return tuple(value)


def _row_payload(
    *, raw_values: Any, context: _RowBuildContext, row_key: str, label: str
) -> tuple[tuple[TijoriTableCell, ...], tuple[str, ...], TijoriRowAlignment]:
    """Build one row's cells, aligning a short row and quarantining a long one.

    Returns ``(cells, unaligned_raw_values, alignment)``.

    A row with FEWER values than columns is left-anchored onto
    ``report_dates``: its values fill the first columns in order and the
    trailing periods are the missing ones. That is an evidenced rule, not a
    guess. RENDERED EVIDENCE (NETWEB ``pl_s_s``, owner capture 2026-08-25): the
    'Others' row publishes 6 values against 10 columns, and the site renders
    them as 325 | 564 | 912 | — | — | — | — — the values in the FIRST columns
    with em-dashes for the trailing periods. The artifact raws 325.24 /
    563.812 / 911.784 sit at columns 4-6, with the first three columns among
    the ones the page skips. Trailing cells are emitted with
    ``published=False`` so an inferred absence never reads as a published null,
    and the row is marked ``LEFT_ANCHORED_TRAILING_MISSING``.

    That rule is applied ONLY to the tables in
    :data:`LEFT_ANCHOR_EVIDENCED_TABLES`, which is where it was actually
    observed. A short row in any other family is quarantined exactly as before:
    one family's rendered layout is not evidence about another's, and inferring
    period assignments from an unobserved layout would fabricate the very thing
    this rule exists to avoid.

    A row with MORE values than columns is quarantined everywhere, including in
    the evidenced tables: nothing observed says which end the surplus belongs
    to, so it yields no cells and keeps its raw lexemes instead. Alignment is
    never guessed and the table never dies.
    """
    if not isinstance(raw_values, list):
        raise TijoriTableSchemaError(
            f"tijori table {context.key.value!r} row {row_key!r} value must be a list"
        )
    if not raw_values:
        return (), (), TijoriRowAlignment.EXACT
    column_count = len(context.column_labels)
    published_count = len(raw_values)
    left_anchorable = context.key in LEFT_ANCHOR_EVIDENCED_TABLES
    if published_count > column_count or (published_count < column_count and not left_anchorable):
        unaligned = tuple(cell_reading(raw_value)[1] for raw_value in raw_values)
        _LOGGER.warning(
            "tijori_row_cardinality_mismatch",
            table=context.key.value,
            row_key=row_key,
            got=published_count,
            expected=column_count,
            left_anchor_evidenced=left_anchorable,
        )
        return (), unaligned, TijoriRowAlignment.EXACT
    alignment = (
        TijoriRowAlignment.EXACT
        if published_count == column_count
        else TijoriRowAlignment.LEFT_ANCHORED_TRAILING_MISSING
    )
    if alignment is TijoriRowAlignment.LEFT_ANCHORED_TRAILING_MISSING:
        _LOGGER.info(
            "tijori_row_left_anchored",
            table=context.key.value,
            row_key=row_key,
            published=published_count,
            columns=column_count,
        )
    padded: list[Any] = [*raw_values, *([None] * (column_count - published_count))]
    cells: list[TijoriTableCell] = []
    for column_index, (column_label, raw_value) in enumerate(
        zip(context.column_labels, padded, strict=True)
    ):
        value, raw_text = cell_reading(raw_value)
        cells.append(
            TijoriTableCell(
                value=value,
                raw_text=raw_text,
                published=column_index < published_count,
                provenance=Provenance(
                    source_id=TIJORI_SOURCE_ID,
                    file_sha256=context.content_sha256,
                    anchor_type=SourceAnchorType.JSON_ISLAND,
                    context_ref=(
                        f"{context.source_url}#{FINANCIALS_ISLAND_ID}/{context.key.value}/"
                        f"{row_key}/{_COLUMN_ANCHOR_SEGMENT}/{column_index}/{column_label}"
                    ),
                    island_id=FINANCIALS_ISLAND_ID,
                    table_key=context.key.value,
                    row_label=label,
                    column_label=column_label,
                    retrieved_at=context.retrieved_at,
                    first_seen_at=context.retrieved_at,
                ),
            )
        )
    return tuple(cells), (), alignment


def _rows(
    *,
    raw_rows: Any,
    context: _RowBuildContext,
    parent_labels: tuple[str, ...] = (),
) -> tuple[TijoriTableRow, ...]:
    """Flatten Tijori's nested rows while keeping parent path and depth."""
    depth = len(parent_labels)
    if depth > MAX_SUB_SECTION_DEPTH:
        raise TijoriTableDepthError(
            f"tijori table {context.key.value!r} nests sub_section deeper than "
            f"{MAX_SUB_SECTION_DEPTH} levels at {ROW_KEY_SEPARATOR.join(parent_labels)!r}"
        )
    if not isinstance(raw_rows, list) or not raw_rows:
        raise TijoriTableSchemaError(
            f"tijori table {context.key.value!r} data must be a non-empty row list"
        )
    rows: list[TijoriTableRow] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise TijoriTableSchemaError(
                f"tijori table {context.key.value!r} contains a non-object row"
            )
        label = raw_row.get(_ROW_LABEL_FIELD)
        if not isinstance(label, str) or not label.strip():
            raise TijoriTableSchemaError(
                f"tijori table {context.key.value!r} row name must be a non-empty string"
            )
        field_id = _field_id(raw_row.get(_ROW_FIELD_ID_FIELD))
        row_key = ROW_KEY_SEPARATOR.join((*parent_labels, label))
        cells, unaligned_raw_values, alignment = _row_payload(
            raw_values=raw_row.get(_ROW_VALUES_FIELD),
            context=context,
            row_key=row_key,
            label=label,
        )
        rows.append(
            TijoriTableRow(
                row_key=row_key,
                label=label,
                field_id=field_id,
                parent_labels=parent_labels,
                depth=depth,
                alignment=alignment,
                cells=cells,
                unaligned_raw_values=unaligned_raw_values,
            )
        )
        raw_subsections = raw_row.get(_SUB_SECTION_FIELD)
        if raw_subsections is None or raw_subsections in _LEAF_SUB_SECTIONS:
            continue
        if not isinstance(raw_subsections, list):
            raise TijoriTableSchemaError(
                f"tijori table {context.key.value!r} row {row_key!r} sub_section must be a "
                f"list, an empty string, or null"
            )
        rows.extend(
            _rows(
                raw_rows=raw_subsections,
                context=context,
                parent_labels=(*parent_labels, label),
            )
        )
    return tuple(rows)


def _null_table_keys(tables: dict[str, Any]) -> tuple[str, ...]:
    """Record supported keys the page ships as null — not offered for this issuer.

    A standalone-only company publishes every consolidated key as JSON null.
    """
    null_keys = tuple(
        sorted(
            table_key.value
            for table_key in TijoriTableKey
            if table_key.value in tables and tables[table_key.value] is None
        )
    )
    if null_keys:
        _LOGGER.info("tijori_tables_not_offered", null_table_keys=null_keys)
    return null_keys


def _present_table_keys(tables: dict[str, Any]) -> tuple[TijoriTableKey, ...]:
    """Select the supported keys that actually carry a table body."""
    return tuple(
        table_key
        for table_key in TijoriTableKey
        if table_key.value in tables and tables[table_key.value] is not None
    )


def _unknown_table_keys(tables: dict[str, Any]) -> tuple[str, ...]:
    """Record island keys outside the published schema as non-fatal drift."""
    supported = {table_key.value for table_key in TijoriTableKey}
    unknown = tuple(sorted(str(raw_key) for raw_key in tables if str(raw_key) not in supported))
    if unknown:
        _LOGGER.warning("tijori_financials_island_key_drift", unknown_keys=unknown)
    return unknown


def _reject_duplicate_row_keys(rows: tuple[TijoriTableRow, ...], table_key: TijoriTableKey) -> None:
    """Fail loudly when two rows would share one address.

    A colliding key makes every downstream selection ambiguous, so it is fatal
    rather than silently disambiguated by position.
    """
    collisions = sorted(
        row_key for row_key, count in Counter(row.row_key for row in rows).items() if count > 1
    )
    if collisions:
        raise TijoriTableSchemaError(
            f"tijori table {table_key.value!r} has duplicate row keys: {', '.join(collisions)}"
        )


def _build_table(
    *,
    tables: dict[str, Any],
    table_key: TijoriTableKey,
    metadata: TijoriTableMetadata,
) -> TijoriTable:
    """Build one table from raw island data that is already known to exist."""
    table = _as_object(tables[table_key.value], f"{FINANCIALS_ISLAND_ID}.{table_key.value}")
    unmodeled_fields = tuple(sorted(set(table) - _KNOWN_TABLE_FIELDS))
    if unmodeled_fields:
        _LOGGER.warning(
            "tijori_table_field_drift",
            table=table_key.value,
            unmodeled_fields=unmodeled_fields,
        )
    column_labels = _period_labels(table.get(_REPORT_DATES_FIELD), table_key)
    raw_footer = table.get(_TABLE_FOOTER_FIELD)
    context = _RowBuildContext(
        key=table_key,
        column_labels=column_labels,
        content_sha256=metadata.file_sha256,
        source_url=metadata.source_url,
        retrieved_at=metadata.retrieved_at,
    )
    rows = _rows(raw_rows=table.get(_DATA_FIELD), context=context)
    _reject_duplicate_row_keys(rows, table_key)
    return TijoriTable(
        key=table_key,
        scope=_TABLE_SCOPES[table_key],
        column_period_labels=column_labels,
        comparative_period_labels=_optional_labels(
            table.get(_REPORT_DATES_YOY_FIELD), key=table_key, field=_REPORT_DATES_YOY_FIELD
        ),
        skipped_period_labels=_optional_labels(
            table.get(_SKIP_REPORT_DATES_FIELD), key=table_key, field=_SKIP_REPORT_DATES_FIELD
        ),
        table_footer_json=None if raw_footer is None else raw_json(raw_footer),
        rows=rows,
        cardinality_mismatch_rows=tuple(row.row_key for row in rows if row.unaligned_raw_values),
        left_anchored_rows=tuple(
            row.row_key
            for row in rows
            if row.alignment is TijoriRowAlignment.LEFT_ANCHORED_TRAILING_MISSING
        ),
        metadata=metadata,
    )


def build_tijori_table(
    *,
    financials: Any,
    financials_locks: Any,
    plan_details: Any,
    key: str,
    content_sha256: str,
    source_url: str,
    retrieved_at: datetime,
    slug: str,
    symbol: str,
    company_id: int,
) -> TijoriTable:
    """Build the one requested table; only that key is validated strictly."""
    table_key = parse_table_key(key)
    tables = _as_object(financials, FINANCIALS_ISLAND_ID)
    if table_key.value not in tables:
        raise TijoriTableAbsentError(
            f"Tijori financial table {table_key.value!r} is absent from {FINANCIALS_ISLAND_ID}"
        )
    if tables[table_key.value] is None:
        raise TijoriTableAbsentError(
            f"Tijori financial table {table_key.value!r} is present but null in "
            f"{FINANCIALS_ISLAND_ID}: not offered for this company"
        )
    metadata = TijoriTableMetadata(
        slug=slug,
        symbol=symbol,
        company_id=company_id,
        source_url=source_url,
        file_sha256=content_sha256,
        retrieved_at=retrieved_at,
        access=build_page_access(financials_locks=financials_locks, plan_details=plan_details),
        observed_unknown_table_keys=_unknown_table_keys(tables),
        null_table_keys=_null_table_keys(tables),
    )
    return _build_table(tables=tables, table_key=table_key, metadata=metadata)


def build_all_tijori_tables(
    *,
    financials: Any,
    financials_locks: Any,
    plan_details: Any,
    content_sha256: str,
    source_url: str,
    retrieved_at: datetime,
    slug: str,
    symbol: str,
    company_id: int,
) -> tuple[TijoriTable, ...]:
    """Build every published table present on the page, in published key order."""
    tables = _as_object(financials, FINANCIALS_ISLAND_ID)
    present_keys = _present_table_keys(tables)
    if not present_keys:
        observed = ", ".join(sorted(str(raw_key) for raw_key in tables)) or "none"
        raise TijoriTablesAbsentError(
            f"tijori {FINANCIALS_ISLAND_ID} carries no supported financial table; "
            f"observed keys: {observed}"
        )
    metadata = TijoriTableMetadata(
        slug=slug,
        symbol=symbol,
        company_id=company_id,
        source_url=source_url,
        file_sha256=content_sha256,
        retrieved_at=retrieved_at,
        access=build_page_access(financials_locks=financials_locks, plan_details=plan_details),
        observed_unknown_table_keys=_unknown_table_keys(tables),
        null_table_keys=_null_table_keys(tables),
    )
    return tuple(
        _build_table(tables=tables, table_key=table_key, metadata=metadata)
        for table_key in present_keys
    )
