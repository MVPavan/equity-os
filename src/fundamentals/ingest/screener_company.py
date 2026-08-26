"""Orchestration: one proven company page, read into its sub-documents.

This is the only module that decides the *order* of Slice 2's work, and the
order is what makes it safe:

1. Slice 0 fetches and proves the page (session, identity, basis). Nothing here
   re-derives any of that; a page that did not carry the requested basis never
   reaches this module.
2. Every part's existence is discovered from the page's own controls
   (:mod:`fundamentals.ingest.screener_company_discovery`). A part whose control
   is absent is ``NOT_OFFERED`` and costs no request.
3. The Shareholding Pattern tables are read from the retained page bytes, before
   any drill-down is fetched, because they are what the drill-downs are checked
   against.
4. Every sub-document is fetched through the *same* session instance, so the
   page and its sub-documents share one spacing and one 429 budget. A full
   TITAN run is nineteen requests: the page, twelve investor buckets, two
   segments tables, related party, corporate actions, peers, quick ratios.
5. Each response is retained *before* it is interpreted, then checked.

Step 4 is where a run can stop short. A 429 that survives the bounded backoff
ends the sweep and the artifact records ``complete=False`` with the reason;
everything already read stays, and what is missing is named rather than implied.

A refusal behaves differently here than in Slice 1. There, one failed schedule
almost certainly means every schedule of the run is wrong the same way, so the
sweep stops. Here the parts are independent — a peers fragment that names the
wrong company says nothing about the corporate-actions modal — so a refusal ends
only its own part, the response is retained, the failure is recorded, and the
remaining parts still run. Only a rate limit stops the sweep, because only a rate
limit is the source telling us to stop. The run's ``acquisition`` still records
that something was refused.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_company_artifacts import (
    CompanyArtifact,
    CompanyMetadata,
    InvestorBucket,
    PartOutcome,
    QuickRatioList,
    SegmentTable,
    ShareholdingTable,
)
from fundamentals.ingest.screener_company_discovery import (
    read_page_hooks,
)
from fundamentals.ingest.screener_company_models import (
    ALL_PARTS,
    MAX_SUB_REQUESTS,
    Acquisition,
    CompanyPart,
    DocumentUnreadableError,
    PageHooks,
)
from fundamentals.ingest.screener_company_parts import (
    PART_REFUSALS,
    read_actions_part,
    read_investors,
    read_peers_part,
    read_quick_ratios_part,
    read_related_party_part,
    read_segments_part,
)
from fundamentals.ingest.screener_company_sweep import (
    MISSING_SECTION,
    OVER_BUDGET,
    OVER_BUDGET_INCOMPLETE,
    CompanyDocument,
    Sweep,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    ScreenerPageFetch,
)
from fundamentals.ingest.screener_session_page import parse_document

_LOGGER = structlog.get_logger(__name__)

_DOCUMENT_EVENT = "screener_company_document_read"
_REFUSED_EVENT = "screener_company_document_refused"
_ABORTED_EVENT = "screener_company_sweep_aborted"


class CompanyRun(BaseModel):
    """Everything one acquisition produced: the artifact and its evidence."""

    model_config = ConfigDict(frozen=True)

    artifact: CompanyArtifact
    page_body: bytes
    documents: tuple[CompanyDocument, ...] = ()


# Which page section each part's control lives in. A part whose section is
# present without its control is genuinely not offered; a part whose section is
# absent is the page changing shape, and the two must never be confused.
OWNING_SECTIONS: dict[CompanyPart, tuple[str, ...]] = {
    CompanyPart.INVESTORS: ("shareholding",),
    CompanyPart.SEGMENTS: ("quarters", "profit-loss"),
    CompanyPart.RELATED_PARTY: ("profit-loss",),
    CompanyPart.CORPORATE_ACTIONS: ("balance-sheet",),
    CompanyPart.PEERS: ("company-info",),
    CompanyPart.QUICK_RATIOS: ("company-info",),
}


def plan_sub_requests(hooks: PageHooks, parts: tuple[CompanyPart, ...]) -> int:
    """How many sub-requests the discovered hooks would make for these parts.

    Computed from the page before anything is fetched so the budget is checked
    against the plan rather than discovered by spending it.
    """
    planned = 0
    for part in parts:
        if not hooks.has(*OWNING_SECTIONS[part]):
            # A part whose owning section is absent is refused rather than
            # fetched, so it costs nothing and must not inflate the plan.
            continue
        if part is CompanyPart.INVESTORS:
            planned += len(hooks.investors)
        elif part is CompanyPart.SEGMENTS:
            planned += len(hooks.segments)
        elif part is CompanyPart.RELATED_PARTY:
            planned += hooks.related_party_url is not None
        elif part is CompanyPart.CORPORATE_ACTIONS:
            planned += hooks.corporate_actions_url is not None
        else:
            planned += hooks.warehouse_id is not None
    return planned


def read_company(
    page_fetch: ScreenerPageFetch,
    *,
    company_id: int,
    parts: tuple[CompanyPart, ...],
    source: ScreenerSessionSource,
) -> CompanyRun:
    """Acquire the requested parts of one proven company page on one basis."""
    metadata = page_fetch.metadata
    root = parse_document(page_fetch.raw_body.decode("utf-8", errors="replace"))
    hooks = read_page_hooks(root)
    basis = metadata.basis_requested
    retrieved_at = metadata.fetched_at
    planned = plan_sub_requests(hooks, parts)
    sweep = Sweep(source=source, planned=planned)
    if planned > MAX_SUB_REQUESTS:
        return _over_budget(page_fetch, hooks, company_id=company_id, parts=parts, planned=planned)

    shareholding: tuple[ShareholdingTable, ...] = ()
    investors: tuple[InvestorBucket, ...] = ()
    segments: tuple[SegmentTable, ...] = ()
    related_party = corporate_actions = peers = None
    quick_ratios: tuple[QuickRatioList, ...] = ()

    for part in parts:
        if not _section_present(sweep, part, hooks=hooks):
            continue
        # Every part runs inside the shared refusal boundary, including the
        # page tables it reads before its first request. A repeated column
        # label in the Shareholding header is a real refusal from the shared
        # table reader, and it happened outside this try until round 3 — so it
        # aborted the whole command and published nothing, exactly like the
        # redirected modal did. A part's structural surprises belong to that
        # part.
        try:
            if part is CompanyPart.INVESTORS:
                shareholding, investors = read_investors(
                    root,
                    sweep,
                    hooks=hooks,
                    company_id=company_id,
                    source_id=metadata.source_id,
                    page_sha256=metadata.content_sha256,
                    retrieved_at=retrieved_at,
                )
            elif part is CompanyPart.SEGMENTS:
                segments = read_segments_part(
                    root,
                    sweep,
                    hooks=hooks,
                    company_id=company_id,
                    basis=basis,
                    source_id=metadata.source_id,
                    retrieved_at=retrieved_at,
                )
            elif part is CompanyPart.RELATED_PARTY:
                related_party = read_related_party_part(
                    sweep, hooks=hooks, source_id=metadata.source_id, retrieved_at=retrieved_at
                )
            elif part is CompanyPart.CORPORATE_ACTIONS:
                corporate_actions = read_actions_part(
                    sweep, hooks=hooks, source_id=metadata.source_id, retrieved_at=retrieved_at
                )
            elif part is CompanyPart.PEERS:
                peers = read_peers_part(
                    sweep,
                    hooks=hooks,
                    company_id=company_id,
                    basis=basis,
                    source_id=metadata.source_id,
                    retrieved_at=retrieved_at,
                )
            else:
                quick_ratios = read_quick_ratios_part(
                    root,
                    sweep,
                    hooks=hooks,
                    source_id=metadata.source_id,
                    page_sha256=metadata.content_sha256,
                    retrieved_at=retrieved_at,
                )
        except PART_REFUSALS as error:
            sweep.refuse(part=part, name=part.value, error=error)

    outcomes = tuple(sweep.outcomes)
    return CompanyRun(
        artifact=CompanyArtifact(
            metadata=_metadata(
                page_fetch,
                company_id=company_id,
                parts=parts,
                outcomes=outcomes,
                sweep=sweep,
                warehouse_id=hooks.warehouse_id,
                planned=planned,
            ),
            outcomes=outcomes,
            shareholding=shareholding,
            investors=investors,
            segments=segments,
            related_party=related_party,
            corporate_actions=corporate_actions,
            peers=peers,
            quick_ratios=quick_ratios,
            failures=tuple(sweep.failures),
        ),
        page_body=page_fetch.raw_body,
        documents=tuple(sweep.documents),
    )


def _section_present(sweep: Sweep, part: CompanyPart, *, hooks: PageHooks) -> bool:
    """Refuse a part whose owning section the page did not render at all.

    ``NOT_OFFERED`` is a claim about the *company*: the page drew the section and
    put no control in it. It is only defensible while the section is there to
    look at. A page with no Shareholding Pattern section has changed shape, and
    filing that as "this company has no investor drill-downs" would record a
    layout change as an issuer property — and would do it silently, for as long
    as the layout stayed changed.
    """
    sections = OWNING_SECTIONS[part]
    if hooks.has(*sections):
        return True
    sweep.refuse(
        part=part,
        name=part.value,
        error=DocumentUnreadableError(
            MISSING_SECTION.format(sections=" or ".join(f"#{name}" for name in sections))
        ),
    )
    return False


def _over_budget(
    page_fetch: ScreenerPageFetch,
    hooks: PageHooks,
    *,
    company_id: int,
    parts: tuple[CompanyPart, ...],
    planned: int,
) -> CompanyRun:
    """Refuse the whole run before any sub-document is fetched.

    Returned rather than raised so the page's own bytes and the reason are still
    published: the next person needs to see what the page offered that made the
    plan too large.
    """
    sweep = Sweep(source=None, planned=planned)  # type: ignore[arg-type]
    sweep.refuse(
        part=parts[0],
        name="request_plan",
        error=DocumentUnreadableError(OVER_BUDGET.format(planned=planned, cap=MAX_SUB_REQUESTS)),
    )
    # Not complete, because nothing planned was attempted. ``acquisition`` is
    # already REFUSED (a failure was recorded); this is what keeps ``complete``
    # from claiming every planned request was made when none was, and it names
    # the plan against the cap for whoever decides whether the page grew or the
    # ceiling is wrong.
    sweep.incomplete_reason = OVER_BUDGET_INCOMPLETE.format(planned=planned, cap=MAX_SUB_REQUESTS)
    return CompanyRun(
        artifact=CompanyArtifact(
            metadata=_metadata(
                page_fetch,
                company_id=company_id,
                parts=parts,
                outcomes=(),
                sweep=sweep,
                warehouse_id=hooks.warehouse_id,
                planned=planned,
            ),
            failures=tuple(sweep.failures),
        ),
        page_body=page_fetch.raw_body,
    )


def _metadata(
    page_fetch: ScreenerPageFetch,
    *,
    company_id: int,
    parts: tuple[CompanyPart, ...],
    outcomes: tuple[PartOutcome, ...],
    sweep: Sweep,
    warehouse_id: int | None,
    planned: int,
) -> CompanyMetadata:
    """Build the evidence record along both axes, and never collapse them.

    ``complete`` and ``all_admitted`` are separate facts with separate repairs:
    a run that stopped early can be re-run later, while a run that refused a
    document will refuse it again. ``proven_documents`` is a third, orthogonal
    thing — how much of what came back is actually established — and no re-run
    changes it, because it is a property of what this source publishes.
    """
    metadata = page_fetch.metadata
    documents = tuple(document for outcome in outcomes for document in outcome.documents)
    by_binding: dict[str, tuple[str, ...]] = {}
    by_validation: dict[str, tuple[str, ...]] = {}
    for document in documents:
        by_binding[document.binding.value] = by_binding.get(document.binding.value, ()) + (
            document.document_id,
        )
        key = f"{document.validation.value}:{document.validation_status.value}"
        by_validation[key] = by_validation.get(key, ()) + (document.document_id,)
    proven = tuple(document.document_id for document in documents if document.proven)
    weak = tuple(document.document_id for document in documents if not document.proven)
    refused = tuple(dict.fromkeys(failure.part for failure in sweep.failures))
    return CompanyMetadata(
        source_id=metadata.source_id,
        symbol=metadata.symbol,
        slug=metadata.slug,
        basis=metadata.basis_requested,
        company_id=company_id,
        warehouse_id=warehouse_id,
        page_url=metadata.source_url,
        page_sha256=metadata.content_sha256,
        parts_requested=parts,
        parts_offered=tuple(outcome.part for outcome in outcomes if outcome.offered),
        parts_not_offered=tuple(outcome.part for outcome in outcomes if not outcome.offered),
        parts_refused=refused,
        proven_documents=proven,
        weak_documents=weak,
        documents_by_binding=by_binding,
        documents_by_validation=by_validation,
        planned_sub_requests=planned,
        request_count=sweep.request_count,
        acquisition=_acquisition(sweep),
        complete=sweep.incomplete_reason is None,
        all_admitted=not sweep.failures,
        incomplete_reason=sweep.incomplete_reason,
        fetched_at=metadata.fetched_at,
    )


def _acquisition(sweep: Sweep) -> Acquisition:
    """The one-word state of the run, derived rather than independently tracked.

    A refusal leads an early stop when both happened: stopping early is a budget
    problem a later re-run fixes, while a refused document is a correctness
    problem the re-run will reproduce, and the caller should see the one that
    will not go away. Both underlying facts stay separately readable.
    """
    if sweep.failures:
        return Acquisition.REFUSED
    if sweep.incomplete_reason is not None:
        return Acquisition.INCOMPLETE
    return Acquisition.COMPLETE


def all_parts() -> tuple[CompanyPart, ...]:
    """Every acquirable part, in declaration order."""
    return ALL_PARTS
