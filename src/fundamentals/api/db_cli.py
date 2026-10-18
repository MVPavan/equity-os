"""The ``db`` command: bootstrap roles and apply migrations on the configured database.

    db bootstrap
    db migrate [--migrations-dir migrations]
    db backup --out DIR --snapshot-root R
    db restore --set DIR --database D --snapshot-root R [--backup-dir DIR] [--replay-runs]
        (--live-snapshot-root L | --unwitnessed) [--config-root config]
    db create-test --suffix S

All read ``PgSettings`` here, at the composition root. ``bootstrap`` runs as the admin role over
the ``postgres`` maintenance database; ``migrate`` runs as the migrator role, which owns every
object it creates. ``backup`` writes a matched set of ``EQOS_PG_DB``; ``restore`` names the new
``eqos_test_*`` ``--database``, exits nonzero unless every check passes, and as the purge login
purges first what the authority files in ``--backup-dir`` (default the set's parent) expired
after the set, refusing a journal not extending the head witnessed in ``--live-snapshot-root``
(``--unwitnessed``: live store lost; a journal rolled back with its witness is undetectable;
plan D9 R11, R12). ``create-test`` prints a new guarded ``eqos_test_<suffix>_<hex>`` database.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.retention_purge import PurgeRefusedError
from fundamentals.pg.approvals import TEST_DATABASE_PREFIX
from fundamentals.pg.backup import BackupError, restore_backup, write_backup
from fundamentals.pg.migrations import (
    LoginRoleError,
    MigrationChecksumError,
    MigrationNameError,
    apply_migrations,
    bootstrap_roles,
    create_login,
)
from fundamentals.pg.retention_io import AuthorityError
from fundamentals.pg.role_secrets import (
    MissingRoleSecretError,
    RoleSecretError,
    load_login,
    secrets_dir,
)
from fundamentals.pg.settings import GROUP_ROLES, PgRole, PgSettings
from fundamentals.pg.test_databases import HarnessGuardError, create_test_database
from fundamentals.retention.purge_first import restore_purge_first

DB_COMMAND = "db"
BOOTSTRAP_ACTION = "bootstrap"
MIGRATE_ACTION = "migrate"
BACKUP_ACTION = "backup"
RESTORE_ACTION = "restore"
CREATE_TEST_ACTION = "create-test"
MAINTENANCE_DB = "postgres"
DEFAULT_MIGRATIONS_DIR = "migrations"
DEFAULT_CONFIG_ROOT = "config"

_ACTION_DEST = "db_action"
_MIGRATIONS_DIR_FLAG = "--migrations-dir"
_HELP = "bootstrap PostgreSQL roles or apply evidence-schema migrations"
_BOOTSTRAP_HELP = (
    "create the migrator, runtime and group roles if missing, grant the database, and create "
    "the panel and owner logins named in the credential files"
)
_MIGRATE_HELP = "apply every unrecorded migration as the migrator role"
_MIGRATIONS_DIR_HELP = "directory of NNNN_<snake>.sql migration files"
_BACKUP_HELP = "write a matched backup set of EQOS_PG_DB and its referenced captures"
_RESTORE_HELP = "restore a verified set into a new eqos_test_* database and check it"
_CREATE_TEST_HELP = "create a guarded eqos_test_<suffix>_<hex> database and print its name"
_BOOTSTRAPPED = "bootstrapped\t{dbname}"
_PUBLISHED = "published\t{path}"
_APPLIED_HEADER = "applied\t{count}"
_REFUSED_EVENT = "db_command_refused"


def add_db_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``db`` and its actions."""
    parser = subparsers.add_parser(DB_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    actions.add_parser(BOOTSTRAP_ACTION, help=_BOOTSTRAP_HELP)
    migrate = actions.add_parser(MIGRATE_ACTION, help=_MIGRATE_HELP)
    migrate.add_argument(
        _MIGRATIONS_DIR_FLAG, default=DEFAULT_MIGRATIONS_DIR, help=_MIGRATIONS_DIR_HELP
    )
    backup = actions.add_parser(BACKUP_ACTION, help=_BACKUP_HELP)
    backup.add_argument("--out", required=True, type=Path)
    backup.add_argument("--snapshot-root", required=True, type=Path)
    restore = actions.add_parser(RESTORE_ACTION, help=_RESTORE_HELP)
    restore.add_argument("--set", required=True, type=Path)
    restore.add_argument("--database", required=True)
    restore.add_argument("--snapshot-root", required=True, type=Path)
    restore.add_argument("--backup-dir", type=Path)
    witness = restore.add_mutually_exclusive_group(required=True)
    witness.add_argument("--live-snapshot-root", type=Path)
    witness.add_argument("--unwitnessed", action="store_true")
    restore.add_argument("--replay-runs", action="store_true")
    restore.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    create_test = actions.add_parser(CREATE_TEST_ACTION, help=_CREATE_TEST_HELP)
    create_test.add_argument("--suffix", required=True)


def dispatch_db_command(args: argparse.Namespace) -> int | None:
    """Run the selected ``db`` action, or return ``None`` for any other command."""
    if args.command != DB_COMMAND:
        return None
    settings = PgSettings()
    action = getattr(args, _ACTION_DEST)
    try:
        if action == CREATE_TEST_ACTION:
            name = f"{TEST_DATABASE_PREFIX}{args.suffix}_{uuid.uuid4().hex[:12]}"
            create_test_database(settings, name)
            sys.stdout.write(name + "\n")
            return EXIT_OK
        if action == BACKUP_ACTION:
            published = write_backup(
                settings, database=settings.db, snapshot_root=args.snapshot_root, out_dir=args.out
            )
            sys.stdout.write(_PUBLISHED.format(path=published) + "\n")
            return EXIT_OK
        if action == RESTORE_ACTION:
            backup_dir, live = args.backup_dir or args.set.parent, args.live_snapshot_root
            check = restore_backup(
                args.set,
                settings,
                database=args.database,
                snapshot_root=args.snapshot_root,
                replay_runs=args.replay_runs,
                config_root=args.config_root,
                backup_dir=backup_dir,
                live_snapshot_root=live,
                purge_login=load_login(PgRole.PURGE, secrets_dir(os.environ)),
                purge_first=restore_purge_first(args.set, backup_dir, args.snapshot_root, live),
            )
            sys.stdout.write(check.model_dump_json() + "\n")
            return EXIT_OK if check.ok else EXIT_REFUSED
        if action == BOOTSTRAP_ACTION:
            with psycopg.connect(
                settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB), autocommit=True
            ) as admin:
                bootstrap_roles(admin, settings, settings.db)
                _create_logins(admin)
            sys.stdout.write(_BOOTSTRAPPED.format(dbname=settings.db) + "\n")
            return EXIT_OK
        with psycopg.connect(settings.conninfo(PgRole.MIGRATOR), autocommit=True) as migrator:
            applied = apply_migrations(migrator, Path(args.migrations_dir))
    except (
        psycopg.OperationalError,
        MigrationChecksumError,
        MigrationNameError,
        BackupError,
        HarnessGuardError,
        RoleSecretError,
        LoginRoleError,
        AuthorityError,
        PurgeRefusedError,
    ) as refusal:
        structlog.get_logger("fundamentals.db").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED
    lines = [_APPLIED_HEADER.format(count=len(applied)), *(item.filename for item in applied)]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK


def _create_logins(admin: psycopg.Connection) -> None:
    """Create each group-role login whose credential file exists; skip a missing file."""
    directory = secrets_dir(os.environ)
    for role in GROUP_ROLES:
        try:
            login = load_login(role, directory)
        except MissingRoleSecretError as missing:
            structlog.get_logger("fundamentals.db").info(
                "pg_role_login_skipped", role=role.value, detail=str(missing)
            )
            continue
        with admin.transaction():
            create_login(admin, role, login)
