"""VENDOR-1 §6.6, finding 10: a filing contradicting the class of an unchecked operand behind a
calculation claim notes that calculation in the sealed version's status note, while the version's
bytes and hash stay unchanged. The world is ``vendor_report_support``'s withheld Apar FY26_Q2."""

from __future__ import annotations

from typing import Any

import pytest
from evidence_support import CONFIG, XBRL_KIND, ingest, policy
from psycopg import Cursor
from psycopg.rows import dict_row
from vendor_report_support import ELIGIBILITY, END, QUARTER, compare, report, vendor_pilot

from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import MappingSet, load_mapping_set
from equity_os.publication.drafting.run_draft import RUN_AUTHOR
from equity_os.publication.export.export import export_version, status_note, stock_versions
from equity_os.verification.admission.eligibility import record_counterexample

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

VERSION = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
HASH = "SELECT content_hash FROM eqos.report_versions WHERE id = %s"
# The unchecked admissions under the version's pins of the operands a calculation claim reaches.
OPERAND_ADMISSIONS = """WITH RECURSIVE traces(id) AS (
    SELECT calculation_trace_id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s
    UNION SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.operand_trace_id IS NOT NULL)
SELECT DISTINCT a.class_digest, a.result_id, a.run_id FROM traces t
JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = t.id
JOIN eqos.fact_admissions a ON a.interpretation_id = o.interpretation_id
JOIN eqos.report_versions v ON v.id = %s AND a.run_id = ANY(v.pinned_run_ids)
WHERE a.class_digest IS NOT NULL ORDER BY a.result_id LIMIT 1"""
NOTE = "class later contradicted by a filing on"


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v9, the pilot comparison pin."""
    return load_mapping_set(CONFIG / "normalisation/mappings", "v9", dictionary=dictionary)


def test_a_contradicted_operand_class_notes_the_calculation(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A calculation claim, which cites a trace and no fact, gets the contradiction note through
    its operands; the export is unchanged."""
    pilot = vendor_pilot(request, monkeypatch, withheld=True)
    run_id = compare(pilot, ELIGIBILITY)
    pilot.evidence_ingest(QUARTER, XBRL_KIND, END)
    assert report(pilot, run_id) == 0
    ((version_id,),) = pilot.query(VERSION, RUN_AUTHOR)
    pilot.approve(version_id)
    calculation = next(
        c.claim_key
        for c in pilot.version(version_id).claims
        if c.claim_key.startswith("calc.")
        and AdmissionLabel.VENDORS_AGREE_NOT_CHECKED in c.qualifiers
    )
    ((class_digest, result_id, admitted_run),) = pilot.query(
        OPERAND_ADMISSIONS, version_id, calculation, version_id
    )
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        with conn.cursor() as cursor:
            before = export_version(cursor, version_id), pilot.query(HASH, version_id)
            assert f"- {calculation}: {NOTE} " not in _note(cursor, pilot.entity_id, version_id)
        with conn.cursor(row_factory=dict_row) as cursor:
            record_counterexample(cursor, class_digest, result_id, admitted_run)
        with conn.cursor() as cursor:
            assert f"- {calculation}: {NOTE} " in _note(cursor, pilot.entity_id, version_id)
            assert (export_version(cursor, version_id), pilot.query(HASH, version_id)) == before


def _note(cursor: Cursor[Any], entity_id: int, version_id: int) -> str:
    """The version's status note."""
    (identity,) = [v for v in stock_versions(cursor, entity_id) if v.version_id == version_id]
    return status_note(cursor, identity, ())
