"""PREP-7 pilot manifest: the real manifest passes, every mutation is refused, and the
retrospective and citation predicates refuse what the contract forbids (Decisions 4 and 6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pilot_manifest_check import (
    PILOT_MUTATIONS,
    admitted,
    check_pilot,
    citations_allowed,
    generic,
    refuses,
)
from test_frozen_manifests import REPO, load

PILOT = REPO / "tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml"
CUTOFF = datetime(2026, 1, 1, 4, 30, tzinfo=UTC)  # 10:00 IST
ENTRY = {"filed_at_nse": "01-Jan-2026 10:00:00", "retrieved_at": "2026-09-06T00:00:00+00:00"}


@pytest.mark.retained
def test_pilot_manifest_passes(path: Path = PILOT) -> None:
    """Every binding holds, including XBRL intervals wider than their PDF cells (PQ0 PAT)."""
    generic(load(path))
    check_pilot(load(path))


@pytest.mark.retained
@pytest.mark.parametrize("name", PILOT_MUTATIONS)
def test_pilot_check_refuses(name: str, path: Path = PILOT) -> None:
    """Each mutation is refused; a binding probe only by its targeted binding."""
    refuses(load(path), name)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({}, None),
        ({"retrieved_at": CUTOFF.isoformat()}, "acquired at or before cutoff"),
        ({"filed_at_nse": "01-Jan-2026 10:00:01"}, "published after cutoff"),
    ],
    ids=["admitted", "acquired-at-cutoff", "published-after-cutoff"],
)
def test_admitted(change: dict[str, str], message: str | None) -> None:
    """A member is admitted only if published by the cutoff and acquired after it."""
    if message is None:
        admitted(ENTRY | change, CUTOFF)
        return
    with pytest.raises(AssertionError, match=message):
        admitted(ENTRY | change, CUTOFF)


def test_citations_allowed() -> None:
    """Own-package and prior-cited captures pass; an earlier package's uncited capture does not."""
    citations_allowed({"own", "prior-quote"}, {"own"}, {"prior-quote"})
    with pytest.raises(AssertionError, match="cited outside the package"):
        citations_allowed({"own", "earlier-package"}, {"own"}, {"prior-quote"})
