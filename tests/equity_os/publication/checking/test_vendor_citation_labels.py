"""VENDOR-1 P1 phase-review findings 1, 2 and 6: a claim states exactly its citation's admission
label; the latest pinned admission at the cutoff authorises a value; a calculation is known no
earlier than both witnesses of its vendor operands.

The world is ``vendor_report_support``'s withheld Apar FY26_Q2 (all six roles row 3, drafted
unchecked). A second comparison run after the filing arrives admits the same vendor values
checked.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from evidence_support import CONFIG, XBRL_KIND, ingest, policy
from prep2b_support import Pilot
from psycopg.rows import dict_row
from vendor_report_support import ELIGIBILITY, END, QUARTER, compare, report, vendor_pilot

from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.publication.ledger import (
    CitationKind,
    ClaimState,
    InputTime,
    NumericClaim,
    ResolvedCitation,
)
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import MappingSet, load_mapping_set
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.citations import resolve_citation
from equity_os.publication.checking.claim_check import check_claim
from equity_os.publication.drafting.display import DisplayError, content_hash
from equity_os.publication.drafting.run_draft import RUN_AUTHOR
from equity_os.storage.records import store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import admit_run
from equity_os.verification.admission.eligibility import record_counterexample

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CHECKED = AdmissionLabel.CHECKED_AGAINST_FILING
UNCHECKED = AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
REVENUE = "fact.revenue"
VERSION = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
# The revenue fact's admissions, earliest first: run, label, class and result.
ADMISSIONS = """SELECT a.run_id, a.label, a.class_digest, a.result_id
FROM eqos.numeric_claims k JOIN eqos.fact_admissions a USING (fact_origin, fact_origin_id)
WHERE k.version_id = %s AND k.claim_key = %s ORDER BY a.overlay_position, a.id"""
# The registration times of the witness captures of the admissions a trace's operands reach.
REGISTERED = """SELECT DISTINCT c.registered_at FROM eqos.calculation_trace_operands o
JOIN eqos.fact_admissions a ON a.interpretation_id = o.interpretation_id
JOIN eqos.interpretations i ON i.id IN (a.interpretation_id, a.witness_interpretation_id)
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
WHERE o.calculation_trace_id = %s AND a.run_id = %s ORDER BY 1"""


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v9, the pilot comparison pin."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v9", dictionary=dictionary)


@pytest.fixture
def drafted(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> tuple[Pilot, int, int]:
    """The withheld world's run draft, not yet approved: the pilot, its run and version."""
    pilot = vendor_pilot(request, monkeypatch, withheld=True)
    run_id = compare(pilot, ELIGIBILITY)
    pilot.evidence_ingest(QUARTER, XBRL_KIND, END)
    assert report(pilot, run_id) == 0
    ((version_id,),) = pilot.query(VERSION, RUN_AUTHOR)
    return pilot, run_id, version_id


@pytest.mark.parametrize("stated", [(), (CHECKED,), (UNCHECKED, CHECKED)])
def test_a_revenue_claim_without_its_exact_label_fails_validation_and_approval(
    drafted: tuple[Pilot, int, int], stated: tuple[AdmissionLabel, ...]
) -> None:
    """Finding 1: the drafted revenue claim's label omitted, upgraded to checked or doubled makes
    an otherwise identical successor unresolvable, so it cannot be approved; the drafted version
    itself matches and approves. A doubled label does not even render."""
    pilot, _, version_id = drafted
    draft = pilot.version(version_id)
    assert dict(pilot.validate(version_id).claim_states)[REVENUE] is ClaimState.MATCH
    claims = tuple(
        c.model_copy(update={"qualifiers": tuple(map(str, stated))})
        if c.claim_key == REVENUE
        else c
        for c in draft.claims
    )
    if len(stated) > 1:
        with pytest.raises(DisplayError, match="more than one admission label"):
            content_hash(draft.sections, claims)
        tampered = next(c for c in claims if c.claim_key == REVENUE)
        resolved = _resolve(pilot, version_id, tampered)
        state = check_claim(
            tampered,
            resolved,
            mode=RunMode.AS_KNOWN,
            cutoff=draft.knowledge_cutoff,
            imported=False,
        )
        assert state is ClaimState.UNRESOLVED
        return
    pilot.approve(version_id)  # the drafted version approves; its tampered successor cannot
    update = {"claims": claims, "content_hash": content_hash(draft.sections, claims)}
    copy = draft.model_copy(update={**update, "predecessor_id": version_id})
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        tampered_id = store.create_version(cursor, copy)
    assert dict(pilot.validate(tampered_id).claim_states)[REVENUE] is ClaimState.UNRESOLVED
    with pytest.raises(DecisionRefusedError):
        pilot.approve(tampered_id)


def test_the_latest_admission_by_the_cutoff_authorises_and_its_label_shows(
    drafted: tuple[Pilot, int, int],
) -> None:
    """Finding 6: with the unchecked run and a later checked run both pinned, revenue and a
    calculation over it resolve checked now, and unchecked at the draft's cutoff (before the
    checked admission). A later contradiction of the former unchecked class withdraws only that
    unchecked authorisation: with both runs pinned the values stay checked, with the first alone
    they are withdrawn."""
    pilot, first, version_id = drafted
    draft = pilot.version(version_id)
    second = compare(pilot)
    with pilot.pg_db.runtime_pool() as pool:
        admit_run(second, pool=pool, store_id=pilot.store_id, config_root=pilot.config_root)  # type: ignore[attr-defined]
    rows = pilot.query(ADMISSIONS, version_id, REVENUE)
    assert [(run, label) for run, label, *_ in rows] == [(first, UNCHECKED), (second, CHECKED)]
    claims = {c.claim_key: c for c in draft.claims}
    computed = next(
        c for c in draft.claims if c.claim_key.startswith("calc.") and UNCHECKED in c.qualifiers
    )
    runs = (first, second)
    now = _now(pilot)
    for claim in (claims[REVENUE], computed):
        assert _label(pilot, version_id, claim, runs, now) is CHECKED, claim.claim_key
        at_draft = _label(pilot, version_id, claim, runs, draft.knowledge_cutoff)
        assert at_draft is UNCHECKED, claim.claim_key
    _, _, class_digest, result_id = rows[0]
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            record_counterexample(cursor, class_digest, result_id, first)
    later = _now(pilot)
    for claim in (claims[REVENUE], computed):
        assert _label(pilot, version_id, claim, runs, later) is CHECKED, claim.claim_key
        assert _label(pilot, version_id, claim, (first,), later) is None, claim.claim_key


def test_a_calculation_is_known_no_earlier_than_both_witnesses(
    drafted: tuple[Pilot, int, int],
) -> None:
    """Finding 2: a calculation over vendor operands carries both witnesses' registrations and
    its admission's recording; a cutoff between the two registrations is post-cutoff even
    retrospectively."""
    pilot, run_id, version_id = drafted
    draft = pilot.version(version_id)
    computed = next(
        c for c in draft.claims if c.claim_key.startswith("calc.") and UNCHECKED in c.qualifiers
    )
    trace = computed.citation.calculation_trace_id
    registered = [row[0] for row in pilot.query(REGISTERED, trace, run_id)]
    assert len(registered) >= 2 and registered[0] < registered[-1]
    resolved = _resolve(pilot, version_id, computed)
    assert resolved is not None
    first_seen = {at for name, at in resolved.times if name is InputTime.FIRST_SEEN}
    assert set(registered) <= first_seen
    assert any(name is InputTime.RECORDED for name, _ in resolved.times)
    between = registered[0] + (registered[-1] - registered[0]) / 2
    for mode in RunMode:
        state = check_claim(computed, resolved, mode=mode, cutoff=between, imported=False)
        assert state is ClaimState.POST_CUTOFF, mode


def _label(
    pilot: Pilot,
    version_id: int,
    claim: NumericClaim,
    runs: tuple[int, ...],
    cutoff: datetime,
) -> AdmissionLabel | None:
    """The claim's resolved label under ``runs`` at ``cutoff``, ``None`` when it is withdrawn."""
    resolved = _resolve(pilot, version_id, claim, runs, cutoff)
    return None if resolved is None else resolved.admission_label


def _resolve(
    pilot: Pilot,
    version_id: int,
    claim: NumericClaim,
    runs: tuple[int, ...] | None = None,
    cutoff: datetime | None = None,
) -> ResolvedCitation | None:
    """The claim's resolution now, under ``runs`` (the version's pins) at ``cutoff`` (its
    knowledge cutoff)."""
    draft = pilot.version(version_id)
    assert claim.citation.kind in (CitationKind.FIGURE, CitationKind.CALCULATION)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        return resolve_citation(
            cursor,
            claim,
            entity_id=pilot.entity_id,
            overlay_position=_now(pilot),
            run_ids=draft.pinned_run_ids if runs is None else runs,
            cutoff=draft.knowledge_cutoff if cutoff is None else cutoff,
            **pilot.sources(),
        )


def _now(pilot: Pilot) -> datetime:
    """The store clock."""
    with pilot.pg_db.runtime_pool() as pool:
        return EvidenceRepository(pool).store_clock()
