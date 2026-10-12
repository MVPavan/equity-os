"""Isolated PostgreSQL databases for tests (D1a design decision 3).

Per session the harness creates ``<prefix>tpl_<hex>``, migrates it as the
migrator role and closes every connection to it. Per test it clones a fresh
``<prefix><hex>`` from that template and drops it afterwards. Nothing ever
deletes rows: the evidence triggers forbid it, and dropping the clone is the
cleanup.

The name guards are the only barrier between the tests and the owner's
database. They run before any connection is opened and again before every
create and drop; lifecycle DDL goes over an admin connection to the
``postgres`` maintenance database, never ``EQOS_PG_DB``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, ValidationError

from fundamentals.pg.migrations import apply_migrations, bootstrap_roles
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import ENV_PREFIX, PgRole, PgSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
MAINTENANCE_DB = "postgres"
TEMPLATE_INFIX = "tpl_"
_SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
_MAX_IDENTIFIER = 63

AdminConnector = Callable[[str], psycopg.Connection]


class HarnessGuardError(RuntimeError):
    """A test database name or prefix could reach a database the tests must not touch."""


def check_prefix(settings: PgSettings) -> None:
    """Refuse a prefix that is unsafe or would match the configured main database."""
    prefix = settings.test_db_prefix
    if not prefix or not _SAFE_NAME.match(prefix):
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
        or not _SAFE_NAME.match(name)
        or len(name) > _MAX_IDENTIFIER
        or name in (settings.db, MAINTENANCE_DB)
    ):
        raise HarnessGuardError(f"refusing database name {name!r}")


def mint_name(settings: PgSettings, *, template: bool = False) -> str:
    """A fresh, guarded test database name."""
    infix = TEMPLATE_INFIX if template else ""
    name = f"{settings.test_db_prefix}{infix}{uuid.uuid4().hex}"[:_MAX_IDENTIFIER]
    check_test_db_name(name, settings)
    return name


def _default_connector(conninfo: str) -> psycopg.Connection:
    """An autocommit admin connection, as CREATE and DROP DATABASE require."""
    return psycopg.connect(conninfo, autocommit=True)


def create_database(
    settings: PgSettings,
    name: str,
    *,
    template: str | None = None,
    connect: AdminConnector = _default_connector,
) -> None:
    """Create a guarded test database (optionally from a guarded template) and grant it."""
    check_test_db_name(name, settings)
    if template is not None:
        check_test_db_name(template, settings)
    with connect(settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)) as admin:
        check_test_db_name(name, settings)
        if template is None:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        else:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(name), sql.Identifier(template)
                )
            )
        bootstrap_roles(admin, settings, name)


def drop_database(
    settings: PgSettings, name: str, *, connect: AdminConnector = _default_connector
) -> None:
    """Drop a guarded test database, terminating any connection left open to it."""
    check_test_db_name(name, settings)
    with connect(settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)) as admin:
        check_test_db_name(name, settings)
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


def load_test_settings() -> PgSettings:
    """Settings for the harness, failing (never skipping) when they are incomplete."""
    try:
        settings = PgSettings()
    except ValidationError as exc:
        missing = sorted(ENV_PREFIX + str(error["loc"][0]).upper() for error in exc.errors())
        pytest.fail(f"PostgreSQL test settings incomplete; set {', '.join(missing)}", pytrace=False)
    check_prefix(settings)
    return settings


class PgTestDatabase(BaseModel):
    """One isolated, migrated test database and the settings that reach it."""

    model_config = ConfigDict(frozen=True)

    dbname: str
    settings: PgSettings

    def runtime_pool(self) -> ConnectionPool:
        """A pool authenticating as the runtime role on this database."""
        return open_pool(self.settings, PgRole.RUNTIME, dbname=self.dbname)

    def migrator_connection(self) -> psycopg.Connection:
        """An autocommit connection as the migration role on this database."""
        return psycopg.connect(
            self.settings.conninfo(PgRole.MIGRATOR, dbname=self.dbname), autocommit=True
        )

    def cli_env(self) -> dict[str, str]:
        """The ``EQOS_PG_*`` variables that point a CLI at this database."""
        settings = self.settings
        return {
            f"{ENV_PREFIX}HOST": settings.host,
            f"{ENV_PREFIX}PORT": str(settings.port),
            f"{ENV_PREFIX}DB": self.dbname,
            f"{ENV_PREFIX}USER": settings.user,
            f"{ENV_PREFIX}PASSWORD": settings.password.get_secret_value(),
            f"{ENV_PREFIX}MIGRATOR_PASSWORD": settings.migrator_password.get_secret_value(),
            f"{ENV_PREFIX}RUNTIME_PASSWORD": settings.runtime_password.get_secret_value(),
            f"{ENV_PREFIX}TEST_DB_PREFIX": settings.test_db_prefix,
        }


@pytest.fixture(scope="session")
def pg_template() -> Iterator[PgTestDatabase]:
    """A migrated template database for the session, dropped at the end."""
    settings = load_test_settings()
    name = mint_name(settings, template=True)
    try:
        create_database(settings, name)
    except psycopg.OperationalError as exc:
        pytest.fail(f"PostgreSQL unreachable for the test harness: {exc}", pytrace=False)
    try:
        with psycopg.connect(
            settings.conninfo(PgRole.MIGRATOR, dbname=name), autocommit=True
        ) as migrator:
            apply_migrations(migrator, MIGRATIONS_DIR)
        yield PgTestDatabase(dbname=name, settings=settings)
    finally:
        drop_database(settings, name)


@pytest.fixture
def pg_db(pg_template: PgTestDatabase) -> Iterator[PgTestDatabase]:
    """A fresh database cloned from the session template, dropped after the test."""
    settings = pg_template.settings
    name = mint_name(settings)
    create_database(settings, name, template=pg_template.dbname)
    try:
        yield PgTestDatabase(dbname=name, settings=settings)
    finally:
        drop_database(settings, name)
