"""Acceptance tests for ``screener-watchlist-corroborate`` (eqos-kx4.3.7).

The residual the outer reviewer found on Slice 4: the watchlist cross-check
corroborates the HTML slug against the CSV exchange code and nothing else, so
swapping the ISIN between two slug-routed export records leaves every oracle
green while each row merges under the other company's ISIN. The export is the
only witness to its own ISIN, and one witness cannot corroborate itself.

This command is the third source. It reads a published ``WatchlistArtifact``
and a retained ``UpstoxInstrumentCatalog``, both already on disk, and asks the
catalog what ISIN each exchange code belongs to. The swap is then two
disagreements rather than two silent merges.

Every ISIN on both sides comes from :func:`entity_map_fixtures.isin`, so the two
artifacts share one vocabulary of check-digit-valid synthetic ISINs and a
resolution can never fail merely because the fixtures disagreed on spelling.

The two modules under test were imported at call time while they did not exist,
so that every requirement below could be independently red rather than collapsed
into one collection error. They exist now, and the indirection has been removed:
it would only hide these assertions from the type checker.
"""

from __future__ import annotations

import socket
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import entity_map_fixtures as emf
import pytest
from upstox_fixtures import bse_equity_row, derivative_row, nse_equity_row, write_parsed_catalog

from fundamentals.api.cli import main
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.api.screener_watchlist_corroborate_cli import (
    REPORT_FILENAME as CLI_REPORT_FILENAME,
)
from fundamentals.api.screener_watchlist_corroborate_cli import (
    SCREENER_WATCHLIST_CORROBORATE_COMMAND,
)
from fundamentals.ingest.screener_watchlist_corroborate import (
    INDUSTRY_NOT_CORROBORATED,
    CorroborationOutcome,
    CorroborationRow,
    WatchlistCorroborationError,
    WatchlistCorroborationReport,
    corroborate_watchlist,
)
from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistFailure,
    WatchlistOutcome,
)

COMMAND = "screener-watchlist-corroborate"
REPORT_FILENAME = "watchlist_corroboration.json"
SUMMARY_HEADER = "name\tisin\tisin_outcome\tresolved_isin\tresolved_via\tnse_code\tbse_code"
TOTAL_PREFIX = "TOTAL"

# The two export fields a resolution can come from, named as the export names
# them so a report row says which code carried the join.
VIA_NSE = "nse_code"
VIA_BSE = "bse_code"


def _listing(index: int, isin_code: str, *, nse: str | None, bse: str | None) -> emf.Listing:
    """One synthetic watchlist member stating an ISIN and its exchange codes."""
    return emf.Listing(
        company_id=9200000 + index,
        slug=None,
        display_name=f"Fixture Company {index} Limited",
        isin_code=isin_code,
        nse_code=nse,
        bse_code=bse,
    )


def _nse_row(isin_code: str, symbol: str, token: str = "10001") -> dict[str, Any]:
    """One ``NSE_EQ`` catalog row binding a trading symbol to an ISIN."""
    return nse_equity_row(
        isin=isin_code,
        instrument_key=f"NSE_EQ|{isin_code}",
        trading_symbol=symbol,
        exchange_token=token,
    )


def _bse_row(isin_code: str, scrip: str) -> dict[str, Any]:
    """One ``BSE_EQ`` catalog row binding an exchange token to an ISIN."""
    return bse_equity_row(
        isin=isin_code,
        instrument_key=f"BSE_EQ|{isin_code}",
        trading_symbol=f"BSE{scrip}",
        exchange_token=scrip,
    )


def _inputs(
    tmp_path: Path, listings: Sequence[emf.Listing], *rows: dict[str, Any]
) -> tuple[Path, Path]:
    """Write the watchlist artifact and the instrument catalog this run reads."""
    return emf.write_s1_artifact(tmp_path, listings), write_parsed_catalog(tmp_path, *rows)


def _report(
    tmp_path: Path, listings: Sequence[emf.Listing], *rows: dict[str, Any]
) -> WatchlistCorroborationReport:
    """Corroborate one synthetic watchlist against one synthetic catalog."""
    watchlist, catalog = _inputs(tmp_path, listings, *rows)
    return corroborate_watchlist(watchlist, catalog)


def _rows_by_isin(report: WatchlistCorroborationReport) -> dict[str, CorroborationRow]:
    """The report's rows, indexed by the ISIN the export published for each."""
    return {row.isin: row for row in report.rows}


def _argv(watchlist: Path, catalog: Path, out: Path) -> list[str]:
    """The invocation the seam fixes: two retained inputs and an output directory."""
    return [
        COMMAND,
        "--watchlist",
        str(watchlist),
        "--upstox-catalog",
        str(catalog),
        "--out",
        str(out),
    ]


def _write_incomplete_watchlist(directory: Path) -> Path:
    """A watchlist artifact that stopped short, written exactly as a run would."""
    artifact = WatchlistArtifact(
        outcome=WatchlistOutcome.INCOMPLETE,
        incomplete_reason="the export response did not prove it is the export",
        failure=WatchlistFailure(
            source_url="https://fixture.invalid/api/export/screen/",
            refusal="WatchlistExportError",
            detail="the export carried no content type",
        ),
    )
    path = directory / "screener_watchlist.json"
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    return path


# C-05
def test_two_companies_whose_isins_were_swapped_are_both_conflicted(tmp_path: Path) -> None:
    """The bead's own reproduction, and the reason this command exists.

    Two export records keep their exchange codes and exchange their ISINs. Every
    Slice 4 oracle passes on that input, because the export is the only source
    that ever stated either ISIN. The catalog has never heard of the export, so
    it resolves each NSE code to the ISIN that code actually belongs to, and the
    swap becomes two disagreements naming each other.
    """
    swapped = [
        _listing(1, emf.BRAVO_ISIN, nse=emf.ALPHA_NSE, bse=None),
        _listing(2, emf.ALPHA_ISIN, nse=emf.BRAVO_NSE, bse=None),
    ]
    report = _report(
        tmp_path,
        swapped,
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, token="10001"),
        _nse_row(emf.BRAVO_ISIN, emf.BRAVO_NSE, token="10002"),
    )
    conflicted = [row for row in report.rows if row.isin_outcome == CorroborationOutcome.CONFLICTED]
    assert len(report.rows) == 2
    assert len(conflicted) == 2

    rows = _rows_by_isin(report)
    assert rows[emf.BRAVO_ISIN].resolved_isin == emf.ALPHA_ISIN
    assert rows[emf.ALPHA_ISIN].resolved_isin == emf.BRAVO_ISIN
    assert {row.resolved_via for row in conflicted} == {VIA_NSE}


# C-03
def test_a_code_resolving_to_the_exported_isin_is_confirmed(tmp_path: Path) -> None:
    """Agreement is the only outcome that may be published as corroboration.

    The sibling tests below prove the same call reports a disagreement and an
    absence differently, so a CONFIRMED here cannot be explained by an
    implementation that confirms everything it is handed.
    """
    report = _report(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.ALPHA_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    row = _rows_by_isin(report)[emf.ALPHA_ISIN]
    assert row.isin_outcome == CorroborationOutcome.CONFIRMED
    assert row.resolved_isin == emf.ALPHA_ISIN
    assert row.resolved_via == VIA_NSE
    assert row.nse_code_corroborated == CorroborationOutcome.CONFIRMED
    assert row.bse_code_corroborated == CorroborationOutcome.CONFIRMED


# C-03
def test_a_company_the_catalog_holds_no_code_for_is_not_covered(tmp_path: Path) -> None:
    """Silence from a filtered catalog is our coverage, never the vendor's claim.

    The retained catalog is an ISIN-filtered view of a current-state file, so a
    code it holds no row for may be our filter, a delisting or a security type
    we never retain. Reporting that as a disagreement would state our own filter
    as a fact about the company, which is the failure the Upstox adapter's
    absence rule already exists to prevent.
    """
    report = _report(
        tmp_path,
        [_listing(1, emf.DELTA_ISIN, nse=emf.ZULU_NSE, bse=emf.ORPHAN_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    row = _rows_by_isin(report)[emf.DELTA_ISIN]
    assert row.isin_outcome == CorroborationOutcome.NOT_COVERED
    assert row.resolved_isin is None
    assert row.resolved_via is None
    assert row.resolutions == ()


# C-03
def test_two_codes_resolving_to_different_isins_are_conflicted_with_both_recorded(
    tmp_path: Path,
) -> None:
    """One code agreeing does not make the row corroborated.

    The NSE code resolves to the exported ISIN and the BSE code resolves to a
    different one. Reporting only the first resolution would publish this row as
    CONFIRMED and lose the very disagreement that was found, so both resolutions
    are recorded and the row is conflicted.
    """
    report = _report(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.CHARLIE_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.CHARLIE_ISIN, emf.CHARLIE_BSE),
    )
    row = _rows_by_isin(report)[emf.ALPHA_ISIN]
    assert row.isin_outcome == CorroborationOutcome.CONFLICTED
    assert {(resolution.via, resolution.isin) for resolution in row.resolutions} == {
        (VIA_NSE, emf.ALPHA_ISIN),
        (VIA_BSE, emf.CHARLIE_ISIN),
    }
    # The headline names the resolution that DISAGREES. Publishing the agreeing
    # one beside a CONFLICTED verdict would read, in the summary table a person
    # actually looks at, as though the row corroborated.
    assert row.resolved_isin == emf.CHARLIE_ISIN
    assert row.resolved_via == VIA_BSE


# C-04
def test_a_bse_code_the_catalog_states_differently_is_conflicted_on_that_field(
    tmp_path: Path,
) -> None:
    """The reverse direction: the catalog's rows for the exported ISIN.

    Resolving the codes only checks the codes the export happens to carry into
    the index. Reading the catalog's own rows for that ISIN checks the export's
    codes against what the vendor publishes for the same security, and a wrong
    BSE scrip beside a right NSE symbol is exactly the shape that direction
    catches. The ISIN itself stays CONFIRMED, because the NSE code did
    corroborate it — a per-field result, not one verdict for the row.
    """
    report = _report(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.DELTA_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    row = _rows_by_isin(report)[emf.ALPHA_ISIN]
    assert row.bse_code_corroborated == CorroborationOutcome.CONFLICTED
    assert row.nse_code_corroborated == CorroborationOutcome.CONFIRMED
    assert row.isin_outcome == CorroborationOutcome.CONFIRMED
    assert row.resolved_via == VIA_NSE


# C-04
def test_an_export_publishing_no_bse_code_is_not_covered_for_that_field(tmp_path: Path) -> None:
    """A field the export left empty is uncorroborated, not disagreeing.

    Several watchlist members legitimately carry no NSE code and a delisted one
    carries neither. ``None`` is "nothing to compare", and calling it a conflict
    would fail the run on a company nobody has a complaint about.
    """
    report = _report(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    row = _rows_by_isin(report)[emf.ALPHA_ISIN]
    assert row.bse_code_corroborated == CorroborationOutcome.NOT_COVERED
    assert row.nse_code_corroborated == CorroborationOutcome.CONFIRMED
    assert row.isin_outcome == CorroborationOutcome.CONFIRMED


# C-01
def test_a_watchlist_that_did_not_publish_results_is_refused_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """Same rule as ``load_s1_records``, and for the same reason.

    An artifact that stopped short records no membership. Corroborating its
    empty rows would report nothing conflicted and print a clean TOTAL line,
    turning a failed acquisition into a passing check.
    """
    watchlist = _write_incomplete_watchlist(tmp_path)
    catalog = write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE))
    with pytest.raises(WatchlistCorroborationError):
        corroborate_watchlist(watchlist, catalog)

    out = tmp_path / "out"
    argv = _argv(watchlist, catalog, out)
    assert build_parser().parse_args(argv).command == COMMAND

    assert main(argv) == EXIT_REFUSED
    assert not (out / REPORT_FILENAME).exists()


# C-01
def test_a_catalog_that_did_not_publish_ok_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """Same rule as ``load_upstox_records``: a drifted catalog corroborates nothing.

    A catalog whose outcome is not OK retains no equity rows, so every company
    would resolve to nothing and be published as NOT_COVERED — a report saying
    the watchlist is simply uncovered, when in truth the evidence never loaded.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.ALPHA_BSE)]
    )
    catalog = write_parsed_catalog(tmp_path, derivative_row())
    with pytest.raises(WatchlistCorroborationError):
        corroborate_watchlist(watchlist, catalog)

    out = tmp_path / "out"
    argv = _argv(watchlist, catalog, out)
    assert build_parser().parse_args(argv).command == COMMAND

    assert main(argv) == EXIT_REFUSED
    assert not (out / REPORT_FILENAME).exists()


# C-02
def test_a_repeated_nse_trading_symbol_makes_the_catalog_unable_to_corroborate(
    tmp_path: Path,
) -> None:
    """An ambiguous code is not evidence, and picking one row would invent one.

    Two NSE rows claiming one trading symbol mean the index cannot say which
    ISIN that symbol belongs to. Resolving it to whichever row happened to be
    read last would make the answer depend on the vendor's file order, and this
    command would then publish a CONFIRMED it cannot justify.
    """
    watchlist, catalog = _inputs(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.SHARED_NSE, bse=None)],
        _nse_row(emf.ALPHA_ISIN, emf.SHARED_NSE, token="10001"),
        _nse_row(emf.BRAVO_ISIN, emf.SHARED_NSE, token="10002"),
    )
    with pytest.raises(WatchlistCorroborationError):
        corroborate_watchlist(watchlist, catalog)


# C-06
def test_corroboration_opens_no_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both inputs are already retained, so the check must stay wholly offline.

    An offline check is re-runnable over the same two files by anyone, which is
    what makes a disagreement it reports auditable rather than a claim about one
    moment on one machine.
    """

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the corroboration read opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    report = _report(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.ALPHA_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    assert report.rows


# C-07
def test_the_command_writes_a_report_that_round_trips_and_prints_a_tsv_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The published surface: one file a human diffs, one table a shell reads.

    The invocation is parsed through :func:`build_parser` first, because argparse
    exits ``2`` on an unregistered command — the same code this repo uses for a
    refusal — so an exit-code assertion alone would pass against a command that
    was never wired up. The written file is parsed back through the report model
    so a truncated or half-serialised document cannot pass.
    """
    watchlist, catalog = _inputs(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.ALPHA_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    out = tmp_path / "out"
    argv = _argv(watchlist, catalog, out)
    assert build_parser().parse_args(argv).command == COMMAND
    assert SCREENER_WATCHLIST_CORROBORATE_COMMAND == COMMAND
    assert CLI_REPORT_FILENAME == REPORT_FILENAME

    assert main(argv) == EXIT_OK
    written = out / REPORT_FILENAME
    report = WatchlistCorroborationReport.model_validate_json(written.read_bytes())
    assert len(report.rows) == 1

    printed = capsys.readouterr().out.splitlines()
    assert SUMMARY_HEADER in printed
    assert any(line.startswith(TOTAL_PREFIX) for line in printed)


# C-07
def test_the_command_exits_refused_when_one_company_is_conflicted(tmp_path: Path) -> None:
    """A disagreement is the finding this command was built to surface.

    The sibling test above exits zero on an invocation whose only difference is
    that no company disagrees, so a non-zero here cannot be explained by a bad
    path, an unparsed flag or a command that always fails. The report is still
    written: a conflict is a result, and discarding it would leave the operator
    with an exit code and nothing to read.
    """
    watchlist, catalog = _inputs(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.BRAVO_NSE, bse=None)],
        _nse_row(emf.BRAVO_ISIN, emf.BRAVO_NSE),
    )
    out = tmp_path / "out"
    argv = _argv(watchlist, catalog, out)
    assert build_parser().parse_args(argv).command == COMMAND

    assert main(argv) == EXIT_REFUSED
    assert (out / REPORT_FILENAME).exists()


# C-08
def test_the_report_states_that_industry_is_not_corroborated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What this command does NOT close, said in the report rather than in a bead.

    Upstox publishes no industry field of any kind, so the export's industry and
    industry group remain its word alone after a clean run. A report that
    reported only what it checked would read as a full identity corroboration,
    and the next reader would take the swap residual as closed for those fields
    too.
    """
    watchlist, catalog = _inputs(
        tmp_path,
        [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.ALPHA_BSE)],
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    sentence = INDUSTRY_NOT_CORROBORATED
    assert "industry" in sentence.lower()

    argv = _argv(watchlist, catalog, tmp_path / "out")
    assert build_parser().parse_args(argv).command == COMMAND

    assert main(argv) == EXIT_OK
    assert sentence in capsys.readouterr().out
