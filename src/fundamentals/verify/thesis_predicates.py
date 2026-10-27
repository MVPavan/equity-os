"""Frozen approved-thesis predicates, their rule and the thesis twin's parser."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class PredicateOp(StrEnum):
    """The complete, versioned set of supported falsifier operators."""

    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    OUTSIDE_BAND = "OUTSIDE_BAND"


class Disposition(StrEnum):
    """The possible outcomes of a deterministic falsifier evaluation."""

    WEAKENED = "WEAKENED"
    HELD = "HELD"
    UNRESOLVED = "UNRESOLVED"


class FalsifierPredicate(BaseModel):
    """A registered comparison over one metric."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    op: PredicateOp
    threshold: Decimal | None = None
    band: tuple[Decimal, Decimal] | None = None

    @model_validator(mode="after")
    def _validate_operands(self) -> FalsifierPredicate:
        """Require a threshold or band only where its operator permits it."""
        if self.op is PredicateOp.OUTSIDE_BAND:
            if self.threshold is not None or self.band is None:
                raise ValueError("OUTSIDE_BAND requires only a band")
            if self.band[0] > self.band[1]:
                raise ValueError("band lower bound must not exceed upper bound")
        elif self.threshold is None or self.band is not None:
            raise ValueError(f"{self.op.value} requires only a threshold")
        return self

    def holds(self, value: Decimal) -> bool:
        """Return whether a sourced metric triggers this registered predicate."""
        if self.op is PredicateOp.LT:
            assert self.threshold is not None
            return value < self.threshold
        if self.op is PredicateOp.LTE:
            assert self.threshold is not None
            return value <= self.threshold
        if self.op is PredicateOp.GT:
            assert self.threshold is not None
            return value > self.threshold
        if self.op is PredicateOp.GTE:
            assert self.threshold is not None
            return value >= self.threshold
        assert self.band is not None
        return value < self.band[0] or value > self.band[1]


class ThesisFalsifier(BaseModel):
    """An analyst-authored statement bound to a deterministic predicate."""

    model_config = ConfigDict(frozen=True)

    falsifier_id: str
    statement: str
    predicate: FalsifierPredicate


class ApprovedThesis(BaseModel):
    """The frozen analyst-approved thesis evaluated against an earnings update."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    version: str
    approved_by: str
    approved_at: date
    stance: str
    assumptions: tuple[str, ...]
    falsifiers: tuple[ThesisFalsifier, ...]
    open_questions: tuple[str, ...]
    content_sha256: str

    @model_validator(mode="after")
    def _validate_falsifier_ids(self) -> ApprovedThesis:
        """Reject ambiguous duplicate falsifier identifiers."""
        ids = tuple(falsifier.falsifier_id for falsifier in self.falsifiers)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate falsifier_id")
        return self


def parse_thesis(content: bytes) -> ApprovedThesis:
    """Parse and hash an analyst-authored thesis YAML twin."""
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise ValueError(f"cannot parse thesis: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("thesis YAML must contain an object")
    data: dict[str, Any] = dict(payload)
    data["content_sha256"] = hashlib.sha256(content).hexdigest()
    return ApprovedThesis.model_validate(data)
