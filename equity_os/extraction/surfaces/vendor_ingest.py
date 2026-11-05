"""Ingest one retained vendor capture: authority, one store read, adapter, interpretation.

Spec §3–§4. The catalog's role and retention authority are checked before the capture is
read. An unauthorised, missing or failed capture becomes one capture-less ``ACQUISITION``
attempt. Vendors declare no publication time, so occurrences carry knowledge time
``UNKNOWN``; the capture's store-clock registration time is its separate availability
boundary (``selection.is_eligible``), never the vendor's own retrieval claim.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    Interpretation,
    KnowledgeTimeStatus,
    MissingValueState,
    Occurrence,
    PrecisionKind,
    RevisionCause,
)
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import (
    ExtractionOutcome,
    OutcomeCode,
    extraction_outcome_for,
)
from equity_os.contracts.sourcing.snapshot import SnapshotError
from equity_os.contracts.sourcing.source_catalog import SurfaceNotAuthorisedError, surface_authority
from equity_os.normalisation.derivation.interval import RoundingPolicy
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary
from equity_os.normalisation.mapping.capture_interpretation import (
    CaptureScope,
    interpret_generation,
)
from equity_os.normalisation.mapping.interpret import input_digest
from equity_os.normalisation.mapping.mapping import MappingSet, NormalisationPolicy
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository, InterpretationConflictError

_LOG = structlog.get_logger(__name__)
_DASHES = ("-", "—", "–")
_NOT_RETAINED = "capture {capture_id} retained no complete body ({code})"
_FOREIGN = "adapter bound issuer {issuer!r} {basis}, not entity {entity_id} {requested}"


class VendorExtractionError(ValueError):
    """Typed refusal before any occurrence can be interpreted."""

    def __init__(self, outcome: ExtractionOutcome, detail: str) -> None:
        self.outcome = outcome
        super().__init__(detail)


class VendorExtraction(BaseModel):
    """Lossless native occurrences plus the honest outcome and pinned extraction context.

    ``issuer`` (NSE symbol or ISIN) and ``basis`` are what the adapter verified the capture
    against; occurrences are stored only when both match the request's seeded entity.
    """

    model_config = ConfigDict(frozen=True)
    occurrences: tuple[Occurrence, ...]
    outcome: ExtractionOutcome
    reasons: tuple[str, ...] = ()
    extraction_context_sha256: str | None = None
    issuer: str | None = None
    basis: Basis | None = None


class VendorIngestRequest(BaseModel):
    """One retained capture's store identity and the request scope it is ingested for."""

    model_config = ConfigDict(frozen=True)
    source_id: str
    surface: str
    request_key: str
    capture_id: str
    representation: Representation
    entity_id: int
    period_end: date
    basis: Basis
    framework: AccountingFramework


class VendorIngestReport(BaseModel):
    """What one ingest stored or reused."""

    model_config = ConfigDict(frozen=True)
    attempt: AcquisitionAttempt
    occurrences: tuple[Occurrence, ...] = ()
    interpretations: tuple[Interpretation, ...] = ()


def ingest_vendor(
    request: VendorIngestRequest,
    *,
    extract: Callable[..., VendorExtraction],
    extractor_version: str,
    snapshot_store: SnapshotStore,
    repository: EvidenceRepository,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    rounding_policy: RoundingPolicy,
    fiscal_year_end_month: int,
) -> VendorIngestReport:
    """Authority, register, extract and interpret one capture (see module docstring).

    ``extract(body, capture=, record=, extractor_version=)`` is a surface adapter. The
    authorised surface's extractor version is pinned to its source content first: changed
    content under a pinned version raises ``VersionContentDriftError`` before anything is read,
    stored or reused.
    """
    # Share the comparison runner's source hash so ingest and comparison enforce one pin.
    from equity_os.verification.comparison.run_config import (
        vendor_extractor_pin,
        vendor_version_pin,
    )

    try:
        surface_authority(request.source_id, request.surface)
        pin = vendor_extractor_pin(request.source_id, request.surface, version=extractor_version)
        repository.pin_versions([vendor_version_pin(pin)])
        identity = (request.source_id, request.surface, request.request_key, request.capture_id)
        record, body = snapshot_store.get_capture(*identity), b""
        if record.body is not None:  # a body-less record is its outcome alone (not_offered)
            record, body = snapshot_store.read_capture_verified(*identity)
    except SurfaceNotAuthorisedError as error:
        return _store(repository, request, ExtractionOutcome.NOT_AUTHORISED, str(error))
    except (SnapshotError, OSError) as error:
        return _store(repository, request, ExtractionOutcome.FAILED, str(error))
    sha256 = record.complete_body_sha256
    if record.outcome.code is not OutcomeCode.OK or sha256 is None:
        outcome = extraction_outcome_for(
            record, parse_failed=False, unsupported_schema=False, identity_rejected=False
        )
        detail = _NOT_RETAINED.format(capture_id=record.capture_id, code=record.outcome.code)
        return _store(repository, request, outcome, detail)
    registered_at = repository.store_clock()
    capture = repository.put_capture_ref(
        CaptureReference(
            capture_ref_id=None,
            source_id=request.source_id,
            surface=request.surface,
            request_key=request.request_key,
            capture_id=request.capture_id,
            blob_sha256=sha256,
            record_sha256=record.record_sha256,
            registered_at=registered_at,
            first_seen_at=registered_at,
        )
    )
    try:
        extraction = extract(
            body, capture=capture, record=record, extractor_version=extractor_version
        )
        _bound(extraction, request, repository)
    except VendorExtractionError as error:
        extraction = VendorExtraction(occurrences=(), outcome=error.outcome, reasons=(str(error),))
    report = _store(
        repository,
        request,
        extraction.outcome,
        "; ".join(extraction.reasons) or None,
        capture=capture,
        extraction=extraction,
        extractor_version=extractor_version,
    )
    scope = CaptureScope(
        capture=capture,
        entity_id=request.entity_id,
        basis=request.basis,
        framework=request.framework,
        mapping_set=mapping_set,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=fiscal_year_end_month,
        rounding_policy=rounding_policy,
    )
    interpretations = _interpretations(report.occurrences, scope, repository, extractor_version)
    _LOG.info(
        "vendor ingest",
        capture_id=request.capture_id,
        outcome=report.attempt.outcome.value,
        occurrences=len(report.occurrences),
        interpretations=len(interpretations),
    )
    return report.model_copy(update={"interpretations": interpretations})


def json_occurrence(
    capture: CaptureReference,
    *,
    extractor_version: str,
    label: str,
    lexeme: str | None,
    value: Decimal | None,
    raw_unit: str,
    raw_scale: int,
    period: PeriodInterval | None,
    native_context: Mapping[str, Any],
    anchor: Mapping[str, Any],
    disclosure: Mapping[str, Any],
    declared_precision: int | None = None,
) -> Occurrence:
    """One vendor JSON numeral: only an evidenced display precision is precision (spec §5)."""
    return Occurrence(
        occurrence_id=None,
        capture=capture,
        representation=surface_authority(capture.source_id, capture.surface).representation,
        extractor_version=extractor_version,
        native_field=label,
        raw_value_text=lexeme,
        raw_unit=raw_unit,
        raw_scale=raw_scale,
        raw_sign=-1 if value is not None and value < 0 else 1,
        precision_kind=PrecisionKind.UNSUPPORTED
        if declared_precision is None
        else PrecisionKind.FINITE,
        declared_precision=declared_precision,
        native_context=native_context,
        period=period,
        missing_state=missing_state(lexeme, value),
        disclosure=disclosure,
        anchor=anchor,
        anchor_key=input_digest(dict(anchor)),
        knowledge_time=None,
        knowledge_time_status=KnowledgeTimeStatus.UNKNOWN,
        first_seen_at=capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def missing_state(lexeme: str | None, value: Decimal | None) -> MissingValueState:
    """The source's own no-value marker, never zero-filled (spec §4)."""
    text = (lexeme or "").strip()
    if lexeme is None:
        return MissingValueState.SOURCE_NULL
    if not text:
        return MissingValueState.BLANK
    if text in _DASHES:
        return MissingValueState.DASH
    if text.lower() == "nil":
        return MissingValueState.NIL
    return MissingValueState.ZERO_PRINTED if value == 0 else MissingValueState.VALUE


def month_period(label: str, months: int) -> PeriodInterval | None:
    """A ``Mon YYYY`` label as the ``months``-long duration ending that month, or ``None``."""
    try:
        month_end = datetime.strptime(label.strip(), "%b %Y").date()
    except ValueError:
        return None
    end = month_end.replace(day=calendar.monthrange(month_end.year, month_end.month)[1])
    offset = end.year * 12 + end.month - months
    return PeriodInterval.duration(date(offset // 12, offset % 12 + 1, 1), end)


def _bound(
    extraction: VendorExtraction, request: VendorIngestRequest, repository: EvidenceRepository
) -> None:
    """Refuse occurrences whose verified issuer or basis is not the request's (spec §3)."""
    if not extraction.occurrences:
        return
    try:
        seeded = repository.issuer_identifiers(request.entity_id)
        known = extraction.issuer in (seeded.isin, seeded.nse_symbol)
    except LookupError:
        known = False
    if not known or extraction.basis is not request.basis:
        raise VendorExtractionError(
            ExtractionOutcome.IDENTITY_REJECTED,
            _FOREIGN.format(
                issuer=extraction.issuer,
                basis=extraction.basis,
                entity_id=request.entity_id,
                requested=request.basis,
            ),
        )


def _interpretations(
    occurrences: tuple[Occurrence, ...],
    scope: CaptureScope,
    repository: EvidenceRepository,
    extractor_version: str,
) -> tuple[Interpretation, ...]:
    """This generation's rows under the pinned versions and scope: reused, else appended.

    A concurrent identical ingest that stores them first wins: its rows are re-read and
    reused. A conflict that leaves none under this scope (a basis or entity change on the
    same occurrences) stays a loud refusal.
    """
    assert scope.capture.capture_ref_id is not None
    pins = (
        scope.mapping_set.version,
        scope.policy.version,
        extractor_version,
        scope.entity_id,
        scope.basis,
    )
    ids = {item.occurrence_id for item in occurrences}

    def under(row: Interpretation) -> bool:
        return (
            row.mapping_set_version,
            row.normalisation_policy_version,
            row.extractor_version,
            row.entity_id,
            row.basis,
        ) == pins

    def current() -> tuple[Interpretation, ...]:
        return tuple(row for row in stored if under(row) and row.occurrence_id in ids)

    capture_ref_id = scope.capture.capture_ref_id
    stored = repository.list_capture_interpretations(capture_ref_id)
    if current() or not occurrences:
        return current()
    prior = [row for row in stored if not under(row)]
    prior_ids = sorted({row.occurrence_id for row in prior if row.occurrence_id is not None})
    written = interpret_generation(
        occurrences,
        scope=scope,
        prior=prior,
        prior_anchor_keys={
            item.occurrence_id: item.anchor_key
            for item in repository.get_occurrences(prior_ids)
            if item.occurrence_id is not None
        },
        reserve_ids=repository.reserve_interpretation_ids,
        recorded_at=repository.store_clock(),
    )
    try:
        repository.put_interpretations(written)
    except InterpretationConflictError:
        stored = repository.list_capture_interpretations(capture_ref_id)
        if not current():
            raise
        return current()
    return written


def _store(
    repository: EvidenceRepository,
    request: VendorIngestRequest,
    outcome: ExtractionOutcome,
    reason: str | None,
    *,
    capture: CaptureReference | None = None,
    extraction: VendorExtraction | None = None,
    extractor_version: str = "",
) -> VendorIngestReport:
    """One attempt and its occurrences in one transaction; capture-less means ``ACQUISITION``."""
    attempt = AcquisitionAttempt(
        attempt_id=None,
        stage=AttemptStage.ACQUISITION if capture is None else AttemptStage.EXTRACTION,
        source_id=request.source_id,
        surface=request.surface,
        entity_id=request.entity_id,
        period_end=request.period_end,
        basis=request.basis,
        framework=request.framework,
        representation=request.representation,
        statement_family=None,
        package_id=None,
        outcome=outcome,
        reason=reason,
        capture=capture,
        input_sha256=input_digest(
            request.model_dump(
                mode="json", include={"source_id", "surface", "request_key", "capture_id"}
            )
        ),
        extractor_version=extractor_version,
        attempted_at=None,
        extraction_context_sha256=extraction.extraction_context_sha256 if extraction else None,
    )
    occurrences, (stored,) = repository.put_generation(
        extraction.occurrences if extraction else (), [attempt]
    )
    return VendorIngestReport(attempt=stored, occurrences=occurrences)
