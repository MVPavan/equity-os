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
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog

from fundamentals.ingest.screener_session_models import (
    COOKIE_HEADER,
    LOCATION_HEADER,
    RATE_LIMITED_STATUS,
    SCREENER_ORIGIN,
    SESSION_COOKIE_NAME,
    TERMINAL_BLOCK_STATUSES,
    USER_AGENT_HEADER,
    XHR_HEADER,
    XHR_HEADER_VALUE,
    Basis,
    BasisTopology,
    IdentityMismatchError,
    ScreenerBlockedError,
    ScreenerCredentials,
    ScreenerCredentialsError,
    ScreenerDocumentFetch,
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
_GET_METHOD = "GET"
_POST_METHOD = "POST"
SET_COOKIE_HEADER = "Set-Cookie"
CONTENT_TYPE_HEADER = "Content-Type"
CONTENT_DISPOSITION_HEADER = "Content-Disposition"
REFERER_HEADER = "Referer"
ORIGIN_HEADER = "Origin"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
_PRIVATE_QUERY_PARAMETER = "query"
_REDACTED_PRIVATE_QUERY = "[redacted]"
_REDACTED_SECRET = "[redacted-secret]"
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


def _redact_private_query(url: str) -> str:
    """Keep a screen selector out of transport diagnostics while retaining its route."""
    parts = urlsplit(url)
    query = urlencode(
        tuple(
            (name, _REDACTED_PRIVATE_QUERY if name == _PRIVATE_QUERY_PARAMETER else value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
        )
    )
    return urlunsplit(parts._replace(query=query))


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

    def fetch_schedule(self, *, url: str) -> ScreenerDocumentFetch:
        """Fetch one on-origin schedules document through the same polite transport.

        Deliberately assertion-free. A schedules response is a bare
        ``{sub_row: {period: value}}`` map: it names no company and declares no
        basis, so there is nothing here to assert against and pretending
        otherwise would manufacture confidence. Its basis comes from the URL —
        which the caller builds through
        :func:`~fundamentals.ingest.screener_financials_models.schedule_url`,
        the one place that knows the API selects basis by the *presence* of the
        ``consolidated`` key — and is proven afterwards by reconciling the body
        against the page row it expands.

        Kept as a named entry point for Slice 1 while delegating to
        :meth:`fetch_document`, which is the same transport for every on-origin
        sub-document — including its ``X-Requested-With`` header, which is what
        the browser sends when it expands a schedule row.
        """
        return self.fetch_document(url=url)

    def fetch_document(self, *, url: str) -> ScreenerDocumentFetch:
        """Fetch one on-origin sub-document through the same polite transport.

        Assertion-free by design, and for a stronger reason than the schedules
        API alone: a segments fragment, a related-party modal, a corporate-
        actions modal and a quick-ratios list carry no company name, no identity
        element and no basis marker at all. There is nothing on them to check,
        so this method returns the bytes, the URL that is their only binding,
        and the hash that ties an artifact to them — and leaves every question
        of meaning to the reader that asked for them.

        It shares this instance's opener, spacing, and 429 budget on purpose: a
        company's page plus its fifteen schedules, or plus its eighteen Slice 2
        sub-documents, is well inside a source observed to rate-limit at ~40, so
        they must be paced as one conversation rather than by a second,
        independently polite fetcher.

        Every request here carries ``X-Requested-With: XMLHttpRequest``. That is
        not cosmetic: Screener answers ``/company/actions/<id>/`` with a 302 to
        the company page without it, which this adapter refuses to follow, so
        the header is the difference between a modal body and a failed part.
        """
        return self._document_fetch(url, xhr=True)

    def fetch_screen_page(self, *, url: str) -> ScreenerDocumentFetch:
        """Fetch a raw-screen navigation through the shared subscriber transport."""
        return self._document_fetch(url, xhr=False)

    def fetch_navigation(self, *, url: str) -> tuple[ScreenerDocumentFetch, tuple[str, ...]]:
        """Fetch one navigation page and return its bytes beside the cookies it set.

        The ``Set-Cookie`` values are returned as separate strings, never
        collapsed into one, because a page that sets several cookies would
        otherwise lose all but the first — and on the watchlist page the
        ``csrftoken`` is not the first. Only the caller that asked for them ever
        sees them; nothing here logs or retains a cookie value.
        """
        credentials = self._require_credentials()
        status, raw, headers = self._request_bytes(
            url, method=_GET_METHOD, headers=self._session_headers(credentials), data=None
        )
        return self._retained(raw, url=url, status=status), tuple(
            headers.get_all(SET_COOKIE_HEADER) or ()
        )

    def post_form(
        self,
        *,
        url: str,
        fields: Mapping[str, str],
        referer: str,
        cookies: Mapping[str, str],
    ) -> tuple[ScreenerDocumentFetch, str | None, str | None]:
        """POST one page-embedded form and return its bytes and two content headers.

        ``cookies`` is the effective cookie state the authorising GET produced.
        It is serialised into the **one** ``Cookie`` header this transport
        already sets, never handed to an :class:`urllib.request.HTTPCookieProcessor`:
        CPython's cookie jar adds nothing when a request already carries a
        ``Cookie`` header, so a jar here would silently drop the CSRF cookie and
        the site's resulting 403 would read as a block on the account.

        Only the two headers that prove what the response is are read back; every
        other response header is neither retained nor logged.
        """
        credentials = self._require_credentials()
        headers = self._session_headers(credentials, extra_cookies=cookies)
        headers[CONTENT_TYPE_HEADER] = FORM_CONTENT_TYPE
        headers[REFERER_HEADER] = referer
        headers[ORIGIN_HEADER] = SCREENER_ORIGIN
        status, raw, response_headers = self._request_bytes(
            url,
            method=_POST_METHOD,
            headers=headers,
            data=urlencode(tuple(fields.items())).encode("utf-8"),
        )
        return (
            self._retained(raw, url=url, status=status),
            response_headers.get(CONTENT_TYPE_HEADER),
            response_headers.get(CONTENT_DISPOSITION_HEADER),
        )

    def _document_fetch(self, url: str, *, xhr: bool) -> ScreenerDocumentFetch:
        """Fetch one document and attach byte-level retention metadata."""
        credentials = self._require_credentials()
        status, raw = self._fetch_bytes(url, credentials, xhr=xhr)
        return self._retained(raw, url=url, status=status)

    def _require_credentials(self) -> ScreenerCredentials:
        """Return the injected subscriber credentials, or refuse before any request."""
        credentials = self._config.credentials
        if credentials is None:
            raise ScreenerCredentialsError(_NO_CREDENTIALS)
        return credentials

    def redact(self, text: str, *, extra: Iterable[str] = ()) -> str:
        """Return ``text`` with this source's session cookie and any named secret removed.

        The session cookie never leaves this object, not even to a caller that
        wants to strip it from a message: the caller hands the text in and gets
        a safe one back. ``extra`` is for the secrets the caller minted or
        received itself, such as a page's CSRF token.
        """
        credentials = self._config.credentials
        secrets = list(extra)
        if credentials is not None:
            secrets.append(credentials.session_cookie.get_secret_value())
        for secret in secrets:
            if secret:
                text = text.replace(secret, _REDACTED_SECRET)
        return text

    def _session_headers(
        self, credentials: ScreenerCredentials, *, extra_cookies: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Build the outbound headers, serialising every cookie into one ``Cookie`` header.

        A page-supplied cookie can never displace the injected session cookie:
        the override is removed here rather than merely being unreached, so no
        future caller can hand this transport a ``sessionid`` it did not mint.
        """
        cookies = {SESSION_COOKIE_NAME: credentials.session_cookie.get_secret_value()}
        cookies.update(
            {
                name: value
                for name, value in (extra_cookies or {}).items()
                if name != SESSION_COOKIE_NAME
            }
        )
        return {
            COOKIE_HEADER: "; ".join(f"{name}={value}" for name, value in cookies.items()),
            USER_AGENT_HEADER: self._config.user_agent,
        }

    @staticmethod
    def _retained(raw: bytes, *, url: str, status: int) -> ScreenerDocumentFetch:
        """Wrap one response body in the record that ties an artifact to those bytes."""
        return ScreenerDocumentFetch(
            raw_body=raw,
            source_url=url,
            http_status=status,
            content_sha256=hashlib.sha256(raw).hexdigest(),
            byte_count=len(raw),
            fetched_at=datetime.now(tz=UTC),
        )

    def _fetch_bytes(
        self, source_url: str, credentials: ScreenerCredentials, *, xhr: bool = False
    ) -> tuple[int, bytes]:
        """GET one page politely through the shared transport body.

        ``xhr`` marks a sub-document rather than a navigation. It is a parameter
        rather than a property of the URL because the same host serves both, and
        the two must be told apart by what the browser would have done.
        """
        headers = self._session_headers(credentials)
        if xhr:
            headers[XHR_HEADER] = XHR_HEADER_VALUE
        status, payload, _ = self._request_bytes(
            source_url, method=_GET_METHOD, headers=headers, data=None
        )
        return status, payload

    def _request_bytes(
        self, source_url: str, *, method: str, headers: dict[str, str], data: bytes | None
    ) -> tuple[int, bytes, Any]:
        """Make one polite request: on-origin, spaced, redirect-refusing, 429-aware, fail-closed.

        The single implementation of politeness for this adapter. It takes the
        URL rather than a built request precisely so the origin gate stays here:
        a helper handed a :class:`urllib.request.Request` would move that check
        into every builder, and the session cookie must never be attached to a
        URL this adapter did not pin.

        The opener is built per request rather than cached on the instance, so a
        test seam that pins :func:`urllib.request.build_opener` covers every
        request this adapter can make.
        """
        url = _redact_private_query(source_url)
        assert_pinned_origin(url)
        request = urllib.request.Request(source_url, data=data, headers=headers, method=method)
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
                    response_headers = response.headers
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
            return (200 if status is None else status), payload, response_headers
        raise ScreenerRateLimitedError(
            f"screener rate-limited {url} after "
            f"{self._config.max_rate_limit_retries + 1} attempts; stopping"
        ) from rate_limit

    @staticmethod
    def _refuse_terminal_status(error: urllib.error.HTTPError, *, url: str) -> None:
        """Raise the typed refusal for any status that is not a retryable 429."""
        if 300 <= error.code < 400:
            location_raw = error.headers.get(LOCATION_HEADER) if error.headers else None
            location = None if location_raw is None else _redact_private_query(location_raw)
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
