"""The shared polite-fetch primitives, tested away from any one adapter.

These three pieces were the seventh candidate for reimplementation when the
Upstox lane arrived (eqos-zfu). They are extracted precisely because they carry
no adapter semantics: no origin pinning, no terminal-status meaning, no auth
header shape, no error taxonomy. Those genuinely differ between adapters and
stay per-adapter.
"""

from __future__ import annotations

import time

import pytest

from fundamentals.ingest.http_session import (
    NonBytesResponseError,
    NoRedirectHandler,
    RequestPacer,
    ResponseTooLargeError,
    read_bounded,
)


class _Response:
    """Minimal stand-in for an ``http.client.HTTPResponse`` body reader."""

    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.requested: int | None = None

    def read(self, amount: int) -> object:
        self.requested = amount
        return self._payload[:amount] if isinstance(self._payload, bytes) else self._payload


# --- NoRedirectHandler ---------------------------------------------------------


def test_a_redirect_is_never_followed() -> None:
    """Returning None makes urllib raise instead of fetching the redirect target.

    A login bounce must not be able to arrive as a plausible 200.
    """
    handler = NoRedirectHandler()
    assert (
        handler.redirect_request(
            request=None, fp=None, code=302, msg="Found", headers=None, newurl="https://elsewhere"
        )
        is None
    )


# --- read_bounded --------------------------------------------------------------


def test_read_bounded_asks_for_one_byte_more_than_the_cap() -> None:
    """The extra byte is how an over-cap body is detected without reading it all."""
    response = _Response(b"x" * 10)
    read_bounded(response, 10)
    assert response.requested == 11


def test_a_body_at_the_cap_is_returned() -> None:
    response = _Response(b"x" * 10)
    assert read_bounded(response, 10) == b"x" * 10


def test_a_body_over_the_cap_is_refused() -> None:
    """Over-cap is an error, never a silent truncation — a truncated body parses."""
    response = _Response(b"x" * 11)
    with pytest.raises(ResponseTooLargeError):
        read_bounded(response, 10)


def test_a_non_bytes_body_is_refused() -> None:
    """A str body means the transport is not what this code assumes."""
    response = _Response("not bytes")
    with pytest.raises(NonBytesResponseError):
        read_bounded(response, 10)


# --- RequestPacer --------------------------------------------------------------


def test_the_first_request_never_waits() -> None:
    pacer = RequestPacer(min_spacing_seconds=5.0)
    slept: list[float] = []
    pacer.wait_for_slot(sleep=slept.append)
    assert slept == []


def test_a_second_request_waits_out_the_remaining_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spacing is held against a monotonic clock, so a wall-clock change cannot skip it."""
    clock = iter([100.0, 100.0, 102.0, 105.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    pacer = RequestPacer(min_spacing_seconds=5.0)
    slept: list[float] = []
    pacer.wait_for_slot(sleep=slept.append)
    pacer.wait_for_slot(sleep=slept.append)
    assert slept == [pytest.approx(3.0)]


def test_a_request_after_the_spacing_has_elapsed_does_not_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter([100.0, 100.0, 110.0, 110.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    pacer = RequestPacer(min_spacing_seconds=5.0)
    slept: list[float] = []
    pacer.wait_for_slot(sleep=slept.append)
    pacer.wait_for_slot(sleep=slept.append)
    assert slept == []


def test_zero_spacing_disables_pacing() -> None:
    pacer = RequestPacer(min_spacing_seconds=0.0)
    slept: list[float] = []
    pacer.wait_for_slot(sleep=slept.append)
    pacer.wait_for_slot(sleep=slept.append)
    assert slept == []


def test_a_negative_spacing_is_refused() -> None:
    """Spacing is a floor, not an offset; a negative floor is a configuration error."""
    with pytest.raises(ValueError, match="min_spacing_seconds"):
        RequestPacer(min_spacing_seconds=-1.0)


def test_patching_time_sleep_still_intercepts_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: ``sleep`` must resolve at call time, not bind as a default.

    Binding ``time.sleep`` as a default argument captures the real function at
    import, so every adapter test that patches ``time.sleep`` silently sleeps
    for real instead. That happened once during the extraction (eqos-zfu) and
    cost 1.5 s of wall clock in a unit test before it was caught.
    """
    clock = iter([100.0, 100.0, 102.0, 105.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", slept.append)

    pacer = RequestPacer(min_spacing_seconds=5.0)
    pacer.wait_for_slot()
    pacer.wait_for_slot()

    assert slept == [pytest.approx(3.0)]


def test_the_pacer_carries_no_adapter_semantics() -> None:
    """Guard against the extraction drifting back into a shared abstraction.

    Origin pinning, terminal statuses, auth headers and error taxonomy differ
    between adapters; unifying them would invent agreement that does not exist.
    """
    forbidden = {"origin", "host", "status", "token", "cookie", "header", "auth"}
    surface: set[str] = set()
    for name in dir(RequestPacer):
        if not name.startswith("__"):
            surface.add(name.lower())
    assert not any(word in name for name in surface for word in forbidden)


def test_read_bounded_accepts_any_object_exposing_read() -> None:
    """The helper must not depend on urllib types, or adapters cannot share it."""

    class _Duck:
        def read(self, amount: int) -> bytes:
            del amount
            return b"ok"

    assert read_bounded(_Duck(), 10) == b"ok"
