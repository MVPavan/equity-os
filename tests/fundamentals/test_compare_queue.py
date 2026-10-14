"""Review queue and run exit statuses (data spec §5; roadmap D1b.3).

The first half runs Apar Q2 FY26 consolidated from the retained first-party originals through
``execute_run`` and the CLI: every run routes its outcomes (``UNMAPPED`` lines LOW, extraction
``DISAGREE`` HIGH), dispositions never change results, a failed attempt makes the run
``INCOMPLETE`` and replays as ``UNAVAILABLE``, and the four exit statuses are distinct. The
second half publishes constructed drafts through ``RunStore.publish`` on an empty run: item
reuse and links, sealed append-only evidence, rollback with the run, and a stable as-of
overlay under concurrency. Each case has its own ``eqos_test_*`` database.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import BOTH, dictionary, ingest, mapping_set, policy
from pg_evidence_schema_support import _seed_every_table, runtime
from pg_support import PgTestDatabase
from psycopg import errors
from psycopg_pool import ConnectionPool
from retained_support import PdfRedaction, marked_pdf
from run_support import Runner, config_copy, edit_yaml, runner

from fundamentals.api.cli import main
from fundamentals.compare.queue import overlay_boundary, read_overlay, record_disposition
from fundamentals.compare.run_config import ConfigVersions
from fundamentals.compare.run_models import (
    DatabaseIdentity,
    RunExitStatus,
    RunManifest,
    RunScope,
    RunStatus,
)
from fundamentals.compare.run_store import STAGE_QUEUE, STAGE_RUNS, RunStore
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.comparison import (
    ExtractionStatus,
    PairKind,
    SourceRef,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    InterpretationStatus,
    PinnedVersions,
    RunMode,
    VersionPin,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import (
    UNMAPPED,
    DispositionKind,
    QueueItemDraft,
    QueueOverlay,
    QueueSeverity,
)

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "runner", "runtime"]
pytestmark = pytest.mark.pg

SCOPE = ("--entity", "APARINDS", "--period-end", "2025-09-30", "--basis", "consolidated")
NO_PL_TITLE = PdfRedaction(page=3, row_of="Statement", words=("financial",))


def _overlay(runner: Runner, run_id: int) -> QueueOverlay:
    """The run's queue at the current boundary."""
    return read_overlay(runner.pool, run_id=run_id, as_of=overlay_boundary(runner.pool))


def _rows(runner: Runner, query: str, *params: object) -> list[tuple[Any, ...]]:
    with runner.pool.connection() as conn:
        return conn.execute(query, params).fetchall()  # type: ignore[arg-type]


def _cli(runner: Runner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI at the runner's database."""
    for name, value in runner.ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)


def _run_id(capsys: pytest.CaptureFixture[str]) -> int:
    """The run id ``compare run`` printed."""
    return int(capsys.readouterr().out.splitlines()[0].split("\t")[1])


def _dispose(item_id: int, kind: DispositionKind, *amount: str) -> int:
    """Record one disposition through the CLI; returns its exit status."""
    return main(
        [
            *("compare", "queue", "dispose", "--item", str(item_id), "--kind", kind.value),
            *("--reason", "fixture", "--decider", "fixture-reviewer"),
            *("--evidence-ref", "retained-apar-q2-fy26"),
            *(("--explained-amount", *amount) if amount else ()),
        ]
    )


# --- runs over retained Apar originals ------------------------------------------------------


def test_a_first_party_run_routes_disagreements_high_and_unmapped_lines_low(
    runner: Runner,
) -> None:
    """No vendor in the run, yet its outcomes reach the queue with the run."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    rows = runner.results(record.run_id)
    overlay = _overlay(runner, record.run_id)
    assert {item.run_id for item in overlay.open_items} == {record.run_id}

    disagree = {r.key.digest() for r in rows if r.extraction_status is ExtractionStatus.DISAGREE}
    high = [item for item in overlay.open_items if item.severity is QueueSeverity.HIGH]
    assert disagree and {item.key.digest() for item in high if item.key} == disagree
    assert {(item.outcome, item.routing_reason) for item in high} == {
        (ExtractionStatus.DISAGREE.value, "EXTRACTION_DISAGREE")
    }

    unmapped = [item for item in overlay.open_items if item.outcome == UNMAPPED]
    assert unmapped and all(item.severity is QueueSeverity.LOW for item in unmapped)
    statuses = _rows(
        runner,
        "SELECT q.item_id, i.status FROM eqos.queue_item_inputs q "
        "JOIN eqos.interpretations i ON i.occurrence_id = q.occurrence_id "
        "WHERE q.item_id = ANY(%s) AND i.mapping_set_version = %s",
        [item.item_id for item in unmapped],
        record.manifest.pinned.mapping_set.version,
    )
    assert {item for item, _ in statuses} == {item.item_id for item in unmapped}
    assert {status for _, status in statuses} == {InterpretationStatus.UNMAPPED.value}


def test_accepted_as_definition_changes_no_result_and_a_new_definition_set_makes_a_new_run(
    runner: Runner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The disposition only proposes a record; its effect appears in a run pinning a new set."""
    _cli(runner, monkeypatch)
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    stored = runner.results(record.run_id)
    before = _overlay(runner, record.run_id)
    by_key = {row.key.digest(): row for row in stored}
    item = min(
        (i for i in before.open_items if i.severity is QueueSeverity.HIGH and i.key),
        key=lambda i: i.item_id,
    )
    assert item.key is not None
    cell = by_key[item.key.digest()]
    (pair,) = [p for p in cell.pairs if p.pair_kind is PairKind.EXTRACTION]
    assert pair.difference is not None
    explained = str(abs(pair.difference))
    assert _dispose(item.item_id, DispositionKind.ACCEPTED_AS_DEFINITION) == RunExitStatus.FAILURE
    assert _dispose(item.item_id, DispositionKind.ACCEPTED_AS_DEFINITION, explained) == 0

    after = _overlay(runner, record.run_id)
    assert item not in after.open_items
    assert [(d.item_id, d.kind) for d in after.dispositions] == [
        (item.item_id, DispositionKind.ACCEPTED_AS_DEFINITION)
    ]
    again = runner.run()
    assert (again.run_id, again.created) == (record.run_id, False)
    assert runner.results(record.run_id) == stored == runner.replay(record.run_id)

    root = config_copy(tmp_path)
    record_yaml = {
        "record_id": f"apar-{cell.key.canonical_id}",
        "scope": "MEASUREMENT",
        "scope_ref": item.key.digest(),
        "canonical_id": cell.key.canonical_id,
        "evidence_ref": f"queue-item:{item.item_id}",
        "explained_amount": explained,
        "unit": cell.key.value_kind.value,
    }
    edit_yaml(root / "definition_sets" / "v2.yaml", {"version": "v2", "records": [record_yaml]})
    redefined = runner.run(config_root=root, versions=ConfigVersions(definition_set="v2"))
    assert redefined.created and redefined.run_id != record.run_id
    (new_cell,) = [r for r in runner.results(redefined.run_id) if r.row_id == cell.row_id]
    assert new_cell.extraction_status is ExtractionStatus.TAGGING_DIFFERENCE
    reused = _overlay(runner, redefined.run_id).open_items
    assert all(i.key is None or i.key.digest() != item.key.digest() for i in reused)
    assert {i.item_id for i in reused if i.outcome == UNMAPPED} == {
        i.item_id for i in before.open_items if i.outcome == UNMAPPED
    }
    assert runner.results(record.run_id) == stored


def test_failure_fixture_is_incomplete_and_replay_reproduces_unavailable(
    runner: Runner, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A PDF without its P&L title: the failed attempt decides UNAVAILABLE, a run-level
    failure that queues no cell item; ``INCOMPLETE`` wins over open HIGH items."""
    _cli(runner, monkeypatch)
    ingest = runner.ingest
    no_pl = marked_pdf(ingest.tmp_path, "no-pl-title", NO_PL_TITLE)
    ingest.run(ingest.intake(BOTH, marked={Representation.PDF: no_pl}))
    assert main(["compare", "run", *SCOPE]) == RunExitStatus.INCOMPLETE
    run_id = _run_id(capsys)
    record = RunStore(runner.pool).read_manifest(run_id)
    assert record.status is RunStatus.INCOMPLETE and record.operational_failures
    stored = runner.results(run_id)
    # A reported side names the failed attempt; a derived side, its operand trace.
    unavailable = [
        value
        for row in stored
        for value in row.source_values
        if value.state is SourceState.UNAVAILABLE
    ]
    assert unavailable and all(
        value.representation is Representation.PDF
        and (value.attempt_id or value.calculation_trace_id)
        for value in unavailable
    )
    assert runner.replay(run_id) == stored
    outcomes = {item.outcome for item in _overlay(runner, run_id).open_items}
    assert SourceState.UNAVAILABLE.value not in outcomes


def test_exit_statuses_separate_open_high_success_and_failure(
    runner: Runner, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Open HIGH items exit 3; once each is disposed the same run exits 0; an unreachable
    database exits 5. With ``INCOMPLETE`` (4, above) the four statuses are distinct."""
    _cli(runner, monkeypatch)
    runner.ingest.run(runner.ingest.intake(BOTH))
    assert main(["compare", "run", *SCOPE]) == RunExitStatus.SUCCESS_WITH_OPEN_HIGH
    run_id = _run_id(capsys)
    assert main(["compare", "queue", "list", "--run", str(run_id)]) == 0
    listed = [line.split("\t") for line in capsys.readouterr().out.splitlines()[2:]]
    severities = [line[2] for line in listed]
    assert severities == sorted(severities, key=list(QueueSeverity).index)
    for line in listed:
        if line[2] == QueueSeverity.HIGH:
            assert _dispose(int(line[1]), DispositionKind.FILER_INCONSISTENCY) == 0
    assert main(["compare", "run", *SCOPE]) == RunExitStatus.SUCCESS
    assert "created\tfalse" in capsys.readouterr().out
    monkeypatch.setenv("EQOS_PG_HOST", "127.0.0.1")
    monkeypatch.setenv("EQOS_PG_PORT", "9")
    monkeypatch.setenv("EQOS_PG_CONNECT_TIMEOUT_S", "1")
    assert main(["compare", "run", *SCOPE]) == RunExitStatus.FAILURE
    assert len({int(status) for status in RunExitStatus}) == 4


# --- constructed drafts over RunStore.publish -----------------------------------------------

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


def test_items_are_append_only_sealed_and_timed_by_the_store_clock(queue: Fixture) -> None:
    """Items never change, evidence cannot be added later, a caller-supplied time is replaced."""
    run_id, _ = queue.publish(1, (queue.draft(),))
    ((item_id, recorded_at),) = queue.rows("SELECT id, recorded_at FROM eqos.queue_items")
    for statement in (
        "UPDATE eqos.queue_items SET severity = 'LOW'",
        "DELETE FROM eqos.queue_run_items",
    ):
        with queue.pool.connection() as conn, pytest.raises(psycopg.Error):
            conn.execute(statement)  # type: ignore[arg-type]
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
