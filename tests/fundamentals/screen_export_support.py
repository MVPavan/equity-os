"""A recorded-response stand-in for ``urllib.request.build_opener`` serving the SYNTHETIC
screen-export fixtures (both vendors), plus a fake monotonic clock. No socket is opened."""

from __future__ import annotations

import io
import time
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from fundamentals.ingest.tijori_source import DEFAULT_BASE_URL

FIXTURES = Path(__file__).parent / "fixtures" / "screen_export"
SCREEN_PATH = "/screen/raw/"
EXPORT_PATH = "/api/export/screen/"
RESULTS_PATH = "/api/filter_queries/advanced_search/"
CSV_TYPE = {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=d7.csv"}
JSON_TYPE = {"Content-Type": "application/json"}
HTML_TYPE = {"Content-Type": "text/html; charset=utf-8"}
PAGE_COOKIE = {"Content-Type": "text/html", "Set-Cookie": "csrftoken=cookie-token; Path=/"}
TIJORI_HOST = urlsplit(DEFAULT_BASE_URL).netloc

Reply = tuple[int, bytes, dict[str, str]]


def fixture(name: str) -> bytes:
    """One committed SYNTHETIC fixture's bytes."""
    return (FIXTURES / name).read_bytes()


def default_replies() -> dict[tuple[str, str], list[Reply]]:
    """Every request of one happy export, keyed by (method, path)."""
    return {
        ("GET", SCREEN_PATH): [(200, fixture("screen.html"), PAGE_COOKIE)],
        ("POST", EXPORT_PATH): [(200, fixture("screener.csv"), CSV_TYPE)],
        ("GET", RESULTS_PATH): [(200, fixture("tijori-results.json"), JSON_TYPE)],
    }


class _Response:
    """A minimal ``http.client.HTTPResponse`` stand-in."""

    def __init__(self, status: int, body: bytes, headers: Message) -> None:
        self._status, self._body, self.headers = status, io.BytesIO(body), headers

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def getcode(self) -> int:
        return self._status

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class FakeWeb:
    """Serves queued replies by (method, path); the last reply of a queue repeats. Records each
    attempt as (method, url, monotonic time)."""

    def __init__(self, replies: dict[tuple[str, str], list[Reply]]) -> None:
        self.replies = replies
        self.requests: list[tuple[str, str, float]] = []

    def build_opener(self, *handlers: Any) -> FakeWeb:
        return self

    def open(self, request: urllib.request.Request, timeout: float | None = None) -> _Response:
        url, method = request.full_url, request.get_method()
        self.requests.append((method, url, time.monotonic()))
        queue = self.replies[(method, urlsplit(url).path)]
        status, body, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        message = Message()
        for name, value in headers.items():
            message[name] = value
        if status >= 400:
            raise urllib.error.HTTPError(url, status, "fake", message, io.BytesIO(body))
        return _Response(status, body, message)


class FakeClock:
    """``time.monotonic`` that only ``time.sleep`` advances."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def serve(
    monkeypatch: pytest.MonkeyPatch, replies: dict[tuple[str, str], list[Reply]] | None = None
) -> FakeWeb:
    """Route every opener this process builds to ``replies`` (default: one happy export)."""
    web = FakeWeb(default_replies() if replies is None else replies)
    monkeypatch.setattr(urllib.request, "build_opener", web.build_opener)
    return web
