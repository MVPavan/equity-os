"""Shared helpers for the comparison-run tests (D1a Task 9).

``Runner`` wraps one seeded test database: it ingests Apar packages from the retained
originals (through ``Ingest``), builds requests pinned to a config root, and executes,
replays and reads runs. Cutoffs default to the store clock, never the host wall clock.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from evidence_support import CONFIG, Ingest
from psycopg import sql
from retained_support import APAR_IDENTITY

from equity_os.companies.identity.identity_seed import load_issuer_identity, seed_issuer_identity
from equity_os.contracts.measurement.canonical import (
    FIRST_PARTY_REPRESENTATIONS,
    ApplicabilityStatus,
    Basis,
    Representation,
    ValueIdentity,
    ValueKind,
)
from equity_os.contracts.measurement.evidence import PinnedVersions, RunMode, VersionPin
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.verification.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceState,
    Triage,
)
from equity_os.extraction.packages.capture_intake import RetainedIntake
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.resolve_models import ReplayReader
from equity_os.verification.comparison.run import (
    DatabaseIdentity,
    ResultRow,
    RunInputDisposition,
    RunInputKind,
    RunRecord,
    RunRequest,
    RunStatus,
    execute_run,
    load_results,
    replay_run,
    request_for,
)
from equity_os.verification.comparison.run_config import ConfigVersions

Q2_FY26 = "FY26_Q2"
Q3_FY26 = "FY26_Q3"
Q4_FY26 = "FY26_Q4"
Q2_FY25 = "FY25_Q2"
Q2_END = date(2025, 9, 30)
Q3_END = date(2025, 12, 31)
Q4_END = date(2026, 3, 31)
FY25_Q2_END = date(2024, 9, 30)
CODE_VERSION = "test-commit"
WRONG_SHA256 = "0" * 64
RESULT_ENUMS = (
    ("basis", Basis),
    ("framework", AccountingFramework),
    ("value_kind", ValueKind),
    ("value_identity", ValueIdentity),
    ("applicability", ApplicabilityStatus),
    ("extraction_status", ExtractionStatus),
    ("extraction_reason", ReasonCode),
    ("corroboration_status", CorroborationStatus),
    ("corroboration_reason", ReasonCode),
)
VALUE_ENUMS = (
    # These donor rows are FIRST_PARTY. Vendor representation checks use actual
    # source-qualified vendor rows in test_vendor_schema/test_vendor_sql_boundaries.
    ("representation", FIRST_PARTY_REPRESENTATIONS),
    ("source_state", SourceState),
    ("calculation_state", CalculationState),
)
PAIR_ENUMS = (
    ("pair_kind", PairKind),
    ("outcome", PairOutcome),
    ("reason", ReasonCode),
    ("triage", Triage),
)
RUN_TABLES = (
    "runs",
    "run_versions",
    "run_inputs",
    "results",
    "result_source_values",
    "result_surfaced_restatements",
    "pair_outcomes",
    "pair_adjustments",
)


class Runner:
    """Execute, replay and read runs over one seeded database."""

    def __init__(self, ingest: Ingest, pool: Any) -> None:
        self.ingest = ingest
        self.pool = pool
        self.repository = ingest.repository
        settings = ingest.pg_db.settings
        self.database = DatabaseIdentity(
            host=settings.host, port=settings.port, name=ingest.pg_db.dbname
        )

    def now(self) -> datetime:
        """The store clock."""
        return self.repository.store_clock()

    def request(
        self,
        period_end: date = Q2_END,
        *,
        cutoff: datetime | None = None,
        mode: RunMode = RunMode.AS_KNOWN,
        config_root: Path = CONFIG,
        extractor_pins: Mapping[Representation, VersionPin] | None = None,
        versions: ConfigVersions | None = None,
    ) -> RunRequest:
        """A consolidated Apar request pinned to the config root."""
        return request_for(
            self.ingest.entity_id,
            period_end,
            Basis.CONSOLIDATED,
            cutoff=cutoff or self.now(),
            config_root=config_root,
            code_version=CODE_VERSION,
            database_identity=self.database,
            mode=mode,
            versions=versions,
            extractor_pins=extractor_pins,
        )

    def execute(
        self,
        request: RunRequest,
        *,
        config_root: Path = CONFIG,
        extractor_pins: Mapping[Representation, VersionPin] | None = None,
        publish_hook: Callable[[str], None] | None = None,
    ) -> RunRecord:
        """Execute one request."""
        return execute_run(
            request,
            pool=self.pool,
            config_root=config_root,
            extractor_pins=extractor_pins,
            publish_hook=publish_hook,
        )

    def run(self, period_end: date = Q2_END, **options: Any) -> RunRecord:
        """Build and execute a default request."""
        config_root = options.get("config_root", CONFIG)
        pins = options.get("extractor_pins")
        request = self.request(period_end, **options)
        return self.execute(request, config_root=config_root, extractor_pins=pins)

    def replay(
        self, run_id: int, *, config_root: Path = CONFIG, reader: ReplayReader | None = None
    ) -> tuple[ResultRow, ...]:
        """Replay a run from its manifest."""
        return replay_run(run_id, pool=self.pool, config_root=config_root, reader=reader)

    def results(self, run_id: int) -> tuple[ResultRow, ...]:
        """A run's stored results."""
        return load_results(run_id, pool=self.pool)

    def run_counts(self) -> dict[str, int]:
        """Row counts of every run table."""
        counts = {}
        with self.pool.connection() as conn:
            for name in RUN_TABLES:
                query = sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(name))
                row = conn.execute(query).fetchone()
                assert row is not None
                counts[name] = int(row[0])
        return counts


def row(
    rows: tuple[ResultRow, ...],
    canonical_id: str,
    period: PeriodInterval,
    identity: ValueIdentity = ValueIdentity.REPORTED,
) -> ResultRow:
    """The one undimensioned row of a canonical id, period and value identity."""
    (found,) = [
        item
        for item in rows
        if item.key.canonical_id == canonical_id
        and item.key.period == period
        and item.value_identity is identity
        and not item.key.dimensions.pairs
    ]
    return found


def quarter(start: date, end: date) -> PeriodInterval:
    """A duration period."""
    return PeriodInterval.duration(start, end)


@pytest.fixture
def runner(ingest: Ingest) -> Iterator[Runner]:
    """A runner over the ingest fixture's seeded database."""
    with ingest.pg_db.runtime_pool() as pool:
        yield Runner(ingest, pool)


# --- evidence and config edits ---------------------------------------------------------------


def config_copy(tmp_path: Path) -> Path:
    """A private copy of ``config`` with v2 copies of the dictionary, mapping set and
    definition set (edited by the test; the v1 files stay byte-identical)."""
    root = tmp_path / "config-root"
    shutil.copytree(CONFIG, root)
    # This legacy mutation fixture deliberately starts its private v2 from v1, even
    # after the repository gains a real v2 dictionary. Never alter repository config.
    if (root / "normalisation/dictionary" / "v2").exists():
        shutil.rmtree(root / "normalisation/dictionary" / "v2")
    shutil.copytree(
        root / "normalisation/dictionary" / "v1", root / "normalisation/dictionary" / "v2"
    )
    shutil.copyfile(
        root / "normalisation/mappings" / "v1.yaml", root / "normalisation/mappings" / "v2.yaml"
    )
    shutil.copyfile(
        root / "verification/definition_sets" / "v1.yaml",
        root / "verification/definition_sets" / "v2.yaml",
    )
    return root


def edit_yaml(
    path: Path,
    updates: Mapping[str, Any] | None = None,
    *,
    rows_append: Mapping[str, Any] | None = None,
    comment: str = "",
) -> None:
    """Rewrite one YAML file with top-level updates, an appended row, or a leading comment."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(updates or {})
    if rows_append is not None:
        data["rows"].append(dict(rows_append))
    path.write_text(comment + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def failed_pdf_staging(intake: RetainedIntake) -> RetainedIntake:
    """The intake with its PDF binding pinned to the wrong SHA-256, so staging fails."""
    bindings = tuple(
        binding.model_copy(update={"expected_sha256": WRONG_SHA256})
        if binding.representation is Representation.PDF
        else binding
        for binding in intake.bindings
    )
    return intake.model_copy(update={"bindings": bindings})


def reseed_basis_status(ingest: Ingest, basis_status: str) -> None:
    """Seed a second identity input recording ``basis_status`` (a later ``recorded_at``)."""
    data = yaml.safe_load(APAR_IDENTITY.read_text(encoding="utf-8"))
    data["basis_status"] = basis_status
    path = ingest.tmp_path / "aparinds-identity.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        seed_issuer_identity(conn, load_issuer_identity(path))


# --- replay spies -------------------------------------------------------------------------------


class SpyReader:
    """A ``ReplayReader`` over the repository that records every by-id read it serves."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        if not name.startswith("get_"):
            raise AssertionError(f"replay used a non-by-id read: {name}")
        self.calls.append(name)
        return getattr(self._repository, name)


def forbid_current_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every as-of and list read of the repository fail the test."""
    for name in dir(EvidenceRepository):
        if name.endswith("_as_of") or name.startswith("list_"):

            def refuse(*_: Any, _name: str = name, **__: Any) -> Any:
                raise AssertionError(f"replay called {_name}")

            monkeypatch.setattr(EvidenceRepository, name, refuse)


# --- enum round trip ----------------------------------------------------------------------------


def enum_round_trip(runner: Runner, run_id: int) -> list[str]:
    """Insert every Python enum value into its run-table column; return the rejected ones.

    Everything happens in one rolled-back transaction: copies of the run's own rows, each
    with one column replaced, inside a savepoint that is rolled back after a success.
    """
    rejected: list[str] = []
    with runner.pool.connection() as conn, conn.transaction(force_rollback=True):

        def copy(table: str, template: int, overrides: Mapping[str, object]) -> int:
            columns = [
                str(row[0])
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = "
                    "'eqos' AND table_name = %s AND column_name <> 'id' ORDER BY ordinal_position",
                    (table,),
                ).fetchall()
            ]
            names = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
            values = sql.SQL(", ").join(
                sql.Literal(overrides[column]) if column in overrides else sql.Identifier(column)
                for column in columns
            )
            query = sql.SQL(
                "INSERT INTO eqos.{table} ({names}) SELECT {values} FROM eqos.{table} "
                "WHERE id = %s RETURNING id"
            ).format(table=sql.Identifier(table), names=names, values=values)
            found = conn.execute(query, (template,)).fetchone()
            assert found is not None
            return int(found[0])

        def attempt(table: str, template: int, overrides: Mapping[str, object], label: str) -> None:
            try:
                with conn.transaction() as savepoint:
                    copy(table, template, overrides)
                    raise psycopg.Rollback(savepoint)
            except psycopg.errors.CheckViolation:
                rejected.append(label)

        def one(query: str, params: tuple[object, ...]) -> int:
            found = conn.execute(query, params).fetchone()
            assert found is not None, query
            return int(found[0])

        run = copy("runs", run_id, {"identity_hash": "enum-round-trip"})
        for column, values in (("mode", list(RunMode)), ("status", list(RunStatus))):
            for value in values:
                overrides = {"identity_hash": f"enum-{value}", column: value.value}
                attempt("runs", run_id, overrides, f"runs.{column}={value}")
        version = one("SELECT id FROM eqos.run_versions WHERE run_id = %s LIMIT 1", (run_id,))
        for pin in (name for name in PinnedVersions.model_fields if name != "vendor_extractors"):
            attempt("run_versions", version, {"run_id": run, "pin": pin}, f"pin={pin}")
        # The typed collection serializes as one source-qualified row per pin,
        # not as a SQL pin named vendor_extractors.
        attempt(
            "run_versions",
            version,
            {
                "run_id": run,
                "pin": "vendor_extractor",
                "source_id": "constructed-enum-vendor",
                "surface": "CONSTRUCTED_HTML",
            },
            "pin=vendor_extractor",
        )
        for kind in RunInputKind:
            template = one(
                "SELECT id FROM eqos.run_inputs WHERE run_id = %s AND input_kind = %s LIMIT 1",
                (run_id, kind.value),
            )
            for disposition in RunInputDisposition:
                overrides = {"run_id": run, "disposition": disposition.value}
                attempt("run_inputs", template, overrides, f"{kind}/{disposition}")
        pair = one(
            "SELECT id FROM eqos.pair_outcomes WHERE result_id IN "
            "(SELECT id FROM eqos.results WHERE run_id = %s) LIMIT 1",
            (run_id,),
        )
        result, left, right = conn.execute(
            "SELECT result_id, left_value_id, right_value_id FROM eqos.pair_outcomes WHERE id = %s",
            (pair,),
        ).fetchone() or (0, 0, 0)
        for column, enum in RESULT_ENUMS:
            for value in enum:
                overrides = {"run_id": run, column: value.value}
                attempt("results", result, overrides, f"results.{column}={value}")
        new_result = copy("results", result, {"run_id": run})
        for column, enum in VALUE_ENUMS:
            for value in enum:
                overrides = {"result_id": new_result, column: value.value}
                attempt("result_source_values", left, overrides, f"values.{column}={value}")
        new_left = copy("result_source_values", left, {"result_id": new_result})
        new_right = copy("result_source_values", right, {"result_id": new_result})
        for column, enum in PAIR_ENUMS:
            for value in enum:
                overrides = {
                    "result_id": new_result,
                    "left_value_id": new_left,
                    "right_value_id": new_right,
                    column: value.value,
                }
                attempt("pair_outcomes", pair, overrides, f"pairs.{column}={value}")
    return rejected
