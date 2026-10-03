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

from fundamentals.api.artifact_writer import write_bytes_no_clobber
from fundamentals.api.cli_parser import REGISTER_SOURCES_COMMAND
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
from fundamentals.api.review_cli import dispatch_review_command
from fundamentals.api.screener_cli_dispatch import dispatch_screener_command
from fundamentals.api.screener_watchlist_corroborate_cli import (
    dispatch_screener_watchlist_corroborate_command,
)
from fundamentals.api.source_admission import (
    NativeSourceEvidenceResolver,
    SourceAdmissionError,
    load_source_manifest,
    prepare_pipeline_sources,
)
from fundamentals.api.source_intake import (
    ApprovedIntakeContext,
    load_approved_config,
    register_sources,
)
from fundamentals.api.thesis_cli import (
    dispatch_adjudicate_command,
    dispatch_thesis_command,
)
from fundamentals.api.thesis_impact_cli import dispatch_thesis_impact_command
from fundamentals.api.three_source_cli import dispatch_three_source_command
from fundamentals.api.tijori_cli_dispatch import dispatch_tijori_command
from fundamentals.api.upstox_cli import dispatch_upstox_command
from fundamentals.api.upstox_crosscheck_cli import dispatch_upstox_crosscheck_command
from fundamentals.api.upstox_sensitivity_cli import dispatch_upstox_sensitivity_command
from fundamentals.api.validate_cli import dispatch_validate_command
from fundamentals.contracts.source_registration import SourceRegistrationError, SourceRole
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
            accepted_entity_ids=config.xbrl.accepted_entity_ids,
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
        retrieved_at=datetime.now(UTC),
    )


def run_command(
    args: argparse.Namespace, *, intake_context: ApprovedIntakeContext | None = None
) -> PipelineResult:
    """Execute the ``run`` subcommand and return the pipeline result."""
    run_started_at = datetime.now(UTC)
    manifest = getattr(args, "source_admission_manifest", None)
    retained_store = getattr(args, "source_admission_store", None)
    if (manifest is None) != (retained_store is None):
        raise SourceAdmissionError("source admission manifest/store are required together")
    if manifest is not None:
        if intake_context is None:
            raise SourceAdmissionError(
                "native source lacks trustworthy completion/first-seen/registration proof: "
                "trusted approved intake context required"
            )
        config_path = Path(args.config).absolute()
        try:
            config = load_approved_config(config_path, approved_intake=intake_context)
        except SourceRegistrationError as error:
            raise SourceAdmissionError(str(error)) from error
    else:
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

    refs = load_source_manifest(Path(manifest)) if manifest is not None else None
    resolver = (
        NativeSourceEvidenceResolver(Path(retained_store), approved_intake=intake_context)
        if retained_store
        else None
    )
    if refs is not None:
        if intake_context is None:
            raise SourceAdmissionError(
                "native source lacks trustworthy completion/first-seen/registration proof: "
                "trusted approved intake context required"
            )
        if config.quarter.knowledge_cutoff > run_started_at:
            raise SourceAdmissionError("retained registered cutoff is in the future")
        # Preparation resolves each role once; no live acquisition or old paths.
        xbrl_input = None
        xbrl_bytes = b""
        xbrl_source_id = config.xbrl.source_id
        xbrl_sha256 = intake_context.binding(SourceRole.XBRL).expected_sha256
    else:
        mode = XbrlMode(args.xbrl_mode) if args.xbrl_mode else config.xbrl.mode
        xbrl_input = _build_xbrl_input(config, config_path, mode)
        xbrl_bytes = xbrl_input.xml_bytes
        xbrl_source_id = xbrl_input.source_id
        xbrl_sha256 = xbrl_input.file_sha256
    results_pdf_path = config.results_pdf_path(config_path)
    transcript_pdf_path = config.transcript_pdf_path(config_path)
    if xbrl_source_id != config.xbrl.source_id:
        raise SourceAdmissionError("XBRL source identity mismatch")
    with prepare_pipeline_sources(
        xbrl_bytes=xbrl_bytes,
        xbrl_source_id=xbrl_source_id,
        xbrl_sha256=xbrl_sha256,
        results_pdf_path=results_pdf_path,
        results_pdf_sha256=config.results_pdf.sha256,
        results_source_id=config.results_pdf.source_id,
        transcript_pdf_path=transcript_pdf_path,
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        transcript_source_id=config.transcript_pdf.source_id,
        cutoff=config.quarter.knowledge_cutoff,
        run_started_at=run_started_at,
        source_refs=refs,
        evidence_resolver=resolver,
    ) as prepared:
        if xbrl_input is None:
            xbrl_input = XbrlInput(
                xml_bytes=prepared.xbrl_bytes,
                source_id=prepared.xbrl.source_id,
                file_sha256=prepared.xbrl.source_sha256,
                retrieved_at=prepared.xbrl.acquired_at,
            )
        store_db_path = config.store_db_path(config_path)
        if store_db_path != ":memory:":
            Path(store_db_path).parent.mkdir(parents=True, exist_ok=True)
        store = FactStore(store_db_path)
        try:
            return run_pipeline(
                config=config,
                config_path=config_path,
                xbrl_input=xbrl_input,
                results_pdf_path=str(results_pdf_path),
                results_pdf_sha256=config.results_pdf.sha256,
                transcript_pdf_path=str(transcript_pdf_path),
                transcript_pdf_sha256=config.transcript_pdf.sha256,
                store=store,
                admitted_inputs=prepared,
            )
        finally:
            store.close()


def main(
    argv: list[str] | None = None, *, intake_context: ApprovedIntakeContext | None = None
) -> int:
    """CLI entry point. Returns a process exit code."""
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == REGISTER_SOURCES_COMMAND:
        register_sources(
            config_path=Path(args.config),
            manifest_path=Path(args.source_admission_manifest),
            store_root=Path(args.source_admission_store),
            out_manifest=Path(args.out_manifest),
            approved_intake=intake_context,
        )
        return 0

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

    three_source_exit_code = dispatch_three_source_command(args)
    if three_source_exit_code is not None:
        return three_source_exit_code

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

    review_exit_code = dispatch_review_command(args)
    if review_exit_code is not None:
        return review_exit_code

    thesis_exit_code = dispatch_thesis_command(args)
    if thesis_exit_code is not None:
        return thesis_exit_code

    thesis_impact_exit_code = dispatch_thesis_impact_command(args)
    if thesis_impact_exit_code is not None:
        return thesis_impact_exit_code

    logger.info(
        "run_invoked",
        issuer=args.issuer,
        quarter=args.quarter,
        started_at=datetime.now(UTC).isoformat(),
    )

    result = run_command(args, intake_context=intake_context)

    if args.out_json:
        write_bytes_no_clobber(
            Path(args.out_json), result.update.model_dump_json(indent=2).encode("utf-8")
        )
        logger.info("json_artifact_written", out_json=args.out_json)

    if args.out:
        Path(args.out).write_text(result.markdown, encoding="utf-8")
        logger.info("artifact_written", out=args.out)
    else:
        sys.stdout.write(result.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
