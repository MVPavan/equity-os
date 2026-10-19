"""The PostgreSQL ``MemoryStore`` (plan D4, M6, M7): it acts as its pool's role, and the
triggers in ``migrations/0016_memory.sql`` are authoritative, so it adds no pre-check. Reads run
in one REPEATABLE READ, READ ONLY transaction, so every query sees one database state.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from typing import Any, LiteralString

from psycopg import Cursor, sql
from psycopg_pool import ConnectionPool

from fundamentals.contracts.ledger import DecisionKind, DecisionRecord, SubjectKind
from fundamentals.contracts.memory import (
    MemoryItemDraft,
    MemoryKind,
    MemoryStatus,
    RetrievedItem,
    SupportDraft,
    SupportTarget,
)
from fundamentals.ledger import lifecycle, panel
from fundamentals.memory import retrieval

_ITEM: LiteralString = (
    "INSERT INTO eqos.memory_items (entity_id, kind, statement, epistemic_class, valid_from, "
    "valid_to, supersedes_item_id) VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING RETURNING id"
)
# The natural key (0041), null-safe.
_EXISTING: LiteralString = (
    "SELECT id FROM eqos.memory_items WHERE entity_id IS NOT DISTINCT FROM %s AND kind = %s "
    "AND statement = %s AND epistemic_class = %s AND valid_from = %s "
    "AND valid_to IS NOT DISTINCT FROM %s AND supersedes_item_id IS NOT DISTINCT FROM %s"
)
_SUPPORTS = sql.SQL("SELECT {} FROM eqos.memory_supports WHERE item_id = %s").format(
    sql.SQL(", ").join(sql.Identifier(target.value) for target in SupportTarget)
)
_SUPPORT: LiteralString = "INSERT INTO eqos.memory_supports (item_id, {}) VALUES (%s, %s)"
_SNAPSHOT: LiteralString = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
_NO_DECIDER = "a memory decision needs a reviewer (panel) or a ruling (owner)"
_NOT_REVIEWED = "a reviewer decides only a candidate's PROMOTE or REJECT_CANDIDATE, not {kind}"
_REVIEWED = frozenset({DecisionKind.PROMOTE, DecisionKind.REJECT_CANDIDATE})
_CONFLICT = "memory item {item_id} has the same columns and different supports"


class MemoryStageConflictError(ValueError):
    """A stage whose columns match an existing item's but whose supports differ."""


def stage(cursor: Cursor[Any], draft: MemoryItemDraft) -> int:
    """Insert the item and its supports in the caller's transaction and return its id; an item
    with the same columns and supports already staged is returned with nothing written."""
    item = draft.model_dump(exclude={"supports"}).values()
    values = tuple(value.value if isinstance(value, StrEnum) else value for value in item)
    row = cursor.execute(_ITEM, values).fetchone()
    if row is None:
        ((item_id,),) = cursor.execute(_EXISTING, values).fetchall()
        rows = cursor.execute(_SUPPORTS, (item_id,)).fetchall()
        staged = {
            SupportDraft(target=target, target_id=target_id)
            for columns in rows
            for target, target_id in zip(SupportTarget, columns, strict=True)
            if target_id is not None
        }
        if staged != set(draft.supports):
            raise MemoryStageConflictError(_CONFLICT.format(item_id=item_id))
        return int(item_id)
    item_id = int(row[0])
    for support in draft.supports:
        statement = sql.SQL(_SUPPORT).format(sql.Identifier(support.target.value))
        cursor.execute(statement, (item_id, support.target_id))
    return item_id


class PgMemoryStore:
    """Memory items in PostgreSQL, written as the pool's role."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def stage(self, draft: MemoryItemDraft) -> int:
        """:func:`stage` in one transaction as the pool's role."""
        with self._pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            return stage(cursor, draft)

    def decide(
        self,
        item_id: int,
        kind: DecisionKind,
        *,
        reviewer: panel.Reviewer | None = None,
        ruling: str | None = None,
    ) -> DecisionRecord:
        """The panel's decision by ``reviewer``'s verdict on the item's review text, else the
        owner's ``kind`` with its verbatim ``ruling``. A reviewer decides only candidate review."""
        if reviewer is not None:
            if kind not in _REVIEWED:
                raise lifecycle.DecisionRefusedError(_NOT_REVIEWED.format(kind=kind.value))
            return panel.review(
                self._pool,
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=item_id,
                reviewer=reviewer,
                describe=retrieval.review_text,
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

    def retrieve(
        self,
        query: str,
        *,
        stock: int | None,
        kinds: frozenset[MemoryKind] | None = None,
        statuses: frozenset[MemoryStatus] = frozenset({MemoryStatus.PROMOTED}),
        cutoff: datetime | None = None,
    ) -> tuple[RetrievedItem, ...]:
        """The stock's items matching ``query`` as known at ``cutoff``, promoted ones by
        default, with supports and flags."""
        with self._snapshot() as cursor:
            return retrieval.retrieve(
                cursor, query=query, stock=stock, kinds=kinds, statuses=statuses, cutoff=cutoff
            )

    def provenance(self, item_id: int) -> tuple[RetrievedItem, ...]:
        """The item and its supersession lineage, each with its supports."""
        with self._snapshot() as cursor:
            return retrieval.provenance(cursor, item_id)

    @contextmanager
    def _snapshot(self) -> Iterator[Cursor[Any]]:
        """A cursor in one REPEATABLE READ, READ ONLY transaction."""
        with self._pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            cursor.execute(_SNAPSHOT)
            yield cursor
