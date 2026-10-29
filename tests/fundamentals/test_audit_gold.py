"""Legacy validation preserves and regresses its established gold reference."""

from decimal import Decimal
from pathlib import Path

import pytest
from test_goal_runner import _REPO_ROOT, EPS, _stock

from fundamentals.api.goal_runner import (
    RunMode,
    SourceKind,
    StockOutcome,
    collect_sources,
    reconcile_stock,
    run_stock,
)
from fundamentals.reconcile.gold_file import DriftKind


@pytest.mark.parametrize(
    "change", ["value", "status", "missing", "new", "empty", "unchanged", "equivalent"]
)
def test_validation_preserves_baseline_and_reports_drift(tmp_path: Path, change: str) -> None:
    stock = _stock()
    kinds = frozenset({SourceKind.NSE, SourceKind.BSE})
    baseline_stock = stock
    if change == "new":
        concepts = stock.concepts.model_copy(
            update={"cross_check": tuple(c for c in stock.concepts.cross_check if c != EPS)}
        )
        baseline_stock = stock.model_copy(update={"concepts": concepts})
    first = run_stock(
        baseline_stock, mode=RunMode.FIXTURE, repo_root=_REPO_ROOT, kinds=kinds, out_dir=tmp_path
    )
    assert first.outcome is StockOutcome.DONE
    path = tmp_path / "SYNTH-Q3FY25.json"
    baseline = path.read_bytes()
    sources = collect_sources(stock, mode=RunMode.FIXTURE, repo_root=_REPO_ROOT, kinds=kinds)
    if change in {"value", "equivalent"}:
        value = "5.000" if change == "equivalent" else "6"
        sources = [
            source.model_copy(
                update={
                    "observations": tuple(
                        obs.model_copy(
                            update={"normalized_value": Decimal(value), "raw_value": value}
                        )
                        if obs.concept_qname == EPS
                        else obs
                        for obs in source.observations
                    )
                }
            )
            for source in sources
        ]
    elif change == "status":
        sources = [source for source in sources if source.kind is SourceKind.NSE]
    elif change == "missing":
        sources = [
            source.model_copy(
                update={
                    "observations": tuple(
                        obs for obs in source.observations if obs.concept_qname != EPS
                    )
                }
            )
            for source in sources
        ]
    elif change == "empty":
        sources = []

    report = reconcile_stock(stock, sources, out_dir=tmp_path)

    assert path.read_bytes() == baseline, "reruns must preserve the reviewed baseline"
    assert report.gold_file_path == str(path)
    regression = report.gold_regression
    assert regression is not None
    if change in {"unchanged", "equivalent"}:
        assert not regression.has_drift
        assert report.outcome is StockOutcome.DONE
        assert report.dod.met
    else:
        expected = {
            "value": DriftKind.VALUE_DRIFT,
            "status": DriftKind.STATUS_CHANGE,
            "missing": DriftKind.MISSING_IN_FRESH,
            "new": DriftKind.NEW_IN_FRESH,
            "empty": DriftKind.MISSING_IN_FRESH,
        }[change]
        assert expected in {drift.kind for drift in regression.drifts}
        assert report.outcome is (
            StockOutcome.BLOCKED if change == "empty" else StockOutcome.NEEDS_ADJUDICATION
        )
        assert not report.dod.met
