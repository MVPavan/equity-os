"""Public evidence boundaries preserve publication eligibility and ambiguous PDF rows."""

from __future__ import annotations

import pytest
from evidence_support import dictionary, mapping_set, pdf_context, policy
from selection_support import at, member, occurrence, package

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, Representation
from equity_os.contracts.measurement.evidence import (
    EligibilityBoundary,
    InterpretationReason,
    InterpretationStatus,
    KnowledgeTimeStatus,
    MissingValueState,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary
from equity_os.normalisation.mapping.interpret import interpret
from equity_os.normalisation.mapping.mapping import MappingSet, NormalisationPolicy

__all__ = ["dictionary", "mapping_set", "policy"]


@pytest.mark.parametrize("defect", ["unknown", "post_cutoff"])
def test_package_contract_refuses_unevidenced_member_publication(defect: str) -> None:
    owner = member(Representation.PDF, 11, at(29), at(30))
    filed = package(1, owner)
    changes = (
        {"knowledge_time_status": KnowledgeTimeStatus.UNKNOWN}
        if defect == "unknown"
        else {"knowledge_time": at(31)}
    )
    changed = owner.model_copy(update=changes)
    filed = filed.model_copy(update={"members": {Representation.PDF: changed}})
    assert not filed.eligible(EligibilityBoundary.at(at(30)))


def test_ambiguous_blank_pdf_row_preserves_key_and_is_invalid(
    dictionary: CanonicalDictionary, mapping_set: MappingSet, policy: NormalisationPolicy
) -> None:
    owner = member(Representation.PDF, 11, at(29), at(30))
    cell = occurrence(1, owner).model_copy(
        update={
            "native_field": "(a) Current tax",
            "raw_value_text": None,
            "missing_state": MissingValueState.BLANK,
            "native_context": {"pdf_row_ambiguous": True, "header_months": 3},
        }
    )
    row = interpret(
        cell,
        entity_id=1,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=pdf_context(PeriodKind.QUARTER),
        recorded_at=at(30),
        as_entry=mapping_set.entry("pdf.current_tax"),
    )
    assert row.status is InterpretationStatus.INVALID
    assert row.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert row.key is not None and row.canonical_id == "current_tax"
    assert row.value is None and row.interval is None
