"""D1a.1 acceptance: the evidence schema is immutable, owned, keyed and seeded.

Every assertion runs against a fresh database cloned from the migrated template.
Rows are written as the runtime role, so the same inserts prove the runtime
grant (SELECT and INSERT) that the refusals then bound.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import entity_map_fixtures as fx
import psycopg
import pytest
import yaml
from pg_support import REPO_ROOT, PgTestDatabase
from psycopg import errors, sql
from psycopg.rows import dict_row
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
from fundamentals.pg.settings import MIGRATOR_ROLE_NAME, RUNTIME_ROLE_NAME, SCHEMA_NAME, PgRole

pytestmark = pytest.mark.pg

APAR_IDENTITY = REPO_ROOT / "config" / "identity" / "aparinds.yaml"
NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
PERIOD_START = date(2025, 7, 1)
PERIOD_END = date(2025, 9, 30)
SHA_A = "a" * 64
SHA_B = "b" * 64
# 0001's 33 tables plus 0003's version_pins.
EXPECTED_TABLE_COUNT = 34


def _connect(db: PgTestDatabase, role: PgRole) -> psycopg.Connection:
    return psycopg.connect(db.settings.conninfo(role, dbname=db.dbname), autocommit=True)


@pytest.fixture
def runtime(pg_db: PgTestDatabase) -> Iterator[psycopg.Connection]:
    with _connect(pg_db, PgRole.RUNTIME) as conn:
        yield conn


@pytest.fixture
def migrator(pg_db: PgTestDatabase) -> Iterator[psycopg.Connection]:
    with pg_db.migrator_connection() as conn:
        yield conn


def _insert(conn: psycopg.Connection, table: str, row: dict[str, Any]) -> int:
    """Insert one row and return its id; raises whatever the schema refuses."""
    query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in row),
        sql.SQL(", ").join(sql.Placeholder() for _ in row),
    )
    fetched = conn.execute(query, tuple(row.values())).fetchone()
    assert fetched is not None
    return int(fetched[0])


def _insert_ignoring_conflict(conn: psycopg.Connection, table: str, row: dict[str, Any]) -> None:
    """The idempotent evidence write: insert-on-conflict-do-nothing."""
    query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in row),
        sql.SQL(", ").join(sql.Placeholder() for _ in row),
    )
    conn.execute(query, tuple(row.values()))


def _count(conn: psycopg.Connection, table: str) -> int:
    query = sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier(SCHEMA_NAME), sql.Identifier(table)
    )
    fetched = conn.execute(query).fetchone()
    assert fetched is not None
    return int(fetched[0])


def _read(conn: psycopg.Connection, table: str, row_id: int) -> dict[str, Any]:
    query = sql.SQL("SELECT * FROM {}.{} WHERE id = %s").format(
        sql.Identifier(SCHEMA_NAME), sql.Identifier(table)
    )
    with conn.cursor(row_factory=dict_row) as cursor:
        fetched = cursor.execute(query, (row_id,)).fetchone()
    assert fetched is not None
    return fetched


# ---------------------------------------------------------------------------
# Row builders: the minimal valid row per table
# ---------------------------------------------------------------------------


def _capture(capture_id: str = "cap-1") -> dict[str, Any]:
    return {
        "source_id": "nse-indas-xbrl-consolidated",
        "surface": "NSE_XBRL_INSTANCE",
        "request_key": "request-1",
        "capture_id": capture_id,
        "blob_sha256": SHA_A,
        "record_sha256": SHA_B,
        "registered_at": NOW,
        "first_seen_at": NOW,
    }


def _occurrence(capture_ref_id: int, anchor_key: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "capture_ref_id": capture_ref_id,
        "representation": "XBRL",
        "extractor_version": "xbrl-1",
        "native_field": "ProfitBeforeTax",
        "raw_value_text": "3405600000",
        "raw_unit": "INR",
        "raw_scale": 0,
        "raw_sign": 1,
        "precision_kind": "EXACT",
        "declared_precision": None,
        "native_context": Jsonb({"context_ref": "OneD"}),
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "period_instant": None,
        "missing_state": "VALUE",
        "disclosure": Jsonb({}),
        "anchor": Jsonb({"fact_id": anchor_key}),
        "anchor_key": anchor_key,
        "valid_time": PERIOD_END,
        "knowledge_time": NOW,
        "knowledge_time_status": "KNOWN",
        "first_seen_at": NOW,
        "revision_cause": "ORIGINAL",
    }
    row.update(overrides)
    return row


def _interpretation(
    entity_id: int, capture_ref_id: int, occurrence_id: int | None, **overrides: Any
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "origin": "DIRECT",
        "occurrence_id": occurrence_id,
        "capture_ref_id": capture_ref_id,
        "representation": "XBRL",
        "construction_rule_id": None,
        "input_digest": str(occurrence_id),
        "status": "MAPPED",
        "entity_id": entity_id,
        "canonical_id": "profit_before_tax",
        "dictionary_version": "v1",
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "period_instant": None,
        "basis": "CONSOLIDATED",
        "framework": "IND_AS",
        "currency": "INR",
        "value_kind": "CURRENCY_AMOUNT",
        "dimension_set": Jsonb([]),
        "dimension_hash": "dims-empty",
        "key_digest": "key-pbt",
        "value": Decimal("3405600000"),
        "lower": Decimal("3405600000"),
        "upper": Decimal("3405600000"),
        "tier": "EQUIVALENCE_UNPROVEN",
        "qualification_ref": None,
        "mapping_set_version": "v1",
        "mapping_entry_id": "in-capmkt.ProfitBeforeTax",
        "normalisation_policy_version": "v1",
        "extractor_version": "xbrl-1",
        "transform_trace": Jsonb({"scale": 0}),
        "reason": None,
        "revision_cause": "ORIGINAL",
        "supersedes_interpretation_id": None,
    }
    row.update(overrides)
    return row


def _attempt(entity_id: int, capture_ref_id: int) -> dict[str, Any]:
    return {
        "stage": "EXTRACTION",
        "source_id": "nse-indas-xbrl-consolidated",
        "surface": "NSE_XBRL_INSTANCE",
        "entity_id": entity_id,
        "period_end": PERIOD_END,
        "basis": "CONSOLIDATED",
        "framework": "IND_AS",
        "representation": "XBRL",
        "statement_family": None,
        "package_id": None,
        "capture_ref_id": capture_ref_id,
        "input_sha256": SHA_A,
        "extractor_version": "xbrl-1",
        "outcome": "COMPLETE",
        "reason": None,
    }


def _trace(content_sha256: str = "c" * 64) -> dict[str, Any]:
    return {
        "content_sha256": content_sha256,
        "trace_kind": "FORMULA",
        "formula_id": "opm",
        "formula_version": "v1",
        "formula_tier": "EQUIVALENCE_UNPROVEN",
        "formula_qualification_ref": None,
        "rounding_policy_id": "v1",
        "key_digest": "key-opm",
        "value_identity": "DERIVED",
        "state": "COMPUTED",
        "value": Decimal("12.34"),
        "lower": Decimal("12.33"),
        "upper": Decimal("12.35"),
        "exact_value": "617/50",
        "exact_lower": "1233/100",
        "exact_upper": "247/20",
        "effective_tier": "EQUIVALENCE_UNPROVEN",
    }


def _run_input(run_id: int, kind: str, **columns: int) -> dict[str, Any]:
    return {"run_id": run_id, "input_kind": kind, "disposition": "SELECTED", **columns}


def _seed_every_table(conn: psycopg.Connection) -> dict[str, int]:
    """One valid row in every table of schema ``eqos``, in reference order."""
    ids: dict[str, int] = {}
    ids["capture_refs"] = capture = _insert(conn, "capture_refs", _capture())
    ids["evidence_inputs"] = evidence = _insert(
        conn,
        "evidence_inputs",
        {"kind": "ISSUER_IDENTITY", "label": "fixture", "content_sha256": SHA_A},
    )
    ids["evidence_input_captures"] = _insert(
        conn,
        "evidence_input_captures",
        {"evidence_input_id": evidence, "capture_ref_id": capture},
    )
    ids["reporting_entities"] = entity = _insert(
        conn,
        "reporting_entities",
        {
            "entity_key": "FIXTURE",
            "market": "IN",
            "display_name": "Fixture Ltd",
            "evidence_input_id": evidence,
        },
    )
    ids["securities"] = security = _insert(
        conn,
        "securities",
        {"entity_id": entity, "isin": None, "share_class": "EQUITY", "evidence_input_id": evidence},
    )
    ids["listings"] = _insert(
        conn,
        "listings",
        {"security_id": security, "venue": "NSE", "symbol": "FIXT", "evidence_input_id": evidence},
    )
    ids["entity_basis_status"] = _insert(
        conn,
        "entity_basis_status",
        {
            "entity_id": entity,
            "basis_status": "CONSOLIDATED_AND_STANDALONE",
            "evidence_input_id": evidence,
        },
    )
    ids["settings_records"] = _insert(
        conn,
        "settings_records",
        {
            "entity_id": entity,
            "setting_key": "FISCAL_YEAR_END_MONTH",
            "value_text": "3",
            "evidence_input_id": evidence,
        },
    )
    ids["filing_packages"] = package = _insert(
        conn,
        "filing_packages",
        {
            "entity_id": entity,
            "family": "FINANCIAL_RESULTS",
            "reporting_period_end": PERIOD_END,
            "basis": "CONSOLIDATED",
            "framework": "IND_AS",
            "reporting_kind": "HALF_YEAR",
            "knowledge_time": NOW,
            "supersedes_package_id": None,
            "evidence_sha256": SHA_A,
        },
    )
    ids["package_members"] = _insert(
        conn,
        "package_members",
        {
            "package_id": package,
            "capture_ref_id": capture,
            "representation": "XBRL",
            "knowledge_time": NOW,
            "knowledge_time_raw": "29-Oct-2025 20:58:58",
            "knowledge_time_status": "KNOWN",
        },
    )
    ids["package_statements"] = statement = _insert(
        conn,
        "package_statements",
        {"package_id": package, "statement_family": "BALANCE_SHEET", "role": "PRESENT"},
    )
    ids["occurrences"] = occurrence = _insert(conn, "occurrences", _occurrence(capture, "f-1"))
    ids["package_statement_evidence"] = _insert(
        conn,
        "package_statement_evidence",
        {"package_statement_id": statement, "occurrence_id": occurrence},
    )
    ids["segment_members"] = segment = _insert(
        conn,
        "segment_members",
        {
            "entity_id": entity,
            "axis": "reportable_segment",
            "member": "conductors",
            "display_name": "Conductors",
            "valid_from": date(2025, 4, 1),
        },
    )
    ids["segment_member_evidence"] = _insert(
        conn,
        "segment_member_evidence",
        {"segment_member_id": segment, "occurrence_id": occurrence},
    )
    ids["acquisition_attempts"] = _insert(conn, "acquisition_attempts", _attempt(entity, capture))
    ids["interpretations"] = direct = _insert(
        conn, "interpretations", _interpretation(entity, capture, occurrence)
    )
    constructed = _insert(
        conn,
        "interpretations",
        _interpretation(
            entity,
            capture,
            None,
            origin="CONSTRUCTED",
            construction_rule_id="pbt-incl-associates",
            input_digest="operands-digest",
            mapping_entry_id=None,
            canonical_id="profit_before_tax_incl_associates",
        ),
    )
    ids["interpretation_operands"] = _insert(
        conn,
        "interpretation_operands",
        {"interpretation_id": constructed, "ordinal": 0, "operand_interpretation_id": direct},
    )
    ids["interpretation_condition_evidence"] = _insert(
        conn,
        "interpretation_condition_evidence",
        {
            "interpretation_id": direct,
            "condition_id": "discontinued-zero",
            "holds": True,
            "evidence_interpretation_id": constructed,
        },
    )
    ids["alignment_proofs"] = proof = _insert(
        conn,
        "alignment_proofs",
        {
            "package_id": package,
            "key_digest": "key-pbt",
            "canonical_id": "profit_before_tax",
            "rule_id": "pbt-subtotal",
            "rule_set_version": "v1",
            "xbrl_interpretation_id": direct,
            "pdf_interpretation_id": constructed,
            "participants_digest": "participants",
            "holds": True,
        },
    )
    ids["alignment_proof_participants"] = _insert(
        conn,
        "alignment_proof_participants",
        {"alignment_proof_id": proof, "interpretation_id": direct, "representation": "XBRL"},
    )
    ids["calculation_traces"] = trace = _insert(conn, "calculation_traces", _trace())
    ids["calculation_trace_operands"] = _insert(
        conn,
        "calculation_trace_operands",
        {
            "calculation_trace_id": trace,
            "ordinal": 0,
            "operand_name": "revenue",
            "key_digest": "key-rev",
            "temporal_role": "DURATION",
            "interpretation_id": direct,
            "scoped_tier": "EQUIVALENCE_UNPROVEN",
            "selection_source": "PACKAGE_AS_REPORTED",
            "source_state": "VALUE",
            "value": Decimal("1"),
        },
    )
    ids["definition_sets"] = definition_set = _insert(
        conn, "definition_sets", {"version": "v1", "content_sha256": SHA_A}
    )
    ids["version_pins"] = _insert(
        conn, "version_pins", {"artifact": "mapping_set", "version": "v1", "content_sha256": SHA_A}
    )
    ids["definition_records"] = record = _insert(
        conn,
        "definition_records",
        {
            "definition_set_id": definition_set,
            "record_id": "r-1",
            "scope": "MAPPING",
            "mapping_entry_id": "in-capmkt.ProfitBeforeTax",
            "canonical_id": "profit_before_tax",
            "evidence_ref": "fixture",
            "explained_amount": Decimal("0"),
            "unit": "CURRENCY_AMOUNT",
        },
    )
    ids["runs"] = run = _insert(
        conn,
        "runs",
        {
            "identity_hash": SHA_A,
            "cutoff": NOW,
            "mode": "AS_KNOWN",
            "status": "COMPLETE",
            "code_version": "abc1234",
            "manifest": Jsonb({}),
            "manifest_sha256": SHA_B,
        },
    )
    ids["run_versions"] = _insert(
        conn,
        "run_versions",
        {"run_id": run, "pin": "dictionary", "version": "v1", "content_sha256": SHA_A},
    )
    ids["run_inputs"] = _insert(
        conn, "run_inputs", _run_input(run, "INTERPRETATION", interpretation_id=direct)
    )
    ids["results"] = result = _insert(
        conn,
        "results",
        {
            "run_id": run,
            "entity_id": entity,
            "canonical_id": "profit_before_tax",
            "dictionary_version": "v1",
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "basis": "CONSOLIDATED",
            "framework": "IND_AS",
            "currency": "INR",
            "value_kind": "CURRENCY_AMOUNT",
            "dimension_set": Jsonb([]),
            "dimension_hash": "dims-empty",
            "key_digest": "key-pbt",
            "value_identity": "REPORTED",
            "applicability": "APPLICABLE",
            "applicability_rule_id": "always",
            "extraction_status": "AGREE",
            "corroboration_status": "FILING_ONLY",
        },
    )
    sides = {}
    for representation in ("XBRL", "PDF"):
        sides[representation] = _insert(
            conn,
            "result_source_values",
            {
                "result_id": result,
                "source_role": "FIRST_PARTY",
                "representation": representation,
                "source_state": "VALUE",
                "value": Decimal("3405600000"),
                "interpretation_id": direct,
            },
        )
    ids["result_source_values"] = sides["XBRL"]
    ids["result_surfaced_restatements"] = _insert(
        conn,
        "result_surfaced_restatements",
        {"result_id": result, "interpretation_id": constructed},
    )
    ids["pair_outcomes"] = pair = _insert(
        conn,
        "pair_outcomes",
        {
            "result_id": result,
            "pair_kind": "EXTRACTION",
            "left_value_id": sides["XBRL"],
            "right_value_id": sides["PDF"],
            "outcome": "AGREE",
            "difference": Decimal("0"),
        },
    )
    ids["pair_adjustments"] = _insert(
        conn,
        "pair_adjustments",
        {
            "pair_outcome_id": pair,
            "definition_record_id": record,
            "operand_name": "revenue",
            "representation": "XBRL",
            "direction": 1,
            "amount": Decimal("0"),
        },
    )
    ids["_entity"] = entity
    ids["_package"] = package
    ids["_capture"] = capture
    ids["_constructed"] = constructed
    return ids


@pytest.fixture
def seeded(runtime: psycopg.Connection) -> dict[str, int]:
    return _seed_every_table(runtime)


def _tables(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename",
        (SCHEMA_NAME,),
    ).fetchall()
    return [row[0] for row in rows]


def _update_column(conn: psycopg.Connection, table: str) -> str:
    """Any non-identity column, so the UPDATE reaches the privilege and trigger checks."""
    fetched = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name <> 'id' "
        "ORDER BY ordinal_position LIMIT 1",
        (SCHEMA_NAME, table),
    ).fetchone()
    assert fetched is not None
    return str(fetched[0])


# ---------------------------------------------------------------------------
# Immutability, ownership and grants
# ---------------------------------------------------------------------------


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
