"""Yield drift compares only like versions and reports every orphaned capture."""

from datetime import UTC, datetime, timedelta
from functools import partial

import pytest
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
    assert "skipped" in captured.err
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
    assert "skipped" in captured.err


@pytest.fixture
def canary_opener():
    """Serve retained surface shapes; redirect controls have synthetic empty bodies."""
    import hashlib
    import io
    from email.message import Message
    from pathlib import Path
    from urllib.error import HTTPError
    from urllib.parse import urlsplit
    from urllib.request import OpenerDirector

    from vendor_surface_support import load_request_index

    rows = load_request_index()
    references = (
        ("S1", "/company/APARINDS/consolidated/", None),
        ("S2", "/company/NETWEB/consolidated/", None),
        ("S3", "/company/ANONDITA/", None),
        ("S4", "/api/company/211/schedules/", "schedules-api"),
        ("S5", "/api/3/211/investors/promoters/quarterly/", "investors-api"),
        ("S6", "/api/company/211/chart/", "chart-api"),
        ("S7", "/static/js/utils.1184f12f9e79.js", "company-notebook-modal"),
        ("S8", "/company/actions/211/", None),
        ("T1", "/company/apar-industries-limited/", None),
        ("T2", "/company/apar-industries-limited/financials/", None),
        ("T3", "/company/apar-industries-limited/shareholding/", None),
        ("T4", "/api/v1/ind/chartdata/4290/price/", "chartdata-price-api"),
        ("T5", "/api/v1/ind/fund_flow_analysis_data/4290/", None),
        ("T6", "/timeline/company/", "company-timeline-api"),
        ("T7", "/results/quarterly-results/api/", "quarterly-results-api"),
        ("T8", "/", None),
    )
    responses = {}
    for name, path, identifier in references:
        raw = b""
        if name not in ("S8", "T8"):
            row = next(
                row
                for row in rows.values()
                if row["path"]
                and row["status"] == 200
                and (row["id"] == identifier if identifier else urlsplit(row["url"]).path == path)
                and (name != "S4" or "81159bca4b63" in row["path"])
            )
            raw = Path(row["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        responses[path] = [name, raw, 302 if name in ("S8", "T8") else 200]

    class CanaryOpener(OpenerDirector):
        """Reject unknown requests and retain request metadata for boundary assertions."""

        def __init__(self):
            super().__init__()
            self.calls = []
            self.responses = responses
            self.location = "/dashboard/"
            self.truncated = False

        def open(self, request, timeout):
            self.calls.append(request)
            name, raw, status = self.responses[urlsplit(request.full_url).path]
            headers = Message()
            headers["Content-Type"] = "text/html"
            if self.truncated and name == "S1":
                headers["Content-Length"] = str(len(raw) + 1)
            if name == "T8":
                headers["Location"] = self.location
            response = HTTPError(request.full_url, status, "fixture", headers, io.BytesIO(raw))
            if status != 200:
                raise response
            return response

    return CanaryOpener()


@pytest.mark.retained
@pytest.mark.parametrize(
    ("mutation", "failed"),
    [
        (None, None),
        ("handler", "S1"),
        ("period", "S1"),
        ("growth", "S1"),
        ("ratios", "T1"),
        ("price", "T4"),
        ("redirect", "T8"),
        ("stop", "S6"),
        ("script", "S7"),
        ("duplicate", "S1"),
        ("truncated", "S1"),
        ("financials", "T2"),
        ("trend", "T3"),
        ("cursor", "T6"),
        ("modal", "S8"),
        ("holders", "S5"),
        ("chart_values", "S6"),
        ("ratios_zero", None),
    ],
)
def test_runbook_canaries_cli_retains_outcomes(
    pg_db, tmp_path, monkeypatch, capsys, canary_opener, mutation, failed
):
    """One command must detect silent shape loss and register even failed controls."""
    import json
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setattr("fundamentals.ingest.http_session.time.sleep", lambda seconds: None)

    from lxml import html
    from pydantic import SecretStr

    from fundamentals.api import cli, vendor_surface_cli
    from fundamentals.ingest.vendor_surface_canary import yield_drift
    from fundamentals.ingest.vendor_surface_fetch import SiteSession

    opener = canary_opener
    target = {
        "ratios": "T1",
        "price": "T4",
        "financials": "T2",
        "trend": "T3",
        "cursor": "T6",
        "modal": "S8",
        "holders": "S5",
        "chart_values": "S6",
        "ratios_zero": "T1",
    }.get(mutation, "S1")
    response = next(value for value in opener.responses.values() if value[0] == target)
    if mutation in (
        "handler",
        "period",
        "growth",
        "ratios",
        "script",
        "duplicate",
        "financials",
        "cursor",
        "ratios_zero",
    ):
        tree = html.fromstring(response[1])
        if mutation == "handler":
            node = tree.xpath('//*[@onclick and contains(@onclick,"showSchedule")]')[0]
            node.set("onclick", node.get("onclick").replace("showSchedule(", "showSchedule ("))
        elif mutation == "period":
            node = tree.xpath('//*[@id="quarters"]//table[contains(@class,"data-table")]//th')[1]
            node.getparent().remove(node)
        elif mutation == "growth":
            node = tree.xpath('//*[@id="profit-loss"]//table[@class="ranges-table"]//tr[td]')[0]
            node.append(html.Element("td"))
        elif mutation == "ratios":
            tree.xpath('//script[@id="ratios_table"]')[0].text = "[]"
        elif mutation == "ratios_zero":
            node = tree.xpath('//script[@id="ratios_table"]')[0]
            data = json.loads(node.text)
            data[0]["value"] = 0
            node.text = json.dumps(data)
        elif mutation == "duplicate":
            import copy

            node = tree.xpath('//*[@onclick and contains(@onclick,"showSchedule")]')[0]
            node.getparent().append(copy.deepcopy(node))
        elif mutation == "financials":
            node = tree.xpath('//script[@id="fin_tables_data"]')[0]
            data = json.loads(node.text)
            data["qt_c"]["data"][0]["value"].pop()
            node.text = json.dumps(data)
        elif mutation == "cursor":
            for node in tree.xpath('//tr[contains(concat(" ",@class," ")," d-none ")]'):
                node.getparent().remove(node)
        else:
            node = tree.xpath('//script[contains(@src,"/js/utils.")]')[0]
            node.set("src", "https://untrusted.example/utils.js")
        response[1] = html.tostring(tree)
    elif mutation == "holders":
        response[1] = b'{"error": "unavailable"}'
    elif mutation == "chart_values":
        document = json.loads(response[1])
        document["datasets"][0]["values"] = {"error": "unavailable"}
        response[1] = json.dumps(document).encode()
    elif mutation == "price":
        document = json.loads(response[1])
        data = json.loads(document["data"])
        data["eod_price"] = []
        document["data"] = json.dumps(data)
        response[1] = json.dumps(document).encode()
    elif mutation == "trend":
        import re

        response[1] = re.sub(
            rb"var\s+trendData\s*=.*?;", b"var trendData = [];", response[1], flags=re.S
        )
    elif mutation == "truncated":
        opener.truncated = True
    elif mutation == "modal":
        response[2] = 200
    elif mutation == "redirect":
        opener.location = "/login/"
    elif mutation == "stop":
        next(value for value in opener.responses.values() if value[0] == "S6")[2] = 429

    monkeypatch.setattr(vendor_surface_cli, "STOP_DIR", tmp_path / "stops")
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
    assert cli.main(["vendor", "canary", "--snapshot-root", str(root)]) == int(failed is not None)
    output = capsys.readouterr().out
    failures = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    assert any(item["surface"] == failed for item in failures) if failed else not failures
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        outcomes = conn.execute(
            "SELECT c.capture_id,o.surface,o.status,a.location FROM eqos.vendor_outcomes o "
            "JOIN eqos.capture_refs c ON c.id=o.capture_ref_id "
            "JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id ORDER BY o.id"
        ).fetchall()
        assert len(outcomes) == len(opener.calls)
        if mutation == "stop":
            assert (tmp_path / "stops" / "STOP-screener-subscriber").is_file()
            assert not any(
                urlsplit(call.full_url).path.startswith("/static/") for call in opener.calls
            )
        assert not yield_drift(pool, datetime.min.replace(tzinfo=UTC))
        if failed:
            assert (
                any(surface == failed and status == "FAILED" for _, surface, status, _ in outcomes)
                if mutation != "script"
                else True
            )
        else:
            assert {surface for _, surface, _, _ in outcomes} == {
                f"{site}{index}" for site in ("S", "T") for index in range(1, 9)
            }
            assert all(status == "OK" for _, _, status, _ in outcomes)
            assert outcomes[-1][3] == "/dashboard/"
            calls = {urlsplit(call.full_url).path: call for call in opener.calls}
            schedule = parse_qs(urlsplit(calls["/api/company/211/schedules/"].full_url).query)
            assert schedule["parent"] and schedule["section"] == ["quarters"]
            assert schedule["consolidated"] == ["true"]
            assert not calls["/company/actions/211/"].has_header("X-requested-with")
            dates = parse_qs(urlsplit(calls["/results/quarterly-results/api/"].full_url).query)[
                "daterange"
            ][0]
            assert dates == (datetime.now(UTC) - timedelta(days=7)).strftime(
                "%m/%d/%Y"
            ) + "," + datetime.now(UTC).strftime("%m/%d/%Y")
        assert len(list(root.rglob("record.json"))) == len(outcomes)


@pytest.mark.retained
def test_each_runbook_check_rejects_bad_status_and_incomplete_body(canary_opener):
    """Every named pure check must validate status and EOF before trusting markers."""
    from fundamentals.contracts.snapshot import BodyCompleteness
    from fundamentals.ingest.vendor_surface_canary import CANARIES

    for canary, (_, raw, status) in zip(CANARIES, canary_opener.responses.values(), strict=True):
        record = record_of(raw).model_copy(update={"http_status": status})
        assert not canary.check(record, raw), canary.name
        assert canary.check(record.model_copy(update={"http_status": 404}), raw), canary.name
        partial = record.model_copy(update={"body_completeness": BodyCompleteness.PARTIAL})
        assert canary.check(partial, raw), canary.name
