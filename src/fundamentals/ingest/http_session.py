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

import time
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

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
