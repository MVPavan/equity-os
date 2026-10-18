"""Restore's phase-2 checks (plan D9 R12): the column-level delta, foreign keys and replay.

The delta compares every ``eqos`` row before and after purge-first. A row may change only into
its A-05 tombstone image (``docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md``,
``redaction-inventory``): every clear column NULL, resets applied, JSON reduced to its kept keys,
nothing else. Rows tied to a capture by column change only for a capture purge-first expired;
the trace tables carry no capture column and are checked by image alone. No row is deleted, and
the only added rows are the retention rows purge-first reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
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

Rows = dict[str, dict[Any, dict[str, Any]]]


class Tombstone(BaseModel):
    """One table's A-05 redaction: the rows it selects and what it does to them."""

    model_config = ConfigDict(frozen=True)

    clear: tuple[str, ...]
    reset: dict[str, Any] = {}
    json_keep: dict[str, frozenset[str]] = {}
    capture_column: str | None = None
    when: dict[str, frozenset[str]] = {}

    def image(self, row: dict[str, Any], expired: frozenset[int]) -> dict[str, Any] | None:
        """``row`` as the tombstone leaves it, or None if the tombstone never selects it."""
        if any(row.get(column) not in allowed for column, allowed in self.when.items()):
            return None
        if self.capture_column and row.get(self.capture_column) not in expired:
            return None
        image = row | dict.fromkeys(self.clear) | self.reset
        for column, keys in self.json_keep.items():
            image[column] = {k: v for k, v in (row[column] or {}).items() if k in keys}
        return image


TOMBSTONES = {
    "occurrences": Tombstone(
        clear=("raw_value_text", "raw_sign"),
        json_keep={
            "native_context": frozenset(
                {
                    "schema_identity",
                    "basis",
                    "statement_family",
                    "label",
                    "section",
                    "section_parent",
                    "field_id",
                    "header_months",
                    "header_kind",
                    "native_period_kind",
                    "native_period_label",
                    "identity_evidence_ref",
                }
            ),
            "disclosure": frozenset(
                {
                    "identity_strength",
                    "quarantined",
                    "reason",
                    "supporting_page_capture_id",
                    "supporting_page_sha256",
                    "reconciliation",
                    "metadata_sha256",
                    "metadata_verification_unknown",
                    "claimed_fetched_at",
                    "surface_unverified",
                    "capture_complete_claim",
                    "capture_verified_claim",
                    "alignment",
                    "skipped_column",
                }
            ),
        },  # fmt: skip
        capture_column="capture_ref_id",
    ),
    "interpretations": Tombstone(
        clear=_VALUES, reset={"transform_trace": {}}, capture_column="capture_ref_id"
    ),
    "calculation_traces": Tombstone(clear=_EXACT),
    "calculation_trace_operands": Tombstone(clear=_EXACT),
    "result_source_values": Tombstone(
        clear=_VALUES, when={"source_role": frozenset({"INDEPENDENT_VENDOR", "DIAGNOSTIC"})}
    ),
    "acquisition_attempts": Tombstone(
        clear=("reason",),
        capture_column="capture_ref_id",
        when={"stage": frozenset({"EXTRACTION"})},
    ),
}


def table_rows(conn: psycopg.Connection[Any], tables: list[str]) -> Rows:
    """Every row of each ``eqos`` table as JSON, keyed by ``id`` (or the row itself)."""
    rows: Rows = {}
    for table in tables:
        query = sql.SQL("SELECT to_jsonb(t) FROM eqos.{} t").format(sql.Identifier(table))
        rows[table] = {
            row.get("id", json.dumps(row, sort_keys=True)): row
            for (row,) in conn.execute(query).fetchall()
        }
    return rows


def delta_problems(before: Rows, after: Rows, delta: RestoreDelta) -> tuple[str, ...]:
    """What purge-first changed beyond tombstones of its expired captures and the retention
    rows it reports adding; empty when the delta is exactly that."""
    expired, problems = frozenset(delta.expired), []
    for table in sorted(before.keys() | after.keys()):
        old, new = before.get(table, {}), after.get(table, {})
        if old.keys() - new.keys():
            problems.append(f"{table}: {len(old.keys() - new.keys())} rows deleted or rewritten")
        if len(new.keys() - old.keys()) != delta.rows.get(table, 0):
            problems.append(f"{table}: {len(new.keys() - old.keys())} rows added")
        rule = TOMBSTONES.get(table)
        for key in sorted(old.keys() & new.keys(), key=str):
            if old[key] != new[key] and (rule is None or rule.image(old[key], expired) != new[key]):
                changed = sorted(c for c in new[key] if new[key][c] != old[key].get(c))
                problems.append(f"{table} row {key}: {changed} changed outside the A-05 inventory")
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
