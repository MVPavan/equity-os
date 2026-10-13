"""Pure append-only queue proposals, independent of the final cell status (data spec §5).

Persistence supplies the store clock and item identity. Operational unavailability has no
cell queue proposal; callers retain it in the run's failure evidence.
"""

from __future__ import annotations

from datetime import datetime

from fundamentals.compare.tables import SourceQualifiedPair
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
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.review_queue import QueueItem, QueueSeverity
from fundamentals.contracts.snapshot import canonical_sha256


def pair_identity(pair: SourceQualifiedPair) -> str:
    """The ordered pair of actual source/surface references, independent of its outcome."""
    return canonical_sha256(
        {
            "kind": pair.pair_kind.value,
            "left": pair.left.model_dump(mode="json"),
            "right": pair.right.model_dump(mode="json"),
        }
    )


def route_pair(
    pair: SourceQualifiedPair,
    *,
    run_id: int,
    key: MeasurementKey,
    input_sha256: str,
    recorded_at: datetime | None = None,
) -> QueueItem | None:
    """Route every problematic pair, even when another pair corroborates the cell.

    Diagnostic mismatch/anomaly precedes all structural and extraction routes. A diagnostic
    internal conflict is already NOT_COMPARABLE from the refusal-first financial pair table.
    """
    outcome = pair.result.outcome
    diagnostic = pair.pair_kind is PairKind.DIAGNOSTIC
    route: tuple[QueueSeverity, str] | None = None
    if diagnostic and outcome in (PairOutcome.MISMATCH, PairOutcome.ANOMALY):
        route = QueueSeverity.MEDIUM, "PARSE_CHECK_DISAGREE"
    elif outcome is PairOutcome.NOT_COMPARABLE:
        route = QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"
    elif pair.pair_kind is PairKind.EXTRACTION and outcome in (
        PairOutcome.MISMATCH,
        PairOutcome.ANOMALY,
    ):
        route = QueueSeverity.HIGH, "EXTRACTION_DISAGREE"
    elif outcome is PairOutcome.MISMATCH:
        route = QueueSeverity.HIGH, "MAPPING_DEFINITION_OR_SOURCE_ERROR"
    elif outcome is PairOutcome.ANOMALY:
        if pair.result.triage is Triage.STRUCTURAL:
            route = QueueSeverity.HIGH, "SCALE_OR_SIGN_FAULT"
        elif pair.result.triage is Triage.MAGNITUDE:
            route = QueueSeverity.MEDIUM, "UNEXPLAINED_DIFFERENCE"
    if route is None:
        return None
    severity, reason = route
    return QueueItem(
        run_id=run_id,
        key=key,
        pair_identity=pair_identity(pair),
        outcome=outcome.value,
        input_sha256=input_sha256,
        severity=severity,
        diagnostic=diagnostic,
        routing_reason=reason,
        reason_code=pair.result.reason,
        source_refs=(pair.left, pair.right),
        attempt_ids=pair.attempt_ids,
        evidence_interpretation_ids=pair.evidence_interpretation_ids,
        evidence_occurrence_ids=pair.evidence_occurrence_ids,
        recorded_at=recorded_at,
    )


def route_status(
    status: ExtractionStatus | CorroborationStatus,
    *,
    run_id: int,
    key: MeasurementKey,
    input_sha256: str,
    reason_code: ReasonCode | None = None,
    source_refs: tuple[SourceRef, ...] = (),
    attempt_ids: tuple[int, ...] = (),
    evidence_interpretation_ids: tuple[int, ...] = (),
    evidence_occurrence_ids: tuple[int, ...] = (),
    recorded_at: datetime | None = None,
) -> QueueItem | None:
    """Routes with no numeric pair; aggregate conflicts are routed through their pairs."""
    routes = {
        ExtractionStatus.DISAGREE: (QueueSeverity.HIGH, "EXTRACTION_DISAGREE"),
        ExtractionStatus.NOT_COMPARABLE: (QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        CorroborationStatus.NOT_COMPARABLE: (QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        ExtractionStatus.ONE_SIDE_XBRL: (QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        ExtractionStatus.ONE_SIDE_PDF: (QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        CorroborationStatus.VENDOR_ONLY: (QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
        CorroborationStatus.NO_SOURCE: (QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
    }
    route = routes.get(status)
    if route is None:
        return None
    severity, reason = route
    return QueueItem(
        run_id=run_id,
        key=key,
        pair_identity=f"status:{type(status).__name__}:{status.value}",
        outcome=status.value,
        input_sha256=input_sha256,
        severity=severity,
        diagnostic=False,
        routing_reason=reason,
        reason_code=reason_code,
        source_refs=source_refs,
        attempt_ids=attempt_ids,
        evidence_interpretation_ids=evidence_interpretation_ids,
        evidence_occurrence_ids=evidence_occurrence_ids,
        recorded_at=recorded_at,
    )


def route_unmapped_occurrence(
    *,
    run_id: int,
    occurrence_id: int,
    source_ref: SourceRef,
    input_sha256: str,
    recorded_at: datetime | None = None,
) -> QueueItem:
    """Dictionary-addition candidate with actual occurrence evidence and no invented key."""
    return QueueItem(
        run_id=run_id,
        key=None,
        pair_identity=f"occurrence:{occurrence_id}:{canonical_sha256(source_ref.model_dump(mode='json'))}",
        outcome="UNMAPPED",
        input_sha256=input_sha256,
        severity=QueueSeverity.LOW,
        diagnostic=source_ref.source_role is SourceRole.DIAGNOSTIC,
        routing_reason="FOLDING_OR_MAPPING_GAP",
        source_refs=(source_ref,),
        evidence_occurrence_ids=(occurrence_id,),
        recorded_at=recorded_at,
    )
