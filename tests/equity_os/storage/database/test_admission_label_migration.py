"""VENDOR-1 Task 1: migration 0047 labels admissions, holds both vendor witnesses and pins the
vendor-first versions, without touching an admission written before it (spec §6.5, §6.9)."""

from __future__ import annotations

import shutil
from pathlib import Path

import psycopg
import pytest
from pg_evidence_schema_support import (
    _capture,
    _insert,
    _interpretation,
    _occurrence,
    _read,
    _seed_every_table,
    _seed_legacy_store,
    runtime,
    seeded,
)
from pg_support import MIGRATIONS_DIR, PgTestDatabase, create_database, drop_database, mint_name

from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.storage.database.migrations import apply_migrations
from equity_os.storage.database.settings import PgRole

pytestmark = pytest.mark.pg
__all__ = ["runtime", "seeded"]

MIGRATION = "0047_admission_label.sql"
ROW_CAPTURES_SOURCE = "0028_retention_protocol.sql"


def test_an_admission_written_before_0047_reads_checked_against_filing(
    pg_template: PgTestDatabase, tmp_path: Path
) -> None:
    """Every pre-0047 admission is a first-party filed value: the migration labels it so without
    an UPDATE, and its other columns keep their content."""
    db = pg_template.model_copy(update={"dbname": mint_name(pg_template.settings)})
    create_database(db.settings, db.dbname)
    try:
        for path in MIGRATIONS_DIR.glob("*.sql"):
            if path.name < "0046":
                shutil.copy(path, tmp_path)
        with db.migrator_connection() as migrator:
            apply_migrations(migrator, tmp_path)
            # 0047 re-creates row_captures from 0028's text; no later migration may have changed it.
            installed = migrator.execute(
                "SELECT prosrc FROM pg_proc WHERE proname = 'row_captures'"
            ).fetchone()
        assert installed is not None
        assert installed[0] in (MIGRATIONS_DIR / ROW_CAPTURES_SOURCE).read_text(encoding="utf-8")
        with psycopg.connect(db.conninfo(PgRole.RUNTIME), autocommit=True) as conn:
            ids = _seed_every_table(conn)
            _seed_legacy_store(conn, ids, labelled=False)
            before = _read(conn, "fact_admissions", ids["fact_admissions"])
        shutil.copy(MIGRATIONS_DIR / MIGRATION, tmp_path)
        with db.migrator_connection() as migrator:
            assert [m.filename for m in apply_migrations(migrator, tmp_path)] == [MIGRATION]
        with psycopg.connect(db.conninfo(PgRole.RUNTIME), autocommit=True) as conn:
            after = _read(conn, "fact_admissions", ids["fact_admissions"])
        assert after == before | {
            "label": AdmissionLabel.CHECKED_AGAINST_FILING,
            "witness_interpretation_id": None,
            "eligibility_version": None,
        }
    finally:
        drop_database(db.settings, db.dbname)


def _vendor_interpretation(conn: psycopg.Connection, ids: dict[str, int], tag: str) -> int:
    """An interpretation on its own new capture, so its capture is reachable only through it."""
    capture = _insert(conn, "capture_refs", _capture(f"cap-{tag}") | {"request_key": tag})
    occurrence = _insert(conn, "occurrences", _occurrence(capture, f"f-{tag}"))
    return _insert(conn, "interpretations", _interpretation(ids["_entity"], capture, occurrence))


def test_vendor_first_columns_tables_and_pins(
    pg_db: PgTestDatabase, runtime: psycopg.Connection, seeded: dict[str, int]
) -> None:
    """An unchecked admission needs a witness and an eligibility version, the retention guard
    holds the witness's capture, counterexamples are append-only, and runs may pin the two new
    versions."""
    chosen = _vendor_interpretation(runtime, seeded, "chosen")
    witness = _vendor_interpretation(runtime, seeded, "witness")
    admission = {"store_id": "sqlite-seed", "row_handle": 1, "fact_origin": "sqlite-seed"} | {
        "fact_origin_id": 1,
        "run_id": seeded["runs"],
        "result_id": seeded["results"],
        "interpretation_id": chosen,
        "occurrence_id": seeded["occurrences"],
        "overlay_position": "2026-11-06T00:00:00Z",
        "bridge_version": "admission-bridge/2",
    }
    unchecked = {"label": AdmissionLabel.VENDORS_AGREE_NOT_CHECKED}
    with pytest.raises(psycopg.errors.NotNullViolation):
        _insert(runtime, "fact_admissions", admission)
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(runtime, "fact_admissions", admission | unchecked | {"eligibility_version": "v1"})
    row = _insert(
        runtime,
        "fact_admissions",
        admission | unchecked | {"witness_interpretation_id": witness, "eligibility_version": "v1"},
    )
    captures = runtime.execute(
        "SELECT eqos.row_captures('fact_admissions', to_jsonb(a)) FROM eqos.fact_admissions a "
        "WHERE id = %s",
        (row,),
    ).fetchone()
    capture_of = "SELECT capture_ref_id FROM eqos.interpretations WHERE id = %s"
    expected = {runtime.execute(capture_of, (i,)).fetchone()[0] for i in (chosen, witness)}
    assert captures is not None and expected <= set(captures[0])

    pin = {"run_id": seeded["runs"], "version": "v1", "content_sha256": "e" * 64}
    _insert(runtime, "run_versions", pin | {"pin": "eligibility"})
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(runtime, "run_versions", pin | {"pin": "unknown_pin"})

    counterexample = _insert(
        runtime,
        "vendor_counterexamples",
        {"class_digest": "d" * 64, "result_id": seeded["results"], "run_id": seeded["runs"]},
    )
    with pg_db.migrator_connection() as migrator, pytest.raises(psycopg.errors.RaiseException):
        migrator.execute(
            "UPDATE eqos.vendor_counterexamples SET run_id = run_id WHERE id = %s",
            (counterexample,),
        )
