"""Acquisition of the typed data islands on Tijori's company overview page.

This module owns the page-level concerns of ``/company/<slug>/``: island
collection, the authentication and identity gates, per-section absence
semantics, and the metadata every section artifact carries. The per-section
shapes live in :mod:`fundamentals.ingest.tijori_overview_models`; the builders in
:mod:`fundamentals.ingest.tijori_overview_sections` and, for the company-details
header and its forensic checklist,
:mod:`fundamentals.ingest.tijori_overview_company`; their shared element helpers
in :mod:`fundamentals.ingest.tijori_overview_common`.

Identity FACT (owner capture, 2026-08-25): unlike the shareholding page, the
overview page DOES publish an identity island — ``company_details_data`` carries
both ``company_id`` and ``symbol`` — and it separately publishes the bare
``companyId`` island. Both are checked against the configured watchlist values,
conjunctively: the response is bound to the requested issuer or it is refused.

Absence is data, not failure. Tijori omits an island for a company that has no
such content, so a breadth run records a typed ``ABSENT`` outcome for it and
keeps going; asking for that one section explicitly is an error, because the
caller asked for something the page does not have.

The ``company_details`` section reads the identity island, which is required, so
it is present whenever the identity gate passed. A breadth run that found no
OTHER section is therefore not an acquisition — it is the header the caller
already knew — and it fails rather than reporting success over one artifact.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import structlog

from fundamentals.ingest.tijori_overview_common import SectionContext, reject_duplicate_anchors
from fundamentals.ingest.tijori_overview_models import (
    COMPANY_DETAILS_DATA_ISLAND_ID,
    COMPANY_ID_ISLAND_ID,
    COMPANY_STATUS_ISLAND_ID,
    IS_AUTH_ISLAND_ID,
    IS_BANKING_ISLAND_ID,
    OVERVIEW_LOCKS_ISLAND_ID,
    OVERVIEW_PAGE_LABEL,
    SECTION_ISLAND_IDS,
    TijoriOverviewIdentityError,
    TijoriOverviewMetadata,
    TijoriOverviewSection,
    TijoriOverviewSectionAbsentError,
    TijoriOverviewSectionBase,
    TijoriOverviewSectionOutcome,
    TijoriOverviewSectionsAbsentError,
)
from fundamentals.ingest.tijori_overview_sections import SECTION_BUILDERS
from fundamentals.ingest.tijori_page import collect_islands, decode_document
from fundamentals.ingest.tijori_tables import (
    PLAN_DETAILS_ISLAND_ID,
    TijoriIslandStatus,
    TijoriParseError,
    TijoriUnparseableIsland,
    build_page_access,
)

_LOGGER = structlog.get_logger(__name__)

_SYMBOL_FIELD = "symbol"
_COMPANY_ID_FIELD = "company_id"

_REQUIRED_ISLAND_IDS = (IS_AUTH_ISLAND_ID, COMPANY_DETAILS_DATA_ISLAND_ID)
# Every data island is optional: a section Tijori does not publish for this
# company must be recorded as absent, never turned into a page-level failure.
_METADATA_ISLAND_IDS = (
    COMPANY_ID_ISLAND_ID,
    OVERVIEW_LOCKS_ISLAND_ID,
    PLAN_DETAILS_ISLAND_ID,
    COMPANY_STATUS_ISLAND_ID,
    IS_BANKING_ISLAND_ID,
)
_OPTIONAL_ISLAND_IDS = _METADATA_ISLAND_IDS + tuple(
    island_id for island_id in SECTION_ISLAND_IDS.values() if island_id not in _REQUIRED_ISLAND_IDS
)

# Every section except the identity header, which is present by construction
# once the identity gate has passed.
_DATA_SECTIONS = frozenset(
    section
    for section in TijoriOverviewSection
    if section is not TijoriOverviewSection.COMPANY_DETAILS
)

_NULL_ISLAND_DETAIL = "island published as JSON null"
_MISSING_ISLAND_DETAIL = "island not present on the page"


def _verified_identity(
    islands: dict[str, Any], *, expected_symbol: str, expected_company_id: int
) -> tuple[str, int, tuple[str, ...]]:
    """Bind the response to the configured issuer, or refuse it.

    ``company_details_data`` is required to agree on both symbol and company id.
    The bare ``companyId`` island is checked whenever it is present — including
    when it is present but unreadable, which is drift on an identity marker and
    therefore fatal rather than ignored.
    """
    details = islands.get(COMPANY_DETAILS_DATA_ISLAND_ID)
    if not isinstance(details, dict):
        raise TijoriOverviewIdentityError(
            f"tijori overview island {COMPANY_DETAILS_DATA_ISLAND_ID!r} must contain an object"
        )
    symbol = details.get(_SYMBOL_FIELD)
    if not isinstance(symbol, str) or not symbol.strip():
        raise TijoriOverviewIdentityError(
            f"tijori overview {COMPANY_DETAILS_DATA_ISLAND_ID} symbol is missing or invalid"
        )
    if symbol.strip() != expected_symbol.strip():
        raise TijoriOverviewIdentityError(
            "tijori overview identity mismatch: "
            f"requested symbol {expected_symbol.strip()!r}, response symbol {symbol.strip()!r}"
        )
    company_id = details.get(_COMPANY_ID_FIELD)
    if not isinstance(company_id, int) or isinstance(company_id, bool):
        raise TijoriOverviewIdentityError(
            f"tijori overview {COMPANY_DETAILS_DATA_ISLAND_ID} company_id is missing or invalid"
        )
    if company_id != expected_company_id:
        raise TijoriOverviewIdentityError(
            "tijori overview identity mismatch: "
            f"requested company ID {expected_company_id}, response company ID {company_id}"
        )
    matched = [COMPANY_DETAILS_DATA_ISLAND_ID]
    if COMPANY_ID_ISLAND_ID in islands:
        declared = islands[COMPANY_ID_ISLAND_ID]
        if not isinstance(declared, int) or isinstance(declared, bool):
            raise TijoriOverviewIdentityError(
                f"tijori overview island {COMPANY_ID_ISLAND_ID!r} is not a company ID: {declared!r}"
            )
        if declared != company_id:
            raise TijoriOverviewIdentityError(
                "tijori overview identity mismatch: "
                f"island {COMPANY_ID_ISLAND_ID!r} company ID {declared}, "
                f"{COMPANY_DETAILS_DATA_ISLAND_ID} company ID {company_id}"
            )
        matched.append(COMPANY_ID_ISLAND_ID)
    return symbol.strip(), company_id, tuple(matched)


def _section_outcome(
    section: TijoriOverviewSection, islands: dict[str, Any]
) -> TijoriOverviewSectionOutcome:
    """Classify one section's island as present, absent, or undecodable."""
    island_id = SECTION_ISLAND_IDS[section]
    if island_id not in islands:
        return TijoriOverviewSectionOutcome(
            section=section,
            island_id=island_id,
            status=TijoriIslandStatus.ABSENT,
            detail=_MISSING_ISLAND_DETAIL,
        )
    island = islands[island_id]
    if isinstance(island, TijoriUnparseableIsland):
        return TijoriOverviewSectionOutcome(
            section=section,
            island_id=island_id,
            status=TijoriIslandStatus.UNPARSEABLE,
            detail=island.error,
        )
    if island is None:
        return TijoriOverviewSectionOutcome(
            section=section,
            island_id=island_id,
            status=TijoriIslandStatus.ABSENT,
            detail=_NULL_ISLAND_DETAIL,
        )
    return TijoriOverviewSectionOutcome(
        section=section, island_id=island_id, status=TijoriIslandStatus.PRESENT
    )


def _optional_metadata_string(islands: dict[str, Any], island_id: str) -> str | None:
    """Read one optional metadata island published as a plain string."""
    value = islands.get(island_id)
    return value if isinstance(value, str) and value.strip() else None


def _optional_metadata_bool(islands: dict[str, Any], island_id: str) -> bool | None:
    """Read one optional metadata island published as a plain boolean."""
    value = islands.get(island_id)
    return value if isinstance(value, bool) else None


def _build_metadata(
    islands: dict[str, Any],
    outcomes: tuple[TijoriOverviewSectionOutcome, ...],
    *,
    slug: str,
    symbol: str,
    company_id: int,
    identity_island_ids: tuple[str, ...],
    source_url: str,
    content_sha256: str,
    retrieved_at: datetime,
) -> TijoriOverviewMetadata:
    """Assemble the metadata every section artifact of this page carries."""
    return TijoriOverviewMetadata(
        slug=slug,
        symbol=symbol,
        company_id=company_id,
        source_url=source_url,
        file_sha256=content_sha256,
        retrieved_at=retrieved_at,
        identity_island_ids=identity_island_ids,
        section_outcomes=outcomes,
        company_status=_optional_metadata_string(islands, COMPANY_STATUS_ISLAND_ID),
        is_banking=_optional_metadata_bool(islands, IS_BANKING_ISLAND_ID),
        access=build_page_access(
            financials_locks=islands.get(OVERVIEW_LOCKS_ISLAND_ID),
            plan_details=islands.get(PLAN_DETAILS_ISLAND_ID),
            locks_island_id=OVERVIEW_LOCKS_ISLAND_ID,
        ),
    )


def _refuse_absent_section(outcome: TijoriOverviewSectionOutcome) -> None:
    """Turn an explicitly requested but unusable section into a typed refusal."""
    if outcome.status is TijoriIslandStatus.PRESENT:
        return
    raise TijoriOverviewSectionAbsentError(
        f"tijori overview section {outcome.section.value!r} is not available: island "
        f"{outcome.island_id!r} is {outcome.status.value} ({outcome.detail})"
    )


def build_tijori_overview(
    raw: bytes,
    *,
    slug: str,
    expected_symbol: str,
    expected_company_id: int,
    source_url: str,
    retrieved_at: datetime,
    section: TijoriOverviewSection | None = None,
) -> tuple[TijoriOverviewSectionBase, ...]:
    """Build the typed overview sections from one rendered overview page.

    With ``section`` unset every published section is built and the absent ones
    are recorded in the metadata of each artifact. With ``section`` set, that one
    section is built or the call fails with a typed absence error.
    """
    if not slug.strip():
        raise TijoriParseError("tijori requested slug is empty")
    if not expected_symbol.strip():
        raise TijoriParseError("tijori expected symbol is empty")
    document = decode_document(raw, page_label=OVERVIEW_PAGE_LABEL)
    islands = collect_islands(
        document,
        required_islands=_REQUIRED_ISLAND_IDS,
        optional_islands=_OPTIONAL_ISLAND_IDS,
    )
    if islands.get(IS_AUTH_ISLAND_ID) is not True:
        raise TijoriParseError("tijori response is not authenticated")
    symbol, company_id, identity_island_ids = _verified_identity(
        islands, expected_symbol=expected_symbol, expected_company_id=expected_company_id
    )
    outcomes = tuple(_section_outcome(known, islands) for known in TijoriOverviewSection)
    metadata = _build_metadata(
        islands,
        outcomes,
        slug=slug,
        symbol=symbol,
        company_id=company_id,
        identity_island_ids=identity_island_ids,
        source_url=source_url,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        retrieved_at=retrieved_at,
    )
    if section is not None:
        requested = next(outcome for outcome in outcomes if outcome.section is section)
        _refuse_absent_section(requested)
        selected: tuple[TijoriOverviewSectionOutcome, ...] = (requested,)
    else:
        selected = tuple(
            outcome for outcome in outcomes if outcome.status is TijoriIslandStatus.PRESENT
        )
        if not any(outcome.section in _DATA_SECTIONS for outcome in selected):
            unavailable = ", ".join(
                f"{outcome.section.value}={outcome.status.value}"
                for outcome in outcomes
                if outcome.section in _DATA_SECTIONS
            )
            raise TijoriOverviewSectionsAbsentError(
                f"tijori overview page for {slug!r} carries no modeled data section beyond its "
                f"identity header: {unavailable}"
            )
    sections = tuple(
        SECTION_BUILDERS[outcome.section](
            islands[outcome.island_id],
            SectionContext(
                section=outcome.section,
                island_id=outcome.island_id,
                source_url=source_url,
                content_sha256=metadata.file_sha256,
                retrieved_at=retrieved_at,
                metadata=metadata,
            ),
        )
        for outcome in selected
    )
    for built in sections:
        reject_duplicate_anchors(built, built.section.value)
    _LOGGER.info(
        "tijori_overview_parsed",
        slug=slug,
        company_id=company_id,
        sections=[built.section.value for built in sections],
        absent_sections=[
            outcome.section.value
            for outcome in outcomes
            if outcome.status is not TijoriIslandStatus.PRESENT
        ],
        identity_islands=identity_island_ids,
    )
    return sections
