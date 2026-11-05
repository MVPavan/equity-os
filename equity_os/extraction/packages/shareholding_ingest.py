"""Ingest one shareholding generation's first-party submissions (plan D8 Task 4, R8).

Each retained SHP instance is one ``SHAREHOLDING`` package (``STANDALONE``, ``UNKNOWN``, period
end the requested instant, knowledge time the listing's broadcast) superseding the latest earlier
broadcast; an instance listed at another instant is refused before any write. Bytes are read only
through D9's ``read_retained`` (an expired or purging capture is refused, ``ORIGINAL_EXPIRED``,
before any write). An extraction refusal is one attempt and nothing else; an unchanged re-ingest
writes nothing; a failed request is one capture-less ``ACQUISITION`` attempt. No calendar (R6).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
)
from equity_os.contracts.measurement.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    KnowledgeTimeStatus,
    Occurrence,
    PackageMember,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import (
    ExtractionOutcome,
    OutcomeCode,
    OutcomeRecord,
    extraction_outcome_for,
)
from equity_os.contracts.sourcing.snapshot import BodyCompleteness, canonical_sha256
from equity_os.contracts.sourcing.source_catalog import surface_authority
from equity_os.extraction.packages.capture_intake import parse_filed_at
from equity_os.extraction.packages.member_identity import IssuerIdentifiers
from equity_os.extraction.xbrl.shareholding_filing import (
    SHP_EXTRACTOR_VERSION,
    ShareholdingListing,
    extract_shareholding,
)
from equity_os.normalisation.mapping.capture_interpretation import (
    CaptureScope,
    interpret_generation,
)
from equity_os.normalisation.mapping.interpret import input_digest
from equity_os.sourcing.exchange.shareholding_filing import listing_date
from equity_os.storage.raw_files.capture_retention import read_retained
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository, VersionPin
from equity_os.verification.comparison.run_family import ANY_FISCAL_MONTH
from equity_os.verification.comparison.selection import select_package

if TYPE_CHECKING:
    from equity_os.verification.comparison.run_config import LoadedConfig

_LOG = structlog.get_logger(__name__)
BASIS = Basis.STANDALONE  # R4: the filing declares neither basis nor framework
FRAMEWORK = AccountingFramework.UNKNOWN
_NATIVE_KIND = "shareholding-discovery"
_TRANSPORT = frozenset({"TIMEOUT", "TRANSPORT_ERROR"})
_FAILED = "request {key} failed: {outcome}"
_NOT_LISTED = "SHP instance {url} is not listed at the requested instant {instant}"


class ShareholdingGeneration(BaseModel):
    """One generation's registered first-party captures and the issuer held at the instant."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    instant: date
    identifiers: IssuerIdentifiers
    listing: CaptureReference
    filings: tuple[tuple[str, CaptureReference], ...]  # (instance URL, its registration)


class ShareholdingIngestReport(BaseModel):
    """What one ingest stored or reused."""

    model_config = ConfigDict(frozen=True)

    packages: tuple[int, ...]
    selected: int | None
    attempts: tuple[AcquisitionAttempt, ...]
    occurrences: int
    interpretations: int


class _Outcome(BaseModel):
    """A failed request's capture-level outcome (no body), as ``extraction_outcome_for`` reads."""

    model_config = ConfigDict(frozen=True)

    outcome: OutcomeRecord
    effective_body_completeness: BodyCompleteness = BodyCompleteness.ABSENT


def shareholding_pins(config: LoadedConfig) -> list[VersionPin]:
    """The mapping set, normalisation policy and SHP extractor content this ingest rests on."""
    from equity_os.verification.comparison.run_config import extractor_pin

    extractor = extractor_pin(Representation.XBRL, family=FilingFamily.SHAREHOLDING)
    mapping_set, policy = config.mapping_set, config.normalisation_policy
    return [
        VersionPin(artifact=name, version=version, content_sha256=sha)
        for name, version, sha in (
            ("mapping_set", mapping_set.version, mapping_set.content_sha256),
            ("normalisation_policy", policy.version, policy.content_sha256),
            ("extractor_xbrl", extractor.version, extractor.content_sha256),
        )
    ]


def failed_attempt(
    source_id: str, surface: str, request_key: str, outcome: str, *, entity_id: int, instant: date
) -> AcquisitionAttempt:
    """One failed request as a capture-less ``ACQUISITION`` attempt (R8)."""
    code = OutcomeCode.TRANSPORT_ERROR if outcome in _TRANSPORT else OutcomeCode.REQUEST_REJECTED
    record = _Outcome(
        outcome=OutcomeRecord(code=code, native_kind=_NATIVE_KIND, native_value=outcome)
    )
    identity = {"source_id": source_id, "surface": surface, "request_key": request_key}
    return AcquisitionAttempt(
        attempt_id=None,
        stage=AttemptStage.ACQUISITION,
        source_id=source_id,
        surface=surface,
        entity_id=entity_id,
        period_end=instant,
        basis=BASIS,
        framework=FRAMEWORK,
        representation=surface_authority(source_id, surface).representation,
        statement_family=None,
        package_id=None,
        outcome=extraction_outcome_for(
            record, parse_failed=False, unsupported_schema=False, identity_rejected=False
        ),
        reason=_FAILED.format(key=request_key, outcome=outcome),
        capture=None,
        input_sha256=input_digest({**identity, "capture_id": None}),
        extractor_version="",  # an ACQUISITION attempt names no extractor (0001 check)
        attempted_at=None,
    )


def ingest_shareholding(
    generation: ShareholdingGeneration,
    *,
    repository: EvidenceRepository,
    snapshots: SnapshotStore,
    config: LoadedConfig,
) -> ShareholdingIngestReport:
    """Pin, read, extract, interpret and package each submission (see module docstring). Raises,
    with nothing written, ``VersionContentDriftError`` for a pin naming other content,
    ``OriginalExpiredError`` for an expired capture and ``ValueError`` for an off-instant one."""
    repository.pin_versions(shareholding_pins(config))
    pool, entity_id, instant = repository._pool, generation.entity_id, generation.instant
    rows = json.loads(read_retained(pool, snapshots, generation.listing)[1])
    at = {str(row.get("xbrl", "")): row for row in rows if listing_date(row.get("date")) == instant}
    submissions = []  # every body is read (expiry refused) before any write
    for url, ref in generation.filings:
        if url not in at:  # never stored under an instant it was not filed at
            raise ValueError(_NOT_LISTED.format(url=url, instant=instant))
        raw = str(at[url]["broadcastDate"])
        listing = ShareholdingListing(
            instant=instant,
            knowledge_time=parse_filed_at(raw.title()),
            knowledge_time_raw=raw,
        )
        submissions.append((listing, ref, read_retained(pool, snapshots, ref)[1]))
    scope = CaptureScope(
        capture=generation.listing,
        entity_id=generation.entity_id,
        basis=BASIS,
        framework=FRAMEWORK,
        mapping_set=config.mapping_set,
        policy=config.normalisation_policy,
        dictionary=config.dictionary,
        fiscal_year_end_month=ANY_FISCAL_MONTH,  # instants ignore the fiscal calendar (R6)
    )
    attempts: list[AcquisitionAttempt] = []
    packages: list[int] = []
    occurrences = interpretations = 0
    for listing, ref, body in sorted(submissions, key=lambda item: item[0].knowledge_time):
        attempt, found = _generation(generation, repository, ref, body, listing)
        attempts.append(attempt)
        if attempt.outcome is not ExtractionOutcome.COMPLETE:
            continue
        interpreted = _interpretations(found, scope.model_copy(update={"capture": ref}), repository)
        packages.append(_package(generation, repository, ref, listing, interpreted))
        occurrences += len(found)
        interpretations += len(interpreted)
    selected = None
    if packages:
        boundary = EligibilityBoundary(
            knowledge_cutoff=max(item[0].knowledge_time for item in submissions),
            first_seen_cutoff=repository.store_clock(),
        )
        listed = repository.list_packages(entity_id, FilingFamily.SHAREHOLDING, generation.instant)
        head = select_package(
            listed,
            entity_id=entity_id,
            family=FilingFamily.SHAREHOLDING,
            statement_family=StatementFamily.SHAREHOLDING,
            basis=BASIS,
            framework=FRAMEWORK,
            period_end=generation.instant,
            boundary=boundary,
        )
        selected = head.package_id if head is not None else None
    report = ShareholdingIngestReport(
        packages=tuple(packages),
        selected=selected,
        attempts=tuple(attempts),
        occurrences=occurrences,
        interpretations=interpretations,
    )
    _LOG.info("shareholding ingest", entity_id=entity_id, **report.model_dump(exclude={"attempts"}))
    return report


def _generation(
    generation: ShareholdingGeneration,
    repository: EvidenceRepository,
    ref: CaptureReference,
    body: bytes,
    listing: ShareholdingListing,
) -> tuple[AcquisitionAttempt, tuple[Occurrence, ...]]:
    """The stored extraction attempt and occurrences for this request, else a new generation."""
    assert ref.capture_ref_id is not None
    stored = repository.list_generation_attempts(
        ref.capture_ref_id,
        SHP_EXTRACTOR_VERSION,
        entity_id=generation.entity_id,
        period_end=generation.instant,
        basis=BASIS,
        framework=FRAMEWORK,
    )
    if stored:
        found = repository.list_capture_occurrences(ref.capture_ref_id, SHP_EXTRACTOR_VERSION)
        return stored[0], found if stored[0].outcome is ExtractionOutcome.COMPLETE else ()
    extraction = extract_shareholding(
        body, capture=ref, identifiers=generation.identifiers, listing=listing
    )
    attempt = AcquisitionAttempt(
        attempt_id=None,
        stage=AttemptStage.EXTRACTION,
        source_id=ref.source_id,
        surface=ref.surface,
        entity_id=generation.entity_id,
        period_end=generation.instant,
        basis=BASIS,
        framework=FRAMEWORK,
        representation=Representation.XBRL,
        statement_family=None,
        package_id=None,
        outcome=extraction.outcome,
        reason=extraction.reason,
        capture=ref,
        input_sha256=ref.blob_sha256,
        extractor_version=SHP_EXTRACTOR_VERSION,
        attempted_at=None,
    )
    found, (written,) = repository.put_generation(extraction.occurrences, [attempt])
    return written, found


def _interpretations(
    occurrences: Sequence[Occurrence], scope: CaptureScope, repository: EvidenceRepository
) -> tuple[Interpretation, ...]:
    """This generation's rows under the pinned versions and scope: reused, else written."""
    assert scope.capture.capture_ref_id is not None
    pins = (scope.mapping_set.version, scope.policy.version, SHP_EXTRACTOR_VERSION)
    stored = repository.list_capture_interpretations(scope.capture.capture_ref_id)
    current = tuple(
        row
        for row in stored
        if (row.mapping_set_version, row.normalisation_policy_version, row.extractor_version)
        == pins
    )
    if current:
        return current
    prior_ids = sorted({row.occurrence_id for row in stored if row.occurrence_id is not None})
    written = interpret_generation(
        occurrences,
        scope=scope,
        prior=stored,
        prior_anchor_keys={
            item.occurrence_id: item.anchor_key
            for item in repository.get_occurrences(prior_ids)
            if item.occurrence_id is not None
        },
        reserve_ids=repository.reserve_interpretation_ids,
        recorded_at=repository.store_clock(),
    )
    repository.put_interpretations(written)
    return written


def _package(
    generation: ShareholdingGeneration,
    repository: EvidenceRepository,
    ref: CaptureReference,
    listing: ShareholdingListing,
    interpretations: Sequence[Interpretation],
) -> int:
    """The submission's package (kept on re-ingest), superseding the latest earlier broadcast."""
    listed = repository.list_packages(
        generation.entity_id, FilingFamily.SHAREHOLDING, generation.instant
    )
    held = {
        (p.members[Representation.XBRL].capture.blob_sha256, p.knowledge_time): p.package_id
        for p in listed
    }
    if (package_id := held.get((ref.blob_sha256, listing.knowledge_time))) is not None:
        return package_id  # a re-ingest keeps its package, whatever was imported since
    earlier = [p for p in listed if p.knowledge_time < listing.knowledge_time]
    latest = max(earlier, key=lambda p: (p.knowledge_time, p.package_id or 0), default=None)
    supersedes = latest.package_id if latest else None  # by knowledge time, then id
    lineage = {"xbrl": ref.blob_sha256, "supersedes_package_id": supersedes}
    member = PackageMember(
        representation=Representation.XBRL,
        capture=ref,
        knowledge_time=listing.knowledge_time,
        knowledge_time_raw=listing.knowledge_time_raw,
        knowledge_time_status=KnowledgeTimeStatus.KNOWN,
    )
    package = FilingPackage(
        package_id=None,
        entity_id=generation.entity_id,
        family=FilingFamily.SHAREHOLDING,
        reporting_period_end=generation.instant,
        basis=BASIS,
        framework=FRAMEWORK,
        reporting_kind=PeriodKind.INSTANT,
        knowledge_time=listing.knowledge_time,
        supersedes_package_id=supersedes,
        replaced_statements=frozenset(),
        statements_present=frozenset({StatementFamily.SHAREHOLDING}),
        members={Representation.XBRL: member},
        evidence_sha256=canonical_sha256(lineage),
    )
    keyed = sorted({row.occurrence_id for row in interpretations if row.key and row.occurrence_id})
    return repository.put_package(package, statement_evidence={StatementFamily.SHAREHOLDING: keyed})
