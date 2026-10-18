"""D1a Task 4 ruling R3: a stored trace operand never records a selection that did not happen.

Migration 0002 lets ``calculation_trace_operands.selection_source`` be NULL, but only for a
missing operand or for a computed one whose constituents (each with its real source) sit in
a child trace. A selected value with no source, or a NULL source pointing at a trace that
does not exist, is refused by the schema itself. Rows are written as the runtime role.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from pg_support import PgTestDatabase
from psycopg import errors, sql

from fundamentals.pg.settings import SCHEMA_NAME, PgRole

pytestmark = pytest.mark.pg

MIGRATION = "0002_trace_selection_provenance.sql"
MISSING_TRACE_ID = 987_654_321


@pytest.fixture
def runtime(pg_db: PgTestDatabase) -> Iterator[psycopg.Connection]:
    with psycopg.connect(
        pg_db.settings.conninfo(PgRole.RUNTIME, dbname=pg_db.dbname), autocommit=True
    ) as conn:
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


def _trace(conn: psycopg.Connection, content_sha256: str) -> int:
    """A stored computed trace."""
    return _insert(
        conn,
        "calculation_traces",
        {
            "content_sha256": content_sha256,
            "trace_kind": "DIMENSIONAL_AGGREGATE",
            "formula_id": None,
            "formula_version": None,
            "formula_tier": None,
            "formula_qualification_ref": None,
            "rounding_policy_id": "v1",
            "key_digest": "key-segments-total",
            "value_identity": "DERIVED",
            "state": "COMPUTED",
            "value": Decimal("3.00"),
            "lower": Decimal("3.00"),
            "upper": Decimal("3.00"),
            "exact_value": "3/1",
            "exact_lower": "3/1",
            "exact_upper": "3/1",
            "effective_tier": "EQUIVALENCE_UNPROVEN",
            "operand_count": 3,
        },
    )


@pytest.fixture
def parent(runtime: psycopg.Connection) -> int:
    return _trace(runtime, "e" * 64)


def _operand(parent: int, ordinal: int, **columns: Any) -> dict[str, Any]:
    """A trace operand row; ``columns`` override state, source and child-trace reference."""
    return {
        "calculation_trace_id": parent,
        "ordinal": ordinal,
        "operand_name": f"operand_{ordinal}",
        "key_digest": "k",
        "temporal_role": "DURATION",
        "scoped_tier": "EQUIVALENCE_UNPROVEN",
        "selection_source": None,
        "source_state": "VALUE",
    } | columns


def test_migration_is_recorded(pg_db: PgTestDatabase) -> None:
    """The template applied 0002 after 0001, so every test database carries the rule."""
    with pg_db.migrator_connection() as migrator:
        rows = migrator.execute("SELECT filename FROM eqos_meta.schema_migrations").fetchall()
    assert MIGRATION in {row[0] for row in rows}


def test_missing_or_computed_operands_may_record_no_source(
    runtime: psycopg.Connection, parent: int
) -> None:
    """A missing member, or an aggregate over mixed sources (its child trace holds them)."""
    child = _trace(runtime, "f" * 64)
    _insert(runtime, "calculation_trace_operands", _operand(parent, 0, source_state="NO_VALUE"))
    _insert(runtime, "calculation_trace_operands", _operand(parent, 1, operand_trace_id=child))
    _insert(
        runtime,
        "calculation_trace_operands",
        _operand(parent, 2, selection_source="HISTORICAL_PACKAGE", operand_trace_id=child),
    )


def test_a_selected_value_without_a_source_is_refused(
    runtime: psycopg.Connection, parent: int
) -> None:
    """A VALUE operand that is not computed was selected by some rule; it must say which."""
    with pytest.raises(errors.CheckViolation, match="selection_provenance"):
        _insert(runtime, "calculation_trace_operands", _operand(parent, 0))


def test_a_source_outside_the_four_rules_is_still_refused(
    runtime: psycopg.Connection, parent: int
) -> None:
    """Dropping NOT NULL kept the closed list of selection sources."""
    with pytest.raises(errors.CheckViolation):
        _insert(
            runtime, "calculation_trace_operands", _operand(parent, 0, selection_source="GUESSED")
        )


def test_no_source_cannot_lean_on_an_orphan_child_trace(
    runtime: psycopg.Connection, parent: int
) -> None:
    """The child-trace exemption needs a real stored trace, never a bare integer."""
    with pytest.raises(errors.ForeignKeyViolation):
        _insert(
            runtime,
            "calculation_trace_operands",
            _operand(parent, 0, operand_trace_id=MISSING_TRACE_ID),
        )
