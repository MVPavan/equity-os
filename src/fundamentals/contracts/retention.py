"""Retention vocabulary shared by SQL, the store and the CLI (plan D9 R2-R6)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.snapshot import SnapshotError


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
    ORIGINAL_EXPIRED = "ORIGINAL_EXPIRED"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    PURGE_PENDING = "PURGE_PENDING"


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


class OriginalExpiredError(Exception):
    """A capture's original is expired or being purged: its bytes are gone by policy (RP7)."""


class LicenceEndedError(SnapshotError):
    """The store refuses a source whose licence has ended (RP4a)."""


class JournalEventKind(StrEnum):
    """An expiry-journal event (R11)."""

    FENCE = "FENCE"
    COMPLETE = "COMPLETE"


class FencedCapture(BaseModel):
    """One intent capture as a ``FENCE`` event records it (R11)."""

    model_config = ConfigDict(frozen=True)

    capture_ref_id: int
    source_id: str
    surface: str
    request_key: str
    capture_id: str
    blob_sha256: str
    record_sha256: str
    url: str | None


class JournalEvent(BaseModel):
    """An append-only expiry-journal event; ``id`` is the previous event's plus one (R11)."""

    model_config = ConfigDict(frozen=True)

    id: int = 0
    kind: JournalEventKind
    run_id: int
    captures: tuple[FencedCapture, ...] = ()
    expired: tuple[int, ...] = ()
    cancelled: tuple[int, ...] = ()
    purged_at: datetime | None = None


class LicenceEnd(BaseModel):
    """A vendor licence end as the authority file records it (R11)."""

    model_config = ConfigDict(frozen=True)

    id: int = 0
    source_id: str
    ended_on: date
    reason: str
    recorded_at: datetime


class BlobDeletion(StrEnum):
    """What ``SnapshotStore.delete_blob`` did (RP5)."""

    DELETED = "DELETED"
    UNKNOWN_LINK = "UNKNOWN_LINK"


class BlobEntry(BaseModel):
    """One stored blob and its hard-link count (RP5)."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    blob_sha256: str
    links: int
