"""Observation: a single measured occurrence of a concept in a source.

An Observation is deliberately richer than a generic ``FinancialFact``: it
carries the identity needed to prove *which* value was read — not inferred from
a plausible label and value. Fact identity collapse — reading a segment, YTD,
prior-year, or standalone value where the current-quarter consolidated value
was intended — is the dominant failure mode this contract guards against.

The XBRL-specific fields (``taxonomy_namespace``, ``registry_version``,
``context_ref``, ``unit_ref``) are *optional*: a PDF-sourced observation has no
XBRL context. What stays mandatory is the core comparison key that makes two
observations of the same thing comparable — concept, period, scope, currency,
scale, dimensions (plus ``accounting_basis`` so an Ind AS value is never footed
against an IFRS/US-GAAP one) — together with the ``provenance`` that binds the
value to its source.
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


class AccountingFramework(StrEnum):
    """Accounting basis a value is reported under.

    Part of the comparison key: cross-source reconciliation must reject a match
    when two observations of the same concept are reported under different
    frameworks (e.g. Ind AS results vs an SEC IFRS filing).
    """

    IND_AS = "IND_AS"
    IFRS = "IFRS"
    US_GAAP = "US_GAAP"
    UNKNOWN = "UNKNOWN"


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
    taxonomy_namespace: str | None = None
    registry_version: str | None = None

    raw_value: str
    normalized_value: Decimal
    normalized_unit: str

    context_ref: str | None = None
    entity_scheme: str
    entity_id: str
    scope: Scope
    accounting_basis: AccountingFramework = AccountingFramework.UNKNOWN

    period_type: PeriodType
    period_start: date | None = None
    period_end: date | None = None
    period_instant: date | None = None

    unit_ref: str | None = None
    currency: str
    scale: int
    decimals: int

    dimensions: tuple[tuple[str, str], ...] = ()

    provenance: Provenance
