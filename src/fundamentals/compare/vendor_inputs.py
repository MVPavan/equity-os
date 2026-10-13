"""Guarded deterministic vendor generations and closed by-id handoffs (D1b Task 6)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydantic import ConfigDict

from fundamentals.compare.run_config import LoadedConfig, pin_published_generation
from fundamentals.compare.run_models import VendorSurfaceRequest
from fundamentals.compare.vendor_input_proof import (
    VendorPreparation,
    recompose_vendor_generation,
    require_matching_claim,
    scoped_existing_occurrences,
)
from fundamentals.compare.vendor_request import VendorComposerContext, VendorGenerationError
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    Interpretation,
    Occurrence,
)
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.first_party_context import (
    FirstPartyGenerationContext,
    bind_first_party_generation_context,
    require_first_party_generation_context,
)
from fundamentals.evidence.repository import EvidenceRepository, InterpretationConflictError
from fundamentals.evidence.vendor_common import VendorGeneration, VendorRequest
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.store.snapshot_store import DirectoryAnchor

PreparedVendorGeneration = VendorPreparation


class VendorScope(VendorPreparation):
    """A release-qualified source and exact rows; it never represents a filing package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @property
    def request(self) -> VendorRequest:
        return self.generation.request

    @property
    def request_sha256(self) -> str:
        return self.request.identity_sha256()

    @property
    def capture(self) -> CaptureReference | None:
        return self.generation.capture

    @property
    def capture_ref_id(self) -> int | None:
        return self.capture.capture_ref_id if self.capture else None

    @property
    def supporting_capture_ref_ids(self) -> tuple[int, ...]:
        return tuple(
            _stored(row.capture_ref_id, "supporting capture") for row in self.supporting_captures
        )

    @property
    def occurrences(self) -> tuple[Occurrence, ...]:
        return self.generation.occurrences

    @property
    def interpretations(self) -> tuple[Interpretation, ...]:
        return self.generation.interpretations

    @property
    def attempts(self) -> tuple[AcquisitionAttempt, ...]:
        return self.generation.attempts

    @property
    def occurrence_ids(self) -> tuple[int, ...]:
        return tuple(_stored(row.occurrence_id, "occurrence") for row in self.occurrences)

    @property
    def interpretation_ids(self) -> tuple[int, ...]:
        return tuple(
            _stored(row.interpretation_id, "interpretation") for row in self.interpretations
        )

    @property
    def attempt_ids(self) -> tuple[int, ...]:
        return tuple(_stored(row.attempt_id, "attempt") for row in self.attempts)


def compose_vendor_generation(
    *,
    declaration: VendorSurfaceRequest,
    loaded_config: LoadedConfig,
    config_root: Path,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
    repository: EvidenceRepository,
) -> VendorGeneration:
    """Read-only fixed composer for callers; neither models nor this return grant authority."""
    return recompose_vendor_generation(
        declaration=declaration,
        loaded_config=loaded_config,
        config_root=config_root,
        input_anchor=input_anchor,
        composer_context=composer_context,
        repository=repository,
    ).generation


def prepare_vendor_generation(
    generation: VendorGeneration,
    *,
    declaration: VendorSurfaceRequest,
    loaded_config: LoadedConfig,
    config_root: Path,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
    repository: EvidenceRepository,
) -> PreparedVendorGeneration:
    """Re-read registered captures and retained bytes; reject forged rows before mutation."""
    prepared = recompose_vendor_generation(
        declaration=declaration,
        loaded_config=loaded_config,
        config_root=config_root,
        input_anchor=input_anchor,
        composer_context=composer_context,
        repository=repository,
    )
    require_matching_claim(generation, prepared)
    _require_claimed_ids(generation, repository)
    _preflight_attempts(prepared, repository)
    _preflight_existing(
        prepared,
        loaded_config,
        repository,
        input_anchor=input_anchor,
        composer_context=composer_context,
    )
    if generation.interpretations:
        current = _current_interpretations(prepared, loaded_config, repository)
        if {row.interpretation_id: row for row in generation.interpretations} != {
            row.interpretation_id: row for row in current
        } or len(generation.interpretations) != len(current):
            raise VendorGenerationError(
                "claimed interpretations do not equal the complete rederived stored generation"
            )
    return prepared


def append_vendor_generation(
    generation: VendorGeneration,
    *,
    declaration: VendorSurfaceRequest,
    loaded_config: LoadedConfig,
    config_root: Path,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
    repository: EvidenceRepository,
) -> VendorScope:
    """Repeat read-only preparation, guard the same repository, then persist derived rows."""
    prepared = prepare_vendor_generation(
        generation,
        declaration=declaration,
        loaded_config=loaded_config,
        config_root=config_root,
        input_anchor=input_anchor,
        composer_context=composer_context,
        repository=repository,
    )
    publication = pin_published_generation(
        loaded_config, config_root=config_root, repository=repository
    )
    if publication.content_sha256 != prepared.publication_sha256:
        raise VendorGenerationError("vendor publication changed during generation preparation")
    _require_current_setting(prepared, repository)
    expected = prepared.generation
    stored_occurrences, stored_attempts = repository.put_generation(
        expected.occurrences, expected.attempts
    )
    occurrences = repository.get_occurrences(
        [_stored(row.occurrence_id, "occurrence") for row in stored_occurrences]
    )
    attempts = repository.get_attempts(
        [_stored(row.attempt_id, "attempt") for row in stored_attempts]
    )
    if {row.occurrence_id: row for row in occurrences} != {
        row.occurrence_id: row for row in stored_occurrences
    } or {row.attempt_id: row for row in attempts} != {
        row.attempt_id: row for row in stored_attempts
    }:
        raise VendorGenerationError("stored vendor generation differs from exact id reload")
    _require_attempt_payloads(expected.attempts, attempts)
    interpreted = _append_interpretations(prepared, occurrences, loaded_config, repository)
    actual = VendorGeneration(
        request=expected.request,
        capture=expected.capture,
        occurrences=occurrences,
        interpretations=interpreted,
        attempts=attempts,
        extractor_pin=expected.extractor_pin,
        source_authority_pin=expected.source_authority_pin,
        published_config_sha256=expected.published_config_sha256,
    )
    _require_current_setting(prepared, repository)
    values = {name: getattr(prepared, name) for name in type(prepared).model_fields}
    values["generation"] = actual
    return VendorScope.model_validate(values)


def _require_claimed_ids(generation: VendorGeneration, repository: EvidenceRepository) -> None:
    for interpretation in generation.interpretations:
        interpretation_id = _stored(interpretation.interpretation_id, "claimed interpretation")
        if repository.get_interpretations([interpretation_id]) != (interpretation,):
            raise VendorGenerationError(
                "claimed interpretation differs from exact stored id reload"
            )
    for row in generation.occurrences:
        if row.occurrence_id is not None and repository.get_occurrences([row.occurrence_id]) != (
            row,
        ):
            raise VendorGenerationError("claimed occurrence id differs from its stored row")
    for attempt in generation.attempts:
        if attempt.attempt_id is None:
            if attempt.attempted_at is not None:
                raise VendorGenerationError("unstored attempt cannot supply a caller store time")
        elif repository.get_attempts([attempt.attempt_id]) != (attempt,):
            raise VendorGenerationError("claimed attempt id differs from its stored row")


def _attempt_payload(row: AcquisitionAttempt) -> dict[str, object]:
    return row.model_dump(mode="json", exclude={"attempt_id", "attempted_at"})


def _attempt_key(row: AcquisitionAttempt) -> str:
    from fundamentals.contracts.snapshot import canonical_sha256

    payload = _attempt_payload(row)
    payload.pop("reason")
    return canonical_sha256(payload)


def _require_attempt_payloads(
    expected: Sequence[AcquisitionAttempt], actual: Sequence[AcquisitionAttempt]
) -> None:
    wanted = {_attempt_key(row): _attempt_payload(row) for row in expected}
    found = {_attempt_key(row): _attempt_payload(row) for row in actual}
    if wanted != found or len(actual) != len(expected):
        raise VendorGenerationError("stored attempt payload differs from fixed recomposition")


def _preflight_attempts(prepared: VendorPreparation, repository: EvidenceRepository) -> None:
    request = prepared.generation.request
    end = request.period.instant or request.period.end
    assert end is not None
    existing = repository.list_attempts(request.entity_id, end)
    expected = {_attempt_key(row): row for row in prepared.generation.attempts}
    for row in existing:
        wanted = expected.get(_attempt_key(row))
        if wanted is not None:
            _require_attempt_payloads((wanted,), (row,))
            reloaded = repository.get_attempts([_stored(row.attempt_id, "existing attempt")])
            if reloaded != (row,):
                raise VendorGenerationError("existing attempt differs from exact stored id reload")


def _preflight_existing(
    prepared: VendorPreparation,
    config: LoadedConfig,
    repository: EvidenceRepository,
    *,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
) -> None:
    capture = prepared.generation.capture
    if capture is None:
        return
    existing = repository.list_capture_occurrences(
        _stored(capture.capture_ref_id, "capture"), prepared.generation.extractor_pin.version
    )
    scoped = scoped_existing_occurrences(
        prepared, existing, input_anchor=input_anchor, composer_context=composer_context
    )
    current = _current_interpretations(prepared, config, repository)
    if current:
        if len(scoped) != len(prepared.generation.occurrences):
            raise VendorGenerationError(
                "stored interpretations have an incomplete semantic occurrence generation"
            )
        _reprove_interpretations(prepared, scoped, current, config, repository)


def _current_interpretations(
    prepared: VendorPreparation, config: LoadedConfig, repository: EvidenceRepository
) -> tuple[Interpretation, ...]:
    capture = prepared.generation.capture
    if capture is None:
        return ()
    capture_id = _stored(capture.capture_ref_id, "capture")
    request = prepared.generation.request
    expected_anchors = {row.anchor_key for row in prepared.generation.occurrences}
    occurrence_ids = {
        _stored(row.occurrence_id, "occurrence")
        for row in repository.list_capture_occurrences(
            capture_id, prepared.generation.extractor_pin.version
        )
        if row.anchor_key in expected_anchors
    }
    rows = tuple(
        row
        for row in repository.list_capture_interpretations(capture_id)
        if (
            row.entity_id,
            row.basis,
            row.framework,
            row.representation,
            row.dictionary_version,
            row.mapping_set_version,
            row.normalisation_policy_version,
            row.extractor_version,
        )
        == (
            request.entity_id,
            request.basis,
            request.framework,
            request.representation,
            config.dictionary.version,
            config.mapping_set.version,
            config.normalisation_policy.version,
            prepared.generation.extractor_pin.version,
        )
    )
    selected = {
        _stored(row.interpretation_id, "interpretation"): row
        for row in rows
        if row.occurrence_id in occurrence_ids
    }
    remaining = [row for row in rows if row.occurrence_id is None]
    while remaining:
        progress = False
        for row in remaining[:]:
            operands = set(row.operand_interpretation_ids)
            if not operands:
                raise VendorGenerationError("stored construction has no semantic operand closure")
            if operands <= selected.keys():
                selected[_stored(row.interpretation_id, "interpretation")] = row
                remaining.remove(row)
                progress = True
        if not progress:
            break
    for row in remaining:
        if set(row.operand_interpretation_ids) & selected.keys():
            raise VendorGenerationError("stored construction crosses semantic source groups")
    return tuple(row for row in rows if row.interpretation_id in selected)


def _require_current_setting(prepared: VendorPreparation, repository: EvidenceRepository) -> None:
    expected = prepared.settings_record
    if expected is None:
        return
    current = repository.settings_as_of(
        prepared.generation.request.entity_id,
        SettingKey.FISCAL_YEAR_END_MONTH,
        repository.store_clock(),
    )
    if current != expected or repository.get_settings_records([expected.id]) != (expected,):
        raise VendorGenerationError("vendor qualification setting changed during preparation")


def _context(prepared: VendorPreparation) -> FirstPartyGenerationContext:
    if prepared.settings_record is None:
        raise VendorGenerationError("numeric vendor generation lacks its exact fiscal setting")
    return FirstPartyGenerationContext.from_record(prepared.settings_record)


def _capture_scope(prepared: VendorPreparation, config: LoadedConfig) -> CaptureScope:
    capture = prepared.generation.capture
    if capture is None:
        raise VendorGenerationError("capture-free generation cannot be interpreted")
    request = prepared.generation.request
    return CaptureScope(
        capture=capture,
        entity_id=request.entity_id,
        basis=request.basis,
        framework=request.framework,
        mapping_set=config.mapping_set,
        policy=config.normalisation_policy,
        dictionary=config.dictionary,
        fiscal_year_end_month=_context(prepared).fiscal_year_end_month,
        expected_extractor_pin=prepared.generation.extractor_pin,
    )


def _prior(
    prepared: VendorPreparation, config: LoadedConfig, repository: EvidenceRepository
) -> tuple[tuple[Interpretation, ...], dict[int, str]]:
    capture_id = _stored(
        prepared.generation.capture.capture_ref_id if prepared.generation.capture else None,
        "capture",
    )
    current = {
        row.interpretation_id for row in _current_interpretations(prepared, config, repository)
    }
    prior = tuple(
        row
        for row in repository.list_capture_interpretations(capture_id)
        if row.interpretation_id not in current
        and (row.entity_id, row.basis, row.framework, row.representation)
        == (
            prepared.generation.request.entity_id,
            prepared.generation.request.basis,
            prepared.generation.request.framework,
            prepared.generation.request.representation,
        )
    )
    anchors = {
        _stored(row.occurrence_id, "occurrence"): row.anchor_key
        for row in repository.list_capture_occurrences(capture_id)
    }
    return prior, anchors


def _reprove_interpretations(
    prepared: VendorPreparation,
    occurrences: Sequence[Occurrence],
    current: tuple[Interpretation, ...],
    config: LoadedConfig,
    repository: EvidenceRepository,
) -> tuple[Interpretation, ...]:
    context = _context(prepared)
    require_first_party_generation_context(current, context)
    by_occurrence = {row.occurrence_id: row for row in current if row.occurrence_id is not None}
    if len(by_occurrence) != len(occurrences):
        raise VendorGenerationError("stored vendor interpretations do not close all occurrences")
    direct = [by_occurrence[_stored(row.occurrence_id, "occurrence")] for row in occurrences]
    constructed = sorted(
        (row for row in current if row.occurrence_id is None),
        key=lambda row: _stored(row.interpretation_id, "interpretation"),
    )
    ids = iter(_stored(row.interpretation_id, "interpretation") for row in (*direct, *constructed))
    prior, anchors = _prior(prepared, config, repository)
    first_recorded_at = min(row.recorded_at for row in current)
    prior = tuple(row for row in prior if row.recorded_at < first_recorded_at)

    def reserve(count: int) -> tuple[int, ...]:
        try:
            return tuple(next(ids) for _ in range(count))
        except StopIteration as error:
            raise VendorGenerationError(
                "stored vendor construction closure is incomplete"
            ) from error

    times = {row.recorded_at for row in current}
    if len(times) != 1:
        raise VendorGenerationError("vendor interpretation generation has conflicting store times")
    recomposed = interpret_generation(
        occurrences,
        scope=_capture_scope(prepared, config),
        prior=prior,
        prior_anchor_keys=anchors,
        reserve_ids=reserve,
        recorded_at=next(iter(times)),
    )
    expected = tuple(bind_first_party_generation_context(row, context) for row in recomposed)
    if {row.interpretation_id: row for row in expected} != {
        row.interpretation_id: row for row in current
    }:
        raise VendorGenerationError(
            "stored vendor interpretations differ from current pinned recomposition"
        )
    return repository.get_interpretations(
        [_stored(row.interpretation_id, "interpretation") for row in current]
    )


def _append_interpretations(
    prepared: VendorPreparation,
    occurrences: tuple[Occurrence, ...],
    config: LoadedConfig,
    repository: EvidenceRepository,
) -> tuple[Interpretation, ...]:
    if not occurrences:
        return ()
    for _ in range(3):
        existing = _current_interpretations(prepared, config, repository)
        if existing:
            return _reprove_interpretations(prepared, occurrences, existing, config, repository)
        prior, anchors = _prior(prepared, config, repository)
        rows = interpret_generation(
            occurrences,
            scope=_capture_scope(prepared, config),
            prior=prior,
            prior_anchor_keys=anchors,
            reserve_ids=repository.reserve_interpretation_ids,
            recorded_at=repository.store_clock(),
        )
        rows = tuple(bind_first_party_generation_context(row, _context(prepared)) for row in rows)
        try:
            repository.put_interpretations(rows)
        except InterpretationConflictError:
            continue
        reloaded = repository.get_interpretations(
            [_stored(row.interpretation_id, "interpretation") for row in rows]
        )
        if {row.interpretation_id: row for row in reloaded} != {
            row.interpretation_id: row for row in rows
        }:
            raise VendorGenerationError("stored vendor interpretations differ from exact id reload")
        return reloaded
    raise VendorGenerationError("concurrent vendor interpretation could not be reloaded")


def _stored(value: int | None, label: str) -> int:
    if value is None or value <= 0:
        raise VendorGenerationError(f"{label} requires a positive stored id")
    return value
