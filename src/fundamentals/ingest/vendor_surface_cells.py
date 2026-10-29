"""Code-read G3 cells and the label evidence consumed by mapping proposals."""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_tables import read_html_table, read_js_var
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext

# Display markers of an intentionally absent measurement, as seen in retained G3 bodies.
MISSING = frozenset({"", "-", "n/a"})


class LabelSample(BaseModel):
    """Verbatim label with code-read unit and per-share evidence."""

    model_config = ConfigDict(frozen=True)
    label: str
    units: frozenset[str]
    per_share: bool


def _text(node: Any) -> str:
    """Keep display text separated across inline markup."""
    return " ".join(" ".join(node.itertext()).split())


def measurement(cell: VendorValue, raw: str, unit: str | None = None) -> VendorValue:
    """Read a measurement's scalar and displayed suffix; only a missing marker is unexpected."""
    match = re.fullmatch(r"([₹$€£¥]?)\s*([+\-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+))\s*([^\d]*)", raw)
    return cell.model_copy(
        update={
            "raw_text": raw,
            "value": Decimal(match[2].replace(",", "")) if match else None,
            "unit": unit
            or (
                " ".join(part for part in (match[1], match[3].strip()) if part) or None
                if match
                else None
            ),
            "expected_numeric": raw.strip().lower() not in MISSING,
        }
    )


def screener_insights(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read loaded yearly/quarterly tables, excluding source tooltips from numbers."""
    tree = body.tree()
    values = []
    for block in tree.xpath('//*[@id="yearly-insights" or @id="quarterly-insights"][.//table]'):
        for cell in read_html_table(tree, f'//*[@id="{block.get("id")}"]//table', block.get("id")):
            node = tree.xpath(cell.locator)[0]
            label = node.getparent().xpath("./td[1]")[0]
            metadata = " ".join(label.xpath("./span/text()"))
            display = node.xpath("./span/span[1]")
            raw = _text(display[0]) if display else _text(node)
            value = (
                measurement(cell, raw, metadata.split("・")[0].strip() or None)
                if cell.column_index
                else cell
            )
            values.append(
                value.model_copy(
                    update={
                        "row_label": " ".join(label.xpath("./text()")).strip(),
                        "basis": "standalone"
                        if "Standalone data" in metadata
                        else (context.basis.value if context.basis else None),
                    }
                )
            )
    return tuple(values)


def screener_compare(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Keep each comparison table separate, including repeated peer rows."""
    tree = body.tree()
    values: list[VendorValue] = []
    for index, table in enumerate(tree.xpath("//table")):
        # Column zero and header cells classed "text" are descriptors, such as the peer name.
        descriptors = {0} | {
            column
            for column, header in enumerate(table.xpath("(./thead/tr)[1]/th"))
            if "text" in (header.get("class") or "").split()
        }
        values += (
            cell if cell.column_index in descriptors else measurement(cell, cell.raw_text)
            for cell in read_html_table(tree, f"(//table)[{index + 1}]", f"compare:{index}")
        )
    return tuple(values)


def benchmark_financial(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the financial KPI table including empty group rows and n/a cells."""
    return tuple(
        measurement(cell, cell.raw_text) if cell.column_index else cell
        for cell in read_html_table(
            body.tree(), '//*[@id="benchmarking-financial"]//table', "benchmark-financial"
        )
    )


def benchmark_business_cards(tree: Any) -> tuple[VendorValue, ...]:
    """Keep business display cells and missing-peer markers at their table positions."""
    return read_html_table(tree, '//*[@id="benchmarking-business"]//table', "business-cards")


def benchmark_business_charts(body: Body) -> tuple[VendorValue, ...]:
    """Decode retained chartdata literals without executing JavaScript."""
    values = []
    tree = body.tree()
    for chart_index, chart in enumerate(
        tree.xpath('//*[@id="benchmarking-business"]//*[@chartdata]')
    ):
        table = chart.xpath("ancestor::table[1]")[0]
        column = len(chart.xpath("ancestor::td[1]/preceding-sibling::td"))
        header = table.xpath("./thead/tr/th")[column]
        data = read_js_var(("var chart = " + chart.get("chartdata") + ";").encode(), "chart")
        for row, (label, number) in enumerate(data):
            values.append(
                VendorValue(
                    table_key=f"business-charts:{chart_index}",
                    row_index=row,
                    column_index=column,
                    locator=tree.getroottree().getpath(chart) + f"/@chartdata/{row}/1",
                    row_label=label,
                    column_label=_text(header),
                    raw_text=str(number),
                    value=number,
                    expected_numeric=True,
                )
            )
    return tuple(values)


def benchmark_business(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read both business representations from the parent's shared document."""
    return benchmark_business_cards(body.tree()) + benchmark_business_charts(body)


def label_samples(cells: Iterable[tuple[str, str | None, bool]]) -> tuple[LabelSample, ...]:
    """Group measurement units by verbatim label; descriptors and missing markers add none."""
    units: dict[str, set[str]] = {}
    for label, unit, measured in cells:
        if label and measured:
            units.setdefault(label, set()).add(unit or "")
    return tuple(
        LabelSample(
            label=label,
            units=frozenset(found),
            per_share=bool(
                re.search(r"per share|/share|₹/sh|\bEPS\b", " ".join([label, *found]), re.I)
            ),
        )
        for label, found in sorted(units.items())
    )


def cell_labels(pool: ConnectionPool, site: Site, surface: str) -> tuple[LabelSample, ...]:
    """Collect units by verbatim label within one site's logical surface."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT v.row_label, v.unit, v.expected_numeric "
            "FROM eqos.vendor_values v JOIN eqos.vendor_outcomes o ON o.id=v.outcome_id "
            "JOIN eqos.capture_refs c ON c.id=v.capture_ref_id "
            "WHERE c.source_id=%s AND o.surface=%s",
            (site, surface),
        ).fetchall()
    return label_samples(rows)
