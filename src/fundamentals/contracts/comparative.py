"""Frozen contracts for sourced quarter-over-quarter and year-over-year changes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.provenance import Provenance

# IEEE 754 decimal128 precision bounds comparator arithmetic and presentation
# without depending on the process-global Decimal context.
PERCENT_CONTEXT_PRECISION = 34


class ComparatorKind(StrEnum):
    """The two prior filing periods used for earnings comparatives."""

    QOQ = "QoQ"
    YOY = "YoY"


class ComparativeChange(BaseModel):
    """One sourced prior value and its deterministic change from the current value."""

    model_config = ConfigDict(frozen=True)

    kind: ComparatorKind
    period_start: date
    period_end: date
    prior_value: Decimal | None = None
    absolute_change: Decimal | None = None
    percent_change: Decimal | None = None
    absolute_trace: str | None = None
    percent_trace: str | None = None
    prior_source: Provenance | None = None
    unavailable_reason: str | None = None
    percent_unavailable_reason: str | None = None

    @model_validator(mode="after")
    def _validate_availability(self) -> ComparativeChange:
        """Reject partially sourced or partially calculated comparator states."""
        if self.prior_value is None:
            if self.unavailable_reason is None:
                raise ValueError("an unavailable comparator requires a reason")
            if any(
                value is not None
                for value in (
                    self.absolute_change,
                    self.percent_change,
                    self.absolute_trace,
                    self.percent_trace,
                    self.prior_source,
                    self.percent_unavailable_reason,
                )
            ):
                raise ValueError("an unavailable comparator cannot carry sourced calculations")
            return self

        if self.unavailable_reason is not None:
            raise ValueError("an available comparator cannot carry an unavailable reason")
        if self.absolute_change is None or self.absolute_trace is None or self.prior_source is None:
            raise ValueError("an available comparator requires a source and absolute-change trace")
        if self.prior_value == 0 and self.percent_change is not None:
            raise ValueError("a zero prior value cannot carry a percent change")
        if self.percent_change is None:
            if self.percent_trace is not None or self.percent_unavailable_reason is None:
                raise ValueError("an unavailable percent requires only an explicit reason")
        elif self.percent_trace is None or self.percent_unavailable_reason is not None:
            raise ValueError("an available percent requires its trace and no unavailable reason")
        return self

    @property
    def available(self) -> bool:
        """Whether a sourced comparator value was available and calculated."""
        return self.prior_value is not None


class ConceptComparative(BaseModel):
    """Current material concept plus its QoQ and YoY sourced comparisons."""

    model_config = ConfigDict(frozen=True)

    concept_qname: str
    current_value: Decimal | None = None
    unit: str | None = None
    current_sources: tuple[Provenance, ...] = ()
    current_unavailable_reason: str | None = None
    qoq: ComparativeChange
    yoy: ComparativeChange

    @model_validator(mode="after")
    def _validate_current_endpoint(self) -> ConceptComparative:
        """Require current values to be provenance-bound or explicitly unavailable."""
        if self.qoq.kind is not ComparatorKind.QOQ or self.yoy.kind is not ComparatorKind.YOY:
            raise ValueError("concept comparatives require one QoQ and one YoY result")
        if self.current_value is None:
            if (
                self.current_sources
                or self.unit is not None
                or self.current_unavailable_reason is None
            ):
                raise ValueError("an unavailable current value requires only an explicit reason")
        elif (
            not self.current_sources
            or self.unit is None
            or self.current_unavailable_reason is not None
        ):
            raise ValueError("a current value requires its unit and at least one source anchor")
        return self
