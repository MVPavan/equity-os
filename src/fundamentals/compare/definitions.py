"""Definition records and immutable, versioned definition sets (data spec §5).

A record explains a pair difference only within its scope: one mapping entry, one measurement
key or one filing package. Records come only from an evidenced disposition or mapping change.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import psycopg
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.versioning import VersionContentDriftError

_ARTIFACT = "definition_set"
_INVALID_SET = "definition set {path} is invalid: {detail}"
_NOT_TEXT = "write the explained amount as a quoted decimal, not {given!r}"
_DUPLICATE_RECORD = "record id {record_id!r} appears more than once"
_NOT_A_PACKAGE = "a FILING record's scope_ref is a package id, got {scope_ref!r}"

_INSERT_SET = (
    "INSERT INTO eqos.definition_sets (version, content_sha256) VALUES (%s, %s) "
    "ON CONFLICT (version) DO NOTHING RETURNING id"
)
_SELECT_SET = "SELECT id, content_sha256 FROM eqos.definition_sets WHERE version = %s"
_SET_BY_ID = "SELECT version, content_sha256 FROM eqos.definition_sets WHERE id = %s"
_RECORDS_OF_SET = (
    "SELECT record_id, scope, mapping_entry_id, key_digest, package_id, canonical_id, "
    "operand_name, evidence_ref, explained_amount, unit FROM eqos.definition_records "
    "WHERE definition_set_id = %s ORDER BY id"
)
_RECORD_IDS = "SELECT id, record_id FROM eqos.definition_records WHERE definition_set_id = %s"
_NO_SET = "definition set {set_id} is not published"
_INSERT_RECORD = (
    "INSERT INTO eqos.definition_records (definition_set_id, record_id, scope, mapping_entry_id, "
    "key_digest, package_id, canonical_id, operand_name, evidence_ref, explained_amount, unit) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (definition_set_id, record_id) DO NOTHING"
)


class DefinitionScope(StrEnum):
    """What a record's ``scope_ref`` names."""

    MAPPING = "MAPPING"
    MEASUREMENT = "MEASUREMENT"
    FILING = "FILING"


class DefinitionRecord(BaseModel):
    """An evidenced, scoped explanation of a difference of ``explained_amount`` in ``unit``.

    The amount is a magnitude; the side it moves and its sign come from the comparison.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    scope: DefinitionScope
    scope_ref: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    operand_name: str | None = None
    evidence_ref: str = Field(min_length=1)
    explained_amount: Decimal = Field(gt=0)
    unit: ValueKind

    @field_validator("explained_amount", mode="before")
    @classmethod
    def _quoted_decimal(cls, value: object) -> object:
        """Refuse a float amount, so binary rounding never enters an explanation."""
        if isinstance(value, float):
            raise ValueError(_NOT_TEXT.format(given=value))
        return value

    def package_id(self) -> int | None:
        """The package a ``FILING`` record is scoped to; ``None`` for other scopes."""
        if self.scope is not DefinitionScope.FILING:
            return None
        if not self.scope_ref.isdigit():
            raise ValueError(_NOT_A_PACKAGE.format(scope_ref=self.scope_ref))
        return int(self.scope_ref)


class DefinitionSet(BaseModel):
    """A published, immutable set of records; a run pins one version."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1)
    content_sha256: str
    records: tuple[DefinitionRecord, ...]

    @field_validator("records", mode="after")
    @classmethod
    def _unique_ids(cls, records: tuple[DefinitionRecord, ...]) -> tuple[DefinitionRecord, ...]:
        """Refuse two records with one id."""
        seen: set[str] = set()
        for definition in records:
            if definition.record_id in seen:
                raise ValueError(_DUPLICATE_RECORD.format(record_id=definition.record_id))
            seen.add(definition.record_id)
        return records

    def record(self, record_id: str) -> DefinitionRecord | None:
        """The record with ``record_id``, if the set holds it."""
        return next((item for item in self.records if item.record_id == record_id), None)


def load_definition_set(path: Path) -> DefinitionSet:
    """Load a definition set, pinned by the SHA-256 of its file bytes."""
    content = path.read_bytes()
    raw = yaml.safe_load(content)
    try:
        return DefinitionSet.model_validate(
            {**raw, "content_sha256": hashlib.sha256(content).hexdigest()}
        )
    except (TypeError, ValidationError) as error:
        raise ValueError(_INVALID_SET.format(path=path, detail=error)) from error


def publish_definition_set(conn: psycopg.Connection, definition_set: DefinitionSet) -> int:
    """Publish a set and its records once; return its id.

    Republishing the same version with the same content returns the stored id; with other
    content it raises :class:`VersionContentDriftError` and writes nothing.
    """
    with conn.transaction():
        inserted = conn.execute(
            _INSERT_SET, (definition_set.version, definition_set.content_sha256)
        ).fetchone()
        if inserted is None:
            stored = conn.execute(_SELECT_SET, (definition_set.version,)).fetchone()
            assert stored is not None
            set_id, pinned = int(stored[0]), str(stored[1])
            if pinned != definition_set.content_sha256:
                raise VersionContentDriftError(
                    artifact=_ARTIFACT,
                    version=definition_set.version,
                    pinned_sha256=pinned,
                    actual_sha256=definition_set.content_sha256,
                )
            return set_id
        set_id = int(inserted[0])
        for definition in definition_set.records:
            conn.execute(_INSERT_RECORD, (set_id, *_record_columns(definition)))
        return set_id


def read_definition_set(conn: psycopg.Connection, definition_set_id: int) -> DefinitionSet:
    """A published set and its records, by id (an immutable read)."""
    stored = conn.execute(_SET_BY_ID, (definition_set_id,)).fetchone()
    if stored is None:
        raise LookupError(_NO_SET.format(set_id=definition_set_id))
    records = []
    for row in conn.execute(_RECORDS_OF_SET, (definition_set_id,)).fetchall():
        record_id, scope, mapping_entry_id, key_digest, package_id = row[:5]
        canonical_id, operand_name, evidence_ref, amount, unit = row[5:]
        scope_ref = {
            DefinitionScope.MAPPING.value: mapping_entry_id,
            DefinitionScope.MEASUREMENT.value: key_digest,
            DefinitionScope.FILING.value: None if package_id is None else str(package_id),
        }[scope]
        records.append(
            DefinitionRecord(
                record_id=record_id,
                scope=DefinitionScope(scope),
                scope_ref=scope_ref,
                canonical_id=canonical_id,
                operand_name=operand_name,
                evidence_ref=evidence_ref,
                explained_amount=amount,
                unit=ValueKind(unit),
            )
        )
    return DefinitionSet(version=stored[0], content_sha256=stored[1], records=tuple(records))


def definition_record_ids(conn: psycopg.Connection, definition_set_id: int) -> dict[str, int]:
    """Stored row ids of a published set's records, by record id."""
    rows = conn.execute(_RECORD_IDS, (definition_set_id,)).fetchall()
    return {str(record_id): int(row_id) for row_id, record_id in rows}


def _record_columns(definition: DefinitionRecord) -> tuple[object, ...]:
    """A record's columns after the set id, with exactly one scope column set."""
    scope = definition.scope
    return (
        definition.record_id,
        scope.value,
        definition.scope_ref if scope is DefinitionScope.MAPPING else None,
        definition.scope_ref if scope is DefinitionScope.MEASUREMENT else None,
        definition.package_id(),
        definition.canonical_id,
        definition.operand_name,
        definition.evidence_ref,
        definition.explained_amount,
        definition.unit.value,
    )
