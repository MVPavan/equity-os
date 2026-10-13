"""Exact recursive source provenance shared by pure vendor assembly and queue routing."""

from __future__ import annotations

from fundamentals.compare.engine_attempts import RunResolutionError, attempt_available
from fundamentals.compare.engine_rows import Cell, reason_codes, selected_side
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig, require_pins
from fundamentals.compare.run_models import (
    ResultRow,
    RunRequest,
    SourceValue,
)
from fundamentals.compare.tables import (
    ComparisonSide,
    SourceQualifiedSide,
)
from fundamentals.contracts.canonical import (
    Representation,
)
from fundamentals.contracts.comparison import (
    SelectionSource,
    SourceRef,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    CaptureReference,
    Interpretation,
    KeySelection,
    Occurrence,
    exact_decimal,
)
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.evidence.selection import _matches, period_end


class RowEvidence:
    def __init__(self, inputs: ResolvedInputs, request: RunRequest, config: LoadedConfig) -> None:
        require_pins(config, request.pinned)
        self.inputs, self.request, self.config = inputs, request, config
        self.interpretations: dict[int, Interpretation] = {}
        self.occurrences: dict[int, Occurrence] = {}
        self.captures: dict[int, CaptureReference] = {}
        for row in inputs.interpretations:
            if row.interpretation_id is None or row.interpretation_id in self.interpretations:
                raise RunResolutionError("closed interpretations require unique stored ids")
            self.interpretations[row.interpretation_id] = row
        for occurrence in inputs.occurrences:
            if occurrence.occurrence_id is None or occurrence.occurrence_id in self.occurrences:
                raise RunResolutionError("closed occurrences require unique stored ids")
            self.occurrences[occurrence.occurrence_id] = occurrence
        for capture in inputs.capture_refs:
            if capture.capture_ref_id is None or capture.capture_ref_id in self.captures:
                raise RunResolutionError("closed captures require unique stored ids")
            self.captures[capture.capture_ref_id] = capture
        self.traces: dict[int, StoredTrace] = {}
        for trace in inputs.traces:
            self._index_trace(trace)

    def _index_trace(self, stored: StoredTrace) -> None:
        previous = self.traces.setdefault(stored.trace_id, stored)
        if previous != stored:
            raise RunResolutionError("one trace id has conflicting closed input rows")
        for child in stored.children:
            self._index_trace(child)

    def _interpretation_closure(self, root_id: int | None) -> tuple[set[int], set[int]]:
        ids: set[int] = set()
        occurrences: set[int] = set()
        visiting: set[int] = set()

        def visit(ref_id: int) -> None:
            if ref_id in visiting:
                raise RunResolutionError("interpretation evidence closure contains a cycle")
            if ref_id in ids:
                return
            row = self.interpretations.get(ref_id)
            if row is None:
                raise RunResolutionError("interpretation evidence closure is not loaded by id")
            visiting.add(ref_id)
            if row.occurrence_id is not None:
                if row.occurrence_id not in self.occurrences:
                    raise RunResolutionError("interpretation occurrence is not loaded by id")
                occurrence = self.occurrences[row.occurrence_id]
                if (
                    occurrence.capture.capture_ref_id != row.capture_ref_id
                    or occurrence.representation is not row.representation
                    or occurrence.capture != self.captures.get(row.capture_ref_id)
                ):
                    raise RunResolutionError(
                        "interpretation occurrence disagrees with actual capture provenance"
                    )
                occurrences.add(row.occurrence_id)
            for child in (
                *row.operand_interpretation_ids,
                *(
                    ref
                    for proof in row.condition_evidence
                    for ref in proof.evidence_interpretation_ids
                ),
            ):
                visit(child)
            visiting.remove(ref_id)
            ids.add(ref_id)

        if root_id is not None:
            visit(root_id)
        return ids, occurrences

    def _trace_closure(self, trace_id: int) -> tuple[set[int], set[int]]:
        stored = self.traces.get(trace_id)
        if stored is None:
            raise RunResolutionError("selected calculation trace is not loaded by id")
        ids, occurrences = set(), set()
        for operand in stored.trace.operands:
            if operand.interpretation_id is not None:
                leaf_ids, leaf_occurrences = self._interpretation_closure(operand.interpretation_id)
                ids.update(leaf_ids)
                occurrences.update(leaf_occurrences)
            if operand.operand_trace_id is not None:
                leaf_ids, leaf_occurrences = self._trace_closure(operand.operand_trace_id)
                ids.update(leaf_ids)
                occurrences.update(leaf_occurrences)
            if operand.alignment_proof_id is not None:
                proofs = [
                    proof
                    for proof in self.inputs.proofs
                    if proof.proof_id == operand.alignment_proof_id
                ]
                if len(proofs) != 1:
                    raise RunResolutionError("trace alignment proof is not loaded exactly")
                for ref_id, _ in proofs[0].participants:
                    leaf_ids, leaf_occurrences = self._interpretation_closure(ref_id)
                    ids.update(leaf_ids)
                    occurrences.update(leaf_occurrences)
        return ids, occurrences

    def _fp_side(self, key: MeasurementKey, value: SourceValue) -> SourceQualifiedSide:
        ids: set[int] = set()
        occurrence_ids: set[int] = set()
        package_id = None
        chosen = (
            self.interpretations.get(value.interpretation_id)
            if value.interpretation_id is not None
            else None
        )
        if value.interpretation_id is not None:
            if (
                chosen is None
                or chosen.key != key
                or chosen.representation is not value.representation
            ):
                raise RunResolutionError(
                    "first-party selected interpretation does not match its row"
                )
            ids, occurrence_ids = self._interpretation_closure(value.interpretation_id)
            packages = [
                package.package_id
                for package in self.inputs.packages
                if any(
                    member.capture.capture_ref_id == chosen.capture_ref_id
                    for member in package.members.values()
                )
            ]
            if len(set(packages)) != 1:
                raise RunResolutionError(
                    "selected first-party interpretation lacks one actual package"
                )
            package_id = packages[0]
        elif value.calculation_trace_id is not None:
            ids, occurrence_ids = self._trace_closure(value.calculation_trace_id)
        elif value.state is SourceState.INVALID:
            for candidate in self.inputs.interpretations:
                if candidate.representation is value.representation and _matches(candidate, key):
                    leaf_ids, leaves = self._interpretation_closure(candidate.interpretation_id)
                    ids.update(leaf_ids)
                    occurrence_ids.update(leaves)
        identities = {
            (self.occurrences[ref].capture.source_id, self.occurrences[ref].capture.surface)
            for ref in occurrence_ids
            if self.occurrences[ref].representation is value.representation
        }
        if value.attempt_id is not None:
            attempts = [row for row in self.inputs.attempts if row.attempt_id == value.attempt_id]
            if len(attempts) != 1:
                raise RunResolutionError("first-party attempt is not loaded exactly")
            identities.add((attempts[0].source_id, attempts[0].surface))
        if not identities:
            identities = {
                (member.capture.source_id, member.capture.surface)
                for package in self.inputs.packages
                if (
                    package.entity_id,
                    package.basis,
                    package.framework,
                    package.reporting_period_end,
                )
                == (key.entity_id, key.basis, key.framework, period_end(key.period))
                for member in package.members.values()
                if member.representation is value.representation
            }
        if len(identities) > 1:
            raise RunResolutionError("first-party side mixes distinct actual source identities")
        source_id, surface = next(iter(identities)) if identities else (None, None)
        if value.source_id is not None and (value.source_id, value.surface) != (source_id, surface):
            raise RunResolutionError("first-party source value disagrees with its actual source")
        ref = SourceRef(
            source_role=value.source_role,
            representation=value.representation,
            source_id=source_id,
            surface=surface,
        )
        if value.calculation_trace_id is not None:
            trace = self.traces[value.calculation_trace_id].trace
            if trace.key_digest != key.digest():
                raise RunResolutionError("first-party selected trace does not match the row key")
            selected = ComparisonSide(
                key=key,
                state=value.state,
                value=trace.value if value.state is SourceState.VALUE else None,
                interval=trace.exact_interval if value.state is SourceState.VALUE else None,
                tier=trace.effective_tier,
                aligned_by_proof=False,
                mapping_entry_ids=tuple(
                    sorted(
                        {
                            entry
                            for ref_id in ids
                            if (entry := self.interpretations[ref_id].mapping_entry_id) is not None
                        }
                    )
                ),
                package_id=None,
                calculation_state=trace.state,
                reasons=reason_codes([value.reason]),
            )
        else:
            selected = selected_side(
                Cell(
                    selection=KeySelection(
                        key=key,
                        representation=value.representation,
                        state=value.state,
                        interpretation=chosen,
                        package_id=package_id,
                        source=SelectionSource.PACKAGE_AS_REPORTED,
                        reason=value.reason,
                        considered_interpretation_ids=tuple(sorted(ids)),
                        surfaced_restatements=(),
                    ),
                    attempt_id=value.attempt_id,
                ),
                value.representation,
                proofs=self.inputs.proofs,
                package_id=package_id,
                role=value.source_role,
            ).comparison
        if selected.value != value.value:
            raise RunResolutionError("first-party numeric value differs from its selected evidence")
        interval = selected.interval
        bounds = (
            (trace.lower, trace.upper)
            if value.calculation_trace_id is not None
            else (
                None if interval is None else exact_decimal(interval.lower),
                None if interval is None else exact_decimal(interval.upper),
            )
        )
        if bounds != (value.lower, value.upper):
            raise RunResolutionError("first-party interval differs from its selected evidence")
        ids = {
            ref_id
            for ref_id in ids
            if self._capture_matches_ref(
                self.captures.get(self.interpretations[ref_id].capture_ref_id),
                self.interpretations[ref_id].representation,
                ref,
            )
        }
        occurrence_ids = {
            ref_id
            for ref_id in occurrence_ids
            if self._capture_matches_ref(
                self.occurrences[ref_id].capture, self.occurrences[ref_id].representation, ref
            )
        }
        attempt_ids = {
            row.attempt_id
            for row in self.inputs.attempts
            if row.attempt_id is not None
            and row.representation is ref.representation
            and (
                ref.source_id is None
                or (row.source_id, row.surface) == (ref.source_id, ref.surface)
            )
            and (row.entity_id, row.basis, row.framework, row.period_end)
            == (key.entity_id, key.basis, key.framework, period_end(key.period))
            and row.statement_family in (None, self.config.dictionary.row(key.canonical_id).family)
            and (
                row.package_id == package_id
                if package_id is not None
                else row.capture is not None
                and any(
                    row.capture.capture_ref_id == member.capture.capture_ref_id
                    for package in self.inputs.packages
                    for member in package.members.values()
                )
            )
            and row.attempted_at is not None
            and attempt_available(
                row,
                cutoff=self.request.cutoff,
                mode=self.request.mode,
                extractor=self.request.pinned.triple().extractor(ref.representation),
            )
        }
        if value.attempt_id is not None:
            attempt_ids.add(value.attempt_id)
        return SourceQualifiedSide(
            ref=ref,
            side=selected,
            interpretation_ids=tuple(sorted(ids)),
            occurrence_ids=tuple(sorted(occurrence_ids)),
            attempt_ids=tuple(sorted(attempt_ids)),
        )

    @staticmethod
    def _capture_matches_ref(
        capture: CaptureReference | None, representation: Representation, ref: SourceRef
    ) -> bool:
        return (
            capture is not None
            and representation is ref.representation
            and (
                ref.source_id is None
                or (capture.source_id, capture.surface) == (ref.source_id, ref.surface)
            )
        )

    def _first_party(self, row: ResultRow) -> tuple[SourceQualifiedSide, tuple[SourceValue, ...]]:
        values = tuple(
            value
            for value in row.source_values
            if value.source_role not in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)
        )
        named = [(value, self._fp_side(row.key, value)) for value in values]
        values = tuple(
            value.model_copy(update={"source_id": side.ref.source_id, "surface": side.ref.surface})
            for value, side in named
        )
        sides = [side for _, side in named if side.ref.source_role is SourceRole.FIRST_PARTY]
        if not sides:
            raise RunResolutionError(
                "vendor corroboration row has no honest first-party representative"
            )
        order = {Representation.XBRL: 0, Representation.PDF: 1}
        sides.sort(key=lambda side: order[side.ref.representation])
        for state in (
            SourceState.VALUE,
            SourceState.UNAVAILABLE,
            SourceState.INVALID,
            SourceState.NO_VALUE,
        ):
            for side in sides:
                if side.side.state is state:
                    return side, values
        raise RunResolutionError("first-party representative has an unknown state")
