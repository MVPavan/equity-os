"""Pure closed-evidence mechanics; synthetic bodies never qualify a real vendor.

The vendor occurrence is parsed from the marked committed Screener fixture. First-party
rows and changed store outcomes are explicit synthetic witnesses for assembly behavior.
"""

from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from test_compare_vendor_inputs import NOW, arguments, fixture
from test_vendor_config_publication import _publish_synthetic
from vendor_rows_support import Case, assembled, later, vendor_value
from vendor_rows_support import case as case

from fundamentals.canon.formula import CalculationTrace, TraceKind, TraceOperand
from fundamentals.canon.interval import Interval
from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.compare.resolve import ReplayMismatchError, load_inputs
from fundamentals.compare.resolve_models import ReplayReader
from fundamentals.compare.run_config import ConfigVersions, load_run_config
from fundamentals.compare.run_models import (
    PairRecord,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    row_id,
)
from fundamentals.compare.vendor_inputs import compose_vendor_generation
from fundamentals.compare.vendor_request import logical_scope_sha256, request_from_declaration
from fundamentals.compare.vendor_rows import attach_vendor_rows, queue_drafts
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    TemporalRole,
    ValueIdentity,
)
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    SelectionSource,
    SourceRef,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    AttemptStage,
    InterpretationReason,
    InterpretationStatus,
    KnowledgeTimeStatus,
    PackageMember,
    exact_decimal,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.qualification import ProvenCondition
from fundamentals.contracts.review_queue import QueueSeverity
from fundamentals.contracts.source_catalog import EvidenceRole
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.repository import SegmentMemberRecord
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.ingest.screener_financials_models import Section


def test_not_applicable_without_representative_preserves_absence(case: Case) -> None:
    row = case.row.model_copy(
        update={
            "applicability": ApplicabilityStatus.NOT_APPLICABLE,
            "extraction_status": ExtractionStatus.NOT_APPLICABLE,
            "corroboration_status": CorroborationStatus.NOT_APPLICABLE,
            "source_values": (),
            "pairs": (),
        }
    )
    assert assembled(case, rows=(row,)) == (row,)
    assert queue_drafts((row,), inputs=case.inputs, request=case.request, config=case.config) == ()


def test_by_id_reload_refuses_segment_link_outside_frozen_occurrences(case: Case) -> None:
    reader = Mock(spec=ReplayReader)
    for name in (
        "get_capture_refs",
        "get_packages",
        "get_package_statements",
        "get_interpretations",
        "get_attempts",
        "get_alignment_proofs",
        "get_calculation_traces",
        "get_evidence_inputs",
        "get_settings_records",
        "get_basis_statuses",
    ):
        getattr(reader, name).return_value = ()
    reader.get_occurrences.return_value = (case.occurrence,)
    segment = SegmentMemberRecord(
        id=401,
        entity_id=1,
        axis="segment",
        member="synthetic-segment",
        display_name="Synthetic segment",
        valid_from=date(2025, 7, 1),
        valid_to=None,
        recorded_at=NOW,
        evidence_occurrence_ids=(101, 999),
    )
    reader.get_segment_members.return_value = (segment,)
    tokens = tuple(
        RunInput(kind=kind, ref_id=identifier, disposition=RunInputDisposition.SELECTED)
        for kind, identifier in (
            (RunInputKind.DEFINITION_SET, 1),
            (RunInputKind.OCCURRENCE, 101),
            (RunInputKind.SEGMENT_MEMBER, 401),
        )
    )
    with pytest.raises(ReplayMismatchError, match="segment.*frozen"):
        load_inputs(reader, tokens)
    closed = segment.model_copy(update={"evidence_occurrence_ids": (101,)})
    reader.get_segment_members.return_value = (closed,)
    loaded = load_inputs(reader, tokens)
    assert loaded.segment_members == (closed,)
    assert loaded.occurrences == (case.occurrence,)
    reader.get_occurrences.assert_called_with([101])
    reader.get_segment_members.assert_called_with([401])


def test_actual_marked_sales_side_pair_and_queue_evidence(case: Case) -> None:
    rows = assembled(case)
    value = vendor_value(rows)
    assert value.value == Decimal("12000000000")  # Sep 2025 Sales: 1,200 printed crore.
    assert value.source_id == "screener-subscriber" and value.surface == "SCREENER_FINANCIALS"
    assert value.interpretation_id == 201 and value.representation is Representation.HTML
    assert rows[0].corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED
    assert rows[0].pairs[0].outcome is PairOutcome.AGREE_UNQUALIFIED
    assert rows[0].pairs[0].left.source_id == "nse"
    drafts = queue_drafts(rows, inputs=case.inputs, request=case.request, config=case.config)
    assert len(drafts) == 1 and drafts[0].severity is QueueSeverity.LOW
    assert drafts[0].evidence_interpretation_ids == (601,)
    assert drafts[0].evidence_occurrence_ids == (501,)
    assert all(ref.source_role is SourceRole.FIRST_PARTY for ref in drafts[0].source_refs)
    assert (
        assembled(
            case,
            inputs=case.inputs.model_copy(
                update={
                    "interpretations": tuple(reversed(case.inputs.interpretations)),
                    "occurrences": tuple(reversed(case.inputs.occurrences)),
                }
            ),
        )
        == rows
    )


def test_two_equal_candidates_are_invalid_without_first_match(case: Case) -> None:
    duplicate_occurrence = case.occurrence.model_copy(
        update={"occurrence_id": 102, "anchor_key": "marked-duplicate"}
    )
    duplicate = case.vendor.model_copy(update={"interpretation_id": 202, "occurrence_id": 102})
    inputs = case.inputs.model_copy(
        update={
            "occurrences": (*case.inputs.occurrences, duplicate_occurrence),
            "interpretations": (*case.inputs.interpretations, duplicate),
        }
    )
    rows = assembled(case, inputs=inputs)
    value = vendor_value(rows)
    assert (
        value.state is SourceState.INVALID
        and value.value is None
        and value.interpretation_id is None
    )
    assert value.reason == "INTERPRETATION_AMBIGUOUS"
    assert rows[0].corroboration_status is CorroborationStatus.NOT_COMPARABLE
    drafts = queue_drafts(rows, inputs=inputs, request=case.request, config=case.config)
    refusal = next(
        draft
        for draft in drafts
        if draft.outcome == "NOT_COMPARABLE" and draft.pair_identity.startswith("status:")
    )
    assert refusal.evidence_interpretation_ids == (201, 202, 601)
    assert refusal.evidence_occurrence_ids == (101, 102, 501)


@pytest.mark.parametrize(
    "stage,captured", ((AttemptStage.ACQUISITION, False), (AttemptStage.EXTRACTION, True))
)
def test_later_same_logical_failure_suppresses_old_value_across_requests(
    case: Case, stage: AttemptStage, captured: bool
) -> None:
    capture = (
        case.occurrence.capture.model_copy(
            update={"capture_ref_id": 2, "capture_id": "marked-new-physical-response"}
        )
        if captured
        else None
    )
    failed = later(case, outcome=ExtractionOutcome.PARSE_FAILED, capture=capture, stage=stage)
    inputs = case.inputs.model_copy(update={"attempts": (*case.inputs.attempts, failed)})
    rows = assembled(case, inputs=inputs)
    value = vendor_value(rows)
    assert (
        value.state is SourceState.UNAVAILABLE and value.value is None and value.attempt_id == 901
    )
    assert (
        value.interpretation_id is None
        and rows[0].corroboration_status is CorroborationStatus.UNAVAILABLE
    )
    drafts = queue_drafts(rows, inputs=inputs, request=case.request, config=case.config)
    assert not any(
        draft.diagnostic
        or any(ref.source_role is SourceRole.INDEPENDENT_VENDOR for ref in draft.source_refs)
        for draft in drafts
    )


def test_failure_in_other_logical_scope_cannot_suppress_success(case: Case) -> None:
    failed = later(case, outcome=ExtractionOutcome.FAILED, logical="f" * 64)
    rows = assembled(
        case, inputs=case.inputs.model_copy(update={"attempts": (*case.inputs.attempts, failed)})
    )
    assert vendor_value(rows).state is SourceState.VALUE
    assert vendor_value(rows).interpretation_id == 201


def test_newer_unhanded_complete_never_substitutes_old_facts(case: Case) -> None:
    complete = later(
        case,
        outcome=ExtractionOutcome.COMPLETE,
        capture=case.occurrence.capture.model_copy(update={"capture_ref_id": 2}),
    )
    rows = assembled(
        case, inputs=case.inputs.model_copy(update={"attempts": (*case.inputs.attempts, complete)})
    )
    value = vendor_value(rows)
    assert value.state is SourceState.UNAVAILABLE and value.reason == "UNHANDED_VENDOR_GENERATION"
    assert value.value is None and value.interpretation_id is None and value.attempt_id == 901


def test_same_clock_uses_actual_attempt_id_and_cutoff_excludes_future_failure(case: Case) -> None:
    failed = later(case, outcome=ExtractionOutcome.FAILED).model_copy(update={"attempted_at": NOW})
    inputs = case.inputs.model_copy(update={"attempts": (*case.inputs.attempts, failed)})
    assert vendor_value(assembled(case, inputs=inputs)).attempt_id == 901
    future = failed.model_copy(update={"attempted_at": case.request.cutoff + timedelta(seconds=1)})
    assert (
        vendor_value(
            assembled(
                case,
                inputs=case.inputs.model_copy(update={"attempts": (*case.inputs.attempts, future)}),
            )
        ).state
        is SourceState.VALUE
    )


def test_same_capture_other_semantic_section_cannot_supply_a_value(case: Case) -> None:
    foreign = case.occurrence.model_copy(
        update={"native_context": {**case.occurrence.native_context, "section": "profit-loss"}}
    )
    rows = assembled(
        case,
        inputs=case.inputs.model_copy(
            update={"occurrences": (foreign, case.inputs.occurrences[1])}
        ),
    )
    assert vendor_value(rows).state is SourceState.NO_VALUE and vendor_value(rows).value is None


def test_invalid_and_nonvalue_interpretations_are_preserved(case: Case) -> None:
    invalid = case.vendor.model_copy(
        update={
            "status": InterpretationStatus.INVALID,
            "reason": InterpretationReason.UNREADABLE_CELL,
            "value": None,
            "interval": None,
        }
    )
    inputs = case.inputs.model_copy(
        update={"interpretations": (invalid, case.inputs.interpretations[1])}
    )
    value = vendor_value(assembled(case, inputs=inputs))
    assert value.state is SourceState.INVALID and value.reason == "UNREADABLE_CELL"
    absent = case.vendor.model_copy(update={"value": None, "interval": None})
    value = vendor_value(
        assembled(
            case,
            inputs=case.inputs.model_copy(
                update={"interpretations": (absent, case.inputs.interpretations[1])}
            ),
        )
    )
    assert (
        value.state is SourceState.NO_VALUE
        and value.value is None
        and value.interpretation_id == 201
    )


def test_diagnostic_authority_routes_disagreement_without_voting(case: Case) -> None:
    # Counterfactual synthetic publication: this grants no rights or role to a real source.
    publication = case.config.vendor_config
    assert publication is not None
    authorities = tuple(
        row.model_copy(update={"evidence_role": EvidenceRole.DIAGNOSTIC_ONLY})
        if row.source_id == case.declaration.source_id
        else row
        for row in publication.authorities
    )
    catalog = publication.catalog.model_copy(
        update={
            "entries": tuple(
                row.model_copy(update={"evidence_role": EvidenceRole.DIAGNOSTIC_ONLY})
                if row.source_id == case.declaration.source_id
                else row
                for row in publication.catalog.entries
            )
        }
    )
    config = case.config.model_copy(
        update={
            "vendor_config": publication.model_copy(
                update={"authorities": authorities, "catalog": catalog}
            )
        }
    )
    vendor = case.vendor.model_copy(
        update={
            "value": Decimal("9000000000"),
            "interval": Interval.from_precision(Decimal("9000000000"), -7),
        }
    )
    inputs = case.inputs.model_copy(
        update={"interpretations": (vendor, case.inputs.interpretations[1])}
    )
    rows = assembled(case, inputs=inputs, config=config)
    assert vendor_value(rows).source_role is SourceRole.DIAGNOSTIC
    assert rows[0].corroboration_status is CorroborationStatus.FILING_ONLY
    assert rows[0].pairs[0].pair_kind is PairKind.DIAGNOSTIC
    drafts = queue_drafts(rows, inputs=inputs, request=case.request, config=config)
    disagreement = next(draft for draft in drafts if draft.diagnostic)
    assert (
        disagreement.severity is QueueSeverity.MEDIUM
        and disagreement.routing_reason == "PARSE_CHECK_DISAGREE"
    )
    assert disagreement.evidence_interpretation_ids == (201, 601)


def test_vendor_only_key_uses_actual_context_and_has_no_invented_fp_value(case: Case) -> None:
    # A closed stored key without an FP result is an honest vendor-only result.
    rows = assembled(case, rows=())
    assert len(rows) == 1 and rows[0].key == case.vendor.key
    assert rows[0].applicability is ApplicabilityStatus.APPLICABLE
    assert rows[0].corroboration_status is CorroborationStatus.VENDOR_ONLY
    fp = next(
        value for value in rows[0].source_values if value.source_role is SourceRole.FIRST_PARTY
    )
    assert fp.state is SourceState.NO_VALUE and fp.value is None and fp.interpretation_id is None
    draft = next(
        draft
        for draft in queue_drafts(
            rows, inputs=case.inputs, request=case.request, config=case.config
        )
        if draft.outcome == "VENDOR_ONLY"
    )
    assert draft.evidence_interpretation_ids == (201,) and draft.evidence_occurrence_ids == (101,)


def test_missing_native_operand_closure_fails_closed(case: Case) -> None:
    constructed = case.vendor.model_copy(update={"operand_interpretation_ids": (999,)})
    inputs = case.inputs.model_copy(
        update={"interpretations": (constructed, case.inputs.interpretations[1])}
    )
    with pytest.raises(RunResolutionError, match="not loaded by id"):
        assembled(case, inputs=inputs)


def test_native_construction_routes_exact_recursive_operands(case: Case, tmp_path: Path) -> None:
    private = tmp_path / "native-balance"
    private.mkdir()
    instant = PeriodInterval.at(date(2026, 3, 31))
    setup = fixture(private, section=Section.BALANCE_SHEET, period=instant)
    # Extend only the private synthetic fixture with the actual committed native rule.
    index_path = setup[0] / "mappings/v2.yaml"
    index = yaml.safe_load(index_path.read_bytes())
    index["construction_files"].append("screener/v2/constructions.yaml")
    index_path.write_text(yaml.safe_dump(index, sort_keys=False))
    _publish_synthetic(setup[0])
    config = load_run_config(
        setup[0], ConfigVersions(mapping_set="v2"), allow_synthetic_vendor_config=True
    )
    setup = (*setup[:2], config, *setup[3:])
    declaration = setup[3].model_copy(update={"statement_family": StatementFamily.BALANCE_SHEET})
    pin = next(
        pin
        for pin in config.pinned.vendor_extractors
        if (pin.source_id, pin.surface) == (declaration.source_id, declaration.surface)
    )
    declaration = declaration.model_copy(
        update={
            "expected_logical_scope_sha256": logical_scope_sha256(
                request_from_declaration(declaration), extractor_pin=pin, composer_context=setup[4]
            )
        }
    )
    generation = compose_vendor_generation(**arguments((*setup[:3], declaration, *setup[4:])))
    occurrences = tuple(
        row.model_copy(update={"occurrence_id": 21 + index})
        for index, row in enumerate(
            row
            for row in generation.occurrences
            if row.period == instant and row.native_field in {"Borrowings", "Other Liabilities"}
        )
    )
    assert {row.raw_value_text for row in occurrences} == {"1,200", "900"}
    counter = iter(range(200, 220))
    scope = CaptureScope(
        capture=generation.capture,
        entity_id=1,
        basis=Basis.CONSOLIDATED,
        framework=declaration.framework,
        mapping_set=config.mapping_set,
        policy=config.normalisation_policy,
        dictionary=config.dictionary,
        fiscal_year_end_month=3,
        expected_extractor_pin=pin,
    )
    interpretations = interpret_generation(
        occurrences,
        scope=scope,
        prior=(),
        prior_anchor_keys={},
        reserve_ids=lambda count: tuple(next(counter) for _ in range(count)),
        recorded_at=NOW,
    )
    constructed = next(row for row in interpretations if row.construction_rule_id is not None)
    assert constructed.value == Decimal("21000000000")  # 1,200 + 900 printed crore.
    package = case.inputs.packages[0].model_copy(
        update={
            "reporting_period_end": instant.instant,
            "reporting_kind": PeriodKind.YEAR,
            "statements_present": frozenset({StatementFamily.BALANCE_SHEET}),
        }
    )
    inputs = case.inputs.model_copy(
        update={
            "capture_refs": (generation.capture, case.inputs.capture_refs[1]),
            "packages": (package,),
            "occurrences": occurrences,
            "interpretations": interpretations,
            "attempts": tuple(
                row.model_copy(update={"attempt_id": 301 + index, "attempted_at": NOW})
                for index, row in enumerate(generation.attempts)
            ),
        }
    )
    request = case.request.model_copy(
        update={
            "pinned": config.pinned,
            "scope": case.request.scope.model_copy(
                update={"period_ends": (instant.instant,), "vendor_sources": (declaration,)}
            ),
        }
    )
    rows = attach_vendor_rows((), inputs=inputs, request=request, config=config)
    row = next(row for row in rows if row.key.canonical_id == "liabilities_incl_nci")
    assert row.corroboration_status is CorroborationStatus.VENDOR_ONLY
    draft = next(
        draft
        for draft in queue_drafts(rows, inputs=inputs, request=request, config=config)
        if draft.key == row.key and draft.outcome == "VENDOR_ONLY"
    )
    assert set(draft.evidence_interpretation_ids) == {
        constructed.interpretation_id,
        *constructed.operand_interpretation_ids,
    }
    assert draft.evidence_occurrence_ids == (21, 22)
    assert {ref.source_id for ref in draft.source_refs} == {"nse", "screener-subscriber"}


def test_condition_evidence_recurses_and_preserves_named_source(case: Case) -> None:
    # Marked stored condition witness; no demonstrated tier is added by the fixture.
    condition_occurrence = case.inputs.occurrences[1].model_copy(
        update={"occurrence_id": 503, "anchor_key": "marked-condition"}
    )
    condition = case.inputs.interpretations[1].model_copy(
        update={"interpretation_id": 603, "occurrence_id": 503}
    )
    selected = case.inputs.interpretations[1].model_copy(
        update={
            "condition_evidence": (
                ProvenCondition(
                    condition_id="marked-nonzero-condition",
                    holds=True,
                    evidence_interpretation_ids=(603,),
                ),
            )
        }
    )
    inputs = case.inputs.model_copy(
        update={
            "occurrences": (*case.inputs.occurrences, condition_occurrence),
            "interpretations": (case.vendor, selected, condition),
        }
    )
    rows = assembled(case, inputs=inputs)
    draft = next(
        draft
        for draft in queue_drafts(rows, inputs=inputs, request=case.request, config=case.config)
        if draft.outcome == "ONE_SIDE_XBRL"
    )
    assert draft.evidence_interpretation_ids == (601, 603)
    assert draft.evidence_occurrence_ids == (501, 503)
    assert {ref.source_id for ref in draft.source_refs} == {"nse"}


def test_explicit_false_fp_source_ref_refuses_instead_of_relabelling(case: Case) -> None:
    value = case.row.source_values[0].model_copy(
        update={"source_id": "wrong-source", "surface": "wrong-surface"}
    )
    row = case.row.model_copy(update={"source_values": (value,)})
    with pytest.raises(RunResolutionError, match="actual source"):
        assembled(case, rows=(row,))


def test_vendor_pair_refs_name_the_exact_returned_source_values(case: Case) -> None:
    rows = assembled(case)
    values = {
        (value.source_role, value.representation, value.source_id, value.surface)
        for value in rows[0].source_values
    }
    assert all(
        (ref.source_role, ref.representation, ref.source_id, ref.surface) in values
        for pair in rows[0].pairs
        for ref in (pair.left, pair.right)
    )


def test_existing_extraction_pairs_get_matching_refs_and_only_fp_queue_evidence(case: Case) -> None:
    capture = case.inputs.capture_refs[1].model_copy(
        update={"capture_ref_id": 11, "surface": "NSE_RESULTS_PDF", "capture_id": "marked-fp-pdf"}
    )
    interval = Interval.from_precision(Decimal("9000000000"), -7)
    occurrence = case.inputs.occurrences[1].model_copy(
        update={
            "occurrence_id": 502,
            "capture": capture,
            "representation": Representation.PDF,
            "extractor_version": case.config.pinned.extractor_pdf.version,
        }
    )
    interpretation = case.inputs.interpretations[1].model_copy(
        update={
            "interpretation_id": 602,
            "occurrence_id": 502,
            "capture_ref_id": 11,
            "representation": Representation.PDF,
            "extractor_version": case.config.pinned.extractor_pdf.version,
            "value": Decimal("9000000000"),
            "interval": interval,
        }
    )
    value = case.row.source_values[0].model_copy(
        update={
            "representation": Representation.PDF,
            "interpretation_id": 602,
            "value": interpretation.value,
            "lower": exact_decimal(interval.lower),
            "upper": exact_decimal(interval.upper),
        }
    )
    package = case.inputs.packages[0]
    package = package.model_copy(
        update={
            "members": {
                **package.members,
                Representation.PDF: PackageMember(
                    representation=Representation.PDF,
                    capture=capture,
                    knowledge_time=NOW,
                    knowledge_time_raw=NOW.isoformat(),
                    knowledge_time_status=KnowledgeTimeStatus.KNOWN,
                ),
            }
        }
    )
    legacy_pair = PairRecord(
        pair_kind=PairKind.EXTRACTION,
        left=SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.XBRL),
        right=SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.PDF),
        outcome=PairOutcome.MISMATCH,
        reason=None,
        triage=None,
        difference=Decimal("3000000000"),
        interval_gap=Decimal("2990000000"),
        definition_record_id=None,
    )
    row = case.row.model_copy(
        update={
            "source_values": (*case.row.source_values, value),
            "pairs": (legacy_pair,),
            "extraction_status": ExtractionStatus.DISAGREE,
        }
    )
    inputs = case.inputs.model_copy(
        update={
            "capture_refs": (*case.inputs.capture_refs, capture),
            "packages": (package,),
            "occurrences": (*case.inputs.occurrences, occurrence),
            "interpretations": (*case.inputs.interpretations, interpretation),
        }
    )
    rows = assembled(case, inputs=inputs, rows=(row,))
    values = {
        (value.source_role, value.representation, value.source_id, value.surface)
        for value in rows[0].source_values
    }
    assert all(
        (ref.source_role, ref.representation, ref.source_id, ref.surface) in values
        for pair in rows[0].pairs
        for ref in (pair.left, pair.right)
    )

    drafts = queue_drafts(rows, inputs=inputs, request=case.request, config=case.config)
    assert len(drafts) == 2
    assert all(draft.severity is QueueSeverity.HIGH for draft in drafts)
    assert all(draft.evidence_interpretation_ids == (601, 602) for draft in drafts)
    assert all(draft.evidence_occurrence_ids == (501, 502) for draft in drafts)
    assert all(
        ref.source_role is SourceRole.FIRST_PARTY for draft in drafts for ref in draft.source_refs
    )


def test_fp_trace_keeps_exact_fraction_interval_and_uses_stored_display_bounds(case: Case) -> None:
    # An explicit marked trace witness for storage conversion, not a qualified formula.
    fp = case.inputs.interpretations[1]
    operand = TraceOperand(
        name="marked-operand",
        key_digest=case.row.key.digest(),
        temporal_role=TemporalRole.DURATION,
        interpretation_id=601,
        operand_trace_id=None,
        alignment_proof_id=None,
        mapping_entry_id=fp.mapping_entry_id,
        qualification_ref=None,
        scoped_tier=fp.tier,
        selection_source=SelectionSource.PACKAGE_AS_REPORTED,
        source_state=SourceState.VALUE,
        value=fp.value,
        lower=case.row.source_values[0].lower,
        upper=case.row.source_values[0].upper,
        exact_value=Fraction(fp.value),
        exact_interval=fp.interval,
    )
    exact = Fraction(fp.value)
    interval = Interval(lower=exact - Fraction(1, 3), upper=exact + Fraction(1, 3))
    trace = CalculationTrace(
        trace_kind=TraceKind.FORMULA,
        formula_id="marked-reader-witness",
        formula_version="fixture",
        formula_tier=None,
        formula_qualification_ref=None,
        rounding_policy_id=case.config.rounding.policy_id,
        key_digest=case.row.key.digest(),
        value_identity=ValueIdentity.DERIVED,
        operands=(operand,),
        state=CalculationState.COMPUTED,
        value=fp.value,
        lower=Decimal("11999999999.66"),
        upper=Decimal("12000000000.34"),
        exact_value=exact,
        exact_interval=interval,
        effective_tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
    )
    value = case.row.source_values[0].model_copy(
        update={
            "interpretation_id": None,
            "calculation_trace_id": 701,
            "calculation_state": CalculationState.COMPUTED,
            "lower": trace.lower,
            "upper": trace.upper,
        }
    )
    row = case.row.model_copy(
        update={
            "value_identity": ValueIdentity.DERIVED,
            "row_id": row_id(case.row.key, ValueIdentity.DERIVED),
            "source_values": (value,),
        }
    )
    inputs = case.inputs.model_copy(
        update={"traces": (StoredTrace(trace_id=701, trace=trace, children=()),)}
    )
    rows = assembled(case, inputs=inputs, rows=(row,))
    assert len(rows) == 1  # An existing FP derived key is not a vendor-only key.
    assert rows[0].corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED
    assert rows[0].source_values[0].calculation_trace_id == 701
    draft = next(
        draft
        for draft in queue_drafts(rows, inputs=inputs, request=case.request, config=case.config)
        if draft.outcome == "ONE_SIDE_XBRL"
    )
    assert draft.evidence_interpretation_ids == (601,) and draft.evidence_occurrence_ids == (501,)
