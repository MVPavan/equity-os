"""Raw-first market traversal and durable pagination over retained responses."""

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr
from vendor_surface_support import load_request_index

from fundamentals.ingest import vendor_surface_market as market
from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_expand import EXPANSIONS
from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import (
    PARSERS,
    Body,
    ParseContext,
    ParserEntry,
    register_tables,
)
from fundamentals.ingest.vendor_surface_specs import (
    Cadence,
    ParseGroup,
    Scope,
    SurfaceSpec,
    load_specs,
)
from fundamentals.ingest.vendor_surface_tables import market_parser
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

MARKET_SPECS = load_specs(
    Path("config/vendor_surface/surfaces.yaml"), Path("docs/research/vendor-surface/catalog.yaml")
)
register_tables(MARKET_SPECS)  # The CLI root binds table parsers; this suite calls capture_market.


class MarketOpener(OpenerDirector):
    """Serve retained bodies and explicit synthetic pagination at the HTTP boundary."""

    def __init__(self):
        super().__init__()
        self.rows, self.calls, self.overrides = load_request_index(), [], {}

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        row = self.rows.get(request.full_url)
        raw, status = b"unretained", 404
        if row and row.get("path"):
            raw, status = Path(row["path"]).read_bytes(), row.get("status", 200)
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        raw, status = self.overrides.get(request.full_url, (raw, status))
        return HTTPError(request.full_url, status, "fixture", {}, io.BytesIO(raw))


@pytest.fixture
def market_rig(pg_db, tmp_path):
    opener = MarketOpener()
    store = SnapshotStore(tmp_path / "captures")
    with pg_db.runtime_pool() as pool:
        locks = PgSiteLock(pool)
        fetcher = VendorFetcher(
            store,
            {
                site: SiteSession(
                    site=site, session_cookie=SecretStr("fake"), cookie_name="sessionid"
                )
                for site in Site
            },
            opener,
            tmp_path / "stops",
            locks,
            spacing_seconds=0,
        )
        try:
            yield (
                opener,
                pool,
                lambda specs, **kwargs: market.capture_market(
                    fetcher, store, pool, VendorValuesStore(pool), specs, **kwargs
                ),
            )
        finally:
            locks.close()


@pytest.mark.pg
@pytest.mark.retained
def test_retained_market_hub_reaches_four_levels(market_rig):
    opener, pool, run = market_rig
    hub = SurfaceSpec(
        site=Site.SCREENER,
        id="market-overview",
        path="/market/",
        scope=Scope.MARKET,
        group=ParseGroup.NONE,
        cadence=Cadence.WEEKLY,
    )
    report = run((hub, next(s for s in MARKET_SPECS if s.id == "market-level")))
    depths = {
        len(urlsplit(url).path.strip("/").split("/")) - 1
        for url in opener.calls
        if "/market/IN" in url
    }
    assert depths == {1, 2, 3, 4}
    assert report.incomplete  # Unretained child pages must remain explicit gaps.
    with pool.connection() as conn:
        assert conn.execute("SELECT count(*) FROM eqos.capture_addresses").fetchone()[0] == len(
            opener.calls
        )


@pytest.mark.pg
def test_page_cap_resumes_and_advances_only_after_boundary(market_rig, monkeypatch):

    monkeypatch.setattr(market, "MAX_FEED_PAGES", 2)
    opener, pool, run = market_rig
    spec = next(s for s in MARKET_SPECS if s.id == "announcements-feed")
    url = "https://www.screener.in/announcements/all/?p=1"
    request = Request(spec=spec, url=url, ids=None, due_since=None)
    for page in range(1, 6):
        next_link = f'<a href="?p={page + 1}">Next</a>' if page < 5 else ""
        raw = (
            '<main><div class="announcement-item"><a href="/company/FIXTURE/">Fixture</a>'
            f'<a href="/event/{page}">Event</a><time datetime="2026-10-28">Date</time>'
            f"</div>{next_link}</main>"
        ).encode()
        opener.overrides[f"https://www.screener.in/announcements/all/?p={page}"] = raw, 200
    for expected_pages, resume in [([1, 2], 2), ([2, 3, 4], 4), ([4, 5], None)]:
        opener.calls.clear()
        report = run((), requests=(request,))
        assert opener.calls == [
            f"https://www.screener.in/announcements/all/?p={page}" for page in expected_pages
        ]
        state = market.progress(pool, market.traversal_key(request))
        assert state.resume_page == resume
        assert bool(report.incomplete) == (resume is not None)
        assert (state.boundary.row_id if state.boundary else None) == (
            "/event/1" if resume is None else None
        )
    level = next(s for s in MARKET_SPECS if s.id == "market-level")
    in10, in11 = (
        Request(
            spec=level, url=f"https://www.screener.in/market/{code}/?p=2", ids=None, due_since=None
        )
        for code in ("IN10", "IN11")
    )
    assert market.traversal_key(in10) != market.traversal_key(in11)
    assert market.traversal_key(in10) == market.traversal_key(
        in10.model_copy(update={"url": "https://www.screener.in/market/IN10/"})
    )
    # Same date, new event: only the stable row id can stop this incremental scan.
    opener.overrides[url] = opener.overrides[url][0].replace(b"/event/1", b"/event/new"), 200
    second = "https://www.screener.in/announcements/all/?p=2"
    opener.overrides[second] = opener.overrides[second][0].replace(b"/event/2", b"/event/1"), 200
    opener.calls.clear()
    assert not run((), requests=(request,)).incomplete
    assert opener.calls == [url, second]
    assert market.progress(pool, market.traversal_key(request)).boundary.row_id == "/event/new"


@pytest.mark.pg
def test_capped_date_window_is_recovered_from_retained_url(market_rig, monkeypatch):
    from datetime import date
    from urllib.parse import parse_qs

    monkeypatch.setattr(market, "MAX_FEED_PAGES", 2)
    opener, pool, run = market_rig
    spec = SurfaceSpec(
        site=Site.TIJORI,
        id="date-fixture",
        path="/fixture/",
        scope=Scope.MARKET,
        group=ParseGroup.TABLE,
        cadence=Cadence.DAILY,
        feed=True,
        selector="//table",
    )
    monkeypatch.setitem(
        PARSERS,
        (spec.site, spec.id),
        ParserEntry(version="tijori:date-fixture.v1", parse=market_parser(spec)),
    )
    request = Request(
        spec=spec, url="https://www.tijorifinance.com/fixture/?page=1", ids=None, due_since=None
    )
    window = "01/01/1970,10/28/2026"
    for page in range(1, 6):
        raw = (
            "<table><thead><tr><th>Company</th><th>Date</th></tr></thead><tbody><tr><td>"
            '<a href="/company/FIXTURE/">Fixture</a>'
            f'<a href="/event/{page}">Event</a></td><td>2026-10-28</td></tr></tbody></table>'
        ).encode()
        if page < 5:
            raw += b'<button class="show_more">More</button>'
        opener.overrides[market.query_url(request.url, page=str(page), daterange=window)] = raw, 200
    for day in [28, 29, 30]:
        opener.calls.clear()
        run((), requests=(request,), today=date(2026, 10, day))
        assert {parse_qs(urlsplit(url).query)["daterange"][0] for url in opener.calls} == {window}
    state = market.progress(pool, market.traversal_key(request))
    assert state.resume_url is None and state.boundary.date_to == date(2026, 10, 28)
    key_other_day = market.traversal_key(
        request.model_copy(
            update={"url": market.query_url(request.url, daterange="10/28/2026,10/31/2026")}
        )
    )
    assert key_other_day == market.traversal_key(request)


@pytest.mark.pg
@pytest.mark.retained
def test_timeline_uses_retained_cursor_until_exhausted(market_rig):
    from urllib.parse import parse_qs

    from fundamentals.ingest.vendor_surface_parse import Body, CompanyIds

    opener, pool, run = market_rig
    row = next(r for r in opener.rows.values() if r["id"] == "company-timeline-api")
    spec = next(s for s in MARKET_SPECS if s.id == row["id"])
    ids = CompanyIds(
        nse_symbol="HDFCBANK",
        isin="INE040A01034",
        tijori_slug="hdfc-bank-limited",
        tijori_company_id=129,
        screener_company_id=None,
        topology=None,
    )
    request = Request(spec=spec, url=row["url"], ids=ids, due_since=None)
    body = Body(raw=Path(row["path"]).read_bytes())
    cursor = body.tree().xpath('//tr[contains(@class,"d-none")]/td')[0].text_content().strip()
    terminal = body.raw.replace(b"True</td>", b"False</td>")
    assert terminal != body.raw
    next_url = market.query_url(row["url"], timestamp=cursor)
    opener.overrides[next_url] = terminal, 200
    report = run((), requests=(request,))
    assert not report.incomplete and report.completed == 2
    assert parse_qs(urlsplit(opener.calls[-1]).query)["timestamp"] == [cursor]
    assert market.progress(pool, market.traversal_key(request)).resume_page is None


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "hub_names",
    [
        "explore screens-list product-prices markets macro people-search",
        "sector-page ideas-dashboard filter-popular-queries-api filter-public-queries-api",
    ],
)
def test_retained_finite_expansions_and_missing_advertisements(market_rig, hub_names):

    opener, pool, run = market_rig
    hubs = set(hub_names.split())
    requests = tuple(
        Request(
            spec=next(
                s
                for s in MARKET_SPECS
                if s.id == row["id"]
                and s.site == (Site.SCREENER if row["site"] == "screener" else Site.TIJORI)
            ),
            url=row["url"],
            ids=None,
            due_since=None,
        )
        for row in opener.rows.values()
        if row["id"] in hubs and row.get("status") == 200
    )
    report = run(MARKET_SPECS, requests=requests)
    expected = (
        (
            "/people/",
            "/screens/",
            "/api/v1/macro/chart/",
            "/api/v1/sector/index-data/",
            "/api/v1/sector/index-metric-data/",
        )
        if "markets" in hubs
        else (
            "/api/v1/sector/ms-chart/",
            "/api/v1/sector/company-opm/",
            "/api/v1/sector/area-chart/",
            "/ideas-dashboard/",
            "/api/filter_queries/popular-query/results/",
        )
    )
    assert all(
        any(urlsplit(url).path.startswith(prefix) for url in opener.calls) for prefix in expected
    )
    if "markets" in hubs:
        for site, surface in [
            ("screener", "index-page"),
            ("screener", "hs-data-api"),
            ("screener", "commodity-page"),
            ("screener", "user-public-profile"),
            ("tijori", "sector-page"),
        ]:
            assert f"{site}:{surface}: no advertised children" in report.incomplete
    assert not any("/user/account/" in url for url in opener.calls)


def retained_context(row, spec):
    """The expansion context of one retained parent body for one child surface."""
    return ParseContext(
        ids=None,
        basis=None,
        url=row["url"],
        retrieved_at=datetime(2026, 10, 28, tzinfo=UTC),
        body_sha256=row["sha256"],
        capture_id="retained-market",
        parent={"spec": spec.model_dump()},
    )


@pytest.mark.retained
def test_widget_requests_follow_the_expanding_metric_mapping():
    spec = next(s for s in MARKET_SPECS if s.id == "markets-indices-widget-api")
    row = next(r for r in load_request_index().values() if r["id"] == "markets")
    raw = Path(row["path"]).read_bytes()
    metrics = Body(raw=raw).tree().xpath('//*[contains(@class,"expanding_metric")]')
    urls = [r.url for r in EXPANSIONS[spec.expand](Body(raw=raw), retained_context(row, spec))]
    # The hub script requests only what a clicked metric names: its table, row and cell.
    assert len(urls) == len(metrics)
    widget = metrics[0].xpath("ancestor::table[1]/@data-widget")[0]
    blank = raw.replace(f'data-widget="{widget}"'.encode(), b'data-widget=""')
    fewer = EXPANSIONS[spec.expand](Body(raw=blank), retained_context(row, spec))
    assert 0 < len(fewer) < len(urls)
    assert all("//" not in urlsplit(r.url).path for r in fewer)
