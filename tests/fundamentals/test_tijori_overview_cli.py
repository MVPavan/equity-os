"""Fixture-only CLI coverage for Tijori overview-section acquisition."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fundamentals.api.cli import main
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewIdentityError,
    TijoriOverviewSectionAbsentError,
    TijoriOverviewSectionsAbsentError,
)
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_tijori_overview.html"
_ALL_SECTION_FILES = [
    "company_details.json",
    "corporate_actions.json",
    "custom_financials.json",
    "market_share.json",
    "peers.json",
    "price_chart.json",
    "price_chart_peers.json",
    "price_returns.json",
    "ratios.json",
]


def _fetch_fixture(
    source: TijoriSource,
    slug: str,
    credentials: TijoriCredentials,
) -> bytes:
    """Replace only the outbound transport boundary with the committed fixture."""
    del source, credentials
    assert slug == "titan-company-limited"
    return _FIXTURE.read_bytes()


def _use_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a session cookie and pin the transport seam to the fixture."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_overview_bytes", _fetch_fixture)


def test_overview_cli_writes_one_artifact_per_published_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The composition root resolves TITAN and writes every fixture-backed section."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"

    code = main(["tijori-overview", "--stock", "TITAN", "--out", str(out_dir)])

    assert code == 0
    assert sorted(path.name for path in out_dir.iterdir()) == _ALL_SECTION_FILES
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[0].split("\t") == ["section", "island", "status", "elements", "plan_tier"]
    rows = {line.split("\t")[0]: line.split("\t") for line in lines[1:]}
    assert rows["ratios"] == ["ratios", "ratios_table", "present", "3", "free"]
    # The section the page does not publish is still reported, so an absent
    # island is visible in the run output rather than inferred from a gap.
    assert rows["intraday_price"] == ["intraday_price", "intraday_price", "absent", "-", "free"]
    assert "fixture-session-token" not in captured.err


def test_overview_cli_serializes_typed_values_and_anchors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The written JSON keeps Decimal readings, source lexemes, and island anchors."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"

    main(["tijori-overview", "--stock", "TITAN", "--out", str(out_dir)])

    ratios = json.loads((out_dir / "ratios.json").read_text(encoding="utf-8"))
    mcap = next(ratio for ratio in ratios["ratios"] if ratio["name"] == "mcap")
    assert mcap["amount"]["value"] == "449713.00"
    assert mcap["amount"]["raw_text"] == "449713.00"
    anchor = mcap["amount"]["provenance"]
    assert anchor["anchor_type"] == "JSON_ISLAND"
    assert anchor["island_id"] == "ratios_table"
    assert anchor["table_key"] == "ratios"
    assert anchor["row_label"] == "mcap"
    assert anchor["column_label"] == "value"

    price_chart = json.loads((out_dir / "price_chart.json").read_text(encoding="utf-8"))
    assert price_chart["malformed_point_count"] == 1
    assert price_chart["points"][0]["timestamp_ms"] == 1223577000000
    assert price_chart["points"][0]["timestamp_iso"].startswith("2008-10-09T18:30:00")

    details = json.loads((out_dir / "company_details.json").read_text(encoding="utf-8"))
    assert details["metadata"]["identity_island_ids"] == ["company_details_data", "companyId"]
    quick_look = details["quick_look"]
    assert quick_look["counts"]["total"] == 17
    assert [category["name"] for category in quick_look["categories"]] == [
        "Accounting & Shareholding",
        "Growth & Returns",
    ]
    assert len(quick_look["categories"][0]["flags"]) == 2
    assert "shape not yet modeled" in quick_look["table_data_json"]


def test_overview_cli_writes_only_the_requested_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``--section`` run writes that one artifact and nothing else."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"

    code = main(
        [
            "tijori-overview",
            "--stock",
            "TITAN",
            "--section",
            "corporate_actions",
            "--out",
            str(out_dir),
        ]
    )

    assert code == 0
    assert [path.name for path in out_dir.iterdir()] == ["corporate_actions.json"]


def test_overview_cli_refuses_a_section_the_page_does_not_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit request for an absent section must not produce an empty file."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"

    with pytest.raises(TijoriOverviewSectionAbsentError, match="'intraday_price' is absent"):
        main(
            [
                "tijori-overview",
                "--stock",
                "TITAN",
                "--section",
                "intraday_price",
                "--out",
                str(out_dir),
            ]
        )

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_overview_cli_fails_when_the_page_carries_no_data_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI must not exit 0 having written only the identity header."""
    stripped = _FIXTURE.read_text(encoding="utf-8")
    for island_id in (
        "corporate_actions",
        "ratios_table",
        "custom_fin_table",
        "ms-charts",
        "peers_table_data",
        "price_returns",
        "price_chart",
        "price_chart_peers",
    ):
        stripped = re.sub(
            rf'<script id="{re.escape(island_id)}" type="application/json">.*?</script>',
            "",
            stripped,
            flags=re.DOTALL,
        )

    def fetch_stripped(source: TijoriSource, slug: str, credentials: TijoriCredentials) -> bytes:
        del source, slug, credentials
        return stripped.encode("utf-8")

    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_overview_bytes", fetch_stripped)
    out_dir = tmp_path / "overview"

    with pytest.raises(TijoriOverviewSectionsAbsentError, match="no modeled data section"):
        main(["tijori-overview", "--stock", "TITAN", "--out", str(out_dir)])

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_overview_cli_preflights_every_output_path_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One colliding target aborts the whole multi-section write, leaving no artifact."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"
    out_dir.mkdir()
    (out_dir / "peers.json").write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite.*peers.json"):
        main(["tijori-overview", "--stock", "TITAN", "--out", str(out_dir)])

    assert sorted(path.name for path in out_dir.iterdir()) == ["peers.json"]
    assert (out_dir / "peers.json").read_text(encoding="utf-8") == "sentinel"


def test_overview_cli_refuses_an_existing_symlink_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller-selected directory cannot redirect a section file through a symlink."""
    _use_fixture(monkeypatch)
    out_dir = tmp_path / "overview"
    out_dir.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("sentinel", encoding="utf-8")
    (out_dir / "ratios.json").symlink_to(victim)

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(["tijori-overview", "--stock", "TITAN", "--section", "ratios", "--out", str(out_dir)])

    assert victim.read_text(encoding="utf-8") == "sentinel"


def test_overview_cli_binds_the_page_to_the_configured_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serving TITAN's page for a THERMAX request is caught by the identity gate."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")

    def fetch_wrong_company(
        source: TijoriSource, slug: str, credentials: TijoriCredentials
    ) -> bytes:
        del source, slug, credentials
        return _FIXTURE.read_bytes()

    monkeypatch.setattr(TijoriSource, "_fetch_overview_bytes", fetch_wrong_company)

    with pytest.raises(TijoriOverviewIdentityError, match="requested symbol 'THERMAX'"):
        main(["tijori-overview", "--stock", "THERMAX", "--out", str(tmp_path / "out")])


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
      tijori_slug: "titan-company-limited"
      tijori_company_id: 81
      needs_verification: [{needs_verification}]
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
"""


@pytest.mark.parametrize("flagged", ["tijori_slug", "tijori_company_id"])
def test_overview_cli_refuses_an_unverified_tijori_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flagged: str,
) -> None:
    """Either unconfirmed Tijori identifier must stop the run, not be trusted."""
    _use_fixture(monkeypatch)
    config = tmp_path / "watchlist.yaml"
    config.write_text(_watchlist_yaml(f'"{flagged}"'), encoding="utf-8")

    with pytest.raises(SystemExit, match=f"not verified: {flagged}"):
        main(
            [
                "tijori-overview",
                "--stock",
                "TITAN",
                "--config",
                str(config),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_overview_cli_requires_an_injected_session_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credentials come from the composition root only, never from the adapter."""
    monkeypatch.delenv("TIJORI_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("TIJORI_EMAIL", raising=False)
    monkeypatch.delenv("TIJORI_PASSWORD", raising=False)

    def unexpected_fetch(*args: object, **kwargs: object) -> bytes:
        raise AssertionError(f"unexpected fetch: {args!r} {kwargs!r}")

    monkeypatch.setattr(TijoriSource, "_fetch_overview_bytes", unexpected_fetch)

    with pytest.raises(SystemExit, match="required for tijori-overview"):
        main(["tijori-overview", "--stock", "TITAN", "--out", str(tmp_path / "out")])
