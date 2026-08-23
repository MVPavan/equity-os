"""Persistent, deterministic adjudication records for thesis discrepancies."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

from fundamentals.thesis.contracts import Discrepancy

_QUEUE_SCHEMA_VERSION = 1
_LOGGER = structlog.get_logger("fundamentals.thesis.adjudication")


def normalize_queue_key(value: str) -> str:
    """Return the canonical stock/quarter key used by queue IDs and lookups."""
    return "".join(value.split()).upper()


class AdjudicationStatus(StrEnum):
    """Lifecycle status of one thesis discrepancy."""

    OPEN = "OPEN"
    ACCEPTED_A = "ACCEPTED_A"
    ACCEPTED_B = "ACCEPTED_B"
    MERGED = "MERGED"
    REJECTED = "REJECTED"


class ResolutionEvent(BaseModel):
    """One immutable human resolution event retained for audit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AdjudicationStatus
    note: str | None
    timestamp: datetime


class AdjudicationEntry(BaseModel):
    """One durable human decision over a model discrepancy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    stock: str
    quarter: str
    discrepancy: Discrepancy
    status: AdjudicationStatus
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    history: tuple[ResolutionEvent, ...] = ()
    superseded: bool = False


class AdjudicationQueue(BaseModel):
    """Versioned collection persisted in the single adjudication JSON file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=_QUEUE_SCHEMA_VERSION, strict=True)
    entries: tuple[AdjudicationEntry, ...] = ()


def _hash_content(stock: str, quarter: str, discrepancy: dict[str, object]) -> str:
    """Return a SHA-256 over canonical queue-key and discrepancy content."""
    content = {
        "stock": normalize_queue_key(stock),
        "quarter": normalize_queue_key(quarter),
        "discrepancy": discrepancy,
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_hash_text(value: str) -> str:
    """Collapse whitespace and case-fold text used by a stable ID."""
    return " ".join(value.split()).casefold()


def _legacy_discrepancy_id(stock: str, quarter: str, discrepancy: Discrepancy) -> str:
    """Return the pre-migration ID so valid legacy queue rows can be recognized."""
    normalized_discrepancy = discrepancy.model_dump(mode="json")
    for field in ("model_a_points", "model_b_points"):
        normalized_discrepancy[field] = sorted(
            {_normalize_hash_text(point) for point in normalized_discrepancy[field]}
        )
    return _hash_content(stock, quarter, normalized_discrepancy)


def discrepancy_id(stock: str, quarter: str, discrepancy: Discrepancy) -> str:
    """Return a stable SHA-256 over stock, quarter, and normalized discrepancy content."""
    normalized_discrepancy = {
        field: _normalize_hash_text(value) if isinstance(value, str) else value
        for field, value in discrepancy.model_dump(mode="json").items()
    }
    for field in ("model_a_points", "model_b_points"):
        normalized_discrepancy[field] = sorted(
            {_normalize_hash_text(point) for point in normalized_discrepancy[field]}
        )
    return _hash_content(stock, quarter, normalized_discrepancy)


def _entry_sort_key(entry: AdjudicationEntry) -> tuple[str, str, str, str]:
    """Return the deterministic ordering key for persisted queue entries."""
    return (entry.stock, entry.quarter, entry.discrepancy.section, entry.id)


def _load_adjudication_queue_unlocked(path: Path) -> AdjudicationQueue:
    """Load, validate, and migrate a queue while the caller owns its lock."""
    if path.exists() and not path.is_file():
        raise ValueError(f"adjudication queue path is not a file: {path}")
    if not path.exists():
        return AdjudicationQueue()
    queue = AdjudicationQueue.model_validate_json(path.read_text(encoding="utf-8"))
    if queue.schema_version != _QUEUE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported adjudication queue schema_version: "
            f"{queue.schema_version}; expected {_QUEUE_SCHEMA_VERSION}"
        )
    stored_ids: set[str] = set()
    migrated_ids: set[str] = set()
    entries: list[AdjudicationEntry] = []
    changed = False
    for entry in queue.entries:
        if entry.id in stored_ids:
            raise ValueError(f"duplicate adjudication entry id: {entry.id}")
        stored_ids.add(entry.id)
        expected = discrepancy_id(entry.stock, entry.quarter, entry.discrepancy)
        if entry.id == expected:
            migrated_entry = entry
        elif entry.id == _legacy_discrepancy_id(entry.stock, entry.quarter, entry.discrepancy):
            migrated_entry = entry.model_copy(update={"id": expected})
            changed = True
            _LOGGER.info("adjudication_id_migrated", old_id=entry.id, new_id=expected)
        else:
            raise ValueError(f"adjudication entry id mismatch for {entry.id}: expected {expected}")
        if migrated_entry.id in migrated_ids:
            raise ValueError(
                f"duplicate adjudication entry id after migration: {migrated_entry.id}"
            )
        migrated_ids.add(migrated_entry.id)
        entries.append(migrated_entry)
    if not changed:
        return queue
    migrated = AdjudicationQueue(entries=tuple(sorted(entries, key=_entry_sort_key)))
    _write_adjudication_queue(path, migrated)
    return migrated


def load_adjudication_queue(path: Path) -> AdjudicationQueue:
    """Load and validate the queue, migrating valid legacy IDs under a file lock."""
    if not path.exists():
        return AdjudicationQueue()
    with _locked_queue(path):
        return _load_adjudication_queue_unlocked(path)


def entries_for_stock_quarter(
    queue: AdjudicationQueue, *, stock: str, quarter: str
) -> tuple[AdjudicationEntry, ...]:
    """Return deterministic queue entries scoped to one stock-quarter."""
    return tuple(
        entry
        for entry in queue.entries
        if normalize_queue_key(entry.stock) == normalize_queue_key(stock)
        and normalize_queue_key(entry.quarter) == normalize_queue_key(quarter)
    )


def _write_adjudication_queue(path: Path, queue: AdjudicationQueue) -> None:
    """Atomically replace the queue file so readers never observe partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(queue.model_dump_json(indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


@contextmanager
def _locked_queue(path: Path) -> Iterator[None]:
    """Hold one advisory lock for a complete queue read-modify-write transaction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def upsert_discrepancies(
    path: Path,
    *,
    stock: str,
    quarter: str,
    discrepancies: Sequence[Discrepancy],
    update_supersession: bool = True,
    now: datetime | None = None,
) -> AdjudicationQueue:
    """Append unseen discrepancies as OPEN without changing existing decisions."""
    canonical_stock = normalize_queue_key(stock)
    canonical_quarter = normalize_queue_key(quarter)
    current_ids = {
        discrepancy_id(canonical_stock, canonical_quarter, discrepancy)
        for discrepancy in discrepancies
    }
    with _locked_queue(path):
        queue = _load_adjudication_queue_unlocked(path)
        entries_by_id: dict[str, AdjudicationEntry] = {}
        changed = False
        for entry in queue.entries:
            updated_entry = entry
            is_target = (
                normalize_queue_key(entry.stock) == canonical_stock
                and normalize_queue_key(entry.quarter) == canonical_quarter
            )
            if update_supersession and is_target and entry.status is not AdjudicationStatus.OPEN:
                superseded = entry.id not in current_ids
                if entry.superseded != superseded:
                    updated_entry = entry.model_copy(update={"superseded": superseded})
                    changed = True
            entries_by_id[entry.id] = updated_entry

        timestamp = now if now is not None else datetime.now(UTC)
        for discrepancy in discrepancies:
            entry_id = discrepancy_id(canonical_stock, canonical_quarter, discrepancy)
            if entry_id in entries_by_id:
                continue
            entries_by_id[entry_id] = AdjudicationEntry(
                id=entry_id,
                stock=canonical_stock,
                quarter=canonical_quarter,
                discrepancy=discrepancy,
                status=AdjudicationStatus.OPEN,
                created_at=timestamp,
                updated_at=timestamp,
            )
            changed = True
        updated = AdjudicationQueue(
            entries=tuple(sorted(entries_by_id.values(), key=_entry_sort_key))
        )
        if changed:
            _write_adjudication_queue(path, updated)
        return updated


def resolve_adjudication(
    path: Path,
    *,
    entry_id: str,
    status: AdjudicationStatus,
    note: str | None = None,
    now: datetime | None = None,
) -> AdjudicationQueue:
    """Persist a human resolution for one queue entry."""
    if status is AdjudicationStatus.OPEN:
        raise ValueError("a resolution status cannot be OPEN")
    normalized_note = note.strip() if note is not None and note.strip() else None
    with _locked_queue(path):
        queue = _load_adjudication_queue_unlocked(path)
        timestamp = now if now is not None else datetime.now(UTC)
        updated_entries: list[AdjudicationEntry] = []
        found = False
        for entry in queue.entries:
            if entry.id != entry_id:
                updated_entries.append(entry)
                continue
            found = True
            effective_note = normalized_note if normalized_note is not None else entry.note
            history = entry.history
            if not history and entry.status is not AdjudicationStatus.OPEN:
                history = (
                    ResolutionEvent(
                        status=entry.status,
                        note=entry.note,
                        timestamp=entry.updated_at,
                    ),
                )
            event = ResolutionEvent(status=status, note=effective_note, timestamp=timestamp)
            updated_entries.append(
                entry.model_copy(
                    update={
                        "status": status,
                        "note": effective_note,
                        "updated_at": timestamp,
                        "history": (*history, event),
                    }
                )
            )
        if not found:
            raise ValueError(f"adjudication entry not found: {entry_id}")
        updated = AdjudicationQueue(entries=tuple(sorted(updated_entries, key=_entry_sort_key)))
        _write_adjudication_queue(path, updated)
        return updated
