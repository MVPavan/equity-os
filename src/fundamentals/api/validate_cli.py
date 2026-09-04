"""Dispatch and command implementation for ``fundamentals validate``.

Extracted verbatim from :mod:`fundamentals.api.cli` so the composition root
stays inside its file-size bound. The gold loop itself is unchanged: the
command still returns one roll-up per wave run and the dispatcher still writes
the JSON array to stdout while diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import TypeAdapter

from fundamentals.api.cli_parser import VALIDATE_COMMAND
from fundamentals.api.env_credentials import _tijori_credentials_from_env
from fundamentals.api.goal_runner import (
    ALL_SOURCE_KINDS,
    QuarterMode,
    RunMode,
    SourceKind,
    StockReport,
    WaveReport,
    run_stock,
    run_wave,
)
from fundamentals.api.watchlist_config import WatchlistConfig, load_watchlist_config
from fundamentals.api.wave_selection import _require_symbol_in_wave, _selected_wave
from fundamentals.reconcile.gold_file import DEFAULT_GOLD_DIR

_CLI_LOGGER_NAME = "fundamentals.cli"
_QUARTER_LATEST = "latest"

# Serializes a per-wave roll-up sequence to a single JSON array for stdout.
_WAVE_REPORTS_ADAPTER: TypeAdapter[tuple[WaveReport, ...]] = TypeAdapter(tuple[WaveReport, ...])


def _parse_source_kinds(raw: str | None) -> frozenset[SourceKind]:
    """Parse a ``--sources nse,bse,...`` list into source kinds, or all when absent."""
    if not raw:
        return ALL_SOURCE_KINDS
    kinds: set[SourceKind] = set()
    for token in raw.split(","):
        name = token.strip().lower()
        if not name:
            continue
        try:
            kinds.add(SourceKind(name))
        except ValueError as error:
            valid = ", ".join(kind.value for kind in SourceKind)
            raise SystemExit(f"unknown source {name!r}; choose from: {valid}") from error
    if not kinds:
        return ALL_SOURCE_KINDS
    return frozenset(kinds)


def _write_reports(report_dir: Path, wave: WaveReport) -> None:
    """Write the per-stock reports and the wave roll-up as JSON under ``report_dir``."""
    report_dir.mkdir(parents=True, exist_ok=True)
    for stock in wave.stocks:
        path = report_dir / f"{stock.symbol}-{stock.quarter}.json"
        path.write_text(stock.model_dump_json(indent=2) + "\n", encoding="utf-8")
    rollup = report_dir / f"{wave.wave}-rollup.json"
    rollup.write_text(wave.model_dump_json(indent=2) + "\n", encoding="utf-8")


def validate_command(args: argparse.Namespace) -> tuple[WaveReport, ...]:
    """Execute the ``validate`` subcommand and return one roll-up per wave run.

    ``--symbol`` returns that stock's own-wave roll-up; ``--wave`` scopes the run to
    one wave (on its own, or narrowing ``--watchlist``); a plain ``--watchlist`` runs
    every wave and returns one roll-up each, so their ``<wave>-rollup.json`` files
    never collide.
    """
    selected_wave = _selected_wave(args)
    if not args.watchlist and not args.symbol and selected_wave is None:
        raise SystemExit("validate requires --watchlist, --symbol <X>, or --wave <Wave-1|Wave-2>")

    config_path = Path(args.config).resolve()
    config: WatchlistConfig = load_watchlist_config(config_path)
    repo_root = config.repo_root(config_path)
    mode = RunMode.LIVE if args.live else RunMode.FIXTURE
    kinds = _parse_source_kinds(args.sources)
    out_dir = Path(args.gold_dir) if args.gold_dir else DEFAULT_GOLD_DIR
    credentials = _tijori_credentials_from_env() if mode is RunMode.LIVE else None
    latest = bool(args.quarter) and args.quarter.strip().lower() == _QUARTER_LATEST
    quarter_mode = QuarterMode.LATEST if latest else QuarterMode.PINNED

    if args.symbol:
        stock = config.stock(args.symbol)
        _require_symbol_in_wave(stock, selected_wave)
        if not latest and args.quarter and args.quarter.upper() != stock.quarter.label.upper():
            raise SystemExit(
                f"quarter {args.quarter!r} does not match configured quarter "
                f"{stock.quarter.label!r} for {stock.symbol}"
            )
        report = run_stock(
            stock,
            mode=mode,
            repo_root=repo_root,
            kinds=kinds,
            tijori_credentials=credentials,
            out_dir=out_dir,
            quarter_mode=quarter_mode,
        )
        waves: tuple[WaveReport, ...] = (
            WaveReport(wave=stock.wave, quarter_labels=(report.quarter,), stocks=(report,)),
        )
    else:
        target_waves = (selected_wave,) if selected_wave is not None else config.waves()
        waves = tuple(
            run_wave(
                config,
                wave=wave,
                mode=mode,
                repo_root=repo_root,
                kinds=kinds,
                tijori_credentials=credentials,
                out_dir=out_dir,
                quarter_mode=quarter_mode,
            )
            for wave in target_waves
        )

    if args.report_dir:
        report_dir = Path(args.report_dir)
        for wave_report in waves:
            _write_reports(report_dir, wave_report)
    return waves


def _stock_summary_line(report: StockReport) -> str:
    """One-line human summary of a stock report for stderr."""
    return (
        f"{report.symbol} ({report.domain}): {report.outcome.value.upper()} — "
        f"{len(report.facts)} facts, {len(report.discrepancies)} discrepancies, "
        f"sources={list(report.available_sources)}"
    )


def dispatch_validate_command(args: argparse.Namespace) -> int | None:
    """Run the ``validate`` command, or return ``None`` for any other command."""
    if args.command != VALIDATE_COMMAND:
        return None
    logger = structlog.get_logger(_CLI_LOGGER_NAME)
    logger.info(
        "validate_invoked",
        watchlist=args.watchlist,
        symbol=args.symbol,
        wave=args.wave,
        live=args.live,
        started_at=datetime.now(UTC).isoformat(),
    )
    waves = validate_command(args)
    for wave_report in waves:
        for stock in wave_report.stocks:
            logger.info("stock_summary", summary=_stock_summary_line(stock))
        logger.info(
            "wave_summary",
            wave=wave_report.wave.value,
            done=wave_report.done_count,
            blocked=wave_report.blocked_count,
            all_done=wave_report.all_done,
        )
    sys.stdout.write(_WAVE_REPORTS_ADAPTER.dump_json(waves, indent=2).decode() + "\n")
    return 0
