"""The refusals every authenticated vendor command shares, in one table.

Each Screener and Tijori acquisition command must stop before its first request
when its output path is occupied, its issuer identifier is unverified, or its
session cookie is missing. A request spent first costs rate-limited budget, and
an unverified id would attach the owner's cookie to another company's URL.
Every fetch seam is replaced by one that fails the test, so a refusal that
arrives only after a request cannot pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import screener_company_support as support

from equity_os.interface.commands.sourcing import (
    screener_company_cli,
    screener_financials_cli,
    screener_page_cli,
)
from equity_os.interface.entry.cli import main
from equity_os.interface.entry.watchlist_config import (
    SCREENER_COMPANY_ID_FIELD,
    SCREENER_IDENTIFIER_FIELDS,
)
from equity_os.sourcing.vendors.screener.screener_session import ScreenerSessionSource
from equity_os.sourcing.vendors.tijori.tijori_source import TijoriSource

_SCREENER = ("screener-page", "screener-company", "screener-financials")
_TIJORI = ("tijori-analysis", "tijori-overview", "tijori-shareholding", "tijori-tables")
_EXTRA_ARGS = {"tijori-events": ("--surface", "company-timeline")}
_META = {
    "screener-page": screener_page_cli.META_FILENAME,
    "screener-company": screener_company_cli.META_FILENAME,
    "screener-financials": screener_financials_cli.META_FILENAME,
}
_COOKIE_ENV = {"screener": "SCREENER_SESSION_COOKIE", "tijori": "TIJORI_SESSION_COOKIE"}
_FETCH_SEAMS = (
    (ScreenerSessionSource, "_fetch_bytes"),
    (TijoriSource, "_fetch_page_bytes"),
    (TijoriSource, "_fetch_overview_bytes"),
    (TijoriSource, "_fetch_pl_envelope"),
    (TijoriSource, "_fetch_shareholding_bytes"),
)

# (command, flagged identifier or "", occupied artifact or "", drop the cookie, refusal)
_CASES = [
    *[
        (command, field, "", False, f"not verified: {field}")
        for command in _SCREENER
        for field in (SCREENER_IDENTIFIER_FIELDS if command == "screener-page" else ())
    ],
    ("screener-company", SCREENER_COMPANY_ID_FIELD, "", False, SCREENER_COMPANY_ID_FIELD),
    ("screener-financials", SCREENER_COMPANY_ID_FIELD, "", False, "not verified"),
    *[(command, "", _META[command], False, "refusing to overwrite") for command in _SCREENER],
    ("screener-page", "", "", True, "SCREENER_SESSION_COOKIE is required"),
    *[
        (command, field, "", False, f"not verified: {field}")
        for command in (*_TIJORI[:3], "tijori-events")
        for field in ("tijori_slug", "tijori_company_id")
    ],
    ("tijori-tables", "", "", True, "TIJORI_SESSION_COOKIE is required"),
    *[(command, "", "", True, f"required for {command}") for command in _TIJORI[:3]],
]


@pytest.mark.parametrize(("command", "flagged", "occupied", "no_cookie", "refusal"), _CASES)
def test_a_vendor_command_refuses_before_its_first_request(
    command: str,
    flagged: str,
    occupied: str,
    no_cookie: bool,
    refusal: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal comes first, names its cause, and leaves an occupied path untouched."""
    for owner, seam in _FETCH_SEAMS:
        monkeypatch.setattr(owner, seam, _unexpected_fetch)
    env = _COOKIE_ENV[command.split("-")[0]]
    for name in (env, "TIJORI_EMAIL", "TIJORI_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    if not no_cookie:
        monkeypatch.setenv(env, "fixture-session-token")
    out_dir = tmp_path / "out"
    if occupied:
        out_dir.mkdir()
        (out_dir / occupied).write_text("sentinel", encoding="utf-8")
    config = support.watchlist(tmp_path, flagged=f'"{flagged}"' if flagged else "")

    with pytest.raises(SystemExit, match=refusal):
        main(
            [
                command,
                *_EXTRA_ARGS.get(command, ()),
                "--stock",
                support.SYMBOL,
                "--config",
                str(config),
                "--out",
                str(out_dir),
            ]
        )

    if occupied:
        assert (out_dir / occupied).read_text(encoding="utf-8") == "sentinel"


def test_the_market_wide_events_run_refuses_without_a_cookie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default ``tijori-events`` run, no stock, needs the injected cookie too."""
    monkeypatch.setattr(TijoriSource, "_fetch_page_bytes", _unexpected_fetch)
    for name in ("TIJORI_SESSION_COOKIE", "TIJORI_EMAIL", "TIJORI_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit, match="required for tijori-events"):
        main(["tijori-events", "--out", str(tmp_path / "out")])


def _unexpected_fetch(*args: object, **kwargs: object) -> bytes:
    """Fail the test: a refused command made a request."""
    raise AssertionError(f"unexpected fetch: {args!r} {kwargs!r}")
