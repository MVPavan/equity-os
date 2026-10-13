"""Real retained witness SQL boundaries, transaction rollback and concurrency.

These are post-implementation acceptance cases, not historical RED evidence. Positive
payloads come from the real retained producer immediately before its seal boundary.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from pg_support import PgTestDatabase
from psycopg import sql
from psycopg.types.json import Jsonb
from test_compare_vendor_handoffs import _pdf_only_with_failed_xbrl
from test_retained_intake_witness_source import _append_witness

from fundamentals.evidence import retained_intake_store as store_module
from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff
from fundamentals.evidence.first_party_ingest import IngestReport
from fundamentals.evidence.retained_intake_models import (
    PreparedRetainedIntakeWitness,
    RetainedIntakeWitness,
    RetainedIntakeWitnessError,
    RetainedIntakeWitnessPayload,
)
from fundamentals.evidence.retained_intake_store import RetainedIntakeWitnessStore

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]

TABLES = (
    "retained_intake_witnesses",
    "retained_intake_witness_bindings",
    "retained_intake_witness_attempts",
    "retained_intake_witness_captures",
    "retained_intake_witness_pins",
    "retained_intake_witness_seals",
)


class StopBeforeSealError(RuntimeError):
    """Test interception after real ingest, before any witness mutation."""


@dataclass(frozen=True)
class PendingSeal:
    store: RetainedIntakeWitnessStore
    prepared: PreparedRetainedIntakeWitness
    handoff: FirstPartyGenerationHandoff
    report: IngestReport

    def seal(self) -> RetainedIntakeWitness:
        return self.store.seal(self.prepared, handoff=self.handoff, report=self.report)

    def payload(self) -> RetainedIntakeWitnessPayload:
        return self.store._payload(self.prepared, self.handoff, self.report)


@pytest.fixture
def pending(ingest: Ingest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PendingSeal:
    root, config, _ = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    captured: list[PendingSeal] = []

    def stop(
        self: RetainedIntakeWitnessStore,
        prepared: PreparedRetainedIntakeWitness,
        *,
        handoff: FirstPartyGenerationHandoff,
        report: IngestReport,
    ) -> None:
        captured.append(
            PendingSeal(RetainedIntakeWitnessStore(ingest.repository), prepared, handoff, report)
        )
        raise StopBeforeSealError("real producer reached witness sealing")

    with monkeypatch.context() as patch:
        patch.setattr(RetainedIntakeWitnessStore, "seal", stop)
        with pytest.raises(StopBeforeSealError, match="reached witness sealing"):
            _append_witness(ingest, root, config)
    assert len(captured) == 1
    counts = ingest.table_counts()
    assert all(counts[table] == 0 for table in TABLES)
    return captured[0]


def _write_unsealed(
    conn: psycopg.Connection[Any], payload: RetainedIntakeWitnessPayload, fault: str = ""
) -> int:
    """Write the actual prepared projection directly at the SQL contract seam."""
    content_hash = "0" * 64 if fault == "content_hash" else payload.content_sha256
    evidence_id = conn.execute(
        "INSERT INTO eqos.evidence_inputs(kind,label,content_sha256) "
        "VALUES ('RETAINED_INTAKE',%s,%s) RETURNING id",
        (payload.label, content_hash),
    ).fetchone()[0]
    header_values = list(store_module._header_values(payload))
    header_values[-1] = content_hash
    witness_id = conn.execute(
        store_module._INSERT_HEADER, (evidence_id, *header_values)
    ).fetchone()[0]
    bindings = {
        request.representation: conn.execute(
            store_module._INSERT_BINDING,
            (witness_id, *store_module._binding_values(request)),
        ).fetchone()[0]
        for request in payload.prepared.requests
    }
    for association in payload.associations:
        binding_id = bindings[association.representation]
        for attempt_id in association.attempt_ids:
            if fault == "missing_attempt" and attempt_id == payload.attempts[-1].attempt_id:
                continue
            linked_binding = binding_id
            if fault == "wrong_binding":
                linked_binding = next(value for value in bindings.values() if value != binding_id)
            linked_attempt = 9223372036854775807 if fault == "dangling_attempt" else attempt_id
            conn.execute(
                "INSERT INTO eqos.retained_intake_witness_attempts "
                "(witness_id,binding_id,attempt_id) "
                "VALUES (%s,%s,%s)",
                (witness_id, linked_binding, linked_attempt),
            )
        for disposition, ids in (
            ("PACKAGE_MEMBER", association.package_capture_ids),
            ("FAILED_PEER", association.failed_capture_ids),
        ):
            for capture_id in ids:
                held_disposition = disposition
                if fault == "capture_disposition":
                    held_disposition = (
                        "FAILED_PEER" if disposition == "PACKAGE_MEMBER" else "PACKAGE_MEMBER"
                    )
                conn.execute(
                    "INSERT INTO eqos.retained_intake_witness_captures "
                    "(witness_id,binding_id,capture_ref_id,disposition) VALUES (%s,%s,%s,%s)",
                    (witness_id, binding_id, capture_id, held_disposition),
                )
    for pin in payload.pins:
        pin_id = payload.pins[-1].id if fault == "pin_identity" else pin.id
        conn.execute(
            "INSERT INTO eqos.retained_intake_witness_pins(witness_id,artifact,version_pin_id) "
            "VALUES (%s,%s,%s)",
            (witness_id, pin.artifact, pin_id),
        )
    return witness_id


def _seal_sql(
    conn: psycopg.Connection[Any],
    witness_id: int,
    payload: RetainedIntakeWitnessPayload,
    fault: str = "",
) -> None:
    closure = "0" * 64 if fault == "closure" else payload.closure_sha256
    # Keep the wrong count within its SQL range so the closure comparison must reject it.
    binding_count = len(payload.prepared.requests) - (fault == "count")
    values = (
        witness_id,
        closure,
        binding_count,
        len(payload.attempts),
        len(payload.captures),
        len(payload.pins),
    )
    if fault == "seal_clock":
        conn.execute(
            "INSERT INTO eqos.retained_intake_witness_seals "
            "(witness_id,closure_sha256,binding_count,attempt_count,capture_count,"
            "pin_count,sealed_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,eqos.store_now()-interval '1 second')",
            values,
        )
    else:
        conn.execute(
            "INSERT INTO eqos.retained_intake_witness_seals "
            "(witness_id,closure_sha256,binding_count,attempt_count,capture_count,pin_count) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            values,
        )


def _duplicate_statement(conn: psycopg.Connection[Any], table: str) -> sql.Composed:
    columns = [
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='eqos' AND table_name=%s AND column_name<>'id' "
            "ORDER BY ordinal_position",
            (table,),
        ).fetchall()
    ]
    target = sql.Identifier("eqos", table)
    names = sql.SQL(",").join(sql.Identifier(column) for column in columns)
    return sql.SQL("INSERT INTO {}({}) SELECT {} FROM {} LIMIT 1").format(
        target, names, names, target
    )


def test_real_store_seal_and_exact_reuse_preserve_every_id_and_store_clock(
    ingest: Ingest, pending: PendingSeal
) -> None:
    first = pending.seal()
    before = ingest.table_counts()
    again = pending.seal()
    (reloaded,) = pending.store.get_by_evidence_ids([first.evidence_input_id])
    assert first == again == reloaded
    assert first.recorded_at == first.sealed_at
    assert ingest.table_counts() == before
    assert before["retained_intake_witnesses"] == 1
    assert before["retained_intake_witness_bindings"] == 2
    assert before["retained_intake_witness_seals"] == 1
    associations = {row.representation.value: row for row in first.payload.associations}
    assert associations["PDF"].package_capture_ids
    assert not associations["PDF"].failed_capture_ids
    assert associations["XBRL"].failed_capture_ids
    assert not associations["XBRL"].package_capture_ids


@pytest.mark.parametrize(
    ("fault", "sqlstate"),
    [
        ("dangling_attempt", "23503"),
        ("wrong_binding", "23514"),
        ("missing_attempt", "23514"),
        ("capture_disposition", "23514"),
        ("pin_identity", "23514"),
        ("content_hash", "23514"),
        ("closure", "23514"),
        ("count", "23514"),
        ("seal_clock", "23514"),
        ("attempt_payload", "23514"),
        ("attempt_clock", "23514"),
        ("capture_payload", "23514"),
        ("pin_clock", "23514"),
        ("settings_identity", "23514"),
        ("package_identity", "23514"),
    ],
)
def test_direct_sql_rejects_forged_typed_closure_without_witness_mutation(
    ingest: Ingest, pending: PendingSeal, fault: str, sqlstate: str
) -> None:
    payload = pending.payload()
    if fault in {"attempt_payload", "attempt_clock"}:
        original = payload.attempts[0]
        updates = (
            {"reason": "declared negative test: unrelated stored reason"}
            if fault == "attempt_payload"
            else {"attempted_at": original.attempted_at - timedelta(seconds=1)}
        )
        payload = payload.model_copy(
            update={"attempts": (original.model_copy(update=updates), *payload.attempts[1:])}
        )
    elif fault == "capture_payload":
        original = payload.captures[0]
        payload = payload.model_copy(
            update={
                "captures": (
                    original.model_copy(update={"record_sha256": "0" * 64}),
                    *payload.captures[1:],
                )
            }
        )
    elif fault == "pin_clock":
        original = payload.pins[0]
        payload = payload.model_copy(
            update={
                "pins": (
                    original.model_copy(
                        update={"pinned_at": original.pinned_at - timedelta(seconds=1)}
                    ),
                    *payload.pins[1:],
                )
            }
        )
    elif fault == "settings_identity":
        generation = json.loads(payload.generation_json)
        generation["qualification_context_sha256"] = "0" * 64
        payload = payload.model_copy(
            update={
                "qualification_context_sha256": "0" * 64,
                "generation_json": json.dumps(generation, sort_keys=True, separators=(",", ":")),
            }
        )
    elif fault == "package_identity":
        generation = json.loads(payload.generation_json)
        generation["package_evidence_sha256"] = "0" * 64
        payload = payload.model_copy(
            update={
                "package_evidence_sha256": "0" * 64,
                "generation_json": json.dumps(generation, sort_keys=True, separators=(",", ":")),
            }
        )
    before = ingest.table_counts()
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.Error) as failure:
            with conn.transaction():
                witness_id = _write_unsealed(conn, payload, fault)
                _seal_sql(conn, witness_id, payload, fault)
    assert failure.value.sqlstate == sqlstate
    assert ingest.table_counts() == before


@pytest.mark.parametrize("table", TABLES)
def test_direct_runtime_append_to_each_sealed_table_refuses_before_unique_collision(
    ingest: Ingest, pending: PendingSeal, table: str
) -> None:
    pending.seal()
    before = ingest.table_counts()
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        statement = _duplicate_statement(conn, table)
        with pytest.raises(psycopg.errors.CheckViolation, match="already sealed"):
            with conn.transaction():
                conn.execute(statement)
    assert ingest.table_counts() == before


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
@pytest.mark.parametrize("table", (*TABLES, "evidence_inputs"))
def test_isolation_refusal_precedes_dangling_lookup_or_missing_columns(
    pg_db: PgTestDatabase, isolation: str, table: str
) -> None:
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.Error) as failure:
            with conn.transaction():
                conn.execute(
                    sql.SQL("SET TRANSACTION ISOLATION LEVEL {}").format(sql.SQL(isolation))
                )
                if table == "evidence_inputs":
                    conn.execute(
                        "INSERT INTO eqos.evidence_inputs(kind,label,content_sha256) "
                        "VALUES ('RETAINED_INTAKE',"
                        "'deliberately-invalid-before-kind-guard','invalid')"
                    )
                else:
                    conn.execute(
                        sql.SQL("INSERT INTO {} DEFAULT VALUES").format(
                            sql.Identifier("eqos", table)
                        )
                    )
        assert failure.value.sqlstate == "25001"
        assert "READ COMMITTED" in str(failure.value)
        target = sql.Identifier("eqos", table)
        assert conn.execute(sql.SQL("SELECT count(*) FROM {}").format(target)).fetchone() == (0,)


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_legacy_evidence_kind_keeps_its_existing_isolation_contract(
    pg_db: PgTestDatabase, isolation: str
) -> None:
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        with conn.transaction():
            conn.execute(sql.SQL("SET TRANSACTION ISOLATION LEVEL {}").format(sql.SQL(isolation)))
            record = conn.execute(
                "INSERT INTO eqos.evidence_inputs(kind,label,content_sha256) "
                "VALUES ('ISSUER_IDENTITY','legacy-isolation-characterization',%s) RETURNING id",
                ("1" * 64,),
            ).fetchone()
        assert record[0] > 0


def test_new_kind_refuses_explicit_backdated_evidence_clock(pg_db: PgTestDatabase) -> None:
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.errors.CheckViolation, match="store clock"):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO eqos.evidence_inputs(kind,label,content_sha256,recorded_at) "
                    "VALUES ('RETAINED_INTAKE','retained_intake_v1:APARINDS:FY26_Q2',%s,"
                    "eqos.store_now()-interval '1 second')",
                    ("1" * 64,),
                )
        assert conn.execute("SELECT count(*) FROM eqos.evidence_inputs").fetchone() == (0,)


def test_mid_witness_insert_fault_rolls_back_only_the_witness_transaction(
    ingest: Ingest, pending: PendingSeal, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = ingest.table_counts()
    real_rows = store_module._rows

    def fail_after_binding(conn, query, params):
        result = real_rows(conn, query, params)
        if query == store_module._INSERT_BINDING:
            raise RuntimeError(
                "witness transaction insertion fault after material and child writes"
            )
        return result

    with monkeypatch.context() as patch:
        patch.setattr(store_module, "_rows", fail_after_binding)
        with pytest.raises(RuntimeError, match="insertion fault"):
            pending.seal()
    assert ingest.table_counts() == before
    assert before["filing_packages"] > 0
    assert before["acquisition_attempts"] > 0
    accepted = pending.seal()
    assert accepted.payload.package_id == pending.handoff.package_id


def test_concurrent_identical_read_committed_seals_reuse_one_complete_witness(
    ingest: Ingest, pending: PendingSeal
) -> None:
    barrier = threading.Barrier(2)

    def seal() -> RetainedIntakeWitness:
        barrier.wait(timeout=20)
        return pending.seal()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = (executor.submit(seal), executor.submit(seal))
        witnesses = [first.result(timeout=40), second.result(timeout=40)]
    assert witnesses[0] == witnesses[1]
    counts = ingest.table_counts()
    assert counts["retained_intake_witnesses"] == 1
    assert counts["retained_intake_witness_bindings"] == 2
    assert counts["retained_intake_witness_seals"] == 1
    assert pending.store.get_by_evidence_ids([witnesses[0].evidence_input_id]) == (witnesses[0],)


def test_stale_repeatable_read_snapshot_refuses_after_another_thread_seals(
    ingest: Ingest, pending: PendingSeal
) -> None:
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as stale:
        with pytest.raises(psycopg.Error) as failure:
            with stale.transaction():
                stale.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                assert stale.execute(
                    "SELECT count(*) FROM eqos.retained_intake_witnesses"
                ).fetchone() == (0,)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    witness = executor.submit(pending.seal).result(timeout=40)
                # Authoritative stale visibility, while the other thread's commit is real.
                assert stale.execute(
                    "SELECT count(*) FROM eqos.retained_intake_witnesses"
                ).fetchone() == (0,)
                with pool.connection() as current:
                    witness_id = current.execute(
                        "SELECT id FROM eqos.retained_intake_witnesses WHERE evidence_input_id=%s",
                        (witness.evidence_input_id,),
                    ).fetchone()[0]
                request = pending.prepared.requests[0]
                stale.execute(
                    store_module._INSERT_BINDING,
                    (witness_id, *store_module._binding_values(request)),
                )
        assert failure.value.sqlstate == "25001"
    assert ingest.table_counts()["retained_intake_witness_bindings"] == 2
    assert pending.store.get_by_evidence_ids([witness.evidence_input_id]) == (witness,)


def test_read_committed_late_child_waits_for_evidence_lock_then_refuses_sealed_witness(
    ingest: Ingest, pending: PendingSeal
) -> None:
    """Atomic publication hides unsealed headers; test the observable late-child lock boundary."""
    witness = pending.seal()
    before = ingest.table_counts()
    child_pid: Future[int] = Future()
    with ingest.pg_db.runtime_pool() as pool:

        def append() -> str | None:
            with pool.connection() as child:
                child_pid.set_result(child.info.backend_pid)
                try:
                    with child.transaction():
                        child.execute(
                            store_module._INSERT_BINDING,
                            (
                                witness_id,
                                *store_module._binding_values(pending.prepared.requests[0]),
                            ),
                        )
                except psycopg.Error as failure:
                    return failure.sqlstate
                return None

        with ThreadPoolExecutor(max_workers=1) as executor:
            with pool.connection() as locker, locker.transaction():
                witness_id = locker.execute(
                    "SELECT id FROM eqos.retained_intake_witnesses WHERE evidence_input_id=%s",
                    (witness.evidence_input_id,),
                ).fetchone()[0]
                locker.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"retained-intake-evidence:{witness.evidence_input_id}",),
                )
                future = executor.submit(append)
                pid = child_pid.result(timeout=10)
                deadline = time.monotonic() + 10
                blockers: list[int] = []
                wait = threading.Event()
                while time.monotonic() < deadline:
                    blockers = locker.execute("SELECT pg_blocking_pids(%s)", (pid,)).fetchone()[0]
                    if locker.info.backend_pid in blockers:
                        break
                    wait.wait(0.02)
                assert locker.info.backend_pid in blockers
                assert not future.done()
            assert future.result(timeout=20) == "23514"
    assert ingest.table_counts() == before


@pytest.mark.parametrize(
    "document",
    [
        {"z": 'slash\\quote"\n\t', "a": [1, True, None]},
        {"é": "漢字😀\x7f", "A": "retained"},
    ],
)
def test_database_content_hash_matches_independent_python_ascii_json_contract(
    pg_db: PgTestDatabase, document: dict[str, object]
) -> None:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        actual = conn.execute(
            "SELECT eqos.retained_intake_hash(%s)", (Jsonb(document),)
        ).fetchone()[0]
    assert actual == expected


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_store_refuses_non_read_committed_caller_before_witness_mutation(
    ingest: Ingest, pending: PendingSeal, monkeypatch: pytest.MonkeyPatch, isolation: str
) -> None:
    from contextlib import contextmanager

    before = ingest.table_counts()
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:

        @contextmanager
        def existing_transaction():
            yield conn

        with pytest.raises(RetainedIntakeWitnessError, match="READ COMMITTED"):
            with conn.transaction(), monkeypatch.context() as patch:
                conn.execute(
                    sql.SQL("SET TRANSACTION ISOLATION LEVEL {}").format(sql.SQL(isolation))
                )
                patch.setattr(pending.store.repository, "_transaction", existing_transaction)
                pending.seal()
    assert ingest.table_counts() == before
