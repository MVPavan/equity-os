"""Retention locks and authority files (plan D9 RP1, R11).

The session locks wrap ``eqos.retention_lock_key()``: purge holds it exclusive, backup shared,
each on its own connection for as long as the session needs it. The two authority files sit in
the backup directory beside the sets: ``licence-ends.json`` and ``expiry-journal.json``, each a
JSON array whose entries carry ids 1, 2, ... in order. One locked helper appends to either; a
file whose ids were dropped or renumbered is refused, never repaired.

The journal's expected head is witnessed by the published sets beside it: each manifest records
its watermark and the digest of the journal up to it, so a journal shorter than a set's
watermark (truncated, rolled back) or differing from the history a set recorded is refused.
Every purge publishes a final backup after ``COMPLETE``, so the newest set witnesses the head.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from fundamentals.contracts.retention import JournalEvent, JournalEventKind, LicenceEnd
from fundamentals.store.snapshot_store import SnapshotStore

LICENCE_ENDS_FILE = "licence-ends.json"
EXPIRY_JOURNAL_FILE = "expiry-journal.json"
AUTHORITY_LOCK_FILE = ".retention-authority.lock"
MANIFEST_FILE = "manifest.yaml"
_SESSION_SHARED: LiteralString = "SELECT pg_advisory_lock_shared(eqos.retention_lock_key())"
_SESSION_EXCLUSIVE: LiteralString = "SELECT pg_advisory_lock(eqos.retention_lock_key())"
_HOLDS_EXCLUSIVE: LiteralString = (
    "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND granted "
    "AND pid = pg_backend_pid() AND mode = 'ExclusiveLock' AND objsubid = 1 "
    "AND (classid::bigint << 32 | objid::bigint) = eqos.retention_lock_key())"
)
_LICENCE_ENDS: LiteralString = "SELECT source_id FROM eqos.licence_ends"
_INSERT_LICENCE_END: LiteralString = (
    "INSERT INTO eqos.licence_ends (source_id, ended_at) VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
_FILES: dict[type[BaseModel], str] = {
    LicenceEnd: LICENCE_ENDS_FILE,
    JournalEvent: EXPIRY_JOURNAL_FILE,
}


class AuthorityError(Exception):
    """An authority file is missing, unreadable, or its ids are not 1..n in order."""


class Authority(BaseModel):
    """Both authority files as read."""

    model_config = ConfigDict(frozen=True)

    licence_ends: tuple[LicenceEnd, ...]
    journal: tuple[JournalEvent, ...]


def session_shared(conn: psycopg.Connection[Any]) -> None:
    """Take the retention lock shared for the rest of this session."""
    conn.execute(_SESSION_SHARED)


def session_exclusive(conn: psycopg.Connection[Any]) -> None:
    """Take the retention lock exclusive for the rest of this session."""
    conn.execute(_SESSION_EXCLUSIVE)


def holds_exclusive(conn: psycopg.Connection[Any]) -> bool:
    """Whether this session holds the retention lock exclusive."""
    row = conn.execute(_HOLDS_EXCLUSIVE).fetchone()
    return bool(row and row[0])


def read_authority(backup_dir: Path) -> Authority:
    """Both authority files, refusing a missing or malformed one or a journal that a published
    set in ``backup_dir`` shows truncated, rolled back or rewritten."""
    authority = Authority(
        licence_ends=tuple(_entries(backup_dir, LicenceEnd)),
        journal=tuple(_entries(backup_dir, JournalEvent)),
    )
    for manifest in sorted(backup_dir.glob(f"[!.]*/{MANIFEST_FILE}")):
        try:
            witness = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise AuthorityError(f"{manifest.parent.name} has no readable manifest") from error
        check_head(
            authority.journal, witness.get("journal_watermark", 0), witness.get("journal_sha256")
        )
    return authority


def journal_digest(journal: tuple[JournalEvent, ...]) -> str:
    """SHA-256 of the journal's events in canonical JSON: what a set records of its history."""
    dumped = json.dumps([event.model_dump(mode="json") for event in journal], sort_keys=True)
    return hashlib.sha256(dumped.encode()).hexdigest()


def check_head(journal: tuple[JournalEvent, ...], watermark: int, digest: str | None) -> None:
    """Refuse a journal that ends before a set's ``watermark`` or whose first ``watermark``
    events differ from the ``digest`` the set recorded (None: a set from before digests)."""
    if watermark > len(journal):
        raise AuthorityError(
            f"{EXPIRY_JOURNAL_FILE} ends at event {len(journal)} but a set was taken at event "
            f"{watermark}: truncated or rolled back"
        )
    if digest is not None and journal_digest(journal[:watermark]) != digest:
        raise AuthorityError(f"{EXPIRY_JOURNAL_FILE} differs from the history a set recorded")


def authority_absent(backup_dir: Path) -> bool:
    """Whether neither authority file exists (the precondition of initialisation)."""
    return not any((backup_dir / name).exists() for name in _FILES.values())


def init_authority(backup_dir: Path) -> None:
    """Write both files empty; only for a provably new backup location (R11)."""
    with _locked(backup_dir):
        if not authority_absent(backup_dir):
            raise AuthorityError(f"{backup_dir} already holds authority files")
        for name in _FILES.values():
            _write(backup_dir, name, [])


def append_authority[M: (JournalEvent, LicenceEnd)](backup_dir: Path, entry: M) -> M:
    """Append ``entry`` to its file with id previous + 1, under the authority lock."""
    with _locked(backup_dir):
        entries = _entries(backup_dir, type(entry))
        stored = entry.model_copy(update={"id": len(entries) + 1})
        dumped = [e.model_dump(mode="json") for e in entries] + [stored.model_dump(mode="json")]
        _write(backup_dir, _FILES[type(entry)], dumped)
    return stored


def mark_licence_ends(snapshot_root: Path, authority: Authority, *also: str) -> None:
    """Write the RP4a marker of every licence end in ``authority`` (and ``also``)."""
    store = SnapshotStore(snapshot_root)
    for source in {end.source_id for end in authority.licence_ends} | set(also):
        store.mark_licence_ended(source)


def reconcile_licence_ends(conn: psycopg.Connection[Any], authority: Authority) -> tuple[str, ...]:
    """Insert the filed licence ends the database lacks, returning them; refuse a database
    licence end the file lacks (R11)."""
    stored = {source for (source,) in conn.execute(_LICENCE_ENDS).fetchall()}
    filed = {end.source_id: end for end in authority.licence_ends}
    if stored - filed.keys():
        unfiled = sorted(stored - filed.keys())
        raise AuthorityError(f"licence ends {unfiled} are not filed; rerun retention licence-end")
    missing = tuple(source for source in filed if source not in stored)
    for source in missing:
        conn.execute(_INSERT_LICENCE_END, (source, filed[source].recorded_at))
    return missing


def expiries_after(journal: tuple[JournalEvent, ...], watermark: int) -> frozenset[int]:
    """Captures expired by runs with an event above ``watermark``: a completed run's expired
    ids, an unresolved run's every fenced capture (R11, conservatively)."""
    runs = {event.run_id for event in journal if event.id > watermark}
    expired: set[int] = set()
    for run in runs:
        events = [event for event in journal if event.run_id == run]
        completes = [e for e in events if e.kind is JournalEventKind.COMPLETE]
        if completes:
            expired.update(completes[-1].expired)
        else:
            expired.update(c.capture_ref_id for e in events for c in e.captures)
    return frozenset(expired)


def _entries[M: (JournalEvent, LicenceEnd)](backup_dir: Path, model: type[M]) -> list[M]:
    """One file's entries, refused unless present, valid and numbered 1..n."""
    name = _FILES[model]
    try:
        raw = json.loads((backup_dir / name).read_text(encoding="utf-8"))
        entries = [model.model_validate(item) for item in raw]
    except (OSError, ValueError, TypeError, ValidationError) as error:
        raise AuthorityError(f"{name} in {backup_dir} is missing or unreadable") from error
    if [entry.id for entry in entries] != list(range(1, len(entries) + 1)):
        raise AuthorityError(f"{name} in {backup_dir} has dropped or renumbered entries")
    return entries


def _write(backup_dir: Path, name: str, entries: list[Any]) -> None:
    """Replace one file atomically: temp, fsync, rename, fsync the directory."""
    temporary = backup_dir / f".{name}.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.rename(backup_dir / name)
    directory = os.open(backup_dir, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def _locked(backup_dir: Path) -> Iterator[None]:
    """The authority files' exclusive flock for one read-modify-write."""
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(backup_dir / AUTHORITY_LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)
