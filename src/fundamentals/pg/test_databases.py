"""Guarded creation and removal of ``eqos_test_*`` databases (D1a design decision 3).

The name guards are the only barrier between test-target operations and the
owner's database. They run before any connection is opened and again before
every create and drop; lifecycle DDL goes over an admin connection to the
``postgres`` maintenance database, never ``EQOS_PG_DB``.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import psycopg
from psycopg import sql

from fundamentals.pg.approvals import TEST_DATABASE_PREFIX
from fundamentals.pg.migrations import bootstrap_roles
from fundamentals.pg.role_secrets import PrivilegedPgSettings
from fundamentals.pg.settings import GROUP_ROLES, MIGRATOR_ROLE_NAME, PgRole, PgSettings

MAINTENANCE_DB = "postgres"
SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
MAX_IDENTIFIER = 63

AdminConnector = Callable[[str], psycopg.Connection]


class HarnessGuardError(RuntimeError):
    """A test database name or prefix could reach a database the tests must not touch."""


def check_prefix(settings: PgSettings) -> None:
    """Refuse a prefix outside the literal ``eqos_test_`` namespace or matching EQOS_PG_DB."""
    prefix = settings.test_db_prefix
    if not prefix.startswith(TEST_DATABASE_PREFIX) or not SAFE_NAME.match(prefix):
        raise HarnessGuardError(f"unsafe test database prefix {prefix!r}")
    if settings.db.startswith(prefix) or prefix.startswith(settings.db):
        raise HarnessGuardError(
            f"test database prefix {prefix!r} would match EQOS_PG_DB {settings.db!r}"
        )
    if MAINTENANCE_DB.startswith(prefix):
        raise HarnessGuardError(f"test database prefix {prefix!r} matches {MAINTENANCE_DB}")


def check_test_db_name(name: str, settings: PgSettings) -> None:
    """Refuse any database name the harness did not mint under the test prefix."""
    check_prefix(settings)
    if (
        not name.startswith(settings.test_db_prefix)
        or not SAFE_NAME.match(name)
        or len(name) > MAX_IDENTIFIER
        or name in (settings.db, MAINTENANCE_DB)
    ):
        raise HarnessGuardError(f"refusing database name {name!r}")


def _default_connector(conninfo: str) -> psycopg.Connection:
    """An autocommit admin connection, as CREATE and DROP DATABASE require."""
    return psycopg.connect(conninfo, autocommit=True)


def create_test_database(
    settings: PrivilegedPgSettings,
    name: str,
    *,
    template: str | None = None,
    closed: bool = False,
    connect: AdminConnector = _default_connector,
) -> None:
    """Create a guarded test database (optionally from a guarded template) and grant it; a
    ``closed`` one admits only the migrator and the purge group until :func:`open_test_database`
    (restore, plan D9 R12)."""
    check_test_db_name(name, settings)
    if template is not None:
        check_test_db_name(template, settings)
    with connect(settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)) as admin:
        check_test_db_name(name, settings)
        database = sql.Identifier(name)
        if template is None:
            closing = sql.SQL(" ALLOW_CONNECTIONS false" if closed else "")
            admin.execute(sql.SQL("CREATE DATABASE {}{}").format(database, closing))
        else:
            copy = sql.SQL("CREATE DATABASE {} TEMPLATE {}")
            admin.execute(copy.format(database, sql.Identifier(template)))
        if not closed:
            bootstrap_roles(admin, settings, name)
            return
        roles = sql.Identifier(MIGRATOR_ROLE_NAME), sql.Identifier(GROUP_ROLES[PgRole.PURGE])
        admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(database))
        admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(database, *roles))
        admin.execute(sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(database))


def open_test_database(settings: PrivilegedPgSettings, name: str) -> None:
    """Grant a closed test database to every role (restore's last step)."""
    check_test_db_name(name, settings)
    with _default_connector(settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)) as admin:
        bootstrap_roles(admin, settings, name)


def drop_test_database(
    settings: PrivilegedPgSettings, name: str, *, connect: AdminConnector = _default_connector
) -> None:
    """Drop a guarded test database, terminating any connection left open to it."""
    check_test_db_name(name, settings)
    with connect(settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)) as admin:
        check_test_db_name(name, settings)
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
