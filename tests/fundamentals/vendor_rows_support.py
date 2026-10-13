"""Shared synthetic witnesses for the public vendor-row mechanism tests."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_compare_vendor_inputs import NOW, QUARTER, arguments, fixture

from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import (
    DatabaseIdentity,
    ResultRow,
    RunRequest,
    RunScope,
    SourceValue,
    VendorSurfaceRequest,
    row_id,
)
from fundamentals.compare.vendor_inputs import compose_vendor_generation
from fundamentals.compare.vendor_rows import attach_vendor_rows
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    ValueIdentity,
)
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    FilingFamily,
    FilingPackage,
    Interpretation,
    KnowledgeTimeStatus,
    Occurrence,
    PackageMember,
    RunMode,
    exact_decimal,
)
from fundamentals.contracts.qualification import QualificationContext
from fundamentals.evidence.interpret import interpret
from fundamentals.evidence.repository import BasisStatusRecord
from fundamentals.evidence.selection import period_end


@dataclass(frozen=True)
class Case:
    config: LoadedConfig
    request: RunRequest
    inputs: ResolvedInputs
    row: ResultRow
    declaration: VendorSurfaceRequest
    vendor: Interpretation
    occurrence: Occurrence


@pytest.fixture
def case(tmp_path: Path) -> Case:
    setup = fixture(tmp_path)
    config, declaration, context, repository = setup[2:]
    generation = compose_vendor_generation(**arguments(setup))
    native = next(
        row
        for row in generation.occurrences
        if row.native_field == "Sales" and row.period == QUARTER
    )
    native = native.model_copy(update={"occurrence_id": 101})
    qualification = QualificationContext(
        schema_identity=declaration.schema_identity,
        surface=declaration.surface,
        basis=declaration.basis,
        period_kind=declaration.period.kind(context.binding.fiscal_year_end_month),
        proven={},
    )
    vendor = interpret(
        native,
        entity_id=1,
        basis=Basis.CONSOLIDATED,
        framework=declaration.framework,
        mapping_set=config.mapping_set,
        policy=config.normalisation_policy,
        dictionary=config.dictionary,
        fiscal_year_end_month=3,
        qualification=qualification,
        recorded_at=NOW,
    ).model_copy(update={"interpretation_id": 201})
    assert vendor.key is not None and vendor.value == Decimal("12000000000")
    fp_capture = CaptureReference(
        capture_ref_id=10,
        source_id="nse",
        surface="NSE_XBRL_INSTANCE",
        request_key="synthetic-first-party-quarter",
        capture_id="marked-fp",
        blob_sha256="1" * 64,
        record_sha256="2" * 64,
        registered_at=NOW,
        first_seen_at=NOW,
    )
    fp_occurrence = native.model_copy(
        update={
            "occurrence_id": 501,
            "capture": fp_capture,
            "representation": Representation.XBRL,
            "extractor_version": config.pinned.extractor_xbrl.version,
        }
    )
    fp_interpretation = vendor.model_copy(
        update={
            "interpretation_id": 601,
            "occurrence_id": 501,
            "capture_ref_id": 10,
            "representation": Representation.XBRL,
            "extractor_version": config.pinned.extractor_xbrl.version,
        }
    )
    package = FilingPackage(
        package_id=20,
        entity_id=1,
        family=FilingFamily.FINANCIAL_RESULTS,
        reporting_period_end=period_end(QUARTER),
        basis=Basis.CONSOLIDATED,
        framework=declaration.framework,
        reporting_kind=PeriodKind.QUARTER,
        knowledge_time=NOW,
        supersedes_package_id=None,
        replaced_statements=frozenset(),
        statements_present=frozenset({StatementFamily.PL}),
        evidence_sha256="3" * 64,
        members={
            Representation.XBRL: PackageMember(
                representation=Representation.XBRL,
                capture=fp_capture,
                knowledge_time=NOW,
                knowledge_time_raw=NOW.isoformat(),
                knowledge_time_status=KnowledgeTimeStatus.KNOWN,
            )
        },
    )
    attempts = tuple(
        row.model_copy(update={"attempt_id": 301 + index, "attempted_at": NOW})
        for index, row in enumerate(generation.attempts)
    )
    inputs = ResolvedInputs(
        capture_refs=(generation.capture, fp_capture),
        packages=(package,),
        occurrences=(native, fp_occurrence),
        interpretations=(vendor, fp_interpretation),
        attempts=attempts,
        settings=(repository.setting,),
        basis_statuses=(
            BasisStatusRecord(
                id=1,
                entity_id=1,
                basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
                evidence_input_id=1,
                recorded_at=NOW,
            ),
        ),
        definition_set_id=1,
    )
    value = SourceValue(
        source_role=SourceRole.FIRST_PARTY,
        representation=Representation.XBRL,
        state=SourceState.VALUE,
        reason=None,
        value=fp_interpretation.value,
        lower=exact_decimal(vendor.interval.lower),
        upper=exact_decimal(vendor.interval.upper),
        interpretation_id=601,
        calculation_trace_id=None,
        attempt_id=None,
        calculation_state=None,
    )
    dictionary_row = config.dictionary.row(vendor.key.canonical_id)
    row = ResultRow(
        row_id=row_id(vendor.key, ValueIdentity.REPORTED),
        key=vendor.key,
        dictionary_version=config.dictionary.version,
        value_identity=ValueIdentity.REPORTED,
        applicability=ApplicabilityStatus.APPLICABLE,
        applicability_rule_id=dictionary_row.applicability_rule_id,
        extraction_status=ExtractionStatus.ONE_SIDE_XBRL,
        extraction_reason=None,
        corroboration_status=CorroborationStatus.FILING_ONLY,
        corroboration_reason=None,
        source_values=(value,),
        pairs=(),
        surfaced_restatements=(),
    )
    request = RunRequest(
        scope=RunScope(
            entity_ids=(1,),
            period_ends=(period_end(QUARTER),),
            bases=(Basis.CONSOLIDATED,),
            sources=("NSE_XBRL_INSTANCE",),
            vendor_sources=(declaration,),
        ),
        cutoff=NOW + timedelta(minutes=10),
        mode=RunMode.AS_KNOWN,
        pinned=config.pinned,
        code_version="marked-pure-fixture",
        database_identity=DatabaseIdentity(host="fixture", port=5432, name="eqos_test_pure"),
    )
    return Case(config, request, inputs, row, declaration, vendor, native)


def assembled(
    case: Case,
    *,
    inputs: ResolvedInputs | None = None,
    config: LoadedConfig | None = None,
    rows: tuple[ResultRow, ...] | None = None,
) -> tuple[ResultRow, ...]:
    chosen_config = config or case.config
    request = case.request.model_copy(update={"pinned": chosen_config.pinned})
    return attach_vendor_rows(
        (case.row,) if rows is None else rows,
        inputs=inputs or case.inputs,
        request=request,
        config=chosen_config,
    )


def vendor_value(rows: tuple[ResultRow, ...]) -> SourceValue:
    return next(
        value
        for row in rows
        if row.key.canonical_id == "revenue_from_operations"
        for value in row.source_values
        if value.source_role in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)
    )


def later(
    case: Case,
    *,
    outcome: ExtractionOutcome,
    logical: str | None = None,
    exact_request: str | None = None,
    capture: CaptureReference | None = None,
    stage: AttemptStage = AttemptStage.ACQUISITION,
) -> AcquisitionAttempt:
    return case.inputs.attempts[0].model_copy(
        update={
            "attempt_id": 901,
            "stage": stage,
            "outcome": outcome,
            "reason": "marked newer store outcome",
            "capture": capture,
            "input_sha256": exact_request or "9" * 64,
            "extraction_context_sha256": logical or case.declaration.expected_logical_scope_sha256,
            "attempted_at": NOW + timedelta(minutes=1),
        }
    )
