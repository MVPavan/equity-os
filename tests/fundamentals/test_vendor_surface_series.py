"""G1 company series retain all cells and fail closed on broken reference bodies."""

import hashlib
import io
from decimal import Decimal
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr
from vendor_surface_support import RetainedOpener, load_request_index

from fundamentals.ingest.vendor_surface_capture import Request, capture
from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import PARSERS
from fundamentals.ingest.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

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
REFERENCES = [
    row
    for row in load_request_index().values()
    if row["site"] == "tijori" and row["sha256"][:12] in EXPECTED and row["status"] == 200
]


class SeriesOpener(RetainedOpener):
    """Serve exactly the selected retained response at the HTTP boundary."""

    def __init__(self, raw):
        super().__init__()
        self.raw = raw

    def open(self, request, timeout):
        headers = Message()
        headers["Content-Type"] = "application/json"
        return HTTPError(request.full_url, 200, "fixture", headers, io.BytesIO(self.raw))


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
    session = SiteSession(
        site=Site.TIJORI, session_cookie=SecretStr("fixture"), cookie_name="sessionid"
    )
    with pg_db.runtime_pool() as pool:
        locks = PgSiteLock(pool)
        try:
            fetcher = VendorFetcher(
                store,
                {Site.TIJORI: session},
                SeriesOpener(raw[:-1] if truncated else raw),
                tmp_path / "stops",
                locks,
                spacing_seconds=0,
            )
            ref, _ = capture(
                fetcher,
                store,
                pool,
                VendorValuesStore(pool),
                Request(spec=spec, url=row["url"], ids=None, due_since=None),
            )
        finally:
            locks.close()
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
            elif row["id"] == "chartdata-median-pe-api":
                locators = ["/data/1d", "/data/1m"]
            by_locator = {locator: (text, value) for locator, text, value in cells}
            assert [by_locator[locator] for locator in locators] == [
                (text, None if text == "null" else Decimal(text)) for text in (first, second)
            ]
