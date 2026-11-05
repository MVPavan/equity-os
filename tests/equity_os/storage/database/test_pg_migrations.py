"""D1a Task 1: migration runner ordering, checksum drift, gap tolerance and harness guards.

The guards are what stand between the suite and the owner's database, so their
refusals are proven with a connection-factory spy: a refused name or prefix
must be refused before any connection is attempted.
"""

from __future__ import annotations

import os
import secrets
import uuid
from pathlib import Path

import psycopg
import pytest
from pg_support import (
    MIGRATIONS_DIR,
    PgTestDatabase,
    check_prefix,
    create_database,
    drop_database,
    privileged_copies,
)
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from pydantic import SecretStr

from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.interface.entry.cli import main
from equity_os.storage.database.migrations import (
    MigrationChecksumError,
    MigrationNameError,
    apply_migrations,
)
from equity_os.storage.database.role_secrets import (
    LOGIN_SUFFIX,
    SECRETS_DIR_ENV,
    PrivilegedPgSettings,
    RoleLogin,
)
from equity_os.storage.database.settings import ENV_PREFIX, GROUP_ROLES, PgRole, PgSettings
from equity_os.storage.database.test_databases import MAINTENANCE_DB, HarnessGuardError

_SCHEMA = "mig_probe"


def _write(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


def _applied_names(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT filename FROM eqos_meta.schema_migrations").fetchall()
    return {row[0] for row in rows}


@pytest.mark.pg
def test_migrations_apply_in_filename_order_and_rerun_applies_nothing(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """0002 alters what 0001 creates, so only filename order can apply them."""
    _write(tmp_path, "0002_add_note.sql", f"ALTER TABLE {_SCHEMA}.probe ADD COLUMN note text;")
    _write(
        tmp_path,
        "0001_create_probe.sql",
        f"CREATE SCHEMA {_SCHEMA}; CREATE TABLE {_SCHEMA}.probe (id int);",
    )
    with pg_db.migrator_connection() as conn:
        applied = apply_migrations(conn, tmp_path)
        assert [item.filename for item in applied] == ["0001_create_probe.sql", "0002_add_note.sql"]
        assert apply_migrations(conn, tmp_path) == ()
        columns = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = 'probe' ORDER BY ordinal_position",
            (_SCHEMA,),
        ).fetchall()
    assert [row[0] for row in columns] == ["id", "note"]


@pytest.mark.pg
def test_lower_numbered_file_added_later_is_applied(pg_db: PgTestDatabase, tmp_path: Path) -> None:
    """Gap tolerance: the runner applies the set difference, not "above the highest"."""
    _write(tmp_path, "0001_schema.sql", f"CREATE SCHEMA {_SCHEMA};")
    _write(tmp_path, "0003_late.sql", f"CREATE TABLE {_SCHEMA}.late (id int);")
    with pg_db.migrator_connection() as conn:
        apply_migrations(conn, tmp_path)
        _write(tmp_path, "0002_gap.sql", f"CREATE TABLE {_SCHEMA}.gap (id int);")
        applied = apply_migrations(conn, tmp_path)
        assert [item.filename for item in applied] == ["0002_gap.sql"]
        assert {"0001_schema.sql", "0002_gap.sql", "0003_late.sql"} <= _applied_names(conn)


@pytest.mark.pg
def test_edited_applied_file_is_refused(pg_db: PgTestDatabase, tmp_path: Path) -> None:
    """A published migration is history; changing its bytes must stop the runner."""
    _write(tmp_path, "0001_schema.sql", f"CREATE SCHEMA {_SCHEMA};")
    with pg_db.migrator_connection() as conn:
        apply_migrations(conn, tmp_path)
        _write(tmp_path, "0001_schema.sql", f"CREATE SCHEMA {_SCHEMA}; -- edited")
        _write(tmp_path, "0002_after.sql", f"CREATE TABLE {_SCHEMA}.after (id int);")
        with pytest.raises(MigrationChecksumError):
            apply_migrations(conn, tmp_path)
        assert "0002_after.sql" not in _applied_names(conn)


def test_misnamed_migration_file_is_refused(tmp_path: Path) -> None:
    """Only ``NNNN_<snake>.sql`` names are accepted, before any SQL is sent."""
    _write(tmp_path, "1_bad.sql", "SELECT 1;")

    class _NeverUsed:
        def __getattr__(self, name: str) -> object:
            raise AssertionError("the runner touched the connection before refusing")

    with pytest.raises(MigrationNameError):
        apply_migrations(_NeverUsed(), tmp_path)  # type: ignore[arg-type]


def _synthetic_settings(**overrides: object) -> PrivilegedPgSettings:
    placeholder = RoleLogin(login="admin", password=SecretStr("not-a-secret"))
    values: dict[str, object] = {
        "host": "127.0.0.1",
        "port": 1,
        "db": "equity_os",
        "admin": placeholder,
        "migrator": placeholder,
        "runtime_password": "not-a-secret",
    }
    values.update(overrides)
    return PrivilegedPgSettings(_env_file=None, **values)  # type: ignore[arg-type]


class _ConnectSpy:
    """Records the database and user each attempted connection names, never the conninfo."""

    def __init__(self) -> None:
        self.targets: list[tuple[str, str]] = []

    def __call__(self, conninfo: str) -> psycopg.Connection:
        parsed = conninfo_to_dict(conninfo)
        self.targets.append((str(parsed["dbname"]), str(parsed["user"])))
        raise psycopg.OperationalError("spy: no connection made")


@pytest.mark.parametrize("name", ["equity_os", "postgres", "scratch_db", "eqos_test_Upper"])
def test_harness_refuses_name_without_test_prefix_before_connecting(name: str) -> None:
    """A name the harness did not mint never reaches CREATE or DROP."""
    settings = _synthetic_settings()
    spy = _ConnectSpy()
    with pytest.raises(HarnessGuardError):
        create_database(settings, name, connect=spy)
    with pytest.raises(HarnessGuardError):
        drop_database(settings, name, connect=spy)
    assert spy.targets == []


def test_harness_refuses_prefix_matching_main_database_before_connecting() -> None:
    """A prefix that matches ``EQOS_PG_DB`` would let a test name the owner's database."""
    settings = _synthetic_settings(db="eqos_test_main")
    spy = _ConnectSpy()
    with pytest.raises(HarnessGuardError):
        check_prefix(settings)
    with pytest.raises(HarnessGuardError):
        create_database(settings, "eqos_test_main", connect=spy)
    with pytest.raises(HarnessGuardError):
        drop_database(settings, "eqos_test_abc", connect=spy)
    assert spy.targets == []


def test_harness_refuses_a_configured_prefix_outside_the_literal_test_namespace() -> None:
    """Config cannot widen the namespace: prefix ``equity_`` would otherwise reach equity_os."""
    settings = _synthetic_settings(db="eqos_stage2_main", test_db_prefix="equity_")
    spy = _ConnectSpy()
    with pytest.raises(HarnessGuardError):
        create_database(settings, "equity_os", connect=spy)
    with pytest.raises(HarnessGuardError):
        create_database(settings, "equity_x", template="equity_os", connect=spy)
    with pytest.raises(HarnessGuardError):
        drop_database(settings, "equity_os", connect=spy)
    assert spy.targets == []


def test_harness_lifecycle_connection_names_the_maintenance_database() -> None:
    """CREATE and DROP go over an admin connection to ``postgres``, never ``EQOS_PG_DB``."""
    settings = _synthetic_settings()
    spy = _ConnectSpy()
    with pytest.raises(psycopg.OperationalError):
        create_database(settings, "eqos_test_abc", connect=spy)
    with pytest.raises(psycopg.OperationalError):
        drop_database(settings, "eqos_test_abc", connect=spy)
    assert spy.targets == [(MAINTENANCE_DB, "admin"), (MAINTENANCE_DB, "admin")]


def test_runtime_settings_never_hold_admin_or_migrator_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An admin login can ``SET ROLE eqos_owner``, so a runtime process must not hold one: even
    an ``.env`` still carrying the admin and migrator passwords yields settings that cannot
    connect as either, and keep neither value (bead eqos-z53). Compose-only keys are ignored."""
    for key in [key for key in os.environ if key.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "EQOS_PG_DATA_DIR=/somewhere/pgdata",
                "EQOS_PG_HOST=127.0.0.1",
                "EQOS_PG_PORT=55432",
                "EQOS_PG_DB=equity_os",
                "EQOS_PG_USER=equity_os",
                "EQOS_PG_PASSWORD=admin-placeholder",
                "EQOS_PG_MIGRATOR_PASSWORD=migrator-placeholder",
                "EQOS_PG_RUNTIME_PASSWORD=placeholder",
            )
        ),
        encoding="utf-8",
    )
    settings = PgSettings(_env_file=env_file)  # type: ignore[call-arg]
    assert (settings.host, settings.port, settings.db) == ("127.0.0.1", 55432, "equity_os")
    assert settings.test_db_prefix == "eqos_test_"
    assert "placeholder" not in repr(settings)
    for role in (PgRole.ADMIN, PgRole.MIGRATOR):
        with pytest.raises(ValueError, match="needs privileged settings"):
            settings.conninfo(role)
    held = str(settings.model_dump())
    assert "admin-placeholder" not in held and "migrator-placeholder" not in held


@pytest.mark.pg
def test_db_cli_bootstraps_and_migrates_the_configured_database(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The composition root reads settings from the environment and runs both actions."""
    for key, value in pg_db.cli_env().items():
        monkeypatch.setenv(key, value)
    assert PgSettings().db == pg_db.dbname
    assert main(["db", "bootstrap"]) == 0
    assert main(["db", "migrate", "--migrations-dir", str(MIGRATIONS_DIR)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "applied\t0"


@pytest.mark.pg
def test_db_bootstrap_creates_file_named_logins_and_refuses_a_foreign_one(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``db bootstrap`` creates a login its credential file names, in its group, able to log in;
    a file naming an existing role outside the group is refused and the role is never granted."""
    settings = pg_db.settings
    fresh, foreign = (
        f"{settings.test_db_prefix}{name}_{uuid.uuid4().hex[:12]}" for name in ("boot", "foreign")
    )
    password = secrets.token_urlsafe(32)
    for key, value in {**pg_db.cli_env(), SECRETS_DIR_ENV: str(tmp_path)}.items():
        monkeypatch.setenv(key, value)

    def credential(role: PgRole, login: str) -> None:
        path = tmp_path / f"{GROUP_ROLES[role]}{LOGIN_SUFFIX}"
        path.unlink(missing_ok=True)
        path.write_text(f"{login}:{password}\n")
        path.chmod(0o600)

    with privileged_copies(settings, tmp_path):
        member = "SELECT pg_has_role(%s, %s, 'MEMBER')"
        admin_info = settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)
        try:
            credential(PgRole.PANEL, fresh)
            assert main(["db", "bootstrap"]) == EXIT_OK
            with psycopg.connect(admin_info, autocommit=True) as admin:
                panel = GROUP_ROLES[PgRole.PANEL]
                assert admin.execute(member, (fresh, panel)).fetchone() == (True,)
                admin.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(foreign)))
            login = conninfo_to_dict(settings.conninfo(PgRole.RUNTIME, dbname=pg_db.dbname))
            with psycopg.connect(**{**login, "user": fresh, "password": password}) as conn:
                assert conn.execute("SELECT current_user").fetchone() == (fresh,)
            credential(PgRole.OWNER, foreign)
            assert main(["db", "bootstrap"]) == EXIT_REFUSED
            with psycopg.connect(admin_info, autocommit=True) as admin:
                owner = GROUP_ROLES[PgRole.OWNER]
                assert admin.execute(member, (foreign, owner)).fetchone() == (False,)
        finally:
            with psycopg.connect(admin_info, autocommit=True) as admin:
                for role in (fresh, foreign):
                    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
