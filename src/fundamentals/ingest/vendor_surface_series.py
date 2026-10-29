"""Code-only point extraction from retained Screener chart JSON."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any
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


class _Number(Decimal):
    """A JSON decimal retaining the original numeric token for raw_text."""

    raw_text: str

    def __new__(cls, raw: str) -> _Number:
        number = super().__new__(cls, raw)
        number.raw_text = raw
        return number


def _json(raw: bytes | str) -> Any:
    """Decode numeric tokens without a binary-float round trip."""
    return json.loads(raw, parse_int=_Number, parse_float=_Number)


def tijori_data(body: bytes) -> Any:
    """Unwrap successful Tijori data, including its JSON-string variant."""
    envelope = _json(body)
    if not isinstance(envelope, dict) or envelope["status"] != 200:
        raise ValueError("invalid Tijori envelope")
    data = envelope["data"]
    return _json(data) if isinstance(data, str) else data


def _cell(
    raw: Any,
    table: str,
    row: int,
    column: int,
    locator: str,
    row_label: str,
    column_label: str,
    basis: str | None = None,
) -> VendorValue:
    """Keep the original token and its independently addressable position."""
    if raw is not None and not isinstance(raw, (Decimal, str)):
        raise ValueError("invalid numeric cell")
    text = raw.raw_text if isinstance(raw, _Number) else str(raw) if raw is not None else "null"
    value = None if raw is None else Decimal(text.removesuffix("%").replace(",", ""))
    if value is not None and not value.is_finite():
        raise ValueError("non-finite numeric cell")
    return VendorValue(
        table_key=table,
        row_index=row,
        column_index=column,
        locator=locator,
        row_label=row_label,
        column_label=column_label,
        raw_text=text,
        value=value,
        unit="%" if text.endswith("%") else None,
        basis=basis,
        expected_numeric=True,
    )


def _pairs(data: Any, path: str, label: str) -> tuple[VendorValue, ...]:
    """Read a positional date/value series; malformed points fail the whole parse."""
    if not isinstance(data, list):
        raise ValueError("series must be an array")
    values = []
    for row, point in enumerate(data):
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not isinstance(point[0], (Decimal, str))
        ):
            raise ValueError("invalid series point")
        values.append(_cell(point[1], path, row, 0, f"{path}/{row}/1", str(point[0]), label))
    return tuple(values)


def tijori_price(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read end-of-day and intraday points plus the intraday headline cells."""
    data = tijori_data(body.raw)
    intraday = data["intraday_price"]
    values = _pairs(data["eod_price"], "/data/eod_price", "eod_price")
    values += _pairs(
        intraday["intraday_price"], "/data/intraday_price/intraday_price", "intraday_price"
    )
    return values + tuple(
        _cell(
            intraday[key], "/data/intraday_price", row, 0, f"/data/intraday_price/{key}", key, key
        )
        for row, key in enumerate(("latest_price", "change", "per_change"))
    )


def tijori_valuation(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read valuation history; the retained median-pe variant uses horizons."""
    data = tijori_data(body.raw)
    if urlsplit(context.url).path.rstrip("/").endswith("/median-pe"):
        return tijori_median_pe(body, context)
    return _pairs(data, "/data", urlsplit(context.url).path.rstrip("/").split("/")[-1])


def tijori_median_pe(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read every median-PE horizon, including explicitly missing values."""
    data = tijori_data(body.raw)
    if not isinstance(data, dict):
        raise ValueError("median PE must be an object")
    return tuple(
        _cell(raw, "/data", row, 0, f"/data/{key}", key, "median-pe")
        for row, (key, raw) in enumerate(data.items())
    )


def _named(data: Any, path: str, label_key: str, points_key: str) -> tuple[VendorValue, ...]:
    """Read named series without making mutable names their positional identity."""
    if not isinstance(data, list):
        raise ValueError("named series must be an array")
    values: tuple[VendorValue, ...] = ()
    for index, series in enumerate(data):
        if not isinstance(series, dict) or not isinstance(series[label_key], str):
            raise ValueError("invalid named series")
        points = series[points_key]
        values += _pairs(
            _json(points) if isinstance(points, str) else points,
            f"{path}/{index}/{points_key}",
            series[label_key],
        )
    return values


def tijori_capex(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read all retained capital-expenditure series."""
    return _named(tijori_data(body.raw), "/data", "name", "data")


def tijori_debt(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read all retained debt series."""
    return _named(tijori_data(body.raw), "/data", "name", "data")


def tijori_revenue_mix(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read the history endpoint's context/graphdata envelope."""
    envelope = _json(body.raw)
    if envelope["status"] != 200 or envelope["success"] is not True:
        raise ValueError("invalid revenue-mix envelope")
    return _named(envelope["context"], "/context", "fieldname", "graphdata")


def tijori_popup(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read every financial-popup history point."""
    return _pairs(
        tijori_data(body.raw), "/data", urlsplit(context.url).path.rstrip("/").split("/")[-1]
    )


def tijori_statement_compare(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Read all nested statement values, growth and composition cells by position."""
    values: list[VendorValue] = []

    def rows(data: Any, path: str, dates: list[str], basis: str) -> None:
        if not isinstance(data, list):
            raise ValueError("statement rows must be an array")
        for index, row in enumerate(data):
            for field in ("value", "value_yoy", "value_perc"):
                if not isinstance(row[field], list) or len(row[field]) != len(dates):
                    raise ValueError("statement columns differ from report dates")
                for column, raw in enumerate(row[field]):
                    values.append(
                        _cell(
                            raw,
                            path + "/" + field,
                            index,
                            column,
                            f"{path}/{index}/{field}/{column}",
                            row["name"],
                            dates[column],
                            basis,
                        )
                    )
            children = row["sub_section"]
            child_path = f"{path}/{index}/sub_section"
            rows([] if children == "" else children, child_path, dates, basis)

    data = tijori_data(body.raw)
    if not isinstance(data, list):
        raise ValueError("statement tables must be an array")
    for index, tables in enumerate(data):
        for key, encoded in tables.items():
            table = _json(encoded)
            dates = table["report_dates"]
            if (
                not isinstance(dates, list)
                or not dates
                or not all(isinstance(date, str) for date in dates)
            ):
                raise ValueError("invalid statement dates")
            path = f"/data/{index}/{key}"
            basis = "consolidated" if "_c_" in key else "standalone"
            rows(table["data"], path + "/data", dates, basis)
    return tuple(values)
