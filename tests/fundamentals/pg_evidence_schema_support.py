"""D1a.1 acceptance: the evidence schema is immutable, owned, keyed and seeded.

Every assertion runs against a fresh database cloned from the migrated template.
Rows are written as the runtime role, so the same inserts prove the runtime
grant (SELECT and INSERT) that the refusals then bound.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from ledger_support import IDENTITY_TABLES, LEDGER_TABLES, MEMORY_TABLES
from pg_support import REPO_ROOT, PgTestDatabase
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from fundamentals.pg.settings import SCHEMA_NAME, PgRole

pytestmark = pytest.mark.pg

APAR_IDENTITY = REPO_ROOT / "config" / "identity" / "aparinds.yaml"
NOW = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
PERIOD_START = date(2025, 7, 1)
PERIOD_END = date(2025, 9, 30)
SHA_A = "a" * 64
SHA_B = "b" * 64
# 0001's 33 tables, 0003's version_pins, 0006's four queue tables, 0007's construction_traces,
# 0008's queue_item_traces, 0010's seven fact-store tables and 0011's fact_admissions.
EXPECTED_TABLE_COUNT = 48


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
    ids["construction_traces"] = _insert(
        conn,
        "construction_traces",
        {"interpretation_id": constructed, "calculation_trace_id": trace},
    )
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
def seeded(pg_db: PgTestDatabase, runtime: psycopg.Connection) -> dict[str, int]:
    """One row in every evidence table, the queue's included, written by the runtime role
    (the disposition by the owner role, plan D3 D11)."""
    ids = _seed_every_table(runtime)
    from selection_support import key

    with runtime.transaction():
        item = _insert(
            runtime,
            "queue_items",
            {
                "run_id": ids["runs"],
                "key_digest": "constructed-queue-key",
                "measurement_key": Jsonb(key("profit_before_tax").model_dump(mode="json")),
                "pair_identity": "constructed-pair",
                "outcome": "MISMATCH",
                "input_sha256": "5" * 64,
                "severity": "HIGH",
                "diagnostic": False,
                "routing_reason": "MAPPING_DEFINITION_OR_SOURCE_ERROR",
                "source_refs": Jsonb([]),
            },
        )
        ids["queue_items"] = item
        ids["queue_item_inputs"] = _insert(
            runtime,
            "queue_item_inputs",
            {"item_id": item, "interpretation_id": ids["interpretations"]},
        )
        ids["queue_item_traces"] = _insert(
            runtime,
            "queue_item_traces",
            {"item_id": item, "calculation_trace_id": ids["calculation_traces"]},
        )
        ids["queue_run_items"] = _insert(
            runtime, "queue_run_items", {"run_id": ids["runs"], "item_id": item}
        )
    with psycopg.connect(pg_db.conninfo(PgRole.OWNER), autocommit=True) as owner:
        ids["queue_dispositions"] = _insert(
            owner,
            "queue_dispositions",
            {
                "item_id": item,
                "kind": "MAPPING_FIX",
                "reason": "constructed schema fixture",
                "decider": "constructed-author",
                "evidence_ref": "constructed-only",
            },
        )
    _seed_legacy_store(runtime, ids)
    return ids


def _seed_legacy_store(conn: psycopg.Connection, ids: dict[str, int]) -> None:
    """One row in each D2 fact-store table (composite keys return no id; 0 stands in)."""
    store, row = {"target_store": "sqlite-seed"}, {"target_store": "sqlite-seed", "row_handle": 1}
    origin = store | {"handle": 1, "origin": "sqlite-seed", "origin_id": 1, "content_identity": "c"}
    rows: dict[str, dict[str, Any]] = {
        "fact_stores": {"store_id": "sqlite-seed", "kind": "LEGACY_SQLITE", "file_label": "seed"}
        | {"file_sha256": SHA_A},
        "fact_rows": origin
        | {"value_hash": "v", "revision_family": "f", "revision_ordinal": 1}
        | {"canonical_status": "canonical", "source_id": "s", "file_sha256": SHA_A, "anchor": "{}"}
        | {"valid_time_start": "2025-07-01", "knowledge_time": "t", "first_seen_time": "t"}
        | {"fact_json": "{}", "created_at": "t"},
        "fact_selections": origin
        | {"row_handle": 1, "sequence": 1, "selected_at": "t", "reason": "r"}
        | {"legacy_baseline": True, "synthesized": True, "selection_sha256": SHA_B},
        "legacy_fact_translations": row
        | {"translation_version": "v", "entity_id": ids["_entity"], "canonical_id": "revenue"}
        | {"basis": "CONSOLIDATED", "framework": "IND_AS", "value_kind": "CURRENCY_AMOUNT"}
        | {"dimension_set": Jsonb([])},
        "legacy_evidence_bindings": row
        | {"capture_ref_id": ids["_capture"], "file_sha256": SHA_A, "anchor": "{}"},
        "legacy_imports": {"store_id": "sqlite-seed", "manifest_sha256": SHA_A}
        | {"preflight_sha256": SHA_B, "file_sha256": SHA_A},
    }
    with conn.transaction():
        for table, values in rows.items():
            _insert_ignoring_conflict(conn, table, values)
            ids[table] = 0
        ids["fact_store_events"] = _insert(
            conn,
            "fact_store_events",
            {"store_id": "sqlite-seed", "operation_id": uuid.uuid4(), "state": "IMPORTED"}
            | {"recorded_at": NOW},
        )
        ids["fact_admissions"] = _insert(
            conn,
            "fact_admissions",
            {"store_id": "sqlite-seed", "row_handle": 1, "fact_origin": "sqlite-seed"}
            | {"fact_origin_id": 1, "run_id": ids["runs"], "result_id": ids["results"]}
            | {"interpretation_id": ids["interpretations"], "occurrence_id": ids["occurrences"]}
            | {"overlay_position": NOW, "bridge_version": "admission-bridge/1"},
        )


def _tables(conn: psycopg.Connection) -> list[str]:
    """The evidence tables: the ledger's and memory's have their own matrix in
    test_ledger_integrity, the identity tables in test_identity_layers."""
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename",
        (SCHEMA_NAME,),
    ).fetchall()
    return [row[0] for row in rows if row[0] not in LEDGER_TABLES | MEMORY_TABLES | IDENTITY_TABLES]


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
