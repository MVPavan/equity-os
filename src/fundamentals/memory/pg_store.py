"""The PostgreSQL ``MemoryStore`` (plan D4, M7): it acts as its pool's role, and the triggers in
``migrations/0016_memory.sql`` are authoritative, so it adds no pre-check.
"""

from __future__ import annotations

from enum import StrEnum
from typing import LiteralString

from psycopg import sql
from psycopg_pool import ConnectionPool

from fundamentals.contracts.ledger import DecisionKind, DecisionRecord, SubjectKind
from fundamentals.contracts.memory import MemoryItemDraft
from fundamentals.ledger import lifecycle, panel
from fundamentals.memory.retrieval import review_text

_ITEM: LiteralString = (
    "INSERT INTO eqos.memory_items (entity_id, kind, statement, epistemic_class, valid_from, "
    "valid_to, supersedes_item_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_SUPPORT: LiteralString = "INSERT INTO eqos.memory_supports (item_id, {}) VALUES (%s, %s)"
_NO_DECIDER = "a memory decision needs a reviewer (panel) or a ruling (owner)"


class PgMemoryStore:
    """Memory items in PostgreSQL, written as the pool's role."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def stage(self, draft: MemoryItemDraft) -> int:
        """Insert the item and its supports in one runtime transaction; returns its id."""
        item = draft.model_dump(exclude={"supports"}).values()
        values = tuple(value.value if isinstance(value, StrEnum) else value for value in item)
        with self._pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            row = cursor.execute(_ITEM, values).fetchone()
            assert row is not None
            item_id = int(row[0])
            for support in draft.supports:
                statement = sql.SQL(_SUPPORT).format(sql.Identifier(support.target.value))
                cursor.execute(statement, (item_id, support.target_id))
        return item_id

    def decide(
        self,
        item_id: int,
        kind: DecisionKind,
        *,
        reviewer: panel.Reviewer | None = None,
        ruling: str | None = None,
    ) -> DecisionRecord:
        """The panel's decision by ``reviewer``'s verdict on the item's review text, else the
        owner's ``kind`` with its verbatim ``ruling``."""
        if reviewer is not None:
            return panel.review(
                self._pool,
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=item_id,
                reviewer=reviewer,
                describe=review_text,
            )
        if ruling is None:
            raise lifecycle.DecisionRefusedError(_NO_DECIDER)
        return lifecycle.decide(
            self._pool,
            subject_kind=SubjectKind.MEMORY_ITEM,
            subject_id=item_id,
            kind=kind,
            ruling=ruling,
        )
