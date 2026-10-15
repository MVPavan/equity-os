"""D1b fresh critical review C1, C3–C6, C8: each finding's failure, reproduced on retained runs."""

from __future__ import annotations

import itertools
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import psycopg
import pytest
import stage1_e2e_support
from stage1_e2e_support import FY25_XBRL, SCREENER, Outcome, Stage, full_run, fy25, mark
from test_data_stage1_e2e import stage

from fundamentals.compare import run_config
from fundamentals.compare.queue import overlay_boundary, read_overlay
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.comparison import PairKind, SourceRole, SourceState
from fundamentals.contracts.evidence import RevisionCause
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.pg.settings import PgRole

__all__ = ["stage"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]
SCR = "/".join(SCREENER)
LAURUS = pytest.mark.parametrize("stage", ["LAURUSLABS-Q3FY25"], indirect=True)


@LAURUS
def test_partial_section_is_not_hidden_by_a_later_complete_one(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: Screener's quarters section is read PARTIAL, later sections of the same capture
    COMPLETE. The capture is not complete: its sides are UNAVAILABLE and the run INCOMPLETE."""
    screener = stage1_e2e_support.screener

    def partial_quarters(entity: str, basis: Any, section: Section) -> Any:
        adapter = screener(entity, basis, section)
        if section is not Section.QUARTERS:
            return adapter
        return lambda *args, **kwargs: adapter(*args, **kwargs).model_copy(
            update={"outcome": ExtractionOutcome.PARTIAL, "reasons": ("test-only quarantine",)}
        )

    monkeypatch.setattr(stage1_e2e_support, "screener", partial_quarters)
    stage.first_party()
    stage.vendor(SCR, "LAURUSLABS-SCR")
    outcome = Outcome(stage, vendors=[SCR])
    for key in ("revenue_from_operations|Q|-|REPORTED", "eps_basic|Q|-|REPORTED"):
        (vendor,) = [v for v in outcome.row(key).source_values if v.source_id == SCREENER[0]]
        assert (vendor.state, vendor.reason) == (SourceState.UNAVAILABLE, "PARTIAL"), key
    assert outcome.status == "INCOMPLETE"


@LAURUS
def test_formula_operand_qualification_is_reproven(stage: Stage) -> None:
    """C3: correcting the discontinued profit to nonzero withdraws the continuing PAT's
    qualification from the formula operand too, not only from the displayed reported side."""
    before = full_run(stage)
    pat_key = "profit_continuing_after_tax|Q|-|REPORTED"
    pat = before.interpretation(pat_key, "xbrl")
    assert pat.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    (zero,) = stage.repository.get_interpretations(
        pat.condition_evidence[0].evidence_interpretation_ids
    )
    mark(
        stage,
        zero,
        "c3-condition-nonzero",
        revision_cause=RevisionCause.MANUAL_CORRECTION,
        supersedes_interpretation_id=zero.interpretation_id,
        value=Decimal(500000000),
        interval=Interval(lower=Fraction(495000000), upper=Fraction(505000000)),
    )
    after = Outcome(stage)
    assert after.row(pat_key).pairs[0].outcome.value == "AGREE_UNQUALIFIED"
    margin = after.row("net_profit_margin_pct|Q|-|DERIVED")
    (xbrl,) = [v for v in margin.source_values if stage1_e2e_support._name(v) == "xbrl"]
    assert xbrl.calculation_trace_id is not None
    (trace,) = stage.repository.get_calculation_traces([xbrl.calculation_trace_id])
    (operand,) = [o for o in trace.trace.operands if o.name == "net_profit"]
    assert (operand.scoped_tier, operand.qualification_ref) == (
        EvidenceTier.EQUIVALENCE_UNPROVEN,
        None,
    )


@LAURUS
def test_changed_vendor_extractor_under_its_version_is_refused(
    stage: Stage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C4: the Tijori adapter's bytes change under ``tijori-v4``: both a new ingest and a new
    run refuse the drift before any stored interpretation is reused."""
    full_run(stage)
    root = tmp_path / "fundamentals"
    shutil.copytree(run_config._SOURCE_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    with (root / "evidence" / "vendor_tijori.py").open("a") as source:
        source.write("\n# Test-only unbumped extractor content change.\n")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", root)
    with pytest.raises(VersionContentDriftError, match="vendor_extractor:tijori"):
        stage.vendor("tijori/financials", "LAURUSLABS-TIJ")
    with pytest.raises(VersionContentDriftError, match="vendor_extractor:tijori"):
        stage.execute()


@pytest.mark.parametrize("stage", ["APARINDS-Q2FY26"], indirect=True)
def test_derived_q4_compares_vendors(stage: Stage) -> None:
    """C6: Apar FY25 Q4 revenue derived FY - 9M (5,209.76) is compared with Screener's 5,210
    exactly as the reported Q4 is, and still pairs with the reported Q4."""
    fy25(stage, [SCR])
    stage.first_party(quarter="FY25_Q3", members=FY25_XBRL, end=date(2024, 12, 31))
    stage.first_party(quarter="FY25_Q4", members=FY25_XBRL)
    stage.vendor(SCR, "A-SCR", end=stage.end)
    outcome = Outcome(stage)
    reported = outcome.row("revenue_from_operations|Q|-|REPORTED")
    derived = outcome.row("revenue_from_operations|Q|-|DERIVED")
    vendor = [v for v in derived.source_values if v.source_role is SourceRole.INDEPENDENT_VENDOR]
    assert vendor == [
        v for v in reported.source_values if v.source_role is SourceRole.INDEPENDENT_VENDOR
    ]
    assert vendor[0].value == Decimal("52100000000")
    kinds = {pair.pair_kind for pair in derived.pairs}
    assert {PairKind.CORROBORATION, PairKind.REPORTED_VS_DERIVED} <= kinds
    assert derived.corroboration_status == reported.corroboration_status


@LAURUS
def test_identical_concurrent_ingests_both_reuse_one_generation(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C8: two identical Tijori ingests interpret the same capture concurrently; the loser
    re-reads and reuses the winner's rows instead of failing."""
    stage.first_party()
    read = EvidenceRepository.list_capture_interpretations
    barrier, calls = threading.Barrier(2), itertools.count()

    def racing_read(repository: EvidenceRepository, capture: int) -> Any:
        rows = read(repository, capture)
        if next(calls) < 2:  # both first reads see nothing before either writes
            barrier.wait(timeout=20)
        return rows

    monkeypatch.setattr(EvidenceRepository, "list_capture_interpretations", racing_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(stage.vendor, "tijori/financials", "LAURUSLABS-TIJ") for _ in range(2)
        ]
        reports = [future.result(timeout=60) for future in futures]
    first, second = (sorted(i.interpretation_id or 0 for i in r.interpretations) for r in reports)
    assert first == second and first


@LAURUS
def test_queue_writes_serialize_at_the_database(stage: Stage) -> None:
    """C5: an owner-role disposition inserted by plain SQL holds the queue lock until commit,
    so a boundary taken meanwhile waits and then sees it; a transaction that read the store
    clock first cannot write the queue at all."""
    outcome = full_run(stage)
    item = next(i for i in outcome.items if not i.diagnostic)
    insert = (
        "INSERT INTO eqos.queue_dispositions (item_id,kind,reason,decider,evidence_ref) "
        "VALUES (%s,'DISMISSED','c5','test','test-only')"
    )
    conninfo = stage.pg_db.conninfo(PgRole.OWNER)
    with psycopg.connect(conninfo) as writer:
        writer.execute("SELECT eqos.store_now()")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            writer.execute(insert, (item.item_id,))
        writer.rollback()
        writer.execute(insert, (item.item_id,))
        boundary: list[Any] = []
        waiting = threading.Thread(target=lambda: boundary.append(overlay_boundary(stage.pool)))
        waiting.start()
        waiting.join(timeout=2)
        assert waiting.is_alive() and not boundary
        writer.commit()
    waiting.join(timeout=20)
    overlay = read_overlay(stage.pool, run_id=outcome.record.run_id, as_of=boundary[0])
    assert item.item_id not in {i.item_id for i in overlay.open_items}
