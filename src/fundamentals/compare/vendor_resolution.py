"""Closed public vendor-run preflight and exact evidence accumulation.

Only fresh execution discovers later attempts. Replay receives the closed manifest
IDs and never enters this module's repository discovery paths.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from fundamentals.compare.engine_attempts import attempt_available
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import (
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunRequest,
    VendorSurfaceRequest,
    sorted_inputs,
)
from fundamentals.compare.vendor_handoffs import FirstPartyScope, validate_first_party_handoff
from fundamentals.compare.vendor_inputs import (
    PreparedVendorGeneration,
    VendorScope,
    append_vendor_generation,
    prepare_vendor_generation,
)
from fundamentals.compare.vendor_request import VendorGenerationError, request_from_declaration
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation, ValueKind
from fundamentals.contracts.evidence import AcquisitionAttempt, Interpretation, StatementRole
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
from fundamentals.evidence.interpret import SEGMENT_AXIS
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_LOCAL_NAME,
    CONTEXT_SCHEMA_IDENTITY,
    in_namespace,
    matches_dimensions,
)
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.selection import period_end
from fundamentals.evidence.vendor_common import VendorGeneration
from fundamentals.evidence.vendor_config_files import read_safe
from fundamentals.evidence.xbrl_adapter import SEGMENT_DESCRIPTION_CONCEPT, member_slug
from fundamentals.ingest.xbrl_identity import (
    BSE_SCRIP_ENTITY_SCHEME,
    NSE_ENTITY_SCHEME,
    SEBI_SCRIP_ENTITY_SCHEME,
)
from fundamentals.pg.identity_seed import IssuerIdentityInput
from fundamentals.store.snapshot_store import DirectoryAnchor


@dataclass(frozen=True)
class VendorRunPreparation:
    """Read-only reproof results; append repeats each producer's own guard."""

    first_party: FirstPartyScope
    base: ResolvedInputs
    declarations: tuple[VendorSurfaceRequest, ...]
    generations: tuple[VendorGeneration, ...]
    prepared: tuple[PreparedVendorGeneration, ...]


def prepare_vendor_run(
    request: RunRequest,
    *,
    first_party_generation: FirstPartyGenerationHandoff | None,
    vendor_generations: tuple[VendorGeneration, ...],
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
    input_anchor: DirectoryAnchor | None,
) -> VendorRunPreparation:
    """Prove every closed claim before any pin, generation or run mutation."""
    if first_party_generation is None:
        raise VendorGenerationError("vendor run requires its exact joined first-party handoff")
    declarations = request.scope.vendor_sources
    if not declarations or len(declarations) != len(vendor_generations):
        raise VendorGenerationError("vendor declarations and generation claims must match exactly")
    expected = tuple(request_from_declaration(item) for item in declarations)
    claims = {item.request.model_dump_json(): item for item in vendor_generations}
    if len(claims) != len(vendor_generations) or set(claims) != {
        item.model_dump_json() for item in expected
    }:
        raise VendorGenerationError("vendor generation claims are missing, duplicate or extra")
    scope = validate_first_party_handoff(
        first_party_generation,
        request=request,
        config=config,
        config_root=config_root,
        repository=repository,
    )
    for expected_request in expected:
        if (
            expected_request.entity_id != scope.handoff.entity_id
            or expected_request.basis is not scope.handoff.basis
            or expected_request.framework is not scope.handoff.framework
            or period_end(expected_request.period) != scope.handoff.reporting_period_end
        ):
            raise VendorGenerationError("vendor declaration differs from first-party entity/scope")
    ordered = tuple(claims[item.model_dump_json()] for item in expected)
    prepared: list[PreparedVendorGeneration] = []
    for declaration, generation in zip(declarations, ordered, strict=True):
        context = declaration.composer_context
        assert context is not None  # the closed declaration was validated above
        item = prepare_vendor_generation(
            generation,
            declaration=declaration,
            loaded_config=config,
            config_root=config_root,
            input_anchor=input_anchor,
            composer_context=context,
            repository=repository,
        )
        if item.settings_record is not None and item.settings_record != scope.settings[0]:
            raise VendorGenerationError("vendor and first-party fiscal context records differ")
        prepared.append(item)
    _result_identities(prepared, config)
    base = _first_party_inputs(scope, request, config_root, repository)
    currencies = {
        item.key.currency
        for item in scope.interpretations
        if item.interpretation_id in scope.eligible_interpretation_ids
        and item.key is not None
        and item.key.value_kind is ValueKind.CURRENCY_AMOUNT
        and item.key.currency is not None
    }
    if len(currencies) != 1:
        raise VendorGenerationError(
            f"first-party eligible source-backed reporting currencies {sorted(currencies)}"
        )
    return VendorRunPreparation(scope, base, declarations, ordered, tuple(prepared))


def append_vendor_run_inputs(
    preparation: VendorRunPreparation,
    request: RunRequest,
    *,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
    input_anchor: DirectoryAnchor | None,
    definition_set_id: int,
) -> ResolvedInputs:
    """Append authorized generations, then close their exact rows and deciding attempts."""
    scopes = []
    for declaration, generation in zip(
        preparation.declarations, preparation.generations, strict=True
    ):
        context = declaration.composer_context
        assert context is not None
        scopes.append(
            append_vendor_generation(
                generation,
                declaration=declaration,
                loaded_config=config,
                config_root=config_root,
                input_anchor=input_anchor,
                composer_context=context,
                repository=repository,
            )
        )
    base = preparation.base.model_copy(update={"definition_set_id": definition_set_id})
    captures = {item.capture_ref_id: item for item in base.capture_refs}
    occurrences = {item.occurrence_id: item for item in base.occurrences}
    interpretations = {item.interpretation_id: item for item in base.interpretations}
    attempts = {item.attempt_id: item for item in base.attempts}
    evidence = {item.id: item for item in base.evidence_inputs}
    settings = {item.id: item for item in base.settings}
    listed = repository.list_attempts(request.scope.entity_ids[0], request.scope.period_ends[0])
    tokens = list(base.inputs)
    for scope in scopes:
        for capture in (*scope.supporting_captures, *((scope.capture,) if scope.capture else ())):
            captures[capture.capture_ref_id] = capture
        occurrences.update({item.occurrence_id: item for item in scope.occurrences})
        interpretations.update({item.interpretation_id: item for item in scope.interpretations})
        candidates = [item for item in listed if _candidate(item, scope, request)]
        attempts.update({item.attempt_id: item for item in (*scope.attempts, *candidates)})
        for item in candidates:
            if item.capture is not None:
                captures[item.capture.capture_ref_id] = item.capture
        evidence.update({item.id: item for item in scope.identity_evidence})
        if scope.settings_record is not None:
            settings[scope.settings_record.id] = scope.settings_record
        tokens.extend(_scope_tokens(scope, candidates, request))
    return base.model_copy(
        update={
            "capture_refs": _ordered(captures),
            "occurrences": _ordered(occurrences),
            "interpretations": _ordered(interpretations),
            "attempts": _ordered(attempts),
            "evidence_inputs": _ordered(evidence),
            "settings": _ordered(settings),
            "inputs": sorted_inputs(tokens),
        }
    )


def _candidate(item: AcquisitionAttempt, scope: VendorScope, request: RunRequest) -> bool:
    expected = scope.request
    return (
        item.package_id is None
        and (
            item.source_id,
            item.surface,
            item.entity_id,
            item.period_end,
            item.basis,
            item.framework,
            item.representation,
            item.statement_family,
            item.extractor_version,
            item.extraction_context_sha256,
        )
        == (
            expected.source_id,
            expected.surface,
            expected.entity_id,
            period_end(expected.period),
            expected.basis,
            expected.framework,
            expected.representation,
            expected.statement_family,
            scope.generation.extractor_pin.version,
            scope.logical_scope_sha256,
        )
        and attempt_available(
            item,
            cutoff=request.cutoff,
            mode=request.mode,
            extractor=scope.generation.extractor_pin.version,
        )
    )


def _scope_tokens(
    scope: VendorScope, candidates: Sequence[AcquisitionAttempt], request: RunRequest
) -> list[RunInput]:
    unused = RunInputDisposition.NOT_SELECTED
    tokens: list[RunInput] = []
    for kind, ids in (
        (RunInputKind.CAPTURE_REF, (*scope.supporting_capture_ref_ids, scope.capture_ref_id)),
        (RunInputKind.OCCURRENCE, scope.occurrence_ids),
        (RunInputKind.INTERPRETATION, scope.interpretation_ids),
        (RunInputKind.ATTEMPT, scope.attempt_ids),
    ):
        tokens.extend(RunInput(kind=kind, ref_id=item, disposition=unused) for item in ids if item)
    for item in candidates:
        assert item.attempt_id is not None
        tokens.append(
            RunInput(
                kind=RunInputKind.ATTEMPT,
                ref_id=item.attempt_id,
                disposition=(
                    RunInputDisposition.FAILED_ATTEMPT
                    if item.outcome is not ExtractionOutcome.COMPLETE
                    else unused
                ),
            )
        )
        if item.capture is not None:
            assert item.capture.capture_ref_id is not None
            tokens.append(
                RunInput(
                    kind=RunInputKind.CAPTURE_REF,
                    ref_id=item.capture.capture_ref_id,
                    disposition=RunInputDisposition.SELECTED,
                )
            )
    if scope.settings_record is not None:
        tokens.append(
            RunInput(
                kind=RunInputKind.SETTINGS_RECORD,
                ref_id=scope.settings_record.id,
                disposition=RunInputDisposition.SELECTED,
            )
        )
    tokens.extend(
        RunInput(
            kind=RunInputKind.EVIDENCE_INPUT,
            ref_id=item.id,
            disposition=RunInputDisposition.SELECTED,
        )
        for item in scope.identity_evidence
    )
    return tokens


def _result_identities(prepared: Sequence[PreparedVendorGeneration], config: LoadedConfig) -> None:
    """Refuse ambiguous stored result-side identities using process-local pure previews."""
    held: set[tuple[str, str, Representation, str]] = set()
    logical: set[str] = set()
    for item in prepared:
        if item.logical_scope_sha256 in logical:
            raise VendorGenerationError("vendor claims repeat one logical result-side scope")
        logical.add(item.logical_scope_sha256)
        current: set[tuple[str, str, Representation, str]] = set()
        for row in _preview(item, config):
            if row.key is None:
                continue
            identity = (
                item.generation.request.source_id,
                item.generation.request.surface,
                row.representation,
                row.key.digest(),
            )
            if identity in held:
                raise VendorGenerationError("vendor claims have an ambiguous result-side identity")
            current.add(identity)
        held.update(current)


def _preview(item: PreparedVendorGeneration, config: LoadedConfig) -> tuple[Interpretation, ...]:
    """Temporary symbols support semantic collision checks; they are never stored or authority."""
    if item.generation.capture is None:
        return ()
    setting = item.settings_record
    if setting is None:
        raise VendorGenerationError("captured vendor generation lacks evidenced fiscal context")
    pending = 0

    def reserve(count: int) -> tuple[int, ...]:
        nonlocal pending
        values = tuple(range(pending + 1, pending + count + 1))
        pending += count
        return values

    occurrences = tuple(
        row.model_copy(update={"occurrence_id": index})
        for index, row in enumerate(item.generation.occurrences, start=1)
    )
    source = item.generation.request
    return interpret_generation(
        occurrences,
        scope=CaptureScope(
            capture=item.generation.capture,
            entity_id=source.entity_id,
            basis=source.basis,
            framework=source.framework,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            dictionary=config.dictionary,
            fiscal_year_end_month=int(setting.value_text),
            expected_extractor_pin=item.generation.extractor_pin,
        ),
        prior=(),
        prior_anchor_keys={},
        reserve_ids=reserve,
        recorded_at=setting.recorded_at,
    )


def _first_party_inputs(
    scope: FirstPartyScope, request: RunRequest, config_root: Path, repository: EvidenceRepository
) -> ResolvedInputs:
    if not scope.package_eligible:
        raise VendorGenerationError("first-party handoff package/context is unavailable at cutoff")
    identifiers = repository.issuer_identifiers(scope.handoff.entity_id)
    if identifiers is None or identifiers.nse_symbol is None:
        raise VendorGenerationError("first-party identity has no verified source symbol")
    body = read_safe(config_root, f"identity/{identifiers.nse_symbol.lower()}.yaml")
    identity = IssuerIdentityInput.model_validate(
        {**yaml.safe_load(body), "content_sha256": hashlib.sha256(body).hexdigest()}
    )
    evidence = scope.evidence_inputs[0]
    if identity.content_sha256 != evidence.content_sha256 or identity.entity_key != evidence.label:
        raise VendorGenerationError("basis context identity bytes differ from handoff evidence")
    found = repository._fetch(
        "SELECT id FROM eqos.entity_basis_status WHERE entity_id = %s AND evidence_input_id = %s "
        "AND recorded_at <= %s ORDER BY id",
        (scope.handoff.entity_id, evidence.id, request.cutoff),
    )
    statuses = repository.get_basis_statuses([int(row["id"]) for row in found])
    if len(statuses) != 1 or any(
        row.entity_id != scope.handoff.entity_id
        or row.evidence_input_id != evidence.id
        or row.basis_status is not identity.basis_status
        or row.recorded_at < evidence.recorded_at
        or row.recorded_at > request.cutoff
        for row in statuses
    ):
        raise VendorGenerationError("basis context is missing, ambiguous or differs from source")
    occurrences = {row.occurrence_id: row for row in scope.occurrences}
    segments = []
    for row in repository.segment_members_as_of(
        scope.handoff.entity_id, SEGMENT_AXIS, request.cutoff
    ):
        if (
            not row.evidence_occurrence_ids
            or not set(row.evidence_occurrence_ids) <= occurrences.keys()
        ):
            continue
        evidence_rows = [occurrences[item] for item in row.evidence_occurrence_ids]
        starts = [
            item.period.start or item.period.instant
            for item in evidence_rows
            if item.period is not None
        ]
        if not (
            all(
                item.native_context.get(CONTEXT_BASIS) == scope.handoff.basis.value
                and item.period is not None
                and period_end(item.period) == scope.handoff.reporting_period_end
                and item.native_context.get(CONTEXT_LOCAL_NAME) == SEGMENT_DESCRIPTION_CONCEPT
                and isinstance(item.native_context.get(CONTEXT_SCHEMA_IDENTITY), str)
                and in_namespace(
                    item.native_context, str(item.native_context[CONTEXT_SCHEMA_IDENTITY])
                )
                and matches_dimensions(
                    item.native_context,
                    str(item.native_context[CONTEXT_SCHEMA_IDENTITY]),
                    "ReportableSegmentsAxis",
                )
                and item.native_context.get("entity")
                in (
                    {"scheme": NSE_ENTITY_SCHEME, "identifier": identity.nse_symbol},
                    {"scheme": BSE_SCRIP_ENTITY_SCHEME, "identifier": identity.bse_scrip},
                    {"scheme": SEBI_SCRIP_ENTITY_SCHEME, "identifier": identity.bse_scrip},
                )
                and member_slug((item.raw_value_text or "").strip()) == row.member
                and (item.raw_value_text or "").strip() == row.display_name
                and item.first_seen_at <= row.recorded_at <= request.cutoff
                for item in evidence_rows
            )
            and starts
            and None not in starts
            and row.valid_from == min(day for day in starts if day is not None)
            and row.valid_to is None
        ):
            raise VendorGenerationError("segment metadata differs from its closed source witness")
        segments.append(row)
    statements = repository.get_package_statements_of([scope.handoff.package_id])
    if any(
        row.package_id != scope.handoff.package_id
        or not set(row.evidence_occurrence_ids) <= occurrences.keys()
        or (
            row.role is StatementRole.PRESENT
            and row.statement_family not in scope.package.statements_present
        )
        for row in statements
    ):
        raise VendorGenerationError("package statement evidence escapes exact handoff scope")
    tokens = list(scope.inputs)
    for kind, rows in (
        (RunInputKind.BASIS_STATUS, statuses),
        (RunInputKind.SEGMENT_MEMBER, segments),
        (RunInputKind.PACKAGE_STATEMENT, statements),
    ):
        tokens.extend(
            RunInput(kind=kind, ref_id=row.id, disposition=RunInputDisposition.SELECTED)
            for row in rows
        )
    return ResolvedInputs(
        capture_refs=scope.capture_refs,
        packages=(scope.package,),
        package_statements=statements,
        occurrences=scope.occurrences,
        interpretations=scope.interpretations,
        attempts=scope.attempts,
        proofs=scope.proofs,
        settings=scope.settings,
        evidence_inputs=scope.evidence_inputs,
        basis_statuses=statuses,
        segment_members=tuple(segments),
        definition_set_id=0,
        inputs=sorted_inputs(tokens),
    )


def _ordered[K: int | None, T](rows: dict[K, T]) -> tuple[T, ...]:
    if None in rows:
        raise VendorGenerationError("run input lacks a stored identity")
    return tuple(rows[key] for key in sorted(rows, key=lambda value: int(str(value))))
