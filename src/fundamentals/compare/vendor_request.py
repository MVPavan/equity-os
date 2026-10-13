"""Closed composer declarations and separate semantic availability identities (D1b)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.evidence import VendorExtractorPin
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.evidence.vendor_common import VendorRequest, VendorRetainedBinding
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding
from fundamentals.ingest.screener_financials_models import Section

if TYPE_CHECKING:
    from fundamentals.compare.run_models import VendorSurfaceRequest


class ScreenerComposerContext(BaseModel):
    """Parser choices plus independently pinned issuer binding and supporting inputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["screener"] = "screener"
    binding: ScreenerIssuerBinding
    section: Section
    identity_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent: str | None = None
    supporting_page_request: VendorRequest | None = None
    supporting_page_capture_ref_id: int | None = Field(default=None, gt=0)
    metadata_binding: VendorRetainedBinding | None = None

    @model_validator(mode="after")
    def _supporting_scope(self) -> ScreenerComposerContext:
        schedule = self.parent is not None
        if schedule != (self.supporting_page_request is not None) or schedule != (
            self.supporting_page_capture_ref_id is not None
        ):
            raise ValueError("a schedule parent requires its exact supporting page and capture")
        if self.parent is not None and not self.parent.strip():
            raise ValueError("a schedule parent is nonempty")
        if self.metadata_binding is not None and not schedule:
            raise ValueError("metadata belongs to a separately declared schedule")
        return self


class OfflineComposerContext(BaseModel):
    """Fixed missing-input composer; no caller outcome, reason, rows or callable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["offline"] = "offline"


VendorComposerContext = Annotated[
    ScreenerComposerContext | OfflineComposerContext, Field(discriminator="kind")
]


class VendorGenerationError(ValueError):
    """A vendor claim cannot be proven against its publication, input or stored identity."""


def request_from_declaration(declaration: VendorSurfaceRequest) -> VendorRequest:
    """Close all required fields; the two-field legacy declaration remains non-executable."""
    required = (
        "representation",
        "schema_identity",
        "entity_id",
        "period",
        "basis",
        "framework",
        "statement_family",
        "composer_context",
        "expected_logical_scope_sha256",
    )
    if any(getattr(declaration, field) is None for field in required):
        raise VendorGenerationError("vendor declaration requires a complete joined handoff")
    return VendorRequest.model_validate(
        {field: getattr(declaration, field) for field in VendorRequest.model_fields}
    )


def semantic_composer_context(context: VendorComposerContext) -> dict[str, object]:
    """Interpretation-affecting choices without physical capture/body/path identity."""
    if isinstance(context, OfflineComposerContext):
        return {"kind": context.kind}
    page = context.supporting_page_request
    return {
        "kind": context.kind,
        "binding": context.binding.model_dump(mode="json"),
        "section": context.section.value,
        "parent": context.parent,
        "identity_config_sha256": context.identity_config_sha256,
        "supporting_page_scope": (request_scope_document(page) if page is not None else None),
        "metadata_declared": context.metadata_binding is not None,
    }


def request_scope_document(request: VendorRequest) -> dict[str, object]:
    """Full logical measurement scope, including interval and known publication evidence."""
    return {
        field: value
        for field, value in request.model_dump(mode="json").items()
        if field not in {"retained", "knowledge_time", "knowledge_time_evidence_ref"}
    }


def logical_scope_sha256(
    request: VendorRequest,
    *,
    extractor_pin: VendorExtractorPin,
    composer_context: VendorComposerContext,
) -> str:
    """Availability identity independent of retained binding and exact request hash."""
    return canonical_sha256(
        {
            "version": "vendor-logical-scope-v1",
            "scope": request_scope_document(request),
            "extractor": extractor_pin.model_dump(mode="json"),
            "composer": semantic_composer_context(composer_context),
        }
    )
