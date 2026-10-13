"""Tijori retained-only seams; numeric qualification waits for actual retained bodies."""

import hashlib
from datetime import datetime

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence import VendorExtractorPin, VersionPin
from fundamentals.contracts.source_catalog import SourceCatalog, SurfaceAuthority
from fundamentals.evidence.vendor_common import VendorGeneration, VendorRequest
from fundamentals.evidence.vendor_offline import unavailable_generation
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriTable

SOURCE_ID = "tijori"
SURFACE = "TIJORI_FINANCIALS"


def prepare_unavailable(
    request: VendorRequest,
    *,
    catalog: SourceCatalog,
    authority: SurfaceAuthority,
    extractor_pin: VendorExtractorPin,
    authority_pin: VersionPin,
) -> VendorGeneration:
    """Prepare an honest unavailable/refused draft; never declare publication absence."""
    return unavailable_generation(
        request,
        source_id=SOURCE_ID,
        surfaces=(SURFACE,),
        representation=Representation.HTML,
        role=SourceRole.INDEPENDENT_VENDOR,
        catalog=catalog,
        authority=authority,
        extractor_pin=extractor_pin,
        authority_pin=authority_pin,
    )


def read_financials(
    body: bytes,
    *,
    expected_sha256: str,
    slug: str,
    expected_symbol: str,
    expected_company_id: int,
    source_url: str,
    claimed_retrieved_at: datetime,
) -> tuple[TijoriTable, ...]:
    """Read pinned native tables through the existing offline parser, with no canonical claim.

    Table scope, raw cells, precision and final-column labels remain native evidence;
    this function does not infer TTM intervals, qualification or first-seen timestamps.
    """
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError("Tijori body differs from its retained content pin")
    if claimed_retrieved_at.tzinfo is None:
        raise ValueError("retained retrieval claim must have an offset")
    return TijoriSource.parse_all_tables_bytes(
        body,
        slug=slug,
        expected_symbol=expected_symbol,
        expected_company_id=expected_company_id,
        source_url=source_url,
        retrieved_at=claimed_retrieved_at,
    )
