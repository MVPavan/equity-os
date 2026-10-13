"""Ordered, checksum-guarded, gap-tolerant SQL migrations and role bootstrap.

The runner applies every file not yet recorded — a set difference, never
"greater than the highest applied" — so a lower-numbered file merged after a
higher one still runs. An applied file whose bytes changed is refused: a
published migration is history, and editing it would fork every database that
already ran it.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

import psycopg
import structlog
from psycopg import sql
from pydantic import BaseModel, ConfigDict

from fundamentals.pg.settings import MIGRATOR_ROLE_NAME, RUNTIME_ROLE_NAME, PgSettings

MIGRATION_SUFFIX = ".sql"
MIGRATION_NAME_PATTERN = re.compile(r"^\d{4}_[a-z0-9]+(?:_[a-z0-9]+)*\.sql$")
# Arbitrary fixed key: every runner serialises on the same session advisory lock.
MIGRATION_LOCK_KEY = 4_215_031_001

_CREATE_META = b"""
CREATE SCHEMA IF NOT EXISTS eqos_meta;
CREATE TABLE IF NOT EXISTS eqos_meta.schema_migrations (
    filename   text PRIMARY KEY,
    sha256     text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""
_SELECT_APPLIED = "SELECT filename, sha256 FROM eqos_meta.schema_migrations"
_RECORD_APPLIED = (
    "INSERT INTO eqos_meta.schema_migrations (filename, sha256) VALUES (%s, %s) "
    "RETURNING applied_at"
)
_LOCK = "SELECT pg_advisory_lock(%s)"
_UNLOCK = "SELECT pg_advisory_unlock(%s)"
_ROLE_EXISTS = "SELECT 1 FROM pg_roles WHERE rolname = %s"
_BAD_NAME = "migration file names must match NNNN_<snake>.sql: {names}"
_CHECKSUM_DRIFT = "applied migration {filename} changed: recorded {recorded}, on disk {actual}"

_log = structlog.get_logger("fundamentals.pg.migrations")


class AppliedMigration(BaseModel):
    """One migration file this runner applied, with the checksum it recorded."""

    model_config = ConfigDict(frozen=True)

    filename: str
    sha256: str
    applied_at: datetime


class MigrationChecksumError(ValueError):
    """An already-applied migration file's bytes no longer match its record."""


class MigrationNameError(ValueError):
    """A file in the migrations directory is not named ``NNNN_<snake>.sql``."""


def bootstrap_roles(admin: psycopg.Connection, settings: PgSettings, dbname: str) -> None:
    """Create the migrator and runtime roles if missing and grant them the database.

    An existing role is never altered — not its password, not its attributes —
    so bootstrap is safe to repeat and cannot reset an operator's change.
    """
    with admin.transaction():
        for role_name, password in (
            (MIGRATOR_ROLE_NAME, settings.migrator_password),
            (RUNTIME_ROLE_NAME, settings.runtime_password),
        ):
            if admin.execute(_ROLE_EXISTS, (role_name,)).fetchone() is None:
                admin.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role_name), sql.Literal(password.get_secret_value())
                    )
                )
                _log.info("pg_role_created", role=role_name)
        database = sql.Identifier(dbname)
        admin.execute(
            sql.SQL("GRANT CONNECT, CREATE ON DATABASE {} TO {}").format(
                database, sql.Identifier(MIGRATOR_ROLE_NAME)
            )
        )
        admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                database, sql.Identifier(RUNTIME_ROLE_NAME)
            )
        )


def apply_migrations(
    migrator: psycopg.Connection, migrations_dir: Path
) -> tuple[AppliedMigration, ...]:
    """Apply every unrecorded migration in filename order, each in its own transaction.

    Returns only the migrations applied by this call; a re-run returns ``()``.
    """
    files = _migration_files(migrations_dir)
    with migrator.transaction():
        migrator.execute(_LOCK, (MIGRATION_LOCK_KEY,))
    try:
        with migrator.transaction():
            migrator.execute(_CREATE_META)
            recorded: dict[str, str] = {
                str(name): str(sha) for name, sha in migrator.execute(_SELECT_APPLIED).fetchall()
            }
        bodies = {path.name: path.read_bytes() for path in files}
        checksums = {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
        for filename, recorded_sha in recorded.items():
            actual = checksums.get(filename)
            if actual is not None and actual != recorded_sha:
                raise MigrationChecksumError(
                    _CHECKSUM_DRIFT.format(filename=filename, recorded=recorded_sha, actual=actual)
                )
        applied: list[AppliedMigration] = []
        for path in files:
            if path.name in recorded:
                continue
            with migrator.transaction():
                migrator.execute(bodies[path.name])
                row = migrator.execute(_RECORD_APPLIED, (path.name, checksums[path.name]))
                fetched = row.fetchone()
                assert fetched is not None
            applied.append(
                AppliedMigration(
                    filename=path.name, sha256=checksums[path.name], applied_at=fetched[0]
                )
            )
            _log.info("pg_migration_applied", filename=path.name)
        return tuple(applied)
    finally:
        with migrator.transaction():
            migrator.execute(_UNLOCK, (MIGRATION_LOCK_KEY,))


def _migration_files(migrations_dir: Path) -> tuple[Path, ...]:
    """The directory's ``.sql`` files in filename order, refusing any misnamed one."""
    files = sorted(
        (path for path in migrations_dir.iterdir() if path.suffix == MIGRATION_SUFFIX),
        key=lambda path: path.name,
    )
    misnamed = [path.name for path in files if not MIGRATION_NAME_PATTERN.match(path.name)]
    if misnamed:
        raise MigrationNameError(_BAD_NAME.format(names=", ".join(misnamed)))
    return tuple(files)
