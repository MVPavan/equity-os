"""D4.2 acceptance: PROMOTE and every write that can falsify a support serialize on the queue lock
(ledger spec §2, amendment A1; plan D4, M4).

Each interleaving is proven by lock observation, not by sleeping: the holder's transaction stays
open while the other side runs in a thread, and the test polls ``pg_blocking_pids`` of the
thread's backend until it names the holder (bounded at 10 s) before the holder commits.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import psycopg
import pytest
from ledger_support import ledger
from memory_support import VERSION_WRITERS, Memory, memory, promote
from pg_evidence_schema_support import runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors

from fundamentals.contracts.memory import MemoryKind, MemoryStatus, SupportDraft, SupportTarget
from fundamentals.memory.pg_store import MemoryStageConflictError, stage
from fundamentals.pg.settings import PgRole

__all__ = ["ledger", "memory", "runtime", "seeded"]
pytestmark = pytest.mark.pg

BLOCKED_WITHIN_SECONDS = 10
_Step = Callable[[psycopg.Cursor[Any]], object]


def race(
    pg_db: PgTestDatabase, hold: _Step, wait: _Step, role: PgRole = PgRole.OWNER
) -> tuple[BaseException | None, datetime]:
    """``hold`` in an open ``role`` transaction, then ``wait`` in a thread's ``role``
    transaction once it is observed blocked on the holder; the holder commits. Returns the
    waiter's error (``None`` when it committed) and the holder's store time."""
    conninfo = pg_db.conninfo(role)
    with (
        psycopg.connect(conninfo) as holder,
        psycopg.connect(conninfo) as waiter,
        psycopg.connect(conninfo, autocommit=True) as watcher,
    ):
        with holder.cursor() as cursor:
            hold(cursor)
            (held_at,) = cursor.execute("SELECT eqos.store_now()").fetchone() or ()
        outcome: list[BaseException | None] = []

        def run() -> None:
            try:
                with waiter.transaction(), waiter.cursor() as cursor:
                    wait(cursor)
                outcome.append(None)
            except (psycopg.Error, MemoryStageConflictError) as error:
                outcome.append(error)

        racer = threading.Thread(target=run)
        racer.start()
        deadline = time.monotonic() + BLOCKED_WITHIN_SECONDS
        blocked = "SELECT %s = ANY (pg_blocking_pids(%s))"
        pids = (holder.info.backend_pid, waiter.info.backend_pid)
        while not (watcher.execute(blocked, pids).fetchone() or (False,))[0]:
            assert racer.is_alive() and time.monotonic() < deadline, outcome
            time.sleep(0.01)
        holder.commit()
        racer.join(timeout=30)
    assert len(outcome) == 1
    return outcome[0], held_at


def _item(memory: Memory, writer: str, target: SupportTarget) -> tuple[int, _Step]:
    """A candidate whose support ``writer`` falsifies, and that write: version writers against
    the base version (cited directly or through its claim), ``redispose`` a SOURCE_QUIRK's
    disposition."""
    if writer == "redispose":
        disposition = memory.one("SELECT max(id) FROM eqos.queue_dispositions")
        support = SupportDraft(target=SupportTarget.DISPOSITION, target_id=disposition)
        quirk = {"kind": MemoryKind.SOURCE_QUIRK, "entity_id": None}
        return memory.stage(**quirk, supports=(support,)), memory.writer(writer, disposition)
    target_id = memory.claim_id if target is SupportTarget.CLAIM else memory.version_id
    item = memory.stage(supports=(SupportDraft(target=target, target_id=target_id),))
    return item, memory.writer(writer, memory.version_id)


CASES = [
    pytest.param(writer, target, id=f"{writer}-{target.name.lower()}")
    for writer in VERSION_WRITERS
    for target in (SupportTarget.CLAIM, SupportTarget.VERSION)
] + [pytest.param("redispose", SupportTarget.DISPOSITION, id="redispose-disposition")]


@pytest.mark.parametrize(("writer", "target"), CASES)
def test_a_writer_holding_the_lock_makes_a_waiting_promote_refuse(
    memory: Memory, pg_db: PgTestDatabase, writer: str, target: SupportTarget
) -> None:
    """The falsifying write holds the queue lock; PROMOTE waits on it, then reads the committed
    write at READ COMMITTED and is refused."""
    item, write = _item(memory, writer, target)
    error, _ = race(pg_db, write, lambda cursor: promote(cursor, item))
    assert isinstance(error, errors.CheckViolation), error
    assert "support predicate" in str(error)
    assert memory.status(item) == (MemoryStatus.CANDIDATE, False)


@pytest.mark.parametrize(("writer", "target"), CASES)
def test_a_writer_waiting_on_promote_commits_later_and_flags_the_item(
    memory: Memory, pg_db: PgTestDatabase, writer: str, target: SupportTarget
) -> None:
    """PROMOTE holds the queue lock; the write waits, commits at a later store time, and the
    promoted item derives NEEDS_REVALIDATION."""
    item, write = _item(memory, writer, target)
    written: list[datetime] = []

    def wait(cursor: psycopg.Cursor[Any]) -> None:
        write(cursor)
        written.extend(cursor.execute("SELECT eqos.store_now()").fetchone() or ())

    error, promoted_at = race(pg_db, lambda cursor: promote(cursor, item), wait)
    assert error is None
    assert written[0] > promoted_at
    assert memory.status(item) == (MemoryStatus.PROMOTED, True)


@pytest.mark.parametrize("supports", ["identical", "different"])
def test_concurrent_identical_stages_converge_on_one_item(
    memory: Memory, pg_db: PgTestDatabase, supports: str
) -> None:
    """eqos-4j2.20: two runtime stages of one item's columns; the waiter blocks on the natural
    key until the holder commits, then returns the holder's item if its supports match, else is
    refused as a conflict. Either way one item row holds the holder's full support set."""
    claim = SupportDraft(target=SupportTarget.CLAIM, target_id=memory.claim_id)
    version = SupportDraft(target=SupportTarget.VERSION, target_id=memory.version_id)
    held = memory.draft(supports=(claim, version))
    waiting = held if supports == "identical" else memory.draft(supports=(version,))
    staged: list[int] = []
    error, _ = race(
        pg_db,
        lambda cursor: staged.append(stage(cursor, held)),
        lambda cursor: staged.append(stage(cursor, waiting)),
        role=PgRole.RUNTIME,
    )
    if supports == "identical":
        assert error is None
        assert staged[1] == staged[0]
    else:
        assert isinstance(error, MemoryStageConflictError), error
    assert memory.rows("SELECT id FROM eqos.memory_items") == [(staged[0],)]
    assert memory.rows(
        "SELECT claim_id, version_id FROM eqos.memory_supports WHERE item_id = %s "
        "ORDER BY claim_id NULLS LAST",
        staged[0],
    ) == [(memory.claim_id, None), (None, memory.version_id)]
