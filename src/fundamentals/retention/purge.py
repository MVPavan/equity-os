"""Purge: delete eligible originals, crash-safe and under the retention lock (plan D9 R7, R8,
RP1, RP4b, RP5).

At most one run is open. A purge first recovers any open run, then commits a new run (its
epoch), rechecks eligibility and commits intents, fences them in the expiry journal, deletes
under the store's writer lock, commits purge records, ``EXPIRED`` and vendor tombstones in
one transaction, journals ``COMPLETE``, takes the injected final backup on its own
connection, sanitizes older sets and closes the run. A crash leaves the run open, which
refuses writers and backups until a rerun converges it through the same routine. A licence
end (R11) and a restore's purge-first (R12, ``purge_first``) reuse the deletion and sanitize
routines. Run ids continue past every run the journal names, which a restored target's ids lag.
"""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime
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
    LicenceEnd,
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
    advance_head,
    append_authority,
    expiries_after,
    read_authority,
    reconcile_licence_ends,
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
_NEW_RUN: LiteralString = (  # an explicit id needs only INSERT, which every 0029+ set grants
    "INSERT INTO eqos.purge_runs (id) OVERRIDING SYSTEM VALUE "
    "SELECT greatest(max(id), %s, 0) + 1 FROM eqos.purge_runs RETURNING id"
)
_CLOSE_RUN: LiteralString = "INSERT INTO eqos.purge_run_closures (run_id) VALUES (%s)"
_STATE: LiteralString = (
    "INSERT INTO eqos.capture_states (capture_ref_id, state, purge_run_id) VALUES (%s, %s, %s)"
)
_CANCEL: LiteralString = (  # back to the state before the intent: RETAINED or RESTORED
    "INSERT INTO eqos.capture_states (capture_ref_id, state, purge_run_id) SELECT %(c)s, "
    "coalesce((SELECT state FROM eqos.capture_states WHERE capture_ref_id = %(c)s AND state "
    "<> 'PURGE_PENDING' ORDER BY id DESC LIMIT 1), 'RETAINED'), %(run)s"
)
_RUN_STATES: LiteralString = (
    "SELECT capture_ref_id, eqos.capture_state(capture_ref_id) FROM eqos.capture_states "
    "WHERE purge_run_id = %s GROUP BY capture_ref_id ORDER BY capture_ref_id"
)
_USERS: LiteralString = (
    "SELECT r.id, r.source_id, r.surface, r.request_key, r.capture_id, r.blob_sha256, "
    "r.record_sha256, a.url, eqos.capture_state(r.id) AS state, k.retention_class "
    "FROM eqos.capture_refs r LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id "
    "LEFT JOIN eqos.retention_classes k ON k.capture_ref_id = r.id ORDER BY r.id"
)
_PURGE_RECORD: LiteralString = (
    "INSERT INTO eqos.purge_records (purge_run_id, capture_ref_id, retention_class, reason, "
    "url, blob_sha256, probe_id) VALUES (%s, %s, %s, %s, %s, %s, "
    "(SELECT max(id) FROM eqos.retention_probes WHERE source_id = %s AND outcome = 'MATCH' "
    "AND %s))"
)
_TOMBSTONE: LiteralString = "SELECT eqos.tombstone_vendor_capture(%s)"
_LICENCE_ENDS: LiteralString = "SELECT source_id FROM eqos.licence_ends"
_VENDOR_NOW: LiteralString = "SELECT eqos.is_vendor_source(%s), eqos.store_now()"
_GONE = frozenset({CaptureState.EXPIRED, CaptureState.PURGE_PENDING})
_KEPT = frozenset({CaptureState.RETAINED, CaptureState.RESTORED})


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
        reconcile_licence_ends(conn, authority := read_authority(backup_dir))
        refuse_unclassified(conn)
        with conn.transaction():
            facts, now = _facts(conn, pinned)
        exchange = _eligible_facts(facts, now, RetentionClass.EXCHANGE_REFETCHABLE)
        probes = probe(conn, exchange, fetch)
        session_exclusive(conn)
        matched = {source for source, outcome in probes.items() if outcome.matched}
        run = _Run(conn, snapshot_root, backup_dir, pinned, final_backup, checkpoint)
        run.halted = frozenset(probes.keys() - matched)
        for (open_run,) in conn.execute(_OPEN_RUNS).fetchall():
            run.converge(open_run)
        run_id = new_run(conn, authority)
        with conn.transaction():
            facts, now = _facts(conn, pinned)
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
        halted_sources=tuple(sorted(run.halted)),
        backup_id=run.backup_id,
    )


_EXCHANGE = RetentionClass.EXCHANGE_REFETCHABLE


def new_run(conn: psycopg.Connection[Any], authority: Authority) -> int:
    """Commit a run row whose id is past every run of the database and of the journal."""
    last = max((event.run_id for event in authority.journal), default=0)
    return int(conn.execute(_NEW_RUN, (last,)).fetchall()[0][0])


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
        snapshot_root: Path,
        backup_dir: Path,
        pinned: Pinned,
        final_backup: FinalBackup | None,
        checkpoint: Checkpoint,
    ) -> None:
        self.conn, self.backup_dir, self.root = conn, backup_dir, snapshot_root
        self.store = SnapshotStore(snapshot_root)
        self.pinned, self.final_backup, self.checkpoint = pinned, final_backup, checkpoint
        self.expired: list[int] = []
        self.cancelled: list[tuple[int, str]] = []
        self.incomplete: list[IncompleteBlob] = []
        self.backup_id: str | None = None
        self.halted: frozenset[str] = frozenset()  # probe-halted sources keep intact intents

    def converge(self, run_id: int) -> None:
        """Fence, delete, expire, complete, back up, sanitize and close one run."""
        with self.conn.cursor(row_factory=dict_row) as cursor:
            users = cursor.execute(_USERS).fetchall()
        pending = [u for u in users if u["state"] == CaptureState.PURGE_PENDING]
        if self._event(run_id, JournalEventKind.FENCE) is None:
            fence = tuple(FencedCapture.model_validate(_fenced(u)) for u in pending)
            event = JournalEvent(kind=JournalEventKind.FENCE, run_id=run_id, captures=fence)
            append_authority(self.backup_dir, event)
            self.checkpoint(PurgeStep.FENCE_WRITTEN)
        done = self._event(run_id, JournalEventKind.COMPLETE)
        if done is not None and (done.expired, done.cancelled) != self._outcomes(run_id):
            raise PurgeRefusedError(f"run {run_id}'s COMPLETE disagrees with its committed states")
        advance_head(self.backup_dir, self.root)
        with self.conn.transaction():
            facts, now = _facts(self.conn, self.pinned)
        verdicts = {f.capture_ref_id: (f, _decision(f, now)) for f in facts}
        eligible = {(b.source_id, b.blob_sha256) for b in eligible_blobs(facts, now)}
        eligible -= {
            (u["source_id"], u["blob_sha256"])
            for u in pending
            if u["source_id"] in self.halted and u["retention_class"] == _EXCHANGE
        }
        with self.store.writer_held():
            cancel = self._delete(users, eligible)
            self.checkpoint(PurgeStep.FILES_DELETED)
            with self.conn.transaction():
                for capture in cancel:
                    self.conn.execute(_CANCEL, {"c": capture, "run": run_id})
                for user in pending:
                    if user["id"] not in cancel:
                        self._expire(run_id, user, verdicts.get(user["id"]))
        self.checkpoint(PurgeStep.EXPIRED_COMMITTED)
        expired, cancelled = self._outcomes(run_id)
        self.expired += [c for c in expired if c not in self.expired]
        self.cancelled += [(c, r) for c, r in cancel.items()]
        if done is None:
            event = JournalEvent(
                kind=JournalEventKind.COMPLETE,
                run_id=run_id,
                expired=expired,
                cancelled=cancelled,
                purged_at=now,
            )
            append_authority(self.backup_dir, event)
            self.checkpoint(PurgeStep.COMPLETION_WRITTEN)
        advance_head(self.backup_dir, self.root)
        if self.final_backup is not None:
            self.backup_id = self.final_backup(self.conn).name
            self.checkpoint(PurgeStep.BACKUP_WRITTEN)
        sanitize(self.conn, self.backup_dir, self.checkpoint)
        self.conn.execute(_CLOSE_RUN, (run_id,))

    def _event(self, run_id: int, kind: JournalEventKind) -> JournalEvent | None:
        """The expiry journal's ``kind`` event for the run, if any."""
        journal = read_authority(self.backup_dir).journal
        return next((e for e in journal if e.run_id == run_id and e.kind is kind), None)

    def _outcomes(self, run_id: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """The run's committed outcomes: the captures it expired and those it cancelled."""
        states = self.conn.execute(_RUN_STATES, (run_id,)).fetchall()
        expired = tuple(c for c, state in states if state == CaptureState.EXPIRED)
        return expired, tuple(c for c, state in states if state in _KEPT)

    def _delete(
        self, users: list[dict[str, Any]], eligible: set[tuple[str, str]]
    ) -> dict[int, str]:
        """Step 3 under the held writer lock (RP5): every licence-ended source's bodies and blobs,
        all checked before any unlink; then per inventoried blob, the body links of its expired
        and purging users (residue included) and the blob unless a retained user keeps it.
        Return the intents to cancel: those with an intact body whose blob is no longer
        eligible or keeps an unknown link; an intent whose body is gone is finished."""
        ended = frozenset(source for (source,) in self.conn.execute(_LICENCE_ENDS).fetchall())
        if (outside := self.store.delete_sources(ended, self._link_deleted)) is not None:
            raise PurgeRefusedError(f"licence-ended blob {outside} is linked outside its trees")
        by_blob: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for user in users:
            by_blob[user["source_id"], user["blob_sha256"]].append(user)
        cancel: dict[int, str] = {}
        for entry in self.store.blob_inventory():
            key = (entry.source_id, entry.blob_sha256)
            group = by_blob.get(key, [])
            if not group:
                self.incomplete.append(_incomplete(entry, IncompleteKind.UNREGISTERED))
                continue
            mine = [u for u in group if u["state"] == CaptureState.PURGE_PENDING]
            intact = [u["id"] for u in mine if self.store.body_link(*key, _link(u))]
            if key not in eligible:
                cancel.update(dict.fromkeys(intact, NO_LONGER_ELIGIBLE))
            gone = [u for u in group if CaptureState(u["state"]) in _GONE and u["id"] not in cancel]
            links = tuple(_link(u) for u in gone)
            kept = len(gone) < len(group)
            deleted = self.store.delete_blob(*key, links, self._link_deleted, keep_blob=kept)
            if deleted is BlobDeletion.UNKNOWN_LINK:
                self.incomplete.append(_incomplete(entry, IncompleteKind.UNKNOWN_LINK))
                cancel.update(dict.fromkeys(intact, IncompleteKind.UNKNOWN_LINK.value))
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


def _decision(fact: CaptureFacts, now: datetime) -> Eligibility:
    """An intent's verdict once its bytes are gone (R8): a hold that appeared since (only a
    pinned file root can, writers being refused) does not undo the deletion."""
    verdict = eligibility(fact, now)
    if verdict.kind is EligibilityKind.HELD:
        return eligibility(fact.model_copy(update={"holds": frozenset()}), now)
    return verdict


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


def _link(user: dict[str, Any]) -> tuple[str, str, str]:
    """A capture's body link under its source: surface, request key and capture id."""
    return user["surface"], user["request_key"], user["capture_id"]


def _incomplete(entry: Any, kind: IncompleteKind) -> IncompleteBlob:
    """An inventory entry the operator must resolve."""
    return IncompleteBlob(source_id=entry.source_id, blob_sha256=entry.blob_sha256, kind=kind)


def record_licence_end(
    settings: PgSettings,
    login: RoleLogin | None,
    *,
    source_id: str,
    ended_on: date,
    reason: str,
    database: str,
    snapshot_root: Path,
    backup_dir: Path,
    pinned: Pinned,
    fetch: Fetch,
    final_backup: FinalBackup | None,
    checkpoint: Checkpoint,
) -> PurgeReport:
    """An owner's vendor licence end (R11), each step idempotent: the store marker, the file
    entry, the database row, then a purge that expires all the source's material, holds
    notwithstanding (R5 puts a reached licence end first)."""
    filed = {end.source_id for end in read_authority(backup_dir).licence_ends}
    conninfo = settings.conninfo(PgRole.PURGE, dbname=database, login=login)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        ((vendor, now),) = conn.execute(_VENDOR_NOW, (source_id,)).fetchall()
        if not vendor:
            raise PurgeRefusedError(f"{source_id} is not a vendor-bounded source")
        SnapshotStore(snapshot_root).mark_licence_ended(source_id)
        if source_id not in filed:
            end = LicenceEnd(source_id=source_id, ended_on=ended_on, reason=reason, recorded_at=now)
            append_authority(backup_dir, end)
        reconcile_licence_ends(conn, read_authority(backup_dir))
    return purge(
        settings,
        login,
        database=database,
        snapshot_root=snapshot_root,
        backup_dir=backup_dir,
        pinned=pinned,
        fetch=fetch,
        final_backup=final_backup,
        checkpoint=checkpoint,
    )
