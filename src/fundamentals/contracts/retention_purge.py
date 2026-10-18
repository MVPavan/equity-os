"""Purge, probe and re-fetch vocabulary (plan D9 R8-R10); beside the capped ``retention.py``."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PurgeStep(StrEnum):
    """A purge crash seam: ``checkpoint`` is called just after each (R8)."""

    INTENTS_COMMITTED = "INTENTS_COMMITTED"
    FENCE_WRITTEN = "FENCE_WRITTEN"
    LINK_DELETED = "LINK_DELETED"
    FILES_DELETED = "FILES_DELETED"
    EXPIRED_COMMITTED = "EXPIRED_COMMITTED"
    COMPLETION_WRITTEN = "COMPLETION_WRITTEN"
    BACKUP_WRITTEN = "BACKUP_WRITTEN"
    SET_RENAMED = "SET_RENAMED"


class FetchFailureCategory(StrEnum):
    """Why a re-fetch or probe got no complete body (R10)."""

    INCOMPLETE = "INCOMPLETE"
    HTTP_STATUS = "HTTP_STATUS"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    REFUSED_ADDRESS = "REFUSED_ADDRESS"


class FetchFailure(Exception):  # noqa: N818 - the name plan D9 R10 fixes
    """A fetch that returned no complete body."""

    def __init__(self, category: FetchFailureCategory, http_status: int | None = None) -> None:
        super().__init__(f"fetch failed: {category}" + (f" {http_status}" if http_status else ""))
        self.category = category
        self.http_status = http_status


class RefetchOutcome(StrEnum):
    """What one ``retention refetch`` did (R10)."""

    RESTORED = "RESTORED"
    REFETCH_MISMATCH = "REFETCH_MISMATCH"
    FAILED = "FAILED"
    NOT_REFETCHABLE = "NOT_REFETCHABLE"


class ProbeOutcome(BaseModel):
    """A source's step-1 probe: whether every sampled capture hash-matched, and its last row."""

    model_config = ConfigDict(frozen=True)

    matched: bool
    probe_id: int


class IncompleteKind(StrEnum):
    """Why a stored blob kept its bytes and made the purge incomplete (RP5)."""

    UNREGISTERED = "UNREGISTERED"
    UNKNOWN_LINK = "UNKNOWN_LINK"


class IncompleteBlob(BaseModel):
    """A blob the operator must register or remove before purge completes (RP5)."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    blob_sha256: str
    kind: IncompleteKind


class PurgeReport(BaseModel):
    """What one ``purge`` call did, recovered runs included."""

    model_config = ConfigDict(frozen=True)

    run_id: int
    expired: tuple[int, ...]
    cancelled: tuple[tuple[int, str], ...]
    incomplete: tuple[IncompleteBlob, ...]
    halted_sources: tuple[str, ...]
    backup_id: str | None

    @property
    def high(self) -> bool:
        """Whether the purge leaves an open HIGH incident or an incomplete blob (exit 3)."""
        return bool(self.incomplete or self.halted_sources)


class PurgeRefusedError(Exception):
    """A purge precondition failed before any deletion; nothing was removed."""


class RestoreDelta(BaseModel):
    """What a restore's purge-first added: the captures it expired and the rows per table, so
    restore can check the database changed by exactly that (R12)."""

    model_config = ConfigDict(frozen=True)

    expired: tuple[int, ...]
    rows: dict[str, int]
