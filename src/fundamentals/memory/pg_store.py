"""The PostgreSQL ``MemoryStore`` (plan D4, M7): it acts as its pool's role, and the triggers in
``migrations/0016_memory.sql`` are authoritative, so it adds no pre-check.
"""

from __future__ import annotations

from enum import StrEnum
from typing import LiteralString

from psycopg import sql
from psycopg_pool import ConnectionPool

from fundamentals.contracts.memory import MemoryItemDraft

_ITEM: LiteralString = (
    "INSERT INTO eqos.memory_items (entity_id, kind, statement, epistemic_class, valid_from, "
    "valid_to, supersedes_item_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_SUPPORT: LiteralString = "INSERT INTO eqos.memory_supports (item_id, {}) VALUES (%s, %s)"


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
