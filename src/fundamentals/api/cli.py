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
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import TypeAdapter

from fundamentals.api.config import FundamentalsConfig, SourceFileConfig, XbrlMode, load_config
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
from fundamentals.api.report_builder import ReportBuildError, render_report
from fundamentals.api.watchlist_config import (
    FixturePaths,
    StockConfig,
    WatchlistConfig,
    Wave,
    load_watchlist_config,
)
from fundamentals.ingest.bse_pdf_source import SOURCE_ID as BSE_RESULTS_PDF_SOURCE_ID
from fundamentals.ingest.ocr_engine import RapidOcrEngine
from fundamentals.ingest.tijori_source import TijoriCredentials
from fundamentals.ingest.xbrl_source import NseXbrlSource
from fundamentals.reconcile.gold_file import DEFAULT_GOLD_DIR, gold_file_path
from fundamentals.store.fact_store import FactStore
from fundamentals.thesis import (
    ClaudeOpusClient,
    CodexSolClient,
    ThesisConfig,
    ThesisDocument,
    ThesisDocumentStatus,
    ThesisModelClient,
    build_thesis,
    from_gold_file,
    load_thesis_config,
    render_thesis_document,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_REPORT_DIR = _REPO_ROOT / "docs" / "research" / "validation" / "reports"
_DEFAULT_THESIS_DIR = _REPO_ROOT / "docs" / "research" / "validation" / "thesis"
_CACHED_RAW_DIR = "data/raw/watchlist"
_COMMAND_RUN = "run"
_COMMAND_VALIDATE = "validate"
_COMMAND_REPORT = "report"
_COMMAND_THESIS = "thesis"
_QUARTER_LATEST = "latest"
# The cached report reconciles the two first-party sources whose raw bytes are
# held on disk (NSE Ind AS XBRL + BSE issuer results PDF); no live fetch.
_REPORT_SOURCE_KINDS: frozenset[SourceKind] = frozenset({SourceKind.NSE, SourceKind.PDF})

_TIJORI_EMAIL_ENV = "TIJORI_EMAIL"
_TIJORI_PASSWORD_ENV = "TIJORI_PASSWORD"
_TIJORI_SESSION_ENV = "TIJORI_SESSION_COOKIE"

# The valid ``--wave`` tokens, derived from the enum so the two never drift.
_WAVE_CHOICES: tuple[str, ...] = tuple(wave.value for wave in Wave)
# Serializes a per-wave roll-up sequence to a single JSON array for stdout.
_WAVE_REPORTS_ADAPTER: TypeAdapter[tuple[WaveReport, ...]] = TypeAdapter(tuple[WaveReport, ...])


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


def _selected_wave(args: argparse.Namespace) -> Wave | None:
    """Resolve the ``--wave`` filter to a :class:`Wave`, or ``None`` when unset."""
    return Wave(args.wave) if args.wave else None


def _require_symbol_in_wave(stock: StockConfig, wave: Wave | None) -> None:
    """Fail closed when an explicit ``--wave`` contradicts the ``--symbol``'s own wave."""
    if wave is not None and stock.wave is not wave:
        raise SystemExit(f"symbol {stock.symbol} is in {stock.wave.value}, not {wave.value}")


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
    nse_dir = repo_root / _CACHED_RAW_DIR / lower / "nse"
    pdf_dir = repo_root / _CACHED_RAW_DIR / lower / "bse_pdf"
    nse = next(iter(sorted(nse_dir.glob("*.xml"))), None) if nse_dir.is_dir() else None
    pdf = next(iter(sorted(pdf_dir.glob("*.pdf"))), None) if pdf_dir.is_dir() else None
    fixtures = FixturePaths(
        nse=str(nse.relative_to(repo_root)) if nse is not None else None,
        results_pdf=str(pdf.relative_to(repo_root)) if pdf is not None else None,
    )
    results_pdf = (
        SourceFileConfig(
            source_id=BSE_RESULTS_PDF_SOURCE_ID, filename=pdf.name, sha256=_sha256_file(pdf)
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
                reason=f"no cached NSE XBRL under {_CACHED_RAW_DIR}/{stock.symbol.lower()}",
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


def _resolve_thesis_out_dir(args: argparse.Namespace) -> Path:
    """Resolve the directory the rendered thesis markdown is written to."""
    return Path(args.out_dir) if args.out_dir else _DEFAULT_THESIS_DIR


def _build_thesis_clients(config: ThesisConfig) -> tuple[ThesisModelClient, ...]:
    """Construct the two real, independent thesis model clients from config."""
    codex: ThesisModelClient = CodexSolClient(config.codex)
    claude: ThesisModelClient = ClaudeOpusClient(config.claude)
    return (codex, claude)


def _stock_name_domain(watchlist: WatchlistConfig, symbol: str) -> tuple[str, str]:
    """Resolve a symbol's display name and domain from the watchlist (best-effort)."""
    try:
        stock = watchlist.stock(symbol)
    except ValueError:
        return "", ""
    return stock.name, stock.domain


def _thesis_exit_code(docs: Sequence[ThesisDocument]) -> int:
    """Non-zero when any thesis is BLOCKED (no usable model draft was produced)."""
    return 1 if any(doc.status is ThesisDocumentStatus.BLOCKED for doc in docs) else 0


def thesis_command(
    args: argparse.Namespace, *, clients: Sequence[ThesisModelClient] | None = None
) -> list[ThesisDocument]:
    """Draft the non-authoritative, cross-verified thesis from validated gold facts.

    Loads each requested stock's gold file (written by ``validate``), runs two
    independent models over the SAME facts, cross-verifies, and writes the sourced
    markdown to ``<out-dir>/<SYM>-<QUARTER>.md``. It never re-fetches or recomputes a
    number: a missing gold file fails closed (run ``validate`` first). The document
    still emits with the recorded gap when one model is unreachable (PARTIAL); when
    both fail (BLOCKED) it emits the facts only and the caller exits non-zero. Model
    clients are injectable so a unit test can pass fakes; the default path builds the
    two real clients (Codex Sol + Claude Opus) from config.
    """
    if not args.watchlist and not args.symbol:
        raise SystemExit("thesis requires either --watchlist or --symbol <X>")

    config_path = Path(args.config).resolve()
    watchlist: WatchlistConfig = load_watchlist_config(config_path)
    gold_dir = Path(args.gold_dir) if args.gold_dir else DEFAULT_GOLD_DIR
    out_dir = _resolve_thesis_out_dir(args)
    thesis_config = (
        load_thesis_config(Path(args.thesis_config)) if args.thesis_config else ThesisConfig()
    )
    if clients is None:
        model_clients: list[ThesisModelClient] = list(_build_thesis_clients(thesis_config))
    else:
        model_clients = list(clients)

    selected_wave = _selected_wave(args)
    if args.symbol:
        if selected_wave is not None:
            _require_symbol_in_wave(watchlist.stock(args.symbol), selected_wave)
        symbols = [args.symbol]
    else:
        scoped = (
            watchlist.stocks_for_wave(selected_wave)
            if selected_wave is not None
            else watchlist.stocks
        )
        symbols = [stock.symbol for stock in scoped]
    logger = structlog.get_logger("fundamentals.thesis")
    generated_at = datetime.now(UTC)
    docs: list[ThesisDocument] = []
    for symbol in symbols:
        gold_path = gold_file_path(symbol, args.quarter, gold_dir)
        if not gold_path.is_file():
            if args.symbol:
                raise SystemExit(
                    f"gold file not found: {gold_path}. Run "
                    f"`fundamentals validate --symbol {symbol} --quarter {args.quarter}` first."
                )
            logger.warning("thesis_skipped_no_gold", symbol=symbol, path=str(gold_path))
            continue
        name, domain = _stock_name_domain(watchlist, symbol)
        fact_set = from_gold_file(gold_path, name=name, domain=domain)
        doc = build_thesis(fact_set, model_clients, max_workers=thesis_config.max_workers)
        markdown = render_thesis_document(doc, generated_at=generated_at)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{symbol}-{args.quarter}.md"
        out_path.write_text(markdown, encoding="utf-8")
        docs.append(doc)
        logger.info(
            "thesis_written",
            symbol=symbol,
            path=str(out_path),
            status=doc.status.value,
            usable_drafts=doc.usable_draft_count,
        )
    return docs


def _add_wave_arg(subparser: argparse.ArgumentParser) -> None:
    """Add the shared ``--wave`` filter that restricts a ``--watchlist`` run to one wave."""
    subparser.add_argument(
        "--wave",
        choices=_WAVE_CHOICES,
        default=None,
        help="scope a run to one wave, e.g. Wave-1 (per-wave roll-ups never collide)",
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
    scope.add_argument(
        "--watchlist",
        action="store_true",
        help="validate every stock, rolling each wave up under its own <wave>-rollup.json",
    )
    scope.add_argument("--symbol", default=None, help="validate a single stock, e.g. TITAN")
    _add_wave_arg(validate)
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
        _COMMAND_REPORT,
        help="render the per-stock source-verified earnings update from CACHED data",
    )
    report_scope = report.add_mutually_exclusive_group()
    report_scope.add_argument(
        "--watchlist",
        action="store_true",
        help="render every watchlist stock (optionally one --wave)",
    )
    report_scope.add_argument("--symbol", default=None, help="render a single stock, e.g. MTARTECH")
    _add_wave_arg(report)
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

    thesis = subparsers.add_parser(
        _COMMAND_THESIS,
        help="draft the non-authoritative cross-verified thesis from validated gold facts",
    )
    thesis_scope = thesis.add_mutually_exclusive_group()
    thesis_scope.add_argument(
        "--watchlist", action="store_true", help="draft a thesis for every watchlist stock"
    )
    thesis_scope.add_argument(
        "--symbol", default=None, help="draft a thesis for a single stock, e.g. MTARTECH"
    )
    _add_wave_arg(thesis)
    thesis.add_argument(
        "--quarter",
        required=True,
        help="the reviewed quarter label, e.g. Q3FY25 (keys the gold file)",
    )
    thesis.add_argument(
        "--config",
        default=str(_DEFAULT_WATCHLIST_PATH),
        help="path to watchlist.yaml (default: repo config/watchlist.yaml); resolves name/domain",
    )
    thesis.add_argument(
        "--thesis-config",
        default=None,
        help="path to non-secret thesis model settings YAML (default: built-in settings)",
    )
    thesis.add_argument(
        "--gold-dir",
        default=None,
        help="directory of <SYM>-<QUARTER>.json gold files (default: data/gold)",
    )
    thesis.add_argument(
        "--out-dir",
        default=None,
        help="directory for rendered thesis .md (default: docs/research/validation/thesis)",
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

    if args.command == _COMMAND_REPORT:
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

    if args.command == _COMMAND_THESIS:
        logger.info(
            "thesis_invoked",
            watchlist=args.watchlist,
            symbol=args.symbol,
            quarter=args.quarter,
            started_at=datetime.now(UTC).isoformat(),
        )
        docs = thesis_command(args)
        out_dir = _resolve_thesis_out_dir(args)
        for doc in docs:
            logger.info(
                "thesis_summary",
                symbol=doc.fact_set.symbol,
                status=doc.status.value,
                usable_drafts=doc.usable_draft_count,
            )
            sys.stdout.write(str(out_dir / f"{doc.fact_set.symbol}-{args.quarter}.md") + "\n")
        return _thesis_exit_code(docs)

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
