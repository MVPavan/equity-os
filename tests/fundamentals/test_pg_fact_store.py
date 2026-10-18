"""D2.3: the PostgreSQL fact store beyond the shared contract suites (plan D2, Task 3).

The both-backend suites (``test_store``, ``test_store_temporal``, ``test_pipeline_e2e`` and the
baseline) prove the ``FactStore`` contract, including concurrent writers; these cases cover what
only PostgreSQL has: handles beside preserved refs, store state, bounded retries and the
non-forking constraint.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from legacy_support import LEGACY_SHA256
from pg_support import PgTestDatabase
from test_legacy_import import Rig
from test_store import _fact, _observation

from fundamentals.compare.queue import overlay_boundary
from fundamentals.contracts.fact import CanonicalStatus
from fundamentals.pg.legacy_import import origin_id_for
from fundamentals.pg.settings import PgRole
from fundamentals.store.fact_store import CanonicalSelectionError, FactRef
from fundamentals.store.pg_fact_store import (
    NATIVE_ORIGIN,
    FactStoreFrozenError,
    FactStoreRetryError,
    PgFactStore,
    create_native_store,
)

pytestmark = pytest.mark.pg

COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.fact_rows WHERE target_store = %s), "
    "(SELECT count(*) FROM eqos.fact_selections WHERE target_store = %s)"
)
OPEN_EVENT = (
    "INSERT INTO eqos.fact_store_events (store_id, operation_id, state, recorded_at) "
    "VALUES (%s, %s, 'OPEN', eqos.store_now())"
)
IDENTITY = "SELECT content_identity FROM eqos.fact_rows WHERE target_store = %s AND handle = 7"
FAIL_INSERTS = """
CREATE SEQUENCE eqos.test_attempts;
CREATE FUNCTION eqos.test_serialization_failure() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER AS $$
BEGIN
    PERFORM nextval('eqos.test_attempts');
    RAISE EXCEPTION 'synthetic serialization failure' USING ERRCODE = '40001';
END $$;
CREATE TRIGGER test_serialization_failure BEFORE INSERT ON eqos.fact_rows
    FOR EACH ROW EXECUTE FUNCTION eqos.test_serialization_failure();
"""
FORK = """
INSERT INTO eqos.fact_selections (target_store, handle, origin, origin_id, content_identity,
    row_handle, sequence, predecessor_handle, selected_at, reason, legacy_baseline, synthesized,
    selection_sha256)
SELECT target_store, 3, origin, 999, content_identity, row_handle, 3, 1,
    '2100-01-01T00:00:00+00:00', 'fork', false, false, selection_sha256
FROM eqos.fact_selections WHERE target_store = %s AND handle = 2
"""


def imported_store(pg_db: PgTestDatabase, tmp_path: Path) -> str:
    """Import a legacy copy into its own store (state ``IMPORTED``) and return the store id."""
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    return origin_id_for(LEGACY_SHA256)


def _sql(pg_db: PgTestDatabase, role: PgRole, statement: str, *params: object) -> list[Any]:
    """Run one autocommit statement as ``role``; its rows, if any."""
    conninfo = pg_db.settings.conninfo(role, dbname=pg_db.dbname)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        cursor = conn.execute(statement, params or None)
        return cursor.fetchall() if cursor.description else []


@pytest.mark.retained
def test_imported_store_refuses_writes_then_keeps_native_and_legacy_ids_apart(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Handles stay unique per store, refs stay origin-qualified, stale checks use handles."""
    store_id = imported_store(pg_db, tmp_path)
    counts = _sql(pg_db, PgRole.RUNTIME, COUNTS, store_id, store_id)
    with pg_db.runtime_pool() as pool:
        store = PgFactStore(pool, store_id)
        with pytest.raises(FactStoreFrozenError):
            store.put(_fact())
        with pytest.raises(FactStoreFrozenError):
            store.select_canonical(1, "frozen")
        assert _sql(pg_db, PgRole.RUNTIME, COUNTS, store_id, store_id) == counts == [(43, 24)]

        _sql(pg_db, PgRole.RUNTIME, OPEN_EVENT, store_id, uuid.uuid4())
        assert store.put(_fact()).row_id == 44
        assert store.fact_ref(44) == FactRef(store_id=store_id, origin=NATIVE_ORIGIN, origin_id=1)
        assert store.fact_ref(1) == FactRef(store_id=store_id, origin=store_id, origin_id=1)

        identity = _sql(pg_db, PgRole.RUNTIME, IDENTITY, store_id)[0][0]
        legacy = next(rev for rev in store.get_revisions(identity) if rev.row_id == 7)
        observation = legacy.fact.observation.model_copy(
            update={"normalized_value": Decimal("1.23"), "raw_value": "1.23"}
        )
        restated = store.put(legacy.fact.model_copy(update={"observation": observation}))
        assert (restated.row_id, restated.revision_ordinal) == (45, 3)
        assert store.fact_ref(45) == FactRef(store_id=store_id, origin=NATIVE_ORIGIN, origin_id=2)

        head = store.get_selection_history(legacy.content_identity)[-1]
        assert head.selection_id != 1
        with pytest.raises(CanonicalSelectionError, match="stale"):
            store.select_canonical(45, "native", expected_selection_id=1)
        selected = store.select_canonical(45, "native", expected_selection_id=head.selection_id)
        assert selected.canonical_status is CanonicalStatus.CANONICAL
        history = store.get_selection_history(legacy.content_identity)
        assert (history[-1].selection_id, history[-1].predecessor_id) == (25, head.selection_id)
    refs = "SELECT handle, origin, origin_id FROM eqos.fact_selections WHERE target_store = %s "
    assert _sql(
        pg_db, PgRole.RUNTIME, refs + "AND handle IN (1, 25) ORDER BY handle", store_id
    ) == [
        (1, store_id, 1),
        (25, NATIVE_ORIGIN, 3),
    ]


def test_persistent_serialization_failure_raises_after_bounded_retries(
    pg_db: PgTestDatabase,
) -> None:
    """Three retries, then a loud failure, and nothing persisted."""
    _sql(pg_db, PgRole.MIGRATOR, FAIL_INSERTS)
    with pg_db.runtime_pool() as pool:
        store_id = create_native_store(pool, "retry")
        with pytest.raises(FactStoreRetryError):
            PgFactStore(pool, store_id).put(_fact())
    assert _sql(pg_db, PgRole.MIGRATOR, "SELECT last_value FROM eqos.test_attempts") == [(4,)]
    assert _sql(pg_db, PgRole.RUNTIME, COUNTS, store_id, store_id) == [(0, 0)]


def test_a_forking_selection_violates_the_store_constraint(pg_db: PgTestDatabase) -> None:
    """A second successor of one predecessor is rejected by the database itself."""
    with pg_db.runtime_pool() as pool:
        store_id = create_native_store(pool, "fork")
        store = PgFactStore(pool, store_id)
        row_id = store.put(_fact()).row_id
        store.select_canonical(row_id, "first")
        store.select_canonical(row_id, "second")
    with pytest.raises(psycopg.errors.UniqueViolation, match="predecessor_handle"):
        _sql(pg_db, PgRole.MIGRATOR, FORK, store_id)


def test_historical_reads_hold_native_selections_to_their_recording_times(
    pg_db: PgTestDatabase,
) -> None:
    """A native selection dated before a cutoff but recorded after it is not effective there
    (PREP-2/2b r2 #2): the cutoff falls back to the last selection recorded by then."""
    early, late = datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)
    with pg_db.runtime_pool() as pool:
        store = PgFactStore(pool, create_native_store(pool, "recorded"))
        original = store.put(_fact())
        store.select_canonical(original.row_id, "original", early)
        between = overlay_boundary(pool)
        restated = store.put(_fact(_observation(normalized_value="6400", raw_value="64000000000")))
        store.select_canonical(restated.row_id, "backdated restatement", late)
        identity = original.content_identity
        assert store.get_canonical(identity, cutoff=datetime(2026, 9, 10, tzinfo=UTC)) is None
        at_between = store.get_canonical(identity, cutoff=between)
        assert at_between is not None and at_between.row_id == original.row_id
        current = store.get_canonical(identity)
        assert current is not None and current.row_id == restated.row_id
