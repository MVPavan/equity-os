"""Yield drift compares only like versions and reports every orphaned capture."""

import copy
import hashlib
import inspect
import json
import re
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest
from lxml import html
from retention_support import record_of
from vendor_surface_support import rig

__all__ = ["rig"]

from fundamentals.ingest.vendor_surface_fetch import Fetched
from fundamentals.store.vendor_values_store import (
    Outcome,
    OutcomeStatus,
    VendorValuesStore,
    register,
)

pytestmark = pytest.mark.pg


@pytest.mark.parametrize(
    ("first", "second", "version", "check"),
    [
        (10, 4, 1, "ROW_COUNT_DROP"),
        (10, 0, 1, "ROW_COUNT_DROP"),
        (0, 0, 1, None),
        (10, 1, 2, "NO_BASELINE"),
        (10, None, 1, "MISSING_OUTCOME"),
    ],
)
@pytest.mark.parametrize("recovered_out_of_order", [False, True])
def test_yield_checks_and_cli(
    pg_db, first, second, version, check, monkeypatch, capsys, recovered_out_of_order
):
    from fundamentals.api import cli
    from fundamentals.api.vendor_surface_cli import dispatch_vendor_command
    from fundamentals.contracts.snapshot import CaptureRecord
    from fundamentals.ingest.vendor_surface_canary import yield_drift

    base = record_of(b"fixture", "tijori", "vs.chart-api")
    with pg_db.runtime_pool() as pool:
        values = VendorValuesStore(pool)
        captures = []
        for index, count in enumerate((first, second)):
            record = CaptureRecord.make(
                base.request,
                base.retrieved_at + timedelta(seconds=index),
                200,
                "text/plain",
                None,
                base.body,
                base.outcome,
                base.rights,
            )
            ref = register(
                pool,
                Fetched(record=record, url="https://www.tijorifinance.com/chart/", location=None),
            )
            captures.append((ref, count, index))
        for ref, count, index in reversed(captures) if recovered_out_of_order else captures:
            if count is not None:
                values.record(
                    ref,
                    Outcome(
                        surface="chart-api",
                        parser_version=f"tijori:chart-api.v{version if index else 1}",
                        parser_sha256="a" * 64,
                        status=OutcomeStatus.OK if count else OutcomeStatus.EMPTY,
                        symbol="APARINDS",
                        detail=None,
                    ),
                    row_count=count,
                )
        drift = yield_drift(pool, datetime(2000, 1, 1, tzinfo=UTC))
    assert [item.check for item in drift] == ([check] if check else [])
    if drift:
        assert drift[0].site.value == "tijori" and drift[0].surface == "chart-api"
        assert drift[0].request_key == base.request.request_key
    monkeypatch.setattr(
        cli,
        "dispatch_vendor_command",
        partial(dispatch_vendor_command, pool_factory=pg_db.runtime_pool),
    )
    assert cli.main(["vendor", "canary", "--yield-only"]) == int(
        check in ("ROW_COUNT_DROP", "MISSING_OUTCOME")
    )
    captured = capsys.readouterr()
    assert "skipped" not in captured.err
    if check:
        assert check in captured.out and base.request.request_key in captured.out


@pytest.mark.retained
def test_retained_tracer_has_green_canary(rig, capsys):
    from test_vendor_surface_tracer import run_capture

    from fundamentals.api.cli import main

    _, root = rig
    assert run_capture(root) == 0
    capsys.readouterr()
    assert main(["vendor", "canary", "--yield-only"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "skipped" not in captured.err


FIXED = datetime(2026, 10, 28, 9, 30, tzinfo=UTC)
# Retained bodies chosen by catalog id because the canary's own request was not retained.
IDS = {
    "S4": "schedules-api",
    "S5": "investors-api",
    "S6": "chart-api",
    "S7": "company-notebook-modal",
    "T4": "chartdata-price-api",
    "T6": "company-timeline-api",
    "T7": "quarterly-results-api",
}
UTILS = "/static/js/utils.1184f12f9e79.js"
SCHEDULE = '//*[@onclick and contains(@onclick,"showSchedule")]'


@pytest.fixture
def canary_opener():
    """Serve one retained body per canary by surface, under whatever path is requested.

    SHAPE/CONTROL ONLY, not exact-request acceptance: S4 gets another basis, S5, T4 and T6
    another company, T7 page 1 for page 2, and S8 and T8 synthetic redirects (runbook §4).
    """
    import hashlib
    import io
    from email.message import Message
    from pathlib import Path
    from urllib.error import HTTPError
    from urllib.parse import urlsplit
    from urllib.request import OpenerDirector

    from vendor_surface_support import load_request_index

    from fundamentals.ingest.vendor_surface_canary import CANARIES

    rows = load_request_index().values()
    paths = {
        UTILS if item.name == "S7" else urlsplit(item.url).path: item.name for item in CANARIES
    }
    bodies = {"S8": b"", "T8": b""}
    for path, name in paths.items():
        if name not in bodies:
            row = next(
                row
                for row in rows
                if row["path"]
                and row["status"] == 200
                and (row["id"] == IDS[name] if name in IDS else urlsplit(row["url"]).path == path)
                and (name != "S4" or "81159bca4b63" in row["path"])
            )
            bodies[name] = Path(row["path"]).read_bytes()
            assert hashlib.sha256(bodies[name]).hexdigest() == row["sha256"]

    class CanaryOpener(OpenerDirector):
        """Reject unknown requests and retain request metadata for boundary assertions."""

        def __init__(self):
            super().__init__()
            self.calls, self.bodies, self.truncated = [], bodies, False
            self.statuses = {"S8": 302, "T8": 302}
            self.locations = {"T8": "/dashboard/"}

        def open(self, request, timeout):
            self.calls.append(request)
            name = paths[urlsplit(request.full_url).path]
            raw, status = self.bodies[name], self.statuses.get(name, 200)
            headers = Message()
            headers["Content-Type"] = "text/html"
            if self.truncated and name == "S1":
                headers["Content-Length"] = str(len(raw) + 1)
            if name in self.locations:
                headers["Location"] = self.locations[name]
            response = HTTPError(request.full_url, status, "fixture", headers, io.BytesIO(raw))
            if status != 200:
                raise response
            return response

    return CanaryOpener()


def _drop(node):
    """Remove one element from its tree."""
    node.getparent().remove(node)


def _set(attribute, name, value):
    """Replace one canary's served body, status or Location."""
    return lambda opener: getattr(opener, attribute).__setitem__(name, value)


def _sub(name, pattern, replacement):
    """Rewrite one canary's served bytes."""
    return lambda opener: opener.bodies.__setitem__(
        name, re.sub(pattern, replacement, opener.bodies[name], flags=re.S)
    )


def _html(name, edit):
    """Edit one canary's served HTML tree."""

    def apply(opener):
        tree = html.fromstring(opener.bodies[name])
        edit(tree)
        opener.bodies[name] = html.tostring(tree)

    return apply


def _json(name, edit, key=None):
    """Edit one canary's JSON body, or one of its JSON script islands."""

    def load_edit(text):
        data = json.loads(text)
        edit(data)
        return json.dumps(data)

    def island(tree):
        node = tree.xpath(f'//script[@id="{key}"]')[0]
        node.text = load_edit(node.text)

    if key:
        return _html(name, island)
    return lambda opener: opener.bodies.__setitem__(name, load_edit(opener.bodies[name]).encode())


def _hollow(name, xpath):
    """Keep each matched wrapper element but remove everything inside it."""

    def apply(tree):
        for node in tree.xpath(xpath):
            del node[:]
            node.text = None

    return _html(name, apply)


def _rename_schedule(tree):
    """Put a space before the handler's parenthesis."""
    node = tree.xpath(SCHEDULE)[0]
    node.set("onclick", node.get("onclick").replace("showSchedule(", "showSchedule ("))


FAILED, UNUSABLE = "FAILED", "UNUSABLE"
MUTATIONS = [
    pytest.param(None, {}, id="green"),
    pytest.param(_html("S1", _rename_schedule), {"S1.handlers": FAILED}, id="handler"),
    pytest.param(
        _html(
            "S1",
            lambda tree: _drop(
                tree.xpath('//*[@id="quarters"]//table[contains(@class,"data-table")]//th')[1]
            ),
        ),
        {"S1.quarters": FAILED},
        id="period",
    ),
    pytest.param(
        _html(
            "S1",
            lambda tree: tree.xpath('//*[@id="profit-loss"]//table[@class="ranges-table"]//tr[td]')[
                0
            ].append(html.Element("td")),
        ),
        {"S1.growth_rows": FAILED},
        id="growth",
    ),
    pytest.param(
        _html(
            "S1",
            lambda tree: (node := tree.xpath(SCHEDULE)[0]).getparent().append(copy.deepcopy(node)),
        ),
        {"S1.structure": FAILED},
        id="duplicate",
    ),
    pytest.param(
        lambda opener: setattr(opener, "truncated", True),
        {"S1.body_completeness": FAILED, "S4.dependency": None, "S7.dependency": None},
        id="truncated",
    ),
    pytest.param(
        _html(
            "S1",
            lambda tree: tree.xpath('//script[contains(@src,"/js/utils.")]')[0].set(
                "src", "https://untrusted.example/utils.js"
            ),
        ),
        {"S7.dependency": None},
        id="script",
    ),
    pytest.param(
        _set("bodies", "S5", b'{"error": "unavailable"}'), {"S5.holders": FAILED}, id="holders"
    ),
    pytest.param(
        _set("bodies", "S5", b'{"error": {"message": "unavailable"}}'),
        {"S5.holders": FAILED},
        id="holders_nested",
    ),
    pytest.param(
        _json("S6", lambda data: data["datasets"][0].update(values={"error": "unavailable"})),
        {"S6.datasets": FAILED},
        id="chart_values",
    ),
    pytest.param(
        _set("statuses", "S6", 429),
        {"S6.refused": UNUSABLE, "S7.fetch": None, "S8.fetch": None},
        id="stop",
    ),
    pytest.param(_set("statuses", "S8", 200), {"S8.http_status": FAILED}, id="modal"),
    pytest.param(_json("T1", list.clear, "ratios_table"), {"T1.ratios_table": FAILED}, id="ratios"),
    pytest.param(
        _json("T1", lambda data: data[0].update(value=0), "ratios_table"), {}, id="ratios_zero"
    ),
    pytest.param(
        _json("T2", lambda data: data["qt_c"]["data"][0]["value"].pop(), "fin_tables_data"),
        {"T2.statement_rows": FAILED},
        id="financials",
    ),
    pytest.param(
        _sub("T3", rb"var\s+trendData\s*=.*?;", b"var trendData = [];"),
        {"T3.trendData": FAILED},
        id="trend",
    ),
    pytest.param(
        _sub("T3", rb"var\s+chartData\s*=.*?;", b"var chartData = [[], []];"),
        {"T3.chartData": FAILED},
        id="chart_empty_rows",
    ),
    pytest.param(
        _sub("T3", rb"var\s+chartData\s*=.*?;", b'var chartData = [["Promoters", null]];'),
        {"T3.chartData": FAILED},
        id="chart_null_value",
    ),
    pytest.param(
        _sub("T3", rb"var\s+chartData\s*=.*?;", b'var chartData = [["Promoters", "n/a"]];'),
        {"T3.chartData": FAILED},
        id="chart_text_value",
    ),
    pytest.param(
        _sub("T3", rb"var\s+chartData\s*=.*?;", b"var chartData = [1, 2];"),
        {"T3.chartData": FAILED},
        id="chart_scalars",
    ),
    pytest.param(
        _sub("T3", rb"var\s+trendData\s*=.*?;", b'var trendData = [{"name": "x", "data": "e"}];'),
        {"T3.trendData": FAILED},
        id="trend_scalar",
    ),
    pytest.param(
        _json(
            "T4",
            lambda data: data.update(
                data=json.dumps({**json.loads(data["data"]), "eod_price": []})
            ),
        ),
        {"T4.eod_price": FAILED},
        id="price",
    ),
    pytest.param(
        _html(
            "T6",
            lambda tree: [_drop(node) for node in tree.xpath('//tr[contains(@class,"d-none")]')],
        ),
        {"T6.cursor": FAILED},
        id="cursor",
    ),
    pytest.param(
        _hollow("T6", '//td[contains(concat(" ",@class," ")," event ")]'),
        {"T6.events": FAILED},
        id="events_hollow",
    ),
    pytest.param(
        _hollow("T7", '//*[contains(concat(" ",@class," ")," result_item ")]'),
        {"T7.result_cards": FAILED},
        id="results_hollow",
    ),
    pytest.param(
        _set("bodies", "S1", b"  "),
        {"S1.structure": FAILED, "S4.dependency": None, "S7.dependency": None},
        id="s1_blank",
    ),
    pytest.param(_set("locations", "S8", "/login/"), {"S8.refused": UNUSABLE}, id="s8_login"),
]


@pytest.mark.retained
@pytest.mark.parametrize(("mutate", "expected"), MUTATIONS)
def test_canary_shapes_and_controls_cli(
    pg_db, tmp_path, monkeypatch, capsys, canary_opener, mutate, expected
):
    """Shape/control test: the command names each lost marker and registers every response.

    The expected check must appear both in the drift output and in its outcome detail.
    """
    from urllib.parse import parse_qs, urlsplit

    from pydantic import SecretStr

    from fundamentals.api import cli, vendor_surface_cli
    from fundamentals.ingest import vendor_surface_canary
    from fundamentals.ingest.vendor_surface_canary import yield_drift
    from fundamentals.ingest.vendor_surface_fetch import SiteSession

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED

    monkeypatch.setattr(vendor_surface_canary, "datetime", Frozen)
    monkeypatch.setattr("fundamentals.ingest.http_session.time.sleep", lambda seconds: None)
    monkeypatch.setattr(vendor_surface_cli, "STOP_DIR", tmp_path / "stops")
    opener = canary_opener
    if mutate:
        mutate(opener)
    monkeypatch.setattr(
        cli,
        "dispatch_vendor_command",
        partial(
            vendor_surface_cli.dispatch_vendor_command,
            pool_factory=pg_db.runtime_pool,
            opener_factory=lambda: opener,
            sessions_factory=lambda sites: {
                site: SiteSession(
                    site=site, session_cookie=SecretStr("fixture"), cookie_name="sessionid"
                )
                for site in sites
            },
        ),
    )
    root = tmp_path / "captures"
    assert cli.main(["vendor", "canary", "--snapshot-root", str(root)]) == int(bool(expected))
    output = capsys.readouterr().out
    assert {json.loads(line)["check"] for line in output.splitlines()} == expected.keys()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        outcomes = conn.execute(
            "SELECT o.surface,o.status,o.detail,a.location FROM eqos.vendor_outcomes o "
            "JOIN eqos.capture_refs c ON c.id=o.capture_ref_id "
            "JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id ORDER BY o.id"
        ).fetchall()
        digests = dict(
            conn.execute(
                "SELECT parser_version,parser_sha256 FROM eqos.vendor_parser_versions"
            ).fetchall()
        )
        for canary in vendor_surface_canary.CANARIES:
            if f"canary.{canary.name}.v1" in digests:
                assert (
                    digests[f"canary.{canary.name}.v1"]
                    == hashlib.sha256(inspect.getsource(canary.markers).encode()).hexdigest()
                )
        assert not yield_drift(pool, datetime.min.replace(tzinfo=UTC))
    assert len(outcomes) == len(opener.calls) == len(list(root.rglob("record.json")))
    recorded = {surface: (status, detail) for surface, status, detail, _ in outcomes}
    for check, status in expected.items():
        if status:
            outcome, detail = recorded[check.split(".")[0]]
            assert outcome == status and check in detail.split(", ")
    refused = {check[0] for check, status in expected.items() if status == UNUSABLE}
    stops = {"S": "STOP-screener-subscriber", "T": "STOP-tijori"}
    assert {path.name for path in tmp_path.glob("stops/STOP-*")} == {stops[s] for s in refused}
    if not expected:
        assert [surface for surface, *_ in outcomes] == [
            item.name for item in vendor_surface_canary.CANARIES
        ]
        assert all(status == "OK" for _, status, _, _ in outcomes)
        calls = {urlsplit(call.full_url).path: call for call in opener.calls}
        schedule = parse_qs(urlsplit(calls["/api/company/211/schedules/"].full_url).query)
        assert schedule["parent"] and schedule["section"] == ["quarters"]
        assert schedule["consolidated"] == ["true"]
        assert not calls["/company/actions/211/"].has_header("X-requested-with")
        query = parse_qs(urlsplit(calls["/results/quarterly-results/api/"].full_url).query)
        assert query["daterange"] == ["10/21/2026,10/28/2026"]


@pytest.mark.retained
def test_each_canary_check_rejects_bad_status_and_incomplete_body(canary_opener):
    """Shape/control: every pure check validates status and EOF before trusting markers."""
    from fundamentals.contracts.snapshot import BodyCompleteness
    from fundamentals.ingest.vendor_surface_canary import CANARIES

    for canary in CANARIES:
        raw = canary_opener.bodies[canary.name]
        status = canary_opener.statuses.get(canary.name, 200)
        record = record_of(raw).model_copy(update={"http_status": status})
        location = canary_opener.locations.get(canary.name)
        fetched = Fetched(record=record, url=canary.url, location=location)
        assert not canary.check(fetched, raw), canary.name
        for bad in ({"http_status": 404}, {"body_completeness": BodyCompleteness.PARTIAL}):
            rejected = fetched.model_copy(update={"record": record.model_copy(update=bad)})
            assert canary.check(rejected, raw), canary.name


@pytest.mark.parametrize(
    ("location", "passed"),
    [
        ("/dashboard/", True),
        ("https://www.tijorifinance.com/dashboard/", True),
        (None, False),
        ("/login/", False),
        ("https://other.example/dashboard/", False),
        ("//other.example/dashboard/", False),
        ("https://[/dashboard/", False),
    ],
)
def test_t8_needs_a_same_host_dashboard_redirect(location, passed):
    """The logged-in marker is the resolved redirect target, not the Location spelling."""
    from fundamentals.ingest.vendor_surface_canary import _canary

    canary = _canary("T8", "/", location="/dashboard/")
    record = record_of(b"").model_copy(update={"http_status": 302})
    fetched = Fetched(record=record, url=canary.url, location=location)
    assert canary.check(fetched, b"") == (() if passed else ("T8.location",))


@pytest.mark.parametrize(
    "initial", ["company-benchmarking", "benchmarking-benchmarking-financial", "claims-only"]
)
def test_missing_logical_outcomes_are_detected_until_parent_dispatch_completes(pg_db, initial):
    from fundamentals.ingest.vendor_surface_canary import yield_drift

    required = [
        "company-benchmarking",
        "benchmarking-benchmarking-financial",
        "benchmarking-benchmarking-business",
    ]
    record = record_of(b"fixture", "tijori", "vs.company-benchmarking")
    with pg_db.runtime_pool() as pool:
        ref = register(
            pool,
            Fetched(
                record=record,
                url="https://www.tijorifinance.com/company/x/benchmarking/",
                location=None,
            ),
        )
        values = VendorValuesStore(pool)

        def record_outcome(surface, version):
            values.record(
                ref,
                Outcome(
                    surface=surface,
                    parser_version=version,
                    parser_sha256="a" * 64,
                    status=OutcomeStatus.KEPT,
                    symbol=None,
                    detail=None,
                ),
                row_count=0,
            )

        record_outcome(
            initial if initial != "claims-only" else required[0],
            "claims:fake:v1" if initial == "claims-only" else "parent.v1",
        )
        drift = yield_drift(pool, datetime.min.replace(tzinfo=UTC))
        assert [(d.surface, d.check) for d in drift] == [
            (surface, "MISSING_OUTCOME") for surface in required if surface != initial
        ]
        for surface in required:
            if surface != initial:
                record_outcome(surface, "completed.v1")
        assert yield_drift(pool, datetime.min.replace(tzinfo=UTC)) == ()


@pytest.mark.retained
def test_full_canary_reports_no_baseline_without_failure(
    pg_db, tmp_path, monkeypatch, capsys, canary_opener
):
    from pydantic import SecretStr

    from fundamentals.api import cli
    from fundamentals.api.vendor_surface_cli import dispatch_vendor_command
    from fundamentals.contracts.snapshot import CaptureRecord
    from fundamentals.ingest.vendor_surface_canary import CANARIES
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteSession, request_key
    from fundamentals.store.snapshot_store import SnapshotStore

    monkeypatch.setattr("fundamentals.ingest.http_session.time.sleep", lambda _: None)
    monkeypatch.setattr("fundamentals.api.vendor_surface_cli.STOP_DIR", tmp_path / "stops")
    canary = next(c for c in CANARIES if c.name == "S6")
    store = SnapshotStore(tmp_path / "store")
    raw = canary_opener.bodies["S6"]
    base = record_of(raw, Site.SCREENER, "vs.S6")
    record = CaptureRecord.make(
        base.request.model_copy(update={"request_key": request_key(canary.url)}),
        base.retrieved_at,
        200,
        "application/json",
        None,
        base.body,
        base.outcome,
        base.rights,
    )
    store.put_capture(record, raw)
    with pg_db.runtime_pool() as pool:
        ref = register(pool, Fetched(record=record, url=canary.url, location=None))
        VendorValuesStore(pool).record(
            ref,
            Outcome(
                surface="S6",
                parser_version="canary.S6.v0",
                parser_sha256="a" * 64,
                status=OutcomeStatus.EMPTY,
                symbol=None,
                detail=None,
            ),
            row_count=0,
        )
    monkeypatch.setattr(
        cli,
        "dispatch_vendor_command",
        partial(
            dispatch_vendor_command,
            pool_factory=pg_db.runtime_pool,
            opener_factory=lambda: canary_opener,
            sessions_factory=lambda sites: {
                site: SiteSession(
                    site=site, session_cookie=SecretStr("synthetic"), cookie_name="sessionid"
                )
                for site in sites
            },
        ),
    )
    capsys.readouterr()
    result = cli.main(["vendor", "canary", "--snapshot-root", str(tmp_path / "store")])
    assert [json.loads(line)["check"] for line in capsys.readouterr().out.splitlines()] == [
        "NO_BASELINE"
    ]
    assert result == 0
