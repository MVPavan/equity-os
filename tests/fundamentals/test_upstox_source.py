"""Fixture-only coverage for the Upstox transport, its route registry and its scope rails.

No test opens a socket: ``urllib``'s opener is replaced with a recording double.

Every gate here exists because this adapter carries a year-long read-only
credential across two hosts with different rules. The Bearer token belongs to
exactly one origin; the instrument files belong to the other and must never see
it. A 403 on this vendor is a Cloudflare browser-signature block, which never
clears on backoff, so retrying it is a politeness failure rather than a recovery
strategy.
"""

from __future__ import annotations

import email.message
import hashlib
import io
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.ingest.upstox_source import (
    APPROVED_SURFACES,
    AUTHORIZATION_HEADER,
    ROUTES,
    UPSTOX_API_ORIGIN,
    UPSTOX_ASSETS_ORIGIN,
    AcquisitionOutcome,
    HttpMethod,
    RouteHost,
    UpstoxAuthExpiredError,
    UpstoxBlockedError,
    UpstoxConfig,
    UpstoxCredentials,
    UpstoxCredentialsError,
    UpstoxFetchError,
    UpstoxRateLimitedError,
    UpstoxRedirectError,
    UpstoxRunBudgetError,
    UpstoxSource,
    UpstoxSurface,
    route_for,
)

_TOKEN = "fixture-analytics-token"
_STAMP = datetime(2026, 9, 4, 6, 30, tzinfo=UTC)


class _Response(io.BytesIO):
    """Minimal urllib response double carrying a status and headers."""

    def __init__(self, payload: bytes, *, status: int = 200, media_type: str | None = None) -> None:
        super().__init__(payload)
        self._status = status
        self.headers = email.message.Message()
        if media_type is not None:
            self.headers["Content-Type"] = media_type

    def getcode(self) -> int:
        """Return the configured HTTP status code."""
        return self._status

    def __enter__(self) -> _Response:
        """Support the ``with opener.open(...)`` form the adapter uses."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the response body."""
        self.close()


class _Opener:
    """Injectable urllib opener that replays a scripted sequence of outcomes."""

    def __init__(self, *outcomes: _Response | urllib.error.HTTPError) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        """Record the outbound request and return (or raise) the next outcome."""
        del timeout
        self.calls.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, urllib.error.HTTPError):
            raise outcome
        return outcome


def _http_error(status: int, *, location: str | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError the way urllib raises one, with real headers."""
    headers = email.message.Message()
    if location is not None:
        headers["Location"] = location
    return urllib.error.HTTPError(UPSTOX_API_ORIGIN, status, "error", headers, None)


def _install(monkeypatch: pytest.MonkeyPatch, opener: _Opener) -> list[float]:
    """Pin opener construction and capture every sleep instead of serving it."""
    slept: list[float] = []

    def build_opener(handler: Any) -> _Opener:
        del handler
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(
        "fundamentals.ingest.upstox_source.time.sleep", lambda seconds: slept.append(seconds)
    )
    return slept


def _config(**overrides: Any) -> UpstoxConfig:
    """A config with a synthetic token, no pacing delay and no real backoff."""
    settings: dict[str, Any] = {
        "credentials": UpstoxCredentials(access_token=_TOKEN),
        "min_request_spacing_seconds": 0.0,
        "rate_limit_backoff_seconds": 0.0,
        "retrieved_at": lambda: _STAMP,
    }
    settings.update(overrides)
    return UpstoxConfig(**settings)


def _source(**overrides: Any) -> UpstoxSource:
    """An Upstox source over the synthetic config above."""
    return UpstoxSource(_config(**overrides))


def _instruments_route() -> Any:
    """The unauthenticated complete-instruments route, used by most transport tests."""
    return route_for(UpstoxSurface.INSTRUMENTS, "complete")


def _candles_route() -> Any:
    """An authenticated route, used to prove the Bearer header reaches the API host."""
    return route_for(UpstoxSurface.CANDLES)


_CANDLE_PARAMS = {
    "instrument_key": "NSE_EQ|INE001A01036",
    "unit": "days",
    "interval": "1",
    "to_date": "2026-09-04",
    "from_date": "2026-08-04",
}


# --- route registry and scope rails -----------------------------------------


def test_route_registry_is_exactly_the_ten_approved_surfaces() -> None:
    """The registry is the scope boundary: ten surfaces, no eleventh.

    Every surface this lane may touch was named in the plan and rights-checked.
    A route added without that review would be acquisition outside the recorded
    scope, so the count is asserted rather than assumed.
    """
    assert len(APPROVED_SURFACES) == 10
    assert {route.surface for route in ROUTES} == set(APPROVED_SURFACES)
    assert set(APPROVED_SURFACES) == set(UpstoxSurface)


def test_every_upstox_route_is_get_only() -> None:
    """This lane reads. A non-GET route would be a write against a broker account."""
    assert {route.method for route in ROUTES} == {HttpMethod.GET}


def test_no_url_builder_can_construct_a_profile_or_competitor_path() -> None:
    """``profile`` and ``competitors`` are out of scope and have no route to build.

    Neither has a Screener counterpart, so neither serves the parse-check this
    lane exists for; ``competitors`` additionally takes a segment-qualified key
    rather than a bare ISIN, which is an integration hazard nobody asked for.
    """
    for route in ROUTES:
        segments = set(route.path_template.split("/"))
        assert "profile" not in segments
        assert "competitors" not in segments


def test_no_url_builder_can_construct_an_account_portfolio_order_or_money_path() -> None:
    """Product invariant 12 bars order, portfolio and money surfaces outright."""
    barred = {"order", "portfolio", "user", "funds", "gtt", "trade", "charges", "logout"}
    for route in ROUTES:
        assert not barred & set(route.path_template.split("/"))


def test_an_unregistered_surface_and_route_key_pair_is_refused() -> None:
    """Routes resolve by lookup only, so no caller can invent a path at the call site."""
    with pytest.raises(LookupError):
        route_for(UpstoxSurface.INSTRUMENTS, "mutual-funds")


def test_only_the_api_host_routes_are_authenticated() -> None:
    """The assets host publishes static files and is never handed a credential."""
    for route in ROUTES:
        assert route.authenticated is (route.host is RouteHost.API)


# --- configuration ----------------------------------------------------------


def test_default_urllib_user_agent_is_refused_at_construction() -> None:
    """A dishonest User-Agent is a correctness rule here, not politeness.

    Upstox's edge answers an unidentified client with a Cloudflare 1010 block,
    which is terminal. Refusing the default at construction turns a silent
    production block into a configuration error.
    """
    with pytest.raises(ValidationError):
        _config(user_agent="Python-urllib/3.12")


def test_an_empty_user_agent_is_refused_at_construction() -> None:
    """An absent identity is no more honest than a library default."""
    with pytest.raises(ValidationError):
        _config(user_agent="   ")


def test_total_retry_backoff_budget_is_bounded_at_construction() -> None:
    """Per-attempt bounds do not bound a run; the doubling budget is capped."""
    with pytest.raises(ValidationError):
        _config(max_rate_limit_retries=6, rate_limit_backoff_seconds=120.0)


def test_compressed_and_decompressed_byte_caps_are_separate_settings() -> None:
    """A 3 MB gzip expands to 55 MB; one cap cannot bound both sides of that."""
    config = _config()
    assert config.max_compressed_bytes != config.max_decompressed_bytes
    assert config.max_decompressed_bytes > config.max_compressed_bytes


# --- transport --------------------------------------------------------------


def test_assets_host_request_carries_no_authorization_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The token belongs to one origin. A static file host never receives it."""
    opener = _Opener(_Response(b"[]"))
    _install(monkeypatch, opener)
    _source().fetch(_instruments_route())
    request = opener.calls[0]
    assert request.full_url.startswith(UPSTOX_ASSETS_ORIGIN)
    assert AUTHORIZATION_HEADER.lower() not in {name.lower() for name in request.headers}


def test_authorization_header_reaches_only_the_pinned_api_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Bearer header is attached by the route's host, never by the caller."""
    opener = _Opener(_Response(b'{"status": "success", "data": {}}'))
    _install(monkeypatch, opener)
    _source().fetch(_candles_route(), **_CANDLE_PARAMS)
    request = opener.calls[0]
    assert request.full_url.startswith(UPSTOX_API_ORIGIN)
    assert request.headers["Authorization"] == f"Bearer {_TOKEN}"


def test_missing_credentials_raise_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unconfigured token is a configuration defect, never ``AUTH_EXPIRED``."""
    opener = _Opener(_Response(b"{}"))
    _install(monkeypatch, opener)
    source = UpstoxSource(_config(credentials=None))
    with pytest.raises(UpstoxCredentialsError):
        source.fetch(_candles_route(), **_CANDLE_PARAMS)
    assert opener.calls == []


def test_an_unauthenticated_route_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """The instrument files ship before any token exists; that is why they are first."""
    opener = _Opener(_Response(b"[]"))
    _install(monkeypatch, opener)
    fetch = UpstoxSource(_config(credentials=None)).fetch(_instruments_route())
    assert fetch.capture.http_status == 200


def test_redirects_are_never_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A redirect off a pinned origin is where a credential leaks; refuse it."""
    opener = _Opener(_http_error(302, location="https://elsewhere.example/"))
    _install(monkeypatch, opener)
    with pytest.raises(UpstoxRedirectError):
        _source().fetch(_instruments_route())


def test_a_three_hundred_status_on_a_returned_response_is_also_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler that returns rather than raises a 3xx must not read as success."""
    opener = _Opener(_Response(b"", status=302))
    _install(monkeypatch, opener)
    with pytest.raises(UpstoxRedirectError):
        _source().fetch(_instruments_route())


def test_cloudflare_403_is_terminal_and_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """403 here is a browser-signature block. Backoff never clears it, so we stop."""
    opener = _Opener(_http_error(403))
    slept = _install(monkeypatch, opener)
    with pytest.raises(UpstoxBlockedError) as caught:
        _source(max_rate_limit_retries=3, rate_limit_backoff_seconds=1.0).fetch(
            _instruments_route()
        )
    assert caught.value.outcome is AcquisitionOutcome.CLIENT_BLOCKED
    assert len(opener.calls) == 1
    assert slept == []


def test_401_is_auth_expired_and_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dead year-long token is renewed by a human, not by a retry loop."""
    opener = _Opener(_http_error(401))
    _install(monkeypatch, opener)
    with pytest.raises(UpstoxAuthExpiredError) as caught:
        _source(max_rate_limit_retries=2).fetch(_instruments_route())
    assert caught.value.outcome is AcquisitionOutcome.AUTH_EXPIRED
    assert len(opener.calls) == 1


def test_rate_limit_retries_and_total_backoff_budget_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429 is the one retryable status, and the doubling is bounded by the config."""
    opener = _Opener(_http_error(429), _http_error(429), _http_error(429))
    slept = _install(monkeypatch, opener)
    with pytest.raises(UpstoxRateLimitedError) as caught:
        _source(max_rate_limit_retries=2, rate_limit_backoff_seconds=1.0).fetch(
            _instruments_route()
        )
    assert caught.value.outcome is AcquisitionOutcome.RATE_LIMITED
    assert len(opener.calls) == 3
    assert slept == [1.0, 2.0]


def test_a_rate_limit_that_clears_returns_the_retried_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry is real: a 429 followed by a 200 yields the 200's bytes."""
    opener = _Opener(_http_error(429), _Response(b"[]"))
    _install(monkeypatch, opener)
    fetch = _source(max_rate_limit_retries=1, rate_limit_backoff_seconds=1.0).fetch(
        _instruments_route()
    )
    assert fetch.raw_body == b"[]"
    assert len(opener.calls) == 2


def test_a_non_retryable_four_hundred_is_request_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed request is a defect in our own call, not a transient failure."""
    opener = _Opener(_http_error(400))
    _install(monkeypatch, opener)
    with pytest.raises(UpstoxFetchError) as caught:
        _source().fetch(_instruments_route())
    assert caught.value.outcome is AcquisitionOutcome.REQUEST_REJECTED


def test_transport_errors_never_contain_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout message is a log line; a log line must never carry a credential."""
    opener = _Opener()

    def failing_open(request: urllib.request.Request, timeout: float) -> _Response:
        del request, timeout
        raise TimeoutError(f"connect timed out with Bearer {_TOKEN}")

    _install(monkeypatch, opener)
    monkeypatch.setattr(opener, "open", failing_open)
    with pytest.raises(UpstoxFetchError) as caught:
        _source().fetch(_candles_route(), **_CANDLE_PARAMS)
    assert _TOKEN not in str(caught.value)
    assert caught.value.outcome is AcquisitionOutcome.TRANSPORT_ERROR


def test_redact_removes_the_token_from_arbitrary_text() -> None:
    """The token never leaves the source, not even to a caller stripping it."""
    source = _source()
    assert _TOKEN not in source.redact(f"failed with Bearer {_TOKEN} attached")


def test_the_token_is_absent_from_the_config_and_source_repr() -> None:
    """``SecretStr`` is the reason a stray repr in a traceback is not a leak."""
    source = _source()
    assert _TOKEN not in repr(source)
    assert _TOKEN not in repr(_config())


def test_a_response_over_the_compressed_cap_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A body is never truncated: a truncated document parses, and parses wrong."""
    opener = _Opener(_Response(b"x" * 64))
    _install(monkeypatch, opener)
    with pytest.raises(UpstoxFetchError) as caught:
        _source(max_compressed_bytes=16).fetch(_instruments_route())
    assert caught.value.outcome is AcquisitionOutcome.TRANSPORT_ERROR


def test_the_run_request_budget_is_enforced_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One command cannot become an unbounded crawl of a rate-limited vendor."""
    opener = _Opener(_Response(b"[]"), _Response(b"[]"))
    _install(monkeypatch, opener)
    source = _source(max_requests_per_run=1)
    source.fetch(_instruments_route())
    with pytest.raises(UpstoxRunBudgetError):
        source.fetch(_instruments_route())
    assert len(opener.calls) == 1


# --- capture ----------------------------------------------------------------


def test_the_capture_hashes_the_raw_bytes_exactly_as_received(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The raw-body hash is the only restatement detector this vendor allows.

    No response on any surface carries an as-of or version field, so a silent
    restatement is invisible in the payload's own content. The hash must cover
    the bytes before decompression, decoding or validation touches them.
    """
    payload = b"\x1f\x8b\x08\x00not-really-gzip"
    opener = _Opener(_Response(payload, media_type="application/gzip"))
    _install(monkeypatch, opener)
    fetch = _source().fetch(_instruments_route())
    assert fetch.raw_body == payload
    assert fetch.capture.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert fetch.capture.byte_count == len(payload)
    assert fetch.capture.media_type == "application/gzip"


def test_the_capture_stamp_comes_from_the_injected_supplier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``retrieved_at`` is wall-clock and injected, so a run is reproducible."""
    opener = _Opener(_Response(b"[]"))
    _install(monkeypatch, opener)
    assert _source().fetch(_instruments_route()).capture.retrieved_at == _STAMP


def test_the_capture_url_carries_no_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """The token is a header on this vendor, so a recorded URL is safe to keep."""
    opener = _Opener(_Response(b"{}"))
    _install(monkeypatch, opener)
    fetch = _source().fetch(_candles_route(), **_CANDLE_PARAMS)
    assert _TOKEN not in fetch.capture.request_url


def test_the_instrument_key_pipe_is_percent_encoded_in_the_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare pipe in a path is not a legal URL character and must be quoted."""
    opener = _Opener(_Response(b"{}"))
    _install(monkeypatch, opener)
    fetch = _source().fetch(_candles_route(), **_CANDLE_PARAMS)
    assert "%7C" in fetch.capture.request_url
    assert "|" not in fetch.capture.request_url


def test_a_path_parameter_cannot_escape_its_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path templates take values, not path fragments; a slash would rewrite the route."""
    opener = _Opener(_Response(b"{}"))
    _install(monkeypatch, opener)
    escaping = dict(_CANDLE_PARAMS, instrument_key="../../v2/user/profile")
    fetch = _source().fetch(_candles_route(), **escaping)
    assert "/v2/user/profile" not in fetch.capture.request_url
