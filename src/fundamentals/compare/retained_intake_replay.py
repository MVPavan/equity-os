"""Pure retained-witness closure and context reproof over manifest-listed records."""

from __future__ import annotations

import json

from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import RunInputKind, RunRequest
from fundamentals.compare.vendor_handoff_attempts import _witnessed_sources
from fundamentals.compare.vendor_handoffs import _package, _pins_and_scope
from fundamentals.contracts.evidence import RunMode
from fundamentals.evidence.first_party_context import FirstPartyGenerationContext
from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
from fundamentals.evidence.repository import EvidenceInputRecord
from fundamentals.evidence.retained_intake_models import (
    RetainedIntakeWitness,
    RetainedIntakeWitnessError,
)
from fundamentals.evidence.retained_intake_proof import (
    reprove_retained_intake_witness,
    require_member_generation_rows,
)
from fundamentals.pg.identity_seed import EvidenceInputKind


def _witnesses(inputs: ResolvedInputs) -> tuple[RetainedIntakeWitness, ...]:
    result = []
    for evidence in inputs.evidence_inputs:
        witness = evidence.retained_intake_witness
        if evidence.kind is not EvidenceInputKind.RETAINED_INTAKE:
            if witness is not None:
                raise RetainedIntakeWitnessError("witness material has the wrong evidence kind")
            continue
        if witness is None:
            raise RetainedIntakeWitnessError("manifest witness evidence lacks sealed material")
        witness = RetainedIntakeWitness.model_validate(witness.model_dump())
        _envelope(evidence, witness)
        result.append(witness)
    if len(result) > 1:
        raise RetainedIntakeWitnessError("one first-party generation requires one exact witness")
    return tuple(result)


def _envelope(evidence: EvidenceInputRecord, witness: RetainedIntakeWitness) -> None:
    if (evidence.id, evidence.label, evidence.content_sha256, evidence.recorded_at) != (
        witness.evidence_input_id,
        witness.label,
        witness.content_sha256,
        witness.recorded_at,
    ):
        raise RetainedIntakeWitnessError("witness envelope differs from manifest evidence row")


def _generation(witness: RetainedIntakeWitness) -> FirstPartyGenerationHandoff:
    return FirstPartyGenerationHandoff.model_validate(json.loads(witness.payload.generation_json))


def _required(
    witness: RetainedIntakeWitness, generation: FirstPartyGenerationHandoff
) -> set[tuple[RunInputKind, int]]:
    refs = {
        (RunInputKind.EVIDENCE_INPUT, witness.evidence_input_id),
        (RunInputKind.EVIDENCE_INPUT, generation.fiscal_year_end_setting_evidence_input_id),
        (RunInputKind.PACKAGE, witness.payload.package_id),
        (RunInputKind.SETTINGS_RECORD, witness.payload.settings_record_id),
    }
    refs.update((RunInputKind.ATTEMPT, value) for value in generation.attempt_ids)
    refs.update(
        (RunInputKind.CAPTURE_REF, _id(capture.capture_ref_id))
        for capture in witness.payload.captures
    )
    refs.update((RunInputKind.ALIGNMENT_PROOF, value) for value in generation.alignment_proof_ids)
    for member in generation.members:
        refs.update((RunInputKind.OCCURRENCE, value) for value in member.occurrence_ids)
        refs.update((RunInputKind.INTERPRETATION, value) for value in member.interpretation_ids)
        refs.update(
            (RunInputKind.INTERPRETATION, value)
            for value in member.qualification_evidence_interpretation_ids
        )
    return refs


def require_witness_manifest_closure(inputs: ResolvedInputs) -> None:
    """Refuse escaping associations without fetching any missing domain record."""
    witnesses = _witnesses(inputs)
    if not witnesses:
        return
    listed = {(row.kind, row.ref_id) for row in inputs.inputs}
    if len(listed) != len(inputs.inputs):
        raise RetainedIntakeWitnessError("witness manifest has duplicate tagged identities")
    actual: set[tuple[RunInputKind, int]] = set()
    for kind, rows, field in (
        (RunInputKind.EVIDENCE_INPUT, inputs.evidence_inputs, "id"),
        (RunInputKind.SETTINGS_RECORD, inputs.settings, "id"),
        (RunInputKind.PACKAGE, inputs.packages, "package_id"),
        (RunInputKind.CAPTURE_REF, inputs.capture_refs, "capture_ref_id"),
        (RunInputKind.ATTEMPT, inputs.attempts, "attempt_id"),
        (RunInputKind.OCCURRENCE, inputs.occurrences, "occurrence_id"),
        (RunInputKind.INTERPRETATION, inputs.interpretations, "interpretation_id"),
        (RunInputKind.ALIGNMENT_PROOF, inputs.proofs, "proof_id"),
    ):
        ids = tuple(_id(getattr(row, field)) for row in rows)
        if len(ids) != len(set(ids)):
            raise RetainedIntakeWitnessError("witness domain records have duplicate identities")
        actual.update((kind, value) for value in ids)
    for witness in witnesses:
        required = _required(witness, _generation(witness))
        if not required <= listed or not required <= actual:
            raise RetainedIntakeWitnessError("witness association escapes manifest-listed records")


def require_witness_replay_context(
    inputs: ResolvedInputs, request: RunRequest, *, config: LoadedConfig
) -> None:
    """Reprove durable original material using supplied frozen rows, never repository or files."""
    require_witness_manifest_closure(inputs)
    for witness in _witnesses(inputs):
        generation = _generation(witness)
        _pins_and_scope(generation, request, config)
        package = _one(
            tuple(row for row in inputs.packages if row.package_id == witness.payload.package_id)
        )
        _package(generation, package)
        settings = _one(
            tuple(row for row in inputs.settings if row.id == witness.payload.settings_record_id)
        )
        attempt_ids = set(generation.attempt_ids)
        capture_ids = {_id(row.capture_ref_id) for row in witness.payload.captures}
        assert config.vendor_config is not None
        reprove_retained_intake_witness(
            witness,
            package=package,
            settings=settings,
            attempts=tuple(row for row in inputs.attempts if row.attempt_id in attempt_ids),
            captures=tuple(row for row in inputs.capture_refs if row.capture_ref_id in capture_ids),
            pins=witness.payload.pins,
            publication=config.vendor_config,
        )
        _witnessed_sources(witness.payload.prepared, config)
        context = FirstPartyGenerationContext.from_record(settings)
        for member in generation.members:
            occurrences = tuple(
                row for row in inputs.occurrences if row.occurrence_id in member.occurrence_ids
            )
            capture = _one(
                tuple(
                    row
                    for row in inputs.capture_refs
                    if row.capture_ref_id == member.capture_ref_id
                )
            )
            if any(
                row.capture != capture
                or row.representation is not member.representation
                or row.extractor_version != member.extractor_pin.version
                for row in occurrences
            ):
                raise RetainedIntakeWitnessError("witness occurrence escapes its stored generation")
        occurrence_ids = {value for member in generation.members for value in member.occurrence_ids}
        interpretation_ids = {
            value for member in generation.members for value in member.interpretation_ids
        }
        require_member_generation_rows(
            witness.payload,
            occurrences=tuple(
                row for row in inputs.occurrences if row.occurrence_id in occurrence_ids
            ),
            interpretations=tuple(
                row for row in inputs.interpretations if row.interpretation_id in interpretation_ids
            ),
            context=context,
        )
        if request.mode is RunMode.AS_KNOWN and (
            witness.recorded_at > request.cutoff or witness.sealed_at > request.cutoff
        ):
            # Engine selection uses source clocks rather than manifest dispositions.
            # Refuse before evaluation so pre-seal source rows cannot re-enter it.
            raise RetainedIntakeWitnessError("future witness cannot evaluate an AS_KNOWN run")


def _id(value: int | None) -> int:
    if value is None or isinstance(value, bool) or value <= 0:
        raise RetainedIntakeWitnessError("witness manifest contains an unstored identity")
    return value


def _one[T](rows: tuple[T, ...]) -> T:
    if len(rows) != 1:
        raise RetainedIntakeWitnessError("witness requires one exact manifest domain record")
    return rows[0]
