"""Local producer observations, independent of capture acquisition claims."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.contracts.snapshot import Sha256, canonical_sha256


class SourceRole(StrEnum):
    XBRL = "xbrl"
    RESULTS_PDF = "results_pdf"
    TRANSCRIPT_PDF = "transcript_pdf"


class SourceRegistrationError(Exception):
    """Trusted local intake refused; no durable success was established."""


def require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise SourceRegistrationError("producer clock must be aware UTC")
    return value


class SourceRegistration(BaseModel):
    """Immutable receipt from the protected producer ledger, never an import API."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[1] = 1
    source_id: str
    surface: str
    request_key: str
    capture_id: str
    source_sha256: Sha256
    record_sha256: Sha256
    role: SourceRole
    capture_completed_at: datetime
    first_observed_at: datetime
    registered_at: datetime
    receipt_sha256: Sha256

    @property
    def binding_id(self) -> str:
        return canonical_sha256(
            {
                key: getattr(self, key)
                for key in ("source_id", "surface", "request_key", "capture_id")
            }
        )

    @model_validator(mode="after")
    def _validate_receipt(self) -> Self:
        clocks = (self.capture_completed_at, self.first_observed_at, self.registered_at)
        for clock in clocks:
            require_utc(clock)
        if not clocks[0] <= clocks[1] <= clocks[2]:
            raise SourceRegistrationError("producer clock moved backward")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise SourceRegistrationError("registration receipt digest mismatch")
        return self
