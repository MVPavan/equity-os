"""Immutable, append-only management-guidance ledger."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.guidance_claim import EpistemicClass, GuidanceClaim
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
    # Older JSON has only entries. New versions retain the full input claims,
    # including qualifiers, so same-quarter conflicts cannot lose information.
    quarter_claims: tuple[GuidanceClaim, ...] | None = None
    # Legacy snapshots have no binding; retain them honestly on replay/migration.
    predecessor_sha256: str | None = None


def _ledger_digest(ledger: ManagementLedger) -> str:
    """Bind a forward output to the complete validated predecessor content."""
    return hashlib.sha256(ledger.model_dump_json().encode("utf-8")).hexdigest()


def _quarter_key(quarter: str) -> tuple[int, int]:
    """Validate the issuer-quarter token before comparing or using it as a filename."""
    match = re.fullmatch(r"FY(\d{2}|\d{4})_Q([1-4])", quarter)
    if match is None:
        raise ValueError(f"invalid issuer quarter {quarter!r}")
    year = int(match[1])
    return year + 2000 if len(match[1]) == 2 else year, int(match[2])


def _replay_matches(ledger: ManagementLedger, claims: dict[str, GuidanceClaim]) -> bool:
    """Check all retained evidence, with a conservative fallback for legacy entries."""
    if ledger.quarter_claims is not None:
        return {_claim_key(claim): claim for claim in ledger.quarter_claims} == claims
    restated = {
        entry.claim_key: entry
        for entry in ledger.entries
        if entry.latest.issuer_quarter == ledger.updated_quarter
    }
    if restated.keys() != claims.keys():
        return False
    for key, claim in claims.items():
        entry = restated[key]
        if (
            claim.qualifiers
            or claim.epistemic_class is not EpistemicClass.FORECAST
            or (entry.lower_bound, entry.upper_bound, entry.unit, entry.constant_currency)
            != (claim.lower_bound, claim.upper_bound, claim.unit, claim.constant_currency)
            or entry.latest != _anchor(claim, ledger.updated_quarter)
        ):
            return False
    return True


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
    quarter_key = _quarter_key(issuer_quarter)
    if prior is not None:
        if prior.symbol != symbol:
            raise ValueError("ledger issuer does not match requested symbol")
        if quarter_key < _quarter_key(prior.updated_quarter):
            raise ValueError("historical replay requires its retained quarter ledger")

    claims_by_key: dict[str, GuidanceClaim] = {}
    for claim in claims:
        key = _claim_key(claim)
        if key in claims_by_key:
            raise ValueError(f"duplicate guidance claim key {key!r}")
        claims_by_key[key] = claim

    if prior is not None and issuer_quarter == prior.updated_quarter:
        if not _replay_matches(prior, claims_by_key):
            raise ValueError("conflicting same-quarter guidance; explicit correction required")
        return prior

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
        quarter_claims=tuple(claims),
        predecessor_sha256=None if prior is None else _ledger_digest(prior),
    )


def _read_ledger(path: Path) -> ManagementLedger | None:
    """Read a validated ledger without resolving the current view."""
    if not path.is_file():
        if path.exists():
            raise OSError(f"ledger path is not a file: {path}")
        return None
    return ManagementLedger.model_validate_json(path.read_text(encoding="utf-8"))


def _snapshot_directory(path: Path) -> Path:
    """Locate the immutable quarter outputs beside the legacy current JSON."""
    return path.with_name(f"{path.stem}.quarters")


def _retained_ledgers(path: Path) -> dict[str, ManagementLedger]:
    """Read snapshots and legacy state, refusing inconsistent retained evidence."""
    ledgers: dict[str, ManagementLedger] = {}
    legacy = _read_ledger(path)
    if legacy is not None:
        _quarter_key(legacy.updated_quarter)
        ledgers[legacy.updated_quarter] = legacy
    for snapshot in _snapshot_directory(path).glob("*.json"):
        _quarter_key(snapshot.stem)
        ledger = _read_ledger(snapshot)
        if ledger is None or ledger.updated_quarter != snapshot.stem:
            raise ValueError(f"ledger snapshot quarter does not match filename: {snapshot}")
        if snapshot.stem in ledgers and ledgers[snapshot.stem] != ledger:
            raise ValueError("conflicting same-quarter ledger evidence")
        ledgers[snapshot.stem] = ledger
    if len({ledger.symbol for ledger in ledgers.values()}) > 1:
        raise ValueError("retained ledgers have conflicting issuers")
    if len({_quarter_key(quarter) for quarter in ledgers}) != len(ledgers):
        raise ValueError("retained ledgers have ambiguous quarter aliases")
    return ledgers


def load_ledger(
    path: Path, *, issuer_quarter: str | None = None, symbol: str | None = None
) -> ManagementLedger | None:
    """Load an exact replay quarter, otherwise its latest available predecessor.

    With no quarter, resolve current authority from retained outputs, even if a
    crash left the derived legacy JSON behind. Legacy-only state can seed forward
    updates, but missing historical quarters fail closed: history is not invented.
    """
    requested = None if issuer_quarter is None else _quarter_key(issuer_quarter)
    ledgers = _retained_ledgers(path)
    if not ledgers:
        return None
    latest = max(ledgers.values(), key=lambda ledger: _quarter_key(ledger.updated_quarter))
    if symbol is not None and latest.symbol != symbol:
        raise ValueError("ledger issuer does not match requested symbol")
    if issuer_quarter in ledgers:
        return ledgers[issuer_quarter]
    if requested is not None and requested <= _quarter_key(latest.updated_quarter):
        raise ValueError("historical replay requires its retained quarter ledger")
    return latest


def _publish_ledger(ledger: ManagementLedger, path: Path, *, immutable: bool) -> None:
    """Publish fully flushed JSON atomically, without clobbering a snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(ledger.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if _read_ledger(path) != ledger:
                    raise ValueError("conflicting same-quarter ledger evidence") from None
        else:
            os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_ledger(ledger: ManagementLedger, path: Path) -> None:
    """Retain an immutable quarter output and advance the derived current JSON.

    On the first save, retain the existing legacy ledger before advancing it.
    Identical saves are no-ops; conflicts require a separate explicit correction
    operation (not provided here). A crash after snapshot publication is repaired
    by a retry. A per-path advisory lock serializes cooperating local writers.
    """
    quarter = _quarter_key(ledger.updated_quarter)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(f".{path.name}.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledgers = _retained_ledgers(path)
        latest = max(
            ledgers.values(), key=lambda item: _quarter_key(item.updated_quarter), default=None
        )
        if latest is not None and latest.symbol != ledger.symbol:
            raise ValueError("ledger issuer does not match requested symbol")
        existing = ledgers.get(ledger.updated_quarter)
        if existing is not None and existing != ledger:
            raise ValueError(
                "conflicting same-quarter ledger evidence; explicit correction required"
            )
        if (
            latest is not None
            and existing is None
            and quarter <= _quarter_key(latest.updated_quarter)
        ):
            raise ValueError("historical replay requires its retained quarter ledger")
        if existing is None:
            expected = None if latest is None else _ledger_digest(latest)
            if ledger.predecessor_sha256 != expected:
                raise ValueError("stale ledger predecessor; reconcile against current authority")
        legacy = _read_ledger(path)
        if legacy is not None:
            snapshot = _snapshot_directory(path) / f"{legacy.updated_quarter}.json"
            if not snapshot.exists():
                _publish_ledger(legacy, snapshot, immutable=True)
        snapshot = _snapshot_directory(path) / f"{ledger.updated_quarter}.json"
        if not snapshot.exists():
            _publish_ledger(ledger, snapshot, immutable=True)
        current = (
            ledger if latest is None or quarter > _quarter_key(latest.updated_quarter) else latest
        )
        if legacy != current:
            _publish_ledger(current, path, immutable=False)
