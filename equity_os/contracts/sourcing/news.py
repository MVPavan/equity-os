"""Frozen provenance-first contracts for corporate news and announcements."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class NewsSourceFamily(StrEnum):
    """Authority family of a news occurrence."""

    FIRST_PARTY = "FIRST_PARTY"
    REGULATORY = "REGULATORY"
    MEDIA = "MEDIA"


class NewsEventType(StrEnum):
    """Stable material-event classification used by derived events."""

    RESULTS = "RESULTS"
    BOARD_MEETING = "BOARD_MEETING"
    CORP_ACTION = "CORP_ACTION"
    MATERIAL_EVENT = "MATERIAL_EVENT"
    AGM_EGM = "AGM_EGM"
    INSIDER_SAST = "INSIDER_SAST"
    OTHER = "OTHER"


class NewsSourceHealthKind(StrEnum):
    """Fail-closed source-health conditions surfaced to the caller."""

    EMPTY = "EMPTY"
    STALE = "STALE"
    UNREACHABLE = "UNREACHABLE"
    INVALID = "INVALID"
    NO_HISTORY = "NO_HISTORY"
    ZERO_RESOLVED = "ZERO_RESOLVED"
    SKIPPED = "SKIPPED"
    STORE = "STORE"


class NewsEntity(BaseModel):
    """Configured issuer identity used by the fail-closed matching ladder."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    bse_scrip: str
    isin: str | None
    aliases: tuple[str, ...] = ()

    @property
    def issuer_id(self) -> str:
        """Return the stable ISIN when known, otherwise the canonical NSE identity."""
        return self.isin or f"NSE:{self.symbol.upper()}"


class NewsObservation(BaseModel):
    """One immutable source occurrence with its raw-payload digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str
    issuer_id: str | None
    symbol: str | None
    isin: str | None
    resolved: bool
    identity_note: str | None = None
    source_family: NewsSourceFamily
    source_id: str
    source_url: str
    attachment_url: str | None
    published_at: datetime
    observed_at: datetime
    raw_title: str
    raw_category: str
    raw_subcategory: str
    raw_published_at: str
    raw_attachment_name: str | None
    raw_source_id: str
    parser_version: str
    payload_sha256: str

    @field_validator("published_at", "observed_at")
    @classmethod
    def _timestamp_must_be_aware(cls, value: datetime) -> datetime:
        """Reject ambiguous naive timestamps at the ingestion boundary."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news timestamps must be timezone-aware")
        return value

    @field_validator("payload_sha256", "observation_id")
    @classmethod
    def _digest_must_be_sha256(cls, value: str) -> str:
        """Reject malformed provenance and identity digests."""
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("expected a lowercase sha256 hex digest")
        return value

    @model_validator(mode="after")
    def _resolved_observation_requires_symbol(self) -> NewsObservation:
        """Keep unresolved occurrences detached from every stock."""
        if self.resolved and (not self.symbol or not self.issuer_id):
            raise ValueError("a resolved news observation requires issuer_id and symbol")
        if not self.resolved and (
            self.issuer_id is not None or self.symbol is not None or self.isin is not None
        ):
            raise ValueError("an unresolved news observation cannot carry a stock identity")
        return self


class NewsEvent(BaseModel):
    """A deterministic event derived from one or more retained observations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    event_type: NewsEventType
    symbol: str
    title: str
    published_at: datetime
    observation_ids: tuple[str, ...]
    confirmed: bool

    @field_validator("published_at")
    @classmethod
    def _published_at_must_be_aware(cls, value: datetime) -> datetime:
        """Reject an event without an unambiguous publication time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news timestamps must be timezone-aware")
        return value

    @field_validator("event_id")
    @classmethod
    def _event_id_must_be_sha256(cls, value: str) -> str:
        """Reject malformed stable event identifiers."""
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("expected a lowercase sha256 hex digest")
        return value

    @field_validator("observation_ids")
    @classmethod
    def _observations_must_be_nonempty_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require at least one unique retained source occurrence."""
        if not value:
            raise ValueError("a news event requires an observation")
        if len(set(value)) != len(value):
            raise ValueError("a news event cannot repeat an observation id")
        return value

    @property
    def context_only(self) -> bool:
        """Whether the event has no first-party confirmation."""
        return not self.confirmed


class NewsSourceWarning(BaseModel):
    """A source-health condition that prevents interpreting absence as no news."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    kind: NewsSourceHealthKind
    message: str


class NewsFetchResult(BaseModel):
    """One source pass split into resolved, quarantined, and health outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    observations: tuple[NewsObservation, ...] = ()
    quarantined: tuple[NewsObservation, ...] = ()
    warnings: tuple[NewsSourceWarning, ...] = ()
    raw_count: int = 0
    dropped_count: int = 0


class NewsLaneResult(BaseModel):
    """One CLI collection outcome with derived events and source diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    events: tuple[NewsEvent, ...]
    observations: tuple[NewsObservation, ...]
    quarantined: tuple[NewsObservation, ...]
    warnings: tuple[NewsSourceWarning, ...]
    sources: tuple[NewsFetchResult, ...]


def _stable_digest(payload: object) -> str:
    """Hash a JSON-serializable identity payload deterministically."""
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_news_observation(
    *,
    symbol: str | None,
    isin: str | None,
    issuer_id: str | None,
    resolved: bool,
    source_family: NewsSourceFamily,
    source_id: str,
    source_url: str,
    attachment_url: str | None,
    published_at: datetime,
    observed_at: datetime,
    raw_title: str,
    raw_category: str,
    raw_subcategory: str,
    raw_published_at: str,
    raw_attachment_name: str | None,
    raw_source_id: str,
    parser_version: str,
    payload: bytes,
    identity_note: str | None = None,
) -> NewsObservation:
    """Build an occurrence whose payload and stable identity are sha256-stamped."""
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    observation_id = _stable_digest(
        {
            "raw_source_id": raw_source_id,
            "published_at": published_at.isoformat(),
            "source_id": source_id,
        }
    )
    return NewsObservation(
        observation_id=observation_id,
        issuer_id=issuer_id,
        symbol=symbol.upper() if symbol is not None else None,
        isin=isin.upper() if isin is not None else None,
        resolved=resolved,
        identity_note=identity_note,
        source_family=source_family,
        source_id=source_id,
        source_url=source_url,
        attachment_url=attachment_url,
        published_at=published_at,
        observed_at=observed_at,
        raw_title=raw_title,
        raw_category=raw_category,
        raw_subcategory=raw_subcategory,
        raw_published_at=raw_published_at,
        raw_attachment_name=raw_attachment_name,
        raw_source_id=raw_source_id,
        parser_version=parser_version,
        payload_sha256=payload_sha256,
    )
