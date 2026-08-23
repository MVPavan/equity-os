"""Period-keyed held-file paths and fail-closed comparator quarantine."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import NamedTuple

import structlog

from fundamentals.contracts.comparative import ComparatorKind

RAW_WATCHLIST_DIR = Path("data/raw/watchlist")
MULTIPLE_DISTINCT_FILINGS_REASON = (
    "multiple distinct cached filings for this period; adjudicate manually"
)

_LOGGER = structlog.get_logger(__name__)


class CachedComparatorSelection(NamedTuple):
    """One unambiguous cached path, or the reason selection failed closed."""

    path: Path | None
    unavailable_reason: str | None


def comparator_period_key(period_start: date, period_end: date) -> str:
    """Return the stable directory key for one exact comparator period."""
    return f"{period_start.isoformat()}_{period_end.isoformat()}"


def comparator_cache_root(repo_root: Path, symbol: str) -> Path:
    """Return the only selectable comparator-cache root for an issuer."""
    return repo_root / RAW_WATCHLIST_DIR / symbol.lower() / "nse" / "comparatives"


def comparator_period_dir(
    repo_root: Path,
    symbol: str,
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
) -> Path:
    """Return the cache directory for one kind and exact derived period."""
    return (
        comparator_cache_root(repo_root, symbol)
        / kind.value.lower()
        / comparator_period_key(period_start, period_end)
    )


def cached_comparator_path(
    repo_root: Path,
    symbol: str,
    kind: ComparatorKind,
    period_start: date,
    period_end: date,
) -> CachedComparatorSelection:
    """Select one content-unambiguous XML from the exact period directory."""
    period_dir = comparator_period_dir(repo_root, symbol, kind, period_start, period_end)
    if not period_dir.is_dir():
        return CachedComparatorSelection(None, None)
    candidates = tuple(sorted(period_dir.glob("*.xml")))
    if not candidates:
        return CachedComparatorSelection(None, None)
    try:
        digests = {hashlib.sha256(candidate.read_bytes()).digest() for candidate in candidates}
    except OSError as error:
        return CachedComparatorSelection(None, f"cached comparator inspection failed: {error}")
    if len(digests) != 1:
        return CachedComparatorSelection(None, MULTIPLE_DISTINCT_FILINGS_REASON)
    return CachedComparatorSelection(candidates[0], None)


def quarantine_rejected_comparator(
    path: Path,
    *,
    repo_root: Path,
    symbol: str,
    xml: bytes,
    reason: str,
) -> bool:
    """Move rejected comparator evidence outside selection without ever deleting it."""
    cache_root = comparator_cache_root(repo_root, symbol).resolve()
    candidate = path.resolve()
    if not candidate.is_relative_to(cache_root) or not candidate.is_file():
        _LOGGER.warning(
            "comparator_quarantine_refused",
            path=str(candidate),
            cache_root=str(cache_root),
            reason=reason,
        )
        return False

    rejected = candidate.parent / "rejected"
    digest = hashlib.sha256(xml).hexdigest()[:12]
    target = rejected / f"{candidate.stem}-{digest}{candidate.suffix}"
    suffix = 1
    while target.exists():
        target = rejected / f"{candidate.stem}-{digest}-{suffix}{candidate.suffix}"
        suffix += 1
    try:
        rejected.mkdir(parents=True, exist_ok=True)
        candidate.rename(target)
    except OSError as error:
        _LOGGER.error(
            "comparator_quarantine_failed",
            path=str(candidate),
            cache_root=str(cache_root),
            reason=reason,
            error=str(error),
        )
        return False
    _LOGGER.warning(
        "comparator_quarantined",
        path=str(candidate),
        quarantine_path=str(target),
        reason=reason,
    )
    return True
