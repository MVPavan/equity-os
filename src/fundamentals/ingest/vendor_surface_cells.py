"""Code-read G3 cells and the label evidence consumed by mapping proposals."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_tables import read_html_table, read_js_var
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext


class LabelSample(BaseModel):
    """Verbatim label with code-read unit and per-share evidence."""

    model_config = ConfigDict(frozen=True)
    label: str
    units: frozenset[str]
    per_share: bool


def _text(node: Any) -> str:
    """Keep display text separated across inline markup."""
    return " ".join(" ".join(node.itertext()).split())


def _number(cell: VendorValue, raw: str, unit: str | None = None) -> VendorValue:
    """Read a scalar and its displayed suffix without interpreting its label."""
    match = re.fullmatch(r"([+\-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+))\s*([^\d]*)", raw)
    return cell.model_copy(
        update={
            "raw_text": raw,
            "value": Decimal(match[1].replace(",", "")) if match else None,
            "unit": unit or (match[2].strip() or None if match else None),
            "expected_numeric": bool(match),
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
                _number(cell, raw, metadata.split("・")[0].strip() or None)
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
    return tuple(
        _number(cell, cell.raw_text) if cell.column_index else cell
        for index, _ in enumerate(tree.xpath("//table"))
        for cell in read_html_table(tree, f"(//table)[{index + 1}]", f"compare:{index}")
    )


def benchmark_financial(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the financial KPI table including empty group rows and n/a cells."""
    return tuple(
        _number(cell, cell.raw_text) if cell.column_index else cell
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


def cell_labels(pool: ConnectionPool, site: Site, surface: str) -> tuple[LabelSample, ...]:
    """Collect units by verbatim label within one site's logical surface."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT v.row_label, array_agg(DISTINCT coalesce(v.unit,'')) "
            "FROM eqos.vendor_values v JOIN eqos.vendor_outcomes o ON o.id=v.outcome_id "
            "JOIN eqos.capture_refs c ON c.id=v.capture_ref_id "
            "WHERE c.source_id=%s AND o.surface=%s AND v.column_index>0 AND v.row_label<>'' "
            "GROUP BY v.row_label ORDER BY v.row_label",
            (site, surface),
        ).fetchall()
    return tuple(
        LabelSample(
            label=label,
            units=frozenset(units),
            per_share=bool(
                re.search(r"per share|/share|₹/sh|\bEPS\b", " ".join([label, *units]), re.I)
            ),
        )
        for label, units in rows
    )
