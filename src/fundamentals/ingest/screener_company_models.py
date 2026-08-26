"""Typed vocabulary for the Screener subscriber company-page sub-documents.

Slice 2 of the Screener build. Slice 0 fetches and proves the page; Slice 1
reads its five financial sections and the schedules that expand their rows.
This slice reads everything else the page offers: the Shareholding Pattern
tables and their per-holder drill-downs, Product Segments, the Related Party
and Corporate actions modals, the Peers table, and the quick-ratio lists.

This module owns the vocabulary — enums, typed refusals, tolerances and the URL
builders. The frozen result models live beside it in
:mod:`fundamentals.ingest.screener_company_artifacts`.

Three facts about this surface are load-bearing enough to state here.

**The segments API selects basis by the VALUE ``consolidated=true``, not by the
presence of the key.** Verified 2026-08-26 against TITAN: ``?consolidated=``
(blank) and omitting the parameter entirely return byte-identical *standalone*
bodies, while ``?consolidated=true`` returns the consolidated one. This is the
exact opposite of the schedules API, where the key's mere presence selects
consolidated and its value is read by nobody (see
:func:`~fundamentals.ingest.screener_financials_models.schedule_path`). The two
rules live one function apart on purpose: :func:`segments_path` emits the value,
``schedule_path`` emits the key, and neither may be copied onto the other.

**Most of these documents cannot be proven at all.** A schedules body at least
expands a row the page also shows, so it can be reconciled. A related-party
fragment carries no nav, no identity element, no basis marker and no company
name; a corporate-actions fragment the same; a quick-ratios list is whatever the
*account owner* configured under Manage quick_ratios. For those the request URL
is the entire binding, which is what :attr:`Binding.CONFIGURED_URL_ONLY` records.
Calling them "verified" because they parsed would be a lie about what is known.

**Two of them can be partly proven, and only partly.** Promoter holdings are
fully disclosed and sum to the page's bucket row, so that one document is
:attr:`Validation.EQUALITY`; every other investor bucket lists only holders
above 1 %, so its sum is a lower bound on a row the page states — checkable as an
:attr:`Validation.UPPER_BOUND` violation and no more. Segment Sales sums behave
the same way in the other direction. Such a document is named in the artifact's
``weak_documents`` and printed by the CLI, but a passing one-sided check does not
fail the run: its proof is structurally impossible, which is a documented
property of the source rather than a gate somebody skipped.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_session_models import (
    SCREENER_ORIGIN,
    Basis,
    ScreenerSessionError,
)

INVESTORS_PATH_TEMPLATE = "/api/3/{company_id}/investors/{bucket}/{periodicity}/"
SEGMENTS_PATH_TEMPLATE = "/api/segments/{company_id}/{section}/{segment_type}/"
PEERS_PATH_TEMPLATE = "/api/company/{warehouse_id}/peers/"
QUICK_RATIOS_PATH_TEMPLATE = "/api/company/{warehouse_id}/quick_ratios/"

# The query key AND value that select consolidated segment figures. Both matter
# here, unlike the schedules API — see the module docstring.
CONSOLIDATED_QUERY_KEY = "consolidated"
CONSOLIDATED_QUERY_VALUE = "true"

# Reserved key inside one investor holder's map: it carries the holder's person
# page, not a period. Retained (never followed), skipped before period matching.
SET_ATTRIBUTES_KEY = "setAttributes"
PERSON_URL_ATTRIBUTE = "data-person-url"
RESERVED_HOLDER_KEYS = frozenset({SET_ATTRIBUTES_KEY})

# Percentages are published to two decimals by both the page row and each
# holder, and each is rounded independently, so ``n`` addends plus one total
# carry a worst-case rounding error of ``(n + 1) / 200``.
PERCENT_HALF_UNIT = Decimal("0.005")
# An absolute ceiling on the percentage band, whatever the holder count. TITAN
# publishes 410 promoters, so the per-holder band alone is 2.055 percentage
# points — wide enough to admit a body missing a 1.5 % shareholder, which is the
# exact failure the sum exists to catch. Observed diffs across TITAN, NETWEB and
# HFCL are 0.00, 0.02 and 0.01, so this keeps every real body and refuses that.
MAX_PERCENT_TOLERANCE = Decimal("0.10")
# Segment amounts are whole crores on both sides, exactly as in Slice 1.
CRORE_HALF_UNIT = Decimal("0.5")

# The one investor bucket Screener discloses in full. Every other bucket lists
# only holders at or above 1 %, so its holders are a subset of the bucket and
# their sum can only ever bound the page row from below.
FULL_DISCLOSURE_BUCKETS = frozenset({"promoters"})

# The segment line whose rows are held to the page. Every other line (Profit,
# Capital Employed, the growth and margin percentages) is analytical: it
# restates or ratios the same figures, so summing it proves nothing.
SEGMENT_SALES_LINE = "Sales"
# The page row a segments table's Sales line is compared against.
PAGE_SALES_ROW = "Sales"

# Corporate-action dates are published as a year plus an abbreviated
# "Mon DD". The map is closed on purpose: an unrecognised month is a change in
# how the site writes dates, and guessing would publish a confident wrong date.
MONTH_ABBREVIATIONS: dict[str, int] = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

# The hard ceiling on sub-requests one run may plan. A full TITAN run is exactly
# eighteen (twelve investor buckets, two segments tables, four fragments) against
# a source observed to rate-limit at ~40 authenticated GETs. The plan is checked
# against this BEFORE anything is fetched: a page that suddenly offered fifty
# drill-downs would otherwise be discovered one 429 at a time, with most of the
# budget already spent.
MAX_SUB_REQUESTS = 18

# The path prefix each part's document must live under. A ``data-url`` is
# page-controlled input that becomes an authenticated request carrying the
# owner's session cookie, so it is checked against the part that asked for it
# rather than merely against the origin.
PART_PATH_PREFIXES: dict[str, str] = {
    "investors": "/api/3/",
    "segments": "/api/segments/",
    "related-party": "/results/rpt/",
    "corporate-actions": "/company/actions/",
    "peers": "/api/company/",
    "quick-ratios": "/api/company/",
}

# The only query this slice will send, keyed by the one part that may carry it.
# Held per part rather than as one shared set: ``consolidated=true`` means
# something to the segments endpoint and nothing to any other, so a shared
# allowance would let a page append a query to a modal path that has no basis
# parameter to interpret it.
SEGMENTS_PART = "segments"
ALLOWED_QUERIES: dict[str, frozenset[str]] = {
    SEGMENTS_PART: frozenset({"", f"{CONSOLIDATED_QUERY_KEY}={CONSOLIDATED_QUERY_VALUE}"}),
}
NO_QUERY = frozenset({""})

# Characters a page-supplied path segment (a bucket key, a section id, a segment
# type) may contain. Anything else could open a new path segment or a query.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")

RUPEE_SIGN = "₹"
CRORE_SUFFIX = "Cr."
PERCENT_SUFFIX = "%"
VALUE_SEPARATOR = "/"


class CompanyPart(StrEnum):
    """One acquirable block of the company page beyond its financial sections.

    Each part names both a CLI ``--part`` value and a family of sub-documents.
    ``INVESTORS`` covers the two Shareholding Pattern tables on the page *and*
    the per-bucket holder drill-downs, because neither is meaningful alone: the
    drill-downs carry no company, no basis and no total, and are checkable only
    against the page row they expand.
    """

    INVESTORS = "investors"
    SEGMENTS = "segments"
    RELATED_PARTY = "related-party"
    CORPORATE_ACTIONS = "corporate-actions"
    PEERS = "peers"
    QUICK_RATIOS = "quick-ratios"


ALL_PARTS: tuple[CompanyPart, ...] = tuple(CompanyPart)


class Binding(StrEnum):
    """How one document is tied to the company it is filed under.

    This answers "how do we know this is theirs", and nothing else. It is
    deliberately separate from :class:`Validation`, which answers "did its
    numbers check out": the two are independent, and a single flag combining
    them let a promoters body whose sum held read exactly like a related-party
    modal that nothing could check.

    * ``PAGE_ASSERTED`` — read out of the company page Slice 0 already proved
      (session, identity, basis).
    * ``BODY_ASSERTED`` — the response's own body names this company and states
      its basis. The peers fragment is the only one that does.
    * ``CONFIGURED_URL_ONLY`` — the request URL is the entire binding. The body
      carries no company, no basis and no identity of any kind.
    """

    PAGE_ASSERTED = "page_asserted"
    BODY_ASSERTED = "body_asserted"
    CONFIGURED_URL_ONLY = "configured_url_only"


class Validation(StrEnum):
    """Which arithmetic relation this document's own rows were held to.

    Named by what the relation *licenses*, not by whether it ran:

    * ``EQUALITY`` — the rows must sum to a figure the proven page states
      (promoter holdings).
    * ``UPPER_BOUND`` — the rows are a disclosed subset and may not exceed the
      page figure they are drawn from (every other investor bucket).
    * ``LOWER_BOUND_NEWEST`` — the newest period's rows may not fall below the
      page figure. A negative trap for a wrong basis, never proof of a right
      one (segments).
    * ``NONE`` — the source publishes nothing this document could be checked
      against.
    """

    EQUALITY = "equality"
    UPPER_BOUND = "upper_bound"
    LOWER_BOUND_NEWEST = "lower_bound_newest"
    NONE = "none"


class ValidationStatus(StrEnum):
    """Whether the relation in :class:`Validation` held.

    There is deliberately no "did not run" member. A check that is applicable
    either passes or refuses the document, so a third value could only ever mean
    "this one was skipped" — which reads as neither success nor failure and is
    exactly what a reader skims past. ``NOT_APPLICABLE`` is the separate, benign
    case: the source publishes nothing this document could be checked against,
    so there was never a check to skip.
    """

    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class AssertionResult(StrEnum):
    """Whether a body-level identity assertion was made, and held.

    Recorded beside the binding rather than folded into it, because the peers
    fragment proves *whose list it is* while saying nothing about the peers'
    figures — which is what a consumer actually reads off it.
    """

    PASSED = "passed"
    NOT_ATTEMPTED = "not_attempted"


class Acquisition(StrEnum):
    """What happened to the run as a whole.

    ``REFUSED`` leads ``INCOMPLETE`` when both apply: a failed check is a
    correctness signal that a re-run will reproduce, while stopping early is a
    budget signal that a later re-run fixes, and the caller should see the one
    that will not go away. The two underlying facts stay separately readable as
    ``complete`` and ``all_admitted``.
    """

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    REFUSED = "refused"


class Periodicity(StrEnum):
    """Which Shareholding Pattern table a drill-down belongs to.

    Read from the page's own ``showShareholders`` call rather than assumed: the
    two tables carry different period sets (12 quarters versus a run of March
    year-ends plus the newest quarter) and the API answers for both.
    """

    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class BucketDisclosure(StrEnum):
    """How completely one investor bucket's holders are published.

    ``FULL`` is claimed only for the buckets in
    :data:`FULL_DISCLOSURE_BUCKETS`; everything else is ``THRESHOLD``, meaning
    the response lists only holders large enough to be named individually.
    """

    FULL = "full"
    THRESHOLD = "threshold"


class SumStrategy(StrEnum):
    """What relation between a document's rows and a page row is checkable.

    ``FLAT_SUM`` asserts equality within rounding; ``UPPER_BOUND`` asserts only
    that the disclosed subset does not exceed the whole it is drawn from. They
    are separate members rather than one flag because they license different
    claims: only ``FLAT_SUM`` carries :attr:`Validation.EQUALITY`.
    """

    FLAT_SUM = "flat_sum"
    UPPER_BOUND = "upper_bound"


class BucketOutcome(StrEnum):
    """Which relation one investor bucket was held to, given that it held.

    Only two members, because only two states are reachable: a bucket that
    violates its relation, carries periods the page does not, or has no page row
    to be held to is refused rather than recorded. Members for those were
    deleted once nothing could emit them — a value nothing produces is an
    invitation to start producing it.
    """

    SUM_MATCHED = "sum_matched"
    WITHIN_BOUND = "within_bound"


class SegmentOutcome(StrEnum):
    """Result of holding a segments table's Sales line to the page Sales row.

    Only ``RECONCILED`` is a proof. The other two are honest descriptions of a
    gap Screener's own presentation creates and does not explain:

    * ``EXCEEDS_PAGE`` — segment revenue above reported revenue, which is what
      an omitted inter-segment elimination looks like (TITAN, every period);
    * ``BELOW_PAGE`` — segment revenue below reported revenue in an older
      period, which is what an unreported segment or an elimination the page
      does not deduct looks like (HFCL Mar 2016, ETERNAL Mar/Jun 2024);
    * ``MIXED_VARIANCE`` — both, which TITAN's and HFCL's yearly tables both do.
      It is its own member because reporting only the overshoot would hide the
      periods that fell short, and those are the interesting ones.

    A *newest* period below the page row is refused instead of classified: that
    is the shape a standalone body served against a consolidated page takes, and
    it is below on every period including the newest (TITAN, −3,114 crore on the
    newest quarter) where the honest cases above are historical only.
    """

    RECONCILED = "reconciled"
    EXCEEDS_PAGE = "exceeds_page"
    BELOW_PAGE = "below_page"
    MIXED_VARIANCE = "mixed_variance"
    NOT_COMPARABLE = "not_comparable"


class ScreenerCompanyError(ScreenerSessionError):
    """Base for every typed refusal raised while reading a company sub-document."""


class DiscoveryAmbiguousError(ScreenerCompanyError):
    """The page offers one part through two different targets.

    Refused rather than resolved by document order: two ``Related Party`` links
    with different ``data-url`` values, or two ``showSegment`` calls naming
    different types for one section, make "the document for this part" depend on
    which element is read first.
    """


class DocumentUnreadableError(ScreenerCompanyError):
    """A fetched sub-document is not the shape this contract can read."""


class EmptyShellError(ScreenerCompanyError):
    """A document the page offered came back as a header-only shell.

    A segments body with a periodless ``<thead>``, or a related-party table with
    an empty ``<tbody>``, is not "this company has no segments" — the page's own
    button is positive proof that it does. It is the shape a wrong id or a wrong
    basis parameter produces, so it is refused rather than recorded as empty.
    """


class PeriodAlignmentError(ScreenerCompanyError):
    """A fragment's period columns are not a window of the page's own.

    The page's header is the only thing binding a fragment's columns to real
    periods. Columns that are not a contiguous run of the page's labels mean the
    fragment describes periods the page does not, so anchoring its values to the
    page's columns would attach numbers to the wrong dates.
    """


class HoldingReconciliationError(ScreenerCompanyError):
    """An investor bucket's holders contradict the page row they expand.

    The investors API names no company and no basis, so the bucket row on the
    proven page is the only thing that can catch a response fetched for the
    wrong company or the wrong bucket. Promoter holdings must sum to it; every
    other bucket must not exceed it.
    """


class SegmentReconciliationError(ScreenerCompanyError):
    """A segments table's newest Sales period falls below the page Sales row.

    Segment revenue below reported revenue in the newest period is the signature
    of a standalone body answering a consolidated request: the segments API
    selects basis by the *value* ``consolidated=true``, so a caller who sends
    the key with any other value silently gets standalone figures that parse and
    align perfectly.
    """


class PeerIdentityError(ScreenerCompanyError):
    """The peers fragment does not name this company exactly once, on this basis.

    The peers table is the one fragment that can be checked against its own
    body: it must carry exactly one row whose ``data-row-company-id`` is this
    company, and that row's link must end in ``/consolidated/`` on a
    consolidated run and must not on a standalone one. Zero rows, two rows, or
    the wrong basis all mean the response is not this company's on this basis.
    """


class CorporateActionDateError(ScreenerCompanyError):
    """A corporate action carries a date this contract will not guess at."""


def assert_safe_segment(value: str, *, what: str) -> str:
    """Refuse a page-supplied path segment that could be more than one segment.

    Bucket keys, section ids and segment types are read verbatim from the page's
    own JavaScript calls and then interpolated into a URL that carries the
    owner's session cookie. A value containing a slash, a dot-dot or a question
    mark would silently become a different request.
    """
    if not _SAFE_SEGMENT.match(value):
        raise DiscoveryAmbiguousError(
            f"screener page supplied {what} {value!r}, which is not a plain path segment; "
            "refusing to build a request from it"
        )
    return value


def assert_document_path(path: str, *, part: str) -> str:
    """Refuse a page-supplied document path that is not this part's own shape.

    Four things are checked, and each corresponds to a way the page could steer
    an authenticated request somewhere this slice never meant to send one: it
    must be a site-relative path (not an absolute URL and not a protocol-relative
    ``//host`` one), it must carry no ``..`` segment, it must sit under the
    prefix its part is defined by, and it must carry no query at all — except on
    ``segments``, the one part whose endpoint has a basis parameter, and only the
    exact parameter this module itself emits.
    """
    prefix = PART_PATH_PREFIXES[part]
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or not path.startswith("/") or path.startswith("//"):
        raise DiscoveryAmbiguousError(
            f"screener {part} target {path!r} is not a site-relative path; the session "
            "cookie is only ever sent to a path this adapter built"
        )
    if ".." in parts.path.split("/"):
        raise DiscoveryAmbiguousError(
            f"screener {part} target {path!r} traverses out of its own prefix"
        )
    if not parts.path.startswith(prefix):
        raise DiscoveryAmbiguousError(
            f"screener {part} target {path!r} is not under {prefix!r}; the page offered a "
            "document that is not the one this part is defined by"
        )
    if parts.query not in ALLOWED_QUERIES.get(part, NO_QUERY):
        raise DiscoveryAmbiguousError(
            f"screener {part} target {path!r} carries the query {parts.query!r}; this slice "
            "sends no query at all except the basis parameter it builds itself for segments"
        )
    if parts.fragment:
        raise DiscoveryAmbiguousError(f"screener {part} target {path!r} carries a fragment")
    return path


def investors_path(company_id: int, *, bucket: str, periodicity: Periodicity) -> str:
    """Build the investors request path for one bucket of one shareholding table.

    ``bucket`` is the first argument of the page's own ``showShareholders``
    call, verbatim: the API's bucket names (``foreign_institutions``) are not
    the labels the page renders (``FIIs``), so reconstructing one from the other
    would invent an endpoint.
    """
    return assert_document_path(
        INVESTORS_PATH_TEMPLATE.format(
            company_id=company_id,
            bucket=assert_safe_segment(bucket, what="an investor bucket"),
            periodicity=periodicity.value,
        ),
        part="investors",
    )


def investors_url(company_id: int, *, bucket: str, periodicity: Periodicity) -> str:
    """The absolute investors URL on the pinned Screener origin."""
    return SCREENER_ORIGIN + investors_path(company_id, bucket=bucket, periodicity=periodicity)


def segments_path(company_id: int, *, section: str, segment_type: str, basis: Basis) -> str:
    """Build the segments request path and query for one section on one basis.

    Basis is expressed by the query **value**: ``consolidated=true`` for
    consolidated, no parameter at all for standalone. Sending the key with any
    other value — including the empty string — returns standalone figures, so
    this is the only place in the repo allowed to decide it.

    ``segment_type`` is recorded verbatim from the page's ``showSegment`` call.
    Only ``'1'`` has ever been offered; ``/2/`` exists server-side as a
    geographic split, and this function will not synthesise a request for it.
    """
    path = SEGMENTS_PATH_TEMPLATE.format(
        company_id=company_id,
        section=assert_safe_segment(section, what="a segments section"),
        segment_type=assert_safe_segment(segment_type, what="a segment type"),
    )
    if basis is Basis.CONSOLIDATED:
        path = f"{path}?{urlencode([(CONSOLIDATED_QUERY_KEY, CONSOLIDATED_QUERY_VALUE)])}"
    return assert_document_path(path, part="segments")


def segments_url(company_id: int, *, section: str, segment_type: str, basis: Basis) -> str:
    """The absolute segments URL on the pinned Screener origin."""
    return SCREENER_ORIGIN + segments_path(
        company_id, section=section, segment_type=segment_type, basis=basis
    )


def peers_path(warehouse_id: int) -> str:
    """Build the peers request path, which is scoped by the *warehouse* id.

    Screener carries two numeric namespaces on one page and this endpoint takes
    the basis-scoped one, so a company id here would silently answer for another
    company (surface-map.md §3).
    """
    return assert_document_path(PEERS_PATH_TEMPLATE.format(warehouse_id=warehouse_id), part="peers")


def peers_url(warehouse_id: int) -> str:
    """The absolute peers URL on the pinned Screener origin."""
    return SCREENER_ORIGIN + peers_path(warehouse_id)


def quick_ratios_path(warehouse_id: int) -> str:
    """Build the quick-ratios request path, also scoped by the warehouse id."""
    return assert_document_path(
        QUICK_RATIOS_PATH_TEMPLATE.format(warehouse_id=warehouse_id), part="quick-ratios"
    )


def quick_ratios_url(warehouse_id: int) -> str:
    """The absolute quick-ratios URL on the pinned Screener origin."""
    return SCREENER_ORIGIN + quick_ratios_path(warehouse_id)


def absolute_url(path: str) -> str:
    """Promote one validated page-supplied ``data-url`` path to the pinned origin.

    The path is used verbatim once :func:`assert_document_path` has accepted it.
    The page states where the modal lives, including whether it carries the
    ``consolidated/`` suffix, and reconstructing it would mean deciding a basis
    rule the page has already decided.
    """
    return SCREENER_ORIGIN + path


def percent_tolerance(addend_count: int) -> Decimal:
    """The rounding band a correct sum of two-decimal percentages may fall in.

    ``addend_count`` is the number of holdings disclosed **in that period**, not
    the holder count of the whole response: only the values actually summed for
    a period were rounded into it.

    Capped absolutely: the per-addend band is the right shape but the wrong size
    once a company has hundreds of holders, because it then exceeds the size of
    the holdings it is meant to detect the loss of.
    """
    return min(PERCENT_HALF_UNIT * (addend_count + 1), MAX_PERCENT_TOLERANCE)


def crore_tolerance(addend_count: int) -> Decimal:
    """The rounding band a correct sum of whole-crore amounts may fall in."""
    return CRORE_HALF_UNIT * (addend_count + 1)


class InvestorHook(BaseModel):
    """One investors drill-down the page offers, read from its own button."""

    model_config = ConfigDict(frozen=True)

    bucket: str
    periodicity: Periodicity
    row_label: str


class SegmentHook(BaseModel):
    """One Product Segments table the page offers, read from its own button."""

    model_config = ConfigDict(frozen=True)

    section: str
    segment_type: str


class PageHooks(BaseModel):
    """Everything one company page offers to expand, and nothing more.

    A part whose hook is absent while its owning section is present is *not
    offered*: the page rendered the section and did not carry the control, which
    is a fact about the issuer. A part whose owning **section** is absent is
    something else entirely — the page changed shape under us — so
    ``sections_present`` is recorded beside the hooks and the two are never
    conflated. Nothing in this slice ever builds a URL the page did not point at.
    """

    model_config = ConfigDict(frozen=True)

    investors: tuple[InvestorHook, ...] = ()
    segments: tuple[SegmentHook, ...] = ()
    related_party_url: str | None = None
    corporate_actions_url: str | None = None
    warehouse_id: int | None = None
    sections_present: frozenset[str] = frozenset()

    def has(self, *section_ids: str) -> bool:
        """True when the page rendered at least one of these section elements."""
        return any(section_id in self.sections_present for section_id in section_ids)
