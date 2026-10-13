"""Persistence and provenance checks for the joined vendor publication pin."""

from __future__ import annotations

import shutil
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from pg_support import (
    MIGRATIONS_DIR,
    PgTestDatabase,
    create_database,
    drop_database,
    load_test_settings,
    mint_name,
)
from psycopg import errors
from test_vendor_config_publication import CONFIG, _draft_root, _publish_synthetic, _write_yaml

from fundamentals.compare.run_config import (
    ConfigVersions,
    LoadedConfig,
    load_run_config,
    pin_config,
    pin_published_generation,
    require_pins,
)
from fundamentals.compare.run_models import DatabaseIdentity, RunManifest, RunScope, RunStatus
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.evidence import RunMode, VersionPin
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository import VersionPin as RepositoryVersionPin
from fundamentals.evidence.vendor_config import VendorConfigPublicationError
from fundamentals.pg.migrations import apply_migrations


class _RecordingRepository:
    def __init__(self, pool: object | None = None, *, refuse_writes: bool = False) -> None:
        self.pool = pool
        self.refuse_writes = refuse_writes
        self.calls: list[tuple[Sequence[Any], str | None]] = []

    def uses_pool(self, pool: object) -> bool:
        return self.pool is pool

    def pin_versions_guarded(
        self, pins: Sequence[Any], *, required_database_prefix: str | None = None
    ) -> None:
        self.calls.append((pins, required_database_prefix))
        if self.refuse_writes:
            raise AssertionError("publication guard reached a repository write")


def test_legacy_pinned_versions_json_omits_publication_pin() -> None:
    loaded = load_run_config(CONFIG)

    assert loaded.pinned.vendor_publication is None
    assert "vendor_publication" not in loaded.pinned.model_dump(mode="json")


def test_deserialized_config_cannot_pin_generation_without_loader_provenance(
    tmp_path: Path,
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    deserialized = LoadedConfig.model_validate(loaded.model_dump(mode="python", warnings=False))
    repository = _RecordingRepository()

    with pytest.raises(VendorConfigPublicationError, match="freshly verified"):
        pin_published_generation(
            deserialized,
            config_root=root,
            repository=repository,  # type: ignore[arg-type]
        )

    assert repository.calls == []


def test_pin_config_refuses_vendor_mapping_when_publication_model_is_removed(
    tmp_path: Path,
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    forged = loaded.model_copy(update={"vendor_config": None})
    pool = object()
    repository = _RecordingRepository(pool, refuse_writes=True)

    with pytest.raises(VendorConfigPublicationError, match="publication"):
        pin_config(
            forged,
            repository=repository,  # type: ignore[arg-type]
            pool=pool,  # type: ignore[arg-type]
            config_root=root,
        )

    assert repository.calls == []


def test_pin_config_refuses_orphan_vendor_pins_before_repository_use() -> None:
    loaded = load_run_config(CONFIG)
    forged = loaded.model_copy(
        update={
            "pinned": loaded.pinned.model_copy(
                update={"vendor_publication": VersionPin(version="v2", content_sha256="4" * 64)}
            )
        }
    )
    pool = object()
    repository = _RecordingRepository(pool, refuse_writes=True)

    with pytest.raises(VendorConfigPublicationError, match="vendor pins"):
        pin_config(
            forged,
            repository=repository,  # type: ignore[arg-type]
            pool=pool,  # type: ignore[arg-type]
        )

    assert repository.calls == []


@pytest.mark.parametrize(
    "pin_name", ["vendor_publication", "source_authority", "vendor_extractors"]
)
def test_pin_config_refuses_publication_model_pin_mismatch_before_repository_use(
    tmp_path: Path, pin_name: str
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    current = getattr(loaded.pinned, pin_name)
    if pin_name == "vendor_extractors":
        mismatched = (
            current[0].model_copy(update={"content_sha256": "5" * 64}),
            *current[1:],
        )
    else:
        assert current is not None
        mismatched = current.model_copy(update={"content_sha256": "5" * 64})
    forged = loaded.model_copy(
        update={"pinned": loaded.pinned.model_copy(update={pin_name: mismatched})}
    )
    pool = object()
    repository = _RecordingRepository(pool, refuse_writes=True)

    with pytest.raises(VendorConfigPublicationError, match="differs"):
        pin_config(
            forged,
            repository=repository,  # type: ignore[arg-type]
            pool=pool,  # type: ignore[arg-type]
            config_root=root,
        )

    assert repository.calls == []


def test_pin_config_refuses_publication_attached_to_first_party_mapping_before_repository_use(
    tmp_path: Path,
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    vendor = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    first_party = load_run_config(root)
    forged = first_party.model_copy(
        update={"vendor_config": vendor.vendor_config, "pinned": vendor.pinned}
    )
    pool = object()
    repository = _RecordingRepository(pool, refuse_writes=True)

    with pytest.raises(VendorConfigPublicationError, match="first-party-only"):
        pin_config(
            forged,
            repository=repository,  # type: ignore[arg-type]
            pool=pool,  # type: ignore[arg-type]
            config_root=root,
        )

    assert repository.calls == []


def test_pin_config_rejects_repository_from_another_pool_before_writes() -> None:
    loaded = load_run_config(CONFIG)
    repository = _RecordingRepository(object(), refuse_writes=True)

    with pytest.raises(ValueError, match="same connection pool"):
        pin_config(
            loaded,
            repository=repository,  # type: ignore[arg-type]
            pool=object(),  # type: ignore[arg-type]
        )

    assert repository.calls == []


def test_publication_generation_pin_requests_test_database_guard(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    repository = _RecordingRepository()

    publication = pin_published_generation(
        loaded,
        config_root=root,
        repository=repository,  # type: ignore[arg-type]
    )

    assert publication == loaded.vendor_config
    assert len(repository.calls) == 1
    assert repository.calls[0][1] == "eqos_test_"


@pytest.mark.pg
def test_run_store_roundtrips_optional_vendor_publication_pin(pg_db: PgTestDatabase) -> None:
    config = load_run_config(CONFIG)
    publication = VersionPin(version="v2", content_sha256="9" * 64)
    pinned = config.pinned.model_copy(update={"vendor_publication": publication})
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        definition_set_id = pin_config(config, repository=repository, pool=pool)
        manifest = RunManifest(
            scope=RunScope(
                entity_ids=(1,),
                period_ends=(date(2026, 3, 31),),
                bases=(Basis.CONSOLIDATED,),
                sources=("NSE_XBRL_INSTANCE",),
            ),
            cutoff=repository.store_clock(),
            mode=RunMode.AS_KNOWN,
            pinned=pinned,
            code_version="publication-pin-roundtrip",
            database_identity=DatabaseIdentity(host="test", port=5432, name=pg_db.dbname),
            inputs=(),
            status=RunStatus.COMPLETE,
        )
        store = RunStore(pool)
        run_id, created = store.publish(manifest, (), definition_set_id=definition_set_id)

        assert created
        assert store.read_versions(run_id).vendor_publication == publication
        assert store.read_manifest(run_id) == manifest


@pytest.mark.pg
def test_stored_v2_manifest_reloads_v2_after_same_root_v3_publication(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    old = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        definition_set_id = pin_config(
            old,
            repository=repository,
            pool=pool,
            config_root=root,
        )
        manifest = RunManifest(
            scope=RunScope(
                entity_ids=(1,),
                period_ends=(date(2026, 3, 31),),
                bases=(Basis.CONSOLIDATED,),
                sources=("NSE_XBRL_INSTANCE",),
            ),
            cutoff=repository.store_clock(),
            mode=RunMode.AS_KNOWN,
            pinned=old.pinned,
            code_version="same-root-publication-replay",
            database_identity=DatabaseIdentity(host="test", port=5432, name=pg_db.dbname),
            inputs=(),
            status=RunStatus.COMPLETE,
        )
        store = RunStore(pool)
        run_id, _ = store.publish(manifest, (), definition_set_id=definition_set_id)

        v2_index = yaml.safe_load((root / "mappings" / "v2.yaml").read_bytes())
        v2_index["version"] = "v3"
        _write_yaml(root / "mappings" / "v3.yaml", v2_index)
        _publish_synthetic(root, version="v3")
        later = load_run_config(
            root,
            ConfigVersions(mapping_set="v3"),
            allow_synthetic_vendor_config=True,
        )

        stored = store.read_versions(run_id)
        replay_config = load_run_config(
            root,
            ConfigVersions.of(stored),
            allow_synthetic_vendor_config=True,
        )
        require_pins(replay_config, stored)

    assert old.vendor_config is not None
    assert later.vendor_config is not None
    assert replay_config.vendor_config is not None
    assert later.vendor_config.content_sha256 != old.vendor_config.content_sha256
    assert replay_config.vendor_config.content_sha256 == old.vendor_config.content_sha256


@pytest.mark.pg
def test_guarded_pin_failure_leaves_no_partial_versions(pg_db: PgTestDatabase) -> None:
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        with pytest.raises(ValueError, match="database prefix"):
            repository.pin_versions_guarded(
                [
                    RepositoryVersionPin(
                        artifact="vendor_publication",
                        version="v2",
                        content_sha256="8" * 64,
                    )
                ],
                required_database_prefix="not_this_database_",
            )
        with pool.connection() as connection:
            count = connection.execute(
                "SELECT count(*) FROM eqos.version_pins "
                "WHERE artifact = 'vendor_publication' AND version = 'v2'"
            ).fetchone()[0]
        assert count == 0


@pytest.fixture
def database_at_0006(tmp_path: Path) -> Iterator[PgTestDatabase]:
    settings = load_test_settings()
    name = mint_name(settings)
    create_database(settings, name)
    database = PgTestDatabase(dbname=name, settings=settings)
    try:
        migrations = tmp_path / "migrations-through-0006"
        migrations.mkdir()
        for source in sorted(MIGRATIONS_DIR.glob("000[1-6]_*.sql")):
            shutil.copyfile(source, migrations / source.name)
        assert len(tuple(migrations.iterdir())) == 6
        with database.migrator_connection() as connection:
            assert len(apply_migrations(connection, migrations)) == 6
        yield database
    finally:
        drop_database(settings, name)


@pytest.mark.pg
def test_0006_to_0007_preserves_old_rows_and_adds_publication_pin(
    database_at_0006: PgTestDatabase,
) -> None:
    database = database_at_0006
    with database.migrator_connection() as connection:
        run_id = connection.execute(
            "INSERT INTO eqos.runs "
            "(identity_hash, cutoff, mode, status, code_version, manifest, manifest_sha256) "
            "VALUES (%s, now(), 'AS_KNOWN', 'COMPLETE', 'migration-compat', '{}'::jsonb, %s) "
            "RETURNING id",
            ("6" * 64, "7" * 64),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256) "
            "VALUES (%s, 'dictionary', 'v1', %s)",
            (run_id, "1" * 64),
        )
        with pytest.raises(errors.CheckViolation):
            with connection.transaction():
                connection.execute(
                    "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256) "
                    "VALUES (%s, 'vendor_publication', 'v2', %s)",
                    (run_id, "2" * 64),
                )

    with database.migrator_connection() as connection:
        applied = apply_migrations(connection, MIGRATIONS_DIR)
        assert [item.filename for item in applied] == ["0007_vendor_publication_pin.sql"]
        connection.execute(
            "INSERT INTO eqos.run_versions (run_id, pin, version, content_sha256) "
            "VALUES (%s, 'vendor_publication', 'v2', %s)",
            (run_id, "2" * 64),
        )
        rows = connection.execute(
            "SELECT pin, version, content_sha256 FROM eqos.run_versions "
            "WHERE run_id = %s ORDER BY pin",
            (run_id,),
        ).fetchall()

    assert rows == [
        ("dictionary", "v1", "1" * 64),
        ("vendor_publication", "v2", "2" * 64),
    ]
