"""Isolated PostgreSQL databases for tests (D1a design decision 3).

Per session the harness creates ``<prefix>tpl_<hex>``, migrates it as the
migrator role and closes every connection to it. Per test it clones a fresh
``<prefix><hex>`` from that template and drops it afterwards. Nothing ever
deletes rows: the evidence triggers forbid it, and dropping the clone is the
cleanup.

The name guards, and guarded create and drop, live in
``fundamentals.pg.test_databases``; they are re-exported here for the tests.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, ValidationError

from fundamentals.pg.migrations import apply_migrations
from fundamentals.pg.pool import open_pool
from fundamentals.pg.settings import ENV_PREFIX, PgRole, PgSettings
from fundamentals.pg.test_databases import (
    MAX_IDENTIFIER,
    check_prefix,
    check_test_db_name,
)
from fundamentals.pg.test_databases import create_test_database as create_database
from fundamentals.pg.test_databases import drop_test_database as drop_database

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
TEMPLATE_INFIX = "tpl_"


def mint_name(settings: PgSettings, *, template: bool = False) -> str:
    """A fresh, guarded test database name."""
    infix = TEMPLATE_INFIX if template else ""
    name = f"{settings.test_db_prefix}{infix}{uuid.uuid4().hex}"[:MAX_IDENTIFIER]
    check_test_db_name(name, settings)
    return name


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
