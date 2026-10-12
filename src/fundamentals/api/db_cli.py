"""The ``db`` command: bootstrap roles and apply migrations on the configured database.

    db bootstrap
    db migrate [--migrations-dir migrations]

Both read ``PgSettings`` here, at the composition root. ``bootstrap`` runs as
the admin role over the ``postgres`` maintenance database; ``migrate`` runs as
the migrator role, which owns every object it creates.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.pg.migrations import (
    MigrationChecksumError,
    MigrationNameError,
    apply_migrations,
    bootstrap_roles,
)
from fundamentals.pg.settings import PgRole, PgSettings

DB_COMMAND = "db"
BOOTSTRAP_ACTION = "bootstrap"
MIGRATE_ACTION = "migrate"
MAINTENANCE_DB = "postgres"
DEFAULT_MIGRATIONS_DIR = "migrations"

_ACTION_DEST = "db_action"
_MIGRATIONS_DIR_FLAG = "--migrations-dir"
_HELP = "bootstrap PostgreSQL roles or apply evidence-schema migrations"
_BOOTSTRAP_HELP = "create the migrator and runtime roles if missing and grant the database"
_MIGRATE_HELP = "apply every unrecorded migration as the migrator role"
_MIGRATIONS_DIR_HELP = "directory of NNNN_<snake>.sql migration files"
_BOOTSTRAPPED = "bootstrapped\t{dbname}"
_APPLIED_HEADER = "applied\t{count}"
_REFUSED_EVENT = "db_command_refused"


def add_db_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``db`` and its two actions."""
    parser = subparsers.add_parser(DB_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    actions.add_parser(BOOTSTRAP_ACTION, help=_BOOTSTRAP_HELP)
    migrate = actions.add_parser(MIGRATE_ACTION, help=_MIGRATE_HELP)
    migrate.add_argument(
        _MIGRATIONS_DIR_FLAG, default=DEFAULT_MIGRATIONS_DIR, help=_MIGRATIONS_DIR_HELP
    )


def dispatch_db_command(args: argparse.Namespace) -> int | None:
    """Run the selected ``db`` action, or return ``None`` for any other command."""
    if args.command != DB_COMMAND:
        return None
    settings = PgSettings()
    try:
        if getattr(args, _ACTION_DEST) == BOOTSTRAP_ACTION:
            with psycopg.connect(
                settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB), autocommit=True
            ) as admin:
                bootstrap_roles(admin, settings, settings.db)
            sys.stdout.write(_BOOTSTRAPPED.format(dbname=settings.db) + "\n")
            return EXIT_OK
        with psycopg.connect(settings.conninfo(PgRole.MIGRATOR), autocommit=True) as migrator:
            applied = apply_migrations(migrator, Path(args.migrations_dir))
    except (psycopg.OperationalError, MigrationChecksumError, MigrationNameError) as refusal:
        structlog.get_logger("fundamentals.db").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED
    lines = [_APPLIED_HEADER.format(count=len(applied)), *(item.filename for item in applied)]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK
