"""Pure append-only queue proposals, independent of the final cell status (data spec §5).

Persistence supplies the store clock and item identity. Operational unavailability has no
cell queue proposal; callers retain it in the run's failure evidence.
"""

from __future__ import annotations

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
from fundamentals.contracts.review_queue import UNMAPPED, QueueItemDraft, QueueSeverity
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


def route_pair_draft(pair: SourceQualifiedPair, *, key: MeasurementKey) -> QueueItemDraft | None:
    """Route a problematic pair with exact evidence, leaving identity and clocks to SQL."""
    route = _pair_route(pair)
    if route is None:
        return None
    severity, reason = route
    return QueueItemDraft(
        key=key,
        pair_identity=pair_identity(pair),
        outcome=pair.result.outcome.value,
        severity=severity,
        diagnostic=pair.pair_kind is PairKind.DIAGNOSTIC,
        routing_reason=reason,
        reason_code=pair.result.reason,
        source_refs=(pair.left, pair.right),
        attempt_ids=tuple(sorted(set(pair.attempt_ids))),
        evidence_interpretation_ids=tuple(sorted(set(pair.evidence_interpretation_ids))),
        evidence_occurrence_ids=tuple(sorted(set(pair.evidence_occurrence_ids))),
    )


def route_status_draft(
    status: ExtractionStatus | CorroborationStatus,
    *,
    key: MeasurementKey,
    reason_code: ReasonCode | None = None,
    source_refs: tuple[SourceRef, ...] = (),
    attempt_ids: tuple[int, ...] = (),
    evidence_interpretation_ids: tuple[int, ...] = (),
    evidence_occurrence_ids: tuple[int, ...] = (),
) -> QueueItemDraft | None:
    """Route an evidenced nonnumeric status without a caller-supplied store identity."""
    route = _status_route(status)
    if route is None:
        return None
    severity, reason = route
    return QueueItemDraft(
        key=key,
        pair_identity=f"status:{type(status).__name__}:{status.value}",
        outcome=status.value,
        severity=severity,
        diagnostic=False,
        routing_reason=reason,
        reason_code=reason_code,
        source_refs=source_refs,
        attempt_ids=tuple(sorted(set(attempt_ids))),
        evidence_interpretation_ids=tuple(sorted(set(evidence_interpretation_ids))),
        evidence_occurrence_ids=tuple(sorted(set(evidence_occurrence_ids))),
    )


def route_unmapped_occurrence_draft(*, occurrence_id: int, source_ref: SourceRef) -> QueueItemDraft:
    """Propose a dictionary addition with its actual occurrence and no invented key."""
    return QueueItemDraft(
        key=None,
        pair_identity=f"occurrence:{occurrence_id}:{canonical_sha256(source_ref.model_dump(mode='json'))}",
        outcome=UNMAPPED,
        severity=QueueSeverity.LOW,
        diagnostic=source_ref.source_role is SourceRole.DIAGNOSTIC,
        routing_reason="FOLDING_OR_MAPPING_GAP",
        source_refs=(source_ref,),
        evidence_occurrence_ids=(occurrence_id,),
    )


def _pair_route(pair: SourceQualifiedPair) -> tuple[QueueSeverity, str] | None:
    """The pair-route precedence: diagnostic disagreement first, then generic rows."""
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
    return route


def _status_route(
    status: ExtractionStatus | CorroborationStatus,
) -> tuple[QueueSeverity, str] | None:
    """The status routes; unavailability remains run failure evidence."""
    routes = {
        ExtractionStatus.DISAGREE: (QueueSeverity.HIGH, "EXTRACTION_DISAGREE"),
        ExtractionStatus.NOT_COMPARABLE: (QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        CorroborationStatus.NOT_COMPARABLE: (QueueSeverity.MEDIUM, "MAPPING_OR_PERIOD_DEFECT"),
        ExtractionStatus.ONE_SIDE_XBRL: (QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        ExtractionStatus.ONE_SIDE_PDF: (QueueSeverity.LOW, "FOLDING_OR_MAPPING_GAP"),
        CorroborationStatus.VENDOR_ONLY: (QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
        CorroborationStatus.NO_SOURCE: (QueueSeverity.MEDIUM, "ALTERNATE_READ_REQUIRED"),
    }
    return routes.get(status)
