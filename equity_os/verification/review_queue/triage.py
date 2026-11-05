"""Triage of a ``MISMATCH`` or ``ANOMALY`` difference: structural, magnitude or noise.

Every decision is exact rational arithmetic: Decimal operations round to the context
precision, which could move a difference across the threshold or fake a scale factor.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Final

from equity_os.contracts.verification.comparison import Triage
from equity_os.verification.comparison.policy import ComparisonPolicy
from equity_os.verification.diagnostics.laneb_sensitivity_model import MutationClass

# An exact power-of-ten ratio is a unit fault, named by the parser defect that produces it.
_SCALE_RATIOS: Final[tuple[tuple[int, MutationClass], ...]] = (
    (10, MutationClass.SCALE_10),
    (100, MutationClass.SCALE_100),
    (1000, MutationClass.THOUSANDS_TRUNCATED),
)


def structural_class(left: Decimal, right: Decimal) -> MutationClass | None:
    """Name a sign flip or an exact scale factor of 10, 100 or 1000 between the two values."""
    first, other = Fraction(left), Fraction(right)
    if first != 0 and first == -other:
        return MutationClass.SIGN_FLIP
    if first == 0 or other == 0:
        return None
    larger, smaller = max(abs(first), abs(other)), min(abs(first), abs(other))
    for ratio, mutation in _SCALE_RATIOS:
        if larger == smaller * ratio:
            return mutation
    return None


def triage(left: Decimal, right: Decimal, policy: ComparisonPolicy) -> Triage:
    """``STRUCTURAL`` if a class is named, else ``MAGNITUDE`` when ``|l − r| / max(|l|, |r|)``
    is at or above the threshold, else ``NOISE``."""
    if structural_class(left, right) is not None:
        return Triage.STRUCTURAL
    first, other = Fraction(left), Fraction(right)
    scale = max(abs(first), abs(other))
    if scale != 0 and abs(first - other) / scale >= Fraction(policy.magnitude_threshold):
        return Triage.MAGNITUDE
    return Triage.NOISE
