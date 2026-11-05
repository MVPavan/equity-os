"""D4.1 acceptance: memory items and supports are append-only, sealed, staged with at least one
support, and decided only by the panel or the owner through the D3 chain; no comparator or
claim-check module can reach ``fundamentals.memory`` (plan D4, M1, M2, M7).

Every database case runs on its own ``eqos_test_*`` database through the real role logins; the
triggers are authoritative, so each refusal is provoked by a direct insert or the stager, never
by a Python pre-check.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from ledger_support import MEMORY_TABLES, RULING, ledger
from memory_support import Memory, memory
from moved_support import OLD_PACKAGES
from pg_evidence_schema_support import _update_column, runtime, seeded
from pg_support import MIGRATIONS_DIR, REPO_ROOT, PgTestDatabase
from psycopg import errors, sql

from equity_os.contracts.publication.ledger import DecisionKind, PanelReview, SubjectKind, Verdict
from equity_os.contracts.storage.memory import MemoryKind, SupportDraft, SupportTarget
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.interface.entry.cli import main
from equity_os.storage.database.settings import PgRole
from equity_os.storage.memory.pg_store import MemoryStageConflictError
from equity_os.storage.records import store

__all__ = ["ledger", "memory", "runtime", "seeded"]

PROMOTE, REJECT, RETIRE = (
    DecisionKind.PROMOTE,
    DecisionKind.REJECT_CANDIDATE,
    DecisionKind.RETIRE,
)
PANEL, OWNER, RUNTIME = PgRole.PANEL, PgRole.OWNER, PgRole.RUNTIME
ILLEGAL = "illegal decision"
# A second item's statement: identical columns stage the same item (0041's natural key).
OTHER = "Railway wires grew their share of consolidated revenue"
pg = pytest.mark.pg


# --- Import graph (eqos-4hi.1): the comparator and report checks never read memory

SRC = REPO_ROOT
BARRED = "equity_os.storage.memory"
CLAIM_CHECK_ROOTS = (
    "equity_os.publication.checking.claim_check",
    "equity_os.publication.checking.citations",
    "equity_os.publication.checking.numeral_scan",
    "equity_os.publication.approval.lifecycle",
)


def _module_file(root: Path, name: str) -> Path | None:
    """The source file of a module or package under ``root``, if it has one there."""
    path = root.joinpath(*name.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imports(root: Path, name: str, path: Path) -> set[str]:
    """Every module one file imports: ``import a.b``, ``from a import b`` (and ``a.b`` when it
    is a module file) and relative imports resolved against the file's package."""
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*parts, *([node.module] if node.module else [])])
            else:
                base = node.module or ""
            found.add(base)
            found.update(
                f"{base}.{alias.name}"
                for alias in node.names
                if _module_file(root, f"{base}.{alias.name}")
            )
    return found


def barred_reached(root: Path, seeds: list[str]) -> set[str]:
    """The barred modules reached from ``seeds`` by following imports (and each module's parent
    packages, which importing it runs) transitively within ``root``."""
    seen: set[str] = set()
    todo = list(seeds)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        todo.extend(".".join(parts[:end]) for end in range(1, len(parts)))
        path = _module_file(root, name)
        if path is not None:
            todo.extend(_imports(root, name, path))
    return {name for name in seen if name == BARRED or name.startswith(BARRED + ".")}


def test_no_comparator_or_claim_check_module_reaches_memory() -> None:
    """Every module under ``compare/`` and the claim-check roots import nothing under
    ``fundamentals.memory``, directly or through any module they reach."""
    seeds = list(OLD_PACKAGES["compare"])
    assert len(seeds) > 5 and (SRC / "equity_os/storage/memory/store.py").is_file()
    assert barred_reached(SRC, [*seeds, *CLAIM_CHECK_ROOTS]) == set()


@pytest.mark.parametrize(
    ("statement", "barred"),
    [
        ("import equity_os.storage.memory.store", "equity_os.storage.memory.store"),
        ("from equity_os.storage import memory", "equity_os.storage.memory"),
        ("from equity_os.storage.memory import store", "equity_os.storage.memory.store"),
        ("from .. import memory", "equity_os.storage.memory"),
        ("import os", None),
    ],
)
def test_the_walker_flags_each_import_form_through_an_intermediate(
    tmp_path: Path, statement: str, barred: str | None
) -> None:
    """A seed importing an intermediate module that imports memory in any form is flagged; an
    intermediate importing nothing barred is not, so the walker cannot pass vacuously."""
    files = {
        "equity_os/__init__.py": "",
        "equity_os/storage/__init__.py": "",
        "equity_os/storage/memory/__init__.py": "",
        "equity_os/storage/memory/store.py": "",
        "equity_os/storage/sub/__init__.py": "",
        "equity_os/storage/sub/mid.py": statement,
        "equity_os/seed.py": "from equity_os.storage.sub import mid",
    }
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    found = barred_reached(tmp_path, ["equity_os.seed"])
    assert barred in found if barred else found == set()


# --- Staging and the seal (M1)


def _support(memory: Memory, item_id: int, column: str, target_id: int) -> None:
    """A raw runtime support insert in its own transaction."""
    statement = sql.SQL("INSERT INTO eqos.memory_supports (item_id, {}) VALUES (%s, %s)").format(
        sql.Identifier(column)
    )
    with memory.ledger._cursor(RUNTIME) as cursor:
        cursor.execute(statement, (item_id, target_id))


@pg
def test_an_item_without_support_is_refused_at_commit(memory: Memory) -> None:
    """The stager adds no pre-check: the deferred trigger refuses the supportless item."""
    with pytest.raises(errors.CheckViolation, match="has no support"):
        memory.stage(supports=())
    assert memory.one("SELECT count(*) FROM eqos.memory_items") == 0
    item = memory.stage()
    assert memory.rows(
        "SELECT version_id, claim_id FROM eqos.memory_supports WHERE item_id = %s", item
    ) == [(memory.version_id, None)]


@pg
def test_a_support_after_its_items_transaction_is_refused(memory: Memory) -> None:
    """A support added in a later transaction, before and after the owner rejects the
    candidate, is refused: supports are sealed with their item."""
    item = memory.stage()
    with pytest.raises(errors.CheckViolation, match="sealed with the item"):
        _support(memory, item, "claim_id", memory.claim_id)
    memory.decide(OWNER, item, REJECT)
    with pytest.raises(errors.CheckViolation, match="sealed with the item"):
        _support(memory, item, "claim_id", memory.claim_id)
    assert memory.one("SELECT count(*) FROM eqos.memory_supports") == 1


@pg
def test_one_item_cites_a_target_once(memory: Memory) -> None:
    """The same claim cited twice by one item is refused; one citation of each target is not."""
    claim = SupportDraft(target=SupportTarget.CLAIM, target_id=memory.claim_id)
    with pytest.raises(errors.UniqueViolation):
        memory.stage(supports=(claim, claim))
    version = SupportDraft(target=SupportTarget.VERSION, target_id=memory.version_id)
    memory.stage(supports=(claim, version))


@pg
@pytest.mark.parametrize("after", ["staged", "promoted", "rejected", "retired", "invalidated"])
def test_a_retry_returns_the_staged_item_and_writes_nothing(memory: Memory, after: str) -> None:
    """eqos-4j2.20: restaging an item's columns and supports returns its id whatever its
    lifecycle, leaving every row and its status unchanged (a terminal item stays terminal); the
    same columns with other supports are a conflict."""
    item = memory.stage()
    if after != "staged":
        memory.decide(OWNER, item, REJECT if after == "rejected" else PROMOTE)
    if after == "retired":
        memory.decide(OWNER, item, RETIRE)
    if after == "invalidated":
        with memory.ledger._cursor(OWNER) as cursor:
            memory.writer("withdraw", memory.version_id)(cursor)
    status, rows = memory.status(item), memory.snapshot()
    assert memory.stage() == item
    claim = SupportDraft(target=SupportTarget.CLAIM, target_id=memory.claim_id)
    with pytest.raises(MemoryStageConflictError, match=f"memory item {item} "):
        memory.stage(supports=(claim,))
    assert (memory.status(item), memory.snapshot()) == (status, rows)


@pg
def test_ledger_stage_prints_one_id_per_item_and_refuses_a_conflict(
    memory: Memory,
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``ledger stage <item.yaml>`` stages as the runtime; a retry prints the same id; the same
    columns with other supports exit refused and write nothing."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    path = tmp_path / "item.yaml"

    def stage(**update: Any) -> int:
        path.write_text(yaml.safe_dump(memory.draft(**update).model_dump(mode="json")))
        return main(["ledger", "stage", str(path)])

    assert stage() == EXIT_OK
    printed = capsys.readouterr().out
    assert printed.startswith("memory item ")
    assert stage() == EXIT_OK
    assert capsys.readouterr().out == printed
    rows = memory.snapshot()
    claim = SupportDraft(target=SupportTarget.CLAIM, target_id=memory.claim_id)
    assert stage(supports=(claim,)) == EXIT_REFUSED
    assert memory.snapshot() == rows


@pg
def test_0041_refuses_existing_duplicates_with_their_ids(
    memory: Memory, pg_db: PgTestDatabase
) -> None:
    """Migration 0041 lists each duplicate key group's ids and deletes nothing."""
    with pg_db.migrator_connection() as conn:
        conn.execute("DROP INDEX eqos.memory_items_natural_key")
    first, second = memory.stage(), memory.stage()
    assert first != second
    rows = memory.snapshot()
    migration = (MIGRATIONS_DIR / "0041_memory_natural_key.sql").read_text(encoding="utf-8")
    with pg_db.migrator_connection() as conn, pytest.raises(errors.UniqueViolation) as refused:
        conn.execute(migration.encode())
    assert f"{first}, {second}" in str(refused.value)
    assert memory.snapshot() == rows


@pg
@pytest.mark.parametrize("across", ["stock", "kind", None])
def test_a_supersession_across_stock_or_kind_is_refused(memory: Memory, across: str | None) -> None:
    """A correction supersedes an item of the same stock and kind only."""
    other = memory.one(
        "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, "
        "evidence_input_id) SELECT 'OTHER', market, 'Other Ltd', evidence_input_id "
        "FROM eqos.reporting_entities WHERE id = %s RETURNING id",
        memory.ledger.entity_id,
    )
    earlier = memory.stage()
    if across is None:
        later = memory.stage(supersedes_item_id=earlier)
        query = "SELECT supersedes_item_id FROM eqos.memory_items WHERE id = %s"
        assert memory.one(query, later) == earlier
        return
    update = {"entity_id": other} if across == "stock" else {"kind": MemoryKind.THESIS_AND_WARNING}
    with pytest.raises(errors.CheckViolation, match="across stock or kind"):
        memory.stage(supersedes_item_id=earlier, **update)


@pg
def test_memory_rows_are_append_only(memory: Memory, pg_db: PgTestDatabase) -> None:
    """The runtime may not update or delete either table, the trigger refuses even the table
    owner, and the runtime may not decide a memory item."""
    item = memory.stage()
    statements = ("UPDATE {0} SET {1} = {1}", "DELETE FROM {0}")
    with (
        memory.ledger.pools[RUNTIME].connection() as conn,
        pg_db.migrator_connection() as migrator,
    ):
        for table in sorted(MEMORY_TABLES):
            column = sql.Identifier(_update_column(conn, table))
            target = sql.Identifier("eqos", table)
            for statement in statements:
                query = sql.SQL(statement).format(target, column)
                with pytest.raises(errors.InsufficientPrivilege), conn.transaction():
                    conn.execute(query)
            for statement in (*statements, "TRUNCATE {0} CASCADE"):
                with pytest.raises(errors.RaiseException, match="immutable"):
                    migrator.execute(sql.SQL(statement).format(target, column))
    for kind in (PROMOTE, REJECT, RETIRE):
        with pytest.raises(errors.InsufficientPrivilege, match="may not decide"):
            memory.decide(RUNTIME, item, kind)


# --- Decisions (M2)


def _review(memory: Memory, item_id: int, verdict: Verdict, kind: DecisionKind) -> None:
    """A panel transaction, as ``panel.review`` orders it: the queue lock, a review of the item
    and the decision naming it."""
    with memory.ledger._cursor(PANEL) as cursor:
        cursor.execute("SELECT eqos.lock_queue()")
        digest = store.subject_digest(cursor, SubjectKind.MEMORY_ITEM, item_id)
        review = store.insert_panel_review(
            cursor,
            PanelReview(
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=item_id,
                sealed_digest=digest,
                provider="fake",
                model="model-1",
                effort="fixture-effort",
                brief_version="b1",
                verdict=verdict,
                rationale="fixture rationale",
            ),
        )
        store.insert_decision(
            cursor,
            subject_kind=SubjectKind.MEMORY_ITEM,
            subject_id=item_id,
            kind=kind,
            predecessor_id=None,
            sealed_digest=digest,
            panel_review_id=review,
        )


@pg
def test_a_panel_decision_needs_its_own_review(memory: Memory) -> None:
    """Without a review the panel's decision is refused; a review binds only the decision its
    verdict maps to (APPROVE → PROMOTE, REJECT → REJECT_CANDIDATE)."""
    item, other = memory.stage(), memory.stage(statement=OTHER)
    with pytest.raises(errors.CheckViolation, match="needs a panel review"):
        memory.decide(PANEL, item, PROMOTE)
    with pytest.raises(errors.CheckViolation, match="does not bind"):
        _review(memory, item, Verdict.APPROVE, REJECT)
    with pytest.raises(errors.CheckViolation, match="does not bind"):
        _review(memory, item, Verdict.REQUEST_CHANGES, PROMOTE)
    _review(memory, item, Verdict.APPROVE, PROMOTE)
    _review(memory, other, Verdict.REJECT, REJECT)
    assert memory.rows(
        "SELECT subject_id, kind, decider FROM eqos.decisions "
        "WHERE subject_kind = 'MEMORY_ITEM' ORDER BY id"
    ) == [(item, "PROMOTE", "PANEL"), (other, "REJECT_CANDIDATE", "PANEL")]


@pg
@pytest.mark.parametrize("kind", [REJECT, PROMOTE])
@pytest.mark.parametrize("digest", ["staged", "zeros", None])
def test_a_decision_on_a_missing_or_future_item_is_refused(
    memory: Memory, kind: DecisionKind, digest: str | None
) -> None:
    """An owner decision naming a nonexistent subject id, or the id the next item will take, is
    refused with any digest, null included; once that item exists it can be decided."""
    staged = memory.stage()
    supplied = {
        "staged": memory.one("SELECT eqos.memory_sealed_digest(%s)", staged),
        "zeros": "0" * 64,
        None: None,
    }[digest]
    future = staged + 1
    for subject in (0, future):
        with (
            pytest.raises(errors.CheckViolation, match=ILLEGAL),
            memory.ledger._cursor(OWNER) as cursor,
        ):
            store.insert_decision(
                cursor,
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=subject,
                kind=kind,
                predecessor_id=None,
                sealed_digest=supplied,
                ruling=RULING,
            )
    assert memory.stage(statement=OTHER) == future
    assert memory.decide(OWNER, future, kind).subject_id == future


@pg
def test_memory_decisions_follow_their_chain(memory: Memory) -> None:
    """Owner PROMOTE needs a ruling, the current head and the item's own digest; nothing but an
    owner RETIRE follows it; nothing follows RETIRE or REJECT_CANDIDATE."""
    item, rejected = memory.stage(), memory.stage(statement=OTHER)
    with pytest.raises(errors.CheckViolation, match="ruling"):
        memory.decide(OWNER, item, PROMOTE, ruling=None)
    with pytest.raises(errors.CheckViolation, match="digest"):
        memory.decide(OWNER, item, PROMOTE, sealed_digest="0" * 64)
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        memory.decide(OWNER, item, RETIRE)
    promoted = memory.decide(OWNER, item, PROMOTE)
    assert (promoted.sequence, promoted.decider) == (1, "OWNER")
    with pytest.raises(errors.CheckViolation, match="stale head"):
        memory.decide(OWNER, item, RETIRE, predecessor_id=None)
    for role, kind in ((OWNER, PROMOTE), (OWNER, REJECT), (PANEL, RETIRE)):
        with pytest.raises(errors.CheckViolation, match=ILLEGAL):
            memory.decide(role, item, kind)
    memory.decide(OWNER, item, RETIRE)
    memory.decide(OWNER, rejected, REJECT)
    for subject in (item, rejected):
        for kind in (PROMOTE, REJECT, RETIRE):
            with pytest.raises(errors.CheckViolation, match=ILLEGAL):
                memory.decide(OWNER, subject, kind)


@pg
def test_a_successor_promotes_only_over_a_promoted_predecessor(memory: Memory) -> None:
    """A correction's PROMOTE needs its predecessor PROMOTED with no promoted successor; once
    it is promoted the predecessor is retired by it, so the owner cannot retire it again and a
    second successor cannot promote."""
    earlier = memory.stage()
    first, second = (
        memory.stage(supersedes_item_id=earlier),
        memory.stage(supersedes_item_id=earlier, statement=OTHER),
    )
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        memory.decide(OWNER, first, PROMOTE)
    memory.decide(OWNER, earlier, PROMOTE)
    memory.decide(OWNER, first, PROMOTE)
    for subject, kind in ((earlier, RETIRE), (second, PROMOTE)):
        with pytest.raises(errors.CheckViolation, match=ILLEGAL):
            memory.decide(OWNER, subject, kind)
    memory.decide(OWNER, first, RETIRE)


@pg
def test_promote_runs_at_read_committed_only(memory: Memory) -> None:
    """A PROMOTE at REPEATABLE READ or SERIALIZABLE is refused (M4, amendment A1)."""
    item = memory.stage()
    for level in (b"REPEATABLE READ", b"SERIALIZABLE"):
        with (
            pytest.raises(errors.CheckViolation, match="READ COMMITTED"),
            memory.ledger._cursor(OWNER) as cursor,
        ):
            cursor.execute(b"SET TRANSACTION ISOLATION LEVEL " + level)
            store.insert_decision(
                cursor,
                subject_kind=SubjectKind.MEMORY_ITEM,
                subject_id=item,
                kind=PROMOTE,
                predecessor_id=None,
                sealed_digest=store.subject_digest(cursor, SubjectKind.MEMORY_ITEM, item),
                ruling=RULING,
            )
    assert memory.decide(OWNER, item, PROMOTE).kind is PROMOTE


@pg
def test_a_stale_snapshot_cannot_retire_an_item_its_successor_retired(memory: Memory) -> None:
    """M2: an owner transaction whose REPEATABLE READ snapshot predates a successor's PROMOTE
    cannot RETIRE the predecessor that PROMOTE already retired; every memory decision runs at
    READ COMMITTED."""
    earlier = memory.stage()
    promotion = memory.decide(OWNER, earlier, PROMOTE)
    correction = memory.stage(supersedes_item_id=earlier)
    with (
        pytest.raises(errors.CheckViolation, match="READ COMMITTED"),
        memory.ledger._cursor(OWNER) as cursor,
    ):
        cursor.execute(b"SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        digest = store.subject_digest(cursor, SubjectKind.MEMORY_ITEM, earlier)
        memory.decide(OWNER, correction, PROMOTE)
        store.insert_decision(
            cursor,
            subject_kind=SubjectKind.MEMORY_ITEM,
            subject_id=earlier,
            kind=RETIRE,
            predecessor_id=promotion.id,
            sealed_digest=digest,
            ruling=RULING,
        )
    assert memory.one("SELECT count(*) FROM eqos.decisions WHERE kind = 'RETIRE'") == 0
