"""Isolated PostgreSQL databases for tests (D1a design decision 3).

Per session the harness creates ``<prefix>tpl_<hex>``, migrates it as the
migrator role and closes every connection to it. It also creates one randomized login per
group role (``GROUP_ROLES``), writes their 0600 credential files to a temporary secrets
directory, and drops the logins at session end (plan D3, D2). The admin and migrator logins come
from the real secrets directory, as for any privileged command; the harness copies them into the
temporary one for CLI subprocesses and deletes those copies at session end (bead eqos-z53). Per test
it clones a fresh ``<prefix><hex>`` from that template and drops it afterwards. Nothing ever
deletes rows: the evidence triggers forbid it, and dropping the clone is the
cleanup.

The name guards, and guarded create and drop, live in
``equity_os.storage.database.test_databases``; they are re-exported here for the tests.
"""

from __future__ import annotations

import os
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from equity_os.storage.database.migrations import apply_migrations, create_login
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.role_secrets import (
    CREDENTIAL_FILES,
    LOGIN_SUFFIX,
    SECRETS_DIR_ENV,
    PrivilegedPgSettings,
    RoleLogin,
    RoleSecretError,
    load_privileged,
)
from equity_os.storage.database.settings import ENV_PREFIX, GROUP_ROLES, PgRole, PgSettings
from equity_os.storage.database.test_databases import (
    MAINTENANCE_DB,
    MAX_IDENTIFIER,
    check_prefix,
    check_test_db_name,
)
from equity_os.storage.database.test_databases import create_test_database as create_database
from equity_os.storage.database.test_databases import drop_test_database as drop_database

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
TEMPLATE_INFIX = "tpl_"
# DROP DATABASE waits for a forced cluster checkpoint; with many workers cloning and dropping,
# queued checkpoints outlast the 30 s runtime statement timeout (eqos-1kq).
DROP_TIMEOUT = "SET statement_timeout = '5min'"


def mint_name(settings: PgSettings, *, template: bool = False) -> str:
    """A fresh, guarded test database name."""
    infix = TEMPLATE_INFIX if template else ""
    name = f"{settings.test_db_prefix}{infix}{uuid.uuid4().hex}"[:MAX_IDENTIFIER]
    check_test_db_name(name, settings)
    return name


def _drop_connector(conninfo: str) -> psycopg.Connection:
    """An admin connection whose DROP DATABASE may wait out a loaded cluster's checkpoints."""
    connection = psycopg.connect(conninfo, autocommit=True)
    connection.execute(DROP_TIMEOUT)
    return connection


def load_test_settings() -> PrivilegedPgSettings:
    """Settings for the harness, failing (never skipping) when they are incomplete."""
    try:
        settings = load_privileged(os.environ)
    except ValidationError as exc:
        missing = sorted(ENV_PREFIX + str(error["loc"][0]).upper() for error in exc.errors())
        pytest.fail(f"PostgreSQL test settings incomplete; set {', '.join(missing)}", pytrace=False)
    except RoleSecretError as exc:
        pytest.fail(f"PostgreSQL test credentials unusable: {exc}", pytrace=False)
    check_prefix(settings)
    return settings


class PgTestDatabase(BaseModel):
    """One isolated, migrated test database, the settings that reach it and the session logins.

    Databases built outside the session fixtures carry no logins.
    """

    model_config = ConfigDict(frozen=True)

    dbname: str
    settings: PrivilegedPgSettings
    logins: dict[PgRole, RoleLogin] = Field(default_factory=dict)
    secrets_dir: Path | None = None

    def runtime_pool(self) -> ConnectionPool:
        """A pool authenticating as the runtime role on this database."""
        return open_pool(self.settings, PgRole.RUNTIME, dbname=self.dbname)

    def panel_pool(self) -> ConnectionPool:
        """A pool authenticating as the session's panel login."""
        return self.role_pool(PgRole.PANEL)

    def owner_pool(self) -> ConnectionPool:
        """A pool authenticating as the session's owner login."""
        return self.role_pool(PgRole.OWNER)

    def role_pool(self, role: PgRole) -> ConnectionPool:
        """A pool for any role, with the session login where the role needs one."""
        login = self.logins.get(role)
        return open_pool(self.settings, role, dbname=self.dbname, login=login)

    def conninfo(self, role: PgRole) -> str:
        """A connection string for any role on this database."""
        return self.settings.conninfo(role, dbname=self.dbname, login=self.logins.get(role))

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
            f"{ENV_PREFIX}RUNTIME_PASSWORD": settings.runtime_password.get_secret_value(),
            f"{ENV_PREFIX}TEST_DB_PREFIX": settings.test_db_prefix,
            **({SECRETS_DIR_ENV: str(self.secrets_dir)} if self.secrets_dir else {}),
        }


def _write_login(directory: Path, role: PgRole, login: RoleLogin) -> Path:
    """Write ``login`` to the role's new 0600 credential file in ``directory``."""
    path = directory / f"{CREDENTIAL_FILES[role]}{LOGIN_SUFFIX}"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"{login.login}:{login.password.get_secret_value()}\n")
    return path


@contextmanager
def privileged_copies(settings: PrivilegedPgSettings, directory: Path) -> Iterator[None]:
    """Copy the admin and migrator logins into ``directory`` for CLI subprocesses; delete the
    copies after, so the real passwords never outlive the test."""
    pairs = ((PgRole.ADMIN, settings.admin), (PgRole.MIGRATOR, settings.migrator))
    paths = [_write_login(directory, role, login) for role, login in pairs]
    try:
        yield
    finally:
        for path in paths:
            path.unlink()


@contextmanager
def _session_logins(
    settings: PrivilegedPgSettings, directory: Path
) -> Iterator[dict[PgRole, RoleLogin]]:
    """Create one randomized login per group role and its 0600 file; drop the logins after."""
    logins = {
        role: RoleLogin(
            login=f"{settings.test_db_prefix}{role.value.lower()}_{uuid.uuid4().hex[:12]}",
            password=SecretStr(secrets.token_urlsafe(32)),
        )
        for role in GROUP_ROLES
    }
    admin_conninfo = settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)
    try:
        with psycopg.connect(admin_conninfo, autocommit=True) as admin:
            for role, login in logins.items():
                create_login(admin, role, login)
                _write_login(directory, role, login)
        yield logins
    finally:
        with psycopg.connect(admin_conninfo, autocommit=True) as admin:
            for login in logins.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login.login)))


@pytest.fixture(scope="session")
def pg_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[PgTestDatabase]:
    """A migrated template database and the session logins, dropped at the end."""
    settings = load_test_settings()
    name = mint_name(settings, template=True)
    try:
        create_database(settings, name)
    except psycopg.OperationalError as exc:
        pytest.fail(f"PostgreSQL unreachable for the test harness: {exc}", pytrace=False)
    directory = tmp_path_factory.mktemp("secrets")
    try:
        with psycopg.connect(
            settings.conninfo(PgRole.MIGRATOR, dbname=name), autocommit=True
        ) as migrator:
            apply_migrations(migrator, MIGRATIONS_DIR)
        with privileged_copies(settings, directory), _session_logins(settings, directory) as logins:
            yield PgTestDatabase(
                dbname=name, settings=settings, logins=logins, secrets_dir=directory
            )
    finally:
        drop_database(settings, name, connect=_drop_connector)


@contextmanager
def cloned_database(template: PgTestDatabase) -> Iterator[PgTestDatabase]:
    """A fresh database cloned from ``template``, dropped on exit."""
    settings = template.settings
    name = mint_name(settings)
    create_database(settings, name, template=template.dbname)
    try:
        yield template.model_copy(update={"dbname": name})
    finally:
        drop_database(settings, name, connect=_drop_connector)


@pytest.fixture
def pg_db(pg_template: PgTestDatabase) -> Iterator[PgTestDatabase]:
    """A fresh database cloned from the session template, dropped after the test."""
    with cloned_database(pg_template) as database:
        yield database
