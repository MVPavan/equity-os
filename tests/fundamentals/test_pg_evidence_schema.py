"""D1a.1 acceptance: the evidence schema is immutable, owned, keyed and seeded.

Every assertion runs against a fresh database cloned from the migrated template.
Rows are written as the runtime role, so the same inserts prove the runtime
grant (SELECT and INSERT) that the refusals then bound.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import entity_map_fixtures as fx
import psycopg
import pytest
import yaml
from pg_evidence_schema_support import (
    APAR_IDENTITY,
    EXPECTED_TABLE_COUNT,
    NOW,
    PERIOD_END,
    SHA_A,
    SHA_B,
    _attempt,
    _capture,
    _count,
    _insert,
    _insert_ignoring_conflict,
    _interpretation,
    _occurrence,
    _read,
    _run_input,
    _tables,
    _trace,
    _update_column,
    migrator,
    runtime,
    seeded,
)
from pg_support import PgTestDatabase
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.identity_seed import (
    IdentityInputError,
    SettingKey,
    load_issuer_identity,
    seed_identity,
    seed_issuer_identity,
)
from fundamentals.pg.settings import MIGRATOR_ROLE_NAME, RUNTIME_ROLE_NAME, SCHEMA_NAME

__all__ = ["runtime", "migrator", "seeded"]

pytestmark = pytest.mark.pg


def test_every_table_refuses_update_and_delete_for_both_roles(
    seeded: dict[str, int], runtime: psycopg.Connection, migrator: psycopg.Connection
) -> None:
    """Evidence never changes: runtime lacks the privilege, the owner hits the trigger."""
    tables = _tables(migrator)
    assert len(tables) == EXPECTED_TABLE_COUNT
    assert set(tables) == {name for name in seeded if not name.startswith("_")}
    for table in tables:
        target = sql.Identifier(SCHEMA_NAME, table)
        column = sql.Identifier(_update_column(migrator, table))
        update = sql.SQL("UPDATE {} SET {} = {} WHERE id = %s").format(target, column, column)
        delete = sql.SQL("DELETE FROM {} WHERE id = %s").format(target)
        row_id = (seeded[table],)
        for statement in (update, delete):
            with pytest.raises(errors.InsufficientPrivilege):
                runtime.execute(statement, row_id)
            with pytest.raises(errors.RaiseException, match="immutable"):
                migrator.execute(statement, row_id)
        with pytest.raises(errors.InsufficientPrivilege):
            runtime.execute(sql.SQL("TRUNCATE {} CASCADE").format(target))
        with pytest.raises(errors.RaiseException, match="immutable"):
            migrator.execute(sql.SQL("TRUNCATE {} CASCADE").format(target))
        assert _count(migrator, table) >= 1


def test_migrator_owns_schema_and_every_object(migrator: psycopg.Connection) -> None:
    """A separate migration role owns the schema; the runtime role owns nothing."""
    schema_owner = migrator.execute(
        "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s", (SCHEMA_NAME,)
    ).fetchone()
    assert schema_owner == (MIGRATOR_ROLE_NAME,)
    owners = migrator.execute(
        "SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s",
        (SCHEMA_NAME,),
    ).fetchall()
    assert {kind for _, kind, _ in owners} >= {"r", "S", "i"}
    assert {owner for _, _, owner in owners} == {MIGRATOR_ROLE_NAME}
    functions = migrator.execute(
        "SELECT p.proname, pg_get_userbyid(p.proowner) FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = %s",
        (SCHEMA_NAME,),
    ).fetchall()
    assert {owner for _, owner in functions} == {MIGRATOR_ROLE_NAME}
    for table in _tables(migrator):
        qualified = f"{SCHEMA_NAME}.{table}"
        granted = migrator.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'INSERT'), "
            "has_table_privilege(%s, %s, 'UPDATE'), has_table_privilege(%s, %s, 'DELETE'), "
            "has_table_privilege(%s, %s, 'TRUNCATE')",
            (RUNTIME_ROLE_NAME, qualified) * 5,
        ).fetchone()
        assert granted == (True, True, False, False, False), table


# ---------------------------------------------------------------------------
# Identity constraints
# ---------------------------------------------------------------------------


def test_securities_null_isin_is_one_identity_and_isin_is_unique_across_entities(
    seeded: dict[str, int], runtime: psycopg.Connection
) -> None:
    """Nulls-equal keys: a NULL ISIN cannot fork one security into two rows."""
    entity = seeded["_entity"]
    evidence = seeded["evidence_inputs"]
    null_isin = {"entity_id": entity, "isin": None, "share_class": "EQUITY"}
    with pytest.raises(errors.UniqueViolation):
        _insert(runtime, "securities", {**null_isin, "evidence_input_id": evidence})
    other_entity = _insert(
        runtime,
        "reporting_entities",
        {
            "entity_key": "OTHER",
            "market": "IN",
            "display_name": "Other",
            "evidence_input_id": evidence,
        },
    )
    first = {"isin": "INE000X01010", "share_class": "EQUITY", "evidence_input_id": evidence}
    _insert(runtime, "securities", {"entity_id": entity, **first})
    with pytest.raises(errors.UniqueViolation, match="securities_isin_key"):
        _insert(runtime, "securities", {"entity_id": other_entity, **first})


def test_repeated_idempotent_writes_leave_one_row(
    seeded: dict[str, int], runtime: psycopg.Connection
) -> None:
    """Nullable key parts (NULL supersedes, NULL family and package) still collide."""
    entity, capture = seeded["_entity"], seeded["_capture"]
    occurrence = _insert(runtime, "occurrences", _occurrence(capture, "f-repeat"))
    interpretation = _interpretation(entity, capture, occurrence)
    attempt = _attempt(entity, capture) | {"input_sha256": SHA_B}
    trace = _trace("d" * 64)
    for table, row in (
        ("interpretations", interpretation),
        ("acquisition_attempts", attempt),
        ("calculation_traces", trace),
    ):
        before = _count(runtime, table)
        _insert_ignoring_conflict(runtime, table, row)
        _insert_ignoring_conflict(runtime, table, row)
        assert _count(runtime, table) == before + 1, table


@pytest.mark.parametrize(
    ("table", "row"),
    [
        ("run_inputs", {"input_kind": "INTERPRETATION", "interpretation_id": 987_654_321}),
        ("calculation_trace_operands", {"interpretation_id": 987_654_321}),
        ("segment_member_evidence", {"occurrence_id": 987_654_321}),
    ],
)
def test_orphan_references_are_refused(
    seeded: dict[str, int], runtime: psycopg.Connection, table: str, row: dict[str, Any]
) -> None:
    """Every reference is a declared foreign key, never a bare integer."""
    base: dict[str, dict[str, Any]] = {
        "run_inputs": {"run_id": seeded["runs"], "disposition": "SELECTED"},
        "calculation_trace_operands": {
            "calculation_trace_id": seeded["calculation_traces"],
            "ordinal": 9,
            "operand_name": "orphan",
            "key_digest": "k",
            "temporal_role": "DURATION",
            "scoped_tier": "EQUIVALENCE_UNPROVEN",
            "selection_source": "PACKAGE_AS_REPORTED",
            "source_state": "VALUE",
        },
        "segment_member_evidence": {"segment_member_id": seeded["segment_members"]},
    }
    with pytest.raises(errors.ForeignKeyViolation):
        _insert(runtime, table, base[table] | row)


def test_conflicting_references_are_refused(
    seeded: dict[str, int], runtime: psycopg.Connection
) -> None:
    """A row may not point two ways, nor at a column its kind does not name."""
    run, direct = seeded["runs"], seeded["interpretations"]
    with pytest.raises(errors.CheckViolation):
        _insert(
            runtime,
            "run_inputs",
            _run_input(
                run, "INTERPRETATION", interpretation_id=direct, occurrence_id=seeded["occurrences"]
            ),
        )
    with pytest.raises(errors.CheckViolation):
        _insert(runtime, "run_inputs", _run_input(run, "PACKAGE", interpretation_id=direct))

    other_capture = _insert(runtime, "capture_refs", _capture("cap-other"))
    with pytest.raises(errors.ForeignKeyViolation):
        _insert(
            runtime,
            "interpretations",
            _interpretation(
                seeded["_entity"], other_capture, seeded["occurrences"], input_digest="cross"
            ),
        )
    foreign = _insert(
        runtime,
        "interpretations",
        _interpretation(seeded["_entity"], other_capture, None, origin="CONSTRUCTED")
        | {"construction_rule_id": "rule", "input_digest": "foreign", "mapping_entry_id": None},
    )
    with pytest.raises(errors.CheckViolation, match="share the capture"):
        _insert(
            runtime,
            "interpretation_operands",
            {
                "interpretation_id": seeded["_constructed"],
                "ordinal": 1,
                "operand_interpretation_id": foreign,
            },
        )
    with pytest.raises(errors.CheckViolation):
        _insert(
            runtime,
            "definition_records",
            {
                "definition_set_id": seeded["definition_sets"],
                "record_id": "r-mismatch",
                "scope": "FILING",
                "mapping_entry_id": "in-capmkt.ProfitBeforeTax",
                "canonical_id": "profit_before_tax",
                "evidence_ref": "fixture",
                "explained_amount": Decimal("0"),
                "unit": "CURRENCY_AMOUNT",
            },
        )


# ---------------------------------------------------------------------------
# Round-trips
# ---------------------------------------------------------------------------


def _plain(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value.obj if isinstance(value, Jsonb) else value for key, value in row.items()}


def test_occurrences_and_interpretations_round_trip_field_for_field(
    seeded: dict[str, int], runtime: psycopg.Connection
) -> None:
    """Precision kinds and qualification refs come back exactly as written."""
    entity, capture = seeded["_entity"], seeded["_capture"]
    variants = {
        "exact": _occurrence(capture, "rt-exact"),
        "finite": _occurrence(
            capture,
            "rt-finite",
            precision_kind="FINITE",
            declared_precision=-7,
            raw_value_text="340.56",
            raw_scale=7,
        ),
        "unsupported": _occurrence(
            capture, "rt-unsupported", precision_kind="UNSUPPORTED", raw_value_text="12"
        ),
    }
    occurrence_ids: dict[str, int] = {}
    for name, row in variants.items():
        occurrence_ids[name] = _insert(runtime, "occurrences", row)
        stored = _read(runtime, "occurrences", occurrence_ids[name])
        assert {key: stored[key] for key in row} == _plain(row), name

    with pytest.raises(errors.CheckViolation):
        _insert(runtime, "occurrences", _occurrence(capture, "rt-bad", precision_kind="FINITE"))

    interpretations = {
        "direct_ref": _interpretation(
            entity,
            capture,
            occurrence_ids["finite"],
            tier="EQUIVALENCE_DEMONSTRATED",
            qualification_ref="scope-quarter",
        ),
        "construction_ref": _interpretation(
            entity,
            capture,
            None,
            origin="CONSTRUCTED",
            construction_rule_id="tax-expense",
            input_digest="tax-operands",
            mapping_entry_id=None,
            qualification_ref="scope-tax",
        ),
        "no_ref": _interpretation(entity, capture, occurrence_ids["exact"], input_digest="no-ref"),
    }
    for name, row in interpretations.items():
        stored = _read(runtime, "interpretations", _insert(runtime, "interpretations", row))
        assert {key: stored[key] for key in row} == _plain(row), name


def test_two_packages_sharing_a_member_resolve_to_one_set_of_rows(
    seeded: dict[str, int], runtime: psycopg.Connection
) -> None:
    """Occurrences belong to the capture, so a revision reuses an unchanged member's rows."""
    original = seeded["_package"]
    revision = _insert(
        runtime,
        "filing_packages",
        {
            "entity_id": seeded["_entity"],
            "family": "FINANCIAL_RESULTS",
            "reporting_period_end": PERIOD_END,
            "basis": "CONSOLIDATED",
            "framework": "IND_AS",
            "reporting_kind": "HALF_YEAR",
            "knowledge_time": NOW,
            "supersedes_package_id": original,
            "evidence_sha256": SHA_B,
        },
    )
    _insert(
        runtime,
        "package_members",
        {
            "package_id": revision,
            "capture_ref_id": seeded["_capture"],
            "representation": "XBRL",
            "knowledge_time": NOW,
            "knowledge_time_raw": "29-Oct-2025 20:58:58",
            "knowledge_time_status": "KNOWN",
        },
    )

    def rows_for(package_id: int, table: str) -> set[int]:
        query = sql.SQL(
            "SELECT t.id FROM {} t JOIN eqos.package_members m "
            "ON m.capture_ref_id = t.capture_ref_id WHERE m.package_id = %s"
        ).format(sql.Identifier(SCHEMA_NAME, table))
        return {row[0] for row in runtime.execute(query, (package_id,)).fetchall()}

    for table in ("occurrences", "interpretations"):
        assert rows_for(original, table) == rows_for(revision, table) != set()


# ---------------------------------------------------------------------------
# Identity seeding
# ---------------------------------------------------------------------------


def _identity_rows(conn: psycopg.Connection) -> dict[str, int]:
    return {
        table: _count(conn, table)
        for table in (
            "evidence_inputs",
            "reporting_entities",
            "securities",
            "listings",
            "entity_basis_status",
            "settings_records",
        )
    }


def test_issuer_identity_seed_is_stable_and_idempotent(pg_db: PgTestDatabase) -> None:
    """APARINDS gets one entity, security and pair of listings with ids that never move."""
    identity = load_issuer_identity(APAR_IDENTITY)
    assert identity.content_sha256 == hashlib.sha256(APAR_IDENTITY.read_bytes()).hexdigest()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        first = seed_issuer_identity(conn, identity)
        after_first = _identity_rows(conn)
        second = seed_issuer_identity(conn, identity)
        assert _identity_rows(conn) == after_first
        listings = conn.execute(
            "SELECT l.venue, l.symbol, s.isin, s.share_class FROM eqos.listings l "
            "JOIN eqos.securities s ON s.id = l.security_id WHERE s.entity_id = %s "
            "ORDER BY l.venue",
            (first.entity_ids["APARINDS"],),
        ).fetchall()
        recorded = conn.execute(
            "SELECT recorded_at FROM eqos.entity_basis_status WHERE entity_id = %s",
            (first.entity_ids["APARINDS"],),
        ).fetchone()
    assert recorded is not None
    assert first.inserted == 7 and first.existing == 0
    assert second.inserted == 0 and second.existing == 7
    assert second.entity_ids == first.entity_ids
    assert second.evidence_input_id == first.evidence_input_id
    assert after_first == {
        "evidence_inputs": 1,
        "reporting_entities": 1,
        "securities": 1,
        "listings": 2,
        "entity_basis_status": 1,
        "settings_records": 1,
    }
    assert listings == [
        ("BSE", "532259", "INE372A01015", "EQUITY"),
        ("NSE", "APARINDS", "INE372A01015", "EQUITY"),
    ]

    entity_id = first.entity_ids["APARINDS"]
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        as_of = repository.basis_status_as_of(entity_id, recorded[0])
        setting = repository.settings_as_of(
            entity_id, SettingKey.FISCAL_YEAR_END_MONTH, recorded[0]
        )
        before = datetime(2000, 1, 1, tzinfo=UTC)
        assert repository.basis_status_as_of(entity_id, before) is None
        assert (
            repository.settings_as_of(entity_id, SettingKey.FISCAL_YEAR_END_MONTH, before) is None
        )
        assert as_of is not None and as_of[1] is BasisStatus.CONSOLIDATED_AND_STANDALONE
        (by_id,) = repository.get_basis_statuses([as_of[0]])
    assert by_id.evidence_input_id == first.evidence_input_id
    assert setting is not None and setting.value_text == "3"


def test_identity_input_without_a_citation_is_refused(tmp_path: Path) -> None:
    """A basis status nobody cited would decide applicability on a guess."""
    data = yaml.safe_load(APAR_IDENTITY.read_text(encoding="utf-8"))
    data["citations"] = [c for c in data["citations"] if c["field"] != "basis_status"]
    uncited = tmp_path / "uncited.yaml"
    uncited.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(IdentityInputError, match="basis_status"):
        load_issuer_identity(uncited)


def test_entity_map_seed_writes_only_verified_identifiers(pg_db: PgTestDatabase) -> None:
    """Unverified identifiers are listed, not seeded; a re-seed resolves to the same ids."""
    entity_map = fx.build(
        fx.record(
            isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE, bse=fx.ALPHA_BSE, display_name=fx.ALPHA_NAME
        ),
        fx.record(
            isin_code=fx.BRAVO_ISIN,
            nse=fx.BRAVO_NSE,
            bse=fx.BRAVO_BSE,
            display_name=fx.BRAVO_NAME,
            unverified=(fx.NSE_NS,),
            row="1",
        ),
    )
    keys = {entity.key for entity in entity_map.entities}
    assert len(keys) == 2
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        first = seed_identity(conn, entity_map, source_sha256=SHA_A)
        counts = _identity_rows(conn)
        second = seed_identity(conn, entity_map, source_sha256=SHA_A)
        assert _identity_rows(conn) == counts
        listed = conn.execute(
            "SELECT venue, symbol FROM eqos.listings ORDER BY venue, symbol"
        ).fetchall()
        isins = conn.execute("SELECT isin FROM eqos.securities ORDER BY isin").fetchall()
    assert set(first.entity_ids) == keys
    assert second.entity_ids == first.entity_ids and second.inserted == 0
    assert counts["reporting_entities"] == 2 and counts["securities"] == 2
    assert sorted(listed) == sorted(
        [("NSE", fx.ALPHA_NSE), ("BSE", fx.ALPHA_BSE), ("BSE", fx.BRAVO_BSE)]
    )
    assert isins == sorted([(fx.ALPHA_ISIN,), (fx.BRAVO_ISIN,)])
    assert any(item.endswith(":NSE_SYMBOL") for item in first.skipped)
