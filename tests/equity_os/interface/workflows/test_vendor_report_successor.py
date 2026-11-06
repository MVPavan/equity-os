"""VENDOR-1 phase-review finding 3: a vendor-valued fact carried by an ordinary rework, then
approved and read as the next quarter's QoQ prior, end to end through ``main``.

Apar FY26_Q2's revenue is admitted from the vendors (row 1 of ``vendor_report_support``). A
rework that reruns only the revenue YoY line carries that revenue, without ``--full-successor``,
and computes the rerun line from it. Once the rework is approved, FY26_Q3's revenue QoQ prior is
the approved vendor-valued fact, not the filed comparator, and its changes are computed from the
fact's interpretation. Values are read back from the run; none is written here.
"""

from __future__ import annotations

import pytest
from evidence_support import ingest, policy
from prep2b_support import RULING, Pilot
from test_prep2b_run_draft import dictionary, mapping_set
from vendor_report_support import compare, report, vendor_pilot

from equity_os.contracts.measurement.role import FactRole
from equity_os.contracts.publication.ledger import DecisionKind, NumericClaim, SubjectKind
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.publication.approval import lifecycle
from equity_os.publication.checking.claim_check import ClaimState
from equity_os.publication.drafting.run_draft import RUN_AUTHOR

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

VENDOR = (
    "SELECT interpretation_id FROM eqos.fact_admissions "
    "WHERE run_id = %s AND witness_interpretation_id IS NOT NULL"
)
OPERANDS = (
    "SELECT interpretation_id FROM eqos.calculation_trace_operands WHERE calculation_trace_id = %s"
)
LATEST = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
REVENUE, YOY, QOQ = "fact.revenue", "cmp.revenue.yoy", "cmp.revenue.qoq"
CHECKED = AdmissionLabel.CHECKED_AGAINST_FILING.value


def _latest(pilot: Pilot) -> int:
    """The latest run draft's id."""
    ((version_id,),) = pilot.query(LATEST, RUN_AUTHOR)
    return int(version_id)


def _claims(pilot: Pilot, version_id: int) -> dict[str, NumericClaim]:
    """A version's claims by key."""
    return {claim.claim_key: claim for claim in pilot.version(version_id).claims}


def _operands(pilot: Pilot, claim: NumericClaim) -> set[int]:
    """The interpretations a computed claim's trace reads."""
    trace = claim.citation.calculation_trace_id
    assert trace is not None, claim.claim_key
    return {row[0] for row in pilot.query(OPERANDS, trace)}


def _matched(pilot: Pilot, version_id: int) -> bool:
    """Whether every claim of the version matches on a runtime check."""
    return set(dict(pilot.validate(version_id).claim_states).values()) == {ClaimState.MATCH}


def test_vendor_fact_carries_through_rework_and_into_next_quarter(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) an ordinary rework of a draft with a vendor-valued revenue carries it and computes
    the rerun line from it; (a) approved, it is the next quarter's revenue QoQ prior, with its
    label, and the QoQ changes are computed from its interpretation; both drafts validate."""
    pilot = vendor_pilot(request, monkeypatch)
    run_id = compare(pilot)
    assert report(pilot, run_id) == 0
    head = _latest(pilot)
    ((vendor,),) = pilot.query(VENDOR, run_id)
    fact = _claims(pilot, head)[REVENUE]
    with pilot.pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, head, **pilot.sources())
    with pilot.pg_db.owner_pool() as owner:
        lifecycle.decide(
            owner,
            subject_kind=SubjectKind.REPORT_VERSION,
            subject_id=head,
            kind=DecisionKind.REQUEST_CHANGES,
            ruling=RULING,
            claims=(f"{YOY}.prior",),
        )

    assert report(pilot, run_id) == 0  # (b) no --full-successor
    reworked = _latest(pilot)
    assert reworked != head
    claims = _claims(pilot, reworked)
    assert claims[REVENUE] == fact
    assert vendor in _operands(pilot, claims[f"{YOY}.abs"])
    assert _matched(pilot, reworked)
    pilot.approve(reworked)

    result = pilot.run("FY26_Q3")  # (a) the next quarter
    assert result.draft_version_id is not None
    claims = _claims(pilot, result.draft_version_id)
    prior = claims[f"{QOQ}.prior"]
    assert prior.value == fact.value and CHECKED in prior.qualifiers
    assert prior.citation.fact_origin_id == fact.citation.fact_origin_id
    (concept,) = [f.concept_qname for f in result.update.facts if f.role is FactRole.REVENUE]
    (filed,) = [c.qoq.prior_value for c in result.update.comparatives if c.concept_qname == concept]
    assert filed != prior.value  # the filed comparator differs: the vendor value is used
    assert vendor in _operands(pilot, claims[f"{QOQ}.abs"]) & _operands(pilot, claims[f"{QOQ}.pct"])
    assert _matched(pilot, result.draft_version_id)
