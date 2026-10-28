"""Code-only point extraction from retained Screener chart JSON."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from fundamentals.ingest.screener_financials_tables import read_number
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext


def screener_chart(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read exact numbers by dataset/point position, preserving display text."""
    document = json.loads(body.raw, parse_float=Decimal)
    metric_set = parse_qs(urlsplit(context.url).query)["q"][0]
    values = []
    for column, dataset in enumerate(document["datasets"]):
        for row, point in enumerate(dataset["values"]):
            raw = str(point[1])
            value, percent = read_number(raw)
            values.append(
                VendorValue(
                    table_key=metric_set,
                    row_index=row,
                    column_index=column,
                    locator=f"/datasets/{column}/values/{row}/1",
                    row_label=str(point[0]),
                    column_label=dataset["label"],
                    raw_text=raw,
                    value=value,
                    unit="percent" if percent else None,
                    expected_numeric=True,
                )
            )
    return tuple(values)
