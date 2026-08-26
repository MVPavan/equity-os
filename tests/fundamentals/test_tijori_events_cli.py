"""Fixture-only CLI coverage for Tijori event-surface acquisition.

No test opens a socket: the fixture-backed tests replace the page-fetch seam, and
the transport tests replace ``urllib``'s opener with a recording double.
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from fundamentals.api.cli import main
from fundamentals.ingest.tijori_events_models import TijoriEventsSurface
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriFetchError,
    TijoriSource,
    TijoriSourceConfig,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_SLUG = "titan-company-limited"
_COMPANY_ID = 81
_BASE = "https://www.tijorifinance.com"

_BREADTH_FILES = [
    "quarterly-results.json",
    "quarterly-results.raw.html",
    "timeline.json",
    "timeline.raw.html",
    "upcoming.json",
    "upcoming.raw.html",
]

_URL_FIXTURES = {
    "/results/upcoming-events/": "synthetic_tijori_upcoming.html",
    "/results/quarterly-results/": "synthetic_tijori_quarterly_results.html",
    "/in/timeline": "synthetic_tijori_timeline_site.html",
    "/timeline/company/": "synthetic_tijori_timeline_company.html",
}


def _fixture_for(url: str) -> bytes:
    """Serve the committed body whose surface path the URL names."""
    for path, filename in _URL_FIXTURES.items():
        if path in url:
            return (_FIXTURES / filename).read_bytes()
    raise AssertionError(f"unexpected events URL: {url}")


def _use_fixtures(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Inject a session cookie and pin the fetch seam to the committed bodies."""
    requested: list[str] = []

    def fetch(
        source: TijoriSource,
        url: str,
        *,
        slug: str,
        credentials: TijoriCredentials,
        fetch_event: str,
    ) -> bytes:
        del source, slug, credentials, fetch_event
        requested.append(url)
        return _fixture_for(url)

    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_page_bytes", fetch)
    return requested


_COLUMNS = ("capability", "surface", "scope", "state", "outcome", "elements", "raw", "note")


def _summary_rows(output: str) -> dict[str, dict[str, str]]:
    """Index one run summary by capability name, with columns keyed by header."""
    lines = output.splitlines()
    assert tuple(lines[0].split("\t")) == _COLUMNS
    rows = [dict(zip(_COLUMNS, line.split("\t"), strict=True)) for line in lines[1:]]
    return {row["capability"]: row for row in rows}


def test_a_breadth_run_acquires_every_market_wide_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A run with no --surface acquires the three surfaces that need no company."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    code = main(["tijori-events", "--out", str(out_dir)])

    assert code == 0
    assert sorted(path.name for path in out_dir.iterdir()) == _BREADTH_FILES
    captured = capsys.readouterr()
    rows = _summary_rows(captured.out)
    results = rows["upcoming-results"]
    assert results["surface"] == "upcoming"
    assert results["scope"] == "market_wide"
    assert results["state"] == "acquired"
    assert results["outcome"] == "ok"
    assert results["elements"] == "3"
    assert results["raw"] == "upcoming.raw.html"
    assert rows["quarterly-results-listing"]["elements"] == "2"
    assert rows["timeline-taxonomy"]["elements"] == "15"
    assert "fixture-session-token" not in captured.err


def test_the_summary_reports_a_withheld_feed_beside_the_data_it_did_acquire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One 'timeline ok 15' line invited reading filter types as market events."""
    _use_fixtures(monkeypatch)

    main(["tijori-events", "--out", str(tmp_path / "events")])

    rows = _summary_rows(capsys.readouterr().out)
    feed = rows["timeline-feed"]
    assert feed["surface"] == "timeline"
    assert feed["state"] == "xhr_not_acquired"
    assert feed["elements"] == "-"
    assert "not the event feed" in feed["note"]
    concalls = rows["upcoming-concalls-feed"]
    assert concalls["state"] == "xhr_not_acquired"
    assert concalls["elements"] == "-"


def test_every_capability_row_dates_the_verdict_it_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An undated capability verdict reads as a permanent claim about Tijori."""
    _use_fixtures(monkeypatch)

    main(["tijori-events", "--out", str(tmp_path / "events")])

    rows = _summary_rows(capsys.readouterr().out)
    assert {row["capability"] for row in rows.values()} == {
        "upcoming-results",
        "upcoming-concalls-feed",
        "quarterly-results-listing",
        "timeline-taxonomy",
        "timeline-feed",
        "company-timeline-events",
        "concall-monitor",
    }
    for name in ("timeline-feed", "upcoming-concalls-feed", "concall-monitor"):
        assert "2026-08-25" in rows[name]["note"]


def test_the_breadth_summary_reports_the_concall_monitor_as_not_static(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A silently omitted surface would read as the market having had no concalls."""
    _use_fixtures(monkeypatch)

    main(["tijori-events", "--out", str(tmp_path / "events")])

    rows = _summary_rows(capsys.readouterr().out)
    assert rows["concall-monitor"]["state"] == "external_product_at_capture"
    assert rows["concall-monitor"]["outcome"] == "not_static"
    assert "no tables, no data islands" in rows["concall-monitor"]["note"]


def test_a_breadth_run_without_a_stock_skips_the_company_timeline_with_its_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Needing a company id is a fact about this run, never a fact about Tijori."""
    _use_fixtures(monkeypatch)

    main(["tijori-events", "--out", str(tmp_path / "events")])

    rows = _summary_rows(capsys.readouterr().out)
    assert rows["company-timeline-events"]["scope"] == "company"
    assert rows["company-timeline-events"]["state"] == "acquired"
    assert rows["company-timeline-events"]["outcome"] == "skipped"
    assert "needs --stock" in rows["company-timeline-events"]["note"]


def test_a_breadth_run_never_requests_the_concall_monitor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its document is verified to carry nothing, so fetching it would be pointless."""
    requested = _use_fixtures(monkeypatch)

    main(["tijori-events", "--out", str(tmp_path / "events")])

    assert requested == [
        f"{_BASE}/results/upcoming-events/",
        f"{_BASE}/results/quarterly-results/",
        f"{_BASE}/in/timeline",
    ]


def test_naming_a_stock_adds_the_company_timeline_to_the_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fragment is addressed by the verified watchlist company id."""
    requested = _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    code = main(["tijori-events", "--stock", "TITAN", "--out", str(out_dir)])

    assert code == 0
    assert "company-timeline.json" in {path.name for path in out_dir.iterdir()}
    assert requested[-1] == f"{_BASE}/timeline/company/?company_id={_COMPANY_ID}&timestamp=0"


def test_the_company_timeline_alone_can_be_requested_by_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One surface, one artifact, one retained body."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    main(
        [
            "tijori-events",
            "--surface",
            "company-timeline",
            "--stock",
            "TITAN",
            "--out",
            str(out_dir),
        ]
    )

    assert sorted(path.name for path in out_dir.iterdir()) == [
        "company-timeline.json",
        "company-timeline.raw.html",
    ]
    rows = _summary_rows(capsys.readouterr().out)
    events = rows["company-timeline-events"]
    assert (events["scope"], events["outcome"], events["elements"]) == ("company", "ok", "4")


def test_the_company_timeline_is_refused_without_a_named_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A surface whose URL cannot be built must not write an empty artifact."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    with pytest.raises(SystemExit, match="needs --stock"):
        main(["tijori-events", "--surface", "company-timeline", "--out", str(out_dir)])

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_the_concall_monitor_is_not_a_selectable_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offering it would promise an acquisition this adapter has verified it cannot make."""
    _use_fixtures(monkeypatch)

    with pytest.raises(SystemExit):
        main(
            [
                "tijori-events",
                "--surface",
                "concall-monitor",
                "--out",
                str(tmp_path / "events"),
            ]
        )


def test_the_written_artifact_records_the_watchlist_cross_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A market listing is only useful here if its tracked rows are identifiable."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    main(["tijori-events", "--surface", "upcoming", "--out", str(out_dir)])

    artifact = json.loads((out_dir / "upcoming.json").read_text(encoding="utf-8"))
    rows = artifact["rows"]
    assert rows[0]["company"]["watchlist_symbol"] == "TITAN"
    assert rows[0]["company"]["on_watchlist"] is True
    assert rows[1]["company"]["on_watchlist"] is False
    assert artifact["metadata"]["scope"] == "market_wide"
    assert artifact["metadata"]["identity_strength"] == "no_company_identity"


def test_the_retained_raw_body_matches_the_hash_the_artifact_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded body hash is only evidence if the bytes it covers are on disk."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"

    main(["tijori-events", "--surface", "upcoming", "--out", str(out_dir)])

    artifact = json.loads((out_dir / "upcoming.json").read_text(encoding="utf-8"))
    raw_bytes = (out_dir / "upcoming.raw.html").read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == artifact["metadata"]["file_sha256"]
    assert raw_bytes == (_FIXTURES / "synthetic_tijori_upcoming.html").read_bytes()


def test_a_colliding_raw_file_aborts_the_whole_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact and body are retained together or not at all."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"
    out_dir.mkdir()
    (out_dir / "timeline.raw.html").write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite.*timeline.raw.html"):
        main(["tijori-events", "--out", str(out_dir)])

    assert sorted(path.name for path in out_dir.iterdir()) == ["timeline.raw.html"]


def test_the_run_refuses_an_existing_symlink_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller-selected directory cannot redirect an artifact through a symlink."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "events"
    out_dir.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("sentinel", encoding="utf-8")
    (out_dir / "upcoming.json").symlink_to(victim)

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(["tijori-events", "--surface", "upcoming", "--out", str(out_dir)])

    assert victim.read_text(encoding="utf-8") == "sentinel"


def _watchlist_yaml(needs_verification: str) -> str:
    """One-stock watchlist whose Tijori verification flags are under test."""
    return f"""
raw_dir: "data/raw/watchlist"
stocks:
  - name: "Titan Company Limited"
    domain: "Jewellery / Retail"
    identifiers:
      nse_symbol: "TITAN"
      bse_scrip: "500114"
      screener_slug: "TITAN"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      tijori_slug: "{_SLUG}"
      tijori_company_id: {_COMPANY_ID}
      needs_verification: [{needs_verification}]
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
"""


@pytest.mark.parametrize("flagged", ["tijori_slug", "tijori_company_id"])
def test_the_company_timeline_refuses_an_unverified_tijori_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flagged: str,
) -> None:
    """The company id in the URL IS the identity here, so it must be a verified one."""
    _use_fixtures(monkeypatch)
    config = tmp_path / "watchlist.yaml"
    config.write_text(_watchlist_yaml(f'"{flagged}"'), encoding="utf-8")

    with pytest.raises(SystemExit, match=f"not verified: {flagged}"):
        main(
            [
                "tijori-events",
                "--surface",
                "company-timeline",
                "--stock",
                "TITAN",
                "--config",
                str(config),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_an_unverified_slug_is_left_out_of_the_market_cross_link_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-linking on an unconfirmed identifier would manufacture an unchecked match."""
    _use_fixtures(monkeypatch)
    config = tmp_path / "watchlist.yaml"
    config.write_text(_watchlist_yaml('"tijori_slug"'), encoding="utf-8")
    out_dir = tmp_path / "events"

    main(
        [
            "tijori-events",
            "--surface",
            "upcoming",
            "--config",
            str(config),
            "--out",
            str(out_dir),
        ]
    )

    artifact = json.loads((out_dir / "upcoming.json").read_text(encoding="utf-8"))
    assert artifact["rows"][0]["company"]["on_watchlist"] is False


def test_the_command_requires_an_injected_session_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credentials come from the composition root only, never from the adapter."""
    monkeypatch.delenv("TIJORI_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("TIJORI_EMAIL", raising=False)
    monkeypatch.delenv("TIJORI_PASSWORD", raising=False)

    def unexpected_fetch(*args: object, **kwargs: object) -> bytes:
        raise AssertionError(f"unexpected fetch: {args!r} {kwargs!r}")

    monkeypatch.setattr(TijoriSource, "_fetch_page_bytes", unexpected_fetch)

    with pytest.raises(SystemExit, match="required for tijori-events"):
        main(["tijori-events", "--out", str(tmp_path / "out")])


class _Response(io.BytesIO):
    """Minimal urllib response double carrying a status and headers."""

    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        super().__init__(payload)
        self._status = status
        self.headers: dict[str, str] = {}

    def getcode(self) -> int:
        """Return the configured HTTP status code."""
        return self._status

    def __enter__(self) -> _Response:
        """Support the ``with opener.open(...)`` form the adapter uses."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the response body."""
        self.close()


class _Opener:
    """Injectable urllib opener that records the one outbound request."""

    def __init__(self, outcome: _Response) -> None:
        self._outcome = outcome
        self.calls: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        """Record the outbound request and return the configured response."""
        del timeout
        self.calls.append(request)
        return self._outcome


def _install_opener(monkeypatch: pytest.MonkeyPatch, opener: _Opener) -> None:
    """Patch opener construction so no socket is ever created."""

    def build_opener(handler: Any) -> _Opener:
        del handler
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)


def _source() -> TijoriSource:
    """An events source carrying a synthetic, redacted session cookie."""
    return TijoriSource(
        TijoriSourceConfig(credentials=TijoriCredentials(session_cookie="session-token"))
    )


def test_a_company_timeline_login_redirect_is_refused_rather_than_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An anonymous session is redirected to login; following it would parse that page."""
    redirect = _Response(b"", status=302)
    redirect.headers["Location"] = "/login/"
    opener = _Opener(redirect)
    _install_opener(monkeypatch, opener)

    with pytest.raises(TijoriFetchError, match="slug not found: redirect"):
        _source().fetch_events(
            surface=TijoriEventsSurface.COMPANY_TIMELINE,
            slug=_SLUG,
            symbol="TITAN",
            company_id=_COMPANY_ID,
        )

    assert len(opener.calls) == 1


def test_the_events_request_carries_the_session_cookie_over_a_plain_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every event surface takes the same session cookie the page fetches use."""
    body = (_FIXTURES / "synthetic_tijori_upcoming.html").read_bytes()
    opener = _Opener(_Response(body))
    _install_opener(monkeypatch, opener)

    fetch = _source().fetch_events(surface=TijoriEventsSurface.UPCOMING)

    assert fetch.artifact.element_count == 3
    assert fetch.raw_body == body
    request = opener.calls[0]
    assert request.get_method() == "GET"
    assert request.full_url == f"{_BASE}/results/upcoming-events/"
    assert request.get_header("Cookie") == "sessionid=session-token"
