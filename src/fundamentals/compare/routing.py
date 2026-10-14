"""Pure append-only queue proposals, independent of the final cell status (data spec §5).

Persistence supplies the store clock and item identity. Operational unavailability has no
cell queue proposal; callers retain it in the run's failure evidence.
"""

from __future__ import annotations

from collections import defaultdict
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
from fundamentals.contracts.source_catalog import surface_authority


def route_run(
    inputs: ResolvedInputs, rows: Sequence[ResultRow], pinned: PinnedVersions
) -> tuple[QueueItemDraft, ...]:
    """Every draft of one run: each applicable row's routes, then each ``UNMAPPED`` first-party
    occurrence and vendor native row of a selected capture interpreted under the run's pins.

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
    occurrences = {item.occurrence_id: item for item in inputs.occurrences}
    triple = pinned.triple()
    queued: dict[str, list[int]] = defaultdict(list)
    refs: dict[str, SourceRef] = {}
    for item in inputs.interpretations:
        if (
            item.status is not InterpretationStatus.UNMAPPED
            or item.occurrence_id is None
            or item.capture_ref_id not in selected
        ):
            continue
        capture = occurrences[item.occurrence_id].capture
        pins = (
            triple.mapping_set,
            triple.normalisation_policy,
            triple.extractor(
                item.representation, source_id=capture.source_id, surface=capture.surface
            ),
        )
        if (
            item.mapping_set_version,
            item.normalisation_policy_version,
            item.extractor_version,
        ) != pins:
            continue
        if item.representation in (Representation.XBRL, Representation.PDF):
            identity = str(item.occurrence_id)
            ref = SourceRef(source_role=SourceRole.FIRST_PARTY, representation=item.representation)
        else:  # a vendor native row: its anchor without the column
            anchor = occurrences[item.occurrence_id].anchor
            row = {name: value for name, value in anchor.items() if name not in _COLUMN_FIELDS}
            identity = canonical_sha256({"capture": item.capture_ref_id, "row": row})
            authority = surface_authority(capture.source_id, capture.surface)
            ref = SourceRef(
                source_role=authority.role,
                representation=authority.representation,
                source_id=capture.source_id,
                surface=capture.surface,
            )
        queued[identity].append(item.occurrence_id)
        refs[identity] = ref
    drafts.extend(
        route_unmapped_occurrence_draft(
            occurrence_id=min(ids), source_ref=refs[identity], row_occurrence_ids=tuple(ids)
        )
        for identity, ids in queued.items()
    )
    return tuple(drafts)


_COLUMN_FIELDS = frozenset({"column_index", "column_label"})
"""Anchor fields that place a vendor cell in its row; the row without them is one native row."""


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


def route_unmapped_occurrence_draft(
    *, occurrence_id: int, source_ref: SourceRef, row_occurrence_ids: tuple[int, ...] = ()
) -> QueueItemDraft:
    """Propose a dictionary addition with its actual occurrence and no invented key; a vendor
    native row names its first occurrence and anchors every other column as evidence."""
    ids = tuple(sorted({occurrence_id, *row_occurrence_ids}))
    return QueueItemDraft(
        key=None,
        pair_identity=f"occurrence:{occurrence_id}:{canonical_sha256(source_ref.model_dump(mode='json'))}",
        outcome=UNMAPPED,
        severity=QueueSeverity.LOW,
        diagnostic=source_ref.source_role is SourceRole.DIAGNOSTIC,
        routing_reason="FOLDING_OR_MAPPING_GAP",
        source_refs=(source_ref,),
        evidence_occurrence_ids=ids,
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
    """The pair-route precedence: diagnostic disagreement first, then generic rows. A
    diagnostic disagreement is a parse check only against a diagnostic source (Upstox);
    between corroborating sources it routes nothing."""
    outcome = pair.result.outcome
    diagnostic = pair.pair_kind is PairKind.DIAGNOSTIC
    route: tuple[QueueSeverity, str] | None = None
    if diagnostic and outcome in (PairOutcome.MISMATCH, PairOutcome.ANOMALY):
        roles = {pair.left.source_role, pair.right.source_role}
        if SourceRole.DIAGNOSTIC in roles:
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
