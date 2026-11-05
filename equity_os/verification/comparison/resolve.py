"""Per-run resolution: read the evidence a request may see, then recompute (D1a Task 9).

``resolve`` is the only place a run uses as-of and list reads. It loads, per (entity, basis,
period end), the eligible packages (and the same fiscal year's nine-month package when a
``YEAR`` package is present), their member captures' occurrences under the pinned extractor
and interpretations, the available attempts, the cutoff's fiscal calendar, basis status and
segment members, and every eligible comparative of the selected keys. Alignment proofs are
computed and stored (reused by content) before results; derived traces are stored as they
are evaluated. ``recompute`` is pure over the loaded inputs and is what replay calls.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.normalisation.derivation.derived import TraceStore
from equity_os.normalisation.derivation.formula import CalculationTrace
from equity_os.normalisation.mapping.alignment import AlignmentProof, prove_alignment
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.storage.records.repository_calc import StoredTrace
from equity_os.verification.comparison.engine import RunEngine
from equity_os.verification.comparison.resolve_loader import RunLoader
from equity_os.verification.comparison.resolve_models import ReplayReader, ResolvedInputs
from equity_os.verification.comparison.run_config import LoadedConfig
from equity_os.verification.comparison.run_models import (
    ResultRow,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunRequest,
    sorted_inputs,
)
from equity_os.verification.comparison.run_store import RunStore

__all__ = [
    "LoadedConfig",
    "ReplayMismatchError",
    "ReplayReader",
    "ResolvedInputs",
    "dispositions",
    "load_inputs",
    "recompute",
    "resolve",
]

_NO_TRACE = "replay evaluated a trace the run did not store (content {digest})"
_MISSING = "run input {kind} ids {ids} are not stored"
_NO_DEFINITION_SET = "a run names exactly one definition set, got {count}"


class ReplayMismatchError(RuntimeError):
    """Replay needed evidence the manifest does not name; it never reads beyond it."""


class ReplayTraces:
    """A read-only trace store over a run's own stored traces (children included)."""

    def __init__(self, traces: Sequence[StoredTrace]) -> None:
        self._ids: dict[str, int] = {}
        pending = list(traces)
        while pending:
            stored = pending.pop()
            self._ids[stored.trace.content_sha256()] = stored.trace_id
            pending.extend(stored.children)

    def put_calculation_trace(self, trace: CalculationTrace) -> int:
        """The stored id of an identical trace; anything else is a replay mismatch."""
        digest = trace.content_sha256()
        if digest not in self._ids:
            raise ReplayMismatchError(_NO_TRACE.format(digest=digest))
        return self._ids[digest]


class _RecordingTraces:
    """The repository's trace writes, remembering every id a run stored or reused."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository
        self.ids: set[int] = set()

    def put_calculation_trace(self, trace: CalculationTrace) -> int:
        """Store (or find) one trace and remember its id."""
        trace_id = self._repository.put_calculation_trace(trace)
        self.ids.add(trace_id)
        return trace_id


def recompute(
    inputs: ResolvedInputs,
    request: RunRequest,
    *,
    config: LoadedConfig,
    traces: TraceStore | None = None,
) -> tuple[ResultRow, ...]:
    """Result rows from loaded inputs alone; replay's traces come from the inputs."""
    store = traces if traces is not None else ReplayTraces(inputs.traces)
    return RunEngine(inputs, request, config=config, traces=store).rows()


def resolve(
    request: RunRequest,
    *,
    repository: EvidenceRepository,
    store: RunStore,
    config: LoadedConfig,
    definition_set_id: int,
) -> tuple[ResolvedInputs, tuple[ResultRow, ...]]:
    """Read the request's evidence, store proofs and traces, and compute its rows."""
    loader = RunLoader(request, repository)
    loader.load()
    base = loader.inputs(definition_set_id)
    probe = RunEngine(base, request, config=config, traces=ReplayTraces(()))
    loader.comparatives(store, probe.comparative_digests())
    base = loader.inputs(definition_set_id)
    selector = RunEngine(base, request, config=config, traces=ReplayTraces(()))
    proofs: list[AlignmentProof] = []
    for package, selections in selector.package_selections():
        proofs.extend(prove_alignment(package, selections, config.alignment_rules))
    stored_proofs = repository.put_alignment_proofs(proofs) if proofs else ()
    proven = base.model_copy(update={"proofs": tuple(stored_proofs)})
    recorder = _RecordingTraces(repository)
    engine = RunEngine(proven, request, config=config, traces=recorder)
    rows = engine.rows()
    traces = repository.get_calculation_traces(sorted(recorder.ids))
    complete = proven.model_copy(update={"traces": traces})
    inputs = dispositions(
        complete,
        rows,
        selected_packages=engine.selected_package_ids,
        definition_set_id=definition_set_id,
        sources=request.scope.sources,
        selected_interpretations=engine.selected_condition_ids,
        selected_captures=engine.selected_vendor_captures,
    )
    return complete.model_copy(update={"inputs": inputs}), rows


def load_inputs(reader: ReplayReader, inputs: Sequence[RunInput]) -> ResolvedInputs:
    """Reload a run's evidence by id through the replay reader only."""
    ids: dict[RunInputKind, list[int]] = {kind: [] for kind in RunInputKind}
    for item in inputs:
        ids[item.kind].append(item.ref_id)
    sets = ids[RunInputKind.DEFINITION_SET]
    if len(sets) != 1:
        raise ReplayMismatchError(_NO_DEFINITION_SET.format(count=len(sets)))
    loaded = ResolvedInputs(
        capture_refs=reader.get_capture_refs(ids[RunInputKind.CAPTURE_REF]),
        packages=reader.get_packages(ids[RunInputKind.PACKAGE]),
        package_statements=reader.get_package_statements(ids[RunInputKind.PACKAGE_STATEMENT]),
        occurrences=reader.get_occurrences(ids[RunInputKind.OCCURRENCE]),
        interpretations=reader.get_interpretations(ids[RunInputKind.INTERPRETATION]),
        attempts=reader.get_attempts(ids[RunInputKind.ATTEMPT]),
        proofs=reader.get_alignment_proofs(ids[RunInputKind.ALIGNMENT_PROOF]),
        traces=reader.get_calculation_traces(ids[RunInputKind.CALCULATION_TRACE]),
        evidence_inputs=reader.get_evidence_inputs(ids[RunInputKind.EVIDENCE_INPUT]),
        settings=reader.get_settings_records(ids[RunInputKind.SETTINGS_RECORD]),
        basis_statuses=reader.get_basis_statuses(ids[RunInputKind.BASIS_STATUS]),
        segment_members=reader.get_segment_members(ids[RunInputKind.SEGMENT_MEMBER]),
        definition_set_id=sets[0],
        inputs=tuple(inputs),
    )
    counts = {
        RunInputKind.CAPTURE_REF: len(loaded.capture_refs),
        RunInputKind.PACKAGE: len(loaded.packages),
        RunInputKind.PACKAGE_STATEMENT: len(loaded.package_statements),
        RunInputKind.OCCURRENCE: len(loaded.occurrences),
        RunInputKind.INTERPRETATION: len(loaded.interpretations),
        RunInputKind.ATTEMPT: len(loaded.attempts),
        RunInputKind.ALIGNMENT_PROOF: len(loaded.proofs),
        RunInputKind.CALCULATION_TRACE: len(loaded.traces),
        RunInputKind.EVIDENCE_INPUT: len(loaded.evidence_inputs),
        RunInputKind.SETTINGS_RECORD: len(loaded.settings),
        RunInputKind.BASIS_STATUS: len(loaded.basis_statuses),
        RunInputKind.SEGMENT_MEMBER: len(loaded.segment_members),
    }
    for kind, count in counts.items():
        if count != len(set(ids[kind])):
            raise ReplayMismatchError(_MISSING.format(kind=kind.value, ids=sorted(ids[kind])[:5]))
    frozen_occurrences = {row.occurrence_id for row in loaded.occurrences}
    if any(
        not set(row.evidence_occurrence_ids) <= frozen_occurrences for row in loaded.segment_members
    ):
        raise ReplayMismatchError("segment metadata evidence escaped frozen occurrence IDs")
    return loaded


def dispositions(
    inputs: ResolvedInputs,
    rows: Sequence[ResultRow],
    *,
    selected_packages: Iterable[int],
    definition_set_id: int,
    sources: Iterable[str],
    selected_interpretations: Iterable[int] = (),
    selected_captures: Iterable[int] = (),
) -> tuple[RunInput, ...]:
    """Every input with what the run did with it; negative inputs included.

    A selected package's member on a source the scope does not request was never read, so
    its capture is not selected; ``selected_captures`` names vendor captures that decided.
    """
    chosen_packages = set(selected_packages)
    surfaces = frozenset(sources)
    decided_captures = {
        member.capture.capture_ref_id
        for package in inputs.packages
        if package.package_id in chosen_packages
        for member in package.members.values()
        if member.capture.surface in surfaces
    } | set(selected_captures)
    used = _used_interpretations(inputs, rows)
    used.update(selected_interpretations)
    by_id = {item.interpretation_id: item for item in inputs.interpretations}
    for interpretation_id in list(used):
        item = by_id.get(interpretation_id)
        if item is not None:
            used.update(item.operand_interpretation_ids)
            used.update(
                evidence
                for proof in item.condition_evidence
                for evidence in proof.evidence_interpretation_ids
            )
    surfaced = {item for row in rows for item in row.surfaced_restatements}
    used_occurrences = {by_id[item].occurrence_id for item in used if item in by_id}
    used_occurrences.update(
        occurrence_id
        for record in inputs.segment_members
        for occurrence_id in record.evidence_occurrence_ids
    )
    found: list[RunInput] = []

    def add(kind: RunInputKind, ref_id: int | None, chosen: bool) -> None:
        """Record one input as selected or not selected."""
        assert ref_id is not None
        disposition = RunInputDisposition.SELECTED if chosen else RunInputDisposition.NOT_SELECTED
        found.append(RunInput(kind=kind, ref_id=ref_id, disposition=disposition))

    for capture in inputs.capture_refs:
        add(
            RunInputKind.CAPTURE_REF,
            capture.capture_ref_id,
            capture.capture_ref_id in decided_captures,
        )
    for package in inputs.packages:
        add(RunInputKind.PACKAGE, package.package_id, package.package_id in chosen_packages)
    for statement in inputs.package_statements:
        add(RunInputKind.PACKAGE_STATEMENT, statement.id, statement.package_id in chosen_packages)
    for occurrence in inputs.occurrences:
        add(
            RunInputKind.OCCURRENCE,
            occurrence.occurrence_id,
            occurrence.occurrence_id in used_occurrences,
        )
    for item in inputs.interpretations:
        if item.interpretation_id in surfaced and item.interpretation_id not in used:
            assert item.interpretation_id is not None
            found.append(
                RunInput(
                    kind=RunInputKind.INTERPRETATION,
                    ref_id=item.interpretation_id,
                    disposition=RunInputDisposition.SURFACED,
                )
            )
            continue
        add(RunInputKind.INTERPRETATION, item.interpretation_id, item.interpretation_id in used)
    for attempt in inputs.attempts:
        assert attempt.attempt_id is not None
        failed = attempt.outcome is not ExtractionOutcome.COMPLETE
        found.append(
            RunInput(
                kind=RunInputKind.ATTEMPT,
                ref_id=attempt.attempt_id,
                disposition=(
                    RunInputDisposition.FAILED_ATTEMPT if failed else RunInputDisposition.SELECTED
                ),
            )
        )
    for proof in inputs.proofs:
        add(RunInputKind.ALIGNMENT_PROOF, proof.proof_id, True)
    for trace_id in _trace_ids(inputs.traces):
        add(RunInputKind.CALCULATION_TRACE, trace_id, True)
    for record in inputs.evidence_inputs:
        add(RunInputKind.EVIDENCE_INPUT, record.id, True)
    for settings in inputs.settings:
        add(RunInputKind.SETTINGS_RECORD, settings.id, True)
    for status in inputs.basis_statuses:
        add(RunInputKind.BASIS_STATUS, status.id, True)
    for member in inputs.segment_members:
        add(RunInputKind.SEGMENT_MEMBER, member.id, True)
    add(RunInputKind.DEFINITION_SET, definition_set_id, True)
    return sorted_inputs(found)


def _used_interpretations(inputs: ResolvedInputs, rows: Sequence[ResultRow]) -> set[int]:
    """Interpretations a result row or a stored trace operand names, or a proof uses."""
    used = {
        value.interpretation_id
        for row in rows
        for value in row.source_values
        if value.interpretation_id is not None
    }
    pending = list(inputs.traces)
    while pending:
        stored = pending.pop()
        used.update(
            operand.interpretation_id
            for operand in stored.trace.operands
            if operand.interpretation_id is not None
        )
        pending.extend(stored.children)
    for proof in inputs.proofs:
        used.update(interpretation_id for interpretation_id, _ in proof.participants)
    return used


def _trace_ids(traces: Sequence[StoredTrace]) -> list[int]:
    """Every trace id, children included."""
    found: list[int] = []
    pending = list(traces)
    while pending:
        stored = pending.pop()
        found.append(stored.trace_id)
        pending.extend(stored.children)
    return found
