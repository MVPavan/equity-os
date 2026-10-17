"""Shareholding-pattern acquisition (plan D8): the transport boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from fundamentals.api import onboard_cli
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import (
    SCREENER_SHAREHOLDING,
    UPSTOX_INSTRUMENTS,
    UPSTOX_SHAREHOLDING,
    UPSTOX_STATEMENT,
)
from fundamentals.entity.discovery import Request

_API = "https://api.upstox.com/v2/x"
_TOKEN = "test-token"


class _Response:
    status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, *_: object) -> bytes:
        """An empty body."""
        return b""


class _RecordingOpener:
    """Records the headers of each request it is asked to open."""

    def __init__(self) -> None:
        self.headers: list[dict[str, str]] = []

    def open(self, request: Any, timeout: float) -> Any:
        """Record the request headers and return an empty 200 response."""
        del timeout
        self.headers.append(dict(request.header_items()))
        return _Response()


@pytest.mark.parametrize(
    ("pair", "url", "bearer"),
    [
        (UPSTOX_STATEMENT, _API, True),
        (UPSTOX_SHAREHOLDING, _API, True),
        (UPSTOX_INSTRUMENTS, "https://assets.upstox.com/m/complete.json.gz", False),
        (UPSTOX_SHAREHOLDING, "https://other.example.com/v2/x", False),
        (UPSTOX_SHAREHOLDING, "http://api.upstox.com/v2/x", False),
        (SCREENER_SHAREHOLDING, "https://www.screener.in/company/X/", False),
    ],
)
def test_transport_sends_the_bearer_only_for_routed_surfaces_on_the_api_origin(
    monkeypatch: pytest.MonkeyPatch, pair: tuple[str, str], url: str, bearer: bool
) -> None:
    """The Upstox token goes only to ``UPSTOX_ROUTED`` on ``api.upstox.com``."""
    opener = _RecordingOpener()
    monkeypatch.setattr(onboard_cli.urllib.request, "build_opener", lambda *_: opener)
    monkeypatch.setattr(onboard_cli, "_screener_credentials_from_env", lambda: None)
    monkeypatch.setattr(onboard_cli, "_tijori_credentials_from_env", lambda: None)
    monkeypatch.setattr(
        onboard_cli,
        "_upstox_credentials_from_env",
        lambda: SimpleNamespace(access_token=SecretStr(_TOKEN)),
    )
    request = Request(unit=VerificationUnit.UPSTOX, source_id=pair[0], surface=pair[1], url=url)
    assert onboard_cli.live_transport()(request) == (200, b"")
    assert ("Authorization" in opener.headers[0]) is bearer
