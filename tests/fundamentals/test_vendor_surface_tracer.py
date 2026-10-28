"""The tracer keeps raw evidence, parses stored bytes, and reports every requested set."""

import json
from decimal import Decimal

import pytest
import yaml
from vendor_surface_support import rig

from fundamentals.api.cli import main

__all__ = ["rig"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def run_capture(root):
    return main(
        [
            "vendor",
            "capture",
            "--symbol",
            "APARINDS",
            "--surface",
            "screener:chart-api",
            "--snapshot-root",
            str(root),
        ]
    )


@pytest.mark.parametrize(
    "chart",
    [
        None,
        '{"datasets": {"label": "Price", "values": []}}',
        '{"datasets": ["invalid"]}',
        '{"datasets": [{"label": "Price", "values": {"2026-10-28": 9107.50}}]}',
        '{"datasets": [{"label": "Price", "values": ["123"]}]}',
        '{"datasets": [{"label": "Price", "values": [["2026-10-28", 1, 2]]}]}',
        '{"datasets": [{"label": "Price", "values": [[123, 1]]}]}',
        '{"datasets": [{"label": "Price", "values": [["2026-10-28", "123"]]}]}',
        '{"datasets": [{"label": "Price", "values": [["2026-10-28", true]]}]}',
        '{"datasets": [{"label": "Price", "values": [["2026-10-28", 1e-8], '
        '["2026-10-29", 1e20], ["2026-10-30", null]]}]}',
    ],
)
def test_tracer_cli_retained_chart(rig, pg_db, capsys, monkeypatch, chart):
    from fundamentals.ingest import vendor_surface_parse

    parses = []
    original = vendor_surface_parse.parse_document

    def counted(text):
        parses.append(True)
        return original(text)

    monkeypatch.setattr(vendor_surface_parse, "parse_document", counted)
    opener, root = rig
    original_open = opener.open

    def chart_response(request, timeout):
        import io
        from urllib.error import HTTPError

        response = original_open(request, timeout)
        if chart is not None and "/chart/" in request.full_url and response.code == 200:
            return HTTPError(
                request.full_url, 200, "fixture", response.headers, io.BytesIO(chart.encode())
            )
        return response

    monkeypatch.setattr(opener, "open", chart_response)
    assert run_capture(root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "expected": 7,
        "completed": 1 if chart is not None and "1e-8" not in chart else 2,
        "refused": [],
        "incomplete": opener.calls[1 if chart is not None and "1e-8" not in chart else 2 :],
        "stopped_sites": [],
    }
    assert len(opener.calls) == 7
    assert len(parses) == 1
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        if chart is not None:
            assert conn.execute(
                "SELECT status FROM eqos.vendor_outcomes "
                "WHERE surface='chart-api' ORDER BY id LIMIT 1"
            ).fetchone() == (("PARTIAL",) if "1e-8" in chart else ("FAILED",))
            assert conn.execute(
                "SELECT raw_text,value FROM eqos.vendor_values ORDER BY row_index"
            ).fetchall() == (
                [
                    ("1e-8", Decimal("0.00000001")),
                    ("1e20", Decimal("100000000000000000000")),
                    ("null", None),
                ]
                if "1e-8" in chart
                else []
            )
            return
        assert conn.execute(
            "SELECT column_label, count(*) FROM eqos.vendor_values "
            "GROUP BY column_label ORDER BY column_label"
        ).fetchall() == [("200 DMA", 248), ("50 DMA", 248), ("Price on NSE", 248), ("Volume", 248)]
        assert conn.execute(
            "SELECT raw_text,value FROM eqos.vendor_values WHERE row_index=0 "
            "AND column_index IN (0,3) ORDER BY column_index"
        ).fetchall() == [("9107.50", Decimal("9107.50")), ("168786", Decimal("168786"))]
        assert conn.execute("SELECT count(*) FROM eqos.capture_refs").fetchone() == (7,)
        assert conn.execute("SELECT count(*) FROM eqos.vendor_outcomes").fetchone() == (7,)


@pytest.mark.parametrize("registration_fails", [False, True])
def test_stop_registered_before_run_ends(rig, pg_db, capsys, monkeypatch, registration_fails):
    from fundamentals.api.vendor_surface_cli import STOP_DIR
    from fundamentals.ingest import vendor_surface_capture as capturing

    original = capturing.register
    marker = STOP_DIR / "STOP-screener-subscriber"

    def checked_register(pool, fetched):
        assert not marker.exists()
        if fetched.record.http_status == 429 and registration_fails:
            raise RuntimeError("fixture registration failure")
        return original(pool, fetched)

    monkeypatch.setattr(capturing, "register", checked_register)
    opener, root = rig
    opener.stop = True
    if registration_fails:
        with pytest.raises(RuntimeError, match="fixture registration failure"):
            run_capture(root)
        assert marker.exists()
        return
    assert run_capture(root) == 0
    assert marker.exists()
    report = json.loads(capsys.readouterr().out)
    assert report["stopped_sites"] == ["screener-subscriber"]
    assert report["expected"] == 7 and report["completed"] == 2
    assert len(opener.calls) == 3
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.capture_refs c JOIN eqos.vendor_outcomes o "
            "ON o.capture_ref_id=c.id WHERE o.status='UNUSABLE'"
        ).fetchone() == (1,)


@pytest.mark.parametrize("previous_outcome", [True, False])
@pytest.mark.parametrize("binding", ["valid", "missing", "mismatch"])
def test_failed_parser_and_network_free_reparse(
    rig, pg_db, capsys, monkeypatch, previous_outcome, binding, tmp_path
):
    from fundamentals.ingest import vendor_surface_capture as capturing
    from fundamentals.ingest import vendor_surface_parse as parsing
    from fundamentals.ingest.vendor_surface_fetch import Site

    opener, root = rig
    key = (Site.SCREENER, "chart-api")
    entry = parsing.PARSERS[key]

    def broken(body, context):
        if not previous_outcome:
            raise SystemExit("fixture interruption after registration")
        raise ValueError("fixture parser failure")

    monkeypatch.setitem(
        parsing.PARSERS, key, parsing.ParserEntry(version="screener:chart-api.v0", parse=broken)
    )
    if previous_outcome:
        run_capture(root)
    else:
        with pytest.raises(SystemExit, match="after registration"):
            run_capture(root)
    capsys.readouterr()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE status='FAILED'"
        ).fetchone() == (int(previous_outcome),)

    attempts = []

    def with_identity(body, context):
        attempts.append(True)
        assert context.ids is not None
        assert context.ids.nse_symbol == "APARINDS"
        assert context.ids.screener_company_id == 211
        return entry.parse(body, context)

    monkeypatch.setitem(parsing.PARSERS, key, entry.model_copy(update={"parse": with_identity}))
    before = len(opener.calls)
    watchlist = capturing.WATCHLIST
    if binding != "valid":
        config = yaml.safe_load(watchlist.read_text())
        if binding == "missing":
            config["stocks"] = [
                stock
                for stock in config["stocks"]
                if stock["identifiers"]["nse_symbol"] != "APARINDS"
            ]
        else:
            stock = next(
                stock
                for stock in config["stocks"]
                if stock["identifiers"]["nse_symbol"] == "APARINDS"
            )
            stock["identifiers"]["screener_company_id"] = 999999999
        config_path = tmp_path / "watchlist.yaml"
        config_path.write_text(yaml.safe_dump(config))
        monkeypatch.setattr(capturing, "WATCHLIST", config_path)
        for _ in range(2):
            assert (
                main(
                    [
                        "vendor",
                        "reparse",
                        "--surface",
                        "screener:chart-api",
                        "--snapshot-root",
                        str(root),
                    ]
                )
                == 0
            )
        assert attempts == []
        with pg_db.runtime_pool() as pool, pool.connection() as conn:
            assert conn.execute(
                "SELECT count(*) FROM eqos.vendor_outcomes WHERE parser_version=%s",
                (entry.version,),
            ).fetchone() == (0,)
            assert conn.execute(
                "SELECT DISTINCT status,detail FROM eqos.vendor_outcomes "
                "WHERE parser_version='screener:gate.identity.v1'"
            ).fetchall() == [("UNUSABLE", "verified company binding unavailable")]
        monkeypatch.setattr(capturing, "WATCHLIST", watchlist)
    assert (
        main(["vendor", "reparse", "--surface", "screener:chart-api", "--snapshot-root", str(root)])
        == 0
    )
    assert len(opener.calls) == before
    assert attempts == [True]
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE status='OK' AND symbol='APARINDS'"
        ).fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM eqos.vendor_values").fetchone() == (992,)


def test_unknown_topology_does_not_block_chart(rig, pg_db, capsys, monkeypatch, tmp_path):
    from fundamentals.api import vendor_surface_cli
    from fundamentals.ingest import vendor_surface_capture as capturing

    watchlist = capturing.WATCHLIST
    config = yaml.safe_load(watchlist.read_text())
    stock = next(
        stock for stock in config["stocks"] if stock["identifiers"]["nse_symbol"] == "APARINDS"
    )
    stock["identifiers"]["needs_verification"] = ["screener_warehouse_id_standalone"]
    config_path = tmp_path / "watchlist.yaml"
    config_path.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(vendor_surface_cli, "WATCHLIST", config_path)
    monkeypatch.setattr(capturing, "WATCHLIST", config_path)
    opener, root = rig
    run_capture(root)
    report = json.loads(capsys.readouterr().out)
    assert report["completed"] == 1 and opener.calls[0] in report["incomplete"]
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT detail FROM eqos.vendor_outcomes "
            "WHERE parser_version='screener:gate.topology.v1'"
        ).fetchone() == ("topology unknown",)
        assert conn.execute("SELECT count(*) FROM eqos.vendor_values").fetchone() == (992,)
    monkeypatch.setattr(capturing, "WATCHLIST", watchlist)
    assert (
        main(
            [
                "vendor",
                "reparse",
                "--surface",
                "screener:company-page",
                "--snapshot-root",
                str(root),
            ]
        )
        == 0
    )
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE status='KEPT'"
        ).fetchone() == (1,)


@pytest.mark.parametrize("group", ["SERIES", "NONE"])
def test_incomplete_body_never_parsed(rig, pg_db, group):
    from datetime import UTC, datetime
    from pathlib import Path

    from retention_support import record_of

    from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
    from fundamentals.contracts.snapshot import (
        CAPTURE_SCHEMA_VERSION,
        BodyCompleteness,
        BodyReadIssue,
        CaptureRecord,
    )
    from fundamentals.ingest.vendor_surface_capture import Request, parse_and_record
    from fundamentals.ingest.vendor_surface_fetch import Fetched
    from fundamentals.ingest.vendor_surface_specs import ParseGroup, load_specs
    from fundamentals.store.snapshot_store import SnapshotStore
    from fundamentals.store.vendor_values_store import VendorValuesStore, register

    _, root = rig
    store = SnapshotStore(root)
    spec = load_specs(
        Path("config/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )[1].model_copy(update={"group": ParseGroup(group)})
    base = record_of(b"prefix", "screener-subscriber", "vs.chart-api")
    record = CaptureRecord.make(
        base.request,
        datetime.now(UTC),
        200,
        "application/json",
        None,
        base.body,
        OutcomeRecord(
            code=OutcomeCode.TRANSPORT_ERROR, native_kind="fixture", native_value="partial"
        ),
        base.rights,
        schema_version=CAPTURE_SCHEMA_VERSION,
        body_completeness=BodyCompleteness.PARTIAL,
        body_read_issue=BodyReadIssue.READ_INTERRUPTED,
    )
    store.put_capture(record, b"prefix")
    with pg_db.runtime_pool() as pool:
        ref = register(
            pool, Fetched(record=record, url="https://www.screener.in/chart/", location=None)
        )
        states = parse_and_record(
            store,
            VendorValuesStore(pool),
            ref,
            record,
            Request(spec=spec, url="https://www.screener.in/chart/", ids=None, due_since=None),
        )
        assert [state.value for state in states] == ["UNUSABLE"]


def test_kept_parent_dispatches_section_parser(rig, pg_db, monkeypatch):
    from fundamentals.api import vendor_surface_cli
    from fundamentals.ingest.vendor_surface_fetch import Site
    from fundamentals.ingest.vendor_surface_parse import PARSERS, ParserEntry, company_page

    original = vendor_surface_cli.load_specs

    def with_section(path, catalog):
        page, chart = original(path, catalog)
        return page.model_copy(update={"sections": ("section-proof",)}), chart

    monkeypatch.setattr(vendor_surface_cli, "load_specs", with_section)
    monkeypatch.setitem(
        PARSERS,
        (Site.SCREENER, "section-proof"),
        ParserEntry(version="screener:section-proof.v1", parse=company_page),
    )
    _, root = rig
    assert run_capture(root) == 0
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT status FROM eqos.vendor_outcomes WHERE surface='section-proof'"
        ).fetchone() == ("EMPTY",)


@pytest.mark.parametrize(
    "mutation", ["basis", "missing", "empty", "anonymous", "identity", "empty-body", "invalid-utf8"]
)
def test_chart_discovery_from_retained_page(rig, capsys, monkeypatch, mutation):
    from fundamentals.ingest.screener_session_page import parse_document

    opener, root = rig
    original = opener.open

    def mutated(request, timeout):
        response = original(request, timeout)
        if request.full_url.startswith("https://www.screener.in/company/"):
            import io
            from urllib.error import HTTPError

            from lxml import html

            if mutation in ("empty-body", "invalid-utf8"):
                return HTTPError(
                    request.full_url,
                    200,
                    "fixture",
                    response.headers,
                    io.BytesIO(b"" if mutation == "empty-body" else b"\xff"),
                )

            tree = parse_document(response.read().decode())
            if mutation == "basis":
                tree.xpath('//*[@id="company-info"]')[0].attrib.pop("data-warehouse-id")
            elif mutation == "missing":
                for control in tree.xpath('//*[@id="chart"]//*[@name="metrics"]'):
                    control.getparent().remove(control)
            elif mutation == "empty":
                for control in tree.xpath('//*[@id="chart"]//*[@name="metrics"]'):
                    control.set("value", "")
            elif mutation == "anonymous":
                for form in tree.xpath('//form[@action="/logout/"]'):
                    form.getparent().remove(form)
            else:
                tree.xpath('//*[@id="company-info"]')[0].set("data-company-id", "1")
            response = HTTPError(
                request.full_url, 200, "fixture", response.headers, io.BytesIO(html.tostring(tree))
            )
        return response

    monkeypatch.setattr(opener, "open", mutated)
    run_capture(root)
    report = json.loads(capsys.readouterr().out)
    if mutation == "basis":
        assert len(opener.calls) == 7 and report["completed"] == 1
    else:
        assert len(opener.calls) == 1
    assert report["incomplete"]
    if mutation in ("missing", "empty"):
        assert report["expected"] == 2 and report["completed"] == 1
    if mutation in ("empty-body", "invalid-utf8"):
        assert report["expected"] == 1 and report["completed"] == 0


def test_stop_shared_across_snapshot_roots(rig, capsys):
    opener, root = rig
    opener.stop = True
    run_capture(root)
    capsys.readouterr()
    before = len(opener.calls)
    run_capture(root.with_name("other-captures"))
    report = json.loads(capsys.readouterr().out)
    assert report["stopped_sites"] == ["screener-subscriber"]
    assert len(opener.calls) == before
