"""Vendor-capture locators: read a retained Screener, Tijori or Upstox file's rows and cells."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any, cast

from lxml import html  # type: ignore[import-untyped]

SCREENER_SECTIONS = ("quarters", "profit-loss", "balance-sheet", "cash-flow")
TIJORI_TABLES = ("bs_c_d", "bs_c_s", "cf_c", "fr_c", "pl_c_d", "pl_c_s", "qt_c")
ISLAND = '<script id="fin_tables_data" type="application/json">'


def text(node: Any) -> str:
    return " ".join(node.text_content().split())


@cache
def screener_table(path: Path, section: str) -> tuple[list[str], dict[str, list[str]]]:
    """A section's data-table: header labels and each body row's cells by label ('+' dropped)."""
    root = html.fromstring(path.read_bytes())
    (table,) = root.get_element_by_id(section).xpath(".//table[contains(@class, 'data-table')]")
    heads = [text(th) for th in table.xpath(".//thead//th")]
    rows: dict[str, list[str]] = {}
    for tr in table.xpath(".//tbody/tr"):
        cells = [text(td) for td in tr.xpath("./td")]
        if cells:
            label = cells[0].removesuffix("+").strip()
            assert label not in rows and len(cells) == len(heads), (path, section, label)
            rows[label] = cells
    return heads, rows


@cache
def tijori_island(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    return cast(
        dict[str, Any], json.JSONDecoder().raw_decode(body, body.index(ISLAND) + len(ISLAND))[0]
    )


def tijori_cell(path: Path, table: str, row: str, column: str) -> str:
    body = tijori_island(path)[table]
    (values,) = [item["value"] for item in body["data"] if item["name"] == row]
    return repr(values[body["report_dates"].index(column)])


def upstox_entries(path: Path, block: str) -> list[tuple[str, list[dict[str, Any]]]]:
    key = "category" if block == "income_statement" else "particular"
    data = json.loads(path.read_text())["data"]
    return [(entry[key], entry["history"]) for entry in data[block]]


def upstox_cell(path: Path, block: str, item: str, column: str) -> str:
    (history,) = [h for name, h in upstox_entries(path, block) if name == item]
    (cell,) = [h["value"] for h in history if h["period"] == column]
    return repr(cell)


def vendor_rows(kind: str, path: Path) -> Iterator[tuple[str, str, str, list[str]]]:
    """(section / table / block, row key, label, columns) of every row a vendor capture yields
    occurrences for (header.interpretations I18); a row without values yields no column."""
    if kind == "screener_html":
        for section in SCREENER_SECTIONS:
            heads, rows = screener_table(path, section)
            yield from ((section, label, label, heads[1:]) for label in rows)
    elif kind == "tijori_island":
        island = tijori_island(path)

        def flatten(table: str, rows: list[Any], parents: str) -> Iterator[Any]:
            dates = island[table]["report_dates"]
            for row in rows:
                key, count = parents + row["name"], len(row["value"])
                assert count in (0, len(dates)) or count < len(dates) and table[:2] == "pl", key
                yield table, key, row["name"], dates if count else []
                yield from flatten(table, row.get("sub_section") or [], key + "/")

        for table in TIJORI_TABLES:
            if island.get(table):
                yield from flatten(table, island[table]["data"], "")
    else:
        for block in ("income_statement", "full_statement"):
            for name, history in upstox_entries(path, block):
                yield block, name, name, [h["period"] for h in history]
