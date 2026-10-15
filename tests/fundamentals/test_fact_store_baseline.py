"""Characterize today's ``FactStore`` over a copy of the real legacy store (D2 Task 1).

The fixture is code output checked by hand against a raw listing: 24 canonical XBRL
rows, visible 0, 0, 12, 24, 24 at the five cutoffs. Any change to the digest, chain
or cutoff rules shows up here as a changed selection hash or count.
"""

import json
import sqlite3
from pathlib import Path

from legacy_support import (
    BASELINE_CUTOFFS,
    LEGACY_PATH,
    LEGACY_SHA256,
    baseline_rows,
    file_sha256,
    legacy_copy,
    second_store,
)

from fundamentals.store.fact_store import FactRef, FactStore

FIXTURE = Path(__file__).parent / "fixtures" / "data_foundation" / "fact_store_baseline.json"


def _column(path: Path, sql: str) -> list[object]:
    """First column of a read-only query against a store copy."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [row[0] for row in conn.execute(sql)]
    finally:
        conn.close()


def test_legacy_canonical_baseline_is_unchanged(tmp_path: Path) -> None:
    """Every cutoff returns the recorded selections; the original file is untouched."""
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    path = legacy_copy(tmp_path)
    store = FactStore(path)
    try:
        assert store.fact_ref(1) == FactRef(store_id=str(path), origin="sqlite-local", origin_id=1)
        cutoffs = {cutoff.isoformat(): baseline_rows(store, cutoff) for cutoff in BASELINE_CUTOFFS}
        identities = {row["content_identity"] for row in cutoffs[BASELINE_CUTOFFS[-1].isoformat()]}
        counts = {str(key): len(store.get_revisions(str(key))) for key in sorted(identities)}
    finally:
        store.close()
    assert [len(rows) for rows in cutoffs.values()] == [0, 0, 12, 24, 24]
    assert {"cutoffs": cutoffs, "revision_counts": counts} == expected
    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256


def test_second_store_collides_on_ids_but_not_fingerprint(tmp_path: Path) -> None:
    """A migrated copy keeps the legacy ids and identities under a new fingerprint."""
    legacy = legacy_copy(tmp_path)
    second = second_store(tmp_path)
    assert _column(second, "SELECT row_id FROM facts ORDER BY row_id") == list(range(1, 44))
    assert _column(
        second, "SELECT selection_id FROM canonical_selections ORDER BY selection_id"
    ) == list(range(1, 25))
    identities = "SELECT content_identity FROM facts ORDER BY row_id"
    assert _column(second, identities) == _column(legacy, identities)
    assert file_sha256(second) != LEGACY_SHA256
    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256
