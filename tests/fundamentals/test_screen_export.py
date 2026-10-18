"""D7 screen export, Task 3: each vendor's export of one saved screen, from recorded SYNTHETIC
responses. Every way a response can fail to be the complete export of exactly one saved screen
refuses before an export exists; every attempt to either vendor is at least 2 s after the last."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr
from screen_export_support import (
    CSV_TYPE,
    EXPORT_PATH,
    HTML_TYPE,
    JSON_TYPE,
    LISTING_PATH,
    PAGE_COOKIE,
    RESULTS_PATH,
    SCREEN_PATH,
    FakeClock,
    Reply,
    default_replies,
    fixture,
    serve,
)

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from fundamentals.ingest.screen_export import (
    ScreenExportError,
    ScreenVendor,
    VendorExport,
    export_screener,
    export_tijori,
    load_screen_config,
    screen_sources,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import ScreenerCredentials
from fundamentals.ingest.screener_watchlist_models import WatchlistExportError
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriFetchError, TijoriSource

CONFIG = Path(__file__).parents[2] / "config" / "screens.yaml"
SYMBOLS = ["ETERNAL", "POLYCAB", "TITAN", "THERMAX", "CGPOWER"]
Replies = dict[tuple[str, str], list[Reply]]


def _sources() -> tuple[ScreenerSessionSource, TijoriSource]:
    return screen_sources(
        ScreenerCredentials(session_cookie=SecretStr("screener-cookie")),
        TijoriCredentials(session_cookie=SecretStr("tijori-cookie")),
    )


def _screener(monkeypatch: pytest.MonkeyPatch, replies: Replies | None = None) -> VendorExport:
    serve(monkeypatch, replies)
    screener, _ = screen_sources(ScreenerCredentials(session_cookie=SecretStr("c")), None)
    return export_screener(screener, "d7-stage4")


def _tijori(
    monkeypatch: pytest.MonkeyPatch, replies: Replies | None = None, name: str = "d7-stage4"
) -> VendorExport:
    serve(monkeypatch, replies)
    _, tijori = screen_sources(None, TijoriCredentials(session_cookie=SecretStr("c")))
    return export_tijori(tijori, name)


def _with(key: tuple[str, str], *replies: Reply) -> Replies:
    """The happy replies with ``key`` answered by ``replies`` instead."""
    return default_replies() | {key: list(replies)}


def _edited(name: str, old: str, new: str) -> bytes:
    body = fixture(name).decode()
    assert old in body
    return body.replace(old, new).encode()


def _listing(**changes: object) -> bytes:
    listing = json.loads(fixture("tijori-listing.json")) | changes
    return json.dumps(listing).encode()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake.monotonic)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    return fake


def test_screener_export_is_the_csv_of_the_one_matching_saved_screen(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """Three requests: the owner's listing, the screen page (the definition capture) and its
    export form; rows are the CSV verbatim, keyed by its header."""
    web = serve(monkeypatch)
    screener, _ = _sources()
    export = export_screener(screener, "d7-stage4")
    assert [(method, urlsplit(url).path) for method, url, _ in web.requests] == [
        ("GET", "/explore/"),
        ("GET", SCREEN_PATH),
        ("POST", EXPORT_PATH),
    ]
    assert export.vendor is ScreenVendor.SCREENER
    assert export.screen_text == "screener:Market Capitalization > 20000"
    assert export.definition.body == fixture("screen.html")
    assert export.results.body == fixture("screener.csv")
    assert [row["NSE Code"] for row in export.rows] == SYMBOLS
    assert export.rows[0]["ISIN Code"] == "INE758T01015"


def test_tijori_export_replays_the_saved_query_text(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """Two requests: the owner listing (the definition capture) and ``advanced_search`` with the
    stored query; the definition text is the stored query as canonical JSON."""
    web = serve(monkeypatch)
    _, tijori = _sources()
    export = export_tijori(tijori, "d7-stage4")
    assert [urlsplit(url).path for _, url, _ in web.requests] == [LISTING_PATH, RESULTS_PATH]
    sent = parse_qs(urlsplit(web.requests[1][1]).query)
    assert sent["financial"] == ["Market Capitalization > 20000"]
    assert (sent["query_id"], sent["is_checked"]) == (["901"], ["False"])
    assert export.screen_text == (
        'tijori:{"alt_query":"","extra_cols":"","financial_query":"Market Capitalization > 20000"}'
    )
    assert export.definition.body == fixture("tijori-listing.json")
    assert [row["nse symbol"] for row in export.rows] == SYMBOLS
    assert (export.rows[0]["scripcode"], export.rows[0]["slug"]) == ("543320", "zomato-ltd")


SCREENER_REFUSALS: dict[str, Callable[[], Replies]] = {
    "slug absent": lambda: _with(
        ("GET", "/explore/"), (200, _edited("explore.html", "d7-stage4", "renamed"), HTML_TYPE)
    ),
    "slug twice": lambda: _with(
        ("GET", "/explore/"),
        (200, _edited("explore.html", "other-screen", "d7-stage4"), HTML_TYPE),
    ),
    "definition absent": lambda: _with(
        ("GET", SCREEN_PATH), (200, _edited("screen.html", 'name="query"', 'name="q"'), PAGE_COOKIE)
    ),
    "definition twice": lambda: _with(
        ("GET", SCREEN_PATH),
        (
            200,
            _edited(
                "screen.html",
                "</form>\n</body>",
                '<textarea name="query">x</textarea></form>\n</body>',
            ),
            PAGE_COOKIE,
        ),
    ),  # fmt: skip
    "page count differs": lambda: _with(
        ("GET", SCREEN_PATH), (200, _edited("screen.html", "5 results", "6 results"), PAGE_COOKIE)
    ),
    "page not 200": lambda: _with(("GET", SCREEN_PATH), (203, fixture("screen.html"), PAGE_COOKIE)),
    "no ISIN column": lambda: _with(
        ("POST", EXPORT_PATH), (200, _edited("screener.csv", "ISIN Code", "ISIN"), CSV_TYPE)
    ),
    "ragged csv": lambda: _with(
        ("POST", EXPORT_PATH), (200, _edited("screener.csv", ",ETERNAL,", ",ETERNAL,,"), CSV_TYPE)
    ),
    "csv not 200": lambda: _with(("POST", EXPORT_PATH), (203, fixture("screener.csv"), CSV_TYPE)),
    "csv as html": lambda: _with(("POST", EXPORT_PATH), (200, fixture("screener.csv"), HTML_TYPE)),
}


@pytest.mark.parametrize("case", SCREENER_REFUSALS)
def test_screener_refusals(case: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Each defect refuses; none returns a partial export."""
    with pytest.raises((ScreenExportError, WatchlistExportError)):
        _screener(monkeypatch, SCREENER_REFUSALS[case]())


TIJORI_REFUSALS: dict[str, Callable[[], Replies]] = {
    "name twice": lambda: _with(
        ("GET", LISTING_PATH),
        (200, _edited("tijori-listing.json", "other-query", "d7-stage4"), JSON_TYPE),
    ),
    "listing has next": lambda: _with(
        ("GET", LISTING_PATH),
        (200, _listing(next="https://example.invalid/?offset=100"), JSON_TYPE),
    ),
    "listing count differs": lambda: _with(
        ("GET", LISTING_PATH), (200, _listing(count=3), JSON_TYPE)
    ),
    "results 203": lambda: _with(
        ("GET", RESULTS_PATH), (203, fixture("tijori-results.json"), JSON_TYPE)
    ),
    "results as html": lambda: _with(
        ("GET", RESULTS_PATH), (200, fixture("tijori-results.json"), HTML_TYPE)
    ),
    "total differs": lambda: _with(
        ("GET", RESULTS_PATH),
        (
            200,
            _edited("tijori-results.json", '"total_results": 5', '"total_results": 6'),
            JSON_TYPE,
        ),
    ),
}


@pytest.mark.parametrize("case", TIJORI_REFUSALS)
def test_tijori_refusals(case: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Each defect refuses; none returns a partial export."""
    with pytest.raises((ScreenExportError, TijoriFetchError)):
        _tijori(monkeypatch, TIJORI_REFUSALS[case]())


def test_tijori_name_absent_refuses(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """A saved query the owner's listing does not carry is never guessed."""
    with pytest.raises(ScreenExportError, match="not exactly one"):
        _tijori(monkeypatch, name="d7-stage5")


def test_every_attempt_is_two_seconds_apart_and_tijori_is_never_retried(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """A Screener 429 is retried, still 2 s after the previous attempt; a Tijori 503 is attempted
    once and refuses."""
    web = serve(
        monkeypatch,
        _with(
            ("GET", SCREEN_PATH), (429, b"", HTML_TYPE), (200, fixture("screen.html"), PAGE_COOKIE)
        )
        | {("GET", RESULTS_PATH): [(503, b"", JSON_TYPE)]},
    )
    screener, tijori = _sources()
    export_screener(screener, "d7-stage4")
    with pytest.raises(TijoriFetchError):
        export_tijori(tijori, "d7-stage4")
    paths = [urlsplit(url).path for _, url, _ in web.requests]
    assert paths == ["/explore/", SCREEN_PATH, SCREEN_PATH, EXPORT_PATH, LISTING_PATH, RESULTS_PATH]
    for vendor in (web.requests[:4], web.requests[4:]):
        times = [at for _, _, at in vendor]
        assert all(later - earlier >= 2.0 for earlier, later in pairwise(times))


def test_screen_config_loads_and_refuses_a_repeated_name(tmp_path: Path) -> None:
    """The committed config names both vendors per screen; a repeated name refuses."""
    screens = load_screen_config(CONFIG)
    assert all(screen.screener and screen.tijori for screen in screens.values())
    repeated = tmp_path / "screens.yaml"
    repeated.write_text(
        "- {name: a, screener: x, tijori: y}\n- {name: a, screener: z, tijori: w}\n"
    )
    with pytest.raises(ScreenExportError):
        load_screen_config(repeated)


@pytest.mark.skipif(
    os.environ.get("RUN_SCREEN_EXPORT_LIVE") != "1", reason="live screen export is opt-in"
)
def test_live_export_passes_every_count_check(tmp_path: Path) -> None:
    """Opt-in (RUN_SCREEN_EXPORT_LIVE=1, cookies from scripts/credentials.sh): the first configured
    screen exports from both vendors; the bodies go to ``tmp_path`` only."""
    screen = next(iter(load_screen_config(CONFIG).values()))
    screener, tijori = screen_sources(
        _screener_credentials_from_env(), _tijori_credentials_from_env()
    )
    for export in (
        export_screener(screener, screen.screener),
        export_tijori(tijori, screen.tijori),
    ):
        (tmp_path / f"{export.vendor}.results").write_bytes(export.results.body)
        assert export.rows
