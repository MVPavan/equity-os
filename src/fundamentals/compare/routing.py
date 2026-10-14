"""Pure append-only queue proposals, independent of the final cell status (data spec §5).

Persistence supplies the store clock and item identity. Operational unavailability has no
cell queue proposal; callers retain it in the run's failure evidence.
"""

from __future__ import annotations

from collections.abc import Sequence

from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_models import (
    ResultRow,
    RunInputDisposition,
    RunInputKind,
    SourceValue,
)
from fundamentals.compare.tables import PairResult, SourceQualifiedPair
from fundamentals.contracts.canonical import ApplicabilityStatus, Representation
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
from fundamentals.contracts.evidence import InterpretationStatus, PinnedVersions
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.review_queue import UNMAPPED, QueueItemDraft, QueueSeverity
from fundamentals.contracts.snapshot import canonical_sha256


def route_run(
    inputs: ResolvedInputs, rows: Sequence[ResultRow], pinned: PinnedVersions
) -> tuple[QueueItemDraft, ...]:
    """Every draft of one run: each applicable row's routes, then each ``UNMAPPED`` occurrence
    of a selected capture interpreted under the run's pins.

    A side without an interpretation or attempt (``NO_VALUE`` from a complete capture, or a
    calculation) is evidenced by the run's attempts.
    """
    run_attempts = tuple(
        sorted({item.attempt_id for item in inputs.attempts if item.attempt_id is not None})
    )
    drafts = [
        draft
        for row in rows
        if row.applicability is not ApplicabilityStatus.NOT_APPLICABLE
        for draft in _row_drafts(row, run_attempts)
    ]
    selected = {
        item.ref_id
        for item in inputs.inputs
        if item.kind is RunInputKind.CAPTURE_REF
        and item.disposition is RunInputDisposition.SELECTED
    }
    extractors = {
        Representation.XBRL: pinned.extractor_xbrl.version,
        Representation.PDF: pinned.extractor_pdf.version,
    }
    drafts.extend(
        route_unmapped_occurrence_draft(
            occurrence_id=item.occurrence_id,
            source_ref=SourceRef(
                source_role=SourceRole.FIRST_PARTY, representation=item.representation
            ),
        )
        for item in inputs.interpretations
        if item.status is InterpretationStatus.UNMAPPED
        and item.occurrence_id is not None
        and item.capture_ref_id in selected
        and (item.mapping_set_version, item.normalisation_policy_version, item.extractor_version)
        == (
            pinned.mapping_set.version,
            pinned.normalisation_policy.version,
            extractors.get(item.representation),
        )
    )
    return tuple(drafts)


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


def _row_drafts(row: ResultRow, run_attempts: tuple[int, ...]) -> list[QueueItemDraft]:
    """Extraction by its status, every other pair on its own, then the corroboration status
    unless its ``NOT_COMPARABLE`` is already carried by a pair."""
    values = {_ref(value): value for value in row.source_values}

    def evidence(sides: Sequence[SourceValue]) -> tuple[tuple[int, ...], tuple[int, ...]]:
        interpretations = sorted({s.interpretation_id for s in sides if s.interpretation_id})
        attempts = sorted({s.attempt_id for s in sides if s.attempt_id})
        return tuple(interpretations), tuple(attempts) or (() if interpretations else run_attempts)

    first_party = [v for v in row.source_values if v.source_role is SourceRole.FIRST_PARTY]
    interpretations, attempts = evidence(first_party)
    found = [
        route_status_draft(
            row.extraction_status,
            key=row.key,
            reason_code=row.extraction_reason,
            source_refs=tuple(_ref(value) for value in first_party),
            evidence_interpretation_ids=interpretations,
            attempt_ids=attempts,
        )
    ]
    pairs = [pair for pair in row.pairs if pair.pair_kind is not PairKind.EXTRACTION]
    for pair in pairs:
        interpretations, attempts = evidence([values[pair.left], values[pair.right]])
        qualified = SourceQualifiedPair(
            pair_kind=pair.pair_kind,
            left=pair.left,
            right=pair.right,
            result=PairResult.model_validate(pair.model_dump(include=set(PairResult.model_fields))),
            evidence_interpretation_ids=interpretations,
            attempt_ids=attempts,
        )
        found.append(route_pair_draft(qualified, key=row.key))
    if not (row.corroboration_status is CorroborationStatus.NOT_COMPARABLE and pairs):
        interpretations, attempts = evidence(row.source_values)
        found.append(
            route_status_draft(
                row.corroboration_status,
                key=row.key,
                reason_code=row.corroboration_reason,
                source_refs=tuple(values),
                evidence_interpretation_ids=interpretations,
                attempt_ids=attempts,
            )
        )
    return [draft for draft in found if draft is not None]


def _ref(value: SourceRef) -> SourceRef:
    """A source value's plain reference."""
    return SourceRef.model_validate(value.model_dump(include=set(SourceRef.model_fields)))


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
