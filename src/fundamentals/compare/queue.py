"""Append-only review queue: publication, dispositions and the as-of overlay (data spec §5).

An item is keyed by measurement key, pair, outcome and input hash. Identical inputs reuse the
stored item; changed inputs open a new item linked to its predecessor. Run membership is
recorded per run. Queue publication, disposition writes and overlay boundaries share one
transaction-level advisory lock, taken before the transaction's first ``eqos.store_now()``
call (the clock caches its time per transaction). Every queue time at or before a boundary
therefore belongs to a committed transaction, so an as-of read is stable.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from fundamentals.contracts.review_queue import (
    DispositionKind,
    QueueDisposition,
    QueueItem,
    QueueItemDraft,
    QueueOverlay,
)
from fundamentals.contracts.snapshot import canonical_sha256

# One fixed key: every queue writer and boundary serializes on it.
QUEUE_LOCK_KEY = 0x5155455545

_LOCK: LiteralString = "SELECT pg_advisory_xact_lock(%s)"
_NOW: LiteralString = "SELECT eqos.store_now() AS now"
_EXACT_ITEM: LiteralString = (
    "SELECT id FROM eqos.queue_items WHERE key_digest IS NOT DISTINCT FROM %s "
    "AND pair_identity = %s AND outcome = %s AND input_sha256 = %s"
)
_LATEST_ITEM: LiteralString = (
    "SELECT id FROM eqos.queue_items WHERE key_digest IS NOT DISTINCT FROM %s "
    "AND pair_identity = %s AND outcome = %s ORDER BY id DESC LIMIT 1"
)
_INSERT_ITEM: LiteralString = (
    "INSERT INTO eqos.queue_items (run_id, key_digest, measurement_key, pair_identity, outcome, "
    "input_sha256, severity, diagnostic, routing_reason, reason_code, source_refs, "
    "predecessor_item_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_INSERT_INPUT: LiteralString = (
    "INSERT INTO eqos.queue_item_inputs (item_id, occurrence_id, interpretation_id, attempt_id) "
    "VALUES (%s, %s, %s, %s)"
)
_INSERT_MEMBERSHIP: LiteralString = (
    "INSERT INTO eqos.queue_run_items (run_id, item_id) VALUES (%s, %s) "
    "ON CONFLICT (run_id, item_id) DO NOTHING"
)
_INSERT_DISPOSITION: LiteralString = (
    "INSERT INTO eqos.queue_dispositions (item_id, kind, reason, decider, evidence_ref, "
    "explained_amount) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
)
_OVERLAY: LiteralString = (
    "SELECT i.id AS item_id, i.run_id, i.measurement_key AS key, i.pair_identity, i.outcome, "
    "i.input_sha256, i.severity, i.diagnostic, i.routing_reason, i.reason_code, i.source_refs, "
    "i.predecessor_item_id, i.recorded_at, d.id AS disposition_id, d.kind, d.reason, d.decider, "
    "d.evidence_ref, d.explained_amount, d.recorded_at AS disposed_at "
    "FROM eqos.queue_run_items m JOIN eqos.queue_items i ON i.id = m.item_id "
    "LEFT JOIN eqos.queue_dispositions d ON d.item_id = i.id AND d.recorded_at <= %(as_of)s "
    "WHERE m.run_id = %(run_id)s AND m.recorded_at <= %(as_of)s ORDER BY i.id, d.id"
)


def lock_queue(cursor: Cursor[Any]) -> None:
    """Take the shared queue lock; call it before the transaction's first store-clock read."""
    cursor.execute(_LOCK, (QUEUE_LOCK_KEY,))


def publish_queue_drafts(
    cursor: Cursor[Any], *, run_id: int, drafts: Sequence[QueueItemDraft]
) -> tuple[int, ...]:
    """Reuse or create each draft's item in the caller's transaction and link it to the run.

    The caller holds :func:`lock_queue` from before its first store-clock read.
    """
    prepared = sorted(((_input_sha256(draft), draft) for draft in drafts), key=_order)
    return tuple(_publish_one(cursor, run_id, digest, draft) for digest, draft in prepared)


def record_disposition(
    pool: ConnectionPool,
    *,
    item_id: int,
    kind: DispositionKind,
    reason: str,
    decider: str,
    evidence_ref: str,
    explained_amount: Decimal | None = None,
) -> int:
    """Append one disposition; its recorded time is the store clock's."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        row = cursor.execute(
            _INSERT_DISPOSITION,
            (item_id, kind.value, reason, decider, evidence_ref, explained_amount),
        ).fetchone()
        assert row is not None
        return int(row[0])


def overlay_boundary(pool: ConnectionPool) -> datetime:
    """A store-clock time before which every queue write is committed."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        lock_queue(cursor)
        row = cursor.execute(_NOW).fetchone()
        assert row is not None
        now: datetime = row[0]
        return now


def read_overlay(pool: ConnectionPool, *, run_id: int, as_of: datetime) -> QueueOverlay:
    """The run's items and dispositions as of ``as_of`` (a :func:`overlay_boundary` time)."""
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(_OVERLAY, {"run_id": run_id, "as_of": as_of}).fetchall()
    items = {row["item_id"]: QueueItem.model_validate(row) for row in rows}
    dispositions = tuple(
        QueueDisposition.model_validate(row | {"recorded_at": row["disposed_at"]})
        for row in rows
        if row["disposition_id"] is not None
    )
    disposed = {item.item_id for item in dispositions}
    return QueueOverlay(
        run_id=run_id,
        as_of=as_of,
        open_items=tuple(item for item_id, item in items.items() if item_id not in disposed),
        dispositions=dispositions,
    )


def _publish_one(cursor: Cursor[Any], run_id: int, digest: str, draft: QueueItemDraft) -> int:
    """Reuse the identical item, else insert one linked to the latest of its key and outcome."""
    key_digest = None if draft.key is None else draft.key.digest()
    identity = (key_digest, draft.pair_identity, draft.outcome)
    stored = cursor.execute(_EXACT_ITEM, (*identity, digest)).fetchone()
    if stored is not None:
        item_id = int(stored[0])
    else:
        latest = cursor.execute(_LATEST_ITEM, identity).fetchone()
        inserted = cursor.execute(
            _INSERT_ITEM,
            (
                run_id,
                key_digest,
                None if draft.key is None else Jsonb(draft.key.model_dump(mode="json")),
                draft.pair_identity,
                draft.outcome,
                digest,
                draft.severity.value,
                draft.diagnostic,
                draft.routing_reason,
                None if draft.reason_code is None else draft.reason_code.value,
                Jsonb([ref.model_dump(mode="json") for ref in draft.source_refs]),
                None if latest is None else int(latest[0]),
            ),
        ).fetchone()
        assert inserted is not None
        item_id = int(inserted[0])
        cursor.executemany(
            _INSERT_INPUT,
            [(item_id, value, None, None) for value in draft.evidence_occurrence_ids]
            + [(item_id, None, value, None) for value in draft.evidence_interpretation_ids]
            + [(item_id, None, None, value) for value in draft.attempt_ids],
        )
    cursor.execute(_INSERT_MEMBERSHIP, (run_id, item_id))
    return item_id


def _input_sha256(draft: QueueItemDraft) -> str:
    """The hash of the routed payload and its sorted typed evidence ids."""
    document = draft.model_dump(mode="json")
    for name in ("attempt_ids", "evidence_interpretation_ids", "evidence_occurrence_ids"):
        document[name] = sorted(document[name])
    return canonical_sha256(document)


def _order(prepared: tuple[str, QueueItemDraft]) -> tuple[str, str, str, str]:
    """A deterministic publication order."""
    digest, draft = prepared
    key = "" if draft.key is None else draft.key.digest()
    return key, draft.pair_identity, draft.outcome, digest
