"""D2.5: matched backup and restore (plan D2, Task 5).

The backed-up database holds the Apar Q2 FY26 first-party run and the imported legacy copy with
its 8 bound originals. Every database restored into is a freshly minted ``eqos_test_*`` name,
dropped afterwards; the snapshot roots are empty directories under ``tmp_path``.
"""

from __future__ import annotations

import shlex
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from pg_support import PgTestDatabase, create_database, drop_database, mint_name
from retention_support import register_body_absent, restore_args
from stage1_e2e_support import CONFIG, RUNS, Stage
from test_legacy_import import Rig
from test_store import _fact

from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.interface.entry.cli import main
from equity_os.storage.backup.backup import (
    CAPTURES_DIR,
    DEFAULT_CLIENT_PREFIX,
    DUMP_FILE,
    MANIFEST_FILE,
    BackupError,
    restore_backup,
    verify_set,
    write_backup,
)
from equity_os.storage.database.role_secrets import PrivilegedPgSettings
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.facts.pg_fact_store import PgFactStore, create_native_store

pytestmark = [pytest.mark.pg, pytest.mark.retained]

LATE = (
    "INSERT INTO eqos.capture_refs (source_id, surface, request_key, capture_id, blob_sha256, "
    "record_sha256, registered_at, first_seen_at) "
    "VALUES ('late', 's', 'k', 'c', 'x', 'y', now(), now())"
)
BOUND = "SELECT DISTINCT capture_ref_id FROM eqos.legacy_evidence_bindings"


def databases(settings: PrivilegedPgSettings) -> set[str]:
    """Every database name on the instance."""
    with psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname="postgres")) as conn:
        return {row[0] for row in conn.execute("SELECT datname FROM pg_database").fetchall()}


def query(settings: PgSettings, dbname: str, statement: str) -> list[Any]:
    """The first column of a runtime-role query."""
    with psycopg.connect(settings.conninfo(PgRole.RUNTIME, dbname=dbname)) as conn:
        return [row[0] for row in conn.execute(statement).fetchall()]


def late_registration(settings: PrivilegedPgSettings, dbname: str) -> tuple[str, ...]:
    """A client prefix that registers one capture after the snapshot is exported, before the
    dump starts, then runs the real client."""
    psql = [*DEFAULT_CLIENT_PREFIX, "psql", "-v", "ON_ERROR_STOP=1", "-q", "-h", settings.host]
    psql += ["-p", str(settings.port), "-U", settings.admin.login, "-d", dbname, "-c", LATE]
    return ("sh", "-c", f'{shlex.join(psql)} >/dev/null && exec "$@"', "sh", *DEFAULT_CLIENT_PREFIX)


def use_env(monkeypatch: pytest.MonkeyPatch, pg_db: PgTestDatabase, dbname: str) -> None:
    """Point the CLI's ``EQOS_PG_*`` settings at ``dbname``, with the session logins."""
    for name, value in pg_db.model_copy(update={"dbname": dbname}).cli_env().items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def restored(pg_db: PgTestDatabase) -> Iterator[str]:
    """A fresh test database name to restore into, dropped afterwards."""
    name = mint_name(pg_db.settings)
    try:
        yield name
    finally:
        drop_database(pg_db.settings, name)


def test_round_trip_snapshot_and_tamper(
    pg_db: PgTestDatabase, tmp_path: Path, restored: str
) -> None:
    settings, snapshots = pg_db.settings, (tmp_path / "store").absolute()
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.first_party()
        run_id = stage.execute(vendors=[]).run_id
    with pg_db.migrator_connection() as conn:
        nobody = register_body_absent(conn, snapshots)

    set_dir = write_backup(
        settings,
        database=pg_db.dbname,
        snapshot_root=snapshots,
        out_dir=tmp_path / "sets",
        client_prefix=late_registration(settings, pg_db.dbname),
    )
    manifest = verify_set(set_dir)
    # The capture registered after the export is in the source, but in neither manifest nor dump.
    assert "late" in query(settings, pg_db.dbname, "SELECT source_id FROM eqos.capture_refs")
    assert "late" not in {capture[1] for capture in manifest.captures}
    bound = set(query(settings, pg_db.dbname, BOUND))
    assert len(bound) == 8 and bound <= {capture[0] for capture in manifest.captures}
    assert manifest.run_ids == (run_id,)
    assert nobody in {capture[0] for capture in manifest.captures}  # restored with check.ok below

    check = restore_backup(
        set_dir,
        settings,
        database=restored,
        snapshot_root=tmp_path / "restored-store",
        replay_runs=True,
        config_root=CONFIG,
        **restore_args(pg_db, set_dir, tmp_path / "restored-store", live=None),
    )
    assert check.ok, check
    assert "late" not in query(settings, restored, "SELECT source_id FROM eqos.capture_refs")

    # Tampered sets fail verification before any database is created.
    for name, target in (("blob", CAPTURES_DIR + "/blobs"), ("dump", DUMP_FILE)):
        copy = shutil.copytree(set_dir, tmp_path / f"tampered-{name}")
        path = copy / target
        path = path if path.is_file() else next(p for p in path.rglob("*") if p.is_file())
        path.write_bytes(path.read_bytes() + b"\0")
        fresh = mint_name(settings)
        with pytest.raises(BackupError):
            restore_backup(
                copy,
                settings,
                database=fresh,
                snapshot_root=tmp_path / f"empty-{name}",
                replay_runs=False,
                config_root=CONFIG,
                **restore_args(pg_db, copy, tmp_path / f"empty-{name}", set_dir.parent, live=None),
            )
        assert fresh not in databases(settings)
    with pytest.raises(BackupError, match="unpublished"):
        verify_set(shutil.copytree(set_dir, tmp_path / f".{set_dir.name}.partial"))
    # A declared capture missing from both the archive and the file list is still caught.
    missing = shutil.copytree(set_dir, tmp_path / "missing-capture")
    blob = next(p for p in (missing / CAPTURES_DIR / "blobs").rglob("*") if p.is_file())
    blob.unlink()
    data = yaml.safe_load((missing / MANIFEST_FILE).read_text())
    data["files"] = [f for f in data["files"] if f[0] != blob.relative_to(missing).as_posix()]
    (missing / MANIFEST_FILE).write_text(yaml.safe_dump(data))
    with pytest.raises(BackupError, match="captures differ"):
        verify_set(missing)
    nested = shutil.copytree(set_dir, tmp_path / "nested-manifest")
    (nested / CAPTURES_DIR / MANIFEST_FILE).write_text("smuggled")
    with pytest.raises(BackupError, match="files differ"):
        verify_set(nested)

    # The manifest's own metadata is not hashed: dropping run ids alone is inconsistent, and an
    # ABSENT claim with empty inventories is caught by reading the restored database itself.
    for name, changes in (
        ("runs", {"run_ids": []}),
        ("absent", {"schema_state": "ABSENT", "table_counts": {}, "run_ids": [], "captures": []}),
    ):
        copy = shutil.copytree(set_dir, tmp_path / f"meta-{name}")
        data = yaml.safe_load((copy / MANIFEST_FILE).read_text()) | changes
        (copy / MANIFEST_FILE).write_text(yaml.safe_dump(data))
        if name == "runs":
            with pytest.raises(BackupError, match="inventories disagree"):
                verify_set(copy)
            continue
        fresh = mint_name(settings)
        try:
            check = restore_backup(
                copy,
                settings,
                database=fresh,
                snapshot_root=tmp_path / f"meta-store-{name}",
                replay_runs=True,
                config_root=CONFIG,
                **restore_args(
                    pg_db, copy, tmp_path / f"meta-store-{name}", set_dir.parent, live=None
                ),
            )
        finally:
            drop_database(settings, fresh)
        assert not check.ok and not check.schema_equal and not check.run_ids_equal, check


def test_backup_refuses_a_native_fact_whose_original_was_never_registered(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """A restore could not resolve that original, so no set is published."""
    with pg_db.runtime_pool() as pool:
        PgFactStore(pool, create_native_store(pool, "orphan")).put(_fact())
    out = tmp_path / "sets"
    with pytest.raises(BackupError, match="not registered"):
        write_backup(pg_db.settings, database=pg_db.dbname, snapshot_root=tmp_path, out_dir=out)
    assert [path.name for path in out.iterdir() if not path.name.startswith(".")] == []


@pytest.mark.parametrize("witnessed", [False, True])
def test_absent_schema_restores_through_the_cli(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    restored: str,
    monkeypatch: pytest.MonkeyPatch,
    witnessed: bool,
) -> None:
    settings, empty = pg_db.settings, mint_name(pg_db.settings)
    create_database(settings, empty)
    try:
        use_env(monkeypatch, pg_db, empty)
        assert main(["db", "backup", "--out", str(tmp_path), "--snapshot-root", "unused"]) == 0
        (set_dir,) = tmp_path.iterdir()
        use_env(monkeypatch, pg_db, settings.db)
        args = ["db", "restore", "--set", str(set_dir), "--database", restored]
        args += ["--snapshot-root", str(tmp_path / "store")]
        with pytest.raises(SystemExit):  # the witness choice is required (R11)
            main(args)
        live = ["--live-snapshot-root", str(tmp_path / "live")] if witnessed else ["--unwitnessed"]
        assert main([*args, *live]) == EXIT_OK  # L3: no live marker, no authority file read
    finally:
        drop_database(settings, empty)
    assert query(settings, restored, "SELECT to_regnamespace('eqos')") == [None]


@pytest.mark.parametrize("name", ["equity_os", "eqos_testx_1"])
@pytest.mark.parametrize("entrypoint", ["restore_backup", "cli"])
def test_restore_refuses_non_test_targets(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    entrypoint: str,
) -> None:
    settings = pg_db.settings
    before = databases(settings)
    if entrypoint == "cli":
        use_env(monkeypatch, pg_db, settings.db)
        args = ["db", "restore", "--set", str(tmp_path), "--database", name, "--unwitnessed"]
        assert main([*args, "--snapshot-root", str(tmp_path / "s")]) == EXIT_REFUSED
    else:
        unreachable = settings.model_copy(update={"port": 1})  # any connection attempt would fail
        with pytest.raises(BackupError, match="not an eqos_test_ database"):
            restore_backup(
                tmp_path,
                unreachable,
                database=name,
                snapshot_root=tmp_path / "s",
                replay_runs=False,
                config_root=CONFIG,
                **restore_args(pg_db, tmp_path, tmp_path / "s", live=None),
            )
    assert databases(settings) == before
