"""Original retained-input witness behavior at the existing append/validate seam.

The first case intentionally expects supported consumption of the actual retained
Apar schema-unsupported XML alongside the usable unchanged PDF. Before witness
production it fails at the existing failed-XBRL physical-binding guard, rather
than at a missing API, import or setup boundary. Root freezes that outcome first.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from retained_intake_witness_support import witnessed_reverse_fixture as _pdf_only_with_failed_xbrl
from test_compare_vendor_handoffs import _request

from fundamentals.compare.vendor_handoffs import validate_first_party_handoff
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def test_original_retained_reverse_xbrl_handoff_is_consumable(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Original input provenance closes a failed XML peer without promoting its failure."""
    root, config, handoff = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    before = ingest.table_counts()

    scope = validate_first_party_handoff(
        handoff,
        request=_request(ingest, config, handoff),
        config=config,
        config_root=root,
        repository=ingest.repository,
    )

    assert scope.package.package_id == handoff.package_id
    assert scope.package_eligible
    assert {member.representation for member in handoff.members} == {Representation.PDF}
    failed_xbrl = tuple(
        attempt for attempt in scope.attempts if attempt.representation is Representation.XBRL
    )
    assert len(failed_xbrl) == 1
    assert failed_xbrl[0].outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
    assert failed_xbrl[0].capture is not None
    assert failed_xbrl[0].package_id is None
    assert failed_xbrl[0].capture.capture_ref_id in {
        capture.capture_ref_id for capture in scope.capture_refs
    }
    assert {attempt.attempt_id for attempt in scope.attempts} == set(handoff.attempt_ids)
    assert ingest.table_counts() == before
