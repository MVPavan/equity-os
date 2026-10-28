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
