"""Shared retained-only vendor contracts and admission; no acquisition or filing packages.

Raw HTML and raw JSON responses are separate source surfaces. A body is verified once
against its retained binding and passed to a parser as bytes. Metadata retrieval times
are claims; first-seen registration and write times come from the evidence store clock.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    Interpretation,
    Occurrence,
    VendorExtractorPin,
    VersionPin,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import (
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SurfaceAuthority,
)
from fundamentals.store.snapshot_store import DescriptorTree, DirectoryAnchor


class RetainedVendorUnavailable(FileNotFoundError):  # noqa: N818 - public handoff name
    """No local response exists for the requested surface; this is not publication absence."""


class VendorAuthorityError(ValueError):
    """The actual source and surface lack an applicable authority decision."""


class VendorRetainedBinding(BaseModel):
    """A source response relative to the operator-pinned input directory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_path: Path
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claimed_retrieved_at: datetime | None = None

    @model_validator(mode="after")
    def _relative_input(self) -> VendorRetainedBinding:
        if self.relative_path.is_absolute() or ".." in self.relative_path.parts:
            raise ValueError("retained input binding stays relative to its pinned input root")
        return self


class VendorRequest(BaseModel):
    """One requested measurement scope and its exact retained response binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    representation: Representation
    schema_identity: str = Field(min_length=1)
    entity_id: int = Field(gt=0)
    period: PeriodInterval
    basis: Basis
    framework: AccountingFramework
    statement_family: StatementFamily
    retained: VendorRetainedBinding | None = None
    knowledge_time: datetime | None = None
    knowledge_time_evidence_ref: str | None = None

    @model_validator(mode="after")
    def _vendor_scope(self) -> VendorRequest:
        if self.representation not in (Representation.HTML, Representation.JSON):
            raise ValueError(
                "vendor requests use HTML or JSON, never a filing package representation"
            )
        if self.knowledge_time is not None and (
            self.knowledge_time.tzinfo is None or not self.knowledge_time_evidence_ref
        ):
            raise ValueError(
                "known vendor publication time needs an offset and its evidence reference"
            )
        return self

    def identity_sha256(self) -> str:
        """The actual request, including unavailable retained binding, hashed deterministically."""
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


class VendorGeneration(BaseModel):
    """A source-qualified generation, never an artificial first-party filing package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request: VendorRequest
    capture: CaptureReference | None
    occurrences: tuple[Occurrence, ...] = ()
    interpretations: tuple[Interpretation, ...] = ()
    attempts: tuple[AcquisitionAttempt, ...] = ()
    extractor_pin: VendorExtractorPin
    source_authority_pin: VersionPin
    published_config_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _same_surface(self) -> VendorGeneration:
        identity = (self.request.source_id, self.request.surface)
        if (self.extractor_pin.source_id, self.extractor_pin.surface) != identity:
            raise ValueError("vendor extractor pin belongs to another source/surface")
        if self.capture is None and (self.occurrences or self.interpretations):
            raise ValueError(
                "a capture-free failure cannot claim extracted or interpreted evidence"
            )
        if self.capture is not None and (self.capture.source_id, self.capture.surface) != identity:
            raise ValueError("vendor capture belongs to another source/surface")
        for item in self.occurrences:
            if (
                item.capture != self.capture
                or item.representation is not self.request.representation
            ):
                raise ValueError("vendor occurrence provenance differs from its generation")
        for interpreted in self.interpretations:
            if self.capture is None or interpreted.capture_ref_id != self.capture.capture_ref_id:
                raise ValueError("vendor interpretation belongs to another capture")
            if (
                interpreted.entity_id != self.request.entity_id
                or interpreted.basis is not self.request.basis
                or interpreted.framework is not self.request.framework
                or interpreted.representation is not self.request.representation
            ):
                raise ValueError("vendor interpretation scope differs from its admitted request")
        for attempt in self.attempts:
            if (attempt.source_id, attempt.surface) != identity or attempt.package_id is not None:
                raise ValueError("vendor attempts name this surface and never a filing package")
            if (
                attempt.entity_id != self.request.entity_id
                or attempt.basis is not self.request.basis
                or attempt.framework is not self.request.framework
                or attempt.representation is not self.request.representation
                or attempt.period_end != (self.request.period.end or self.request.period.instant)
                or attempt.statement_family is not self.request.statement_family
            ):
                raise ValueError("vendor attempt scope differs from its admitted request")
        return self


def authorize_vendor(
    request: VendorRequest,
    *,
    catalog: SourceCatalog,
    authority: SurfaceAuthority,
) -> SourceRole:
    """Require the explicit source declaration and matching pinned surface authority."""
    descriptor = catalog.describe(request.source_id)
    if descriptor.source_class is not SourceClass.DERIVED or (
        authority.source_id,
        authority.surface,
        authority.representation,
    ) != (request.source_id, request.surface, request.representation):
        raise VendorAuthorityError(
            "source classification and exact retained surface authority required"
        )
    if authority.evidence_role is not descriptor.evidence_role:
        raise VendorAuthorityError("surface authority cannot promote the declared source role")
    return (
        SourceRole.INDEPENDENT_VENDOR
        if authority.evidence_role is EvidenceRole.RECONCILABLE
        else SourceRole.DIAGNOSTIC
    )


def load_vendor_bytes(request: VendorRequest, *, input_anchor: DirectoryAnchor) -> bytes:
    """Read the bound body once, refusing missing bytes, path escape or content drift."""
    binding = request.retained
    if binding is None:
        raise RetainedVendorUnavailable("no retained input binding for this source surface")
    try:
        with DescriptorTree(input_anchor) as tree:
            parent = tree.root
            for component in binding.relative_path.parts[:-1]:
                parent = tree.child(parent, component)
            body = tree.read(parent, binding.relative_path.name, 32 * 1024 * 1024)
            tree.verify()
    except FileNotFoundError as error:
        raise RetainedVendorUnavailable("bound retained vendor response is unavailable") from error
    if hashlib.sha256(body).hexdigest() != binding.expected_sha256:
        raise ValueError("retained vendor bytes differ from their source-pinned hash")
    return body
