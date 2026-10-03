"""Ephemeral admission from pinned bytes and protected local producer receipts."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from fundamentals.api.config import FundamentalsConfig
from fundamentals.api.source_intake import ApprovedIntakeContext
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.fact import CanonicalStatus, Fact, ReconciliationStatus
from fundamentals.contracts.observation import Observation
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.snapshot import (
    CAPTURE_ID_PATTERN,
    REQUEST_KEY_PATTERN,
    SHA256_PATTERN,
    CaptureRecord,
    SnapshotError,
    canonical_sha256,
)
from fundamentals.contracts.source_registration import (
    SourceRegistration,
    SourceRegistrationError,
    SourceRole,
)
from fundamentals.store.snapshot_store import (
    MAX_METADATA_BYTES,
    DescriptorTree,
    DirectoryAnchor,
    SnapshotStore,
)
from fundamentals.store.source_intake_store import SourceIntakeStore


class SourceAdmissionError(ValueError):
    """Source eligibility or immutable binding could not be established."""


def utc_time(value: datetime) -> datetime:
    """Refuse ambiguous time instead of converting it into evidence."""
    if value.utcoffset() != timedelta(0):
        raise SourceAdmissionError("temporal evidence requires aware UTC time")
    return value


def actual_clock() -> datetime:
    return datetime.now(UTC)


class RetainedSourceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: str
    surface: str
    request_key: str
    capture_id: str
    source_sha256: str
    record_sha256: str

    @field_validator("source_id", "surface", "request_key")
    @classmethod
    def _component(cls, value: str) -> str:
        if not re.fullmatch(REQUEST_KEY_PATTERN, value) or value in {".", ".."}:
            raise ValueError("source reference requires plain path components")
        return value

    @field_validator("source_sha256", "record_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not re.fullmatch(SHA256_PATTERN, value):
            raise ValueError("source reference requires SHA-256")
        return value

    @field_validator("capture_id")
    @classmethod
    def _capture(cls, value: str) -> str:
        if not re.fullmatch(CAPTURE_ID_PATTERN, value):
            raise ValueError("invalid capture ID")
        return value


class PipelineSourceRefs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    xbrl: RetainedSourceRef
    results_pdf: RetainedSourceRef
    transcript_pdf: RetainedSourceRef


class SourceCaptureEvidence(BaseModel):
    """Trusted direct composition only; never deserialized by the CLI."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    reference: RetainedSourceRef
    source_id: str
    source_sha256: str
    acquired_at: datetime
    first_seen_at: datetime
    body: bytes
    complete: bool
    outcome: OutcomeCode
    private_internal: bool
    registration: SourceRegistration | None = None
    claimed_retrieved_at: datetime | None = None


class SourceEvidenceResolver(Protocol):
    def resolve(self, ref: RetainedSourceRef) -> SourceCaptureEvidence: ...


class NativeSourceEvidenceResolver:
    """Reopen exact protected producer proof against current operator bindings."""

    def __init__(self, root: Path, *, approved_intake: ApprovedIntakeContext | None = None) -> None:
        self._store = SnapshotStore(root)
        self._context = approved_intake

    def resolve(self, ref: RetainedSourceRef) -> SourceCaptureEvidence:
        if self._context is None:
            raise SourceAdmissionError(
                "native source lacks trustworthy completion/first-seen/registration proof: "
                "trusted approved intake context required"
            )
        try:
            ledger = SourceIntakeStore(self._store, approved_intake=self._context)
            coordinates = ref.model_dump(exclude={"source_sha256", "record_sha256"})
            binding_id = canonical_sha256(coordinates)
            # The stored role selects a lookup, never authority. The producer then
            # verifies it against the independent current context and installed binding.
            with DescriptorTree(self._context.store_anchor) as tree:
                directory = tree.descend((".source-intake", binding_id), private=True)
                receipt = SourceRegistration.model_validate_json(
                    tree.read(directory, "registration.json", MAX_METADATA_BYTES, private=True)
                )
                tree.verify()
            receipt, body = ledger.resolve_verified(role=receipt.role, **ref.model_dump())
            # Read only bounded record metadata for the separately labelled acquisition claim.
            with DescriptorTree(self._context.store_anchor) as tree:
                directory = tree.descend(
                    (ref.source_id, ref.surface, ref.request_key, ref.capture_id)
                )
                record = CaptureRecord.model_validate_json(
                    tree.read(directory, "record.json", MAX_METADATA_BYTES)
                )
                if record.record_sha256 != ref.record_sha256:
                    raise SourceAdmissionError("retained reference/record binding mismatch")
                tree.verify()
            return SourceCaptureEvidence(
                reference=ref,
                source_id=receipt.source_id,
                source_sha256=receipt.source_sha256,
                acquired_at=receipt.capture_completed_at,
                first_seen_at=receipt.first_observed_at,
                body=body,
                complete=True,
                outcome=OutcomeCode.OK,
                private_internal=True,
                registration=receipt,
                claimed_retrieved_at=record.retrieved_at,
            )
        except (SourceRegistrationError, SnapshotError, OSError, ValueError) as error:
            raise SourceAdmissionError(f"native registered source refused: {error}") from error


class AdmittedSource(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str
    source_sha256: str
    acquired_at: datetime
    first_seen_at: datetime
    mode: Literal["trusted_direct", "new_local_capture", "retained_registered"]
    reference: RetainedSourceRef | None = None
    registration: SourceRegistration | None = None
    claimed_retrieved_at: datetime | None = None


@dataclass(frozen=True)
class AdmittedPipelineInputs:
    run_started_at: datetime
    cutoff: datetime
    admitted_at: datetime
    xbrl: AdmittedSource
    results_pdf: AdmittedSource
    transcript_pdf: AdmittedSource
    xbrl_bytes: bytes
    _results_path: Path
    _transcript_path: Path
    _clock: Callable[[], datetime]


_ACTIVE: dict[int, AdmittedPipelineInputs] = {}


def validate_prepared(
    inputs: AdmittedPipelineInputs,
    *,
    cutoff: datetime,
    source_ids: tuple[str, str, str],
    hashes: tuple[str, str, str],
    xbrl_bytes: bytes,
) -> None:
    """A live preparation must bind the caller's exact run inputs."""
    if _ACTIVE.get(id(inputs)) is not inputs:
        raise SourceAdmissionError("prepared inputs are not in an active admission context")
    sources = (inputs.xbrl, inputs.results_pdf, inputs.transcript_pdf)
    if (
        inputs.cutoff != cutoff
        or inputs.xbrl_bytes != xbrl_bytes
        or tuple(s.source_id for s in sources) != source_ids
        or tuple(s.source_sha256 for s in sources) != hashes
    ):
        raise SourceAdmissionError("prepared inputs do not bind this run")


def load_source_manifest(path: Path) -> PipelineSourceRefs:
    try:
        with DescriptorTree(DirectoryAnchor(path.absolute().parent)) as tree:
            payload = tree.read(tree.root, path.name, MAX_METADATA_BYTES)
            tree.verify()
        return PipelineSourceRefs.model_validate_json(payload)
    except (SnapshotError, OSError) as error:
        raise SourceAdmissionError(f"source admission manifest refused: {error}") from error


@contextmanager
def prepare_pipeline_sources(
    *,
    xbrl_bytes: bytes,
    xbrl_source_id: str,
    xbrl_sha256: str,
    results_pdf_path: str | Path,
    results_pdf_sha256: str,
    results_source_id: str,
    transcript_pdf_path: str | Path,
    transcript_pdf_sha256: str,
    transcript_source_id: str,
    cutoff: datetime,
    run_started_at: datetime,
    source_refs: PipelineSourceRefs | None = None,
    evidence_resolver: SourceEvidenceResolver | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Iterator[AdmittedPipelineInputs]:
    tick = clock or actual_clock
    utc_time(cutoff)
    last = utc_time(run_started_at)
    if (source_refs is None) != (evidence_resolver is None):
        raise SourceAdmissionError("source references and trusted resolver are required together")
    bindings = []
    buffers = []
    for purpose, source_id, expected, original in (
        ("xbrl", xbrl_source_id, xbrl_sha256, xbrl_bytes),
        ("results_pdf", results_source_id, results_pdf_sha256, Path(results_pdf_path)),
        ("transcript_pdf", transcript_source_id, transcript_pdf_sha256, Path(transcript_pdf_path)),
    ):
        ref = getattr(source_refs, purpose) if source_refs is not None else None
        evidence = evidence_resolver.resolve(ref) if ref is not None and evidence_resolver else None
        try:
            body = (
                evidence.body
                if evidence is not None
                else (bytes(original) if isinstance(original, bytes) else original.read_bytes())
            )
        except OSError as error:
            raise SourceAdmissionError(f"{purpose}: source body unavailable") from error
        if hashlib.sha256(body).hexdigest() != expected:
            raise SourceAdmissionError(f"{purpose}: source digest mismatch")
        completed = utc_time(tick())
        if completed < last:
            raise SourceAdmissionError(f"{purpose}: clock moved backwards")
        last = completed
        registration = None
        claimed_retrieved_at = None
        mode: Literal["trusted_direct", "new_local_capture", "retained_registered"]
        if ref is not None and evidence is not None:
            if (
                ref.source_id != source_id
                or ref.source_sha256 != expected
                or evidence.reference != ref
                or evidence.source_id != source_id
                or evidence.source_sha256 != expected
                or not evidence.complete
                or evidence.outcome is not OutcomeCode.OK
                or not evidence.private_internal
            ):
                raise SourceAdmissionError(f"{purpose}: capture binding/outcome/rights refused")
            acquired = utc_time(evidence.acquired_at)
            first_seen = utc_time(evidence.first_seen_at)
            mode = "trusted_direct"
            registration = evidence.registration
            claimed_retrieved_at = evidence.claimed_retrieved_at
            if registration is not None:
                if (
                    registration.role is not SourceRole(purpose)
                    or any(
                        getattr(registration, key) != value
                        for key, value in ref.model_dump().items()
                    )
                    or acquired != registration.capture_completed_at
                    or first_seen != registration.first_observed_at
                ):
                    raise SourceAdmissionError(f"{purpose}: registration role/reference mismatch")
                if cutoff > min(run_started_at, completed):
                    raise SourceAdmissionError("retained registered cutoff is in the future")
                mode = "retained_registered"
            bound = max(
                acquired, first_seen, registration.registered_at if registration else first_seen
            )
            if bound > completed:
                raise SourceAdmissionError(f"{purpose}: evidence is in the future")
        else:
            acquired = first_seen = completed
            bound = completed
            mode = "new_local_capture"
        if bound > cutoff:
            raise SourceAdmissionError(
                f"{purpose}: source acquisition/first-seen/registration exceeds cutoff"
            )
        bindings.append(
            AdmittedSource(
                source_id=source_id,
                source_sha256=expected,
                acquired_at=acquired,
                first_seen_at=first_seen,
                mode=mode,
                reference=ref,
                registration=registration,
                claimed_retrieved_at=claimed_retrieved_at,
            )
        )
        buffers.append(body)
    with tempfile.TemporaryDirectory(prefix="fundamentals-admission-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        paths = []
        for name, body in zip(("results.pdf", "transcript.pdf"), buffers[1:], strict=True):
            path = root / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
            path.chmod(0o400)
            paths.append(path)
        prepared = AdmittedPipelineInputs(
            run_started_at=run_started_at,
            cutoff=cutoff,
            admitted_at=last,
            xbrl=bindings[0],
            results_pdf=bindings[1],
            transcript_pdf=bindings[2],
            xbrl_bytes=buffers[0],
            _results_path=paths[0],
            _transcript_path=paths[1],
            _clock=tick,
        )
        _ACTIVE[id(prepared)] = prepared
        try:
            yield prepared
        finally:
            _ACTIVE.pop(id(prepared), None)


def admitted_provenance(provenance: Provenance, source: AdmittedSource) -> Provenance:
    """Bind actual receipt and availability without changing the source locator."""
    return provenance.model_copy(
        update={
            "retrieved_at": source.acquired_at,
            "first_seen_at": source.first_seen_at,
        }
    )


def monotonic_clock(prepared: AdmittedPipelineInputs) -> Callable[[], datetime]:
    """Continue this run's clock after all admission reads have completed."""
    previous = prepared.admitted_at

    def completed() -> datetime:
        nonlocal previous
        stamp = utc_time(prepared._clock())
        if stamp < previous:
            raise SourceAdmissionError("derivation clock moved backwards")
        previous = stamp
        return stamp

    return completed


def bind_observation(observation: Observation, source: AdmittedSource) -> Observation:
    """Attach admission clocks while preserving the observation's typed locator."""
    return observation.model_copy(
        update={
            "provenance": admitted_provenance(observation.provenance, source),
        }
    )


def build_derived_fact(
    obs: Observation,
    *,
    role_family: str,
    reconciliation_status: ReconciliationStatus,
    config: FundamentalsConfig,
    run_id: str,
    completed_at: datetime,
) -> Fact:
    """Wrap an observation as an append-only, revision-aware Fact."""
    return Fact(
        observation=obs,
        reconciliation_status=reconciliation_status,
        canonical_status=CanonicalStatus.CANDIDATE,
        revision_family=role_family,
        run_id=run_id,
        valid_time_start=config.quarter.period_start,
        valid_time_end=config.quarter.period_end,
        knowledge_time=completed_at,
        first_seen_time=completed_at,
    )
