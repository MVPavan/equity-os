"""The live-state preflight fails loudly on an empty or unseeded database (bead eqos-px2).

Incident eqos-89z: the live database ran empty for 9 days while every test stayed green, because
tests only touch ``eqos_test_*`` databases. These cases point the check at guarded test databases.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
from pg_support import MIGRATIONS_DIR, REPO_ROOT, PgTestDatabase, mint_name
from pg_support import create_database as create_test_database
from pg_support import drop_database as drop_test_database

from fundamentals.api.cli import main
from fundamentals.pg.identity_seed import load_issuer_identity, seed_issuer_identity
from fundamentals.pg.live_check import LiveCheckError, check_live
from fundamentals.pg.settings import PgRole

pytestmark = pytest.mark.pg

ISSUER = load_issuer_identity(REPO_ROOT / "config/identity/aparinds.yaml")
_STORE = "INSERT INTO eqos.fact_stores VALUES ('sqlite-test', 'LEGACY_SQLITE', 'facts.db', 'ab')"
_EVENT = (
    "INSERT INTO eqos.fact_store_events (store_id, operation_id, state, recorded_at) "
    "VALUES ('sqlite-test', %s, %s, now())"
)


def _check(database: PgTestDatabase) -> None:
    """Run the check as the migrator against ``database``."""
    with psycopg.connect(database.conninfo(PgRole.MIGRATOR)) as conn:
        check_live(conn, database=database.dbname, migrations_dir=MIGRATIONS_DIR, issuer=ISSUER)


def test_empty_database_fails_on_missing_schema(pg_template: PgTestDatabase) -> None:
    """An unmigrated database is a named schema failure, not a traceback."""
    settings = pg_template.settings
    name = mint_name(settings)
    create_test_database(settings, name)
    try:
        with pytest.raises(LiveCheckError, match=r"^schema: .*schema_migrations"):
            _check(pg_template.model_copy(update={"dbname": name}))
    finally:
        drop_test_database(settings, name)


def test_migrated_database_needs_setting_and_open_store(pg_db: PgTestDatabase) -> None:
    """Migrations alone are not a live store: the setting, then an OPEN legacy store, are required;
    a store whose latest event is not OPEN fails again."""
    with pytest.raises(LiveCheckError, match=r"^fiscal setting: APARINDS"):
        _check(pg_db)
    with pg_db.migrator_connection() as migrator:
        seed_issuer_identity(migrator, ISSUER)
    with pytest.raises(LiveCheckError, match=r"^legacy store: .*\[\]"):
        _check(pg_db)
    with pg_db.migrator_connection() as migrator:
        migrator.execute(_STORE)
        migrator.execute(_EVENT, (uuid.uuid4(), "OPEN"))
    _check(pg_db)
    with pg_db.migrator_connection() as migrator:
        migrator.execute(_EVENT, (uuid.uuid4(), "CUTOVER_FROZEN"))
    with pytest.raises(LiveCheckError, match=r"^legacy store: .*CUTOVER_FROZEN"):
        _check(pg_db)


def test_cli_refuses_a_test_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], pg_db: PgTestDatabase
) -> None:
    """The CLI never treats an ``eqos_test_*`` database as the live one."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    assert main(["db", "check-live"]) != 0
    assert f"database: {pg_db.dbname} is a test database" in capsys.readouterr().err
