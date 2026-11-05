"""Raw-first market traversal and durable pagination over retained responses."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr
from vendor_surface_support import RetainedResponseOpener, load_request_index

from equity_os.extraction.surfaces.vendor_surface_parse import (
    PARSERS,
    Body,
    ParseContext,
    ParserEntry,
    register_tables,
)
from equity_os.extraction.surfaces.vendor_surface_tables import market_parser
from equity_os.sourcing.surfaces import vendor_surface_market as market
from equity_os.sourcing.surfaces.vendor_surface_capture import Request
from equity_os.sourcing.surfaces.vendor_surface_due import is_due
from equity_os.sourcing.surfaces.vendor_surface_expand import EXPANSIONS, MARKET_PARENTS
from equity_os.sourcing.surfaces.vendor_surface_fetch import (
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from equity_os.sourcing.surfaces.vendor_surface_specs import (
    SITE_NAME,
    Cadence,
    ParseGroup,
    Scope,
    SurfaceSpec,
    load_specs,
)
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import VendorValuesStore

MARKET_SPECS = load_specs(
    Path("config/sourcing/vendor_surface/surfaces.yaml"),
    Path("docs/research/vendor-surface/catalog.yaml"),
)
register_tables(MARKET_SPECS)  # The CLI root binds table parsers; this suite calls capture_market.


# Rows outside the plan's traversal table whose only retained advertisement is never fetched.
MARKET_GAPS = {
    "capsule": "advertised only on the account dashboard (/dash/), which is not traversed",
    "insider-summary": "advertised only on the account dashboard; its retained fetch is a 302",
}


MarketOpener = RetainedResponseOpener


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

    from equity_os.extraction.surfaces.vendor_surface_parse import Body, CompanyIds

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
def test_timeline_resumes_past_an_unreadable_page_and_finishes(market_rig):
    # An unreadable page records no progress; the next run must resume and reach the end, or
    # the timeline root stays unusable and the canary reports the company overdue forever.
    from equity_os.extraction.surfaces.vendor_surface_parse import Body, CompanyIds

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
    next_url = market.query_url(row["url"], timestamp=cursor)
    opener.overrides[next_url] = b"<table></table>", 200
    assert run((), requests=(request,)).incomplete
    opener.overrides[next_url] = body.raw.replace(b"True</td>", b"False</td>"), 200
    report = run((), requests=(request,))
    assert not report.incomplete and opener.calls[-1] == next_url
    assert market.progress(pool, market.traversal_key(request)).resume_page is None


@pytest.mark.pg
@pytest.mark.retained
def test_timeline_finishes_on_an_empty_last_page(market_rig):
    # Tijori's has-more flag stays True on the last page of events and the next page renders
    # only a blank pager row; reading that page is what ends the traversal.
    from equity_os.extraction.surfaces.vendor_surface_parse import Body, CompanyIds

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
    next_url = market.query_url(row["url"], timestamp=cursor)
    opener.overrides[next_url] = b'<tr class="d-none"><td> </td><td></td></tr>', 200
    report = run((), requests=(request,))
    assert not report.incomplete and opener.calls[-1] == next_url
    assert market.progress(pool, market.traversal_key(request)).resume_page is None


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "hub_names",
    [
        "explore screens-list hs-search-api search-page markets macro people-search",
        "sector-page screen-page filter-popular-queries-api",
    ],
)
def test_retained_finite_expansions_reach_every_level(market_rig, hub_names):
    opener, pool, run = market_rig
    hubs = set(hub_names.split())
    requests = tuple(
        Request(
            spec=next(
                s for s in MARKET_SPECS if s.id == row["id"] and SITE_NAME[s.site] == row["site"]
            ),
            url=row["url"],
            ids=None,
            due_since=None,
        )
        for row in opener.rows.values()
        if row["id"] in hubs and row.get("status") == 200 and row["kind"] == "response"
    )
    report = run(MARKET_SPECS, requests=requests)
    expected = (
        (
            "/people/",
            "/screens/",
            "/commodity/",
            "/api/hs/",
            "/api/v1/macro/chart/",
            "/api/v1/sector/index-data/",
        )
        if "markets" in hubs
        else (
            "/api/v1/sector/ms-chart/",
            "/api/v1/sector/company-opm/",
            "/api/v1/sector/area-chart/",
            "/user/",
        )
    )
    assert all(
        any(urlsplit(url).path.startswith(prefix) for url in opener.calls) for prefix in expected
    )
    gaps = {entry for entry in report.incomplete if entry.endswith("no advertised children")}
    assert gaps == ({"screener:capsule: no advertised children"} if "explore" in hubs else set())
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
@pytest.mark.parametrize(
    "spec", [s for s in MARKET_SPECS if s.expand in MARKET_PARENTS], ids=lambda s: s.id
)
def test_every_traversal_row_has_retained_children(spec):
    children = [
        request
        for row in load_request_index().values()
        if row["id"] in MARKET_PARENTS[spec.expand]
        and row["site"] == SITE_NAME[spec.site]
        and row["kind"] == "response"
        and row.get("status") == 200
        for request in EXPANSIONS[spec.expand](
            Body(raw=Path(row["path"]).read_bytes()), retained_context(row, spec)
        )
    ]
    # A zero here is a wrong hub or reader, unless the row is a named gap.
    assert bool(children) == (spec.id not in MARKET_GAPS)
    assert all("{" not in r.url and "//" not in urlsplit(r.url).path for r in children)


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


@pytest.mark.pg
@pytest.mark.retained
def test_announcements_continue_through_the_show_more_timestamp(market_rig):
    from urllib.parse import urljoin

    opener, pool, run = market_rig
    row = next(r for r in opener.rows.values() if r["id"] == "announcements-feed")
    spec = next(s for s in MARKET_SPECS if s.id == row["id"])
    request = Request(spec=spec, url=row["url"], ids=None, due_since=None)
    raw = Path(row["path"]).read_bytes()
    onclick = Body(raw=raw).tree().xpath('//div[starts-with(@id,"show-more-")]/button/@onclick')
    next_url = urljoin(row["url"], onclick[0].split("'")[1])
    opener.overrides[next_url] = raw.replace(b"Utils.ajaxLoad", b"Utils.disabled"), 200
    report = run((), requests=(request,))
    # Page 1 is not the whole feed: the source continues by timestamp and same-second offset.
    assert opener.calls == [row["url"], next_url] and report.completed == 2
    assert not report.incomplete
    assert market.traversal_key(request.model_copy(update={"url": next_url})) == (
        market.traversal_key(request)
    )
    assert market.progress(pool, market.traversal_key(request)).resume_page is None


def test_hub_requests_include_optional_bases_and_named_companions():
    found = {
        (r.spec.id, urlsplit(r.url).path, urlsplit(r.url).query)
        for r in market.market_requests(MARKET_SPECS, None, ())
    }
    # `[x]` is optional in the catalog: the bare page is a real, distinct listing.
    assert {
        ("ipo", "/ipo/", ""),
        ("ipo", "/ipo/recent/", ""),
        ("announcements-feed", "/announcements/", ""),
        ("filter", "/filter/", ""),
        ("filter", "/filter/", "qt=basic"),
        ("faq", "/in/faq/", ""),
        ("faq", "/faq/data/", ""),
    } <= found


def test_unusable_market_surfaces_are_not_requested_and_feeds_send_accepted_queries():
    """Live 2026-10-30/31 404, 500, 400 and 302 responses for these requests (eqos-aa6.22)."""
    # A blank search term 404s; every widget field 500s as an index metric; every popular
    # query 500s. None has advertised parameters that work, so none is requested.
    assert not {s.id for s in MARKET_SPECS} & {
        "index-search-api",
        "index-metric-data-api",
        "filter-popular-query-results-api",
    }
    fixed = {
        "concalls-feed",
        "results-latest",
        "upcoming-results",
        "sectors-filter-api",
        "quarterly-results-api",
        "upcoming-events-api",
    }
    found = {
        (r.spec.id, urlsplit(r.url).path, urlsplit(r.url).query)
        for r in market.market_requests(MARKET_SPECS, None, (129, 7))
        if r.spec.id in fixed
    }
    # Screener 302s blank date filters (and /concalls/upcoming/) to the bare listing; Tijori
    # 400s a blank page ("Invalid page number"); only goto_sublist works without a screen id.
    assert found == {
        ("concalls-feed", "/concalls/", ""),
        ("results-latest", "/results/latest/", ""),
        ("upcoming-results", "/upcoming-results/", ""),
        ("sectors-filter-api", "/api/get/sectors/", "url_name=goto_sublist"),
        (
            "quarterly-results-api",
            "/results/quarterly-results/api/",
            "page=1&sort_by=latest&mcap=&timeline_type=all&sectors=&company_ids=129,7",
        ),
        (
            "upcoming-events-api",
            "/results/upcoming-events/api/",
            "page=1&mcap=&timeline_type=all&sectors=&company_ids=129,7&type=results",
        ),
    }


def test_tijori_market_listings_fetch_only_covered_companies():
    """Owner (eqos-aa6.26): fetch only what the covered universe needs, not market-wide pages."""
    feeds = {"quarterly-results-api", "upcoming-events-api"}
    # The result feeds name the covered companies, so no page carries an uncovered company.
    assert not {r.spec.id for r in market.market_requests(MARKET_SPECS, None, ())} & feeds
    # Idea themes are not tied to a covered company, so none is requested.
    assert not {s.id for s in MARKET_SPECS} & {"idea-page", "idea-card-body"}
    # Landing pages and the changelog keep their first page; later pages are market-wide.
    more = Body(raw=b'<html><body><button class="show_more">More</button></body></html>')
    for spec in (
        s for s in MARKET_SPECS if s.id in {"quarterly-results", "upcoming-events", "whats-new"}
    ):
        request = Request(spec=spec, url=f"https://x{spec.path}", ids=None, due_since=None)
        assert market.continuation(request, more, 1) is None


@pytest.mark.pg
@pytest.mark.retained
def test_feed_page_without_unique_identities_is_reported(market_rig):
    opener, pool, run = market_rig
    row = next(r for r in opener.rows.values() if r["id"] == "trades-feed")
    spec = next(s for s in MARKET_SPECS if s.id == row["id"])
    report = run((), requests=(Request(spec=spec, url=row["url"], ids=None, due_since=None),))
    assert "screener:trades-feed: rows without a unique identity" in report.incomplete


@pytest.mark.pg
@pytest.mark.retained
def test_market_children_expand_at_the_parent_retrieval_time(market_rig, tmp_path, monkeypatch):
    from equity_os.sourcing.surfaces.vendor_surface_fetch import request_key

    opener, pool, run = market_rig
    row = next(r for r in opener.rows.values() if r["id"] == "macro")
    hub = next(s for s in MARKET_SPECS if s.id == row["id"])
    seen = []
    monkeypatch.setitem(EXPANSIONS, "tijori_macro", lambda body, ctx: seen.append(ctx) or ())
    run(MARKET_SPECS, requests=(Request(spec=hub, url=row["url"], ids=None, due_since=None),))
    record = SnapshotStore(tmp_path / "captures").get_capture(
        Site.TIJORI.value, "vs." + hub.id, request_key(row["url"]), seen[0].capture_id
    )
    # Expansion time is evidence time: the parent's retrieval, never the expansion's clock.
    assert seen[0].retrieved_at == record.retrieved_at


@pytest.mark.pg
@pytest.mark.retained
def test_market_report_names_requests_without_vendor_addresses(market_rig):
    import re

    opener, pool, run = market_rig
    row = next(r for r in opener.rows.values() if r["id"] == "explore")
    hub = next(s for s in MARKET_SPECS if s.id == row["id"])
    report = run(
        MARKET_SPECS, requests=(Request(spec=hub, url=row["url"], ids=None, due_since=None),)
    )
    # Unadvertised children stay gaps; the cron line logs only site, surface and key.
    assert report.incomplete
    assert all(
        re.fullmatch(r"(screener|tijori):[a-z0-9-]+(:[0-9a-f]{64})?(: [a-z -]+)?", entry)
        for entry in (*report.incomplete, *report.refused)
    )


@pytest.mark.pg
def test_ambiguous_feed_identity_never_sets_or_reaches_a_boundary(market_rig):
    opener, pool, run = market_rig
    spec = next(s for s in MARKET_SPECS if s.id == "announcements-feed")
    first, second = (f"https://www.screener.in/announcements/all/?p={n}" for n in (1, 2))
    request = Request(spec=spec, url=first, ids=None, due_since=None)

    def page(*events, more=False):
        items = "".join(
            '<div class="announcement-item"><a href="/company/FIXTURE/">Fixture</a>'
            f'<a href="/event/{e}">Event</a><time datetime="2026-10-28">Date</time></div>'
            for e in events
        )
        return f"<main>{items}{'<a href="?p=2">Next</a>' if more else ''}</main>".encode(), 200

    opener.overrides[first] = page("B")
    run((), requests=(request,))
    # Establish a completed boundary before encountering an ambiguous page.
    assert market.progress(pool, market.traversal_key(request)).boundary.row_id == "/event/B"
    opener.overrides |= {first: page("new", "A", "A", more=True), second: page("B")}
    opener.calls.clear()
    run((), requests=(request,))
    assert opener.calls == [first]  # An ambiguous page stays unfinished and is retried.
    state = market.progress(pool, market.traversal_key(request))
    assert state.boundary.row_id == "/event/B" and state.resume_page == 1


@pytest.mark.pg
def test_ambiguous_terminal_page_persists_incomplete_and_prior_boundary(market_rig, tmp_path):
    from equity_os.sourcing.surfaces import vendor_surface_due as due

    opener, pool, run = market_rig
    spec = next(s for s in MARKET_SPECS if s.id == "announcements-feed").model_copy(
        update={"path": "/announcements/all/?p=1"}
    )
    url = "https://www.screener.in/announcements/all/?p=1"
    request = Request(spec=spec, url=url, ids=None, due_since=None)
    item = (
        b'<div class="announcement-item"><a href="/company/FIXTURE/">Fixture</a>'
        b'<a href="/event/old">Event</a><time datetime="2026-10-28">Date</time></div>'
    )
    opener.overrides[url] = b"<main>" + item + b"</main>", 200
    assert not run((), requests=(request,)).incomplete
    key = market.traversal_key(request)
    boundary = market.progress(pool, key).boundary
    duplicate = item.replace(b"/event/old", b"/event/new")
    opener.overrides[url] = b"<main>" + duplicate * 2 + b"</main>", 200
    for _ in range(2):
        assert run((), requests=(request,)).incomplete
        state = market.progress(pool, key)
        assert state.boundary == boundary and state.resume_page == 1
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT status,traversal_done FROM eqos.vendor_outcomes "
                "WHERE traversal_key=%s ORDER BY id DESC LIMIT 1",
                (key,),
            ).fetchone() == ("UNUSABLE", False)
    queued, notes = due.due_requests(
        pool, SnapshotStore(tmp_path / "captures"), (spec,), datetime.now(UTC)
    )
    assert not queued
    assert "screener:announcements-feed: INCOMPLETE" in notes


def test_traversal_checkpoint_hides_yield_drop(market_rig):
    from equity_os.sourcing.surfaces.vendor_surface_canary import ROW_COUNT_DROP, yield_drift

    def announcement_page(count):
        return (
            "<main>"
            + "".join(
                '<div class="announcement-item"><a href="/company/FIXTURE/">Company</a>'
                f'<a href="/event/{i}">Event</a><time datetime="2026-10-28">Date</time></div>'
                for i in range(count)
            )
            + "</main>"
        ).encode()

    opener, pool, run = market_rig
    spec = next(s for s in MARKET_SPECS if s.id == "announcements-feed")
    url = "https://www.screener.in/announcements/all/"
    request = Request(spec=spec, url=url, ids=None, due_since=None)
    for count in (10, 1):
        opener.overrides[url] = announcement_page(count), 200
        run((), requests=(request,))
    checks = yield_drift(pool, datetime.min.replace(tzinfo=UTC))
    assert any(c.check == ROW_COUNT_DROP for c in checks), "10-to-1 feed shrink not detected"


def test_nonfeed_market_table_refreshes_all_pages(market_rig):
    opener, pool, run = market_rig
    spec = next(s for s in MARKET_SPECS if s.id == "market-level")
    url = "https://www.screener.in/market/IN10/"
    request = Request(spec=spec, url=url, ids=None, due_since=None)
    for number in (1, 2):
        raw = (
            '<table class="data-table"><thead><tr><th>Company</th><th>Revenue</th></tr>'
            f'</thead><tbody><tr><td><a href="/company/C{number}/">Company</a></td>'
            "<td>1</td></tr></tbody></table>" + ('<a href="?p=2">Next</a>' if number == 1 else "")
        ).encode()
        opener.overrides[url if number == 1 else url + "?p=2"] = raw, 200
    run((), requests=(request,))
    assert len(opener.calls) == 2
    opener.calls.clear()
    run((), requests=(request,))
    assert len(opener.calls) == 2, "weekly non-feed snapshot stops after old company link on page 1"


def test_selected_market_surface_includes_its_hub(pg_db, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("equity_os.sourcing.transport.http_session.time.sleep", lambda _: None)
    import argparse

    from equity_os.interface.commands.sourcing.vendor_surface_cli import dispatch_vendor_command

    opener = MarketOpener()
    args = argparse.Namespace(
        command="vendor",
        vendor_command="capture",
        market=True,
        symbol=None,
        surface=["tijori:index-data-api"],
        snapshot_root=tmp_path / "captures",
        tijori_slug=None,
    )
    dispatch_vendor_command(
        args,
        opener_factory=lambda: opener,
        pool_factory=pg_db.runtime_pool,
        sessions_factory=lambda sites: {
            s: SiteSession(site=s, session_cookie=SecretStr("synthetic"), cookie_name="sid")
            for s in sites
        },
    )
    capsys.readouterr()
    count = len(opener.calls)
    assert count > 0, f"{count} requests for selected market surface; its hub was omitted"


def test_sitemap_with_xml_declaration_has_no_continuation():
    """Live capture-due died on sitemap.xml: lxml rejects a str with an encoding declaration."""
    spec = next(s for s in MARKET_SPECS if s.site is Site.SCREENER and s.id == "sitemap")
    request = Request(
        spec=spec, url="https://www.screener.in/sitemap.xml", ids=None, due_since=None
    )
    raw = b'<?xml version="1.0" encoding="UTF-8"?><sitemapindex><sitemap/></sitemapindex>'
    assert market.continuation(request, Body(raw=raw), 1) is None


@pytest.mark.parametrize("surface", ["macro-chart-api", "markets-indices-widget-api"])
@pytest.mark.parametrize("age,pending", [(None, False), (timedelta(days=30), True)])
def test_owner_disabled_surface_is_never_due_but_can_be_reenabled(surface, age, pending):
    """The owner stopped these fetches pending a later decision; the flag alone restores them."""
    now = datetime(2026, 11, 3, tzinfo=UTC)
    last = now - age if age else None
    spec = next(s for s in MARKET_SPECS if s.id == surface)
    assert is_due(spec, last, now, pending) is False
    assert is_due(spec.model_copy(update={"enabled": True}), last, now, pending) is True
