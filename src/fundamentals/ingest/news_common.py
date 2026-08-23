"""Shared bounded-retry policy for the news source adapters."""

from __future__ import annotations

import time
from collections.abc import Callable

import structlog

_LOGGER = structlog.get_logger(__name__)
_TERMINAL_HTTP_CODES = frozenset({401, 403, 407, 451})


class NewsSourceError(Exception):
    """A source pass failed without producing trustworthy occurrences."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Capture optional typed HTTP status without deriving it from message text."""
        super().__init__(message)
        self.status_code = status_code


class NewsSourceHardBlockError(NewsSourceError):
    """A terminal provider block that must not be retried."""


class NewsSourceSchemaError(NewsSourceError):
    """A source shape changed and needs remediation, never retry backoff."""


def reject_terminal_http_status(status_code: int, *, description: str) -> None:
    """Raise a typed hard block for explicit provider policy status codes."""
    if status_code in _TERMINAL_HTTP_CODES:
        raise NewsSourceHardBlockError(
            f"{description} hit terminal HTTP status {status_code}; not retrying"
        )


def _is_terminal_error(error: Exception) -> bool:
    """Classify explicit auth and policy blocks from typed HTTP status metadata."""
    response = getattr(error, "response", None)
    code = (
        getattr(error, "status_code", None)
        or getattr(error, "code", None)
        or getattr(error, "status", None)
        or getattr(response, "status_code", None)
    )
    if isinstance(code, int) and code in _TERMINAL_HTTP_CODES:
        return True
    return False


def run_with_retries[Result](
    description: str,
    action: Callable[[], Result],
    *,
    max_retries: int,
    retry_backoff_seconds: float,
) -> Result:
    """Run one external operation with bounded transient retries."""
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return action()
        except NewsSourceHardBlockError:
            raise
        except NewsSourceSchemaError:
            raise
        except (AttributeError, KeyError, TypeError):
            raise
        except (NewsSourceError, OSError, TimeoutError) as error:
            if _is_terminal_error(error):
                raise NewsSourceHardBlockError(
                    f"{description} hit a terminal block; not retrying: {error}"
                ) from error
            last_error = error
            _LOGGER.warning(
                "news_source_retry",
                source_action=description,
                attempt=attempt + 1,
                error=str(error),
            )
            if attempt + 1 < max_retries:
                time.sleep(retry_backoff_seconds * (attempt + 1))
    raise NewsSourceError(
        f"{description} failed after {max_retries} attempts: {last_error}"
    ) from last_error
