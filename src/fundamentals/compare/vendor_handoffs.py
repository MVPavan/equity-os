"""Read-only reproof of a publication-bound first-party generation (D1b Task 6).

A handoff is a claim about immutable stored rows, never an authority token. Fresh
preflight scoped reads only check generation completeness; replay consumes the
returned manifest identities by id and never repeats those discovery reads.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run_config import LoadedConfig, require_published_generation
from fundamentals.compare.run_models import (
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunRequest,
    sorted_inputs,
)
from fundamentals.compare.vendor_handoff_attempts import validate_handoff_attempts
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    EligibilityBoundary,
    FilingPackage,
    Interpretation,
    Occurrence,
    RunMode,
)
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.evidence.alignment import AlignmentProof, prove_alignment
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.capture_interpretation import _conditions
from fundamentals.evidence.first_party_context import (
    FirstPartyGenerationContext,
    require_first_party_generation_context,
)
from fundamentals.evidence.first_party_generation import (
    FirstPartyGenerationHandoff,
    FirstPartyGenerationMember,
    _member,
)
from fundamentals.evidence.first_party_ingest import IngestMemberGeneration
from fundamentals.evidence.interpret import prove_conditions
from fundamentals.evidence.mapping import CONTEXT_BASIS
from fundamentals.evidence.repository import (
    EvidenceInputRecord,
    EvidenceRepository,
    SettingsRecord,
)
from fundamentals.evidence.selection import is_eligible, select_key
from fundamentals.evidence.vendor_config import PublicationState
from fundamentals.evidence.vendor_config_files import read_safe
from fundamentals.pg.identity_seed import (
    CITED_FIELDS,
    EvidenceInputKind,
    IssuerIdentityInput,
)

__all__ = ["FirstPartyHandoffError", "FirstPartyScope", "validate_first_party_handoff"]

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
_PIN_FIELDS = (
    "dictionary",
    "formula_set",
    "mapping_set",
    "normalisation_policy",
    "alignment_rules",
    "source_authority",
)


class FirstPartyHandoffError(ValueError):
    """A claimed first-party generation cannot be reproven from stored evidence."""


class FirstPartyScope(BaseModel):
    """Exact validated rows and explicit eligibility, ready for the shared run writer.

    All handed-off rows remain closed in ``inputs`` even when the cutoff excludes
    them. Eligible interpretation ids additionally close operands and condition
    evidence; a later context never makes an earlier row eligible in AS_KNOWN.
    """

    model_config = ConfigDict(frozen=True)

    handoff: FirstPartyGenerationHandoff
    package: FilingPackage
    capture_refs: tuple[CaptureReference, ...]
    occurrences: tuple[Occurrence, ...]
    interpretations: tuple[Interpretation, ...]
    attempts: tuple[AcquisitionAttempt, ...]
    proofs: tuple[AlignmentProof, ...]
    settings: tuple[SettingsRecord, ...]
    evidence_inputs: tuple[EvidenceInputRecord, ...]
    package_eligible: bool
    eligible_occurrence_ids: tuple[int, ...]
    eligible_interpretation_ids: tuple[int, ...]
    eligible_attempt_ids: tuple[int, ...]
    inputs: tuple[RunInput, ...]


def validate_first_party_handoff(
    handoff: FirstPartyGenerationHandoff,
    *,
    request: RunRequest,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
) -> FirstPartyScope:
    """Reprove the complete generation without pinning or writing any store row."""
    try:
        return _validate(handoff, request, config, config_root, repository)
    except (ValueError, LookupError, TypeError, yaml.YAMLError) as error:
        if isinstance(error, FirstPartyHandoffError):
            raise
        raise FirstPartyHandoffError(f"first-party handoff reproof refused: {error}") from error


def _validate(
    handoff: FirstPartyGenerationHandoff,
    request: RunRequest,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
) -> FirstPartyScope:
    publication = require_published_generation(config, config_root=config_root)
    if publication.state is PublicationState.SYNTHETIC:
        found = repository._fetch("SELECT current_database() AS name", ())
        if len(found) != 1 or not str(found[0]["name"]).startswith("eqos_test_"):
            raise FirstPartyHandoffError("synthetic handoff requires an actual eqos_test_ database")
    _pins_and_scope(handoff, request, config)
    package = _one(repository.get_packages([handoff.package_id]), "package")
    _package(handoff, package)
    setting = _one(
        repository.get_settings_records([handoff.fiscal_year_end_setting_id]), "settings record"
    )
    evidence = _one(
        repository.get_evidence_inputs([setting.evidence_input_id]), "settings evidence input"
    )
    context = _settings(handoff, setting, evidence, config_root, repository)
    attempts = repository.get_attempts(handoff.attempt_ids)
    _exact(handoff.attempt_ids, [row.attempt_id for row in attempts], "attempt")
    captures: list[CaptureReference] = []
    occurrences: list[Occurrence] = []
    interpretations: list[Interpretation] = []
    for claimed in handoff.members:
        reported = IngestMemberGeneration(
            representation=claimed.representation,
            source_id=claimed.source_id,
            surface=claimed.surface,
            capture_ref_id=claimed.capture_ref_id,
            extractor_version=claimed.extractor_pin.version,
            occurrence_ids=claimed.occurrence_ids,
            interpretation_ids=claimed.interpretation_ids,
        )
        actual, member_occurrences, member_interpretations = _member(
            reported, package=package, attempts=attempts, repository=repository, config=config
        )
        if actual != claimed:
            raise FirstPartyHandoffError("member hashes, times, bounds or qualification set differ")
        capture = _one(repository.get_capture_refs([claimed.capture_ref_id]), "member capture")
        _complete_member(
            claimed, member_occurrences, member_interpretations, handoff, config, repository
        )
        captures.append(capture)
        occurrences.extend(member_occurrences)
        interpretations.extend(member_interpretations)
    deciding_captures = validate_handoff_attempts(
        handoff,
        attempts,
        context=context,
        config=config,
        config_root=config_root,
        repository=repository,
    )
    by_id = {row.capture_ref_id: row for row in (*captures, *deciding_captures)}
    captures = [by_id[item] for item in sorted(by_id, key=lambda item: item or 0)]
    require_first_party_generation_context(interpretations, context)
    _qualified(interpretations, config)
    proofs = _proofs(handoff, package, occurrences, interpretations, config, repository)
    clock = repository.store_clock()
    _clocks(setting, evidence, captures, occurrences, interpretations, attempts, clock)
    return _scope(
        handoff,
        request,
        package,
        captures,
        occurrences,
        interpretations,
        attempts,
        proofs,
        setting,
        evidence,
    )


def _pins_and_scope(
    handoff: FirstPartyGenerationHandoff, request: RunRequest, config: LoadedConfig
) -> None:
    publication = config.vendor_config
    assert publication is not None  # fresh loader proof already required it
    if request.pinned != config.pinned:
        raise FirstPartyHandoffError("request pins differ from the verified publication")
    if (handoff.publication_version, handoff.publication_sha256, handoff.publication_state) != (
        publication.version,
        publication.published_config_sha256,
        publication.state,
    ):
        raise FirstPartyHandoffError("handoff publication identity differs")
    for name in _PIN_FIELDS:
        if getattr(handoff, f"{name}_pin") != getattr(config.pinned, name):
            raise FirstPartyHandoffError(f"handoff {name} pin differs")
    expected = {
        Representation.XBRL: config.pinned.extractor_xbrl,
        Representation.PDF: config.pinned.extractor_pdf,
    }
    if len(handoff.extractor_pins) != 2 or {
        item.representation: (item.version, item.content_sha256) for item in handoff.extractor_pins
    } != {
        representation: (pin.version, pin.content_sha256)
        for representation, pin in expected.items()
    }:
        raise FirstPartyHandoffError("handoff extractor content pins differ")
    if (
        request.scope.entity_ids != (handoff.entity_id,)
        or request.scope.period_ends != (handoff.reporting_period_end,)
        or request.scope.bases != (handoff.basis,)
    ):
        raise FirstPartyHandoffError("vendor run requires one matching entity/end/basis")
    for declaration in request.scope.vendor_sources:
        if getattr(declaration, "framework", None) not in (None, handoff.framework):
            raise FirstPartyHandoffError(
                "vendor declaration framework differs from first-party scope"
            )
    if (
        not handoff.qualification_context_trace_stored
        or handoff.qualification_context_foreign_key_stored
    ):
        raise FirstPartyHandoffError("handoff misstates the accepted durable context contract")


def _package(handoff: FirstPartyGenerationHandoff, package: FilingPackage) -> None:
    if (
        package.entity_id,
        package.reporting_period_end,
        package.basis,
        package.framework,
        package.family,
    ) != (
        handoff.entity_id,
        handoff.reporting_period_end,
        handoff.basis,
        handoff.framework,
        handoff.family,
    ):
        raise FirstPartyHandoffError("package family or scope differs")
    digest = canonical_sha256(
        {
            "members": {
                representation.value: member.capture.blob_sha256
                for representation, member in package.members.items()
            },
            "supersedes_package_id": package.supersedes_package_id,
            "replaced_statements": sorted(family.value for family in package.replaced_statements),
        }
    )
    if digest != package.evidence_sha256 or digest != handoff.package_evidence_sha256:
        raise FirstPartyHandoffError("package evidence hash differs from immutable members")
    if len(handoff.members) != len(package.members) or {
        member.representation for member in handoff.members
    } != set(package.members):
        raise FirstPartyHandoffError("handoff omits or duplicates package members")


def _settings(
    handoff: FirstPartyGenerationHandoff,
    setting: SettingsRecord,
    evidence: EvidenceInputRecord,
    config_root: Path,
    repository: EvidenceRepository,
) -> FirstPartyGenerationContext:
    context = FirstPartyGenerationContext.from_record(setting)
    if (
        context.entity_id,
        context.evidence_input_id,
        context.recorded_at,
        context.fiscal_year_end_month,
        context.record_sha256,
    ) != (
        handoff.entity_id,
        handoff.fiscal_year_end_setting_evidence_input_id,
        handoff.fiscal_year_end_setting_recorded_at,
        handoff.fiscal_year_end_month,
        handoff.qualification_context_sha256,
    ):
        raise FirstPartyHandoffError("exact settings context differs from the handoff")
    identifiers = repository.issuer_identifiers(handoff.entity_id)
    if not _SYMBOL.fullmatch(identifiers.nse_symbol):
        raise FirstPartyHandoffError("seeded NSE symbol has no safe identity artifact convention")
    body = read_safe(config_root, f"identity/{identifiers.nse_symbol.lower()}.yaml")
    identity = IssuerIdentityInput.model_validate(
        {**yaml.safe_load(body), "content_sha256": hashlib.sha256(body).hexdigest()}
    )
    if {citation.field for citation in identity.citations} != CITED_FIELDS:
        raise FirstPartyHandoffError("source identity artifact has incomplete or unknown citations")
    if (
        identity.nse_symbol,
        identity.isin,
        identity.bse_scrip,
        repository.entity_id(identity.entity_key),
        identity.fiscal_year_end_month,
    ) != (
        identifiers.nse_symbol,
        identifiers.isin,
        identifiers.bse_scrip,
        handoff.entity_id,
        context.fiscal_year_end_month,
    ):
        raise FirstPartyHandoffError(
            "source identity artifact differs from seeded entity or setting"
        )
    if (evidence.id, evidence.kind, evidence.label, evidence.content_sha256) != (
        setting.evidence_input_id,
        EvidenceInputKind.ISSUER_IDENTITY,
        identity.entity_key,
        identity.content_sha256,
    ):
        raise FirstPartyHandoffError("settings source artifact kind/label/content hash differs")
    return context


def _complete_member(
    member: FirstPartyGenerationMember,
    occurrences: tuple[Occurrence, ...],
    interpretations: tuple[Interpretation, ...],
    handoff: FirstPartyGenerationHandoff,
    config: LoadedConfig,
    repository: EvidenceRepository,
) -> None:
    if member.surface != SURFACE_OF[member.representation].value:
        raise FirstPartyHandoffError("member does not have the first-party representation surface")
    complete_occurrences = tuple(
        row
        for row in repository.list_capture_occurrences(
            member.capture_ref_id, member.extractor_pin.version
        )
        if row.native_context.get(CONTEXT_BASIS) == handoff.basis.value
    )
    _exact(
        member.occurrence_ids,
        [row.occurrence_id for row in complete_occurrences],
        "complete occurrence",
    )
    complete_interpretations = tuple(
        row
        for row in repository.list_capture_interpretations(member.capture_ref_id)
        if (
            row.entity_id,
            row.basis,
            row.framework,
            row.dictionary_version,
            row.mapping_set_version,
            row.normalisation_policy_version,
            row.extractor_version,
        )
        == (
            handoff.entity_id,
            handoff.basis,
            handoff.framework,
            config.pinned.dictionary.version,
            config.pinned.mapping_set.version,
            config.pinned.normalisation_policy.version,
            member.extractor_pin.version,
        )
    )
    _exact(
        member.interpretation_ids,
        [row.interpretation_id for row in complete_interpretations],
        "complete interpretation",
    )
    if not occurrences or not interpretations:
        raise FirstPartyHandoffError("successful member has no exact stored generation")
    capture = _one(repository.get_capture_refs([member.capture_ref_id]), "capture")
    if member.representation is Representation.XBRL:
        assert config.vendor_config is not None
        source = config.vendor_config.catalog.describe(member.source_id)
        if source.source_class is not SourceClass.FIRST_PARTY or not source.may_reconcile:
            raise FirstPartyHandoffError("XBRL member is not an authorized first-party source")
    for row in occurrences:
        if row.capture != capture:
            raise FirstPartyHandoffError("occurrence capture identity differs")


def _qualified(interpretations: Sequence[Interpretation], config: LoadedConfig) -> None:
    ids = {row.interpretation_id for row in interpretations}
    conditions = _conditions(config.mapping_set)
    for row in interpretations:
        if not row.condition_evidence:
            continue
        if row.period is None:
            raise FirstPartyHandoffError("qualified interpretation has no evidenced period")
        owned = [item for item in interpretations if item.capture_ref_id == row.capture_ref_id]
        proven = prove_conditions(
            conditions, interpretations=owned, period=row.period, basis=row.basis
        )
        for condition in row.condition_evidence:
            if (
                not set(condition.evidence_interpretation_ids) <= ids
                or proven.get(condition.condition_id) != condition
            ):
                raise FirstPartyHandoffError(
                    "ProvenCondition escapes or differs from exact generation evidence"
                )


def _proofs(
    handoff: FirstPartyGenerationHandoff,
    package: FilingPackage,
    occurrences: Sequence[Occurrence],
    interpretations: Sequence[Interpretation],
    config: LoadedConfig,
    repository: EvidenceRepository,
) -> tuple[AlignmentProof, ...]:
    stored = repository.get_alignment_proofs(handoff.alignment_proof_ids)
    _exact(handoff.alignment_proof_ids, [row.proof_id for row in stored], "alignment proof")
    keys = {row.key.digest(): row.key for row in interpretations if row.key is not None}
    cutoff = max(
        *(row.recorded_at for row in interpretations),
        *(member.capture.first_seen_at for member in package.members.values()),
    )
    boundary = EligibilityBoundary(
        knowledge_cutoff=package.knowledge_time, first_seen_cutoff=cutoff
    )
    selections = {
        (digest, representation): select_key(
            key,
            representation,
            package=package,
            occurrences=occurrences,
            interpretations=interpretations,
            boundary=boundary,
            mode=RunMode.AS_KNOWN,
            pinned=config.pinned,
        )
        for digest, key in sorted(keys.items())
        for representation in (Representation.PDF, Representation.XBRL)
    }
    expected = prove_alignment(package, selections, config.alignment_rules)
    actual_documents = [row.model_dump(mode="json", exclude={"proof_id"}) for row in stored]
    expected_documents = [row.model_dump(mode="json", exclude={"proof_id"}) for row in expected]
    if sorted(map(canonical_sha256, actual_documents)) != sorted(
        map(canonical_sha256, expected_documents)
    ):
        raise FirstPartyHandoffError(
            "alignment proof set differs from exact generation rederivation"
        )
    return stored


def _clocks(
    setting: SettingsRecord,
    evidence: EvidenceInputRecord,
    captures: Sequence[CaptureReference],
    occurrences: Sequence[Occurrence],
    interpretations: Sequence[Interpretation],
    attempts: Sequence[AcquisitionAttempt],
    clock: datetime,
) -> None:
    times = [setting.recorded_at, evidence.recorded_at]
    times += [
        time for capture in captures for time in (capture.registered_at, capture.first_seen_at)
    ]
    times += [row.first_seen_at for row in occurrences]
    times += [row.recorded_at for row in interpretations]
    times += [row.attempted_at for row in attempts if row.attempted_at is not None]
    if (
        any(time.tzinfo is None or time > clock for time in times)
        or evidence.recorded_at > setting.recorded_at
    ):
        raise FirstPartyHandoffError("stored generation has inconsistent or future database clocks")
    if any(row.recorded_at < setting.recorded_at for row in interpretations):
        raise FirstPartyHandoffError("interpretation predates its durable settings context")


def _scope(
    handoff: FirstPartyGenerationHandoff,
    request: RunRequest,
    package: FilingPackage,
    captures: Sequence[CaptureReference],
    occurrences: Sequence[Occurrence],
    interpretations: Sequence[Interpretation],
    attempts: Sequence[AcquisitionAttempt],
    proofs: tuple[AlignmentProof, ...],
    setting: SettingsRecord,
    evidence: EvidenceInputRecord,
) -> FirstPartyScope:
    boundary = EligibilityBoundary.at(request.cutoff)
    active = (
        package.eligible(boundary)
        and setting.recorded_at <= request.cutoff
        and evidence.recorded_at <= request.cutoff
    )
    owned = {
        row.capture_ref_id
        for row in captures
        if row.surface in request.scope.sources
        and row.first_seen_at <= request.cutoff
        and row.registered_at <= request.cutoff
    }
    occurrence_ids = tuple(
        row.occurrence_id
        for row in occurrences
        if active and row.capture.capture_ref_id in owned and is_eligible(row, boundary)
    )
    eligible = {
        row.interpretation_id
        for row in interpretations
        if active
        and row.capture_ref_id in owned
        and (request.mode is RunMode.RETROSPECTIVE or row.recorded_at <= request.cutoff)
    }
    # A constructed/qualified row is usable only when all its exact dependencies are usable.
    changed = True
    while changed:
        excluded = {
            row.interpretation_id
            for row in interpretations
            if row.interpretation_id in eligible
            and (
                (row.occurrence_id is not None and row.occurrence_id not in occurrence_ids)
                or not set(row.operand_interpretation_ids) <= eligible
                or any(
                    not set(condition.evidence_interpretation_ids) <= eligible
                    for condition in row.condition_evidence
                )
            )
        }
        changed = bool(excluded)
        eligible -= excluded
    attempt_ids = tuple(
        row.attempt_id
        for row in attempts
        if row.attempted_at is not None
        and row.surface in request.scope.sources
        and row.attempted_at <= request.cutoff
        and (row.capture is None or row.capture.first_seen_at <= request.cutoff)
    )
    selected = RunInputDisposition.SELECTED
    unused = RunInputDisposition.NOT_SELECTED
    items = [
        RunInput(
            kind=RunInputKind.PACKAGE,
            ref_id=handoff.package_id,
            disposition=selected if active else unused,
        ),
        RunInput(
            kind=RunInputKind.SETTINGS_RECORD,
            ref_id=setting.id,
            disposition=selected if active else unused,
        ),
        RunInput(
            kind=RunInputKind.EVIDENCE_INPUT,
            ref_id=evidence.id,
            disposition=selected if active else unused,
        ),
    ]
    for kind, rows, available in (
        (
            RunInputKind.CAPTURE_REF,
            ((row.capture_ref_id, row) for row in captures),
            owned if active else set(),
        ),
        (
            RunInputKind.OCCURRENCE,
            ((row.occurrence_id, row) for row in occurrences),
            set(occurrence_ids),
        ),
        (
            RunInputKind.INTERPRETATION,
            ((row.interpretation_id, row) for row in interpretations),
            eligible,
        ),
        (
            RunInputKind.ALIGNMENT_PROOF,
            ((row.proof_id, row) for row in proofs),
            {
                row.proof_id
                for row in proofs
                if set(item for item, _ in row.participants) <= eligible
            },
        ),
    ):
        items.extend(
            RunInput(
                kind=kind,
                ref_id=_id(ref_id),
                disposition=selected if ref_id in available else unused,
            )
            for ref_id, _ in rows
        )
    items.extend(
        RunInput(
            kind=RunInputKind.ATTEMPT,
            ref_id=_id(row.attempt_id),
            disposition=(
                RunInputDisposition.FAILED_ATTEMPT
                if row.outcome is not ExtractionOutcome.COMPLETE
                else selected
            )
            if row.attempt_id in attempt_ids
            else unused,
        )
        for row in attempts
    )
    return FirstPartyScope(
        handoff=handoff,
        package=package,
        capture_refs=tuple(captures),
        occurrences=tuple(occurrences),
        interpretations=tuple(interpretations),
        attempts=tuple(attempts),
        proofs=proofs,
        settings=(setting,),
        evidence_inputs=(evidence,),
        package_eligible=active,
        eligible_occurrence_ids=tuple(sorted(_id(item) for item in occurrence_ids)),
        eligible_interpretation_ids=tuple(sorted(_id(item) for item in eligible)),
        eligible_attempt_ids=tuple(sorted(_id(item) for item in attempt_ids)),
        inputs=sorted_inputs(items),
    )


def _id(value: int | None) -> int:
    if value is None or value <= 0:
        raise FirstPartyHandoffError("generation contains an unstored identity")
    return value


def _exact(expected: Sequence[int | None], actual: Sequence[int | None], label: str) -> None:
    wanted = [_id(item) for item in expected]
    found = [_id(item) for item in actual]
    if (
        len(wanted) != len(set(wanted))
        or len(found) != len(set(found))
        or set(wanted) != set(found)
    ):
        raise FirstPartyHandoffError(f"{label} ids do not close the exact stored set")


def _one[T](rows: Sequence[T], label: str) -> T:
    if len(rows) != 1:
        raise FirstPartyHandoffError(f"expected exactly one stored {label}")
    return rows[0]
