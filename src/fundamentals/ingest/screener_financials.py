"""Orchestration: one company page on one basis, read into typed sections.

This is the only module that decides the *order* of Slice 1's work, and the
order is what makes it safe:

1. Slice 0 fetches and proves the page (session, identity, basis). Nothing here
   re-derives any of that; a page that did not carry the requested basis never
   reaches this module.
2. The requested sections are parsed from the retained page bytes.
3. The schedule families are read from the page's own ``showSchedule`` buttons —
   never from a constant — and fetched through the *same* session instance, so
   the page and its schedules share one spacing and one 429 budget.
4. Each schedule is reconciled against the page row it expands before it is
   admitted to the artifact, and any schedule its own sub-rows advertise is
   fetched immediately afterwards and reconciled against that sub-row.

Step 3 is where the run can stop short: a company page, fifteen schedules and
the two nested ones they advertise is eighteen authenticated requests against a
source observed to rate-limit at ~40. A 429 that survives the bounded backoff
ends the sweep — at either depth, since they share one budget — and the artifact
records ``complete=False`` with the reason. Everything already read stays —
what is missing is named, never implied.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_financials_models import (
    DATA_TABLE_SECTIONS,
    AmbiguousStructureError,
    FinancialsArtifact,
    FinancialsMetadata,
    ScheduleBodyError,
    ScheduleFailure,
    ScheduleFamily,
    ScreenerFinancialsError,
    Section,
    SectionTable,
    TableRow,
    family_key,
    reconciliation_is_proven,
    schedule_path,
    schedule_url,
)
from fundamentals.ingest.screener_financials_nested import (
    SALES_SCHEDULE_PARENT,
    nested_call_defect,
    read_nested_schedule,
)
from fundamentals.ingest.screener_financials_schedules import read_schedule
from fundamentals.ingest.screener_financials_tables import (
    read_growth_section,
    read_section,
    schedule_parents,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    ScreenerPageFetch,
    ScreenerRateLimitedError,
)
from fundamentals.ingest.screener_session_page import parse_document

_LOGGER = structlog.get_logger(__name__)

ALL_SECTIONS: tuple[Section, ...] = (*DATA_TABLE_SECTIONS, Section.GROWTH)

_SCHEDULE_EVENT = "screener_schedule_read"
_NESTED_EVENT = "screener_nested_schedule_read"
_ABORTED_EVENT = "screener_schedule_sweep_aborted"
_REFUSED_EVENT = "screener_schedule_refused"
_RATE_LIMITED = (
    "rate-limited after {done} of {total} schedules; the sweep stopped and the "
    "sections already read are retained"
)
_REFUSED = (
    "{family} was refused ({refusal}); the sweep stopped with its response retained, "
    "because a family that fails this gate usually means every family of the run is "
    "wrong in the same way"
)
_AMBIGUOUS_PARENT = (
    "screener {section!r} section has {count} rows whose expander requests {parent!r}; "
    "a reconciliation would compare the schedule against whichever was read first"
)


class ScheduleDocument(BaseModel):
    """One retained schedule response, kept beside the artifact it fed.

    The bytes are retained for the same reason the page's are: an artifact whose
    source document is gone cannot be re-derived or audited, and this one's
    ``document_id`` is the whole of its identity.
    """

    model_config = ConfigDict(frozen=True)

    section: Section
    parent: str
    document_id: str
    url: str
    content_sha256: str
    raw_body: bytes
    expands: str | None = None


class ScheduleSweep(BaseModel):
    """What one pass over the page's schedule families produced.

    A record rather than a tuple because the sweep now reports five things: the
    nested families it requested are named separately from the level-2 ones the
    page advertised, since they exist only because a level-2 *body* said so.
    """

    model_config = ConfigDict(frozen=True)

    families: tuple[ScheduleFamily, ...] = ()
    documents: tuple[ScheduleDocument, ...] = ()
    failures: tuple[ScheduleFailure, ...] = ()
    nested_requested: tuple[str, ...] = ()
    incomplete_reason: str | None = None


class FinancialsRun(BaseModel):
    """Everything one acquisition produced: the artifact and its evidence."""

    model_config = ConfigDict(frozen=True)

    artifact: FinancialsArtifact
    page_body: bytes
    schedule_documents: tuple[ScheduleDocument, ...] = ()


def read_financials(
    page_fetch: ScreenerPageFetch,
    *,
    company_id: int,
    sections: tuple[Section, ...],
    source: ScreenerSessionSource,
) -> FinancialsRun:
    """Read the requested sections of one proven page and expand their schedules."""
    metadata = page_fetch.metadata
    root = parse_document(page_fetch.raw_body.decode("utf-8", errors="replace"))
    retrieved_at = metadata.fetched_at
    parsed = {
        section: _read_one_section(
            root,
            section,
            source_id=metadata.source_id,
            file_sha256=metadata.content_sha256,
            retrieved_at=retrieved_at,
        )
        for section in sections
    }

    wanted = tuple(family for family in schedule_parents(root) if family[0] in parsed)
    sweep = _sweep_schedules(
        wanted,
        parsed=parsed,
        company_id=company_id,
        basis=metadata.basis_requested,
        source=source,
        source_id=metadata.source_id,
        retrieved_at=retrieved_at,
    )
    families = sweep.families
    incomplete_reason = sweep.incomplete_reason
    # A nested family is part of the run's claim, so it is counted here rather
    # than only hanging off its parent: an artifact whose level-2 families all
    # reconcile while a level-3 breakdown is an unrecognised shape is not a
    # clean acquisition.
    acquired = _with_nested(families)
    # Every status other than RECONCILED and NOT_APPLICABLE means the gate did
    # not run. NOT_COMPARABLE used to be left out here while the CLI still
    # exited non-zero for it, so the artifact recorded ``verified: true`` for a
    # run its own command called a failure. One shared predicate now decides it.
    unverified = tuple(
        family_key(family.section, family.parent, family.expands)
        for family in acquired
        if not reconciliation_is_proven(family.reconciliation)
    )
    attached = tuple(
        table.model_copy(
            update={"schedules": tuple(family for family in families if family.section is section)}
        )
        for section, table in parsed.items()
    )
    return FinancialsRun(
        artifact=FinancialsArtifact(
            metadata=FinancialsMetadata(
                source_id=metadata.source_id,
                symbol=metadata.symbol,
                slug=metadata.slug,
                basis=metadata.basis_requested,
                company_id=company_id,
                page_url=metadata.source_url,
                page_sha256=metadata.content_sha256,
                sections_requested=sections,
                schedule_families_requested=(
                    *(family_key(section, parent) for section, parent in wanted),
                    *sweep.nested_requested,
                ),
                schedule_families_fetched=tuple(
                    family_key(family.section, family.parent, family.expands) for family in acquired
                ),
                schedule_families_refused=tuple(
                    family_key(failure.section, failure.parent, failure.expands)
                    for failure in sweep.failures
                ),
                schedule_families_unverified=unverified,
                complete=incomplete_reason is None,
                verified=incomplete_reason is None and not sweep.failures and not unverified,
                incomplete_reason=incomplete_reason,
                fetched_at=retrieved_at,
            ),
            sections=attached,
            failures=sweep.failures,
        ),
        page_body=page_fetch.raw_body,
        schedule_documents=sweep.documents,
    )


def _read_one_section(
    root: Any,
    section: Section,
    *,
    source_id: str,
    file_sha256: str,
    retrieved_at: Any,
) -> SectionTable:
    """Read one requested section, routing the synthetic growth section."""
    if section is Section.GROWTH:
        return read_growth_section(
            root, source_id=source_id, file_sha256=file_sha256, retrieved_at=retrieved_at
        )
    return read_section(
        root,
        section,
        source_id=source_id,
        file_sha256=file_sha256,
        retrieved_at=retrieved_at,
    )


def _sweep_schedules(
    wanted: tuple[tuple[Section, str], ...],
    *,
    parsed: dict[Section, SectionTable],
    company_id: int,
    basis: Basis,
    source: ScreenerSessionSource,
    source_id: str,
    retrieved_at: Any,
) -> ScheduleSweep:
    """Fetch and reconcile every requested family, stopping short on trouble.

    A refusal is recorded, not propagated. ``read_schedule`` still raises — the
    typed error is the contract — but here it is caught so the response that
    triggered it survives to disk. That body is the most useful artifact this
    adapter produces: it is what a wrong basis, or a row that changed meaning,
    actually looks like, and letting the exception escape would discard it.

    The sweep then stops. A family that fails the gate almost always means the
    whole run is wrong the same way, so spending the remaining rate-limited
    requests to collect more of it helps nobody.

    A *level-3* refusal is different and does not stop it: the level-2 parent
    already reconciled against the page on this basis, so a disagreement inside
    its breakdown is local to that breakdown. A rate limit still stops the
    sweep, because level-3 fetches spend the same 429 budget.
    """
    families: list[ScheduleFamily] = []
    documents: list[ScheduleDocument] = []
    failures: list[ScheduleFailure] = []
    nested_requested: list[str] = []
    for done, (section, parent) in enumerate(wanted):
        table = parsed[section]
        url = schedule_url(company_id, parent=parent, section=section, basis=basis)
        document_id = schedule_path(company_id, parent=parent, section=section, basis=basis)
        try:
            fetched = source.fetch_schedule(url=url)
        except ScreenerRateLimitedError:
            _LOGGER.warning(_ABORTED_EVENT, fetched=done, requested=len(wanted), basis=basis.value)
            return ScheduleSweep(
                families=tuple(families),
                documents=tuple(documents),
                failures=tuple(failures),
                nested_requested=tuple(nested_requested),
                incomplete_reason=_RATE_LIMITED.format(done=done, total=len(wanted)),
            )
        # Retained before it is interpreted: a body that fails the reconciliation
        # gate is exactly the body someone will need to look at.
        documents.append(
            ScheduleDocument(
                section=section,
                parent=parent,
                document_id=document_id,
                url=url,
                content_sha256=fetched.content_sha256,
                raw_body=fetched.raw_body,
            )
        )
        try:
            family = read_schedule(
                fetched.raw_body,
                section=section,
                parent=parent,
                basis=basis,
                url=url,
                document_id=document_id,
                body_sha256=fetched.content_sha256,
                periods=table.periods,
                page_row=_page_row(table, parent),
                source_id=source_id,
                retrieved_at=fetched.fetched_at,
            )
        except ScreenerFinancialsError as error:
            failures.append(
                ScheduleFailure(
                    section=section,
                    parent=parent,
                    basis=basis,
                    url=url,
                    document_id=document_id,
                    body_sha256=fetched.content_sha256,
                    refusal=type(error).__name__,
                    detail=str(error),
                )
            )
            _LOGGER.warning(
                _REFUSED_EVENT,
                section=section.value,
                parent=parent,
                basis=basis.value,
                refusal=type(error).__name__,
            )
            return ScheduleSweep(
                families=tuple(families),
                documents=tuple(documents),
                failures=tuple(failures),
                nested_requested=tuple(nested_requested),
                incomplete_reason=_REFUSED.format(
                    family=family_key(section, parent), refusal=type(error).__name__
                ),
            )
        _LOGGER.info(
            _SCHEDULE_EVENT,
            section=section.value,
            parent=parent,
            basis=basis.value,
            strategy=family.strategy.value,
            reconciliation=family.reconciliation.value,
            sub_rows=len(family.sub_rows),
        )
        families.append(family)
        # Immediately, inside this loop: a nested family is fetched as soon as
        # the family that advertised it is admitted, so retention order on disk
        # follows fetch order and a rate limit lands where it really landed.
        nested, rate_limited = _sweep_nested(
            family,
            table=table,
            company_id=company_id,
            basis=basis,
            source=source,
            source_id=source_id,
            documents=documents,
            failures=failures,
            requested=nested_requested,
        )
        if nested:
            families[-1] = family.model_copy(update={"nested": nested})
        if rate_limited:
            _LOGGER.warning(
                _ABORTED_EVENT,
                fetched=done + 1,
                requested=len(wanted),
                basis=basis.value,
                expands=parent,
            )
            return ScheduleSweep(
                families=tuple(families),
                documents=tuple(documents),
                failures=tuple(failures),
                nested_requested=tuple(nested_requested),
                incomplete_reason=_RATE_LIMITED.format(done=done + 1, total=len(wanted)),
            )
    return ScheduleSweep(
        families=tuple(families),
        documents=tuple(documents),
        failures=tuple(failures),
        nested_requested=tuple(nested_requested),
    )


def _sweep_nested(
    family: ScheduleFamily,
    *,
    table: SectionTable,
    company_id: int,
    basis: Basis,
    source: ScreenerSessionSource,
    source_id: str,
    documents: list[ScheduleDocument],
    failures: list[ScheduleFailure],
    requested: list[str],
) -> tuple[tuple[ScheduleFamily, ...], bool]:
    """Expand every sub-row of one admitted family that advertises its own schedule.

    Returns the nested families and whether a rate limit ended the sweep.
    Discovery is the level-2 body's own ``isExpandable`` call and nothing else,
    so a family this contract expects but the body does not advertise is never
    requested — and a call that does not describe its own sub-row is recorded as
    drift without spending a request on it.
    """
    section = family.section
    nested: list[ScheduleFamily] = []
    for sub_row in family.sub_rows:
        call = sub_row.nested_schedule_call
        if call is None:
            continue
        label = sub_row.label
        url = schedule_url(company_id, parent=label, section=section, basis=basis)
        document_id = schedule_path(company_id, parent=label, section=section, basis=basis)
        requested.append(family_key(section, label, family.parent))
        defect = nested_call_defect(call, label=label, section=section)
        if defect is not None:
            failures.append(
                ScheduleFailure(
                    section=section,
                    parent=label,
                    basis=basis,
                    url=url,
                    document_id=document_id,
                    body_sha256=None,
                    expands=family.parent,
                    refusal=ScheduleBodyError.__name__,
                    detail=defect,
                )
            )
            _LOGGER.warning(
                _REFUSED_EVENT,
                section=section.value,
                parent=label,
                expands=family.parent,
                basis=basis.value,
                refusal=ScheduleBodyError.__name__,
            )
            continue
        try:
            fetched = source.fetch_schedule(url=url)
        except ScreenerRateLimitedError:
            return tuple(nested), True
        documents.append(
            ScheduleDocument(
                section=section,
                parent=label,
                document_id=document_id,
                url=url,
                content_sha256=fetched.content_sha256,
                raw_body=fetched.raw_body,
                expands=family.parent,
            )
        )
        try:
            child = read_nested_schedule(
                fetched.raw_body,
                section=section,
                parent=label,
                expands=family.parent,
                basis=basis,
                url=url,
                document_id=document_id,
                body_sha256=fetched.content_sha256,
                periods=family.periods,
                reference_row=sub_row,
                sales_row=_page_row(table, SALES_SCHEDULE_PARENT),
                source_id=source_id,
                retrieved_at=fetched.fetched_at,
            )
        except ScreenerFinancialsError as error:
            failures.append(
                ScheduleFailure(
                    section=section,
                    parent=label,
                    basis=basis,
                    url=url,
                    document_id=document_id,
                    body_sha256=fetched.content_sha256,
                    expands=family.parent,
                    refusal=type(error).__name__,
                    detail=str(error),
                )
            )
            _LOGGER.warning(
                _REFUSED_EVENT,
                section=section.value,
                parent=label,
                expands=family.parent,
                basis=basis.value,
                refusal=type(error).__name__,
            )
            continue
        _LOGGER.info(
            _NESTED_EVENT,
            section=section.value,
            parent=label,
            expands=family.parent,
            basis=basis.value,
            strategy=child.strategy.value,
            reconciliation=child.reconciliation.value,
            sub_rows=len(child.sub_rows),
        )
        nested.append(child)
    return tuple(nested), False


def _with_nested(families: tuple[ScheduleFamily, ...]) -> tuple[ScheduleFamily, ...]:
    """Every family of one run, each nested family beside the parent it expands."""
    flattened: list[ScheduleFamily] = []
    for family in families:
        flattened.append(family)
        flattened.extend(family.nested)
    return tuple(flattened)


def _page_row(table: SectionTable, parent: str) -> TableRow | None:
    """The parsed row this family expands, matched by the button's own parent value.

    Exactly one row may claim a family. Taking the first of several would pick
    the reconciliation's reference by document order, which is the one thing the
    gate must not leave to chance; ``None`` (no row claims it) stays legal and
    is handled as "nothing to compare against".
    """
    matched = [row for row in table.rows if row.schedule_parent == parent]
    if len(matched) > 1:
        raise AmbiguousStructureError(
            _AMBIGUOUS_PARENT.format(section=table.section.value, count=len(matched), parent=parent)
        )
    return matched[0] if matched else None
