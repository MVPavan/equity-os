"""The tracer keeps raw evidence, parses stored bytes, and reports every requested set."""

import json
from decimal import Decimal

import pytest
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


def test_tracer_cli_retained_chart(rig, pg_db, capsys):
    opener, root = rig
    assert run_capture(root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "expected": 7,
        "completed": 2,
        "refused": [],
        "incomplete": opener.calls[2:],
        "stopped_sites": [],
    }
    assert len(opener.calls) == 7
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
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


def test_stop_registered_before_run_ends(rig, pg_db, capsys):
    opener, root = rig
    opener.stop = True
    assert run_capture(root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stopped_sites"] == ["screener-subscriber"]
    assert report["expected"] == 7 and report["completed"] == 2
    assert len(opener.calls) == 3
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.capture_refs c JOIN eqos.vendor_outcomes o "
            "ON o.capture_ref_id=c.id WHERE o.status='UNUSABLE'"
        ).fetchone() == (1,)


def test_failed_parser_and_network_free_reparse(rig, pg_db, capsys, monkeypatch):
    from fundamentals.ingest import vendor_surface_parse as parsing
    from fundamentals.ingest.vendor_surface_fetch import Site

    opener, root = rig
    key = (Site.SCREENER, "chart-api")
    entry = parsing.PARSERS[key]

    def broken(body, context):
        raise ValueError("fixture parser failure")

    monkeypatch.setitem(
        parsing.PARSERS, key, parsing.ParserEntry(version="screener:chart-api.v0", parse=broken)
    )
    run_capture(root)
    capsys.readouterr()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE status='FAILED'"
        ).fetchone() == (1,)
    monkeypatch.setitem(parsing.PARSERS, key, entry)
    before = len(opener.calls)
    assert (
        main(["vendor", "reparse", "--surface", "screener:chart-api", "--snapshot-root", str(root)])
        == 0
    )
    assert len(opener.calls) == before
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.vendor_outcomes WHERE status='OK'"
        ).fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM eqos.vendor_values").fetchone() == (992,)


def test_unknown_topology_does_not_block_chart(rig, pg_db, capsys, monkeypatch):
    from fundamentals.api import vendor_surface_cli
    from fundamentals.ingest import vendor_surface_capture as capturing

    original = capturing.company_ids
    monkeypatch.setattr(
        capturing,
        "company_ids",
        lambda stock: original(stock).model_copy(update={"topology": None}),
    )
    monkeypatch.setattr(vendor_surface_cli, "company_ids", capturing.company_ids)
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
    monkeypatch.setattr(capturing, "company_ids", original)
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
