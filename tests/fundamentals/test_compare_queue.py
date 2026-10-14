"""Review queue (data spec §5): item reuse and links, sealed evidence, run-transaction
publication through ``RunStore.publish``, and a stable as-of overlay under concurrency.

Rows are constructed plumbing fixtures on a disposable ``eqos_test_*`` database.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from typing import Any

import psycopg
import pytest
from pg_evidence_schema_support import _seed_every_table, runtime
from pg_support import PgTestDatabase
from psycopg import errors
from psycopg_pool import ConnectionPool

from fundamentals.compare.queue import overlay_boundary, read_overlay, record_disposition
from fundamentals.compare.run_models import DatabaseIdentity, RunManifest, RunScope, RunStatus
from fundamentals.compare.run_store import STAGE_QUEUE, STAGE_RUNS, RunStore
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.comparison import SourceRef, SourceRole
from fundamentals.contracts.evidence import PinnedVersions, RunMode, VersionPin
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import DispositionKind, QueueItemDraft, QueueSeverity

__all__ = ["runtime"]
pytestmark = pytest.mark.pg

_PINS = PinnedVersions.model_validate(
    {
        name: VersionPin(
            version="fixture", content_sha256=hashlib.sha256(name.encode()).hexdigest()
        )
        for name in PinnedVersions.model_fields
        if name != "vendor_extractors"
    }
)


class Fixture:
    """Seeded evidence, a runtime pool and a run factory over ``RunStore.publish``."""

    def __init__(self, ids: dict[str, int], pool: ConnectionPool) -> None:
        self.ids = ids
        self.pool = pool
        self.store = RunStore(pool)

    def draft(self, *, interpretation: bool = True, pair: str = "fixture-pair") -> QueueItemDraft:
        """A HIGH mismatch on one key, evidenced by the seeded occurrence (and interpretation)."""
        return QueueItemDraft(
            key=MeasurementKey(
                entity_id=self.ids["_entity"],
                canonical_id="synthetic_metric",
                period=PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)),
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
                currency="INR",
                value_kind=ValueKind.CURRENCY_AMOUNT,
                dimensions=DimensionSet(),
            ),
            pair_identity=pair,
            outcome="MISMATCH",
            severity=QueueSeverity.HIGH,
            routing_reason="EXTRACTION_DISAGREE",
            source_refs=(
                SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.XBRL),
                SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.PDF),
            ),
            evidence_occurrence_ids=(self.ids["occurrences"],),
            evidence_interpretation_ids=(self.ids["interpretations"],) if interpretation else (),
        )

    def publish(
        self, day: int, drafts: tuple[QueueItemDraft, ...], hook: Any = None
    ) -> tuple[int, bool]:
        """Publish a distinct (by period end) empty run carrying ``drafts``."""
        manifest = RunManifest(
            scope=RunScope(
                entity_ids=(self.ids["_entity"],),
                period_ends=(date(2025, 9, day),),
                bases=(Basis.CONSOLIDATED,),
                sources=("NSE_XBRL_INSTANCE",),
            ),
            cutoff=datetime(2026, 1, 1, tzinfo=UTC),
            mode=RunMode.AS_KNOWN,
            pinned=_PINS,
            code_version="queue-fixture",
            database_identity=DatabaseIdentity(host="fixture", port=1, name="fixture"),
            inputs=(),
            status=RunStatus.COMPLETE,
        )
        return self.store.publish(
            manifest,
            (),
            definition_set_id=self.ids["definition_sets"],
            publish_hook=hook,
            queue_drafts=drafts,
        )

    def rows(self, query: str, *params: object) -> list[tuple[Any, ...]]:
        with self.pool.connection() as conn:
            return conn.execute(query, params).fetchall()  # type: ignore[arg-type]


@pytest.fixture
def queue(pg_db: PgTestDatabase, runtime: psycopg.Connection) -> Iterator[Fixture]:
    ids = _seed_every_table(runtime)
    with pg_db.runtime_pool() as pool:
        yield Fixture(ids, pool)


def test_identical_inputs_reuse_the_item_and_changed_inputs_link_a_new_one(
    queue: Fixture,
) -> None:
    """Same inputs: one item, a membership per run. Changed inputs: a new, linked item."""
    first, _ = queue.publish(1, (queue.draft(),))
    second, _ = queue.publish(2, (queue.draft(),))
    changed, _ = queue.publish(3, (queue.draft(interpretation=False),))
    items = queue.rows("SELECT id, run_id, predecessor_item_id FROM eqos.queue_items ORDER BY id")
    assert [(run, predecessor) for _, run, predecessor in items] == [
        (first, None),
        (changed, items[0][0]),
    ]
    links = queue.rows("SELECT run_id, item_id FROM eqos.queue_run_items ORDER BY id")
    assert links == [(first, items[0][0]), (second, items[0][0]), (changed, items[1][0])]
    inputs = queue.rows(
        "SELECT item_id, occurrence_id, interpretation_id FROM eqos.queue_item_inputs ORDER BY id"
    )
    assert {row[0] for row in inputs if row[2] is not None} == {items[0][0]}


def test_item_evidence_is_sealed_and_times_are_the_store_clock(queue: Fixture) -> None:
    """Evidence cannot be added to an item later; a caller-supplied time is overwritten."""
    run_id, _ = queue.publish(1, (queue.draft(),))
    ((item_id, recorded_at),) = queue.rows("SELECT id, recorded_at FROM eqos.queue_items")
    ((created_at,),) = queue.rows("SELECT created_at FROM eqos.runs WHERE id = %s", run_id)
    assert recorded_at == created_at  # one transaction, one cached store-clock time
    with queue.pool.connection() as conn, pytest.raises(errors.CheckViolation, match="sealed"):
        conn.execute(
            "INSERT INTO eqos.queue_item_inputs (item_id, attempt_id) VALUES (%s, %s)",
            (item_id, queue.ids["acquisition_attempts"]),
        )
    early = datetime(2000, 1, 1, tzinfo=UTC)
    with queue.pool.connection() as conn:
        conn.execute(
            "INSERT INTO eqos.queue_run_items (run_id, item_id, recorded_at) VALUES (%s, %s, %s)",
            (queue.ids["runs"], item_id, early),
        )
    ((stored,),) = queue.rows(
        "SELECT recorded_at FROM eqos.queue_run_items WHERE run_id = %s", queue.ids["runs"]
    )
    assert stored > early


def test_queue_failure_rolls_back_the_run_and_a_retry_publishes(queue: Fixture) -> None:
    """Queue publication is part of the run transaction."""

    def fail_at_queue(stage: str) -> None:
        if stage == STAGE_QUEUE:
            raise RuntimeError("injected queue fault")

    with pytest.raises(RuntimeError, match="injected"):
        queue.publish(1, (queue.draft(),), hook=fail_at_queue)
    assert queue.rows("SELECT count(*) FROM eqos.runs") == [(1,)]  # the seeded run only
    assert queue.rows("SELECT count(*) FROM eqos.queue_items") == [(0,)]
    run_id, created = queue.publish(1, (queue.draft(),))
    assert created
    assert queue.rows("SELECT run_id FROM eqos.queue_run_items") == [(run_id,)]


def test_concurrent_reversed_batches_share_items_without_deadlock(queue: Fixture) -> None:
    """Two runs publishing the same two drafts in opposite orders: two items, four links."""
    first, other = queue.draft(pair="pair-a"), queue.draft(pair="pair-b")
    barrier = threading.Barrier(2)

    def publish(day: int, drafts: tuple[QueueItemDraft, ...]) -> int:
        barrier.wait(timeout=10)
        return queue.publish(day, drafts)[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = [
            pool.submit(publish, 1, (first, other)),
            pool.submit(publish, 2, (other, first)),
        ]
        run_ids = {future.result(timeout=30) for future in runs}
    assert queue.rows("SELECT count(*) FROM eqos.queue_items") == [(2,)]
    links = queue.rows("SELECT run_id, count(*) FROM eqos.queue_run_items GROUP BY run_id")
    assert dict(links) == dict.fromkeys(run_ids, 2)


def test_overlay_boundary_waits_for_writers_and_rereads_identically(queue: Fixture) -> None:
    """A boundary taken while a run is publishing waits for it; later writes never leak in."""
    started, release = threading.Event(), threading.Event()

    def hold(stage: str) -> None:
        if stage == STAGE_RUNS:
            started.set()
            assert release.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=2) as pool:
        publishing = pool.submit(queue.publish, 1, (queue.draft(),), hold)
        assert started.wait(timeout=10)
        boundary = pool.submit(overlay_boundary, queue.pool)
        with pytest.raises(TimeoutError):
            boundary.result(timeout=0.5)  # the writer holds the queue lock
        release.set()
        run_id, _ = publishing.result(timeout=10)
        as_of = boundary.result(timeout=10)

    before = read_overlay(queue.pool, run_id=run_id, as_of=as_of)
    (item,) = before.open_items
    assert item.run_id == run_id and item.recorded_at <= as_of and before.dispositions == ()
    disposition = record_disposition(
        queue.pool,
        item_id=item.item_id,
        kind=DispositionKind.PARSER_DEFECT,
        reason="fixture",
        decider="fixture-reviewer",
        evidence_ref="fixture-evidence",
    )
    later_run, _ = queue.publish(2, (queue.draft(),))
    assert read_overlay(queue.pool, run_id=run_id, as_of=as_of) == before
    assert read_overlay(queue.pool, run_id=later_run, as_of=as_of).open_items == ()

    after = read_overlay(queue.pool, run_id=run_id, as_of=overlay_boundary(queue.pool))
    assert after.open_items == ()
    assert [(item.disposition_id, item.kind) for item in after.dispositions] == [
        (disposition, DispositionKind.PARSER_DEFECT)
    ]
