"""Vendor shareholding trees to node and cell occurrences (plan D8 Task 6, R11).

Each vendor node emits one *node* occurrence (no value: label, parent, label path, depth,
periodicity, offered periods) and one *cell* occurrence per printed cell. A printed dash is a
cell with its marker and no value; an unoffered period has no cell; an empty Screener bucket has
no holder. Nothing is fabricated, deduplicated or zero-filled. Only cells carry
``statement_family``, so nodes stay ``UNMAPPED`` diagnostics. Only Mar, Jun, Sep and Dec labels
have an instant (R4), so a mapped cell of another month is ``PERIOD_AMBIGUOUS``. Identity:
Screener page (and drill-down URL) company id, Tijori heading ``comp_id``, Upstox route ISIN;
the API layer binds ``security_isin``. Upstox numerals declare no precision.
"""

from __future__ import annotations

import calendar
import json
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from functools import partial
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, StatementFamily
from fundamentals.contracts.evidence import CaptureReference, Occurrence
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.contracts.source_catalog import (
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
)
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.vendor_ingest import (
    VendorExtraction,
    VendorExtractionError,
    json_occurrence,
    month_period,
)
from fundamentals.ingest.screener_company_artifacts import ShareholdingTable
from fundamentals.ingest.screener_company_models import (
    SET_ATTRIBUTES_KEY,
    InvestorHook,
    Periodicity,
)
from fundamentals.ingest.screener_financials_models import Unit
from fundamentals.ingest.screener_session_models import IdentityAmbiguousError, ScreenerSessionError
from fundamentals.ingest.screener_session_page import parse_document, read_identity
from fundamentals.ingest.screener_shareholding import (
    read_investor_bucket,
    read_shareholding_table,
)
from fundamentals.ingest.tijori_shareholding import (
    TijoriShareholdingIdentityError,
    build_tijori_shareholding,
)
from fundamentals.ingest.tijori_shareholding_table import TijoriShareholdingSchemaError
from fundamentals.ingest.tijori_tables import TijoriParseError
from fundamentals.ingest.upstox_retention import PATH_PARAMETER

SCREENER_VERSION = "screener-shp-v1"
TIJORI_VERSION = "tijori-shp-v1"
UPSTOX_VERSION = "upstox-shp-v1"
SCHEMA = {
    SCREENER_SHAREHOLDING: "screener-shareholding-tree-v1",
    SCREENER_INVESTORS: "screener-investors-tree-v1",
    TIJORI_SHAREHOLDING: "tijori-shareholding-tree-v1",
    UPSTOX_SHAREHOLDING: "upstox-share-holdings-v1",
}
NODE, CELL = "NODE", "CELL"
BASIS = Basis.STANDALONE  # R4: a shareholding package is stored STANDALONE
UPSTOX_CATEGORIES = ("fii", "mutual_funds", "other_dii", "promoters", "retail_and_other")
_QUARTERLY = Periodicity.QUARTERLY.value
_SCREENER = SCREENER_SHAREHOLDING[0]
_FAMILY = StatementFamily.SHAREHOLDING.value  # on cells only: a node never matches a selector
_QUARTER_ENDS = (3, 6, 9, 12)
_SCREENER_MONTH, _TIJORI_MONTH = "%b %Y", "%b'%y"
_UNKNOWN = {"completeness": "UNKNOWN", "threshold_pct": None, "threshold_denominator": None}
_THRESHOLDED = {
    "completeness": "THRESHOLDED",
    "threshold_pct": 1,
    "threshold_inclusive": False,
    "threshold_denominator": "TOTAL_SHARES",
    "completeness_reason": "Screener names holders 'who hold over 1% shares' (R/reference/gen-1/"
    "04.bin l.349, d8-probe.md §11.4); no holder of this list is at or below 1 in any period",
}
_SCREENER_UNMET = "a holder of this list is at or below 1, so Screener's stated threshold fails"
_TIJORI_REASON = "no retained Tijori text states a list threshold (d8-probe.md §11.4; R11)"
_FOREIGN = "{what} names company {seen}, not the bound {expected}"
_DEEPER = "holder {holder!r} carries key {key!r}: an unread deeper level (R11 Depth)"
_SHAPE = "Upstox share-holdings body is not the documented shape: {why}"

Cells = tuple[tuple[str, str | None, Decimal | None], ...]  # (period label, lexeme, value)


class ShareholdingBinding(BaseModel):
    """The API layer's binding for one capture: the share class resolved at the instant
    (``None`` leaves every occurrence keyless), the request URL, and the generation's Screener
    page, which a drill-down is held to."""

    model_config = ConfigDict(frozen=True)
    symbol: str
    security_isin: str | None
    screener_company_id: int
    tijori_slug: str
    tijori_company_id: int
    url: str = ""
    page: bytes = b""


class _Node(BaseModel):
    """One vendor node and its printed cells."""

    model_config = ConfigDict(frozen=True)
    path: tuple[str, ...]
    source_node_id: str
    periodicity: str = _QUARTERLY
    cells: Cells
    raw_unit: str = "percent"
    anchor: dict[str, Any]
    disclosure: dict[str, Any] = Field(default_factory=dict)


_Read = tuple[list[_Node], str, tuple[str, ...]]  # nodes, verified issuer, partial reasons


def extract_vendor_shareholding(
    body: bytes,
    *,
    capture: CaptureReference,
    record: CaptureRecord,
    extractor_version: str,
    binding: ShareholdingBinding,
) -> VendorExtraction:
    """One registered Screener page or drill-down, Tijori page or Upstox response as its tree."""
    pair = (capture.source_id, capture.surface)
    reader = {
        SCREENER_SHAREHOLDING: _screener_page,
        SCREENER_INVESTORS: _screener_bucket,
        TIJORI_SHAREHOLDING: _tijori,
        UPSTOX_SHAREHOLDING: _upstox,
    }[pair]
    nodes, issuer, reasons = reader(body, capture, record, binding)
    month_format = _TIJORI_MONTH if pair == TIJORI_SHAREHOLDING else _SCREENER_MONTH
    occurrences = [
        occurrence
        for node in nodes
        for occurrence in _occurrences(node, capture, extractor_version, binding, month_format)
    ]
    return VendorExtraction(
        occurrences=tuple(occurrences),
        outcome=ExtractionOutcome.PARTIAL if reasons else ExtractionOutcome.COMPLETE,
        reasons=reasons,
        issuer=issuer,
        basis=BASIS,
        extraction_context_sha256=input_digest(
            {
                "surface": capture.surface,
                "capture_sha256": capture.blob_sha256,
                "binding": binding.model_dump(mode="json", exclude={"page"}),
            }
        ),
    )


def _screener_page(
    body: bytes, capture: CaptureReference, record: CaptureRecord, binding: ShareholdingBinding
) -> _Read:
    """Every row of both Shareholding Pattern tables of one bound Screener page."""
    tables = _screener_tables(body, binding.screener_company_id, record.retrieved_at)
    nodes = [
        _Node(
            path=(row.label,),
            source_node_id=row.bucket or row.label,
            periodicity=table.periodicity.value,
            cells=_screener_cells(table, row.cells),
            raw_unit="count" if row.unit is Unit.COUNT else "percent",
            anchor={"table_key": table.table_id, "row_position": row.position},
            disclosure={"unit_statement": table.unit_statement},
        )
        for table in tables
        for row in table.rows
    ]
    reasons = tuple(
        f"{table.table_id}: {row.label} could not be aligned"
        for table in tables
        for row in table.quarantined
    )
    return nodes, binding.symbol, reasons


def _screener_bucket(
    body: bytes, capture: CaptureReference, record: CaptureRecord, binding: ShareholdingBinding
) -> _Read:
    """Every holder of one drill-down, held to the page row it expands (level 2)."""
    parts = urlsplit(binding.url).path.strip("/").split("/")  # api/3/<id>/investors/<b>/<p>
    if len(parts) != 6 or parts[2] != str(binding.screener_company_id):
        raise VendorExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED,
            _FOREIGN.format(
                what=binding.url, seen=parts[2:3], expected=binding.screener_company_id
            ),
        )
    bucket, periodicity = parts[4], Periodicity(parts[5])
    _refuse_deeper(body)
    tables = _screener_tables(binding.page, binding.screener_company_id, record.retrieved_at)
    table = next((table for table in tables if table.periodicity is periodicity), None)
    row = next((row for row in table.rows if row.bucket == bucket), None) if table else None
    hook = InvestorHook(bucket=bucket, periodicity=periodicity, row_label=row.label if row else "")
    try:
        parsed = read_investor_bucket(
            body,
            hook=hook,
            table=table,
            url=binding.url,
            document_id=capture.capture_id,
            body_sha256=capture.blob_sha256,
            source_id=capture.source_id,
            retrieved_at=record.retrieved_at,
        )
    except ScreenerSessionError as error:
        raise VendorExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error
    assert table is not None and row is not None  # the reader refuses a bucket without its row
    values = [cell.value for holder in parsed.holders for cell in holder.cells]
    stated = all(value is not None and value > 1 for value in values)
    listed = _THRESHOLDED if stated else {**_UNKNOWN, "completeness_reason": _SCREENER_UNMET}
    nodes = [
        _Node(
            path=(row.label, holder.holder),
            source_node_id=holder.holder,
            periodicity=periodicity.value,
            cells=_screener_cells(table, holder.cells),
            anchor={
                "table_key": f"investors:{bucket}:{periodicity.value}",
                "holder": holder.holder,
            },
            disclosure={**listed, "bucket": bucket, "person_url": holder.person_url},
        )
        for holder in parsed.holders
    ]
    return nodes, binding.symbol, ()


def _tijori(
    body: bytes, capture: CaptureReference, record: CaptureRecord, binding: ShareholdingBinding
) -> _Read:
    """Every row of Tijori's detailed shareholding tree, at any depth its parser reads."""
    try:
        table = build_tijori_shareholding(
            body,
            slug=binding.tijori_slug,
            expected_symbol=binding.symbol,
            expected_company_id=binding.tijori_company_id,
            source_url=binding.url,
            retrieved_at=record.retrieved_at,
        )
    except TijoriShareholdingIdentityError as error:
        raise VendorExtractionError(ExtractionOutcome.IDENTITY_REJECTED, str(error)) from error
    except TijoriShareholdingSchemaError as error:
        raise VendorExtractionError(ExtractionOutcome.UNSUPPORTED_SCHEMA, str(error)) from error
    except TijoriParseError as error:
        raise VendorExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error
    nodes = [
        _Node(
            path=(*row.parent_labels, row.label),
            source_node_id=row.source_node_id,
            cells=tuple(
                (label, cell.raw_text, cell.value)
                for label, cell in zip(table.column_period_labels, row.cells, strict=True)
            ),
            anchor={"table_key": table.metadata.table_id, "row_key": row.row_key},
            disclosure={
                **_UNKNOWN,
                "completeness_reason": _TIJORI_REASON,
                "unit": table.unit_label,
            },
        )
        for row in table.rows
    ]
    reasons = tuple(f"{key} could not be aligned" for key in table.cardinality_mismatch_rows)
    return nodes, binding.symbol, reasons


def _upstox(
    body: bytes, capture: CaptureReference, record: CaptureRecord, binding: ShareholdingBinding
) -> _Read:
    """The five documented categories of one Upstox share-holdings response, read by key."""
    params = {item.name: item.value for item in record.request.parameters}
    isin = params[PATH_PARAMETER].split("/")[3]  # /v2/fundamentals/{isin}/share-holdings
    document = _strict_json(body)
    if not isinstance(document, dict) or set(document) != {"status", "data"}:
        raise _shape("the envelope is not exactly status and data")
    if document["status"] != "success" or not isinstance(document["data"], list):
        raise _shape(f"status {document['status']!r}, or data is not a list")
    nodes = []
    for item in document["data"]:
        if not isinstance(item, dict) or set(item) != {"category", "history"}:
            raise _shape("a data entry is not exactly category and history")
        history = item["history"]
        if not isinstance(history, list) or not all(map(_point, history)):
            raise _shape(f"{item['category']!r} history is not period and numeral pairs")
        if len({point["period"] for point in history}) != len(history):
            raise _shape(f"{item['category']!r} repeats a period")
        cells = tuple((p["period"], str(p["value"]), Decimal(p["value"])) for p in history)
        category = str(item["category"])
        nodes.append(_Node(path=(category,), source_node_id=category, cells=cells, anchor={}))
    categories = sorted(node.source_node_id for node in nodes)
    if tuple(categories) != UPSTOX_CATEGORIES:
        raise _shape(f"categories {categories} are not the five documented keys, once each")
    return nodes, isin, ()


def _point(point: object) -> bool:
    """A history entry is exactly a string period and a JSON numeral."""
    return (
        isinstance(point, dict)
        and set(point) == {"period", "value"}
        and isinstance(point["period"], str)
        and isinstance(point["value"], _Number)
    )


class _Number(str):
    """A JSON numeral kept as its exact lexeme."""


def _screener_tables(
    page: bytes, company_id: int, retrieved_at: datetime
) -> list[ShareholdingTable]:
    """The Shareholding Pattern tables of a page proven to be ``company_id``'s."""
    try:
        root = parse_document(page.decode("utf-8"))
        seen = read_identity(root)[0]
        read = partial(read_shareholding_table, source_id=_SCREENER, retrieved_at=retrieved_at)
        tables = [read(root, item, file_sha256=sha256(page).hexdigest()) for item in Periodicity]
    except IdentityAmbiguousError as error:
        raise VendorExtractionError(ExtractionOutcome.IDENTITY_REJECTED, str(error)) from error
    except (ScreenerSessionError, UnicodeDecodeError) as error:
        raise VendorExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error
    if seen != company_id:
        raise VendorExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED,
            _FOREIGN.format(what="the Screener page", seen=seen, expected=company_id),
        )
    return [table for table in tables if table is not None]


def _screener_cells(table: ShareholdingTable, cells: Iterable[Any]) -> Cells:
    """Screener cells as ``(period label, lexeme, value)`` under the table's own headers."""
    return tuple(
        (table.periods[cell.period_index].label, cell.raw_text, cell.value) for cell in cells
    )


def _refuse_deeper(body: bytes) -> None:
    """A holder key that is neither a ``Mon YYYY`` period nor ``setAttributes`` is a level the
    reader cannot see, so the body is refused rather than read short (R11 Depth)."""
    try:
        holders = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return  # the parser refuses it with its own reason
    for holder, values in holders.items() if isinstance(holders, dict) else ():
        for key in values if isinstance(values, dict) else ():
            if key != SET_ATTRIBUTES_KEY and month_period(key, 3) is None:
                raise VendorExtractionError(
                    ExtractionOutcome.UNSUPPORTED_SCHEMA, _DEEPER.format(holder=holder, key=key)
                )


def _strict_json(body: bytes) -> Any:
    """Decode JSON keeping numerals as lexemes and refusing a repeated key."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        if len({key for key, _ in items}) != len(items):
            raise _shape(f"an object repeats a key among {[key for key, _ in items]}")
        return dict(items)

    try:
        return json.loads(body, object_pairs_hook=pairs, parse_float=_Number, parse_int=_Number)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VendorExtractionError(ExtractionOutcome.PARSE_FAILED, str(error)) from error


def _shape(why: str) -> VendorExtractionError:
    """An Upstox body off its documented shape."""
    return VendorExtractionError(ExtractionOutcome.UNSUPPORTED_SCHEMA, _SHAPE.format(why=why))


def _instant(label: str, month_format: str) -> PeriodInterval | None:
    """A quarter-end month label as its month-end instant; any other month has none (R4)."""
    try:
        month = datetime.strptime(label.strip(), month_format).date()
    except ValueError:
        return None
    if month.month not in _QUARTER_ENDS:
        return None
    return PeriodInterval.at(month.replace(day=calendar.monthrange(month.year, month.month)[1]))


def _occurrences(
    node: _Node,
    capture: CaptureReference,
    extractor_version: str,
    binding: ShareholdingBinding,
    month_format: str,
) -> list[Occurrence]:
    """The node occurrence, then one cell occurrence per printed cell."""
    schema = SCHEMA[(capture.source_id, capture.surface)]
    displayed = (capture.source_id, capture.surface) != UPSTOX_SHAREHOLDING
    context = {
        "schema_identity": schema,
        "basis": BASIS.value,
        "label": node.path[-1],
        "parent": node.path[-2] if len(node.path) > 1 else None,
        "path": list(node.path),
        "depth": len(node.path),
        "source_node_id": node.source_node_id,
        "periodicity": node.periodicity,
        "periods": [label for label, _, _ in node.cells],
        "security_isin": binding.security_isin,
    }
    anchor = {"anchor_type": schema, "node": list(node.path), **node.anchor}
    items: list[tuple[str, str | None, str | None, Decimal | None]] = [(NODE, None, None, None)]
    items += [(CELL, label, lexeme, value) for label, lexeme, value in node.cells]
    return [
        json_occurrence(
            capture,
            extractor_version=extractor_version,
            label=node.path[-1],
            lexeme=lexeme,
            value=value,
            raw_unit=node.raw_unit,
            raw_scale=0,
            period=_instant(label, month_format) if label else None,
            native_context=context
            | {"kind": kind}
            | ({"statement_family": _FAMILY, "period_label": label} if label else {}),
            anchor=anchor | {"kind": kind, "column_label": label},
            disclosure=node.disclosure,
            declared_precision=len((lexeme or "").rstrip("%").partition(".")[2])
            if displayed and value is not None
            else None,
        )
        for kind, label, lexeme, value in items
    ]
