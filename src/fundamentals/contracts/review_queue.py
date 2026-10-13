"""Append-only review items, proposals, decisions and named as-of overlays.

Review state is outside immutable run results. Runtime proposals contain no amounts;
final dispositions require a protected, subject/proposal-bound approval receipt.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

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


class QueueItemDraft(BaseModel):
    """A routing payload whose identity, clocks and predecessor belong to queue SQL."""

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

    @model_validator(mode="after")
    def _evidenced_route(self) -> QueueItemDraft:
        associations = (
            self.attempt_ids,
            self.evidence_interpretation_ids,
            self.evidence_occurrence_ids,
        )
        if self.key is None and (self.outcome != "UNMAPPED" or not self.evidence_occurrence_ids):
            raise ValueError("only an evidenced UNMAPPED occurrence may lack a measurement key")
        if not any(associations):
            raise ValueError("a queue draft names at least one typed evidence id")
        if any(len(values) != len(set(values)) for values in associations):
            raise ValueError("typed evidence ids are unique within each association kind")
        return self


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


class QueueRunMembership(BaseModel):
    """One run's link to an item while preserving the item's creating run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: PositiveInt
    item_id: PositiveInt
    origin_run_id: PositiveInt
    recorded_at: datetime

    @model_validator(mode="after")
    def _store_time(self) -> QueueRunMembership:
        if self.recorded_at.tzinfo is None:
            raise ValueError("queue membership recorded time is timezone-aware")
        return self


class QueueClosureFailure(BaseModel):
    """One sealed disposition candidate that did not pass authenticated receipt replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    disposition_id: PositiveInt
    item_id: PositiveInt
    reason: str = Field(min_length=1)


class QueueOverlay(BaseModel):
    """Only the named run's queue state through this monotonic store position affects trust."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: int
    recorded_position: int = Field(ge=0)
    as_of: datetime
    open_items: tuple[QueueItem, ...] = ()
    accepted_dispositions: tuple[QueueDisposition, ...] = ()
    memberships: tuple[QueueRunMembership, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    closure_failures: tuple[QueueClosureFailure, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )

    @model_validator(mode="after")
    def _named_run(self) -> QueueOverlay:
        if self.as_of.tzinfo is None:
            raise ValueError("queue overlay as-of time is timezone-aware")
        if not self.memberships:
            if self.closure_failures:
                raise ValueError("queue closure failures require sealed run membership")
            if any(item.run_id != self.run_id for item in self.open_items):
                raise ValueError("queue overlay cannot mix named runs")
            return self
        if any(membership.run_id != self.run_id for membership in self.memberships):
            raise ValueError("queue overlay membership belongs to another named run")
        by_item = {membership.item_id: membership for membership in self.memberships}
        if len(by_item) != len(self.memberships):
            raise ValueError("queue overlay has duplicate item memberships")
        visible_item_ids = {
            item.item_id for item in self.open_items if item.item_id is not None
        } | {disposition.item_id for disposition in self.accepted_dispositions}
        if any(item.item_id is None for item in self.open_items) or visible_item_ids != set(
            by_item
        ):
            raise ValueError("queue overlay items and dispositions require exact membership")
        failure_dispositions = {failure.disposition_id for failure in self.closure_failures}
        accepted_dispositions = {
            disposition.disposition_id
            for disposition in self.accepted_dispositions
            if disposition.disposition_id is not None
        }
        if (
            len(failure_dispositions) != len(self.closure_failures)
            or any(failure.item_id not in by_item for failure in self.closure_failures)
            or failure_dispositions & accepted_dispositions
        ):
            raise ValueError("queue closure proof outcomes require exact candidate membership")
        for item in self.open_items:
            assert item.item_id is not None
            membership = by_item[item.item_id]
            if membership.origin_run_id != item.run_id:
                raise ValueError("queue item origin differs from its run membership")
            if item.recorded_at is None or item.recorded_at > self.as_of:
                raise ValueError("queue item is newer than the overlay position")
        if any(membership.recorded_at > self.as_of for membership in self.memberships) or any(
            disposition.recorded_at is None or disposition.recorded_at > self.as_of
            for disposition in self.accepted_dispositions
        ):
            raise ValueError("queue overlay contains state newer than its position")
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
