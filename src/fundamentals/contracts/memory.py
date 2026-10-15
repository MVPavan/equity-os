"""Long-term memory contracts: items, their supports and what retrieval returns (ledger spec §2;
plan D4, M1, M5-M7).

Rows are append-only in ``migrations/0016_memory.sql``; the database sets recorded times, so
those appear only on items read back. Status is derived from the decision log (P1).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    GuidanceContract,
    ReportKind,
    VersionStatus,
)


class MemoryKind(StrEnum):
    COMPANY_UNDERSTANDING = "COMPANY_UNDERSTANDING"
    MANAGEMENT_TRACK_RECORD = "MANAGEMENT_TRACK_RECORD"
    THESIS_AND_WARNING = "THESIS_AND_WARNING"
    SOURCE_QUIRK = "SOURCE_QUIRK"
    OWNER_RULING = "OWNER_RULING"
    LESSON = "LESSON"


class MemoryStatus(StrEnum):
    """An item's status, derived from the decision log and never stored (P1)."""

    CANDIDATE = "CANDIDATE"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class SupportTarget(StrEnum):
    """What a support cites; each value is its ``memory_supports`` column."""

    CLAIM = "claim_id"
    VERSION = "version_id"
    DEFINITION_RECORD = "definition_record_id"
    DISPOSITION = "disposition_id"
    DECISION = "decision_id"
    CAPTURE = "capture_ref_id"


class SupportDraft(BaseModel):
    """One support to stage with its item."""

    model_config = ConfigDict(frozen=True)

    target: SupportTarget
    target_id: int


class MemoryItemDraft(BaseModel):
    """An item to stage; ``entity_id`` is ``None`` only for the cross-stock kinds. A correction
    names the item it supersedes."""

    model_config = ConfigDict(frozen=True)

    entity_id: int | None
    kind: MemoryKind
    statement: str
    epistemic_class: EpistemicClass
    valid_from: date
    valid_to: date | None
    supersedes_item_id: int | None
    supports: tuple[SupportDraft, ...]


class SupportRef(BaseModel):
    """A support resolved at a cutoff; fields its target does not carry are ``None`` or empty.
    A version's ``claims`` reach its figures and captures."""

    model_config = ConfigDict(frozen=True)

    target: SupportTarget
    target_id: int
    version_id: int | None = None
    stock: str | None = None
    period: str | None = None
    report_kind: ReportKind | None = None
    version_status: VersionStatus | None = None
    claim_key: str | None = None
    value: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    unit: str | None = None
    qualifiers: tuple[str, ...] = ()
    contract: GuidanceContract | None = None
    citation: Citation | None = None
    blob_sha256: str | None = None
    row: dict[str, Any] | None = None
    claims: tuple[SupportRef, ...] = ()


class RetrievedItem(BaseModel):
    """An item as known at a cutoff: its derived status, revalidation flag and supports."""

    model_config = ConfigDict(frozen=True)

    id: int
    entity_id: int | None
    kind: MemoryKind
    statement: str
    epistemic_class: EpistemicClass
    valid_from: date
    valid_to: date | None
    supersedes_item_id: int | None
    recorded_at: datetime
    status: MemoryStatus
    needs_revalidation: bool
    supports: tuple[SupportRef, ...]
