"""The fallback workflow (spec 2026-11-06-vendor-first §6.8): for each company-period a run's
admission triggers, acquire that period's results filing, ingest it, rerun with the default
vendor sides under the run's pins, admit, settle each original trigger cell against its rerun row
and store one terminal outcome. Entity, symbol, ISIN, period end and basis come from the
triggering run, so no other issuer is requested. A run whose results span more than one group is
refused before admission or any fetch: each group requests the same two listings, and a
replayable generation holds each request once. The public ``compare run`` builder
(``request_for``) makes one entity, period end and basis, so its runs span one group; this bounds
stored runs, whose scope may hold several, to that interface."""

from __future__ import annotations

import tempfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path

import structlog
import yaml
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from equity_os.companies.identity.identity_layers import latest_slice
from equity_os.companies.onboarding.discovery import Fetch
from equity_os.contracts.companies.entity_identity import IdentifierNamespace
from equity_os.contracts.measurement.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
)
from equity_os.contracts.measurement.evidence import FilingFamily, VersionPin
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import outcome_source_state
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.contracts.verification.comparison import SourceRole, SourceState
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import (
    FallbackDisposition,
    FallbackFailure,
    FallbackOutcome,
)
from equity_os.extraction.packages.capture_intake import (
    PDF_INPUT_DIR,
    XBRL_INPUT_DIR,
    IntakeError,
    retained_intake_from_manifest,
)
from equity_os.extraction.packages.first_party_ingest import (
    IngestError,
    IngestReport,
    ingest_first_party,
)
from equity_os.extraction.results_pdf.pdf_statement_pages import specs_from_config
from equity_os.interface.commands.companies.onboard_cli import (
    RETRIEVAL_NAME,
    XBRL_KIND,
    package_manifest,
)
from equity_os.interface.entry.config import load_config
from equity_os.interface.entry.watchlist_config import with_issuer_pdfs
from equity_os.sourcing.exchange.results_filing import (
    ListingUnparsedError,
    ResultsFiling,
    acquire_results,
)
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import (
    TRIGGERS,
    AdmissionOutcome,
    AdmissionRefusal,
    admit_run,
)
from equity_os.verification.comparison.engine_attempts import RunResolutionError
from equity_os.verification.comparison.run import execute_run, request_for
from equity_os.verification.comparison.run_config import (
    LoadedConfig,
    extractor_pin,
    load_run_config,
    require_pins,
)
from equity_os.verification.comparison.run_models import ResultRow, RunManifest
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.comparison.selection import NO_ELIGIBLE_PACKAGE, period_end

Group = tuple[int, date, Basis]
# A cell's disposition (an ``AdmissionRefusal`` or ``FallbackDisposition``) and its detail: the
# admission id, the applicability rule, or the filing or stage failure.
Cell = tuple[str, int | str | None]
# REVIEW_OPEN and FILING_UNRESOLVED belong to the queue: a trigger left with one is unresolved.
UNRESOLVED = frozenset({AdmissionRefusal.REVIEW_OPEN, AdmissionRefusal.FILING_UNRESOLVED})
SETTLED = frozenset(
    {
        FallbackDisposition.ADMITTED,
        FallbackDisposition.NOT_DISCLOSED,
        FallbackDisposition.NOT_APPLICABLE,
    }
)
RESULTS_KIND = "results"
PDF_PARSE = "pdf_parse"
AUTHORIZATION = "vendor-first fallback of run {run_id}"
_LOG = structlog.get_logger("verification.fallback")
_EVENT = "fallback_outcome"
_MANY_GROUPS = "run {run_id} spans {count} company-periods; fallback takes one"
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
    ``vendors`` and admit; its terminal outcome is stored with the run, the rerun and every
    original trigger cell's disposition."""
    manifest = RunStore(pool).read_manifest(run_id)
    extractors = {
        Representation.XBRL: manifest.pinned.extractor_xbrl,
        Representation.PDF: manifest.pinned.extractor_pdf,
    }
    # Unsupported pin drift is refused here, before any acquisition (§6.8 step 3).
    config = load_run_config(
        config_root,
        ConfigVersions.of(manifest.pinned),
        extractor_pins={r: extractor_pin(r, version=p.version) for r, p in extractors.items()},
        vendors=manifest.scope.vendors,
    )
    require_pins(config, manifest.pinned)
    groups = {
        row.row_id: (row.key.entity_id, period_end(row.key.period), row.key.basis)
        for row in RunStore(pool).read_results(run_id)
    }
    if len(spanned := set(groups.values())) > 1:
        raise ValueError(_MANY_GROUPS.format(run_id=run_id, count=len(spanned)))
    triggered: dict[Group, dict[str, AdmissionRefusal]] = {}
    for row_id, refusal in admit_run(
        run_id, pool=pool, store_id=store_id, config_root=config_root
    ).refusals:
        if refusal in TRIGGERS:
            triggered.setdefault(groups[row_id], {})[row_id] = refusal
    pdf_config = pdf_issuer_config(issuer_config)
    authorization, roots = AUTHORIZATION.format(run_id=run_id), (snapshot_root, raw_root)
    outcomes = []
    for group, refused in sorted(triggered.items()):
        rerun, filing, failure = None, None, None
        try:
            filing, symbol = acquire_group(pool, SnapshotStore(snapshot_root), fetch, group)
            if filing is not None and filing.pdf is None and pdf_config is not None:
                failure = FallbackFailure.PDF_UNACQUIRED
            elif filing is not None:
                report = ingest_group(
                    pool,
                    filing,
                    group,
                    symbol,
                    authorization,
                    roots,
                    config,
                    pdf_config,
                    extractors,
                )
                failure = None if ingested(report) else FallbackFailure.EXTRACTION_FAILED
            if filing is not None and failure is None:
                rerun = _rerun(
                    pool, manifest, group, config_root, vendors, code_version, extractors
                )
        except IntakeError:
            failure = FallbackFailure.INTAKE_REFUSED
        except IngestError:
            failure = FallbackFailure.EXTRACTION_FAILED
        # A listing that does not parse, or a rerun that does not resolve, still ends the group
        # with the stage's reason (§6.8: every processed group has a terminal outcome).
        except ListingUnparsedError as error:
            failure = FallbackFailure.LISTING_UNPARSED
            _LOG.warning("fallback_stage_failed", reason=failure, error=str(error))
        except RunResolutionError as error:
            failure = FallbackFailure.RERUN_UNRESOLVED
            _LOG.warning("fallback_stage_failed", reason=failure, error=str(error))
        if rerun is None:
            outcome = FallbackOutcome.FILING_UNAVAILABLE
            if failure is not None:
                outcome = FallbackOutcome.FILING_UNRESOLVED
            cells: dict[str, Cell] = {i: (r.value, failure) for i, r in refused.items()}
        else:
            admitted = admit_run(rerun, pool=pool, store_id=store_id, config_root=config_root)
            rows = {row.row_id: row for row in RunStore(pool).read_results(rerun)}
            read = all(_read(rows.values(), page) for page in vendors)
            cells = {i: settle(rows.get(i), admitted, read) for i in refused}
            dispositions = {disposition for disposition, _ in cells.values()}
            outcome = FallbackOutcome.ADMITTED
            if UNRESOLVED & dispositions:
                outcome = FallbackOutcome.FILING_UNRESOLVED
            elif dispositions - SETTLED:
                outcome = FallbackOutcome.STILL_REFUSED
        entity_id, end, basis = group
        with pool.connection() as conn:
            params = (run_id, entity_id, end, basis.value, outcome.value, rerun, Jsonb(cells))
            conn.execute(_INSERT, params)
        _LOG.info(
            _EVENT,
            run_id=run_id,
            entity_id=entity_id,
            period_end=str(end),
            basis=basis.value,
            outcome=outcome.value,
            rerun_id=rerun,
            cells=cells,
        )
        outcomes.append((*group, outcome))
    return outcomes


def pdf_issuer_config(issuer_config: Path | None) -> Path | None:
    """The issuer config when it has a ``pdf_parse`` block: the results PDF is then wanted."""
    if issuer_config is None or PDF_PARSE not in yaml.safe_load(issuer_config.read_bytes()):
        return None
    return issuer_config


def acquire_group(
    pool: ConnectionPool, store: SnapshotStore, fetch: Fetch, group: Group
) -> tuple[ResultsFiling | None, str]:
    """The group's filing, requested for the entity's one held NSE symbol and ISIN, which are
    resolved before any output is prepared."""
    entity_id, end, basis = group
    with pool.connection() as conn:
        held = [h for h in latest_slice(conn) if h.entity_id == entity_id]
        (symbol,), (isin,) = (
            {h.value for h in held if h.namespace is namespace}
            for namespace in (IdentifierNamespace.NSE_SYMBOL, IdentifierNamespace.ISIN)
        )
    with store.prepare_ordinary_output(), pool.connection() as conn:
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


def ingest_group(
    pool: ConnectionPool,
    filing: ResultsFiling,
    group: Group,
    symbol: str,
    authorization: str,
    roots: tuple[Path, Path],
    config: LoadedConfig,
    pdf_config: Path | None,
    extractors: dict[Representation, VersionPin],
) -> IngestReport:
    """Ingest the filing as onboarding does, under ``extractors``: XBRL-only, plus the results
    PDF when ``pdf_config`` (an issuer config with a ``pdf_parse`` block, whose declared
    ``sha256`` must be the acquired PDF's) is given. Intake refusal raises ``IntakeError``, an
    extraction refusal ``IngestError``."""
    (entity_id, end, basis), (snapshot_root, raw_root) = group, roots
    xbrl_kind = XBRL_KIND.format(basis=basis.value.lower())
    members = [(Representation.XBRL, xbrl_kind, XBRL_INPUT_DIR, filing.xbrl)]
    catalog, specs = BUILTIN_SOURCES, None
    if pdf_config is not None and filing.pdf is not None:
        loaded = load_config(pdf_config)
        catalog, specs = with_issuer_pdfs(catalog, loaded), specs_from_config(loaded.pdf_parse)
        members.append((Representation.PDF, RESULTS_KIND, PDF_INPUT_DIR, filing.pdf))
    files = [(kind, member) for _, kind, _, member in members]
    package = package_manifest(symbol, authorization, files)
    with tempfile.TemporaryDirectory(dir=raw_root) as staging:
        inputs = Path(staging)
        for _, _, folder, member in members:
            (inputs / folder).mkdir()
            (inputs / folder / member.url.rsplit("/", 1)[-1]).write_bytes(member.body)
        (inputs / RETRIEVAL_NAME).write_bytes(package)
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
        return ingest_first_party(
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
            extractor_versions={r: pin.version for r, pin in extractors.items()},
        )


def ingested(report: IngestReport) -> bool:
    """Whether the ingest stored a package and no extraction attempt failed."""
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
    extractors: dict[Representation, VersionPin],
) -> int:
    """A fresh run of the group with the default vendor sides (each new one pinned at its
    current extractor) and the triggering run's other pins."""
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
        extractor_pins=extractors,
    )
    return execute_run(
        request, pool=pool, config_root=config_root, extractor_pins=extractors
    ).run_id


def settle(row: ResultRow | None, admitted: AdmissionOutcome, vendors_read: bool) -> Cell:
    """One original trigger cell against its rerun row of the same measurement identity: a
    matching admission, a rerun-proven ``NOT_APPLICABLE``, a guarded ``NOT_DISCLOSED``, or the
    rerun's refusal (with its filing failure). No row is ``RERUN_ROW_MISSING``."""
    if row is None:
        return FallbackDisposition.RERUN_ROW_MISSING.value, None
    digest = row.key.digest()
    for record in admitted.records:
        if record.key_digest == digest:
            return FallbackDisposition.ADMITTED.value, record.admission_id
    refusal = dict(admitted.refusals)[row.row_id]
    if refusal not in UNRESOLVED:
        if row.applicability is ApplicabilityStatus.NOT_APPLICABLE:
            return FallbackDisposition.NOT_APPLICABLE.value, row.applicability_rule_id
        if refusal is AdmissionRefusal.VENDOR_UNMAPPED and vendors_read and _absent(row):
            return FallbackDisposition.NOT_DISCLOSED.value, None
    return refusal.value, dict(admitted.filing_failures).get(row.row_id)


def _absent(row: ResultRow) -> bool:
    """§6.4's ``FILING_ABSENT`` read from the selected package, with no value on any side: a
    failed, invalid, constructed or zero value is not absence. A vendor with no side here has no
    table mapping the key in the pinned mapping set."""
    first_party = [v for v in row.source_values if v.source_role is SourceRole.FIRST_PARTY]
    return (
        bool(first_party)
        and all(v.reason != NO_ELIGIBLE_PACKAGE for v in first_party)
        and all(v.state is SourceState.NO_VALUE for v in row.source_values)
    )


def _read(rows: Iterable[ResultRow], page: tuple[str, str]) -> bool:
    """Whether a vendor page's capture was read in the run: some side of it is a value or
    an interpreted absence, so the capture was acquired and interpreted under the pins."""
    return any(
        (v.source_id, v.surface) == page and v.state in (SourceState.VALUE, SourceState.NO_VALUE)
        for row in rows
        for v in row.source_values
    )
