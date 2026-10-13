"""Durably sealed queue-overlay capture and authenticated closure replay."""

from __future__ import annotations

from datetime import datetime
from typing import Any, LiteralString

from psycopg import Connection, Cursor
from psycopg.errors import SerializationFailure
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator

from fundamentals.compare.approval_receipts import (
    ApprovalRefusedError,
    reload_verified_receipt,
)
from fundamentals.contracts.review_queue import (
    ApprovalDecision,
    ApprovalSubject,
    QueueClosureFailure,
    QueueDisposition,
    QueueItem,
    QueueOverlay,
    QueueRunMembership,
)
from fundamentals.pg.settings import MIGRATOR_ROLE_NAME

MAX_CAPTURE_ATTEMPTS = 3

_SET_REPEATABLE_READ: LiteralString = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
_SET_READ_ONLY: LiteralString = "SET TRANSACTION READ ONLY"
_CAPTURE_SNAPSHOT: LiteralString = (
    "SELECT id AS snapshot_id,run_id,as_of,recorded_position,membership_ids,item_ids,"
    "disposition_candidate_ids FROM eqos.capture_queue_overlay_snapshot(%s)"
)
_READ_SNAPSHOT: LiteralString = (
    "SELECT id AS snapshot_id,run_id,as_of,recorded_position,membership_ids,item_ids,"
    "disposition_candidate_ids FROM eqos.queue_overlay_snapshots "
    "WHERE run_id=%s AND as_of=%s AND recorded_position=%s"
)
_ITEM_COLUMNS: LiteralString = (
    "qi.id,qi.run_id,qi.key_digest,qi.measurement_key,qi.pair_identity,qi.outcome,"
    "qi.input_sha256,qi.severity,qi.diagnostic,qi.routing_reason,qi.reason_code,"
    "qi.source_refs,qi.predecessor_item_id,qi.recorded_at"
)
_SEALED_ITEMS: LiteralString = (
    f"SELECT {_ITEM_COLUMNS},qri.id AS membership_id,"
    "qri.run_id AS membership_run_id,qri.recorded_at AS membership_recorded_at "
    "FROM eqos.queue_run_items qri JOIN eqos.queue_items qi ON qi.id=qri.item_id "
    "WHERE qri.id=ANY(%s) ORDER BY qi.id"
)
_SEALED_INPUTS: LiteralString = (
    "SELECT item_id,occurrence_id,interpretation_id,attempt_id "
    "FROM eqos.queue_item_inputs WHERE item_id=ANY(%s) ORDER BY item_id,id"
)
_SEALED_CANDIDATES: LiteralString = (
    "SELECT qd.id,qd.item_id,qd.proposal_id,qd.approval_receipt_id,qd.kind,qd.reason,"
    "qd.proposer,qd.decider,qd.evidence_ref,qd.explained_amount,qd.amount_trace_id,"
    "qd.producer_database_identity,qd.recorded_at,"
    "p.item_id AS proposal_item_id,p.kind AS proposal_kind,p.reason AS proposal_reason,"
    "p.proposer AS proposal_proposer,p.evidence_ref AS proposal_evidence_ref,"
    "p.explained_amount AS proposal_explained_amount,"
    "p.amount_trace_id AS proposal_amount_trace_id,p.recorded_at AS proposal_recorded_at,"
    "ar.recorded_at AS receipt_recorded_at,e.recorded_at AS evidence_recorded_at "
    "FROM eqos.queue_dispositions qd "
    "JOIN eqos.queue_disposition_proposals p ON p.id=qd.proposal_id "
    "JOIN eqos.approval_receipts ar ON ar.id=qd.approval_receipt_id "
    "JOIN eqos.approval_review_evidence e ON e.id=ar.review_evidence_id "
    "WHERE qd.id=ANY(%s) ORDER BY qd.id"
)


class QueueOverlayReadError(ValueError):
    """A requested durable queue visibility seal cannot be loaded exactly."""


class QueueOverlayCaptureExhaustedError(RuntimeError):
    """All bounded Repeatable Read capture transactions hit serialization failure."""


class _Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: PositiveInt
    run_id: PositiveInt
    as_of: datetime
    recorded_position: int
    membership_ids: tuple[PositiveInt, ...]
    item_ids: tuple[PositiveInt, ...]
    disposition_candidate_ids: tuple[PositiveInt, ...]

    @field_validator("as_of")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("queue overlay snapshot time is timezone-aware")
        return value


def capture_queue_overlay(pool: ConnectionPool, *, run_id: int) -> QueueOverlay:
    """Commit and return one database-derived durable visibility seal."""
    _positive_run_id(run_id)
    last_failure: SerializationFailure | None = None
    for _ in range(MAX_CAPTURE_ATTEMPTS):
        try:
            return _capture_once(pool, run_id)
        except SerializationFailure as error:
            last_failure = error
    assert last_failure is not None
    raise QueueOverlayCaptureExhaustedError(
        f"queue overlay capture hit {MAX_CAPTURE_ATTEMPTS} serialization failures"
    ) from last_failure


def _capture_once(pool: ConnectionPool, run_id: int) -> QueueOverlay:
    with pool.connection() as connection:
        with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(_SET_REPEATABLE_READ)
            rows = cursor.execute(_CAPTURE_SNAPSHOT, (run_id,)).fetchall()
            if len(rows) != 1:
                raise QueueOverlayReadError("queue capture did not return exactly one snapshot")
            snapshot = _Snapshot.model_validate(rows[0])
            overlay = _read_sealed_overlay(connection, cursor, snapshot)
    return overlay


def read_queue_overlay(
    pool: ConnectionPool,
    *,
    run_id: int,
    as_of: datetime,
    recorded_position: int,
) -> QueueOverlay:
    """Re-read only the immutable IDs named by an exact captured visibility triple."""
    _positive_run_id(run_id)
    if as_of.tzinfo is None or isinstance(recorded_position, bool) or recorded_position < 0:
        raise QueueOverlayReadError("queue overlay requires an aware, non-negative position")
    with pool.connection() as connection:
        with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(_SET_READ_ONLY)
            rows = cursor.execute(_READ_SNAPSHOT, (run_id, as_of, recorded_position)).fetchall()
            if len(rows) != 1:
                raise QueueOverlayReadError("queue overlay position/triple was not captured")
            overlay = _read_sealed_overlay(connection, cursor, _Snapshot.model_validate(rows[0]))
    return overlay


def _read_sealed_overlay(
    connection: Connection[Any],
    cursor: Cursor[DictRow],
    snapshot: _Snapshot,
) -> QueueOverlay:
    rows = (
        cursor.execute(_SEALED_ITEMS, (list(snapshot.membership_ids),)).fetchall()
        if snapshot.membership_ids
        else []
    )
    _verify_membership_rows(snapshot, rows)
    inputs_by_item = _load_inputs(cursor, snapshot.item_ids)
    items = tuple(_item_of(row, inputs_by_item[int(row["id"])]) for row in rows)
    candidate_rows = (
        cursor.execute(_SEALED_CANDIDATES, (list(snapshot.disposition_candidate_ids),)).fetchall()
        if snapshot.disposition_candidate_ids
        else []
    )
    if tuple(int(row["id"]) for row in candidate_rows) != snapshot.disposition_candidate_ids:
        raise QueueOverlayReadError("sealed queue disposition candidate set is unavailable")

    accepted: list[QueueDisposition] = []
    failures: list[QueueClosureFailure] = []
    for row in candidate_rows:
        if int(row["item_id"]) not in snapshot.item_ids:
            raise QueueOverlayReadError("sealed disposition names an unsealed queue item")
        failure = _candidate_failure(connection, row, snapshot)
        if failure is None:
            accepted.append(_disposition_of(row))
        else:
            failures.append(
                QueueClosureFailure(
                    disposition_id=row["id"],
                    item_id=row["item_id"],
                    reason=failure,
                )
            )

    closed = {disposition.item_id for disposition in accepted}
    memberships = tuple(
        QueueRunMembership(
            run_id=snapshot.run_id,
            item_id=row["id"],
            origin_run_id=row["run_id"],
            recorded_at=row["membership_recorded_at"],
        )
        for row in rows
    )
    return QueueOverlay(
        run_id=snapshot.run_id,
        recorded_position=snapshot.recorded_position,
        as_of=snapshot.as_of,
        open_items=tuple(item for item in items if item.item_id not in closed),
        accepted_dispositions=tuple(accepted),
        memberships=memberships,
        closure_failures=tuple(failures),
    )


def _verify_membership_rows(snapshot: _Snapshot, rows: list[DictRow]) -> None:
    if tuple(sorted(int(row["membership_id"]) for row in rows)) != snapshot.membership_ids:
        raise QueueOverlayReadError("sealed queue membership set is unavailable")
    if tuple(sorted(int(row["id"]) for row in rows)) != snapshot.item_ids:
        raise QueueOverlayReadError("sealed queue item set differs from membership")
    if any(
        row["membership_run_id"] != snapshot.run_id
        or row["membership_recorded_at"] > snapshot.as_of
        or row["recorded_at"] > snapshot.as_of
        for row in rows
    ):
        raise QueueOverlayReadError("sealed queue membership is outside its capture position")


def _load_inputs(
    cursor: Cursor[DictRow], item_ids: tuple[PositiveInt, ...]
) -> dict[int, set[tuple[str, int]]]:
    inputs: dict[int, set[tuple[str, int]]] = {int(item_id): set() for item_id in item_ids}
    if not item_ids:
        return inputs
    for row in cursor.execute(_SEALED_INPUTS, (list(item_ids),)).fetchall():
        item_id = int(row["item_id"])
        if item_id not in inputs:
            raise QueueOverlayReadError("queue input belongs to an unsealed item")
        for kind, column in (
            ("OCCURRENCE", "occurrence_id"),
            ("INTERPRETATION", "interpretation_id"),
            ("ATTEMPT", "attempt_id"),
        ):
            if row[column] is not None:
                inputs[item_id].add((kind, int(row[column])))
    return inputs


def _candidate_failure(
    connection: Connection[Any], row: DictRow, snapshot: _Snapshot
) -> str | None:
    if any(
        row[column] > snapshot.as_of
        for column in (
            "proposal_recorded_at",
            "evidence_recorded_at",
            "receipt_recorded_at",
            "recorded_at",
        )
    ):
        return "closure proof was recorded after the sealed overlay position"
    if row["producer_database_identity"] != MIGRATOR_ROLE_NAME:
        return "final disposition lacks the protected database producer"
    if (
        row["proposal_item_id"] != row["item_id"]
        or row["proposal_kind"] != row["kind"]
        or row["proposal_reason"] != row["reason"]
        or row["proposal_proposer"] != row["proposer"]
        or row["proposal_evidence_ref"] != row["evidence_ref"]
        or row["proposal_explained_amount"] != row["explained_amount"]
        or row["proposal_amount_trace_id"] != row["amount_trace_id"]
    ):
        return "final disposition differs from its sealed proposal"
    try:
        verified = reload_verified_receipt(connection, int(row["approval_receipt_id"]))
    except ApprovalRefusedError as error:
        return str(error)
    receipt = verified.receipt
    if (
        receipt.decision is not ApprovalDecision.ACCEPT
        or receipt.subject_kind is not ApprovalSubject.QUEUE_DISPOSITION
        or receipt.receipt_id != row["approval_receipt_id"]
        or receipt.subject_id != row["item_id"]
        or receipt.proposal_id != row["proposal_id"]
        or receipt.decider != row["decider"]
    ):
        return "final disposition differs from its verified ACCEPT receipt"
    return None


def _item_of(stored: DictRow, inputs: set[tuple[str, int]]) -> QueueItem:
    return QueueItem.model_validate(
        {
            "item_id": stored["id"],
            "run_id": stored["run_id"],
            "key": stored["measurement_key"],
            "pair_identity": stored["pair_identity"],
            "outcome": stored["outcome"],
            "input_sha256": stored["input_sha256"],
            "severity": stored["severity"],
            "diagnostic": stored["diagnostic"],
            "routing_reason": stored["routing_reason"],
            "reason_code": stored["reason_code"],
            "source_refs": stored["source_refs"],
            "attempt_ids": _ids_of(inputs, "ATTEMPT"),
            "evidence_interpretation_ids": _ids_of(inputs, "INTERPRETATION"),
            "evidence_occurrence_ids": _ids_of(inputs, "OCCURRENCE"),
            "predecessor_item_id": stored["predecessor_item_id"],
            "recorded_at": stored["recorded_at"],
        }
    )


def _disposition_of(row: DictRow) -> QueueDisposition:
    return QueueDisposition.model_validate(
        {
            "disposition_id": row["id"],
            "item_id": row["item_id"],
            "kind": row["kind"],
            "reason": row["reason"],
            "proposer": row["proposer"],
            "decider": row["decider"],
            "evidence_ref": row["evidence_ref"],
            "explained_amount": row["explained_amount"],
            "amount_trace_id": row["amount_trace_id"],
            "approval_receipt_id": row["approval_receipt_id"],
            "recorded_at": row["recorded_at"],
        }
    )


def _ids_of(inputs: set[tuple[str, int]], kind: str) -> tuple[int, ...]:
    return tuple(sorted(evidence_id for input_kind, evidence_id in inputs if input_kind == kind))


def _positive_run_id(run_id: int) -> None:
    if isinstance(run_id, bool) or run_id <= 0:
        raise ValueError("queue run id is a positive integer")
