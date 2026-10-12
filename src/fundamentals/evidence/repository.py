"""PostgreSQL reads and writes for the evidence and run tables.

D1a Task 2 lands the identity-evidence reads; Task 5 adds the evidence writes
and reads to this same class. As-of reads serve a fresh run's resolution only;
replay reads strictly by id, because a stored row never changes. A row's child sets
(a package's members, statements and their evidence; a segment member's evidence) are
written once, in the transaction that inserts the row, so a by-id read never grows and an
as-of read on the row's own ``recorded_at`` is exactly its associations' time.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import Basis, StatementFamily
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    FilingFamily,
    FilingPackage,
    Interpretation,
    Occurrence,
    StatementRole,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence import repository_rows as rows_sql
from fundamentals.evidence.member_identity import IssuerIdentifiers
from fundamentals.evidence.repository_rows import PackageStatementRecord, SegmentMemberWrite
from fundamentals.pg.identity_seed import EvidenceInputKind, SettingKey

_NO_IDENTIFIERS = "entity {entity_id} has no seeded security with ISIN, NSE and BSE listings"
_AMBIGUOUS_IDENTIFIERS = "entity {entity_id} has {count} seeded securities; identity is ambiguous"
_UNSTORED = "{what} has no stored id"


class InterpretationConflictError(RuntimeError):
    """A concurrent ingest stored the same interpretation identity first; retry from a read."""


class VersionPin(BaseModel):
    """A versioned artifact's content hash, pinned on first use (``eqos.version_pins``)."""

    model_config = ConfigDict(frozen=True)

    artifact: str
    version: str
    content_sha256: str


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

    # --- writes ---------------------------------------------------------------------

    def store_clock(self) -> datetime:
        """The store's own clock (``recorded_at`` is never a knowledge time)."""
        clock: datetime = self._fetch(rows_sql.STORE_CLOCK, ())[0]["now"]
        return clock

    def put_evidence_input(self, kind: EvidenceInputKind, label: str, content_sha256: str) -> int:
        """Record one evidence input, returning the stored id."""
        with self._transaction() as conn:
            conn.execute(rows_sql.INSERT_EVIDENCE_INPUT, (kind.value, label, content_sha256))
            return _one_id(conn, rows_sql.SELECT_EVIDENCE_INPUT, (kind.value, content_sha256))

    def put_settings_record(
        self, entity_id: int, key: SettingKey, value_text: str, evidence_input_id: int
    ) -> int:
        """Record one evidenced setting value, returning the stored id."""
        params = (entity_id, key.value, value_text, evidence_input_id)
        with self._transaction() as conn:
            conn.execute(rows_sql.INSERT_SETTING, params)
            return _one_id(conn, rows_sql.SELECT_SETTING, params)

    def put_capture_ref(self, ref: CaptureReference) -> CaptureReference:
        """Register a capture; an existing registration (and its first-seen time) wins."""
        with self._transaction() as conn:
            conn.execute(rows_sql.INSERT_CAPTURE_REF, rows_sql.capture_params(ref))
            found = _rows(
                conn,
                rows_sql.SELECT_CAPTURE_REF,
                (ref.source_id, ref.surface, ref.request_key, ref.capture_id),
            )
        return rows_sql.capture_of(found[0])

    def find_capture_ref(
        self, source_id: str, surface: str, blob_sha256: str
    ) -> CaptureReference | None:
        """The first registration of these bytes from this source (reuse level 1)."""
        found = self._fetch(rows_sql.FIND_CAPTURE_REF, (source_id, surface, blob_sha256))
        return rows_sql.capture_of(found[0]) if found else None

    def pin_versions(self, pins: Sequence[VersionPin]) -> None:
        """Pin each artifact version to its content on first use, all in one transaction.

        A version already pinned to other content raises :class:`VersionContentDriftError`
        and nothing is written (mirrors ``publish_definition_set``).
        """
        with self._transaction() as conn:
            for pin in pins:
                params = (pin.artifact, pin.version, pin.content_sha256)
                if _rows(conn, rows_sql.INSERT_VERSION_PIN, params):
                    continue
                stored = _rows(conn, rows_sql.SELECT_VERSION_PIN, (pin.artifact, pin.version))
                pinned = str(stored[0]["content_sha256"])
                if pinned != pin.content_sha256:
                    raise VersionContentDriftError(
                        artifact=pin.artifact,
                        version=pin.version,
                        pinned_sha256=pinned,
                        actual_sha256=pin.content_sha256,
                    )

    def put_package(
        self,
        package: FilingPackage,
        *,
        statement_evidence: Mapping[StatementFamily, Sequence[int]],
    ) -> int:
        """Record a package with its members, statement roles and presence evidence.

        Members, statements and evidence are written only with a new package row; an
        existing package is returned as stored (its statement evidence pinned at first write).
        """
        with self._transaction() as conn:
            key = (
                package.entity_id,
                package.family.value,
                package.reporting_period_end,
                package.basis.value,
                package.framework.value,
            )
            inserted = _rows(
                conn,
                rows_sql.INSERT_PACKAGE,
                (
                    *key,
                    package.reporting_kind.value,
                    package.knowledge_time,
                    package.supersedes_package_id,
                    package.evidence_sha256,
                ),
            )
            if not inserted:
                return _one_id(conn, rows_sql.SELECT_PACKAGE_ID, (*key, package.evidence_sha256))
            package_id = int(inserted[0]["id"])
            for member in package.members.values():
                conn.execute(
                    rows_sql.INSERT_MEMBER,
                    (
                        package_id,
                        _stored(member.capture.capture_ref_id, "package member capture"),
                        member.representation.value,
                        member.knowledge_time,
                        member.knowledge_time_raw,
                        member.knowledge_time_status.value,
                    ),
                )
            roles = [(family, StatementRole.PRESENT) for family in package.statements_present]
            roles += [(family, StatementRole.REPLACED) for family in package.replaced_statements]
            for family, role in sorted(roles):
                conn.execute(rows_sql.INSERT_STATEMENT, (package_id, family.value, role.value))
                if role is not StatementRole.PRESENT:
                    continue
                statement_id = _one_id(
                    conn, rows_sql.SELECT_STATEMENT_ID, (package_id, family.value, role.value)
                )
                for occurrence_id in statement_evidence.get(family, ()):
                    conn.execute(rows_sql.INSERT_STATEMENT_EVIDENCE, (statement_id, occurrence_id))
        return package_id

    def put_occurrences(self, occurrences: Sequence[Occurrence]) -> tuple[Occurrence, ...]:
        """Record occurrences, returning every one with its stored id."""
        stored, _ = self.put_generation(occurrences, ())
        return stored

    def put_attempts(
        self, attempts: Sequence[AcquisitionAttempt]
    ) -> tuple[AcquisitionAttempt, ...]:
        """Record attempts in one transaction, so they share one ``attempted_at``."""
        _, stored = self.put_generation((), attempts)
        return stored

    def put_generation(
        self, occurrences: Sequence[Occurrence], attempts: Sequence[AcquisitionAttempt]
    ) -> tuple[tuple[Occurrence, ...], tuple[AcquisitionAttempt, ...]]:
        """One adapter invocation's occurrences and attempts, in one transaction."""
        with self._transaction() as conn:
            stored_occurrences = _insert_occurrences(conn, occurrences)
            stored_attempts = tuple(_insert_attempt(conn, attempt) for attempt in attempts)
        return stored_occurrences, stored_attempts

    def reserve_interpretation_ids(self, count: int) -> tuple[int, ...]:
        """Reserve ``count`` interpretation ids from the identity sequence."""
        if count == 0:
            return ()
        return tuple(
            int(row["id"]) for row in self._fetch(rows_sql.RESERVE_INTERPRETATION_IDS, (count,))
        )

    def put_interpretations(self, interpretations: Sequence[Interpretation]) -> None:
        """Insert interpretations under their reserved ids, with operands and condition evidence.

        One transaction. Direct rows go first so constructions can name them. An identity
        already stored by a concurrent ingest raises :class:`InterpretationConflictError`
        and nothing is written; the caller retries from a fresh read.
        """
        ordered = sorted(interpretations, key=lambda item: item.occurrence_id is None)
        try:
            with self._transaction() as conn, conn.cursor() as cursor:
                cursor.executemany(
                    rows_sql.INSERT_INTERPRETATION,
                    [rows_sql.interpretation_params(item) for item in ordered],
                )
                cursor.executemany(
                    rows_sql.INSERT_OPERAND,
                    [
                        (item.interpretation_id, ordinal, operand_id)
                        for item in ordered
                        for ordinal, operand_id in enumerate(item.operand_interpretation_ids)
                    ],
                )
                cursor.executemany(
                    rows_sql.INSERT_CONDITION_EVIDENCE,
                    [
                        (item.interpretation_id, proof.condition_id, proof.holds, evidence_id)
                        for item in ordered
                        for proof in item.condition_evidence
                        for evidence_id in proof.evidence_interpretation_ids
                    ],
                )
        except psycopg.errors.UniqueViolation as error:
            raise InterpretationConflictError(str(error)) from error

    def put_segment_members(self, members: Sequence[SegmentMemberWrite]) -> tuple[int, ...]:
        """Record segment members with their evidence occurrences, returning stored ids.

        Evidence is written only with a new member row; an existing member keeps the
        evidence it was first recorded with.
        """
        ids: list[int] = []
        with self._transaction() as conn:
            for member in members:
                key = (member.entity_id, member.axis, member.member, member.valid_from)
                inserted = _rows(
                    conn,
                    rows_sql.INSERT_SEGMENT_MEMBER,
                    (
                        member.entity_id,
                        member.axis,
                        member.member,
                        member.display_name,
                        member.valid_from,
                    ),
                )
                if not inserted:
                    ids.append(_one_id(conn, rows_sql.SELECT_SEGMENT_MEMBER, key))
                    continue
                member_id = int(inserted[0]["id"])
                for occurrence_id in member.evidence_occurrence_ids:
                    conn.execute(rows_sql.INSERT_SEGMENT_EVIDENCE, (member_id, occurrence_id))
                ids.append(member_id)
        return tuple(ids)

    # --- current reads (ingest and fresh runs only) ----------------------------------

    def entity_id(self, entity_key: str) -> int | None:
        """The seeded reporting entity's id for its key, if seeded."""
        found = self._fetch(rows_sql.ENTITY_BY_KEY, (entity_key,))
        return int(found[0]["id"]) if found else None

    def issuer_identifiers(self, entity_id: int) -> IssuerIdentifiers:
        """The seeded ISIN, NSE symbol and BSE scrip of one entity."""
        found = self._fetch(rows_sql.ISSUER_IDENTIFIERS, (entity_id,))
        complete = [row for row in found if row["nse"] and row["bse"]]
        if not complete:
            raise LookupError(_NO_IDENTIFIERS.format(entity_id=entity_id))
        if len(complete) > 1 or len(complete[0]["nse"]) > 1 or len(complete[0]["bse"]) > 1:
            raise LookupError(
                _AMBIGUOUS_IDENTIFIERS.format(entity_id=entity_id, count=len(complete))
            )
        row = complete[0]
        return IssuerIdentifiers(
            entity_id=entity_id,
            isin=row["isin"],
            nse_symbol=row["nse"][0],
            bse_scrip=row["bse"][0],
            evidence_input_id=row["evidence_input_id"],
        )

    def list_packages(
        self, entity_id: int, family: FilingFamily, period_end: date
    ) -> tuple[FilingPackage, ...]:
        """Every package of one entity, family and period end, oldest knowledge first."""
        found = self._fetch(rows_sql.PACKAGES_FOR_PERIOD, (entity_id, family.value, period_end))
        return self.get_packages([row["id"] for row in found])

    def list_package_lineage(self, package_id: int) -> tuple[FilingPackage, ...]:
        """A package and every package it supersedes, oldest first."""
        ids = [row["id"] for row in self._fetch(rows_sql.PACKAGE_LINEAGE, (package_id,))]
        by_id = {package.package_id: package for package in self.get_packages(ids)}
        return tuple(by_id[package_id_] for package_id_ in ids)

    def list_capture_occurrences(
        self, capture_ref_id: int, extractor_version: str | None = None
    ) -> tuple[Occurrence, ...]:
        """Occurrences of one capture, optionally of one extractor generation."""
        if extractor_version is None:
            found = self._fetch(rows_sql.OCCURRENCES_OF_CAPTURE, (capture_ref_id,))
        else:
            found = self._fetch(
                rows_sql.OCCURRENCES_OF_GENERATION, (capture_ref_id, extractor_version)
            )
        return tuple(rows_sql.occurrence_of(row) for row in found)

    def list_interpretations(self, occurrence_ids: Sequence[int]) -> tuple[Interpretation, ...]:
        """Every interpretation of the given occurrences."""
        found = self._fetch(rows_sql.INTERPRETATIONS_OF_OCCURRENCES, (list(occurrence_ids),))
        return tuple(rows_sql.interpretation_of(row) for row in found)

    def list_capture_interpretations(self, capture_ref_id: int) -> tuple[Interpretation, ...]:
        """Every interpretation owned by one capture, direct and constructed."""
        found = self._fetch(rows_sql.INTERPRETATIONS_OF_CAPTURE, (capture_ref_id,))
        return tuple(rows_sql.interpretation_of(row) for row in found)

    def list_attempts(self, entity_id: int, period_end: date) -> tuple[AcquisitionAttempt, ...]:
        """Every attempt for one entity and period end."""
        found = self._fetch(rows_sql.ATTEMPTS_FOR_PERIOD, (entity_id, period_end))
        return tuple(rows_sql.attempt_of(row) for row in found)

    def list_generation_attempts(
        self,
        capture_ref_id: int,
        extractor_version: str,
        *,
        entity_id: int,
        period_end: date,
        basis: Basis,
        framework: AccountingFramework,
    ) -> tuple[AcquisitionAttempt, ...]:
        """The capture-owned extraction attempts of one extractor generation for one request
        scope (reuse level 2): a generation is reused only for the request it was checked for.
        """
        found = self._fetch(
            rows_sql.GENERATION_ATTEMPTS,
            (
                capture_ref_id,
                extractor_version,
                entity_id,
                period_end,
                basis.value,
                framework.value,
            ),
        )
        return tuple(rows_sql.attempt_of(row) for row in found)

    # --- immutable by-id reads (replay) ---------------------------------------------

    def get_capture_refs(self, ids: Sequence[int]) -> tuple[CaptureReference, ...]:
        """Stored capture registrations by id."""
        found = self._fetch(rows_sql.CAPTURE_REFS_BY_ID, (list(ids),))
        return tuple(rows_sql.capture_of(row) for row in found)

    def get_packages(self, ids: Sequence[int]) -> tuple[FilingPackage, ...]:
        """Stored packages by id, with members and statement roles."""
        packages = self._fetch(rows_sql.PACKAGES_BY_ID, (list(ids),))
        members = self._fetch(rows_sql.MEMBERS_OF_PACKAGES, (list(ids),))
        statements = [
            PackageStatementRecord.model_validate(row)
            for row in self._fetch(rows_sql.STATEMENTS_OF_PACKAGES, (list(ids),))
        ]
        return tuple(
            rows_sql.package_of(
                row,
                [member for member in members if member["package_id"] == row["id"]],
                [item for item in statements if item.package_id == row["id"]],
            )
            for row in packages
        )

    def get_package_statements(self, ids: Sequence[int]) -> tuple[PackageStatementRecord, ...]:
        """Stored package statement roles by id, with their evidence occurrence ids."""
        found = self._fetch(rows_sql.STATEMENTS_BY_ID, (list(ids),))
        return tuple(PackageStatementRecord.model_validate(row) for row in found)

    def get_package_statements_of(
        self, package_ids: Sequence[int]
    ) -> tuple[PackageStatementRecord, ...]:
        """Every statement role of the given packages."""
        found = self._fetch(rows_sql.STATEMENTS_OF_PACKAGES, (list(package_ids),))
        return tuple(PackageStatementRecord.model_validate(row) for row in found)

    def get_occurrences(self, ids: Sequence[int]) -> tuple[Occurrence, ...]:
        """Stored occurrences by id."""
        found = self._fetch(rows_sql.OCCURRENCES_BY_ID, (list(ids),))
        return tuple(rows_sql.occurrence_of(row) for row in found)

    def get_interpretations(self, ids: Sequence[int]) -> tuple[Interpretation, ...]:
        """Stored interpretations by id, with operands and condition evidence."""
        found = self._fetch(rows_sql.INTERPRETATIONS_BY_ID, (list(ids),))
        return tuple(rows_sql.interpretation_of(row) for row in found)

    def get_attempts(self, ids: Sequence[int]) -> tuple[AcquisitionAttempt, ...]:
        """Stored attempts by id."""
        found = self._fetch(rows_sql.ATTEMPTS_BY_ID, (list(ids),))
        return tuple(rows_sql.attempt_of(row) for row in found)

    @contextmanager
    def _transaction(self) -> Iterator[psycopg.Connection[Any]]:
        """One pooled connection inside one transaction."""
        with self._pool.connection() as conn, conn.transaction():
            yield conn

    def _fetch(self, query: LiteralString, params: tuple[object, ...]) -> list[dict[str, Any]]:
        """Run one parameterised read and return its rows as column dicts."""
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def _rows(
    conn: psycopg.Connection[Any], query: LiteralString, params: tuple[object, ...]
) -> list[dict[str, Any]]:
    """Run one parameterised statement on an open connection and return its rows."""
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _one_id(conn: psycopg.Connection[Any], query: LiteralString, params: tuple[object, ...]) -> int:
    """The id of the one row a natural-key select finds."""
    return int(_rows(conn, query, params)[0]["id"])


def _stored(value: int | None, what: str) -> int:
    """An id that must already be stored."""
    if value is None:
        raise ValueError(_UNSTORED.format(what=what))
    return value


def _insert_occurrences(
    conn: psycopg.Connection[Any], occurrences: Sequence[Occurrence]
) -> tuple[Occurrence, ...]:
    """Insert occurrences idempotently and read each back with its id."""
    if not occurrences:
        return ()
    with conn.cursor() as cursor:
        cursor.executemany(
            rows_sql.INSERT_OCCURRENCE, [rows_sql.occurrence_params(item) for item in occurrences]
        )
    stored: dict[tuple[int, str, str], int] = {}
    for capture_ref_id, extractor_version in {
        (_stored(item.capture.capture_ref_id, "occurrence capture"), item.extractor_version)
        for item in occurrences
    }:
        for row in _rows(
            conn, rows_sql.OCCURRENCES_OF_GENERATION, (capture_ref_id, extractor_version)
        ):
            stored[(capture_ref_id, extractor_version, row["anchor_key"])] = row["occurrence_id"]
    return tuple(
        item.model_copy(
            update={
                "occurrence_id": stored[
                    (item.capture.capture_ref_id or 0, item.extractor_version, item.anchor_key)
                ]
            }
        )
        for item in occurrences
    )


def _insert_attempt(
    conn: psycopg.Connection[Any], attempt: AcquisitionAttempt
) -> AcquisitionAttempt:
    """Insert one attempt idempotently and read the stored row back."""
    params = rows_sql.attempt_params(attempt)
    conn.execute(rows_sql.INSERT_ATTEMPT, (*params, attempt.reason))
    return rows_sql.attempt_of(_rows(conn, rows_sql.SELECT_ATTEMPT, params)[0])
