"""Append-only review items, dispositions and the as-of queue overlay (data spec §5).

Review state is outside immutable run results; recorded times are the store clock's.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.verification.comparison import ReasonCode, SourceRef

UNMAPPED = "UNMAPPED"


class QueueSeverity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DispositionKind(StrEnum):
    ACCEPTED_AS_DEFINITION = "ACCEPTED_AS_DEFINITION"
    MAPPING_FIX = "MAPPING_FIX"
    PARSER_DEFECT = "PARSER_DEFECT"
    FILER_INCONSISTENCY = "FILER_INCONSISTENCY"
    ALTERNATE_READ_REQUIRED = "ALTERNATE_READ_REQUIRED"
    DISMISSED = "DISMISSED"


class QueueItemDraft(BaseModel):
    """A routed issue with its typed evidence; identity, clocks and links belong to the store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: MeasurementKey | None
    pair_identity: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    severity: QueueSeverity
    diagnostic: bool = False
    routing_reason: str = ""
    reason_code: ReasonCode | None = None
    source_refs: tuple[SourceRef, ...] = ()
    attempt_ids: tuple[PositiveInt, ...] = ()
    evidence_interpretation_ids: tuple[PositiveInt, ...] = ()
    evidence_occurrence_ids: tuple[PositiveInt, ...] = ()
    calculation_trace_ids: tuple[PositiveInt, ...] = ()

    @model_validator(mode="after")
    def _evidenced_route(self) -> QueueItemDraft:
        associations = (
            self.attempt_ids,
            self.evidence_interpretation_ids,
            self.evidence_occurrence_ids,
        )
        if self.key is None and (self.outcome != UNMAPPED or not self.evidence_occurrence_ids):
            raise ValueError("only an evidenced UNMAPPED occurrence may lack a measurement key")
        if not any(associations):
            raise ValueError("a queue draft names at least one typed evidence id")
        if any(len(values) != len(set(values)) for values in associations):
            raise ValueError("typed evidence ids are unique within each association kind")
        return self


class QueueItem(BaseModel):
    """A stored item: created by run ``run_id``, linked to the item it replaces, if any."""

    model_config = ConfigDict(frozen=True)

    item_id: int
    run_id: int
    key: MeasurementKey | None
    pair_identity: str
    outcome: str
    input_sha256: str
    severity: QueueSeverity
    diagnostic: bool
    routing_reason: str
    reason_code: ReasonCode | None
    source_refs: tuple[SourceRef, ...]
    predecessor_item_id: int | None
    recorded_at: datetime


class QueueDisposition(BaseModel):
    """A disposition record; it never edits results (data spec §5)."""

    model_config = ConfigDict(frozen=True)

    disposition_id: int
    item_id: int
    kind: DispositionKind
    reason: str
    decider: str
    evidence_ref: str
    explained_amount: Decimal | None
    recorded_at: datetime


class QueueOverlay(BaseModel):
    """One run's queue as of a committed store-clock boundary: open and disposed items and
    the dispositions."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    as_of: datetime
    open_items: tuple[QueueItem, ...]
    dispositions: tuple[QueueDisposition, ...]
    disposed_items: tuple[QueueItem, ...] = ()
