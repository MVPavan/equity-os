"""Cross-foot accounting identities over same-footing observations.

Numeric tolerance is *derived* from each observation's XBRL ``decimals`` (a
half unit in the last reported place, rescaled to normalized units), never a
fixed constant. The identity's tolerance is the sum of the participating
half-ULPs, matching how rounding error propagates through addition and
subtraction. A missing required concept fails closed (raises), and observations
that do not share a footing context (period, scope, basis, currency, unit,
scale, dimensions) cannot be footed together.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation
from fundamentals.verify.comparison_key import ComparisonKey

_HALF = Decimal("0.5")
_TEN = Decimal(10)


class MissingRequiredFactError(Exception):
    """An identity references a concept for which no observation was supplied."""


class FootingContextError(Exception):
    """Observations in an identity do not share the same footing context."""


def observation_half_ulp(obs: Observation) -> Decimal:
    """Return the half-ULP tolerance in normalized units for an observation.

    ``decimals`` counts digits of accuracy relative to the raw lexical value; the
    result is rescaled by ``scale`` into the normalized unit the identities work
    in (e.g. ``decimals=-7`` with ``scale=10**7`` yields ``0.5`` crore).
    """
    return _HALF * _TEN ** (-obs.decimals) / Decimal(obs.scale)


class SignedTerm(BaseModel):
    """One right-hand-side term of an accounting identity."""

    model_config = ConfigDict(frozen=True)

    sign: Literal[-1, 1]
    concept_qname: str


class Identity(BaseModel):
    """An accounting identity: ``lhs_concept == sum(sign * term)``."""

    model_config = ConfigDict(frozen=True)

    name: str
    lhs_concept: str
    terms: tuple[SignedTerm, ...]


class CrossFootResult(BaseModel):
    """Pass/fail of one identity with its residual and derived tolerance."""

    model_config = ConfigDict(frozen=True)

    identity: str
    passed: bool
    residual: Decimal
    tolerance: Decimal


def _resolve(concept: str, observations: Mapping[str, Observation]) -> Observation:
    """Return the observation for ``concept`` or fail closed."""
    obs = observations.get(concept)
    if obs is None:
        raise MissingRequiredFactError(
            f"identity requires concept {concept!r} but no observation was provided"
        )
    return obs


def _require_common_footing(observations: Sequence[Observation]) -> None:
    """Raise unless every observation shares the same footing context."""
    base = ComparisonKey.from_observation(observations[0])
    for obs in observations[1:]:
        result = base.footing_compatibility(ComparisonKey.from_observation(obs))
        if not result.comparable:
            raise FootingContextError(
                "cannot cross-foot across differing footing context: " + ", ".join(result.reasons)
            )


def check_identity(identity: Identity, observations: Mapping[str, Observation]) -> CrossFootResult:
    """Check one accounting identity; tolerance is derived from XBRL decimals."""
    lhs = _resolve(identity.lhs_concept, observations)
    involved: list[Observation] = [lhs]
    rhs_total = Decimal(0)
    for term in identity.terms:
        obs = _resolve(term.concept_qname, observations)
        involved.append(obs)
        rhs_total += Decimal(term.sign) * obs.normalized_value

    _require_common_footing(involved)

    residual = lhs.normalized_value - rhs_total
    tolerance = Decimal(0)
    for obs in involved:
        tolerance += observation_half_ulp(obs)

    return CrossFootResult(
        identity=identity.name,
        passed=abs(residual) <= tolerance,
        residual=residual,
        tolerance=tolerance,
    )
