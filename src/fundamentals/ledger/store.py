"""Ledger rows in and out, inside the caller's transaction (ledger spec §1; plan D3, D1-D4).

Every function takes a cursor, so the caller owns the transaction and its lock order. The
triggers are authoritative: they set the decider, sequence, recorded time and digests, and
refuse an insert after a seal, a stale head, an illegal transition or an unbound approval.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Any, LiteralString

from psycopg import Cursor, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fundamentals.contracts.ledger import (
    Citation,
    ClaimState,
    DecisionKind,
    DecisionRecord,
    NumericClaim,
    PanelReview,
    PolicyValue,
    ReportKind,
    SubjectKind,
    Validation,
    VersionDraft,
    VersionState,
)
from fundamentals.contracts.snapshot import canonical_sha256

_SCHEMA = "eqos"
_SEALED_DIGEST: LiteralString = "SELECT eqos.version_sealed_digest(%s)"
_SUBJECT_DIGEST: LiteralString = "SELECT eqos.subject_digest(%s, %s)"
_HEAD: LiteralString = (
    "SELECT * FROM eqos.decisions WHERE subject_kind = %s AND subject_id = %s "
    "ORDER BY sequence DESC LIMIT 1"
)
_DECISION: LiteralString = "SELECT * FROM eqos.decisions WHERE id = %s"
_LATEST_VALIDATION: LiteralString = (
    "SELECT * FROM eqos.validations WHERE version_id = %s ORDER BY id DESC LIMIT 1"
)
_STATES: LiteralString = (
    "SELECT c.claim_key, s.state FROM eqos.validation_claim_states s "
    "LEFT JOIN eqos.numeric_claims c ON c.id = s.claim_id WHERE s.validation_id = %s "
    "ORDER BY s.id"
)
_CLAIM_STATE: LiteralString = (
    "INSERT INTO eqos.validation_claim_states (validation_id, version_id, claim_id, state) "
    "SELECT %s, %s, id, %s FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s "
    "RETURNING id"
)
_VERSION_STATE: LiteralString = (
    "INSERT INTO eqos.validation_claim_states (validation_id, version_id, state) "
    "VALUES (%s, %s, %s)"
)
_VERSION: LiteralString = "SELECT * FROM eqos.report_versions WHERE id = %s"
_SECTIONS: LiteralString = (
    "SELECT ordinal, section_key, body FROM eqos.report_sections WHERE version_id = %s "
    "ORDER BY ordinal"
)
_CLAIMS: LiteralString = (
    "SELECT c.*, s.section_key FROM eqos.numeric_claims c "
    "JOIN eqos.report_sections s ON s.id = c.section_id WHERE c.version_id = %s ORDER BY c.id"
)
_SOURCES: LiteralString = (
    "SELECT source_path, body FROM eqos.import_sources WHERE version_id = %s ORDER BY id"
)
_NO_VERSION = "no report version {version_id}"
_NO_SUBJECT = "no {subject_kind} {subject_id}"
_UNKNOWN_CLAIM = "version {version_id} has no claim {claim_key!r}"
_ACQUISITION: LiteralString = (
    "INSERT INTO eqos.legacy_acquisitions (blob_sha256, retrieved_at, manifest_sha256, "
    "entry_sha256) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING"
)
_MANIFEST_PIN = "retrieval manifest SHA-256 {actual} is not the pinned {expected}"


def create_report(cursor: Cursor[Any], *, entity_id: int, period: str, kind: ReportKind) -> int:
    """Insert one report (one per stock, period and kind); returns its id."""
    return _insert(cursor, "reports", {"entity_id": entity_id, "period": period, "kind": kind})


def create_version(cursor: Cursor[Any], draft: VersionDraft) -> int:
    """Insert a version with its import sources, sections and claims; returns its id."""
    version_id = _insert(
        cursor,
        "report_versions",
        {
            "report_id": draft.report_id,
            "predecessor_id": draft.predecessor_id,
            "author": draft.author,
            "knowledge_cutoff": draft.knowledge_cutoff,
            "pinned_run_ids": list(draft.pinned_run_ids),
            "content_hash": draft.content_hash,
        },
    )
    for path, body in draft.import_sources:
        _insert(
            cursor,
            "import_sources",
            {"version_id": version_id, "source_path": path, "body": body},
        )
    section_ids = {
        section.section_key: _insert(
            cursor,
            "report_sections",
            {
                "version_id": version_id,
                "ordinal": section.ordinal,
                "section_key": section.section_key,
                "body": section.body,
                "sha256": hashlib.sha256(section.body.encode()).hexdigest(),
            },
        )
        for section in draft.sections
    }
    for claim in draft.claims:
        _insert(cursor, "numeric_claims", _claim_row(claim, version_id, section_ids))
    return version_id


def read_version(cursor: Cursor[Any], version_id: int) -> VersionDraft:
    """A stored version's content, as :func:`create_version` was given it."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        row = own.execute(_VERSION, (version_id,)).fetchone()
        if row is None:
            raise LookupError(_NO_VERSION.format(version_id=version_id))
        sections = own.execute(_SECTIONS, (version_id,)).fetchall()
        claims = own.execute(_CLAIMS, (version_id,)).fetchall()
        sources = own.execute(_SOURCES, (version_id,)).fetchall()
    return VersionDraft.model_validate(
        {
            **row,
            "pinned_run_ids": tuple(row["pinned_run_ids"]),
            "sections": sections,
            "claims": tuple(
                {
                    **claim,
                    "citation": Citation.model_validate({**claim, "kind": claim["citation_kind"]}),
                    "qualifiers": tuple(claim["qualifiers"]),
                }
                for claim in claims
            ),
            "import_sources": tuple((s["source_path"], bytes(s["body"])) for s in sources),
        }
    )


def sealed_digest(cursor: Cursor[Any], version_id: int) -> str:
    """The version's sealed digest, as the database computes it."""
    row = cursor.execute(_SEALED_DIGEST, (version_id,)).fetchone()
    assert row is not None and row[0] is not None, version_id
    return str(row[0])


def subject_digest(cursor: Cursor[Any], subject_kind: SubjectKind, subject_id: int) -> str:
    """The digest a decision on the subject must carry, as the database computes it (D1)."""
    row = cursor.execute(_SUBJECT_DIGEST, (subject_kind.value, subject_id)).fetchone()
    if row is None or row[0] is None:
        raise LookupError(_NO_SUBJECT.format(subject_kind=subject_kind, subject_id=subject_id))
    return str(row[0])


def chain_head(
    cursor: Cursor[Any], subject_kind: SubjectKind, subject_id: int
) -> DecisionRecord | None:
    """The subject's latest decision, or ``None`` before its first."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        row = own.execute(_HEAD, (subject_kind.value, subject_id)).fetchone()
    return None if row is None else _decision(row)


def insert_decision(
    cursor: Cursor[Any],
    *,
    subject_kind: SubjectKind,
    subject_id: int,
    kind: DecisionKind,
    predecessor_id: int | None,
    sealed_digest: str | None = None,
    validation_id: int | None = None,
    original_approval_sha256: str | None = None,
    ruling: str | None = None,
    decided_on: date | None = None,
    policy: PolicyValue | None = None,
    panel_review_id: int | None = None,
) -> DecisionRecord:
    """Append one decision naming the head it follows; the trigger checks and completes it."""
    decision_id = _insert(
        cursor,
        "decisions",
        {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "kind": kind,
            "predecessor_id": predecessor_id,
            "sealed_digest": sealed_digest,
            "validation_id": validation_id,
            "panel_review_id": panel_review_id,
            "original_approval_sha256": original_approval_sha256,
            "ruling": ruling,
            "decided_on": decided_on,
            "policy_key": None if policy is None else policy.key,
            "policy_value": None if policy is None else policy.value,
            "policy_unit": None if policy is None else policy.unit,
        },
    )
    with cursor.connection.cursor(row_factory=dict_row) as own:
        row = own.execute(_DECISION, (decision_id,)).fetchone()
    assert row is not None
    return _decision(row)


def insert_panel_review(cursor: Cursor[Any], review: PanelReview) -> int:
    """Append one reviewer verdict in the deciding transaction; returns its id."""
    return _insert(cursor, "panel_reviews", review.model_dump())


def insert_validation(cursor: Cursor[Any], validation: Validation) -> int:
    """Append a validation and its states; returns its id."""
    version_id = validation.version_id
    validation_id = _insert(
        cursor,
        "validations",
        {
            "version_id": version_id,
            "checker_version": validation.checker_version,
            "mode": validation.mode,
            "overlay_position": validation.overlay_position,
            "pinned_input_sha256": validation.pinned_input_sha256,
            "sealed_digest": validation.sealed_digest,
        },
    )
    for claim_key, state in validation.claim_states:
        params = (validation_id, version_id, state.value, version_id, claim_key)
        if cursor.execute(_CLAIM_STATE, params).fetchone() is None:
            raise LookupError(_UNKNOWN_CLAIM.format(version_id=version_id, claim_key=claim_key))
    for version_state in validation.version_states:
        cursor.execute(_VERSION_STATE, (validation_id, version_id, version_state.value))
    return validation_id


def latest_validation(cursor: Cursor[Any], version_id: int) -> Validation | None:
    """The version's latest validation (highest id), the one an approval must bind."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        row = own.execute(_LATEST_VALIDATION, (version_id,)).fetchone()
        if row is None:
            return None
        states = own.execute(_STATES, (row["id"],)).fetchall()
    return Validation.model_validate(
        {
            **row,
            "claim_states": tuple(
                (s["claim_key"], ClaimState(s["state"])) for s in states if s["claim_key"]
            ),
            "version_states": tuple(
                VersionState(s["state"]) for s in states if s["claim_key"] is None
            ),
        }
    )


def insert_qa_record(
    cursor: Cursor[Any], *, version_id: int, gate: str, result: Mapping[str, Any]
) -> int:
    """Append one imported automated gate result (never a decision); returns its id."""
    return _insert(
        cursor, "qa_records", {"version_id": version_id, "gate": gate, "result": Jsonb(result)}
    )


def insert_acquisitions(cursor: Cursor[Any], manifest_bytes: bytes, *, expected_sha256: str) -> int:
    """Record each retrieval-manifest entry's retrieval time for its blob (D8); returns how
    many rows were new. Refuses bytes other than the pinned manifest's."""
    actual = hashlib.sha256(manifest_bytes).hexdigest()
    if actual != expected_sha256:
        raise ValueError(_MANIFEST_PIN.format(actual=actual, expected=expected_sha256))
    inserted = 0
    for entry in json.loads(manifest_bytes)["entries"]:
        params = (entry["sha256"], entry["retrieved_at"], actual, canonical_sha256(entry))
        inserted += cursor.execute(_ACQUISITION, params).rowcount
    return inserted


def _claim_row(
    claim: NumericClaim, version_id: int, section_ids: Mapping[str, int]
) -> dict[str, Any]:
    """The ``numeric_claims`` row for one claim."""
    key = claim.measurement_key
    return {
        **claim.model_dump(exclude={"section_key", "citation", "measurement_key"}),
        **claim.citation.model_dump(exclude={"kind"}),
        "version_id": version_id,
        "section_id": section_ids[claim.section_key],
        "citation_kind": claim.citation.kind,
        "key_digest": None if key is None else key.digest(),
        "measurement_key": None if key is None else Jsonb(key.model_dump(mode="json")),
        "qualifiers": list(claim.qualifiers),
    }


def _insert(cursor: Cursor[Any], table: str, row: Mapping[str, Any]) -> int:
    """Insert one row (enum members as their values); returns its id."""
    values = [value.value if isinstance(value, StrEnum) else value for value in row.values()]
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(_SCHEMA, table),
        sql.SQL(", ").join(map(sql.Identifier, row)),
        sql.SQL(", ").join(sql.Placeholder() * len(row)),
    )
    fetched = cursor.execute(statement, values).fetchone()
    assert fetched is not None
    return int(fetched[0])


def _decision(row: Mapping[str, Any]) -> DecisionRecord:
    """A decision record from its row."""
    policy = (
        None
        if row["policy_key"] is None
        else PolicyValue(key=row["policy_key"], value=row["policy_value"], unit=row["policy_unit"])
    )
    return DecisionRecord.model_validate({**row, "policy": policy})
