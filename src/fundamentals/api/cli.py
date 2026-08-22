"""Composition root: load config, construct adapters, run the increment.

``fundamentals run --issuer INFY --quarter Q1-FY25`` loads the non-secret YAML
configuration, resolves the held-source paths, constructs the XBRL input (from a
held/synthetic local instance by default, or a polite live NSE fetch when
``--xbrl-mode live`` is passed), opens the append-only fact store, runs the
end-to-end pipeline, and writes the sourced markdown update to stdout (or a file
given by ``--out``). All configuration is injected here — no business-logic
module reads the environment. structlog diagnostics go to stderr so stdout
carries only the rendered artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

from fundamentals.api.config import FundamentalsConfig, XbrlMode, load_config
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
from fundamentals.api.pipeline import PipelineResult, XbrlInput, run_pipeline
from fundamentals.api.watchlist_config import WatchlistConfig, load_watchlist_config
from fundamentals.ingest.tijori_source import TijoriCredentials
from fundamentals.ingest.xbrl_source import NseXbrlSource
from fundamentals.reconcile.gold_file import DEFAULT_GOLD_DIR
from fundamentals.store.fact_store import FactStore

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_COMMAND_RUN = "run"
_COMMAND_VALIDATE = "validate"
_QUARTER_LATEST = "latest"

_TIJORI_EMAIL_ENV = "TIJORI_EMAIL"
_TIJORI_PASSWORD_ENV = "TIJORI_PASSWORD"
_TIJORI_SESSION_ENV = "TIJORI_SESSION_COOKIE"


class _LazyStderrLoggerFactory:
    """Build a PrintLogger bound to the *current* ``sys.stderr`` on each call.

    Resolving the stream lazily (never capturing a handle at configure time)
    keeps stdout clean for the artifact while staying robust to test harnesses
    that swap ``sys.stderr`` between runs.
    """

    def __call__(self, *args: object) -> structlog.PrintLogger:
        """Return a fresh stderr-bound PrintLogger."""
        return structlog.PrintLogger(file=sys.stderr)


def _configure_logging() -> None:
    """Route structlog output to stderr, keeping stdout clean for the artifact."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=_LazyStderrLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def _expected_quarter_arg(config: FundamentalsConfig) -> str:
    """Derive the CLI ``--quarter`` token (e.g. ``Q1-FY25``) from the config."""
    fiscal, quarter = config.quarter.issuer_quarter.split("_")
    return f"{quarter}-{fiscal}"


def _build_xbrl_input(config: FundamentalsConfig, config_path: Path, mode: XbrlMode) -> XbrlInput:
    """Construct the XBRL input for the requested mode, injecting config."""
    if mode is XbrlMode.LIVE:
        download_folder = config.repo_root(config_path) / config.raw_dir / "nse-xbrl"
        source = NseXbrlSource(
            download_folder,
            symbol=config.xbrl.symbol,
            timeout_seconds=config.xbrl.timeout_seconds,
            max_retries=config.xbrl.max_retries,
            retry_backoff_seconds=config.xbrl.retry_backoff_seconds,
        )
        retrieval = source.fetch_consolidated_quarter(
            from_date=config.quarter.period_start,
            to_date=config.quarter.period_end,
        )
        return XbrlInput(
            xml_bytes=retrieval.local_path.read_bytes(),
            file_sha256=retrieval.file_sha256,
            source_id=retrieval.source_id,
            retrieved_at=retrieval.retrieved_at,
        )

    local_path = config.xbrl_local_path(config_path)
    xml_bytes = local_path.read_bytes()
    return XbrlInput(
        xml_bytes=xml_bytes,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=config.quarter.knowledge_cutoff,
    )


def run_command(args: argparse.Namespace) -> PipelineResult:
    """Execute the ``run`` subcommand and return the pipeline result."""
    config_path = Path(args.config).resolve()
    config = load_config(config_path)

    if args.issuer.upper() != config.issuer.nse_symbol.upper():
        raise SystemExit(
            f"issuer {args.issuer!r} does not match configured issuer {config.issuer.nse_symbol!r}"
        )
    expected_quarter = _expected_quarter_arg(config)
    if args.quarter.upper() != expected_quarter.upper():
        raise SystemExit(
            f"quarter {args.quarter!r} does not match configured quarter {expected_quarter!r}"
        )

    mode = XbrlMode(args.xbrl_mode) if args.xbrl_mode else config.xbrl.mode
    xbrl_input = _build_xbrl_input(config, config_path, mode)

    results_pdf_path = config.results_pdf_path(config_path)
    transcript_pdf_path = config.transcript_pdf_path(config_path)

    store = FactStore(config.store_db_path(config_path))
    try:
        return run_pipeline(
            config=config,
            xbrl_input=xbrl_input,
            results_pdf_path=str(results_pdf_path),
            results_pdf_sha256=config.results_pdf.sha256,
            transcript_pdf_path=str(transcript_pdf_path),
            transcript_pdf_sha256=config.transcript_pdf.sha256,
            store=store,
        )
    finally:
        store.close()


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


def _tijori_credentials_from_env() -> TijoriCredentials | None:
    """Read Tijori owner-account credentials from the environment (composition root only).

    Returns ``None`` when no credentials are present, so the runner skips Tijori
    cleanly rather than hard-failing. This is the only place credentials are read.
    """
    email = os.environ.get(_TIJORI_EMAIL_ENV)
    password = os.environ.get(_TIJORI_PASSWORD_ENV)
    if email is None or password is None:
        return None
    return TijoriCredentials(
        email=email,
        password=password,
        session_cookie=os.environ.get(_TIJORI_SESSION_ENV),
    )


def _write_reports(report_dir: Path, wave: WaveReport) -> None:
    """Write the per-stock reports and the wave roll-up as JSON under ``report_dir``."""
    report_dir.mkdir(parents=True, exist_ok=True)
    for stock in wave.stocks:
        path = report_dir / f"{stock.symbol}-{stock.quarter}.json"
        path.write_text(stock.model_dump_json(indent=2) + "\n", encoding="utf-8")
    rollup = report_dir / f"{wave.wave}-rollup.json"
    rollup.write_text(wave.model_dump_json(indent=2) + "\n", encoding="utf-8")


def validate_command(args: argparse.Namespace) -> WaveReport:
    """Execute the ``validate`` subcommand and return the wave roll-up."""
    if not args.watchlist and not args.symbol:
        raise SystemExit("validate requires either --watchlist or --symbol <X>")

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
        wave = WaveReport(wave=config.wave, quarter_labels=(report.quarter,), stocks=(report,))
    else:
        wave = run_wave(
            config,
            mode=mode,
            repo_root=repo_root,
            kinds=kinds,
            tijori_credentials=credentials,
            out_dir=out_dir,
            quarter_mode=quarter_mode,
        )

    if args.report_dir:
        _write_reports(Path(args.report_dir), wave)
    return wave


def _stock_summary_line(report: StockReport) -> str:
    """One-line human summary of a stock report for stderr."""
    return (
        f"{report.symbol} ({report.domain}): {report.outcome.value.upper()} — "
        f"{len(report.facts)} facts, {len(report.discrepancies)} discrepancies, "
        f"sources={list(report.available_sources)}"
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the ``fundamentals`` argument parser."""
    parser = argparse.ArgumentParser(prog="fundamentals", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser(_COMMAND_RUN, help="run the source-verified earnings update")
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
        _COMMAND_VALIDATE,
        help="cross-check the watchlist across every available source (gold loop)",
    )
    scope = validate.add_mutually_exclusive_group()
    scope.add_argument("--watchlist", action="store_true", help="validate every Wave-1 stock")
    scope.add_argument("--symbol", default=None, help="validate a single stock, e.g. TITAN")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    logger = structlog.get_logger("fundamentals.cli")

    if args.command == _COMMAND_VALIDATE:
        logger.info(
            "validate_invoked",
            watchlist=args.watchlist,
            symbol=args.symbol,
            live=args.live,
            started_at=datetime.now(UTC).isoformat(),
        )
        wave = validate_command(args)
        for stock in wave.stocks:
            logger.info("stock_summary", summary=_stock_summary_line(stock))
        logger.info(
            "wave_summary",
            wave=wave.wave,
            done=wave.done_count,
            blocked=wave.blocked_count,
            all_done=wave.all_done,
        )
        sys.stdout.write(wave.model_dump_json(indent=2) + "\n")
        return 0

    logger.info(
        "run_invoked",
        issuer=args.issuer,
        quarter=args.quarter,
        started_at=datetime.now(UTC).isoformat(),
    )

    result = run_command(args)

    if args.out:
        Path(args.out).write_text(result.markdown, encoding="utf-8")
        logger.info("artifact_written", out=args.out)
    else:
        sys.stdout.write(result.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
