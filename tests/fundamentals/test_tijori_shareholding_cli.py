"""Fixture-only CLI coverage for Tijori shareholding acquisition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tijori_cli_support import assert_raw_first
from tijori_cli_support import tijori_cli_capture as tijori_cli_capture

from fundamentals.api.cli import main
from fundamentals.ingest.tijori_shareholding import TijoriShareholdingIdentityError
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource

pytestmark = [pytest.mark.pg, pytest.mark.usefixtures("tijori_cli_capture")]

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_tijori_shareholding.html"
_ARTIFACT_FILENAME = "shareholding.json"


def _fetch_fixture(
    source: TijoriSource,
    slug: str,
    credentials: TijoriCredentials,
) -> bytes:
    """Replace only the outbound transport boundary with the committed fixture."""
    del source, credentials
    assert slug == "titan-company-limited"
    return _FIXTURE.read_bytes()


def _row(payload: dict[str, Any], row_key: str) -> dict[str, Any]:
    """Select one serialized row by its stable row key."""
    matches = [row for row in payload["rows"] if row["row_key"] == row_key]
    assert len(matches) == 1
    return matches[0]


def test_shareholding_cli_writes_structured_json_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The composition root resolves TITAN and writes one fixture-backed table."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_shareholding_bytes", _fetch_fixture)
    out_dir = tmp_path / "shareholding"

    code = main(["tijori-shareholding", "--stock", "TITAN", "--out", str(out_dir)])

    assert code == 0
    payload = json.loads((out_dir / _ARTIFACT_FILENAME).read_text(encoding="utf-8"))
    assert payload["column_period_labels"] == ["Mar'24", "Jun'24", "Sep'24"]
    # The CLI supplies the watchlist's tijori_company_id, which the page heading
    # must match; no island corroborates it on the live page shape.
    assert payload["metadata"]["company_id"] == 81
    assert payload["metadata"]["identity_island_ids"] == []
    fund = _row(payload, "Public Shareholding/Institutions/Synthetic Large Cap Fund")
    assert fund["depth"] == 2
    assert fund["source_depth"] == 3
    assert fund["cells"][0]["provenance"]["anchor_type"] == "HTML_TABLE"
    assert payload["breakups"][0]["table_id"] == "chartData:overview"
    summary = capsys.readouterr().out.splitlines()
    assert summary[0].split("\t") == [
        "stock",
        "rows",
        "columns",
        "quarantined",
        "breakups",
        "unreadable",
        "comp_id",
    ]
    # Two readable charts and the one drifted chart the fixture also carries, so
    # a chart the page published but this adapter could not read stays visible.
    assert summary[1].split("\t") == ["TITAN", "14", "3", "1", "2", "1", "81"]


def test_shareholding_cli_refuses_to_overwrite_an_existing_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-existing artifact is never replaced, and the fetch result is discarded."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_shareholding_bytes", _fetch_fixture)
    out_dir = tmp_path / "shareholding"
    out_dir.mkdir()
    (out_dir / _ARTIFACT_FILENAME).write_text("previous", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(["tijori-shareholding", "--stock", "TITAN", "--out", str(out_dir)])

    assert (out_dir / _ARTIFACT_FILENAME).read_text(encoding="utf-8") == "previous"


def test_shareholding_cli_binds_the_page_to_the_configured_company_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serving TITAN's page for a THERMAX request is caught by the heading gate."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")

    def _fetch_wrong_company(
        source: TijoriSource, slug: str, credentials: TijoriCredentials
    ) -> bytes:
        del source, slug, credentials
        return _FIXTURE.read_bytes()

    monkeypatch.setattr(TijoriSource, "_fetch_shareholding_bytes", _fetch_wrong_company)

    with pytest.raises(TijoriShareholdingIdentityError, match="requested company ID 301"):
        main(["tijori-shareholding", "--stock", "THERMAX", "--out", str(tmp_path / "out")])


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
def test_shareholding_cli_refuses_an_unverified_tijori_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flagged: str,
) -> None:
    """Either unconfirmed Tijori identifier must stop the run, not be trusted."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_shareholding_bytes", _fetch_fixture)
    config = tmp_path / "watchlist.yaml"
    config.write_text(_watchlist_yaml(f'"{flagged}"'), encoding="utf-8")

    with pytest.raises(SystemExit, match=f"not verified: {flagged}"):
        main(
            [
                "tijori-shareholding",
                "--stock",
                "TITAN",
                "--config",
                str(config),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_shareholding_cli_requires_an_injected_session_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credentials come from the composition root only, never from the adapter."""
    monkeypatch.delenv("TIJORI_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("TIJORI_EMAIL", raising=False)
    monkeypatch.delenv("TIJORI_PASSWORD", raising=False)

    with pytest.raises(SystemExit, match="required for tijori-shareholding"):
        main(["tijori-shareholding", "--stock", "TITAN", "--out", str(tmp_path / "out")])


@pytest.mark.parametrize("case", ["ok", "failed", "stopped"])
def test_shareholding_cli_raw_first(case, tijori_cli_capture, pg_db, tmp_path, monkeypatch):
    """Every raw response is registered before parsing or a durable stop."""
    assert_raw_first("shareholding", case, tijori_cli_capture, pg_db, tmp_path, monkeypatch)


def test_builder_logs_exclude_vendor_text(tmp_path, monkeypatch, capsys):
    """Raw-first artifact building must sanitize pinned-reader diagnostics too."""
    from lxml import etree, html

    marker = "PRIVATE_LOG_SENTINEL"
    tree = html.fromstring(_FIXTURE.read_bytes())
    tree.xpath('//script[@id="plan_details"]')[0].text = json.dumps(
        {"name": {"private": marker}, "plan_tier": {"private": marker}}
    )
    for script in tree.xpath("//script[not(@src)]"):
        if script.text:
            script.text = script.text.replace(
                'var subcategory = "overview"', f'var subcategory = "{marker}"'
            )
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "synthetic")
    monkeypatch.setattr(TijoriSource, "_fetch_shareholding_bytes", lambda *a: etree.tostring(tree))
    assert main(["tijori-shareholding", "--stock", "TITAN", "--out", str(tmp_path / "out")]) == 0
    assert marker not in capsys.readouterr().err


def test_shareholding_final_log_excludes_quarantine_labels(pg_db, tmp_path, monkeypatch):
    import argparse

    from types import SimpleNamespace

    import structlog.testing
    from vendor_surface_support import retained

    from fundamentals.api import tijori_shareholding_cli as cli
    from fundamentals.ingest.tijori_source import TijoriCredentials

    body, ctx = retained("tijori", "company-shareholding", "APARINDS")
    record = SimpleNamespace(retrieved_at=ctx.retrieved_at)
    monkeypatch.setattr(cli, "_capture_page", lambda *a: (record, body.raw, ctx.url))
    original = cli.build_tijori_shareholding

    def with_quarantine(*a, **kw):
        return original(*a, **kw).model_copy(
            update={"cardinality_mismatch_rows": ("review_private_label",)}
        )

    monkeypatch.setattr(cli, "build_tijori_shareholding", with_quarantine)
    with structlog.testing.capture_logs() as logs:
        cli.run_tijori_shareholding_command(
            argparse.Namespace(
                stock="APARINDS",
                config="config/watchlist.yaml",
                out=str(tmp_path / "out"),
                snapshot_root=tmp_path / "raw",
            ),
            credentials=TijoriCredentials(session_cookie="synthetic"),
        )
    leaked = sum("review_private_label" in str(event) for event in logs)
    assert leaked == 0, f"{leaked} final-log events contain quarantined vendor labels"
