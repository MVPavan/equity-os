"""Fixture-only CLI coverage for raw Tijori table acquisition."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from fundamentals.api.cli import main
from fundamentals.ingest.tijori_capture import PageEnvelope
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource
from fundamentals.ingest.tijori_tables import TijoriTablesAbsentError

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_tijori_financials.html"
_MEDIA_TYPE = "text/html; charset=utf-8"


def _envelope(body: bytes) -> PageEnvelope:
    """One complete 200 response carrying the given page bytes."""
    return PageEnvelope(payload=body, status=200, media_type=_MEDIA_TYPE)


def _fetch_fixture(
    source: TijoriSource,
    slug: str,
    credentials: TijoriCredentials,
) -> PageEnvelope:
    """Replace only the outbound transport boundary with the committed fixture."""
    del source, credentials
    assert slug == "titan-company-limited"
    return _envelope(_FIXTURE.read_bytes())


def _row(payload: dict[str, Any], row_key: str) -> dict[str, Any]:
    """Select one serialized row by its stable row key."""
    matches = [row for row in payload["rows"] if row["row_key"] == row_key]
    assert len(matches) == 1
    return matches[0]


def test_tijori_tables_cli_writes_structured_json_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The composition root resolves TITAN and writes one fixture-backed raw table."""

    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", _fetch_fixture)
    out_dir = tmp_path / "tijori"

    code = main(
        [
            "tijori-tables",
            "--stock",
            "TITAN",
            "--table",
            "fr_c",
            "--out",
            str(out_dir),
            "--snapshot-root",
            str(tmp_path / "snapshots"),
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert captured.out == "table\trows\tcolumns\tplan_tier\nfr_c\t8\t2\tfree\n"
    payload = json.loads((out_dir / "fr_c.json").read_text(encoding="utf-8"))
    debt_to_equity = _row(payload, "Operational Ratios/Debt to Equity")
    assert debt_to_equity["parent_labels"] == ["Operational Ratios"]
    assert debt_to_equity["cells"][1]["value"] == "0.625"
    assert debt_to_equity["cells"][1]["raw_text"] == "0.625"
    assert debt_to_equity["field_id"] == "debt_to_equity"
    assert debt_to_equity["cells"][1]["provenance"]["table_key"] == "fr_c"
    assert _row(payload, "Profitability Ratios/Return on Equity")["cells"][0]["raw_text"] == (
        "12.5%"
    )
    assert payload["metadata"]["observed_unknown_table_keys"] == ["fundflow_c"]
    assert "fixture-session-token" not in captured.err


def test_tijori_tables_cli_refuses_existing_symlink_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller-selected directory cannot redirect a table file through a symlink."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", _fetch_fixture)
    out_dir = tmp_path / "tijori"
    out_dir.mkdir()
    victim = tmp_path / "victim.json"
    victim.write_text("sentinel", encoding="utf-8")
    (out_dir / "fr_c.json").symlink_to(victim)

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "tijori-tables",
                "--stock",
                "TITAN",
                "--table",
                "fr_c",
                "--out",
                str(out_dir),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
            ]
        )

    assert victim.read_text(encoding="utf-8") == "sentinel"


def test_tijori_tables_cli_preflights_every_output_path_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One colliding target aborts the whole multi-table write, leaving no artifact."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", _fetch_fixture)
    out_dir = tmp_path / "tijori"
    out_dir.mkdir()
    (out_dir / "growth.json").write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite.*growth.json"):
        main(
            [
                "tijori-tables",
                "--stock",
                "TITAN",
                "--out",
                str(out_dir),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
            ]
        )

    assert sorted(path.name for path in out_dir.iterdir()) == ["growth.json"]
    assert (out_dir / "growth.json").read_text(encoding="utf-8") == "sentinel"


def test_tijori_tables_cli_writes_every_present_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default breadth run writes one artifact per published key with data."""
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", _fetch_fixture)
    out_dir = tmp_path / "tijori"

    code = main(
        [
            "tijori-tables",
            "--stock",
            "TITAN",
            "--out",
            str(out_dir),
            "--snapshot-root",
            str(tmp_path / "snapshots"),
        ]
    )

    assert code == 0
    assert sorted(path.name for path in out_dir.iterdir()) == [
        "bs_c_d.json",
        "bs_c_s.json",
        "cf_c.json",
        "fr_c.json",
        "growth.json",
        "pl_c_s.json",
        "pl_s_s.json",
        "qt_c.json",
        "qt_s.json",
    ]
    assert capsys.readouterr().out.splitlines()[0] == "table\trows\tcolumns\tplan_tier"


@pytest.mark.parametrize(
    "island_json",
    [b"{}", b'{"fundflow_c": {"report_dates": ["Mar 2024"], "data": []}}'],
)
def test_tijori_tables_cli_fails_when_no_supported_table_is_present(
    island_json: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI must not exit 0 having written nothing when acquisition found nothing."""
    page = re.sub(
        rb'(<script id="fin_tables_data" type="application/json">)(.*?)(</script>)',
        rb"\1" + island_json + rb"\3",
        _FIXTURE.read_bytes(),
        flags=re.DOTALL,
    )

    def fetch_stripped(
        source: TijoriSource, slug: str, credentials: TijoriCredentials
    ) -> PageEnvelope:
        del source, slug, credentials
        return _envelope(page)

    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "fixture-session-token")
    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", fetch_stripped)
    out_dir = tmp_path / "tijori"

    with pytest.raises(TijoriTablesAbsentError, match="no supported financial table"):
        main(
            [
                "tijori-tables",
                "--stock",
                "TITAN",
                "--out",
                str(out_dir),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
            ]
        )

    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_tijori_tables_cli_requires_cookie_before_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing composition-root credentials fail before the outbound boundary."""
    monkeypatch.delenv("TIJORI_EMAIL", raising=False)
    monkeypatch.delenv("TIJORI_PASSWORD", raising=False)
    monkeypatch.delenv("TIJORI_SESSION_COOKIE", raising=False)

    def unexpected_fetch(*args: object, **kwargs: object) -> PageEnvelope:
        raise AssertionError(f"unexpected fetch: {args!r} {kwargs!r}")

    monkeypatch.setattr(TijoriSource, "_fetch_pl_envelope", unexpected_fetch)

    with pytest.raises(SystemExit, match="TIJORI_SESSION_COOKIE is required"):
        main(
            [
                "tijori-tables",
                "--stock",
                "TITAN",
                "--out",
                str(tmp_path),
            ]
        )
