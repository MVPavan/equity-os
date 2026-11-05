"""An ambiguous filed line names candidate measurements without supplying any value."""

from datetime import UTC, datetime
from decimal import Decimal

from evidence_support import Q2_QUARTER, dictionary, mapping_set, policy
from selection_support import at, key, member, occurrence, package

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import (
    EligibilityBoundary,
    InterpretationStatus,
    InterpretationTriple,
    RunMode,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.qualification import QualificationContext
from equity_os.contracts.verification.comparison import SourceState
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary
from equity_os.normalisation.mapping.interpret import interpret
from equity_os.normalisation.mapping.mapping import MappingSet, NormalisationPolicy
from equity_os.verification.comparison.selection import select_key

__all__ = ["dictionary", "mapping_set", "policy"]


def test_ambiguous_attribution_routes_invalid_to_every_evidenced_candidate(
    dictionary: CanonicalDictionary, mapping_set: MappingSet, policy: NormalisationPolicy
) -> None:
    owner = member(Representation.PDF, 1, at(29), at(30))
    owner = owner.model_copy(
        update={"capture": owner.capture.model_copy(update={"surface": "NSE_RESULTS_PDF"})}
    )
    filed = occurrence(1, owner, extractor="pdf-occurrences/1").model_copy(
        update={
            "native_field": "(a) Owners of the Company",
            "raw_value_text": "251.70",
            "raw_scale": 7,
            "anchor": {"page": 3, "line": 44, "column_index": 0},
            "period": Q2_QUARTER,
            "native_context": {
                "schema_identity": "sebi-lodr-results-layout",
                "basis": "CONSOLIDATED",
                "statement_family": "PL",
                "label": "(a) Owners of the Company",
                "section": "unestablished attribution",
                "label_ordinal": 1,
                "header_months": 3,
            },
        }
    )
    qualification = QualificationContext(
        schema_identity="sebi-lodr-results-layout",
        surface="NSE_RESULTS_PDF",
        basis=key().basis,
        period_kind=Q2_QUARTER.kind(3),
        proven={},
    )
    invalid = interpret(
        filed,
        entity_id=1,
        basis=key().basis,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=qualification,
        recorded_at=datetime(2025, 10, 30, tzinfo=UTC),
    ).model_copy(update={"interpretation_id": 1})
    assert invalid.status is InterpretationStatus.INVALID and invalid.value is None
    pins = InterpretationTriple(
        mapping_set=mapping_set.version,
        normalisation_policy=policy.version,
        extractor_xbrl="unused",
        extractor_pdf="pdf-occurrences/1",
    )
    for canonical_id in (
        "profit_attributable_owners",
        "oci_attributable_owners",
        "tci_attributable_owners",
    ):
        selected = select_key(
            key(canonical_id),
            Representation.PDF,
            package=package(1, owner),
            occurrences=[filed],
            interpretations=[invalid],
            boundary=EligibilityBoundary.at(at(31)),
            mode=RunMode.AS_KNOWN,
            pinned=pins,
        )
        assert selected.state is SourceState.INVALID
        assert selected.interpretation == invalid
        assert selected.reason == "INTERPRETATION_AMBIGUOUS"
    unrelated = select_key(
        key("other_income"),
        Representation.PDF,
        package=package(1, owner),
        occurrences=[filed],
        interpretations=[invalid],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.AS_KNOWN,
        pinned=pins,
    )
    assert unrelated.state is SourceState.NO_VALUE
    for mismatched in (
        key("profit_attributable_owners").model_copy(update={"entity_id": 2}),
        key("profit_attributable_owners").model_copy(update={"currency": "USD"}),
        key("profit_attributable_owners").model_copy(
            update={"framework": AccountingFramework.IFRS}
        ),
    ):
        assert (
            select_key(
                mismatched,
                Representation.PDF,
                package=package(1, owner),
                occurrences=[filed],
                interpretations=[invalid],
                boundary=EligibilityBoundary.at(at(31)),
                mode=RunMode.AS_KNOWN,
                pinned=pins,
            ).state
            is SourceState.NO_VALUE
        )
    candidates = invalid.transform_trace["ambiguous_candidate_keys"]
    assert isinstance(candidates, list) and len(candidates) == 3
    assert all(
        isinstance(candidate, dict) and "value" not in candidate and "interval" not in candidate
        for candidate in candidates
    )
    oci_filed = filed.model_copy(
        update={
            "occurrence_id": 2,
            "raw_value_text": "22.95",
            "anchor": {"page": 3, "line": 47, "column_index": 0},
            "native_context": {
                **filed.native_context,
                "section": "Other comprehensive incomes attributable to",
            },
        }
    )
    explicit = interpret(
        oci_filed,
        entity_id=1,
        basis=key().basis,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        qualification=qualification,
        recorded_at=datetime(2025, 10, 30, tzinfo=UTC),
    ).model_copy(update={"interpretation_id": 2})
    assert explicit.status is InterpretationStatus.MAPPED and explicit.value == Decimal("229500000")
    selected_oci = select_key(
        key("oci_attributable_owners"),
        Representation.PDF,
        package=package(1, owner),
        occurrences=[filed, oci_filed],
        interpretations=[invalid, explicit],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.AS_KNOWN,
        pinned=pins,
    )
    # The explicit section-scoped reading stands; the unestablished line never displaces it
    # (stage1_manifest discrepancy apar-p3-profit-attributable-heading: oci_attributable_owners
    # PDF VALUE 22.95).
    assert selected_oci.state is SourceState.VALUE
    assert selected_oci.interpretation == explicit
    assert explicit.value == Decimal("229500000")
    # A line below the keyed reading (a duplicate whose heading was lost) is not excluded by
    # that heading: it stays a candidate and the key is ambiguous.
    below = invalid.model_copy(update={"interpretation_id": 3, "occurrence_id": 3})
    lost_heading = filed.model_copy(
        update={"occurrence_id": 3, "anchor": {"page": 3, "line": 50, "column_index": 0}}
    )
    duplicate = select_key(
        key("oci_attributable_owners"),
        Representation.PDF,
        package=package(1, owner),
        occurrences=[filed, oci_filed, lost_heading],
        interpretations=[invalid, explicit, below],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.AS_KNOWN,
        pinned=pins,
    )
    assert (duplicate.state, duplicate.reason) == (SourceState.INVALID, "INTERPRETATION_AMBIGUOUS")
