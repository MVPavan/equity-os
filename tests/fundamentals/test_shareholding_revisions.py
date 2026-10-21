"""D8 closing review C1 and C2: an ingest refuses an instant its filing is not listed at, and a
revision's predecessor is the latest earlier broadcast whatever order the submissions arrive in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pg_support import PgTestDatabase
from test_shareholding_filing import (
    INSTANT,
    INSTANT4,
    _counts,
    _Edit,
    _ingest,
    _marked,
    _seed,
)
from test_shareholding_filing import guarded as guarded  # the fixture, re-exported

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import SHP_LISTING, SHP_XBRL
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ingest.shareholding_filing import listing_date

APAR = "APARINDS"
# Broadcast days of the original, intermediate and newer submission; ingested out of order.
ORIGINAL, INTERMEDIATE, NEWER = "14-JUL-2026", "16-JUL-2026", "18-JUL-2026"


def _submission(day: str) -> _Edit:
    """The gen-2 instance re-broadcast on ``day`` with distinct bytes (a revised submission)."""

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        by_pair = {(e["source_id"], e["surface"]): folder / e["filename"] for e in entries}
        rows = json.loads(by_pair[SHP_LISTING].read_bytes())
        for row in rows:
            if listing_date(row["date"]) == INSTANT:
                row["broadcastDate"] = f"{day} {row['broadcastDate'].split(' ', 1)[1]}"
        by_pair[SHP_LISTING].write_text(json.dumps(rows))
        filing = by_pair[SHP_XBRL]
        filing.write_bytes(filing.read_bytes() + f"<!-- revision {day} -->".encode())

    return edit


@pytest.mark.pg
@pytest.mark.retained
def test_an_instant_the_filing_is_not_listed_at_is_refused(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """C1: ``--instant`` names an earlier pilot quarter (gen-4's) than gen-2's filing; the ingest
    exits non-zero and stores no attempt, occurrence, interpretation or package at either."""
    entity_id = _seed(guarded, APAR)
    assert _ingest(_marked(tmp_path, APAR, lambda *_: None), tmp_path / "s", APAR, INSTANT4) != 0
    with guarded.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        assert [repository.list_attempts(entity_id, day) for day in (INSTANT, INSTANT4)] == [(), ()]
    counts = _counts(guarded)
    assert counts["occurrences"] == counts["interpretations"] == counts["filing_packages"] == 0


@pytest.mark.pg
@pytest.mark.retained
def test_a_late_imported_original_does_not_reroute_the_lineage(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """C2: intermediate, original, then newer revision are ingested; the newer supersedes the
    intermediate (the latest earlier broadcast), and re-ingesting the intermediate after its
    predecessor arrived reuses its package rather than writing another."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    days = (INTERMEDIATE, ORIGINAL, NEWER)  # arrival order, not broadcast order
    roots = {day: _marked(tmp_path / day, APAR, _submission(day)) for day in days}
    for day in days:
        assert _ingest(roots[day], snapshots, APAR) == 0
    with guarded.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        listed = repository.list_packages(entity_id, FilingFamily.SHAREHOLDING, INSTANT)
        by_day = {p.knowledge_time.strftime("%d-%b-%Y").upper(): p for p in listed}
        newer, intermediate = by_day[NEWER], by_day[INTERMEDIATE]
        assert newer.package_id is not None
        assert newer.supersedes_package_id == intermediate.package_id
        assert repository.list_package_lineage(newer.package_id) == (intermediate, newer)
    blob = newer.members[Representation.XBRL].capture.blob_sha256
    lineage = {"xbrl": blob, "supersedes_package_id": intermediate.package_id}
    assert newer.evidence_sha256 == canonical_sha256(lineage)
    before = _counts(guarded)
    assert _ingest(roots[INTERMEDIATE], snapshots, APAR) == 0
    assert _counts(guarded) == before and before["filing_packages"] == 3
