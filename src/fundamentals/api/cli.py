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
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

from fundamentals.api.cli_parser import build_parser as _build_parser
from fundamentals.api.config import FundamentalsConfig, XbrlMode, load_config
from fundamentals.api.entity_map_cli import (
    ENTITY_MAP_COMMAND,
    dispatch_entity_map_command,
)
from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
    _upstox_credentials_from_env,
)
from fundamentals.api.news_cli import dispatch_news_command
from fundamentals.api.pipeline import PipelineResult, XbrlInput, run_pipeline
from fundamentals.api.report_cli import dispatch_report_command
from fundamentals.api.screener_cli_dispatch import dispatch_screener_command
from fundamentals.api.screener_watchlist_corroborate_cli import (
    dispatch_screener_watchlist_corroborate_command,
)
from fundamentals.api.thesis_cli import (
    dispatch_adjudicate_command,
    dispatch_thesis_command,
)
from fundamentals.api.tijori_cli_dispatch import dispatch_tijori_command
from fundamentals.api.upstox_cli import dispatch_upstox_command
from fundamentals.api.upstox_crosscheck_cli import dispatch_upstox_crosscheck_command
from fundamentals.api.upstox_sensitivity_cli import dispatch_upstox_sensitivity_command
from fundamentals.api.validate_cli import dispatch_validate_command
from fundamentals.ingest.xbrl_source import NseXbrlSource
from fundamentals.store.fact_store import FactStore


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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    logger = structlog.get_logger("fundamentals.cli")

    tijori_exit_code = dispatch_tijori_command(
        args, credentials_factory=_tijori_credentials_from_env
    )
    if tijori_exit_code is not None:
        return tijori_exit_code

    screener_exit_code = dispatch_screener_command(
        args, credentials_factory=_screener_credentials_from_env
    )
    if screener_exit_code is not None:
        return screener_exit_code

    upstox_exit_code = dispatch_upstox_command(
        args, credentials_factory=_upstox_credentials_from_env
    )
    if upstox_exit_code is not None:
        return upstox_exit_code

    crosscheck_exit_code = dispatch_upstox_crosscheck_command(
        args, credentials_factory=_upstox_credentials_from_env
    )
    if crosscheck_exit_code is not None:
        return crosscheck_exit_code

    sensitivity_exit_code = dispatch_upstox_sensitivity_command(args)
    if sensitivity_exit_code is not None:
        return sensitivity_exit_code

    corroborate_exit_code = dispatch_screener_watchlist_corroborate_command(args)
    if corroborate_exit_code is not None:
        return corroborate_exit_code

    if args.command == ENTITY_MAP_COMMAND:
        return dispatch_entity_map_command(args)

    news_exit_code = dispatch_news_command(args)
    if news_exit_code is not None:
        return news_exit_code

    adjudicate_exit_code = dispatch_adjudicate_command(args)
    if adjudicate_exit_code is not None:
        return adjudicate_exit_code

    validate_exit_code = dispatch_validate_command(args)
    if validate_exit_code is not None:
        return validate_exit_code

    report_exit_code = dispatch_report_command(args)
    if report_exit_code is not None:
        return report_exit_code

    thesis_exit_code = dispatch_thesis_command(args)
    if thesis_exit_code is not None:
        return thesis_exit_code

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
