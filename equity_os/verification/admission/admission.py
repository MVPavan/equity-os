"""Fact admission by the vendor-first rows, selection and the admitted-fact read (data spec §4;
VENDOR-1 spec §6.5, §6.6, §6.9).

``admit_run`` copies a run's ``REPORTED`` cells into a native fact store by §6.5's rows: an open
non-diagnostic HIGH item or a failed filing refuses first; agreeing vendors give the vendor value
when the filing agrees or, for an eligible check class, when there is no filing; otherwise the
admissible filed value. A run without a vendor-first policy pin has no vendor outcome, so it is
admitted from the filing alone, as before. Admission never selects: selection and the read are
separate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.canonical import Basis, Representation, ValueIdentity
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationOrigin,
    Occurrence,
    PrecisionKind,
    RunMode,
)
from equity_os.contracts.measurement.fact import CanonicalStatus, Fact, ReconciliationStatus
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.measurement.observation import Observation, PeriodType, Scope
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import ExtractionStatus, SourceState
from equity_os.contracts.verification.vendor_first import (
    AdmissionLabel,
    FilingFailure,
    FilingState,
    VendorOutcome,
)
from equity_os.extraction.vendors.tijori.tijori_tables import FINANCIALS_ISLAND_ID
from equity_os.extraction.xbrl.xbrl_parser import INF_DECIMALS
from equity_os.storage.facts.fact_store import FactRef, FactStore, FactStoreLike, StoredRevision
from equity_os.storage.facts.pg_fact_store import PgFactStore, insert_revision, run_serializable
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.eligibility import (
    EligibilityArtifact,
    counterexample_at,
    eligible,
    load_eligibility,
    record_counterexample,
    row_class,
)
from equity_os.verification.admission.vendor_first import (
    filing_admissible,
    filing_state,
    issuer_class,
    vendor_outcome,
)
from equity_os.verification.comparison.report import key_unit
from equity_os.verification.comparison.run import replay_inputs
from equity_os.verification.comparison.run_config import ELIGIBILITY_DIR, YAML_SUFFIX
from equity_os.verification.comparison.run_models import ResultRow, RunManifest
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.comparison.selection import period_end
from equity_os.verification.review_queue.queue import overlay_at
from equity_os.verification.review_queue.trust import open_high

BRIDGE_VERSION = "admission-bridge/2"
ADMITTED_CONCEPT_PREFIX = "eqos:"
CONFIG_DIR = "config"  # as ``compare run``'s default config root
_NAMESPACE = "eqos-dictionary"
_ENTITY_SCHEME = "eqos-reporting-entity"
_FAMILY_PREFIX = "admitted:"
_VENDOR_PAGES = (SCREENER_PAGE, TIJORI_PAGE)
_UNBOUNDED = datetime.max.replace(tzinfo=UTC)

_NOW: LiteralString = "SELECT eqos.store_now() AS now"
_RESULT_ID: LiteralString = (
    "SELECT id FROM eqos.results WHERE run_id = %s AND key_digest = %s AND value_identity = %s"
)
_INSERT: LiteralString = """
INSERT INTO eqos.fact_admissions (store_id, row_handle, fact_origin, fact_origin_id, run_id,
    result_id, interpretation_id, occurrence_id, overlay_position, bridge_version, label,
    witness_interpretation_id, eligibility_version, class_digest)
SELECT target_store, handle, origin, origin_id, %(run_id)s, %(result_id)s,
    %(interpretation_id)s, %(occurrence_id)s, %(position)s, %(bridge)s, %(label)s,
    %(witness)s, %(eligibility)s, %(class_digest)s
FROM eqos.fact_rows WHERE target_store = %(store)s AND handle = %(handle)s
ON CONFLICT (store_id, result_id, interpretation_id) DO NOTHING RETURNING id
"""
_RECORD: LiteralString = """
SELECT a.id AS admission_id, a.row_handle AS handle, a.store_id, a.fact_origin AS origin,
    a.fact_origin_id AS origin_id, a.run_id, a.result_id, a.interpretation_id, a.occurrence_id,
    a.overlay_position, r.key_digest, a.label, a.witness_interpretation_id,
    a.eligibility_version
FROM eqos.fact_admissions a JOIN eqos.results r ON r.id = a.result_id
WHERE a.store_id = %s AND a.result_id = %s AND a.interpretation_id = %s
"""
_HANDLE: LiteralString = (
    "SELECT row_handle FROM eqos.fact_admissions WHERE id = %s AND store_id = %s"
)
# The retention guard reaches only the chosen witness's capture on insert; this is the other's.
_LICENCE_ENDED: LiteralString = """
SELECT l.source_id FROM eqos.interpretations i JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
JOIN eqos.licence_ends l ON l.source_id = c.source_id WHERE i.id = %s
"""
# The latest admission of a selected row by the bound, and whether every witness capture of a
# vendor-valued one is still retained and licensed (§6.9).
_AUTHORISING: LiteralString = """
SELECT a.label, a.class_digest, NOT EXISTS (
        SELECT 1 FROM eqos.interpretations i JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
        WHERE a.witness_interpretation_id IS NOT NULL
            AND i.id IN (a.interpretation_id, a.witness_interpretation_id)
            AND (eqos.capture_state(c.id) NOT IN ('RETAINED', 'RESTORED')
                OR EXISTS (SELECT 1 FROM eqos.licence_ends l WHERE l.source_id = c.source_id))
    ) AS retained
FROM eqos.fact_admissions a
WHERE a.store_id = %s AND a.row_handle = %s AND a.overlay_position <= %s
ORDER BY a.overlay_position DESC, a.id DESC LIMIT 1
"""


class BridgeError(ValueError):
    """An interpretation or occurrence that cannot become an admitted ``Fact``."""


class AdmissionRefusal(StrEnum):
    """Why a run cell was not admitted (§6.5); every non-admitted cell gets exactly one."""

    NOT_REPORTED = "NOT_REPORTED"
    REVIEW_OPEN = "REVIEW_OPEN"
    FILING_UNRESOLVED = "FILING_UNRESOLVED"
    CHECK_REQUIRED = "CHECK_REQUIRED"
    VENDOR_UNMAPPED = "VENDOR_UNMAPPED"
    VENDORS_DISAGREE = "VENDORS_DISAGREE"
    VENDORS_IMPRECISE = "VENDORS_IMPRECISE"


# Rows 4 and 6 of §6.5: the fallback workflow's triggers (§6.8).
TRIGGERS = frozenset(
    {
        AdmissionRefusal.CHECK_REQUIRED,
        AdmissionRefusal.VENDOR_UNMAPPED,
        AdmissionRefusal.VENDORS_DISAGREE,
        AdmissionRefusal.VENDORS_IMPRECISE,
    }
)


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
    key_digest: str
    label: AdmissionLabel
    witness_interpretation_id: int | None
    eligibility_version: str | None


class AdmissionOutcome(BaseModel):
    """One ``admit_run``: every admitted record, every refusal (with each failed filing's
    detail), the fallback triggers per company-period and how many rows it created."""

    model_config = ConfigDict(frozen=True)

    records: tuple[AdmissionRecord, ...]
    refusals: tuple[tuple[str, AdmissionRefusal], ...]
    filing_failures: tuple[tuple[str, FilingFailure], ...]
    triggers: tuple[tuple[int, date, Basis], ...]
    created: int


class SelectedFact(BaseModel):
    """An admitted fact as selected at a cutoff, with its ref, provenance and label."""

    model_config = ConfigDict(frozen=True)

    value: Decimal
    unit: str
    decimals: int
    ref: FactRef
    provenance: Provenance
    selected_at: datetime
    label: AdmissionLabel


class _Cell(BaseModel):
    """A cell's vendor outcome: on agreement, the chosen and witness interpretations, and the
    check class when the issuer has one."""

    model_config = ConfigDict(frozen=True)

    outcome: VendorOutcome
    chosen: int | None = None
    witness: int | None = None
    class_digest: str | None = None


_UNMAPPED = _Cell(outcome=VendorOutcome.VENDOR_UNMAPPED)


def admit_run(
    run_id: int, *, pool: ConnectionPool, store_id: str, config_root: Path = Path(CONFIG_DIR)
) -> AdmissionOutcome:
    """Admit every cell of a stored run that §6.5 admits into ``store_id``, atomically and
    idempotently. Counterexamples are recorded first, in the same transaction.

    The overlay is read at the transaction's own store-clock position, after the queue lock, so
    it is complete and current; no older overlay can authorize an admission. A run pinning the
    vendor-first policy is reloaded under its own pins from ``config_root``.
    """
    runs = RunStore(pool)
    rows, manifest = runs.read_results(run_id), runs.read_manifest(run_id)
    repository = EvidenceRepository(pool)
    interpretations = {
        item.interpretation_id: item
        for item in repository.get_interpretations(
            sorted(
                {
                    value.interpretation_id
                    for row in rows
                    for value in row.source_values
                    if value.state is SourceState.VALUE and value.interpretation_id is not None
                }
            )
        )
    }
    occurrences = {
        item.occurrence_id: item
        for item in repository.get_occurrences(
            sorted({i.occurrence_id for i in interpretations.values() if i.occurrence_id})
        )
    }
    cells: dict[str, _Cell] = {}
    artifact = None
    if manifest.pinned.vendor_first_policy is not None:
        cells, artifact = _vendor_cells(run_id, rows, interpretations, pool, config_root)
    judged = [
        (row, cells.get(row.row_id, _UNMAPPED), filed, filing_state(row, isinstance(filed, tuple)))
        for row in rows
        for filed in (filing_admissible(row, interpretations, occurrences),)
    ]

    def admit(cursor: Cursor[dict[str, Any]]) -> AdmissionOutcome:
        position: datetime = _one(cursor, _NOW, ())["now"]
        overlay = overlay_at(cursor, run_id=run_id, as_of=position)
        for row, cell, _, state in judged:
            if cell.class_digest is not None and state is FilingState.FILING_DIFFERS:
                record_counterexample(
                    cursor, cell.class_digest, _result_id(cursor, run_id, row), run_id
                )
        records: list[AdmissionRecord] = []
        refusals: list[tuple[str, AdmissionRefusal]] = []
        failures: list[tuple[str, FilingFailure]] = []
        triggers: set[tuple[int, date, Basis]] = set()
        created = 0
        for row, cell, filed, state in judged:
            vendor = cell.outcome is VendorOutcome.VENDORS_AGREE and state in (
                FilingState.FILING_AGREES,
                FilingState.FILING_ABSENT,
            )
            refusal = None
            if row.value_identity is not ValueIdentity.REPORTED:
                refusal = AdmissionRefusal.NOT_REPORTED
            elif open_high(overlay, row.key):
                refusal = AdmissionRefusal.REVIEW_OPEN
            elif state is FilingState.FILING_FAILED:
                refusal = AdmissionRefusal.FILING_UNRESOLVED
                # A failed or invalid first-party side fails the filing with no rule failure.
                detail = FilingFailure.EXTRACTION_NOT_AGREE if isinstance(filed, tuple) else filed
                failures.append((row.row_id, detail))
            elif state is FilingState.FILING_ABSENT and not vendor:
                refusal = AdmissionRefusal(cell.outcome)
            elif state is FilingState.FILING_ABSENT and not _unchecked(
                cursor, cell, artifact, manifest, position
            ):
                refusal = AdmissionRefusal.CHECK_REQUIRED
            if refusal is not None:
                refusals.append((row.row_id, refusal))
                if refusal in TRIGGERS:
                    triggers.add((row.key.entity_id, period_end(row.key.period), row.key.basis))
                continue
            witness = None
            if vendor:
                chosen = interpretations[cell.chosen]
                witness = interpretations[cell.witness]
                occurrence = occurrences[chosen.occurrence_id]
                fact = fact_for(
                    chosen,
                    occurrence,
                    row.key,
                    run_id=run_id,
                    reconciliation=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
                    knowledge_time=max(
                        occurrences[item.occurrence_id].capture.registered_at
                        for item in (chosen, witness)
                    ),
                )
            else:
                assert isinstance(filed, tuple)
                chosen, occurrence = filed
                fact = fact_for(
                    chosen,
                    occurrence,
                    row.key,
                    run_id=run_id,
                    reconciliation=ReconciliationStatus.CROSS_SOURCE_CONFIRMED
                    if row.extraction_status is ExtractionStatus.AGREE
                    else ReconciliationStatus.UNRECONCILED,
                )
            unchecked = vendor and state is FilingState.FILING_ABSENT
            result_id = _result_id(cursor, run_id, row)
            eligibility = manifest.pinned.eligibility
            params = {
                "store": store_id,
                "handle": insert_revision(cursor, store_id, fact),
                "run_id": run_id,
                "result_id": result_id,
                "interpretation_id": chosen.interpretation_id,
                "occurrence_id": occurrence.occurrence_id,
                "position": position,
                "bridge": BRIDGE_VERSION,
                "label": AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
                if unchecked
                else AdmissionLabel.CHECKED_AGAINST_FILING,
                "witness": witness and witness.interpretation_id,
                "eligibility": eligibility.version if vendor and eligibility else None,
                "class_digest": cell.class_digest if unchecked else None,
            }
            created += cursor.execute(_INSERT, params).rowcount
            if witness is not None and (
                ended := cursor.execute(_LICENCE_ENDED, (witness.interpretation_id,)).fetchone()
            ):
                raise BridgeError(f"the {ended['source_id']} licence has ended; witness refused")
            stored = _one(cursor, _RECORD, (store_id, result_id, chosen.interpretation_id))
            records.append(AdmissionRecord.model_validate(stored | {"ref": stored}))
        return AdmissionOutcome(
            records=tuple(records),
            refusals=tuple(refusals),
            filing_failures=tuple(failures),
            triggers=tuple(sorted(triggers)),
            created=created,
        )

    return run_serializable(pool, store_id, admit)


def fact_for(
    interpretation: Interpretation,
    occurrence: Occurrence | None,
    key: MeasurementKey,
    *,
    run_id: int,
    reconciliation: ReconciliationStatus,
    knowledge_time: datetime | None = None,
) -> Fact:
    """Bridge a DIRECT interpretation and its occurrence to an admitted ``Fact`` on ``key``.

    A vendor value passes ``knowledge_time`` (its later witness's capture registration); its
    occurrence keeps an unknown knowledge time, and none is invented for it.
    """
    if (
        interpretation.origin is not InterpretationOrigin.DIRECT
        or occurrence is None
        or occurrence.occurrence_id != interpretation.occurrence_id
    ):
        raise BridgeError("only a DIRECT interpretation with its own occurrence is admitted")
    known = occurrence.knowledge_time if knowledge_time is None else knowledge_time
    if interpretation.value is None or occurrence.raw_value_text is None or known is None:
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
        knowledge_time=known.astimezone(UTC),
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
    store: FactStoreLike,
    key: MeasurementKey,
    *,
    cutoff: datetime,
    mode: RunMode,
    pool: ConnectionPool,
) -> SelectedFact | None:
    """The selected admitted fact for ``key``: as known at ``cutoff``, or (retrospective) the
    current selection if its fact was known and first seen by ``cutoff``.

    The label is the latest authorising admission's (by the cutoff when as known). Nothing is
    returned for a vendor value whose witness capture expired or whose licence ended, nor for
    an unchecked one whose class has a counterexample by the cutoff (§6.6, §6.9).
    """
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
    ref = store.fact_ref(revision.row_id)
    bound = cutoff if mode is RunMode.AS_KNOWN else _UNBOUNDED
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        found = cursor.execute(_AUTHORISING, (ref.store_id, revision.row_id, bound)).fetchone()
        if found is None or not found["retained"]:
            return None
        label = AdmissionLabel(found["label"])
        if label is AdmissionLabel.VENDORS_AGREE_NOT_CHECKED and counterexample_at(
            cursor, found["class_digest"], cutoff
        ):
            return None
    observation = revision.fact.observation
    assert revision.canonical_selected_at is not None
    return SelectedFact(
        value=observation.normalized_value,
        unit=observation.normalized_unit,
        decimals=observation.decimals,
        ref=ref,
        provenance=observation.provenance,
        selected_at=revision.canonical_selected_at,
        label=label,
    )


def _vendor_cells(
    run_id: int,
    rows: tuple[ResultRow, ...],
    interpretations: dict[int | None, Interpretation],
    pool: ConnectionPool,
    config_root: Path,
) -> tuple[dict[str, _Cell], EligibilityArtifact | None]:
    """T1 per cell under the run's own pins, with the check class of agreeing cells, and the
    run's pinned eligibility artifact (none unpinned: row 3 is then unreachable)."""
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=config_root)
    policy = config.vendor_first_policy
    assert policy is not None
    (entity_id,) = request.scope.entity_ids
    with pool.connection() as conn:
        issuer = issuer_class(conn, entity_id, request.cutoff)
    cells = {}
    for row in rows:
        outcome, chosen = vendor_outcome(row, interpretations, config.mapping_set, policy)
        if chosen is None:
            cells[row.row_id] = _Cell(outcome=outcome)
            continue
        (witness,) = [
            value.interpretation_id
            for value in row.source_values
            if (value.source_id, value.surface) in _VENDOR_PAGES
            and value.state is SourceState.VALUE
            and value is not chosen
        ]
        cells[row.row_id] = _Cell(
            outcome=outcome,
            chosen=chosen.interpretation_id,
            witness=witness,
            class_digest=None
            if issuer is None
            else row_class(row, interpretations, inputs, request, config, issuer),
        )
    pin = request.pinned.eligibility
    path = config_root / ELIGIBILITY_DIR / f"{pin.version}{YAML_SUFFIX}" if pin else None
    return cells, None if path is None else load_eligibility(path)


def _unchecked(
    cursor: Cursor[dict[str, Any]],
    cell: _Cell,
    artifact: EligibilityArtifact | None,
    manifest: RunManifest,
    position: datetime,
) -> bool:
    """Row 3: the cell's class is eligible at the run's cutoff under its pinned artifact, and no
    counterexample of it is recorded by now (this transaction's included)."""
    digest = cell.class_digest
    return (
        artifact is not None
        and digest is not None
        and eligible(artifact, digest, cutoff=manifest.cutoff, mode=manifest.mode, cursor=cursor)
        and counterexample_at(cursor, digest, position) is None
    )


def _result_id(cursor: Cursor[dict[str, Any]], run_id: int, row: ResultRow) -> int:
    """The stored result id of a run row."""
    identity = (run_id, row.key.digest(), row.value_identity.value)
    return int(_one(cursor, _RESULT_ID, identity)["id"])


def _one(
    cursor: Cursor[dict[str, Any]], query: LiteralString, params: tuple[object, ...]
) -> dict[str, Any]:
    """The single row a query must return."""
    row = cursor.execute(query, params).fetchone()
    assert row is not None
    return row


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
    """The provenance anchor fields: an XBRL context, a vendor's native anchor (Tijori's JSON
    island cell, Screener's HTML table cell) or the PDF cell's native locator."""
    anchor = occurrence.anchor
    if occurrence.representation is Representation.XBRL:
        return {"anchor_type": SourceAnchorType.XBRL_CONTEXT, "context_ref": anchor["context_ref"]}
    kind = anchor.get("anchor_type")
    if kind == SourceAnchorType.JSON_ISLAND:
        fields = {
            "anchor_type": SourceAnchorType.JSON_ISLAND,
            "island_id": FINANCIALS_ISLAND_ID,
            "table_key": anchor.get("table_key"),
            "row_label": anchor.get("row_key"),
            "column_label": anchor.get("column_label"),
        }
    elif kind == SourceAnchorType.HTML_TABLE:
        names = ("table_id", "row_path", "column_index", "column_label")
        fields = {"anchor_type": SourceAnchorType.HTML_TABLE}
        fields |= {name: anchor.get(name) for name in names}
    else:
        if None in (anchor.get("page"), anchor.get("line"), anchor.get("column_index")):
            raise BridgeError(f"PDF occurrence {occurrence.occurrence_id} lacks its cell locator")
        return {
            "anchor_type": SourceAnchorType.PDF_CELL,
            "page": anchor["page"],
            "row_path": str(anchor["line"]),
            "column_index": anchor["column_index"],
            "table_key": occurrence.anchor_key,
        }
    if any(value is None or value == "" for value in fields.values()):
        raise BridgeError(f"{kind} occurrence {occurrence.occurrence_id} lacks an anchor field")
    return fields
