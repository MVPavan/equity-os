"""Fixture-only CLI coverage for Tijori analysis-API acquisition.

No test opens a socket: the fixture-backed tests replace the page-fetch seam,
and the transport tests replace ``urllib``'s opener with a recording double.
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
from fundamentals.ingest.tijori_analysis_models import TijoriAnalysisSection
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriFetchError,
    TijoriSource,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "tijori_api"
_SLUG = "titan-company-limited"
_COMPANY_ID = 81
_METRIC_ID = 2448
_BREADTH_FILES = [
    "balance_sheet_snapshot.json",
    "balance_sheet_snapshot.raw.json",
    "cash_flow_waterfall.json",
    "cash_flow_waterfall.raw.json",
    "fund_flow.json",
    "fund_flow.raw.json",
]

_URL_FIXTURES = {
    "fund_flow_analysis_data": "fund_flow_analysis_data.json",
    "balance_sheet_snap_shot": "balance_sheet_snap_shot.json",
    "cash_flow_waterfall": "cash_flow_waterfall.json",
    "company_op_metrics": "company_op_metrics.json",
}


def _fixture_for(url: str) -> bytes:
    """Serve the committed body whose API path segment the URL names."""
    for segment, filename in _URL_FIXTURES.items():
        if f"/{segment}/" in url:
            return (_FIXTURES / filename).read_bytes()
    raise AssertionError(f"unexpected analysis URL: {url}")


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
        del source, credentials, fetch_event
        assert slug == _SLUG
        requested.append(url)
        return _fixture_for(url)

    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_page_bytes", fetch)
    return requested


def test_analysis_cli_writes_one_artifact_per_breadth_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A breadth run acquires every API that needs only the company id."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"

    code = main(["tijori-analysis", "--stock", "TITAN", "--out", str(out_dir)])

    assert code == 0
    assert sorted(path.name for path in out_dir.iterdir()) == _BREADTH_FILES
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[0].split("\t") == [
        "section",
        "document",
        "outcome",
        "elements",
        "metric_id",
        "raw",
        "note",
    ]
    rows = {line.split("\t")[0]: line.split("\t") for line in lines[1:]}
    assert rows["fund_flow"] == [
        "fund_flow",
        "api:fund_flow_analysis_data",
        "ok",
        "9",
        "-",
        "fund_flow.raw.json",
        "-",
    ]
    assert rows["balance_sheet_snapshot"][3] == "5"
    assert "fixture-session-token" not in captured.err


def test_analysis_cli_requests_the_company_id_bearing_url_with_its_trailing_slash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The trailing slash is load-bearing: without it the API answers a redirect."""
    requested = _use_fixtures(monkeypatch)

    main(["tijori-analysis", "--stock", "TITAN", "--out", str(tmp_path / "analysis")])

    assert requested == [
        f"https://www.tijorifinance.com/api/v1/ind/fund_flow_analysis_data/{_COMPANY_ID}/",
        f"https://www.tijorifinance.com/api/v1/ind/balance_sheet_snap_shot/{_COMPANY_ID}/",
        f"https://www.tijorifinance.com/api/v1/ind/cash_flow_waterfall/{_COMPANY_ID}/",
    ]


def test_the_breadth_summary_lists_op_metrics_as_skipped_with_its_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A silently omitted section would read as the API having nothing to give."""
    _use_fixtures(monkeypatch)

    main(["tijori-analysis", "--stock", "TITAN", "--out", str(tmp_path / "analysis")])

    rows = {
        line.split("\t")[0]: line.split("\t") for line in capsys.readouterr().out.splitlines()[1:]
    }
    assert "op_metrics" in rows
    assert rows["op_metrics"][1] == "api:company_op_metrics"
    assert rows["op_metrics"][2] == "skipped"
    assert "needs --metric-id" in rows["op_metrics"][6]


def test_the_retained_raw_body_matches_the_hash_the_artifact_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded body hash is only evidence if the bytes it covers are on disk."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"

    main(["tijori-analysis", "--stock", "TITAN", "--out", str(out_dir)])

    artifact = json.loads((out_dir / "fund_flow.json").read_text(encoding="utf-8"))
    raw_bytes = (out_dir / "fund_flow.raw.json").read_bytes()
    assert hashlib.sha256(raw_bytes).hexdigest() == artifact["metadata"]["file_sha256"]
    assert raw_bytes == (_FIXTURES / "fund_flow_analysis_data.json").read_bytes()


def test_a_colliding_raw_file_aborts_the_write_like_a_colliding_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact and body are retained together or not at all."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"
    out_dir.mkdir()
    (out_dir / "fund_flow.raw.json").write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite.*fund_flow.raw.json"):
        main(["tijori-analysis", "--stock", "TITAN", "--out", str(out_dir)])

    assert sorted(path.name for path in out_dir.iterdir()) == ["fund_flow.raw.json"]


def test_analysis_cli_skips_op_metrics_until_a_metric_id_is_supplied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No acquired artifact publishes op-metric ids, so breadth cannot guess one."""
    requested = _use_fixtures(monkeypatch)

    main(["tijori-analysis", "--stock", "TITAN", "--out", str(tmp_path / "analysis")])

    assert not any("company_op_metrics" in url for url in requested)


def test_analysis_cli_fetches_one_artifact_per_requested_metric_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two metrics must not collide on one filename or one anchor."""
    requested = _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"

    code = main(
        [
            "tijori-analysis",
            "--stock",
            "TITAN",
            "--section",
            "op_metrics",
            "--metric-id",
            str(_METRIC_ID),
            "--metric-id",
            "2449",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    assert sorted(path.name for path in out_dir.iterdir()) == [
        "op_metrics-2448.json",
        "op_metrics-2448.raw.json",
        "op_metrics-2449.json",
        "op_metrics-2449.raw.json",
    ]
    assert requested == [
        f"https://www.tijorifinance.com/api/v1/ind/company_op_metrics/{_COMPANY_ID}/2448/",
        f"https://www.tijorifinance.com/api/v1/ind/company_op_metrics/{_COMPANY_ID}/2449/",
    ]


def test_analysis_cli_refuses_op_metrics_without_a_metric_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asking for a section whose URL cannot be built must not write an empty file."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"

    with pytest.raises(SystemExit, match="needs --metric-id"):
        main(
            [
                "tijori-analysis",
                "--stock",
                "TITAN",
                "--section",
                "op_metrics",
                "--out",
                str(out_dir),
            ]
        )

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_analysis_cli_serializes_typed_values_and_api_anchors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The written JSON keeps Decimal readings, source lexemes, and API anchors."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"

    main(["tijori-analysis", "--stock", "TITAN", "--out", str(out_dir)])

    waterfall = json.loads((out_dir / "cash_flow_waterfall.json").read_text(encoding="utf-8"))
    first_window = waterfall["windows"][0]
    assert first_window["window"] == "1yr"
    total = first_window["items"][2]
    assert total["is_sum"] is True
    assert total["amount_published"] is False
    assert total["amount"]["value"] is None

    anchor = first_window["items"][0]["amount"]["provenance"]
    assert anchor["anchor_type"] == "API_DOCUMENT"
    assert anchor["document_id"] == "api:cash_flow_waterfall"
    assert anchor["island_id"] is None
    assert anchor["table_key"] == "1yr"
    assert anchor["row_label"] == "0/OCF (Before WCC)"
    assert anchor["column_label"] == "y"

    metadata = waterfall["metadata"]
    assert metadata["symbol"] == "TITAN"
    assert metadata["company_id"] == _COMPANY_ID
    assert "no identity field" in metadata["identity_basis"]


def test_analysis_cli_preflights_every_output_path_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One colliding target aborts the whole multi-document write, leaving no artifact."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"
    out_dir.mkdir()
    (out_dir / "cash_flow_waterfall.json").write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite.*cash_flow_waterfall.json"):
        main(["tijori-analysis", "--stock", "TITAN", "--out", str(out_dir)])

    assert sorted(path.name for path in out_dir.iterdir()) == ["cash_flow_waterfall.json"]
    assert (out_dir / "cash_flow_waterfall.json").read_text(encoding="utf-8") == "sentinel"


def test_analysis_cli_refuses_an_existing_symlink_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller-selected directory cannot redirect an artifact through a symlink."""
    _use_fixtures(monkeypatch)
    out_dir = tmp_path / "analysis"
    out_dir.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("sentinel", encoding="utf-8")
    (out_dir / "fund_flow.json").symlink_to(victim)

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "tijori-analysis",
                "--stock",
                "TITAN",
                "--section",
                "fund_flow",
                "--out",
                str(out_dir),
            ]
        )

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
def test_analysis_cli_refuses_an_unverified_tijori_identifier(
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
                "tijori-analysis",
                "--stock",
                "TITAN",
                "--config",
                str(config),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_analysis_cli_requires_an_injected_session_cookie(
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

    with pytest.raises(SystemExit, match="required for tijori-analysis"):
        main(["tijori-analysis", "--stock", "TITAN", "--out", str(tmp_path / "out")])


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
    """An analysis source carrying a synthetic, redacted session cookie."""
    from fundamentals.ingest.tijori_source import TijoriSourceConfig

    return TijoriSource(
        TijoriSourceConfig(credentials=TijoriCredentials(session_cookie="session-token"))
    )


def test_an_analysis_redirect_is_refused_rather_than_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The slash-less path answers 301; following it would parse the wrong document."""
    redirect = _Response(b"", status=301)
    redirect.headers["Location"] = "/api/v1/ind/cash_flow_waterfall/81/"
    opener = _Opener(redirect)
    _install_opener(monkeypatch, opener)

    with pytest.raises(TijoriFetchError, match="slug not found: redirect"):
        _source().fetch_analysis(
            slug=_SLUG,
            symbol="TITAN",
            company_id=_COMPANY_ID,
            section=TijoriAnalysisSection.CASH_FLOW_WATERFALL,
        )

    assert len(opener.calls) == 1


def test_the_analysis_request_carries_the_session_cookie_and_no_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API takes the same session cookie the page fetches use, over a plain GET."""
    body = (_FIXTURES / "cash_flow_waterfall.json").read_bytes()
    opener = _Opener(_Response(body))
    _install_opener(monkeypatch, opener)

    fetch = _source().fetch_analysis(
        slug=_SLUG,
        symbol="TITAN",
        company_id=_COMPANY_ID,
        section=TijoriAnalysisSection.CASH_FLOW_WATERFALL,
    )

    assert fetch.document.element_count == 11
    assert fetch.raw_body == body
    request = opener.calls[0]
    assert request.get_method() == "GET"
    assert request.full_url.endswith(f"/api/v1/ind/cash_flow_waterfall/{_COMPANY_ID}/")
    assert request.get_header("Cookie") == "sessionid=session-token"
