"""Lossless import of legacy SQLite fact stores into PostgreSQL (data spec §6 steps 1-5).

A manifest names the exact files and fingerprints. Each file is opened read-only, never through
``FactStore``, and hashed before and after reading. The preflight only reads. The import runs in
one serialisable transaction: gate, raw-table copy, then ``verify_import`` and a recomputed
preflight before commit. No identity is recomputed into storage: the copy is the legacy text.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import psycopg
import structlog
import yaml
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import TRANSLATION_VERSION, translate, translation_sha256
from fundamentals.compare.run_models import DatabaseIdentity
from fundamentals.contracts.fact import CanonicalStatus, Fact
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.pg.approvals import (
    GatedOperation,
    GateRefusal,
    GateRefusedError,
    authorize,
    check_approval,
    current_database,
    load_approved,
    split_approval,
)
from fundamentals.pg.settings import PgSettings
from fundamentals.store.fact_store import (
    CanonicalSelection,
    FactStore,
    selection_digest,
    verify_chain,
)
from fundamentals.store.snapshot_store import SnapshotStore

ORIGIN_PREFIX = "sqlite-"
LEGACY_BASELINE_REASON = "legacy baseline"
FACT_COLUMNS = (
    "row_id", "content_identity", "value_hash", "revision_family", "revision_ordinal",
    "canonical_status", "canonical_selected_at", "canonical_reason", "source_id", "file_sha256",
    "anchor", "valid_time_start", "valid_time_end", "knowledge_time", "first_seen_time",
    "fact_json", "created_at",
)  # fmt: skip
SELECTION_COLUMNS = (
    "selection_id", "content_identity", "row_id", "sequence", "predecessor_id", "selected_at",
    "reason", "legacy_baseline", "selection_sha256",
)  # fmt: skip

_HAS_SELECTIONS = (
    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'canonical_selections'"
)
_ENTITY = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
_CAPTURE = (
    "SELECT id, blob_sha256 FROM eqos.capture_refs WHERE blob_sha256 = %s ORDER BY id LIMIT 1"
)
_IMPORTED = "SELECT 1 FROM eqos.legacy_imports WHERE store_id = %s"
_LABEL_CONFLICT = (
    "SELECT 1 FROM eqos.fact_stores WHERE kind = 'LEGACY_SQLITE' AND file_label = %s "
    "AND file_sha256 <> %s"
)
_INSERT_STORE = (
    "INSERT INTO eqos.fact_stores (store_id, kind, file_label, file_sha256) "
    "VALUES (%s, 'LEGACY_SQLITE', %s, %s)"
)
_INSERT_ROW = """
INSERT INTO eqos.fact_rows (target_store, handle, origin, origin_id, content_identity, value_hash,
    revision_family, revision_ordinal, canonical_status, canonical_selected_at, canonical_reason,
    source_id, file_sha256, anchor, valid_time_start, valid_time_end, knowledge_time,
    first_seen_time, fact_json, created_at)
VALUES (%(store)s, %(row_id)s, %(store)s, %(row_id)s, %(content_identity)s, %(value_hash)s,
    %(revision_family)s, %(revision_ordinal)s, %(canonical_status)s, %(canonical_selected_at)s,
    %(canonical_reason)s, %(source_id)s, %(file_sha256)s, %(anchor)s, %(valid_time_start)s,
    %(valid_time_end)s, %(knowledge_time)s, %(first_seen_time)s, %(fact_json)s, %(created_at)s)
"""
_INSERT_SELECTION = """
INSERT INTO eqos.fact_selections (target_store, handle, origin, origin_id, content_identity,
    row_handle, sequence, predecessor_handle, selected_at, reason, legacy_baseline, synthesized,
    selection_sha256)
VALUES (%(store)s, %(selection_id)s, %(store)s, %(selection_id)s, %(content_identity)s,
    %(row_id)s, %(sequence)s, %(predecessor_id)s, %(selected_at)s, %(reason)s,
    %(legacy_baseline)s <> 0, %(synthesized)s, %(selection_sha256)s)
"""
_INSERT_TRANSLATION = """
INSERT INTO eqos.legacy_fact_translations (target_store, row_handle, translation_version,
    entity_id, canonical_id, period_start, period_end, period_instant, basis, framework,
    currency, value_kind, dimension_set)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_INSERT_BINDING = (
    "INSERT INTO eqos.legacy_evidence_bindings (target_store, row_handle, capture_ref_id, "
    "file_sha256, anchor) VALUES (%s, %s, %s, %s, %s)"
)
_INSERT_IMPORT = (
    "INSERT INTO eqos.legacy_imports (store_id, manifest_sha256, preflight_sha256, file_sha256) "
    "VALUES (%s, %s, %s, %s)"
)
_INSERT_EVENT = """
INSERT INTO eqos.fact_store_events (store_id, operation_id, state, approval_sha256,
    owner_record_sha256, last_row_handle, last_selection_handle, recorded_at)
VALUES (%s, %s, 'IMPORTED', %s, %s, %s, %s, eqos.store_now())
"""
_COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.fact_rows WHERE target_store = ANY(%(s)s)), "
    "(SELECT count(*) FROM eqos.fact_selections WHERE target_store = ANY(%(s)s))"
)
_FINGERPRINT = "SELECT file_sha256 FROM eqos.fact_stores WHERE store_id = %s"
_STORE_ROWS = """
SELECT handle, origin, origin_id AS row_id, content_identity, value_hash, revision_family,
    revision_ordinal, canonical_status, canonical_selected_at, canonical_reason, source_id,
    file_sha256, anchor, valid_time_start, valid_time_end, knowledge_time, first_seen_time,
    fact_json, created_at
FROM eqos.fact_rows WHERE target_store = %s AND origin = target_store ORDER BY handle
"""
_STORE_SELECTIONS = """
SELECT handle, origin, origin_id AS selection_id, content_identity, row_handle AS row_id,
    sequence, predecessor_handle AS predecessor_id, selected_at, reason,
    legacy_baseline::int AS legacy_baseline, selection_sha256, synthesized
FROM eqos.fact_selections WHERE target_store = %s AND origin = target_store
ORDER BY handle
"""
_STORE_BINDINGS = """
SELECT b.row_handle, b.file_sha256, b.anchor, c.source_id, c.surface, c.request_key,
    c.capture_id, c.blob_sha256
FROM eqos.legacy_evidence_bindings b JOIN eqos.capture_refs c ON c.id = b.capture_ref_id
WHERE b.target_store = %s ORDER BY b.row_handle
"""
_TRANSLATED = "SELECT count(*) AS n FROM eqos.legacy_fact_translations WHERE target_store = %s"
_STATE = "SELECT state FROM eqos.fact_store_events WHERE store_id = %s ORDER BY id DESC LIMIT 1"

_log = structlog.get_logger("fundamentals.pg.legacy_import")
_Rows = list[dict[str, Any]]


class ImportRefusal(StrEnum):
    """Why an import (or its preflight) refused."""

    FINGERPRINT_CHANGED = "FINGERPRINT_CHANGED"
    FINGERPRINT_CONFLICT = "FINGERPRINT_CONFLICT"
    PREFLIGHT_NOT_CLEAN = "PREFLIGHT_NOT_CLEAN"
    NO_BASELINE_TIME = "NO_BASELINE_TIME"
    MULTIPLE_BASELINES = "MULTIPLE_BASELINES"
    ROW_MISMATCH = "ROW_MISMATCH"
    CHAIN_INVALID = "CHAIN_INVALID"


class LegacyImportRefusedError(Exception):
    """The import refused; its transaction wrote nothing."""

    def __init__(self, reason: ImportRefusal) -> None:
        """Carry the refusal reason."""
        super().__init__(reason.value)
        self.reason = reason


class SchemaKind(StrEnum):
    """Whether the file predates ``canonical_selections``."""

    PRE_SELECTION = "PRE_SELECTION"
    SELECTIONS = "SELECTIONS"


class ManifestFile(BaseModel):
    """One exact legacy file to import."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    path: Path
    sha256: str
    new_import: bool = False


class LegacyImportManifest(BaseModel):
    """The approved list of files, and the snapshot store holding their originals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    files: tuple[ManifestFile, ...]
    snapshot_root: Path


class FileReport(BaseModel):
    """What the preflight found in one file."""

    model_config = ConfigDict(frozen=True)

    label: str
    sha256: str
    origin_id: str
    rows: int
    selections: int
    schema_kind: SchemaKind
    unresolved_originals: tuple[str, ...]
    untranslatable_rows: tuple[int, ...]


class EvidenceBinding(BaseModel):
    """A legacy ``file_sha256`` resolved to a registered capture."""

    model_config = ConfigDict(frozen=True)

    file_sha256: str
    capture_ref_id: int
    blob_sha256: str


class PreflightReport(BaseModel):
    """The deterministic, approvable preflight: no wall-clock time."""

    model_config = ConfigDict(frozen=True)

    manifest_sha256: str
    database: DatabaseIdentity
    translation_version: str
    translation_sha256: str
    files: tuple[FileReport, ...]
    bindings: tuple[EvidenceBinding, ...]

    def clean(self) -> bool:
        """No unresolved original and no untranslatable row in any file."""
        return not any(f.unresolved_originals or f.untranslatable_rows for f in self.files)

    def to_yaml(self) -> bytes:
        """The report's canonical bytes."""
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=True).encode()


class ImportResult(BaseModel):
    """The manifest's stores, their row and selection counts, and whether any was new."""

    model_config = ConfigDict(frozen=True)

    stores: tuple[str, ...]
    rows: int
    selections: int
    created: bool


class ImportCheck(BaseModel):
    """What ``verify_import`` proved equal."""

    model_config = ConfigDict(frozen=True)

    rows: int
    selections: int
    bindings: int


_Survey = tuple[ManifestFile, SchemaKind, _Rows, _Rows, dict[int, MeasurementKey]]


def origin_id_for(sha256: str) -> str:
    """The origin (and store) id of a legacy file."""
    return ORIGIN_PREFIX + sha256[:16]


def row_sha256(columns: Mapping[str, object]) -> str:
    """A stable digest over one row's columns."""
    return _sha(json.dumps(dict(columns), sort_keys=True, separators=(",", ":")).encode())


def load_manifest(path: Path) -> LegacyImportManifest:
    """The manifest payload, with or without its approval line."""
    return LegacyImportManifest.model_validate(yaml.safe_load(split_approval(path.read_bytes())[0]))


def preflight(
    manifest_path: Path, *, root: Path, conn: psycopg.Connection[Any], settings: PgSettings
) -> PreflightReport:
    """Read every listed file and resolve its originals and translations; write nothing."""
    return _survey(manifest_path, root=root, conn=conn, settings=settings)[1]


def import_legacy(
    manifest_path: Path,
    preflight_path: Path,
    *,
    root: Path,
    pool: ConnectionPool,
    settings: PgSettings,
    owner_path: Path | None = None,
) -> ImportResult:
    """Copy each approved file into its own store and prove it before commit."""
    _, manifest_approval = load_approved(manifest_path)
    with pool.connection() as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        check_approval(manifest_approval, database=current_database(conn))
        payload = authorize(
            conn,
            GatedOperation.IMPORT,
            approval_path=preflight_path,
            owner_path=owner_path,
            settings=settings,
        )
        approved = PreflightReport.model_validate(yaml.safe_load(payload))
        if approved.manifest_sha256 != manifest_approval.payload_sha256:
            raise GateRefusedError(GateRefusal.PAYLOAD_MISMATCH)
        if not approved.clean():
            raise LegacyImportRefusedError(ImportRefusal.PREFLIGHT_NOT_CLEAN)
        manifest, report, surveyed = _survey(manifest_path, root=root, conn=conn, settings=settings)
        snapshots = SnapshotStore(root / manifest.snapshot_root)
        captures = {binding.file_sha256: binding.capture_ref_id for binding in report.bindings}
        owner_sha = _sha(owner_path.read_bytes()) if owner_path is not None else None
        operation, created = uuid.uuid4(), False
        for file, kind, rows, selections, keys in surveyed:
            store = origin_id_for(file.sha256)
            if conn.execute(_IMPORTED, (store,)).fetchone() is not None:
                continue
            conflict = conn.execute(_LABEL_CONFLICT, (file.label, file.sha256)).fetchone()
            if conflict is not None and not file.new_import:
                raise LegacyImportRefusedError(ImportRefusal.FINGERPRINT_CONFLICT)
            synthesized = kind is SchemaKind.PRE_SELECTION
            with conn.cursor() as cursor:
                cursor.execute(_INSERT_STORE, (store, file.label, file.sha256))
                cursor.executemany(_INSERT_ROW, [row | {"store": store} for row in rows])
                cursor.executemany(
                    _INSERT_SELECTION,
                    [item | {"store": store, "synthesized": synthesized} for item in selections],
                )
                cursor.executemany(
                    _INSERT_TRANSLATION, [_translation(store, h, k) for h, k in keys.items()]
                )
                cursor.executemany(
                    _INSERT_BINDING,
                    [
                        (store, row["row_id"], captures[row["file_sha256"]], row["file_sha256"],
                         row["anchor"])
                        for row in rows
                    ],
                )  # fmt: skip
                cursor.execute(
                    _INSERT_IMPORT, (store, approved.manifest_sha256, _sha(payload), file.sha256)
                )
                last_row = max((row["row_id"] for row in rows), default=None)
                last_selection = max((item["selection_id"] for item in selections), default=None)
                cursor.execute(
                    _INSERT_EVENT,
                    (store, operation, _sha(payload), owner_sha, last_row, last_selection),
                )
            verify_import(conn, store, root / file.path, snapshots=snapshots)
            created = True
        if preflight(manifest_path, root=root, conn=conn, settings=settings).to_yaml() != payload:
            raise GateRefusedError(GateRefusal.APPROVAL_STALE)
        stores = tuple(origin_id_for(file.sha256) for file in manifest.files)
        counts = conn.execute(_COUNTS, {"s": list(stores)}).fetchone()
        assert counts is not None
    result = ImportResult(stores=stores, rows=counts[0], selections=counts[1], created=created)
    _log.info("legacy_import_committed", operation_id=str(operation), **result.model_dump())
    return result


def verify_import(
    conn: psycopg.Connection[Any], store_id: str, file: Path, *, snapshots: SnapshotStore
) -> ImportCheck:
    """Prove a store's imported rows equal its source file: chains, rows, identities, bindings,
    captures. Native rows (written after reopen) are not read."""
    with conn.cursor(row_factory=dict_row) as cursor:
        found = cursor.execute(_FINGERPRINT, (store_id,)).fetchone()
        if found is None:
            raise LegacyImportRefusedError(ImportRefusal.ROW_MISMATCH)
        kind, rows, selections = _read(file, found["file_sha256"])
        stored = cursor.execute(_STORE_ROWS, (store_id,)).fetchall()
        chosen = cursor.execute(_STORE_SELECTIONS, (store_id,)).fetchall()
        bound = cursor.execute(_STORE_BINDINGS, (store_id,)).fetchall()
        translated = cursor.execute(_TRANSLATED, (store_id,)).fetchone()
    _check_chains(stored, chosen)
    synthesized = kind is SchemaKind.PRE_SELECTION
    if not (
        _same(rows, stored, FACT_COLUMNS, store_id)
        and _same(selections, chosen, SELECTION_COLUMNS, store_id)
        and all(item["synthesized"] is synthesized for item in chosen)
        and translated is not None
        and translated["n"] == len(rows)
        and all(_identity_holds(row) for row in rows)
        and _bindings_hold(rows, bound, snapshots)
    ):
        raise LegacyImportRefusedError(ImportRefusal.ROW_MISMATCH)
    return ImportCheck(rows=len(rows), selections=len(selections), bindings=len(bound))


def store_state(conn: psycopg.Connection[Any], store_id: str) -> str | None:
    """A store's state: its latest event, if any."""
    row = conn.execute(_STATE, (store_id,)).fetchone()
    return None if row is None else str(row[0])


def _survey(
    manifest_path: Path, *, root: Path, conn: psycopg.Connection[Any], settings: PgSettings
) -> tuple[LegacyImportManifest, PreflightReport, list[_Survey]]:
    """Read every file once; return the manifest, the preflight and the data to copy."""
    payload, _ = split_approval(manifest_path.read_bytes())
    manifest = load_manifest(manifest_path)
    entities: dict[str, int | None] = {}
    bindings: dict[str, EvidenceBinding] = {}
    reports, surveyed = [], []
    for file in manifest.files:
        kind, rows, selections = _read(root / file.path, file.sha256)
        keys: dict[int, MeasurementKey] = {}
        for row in rows:
            fact = Fact.model_validate_json(row["fact_json"])
            entity_key = fact.observation.entity_id
            if entity_key not in entities:
                found = conn.execute(_ENTITY, (entity_key,)).fetchone()
                entities[entity_key] = None if found is None else int(found[0])
            entity_id = entities[entity_key]
            key = None if entity_id is None else translate(fact, entity_id=entity_id)
            if key is not None:
                keys[row["row_id"]] = key
        originals = sorted({row["file_sha256"] for row in rows})
        for sha in originals:
            capture = conn.execute(_CAPTURE, (sha,)).fetchone()
            if capture is not None:
                bindings[sha] = EvidenceBinding(
                    file_sha256=sha, capture_ref_id=capture[0], blob_sha256=capture[1]
                )
        reports.append(
            FileReport(
                label=file.label,
                sha256=file.sha256,
                origin_id=origin_id_for(file.sha256),
                rows=len(rows),
                selections=len(selections),
                schema_kind=kind,
                unresolved_originals=tuple(sha for sha in originals if sha not in bindings),
                untranslatable_rows=tuple(r["row_id"] for r in rows if r["row_id"] not in keys),
            )
        )
        surveyed.append((file, kind, rows, selections, keys))
    report = PreflightReport(
        manifest_sha256=_sha(payload),
        database=DatabaseIdentity(
            host=settings.host, port=settings.port, name=current_database(conn)
        ),
        translation_version=TRANSLATION_VERSION,
        translation_sha256=translation_sha256(),
        files=tuple(reports),
        bindings=tuple(sorted(bindings.values(), key=lambda binding: binding.file_sha256)),
    )
    _log.info("legacy_preflight", files=len(reports), clean=report.clean())
    return manifest, report, surveyed


def _read(path: Path, sha256: str) -> tuple[SchemaKind, _Rows, _Rows]:
    """Open read-only between two fingerprint checks; selections verbatim or synthesized."""
    if _sha(path.read_bytes()) != sha256:
        raise LegacyImportRefusedError(ImportRefusal.FINGERPRINT_CHANGED)
    with closing(sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM facts ORDER BY row_id")]
        kind = SchemaKind.SELECTIONS
        if conn.execute(_HAS_SELECTIONS).fetchone() is None:
            kind, selections = SchemaKind.PRE_SELECTION, _synthesize(rows)
        else:
            query = "SELECT * FROM canonical_selections ORDER BY selection_id"
            selections = [dict(row) for row in conn.execute(query)]
    if _sha(path.read_bytes()) != sha256:
        raise LegacyImportRefusedError(ImportRefusal.FINGERPRINT_CHANGED)
    if any(set(row) != set(FACT_COLUMNS) for row in rows) or any(
        set(item) != set(SELECTION_COLUMNS) for item in selections
    ):
        raise LegacyImportRefusedError(ImportRefusal.ROW_MISMATCH)
    return kind, rows, selections


def _synthesize(rows: _Rows) -> _Rows:
    """``FactStore``'s legacy-selection migration, from the stored selection text."""
    selections: _Rows = []
    for row in rows:
        if row["canonical_status"] != CanonicalStatus.CANONICAL:
            continue
        identity = row["content_identity"]
        if any(item["content_identity"] == identity for item in selections):
            raise LegacyImportRefusedError(ImportRefusal.MULTIPLE_BASELINES)
        if not row["canonical_selected_at"]:
            raise LegacyImportRefusedError(ImportRefusal.NO_BASELINE_TIME)
        decision = {
            "content_identity": identity,
            "row_id": row["row_id"],
            "sequence": 1,
            "predecessor_id": None,
            "selected_at": row["canonical_selected_at"],
            "reason": row["canonical_reason"] or LEGACY_BASELINE_REASON,
        }
        digest = selection_digest(
            value_hash=row["value_hash"], predecessor_sha256=None, legacy_baseline=True, **decision
        )
        selections.append(
            {"selection_id": len(selections) + 1, **decision, "legacy_baseline": 1}
            | {"selection_sha256": digest}
        )
    return selections


def _check_chains(stored: _Rows, chosen: _Rows) -> None:
    """Every identity's chain is linear, digest-bound and never precedes its fact's times."""
    targets = {row["handle"]: (row["content_identity"], row["value_hash"]) for row in stored}
    facts = {row["handle"]: Fact.model_validate_json(row["fact_json"]) for row in stored}
    chains: defaultdict[str, list[CanonicalSelection]] = defaultdict(list)
    try:
        for item in chosen:
            chains[item["content_identity"]].append(
                CanonicalSelection(
                    selection_id=item["handle"],
                    content_identity=item["content_identity"],
                    row_id=item["row_id"],
                    sequence=item["sequence"],
                    predecessor_id=item["predecessor_id"],
                    selected_at=datetime.fromisoformat(item["selected_at"]),
                    reason=item["reason"],
                    legacy_baseline=bool(item["legacy_baseline"]),
                    selection_sha256=item["selection_sha256"],
                )
            )
        for identity, decisions in chains.items():
            verify_chain(identity, decisions, targets)
            for decision in decisions:
                fact = facts[decision.row_id]
                if decision.selected_at < max(fact.knowledge_time, fact.first_seen_time):
                    raise ValueError("selection precedes fact knowledge")
    except (ValueError, KeyError, TypeError) as error:
        raise LegacyImportRefusedError(ImportRefusal.CHAIN_INVALID) from error


def _same(source: _Rows, stored: _Rows, columns: Sequence[str], store_id: str) -> bool:
    """Equal counts, and each stored row keeps its origin id as handle and every source column."""
    return len(source) == len(stored) and all(
        row["handle"] == row[columns[0]]
        and row["origin"] == store_id
        and row_sha256({c: row[c] for c in columns}) == row_sha256({c: src[c] for c in columns})
        for src, row in zip(source, stored, strict=True)
    )


def _identity_holds(row: Mapping[str, Any]) -> bool:
    """The stored content identity and value hash recompute from ``fact_json`` (a check only)."""
    observation = Fact.model_validate_json(row["fact_json"]).observation
    return (FactStore.content_identity_for(observation), FactStore.value_hash_for(observation)) == (
        row["content_identity"],
        row["value_hash"],
    )


def _bindings_hold(rows: _Rows, bound: _Rows, snapshots: SnapshotStore) -> bool:
    """Every row is bound to its original, and every bound capture re-hashes."""
    if len(rows) != len(bound) or any(
        (b["row_handle"], b["file_sha256"], b["blob_sha256"], b["anchor"])
        != (row["row_id"], row["file_sha256"], row["file_sha256"], row["anchor"])
        for row, b in zip(rows, bound, strict=True)
    ):
        return False
    captures = {
        (b["source_id"], b["surface"], b["request_key"], b["capture_id"], b["blob_sha256"])
        for b in bound
    }
    return all(
        _sha(snapshots.read_capture_verified(*capture[:4])[1]) == capture[4] for capture in captures
    )


def _translation(store: str, handle: int, key: MeasurementKey) -> tuple[object, ...]:
    """One translation row's parameters."""
    period = key.period
    return (
        store, handle, TRANSLATION_VERSION, key.entity_id, key.canonical_id, period.start,
        period.end, period.instant, key.basis.value, key.framework.value, key.currency,
        key.value_kind.value, Jsonb([list(pair) for pair in key.dimensions.pairs]),
    )  # fmt: skip


def _sha(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()
