"""Dispatch and command implementation for ``fundamentals report``.

Extracted verbatim from :mod:`fundamentals.api.cli` so the composition root
stays inside its file-size bound. The command still renders each stock's update
from the held raw first-party bytes only — no live fetch — and still writes the
paths it produced to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog

from fundamentals.api.cli_parser import REPORT_COMMAND
from fundamentals.api.comparatives import derive_comparator_periods
from fundamentals.api.config import SourceFileConfig
from fundamentals.api.goal_runner import RunMode, SourceKind, run_stock
from fundamentals.api.report_builder import ReportBuildError, render_report
from fundamentals.api.watchlist_config import (
    FixturePaths,
    StockConfig,
    WatchlistConfig,
    load_watchlist_config,
)
from fundamentals.api.wave_selection import _require_symbol_in_wave, _selected_wave
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.source_catalog import SourceClass
from fundamentals.ingest.bse_pdf_source import SOURCE_ID as BSE_RESULTS_PDF_SOURCE_ID
from fundamentals.ingest.comparator_cache import RAW_WATCHLIST_DIR, cached_comparator_path
from fundamentals.ingest.ocr_engine import RapidOcrEngine

_CLI_LOGGER_NAME = "fundamentals.cli"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REPORT_DIR = _REPO_ROOT / "docs" / "research" / "validation" / "reports"
# The cached report reconciles the two first-party sources whose raw bytes are
# held on disk (NSE Ind AS XBRL + BSE issuer results PDF); no live fetch.
_REPORT_SOURCE_KINDS: frozenset[SourceKind] = frozenset({SourceKind.NSE, SourceKind.PDF})


def _sha256_file(path: Path) -> str:
    """Return the hex sha256 of a file's bytes (self-verifying provenance stamp)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cached_stock(stock: StockConfig, repo_root: Path) -> StockConfig:
    """Point a stock at its already-downloaded raw NSE XBRL + BSE results PDF.

    Wave-1 stocks carry no committed fixtures; the report command reconciles from
    the raw bytes a prior live run left under ``data/raw/watchlist/<symbol>/`` so it
    never touches the network. A missing raw file leaves that source unconfigured
    (skipped), so the reconcile fails closed rather than fabricating a value.
    """
    lower = stock.symbol.lower()
    nse_dir = repo_root / RAW_WATCHLIST_DIR / lower / "nse"
    pdf_dir = repo_root / RAW_WATCHLIST_DIR / lower / "bse_pdf"
    nse = next(iter(sorted(nse_dir.glob("*.xml"))), None) if nse_dir.is_dir() else None
    periods = derive_comparator_periods(stock.quarter.period_start, stock.quarter.period_end)
    qoq_start, qoq_end = periods[ComparatorKind.QOQ]
    yoy_start, yoy_end = periods[ComparatorKind.YOY]
    nse_qoq = cached_comparator_path(
        repo_root, stock.symbol, ComparatorKind.QOQ, qoq_start, qoq_end
    )
    nse_yoy = cached_comparator_path(
        repo_root, stock.symbol, ComparatorKind.YOY, yoy_start, yoy_end
    )
    pdf = next(iter(sorted(pdf_dir.glob("*.pdf"))), None) if pdf_dir.is_dir() else None
    fixtures = FixturePaths(
        nse=str(nse.relative_to(repo_root)) if nse is not None else None,
        nse_qoq=(str(nse_qoq.path.relative_to(repo_root)) if nse_qoq.path is not None else None),
        nse_qoq_unavailable_reason=nse_qoq.unavailable_reason,
        nse_yoy=(str(nse_yoy.path.relative_to(repo_root)) if nse_yoy.path is not None else None),
        nse_yoy_unavailable_reason=nse_yoy.unavailable_reason,
        results_pdf=str(pdf.relative_to(repo_root)) if pdf is not None else None,
    )
    results_pdf = (
        SourceFileConfig(
            source_id=BSE_RESULTS_PDF_SOURCE_ID,
            source_class=SourceClass.FIRST_PARTY,
            filename=pdf.name,
            sha256=_sha256_file(pdf),
        )
        if pdf is not None
        else None
    )
    return stock.model_copy(update={"fixtures": fixtures, "results_pdf": results_pdf})


def report_command(args: argparse.Namespace) -> list[str]:
    """Render the per-stock source-verified earnings updates from CACHED data.

    Reconciles each stock's held raw first-party sources offline, bridges the
    reconciled report into the frozen 11-section renderer, and writes
    ``<report_dir>/<SYM>-<QUARTER>.md``. A stock with no cached source, or one that
    cannot resolve every required role, is surfaced and skipped (never written
    half-sourced).
    """
    if not args.watchlist and not args.symbol:
        raise SystemExit("report requires either --watchlist or --symbol <X>")

    config_path = Path(args.config).resolve()
    config: WatchlistConfig = load_watchlist_config(config_path)
    repo_root = config.repo_root(config_path)
    report_dir = Path(args.out_dir) if args.out_dir else _DEFAULT_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    # The cached reconcile writes a gold file as a side effect; route it to a
    # scratch dir so a report run never clobbers the committed data/gold set.
    gold_dir = (
        Path(args.gold_dir)
        if args.gold_dir
        else Path(tempfile.mkdtemp(prefix="fundamentals-report-gold-"))
    )

    selected_wave = _selected_wave(args)
    if args.symbol:
        stock = config.stock(args.symbol)
        _require_symbol_in_wave(stock, selected_wave)
        stocks = [stock]
    elif selected_wave is not None:
        stocks = list(config.stocks_for_wave(selected_wave))
    else:
        stocks = list(config.stocks)
    logger = structlog.get_logger("fundamentals.report")
    written: list[str] = []
    for stock in stocks:
        if args.symbol and args.quarter and args.quarter.upper() != stock.quarter.label.upper():
            raise SystemExit(
                f"quarter {args.quarter!r} does not match configured quarter "
                f"{stock.quarter.label!r} for {stock.symbol}"
            )
        cached = _cached_stock(stock, repo_root)
        if cached.fixtures.nse is None:
            logger.warning(
                "report_skipped_no_cached_source",
                symbol=stock.symbol,
                reason=(
                    "no cached NSE XBRL under "
                    f"{RAW_WATCHLIST_DIR.as_posix()}/{stock.symbol.lower()}"
                ),
            )
            continue
        stock_report = run_stock(
            cached,
            mode=RunMode.FIXTURE,
            repo_root=repo_root,
            kinds=_REPORT_SOURCE_KINDS,
            out_dir=gold_dir,
            # Recover OCR-dependent facts (e.g. THERMAX's garbled revenue) so the
            # report matches the validated gold; lazy engine, fail-closed if the
            # optional 'ocr' extra is absent.
            ocr_engine=RapidOcrEngine(),
        )
        try:
            markdown = render_report(stock_report, cached)
        except ReportBuildError as error:
            logger.warning("report_failed_closed", symbol=stock.symbol, reason=str(error))
            continue
        out_path = report_dir / f"{stock.symbol}-{stock.quarter.label}.md"
        out_path.write_text(markdown, encoding="utf-8")
        written.append(str(out_path))
        logger.info(
            "report_written",
            symbol=stock.symbol,
            path=str(out_path),
            sources=list(stock_report.available_sources),
        )
    return written


def dispatch_report_command(args: argparse.Namespace) -> int | None:
    """Run the ``report`` command, or return ``None`` for any other command."""
    if args.command != REPORT_COMMAND:
        return None
    logger = structlog.get_logger(_CLI_LOGGER_NAME)
    logger.info(
        "report_invoked",
        watchlist=args.watchlist,
        symbol=args.symbol,
        started_at=datetime.now(UTC).isoformat(),
    )
    written = report_command(args)
    logger.info("report_summary", reports=len(written))
    for path in written:
        sys.stdout.write(path + "\n")
    return 0
