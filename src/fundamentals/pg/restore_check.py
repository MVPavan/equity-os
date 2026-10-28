"""Restore's phase-2 checks (plan D9 R12): the column-level delta, foreign keys and replay.

The delta compares every ``eqos`` row before and after purge-first. A row may change only into
its A-05 tombstone image (``docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md``,
``redaction-inventory``): every clear column NULL, resets applied, JSON reduced to its kept keys,
nothing else. The rows it may change are derived from the pre-purge rows the way
``eqos.tombstone_vendor_capture`` selects them for each expired VENDOR capture (0029); those must
equal their image exactly and every other row must be unchanged, numerics compared as decimals.
No row is deleted, and the only added rows are the retention rows purge-first reports.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import set_json_loads
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.compare.run import load_results, replay_run
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.retention_purge import RestoreDelta

_FOREIGN_KEYS = (
    "SELECT conrelid::regclass::text, conname FROM pg_constraint "
    "WHERE contype = 'f' AND connamespace = 'eqos'::regnamespace ORDER BY 1, 2"
)
_VALUES = ("value", "lower", "upper")
_EXACT = (*_VALUES, "exact_value", "exact_lower", "exact_upper")
_VENDOR_ROLES = frozenset({"INDEPENDENT_VENDOR", "DIAGNOSTIC"})
_CONTEXT_KEPT = frozenset(
    "schema_identity basis statement_family label section section_parent field_id header_months "
    "header_kind native_period_kind native_period_label identity_evidence_ref".split()
)
_DISCLOSURE_KEPT = frozenset(
    "identity_strength quarantined reason supporting_page_capture_id supporting_page_sha256 "
    "reconciliation metadata_sha256 metadata_verification_unknown claimed_fetched_at alignment "
    "surface_unverified capture_complete_claim capture_verified_claim skipped_column".split()
)

Rows = dict[str, dict[Any, dict[str, Any]]]


class Tombstone(BaseModel):
    """One table's A-05 redaction: what it does to a row it selects."""

    model_config = ConfigDict(frozen=True)

    clear: tuple[str, ...]
    reset: dict[str, Any] = {}
    json_keep: dict[str, frozenset[str]] = {}

    def image(self, row: dict[str, Any]) -> dict[str, Any]:
        """``row`` as the tombstone leaves it."""
        image = row | dict.fromkeys(self.clear) | self.reset
        for column, keys in self.json_keep.items():
            image[column] = {k: v for k, v in (row[column] or {}).items() if k in keys}
        return image


TOMBSTONES = {
    "occurrences": Tombstone(
        clear=("raw_value_text", "raw_sign"),
        json_keep={"native_context": _CONTEXT_KEPT, "disclosure": _DISCLOSURE_KEPT},
    ),
    "interpretations": Tombstone(clear=_VALUES, reset={"transform_trace": {}}),
    "calculation_traces": Tombstone(clear=_EXACT),
    "calculation_trace_operands": Tombstone(clear=_EXACT),
    "result_source_values": Tombstone(clear=_VALUES),
    "acquisition_attempts": Tombstone(clear=("reason",)),
    "vendor_values": Tombstone(clear=("value", "raw_text", "row_label", "column_label", "link")),
}


def table_rows(conn: psycopg.Connection[Any], tables: list[str]) -> Rows:
    """Every ``eqos`` table's rows as JSON with exact numerics, keyed by ``id`` (or the row)."""
    rows: Rows = {}
    with conn.cursor() as cursor:
        set_json_loads(partial(json.loads, parse_float=Decimal), cursor)
        for table in tables:
            query = sql.SQL("SELECT to_jsonb(t) FROM eqos.{} t").format(sql.Identifier(table))
            rows[table] = {
                row.get("id", json.dumps(row, sort_keys=True, default=str)): row
                for (row,) in cursor.execute(query).fetchall()
            }
    return rows


def tombstoned(before: Rows, expired: frozenset[int]) -> dict[str, set[Any]]:
    """Keys of the pre-purge rows ``tombstone_vendor_capture`` redacts for expired VENDOR ids."""
    classes = before["retention_classes"].values()
    vendor = {r["capture_ref_id"] for r in classes if r["retention_class"] == "VENDOR"} & expired
    interps = {k for k, r in before["interpretations"].items() if r["capture_ref_id"] in vendor}
    operands = before["calculation_trace_operands"]
    links = (*before["construction_traces"].values(), *operands.values())
    traces = {r["calculation_trace_id"] for r in links if r["interpretation_id"] in interps}
    fed = [(r["operand_trace_id"], r["calculation_trace_id"]) for r in operands.values()]
    while more := {trace for operand, trace in fed if operand in traces} - traces:
        traces |= more

    def pick(table: str, test: Any) -> set[Any]:
        return {key for key, row in before[table].items() if test(row)}

    return {
        "vendor_values": {
            key
            for key, row in before.get("vendor_values", {}).items()
            if row["capture_ref_id"] in vendor
        },
        "occurrences": pick("occurrences", lambda r: r["capture_ref_id"] in vendor),
        "interpretations": interps,
        "calculation_traces": traces,
        "calculation_trace_operands": pick(
            "calculation_trace_operands",
            lambda r: (
                r["calculation_trace_id"] in traces
                and (r["interpretation_id"] in interps or r["operand_trace_id"] in traces)
            ),
        ),
        "result_source_values": pick(
            "result_source_values",
            lambda r: (
                r["source_role"] in _VENDOR_ROLES
                and (r["interpretation_id"] in interps or r["calculation_trace_id"] in traces)
            ),
        ),
        "acquisition_attempts": pick(
            "acquisition_attempts",
            lambda r: r["stage"] == "EXTRACTION" and r["capture_ref_id"] in vendor,
        ),
    }


def delta_problems(before: Rows, after: Rows, delta: RestoreDelta) -> tuple[str, ...]:
    """Where purge-first's delta differs from the tombstones of its expired VENDOR captures and
    the retention rows it reports adding; empty when the delta is exactly that."""
    affected, problems = tombstoned(before, frozenset(delta.expired)), []
    for table in sorted(before.keys() | after.keys()):
        old, new = before.get(table, {}), after.get(table, {})
        if old.keys() - new.keys():
            problems.append(f"{table}: {len(old.keys() - new.keys())} rows deleted or rewritten")
        if len(new.keys() - old.keys()) != delta.rows.get(table, 0):
            problems.append(f"{table}: {len(new.keys() - old.keys())} rows added")
        for key in sorted(old.keys() & new.keys(), key=str):
            picked = key in affected.get(table, ())
            expected = TOMBSTONES[table].image(old[key]) if picked else old[key]
            if new[key] != expected:
                differ = sorted(c for c in expected if new[key].get(c) != expected[c])
                problems.append(f"{table} row {key}: {differ} differ from the A-05 delta")
    return tuple(problems)


def validate_foreign_keys(conn: psycopg.Connection[Any]) -> bool:
    """``VALIDATE CONSTRAINT`` every ``eqos`` foreign key; False on the first violation."""
    try:
        for table, constraint in conn.execute(_FOREIGN_KEYS).fetchall():
            conn.execute(
                sql.SQL("ALTER TABLE {} VALIDATE CONSTRAINT {}").format(
                    sql.SQL(table), sql.Identifier(constraint)
                )
            )
    except psycopg.errors.ForeignKeyViolation:
        return False
    return True


def replay(
    run_ids: tuple[int, ...], pool: ConnectionPool, config_root: Path
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The runs whose replay differs from their stored results, and those whose replay needs
    an expired vendor original (``replay_expired``, reported apart)."""
    mismatched, expired = [], []
    for run_id in run_ids:
        try:
            replayed = replay_run(run_id, pool=pool, config_root=config_root)
            if replayed != load_results(run_id, pool=pool):
                mismatched.append(run_id)
        except OriginalExpiredError:
            expired.append(run_id)
    return tuple(mismatched), tuple(expired)
