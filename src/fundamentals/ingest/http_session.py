"""Adapter-neutral primitives for polite outbound HTTP.

Three pieces, shared because they carry no adapter semantics: refusing
redirects, holding a minimum spacing between requests, and reading a response
body under a hard byte cap. Extracted from
:mod:`fundamentals.ingest.screener_session` when a seventh reimplementation
came due (bead ``eqos-zfu``).

**What deliberately stays per-adapter.** Origin pinning (different hosts),
terminal-status meaning (a 403 is a Cloudflare browser-signature block on one
host and an authorization failure on another), auth header shape (session
cookie vs bearer token), error taxonomy, and log redaction. Those genuinely
differ; unifying them would invent a shared abstraction over two things that
disagree.
"""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fundamentals.contracts.snapshot import BodyCompleteness, BodyReadIssue

MIN_SPACING_FIELD = "min_spacing_seconds"


class NonBytesResponseError(ValueError):
    """Raised when a response body is not ``bytes``.

    The transport is not what the calling adapter assumes; fail rather than
    guess an encoding.
    """


class ResponseTooLargeError(ValueError):
    """Raised when a response body exceeds its byte cap.

    Never a truncation: a truncated document parses, and a parse of a truncated
    document is silently wrong.
    """


class ReadableResponse(Protocol):
    """Anything exposing ``read(amount)`` — keeps this module off urllib types."""

    def read(self, amount: int, /) -> Any:
        """Read at most ``amount`` bytes."""
        ...


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
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


def read_bounded(response: ReadableResponse, max_bytes: int) -> bytes:
    """Read a response body, refusing anything over ``max_bytes``.

    Reads one byte past the cap so an over-cap body is detected without pulling
    the whole thing into memory.
    """
    payload = response.read(max_bytes + 1)
    if not isinstance(payload, bytes):
        raise NonBytesResponseError(f"response body is {type(payload).__name__}, not bytes")
    if len(payload) > max_bytes:
        raise ResponseTooLargeError(f"response exceeded maximum {max_bytes} bytes")
    return payload


@dataclass(frozen=True)
class BoundedBodyRead:
    """Available evidence, independently of the adapter's HTTP outcome."""

    raw_body: bytes | None
    completeness: BodyCompleteness
    issue: BodyReadIssue | None


def read_bounded_capture(
    response: ReadableResponse,
    max_bytes: int,
    *,
    timeout_seconds: float,
    expected_bytes: int | None = None,
) -> BoundedBodyRead:
    """Retain a capped prefix; require EOF within byte, call and between-read budgets.

    An individual read can outlast the deadline while making progress. This
    does not cancel underlying reads or bound their allocations.
    """
    if max_bytes <= 0 or timeout_seconds <= 0:
        raise ValueError("body and time budgets must be positive")
    prefix = bytearray()
    started = time.monotonic()

    def failed(issue: BodyReadIssue) -> BoundedBodyRead:
        return BoundedBodyRead(
            bytes(prefix) if prefix else None,
            BodyCompleteness.PARTIAL if prefix else BodyCompleteness.ABSENT,
            issue,
        )

    for _ in range(1024):
        if time.monotonic() - started >= timeout_seconds:
            return failed(BodyReadIssue.READ_BUDGET_EXCEEDED)
        try:
            chunk = response.read(min(64 * 1024, max_bytes + 1 - len(prefix)))
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, OSError) as error:
            partial = getattr(error, "partial", b"")
            if not isinstance(partial, bytes):
                return failed(BodyReadIssue.NON_BYTES)
            prefix.extend(memoryview(partial)[: max_bytes - len(prefix)])
            # CPython's chunked reader wraps completed chunks around a failed
            # _safe_read of the next chunk. Only that immediate wrapper is known
            # to expose disjoint contiguous payload segments.
            cause = error.__cause__
            trace = error.__traceback__
            chunk_wrapper = False
            while trace is not None:
                if trace.tb_frame.f_code is http.client.HTTPResponse._read_chunked.__code__:  # type: ignore[attr-defined]
                    chunk_wrapper = True
                trace = trace.tb_next
            if (
                isinstance(error, http.client.IncompleteRead)
                and chunk_wrapper
                and isinstance(cause, http.client.IncompleteRead)
                and cause.__traceback__ is not None
                and cause.__traceback__.tb_next is not None
                and cause.__traceback__.tb_next.tb_frame.f_code
                is http.client.HTTPResponse._safe_read.__code__  # type: ignore[attr-defined]
            ):
                if not isinstance(cause.partial, bytes):
                    return failed(BodyReadIssue.NON_BYTES)
                prefix.extend(memoryview(cause.partial)[: max_bytes - len(prefix)])
            return failed(BodyReadIssue.READ_INTERRUPTED)
        if not isinstance(chunk, bytes):
            return failed(BodyReadIssue.NON_BYTES)
        overflow = len(prefix) + len(chunk) > max_bytes
        prefix.extend(memoryview(chunk)[: max_bytes - len(prefix)])
        if overflow:
            return failed(BodyReadIssue.LIMIT_EXCEEDED)
        if time.monotonic() - started >= timeout_seconds:
            return failed(BodyReadIssue.READ_BUDGET_EXCEEDED)
        if not chunk:
            if expected_bytes is not None and len(prefix) != expected_bytes:
                return failed(BodyReadIssue.READ_INTERRUPTED)
            return BoundedBodyRead(bytes(prefix), BodyCompleteness.COMPLETE, None)
    return failed(BodyReadIssue.READ_BUDGET_EXCEEDED)


class RequestPacer:
    """Hold a minimum spacing between two outbound requests.

    Uses a monotonic clock, so a wall-clock adjustment cannot let a caller skip
    the spacing it agreed to hold.
    """

    def __init__(self, min_spacing_seconds: float) -> None:
        if min_spacing_seconds < 0:
            raise ValueError(f"{MIN_SPACING_FIELD} must not be negative")
        self._min_spacing_seconds = min_spacing_seconds
        self._last_request_at: float | None = None

    def wait_for_slot(self, *, sleep: Callable[[float], None] | None = None) -> None:
        """Block until the configured spacing since the previous request has elapsed.

        ``sleep`` is resolved at call time rather than bound as a default, so a
        test that patches ``time.sleep`` still intercepts the wait. Binding it
        as a default argument would capture the real function at import.
        """
        wait = time.sleep if sleep is None else sleep
        now = time.monotonic()
        if self._last_request_at is not None and self._min_spacing_seconds > 0:
            remaining = self._min_spacing_seconds - (now - self._last_request_at)
            if remaining > 0:
                wait(remaining)
        self._last_request_at = time.monotonic()
