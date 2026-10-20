"""Ingest one shareholding generation's first-party submissions (plan D8 Task 4, R8).

Each retained SHP instance is one ``SHAREHOLDING`` package (``STANDALONE``, framework
``UNKNOWN``, period end the filed instant, knowledge time the listing's broadcast time).
Later broadcasts supersede earlier ones through the existing package lineage. Bytes are read
only through D9's ``read_retained``, so an expired or purging capture is refused
(``ORIGINAL_EXPIRED``) before any write. An extraction refusal is one attempt and nothing else.
Re-ingesting unchanged inputs reuses the attempt generation, occurrences, interpretations
and package, and writes nothing. A failed listing or SHP request is recorded apart from usable
evidence as one capture-less ``ACQUISITION`` attempt (``failed_attempt``).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import date
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import (
    ExtractionOutcome,
    OutcomeCode,
    OutcomeRecord,
    extraction_outcome_for,
)
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation, StatementFamily
from fundamentals.contracts.evidence import (
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
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import BodyCompleteness, canonical_sha256
from fundamentals.contracts.source_catalog import surface_authority
from fundamentals.evidence.capture_intake import parse_filed_at
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.capture_retention import read_retained
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.member_identity import IssuerIdentifiers
from fundamentals.evidence.repository import EvidenceRepository, VersionPin
from fundamentals.evidence.selection import select_package
from fundamentals.evidence.shareholding_filing import (
    SHP_EXTRACTOR_VERSION,
    ShareholdingListing,
    extract_shareholding,
)
from fundamentals.ingest.shareholding_filing import listing_date
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.store.snapshot_store import SnapshotStore

if TYPE_CHECKING:
    from fundamentals.compare.run_config import LoadedConfig

_LOG = structlog.get_logger(__name__)
BASIS = Basis.STANDALONE  # R4: the filing declares neither basis nor framework
FRAMEWORK = AccountingFramework.UNKNOWN
_NATIVE_KIND = "shareholding-discovery"
_TRANSPORT = frozenset({"TIMEOUT", "TRANSPORT_ERROR"})
_FAILED = "request {key} failed: {outcome}"
_NO_FISCAL_YEAR_END = "entity {entity_id} has no evidenced fiscal-year-end month"
_NOT_LISTED = "SHP instance {url} is not in the listing"


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
    """The mapping set, normalisation policy and ``nse-shp-v1`` content this ingest rests on."""
    from fundamentals.compare.run_config import extractor_pin

    extractor = extractor_pin(Representation.XBRL, family=FilingFamily.SHAREHOLDING)
    return [
        VersionPin(
            artifact="mapping_set",
            version=config.mapping_set.version,
            content_sha256=config.mapping_set.content_sha256,
        ),
        VersionPin(
            artifact="normalisation_policy",
            version=config.normalisation_policy.version,
            content_sha256=config.normalisation_policy.content_sha256,
        ),
        VersionPin(
            artifact="extractor_xbrl",
            version=extractor.version,
            content_sha256=extractor.content_sha256,
        ),
    ]


def failed_attempt(
    source_id: str, surface: str, request_key: str, outcome: str, *, entity_id: int, instant: date
) -> AcquisitionAttempt:
    """One failed listing or SHP request as a capture-less ``ACQUISITION`` attempt (R8)."""
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
    """Pin, read, extract, interpret and package each submission (see module docstring).

    Raises ``VersionContentDriftError`` (nothing written) when a pinned version names other
    content, and ``OriginalExpiredError`` (nothing written) for an expired capture.
    """
    repository.pin_versions(shareholding_pins(config))
    pool = repository._pool
    rows = json.loads(read_retained(pool, snapshots, generation.listing)[1])
    by_url = {str(row.get("xbrl", "")): row for row in rows}
    bodies = [(url, ref, read_retained(pool, snapshots, ref)[1]) for url, ref in generation.filings]
    submissions = []
    for url, ref, body in bodies:
        if url not in by_url:
            raise ValueError(_NOT_LISTED.format(url=url))
        raw = str(by_url[url]["broadcastDate"])
        listing = ShareholdingListing(
            instant=listing_date(by_url[url].get("date")),
            knowledge_time=parse_filed_at(raw.title()),
            knowledge_time_raw=raw,
        )
        submissions.append((listing, ref, body))
    scope_of = _scope(generation, repository, config)
    attempts: list[AcquisitionAttempt] = []
    packages: list[int] = []
    occurrences = interpretations = 0
    for listing, ref, body in sorted(submissions, key=lambda item: item[0].knowledge_time):
        attempt, found = _generation(generation, repository, ref, body, listing)
        attempts.append(attempt)
        if attempt.outcome is not ExtractionOutcome.COMPLETE:
            continue
        interpreted = _interpretations(found, scope_of(ref), repository)
        packages.append(_package(generation, repository, ref, listing, interpreted))
        occurrences += len(found)
        interpretations += len(interpreted)
    selected = None
    if packages:
        boundary = EligibilityBoundary(
            knowledge_cutoff=max(item[0].knowledge_time for item in submissions),
            first_seen_cutoff=repository.store_clock(),
        )
        head = select_package(
            repository.list_packages(
                generation.entity_id, FilingFamily.SHAREHOLDING, generation.instant
            ),
            entity_id=generation.entity_id,
            family=FilingFamily.SHAREHOLDING,
            statement_family=StatementFamily.SHAREHOLDING,
            basis=BASIS,
            framework=FRAMEWORK,
            period_end=generation.instant,
            boundary=boundary,
        )
        selected = head.package_id if head is not None else None
    _LOG.info(
        "shareholding ingest",
        entity_id=generation.entity_id,
        instant=str(generation.instant),
        packages=packages,
        occurrences=occurrences,
        interpretations=interpretations,
    )
    return ShareholdingIngestReport(
        packages=tuple(packages),
        selected=selected,
        attempts=tuple(attempts),
        occurrences=occurrences,
        interpretations=interpretations,
    )


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


def _scope(
    generation: ShareholdingGeneration, repository: EvidenceRepository, config: LoadedConfig
) -> Callable[[CaptureReference], CaptureScope]:
    """Each capture's interpretation scope under the evidenced fiscal-year-end month."""
    record = repository.settings_as_of(
        generation.entity_id,
        SettingKey.FISCAL_YEAR_END_MONTH,
        repository.store_clock(),
        generation.instant,
    )
    if record is None:
        raise LookupError(_NO_FISCAL_YEAR_END.format(entity_id=generation.entity_id))

    def scope(capture: CaptureReference) -> CaptureScope:
        return CaptureScope(
            capture=capture,
            entity_id=generation.entity_id,
            basis=BASIS,
            framework=FRAMEWORK,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            dictionary=config.dictionary,
            fiscal_year_end_month=int(record.value_text),
        )

    return scope


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
    """The submission's package, superseding the latest earlier broadcast at this instant."""
    assert listing.instant is not None
    earlier = [
        package
        for package in repository.list_packages(
            generation.entity_id, FilingFamily.SHAREHOLDING, listing.instant
        )
        if package.knowledge_time < listing.knowledge_time
    ]
    supersedes = earlier[-1].package_id if earlier else None
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
        reporting_period_end=listing.instant,
        basis=BASIS,
        framework=FRAMEWORK,
        reporting_kind=PeriodKind.INSTANT,
        knowledge_time=listing.knowledge_time,
        supersedes_package_id=supersedes,
        replaced_statements=frozenset(),
        statements_present=frozenset({StatementFamily.SHAREHOLDING}),
        members={Representation.XBRL: member},
        evidence_sha256=canonical_sha256(
            {"xbrl": ref.blob_sha256, "supersedes_package_id": supersedes}
        ),
    )
    keyed = sorted({row.occurrence_id for row in interpretations if row.key and row.occurrence_id})
    return repository.put_package(package, statement_evidence={StatementFamily.SHAREHOLDING: keyed})
