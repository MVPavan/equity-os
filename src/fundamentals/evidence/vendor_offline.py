"""Capture-free draft outcomes for vendor inputs that have not been retained.

These preparations are not published generations and contain no numeric evidence. The
repository assigns actual store timestamps if their attempts are subsequently persisted.
"""

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    VendorExtractorPin,
    VersionPin,
)
from fundamentals.contracts.source_catalog import (
    SourceCatalog,
    SurfaceAuthority,
    UnknownSourceError,
)
from fundamentals.evidence.vendor_common import (
    VendorAuthorityError,
    VendorGeneration,
    VendorRequest,
    authorize_vendor,
)


def unavailable_generation(
    request: VendorRequest,
    *,
    source_id: str,
    surfaces: tuple[str, ...],
    representation: Representation,
    role: SourceRole,
    catalog: SourceCatalog,
    authority: SurfaceAuthority,
    extractor_pin: VendorExtractorPin,
    authority_pin: VersionPin,
) -> VendorGeneration:
    """An authorized missing binding is unavailable; undeclared authority is refused."""
    if (
        request.source_id != source_id
        or request.surface not in surfaces
        or request.representation is not representation
        or (extractor_pin.source_id, extractor_pin.surface) != (source_id, request.surface)
    ):
        raise ValueError("offline vendor request and extractor must name this exact source/surface")
    if request.retained is not None:
        raise ValueError(
            "a present binding requires actual retained admission, not a missing-input claim"
        )
    outcome = ExtractionOutcome.FAILED
    reason = "RETAINED_INPUT_UNAVAILABLE: no retained response binding; publication is unknown"
    try:
        actual_role = authorize_vendor(request, catalog=catalog, authority=authority)
        if actual_role is not role:
            raise VendorAuthorityError("this vendor cannot be promoted to another evidence role")
    except (UnknownSourceError, VendorAuthorityError):
        outcome = ExtractionOutcome.NOT_AUTHORISED
        reason = "SOURCE_SURFACE_NOT_AUTHORISED: explicit matching source authority required"
    end = request.period.instant or request.period.end
    assert end is not None
    attempt = AcquisitionAttempt(
        attempt_id=None,
        stage=AttemptStage.ACQUISITION,
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
        reason=reason,
        capture=None,
        input_sha256=request.identity_sha256(),
        extractor_version=extractor_pin.version,
        attempted_at=None,
    )
    return VendorGeneration(
        request=request,
        capture=None,
        attempts=(attempt,),
        extractor_pin=extractor_pin,
        source_authority_pin=authority_pin,
    )
