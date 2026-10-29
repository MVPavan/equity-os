"""Cadence over the covered universe: only stored outcomes decide what is due."""

import argparse
import hashlib
import io
import re
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest
from coverage_support import SEED_RULING, watchlist
from onboarding_support import seed
from pydantic import SecretStr
from vendor_surface_support import load_request_index

from fundamentals.contracts.ledger import DecisionKind, SubjectKind
from fundamentals.ingest import vendor_surface_due as due
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_market import capture_market, market_requests
from fundamentals.ingest.vendor_surface_parse import (
    PARSERS,
    Body,
    ParseContext,
    ParserEntry,
    kept_section,
    register_tables,
)
from fundamentals.ingest.vendor_surface_specs import Cadence, load_specs
from fundamentals.ingest.vendor_surface_tables import feed_rows
from fundamentals.ledger.lifecycle import decide
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

SPECS = load_specs(
    Path("config/vendor_surface/surfaces.yaml"), Path("docs/research/vendor-surface/catalog.yaml")
)
register_tables(SPECS)  # The CLI root binds table parsers; this suite calls capture_due directly.
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
DAY = timedelta(days=1)
FEED = "/results/latest/"
PAGES = {
    Basis.CONSOLIDATED: "https://www.screener.in/company/APARINDS/consolidated/",
    Basis.STANDALONE: "https://www.screener.in/company/APARINDS/",
}
FINANCIALS = "https://www.tijorifinance.com/company/apar-industries-limited/financials/"
PERIOD = re.compile(rb"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (20\d\d)\b")


def pick(*ids, site=None):
    return tuple(s for s in SPECS if s.id in ids and site in (None, s.site))


@pytest.mark.parametrize(
    "cadence,last,pending,expected",
    [
        (Cadence.DAILY, None, False, True),
        (Cadence.DAILY, NOW - timedelta(hours=11), False, False),
        (Cadence.DAILY, NOW - timedelta(hours=13), False, True),
        (Cadence.WEEKLY, None, False, True),
        (Cadence.WEEKLY, NOW - 6 * DAY, False, False),
        (Cadence.WEEKLY, NOW - 7 * DAY, False, True),
        (Cadence.AFTER_RESULTS, None, False, True),
        (Cadence.AFTER_RESULTS, NOW - 300 * DAY, False, False),
        (Cadence.AFTER_RESULTS, NOW - timedelta(hours=1), True, True),
    ],
)
def test_is_due(cadence, last, pending, expected):
    spec = next(s for s in SPECS if s.cadence is cadence)
    assert due.is_due(spec, last, NOW, pending) is expected


class DueOpener(OpenerDirector):
    """Exact retained addresses, the results feed by path, otherwise 404."""

    def __init__(self):
        super().__init__()
        self.rows, self.calls, self.overrides = load_request_index(), [], {}
        row = next(r for r in self.rows.values() if r["id"] == "results-latest")
        self.feed = Path(row["path"]).read_bytes()
        self.overrides[FEED] = self.feed, 200

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        row = self.rows.get(request.full_url)
        raw, status = b"unretained", 404
        if row and row.get("path"):
            raw, status = Path(row["path"]).read_bytes(), row.get("status", 200)
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        key = urlsplit(request.full_url).path if FEED in request.full_url else request.full_url
        raw, status = self.overrides.get(key, (raw, status))
        return HTTPError(request.full_url, status, "fixture", {}, io.BytesIO(raw))

    def new_results_row(self):
        """Give a non-boundary feed row to APARINDS under a new row identity."""
        spec = pick("results-latest")[0]
        context = ParseContext(
            ids=None, basis=None, url="", retrieved_at=NOW, body_sha256="", capture_id=""
        )
        row = feed_rows(spec, PARSERS[spec.site, spec.id].parse(Body(raw=self.feed), context))[1]
        raw = self.feed.replace(row.company.encode(), b"/company/APARINDS/consolidated/#quarters")
        self.overrides[FEED] = (
            raw.replace(row.row_id.encode(), b"/company/source/quarter/211/12/2030/"),
            200,
        )

    def newer_period(self, url):
        """Serve the retained body with its latest period label moved five years on."""
        raw = Path(self.rows[url]["path"]).read_bytes()
        month, year = max(
            PERIOD.findall(raw), key=lambda m: (m[1], datetime.strptime(m[0].decode(), "%b").month)
        )
        self.overrides[url] = (
            raw.replace(month + b" " + year, month + b" " + str(int(year) + 5).encode()),
            200,
        )


@pytest.fixture
def due_rig(pg_db, tmp_path):
    entity = seed(pg_db, "APARINDS", "INE372A01015", "APARINDS", "532259")
    with ExitStack() as stack:
        pools = {r: stack.enter_context(pg_db.role_pool(r)) for r in (PgRole.RUNTIME, PgRole.OWNER)}
        watchlist(pools, entity, SnapshotStore(tmp_path / "seed"))
        with pools[PgRole.OWNER].connection() as conn:
            load = conn.execute(
                "INSERT INTO eqos.registry_loads (capture_ref_id,content_sha256) "
                "SELECT min(id),'seed' FROM eqos.capture_refs RETURNING id"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO eqos.registry_sightings "
                "(listing_id,load_id,trading_symbol,exchange_token,name) "
                "SELECT id,%s,'APARINDS','1','seed' FROM eqos.registry_listings "
                "WHERE segment='NSE_EQ'",
                (load,),
            )
        pool, store, opener = pools[PgRole.RUNTIME], SnapshotStore(tmp_path / "raw"), DueOpener()
        locks = PgSiteLock(pool)
        stack.callback(locks.close)
        sessions = {
            s: SiteSession(site=s, session_cookie=SecretStr("fake"), cookie_name="sessionid")
            for s in Site
        }

        def fetcher(budget=350):
            return VendorFetcher(
                store,
                sessions,
                opener,
                tmp_path / "stops",
                locks,
                spacing_seconds=0,
                site_budget=budget,
            )

        def run(specs, now, budget=350):
            opener.calls.clear()
            return due.capture_due(
                fetcher(budget), store, pool, VendorValuesStore(pool), specs, now
            )

        yield SimpleNamespace(**locals())  # The rig's handles, by name.


def states(rig, specs):
    (ids,) = due.covered_universe(rig.pool, rig.store)
    triggers = due.pending_triggers(rig.pool, rig.store, ids, specs)
    return {(o.surface, o.basis): o.state for t in triggers for o in t.obligations}


@pytest.mark.pg
def test_covered_universe_follows_latest_watchlist_decision(due_rig):
    def covered():
        return [ids.nse_symbol for ids in due.covered_universe(due_rig.pool, due_rig.store)]

    assert covered() == ["APARINDS"]
    for kind, expected in ((DecisionKind.REMOVE, []), (DecisionKind.ADD, ["APARINDS"])):
        decide(
            due_rig.pools[PgRole.OWNER],
            subject_kind=SubjectKind.WATCHLIST,
            subject_id=due_rig.entity,
            kind=kind,
            ruling=SEED_RULING,
        )
        assert covered() == expected
    assert due.covered_universe(due_rig.pool, due_rig.store)[0].topology is not None


@pytest.mark.pg
@pytest.mark.retained
def test_idle_second_run_and_results_obligations(due_rig, monkeypatch):
    monkeypatch.setattr(due, "MAX_ATTEMPTS", 3)
    rig, specs = due_rig, pick("results-latest", "company-page", "company-financials")
    day = datetime.now(UTC)

    def statements(report):
        assert not report.refused and not report.stopped_sites
        return {url for url in rig.opener.calls if FEED not in url}

    assert statements(rig.run(specs, day)) == {*PAGES.values(), FINANCIALS}
    assert any(FEED in url for url in rig.opener.calls)
    rig.run(specs, day)
    assert rig.opener.calls == []
    assert statements(rig.run(specs, day + DAY)) == set()
    assert rig.opener.calls  # The daily feed alone.

    rig.opener.new_results_row()
    rig.opener.newer_period(PAGES[Basis.CONSOLIDATED])
    assert statements(rig.run(specs, day + 2 * DAY)) == {*PAGES.values(), FINANCIALS}
    pending, done = due.ObligationState.PENDING, due.ObligationState.SATISFIED
    assert states(rig, specs) == {
        ("company-page", Basis.CONSOLIDATED): done,
        ("company-page", Basis.STANDALONE): pending,
        ("company-financials", None): pending,
    }
    rig.opener.newer_period(PAGES[Basis.STANDALONE])
    assert statements(rig.run(specs, day + 3 * DAY)) == {PAGES[Basis.STANDALONE], FINANCIALS}
    assert states(rig, specs)[("company-page", Basis.STANDALONE)] is done
    report = rig.run(specs, day + 4 * DAY)
    assert statements(report) == {FINANCIALS}
    assert states(rig, specs)[("company-financials", None)] is due.ObligationState.EXHAUSTED
    report = rig.run(specs, day + 5 * DAY)
    assert statements(report) == set()
    assert "APARINDS:tijori:company-financials:-: INCOMPLETE" in report.incomplete


@pytest.mark.pg
@pytest.mark.retained
def test_failed_expanded_schedule_alone_keeps_obligation_pending(due_rig, monkeypatch):
    # Cadence, not reading: any retained schedule body is a usable instance, a 404 a failed one.
    monkeypatch.setitem(
        PARSERS,
        (Site.SCREENER, "schedules-api"),
        ParserEntry(version="screener:schedules-api.fixture.v1", parse=kept_section),
    )
    rig, specs = due_rig, pick("results-latest", "company-page", "schedules-api")
    day = datetime.now(UTC)
    rig.run(specs, day)
    schedules = {url for url in rig.opener.calls if "/schedules/" in url}
    retained = {url for url in schedules if url in rig.opener.rows}
    assert retained and schedules - retained
    rig.opener.new_results_row()
    for url in PAGES.values():
        rig.opener.newer_period(url)
    rig.run(specs, day + DAY)
    assert schedules <= set(rig.opener.calls)  # A new parent capture refreshes every child.
    found = states(rig, specs)
    assert found[("company-page", Basis.STANDALONE)] is due.ObligationState.SATISFIED
    assert found[("schedules-api", Basis.STANDALONE)] is due.ObligationState.PENDING
    rig.run(specs, day + 2 * DAY)
    assert {url for url in rig.opener.calls if FEED not in url} == schedules - retained


@pytest.mark.pg
@pytest.mark.retained
def test_budget_captures_each_due_request_once_oldest_first(due_rig):
    rig = due_rig
    specs = pick(
        "robots",
        "changelog",
        "features",
        "support",
        "ratio-gallery",
        "fii-page",
        "fii-api",
        site=Site.SCREENER,
    )
    oldest_first = tuple(reversed(market_requests(specs, rig.pool)))
    assert len(oldest_first) == 7
    capture_market(
        rig.fetcher(), rig.store, rig.pool, VendorValuesStore(rig.pool), (), requests=oldest_first
    )
    week_later = datetime.now(UTC) + 7 * DAY
    calls = []
    for held in (4, 1, 0):
        report = rig.run(specs, week_later, budget=3)
        calls.extend(rig.opener.calls)
        assert len(report.incomplete) == held
    assert calls == [request.url for request in oldest_first]


@pytest.mark.pg
@pytest.mark.retained
def test_capture_due_exit_code(due_rig, monkeypatch):
    from fundamentals.api import vendor_surface_cli as cli

    stops = due_rig.tmp_path / "cli-stops"
    monkeypatch.setattr(cli, "load_specs", lambda *_: pick("robots", site=Site.SCREENER))
    monkeypatch.setattr(cli, "STOP_DIR", stops)
    args = argparse.Namespace(command="vendor", vendor_command="capture-due", snapshot_root=stops)

    def dispatch():
        return cli.dispatch_vendor_command(
            args,
            opener_factory=lambda: due_rig.opener,
            pool_factory=due_rig.pg_db.runtime_pool,
            sessions_factory=lambda sites: {
                s: SiteSession(site=s, session_cookie=SecretStr("x"), cookie_name="sessionid")
                for s in sites
            },
        )

    stops.mkdir()
    (stops / f"STOP-{Site.SCREENER}").write_text("diagnosis pending\n")
    assert dispatch() == 1 and due_rig.opener.calls == []
    (stops / f"STOP-{Site.SCREENER}").unlink()
    assert dispatch() == 0 and due_rig.opener.calls == ["https://www.screener.in/robots.txt"]
