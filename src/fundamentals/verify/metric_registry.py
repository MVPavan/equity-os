"""Versioned, deterministic metrics for approved-thesis falsifiers."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.role import FactRole
from fundamentals.output.earnings_update import EarningsUpdate, RenderedFact

METRIC_REGISTRY_VERSION = "2026-09-07.1"
_PERCENT_UNIT = "percent"
_CRORE_UNIT = "INR crore"
_PER_SHARE_UNIT = "INR per share"
_MISSING_ROLE_REASON = "required role is absent from the earnings update"
_ZERO_DENOMINATOR_REASON = "metric denominator is zero"
_DERIVED_QUANTUM = Decimal("0.01")


class MetricKind(StrEnum):
    """The evidence shape a registered metric resolves from."""

    FACT = "FACT"
    COMPARATIVE = "COMPARATIVE"
    DERIVED = "DERIVED"


class MetricDefinition(BaseModel):
    """One metric's pinned evidence definition."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    label: str
    unit: str
    kind: MetricKind
    role: FactRole | None = None
    comparator: ComparatorKind | None = None
    numerator_role: FactRole | None = None
    denominator_role: FactRole | None = None
    scale: Decimal | None = None

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> MetricDefinition:
        """Require exactly the fields used by this metric kind."""
        if self.kind is MetricKind.FACT:
            valid = self.role is not None and all(
                value is None
                for value in (
                    self.comparator,
                    self.numerator_role,
                    self.denominator_role,
                    self.scale,
                )
            )
        elif self.kind is MetricKind.COMPARATIVE:
            valid = (
                self.role is not None
                and self.comparator is not None
                and all(
                    value is None
                    for value in (self.numerator_role, self.denominator_role, self.scale)
                )
            )
        else:
            valid = (
                self.numerator_role is not None
                and self.denominator_role is not None
                and self.scale is not None
                and self.role is None
                and self.comparator is None
            )
        if not valid:
            raise ValueError(f"{self.kind.value} metric has incompatible definition fields")
        return self


class MetricValue(BaseModel):
    """A resolved metric with its deterministic trace and source anchors."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    value: Decimal
    unit: str
    trace: str
    sources: tuple[Provenance, ...]


class MetricUnavailable(BaseModel):
    """A metric that cannot be resolved without fabricating evidence."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    reason: str


REGISTRY: dict[str, MetricDefinition] = {
    "revenue_crore": MetricDefinition(
        metric_id="revenue_crore",
        label="Revenue",
        unit=_CRORE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.REVENUE,
    ),
    "total_income_crore": MetricDefinition(
        metric_id="total_income_crore",
        label="Total income",
        unit=_CRORE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.TOTAL_INCOME,
    ),
    "total_expenses_crore": MetricDefinition(
        metric_id="total_expenses_crore",
        label="Total expenses",
        unit=_CRORE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.TOTAL_EXPENSES,
    ),
    "pbt_crore": MetricDefinition(
        metric_id="pbt_crore",
        label="Profit before tax",
        unit=_CRORE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.PROFIT_BEFORE_TAX,
    ),
    "pat_crore": MetricDefinition(
        metric_id="pat_crore",
        label="Profit after tax",
        unit=_CRORE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.PROFIT_FOR_PERIOD,
    ),
    "eps_basic_inr": MetricDefinition(
        metric_id="eps_basic_inr",
        label="Basic EPS",
        unit=_PER_SHARE_UNIT,
        kind=MetricKind.FACT,
        role=FactRole.BASIC_EPS,
    ),
    "revenue_qoq_pct": MetricDefinition(
        metric_id="revenue_qoq_pct",
        label="Revenue QoQ change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.REVENUE,
        comparator=ComparatorKind.QOQ,
    ),
    "revenue_yoy_pct": MetricDefinition(
        metric_id="revenue_yoy_pct",
        label="Revenue YoY change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.REVENUE,
        comparator=ComparatorKind.YOY,
    ),
    "pbt_qoq_pct": MetricDefinition(
        metric_id="pbt_qoq_pct",
        label="PBT QoQ change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.PROFIT_BEFORE_TAX,
        comparator=ComparatorKind.QOQ,
    ),
    "pbt_yoy_pct": MetricDefinition(
        metric_id="pbt_yoy_pct",
        label="PBT YoY change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.PROFIT_BEFORE_TAX,
        comparator=ComparatorKind.YOY,
    ),
    "pat_qoq_pct": MetricDefinition(
        metric_id="pat_qoq_pct",
        label="PAT QoQ change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.PROFIT_FOR_PERIOD,
        comparator=ComparatorKind.QOQ,
    ),
    "pat_yoy_pct": MetricDefinition(
        metric_id="pat_yoy_pct",
        label="PAT YoY change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.PROFIT_FOR_PERIOD,
        comparator=ComparatorKind.YOY,
    ),
    "eps_yoy_pct": MetricDefinition(
        metric_id="eps_yoy_pct",
        label="EPS YoY change",
        unit=_PERCENT_UNIT,
        kind=MetricKind.COMPARATIVE,
        role=FactRole.BASIC_EPS,
        comparator=ComparatorKind.YOY,
    ),
    "pbt_margin_pct": MetricDefinition(
        metric_id="pbt_margin_pct",
        label="PBT margin",
        unit=_PERCENT_UNIT,
        kind=MetricKind.DERIVED,
        numerator_role=FactRole.PROFIT_BEFORE_TAX,
        denominator_role=FactRole.REVENUE,
        scale=Decimal("100"),
    ),
    "pat_margin_pct": MetricDefinition(
        metric_id="pat_margin_pct",
        label="PAT margin",
        unit=_PERCENT_UNIT,
        kind=MetricKind.DERIVED,
        numerator_role=FactRole.PROFIT_FOR_PERIOD,
        denominator_role=FactRole.REVENUE,
        scale=Decimal("100"),
    ),
    "effective_tax_rate_pct": MetricDefinition(
        metric_id="effective_tax_rate_pct",
        label="Effective tax rate",
        unit=_PERCENT_UNIT,
        kind=MetricKind.DERIVED,
        numerator_role=FactRole.PROFIT_BEFORE_TAX,
        denominator_role=FactRole.PROFIT_BEFORE_TAX,
        scale=Decimal("100"),
    ),
}


def _fact_for_role(update: EarningsUpdate, role: FactRole) -> RenderedFact | None:
    """Find the rendered fact carrying one registered role."""
    return next((fact for fact in update.facts if fact.role is role), None)


def _resolve_fact(
    update: EarningsUpdate, definition: MetricDefinition
) -> MetricValue | MetricUnavailable:
    """Resolve a direct role-backed metric."""
    assert definition.role is not None
    fact = _fact_for_role(update, definition.role)
    if fact is None:
        return MetricUnavailable(metric_id=definition.metric_id, reason=_MISSING_ROLE_REASON)
    return MetricValue(
        metric_id=definition.metric_id,
        value=fact.value,
        unit=definition.unit,
        trace=f"{definition.label}: {fact.value} {definition.unit}",
        sources=fact.sources,
    )


def _resolve_comparative(
    update: EarningsUpdate, definition: MetricDefinition
) -> MetricValue | MetricUnavailable:
    """Resolve a role's audited QoQ or YoY percentage trace."""
    assert definition.role is not None
    assert definition.comparator is not None
    fact = _fact_for_role(update, definition.role)
    if fact is None:
        return MetricUnavailable(metric_id=definition.metric_id, reason=_MISSING_ROLE_REASON)
    comparative = next(
        (
            candidate
            for candidate in update.comparatives
            if candidate.concept_qname == fact.concept_qname
        ),
        None,
    )
    if comparative is None:
        return MetricUnavailable(
            metric_id=definition.metric_id,
            reason="no comparative was retained for the registered concept",
        )
    change = comparative.qoq if definition.comparator is ComparatorKind.QOQ else comparative.yoy
    if not change.available or change.percent_change is None or change.percent_trace is None:
        return MetricUnavailable(
            metric_id=definition.metric_id,
            reason=change.unavailable_reason
            or change.percent_unavailable_reason
            or "percent unavailable",
        )
    sources = (
        *comparative.current_sources,
        *((change.prior_source,) if change.prior_source else ()),
    )
    return MetricValue(
        metric_id=definition.metric_id,
        value=change.percent_change,
        unit=definition.unit,
        trace=change.percent_trace,
        sources=sources,
    )


def _resolve_derived(
    update: EarningsUpdate, definition: MetricDefinition
) -> MetricValue | MetricUnavailable:
    """Resolve a ratio over two sourced facts."""
    assert definition.numerator_role is not None
    assert definition.denominator_role is not None
    assert definition.scale is not None
    numerator = _fact_for_role(update, definition.numerator_role)
    denominator = _fact_for_role(update, definition.denominator_role)
    if numerator is None or denominator is None:
        return MetricUnavailable(metric_id=definition.metric_id, reason=_MISSING_ROLE_REASON)
    if denominator.value == 0:
        return MetricUnavailable(metric_id=definition.metric_id, reason=_ZERO_DENOMINATOR_REASON)
    numerator_value = numerator.value
    if definition.metric_id == "effective_tax_rate_pct":
        pat = _fact_for_role(update, FactRole.PROFIT_FOR_PERIOD)
        if pat is None:
            return MetricUnavailable(metric_id=definition.metric_id, reason=_MISSING_ROLE_REASON)
        numerator_value = numerator.value - pat.value
        sources = (*numerator.sources, *pat.sources)
        trace = f"({numerator.value} - {pat.value}) / {denominator.value} * {definition.scale}"
    else:
        sources = (*numerator.sources, *denominator.sources)
        trace = f"{numerator.value} / {denominator.value} * {definition.scale}"
    return MetricValue(
        metric_id=definition.metric_id,
        value=(numerator_value / denominator.value * definition.scale).quantize(_DERIVED_QUANTUM),
        unit=definition.unit,
        trace=trace,
        sources=sources,
    )


def resolve_metric(update: EarningsUpdate, metric_id: str) -> MetricValue | MetricUnavailable:
    """Resolve one registered metric or return its explicit failure reason."""
    definition = REGISTRY.get(metric_id)
    if definition is None:
        return MetricUnavailable(metric_id=metric_id, reason="unregistered metric")
    if definition.kind is MetricKind.FACT:
        return _resolve_fact(update, definition)
    if definition.kind is MetricKind.COMPARATIVE:
        return _resolve_comparative(update, definition)
    return _resolve_derived(update, definition)
