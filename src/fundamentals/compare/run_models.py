"""Run contracts: request, manifest, inputs and result rows (D1a Task 9; data spec §5–§6).

A run's identity is its request scope, mode, every pinned version with its content hash and
its resolved input set, including negative inputs (design decision 6). It excludes the
cutoff and the code commit, which the manifest records. Per-source values live apart from
outcomes (ledger spec §6 item 4), so a ``ResultRow`` carries them as child records.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from fundamentals.compare.tables import TaggingAdjustment
from fundamentals.compare.vendor_request import VendorComposerContext
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    StatementFamily,
    ValueIdentity,
)
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceState,
    Triage,
)
from fundamentals.contracts.comparison import (
    SourceRef as SourceRef,
)
from fundamentals.contracts.comparison import (
    SourceRole as SourceRole,
)
from fundamentals.contracts.evidence import PinnedVersions, RunMode
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.review_queue import QueueOverlay
from fundamentals.evidence.capture_intake import FirstPartySurface
from fundamentals.evidence.vendor_common import VendorRetainedBinding

NO_DIMENSIONS = "-"
_ROW_ID_SEPARATOR = "|"
_MEMBER_SEPARATOR = ","
_PERIOD_SEPARATOR = ".."
_NAIVE_CUTOFF = "a run cutoff carries its UTC offset"
_ONE_ENTITY = "a D1a run covers exactly one entity, got {count}: run each entity on its own"
_NO_SOURCES = "a run requests at least one first-party source"
_UNKNOWN_SOURCES = "requested sources {unknown} are not first-party surfaces {known}"
FIRST_PARTY_SOURCES = tuple(sorted(surface.value for surface in FirstPartySurface))


class RunStatus(StrEnum):
    """Whether every non-diagnostic source state was decided from available evidence."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class RunExitStatus(IntEnum):
    """Exit codes of ``fundamentals compare run`` (design decision 14; 2 is argparse's)."""

    SUCCESS = 0
    SUCCESS_WITH_OPEN_HIGH = 3
    INCOMPLETE = 4
    FAILURE = 5


class RunInputKind(StrEnum):
    """Which evidence table a run input names (``run_inputs.input_kind``)."""

    CAPTURE_REF = "CAPTURE_REF"
    PACKAGE = "PACKAGE"
    OCCURRENCE = "OCCURRENCE"
    INTERPRETATION = "INTERPRETATION"
    ATTEMPT = "ATTEMPT"
    ALIGNMENT_PROOF = "ALIGNMENT_PROOF"
    CALCULATION_TRACE = "CALCULATION_TRACE"
    EVIDENCE_INPUT = "EVIDENCE_INPUT"
    SETTINGS_RECORD = "SETTINGS_RECORD"
    BASIS_STATUS = "BASIS_STATUS"
    SEGMENT_MEMBER = "SEGMENT_MEMBER"
    PACKAGE_STATEMENT = "PACKAGE_STATEMENT"
    DEFINITION_SET = "DEFINITION_SET"


class RunInputDisposition(StrEnum):
    """What the run did with an input; negative inputs are recorded as well."""

    SELECTED = "SELECTED"
    SURFACED = "SURFACED"
    NOT_SELECTED = "NOT_SELECTED"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"


class RunInput(BaseModel):
    """One evidence row a run read, with what it did with it."""

    model_config = ConfigDict(frozen=True)

    kind: RunInputKind
    ref_id: int
    disposition: RunInputDisposition


class VendorSurfaceRequest(BaseModel):
    """Legacy source/surface declaration, optionally closed into one v2 input request."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    surface: str
    representation: Representation | None = None
    schema_identity: str | None = None
    entity_id: int | None = Field(default=None, gt=0)
    period: PeriodInterval | None = None
    basis: Basis | None = None
    framework: AccountingFramework | None = None
    statement_family: StatementFamily | None = None
    retained: VendorRetainedBinding | None = None
    knowledge_time: datetime | None = None
    knowledge_time_evidence_ref: str | None = None
    capture_ref_id: int | None = Field(default=None, gt=0)
    composer_context: VendorComposerContext | None = None
    expected_logical_scope_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_serializer(mode="wrap")
    def _legacy_document(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        document: dict[str, Any] = handler(self)
        return {key: value for key, value in document.items() if value is not None}

    @field_validator("source_id", "surface")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("vendor source/surface is nonempty")
        return value


class RunScope(BaseModel):
    """What a run covers: one entity, period ends, bases and first-party sources.

    ``sources`` names the first-party surfaces the run reads (sorted, each once); members
    and attempts on any other surface never decide a side. Row ids carry no entity, so a
    run holds exactly one entity (D1a/D1b ruling).
    """

    model_config = ConfigDict(frozen=True)

    entity_ids: tuple[int, ...]
    period_ends: tuple[date, ...]
    bases: tuple[Basis, ...]
    sources: tuple[str, ...]
    vendor_sources: tuple[VendorSurfaceRequest, ...] = ()

    @field_validator("vendor_sources")
    @classmethod
    def _vendor_surfaces(
        cls, value: tuple[VendorSurfaceRequest, ...]
    ) -> tuple[VendorSurfaceRequest, ...]:
        documents = {item.model_dump_json(): item for item in value}
        return tuple(documents[key] for key in sorted(documents))

    @model_serializer(mode="wrap")
    def _legacy_document(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        document: dict[str, Any] = handler(self)
        if not self.vendor_sources:
            document.pop("vendor_sources", None)
        return document

    @field_validator("entity_ids")
    @classmethod
    def _one_entity(cls, entity_ids: tuple[int, ...]) -> tuple[int, ...]:
        """Refuse a scope of other than one entity."""
        if len(entity_ids) != 1:
            raise ValueError(_ONE_ENTITY.format(count=len(entity_ids)))
        return entity_ids

    @field_validator("sources")
    @classmethod
    def _first_party_sources(cls, sources: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse an empty or unknown source; keep them sorted, each once."""
        if not sources:
            raise ValueError(_NO_SOURCES)
        unknown = sorted(set(sources) - set(FIRST_PARTY_SOURCES))
        if unknown:
            raise ValueError(_UNKNOWN_SOURCES.format(unknown=unknown, known=FIRST_PARTY_SOURCES))
        return tuple(sorted(set(sources)))


class DatabaseIdentity(BaseModel):
    """Where a run was stored: host, port and database name, never a credential."""

    model_config = ConfigDict(frozen=True)

    host: str
    port: int
    name: str


class RunRequest(BaseModel):
    """Everything a caller fixes before a run resolves its inputs."""

    model_config = ConfigDict(frozen=True)

    scope: RunScope
    cutoff: datetime
    mode: RunMode
    pinned: PinnedVersions
    code_version: str
    database_identity: DatabaseIdentity

    @field_validator("cutoff")
    @classmethod
    def _aware(cls, cutoff: datetime) -> datetime:
        """Refuse a naive cutoff: knowledge times are compared in UTC."""
        if cutoff.tzinfo is None:
            raise ValueError(_NAIVE_CUTOFF)
        return cutoff


class RunManifest(BaseModel):
    """The request, the sorted resolved inputs, the status and any operational failures."""

    model_config = ConfigDict(frozen=True)

    scope: RunScope
    cutoff: datetime
    mode: RunMode
    pinned: PinnedVersions
    code_version: str
    database_identity: DatabaseIdentity
    inputs: tuple[RunInput, ...]
    status: RunStatus
    operational_failures: tuple[str, ...] = ()

    def identity_hash(self) -> str:
        """SHA-256 of scope, mode, pinned versions and inputs (design decision 6)."""
        payload = {
            "scope": self.scope.model_dump(mode="json"),
            "mode": self.mode.value,
            "pinned": self.pinned.model_dump(mode="json"),
            "inputs": [item.model_dump(mode="json") for item in sorted_inputs(self.inputs)],
        }
        return _sha256(payload)

    def stored_document(self) -> dict[str, object]:
        """The manifest as stored in ``runs.manifest``; inputs live in ``run_inputs``."""
        return self.model_dump(mode="json", exclude={"inputs"})

    def content_sha256(self) -> str:
        """SHA-256 of the whole manifest, inputs included, checked when a run is read back."""
        return _sha256(self.model_dump(mode="json"))


class SourceValue(SourceRef):
    """One source's value for one result row; ``interpretation_id`` and trace id exclusive."""

    model_config = ConfigDict(frozen=True)

    state: SourceState
    reason: str | None
    value: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    interpretation_id: int | None
    calculation_trace_id: int | None
    attempt_id: int | None
    calculation_state: CalculationState | None

    @model_validator(mode="after")
    def _vendor_value_provenance(self) -> SourceValue:
        if self.source_role in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC):
            if self.state is SourceState.VALUE and (
                (self.interpretation_id is None) == (self.calculation_trace_id is None)
            ):
                raise ValueError("vendor VALUE names its selected interpretation or child trace")
        return self


class PairRecord(BaseModel):
    """One stored pair outcome between two source values of the same row."""

    model_config = ConfigDict(frozen=True)

    pair_kind: PairKind
    left: SourceRef
    right: SourceRef
    outcome: PairOutcome
    reason: ReasonCode | None
    triage: Triage | None
    difference: Decimal | None
    interval_gap: Decimal | None
    definition_record_id: str | None
    adjustments: tuple[TaggingAdjustment, ...] = ()


class ResultRow(BaseModel):
    """One cell of a run: its key, applicability, statuses, source values and pairs."""

    model_config = ConfigDict(frozen=True)

    row_id: str
    key: MeasurementKey
    dictionary_version: str
    value_identity: ValueIdentity
    applicability: ApplicabilityStatus
    applicability_rule_id: str
    extraction_status: ExtractionStatus
    extraction_reason: ReasonCode | None
    corroboration_status: CorroborationStatus
    corroboration_reason: ReasonCode | None
    source_values: tuple[SourceValue, ...]
    pairs: tuple[PairRecord, ...]
    surfaced_restatements: tuple[int, ...]

    @field_validator("source_values")
    @classmethod
    def _ordered_sources(cls, values: tuple[SourceValue, ...]) -> tuple[SourceValue, ...]:
        """Canonical order includes source/surface when providers share a representation."""
        return tuple(
            sorted(
                values,
                key=lambda item: (
                    item.source_role.value,
                    item.representation.value,
                    item.source_id or "",
                    item.surface or "",
                ),
            )
        )


class RunRecord(BaseModel):
    """A stored run and whether this call created it."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    manifest: RunManifest
    created: bool
    queue_overlay: QueueOverlay | None = None

    @model_serializer(mode="wrap")
    def _legacy_document(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        document: dict[str, Any] = handler(self)
        if self.queue_overlay is None:
            document.pop("queue_overlay", None)
        return document


def row_id(key: MeasurementKey, value_identity: ValueIdentity) -> str:
    """``canonical_id|period|basis|dimension members|value_identity`` (stable report key)."""
    members = _MEMBER_SEPARATOR.join(f"{axis}={member}" for axis, member in key.dimensions.pairs)
    return _ROW_ID_SEPARATOR.join(
        (
            key.canonical_id,
            period_text(key.period),
            key.basis.value,
            members or NO_DIMENSIONS,
            value_identity.value,
        )
    )


def period_text(period: PeriodInterval) -> str:
    """A period as ``start..end``, or the instant."""
    if period.instant is not None:
        return period.instant.isoformat()
    assert period.start is not None and period.end is not None
    return f"{period.start.isoformat()}{_PERIOD_SEPARATOR}{period.end.isoformat()}"


def sorted_inputs(inputs: tuple[RunInput, ...] | list[RunInput]) -> tuple[RunInput, ...]:
    """Inputs in one canonical order, each (kind, id) once under its strongest disposition.

    One row can be selected for one key and merely considered for another; the stored
    input keeps the strongest use (``run_inputs`` holds one row per evidence id).
    """
    unique: dict[tuple[RunInputKind, int], RunInput] = {}
    for item in inputs:
        held = unique.get((item.kind, item.ref_id))
        if held is None or _STRENGTH[item.disposition] < _STRENGTH[held.disposition]:
            unique[(item.kind, item.ref_id)] = item
    return tuple(unique[key] for key in sorted(unique, key=lambda pair: (pair[0].value, pair[1])))


_STRENGTH = {
    RunInputDisposition.SELECTED: 0,
    RunInputDisposition.SURFACED: 1,
    RunInputDisposition.FAILED_ATTEMPT: 2,
    RunInputDisposition.NOT_SELECTED: 3,
}


def _sha256(payload: object) -> str:
    """SHA-256 of a JSON payload in sorted, compact form."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
