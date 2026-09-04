"""The ``screener-watchlist-corroborate`` command: check the export against Upstox.

    screener-watchlist-corroborate --watchlist <artifact.json>
                                   --upstox-catalog <parsed_catalog.json>
                                   --out <dir>

Both inputs are already retained, so the run is wholly offline: it opens no
socket and needs no credential. It writes one report a human diffs and prints
one table a shell reads.

A disagreement exits non-zero, because a disagreement is the finding this
command exists to surface — but the report is still written. A conflict is a
result, and discarding it would leave the operator with an exit code and
nothing to read. Only a refused input publishes nothing at all. A member the
catalog does not cover never affects the exit code: our own filter is not a
statement about the company.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.ingest.screener_watchlist_corroborate import (
    CorroborationRow,
    WatchlistCorroborationError,
    WatchlistCorroborationReport,
    corroborate_watchlist,
)

SCREENER_WATCHLIST_CORROBORATE_COMMAND = "screener-watchlist-corroborate"
REPORT_FILENAME = "watchlist_corroboration.json"
SUMMARY_HEADER = "name\tisin\tisin_outcome\tresolved_isin\tresolved_via\tnse_code\tbse_code"
TOTAL_LABEL = "TOTAL"

_HELP = "corroborate a published watchlist's ISINs and exchange codes against Upstox"
_WATCHLIST_FLAG = "--watchlist"
_CATALOG_FLAG = "--upstox-catalog"
_OUT_FLAG = "--out"
_WATCHLIST_HELP = "path to a published screener-watchlist artifact JSON"
_CATALOG_HELP = "path to a retained Upstox instrument catalog JSON"
_OUT_HELP = "directory the corroboration report is written into"

_ABSENT = ""
_CONFIRMED_TOTAL = "confirmed={count}"
_CONFLICTED_TOTAL = "conflicted={count}"
_NOT_COVERED_TOTAL = "not_covered={count}"
_UNSAFE_OUT = "refusing unsafe corroboration report path: {path}"
_LOGGER_NAME = "fundamentals.screener_watchlist_corroborate"
_REFUSED_EVENT = "watchlist_corroboration_refused"
_WRITTEN_EVENT = "watchlist_corroboration_written"


def add_screener_watchlist_corroborate_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``screener-watchlist-corroborate`` and its three paths.

    Every path is required rather than defaulted: this command names one
    published artifact against one retained catalog, and a caller who mistyped
    either must be told rather than quietly given some other run's files.
    """
    parser = subparsers.add_parser(SCREENER_WATCHLIST_CORROBORATE_COMMAND, help=_HELP)
    parser.add_argument(_WATCHLIST_FLAG, required=True, help=_WATCHLIST_HELP)
    parser.add_argument(_CATALOG_FLAG, required=True, help=_CATALOG_HELP)
    parser.add_argument(_OUT_FLAG, required=True, help=_OUT_HELP)


def dispatch_screener_watchlist_corroborate_command(args: argparse.Namespace) -> int | None:
    """Run the corroboration and return its exit code, or ``None`` for another command.

    Every refusal this command can reach is typed, so a mistyped path, a file
    that is not the artifact it was named as, an incomplete artifact, a drifted
    catalog or an ambiguous exchange code all leave the same ``EXIT_REFUSED``
    its sibling commands use rather than a traceback that reads as a crash.
    """
    if getattr(args, "command", None) != SCREENER_WATCHLIST_CORROBORATE_COMMAND:
        return None
    logger = structlog.get_logger(_LOGGER_NAME)
    try:
        report = corroborate_watchlist(Path(args.watchlist), Path(args.upstox_catalog))
        out_path = write_corroboration_report(Path(args.out), report)
    except WatchlistCorroborationError as refusal:
        logger.warning(_REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal))
        return EXIT_REFUSED
    logger.info(
        _WRITTEN_EVENT,
        report=str(out_path),
        rows=len(report.rows),
        conflicted=report.conflicted_count,
    )
    sys.stdout.write(render_corroboration_summary(report) + "\n")
    return EXIT_REFUSED if report.has_conflict() else EXIT_OK


def write_corroboration_report(out_dir: Path, report: WatchlistCorroborationReport) -> Path:
    """Publish the report into ``out_dir`` and return the path written.

    Replaced rather than refused on a re-run: the report is derived from two
    retained files, not evidence itself, so re-running it over unchanged inputs
    is expected to leave the same document. A symlink or a non-regular file at
    the target is refused BEFORE the output directory is created, so a run that
    will not publish leaves no directory tree behind either.
    """
    out_path = out_dir / REPORT_FILENAME
    if out_path.is_symlink() or (out_path.exists() and not out_path.is_file()):
        raise WatchlistCorroborationError(_UNSAFE_OUT.format(path=out_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return out_path


def render_corroboration_summary(report: WatchlistCorroborationReport) -> str:
    """Render the report as a TSV: one line per member, a total, then what was not checked."""
    return "\n".join(
        (
            SUMMARY_HEADER,
            *(_summary_line(row) for row in report.rows),
            "\t".join(
                (
                    TOTAL_LABEL,
                    _CONFIRMED_TOTAL.format(count=report.confirmed_count),
                    _CONFLICTED_TOTAL.format(count=report.conflicted_count),
                    _NOT_COVERED_TOTAL.format(count=report.not_covered_count),
                )
            ),
            report.industry_note,
        )
    )


def _summary_line(row: CorroborationRow) -> str:
    """One member's line, with an empty field wherever nothing was published."""
    return "\t".join(
        (
            row.name,
            row.isin,
            row.isin_outcome.value,
            row.resolved_isin or _ABSENT,
            _ABSENT if row.resolved_via is None else row.resolved_via.value,
            row.nse_code or _ABSENT,
            row.bse_code or _ABSENT,
        )
    )
