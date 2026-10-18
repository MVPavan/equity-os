"""PREP-2b Task 6 support: one test database ready for PostgreSQL runs of the Apar pilot.

The originals are registered (the D2 rig), ``ledger import`` runs as the panel, the stock is
watchlisted, every quarter's transcript is a first-party capture and every run and comparator
XBRL is evidence-ingested; runs write to an ``OPEN`` native store. Each quarter's three
originals are registered through the source intake at real times and run ``--retrospective``
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
from evidence_support import XBRL_KIND, Ingest
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from retained_support import APAR_MANIFEST, REPO_ROOT, apar_store
from test_legacy_import import Rig
from test_transcript_admission import issuer_config, transcript_intake

from fundamentals.api.cli import _build_parser, main, run_command
from fundamentals.api.config import load_config
from fundamentals.api.ledger_cli import DEFAULT_IMPORT_CONFIG, DEFAULT_WATCHLIST, ledger_catalog
from fundamentals.api.pipeline import PipelineResult
from fundamentals.api.source_admission import PipelineSourceRefs, RetainedSourceRef
from fundamentals.api.source_intake import ApprovedIntakeBinding, ApprovedIntakeContext
from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import DecisionKind, SubjectKind, Validation, VersionDraft
from fundamentals.contracts.snapshot import (
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
)
from fundamentals.contracts.source_registration import SourceRole
from fundamentals.evidence.first_party_ingest import admit_transcript
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle, store
from fundamentals.pg.settings import PgRole
from fundamentals.store.pg_fact_store import create_native_store
from fundamentals.store.snapshot_store import DirectoryAnchor, SnapshotStore

STOCK = "APARINDS"
# Each pilot quarter's committed config (Q4 runs from its -pg copy; the frozen one is pinned).
QUARTERS = {
    "FY26_Q2": "fy26-q2",
    "FY26_Q3": "fy26-q3",
    "FY26_Q4": "fy26-q4-pg",
    "FY27_Q1": "fy27-q1",
}
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
COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.fact_rows), (SELECT count(*) FROM eqos.fact_selections), "
    "(SELECT count(*) FROM eqos.report_versions)"
)
RULING = "TEST: approve the pilot run's draft"


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
    ) -> None:
        """``rig``: one whose originals are already registered; ``transcripts``: the quarters
        whose transcript is admitted as a first-party capture; ``imported``: whether the sealed
        versions are imported now."""
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
        with pg_db.runtime_pool() as runtime, pg_db.owner_pool() as owner:
            pools = {PgRole.RUNTIME: runtime, PgRole.OWNER: owner}
            watchlist(pools, self.entity_id, self.snapshots)
            for quarter in transcripts:
                self.admit_transcript(quarter, runtime)
            self.store_id = create_native_store(runtime, "pilot")
        for quarter, kind, period_end in xbrls:
            ingest.run(ingest.intake({Representation.XBRL: kind}, quarter), period_end)
        (tmp_path / "config").mkdir(exist_ok=True)
        shutil.copyfile(REPO_ROOT / DEFAULT_IMPORT_CONFIG, tmp_path / DEFAULT_IMPORT_CONFIG)
        self.retained = tmp_path / "retained"
        self.retained.mkdir(mode=0o700)
        self._registered: dict[str, tuple[ApprovedIntakeContext, list[str]]] = {}

    def import_ledger(self) -> None:
        """``ledger import`` of the sealed Apar versions, as the panel."""
        command = ["ledger", "import", "--config", str(REPO_ROOT / DEFAULT_IMPORT_CONFIG)]
        command += ["--repo", str(REPO_ROOT), "--snapshot-root", str(self.rig.snapshots)]
        assert main(command) == 0

    def admit_transcript(self, quarter: str, runtime: ConnectionPool) -> None:
        """The quarter's transcript as a first-party capture."""
        intake = transcript_intake(self.tmp_path, quarter)
        repository = EvidenceRepository(runtime)
        admit_transcript(repository, apar_store(self.tmp_path), intake, catalog=self.catalog)

    def config(self, quarter: str) -> Path:
        """The quarter's config with repo-absolute sources, routed to the native store."""
        source = REPO_ROOT / "config" / f"aparinds-{QUARTERS[quarter]}.yaml"
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
        """The quarter's originals registered now through the intake, and its run argv."""
        if quarter not in self._registered:
            context, register, argv = self.prepared(quarter)
            assert main(register, intake_context=context) == 0
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
