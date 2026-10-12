"""One package member's adapter invocation, or its reused generation (D1a Task 5, level 2).

An invocation reads the member's bytes and checks, before anything is kept, that the
capture is the requested one: the seeded issuer (identity), the package basis, the
requested period end and the requested accounting framework, each from the capture's own
declarations. The result is a **pending** generation — one overall ``EXTRACTION`` attempt
plus any family attempts, and the occurrences when ``COMPLETE`` — that the ingest writes in
one transaction once structural presence is known, so every attempt of the invocation
(unlocated-family failures included) shares one ``attempted_at`` and belongs to the
generation. A generation is reused only for the same capture, extractor version and
request scope (entity, period end, basis, framework); any other request runs every check
again. Parser failures of the documented kinds are one overall ``PARSE_FAILED`` attempt.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pymupdf
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    Occurrence,
    PackageMember,
    RevisionCause,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_intake import (
    SURFACE_OF,
    RetainedCaptureBinding,
    RetainedIntake,
)
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_STATEMENT_FAMILY,
    MappingSet,
    UnsupportedSchemaError,
)
from fundamentals.evidence.member_identity import (
    IdentityVerdict,
    IssuerIdentifiers,
    verify_pdf_framework,
    verify_pdf_identity,
    verify_pdf_period,
    verify_xbrl_framework,
    verify_xbrl_identity,
    verify_xbrl_period,
)
from fundamentals.evidence.pdf_adapter import read_pdf_occurrences
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.xbrl_adapter import occurrences_from_instance, parse_instance
from fundamentals.extract.pdf_statement_pages import StatementPageSpec
from fundamentals.extract.xbrl_parser import XbrlParseError
from fundamentals.ingest.pdf_source import LoadedPdf, PdfIntegrityError, load_pdf

_PIN_CHANGED = "{path} no longer matches its pinned SHA-256"
_NOT_LOCATED = "statement present in the package but its PDF block was not located"
_DECLARED = "verified: {evidence}"


class IngestError(RuntimeError):
    """A member could not be staged or read, or the package cannot be ingested at all."""


class IngestRequest(BaseModel):
    """The request identity every attempt of one ingest carries."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    period_end: date
    basis: Basis
    framework: AccountingFramework

    def attempt(
        self,
        binding: RetainedCaptureBinding,
        outcome: ExtractionOutcome,
        *,
        stage: AttemptStage,
        capture: CaptureReference | None,
        extractor_version: str = "",
        family: StatementFamily | None = None,
        package_id: int | None = None,
        reason: str | None = None,
    ) -> AcquisitionAttempt:
        """One attempt for one member binding."""
        return AcquisitionAttempt(
            attempt_id=None,
            stage=stage,
            source_id=binding.source_id,
            surface=SURFACE_OF[binding.representation].value,
            entity_id=self.entity_id,
            period_end=self.period_end,
            basis=self.basis,
            framework=self.framework,
            representation=binding.representation,
            statement_family=family,
            package_id=package_id,
            outcome=outcome,
            reason=reason,
            capture=capture,
            input_sha256=binding.expected_sha256,
            extractor_version=extractor_version,
            attempted_at=None,
        )


class MemberGeneration(BaseModel):
    """One staged member's attempt generation: stored (reused or written) or pending."""

    model_config = ConfigDict(frozen=True)

    binding: RetainedCaptureBinding
    member: PackageMember
    extractor_version: str
    outcome: ExtractionOutcome
    occurrences: tuple[Occurrence, ...]
    pdf_located: frozenset[StatementFamily]
    attempts: tuple[AcquisitionAttempt, ...]
    stored: bool

    def with_unlocated(
        self, present: Mapping[StatementFamily, object], request: IngestRequest
    ) -> MemberGeneration:
        """A pending PDF generation plus ``PARSE_FAILED`` for each present, unlocated family."""
        if self.stored or self.binding.representation is not Representation.PDF:
            return self
        failures = tuple(
            request.attempt(
                self.binding,
                ExtractionOutcome.PARSE_FAILED,
                stage=AttemptStage.EXTRACTION,
                capture=self.member.capture,
                extractor_version=self.extractor_version,
                family=family,
                reason=f"{_NOT_LOCATED}: {family.value}",
            )
            for family in sorted(present)
            if family not in self.pdf_located and family is not StatementFamily.DERIVED
        )
        return self.model_copy(update={"attempts": (*self.attempts, *failures)})

    def written(self, repository: EvidenceRepository) -> MemberGeneration:
        """The generation stored in one transaction (one shared ``attempted_at``)."""
        if self.stored:
            return self
        occurrences, attempts = repository.put_generation(self.occurrences, self.attempts)
        return self.model_copy(
            update={"occurrences": occurrences, "attempts": attempts, "stored": True}
        )


class _Read(BaseModel):
    """What one adapter invocation read: outcome, reason, occurrences and family results."""

    model_config = ConfigDict(frozen=True)

    outcome: ExtractionOutcome
    reason: str | None
    occurrences: tuple[Occurrence, ...] = ()
    family_failures: Mapping[StatementFamily, str] = {}
    located: frozenset[StatementFamily] = frozenset()


def extract_member(
    binding: RetainedCaptureBinding,
    member: PackageMember,
    *,
    intake: RetainedIntake,
    repository: EvidenceRepository,
    request: IngestRequest,
    identifiers: IssuerIdentifiers,
    mapping_set: MappingSet,
    pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None,
    extractor_version: str,
) -> MemberGeneration:
    """Reuse the member's generation for this request, or run its adapter (pending, unwritten)."""
    capture_ref_id = stored_capture(member.capture)
    generation = repository.list_generation_attempts(
        capture_ref_id,
        extractor_version,
        entity_id=request.entity_id,
        period_end=request.period_end,
        basis=request.basis,
        framework=request.framework,
    )
    overall = [attempt for attempt in generation if attempt.statement_family is None]
    if overall:
        occurrences: tuple[Occurrence, ...] = ()
        if overall[0].outcome is ExtractionOutcome.COMPLETE:
            occurrences = tuple(
                occurrence
                for occurrence in repository.list_capture_occurrences(
                    capture_ref_id, extractor_version
                )
                if occurrence.native_context.get(CONTEXT_BASIS) == request.basis.value
            )
        return MemberGeneration(
            binding=binding,
            member=member,
            extractor_version=extractor_version,
            outcome=overall[0].outcome,
            occurrences=occurrences,
            pdf_located=_located(occurrences, generation),
            attempts=generation,
            stored=True,
        )
    path = intake.input_anchor.path / binding.relative_path
    if binding.representation is Representation.XBRL:
        read = _read_xbrl(path, binding, member, identifiers, request, mapping_set)
    else:
        if pdf_specs is None:
            raise IngestError("a PDF member needs the issuer's PDF statement specs")
        read = _read_pdf(path, binding, member, identifiers, request, pdf_specs)

    def extraction(
        outcome: ExtractionOutcome, reason: str | None, family: StatementFamily | None = None
    ) -> AcquisitionAttempt:
        """One extraction attempt of this member under this extractor."""
        return request.attempt(
            binding,
            outcome,
            stage=AttemptStage.EXTRACTION,
            capture=member.capture,
            extractor_version=extractor_version,
            family=family,
            reason=reason,
        )

    complete = read.outcome is ExtractionOutcome.COMPLETE
    attempts = [extraction(read.outcome, read.reason)]
    attempts += [
        extraction(ExtractionOutcome.PARSE_FAILED, detail, family)
        for family, detail in sorted(read.family_failures.items())
    ]
    return MemberGeneration(
        binding=binding,
        member=member,
        extractor_version=extractor_version,
        outcome=read.outcome,
        occurrences=(
            _versioned(read.occurrences, extractor_version, repository, capture_ref_id)
            if complete
            else ()
        ),
        pdf_located=read.located if complete else frozenset(),
        attempts=tuple(attempts),
        stored=False,
    )


def stored_capture(capture: CaptureReference) -> int:
    """A registered capture's id."""
    if capture.capture_ref_id is None:
        raise IngestError("capture is not registered")
    return capture.capture_ref_id


def _read_xbrl(
    path: Path,
    binding: RetainedCaptureBinding,
    member: PackageMember,
    identifiers: IssuerIdentifiers,
    request: IngestRequest,
    mapping_set: MappingSet,
) -> _Read:
    """Parse one XBRL member and check identity, period and framework before reading it."""
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != binding.expected_sha256:
        raise IngestError(_PIN_CHANGED.format(path=path))
    try:
        instance = parse_instance(body, mapping_set=mapping_set)
    except UnsupportedSchemaError as error:
        return _Read(outcome=ExtractionOutcome.UNSUPPORTED_SCHEMA, reason=str(error))
    except XbrlParseError as error:
        return _Read(outcome=ExtractionOutcome.PARSE_FAILED, reason=str(error))
    framework = verify_xbrl_framework(instance, request.framework)
    rejected = _first_rejection(
        verify_xbrl_identity(instance, identifiers, basis=request.basis),
        verify_xbrl_period(instance, request.period_end),
        framework,
    )
    if rejected is not None:
        return rejected
    occurrences = occurrences_from_instance(
        instance, capture=member.capture, member=member, mapping_set=mapping_set
    )
    return _Read(
        outcome=ExtractionOutcome.COMPLETE,
        reason=_DECLARED.format(evidence="; ".join(framework.evidence)),
        occurrences=occurrences,
    )


def _read_pdf(
    path: Path,
    binding: RetainedCaptureBinding,
    member: PackageMember,
    identifiers: IssuerIdentifiers,
    request: IngestRequest,
    specs: Mapping[StatementFamily, StatementPageSpec],
) -> _Read:
    """Load one PDF member, check identity and framework, read its blocks, check the period."""
    try:
        pdf = load_pdf(
            source_id=binding.source_id, path=path, expected_sha256=binding.expected_sha256
        )
    except PdfIntegrityError as error:
        raise IngestError(str(error)) from error
    except pymupdf.FileDataError as error:
        return _Read(outcome=ExtractionOutcome.PARSE_FAILED, reason=str(error))
    try:
        identity = verify_pdf_identity(pdf, identifiers)
    except PdfIntegrityError as error:
        # The document opened but lacks the identity page: an unreadable member.
        return _Read(outcome=ExtractionOutcome.PARSE_FAILED, reason=str(error))
    framework = verify_pdf_framework(pdf, request.framework)
    rejected = _first_rejection(identity, framework)
    if rejected is not None:
        return rejected
    return _read_pdf_blocks(pdf, member, request, specs, framework)


def _read_pdf_blocks(
    pdf: LoadedPdf,
    member: PackageMember,
    request: IngestRequest,
    specs: Mapping[StatementFamily, StatementPageSpec],
    framework: IdentityVerdict,
) -> _Read:
    """Read a verified PDF's located blocks; the latest header period must be the request's."""
    result = read_pdf_occurrences(
        pdf, capture=member.capture, member=member, basis=request.basis, specs=specs
    )
    rejected = _first_rejection(verify_pdf_period(result.occurrences, request.period_end))
    if rejected is not None:
        return rejected
    # A located block with no parsable row fails here; a block that was not located fails
    # only when the package says the family is present (MemberGeneration.with_unlocated).
    return _Read(
        outcome=ExtractionOutcome.COMPLETE,
        reason=_DECLARED.format(evidence="; ".join(framework.evidence)),
        occurrences=result.occurrences,
        family_failures=result.family_failures,
        located=frozenset(
            family for family, found in result.locations.items() if found is not None
        ),
    )


def _first_rejection(*verdicts: IdentityVerdict) -> _Read | None:
    """``IDENTITY_REJECTED`` with the first failed verdict's reason, else ``None``."""
    for verdict in verdicts:
        if not verdict.verified:
            return _Read(outcome=ExtractionOutcome.IDENTITY_REJECTED, reason=verdict.reason)
    return None


def _versioned(
    occurrences: Sequence[Occurrence],
    extractor_version: str,
    repository: EvidenceRepository,
    capture_ref_id: int,
) -> tuple[Occurrence, ...]:
    """Stamp the extractor version; re-extracting a stored capture is ``PARSER_REEXTRACTION``."""
    earlier = any(
        occurrence.extractor_version != extractor_version
        for occurrence in repository.list_capture_occurrences(capture_ref_id)
    )
    cause = RevisionCause.PARSER_REEXTRACTION if earlier else RevisionCause.ORIGINAL
    return tuple(
        occurrence.model_copy(
            update={"extractor_version": extractor_version, "revision_cause": cause}
        )
        for occurrence in occurrences
    )


def _located(
    occurrences: Sequence[Occurrence], generation: Sequence[AcquisitionAttempt]
) -> frozenset[StatementFamily]:
    """Families a reused PDF generation located: its blocks' rows and its unparsed blocks.

    An unlocated family's failure says "not located" and is excluded.
    """
    families = {
        StatementFamily(str(occurrence.native_context[CONTEXT_STATEMENT_FAMILY]))
        for occurrence in occurrences
        if occurrence.representation is Representation.PDF
    }
    families.update(
        attempt.statement_family
        for attempt in generation
        if attempt.statement_family is not None
        and attempt.outcome is ExtractionOutcome.PARSE_FAILED
        and not (attempt.reason or "").startswith(_NOT_LOCATED)
    )
    return frozenset(families)
