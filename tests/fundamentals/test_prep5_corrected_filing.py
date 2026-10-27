"""PREP-5 Task 4 (PILOT-11) acceptance, split from ``test_prep5_rework``: a corrected
comparator filing reworks its dependent claims into an approved v(N+1); a correction reaching a
carried claim, or a source outside the cutoff or the package, refuses before any write.
"""

from __future__ import annotations

import io
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import pytest
from evidence_support import Ingest, ingest, policy
from ledger_support import RULING
from pg_evidence_schema_support import runtime, seeded
from pg_support import PgTestDatabase
from prep2b_support import COMPARATOR_KIND, Pilot
from prep5_support import LATE, Q1, _correct, _rerun
from retained_support import manifest_entry
from test_prep2b_run_draft import dictionary, mapping_set
from test_prep5_rework import (
    FACTS,
    PBT,
    QOQ,
    REQUEST,
    WRITES,
    Calls,
    V,
    _counts,
    _lines,
    _plan,
    _request_changes,
    _successor,
    calls,
    submitted_q2,
)

from fundamentals.api import cli
from fundamentals.api.cli import main
from fundamentals.api.pipeline import PipelineResult
from fundamentals.contracts.fact import CanonicalStatus
from fundamentals.contracts.ledger import ClaimState, NumericClaim, VersionStatus
from fundamentals.ledger import lifecycle, rework, run_draft, store
from fundamentals.ledger.run_traces import RunDraftError
from fundamentals.store.pg_fact_store import PgFactStore

__all__ = [
    "calls",
    "dictionary",
    "ingest",
    "mapping_set",
    "policy",
    "runtime",
    "seeded",
    "submitted_q2",
]

pytestmark = [pytest.mark.pg, pytest.mark.retained]


_CAPTURE_BLOB = """SELECT c.blob_sha256 FROM eqos.interpretations i
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s"""
_TRACE_BLOBS = """SELECT DISTINCT c.blob_sha256 FROM eqos.calculation_trace_operands o
JOIN eqos.interpretations i ON i.id = o.interpretation_id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE o.calculation_trace_id = %s"""


def _blob(pilot: Pilot, claim: NumericClaim) -> str:
    """The capture blob of the interpretation a figure cites."""
    ((found,),) = pilot.query(_CAPTURE_BLOB, claim.citation.interpretation_id)
    return str(found)


def _sealed(pilot: Pilot, version: int) -> tuple[VersionStatus, str, str, rework.Rework | None]:
    """The version's status, sealed digest, content hash and rework (package inputs, rerun set)."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        cursor = conn.cursor()
        status = lifecycle.version_status(cursor, version)
        digest = store.sealed_digest(cursor, version)
    return status, digest, pilot.version(version).content_hash, _plan(pilot, version)


def test_corrected_filing_reworks_only_dependent_claims(
    submitted_q2: tuple[Pilot, int],
    ingest: Ingest,
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PILOT-11: a restated QoQ comparator moves only the rejected prior's changes line. v(N+1)
    carries the values recomputed from the new filing; every other claim keeps N's citation,
    the other QoQ priors the old filing's (finding 4); only the two dependent calculations run,
    no fact row, admission or selection is new; v(N+1) is approved and N's package is as it was."""
    pilot, version = submitted_q2
    monkeypatch.setattr("sys.stdin", io.StringIO(RULING))
    command = ["ledger", "decide", V.value, str(version), REQUEST.value, "--claim", QOQ[0]]
    assert main(command) == 0
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert rework.rejected(conn.cursor(), version) == (QOQ[0],)
    baseline = _sealed(pilot, version)
    assert baseline[3] is not None and baseline[3].rerun == set(QOQ)
    sha, rerun = _correct(pilot, ingest)
    facts = _counts(pilot)[:FACTS]
    new = rerun().draft_version_id
    assert new is not None and _successor(pilot, version) == new
    numbers = pilot.query("SELECT eqos.version_number(%s), eqos.version_number(%s)", version, new)
    assert numbers[0][1] == numbers[0][0] + 1
    old = {c.claim_key: c for c in pilot.version(version).claims}
    claims = {c.claim_key: c for c in pilot.version(new).claims}
    current, prior = old["fact.revenue"].value, old[QOQ[0]].value
    assert current is not None and prior is not None
    prior += 100  # a run states amounts in ₹ crore
    pct = ((current - prior) / prior * 100).quantize(Decimal(1).scaleb(-2), ROUND_HALF_EVEN)
    expected = dict(zip(QOQ, (prior, current - prior, pct), strict=True))
    assert {key: claims[key].value for key in QOQ} == expected
    assert all(old[key].value != value for key, value in expected.items())
    assert _blob(pilot, claims[QOQ[0]]) == sha
    for key in QOQ[1:]:
        trace = claims[key].citation.calculation_trace_id
        assert trace != old[key].citation.calculation_trace_id
        assert sha in {row[0] for row in pilot.query(_TRACE_BLOBS, trace)}
    digest = {key: c.measurement_key.digest() for key, c in old.items() if c.measurement_key}
    assert sorted(calls["conclude"]) == sorted(digest[key] for key in QOQ[1:])
    assert len(calls["put_calculation_trace"]) == 2
    assert set(calls["operand"]) == {digest["fact.revenue"], digest[QOQ[0]]}
    assert calls["admit_run"] == [0] and calls["select_admitted"] == []
    assert _counts(pilot)[:FACTS] == facts
    unchanged = {key: c for key, c in claims.items() if key not in QOQ}
    assert unchanged == {key: c for key, c in old.items() if key not in QOQ}
    assert _lines(pilot, new) == _lines(pilot, version)
    original = manifest_entry(Q1, COMPARATOR_KIND)["sha256"]
    priors = [key for key in unchanged if key.endswith(".qoq.prior")]
    assert priors and {_blob(pilot, claims[key]) for key in priors} == {original}
    pilot.approve(new)
    assert _sealed(pilot, new)[0] is VersionStatus.APPROVED
    assert _sealed(pilot, version) == baseline
    assert baseline[0] is VersionStatus.CHANGES_REQUESTED


def test_a_corrected_filing_reaching_a_carried_claim_refuses_before_writing(
    submitted_q2: tuple[Pilot, int], ingest: Ingest, calls: Calls
) -> None:
    """With PBT rejected, the restated comparator moves the carried revenue QoQ line: carrying
    N's value would publish a stale one, taking the new one would bypass review."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, PBT)
    _, rerun = _correct(pilot, ingest)
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=QOQ[0]):
        rerun()
    for name in WRITES:
        assert calls[name] == [], name
    assert _counts(pilot) == before


@pytest.mark.parametrize("case", ["late", "outside", "omitted"])
def test_a_rework_source_outside_its_package_refuses_before_writing(
    submitted_q2: tuple[Pilot, int],
    ingest: Ingest,
    calls: Calls,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """The corrected filing published after the cutoff, a capture outside the run's package,
    and the original filing that carried claims still cite missing from the manifest each
    refuse before the rerun's traces are stored (closing r2 3, r3 1): at the draft write they
    would follow it."""
    pilot, version = submitted_q2
    _request_changes(pilot, version, QOQ[0])
    original = manifest_entry(Q1, COMPARATOR_KIND)["sha256"]
    sha, rerun = _correct(
        pilot, ingest, filed_at=LATE if case == "late" else None, original=case != "omitted"
    )
    if case == "outside":
        check = cli.check_blobs

        def narrowed(*args: Any, allowed: set[str], **kwargs: Any) -> None:
            check(*args, allowed=allowed - {sha}, **kwargs)

        monkeypatch.setattr(cli, "check_blobs", narrowed)
    named = {
        "late": f"past the source cutoff .*{sha[:12]}",
        "outside": f"not in the run's package: {sha[:12]}",
        "omitted": f"past the source cutoff .*{original[:12]}",
    }[case]
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=named):
        rerun()
    for name in WRITES:
        assert calls[name] == [], name
    assert _counts(pilot) == before


def test_a_head_citing_run_written_facts_reworks_only_in_full(
    pg_db: PgTestDatabase, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, ingest: Any
) -> None:
    """A head written before fact admission (its pipeline-written fact rows cited, no pinned
    comparison run) cannot carry those facts: a selective rework refuses naming
    ``--full-successor`` and writes nothing; the full successor cites six admitted facts and
    the old head still validates."""
    pilot = Pilot(pg_db, tmp_path, monkeypatch, ingest)
    results: list[PipelineResult] = []
    with pytest.MonkeyPatch.context() as patch:
        real_pipeline, real_write = cli.run_pipeline, cli.write_run_draft
        real_create = store.create_version

        def pipeline(**kwargs: Any) -> PipelineResult:
            """The pre-admission pipeline: it writes and selects every role's fact."""
            results.append(real_pipeline(**kwargs | {"skip_roles": frozenset()}))
            return results[-1]

        def write(pool: Any, prior: run_draft.Prior, run: run_draft.RunDraft, **kw: Any) -> int:
            """The draft citing the pipeline's canonical rows, as before admission."""
            stored = PgFactStore(pool, pilot.store_id)
            facts = {
                revision.revision_family.split(":")[1]: stored.fact_ref(revision.row_id)
                for revision in results[-1].stored_revisions
                if revision.canonical_status is CanonicalStatus.CANONICAL
            }
            return real_write(pool, prior, run.model_copy(update={"facts": facts}), **kw)

        patch.setattr(cli, "run_pipeline", pipeline)
        patch.setattr(cli, "_admit", lambda *_: {})
        patch.setattr(cli, "write_run_draft", write)
        patch.setattr(
            store,
            "create_version",
            lambda cursor, draft: real_create(
                cursor, draft.model_copy(update={"pinned_run_ids": ()})
            ),
        )
        old = pilot.run("FY26_Q2").draft_version_id
    assert old is not None and pilot.version(old).pinned_run_ids == ()
    with pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, old, **pilot.sources())
    _request_changes(pilot, old, "fact.revenue")
    before = _counts(pilot)
    with pytest.raises(RunDraftError, match=f"version {old} predates fact admission"):
        _rerun(pilot)
    assert _counts(pilot) == before
    new = _rerun(pilot, "--full-successor").draft_version_id
    assert new is not None
    pilot.admitted(new)
    assert {state for _, state in pilot.validate(old).claim_states} == {ClaimState.MATCH}
