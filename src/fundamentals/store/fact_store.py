"""Append-only, revision-aware provenance fact store (SQLite, stdlib only).

Persistence honours the product-doctrine invariant that corrections and
restatements are **never silently overwritten** (roadmap §8):

* Identical content identity **and** identical values -> the existing row is
  returned unchanged (idempotent; no duplicate).
* Same content identity with **different** values -> a new revision is appended
  under the same ``revision_family``; every prior revision is retained.
* Canonical selection is a **separate, auditable step** (``select_canonical``),
  never a side effect of writing. A ``put`` always lands a ``CANDIDATE``.

Content identity is a stable sha256 over an Observation's comparison key
(concept + period + scope + dimensions + currency + unit + scale + accounting
basis + entity). Value identity additionally hashes the value-bearing fields
(raw/normalized value, decimals) and the provenance binding, so a restatement
that changes a value — or its source — produces a new revision rather than a
collision.

No un-provenanced fact may be stored: a Fact whose observation provenance is
missing or whose ``file_sha256`` is empty is rejected fail-closed.

Nor may a fact whose anchor kind has not been admitted to the store. An
``API_DOCUMENT``-anchored observation is currently **barred**: those responses
carry no identity field of their own, so the only binding to an issuer is the id
in the request URL. That is enough to acquire and retain a document, but not to
let a value join the canonical revision chain, where content identity is assumed
to be corroborated by the source. The bar lifts when reconciliation or an
explicit promotion step exists to supply that corroboration.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import assert_never

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.fact import CanonicalStatus, Fact
from fundamentals.contracts.observation import Observation
from fundamentals.contracts.provenance import SourceAnchorType

_TABLE = "facts"

_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_identity TEXT NOT NULL,
    value_hash TEXT NOT NULL,
    revision_family TEXT NOT NULL,
    revision_ordinal INTEGER NOT NULL,
    canonical_status TEXT NOT NULL,
    canonical_selected_at TEXT,
    canonical_reason TEXT,
    source_id TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    anchor TEXT NOT NULL,
    valid_time_start TEXT NOT NULL,
    valid_time_end TEXT,
    knowledge_time TEXT NOT NULL,
    first_seen_time TEXT NOT NULL,
    fact_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_CREATE_UNIQUE_INDEX = (
    f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{_TABLE}_identity_value "
    f"ON {_TABLE} (content_identity, value_hash)"
)

_SELECT_BY_IDENTITY = "SELECT * FROM facts WHERE content_identity = ? ORDER BY revision_ordinal ASC"
_SELECT_BY_IDENTITY_VALUE = "SELECT * FROM facts WHERE content_identity = ? AND value_hash = ?"
_SELECT_BY_ROW_ID = "SELECT * FROM facts WHERE row_id = ?"
_SELECT_MAX_ORDINAL = (
    "SELECT MAX(revision_ordinal) AS max_ordinal FROM facts WHERE content_identity = ?"
)

_INSERT = f"""
INSERT INTO {_TABLE} (
    content_identity, value_hash, revision_family, revision_ordinal,
    canonical_status, canonical_selected_at, canonical_reason,
    source_id, file_sha256, anchor,
    valid_time_start, valid_time_end, knowledge_time, first_seen_time,
    fact_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_CREATE_SELECTIONS = """
CREATE TABLE IF NOT EXISTS canonical_selections (
    selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_identity TEXT NOT NULL,
    row_id INTEGER NOT NULL REFERENCES facts(row_id),
    sequence INTEGER NOT NULL,
    predecessor_id INTEGER REFERENCES canonical_selections(selection_id),
    selected_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    legacy_baseline INTEGER NOT NULL,
    selection_sha256 TEXT NOT NULL,
    UNIQUE(content_identity, sequence),
    UNIQUE(content_identity, selected_at),
    UNIQUE(predecessor_id)
)
"""
_HISTORY = "SELECT * FROM canonical_selections WHERE content_identity = ? ORDER BY sequence"
_APPEND_SELECTION = """
INSERT INTO canonical_selections (
    content_identity, row_id, sequence, predecessor_id, selected_at, reason,
    legacy_baseline, selection_sha256
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


class CanonicalSelectionError(ValueError):
    """A selection is ineligible, ambiguous, backdated, or based on a stale head."""


class CanonicalSelection(BaseModel):
    """One immutable selection; legacy baselines do not reconstruct lost history."""

    model_config = ConfigDict(frozen=True)

    selection_id: int
    content_identity: str
    row_id: int
    sequence: int
    predecessor_id: int | None
    selected_at: datetime
    reason: str
    legacy_baseline: bool
    selection_sha256: str


def _utc(value: datetime) -> datetime:
    """Reject naive/non-UTC temporal inputs instead of guessing their meaning."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("temporal timestamps must be aware UTC")
    return value.astimezone(UTC)


class UnprovenancedFactError(ValueError):
    """Raised when a Fact lacking usable source provenance is offered to the store."""


class BarredAnchorFactError(ValueError):
    """Raised when a Fact whose anchor kind is not admitted to the store is offered."""


# Anchor kinds whose identity binding is too weak to enter the revision chain.
_BARRED_ANCHOR_TYPES: frozenset[SourceAnchorType] = frozenset(
    {SourceAnchorType.API_DOCUMENT, SourceAnchorType.CONFIG_PIN}
)

_BARRED_ANCHOR_REASON = "{anchor} observations are barred from the fact store: {why}"
_BARRED_ANCHOR_WHY: dict[SourceAnchorType, str] = {
    SourceAnchorType.API_DOCUMENT: (
        "the response carries no identity field, so the value is bound to an issuer "
        "only by the id in its request URL. Acquire and retain the document; admit it "
        "here once reconciliation or an explicit promotion step corroborates that "
        "identity."
    ),
    SourceAnchorType.CONFIG_PIN: (
        "a human typed the value into a committed config file and nothing corroborated "
        "it, so admitting it would let an unverified assertion enter the canonical "
        "revision chain. Acquire the same value from a source and admit that instead."
    ),
}


class StoredRevision(BaseModel):
    """One persisted, retained revision within a revision family.

    ``canonical_status`` is projected from immutable selection history (or
    retained legacy metadata), superseding stale status on the embedded ``fact``.
    """

    model_config = ConfigDict(frozen=True)

    row_id: int
    content_identity: str
    value_hash: str
    revision_family: str
    revision_ordinal: int
    canonical_status: CanonicalStatus
    canonical_selected_at: datetime | None
    canonical_reason: str | None
    fact: Fact


def _stable_json(payload: object) -> str:
    """Serialize ``payload`` deterministically for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text: str) -> str:
    """Return the hex sha256 digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _anchor_payload(observation: Observation) -> dict[str, object]:
    """Serialize the complete typed provenance anchor for hashing.

    Every field the declared ``anchor_type`` uses to locate a value must appear
    here: two observations that differ only in where they were read from are
    different observations, and omitting a location field would collapse them
    onto one value hash.
    """
    prov = observation.provenance
    payload: dict[str, object] = {
        "anchor_type": str(prov.anchor_type),
        "context_ref": prov.context_ref,
    }
    if prov.anchor_type is SourceAnchorType.PDF_SPAN:
        payload.update({"page": prov.page, "block": prov.block, "span": prov.span})
    elif prov.anchor_type is SourceAnchorType.XBRL_CONTEXT:
        pass
    elif prov.anchor_type is SourceAnchorType.JSON_ISLAND:
        payload.update(
            {
                "island_id": prov.island_id,
                "table_key": prov.table_key,
                "row_label": prov.row_label,
                "column_label": prov.column_label,
            }
        )
    elif prov.anchor_type is SourceAnchorType.API_DOCUMENT:
        payload.update(
            {
                "document_id": prov.document_id,
                "table_key": prov.table_key,
                "row_label": prov.row_label,
                "column_label": prov.column_label,
            }
        )
    elif prov.anchor_type in (SourceAnchorType.HTML_TABLE, SourceAnchorType.CSV_RECORD):
        payload.update(
            {
                "table_id": prov.table_id,
                "row_path": prov.row_path,
                "row_label": prov.row_label,
                "column_index": prov.column_index,
                "column_label": prov.column_label,
            }
        )
    elif prov.anchor_type is SourceAnchorType.CONFIG_PIN:
        payload.update({"row_label": prov.row_label, "column_label": prov.column_label})
    else:
        assert_never(prov.anchor_type)
    return payload


def _content_identity(observation: Observation) -> str:
    """Stable hash over the comparison key that makes two values comparable."""
    key = {
        "concept_qname": observation.concept_qname,
        "period_type": str(observation.period_type),
        "period_start": observation.period_start.isoformat() if observation.period_start else None,
        "period_end": observation.period_end.isoformat() if observation.period_end else None,
        "period_instant": observation.period_instant.isoformat()
        if observation.period_instant
        else None,
        "scope": str(observation.scope),
        "dimensions": [list(pair) for pair in observation.dimensions],
        "currency": observation.currency,
        "unit": observation.normalized_unit,
        "scale": observation.scale,
        "accounting_basis": str(observation.accounting_basis),
        "entity_scheme": observation.entity_scheme,
        "entity_id": observation.entity_id,
    }
    return _sha256(_stable_json(key))


def _value_hash(observation: Observation) -> str:
    """Stable hash over value-bearing fields plus the provenance binding."""
    prov = observation.provenance
    payload = {
        "raw_value": observation.raw_value,
        "normalized_value": str(observation.normalized_value),
        "decimals": observation.decimals,
        "source_id": prov.source_id,
        "file_sha256": prov.file_sha256,
        "anchor": _anchor_payload(observation),
    }
    return _sha256(_stable_json(payload))


class FactStore:
    """SQLite-backed append-only, revision-aware fact store.

    One connection is owned per instance; all SQL is parameterized. Construct
    against a file path or ``":memory:"``.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Open (or create) the store and ensure its schema exists."""
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            self._init_schema()
        except Exception:
            self._conn.close()
            raise

    def _init_schema(self) -> None:
        """Atomically migrate legacy selections and install append-only storage."""
        with self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(_CREATE_TABLE)
            self._conn.execute(_CREATE_UNIQUE_INDEX)
            exists = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'canonical_selections'"
            ).fetchone()
            self._conn.execute(_CREATE_SELECTIONS)
            if exists is None:
                self._migrate_legacy_selections()
            for table in ("facts", "canonical_selections"):
                for operation in ("UPDATE", "DELETE"):
                    # Names are fixed internal constants, never caller input.
                    self._conn.execute(
                        f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} "
                        f"BEFORE {operation} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'append-only store'); END"
                    )

    def _migrate_legacy_selections(self) -> None:
        """Import only the surviving current decision, never overwritten selections."""
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE canonical_status = ? ORDER BY row_id",
            (str(CanonicalStatus.CANONICAL),),
        ).fetchall()
        seen: set[str] = set()
        for row in rows:
            identity = str(row["content_identity"])
            if identity in seen:
                raise CanonicalSelectionError("multiple legacy canonical rows in one family")
            seen.add(identity)
            fact = Fact.model_validate_json(row["fact_json"])
            known = max(_utc(fact.knowledge_time), _utc(fact.first_seen_time))
            raw = row["canonical_selected_at"]
            stamp = _utc(datetime.fromisoformat(raw)) if raw else datetime.now(UTC)
            if stamp < known:
                raise CanonicalSelectionError("legacy selection precedes fact knowledge")
            self._append_selection(
                row, stamp, row["canonical_reason"] or "legacy baseline", None, legacy=True
            )

    def _append_selection(
        self,
        target: sqlite3.Row,
        stamp: datetime,
        reason: str,
        predecessor: CanonicalSelection | None,
        *,
        legacy: bool = False,
    ) -> None:
        """Append a digest-bound successor while the write lock is held."""
        sequence = predecessor.sequence + 1 if predecessor else 1
        predecessor_id = predecessor.selection_id if predecessor else None
        digest = self._selection_digest(target, stamp, reason, predecessor, legacy)
        self._conn.execute(
            _APPEND_SELECTION,
            (
                target["content_identity"],
                target["row_id"],
                sequence,
                predecessor_id,
                stamp.isoformat(),
                reason,
                int(legacy),
                digest,
            ),
        )

    @staticmethod
    def _selection_digest(
        target: sqlite3.Row,
        stamp: datetime,
        reason: str,
        predecessor: CanonicalSelection | None,
        legacy: bool,
    ) -> str:
        """Bind the selected value and exact predecessor to immutable decision bytes."""
        payload = {
            "content_identity": target["content_identity"],
            "row_id": target["row_id"],
            "value_hash": target["value_hash"],
            "sequence": predecessor.sequence + 1 if predecessor else 1,
            "predecessor_id": predecessor.selection_id if predecessor else None,
            "predecessor_sha256": predecessor.selection_sha256 if predecessor else None,
            "selected_at": stamp.isoformat(),
            "reason": reason,
            "legacy_baseline": legacy,
        }
        return _sha256(_stable_json(payload))

    def close(self) -> None:
        """Close the owned connection."""
        self._conn.close()

    @staticmethod
    def content_identity_for(observation: Observation) -> str:
        """Public helper: the content-identity key for an observation."""
        return _content_identity(observation)

    def put(self, fact: Fact) -> StoredRevision:
        """Store ``fact`` append-only; never overwrite an existing revision.

        Returns the existing row when an identical content-identity/value pair is
        already present (idempotent); otherwise appends a new ``CANDIDATE``
        revision under the content-identity's revision family and returns it.
        """
        observation = fact.observation
        self._require_provenance(observation)
        _utc(fact.knowledge_time)
        _utc(fact.first_seen_time)

        content_identity = _content_identity(observation)
        value_hash = _value_hash(observation)

        prov = observation.provenance
        stored_fact = fact.model_copy(update={"canonical_status": CanonicalStatus.CANDIDATE})
        with self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                _SELECT_BY_IDENTITY_VALUE, (content_identity, value_hash)
            ).fetchone()
            if existing is not None:
                return self._row_to_revision(existing)
            siblings = self._conn.execute(_SELECT_BY_IDENTITY, (content_identity,)).fetchall()
            revision_family = siblings[0]["revision_family"] if siblings else fact.revision_family
            next_ordinal = self._next_ordinal(content_identity)
            cursor = self._conn.execute(
                _INSERT,
                (
                    content_identity,
                    value_hash,
                    revision_family,
                    next_ordinal,
                    str(CanonicalStatus.CANDIDATE),
                    None,
                    None,
                    prov.source_id,
                    prov.file_sha256,
                    _stable_json(_anchor_payload(observation)),
                    fact.valid_time_start.isoformat(),
                    fact.valid_time_end.isoformat() if fact.valid_time_end else None,
                    fact.knowledge_time.isoformat(),
                    fact.first_seen_time.isoformat(),
                    stored_fact.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )
        row_id = int(cursor.lastrowid or 0)
        inserted = self._conn.execute(_SELECT_BY_ROW_ID, (row_id,)).fetchone()
        return self._row_to_revision(inserted)

    def select_canonical(
        self,
        row_id: int,
        reason: str,
        selected_at: datetime | None = None,
        *,
        expected_selection_id: int | None = None,
    ) -> StoredRevision:
        """Auditably mark one retained revision canonical within its family.

        Times strictly increase; equal-time decisions are rejected, never tied
        by insertion order. ``expected_selection_id=0`` expects an empty chain;
        another ID compares against that exact head. Omission captures the head
        before locking for compatibility with existing callers.
        """
        target = self._conn.execute(_SELECT_BY_ROW_ID, (row_id,)).fetchone()
        if target is None:
            raise KeyError(f"no revision with row_id={row_id}")

        content_identity = target["content_identity"]
        stamp = _utc(selected_at if selected_at is not None else datetime.now(UTC))
        if not reason.strip():
            raise CanonicalSelectionError("selection reason must be non-empty")
        fact = Fact.model_validate_json(target["fact_json"])
        if stamp < max(_utc(fact.knowledge_time), _utc(fact.first_seen_time)):
            raise CanonicalSelectionError("selection precedes fact knowledge/first-seen time")
        history = self.get_selection_history(content_identity)
        expected = expected_selection_id
        if expected is None:
            expected = history[-1].selection_id if history else 0
        with self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            history = self.get_selection_history(content_identity)
            head = history[-1] if history else None
            if expected != (head.selection_id if head else 0):
                raise CanonicalSelectionError("stale canonical selection predecessor")
            if head is not None and stamp <= head.selected_at:
                raise CanonicalSelectionError("selection time must strictly follow predecessor")
            self._append_selection(target, stamp, reason, head)
        updated = self._conn.execute(_SELECT_BY_ROW_ID, (row_id,)).fetchone()
        return self._row_to_revision(updated)

    def get_revisions(self, content_identity: str) -> tuple[StoredRevision, ...]:
        """Return all retained revisions for a content identity, oldest first."""
        rows = self._conn.execute(_SELECT_BY_IDENTITY, (content_identity,)).fetchall()
        return tuple(self._row_to_revision(row) for row in rows)

    def get_selection_history(self, content_identity: str) -> tuple[CanonicalSelection, ...]:
        """Return and verify the immutable linear chain, including legacy baselines."""
        rows = self._conn.execute(_HISTORY, (content_identity,)).fetchall()
        result: list[CanonicalSelection] = []
        for row in rows:
            decision = CanonicalSelection(
                selection_id=row["selection_id"],
                content_identity=row["content_identity"],
                row_id=row["row_id"],
                sequence=row["sequence"],
                predecessor_id=row["predecessor_id"],
                selected_at=_utc(datetime.fromisoformat(row["selected_at"])),
                reason=row["reason"],
                legacy_baseline=bool(row["legacy_baseline"]),
                selection_sha256=row["selection_sha256"],
            )
            predecessor = result[-1] if result else None
            target = self._conn.execute(_SELECT_BY_ROW_ID, (decision.row_id,)).fetchone()
            if (
                target is None
                or target["content_identity"] != content_identity
                or decision.sequence != len(result) + 1
                or decision.predecessor_id != (predecessor.selection_id if predecessor else None)
                or (predecessor is not None and decision.selected_at <= predecessor.selected_at)
            ):
                raise CanonicalSelectionError("invalid canonical selection chain")
            digest = self._selection_digest(
                target, decision.selected_at, decision.reason, predecessor, decision.legacy_baseline
            )
            if digest != decision.selection_sha256:
                raise CanonicalSelectionError("canonical selection digest mismatch")
            result.append(decision)
        return tuple(result)

    def get_canonical(
        self,
        content_identity: str,
        *,
        cutoff: datetime | None = None,
    ) -> StoredRevision | None:
        """Return the decision effective at cutoff, with eligible recorded fact times."""
        stamp = _utc(cutoff) if cutoff is not None else datetime.now(UTC)
        history = self.get_selection_history(content_identity)
        eligible = [decision for decision in history if decision.selected_at <= stamp]
        if not eligible:
            return None
        decision = eligible[-1]
        row = self._conn.execute(_SELECT_BY_ROW_ID, (decision.row_id,)).fetchone()
        fact = Fact.model_validate_json(row["fact_json"])
        if max(_utc(fact.knowledge_time), _utc(fact.first_seen_time)) > stamp:
            return None
        return self._row_to_revision(row, decision=decision)

    def query_canonical(self, *, cutoff: datetime | None = None) -> tuple[StoredRevision, ...]:
        """Return one cutoff-eligible selected revision per existing content identity."""
        stamp = _utc(cutoff) if cutoff is not None else datetime.now(UTC)
        # A read transaction gives all families the same database snapshot.
        with self._conn:
            self._conn.execute("BEGIN")
            identities = self._conn.execute(
                "SELECT DISTINCT content_identity FROM canonical_selections"
            ).fetchall()
            revisions = [
                self.get_canonical(row["content_identity"], cutoff=stamp) for row in identities
            ]
        return tuple(
            sorted((row for row in revisions if row is not None), key=lambda row: row.row_id)
        )

    def _next_ordinal(self, content_identity: str) -> int:
        """Return the next revision ordinal within a content identity (1-based)."""
        row = self._conn.execute(_SELECT_MAX_ORDINAL, (content_identity,)).fetchone()
        current = row["max_ordinal"] if row is not None else None
        return 1 if current is None else int(current) + 1

    @staticmethod
    def _require_provenance(observation: Observation) -> None:
        """Fail closed on any un-provenanced observation."""
        provenance = getattr(observation, "provenance", None)
        if provenance is None:
            raise UnprovenancedFactError("observation is missing provenance")
        if not provenance.file_sha256:
            raise UnprovenancedFactError("provenance.file_sha256 must be non-empty")
        if provenance.anchor_type in _BARRED_ANCHOR_TYPES:
            raise BarredAnchorFactError(
                _BARRED_ANCHOR_REASON.format(
                    anchor=provenance.anchor_type.value,
                    why=_BARRED_ANCHOR_WHY[provenance.anchor_type],
                )
            )

    def _row_to_revision(
        self,
        row: sqlite3.Row,
        *,
        decision: CanonicalSelection | None = None,
    ) -> StoredRevision:
        """Project current status without mutating fact or historical decision rows."""
        status = CanonicalStatus(row["canonical_status"])
        selected_raw = row["canonical_selected_at"]
        selected_at = datetime.fromisoformat(selected_raw) if selected_raw else None
        reason = row["canonical_reason"]
        if decision is None:
            history = self.get_selection_history(row["content_identity"])
            own = [item for item in history if item.row_id == row["row_id"]]
            if own:
                decision = own[-1]
                status = (
                    CanonicalStatus.CANONICAL
                    if history[-1] == decision
                    else CanonicalStatus.SUPERSEDED
                )
        else:
            status = CanonicalStatus.CANONICAL
        if decision is not None:
            selected_at = decision.selected_at
            reason = decision.reason
        fact = Fact.model_validate_json(row["fact_json"]).model_copy(
            update={"canonical_status": status}
        )
        return StoredRevision(
            row_id=int(row["row_id"]),
            content_identity=row["content_identity"],
            value_hash=row["value_hash"],
            revision_family=row["revision_family"],
            revision_ordinal=int(row["revision_ordinal"]),
            canonical_status=status,
            canonical_selected_at=selected_at,
            canonical_reason=reason,
            fact=fact,
        )
