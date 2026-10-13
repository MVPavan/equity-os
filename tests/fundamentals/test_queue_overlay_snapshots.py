"""Durable queue-overlay snapshot migration and retry acceptance."""

from __future__ import annotations

import shutil
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
from evidence_support import BOTH, Ingest, dictionary, mapping_set, policy
from pg_evidence_schema_support import (
    NOW,
    SHA_A,
    _seed_every_table,
    migrator,
    runtime,
    seeded,
)
from pg_support import (
    MIGRATIONS_DIR,
    PgTestDatabase,
    create_database,
    drop_database,
    load_test_settings,
    mint_name,
)
from psycopg import errors
from run_support import Runner, SpyReader, forbid_current_reads
from test_compare_queue import _draft, _key

from fundamentals.compare import queue_overlay
from fundamentals.compare.queue import publish_queue_drafts
from fundamentals.compare.run_models import (
    DatabaseIdentity,
    ResultRow,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    RunManifest,
    RunScope,
    RunStatus,
    row_id,
)
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.canonical import ApplicabilityStatus, Basis, ValueIdentity
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
)
from fundamentals.contracts.evidence import PinnedVersions, RunMode, VersionPin
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.migrations import apply_migrations
from fundamentals.pg.settings import PgRole

__all__ = ["dictionary", "mapping_set", "migrator", "policy", "runtime", "seeded"]


def test_capture_retries_only_three_complete_serialization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fail(_pool: object, _run_id: int) -> object:
        nonlocal attempts
        attempts += 1
        raise errors.SerializationFailure("constructed serialization fixture")

    monkeypatch.setattr(queue_overlay, "_capture_once", fail)
    with pytest.raises(queue_overlay.QueueOverlayCaptureExhaustedError, match="3"):
        queue_overlay.capture_queue_overlay(object(), run_id=1)  # type: ignore[arg-type]
    assert attempts == 3


def test_capture_retries_serialization_then_returns_and_does_not_retry_other_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returned = object()
    attempts = 0

    def eventually_succeed(_pool: object, _run_id: int) -> object:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise errors.SerializationFailure("constructed retry fixture")
        return returned

    monkeypatch.setattr(queue_overlay, "_capture_once", eventually_succeed)
    assert queue_overlay.capture_queue_overlay(object(), run_id=1) is returned  # type: ignore[arg-type]
    assert attempts == 3

    def refuse(_pool: object, _run_id: int) -> object:
        raise queue_overlay.QueueOverlayReadError("constructed non-retry fixture")

    monkeypatch.setattr(queue_overlay, "_capture_once", refuse)
    with pytest.raises(queue_overlay.QueueOverlayReadError, match="non-retry"):
        queue_overlay.capture_queue_overlay(object(), run_id=1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "late_column",
    ("proposal_recorded_at", "evidence_recorded_at", "receipt_recorded_at", "recorded_at"),
)
def test_each_late_closure_proof_clock_is_refused_directly(late_column: str) -> None:
    snapshot = queue_overlay._Snapshot(
        snapshot_id=1,
        run_id=1,
        as_of=NOW,
        recorded_position=int(NOW.timestamp() * 1_000_000),
        membership_ids=(1,),
        item_ids=(1,),
        disposition_candidate_ids=(1,),
    )
    row = {
        "proposal_recorded_at": NOW,
        "evidence_recorded_at": NOW,
        "receipt_recorded_at": NOW,
        "recorded_at": NOW,
    }
    row[late_column] = NOW + timedelta(microseconds=1)

    failure = queue_overlay._candidate_failure(cast(Any, object()), cast(Any, row), snapshot)

    assert failure == "closure proof was recorded after the sealed overlay position"


@pytest.mark.pg
def test_runtime_capture_function_requires_repeatable_read(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    with pytest.raises(errors.ActiveSqlTransaction, match="repeatable read"):
        runtime.execute(
            "SELECT * FROM eqos.capture_queue_overlay_snapshot(%s)",
            (seeded["runs"],),
        )


@pytest.mark.pg
def test_runtime_cannot_forge_or_mutate_overlay_snapshots(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    statements = (
        (
            "INSERT INTO eqos.queue_overlay_snapshots "
            "(run_id,as_of,recorded_position,membership_ids,item_ids,"
            "disposition_candidate_ids) VALUES (%s,now(),0,'{}','{}','{}')",
            (seeded["runs"],),
        ),
        ("UPDATE eqos.queue_overlay_snapshots SET item_ids='{}'", ()),
        ("DELETE FROM eqos.queue_overlay_snapshots", ()),
        ("TRUNCATE eqos.queue_overlay_snapshots", ()),
    )
    for statement, parameters in statements:
        with pytest.raises(errors.InsufficientPrivilege):
            runtime.execute(statement, parameters)
    public_acl = runtime.execute(
        "SELECT NOT EXISTS ("
        "SELECT 1 FROM pg_class c CROSS JOIN LATERAL "
        "aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a "
        "WHERE c.oid='eqos.queue_overlay_snapshots'::regclass AND a.grantee=0 "
        "AND a.privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE')"
        "), NOT EXISTS ("
        "SELECT 1 FROM pg_proc p CROSS JOIN LATERAL "
        "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
        "WHERE p.oid='eqos.capture_queue_overlay_snapshot(bigint)'::regprocedure "
        "AND a.grantee=0 AND a.privilege_type='EXECUTE')"
    ).fetchone()
    assert public_acl == (True, True)


@pytest.mark.pg
def test_same_transaction_reuses_only_an_identical_visibility_set(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    with runtime.transaction():
        runtime.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        first = runtime.execute(
            "SELECT * FROM eqos.capture_queue_overlay_snapshot(%s)",
            (seeded["runs"],),
        ).fetchone()
        second = runtime.execute(
            "SELECT * FROM eqos.capture_queue_overlay_snapshot(%s)",
            (seeded["runs"],),
        ).fetchone()
        assert second == first
        assert first is not None
        expected = runtime.execute(
            "SELECT array_agg(qri.id ORDER BY qri.id),"
            "array_agg(qri.item_id ORDER BY qri.item_id) "
            "FROM eqos.queue_run_items qri WHERE qri.run_id=%s",
            (seeded["runs"],),
        ).fetchone()
        candidates = runtime.execute(
            "SELECT array_agg(qd.id ORDER BY qd.id) FROM eqos.queue_dispositions qd "
            "JOIN eqos.queue_run_items qri ON qri.item_id=qd.item_id WHERE qri.run_id=%s",
            (seeded["runs"],),
        ).fetchone()
        assert expected is not None
        assert candidates is not None
        assert tuple(first[4]) == tuple(expected[0] or ())
        assert tuple(first[5]) == tuple(expected[1] or ())
        assert tuple(first[6]) == tuple(candidates[0] or ())


@pytest.mark.pg
def test_same_triple_refuses_an_intervening_own_membership(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    before = runtime.execute("SELECT count(*) FROM eqos.queue_overlay_snapshots").fetchone()
    with pytest.raises(errors.CheckViolation, match="different visible row set"):
        with runtime.transaction(), runtime.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute(
                "SELECT * FROM eqos.capture_queue_overlay_snapshot(%s)",
                (seeded["runs"],),
            )
            publish_queue_drafts(
                cursor,
                run_id=seeded["runs"],
                drafts=(_draft(seeded, pair_identity="same-triple-intervening-item"),),
            )
            cursor.execute(
                "SELECT * FROM eqos.capture_queue_overlay_snapshot(%s)",
                (seeded["runs"],),
            )
    assert runtime.execute("SELECT count(*) FROM eqos.queue_overlay_snapshots").fetchone() == before


@pytest.mark.pg
def test_mathematically_matching_but_uncaptured_triple_is_refused(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    with pg_db.runtime_pool() as pool:
        captured = queue_overlay.capture_queue_overlay(pool, run_id=seeded["runs"])
        with pytest.raises(queue_overlay.QueueOverlayReadError, match="not captured"):
            queue_overlay.read_queue_overlay(
                pool,
                run_id=seeded["runs"],
                as_of=captured.as_of + timedelta(microseconds=1),
                recorded_position=captured.recorded_position + 1,
            )


@pytest.mark.pg
def test_concurrent_capture_is_a_complete_mvcc_publication_cut(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    staged = threading.Event()
    release = threading.Event()

    with pg_db.runtime_pool() as pool:

        def publish_uncommitted() -> int:
            with pool.connection() as connection:
                with connection.transaction(), connection.cursor() as cursor:
                    (item,) = publish_queue_drafts(
                        cursor,
                        run_id=seeded["runs"],
                        drafts=(_draft(seeded, pair_identity="concurrent-complete-mvcc-cut"),),
                    )
                    assert item.item_id is not None
                    staged.set()
                    assert release.wait(timeout=10)
                    return item.item_id

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(publish_uncommitted)
            assert staged.wait(timeout=10)
            try:
                during = queue_overlay.capture_queue_overlay(pool, run_id=seeded["runs"])
            finally:
                release.set()
            item_id = pending.result(timeout=10)
        after = queue_overlay.capture_queue_overlay(pool, run_id=seeded["runs"])

    assert "concurrent-complete-mvcc-cut" not in {item.pair_identity for item in during.open_items}
    (published,) = [item for item in after.open_items if item.item_id == item_id]
    assert published.evidence_interpretation_ids == (seeded["interpretations"],)
    assert item_id in {membership.item_id for membership in after.memberships}


@pytest.fixture
def through_0008_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[PgTestDatabase]:
    """Apply byte-identical migrations through the named 0008 boundary."""
    settings = load_test_settings()
    name = mint_name(settings)
    create_database(settings, name)
    database = PgTestDatabase(dbname=name, settings=settings)
    try:
        migrations = tmp_path / "through-0008"
        migrations.mkdir()
        expected = []
        for number in range(1, 9):
            matches = tuple(MIGRATIONS_DIR.glob(f"{number:04d}_*.sql"))
            assert len(matches) == 1
            source = matches[0]
            shutil.copyfile(source, migrations / source.name)
            expected.append(source.name)
        with database.migrator_connection() as connection:
            applied = apply_migrations(connection, migrations)
            assert [item.filename for item in applied] == expected
        # Only the two historical upgrade targets use this fixture. Keep their
        # unchanged migration calls bound to byte-identical 0001 through 0009.
        upgrade_migrations = tmp_path / "through-0009"
        upgrade_migrations.mkdir()
        for filename in expected:
            shutil.copyfile(migrations / filename, upgrade_migrations / filename)
        (ninth,) = MIGRATIONS_DIR.glob("0009_*.sql")
        shutil.copyfile(ninth, upgrade_migrations / ninth.name)
        monkeypatch.setitem(globals(), "MIGRATIONS_DIR", upgrade_migrations)
        yield database
    finally:
        drop_database(settings, name)


def _pins() -> PinnedVersions:
    pin = VersionPin(version="constructed-v1", content_sha256=SHA_A)
    return PinnedVersions(
        dictionary=pin,
        formula_set=pin,
        mapping_set=pin,
        normalisation_policy=pin,
        extractor_xbrl=pin,
        extractor_pdf=pin,
        rounding_policy=pin,
        definition_set=pin,
        comparison_policy=pin,
        alignment_rules=pin,
    )


@pytest.mark.pg
def test_0001_through_0008_run_result_and_queue_survive_0009_exactly(
    through_0008_db: PgTestDatabase,
) -> None:
    database = through_0008_db
    with psycopg.connect(
        database.settings.conninfo(PgRole.RUNTIME, dbname=database.dbname),
        autocommit=True,
    ) as runtime:
        ids = _seed_every_table(runtime)
    measurement = _key(ids["_entity"])
    period_end = measurement.period.end
    assert period_end is not None
    manifest = RunManifest(
        scope=RunScope(
            entity_ids=(ids["_entity"],),
            period_ends=(period_end,),
            bases=(Basis.CONSOLIDATED,),
            sources=("NSE_XBRL_INSTANCE",),
        ),
        cutoff=NOW,
        mode=RunMode.AS_KNOWN,
        pinned=_pins(),
        code_version="constructed-0008-upgrade",
        database_identity=DatabaseIdentity(host="constructed", port=5432, name=database.dbname),
        inputs=(
            RunInput(
                kind=RunInputKind.INTERPRETATION,
                ref_id=ids["interpretations"],
                disposition=RunInputDisposition.SELECTED,
            ),
        ),
        status=RunStatus.COMPLETE,
    )
    result = ResultRow(
        row_id=row_id(measurement, ValueIdentity.REPORTED),
        key=measurement,
        dictionary_version="constructed-v1",
        value_identity=ValueIdentity.REPORTED,
        applicability=ApplicabilityStatus.APPLICABLE,
        applicability_rule_id="constructed.always",
        extraction_status=ExtractionStatus.NONE,
        extraction_reason=None,
        corroboration_status=CorroborationStatus.FILING_ONLY,
        corroboration_reason=None,
        source_values=(),
        pairs=(),
        surfaced_restatements=(),
    )
    with database.runtime_pool() as pool:
        store = RunStore(pool)
        run_id, created = store.publish(
            manifest,
            (result,),
            definition_set_id=ids["definition_sets"],
        )
        assert created
        with (
            pool.connection() as connection,
            connection.transaction(),
            connection.cursor() as cursor,
        ):
            draft = _draft(ids, pair_identity="constructed-0008-queue").model_copy(
                update={"source_refs": (_draft(ids).source_refs[0],)}
            )
            (item,) = publish_queue_drafts(cursor, run_id=run_id, drafts=(draft,))
        before_manifest = store.read_manifest(run_id)
        before_results = store.read_results(run_id)
        with pool.connection() as connection:
            before_rows = (
                connection.execute(
                    "SELECT id,identity_hash,manifest_sha256,manifest FROM eqos.runs WHERE id=%s",
                    (run_id,),
                ).fetchone(),
                connection.execute(
                    "SELECT id,run_id,key_digest,value_identity FROM eqos.results WHERE run_id=%s",
                    (run_id,),
                ).fetchall(),
                connection.execute(
                    "SELECT id,run_id,input_sha256 FROM eqos.queue_items WHERE id=%s",
                    (item.item_id,),
                ).fetchone(),
            )

    with database.migrator_connection() as migrator:
        applied = apply_migrations(migrator, MIGRATIONS_DIR)
        assert [entry.filename for entry in applied] == ["0009_queue_overlay_snapshots.sql"]

    with database.runtime_pool() as pool:
        store = RunStore(pool)
        assert store.read_manifest(run_id) == before_manifest
        assert store.read_results(run_id) == before_results
        with pool.connection() as connection:
            after_rows = (
                connection.execute(
                    "SELECT id,identity_hash,manifest_sha256,manifest FROM eqos.runs WHERE id=%s",
                    (run_id,),
                ).fetchone(),
                connection.execute(
                    "SELECT id,run_id,key_digest,value_identity FROM eqos.results WHERE run_id=%s",
                    (run_id,),
                ).fetchall(),
                connection.execute(
                    "SELECT id,run_id,input_sha256 FROM eqos.queue_items WHERE id=%s",
                    (item.item_id,),
                ).fetchone(),
            )
        assert after_rows == before_rows
        overlay = queue_overlay.capture_queue_overlay(pool, run_id=run_id)
        assert [queued.item_id for queued in overlay.open_items] == [item.item_id]


@pytest.mark.pg
@pytest.mark.retained
def test_actual_v1_by_id_replay_survives_0001_through_0008_to_0009(
    through_0008_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: Any,
    mapping_set: Any,
    policy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = through_0008_db
    with database.runtime_pool() as pool:
        ingest = Ingest(
            database,
            EvidenceRepository(pool),
            tmp_path,
            dictionary,
            mapping_set,
            policy,
        )
        ingest.run(ingest.intake(BOTH))
        runner = Runner(ingest, pool)
        record = runner.run()
        stored = runner.results(record.run_id)

    with database.migrator_connection() as migrator_connection:
        applied = apply_migrations(migrator_connection, MIGRATIONS_DIR)
        assert [entry.filename for entry in applied] == ["0009_queue_overlay_snapshots.sql"]

    with database.runtime_pool() as pool:
        spy = SpyReader(EvidenceRepository(pool))
        forbid_current_reads(monkeypatch)
        replayed = Runner(ingest, pool).replay(record.run_id, reader=spy)

    assert replayed == stored
    assert spy.calls
