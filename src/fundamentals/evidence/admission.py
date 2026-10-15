"""First-party fact admission, selection and the admitted-fact read (data spec §4; plan D2 Task 4).

Admission copies a run's first-party ``REPORTED`` cell into a native fact store only when its
extraction is ``AGREE`` (or ``NOT_APPLICABLE`` on one first-party value) and no open
non-diagnostic HIGH item names it in the queue overlay current at admission. The value is the
run-selected DIRECT interpretation's occurrence (XBRL preferred), bridged to a ``Fact``. Vendor
values are never candidates. Admission never selects: selection and the read are separate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.queue import overlay_at
from fundamentals.compare.report import key_unit
from fundamentals.compare.run_models import ResultRow
from fundamentals.compare.run_store import RunStore
from fundamentals.compare.trust import open_high
from fundamentals.contracts.canonical import Representation, ValueIdentity
from fundamentals.contracts.comparison import ExtractionStatus, SourceRole, SourceState
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    KnowledgeTimeStatus,
    Occurrence,
    PrecisionKind,
    RunMode,
)
from fundamentals.contracts.fact import CanonicalStatus, Fact, ReconciliationStatus
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.observation import Observation, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.review_queue import QueueOverlay
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.extract.xbrl_parser import INF_DECIMALS
from fundamentals.store.fact_store import FactRef, FactStore, FactStoreLike, StoredRevision
from fundamentals.store.pg_fact_store import PgFactStore, insert_revision, run_serializable

BRIDGE_VERSION = "admission-bridge/1"
ADMITTED_CONCEPT_PREFIX = "eqos:"
_NAMESPACE = "eqos-dictionary"
_ENTITY_SCHEME = "eqos-reporting-entity"
_FAMILY_PREFIX = "admitted:"

_NOW: LiteralString = "SELECT eqos.store_now() AS now"
_RESULT_ID: LiteralString = (
    "SELECT id FROM eqos.results WHERE run_id = %s AND key_digest = %s AND value_identity = %s"
)
_INSERT: LiteralString = """
INSERT INTO eqos.fact_admissions (store_id, row_handle, fact_origin, fact_origin_id, run_id,
    result_id, interpretation_id, occurrence_id, overlay_position, bridge_version)
SELECT target_store, handle, origin, origin_id, %(run_id)s, %(result_id)s,
    %(interpretation_id)s, %(occurrence_id)s, %(position)s, %(bridge)s
FROM eqos.fact_rows WHERE target_store = %(store)s AND handle = %(handle)s
ON CONFLICT (store_id, result_id, interpretation_id) DO NOTHING RETURNING id
"""
_RECORD: LiteralString = """
SELECT id AS admission_id, row_handle AS handle, store_id, fact_origin AS origin,
    fact_origin_id AS origin_id, run_id, result_id, interpretation_id, occurrence_id,
    overlay_position
FROM eqos.fact_admissions WHERE store_id = %s AND result_id = %s AND interpretation_id = %s
"""
_HANDLE: LiteralString = (
    "SELECT row_handle FROM eqos.fact_admissions WHERE id = %s AND store_id = %s"
)


class BridgeError(ValueError):
    """An interpretation or occurrence that cannot become an admitted ``Fact``."""


class AdmissionRefusal(StrEnum):
    """Why a run cell was not admitted; every non-admitted cell gets exactly one."""

    NOT_REPORTED = "NOT_REPORTED"
    EXTRACTION_NOT_AGREE = "EXTRACTION_NOT_AGREE"
    NOT_SINGLE_REPRESENTATION = "NOT_SINGLE_REPRESENTATION"
    OPEN_HIGH = "OPEN_HIGH"
    NO_DIRECT_OCCURRENCE = "NO_DIRECT_OCCURRENCE"
    KNOWLEDGE_TIME_UNKNOWN = "KNOWLEDGE_TIME_UNKNOWN"


class AdmissionRecord(BaseModel):
    """One stored admission: the fact it admitted and the run evidence that authorized it."""

    model_config = ConfigDict(frozen=True)

    admission_id: int
    ref: FactRef
    handle: int
    run_id: int
    result_id: int
    interpretation_id: int
    occurrence_id: int
    overlay_position: datetime


class AdmissionOutcome(BaseModel):
    """One ``admit_run``: every admitted record, every refusal and how many rows it created."""

    model_config = ConfigDict(frozen=True)

    records: tuple[AdmissionRecord, ...]
    refusals: tuple[tuple[str, AdmissionRefusal], ...]
    created: int


class SelectedFact(BaseModel):
    """An admitted fact as selected at a cutoff, with its ref and provenance."""

    model_config = ConfigDict(frozen=True)

    value: Decimal
    unit: str
    ref: FactRef
    provenance: Provenance
    selected_at: datetime


def admit_run(run_id: int, *, pool: ConnectionPool, store_id: str) -> AdmissionOutcome:
    """Admit every eligible cell of a stored run into ``store_id`` atomically and idempotently.

    The overlay is read at the transaction's own store-clock position, after the queue lock, so
    it is complete and current; no older overlay can authorize an admission.
    """
    rows = RunStore(pool).read_results(run_id)
    repository = EvidenceRepository(pool)
    interpretations = {
        item.interpretation_id: item
        for item in repository.get_interpretations(
            sorted({value.interpretation_id for row in rows for value in _first_party(row)})
        )
    }
    occurrences = {
        item.occurrence_id: item
        for item in repository.get_occurrences(
            sorted({i.occurrence_id for i in interpretations.values() if i.occurrence_id})
        )
    }

    def admit(cursor: Cursor[dict[str, Any]]) -> AdmissionOutcome:
        position: datetime = _one(cursor, _NOW, ())["now"]
        overlay = overlay_at(cursor, run_id=run_id, as_of=position)
        records: list[AdmissionRecord] = []
        refusals: list[tuple[str, AdmissionRefusal]] = []
        created = 0
        for row in rows:
            decision = _decide(row, overlay, interpretations, occurrences)
            if isinstance(decision, AdmissionRefusal):
                refusals.append((row.row_id, decision))
                continue
            interpretation, occurrence = decision
            fact = fact_for(
                interpretation,
                occurrence,
                row.key,
                run_id=run_id,
                reconciliation=ReconciliationStatus.CROSS_SOURCE_CONFIRMED
                if row.extraction_status is ExtractionStatus.AGREE
                else ReconciliationStatus.UNRECONCILED,
            )
            identity = (run_id, row.key.digest(), row.value_identity.value)
            result_id = _one(cursor, _RESULT_ID, identity)["id"]
            params = {
                "store": store_id,
                "handle": insert_revision(cursor, store_id, fact),
                "run_id": run_id,
                "result_id": result_id,
                "interpretation_id": interpretation.interpretation_id,
                "occurrence_id": occurrence.occurrence_id,
                "position": position,
                "bridge": BRIDGE_VERSION,
            }
            created += cursor.execute(_INSERT, params).rowcount
            stored = _one(cursor, _RECORD, (store_id, result_id, interpretation.interpretation_id))
            records.append(AdmissionRecord.model_validate(stored | {"ref": stored}))
        return AdmissionOutcome(records=tuple(records), refusals=tuple(refusals), created=created)

    return run_serializable(pool, store_id, admit)


def fact_for(
    interpretation: Interpretation,
    occurrence: Occurrence | None,
    key: MeasurementKey,
    *,
    run_id: int,
    reconciliation: ReconciliationStatus,
) -> Fact:
    """Bridge a DIRECT interpretation and its occurrence to an admitted ``Fact`` on ``key``."""
    if (
        interpretation.origin is not InterpretationOrigin.DIRECT
        or occurrence is None
        or occurrence.occurrence_id != interpretation.occurrence_id
    ):
        raise BridgeError("only a DIRECT interpretation with its own occurrence is admitted")
    if (
        interpretation.value is None
        or occurrence.raw_value_text is None
        or occurrence.knowledge_time is None
    ):
        raise BridgeError("the occurrence carries no value or no known knowledge time")
    capture = occurrence.capture
    location = _location(occurrence)
    provenance = Provenance(
        source_id=capture.source_id,
        file_sha256=capture.blob_sha256,
        retrieved_at=capture.registered_at.astimezone(UTC),
        first_seen_at=occurrence.first_seen_at.astimezone(UTC),
        **location,
    )
    period = key.period
    valid_from = period.start or period.instant
    assert valid_from is not None  # a period is a duration or an instant
    return Fact(
        observation=Observation(
            **_key_fields(key),
            taxonomy_namespace=_NAMESPACE,
            registry_version=interpretation.dictionary_version,
            raw_value=occurrence.raw_value_text,
            normalized_value=interpretation.value,
            context_ref=location.get("context_ref"),
            decimals=_decimals(occurrence),
            provenance=provenance,
        ),
        reconciliation_status=reconciliation,
        canonical_status=CanonicalStatus.CANDIDATE,
        revision_family=f"{_FAMILY_PREFIX}{key.digest()}",
        run_id=str(run_id),
        valid_time_start=valid_from,
        valid_time_end=period.end,
        knowledge_time=occurrence.knowledge_time.astimezone(UTC),
        first_seen_time=occurrence.first_seen_at.astimezone(UTC),
    )


def key_identity(key: MeasurementKey) -> str:
    """The fact-store content identity of every admitted revision of ``key``."""
    return FactStore.content_identity_for(Observation.model_construct(**_key_fields(key)))


def select_admitted(
    pool: ConnectionPool,
    *,
    store_id: str,
    admission_id: int,
    reason: str,
    expected_selection_id: int,
) -> StoredRevision:
    """Select an admission's fact as canonical in its own store."""
    with pool.connection() as conn:
        row = conn.execute(_HANDLE, (admission_id, store_id)).fetchone()
    if row is None:
        raise KeyError(f"no admission {admission_id} in store {store_id}")
    return PgFactStore(pool, store_id).select_canonical(
        int(row[0]), reason, expected_selection_id=expected_selection_id
    )


def read_selected(
    store: FactStoreLike, key: MeasurementKey, *, cutoff: datetime, mode: RunMode
) -> SelectedFact | None:
    """The selected admitted fact for ``key``: as known at ``cutoff``, or (retrospective) the
    current selection if its fact was known and first seen by ``cutoff``."""
    identity = key_identity(key)
    if mode is RunMode.AS_KNOWN:
        revision = store.get_canonical(identity, cutoff=cutoff)
    else:
        revision = store.get_canonical(identity)
        if revision is not None:
            fact = revision.fact
            if max(fact.knowledge_time, fact.first_seen_time) > cutoff:
                revision = None
    if revision is None:
        return None
    observation = revision.fact.observation
    assert revision.canonical_selected_at is not None
    return SelectedFact(
        value=observation.normalized_value,
        unit=observation.normalized_unit,
        ref=store.fact_ref(revision.row_id),
        provenance=observation.provenance,
        selected_at=revision.canonical_selected_at,
    )


def _one(
    cursor: Cursor[dict[str, Any]], query: LiteralString, params: tuple[object, ...]
) -> dict[str, Any]:
    """The single row a query must return."""
    row = cursor.execute(query, params).fetchone()
    assert row is not None
    return row


def _first_party(row: ResultRow) -> list[Any]:
    """A row's first-party source values that carry a value and its interpretation."""
    return [
        value
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY
        and value.state is SourceState.VALUE
        and value.interpretation_id is not None
    ]


def _decide(
    row: ResultRow,
    overlay: QueueOverlay,
    interpretations: dict[int | None, Interpretation],
    occurrences: dict[int | None, Occurrence],
) -> AdmissionRefusal | tuple[Interpretation, Occurrence]:
    """The §4 rule for one cell: its admitted interpretation and occurrence, or one refusal."""
    if row.value_identity is not ValueIdentity.REPORTED:
        return AdmissionRefusal.NOT_REPORTED
    values = _first_party(row)
    if row.extraction_status is ExtractionStatus.NOT_APPLICABLE:
        if len(values) != 1:
            return AdmissionRefusal.NOT_SINGLE_REPRESENTATION
    elif row.extraction_status is not ExtractionStatus.AGREE:
        return AdmissionRefusal.EXTRACTION_NOT_AGREE
    if open_high(overlay, row.key):
        return AdmissionRefusal.OPEN_HIGH
    direct = {
        value.representation: interpretations[value.interpretation_id]
        for value in values
        if interpretations[value.interpretation_id].origin is InterpretationOrigin.DIRECT
    }
    chosen = direct.get(Representation.XBRL) or direct.get(Representation.PDF)
    if chosen is None:
        return AdmissionRefusal.NO_DIRECT_OCCURRENCE
    occurrence = occurrences[chosen.occurrence_id]
    if occurrence.knowledge_time_status is not KnowledgeTimeStatus.KNOWN:
        return AdmissionRefusal.KNOWLEDGE_TIME_UNKNOWN
    return chosen, occurrence


def _key_fields(key: MeasurementKey) -> dict[str, Any]:
    """The observation fields that the fact store's content identity reads, from ``key``."""
    period = key.period
    return {
        "concept_qname": f"{ADMITTED_CONCEPT_PREFIX}{key.canonical_id}",
        "normalized_unit": key_unit(key),
        "entity_scheme": _ENTITY_SCHEME,
        "entity_id": str(key.entity_id),
        "scope": Scope(key.basis.value.lower()),
        "accounting_basis": key.framework,
        "period_type": PeriodType.INSTANT if period.instant else PeriodType.DURATION,
        "period_start": period.start,
        "period_end": period.end,
        "period_instant": period.instant,
        "currency": key.currency,
        "scale": 1,
        "dimensions": key.dimensions.pairs,
    }


def _decimals(occurrence: Occurrence) -> int:
    """Precision relative to the normalized value (scale 1): exact is ``INF_DECIMALS``."""
    if occurrence.precision_kind is PrecisionKind.EXACT:
        return INF_DECIMALS
    if (
        occurrence.precision_kind is PrecisionKind.FINITE
        and occurrence.declared_precision is not None
    ):
        return occurrence.declared_precision - occurrence.raw_scale
    raise BridgeError(f"precision {occurrence.precision_kind} cannot be admitted")


def _location(occurrence: Occurrence) -> dict[str, Any]:
    """The provenance anchor fields: an XBRL context, or the PDF cell's native locator."""
    anchor = occurrence.anchor
    if occurrence.representation is Representation.XBRL:
        return {"anchor_type": SourceAnchorType.XBRL_CONTEXT, "context_ref": anchor["context_ref"]}
    if None in (anchor.get("page"), anchor.get("line"), anchor.get("column_index")):
        raise BridgeError(f"PDF occurrence {occurrence.occurrence_id} lacks its cell locator")
    return {
        "anchor_type": SourceAnchorType.PDF_CELL,
        "page": anchor["page"],
        "row_path": str(anchor["line"]),
        "column_index": anchor["column_index"],
        "table_key": occurrence.anchor_key,
    }
