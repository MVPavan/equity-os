"""D7 screen export, Task 3 (direct-query revision): each vendor's run of one configured formula,
from recorded SYNTHETIC responses. Every way a response can fail to be the complete export of
exactly that formula refuses before an export exists; every attempt to either vendor is at least
2 s after the last."""

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
from fundamentals.ingest.screener_session_models import ScreenerCredentials, ScreenerSessionError
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriFetchError, TijoriSource

CONFIG = Path(__file__).parents[2] / "config" / "screens.yaml"
FORMULA = "Market Capitalization > 20000"
SYMBOLS = ["ETERNAL", "POLYCAB", "TITAN", "THERMAX", "CGPOWER"]
ACTION = "/api/export/screen/?query=Market+Capitalization+%3E+20000&amp;url_name=raw_query"
ECHO = "Market Capitalization &gt; 20000</textarea>"
Replies = dict[tuple[str, str], list[Reply]]


def _sources() -> tuple[ScreenerSessionSource, TijoriSource]:
    return screen_sources(
        ScreenerCredentials(session_cookie=SecretStr("c")),
        TijoriCredentials(session_cookie=SecretStr("c")),
    )


def _screener(
    monkeypatch: pytest.MonkeyPatch, replies: Replies | None = None, formula: str = FORMULA
) -> VendorExport:
    serve(monkeypatch, replies)
    return export_screener(_sources()[0], formula)


def _tijori(
    monkeypatch: pytest.MonkeyPatch, replies: Replies | None = None, formula: str = FORMULA
) -> VendorExport:
    serve(monkeypatch, replies)
    return export_tijori(_sources()[1], formula)


def _with(key: tuple[str, str], *replies: Reply) -> Replies:
    """The happy replies with ``key`` answered by ``replies`` instead."""
    return default_replies() | {key: list(replies)}


def _page(old: str, new: str) -> Replies:
    """The happy replies with ``old`` replaced by ``new`` in the raw-query page."""
    body = fixture("screen.html").decode()
    assert old in body
    return _with(("GET", SCREEN_PATH), (200, body.replace(old, new).encode(), PAGE_COOKIE))


def _csv(old: str, new: str) -> Replies:
    body = fixture("screener.csv").decode()
    assert old in body
    return _with(("POST", EXPORT_PATH), (200, body.replace(old, new).encode(), CSV_TYPE))


def _results(drop: str = "", **changes: object) -> Replies:
    """The happy replies with Tijori's results JSON changed and key ``drop`` removed."""
    payload = json.loads(fixture("tijori-results.json")) | changes
    payload.pop(drop, None)
    return _with(("GET", RESULTS_PATH), (200, json.dumps(payload).encode(), JSON_TYPE))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake.monotonic)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    return fake


def test_screener_export_is_the_csv_of_the_formula(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """Two requests: the raw-query page for the formula (``query`` its only parameter; the
    definition capture) and its export form; rows are the CSV verbatim, keyed by its header."""
    web = serve(monkeypatch)
    export = export_screener(_sources()[0], FORMULA)
    assert [(method, urlsplit(url).path) for method, url, _ in web.requests] == [
        ("GET", SCREEN_PATH),
        ("POST", EXPORT_PATH),
    ]
    assert parse_qs(urlsplit(web.requests[0][1]).query) == {"query": [FORMULA]}
    assert export.vendor is ScreenVendor.SCREENER
    assert export.screen_text == f"screener:{FORMULA}"
    assert export.definition.body == fixture("screen.html")
    assert export.results.body == fixture("screener.csv")
    assert [row["NSE Code"] for row in export.rows] == SYMBOLS
    assert export.rows[0]["ISIN Code"] == "INE758T01015"


def test_tijori_export_is_one_advanced_search_echoing_the_formula(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """One request carrying the formula and the fixed flags only; the results capture is also the
    definition capture."""
    web = serve(monkeypatch)
    export = export_tijori(_sources()[1], FORMULA)
    assert [urlsplit(url).path for _, url, _ in web.requests] == [RESULTS_PATH]
    assert parse_qs(urlsplit(web.requests[0][1]).query) == {
        "financial": [FORMULA], "is_checked": ["False"], "whales": ["False"], "is_sme": ["False"],
    }  # fmt: skip
    assert export.screen_text == f"tijori:{FORMULA}"
    assert export.definition == export.results
    assert export.results.body == fixture("tijori-results.json")
    assert [row["nse symbol"] for row in export.rows] == SYMBOLS
    assert (export.rows[0]["scripcode"], export.rows[0]["slug"]) == ("543320", "zomato-ltd")


def test_echoes_compare_with_whitespace_collapsed(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """A vendor echo differing only in whitespace runs or at the ends is the same formula."""
    replies = _page(ECHO, "\n  Market   Capitalization\n&gt; 20000 </textarea>")
    assert _screener(monkeypatch, replies, formula=f" {FORMULA}\n").rows
    spaced = _results(financial_q=" Market  Capitalization > 20000\n")
    assert _tijori(monkeypatch, spaced, formula=FORMULA).rows


SCREENER_REFUSALS: dict[str, Callable[[], Replies]] = {
    "page not 200": lambda: _with(("GET", SCREEN_PATH), (203, fixture("screen.html"), PAGE_COOKIE)),
    "not logged in": lambda: _page('<a href="/user/account/">Account</a>', ""),
    "echo absent": lambda: _page('name="query"', 'name="q"'),
    "echo twice": lambda: _page(
        "</form>\n</body>", f"<textarea name='query'>{ECHO}</form>\n</body>"
    ),
    "echo differs": lambda: _page(ECHO, "Market Capitalization &gt; 2000</textarea>"),
    "no count": lambda: _page("5 results found", "results found"),
    "two counts": lambda: _page("</body>", "<p data-page-info>5 results found</p></body>"),
    "page count differs": lambda: _page("5 results", "6 results"),
    "action other host": lambda: _page(ACTION, "https://example.invalid" + ACTION),
    "action extra key": lambda: _page(ACTION, ACTION + "&amp;sort=name"),
    "action missing key": lambda: _page(ACTION, ACTION.replace("&amp;url_name=raw_query", "")),
    "action repeated key": lambda: _page(ACTION, ACTION + "&amp;url_name=raw_query"),
    "action query differs": lambda: _page(ACTION, ACTION.replace("20000", "2000")),
    "action url_name differs": lambda: _page(ACTION, ACTION.replace("raw_query", "screen")),
    "action fragment": lambda: _page(ACTION, ACTION + "#results"),
    "no ISIN column": lambda: _csv("ISIN Code", "ISIN"),
    "ragged csv": lambda: _csv(",ETERNAL,", ",ETERNAL,,"),
    "csv not 200": lambda: _with(("POST", EXPORT_PATH), (203, fixture("screener.csv"), CSV_TYPE)),
    "csv as html": lambda: _with(("POST", EXPORT_PATH), (200, fixture("screener.csv"), HTML_TYPE)),
}


@pytest.mark.parametrize("case", SCREENER_REFUSALS)
def test_screener_refusals(case: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Each defect refuses; none returns a partial export. The page's stated count still equals
    the CSV rows in every action case, so only the action check refuses those."""
    with pytest.raises((ScreenExportError, ScreenerSessionError)):
        _screener(monkeypatch, SCREENER_REFUSALS[case]())


TIJORI_REFUSALS: dict[str, Callable[[], Replies]] = {
    "results 203": lambda: _with(
        ("GET", RESULTS_PATH), (203, fixture("tijori-results.json"), JSON_TYPE)
    ),
    "results as html": lambda: _with(
        ("GET", RESULTS_PATH), (200, fixture("tijori-results.json"), HTML_TYPE)
    ),
    "total differs": lambda: _results(total_results=6),
    "echo missing": lambda: _results(drop="financial_q"),
    "echo differs": lambda: _results(financial_q="Market Capitalization > 2000"),
    "alternate set": lambda: _results(alternate_q="Sales > 1"),
}


@pytest.mark.parametrize("case", TIJORI_REFUSALS)
def test_tijori_refusals(case: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Each defect refuses; none returns a partial export (every echo case keeps
    ``total_results == len(data)``)."""
    with pytest.raises((ScreenExportError, TijoriFetchError)):
        _tijori(monkeypatch, TIJORI_REFUSALS[case]())


@pytest.mark.parametrize("formula", ["", " \n "])
def test_an_empty_formula_requests_nothing(
    formula: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """An empty formula refuses at either vendor before any request."""
    web = serve(monkeypatch)
    screener, tijori = _sources()
    with pytest.raises(ScreenExportError, match="empty"):
        export_screener(screener, formula)
    with pytest.raises(ScreenExportError, match="empty"):
        export_tijori(tijori, formula)
    assert web.requests == []


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
    export_screener(screener, FORMULA)
    with pytest.raises(TijoriFetchError):
        export_tijori(tijori, FORMULA)
    paths = [urlsplit(url).path for _, url, _ in web.requests]
    assert paths == [SCREEN_PATH, SCREEN_PATH, EXPORT_PATH, RESULTS_PATH]
    times = [at for _, _, at in web.requests[:3]]
    assert all(later - earlier >= 2.0 for earlier, later in pairwise(times))


def test_screen_config_loads_and_refuses_a_repeated_name(tmp_path: Path) -> None:
    """The committed config gives both vendors' formulas per screen; a repeated name refuses."""
    screens = load_screen_config(CONFIG)
    assert (screens["d7-stage4"].screener, screens["d7-stage4"].tijori) == (FORMULA, FORMULA)
    repeated = tmp_path / "screens.yaml"
    repeated.write_text(
        "- {name: a, screener: x, tijori: y}\n- {name: a, screener: z, tijori: w}\n"
    )
    with pytest.raises(ScreenExportError):
        load_screen_config(repeated)


@pytest.mark.skipif(
    os.environ.get("RUN_SCREEN_EXPORT_LIVE") != "1", reason="live screen export is opt-in"
)
def test_live_export_passes_every_check(tmp_path: Path) -> None:
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
