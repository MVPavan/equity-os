"""Atomic immutable queue publication on a caller-owned transaction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, LiteralString

from psycopg import Cursor
from psycopg.pq import TransactionStatus
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from fundamentals.compare.queue_overlay import (
    QueueOverlayCaptureExhaustedError,
    QueueOverlayReadError,
    capture_queue_overlay,
    read_queue_overlay,
)
from fundamentals.contracts.comparison import SourceRef
from fundamentals.contracts.review_queue import (
    QueueItem,
    QueueItemDraft,
)
from fundamentals.evidence.capture_intake import SURFACE_OF

__all__ = [
    "QueueOverlayCaptureExhaustedError",
    "QueueOverlayReadError",
    "QueuePublicationError",
    "capture_queue_overlay",
    "publish_queue_drafts",
    "read_queue_overlay",
]

_DIGEST_SCHEMA = "eqos.queue-item-input.v2"
_INPUT_KINDS: tuple[Literal["OCCURRENCE", "INTERPRETATION", "ATTEMPT"], ...] = (
    "OCCURRENCE",
    "INTERPRETATION",
    "ATTEMPT",
)

_RUN: LiteralString = "SELECT manifest FROM eqos.runs WHERE id=%s"
_OCCURRENCES: LiteralString = (
    "SELECT ri.occurrence_id AS id,o.first_seen_at AS provenance_time,"
    "c.source_id,c.surface,o.representation "
    "FROM eqos.run_inputs ri JOIN eqos.occurrences o ON o.id=ri.occurrence_id "
    "JOIN eqos.capture_refs c ON c.id=o.capture_ref_id "
    "WHERE ri.run_id=%s AND ri.input_kind='OCCURRENCE' AND ri.occurrence_id=ANY(%s)"
)
_INTERPRETATIONS: LiteralString = (
    "SELECT ri.interpretation_id AS id,i.recorded_at AS provenance_time,"
    "c.source_id,c.surface,i.representation "
    "FROM eqos.run_inputs ri JOIN eqos.interpretations i ON i.id=ri.interpretation_id "
    "JOIN eqos.capture_refs c ON c.id=i.capture_ref_id "
    "WHERE ri.run_id=%s AND ri.input_kind='INTERPRETATION' "
    "AND ri.interpretation_id=ANY(%s)"
)
_ATTEMPTS: LiteralString = (
    "SELECT ri.attempt_id AS id,a.attempted_at AS provenance_time,"
    "a.source_id,a.surface,a.representation "
    "FROM eqos.run_inputs ri JOIN eqos.acquisition_attempts a ON a.id=ri.attempt_id "
    "WHERE ri.run_id=%s AND ri.input_kind='ATTEMPT' AND ri.attempt_id=ANY(%s)"
)
_ITEM_COLUMNS: LiteralString = (
    "id,run_id,key_digest,measurement_key,pair_identity,outcome,input_sha256,severity,"
    "diagnostic,routing_reason,reason_code,source_refs,predecessor_item_id,recorded_at"
)
_EXACT_ITEM: LiteralString = (
    f"SELECT {_ITEM_COLUMNS} FROM eqos.queue_items "
    "WHERE key_digest IS NOT DISTINCT FROM %s AND pair_identity=%s AND outcome=%s "
    "AND input_sha256=%s"
)
_LATEST_ITEM: LiteralString = (
    "SELECT id FROM eqos.queue_items WHERE key_digest IS NOT DISTINCT FROM %s "
    "AND pair_identity=%s AND outcome=%s ORDER BY recorded_at DESC,id DESC LIMIT 1"
)
_INSERT_ITEM: LiteralString = (
    "INSERT INTO eqos.queue_items (run_id,key_digest,measurement_key,pair_identity,outcome,"
    "input_sha256,severity,diagnostic,routing_reason,reason_code,source_refs,"
    "predecessor_item_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    f"ON CONFLICT DO NOTHING RETURNING {_ITEM_COLUMNS}"
)
_INSERT_INPUT: LiteralString = (
    "INSERT INTO eqos.queue_item_inputs "
    "(item_id,occurrence_id,interpretation_id,attempt_id) VALUES (%s,%s,%s,%s)"
)
_STORED_INPUTS: LiteralString = (
    "SELECT occurrence_id,interpretation_id,attempt_id FROM eqos.queue_item_inputs "
    "WHERE item_id=%s ORDER BY id"
)
_INSERT_MEMBERSHIP: LiteralString = (
    "INSERT INTO eqos.queue_run_items (run_id,item_id) VALUES (%s,%s) "
    "ON CONFLICT (run_id,item_id) DO NOTHING"
)
_LOCK: LiteralString = "SELECT pg_advisory_xact_lock(%s)"


class QueuePublicationError(ValueError):
    """A queue draft, stored seal, or typed run input is invalid."""


class _Association(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["OCCURRENCE", "INTERPRETATION", "ATTEMPT"]
    evidence_id: int
    provenance_time: datetime
    source_id: str
    surface: str
    representation: str

    def document(self) -> dict[str, object]:
        """Return the tagged canonical evidence identity and authoritative clock."""
        clock_name = {
            "OCCURRENCE": "first_seen_at",
            "INTERPRETATION": "recorded_at",
            "ATTEMPT": "attempted_at",
        }[self.kind]
        return {
            "kind": self.kind,
            "id": self.evidence_id,
            "source_id": self.source_id,
            "surface": self.surface,
            "representation": self.representation,
            clock_name: _clock_text(self.provenance_time),
        }


class _VendorRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    source_id: str
    surface: str
    representation: Literal["HTML", "JSON"]


class _RoutingScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    sources: tuple[str, ...]
    vendor_sources: tuple[_VendorRoute, ...] = ()


class _PreparedDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft: QueueItemDraft
    key_digest: str | None
    measurement_key: dict[str, Any] | None
    source_refs: tuple[dict[str, Any], ...]
    associations: tuple[_Association, ...]
    input_sha256: str
    base_canonical: str
    lock_key: int


def publish_queue_drafts(
    cursor: Cursor[Any],
    *,
    run_id: int,
    drafts: Sequence[QueueItemDraft],
) -> tuple[QueueItem, ...]:
    """Create or exactly reuse sealed queue items inside the caller's transaction."""
    _require_transaction(cursor)
    _positive_run_id(run_id)
    if not drafts:
        return ()
    with cursor.connection.cursor(row_factory=dict_row) as database:
        run = database.execute(_RUN, (run_id,)).fetchone()
        if run is None:
            raise QueuePublicationError(f"queue run {run_id} is not stored")
        evidence = _load_run_evidence(database, run_id, drafts)
        prepared = tuple(_prepare(draft, evidence, run["manifest"]) for draft in drafts)
        for lock_key in sorted({item.lock_key for item in prepared}):
            database.execute(_LOCK, (lock_key,))
        stored = tuple(
            _publish_one(database, run_id, item)
            for item in sorted(prepared, key=lambda item: (item.base_canonical, item.input_sha256))
        )
    return stored


def _load_run_evidence(
    cursor: Cursor[DictRow],
    run_id: int,
    drafts: Sequence[QueueItemDraft],
) -> dict[tuple[str, int], _Association]:
    requested = {
        "OCCURRENCE": {
            evidence_id for draft in drafts for evidence_id in draft.evidence_occurrence_ids
        },
        "INTERPRETATION": {
            evidence_id for draft in drafts for evidence_id in draft.evidence_interpretation_ids
        },
        "ATTEMPT": {evidence_id for draft in drafts for evidence_id in draft.attempt_ids},
    }
    queries = {
        "OCCURRENCE": _OCCURRENCES,
        "INTERPRETATION": _INTERPRETATIONS,
        "ATTEMPT": _ATTEMPTS,
    }
    loaded: dict[tuple[str, int], _Association] = {}
    for kind in _INPUT_KINDS:
        evidence_ids = requested[kind]
        if not evidence_ids:
            continue
        rows = cursor.execute(queries[kind], (run_id, list(evidence_ids))).fetchall()
        for row in rows:
            association = _Association(
                kind=kind,
                evidence_id=int(row["id"]),
                provenance_time=row["provenance_time"],
                source_id=row["source_id"],
                surface=row["surface"],
                representation=row["representation"],
            )
            loaded[(kind, association.evidence_id)] = association
        missing = evidence_ids - {
            evidence_id for loaded_kind, evidence_id in loaded if loaded_kind == kind
        }
        if missing:
            raise QueuePublicationError(
                f"queue run {run_id} lacks typed {kind} inputs {sorted(missing)}"
            )
    return loaded


def _prepare(
    draft: QueueItemDraft,
    evidence: dict[tuple[str, int], _Association],
    manifest: object,
) -> _PreparedDraft:
    key_digest = None if draft.key is None else draft.key.digest()
    measurement_key = None if draft.key is None else draft.key.model_dump(mode="json")
    source_refs = tuple(
        sorted(
            (ref.model_dump(mode="json") for ref in draft.source_refs),
            key=_canonical_json,
        )
    )
    associations = tuple(
        sorted(
            (
                *(
                    evidence[("OCCURRENCE", evidence_id)]
                    for evidence_id in draft.evidence_occurrence_ids
                ),
                *(
                    evidence[("INTERPRETATION", evidence_id)]
                    for evidence_id in draft.evidence_interpretation_ids
                ),
                *(evidence[("ATTEMPT", evidence_id)] for evidence_id in draft.attempt_ids),
            ),
            key=lambda item: (item.kind, item.evidence_id),
        )
    )
    _validate_provenance(draft, associations, manifest)
    base = {
        "key_digest": key_digest,
        "pair_identity": draft.pair_identity,
        "outcome": draft.outcome,
    }
    base_canonical = _canonical_json(base)
    document = {
        "schema": _DIGEST_SCHEMA,
        "base": {
            **base,
            "measurement_key": measurement_key,
        },
        "payload": {
            "severity": draft.severity.value,
            "diagnostic": draft.diagnostic,
            "routing_reason": draft.routing_reason,
            "reason_code": None if draft.reason_code is None else draft.reason_code.value,
            "source_refs": source_refs,
        },
        "inputs": [association.document() for association in associations],
    }
    return _PreparedDraft(
        draft=draft,
        key_digest=key_digest,
        measurement_key=measurement_key,
        source_refs=source_refs,
        associations=associations,
        input_sha256=_sha256(document),
        base_canonical=base_canonical,
        lock_key=int.from_bytes(
            hashlib.sha256(base_canonical.encode()).digest()[:8],
            byteorder="big",
            signed=True,
        ),
    )


def _validate_provenance(
    draft: QueueItemDraft,
    associations: tuple[_Association, ...],
    manifest: object,
) -> None:
    scope = _routing_scope(manifest)
    actual = {
        (association.source_id, association.surface, association.representation)
        for association in associations
    }
    for source_id, surface, representation in actual:
        if not _actual_source_is_declared(source_id, surface, representation, scope):
            raise QueuePublicationError(
                "queue evidence source/surface/representation is outside the stored run scope"
            )
        if not any(
            _reference_matches(ref, source_id, surface, representation) for ref in draft.source_refs
        ):
            raise QueuePublicationError(
                "queue evidence provenance has no matching draft source reference"
            )
    for ref in draft.source_refs:
        if any(
            _reference_matches(ref, source_id, surface, representation)
            for source_id, surface, representation in actual
        ):
            continue
        if not _missing_reference_is_declared(ref, scope):
            raise QueuePublicationError(
                "queue source reference has no evidence or declared missing-side provenance"
            )


def _routing_scope(manifest: object) -> _RoutingScope | None:
    if not isinstance(manifest, Mapping):
        raise QueuePublicationError("stored queue run manifest is not a routing document")
    document = manifest.get("scope")
    if document is None:
        return None
    try:
        return _RoutingScope.model_validate(document)
    except ValidationError as error:
        raise QueuePublicationError("stored queue run routing scope is invalid") from error


def _actual_source_is_declared(
    source_id: str,
    surface: str,
    representation: str,
    scope: _RoutingScope | None,
) -> bool:
    if representation in {"HTML", "JSON"}:
        return scope is not None and (source_id, surface, representation) in {
            (route.source_id, route.surface, route.representation) for route in scope.vendor_sources
        }
    if representation not in {"XBRL", "PDF"}:
        return False
    return scope is None or surface in scope.sources


def _reference_matches(
    ref: SourceRef,
    source_id: str,
    surface: str,
    representation: str,
) -> bool:
    if ref.representation.value != representation:
        return False
    if ref.source_id is None:
        return representation in {"XBRL", "PDF"}
    return (ref.source_id, ref.surface) == (source_id, surface)


def _missing_reference_is_declared(ref: SourceRef, scope: _RoutingScope | None) -> bool:
    if ref.representation.value in {"HTML", "JSON"}:
        return scope is not None and (
            ref.source_id,
            ref.surface,
            ref.representation.value,
        ) in {
            (route.source_id, route.surface, route.representation) for route in scope.vendor_sources
        }
    if ref.source_id is not None:
        return False
    expected_surface = SURFACE_OF.get(ref.representation)
    return scope is None or (
        expected_surface is not None and expected_surface.value in scope.sources
    )


def _publish_one(
    cursor: Cursor[DictRow],
    run_id: int,
    prepared: _PreparedDraft,
) -> QueueItem:
    identity = (
        prepared.key_digest,
        prepared.draft.pair_identity,
        prepared.draft.outcome,
    )
    stored = cursor.execute(_EXACT_ITEM, (*identity, prepared.input_sha256)).fetchone()
    if stored is None:
        latest = cursor.execute(_LATEST_ITEM, identity).fetchone()
        predecessor = None if latest is None else int(latest["id"])
        stored = cursor.execute(
            _INSERT_ITEM,
            (
                run_id,
                prepared.key_digest,
                None if prepared.measurement_key is None else Jsonb(prepared.measurement_key),
                prepared.draft.pair_identity,
                prepared.draft.outcome,
                prepared.input_sha256,
                prepared.draft.severity.value,
                prepared.draft.diagnostic,
                prepared.draft.routing_reason,
                None if prepared.draft.reason_code is None else prepared.draft.reason_code.value,
                Jsonb(list(prepared.source_refs)),
                predecessor,
            ),
        ).fetchone()
        if stored is not None:
            _insert_associations(cursor, int(stored["id"]), prepared.associations)
        else:
            stored = cursor.execute(_EXACT_ITEM, (*identity, prepared.input_sha256)).fetchone()
    if stored is None:
        raise QueuePublicationError("queue item conflict did not yield a stored item")
    item = _verified_item(cursor, stored, prepared)
    assert item.item_id is not None
    cursor.execute(_INSERT_MEMBERSHIP, (run_id, item.item_id))
    return item


def _insert_associations(
    cursor: Cursor[DictRow],
    item_id: int,
    associations: tuple[_Association, ...],
) -> None:
    cursor.executemany(
        _INSERT_INPUT,
        [
            (
                item_id,
                association.evidence_id if association.kind == "OCCURRENCE" else None,
                association.evidence_id if association.kind == "INTERPRETATION" else None,
                association.evidence_id if association.kind == "ATTEMPT" else None,
            )
            for association in associations
        ],
    )


def _verified_item(
    cursor: Cursor[DictRow],
    stored: DictRow,
    prepared: _PreparedDraft,
) -> QueueItem:
    expected_payload = {
        "key_digest": prepared.key_digest,
        "measurement_key": prepared.measurement_key,
        "pair_identity": prepared.draft.pair_identity,
        "outcome": prepared.draft.outcome,
        "input_sha256": prepared.input_sha256,
        "severity": prepared.draft.severity.value,
        "diagnostic": prepared.draft.diagnostic,
        "routing_reason": prepared.draft.routing_reason,
        "reason_code": (
            None if prepared.draft.reason_code is None else prepared.draft.reason_code.value
        ),
        "source_refs": list(prepared.source_refs),
    }
    if any(stored[name] != value for name, value in expected_payload.items()):
        raise QueuePublicationError("stored queue item differs from its sealed input digest")
    rows = cursor.execute(_STORED_INPUTS, (stored["id"],)).fetchall()
    actual_inputs = {
        (kind, int(row[column]))
        for row in rows
        for kind, column in (
            ("OCCURRENCE", "occurrence_id"),
            ("INTERPRETATION", "interpretation_id"),
            ("ATTEMPT", "attempt_id"),
        )
        if row[column] is not None
    }
    expected_inputs = {
        (association.kind, association.evidence_id) for association in prepared.associations
    }
    if actual_inputs != expected_inputs or len(rows) != len(expected_inputs):
        raise QueuePublicationError("stored queue item inputs differ from their sealed digest")
    return _item_of(stored, actual_inputs)


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


def _ids_of(inputs: set[tuple[str, int]], kind: str) -> tuple[int, ...]:
    return tuple(sorted(evidence_id for input_kind, evidence_id in inputs if input_kind == kind))


def _clock_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise QueuePublicationError("queue evidence provenance clock is not timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _require_transaction(cursor: Cursor[Any]) -> None:
    if cursor.connection.info.transaction_status != TransactionStatus.INTRANS:
        raise QueuePublicationError("queue publication requires an active caller transaction")


def _positive_run_id(run_id: int) -> None:
    if isinstance(run_id, bool) or run_id <= 0:
        raise ValueError("queue run id is a positive integer")
