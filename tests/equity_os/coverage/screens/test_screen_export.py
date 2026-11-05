"""D7 screen export, Task 3 (direct-query revision): each vendor's run of one configured formula,
from recorded SYNTHETIC responses. Every way a response can fail to be the complete export of
exactly that formula refuses before an export exists; every attempt to either vendor is at least
2 s after the last."""

from __future__ import annotations

import json
import os
import socket
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

from equity_os.coverage.screens.screen_export import (
    SPACING_SECONDS,
    ScreenExportError,
    ScreenVendor,
    VendorExport,
    export_screener,
    export_tijori,
    load_screen_config,
    result_rows,
    screen_sources,
)
from equity_os.coverage.screens.screen_review import (
    ItemStatus,
    ReadGap,
    ReviewItem,
    read_other_vendor,
)
from equity_os.extraction.vendors.screener.screener_session_models import (
    ScreenerCredentials,
    ScreenerSessionError,
)
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_REFUSED
from equity_os.interface.entry.cli import main
from equity_os.interface.entry.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
)
from equity_os.interface.entry.watchlist_config import StockConfig, load_watchlist_config
from equity_os.sourcing.transport.http_session import RequestPacer
from equity_os.sourcing.vendors.screener.screener_session import ScreenerSessionSource
from equity_os.sourcing.vendors.screener.screener_watchlist_models import WatchlistExportError
from equity_os.sourcing.vendors.tijori.tijori_source import (
    TijoriCredentials,
    TijoriFetchError,
    TijoriSource,
)

CONFIG = Path(__file__).parents[4] / "config" / "coverage/screens.yaml"
WATCHLIST = Path(__file__).parents[4] / "config" / "coverage/watchlist.yaml"
OVERVIEW_PATH = "/company/titan-company-limited/"  # TITAN's verified Tijori slug
OVERVIEW = (
    Path(__file__).parents[4] / "tests/fundamentals/fixtures" / "synthetic_tijori_overview.html"
).read_bytes()
FORMULA = "Market Capitalization > 20000"
TITAN_ISIN = "INE280A01028"  # TITAN's ISIN in the SYNTHETIC CSV
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
    rows = result_rows(export.vendor, export.results.body)
    assert [row["NSE Code"] for row in rows] == SYMBOLS
    assert rows[0]["ISIN Code"] == "INE758T01015"


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
    rows = result_rows(export.vendor, export.results.body)
    assert [row["nse symbol"] for row in rows] == SYMBOLS
    assert (rows[0]["scripcode"], rows[0]["slug"]) == ("543320", "zomato-ltd")


def test_echoes_compare_with_whitespace_collapsed(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """A vendor echo differing only in whitespace runs or at the ends is the same formula."""
    replies = _page(ECHO, "\n  Market   Capitalization\n&gt; 20000 </textarea>")
    assert _screener(monkeypatch, replies, formula=f" {FORMULA}\n")
    spaced = _results(financial_q=" Market  Capitalization > 20000\n")
    assert _tijori(monkeypatch, spaced, formula=FORMULA)


SCREENER_REFUSALS: dict[str, Callable[[], Replies]] = {
    "page not 200": lambda: _with(("GET", SCREEN_PATH), (203, fixture("screen.html"), PAGE_COOKIE)),
    "page as json": lambda: _with(
        ("GET", SCREEN_PATH), (200, fixture("screen.html"), PAGE_COOKIE | JSON_TYPE)
    ),
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
    "repeated column": lambda: _csv("BSE Code", "Name"),
    "ragged csv": lambda: _csv(",ETERNAL,", ",ETERNAL,,"),
    "csv shorter than declared": lambda: _with(
        ("POST", EXPORT_PATH),
        (200, fixture("screener.csv"), CSV_TYPE | {"Content-Length": "999999"}),
    ),
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
    "not an object": lambda: _with(("GET", RESULTS_PATH), (200, b"[]", JSON_TYPE)),
}


@pytest.mark.parametrize("case", TIJORI_REFUSALS)
def test_tijori_refusals(case: str, monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Each defect refuses; none returns a partial export (every echo case keeps
    ``total_results == len(data)``)."""
    with pytest.raises((ScreenExportError, TijoriFetchError)):
        _tijori(monkeypatch, TIJORI_REFUSALS[case]())


def test_a_repeated_column_refuses_on_hydration() -> None:
    """A retained results capture whose header repeats a column refuses rather than collapsing
    two fields into one."""
    body = fixture("screener.csv").decode()
    assert "BSE Code" in body
    with pytest.raises(ScreenExportError, match="repeats columns"):
        result_rows(ScreenVendor.SCREENER, body.replace("BSE Code", "Name", 1).encode())


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


def test_tijori_export_and_its_diagnostic_reads_share_one_pacer(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """An export, then two Tijori overview reads through the export's pacer: every Tijori
    attempt is at least 2 s after the previous one, as is every Screener attempt."""
    web = serve(
        monkeypatch, default_replies() | {("GET", OVERVIEW_PATH): [(200, OVERVIEW, HTML_TYPE)]}
    )
    screener, tijori = _sources()
    pacer = RequestPacer(SPACING_SECONDS)
    export_screener(screener, FORMULA)
    export_tijori(tijori, FORMULA, pacer=pacer)
    (titan,) = [s for s in load_watchlist_config(WATCHLIST).stocks if s.symbol == "TITAN"]
    item = ReviewItem(
        pair_id=1, member_id=1, vendor=ScreenVendor.SCREENER, status=ItemStatus.ABSENT,
        reason=None, nse_code="TITAN", candidate_member_ids=(), row_number=1, results_ref=1,
        read=None, isin=TITAN_ISIN, bse_codes=("500114",),
    )  # fmt: skip
    for _ in range(2):
        assert not isinstance(read_other_vendor(item, titan, tijori, pacer, screener), str)
    hosts = {urlsplit(url).netloc for _, url, _ in web.requests}
    for host in hosts:
        times = [at for _, url, at in web.requests if urlsplit(url).netloc == host]
        assert all(later - earlier >= 2.0 for earlier, later in pairwise(times)), host
    assert [urlsplit(url).path for _, url, _ in web.requests][-3:] == [
        RESULTS_PATH, OVERVIEW_PATH, OVERVIEW_PATH
    ]  # fmt: skip


def _titan_item(vendor: ScreenVendor, **changes: object) -> tuple[ReviewItem, StockConfig]:
    """A bound TITAN item of ``vendor`` and TITAN's watchlist stock, its identifiers changed."""
    (titan,) = [s for s in load_watchlist_config(WATCHLIST).stocks if s.symbol == "TITAN"]
    ids = titan.identifiers.model_copy(update=changes)
    item = ReviewItem(
        pair_id=1, member_id=1, vendor=vendor, status=ItemStatus.ABSENT, reason=None,
        nse_code="TITAN", candidate_member_ids=(), row_number=1, results_ref=1, read=None,
        isin=TITAN_ISIN, bse_codes=("500114",),
    )  # fmt: skip
    return item, titan.model_copy(update={"identifiers": ids})


@pytest.mark.parametrize(
    ("vendor", "changes", "gap"),
    [
        *[(v, {"isin": "INE000A01010"}, ReadGap.NOT_VERIFIED) for v in ScreenVendor],
        *[(v, {"bse_scrip": "999999"}, ReadGap.NOT_VERIFIED) for v in ScreenVendor],
        (ScreenVendor.TIJORI, {"screener_slug": "TITAN/?q=x"}, ReadGap.READ_REFUSED),
        (ScreenVendor.TIJORI, {"screener_slug": ".."}, ReadGap.READ_REFUSED),
    ],
)
def test_a_diagnostic_read_of_another_issuer_or_url_requests_nothing(
    vendor: ScreenVendor,
    changes: dict[str, str],
    gap: ReadGap,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
) -> None:
    """A watchlist stock that is not the member's bound issuer (another ISIN, or a BSE scrip not
    the bound ISIN's: its NSE symbol reused), or a Screener slug that is not one plain path
    segment (a prohibited query, a traversal), refuses before any request."""
    web = serve(monkeypatch, {})
    item, stock = _titan_item(vendor, **changes)
    screener, tijori = _sources()
    assert read_other_vendor(item, stock, tijori, RequestPacer(0.0), screener) == gap
    assert web.requests == []


def test_malformed_csv_quoting_refuses_at_export_and_hydration(
    monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    """An unterminated quoted final cell keeps every record's width, so only strict parsing in the
    one shared reader catches it, at export and on re-reading the retained capture."""
    body = fixture("screener.csv")
    assert body.endswith(b",5.00\n")
    broken = body[:-5] + b'"5.00\n'
    with pytest.raises(WatchlistExportError, match="well-formed"):
        _screener(monkeypatch, _with(("POST", EXPORT_PATH), (200, broken, CSV_TYPE)))
    with pytest.raises(WatchlistExportError, match="well-formed"):
        result_rows(ScreenVendor.SCREENER, broken)


def test_tijori_hydration_keeps_number_lexemes() -> None:
    """A Tijori value is the vendor's text: a JSON number is never rounded through a float."""
    body = b'{"data": [{"a": 1.2300, "b": 9007199254740993.125, "c": 7, "d": null}]}'
    assert result_rows(ScreenVendor.TIJORI, body) == (
        {"a": "1.2300", "b": "9007199254740993.125", "c": "7", "d": ""},
    )


@pytest.mark.parametrize("text", ["", "- {name: a, screener: [x\n"])
def test_an_empty_or_unparsable_screen_config_refuses(
    text: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty screens file, or one that is not YAML, refuses through the CLI's handler before
    any request."""
    connects: list[object] = []
    monkeypatch.setattr(socket.socket, "connect", lambda *args: connects.append(args))
    screens = tmp_path / "screens.yaml"
    screens.write_text(text)
    code = main(["coverage", "export", "--screen", "a", "--screens", str(screens),
                 "--snapshot-root", str(tmp_path)])  # fmt: skip
    assert code == EXIT_REFUSED and connects == []


def test_screen_config_loads_and_refuses_a_repeated_name_or_blank_field(tmp_path: Path) -> None:
    """The committed config gives both vendors' formulas per screen; a repeated name, or a blank
    name or formula (found before any request), refuses."""
    screens = load_screen_config(CONFIG)
    assert (screens["d7-stage4"].screener, screens["d7-stage4"].tijori) == (FORMULA, FORMULA)
    repeated = tmp_path / "screens.yaml"
    repeated.write_text(
        "- {name: a, screener: x, tijori: y}\n- {name: a, screener: z, tijori: w}\n"
    )
    with pytest.raises(ScreenExportError):
        load_screen_config(repeated)
    for blank in ("{name: ' ', screener: x, tijori: y}", "{name: a, screener: x, tijori: '   '}"):
        repeated.write_text(f"- {blank}\n")
        with pytest.raises(ScreenExportError, match="blank"):
            load_screen_config(repeated)


def test_a_refused_cookie_never_reaches_the_log(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A session cookie ``http.client`` refuses as a header value (a newline) refuses the export
    before any connection, and the failure log names its type without quoting the cookie."""
    secret = "sentinel-cookie-7f3a"
    monkeypatch.setenv("SCREENER_SESSION_COOKIE", f"{secret}\nx")
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", secret)
    connects: list[object] = []
    monkeypatch.setattr(socket.socket, "connect", lambda *args: connects.append(args))
    code = main(["coverage", "export", "--screen", "d7-stage4", "--screens", str(CONFIG),
                 "--snapshot-root", str(tmp_path)])  # fmt: skip
    out, err = capfd.readouterr()
    assert code == EXIT_REFUSED and connects == []
    assert "coverage_command_failed" in err and "failure=ValueError" in err
    assert secret not in out + err


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
        assert result_rows(export.vendor, export.results.body)
