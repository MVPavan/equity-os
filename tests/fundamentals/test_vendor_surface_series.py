"""G1 company series retain all cells and fail closed on broken reference bodies."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from vendor_surface_support import INDEX, capture_response, load_request_index

from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_parse import PARSERS, Body, ParseContext
from fundamentals.ingest.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from fundamentals.store.snapshot_store import SnapshotStore

CONTEXT = ParseContext(
    ids=None,
    basis=None,
    url="https://www.tijorifinance.com/api/v1/ind/chartdata/129/pe/",
    retrieved_at=datetime.now(UTC),
    body_sha256="fixture",
    capture_id="fixture",
)

EXPECTED = {
    "85ca8991672c": (4124, "27.02", "27.05"),
    "f5697fbd70c1": (4133, "2.9", "2.89"),
    "5cc959d74055": (42, "4210", "-21280"),
    "f7f7413feb1e": (900, "1063934.3234", "1244540.6906"),
    "4d8c7bb555a4": (79, "48.16", "46.92"),
    "a906f20883b0": (4133, "2.18", "2.18"),
    "bf7df2db9bca": (28, "49596", "59478"),
    "1f74eb477db2": (106, "5936.0", "12551.0"),
    "b96ddae02840": (9, "null", "21.5"),
    "ce2a1c735d60": (900, "1103186.1695", "1292805.7065"),
    "8af35915e9c8": (7783, "4.555", "4.525"),
    "e7283ebbfa86": (4133, "14.92", "14.87"),
    "7808286e39e1": (30, "0.0", "0.0"),
}
REFERENCES = list(
    {
        (row["id"], row["sha256"]): row
        for row in [
            *load_request_index().values(),
            *json.loads(INDEX.with_name("kinds-index.json").read_text()),
        ]
        if row["site"] == "tijori" and row["sha256"][:12] in EXPECTED and row["status"] == 200
    }.values()
)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("row", REFERENCES, ids=lambda row: row["id"] + "-" + row["sha256"][:12])
@pytest.mark.parametrize("truncated", [False, True])
def test_series_capture_keeps_points_or_records_failed(pg_db, tmp_path, row, truncated):
    """Wrong counts, numeric readings, positional collisions or partial writes must fail."""
    assert (Site.TIJORI, row["id"]) in PARSERS
    raw = Path(row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    store = SnapshotStore(tmp_path / "captures")
    spec = SurfaceSpec(
        site=Site.TIJORI,
        id=row["id"],
        scope=Scope.COMPANY,
        path=urlsplit(row["url"]).path,
        group=ParseGroup.SERIES,
        cadence=Cadence.DAILY,
    )
    with pg_db.runtime_pool() as pool:
        ref = capture_response(
            pool,
            store,
            tmp_path / "stops",
            Request(spec=spec, url=row["url"], ids=None, due_since=None),
            raw[:-1] if truncated else raw,
        )
        with pool.connection() as conn:
            status, count = conn.execute(
                "SELECT status,row_count FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone()
            cells = conn.execute(
                "SELECT locator,raw_text,value FROM eqos.vendor_values WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchall()
            assert conn.execute(
                "SELECT count(DISTINCT (table_key,row_index,column_index)) FROM eqos.vendor_values "
                "WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone() == (count,)
        if truncated:
            assert (status, count, cells) == ("FAILED", 0, [])
        else:
            count_expected, first, second = EXPECTED[row["sha256"][:12]]
            assert status in ("OK", "PARTIAL") and count == count_expected
            prefix = "/data"
            if row["id"] == "chartdata-price-api":
                prefix += "/eod_price"
            elif row["id"] in ("capex-api", "debt-api"):
                prefix += "/0/data"
            elif row["id"] == "revenue-mix-history-api":
                prefix = "/context/0/graphdata"
            elif row["id"] == "financial-statement-compare-api":
                prefix += "/0/" + urlsplit(row["url"]).path.split("/")[-1] + "/data/0/value"
            locators = [f"{prefix}/{i}/1" for i in (0, 1)]
            if row["id"] == "financial-statement-compare-api":
                locators = [f"{prefix}/{i}" for i in (0, 1)]
            elif row["url"].rstrip("/").endswith("/median-pe"):
                locators = ["/data/1d", "/data/1m"]
            by_locator = {locator: (text, value) for locator, text, value in cells}
            assert [by_locator[locator] for locator in locators] == [
                (text, None if text == "null" else Decimal(text)) for text in (first, second)
            ]


def test_valuation_rejects_unrelated_numeric_object():
    """A changed valuation shape must not be mistaken for median-PE horizons."""
    with pytest.raises(ValueError):
        PARSERS[Site.TIJORI, "chartdata-valuation-api"].parse(
            Body(raw=b'{"status":200,"data":{"changed":1}}'),
            CONTEXT,
        )


def test_string_envelope_keeps_lexemes_nulls_and_duplicate_series_names():
    """Numeric tokens survive both decoders, while labels cannot collapse series."""
    raw = json.dumps(
        {
            "status": 200,
            "data": '[{"name":"same","data":[[1,1e-8],[2,null]]},'
            '{"name":"same","data":[[1,"-2.00%"]]}]',
        }
    ).encode()
    cells = PARSERS[Site.TIJORI, "capex-api"].parse(Body(raw=raw), CONTEXT)
    assert [(cell.raw_text, cell.value, cell.unit) for cell in cells] == [
        ("1e-8", Decimal("1e-8"), None),
        ("null", None, None),
        ("-2.00%", Decimal("-2.00"), "%"),
    ]
    assert len({(cell.table_key, cell.row_index, cell.column_index) for cell in cells}) == 3


MARKET_EXPECTED = {
    "fii-api": (242, "/values/0", "615.99", "/values/1", "10047.07"),
    "hs-data-api": (720, "/0/import_value", "20", "/0/export_value", "569"),
    "macro-chart-api": (106, "/0/1", "11.38", "/1/1", "5.38"),
    "sector-ms-chart-api": (1611, "/0/data/0/1", "51.43", "/0/data/1/1", "52.35"),
    "sector-company-opm-api": (2389, "/0/data/0/1", "11.0", "/0/data/1/1", "11.2"),
    "index-data-api": (2620, "/0/1", "100.0", "/1/1", "100.213"),
    "index-metric-data-api": (3564, "/0/1", "38.42", "/1/1", "38.42"),
}
MARKET_REFERENCES = [
    row
    for row in load_request_index().values()
    if row["id"] in MARKET_EXPECTED and row["status"] == 200
]


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("row", MARKET_REFERENCES, ids=lambda row: row["id"])
@pytest.mark.parametrize("truncated", [False, True])
def test_market_series_capture_preserves_cells_or_fails(pg_db, tmp_path, row, truncated):
    """Market shapes must retain every point atomically, with HS identity in the key."""
    site = Site.SCREENER if row["site"] == "screener" else Site.TIJORI
    assert (site, row["id"]) in PARSERS
    raw = Path(row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    store = SnapshotStore(tmp_path / "captures")
    spec = SurfaceSpec(
        site=site,
        id=row["id"],
        scope=Scope.MARKET,
        path=urlsplit(row["url"]).path,
        group=ParseGroup.SERIES,
        cadence=Cadence.DAILY,
    )
    with pg_db.runtime_pool() as pool:
        ref = capture_response(
            pool,
            store,
            tmp_path / "stops",
            Request(spec=spec, url=row["url"], ids=None, due_since=None),
            raw.rstrip()[:-1] if truncated else raw,
        )
        with pool.connection() as conn:
            status, count, version = conn.execute(
                "SELECT status,row_count,parser_version FROM eqos.vendor_outcomes "
                "WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone()
            cells = conn.execute(
                "SELECT locator,raw_text,value,table_key,row_index,column_index "
                "FROM eqos.vendor_values WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchall()
        assert version == f"{row['site']}:{row['id']}.v1"
        if truncated:
            assert (status, count, cells) == ("FAILED", 0, [])
        else:
            expected, first_path, first, second_path, second = MARKET_EXPECTED[row["id"]]
            assert status in ("OK", "PARTIAL") and count == len(cells) == expected
            assert len({tuple(cell[3:]) for cell in cells}) == count
            by_locator = {cell[0]: cell[1:3] for cell in cells}
            assert [by_locator[path] for path in (first_path, second_path)] == [
                (text, Decimal(text)) for text in (first, second)
            ]
            if row["id"] == "hs-data-api":
                assert {cell[3] for cell in cells} == {"74031100"}
