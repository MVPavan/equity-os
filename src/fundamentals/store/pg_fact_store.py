"""PostgreSQL-backed fact store (plan D2, design decisions 2, 3, 7 and 9).

A ``PgFactStore`` is scoped to one ``eqos.fact_stores`` namespace: its public ids are that
store's handles, and each row and selection keeps its origin-qualified ref. Writes run at
SERIALIZABLE after the store-clock lock, only while the store is ``OPEN``, and retry
serialisation failures at most three times. Rules shared with SQLite (column text, digest,
chain and cutoff) come from ``fact_store``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import Any, LiteralString, TypeVar

import psycopg
from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fundamentals.compare.queue import lock_queue, overlay_boundary
from fundamentals.contracts.fact import Fact
from fundamentals.contracts.observation import Observation
from fundamentals.pg.legacy_import import store_state
from fundamentals.store.fact_store import (
    CanonicalSelection,
    CanonicalSelectionError,
    FactRef,
    FactStore,
    StoredRevision,
    effective_revision,
    fact_columns,
    project_revision,
    require_utc,
    selection_digest,
    verify_chain,
)

NATIVE_ORIGIN = "pg-native"
MAX_RETRIES = 3
_OPEN = "OPEN"

_ROW_COLUMNS = (
    "handle AS row_id, origin, origin_id, content_identity, value_hash, revision_family, "
    "revision_ordinal, canonical_status, canonical_selected_at, canonical_reason, fact_json"
)
_ROW: LiteralString = (
    f"SELECT {_ROW_COLUMNS} FROM eqos.fact_rows WHERE target_store = %s AND handle = %s"
)
_REVISIONS: LiteralString = (
    f"SELECT {_ROW_COLUMNS} FROM eqos.fact_rows WHERE target_store = %s AND content_identity = %s "
    "ORDER BY revision_ordinal"
)
_HISTORY: LiteralString = """
SELECT s.handle AS selection_id, s.content_identity, s.row_handle AS row_id, s.sequence,
    s.predecessor_handle AS predecessor_id, s.selected_at, s.reason, s.legacy_baseline,
    s.selection_sha256, r.content_identity AS target_identity, r.value_hash AS target_value_hash
FROM eqos.fact_selections s
JOIN eqos.fact_rows r ON r.target_store = s.target_store AND r.handle = s.row_handle
WHERE s.target_store = %s AND s.content_identity = %s ORDER BY s.sequence
"""
_IDENTITIES: LiteralString = (
    "SELECT DISTINCT content_identity FROM eqos.fact_selections WHERE target_store = %s"
)
_EXISTING: LiteralString = (
    "SELECT handle FROM eqos.fact_rows WHERE target_store = %(store)s "
    "AND content_identity = %(content_identity)s AND value_hash = %(value_hash)s"
)
_NOW: LiteralString = "SELECT eqos.store_now()"
_INSERT_ROW: LiteralString = """
INSERT INTO eqos.fact_rows (target_store, handle, origin, origin_id, content_identity, value_hash,
    revision_family, revision_ordinal, canonical_status, source_id, file_sha256, anchor,
    valid_time_start, valid_time_end, knowledge_time, first_seen_time, fact_json)
VALUES (%(store)s,
    (SELECT coalesce(max(handle), 0) + 1 FROM eqos.fact_rows WHERE target_store = %(store)s),
    %(origin)s, nextval('eqos.fact_native_id'), %(content_identity)s, %(value_hash)s,
    coalesce((SELECT revision_family FROM eqos.fact_rows WHERE target_store = %(store)s
        AND content_identity = %(content_identity)s ORDER BY revision_ordinal LIMIT 1),
        %(revision_family)s),
    (SELECT coalesce(max(revision_ordinal), 0) + 1 FROM eqos.fact_rows
        WHERE target_store = %(store)s AND content_identity = %(content_identity)s),
    %(canonical_status)s, %(source_id)s, %(file_sha256)s, %(anchor)s, %(valid_time_start)s,
    %(valid_time_end)s, %(knowledge_time)s, %(first_seen_time)s, %(fact_json)s)
RETURNING handle
"""
# Native selections recorded, or targeting rows created, after a cutoff (0037: store clock).
_LATE: LiteralString = """
SELECT s.handle FROM eqos.fact_selections s
JOIN eqos.fact_rows r ON r.target_store = s.target_store AND r.handle = s.row_handle
WHERE s.target_store = %(store)s AND s.content_identity = %(identity)s
    AND ((s.recorded_at > %(cutoff)s AND NOT eqos.legacy_time_exempt(s.target_store, s.origin))
    OR (r.created_at::timestamptz > %(cutoff)s
        AND NOT eqos.legacy_time_exempt(r.target_store, r.origin)))
"""
_INSERT_SELECTION: LiteralString = """
INSERT INTO eqos.fact_selections (target_store, handle, origin, origin_id, content_identity,
    row_handle, sequence, predecessor_handle, selected_at, reason, legacy_baseline, synthesized,
    selection_sha256)
VALUES (%(store)s,
    (SELECT coalesce(max(handle), 0) + 1 FROM eqos.fact_selections WHERE target_store = %(store)s),
    %(origin)s, nextval('eqos.fact_native_id'), %(content_identity)s, %(row_id)s, %(sequence)s,
    %(predecessor_id)s, %(selected_at)s, %(reason)s, false, false, %(digest)s)
"""
_INSERT_STORE: LiteralString = "INSERT INTO eqos.fact_stores (store_id, kind) VALUES (%s, 'NATIVE')"
_OPEN_EVENT: LiteralString = (
    "INSERT INTO eqos.fact_store_events (store_id, operation_id, state, recorded_at) "
    "VALUES (%s, %s, 'OPEN', eqos.store_now())"
)

# One snapshot for a cutoff read: the late-selection set and the history must agree.
_SNAPSHOT: LiteralString = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"

_T = TypeVar("_T")
_DictCursor = Cursor[dict[str, Any]]


class FactStoreFrozenError(Exception):
    """A write reached a store that is not ``OPEN``; nothing was persisted."""

    def __init__(self, state: str | None) -> None:
        super().__init__(f"fact store state is {state}; writes need {_OPEN}")
        self.state = state


class FactStoreRetryError(Exception):
    """A write kept failing serialisation after the bounded retries."""


def require_open(cursor: Cursor[Any], store_id: str) -> None:
    """Refuse unless the store's latest event is ``OPEN``."""
    state = store_state(cursor.connection, store_id)
    if state != _OPEN:
        raise FactStoreFrozenError(state)


def insert_revision(cursor: Cursor[Any], store_id: str, fact: Fact) -> int:
    """The handle of ``fact`` in ``store_id``: existing, or a newly appended ``CANDIDATE``.

    The caller holds a SERIALIZABLE transaction that took ``lock_queue`` and ``require_open``.
    """
    params: dict[str, object] = {"store": store_id, "origin": NATIVE_ORIGIN, **fact_columns(fact)}
    with cursor.connection.cursor() as own:
        existing = own.execute(_EXISTING, params).fetchone()
        if existing is not None:
            return int(existing[0])
        params |= {"revision_family": fact.revision_family}
        inserted = own.execute(_INSERT_ROW, params).fetchone()
    assert inserted is not None
    return int(inserted[0])


def create_native_store(pool: ConnectionPool, label: str) -> str:
    """Register an empty ``OPEN`` native store and return its id."""
    store_id = f"{NATIVE_ORIGIN}-{label}"
    with pool.connection() as conn, conn.transaction():
        conn.execute(_INSERT_STORE, (store_id,))
        conn.execute(_OPEN_EVENT, (store_id, uuid.uuid4()))
    return store_id


def run_serializable[T](
    pool: ConnectionPool, store_id: str, operation: Callable[[_DictCursor], T]
) -> T:
    """Run ``operation`` at SERIALIZABLE after the clock lock on an ``OPEN`` store, retrying
    serialisation failures at most ``MAX_RETRIES`` times (design decision 9)."""
    for _ in range(MAX_RETRIES + 1):
        try:
            with _transaction(pool, "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE") as cursor:
                lock_queue(cursor)
                require_open(cursor, store_id)
                return operation(cursor)
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            continue
    raise FactStoreRetryError(f"fact store write failed {MAX_RETRIES + 1} times")


@contextmanager
def _transaction(pool: ConnectionPool, mode: LiteralString | None) -> Iterator[_DictCursor]:
    """A dict cursor inside one transaction, optionally set to ``mode``."""
    with pool.connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cursor:
        if mode is not None:
            cursor.execute(mode)
        yield cursor


def _store_now(cursor: Cursor[Any]) -> str:
    """The store clock as the SQLite store writes times (UTC ``isoformat``)."""
    row = cursor.connection.execute(_NOW).fetchone()
    assert row is not None
    now: datetime = row[0]
    return now.astimezone(UTC).isoformat()


class PgFactStore:
    """The ``FactStoreLike`` contract over one PostgreSQL store namespace.

    The pool belongs to the caller; ``close`` releases nothing.
    """

    def __init__(self, pool: ConnectionPool, store_id: str) -> None:
        """Scope the store to ``store_id``."""
        self._pool = pool
        self._store_id = store_id

    def close(self) -> None:
        """Nothing to release: the caller owns the pool."""

    @staticmethod
    def content_identity_for(observation: Observation) -> str:
        """The content-identity key for an observation."""
        return FactStore.content_identity_for(observation)

    def fact_ref(self, row_id: int) -> FactRef:
        """The row's preserved origin-qualified reference."""
        with self._read() as cursor:
            row = self._row(cursor, row_id)
        return FactRef(store_id=self._store_id, origin=row["origin"], origin_id=row["origin_id"])

    def put(self, fact: Fact) -> StoredRevision:
        """Store ``fact`` append-only; an identical identity and value returns the existing row."""

        def write(cursor: _DictCursor) -> StoredRevision:
            handle = insert_revision(cursor, self._store_id, fact)
            return self._revision(cursor, self._row(cursor, handle))

        return self._write(write)

    def select_canonical(
        self,
        row_id: int,
        reason: str,
        selected_at: datetime | None = None,
        *,
        expected_selection_id: int | None = None,
    ) -> StoredRevision:
        """Append a selection with SQLite's rules; ids are this store's handles.

        ``expected_selection_id=0`` expects an empty chain; omission captures the head before
        the write transaction, as SQLite does.
        """
        stamp = require_utc(selected_at) if selected_at is not None else None
        if not reason.strip():
            raise CanonicalSelectionError("selection reason must be non-empty")
        expected = expected_selection_id
        if expected is None:
            with self._read() as cursor:
                history = self._history(cursor, self._row(cursor, row_id)["content_identity"])
            expected = history[-1].selection_id if history else 0

        def write(cursor: _DictCursor) -> StoredRevision:
            target = self._row(cursor, row_id)
            history = self._history(cursor, target["content_identity"])
            head = history[-1] if history else None
            if expected != (head.selection_id if head else 0):
                raise CanonicalSelectionError("stale canonical selection predecessor")
            when = stamp or datetime.fromisoformat(_store_now(cursor))
            fact = Fact.model_validate_json(target["fact_json"])
            if when < max(require_utc(fact.knowledge_time), require_utc(fact.first_seen_time)):
                raise CanonicalSelectionError("selection precedes fact knowledge/first-seen time")
            if head is not None and when <= head.selected_at:
                raise CanonicalSelectionError("selection time must strictly follow predecessor")
            values: dict[str, Any] = {
                "content_identity": target["content_identity"],
                "row_id": row_id,
                "sequence": head.sequence + 1 if head else 1,
                "predecessor_id": head.selection_id if head else None,
                "selected_at": when.isoformat(),
                "reason": reason,
            }
            digest = selection_digest(
                **values,
                value_hash=target["value_hash"],
                predecessor_sha256=head.selection_sha256 if head else None,
                legacy_baseline=False,
            )
            cursor.execute(
                _INSERT_SELECTION,
                values | {"store": self._store_id, "origin": NATIVE_ORIGIN, "digest": digest},
            )
            return self._revision(cursor, target)

        return self._write(write)

    def get_revisions(self, content_identity: str) -> tuple[StoredRevision, ...]:
        """All retained revisions for an identity, oldest first."""
        with self._read() as cursor:
            rows = cursor.execute(_REVISIONS, (self._store_id, content_identity)).fetchall()
            return tuple(self._revision(cursor, row) for row in rows)

    def get_selection_history(self, content_identity: str) -> tuple[CanonicalSelection, ...]:
        """The verified selection chain, imported and native alike."""
        with self._read() as cursor:
            return self._history(cursor, content_identity)

    def get_canonical(
        self, content_identity: str, *, cutoff: datetime | None = None
    ) -> StoredRevision | None:
        """The decision effective at ``cutoff`` (default: the overlay boundary)."""
        stamp = require_utc(cutoff) if cutoff is not None else overlay_boundary(self._pool)
        with self._read(_SNAPSHOT) as cursor:
            return self._canonical(cursor, content_identity, stamp)

    def query_canonical(self, *, cutoff: datetime | None = None) -> tuple[StoredRevision, ...]:
        """One effective selection per identity, read from one snapshot."""
        stamp = require_utc(cutoff) if cutoff is not None else overlay_boundary(self._pool)
        with self._read(_SNAPSHOT) as cursor:
            identities = cursor.execute(_IDENTITIES, (self._store_id,)).fetchall()
            found = [self._canonical(cursor, row["content_identity"], stamp) for row in identities]
        return tuple(sorted((row for row in found if row is not None), key=lambda row: row.row_id))

    def _read(self, mode: LiteralString | None = None) -> AbstractContextManager[_DictCursor]:
        """A dict cursor inside one transaction, optionally set to ``mode``."""
        return _transaction(self._pool, mode)

    def _write(self, operation: Callable[[_DictCursor], _T]) -> _T:
        """Run ``operation`` in design decision 9's transaction on this store."""
        return run_serializable(self._pool, self._store_id, operation)

    def _row(self, cursor: _DictCursor, row_id: int) -> dict[str, Any]:
        """The stored row for handle ``row_id``."""
        row = cursor.execute(_ROW, (self._store_id, row_id)).fetchone()
        if row is None:
            raise KeyError(f"no revision with row_id={row_id}")
        return row

    def _history(
        self, cursor: _DictCursor, content_identity: str
    ) -> tuple[CanonicalSelection, ...]:
        """The identity's selection chain, verified."""
        rows = cursor.execute(_HISTORY, (self._store_id, content_identity)).fetchall()
        decisions = tuple(
            CanonicalSelection.model_validate(
                row | {"selected_at": require_utc(datetime.fromisoformat(row["selected_at"]))}
            )
            for row in rows
        )
        targets = {
            row["row_id"]: (row["target_identity"], row["target_value_hash"]) for row in rows
        }
        verify_chain(content_identity, decisions, targets)
        return decisions

    def _revision(self, cursor: _DictCursor, row: dict[str, Any]) -> StoredRevision:
        """A row with its status projected from its identity's chain."""
        return project_revision(row, self._history(cursor, row["content_identity"]))

    def _canonical(
        self, cursor: _DictCursor, content_identity: str, cutoff: datetime
    ) -> StoredRevision | None:
        """The revision selected at ``cutoff``, if its fact was known, and (native) its row and
        selection recorded, by then."""
        params = {"store": self._store_id, "identity": content_identity, "cutoff": cutoff}
        late = {row["handle"] for row in cursor.execute(_LATE, params).fetchall()}
        decision = effective_revision(
            [d for d in self._history(cursor, content_identity) if d.selection_id not in late],
            cutoff,
            lambda row_id: Fact.model_validate_json(self._row(cursor, row_id)["fact_json"]),
        )
        if decision is None:
            return None
        return project_revision(self._row(cursor, decision.row_id), (), decision)
