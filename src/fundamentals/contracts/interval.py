"""Exact rational uncertainty intervals (data spec §5 tolerance and precision).

A shared value type: ``contracts/evidence.py`` and ``canon/`` both carry it, so it imports
nothing above ``contracts/``. Bounds are ``Fraction`` and every operation is exact; rounding
happens only when a value is stored or displayed (``fundamentals.canon.interval``).
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Strict, model_validator

# A rational that refuses floats and strings at construction, so binary rounding never enters.
ExactValue = Annotated[Fraction, Strict()]

_REVERSED = "interval lower bound {lower} is above its upper bound {upper}"
_ZERO_DENOMINATOR = "denominator interval [{lower}, {upper}] contains zero"
_NOT_EXACT = "{factory} takes {accepted}, not {given}: a float is not an exact value"
_HALF = Fraction(1, 2)
_TEN = Fraction(10)


class UndefinedDivisionError(ArithmeticError):
    """The denominator interval contains zero, so the quotient has no bound."""


class Interval(BaseModel):
    """A closed interval ``[lower, upper]`` of exact rationals."""

    model_config = ConfigDict(frozen=True, strict=True)

    lower: Fraction
    upper: Fraction

    @model_validator(mode="after")
    def _ordered(self) -> Interval:
        """Refuse reversed bounds."""
        if self.lower > self.upper:
            raise ValueError(_REVERSED.format(lower=self.lower, upper=self.upper))
        return self

    @classmethod
    def exact(cls, value: Fraction | Decimal) -> Interval:
        """The singleton interval of an exact value (an exact count, an XBRL ``INF`` value)."""
        if not isinstance(value, Fraction | Decimal):
            raise TypeError(
                _NOT_EXACT.format(factory="exact", accepted="Fraction or Decimal", given=value)
            )
        point = Fraction(value)
        return cls(lower=point, upper=point)

    @classmethod
    def from_precision(cls, value: Decimal, decimals: int) -> Interval:
        """Value ± half a unit at ``decimals`` places (negative places are tens, hundreds, …)."""
        if not isinstance(value, Decimal):
            raise TypeError(
                _NOT_EXACT.format(factory="from_precision", accepted="Decimal", given=value)
            )
        point = Fraction(value)
        half_unit = _HALF * _TEN ** (-decimals)
        return cls(lower=point - half_unit, upper=point + half_unit)

    def contains(self, value: Fraction) -> bool:
        """Whether ``value`` lies inside the interval."""
        return self.lower <= value <= self.upper

    def add(self, other: Interval) -> Interval:
        """Sum of two intervals."""
        return Interval(lower=self.lower + other.lower, upper=self.upper + other.upper)

    def sub(self, other: Interval) -> Interval:
        """Difference of two intervals."""
        return Interval(lower=self.lower - other.upper, upper=self.upper - other.lower)

    def mul(self, other: Interval) -> Interval:
        """Product of two intervals: the extremes of the four corner products."""
        corners = [a * b for a in (self.lower, self.upper) for b in (other.lower, other.upper)]
        return Interval(lower=min(corners), upper=max(corners))

    def div(self, other: Interval) -> Interval:
        """Quotient; raises :class:`UndefinedDivisionError` when ``other`` contains zero."""
        if other.contains(Fraction(0)):
            raise UndefinedDivisionError(
                _ZERO_DENOMINATOR.format(lower=other.lower, upper=other.upper)
            )
        return self.mul(Interval(lower=1 / other.upper, upper=1 / other.lower))

    def shift(self, amount: Fraction) -> Interval:
        """Move both bounds by ``amount``."""
        return Interval(lower=self.lower + amount, upper=self.upper + amount)

    def intersects(self, other: Interval) -> bool:
        """Whether the two intervals share at least one point."""
        return self.lower <= other.upper and other.lower <= self.upper

    def gap(self, other: Interval) -> Fraction:
        """Distance between the intervals; zero when they intersect."""
        return max(Fraction(0), other.lower - self.upper, self.lower - other.upper)
