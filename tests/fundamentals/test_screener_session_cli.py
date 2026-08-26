"""Fixture-only CLI coverage for ``fundamentals screener-page``.

No test opens a socket: the transport seam is replaced with committed synthetic
bodies. These tests pin the acquisition contract around the fetch — refusal
before the network, no-clobber, retained evidence, and an outcome that a caller
cannot mistake for the basis they asked for.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fundamentals.api import screener_page_cli
from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_BASIS_UNAVAILABLE, EXIT_REFUSED
from fundamentals.api.screener_page_cli import META_FILENAME, RAW_FILENAME
from fundamentals.api.watchlist_config import (
    SCREENER_IDENTIFIER_FIELDS,
    load_watchlist_config,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import Basis, ScreenerCredentials

_FIXTURES = Path(__file__).parent / "fixtures"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_SESSION_ENV = "SCREENER_SESSION_COOKIE"
_SESSION_TOKEN = "fixture-session-token"

# The two shapes the watchlist must express: a dual-basis company and a
# standalone-only one whose consolidated warehouse id does not exist.
_WATCHLIST_YAML = """
raw_dir: "data/raw/watchlist"
stocks:
  - name: "Fixture Consolidated Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "FIXTURECO"
      bse_scrip: "500999"
      screener_slug: "FIXTURECO"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      screener_warehouse_id_standalone: 992002
      tijori_slug: "fixture-consolidated-ltd"
      tijori_company_id: 81
      needs_verification: [{flagged}]
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
  - name: "Fixture Standalone Only Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "SOLOCO"
      bse_scrip: "500998"
      screener_slug: "SOLOCO"
      screener_company_id: 991002
      screener_warehouse_id_standalone: 992003
      tijori_slug: "fixture-standalone-only-ltd"
      tijori_company_id: 82
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
"""


def _watchlist(tmp_path: Path, *, flagged: str = "") -> Path:
    """Write the two-stock fixture watchlist, optionally flagging one identifier."""
    path = tmp_path / "watchlist.yaml"
    path.write_text(_WATCHLIST_YAML.format(flagged=flagged), encoding="utf-8")
    return path


def _body(name: str) -> bytes:
    """Read one committed synthetic company-page body."""
    return (_FIXTURES / f"synthetic_screener_session_{name}.html").read_bytes()


def _serve(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
    """Pin the transport seam to one committed body and record requested URLs."""
    requested: list[str] = []

    def fetch_bytes(
        source: ScreenerSessionSource, url: str, credentials: ScreenerCredentials
    ) -> tuple[int, bytes]:
        del source, credentials
        requested.append(url)
        return 200, _body(name)

    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)
    return requested


def _refuse_any_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if a request is attempted at all."""

    def unexpected(*args: object, **kwargs: object) -> tuple[int, bytes]:
        raise AssertionError(f"unexpected fetch: {args!r} {kwargs!r}")

    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", unexpected)


def _meta(out_dir: Path) -> dict[str, object]:
    """Read the metadata artifact one run wrote."""
    return json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))


def test_the_command_writes_the_page_bytes_beside_their_assertion_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The artifact is only trustworthy with the bytes it was derived from beside it."""
    requested = _serve(monkeypatch, "consolidated")
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "FIXTURECO",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    assert requested == ["https://www.screener.in/company/FIXTURECO/consolidated/"]
    raw = (out_dir / RAW_FILENAME).read_bytes()
    metadata = _meta(out_dir)
    assert raw == _body("consolidated")
    assert metadata["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert metadata["byte_count"] == len(raw)
    assert metadata["basis_requested"] == Basis.CONSOLIDATED.value
    assert metadata["basis_observed"] == Basis.CONSOLIDATED.value
    assert metadata["outcome"] == "ok"
    assert metadata["company_id_seen"] == 991001
    assert metadata["warehouse_id_seen"] == 992001
    assert metadata["logged_in"] is True
    summary = capsys.readouterr().out.splitlines()
    assert summary[0].split("\t")[:4] == ["symbol", "basis_requested", "basis_observed", "outcome"]
    assert summary[1].split("\t")[:4] == ["FIXTURECO", "consolidated", "consolidated", "ok"]


def test_the_standalone_basis_is_requested_only_when_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Consolidated is this repo's default basis; standalone is an explicit request."""
    requested = _serve(monkeypatch, "standalone")
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "FIXTURECO",
            "--basis",
            "standalone",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    assert requested == ["https://www.screener.in/company/FIXTURECO/"]
    assert _meta(out_dir)["warehouse_id_seen"] == 992002


def test_an_unavailable_basis_exits_non_zero_with_its_evidence_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A standalone-only company's consolidated URL must not be reported as a success.

    The evidence is still written — the fact "this company publishes no
    consolidated figures" is worth keeping — but the command fails so no caller
    reads the standalone shell as consolidated data.
    """
    _serve(monkeypatch, "basis_unavailable")
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "SOLOCO",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == EXIT_BASIS_UNAVAILABLE
    assert "screener served no consolidated basis for SOLOCO" in capsys.readouterr().err
    metadata = _meta(out_dir)
    assert metadata["outcome"] == "basis_unavailable"
    assert metadata["basis_observed"] is None
    assert metadata["single_basis"] is True
    assert metadata["tables_empty"] is True
    assert (out_dir / RAW_FILENAME).read_bytes() == _body("basis_unavailable")


def test_a_standalone_only_company_acquires_cleanly_on_its_own_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The absence of a consolidated page is not a defect in the standalone one."""
    _serve(monkeypatch, "single_basis")
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "SOLOCO",
            "--basis",
            "standalone",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    metadata = _meta(out_dir)
    assert metadata["outcome"] == "ok"
    assert metadata["single_basis"] is True
    assert metadata["markers"] == []


@pytest.mark.parametrize("flagged", SCREENER_IDENTIFIER_FIELDS)
def test_an_unverified_screener_identifier_stops_the_run_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flagged: str
) -> None:
    """An unconfirmed identifier must not be spent on a rate-limited request."""
    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    _refuse_any_fetch(monkeypatch)

    with pytest.raises(SystemExit, match=f"not verified: {flagged}"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path, flagged=f'"{flagged}"')),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_an_existing_artifact_is_never_overwritten_and_costs_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No-clobber is pre-flighted: a doomed write must not spend a request first."""
    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    _refuse_any_fetch(monkeypatch)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    victim = out_dir / META_FILENAME
    victim.write_text("sentinel", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(out_dir),
            ]
        )

    assert victim.read_text(encoding="utf-8") == "sentinel"


def test_a_missing_session_cookie_refuses_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the cookie Screener would serve a valid anonymous page, not an error."""
    monkeypatch.delenv(_SESSION_ENV, raising=False)
    _refuse_any_fetch(monkeypatch)

    with pytest.raises(SystemExit, match="SCREENER_SESSION_COOKIE is required"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_a_symbol_outside_the_watchlist_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only configured, identity-pinned stocks may be fetched."""
    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    _refuse_any_fetch(monkeypatch)

    with pytest.raises(SystemExit, match="is not in the watchlist"):
        main(
            [
                "screener-page",
                "--stock",
                "NOTLISTED",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_the_watchlist_pins_both_screener_id_namespaces_for_every_stock() -> None:
    """Every watchlist stock carries a live-verified company id and at least one basis."""
    watchlist = load_watchlist_config(_WATCHLIST_PATH)

    assert len(watchlist.stocks) == 10
    for stock in watchlist.stocks:
        identifiers = stock.identifiers
        assert identifiers.screener_company_id > 0
        assert identifiers.unverified_screener_fields() == ()
        assert (
            identifiers.screener_warehouse_id_consolidated is not None
            or identifiers.screener_warehouse_id_standalone is not None
        )


def test_the_standalone_only_stock_carries_no_consolidated_warehouse_id() -> None:
    """NETWEB publishes no consolidated page; that null is a fact, not an unverified guess."""
    netweb = load_watchlist_config(_WATCHLIST_PATH).stock("NETWEB")

    assert netweb.identifiers.screener_warehouse_id_consolidated is None
    assert netweb.identifiers.screener_warehouse_id_standalone == 104235517
    assert netweb.identifiers.needs_verification == ()


def test_a_stock_with_no_screener_warehouse_id_on_either_basis_is_rejected(
    tmp_path: Path,
) -> None:
    """A stock with neither id could not be fetched on any basis."""
    yaml_text = _WATCHLIST_YAML.format(flagged="").replace(
        "      screener_warehouse_id_standalone: 992003\n", ""
    )
    path = tmp_path / "watchlist.yaml"
    path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError, match="at least one of"):
        load_watchlist_config(path)


def test_two_stocks_may_not_share_one_screener_company_id(tmp_path: Path) -> None:
    """A duplicate id would let one issuer's page satisfy another issuer's request."""
    yaml_text = _WATCHLIST_YAML.format(flagged="").replace(
        "screener_company_id: 991002", "screener_company_id: 991001"
    )
    path = tmp_path / "watchlist.yaml"
    path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError, match="reuses screener_company_id"):
        load_watchlist_config(path)


def test_two_stocks_may_not_share_one_screener_warehouse_id(tmp_path: Path) -> None:
    """Warehouse ids scope the basis-specific APIs, so they must be unique too."""
    yaml_text = _WATCHLIST_YAML.format(flagged="").replace(
        "screener_warehouse_id_standalone: 992003", "screener_warehouse_id_standalone: 992001"
    )
    path = tmp_path / "watchlist.yaml"
    path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError, match="reuses a screener warehouse id"):
        load_watchlist_config(path)


@pytest.mark.parametrize(
    ("fixture", "refusal"),
    [("anonymous", "AnonymousPageError"), ("wrong_identity", "IdentityMismatchError")],
)
def test_a_typed_refusal_is_one_clean_line_and_never_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fixture: str,
    refusal: str,
) -> None:
    """Refusals are expected outcomes of talking to this source, not crashes.

    A dead cookie and a swapped page are both ordinary operational events; a
    traceback buries the one line that says which, and makes an expected refusal
    look like a defect in the tool.
    """
    _serve(monkeypatch, fixture)

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "FIXTURECO",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    captured = capsys.readouterr()
    # structlog diagnostics also go to stderr by repo convention; what matters is
    # that the refusal itself is exactly one line and carries no traceback.
    refusal_lines = [line for line in captured.err.splitlines() if "refused (" in line]
    assert exit_code == EXIT_REFUSED
    assert captured.out == ""
    assert len(refusal_lines) == 1
    assert refusal in refusal_lines[0]
    assert "Traceback" not in captured.err


def test_a_failed_metadata_write_leaves_the_directory_clean_for_a_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Metadata is the completion marker, so a half-written pair must not survive.

    Durable success metadata pointing at absent bytes would read as a completed
    acquisition, and no-clobber would then block the rerun that could fix it.
    """
    _serve(monkeypatch, "consolidated")

    def failing_write(out_path: Path, payload: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("fundamentals.api.screener_page_cli.write_json_no_clobber", failing_write)
    out_dir = tmp_path / "out"

    with pytest.raises(OSError, match="disk full"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(out_dir),
            ]
        )

    assert not (out_dir / RAW_FILENAME).exists()
    assert not (out_dir / META_FILENAME).exists()


def test_an_existing_raw_body_is_refused_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both artifacts are pre-flighted together: either one present blocks the fetch."""
    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    _refuse_any_fetch(monkeypatch)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    victim = out_dir / RAW_FILENAME
    victim.write_bytes(b"sentinel")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(out_dir),
            ]
        )

    assert victim.read_bytes() == b"sentinel"
    assert not (out_dir / META_FILENAME).exists()


def test_the_raw_bytes_are_on_disk_before_the_metadata_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Order is the contract, not just cleanup: metadata marks completed evidence.

    Asserting only that both files exist afterwards would pass with the writes
    reversed, so this spies on the metadata write and records what was already
    on disk at that instant.
    """
    _serve(monkeypatch, "consolidated")
    out_dir = tmp_path / "out"
    real_write = screener_page_cli.write_json_no_clobber
    seen: dict[str, object] = {}

    def spy(out_path: Path, payload: str) -> None:
        seen["raw_exists"] = (out_dir / RAW_FILENAME).exists()
        seen["raw_bytes"] = (out_dir / RAW_FILENAME).read_bytes()
        real_write(out_path, payload)

    monkeypatch.setattr(screener_page_cli, "write_json_no_clobber", spy)

    exit_code = main(
        [
            "screener-page",
            "--stock",
            "FIXTURECO",
            "--config",
            str(_watchlist(tmp_path)),
            "--out",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    assert seen["raw_exists"] is True
    assert seen["raw_bytes"] == _body("consolidated")


def _serve_and_publish_concurrently(
    monkeypatch: pytest.MonkeyPatch, name: str, *, out_dir: Path, filenames: tuple[str, ...]
) -> None:
    """Serve one body, and have a *different* writer publish into out_dir mid-fetch.

    Pre-flight runs before the request, so this is the real window in which
    another process can land artifacts in the output directory.
    """

    def fetch_bytes(
        source: ScreenerSessionSource, url: str, credentials: ScreenerCredentials
    ) -> tuple[int, bytes]:
        del source, url, credentials
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            (out_dir / filename).write_bytes(b"another process's evidence")
        return 200, _body(name)

    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)


@pytest.mark.parametrize("filenames", [(RAW_FILENAME, META_FILENAME), (RAW_FILENAME,)])
def test_a_concurrent_publishers_artifacts_are_never_deleted_by_our_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filenames: tuple[str, ...]
) -> None:
    """Losing the no-clobber race must cost us the write, never their evidence.

    Rollback that unlinks by name would delete files this run never created —
    turning a refusal that exists to protect data into the data loss itself.
    """
    out_dir = tmp_path / "out"
    _serve_and_publish_concurrently(
        monkeypatch, "consolidated", out_dir=out_dir, filenames=filenames
    )

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(out_dir),
            ]
        )

    for filename in filenames:
        assert (out_dir / filename).read_bytes() == b"another process's evidence"


def test_losing_the_race_on_metadata_removes_only_our_own_raw_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Our half-written pair is cleaned up; the other writer's metadata is untouched."""
    out_dir = tmp_path / "out"
    _serve_and_publish_concurrently(
        monkeypatch, "consolidated", out_dir=out_dir, filenames=(META_FILENAME,)
    )

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                "screener-page",
                "--stock",
                "FIXTURECO",
                "--config",
                str(_watchlist(tmp_path)),
                "--out",
                str(out_dir),
            ]
        )

    assert (out_dir / META_FILENAME).read_bytes() == b"another process's evidence"
    assert not (out_dir / RAW_FILENAME).exists()
