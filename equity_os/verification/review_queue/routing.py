"""Pure append-only queue proposals, independent of the final cell status (data spec §5).

Persistence supplies the store clock and item identity. Operational unavailability has no
cell queue proposal; callers retain it in the run's failure evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from equity_os.contracts.measurement.canonical import ApplicabilityStatus, Representation
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationStatus,
    PinnedVersions,
)
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.sourcing.snapshot import canonical_sha256
from equity_os.contracts.sourcing.source_catalog import surface_authority
from equity_os.contracts.verification.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceRef,
    SourceRole,
    Triage,
)
from equity_os.contracts.verification.review_queue import UNMAPPED, QueueItemDraft, QueueSeverity
from equity_os.storage.records.repository_calc import StoredTrace
from equity_os.verification.comparison.resolve_models import ResolvedInputs
from equity_os.verification.comparison.run_models import (
    ResultRow,
    RunInputDisposition,
    RunInputKind,
    SourceValue,
)
from equity_os.verification.comparison.selection import (
    INTERPRETATION_AMBIGUOUS,
    current_interpretations,
    matches_key,
)
from equity_os.verification.comparison.tables import PairResult, SourceQualifiedPair


def route_run(
    inputs: ResolvedInputs, rows: Sequence[ResultRow], pinned: PinnedVersions
) -> tuple[QueueItemDraft, ...]:
    """Every draft of one run: each applicable row's routes, then each ``UNMAPPED`` first-party
    occurrence and vendor native row of a selected capture interpreted under the run's pins.

    A side without an interpretation or attempt (``NO_VALUE`` from a complete capture, or a
    calculation) is evidenced by the run's attempts. A calculation also names its trace and
    every operand interpretation, and an ambiguous side every candidate, so changed inputs
    hash to a new item.
    """
    run_attempts = tuple(
        sorted({item.attempt_id for item in inputs.attempts if item.attempt_id is not None})
    )
    evidence = _Evidence(inputs, run_attempts)
    drafts = [
        draft
        for row in rows
        if row.applicability is not ApplicabilityStatus.NOT_APPLICABLE
        for draft in _row_drafts(row, evidence)
    ]
    selected = {
        item.ref_id
        for item in inputs.inputs
        if item.kind is RunInputKind.CAPTURE_REF
        and item.disposition is RunInputDisposition.SELECTED
    }
    occurrences = {item.occurrence_id: item for item in inputs.occurrences}
    triple = pinned.triple()

    def under_pins(item: Interpretation) -> bool:
        capture = occurrences[item.occurrence_id].capture
        extractor = triple.extractor(
            item.representation, source_id=capture.source_id, surface=capture.surface
        )
        return (
            item.mapping_set_version,
            item.normalisation_policy_version,
            item.extractor_version,
        ) == (triple.mapping_set, triple.normalisation_policy, extractor)

    generation = [
        item
        for item in inputs.interpretations
        if item.occurrence_id in occurrences
        and item.capture_ref_id in selected
        and under_pins(item)
    ]
    queued: dict[str, list[int]] = defaultdict(list)
    refs: dict[str, SourceRef] = {}
    for item in current_interpretations(generation):
        if item.status is not InterpretationStatus.UNMAPPED or item.occurrence_id is None:
            continue
        capture = occurrences[item.occurrence_id].capture
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


def pair_identity(pair_kind: PairKind, left: SourceRef, right: SourceRef) -> str:
    """The ordered pair of actual source/surface references, independent of its outcome; the
    queue item and the stored pair outcome both carry it (plan D11)."""
    return canonical_sha256(
        {
            "kind": pair_kind.value,
            "left": left.model_dump(mode="json"),
            "right": right.model_dump(mode="json"),
        }
    )


def route_pair_draft(
    pair: SourceQualifiedPair, *, key: MeasurementKey, calculation_trace_ids: tuple[int, ...] = ()
) -> QueueItemDraft | None:
    """Route a problematic pair with exact evidence, leaving identity and clocks to SQL."""
    route = _pair_route(pair)
    if route is None:
        return None
    severity, reason = route
    return QueueItemDraft(
        key=key,
        pair_identity=pair_identity(pair.pair_kind, pair.left, pair.right),
        outcome=pair.result.outcome.value,
        severity=severity,
        diagnostic=pair.pair_kind is PairKind.DIAGNOSTIC,
        routing_reason=reason,
        reason_code=pair.result.reason,
        source_refs=(pair.left, pair.right),
        attempt_ids=tuple(sorted(set(pair.attempt_ids))),
        evidence_interpretation_ids=tuple(sorted(set(pair.evidence_interpretation_ids))),
        evidence_occurrence_ids=tuple(sorted(set(pair.evidence_occurrence_ids))),
        calculation_trace_ids=calculation_trace_ids,
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
    calculation_trace_ids: tuple[int, ...] = (),
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
        calculation_trace_ids=calculation_trace_ids,
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


class _Evidence:
    """The typed evidence ids of a row's sides, from the run's own loaded inputs."""

    def __init__(self, inputs: ResolvedInputs, run_attempts: tuple[int, ...]) -> None:
        self._run_attempts = run_attempts
        self._interpretations = inputs.interpretations
        self._surface = {
            item.capture_ref_id: (item.source_id, item.surface) for item in inputs.capture_refs
        }
        self._traces: dict[int, StoredTrace] = {}
        pending = list(inputs.traces)
        while pending:
            stored = pending.pop()
            self._traces[stored.trace_id] = stored
            pending.extend(stored.children)

    def of(self, key: MeasurementKey, sides: Sequence[SourceValue]) -> dict[str, tuple[int, ...]]:
        """Interpretations (selected, trace operands, ambiguous candidates), attempts, traces."""
        traces = {s.calculation_trace_id for s in sides if s.calculation_trace_id}
        interpretations = {s.interpretation_id for s in sides if s.interpretation_id}
        interpretations |= {
            item
            for trace in traces
            if trace in self._traces
            for item in _operands(self._traces[trace])
        }
        for side in sides:
            if side.interpretation_id is None and side.reason == INTERPRETATION_AMBIGUOUS:
                interpretations |= self._candidates(key, side)
        attempts = sorted({s.attempt_id for s in sides if s.attempt_id})
        return {
            "evidence_interpretation_ids": tuple(sorted(interpretations)),
            "attempt_ids": tuple(attempts) or (() if interpretations else self._run_attempts),
            "calculation_trace_ids": tuple(sorted(traces)),
        }

    def _candidates(self, key: MeasurementKey, side: SourceValue) -> set[int]:
        """Every loaded interpretation of the key in the side's representation and surface."""
        surface = (side.source_id, (side.surface or "").split(":")[0])
        return {
            item.interpretation_id
            for item in self._interpretations
            if item.interpretation_id is not None
            and item.representation is side.representation
            and matches_key(item, key)
            and (side.source_id is None or self._surface.get(item.capture_ref_id) == surface)
        }


def _operands(stored: StoredTrace) -> set[int]:
    """A trace's operand interpretations, its children's included."""
    own = {item.interpretation_id for item in stored.trace.operands if item.interpretation_id}
    return own.union(*(_operands(child) for child in stored.children))


def _row_drafts(row: ResultRow, evidence: _Evidence) -> list[QueueItemDraft]:
    """Extraction by its status, every other pair on its own, then the corroboration status
    unless its ``NOT_COMPARABLE`` is already carried by a pair."""
    values = {_ref(value): value for value in row.source_values}
    first_party = [v for v in row.source_values if v.source_role is SourceRole.FIRST_PARTY]
    found = [
        route_status_draft(
            row.extraction_status,
            key=row.key,
            reason_code=row.extraction_reason,
            source_refs=tuple(_ref(value) for value in first_party),
            **evidence.of(row.key, first_party),
        )
    ]
    pairs = [pair for pair in row.pairs if pair.pair_kind is not PairKind.EXTRACTION]
    for pair in pairs:
        ids = evidence.of(row.key, [values[pair.left], values[pair.right]])
        qualified = SourceQualifiedPair(
            pair_kind=pair.pair_kind,
            left=pair.left,
            right=pair.right,
            result=PairResult.model_validate(pair.model_dump(include=set(PairResult.model_fields))),
            evidence_interpretation_ids=ids["evidence_interpretation_ids"],
            attempt_ids=ids["attempt_ids"],
        )
        found.append(
            route_pair_draft(
                qualified, key=row.key, calculation_trace_ids=ids["calculation_trace_ids"]
            )
        )
    if not (row.corroboration_status is CorroborationStatus.NOT_COMPARABLE and pairs):
        found.append(
            route_status_draft(
                row.corroboration_status,
                key=row.key,
                reason_code=row.corroboration_reason,
                source_refs=tuple(values),
                **evidence.of(row.key, row.source_values),
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
