"""PostgreSQL reads and writes for the evidence and run tables.

D1a Task 2 lands the identity-evidence reads; Task 5 adds the evidence writes
and reads to this same class. As-of reads serve a fresh run's resolution only;
replay reads strictly by id, because a stored row never changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import LiteralString

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.pg.identity_seed import EvidenceInputKind, SettingKey


class EvidenceInputRecord(BaseModel):
    """One stored ``evidence_inputs`` row."""

    model_config = ConfigDict(frozen=True)

    id: int
    kind: EvidenceInputKind
    label: str
    content_sha256: str
    recorded_at: datetime


class BasisStatusRecord(BaseModel):
    """One stored ``entity_basis_status`` row."""

    model_config = ConfigDict(frozen=True)

    id: int
    entity_id: int
    basis_status: BasisStatus
    evidence_input_id: int
    recorded_at: datetime


class SettingsRecord(BaseModel):
    """One stored ``settings_records`` row."""

    model_config = ConfigDict(frozen=True)

    id: int
    entity_id: int
    setting_key: SettingKey
    value_text: str
    evidence_input_id: int
    recorded_at: datetime


class SegmentMemberRecord(BaseModel):
    """One stored ``segment_members`` row with the occurrences that evidence it."""

    model_config = ConfigDict(frozen=True)

    id: int
    entity_id: int
    axis: str
    member: str
    display_name: str
    valid_from: date
    valid_to: date | None
    recorded_at: datetime
    evidence_occurrence_ids: tuple[int, ...]


_EVIDENCE_INPUTS_BY_ID: LiteralString = (
    "SELECT id, kind, label, content_sha256, recorded_at FROM eqos.evidence_inputs "
    "WHERE id = ANY(%s) ORDER BY id"
)
_BASIS_COLUMNS: LiteralString = (
    "SELECT id, entity_id, basis_status, evidence_input_id, recorded_at "
    "FROM eqos.entity_basis_status "
)
_BASIS_AS_OF: LiteralString = (
    _BASIS_COLUMNS + "WHERE entity_id = %s AND recorded_at <= %s "
    "ORDER BY recorded_at DESC, id DESC LIMIT 1"
)
_BASIS_BY_ID: LiteralString = _BASIS_COLUMNS + "WHERE id = ANY(%s) ORDER BY id"
_SETTINGS_COLUMNS: LiteralString = (
    "SELECT id, entity_id, setting_key, value_text, evidence_input_id, recorded_at "
    "FROM eqos.settings_records "
)
_SETTINGS_AS_OF: LiteralString = (
    _SETTINGS_COLUMNS + "WHERE entity_id = %s AND setting_key = %s AND recorded_at <= %s "
    "ORDER BY recorded_at DESC, id DESC LIMIT 1"
)
_SETTINGS_BY_ID: LiteralString = _SETTINGS_COLUMNS + "WHERE id = ANY(%s) ORDER BY id"
_SEGMENT_COLUMNS: LiteralString = (
    "SELECT m.id, m.entity_id, m.axis, m.member, m.display_name, m.valid_from, m.valid_to, "
    "m.recorded_at, "
    "COALESCE(array_agg(e.occurrence_id ORDER BY e.occurrence_id) "
    "FILTER (WHERE e.occurrence_id IS NOT NULL), '{}') AS evidence_occurrence_ids "
    "FROM eqos.segment_members m "
    "LEFT JOIN eqos.segment_member_evidence e ON e.segment_member_id = m.id "
)
_SEGMENTS_AS_OF: LiteralString = (
    _SEGMENT_COLUMNS + "WHERE m.entity_id = %s AND m.axis = %s AND m.recorded_at <= %s "
    "GROUP BY m.id ORDER BY m.member, m.valid_from, m.id"
)
_SEGMENTS_BY_ID: LiteralString = (
    _SEGMENT_COLUMNS + "WHERE m.id = ANY(%s) GROUP BY m.id ORDER BY m.id"
)


class EvidenceRepository:
    """Idempotent, parameterised access to schema ``eqos`` through a runtime pool."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def basis_status_as_of(
        self, entity_id: int, cutoff: datetime
    ) -> tuple[int, BasisStatus] | None:
        """The latest basis status recorded at or before the cutoff, with its row id."""
        rows = self._fetch(_BASIS_AS_OF, (entity_id, cutoff))
        if not rows:
            return None
        record = BasisStatusRecord.model_validate(rows[0])
        return record.id, record.basis_status

    def settings_as_of(
        self, entity_id: int, key: SettingKey, cutoff: datetime
    ) -> SettingsRecord | None:
        """The latest value of one setting recorded at or before the cutoff."""
        rows = self._fetch(_SETTINGS_AS_OF, (entity_id, key.value, cutoff))
        return SettingsRecord.model_validate(rows[0]) if rows else None

    def segment_members_as_of(
        self, entity_id: int, axis: str, cutoff: datetime
    ) -> tuple[SegmentMemberRecord, ...]:
        """Every member of one segment axis recorded at or before the cutoff."""
        rows = self._fetch(_SEGMENTS_AS_OF, (entity_id, axis, cutoff))
        return tuple(SegmentMemberRecord.model_validate(row) for row in rows)

    def get_evidence_inputs(self, ids: Sequence[int]) -> tuple[EvidenceInputRecord, ...]:
        """Stored evidence-input rows by id."""
        rows = self._fetch(_EVIDENCE_INPUTS_BY_ID, (list(ids),))
        return tuple(EvidenceInputRecord.model_validate(row) for row in rows)

    def get_basis_statuses(self, ids: Sequence[int]) -> tuple[BasisStatusRecord, ...]:
        """Stored basis-status rows by id."""
        rows = self._fetch(_BASIS_BY_ID, (list(ids),))
        return tuple(BasisStatusRecord.model_validate(row) for row in rows)

    def get_settings_records(self, ids: Sequence[int]) -> tuple[SettingsRecord, ...]:
        """Stored settings rows by id."""
        rows = self._fetch(_SETTINGS_BY_ID, (list(ids),))
        return tuple(SettingsRecord.model_validate(row) for row in rows)

    def get_segment_members(self, ids: Sequence[int]) -> tuple[SegmentMemberRecord, ...]:
        """Stored segment-member rows by id, with their evidence occurrence ids."""
        rows = self._fetch(_SEGMENTS_BY_ID, (list(ids),))
        return tuple(SegmentMemberRecord.model_validate(row) for row in rows)

    def _fetch(self, query: LiteralString, params: tuple[object, ...]) -> list[dict[str, object]]:
        """Run one parameterised read and return its rows as column dicts."""
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
