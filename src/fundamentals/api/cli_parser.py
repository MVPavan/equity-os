"""Argument-parser registration for the Fundamentals composition root."""

from __future__ import annotations

import argparse
from pathlib import Path

from fundamentals.api.adjudication_cli import add_adjudication_parser
from fundamentals.api.config import XbrlMode
from fundamentals.api.news_cli import add_news_parser
from fundamentals.api.screener_company_cli import add_screener_company_parser
from fundamentals.api.screener_financials_cli import add_screener_financials_parser
from fundamentals.api.screener_page_cli import add_screener_page_parser
from fundamentals.api.screener_screen_cli import add_screener_screen_parser
from fundamentals.api.thesis_cli import add_thesis_parser, add_wave_arg
from fundamentals.api.tijori_analysis_cli import add_tijori_analysis_parser
from fundamentals.api.tijori_events_cli import add_tijori_events_parser
from fundamentals.api.tijori_overview_cli import add_tijori_overview_parser
from fundamentals.api.tijori_shareholding_cli import add_tijori_shareholding_parser
from fundamentals.api.tijori_tables_cli import add_tijori_tables_parser

RUN_COMMAND = "run"
VALIDATE_COMMAND = "validate"
REPORT_COMMAND = "report"
THESIS_COMMAND = "thesis"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DESCRIPTION = "Run source-backed Fundamentals acquisition, validation, and reporting commands."


def build_parser() -> argparse.ArgumentParser:
    """Build the ``fundamentals`` argument parser."""
    parser = argparse.ArgumentParser(prog="fundamentals", description=_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser(RUN_COMMAND, help="run the source-verified earnings update")
    run.add_argument("--issuer", required=True, help="issuer symbol, e.g. INFY")
    run.add_argument("--quarter", required=True, help="issuer quarter, e.g. Q1-FY25")
    run.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG_PATH),
        help="path to fundamentals.yaml (default: repo config/fundamentals.yaml)",
    )
    run.add_argument(
        "--xbrl-mode",
        choices=[mode.value for mode in XbrlMode],
        default=None,
        help="override the configured XBRL retrieval mode (local | live)",
    )
    run.add_argument("--out", default=None, help="write the markdown to a file instead of stdout")

    validate = subparsers.add_parser(
        VALIDATE_COMMAND,
        help="cross-check the watchlist across every available source (gold loop)",
    )
    scope = validate.add_mutually_exclusive_group()
    scope.add_argument(
        "--watchlist",
        action="store_true",
        help="validate every stock, rolling each wave up under its own <wave>-rollup.json",
    )
    scope.add_argument("--symbol", default=None, help="validate a single stock, e.g. TITAN")
    add_wave_arg(validate)
    validate.add_argument(
        "--quarter",
        default=None,
        help=(
            "assert the reviewed quarter label, e.g. Q3FY25; or 'latest' to target the "
            "newest completed quarter BSE publishes and align NSE/Screener to it"
        ),
    )
    validate.add_argument(
        "--sources",
        default=None,
        help="comma-separated sources to pull (default: all): nse,bse,screener,tijori,pdf,sec",
    )
    fetch = validate.add_mutually_exclusive_group()
    fetch.add_argument(
        "--live", action="store_true", help="fetch sources live (polite, owner-authorized)"
    )
    fetch.add_argument(
        "--fixture",
        action="store_true",
        help="read committed/local fixtures instead of the network (default)",
    )
    validate.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml (default: repo config/watchlist.yaml)",
    )
    validate.add_argument(
        "--report-dir", default=None, help="write per-stock + roll-up JSON reports here"
    )
    validate.add_argument(
        "--gold-dir", default=None, help="override the gold-file output directory"
    )

    report = subparsers.add_parser(
        REPORT_COMMAND,
        help="render the per-stock source-verified earnings update from CACHED data",
    )
    report_scope = report.add_mutually_exclusive_group()
    report_scope.add_argument(
        "--watchlist",
        action="store_true",
        help="render every watchlist stock (optionally one --wave)",
    )
    report_scope.add_argument("--symbol", default=None, help="render a single stock, e.g. MTARTECH")
    add_wave_arg(report)
    report.add_argument(
        "--quarter", default=None, help="assert the reviewed quarter label, e.g. Q3FY25"
    )
    report.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml (default: repo config/watchlist.yaml)",
    )
    report.add_argument(
        "--out-dir",
        default=None,
        help="directory for rendered .md reports (default: docs/research/validation/reports)",
    )
    report.add_argument(
        "--gold-dir",
        default=None,
        help="override the scratch gold directory the cached reconcile writes to",
    )

    add_thesis_parser(
        subparsers,
        command=THESIS_COMMAND,
        default_watchlist_path=_DEFAULT_WATCHLIST_PATH,
    )
    add_news_parser(subparsers)
    add_adjudication_parser(subparsers)
    add_tijori_tables_parser(subparsers)
    add_tijori_shareholding_parser(subparsers)
    add_tijori_overview_parser(subparsers)
    add_tijori_analysis_parser(subparsers)
    add_tijori_events_parser(subparsers)
    add_screener_page_parser(subparsers)
    add_screener_screen_parser(subparsers)
    add_screener_financials_parser(subparsers)
    add_screener_company_parser(subparsers)
    return parser
