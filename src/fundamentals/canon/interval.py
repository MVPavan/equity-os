"""Intervals for canonical values, and the rounding policy used only at storage and display.

Arithmetic stays exact (:class:`Interval`). A stored point value rounds half-even at the
policy's pinned scale for its value kind; stored bounds round outward, so a stored interval
always contains the exact one (data spec §1 Arithmetic).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.interval import ExactValue, Interval, UndefinedDivisionError

__all__ = [
    "ExactValue",
    "Interval",
    "RoundingPolicy",
    "RoundingPolicyError",
    "UndefinedDivisionError",
    "load_rounding_policy",
    "store_bounds",
    "store_value",
]

_INVALID_POLICY = "rounding policy {path} is invalid: {detail}"
_MISSING_KINDS = "no scale for {kinds}"

# Decimal places of the stored unit. Negative scales (rounding to tens) are refused (ruling R1).
Scale = Annotated[int, Field(ge=0)]


class RoundingPolicyError(ValueError):
    """The rounding policy file is malformed or leaves a value kind without a scale."""


class _PolicyFile(BaseModel):
    """The policy file as written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    scale: Mapping[ValueKind, Scale]


class RoundingPolicy(BaseModel):
    """Pinned storage scale (decimal places of the stored unit) per value kind."""

    model_config = ConfigDict(frozen=True)

    policy_id: str
    content_sha256: str
    scale: Mapping[ValueKind, Scale]

    @field_validator("scale", mode="after")
    @classmethod
    def _read_only(cls, scale: Mapping[ValueKind, int]) -> Mapping[ValueKind, int]:
        """Freeze the scales: the policy is pinned by content hash and must not drift under it."""
        return MappingProxyType(dict(scale))


def load_rounding_policy(path: Path) -> RoundingPolicy:
    """Load a rounding policy, pinned by the SHA-256 of its file bytes."""
    content = path.read_bytes()
    try:
        parsed = _PolicyFile.model_validate(yaml.safe_load(content))
    except ValidationError as error:
        raise RoundingPolicyError(_INVALID_POLICY.format(path=path, detail=error)) from error
    missing = sorted(set(ValueKind) - set(parsed.scale))
    if missing:
        detail = _MISSING_KINDS.format(kinds=missing)
        raise RoundingPolicyError(_INVALID_POLICY.format(path=path, detail=detail))
    return RoundingPolicy(
        policy_id=parsed.policy_id,
        content_sha256=hashlib.sha256(content).hexdigest(),
        scale=parsed.scale,
    )


def store_value(value: Fraction, kind: ValueKind, policy: RoundingPolicy) -> Decimal:
    """Round an exact value half-even to the kind's pinned scale."""
    scale = policy.scale[kind]
    # ``round`` on a Fraction is exact and rounds ties to even.
    return _scaled(round(value * 10**scale), scale)


def store_bounds(
    interval: Interval, kind: ValueKind, policy: RoundingPolicy
) -> tuple[Decimal, Decimal]:
    """Round bounds outward to the kind's pinned scale: lower down, upper up."""
    scale = policy.scale[kind]
    factor = 10**scale
    return (
        _scaled(math.floor(interval.lower * factor), scale),
        _scaled(math.ceil(interval.upper * factor), scale),
    )


def _scaled(units: int, scale: int) -> Decimal:
    """An integer count of ``10**-scale`` units as a Decimal with exactly ``scale`` places.

    Built from sign, digits and exponent, so no Decimal context precision ever applies.
    """
    digits = tuple(int(digit) for digit in str(abs(units)))
    return Decimal((1 if units < 0 else 0, digits, -scale))
