"""Vendor values remain attached to registered originals and commit atomically."""

from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from pg_evidence_schema_support import _insert
from pg_support import PgTestDatabase, drop_database, mint_name
from retention_support import record_of, restore_args

from fundamentals.ingest.vendor_surface_fetch import Fetched
from fundamentals.pg.backup import restore_backup, write_backup
from fundamentals.pg.restore_check import table_rows
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
        pool,
        Fetched(record=record, url="https://www.tijorifinance.com/chart/", location="/%6cogin/"),
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
        unit="PRIVATE_UNIT_SENTINEL",
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


# Each table's no-op UPDATE, which only the tombstone's inventory columns may escape.
TABLES = {
    "vendor_parser_versions": "parser_version=parser_version",
    "vendor_outcomes": "capture_ref_id=capture_ref_id",
    "vendor_values": "capture_ref_id=capture_ref_id",
    "vendor_basis_bindings": "capture_ref_id=capture_ref_id",
    "vendor_label_proposals": "source_id=source_id",
    "vendor_text_claims": "capture_ref_id=capture_ref_id",
}
PROPOSAL = (
    "INSERT INTO eqos.vendor_label_proposals (source_id,surface,label,units,reason,model_id,"
    "prompt_version,dictionary_version,prompt,raw_response) VALUES "
    "('tijori','chart-api','Sales','{PRIVATE_UNIT_SENTINEL}','MODEL_UNMAPPED','m','v1','v3','p','r')"
)
CLAIM = (
    "INSERT INTO eqos.vendor_text_claims (capture_ref_id,surface,kind,span_start,span_end,text,"
    "model_id,prompt_version,epistemic_class) VALUES (%s,'chart-api','NAME',0,4,'Acme','m','v1',"
    "'inferred')"
)


def test_licence_end_and_immutable_tables(pg_db, tmp_path):
    _, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        values.record(ref, outcome(), row_count=2)
        with pool.connection() as conn:
            evidence = _insert(
                conn,
                "evidence_inputs",
                {"kind": "ISSUER_IDENTITY", "label": "fixture", "content_sha256": "d" * 64},
            )
            entity = _insert(
                conn,
                "reporting_entities",
                {
                    "entity_key": "FIXTURE",
                    "market": "IN",
                    "display_name": "Fixture",
                    "evidence_input_id": evidence,
                },
            )
            conn.execute(
                "INSERT INTO eqos.vendor_basis_bindings "
                "(entity_id,basis,screener_company_id,warehouse_id,capture_ref_id,evidence) "
                "VALUES (%s,'STANDALONE',1,2,%s,'FIRST_CAPTURE')",
                (entity, ref.capture_ref_id),
            )
            conn.execute(PROPOSAL)
            conn.execute(CLAIM, (ref.capture_ref_id,))
            for role in ("eqos_runtime", "eqos_panel", "eqos_owner", "eqos_purge"):
                for table in TABLES:
                    assert conn.execute(
                        "SELECT has_table_privilege(%s,%s,'SELECT'), "
                        "has_table_privilege(%s,%s,'INSERT'), "
                        "has_table_privilege(%s,%s,'UPDATE,DELETE,TRUNCATE')",
                        (role, "eqos." + table) * 3,
                    ).fetchone() == (True, role == "eqos_runtime", False)
            # Only the complete wrapper tombstones; its cell-only helper is not callable.
            assert conn.execute(
                "SELECT has_function_privilege('eqos_purge',"
                "'eqos.tombstone_vendor_capture(bigint)','EXECUTE'), "
                "has_function_privilege('eqos_purge',"
                "'eqos.tombstone_vendor_capture_cells(bigint)','EXECUTE')"
            ).fetchone() == (True, False)

        with pg_db.migrator_connection() as conn:
            for table, noop in TABLES.items():
                for statement in (
                    f"UPDATE eqos.{table} SET {noop}",
                    f"DELETE FROM eqos.{table}",
                    f"TRUNCATE eqos.{table} CASCADE",
                ):
                    with pytest.raises(psycopg.Error), conn.transaction():
                        conn.execute(statement)
            # Inside a tombstone only the redaction inventory may change.
            for statement in (
                "UPDATE eqos.vendor_label_proposals SET label=NULL, reason='MALFORMED_REPLY'",
                "UPDATE eqos.vendor_text_claims SET text=NULL, span_end=5",
            ):
                with pytest.raises(psycopg.Error), conn.transaction():
                    conn.execute("SELECT set_config('eqos.tombstone','fixture',true)")
                    conn.execute(statement)
        with pool.connection() as conn:
            before = table_rows(conn, ["vendor_label_proposals"])["vendor_label_proposals"]
        with pg_db.owner_pool() as owners, owners.connection() as owner:
            owner.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('tijori')")
        with pool.connection() as conn:
            after = table_rows(conn, ["vendor_label_proposals"])["vendor_label_proposals"]
            assert after == {
                key: row | {"label": None, "prompt": None, "raw_response": None, "units": None}
                for key, row in before.items()
            }
            for statement, params in ((PROPOSAL, ()), (CLAIM, (ref.capture_ref_id,))):
                with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                    conn.execute(statement, params)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="BEYOND_AUTHORITY"):
            values.record(ref, outcome(version="tijori:chart-api.v2"), row_count=2)


def test_tombstone_clears_content_keeps_positions(pg_db, tmp_path):
    _, pool, ref, values = setup_store(pg_db, tmp_path)
    with pool:
        values.record(ref, outcome(), row_count=2)
        with pool.connection() as conn:
            conn.execute(CLAIM, (ref.capture_ref_id,))
            before = table_rows(conn, ["vendor_values"])["vendor_values"]
        with pg_db.role_pool(PgRole.PURGE) as purges, purges.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.capture_states (capture_ref_id,state) "
                "VALUES (%s,'PURGE_PENDING')",
                (ref.capture_ref_id,),
            )
            conn.execute("SELECT eqos.tombstone_vendor_capture(%s)", (ref.capture_ref_id,))
        with pool.connection() as conn:
            assert table_rows(conn, ["vendor_values"])["vendor_values"].keys() == before.keys()
            assert conn.execute(
                "SELECT row_index, column_index, value, raw_text, row_label, column_label, link, unit "
                "FROM eqos.vendor_values ORDER BY row_index"
            ).fetchall() == [
                (0, 0, None, None, None, None, None, None),
                (1, 0, None, None, None, None, None, None),
            ]
            assert conn.execute(
                "SELECT kind,span_start,span_end,text FROM eqos.vendor_text_claims"
            ).fetchall() == [("NAME", 0, 4, None)]


def test_capture_and_values_backup_restore(pg_db: PgTestDatabase, tmp_path: Path):
    from fundamentals.api.cli_parser import build_parser
    from fundamentals.store.vendor_values_store import register

    for command in ("capture", "reparse"):
        args = build_parser().parse_args(
            ["vendor", command, "--surface", "screener:chart-api"]
            + (["--symbol", "APARINDS"] if command == "capture" else [])
        )
        assert args.snapshot_root == Path("data/raw/snapshots/v1")
    store, pool, ref, values = setup_store(pg_db, tmp_path)
    existing = record_of(b"exchange", "nse", "EQUITY_L")
    store.put_capture(existing, b"exchange")
    with pool:
        register(pool, Fetched(record=existing, url="https://nse.example/", location=None))
        values.record(ref, outcome(), row_count=2)
    # Reopen the registration independently before archiving it.
    with pg_db.runtime_pool() as reopened, reopened.connection() as conn:
        assert conn.execute(
            "SELECT location FROM eqos.capture_addresses WHERE capture_ref_id=%s",
            (ref.capture_ref_id,),
        ).fetchone() == ("/%6cogin/",)
    saved = write_backup(
        pg_db.settings,
        database=pg_db.dbname,
        snapshot_root=tmp_path / "store",
        out_dir=tmp_path / "sets",
    )
    target = mint_name(pg_db.settings)
    restored_root = tmp_path / "restored"
    try:
        check = restore_backup(
            saved,
            pg_db.settings,
            database=target,
            snapshot_root=restored_root,
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
            assert conn.execute(
                "SELECT location FROM eqos.capture_addresses WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone() == ("/%6cogin/",)
        assert SnapshotStore(restored_root).read_body(existing) == b"exchange"
        record = SnapshotStore(restored_root).get_capture(
            ref.source_id, ref.surface, ref.request_key, ref.capture_id
        )
        assert SnapshotStore(restored_root).read_body(record) == b"fixture"
    finally:
        drop_database(pg_db.settings, target)


@pytest.mark.parametrize("session_error", [False, True])
def test_parser_error_detail_survives_licence_end_without_content(
    pg_db, tmp_path, monkeypatch, session_error
):
    from fundamentals.ingest.screener_session_models import ScreenerSessionError
    from fundamentals.ingest.vendor_surface_capture import Request, parse_and_record
    from fundamentals.ingest.vendor_surface_fetch import Site
    from fundamentals.ingest.vendor_surface_parse import PARSERS, ParserEntry
    from fundamentals.ingest.vendor_surface_specs import load_specs
    from fundamentals.store.vendor_values_store import register

    store, pool, _, values = setup_store(pg_db, tmp_path)
    raw = b'{"datasets":[{"label":["vendor-private-text"],"values":[["date",1]]}]}'
    record = record_of(raw, "tijori", "vs.chart-api")
    store.put_capture(record, raw)
    spec = load_specs(
        Path("config/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )[1]
    if session_error:

        def rejected(body, context):
            raise ScreenerSessionError(body.raw.decode())

        monkeypatch.setitem(
            PARSERS,
            (Site.SCREENER, "chart-api"),
            ParserEntry(version="screener:malformed.v1", parse=rejected),
        )
    with pool:
        ref = register(
            pool,
            Fetched(
                record=record, url="https://www.tijorifinance.com/chart/?q=price", location=None
            ),
        )
        parse_and_record(
            store,
            values,
            ref,
            record,
            Request(
                spec=spec,
                url="https://www.tijorifinance.com/chart/?q=price",
                ids=None,
                due_since=None,
            ),
        )
        with pg_db.owner_pool() as owners, owners.connection() as owner:
            owner.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('tijori')")
        with pg_db.role_pool(PgRole.PURGE) as purges, purges.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.capture_states (capture_ref_id,state) "
                "VALUES (%s,'PURGE_PENDING')",
                (ref.capture_ref_id,),
            )
            conn.execute("SELECT eqos.tombstone_vendor_capture(%s)", (ref.capture_ref_id,))
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT detail FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone() == (("ScreenerSessionError" if session_error else "ValueError"),)
