"""G1 company series retain all cells and fail closed on broken reference bodies.

PYTEST_DONT_REWRITE: failing assertions must not print licensed vendor data.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from vendor_surface_support import INDEX, capture_response, load_request_index

from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS, Body, ParseContext
from equity_os.extraction.surfaces.vendor_surface_series import tijori_data
from equity_os.sourcing.surfaces.vendor_surface_capture import Request
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site
from equity_os.sourcing.surfaces.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

CONTEXT = ParseContext(
    ids=None,
    basis=None,
    url="https://www.tijorifinance.com/api/v1/ind/chartdata/129/pe/",
    retrieved_at=datetime.now(UTC),
    body_sha256="fixture",
    capture_id="fixture",
)

EXPECTED = {
    "85ca8991672c": (
        4124,
        "952cc81fd8998a668271de513515e5660058a5ee83e9e5ef8088c2e350328f18",
        "5cd727242e802d8811fae4d1af1147e0249f3cad239ddcd68282091eeed399b1",
    ),
    "f5697fbd70c1": (
        4133,
        "f491e65f8d4b8dbec7621fcedaf1b7a4b21bf6cfe8070f407548a6334dc55ccd",
        "df67abc82f091e1efd1c9891462b5f2cf2c69c2455a13fcc636a1ea7b15f8fa3",
    ),
    "5cc959d74055": (
        42,
        "0c4d6bf3265be8b2d1fb8b985782b838fb5485844ca52fed0d80464be4328ce2",
        "b7987fe3c78b6e2e5519764776165296e76aa026caefe72d718e6dfe611c863e",
    ),
    "f7f7413feb1e": (
        900,
        "e96780e7e153822e0bc1a575430d8c9625be5810f09fa98d9ab29990ae34fb1b",
        "4db73a2bc33dcc571d5683ae1f73603fc5f8f5e57d970497cfe13fc594e4c652",
    ),
    "4d8c7bb555a4": (
        79,
        "328c0dce07d6faafcd4c69a53a5b918a77fc939e47aa107dc10a3274c3ca3a1d",
        "d5fa68c45477eb86a4af95b61b277357947500c6a1b8fd5d7a2e22338fc33085",
    ),
    "a906f20883b0": (
        4133,
        "6168a49582bc6332dac01fad591381aceb1b63036ce799ba373cdaba11b2ef6f",
        "6168a49582bc6332dac01fad591381aceb1b63036ce799ba373cdaba11b2ef6f",
    ),
    "bf7df2db9bca": (
        28,
        "cdc3323aafd9bd83a983ce86e10b64dbc9205f55aecb15c772f963995cb23ee0",
        "145c0f8f5a3776370e37317ec597a1f49b5e38d10b377d8f1ac06caa64d8d227",
    ),
    "1f74eb477db2": (
        106,
        "2b211a9f4078ff662f4dd6e28884472718c9c3f426cfc111754149f0cd3067b8",
        "34fa5b6ecb1f31b47a7d09ead6c374397812e37c86e2b8189642dcdd02dcff08",
    ),
    "b96ddae02840": (
        9,
        "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "a20fa123d4d8977782c80981ddbe6177a8d5ba294eaffd08a88669e246c37110",
    ),
    "ce2a1c735d60": (
        900,
        "782c1f646c74f0476b719d7a42e1027cfc38f33652ff074f448ba77bfaf25d6e",
        "1dc2a37c16a83c280083c60a46aaeaa9719544eba6f7336fcad2687d3c2fa6b5",
    ),
    "8af35915e9c8": (
        7783,
        "11df90ee562d5b2de95edd61ec5c160cfdbb819fdb7ada24c95ab9bee54bc68a",
        "d269a230c448b72e723e6c8f449e59f9f85dfcfa48f20500800f84fe8a3e0d87",
    ),
    "e7283ebbfa86": (
        4133,
        "4829efbfa8d976f1410ea1544dd0c48339d0d9e9c20fd2ac6a740ded4e6a4cd1",
        "1f035024bf808b39348eee0bb0924c2a411d0b1a58ef3dcd8792b118efa07f36",
    ),
    "7808286e39e1": (
        30,
        "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7",
        "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7",
    ),
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


def _digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("row", REFERENCES, ids=lambda row: row["id"] + "-" + row["sha256"][:12])
@pytest.mark.parametrize("truncated", [False, True])
def test_series_capture_keeps_points_or_records_failed(pg_db, tmp_path, row, truncated):
    """Wrong counts, numeric readings, positional collisions or partial writes must fail."""
    assert (Site.TIJORI, row["id"]) in PARSERS
    raw = Path(row["path"]).read_bytes()
    digest_ok = hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert digest_ok, "retained body digest mismatch"
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
            got = [by_locator[locator] for locator in locators]
            assert [_digest(text) for text, _ in got] == [first, second]
            assert all(value == (None if text == "null" else Decimal(text)) for text, value in got)


def test_valuation_rejects_unrelated_numeric_object():
    """A changed valuation shape must not be mistaken for median-PE horizons."""
    with pytest.raises(ValueError):
        PARSERS[Site.TIJORI, "chartdata-valuation-api"].parse(
            Body(raw=b'{"status":200,"data":{"changed":1}}'),
            CONTEXT,
        )


def test_envelope_without_status_still_reads_and_a_bad_status_still_refuses():
    """Tijori dropped `status` from some envelopes on 2026-10-31 (canary T4)."""
    data = json.dumps({"eod_price": []})
    assert tijori_data(json.dumps({"data": data}).encode()) == {"eod_price": []}
    with pytest.raises(ValueError):
        tijori_data(json.dumps({"status": 500, "data": data}).encode())


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
    "fii-api": (
        242,
        "/values/0",
        "d2c0352a5c8b1a98661d86e87111c102e04bf6fa506fccf8952fb6b6343718e1",
        "/values/1",
        "1a4fa86d38bee14996552ff3e6295be6bfac2685781e3f798d04354c6b04270e",
    ),
    "hs-data-api": (
        720,
        "/0/import_value",
        "f5ca38f748a1d6eaf726b8a42fb575c3c71f1864a8143301782de13da2d9202b",
        "/0/export_value",
        "c7ce483fd1cc5fd498e7e2a09851c65f89a33a6837f66d9fbb36e5e5f70b41a2",
    ),
    "macro-chart-api": (
        106,
        "/0/1",
        "62609ee6a8d2c894b76b6e899196e3f729dcfe76d8c3fc61eb5262f1c5f1a9b3",
        "/1/1",
        "676bb5c3aaa5adca1410698d951f0092620f978a7c42003b9943bb46c18f3ff0",
    ),
    "sector-ms-chart-api": (
        1611,
        "/0/data/0/1",
        "96512ba2bdf381315e2c7b95c9be91f8479202615eb12d5c28b14a27d02c1808",
        "/0/data/1/1",
        "651eeefbde20002e635b888c31377f8557ba96512ff2d8f3bede03c32a1cf5ac",
    ),
    "sector-company-opm-api": (
        2389,
        "/0/data/0/1",
        "56824d16dcb61c982fc31a731cf6f20594c0a3f1da2aff349ee804bf1c4544d1",
        "/0/data/1/1",
        "038c616c58034ec577ee376a5ebf31164c4250b057c13acd5fc197711266e488",
    ),
    "index-data-api": (
        2620,
        "/0/1",
        "43b87f618caab482ebe4976c92bcd6ad308b48055f1c27b4c574f3e31d7683e0",
        "/1/1",
        "8270fdd45ffeb8d4a3cd34d0c7498f148b264d5865f957f5d53ef1fd5fc98670",
    ),
    "index-metric-data-api": (
        3564,
        "/0/1",
        "dfbd52ee3c6339ae33822b73797ac9717d792d0fbb3d70a0f17709514c86dd7a",
        "/1/1",
        "dfbd52ee3c6339ae33822b73797ac9717d792d0fbb3d70a0f17709514c86dd7a",
    ),
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
    digest_ok = hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert digest_ok, "retained body digest mismatch"
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
            got = [by_locator[path] for path in (first_path, second_path)]
            assert [_digest(text) for text, _ in got] == [first, second]
            assert all(value == Decimal(text) for text, value in got)
            if row["id"] == "hs-data-api":
                assert {cell[3] for cell in cells} == {"74031100"}


def test_statement_compare_reads_live_ratio_rows_and_quarterly_growth_axis():
    """APARINDS shapes (2026-10-30): ratio rows omit value_perc; quarterly growth has its own
    shorter axis, and a group header pads it with nulls on the main axis."""

    def row(name, value, yoy, perc=None, children=""):
        shares = {} if perc is None else {"value_perc": perc}
        return {"name": name, "value": value, "value_yoy": yoy, **shares, "sub_section": children}

    annual = {
        "report_dates": ["Mar 2025", "Mar 2026"],
        "data": [row("Sales", [10, 12], [None, "20%"], [100, 100]), row("OPM (%)", [9, 8], [1, 2])],
    }
    quarterly = {
        "report_dates": ["Jun 2026", "Sep 2026"],
        "report_dates_yoy": ["Sep 2026"],
        "data": [
            row("Net Sales", [5, 6], ["25%"], [100, 100]),
            row(
                "Quarterly Ratios",
                [0, 0],
                [None, None],
                [None, None],
                [row("EPS", [1, 2], ["9%"], [None, None])],
            ),
        ],
    }

    def cells(tables):
        raw = json.dumps({"data": [{k: json.dumps(v) for k, v in tables.items()}]}).encode()
        return PARSERS[Site.TIJORI, "financial-statement-compare-api"].parse(Body(raw=raw), CONTEXT)

    read = {
        (c.row_label, c.table_key.rsplit("/", 1)[1], c.column_label): c.raw_text
        for c in cells({"pl_c_s": annual, "qt_c": quarterly})
    }
    assert read[("Sales", "value_perc", "Mar 2026")] == "100"
    assert not any(label == "OPM (%)" and field == "value_perc" for label, field, _ in read)
    assert read[("Net Sales", "value_yoy", "Sep 2026")] == "25%"
    assert read[("EPS", "value_yoy", "Sep 2026")] == "9%"
    assert read[("Quarterly Ratios", "value_yoy", "Jun 2026")] == "null"
    assert PARSERS[Site.TIJORI, "financial-statement-compare-api"].version.endswith(".v2")
    # Still refused: a breakdown one column short (live pl_s_*) has no axis naming the gap,
    # and a real growth reading laid on the main axis of a quarterly table.
    short = {**annual, "data": [row("Others", [1], [None], [5])]}
    misplaced = {**quarterly, "data": [row("Net Sales", [5, 6], ["1%", "2%"], [100, 100])]}
    for tables in ({"pl_s_s": short}, {"qt_s": misplaced}):
        with pytest.raises(ValueError, match="report dates"):
            cells(tables)
