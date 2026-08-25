"""CLI composition helpers for typed Tijori shareholding acquisition."""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.ingest.tijori_shareholding import TijoriShareholding
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)

TIJORI_SHAREHOLDING_COMMAND = "tijori-shareholding"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "tijori-shareholding"
_ARTIFACT_FILENAME = "shareholding.json"
_SUMMARY_HEADER = "stock\trows\tcolumns\tquarantined\tcomp_id"


def add_tijori_shareholding_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``fundamentals tijori-shareholding`` command."""
    parser = subparsers.add_parser(
        TIJORI_SHAREHOLDING_COMMAND,
        help="acquire the typed Tijori detailed shareholding table for one watchlist stock",
    )
    parser.add_argument("--stock", required=True, help="watchlist NSE symbol, e.g. TITAN")
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: data/raw/watchlist/tijori-shareholding/<stock>)",
    )
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml",
    )


def run_tijori_shareholding_command(
    args: argparse.Namespace,
    *,
    credentials: TijoriCredentials,
) -> TijoriShareholding:
    """Resolve one stock, fetch its shareholding page, and write the typed JSON."""
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
    shareholding = source.fetch_shareholding(
        slug=stock.identifiers.tijori_slug,
        expected_symbol=stock.symbol,
        expected_company_id=stock.identifiers.tijori_company_id,
    )

    out_dir = Path(args.out).resolve() if args.out else _DEFAULT_OUT_ROOT / stock.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _ARTIFACT_FILENAME
    preflight_out_paths((out_path,))
    write_json_no_clobber(out_path, shareholding.model_dump_json(indent=2) + "\n")
    structlog.get_logger("fundamentals.tijori_shareholding").info(
        "tijori_shareholding_written",
        stock=stock.symbol,
        rows=len(shareholding.rows),
        columns=len(shareholding.column_period_labels),
        quarantined_rows=shareholding.cardinality_mismatch_rows,
        identity_islands=shareholding.metadata.identity_island_ids,
        path=str(out_path),
    )
    return shareholding


def render_tijori_shareholding_summary(shareholding: TijoriShareholding) -> str:
    """Render deterministic row and column counts plus the verified company id."""
    row = "\t".join(
        (
            shareholding.metadata.symbol,
            str(len(shareholding.rows)),
            str(len(shareholding.column_period_labels)),
            str(len(shareholding.cardinality_mismatch_rows)),
            str(shareholding.metadata.company_id),
        )
    )
    return "\n".join((_SUMMARY_HEADER, row))
