"""A retained v1 run stays readable across the 0006 upgrade; its replay refuses under D1b."""

import shutil
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from evidence_support import CONFIG, Q2_QUARTER, Ingest, dictionary, mapping_set, policy
from pg_support import (
    MIGRATIONS_DIR,
    PgTestDatabase,
    create_database,
    drop_database,
    load_test_settings,
    mint_name,
)
from run_support import Runner, row

from equity_os.companies.identity import identity_layers
from equity_os.companies.onboarding import discovery_gate
from equity_os.contracts.measurement.evidence import PinnedVersions
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary
from equity_os.normalisation.mapping.mapping import MappingSet, NormalisationPolicy
from equity_os.storage.database.migrations import apply_migrations
from equity_os.storage.raw_files import capture_retention
from equity_os.storage.records import repository
from equity_os.storage.records import repository_calc as calc_sql
from equity_os.storage.records import repository_rows as rows_sql
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison import run, run_config, run_store

__all__ = ["dictionary", "mapping_set", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


@pytest.fixture
def old_db(tmp_path: Path) -> Iterator[PgTestDatabase]:
    """Use the guarded harness with byte-identical applied 0001–0005 migrations."""
    settings = load_test_settings()
    name = mint_name(settings)
    create_database(settings, name)
    database = PgTestDatabase(dbname=name, settings=settings)
    try:
        migrations = tmp_path / "old-migrations"
        migrations.mkdir()
        for source in sorted(MIGRATIONS_DIR.glob("000[1-5]_*.sql")):
            shutil.copyfile(source, migrations / source.name)
        assert len(tuple(migrations.iterdir())) == 5
        with database.migrator_connection() as connection:
            applied = apply_migrations(connection, migrations)
            assert len(applied) == 5
        yield database
    finally:
        drop_database(settings, name)


def legacy_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    """The small unchanged SQL producer seam from source commit 22a3c78.

    It omits only columns and queue tables added in 0006. The real retained intake, comparison,
    financial rows, manifests and digests are never rewritten. The committed
    producer was independently exercised as the witness for this portable seam.
    """
    version_params = run_store._version_params
    value_params = run_store._value_params
    monkeypatch.setattr(
        run_store,
        "_INSERT_VERSION",
        "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256) "
        "VALUES (%s, %s, %s, %s)",
    )
    monkeypatch.setattr(
        run_store,
        "_VERSIONS",
        "SELECT pin, version, content_sha256 FROM eqos.run_versions WHERE run_id = %s",
    )
    monkeypatch.setattr(
        run_store,
        "_version_params",
        lambda run_id, pinned: [values[:4] for values in version_params(run_id, pinned)],
    )
    monkeypatch.setattr(
        run_store,
        "_INSERT_VALUE",
        "INSERT INTO eqos.result_source_values (result_id, source_role, representation, "
        "source_state, reason, value, lower, upper, interpretation_id, calculation_trace_id, "
        "attempt_id, calculation_state) VALUES "
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
    )
    monkeypatch.setattr(
        run_store, "_value_params", lambda result_id, value: value_params(result_id, value)[:12]
    )
    # pair_outcomes.pair_identity arrives in 0013.
    pair_params = run_store._pair_params
    monkeypatch.setattr(
        run_store,
        "_INSERT_PAIR",
        run_store._INSERT_PAIR.replace(", pair_identity", "").replace(", %s)", ")"),
    )
    monkeypatch.setattr(run_store, "_pair_params", lambda *args: pair_params(*args)[:-1])
    value_of = run_store._value_of
    monkeypatch.setattr(
        run_store, "_value_of", lambda row: value_of({"source_id": None, "surface": None} | row)
    )
    # The queue tables arrive in 0006; the old producer routed nothing.
    monkeypatch.setattr(run, "route_run", lambda *_: ())
    # No capture expires before 0030 (R13).
    monkeypatch.setattr(run, "_expired", lambda *_: set())
    # D1a recorded no comparison-semantics pin (D1b review C2).
    monkeypatch.setattr(run_config, "COMPARISON_SEMANTICS", None)


def pre_0022_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Today's reads on a schema before 0022: settings carry no ``valid_from`` (every row
    governs every period), no identifier relationship exists and no capture is discovery's."""
    for name in ("SETTINGS_AS_OF", "SETTINGS_BY_ID"):
        monkeypatch.setattr(
            rows_sql, name, getattr(rows_sql, name).replace("valid_from", "NULL::date")
        )
    monkeypatch.setattr(identity_layers, "_RELATIONSHIPS", "SELECT 1 WHERE false")
    monkeypatch.setattr(
        discovery_gate,
        "_ELIGIBILITY",
        "SELECT id, source_id, surface, false, false FROM eqos.capture_refs "
        "WHERE id = ANY(%(ids)s)",
    )


def test_0005_retained_run_keeps_manifest_and_results_after_0006(
    old_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre_0022_reads(monkeypatch)
    # No capture_addresses before 0027 and no retention lock or states before 0028.
    monkeypatch.setattr(capture_retention, "_INSERT_ADDRESS", "SELECT %s, %s")
    monkeypatch.setattr(capture_retention, "_RETENTION_SHARED", "SELECT 1")
    monkeypatch.setattr(
        capture_retention,
        "_FIND_RETAINED",
        capture_retention._FIND_RETAINED.replace(
            "eqos.capture_state(id) IN ('RETAINED', 'RESTORED')", "true"
        ),
    )
    # No capture expires before 0028, so no trace rests on one (R13).
    monkeypatch.setattr(repository, "_TRACES_EXPIRED", "SELECT '{}'::bigint[] AS expired, %s")
    monkeypatch.setattr(repository, "_RETENTION_SHARED", "SELECT 1")
    # No operand count before 0039: the writer's count binds to RETURNING instead.
    monkeypatch.setattr(
        calc_sql,
        "INSERT_TRACE",
        calc_sql.INSERT_TRACE.replace(", operand_count)", ")")
        .replace(", %s) ON CONFLICT", ") ON CONFLICT")
        .replace("RETURNING id", "RETURNING id, %s"),
    )
    # Every row is visible before 0029's state-aware readers (R13).
    for module in (rows_sql, run_store):
        for name, fragment in vars(module).items():
            if isinstance(fragment, str) and rows_sql._VISIBLE in fragment and name != "_VISIBLE":
                monkeypatch.setattr(module, name, fragment.replace(rows_sql._VISIBLE, "true "))
    upgrade_migrations = tmp_path / "through-0006-migrations"
    upgrade_migrations.mkdir()
    for source in sorted(MIGRATIONS_DIR.glob("000[1-6]_*.sql")):
        shutil.copyfile(source, upgrade_migrations / source.name)
    with old_db.runtime_pool() as pool:
        ingest = Ingest(old_db, EvidenceRepository(pool), tmp_path, dictionary, mapping_set, policy)
        ingest.run(ingest.intake())
        runner = Runner(ingest, pool)
        with monkeypatch.context() as old_producer:
            legacy_publication(old_producer)
            # A pre-0047 schema has no vendor-first policy pin.
            record = runner.run(versions=ConfigVersions(vendor_first_policy=None))
            before = runner.results(record.run_id)
            manifest = run_store.RunStore(pool).read_manifest(record.run_id)
        assert {
            value.value
            for value in row(before, "revenue_from_operations", Q2_QUARTER).source_values
        } == {Decimal("57154200000")}
        assert all(value.source_id is None for result in before for value in result.source_values)
        with pool.connection() as connection:
            identity_before = connection.execute(
                "SELECT identity_hash, manifest_sha256, manifest FROM eqos.runs WHERE id = %s",
                (record.run_id,),
            ).fetchone()
        with old_db.migrator_connection() as connection:
            applied = apply_migrations(connection, upgrade_migrations)
            assert [item.filename for item in applied] == ["0006_vendor_and_queue.sql"]
            # Stored result values are append-only: 0006 adds nullable columns, no backfill.
            assert (
                connection.execute(
                    "SELECT count(*) FROM eqos.result_source_values WHERE source_id IS NOT NULL"
                ).fetchone()[0]
                == 0
            )
        with pool.connection() as connection:
            identity_after = connection.execute(
                "SELECT identity_hash, manifest_sha256, manifest FROM eqos.runs WHERE id = %s",
                (record.run_id,),
            ).fetchone()
        assert identity_after == identity_before
        assert run_store.RunStore(pool).read_manifest(record.run_id) == manifest
        assert runner.results(record.run_id) == before
        # D1b changed comparison semantics: replaying the D1a run refuses rather than
        # recomputing it differently; its stored results stay readable as published.
        with pytest.raises(run_config.ComparisonSemanticsError, match="under semantics None"):
            runner.replay(record.run_id, config_root=CONFIG)
        assert not PinnedVersions.model_validate(manifest.pinned).vendor_extractors
