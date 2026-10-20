"""PILOT-4 citation route (eqos-4j2.27; owner amendment 2026-10-20, invariant 7).

A QoQ prior cites the predecessor run version's admitted ``fact.<role>`` (its comparison runs
pinned); every other comparator figure and the filed tax total cite their filed interpretation,
labelled ``FILED`` and rendered as single-source. Each route fails closed: no predecessor pin,
a predecessor fact that is not the prior's, a missing or false label, or a late input.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from evidence_support import ingest, policy
from prep2b_support import COUNTS, Pilot
from test_prep2b_run_draft import _head, approved_q2, dictionary, mapping_set, pilot
from test_prep5_rework import QOQ, _plan, _request_changes, calls

import fundamentals.api.cli as cli
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    NumericClaim,
    VersionDraft,
    VersionStatus,
)
from fundamentals.ledger import lifecycle
from fundamentals.ledger.citations import _FIRST_SEEN, resolve_citation
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.display import FILED, FILED_SUFFIX
from fundamentals.ledger.export import export_version
from fundamentals.ledger.run_draft import Prior, RunDraft, preflight, write_run_draft
from fundamentals.ledger.run_traces import RunDraftError

__all__ = ["approved_q2", "calls", "dictionary", "ingest", "mapping_set", "pilot", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

Q2, Q3 = "FY26_Q2", "FY26_Q3"
REVENUE_QOQ, REVENUE_YOY, TAX = "cmp.revenue.qoq.prior", "cmp.revenue.yoy.prior", "calc.2"
# The filed counts the plan derives from the probed citations (Evidence 2): every comparator
# prior and the tax total in PQ0, less the six predecessor-backed QoQ priors in PQ1.
FILED_COUNTS = {Q2: 13, Q3: 7}
TICK = timedelta(microseconds=1)
_SELECTED = """SELECT min(greatest(s.selected_at::timestamptz, s.recorded_at))
FROM eqos.fact_selections s JOIN eqos.fact_rows f
    ON f.target_store = s.target_store AND f.handle = s.row_handle
WHERE f.origin = %s AND f.origin_id = %s"""
_ADMITTED_AT = """SELECT min(overlay_position) FROM eqos.fact_admissions
WHERE fact_origin = %s AND fact_origin_id = %s AND run_id = ANY(%s)"""
_INTERPRETED = """SELECT i.id FROM eqos.interpretations i
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
WHERE i.status = 'MAPPED' AND i.entity_id = %s AND i.key_digest = %s AND c.blob_sha256 = %s
ORDER BY i.id LIMIT 1"""
_CAPTURED = (
    "SELECT " + _FIRST_SEEN + " FROM eqos.interpretations i "
    "JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id = %s"
)


def _claims(version: VersionDraft) -> dict[str, NumericClaim]:
    """A version's claims by key."""
    return {claim.claim_key: claim for claim in version.claims}


def _state(
    pilot: Pilot, version: VersionDraft, claim: NumericClaim, cutoff: datetime | None = None
) -> ClaimState:
    """A figure claim's ``AS_KNOWN`` state under the version's pins, at its cutoff by
    default."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        resolved = resolve_citation(
            conn.cursor(),
            claim,
            entity_id=pilot.entity_id,
            overlay_position=datetime.now(UTC),
            run_ids=version.pinned_run_ids,
            **pilot.sources(),
        )
    at = version.knowledge_cutoff if cutoff is None else cutoff
    return check_claim(claim, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False)


def _q3(pilot: Pilot) -> tuple[VersionDraft, int, VersionDraft]:
    """FY26_Q2's approved version, then FY26_Q3's run draft on it: its id and content."""
    version_id = pilot.run(Q3).draft_version_id
    assert version_id is not None
    return pilot.version(_head(pilot, Q2)), version_id, pilot.version(version_id)


def _cites_predecessor(claim: NumericClaim, predecessor: VersionDraft) -> bool:
    """Whether a QoQ prior cites the predecessor's fact of its role, unlabelled."""
    role = claim.claim_key.split(".")[1]
    fact = _claims(predecessor)[f"fact.{role}"].citation
    cited = claim.citation
    return (
        cited.kind is CitationKind.FIGURE
        and (cited.fact_origin, cited.fact_origin_id) == (fact.fact_origin, fact.fact_origin_id)
        and cited.interpretation_id is None
        and claim.qualifiers == ()
    )


def _rows(pilot: Pilot) -> tuple[Any, ...]:
    """Rows of every table a run writes, and of reports."""
    return (*pilot.query(COUNTS)[0], *pilot.query("SELECT count(*) FROM eqos.reports")[0])


def test_qoq_priors_cite_the_predecessor_and_filed_values_are_labelled(
    approved_q2: Pilot,
) -> None:
    """FY26_Q3's QoQ priors cite FY26_Q2's admitted facts, whose runs it pins, and resolve
    ``MATCH``; the filed values (13 in FY26_Q2, 7 in FY26_Q3) are only comparator priors and the
    tax total, resolve ``MATCH`` and render the single-source suffix; both approve."""
    pilot = approved_q2
    q2, q3_id, q3 = _q3(pilot)
    qoq = [claim for key, claim in _claims(q3).items() if key.endswith(".qoq.prior")]
    assert len(qoq) == 6 and all(_cites_predecessor(claim, q2) for claim in qoq)
    assert set(q2.pinned_run_ids) < set(q3.pinned_run_ids)
    for quarter, version, version_id in ((Q2, q2, _head(pilot, Q2)), (Q3, q3, q3_id)):
        claims = _claims(version)
        filed = {key for key, claim in claims.items() if FILED in claim.qualifiers}
        priors = {key for key in claims if key.startswith("cmp.") and key.endswith(".prior")}
        assert filed == (priors | {TAX}) - {claim.claim_key for claim in qoq if version is q3}
        assert len(filed) == FILED_COUNTS[quarter]
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
            exported = export_version(conn.cursor(), version_id).decode()
        assert exported.count(FILED_SUFFIX) == len(filed)
    assert set(dict(pilot.validate(q3_id).claim_states).values()) == {ClaimState.MATCH}
    pilot.approve(q3_id)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert lifecycle.version_status(conn.cursor(), q3_id) is VersionStatus.APPROVED


def test_a_qoq_rework_carries_the_predecessor_citations(approved_q2: Pilot, calls: Any) -> None:
    """Rejecting FY26_Q3's revenue QoQ prior reruns that line alone (its two traces), carries the
    other five QoQ priors with their predecessor citations and ``MATCH``, and the successor,
    whose rerun prior again cites FY26_Q2's fact, approves."""
    pilot = approved_q2
    q2, q3_id, q3 = _q3(pilot)
    with pilot.pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, q3_id, **pilot.sources())
    _request_changes(pilot, q3_id, REVENUE_QOQ)
    found = _plan(pilot, q3_id)
    assert found is not None and found.rerun == set(QOQ)
    calls.clear()
    new_id = pilot.run(Q3).draft_version_id
    assert new_id is not None
    successor, before = pilot.version(new_id), _claims(q3)
    digests = {before[key].measurement_key.digest() for key in QOQ[1:]}  # type: ignore[union-attr]
    assert set(calls["conclude"]) == digests and len(calls["conclude"]) == len(digests)
    after = _claims(successor)
    assert all(after[key] == before[key] for key in found.carried)
    qoq = [claim for key, claim in after.items() if key.endswith(".qoq.prior")]
    assert len(qoq) == 6 and all(_cites_predecessor(claim, q2) for claim in qoq)
    assert set(dict(pilot.validate(new_id).claim_states).values()) == {ClaimState.MATCH}
    pilot.approve(new_id)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert lifecycle.version_status(conn.cursor(), new_id) is VersionStatus.APPROVED


def test_without_the_predecessor_pins_qoq_priors_do_not_resolve(
    approved_q2: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A draft pinning only its own comparison run leaves exactly the six predecessor-backed
    QoQ priors ``UNRESOLVED``: its in-transaction check refuses it and no version is written."""

    def unpinned(pool: Any, prior: Prior, run: RunDraft, **kwargs: Any) -> int:
        return write_run_draft(pool, prior.model_copy(update={"pinned_run_ids": ()}), run, **kwargs)

    monkeypatch.setattr(cli, "write_run_draft", unpinned)
    pilot = approved_q2
    pilot.registered(Q3)
    before = _rows(pilot)[-3:]  # versions, claims, reports
    with pytest.raises(RunDraftError, match="does not validate AS_KNOWN") as refused:
        pilot.run(Q3)
    failed = str(refused.value).split(": ", 1)[1].split(", ")
    expected = [f"cmp.{role}.qoq.prior: UNRESOLVED" for role in _roles(pilot)]
    assert sorted(failed) == sorted(expected)
    assert _rows(pilot)[-3:] == before


def _roles(pilot: Pilot) -> list[str]:
    """The roles of FY26_Q2's approved facts."""
    keys = _claims(pilot.version(_head(pilot, Q2)))
    return [key.removeprefix("fact.") for key in keys if key.startswith("fact.")]


def _other_fact(field: str) -> Callable[[NumericClaim, NumericClaim], NumericClaim]:
    """The revenue fact with another fact's key or value."""

    def edit(revenue: NumericClaim, other: NumericClaim) -> NumericClaim:
        name = "measurement_key" if field == "key" else "value"
        return revenue.model_copy(update={name: getattr(other, name)})

    return edit


@pytest.mark.parametrize("field", ["key", "value"])
def test_a_predecessor_fact_that_is_not_the_prior_refuses_before_any_write(
    approved_q2: Pilot, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """The prior head's revenue fact under another fact's key or value refuses the public run
    before any trace, operand, fact row, admission, selection, report, version or claim is
    written (baseline after source registration and the comparison run)."""
    edit = _other_fact(field)

    def mismatched(*args: Any, **kwargs: Any) -> Prior:
        prior = preflight(*args, **kwargs)
        facts = {claim.claim_key: claim for claim in prior.facts}
        facts["fact.revenue"] = edit(facts["fact.revenue"], facts["fact.total_income"])
        return prior.model_copy(update={"facts": tuple(facts.values())})

    monkeypatch.setattr(cli, "preflight", mismatched)
    pilot = approved_q2
    pilot.registered(Q3)
    before = _rows(pilot)
    with pytest.raises(RunDraftError, match=f"{REVENUE_QOQ} is not version"):
        pilot.run(Q3)
    assert _rows(pilot) == before


def test_a_missing_or_false_filed_label_is_unresolved(approved_q2: Pilot) -> None:
    """``FILED`` stripped from a filed comparator prior or tax total, or set on a fact or a
    predecessor-backed QoQ prior, is ``UNRESOLVED``; each as stored is ``MATCH``."""
    pilot = approved_q2
    _, _, q3 = _q3(pilot)
    claims = _claims(q3)
    for key in (REVENUE_YOY, TAX, "fact.revenue", REVENUE_QOQ):
        claim = claims[key]
        labels = set(claim.qualifiers) ^ {FILED}
        mislabelled = claim.model_copy(update={"qualifiers": tuple(sorted(labels))})
        assert _state(pilot, q3, claim) is ClaimState.MATCH, key
        assert _state(pilot, q3, mislabelled) is ClaimState.UNRESOLVED, key


def test_a_current_period_fact_cannot_swap_its_admission_for_a_filed_value(
    approved_q2: Pilot,
) -> None:
    """``FILED`` is only for comparator priors and the filed tax total: a current-period
    ``fact.revenue`` citing its own mapped interpretation, labelled ``FILED``, is
    ``UNRESOLVED`` (invariant 7) even though key, value and source agree."""
    pilot = approved_q2
    _, _, q3 = _q3(pilot)
    fact = _claims(q3)["fact.revenue"]
    assert fact.measurement_key is not None
    ((interpretation_id,),) = pilot.query(
        _INTERPRETED,
        pilot.entity_id,
        fact.measurement_key.digest(),
        fact.citation.source_sha256,
    )
    citation = fact.citation.model_copy(
        update={"fact_origin": None, "fact_origin_id": None, "interpretation_id": interpretation_id}
    )
    filed = fact.model_copy(update={"citation": citation, "qualifiers": (FILED,)})
    assert _state(pilot, q3, filed) is ClaimState.UNRESOLVED


def test_late_predecessor_inputs_and_filed_captures_are_post_cutoff(approved_q2: Pilot) -> None:
    """A cutoff before the cited predecessor fact's selection or admission, or before the filed
    value's capture was first seen, makes the claim ``POST_CUTOFF``."""
    pilot = approved_q2
    _, _, q3 = _q3(pilot)
    qoq, filed = _claims(q3)[REVENUE_QOQ], _claims(q3)[REVENUE_YOY]
    fact = (qoq.citation.fact_origin, qoq.citation.fact_origin_id)
    ((selected,),) = pilot.query(_SELECTED, *fact)
    ((admitted,),) = pilot.query(_ADMITTED_AT, *fact, list(q3.pinned_run_ids))
    ((captured,),) = pilot.query(_CAPTURED, filed.citation.interpretation_id)
    for claim, at in ((qoq, selected), (qoq, admitted), (filed, captured)):
        assert at is not None and at <= q3.knowledge_cutoff
        assert _state(pilot, q3, claim, at - TICK) is ClaimState.POST_CUTOFF, claim.claim_key
