"""CLI composition helpers for typed Tijori financial-table acquisition."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.ingest.tijori_tables import TijoriTable, TijoriTableKey

TIJORI_TABLES_COMMAND = "tijori-tables"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-tables"
_SUMMARY_HEADER = "table\trows\tcolumns\tplan_tier"
_UNKNOWN_PLAN_TIER = "unknown"


def add_tijori_tables_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-tables`` command."""
    parser = subparsers.add_parser(
        TIJORI_TABLES_COMMAND,
        help="acquire typed raw Tijori financial tables for one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--table",
        choices=tuple(key.value for key in TijoriTableKey),
        default=None,
        help="one table key (default: every table in fin_tables_data)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-tables/<stock>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def run_tijori_tables_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> tuple[TijoriTable, ...]:
    """Resolve one stock, fetch one page, and write its typed table JSON files."""
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

    # The financials page already publishes company_details.company_id; asserting
    # it equals the configured id is an extra conjunctive identity constraint.
    source = TijoriSource(
        TijoriSourceConfig(
            credentials=credentials,
            expected_company_id=stock.identifiers.tijori_company_id,
        )
    )
    if args.table is None:
        tables = source.fetch_all_tables(
            slug=stock.identifiers.tijori_slug,
            expected_symbol=stock.symbol,
        )
    else:
        tables = (
            source.fetch_table(
                args.table,
                slug=stock.identifiers.tijori_slug,
                expected_symbol=stock.symbol,
            ),
        )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths = tuple(out_dir / f"{table.key.value}.json" for table in tables)
    preflight_out_paths(out_paths)
    logger = structlog.get_logger("fundamentals.tijori_tables")
    for table, out_path in zip(tables, out_paths, strict=True):
        write_json_no_clobber(out_path, table.model_dump_json(indent=2) + "\n")
        logger.info(
            "tijori_table_written",
            stock=stock.symbol,
            table=table.key.value,
            rows=len(table.rows),
            columns=len(table.column_period_labels),
            plan_tier=table.metadata.access.plan_tier,
            unknown_island_keys=table.metadata.observed_unknown_table_keys,
            path=str(out_path),
        )
    return tables


def render_tijori_tables_summary(tables: tuple[TijoriTable, ...]) -> str:
    """Render deterministic row, column, and access counts for stdout."""
    lines = [_SUMMARY_HEADER]
    lines.extend(
        "\t".join(
            (
                table.key.value,
                str(len(table.rows)),
                str(len(table.column_period_labels)),
                table.metadata.access.plan_tier or _UNKNOWN_PLAN_TIER,
            )
        )
        for table in tables
    )
    return "\n".join(lines)
