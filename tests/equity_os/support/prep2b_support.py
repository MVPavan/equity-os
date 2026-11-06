"""PREP-2b Task 6 support: one test database ready for PostgreSQL runs of the Apar pilot.

The originals are registered (the D2 rig), ``ledger import`` runs as the panel, the stock is
watchlisted, every quarter's transcript is a first-party capture and every run and comparator
XBRL is ``evidence ingest``-ed under the pilot pins, each run quarter's beside its results PDF;
runs write to an ``OPEN`` native store. Each quarter's three originals are registered through the
source intake at real times, compared by ``compare run`` and run ``--retrospective --compare-run``
against the pinned retrieval manifest (contract a-b): no clock is synthetic.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from coverage_support import watchlist
from evidence_support import CONFIG, PDF_KIND, XBRL_KIND, Ingest
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from retained_support import (
    APAR_MANIFEST,
    INPUTS_DIR,
    REPO_ROOT,
    STORE_DIR,
    apar_intake,
    apar_store,
)
from test_legacy_import import Rig
from test_transcript_admission import issuer_config, transcript_intake

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.publication.ledger import (
    DecisionKind,
    SubjectKind,
    Validation,
    VersionDraft,
)
from equity_os.contracts.sourcing.acquisition_outcome import OutcomeCode, OutcomeRecord
from equity_os.contracts.sourcing.snapshot import (
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
)
from equity_os.contracts.sourcing.source_registration import SourceRole
from equity_os.extraction.packages.first_party_ingest import admit_transcript
from equity_os.interface.commands.publication.ledger_cli import (
    DEFAULT_IMPORT_CONFIG,
    DEFAULT_WATCHLIST,
    ledger_catalog,
)
from equity_os.interface.commands.sourcing.source_admission import (
    PipelineSourceRefs,
    RetainedSourceRef,
)
from equity_os.interface.commands.sourcing.source_intake import (
    ApprovedIntakeBinding,
    ApprovedIntakeContext,
)
from equity_os.interface.commands.verification.compare_cli import run_compare
from equity_os.interface.entry.cli import _build_parser, main, run_command
from equity_os.interface.entry.config import load_config
from equity_os.interface.workflows.pipeline import PipelineResult
from equity_os.publication.approval import lifecycle
from equity_os.publication.drafting.earnings_update import REQUIRED_ROLES
from equity_os.storage.database.settings import PgRole
from equity_os.storage.facts.pg_fact_store import PgFactStore, create_native_store
from equity_os.storage.raw_files.snapshot_store import DirectoryAnchor, SnapshotStore
from equity_os.storage.records import store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import key_identity

STOCK = "APARINDS"
# Each pilot quarter's committed config (Q4 runs from its -pg copy; the frozen one is pinned).
QUARTERS = {
    "FY26_Q2": "fy26-q2",
    "FY26_Q3": "fy26-q3",
    "FY26_Q4": "fy26-q4-pg",
    "FY27_Q1": "fy27-q1",
}
# Each run quarter's results-PDF parse config: PQ3 reads its -pg unit marker (eqos-4j2.33).
PDF_CONFIGS = QUARTERS | {"FY27_Q1": "fy27-q1-pg"}
# The pilot comparison pins (``cli.PILOT_VERSIONS``) every ingest and comparison names.
PINS = ("--dictionary", "v2", "--mapping-set", "v9")
COMPARATOR_KIND = "xbrl-consolidated-comparator"
# Every XBRL a pilot run reads (run quarters and comparators): manifest quarter, kind, period end.
XBRLS = (
    ("FY26_Q2", XBRL_KIND, date(2025, 9, 30)),
    ("FY26_Q3", XBRL_KIND, date(2025, 12, 31)),
    ("FY26_Q4", XBRL_KIND, date(2026, 3, 31)),
    ("FY27_Q1", XBRL_KIND, date(2026, 6, 30)),
    ("FY25_Q2", COMPARATOR_KIND, date(2024, 9, 30)),
    ("FY25_Q3", COMPARATOR_KIND, date(2024, 12, 31)),
    ("FY25_Q4", COMPARATOR_KIND, date(2025, 3, 31)),
    ("FY26_Q1", COMPARATOR_KIND, date(2025, 6, 30)),
)
RIGHTS = SnapshotRights(authority_refs=("prep2b-test-retained-originals",))
# Every table a run writes; the first three are its facts: rows, admissions and selections.
TABLES = (
    "fact_rows",
    "fact_admissions",
    "fact_selections",
    "calculation_traces",
    "calculation_trace_operands",
    "report_versions",
    "numeric_claims",
)
COUNTS = f"SELECT {', '.join(f'(SELECT count(*) FROM eqos.{table})' for table in TABLES)}"
RULING = "TEST: approve the pilot run's draft"
ADMITTED = (
    "SELECT row_handle FROM eqos.fact_admissions WHERE store_id = %s AND fact_origin = %s "
    "AND fact_origin_id = %s AND run_id = ANY(%s)"
)


class Pilot:
    """The pilot's database, stores and catalog; ``run`` registers and runs one quarter."""

    def __init__(
        self,
        pg_db: PgTestDatabase,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        ingest: Ingest,
        xbrls: tuple[tuple[str, str, date], ...] = XBRLS,
        *,
        rig: Rig | None = None,
        transcripts: tuple[str, ...] = tuple(QUARTERS),
        imported: bool = True,
        replayable: bool = False,
    ) -> None:
        """``rig``: one whose originals are already registered; ``transcripts``: the quarters
        whose transcript is admitted as a first-party capture; ``imported``: whether the sealed
        versions are imported now; ``replayable``: whether the watchlist batch names a real
        comparison run of the first quarter (so ``db restore --replay-runs`` can replay it)
        instead of a stub."""
        self.pg_db, self.tmp_path, self.entity_id = pg_db, tmp_path, ingest.entity_id
        if rig is None:
            rig = Rig(pg_db, tmp_path)
            rig.register()
        self.rig, self.snapshots = rig, SnapshotStore(rig.snapshots)
        for name, value in pg_db.cli_env().items():
            monkeypatch.setenv(name, value)
        if imported:
            self.import_ledger()
        self.catalog = ledger_catalog(
            REPO_ROOT / DEFAULT_WATCHLIST, STOCK, [issuer_config(q) for q in QUARTERS]
        )
        self.period_ends = {quarter: end for quarter, kind, end in xbrls if kind == XBRL_KIND}
        for quarter, kind, period_end in xbrls:
            self.evidence_ingest(quarter, kind, period_end)
        run = self.compare_run(next(iter(self.period_ends))) if replayable else None
        with pg_db.runtime_pool() as runtime, pg_db.owner_pool() as owner:
            pools = {PgRole.RUNTIME: runtime, PgRole.OWNER: owner}
            watchlist(pools, self.entity_id, self.snapshots, run)
            for quarter in transcripts:
                self.admit_transcript(quarter, runtime)
            self.store_id = create_native_store(runtime, "pilot")
        (tmp_path / DEFAULT_IMPORT_CONFIG).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / DEFAULT_IMPORT_CONFIG, tmp_path / DEFAULT_IMPORT_CONFIG)
        self.retained = tmp_path / "retained"
        self.retained.mkdir(mode=0o700)
        self._registered: dict[str, tuple[ApprovedIntakeContext, list[str]]] = {}

    def import_ledger(self) -> None:
        """``ledger import`` of the sealed Apar versions, as the panel."""
        command = ["ledger", "import", "--config", str(REPO_ROOT / DEFAULT_IMPORT_CONFIG)]
        command += ["--repo", str(REPO_ROOT), "--snapshot-root", str(self.rig.snapshots)]
        assert main(command) == 0

    def evidence_ingest(self, quarter: str, kind: str, period_end: date) -> None:
        """``evidence ingest`` of one XBRL under the pilot pins, a run quarter's beside its
        results PDF read with that quarter's specs."""
        members = {Representation.XBRL: kind}
        command = ["evidence", "ingest", "--retrieval-manifest", str(APAR_MANIFEST)]
        command += ["--issuer", STOCK, "--quarter", quarter, "--period-end", str(period_end)]
        command += ["--basis", "consolidated", "--member", f"xbrl={kind}", *PINS]
        command += ["--raw-root", str(self.tmp_path / INPUTS_DIR), "--config-root", str(CONFIG)]
        command += ["--snapshot-root", str(self.tmp_path / STORE_DIR)]
        if kind == XBRL_KIND:
            members[Representation.PDF] = PDF_KIND
            config = CONFIG / f"runs/aparinds-{PDF_CONFIGS[quarter]}.yaml"
            command += ["--member", f"pdf={PDF_KIND}", "--issuer-config", str(config)]
            apar_intake(self.tmp_path, quarter, members, issuer_config=config)  # stages originals
        else:
            apar_intake(self.tmp_path, quarter, members)
        assert main(command) == 0

    def compare_run(self, quarter: str, config_root: Path = CONFIG) -> int:
        """``compare run`` of the quarter's package under the pilot pins (``AS_KNOWN`` at the
        store clock): the run a ``fundamentals run`` admits its facts from."""
        command = ["compare", "run", "--entity", STOCK, "--basis", "consolidated", *PINS]
        command += ["--period-end", str(self.period_ends[quarter]), "--alignment-rules", "v2"]
        command += ["--config-root", str(config_root)]
        return run_compare(_build_parser().parse_args(command)).run_id

    def admit_transcript(self, quarter: str, runtime: ConnectionPool) -> None:
        """The quarter's transcript as a first-party capture."""
        intake = transcript_intake(self.tmp_path, quarter)
        repository = EvidenceRepository(runtime)
        admit_transcript(repository, apar_store(self.tmp_path), intake, catalog=self.catalog)

    def config(self, quarter: str) -> Path:
        """The quarter's config with repo-absolute sources, routed to the native store."""
        source = REPO_ROOT / "config" / f"runs/aparinds-{QUARTERS[quarter]}.yaml"
        body = yaml.safe_load(source.read_text(encoding="utf-8"))
        body["raw_dir"] = str(REPO_ROOT / body["raw_dir"])
        body["xbrl"]["local_path"] = str(REPO_ROOT / body["xbrl"]["local_path"])
        for comparator in body["comparators"].values():
            comparator["local_path"] = str(REPO_ROOT / comparator["local_path"])
        body["fact_store_id"] = self.store_id
        path = self.tmp_path / "config" / source.name
        path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
        return path

    def registered(self, quarter: str) -> tuple[ApprovedIntakeContext, list[str]]:
        """The quarter's originals registered now through the intake, and its run argv naming
        the quarter's comparison run."""
        if quarter not in self._registered:
            context, register, argv = self.prepared(quarter)
            assert main(register, intake_context=context) == 0
            argv += ["--compare-run", str(self.compare_run(quarter))]
            self._registered[quarter] = (context, argv)
        return self._registered[quarter]

    def prepared(self, quarter: str) -> tuple[ApprovedIntakeContext, list[str], list[str]]:
        """The quarter's originals captured now (not registered), its approved intake context,
        and its ``register-sources`` and run argv."""
        path = self.config(quarter)
        config = load_config(path)
        refs, bindings = {}, []
        for role, source_id, original in (
            (SourceRole.XBRL, config.xbrl.source_id, config.xbrl_local_path(path)),
            (SourceRole.RESULTS_PDF, config.results_pdf.source_id, config.results_pdf_path(path)),
            (
                SourceRole.TRANSCRIPT_PDF,
                config.transcript_pdf.source_id,
                config.transcript_pdf_path(path),
            ),
        ):
            body = original.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            request = RequestIdentity(
                source_id=source_id, surface="retained", request_key=quarter.lower()
            )
            record = CaptureRecord.make(
                request=request,
                retrieved_at=datetime.now(UTC),
                http_status=200,
                media_type="application/octet-stream",
                content_encoding=None,
                body=BlobRef(source_id=source_id, content_sha256=digest, byte_count=len(body)),
                outcome=OutcomeRecord(
                    code=OutcomeCode.OK, native_kind="retained", native_value="ok"
                ),
                rights=RIGHTS,
                schema_version=2,
                body_completeness=BodyCompleteness.COMPLETE,
            )
            SnapshotStore(self.retained).put_capture(record, body)
            refs[role.value] = RetainedSourceRef(
                **request.model_dump(include={"source_id", "surface", "request_key"}),
                capture_id=record.capture_id,
                source_sha256=digest,
                record_sha256=record.record_sha256,
            )
            bindings.append(ApprovedIntakeBinding(role, source_id, digest, RIGHTS))
        context = ApprovedIntakeContext(
            tuple(bindings),
            hashlib.sha256(path.read_bytes()).hexdigest(),
            DirectoryAnchor(self.retained),
            DirectoryAnchor(self.tmp_path),
        )
        manifest, locator = (self.tmp_path / f"{quarter}-{name}.json" for name in ("refs", "at"))
        manifest.write_text(PipelineSourceRefs(**refs).model_dump_json())
        retained = ["--source-admission-store", str(self.retained)]
        register = ["register-sources", "--config", str(path), *retained]
        register += ["--source-admission-manifest", str(manifest), "--out-manifest", str(locator)]
        fiscal, number = quarter.split("_")
        argv = ["run", "--issuer", STOCK, "--quarter", f"{number}-{fiscal}", "--config", str(path)]
        argv += ["--source-admission-manifest", str(locator), *retained]
        argv += ["--snapshot-root", str(self.rig.snapshots)]
        argv += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
        argv += [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]
        return context, register, argv

    def run(self, quarter: str, *, retrospective: bool = True) -> PipelineResult:
        """The quarter's ``run`` (``--retrospective`` on the pinned manifest by default)."""
        context, argv = self.registered(quarter)
        flags = ["--retrospective", str(APAR_MANIFEST)] if retrospective else []
        return run_command(_build_parser().parse_args([*argv, *flags]), intake_context=context)

    def query(self, statement: str, *params: object) -> list[tuple[Any, ...]]:
        """Rows of one runtime-role query."""
        return self.rig.query(statement, *params)  # type: ignore[no-any-return]

    def version(self, version_id: int) -> VersionDraft:
        """A stored version's content."""
        with self.pg_db.runtime_pool() as pool, pool.connection() as conn:
            return store.read_version(conn.cursor(), version_id)

    def admitted(self, version_id: int) -> None:
        """Each of the version's required fact claims cites a row one of its pinned comparison
        runs admitted, and that row is its key's current selection."""
        version = self.version(version_id)
        facts = [c for c in version.claims if c.claim_key.startswith("fact.")]
        assert len(facts) == len(REQUIRED_ROLES) and version.pinned_run_ids
        runs = list(version.pinned_run_ids)
        with self.pg_db.runtime_pool() as pool:
            selected = PgFactStore(pool, self.store_id)
            for claim in facts:
                cited, key = claim.citation, claim.measurement_key
                assert key is not None
                found = self.query(
                    ADMITTED, self.store_id, cited.fact_origin, cited.fact_origin_id, runs
                )
                current = selected.get_canonical(key_identity(key))
                assert current is not None, claim.claim_key
                assert {row[0] for row in found} == {current.row_id}, claim.claim_key

    def sources(self) -> dict[str, Any]:
        """The catalog and snapshot store a claim check reads."""
        return {"catalog": self.catalog, "snapshots": self.snapshots}

    def validate(self, version_id: int, mode: RunMode = RunMode.AS_KNOWN) -> Validation:
        """A runtime check of the version, appended (advisory)."""
        with self.pg_db.runtime_pool() as runtime:
            return lifecycle.validate(runtime, version_id, mode=mode, **self.sources())

    def approve(self, version_id: int, *, submit: bool = True) -> None:
        """Submit the draft (runtime) and approve it on the owner's own ``AS_KNOWN`` check."""
        sources = self.sources()
        if submit:
            with self.pg_db.runtime_pool() as runtime:
                lifecycle.submit(runtime, version_id, **sources)
        with self.pg_db.owner_pool() as owner:
            lifecycle.decide(
                owner,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=version_id,
                kind=DecisionKind.APPROVE,
                ruling=RULING,
                **sources,
            )
