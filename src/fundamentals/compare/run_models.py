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

from pydantic import BaseModel, ConfigDict, field_validator

from fundamentals.compare.tables import TaggingAdjustment
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
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
from fundamentals.contracts.evidence import PinnedVersions, RunMode
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval

NO_DIMENSIONS = "-"
_ROW_ID_SEPARATOR = "|"
_MEMBER_SEPARATOR = ","
_PERIOD_SEPARATOR = ".."
_NAIVE_CUTOFF = "a run cutoff carries its UTC offset"


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


class SourceRole(StrEnum):
    """Which side a stored source value plays in its result row."""

    FIRST_PARTY = "FIRST_PARTY"
    # A reported value copied onto a derived row so its REPORTED_VS_DERIVED pair can name it.
    REPORTED_COUNTERPART = "REPORTED_COUNTERPART"


class RunInput(BaseModel):
    """One evidence row a run read, with what it did with it."""

    model_config = ConfigDict(frozen=True)

    kind: RunInputKind
    ref_id: int
    disposition: RunInputDisposition


class RunScope(BaseModel):
    """What a run covers: entities, period ends, bases and first-party sources."""

    model_config = ConfigDict(frozen=True)

    entity_ids: tuple[int, ...]
    period_ends: tuple[date, ...]
    bases: tuple[Basis, ...]
    sources: tuple[str, ...]


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


class SourceValue(BaseModel):
    """One source's value for one result row; ``interpretation_id`` and trace id exclusive."""

    model_config = ConfigDict(frozen=True)

    source_role: SourceRole
    representation: Representation
    state: SourceState
    reason: str | None
    value: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    interpretation_id: int | None
    calculation_trace_id: int | None
    attempt_id: int | None
    calculation_state: CalculationState | None


class SourceRef(BaseModel):
    """Which source value of the same row one side of a pair is."""

    model_config = ConfigDict(frozen=True)

    source_role: SourceRole
    representation: Representation


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


class RunRecord(BaseModel):
    """A stored run and whether this call created it."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    manifest: RunManifest
    created: bool


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
