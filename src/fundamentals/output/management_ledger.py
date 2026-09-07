"""Immutable, append-only management-guidance ledger."""

from __future__ import annotations

import os
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.provenance import Provenance


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


def _claim_key(claim: GuidanceClaim) -> str:
    """Return the stable identity of a guidance commitment."""
    return f"{claim.metric}|{claim.horizon}|{claim.scope}"


def _anchor(claim: GuidanceClaim, issuer_quarter: str) -> LedgerAnchor:
    """Build the ledger's transcript anchor from a quote-verified claim."""
    if claim.source_quote is None:
        raise ValueError(f"guidance claim {claim.metric!r} has no source quote")
    return LedgerAnchor(
        issuer_quarter=issuer_quarter,
        quote=claim.source_quote,
        source=claim.provenance,
    )


def _new_entry(claim: GuidanceClaim, issuer_quarter: str) -> LedgerEntry:
    """Create a first-seen commitment."""
    anchor = _anchor(claim, issuer_quarter)
    return LedgerEntry(
        claim_key=_claim_key(claim),
        metric=claim.metric,
        lower_bound=claim.lower_bound,
        upper_bound=claim.upper_bound,
        unit=claim.unit,
        constant_currency=claim.constant_currency,
        horizon=claim.horizon,
        scope=str(claim.scope),
        first=anchor,
        latest=anchor,
        status=LedgerStatus.NEW,
        history=(),
    )


def reconcile_ledger(
    prior: ManagementLedger | None,
    *,
    symbol: str,
    issuer_quarter: str,
    claims: Sequence[GuidanceClaim],
) -> ManagementLedger:
    """Reconcile this quarter's verified claims against the prior immutable ledger."""
    if prior is not None and issuer_quarter <= prior.updated_quarter:
        raise ValueError("issuer quarter must be later than the saved ledger")

    claims_by_key: dict[str, GuidanceClaim] = {}
    for claim in claims:
        key = _claim_key(claim)
        if key in claims_by_key:
            raise ValueError(f"duplicate guidance claim key {key!r}")
        claims_by_key[key] = claim

    entries: list[LedgerEntry] = []
    if prior is not None:
        for prior_entry in prior.entries:
            if prior_entry.claim_key not in claims_by_key:
                entries.append(
                    prior_entry.model_copy(
                        update={
                            "status": LedgerStatus.CARRIED,
                            "history": (
                                *prior_entry.history,
                                LedgerRevision(
                                    issuer_quarter=issuer_quarter,
                                    lower_bound=prior_entry.lower_bound,
                                    upper_bound=prior_entry.upper_bound,
                                    status=LedgerStatus.CARRIED,
                                ),
                            ),
                        }
                    )
                )
                continue
            claim = claims_by_key.pop(prior_entry.claim_key)

            latest = _anchor(claim, issuer_quarter)
            updates = {
                "lower_bound": claim.lower_bound,
                "upper_bound": claim.upper_bound,
                "unit": claim.unit,
                "constant_currency": claim.constant_currency,
                "latest": latest,
            }
            if (prior_entry.lower_bound, prior_entry.upper_bound, prior_entry.unit) == (
                claim.lower_bound,
                claim.upper_bound,
                claim.unit,
            ):
                entries.append(
                    prior_entry.model_copy(update={**updates, "status": LedgerStatus.REAFFIRMED})
                )
                continue
            entries.append(
                prior_entry.model_copy(
                    update={
                        **updates,
                        "status": LedgerStatus.MODIFIED,
                        "history": (
                            *prior_entry.history,
                            LedgerRevision(
                                issuer_quarter=prior_entry.latest.issuer_quarter,
                                lower_bound=prior_entry.lower_bound,
                                upper_bound=prior_entry.upper_bound,
                                status=prior_entry.status,
                            ),
                        ),
                    }
                )
            )

    entries.extend(
        _new_entry(claim, issuer_quarter) for claim in claims if _claim_key(claim) in claims_by_key
    )
    return ManagementLedger(
        symbol=symbol,
        version=1 if prior is None else prior.version + 1,
        updated_quarter=issuer_quarter,
        entries=tuple(entries),
    )


def load_ledger(path: Path) -> ManagementLedger | None:
    """Load a ledger, treating a missing file as the first tracked quarter."""
    if not path.is_file():
        if path.exists():
            raise OSError(f"ledger path is not a file: {path}")
        return None
    return ManagementLedger.model_validate_json(path.read_text(encoding="utf-8"))


def save_ledger(ledger: ManagementLedger, path: Path) -> None:
    """Atomically replace ``path`` with the supplied ledger JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(ledger.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
