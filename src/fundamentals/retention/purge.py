"""Purge: delete eligible originals, crash-safe and under the retention lock (plan D9 R7, R8,
RP1, RP4b, RP5).

At most one run is open. A purge first recovers any open run, then commits a new run (its
epoch), rechecks eligibility and commits intents, fences them in the expiry journal, deletes
under the store's writer lock, commits purge records, ``EXPIRED`` and vendor tombstones in
one transaction, journals ``COMPLETE``, takes the injected final backup on its own
connection, sanitizes older sets and closes the run. A crash leaves the run open, which
refuses writers and backups until a rerun converges it through the same routine.
"""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import yaml
from psycopg.rows import dict_row

from fundamentals.contracts.retention import (
    BlobDeletion,
    CaptureFacts,
    CaptureState,
    Eligibility,
    EligibilityKind,
    EligibleBlob,
    FencedCapture,
    HoldRoot,
    JournalEvent,
    JournalEventKind,
    RetentionClass,
)
from fundamentals.contracts.retention_purge import (
    IncompleteBlob,
    IncompleteKind,
    PurgeRefusedError,
    PurgeReport,
    PurgeStep,
)
from fundamentals.pg.backup import MANIFEST_FILE, PARTIAL_SUFFIX, BackupManifest
from fundamentals.pg.retention_io import (
    Authority,
    append_authority,
    expiries_after,
    read_authority,
    session_exclusive,
)
from fundamentals.pg.role_secrets import RoleLogin
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.retention.eligibility import eligibility, eligible_blobs
from fundamentals.retention.holds import capture_facts
from fundamentals.retention.refetch import Fetch, probe
from fundamentals.store.snapshot_store import SnapshotStore

Checkpoint = Callable[[PurgeStep], None]
FinalBackup = Callable[[psycopg.Connection[Any]], Path]
Pinned = dict[HoldRoot, frozenset[str]]
NO_LONGER_ELIGIBLE = "NO_LONGER_ELIGIBLE"
DELETING_SUFFIX = ".deleting"
_NOW: LiteralString = "SELECT eqos.store_now()"
UNCLASSIFIED: LiteralString = (
    "SELECT DISTINCT source_id, surface FROM eqos.capture_refs r WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.retention_classes c WHERE c.capture_ref_id = r.id) ORDER BY 1, 2"
)
INCIDENTS: LiteralString = (
    "SELECT kind, id, source_id, capture_ref_id, outcome FROM eqos.retention_incidents ORDER BY id"
)
_OPEN_RUNS: LiteralString = (
    "SELECT id FROM eqos.purge_runs r WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.purge_run_closures c WHERE c.run_id = r.id) ORDER BY id"
)
_NEW_RUN: LiteralString = "INSERT INTO eqos.purge_runs DEFAULT VALUES RETURNING id"
_CLOSE_RUN: LiteralString = "INSERT INTO eqos.purge_run_closures (run_id) VALUES (%s)"
_STATE: LiteralString = (
    "INSERT INTO eqos.capture_states (capture_ref_id, state, purge_run_id) VALUES (%s, %s, %s)"
)
_RUN_STATES: LiteralString = (
    "SELECT capture_ref_id, eqos.capture_state(capture_ref_id) FROM eqos.capture_states "
    "WHERE purge_run_id = %s GROUP BY capture_ref_id ORDER BY capture_ref_id"
)
_USERS: LiteralString = (
    "SELECT r.id, r.source_id, r.surface, r.request_key, r.capture_id, r.blob_sha256, "
    "r.record_sha256, a.url, eqos.capture_state(r.id) AS state FROM eqos.capture_refs r "
    "LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id ORDER BY r.id"
)
_PURGE_RECORD: LiteralString = (
    "INSERT INTO eqos.purge_records (purge_run_id, capture_ref_id, retention_class, reason, "
    "url, blob_sha256, probe_id) VALUES (%s, %s, %s, %s, %s, %s, "
    "(SELECT max(id) FROM eqos.retention_probes WHERE source_id = %s AND outcome = 'MATCH' "
    "AND %s))"
)
_TOMBSTONE: LiteralString = "SELECT eqos.tombstone_vendor_capture(%s)"
_LICENCE_ENDS: LiteralString = "SELECT source_id FROM eqos.licence_ends"
_INSERT_LICENCE_END: LiteralString = (
    "INSERT INTO eqos.licence_ends (source_id, ended_at) VALUES (%s, %s)"
)
_GONE = frozenset({CaptureState.EXPIRED, CaptureState.PURGE_PENDING})


def dry_run(conn: psycopg.Connection[Any], pinned: Pinned) -> tuple[EligibleBlob, ...]:
    """The blobs eligible now; refused while any capture is unclassified (R2)."""
    with conn.transaction():
        refuse_unclassified(conn)
        facts, now = _facts(conn, pinned)
    return eligible_blobs(facts, now)


def refuse_unclassified(conn: psycopg.Connection[Any]) -> None:
    """Raise, naming them, while any (source, surface) has an unclassified capture."""
    left = conn.execute(UNCLASSIFIED).fetchall()
    if left:
        named = ", ".join(f"{source}/{surface}" for source, surface in left)
        raise PurgeRefusedError(f"unclassified captures: {named}; run retention classify")


def purge(
    settings: PgSettings,
    login: RoleLogin | None,
    *,
    database: str,
    snapshot_root: Path,
    backup_dir: Path,
    pinned: Pinned,
    fetch: Fetch,
    final_backup: FinalBackup | None,
    checkpoint: Checkpoint,
) -> PurgeReport:
    """Recover any open run, then purge every eligible blob in a new run (R8)."""
    conninfo = settings.conninfo(PgRole.PURGE, dbname=database, login=login)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        reconcile_licence_ends(conn, read_authority(backup_dir))
        refuse_unclassified(conn)
        with conn.transaction():
            facts, now = _facts(conn, pinned)
        exchange = _eligible_facts(facts, now, RetentionClass.EXCHANGE_REFETCHABLE)
        probes = probe(conn, exchange, fetch)
        session_exclusive(conn)
        store = SnapshotStore(snapshot_root)
        run = _Run(conn, store, backup_dir, pinned, final_backup, checkpoint)
        for (open_run,) in conn.execute(_OPEN_RUNS).fetchall():
            run.converge(open_run)
        ((run_id,),) = conn.execute(_NEW_RUN).fetchall()
        with conn.transaction():
            facts, now = _facts(conn, pinned)
            matched = {source for source, outcome in probes.items() if outcome.matched}
            for fact in _eligible_facts(facts, now):
                if fact.base_class is not _EXCHANGE or fact.source_id in matched:
                    conn.execute(_STATE, (fact.capture_ref_id, CaptureState.PURGE_PENDING, run_id))
        checkpoint(PurgeStep.INTENTS_COMMITTED)
        run.converge(run_id)
    return PurgeReport(
        run_id=run_id,
        expired=tuple(run.expired),
        cancelled=tuple(run.cancelled),
        incomplete=tuple(run.incomplete),
        halted_sources=tuple(sorted(probes.keys() - matched)),
        backup_id=run.backup_id,
    )


_EXCHANGE = RetentionClass.EXCHANGE_REFETCHABLE


def reconcile_licence_ends(conn: psycopg.Connection[Any], authority: Authority) -> None:
    """Insert file licence ends the database lacks; refuse one the file lacks (R11)."""
    stored = {source for (source,) in conn.execute(_LICENCE_ENDS).fetchall()}
    filed = {end.source_id: end for end in authority.licence_ends}
    if stored - filed.keys():
        raise PurgeRefusedError(f"licence ends {sorted(stored - filed.keys())} are not filed")
    for source, end in filed.items():
        if source not in stored:
            conn.execute(_INSERT_LICENCE_END, (source, end.recorded_at))


def _facts(conn: psycopg.Connection[Any], pinned: Pinned) -> tuple[tuple[CaptureFacts, ...], Any]:
    """Every non-expired capture's facts and the store clock, in the caller's transaction."""
    ((now,),) = conn.execute(_NOW).fetchall()
    return capture_facts(conn, pinned), now


def _eligible_facts(
    facts: tuple[CaptureFacts, ...], now: datetime, kind: RetentionClass | None = None
) -> tuple[CaptureFacts, ...]:
    """The facts of every capture of an eligible blob, optionally of one class only."""
    ids = {c for blob in eligible_blobs(facts, now) for c in blob.capture_ref_ids}
    return tuple(f for f in facts if f.capture_ref_id in ids and kind in (None, f.base_class))


class _Run:
    """Steps 3-5 of one run, the same for a new run and a recovered one."""

    def __init__(
        self,
        conn: psycopg.Connection[Any],
        store: SnapshotStore,
        backup_dir: Path,
        pinned: Pinned,
        final_backup: FinalBackup | None,
        checkpoint: Checkpoint,
    ) -> None:
        self.conn, self.store, self.backup_dir = conn, store, backup_dir
        self.pinned, self.final_backup, self.checkpoint = pinned, final_backup, checkpoint
        self.expired: list[int] = []
        self.cancelled: list[tuple[int, str]] = []
        self.incomplete: list[IncompleteBlob] = []
        self.backup_id: str | None = None

    def converge(self, run_id: int) -> None:
        """Fence, delete, expire, complete, back up, sanitize and close one run."""
        with self.conn.cursor(row_factory=dict_row) as cursor:
            users = cursor.execute(_USERS).fetchall()
        pending = [u for u in users if u["state"] == CaptureState.PURGE_PENDING]
        if not self._journaled(run_id, JournalEventKind.FENCE):
            fence = tuple(FencedCapture.model_validate(_fenced(u)) for u in pending)
            event = JournalEvent(kind=JournalEventKind.FENCE, run_id=run_id, captures=fence)
            append_authority(self.backup_dir, event)
            self.checkpoint(PurgeStep.FENCE_WRITTEN)
        with self.conn.transaction():
            facts, now = _facts(self.conn, self.pinned)
        verdicts = {f.capture_ref_id: (f, eligibility(f, now)) for f in facts}
        eligible = {(b.source_id, b.blob_sha256) for b in eligible_blobs(facts, now)}
        with self.store.writer_held():
            cancel = self._delete(users, eligible)
            self.checkpoint(PurgeStep.FILES_DELETED)
            with self.conn.transaction():
                for capture in cancel:
                    self.conn.execute(_STATE, (capture, CaptureState.RETAINED, run_id))
                for user in pending:
                    if user["id"] not in cancel:
                        self._expire(run_id, user, verdicts.get(user["id"]))
        self.checkpoint(PurgeStep.EXPIRED_COMMITTED)
        states = self.conn.execute(_RUN_STATES, (run_id,)).fetchall()
        expired = tuple(c for c, state in states if state == CaptureState.EXPIRED)
        cancelled = tuple(c for c, state in states if state == CaptureState.RETAINED)
        self.expired += [c for c in expired if c not in self.expired]
        self.cancelled += [(c, r) for c, r in cancel.items()]
        if not self._journaled(run_id, JournalEventKind.COMPLETE):
            event = JournalEvent(
                kind=JournalEventKind.COMPLETE,
                run_id=run_id,
                expired=expired,
                cancelled=cancelled,
                purged_at=now,
            )
            append_authority(self.backup_dir, event)
            self.checkpoint(PurgeStep.COMPLETION_WRITTEN)
        if self.final_backup is not None:
            self.backup_id = self.final_backup(self.conn).name
            self.checkpoint(PurgeStep.BACKUP_WRITTEN)
        sanitize(self.conn, self.backup_dir, self.checkpoint)
        self.conn.execute(_CLOSE_RUN, (run_id,))

    def _journaled(self, run_id: int, kind: JournalEventKind) -> bool:
        """Whether the expiry journal has a ``kind`` event for the run."""
        journal = read_authority(self.backup_dir).journal
        return any(e.run_id == run_id and e.kind is kind for e in journal)

    def _delete(
        self, users: list[dict[str, Any]], eligible: set[tuple[str, str]]
    ) -> dict[int, str]:
        """Step 3 under the held writer lock (RP5): inventory every blob; delete those whose
        registered users are all purging or expired (residue included); return the intents
        to cancel: an unknown link, or intact bytes no longer eligible."""
        by_blob: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for user in users:
            by_blob[user["source_id"], user["blob_sha256"]].append(user)
        cancel: dict[int, str] = {}
        for entry in self.store.blob_inventory():
            key = (entry.source_id, entry.blob_sha256)
            group = by_blob.get(key, [])
            mine = [u["id"] for u in group if u["state"] == CaptureState.PURGE_PENDING]
            if not group:
                self.incomplete.append(_incomplete(entry, IncompleteKind.UNREGISTERED))
                continue
            if any(CaptureState(u["state"]) not in _GONE for u in group):
                continue
            if mine and key not in eligible and entry.links >= 1 + len(mine):
                cancel.update(dict.fromkeys(mine, NO_LONGER_ELIGIBLE))
                continue
            links = tuple((u["surface"], u["request_key"], u["capture_id"]) for u in group)
            deleted = self.store.delete_blob(*key, links, self._link_deleted)
            if deleted is BlobDeletion.UNKNOWN_LINK:
                self.incomplete.append(_incomplete(entry, IncompleteKind.UNKNOWN_LINK))
                cancel.update(dict.fromkeys(mine, IncompleteKind.UNKNOWN_LINK.value))
        return cancel

    def _link_deleted(self) -> None:
        """The per-unlink crash seam."""
        self.checkpoint(PurgeStep.LINK_DELETED)

    def _expire(
        self, run_id: int, user: dict[str, Any], judged: tuple[CaptureFacts, Eligibility] | None
    ) -> None:
        """Step 4 for one intent: its purge record, ``EXPIRED`` and a vendor tombstone."""
        fact, verdict = judged or (None, None)
        if fact is None or verdict is None or verdict.kind is not EligibilityKind.ELIGIBLE:
            raise PurgeRefusedError(f"capture {user['id']} lost its bytes but is not eligible")
        exchange = fact.base_class is _EXCHANGE
        record = (run_id, fact.capture_ref_id, fact.base_class, verdict.reason, user["url"])
        self.conn.execute(_PURGE_RECORD, (*record, fact.blob_sha256, fact.source_id, exchange))
        if fact.base_class is RetentionClass.VENDOR:
            self.conn.execute(_TOMBSTONE, (fact.capture_ref_id,))
        self.conn.execute(_STATE, (fact.capture_ref_id, CaptureState.EXPIRED, run_id))


def sanitize(conn: psycopg.Connection[Any], backup_dir: Path, checkpoint: Checkpoint) -> None:
    """Remove every set archiving bytes the journal expired after its watermark or of a
    licence-ended source, then every ``.deleting``/``.partial`` remnant (R11)."""
    journal = read_authority(backup_dir).journal
    ended = {source for (source,) in conn.execute(_LICENCE_ENDS).fetchall()}
    for path in sorted(p for p in backup_dir.iterdir() if p.is_dir()):
        if path.name.startswith("."):
            continue
        manifest = BackupManifest.model_validate(yaml.safe_load((path / MANIFEST_FILE).read_text()))
        expired = expiries_after(journal, manifest.journal_watermark)
        if any(c[0] in expired or c[1] in ended for c in manifest.captures):
            path.rename(backup_dir / f".{path.name}{DELETING_SUFFIX}")
            directory = os.open(backup_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            checkpoint(PurgeStep.SET_RENAMED)
    for path in backup_dir.iterdir():
        if path.is_dir() and path.name.startswith("."):
            if path.name.endswith((DELETING_SUFFIX, PARTIAL_SUFFIX)):
                shutil.rmtree(path)


def _fenced(user: dict[str, Any]) -> dict[str, Any]:
    """A pending capture's row as its ``FENCE`` entry."""
    return (
        {"capture_ref_id": user["id"]}
        | {
            key: user[key]
            for key in ("source_id", "surface", "request_key", "capture_id", "blob_sha256")
        }
        | {"record_sha256": user["record_sha256"], "url": user["url"]}
    )


def _incomplete(entry: Any, kind: IncompleteKind) -> IncompleteBlob:
    """An inventory entry the operator must resolve."""
    return IncompleteBlob(source_id=entry.source_id, blob_sha256=entry.blob_sha256, kind=kind)
