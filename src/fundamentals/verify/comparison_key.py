"""ComparisonKey: the full identity two observations must share before comparison.

Cross-footing or cross-source comparison is only meaningful once the *column* is
proven identical. A currency-only guard is not enough: an SEC USD/annual/IFRS
column can cross-foot perfectly against an Ind AS INR/quarterly column and still
be a category error. The key therefore carries entity, concept, period, scope,
dimensions, accounting basis, currency, unit, and scale — and the comparability
helper explains *why* two observations are or are not comparable, field by field.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)

FIELD_ENTITY = "entity"
FIELD_CONCEPT = "concept"
FIELD_PERIOD = "period"
FIELD_SCOPE = "scope"
FIELD_ACCOUNTING_BASIS = "accounting_basis"
FIELD_CURRENCY = "currency"
FIELD_UNIT = "unit"
FIELD_SCALE = "scale"
FIELD_DIMENSIONS = "dimensions"


class ComparabilityResult(BaseModel):
    """Whether two comparison keys are compatible, with per-field mismatch reasons."""

    model_config = ConfigDict(frozen=True)

    comparable: bool
    reasons: tuple[str, ...] = ()


class ComparisonKey(BaseModel):
    """The full column identity an observation belongs to.

    ``unit`` is the observation's ``normalized_unit`` (presentation unit) and is
    kept distinct from ``scale`` so that, e.g., "INR crore" at scale ``10**7`` is
    never silently compared against "INR million" at scale ``10**6``.
    """

    model_config = ConfigDict(frozen=True)

    entity_scheme: str
    entity_id: str
    concept_qname: str
    period_type: PeriodType
    period_start: date | None = None
    period_end: date | None = None
    period_instant: date | None = None
    scope: Scope
    accounting_basis: AccountingFramework
    currency: str
    unit: str
    scale: int
    dimensions: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_observation(cls, obs: Observation) -> ComparisonKey:
        """Derive the full comparison key from an observation."""
        return cls(
            entity_scheme=obs.entity_scheme,
            entity_id=obs.entity_id,
            concept_qname=obs.concept_qname,
            period_type=obs.period_type,
            period_start=obs.period_start,
            period_end=obs.period_end,
            period_instant=obs.period_instant,
            scope=obs.scope,
            accounting_basis=obs.accounting_basis,
            currency=obs.currency,
            unit=obs.normalized_unit,
            scale=obs.scale,
            dimensions=tuple(sorted(obs.dimensions)),
        )

    def _diffs(self, other: ComparisonKey, *, include_concept: bool) -> tuple[str, ...]:
        """List human-readable mismatch reasons between two keys."""
        reasons: list[str] = []

        def add(label: str, own: object, their: object) -> None:
            if own != their:
                reasons.append(f"{label} mismatch: {own!r} != {their!r}")

        add(
            FIELD_ENTITY,
            (self.entity_scheme, self.entity_id),
            (other.entity_scheme, other.entity_id),
        )
        if include_concept:
            add(FIELD_CONCEPT, self.concept_qname, other.concept_qname)
        add(
            FIELD_PERIOD,
            (self.period_type, self.period_start, self.period_end, self.period_instant),
            (other.period_type, other.period_start, other.period_end, other.period_instant),
        )
        add(FIELD_SCOPE, self.scope, other.scope)
        add(FIELD_ACCOUNTING_BASIS, self.accounting_basis, other.accounting_basis)
        add(FIELD_CURRENCY, self.currency, other.currency)
        add(FIELD_UNIT, self.unit, other.unit)
        add(FIELD_SCALE, self.scale, other.scale)
        add(FIELD_DIMENSIONS, self.dimensions, other.dimensions)
        return tuple(reasons)

    def compatibility(self, other: ComparisonKey) -> ComparabilityResult:
        """Full-key comparability (concept included) for cross-source comparison."""
        reasons = self._diffs(other, include_concept=True)
        return ComparabilityResult(comparable=not reasons, reasons=reasons)

    def footing_compatibility(self, other: ComparisonKey) -> ComparabilityResult:
        """Comparability ignoring concept, for cross-footing distinct line items.

        An accounting identity relates *different* concepts within one column, so
        the concept must differ; every other key field must still match.
        """
        reasons = self._diffs(other, include_concept=False)
        return ComparabilityResult(comparable=not reasons, reasons=reasons)


def explain_comparability(left: Observation, right: Observation) -> ComparabilityResult:
    """Explain whether two observations share a full comparison key, and why not."""
    return ComparisonKey.from_observation(left).compatibility(ComparisonKey.from_observation(right))
