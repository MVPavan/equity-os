"""Typed contracts for Tijori's detailed shareholding table.

Shareholding is the one verified Tijori company surface whose data is
server-rendered HTML rather than a JSON island, so its cells anchor as
``SourceAnchorType.HTML_TABLE``. The page still carries Django JSON islands for
authentication and identity, and those gates run before any row is parsed.

The page carries a second, differently-shaped payload beside the table: the
aggregate break-up charts, declared as JavaScript array literals in inline
scripts. Their reader lives in
:mod:`fundamentals.ingest.tijori_shareholding_breakup` and they reach the
artifact as an additive ``breakups`` field, so a drifted chart script can never
degrade the detailed table.

Identity FACT (owner capture, 2026-08-25): the shareholding page publishes NO
identity island. Its islands are ``is_landing_page``, ``peersList``,
``alerts_limit_exceeded``, ``metrics``, ``plan_details``, ``pagesremain`` and
``is_auth``; ``metrics`` is a chart-metric catalogue carrying no company, and
``peersList`` names peers, so "the first entry is the subject company" is an
assumption this module refuses to make.

The page's one deterministic marker is the ``comp_id`` attribute on its ``<h1>``
heading, which is Tijori's numeric company id. Identity is therefore REQUIRED to
pass ``comp_id`` against the watchlist's configured ``tijori_company_id``; the
page renders the heading twice, and both must agree. Every island in
``IDENTITY_ISLAND_IDS`` that does carry a ``symbol`` is checked too — none does
today, but the check costs nothing and hardens against page changes.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_page import collect_islands, decode_document
from fundamentals.ingest.tijori_shareholding_breakup import (
    TijoriShareholdingBreakup as TijoriShareholdingBreakup,
)
from fundamentals.ingest.tijori_shareholding_breakup import (
    TijoriShareholdingBreakupEntry as TijoriShareholdingBreakupEntry,
)
from fundamentals.ingest.tijori_shareholding_breakup import (
    TijoriShareholdingBreakupError as TijoriShareholdingBreakupError,
)
from fundamentals.ingest.tijori_shareholding_breakup import (
    build_shareholding_breakups,
)
from fundamentals.ingest.tijori_shareholding_table import (
    SHAREHOLDING_TABLE_ELEMENT_ID as SHAREHOLDING_TABLE_ELEMENT_ID,
)
from fundamentals.ingest.tijori_shareholding_table import (
    SHAREHOLDING_UNIT_LABEL,
    _RawRow,
    _select_shareholding_table,
)
from fundamentals.ingest.tijori_shareholding_table import (
    TijoriShareholdingAbsentError as TijoriShareholdingAbsentError,
)
from fundamentals.ingest.tijori_shareholding_table import (
    TijoriShareholdingAmbiguousError as TijoriShareholdingAmbiguousError,
)
from fundamentals.ingest.tijori_shareholding_table import (
    TijoriShareholdingSchemaError as TijoriShareholdingSchemaError,
)
from fundamentals.ingest.tijori_tables import (
    PLAN_DETAILS_ISLAND_ID,
    ROW_KEY_SEPARATOR,
    TIJORI_SOURCE_ID,
    TijoriParseError,
    TijoriTableAccessMetadata,
    build_page_access,
    decimal_from_text,
)

_LOGGER = structlog.get_logger(__name__)

# The provenance anchor discriminator (our name for the table).
SHAREHOLDING_TABLE_ID = "detailed_shareholding"
SHAREHOLDING_PAGE_LABEL = "shareholding"
MAX_SHAREHOLDING_DEPTH = 8
ROOT_PARENT_ID = "1"

IS_AUTH_ISLAND_ID = "is_auth"
COMPANY_DETAILS_ISLAND_ID = "company_details"
COMPANY_DETAILS_DATA_ISLAND_ID = "company_details_data"
METRICS_ISLAND_ID = "metrics"
# Tijori names its identity island differently per surface: ``company_details``
# on financials, ``company_details_data`` on overview. The shareholding page
# carries neither, so these are supplementary: any candidate that IS present and
# carries a symbol must agree, but the heading comp_id is the required marker.
IDENTITY_ISLAND_IDS = (
    COMPANY_DETAILS_ISLAND_ID,
    COMPANY_DETAILS_DATA_ISLAND_ID,
    METRICS_ISLAND_ID,
)

_REQUIRED_ISLAND_IDS = (IS_AUTH_ISLAND_ID,)
_OPTIONAL_ISLAND_IDS = IDENTITY_ISLAND_IDS + (PLAN_DETAILS_ISLAND_ID,)

_SYMBOL_FIELD = "symbol"
_COMPANY_ID_FIELD = "company_id"

_HEADING_TAG = "h1"
_HEADING_COMPANY_ID_ATTRIBUTE = "comp_id"


# Cell anchors carry the positional column index so provenance stays unique even
# when the page repeats a quarter label.
_COLUMN_ANCHOR_SEGMENT = "col"


class TijoriShareholdingDepthError(TijoriShareholdingSchemaError):
    """Row nesting exceeded the supported shareholding recursion bound."""


class TijoriShareholdingIdentityError(TijoriParseError):
    """The shareholding page carries no usable identity marker, or it disagrees."""


class TijoriShareholdingRowSelectionError(TijoriParseError):
    """A row selector matched no row, or matched more than one row."""


class TijoriShareholdingCell(BaseModel):
    """One rendered shareholding cell: its lexeme plus its numeric reading."""

    model_config = ConfigDict(frozen=True)

    value: Decimal | None
    raw_text: str
    provenance: Provenance


class TijoriShareholdingRow(BaseModel):
    """One shareholding row addressed by its parent-qualified label path.

    ``source_node_id``/``source_parent_id`` preserve Tijori's ``myid`` and
    ``data-parent`` attributes verbatim: they are the page's machine-readable
    nesting, kept as source metadata rather than used as the address. A
    ``source_node_id`` is unique only within one parent — a reclassified
    shareholder is listed under two category parents — so the pair, not the bare
    id, identifies a node.

    ``depth`` is ``len(parent_labels)`` (roots are 0), matching
    :class:`~fundamentals.ingest.tijori_tables.TijoriTableRow`. Tijori's own
    one-based ``rowN`` class is preserved separately as ``source_depth``.

    A row whose value count disagrees with the column count is quarantined:
    ``cells`` is empty and the raw lexemes survive in ``unaligned_raw_values``.
    """

    model_config = ConfigDict(frozen=True)

    row_key: str
    label: str
    source_node_id: str
    source_parent_id: str
    parent_labels: tuple[str, ...]
    depth: int
    source_depth: int
    cells: tuple[TijoriShareholdingCell, ...]
    unaligned_raw_values: tuple[str, ...] = ()


class TijoriShareholdingMetadata(BaseModel):
    """Response identity and acquisition metadata for one shareholding page.

    ``company_id`` is the heading ``comp_id`` that was matched against the
    configured ``tijori_company_id`` — the page's required identity marker.
    ``identity_island_ids`` records any island that additionally corroborated it,
    and is empty on today's page because none publishes an identity.
    """

    model_config = ConfigDict(frozen=True)

    slug: str
    symbol: str
    company_id: int
    source_url: str
    file_sha256: str
    retrieved_at: datetime
    table_id: str = SHAREHOLDING_TABLE_ID
    identity_island_ids: tuple[str, ...]
    access: TijoriTableAccessMetadata


class TijoriShareholding(BaseModel):
    """The immutable detailed shareholding table in source row order.

    ``breakups`` carries the page's aggregate break-up charts, which the
    template renders as inline scripts rather than as table rows. They are a
    different acquisition from the table beside them — a different location, a
    different reader, and their own per-chart outcome — so they are an additive
    field here rather than rows folded into ``rows``, and an unreadable chart
    never affects the table.
    """

    model_config = ConfigDict(frozen=True)

    unit_label: str
    column_period_labels: tuple[str, ...]
    rows: tuple[TijoriShareholdingRow, ...]
    cardinality_mismatch_rows: tuple[str, ...] = ()
    breakups: tuple[TijoriShareholdingBreakup, ...] = ()
    metadata: TijoriShareholdingMetadata

    def row(self, selector: str) -> TijoriShareholdingRow:
        """Select one row by its row key, or by Tijori's node id as a convenience."""
        matches = tuple(row for row in self.rows if row.row_key == selector) or tuple(
            row for row in self.rows if row.source_node_id == selector
        )
        if not matches:
            raise TijoriShareholdingRowSelectionError(
                f"tijori shareholding has no row matching {selector!r}"
            )
        if len(matches) > 1:
            candidates = ", ".join(row.row_key for row in matches)
            raise TijoriShareholdingRowSelectionError(
                f"tijori shareholding row selector {selector!r} is ambiguous; "
                f"candidates: {candidates}"
            )
        return matches[0]


class _RowBuildContext(BaseModel):
    """Invariant inputs shared by every row built for the shareholding table."""

    model_config = ConfigDict(frozen=True)

    column_labels: tuple[str, ...]
    content_sha256: str
    source_url: str
    retrieved_at: datetime


class _CompanyHeadingCollector(HTMLParser):
    """Collect the ``comp_id`` attribute of every ``<h1>`` that declares one.

    The page renders its company heading twice. Both are collected verbatim —
    including a value that is not an integer — so the gate can name exactly what
    it found instead of silently ignoring an unreadable marker.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.company_ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record one heading's declared company id."""
        if tag != _HEADING_TAG:
            return
        raw = dict(attrs).get(_HEADING_COMPANY_ID_ATTRIBUTE)
        if raw is not None:
            self.company_ids.append(raw.strip())


def _verified_heading_company_id(document: str, expected_company_id: int) -> int:
    """Match the page heading's ``comp_id`` against the configured company id.

    This is the shareholding page's only deterministic identity marker, so a
    missing, unreadable, self-contradicting, or mismatched value is fatal.
    """
    collector = _CompanyHeadingCollector()
    collector.feed(document)
    collector.close()
    declared = collector.company_ids
    if not declared:
        raise TijoriShareholdingIdentityError(
            f"tijori shareholding page publishes no <{_HEADING_TAG} "
            f"{_HEADING_COMPANY_ID_ATTRIBUTE}> marker, so the response cannot be bound to "
            f"company ID {expected_company_id}"
        )
    distinct = sorted(set(declared))
    if len(distinct) > 1:
        found = ", ".join(repr(value) for value in distinct)
        raise TijoriShareholdingIdentityError(
            f"tijori shareholding page publishes disagreeing <{_HEADING_TAG} "
            f"{_HEADING_COMPANY_ID_ATTRIBUTE}> values: {found}"
        )
    marker = distinct[0]
    if not marker.isdigit():
        raise TijoriShareholdingIdentityError(
            f"tijori shareholding <{_HEADING_TAG} {_HEADING_COMPANY_ID_ATTRIBUTE}> "
            f"is not a company ID: {marker!r}"
        )
    company_id = int(marker)
    if company_id != expected_company_id:
        raise TijoriShareholdingIdentityError(
            "tijori shareholding identity mismatch: "
            f"requested company ID {expected_company_id}, page <{_HEADING_TAG} "
            f"{_HEADING_COMPANY_ID_ATTRIBUTE}> {company_id}"
        )
    return company_id


def _identity_symbol(island: Any) -> tuple[str | None, int | None]:
    """Read the symbol and company id one island publishes, if it publishes them."""
    if not isinstance(island, dict):
        return None, None
    raw_symbol = island.get(_SYMBOL_FIELD)
    symbol = raw_symbol.strip() if isinstance(raw_symbol, str) and raw_symbol.strip() else None
    raw_company_id = island.get(_COMPANY_ID_FIELD)
    company_id = (
        raw_company_id
        if isinstance(raw_company_id, int) and not isinstance(raw_company_id, bool)
        else None
    )
    return symbol, company_id


def _verified_supplementary_islands(
    islands: dict[str, Any], *, expected_symbol: str, expected_company_id: int
) -> tuple[str, ...]:
    """Check every island that happens to publish an identity, and name those that did.

    No shareholding island carries one today. Any that appears later must agree
    rather than be ignored, so this is conjunctive with the heading gate — never
    a substitute for it.
    """
    matched: list[str] = []
    for island_id in IDENTITY_ISLAND_IDS:
        symbol, island_company_id = _identity_symbol(islands.get(island_id))
        if symbol is None and island_company_id is None:
            continue
        if symbol is not None and symbol != expected_symbol:
            raise TijoriShareholdingIdentityError(
                "tijori shareholding identity mismatch: "
                f"requested symbol {expected_symbol!r}, island {island_id!r} symbol {symbol!r}"
            )
        if island_company_id is not None and island_company_id != expected_company_id:
            raise TijoriShareholdingIdentityError(
                "tijori shareholding identity mismatch: "
                f"requested company ID {expected_company_id}, island {island_id!r} "
                f"company ID {island_company_id}"
            )
        matched.append(island_id)
    return tuple(matched)


def _row_payload(
    *, raw_values: tuple[str, ...], context: _RowBuildContext, row_key: str, label: str
) -> tuple[tuple[TijoriShareholdingCell, ...], tuple[str, ...]]:
    """Build one row's cells, or quarantine it when its cardinality disagrees.

    A row whose value count differs from the column count cannot be aligned to
    quarters — which end is missing is not determinable from the markup — so it
    yields no cells and keeps its raw lexemes instead.
    """
    if not raw_values:
        return (), ()
    if len(raw_values) != len(context.column_labels):
        _LOGGER.warning(
            "tijori_shareholding_row_cardinality_mismatch",
            row_key=row_key,
            got=len(raw_values),
            expected=len(context.column_labels),
        )
        return (), raw_values
    cells: list[TijoriShareholdingCell] = []
    for column_index, (column_label, raw_text) in enumerate(
        zip(context.column_labels, raw_values, strict=True)
    ):
        cells.append(
            TijoriShareholdingCell(
                value=decimal_from_text(raw_text),
                raw_text=raw_text,
                provenance=Provenance(
                    source_id=TIJORI_SOURCE_ID,
                    file_sha256=context.content_sha256,
                    anchor_type=SourceAnchorType.HTML_TABLE,
                    context_ref=(
                        f"{context.source_url}#{SHAREHOLDING_TABLE_ID}/{row_key}/"
                        f"{_COLUMN_ANCHOR_SEGMENT}/{column_index}/{column_label}"
                    ),
                    table_id=SHAREHOLDING_TABLE_ID,
                    row_path=row_key,
                    row_label=label,
                    column_index=column_index,
                    column_label=column_label,
                    retrieved_at=context.retrieved_at,
                    first_seen_at=context.retrieved_at,
                ),
            )
        )
    return tuple(cells), ()


def _resolve_parent(
    raw_row: _RawRow,
    label_paths: dict[str, tuple[str, ...]],
    source_depths: dict[str, int],
) -> tuple[str, ...]:
    """Resolve one row's parent label path, rejecting broken machine nesting.

    Consistency is checked against Tijori's own one-based ``rowN``, because that
    is what the page declares; the normalized depth is derived afterwards.
    """
    if raw_row.parent_id == ROOT_PARENT_ID:
        if raw_row.source_depth != 1:
            raise TijoriShareholdingSchemaError(
                f"tijori shareholding root row {raw_row.node_id!r} declares depth "
                f"{raw_row.source_depth}, expected 1"
            )
        return ()
    if raw_row.parent_id not in label_paths:
        raise TijoriShareholdingSchemaError(
            f"tijori shareholding row {raw_row.node_id!r} names unknown parent "
            f"{raw_row.parent_id!r}"
        )
    expected_depth = source_depths[raw_row.parent_id] + 1
    if raw_row.source_depth != expected_depth:
        raise TijoriShareholdingSchemaError(
            f"tijori shareholding row {raw_row.node_id!r} declares depth "
            f"{raw_row.source_depth} under parent {raw_row.parent_id!r} at depth "
            f"{source_depths[raw_row.parent_id]}"
        )
    return label_paths[raw_row.parent_id]


def _repeated_node_ids(raw_rows: tuple[_RawRow, ...]) -> frozenset[str]:
    """Find node ids the page reuses, rejecting only those that break the tree.

    FACT (live, 2026-08-25): one shareholder legitimately appears under two
    category parents when it is reclassified across the quarter columns — HFCL
    lists ``RelianceVenturesLimited`` under both Institutions and
    Non-Institutions. Node identity is therefore ``(myid, data-parent)``, and a
    reused ``myid`` is fatal only when some row names it as ``data-parent``,
    because that reference genuinely cannot be resolved to one node.
    """
    repeated = frozenset(
        node_id for node_id, count in Counter(row.node_id for row in raw_rows).items() if count > 1
    )
    if not repeated:
        return repeated
    referencing: dict[str, list[str]] = {}
    for row in raw_rows:
        if row.parent_id in repeated:
            referencing.setdefault(row.parent_id, []).append(row.node_id)
    if referencing:
        detail = "; ".join(
            f"{parent_id!r} referenced by {', '.join(children)}"
            for parent_id, children in sorted(referencing.items())
        )
        raise TijoriShareholdingSchemaError(
            f"tijori shareholding repeats a node id that is used as a parent: {detail}"
        )
    _LOGGER.info("tijori_shareholding_reclassified_nodes", node_ids=sorted(repeated))
    return repeated


def _rows(
    raw_rows: tuple[_RawRow, ...], context: _RowBuildContext
) -> tuple[TijoriShareholdingRow, ...]:
    """Build the shareholding tree in source order from attribute nesting."""
    repeated_ids = _repeated_node_ids(raw_rows)
    label_paths: dict[str, tuple[str, ...]] = {}
    source_depths: dict[str, int] = {}
    placed_nodes: set[tuple[str, str]] = set()
    rows: list[TijoriShareholdingRow] = []
    for raw_row in raw_rows:
        if not raw_row.label:
            raise TijoriShareholdingSchemaError(
                f"tijori shareholding row {raw_row.node_id!r} has an empty display name"
            )
        node = (raw_row.node_id, raw_row.parent_id)
        if node in placed_nodes:
            raise TijoriShareholdingSchemaError(
                f"tijori shareholding repeats node id {raw_row.node_id!r} under one parent "
                f"{raw_row.parent_id!r}"
            )
        placed_nodes.add(node)
        parent_labels = _resolve_parent(raw_row, label_paths, source_depths)
        depth = len(parent_labels)
        if depth > MAX_SHAREHOLDING_DEPTH:
            raise TijoriShareholdingDepthError(
                f"tijori shareholding row {raw_row.node_id!r} nests deeper than "
                f"{MAX_SHAREHOLDING_DEPTH} levels"
            )
        row_key = ROW_KEY_SEPARATOR.join((*parent_labels, raw_row.label))
        cells, unaligned_raw_values = _row_payload(
            raw_values=raw_row.raw_values,
            context=context,
            row_key=row_key,
            label=raw_row.label,
        )
        rows.append(
            TijoriShareholdingRow(
                row_key=row_key,
                label=raw_row.label,
                source_node_id=raw_row.node_id,
                source_parent_id=raw_row.parent_id,
                parent_labels=parent_labels,
                depth=depth,
                source_depth=raw_row.source_depth,
                cells=cells,
                unaligned_raw_values=unaligned_raw_values,
            )
        )
        if raw_row.node_id not in repeated_ids:
            label_paths[raw_row.node_id] = (*parent_labels, raw_row.label)
            source_depths[raw_row.node_id] = raw_row.source_depth
    _reject_duplicate_row_keys(tuple(rows))
    return tuple(rows)


def _reject_duplicate_row_keys(rows: tuple[TijoriShareholdingRow, ...]) -> None:
    """Fail loudly when two rows would share one address."""
    collisions = sorted(
        row_key for row_key, count in Counter(row.row_key for row in rows).items() if count > 1
    )
    if collisions:
        raise TijoriShareholdingSchemaError(
            f"tijori shareholding has duplicate row keys: {', '.join(collisions)}"
        )


def build_tijori_shareholding(
    raw: bytes,
    *,
    slug: str,
    expected_symbol: str,
    expected_company_id: int,
    source_url: str,
    retrieved_at: datetime,
) -> TijoriShareholding:
    """Build the typed detailed shareholding table from one rendered page."""
    document = decode_document(raw, page_label=SHAREHOLDING_PAGE_LABEL)
    islands = collect_islands(
        document,
        required_islands=_REQUIRED_ISLAND_IDS,
        optional_islands=_OPTIONAL_ISLAND_IDS,
    )
    if islands.get(IS_AUTH_ISLAND_ID) is not True:
        raise TijoriParseError("tijori response is not authenticated")
    symbol = expected_symbol.strip()
    company_id = _verified_heading_company_id(document, expected_company_id)
    identity_island_ids = _verified_supplementary_islands(
        islands, expected_symbol=symbol, expected_company_id=company_id
    )
    table = _select_shareholding_table(document)
    context = _RowBuildContext(
        column_labels=table.column_labels,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        source_url=source_url,
        retrieved_at=retrieved_at,
    )
    rows = _rows(table.rows, context)
    if not any(row.cells for row in rows):
        raise TijoriShareholdingSchemaError(
            f"tijori shareholding table carries no aligned cells across {len(rows)} rows "
            f"and {len(table.column_labels)} columns; that is page drift, not data"
        )
    breakups = build_shareholding_breakups(
        document,
        content_sha256=context.content_sha256,
        source_url=source_url,
        retrieved_at=retrieved_at,
    )
    _LOGGER.info(
        "tijori_shareholding_parsed",
        slug=slug,
        company_id=company_id,
        rows=len(rows),
        columns=len(table.column_labels),
        breakups=len(breakups),
        identity_islands=identity_island_ids,
    )
    return TijoriShareholding(
        unit_label=table.unit_label or SHAREHOLDING_UNIT_LABEL,
        column_period_labels=table.column_labels,
        rows=rows,
        cardinality_mismatch_rows=tuple(row.row_key for row in rows if row.unaligned_raw_values),
        breakups=breakups,
        metadata=TijoriShareholdingMetadata(
            slug=slug,
            symbol=symbol,
            company_id=company_id,
            source_url=source_url,
            file_sha256=context.content_sha256,
            retrieved_at=retrieved_at,
            identity_island_ids=identity_island_ids,
            access=build_page_access(
                financials_locks=None, plan_details=islands.get(PLAN_DETAILS_ISLAND_ID)
            ),
        ),
    )
