"""Code-only point extraction from retained Screener chart JSON."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext


def screener_chart(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read exact numbers by dataset/point position, preserving display text."""

    def valid_value(value: object) -> bool:
        return (
            value is None
            or isinstance(value, tuple)
            or (
                isinstance(value, str)
                and re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", value) is not None
            )
        )

    # A tuple tags a JSON number while retaining its exact lexeme, unlike a JSON string.
    document = json.loads(body.raw, parse_float=lambda raw: (raw,), parse_int=lambda raw: (raw,))
    if not isinstance(document, dict) or not isinstance(document.get("datasets"), list):
        raise ValueError("chart datasets must be an array")
    metric_set = parse_qs(urlsplit(context.url).query)["q"][0]
    values = []
    for column, dataset in enumerate(document["datasets"]):
        if (
            not isinstance(dataset, dict)
            or not isinstance(dataset.get("label"), str)
            or not isinstance(dataset.get("values"), list)
        ):
            raise ValueError("invalid chart dataset")
        for row, point in enumerate(dataset["values"]):
            if (
                not isinstance(point, list)
                or len(point) not in (2, 3)
                or not isinstance(point[0], str)
                or not valid_value(point[1])
                or (
                    len(point) == 3
                    and (
                        not isinstance(point[2], dict)
                        or point[2].keys() != {"delivery"}
                        or not valid_value(point[2]["delivery"])
                    )
                )
            ):
                raise ValueError("invalid chart point or delivery metadata")
            raw = point[1][0] if isinstance(point[1], tuple) else point[1]
            value = Decimal(raw) if raw is not None else None
            values.append(
                VendorValue(
                    table_key=metric_set,
                    row_index=row,
                    column_index=column,
                    locator=f"/datasets/{column}/values/{row}/1",
                    row_label=str(point[0]),
                    column_label=dataset["label"],
                    raw_text=raw if raw is not None else "null",
                    value=value,
                    expected_numeric=True,
                )
            )
    return tuple(values)
