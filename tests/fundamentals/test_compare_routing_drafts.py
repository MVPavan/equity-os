"""Pure routing payloads retain evidence while leaving store identity to queue SQL."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fundamentals.compare import routing
from fundamentals.compare.tables import PairResult, SourceQualifiedPair
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceRef,
    SourceRole,
    Triage,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import QueueSeverity

KEY = MeasurementKey(
    entity_id=1,
    canonical_id="revenue_from_operations",
    period=PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)),
    basis=Basis.CONSOLIDATED,
    framework=AccountingFramework.IND_AS,
    currency="INR",
    value_kind=ValueKind.CURRENCY_AMOUNT,
    dimensions=DimensionSet(),
)
LEFT = SourceRef(
    source_role=SourceRole.FIRST_PARTY,
    representation=Representation.XBRL,
    source_id="nse",
    surface="results_xbrl",
)
VENDOR = SourceRef(
    source_role=SourceRole.INDEPENDENT_VENDOR,
    representation=Representation.HTML,
    source_id="screener",
    surface="consolidated_quarters",
)
DIAGNOSTIC = SourceRef(
    source_role=SourceRole.DIAGNOSTIC,
    representation=Representation.JSON,
    source_id="upstox",
    surface="income_statement",
)
PAIR_ROUTES = (
    (
        PairKind.CORROBORATION,
        PairOutcome.MISMATCH,
        Triage.MAGNITUDE,
        QueueSeverity.HIGH,
        "MAPPING_DEFINITION_OR_SOURCE_ERROR",
    ),
    (
        PairKind.DIAGNOSTIC,
        PairOutcome.MISMATCH,
        Triage.STRUCTURAL,
        QueueSeverity.MEDIUM,
        "PARSE_CHECK_DISAGREE",
    ),
    (
        PairKind.DIAGNOSTIC,
        PairOutcome.ANOMALY,
        Triage.STRUCTURAL,
        QueueSeverity.MEDIUM,
        "PARSE_CHECK_DISAGREE",
    ),
    (
        PairKind.EXTRACTION,
        PairOutcome.MISMATCH,
        Triage.MAGNITUDE,
        QueueSeverity.HIGH,
        "EXTRACTION_DISAGREE",
    ),
    (
        PairKind.EXTRACTION,
        PairOutcome.ANOMALY,
        Triage.MAGNITUDE,
        QueueSeverity.HIGH,
        "EXTRACTION_DISAGREE",
    ),
    (
        PairKind.CORROBORATION,
        PairOutcome.ANOMALY,
        Triage.STRUCTURAL,
        QueueSeverity.HIGH,
        "SCALE_OR_SIGN_FAULT",
    ),
    (
        PairKind.CORROBORATION,
        PairOutcome.ANOMALY,
        Triage.MAGNITUDE,
        QueueSeverity.MEDIUM,
        "UNEXPLAINED_DIFFERENCE",
    ),
    (
        PairKind.CORROBORATION,
        PairOutcome.NOT_COMPARABLE,
        None,
        QueueSeverity.MEDIUM,
        "MAPPING_OR_PERIOD_DEFECT",
    ),
)


def pair(kind: PairKind, outcome: PairOutcome, triage: Triage | None) -> SourceQualifiedPair:
    right = DIAGNOSTIC if kind is PairKind.DIAGNOSTIC else VENDOR
    if kind is PairKind.EXTRACTION:
        right = SourceRef(
            source_role=SourceRole.REPORTED_COUNTERPART,
            representation=Representation.PDF,
            source_id="nse",
            surface="results_pdf",
        )
    return SourceQualifiedPair(
        pair_kind=kind,
        left=LEFT,
        right=right,
        result=PairResult(
            outcome=outcome,
            reason=ReasonCode.PERIOD_MISMATCH if outcome is PairOutcome.NOT_COMPARABLE else None,
            triage=triage,
            difference=Decimal("100"),
            interval_gap=Decimal("99"),
            definition_record_id=None,
        ),
        attempt_ids=(9, 4, 9),
        evidence_interpretation_ids=(6, 2, 6),
        evidence_occurrence_ids=(8, 3, 8),
    )


@pytest.mark.parametrize("kind,outcome,triage,severity,reason", PAIR_ROUTES)
def test_pair_draft_preserves_route_and_all_typed_evidence(
    kind: PairKind,
    outcome: PairOutcome,
    triage: Triage | None,
    severity: QueueSeverity,
    reason: str,
) -> None:
    source_pair = pair(kind, outcome, triage)
    draft = routing.route_pair_draft(source_pair, key=KEY)
    assert draft is not None
    assert draft.key == KEY
    assert draft.pair_identity == routing.pair_identity(
        source_pair.pair_kind, source_pair.left, source_pair.right
    )
    assert draft.outcome == outcome.value
    assert draft.severity is severity
    assert draft.routing_reason == reason
    assert draft.diagnostic is (kind is PairKind.DIAGNOSTIC)
    assert draft.reason_code == source_pair.result.reason
    assert draft.source_refs == (source_pair.left, source_pair.right)
    assert draft.attempt_ids == (4, 9)
    assert draft.evidence_interpretation_ids == (2, 6)
    assert draft.evidence_occurrence_ids == (3, 8)
    assert set(draft.model_dump(mode="json")) == {
        "key",
        "pair_identity",
        "outcome",
        "severity",
        "diagnostic",
        "routing_reason",
        "reason_code",
        "source_refs",
        "attempt_ids",
        "evidence_interpretation_ids",
        "evidence_occurrence_ids",
        "calculation_trace_ids",
    }


@pytest.mark.parametrize(
    "status,severity,reason",
    (
        (ExtractionStatus.DISAGREE, QueueSeverity.HIGH, "EXTRACTION_DISAGREE"),
        (ExtractionStatus.NOT_COMPARABLE, QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        (CorroborationStatus.NOT_COMPARABLE, QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        (ExtractionStatus.ONE_SIDE_XBRL, QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        (ExtractionStatus.ONE_SIDE_PDF, QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        (CorroborationStatus.VENDOR_ONLY, QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
        (CorroborationStatus.NO_SOURCE, QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
    ),
)
def test_status_draft_preserves_route_and_attempt_only_evidence(
    status: ExtractionStatus | CorroborationStatus,
    severity: QueueSeverity,
    reason: str,
) -> None:
    draft = routing.route_status_draft(
        status,
        key=KEY,
        reason_code=ReasonCode.UNREADABLE_CELL,
        source_refs=(LEFT, VENDOR),
        attempt_ids=(12, 3, 12),
    )
    assert draft is not None
    assert draft.pair_identity == f"status:{type(status).__name__}:{status.value}"
    assert draft.outcome == status.value
    assert draft.severity is severity
    assert draft.routing_reason == reason
    assert draft.reason_code is ReasonCode.UNREADABLE_CELL
    assert draft.diagnostic is False
    assert draft.source_refs == (LEFT, VENDOR)
    assert draft.attempt_ids == (3, 12)
    assert draft.evidence_interpretation_ids == ()
    assert draft.evidence_occurrence_ids == ()


def test_status_draft_preserves_interpretation_and_occurrence_associations() -> None:
    draft = routing.route_status_draft(
        CorroborationStatus.NO_SOURCE,
        key=KEY,
        evidence_interpretation_ids=(11, 2, 11),
        evidence_occurrence_ids=(19, 4, 19),
    )
    assert draft is not None
    assert draft.attempt_ids == ()
    assert draft.evidence_interpretation_ids == (2, 11)
    assert draft.evidence_occurrence_ids == (4, 19)


@pytest.mark.parametrize("source_ref", (LEFT, DIAGNOSTIC))
def test_unmapped_draft_names_actual_occurrence_without_inventing_key(
    source_ref: SourceRef,
) -> None:
    draft = routing.route_unmapped_occurrence_draft(occurrence_id=23, source_ref=source_ref)
    assert draft.key is None
    assert draft.outcome == "UNMAPPED"
    assert draft.severity is QueueSeverity.LOW
    assert draft.diagnostic is (source_ref.source_role is SourceRole.DIAGNOSTIC)
    assert draft.routing_reason == "FOLDING_OR_MAPPING_GAP"
    assert draft.source_refs == (source_ref,)
    assert draft.evidence_occurrence_ids == (23,)


def test_routed_drafts_refuse_empty_evidence() -> None:
    source_pair = pair(PairKind.CORROBORATION, PairOutcome.MISMATCH, Triage.MAGNITUDE).model_copy(
        update={"attempt_ids": (), "evidence_interpretation_ids": (), "evidence_occurrence_ids": ()}
    )
    with pytest.raises(ValidationError, match="at least one typed evidence id"):
        routing.route_pair_draft(source_pair, key=KEY)
    with pytest.raises(ValidationError, match="at least one typed evidence id"):
        routing.route_status_draft(CorroborationStatus.NO_SOURCE, key=KEY, source_refs=(LEFT,))


@pytest.mark.parametrize("invalid_id", (0, -1))
def test_drafts_refuse_invalid_typed_ids_instead_of_silently_dropping_them(invalid_id: int) -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        routing.route_status_draft(
            CorroborationStatus.NO_SOURCE, key=KEY, attempt_ids=(invalid_id,)
        )
    with pytest.raises(ValidationError, match="greater than 0"):
        routing.route_unmapped_occurrence_draft(occurrence_id=invalid_id, source_ref=LEFT)


@pytest.mark.parametrize(
    "outcome", (PairOutcome.AGREE, PairOutcome.AGREE_UNQUALIFIED, PairOutcome.DEFINITION_DIFFERENCE)
)
def test_agreeing_and_explained_pairs_create_no_draft(outcome: PairOutcome) -> None:
    source_pair = pair(PairKind.CORROBORATION, outcome, None).model_copy(
        update={"attempt_ids": (), "evidence_interpretation_ids": (), "evidence_occurrence_ids": ()}
    )
    assert routing.route_pair_draft(source_pair, key=KEY) is None


@pytest.mark.parametrize(
    "status",
    (
        ExtractionStatus.UNAVAILABLE,
        ExtractionStatus.AGREE,
        CorroborationStatus.UNAVAILABLE,
        CorroborationStatus.FILING_ONLY,
    ),
)
def test_unavailability_and_nonproblematic_statuses_create_no_draft(
    status: ExtractionStatus | CorroborationStatus,
) -> None:
    assert routing.route_status_draft(status, key=KEY) is None
