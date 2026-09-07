"""Frozen approved-thesis predicates and their YAML loader."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

PREDICATE_REGISTRY_VERSION = "2026-09-07.1"


class PredicateOp(StrEnum):
    """The complete, versioned set of supported falsifier operators."""

    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    OUTSIDE_BAND = "OUTSIDE_BAND"


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


def load_thesis(path: Path) -> ApprovedThesis:
    """Load and hash an analyst-authored thesis YAML file."""
    try:
        content = path.read_bytes()
        payload = yaml.safe_load(content)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load thesis {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("thesis YAML must contain an object")
    data: dict[str, Any] = dict(payload)
    data["content_sha256"] = hashlib.sha256(content).hexdigest()
    return ApprovedThesis.model_validate(data)
