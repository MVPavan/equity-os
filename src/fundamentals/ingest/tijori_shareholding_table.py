"""Rendered-HTML collection for Tijori's detailed shareholding table.

The shareholding surface is server-rendered markup rather than a JSON island,
so this module owns the DOM layer: reducing every ``<table>`` on the page to its
header labels and attribute-nested rows, and selecting the one authoritative
table. The typed contract, identity gate, and tree builder live in
:mod:`fundamentals.ingest.tijori_shareholding`, which re-exports what callers
need from here.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.tijori_tables import TijoriParseError

# The rendered DOM id of the real table, inside
# <section id="detailed" subpart="detailed-shareholding" mainpart="shareholding">.
# The sample-report decoys render as class="peg-sample__table" and carry no id,
# so the id finds the table and the structural assertions below prove it.
SHAREHOLDING_TABLE_ELEMENT_ID = "company_detailed"
SHAREHOLDING_UNIT_LABEL = "in %"

_TABLE_TAG = "table"
_ROW_TAG = "tr"
_HEADER_CELL_TAG = "th"
_DATA_CELL_TAG = "td"
_DIV_TAG = "div"

_UNIT_CELL_CLASS = "unit_val"
_HEADER_ITEM_CLASS = "headerItem"
_VALUE_CELL_CLASS = "numericvalue"
_NAME_BLOCK_CLASS = "nameofmetriccol"
_ROW_ID_ATTRIBUTE = "myid"
_ROW_PARENT_ATTRIBUTE = "data-parent"
_ROW_DEPTH_ATTRIBUTE = "class rowN"
_CLASS_ATTRIBUTE = "class"
_ELEMENT_ID_ATTRIBUTE = "id"
_ROW_DEPTH_CLASS = re.compile(r"^row(\d+)$")
_UNNAMED_ROW_LABEL = "<unnamed>"


class TijoriShareholdingAbsentError(TijoriParseError):
    """The shareholding page carries no table matching the verified shape."""


class TijoriShareholdingAmbiguousError(TijoriParseError):
    """More than one table on the page matches the shareholding shape."""


class TijoriShareholdingSchemaError(TijoriParseError):
    """The shareholding table does not satisfy its typed row/nesting shape."""


class _RawRow(BaseModel):
    """One rendered ``<tr>`` reduced to the attributes and lexemes that matter.

    ``source_depth`` is Tijori's one-based ``rowN`` class, preserved as rendered.
    """

    model_config = ConfigDict(frozen=True)

    source_depth: int
    node_id: str
    parent_id: str
    label: str
    raw_values: tuple[str, ...]


class _RawTable(BaseModel):
    """One rendered ``<table>`` reduced to its header labels and data rows.

    ``malformed_rows`` names data rows — rows that rendered ``<td>`` cells — which
    lack the machine-readable nesting attributes. They are carried rather than
    dropped so that discarding one is a decision the caller makes loudly.
    """

    model_config = ConfigDict(frozen=True)

    element_id: str | None
    unit_label: str | None
    column_labels: tuple[str, ...]
    rows: tuple[_RawRow, ...]
    malformed_rows: tuple[str, ...] = ()

    def shape_failures(self) -> tuple[str, ...]:
        """Name every structural expectation this table does not satisfy."""
        failures: list[str] = []
        if self.unit_label != SHAREHOLDING_UNIT_LABEL:
            failures.append(
                f"unit header is {self.unit_label!r}, expected {SHAREHOLDING_UNIT_LABEL!r}"
            )
        if not self.column_labels:
            failures.append("no quarter column headers")
        if not self.rows:
            failures.append("no attribute-nested rows")
        if self.malformed_rows:
            failures.append(
                f"data rows without rowN/myid/data-parent: {', '.join(self.malformed_rows)}"
            )
        return tuple(failures)


def _collapse(text: str) -> str:
    """Collapse rendered whitespace without altering the visible lexeme."""
    return " ".join(text.split())


def _classes(attrs: list[tuple[str, str | None]]) -> frozenset[str]:
    """Read one element's CSS class tokens."""
    raw = dict(attrs).get(_CLASS_ATTRIBUTE)
    return frozenset() if raw is None else frozenset(raw.split())


class _ShareholdingTableCollector(HTMLParser):
    """Collect every rendered table's header labels and nested rows.

    Character references are converted here — unlike JSON-island collection —
    because this markup IS the data: ``&#x27;`` belongs to a quarter label and
    ``&mdash;`` is the rendered absent-value lexeme.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_RawTable] = []
        self._table_stack: list[dict[str, Any]] = []
        self._row: dict[str, Any] | None = None
        self._capture: list[str] | None = None
        self._name_div_depth = 0

    @property
    def _table(self) -> dict[str, Any] | None:
        """The innermost table currently being collected, if any."""
        return self._table_stack[-1] if self._table_stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open a table, row, or capturing cell."""
        if tag == _TABLE_TAG:
            self._table_stack.append(
                {
                    "element_id": dict(attrs).get(_ELEMENT_ID_ATTRIBUTE),
                    "unit_label": None,
                    "columns": [],
                    "rows": [],
                    "malformed": [],
                }
            )
            return
        table = self._table
        if table is None:
            return
        if tag == _ROW_TAG:
            self._start_row(attrs)
            return
        if self._row is None:
            return
        if tag == _HEADER_CELL_TAG:
            self._start_header_cell(attrs, table)
            return
        if tag == _DATA_CELL_TAG:
            self._row["has_data_cell"] = True
            self._start_data_cell(attrs)
            return
        if self._name_div_depth and tag == _DIV_TAG:
            self._name_div_depth += 1
            return
        if tag == _DIV_TAG and _NAME_BLOCK_CLASS in _classes(attrs):
            self._name_div_depth = 1
            self._capture = []

    def _start_row(self, attrs: list[tuple[str, str | None]]) -> None:
        """Begin one ``<tr>``, recording its nesting attributes when present."""
        attributes = dict(attrs)
        depth = next(
            (
                int(match.group(1))
                for token in _classes(attrs)
                if (match := _ROW_DEPTH_CLASS.match(token)) is not None
            ),
            None,
        )
        self._row = {
            "source_depth": depth,
            "node_id": attributes.get(_ROW_ID_ATTRIBUTE),
            "parent_id": attributes.get(_ROW_PARENT_ATTRIBUTE),
            "label": None,
            "values": [],
            "has_data_cell": False,
        }

    def _start_header_cell(
        self, attrs: list[tuple[str, str | None]], table: dict[str, Any]
    ) -> None:
        """Begin capturing a unit or column header cell."""
        classes = _classes(attrs)
        if _UNIT_CELL_CLASS in classes or _HEADER_ITEM_CLASS in classes:
            self._capture = []
            table["pending_header"] = (
                _UNIT_CELL_CLASS if _UNIT_CELL_CLASS in classes else _HEADER_ITEM_CLASS
            )

    def _start_data_cell(self, attrs: list[tuple[str, str | None]]) -> None:
        """Begin capturing a numeric value cell (name cells capture at their div)."""
        if _VALUE_CELL_CLASS in _classes(attrs):
            self._capture = []

    def handle_data(self, data: str) -> None:
        """Accumulate text for the cell currently being captured."""
        if self._capture is not None:
            self._capture.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Close a capturing cell, a row, or a table."""
        if tag == _DIV_TAG and self._name_div_depth:
            self._name_div_depth -= 1
            if self._name_div_depth == 0:
                self._finish_name()
            return
        if tag in (_HEADER_CELL_TAG, _DATA_CELL_TAG):
            self._finish_cell(tag)
            return
        if tag == _ROW_TAG:
            self._finish_row()
            return
        if tag == _TABLE_TAG:
            self._finish_table()

    def _finish_name(self) -> None:
        """Store the display name captured from the row's name block."""
        if self._row is not None and self._capture is not None:
            self._row["label"] = _collapse("".join(self._capture))
        self._capture = None

    def _finish_cell(self, tag: str) -> None:
        """Store one captured header or value lexeme."""
        table = self._table
        if table is None or self._capture is None:
            return
        text = _collapse("".join(self._capture))
        self._capture = None
        if tag == _HEADER_CELL_TAG:
            slot = table.pop("pending_header", None)
            if slot == _UNIT_CELL_CLASS:
                table["unit_label"] = text
            elif slot == _HEADER_ITEM_CLASS:
                table["columns"].append(text)
        elif self._row is not None:
            self._row["values"].append(text)

    def _finish_row(self) -> None:
        """Retain a completed data row, or record it as malformed — never drop it.

        A row that rendered no ``<td>`` is a header row, not a dropped data row,
        so it is excluded explicitly by that fact rather than by its missing
        nesting attributes.
        """
        row, self._row = self._row, None
        self._capture = None
        self._name_div_depth = 0
        table = self._table
        if table is None or row is None:
            return
        if not row["has_data_cell"]:
            return
        missing = tuple(
            attribute
            for attribute, value in (
                (_ROW_DEPTH_ATTRIBUTE, row["source_depth"]),
                (_ROW_ID_ATTRIBUTE, row["node_id"]),
                (_ROW_PARENT_ATTRIBUTE, row["parent_id"]),
            )
            if value is None
        )
        if missing:
            label = row["label"] or _UNNAMED_ROW_LABEL
            table["malformed"].append(f"{label!r} (missing {', '.join(missing)})")
            return
        table["rows"].append(
            _RawRow(
                source_depth=row["source_depth"],
                node_id=row["node_id"],
                parent_id=row["parent_id"],
                label=row["label"] or "",
                raw_values=tuple(row["values"]),
            )
        )

    def _finish_table(self) -> None:
        """Close the innermost table and retain its reduced shape."""
        if not self._table_stack:
            return
        table = self._table_stack.pop()
        self.tables.append(
            _RawTable(
                element_id=table["element_id"],
                unit_label=table["unit_label"],
                column_labels=tuple(table["columns"]),
                rows=tuple(table["rows"]),
                malformed_rows=tuple(table["malformed"]),
            )
        )


def _select_shareholding_table(document: str) -> _RawTable:
    """Select the detailed-shareholding table by DOM id, then prove its shape.

    Selecting on shape alone is spoofable: the page renders sample-report modal
    templates that can be made to satisfy the same structural predicate. The
    rendered ``id`` identifies the table exactly; the structural assertions then
    verify that what the id pointed at really is the shareholding table. Both are
    mandatory — the id alone would trust a renamed element.
    """
    collector = _ShareholdingTableCollector()
    collector.feed(document)
    collector.close()
    candidates = tuple(
        table for table in collector.tables if table.element_id == SHAREHOLDING_TABLE_ELEMENT_ID
    )
    if not candidates:
        raise TijoriShareholdingAbsentError(
            f"tijori shareholding page carries no <table id={SHAREHOLDING_TABLE_ELEMENT_ID!r}>; "
            f"inspected {len(collector.tables)} tables"
        )
    if len(candidates) > 1:
        raise TijoriShareholdingAmbiguousError(
            f"tijori shareholding page has {len(candidates)} tables with id "
            f"{SHAREHOLDING_TABLE_ELEMENT_ID!r}; refusing to guess which one is authoritative"
        )
    failures = candidates[0].shape_failures()
    if failures:
        raise TijoriShareholdingSchemaError(
            f"tijori <table id={SHAREHOLDING_TABLE_ELEMENT_ID!r}> is not the detailed "
            f"shareholding shape: {'; '.join(failures)}"
        )
    return candidates[0]
