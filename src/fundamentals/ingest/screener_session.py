"""Screener.in subscriber transport — one authenticated company-page fetch.

This is the session-authenticated sibling of
:mod:`fundamentals.ingest.screener_source` (the anonymous, credential-free
derived cross-check adapter), not a replacement for it. It owns the polite
authenticated GET, the per-response authentication / identity / basis gates, and
the retained response bytes. It performs **no financial parsing**.

Operating rules, all of them fail-closed:

* the ``sessionid`` cookie is read only into the outbound header — never logged;
* redirects are refused, never followed (the login redirect and the outbound
  BSE/NSE document links both depend on this);
* requests are spaced by a configured minimum, 429 is retried a bounded number
  of times with exponential backoff and then fails closed, and 403/451 are
  terminal — this adapter never works around a block;
* the response must positively prove it is logged in, prove it is the configured
  company, and prove which basis it carries, before it is returned.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import structlog

from fundamentals.ingest.screener_session_models import (
    COOKIE_HEADER,
    LOCATION_HEADER,
    RATE_LIMITED_STATUS,
    SESSION_COOKIE_NAME,
    TERMINAL_BLOCK_STATUSES,
    USER_AGENT_HEADER,
    Basis,
    BasisTopology,
    IdentityMismatchError,
    ScreenerBlockedError,
    ScreenerCredentials,
    ScreenerCredentialsError,
    ScreenerPageFetch,
    ScreenerPageMetadata,
    ScreenerRateLimitedError,
    ScreenerRedirectError,
    ScreenerSessionConfig,
    ScreenerSessionFetchError,
    assert_pinned_origin,
    company_page_url,
)
from fundamentals.ingest.screener_session_page import read_page_evidence

_LOGGER = structlog.get_logger(__name__)

_FETCH_EVENT = "screener_session_page_fetched"
_RATE_LIMITED_EVENT = "screener_session_rate_limited"
_NO_CREDENTIALS = (
    "screener session cookie required for a subscriber fetch; mint one from an "
    "authenticated browser session and inject it as credentials.session_cookie"
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Turn every HTTP redirect into a terminal response error."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        """Refuse redirects so a login bounce cannot become a plausible page."""
        del request, fp, code, msg, headers, newurl
        return None


class ScreenerSessionSource:
    """Fetches one subscriber company page and proves who and what served it."""

    def __init__(self, config: ScreenerSessionConfig | None = None) -> None:
        self._config = config or ScreenerSessionConfig()
        self._last_request_at: float | None = None

    def fetch_company_page(
        self,
        *,
        symbol: str,
        slug: str,
        basis: Basis,
        expected_company_id: int,
        topology: BasisTopology,
    ) -> ScreenerPageFetch:
        """Fetch one company page on one basis, asserting session, identity, and basis.

        ``topology`` is the configured record of which bases this company
        publishes; the basis rules are applied against it, never inferred from
        the response. Returns the retained bytes with a metadata record whose
        :class:`~fundamentals.ingest.screener_session_models.PageOutcome` states
        whether the requested basis was actually served; every other failure
        mode raises a typed refusal rather than returning a plausible page.
        """
        credentials = self._config.credentials
        if credentials is None:
            raise ScreenerCredentialsError(_NO_CREDENTIALS)
        url = company_page_url(slug, basis)
        status, raw = self._fetch_bytes(url, credentials)
        fetched_at = datetime.now(tz=UTC)

        evidence, outcome = read_page_evidence(
            raw.decode("utf-8", errors="replace"), basis_requested=basis, topology=topology
        )
        if evidence.company_id != expected_company_id:
            raise IdentityMismatchError(
                f"screener page for {symbol} carries company id {evidence.company_id}, "
                f"expected {expected_company_id}"
            )

        metadata = ScreenerPageMetadata(
            symbol=symbol,
            slug=slug,
            source_url=url,
            http_status=status,
            outcome=outcome,
            basis_requested=basis,
            basis_observed=evidence.basis_observed,
            single_basis=evidence.single_basis,
            markers=evidence.markers,
            tables_empty=evidence.tables_empty,
            expected_company_id=expected_company_id,
            expected_warehouse_id=topology.warehouse_id_for(basis),
            company_id_seen=evidence.company_id,
            warehouse_id_seen=evidence.warehouse_id,
            logged_in=evidence.logged_in,
            content_sha256=hashlib.sha256(raw).hexdigest(),
            byte_count=len(raw),
            fetched_at=fetched_at,
        )
        _LOGGER.info(
            _FETCH_EVENT,
            symbol=symbol,
            basis_requested=basis.value,
            basis_observed=(
                None if evidence.basis_observed is None else evidence.basis_observed.value
            ),
            outcome=outcome.value,
            single_basis=evidence.single_basis,
            warehouse_id=evidence.warehouse_id,
            bytes=len(raw),
        )
        return ScreenerPageFetch(raw_body=raw, metadata=metadata)

    def _fetch_bytes(self, url: str, credentials: ScreenerCredentials) -> tuple[int, bytes]:
        """GET one page politely: on-origin, spaced, redirect-refusing, 429-aware, fail-closed.

        The origin is checked before the request object exists, so a URL that is
        not the pinned Screener origin never gets near the session cookie.
        """
        assert_pinned_origin(url)
        request = urllib.request.Request(
            url,
            headers={
                COOKIE_HEADER: (
                    f"{SESSION_COOKIE_NAME}={credentials.session_cookie.get_secret_value()}"
                ),
                USER_AGENT_HEADER: self._config.user_agent,
            },
            method="GET",
        )
        opener = urllib.request.build_opener(_NoRedirectHandler())
        rate_limit: urllib.error.HTTPError | None = None
        for attempt in range(self._config.max_rate_limit_retries + 1):
            self._wait_for_slot()
            try:
                with opener.open(request, timeout=self._config.request_timeout_seconds) as response:
                    status = response.getcode()
                    if status is not None and 300 <= status < 400:
                        raise ScreenerRedirectError(
                            f"screener returned redirect status {status} for {url}"
                        )
                    payload = response.read(self._config.max_response_bytes + 1)
            except urllib.error.HTTPError as error:
                self._refuse_terminal_status(error, url=url)
                rate_limit = error
                if attempt >= self._config.max_rate_limit_retries:
                    break
                backoff = self._config.rate_limit_backoff_seconds * (2**attempt)
                _LOGGER.warning(
                    _RATE_LIMITED_EVENT, url=url, attempt=attempt + 1, backoff_seconds=backoff
                )
                time.sleep(backoff)
                continue
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ScreenerSessionFetchError(
                    f"screener fetch failed for {url}: {type(error).__name__}"
                ) from error
            if not isinstance(payload, bytes):
                raise ScreenerSessionFetchError("screener response body is not bytes")
            if len(payload) > self._config.max_response_bytes:
                raise ScreenerSessionFetchError(
                    f"screener response exceeded maximum {self._config.max_response_bytes} bytes"
                )
            return (200 if status is None else status), payload
        raise ScreenerRateLimitedError(
            f"screener rate-limited {url} after "
            f"{self._config.max_rate_limit_retries + 1} attempts; stopping"
        ) from rate_limit

    @staticmethod
    def _refuse_terminal_status(error: urllib.error.HTTPError, *, url: str) -> None:
        """Raise the typed refusal for any status that is not a retryable 429."""
        if 300 <= error.code < 400:
            location = error.headers.get(LOCATION_HEADER) if error.headers else None
            raise ScreenerRedirectError(
                f"screener redirected {url} to {location!r}; refusing to follow"
            ) from error
        if error.code in TERMINAL_BLOCK_STATUSES:
            raise ScreenerBlockedError(
                f"screener returned terminal status {error.code} for {url}"
            ) from error
        if error.code != RATE_LIMITED_STATUS:
            raise ScreenerSessionFetchError(
                f"screener returned HTTP {error.code} for {url}"
            ) from error

    def _wait_for_slot(self) -> None:
        """Hold the configured minimum spacing between two outbound requests."""
        spacing = self._config.min_request_spacing_seconds
        now = time.monotonic()
        if self._last_request_at is not None and spacing > 0:
            remaining = spacing - (now - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()
