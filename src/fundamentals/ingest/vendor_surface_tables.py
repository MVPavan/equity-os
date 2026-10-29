"""Positional cells from retained G2 tables, document lists and script literals."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tokenize
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.vendor_surface_series import numeric_cell, numeric_column, numeric_json
from fundamentals.ingest.vendor_surface_specs import SurfaceSpec
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext, Parser


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
        expected_numeric=numeric_column(header),
    )


def read_html_table(tree: Any, selector: str, table_key: str) -> tuple[VendorValue, ...]:
    """Read a rectangular HTML table, rejecting missing or ragged markup."""
    (table,) = tree.xpath(selector)
    return _table_rows(table, table_key, table.xpath("./tbody/tr[td] | ./tr[td]"))


def _table_rows(table: Any, table_key: str, rows: list[Any]) -> tuple[VendorValue, ...]:
    """Preserve source locators while applying the strict table shape contract."""
    headers = [
        _text(n)
        for n in table.xpath(
            "(./thead/tr | ./tr[th and not(td)] | ./tbody/tr[th and not(td)])[1]/th"
        )
    ]
    if not headers:
        raise ValueError("table header missing")
    values: list[VendorValue] = []
    for row, node in enumerate(rows):
        cells = node.xpath("./td | ./th")
        if len(cells) != len(headers):
            raise ValueError("ragged table row")
        for column, cell in enumerate(cells):
            values.append(_cell(cell, table_key, row, column, _text(cells[0]), headers[column]))
            values.extend(
                _cell(
                    link,
                    f"{table_key}:links:{column}",
                    row,
                    index,
                    _text(cells[0]),
                    headers[column],
                )
                for index, link in enumerate(cell.xpath(".//a[@href]")[1:], start=1)
            )
    return tuple(values)


def screener_trades(body: Body, context: ParseContext, selector: str) -> tuple[VendorValue, ...]:
    """Keep month dividers separately so repeated trade labels never collapse."""
    values: list[VendorValue] = []
    tables = body.tree().xpath(selector)
    if not tables:
        raise ValueError("trade tables missing")
    for table in tables:
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


def screener_documents(body: Body, context: ParseContext, selector: str) -> tuple[VendorValue, ...]:
    """Use each document heading to distinguish present blocks from absent kinds."""
    values: list[VendorValue] = []
    for index, heading in enumerate(body.tree().xpath(selector + "//h3")):
        block = heading
        while "documents" not in block.get("class", "").split():
            block = block.getparent()
        values.extend(
            cell.model_copy(update={"row_label": _text(heading)})
            for cell in _documents(block, f"documents:{index}")
        )
    return tuple(values)


def screener_announcements(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the retained announcement fragment, excluding action controls."""
    return _documents(body.tree(), "Announcements")


def tijori_filings(body: Body, context: ParseContext, selector: str) -> tuple[VendorValue, ...]:
    """Keep every filing cell and link at its year/category position."""
    return read_html_table(body.tree(), selector, "companyFilings")


def _cards(body: Body, surface: str, selector: str) -> tuple[VendorValue, ...]:
    """An absent section heading means this company kind lacks that block."""
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
    return numeric_json("".join(parts))


def tijori_shareholding_overview(
    body: Body, context: ParseContext, selector: str
) -> tuple[VendorValue, ...]:
    """Read the Overview table and its separately declared chart slices."""
    values = list(read_html_table(body.tree(), selector, "overview"))
    for row, (label, number) in enumerate(read_js_var(body.raw, "chartData")):
        values.append(
            numeric_cell(
                number, "chartData", row, 0, f"var chartData/{row}/1", label, "Shareholding"
            ).model_copy(update={"unit": "%"})
        )
    return tuple(values)


def tijori_shareholding_trend(
    body: Body, context: ParseContext, selector: str
) -> tuple[VendorValue, ...]:
    """Read each trend series by its own point position and timestamp."""
    values: list[VendorValue] = []
    for column, series in enumerate(read_js_var(body.raw, "trendData")):
        for row, (timestamp, number) in enumerate(series["data"]):
            values.append(
                numeric_cell(
                    number,
                    "trendData",
                    row,
                    column,
                    f"var trendData/{column}/data/{row}/1",
                    str(timestamp),
                    series["name"],
                ).model_copy(update={"unit": "%"})
            )
    return tuple(values)


def company_parser(spec: SurfaceSpec) -> Parser:
    """Bind the configured selector once, without a second configuration read."""

    def parse(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
        assert spec.selector is not None or spec.id == "company-announcements"
        if spec.id in {
            "overview-customers",
            "overview-suppliers",
            "overview-brands",
            "overview-connections",
        }:
            return _cards(body, spec.id, spec.selector or "")
        if spec.id == "company-announcements":
            return screener_announcements(body, context)
        return {
            "company-trades": screener_trades,
            "section-documents": screener_documents,
            "overview-company-filings": tijori_filings,
            "shareholding-overview": tijori_shareholding_overview,
            "shareholding-trend": tijori_shareholding_trend,
        }[spec.id](body, context, spec.selector or "")

    return parse


class FeedRow(BaseModel):
    """A source event identity with a date only when the source supplies one."""

    model_config = ConfigDict(frozen=True)
    row_id: str
    company: str
    row_date: date | None = None


def _feed_date(raw: str) -> date:
    """Accept the full date formats actually displayed by the retained feeds."""
    for format in ("%d %B %Y", "%d %b %Y", "%d %b, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, format).date()
        except ValueError:
            pass
    return datetime.fromisoformat(raw).date()


def feed_rows(spec: SurfaceSpec, values: tuple[VendorValue, ...]) -> tuple[FeedRow, ...]:
    """Read persisted feed metadata, rejecting category hubs and other non-feeds."""
    if not spec.feed:
        raise ValueError("surface is not a feed")
    rows: dict[int, dict[str, VendorValue]] = {}
    for value in values:
        if value.table_key == spec.id + ":feed":
            rows.setdefault(value.row_index, {})[value.column_label] = value
    return tuple(
        FeedRow(
            row_id=row["Row ID"].link
            or hashlib.sha256(
                json.dumps([row["Company"].link, row["Row ID"].raw_text]).encode()
            ).hexdigest(),
            company=row["Company"].link or row["Company"].raw_text,
            row_date=_feed_date(row["Date"].raw_text) if "Date" in row else None,
        )
        for _, row in sorted(rows.items())
    )


def _feed_cells(
    node: Any, company: Any, surface: str, row: int, dated: Any = None, event: Any = None
) -> tuple[VendorValue, ...]:
    """Anchor event and company metadata to source text and links."""
    companies = company.xpath(
        './/a[starts-with(@href,"/company/")] | self::a[starts-with(@href,"/company/")]'
    )
    company = companies[0] if companies else company
    links = node.xpath(
        './/a[not(starts-with(@href,"/company/")) and not(starts-with(@href,"/people/"))]/@href'
    )
    identity = links[0] if links else None
    if event is not None:
        identity = event.get("href")
    if surface == "ipo":
        identity = company.get("href")
    fields = [
        ("Company", company, company.get("href") if companies else None),
        ("Row ID", event if event is not None else node, identity),
    ]
    if dated is not None:
        fields.append(("Date", dated, None))
    return tuple(
        _cell(part, surface + ":feed", row, column, _text(company), label).model_copy(
            update={"link": link, "raw_text": part.get("datetime") or _text(part)}
        )
        for column, (label, part, link) in enumerate(fields)
    )


def market_parser(spec: SurfaceSpec) -> Parser:
    """Bind one configured market surface to its retained table or card shape."""
    surface = spec.id

    def parse(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
        """Preserve positional cells and validate full feed dates before recording."""
        assert spec.selector is not None
        nodes = body.tree().xpath(spec.selector)
        if not nodes:
            raise ValueError("market block missing")
        values: list[VendorValue] = []
        event_index = 0
        for index, node in enumerate(nodes):
            key = f"{surface}:{index}"
            if node.tag == "table":
                values.extend(read_html_table(node, ".", key))
                if spec.feed:
                    headers = [_text(n) for n in node.xpath("./thead/tr/th")]
                    for tr in node.xpath("./tbody/tr[td] | ./tr[td]"):
                        cells = tr.xpath("./td | ./th")
                        company = cells[0]
                        date_node = next(
                            (
                                cell
                                for cell, label in zip(cells, headers, strict=True)
                                if label in {"Date", "Result date", "Pub date", "Ex date"}
                            ),
                            None,
                        )
                        if date_node is not None and date_node.xpath('./div[@class="desktop"]'):
                            date_node = date_node.xpath('./div[@class="desktop"]')[0]
                        values.extend(_feed_cells(tr, company, surface, event_index, date_node))
                        event_index += 1
            elif surface in {"results-latest", "quarterly-results-api"}:
                table = node.xpath(".//table")[0]
                values.extend(read_html_table(table, ".", key))
                header = node.getprevious() if surface == "results-latest" else node
                company = header.xpath('.//a[starts-with(@href,"/company/")]')[0]
                dates = header.xpath('.//span[contains(@class,"event_date")]')
                date_node = dates[0] if dates and _text(dates[0]) not in {"", "Today"} else None
                event = (
                    header.xpath('.//a[contains(@href,"/source/quarter/")]')[0]
                    if surface == "results-latest"
                    else table.xpath("./thead/tr/th[4]")[0]
                )
                values.extend(_feed_cells(header, company, surface, index, date_node, event))
                for column, part in enumerate(
                    header.xpath(
                        './/a[@href] | .//div[@class="metrics"]/div | '
                        './/span[@class="sub" or @data-mcap or @class="sub margin-left-16"]'
                    )
                ):
                    values.append(_cell(part, key + ":header", 0, column, _text(company), "Header"))
            elif surface == "idea-page":
                if "no_data" not in node.get("class", "").split():
                    raise ValueError("unretained idea card shape")
            elif surface == "idea-card-body":
                for column, part in enumerate(
                    node.xpath(
                        './/span[@class="name" or @class="symbol" '
                        'or @class="market_cap" or @class="sector"]'
                    )
                ):
                    values.append(
                        _cell(part, surface, index, column, _text(node), part.get("class"))
                    )
            else:
                parts = (
                    node.xpath(".//a[@href]") if surface != "market-pulse" else node.xpath("./div")
                )
                if surface == "ratings-feed":
                    company = node.xpath("./a")[0]
                    label = _text(company).split(":", 1)[0]
                    values.append(_cell(company, key, 0, 0, label, "Report"))
                    metadata = _feed_cells(node, company, surface, index)
                    values.extend(
                        v.model_copy(update={"raw_text": label})
                        if v.column_label == "Company"
                        else v
                        for v in metadata
                    )
                else:
                    for column, part in enumerate(parts):
                        values.append(_cell(part, surface, index, column, _text(node), "Text"))
                    if spec.feed:
                        company = node.xpath('.//a[starts-with(@href,"/company/")]')[0]
                        dates = node.xpath(".//time[@datetime]")
                        values.extend(
                            _feed_cells(node, company, surface, index, dates[0] if dates else None)
                        )
        result = tuple(values)
        if spec.feed:
            feed_rows(spec, result)
        return result

    return parse
