"""Append and identify one publication-bound first-party interpretation generation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run_config import LoadedConfig
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationOrigin,
    Occurrence,
    RunMode,
    VersionPin,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import (
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SourceDescriptor,
    UnknownSourceError,
)
from fundamentals.evidence.alignment import AlignmentProof, prove_alignment
from fundamentals.evidence.capture_intake import RetainedIntake
from fundamentals.evidence.first_party_context import (
    FirstPartyContextError,
    FirstPartyGenerationContext,
    capture_first_party_generation_context,
    reload_first_party_generation_context,
    require_first_party_generation_context,
)
from fundamentals.evidence.first_party_ingest import IngestMemberGeneration, ingest_first_party
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.selection import select_key
from fundamentals.evidence.vendor_config import (
    PublicationState,
    VendorConfigPublicationError,
    mapping_requires_publication,
)
from fundamentals.extract.pdf_statement_pages import StatementPageSpec
from fundamentals.store.snapshot_store import SnapshotStore

__all__ = [
    "FirstPartyExtractorPin",
    "FirstPartyGenerationError",
    "FirstPartyGenerationHandoff",
    "FirstPartyGenerationMember",
    "append_first_party_generation",
]


class FirstPartyGenerationError(ValueError):
    """A stored row cannot be proven to belong to the requested published generation."""


class FirstPartyExtractorPin(BaseModel):
    """One representation-specific first-party extractor pin."""

    model_config = ConfigDict(frozen=True)

    representation: Representation
    version: str
    content_sha256: str


class FirstPartyGenerationMember(BaseModel):
    """Exact stored identities for one successful member of the published generation."""

    model_config = ConfigDict(frozen=True)

    representation: Representation
    source_id: str
    surface: str
    capture_ref_id: int
    blob_sha256: str
    record_sha256: str
    capture_registered_at: datetime
    capture_first_seen_at: datetime
    extractor_pin: VersionPin
    occurrence_ids: tuple[int, ...]
    attempt_ids: tuple[int, ...]
    extraction_context_sha256s: tuple[str, ...]
    attempted_at_min: datetime | None
    attempted_at_max: datetime | None
    interpretation_ids: tuple[int, ...]
    interpretation_recorded_at_min: datetime
    interpretation_recorded_at_max: datetime
    qualified_interpretation_ids: tuple[int, ...]
    qualification_condition_ids: tuple[str, ...]
    qualification_evidence_interpretation_ids: tuple[int, ...]


class FirstPartyGenerationHandoff(BaseModel):
    """Closed candidate set Task 6 may consume by id under one joined publication."""

    model_config = ConfigDict(frozen=True)

    package_id: int
    package_evidence_sha256: str
    entity_id: int
    family: FilingFamily
    reporting_period_end: date
    basis: Basis
    framework: AccountingFramework
    publication_version: str
    publication_sha256: str
    publication_state: PublicationState
    dictionary_pin: VersionPin
    formula_set_pin: VersionPin
    mapping_set_pin: VersionPin
    normalisation_policy_pin: VersionPin
    alignment_rules_pin: VersionPin
    source_authority_pin: VersionPin
    extractor_pins: tuple[FirstPartyExtractorPin, ...]
    fiscal_year_end_setting_id: int
    fiscal_year_end_setting_evidence_input_id: int
    fiscal_year_end_setting_recorded_at: datetime
    fiscal_year_end_month: int
    qualification_context_sha256: str
    qualification_context_trace_stored: Literal[True] = True
    qualification_context_foreign_key_stored: Literal[False] = False
    members: tuple[FirstPartyGenerationMember, ...]
    attempt_ids: tuple[int, ...]
    capture_free_attempt_ids: tuple[int, ...]
    alignment_proof_ids: tuple[int, ...]


def append_first_party_generation(
    *,
    intake: RetainedIntake,
    snapshot_store: SnapshotStore,
    pool: ConnectionPool,
    config: LoadedConfig,
    config_root: Path,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    family: FilingFamily,
    reporting_period_end: date,
    pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None,
    supersedes_package_id: int | None = None,
    replaced_statements: frozenset[StatementFamily] = frozenset(),
) -> FirstPartyGenerationHandoff:
    """Append through existing ingest, then return only its exact persisted generation ids."""
    publication = config.vendor_config
    if publication is None or not mapping_requires_publication(config.mapping_set):
        raise VendorConfigPublicationError(
            "first-party generation requires a joined verified vendor publication"
        )
    repository = EvidenceRepository(pool)
    catalog = _catalog_for_intake(publication.catalog, intake)
    extractors = {
        Representation.XBRL: config.pinned.extractor_xbrl.version,
        Representation.PDF: config.pinned.extractor_pdf.version,
    }
    try:
        report = ingest_first_party(
            intake=intake,
            catalog=catalog,
            snapshot_store=snapshot_store,
            repository=repository,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            entity_id=entity_id,
            basis=basis,
            framework=framework,
            family=family,
            reporting_period_end=reporting_period_end,
            pdf_specs=pdf_specs,
            supersedes_package_id=supersedes_package_id,
            replaced_statements=replaced_statements,
            extractor_versions=extractors,
            config=config,
            config_root=config_root,
        )
        if report.generation_context is None:
            raise FirstPartyGenerationError(
                "published generation did not report its stored qualification context"
            )
        return _handoff(
            report.package_id,
            report.members,
            report.attempts,
            repository=repository,
            config=config,
            qualification_context=report.generation_context,
            entity_id=entity_id,
            basis=basis,
            framework=framework,
            family=family,
            reporting_period_end=reporting_period_end,
        )
    except FirstPartyContextError as exc:
        raise FirstPartyGenerationError(str(exc)) from exc


def _catalog_for_intake(catalog: SourceCatalog, intake: RetainedIntake) -> SourceCatalog:
    """Join the retained issuer-config PDF declaration to the published vendor catalog."""
    source_id = intake.results_pdf_source_id
    if source_id is None:
        return catalog
    try:
        declared = catalog.describe(source_id)
    except UnknownSourceError:
        return catalog.extend(
            SourceDescriptor(
                source_id=source_id,
                source_class=SourceClass.FIRST_PARTY,
                evidence_role=EvidenceRole.RECONCILABLE,
            )
        )
    if declared.source_class is not SourceClass.FIRST_PARTY or not declared.may_reconcile:
        raise FirstPartyGenerationError(
            "retained results PDF conflicts with the published source catalog"
        )
    return catalog


def _handoff(
    package_id: int | None,
    reported_members: tuple[IngestMemberGeneration, ...],
    reported_attempts: tuple[AcquisitionAttempt, ...],
    *,
    repository: EvidenceRepository,
    config: LoadedConfig,
    qualification_context: FirstPartyGenerationContext,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    family: FilingFamily,
    reporting_period_end: date,
) -> FirstPartyGenerationHandoff:
    publication = config.vendor_config
    authority = config.pinned.source_authority
    if package_id is None or publication is None or authority is None:
        raise FirstPartyGenerationError("published generation did not produce one stored package")
    package = _one(repository.get_packages([package_id]), "package")
    _validate_package(
        package,
        entity_id=entity_id,
        basis=basis,
        framework=framework,
        family=family,
        reporting_period_end=reporting_period_end,
    )
    attempts = _attempts(
        reported_attempts,
        repository=repository,
        entity_id=entity_id,
        basis=basis,
        framework=framework,
        reporting_period_end=reporting_period_end,
    )
    member_rows: list[
        tuple[FirstPartyGenerationMember, tuple[Occurrence, ...], tuple[Interpretation, ...]]
    ] = []
    all_interpretation_ids: set[int] = set()
    for reported in reported_members:
        member, occurrences, interpretations = _member(
            reported,
            package=package,
            attempts=attempts,
            repository=repository,
            config=config,
        )
        member_rows.append((member, occurrences, interpretations))
        all_interpretation_ids.update(member.interpretation_ids)
    if set(package.members) != {item.representation for item, _, _ in member_rows}:
        raise FirstPartyGenerationError("ingest report does not name every stored package member")
    for member, _, _ in member_rows:
        if not set(member.qualification_evidence_interpretation_ids) <= all_interpretation_ids:
            raise FirstPartyGenerationError(
                "qualification evidence escapes the exact published generation"
            )
    occurrences = tuple(row for _, rows, _ in member_rows for row in rows)
    interpretations = tuple(row for _, _, rows in member_rows for row in rows)
    proofs = _alignment_proofs(
        package,
        occurrences,
        interpretations,
        repository=repository,
        config=config,
    )
    qualification_context = _validate_qualification_context(
        qualification_context,
        interpretations=interpretations,
        repository=repository,
    )
    attempt_ids = tuple(_stored_attempt_id(row) for row in attempts)
    return FirstPartyGenerationHandoff(
        package_id=package_id,
        package_evidence_sha256=package.evidence_sha256,
        entity_id=entity_id,
        family=family,
        reporting_period_end=reporting_period_end,
        basis=basis,
        framework=framework,
        publication_version=publication.version,
        publication_sha256=publication.published_config_sha256,
        publication_state=publication.state,
        dictionary_pin=config.pinned.dictionary,
        formula_set_pin=config.pinned.formula_set,
        mapping_set_pin=config.pinned.mapping_set,
        normalisation_policy_pin=config.pinned.normalisation_policy,
        alignment_rules_pin=config.pinned.alignment_rules,
        source_authority_pin=authority,
        extractor_pins=tuple(
            FirstPartyExtractorPin(
                representation=representation,
                version=pin.version,
                content_sha256=pin.content_sha256,
            )
            for representation, pin in (
                (Representation.PDF, config.pinned.extractor_pdf),
                (Representation.XBRL, config.pinned.extractor_xbrl),
            )
        ),
        fiscal_year_end_setting_id=qualification_context.settings_record_id,
        fiscal_year_end_setting_evidence_input_id=qualification_context.evidence_input_id,
        fiscal_year_end_setting_recorded_at=qualification_context.recorded_at,
        fiscal_year_end_month=qualification_context.fiscal_year_end_month,
        qualification_context_sha256=qualification_context.record_sha256,
        members=tuple(item for item, _, _ in member_rows),
        attempt_ids=attempt_ids,
        capture_free_attempt_ids=tuple(
            _stored_attempt_id(row) for row in attempts if row.capture is None
        ),
        alignment_proof_ids=tuple(_stored_proof_id(row.proof_id) for row in proofs),
    )


def _validate_qualification_context(
    expected: FirstPartyGenerationContext,
    *,
    interpretations: tuple[Interpretation, ...],
    repository: EvidenceRepository,
) -> FirstPartyGenerationContext:
    """Reprove the trace context, exact settings row, and current-setting identity."""
    reload_first_party_generation_context(repository, expected)
    require_first_party_generation_context(interpretations, expected)
    current = capture_first_party_generation_context(repository, expected.entity_id)
    if current != expected:
        raise FirstPartyGenerationError(
            "qualification setting changed during generation; stored context differs"
        )
    return current


def _attempts(
    reported: tuple[AcquisitionAttempt, ...],
    *,
    repository: EvidenceRepository,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    reporting_period_end: date,
) -> tuple[AcquisitionAttempt, ...]:
    ids = tuple(sorted(_stored_attempt_id(row) for row in reported))
    if len(ids) != len(set(ids)):
        raise FirstPartyGenerationError("ingest report contains duplicate attempt ids")
    stored = repository.get_attempts(ids)
    if tuple(_stored_attempt_id(row) for row in stored) != ids:
        raise FirstPartyGenerationError("ingest report attempt ids do not reload exactly")
    by_id = {_stored_attempt_id(row): row for row in reported}
    for row in stored:
        if row != by_id[_stored_attempt_id(row)] or (
            row.entity_id,
            row.period_end,
            row.basis,
            row.framework,
        ) != (entity_id, reporting_period_end, basis, framework):
            raise FirstPartyGenerationError("attempt does not match the requested stored scope")
        if row.attempted_at is None:
            raise FirstPartyGenerationError("stored attempt has no database attempted-at time")
    return stored


def _member(
    reported: IngestMemberGeneration,
    *,
    package: FilingPackage,
    attempts: tuple[AcquisitionAttempt, ...],
    repository: EvidenceRepository,
    config: LoadedConfig,
) -> tuple[FirstPartyGenerationMember, tuple[Occurrence, ...], tuple[Interpretation, ...]]:
    package_member = package.members.get(reported.representation)
    if package_member is None or package_member.capture.capture_ref_id != reported.capture_ref_id:
        raise FirstPartyGenerationError("reported generation is not a member of the stored package")
    capture = _one(repository.get_capture_refs([reported.capture_ref_id]), "capture")
    if capture != package_member.capture or (capture.source_id, capture.surface) != (
        reported.source_id,
        reported.surface,
    ):
        raise FirstPartyGenerationError("reported member capture identity does not reload exactly")
    extractor_pin = (
        config.pinned.extractor_xbrl
        if reported.representation is Representation.XBRL
        else config.pinned.extractor_pdf
    )
    if reported.extractor_version != extractor_pin.version:
        raise FirstPartyGenerationError("reported member extractor differs from the published pin")
    occurrences = repository.get_occurrences(reported.occurrence_ids)
    if tuple(_stored_occurrence_id(row) for row in occurrences) != reported.occurrence_ids:
        raise FirstPartyGenerationError("reported occurrence ids do not reload exactly")
    for row in occurrences:
        if (
            row.capture.capture_ref_id != reported.capture_ref_id
            or row.representation is not reported.representation
            or row.extractor_version != extractor_pin.version
        ):
            raise FirstPartyGenerationError("occurrence escapes the reported member generation")
    interpretations = repository.get_interpretations(reported.interpretation_ids)
    if (
        tuple(_stored_interpretation_id(row) for row in interpretations)
        != reported.interpretation_ids
    ):
        raise FirstPartyGenerationError("reported interpretation ids do not reload exactly")
    _validate_interpretations(
        interpretations,
        occurrence_ids=set(reported.occurrence_ids),
        member=reported,
        package=package,
        config=config,
    )
    member_attempts = tuple(
        row
        for row in attempts
        if row.capture is not None and row.capture.capture_ref_id == reported.capture_ref_id
    )
    attempted = tuple(row.attempted_at for row in member_attempts if row.attempted_at is not None)
    recorded = tuple(row.recorded_at for row in interpretations)
    qualified = tuple(row for row in interpretations if row.qualification_ref is not None)
    return (
        FirstPartyGenerationMember(
            representation=reported.representation,
            source_id=capture.source_id,
            surface=capture.surface,
            capture_ref_id=reported.capture_ref_id,
            blob_sha256=capture.blob_sha256,
            record_sha256=capture.record_sha256,
            capture_registered_at=capture.registered_at,
            capture_first_seen_at=capture.first_seen_at,
            extractor_pin=extractor_pin,
            occurrence_ids=reported.occurrence_ids,
            attempt_ids=tuple(_stored_attempt_id(row) for row in member_attempts),
            extraction_context_sha256s=tuple(
                sorted(
                    {
                        row.extraction_context_sha256
                        for row in member_attempts
                        if row.extraction_context_sha256 is not None
                    }
                )
            ),
            attempted_at_min=min(attempted, default=None),
            attempted_at_max=max(attempted, default=None),
            interpretation_ids=reported.interpretation_ids,
            interpretation_recorded_at_min=min(recorded),
            interpretation_recorded_at_max=max(recorded),
            qualified_interpretation_ids=tuple(_stored_interpretation_id(row) for row in qualified),
            qualification_condition_ids=tuple(
                sorted(
                    {
                        condition.condition_id
                        for row in qualified
                        for condition in row.condition_evidence
                    }
                )
            ),
            qualification_evidence_interpretation_ids=tuple(
                sorted(
                    {
                        evidence_id
                        for row in qualified
                        for condition in row.condition_evidence
                        for evidence_id in condition.evidence_interpretation_ids
                    }
                )
            ),
        ),
        occurrences,
        interpretations,
    )


def _validate_interpretations(
    rows: tuple[Interpretation, ...],
    *,
    occurrence_ids: set[int],
    member: IngestMemberGeneration,
    package: FilingPackage,
    config: LoadedConfig,
) -> None:
    ids = {_stored_interpretation_id(row) for row in rows}
    direct_occurrences: set[int] = set()
    by_id = {_stored_interpretation_id(row): row for row in rows}
    for row in rows:
        if (
            row.capture_ref_id != member.capture_ref_id
            or row.representation is not member.representation
            or (row.entity_id, row.basis, row.framework)
            != (package.entity_id, package.basis, package.framework)
            or row.dictionary_version != config.pinned.dictionary.version
            or row.mapping_set_version != config.pinned.mapping_set.version
            or row.normalisation_policy_version != config.pinned.normalisation_policy.version
            or row.extractor_version != member.extractor_version
        ):
            raise FirstPartyGenerationError(
                "interpretation escapes the exact published member scope or pins"
            )
        if row.origin is InterpretationOrigin.DIRECT:
            if row.occurrence_id not in occurrence_ids or row.operand_interpretation_ids:
                raise FirstPartyGenerationError(
                    "direct interpretation has invalid occurrence closure"
                )
            direct_occurrences.add(row.occurrence_id)
        elif (
            row.occurrence_id is not None
            or row.construction_rule_id is None
            or not row.operand_interpretation_ids
            or not set(row.operand_interpretation_ids) <= ids
        ):
            raise FirstPartyGenerationError(
                "constructed interpretation has invalid operand closure"
            )
    if direct_occurrences != occurrence_ids:
        raise FirstPartyGenerationError("direct interpretations do not cover exact occurrences")
    _validate_acyclic_closure(by_id)


def _validate_acyclic_closure(rows: Mapping[int, Interpretation]) -> None:
    complete: set[int] = set()

    def visit(row_id: int, active: set[int]) -> None:
        if row_id in complete:
            return
        if row_id in active:
            raise FirstPartyGenerationError("interpretation operand closure contains a cycle")
        active.add(row_id)
        for operand_id in rows[row_id].operand_interpretation_ids:
            visit(operand_id, active)
        active.remove(row_id)
        complete.add(row_id)

    for row_id in rows:
        visit(row_id, set())


def _alignment_proofs(
    package: FilingPackage,
    occurrences: tuple[Occurrence, ...],
    interpretations: tuple[Interpretation, ...],
    *,
    repository: EvidenceRepository,
    config: LoadedConfig,
) -> tuple[AlignmentProof, ...]:
    keys = {row.key.digest(): row.key for row in interpretations if row.key is not None}
    if not keys:
        return ()
    cutoff = max(
        *(row.recorded_at for row in interpretations),
        *(member.capture.first_seen_at for member in package.members.values()),
    )
    boundary = EligibilityBoundary(
        knowledge_cutoff=package.knowledge_time,
        first_seen_cutoff=cutoff,
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
    proofs = prove_alignment(package, selections, config.alignment_rules)
    stored = repository.put_alignment_proofs(proofs) if proofs else ()
    exact_ids = {_stored_interpretation_id(row) for row in interpretations}
    for proof in stored:
        if (
            proof.package_id != package.package_id
            or not {interpretation_id for interpretation_id, _ in proof.participants} <= exact_ids
        ):
            raise FirstPartyGenerationError(
                "alignment proof escapes the exact published generation"
            )
    return stored


def _validate_package(
    package: FilingPackage,
    *,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    family: FilingFamily,
    reporting_period_end: date,
) -> None:
    if (
        package.entity_id,
        package.basis,
        package.framework,
        package.family,
        package.reporting_period_end,
    ) != (entity_id, basis, framework, family, reporting_period_end):
        raise FirstPartyGenerationError("stored package differs from the requested scope")


def _one[T](rows: tuple[T, ...], label: str) -> T:
    if len(rows) != 1:
        raise FirstPartyGenerationError(f"expected exactly one stored {label}, found {len(rows)}")
    return rows[0]


def _stored_attempt_id(row: AcquisitionAttempt) -> int:
    if row.attempt_id is None:
        raise FirstPartyGenerationError("ingest report contains an unstored attempt")
    return row.attempt_id


def _stored_occurrence_id(row: Occurrence) -> int:
    if row.occurrence_id is None:
        raise FirstPartyGenerationError("ingest report contains an unstored occurrence")
    return row.occurrence_id


def _stored_interpretation_id(row: Interpretation) -> int:
    if row.interpretation_id is None:
        raise FirstPartyGenerationError("ingest report contains an unstored interpretation")
    return row.interpretation_id


def _stored_proof_id(proof_id: int | None) -> int:
    if proof_id is None:
        raise FirstPartyGenerationError("alignment proof was not stored")
    return proof_id
