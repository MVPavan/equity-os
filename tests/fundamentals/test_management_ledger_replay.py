"""Replay must preserve the evidence and status originally recorded for a quarter."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import Any

import pymupdf
import pytest
from tests.fundamentals.test_pipeline_temporal_admission import run_synthetic_pipeline

from fundamentals.api.pipeline import PipelineResult
from fundamentals.contracts.guidance_claim import EpistemicClass, GuidanceClaim
from fundamentals.contracts.observation import Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.output.management_ledger import (
    LedgerStatus,
    load_ledger,
    reconcile_ledger,
    save_ledger,
)
from fundamentals.store.fact_store import FactStore


def claim(quarter: str, lower: str = "10") -> GuidanceClaim:
    """Build synthetic quote evidence without accessing retained company documents."""
    return GuidanceClaim(
        metric="margin",
        lower_bound=Decimal(lower),
        upper_bound=Decimal("12"),
        unit="%",
        constant_currency=False,
        horizon="FY27",
        scope=Scope.CONSOLIDATED,
        source_quote=f"We expect {lower}% to 12% for FY27.",
        provenance=Provenance(
            source_id=f"synthetic-{quarter}",
            file_sha256="ab" * 32,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=1,
            block=0,
            span="0:35",
            retrieved_at=datetime(2027, 7, 1, tzinfo=UTC),
        ),
    )


def test_same_quarter_replay_preserves_new_and_modified_status_and_history() -> None:
    """Replay must not turn NEW/MODIFIED into REAFFIRMED or append history again."""
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    assert (
        reconcile_ledger(first, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
        == first
    )
    second = reconcile_ledger(
        first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    replay = reconcile_ledger(
        second, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    assert replay == second
    assert replay.entries[0].status is LedgerStatus.MODIFIED
    assert len(replay.entries[0].history) == 1


def test_saving_later_quarter_retains_earlier_snapshot(tmp_path: Path) -> None:
    """A later save must preserve a loadable version of the original quarter."""
    from fundamentals.output.management_ledger import load_ledger, save_ledger

    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    second = reconcile_ledger(
        first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    save_ledger(first, path)
    save_ledger(second, path)
    snapshot = tmp_path / "ledger.quarters" / "FY27_Q1.json"
    assert snapshot.is_file(), "later saves must retain the original quarter"
    assert load_ledger(path, issuer_quarter="FY27_Q1", symbol="SYNTH") == first
    assert load_ledger(path) == second


@pytest.mark.parametrize(
    "change", ["lower_bound", "source_quote", "qualifiers", "epistemic_class", "provenance"]
)
def test_changed_same_quarter_evidence_is_refused(change: str, tmp_path: Path) -> None:
    """Same range does not make changed qualifiers or source evidence identical."""
    original = claim("Q1")
    changes: dict[str, object] = {
        "lower_bound": Decimal("11"),
        "source_quote": "A different management quote with 10% to 12%.",
        "qualifiers": ("subject to market conditions",),
        "epistemic_class": EpistemicClass.OPINION,
        "provenance": original.provenance.model_copy(update={"file_sha256": "cd" * 32}),
    }
    ledger = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[original])
    path = tmp_path / "ledger.json"
    save_ledger(ledger, path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="conflicting same-quarter"):
        reconcile_ledger(
            ledger,
            symbol="SYNTH",
            issuer_quarter="FY27_Q1",
            claims=[original.model_copy(update={change: changes[change]})],
        )
    assert path.read_bytes() == before
    assert load_ledger(path) == ledger


def test_conflicting_snapshot_save_cannot_clobber_retained_output(tmp_path: Path) -> None:
    """Even callers bypassing reconciliation cannot overwrite an existing quarter."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    conflict = reconcile_ledger(
        None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1", "11")]
    )
    save_ledger(first, path)
    before = {
        file.name: file.read_bytes() for file in (tmp_path / "ledger.quarters").glob("*.json")
    }
    with pytest.raises(ValueError, match="conflicting same-quarter"):
        save_ledger(conflict, path)
    assert load_ledger(path) == first
    assert {
        file.name: file.read_bytes() for file in (tmp_path / "ledger.quarters").glob("*.json")
    } == before


def test_historical_replay_leaves_current_authority_and_all_snapshots_unchanged(
    tmp_path: Path,
) -> None:
    """Q0 -> Q1 -> Q2 then replay Q0/Q1, without rolling the current view back."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    second = reconcile_ledger(
        first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    third = reconcile_ledger(second, symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[])
    for ledger in (first, second, third):
        save_ledger(ledger, path)
    before = {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")}
    for quarter, claims, expected in (
        ("FY27_Q1", [claim("Q1")], first),
        ("FY27_Q2", [claim("Q2", "11")], second),
        ("FY27_Q3", [], third),
    ):
        base = load_ledger(path, issuer_quarter=quarter, symbol="SYNTH")
        replay = reconcile_ledger(base, symbol="SYNTH", issuer_quarter=quarter, claims=claims)
        assert replay == expected
        save_ledger(replay, path)
        assert load_ledger(path) == third
    assert {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")} == before
    assert third.entries[0].status is LedgerStatus.CARRIED
    assert third.version == 3
    assert load_ledger(path, issuer_quarter="FY27_Q4") == third


def test_legacy_migration_retains_known_state_and_refuses_missing_history(tmp_path: Path) -> None:
    """Legacy state seeds forward reconciliation but cannot invent prior quarters."""
    path = tmp_path / "ledger.json"
    original = reconcile_ledger(
        None, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2")]
    )
    payload = original.model_dump(mode="json")
    payload.pop("quarter_claims")
    path.write_text(json.dumps(payload), encoding="utf-8")
    legacy = load_ledger(path)
    assert legacy is not None
    assert (
        reconcile_ledger(legacy, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2")])
        == legacy
    )
    with pytest.raises(ValueError, match="historical replay"):
        load_ledger(path, issuer_quarter="FY27_Q1")
    forward = reconcile_ledger(legacy, symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[])
    save_ledger(forward, path)
    assert load_ledger(path, issuer_quarter="FY27_Q2") == legacy
    assert load_ledger(path) == forward
    assert (tmp_path / "ledger.quarters" / "FY27_Q2.json").is_file()
    with pytest.raises(ValueError, match="conflicting same-quarter"):
        reconcile_ledger(
            legacy,
            symbol="SYNTH",
            issuer_quarter="FY27_Q2",
            claims=[claim("Q2").model_copy(update={"qualifiers": ("unretained",)})],
        )


def test_wrong_issuer_and_duplicate_claims_fail_before_persistence(tmp_path: Path) -> None:
    """Issuer isolation and unique commitment keys are required on all replays."""
    path = tmp_path / "ledger.json"
    ledger = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    save_ledger(ledger, path)
    with pytest.raises(ValueError, match="issuer"):
        reconcile_ledger(ledger, symbol="OTHER", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    with pytest.raises(ValueError, match="issuer"):
        load_ledger(path, symbol="OTHER")
    with pytest.raises(ValueError, match="issuer"):
        save_ledger(ledger.model_copy(update={"symbol": "OTHER"}), path)
    with pytest.raises(ValueError, match="duplicate"):
        reconcile_ledger(
            ledger, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1"), claim("Q1")]
        )
    assert load_ledger(path) == ledger


@pytest.mark.parametrize("boundary", ["link", "replace", "fsync"])
def test_interrupted_persistence_preserves_prior_data_and_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """An interrupted write exposes only complete JSON and never loses prior outputs."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    second = reconcile_ledger(
        first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    save_ledger(first, path)
    before = path.read_bytes()
    original_operation = getattr(os, boundary)

    def interrupt(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic interrupted persistence")

    monkeypatch.setattr(os, boundary, interrupt)
    with pytest.raises(OSError, match="interrupted"):
        save_ledger(second, path)
    assert path.read_bytes() == before
    assert load_ledger(path, issuer_quarter="FY27_Q1") == first
    assert load_ledger(path) == (second if boundary == "replace" else first)
    assert not list(tmp_path.rglob(".FY27_Q2.json.*"))
    monkeypatch.setattr(os, boundary, original_operation)
    save_ledger(second, path)
    assert load_ledger(path) == second
    assert json.loads(path.read_text())["updated_quarter"] == "FY27_Q2"


@pytest.mark.parametrize("quarter", ["../FY27_Q1", "FY27_Q0", "FY27_Q5", "FY270_Q1"])
def test_invalid_quarter_cannot_become_a_snapshot_path(quarter: str) -> None:
    """Only valid issuer-quarter tokens can name retained outputs."""
    with pytest.raises(ValueError, match="invalid issuer quarter"):
        reconcile_ledger(None, symbol="SYNTH", issuer_quarter=quarter, claims=[])


def _synthetic_pipeline_run(
    tmp_path: Path, quarter: str, lower: str, store: FactStore
) -> PipelineResult:
    """Run the actual pipeline with generated local PDFs and synthetic XBRL bytes."""
    from fundamentals.api.config import GuidanceConfig, GuidanceRuleConfig, load_config
    from fundamentals.api.pipeline import XbrlInput

    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config" / "fundamentals.yaml")
    start, end = (
        (date(2026, 4, 1), date(2026, 6, 30))
        if quarter == "FY27_Q1"
        else (date(2026, 7, 1), date(2026, 9, 30))
    )
    config = config.model_copy(
        update={
            "issuer": config.issuer.model_copy(
                update={"name": "Synthetic Corp", "nse_symbol": "SYNTH"}
            ),
            "quarter": config.quarter.model_copy(
                update={
                    "issuer_quarter": quarter,
                    "period_start": start,
                    "period_end": end,
                    "knowledge_cutoff": datetime(2026, end.month, end.day, tzinfo=UTC),
                }
            ),
            "results_pdf": config.results_pdf.model_copy(
                update={"source_id": f"synthetic-results-{quarter}"}
            ),
            "transcript_pdf": config.transcript_pdf.model_copy(
                update={"source_id": f"synthetic-transcript-{quarter}"}
            ),
            "xbrl": config.xbrl.model_copy(update={"source_id": "synthetic-xbrl"}),
            "ledger_path": str(tmp_path / "ledger.json"),
            "guidance": GuidanceConfig(
                rules=(
                    GuidanceRuleConfig(
                        metric="margin",
                        label="Margin",
                        pattern=r"margin guidance (\d+)% to (\d+)%",
                        horizon="FY27",
                    ),
                )
            ),
        }
    )
    results = tmp_path / f"results-{quarter}.pdf"
    transcript = tmp_path / f"transcript-{quarter}-{lower}.pdf"
    if not results.exists():
        document: Any = pymupdf.open()  # type: ignore[no-untyped-call]
        page = document.new_page()
        page.insert_text(
            (50, 65), "Statement of consolidated unaudited financial results", fontsize=9
        )
        page.insert_text((50, 85), "(Rs. in crore)", fontsize=9)
        page.insert_text((350, 120), end.strftime("%d-%m-%Y"), fontsize=9)
        rows = (
            ("Revenue from operations", "39315"),
            ("Total income", "40153"),
            ("Total expenses", "31132"),
            ("Profit before tax", "9021"),
            ("Profit for the period", "6374"),
            ("Profit attributable to owners", "6368"),
            ("Non-controlling interests", "6"),
            ("Basic", "15.38"),
        )
        for index, (label, value) in enumerate(rows):
            y = 155 + 25 * index
            page.insert_text((50, y), label, fontsize=9)
            page.insert_text((350, y), value, fontsize=9)
        document.save(str(results))
        document.close()
    if not transcript.exists():
        document = pymupdf.open()  # type: ignore[no-untyped-call]
        document.new_page().insert_text(
            (50, 80), f"We expect margin guidance {lower}% to 12% for FY27.", fontsize=9
        )
        document.save(str(transcript))
        document.close()
    xml = (
        (root / "tests" / "fundamentals" / "fixtures" / "synthetic_q1_fy25_consolidated.xml")
        .read_text()
        .replace("INFY", "SYNTH")
        .replace("2024-04-01", str(start))
        .replace("2024-06-30", str(end))
        .encode()
    )
    return run_synthetic_pipeline(
        config=config,
        xbrl_input=XbrlInput(
            xml_bytes=xml,
            file_sha256=hashlib.sha256(xml).hexdigest(),
            source_id="synthetic-xbrl",
            retrieved_at=config.quarter.knowledge_cutoff,
        ),
        results_pdf_path=str(results),
        results_pdf_sha256=hashlib.sha256(results.read_bytes()).hexdigest(),
        transcript_pdf_path=str(transcript),
        transcript_pdf_sha256=hashlib.sha256(transcript.read_bytes()).hexdigest(),
        store=store,
    )


def test_pipeline_replays_quarter_without_changing_status_or_latest_authority(
    tmp_path: Path,
) -> None:
    """The pipeline must use the requested quarter rather than the latest pointer."""
    with closing(FactStore(":memory:")) as store:
        first = _synthetic_pipeline_run(tmp_path, "FY27_Q1", "10", store)
        repeated = _synthetic_pipeline_run(tmp_path, "FY27_Q1", "10", store)
        assert repeated.update.ledger == first.update.ledger
        assert repeated.markdown == first.markdown
        second = _synthetic_pipeline_run(tmp_path, "FY27_Q2", "11", store)
        assert second.update.ledger is not None
        assert second.update.ledger.entries[0].status is LedgerStatus.MODIFIED
        current_bytes = (tmp_path / "ledger.json").read_bytes()
        historical = _synthetic_pipeline_run(tmp_path, "FY27_Q1", "10", store)
        assert historical.update.ledger == first.update.ledger
        assert (tmp_path / "ledger.json").read_bytes() == current_bytes
        assert load_ledger(tmp_path / "ledger.json") == second.update.ledger
        with pytest.raises(ValueError, match="conflicting same-quarter"):
            _synthetic_pipeline_run(tmp_path, "FY27_Q1", "11", store)
        assert load_ledger(tmp_path / "ledger.json") == second.update.ledger


def test_stale_forward_save_refuses_before_publication(tmp_path: Path) -> None:
    """A later quarter cannot discard a predecessor committed after it was built."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    save_ledger(first, path)
    second = reconcile_ledger(
        first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
    )
    stale = reconcile_ledger(first, symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[])
    save_ledger(second, path)
    before = {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")}
    with pytest.raises(ValueError, match="stale.*predecessor"):
        save_ledger(stale, path)
    assert {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")} == before
    assert not (tmp_path / "ledger.quarters" / "FY27_Q3.json").exists()
    assert load_ledger(path) == second
    correct = reconcile_ledger(
        load_ledger(path), symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[]
    )
    save_ledger(correct, path)
    assert load_ledger(path) == correct
    assert correct.entries[0].lower_bound == Decimal("11")
    assert correct.version == 3


def test_forward_save_allows_skipped_quarter_from_actual_current(tmp_path: Path) -> None:
    """Predecessor identity matters; quarterly cadence is not a persistence rule."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    save_ledger(first, path)
    later = reconcile_ledger(load_ledger(path), symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[])
    save_ledger(later, path)
    assert load_ledger(path) == later


def test_concurrent_forward_writer_rejects_changed_predecessor(tmp_path: Path) -> None:
    """A paused writer revalidates after another writer advances authority."""
    path = tmp_path / "ledger.json"
    first = reconcile_ledger(None, symbol="SYNTH", issuer_quarter="FY27_Q1", claims=[claim("Q1")])
    save_ledger(first, path)
    built, resume = Event(), Event()

    def stale_writer() -> None:
        stale = reconcile_ledger(
            load_ledger(path), symbol="SYNTH", issuer_quarter="FY27_Q3", claims=[]
        )
        built.set()
        assert resume.wait(timeout=5)
        save_ledger(stale, path)

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(stale_writer)
        try:
            assert built.wait(timeout=5)
            second = reconcile_ledger(
                first, symbol="SYNTH", issuer_quarter="FY27_Q2", claims=[claim("Q2", "11")]
            )
            save_ledger(second, path)
            before = {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")}
        finally:
            resume.set()
        with pytest.raises(ValueError, match="stale.*predecessor"):
            pending.result(timeout=5)
    assert {str(file): file.read_bytes() for file in tmp_path.rglob("*.json")} == before
    assert load_ledger(path) == second
