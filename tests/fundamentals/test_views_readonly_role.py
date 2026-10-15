"""D5.2 acceptance: a read-only role SELECTs the two generated status views and writes nothing
(ledger spec O5, §3; plan D5, D1, D2).

The views duplicate the Python status derivations in SQL, so the fixture matrix reaches every
report status (SUPERSEDED through a non-immediate descendant's ``APPROVE`` and, separately, its
``IMPORTED_APPROVAL``) and every memory retirement path, and the complete view row sets must
equal what ``version_status``, ``latest_validation`` and ``retrieve`` derive.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from ledger_support import ledger
from memory_support import Memory, memory
from pg_evidence_schema_support import runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors
from test_memory_promotion import capture_of_blob, cites

from fundamentals.contracts.ledger import ClaimState, DecisionKind, VersionStatus
from fundamentals.contracts.memory import MemoryKind, MemoryStatus, SupportTarget
from fundamentals.ledger import store
from fundamentals.ledger.lifecycle import version_status
from fundamentals.memory.retrieval import retrieve
from fundamentals.pg.settings import GROUP_ROLES, PgRole

__all__ = ["ledger", "memory", "runtime", "seeded"]

pytestmark = pytest.mark.pg

VIEWS = ("eqos.report_status_view", "eqos.promoted_memory_view")
_IDENTITY = """SELECT v.id, v.predecessor_id, e.entity_key, r.period, r.kind, v.knowledge_cutoff,
    v.content_hash FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.reporting_entities e ON e.id = r.entity_id"""
_ENTITY_KEY = "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s"
# Writes on each view; each is refused before or at the privilege check.
_VIEW_WRITES = {
    "eqos.report_status_view": (
        "INSERT INTO eqos.report_status_view (version_id) VALUES (1)",
        "UPDATE eqos.report_status_view SET period = 'x'",
        "DELETE FROM eqos.report_status_view",
    ),
    "eqos.promoted_memory_view": (
        "INSERT INTO eqos.promoted_memory_view (item_id) VALUES (1)",
        "UPDATE eqos.promoted_memory_view SET statement = 'x'",
        "DELETE FROM eqos.promoted_memory_view",
    ),
}
_BASE_WRITES = (
    "INSERT INTO eqos.decisions DEFAULT VALUES",
    "UPDATE eqos.decisions SET ruling = ruling",
    "DELETE FROM eqos.decisions",
    "INSERT INTO eqos.memory_items DEFAULT VALUES",
    "UPDATE eqos.memory_items SET statement = statement",
    "DELETE FROM eqos.memory_items",
    "SELECT * FROM eqos.decisions",
    "SELECT * FROM eqos.memory_items",
)


def _report_matrix(memory: Memory) -> dict[str, int]:
    """Versions whose decision heads reach every report status but ``WITHDRAWN``; returns the
    notable ids."""
    ledger, owner = memory.ledger, PgRole.OWNER
    for kind in (None, DecisionKind.REQUEST_CHANGES, DecisionKind.REJECT):
        submitted = ledger.draft(ledger.report())
        ledger.submit(submitted)
        if kind is not None:
            ledger.decide(owner, submitted, kind)
    # v1 approved, v2 rejected, v3 approved: v1 is superseded through v3, not its successor.
    v1 = memory.approved()
    v2 = memory.successor(v1)
    ledger.decide(owner, v2, DecisionKind.REJECT)
    ledger.approve(memory.successor(v2), state=ClaimState.MATCH_UNTRUSTED)
    # i1 sealed, i2 sealed, i3 imported-approved: i1 is superseded through i3.
    report = ledger.report()
    i1 = ledger.imported(report)
    ledger.imported(report, ledger.imported(report, i1), approve=True)
    ledger.imported(ledger.report())
    ledger.draft(ledger.report())
    return {"v1": v1, "i1": i1}


def _memory_matrix(memory: Memory, withdrawn: int) -> dict[str, int]:
    """Items promoted, promoted-and-flagged, retired both ways, candidate and rejected."""
    owner = PgRole.OWNER
    items = {name: memory.stage() for name in ("promoted", "retired", "superseded", "rejected")}
    items["flagged"] = memory.stage(supports=cites((SupportTarget.VERSION, withdrawn)))
    items["cross_stock"] = memory.stage(
        entity_id=None,
        kind=MemoryKind.SOURCE_QUIRK,
        supports=cites((SupportTarget.CAPTURE, capture_of_blob(memory))),
    )
    for name in ("promoted", "retired", "superseded", "flagged", "cross_stock"):
        memory.decide(owner, items[name], DecisionKind.PROMOTE)
    memory.decide(owner, items["retired"], DecisionKind.RETIRE)
    memory.decide(owner, items["rejected"], DecisionKind.REJECT_CANDIDATE)
    items["successor"] = memory.stage(supersedes_item_id=items["superseded"])
    memory.decide(owner, items["successor"], DecisionKind.PROMOTE)
    items["candidate"] = memory.stage()
    return items


def test_views_equal_the_python_derivations_for_every_status(
    memory: Memory, pg_db: PgTestDatabase
) -> None:
    """As the reader login, both views' complete row sets equal the Python derivations: every
    report status (both SUPERSEDED paths through a non-immediate descendant) and only the
    promoted items, so retired, rejected and candidate items are absent."""
    reports = _report_matrix(memory)
    withdrawn = memory.approved()
    items = _memory_matrix(memory, withdrawn)
    memory.ledger.decide(PgRole.OWNER, withdrawn, DecisionKind.WITHDRAW)
    with memory.ledger._cursor(PgRole.RUNTIME) as cursor:
        expected_reports = set()
        for identity in cursor.execute(_IDENTITY).fetchall():
            latest = store.latest_validation(cursor, identity[0])
            derived: tuple[Any, ...] = (version_status(cursor, identity[0]), None, None, None)
            if latest is not None:
                untrusted = sum(state is not ClaimState.MATCH for _, state in latest.claim_states)
                derived = (derived[0], latest.id, latest.mode, untrusted)
            expected_reports.add((*identity, *derived))
        promoted = [
            item
            for stock in (memory.ledger.entity_id, None)
            for item in retrieve(
                cursor,
                query="",
                stock=stock,
                kinds=None,
                statuses=frozenset({MemoryStatus.PROMOTED}),
                cutoff=None,
            )
        ]
        stock_key = cursor.execute(_ENTITY_KEY, (memory.ledger.entity_id,)).fetchone()
        assert stock_key is not None
    expected_items = {
        (
            item.id,
            None if item.entity_id is None else stock_key[0],
            item.kind,
            item.statement,
            item.epistemic_class,
            item.valid_from,
            item.valid_to,
            item.recorded_at,
        )
        for item in promoted
    }
    with pg_db.role_pool(PgRole.READER) as pool, pool.connection() as conn:
        assert conn.execute("SELECT current_user").fetchone() == (GROUP_ROLES[PgRole.READER],)
        report_rows = set(conn.execute(f"SELECT * FROM {VIEWS[0]}").fetchall())
        item_rows = set(conn.execute(f"SELECT * FROM {VIEWS[1]}").fetchall())

    assert report_rows == expected_reports
    statuses = {row[0]: row[7] for row in report_rows}
    assert set(statuses.values()) == set(VersionStatus)
    assert statuses[reports["v1"]] == statuses[reports["i1"]] == VersionStatus.SUPERSEDED
    assert statuses[withdrawn] == VersionStatus.WITHDRAWN
    assert any(row[10] for row in report_rows), "a non-MATCH claim is counted"

    assert item_rows == expected_items
    shown = {row[0] for row in item_rows}
    names = ("promoted", "flagged", "successor", "cross_stock")
    assert shown == {items[name] for name in names}
    assert [item.needs_revalidation for item in promoted if item.id == items["flagged"]] == [True]


def test_reader_selects_the_views_and_writes_nothing(pg_db: PgTestDatabase) -> None:
    """The reader holds no write privilege on either view and every view write is refused (the
    rewriter refuses a non-updatable view before the privilege check); base-table writes and
    reads raise ``InsufficientPrivilege``."""
    with pg_db.role_pool(PgRole.READER) as pool:
        with pool.connection() as conn:
            assert conn.execute("SELECT current_user").fetchone() == (GROUP_ROLES[PgRole.READER],)
            for view in VIEWS:
                conn.execute(f"SELECT * FROM {view}").fetchall()
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    assert conn.execute(
                        "SELECT has_table_privilege(current_user, %s, %s)", (view, privilege)
                    ).fetchone() == (False,), (view, privilege)
        for view, writes in _VIEW_WRITES.items():
            for write in writes:
                with pytest.raises(psycopg.Error) as refused, pool.connection() as conn:
                    conn.execute(write)
                assert refused.value.sqlstate in {"55000", "42501"}, (view, write)
        for statement in _BASE_WRITES:
            with pytest.raises(errors.InsufficientPrivilege), pool.connection() as conn:
                conn.execute(statement)
