"""Vendor values remain attached to registered originals and commit atomically."""

from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from pg_support import PgTestDatabase, drop_database, mint_name
from retention_support import record_of, restore_args

from fundamentals.ingest.vendor_surface_fetch import Fetched
from fundamentals.pg.backup import restore_backup, write_backup
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg


def setup_store(pg_db, tmp_path):
    from fundamentals.store.vendor_values_store import VendorValuesStore, register

    store = SnapshotStore(tmp_path / "store")
    record = record_of(b"fixture", "tijori", "vs.chart-api")
    store.put_capture(record, b"fixture")
    pool = pg_db.runtime_pool()
    ref = register(
        pool, Fetched(record=record, url="https://www.tijorifinance.com/chart/", location=None)
    )
    return store, pool, ref, VendorValuesStore(pool)


def outcome(version="tijori:chart-api.v1", digest="a" * 64, **changes):
    from fundamentals.store.vendor_values_store import Outcome, OutcomeStatus, VendorValue

    value = VendorValue(
        table_key="price",
        row_index=0,
        column_index=0,
        locator="/0",
        row_label="date",
        column_label="price",
        raw_text="12.5",
        value=Decimal("12.5"),
        link="https://example.com/document",
    )
    return Outcome(
        surface="chart-api",
        parser_version=version,
        parser_sha256=digest,
        status=OutcomeStatus.OK,
        symbol="APARINDS",
        detail=None,
        values=(value, value.model_copy(update={"row_index": 1})),
    ).model_copy(update=changes)


def test_atomic_registration_pinning_and_capture_fk(pg_db, tmp_path):
    from fundamentals.store.vendor_values_store import ParserVersionDrift

    _, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        with pytest.raises(psycopg.errors.UniqueViolation):
            values.record(ref, outcome(values=(outcome().values[0],) * 2), row_count=2)
        assert not values.has_outcome(ref.capture_ref_id, "chart-api", "tijori:chart-api.v1")
        identifier = values.record(ref, outcome(), row_count=2)
        assert values.has_outcome(ref.capture_ref_id, "chart-api", "tijori:chart-api.v1")
        with pytest.raises(ParserVersionDrift):
            values.record(ref, outcome(digest="b" * 64), row_count=2)
        values.record(ref, outcome(version="screener:company-search-api.reader.v1"), row_count=2)
        values.record(ref, outcome(version="tijori:company-search-api.reader.v1"), row_count=2)
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT url FROM eqos.capture_addresses WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone() == ("https://www.tijorifinance.com/chart/",)
            other = record_of(b"other", "tijori", "vs.chart-api")
            from fundamentals.store.vendor_values_store import register

            second = register(
                pool,
                Fetched(record=other, url="https://www.tijorifinance.com/other/", location=None),
            )
            with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
                conn.execute(
                    "INSERT INTO eqos.vendor_values "
                    "(outcome_id,capture_ref_id,table_key,row_index,column_index,locator) "
                    "VALUES (%s,%s,'x',0,0,'/0')",
                    (identifier, second.capture_ref_id),
                )
        with pytest.raises(RuntimeError), pool.connection() as conn, conn.transaction():
            values.record(ref, outcome(version="tijori:chart-api.v3"), row_count=2, conn=conn)
            raise RuntimeError("caller rolls back")
        assert not values.has_outcome(ref.capture_ref_id, "chart-api", "tijori:chart-api.v3")
        with pytest.raises(ValueError, match="row_count"):
            values.record(ref, outcome(), row_count=1)


def test_licence_end_and_immutable_tables(pg_db, tmp_path):
    _, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        values.record(ref, outcome(), row_count=2)
        with pg_db.migrator_connection() as conn:
            for table in ("vendor_parser_versions", "vendor_outcomes", "vendor_values"):
                for statement in (
                    f"UPDATE eqos.{table} SET "
                    + (
                        "parser_version=parser_version"
                        if table == "vendor_parser_versions"
                        else "capture_ref_id=capture_ref_id"
                    ),
                    f"DELETE FROM eqos.{table}",
                    f"TRUNCATE eqos.{table} CASCADE",
                ):
                    with pytest.raises(psycopg.Error), conn.transaction():
                        conn.execute(statement)
        with pg_db.owner_pool() as owners, owners.connection() as owner:
            owner.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('tijori')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="BEYOND_AUTHORITY"):
            values.record(ref, outcome(version="tijori:chart-api.v2"), row_count=2)


def test_tombstone_clears_content_keeps_positions(pg_db, tmp_path):
    _, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        values.record(ref, outcome(), row_count=2)
        with pg_db.role_pool(PgRole.PURGE) as purges, purges.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.capture_states (capture_ref_id,state) "
                "VALUES (%s,'PURGE_PENDING')",
                (ref.capture_ref_id,),
            )
            conn.execute("SELECT eqos.tombstone_vendor_capture(%s)", (ref.capture_ref_id,))
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT row_index, column_index, value, raw_text, row_label, column_label, link "
                "FROM eqos.vendor_values ORDER BY row_index"
            ).fetchall() == [
                (0, 0, None, None, None, None, None),
                (1, 0, None, None, None, None, None),
            ]


def test_capture_and_values_backup_restore(pg_db: PgTestDatabase, tmp_path: Path):
    store, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        values.record(ref, outcome(), row_count=2)
    # Use installed native clients; this test never invokes Docker.
    saved = write_backup(
        pg_db.settings,
        database=pg_db.dbname,
        snapshot_root=tmp_path / "store",
        out_dir=tmp_path / "sets",
        client_prefix=(),
    )
    target = mint_name(pg_db.settings)
    restored_root = tmp_path / "restored"
    try:
        check = restore_backup(
            saved,
            pg_db.settings,
            database=target,
            snapshot_root=restored_root,
            client_prefix=(),
            replay_runs=False,
            config_root=Path("config"),
            **restore_args(pg_db, saved, restored_root, live=None),
        )
        assert check.ok
        restored = pg_db.model_copy(update={"dbname": target})
        with restored.runtime_pool() as pool, pool.connection() as conn:
            assert conn.execute(
                "SELECT count(*) FROM eqos.vendor_values WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone() == (2,)
        record = SnapshotStore(restored_root).get_capture(
            ref.source_id, ref.surface, ref.request_key, ref.capture_id
        )
        assert SnapshotStore(restored_root).read_body(record) == b"fixture"
    finally:
        drop_database(pg_db.settings, target)
