"""Import of the retained Apar versions into the ledger (ledger spec §1 Import; plan D6-D8).

Runs as the panel role, with no model call. The retrieval manifest's acquisitions are recorded
first (D8). Every version is mapped in memory (:mod:`fundamentals.ledger.import_mapping`); each
that maps losslessly then persists in its own transaction: report, version with its import
sources, QA records, ``IMPORT_SEAL`` and, for Q0 when the evidence rule holds,
``IMPORTED_APPROVAL``. Each then gets a ``RETROSPECTIVE`` validation. A version that does not
map persists nothing.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, LiteralString

import structlog
import yaml
from psycopg import Cursor
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    DecisionKind,
    NumericClaim,
    ReportKind,
    SubjectKind,
    VersionDraft,
    VersionStatus,
)
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.ledger import store
from fundamentals.ledger.claim_check import cutoff_instant
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.import_mapping import (
    UPDATE_FILES,
    LosslessError,
    MappedVersion,
    map_earnings_update,
    map_q0,
)
from fundamentals.ledger.lifecycle import validate, version_status
from fundamentals.store.snapshot_store import SnapshotStore

IMPORT_AUTHOR = "ledger-import"
GIT_TIMEOUT_SECONDS = 30
_ENTITY: LiteralString = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
# A reported value's fact: its key's translation, in the claim's source file.
_FACT: LiteralString = """SELECT f.origin, f.origin_id FROM eqos.fact_rows f
JOIN eqos.legacy_fact_translations t ON t.target_store = f.target_store AND t.row_handle = f.handle
WHERE f.file_sha256 = %s AND t.entity_id = %s AND t.canonical_id = %s AND t.period_start = %s
    AND t.period_end = %s AND t.basis = %s AND t.framework = %s AND t.currency = %s
    AND t.value_kind = %s AND t.dimension_set = '[]'::jsonb
ORDER BY f.origin_id LIMIT 1"""
_CAPTURE: LiteralString = (
    "SELECT id FROM eqos.capture_refs WHERE blob_sha256 = %s ORDER BY id LIMIT 1"
)
_log = structlog.get_logger(__name__)
_Files = tuple[tuple[str, bytes], ...]


class Q0Import(BaseModel):
    """The Q0 thesis files, cutoff and the evidence binding the owner's ruling to them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    period: str
    markdown: str
    twin: str
    cutoff: date
    evidence_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decided_on: date
    ruling: str


class ImportConfig(BaseModel):
    """``config/ledger_import.yaml``: repo-relative source paths and pins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stock: str
    retrieval_manifest: str
    retrieval_manifest_sha256: str
    management_ledger: str
    reports_dir: str
    earnings_updates: tuple[str, ...]
    q0: Q0Import


class ImportedVersion(BaseModel):
    """One version's import outcome: its id and status, or why it did not map."""

    model_config = ConfigDict(frozen=True)

    period: str
    kind: ReportKind
    version_id: int | None = None
    status: VersionStatus | None = None
    failure: str | None = None


def load_import_config(path: Path) -> ImportConfig:
    """The import config from its YAML file."""
    return ImportConfig.model_validate(yaml.safe_load(path.read_text()))


def import_versions(
    pool: ConnectionPool,
    config: ImportConfig,
    *,
    repo: Path,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> tuple[ImportedVersion, ...]:
    """Import every configured version through ``pool`` (the panel role); paths are relative
    to ``repo``, whose git history holds the Q0 evidence."""

    def sources(*paths: str) -> tuple[tuple[str, bytes], ...]:
        return tuple((path, (repo / path).read_bytes()) for path in paths)

    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        ((_, body),) = sources(config.retrieval_manifest)
        store.insert_acquisitions(cursor, body, expected_sha256=config.retrieval_manifest_sha256)
        row = cursor.execute(_ENTITY, (config.stock,)).fetchone()
        assert row is not None, config.stock
        entity_id = int(row[0])
    retained = frozenset(entry["sha256"] for entry in json.loads(body)["entries"])
    ((_, ledger),) = sources(config.management_ledger)
    mapped: dict[str, MappedVersion] = {}
    outcomes: list[tuple[str, ReportKind, _Files, MappedVersion | LosslessError]] = []
    for period in config.earnings_updates:
        files = sources(*(f"{config.reports_dir}/{period}/{name}" for name in UPDATE_FILES))
        files += sources(config.management_ledger)
        try:
            mapped[period] = map_earnings_update(
                files[0][1],
                files[1][1],
                ledger,
                period=period,
                entity_id=entity_id,
                mapped_quarters=mapped,
                retained=retained,
            )
            outcomes.append((period, ReportKind.EARNINGS_UPDATE, files, mapped[period]))
        except LosslessError as failure:
            outcomes.append((period, ReportKind.EARNINGS_UPDATE, files, failure))
    q0 = config.q0
    files = sources(q0.markdown, q0.twin)
    try:
        thesis: MappedVersion | LosslessError = map_q0(files[0][1], files[1][1], cutoff=q0.cutoff)
    except LosslessError as failure:
        thesis = failure
    outcomes.append((q0.period, ReportKind.BOOTSTRAP_THESIS, files, thesis))
    results = []
    for period, kind, files, version in outcomes:
        if isinstance(version, LosslessError):
            _log.error("ledger_import_refused", period=period, kind=kind, detail=str(version))
            results.append(ImportedVersion(period=period, kind=kind, failure=str(version)))
            continue
        approval = None
        if kind is ReportKind.BOOTSTRAP_THESIS:
            approval = evidence_holds(repo, q0.evidence_commit, dict(files), q0.decided_on)
        version_id = _persist(pool, version, files, entity_id, period, kind, approval, q0)
        validate(
            pool,
            version_id,
            mode=RunMode.RETROSPECTIVE,
            catalog=catalog,
            snapshots=snapshots,
            bound=dict(version.bound),
        )
        with pool.connection() as conn, conn.cursor() as cursor:
            status = version_status(cursor, version_id)
        _log.info("ledger_version_imported", period=period, kind=kind, version_id=version_id)
        results.append(
            ImportedVersion(period=period, kind=kind, version_id=version_id, status=status)
        )
    return tuple(results)


def evidence_holds(
    repo: Path, commit: str, files: Mapping[str, bytes], decided_on: date
) -> str | None:
    """The original approval hash (the files' SHA-256s, comma-joined in order) when ``commit``
    holds exactly these bytes at these paths and was committed on ``decided_on`` (UTC); else
    ``None``."""
    try:
        stamp = _git(repo, "show", "-s", "--format=%cI", commit).decode().strip()
        held = all(_git(repo, "show", f"{commit}:{path}") == body for path, body in files.items())
    except subprocess.CalledProcessError:
        return None
    if not held or datetime.fromisoformat(stamp).astimezone(UTC).date() != decided_on:
        return None
    return ",".join(hashlib.sha256(body).hexdigest() for body in files.values())


def _git(repo: Path, *args: str) -> bytes:
    """A read-only git command's output, bounded in time."""
    command = ["git", "-C", str(repo), *args]
    return subprocess.run(
        command, check=True, capture_output=True, timeout=GIT_TIMEOUT_SECONDS
    ).stdout


def _persist(
    pool: ConnectionPool,
    version: MappedVersion,
    files: _Files,
    entity_id: int,
    period: str,
    kind: ReportKind,
    approval: str | None,
    q0: Q0Import,
) -> int:
    """Store one mapped version, its QA records and its import decisions in one transaction."""
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        report_id = store.create_report(cursor, entity_id=entity_id, period=period, kind=kind)
        claims = tuple(_cited(cursor, claim) for claim in version.claims)
        draft = VersionDraft(
            report_id=report_id,
            author=IMPORT_AUTHOR,
            knowledge_cutoff=cutoff_instant(version.cutoff),
            content_hash=content_hash(version.sections, claims),
            sections=version.sections,
            claims=claims,
            import_sources=files,
        )
        version_id = store.create_version(cursor, draft)
        for gate, result in version.qa_records:
            store.insert_qa_record(cursor, version_id=version_id, gate=gate, result=result)
        seal = store.insert_decision(
            cursor,
            subject_kind=SubjectKind.REPORT_VERSION,
            subject_id=version_id,
            kind=DecisionKind.IMPORT_SEAL,
            predecessor_id=None,
            sealed_digest=store.sealed_digest(cursor, version_id),
        )
        if approval is not None:
            store.insert_decision(
                cursor,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=version_id,
                kind=DecisionKind.IMPORTED_APPROVAL,
                predecessor_id=seal.id,
                sealed_digest=seal.sealed_digest,
                original_approval_sha256=approval,
                ruling=q0.ruling,
                decided_on=q0.decided_on,
            )
    return version_id


def _cited(cursor: Cursor[Any], claim: NumericClaim) -> NumericClaim:
    """The claim citing the stored record its source file holds (D6): a ``FIGURE`` the fact
    under its key, a quote the capture of its file; else it stays unresolved."""
    citation, key = claim.citation, claim.measurement_key
    if citation.kind is CitationKind.FIGURE and key is not None:
        fields = (key.entity_id, key.canonical_id, key.period.start, key.period.end)
        kinds = (key.basis.value, key.framework.value, key.currency, key.value_kind.value)
        row = cursor.execute(_FACT, (citation.source_sha256, *fields, *kinds)).fetchone()
        update = None if row is None else {"fact_origin": row[0], "fact_origin_id": row[1]}
    elif citation.kind is CitationKind.SOURCE_QUOTE:
        row = cursor.execute(_CAPTURE, (citation.source_sha256,)).fetchone()
        update = None if row is None else {"capture_ref_id": row[0]}
    else:
        return claim
    if update is None:
        return claim
    return claim.model_copy(
        update={"citation": citation.model_copy(update=update), "unresolved": False}
    )
