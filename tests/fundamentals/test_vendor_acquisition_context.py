"""Narrow vendor acquisition pin admission and genuine 0007 upgrade preservation."""

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import Ingest, dictionary, mapping_set, policy
from pg_evidence_schema_support import _attempt, _insert, _read, migrator, runtime, seeded
from pg_support import (
    MIGRATIONS_DIR,
    PgTestDatabase,
    create_database,
    drop_database,
    load_test_settings,
    mint_name,
)
from run_support import CONFIG, Runner

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.compare.run_store import RunStore
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.migrations import apply_migrations

__all__ = ["dictionary", "mapping_set", "policy", "migrator", "runtime", "seeded"]
pytestmark = pytest.mark.pg


def _vendor_attempt(ids: dict[str, int], representation: str = "HTML") -> dict[str, Any]:
    row = _attempt(ids["_entity"], ids["_capture"])
    row.update(
        stage="ACQUISITION",
        source_id="screener-subscriber",
        surface="SCREENER_FINANCIALS" if representation == "HTML" else "SCREENER_SCHEDULE",
        representation=representation,
        statement_family="PL",
        package_id=None,
        capture_ref_id=None,
        input_sha256="b" * 64,
        extractor_version="screener-v1",
        extraction_context_sha256="c" * 64,
        outcome="FAILED",
        reason="constructed acquisition-schema fixture; no retained binding",
    )
    return row


@pytest.mark.parametrize("representation", ["HTML", "JSON"])
def test_pinned_capture_free_vendor_acquisition_shape_is_admitted(
    seeded: dict[str, int], runtime: psycopg.Connection[Any], representation: str
) -> None:
    """A real runtime insert retains its extractor and logical scope without a capture."""
    supplied = _vendor_attempt(seeded, representation)
    row_id = _insert(runtime, "acquisition_attempts", supplied)
    actual = _read(runtime, "acquisition_attempts", row_id)
    assert all(actual[name] == value for name, value in supplied.items())
    assert actual["attempted_at"] is not None


def test_legacy_first_party_acquisition_still_uses_empty_extractor(
    seeded: dict[str, int], runtime: psycopg.Connection[Any]
) -> None:
    row = _attempt(seeded["_entity"], seeded["_capture"])
    row.update(
        stage="ACQUISITION",
        capture_ref_id=None,
        extractor_version="",
        input_sha256="d" * 64,
        outcome="FAILED",
    )
    row_id = _insert(runtime, "acquisition_attempts", row)
    assert _read(runtime, "acquisition_attempts", row_id)["extractor_version"] == ""


@pytest.mark.parametrize(
    "defect",
    ["package", "capture", "missing_context", "malformed_context", "upper_context", "xbrl_pin"],
)
def test_vendor_pin_branch_refuses_broader_or_unproven_shapes(
    seeded: dict[str, int], runtime: psycopg.Connection[Any], defect: str
) -> None:
    row = _vendor_attempt(seeded)
    changes = {
        "package": {"package_id": seeded["_package"]},
        "capture": {"capture_ref_id": seeded["_capture"]},
        "missing_context": {"extraction_context_sha256": None},
        "malformed_context": {"extraction_context_sha256": "not-a-sha256"},
        "upper_context": {"extraction_context_sha256": "C" * 64},
        "xbrl_pin": {"representation": "XBRL"},
    }
    row.update(changes[defect])
    before = runtime.execute("SELECT count(*) FROM eqos.acquisition_attempts").fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(runtime, "acquisition_attempts", row)
    assert runtime.execute("SELECT count(*) FROM eqos.acquisition_attempts").fetchone()[0] == before


@pytest.mark.parametrize("defect", ["capture", "extractor"])
def test_extraction_still_requires_its_actual_capture_and_extractor(
    seeded: dict[str, int], runtime: psycopg.Connection[Any], defect: str
) -> None:
    row = _attempt(seeded["_entity"], seeded["_capture"])
    row.update(input_sha256="e" * 64)
    row.update({"capture_ref_id": None} if defect == "capture" else {"extractor_version": ""})
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(runtime, "acquisition_attempts", row)


@pytest.fixture
def through_0007_db(tmp_path: Path) -> Iterator[PgTestDatabase]:
    settings = load_test_settings()
    name = mint_name(settings)
    create_database(settings, name)
    database = PgTestDatabase(dbname=name, settings=settings)
    try:
        old = tmp_path / "through-0007"
        old.mkdir()
        for source in sorted(MIGRATIONS_DIR.glob("000[1-7]_*.sql")):
            shutil.copyfile(source, old / source.name)
        assert len(tuple(old.iterdir())) == 7
        with database.migrator_connection() as connection:
            assert len(apply_migrations(connection, old)) == 7
        yield database
    finally:
        drop_database(settings, name)


@pytest.mark.retained
def test_0008_upgrade_preserves_actual_v1_run_results_inputs_and_replay(
    through_0007_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> None:
    upgrade = tmp_path / "through-0008"
    upgrade.mkdir()
    for source in sorted(MIGRATIONS_DIR.glob("000[1-8]_*.sql")):
        shutil.copyfile(source, upgrade / source.name)
    with through_0007_db.runtime_pool() as pool:
        evidence = EvidenceRepository(pool)
        intake = Ingest(through_0007_db, evidence, tmp_path, dictionary, mapping_set, policy)
        intake.run(intake.intake())
        runner = Runner(intake, pool)
        record = runner.run()
        before_results = runner.results(record.run_id)
        before_manifest = RunStore(pool).read_manifest(record.run_id)
        with pool.connection() as connection:
            with connection.transaction():
                item_id = _insert(
                    connection,
                    "queue_items",
                    {
                        "run_id": record.run_id,
                        "pair_identity": "constructed-upgrade-queue-witness",
                        "outcome": "UNMAPPED",
                        "input_sha256": "f" * 64,
                        "severity": "MEDIUM",
                        "diagnostic": False,
                        "routing_reason": "CONSTRUCTED_SCHEMA_UPGRADE_WITNESS",
                    },
                )
                _insert(
                    connection,
                    "queue_run_items",
                    {"run_id": record.run_id, "item_id": item_id},
                )
                deciding_attempt = connection.execute(
                    "SELECT id FROM eqos.acquisition_attempts ORDER BY id LIMIT 1"
                ).fetchone()[0]
                _insert(
                    connection,
                    "queue_item_inputs",
                    {"item_id": item_id, "attempt_id": deciding_attempt},
                )
            before = connection.execute(
                "SELECT identity_hash,manifest_sha256,manifest FROM eqos.runs WHERE id=%s",
                (record.run_id,),
            ).fetchone()
            attempts = connection.execute(
                "SELECT * FROM eqos.acquisition_attempts ORDER BY id"
            ).fetchall()
            queue_before = connection.execute(
                "SELECT * FROM eqos.queue_items ORDER BY id"
            ).fetchall()
            membership_before = connection.execute(
                "SELECT * FROM eqos.queue_run_items ORDER BY id"
            ).fetchall()
            queue_inputs_before = connection.execute(
                "SELECT * FROM eqos.queue_item_inputs ORDER BY id"
            ).fetchall()
        with through_0007_db.migrator_connection() as connection:
            applied = apply_migrations(connection, upgrade)
            assert [item.filename for item in applied] == ["0008_vendor_acquisition_context.sql"]
        with pool.connection() as connection:
            assert (
                connection.execute(
                    "SELECT identity_hash,manifest_sha256,manifest FROM eqos.runs WHERE id=%s",
                    (record.run_id,),
                ).fetchone()
                == before
            )
            assert (
                connection.execute("SELECT * FROM eqos.acquisition_attempts ORDER BY id").fetchall()
                == attempts
            )
            assert (
                connection.execute("SELECT * FROM eqos.queue_items ORDER BY id").fetchall()
                == queue_before
            )
            assert (
                connection.execute("SELECT * FROM eqos.queue_run_items ORDER BY id").fetchall()
                == membership_before
            )
            assert (
                connection.execute("SELECT * FROM eqos.queue_item_inputs ORDER BY id").fetchall()
                == queue_inputs_before
            )
        assert RunStore(pool).read_manifest(record.run_id) == before_manifest
        assert runner.results(record.run_id) == before_results
        assert runner.replay(record.run_id, config_root=CONFIG) == before_results
