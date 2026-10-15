"""Matched backup and restore of the PostgreSQL store and its captures (data spec §6, D2 Task 5).

A set is one exported snapshot: the custom-format dump, the table counts, the stored-run ids and
the referenced captures are all read from it, so the manifest and the dump cannot disagree. The
set is staged under ``.<id>.partial`` and renamed into place only once it verifies. Restore
verifies the set first and only ever targets a fresh ``eqos_test_*`` database (design decision
6); a production restore is the owner's runbook, not code. Every client or SQL failure is fatal.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import IO, Any, cast

import psycopg
import structlog
import yaml
from psycopg import IsolationLevel, sql
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run import load_results, replay_run
from fundamentals.compare.run_models import DatabaseIdentity
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.pg.approvals import current_database, is_test_database
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.pg.test_databases import check_test_db_name, create_test_database
from fundamentals.store.snapshot_store import SnapshotStore

DEFAULT_CLIENT_PREFIX = (
    "docker", "run", "--rm", "-i", "--network", "host", "-e", "PGPASSWORD", "postgres:18.6",
)  # fmt: skip
CLIENT_TIMEOUT_S = 900
MANIFEST_FILE = "manifest.yaml"
DUMP_FILE = "database.dump"
CAPTURES_DIR = "captures"
PARTIAL_SUFFIX = ".partial"
_PASSWORD_ENV = "PGPASSWORD"
_TABLES = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'eqos' AND table_type = 'BASE TABLE' ORDER BY table_name"
)
_CAPTURES = (
    "SELECT id, source_id, surface, request_key, capture_id, blob_sha256, record_sha256 "
    "FROM eqos.capture_refs ORDER BY id"
)
_FOREIGN_KEYS = (
    "SELECT conrelid::regclass::text, conname FROM pg_constraint "
    "WHERE contype = 'f' AND connamespace = 'eqos'::regnamespace ORDER BY 1, 2"
)
_UNRESOLVED_BINDINGS = (
    "SELECT b.target_store, b.row_handle FROM eqos.legacy_evidence_bindings b "
    "JOIN eqos.capture_refs c ON c.id = b.capture_ref_id WHERE c.blob_sha256 <> b.file_sha256 "
    "OR c.id = ANY(%s) ORDER BY 1, 2"
)
_SCHEMA_PRESENT = "SELECT to_regnamespace('eqos') IS NOT NULL"
_RUN_IDS = "SELECT id FROM eqos.runs ORDER BY id"
_PUBLISHED = "backup_published"

Capture = tuple[int, str, str, str, str, str, str]


class SchemaState(StrEnum):
    """Whether the backed-up database had the ``eqos`` schema (absent before migration)."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class BackupError(Exception):
    """A backup or restore step failed; nothing is published or reported as restored."""


class BackupManifest(BaseModel):
    """What one set holds, all read from the dump's own exported snapshot."""

    model_config = ConfigDict(frozen=True)

    backup_id: str
    database: DatabaseIdentity
    schema_state: SchemaState
    dump_sha256: str
    table_counts: dict[str, int]
    run_ids: tuple[int, ...]
    captures: tuple[Capture, ...]
    files: tuple[tuple[str, str], ...]


class RestoreCheck(BaseModel):
    """The restored database and snapshot root, checked against the manifest."""

    model_config = ConfigDict(frozen=True)

    schema_equal: bool
    run_ids_equal: bool
    counts_equal: bool
    fk_valid: bool
    missing_captures: tuple[int, ...]
    extra_captures: tuple[int, ...]
    hash_mismatches: tuple[int, ...]
    unresolved_bindings: tuple[tuple[str, int], ...]
    replay_mismatches: tuple[int, ...]

    @property
    def ok(self) -> bool:
        """Whether every check passed."""
        return (
            self.schema_equal
            and self.run_ids_equal
            and self.counts_equal
            and self.fk_valid
            and not self.missing_captures
            and not self.extra_captures
            and not self.hash_mismatches
            and not self.unresolved_bindings
            and not self.replay_mismatches
        )


def write_backup(
    settings: PgSettings,
    *,
    database: str,
    snapshot_root: Path,
    out_dir: Path,
    client_prefix: Sequence[str] = DEFAULT_CLIENT_PREFIX,
) -> Path:
    """Write, verify and publish one matched set of ``database``; return its directory."""
    backup_id = uuid.uuid4().hex
    staging = out_dir / f".{backup_id}{PARTIAL_SUFFIX}"
    staging.mkdir(mode=0o700, parents=True)
    source, archive = SnapshotStore(snapshot_root), SnapshotStore(staging / CAPTURES_DIR)
    try:
        with psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname=database)) as conn:
            conn.isolation_level, conn.read_only = IsolationLevel.REPEATABLE_READ, True
            with conn.transaction():
                snapshot = _scalar(conn, "SELECT pg_export_snapshot()")
                present = _scalar(conn, _SCHEMA_PRESENT)
                counts = _counts(conn) if present else {}
                run_ids = _column(conn, _RUN_IDS) if present else ()
                captures = _captures(conn) if present else ()
                with (staging / DUMP_FILE).open("wb") as dump:
                    _client(
                        client_prefix, settings, database,
                        ("pg_dump", "-Fc", f"--snapshot={snapshot}"), stdout=dump,
                    )  # fmt: skip
        for capture in captures:
            record, body = source.read_capture_verified(*capture[1:5])
            if not _matches(record.record_sha256, body, capture):
                raise BackupError(f"capture {capture[0]} differs from its registration")
            archive.put_capture(record, body)
    except (psycopg.Error, SnapshotError, OSError) as error:
        raise BackupError(f"backup of {database} failed: {type(error).__name__}") from error
    files = _hash_files(staging)
    manifest = BackupManifest(
        backup_id=backup_id,
        database=DatabaseIdentity(host=settings.host, port=settings.port, name=database),
        schema_state=SchemaState.PRESENT if present else SchemaState.ABSENT,
        dump_sha256=dict(files)[DUMP_FILE],
        table_counts=counts,
        run_ids=run_ids,
        captures=captures,
        files=files,
    )
    (staging / MANIFEST_FILE).write_text(yaml.safe_dump(manifest.model_dump(mode="json")))
    _verify(staging)
    published = staging.rename(out_dir / backup_id)
    structlog.get_logger(__name__).info(_PUBLISHED, backup_id=backup_id, captures=len(captures))
    return published


def verify_set(set_dir: Path) -> BackupManifest:
    """The set's manifest, refusing a staging directory or any missing, extra or changed file."""
    if set_dir.name.startswith(".") or set_dir.name.endswith(PARTIAL_SUFFIX):
        raise BackupError(f"{set_dir.name} is an unpublished set")
    return _verify(set_dir)


def restore_backup(
    set_dir: Path,
    settings: PgSettings,
    *,
    database: str,
    snapshot_root: Path,
    client_prefix: Sequence[str] = DEFAULT_CLIENT_PREFIX,
    replay_runs: bool,
    config_root: Path,
) -> RestoreCheck:
    """Restore a verified set into a new test database and an empty snapshot root, then check."""
    if not is_test_database(database):
        raise BackupError(f"restore refuses {database!r}: not an eqos_test_ database")
    check_test_db_name(database, settings)
    manifest = verify_set(set_dir)
    if snapshot_root.exists() and any(snapshot_root.iterdir()):
        raise BackupError(f"snapshot root {snapshot_root} is not empty")
    create_test_database(settings, database)
    with psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname=database)) as conn:
        if current_database(conn) != database:
            raise BackupError(f"connected to {current_database(conn)!r}, not {database!r}")
    with (set_dir / DUMP_FILE).open("rb") as dump:
        _client(client_prefix, settings, database, ("pg_restore", "--exit-on-error"), stdin=dump)
    archive, target = SnapshotStore(set_dir / CAPTURES_DIR), SnapshotStore(snapshot_root)
    for capture in manifest.captures:
        target.put_capture(*archive.read_capture_verified(*capture[1:5]))
    bad = tuple(capture[0] for capture in manifest.captures if not _restored(target, capture))
    counts: dict[str, int] = {}
    captures: tuple[Capture, ...] = ()
    unresolved: tuple[tuple[str, int], ...] = ()
    run_ids: tuple[int, ...] = ()
    replayed: tuple[int, ...] = ()
    fk_valid = True
    conninfo = settings.conninfo(PgRole.ADMIN, dbname=database)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        present = bool(_scalar(conn, _SCHEMA_PRESENT))
        if present:
            fk_valid = _validate_foreign_keys(conn)
            counts, captures = _counts(conn), _captures(conn)
            run_ids = _column(conn, _RUN_IDS)
            rows = conn.execute(_UNRESOLVED_BINDINGS, (list(bad),)).fetchall()
            unresolved = tuple((str(row[0]), int(row[1])) for row in rows)
    if present and replay_runs:
        with open_pool(settings, PgRole.RUNTIME, dbname=database) as pool:
            replayed = tuple(
                run_id
                for run_id in run_ids
                if replay_run(run_id, pool=pool, config_root=config_root)
                != load_results(run_id, pool=pool)
            )
    expected, restored = set(manifest.captures), set(captures)
    return RestoreCheck(
        schema_equal=(manifest.schema_state is SchemaState.PRESENT) == present,
        run_ids_equal=run_ids == manifest.run_ids,
        counts_equal=counts == manifest.table_counts,
        fk_valid=fk_valid,
        missing_captures=tuple(sorted(item[0] for item in expected - restored)),
        extra_captures=tuple(sorted(item[0] for item in restored - expected)),
        hash_mismatches=bad,
        unresolved_bindings=unresolved,
        replay_mismatches=replayed,
    )


def _restored(target: SnapshotStore, capture: Capture) -> bool:
    """Whether a capture re-reads from ``target`` with its registered record and blob hashes."""
    try:
        record, body = target.read_capture_verified(*capture[1:5])
    except SnapshotError:
        return False
    return _matches(record.record_sha256, body, capture)


def _matches(record_sha256: str, body: bytes, capture: Capture) -> bool:
    """Whether a record hash and body equal the registered ``record_sha256`` and ``blob_sha256``."""
    return record_sha256 == capture[6] and _sha256(body) == capture[5]


def _validate_foreign_keys(conn: psycopg.Connection[Any]) -> bool:
    """``VALIDATE CONSTRAINT`` every ``eqos`` foreign key; False on the first violation."""
    try:
        for table, constraint in conn.execute(_FOREIGN_KEYS).fetchall():
            conn.execute(
                sql.SQL("ALTER TABLE {} VALIDATE CONSTRAINT {}").format(
                    sql.SQL(table), sql.Identifier(constraint)
                )
            )
    except psycopg.errors.ForeignKeyViolation:
        return False
    return True


def _verify(set_dir: Path) -> BackupManifest:
    """Load the manifest and check every listed file, and only those, by hash."""
    try:
        manifest = BackupManifest.model_validate(
            yaml.safe_load((set_dir / MANIFEST_FILE).read_text())
        )
    except (OSError, ValueError) as error:
        raise BackupError(f"{set_dir.name} has no valid manifest") from error
    if _hash_files(set_dir) != manifest.files:
        raise BackupError(f"{set_dir.name} files differ from its manifest")
    if dict(manifest.files).get(DUMP_FILE) != manifest.dump_sha256:
        raise BackupError(f"{set_dir.name} dump differs from its manifest")
    if not _inventories_consistent(manifest):
        raise BackupError(f"{set_dir.name} manifest inventories disagree")
    return manifest


def _inventories_consistent(manifest: BackupManifest) -> bool:
    """Whether the run and capture inventories agree with the table counts and schema state."""
    if manifest.schema_state is SchemaState.ABSENT:
        return not (manifest.table_counts or manifest.run_ids or manifest.captures)
    counts = manifest.table_counts
    return counts.get("runs") == len(manifest.run_ids) and counts.get("capture_refs") == len(
        manifest.captures
    )


def _client(
    prefix: Sequence[str],
    settings: PgSettings,
    database: str,
    args: tuple[str, ...],
    *,
    stdin: IO[bytes] | None = None,
    stdout: IO[bytes] | None = None,
) -> None:
    """Run one PostgreSQL client as the admin role; the password travels only in the env."""
    target = ("-h", settings.host, "-p", str(settings.port), "-U", settings.user, "-d", database)
    env = {**os.environ, _PASSWORD_ENV: settings.password.get_secret_value()}
    try:
        subprocess.run(
            [*prefix, *args, *target], stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
            env=env, timeout=CLIENT_TIMEOUT_S, check=True,
        )  # fmt: skip
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip().splitlines()[-1:]
        raise BackupError(f"{args[0]} exited {error.returncode}: {detail}") from error
    except (subprocess.TimeoutExpired, OSError) as error:
        raise BackupError(f"{args[0]} failed: {type(error).__name__}") from error


def _counts(conn: psycopg.Connection[Any]) -> dict[str, int]:
    """Row count of every ``eqos`` table."""
    return {
        table: int(
            _scalar(conn, sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table)))
        )
        for table in _column(conn, _TABLES)
    }


def _captures(conn: psycopg.Connection[Any]) -> tuple[Capture, ...]:
    """Every registered capture; legacy bindings and run inputs reference these rows."""
    return tuple(cast(Capture, tuple(row)) for row in conn.execute(_CAPTURES).fetchall())


def _column(conn: psycopg.Connection[Any], query: str) -> tuple[Any, ...]:
    """The first column of every row."""
    return tuple(row[0] for row in conn.execute(query).fetchall())


def _scalar(conn: psycopg.Connection[Any], query: str | sql.Composed) -> Any:
    """The single value of a one-row query."""
    row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def _hash_files(root: Path) -> tuple[tuple[str, str], ...]:
    """``(relative path, sha256)`` of every file under ``root`` except its root manifest."""
    return tuple(
        (path.relative_to(root).as_posix(), _sha256(path.read_bytes()))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != root / MANIFEST_FILE
    )


def _sha256(data: bytes) -> str:
    """Hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()
