"""Restore's purge-first (plan D9 R12) on R8's deletion and sanitize routines.

Composed before the target exists, it refuses a live store whose licence-ended markers name a
source the licence-ends file lacks (a rolled-back file would reopen that vendor). On the closed
target it closes the imported runs the journal completed (a final purge backup holds its own run
open), expires what the journal expired after the set and every licence-ended capture, deletes
their bytes, sanitizes the backup directory and closes its own run; anything left pending refuses.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row

from equity_os.contracts.storage.retention import (
    CaptureState,
    EligibleReason,
    JournalEventKind,
    RetentionClass,
)
from equity_os.contracts.storage.retention_purge import PurgeRefusedError, PurgeStep, RestoreDelta
from equity_os.storage.backup.backup import BackupError, verify_set
from equity_os.storage.raw_files.snapshot_store import LICENCE_ENDED_DIRNAME, RETENTION_DIRNAME
from equity_os.storage.retention.purge import (
    _CLOSE_RUN,
    _GONE,
    _LICENCE_ENDS,
    _OPEN_RUNS,
    _PURGE_RECORD,
    _STATE,
    _TOMBSTONE,
    _USERS,
    _Run,
    new_run,
    sanitize,
)
from equity_os.storage.retention.retention_io import (
    Authority,
    AuthorityError,
    expiries_after,
    mark_licence_ends,
    read_authority,
    reconcile_licence_ends,
    session_exclusive,
)

JOURNAL_EXPIRY = "EXPIRY_JOURNAL"  # the purge-record reason of a journal expiry
_PENDING: LiteralString = "SELECT kind, id FROM eqos.retention_pending ORDER BY kind, id"


def restore_purge_first(
    set_dir: Path, backup_dir: Path, snapshot_root: Path, live: Path | None
) -> Callable[[psycopg.Connection[Any]], RestoreDelta]:
    """Restore's injected purge-first (pg never imports retention): one authority snapshot read
    against the head in ``live`` when the target is ready, marks its licence ends and is purged.
    Refuses now when a live licence-ended marker's source is not filed."""
    ended = (live / RETENTION_DIRNAME / LICENCE_ENDED_DIRNAME).glob("*") if live else ()
    if marked := {p.name for p in ended}:  # no marker: nothing to reconcile, no authority read
        try:
            filed = {end.source_id for end in read_authority(backup_dir).licence_ends}
            if unfiled := sorted(marked - filed):
                raise AuthorityError(f"live licence ends {unfiled} are not filed")
        except AuthorityError as error:
            raise BackupError(f"retention authority refused: {error}") from error

    def purge_first(conn: psycopg.Connection[Any]) -> RestoreDelta:
        watermark = verify_set(set_dir).journal_watermark
        mark_licence_ends(snapshot_root, authority := read_authority(backup_dir, live))
        return restore_purge(conn, authority, watermark, snapshot_root, backup_dir)

    return purge_first


def restore_purge(
    conn: psycopg.Connection[Any],
    authority: Authority,
    watermark: int,
    snapshot_root: Path,
    backup_dir: Path,
) -> RestoreDelta:
    """Purge-first of a restored set (R12): insert the filed licence ends, close the imported
    runs the journal completed, expire the set's expiries after ``watermark`` (a run completed
    past the live head by its fence) and every licence-ended capture with purge records, holds
    notwithstanding and without an eligibility recompute; delete their bytes, sanitize the
    backup directory and close the run. No journal append, no final backup."""
    inserted = reconcile_licence_ends(conn, authority)
    session_exclusive(conn)
    completed = {e.run_id for e in authority.journal if e.kind is JournalEventKind.COMPLETE}
    imported = [run for (run,) in conn.execute(_OPEN_RUNS).fetchall() if run in completed]
    for run in imported:
        conn.execute(_CLOSE_RUN, (run,))
    run_id = new_run(conn, authority)
    ended = {source for (source,) in conn.execute(_LICENCE_ENDS).fetchall()}
    expiries = expiries_after(authority.journal, watermark, authority.head)
    with conn.cursor(row_factory=dict_row) as cursor:
        users = cursor.execute(_USERS).fetchall()
    targets = [
        u
        for u in users
        if u["state"] not in _GONE and (u["id"] in expiries or u["source_id"] in ended)
    ]
    with conn.transaction():
        for user in targets:
            capture, gone = user["id"], user["source_id"] in ended
            conn.execute(_STATE, (capture, CaptureState.PURGE_PENDING, run_id))
            if user["retention_class"] == RetentionClass.VENDOR:
                conn.execute(_TOMBSTONE, (capture,))
            reason = EligibleReason.LICENCE_END if gone else JOURNAL_EXPIRY
            record = (run_id, capture, user["retention_class"], reason, user["url"])
            conn.execute(_PURGE_RECORD, (*record, user["blob_sha256"], user["source_id"], False))
            conn.execute(_STATE, (capture, CaptureState.EXPIRED, run_id))
    run = _Run(conn, snapshot_root, backup_dir, {}, None, _no_step)
    with conn.cursor(row_factory=dict_row) as cursor:
        users = cursor.execute(_USERS).fetchall()
    with run.store.writer_held():
        run._delete(users, set())
    if run.incomplete:
        raise PurgeRefusedError(f"restored store has blobs to register or remove: {run.incomplete}")
    sanitize(conn, backup_dir, _no_step)
    conn.execute(_CLOSE_RUN, (run_id,))
    if pending := conn.execute(_PENDING).fetchall():
        raise PurgeRefusedError(f"restored database has unfinished purges {pending}")
    count = len(targets)
    rows = {"purge_runs": 1, "purge_run_closures": 1 + len(imported), "licence_ends": len(inserted)}
    rows |= {"capture_states": 2 * count, "purge_records": count}
    return RestoreDelta(expired=tuple(u["id"] for u in targets), rows=rows)


def _no_step(step: PurgeStep) -> None:
    """Restore's purge-first has no crash seam: a failure leaves the target closed."""
    del step
