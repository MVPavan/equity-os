"""Composition root: load config, construct adapters, run the increment.

``eqos run --issuer INFY --quarter Q1-FY25`` loads the non-secret YAML
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
import json
import subprocess
import sys
from collections import Counter
from contextlib import ExitStack
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any, LiteralString

import structlog
from psycopg import Cursor
from psycopg_pool import ConnectionPool

from equity_os.analysis.calculations.run_traces import (
    Line,
    RunDraftError,
    _fiscal_month,
    bind_computed,
)
from equity_os.analysis.lenses.credibility.credibility import Built, bind_credibility, prepare
from equity_os.analysis.lenses.credibility.guidance_targets import check_pins, load_targets
from equity_os.analysis.lenses.risk.risk_probe import Probe, bind_probe
from equity_os.contracts.measurement.canonical import Basis, Representation, ValueIdentity
from equity_os.contracts.measurement.evidence import KnowledgeTimeStatus, RunMode
from equity_os.contracts.measurement.guidance_claim import GuidanceClaim
from equity_os.contracts.measurement.role import FactRole
from equity_os.contracts.sourcing.source_registration import SourceRegistrationError, SourceRole
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.versioning import VersionContentDriftError
from equity_os.interface.commands.companies.entity_map_cli import (
    ENTITY_MAP_COMMAND,
    dispatch_entity_map_command,
)
from equity_os.interface.commands.companies.onboard_cli import (
    dispatch_onboard_command,
    live_transport,
)
from equity_os.interface.commands.extraction.evidence_cli import dispatch_evidence_command
from equity_os.interface.commands.publication.ledger_cli import (
    DEFAULT_IMPORT_CONFIG,
    dispatch_ledger_command,
    ledger_catalog,
)
from equity_os.interface.commands.publication.report_cli import dispatch_report_command
from equity_os.interface.commands.publication.review_cli import dispatch_review_command
from equity_os.interface.commands.publication.thesis_cli import (
    dispatch_adjudicate_command,
    dispatch_thesis_command,
)
from equity_os.interface.commands.sourcing.artifact_writer import write_bytes_no_clobber
from equity_os.interface.commands.sourcing.coverage_cli import dispatch_coverage_command
from equity_os.interface.commands.sourcing.documents_cli import run_documents
from equity_os.interface.commands.sourcing.news_cli import dispatch_news_command
from equity_os.interface.commands.sourcing.screener_cli_dispatch import dispatch_screener_command
from equity_os.interface.commands.sourcing.shareholding_cli import dispatch_shareholding_command
from equity_os.interface.commands.sourcing.source_admission import (
    NativeSourceEvidenceResolver,
    SourceAdmissionError,
    load_source_manifest,
    prepare_pipeline_sources,
    published_package,
)
from equity_os.interface.commands.sourcing.source_intake import (
    ApprovedIntakeContext,
    load_approved_config,
    register_sources,
)
from equity_os.interface.commands.sourcing.tijori_cli_dispatch import dispatch_tijori_command
from equity_os.interface.commands.sourcing.upstox_cli import dispatch_upstox_command
from equity_os.interface.commands.sourcing.vendor_surface_cli import dispatch_vendor_command
from equity_os.interface.commands.storage.db_cli import dispatch_db_command
from equity_os.interface.commands.storage.legacy_cli import dispatch_legacy_command
from equity_os.interface.commands.storage.retention_cli import dispatch_retention_command
from equity_os.interface.commands.verification.compare_cli import dispatch_compare_command
from equity_os.interface.commands.verification.screener_watchlist_corroborate_cli import (
    dispatch_screener_watchlist_corroborate_command,
)
from equity_os.interface.commands.verification.three_source_cli import dispatch_three_source_command
from equity_os.interface.commands.verification.upstox_crosscheck_cli import (
    dispatch_upstox_crosscheck_command,
)
from equity_os.interface.commands.verification.upstox_sensitivity_cli import (
    dispatch_upstox_sensitivity_command,
)
from equity_os.interface.commands.verification.validate_cli import dispatch_validate_command
from equity_os.interface.entry.cli_parser import REGISTER_SOURCES_COMMAND
from equity_os.interface.entry.cli_parser import build_parser as _build_parser
from equity_os.interface.entry.config import FundamentalsConfig, XbrlMode, load_config
from equity_os.interface.entry.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
    _upstox_credentials_from_env,
)
from equity_os.interface.workflows.pipeline import PipelineResult, XbrlInput, run_pipeline
from equity_os.normalisation.dictionary.role_translation import LEGACY_CONCEPTS
from equity_os.publication.drafting.earnings_update import (
    REQUIRED_ROLES,
    EarningsUpdate,
    render_earnings_update,
)
from equity_os.publication.drafting.run_draft import (
    Retrospective,
    RunDraft,
    allowed_captures,
    check_blobs,
    check_head,
    gate_lines,
    predecessor,
    preflight,
    recall,
    section_body,
    stated_claims,
    write_run_draft,
)
from equity_os.publication.revision.import_mapping import measurement_key
from equity_os.publication.revision.importer import load_import_config
from equity_os.publication.revision.rework import Rework
from equity_os.sourcing.exchange.xbrl_source import NseXbrlSource
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.facts.cutover import open_fact_store
from equity_os.storage.facts.fact_store import FactRef
from equity_os.storage.facts.pg_fact_store import PgFactStore
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store as ledger_store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import admit_run, key_identity, select_admitted
from equity_os.verification.comparison.run_config import (
    ComparisonSemanticsError,
    load_run_config,
    require_pins,
)
from equity_os.verification.comparison.run_models import (
    RunInputDisposition,
    RunInputKind,
    RunStatus,
    row_id,
)
from equity_os.verification.comparison.run_store import RunReadError, RunStore

# The pins a pilot run's comparison run must name, by content (PILOT-GAP admission Decision 8).
PILOT_VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
_CONFIG_DIR = "config"  # as ``compare run``'s default config root
TEMPORAL_SOURCES_KEY = "temporal_sources"
_ADMITTED_IN: LiteralString = (
    "SELECT 1 FROM eqos.fact_admissions WHERE store_id = %s AND fact_origin = %s"
    " AND fact_origin_id = %s AND run_id = ANY(%s)"
)


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
    package, retrospective = _retrospective(args, config, config_path)
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
        package=package,
    ) as prepared:
        if xbrl_input is None:
            xbrl_input = XbrlInput(
                xml_bytes=prepared.xbrl_bytes,
                source_id=prepared.xbrl.source_id,
                file_sha256=prepared.xbrl.source_sha256,
                retrieved_at=prepared.xbrl.acquired_at,
            )
        store_db_path = config.store_db_path(config_path)
        if store_db_path not in (None, ":memory:"):
            Path(store_db_path).parent.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            pools: list[ConnectionPool] = []

            def runtime_pool() -> ConnectionPool:
                pools.append(stack.enter_context(open_pool(PgSettings(), PgRole.RUNTIME)))
                return pools[-1]

            store = open_fact_store(config.fact_store_id, store_db_path, pool_factory=runtime_pool)
            stack.callback(store.close)
            run = partial(
                run_pipeline,
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
            if not isinstance(store, PgFactStore):
                if args.full_successor:
                    raise RunDraftError("--full-successor needs a PostgreSQL store")
                return run()
            # A PostgreSQL run reads its prior and writes its earnings update as a DRAFT.
            if args.snapshot_root is None:
                raise RunDraftError("a PostgreSQL run needs --snapshot-root for its draft")
            store_id = config.fact_store_id
            if args.compare_run is None or store_id is None:
                raise RunDraftError("a PostgreSQL run needs --compare-run for its facts")
            symbol, period = config.issuer.nse_symbol, config.quarter.issuer_quarter
            catalog = ledger_catalog(args.watchlist, symbol, [config_path, *args.issuer_config])
            snapshots = SnapshotStore(args.snapshot_root.resolve())
            comparators = config.comparators
            declared = () if comparators is None else (comparators.qoq, comparators.yoy)
            xbrl = (prepared.xbrl.source_sha256,) + tuple(
                instance.sha256 for instance in declared if instance is not None
            )
            pdfs = (prepared.results_pdf.source_sha256, prepared.transcript_pdf.source_sha256)
            (pool,) = pools
            prior = preflight(
                pool,
                stock=symbol,
                period=period,
                xbrl=xbrl,
                pdfs=pdfs,
                catalog=catalog,
                snapshots=snapshots,
                full_successor=args.full_successor,
            )
            targets = load_targets(symbol)
            check_pins(targets, prior.record.pins)
            check_pins(targets, prior.same_period_record.pins)
            memory = recall(pool, prior.entity_id)
            repository = EvidenceRepository(pool)
            versions, members = _comparison(
                pool, repository, args.compare_run, prior.entity_id, config, xbrl, pdfs
            )
            bound: list[tuple[Line, ...]] = []
            probes: list[Probe] = []
            credibility: list[Built] = []
            facts: dict[str, FactRef] = {}

            def admit(update: EarningsUpdate, blobs: frozenset[str]) -> None:
                assert update.source_cutoff is not None
                with pool.connection() as conn, conn.cursor() as cursor:
                    check_blobs(
                        cursor,
                        blobs,
                        allowed=allowed_captures(prior, xbrl, pdfs),
                        cutoff=update.source_cutoff,
                        retrospective=retrospective,
                        catalog=catalog,
                    )

            def before_commit(update: EarningsUpdate, guidance: tuple[GuidanceClaim, ...]) -> None:
                gate = None
                month = _fiscal_month(repository, prior.entity_id, update)
                with pool.connection() as conn, conn.cursor() as cursor:
                    check_head(cursor, prior, period)  # before the run's first write
                    ready = prepare(
                        stated_claims(cursor, guidance, update, prior, catalog),
                        prior.record,
                        prior.same_period_record,
                        targets,
                        period=period,
                        period_end=update.period_end,
                        month=month,
                        filed_at={} if retrospective is None else retrospective.published,
                        actual_blobs=prior.actual_blobs,
                    )
                    if prior.rework is not None:
                        gate = prior.rework.gate(section_body, partial(admit, update))
                        gate_lines(cursor, gate, update, guidance, prior, catalog)
                        _check_carried(cursor, prior.rework, store_id)
                admit(update, ready.blobs)
                lines = bind_computed(
                    repository,
                    update,
                    entity_id=prior.entity_id,
                    versions=versions,
                    carry=gate,
                    check=partial(predecessor, prior),  # before any trace persists
                )
                bound.append(lines)
                probes.append(
                    bind_probe(
                        repository,
                        update,
                        entity_id=prior.entity_id,
                        versions=versions,
                        fiscal_year_end_month=month,
                    )
                )
                credibility.append(
                    bind_credibility(
                        repository,
                        update,
                        ready,
                        prior.actuals,
                        entity_id=prior.entity_id,
                        versions=versions,
                        declared=xbrl[1:],
                    )
                )
                facts.update(
                    _admit(
                        pool,
                        store_id,
                        args.compare_run,
                        update,
                        prior.entity_id,
                        members,
                        carried,
                    )
                )

            carried = prior.rework.carried if prior.rework is not None else frozenset()
            result = run(
                comparators_acquired_at=prior.first_seen,
                before_commit=before_commit,
                skip_roles=frozenset(FactRole),  # facts come only from admission
            )
            # The store stamps the run's writes, so its derivation cutoff is the store's clock.
            update = result.update.model_copy(
                update={"derivation_cutoff": repository.store_clock()}
            )
            result = result.model_copy(
                update={"update": update, "markdown": render_earnings_update(update)}
            )
            draft = RunDraft(
                period=period,
                update=result.update,
                guidance=result.guidance_claims,
                facts=facts,
                lines=bound[0],
                probe=probes[0],
                credibility=credibility[0],
                xbrl=xbrl,
                pdfs=pdfs,
                memory=memory,
                run_id=args.compare_run,
                retrospective=retrospective,
            )
            version_id = write_run_draft(pool, prior, draft, catalog=catalog, snapshots=snapshots)
            structlog.get_logger("fundamentals.cli").info("run_draft_written", version=version_id)
            return result.model_copy(update={"draft_version_id": version_id})


def _comparison(
    pool: ConnectionPool,
    repository: EvidenceRepository,
    run_id: int,
    entity_id: int,
    config: FundamentalsConfig,
    xbrl: tuple[str, ...],
    pdfs: tuple[str, ...],
) -> tuple[ConfigVersions, frozenset[tuple[str, str]]]:
    """Comparison run ``run_id``'s pins and its quarter package's member captures, once the run
    is a complete ``AS_KNOWN`` run of this entity and quarter under ``PILOT_VERSIONS`` whose one
    selected package holds the run's own XBRL and results PDF, published by the cutoff."""
    try:
        manifest = RunStore(pool).read_manifest(run_id)
    except (LookupError, RunReadError) as error:
        raise RunDraftError(f"comparison run {run_id}: {error}") from error
    period_end, cutoff = config.quarter.period_end, config.quarter.knowledge_cutoff
    if (
        manifest.status is not RunStatus.COMPLETE
        or manifest.mode is not RunMode.AS_KNOWN
        or manifest.scope.entity_ids != (entity_id,)
        or period_end not in manifest.scope.period_ends
    ):
        raise RunDraftError(
            f"comparison run {run_id} is not a complete AS_KNOWN run of {period_end}"
        )
    try:
        require_pins(load_run_config(Path(_CONFIG_DIR), PILOT_VERSIONS), manifest.pinned)
    except (VersionContentDriftError, ComparisonSemanticsError) as error:
        raise RunDraftError(f"comparison run {run_id}: {error}") from error
    selected = [
        item.ref_id
        for item in manifest.inputs
        if item.kind is RunInputKind.PACKAGE and item.disposition is RunInputDisposition.SELECTED
    ]
    packages = [
        package
        for package in repository.get_packages(selected)
        if (package.entity_id, package.reporting_period_end, package.basis)
        == (entity_id, period_end, Basis.CONSOLIDATED)
    ]
    if len(packages) != 1 or packages[0].knowledge_time > cutoff:
        raise RunDraftError(f"comparison run {run_id} has no single package published by {cutoff}")
    expected = {
        Representation.XBRL: (config.xbrl.source_id, xbrl[0]),
        Representation.PDF: (config.results_pdf.source_id, pdfs[0]),
    }
    for representation, capture in expected.items():
        member = packages[0].members.get(representation)
        if (
            member is None
            or (member.capture.source_id, member.capture.blob_sha256) != capture
            or member.knowledge_time_status is not KnowledgeTimeStatus.KNOWN
            or member.knowledge_time > cutoff
        ):
            raise RunDraftError(
                f"comparison run {run_id}'s {representation.value} member is not the run's own "
                f"{capture[1]} published by {cutoff}"
            )
    return ConfigVersions.of(manifest.pinned), frozenset(expected.values())


def _check_carried(cursor: Cursor[Any], rework: Rework, store_id: str) -> None:
    """Refuse a rework whose carried facts were not admitted by its head's comparison runs."""
    runs = list(ledger_store.read_version(cursor, rework.head).pinned_run_ids)
    for key in sorted(rework.carried):
        citation = rework.claims[key].citation
        if key.startswith("fact.") and (
            cursor.execute(
                _ADMITTED_IN, (store_id, citation.fact_origin, citation.fact_origin_id, runs)
            ).fetchone()
            is None
        ):
            raise RunDraftError(
                f"version {rework.head} predates fact admission; rerun with --full-successor"
            )


def _admit(
    pool: ConnectionPool,
    store_id: str,
    run_id: int,
    update: EarningsUpdate,
    entity_id: int,
    members: frozenset[tuple[str, str]],
    carried: frozenset[str],
) -> dict[str, FactRef]:
    """Admit comparison run ``run_id``, then select each non-carried required role's admitted
    fact; a refused role or an admission outside the package refuses before any selection."""
    outcome = admit_run(run_id, pool=pool, store_id=store_id)
    others = Counter(refusal.value for _, refusal in outcome.refusals)
    structlog.get_logger("fundamentals.cli").info("admission_refusals", run_id=run_id, **others)
    refusals = dict(outcome.refusals)
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    by_role = {fact.role: fact for fact in update.facts}
    chosen = {}
    for role in REQUIRED_ROLES:
        if f"fact.{role.value}" in carried:
            continue
        fact = by_role[role]
        key = measurement_key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit, entity_id, start, end)
        found = [record for record in outcome.records if record.key_digest == key.digest()]
        if len(found) != 1:
            refusal = refusals.get(row_id(key, ValueIdentity.REPORTED), "not in run")
            raise RunDraftError(
                f"{role.value} not admitted from comparison run {run_id}: {refusal}"
            )
        chosen[role.value] = (key, found[0])
    occurrences = {
        item.occurrence_id: item
        for item in EvidenceRepository(pool).get_occurrences(
            [record.occurrence_id for _, record in chosen.values()]
        )
    }
    for name, (_, record) in chosen.items():
        capture = occurrences[record.occurrence_id].capture
        if (capture.source_id, capture.blob_sha256) not in members:
            raise RunDraftError(f"{name} was admitted from {capture.blob_sha256}, not the package")
    store = PgFactStore(pool, store_id)
    reason = f"admitted from comparison run {run_id}"
    for key, record in chosen.values():
        history = store.get_selection_history(key_identity(key))
        if not history or history[-1].row_id != record.handle:
            head = history[-1].selection_id if history else 0
            select_admitted(
                pool,
                store_id=store_id,
                admission_id=record.admission_id,
                reason=reason,
                expected_selection_id=head,
            )
    return {name: record.ref for name, (_, record) in chosen.items()}


def _retrospective(
    args: argparse.Namespace, config: FundamentalsConfig, config_path: Path
) -> tuple[dict[str, datetime] | None, Retrospective | None]:
    """The quarter's package from ``--retrospective``'s manifest, which must be the one
    ``config/publication/ledger_import.yaml`` pins, and the designation the draft records."""
    manifest: Path | None = getattr(args, "retrospective", None)
    if manifest is None:
        return None, None
    body = manifest.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    pin = load_import_config(config.repo_root(config_path) / DEFAULT_IMPORT_CONFIG)
    if digest != pin.retrieval_manifest_sha256:
        raise SourceAdmissionError(
            f"retrieval manifest {digest} is not the pinned {pin.retrieval_manifest_sha256}"
        )
    issuer = config.issuer.nse_symbol
    published = published_package(body, issuer=issuer, quarter=None)
    package = published_package(body, issuer=issuer, quarter=config.quarter.issuer_quarter)
    return package, Retrospective(manifest_sha256=digest, published=published)


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

    db_exit_code = dispatch_db_command(args)
    if db_exit_code is not None:
        return db_exit_code

    legacy_exit_code = dispatch_legacy_command(args)
    if legacy_exit_code is not None:
        return legacy_exit_code

    evidence_exit_code = dispatch_evidence_command(args)
    if evidence_exit_code is not None:
        return evidence_exit_code

    compare_exit_code = dispatch_compare_command(args)
    if compare_exit_code is not None:
        return compare_exit_code

    onboard_exit_code = dispatch_onboard_command(args)
    if onboard_exit_code is not None:
        return onboard_exit_code

    if args.command == "documents":
        return run_documents(
            args,
            send=live_transport(),
            clock=lambda: datetime.now(UTC),
            bd=lambda argv: subprocess.run(
                ["bd", *argv], timeout=30, capture_output=True, text=True
            ),
        )

    if (shareholding_exit_code := dispatch_shareholding_command(args)) is not None:
        return shareholding_exit_code

    coverage_exit_code = dispatch_coverage_command(args)
    if coverage_exit_code is not None:
        return coverage_exit_code

    if (retention_exit_code := dispatch_retention_command(args)) is not None:
        return retention_exit_code

    ledger_exit_code = dispatch_ledger_command(args)
    if ledger_exit_code is not None:
        return ledger_exit_code

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

    if (vendor_exit := dispatch_vendor_command(args)) is not None:
        return vendor_exit

    logger.info(
        "run_invoked",
        issuer=args.issuer,
        quarter=args.quarter,
        started_at=datetime.now(UTC).isoformat(),
    )

    result = run_command(args, intake_context=intake_context)

    if args.out_json:
        payload = result.update.model_dump_json(indent=2)
        if result.update.retrospective:
            # Contract (c) evidence: each role's admission mode and registration (the pipeline
            # admits its sources in ``SourceRole`` order).
            artifact = json.loads(payload)
            artifact[TEMPORAL_SOURCES_KEY] = {
                role.value: source.model_dump(mode="json")
                for role, source in zip(SourceRole, result.temporal_evidence.sources, strict=True)
            }
            payload = json.dumps(artifact, indent=2, ensure_ascii=False)
        write_bytes_no_clobber(Path(args.out_json), payload.encode("utf-8"))
        logger.info("json_artifact_written", out_json=args.out_json)

    if args.out:
        Path(args.out).write_text(result.markdown, encoding="utf-8")
        logger.info("artifact_written", out=args.out)
    else:
        sys.stdout.write(result.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
