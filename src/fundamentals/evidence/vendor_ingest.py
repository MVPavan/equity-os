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

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.canon.interval import RoundingPolicy
from fundamentals.contracts.acquisition_outcome import (
    ExtractionOutcome,
    OutcomeCode,
    extraction_outcome_for,
)
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import (
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
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import SurfaceNotAuthorisedError, surface_authority
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.store.snapshot_store import SnapshotStore

_LOG = structlog.get_logger(__name__)
_DASHES = ("-", "—", "–")
_NOT_RETAINED = "capture {capture_id} retained no complete body ({code})"


class VendorExtractionError(ValueError):
    """Typed refusal before any occurrence can be interpreted."""

    def __init__(self, outcome: ExtractionOutcome, detail: str) -> None:
        self.outcome = outcome
        super().__init__(detail)


class VendorExtraction(BaseModel):
    """Lossless native occurrences plus the honest outcome and pinned extraction context."""

    model_config = ConfigDict(frozen=True)
    occurrences: tuple[Occurrence, ...]
    outcome: ExtractionOutcome
    reasons: tuple[str, ...] = ()
    extraction_context_sha256: str | None = None


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

    ``extract(body, capture=, record=, extractor_version=)`` is a surface adapter.
    """
    try:
        surface_authority(request.source_id, request.surface)
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


def _interpretations(
    occurrences: tuple[Occurrence, ...],
    scope: CaptureScope,
    repository: EvidenceRepository,
    extractor_version: str,
) -> tuple[Interpretation, ...]:
    """This generation's rows under the pinned triple: reused if stored, else appended."""
    assert scope.capture.capture_ref_id is not None
    triple = (scope.mapping_set.version, scope.policy.version, extractor_version)
    ids = {item.occurrence_id for item in occurrences}
    stored = repository.list_capture_interpretations(scope.capture.capture_ref_id)

    def under(row: Interpretation) -> bool:
        return (
            row.mapping_set_version,
            row.normalisation_policy_version,
            row.extractor_version,
        ) == triple

    current = tuple(row for row in stored if under(row) and row.occurrence_id in ids)
    if current or not occurrences:
        return current
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
    repository.put_interpretations(written)
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
