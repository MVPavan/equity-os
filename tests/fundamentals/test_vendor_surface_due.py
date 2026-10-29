"""Cadence over the covered universe: only stored outcomes decide what is due."""

import argparse
import hashlib
import io
import re
from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest
from coverage_support import SEED_RULING, watchlist
from onboarding_support import seed
from psycopg.rows import dict_row
from pydantic import SecretStr
from vendor_surface_support import load_request_index

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.ledger import DecisionKind, SubjectKind
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest import vendor_surface_capture as capture
from fundamentals.ingest import vendor_surface_due as due
from fundamentals.ingest import vendor_surface_expand as expand
from fundamentals.ingest.screener_session_models import Basis, BasisTopology
from fundamentals.ingest.vendor_surface_canary import COMPANY_OVERDUE, overdue
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
from fundamentals.store.vendor_values_store import Outcome, OutcomeStatus, VendorValuesStore

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
def due_rig(pg_db, tmp_path, monkeypatch):
    # APARINDS's retained financials fail these three section readers, which leaves the capture
    # unusable and due every run; cadence tests need one usable capture.
    for section in ("balance-sheet-snapshot", "fundflow-analysis", "cash-flow-analysis"):
        entry = ParserEntry(version=f"tijori:{section}.fixture.v1", parse=kept_section)
        monkeypatch.setitem(PARSERS, (Site.TIJORI, "financials-" + section), entry)
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
    seen = due.history(rig.pool, specs)
    nodes = due.tree(capture.company_requests(specs, ids), seen, rig.store, specs, ())
    triggers = due.pending_triggers(ids, specs, nodes, seen, due.results_rows(rig.pool, specs))
    return {(o.surface, o.basis): o.state for t in triggers for o in t.obligations}


def at(day, *, usable=True, period=None):
    """One classified capture of an instance, `day` days after the trigger."""
    return day, usable, period


def seen_of(day, usable, period):
    """Build the classified capture `at` describes."""
    when = NOW + day * DAY
    ref = CaptureReference(
        capture_ref_id=1,
        source_id="s",
        surface="vs.s",
        request_key="k",
        capture_id="c",
        blob_sha256="0" * 64,
        record_sha256="0" * 64,
        registered_at=when,
        first_seen_at=when,
    )
    return due.Seen(ref=ref, retrieved_at=when, usable=usable, gated=False, period=period)


OLD, NEW = date(2026, 6, 1), date(2026, 9, 1)
PAGE = {"page": [at(-5, period=OLD), at(1, period=NEW)]}  # Shows the new period on day 1.


@pytest.mark.parametrize(
    "parents,seen,state,retry",
    [
        # A child with a period header must show a period newer than its own baseline.
        ({"s1": "page"}, PAGE | {"s1": [at(-5, period=OLD), at(2, period=OLD)]}, "PENDING", ["s1"]),
        ({"s1": "page"}, PAGE | {"s1": [at(-5, period=OLD), at(2, period=NEW)]}, "SATISFIED", []),
        # A headerless child needs a usable capture after its parent's refresh.
        ({"s1": "page"}, PAGE | {"s1": [at(-5), at(2)]}, "SATISFIED", []),
        ({"s1": "page"}, {"page": PAGE["page"][:1], "s1": [at(2)]}, "PENDING", ["page"]),
        # Nested instances are required, each against its own parent.
        ({"s1": "page", "s2": "s1"}, PAGE | {"s1": [at(2)], "s2": [at(-5)]}, "PENDING", ["s2"]),
        # A successful empty expansion satisfies; a failed one keeps the obligation pending.
        ({}, PAGE, "SATISFIED", []),
        ({"gap": None}, PAGE, "PENDING", []),
        # Attempts and exhaustion are per instance.
        (
            {"s1": "page", "s2": "page"},
            PAGE | {"s1": [at(2, usable=False)] * 10, "s2": [at(2, usable=False)] * 3},
            "PENDING",
            ["s2"],
        ),
        (
            {"s1": "page", "s2": "page"},
            PAGE | {"s1": [at(2, usable=False)] * 10, "s2": [at(2, usable=False)] * 10},
            "EXHAUSTED",
            [],
        ),
    ],
)
def test_obligation_requires_every_instance_of_the_retained_tree(parents, seen, state, retry):
    page, schedules = pick("company-page", "schedules-api")

    def node(spec, parent=None, gaps=()):
        request = due.Request(
            spec=spec, url="https://x/", ids=None, basis=Basis.STANDALONE, due_since=None
        )
        return due.Node(request=request, parent=parent, gaps=gaps)

    gaps = ("screener:schedules-api: expansion failed: KeyError",) if "gap" in parents else ()
    nodes = {"page": node(page, gaps=gaps)}
    nodes |= {key: node(schedules, parent) for key, parent in parents.items() if key != "gap"}
    seen = {key: [seen_of(*item) for item in items] for key, items in seen.items()}
    found = due.obligation(schedules, Basis.STANDALONE, NOW, nodes, seen)
    assert (found.state, list(found.retry)) == (state, retry)


def test_obligations_follow_published_bases_only():
    ids = due.CompanyIds(
        nse_symbol="APARINDS",
        isin="INE372A01015",
        tijori_slug=None,
        tijori_company_id=None,
        screener_company_id=211,
        topology=BasisTopology(consolidated_warehouse_id=None, standalone_warehouse_id=5),
    )
    specs = pick("company-page")
    roots = capture.company_requests(specs, ids)
    nodes = {r.url: due.Node(request=r, parent=None, gaps=()) for r in roots}
    (trigger,) = due.pending_triggers(ids, specs, nodes, {}, {("APARINDS", "row"): NOW})
    assert [(o.surface, o.basis) for o in trigger.obligations] == [
        ("company-page", Basis.STANDALONE)
    ]


@pytest.mark.pg
def test_covered_universe_follows_latest_watchlist_decision(due_rig, monkeypatch):
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
    # An entity covered by the ledger stays covered without a watchlist.yaml entry.
    monkeypatch.setattr(due, "load_watchlist_config", lambda _: SimpleNamespace(stocks=()))
    assert covered() == ["APARINDS"]
    _, notes = due.due_requests(due_rig.pool, due_rig.store, pick("company-page"), NOW)
    assert {"APARINDS: screener:missing company id", "APARINDS: topology unknown"} <= set(notes)


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


@pytest.mark.pg
@pytest.mark.retained
def test_scheduled_company_capture_passes_the_company_gates(due_rig, monkeypatch):
    rig, specs = due_rig, pick("results-latest", "company-page", "company-financials")
    unbound = {"topology": None, "tijori_slug": None, "tijori_company_id": None}
    monkeypatch.setattr(
        due, "company_ids", lambda s: capture.company_ids(s).model_copy(update=unbound)
    )
    search = "https://www.tijorifinance.com/api/v1/ind/company_search/?q=INE372A01015"
    day = datetime.now(UTC)
    report = rig.run(specs, day)
    assert set(PAGES.values()) <= set(rig.opener.calls) and search in rig.opener.calls
    assert "APARINDS: tijori:missing slug" in report.incomplete
    with rig.pool.connection() as conn:
        bound = conn.execute("SELECT evidence FROM eqos.vendor_basis_bindings").fetchall()
        gated = conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE detail = %s", (due.TOPOLOGY_UNKNOWN,)
        ).fetchone()
    # Both first-captured pages bind the topology before either is parsed.
    assert bound == [("FIRST_CAPTURE",)] * 2 and gated == (0,)
    rig.run(specs, day + DAY)
    assert search in rig.opener.calls and not set(PAGES.values()) & set(rig.opener.calls)


@pytest.mark.pg
@pytest.mark.retained
def test_usability_needs_every_logical_outcome_and_expansion(due_rig, monkeypatch):
    def broken(body, context):
        raise KeyError("fixture")

    monkeypatch.setitem(expand.EXPANSIONS, "screener_schedules", broken)
    rig, specs = due_rig, pick("company-page", "schedules-api")
    report = rig.run(specs, NOW)
    assert "APARINDS: screener:schedules-api: expansion failed: KeyError" in report.incomplete

    def due_urls():
        return {r.url for r in due.due_requests(rig.pool, rig.store, specs, NOW)[0]}

    assert due_urls() == set()
    with rig.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            "SELECT c.* FROM eqos.capture_refs c JOIN eqos.capture_addresses a "
            "ON a.capture_ref_id = c.id WHERE a.url = %s",
            (PAGES[Basis.CONSOLIDATED],),
        ).fetchone()
    values = VendorValuesStore(rig.pool)
    for version, status in ((2, OutcomeStatus.FAILED), (3, OutcomeStatus.OK)):
        outcome = Outcome(
            surface="section-quarters",
            parser_version=f"screener:section-quarters.fixture.v{version}",
            parser_sha256="a" * 64,
            status=status,
            symbol="APARINDS",
            detail=None,
        )
        values.record(capture_of(row), outcome, row_count=0)
        # A failed statement section makes the page unusable until a later parse supersedes it.
        assert due_urls() == ({PAGES[Basis.CONSOLIDATED]} if version == 2 else set())


@pytest.mark.pg
@pytest.mark.retained
def test_children_keep_their_own_cadence_under_a_budget(due_rig, monkeypatch):
    # Cadence, not reading: every investors response is a usable instance.
    entry = ParserEntry(version="screener:investors-api.fixture.v1", parse=kept_section)
    monkeypatch.setitem(PARSERS, (Site.SCREENER, "investors-api"), entry)
    rig, opener = due_rig, due_rig.opener
    serve = opener.open

    def open(request, timeout):
        if "/investors/" in request.full_url and request.full_url not in opener.rows:
            opener.overrides.setdefault(request.full_url, (b"{}", 200))
        return serve(request, timeout)

    monkeypatch.setattr(opener, "open", open)
    day, calls = datetime.now(UTC), []
    for _ in range(5):
        rig.run(pick("company-page", "investors-api"), day, budget=3)
        calls.extend(opener.calls)
    # Never-captured parents first, then each advertised child exactly once across runs.
    assert set(calls[:2]) == set(PAGES.values()) and len(calls) == len(set(calls)) > 3
    opener.new_results_row()
    opener.newer_period(PAGES[Basis.CONSOLIDATED])
    rig.run(pick("results-latest", "company-page", "investors-api"), day + DAY)
    # A newer parent capture alone does not make its weekly children due again.
    assert PAGES[Basis.CONSOLIDATED] in opener.calls
    assert not any("/investors/" in url for url in opener.calls)


@pytest.mark.pg
@pytest.mark.retained
def test_canary_names_an_overdue_covered_request(due_rig):
    rig, specs = due_rig, pick("company-financials")
    assert [d.check for d in overdue(rig.pool, rig.store, specs, NOW)] == [COMPANY_OVERDUE]
    day = datetime.now(UTC)
    rig.run(specs, day)
    assert overdue(rig.pool, rig.store, specs, day + DAY) == ()
    (late,) = overdue(rig.pool, rig.store, specs, day + 185 * DAY)
    assert (late.surface, late.check) == ("company-financials", COMPANY_OVERDUE)
