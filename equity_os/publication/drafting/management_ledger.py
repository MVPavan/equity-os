"""The management-guidance ledger models an earnings update renders and an import maps."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.guidance_claim import GuidanceClaim
from equity_os.contracts.measurement.provenance import Provenance


class LedgerStatus(StrEnum):
    """How a commitment changed in the ledger's updated quarter."""

    NEW = "NEW"
    REAFFIRMED = "REAFFIRMED"
    MODIFIED = "MODIFIED"
    CARRIED = "CARRIED"


class LedgerAnchor(BaseModel):
    """The transcript evidence for a commitment at one point in time."""

    model_config = ConfigDict(frozen=True)

    issuer_quarter: str
    quote: str
    source: Provenance


class LedgerRevision(BaseModel):
    """A prior range or quarter in which a commitment was not restated."""

    model_config = ConfigDict(frozen=True)

    issuer_quarter: str
    lower_bound: Decimal
    upper_bound: Decimal
    status: LedgerStatus


class LedgerEntry(BaseModel):
    """One management commitment retained across issuer quarters."""

    model_config = ConfigDict(frozen=True)

    claim_key: str
    metric: str
    lower_bound: Decimal
    upper_bound: Decimal
    unit: str
    constant_currency: bool
    horizon: str
    scope: str
    first: LedgerAnchor
    latest: LedgerAnchor
    status: LedgerStatus
    history: tuple[LedgerRevision, ...]


class ManagementLedger(BaseModel):
    """The complete per-symbol management-commitment ledger."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    version: int
    updated_quarter: str
    entries: tuple[LedgerEntry, ...]
    # Older JSON has only entries. New versions retain the full input claims,
    # including qualifiers, so same-quarter conflicts cannot lose information.
    quarter_claims: tuple[GuidanceClaim, ...] | None = None
    # Legacy snapshots have no binding; retain them honestly on replay/migration.
    predecessor_sha256: str | None = None
