"""VENDOR-1 Task 9: citations of a report drafted from vendor-admitted facts (spec §6.6, §6.9,
§6.10; acceptance 9 and 10).

The world is ``vendor_report_support``'s withheld Apar FY26_Q2: all six roles row 3, the draft
approved. A citation resolves with the weakest admission label; a quote or policy citation has
none. An expired witness, an ended licence or a contradicted class withdraws the vendor value
for a new report, while the sealed version's bytes and hash never change and its status note
says why. A re-fetch cannot revive a vendor capture (0031 restores exchange captures only).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from evidence_support import CONFIG, XBRL_KIND, ingest, policy
from prep2b_support import Pilot
from psycopg.rows import dict_row
from vendor_report_support import ELIGIBILITY, END, QUARTER, compare, report, vendor_pilot

from equity_os.contracts.publication.ledger import CitationKind, NumericClaim
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import MappingSet, load_mapping_set
from equity_os.publication.checking.citations import ResolvedCitation, resolve_citation
from equity_os.publication.drafting.run_draft import RUN_AUTHOR
from equity_os.publication.export.export import export_version, status_note, stock_versions
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.eligibility import record_counterexample

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

UNCHECKED = AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
VERSION = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
HASH = "SELECT content_hash FROM eqos.report_versions WHERE id = %s"
REVENUE = "fact.revenue"
# The revenue claim's admission under the run, with its witnesses' captures and sources.
ADMISSION = """SELECT a.class_digest, r.id AS result_id, cw.id AS witness, cw.source_id
FROM eqos.numeric_claims k
JOIN eqos.fact_admissions a USING (fact_origin, fact_origin_id)
JOIN eqos.results r ON r.run_id = a.run_id AND r.key_digest = k.key_digest
JOIN eqos.interpretations w ON w.id = a.witness_interpretation_id
JOIN eqos.capture_refs cw ON cw.id = w.capture_ref_id
WHERE k.version_id = %s AND k.claim_key = %s AND a.run_id = %s"""
WITNESS_PAIR = """SELECT c.id FROM eqos.fact_admissions a
JOIN eqos.interpretations i ON i.id IN (a.interpretation_id, a.witness_interpretation_id)
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
JOIN eqos.numeric_claims k USING (fact_origin, fact_origin_id)
WHERE k.version_id = %s AND k.claim_key = %s AND a.run_id = %s"""
ROW_CAPTURES = (
    "SELECT unnest(eqos.row_captures('numeric_claims', to_jsonb(k))) FROM eqos.numeric_claims k "
    "WHERE k.version_id = %s AND k.claim_key = %s"
)
POLICY = (
    "SELECT version_id, claim_key FROM eqos.numeric_claims WHERE citation_kind = 'POLICY' "
    "ORDER BY id LIMIT 1"
)
CAPTURE_STATE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, 'EXPIRED')"
LICENCE_END = "INSERT INTO eqos.licence_ends (source_id) VALUES (%s)"
NOTES = {
    "expired": "vendor source expired",
    "licence": "vendor source expired",
    "contradicted": "class later contradicted by a filing on",
}


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v9, the pilot comparison pin."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v9", dictionary=dictionary)


@pytest.fixture
def approved(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> tuple[Pilot, int, int]:
    """The withheld world's run draft, approved: the pilot, its comparison run and version."""
    pilot = vendor_pilot(request, monkeypatch, withheld=True)
    run_id = compare(pilot, ELIGIBILITY)
    pilot.evidence_ingest(QUARTER, XBRL_KIND, END)
    assert report(pilot, run_id) == 0
    ((version_id,),) = pilot.query(VERSION, RUN_AUTHOR)
    pilot.approve(version_id)
    return pilot, run_id, version_id


def test_vendor_citations_carry_the_label_and_retain_both_witnesses(
    approved: tuple[Pilot, int, int],
) -> None:
    """Acceptance 9: a fact and a calculation from it resolve labelled "vendors agree, not
    checked"; quote and policy citations carry no label; the fact's claim retains both
    witnesses' captures."""
    pilot, run_id, version_id = approved
    claims = {claim.claim_key: claim for claim in pilot.version(version_id).claims}
    computed = next(
        c for c in claims.values() if c.claim_key.startswith("calc.") and UNCHECKED in c.qualifiers
    )
    for claim in (claims[REVENUE], computed):
        resolved = _resolve(pilot, version_id, claim)
        assert resolved is not None and resolved.admission_label is UNCHECKED, claim.claim_key
    quotes = [c for c in claims.values() if c.citation.kind is CitationKind.SOURCE_QUOTE]
    ((sealed, key),) = pilot.query(POLICY)  # an imported version's policy claim
    policies = [c for c in pilot.version(sealed).claims if c.claim_key == key]
    assert quotes and policies
    for owner, claim in [*((version_id, c) for c in quotes), (sealed, policies[0])]:
        resolved = _resolve(pilot, owner, claim)
        assert resolved is not None and resolved.admission_label is None, claim.claim_key
    witnesses = {row[0] for row in pilot.query(WITNESS_PAIR, version_id, REVENUE, run_id)}
    assert len(witnesses) == 2
    assert witnesses <= {row[0] for row in pilot.query(ROW_CAPTURES, version_id, REVENUE)}


@pytest.mark.parametrize("withdrawal", sorted(NOTES))
def test_a_withdrawn_vendor_value_leaves_the_sealed_version_unchanged(
    approved: tuple[Pilot, int, int], withdrawal: str
) -> None:
    """Acceptance 10 and §6.6: an expired witness, an ended licence or a filing contradicting
    the class withdraws the fact for a new report; the sealed version's bytes and hash do not
    change and its status note gives the reason and date. A contradiction leaves a report drafted
    before it standing."""
    pilot, run_id, version_id = approved
    draft = pilot.version(version_id)
    before = _export(pilot, version_id)
    (admission,) = pilot.query(ADMISSION, version_id, REVENUE, run_id)
    class_digest, result_id, witness, source_id = admission
    if withdrawal == "expired":
        with pilot.pg_db.migrator_connection() as migrator:
            migrator.execute(CAPTURE_STATE, (witness,))
    elif withdrawal == "licence":
        with pilot.pg_db.owner_pool() as owner, owner.connection() as conn:
            conn.execute(LICENCE_END, (source_id,))
    else:
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                record_counterexample(cursor, class_digest, result_id, run_id)
    revenue = next(c for c in draft.claims if c.claim_key == REVENUE)
    assert _resolve(pilot, version_id, revenue, cutoff=_now(pilot)) is None  # a new report
    standing = _resolve(pilot, version_id, revenue, cutoff=draft.knowledge_cutoff)
    assert (standing is not None) is (withdrawal == "contradicted")
    assert _export(pilot, version_id) == before
    note = _note(pilot, version_id)
    assert f"- {REVENUE}: {NOTES[withdrawal]} " in note


def _resolve(
    pilot: Pilot, version_id: int, claim: NumericClaim, cutoff: datetime | None = None
) -> ResolvedCitation | None:
    """The claim's resolution under the version's pins, now, judged at ``cutoff`` (the
    version's knowledge cutoff unless given)."""
    draft = pilot.version(version_id)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        return resolve_citation(
            cursor,
            claim,
            entity_id=pilot.entity_id,
            overlay_position=_now(pilot),
            run_ids=draft.pinned_run_ids,
            cutoff=cutoff or draft.knowledge_cutoff,
            **pilot.sources(),
        )


def _export(pilot: Pilot, version_id: int) -> tuple[bytes, Any]:
    """The version's exported bytes and stored content hash."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        return export_version(cursor, version_id), pilot.query(HASH, version_id)


def _note(pilot: Pilot, version_id: int) -> str:
    """The version's status note."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        (identity,) = [
            v for v in stock_versions(cursor, pilot.entity_id) if v.version_id == version_id
        ]
        return status_note(cursor, identity, ())


def _now(pilot: Pilot) -> datetime:
    """The store clock."""
    with pilot.pg_db.runtime_pool() as pool:
        return EvidenceRepository(pool).store_clock()
