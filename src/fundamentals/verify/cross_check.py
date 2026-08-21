"""Cross-source comparison guarded by the full comparison key.

Two observations are compared numerically only after their comparison keys are
proven compatible — same concept, period, scope, accounting basis, currency,
unit, scale, and dimensions. This is the guard that stops an SEC USD/annual
value from being footed against an Ind AS INR/quarterly value: the keys differ,
so the comparison is rejected with a reason rather than silently performed. Only
when the keys match is a decimals-derived numeric tolerance applied.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation
from fundamentals.verify.comparison_key import ComparisonKey
from fundamentals.verify.crossfoot import observation_half_ulp


class CrossCheckResult(BaseModel):
    """Outcome of comparing two observations across sources.

    ``keys_compatible`` records whether the full comparison keys matched;
    ``matched`` is true only when the keys matched *and* the values agree within
    the derived tolerance. ``reasons`` explains any key or value mismatch.
    """

    model_config = ConfigDict(frozen=True)

    keys_compatible: bool
    matched: bool
    reasons: tuple[str, ...] = ()
    residual: Decimal | None = None
    tolerance: Decimal | None = None


def cross_check(left: Observation, right: Observation) -> CrossCheckResult:
    """Compare two observations only if their full comparison keys are compatible."""
    compatibility = ComparisonKey.from_observation(left).compatibility(
        ComparisonKey.from_observation(right)
    )
    if not compatibility.comparable:
        return CrossCheckResult(
            keys_compatible=False,
            matched=False,
            reasons=compatibility.reasons,
        )

    residual = left.normalized_value - right.normalized_value
    tolerance = observation_half_ulp(left) + observation_half_ulp(right)
    matched = abs(residual) <= tolerance
    reasons = (
        () if matched else (f"value mismatch: residual {residual} exceeds tolerance {tolerance}",)
    )
    return CrossCheckResult(
        keys_compatible=True,
        matched=matched,
        reasons=reasons,
        residual=residual,
        tolerance=tolerance,
    )
