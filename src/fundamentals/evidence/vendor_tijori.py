"""Tijori retained financials: pinned bytes to native tables (occurrence mapping is D1b.1)."""

import hashlib
from datetime import datetime

from fundamentals.contracts.source_catalog import surface_authority
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriTable

SOURCE_ID = "tijori"
SURFACE = "TIJORI_FINANCIALS"


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
    surface_authority(SOURCE_ID, SURFACE)
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
