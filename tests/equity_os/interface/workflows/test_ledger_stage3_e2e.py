"""D5.5: the ledger Stage 3 end-to-end (plan D5, Task 5; ledger spec §3, O5, P2), the D5 exit.

On the ledger Stage 2 state, ``ledger export --stock APARINDS --status-notes --memory`` writes
each version's narrative and status note and the stock's promoted memory; each narrative hashes
to its stored content hash, so status never alters narrative bytes. The reader login SELECTs
exactly the manifest's rows from the two status views, every write it attempts is refused and
no table changes. No vault is written. The frozen ledger Stage 3 manifest is the only source of
expected values.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from operator import itemgetter
from pathlib import Path
from typing import Any

import psycopg
import pytest
from pg_support import PgTestDatabase
from psycopg import errors, sql
from test_frozen_manifests import LEDGER3, load
from test_ledger_stage2_e2e import stage2_state

from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK
from equity_os.interface.entry.cli import main
from equity_os.storage.database.settings import GROUP_ROLES, PgRole

MANIFEST = load(LEDGER3)
_VERSIONS = (
    "SELECT v.id, v.predecessor_id, r.period, r.kind, v.content_hash FROM eqos.report_versions v "
    "JOIN eqos.reports r ON r.id = v.report_id "
    "JOIN eqos.reporting_entities e ON e.id = r.entity_id WHERE e.entity_key = %s"
)
_REPORT_ROWS = (
    "SELECT version_id, predecessor_id, stock, period, report_kind, status, "
    "latest_validation_mode, untrusted_claims FROM eqos.report_status_view"
)
_MEMORY_ROWS = (
    "SELECT kind, stock, statement, epistemic_class, valid_from, valid_to "
    "FROM eqos.promoted_memory_view"
)
_CLAIM_ID = "SELECT id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s"
_TABLES = "SELECT tablename FROM pg_tables WHERE schemaname = 'eqos'"
_WRITES = {
    "INSERT": "INSERT INTO {target} DEFAULT VALUES",
    "UPDATE": "UPDATE {target} SET {column} = {column}",
    "DELETE": "DELETE FROM {target}",
}
_COLUMN = {
    "eqos.report_status_view": "stock",
    "eqos.promoted_memory_view": "stock",
    "eqos.decisions": "ruling",
}
_VIEW_REFUSALS = {"55000", "42501"}  # rewriter (non-updatable view) or privilege check
_NONE = "none"
_OPEN = "open"


def positions(rows: list[tuple[Any, ...]]) -> dict[int, int]:
    """Each version id's chain position (root 1) from ``(id, predecessor_id, ...)`` rows."""
    predecessor = {row[0]: row[1] for row in rows}

    def position(version_id: int) -> int:
        parent = predecessor[version_id]
        return 1 if parent is None else 1 + position(parent)

    return {version_id: position(version_id) for version_id in predecessor}


def sections(text: str) -> tuple[str, dict[str, list[str]]]:
    """A note's head and its ``## `` sections' non-empty lines, ``none`` read as no lines."""
    head, *rest = text.split("\n## ")
    bodies = {}
    for section in rest:
        heading, _, body = section.partition("\n")
        lines = body.strip().splitlines()
        bodies[heading] = [] if lines == [_NONE] else lines
    return head, bodies


def fields(lines: list[str]) -> dict[str, str]:
    """``- key: value`` lines as a mapping."""
    pairs = (line.removeprefix("- ").partition(": ") for line in lines if line.startswith("- "))
    return {key: value for key, _, value in pairs}


def note_shown(text: str) -> dict[str, Any]:
    """What a status note shows, in the manifest's shape (untrusted claims as a multiset, since
    the note lists them in store order), plus its version id."""
    head, bodies = sections(text)
    identity, validation = fields(head.splitlines()), fields(bodies["Latest validation"])
    return {
        "version": int(identity["version"]),
        "status": identity["status"],
        "decisions": [line.split()[1] for line in bodies["Decisions"]],
        "validation": {"mode": validation["mode"], "creator": validation["creator"]},
        "untrusted": Counter(
            tuple(line.removeprefix("- ").split(": ")) for line in bodies["Untrusted claims"]
        ),
        "flags": bodies["Revalidation flags"],
    }


def memory_shown(text: str) -> list[dict[str, Any]]:
    """Each ``memory.md`` item: kind, statement, epistemic class, valid range, flag, supports."""
    _, *items = text.split("\n## Memory item ")
    shown = []
    for item in items:
        heading, statement, listed = item.strip().split("\n\n", 2)
        values = fields(listed.splitlines())
        shown.append(
            {
                "kind": heading.split(": ", 1)[1],
                "statement": statement,
                "epistemic_class": values["epistemic class"],
                "valid": values["valid"],
                "needs_revalidation": values["needs revalidation"],
                "supports": [
                    line.strip().removeprefix("- ")
                    for line in listed.splitlines()
                    if line.startswith("  - ")
                ],
            }
        )
    return shown


def expected_memory(
    files: dict[str, dict[str, Any]],
    version_ids: dict[str, int],
    claim_id: Callable[[int, str], int],
) -> list[dict[str, Any]]:
    """The manifest's items in :func:`memory_shown`'s shape, each support with its version id and
    the database id ``claim_id(version_id, claim_key)`` of the claim the manifest names."""
    return [
        {
            "kind": item["kind"],
            "statement": item["statement"],
            "epistemic_class": item["epistemic_class"],
            "valid": f"{item['valid_from']} to {item['valid_to'] or _OPEN}",
            "needs_revalidation": "yes" if item["needs_revalidation"] else "no",
            "supports": [
                f"{files[s['stem']]['report']['period']} {files[s['stem']]['report']['kind']} "
                f"{s['claim']} (version {version_ids[s['stem']]}, "
                f"claim {claim_id(version_ids[s['stem']], s['claim'])})"
                for s in item["supports"]
            ],
        }
        for item in MANIFEST["memory"]
    ]


def table_counts(pg_db: PgTestDatabase) -> dict[str, int]:
    """Every ``eqos`` table's row count, read as the migrator."""
    with pg_db.migrator_connection() as conn:
        tables = [name for (name,) in conn.execute(_TABLES).fetchall()]
        query = "SELECT count(*) FROM eqos.{}"
        return {
            name: conn.execute(sql.SQL(query).format(sql.Identifier(name))).fetchall()[0][0]
            for name in tables
        }


@pytest.mark.pg
@pytest.mark.retained
def test_ledger_stage3_end_to_end(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    header, reader = MANIFEST["header"], MANIFEST["reader"]
    files = {f["stem"]: f for f in MANIFEST["files"]}
    (stock,) = {f["report"]["stock"] for f in files.values()}
    out = tmp_path / "views"
    with stage2_state(pg_db, tmp_path, monkeypatch) as built:
        # 1. The stock's narratives, status notes and promoted memory.
        command = ["ledger", "export", "--stock", stock, "--out", str(out)]
        assert main([*command, "--status-notes", "--memory"]) == EXIT_OK
        written = out / stock
        names = {f"{stem}{suffix}" for stem in files for suffix in (".md", ".status.md")}
        assert {p.name for p in written.iterdir()} == names | {"memory.md"}

        # 2. Each narrative hashes to its version's stored content hash; each note shows the
        # manifest's status, decisions, validation, untrusted claims and (no) flags.
        rows = built.rig.query(_VERSIONS, stock)
        chain = positions(rows)
        stems = {f"{period}-{kind}-v{chain[i]}": (i, digest) for i, _, period, kind, digest in rows}
        assert set(stems) == set(files)
        for stem, spec in files.items():
            version_id, digest = stems[stem]
            assert hashlib.sha256((written / f"{stem}.md").read_bytes()).hexdigest() == digest
            expected = {k: spec[k] for k in ("status", "decisions", "validation", "flags")}
            expected["untrusted"] = Counter((u["key"], u["state"]) for u in spec["untrusted"])
            shown = note_shown((written / f"{stem}.status.md").read_text())
            assert shown == expected | {"version": version_id}, stem

        # 3. memory.md holds exactly the manifest's item.
        version_ids = {stem: version_id for stem, (version_id, _) in stems.items()}
        shown_memory = memory_shown((written / "memory.md").read_text())

        def claim_id(version_id: int, claim_key: str) -> int:
            ((found,),) = built.rig.query(_CLAIM_ID, version_id, claim_key)
            return int(found)

        assert shown_memory == expected_memory(files, version_ids, claim_id)

    # 4. The reader sees exactly the manifest's view rows, every write is refused and no table
    # changes.
    views = {view["name"] for view in reader["views"]}
    before = table_counts(pg_db)
    with pg_db.role_pool(PgRole.READER) as pool:
        with pool.connection() as conn:
            assert conn.execute("SELECT current_user").fetchone() == (GROUP_ROLES[PgRole.READER],)
            report_rows = conn.execute(_REPORT_ROWS).fetchall()
            memory_rows = conn.execute(_MEMORY_ROWS).fetchall()
        chain = positions(report_rows)
        shown_reports = [
            {
                "stock": row[2],
                "period": row[3],
                "kind": row[4],
                "version": f"v{chain[row[0]]}",
                "status": row[5],
                "mode": row[6],
                "untrusted": row[7],
            }
            for row in report_rows
        ]
        key = itemgetter("period", "kind", "version")
        assert sorted(shown_reports, key=key) == sorted(reader["report_status_view"], key=key)
        columns = ("kind", "stock", "statement", "epistemic_class", "valid_from", "valid_to")
        shown_items = [dict(zip(columns, row, strict=True)) for row in memory_rows]
        for item in shown_items:
            item["valid_from"] = item["valid_from"].isoformat()
        assert shown_items == reader["promoted_memory_view"]
        for refusal in reader["refused"]:
            target = refusal["target"]
            for op in refusal["ops"]:
                write = _WRITES[op].format(target=target, column=_COLUMN[target])
                if target in views:
                    with pytest.raises(psycopg.Error) as refused, pool.connection() as conn:
                        conn.execute(write)
                    assert refused.value.sqlstate in _VIEW_REFUSALS, write
                else:
                    with pytest.raises(errors.InsufficientPrivilege), pool.connection() as conn:
                        conn.execute(write)
    assert table_counts(pg_db) == before

    # 5. No vault (V1).
    assert header["vault_in_scope"] is False and MANIFEST["vault"] == []
    assert [p.name for p in out.iterdir()] == [stock]
