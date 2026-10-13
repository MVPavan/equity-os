"""The evidence store's clock stays monotonic when the host wall clock steps backwards.

A backward wall-clock step is simulated deterministically: the clock's high-water mark is
seeded an hour ahead of ``clock_timestamp()``, which is exactly the state a real step back
leaves behind. Knowledge-time ordering and as-of reads must hold regardless.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from evidence_support import XBRL_ONLY, Ingest, dictionary, ingest, mapping_set, policy
from pg_support import PgTestDatabase
from psycopg import errors

from fundamentals.contracts.canonical import Representation
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.pg.settings import RUNTIME_ROLE_NAME

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

AHEAD = timedelta(hours=1)
_SEED_AHEAD = (
    "SELECT setval('eqos.store_clock_us', "
    "(extract(epoch FROM clock_timestamp() + %s) * 1000000)::bigint, true)"
)
_WALL_CLOCK = "SELECT clock_timestamp()"


def _wall_clock(repository_db: PgTestDatabase) -> datetime:
    """The server's raw wall clock, which the store clock must never fall back to."""
    with repository_db.runtime_pool() as pool, pool.connection() as conn:
        row = conn.execute(_WALL_CLOCK).fetchone()
    assert row is not None
    wall: datetime = row[0]
    return wall


@pytest.fixture
def clock_ahead(pg_db: PgTestDatabase) -> None:
    """Leave the store clock's last issued time an hour past the server wall clock.

    Requested before any fixture that writes, so every row is stamped after the seeding.
    """
    with pg_db.migrator_connection() as migrator:
        migrator.execute(_SEED_AHEAD, (AHEAD,))


@pytest.fixture
def ahead_repository(clock_ahead: None, pg_db: PgTestDatabase) -> Iterator[EvidenceRepository]:
    """A repository on a database whose store clock is ahead of the wall clock."""
    with pg_db.runtime_pool() as pool:
        yield EvidenceRepository(pool)


@pytest.mark.pg
def test_store_clock_strictly_increases_past_a_stepped_back_wall_clock(
    pg_db: PgTestDatabase, ahead_repository: EvidenceRepository
) -> None:
    """Every read is strictly later than the last, never the earlier wall-clock time.

    A store time that went back would let a row recorded later sort before one recorded
    earlier, and an as-of read at "now" would miss evidence already stored.
    """
    stamps = [ahead_repository.store_clock() for _ in range(5)]
    assert all(later > earlier for earlier, later in zip(stamps, stamps[1:], strict=False))
    assert stamps[0] > _wall_clock(pg_db) + AHEAD - timedelta(minutes=5)
    with pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
        first = conn.execute("SELECT eqos.store_now()").fetchone()
        second = conn.execute("SELECT eqos.store_now()").fetchone()
    assert first is not None and second is not None
    assert first == second, "one transaction is one knowledge time, like now()"
    assert first[0] > stamps[-1]


@pytest.mark.pg
def test_runtime_role_cannot_move_the_store_clock(pg_db: PgTestDatabase) -> None:
    """The runtime role may read the clock only through the function, never set it."""
    with (
        pg_db.runtime_pool() as pool,
        pool.connection() as conn,
        pytest.raises(errors.InsufficientPrivilege),
    ):
        conn.execute("SELECT setval('eqos.store_clock_us', 0, true)")
    with pg_db.migrator_connection() as migrator:
        row = migrator.execute(
            "SELECT has_function_privilege(%s, 'eqos.store_now()', 'EXECUTE'), "
            "has_sequence_privilege(%s, 'eqos.store_clock_us', 'SELECT')",
            (RUNTIME_ROLE_NAME, RUNTIME_ROLE_NAME),
        ).fetchone()
    assert row == (True, False)


@pytest.mark.pg
@pytest.mark.retained
def test_setting_recorded_ahead_of_wall_clock_is_found_by_the_next_ingest(
    clock_ahead: None, pg_db: PgTestDatabase, ingest: Ingest
) -> None:
    """The observed failure: the seeded fiscal-year-end setting looked "in the future".

    After a backward step the setting's recorded time was later than the ingest's as-of
    read, so the ingest refused with no evidenced fiscal-year-end month.
    """
    repository = ingest.repository
    before = repository.store_clock()
    setting = repository.settings_as_of(ingest.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, before)
    assert setting is not None
    assert setting.recorded_at > _wall_clock(pg_db), "seeded on the store clock"
    report = ingest.run(ingest.intake(XBRL_ONLY))
    assert report.package_id is not None
    capture = ingest.package(report).members[Representation.XBRL].capture
    assert capture.first_seen_at > before, "capture stamped on the store clock"
    assert all(row.recorded_at > capture.first_seen_at for row in ingest.interpretations(report))


@pytest.mark.pg
def test_runtime_session_setting_cannot_move_or_freeze_the_clock(pg_db: PgTestDatabase) -> None:
    """A session-settable value must never decide a knowledge time.

    0004 cached the transaction's time in the custom setting ``eqos.store_now_us``; the runtime
    role could ``SET LOCAL`` it to stamp rows at the epoch (moved back) or at one fixed time in
    every transaction (frozen).
    """
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        stamps: list[datetime] = []
        for _ in range(2):
            with conn.transaction():
                conn.execute("SET LOCAL eqos.store_now_us = '0'")
                row = conn.execute("SELECT eqos.store_now()").fetchone()
                assert row is not None
                stamps.append(row[0])
        assert stamps[0] > _wall_clock(pg_db) - timedelta(minutes=5), "not moved to the epoch"
        assert stamps[1] > stamps[0], "not frozen across transactions"
        with conn.transaction():
            first = conn.execute("SELECT eqos.store_now()").fetchone()
            conn.execute("SET LOCAL eqos.store_now_us = '1'")
            second = conn.execute("SELECT eqos.store_now()").fetchone()
        assert first == second, "the cache ignores the setting inside a transaction too"
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM eqos_clock.transaction_times")
