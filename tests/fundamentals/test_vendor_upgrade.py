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

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.compare import run, run_config, run_store
from fundamentals.contracts.evidence import PinnedVersions
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.migrations import apply_migrations

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
    value_of = run_store._value_of
    monkeypatch.setattr(
        run_store, "_value_of", lambda row: value_of({"source_id": None, "surface": None} | row)
    )
    # The queue tables arrive in 0006; the old producer routed nothing.
    monkeypatch.setattr(run, "route_run", lambda *_: ())
    # D1a recorded no comparison-semantics pin (D1b review C2).
    monkeypatch.setattr(run_config, "COMPARISON_SEMANTICS", None)


def test_0005_retained_run_keeps_manifest_and_results_after_0006(
    old_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            record = runner.run()
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
