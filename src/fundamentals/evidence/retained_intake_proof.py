"""Pure original-material and stored-generation reproof shared by consumption/replay."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    FilingPackage,
    Interpretation,
    InterpretationOrigin,
    KnowledgeTimeStatus,
    Occurrence,
    VersionPin,
)
from fundamentals.evidence.retained_intake_models import (
    PreparedRetainedIntakeWitness,
    RetainedIntakeAssociation,
    RetainedIntakeRequest,
    RetainedIntakeVersionPin,
    RetainedIntakeWitness,
    RetainedIntakeWitnessError,
    RetainedIntakeWitnessPayload,
)
from fundamentals.evidence.retained_intake_source import (
    canonical_document,
    derive_retained_intake_material,
)

if TYPE_CHECKING:
    from fundamentals.evidence.first_party_context import FirstPartyGenerationContext
    from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
    from fundamentals.evidence.repository import SettingsRecord
    from fundamentals.evidence.vendor_config import PublishedVendorConfig


def generation_document(handoff: FirstPartyGenerationHandoff) -> str:
    """The unchanged full handoff projection; the new witness ID is not a content input."""
    document = handoff.model_dump(mode="json")
    document.pop("retained_intake_witness_id", None)
    return canonical_document(document)


def require_prepared_material(prepared: PreparedRetainedIntakeWitness) -> None:
    """Reparse material, selection, contexts and every original request without reads."""
    pins: dict[Representation, VersionPin] = {
        request.representation: request.extractor_pin for request in prepared.requests
    }
    try:
        xbrl = next(
            (row for row in prepared.requests if row.representation is Representation.XBRL), None
        )
        mapping_version = (
            json.loads(xbrl.context_material_json)["mapping_set_version"]
            if xbrl
            else "not-applicable"
        )
        derived = derive_retained_intake_material(
            manifest=prepared.manifest,
            issuer_config=prepared.issuer_config,
            issuer=prepared.issuer,
            quarter=prepared.quarter,
            selection=prepared.selection,
            entity_id=prepared.entity_id,
            family=prepared.family,
            reporting_period_end=prepared.reporting_period_end,
            basis=prepared.basis,
            framework=prepared.framework,
            extractor_pins=pins,
            mapping_set_version=mapping_version,
        )
        if derived != prepared:
            raise ValueError("prepared requests/context differ from original metadata")
    except (ValueError, TypeError, KeyError) as exc:
        raise RetainedIntakeWitnessError(str(exc)) from exc


def reprove_retained_intake_witness(
    witness: RetainedIntakeWitness,
    *,
    package: FilingPackage,
    settings: SettingsRecord,
    captures: Sequence[CaptureReference],
    attempts: Sequence[AcquisitionAttempt],
    pins: Sequence[RetainedIntakeVersionPin],
    publication: PublishedVendorConfig,
) -> tuple[RetainedIntakeRequest, ...]:
    """Reprove exact supplied durable rows and source-derived bindings; never choose/read latest."""
    try:
        witness = RetainedIntakeWitness.model_validate(witness.model_dump())
        payload = witness.payload
        require_payload_association(
            payload,
            package=package,
            settings=settings,
            captures=captures,
            attempts=attempts,
            pins=pins,
        )
        if (
            publication.version,
            publication.published_config_sha256,
            publication.state.value,
        ) != (payload.publication_version, payload.publication_sha256, payload.publication_state):
            raise ValueError("witness publication differs from supplied pinned publication")
        clocks = [
            _utc(settings.recorded_at),
            *(_utc(row.attempted_at) for row in payload.attempts),
            *(_utc(row.registered_at) for row in payload.captures),
            *(_utc(row.first_seen_at) for row in payload.captures),
            *(_utc(row.pinned_at) for row in payload.pins),
        ]
        if any(clock > witness.recorded_at for clock in clocks):
            raise ValueError("witness predates an associated database row")
        return payload.prepared.requests
    except (ValueError, TypeError, KeyError) as exc:
        raise RetainedIntakeWitnessError(f"retained witness reproof refused: {exc}") from exc


def require_payload_association(
    payload: RetainedIntakeWitnessPayload,
    *,
    package: FilingPackage,
    settings: SettingsRecord,
    captures: Sequence[CaptureReference],
    attempts: Sequence[AcquisitionAttempt],
    pins: Sequence[RetainedIntakeVersionPin],
) -> None:
    """Prove normalized association data before insertion and on every by-ID reload."""
    from fundamentals.evidence.first_party_context import FirstPartyGenerationContext
    from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff

    require_prepared_material(payload.prepared)
    prepared = payload.prepared
    try:
        generation_raw = json.loads(payload.generation_json)
        if "retained_intake_witness_id" in generation_raw:
            raise ValueError("witness content cannot contain its newly generated ID")
        generation = FirstPartyGenerationHandoff.model_validate(generation_raw)
        if generation_document(generation) != payload.generation_json:
            raise ValueError("witness generation projection is not canonical")
        if (
            package.package_id,
            package.evidence_sha256,
            package.entity_id,
            package.family,
            package.reporting_period_end,
            package.basis,
            package.framework,
        ) != (
            payload.package_id,
            payload.package_evidence_sha256,
            prepared.entity_id,
            prepared.family,
            prepared.reporting_period_end,
            prepared.basis,
            prepared.framework,
        ):
            raise ValueError("witness package/scope differs from exact stored package")
        if (
            generation.package_id != payload.package_id
            or generation.package_evidence_sha256 != payload.package_evidence_sha256
            or generation.entity_id != prepared.entity_id
            or generation.family != prepared.family
            or generation.reporting_period_end != prepared.reporting_period_end
            or generation.basis != prepared.basis
            or generation.framework != prepared.framework
            or generation.publication_version != payload.publication_version
            or generation.publication_sha256 != payload.publication_sha256
            or generation.publication_state.value != payload.publication_state
            or generation.fiscal_year_end_setting_id != payload.settings_record_id
            or generation.qualification_context_sha256 != payload.qualification_context_sha256
        ):
            raise ValueError("witness full generation projection differs from package/scope")
        context = FirstPartyGenerationContext.from_record(settings)
        if (
            context.settings_record_id != payload.settings_record_id
            or context.entity_id != prepared.entity_id
            or context.record_sha256 != payload.qualification_context_sha256
            or context.evidence_input_id != generation.fiscal_year_end_setting_evidence_input_id
            or context.recorded_at != generation.fiscal_year_end_setting_recorded_at
            or context.fiscal_year_end_month != generation.fiscal_year_end_month
        ):
            raise ValueError("witness qualification settings differ from complete stored identity")
        ordered_attempts = tuple(sorted(attempts, key=lambda item: _id(item.attempt_id)))
        ordered_captures = tuple(sorted(captures, key=lambda item: _id(item.capture_ref_id)))
        if ordered_attempts != payload.attempts or ordered_captures != payload.captures:
            raise ValueError("witness attempt/capture payload or stored clocks differ")
        if tuple(sorted(pins, key=lambda row: row.artifact)) != payload.pins:
            raise ValueError("witness version pin identities/payload differ")
        _require_generation_pins(generation, payload.pins)
        if tuple(_id(row.attempt_id) for row in payload.attempts) != generation.attempt_ids:
            raise ValueError("witness omits or adds an exact generation attempt")
        member_captures = {
            member.capture_ref_id: member.representation for member in generation.members
        }
        if member_captures != {
            _id(member.capture.capture_ref_id): representation
            for representation, member in package.members.items()
        }:
            raise ValueError("witness successful member capture projection differs from package")
        for member in generation.members:
            capture = package.members[member.representation].capture
            if (
                member.source_id,
                member.surface,
                member.blob_sha256,
                member.record_sha256,
                member.capture_registered_at,
                member.capture_first_seen_at,
            ) != (
                capture.source_id,
                capture.surface,
                capture.blob_sha256,
                capture.record_sha256,
                capture.registered_at,
                capture.first_seen_at,
            ):
                raise ValueError("full generation member capture payload/clocks differ")
            owned = tuple(
                row
                for row in payload.attempts
                if row.capture is not None and row.capture.capture_ref_id == member.capture_ref_id
            )
            clocks = tuple(_utc(row.attempted_at) for row in owned)
            if (
                member.attempt_ids != tuple(_id(row.attempt_id) for row in owned)
                or member.extraction_context_sha256s
                != tuple(
                    sorted(
                        {
                            row.extraction_context_sha256
                            for row in owned
                            if row.extraction_context_sha256 is not None
                        }
                    )
                )
                or member.attempted_at_min != min(clocks, default=None)
                or member.attempted_at_max != max(clocks, default=None)
            ):
                raise ValueError("full generation member attempt projection/clocks differ")
        requests: dict[Representation, RetainedIntakeRequest] = {
            row.representation: row for row in prepared.requests
        }
        for representation, package_member in package.members.items():
            original = requests.get(representation)
            if original is None or (
                package_member.knowledge_time,
                package_member.knowledge_time_raw,
                package_member.knowledge_time_status,
            ) != (original.knowledge_time, original.filed_at_raw, KnowledgeTimeStatus.KNOWN):
                raise ValueError(
                    "package member knowledge time differs from original filed-at material"
                )
        if any(
            row.representation not in requests
            or not request_matches_attempt(requests[row.representation], prepared, row)
            or row.package_id not in {None, payload.package_id}
            for row in payload.attempts
        ):
            raise ValueError("attempt scope/stage/context differs from original request")
        associations = _associations(payload.attempts, payload.captures, member_captures, requests)
        if associations != payload.associations:
            raise ValueError("witness normalized request/attempt/capture closure differs")
        for request in prepared.requests:
            pin = next(
                row
                for row in payload.pins
                if row.artifact == f"extractor_{request.representation.value.lower()}"
            )
            if request.extractor_pin != VersionPin(
                version=pin.version, content_sha256=pin.content_sha256
            ):
                raise ValueError("original request extractor differs from actual generation pin")
            if request.representation is Representation.XBRL and json.loads(
                request.context_material_json
            ) != {"mapping_set_version": generation.mapping_set_pin.version}:
                raise ValueError("original XBRL decision context differs from generation mapping")
    except (ValueError, TypeError, KeyError, StopIteration) as exc:
        raise RetainedIntakeWitnessError(f"retained association refused: {exc}") from exc


def request_matches_attempt(
    request: RetainedIntakeRequest, prepared: PreparedRetainedIntakeWitness, row: AcquisitionAttempt
) -> bool:
    """A source-derived logical request, with stage-specific extraction semantics."""
    if (
        row.representation,
        row.source_id,
        row.surface,
        row.input_sha256,
        row.entity_id,
        row.period_end,
        row.basis,
        row.framework,
    ) != (
        request.representation,
        request.source_id,
        request.surface,
        request.expected_input_sha256,
        prepared.entity_id,
        prepared.reporting_period_end,
        prepared.basis,
        prepared.framework,
    ):
        return False
    if row.stage is AttemptStage.ACQUISITION:
        return (
            row.capture is None
            and row.package_id is None
            and row.statement_family is None
            and row.extractor_version == ""
            and row.extraction_context_sha256 is None
            and row.outcome in {ExtractionOutcome.FAILED, ExtractionOutcome.NOT_AUTHORISED}
        )
    if row.capture is None or row.extractor_version != request.extractor_pin.version:
        return False
    if request.representation is Representation.PDF:
        return row.extraction_context_sha256 == request.extraction_context_sha256
    return row.extraction_context_sha256 == (
        request.extraction_context_sha256
        if row.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
        else None
    )


def require_member_generation_rows(
    payload: RetainedIntakeWitnessPayload,
    *,
    occurrences: Sequence[Occurrence],
    interpretations: Sequence[Interpretation],
    context: FirstPartyGenerationContext,
) -> None:
    """Prove every exact member occurrence/interpretation ID before any witness insert."""
    from fundamentals.evidence.first_party_context import require_first_party_generation_context
    from fundamentals.evidence.first_party_generation import (
        FirstPartyGenerationHandoff,
        _validate_acyclic_closure,
    )

    generation = FirstPartyGenerationHandoff.model_validate_json(payload.generation_json)
    actual_occurrences = {_id(row.occurrence_id): row for row in occurrences}
    actual_interpretations = {_id(row.interpretation_id): row for row in interpretations}
    if len(actual_occurrences) != len(occurrences) or len(actual_interpretations) != len(
        interpretations
    ):
        raise RetainedIntakeWitnessError("member rows contain duplicate stored IDs")
    expected_occurrence_ids = tuple(
        sorted(item for member in generation.members for item in member.occurrence_ids)
    )
    expected_interpretation_ids = tuple(
        sorted(item for member in generation.members for item in member.interpretation_ids)
    )
    if (
        tuple(sorted(actual_occurrences)) != expected_occurrence_ids
        or tuple(sorted(actual_interpretations)) != expected_interpretation_ids
    ):
        raise RetainedIntakeWitnessError("exact member occurrence/interpretation IDs do not reload")
    for member in generation.members:
        ids = set(member.interpretation_ids)
        direct: set[int] = set()
        rows = tuple(actual_interpretations[item] for item in member.interpretation_ids)
        for occurrence_id in member.occurrence_ids:
            occurrence = actual_occurrences[occurrence_id]
            if (
                occurrence.capture.capture_ref_id,
                occurrence.representation,
                occurrence.extractor_version,
            ) != (member.capture_ref_id, member.representation, member.extractor_pin.version):
                raise RetainedIntakeWitnessError("member occurrence escapes exact source/extractor")
        for row in rows:
            if (
                row.capture_ref_id,
                row.representation,
                row.extractor_version,
                row.entity_id,
                row.basis,
                row.framework,
                row.dictionary_version,
                row.mapping_set_version,
                row.normalisation_policy_version,
            ) != (
                member.capture_ref_id,
                member.representation,
                member.extractor_pin.version,
                generation.entity_id,
                generation.basis,
                generation.framework,
                generation.dictionary_pin.version,
                generation.mapping_set_pin.version,
                generation.normalisation_policy_pin.version,
            ):
                raise RetainedIntakeWitnessError("member interpretation escapes exact scope/pins")
            if row.origin is InterpretationOrigin.DIRECT:
                if row.occurrence_id not in member.occurrence_ids or row.operand_interpretation_ids:
                    raise RetainedIntakeWitnessError("member direct occurrence closure differs")
                direct.add(_id(row.occurrence_id))
            elif (
                row.occurrence_id is not None
                or not row.construction_rule_id
                or not row.operand_interpretation_ids
                or not set(row.operand_interpretation_ids) <= ids
            ):
                raise RetainedIntakeWitnessError("member construction operand closure differs")
        if direct != set(member.occurrence_ids):
            raise RetainedIntakeWitnessError("member direct rows omit original occurrences")
        _validate_acyclic_closure({_id(row.interpretation_id): row for row in rows})
        require_first_party_generation_context(rows, context)
        clocks = tuple(_utc(row.recorded_at) for row in rows)
        qualified = tuple(row for row in rows if row.qualification_ref is not None)
        if (
            not clocks
            or min(clocks) != member.interpretation_recorded_at_min
            or max(clocks) != member.interpretation_recorded_at_max
            or tuple(_id(row.interpretation_id) for row in qualified)
            != member.qualified_interpretation_ids
            or tuple(
                sorted(
                    {
                        condition.condition_id
                        for row in qualified
                        for condition in row.condition_evidence
                    }
                )
            )
            != member.qualification_condition_ids
            or tuple(
                sorted(
                    {
                        item
                        for row in qualified
                        for condition in row.condition_evidence
                        for item in condition.evidence_interpretation_ids
                    }
                )
            )
            != member.qualification_evidence_interpretation_ids
            or not set(member.qualification_evidence_interpretation_ids)
            <= actual_interpretations.keys()
        ):
            raise RetainedIntakeWitnessError("member stored clock/qualification projection differs")


def _associations(
    attempts: tuple[AcquisitionAttempt, ...],
    captures: tuple[CaptureReference, ...],
    member_captures: dict[int, Representation],
    requests: dict[Representation, RetainedIntakeRequest],
) -> tuple[RetainedIntakeAssociation, ...]:
    capture_ids = {_id(row.capture_ref_id): row for row in captures}
    used: set[int] = set()
    result: list[RetainedIntakeAssociation] = []
    for representation, request in sorted(requests.items()):
        owned = tuple(row for row in attempts if row.representation is representation)
        if not owned:
            raise ValueError("original request lacks any deciding attempt")
        for row in owned:
            # Scope is checked separately in the caller with the complete prepared value.
            if (row.source_id, row.surface, row.input_sha256) != (
                request.source_id,
                request.surface,
                request.expected_input_sha256,
            ):
                raise ValueError("attempt physical source differs from original binding")
            _utc(row.attempted_at)
            if row.capture is not None:
                capture_id = _id(row.capture.capture_ref_id)
                capture = capture_ids.get(capture_id)
                if capture != row.capture or (
                    row.capture.source_id,
                    row.capture.surface,
                    row.capture.request_key,
                    row.capture.blob_sha256,
                ) != (
                    request.source_id,
                    request.surface,
                    request.request_key,
                    request.expected_input_sha256,
                ):
                    raise ValueError("attempt capture differs from exact original physical binding")
                _utc(row.capture.registered_at)
                _utc(row.capture.first_seen_at)
                if row.capture.first_seen_at > row.capture.registered_at:
                    raise ValueError("capture first-seen clock contradicts registration")
                used.add(capture_id)
        ids = {_id(row.capture.capture_ref_id) for row in owned if row.capture is not None}
        for capture_id in ids:
            overall = tuple(
                row
                for row in owned
                if row.capture is not None
                and row.capture.capture_ref_id == capture_id
                and row.package_id is None
                and row.statement_family is None
                and row.stage is AttemptStage.EXTRACTION
            )
            if len(overall) != 1 or (
                (overall[0].outcome is ExtractionOutcome.COMPLETE)
                != (capture_id in member_captures)
            ):
                raise ValueError("captured disposition lacks its exact overall extraction")
        result.append(
            RetainedIntakeAssociation.model_validate(
                {
                    "representation": representation,
                    "attempt_ids": tuple(_id(row.attempt_id) for row in owned),
                    "package_capture_ids": tuple(sorted(ids & member_captures.keys())),
                    "failed_capture_ids": tuple(sorted(ids - member_captures.keys())),
                }
            )
        )
    if used != set(capture_ids):
        raise ValueError("witness contains a capture unrelated to deciding attempts")
    return tuple(result)


def _require_generation_pins(
    generation: FirstPartyGenerationHandoff, pins: tuple[RetainedIntakeVersionPin, ...]
) -> None:
    expected = generation_pin_projection(generation)
    if {pin.artifact for pin in pins} != set(expected):
        raise ValueError("witness complete generation pin projection differs")
    for pin in pins:
        if (pin.version, pin.content_sha256) != (
            expected[pin.artifact].version,
            expected[pin.artifact].content_sha256,
        ):
            raise ValueError("witness generation pin content differs")
        _utc(pin.pinned_at)


def generation_pin_projection(generation: FirstPartyGenerationHandoff) -> dict[str, VersionPin]:
    """The complete frozen generation pin vocabulary, independent of later stored versions."""
    expected = {
        name: getattr(generation, f"{name}_pin")
        for name in (
            "dictionary",
            "formula_set",
            "mapping_set",
            "normalisation_policy",
            "alignment_rules",
            "source_authority",
        )
    }
    expected["vendor_publication"] = VersionPin(
        version=generation.publication_version, content_sha256=generation.publication_sha256
    )
    expected.update(
        {
            f"extractor_{pin.representation.value.lower()}": VersionPin(
                version=pin.version, content_sha256=pin.content_sha256
            )
            for pin in generation.extractor_pins
        }
    )
    return expected


def _utc(value: datetime | None) -> datetime:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retained witness requires aware database clocks")
    return value.astimezone(UTC)


def _id(value: int | None) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("retained witness requires a positive stored identity")
    return value
