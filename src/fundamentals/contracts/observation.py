"""Observation: a single measured occurrence of a concept in a source.

An Observation is deliberately richer than a generic ``FinancialFact``: it
carries the full XBRL identity (concept QName + taxonomy/registry version,
context reference, scope, period, unit, decimals, dimensions) so that fact
identity is *proven*, not inferred from a plausible label and value. Fact
identity collapse — reading a segment, YTD, prior-year, or standalone value
where the current-quarter consolidated value was intended — is the dominant
failure mode this contract guards against.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance


class Scope(StrEnum):
    """Reporting basis: consolidated group vs standalone parent-only."""

    CONSOLIDATED = "consolidated"
    STANDALONE = "standalone"


class PeriodType(StrEnum):
    """Whether the concept is measured over a duration or at an instant."""

    DURATION = "duration"
    INSTANT = "instant"


class Observation(BaseModel):
    """A single context-bound measured value extracted from one source.

    ``dimensions`` holds explicit XBRL axis/member pairs (empty for the
    segment-free primary context); ``raw_value`` is the lexical value exactly as
    it appeared, and ``normalized_value`` is its decimal reading in
    ``normalized_unit`` after applying ``scale``.
    """

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    taxonomy_namespace: str
    registry_version: str

    raw_value: str
    normalized_value: Decimal
    normalized_unit: str

    context_ref: str
    entity_scheme: str
    entity_id: str
    scope: Scope

    period_type: PeriodType
    period_start: date | None = None
    period_end: date | None = None
    period_instant: date | None = None

    unit_ref: str
    currency: str
    scale: int
    decimals: int

    dimensions: tuple[tuple[str, str], ...] = ()

    provenance: Provenance
