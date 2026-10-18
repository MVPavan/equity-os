"""Reconciliation, cutover, frozen-window rollback and routing (plan D2, design decision 7).

A store's state is its latest ``eqos.fact_store_events`` row. ``transition`` moves a manifest's
whole store set in one SERIALIZABLE transaction, after the gate, or refuses and writes nothing.
Rollback exists only inside the cutover window (``CUTOVER_FROZEN``); after reopen, recovery is
verified backups plus forward repair. The reconciliation report reads imported rows only (by
legacy origin), so later native writes never change its bytes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import structlog
import yaml
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import TRANSLATION_VERSION, translation_sha256
from fundamentals.compare.queue import lock_queue
from fundamentals.compare.run_models import DatabaseIdentity
from fundamentals.contracts.fact import Fact
from fundamentals.pg.approvals import (
    GatedOperation,
    GateRefusal,
    GateRefusedError,
    authorize,
    current_database,
)
from fundamentals.pg.legacy_import import (
    EvidenceBinding,
    ImportCheck,
    load_manifest,
    origin_id_for,
    store_state,
    verify_import,
)
from fundamentals.pg.settings import PgSettings
from fundamentals.store.fact_store import (
    CanonicalSelection,
    FactStore,
    FactStoreLike,
    effective_revision,
)
from fundamentals.store.pg_fact_store import FactStoreFrozenError, PgFactStore
from fundamentals.store.snapshot_store import SnapshotStore

_LEGACY_STORES = "SELECT store_id FROM eqos.fact_stores WHERE kind = 'LEGACY_SQLITE' ORDER BY 1"
_FINGERPRINT = "SELECT file_sha256 FROM eqos.fact_stores WHERE store_id = %s"
_BINDINGS = """
SELECT DISTINCT b.file_sha256, b.capture_ref_id, c.blob_sha256
FROM eqos.legacy_evidence_bindings b JOIN eqos.capture_refs c ON c.id = b.capture_ref_id
WHERE b.target_store = %s ORDER BY b.file_sha256
"""
_LEGACY_ROWS = """
SELECT handle, content_identity, value_hash, knowledge_time, fact_json
FROM eqos.fact_rows WHERE target_store = %(s)s AND origin = %(s)s
"""
_LEGACY_SELECTIONS = """
SELECT handle AS selection_id, content_identity, row_handle AS row_id, sequence,
    predecessor_handle AS predecessor_id, selected_at, reason, legacy_baseline, selection_sha256
FROM eqos.fact_selections WHERE target_store = %(s)s AND origin = %(s)s
ORDER BY content_identity, sequence
"""
_LATEST = (
    "SELECT state, operation_id, last_row_handle, last_selection_handle, approval_sha256 "
    "FROM eqos.fact_store_events WHERE store_id = %s ORDER BY id DESC LIMIT 1"
)
_LAST_HANDLES = (
    "SELECT (SELECT max(handle) FROM eqos.fact_rows WHERE target_store = %(s)s), "
    "(SELECT max(handle) FROM eqos.fact_selections WHERE target_store = %(s)s)"
)
_INSERT_EVENT = """
INSERT INTO eqos.fact_store_events (store_id, operation_id, state, approval_sha256,
    owner_record_sha256, last_row_handle, last_selection_handle, recorded_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, eqos.store_now())
"""
_TICK = timedelta(microseconds=1)

_log = structlog.get_logger("fundamentals.pg.cutover")


class FactStoreState(StrEnum):
    """A fact store's state (design decision 7)."""

    IMPORTED = "IMPORTED"
    CUTOVER_FROZEN = "CUTOVER_FROZEN"
    OPEN = "OPEN"
    ROLLED_BACK = "ROLLED_BACK"


LEGAL_COMMANDS: Mapping[FactStoreState, str] = {
    FactStoreState.IMPORTED: (
        "legacy reconcile, then legacy cutover; to abandon: restore legacy write permission "
        "(once the legacy file changes cutover is refused FINGERPRINT_CHANGED; re-import with "
        "new_import: true)"
    ),
    FactStoreState.CUTOVER_FROZEN: (
        "legacy reopen (PostgreSQL authoritative) or legacy rollback (SQLite authoritative)"
    ),
    FactStoreState.ROLLED_BACK: (
        "legacy reconcile, then legacy cutover (refused FINGERPRINT_CHANGED after any SQLite "
        "write; then abandon as from IMPORTED)"
    ),
    FactStoreState.OPEN: "none; recovery is verified backups plus forward repair",
}

# Operation -> (states it may leave, state it enters).
_RULES: Mapping[GatedOperation, tuple[frozenset[FactStoreState], FactStoreState]] = {
    GatedOperation.CUTOVER: (
        frozenset({FactStoreState.IMPORTED, FactStoreState.ROLLED_BACK}),
        FactStoreState.CUTOVER_FROZEN,
    ),
    GatedOperation.REOPEN: (frozenset({FactStoreState.CUTOVER_FROZEN}), FactStoreState.OPEN),
    GatedOperation.ROLLBACK: (
        frozenset({FactStoreState.CUTOVER_FROZEN}),
        FactStoreState.ROLLED_BACK,
    ),
}


class TransitionRefusal(StrEnum):
    """Why a transition refused."""

    ILLEGAL_STATE = "ILLEGAL_STATE"
    ROLLBACK_WINDOW_CLOSED = "ROLLBACK_WINDOW_CLOSED"
    FINGERPRINT_CHANGED = "FINGERPRINT_CHANGED"
    ROWS_BEYOND_MARKER = "ROWS_BEYOND_MARKER"
    RECONCILIATION_DRIFTED = "RECONCILIATION_DRIFTED"
    NOT_THE_CUTOVER_REPORT = "NOT_THE_CUTOVER_REPORT"


class TransitionRefusedError(Exception):
    """A transition refused; no store switched."""

    def __init__(self, reason: TransitionRefusal) -> None:
        """Carry the refusal reason."""
        super().__init__(reason.value)
        self.reason = reason


class FactStoreRequiredError(Exception):
    """No writable fact store: the config names no ``OPEN`` PostgreSQL store and no SQLite one."""

    def __init__(self, store_id: str | None) -> None:
        """Name the store that could not be routed."""
        super().__init__(f"fact store {store_id} needs an OPEN PostgreSQL store or a store_db")
        self.store_id = store_id


class CutoffCheck(BaseModel):
    """SQLite and PostgreSQL canonical rows at one reconcile cutoff."""

    model_config = ConfigDict(frozen=True)

    cutoff: datetime
    rows: int
    rows_sha256: str
    equal: bool


class StoreReconciliation(BaseModel):
    """One imported store against its legacy file."""

    model_config = ConfigDict(frozen=True)

    label: str
    store_id: str
    check: ImportCheck
    fingerprint_before: str
    fingerprint_after: str
    bindings: tuple[EvidenceBinding, ...]
    cutoffs: tuple[CutoffCheck, ...]


class ReconciliationReport(BaseModel):
    """The deterministic, approvable reconciliation: no wall-clock time, no native rows."""

    model_config = ConfigDict(frozen=True)

    database: DatabaseIdentity
    translation_version: str
    translation_sha256: str
    legacy_stores: tuple[str, ...]
    stores: tuple[StoreReconciliation, ...]

    def equal(self) -> bool:
        """Every store matches its file at every cutoff."""
        return all(check.equal for store in self.stores for check in store.cutoffs)

    def to_yaml(self) -> bytes:
        """The report's canonical bytes."""
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=True).encode()


def reconcile(
    manifest: Path, *, root: Path, pool: ConnectionPool, settings: PgSettings
) -> ReconciliationReport:
    """Reconcile every manifest store against its legacy file."""
    with pool.connection() as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return _reconcile(manifest, root=root, conn=conn, settings=settings)


def transition(
    op: GatedOperation,
    manifest: Path,
    *,
    report_path: Path,
    owner_path: Path | None,
    pool: ConnectionPool,
    settings: PgSettings,
    root: Path,
) -> UUID:
    """Move the manifest's whole store set by ``op``, or refuse and switch nothing."""
    files = load_manifest(manifest).files
    stores = [origin_id_for(file.sha256) for file in files]
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        payload = authorize(conn, op, approval_path=report_path, owner_path=owner_path)
        lock_queue(cursor)
        latest = {store: cursor.execute(_LATEST, (store,)).fetchone() for store in stores}
        if op not in _RULES:
            raise TransitionRefusedError(TransitionRefusal.ILLEGAL_STATE)
        sources, target = _RULES[op]
        if all(event is not None and event[0] == target for event in latest.values()):
            existing = latest[stores[0]]
            assert existing is not None
            return UUID(str(existing[1]))
        for event in latest.values():
            state = None if event is None else event[0]
            if op is GatedOperation.ROLLBACK and state == FactStoreState.OPEN:
                raise TransitionRefusedError(TransitionRefusal.ROLLBACK_WINDOW_CLOSED)
            if state not in sources:
                raise TransitionRefusedError(TransitionRefusal.ILLEGAL_STATE)
        if op is not GatedOperation.CUTOVER:
            _check_cutover_report(stores, latest, payload)
        if op is not GatedOperation.REOPEN:
            for file, store in zip(files, stores, strict=True):
                found = cursor.execute(_FINGERPRINT, (store,)).fetchone()
                if found is None or _sha((root / file.path).read_bytes()) != found[0]:
                    raise TransitionRefusedError(TransitionRefusal.FINGERPRINT_CHANGED)
        if op is GatedOperation.CUTOVER:
            report = _reconcile(manifest, root=root, conn=conn, settings=settings)
            if report.to_yaml() != payload:
                raise GateRefusedError(GateRefusal.APPROVAL_STALE)
            if not report.equal():
                raise TransitionRefusedError(TransitionRefusal.RECONCILIATION_DRIFTED)
        if op is GatedOperation.ROLLBACK and any(
            _last_handles(cursor, store) != tuple(event[2:4])
            for store, event in latest.items()
            if event is not None
        ):
            raise TransitionRefusedError(TransitionRefusal.ROWS_BEYOND_MARKER)
        operation = uuid.uuid4()
        owner_sha = _sha(owner_path.read_bytes()) if owner_path is not None else None
        for store in stores:
            marker = _last_handles(cursor, store) if op is GatedOperation.CUTOVER else (None, None)
            cursor.execute(
                _INSERT_EVENT, (store, operation, target.value, _sha(payload), owner_sha, *marker)
            )
    _log.info("fact_store_transition", op=op.value, operation_id=str(operation), stores=stores)
    return operation


def store_status(pool: ConnectionPool, store_ids: Sequence[str]) -> Mapping[str, FactStoreState]:
    """Each store's state; stores with no event are absent."""
    with pool.connection() as conn:
        states = {store: store_state(conn, store) for store in store_ids}
    return {store: FactStoreState(state) for store, state in states.items() if state is not None}


def open_fact_store(
    store_id: str | None, store_db_path: str | None, *, pool_factory: Callable[[], ConnectionPool]
) -> FactStoreLike:
    """The authoritative store: SQLite without a store id or after rollback, PostgreSQL when
    ``OPEN``; refused while frozen or when SQLite is needed but not configured. The pool belongs
    to ``pool_factory``'s owner."""
    if store_id is not None:
        pool = pool_factory()
        with pool.connection() as conn:
            state = store_state(conn, store_id)
        if state == FactStoreState.OPEN:
            return PgFactStore(pool, store_id)
        if state != FactStoreState.ROLLED_BACK:
            raise FactStoreFrozenError(state)
    if store_db_path is None:
        raise FactStoreRequiredError(store_id)
    return FactStore(store_db_path)


def _reconcile(
    manifest_path: Path, *, root: Path, conn: psycopg.Connection[Any], settings: PgSettings
) -> ReconciliationReport:
    """The report, read on ``conn``."""
    manifest = load_manifest(manifest_path)
    snapshots = SnapshotStore(root / manifest.snapshot_root)
    stores = []
    for file in manifest.files:
        path, store = root / file.path, origin_id_for(file.sha256)
        before = _sha(path.read_bytes())
        check = verify_import(conn, store, path, snapshots=snapshots)
        with conn.cursor(row_factory=dict_row) as cursor:
            bindings = cursor.execute(_BINDINGS, (store,)).fetchall()
        cutoffs = _cutoff_checks(conn, store, path)
        stores.append(
            StoreReconciliation(
                label=file.label,
                store_id=store,
                check=check,
                fingerprint_before=before,
                fingerprint_after=_sha(path.read_bytes()),
                bindings=tuple(EvidenceBinding.model_validate(row) for row in bindings),
                cutoffs=cutoffs,
            )
        )
    return ReconciliationReport(
        database=DatabaseIdentity(
            host=settings.host, port=settings.port, name=current_database(conn)
        ),
        translation_version=TRANSLATION_VERSION,
        translation_sha256=translation_sha256(),
        legacy_stores=tuple(row[0] for row in conn.execute(_LEGACY_STORES).fetchall()),
        stores=tuple(stores),
    )


def _cutoff_checks(
    conn: psycopg.Connection[Any], store: str, path: Path
) -> tuple[CutoffCheck, ...]:
    """Imported PostgreSQL rows against ``FactStore`` on a temp copy, at the data's cutoffs:
    before the first knowledge time, before the first selection, at the median and at the last
    selection."""
    with conn.cursor(row_factory=dict_row) as cursor:
        rows = {row["handle"]: row for row in cursor.execute(_LEGACY_ROWS, {"s": store})}
        chosen = cursor.execute(_LEGACY_SELECTIONS, {"s": store}).fetchall()
    histories: defaultdict[str, list[CanonicalSelection]] = defaultdict(list)
    for item in chosen:
        decision = CanonicalSelection.model_validate(
            item | {"selected_at": _time(item["selected_at"])}
        )
        histories[decision.content_identity].append(decision)
    times = sorted(decision.selected_at for chain in histories.values() for decision in chain)
    first_known = min(_time(row["knowledge_time"]) for row in rows.values())
    cutoffs = (first_known - _TICK, times[0] - _TICK, times[(len(times) - 1) // 2], times[-1])

    def fact(handle: int) -> Fact:
        return Fact.model_validate_json(rows[handle]["fact_json"])

    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / path.name
        shutil.copyfile(path, copy)
        sqlite = FactStore(copy)
        try:
            checks = []
            for cutoff in cutoffs:
                imported = sorted(
                    (d.row_id, identity, rows[d.row_id]["value_hash"], d.selection_id,
                     d.selection_sha256)
                    for identity, history in histories.items()
                    if (d := effective_revision(history, cutoff, fact)) is not None
                )  # fmt: skip
                legacy = _sqlite_rows(sqlite, cutoff)
                checks.append(
                    CutoffCheck(
                        cutoff=cutoff,
                        rows=len(imported),
                        rows_sha256=_sha(json.dumps(imported).encode()),
                        equal=imported == legacy,
                    )
                )
        finally:
            sqlite.close()
    return tuple(checks)


def _sqlite_rows(store: FactStore, cutoff: datetime) -> list[tuple[Any, ...]]:
    """``FactStore``'s canonical revision and effective selection per identity at ``cutoff``."""
    found = []
    for revision in store.query_canonical(cutoff=cutoff):
        history = store.get_selection_history(revision.content_identity)
        decision = [item for item in history if item.selected_at <= cutoff][-1]
        found.append(
            (revision.row_id, revision.content_identity, revision.value_hash,
             decision.selection_id, decision.selection_sha256)
        )  # fmt: skip
    return sorted(found)


def _check_cutover_report(stores: Sequence[str], latest: Mapping[str, Any], payload: bytes) -> None:
    """Refuse unless ``payload`` is the reconciliation report every store's cutover recorded,
    over exactly the manifest's stores; cutover bound that report to its whole store set."""
    try:
        report = ReconciliationReport.model_validate(yaml.safe_load(payload))
    except ValueError as error:
        raise TransitionRefusedError(TransitionRefusal.NOT_THE_CUTOVER_REPORT) from error
    if {store.store_id for store in report.stores} != set(stores) or any(
        event[4] != _sha(payload) for event in latest.values()
    ):
        raise TransitionRefusedError(TransitionRefusal.NOT_THE_CUTOVER_REPORT)


def _last_handles(cursor: psycopg.Cursor[Any], store: str) -> tuple[int | None, int | None]:
    """The store's max row and selection handles."""
    row = cursor.execute(_LAST_HANDLES, {"s": store}).fetchone()
    assert row is not None
    return row[0], row[1]


def _time(text: str) -> datetime:
    """Stored timestamp text as aware UTC."""
    return datetime.fromisoformat(text).astimezone(UTC)


def _sha(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()
