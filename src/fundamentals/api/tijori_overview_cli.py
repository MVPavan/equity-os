"""CLI composition helpers for typed Tijori overview-section acquisition."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewSection,
    TijoriOverviewSectionBase,
)
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)

TIJORI_OVERVIEW_COMMAND = "tijori-overview"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-overview"
_SUMMARY_HEADER = "section\tisland\tstatus\telements\tplan_tier"
_UNKNOWN_PLAN_TIER = "unknown"
_NOT_BUILT = "-"


def add_tijori_overview_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-overview`` command."""
    parser = subparsers.add_parser(
        TIJORI_OVERVIEW_COMMAND,
        help="acquire the typed Tijori overview-page data sections for one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--section",
        choices=tuple(section.value for section in TijoriOverviewSection),
        default=None,
        help="one overview section (default: every section published on the page)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-overview/<stock>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def run_tijori_overview_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> tuple[TijoriOverviewSectionBase, ...]:
    """Resolve one stock, fetch one overview page, and write its section JSON files."""
    config_path = Path(args.config).resolve()
    watchlist = load_watchlist_config(config_path)
    try:
        stock = watchlist.stock(args.stock)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unverified = stock.identifiers.unverified_tijori_fields()
    if unverified:
        raise SystemExit(
            f"Tijori identifiers for {stock.symbol} are not verified: {', '.join(unverified)}"
        )

    source = TijoriSource(TijoriSourceConfig(credentials=credentials))
    sections = source.fetch_overview(
        slug=stock.identifiers.tijori_slug,
        expected_symbol=stock.symbol,
        expected_company_id=stock.identifiers.tijori_company_id,
        section=None if args.section is None else TijoriOverviewSection(args.section),
    )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths = tuple(out_dir / f"{built.section.value}.json" for built in sections)
    preflight_out_paths(out_paths)
    logger = structlog.get_logger("fundamentals.tijori_overview")
    for built, out_path in zip(sections, out_paths, strict=True):
        write_json_no_clobber(out_path, built.model_dump_json(indent=2) + "\n")
        logger.info(
            "tijori_overview_section_written",
            stock=stock.symbol,
            section=built.section.value,
            island=built.island_id,
            elements=built.element_count,
            path=str(out_path),
        )
    return sections


def render_tijori_overview_summary(sections: tuple[TijoriOverviewSectionBase, ...]) -> str:
    """Render one deterministic line per section the page declares.

    Every section is listed, including the ones the page does not publish, so an
    absent section is visible in the run output rather than inferred from a
    missing file.
    """
    if not sections:
        return _SUMMARY_HEADER
    metadata = sections[0].metadata
    built = {section.section: section for section in sections}
    lines = [_SUMMARY_HEADER]
    lines.extend(
        "\t".join(
            (
                outcome.section.value,
                outcome.island_id,
                outcome.status.value,
                (
                    str(built[outcome.section].element_count)
                    if outcome.section in built
                    else _NOT_BUILT
                ),
                metadata.access.plan_tier or _UNKNOWN_PLAN_TIER,
            )
        )
        for outcome in metadata.section_outcomes
    )
    return "\n".join(lines)
