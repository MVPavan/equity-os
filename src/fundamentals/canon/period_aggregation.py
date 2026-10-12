"""Period derivation for additive duration amounts: Q4 = FY − 9M, H2 = FY − H1, TTM (spec §1).

Operands share every key part but the period, must line up exactly in time, and must be
revision-compatible: an operand with a differing eligible restatement makes the derivation
``REVISION_INCOMPATIBLE`` (Task 6 decides that from evidence). Instants, per-share values,
ratios, percentages, days and counts are never summed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from enum import StrEnum
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import DictionaryRow, PeriodAggregationKind
from fundamentals.canon.formula import (
    CalculationResult,
    OperandKeyMismatchError,
    OperandValue,
    TraceKind,
    calculation_state,
    check_currency,
    check_output_key,
    conclude,
)
from fundamentals.canon.interval import Interval, RoundingPolicy
from fundamentals.contracts.canonical import PeriodKind, PeriodNature, TemporalRole, ValueKind
from fundamentals.contracts.comparison import CalculationState
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval

_ONE_DAY = timedelta(days=1)
_NON_ADDITIVE = "row {canonical_id!r} ({kind}, {nature}) is not an additive duration amount"
_KEY_MISMATCH = "operand key {given} differs from output {output} in more than the period"
_COUNT = "{derivation} takes {expected} operands, got {got}"
_MISALIGNED = "{derivation}: {detail}"
_NOT_NESTED = "subtrahend {sub} is not nested at the start of {fy} as a {kind}"
_NOT_REMAINDER = "output {output} is not the remainder of {fy} after {sub}"
_NOT_CONTIGUOUS = "quarters {periods} are not four contiguous quarters ending at {output}"


class PeriodDerivation(StrEnum):
    """Which period identity derives the output."""

    Q4_FROM_FY_MINUS_9M = "Q4_FROM_FY_MINUS_9M"
    H2_FROM_FY_MINUS_H1 = "H2_FROM_FY_MINUS_H1"
    TTM_FROM_FOUR_QUARTERS = "TTM_FROM_FOUR_QUARTERS"


# Subtracting derivations: (subtrahend kind, output kind, subtrahend operand name).
_SUBTRACTIONS: Mapping[PeriodDerivation, tuple[PeriodKind, PeriodKind, str]] = {
    PeriodDerivation.Q4_FROM_FY_MINUS_9M: (PeriodKind.NINE_MONTH, PeriodKind.QUARTER, "nine_month"),
    PeriodDerivation.H2_FROM_FY_MINUS_H1: (PeriodKind.HALF_YEAR, PeriodKind.HALF_YEAR, "h1"),
}
_FY = "fy"
_QUARTER_NAMES = ("quarter_1", "quarter_2", "quarter_3", "quarter_4")


class AggregationOperand(BaseModel):
    """A period operand, flagged when it has a differing eligible restatement."""

    model_config = ConfigDict(frozen=True)

    operand: OperandValue
    has_differing_restatement: bool


class NonAdditiveAggregationError(ValueError):
    """The row's values may not be derived across periods."""


class PeriodAlignmentError(ValueError):
    """The operand periods do not line up exactly for the derivation."""


def derive_period_value(
    derivation: PeriodDerivation,
    row: DictionaryRow,
    output: MeasurementKey,
    operands: Sequence[AggregationOperand],
    policy: RoundingPolicy,
) -> CalculationResult:
    """Derive ``output`` from period operands; ``DERIVED``, exact, with a trace.

    Q4 and H2 take ``(FY, subtrahend)``: the subtrahend nested at the FY start and the
    output exactly the remainder. TTM takes four contiguous quarters in order, ending at
    the output end.
    """
    if (
        row.period_aggregation is not PeriodAggregationKind.ADDITIVE_DURATION
        or row.period_nature is not PeriodNature.DURATION
        or row.value_kind is not ValueKind.CURRENCY_AMOUNT
    ):
        raise NonAdditiveAggregationError(
            _NON_ADDITIVE.format(
                canonical_id=row.canonical_id, kind=row.value_kind, nature=row.period_nature
            )
        )
    check_output_key(output, row.canonical_id, row.value_kind)
    values = [operand.operand for operand in operands]
    for value in values:
        check_currency(value.key.canonical_id, value.key, output.currency)
        if value.key.model_copy(update={"period": output.period}) != output:
            raise OperandKeyMismatchError(_KEY_MISMATCH.format(given=value.key, output=output))
    periods = [value.key.period for value in values]
    names = _check_alignment(derivation, output.period, periods)
    state = calculation_state(
        values,
        revision_incompatible=any(operand.has_differing_restatement for operand in operands),
        denominator_contains_zero=False,
    )
    point: tuple[Fraction, Interval] | None = None
    if state is CalculationState.COMPUTED:
        point = _combine(derivation, values)
    entries = [
        (name, TemporalRole.DURATION, value) for name, value in zip(names, values, strict=True)
    ]
    return conclude(
        TraceKind.PERIOD_DERIVATION,
        output,
        entries,
        state,
        point,
        policy,
        formula_id=derivation.value,
    )


def _check_alignment(
    derivation: PeriodDerivation, output: PeriodInterval, periods: Sequence[PeriodInterval]
) -> tuple[str, ...]:
    """Raise :class:`PeriodAlignmentError` unless the periods fit; return the operand names."""
    if derivation is PeriodDerivation.TTM_FROM_FOUR_QUARTERS:
        _expect_count(derivation, periods, len(_QUARTER_NAMES))
        if not _contiguous_quarters(output, periods):
            raise _misaligned(
                derivation, _NOT_CONTIGUOUS.format(periods=list(periods), output=output)
            )
        return _QUARTER_NAMES
    sub_kind, output_kind, sub_name = _SUBTRACTIONS[derivation]
    _expect_count(derivation, periods, 2)
    fy, sub = periods
    if fy.start is None or fy.end is None or sub.start is None or sub.end is None:
        raise _misaligned(derivation, _NOT_NESTED.format(sub=sub, fy=fy, kind=sub_kind))
    fiscal_year_end = fy.end.month
    if (
        fy.kind(fiscal_year_end) is not PeriodKind.YEAR
        or sub.kind(fiscal_year_end) is not sub_kind
        or sub.start != fy.start
        or sub.end >= fy.end
    ):
        raise _misaligned(derivation, _NOT_NESTED.format(sub=sub, fy=fy, kind=sub_kind))
    remainder = PeriodInterval.duration(sub.end + _ONE_DAY, fy.end)
    if output != remainder or output.kind(fiscal_year_end) is not output_kind:
        raise _misaligned(derivation, _NOT_REMAINDER.format(output=output, fy=fy, sub=sub))
    return (_FY, sub_name)


def _contiguous_quarters(output: PeriodInterval, periods: Sequence[PeriodInterval]) -> bool:
    """Four 3-month quarters, each starting the day after the previous ends, spanning ``output``."""
    for period in periods:
        if period.end is None or period.kind(period.end.month) is not PeriodKind.QUARTER:
            return False
    for previous, current in zip(periods, periods[1:], strict=False):
        assert previous.end is not None
        if current.start != previous.end + _ONE_DAY:
            return False
    return output == PeriodInterval.duration(_start(periods[0]), _finish(periods[-1]))


def _combine(
    derivation: PeriodDerivation, values: Sequence[OperandValue]
) -> tuple[Fraction, Interval]:
    """FY minus the subtrahend, or the sum of the quarters, exactly."""
    points = []
    for value in values:
        assert value.exact is not None and value.interval is not None
        points.append((value.exact, value.interval))
    if derivation is PeriodDerivation.TTM_FROM_FOUR_QUARTERS:
        exact, interval = points[0]
        for next_exact, next_interval in points[1:]:
            exact, interval = exact + next_exact, interval.add(next_interval)
        return exact, interval
    (fy_exact, fy_interval), (sub_exact, sub_interval) = points
    return fy_exact - sub_exact, fy_interval.sub(sub_interval)


def _expect_count(
    derivation: PeriodDerivation, periods: Sequence[PeriodInterval], expected: int
) -> None:
    """Refuse the wrong number of operands."""
    if len(periods) != expected:
        detail = _COUNT.format(derivation=derivation, expected=expected, got=len(periods))
        raise PeriodAlignmentError(detail)


def _misaligned(derivation: PeriodDerivation, detail: str) -> PeriodAlignmentError:
    """A :class:`PeriodAlignmentError` naming the derivation."""
    return PeriodAlignmentError(_MISALIGNED.format(derivation=derivation, detail=detail))


def _start(period: PeriodInterval) -> date:
    """First day of a duration."""
    assert period.start is not None
    return period.start


def _finish(period: PeriodInterval) -> date:
    """Last day of a duration."""
    assert period.end is not None
    return period.end
