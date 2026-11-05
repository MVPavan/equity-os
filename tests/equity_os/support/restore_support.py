"""Shared seams of the D9 restore tests (plan D9 R12): restore with the authority files of an
environment's backup directory, reads of a restored target, sets aside, and a quote seed on a
capture with stored bytes (the ledger fixtures register captures without them).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg
from purge_support import Env
from retention_support import CONFIG, restore_args

from equity_os.contracts.storage.retention_purge import RestoreDelta
from equity_os.storage.backup.backup import RestoreCheck, restore_backup
from equity_os.storage.database.settings import PgRole

PurgeFirst = Callable[[psycopg.Connection], RestoreDelta]

REPORT = (
    "INSERT INTO eqos.reports (entity_id, period, kind) VALUES (%s, 'FY27_Q1', 'BOOTSTRAP_THESIS') "
    "RETURNING id"
)
VERSION = (
    "INSERT INTO eqos.report_versions (report_id, author, knowledge_cutoff, pinned_run_ids, "
    "content_hash, created_at, created_xid) VALUES (%s, 'fixture', now(), '{}', %s, now(), 0) "
    "RETURNING id"
)
SECTION = (
    "INSERT INTO eqos.report_sections (version_id, ordinal, section_key, body, sha256) "
    "VALUES (%s, 0, 'q', 'q', encode(sha256('q'), 'hex')) RETURNING id"
)
QUOTE = (
    "INSERT INTO eqos.numeric_claims (version_id, section_id, claim_key, citation_kind, "
    "value_kind, value, qualifiers, precision, rounding, epistemic_class, unresolved, "
    "capture_ref_id, anchor, quote) VALUES (%s, %s, 'q.1', 'SOURCE_QUOTE', 'COUNT', 7, '{}', 0, "
    "'ROUND_HALF_UP', 'observed', false, %s, 'p1', %s) RETURNING id"
)
QUOTED = "SELECT capture_ref_id, quote FROM eqos.numeric_claims WHERE id = %s"
REPLICA = "SET session_replication_role = replica"  # past the evidence mutation triggers
TAMPER = {
    "kept column": "UPDATE eqos.occurrences SET first_seen_at = first_seen_at + interval '1 day' "
    "WHERE capture_ref_id = %s",
    "retained capture": "UPDATE eqos.occurrences SET raw_value_text = NULL, raw_sign = NULL "
    "WHERE capture_ref_id = %s",
    "untouched payload": "UPDATE eqos.occurrences SET raw_value_text = '3405600000', raw_sign = 1, "
    """native_context = '{"context_ref": "OneD"}' WHERE capture_ref_id = %s""",
    "exact numeric": "UPDATE eqos.interpretations SET upper = 3405600000.000000000000000002 "
    "WHERE capture_ref_id = %s",
}


def restore(
    env: Env, set_dir: Path, database: str, *, first: Any = None, replay: bool = False
) -> tuple[RestoreCheck, Path]:
    """Restore ``set_dir`` with the authority files of ``env.sets`` and the journal head of
    ``env.root``; ``first`` wraps the composed purge-first. Returns the check and the restored
    snapshot root."""
    root = env.root.parent / f"restored-{database}"
    args = restore_args(env.db, set_dir, root, env.sets, live=env.root)
    if first is not None:
        args["purge_first"] = first(args["purge_first"])
    check = restore_backup(
        set_dir,
        env.db.settings,
        database=database,
        snapshot_root=root,
        replay_runs=replay,
        config_root=CONFIG,
        **args,
    )
    return check, root


def on(env: Env, database: str, query: str, *params: object) -> list[tuple[Any, ...]]:
    """Rows of one statement on a restored database, as the admin role."""
    with psycopg.connect(env.db.settings.conninfo(PgRole.ADMIN, dbname=database)) as conn:
        return conn.execute(query, params).fetchall()


def runtime_refused(env: Env, database: str) -> bool:
    """Whether the runtime role is refused a connection to ``database``."""
    try:
        psycopg.connect(env.db.settings.conninfo(PgRole.RUNTIME, dbname=database)).close()
    except psycopg.OperationalError:
        return True
    return False


def aside(set_dir: Path, tmp_path: Path) -> Path:
    """A copy of a set outside the backup directory, taken before a purge removes it."""
    return Path(shutil.copytree(set_dir, tmp_path / "aside" / set_dir.name))


def quote(env: Env, entity_id: int, capture: int, text: str) -> int:
    """SEED: a report version whose ``SOURCE_QUOTE`` claim quotes ``text`` from ``capture`` (a
    capture with stored bytes, which the ledger fixtures' captures lack); returns the claim."""
    with env.db.migrator_connection() as conn:
        ((report,),) = conn.execute(REPORT, (entity_id,)).fetchall()
        ((version,),) = conn.execute(VERSION, (report, uuid.uuid4().hex * 2)).fetchall()
        ((section,),) = conn.execute(SECTION, (version,)).fetchall()
        ((claim,),) = conn.execute(QUOTE, (version, section, capture, text)).fetchall()
        return int(claim)
