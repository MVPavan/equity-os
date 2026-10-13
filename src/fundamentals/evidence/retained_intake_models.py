"""Frozen source and durable association contracts for retained-intake witnesses."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Final, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    FilingFamily,
    VersionPin,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.store.snapshot_store import DirectoryAnchor

WITNESS_SCHEMA: Final[Literal["retained_intake_v1"]] = "retained_intake_v1"
MAX_METADATA_BYTES = 1024 * 1024
PositiveId = Annotated[StrictInt, Field(gt=0)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RetainedIntakeWitnessError(ValueError):
    """An original material or sealed generation association cannot be proven."""


def safe_relative_label(value: str) -> str:
    """Accept a canonical POSIX relative label without filesystem interpretation."""
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or str(path) != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(char in value for char in ("\\", "\x00", "\t", "\n", "\r"))
    ):
        raise ValueError("retained metadata/input label is unsafe")
    return value


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RetainedIntakeSelection(_Frozen):
    representation: Literal[Representation.XBRL, Representation.PDF]
    kind: str = Field(min_length=1)


class RetainedIntakeMetadataSource(_Frozen):
    """Locally observed descriptor anchors; this value is never deserialized or stored."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    manifest_anchor: DirectoryAnchor
    manifest_relative_path: Path
    issuer_config_anchor: DirectoryAnchor | None
    issuer_config_relative_path: Path | None
    issuer: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    quarter: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    selection: tuple[RetainedIntakeSelection, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        safe_relative_label(self.manifest_relative_path.as_posix())
        if (self.issuer_config_anchor is None) != (self.issuer_config_relative_path is None):
            raise ValueError("retained config anchor and label must occur together")
        if self.issuer_config_relative_path is not None:
            safe_relative_label(self.issuer_config_relative_path.as_posix())
        _sorted_unique(tuple(item.representation.value for item in self.selection), "selection")
        return self


class RetainedIntakeMaterial(_Frozen):
    """Exact bounded metadata bytes, with a self-checked size and hash."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64"
    )

    label: str
    body: bytes = Field(min_length=1, max_length=MAX_METADATA_BYTES)
    sha256: Sha256
    size: PositiveId

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        safe_relative_label(self.label)
        if self.size != len(self.body) or self.sha256 != hashlib.sha256(self.body).hexdigest():
            raise ValueError("retained metadata size or SHA differs from exact material")
        return self

    @classmethod
    def of(cls, label: str, body: bytes) -> Self:
        return cls(label=label, body=body, sha256=hashlib.sha256(body).hexdigest(), size=len(body))


class RetainedIntakeRequest(_Frozen):
    representation: Literal[Representation.XBRL, Representation.PDF]
    source_id: str = Field(min_length=1)
    surface: Literal["NSE_XBRL_INSTANCE", "NSE_RESULTS_PDF"]
    relative_path: str
    expected_input_sha256: Sha256
    request_key: Sha256
    filed_at_raw: str = Field(min_length=1)
    knowledge_time: AwareDatetime
    extractor_pin: VersionPin
    extraction_context_sha256: Sha256 | None
    context_material_json: str = Field(min_length=1)

    @field_validator("extractor_pin", mode="before")
    @classmethod
    def _closed_pin(cls, value: object) -> object:
        document = value.model_dump() if isinstance(value, VersionPin) else value
        if (
            not isinstance(document, dict)
            or set(document) != {"version", "content_sha256"}
            or not isinstance(document["version"], str)
            or not document["version"]
            or not isinstance(document["content_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", document["content_sha256"]) is None
        ):
            raise ValueError("retained request extractor pin is not a closed version/SHA pair")
        return value

    @field_validator("relative_path")
    @classmethod
    def _path(cls, value: str) -> str:
        return safe_relative_label(value)

    @field_validator("knowledge_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class PreparedRetainedIntakeWitness(_Frozen):
    schema_version: Literal["retained_intake_v1"] = WITNESS_SCHEMA
    issuer: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    quarter: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    manifest: RetainedIntakeMaterial
    issuer_config: RetainedIntakeMaterial
    selection: tuple[RetainedIntakeSelection, ...] = Field(min_length=1, max_length=2)
    authority_ref: str = Field(min_length=1)
    results_pdf_source_id: str = Field(min_length=1)
    entity_id: PositiveId
    family: FilingFamily
    reporting_period_end: date
    basis: Basis
    framework: AccountingFramework
    requests: tuple[RetainedIntakeRequest, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        _sorted_unique(tuple(item.representation.value for item in self.selection), "selection")
        _sorted_unique(tuple(item.representation.value for item in self.requests), "requests")
        if tuple(item.representation for item in self.selection) != tuple(
            item.representation for item in self.requests
        ):
            raise ValueError("retained selection and requests differ")
        return self


class RetainedIntakeAssociation(_Frozen):
    representation: Literal[Representation.XBRL, Representation.PDF]
    attempt_ids: tuple[PositiveId, ...] = Field(min_length=1)
    package_capture_ids: tuple[PositiveId, ...] = ()
    failed_capture_ids: tuple[PositiveId, ...] = ()

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        for name in ("attempt_ids", "package_capture_ids", "failed_capture_ids"):
            _sorted_unique(getattr(self, name), name)
        if set(self.package_capture_ids) & set(self.failed_capture_ids):
            raise ValueError("one capture cannot be both successful and failed")
        return self


class RetainedIntakeVersionPin(_Frozen):
    id: PositiveId
    artifact: str = Field(min_length=1, pattern=r"^[^\t\n\r]+$")
    version: str = Field(min_length=1)
    content_sha256: Sha256
    pinned_at: AwareDatetime

    @field_validator("pinned_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class RetainedIntakeWitnessPayload(_Frozen):
    """Content-addressed material and exact old row identities; no new storage identities."""

    prepared: PreparedRetainedIntakeWitness
    package_id: PositiveId
    package_evidence_sha256: Sha256
    settings_record_id: PositiveId
    qualification_context_sha256: Sha256
    publication_version: str = Field(min_length=1)
    publication_sha256: Sha256
    publication_state: Literal["RELEASED", "SYNTHETIC"]
    generation_json: str = Field(min_length=1)
    attempts: tuple[AcquisitionAttempt, ...] = Field(min_length=1)
    captures: tuple[CaptureReference, ...]
    pins: tuple[RetainedIntakeVersionPin, ...] = Field(min_length=1)
    associations: tuple[RetainedIntakeAssociation, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        _sorted_unique(tuple(row.attempt_id for row in self.attempts), "attempts")
        _sorted_unique(tuple(row.capture_ref_id for row in self.captures), "captures")
        _sorted_unique(tuple(row.artifact for row in self.pins), "pins")
        _sorted_unique(tuple(row.representation.value for row in self.associations), "associations")
        return self

    def content_payload(self) -> dict[str, object]:
        """Exact metadata bytes are committed by hash/size; stored old row clocks are included."""
        document: dict[str, object] = self.model_dump(mode="json")
        prepared = self.prepared.model_dump(mode="json")
        for name in ("manifest", "issuer_config"):
            material = dict(prepared[name])
            material.pop("body")
            prepared[name] = material
        document["prepared"] = prepared
        return document

    @property
    def content_sha256(self) -> str:
        return canonical_sha256(self.content_payload())

    @property
    def label(self) -> str:
        return f"{WITNESS_SCHEMA}:{self.prepared.issuer}:{self.prepared.quarter}"

    @property
    def closure_sha256(self) -> str:
        lines = [f"B\t{request.representation.value}\n" for request in self.prepared.requests]
        for association in self.associations:
            representation = association.representation.value
            lines.extend(f"A\t{representation}\t{item}\n" for item in association.attempt_ids)
            for disposition, ids in (
                ("PACKAGE_MEMBER", association.package_capture_ids),
                ("FAILED_PEER", association.failed_capture_ids),
            ):
                lines.extend(f"C\t{representation}\t{item}\t{disposition}\n" for item in ids)
        lines.extend(f"P\t{pin.artifact}\t{pin.id}\n" for pin in self.pins)
        return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


class RetainedIntakeWitness(_Frozen):
    """A sealed by-evidence-ID witness; header/link IDs deliberately are not transported."""

    evidence_input_id: PositiveId
    label: str = Field(min_length=1)
    content_sha256: Sha256
    recorded_at: AwareDatetime
    sealed_at: AwareDatetime
    closure_sha256: Sha256
    payload: RetainedIntakeWitnessPayload

    @field_validator("recorded_at", "sealed_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _sealed(self) -> Self:
        if (
            self.label != self.payload.label
            or self.content_sha256 != self.payload.content_sha256
            or self.closure_sha256 != self.payload.closure_sha256
            or self.recorded_at != self.sealed_at
        ):
            raise ValueError("retained witness kind/label/content/clock/closure differs")
        return self


def _sorted_unique(values: tuple[Any, ...], label: str) -> None:
    if any(item is None for item in values) or values != tuple(sorted(set(values))):
        raise ValueError(f"retained witness {label} must be stored, sorted and duplicate-free")
