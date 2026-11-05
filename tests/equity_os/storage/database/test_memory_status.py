"""D4.2 acceptance (unit): memory status derives from the decision log, and memory decisions sit
on the D3 chain digest (ledger spec P1, §2; plan D4, M5)."""

from __future__ import annotations

from typing import Any

import pytest
from ledger_support import ledger
from memory_support import Memory, memory
from pg_evidence_schema_support import runtime, seeded
from psycopg.rows import dict_row
from test_ledger_integrity import chain_digest

from equity_os.contracts.publication.ledger import DecisionKind
from equity_os.contracts.storage.memory import MemoryStatus
from equity_os.storage.database.settings import PgRole
from equity_os.storage.memory.status import derive_status

__all__ = ["ledger", "memory", "runtime", "seeded"]

PROMOTE, REJECT, RETIRE = (
    DecisionKind.PROMOTE,
    DecisionKind.REJECT_CANDIDATE,
    DecisionKind.RETIRE,
)
S = MemoryStatus


@pytest.mark.parametrize(
    ("head", "retired_by_successor", "supported", "expected"),
    [
        (None, False, True, (S.CANDIDATE, False)),
        (None, False, False, (S.CANDIDATE, False)),
        (PROMOTE, False, True, (S.PROMOTED, False)),
        # Only a promoted item is flagged when a support stops holding.
        (PROMOTE, False, False, (S.PROMOTED, True)),
        (PROMOTE, True, True, (S.RETIRED, False)),
        (PROMOTE, True, False, (S.RETIRED, False)),
        (REJECT, False, False, (S.REJECTED, False)),
        (RETIRE, False, False, (S.RETIRED, False)),
    ],
)
def test_derive_status(
    head: DecisionKind | None,
    retired_by_successor: bool,
    supported: bool,
    expected: tuple[MemoryStatus, bool],
) -> None:
    """None is a candidate; PROMOTE is promoted unless a promoted successor retired it; the
    revalidation flag marks only a promoted item whose supports no longer hold."""
    assert derive_status(head, retired_by_successor, supported) == expected


@pytest.mark.pg
def test_memory_decisions_recompute_on_the_chain_digest(memory: Memory) -> None:
    """A promotion and its retirement chain like any D3 decision: each digest recomputes from
    the read-back row and its predecessor's digest."""
    item = memory.stage()
    memory.decide(PgRole.OWNER, item, PROMOTE)
    memory.decide(PgRole.OWNER, item, RETIRE)
    with memory.ledger._cursor(PgRole.RUNTIME) as cursor:
        cursor.row_factory = dict_row  # type: ignore[assignment]
        rows: list[dict[str, Any]] = cursor.execute(  # type: ignore[assignment]
            "SELECT * FROM eqos.decisions WHERE subject_kind = 'MEMORY_ITEM' AND subject_id = %s "
            "ORDER BY sequence",
            (item,),
        ).fetchall()
    assert [row["kind"] for row in rows] == [PROMOTE, RETIRE]
    predecessor = None
    for row in rows:
        assert chain_digest(row, predecessor) == row["decision_sha256"]
        predecessor = row["decision_sha256"]
