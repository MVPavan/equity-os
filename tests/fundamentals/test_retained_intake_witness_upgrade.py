"""Exact 0001–0009 to0010 upgrade with actual retained v1/v2 runs and replay."""

import shutil
from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, mapping_set, policy
from pg_support import MIGRATIONS_DIR, PgTestDatabase
from psycopg import sql
from run_support import CONFIG, Runner, SpyReader, forbid_current_reads
from test_first_party_generation import _append
from test_queue_overlay_snapshots import through_0008_db

from fundamentals.compare.queue import publish_queue_drafts
from fundamentals.compare.queue_overlay import capture_queue_overlay, read_queue_overlay
from fundamentals.compare.run_config import ConfigVersions, load_run_config
from fundamentals.contracts.comparison import SourceRef, SourceRole
from fundamentals.contracts.review_queue import QueueItemDraft, QueueSeverity
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.migrations import apply_migrations

__all__ = ["dictionary", "mapping_set", "policy", "through_0008_db"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def _directory(tmp_path: Path, name: str, last: int) -> Path:
    target = tmp_path / name
    target.mkdir()
    for number in range(1, last + 1):
        (source,) = MIGRATIONS_DIR.glob(f"{number:04d}_*.sql")
        shutil.copyfile(source, target / source.name)
    return target


def test_actual_retained_v1_v2_rows_results_and_queue_survive_only_0010(
    through_0008_db: PgTestDatabase,
    tmp_path: Path,
    dictionary,
    mapping_set,
    policy,
    monkeypatch,
) -> None:
    database = through_0008_db
    through9 = _directory(tmp_path, "exact-through-0009", 9)
    with database.migrator_connection() as connection:
        applied = apply_migrations(connection, through9)
        assert [entry.filename for entry in applied] == ["0009_queue_overlay_snapshots.sql"]
    with database.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        intake = Ingest(database, repository, tmp_path, dictionary, mapping_set, policy)
        intake.run(intake.intake())
        runner = Runner(intake, pool)
        old = runner.run()
        old_results = runner.results(old.run_id)
        loaded = load_run_config(CONFIG, ConfigVersions(dictionary="v2", mapping_set="v2"))
        handoff = _append(intake, CONFIG, loaded, pool)
        new = runner.run(versions=ConfigVersions(dictionary="v2", mapping_set="v2"))
        new_results = runner.results(new.run_id)
        assert new.run_id != old.run_id
        assert handoff.retained_intake_witness_id is None
        selected = next(
            value
            for row in old_results
            for value in row.source_values
            if value.interpretation_id is not None
        )
        (interpretation,) = repository.get_interpretations([selected.interpretation_id])
        (capture,) = repository.get_capture_refs([interpretation.capture_ref_id])
        row = next(item for item in old_results if selected in item.source_values)
        draft = QueueItemDraft(
            key=row.key,
            pair_identity="retained-0010-upgrade",
            outcome="NOT_COMPARABLE",
            severity=QueueSeverity.MEDIUM,
            source_refs=(
                SourceRef(
                    source_role=SourceRole.FIRST_PARTY,
                    source_id=capture.source_id,
                    surface=capture.surface,
                    representation=interpretation.representation,
                ),
            ),
            evidence_interpretation_ids=(selected.interpretation_id,),
        )
        with pool.connection() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                publish_queue_drafts(cursor, run_id=old.run_id, drafts=(draft,))
        overlay = capture_queue_overlay(pool, run_id=old.run_id)
        with pool.connection() as connection:
            tables = tuple(
                name
                for (name,) in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='eqos' ORDER BY tablename"
                ).fetchall()
            )
            assert len(tables) == 42
            before = {
                table: connection.execute(
                    sql.SQL("SELECT * FROM eqos.{} ORDER BY id").format(sql.Identifier(table))
                ).fetchall()
                for table in tables
            }
        through10 = _directory(tmp_path, "exact-through-0010", 10)
        with database.migrator_connection() as connection:
            applied = apply_migrations(connection, through10)
            assert [entry.filename for entry in applied] == ["0010_retained_intake_witness.sql"]
        with pool.connection() as connection:
            after = {
                table: connection.execute(
                    sql.SQL("SELECT * FROM eqos.{} ORDER BY id").format(sql.Identifier(table))
                ).fetchall()
                for table in tables
            }
        assert after == before
        assert runner.results(old.run_id) == old_results
        assert runner.results(new.run_id) == new_results
        assert (
            read_queue_overlay(
                pool,
                run_id=old.run_id,
                as_of=overlay.as_of,
                recorded_position=overlay.recorded_position,
            )
            == overlay
        )
        spy = SpyReader(repository)
        forbid_current_reads(monkeypatch)
        assert runner.replay(old.run_id, reader=spy) == old_results
        assert runner.replay(new.run_id, reader=spy) == new_results
        assert spy.calls
