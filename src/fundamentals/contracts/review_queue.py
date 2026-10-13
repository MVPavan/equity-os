"""Append-only review items, proposals, decisions and named as-of overlays.

Review state is outside immutable run results. Runtime proposals contain no amounts;
final dispositions require a protected, subject/proposal-bound approval receipt.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.comparison import ReasonCode, SourceRef
from fundamentals.contracts.measurement_key import MeasurementKey


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


class ApprovalDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class ApprovalSubject(StrEnum):
    QUEUE_DISPOSITION = "QUEUE_DISPOSITION"
    INTERPRETATION = "INTERPRETATION"


class QueueItem(BaseModel):
    """An exact input/outcome issue; an unmapped occurrence has no invented measurement key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: int | None = None
    run_id: int
    key: MeasurementKey | None
    pair_identity: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    severity: QueueSeverity
    diagnostic: bool = False
    routing_reason: str = ""
    reason_code: ReasonCode | None = None
    source_refs: tuple[SourceRef, ...] = ()
    attempt_ids: tuple[int, ...] = ()
    evidence_interpretation_ids: tuple[int, ...] = ()
    evidence_occurrence_ids: tuple[int, ...] = ()
    predecessor_item_id: int | None = None
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def _occurrence_identity(self) -> QueueItem:
        if self.key is None and (self.outcome != "UNMAPPED" or not self.evidence_occurrence_ids):
            raise ValueError("only an evidenced UNMAPPED occurrence may lack a measurement key")
        return self


class QueueDisposition(BaseModel):
    """A proposed or protected final disposition; recorded time belongs to the store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    disposition_id: int | None = None
    item_id: int
    kind: DispositionKind
    reason: str = Field(min_length=1)
    proposer: str = Field(min_length=1)
    decider: str | None = None
    evidence_ref: str = Field(min_length=1)
    explained_amount: Decimal | None = None
    amount_trace_id: int | None = None
    approval_receipt_id: int | None = None
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def _amount_origin(self) -> QueueDisposition:
        if (
            self.explained_amount is not None
            and self.amount_trace_id is None
            and self.approval_receipt_id is None
        ):
            raise ValueError("an explained amount names its code trace or bound owner receipt")
        return self


class QueueOverlay(BaseModel):
    """Only the named run's queue state through this monotonic store position affects trust."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: int
    recorded_position: int = Field(ge=0)
    as_of: datetime
    open_items: tuple[QueueItem, ...] = ()
    accepted_dispositions: tuple[QueueDisposition, ...] = ()

    @model_validator(mode="after")
    def _named_run(self) -> QueueOverlay:
        if self.as_of.tzinfo is None:
            raise ValueError("queue overlay as-of time is timezone-aware")
        if any(item.run_id != self.run_id for item in self.open_items):
            raise ValueError("queue overlay cannot mix named runs")
        return self


class ApprovalReceipt(BaseModel):
    """Claims as stored by the privileged producer; claims alone are never verified approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt_id: int
    subject_kind: ApprovalSubject
    subject_id: int
    proposal_id: int
    proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    subject_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: ApprovalDecision
    review_evidence_id: int
    review_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decider: str = Field(min_length=1)
    producer_database_identity: str = Field(min_length=1)
    recorded_at: datetime
