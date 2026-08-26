"""Reading one company part each: fetch what the page offered, then check it.

Split from :mod:`fundamentals.ingest.screener_company`, which owns the order of
the work and the evidence bookkeeping. Each function here is the whole of one
part: it turns the page's own hooks into requests, hands each response to its
reader, and records what the response established.

They share one shape on purpose. A part that is not offered records that and
costs nothing; a document that is refused is recorded against its own part with
its bytes retained, and the part carries on; only a rate limit stops anything,
because only a rate limit is the source asking us to stop. That is what keeps a
single redirected modal from discarding a run's worth of fetched bodies.
"""

from __future__ import annotations

from typing import Any

import structlog

from fundamentals.ingest.screener_company_artifacts import (
    DocumentEvidence,
    InvestorBucket,
    QuickRatioList,
    SegmentTable,
    ShareholdingTable,
)
from fundamentals.ingest.screener_company_discovery import top_ratios_list
from fundamentals.ingest.screener_company_fragments import (
    read_corporate_actions,
    read_peers,
    read_quick_ratios,
    read_related_party,
)
from fundamentals.ingest.screener_company_models import (
    AssertionResult,
    Binding,
    CompanyPart,
    PageHooks,
    Periodicity,
    ScreenerCompanyError,
    Validation,
    ValidationStatus,
    absolute_url,
    assert_document_path,
    investors_path,
    investors_url,
    peers_path,
    peers_url,
    quick_ratios_path,
    quick_ratios_url,
    segments_path,
    segments_url,
)
from fundamentals.ingest.screener_company_sweep import NO_WAREHOUSE_ID, NOT_OFFERED, Sweep
from fundamentals.ingest.screener_financials_models import (
    IdentityStrength,
    ScreenerFinancialsError,
    Section,
    SectionTable,
)
from fundamentals.ingest.screener_financials_tables import read_section
from fundamentals.ingest.screener_segments import read_segments
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.screener_session_page import parse_document
from fundamentals.ingest.screener_shareholding import (
    read_investor_bucket,
    read_shareholding_table,
)

_LOGGER = structlog.get_logger(__name__)

_DOCUMENT_EVENT = "screener_company_document_read"

# Every refusal a part may raise. ``ScreenerFinancialsError`` is here because the
# shared table reader is what raises ``AmbiguousStructureError`` and
# ``DuplicateAnchorError``, and those describe ONE fragment's structure: a peers
# table carrying two ``data-table`` elements says nothing about the
# corporate-actions modal, so it must not take the run with it.
PART_REFUSALS = (ScreenerCompanyError, ScreenerFinancialsError)

PAGE_QUICK_RATIOS_DOCUMENT_ID = "page:#top-ratios"


def read_investors(
    root: Any,
    sweep: Sweep,
    *,
    hooks: PageHooks,
    company_id: int,
    source_id: str,
    page_sha256: str,
    retrieved_at: Any,
) -> tuple[tuple[ShareholdingTable, ...], tuple[InvestorBucket, ...]]:
    """Read both shareholding tables, then every drill-down they offer.

    The tables come first and unconditionally: they are page-asserted evidence
    in their own right, and they are also the only thing the drill-downs can be
    checked against, so a drill-down fetched before them would have nothing to
    reconcile with.
    """
    tables = tuple(
        table
        for periodicity in Periodicity
        if (
            table := read_shareholding_table(
                root,
                periodicity,
                source_id=source_id,
                file_sha256=page_sha256,
                retrieved_at=retrieved_at,
            )
        )
        is not None
    )
    by_periodicity = {table.periodicity: table for table in tables}
    page_documents = tuple(
        DocumentEvidence(
            document_id=table.table_id,
            binding=Binding.PAGE_ASSERTED,
            validation=Validation.NONE,
            validation_status=ValidationStatus.NOT_APPLICABLE,
            page_table=True,
        )
        for table in tables
    )
    if not hooks.investors:
        sweep.record(
            CompanyPart.INVESTORS,
            offered=False,
            documents=page_documents,
            note=NOT_OFFERED,
        )
        return tables, ()

    buckets: list[InvestorBucket] = []
    for hook in hooks.investors:
        if sweep.rate_limited:
            break
        name = f"{hook.bucket}_{hook.periodicity.value}"
        url = investors_url(company_id, bucket=hook.bucket, periodicity=hook.periodicity)
        document_id = investors_path(company_id, bucket=hook.bucket, periodicity=hook.periodicity)
        fetched = sweep.fetch(part=CompanyPart.INVESTORS, name=name, url=url, is_json=True)
        if fetched is None:
            # A rate limit means stop asking; anything else means this one
            # bucket did not arrive, and the buckets after it are unaffected.
            if sweep.rate_limited:
                break
            continue
        try:
            bucket = read_investor_bucket(
                fetched.raw_body,
                hook=hook,
                table=by_periodicity.get(hook.periodicity),
                url=url,
                document_id=document_id,
                body_sha256=fetched.content_sha256,
                source_id=source_id,
                retrieved_at=fetched.fetched_at,
            )
        except PART_REFUSALS as error:
            sweep.refuse(
                part=CompanyPart.INVESTORS,
                name=name,
                url=url,
                document_id=document_id,
                sha=fetched.content_sha256,
                error=error,
            )
            continue
        _LOGGER.info(
            _DOCUMENT_EVENT,
            part=CompanyPart.INVESTORS.value,
            name=name,
            outcome=bucket.outcome.value,
            holders=len(bucket.holders),
        )
        buckets.append(bucket)

    documents = page_documents + tuple(
        DocumentEvidence(
            document_id=bucket.document_id,
            binding=bucket.binding,
            validation=bucket.validation,
            validation_status=bucket.validation_status,
        )
        for bucket in buckets
    )
    sweep.record(
        CompanyPart.INVESTORS,
        offered=True,
        documents=documents,
        note=f"{len(buckets)} bucket(s) read across {len(tables)} shareholding table(s)",
    )
    return tables, tuple(buckets)


def read_segments_part(
    root: Any,
    sweep: Sweep,
    *,
    hooks: PageHooks,
    company_id: int,
    basis: Basis,
    source_id: str,
    retrieved_at: Any,
) -> tuple[SegmentTable, ...]:
    """Fetch each offered Product Segments table and hold its Sales line to the page."""
    if not hooks.segments:
        sweep.record(CompanyPart.SEGMENTS, offered=False, note=NOT_OFFERED)
        return ()
    tables: list[SegmentTable] = []
    for hook in hooks.segments:
        if sweep.rate_limited:
            break
        name = f"{hook.section}_{hook.segment_type}"
        url = segments_url(
            company_id, section=hook.section, segment_type=hook.segment_type, basis=basis
        )
        document_id = segments_path(
            company_id, section=hook.section, segment_type=hook.segment_type, basis=basis
        )
        fetched = sweep.fetch(part=CompanyPart.SEGMENTS, name=name, url=url, is_json=False)
        if fetched is None:
            if sweep.rate_limited:
                break
            continue
        try:
            table = read_segments(
                fetched.raw_body,
                hook=hook,
                page_section=_page_section(
                    root, hook.section, source_id=source_id, retrieved_at=retrieved_at
                ),
                url=url,
                document_id=document_id,
                body_sha256=fetched.content_sha256,
                source_id=source_id,
                retrieved_at=fetched.fetched_at,
                parse=parse_document,
            )
        except PART_REFUSALS as error:
            sweep.refuse(
                part=CompanyPart.SEGMENTS,
                name=name,
                url=url,
                document_id=document_id,
                sha=fetched.content_sha256,
                error=error,
            )
            continue
        _LOGGER.info(
            _DOCUMENT_EVENT,
            part=CompanyPart.SEGMENTS.value,
            name=name,
            outcome=table.outcome.value,
            lines=len(table.lines),
        )
        tables.append(table)
    sweep.record(
        CompanyPart.SEGMENTS,
        offered=True,
        documents=tuple(
            DocumentEvidence(
                document_id=table.document_id,
                binding=table.binding,
                validation=table.validation,
                validation_status=table.validation_status,
            )
            for table in tables
        ),
        note=f"{len(tables)} segments table(s) read",
    )
    return tuple(tables)


def _page_section(
    root: Any, section_id: str, *, source_id: str, retrieved_at: Any
) -> SectionTable | None:
    """The page section a segments fragment expands, parsed for its Sales row.

    Parsed here rather than taken from a Slice 1 artifact so this command stands
    alone: ``screener-company`` may be run without ``screener-financials`` ever
    having been run for this stock.
    """
    try:
        section = Section(section_id)
    except ValueError:
        return None
    try:
        return read_section(
            root,
            section,
            source_id=source_id,
            file_sha256="0" * 64,
            retrieved_at=retrieved_at,
        )
    except ScreenerCompanyError:
        return None


def read_related_party_part(
    sweep: Sweep, *, hooks: PageHooks, source_id: str, retrieved_at: Any
) -> Any:
    """Fetch and read the Related Party modal the page links to, if any."""
    return read_simple_fragment(
        sweep,
        part=CompanyPart.RELATED_PARTY,
        path=hooks.related_party_url,
        name="related_party",
        reader=lambda fetched, url, path: read_related_party(
            fetched.raw_body,
            url=url,
            document_id=path,
            body_sha256=fetched.content_sha256,
            source_id=source_id,
            retrieved_at=fetched.fetched_at,
            parse=parse_document,
        ),
    )


def read_actions_part(sweep: Sweep, *, hooks: PageHooks, source_id: str, retrieved_at: Any) -> Any:
    """Fetch and read the Corporate actions modal the page links to, if any."""
    return read_simple_fragment(
        sweep,
        part=CompanyPart.CORPORATE_ACTIONS,
        path=hooks.corporate_actions_url,
        name="corporate_actions",
        reader=lambda fetched, url, path: read_corporate_actions(
            fetched.raw_body,
            url=url,
            document_id=path,
            body_sha256=fetched.content_sha256,
            source_id=source_id,
            retrieved_at=fetched.fetched_at,
            parse=parse_document,
        ),
    )


def read_simple_fragment(
    sweep: Sweep,
    *,
    part: CompanyPart,
    path: str | None,
    name: str,
    reader: Any,
) -> Any:
    """Fetch one page-linked modal and read it, recording what happened."""
    if path is None:
        sweep.record(part, offered=False, note=NOT_OFFERED)
        return None
    try:
        url = absolute_url(assert_document_path(path, part=part.value))
    except PART_REFUSALS as error:
        sweep.refuse(part=part, name=name, document_id=path, error=error)
        return None
    fetched = sweep.fetch(part=part, name=name, url=url, is_json=False)
    if fetched is None:
        return None
    try:
        artifact = reader(fetched, url, path)
    except PART_REFUSALS as error:
        sweep.refuse(
            part=part,
            name=name,
            url=url,
            document_id=path,
            sha=fetched.content_sha256,
            error=error,
        )
        return None
    sweep.record(
        part,
        offered=True,
        documents=(
            DocumentEvidence(
                document_id=path,
                binding=Binding.CONFIGURED_URL_ONLY,
                validation=Validation.NONE,
                validation_status=ValidationStatus.NOT_APPLICABLE,
            ),
        ),
        note="",
    )
    _LOGGER.info(_DOCUMENT_EVENT, part=part.value, name=name)
    return artifact


def read_peers_part(
    sweep: Sweep,
    *,
    hooks: PageHooks,
    company_id: int,
    basis: Basis,
    source_id: str,
    retrieved_at: Any,
) -> Any:
    """Fetch the peers fragment and assert it is this company's, on this basis."""
    if hooks.warehouse_id is None:
        sweep.record(
            CompanyPart.PEERS,
            offered=False,
            note=NO_WAREHOUSE_ID,
        )
        return None
    url = peers_url(hooks.warehouse_id)
    path = peers_path(hooks.warehouse_id)
    fetched = sweep.fetch(part=CompanyPart.PEERS, name="peers", url=url, is_json=False)
    if fetched is None:
        return None
    try:
        table = read_peers(
            fetched.raw_body,
            company_id=company_id,
            basis=basis,
            url=url,
            document_id=path,
            body_sha256=fetched.content_sha256,
            source_id=source_id,
            retrieved_at=fetched.fetched_at,
            parse=parse_document,
        )
    except PART_REFUSALS as error:
        sweep.refuse(
            part=CompanyPart.PEERS,
            name="peers",
            url=url,
            document_id=path,
            sha=fetched.content_sha256,
            error=error,
        )
        return None
    sweep.record(
        CompanyPart.PEERS,
        offered=True,
        documents=(
            DocumentEvidence(
                document_id=path,
                binding=Binding.BODY_ASSERTED,
                validation=Validation.NONE,
                validation_status=ValidationStatus.NOT_APPLICABLE,
                identity_assertion=AssertionResult.PASSED,
            ),
        ),
        note=f"self row at position {table.self_row_position}, {basis.value} basis asserted; "
        "peer values remain configured-url-only",
    )
    _LOGGER.info(
        _DOCUMENT_EVENT,
        part=CompanyPart.PEERS.value,
        name="peers",
        self_row=table.self_row_position,
        rows=len(table.rows),
    )
    return table


def read_quick_ratios_part(
    root: Any,
    sweep: Sweep,
    *,
    hooks: PageHooks,
    source_id: str,
    page_sha256: str,
    retrieved_at: Any,
) -> tuple[QuickRatioList, ...]:
    """Read the page's own header ratios and the account-configured API list.

    Both are kept because they are different objects: ``#top-ratios`` is what
    Screener shows every visitor for this company, while the API list is the
    signed-in owner's Manage-quick_ratios selection and so says as much about
    the account as about the issuer.
    """
    lists: list[QuickRatioList] = []
    page_block = top_ratios_list(root)
    if page_block is not None:
        lists.append(
            read_quick_ratios(
                None,
                element=page_block,
                url=None,
                document_id=PAGE_QUICK_RATIOS_DOCUMENT_ID,
                body_sha256=page_sha256,
                source_id=source_id,
                retrieved_at=retrieved_at,
                parse=parse_document,
                configured_by_account=False,
                identity_strength=IdentityStrength.PAGE_ASSERTED,
                binding=Binding.PAGE_ASSERTED,
            )
        )
    if hooks.warehouse_id is None:
        sweep.record(
            CompanyPart.QUICK_RATIOS,
            offered=bool(lists),
            documents=_ratio_documents(lists),
            note=NO_WAREHOUSE_ID,
        )
        return tuple(lists)
    url = quick_ratios_url(hooks.warehouse_id)
    path = quick_ratios_path(hooks.warehouse_id)
    fetched = sweep.fetch(
        part=CompanyPart.QUICK_RATIOS, name="quick_ratios", url=url, is_json=False
    )
    if fetched is not None:
        lists.append(
            read_quick_ratios(
                fetched.raw_body,
                element=None,
                url=url,
                document_id=path,
                body_sha256=fetched.content_sha256,
                source_id=source_id,
                retrieved_at=fetched.fetched_at,
                parse=parse_document,
                configured_by_account=True,
                identity_strength=IdentityStrength.CONFIGURED_URL_ONLY,
                binding=Binding.CONFIGURED_URL_ONLY,
            )
        )
    sweep.record(
        CompanyPart.QUICK_RATIOS,
        offered=True,
        documents=_ratio_documents(lists),
        note=f"{len(lists)} ratio list(s) read",
    )
    return tuple(lists)


def _ratio_documents(lists: list[QuickRatioList]) -> tuple[DocumentEvidence, ...]:
    """Per-list evidence: the page block and the account's API list differ in binding."""
    return tuple(
        DocumentEvidence(
            document_id=entry.document_id,
            binding=entry.binding,
            validation=Validation.NONE,
            validation_status=ValidationStatus.NOT_APPLICABLE,
            page_table=entry.binding is Binding.PAGE_ASSERTED,
        )
        for entry in lists
    )
