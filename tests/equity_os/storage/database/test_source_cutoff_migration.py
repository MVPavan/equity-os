"""VENDOR-1 Phase 2 Task 4: migration 0051 adds the source cutoff without touching a sealed
digest recorded before it; those versions carry no cutoff and their digests still verify."""

from __future__ import annotations

import shutil
from contextlib import ExitStack
from pathlib import Path

import psycopg
import pytest
from ledger_support import Ledger
from pg_evidence_schema_support import _seed_every_table
from pg_support import MIGRATIONS_DIR, PgTestDatabase, create_database, drop_database, mint_name

from equity_os.contracts.publication.ledger import DecisionKind
from equity_os.storage.database.migrations import apply_migrations
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store

pytestmark = pytest.mark.pg

MIGRATION = "0051_version_source_cutoff.sql"
# Every version decision's recorded digest beside the one the database computes now.
DIGESTS = (
    "SELECT id, subject_id, sealed_digest, eqos.version_sealed_digest(subject_id) "
    "FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION' AND sealed_digest IS NOT NULL "
    "ORDER BY id"
)
# The pre-0051 producer wrote no cutoff row; its parameters stay bound.
NO_CUTOFF_ROW = "SELECT %(version)s, %(cutoff)s::timestamptz, %(predecessor)s"


def test_sealed_digests_recorded_before_0051_still_verify(
    pg_template: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = pg_template.model_copy(update={"dbname": mint_name(pg_template.settings)})
    create_database(db.settings, db.dbname)
    try:
        for path in MIGRATIONS_DIR.glob("*.sql"):
            if path.name < MIGRATION:
                shutil.copy(path, tmp_path)
        with db.migrator_connection() as migrator:
            apply_migrations(migrator, tmp_path)
        with psycopg.connect(db.conninfo(PgRole.RUNTIME), autocommit=True) as conn:
            ids = _seed_every_table(conn)
        with ExitStack() as stack:
            pools = {
                role: stack.enter_context(db.role_pool(role))
                for role in (PgRole.RUNTIME, PgRole.PANEL, PgRole.OWNER)
            }
            with monkeypatch.context() as patch:
                patch.setattr(store, "_SOURCE_CUTOFF", NO_CUTOFF_ROW)
                ledger = Ledger(pools, ids, SnapshotStore(tmp_path / "snapshots"))
                sealed = ledger.imported(ledger.report(), approve=True)
                submitted = ledger.draft(ledger.report())
                ledger.submit(submitted)
            with pools[PgRole.RUNTIME].connection() as conn:
                before = conn.execute(DIGESTS).fetchall()
            assert {row[1] for row in before} >= {sealed, submitted}
            assert all(row[2] == row[3] for row in before)
            shutil.copy(MIGRATIONS_DIR / MIGRATION, tmp_path)
            with db.migrator_connection() as migrator:
                assert [m.filename for m in apply_migrations(migrator, tmp_path)] == [MIGRATION]
            with pools[PgRole.RUNTIME].connection() as conn, conn.cursor() as cursor:
                assert cursor.execute(DIGESTS).fetchall() == before
                held = [store.read_version(cursor, v).source_cutoff for v in (sealed, submitted)]
            assert held == [None, None]
            # The database re-verifies the pre-0051 digest when the approval names it.
            assert ledger.approve(submitted).kind is DecisionKind.APPROVE
    finally:
        drop_database(db.settings, db.dbname)
