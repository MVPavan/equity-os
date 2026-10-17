"""Ingest one first-party results package from retained originals (D1a Task 5).

Pins, authority, staging, extraction (with identity, period and framework checks),
presence, attempt generations, interpretation, package and segment members, with three
reuse levels (data spec l.346: re-mapping adds, never rewrites): (1) a capture
registration is always reused; (2) an attempt generation is reused under the same
content-pinned extractor and request scope, with mapping/spec-dependent decisions pinned
separately; (3) interpretations are reused under the same
(mapping set, normalisation policy, extractor) triple and scope. The mapping set and
normalisation policy and extractor versions are pinned before any reuse or write.
Re-ingesting unchanged inputs writes nothing new.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    InterpretationTriple,
    KnowledgeTimeStatus,
    Occurrence,
    PackageMember,
    RevisionCause,
    RunMode,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import SnapshotError, canonical_sha256
from fundamentals.contracts.source_catalog import SourceCatalog, SourceClass, UnknownSourceError
from fundamentals.contracts.source_registration import SourceRegistrationError
from fundamentals.evidence.capture_intake import (
    NSE_WALL_ZONE,
    SURFACE_OF,
    TRANSCRIPT_SURFACE,
    IntakeError,
    RetainedCaptureBinding,
    RetainedIntake,
    authorise,
    parse_filed_at,
    stage_retained_member,
)
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.capture_retention import capture_registration
from fundamentals.evidence.first_party_extract import (
    IngestError,
    IngestRequest,
    MemberGeneration,
    _read_xbrl,
    extract_member,
    stored_capture,
)
from fundamentals.evidence.interpret import SEGMENT_AXIS
from fundamentals.evidence.mapping import (
    CONTEXT_LOCAL_NAME,
    CONTEXT_SCHEMA_IDENTITY,
    MappingSet,
    NormalisationPolicy,
    in_namespace,
)
from fundamentals.evidence.pdf_adapter import PDF_EXTRACTOR_VERSION
from fundamentals.evidence.presence import reporting_kind, statements_present
from fundamentals.evidence.repository import (
    EvidenceRepository,
    InterpretationConflictError,
    VersionPin,
)
from fundamentals.evidence.repository_rows import SegmentMemberWrite
from fundamentals.evidence.selection import (
    differing_restatement,
    period_end,
    select_key,
    select_package,
)
from fundamentals.evidence.xbrl_adapter import (
    SEGMENT_DESCRIPTION_CONCEPT,
    XBRL_EXTRACTOR_VERSION,
    member_slug,
)
from fundamentals.extract.pdf_statement_pages import StatementPageSpec
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.store.snapshot_store import SnapshotStore

__all__ = ["IngestError", "IngestReport", "admit_transcript", "ingest_first_party"]

_LOG = structlog.get_logger(__name__)
MAX_INTERPRETATION_RETRIES = 3
MAPPING_SET_ARTIFACT = "mapping_set"
NORMALISATION_POLICY_ARTIFACT = "normalisation_policy"
DEFAULT_EXTRACTOR_VERSIONS: Mapping[Representation, str] = {
    Representation.XBRL: XBRL_EXTRACTOR_VERSION,
    Representation.PDF: PDF_EXTRACTOR_VERSION,
}
_MEMBER_ORDER = (Representation.XBRL, Representation.PDF)
_NOT_AUTHORISED = "source {source_id!r} is not an authorised first-party {representation} source"
_NOT_TRANSCRIPT = "source {source_id!r} is not a declared diagnostic-only first-party source"
_NO_FISCAL_YEAR_END = "entity {entity_id} has no evidenced fiscal-year-end month"
_STAGING_FAILED = "members failed to stage: {members}"
_REUSE_REJECTED = "reused XBRL generation no longer passes its pinned checks: {outcome}"
_RETRIES_EXHAUSTED = "interpretations of capture {capture} conflicted {count} times"
_SCOPE_CONFLICT = (
    "capture {capture} has interpretations under this triple for another entity, basis or "
    "framework; refusing to reuse or add to them"
)


class IngestReport(BaseModel):
    """What one ingest invocation stored or reused."""

    model_config = ConfigDict(frozen=True)

    package_id: int | None
    occurrence_count: int
    interpretation_counts: Mapping[InterpretationStatus, int]
    attempts: tuple[AcquisitionAttempt, ...]


def ingest_first_party(
    *,
    intake: RetainedIntake,
    catalog: SourceCatalog,
    snapshot_store: SnapshotStore,
    repository: EvidenceRepository,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    family: FilingFamily,
    reporting_period_end: date,
    pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None,
    supersedes_package_id: int | None = None,
    replaced_statements: frozenset[StatementFamily] = frozenset(),
    extractor_versions: Mapping[Representation, str] | None = None,
) -> IngestReport:
    """Stage, extract, interpret and package one filing's members (see module docstring).

    Raises ``VersionContentDriftError`` (nothing written) when the mapping set or policy
    version is already pinned to other content.
    """
    # Share the comparison runner's source hash so ingest and replay enforce one pin.
    from fundamentals.compare.run_config import extractor_pin

    versions = {**DEFAULT_EXTRACTOR_VERSIONS, **(extractor_versions or {})}
    extractor_pins = [
        VersionPin(
            artifact=f"extractor_{representation.value.lower()}",
            version=versions[representation],
            content_sha256=extractor_pin(
                representation, version=versions[representation]
            ).content_sha256,
        )
        for representation in sorted({binding.representation for binding in intake.bindings})
    ]
    repository.pin_versions(
        [
            VersionPin(
                artifact=MAPPING_SET_ARTIFACT,
                version=mapping_set.version,
                content_sha256=mapping_set.content_sha256,
            ),
            VersionPin(
                artifact=NORMALISATION_POLICY_ARTIFACT,
                version=policy.version,
                content_sha256=policy.content_sha256,
            ),
            *extractor_pins,
        ]
    )
    request = IngestRequest(
        entity_id=entity_id, period_end=reporting_period_end, basis=basis, framework=framework
    )
    fiscal_year_end_month = _fiscal_year_end_month(repository, entity_id, reporting_period_end)
    member_failures: list[AcquisitionAttempt] = []
    failed_staging: list[str] = []
    pending: list[MemberGeneration] = []
    bindings = sorted(intake.bindings, key=lambda item: _MEMBER_ORDER.index(item.representation))
    for binding in bindings:
        if (
            authorise(binding, catalog=catalog, results_pdf_source_id=intake.results_pdf_source_id)
            is None
        ):
            member_failures.append(
                request.attempt(
                    binding,
                    ExtractionOutcome.NOT_AUTHORISED,
                    stage=AttemptStage.ACQUISITION,
                    capture=None,
                    reason=_NOT_AUTHORISED.format(
                        source_id=binding.source_id, representation=binding.representation
                    ),
                )
            )
            continue
        try:
            capture = _registered(
                repository,
                snapshot_store,
                intake,
                binding,
                SURFACE_OF[binding.representation].value,
            )
        except (SourceRegistrationError, IntakeError, SnapshotError, OSError) as error:
            failed_staging.append(binding.representation.value)
            member_failures.append(
                request.attempt(
                    binding,
                    ExtractionOutcome.FAILED,
                    stage=AttemptStage.ACQUISITION,
                    capture=None,
                    reason=str(error),
                )
            )
            continue
        member = PackageMember(
            representation=binding.representation,
            capture=capture,
            knowledge_time=parse_filed_at(binding.filed_at_raw),
            knowledge_time_raw=binding.filed_at_raw,
            knowledge_time_status=KnowledgeTimeStatus.KNOWN,
        )
        filed_on = member.knowledge_time.astimezone(NSE_WALL_ZONE).date()
        identifiers = repository.issuer_identifiers(entity_id, as_of=filed_on)
        generation = extract_member(
            binding,
            member,
            intake=intake,
            repository=repository,
            request=request,
            identifiers=identifiers,
            mapping_set=mapping_set,
            pdf_specs=pdf_specs,
            extractor_version=versions[binding.representation],
        )
        # A reused XBRL generation answers to the identity governing its filing date today.
        reused = generation.stored and generation.outcome is ExtractionOutcome.COMPLETE
        if reused and binding.representation is Representation.XBRL:
            path = intake.input_anchor.path / binding.relative_path
            read = _read_xbrl(path, binding, member, identifiers, request, mapping_set)
            if read.outcome is not ExtractionOutcome.COMPLETE:
                raise IngestError(_REUSE_REJECTED.format(outcome=read.outcome.value))
        pending.append(generation)
    # Every member's capture, a reused generation's included, passes the D4.5 gate first.
    repository.refuse_ineligible([item.member.capture.capture_ref_id for item in pending])
    # Presence first, so a present family's unlocated PDF block fails inside its generation.
    present = _present(pending, mapping_set, reporting_period_end)
    extracted = [item.written(repository) for item in pending]
    usable = [item for item in extracted if item.outcome is ExtractionOutcome.COMPLETE]
    interpretations: list[Interpretation] = []
    comparative = (
        _ComparativeCheck(
            repository=repository,
            family=family,
            reporting_period_end=reporting_period_end,
            knowledge_time=max(item.member.knowledge_time for item in usable),
            triple=InterpretationTriple(
                mapping_set=mapping_set.version,
                normalisation_policy=policy.version,
                extractor_xbrl=versions[Representation.XBRL],
                extractor_pdf=versions[Representation.PDF],
            ),
            dictionary=dictionary,
        )
        if usable
        else None
    )
    for item in usable:
        scope = CaptureScope(
            capture=item.member.capture,
            entity_id=entity_id,
            basis=basis,
            framework=framework,
            mapping_set=mapping_set,
            policy=policy,
            dictionary=dictionary,
            fiscal_year_end_month=fiscal_year_end_month,
        )
        assert comparative is not None
        interpretations.extend(
            _interpretations(item, scope=scope, repository=repository, comparative=comparative)
        )
    package_id = None
    occurrences = [occurrence for item in usable for occurrence in item.occurrences]
    if usable:
        stored_present = _present(usable, mapping_set, reporting_period_end)
        package = FilingPackage(
            package_id=None,
            entity_id=entity_id,
            family=family,
            reporting_period_end=reporting_period_end,
            basis=basis,
            framework=framework,
            reporting_kind=reporting_kind(
                occurrences,
                period_end=reporting_period_end,
                fiscal_year_end_month=fiscal_year_end_month,
            ),
            knowledge_time=max(item.member.knowledge_time for item in usable),
            supersedes_package_id=supersedes_package_id,
            replaced_statements=replaced_statements,
            statements_present=frozenset(stored_present),
            members={item.binding.representation: item.member for item in usable},
            evidence_sha256=_package_sha256(usable, supersedes_package_id, replaced_statements),
        )
        package_id = repository.put_package(
            package,
            statement_evidence={
                family_: [_stored_id(occurrence) for occurrence in found]
                for family_, found in stored_present.items()
            },
        )
        repository.put_segment_members(_segment_members(occurrences, entity_id))
    # Unlocated families depend on the assembled package; capture reuse must not
    # reuse another package's presence decisions.
    extracted = [
        item.with_unlocated(present, request, package_id=package_id).written(repository)
        for item in extracted
    ]
    acquisition = [
        attempt.model_copy(update={"package_id": package_id}) for attempt in member_failures
    ]
    stored_acquisition = repository.put_attempts(acquisition) if acquisition else ()
    attempts = (*(a for item in extracted for a in item.attempts), *stored_acquisition)
    _LOG.info(
        "first-party ingest",
        entity_id=entity_id,
        period_end=str(reporting_period_end),
        package_id=package_id,
        occurrences=len(occurrences),
        interpretations=len(interpretations),
    )
    if failed_staging:
        raise IngestError(_STAGING_FAILED.format(members=", ".join(failed_staging)))
    return IngestReport(
        package_id=package_id,
        occurrence_count=len(occurrences),
        interpretation_counts=dict(Counter(item.status for item in interpretations)),
        attempts=attempts,
    )


def _fiscal_year_end_month(repository: EvidenceRepository, entity_id: int, period_end: date) -> int:
    """The evidenced fiscal-year-end month governing the period, as of the store clock."""
    record = repository.settings_as_of(
        entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock(), period_end
    )
    if record is None:
        raise IngestError(_NO_FISCAL_YEAR_END.format(entity_id=entity_id))
    return int(record.value_text)


def _registered(
    repository: EvidenceRepository,
    store: SnapshotStore,
    intake: RetainedIntake,
    binding: RetainedCaptureBinding,
    surface: str,
) -> CaptureReference:
    """The stored registration of these bytes, staging them only when none exists (level 1)."""
    with capture_registration(repository._pool) as registration:
        existing = registration.find(
            binding.source_id, surface, blob_sha256=binding.expected_sha256
        )
        if existing is not None:
            return existing
        staged = stage_retained_member(
            store, intake, binding.representation, surface=surface, clock=repository.store_clock
        )
        return registration.insert(staged, url=binding.url)


def admit_transcript(
    repository: EvidenceRepository,
    store: SnapshotStore,
    intake: RetainedIntake,
    *,
    catalog: SourceCatalog,
) -> CaptureReference:
    """Register a transcript PDF intake as a diagnostic first-party capture (plan D4, Task 3b).

    Capture only: no package, extraction or interpretation, so comparison never reads it.
    The source must be declared first-party and diagnostic-only, else ``IngestError``.
    """
    binding = intake.binding(Representation.PDF)
    try:
        descriptor = catalog.describe(binding.source_id)
    except UnknownSourceError as error:
        raise IngestError(_NOT_TRANSCRIPT.format(source_id=binding.source_id)) from error
    if descriptor.source_class is not SourceClass.FIRST_PARTY or descriptor.may_reconcile:
        raise IngestError(_NOT_TRANSCRIPT.format(source_id=binding.source_id))
    return _registered(repository, store, intake, binding, TRANSCRIPT_SURFACE)


def _present(
    generations: Sequence[MemberGeneration], mapping_set: MappingSet, period_end: date
) -> Mapping[StatementFamily, tuple[Occurrence, ...]]:
    """Structural presence over the complete members' occurrences and located PDF blocks."""
    usable = [item for item in generations if item.outcome is ExtractionOutcome.COMPLETE]
    return statements_present(
        [occurrence for item in usable for occurrence in item.occurrences],
        period_end=period_end,
        anchors=mapping_set.statement_anchors,
        pdf_located=frozenset(family for item in usable for family in item.pdf_located),
    )


def _interpretations(
    item: MemberGeneration,
    *,
    scope: CaptureScope,
    repository: EvidenceRepository,
    comparative: _ComparativeCheck,
) -> tuple[Interpretation, ...]:
    """Reuse the capture's rows under the current triple, else interpret and append (level 3).

    Rows under the triple for another entity, basis or framework are never reused or added
    to: the ingest refuses.
    """
    capture_ref_id = stored_capture(item.member.capture)
    for _ in range(MAX_INTERPRETATION_RETRIES):
        stored = repository.list_capture_interpretations(capture_ref_id)
        current = tuple(
            row
            for row in stored
            if row.mapping_set_version == scope.mapping_set.version
            and row.normalisation_policy_version == scope.policy.version
            and row.extractor_version == item.extractor_version
        )
        if any(
            (row.entity_id, row.basis, row.framework)
            != (scope.entity_id, scope.basis, scope.framework)
            for row in current
        ):
            raise IngestError(_SCOPE_CONFLICT.format(capture=capture_ref_id))
        occurrence_ids = {_stored_id(occurrence) for occurrence in item.occurrences}
        active_direct = tuple(row for row in current if row.occurrence_id in occurrence_ids)
        direct_ids = {row.interpretation_id for row in active_direct}
        active_constructed = tuple(
            row
            for row in current
            if row.origin is InterpretationOrigin.CONSTRUCTED
            and row.operand_interpretation_ids
            and set(row.operand_interpretation_ids) <= direct_ids
        )
        if occurrence_ids <= {row.occurrence_id for row in active_direct}:
            return (*active_direct, *active_constructed)
        prior = [row for row in stored if row not in current]
        prior_occurrences = {row.occurrence_id for row in prior if row.occurrence_id is not None}
        prior_anchor_keys = {
            _stored_id(occurrence): occurrence.anchor_key
            for occurrence in repository.get_occurrences(sorted(prior_occurrences))
        }
        recorded_at = repository.store_clock()
        existing_direct = {row.occurrence_id: row for row in active_direct}
        first_reservation = True

        def reserve_ids(
            count: int, existing_rows: Mapping[int | None, Interpretation] = existing_direct
        ) -> tuple[int, ...]:
            """Keep existing direct ids while appending a newly located family's rows."""
            nonlocal first_reservation
            if not first_reservation:
                return repository.reserve_interpretation_ids(count)
            first_reservation = False
            new_ids = iter(repository.reserve_interpretation_ids(count - len(existing_rows)))
            reserved: list[int] = []
            for occurrence in item.occurrences:
                existing = existing_rows.get(occurrence.occurrence_id)
                if existing is None:
                    reserved.append(next(new_ids))
                else:
                    assert existing.interpretation_id is not None
                    reserved.append(existing.interpretation_id)
            return tuple(reserved)

        written = comparative.causes(
            interpret_generation(
                item.occurrences,
                scope=scope,
                prior=prior,
                prior_anchor_keys=prior_anchor_keys,
                reserve_ids=reserve_ids,
                recorded_at=recorded_at,
            ),
            registered_at=recorded_at,
        )
        existing_constructions = {
            (row.construction_rule_id, row.input_digest): row for row in active_constructed
        }
        replacements = {
            row.interpretation_id: existing_constructions[
                (row.construction_rule_id, row.input_digest)
            ].interpretation_id
            for row in written
            if row.origin is InterpretationOrigin.CONSTRUCTED
            and (row.construction_rule_id, row.input_digest) in existing_constructions
        }
        merged: list[Interpretation] = []
        additions: list[Interpretation] = []
        for row in written:
            existing = (
                existing_direct.get(row.occurrence_id)
                if row.origin is InterpretationOrigin.DIRECT
                else existing_constructions.get((row.construction_rule_id, row.input_digest))
            )
            if existing is not None:
                merged.append(existing)
                continue
            row = row.model_copy(
                update={
                    "condition_evidence": tuple(
                        proof.model_copy(
                            update={
                                "evidence_interpretation_ids": tuple(
                                    replacements.get(id_, id_)
                                    for id_ in proof.evidence_interpretation_ids
                                )
                            }
                        )
                        for proof in row.condition_evidence
                    )
                }
            )
            merged.append(row)
            additions.append(row)
        try:
            repository.put_interpretations(additions)
        except InterpretationConflictError:
            _LOG.warning("interpretation conflict; retrying", capture_ref_id=capture_ref_id)
            continue
        return tuple(merged)
    raise IngestError(
        _RETRIES_EXHAUSTED.format(capture=capture_ref_id, count=MAX_INTERPRETATION_RETRIES)
    )


class _ComparativeCheck:
    """The ingest-time comparative test (Task 6), with per-ingest read caches.

    The eligible original is the package already stored for the comparative's period end,
    selected under the honest ingest boundary (filed no later than this package, stored
    before this ingest) and read ``RETROSPECTIVE`` under this ingest's own versions — in the
    comparative's representation if the original has it, else XBRL, else PDF.
    """

    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        family: FilingFamily,
        reporting_period_end: date,
        knowledge_time: datetime,
        triple: InterpretationTriple,
        dictionary: CanonicalDictionary,
    ) -> None:
        self._repository = repository
        self._family = family
        self._period_end = reporting_period_end
        self._knowledge_time = knowledge_time
        self._triple = triple
        self._dictionary = dictionary
        self._packages: dict[date, tuple[FilingPackage, ...]] = {}
        self._rows: dict[int, tuple[tuple[Occurrence, ...], tuple[Interpretation, ...]]] = {}

    def causes(
        self, written: Sequence[Interpretation], *, registered_at: datetime
    ) -> tuple[Interpretation, ...]:
        """Each row unchanged, or ``COMPARATIVE_RESTATEMENT`` when it differs from its original."""
        boundary = EligibilityBoundary.for_ingest(self._knowledge_time, registered_at)
        return tuple(self._cause(row, boundary) for row in written)

    def _cause(self, row: Interpretation, boundary: EligibilityBoundary) -> Interpretation:
        """One row's comparative cause (design decision 10 step 2)."""
        if (
            row.key is None
            or row.revision_cause is not RevisionCause.ORIGINAL
            or row.supersedes_interpretation_id is not None
            or period_end(row.key.period) == self._period_end
        ):
            return row
        end = period_end(row.key.period)
        if end not in self._packages:
            self._packages[end] = self._repository.list_packages(row.entity_id, self._family, end)
        original = select_package(
            self._packages[end],
            entity_id=row.entity_id,
            family=self._family,
            statement_family=self._dictionary.row(row.key.canonical_id).family,
            basis=row.basis,
            framework=row.framework,
            period_end=end,
            boundary=boundary,
        )
        if original is None:
            return row
        representation = next(
            item
            for item in (row.representation, Representation.XBRL, Representation.PDF)
            if item in original.members
        )
        occurrences, interpretations = self._member_rows(original, representation)
        selected = select_key(
            row.key,
            representation,
            package=original,
            occurrences=occurrences,
            interpretations=interpretations,
            boundary=boundary,
            mode=RunMode.RETROSPECTIVE,
            pinned=self._triple,
        )
        if not differing_restatement(selected, [row]):
            return row
        return row.model_copy(update={"revision_cause": RevisionCause.COMPARATIVE_RESTATEMENT})

    def _member_rows(
        self, package: FilingPackage, representation: Representation
    ) -> tuple[tuple[Occurrence, ...], tuple[Interpretation, ...]]:
        """A member capture's occurrences and interpretations, read once per ingest."""
        capture_ref_id = stored_capture(package.members[representation].capture)
        if capture_ref_id not in self._rows:
            self._rows[capture_ref_id] = (
                self._repository.list_capture_occurrences(capture_ref_id),
                self._repository.list_capture_interpretations(capture_ref_id),
            )
        return self._rows[capture_ref_id]


def _segment_members(occurrences: Sequence[Occurrence], entity_id: int) -> list[SegmentMemberWrite]:
    """One member per evidenced segment description, valid from its earliest period start."""
    found: dict[str, tuple[str, list[Occurrence]]] = {}
    for occurrence in occurrences:
        context = occurrence.native_context
        if context.get(CONTEXT_LOCAL_NAME) != SEGMENT_DESCRIPTION_CONCEPT or not in_namespace(
            context, str(context.get(CONTEXT_SCHEMA_IDENTITY))
        ):
            continue
        text = (occurrence.raw_value_text or "").strip()
        if not text or occurrence.period is None:
            continue
        found.setdefault(member_slug(text), (text, []))[1].append(occurrence)
    members = []
    for slug, (text, evidence) in sorted(found.items()):
        starts = [
            occurrence.period.start or occurrence.period.instant
            for occurrence in evidence
            if occurrence.period is not None
        ]
        members.append(
            SegmentMemberWrite(
                entity_id=entity_id,
                axis=SEGMENT_AXIS,
                member=slug,
                display_name=text,
                valid_from=min(day for day in starts if day is not None),
                evidence_occurrence_ids=tuple(sorted(_stored_id(item) for item in evidence)),
            )
        )
    return members


def _package_sha256(
    usable: Sequence[MemberGeneration],
    supersedes_package_id: int | None,
    replaced_statements: frozenset[StatementFamily],
) -> str:
    """Content identity of a package: its members' bytes, what it supersedes and replaces."""
    return canonical_sha256(
        {
            "members": {
                item.binding.representation.value: item.binding.expected_sha256 for item in usable
            },
            "supersedes_package_id": supersedes_package_id,
            "replaced_statements": sorted(family.value for family in replaced_statements),
        }
    )


def _stored_id(occurrence: Occurrence) -> int:
    """A stored occurrence's id."""
    if occurrence.occurrence_id is None:
        raise IngestError("occurrence is not stored")
    return occurrence.occurrence_id
