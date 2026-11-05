"""D2.6: reconciliation, cutover and the frozen-window rollback (plan D2, Task 6).

Every case imports byte copies of the legacy store into an isolated ``eqos_test_*`` database
and approves its reconciliation report as the test fixture reviewer. The SQLite baseline JSON
is the oracle that rollback restores SQLite authority.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from legacy_support import (
    BASELINE_CUTOFFS,
    LEGACY_PATH,
    LEGACY_SHA256,
    baseline_rows,
    file_sha256,
    second_store,
)
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from test_fact_store_baseline import FIXTURE
from test_legacy_import import Rig, approve, edit_copy, unapprove
from test_store import _fact

from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_REFUSED
from equity_os.interface.entry.cli import main
from equity_os.storage.database.approvals import (
    GatedOperation,
    GateRefusal,
    GateRefusedError,
    split_approval,
)
from equity_os.storage.database.settings import ENV_PREFIX, PgRole
from equity_os.storage.database.test_databases import drop_test_database
from equity_os.storage.facts.cutover import (
    LEGAL_COMMANDS,
    FactStoreRequiredError,
    FactStoreState,
    TransitionRefusal,
    TransitionRefusedError,
    open_fact_store,
    reconcile,
    store_status,
    transition,
)
from equity_os.storage.facts.fact_store import FactStore
from equity_os.storage.facts.legacy_import import origin_id_for
from equity_os.storage.facts.pg_fact_store import FactStoreFrozenError, PgFactStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CUTOVER, REOPEN, ROLLBACK = GatedOperation.CUTOVER, GatedOperation.REOPEN, GatedOperation.ROLLBACK
MARKER = (
    "SELECT state, operation_id, last_row_handle, last_selection_handle, approval_sha256 "
    "FROM eqos.fact_store_events WHERE store_id = %s ORDER BY id DESC LIMIT 1"
)
COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.fact_rows), (SELECT count(*) FROM eqos.fact_selections), "
    "(SELECT count(*) FROM eqos.fact_store_events)"
)


def _never() -> ConnectionPool:
    raise AssertionError("routing without fact_store_id must not open a pool")


class Window:
    """A rig with the manifest's files imported and their reconciliation approved."""

    def __init__(self, rig: Rig, *files: tuple[str, Path]) -> None:
        rig.register()
        self.rig, self.manifest = rig, rig.manifest(*files)
        rig.run(self.manifest, rig.preflight(self.manifest))
        paths = [path for _, path in files] or [rig.legacy]
        self.stores = [origin_id_for(file_sha256(path)) for path in paths]
        with rig.pg_db.runtime_pool() as pool:
            report = reconcile(self.manifest, root=rig.tmp_path, pool=pool, settings=rig.settings)
        self.reconciled = report
        self.report = rig.tmp_path / "reconciliation.yaml"
        self.report.write_bytes(report.to_yaml())
        approve(self.report)

    def move(self, op: GatedOperation) -> UUID:
        """Run ``op`` on the whole store set under the approved report."""
        with self.rig.pg_db.runtime_pool() as pool:
            return transition(
                op,
                self.manifest,
                report_path=self.report,
                owner_path=None,
                pool=pool,
                settings=self.rig.settings,
                root=self.rig.tmp_path,
            )

    def states(self) -> dict[str, FactStoreState]:
        """Every store's state."""
        with self.rig.pg_db.runtime_pool() as pool:
            return dict(store_status(pool, self.stores))


@pytest.fixture
def rig(pg_db: PgTestDatabase, tmp_path: Path) -> Rig:
    """The shared seeded database and legacy copy."""
    return Rig(pg_db, tmp_path)


def _rewritten(old: bytes, new: bytes, *, reapprove: bool) -> Callable[[Window], object]:
    def case(window: Window) -> object:
        payload = unapprove(window.report).read_bytes()
        window.report.write_bytes(payload.replace(old, new, 1))
        return approve(window.report, None if reapprove else payload)

    return case


def _other_store_imported(window: Window) -> object:
    return window.rig.run(*window.rig.pair(("migrated", second_store(window.rig.tmp_path))))


REFUSALS: dict[str, tuple[GatedOperation, Callable[[Window], object], str]] = {
    "unapproved": (CUTOVER, lambda window: unapprove(window.report), GateRefusal.UNAPPROVED),
    "wrong-payload-hash": (
        CUTOVER,
        lambda window: approve(unapprove(window.report), b"another payload"),
        GateRefusal.PAYLOAD_MISMATCH,
    ),
    "approval-names-another-test-database": (
        CUTOVER,
        _rewritten(b"name: eqos_test_", b"name: eqos_test_x", reapprove=True),
        GateRefusal.WRONG_DATABASE,
    ),
    "report-edited-after-approval": (
        CUTOVER,
        _rewritten(b"rows: 43", b"rows: 42", reapprove=False),
        GateRefusal.PAYLOAD_MISMATCH,
    ),
    "row-imported-into-another-store-after-approval": (
        CUTOVER,
        _other_store_imported,
        GateRefusal.APPROVAL_STALE,
    ),
    "rollback-from-imported": (ROLLBACK, lambda window: None, TransitionRefusal.ILLEGAL_STATE),
    "reopen-from-imported": (REOPEN, lambda window: None, TransitionRefusal.ILLEGAL_STATE),
}


@pytest.mark.parametrize("name", list(REFUSALS))
def test_refused_transitions_switch_nothing(rig: Rig, name: str) -> None:
    """Each gate and state refusal names its reason and leaves the store ``IMPORTED``."""
    op, arrange, reason = REFUSALS[name]
    window = Window(rig)
    arrange(window)
    before = rig.query(COUNTS)
    with pytest.raises((GateRefusedError, TransitionRefusedError)) as refused:
        window.move(op)
    assert refused.value.reason == reason
    assert rig.query(COUNTS) == before
    assert window.states() == {window.stores[0]: FactStoreState.IMPORTED}


def test_frozen_write_is_refused_then_rollback_restores_sqlite_authority(rig: Rig) -> None:
    """The marker records the approval and last handles; a frozen write persists nothing and
    succeeds on the store routed after rollback (refused with no SQLite path); the SQLite write
    then blocks re-cutover."""
    window = Window(rig)
    store = window.stores[0]
    # Before the first knowledge time, before the first selection, median, last selection.
    assert [check.rows for check in window.reconciled.stores[0].cutoffs] == [0, 0, 12, 24]
    operation = window.move(CUTOVER)
    approval = split_approval(window.report.read_bytes())[1]
    assert approval is not None
    marker = ("CUTOVER_FROZEN", operation, 43, 24, approval.payload_sha256)
    assert rig.query(MARKER, store) == [marker]
    counts = rig.query(COUNTS)
    with rig.pg_db.runtime_pool() as pool:
        with pytest.raises(FactStoreFrozenError):
            open_fact_store(store, str(rig.legacy), pool_factory=lambda: pool)
        stale = PgFactStore(pool, store)
        with pytest.raises(FactStoreFrozenError):
            stale.put(_fact())
        assert rig.query(COUNTS) == counts

        window.move(ROLLBACK)
        assert window.states() == {store: FactStoreState.ROLLED_BACK}
        with pytest.raises(FactStoreRequiredError):
            open_fact_store(store, None, pool_factory=lambda: pool)
        routed = open_fact_store(store, str(rig.legacy), pool_factory=lambda: pool)
        assert isinstance(routed, FactStore)
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["cutoffs"]
        assert {c.isoformat(): baseline_rows(routed, c) for c in BASELINE_CUTOFFS} == expected
        assert routed.put(_fact()).row_id == 44
        routed.close()
        with pytest.raises(FactStoreFrozenError):
            stale.put(_fact())
    with pytest.raises(TransitionRefusedError) as refused:
        window.move(CUTOVER)
    assert refused.value.reason == TransitionRefusal.FINGERPRINT_CHANGED
    assert window.states() == {store: FactStoreState.ROLLED_BACK}
    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256


def test_a_failed_rollback_switches_no_store(rig: Rig, tmp_path: Path) -> None:
    """One changed fingerprint across two stores refuses rollback for both."""
    second = second_store(tmp_path)
    window = Window(rig, ("aparinds", rig.legacy), ("aparinds-migrated", second))
    window.move(CUTOVER)
    edit_copy(second, "PRAGMA user_version = 7")
    with pytest.raises(TransitionRefusedError) as refused:
        window.move(ROLLBACK)
    assert refused.value.reason == TransitionRefusal.FINGERPRINT_CHANGED
    assert window.states() == dict.fromkeys(window.stores, FactStoreState.CUTOVER_FROZEN)


BEYOND = {
    "row": (
        "INSERT INTO eqos.fact_rows SELECT target_store, handle + 1, origin, origin_id + 1, "
        "content_identity, 'beyond', revision_family, revision_ordinal + 1000, canonical_status, "
        "canonical_selected_at, canonical_reason, source_id, file_sha256, anchor, "
        "valid_time_start, valid_time_end, knowledge_time, first_seen_time, fact_json, created_at "
        "FROM eqos.fact_rows WHERE target_store = %s ORDER BY handle DESC LIMIT 1"
    ),
    "selection": (
        "INSERT INTO eqos.fact_selections SELECT target_store, handle + 1, origin, origin_id + 1, "
        "content_identity, row_handle, sequence + 1, handle, 'beyond', reason, false, "
        "synthesized, selection_sha256 FROM eqos.fact_selections WHERE target_store = %s "
        "ORDER BY handle DESC LIMIT 1"
    ),
}


@pytest.mark.parametrize("kind", list(BEYOND))
def test_rollback_refuses_rows_beyond_the_marker(rig: Rig, tmp_path: Path, kind: str) -> None:
    """A row or selection written past one store's cutover marker refuses rollback for all."""
    second = second_store(tmp_path)
    window = Window(rig, ("aparinds", rig.legacy), ("aparinds-migrated", second))
    window.move(CUTOVER)
    admin = rig.settings.conninfo(PgRole.ADMIN, dbname=rig.pg_db.dbname)
    with psycopg.connect(admin) as conn:
        conn.execute(BEYOND[kind], (window.stores[1],))
    before = rig.query(COUNTS)
    with pytest.raises(TransitionRefusedError) as refused:
        window.move(ROLLBACK)
    assert refused.value.reason == TransitionRefusal.ROWS_BEYOND_MARKER
    assert rig.query(COUNTS) == before
    assert window.states() == dict.fromkeys(window.stores, FactStoreState.CUTOVER_FROZEN)


@pytest.mark.parametrize("op", [REOPEN, ROLLBACK])
def test_reopen_and_rollback_need_the_whole_sets_cutover_report(
    rig: Rig, tmp_path: Path, op: GatedOperation
) -> None:
    """Another approved payload on the same database, or a subset manifest, switches nothing."""
    second = second_store(tmp_path)
    window = Window(rig, ("aparinds", rig.legacy), ("aparinds-migrated", second))
    window.move(CUTOVER)
    subset = rig.manifest(("aparinds", rig.legacy))
    for manifest, report in (
        (window.manifest, rig.preflight(window.manifest)),
        (subset, window.report),
    ):
        with rig.pg_db.runtime_pool() as pool, pytest.raises(TransitionRefusedError) as refused:
            transition(
                op,
                manifest,
                report_path=report,
                owner_path=None,
                pool=pool,
                settings=rig.settings,
                root=rig.tmp_path,
            )
        assert refused.value.reason == TransitionRefusal.NOT_THE_CUTOVER_REPORT
    assert window.states() == dict.fromkeys(window.stores, FactStoreState.CUTOVER_FROZEN)
    window.move(op)


def test_cli_reopen_closes_the_window_and_reconcile_ignores_native_writes(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the CLI: cutover, status with legal commands, reopen (idempotent), rollback
    refused; native writes route to PostgreSQL and leave the report's bytes unchanged."""
    window = Window(rig)
    store = window.stores[0]
    for name, value in rig.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(rig.tmp_path)
    manifest = ["--manifest", str(window.manifest)]
    flags = [*manifest, "--report", str(window.report)]
    assert main(["legacy", "cutover", *flags]) == 0
    capsys.readouterr()
    assert main(["legacy", "status", *manifest]) == 0
    commands = LEGAL_COMMANDS[FactStoreState.CUTOVER_FROZEN]
    assert capsys.readouterr().out == f"aparinds\t{store}\tCUTOVER_FROZEN\t{commands}\n"
    assert main(["legacy", "reopen", *flags]) == 0
    reopened = capsys.readouterr().out.split("\t")[1].strip()
    assert str(window.move(REOPEN)) == reopened
    assert main(["legacy", "rollback", *flags]) == EXIT_REFUSED
    with pytest.raises(TransitionRefusedError) as refused:
        window.move(ROLLBACK)
    assert refused.value.reason == TransitionRefusal.ROLLBACK_WINDOW_CLOSED

    with rig.pg_db.runtime_pool() as pool:
        routed = open_fact_store(store, str(rig.legacy), pool_factory=lambda: pool)
        assert isinstance(routed, PgFactStore)
        assert routed.select_canonical(routed.put(_fact()).row_id, "native").row_id == 44
    sqlite = open_fact_store(None, str(rig.tmp_path / "facts.db"), pool_factory=_never)
    assert isinstance(sqlite, FactStore)
    sqlite.close()
    with pytest.raises(FactStoreRequiredError):
        open_fact_store(None, None, pool_factory=_never)
    after = rig.tmp_path / "after.yaml"
    assert main(["legacy", "reconcile", *manifest, "--out", str(after)]) == 0
    assert after.read_bytes() == split_approval(window.report.read_bytes())[0]


def test_cli_create_test_database(
    pg_template: PgTestDatabase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``db create-test`` mints a guarded, reachable ``eqos_test_<suffix>_<hex>`` database."""
    for name, value in pg_template.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(f"{ENV_PREFIX}DB", "eqos_cli_main")
    assert main(["db", "create-test", "--suffix", "t6"]) == 0
    name = capsys.readouterr().out.strip()
    try:
        assert re.fullmatch(r"eqos_test_t6_[0-9a-f]{12}", name)
        conninfo = pg_template.settings.conninfo(PgRole.RUNTIME, dbname=name)
        with psycopg.connect(conninfo) as conn:
            assert conn.execute("SELECT current_database()").fetchone() == (name,)
    finally:
        drop_test_database(pg_template.settings, name)
