"""Matched backup and restore of the PostgreSQL store and its captures (data spec §6, D2 Task 5).

A set is one exported snapshot: the custom-format dump, the table counts, the stored-run ids and
the referenced captures are all read from it, so the manifest and the dump cannot disagree. The
set is staged under ``.<id>.partial`` and renamed into place only once it verifies. Restore
verifies the set first and only ever targets a fresh ``eqos_test_*`` database (design decision
6); a production restore is the owner's runbook, not code. Every client or SQL failure is fatal.

Retention (plan D9 R12): a backup holds the retention lock shared from before its export until
the set is published, refuses an unfinished purge and missing authority files, archives the
body of every retained capture and only the ``record.json`` of every other one, lists those in
``expired`` and records the expiry journal's last event id as its watermark.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from collections.abc import Sequence
from contextlib import ExitStack
from enum import StrEnum
from pathlib import Path
from typing import IO, Any, cast

import psycopg
import structlog
import yaml
from psycopg import sql
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run import load_results, replay_run
from fundamentals.compare.run_models import DatabaseIdentity
from fundamentals.contracts.retention import CaptureState, JournalEventKind
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.pg.approvals import current_database, is_test_database
from fundamentals.pg.pool import open_pool
from fundamentals.pg.retention_io import (
    AuthorityError,
    authority_absent,
    holds_exclusive,
    init_authority,
    read_authority,
    session_shared,
)
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
_UNRESOLVED = (
    "SELECT b.target_store, b.row_handle FROM eqos.legacy_evidence_bindings b "
    "JOIN eqos.capture_refs c ON c.id = b.capture_ref_id WHERE c.blob_sha256 <> b.file_sha256 "
    "OR c.id = ANY(%(bad)s) UNION SELECT r.target_store, r.handle FROM eqos.fact_rows r "
    "WHERE NOT EXISTS (SELECT 1 FROM eqos.capture_refs c WHERE c.blob_sha256 = r.file_sha256 "
    "AND c.id <> ALL(%(bad)s)) ORDER BY 1, 2"
)
_SCHEMA_PRESENT = "SELECT to_regnamespace('eqos') IS NOT NULL"
_STATES = (
    "SELECT r.id, eqos.capture_state(r.id), a.url, (SELECT max(p.id) FROM eqos.purge_records p "
    "WHERE p.capture_ref_id = r.id) FROM eqos.capture_refs r "
    "LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id"
)
_PENDING = "SELECT kind, id FROM eqos.retention_pending ORDER BY kind, id"
_UNTOUCHED = (
    "SELECT NOT EXISTS (SELECT 1 FROM eqos.licence_ends) AND NOT EXISTS "
    "(SELECT 1 FROM eqos.capture_states WHERE state = 'EXPIRED')"
)
_RETAINED = frozenset({CaptureState.RETAINED, CaptureState.RESTORED})
_RUN_IDS = "SELECT id FROM eqos.runs ORDER BY id"
_PUBLISHED = "backup_published"

Capture = tuple[int, str, str, str, str, str, str]


class SchemaState(StrEnum):
    """Whether the backed-up database had the ``eqos`` schema (absent before migration)."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class BackupError(Exception):
    """A backup or restore step failed; nothing is published or reported as restored."""


class ExpiredCapture(BaseModel):
    """A capture whose body the set does not hold, only its registered ``record.json``."""

    model_config = ConfigDict(frozen=True)

    capture: Capture
    url: str | None
    purge_record_id: int | None = None


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
    expired: tuple[ExpiredCapture, ...] = ()
    journal_watermark: int = 0


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
    held: psycopg.Connection[Any] | None = None,
) -> Path:
    """Write, verify and publish one matched set of ``database``; return its directory.

    ``held`` is a purge's own autocommit connection holding the retention lock exclusive: its
    finished run (one with a ``COMPLETE`` event) does not count as pending recovery.
    """
    backup_id = uuid.uuid4().hex
    staging = out_dir / f".{backup_id}{PARTIAL_SUFFIX}"
    source, archive = SnapshotStore(snapshot_root), SnapshotStore(staging / CAPTURES_DIR)
    try:
        with ExitStack() as stack:
            conn = held or stack.enter_context(
                psycopg.connect(settings.conninfo(PgRole.ADMIN, dbname=database), autocommit=True)
            )
            present = bool(_scalar(conn, _SCHEMA_PRESENT))
            watermark, fresh = _retention_preflight(conn, out_dir, held) if present else (0, False)
            staging.mkdir(mode=0o700, parents=True)
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                snapshot = _scalar(conn, "SELECT pg_export_snapshot()")
                counts = _counts(conn) if present else {}
                run_ids = _column(conn, _RUN_IDS) if present else ()
                everything = _captures(conn) if present else ()
                states = {row[0]: row[1:] for row in conn.execute(_STATES)} if present else {}
                if present and conn.execute(_UNRESOLVED, {"bad": []}).fetchone() is not None:
                    raise BackupError(f"{database} has a fact whose original is not registered")
                with (staging / DUMP_FILE).open("wb") as dump:
                    _client(
                        client_prefix, settings, database,
                        ("pg_dump", "-Fc", f"--snapshot={snapshot}"), stdout=dump,
                    )  # fmt: skip
            captures = tuple(c for c in everything if states[c[0]][0] in _RETAINED)
            expired = tuple(
                ExpiredCapture(capture=c, url=states[c[0]][1], purge_record_id=states[c[0]][2])
                for c in everything
                if c not in captures
            )
            for capture in captures:
                record, body = source.read_capture_verified(*capture[1:5])
                if not _matches(record.record_sha256, body, capture):
                    raise BackupError(f"capture {capture[0]} differs from its registration")
                archive.put_capture(record, body)
            for item in expired:
                kept = source.read_record(*item.capture[1:5], item.capture[6])
                archive.put_record(kept, item.capture[6])
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
                expired=expired,
                journal_watermark=watermark,
            )
            (staging / MANIFEST_FILE).write_text(yaml.safe_dump(manifest.model_dump(mode="json")))
            _verify(staging)
            published = staging.rename(out_dir / backup_id)
            if fresh:
                init_authority(out_dir)
    except (psycopg.Error, SnapshotError, OSError, AuthorityError) as error:
        raise BackupError(f"backup of {database} failed: {type(error).__name__}") from error
    structlog.get_logger(__name__).info(_PUBLISHED, backup_id=backup_id, captures=len(captures))
    return published


def _retention_preflight(
    conn: psycopg.Connection[Any], out_dir: Path, held: psycopg.Connection[Any] | None
) -> tuple[int, bool]:
    """Take the shared lock (unless ``held``), refuse an unfinished purge or missing authority;
    return the journal watermark and whether this backup initialises the authority files."""
    if held is None:
        session_shared(conn)
    elif not holds_exclusive(held):
        raise BackupError("held= needs the connection holding the retention lock exclusive")
    pending = conn.execute(_PENDING).fetchall()
    fresh = authority_absent(out_dir)
    if fresh and ((out_dir.exists() and any(out_dir.iterdir())) or not _scalar(conn, _UNTOUCHED)):
        raise BackupError(f"{out_dir} has no retention authority files and is not new")
    try:
        journal = () if fresh else read_authority(out_dir).journal
    except AuthorityError as error:
        raise BackupError(f"retention authority refused: {error}") from error
    completed = {e.run_id for e in journal if e.kind is JournalEventKind.COMPLETE}
    unfinished = [p for p in pending if not (held and p[0] == "RUN" and p[1] in completed)]
    if unfinished:
        raise BackupError(f"a purge is unfinished {unfinished}; run fundamentals retention purge")
    return (journal[-1].id if journal else 0), fresh


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
            rows = conn.execute(_UNRESOLVED, {"bad": list(bad)}).fetchall()
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
    """Load the manifest, check every listed file (and only those) and every capture by hash."""
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
    archive = SnapshotStore(set_dir / CAPTURES_DIR)
    if not all(_restored(archive, capture) for capture in manifest.captures):
        raise BackupError(f"{set_dir.name} captures differ from its manifest")
    try:
        for item in manifest.expired:
            archive.read_record(*item.capture[1:5], item.capture[6])
    except SnapshotError as error:
        raise BackupError(f"{set_dir.name} expired records differ from its manifest") from error
    return manifest


def _inventories_consistent(manifest: BackupManifest) -> bool:
    """Whether the run and capture inventories agree with the table counts and schema state."""
    if manifest.schema_state is SchemaState.ABSENT:
        return not (manifest.table_counts or manifest.run_ids or manifest.captures)
    counts = manifest.table_counts
    registered = len(manifest.captures) + len(manifest.expired)
    return counts.get("runs") == len(manifest.run_ids) and counts.get("capture_refs") == registered


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
