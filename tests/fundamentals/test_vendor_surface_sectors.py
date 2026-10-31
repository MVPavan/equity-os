"""Tijori sector pages and their charts are fetched only for covered companies' sectors."""

from pathlib import Path

import pytest
from test_vendor_surface_due import FINANCIALS, NOW, due_rig, pick  # noqa: F401

from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_market import capture_market
from fundamentals.store.vendor_values_store import VendorValuesStore


@pytest.mark.pg
@pytest.mark.retained
def test_sector_pages_and_charts_follow_covered_companies_only(due_rig):  # noqa: F811
    rig, opener = due_rig, due_rig.opener
    covered, other = (f"https://www.tijorifinance.com/sector/{s}" for s in ("banking", "telecom"))
    overview = FINANCIALS.removesuffix("financials/")
    raw = Path(opener.rows[overview]["path"]).read_bytes()
    opener.overrides[overview] = raw.replace(b'"/sector/None"', b'"/sector/banking"'), 200
    marker = b'<a href="/api/v1/sector/ms-chart/999999/">x</a>'
    opener.overrides[other] = Path(opener.rows[covered]["path"]).read_bytes() + marker, 200
    sector = pick("sector-page")[0]
    # A sector page retained before the ruling, which no covered company belongs to.
    capture_market(
        rig.fetcher(),
        rig.store,
        rig.pool,
        VendorValuesStore(rig.pool),
        (),
        requests=(Request(spec=sector, url=other, ids=None, due_since=None),),
        scheduled=True,
    )
    charts = ("sector-ms-chart-api", "sector-company-opm-api", "sector-area-chart-api")
    rig.run(pick("search-page", "company-overview", "sector-page", *charts), NOW)
    # The search page publishes both sectors; only the covered company's own is fetched.
    assert covered in opener.calls and other not in opener.calls
    assert any("/api/v1/sector/" in url for url in opener.calls)
    assert not any("999999" in url for url in opener.calls)
