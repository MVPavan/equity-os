"""SQL text and row conversions for the evidence writes and reads (D1a Task 5).

Kept apart from :mod:`fundamentals.evidence.repository` so the repository class stays a
thin, readable list of operations. Every statement is parameterised.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from fractions import Fraction
from typing import Any, LiteralString

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    ValueKind,
)
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    KnowledgeTimeStatus,
    MissingValueState,
    Occurrence,
    PackageMember,
    PrecisionKind,
    RevisionCause,
    StatementRole,
    exact_decimal,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import ProvenCondition

Row = Mapping[str, Any]


class PackageStatementRecord(BaseModel):
    """One stored ``package_statements`` row with its evidence occurrence ids."""

    model_config = ConfigDict(frozen=True)

    id: int
    package_id: int
    statement_family: StatementFamily
    role: StatementRole
    evidence_occurrence_ids: tuple[int, ...]


class SegmentMemberWrite(BaseModel):
    """A segment member to record, with the occurrences that evidence it."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    axis: str
    member: str
    display_name: str
    valid_from: date
    evidence_occurrence_ids: tuple[int, ...]


# --- capture refs ---------------------------------------------------------------------

CAPTURE_COLUMNS: LiteralString = (
    "id, source_id, surface, request_key, capture_id, blob_sha256, record_sha256, "
    "registered_at, first_seen_at"
)
INSERT_CAPTURE_REF: LiteralString = (
    "INSERT INTO eqos.capture_refs (source_id, surface, request_key, capture_id, blob_sha256, "
    "record_sha256, registered_at, first_seen_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING"
)
SELECT_CAPTURE_REF: LiteralString = (
    "SELECT " + CAPTURE_COLUMNS + " FROM eqos.capture_refs "
    "WHERE source_id = %s AND surface = %s AND request_key = %s AND capture_id = %s"
)
FIND_CAPTURE_REF: LiteralString = (
    "SELECT " + CAPTURE_COLUMNS + " FROM eqos.capture_refs "
    "WHERE source_id = %s AND surface = %s AND blob_sha256 = %s ORDER BY id LIMIT 1"
)
CAPTURE_REFS_BY_ID: LiteralString = (
    "SELECT " + CAPTURE_COLUMNS + " FROM eqos.capture_refs WHERE id = ANY(%s) ORDER BY id"
)

# --- evidence inputs, settings --------------------------------------------------------

INSERT_EVIDENCE_INPUT: LiteralString = (
    "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) VALUES (%s, %s, %s) "
    "ON CONFLICT DO NOTHING"
)
SELECT_EVIDENCE_INPUT: LiteralString = (
    "SELECT id FROM eqos.evidence_inputs WHERE kind = %s AND content_sha256 = %s"
)
INSERT_SETTING: LiteralString = (
    "INSERT INTO eqos.settings_records "
    "(entity_id, setting_key, value_text, evidence_input_id, valid_from) "
    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
)
SELECT_SETTING: LiteralString = (
    "SELECT id FROM eqos.settings_records "
    "WHERE entity_id = %s AND setting_key = %s AND value_text = %s AND evidence_input_id = %s"
)

_SETTINGS_COLUMNS: LiteralString = (
    "SELECT id, entity_id, setting_key, value_text, evidence_input_id, recorded_at, valid_from "
    "FROM eqos.settings_records "
)
# The governing rule (plan D6 D5): null valid_from governs every period and ranks last.
SETTINGS_AS_OF: LiteralString = (
    _SETTINGS_COLUMNS + "WHERE entity_id = %s AND setting_key = %s AND recorded_at <= %s "
    "AND (%s::date IS NULL OR valid_from IS NULL OR valid_from <= %s::date) "
    "ORDER BY valid_from DESC NULLS LAST, recorded_at DESC, id DESC LIMIT 1"
)
SETTINGS_BY_ID: LiteralString = _SETTINGS_COLUMNS + "WHERE id = ANY(%s) ORDER BY id"

ENTITY_BY_KEY: LiteralString = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"

# --- packages -------------------------------------------------------------------------

INSERT_PACKAGE: LiteralString = (
    "INSERT INTO eqos.filing_packages (entity_id, family, reporting_period_end, basis, "
    "framework, reporting_kind, knowledge_time, supersedes_package_id, evidence_sha256) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id"
)
SELECT_PACKAGE_ID: LiteralString = (
    "SELECT id FROM eqos.filing_packages WHERE entity_id = %s AND family = %s "
    "AND reporting_period_end = %s AND basis = %s AND framework = %s AND evidence_sha256 = %s"
)
INSERT_MEMBER: LiteralString = (
    "INSERT INTO eqos.package_members (package_id, capture_ref_id, representation, "
    "knowledge_time, knowledge_time_raw, knowledge_time_status) VALUES (%s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING"
)
INSERT_STATEMENT: LiteralString = (
    "INSERT INTO eqos.package_statements (package_id, statement_family, role) "
    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
)
SELECT_STATEMENT_ID: LiteralString = (
    "SELECT id FROM eqos.package_statements "
    "WHERE package_id = %s AND statement_family = %s AND role = %s"
)
INSERT_STATEMENT_EVIDENCE: LiteralString = (
    "INSERT INTO eqos.package_statement_evidence (package_statement_id, occurrence_id) "
    "VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
PACKAGE_COLUMNS: LiteralString = (
    "SELECT id, entity_id, family, reporting_period_end, basis, framework, reporting_kind, "
    "knowledge_time, supersedes_package_id, evidence_sha256 FROM eqos.filing_packages "
)
PACKAGES_BY_ID: LiteralString = PACKAGE_COLUMNS + "WHERE id = ANY(%s) ORDER BY id"
PACKAGES_FOR_PERIOD: LiteralString = (
    PACKAGE_COLUMNS + "WHERE entity_id = %s AND family = %s AND reporting_period_end = %s "
    "ORDER BY knowledge_time, id"
)
PACKAGE_LINEAGE: LiteralString = (
    "WITH RECURSIVE lineage(id, supersedes_package_id, depth) AS ("
    " SELECT id, supersedes_package_id, 0 FROM eqos.filing_packages WHERE id = %s"
    " UNION ALL SELECT p.id, p.supersedes_package_id, l.depth + 1"
    " FROM eqos.filing_packages p JOIN lineage l ON p.id = l.supersedes_package_id"
    ") SELECT id FROM lineage ORDER BY depth DESC"
)
MEMBERS_OF_PACKAGES: LiteralString = (
    "SELECT m.package_id, m.representation, m.knowledge_time, m.knowledge_time_raw, "
    "m.knowledge_time_status, c.id, c.source_id, c.surface, c.request_key, c.capture_id, "
    "c.blob_sha256, c.record_sha256, c.registered_at, c.first_seen_at "
    "FROM eqos.package_members m JOIN eqos.capture_refs c ON c.id = m.capture_ref_id "
    "WHERE m.package_id = ANY(%s) ORDER BY m.package_id, m.id"
)
STATEMENT_COLUMNS: LiteralString = (
    "SELECT s.id, s.package_id, s.statement_family, s.role, "
    "COALESCE(array_agg(e.occurrence_id ORDER BY e.occurrence_id) "
    "FILTER (WHERE e.occurrence_id IS NOT NULL), '{}') AS evidence_occurrence_ids "
    "FROM eqos.package_statements s "
    "LEFT JOIN eqos.package_statement_evidence e ON e.package_statement_id = s.id "
)
STATEMENTS_BY_ID: LiteralString = (
    STATEMENT_COLUMNS + "WHERE s.id = ANY(%s) GROUP BY s.id ORDER BY s.id"
)
STATEMENTS_OF_PACKAGES: LiteralString = (
    STATEMENT_COLUMNS + "WHERE s.package_id = ANY(%s) GROUP BY s.id ORDER BY s.id"
)

# --- occurrences ----------------------------------------------------------------------

INSERT_OCCURRENCE: LiteralString = (
    "INSERT INTO eqos.occurrences (capture_ref_id, representation, extractor_version, "
    "native_field, raw_value_text, raw_unit, raw_scale, raw_sign, precision_kind, "
    "declared_precision, native_context, period_start, period_end, period_instant, "
    "missing_state, disclosure, anchor, anchor_key, valid_time, knowledge_time, "
    "knowledge_time_status, first_seen_at, revision_cause) VALUES (%s, %s, %s, %s, %s, %s, "
    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING"
)
OCCURRENCE_COLUMNS: LiteralString = (
    "SELECT o.id AS occurrence_id, o.representation, o.extractor_version, o.native_field, "
    "o.raw_value_text, o.raw_unit, o.raw_scale, o.raw_sign, o.precision_kind, "
    "o.declared_precision, o.native_context, o.period_start, o.period_end, o.period_instant, "
    "o.missing_state, o.disclosure, o.anchor, o.anchor_key, o.knowledge_time, "
    "o.knowledge_time_status, o.first_seen_at, o.revision_cause, "
    "c.id, c.source_id, c.surface, c.request_key, c.capture_id, c.blob_sha256, "
    "c.record_sha256, c.registered_at, c.first_seen_at AS capture_first_seen_at "
    "FROM eqos.occurrences o JOIN eqos.capture_refs c ON c.id = o.capture_ref_id "
)
OCCURRENCES_OF_GENERATION: LiteralString = (
    OCCURRENCE_COLUMNS + "WHERE o.capture_ref_id = %s AND o.extractor_version = %s ORDER BY o.id"
)
OCCURRENCES_OF_CAPTURE: LiteralString = (
    OCCURRENCE_COLUMNS + "WHERE o.capture_ref_id = %s ORDER BY o.id"
)
OCCURRENCES_BY_ID: LiteralString = OCCURRENCE_COLUMNS + "WHERE o.id = ANY(%s) ORDER BY o.id"

# --- attempts -------------------------------------------------------------------------

ATTEMPT_KEY: LiteralString = (
    "stage, source_id, surface, entity_id, period_end, basis, framework, representation, "
    "statement_family, package_id, capture_ref_id, input_sha256, extractor_version, outcome, "
    "extraction_context_sha256"
)
INSERT_ATTEMPT: LiteralString = (
    "INSERT INTO eqos.acquisition_attempts (" + ATTEMPT_KEY + ", reason) VALUES (%s, %s, %s, "
    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"
)
ATTEMPT_COLUMNS: LiteralString = (
    "SELECT a.id AS attempt_id, a.stage, a.source_id AS attempt_source_id, "
    "a.surface AS attempt_surface, a.entity_id, a.period_end, a.basis, a.framework, "
    "a.representation, a.statement_family, a.package_id, a.outcome, a.reason, "
    "a.input_sha256, a.extractor_version, a.extraction_context_sha256, a.attempted_at, "
    "c.id, c.source_id, c.surface, c.request_key, c.capture_id, c.blob_sha256, "
    "c.record_sha256, c.registered_at, c.first_seen_at "
    "FROM eqos.acquisition_attempts a LEFT JOIN eqos.capture_refs c ON c.id = a.capture_ref_id "
)
SELECT_ATTEMPT: LiteralString = (
    ATTEMPT_COLUMNS + "WHERE a.stage = %s AND a.source_id = %s AND a.surface = %s "
    "AND a.entity_id = %s AND a.period_end = %s AND a.basis = %s AND a.framework = %s "
    "AND a.representation = %s AND a.statement_family IS NOT DISTINCT FROM %s "
    "AND a.package_id IS NOT DISTINCT FROM %s AND a.capture_ref_id IS NOT DISTINCT FROM %s "
    "AND a.input_sha256 = %s AND a.extractor_version = %s AND a.outcome = %s "
    "AND a.extraction_context_sha256 IS NOT DISTINCT FROM %s"
)
ATTEMPTS_BY_ID: LiteralString = ATTEMPT_COLUMNS + "WHERE a.id = ANY(%s) ORDER BY a.id"
ATTEMPTS_FOR_PERIOD: LiteralString = (
    ATTEMPT_COLUMNS + "WHERE a.entity_id = %s AND a.period_end = %s ORDER BY a.id"
)
GENERATION_ATTEMPTS: LiteralString = (
    ATTEMPT_COLUMNS + "WHERE a.stage = 'EXTRACTION' AND a.capture_ref_id = %s "
    "AND a.extractor_version = %s AND a.entity_id = %s AND a.period_end = %s AND a.basis = %s "
    "AND a.framework = %s AND a.package_id IS NULL ORDER BY a.id"
)

# --- interpretations ------------------------------------------------------------------

RESERVE_INTERPRETATION_IDS: LiteralString = (
    "SELECT nextval(pg_get_serial_sequence('eqos.interpretations', 'id')) AS id "
    "FROM generate_series(1, %s)"
)
STORE_CLOCK: LiteralString = "SELECT eqos.store_now() AS now"
INSERT_INTERPRETATION: LiteralString = (
    "INSERT INTO eqos.interpretations (id, origin, occurrence_id, capture_ref_id, "
    "representation, construction_rule_id, input_digest, status, entity_id, canonical_id, "
    "dictionary_version, period_start, period_end, period_instant, basis, framework, currency, "
    "value_kind, dimension_set, dimension_hash, key_digest, value, lower, upper, tier, "
    "qualification_ref, mapping_set_version, mapping_entry_id, normalisation_policy_version, "
    "extractor_version, transform_trace, reason, revision_cause, supersedes_interpretation_id, "
    "recorded_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
INSERT_OPERAND: LiteralString = (
    "INSERT INTO eqos.interpretation_operands (interpretation_id, ordinal, "
    "operand_interpretation_id) VALUES (%s, %s, %s)"
)
INSERT_CONDITION_EVIDENCE: LiteralString = (
    "INSERT INTO eqos.interpretation_condition_evidence (interpretation_id, condition_id, "
    "holds, evidence_interpretation_id) VALUES (%s, %s, %s, %s)"
)
INTERPRETATION_COLUMNS: LiteralString = (
    "SELECT i.*, "
    "COALESCE((SELECT array_agg(o.operand_interpretation_id ORDER BY o.ordinal) "
    " FROM eqos.interpretation_operands o WHERE o.interpretation_id = i.id), '{}') AS operands, "
    "COALESCE((SELECT jsonb_agg(jsonb_build_array(e.condition_id, e.holds, "
    " e.evidence_interpretation_id) ORDER BY e.condition_id, e.evidence_interpretation_id) "
    " FROM eqos.interpretation_condition_evidence e WHERE e.interpretation_id = i.id), "
    " '[]'::jsonb) AS conditions "
    "FROM eqos.interpretations i "
)
INTERPRETATIONS_BY_ID: LiteralString = INTERPRETATION_COLUMNS + "WHERE i.id = ANY(%s) ORDER BY i.id"
INTERPRETATIONS_OF_OCCURRENCES: LiteralString = (
    INTERPRETATION_COLUMNS + "WHERE i.occurrence_id = ANY(%s) ORDER BY i.id"
)
INTERPRETATIONS_OF_CAPTURE: LiteralString = (
    INTERPRETATION_COLUMNS + "WHERE i.capture_ref_id = %s ORDER BY i.id"
)

# --- version pins (0003) ----------------------------------------------------------------

INSERT_VERSION_PIN: LiteralString = (
    "INSERT INTO eqos.version_pins (artifact, version, content_sha256) VALUES (%s, %s, %s) "
    "ON CONFLICT DO NOTHING RETURNING id"
)
SELECT_VERSION_PIN: LiteralString = (
    "SELECT content_sha256 FROM eqos.version_pins WHERE artifact = %s AND version = %s"
)

# --- segment members ------------------------------------------------------------------

INSERT_SEGMENT_MEMBER: LiteralString = (
    "INSERT INTO eqos.segment_members (entity_id, axis, member, display_name, valid_from) "
    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id"
)
SELECT_SEGMENT_MEMBER: LiteralString = (
    "SELECT id FROM eqos.segment_members WHERE entity_id = %s AND axis = %s AND member = %s "
    "AND valid_from = %s AND valid_to IS NULL"
)
INSERT_SEGMENT_EVIDENCE: LiteralString = (
    "INSERT INTO eqos.segment_member_evidence (segment_member_id, occurrence_id) "
    "VALUES (%s, %s) ON CONFLICT DO NOTHING"
)


def json_value(value: Mapping[str, object]) -> Jsonb:
    """A strict JSON parameter: anything not plain JSON is a defect, never stringified."""
    return Jsonb(_plain(value))


def _plain(value: object) -> object:
    """Plain containers all the way down so ``json.dumps`` sees only JSON types."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    json.dumps(value)
    return value


def period_params(period: PeriodInterval | None) -> tuple[date | None, date | None, date | None]:
    """A period's three storage columns."""
    if period is None:
        return None, None, None
    return period.start, period.end, period.instant


def period_of(row: Row, prefix: str = "period_") -> PeriodInterval | None:
    """A stored period, or ``None`` when all three columns are null."""
    start, end, instant = row[prefix + "start"], row[prefix + "end"], row[prefix + "instant"]
    if instant is not None:
        return PeriodInterval.at(instant)
    if start is not None and end is not None:
        return PeriodInterval.duration(start, end)
    return None


def capture_of(row: Row, *, first_seen_column: str = "first_seen_at") -> CaptureReference:
    """A capture reference from ``capture_refs`` columns in a row."""
    return CaptureReference(
        capture_ref_id=row["id"],
        source_id=row["source_id"],
        surface=row["surface"],
        request_key=row["request_key"],
        capture_id=row["capture_id"],
        blob_sha256=row["blob_sha256"],
        record_sha256=row["record_sha256"],
        registered_at=row["registered_at"],
        first_seen_at=row[first_seen_column],
    )


def capture_params(ref: CaptureReference) -> tuple[object, ...]:
    """Insert parameters of one capture reference."""
    return (
        ref.source_id,
        ref.surface,
        ref.request_key,
        ref.capture_id,
        ref.blob_sha256,
        ref.record_sha256,
        ref.registered_at,
        ref.first_seen_at,
    )


def occurrence_params(occurrence: Occurrence) -> tuple[object, ...]:
    """Insert parameters of one occurrence."""
    return (
        occurrence.capture.capture_ref_id,
        occurrence.representation.value,
        occurrence.extractor_version,
        occurrence.native_field,
        occurrence.raw_value_text,
        occurrence.raw_unit,
        occurrence.raw_scale,
        occurrence.raw_sign,
        occurrence.precision_kind.value,
        occurrence.declared_precision,
        json_value(occurrence.native_context),
        *period_params(occurrence.period),
        occurrence.missing_state.value,
        json_value(occurrence.disclosure),
        json_value(occurrence.anchor),
        occurrence.anchor_key,
        occurrence.valid_time,
        occurrence.knowledge_time,
        occurrence.knowledge_time_status.value,
        occurrence.first_seen_at,
        occurrence.revision_cause.value,
    )


def occurrence_of(row: Row) -> Occurrence:
    """An occurrence from a joined occurrence/capture row."""
    return Occurrence(
        occurrence_id=row["occurrence_id"],
        capture=capture_of(row, first_seen_column="capture_first_seen_at"),
        representation=Representation(row["representation"]),
        extractor_version=row["extractor_version"],
        native_field=row["native_field"],
        raw_value_text=row["raw_value_text"],
        raw_unit=row["raw_unit"],
        raw_scale=row["raw_scale"],
        raw_sign=row["raw_sign"],
        precision_kind=PrecisionKind(row["precision_kind"]),
        declared_precision=row["declared_precision"],
        native_context=row["native_context"],
        period=period_of(row),
        missing_state=MissingValueState(row["missing_state"]),
        disclosure=row["disclosure"],
        anchor=row["anchor"],
        anchor_key=row["anchor_key"],
        knowledge_time=row["knowledge_time"],
        knowledge_time_status=KnowledgeTimeStatus(row["knowledge_time_status"]),
        first_seen_at=row["first_seen_at"],
        revision_cause=RevisionCause(row["revision_cause"]),
    )


def attempt_params(attempt: AcquisitionAttempt) -> tuple[object, ...]:
    """Key parameters of one attempt, in ``ATTEMPT_KEY`` order."""
    return (
        attempt.stage.value,
        attempt.source_id,
        attempt.surface,
        attempt.entity_id,
        attempt.period_end,
        attempt.basis.value,
        attempt.framework.value,
        attempt.representation.value,
        attempt.statement_family.value if attempt.statement_family is not None else None,
        attempt.package_id,
        attempt.capture.capture_ref_id if attempt.capture is not None else None,
        attempt.input_sha256,
        attempt.extractor_version,
        attempt.outcome.value,
        attempt.extraction_context_sha256,
    )


def attempt_of(row: Row) -> AcquisitionAttempt:
    """An attempt from a joined attempt/capture row."""
    family = row["statement_family"]
    return AcquisitionAttempt(
        attempt_id=row["attempt_id"],
        stage=AttemptStage(row["stage"]),
        source_id=row["attempt_source_id"],
        surface=row["attempt_surface"],
        entity_id=row["entity_id"],
        period_end=row["period_end"],
        basis=Basis(row["basis"]),
        framework=AccountingFramework(row["framework"]),
        representation=Representation(row["representation"]),
        statement_family=StatementFamily(family) if family is not None else None,
        package_id=row["package_id"],
        outcome=ExtractionOutcome(row["outcome"]),
        reason=row["reason"],
        capture=capture_of(row) if row["id"] is not None else None,
        input_sha256=row["input_sha256"],
        extractor_version=row["extractor_version"],
        extraction_context_sha256=row["extraction_context_sha256"],
        attempted_at=row["attempted_at"],
    )


def interpretation_params(item: Interpretation) -> tuple[object, ...]:
    """Insert parameters of one interpretation (its id reserved in advance)."""
    key = item.key
    dimensions = item.dimensions
    period = key.period if key is not None else item.period
    interval = item.interval
    return (
        item.interpretation_id,
        item.origin.value,
        item.occurrence_id,
        item.capture_ref_id,
        item.representation.value,
        item.construction_rule_id,
        item.input_digest,
        item.status.value,
        item.entity_id,
        item.canonical_id,
        item.dictionary_version,
        *period_params(period),
        item.basis.value,
        item.framework.value,
        key.currency if key is not None else None,
        key.value_kind.value if key is not None else None,
        Jsonb([list(pair) for pair in dimensions.pairs]) if dimensions is not None else None,
        dimensions.digest() if dimensions is not None else None,
        key.digest() if key is not None else None,
        item.value,
        exact_decimal(interval.lower) if interval is not None else None,
        exact_decimal(interval.upper) if interval is not None else None,
        item.tier.value,
        item.qualification_ref,
        item.mapping_set_version,
        item.mapping_entry_id,
        item.normalisation_policy_version,
        item.extractor_version,
        json_value(item.transform_trace),
        item.reason.value if item.reason is not None else None,
        item.revision_cause.value,
        item.supersedes_interpretation_id,
        item.recorded_at,
    )


def interpretation_of(row: Row) -> Interpretation:
    """An interpretation with its operands and condition evidence."""
    period = period_of(row)
    stored = row["dimension_set"]
    dimensions = (
        DimensionSet(pairs=tuple(tuple(pair) for pair in stored)) if stored is not None else None
    )
    key = None
    if row["key_digest"] is not None and period is not None and dimensions is not None:
        key = MeasurementKey(
            entity_id=row["entity_id"],
            canonical_id=row["canonical_id"],
            period=period,
            basis=Basis(row["basis"]),
            framework=AccountingFramework(row["framework"]),
            currency=row["currency"],
            value_kind=ValueKind(row["value_kind"]),
            dimensions=dimensions,
        )
    lower, upper = row["lower"], row["upper"]
    reason = row["reason"]
    return Interpretation(
        interpretation_id=row["id"],
        origin=InterpretationOrigin(row["origin"]),
        occurrence_id=row["occurrence_id"],
        capture_ref_id=row["capture_ref_id"],
        representation=Representation(row["representation"]),
        construction_rule_id=row["construction_rule_id"],
        operand_interpretation_ids=tuple(row["operands"]),
        input_digest=row["input_digest"],
        status=InterpretationStatus(row["status"]),
        entity_id=row["entity_id"],
        basis=Basis(row["basis"]),
        framework=AccountingFramework(row["framework"]),
        canonical_id=row["canonical_id"],
        period=period,
        dictionary_version=row["dictionary_version"],
        key=key,
        dimensions=dimensions,
        value=row["value"],
        interval=(
            Interval(lower=Fraction(lower), upper=Fraction(upper))
            if lower is not None and upper is not None
            else None
        ),
        tier=EvidenceTier(row["tier"]),
        mapping_set_version=row["mapping_set_version"],
        mapping_entry_id=row["mapping_entry_id"],
        qualification_ref=row["qualification_ref"],
        condition_evidence=_conditions(row["conditions"]),
        normalisation_policy_version=row["normalisation_policy_version"],
        extractor_version=row["extractor_version"],
        transform_trace=row["transform_trace"],
        reason=InterpretationReason(reason) if reason is not None else None,
        revision_cause=RevisionCause(row["revision_cause"]),
        supersedes_interpretation_id=row["supersedes_interpretation_id"],
        recorded_at=row["recorded_at"],
    )


def _conditions(rows: Sequence[Sequence[Any]]) -> tuple[ProvenCondition, ...]:
    """Condition evidence rows regrouped into one proof per condition."""
    grouped: dict[tuple[str, bool], list[int]] = {}
    for condition_id, holds, evidence_id in rows:
        grouped.setdefault((condition_id, holds), []).append(evidence_id)
    return tuple(
        ProvenCondition(
            condition_id=condition_id, holds=holds, evidence_interpretation_ids=tuple(ids)
        )
        for (condition_id, holds), ids in grouped.items()
    )


def package_of(
    row: Row, members: Sequence[Row], statements: Sequence[PackageStatementRecord]
) -> FilingPackage:
    """A package with its members and statement roles."""
    return FilingPackage(
        package_id=row["id"],
        entity_id=row["entity_id"],
        family=FilingFamily(row["family"]),
        reporting_period_end=row["reporting_period_end"],
        basis=Basis(row["basis"]),
        framework=AccountingFramework(row["framework"]),
        reporting_kind=PeriodKind(row["reporting_kind"]),
        knowledge_time=row["knowledge_time"],
        supersedes_package_id=row["supersedes_package_id"],
        replaced_statements=frozenset(
            item.statement_family for item in statements if item.role is StatementRole.REPLACED
        ),
        statements_present=frozenset(
            item.statement_family for item in statements if item.role is StatementRole.PRESENT
        ),
        members={
            Representation(member["representation"]): PackageMember(
                representation=Representation(member["representation"]),
                capture=capture_of(member),
                knowledge_time=member["knowledge_time"],
                knowledge_time_raw=member["knowledge_time_raw"],
                knowledge_time_status=KnowledgeTimeStatus(member["knowledge_time_status"]),
            )
            for member in members
        },
        evidence_sha256=row["evidence_sha256"],
    )
