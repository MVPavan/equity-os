"""The versioned comparison policy: the triage magnitude threshold (data spec §5)."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_INVALID_POLICY = "comparison policy {path} is invalid: {detail}"
_NOT_TEXT = "write the threshold as a quoted decimal, not {given!r}: a float is not exact"


class ComparisonPolicyError(ValueError):
    """The comparison policy file is malformed."""


class ComparisonPolicy(BaseModel):
    """Policy pinned by the SHA-256 of its file bytes; the threshold is a fraction, not percent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    content_sha256: str
    magnitude_threshold: Decimal = Field(gt=0, lt=1)

    @field_validator("magnitude_threshold", mode="before")
    @classmethod
    def _quoted_decimal(cls, value: object) -> object:
        """Refuse a float threshold, so binary rounding never sets the boundary."""
        if isinstance(value, float):
            raise ValueError(_NOT_TEXT.format(given=value))
        return value


def load_comparison_policy(path: Path) -> ComparisonPolicy:
    """Load a comparison policy and pin it by content.

    Version drift (a stored run naming this version with other content) is detected where
    the pin is stored, by comparing ``content_sha256`` and raising ``VersionContentDriftError``.
    """
    content = path.read_bytes()
    raw = yaml.safe_load(content)
    try:
        return ComparisonPolicy.model_validate(
            {**raw, "content_sha256": hashlib.sha256(content).hexdigest()}
        )
    except (TypeError, ValidationError) as error:
        raise ComparisonPolicyError(_INVALID_POLICY.format(path=path, detail=error)) from error
