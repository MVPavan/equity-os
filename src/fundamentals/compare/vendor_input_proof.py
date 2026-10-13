"""Read-only vendor claim reproof against fixed composers and registered evidence."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run_config import LoadedConfig, require_published_generation
from fundamentals.compare.run_models import VendorSurfaceRequest
from fundamentals.compare.vendor_request import (
    OfflineComposerContext,
    ScreenerComposerContext,
    VendorComposerContext,
    VendorGenerationError,
    logical_scope_sha256,
    request_from_declaration,
)
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    Occurrence,
    VendorExtractorPin,
)
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SurfaceAuthority
from fundamentals.evidence.repository import EvidenceInputRecord, EvidenceRepository, SettingsRecord
from fundamentals.evidence.vendor_common import (
    VendorGeneration,
    VendorRequest,
    authorize_vendor,
    load_vendor_bytes,
)
from fundamentals.evidence.vendor_config import (
    SCREENER_SCHEMA_IDENTITIES,
    SCREENER_SOURCE,
    PublicationState,
    PublishedVendorConfig,
    SurfaceDisposition,
)
from fundamentals.evidence.vendor_config_files import read_safe
from fundamentals.evidence.vendor_offline import unavailable_generation
from fundamentals.evidence.vendor_screener import (
    FAMILY_BY_SECTION,
    PAGE_SCHEMA,
    PAGE_SURFACE,
    SCHEDULE_SCHEMA,
    SCHEDULE_SURFACE,
    ScreenerExtractionError,
    extract_screener_page,
    extract_screener_schedule,
)
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.pg.identity_seed import (
    CITED_FIELDS,
    EvidenceInputKind,
    IssuerIdentityInput,
    SettingKey,
)
from fundamentals.store.snapshot_store import DirectoryAnchor


class VendorPreparation(BaseModel):
    """A rederived draft; append redoes preparation rather than accepting this as authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generation: VendorGeneration
    logical_scope_sha256: str
    evidence_identity_sha256: str
    supporting_captures: tuple[CaptureReference, ...] = ()
    settings_record: SettingsRecord | None = None
    identity_evidence: tuple[EvidenceInputRecord, ...] = ()
    source_role: SourceRole
    disposition: SurfaceDisposition
    publication_version: str
    publication_sha256: str
    publication_state: PublicationState


def recompose_vendor_generation(
    *,
    declaration: VendorSurfaceRequest,
    loaded_config: LoadedConfig,
    config_root: Path,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
    repository: EvidenceRepository,
) -> VendorPreparation:
    """Authorize before reads; derive every numeric/attempt claim from registered bytes."""
    request = request_from_declaration(declaration)
    verified_context: VendorComposerContext
    try:
        if isinstance(composer_context, ScreenerComposerContext):
            verified_context = ScreenerComposerContext.model_validate(
                composer_context.model_dump(mode="json")
            )
        else:
            verified_context = OfflineComposerContext.model_validate(
                composer_context.model_dump(mode="json")
            )
    except ValueError as error:
        raise VendorGenerationError(
            "vendor composer context is not a valid closed declaration"
        ) from error
    if verified_context != composer_context:
        raise VendorGenerationError(
            "vendor composer context differs from validated semantic fields"
        )
    if composer_context != declaration.composer_context:
        raise VendorGenerationError("composer context differs from the complete declaration")
    publication = require_published_generation(loaded_config, config_root=config_root)
    pin, role, disposition = _authorize(request, publication)
    logical = logical_scope_sha256(request, extractor_pin=pin, composer_context=composer_context)
    if declaration.expected_logical_scope_sha256 != logical:
        raise VendorGenerationError(
            "vendor declaration logical scope claim differs from derivation"
        )
    settings: SettingsRecord | None = None
    identity_evidence: tuple[EvidenceInputRecord, ...] = ()
    if isinstance(composer_context, ScreenerComposerContext):
        settings, identity_evidence = _issuer_scope(
            request, composer_context, config_root=config_root, repository=repository
        )
    elif request.retained is not None:
        raise VendorGenerationError("captured input requires its fixed source-specific composer")
    capture: CaptureReference | None = None
    supporting: tuple[CaptureReference, ...] = ()
    body_sha256: str | None = None
    if request.retained is None:
        if declaration.capture_ref_id is not None:
            raise VendorGenerationError("capture-free request cannot name a registered capture")
        generation = unavailable_generation(
            request,
            source_id=request.source_id,
            surfaces=(request.surface,),
            representation=request.representation,
            role=role,
            catalog=publication.catalog,
            authority=_authority(request, publication),
            extractor_pin=pin,
            authority_pin=publication.source_authority.pin,
        )
        attempts = tuple(
            attempt.model_copy(update={"extraction_context_sha256": logical})
            for attempt in generation.attempts
        )
        generation = generation.model_copy(
            update={
                "attempts": attempts,
                "published_config_sha256": publication.content_sha256,
            }
        )
    else:
        if disposition is not SurfaceDisposition.INCLUDED:
            raise VendorGenerationError("retained vendor input is not INCLUDED in this release")
        if input_anchor is None or declaration.capture_ref_id is None:
            raise VendorGenerationError(
                "captured vendor input requires its anchor and registered id"
            )
        capture = _capture(request, declaration.capture_ref_id, repository)
        body = load_vendor_bytes(request, input_anchor=input_anchor)
        body_sha256 = hashlib.sha256(body).hexdigest()
        if not isinstance(composer_context, ScreenerComposerContext):
            raise VendorGenerationError("unsupported captured vendor composer")
        occurrences, outcome, reasons, supporting = _extract(
            request,
            body=body,
            capture=capture,
            context=composer_context,
            input_anchor=input_anchor,
            repository=repository,
            publication=publication,
            extractor_pin=pin,
        )
        attempt = _attempt(request, capture, pin, logical, outcome, reasons)
        generation = VendorGeneration(
            request=request,
            capture=capture,
            occurrences=occurrences,
            attempts=(attempt,),
            extractor_pin=pin,
            source_authority_pin=publication.source_authority.pin,
            published_config_sha256=publication.content_sha256,
        )
    evidence_identity = canonical_sha256(
        {
            "version": "vendor-evidence-identity-v1",
            "request_sha256": request.identity_sha256(),
            "request": request.model_dump(mode="json"),
            "primary_capture": capture.model_dump(mode="json") if capture else None,
            "primary_body_sha256": body_sha256,
            "supporting_captures": [item.model_dump(mode="json") for item in supporting],
            "composer_context": composer_context.model_dump(mode="json"),
            "extractor": pin.model_dump(mode="json"),
            "publication_sha256": publication.content_sha256,
            "logical_scope_sha256": logical,
            "settings_record": settings.model_dump(mode="json") if settings else None,
            "identity_evidence": [row.model_dump(mode="json") for row in identity_evidence],
        }
    )
    return VendorPreparation(
        generation=generation,
        logical_scope_sha256=logical,
        evidence_identity_sha256=evidence_identity,
        supporting_captures=supporting,
        settings_record=settings,
        identity_evidence=identity_evidence,
        source_role=role,
        disposition=disposition,
        publication_version=publication.version,
        publication_sha256=publication.content_sha256,
        publication_state=publication.state,
    )


def require_matching_claim(claim: VendorGeneration, prepared: VendorPreparation) -> None:
    """Caller-built models are claims only; ids/times must additionally reload exactly."""
    expected = prepared.generation
    if (
        claim.request != expected.request
        or claim.capture != expected.capture
        or claim.extractor_pin != expected.extractor_pin
        or claim.source_authority_pin != expected.source_authority_pin
        or claim.published_config_sha256 != expected.published_config_sha256
    ):
        raise VendorGenerationError("vendor generation publication or provenance claim differs")
    if [_occurrence_payload(row) for row in claim.occurrences] != [
        _occurrence_payload(row) for row in expected.occurrences
    ]:
        raise VendorGenerationError("vendor occurrence claim differs from byte recomposition")
    if [_attempt_payload(row) for row in claim.attempts] != [
        _attempt_payload(row) for row in expected.attempts
    ]:
        raise VendorGenerationError("vendor attempt claim differs from fixed composer")


def _occurrence_payload(row: Occurrence) -> dict[str, object]:
    return row.model_dump(mode="json", exclude={"occurrence_id"})


def _attempt_payload(row: AcquisitionAttempt) -> dict[str, object]:
    return row.model_dump(mode="json", exclude={"attempt_id", "attempted_at"})


def _authority(request: VendorRequest, publication: PublishedVendorConfig) -> SurfaceAuthority:
    authorities = [
        row
        for row in publication.authorities
        if (row.source_id, row.surface, row.representation)
        == (request.source_id, request.surface, request.representation)
    ]
    if len(authorities) != 1:
        raise VendorGenerationError("vendor source/surface lacks an actual release authority")
    return authorities[0]


def _authorize(
    request: VendorRequest, publication: PublishedVendorConfig
) -> tuple[VendorExtractorPin, SourceRole, SurfaceDisposition]:
    declarations = [
        row
        for row in publication.surface_ledger
        if (row.source_id, row.surface, row.representation)
        == (request.source_id, request.surface, request.representation)
    ]
    if len(declarations) != 1 or declarations[0].disposition is SurfaceDisposition.EXCLUDED:
        raise VendorGenerationError("vendor surface is undeclared or EXCLUDED by the publication")
    role = authorize_vendor(
        request, catalog=publication.catalog, authority=_authority(request, publication)
    )
    bundles = [
        row
        for row in publication.extractor_bundles
        if (row.source_id, row.surface) == (request.source_id, request.surface)
    ]
    if len(bundles) != 1:
        raise VendorGenerationError("vendor surface has no actual published extractor bundle")
    bundle = bundles[0]
    fixed = SCREENER_SCHEMA_IDENTITIES.get(request.surface, frozenset())
    supported = bundle.supported_schema_identities
    if not supported and publication.state is PublicationState.SYNTHETIC:
        supported = tuple(fixed) if request.source_id == SCREENER_SOURCE else ()
    if request.schema_identity not in supported:
        raise VendorGenerationError("vendor schema is not supported by its published extractor")
    if request.source_id != SCREENER_SOURCE or request.schema_identity not in fixed:
        raise VendorGenerationError("no fixed composer exists for this vendor source/schema")
    pin = next(
        row
        for row in publication.extractor_pins
        if (row.source_id, row.surface) == (request.source_id, request.surface)
    )
    return pin, role, declarations[0].disposition


def _capture(
    request: VendorRequest, capture_id: int, repository: EvidenceRepository
) -> CaptureReference:
    rows = repository.get_capture_refs([capture_id])
    if len(rows) != 1:
        raise VendorGenerationError("vendor capture is not pre-registered")
    row = rows[0]
    if (
        row.capture_ref_id != capture_id
        or (row.source_id, row.surface) != (request.source_id, request.surface)
        or request.retained is None
        or row.blob_sha256 != request.retained.expected_sha256
        or len(row.record_sha256) != 64
        or row.registered_at.tzinfo is None
        or row.first_seen_at.tzinfo is None
        or row.first_seen_at > row.registered_at
    ):
        raise VendorGenerationError("vendor capture source, body, record or store time differs")
    return row


def _issuer_scope(
    request: VendorRequest,
    context: ScreenerComposerContext,
    *,
    config_root: Path,
    repository: EvidenceRepository,
) -> tuple[SettingsRecord, tuple[EvidenceInputRecord, ...]]:
    if (
        request.source_id != SCREENER_SOURCE
        or FAMILY_BY_SECTION[context.section] is not request.statement_family
    ):
        raise VendorGenerationError("Screener context and statement family differ")
    identifiers = repository.issuer_identifiers(request.entity_id)
    binding = context.binding
    if (identifiers.entity_id, identifiers.nse_symbol, identifiers.bse_scrip) != (
        request.entity_id,
        binding.symbol,
        binding.bse_code,
    ) or binding.identity_evidence_ref != "config/watchlist.yaml":
        raise VendorGenerationError(
            "Screener binding does not match stored entity/listing evidence"
        )
    body = read_safe(config_root, "watchlist.yaml")
    if hashlib.sha256(body).hexdigest() != context.identity_config_sha256:
        raise VendorGenerationError("Screener identity configuration content drift")
    document = yaml.safe_load(body)
    stocks = [
        stock["identifiers"]
        for stock in document["stocks"]
        if stock["identifiers"]["nse_symbol"] == binding.symbol
    ]
    if len(stocks) != 1:
        raise VendorGenerationError("Screener issuer is absent or ambiguous in verified config")
    actual = stocks[0]
    topology = binding.topology
    if actual.get("needs_verification") or (
        str(actual["bse_scrip"]),
        actual.get("screener_company_id"),
        actual.get("screener_warehouse_id_consolidated"),
        actual.get("screener_warehouse_id_standalone"),
    ) != (
        binding.bse_code,
        binding.company_id,
        topology.consolidated_warehouse_id,
        topology.standalone_warehouse_id,
    ):
        raise VendorGenerationError("Screener issuer/topology is unverified or differs from config")
    settings = repository.settings_as_of(
        request.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock()
    )
    if settings is None or settings.value_text != str(binding.fiscal_year_end_month):
        raise VendorGenerationError("Screener fiscal month lacks matching stored settings evidence")
    records = repository.get_settings_records([settings.id])
    if records != (settings,):
        raise VendorGenerationError("Screener qualification setting differs from exact id reload")
    evidence_ids = sorted({identifiers.evidence_input_id, settings.evidence_input_id})
    evidence = repository.get_evidence_inputs(evidence_ids)
    if sorted(row.id for row in evidence) != evidence_ids:
        raise VendorGenerationError("Screener issuer/settings evidence is incomplete")
    _prove_identity_artifact(
        request.entity_id,
        identifiers.nse_symbol,
        identifiers.isin,
        identifiers.bse_scrip,
        binding.fiscal_year_end_month,
        evidence,
        config_root=config_root,
        repository=repository,
    )
    return settings, evidence


def _prove_identity_artifact(
    entity_id: int,
    symbol: str,
    isin: str,
    bse_scrip: str,
    fiscal_month: int,
    evidence: tuple[EvidenceInputRecord, ...],
    *,
    config_root: Path,
    repository: EvidenceRepository,
) -> None:
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", symbol):
        raise VendorGenerationError("issuer symbol has no safe source identity artifact convention")
    body = read_safe(config_root, f"identity/{symbol.lower()}.yaml")
    try:
        identity = IssuerIdentityInput.model_validate(
            {**yaml.safe_load(body), "content_sha256": hashlib.sha256(body).hexdigest()}
        )
    except (ValueError, TypeError, yaml.YAMLError) as error:
        raise VendorGenerationError("source identity artifact is invalid") from error
    if {citation.field for citation in identity.citations} != CITED_FIELDS:
        raise VendorGenerationError("source identity artifact citations are incomplete or unknown")
    if (
        identity.nse_symbol,
        identity.isin,
        identity.bse_scrip,
        repository.entity_id(identity.entity_key),
        identity.fiscal_year_end_month,
    ) != (symbol, isin, bse_scrip, entity_id, fiscal_month):
        raise VendorGenerationError("source identity artifact differs from entity/listings/setting")
    for record in evidence:
        if (record.kind, record.label, record.content_sha256) != (
            EvidenceInputKind.ISSUER_IDENTITY,
            identity.entity_key,
            identity.content_sha256,
        ):
            raise VendorGenerationError(
                "issuer/settings source evidence kind/label/content hash differs"
            )


def _extract(
    request: VendorRequest,
    *,
    body: bytes,
    capture: CaptureReference,
    context: ScreenerComposerContext,
    input_anchor: DirectoryAnchor,
    repository: EvidenceRepository,
    publication: PublishedVendorConfig,
    extractor_pin: VendorExtractorPin,
) -> tuple[
    tuple[Occurrence, ...], ExtractionOutcome, tuple[str, ...], tuple[CaptureReference, ...]
]:
    supporting: tuple[CaptureReference, ...] = ()
    try:
        if (request.surface, request.schema_identity) == (PAGE_SURFACE, PAGE_SCHEMA):
            if context.parent is not None:
                raise VendorGenerationError("page composer cannot carry a schedule context")
            extraction = extract_screener_page(
                request,
                body=body,
                capture=capture,
                binding=context.binding,
                section=context.section,
                extractor_version=extractor_pin.version,
            )
        elif (request.surface, request.schema_identity) == (SCHEDULE_SURFACE, SCHEDULE_SCHEMA):
            page = context.supporting_page_request
            page_id = context.supporting_page_capture_ref_id
            if page is None or page_id is None or context.parent is None:
                raise VendorGenerationError("schedule lacks exact supporting page context")
            _authorize(page, publication)
            if (page.entity_id, page.basis, page.framework, page.statement_family, page.period) != (
                request.entity_id,
                request.basis,
                request.framework,
                request.statement_family,
                request.period,
            ):
                raise VendorGenerationError("supporting page scope differs from schedule request")
            page_capture = _capture(page, page_id, repository)
            page_body = load_vendor_bytes(page, input_anchor=input_anchor)
            metadata = None
            if context.metadata_binding is not None:
                metadata = load_vendor_bytes(
                    request.model_copy(update={"retained": context.metadata_binding}),
                    input_anchor=input_anchor,
                )
            supporting = (page_capture,)
            extraction = extract_screener_schedule(
                request,
                body=body,
                capture=capture,
                page_request=page,
                page_body=page_body,
                page_capture=page_capture,
                binding=context.binding,
                section=context.section,
                parent=context.parent,
                metadata_body=metadata,
                extractor_version=extractor_pin.version,
            )
        else:
            raise VendorGenerationError("unsupported fixed vendor schema dispatch")
    except ScreenerExtractionError as error:
        return (), error.outcome, (str(error),), supporting
    periods = {row.period for row in extraction.occurrences if row.period is not None}
    if request.period not in periods:
        raise VendorGenerationError(
            "source headers do not prove the requested exact period; annual/TTM is never relabelled"
        )
    return extraction.occurrences, extraction.outcome, extraction.reasons, supporting


def _attempt(
    request: VendorRequest,
    capture: CaptureReference,
    pin: VendorExtractorPin,
    logical: str,
    outcome: ExtractionOutcome,
    reasons: tuple[str, ...],
) -> AcquisitionAttempt:
    end = request.period.instant or request.period.end
    assert end is not None
    return AcquisitionAttempt(
        attempt_id=None,
        stage=AttemptStage.EXTRACTION,
        source_id=request.source_id,
        surface=request.surface,
        entity_id=request.entity_id,
        period_end=end,
        basis=request.basis,
        framework=request.framework,
        representation=request.representation,
        statement_family=request.statement_family,
        package_id=None,
        outcome=outcome,
        reason="; ".join(reasons) or None,
        capture=capture,
        input_sha256=request.identity_sha256(),
        extractor_version=pin.version,
        attempted_at=None,
        extraction_context_sha256=logical,
    )


def scoped_existing_occurrences(
    prepared: VendorPreparation,
    existing: Sequence[Occurrence],
    *,
    input_anchor: DirectoryAnchor | None,
    composer_context: VendorComposerContext,
) -> tuple[Occurrence, ...]:
    """Reprove every shared-capture row; return only the current complete semantic section."""
    expected = {row.anchor_key: row for row in prepared.generation.occurrences}
    current: list[Occurrence] = []
    foreign: dict[str, dict[str, Occurrence]] = {}
    request = prepared.generation.request
    capture = prepared.generation.capture
    for row in existing:
        wanted = expected.get(row.anchor_key)
        if wanted is None:
            section_name = str(row.native_context.get("section", ""))
            if (
                request.surface != PAGE_SURFACE
                or not isinstance(composer_context, ScreenerComposerContext)
                or input_anchor is None
                or capture is None
            ):
                raise VendorGenerationError("stored occurrence has no valid shared-capture context")
            if section_name not in foreign:
                try:
                    section = Section(section_name)
                except ValueError as error:
                    raise VendorGenerationError(
                        "stored occurrence has an unknown semantic section"
                    ) from error
                section_request = request.model_copy(
                    update={"statement_family": FAMILY_BY_SECTION[section]}
                )
                extraction = extract_screener_page(
                    section_request,
                    body=load_vendor_bytes(request, input_anchor=input_anchor),
                    capture=capture,
                    binding=composer_context.binding,
                    section=section,
                    extractor_version=prepared.generation.extractor_pin.version,
                )
                foreign[section_name] = {item.anchor_key: item for item in extraction.occurrences}
            wanted = foreign[section_name].get(row.anchor_key)
        else:
            current.append(row)
        if wanted is None or _occurrence_payload(row) != _occurrence_payload(wanted):
            raise VendorGenerationError(
                "stored occurrence generation differs from retained semantic bytes"
            )
    return tuple(current)
