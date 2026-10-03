"""Public-seam proofs that later selections cannot rewrite earlier knowledge."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest
from test_store import _fact, _observation

from fundamentals.store.fact_store import CanonicalSelectionError, FactStore


def test_later_selection_preserves_earlier_cutoff_after_reopen(tmp_path: Path) -> None:
    """A restatement changes current results without changing the July result."""
    path = tmp_path / "temporal.db"
    store = FactStore(path)
    original = store.put(_fact())
    store.select_canonical(original.row_id, "original", datetime(2024, 7, 19, tzinfo=UTC))
    restated = store.put(
        _fact(_observation(normalized_value="6400", raw_value="64000000000")).model_copy(
            update={
                "knowledge_time": datetime(2024, 8, 1, tzinfo=UTC),
                "first_seen_time": datetime(2024, 8, 1, tzinfo=UTC),
            }
        )
    )
    store.select_canonical(restated.row_id, "restated", datetime(2024, 8, 2, tzinfo=UTC))
    store.close()

    reopened = FactStore(path)
    try:
        past = reopened.get_canonical(
            original.content_identity, cutoff=datetime(2024, 7, 31, tzinfo=UTC)
        )
        assert past is not None
        assert past.fact.observation.normalized_value == Decimal("6374")
        assert past.canonical_reason == "original"
        assert past.canonical_selected_at == datetime(2024, 7, 19, tzinfo=UTC)
        assert reopened.query_canonical(cutoff=datetime(2024, 7, 18, tzinfo=UTC)) == ()
        assert [row.fact.observation.normalized_value for row in reopened.query_canonical()] == [
            Decimal("6400")
        ]
    finally:
        reopened.close()


@pytest.mark.parametrize("field", ["knowledge_time", "first_seen_time"])
def test_unselected_and_future_known_facts_are_not_historical_evidence(
    tmp_path: Path, field: str
) -> None:
    """A value alone is not a decision, and first-seen bounds cannot be bypassed."""
    store = FactStore(tmp_path / "eligibility.db")
    try:
        candidate = store.put(_fact())
        assert store.get_canonical(candidate.content_identity) is None
        future = store.put(
            _fact(_observation(normalized_value="6500", raw_value="65000000000")).model_copy(
                update={field: datetime(2024, 8, 1, tzinfo=UTC)}
            )
        )
        with pytest.raises(CanonicalSelectionError):
            store.select_canonical(future.row_id, "too early", datetime(2024, 7, 31, tzinfo=UTC))
        assert store.get_selection_history(candidate.content_identity) == ()
        store.select_canonical(future.row_id, "eligible", datetime(2024, 8, 1, tzinfo=UTC))
        assert store.query_canonical(cutoff=datetime(2024, 7, 31, tzinfo=UTC)) == ()
        assert [
            row.fact.observation.normalized_value
            for row in store.query_canonical(cutoff=datetime(2024, 8, 1, tzinfo=UTC))
        ] == [Decimal("6500")]
    finally:
        store.close()


@pytest.mark.parametrize("field", ["knowledge_time", "first_seen_time"])
def test_put_rejects_naive_fact_times_without_writing(tmp_path: Path, field: str) -> None:
    """A timezone guess must not silently make a fact eligible for historical use."""
    store = FactStore(tmp_path / "naive.db")
    try:
        fact = _fact().model_copy(update={field: datetime(2024, 7, 18)})
        with pytest.raises(ValueError, match="aware UTC"):
            store.put(fact)
        assert store.get_revisions(FactStore.content_identity_for(fact.observation)) == ()
    finally:
        store.close()


def test_invalid_and_stale_decisions_leave_chain_and_reasons_unchanged(tmp_path: Path) -> None:
    """Rejected decisions neither demote the prior revision nor replace its reason."""
    store = FactStore(tmp_path / "invalid.db")
    try:
        original = store.put(_fact())
        stamp = datetime(2024, 7, 19, tzinfo=UTC)
        store.select_canonical(original.row_id, "original", stamp)
        before = store.get_selection_history(original.content_identity)
        restated = store.put(_fact(_observation("6400", "64000000000")))
        for invalid_time in (stamp, datetime(2024, 7, 18, tzinfo=UTC), datetime(2024, 7, 20)):
            with pytest.raises(ValueError):
                store.select_canonical(restated.row_id, "invalid", invalid_time)
        with pytest.raises(KeyError):
            store.select_canonical(999, "missing", datetime(2024, 7, 20, tzinfo=UTC))
        with pytest.raises(CanonicalSelectionError):
            store.select_canonical(
                restated.row_id, "stale", datetime(2024, 7, 20, tzinfo=UTC), expected_selection_id=0
            )
        assert store.get_selection_history(original.content_identity) == before
        current = store.get_canonical(original.content_identity)
        assert current is not None and current.row_id == original.row_id
        store.select_canonical(
            restated.row_id,
            "restated",
            datetime(2024, 7, 20, tzinfo=UTC),
            expected_selection_id=before[0].selection_id,
        )
        history = store.get_selection_history(original.content_identity)
        assert [item.reason for item in history] == ["original", "restated"]
        assert history[1].predecessor_id == history[0].selection_id
        retained = store.get_revisions(original.content_identity)
        assert retained[0].canonical_reason == "original"
        assert retained[0].canonical_selected_at == stamp
    finally:
        store.close()


def test_concurrent_compare_and_append_has_one_winner(tmp_path: Path) -> None:
    """Two writers naming the same predecessor cannot fork the selection history."""
    path = tmp_path / "concurrent.db"
    store = FactStore(path)
    original = store.put(_fact())
    restated = store.put(_fact(_observation("6400", "64000000000")))
    store.select_canonical(original.row_id, "root", datetime(2024, 7, 19, tzinfo=UTC))
    head_id = store.get_selection_history(original.content_identity)[0].selection_id
    store.close()
    barrier = Barrier(2)

    def select(row_id: int) -> str:
        """Compete through separate real SQLite connections after a deterministic barrier."""
        writer = FactStore(path)
        try:
            barrier.wait(timeout=5)
            try:
                writer.select_canonical(
                    row_id,
                    "winner",
                    datetime(2024, 7, 20, tzinfo=UTC),
                    expected_selection_id=head_id,
                )
                return "selected"
            except CanonicalSelectionError:
                return "stale"
        finally:
            writer.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(select, [original.row_id, restated.row_id]))
    assert sorted(results) == ["selected", "stale"]
    reopened = FactStore(path)
    try:
        history = reopened.get_selection_history(original.content_identity)
        assert [item.sequence for item in history] == [1, 2]
        assert history[1].predecessor_id == head_id
        assert len(reopened.query_canonical()) == 1
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "cutoff", [datetime(2024, 7, 20), datetime(2024, 7, 20, tzinfo=timezone(timedelta(hours=5)))]
)
def test_canonical_reads_require_aware_utc_cutoff(tmp_path: Path, cutoff: datetime) -> None:
    """Neither read interface silently translates an ambiguous caller cutoff."""
    store = FactStore(tmp_path / "cutoff.db")
    try:
        candidate = store.put(_fact())
        with pytest.raises(ValueError, match="aware UTC"):
            store.get_canonical(candidate.content_identity, cutoff=cutoff)
        with pytest.raises(ValueError, match="aware UTC"):
            store.query_canonical(cutoff=cutoff)
    finally:
        store.close()


def test_database_failure_rolls_back_selection_and_allows_a_later_append(tmp_path: Path) -> None:
    """A real SQLite write failure leaves the prior chain intact and the connection usable."""
    path = tmp_path / "rollback.db"
    store = FactStore(path)
    try:
        original = store.put(_fact())
        store.select_canonical(original.row_id, "original", datetime(2024, 7, 19, tzinfo=UTC))
        before = store.get_selection_history(original.content_identity)
        restated = store.put(_fact(_observation("6400", "64000000000")))
        with sqlite3.connect(path) as database:
            database.execute("""CREATE TRIGGER synthetic_failure BEFORE INSERT
                ON canonical_selections WHEN NEW.reason = 'reject'
                BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="synthetic disk failure"):
            store.select_canonical(restated.row_id, "reject", datetime(2024, 7, 20, tzinfo=UTC))
        assert store.get_selection_history(original.content_identity) == before
        current = store.get_canonical(original.content_identity)
        assert current is not None and current.row_id == original.row_id
        store.select_canonical(restated.row_id, "accepted", datetime(2024, 7, 20, tzinfo=UTC))
        assert [item.reason for item in store.get_selection_history(original.content_identity)] == [
            "original",
            "accepted",
        ]
    finally:
        store.close()


@pytest.mark.parametrize("table", ["facts", "canonical_selections"])
def test_persisted_records_cannot_be_updated_or_deleted(tmp_path: Path, table: str) -> None:
    """SQLite rejects a caller attempting to rewrite either value or decision history."""
    path = tmp_path / "immutable.db"
    store = FactStore(path)
    try:
        original = store.put(_fact())
        store.select_canonical(original.row_id, "original", datetime(2024, 7, 19, tzinfo=UTC))
        before = store.get_selection_history(original.content_identity)
        with sqlite3.connect(path) as database:
            column = "canonical_reason" if table == "facts" else "reason"
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                database.execute(f"UPDATE {table} SET {column} = 'rewritten'")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                database.execute(f"DELETE FROM {table}")
        assert store.get_selection_history(original.content_identity) == before
        assert len(store.get_revisions(original.content_identity)) == 1
    finally:
        store.close()


def test_audit_digest_detects_changed_decision_even_if_trigger_is_bypassed(tmp_path: Path) -> None:
    """A corrupted decision cannot masquerade as a valid canonical selection."""
    path = tmp_path / "tamper.db"
    store = FactStore(path)
    try:
        original = store.put(_fact())
        store.select_canonical(original.row_id, "original", datetime(2024, 7, 19, tzinfo=UTC))
        with sqlite3.connect(path) as database:
            database.execute("DROP TRIGGER immutable_canonical_selections_UPDATE")
            database.execute("UPDATE canonical_selections SET reason = 'tampered'")
        with pytest.raises(CanonicalSelectionError, match="digest mismatch"):
            store.get_canonical(original.content_identity)
        with pytest.raises(CanonicalSelectionError, match="digest mismatch"):
            store.query_canonical()
    finally:
        store.close()


def test_concurrent_put_is_idempotent_and_ordinals_are_unique(tmp_path: Path) -> None:
    """A locked append prevents duplicate rows and duplicate revision ordinals."""
    path = tmp_path / "concurrent-put.db"
    barrier = Barrier(2)

    def put(value: str) -> int:
        """Append using separate connections, without sharing a thread-bound store."""
        writer = FactStore(path)
        try:
            barrier.wait(timeout=5)
            return writer.put(_fact(_observation(value, value))).row_id
        finally:
            writer.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        duplicate = list(pool.map(put, ["6374", "6374"]))
        distinct = list(pool.map(put, ["6400", "6500"]))
    assert duplicate[0] == duplicate[1]
    assert distinct[0] != distinct[1]
    store = FactStore(path)
    try:
        identity = FactStore.content_identity_for(_observation())
        assert [row.revision_ordinal for row in store.get_revisions(identity)] == [1, 2, 3]
    finally:
        store.close()


@pytest.mark.parametrize("missing_time", [False, True])
def test_migration_retains_all_values_without_inventing_overwritten_selection(
    tmp_path: Path,
    missing_time: bool,
) -> None:
    """Only the surviving canonical decision is recoverable from mutable legacy metadata."""
    path = tmp_path / "legacy.db"
    identity = FactStore.content_identity_for(_observation())
    with sqlite3.connect(path) as legacy:
        legacy.execute("""CREATE TABLE facts (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT, content_identity TEXT NOT NULL,
            value_hash TEXT NOT NULL, revision_family TEXT NOT NULL, revision_ordinal INTEGER,
            canonical_status TEXT, canonical_selected_at TEXT, canonical_reason TEXT,
            source_id TEXT, file_sha256 TEXT, anchor TEXT, valid_time_start TEXT,
            valid_time_end TEXT, knowledge_time TEXT, first_seen_time TEXT,
            fact_json TEXT, created_at TEXT)""")
        for row_id, value, status in [(1, "6374", "superseded"), (2, "6400", "canonical")]:
            fact = _fact(_observation(value, value))
            legacy.execute(
                "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id,
                    identity,
                    f"legacy-value-{row_id}",
                    "infy-fy25q1-profit",
                    row_id,
                    status,
                    None if missing_time else "2024-08-02T00:00:00+00:00",
                    "restated",
                    "synthetic",
                    "0" * 64,
                    "{}",
                    "2024-04-01",
                    "2024-06-30",
                    "2024-07-18T00:00:00+00:00",
                    "2024-07-18T00:00:00+00:00",
                    fact.model_dump_json(),
                    "2024-07-18T00:00:00+00:00",
                ),
            )
    migration_started = datetime.now(UTC)
    migrated = FactStore(path)
    try:
        assert [
            row.fact.observation.normalized_value for row in migrated.get_revisions(identity)
        ] == [Decimal("6374"), Decimal("6400")]
        assert migrated.get_canonical(identity, cutoff=datetime(2024, 7, 31, tzinfo=UTC)) is None
        current = migrated.get_canonical(identity)
        assert current is not None and current.row_id == 2
        history = migrated.get_selection_history(identity)
        assert len(history) == 1 and history[0].legacy_baseline
        if missing_time:
            assert history[0].selected_at >= migration_started
        else:
            assert history[0].selected_at == datetime(2024, 8, 2, tzinfo=UTC)
    finally:
        migrated.close()
    reopened = FactStore(path)
    try:
        assert len(reopened.get_selection_history(identity)) == 1
        assert reopened.get_revisions(identity)[0].canonical_reason == "restated"
    finally:
        reopened.close()
