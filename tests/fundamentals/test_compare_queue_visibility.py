"""Coordinator regressions for queue commit visibility and transaction boundaries."""

from typing import Any

import psycopg
import pytest
from pg_evidence_schema_support import migrator, runtime, seeded
from pg_support import PgTestDatabase
from test_compare_queue import _draft, _publish, _seed_verified_synthetic_accept

from fundamentals.compare.queue import (
    capture_queue_overlay,
    publish_queue_drafts,
    read_queue_overlay,
)

__all__ = ["migrator", "runtime", "seeded"]
pytestmark = pytest.mark.pg


def test_overlay_reread_excludes_queue_membership_committed_after_capture(
    seeded: dict[str, int], pg_db: PgTestDatabase
) -> None:
    """An older store clock must not make a later commit enter a captured overlay."""
    with pg_db.runtime_pool() as pool:
        with pool.connection() as writer, writer.transaction(), writer.cursor() as cursor:
            publish_queue_drafts(
                cursor,
                run_id=seeded["runs"],
                drafts=(_draft(seeded, pair_identity="late-committed-membership"),),
            )
            captured = capture_queue_overlay(pool, run_id=seeded["runs"])
        reread = read_queue_overlay(
            pool,
            run_id=seeded["runs"],
            as_of=captured.as_of,
            recorded_position=captured.recorded_position,
        )
    assert reread == captured


def test_queue_publisher_refuses_autocommit_before_item_mutation(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    """The cursor helper cannot publish outside its caller's active transaction."""
    before = runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0]
    with pytest.raises(ValueError, match="(?i)transaction"):
        with runtime.cursor() as cursor:
            publish_queue_drafts(
                cursor,
                run_id=seeded["runs"],
                drafts=(_draft(seeded, pair_identity="autocommit-refusal"),),
            )
    assert runtime.execute("SELECT count(*) FROM eqos.queue_items").fetchone()[0] == before


def test_overlay_reread_excludes_verified_disposition_committed_after_capture(
    seeded: dict[str, int],
    runtime: psycopg.Connection[Any],
    migrator: psycopg.Connection[Any],
    pg_db: PgTestDatabase,
) -> None:
    (item,) = _publish(
        runtime,
        seeded["runs"],
        (_draft(seeded, pair_identity="late-verified-disposition"),),
    )
    assert item.item_id is not None
    with pg_db.runtime_pool() as pool:
        with migrator.transaction():
            disposition_id = _seed_verified_synthetic_accept(migrator, item.item_id)
            captured = capture_queue_overlay(pool, run_id=seeded["runs"])
        reread = read_queue_overlay(
            pool,
            run_id=seeded["runs"],
            as_of=captured.as_of,
            recorded_position=captured.recorded_position,
        )
        fresh = capture_queue_overlay(pool, run_id=seeded["runs"])

    assert reread == captured
    assert item.item_id in {queued.item_id for queued in reread.open_items}
    assert item.item_id not in {queued.item_id for queued in fresh.open_items}
    assert disposition_id in {
        disposition.disposition_id for disposition in fresh.accepted_dispositions
    }
