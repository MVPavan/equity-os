"""Unit tests for the corroboration report's provenance, counts and rendering.

The acceptance suite pins the outcomes; nothing there reads the header the
report carries about its own inputs. A report that named the wrong bytes would
still pass every outcome test while being unauditable, so the digests, the
timestamps and the counts are checked here against the two producers' own
metadata.

Every input is synthetic and written to a tmp path: these tests read files, and
never the repository's retained data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import entity_map_fixtures as emf
import pytest
import upstox_fixtures as uf
from pydantic import ValidationError

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.api.screener_watchlist_corroborate_cli import (
    REPORT_FILENAME,
    SCREENER_WATCHLIST_CORROBORATE_COMMAND,
    SUMMARY_HEADER,
    TOTAL_LABEL,
    render_corroboration_summary,
)
from fundamentals.ingest.screener_watchlist_corroborate import (
    INDUSTRY_NOT_CORROBORATED,
    CorroborationOutcome,
    WatchlistCorroborationError,
    WatchlistCorroborationReport,
    corroborate_watchlist,
)
from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistCell,
    WatchlistRow,
)
from fundamentals.ingest.upstox_instruments import UpstoxInstrumentCatalog

EARLIER = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 2, 5, 0, tzinfo=UTC)

WATCHLIST_FILENAME = "screener_watchlist.json"


def _listing(index: int, isin_code: str, *, nse: str | None, bse: str | None) -> emf.Listing:
    """One synthetic watchlist member stating an ISIN and its exchange codes."""
    return emf.Listing(
        company_id=9300000 + index,
        slug=None,
        display_name=f"Fixture Company {index} Limited",
        isin_code=isin_code,
        nse_code=nse,
        bse_code=bse,
    )


def _nse_row(isin_code: str, symbol: str, token: str) -> dict[str, object]:
    """One ``NSE_EQ`` catalog row binding a trading symbol to an ISIN."""
    return uf.nse_equity_row(
        isin=isin_code,
        instrument_key=f"NSE_EQ|{isin_code}",
        trading_symbol=symbol,
        exchange_token=token,
    )


def _bse_row(isin_code: str, scrip: str) -> dict[str, object]:
    """One ``BSE_EQ`` catalog row binding an exchange token to an ISIN."""
    return uf.bse_equity_row(
        isin=isin_code,
        instrument_key=f"BSE_EQ|{isin_code}",
        trading_symbol=f"BSE{scrip}",
        exchange_token=scrip,
    )


def _directory(parent: Path, name: str) -> Path:
    """One created child directory, for a test writing two catalogs side by side."""
    path = parent / name
    path.mkdir()
    return path


def _argv(watchlist: Path, catalog: Path, out: Path) -> list[str]:
    """One CLI invocation over two named inputs and an output directory."""
    return [
        SCREENER_WATCHLIST_CORROBORATE_COMMAND,
        "--watchlist",
        str(watchlist),
        "--upstox-catalog",
        str(catalog),
        "--out",
        str(out),
    ]


def _cell(stamp: datetime) -> WatchlistCell:
    """One value cell whose provenance records the given retrieval time."""
    return WatchlistCell(
        csv_field_index=0,
        value=None,
        csv_text="",
        html_text="",
        provenance=emf.provenance(emf.S1_SOURCE_ID).model_copy(update={"retrieved_at": stamp}),
    )


def _write_stamped_watchlist(directory: Path, *stamps: datetime) -> Path:
    """Write a watchlist artifact whose single member carries the given cell stamps."""
    artifact = emf.watchlist_artifact([_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None)])
    stamped = WatchlistRow(
        serial_number=artifact.rows[0].serial_number,
        company=artifact.rows[0].company,
        cells=tuple(_cell(stamp) for stamp in stamps),
    )
    path = directory / WATCHLIST_FILENAME
    path.write_text(
        WatchlistArtifact(
            outcome=artifact.outcome,
            columns=artifact.columns,
            rows=(stamped,),
            cross_check=artifact.cross_check,
        ).model_dump_json(),
        encoding="utf-8",
    )
    return path


def test_the_report_names_the_bytes_both_producers_recorded(tmp_path: Path) -> None:
    """A finding is only auditable against the exact inputs that produced it.

    Every digest is the producer's own — the catalog's ``content_sha256`` and
    the watchlist's two cross-check digests — rather than a hash this command
    took of the files it happened to open, so the report's header can be
    compared against the artifacts themselves.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None)]
    )
    catalog_path = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))
    catalog = UpstoxInstrumentCatalog.model_validate_json(catalog_path.read_bytes())

    report = corroborate_watchlist(watchlist, catalog_path)

    assert report.catalog_sha256 == catalog.content_sha256
    assert report.catalog_retrieved_at == catalog.retrieved_at
    assert report.watchlist_html_sha256 == emf.FIXTURE_SHA256
    assert report.watchlist_export_sha256 == emf.FIXTURE_SHA256
    assert report.industry_note == INDUSTRY_NOT_CORROBORATED


def test_the_watchlist_retrieval_time_is_the_earliest_the_artifact_records(tmp_path: Path) -> None:
    """Read from the artifact's own cells, never from the filesystem.

    An mtime is restamped by any clone or checkout, so a report derived from it
    would disagree with itself over identical bytes. The earliest recorded cell
    stamp is the one time the artifact can actually vouch for.
    """
    watchlist = _write_stamped_watchlist(tmp_path, LATER, EARLIER)
    catalog = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))

    assert corroborate_watchlist(watchlist, catalog).watchlist_retrieved_at == EARLIER


def test_an_artifact_recording_no_retrieval_time_says_so(tmp_path: Path) -> None:
    """``None`` is "the artifact records none", which is not a time to invent."""
    watchlist = _write_stamped_watchlist(tmp_path)
    catalog = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))

    assert corroborate_watchlist(watchlist, catalog).watchlist_retrieved_at is None


def test_a_code_field_disagreement_alone_makes_the_report_conflicted(tmp_path: Path) -> None:
    """A wrong exchange code is a real identity disagreement, not a coverage gap.

    The ISIN here is confirmed by the NSE code, so a report that only weighed
    ``isin_outcome`` would exit clean while publishing a BSE scrip the vendor
    states differently for that very security.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.DELTA_BSE)]
    )
    catalog = uf.write_parsed_catalog(
        tmp_path,
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )

    report = corroborate_watchlist(watchlist, catalog)

    assert report.rows[0].isin_outcome is CorroborationOutcome.CONFIRMED
    assert report.rows[0].bse_code_corroborated is CorroborationOutcome.CONFLICTED
    assert report.has_conflict()


def test_the_summary_counts_every_member_once_and_names_what_it_did_not_check(
    tmp_path: Path,
) -> None:
    """The rendered table is the surface a shell reads, so its total must add up.

    Three members, one of each outcome: a total that agreed with the rows only
    on a uniform report would be worthless exactly when a run has mixed results.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path,
        [
            _listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None),
            _listing(2, emf.BRAVO_ISIN, nse=emf.CHARLIE_NSE, bse=None),
            _listing(3, emf.DELTA_ISIN, nse=emf.ZULU_NSE, bse=None),
        ],
    )
    catalog = uf.write_parsed_catalog(
        tmp_path,
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"),
        _nse_row(emf.CHARLIE_ISIN, emf.CHARLIE_NSE, "2"),
    )

    report = corroborate_watchlist(watchlist, catalog)
    lines = render_corroboration_summary(report).splitlines()

    assert (report.confirmed_count, report.conflicted_count, report.not_covered_count) == (1, 1, 1)
    assert lines[0] == SUMMARY_HEADER
    assert len(lines) == len(report.rows) + 3
    assert lines[-2].split("\t") == [TOTAL_LABEL, "confirmed=1", "conflicted=1", "not_covered=1"]
    assert lines[-1] == INDUSTRY_NOT_CORROBORATED


def test_a_named_input_that_is_not_there_is_refused_by_name(tmp_path: Path) -> None:
    """A mistyped path is a caller defect, and it is told as one.

    An unhandled ``FileNotFoundError`` would reach the operator as a traceback on
    exit 1 — indistinguishable from this command crashing, and impossible for a
    shell loop to tell apart from a real finding.
    """
    catalog = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))
    out = tmp_path / "out"

    assert main(_argv(tmp_path / "no-such-watchlist.json", catalog, out)) == EXIT_REFUSED
    assert not out.exists()


def test_a_report_target_that_is_not_a_regular_file_is_refused(tmp_path: Path) -> None:
    """The command publishes into a path it owns, or it publishes nothing.

    Writing through whatever happens to sit at the target — a symlink, or a
    directory left by another tool — would put a report somewhere nobody asked
    for it, or destroy something this command did not create.
    """
    out = tmp_path / "out"
    (out / REPORT_FILENAME).mkdir(parents=True)
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None)]
    )
    catalog = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))

    assert main(_argv(watchlist, catalog, out)) == EXIT_REFUSED
    assert (out / REPORT_FILENAME).is_dir()


def test_two_bse_rows_sharing_one_scrip_are_refused_apart_from_one_row_stated_twice(
    tmp_path: Path,
) -> None:
    """Both repeats refuse, and the two refusals do not read alike.

    One scrip on two securities means the index cannot say which ISIN it belongs
    to; one security stated twice means the file repeats a row. An operator
    chases those two faults in completely different places, so a single shared
    message would send them to the wrong one.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=None, bse=emf.SHARED_BSE)]
    )
    ambiguous = uf.write_parsed_catalog(
        _directory(tmp_path, "ambiguous"),
        _bse_row(emf.ALPHA_ISIN, emf.SHARED_BSE),
        _bse_row(emf.BRAVO_ISIN, emf.SHARED_BSE),
    )
    duplicated = uf.write_parsed_catalog(
        _directory(tmp_path, "duplicated"),
        _bse_row(emf.ALPHA_ISIN, emf.SHARED_BSE),
        _bse_row(emf.ALPHA_ISIN, emf.SHARED_BSE),
    )

    with pytest.raises(WatchlistCorroborationError) as two_securities:
        corroborate_watchlist(watchlist, ambiguous)
    with pytest.raises(WatchlistCorroborationError) as one_security_twice:
        corroborate_watchlist(watchlist, duplicated)

    assert emf.BRAVO_ISIN in str(two_securities.value)
    assert emf.BRAVO_ISIN not in str(one_security_twice.value)
    assert str(two_securities.value) != str(one_security_twice.value)


def test_the_command_exits_refused_when_only_a_code_field_disagrees(tmp_path: Path) -> None:
    """The exit code weighs the code fields, not only the ISIN verdict.

    This run's ISIN is confirmed by its NSE symbol, so a command that gated on
    ``isin_outcome`` alone would exit clean while publishing a BSE scrip the
    vendor states differently for that very security — a wrong identifier
    leaving a green run behind it.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=emf.DELTA_BSE)]
    )
    catalog = uf.write_parsed_catalog(
        tmp_path,
        _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"),
        _bse_row(emf.ALPHA_ISIN, emf.ALPHA_BSE),
    )
    out = tmp_path / "out"

    assert main(_argv(watchlist, catalog, out)) == EXIT_REFUSED

    published = WatchlistCorroborationReport.model_validate_json(
        (out / REPORT_FILENAME).read_bytes()
    )
    assert published.rows[0].isin_outcome is CorroborationOutcome.CONFIRMED
    assert published.rows[0].bse_code_corroborated is CorroborationOutcome.CONFLICTED


def test_a_report_may_not_restate_what_it_did_not_corroborate(tmp_path: Path) -> None:
    """The industry sentence is pinned, so it cannot be softened or dropped.

    It is the only place a clean run says what it did NOT check. A report free
    to carry any sentence there is free to carry a reassuring one.
    """
    watchlist = emf.write_s1_artifact(
        tmp_path, [_listing(1, emf.ALPHA_ISIN, nse=emf.ALPHA_NSE, bse=None)]
    )
    catalog = uf.write_parsed_catalog(tmp_path, _nse_row(emf.ALPHA_ISIN, emf.ALPHA_NSE, "1"))
    report = corroborate_watchlist(watchlist, catalog)

    rewritten = report.model_dump() | {"industry_note": "everything checks out"}
    with pytest.raises(ValidationError, match="industry_note"):
        WatchlistCorroborationReport.model_validate(rewritten)
