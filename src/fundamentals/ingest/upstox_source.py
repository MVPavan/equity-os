"""Upstox read-only transport: the route registry, the polite GET, and the capture.

This module is the scope boundary of the whole Upstox lane. Ten approved GET
surfaces live in :data:`ROUTES`, every URL is built from that registry, and no
caller can assemble a path at the call site — which is how ``profile``,
``competitors`` and every order/portfolio/money surface stay unreachable rather
than merely unused.

Two hosts with different rules:

* ``api.upstox.com`` takes the Analytics Token as a ``Bearer`` header and is the
  only origin that ever sees it;
* ``assets.upstox.com`` publishes the static instrument files and is never
  handed a credential, which is why the instrument slice ships before any token
  exists.

Three fail-closed rules the vendor makes load-bearing. A 403 here is a
Cloudflare browser-signature block that never clears on backoff, so it is
terminal and unretried. A redirect is refused rather than followed, because a
followed redirect is where a Bearer header leaves its pinned origin. And the
response body is **hashed before anything else touches it** — no Upstox surface
carries a server-side as-of or version field, so our own hash over the raw bytes
is the only restatement detector that exists.

This module performs no parsing beyond the transport envelope. Surface
semantics live in the per-surface modules that read a :class:`UpstoxFetch`.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, assert_never
from urllib.parse import quote, urlencode, urlsplit

import structlog
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import BodyCompleteness, BodyReadIssue, CaptureRecord
from fundamentals.ingest.http_session import (
    BoundedBodyRead,
    NoRedirectHandler,
    RequestPacer,
    read_bounded_capture,
)
from fundamentals.ingest.upstox_retention import seal_capture
from fundamentals.store.snapshot_store import SnapshotStore

_LOGGER = structlog.get_logger(__name__)

UPSTOX_API_ORIGIN = "https://api.upstox.com"
UPSTOX_ASSETS_ORIGIN = "https://assets.upstox.com"

# Honest self-identification, required rather than polite: the vendor's edge
# answers an unidentified client with a Cloudflare 1010 block, which is terminal.
DEFAULT_USER_AGENT = "EquityOS Research"

AUTHORIZATION_HEADER = "Authorization"
USER_AGENT_HEADER = "User-Agent"
ACCEPT_HEADER = "Accept"
CONTENT_TYPE_HEADER = "Content-Type"
CONTENT_ENCODING_HEADER = "Content-Encoding"
LOCATION_HEADER = "Location"
BEARER_PREFIX = "Bearer"

RATE_LIMITED_STATUS = 429
UNAUTHORIZED_STATUS = 401
# 403 is a browser-signature block on this vendor, not an authorization failure.
BLOCKED_STATUSES = frozenset({403, 451})

REDACTED_SECRET = "[redacted-secret]"

# The documented "Other Standard APIs" bucket is 2,000 requests per 30 minutes,
# which binds at ~1.1 req/s sustained; the 50/s burst is headroom we do not use.
DEFAULT_MIN_REQUEST_SPACING_SECONDS = 1.1
DEFAULT_RATE_LIMIT_RETRIES = 3
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 2.0
MAX_REQUEST_TIMEOUT_SECONDS = 120.0
MAX_REQUEST_SPACING_SECONDS = 60.0
MAX_RATE_LIMIT_RETRIES = 6
MAX_RATE_LIMIT_BACKOFF_SECONDS = 120.0
MAX_TOTAL_RETRY_BUDGET_SECONDS = 300.0

# The complete instrument file is ~3.2 MB compressed and ~54.6 MB decompressed.
# One cap cannot bound both sides of that ratio, so there are two.
DEFAULT_MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_DECOMPRESSED_BYTES = 192 * 1024 * 1024
DEFAULT_MAX_REQUESTS_PER_RUN = 500

_DISHONEST_USER_AGENT_PREFIX = "Python-urllib"

_NO_CREDENTIALS = (
    "upstox analytics token required for an authenticated surface; mint one from the "
    "developer console and inject it as credentials.access_token"
)


class UpstoxSurface(StrEnum):
    """One approved acquisition surface. The set is the lane's scope boundary."""

    INSTRUMENTS = "instruments"
    CANDLES = "candles"
    CORPORATE_ACTIONS = "corporate-actions"
    SHARE_HOLDINGS = "share-holdings"
    HOLIDAYS = "holidays"
    FII_DII = "fii-dii"
    INCOME_STATEMENT = "income-statement"
    BALANCE_SHEET = "balance-sheet"
    CASH_FLOW = "cash-flow"
    KEY_RATIOS = "key-ratios"


# The six Lane A surfaces have no XBRL or Screener counterpart; the four Lane B
# surfaces are a differential parse-check and never adjudicate anything.
APPROVED_SURFACES: tuple[UpstoxSurface, ...] = tuple(UpstoxSurface)


class RouteHost(StrEnum):
    """Which of the two pinned origins a route addresses."""

    API = UPSTOX_API_ORIGIN
    ASSETS = UPSTOX_ASSETS_ORIGIN


class HttpMethod(StrEnum):
    """The only method this lane may use."""

    GET = "GET"


class AcquisitionOutcome(StrEnum):
    """What one acquisition attempt established.

    Deliberately **local** to this module and not published under ``contracts/``.
    The shared capture-level code now exists as
    :class:`~fundamentals.contracts.acquisition_outcome.OutcomeCode`; this enum
    stays the lane's wire vocabulary and :func:`to_outcome_record` is the only
    bridge, so a second shared enum with this name is still the migration cost
    the lane exists to avoid.
    """

    OK = "OK"
    OK_EMPTY = "OK_EMPTY"
    CLIENT_BLOCKED = "CLIENT_BLOCKED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    PLAN_LOCKED = "PLAN_LOCKED"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"


# The two outcomes a bounded retry can clear. Every other failure is terminal:
# a block never clears on backoff, and a dead token is renewed by a human.
RETRYABLE_OUTCOMES = frozenset(
    {AcquisitionOutcome.RATE_LIMITED, AcquisitionOutcome.TRANSPORT_ERROR}
)

ACQUISITION_OUTCOME_KIND = f"{AcquisitionOutcome.__module__}.{AcquisitionOutcome.__qualname__}"


def to_outcome_record(outcome: AcquisitionOutcome) -> OutcomeRecord:
    """Restate one Upstox outcome in the shared capture-level vocabulary.

    Every member is spelled out and the fallthrough is :func:`assert_never`, so
    a member added here without a shared code fails type checking rather than
    raising while a capture is being recorded or defaulting a block to success.
    """
    match outcome:
        case AcquisitionOutcome.OK:
            code = OutcomeCode.OK
        case AcquisitionOutcome.OK_EMPTY:
            code = OutcomeCode.OK_EMPTY
        case AcquisitionOutcome.CLIENT_BLOCKED:
            code = OutcomeCode.CLIENT_BLOCKED
        case AcquisitionOutcome.AUTH_EXPIRED:
            code = OutcomeCode.AUTH_EXPIRED
        case AcquisitionOutcome.RATE_LIMITED:
            code = OutcomeCode.RATE_LIMITED
        case AcquisitionOutcome.REQUEST_REJECTED:
            code = OutcomeCode.REQUEST_REJECTED
        case AcquisitionOutcome.PLAN_LOCKED:
            code = OutcomeCode.PLAN_LOCKED
        case AcquisitionOutcome.SCHEMA_DRIFT:
            code = OutcomeCode.SCHEMA_DRIFT
        case AcquisitionOutcome.TRANSPORT_ERROR:
            code = OutcomeCode.TRANSPORT_ERROR
        case _:
            assert_never(outcome)
    return OutcomeRecord(
        code=code, native_kind=ACQUISITION_OUTCOME_KIND, native_value=outcome.value
    )


class UpstoxError(Exception):
    """Base for every typed refusal this adapter raises."""


class UpstoxCredentialsError(UpstoxError):
    """Raised when an authenticated route is called with no injected token.

    A configuration defect, deliberately not ``AUTH_EXPIRED``: nothing was sent,
    so the vendor said nothing about the credential.
    """


class UpstoxOriginError(UpstoxError):
    """Raised when a built URL is not exactly one of the two pinned origins."""


class UpstoxRedirectError(UpstoxError):
    """Raised when the vendor redirects a pinned request.

    Carries no :class:`AcquisitionOutcome` on purpose. No acquisition happened
    against the resource that was asked for, so classifying the attempt would
    record an outcome for a fetch that never took place.
    """


class UpstoxRunBudgetError(UpstoxError):
    """Raised when one command would exceed its configured request budget.

    Also outcome-free: the request was never made, so there is nothing to
    classify. This is what keeps a single command from becoming an unbounded
    crawl of a rate-limited vendor.
    """


class UnknownRouteError(LookupError):
    """Raised when a surface/route-key pair is not in the approved registry."""


class UpstoxFetchError(UpstoxError):
    """A failed acquisition attempt, carrying the outcome it classified as."""

    outcome: AcquisitionOutcome = AcquisitionOutcome.TRANSPORT_ERROR

    def __init__(self, message: str, *, outcome: AcquisitionOutcome | None = None) -> None:
        super().__init__(message)
        self.raw_body: bytes | None = None
        self.http_status: int | None = None
        self.media_type: str | None = None
        self.content_encoding: str | None = None
        self.body_completeness = BodyCompleteness.ABSENT
        self.body_read_issue: BodyReadIssue | None = None
        self.capture_record: CaptureRecord | None = None
        if outcome is not None:
            self.outcome = outcome

    @property
    def retryable(self) -> bool:
        """Whether a bounded retry could plausibly clear this failure."""
        return self.outcome in RETRYABLE_OUTCOMES


class UpstoxBlockedError(UpstoxFetchError):
    """Cloudflare 1010 or an equivalent terminal block. Never retried."""

    outcome = AcquisitionOutcome.CLIENT_BLOCKED


class UpstoxAuthExpiredError(UpstoxFetchError):
    """The Analytics Token was rejected. A human renews it; a retry cannot."""

    outcome = AcquisitionOutcome.AUTH_EXPIRED


class UpstoxRateLimitedError(UpstoxFetchError):
    """The bounded 429 retry budget was exhausted without clearing."""

    outcome = AcquisitionOutcome.RATE_LIMITED


class UpstoxRoute(BaseModel):
    """One approved GET, addressed by surface and route key.

    ``path_template`` holds ``{name}`` placeholders filled by
    :func:`build_path`, which percent-encodes each value as a single segment.
    Authentication follows the host and is never a per-call choice.
    """

    model_config = ConfigDict(frozen=True)

    surface: UpstoxSurface
    route_key: str = Field(min_length=1)
    host: RouteHost
    path_template: str = Field(min_length=1)
    method: HttpMethod = HttpMethod.GET

    @property
    def authenticated(self) -> bool:
        """Only the API host takes the Bearer token; the assets host never does."""
        return self.host is RouteHost.API

    @property
    def origin(self) -> str:
        """The pinned origin this route addresses."""
        return self.host.value


DEFAULT_ROUTE_KEY = "default"
INSTRUMENTS_COMPLETE_KEY = "complete"
INSTRUMENTS_SUSPENDED_KEY = "suspended"

_INSTRUMENTS_PREFIX = "/market-quote/instruments/exchange"

# to_date comes BEFORE from_date. Reversing the two returns a WRONG WINDOW with
# HTTP 200 and no error of any kind. Verified live; the template is the only
# place the order is written down.
CANDLE_PATH_TEMPLATE = (
    "/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}"
)

ROUTES: tuple[UpstoxRoute, ...] = (
    UpstoxRoute(
        surface=UpstoxSurface.INSTRUMENTS,
        route_key=INSTRUMENTS_COMPLETE_KEY,
        host=RouteHost.ASSETS,
        path_template=f"{_INSTRUMENTS_PREFIX}/complete.json.gz",
    ),
    # ``suspended-instrument`` is singular. The plural spelling 404s.
    UpstoxRoute(
        surface=UpstoxSurface.INSTRUMENTS,
        route_key=INSTRUMENTS_SUSPENDED_KEY,
        host=RouteHost.ASSETS,
        path_template=f"{_INSTRUMENTS_PREFIX}/suspended-instrument.json.gz",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.CANDLES,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template=CANDLE_PATH_TEMPLATE,
    ),
    UpstoxRoute(
        surface=UpstoxSurface.CORPORATE_ACTIONS,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/corporate-actions",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.SHARE_HOLDINGS,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/share-holdings",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.HOLIDAYS,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/market/holidays",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.HOLIDAYS,
        route_key="on-date",
        host=RouteHost.API,
        path_template="/v2/market/holidays/{date}",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.FII_DII,
        route_key="fii",
        host=RouteHost.API,
        path_template="/v2/market/fii",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.FII_DII,
        route_key="dii",
        host=RouteHost.API,
        path_template="/v2/market/dii",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.INCOME_STATEMENT,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/income-statement",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.BALANCE_SHEET,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/balance-sheet",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.CASH_FLOW,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/cash-flow",
    ),
    UpstoxRoute(
        surface=UpstoxSurface.KEY_RATIOS,
        route_key=DEFAULT_ROUTE_KEY,
        host=RouteHost.API,
        path_template="/v2/fundamentals/{isin}/key-ratios",
    ),
)

# Path segments no route may contain. ``profile`` and ``competitors`` are out of
# scope because neither has a Screener counterpart to check against; the rest are
# barred outright by product invariant 12 — no order APIs, broker credentials or
# portfolio state in the research system.
BARRED_PATH_SEGMENTS = frozenset(
    {
        "profile",
        "competitors",
        "order",
        "portfolio",
        "user",
        "funds",
        "gtt",
        "trade",
        "charges",
        "logout",
        "login",
        "payments",
        "mutual-fund",
    }
)


def _assert_registry_is_in_scope() -> None:
    """Refuse at import if any registered route names a barred or unapproved surface.

    A structural check rather than only a test: a route added later without the
    scope review fails the process rather than shipping quietly.
    """
    for route in ROUTES:
        if route.method is not HttpMethod.GET:
            raise ValueError(f"non-GET route registered: {route.path_template}")
        for segment in route.path_template.split("/"):
            if segment.lower() in BARRED_PATH_SEGMENTS:
                raise ValueError(f"barred path segment {segment!r} in {route.path_template}")
    registered = {route.surface for route in ROUTES}
    if registered != set(APPROVED_SURFACES):
        raise ValueError("route registry does not cover exactly the approved surfaces")


_assert_registry_is_in_scope()

_ROUTE_INDEX: dict[tuple[UpstoxSurface, str], UpstoxRoute] = {
    (route.surface, route.route_key): route for route in ROUTES
}


def route_for(surface: UpstoxSurface, route_key: str = DEFAULT_ROUTE_KEY) -> UpstoxRoute:
    """Resolve one approved route, refusing anything the registry does not hold."""
    route = _ROUTE_INDEX.get((surface, route_key))
    if route is None:
        raise UnknownRouteError(f"no approved upstox route for {surface.value}/{route_key}")
    return route


def build_path(route: UpstoxRoute, params: Mapping[str, str]) -> str:
    """Fill a route's template, encoding each value as exactly one path segment.

    ``quote(value, safe="")`` is what makes the pipe in an ``instrument_key``
    legal (``NSE_EQ%7CINE009A01021``) and what stops a value containing a slash
    from rewriting the route into a path nobody approved.
    """
    encoded = {name: quote(value, safe="") for name, value in params.items()}
    try:
        return route.path_template.format(**encoded)
    except KeyError as error:
        raise UnknownRouteError(
            f"route {route.surface.value}/{route.route_key} needs path parameter {error}"
        ) from error


def build_url(
    route: UpstoxRoute,
    params: Mapping[str, str] | None = None,
    query: Mapping[str, str] | None = None,
) -> str:
    """Build one absolute URL from the registry, then prove its origin is pinned."""
    url = f"{route.origin}{build_path(route, params or {})}"
    if query:
        url = f"{url}?{urlencode(sorted(query.items()))}"
    assert_pinned_origin(url, route.host)
    return url


def assert_pinned_origin(url: str, host: RouteHost) -> None:
    """Refuse any URL that is not plain HTTPS on the route's own host, credential-free."""
    parts = urlsplit(url)
    expected = urlsplit(host.value)
    if (
        parts.scheme != expected.scheme
        or parts.hostname != expected.hostname
        or parts.port is not None
        or parts.username is not None
        or parts.password is not None
    ):
        raise UpstoxOriginError(f"refusing off-origin upstox request: {url!r} is not {host.value}")


class UpstoxCredentials(BaseModel):
    """The Analytics Token, injected at the composition root only.

    ``SecretStr`` so a stray ``repr`` in a traceback or a log line is not a leak;
    only the transport reads its secret value, into the outbound ``Bearer``
    header. The token is read-only, valid for a year, and never sent anywhere
    but :data:`UPSTOX_API_ORIGIN`.
    """

    model_config = ConfigDict(frozen=True)

    access_token: SecretStr


def _utc_now() -> datetime:
    """The default wall-clock supplier for ``retrieved_at``."""
    return datetime.now(tz=UTC)


class UpstoxConfig(BaseModel):
    """Injected settings for the Upstox lane (no environment reads here)."""

    model_config = ConfigDict(frozen=True)

    credentials: UpstoxCredentials | None = None
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
    max_compressed_bytes: int = Field(
        default=DEFAULT_MAX_COMPRESSED_BYTES, gt=0, le=DEFAULT_MAX_COMPRESSED_BYTES
    )
    max_decompressed_bytes: int = Field(
        default=DEFAULT_MAX_DECOMPRESSED_BYTES, gt=0, le=DEFAULT_MAX_DECOMPRESSED_BYTES
    )
    max_requests_per_run: int = Field(default=DEFAULT_MAX_REQUESTS_PER_RUN, gt=0)
    retrieved_at: Callable[[], datetime] = _utc_now

    @field_validator("user_agent")
    @classmethod
    def _check_user_agent_is_honest(cls, value: str) -> str:
        """Refuse an absent or library-default identity.

        Correctness, not politeness: the vendor's edge answers an unidentified
        client with a terminal Cloudflare block, so a dishonest agent turns into
        a production outage that looks like a rights problem.
        """
        agent = value.strip()
        if not agent:
            raise ValueError("user_agent must identify this client")
        if agent.startswith(_DISHONEST_USER_AGENT_PREFIX):
            raise ValueError(f"user_agent must not be the library default {agent!r}")
        return value

    @model_validator(mode="after")
    def _check_retry_budget_is_bounded(self) -> UpstoxConfig:
        """Cap the total time a single fetch may spend backing off."""
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

    @model_validator(mode="after")
    def _check_decompressed_cap_exceeds_compressed(self) -> UpstoxConfig:
        """A gzip that cannot expand is a cap that bounds nothing."""
        if self.max_decompressed_bytes <= self.max_compressed_bytes:
            raise ValueError(
                "max_decompressed_bytes must exceed max_compressed_bytes; the complete "
                "instrument file expands roughly seventeen-fold"
            )
        return self


class UpstoxCapture(BaseModel):
    """What one acquisition attempt retained about the bytes it received.

    ``raw_body`` is deliberately not a field here: the bytes travel beside this
    record in :class:`UpstoxFetch` and are written verbatim, so what lands on
    disk is byte-identical to what ``content_sha256`` covers.
    """

    model_config = ConfigDict(frozen=True)

    surface: UpstoxSurface
    route_key: str
    request_url: str
    http_status: int
    media_type: str | None
    byte_count: int
    content_sha256: str
    outcome: AcquisitionOutcome
    retrieved_at: datetime
    content_encoding: str | None = None

    @property
    def capture_id(self) -> str:
        """A per-capture directory name, unique by construction within a surface."""
        stamp = self.retrieved_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{self.content_sha256[:12]}"


class UpstoxFetch(BaseModel):
    """One response: the untouched bytes plus the record that binds them."""

    model_config = ConfigDict(frozen=True)

    raw_body: bytes
    capture: UpstoxCapture


class UpstoxSource:
    """The polite, pinned, GET-only Upstox transport.

    One instance is one run: it holds the request budget and the pacer, so a
    command cannot exceed either by constructing a second source.
    """

    def __init__(
        self, config: UpstoxConfig | None = None, *, snapshot_store: SnapshotStore | None = None
    ) -> None:
        self._config = config or UpstoxConfig()
        self._snapshot_store = snapshot_store
        self._pacer = RequestPacer(self._config.min_request_spacing_seconds)
        self._requests_made = 0

    @property
    def requests_made(self) -> int:
        """How many outbound requests this run has spent."""
        return self._requests_made

    def redact(self, text: str) -> str:
        """Return ``text`` with this source's access token removed.

        The token never leaves this object, not even to a caller that wants to
        strip it from a message: the caller hands the text in and gets a safe
        one back.
        """
        credentials = self._config.credentials
        if credentials is None:
            return text
        return text.replace(credentials.access_token.get_secret_value(), REDACTED_SECRET)

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        """GET one approved route and retain its bytes with a hash and an outcome.

        The URL is built here from the registry rather than accepted from the
        caller, so the origin gate and the auth decision cannot be bypassed by
        handing this method a string.
        """
        url = build_url(route, params, query)
        headers = self._headers(route)
        try:
            status, payload, media_type, encoding = self._request_bytes(
                url, headers=headers, route=route
            )
        except UpstoxFetchError as error:
            if error.capture_record is None:
                error.capture_record = self._retain_response(
                    route,
                    url,
                    error.raw_body,
                    error.http_status,
                    error.media_type,
                    error.content_encoding,
                    error.outcome,
                    error.body_completeness,
                    error.body_read_issue,
                )
            raise
        capture = UpstoxCapture(
            surface=route.surface,
            route_key=route.route_key,
            request_url=url,
            http_status=status,
            media_type=media_type,
            byte_count=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            outcome=AcquisitionOutcome.OK,
            retrieved_at=self._config.retrieved_at(),
            content_encoding=encoding,
        )
        record = seal_capture(
            surface=capture.surface.value,
            route_key=capture.route_key,
            url=url,
            retrieved_at=capture.retrieved_at,
            http_status=status,
            media_type=media_type,
            content_encoding=encoding,
            raw_body=payload,
            outcome=to_outcome_record(capture.outcome),
            body_completeness=BodyCompleteness.COMPLETE,
        )
        if self._snapshot_store is not None:
            self._snapshot_store.put_capture(record, payload)
        _LOGGER.info(
            "upstox_fetched",
            surface=route.surface.value,
            route_key=route.route_key,
            status=status,
            bytes=len(payload),
        )
        return UpstoxFetch(raw_body=payload, capture=capture)

    def _headers(self, route: UpstoxRoute) -> dict[str, str]:
        """Build the outbound headers, attaching the token only on the API host."""
        headers = {
            USER_AGENT_HEADER: self._config.user_agent,
            ACCEPT_HEADER: "application/json",
        }
        if not route.authenticated:
            return headers
        credentials = self._config.credentials
        if credentials is None:
            raise UpstoxCredentialsError(_NO_CREDENTIALS)
        headers[AUTHORIZATION_HEADER] = (
            f"{BEARER_PREFIX} {credentials.access_token.get_secret_value()}"
        )
        return headers

    def _request_bytes(
        self, url: str, *, headers: Mapping[str, str], route: UpstoxRoute
    ) -> tuple[int, bytes, str | None, str | None]:
        """Make one polite request: spaced, budgeted, redirect-refusing, 429-aware.

        The opener is built per request rather than cached on the instance, so a
        test seam pinning :func:`urllib.request.build_opener` covers every
        request this adapter can make.
        """
        request = urllib.request.Request(url, headers=dict(headers), method=HttpMethod.GET.value)
        opener = urllib.request.build_opener(NoRedirectHandler())
        for attempt in range(self._config.max_rate_limit_retries + 1):
            self._spend_request(url)
            self._pacer.wait_for_slot()
            refusal: UpstoxFetchError | None = None
            try:
                response = opener.open(request, timeout=self._config.request_timeout_seconds)
            except urllib.error.HTTPError as error:
                response = error
                status = error.code
                try:
                    self._refuse_terminal_status(error, url=url)
                except UpstoxRedirectError:
                    error.close()
                    raise
                except UpstoxFetchError as classified:
                    refusal = classified
                else:
                    refusal = UpstoxRateLimitedError(f"upstox rate-limited {url}")
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                interrupted = UpstoxFetchError(
                    f"upstox fetch failed for {url}: {type(error).__name__}"
                )
                interrupted.body_read_issue = BodyReadIssue.READ_INTERRUPTED
                raise interrupted from error
            else:
                status = response.getcode()
                if status is not None and 300 <= status < 400:
                    response.close()
                    raise UpstoxRedirectError(f"upstox returned redirect status {status} for {url}")
                if status is not None and status >= 400:
                    status_error = urllib.error.HTTPError(
                        url, status, "refused", response.headers, None
                    )
                    try:
                        self._refuse_terminal_status(status_error, url=url)
                    except UpstoxFetchError as classified:
                        refusal = classified
                    else:
                        refusal = UpstoxRateLimitedError(f"upstox rate-limited {url}")
            try:
                media_type = _media_type(response.headers)
                encoding = (
                    response.headers.get(CONTENT_ENCODING_HEADER) if response.headers else None
                )
                length = response.headers.get("Content-Length") if response.headers else None
                expected = None
                if length and length.strip().isascii() and length.strip().isdigit():
                    try:
                        expected = int(length)
                    except ValueError:
                        # Excessively long digit strings are invalid framing too.
                        pass
                read = (
                    BoundedBodyRead(None, BodyCompleteness.ABSENT, None)
                    if isinstance(response, urllib.error.HTTPError) and response.fp is None
                    else read_bounded_capture(
                        response,
                        self._config.max_compressed_bytes,
                        timeout_seconds=self._config.request_timeout_seconds,
                        expected_bytes=expected,
                    )
                )
            finally:
                response.close()
            if refusal is None and read.completeness is not BodyCompleteness.COMPLETE:
                refusal = UpstoxFetchError(
                    "upstox response body could not be read completely",
                    outcome=(
                        AcquisitionOutcome.SCHEMA_DRIFT
                        if read.issue is BodyReadIssue.NON_BYTES
                        else AcquisitionOutcome.TRANSPORT_ERROR
                    ),
                )
            if refusal is None:
                assert read.raw_body is not None
                return (200 if status is None else status), read.raw_body, media_type, encoding
            refusal.raw_body = read.raw_body
            refusal.http_status = status
            refusal.media_type = media_type
            refusal.content_encoding = encoding
            refusal.body_completeness = read.completeness
            refusal.body_read_issue = read.issue
            # Publication runs under the acquisition refusal's exception context.
            # Raw storage OSError must escape here, not become a transport retry.
            try:
                raise refusal
            except UpstoxFetchError:
                refusal.capture_record = self._retain_response(
                    route,
                    url,
                    read.raw_body,
                    status,
                    media_type,
                    encoding,
                    refusal.outcome,
                    read.completeness,
                    read.issue,
                )
                if refusal.outcome is not AcquisitionOutcome.RATE_LIMITED:
                    raise
                if attempt >= self._config.max_rate_limit_retries:
                    raise
            backoff = self._config.rate_limit_backoff_seconds * (2**attempt)
            _LOGGER.warning(
                "upstox_rate_limited", url=url, attempt=attempt + 1, backoff_seconds=backoff
            )
            del response, read, refusal
            time.sleep(backoff)
        raise AssertionError("rate-limit loop cannot fall through")

    def _retain_response(
        self,
        route: UpstoxRoute,
        url: str,
        payload: bytes | None,
        status: int | None,
        media_type: str | None,
        encoding: str | None,
        outcome: AcquisitionOutcome,
        body_completeness: BodyCompleteness,
        body_read_issue: BodyReadIssue | None,
    ) -> CaptureRecord:
        """Retain failed attempts before retry or refusal can discard evidence."""
        record = seal_capture(
            surface=route.surface.value,
            route_key=route.route_key,
            url=url,
            retrieved_at=self._config.retrieved_at(),
            http_status=status,
            media_type=media_type,
            content_encoding=encoding,
            raw_body=payload,
            outcome=to_outcome_record(outcome),
            body_completeness=body_completeness,
            body_read_issue=body_read_issue,
        )
        if self._snapshot_store is not None:
            self._snapshot_store.put_capture(record, payload)
        return record

    def _spend_request(self, url: str) -> None:
        """Charge one request against the run budget, refusing before the call."""
        if self._requests_made >= self._config.max_requests_per_run:
            raise UpstoxRunBudgetError(
                f"run budget of {self._config.max_requests_per_run} requests is spent; "
                f"refusing {url}"
            )
        self._requests_made += 1

    @staticmethod
    def _refuse_terminal_status(error: urllib.error.HTTPError, *, url: str) -> None:
        """Raise the typed refusal for any status that is not a retryable 429.

        A 403 is not retried. On this vendor it is a browser-signature block,
        and backoff never clears one — retrying it is a politeness failure
        dressed up as recovery.
        """
        if 300 <= error.code < 400:
            location = error.headers.get(LOCATION_HEADER) if error.headers else None
            raise UpstoxRedirectError(
                f"upstox redirected {url} to {location!r}; refusing to follow"
            ) from error
        if error.code in BLOCKED_STATUSES:
            raise UpstoxBlockedError(
                f"upstox returned terminal status {error.code} for {url}"
            ) from error
        if error.code == UNAUTHORIZED_STATUS:
            raise UpstoxAuthExpiredError(
                f"upstox rejected the analytics token for {url}"
            ) from error
        if error.code != RATE_LIMITED_STATUS:
            raise UpstoxFetchError(
                f"upstox returned HTTP {error.code} for {url}",
                outcome=AcquisitionOutcome.REQUEST_REJECTED,
            ) from error


def _media_type(headers: Any) -> str | None:
    """Read the declared media type, or ``None`` when the response declares none."""
    if headers is None:
        return None
    raw = headers.get(CONTENT_TYPE_HEADER)
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.split(";")[0].strip()
