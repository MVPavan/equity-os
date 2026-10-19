"""Typed vocabulary for the subscriber-session Screener adapter.

This module holds the enums, injected settings, typed refusals, and frozen
artifacts shared by the transport (:mod:`fundamentals.ingest.screener_session`)
and the page assertions (:mod:`fundamentals.ingest.screener_session_page`).

It is a sibling of the anonymous derived adapter
(:mod:`fundamentals.ingest.screener_source`), never a replacement: that adapter
reads the credential-free public page and emits derived cross-check
observations; this one carries the owner's Premium ``sessionid`` cookie, and in
this slice acquires page bytes plus proof of *who* and *which basis* served
them. No financial parsing happens here.

Rights posture is unchanged (A05-DECISION-004): Screener is a derived
aggregator, subscriber content is private-use only, and every block status is
terminal — this adapter never works around one.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import assert_never
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord

# The subscriber surface is a distinct source from the anonymous public page:
# same site, different rights posture and different evidence, so it carries its
# own id rather than silently widening ``screener_source.SOURCE_ID``.
SOURCE_ID = "screener-subscriber"

# The origin is pinned, not configured: a settable base URL would let a config
# edit attach the owner's session cookie to an arbitrary host.
SCREENER_SCHEME = "https"
SCREENER_HOST = "www.screener.in"
SCREENER_ORIGIN = f"{SCREENER_SCHEME}://{SCREENER_HOST}"
CONSOLIDATED_PATH_TEMPLATE = "/company/{slug}/consolidated/"
STANDALONE_PATH_TEMPLATE = "/company/{slug}/"
DEFAULT_USER_AGENT = "EquityOS Research"
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024

# Observed 2026-08-26: authenticated GETs at ~0.6 s spacing were rate-limited
# after ~40 requests (surface-map.md §9). Default spacing sits well above that.
DEFAULT_MIN_REQUEST_SPACING_SECONDS = 1.5
DEFAULT_RATE_LIMIT_RETRIES = 2
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 2.0

# Upper bounds on injected timing. They exist so a mistyped or hostile config
# cannot turn a polite fetcher into a hang (huge timeout), a hammer (many
# retries), or a stall (unbounded backoff).
MAX_RATE_LIMIT_RETRIES = 2
MAX_RATE_LIMIT_BACKOFF_SECONDS = 60.0
MAX_TOTAL_RETRY_BUDGET_SECONDS = 120.0
MAX_REQUEST_TIMEOUT_SECONDS = 120.0
MAX_REQUEST_SPACING_SECONDS = 60.0

SESSION_COOKIE_NAME = "sessionid"
COOKIE_HEADER = "Cookie"
USER_AGENT_HEADER = "User-Agent"
LOCATION_HEADER = "Location"

# Screener routes the company page and its sub-documents differently on this
# header alone. ``/company/actions/<id>/`` answers HTTP 302 to the company page
# without it and 200 with the modal body with it (verified live 2026-08-26); the
# peers fragment differs slightly too. A browser sends it on every XHR the
# company page issues and on none of its navigations, so it is attached to
# sub-document fetches only — sending it on the page would be asking for a
# response no browser ever receives.
XHR_HEADER = "X-Requested-With"
XHR_HEADER_VALUE = "XMLHttpRequest"

RATE_LIMITED_STATUS = 429
# 403/451 are terminal exactly as in the anonymous adapter: stop, never evade.
TERMINAL_BLOCK_STATUSES = frozenset({403, 451})


class Basis(StrEnum):
    """Which set of figures a company page was asked for, or observed to carry.

    Consolidated is the default basis for this repo (surface-map.md §10);
    standalone is acquired only as an explicit request.
    """

    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"


class PageOutcome(StrEnum):
    """Whether a fetched page carried the basis that was asked for.

    ``BASIS_UNAVAILABLE`` is a fact about the company, not a transport failure:
    a standalone-only company serves its ``/consolidated/`` URL as HTTP 200 with
    no basis marker, no warehouse id, and empty financial tables. It must never
    read as success and must never be substituted with the standalone page.
    """

    OK = "ok"
    BASIS_UNAVAILABLE = "basis_unavailable"


PAGE_OUTCOME_KIND = f"{PageOutcome.__module__}.{PageOutcome.__qualname__}"


def to_outcome_record(outcome: PageOutcome) -> OutcomeRecord:
    """Restate one page outcome in the shared capture-level vocabulary.

    ``BASIS_UNAVAILABLE`` becomes ``NOT_OFFERED``, never ``OK`` or ``OK_EMPTY``
    (owner decision 2, 2026-09-05): the vendor has no consolidated basis for
    this company, which a later coverage report must be able to tell apart from
    a basis that was offered and came back blank — the second invites a retry
    and a standalone substitution, the exact contamination this outcome exists
    to prevent.
    """
    match outcome:
        case PageOutcome.OK:
            code = OutcomeCode.OK
        case PageOutcome.BASIS_UNAVAILABLE:
            code = OutcomeCode.NOT_OFFERED
        case _:
            assert_never(outcome)
    return OutcomeRecord(code=code, native_kind=PAGE_OUTCOME_KIND, native_value=outcome.value)


class ScreenerSessionError(Exception):
    """Base for every typed refusal raised by the subscriber adapter."""


class ScreenerCredentialsError(ScreenerSessionError):
    """No session cookie was injected; the fetch is refused before any request."""


class ScreenerSessionFetchError(ScreenerSessionError):
    """Transport failed or returned a status this adapter will not interpret."""


class ScreenerRedirectError(ScreenerSessionFetchError):
    """A redirect was returned and refused rather than followed.

    Redirects are never followed: the login redirect would otherwise turn an
    expired session into a plausible page, and the outbound BSE/NSE document
    links would turn an in-repo fetch into a third-party one.
    """


class ScreenerBlockedError(ScreenerSessionFetchError):
    """Terminal block (403/451) — stop; never retry or work around it."""


class ScreenerRateLimitedError(ScreenerSessionFetchError):
    """HTTP 429 survived the bounded backoff; the run fails closed."""


class ScreenerOriginError(ScreenerSessionFetchError):
    """A request was about to leave the pinned Screener origin.

    Raised before any request object is built: the session cookie is owner auth
    material, so it must never be attached to a URL this adapter did not pin.
    """


class AnonymousPageError(ScreenerSessionError):
    """The response carried no proof of an authenticated session.

    An expired Screener cookie yields a *valid anonymous page*, not an error, so
    absence of a login form proves nothing: only the Account menu (Profile link
    plus the logout form) is accepted as evidence.
    """


class IdentityMismatchError(ScreenerSessionError):
    """The page's own numeric ids did not match the configured identity."""


class IdentityAmbiguousError(ScreenerSessionError):
    """The page carried zero, or more than one, identity element.

    A second ``#company-info`` element would make identity a question of which
    one is read first — and a decoy carrying the expected ids would let a page
    about another company pass the check. Exactly one is required.
    """


class BasisMismatchError(ScreenerSessionError):
    """The page positively declared the basis that was *not* requested.

    Distinct from :class:`ScreenerSessionError` subclasses about availability: a
    substituted basis is a page that would parse cleanly into the wrong numbers.
    """


class BasisEvidenceMissingError(ScreenerSessionError):
    """A basis the config says exists was not proven by the page that served it.

    Distinct from :class:`PageOutcome.BASIS_UNAVAILABLE`, which is a *structural
    fact* about a standalone-only company. This is drift: the config records a
    warehouse id for the requested basis, so the page must prove that basis; a
    page that no longer does has changed under us and must stop the run rather
    than be recorded as either success or a structural absence.
    """


class BasisTopology(BaseModel):
    """Which bases a company publishes, as recorded in config.

    Basis topology is configuration, never an inference from the page: a page
    that has lost its marker looks exactly like a standalone-only company's
    page, so reading topology off the response would let drift masquerade as a
    structural fact about the issuer.
    """

    model_config = ConfigDict(frozen=True)

    consolidated_warehouse_id: int | None = Field(default=None, gt=0)
    standalone_warehouse_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_at_least_one_basis(self) -> BasisTopology:
        """Reject a topology that publishes no basis at all."""
        if self.consolidated_warehouse_id is None and self.standalone_warehouse_id is None:
            raise ValueError("a basis topology must carry at least one warehouse id")
        return self

    def warehouse_id_for(self, basis: Basis) -> int | None:
        """The configured warehouse id for one basis, or ``None`` if unpublished."""
        if basis is Basis.CONSOLIDATED:
            return self.consolidated_warehouse_id
        return self.standalone_warehouse_id

    @property
    def single_basis(self) -> bool:
        """True when config records exactly one published basis for this company."""
        return (self.consolidated_warehouse_id is None) != (self.standalone_warehouse_id is None)

    @property
    def standalone_only(self) -> bool:
        """True when config records a standalone basis and no consolidated one.

        This is the *only* topology whose page legitimately carries no basis
        marker: such a company is offered no toggle, so Screener renders a bare
        "Figures in Rs. Crores" (verified on NETWEB, surface-map.md §10). A
        consolidated page always carries its marker, whatever the topology.
        """
        return self.consolidated_warehouse_id is None and self.standalone_warehouse_id is not None


def company_page_url(slug: str, basis: Basis) -> str:
    """Build one company-page URL on the pinned Screener origin."""
    template = (
        CONSOLIDATED_PATH_TEMPLATE if basis is Basis.CONSOLIDATED else STANDALONE_PATH_TEMPLATE
    )
    return f"{SCREENER_ORIGIN}{template.format(slug=slug)}"


def assert_pinned_origin(url: str) -> None:
    """Refuse any URL that is not plain ``https://www.screener.in`` with no credentials."""
    parts = urlsplit(url)
    if (
        parts.scheme != SCREENER_SCHEME
        or parts.hostname != SCREENER_HOST
        or parts.port is not None
        or parts.username is not None
        or parts.password is not None
    ):
        raise ScreenerOriginError(
            f"refusing to send the session cookie off-origin: {url!r} is not {SCREENER_ORIGIN}"
        )


class ScreenerCredentials(BaseModel):
    """Owner subscriber auth material, injected at the composition root only.

    The cookie is a :class:`~pydantic.SecretStr` so it cannot be logged or
    serialized by accident; only the transport reads its secret value, into the
    outbound ``Cookie`` header.
    """

    model_config = ConfigDict(frozen=True)

    session_cookie: SecretStr


class ScreenerSessionConfig(BaseModel):
    """Injected settings for the subscriber adapter (no environment reads here)."""

    model_config = ConfigDict(frozen=True)

    credentials: ScreenerCredentials | None = None
    user_agent: str = DEFAULT_USER_AGENT
    request_timeout_seconds: float = Field(
        default=30.0, gt=0, le=MAX_REQUEST_TIMEOUT_SECONDS, allow_inf_nan=False
    )
    min_request_spacing_seconds: float = Field(
        default=DEFAULT_MIN_REQUEST_SPACING_SECONDS,
        ge=0,
        le=MAX_REQUEST_SPACING_SECONDS,
        allow_inf_nan=False,
    )
    max_rate_limit_retries: int = Field(
        default=DEFAULT_RATE_LIMIT_RETRIES, ge=0, le=MAX_RATE_LIMIT_RETRIES
    )
    rate_limit_backoff_seconds: float = Field(
        default=DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
        ge=0,
        le=MAX_RATE_LIMIT_BACKOFF_SECONDS,
        allow_inf_nan=False,
    )
    max_response_bytes: int = Field(default=DEFAULT_MAX_RESPONSE_BYTES, gt=0)

    @model_validator(mode="after")
    def _check_retry_budget_is_bounded(self) -> ScreenerSessionConfig:
        """Cap the total time a single fetch may spend backing off.

        Each retry doubles the wait, so per-attempt bounds alone do not bound the
        run; this pins the worst case a caller can configure.
        """
        budget = sum(
            self.rate_limit_backoff_seconds * (2**attempt)
            for attempt in range(self.max_rate_limit_retries)
        )
        if budget > MAX_TOTAL_RETRY_BUDGET_SECONDS:
            raise ValueError(
                f"total retry backoff budget {budget}s exceeds the "
                f"{MAX_TOTAL_RETRY_BUDGET_SECONDS}s cap"
            )
        return self


class PageEvidence(BaseModel):
    """What one fetched company page proved about itself.

    Every field is an observation, never an assumption: the basis is read from
    the page's own markers and warehouse id, not from the URL that was asked for
    (a standalone-only company answers the consolidated URL with HTTP 200).
    """

    model_config = ConfigDict(frozen=True)

    logged_in: bool
    company_id: int
    warehouse_id: int | None
    markers: tuple[str, ...]
    basis_observed: Basis | None
    single_basis: bool
    tables_empty: bool


class ScreenerPageMetadata(BaseModel):
    """Provenance and assertion record for one subscriber company-page fetch."""

    model_config = ConfigDict(frozen=True)

    source_id: str = SOURCE_ID
    symbol: str
    slug: str
    source_url: str
    http_status: int
    outcome: PageOutcome
    basis_requested: Basis
    basis_observed: Basis | None
    single_basis: bool
    markers: tuple[str, ...]
    tables_empty: bool
    expected_company_id: int
    expected_warehouse_id: int | None
    company_id_seen: int
    warehouse_id_seen: int | None
    logged_in: bool
    content_sha256: str
    byte_count: int
    fetched_at: datetime


class ScreenerPageFetch(BaseModel):
    """One retained company-page response: its bytes and what they proved."""

    model_config = ConfigDict(frozen=True)

    raw_body: bytes
    metadata: ScreenerPageMetadata


class ScreenerDocumentFetch(BaseModel):
    """One retained on-origin API response, with no assertions about its content.

    The company page proves who and what served it; a Screener API document
    proves nothing at all — a schedules body is a bare label-to-value map. So
    this record deliberately carries no outcome and no identity: it is the bytes,
    the URL that is their only binding, and the hash that ties an artifact to
    them. Whether the body is meaningful is decided by the reader that asked
    for it, against evidence the page supplies.
    """

    model_config = ConfigDict(frozen=True)

    raw_body: bytes
    source_url: str
    http_status: int
    content_sha256: str
    byte_count: int
    fetched_at: datetime
