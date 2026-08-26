"""Frozen artifacts for the Screener subscriber company-page sub-documents.

The typed *result* of Slice 2, split from
:mod:`fundamentals.ingest.screener_company_models` (which owns the vocabulary:
enums, typed refusals, tolerances and URL builders) so neither file has to be
read whole to answer a question about the other. The dependency runs one way —
artifacts import vocabulary, never the reverse.

Every model here is frozen, and every number carries the lexeme it was read from
beside it: a display string is what the source actually published, and a
``Decimal`` is this contract's reading of it. Where the two disagree the lexeme
is the evidence.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.provenance import Provenance
from fundamentals.ingest.screener_company_models import (
    Acquisition,
    AssertionResult,
    Binding,
    BucketDisclosure,
    BucketOutcome,
    CompanyPart,
    Periodicity,
    SegmentOutcome,
    SumStrategy,
    Validation,
    ValidationStatus,
)
from fundamentals.ingest.screener_financials_models import (
    Cell,
    IdentityStrength,
    Period,
    QuarantinedRow,
    Unit,
)
from fundamentals.ingest.screener_session_models import Basis


class BucketRow(BaseModel):
    """One bucket row of a Shareholding Pattern table.

    ``bucket`` is the API key from the row's own drill-down button, which is
    what binds this row to the response that expands it. A row with no button
    (``No. of Shareholders``) carries ``None`` and is never expanded.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    bucket: str | None
    unit: Unit
    cells: tuple[Cell, ...] = ()


class ShareholdingTable(BaseModel):
    """One Shareholding Pattern table, read off the proven page."""

    model_config = ConfigDict(frozen=True)

    periodicity: Periodicity
    table_id: str
    unit_statement: str | None
    identity_strength: IdentityStrength = IdentityStrength.PAGE_ASSERTED
    binding: Binding = Binding.PAGE_ASSERTED
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.NOT_APPLICABLE
    periods: tuple[Period, ...] = ()
    rows: tuple[BucketRow, ...] = ()
    quarantined: tuple[QuarantinedRow, ...] = ()


class InvestorHolding(BaseModel):
    """One named holder inside one investor bucket.

    ``person_url`` is the relative path Screener attaches to the holder. It is
    retained as evidence of who the holder is and is never followed.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    holder: str
    person_url: str | None
    cells: tuple[Cell, ...] = ()
    unmatched_periods: tuple[str, ...] = ()


class PeriodComparison(BaseModel):
    """One period's disclosed total against the page figure it is held to."""

    model_config = ConfigDict(frozen=True)

    period_label: str
    disclosed_total: Decimal
    page_value: Decimal
    difference: Decimal
    tolerance: Decimal
    within_tolerance: bool


class InvestorBucket(BaseModel):
    """One investors drill-down response and what it was held to."""

    model_config = ConfigDict(frozen=True)

    bucket: str
    periodicity: Periodicity
    row_label: str
    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    disclosure: BucketDisclosure
    strategy: SumStrategy
    outcome: BucketOutcome
    binding: Binding = Binding.CONFIGURED_URL_ONLY
    validation: Validation
    validation_status: ValidationStatus
    note: str
    holders: tuple[InvestorHolding, ...] = ()
    comparisons: tuple[PeriodComparison, ...] = ()
    unmatched_periods: tuple[str, ...] = ()


class SegmentRow(BaseModel):
    """One segment's values on one line of a Product Segments table."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    cells: tuple[Cell, ...] = ()


class SegmentLine(BaseModel):
    """One ``tbody[data-segment-line]`` block of a Product Segments table.

    ``line`` is the machine key Screener stamps on the block; ``title`` is the
    heading it renders above it and is often different (the ``Profit`` and
    ``Profit Growth %`` lines both render "Profit before Tax & Int"). Both are
    kept: the key addresses the block, the title is what a reader sees.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    line: str
    title: str
    table_id: str
    rows: tuple[SegmentRow, ...] = ()
    quarantined: tuple[QuarantinedRow, ...] = ()


class SegmentTable(BaseModel):
    """One Product Segments fragment for one page section on one basis."""

    model_config = ConfigDict(frozen=True)

    section: str
    segment_type: str
    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    outcome: SegmentOutcome
    binding: Binding = Binding.CONFIGURED_URL_ONLY
    validation: Validation = Validation.LOWER_BOUND_NEWEST
    validation_status: ValidationStatus
    note: str
    periods: tuple[Period, ...] = ()
    lines: tuple[SegmentLine, ...] = ()
    comparisons: tuple[PeriodComparison, ...] = ()


class RelatedPartyLine(BaseModel):
    """One transaction line under one related party.

    Addressed by position, never by label: line labels repeat across parties and
    even within one party with case variants ("Inter-corporate deposit placed"
    beside "Inter-corporate Deposit placed"), so a label-keyed map would collapse
    two genuinely different rows into one.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    label: str
    cells: tuple[Cell, ...] = ()


class RelatedParty(BaseModel):
    """One counterparty block of the Related Party modal."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    name: str
    tag: str | None
    lines: tuple[RelatedPartyLine, ...] = ()
    quarantined: tuple[QuarantinedRow, ...] = ()


class RelatedPartyTable(BaseModel):
    """The Related Party modal fragment, retained with its own disclaimer.

    ``source_note`` is Screener's callout ("Experimental new feature …"),
    retained verbatim because it is the source's own statement about how far the
    numbers can be trusted, and dropping it would make the artifact look firmer
    than the source does.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    binding: Binding = Binding.CONFIGURED_URL_ONLY
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.NOT_APPLICABLE
    source_note: str | None = None
    periods: tuple[Period, ...] = ()
    parties: tuple[RelatedParty, ...] = ()


class CorporateAction(BaseModel):
    """One dated event on one Corporate actions tab.

    ``amount`` is populated only when the title is a bare rupee figure, which is
    how the dividend tabs render. Everything else keeps ``None`` beside the
    verbatim title rather than a number squeezed out of prose.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    event_date: date
    year_text: str
    day_text: str
    title: str
    detail: str
    amount: Decimal | None
    provenance: Provenance


class CorporateActionTab(BaseModel):
    """One tab of the Corporate actions modal, whatever the site calls it.

    ``tab`` is the suffix of the page's own ``corporate-actions-<tab>`` id and
    is not validated against a known set: the tabs a company renders vary
    (equityhistory, dividend, bonus, split, esops, prefissue), so an unknown one
    is retained rather than dropped.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    tab: str
    label: str
    table_id: str
    actions: tuple[CorporateAction, ...] = ()


class CorporateActionsTable(BaseModel):
    """The Corporate actions modal fragment."""

    model_config = ConfigDict(frozen=True)

    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    binding: Binding = Binding.CONFIGURED_URL_ONLY
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.NOT_APPLICABLE
    tabs: tuple[CorporateActionTab, ...] = ()


class PeerColumn(BaseModel):
    """One column of the peers table, addressed by its full field name.

    ``field`` is the header's ``data-tooltip`` ("Return on capital employed"),
    which is the name the screening query language uses; ``label`` is the
    abbreviation rendered in the header ("ROCE %").
    """

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    field: str
    label: str


class PeerRow(BaseModel):
    """One company in the peers table, including this company's own row."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    company_id: int | None
    name: str
    href: str | None
    is_self: bool
    identity_strength: IdentityStrength = IdentityStrength.CONFIGURED_URL_ONLY
    cells: tuple[Cell, ...] = ()


class PeersTable(BaseModel):
    """The peers fragment, whose own body proves whose page asked for it.

    ``binding`` is ``BODY_ASSERTED`` because the identity and basis checks ran
    against the response itself, and ``identity_assertion`` records that they
    held. ``peer_values_binding`` is separate and weaker on purpose: proving the
    fragment is this company's on this basis says nothing about whether the
    *other* rows' numbers are right, and those figures are what a consumer
    actually reads off the table. That is why this document is a weak one
    despite carrying the strongest body-level assertion in the slice.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength = IdentityStrength.PAGE_ASSERTED
    binding: Binding = Binding.BODY_ASSERTED
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.NOT_APPLICABLE
    identity_assertion: AssertionResult = AssertionResult.PASSED
    peer_values_binding: Binding = Binding.CONFIGURED_URL_ONLY
    self_row_position: int = Field(ge=0)
    columns: tuple[PeerColumn, ...] = ()
    rows: tuple[PeerRow, ...] = ()
    median_label: str | None = None
    quarantined: tuple[QuarantinedRow, ...] = ()


class QuickRatio(BaseModel):
    """One header ratio, with every number the site rendered for it.

    ``values`` is a tuple because "High / Low" renders two numbers inside one
    value span. Splitting it into two ratios would invent names the site does
    not publish; collapsing it to one number would drop half the reading.
    """

    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0)
    name: str
    values: tuple[Decimal | None, ...] = ()
    raw_text: str
    unit: Unit
    source: str
    provenances: tuple[Provenance, ...] = ()


class QuickRatioList(BaseModel):
    """One list of header ratios: the API's, or the page's own ``#top-ratios``.

    ``configured_by_account`` is true for the API list, which is literally the
    signed-in owner's Manage-quick_ratios selection. Its contents are therefore
    a fact about this account, not about the company, and it is recorded so a
    consumer never reads the list's membership as a property of the issuer.
    """

    model_config = ConfigDict(frozen=True)

    url: str | None
    document_id: str
    body_sha256: str
    identity_strength: IdentityStrength
    binding: Binding
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.NOT_APPLICABLE
    configured_by_account: bool
    table_id: str
    ratios: tuple[QuickRatio, ...] = ()


class DocumentEvidence(BaseModel):
    """What one acquired document established, on its own, along two axes.

    Per document rather than per part, because a part's documents do not all
    establish the same thing: the promoters bucket is held to equality while the
    threshold buckets beside it are only bounded. Recording one verdict for the
    whole part would either promote the weak ones or demote the strong one, and
    the promoted case is the dangerous one.

    ``page_table`` marks a document that was read straight off the proven page
    rather than fetched. Such a document has nothing to validate — it *is* the
    reference other documents are validated against — so it is the one case
    where ``NOT_APPLICABLE`` still counts as proven.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    binding: Binding
    validation: Validation
    validation_status: ValidationStatus
    identity_assertion: AssertionResult = AssertionResult.NOT_ATTEMPTED
    page_table: bool = False

    @property
    def proven(self) -> bool:
        """True when this document's own contents are actually established.

        Two ways in, and only two. A table read straight off the page Slice 0
        proved is established by that page — it is the reference everything else
        is checked against. And an **equality** that held establishes a fetched
        document even though its body names no company: 410 promoter holdings
        adding to the exact figure the proven page states cannot plausibly be
        another issuer's promoters, which is precisely the mistake that check
        exists to catch.

        A one-sided bound does not qualify, and the difference is not one of
        degree. "The disclosed subset is no larger than the whole" is true of
        any subset, including one from the wrong company; "the newest segment
        period does not undershoot the page" is a trap for a wrong basis rather
        than evidence of a right one. Both are worth running and neither
        establishes the document, so both stay weak.
        """
        if self.validation is Validation.EQUALITY:
            return self.validation_status is ValidationStatus.PASSED
        return (
            self.page_table
            and self.binding is Binding.PAGE_ASSERTED
            and self.validation_status is ValidationStatus.NOT_APPLICABLE
        )


class PartOutcome(BaseModel):
    """What one requested part produced.

    Carries no verdict of its own: a part is a bag of documents that were
    established to different degrees, and any single roll-up either flatters the
    weakest or buries the strongest. The per-document records are the answer.
    """

    model_config = ConfigDict(frozen=True)

    part: CompanyPart
    offered: bool
    documents: tuple[DocumentEvidence, ...] = ()
    note: str = ""

    @property
    def document_ids(self) -> tuple[str, ...]:
        """Every document this part acquired, in request order."""
        return tuple(document.document_id for document in self.documents)


class CompanyFailure(BaseModel):
    """A sub-document that was refused, with its bytes retained where there are any.

    Recorded beside the retained bytes rather than existing only in a traceback:
    the body that fails a check is the most useful evidence this adapter
    produces — it is what a wrong basis or a changed surface actually looks like.

    ``url``, ``document_id`` and ``body_sha256`` are optional because two kinds
    of failure have no body: a transport refusal, where the request was made and
    answered with a redirect or an error status, and a page-shape refusal, where
    the section that would have named the document is missing so no request was
    ever built.
    """

    model_config = ConfigDict(frozen=True)

    part: CompanyPart
    name: str
    url: str | None
    document_id: str | None
    body_sha256: str | None
    refusal: str
    detail: str
    validation: Validation = Validation.NONE
    validation_status: ValidationStatus = ValidationStatus.FAILED


class CompanyMetadata(BaseModel):
    """Provenance and evidence record for one company sub-document acquisition.

    There is deliberately no single ``verified`` flag. Three independent things
    can go right or wrong and a caller repairs each differently: ``complete``
    says every planned request was attempted (a budget fact, fixed by re-running
    later), ``all_admitted`` says nothing failed a check it could run (a
    correctness fact, which re-running reproduces), and ``proven_documents``
    versus ``weak_documents`` says how much of what came back is actually
    established (a property of the source, which no re-run changes).
    ``acquisition`` is the one-word summary, and it is derived from the first
    two rather than being a fourth opinion.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    symbol: str
    slug: str
    basis: Basis
    company_id: int
    warehouse_id: int | None
    page_url: str
    page_sha256: str
    parts_requested: tuple[CompanyPart, ...]
    parts_offered: tuple[CompanyPart, ...]
    parts_not_offered: tuple[CompanyPart, ...]
    parts_refused: tuple[CompanyPart, ...]
    proven_documents: tuple[str, ...]
    weak_documents: tuple[str, ...]
    documents_by_binding: dict[str, tuple[str, ...]]
    documents_by_validation: dict[str, tuple[str, ...]]
    planned_sub_requests: int
    request_count: int
    acquisition: Acquisition
    complete: bool
    all_admitted: bool
    incomplete_reason: str | None
    fetched_at: datetime


class CompanyArtifact(BaseModel):
    """Every sub-document read from one page on one basis.

    ``metadata.complete`` is false when the run stopped early (a rate limit
    mid-sweep) or a document was refused. What was already read stays and is
    still true; what is missing is named rather than implied.
    """

    model_config = ConfigDict(frozen=True)

    metadata: CompanyMetadata
    outcomes: tuple[PartOutcome, ...] = ()
    shareholding: tuple[ShareholdingTable, ...] = ()
    investors: tuple[InvestorBucket, ...] = ()
    segments: tuple[SegmentTable, ...] = ()
    related_party: RelatedPartyTable | None = None
    corporate_actions: CorporateActionsTable | None = None
    peers: PeersTable | None = None
    quick_ratios: tuple[QuickRatioList, ...] = ()
    failures: tuple[CompanyFailure, ...] = ()
