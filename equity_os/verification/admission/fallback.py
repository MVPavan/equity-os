"""The fallback workflow (spec 2026-11-06-vendor-first §6.8): for each company-period a run's
admission triggers, acquire that period's results filing, ingest it, rerun with the default
vendor sides under the run's pins, admit, and store one terminal outcome. Entity, symbol, ISIN,
period end and basis come from the triggering run, so no other issuer is requested."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import structlog
import yaml
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from equity_os.companies.identity.identity_layers import latest_slice
from equity_os.companies.onboarding.discovery import Fetch
from equity_os.contracts.companies.entity_identity import IdentifierNamespace
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import FilingFamily
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import outcome_source_state
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import FallbackOutcome
from equity_os.extraction.packages.capture_intake import (
    PDF_INPUT_DIR,
    XBRL_INPUT_DIR,
    IntakeError,
    retained_intake_from_manifest,
)
from equity_os.extraction.packages.first_party_ingest import IngestError, ingest_first_party
from equity_os.extraction.results_pdf.pdf_statement_pages import specs_from_config
from equity_os.interface.commands.companies.onboard_cli import (
    RETRIEVAL_NAME,
    XBRL_KIND,
    package_manifest,
)
from equity_os.interface.entry.config import load_config
from equity_os.interface.entry.watchlist_config import with_issuer_pdfs
from equity_os.sourcing.exchange.results_filing import ResultsFiling, acquire_results
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import AdmissionRefusal, admit_run
from equity_os.verification.comparison.run import execute_run, request_for
from equity_os.verification.comparison.run_config import LoadedConfig, load_run_config
from equity_os.verification.comparison.run_models import RunManifest
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.comparison.selection import period_end

Group = tuple[int, date, Basis]
# Rows 4 and 6 of §6.5 refuse with these; REVIEW_OPEN and FILING_UNRESOLVED belong to the queue.
TRIGGERS = frozenset(
    {
        AdmissionRefusal.CHECK_REQUIRED,
        AdmissionRefusal.VENDOR_UNMAPPED,
        AdmissionRefusal.VENDORS_DISAGREE,
        AdmissionRefusal.VENDORS_IMPRECISE,
    }
)
UNRESOLVED = frozenset({AdmissionRefusal.REVIEW_OPEN, AdmissionRefusal.FILING_UNRESOLVED})
RESULTS_KIND = "results"
PDF_PARSE = "pdf_parse"
AUTHORIZATION = "vendor-first fallback of run {run_id}"
_LOG = structlog.get_logger("verification.fallback")
_EVENT = "fallback_outcome"
_INSERT = (
    "INSERT INTO eqos.vendor_fallback_outcomes "
    "(run_id, entity_id, period_end, basis, outcome, rerun_id, cells) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def run_fallback(
    pool: ConnectionPool,
    run_id: int,
    *,
    fetch: Fetch,
    snapshot_root: Path,
    raw_root: Path,
    store_id: str,
    config_root: Path,
    issuer_config: Path | None,
    vendors: tuple[tuple[str, str], ...],
    code_version: str,
) -> list[tuple[int, date, Basis, FallbackOutcome]]:
    """Each triggered company-period of ``run_id`` through acquire, ingest, a rerun with
    ``vendors`` and admit; its terminal outcome is stored with the run, the rerun and the trigger
    cells still refused."""
    manifest = RunStore(pool).read_manifest(run_id)
    groups = {
        row.row_id: (row.key.entity_id, period_end(row.key.period), row.key.basis)
        for row in RunStore(pool).read_results(run_id)
    }
    triggered: dict[Group, dict[str, str]] = {}
    for row_id, refusal in admit_run(
        run_id, pool=pool, store_id=store_id, config_root=config_root
    ).refusals:
        if refusal in TRIGGERS:
            triggered.setdefault(groups[row_id], {})[row_id] = refusal.value
    config = load_run_config(config_root, ConfigVersions.of(manifest.pinned))
    authorization, roots = AUTHORIZATION.format(run_id=run_id), (snapshot_root, raw_root)
    outcomes = []
    for group, cells in sorted(triggered.items()):
        outcome, rerun, left = FallbackOutcome.FILING_UNAVAILABLE, None, cells
        filing, symbol = _acquire(pool, SnapshotStore(snapshot_root), fetch, group)
        if filing is not None and not _ingest(
            pool, filing, group, symbol, authorization, roots, config, issuer_config
        ):
            outcome = FallbackOutcome.FILING_UNRESOLVED
        elif filing is not None:
            rerun = _rerun(pool, manifest, group, config_root, vendors, code_version)
            admitted = admit_run(rerun, pool=pool, store_id=store_id, config_root=config_root)
            refusals = dict(admitted.refusals)
            left = {row_id: refusals[row_id].value for row_id in cells if row_id in refusals}
            outcome = FallbackOutcome.STILL_REFUSED if left else FallbackOutcome.ADMITTED
            if UNRESOLVED.intersection(refusals[row_id] for row_id in left):
                outcome = FallbackOutcome.FILING_UNRESOLVED
        entity_id, end, basis = group
        with pool.connection() as conn:
            params = (run_id, entity_id, end, basis.value, outcome.value, rerun, Jsonb(left))
            conn.execute(_INSERT, params)
        _LOG.info(
            _EVENT,
            run_id=run_id,
            entity_id=entity_id,
            period_end=str(end),
            basis=basis.value,
            outcome=outcome.value,
            rerun_id=rerun,
            cells=left,
        )
        outcomes.append((*group, outcome))
    return outcomes


def _acquire(
    pool: ConnectionPool, store: SnapshotStore, fetch: Fetch, group: Group
) -> tuple[ResultsFiling | None, str]:
    """The group's filing, requested for the entity's one held NSE symbol and ISIN."""
    entity_id, end, basis = group
    with store.prepare_ordinary_output(), pool.connection() as conn:
        held = [h for h in latest_slice(conn) if h.entity_id == entity_id]
        (symbol,), (isin,) = (
            {h.value for h in held if h.namespace is namespace}
            for namespace in (IdentifierNamespace.NSE_SYMBOL, IdentifierNamespace.ISIN)
        )
        conn.commit()
        conn.autocommit = True  # each listing and capture commits on its own, as in a pass
        try:
            filing = acquire_results(
                conn,
                store,
                fetch,
                entity_id=entity_id,
                symbol=symbol,
                isin=isin,
                period_end=end,
                basis=basis,
            )
        finally:
            conn.autocommit = False
    return filing, symbol


def _ingest(
    pool: ConnectionPool,
    filing: ResultsFiling,
    group: Group,
    symbol: str,
    authorization: str,
    roots: tuple[Path, Path],
    config: LoadedConfig,
    issuer_config: Path | None,
) -> bool:
    """Ingest the filing as onboarding does: XBRL-only, plus the results PDF when the issuer
    config has a ``pdf_parse`` block (its declared ``sha256`` must be the acquired PDF's).
    ``False`` when the intake is refused or any extraction fails."""
    (entity_id, end, basis), (snapshot_root, raw_root) = group, roots
    xbrl_kind = XBRL_KIND.format(basis=basis.value.lower())
    members = [(Representation.XBRL, xbrl_kind, XBRL_INPUT_DIR, filing.xbrl)]
    catalog, specs, pdf_config = BUILTIN_SOURCES, None, None
    if filing.pdf is not None and issuer_config is not None:
        if PDF_PARSE in yaml.safe_load(issuer_config.read_bytes()):
            loaded = load_config(issuer_config)
            catalog, specs = with_issuer_pdfs(catalog, loaded), specs_from_config(loaded.pdf_parse)
            members.append((Representation.PDF, RESULTS_KIND, PDF_INPUT_DIR, filing.pdf))
            pdf_config = issuer_config
    files = [(kind, member) for _, kind, _, member in members]
    package = package_manifest(symbol, authorization, files)
    with tempfile.TemporaryDirectory(dir=raw_root) as staging:
        inputs = Path(staging)
        for _, _, folder, member in members:
            (inputs / folder).mkdir()
            (inputs / folder / member.url.rsplit("/", 1)[-1]).write_bytes(member.body)
        (inputs / RETRIEVAL_NAME).write_bytes(package)
        try:
            intake = retained_intake_from_manifest(
                inputs / RETRIEVAL_NAME,
                issuer=symbol,
                quarter=end.isoformat(),
                kinds={representation: kind for representation, kind, _, _ in members},
                store_root=snapshot_root.absolute(),
                input_root=inputs.absolute(),
                issuer_config=pdf_config,
                basis=basis,
            )
            report = ingest_first_party(
                intake=intake,
                catalog=catalog,
                snapshot_store=SnapshotStore(snapshot_root),
                repository=EvidenceRepository(pool),
                dictionary=config.dictionary,
                mapping_set=config.mapping_set,
                policy=config.normalisation_policy,
                entity_id=entity_id,
                basis=basis,
                framework=AccountingFramework.IND_AS,
                family=FilingFamily.FINANCIAL_RESULTS,
                reporting_period_end=end,
                pdf_specs=specs,
            )
        except (IntakeError, IngestError):
            return False
    return report.package_id is not None and not any(
        outcome_source_state(attempt.outcome) is SourceState.UNAVAILABLE
        for attempt in report.attempts
    )


def _rerun(
    pool: ConnectionPool,
    manifest: RunManifest,
    group: Group,
    config_root: Path,
    vendors: tuple[tuple[str, str], ...],
    code: str,
) -> int:
    """A fresh run of the group with the default vendor sides and the triggering run's pins."""
    entity_id, end, basis = group
    request = request_for(
        entity_id,
        end,
        basis,
        cutoff=EvidenceRepository(pool).store_clock(),
        config_root=config_root,
        code_version=code,
        database_identity=manifest.database_identity,
        mode=manifest.mode,
        vendors=vendors,
        versions=ConfigVersions.of(manifest.pinned),
    )
    return execute_run(request, pool=pool, config_root=config_root).run_id
