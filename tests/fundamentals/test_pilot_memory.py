"""PILOT-GAP memory Task 2 (eqos-4j2.25, PILOT-5): each pilot quarter's run retrieves the
stock's promoted memory at a store-clock boundary taken before its pipeline and seals the line
in its draft heading; later events are excluded, a replay at the boundary reproduces it, and
nothing the pilot created is visible at a run's own source cutoff.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from evidence_support import ingest, policy
from prep2b_support import RULING, Pilot
from test_prep2b_run_draft import dictionary, mapping_set, pilot

import fundamentals.api.cli as cli
from fundamentals.api.cli import main
from fundamentals.api.pipeline import PipelineResult
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import DecisionKind
from fundamentals.contracts.memory import MemoryItemDraft, MemoryKind, SupportDraft, SupportTarget
from fundamentals.ledger.run_draft import recall
from fundamentals.memory.pg_store import PgMemoryStore

__all__ = ["dictionary", "ingest", "mapping_set", "pilot", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

LINE = re.compile(r"^Memory retrieved at store time (\S+): .*$", re.MULTILINE)
_CREATED = "SELECT created_at FROM eqos.report_versions WHERE id = %s"
_PROMOTED = (
    "SELECT recorded_at FROM eqos.decisions WHERE subject_kind = 'MEMORY_ITEM' "
    "AND subject_id = %s AND kind = 'PROMOTE'"
)
_FACT_CLAIM = (
    "SELECT min(id) FROM eqos.numeric_claims WHERE version_id = %s AND claim_key LIKE 'fact.%%'"
)


def _line(pilot: Pilot, result: PipelineResult) -> tuple[str, datetime]:
    """The run's sealed memory line and its boundary."""
    assert result.draft_version_id is not None
    match = LINE.search(pilot.version(result.draft_version_id).sections[0].body)
    assert match is not None
    return match.group(0), datetime.fromisoformat(match.group(1))


def _item(pilot: Pilot, claim_id: int, statement: str) -> MemoryItemDraft:
    """A company-understanding item supported by one pilot claim."""
    return MemoryItemDraft(
        entity_id=pilot.entity_id,
        kind=MemoryKind.COMPANY_UNDERSTANDING,
        statement=statement,
        epistemic_class=EpistemicClass.OBSERVED,
        valid_from=date(2025, 12, 31),
        valid_to=None,
        supersedes_item_id=None,
        supports=(SupportDraft(target=SupportTarget.CLAIM, target_id=claim_id),),
    )


def _promote(pilot: Pilot, item_id: int) -> None:
    """The owner's PROMOTE of a staged item."""
    with pilot.pg_db.owner_pool() as owner:
        PgMemoryStore(owner).decide(item_id, DecisionKind.PROMOTE, ruling=RULING)


def _stage_cli(path: Path, capsys: pytest.CaptureFixture[str]) -> int:
    """``ledger stage <path>``; returns the printed item id."""
    assert main(["ledger", "stage", str(path)]) == 0
    printed = capsys.readouterr().out.strip()
    assert printed.startswith("memory item ")
    return int(printed.removeprefix("memory item "))


def test_sequential_quarters_retrieve_memory_at_their_boundaries(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bootstrap and PQ1 retrieve nothing; A, staged by CLI (a retry prints the same id) and
    promoted after PQ1, is in PQ2's line unflagged; after a RETROSPECTIVE validation of PQ1
    fails A's support, PQ3's line flags A (an invalidation integration test, not contradiction
    evidence: eqos-4j2.8) and omits B, promoted after PQ3's recall and before its draft."""
    results: dict[str, PipelineResult] = {}
    for quarter in ("FY26_Q2", "FY26_Q3"):
        results[quarter] = pilot.run(quarter)
        assert _line(pilot, results[quarter])[0].endswith(": none.")
        pilot.approve(results[quarter].draft_version_id)  # type: ignore[arg-type]
    pq1 = results["FY26_Q3"].draft_version_id
    ((claim_a,),) = pilot.query(_FACT_CLAIM, pq1)
    path = pilot.tmp_path / "item_a.yaml"
    item_a = _item(pilot, claim_a, "PQ1's reported figures check MATCH")
    path.write_text(yaml.safe_dump(item_a.model_dump(mode="json")), encoding="utf-8")
    a = _stage_cli(path, capsys)
    assert _stage_cli(path, capsys) == a
    _promote(pilot, a)

    results["FY26_Q4"] = pilot.run("FY26_Q4")
    line, _ = _line(pilot, results["FY26_Q4"])
    assert f"memory:{a} (needs revalidation: no; supports claim:{claim_a})" in line
    pilot.approve(results["FY26_Q4"].draft_version_id)  # type: ignore[arg-type]

    assert pilot.validate(pq1, RunMode.RETROSPECTIVE).mode is RunMode.RETROSPECTIVE  # type: ignore[arg-type]
    ((claim_b,),) = pilot.query(_FACT_CLAIM, results["FY26_Q4"].draft_version_id)
    with pilot.pg_db.runtime_pool() as runtime:
        b = PgMemoryStore(runtime).stage(_item(pilot, claim_b, "PQ2's figures check MATCH"))
    run_pipeline = cli.run_pipeline

    def promote_first(*args: Any, **kwargs: Any) -> Any:
        _promote(pilot, b)
        return run_pipeline(*args, **kwargs)

    monkeypatch.setattr(cli, "run_pipeline", promote_first)
    results["FY27_Q1"] = pilot.run("FY27_Q1")
    line, _ = _line(pilot, results["FY27_Q1"])
    assert f"memory:{a} (needs revalidation: yes; supports claim:{claim_a})" in line
    assert f"memory:{b} " not in line

    boundaries = [_line(pilot, result)[1] for result in results.values()]
    created = [pilot.query(_CREATED, r.draft_version_id)[0][0] for r in results.values()]
    for at, made, following in zip(boundaries, created, boundaries[1:] + [None], strict=True):
        assert at < made and (following is None or made < following)
    ((b_promoted,),) = pilot.query(_PROMOTED, b)
    assert boundaries[-1] < b_promoted < created[-1]

    with pilot.pg_db.runtime_pool() as runtime:
        for quarter in ("FY26_Q4", "FY27_Q1"):
            line, at = _line(pilot, results[quarter])
            assert recall(runtime, pilot.entity_id, at=at) == line
        assert f"memory:{b} " in recall(runtime, pilot.entity_id)
        memory = PgMemoryStore(runtime)
        cutoffs = {q: results[q].update.source_cutoff for q in ("FY26_Q3", "FY26_Q4", "FY27_Q1")}
        for at in cutoffs.values():
            assert memory.retrieve("", stock=pilot.entity_id, cutoff=at) == (), cutoffs
