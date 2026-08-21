"""Fact: a reconciled identity over one or more observations.

Facts are append-only and revision-aware. Multiple observations of the same
underlying measurement (across sources, extractions, or restatements) share a
``revision_family``; canonical selection over that family is a separate,
auditable step recorded in ``canonical_status`` — never a side effect of
writing. Bitemporal timestamps distinguish when a fact *applies* (valid time)
from when the system could first have known it (knowledge / first-seen time).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation


class ReconciliationStatus(StrEnum):
    """Quality/reconciliation state of a fact over its observations."""

    UNRECONCILED = "unreconciled"
    CROSS_FOOT_PASS = "cross_foot_pass"
    CROSS_SOURCE_CONFIRMED = "cross_source_confirmed"
    CONFLICT = "conflict"


class CanonicalStatus(StrEnum):
    """Canonical-selection state within a revision family."""

    CANDIDATE = "candidate"
    CANONICAL = "canonical"
    SUPERSEDED = "superseded"


class Fact(BaseModel):
    """A reconciled, revision-aware fact backed by a canonical observation."""

    model_config = ConfigDict(frozen=True)

    observation: Observation
    reconciliation_status: ReconciliationStatus
    canonical_status: CanonicalStatus
    revision_family: str

    valid_time_start: date
    valid_time_end: date | None = None
    knowledge_time: datetime
    first_seen_time: datetime
