"""Positional cells from retained G2 tables, document lists and script literals."""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fundamentals.ingest.vendor_surface_specs import load_specs
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext


def _text(node: Any) -> str:
    """Preserve display text apart from surrounding markup whitespace."""
    return " ".join(node.text_content().split())


def _cell(node: Any, key: str, row: int, column: int, label: str, header: str) -> VendorValue:
    """Anchor one display cell without deriving numbers from prose."""
    raw = _text(node)
    candidate = raw.replace(",", "").removesuffix("%")
    try:
        number = Decimal(candidate)
    except InvalidOperation:
        number = None
    links = node.xpath(".//a[@href]/@href | self::a/@href")
    return VendorValue(
        table_key=key,
        row_index=row,
        column_index=column,
        locator=node.getroottree().getpath(node),
        row_label=label,
        column_label=header,
        raw_text=raw,
        value=number,
        link=links[0] if links else None,
        expected_numeric=bool(re.fullmatch(r"[+\-]?[\d,.]+%?", raw)),
    )


def read_html_table(tree: Any, selector: str, table_key: str) -> tuple[VendorValue, ...]:
    """Read a rectangular HTML table, rejecting missing or ragged markup."""
    (table,) = tree.xpath(selector)
    return _table_rows(table, table_key, table.xpath("./tbody/tr | ./tr[td]"))


def _table_rows(table: Any, table_key: str, rows: list[Any]) -> tuple[VendorValue, ...]:
    """Preserve source locators while applying the strict table shape contract."""
    headers = [_text(n) for n in table.xpath("./thead/tr/th | ./tr[th]/th")]
    if not headers:
        raise ValueError("table header missing")
    values: list[VendorValue] = []
    for row, node in enumerate(rows):
        cells = node.xpath("./td | ./th")
        if len(cells) != len(headers):
            raise ValueError("ragged table row")
        for column, cell in enumerate(cells):
            values.append(_cell(cell, table_key, row, column, _text(cells[0]), headers[column]))
    return tuple(values)


@cache
def _selector(surface: str) -> str:
    """Read the task's selectors from the shared finite surface table."""
    spec = next(
        s
        for s in load_specs(
            Path("config/vendor_surface/surfaces.yaml"),
            Path("docs/research/vendor-surface/catalog.yaml"),
        )
        if s.id == surface
    )
    assert spec.selector is not None
    return spec.selector


def screener_trades(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Keep month dividers separately so repeated trade labels never collapse."""
    values: list[VendorValue] = []
    for table in body.tree().xpath(_selector("company-trades")):
        key = table.getparent().get("id")
        for row in table.xpath("./tbody/tr[td/@colspan]"):
            (cell,) = row.xpath("./td")
            if int(cell.get("colspan")) != len(table.xpath("./thead/tr/th")):
                raise ValueError("invalid trade month divider")
            values.append(_cell(cell, key + ":months", len(values), 0, _text(cell), "Month"))
        values.extend(_table_rows(table, key, table.xpath("./tbody/tr[not(td/@colspan)]")))
    return tuple(values)


def _documents(tree: Any, key: str) -> tuple[VendorValue, ...]:
    """Read each linked document as title, date and URL, including every concall link."""
    values: list[VendorValue] = []
    for item in tree.xpath('.//ul[@class="list-links"]/li'):
        for link in item.xpath("./a[@href]"):
            row = len(values) // 3
            date = item.xpath(".//time/@datetime") or item.xpath("./div[1] | ./a/div")
            date_text = (
                date[0] if date and isinstance(date[0], str) else (_text(date[0]) if date else "")
            )
            title = " ".join(link.xpath("./text()")).strip()
            for column, (header, raw) in enumerate(
                (("Title", title), ("Date", date_text), ("Link", link.get("href")))
            ):
                cell = _cell(link, key, row, column, title, header)
                values.append(
                    cell.model_copy(
                        update={"raw_text": raw, "value": None, "expected_numeric": False}
                    )
                )
    return tuple(values)


def screener_documents(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Use each document heading to distinguish present blocks from absent kinds."""
    values: list[VendorValue] = []
    for heading in body.tree().xpath(_selector("section-documents") + "//h3"):
        block = heading
        while "documents" not in block.get("class", "").split():
            block = block.getparent()
        values.extend(_documents(block, _text(heading)))
    return tuple(values)


def screener_announcements(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the retained announcement fragment, excluding action controls."""
    return _documents(body.tree(), "Announcements")


def tijori_filings(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Keep every filing cell and link at its year/category position."""
    return read_html_table(body.tree(), _selector("overview-company-filings"), "companyFilings")


def _cards(body: Body, surface: str) -> tuple[VendorValue, ...]:
    """An absent section heading means this company kind lacks that block."""
    selector = _selector(surface)
    blocks = body.tree().xpath(selector)
    if not blocks or not blocks[0].xpath(".//h2"):
        return ()
    nodes = blocks[0].xpath('.//li | .//div[@class="brand_name"]')
    if not nodes:
        raise ValueError("headed card block has no rows")
    return tuple(
        _cell(node, surface, row, 0, _text(node), _text(node.xpath("ancestor::section[1]//h2")[0]))
        for row, node in enumerate(nodes)
    )


def tijori_customers(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read customers from the headed card list."""
    return _cards(body, "overview-customers")


def tijori_suppliers(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read suppliers from the headed card list."""
    return _cards(body, "overview-suppliers")


def tijori_brands(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read brands from the headed card list."""
    return _cards(body, "overview-brands")


def tijori_connections(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the connection list, retaining its supplier/customer subheadings."""
    return _cards(body, "overview-connections")


def read_js_var(body: bytes, name: str) -> Any:
    """Decode a literal assignment with exact decimals, never executing JavaScript."""
    match = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*", body.decode("utf-8"))
    if match is None:
        raise ValueError("script variable missing")
    source = body.decode("utf-8")[match.end() :]
    parts = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.string == ";" and token.type == tokenize.OP:
            break
        parts.append(
            json.dumps(ast.literal_eval(token.string))
            if token.type == tokenize.STRING
            else token.string
        )
    return json.loads("".join(parts), parse_float=Decimal, parse_int=Decimal)


def tijori_shareholding_overview(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the Overview table and its separately declared chart slices."""
    values = list(read_html_table(body.tree(), _selector("shareholding-overview"), "overview"))
    for row, (label, number) in enumerate(read_js_var(body.raw, "chartData")):
        values.append(
            VendorValue(
                table_key="chartData",
                row_index=row,
                column_index=0,
                locator=f"var chartData/{row}/1",
                row_label=label,
                column_label="Shareholding",
                raw_text="null" if number is None else str(number),
                value=number,
                expected_numeric=True,
                unit="%",
            )
        )
    return tuple(values)


def tijori_shareholding_trend(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read each trend series by its own point position and timestamp."""
    values: list[VendorValue] = []
    for column, series in enumerate(read_js_var(body.raw, "trendData")):
        for row, (timestamp, number) in enumerate(series["data"]):
            values.append(
                VendorValue(
                    table_key="trendData",
                    row_index=row,
                    column_index=column,
                    locator=f"var trendData/{column}/data/{row}/1",
                    row_label=str(timestamp),
                    column_label=series["name"],
                    raw_text="null" if number is None else str(number),
                    value=number,
                    expected_numeric=True,
                    unit="%",
                )
            )
    return tuple(values)
