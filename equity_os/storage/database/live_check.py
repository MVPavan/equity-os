"""Read-only live-state preflight for ``EQOS_PG_DB`` (bead eqos-px2, incident eqos-89z).

The test gate runs on isolated ``eqos_test_*`` databases, so it stays green while the live
database is empty. This check reads the live one: it is the configured database, every migration
is recorded with its on-disk sha256, the issuer's fiscal-year end is seeded, and every imported
legacy fact store is ``OPEN``. Reports are not required.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from equity_os.companies.identity.identity_seed import IssuerIdentityInput, SettingKey
from equity_os.storage.database.migrations import migration_checksums

OPEN_STATE = "OPEN"
_CURRENT_DB = "SELECT current_database()"
_RECORDED = "SELECT filename, sha256 FROM eqos_meta.schema_migrations"
_FISCAL = (
    "SELECT s.value_text FROM eqos.settings_records s "
    "JOIN eqos.reporting_entities e ON e.id = s.entity_id "
    "WHERE e.entity_key = %s AND s.setting_key = %s"
)
_LEGACY_STATES = (
    "SELECT f.store_id, (SELECT v.state FROM eqos.fact_store_events v "
    "WHERE v.store_id = f.store_id ORDER BY v.id DESC LIMIT 1) "
    "FROM eqos.fact_stores f WHERE f.kind = 'LEGACY_SQLITE' ORDER BY 1"
)


class LiveCheckError(RuntimeError):
    """A live-state check failed; the message starts with the check's name."""


def check_live(
    conn: psycopg.Connection, *, database: str, migrations_dir: Path, issuer: IssuerIdentityInput
) -> None:
    """Pass silently, or raise ``LiveCheckError`` naming the first failed check."""
    conn.read_only = True
    try:
        row = conn.execute(_CURRENT_DB).fetchone()
        if row is None or row[0] != database:
            raise LiveCheckError(f"database: connected to {row}, expected {database}")
        recorded = {str(name): str(sha) for name, sha in conn.execute(_RECORDED).fetchall()}
        drift = sorted(dict(recorded.items() ^ migration_checksums(migrations_dir).items()))
        if drift:
            raise LiveCheckError(f"migrations: missing, extra or changed: {', '.join(drift)}")
        months = conn.execute(_FISCAL, (issuer.entity_key, SettingKey.FISCAL_YEAR_END_MONTH))
        if (str(issuer.fiscal_year_end_month),) not in months.fetchall():
            raise LiveCheckError(
                f"fiscal setting: {issuer.entity_key} has no "
                f"{SettingKey.FISCAL_YEAR_END_MONTH}={issuer.fiscal_year_end_month}"
            )
        states = conn.execute(_LEGACY_STATES).fetchall()
        if not states or any(state != OPEN_STATE for _, state in states):
            raise LiveCheckError(f"legacy store: expected every store {OPEN_STATE}, got {states}")
    except psycopg.errors.UndefinedTable as missing:
        raise LiveCheckError(f"schema: {missing.diag.message_primary}") from missing
    finally:
        conn.rollback()
