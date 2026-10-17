"""Retention vocabulary shared by SQL, the store and the CLI (plan D9 R2-R6)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RetentionClass(StrEnum):
    """A capture's retention class, as ``eqos.base_class`` assigns it (R2)."""

    VENDOR = "VENDOR"
    IDENTITY = "IDENTITY"
    EXCHANGE_REFETCHABLE = "EXCHANGE_REFETCHABLE"
    COVERED = "COVERED"
    UNCLASSIFIED = "UNCLASSIFIED"


class RefusalCode(StrEnum):
    """The prefix of a retention refusal raised by the database (RP3)."""

    BEYOND_AUTHORITY = "BEYOND_AUTHORITY"


class CaptureState(StrEnum):
    """A capture's retention state (R6); ``RESTORED`` is evaluated like ``RETAINED``."""

    RETAINED = "RETAINED"
    PURGE_PENDING = "PURGE_PENDING"
    EXPIRED = "EXPIRED"
    RESTORED = "RESTORED"


class HoldRoot(StrEnum):
    """A citation-graph root from which a capture is reachable (R4)."""

    REPORT_VERSION = "REPORT_VERSION"
    MEMORY_SUPPORT = "MEMORY_SUPPORT"
    QUEUE_ITEM = "QUEUE_ITEM"
    OPEN_QUEUE_ITEM = "OPEN_QUEUE_ITEM"
    LEGACY_BINDING = "LEGACY_BINDING"
    IDENTITY_EVENT = "IDENTITY_EVENT"
    ONBOARDING_RECORD = "ONBOARDING_RECORD"
    QUALIFICATION_FIXTURE = "QUALIFICATION_FIXTURE"
    MANIFEST_INPUT = "MANIFEST_INPUT"


class EligibilityKind(StrEnum):
    """What purge may do with a capture's bytes (R5)."""

    KEEP = "KEEP"
    HELD = "HELD"
    ELIGIBLE = "ELIGIBLE"


class EligibleReason(StrEnum):
    """Why an eligible capture is eligible (R5)."""

    WINDOW = "WINDOW"
    CATALOG_CEILING = "CATALOG_CEILING"
    LICENCE_END = "LICENCE_END"


class CaptureFacts(BaseModel):
    """Everything eligibility reads about one non-expired capture (R5)."""

    model_config = ConfigDict(frozen=True)

    capture_ref_id: int
    source_id: str
    surface: str
    blob_sha256: str
    base_class: RetentionClass
    covered: bool
    vendor_bounded: bool
    registered_at: datetime
    verified_at: datetime | None
    holds: frozenset[HoldRoot]
    licence_ended_at: datetime | None
    state: CaptureState
    url: str | None


class Eligibility(BaseModel):
    """A capture's eligibility: the holds that keep it, or since when it may be purged."""

    model_config = ConfigDict(frozen=True)

    kind: EligibilityKind
    held_by: frozenset[HoldRoot] = frozenset()
    since: datetime | None = None
    reason: EligibleReason | None = None


class EligibleBlob(BaseModel):
    """A stored blob every one of whose users is eligible, since the latest of them."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    blob_sha256: str
    since: datetime
    capture_ref_ids: tuple[int, ...]
