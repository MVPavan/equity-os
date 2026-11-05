"""D7 Task 3 (eqos-3oq.3): watchlist decisions and the drafting gate (plan D7 R3, R6, R7).

``ADD``/``REMOVE`` are the owner's, with a ruling, on a stock admitted by a completed batch. The
runtime role drafts a version, or content into one, only for a watchlisted stock, and a stock's
first runtime version is its bootstrap thesis. The ``ledger`` fixture's stock is watchlisted
with a bootstrap draft; every other stock here starts with nothing.
"""

from __future__ import annotations

import threading
from typing import Any

import psycopg
import pytest
from coverage_support import SEED_RULING, batched, watchlist
from ledger_support import Ledger, ledger
from pg_evidence_schema_support import runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors

from equity_os.contracts.publication.ledger import (
    DeciderRole,
    DecisionKind,
    DecisionRecord,
    ReportKind,
    SubjectKind,
)
from equity_os.publication.approval import lifecycle
from equity_os.storage.database.settings import PgRole
from equity_os.storage.records import store

pytestmark = pytest.mark.pg
__all__ = ["ledger", "runtime", "seeded"]

W = SubjectKind.WATCHLIST
OFF = "is not on the watchlist"
_DIGEST = "SELECT eqos.watchlist_digest(%s)"
_SECTION = (
    "INSERT INTO eqos.report_sections (version_id, ordinal, section_key, body, sha256) "
    "VALUES (%(version)s, %(ordinal)s, %(key)s, %(key)s, "
    "encode(sha256(convert_to(%(key)s, 'UTF8')), 'hex'))"
)
_CLAIM = (
    "INSERT INTO eqos.numeric_claims (version_id, section_id, claim_key) "
    "SELECT version_id, min(id), 'late' FROM eqos.report_sections WHERE version_id = %s "
    "GROUP BY version_id"
)
_ENTITY = (
    "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, evidence_input_id) "
    "SELECT %s, market, %s, evidence_input_id FROM eqos.reporting_entities WHERE id = %s "
    "RETURNING id"
)


def stock(ledger: Ledger, key: str) -> int:
    """A new reporting entity with nothing: no onboarding record, batch or decision."""
    with ledger._cursor(PgRole.RUNTIME) as cursor:
        ((entity,),) = cursor.execute(_ENTITY, (key, key, ledger.entity_id)).fetchall()
    return int(entity)


def report(ledger: Ledger, entity_id: int, kind: ReportKind, role: PgRole = PgRole.RUNTIME) -> int:
    """A report header of ``kind`` for the stock."""
    with ledger._cursor(role) as cursor:
        return store.create_report(cursor, entity_id=entity_id, period="FY27_Q1", kind=kind)


def decide(ledger: Ledger, role: PgRole, entity_id: int, kind: DecisionKind) -> DecisionRecord:
    """A watchlist decision by ``role`` through the trigger only: the head and digest named, the
    decider never supplied."""
    return ledger.decide(
        role,
        entity_id,
        kind,
        subject_kind=W,
        sealed_digest=None,
        ruling=SEED_RULING if role is PgRole.OWNER else None,
    )


def section(ledger: Ledger, version_id: int, ordinal: int) -> None:
    """A runtime section appended to an existing version."""
    with ledger._cursor(PgRole.RUNTIME) as cursor:
        cursor.execute(_SECTION, {"version": version_id, "ordinal": ordinal, "key": f"s{ordinal}"})


def late_claim(ledger: Ledger, version_id: int) -> None:
    """A runtime claim appended to an existing version (refused at the gate, before any column
    check)."""
    with ledger._cursor(PgRole.RUNTIME) as cursor:
        cursor.execute(_CLAIM, (version_id,))


def test_the_owner_adds_with_a_ruling_and_nobody_else_does(ledger: Ledger) -> None:
    """The owner's ADD through ``store.insert_decision`` with no decider is stamped OWNER and
    sealed to the coverage digest; an empty ruling, the runtime and the panel are refused, for
    ADD and REMOVE; REMOVE then re-ADD is legal."""
    entity = stock(ledger, "ADDED")
    batched(ledger.pools, entity, ledger.snapshots)
    for role in (PgRole.RUNTIME, PgRole.PANEL):
        with pytest.raises(errors.InsufficientPrivilege):
            decide(ledger, role, entity, DecisionKind.ADD)
    with pytest.raises(errors.CheckViolation, match="verbatim ruling"):
        ledger.decide(PgRole.OWNER, entity, DecisionKind.ADD, subject_kind=W, ruling="")
    added = decide(ledger, PgRole.OWNER, entity, DecisionKind.ADD)
    with ledger._cursor(PgRole.RUNTIME) as cursor:
        ((digest,),) = cursor.execute(_DIGEST, (entity,)).fetchall()
    assert (added.decider, added.sealed_digest) == (DeciderRole.OWNER, digest)
    for role in (PgRole.RUNTIME, PgRole.PANEL):
        with pytest.raises(errors.InsufficientPrivilege):
            decide(ledger, role, entity, DecisionKind.REMOVE)
    with pytest.raises(errors.CheckViolation, match="illegal decision"):
        decide(ledger, PgRole.OWNER, entity, DecisionKind.ADD)
    decide(ledger, PgRole.OWNER, entity, DecisionKind.REMOVE)
    assert decide(ledger, PgRole.OWNER, entity, DecisionKind.ADD).sequence == 3


@pytest.mark.parametrize("coverage", ["nothing", "never-batched", "unfinished-batch"])
def test_an_uncovered_stock_cannot_be_added(ledger: Ledger, coverage: str) -> None:
    """No onboarding record, an onboarding record in no batch, or an admitted result in
    a batch with no completion: ``lifecycle.decide`` refuses before insert, the trigger at it."""
    entity = stock(ledger, coverage)
    if coverage == "unfinished-batch":
        batched(ledger.pools, entity, ledger.snapshots, complete=False)
    elif coverage == "never-batched":
        with ledger._cursor(PgRole.RUNTIME) as cursor:
            cursor.execute(
                "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, "
                "outcome, entity_id) VALUES ('NEVER', 'NSE_SYMBOL', 'PARTIAL', %s)",
                (entity,),
            )
    with pytest.raises(LookupError):
        lifecycle.decide(
            ledger.pools[PgRole.OWNER],
            subject_kind=W,
            subject_id=entity,
            kind=DecisionKind.ADD,
            ruling=SEED_RULING,
        )
    with pytest.raises(errors.CheckViolation, match="no admitted result"):
        decide(ledger, PgRole.OWNER, entity, DecisionKind.ADD)


def test_runtime_drafting_needs_the_watchlist(ledger: Ledger) -> None:
    """Off the watchlist the runtime drafts no version; content into a version drafted before
    REMOVE, or into a panel-created unsealed version, is refused after it; a draft runs at READ
    COMMITTED only."""
    entity = stock(ledger, "GATED")
    bootstrap = report(ledger, entity, ReportKind.BOOTSTRAP_THESIS)
    with pytest.raises(errors.CheckViolation, match=OFF):
        ledger.draft(bootstrap)
    watchlist(ledger.pools, entity, ledger.snapshots)
    drafted = ledger.draft(bootstrap)
    panel_report = report(ledger, entity, ReportKind.EARNINGS_UPDATE, PgRole.PANEL)
    with ledger._cursor(PgRole.PANEL) as cursor:
        unsealed = store.create_version(cursor, ledger.version_draft(panel_report))
    for version_id in (drafted, unsealed):
        section(ledger, version_id, 1)  # negative control: on the watchlist
    decide(ledger, PgRole.OWNER, entity, DecisionKind.REMOVE)
    for version_id in (drafted, unsealed):
        with pytest.raises(errors.CheckViolation, match=OFF):
            section(ledger, version_id, 2)
        with pytest.raises(errors.CheckViolation, match=OFF):
            late_claim(ledger, version_id)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        with pytest.raises(errors.CheckViolation, match="READ COMMITTED"), conn.transaction():
            store.create_version(conn.cursor(), ledger.version_draft(ledger.report()))


def test_a_new_members_first_version_is_its_bootstrap(ledger: Ledger) -> None:
    """A bootstrap header without a version does not count: the earnings update is refused
    until the bootstrap has a version; then it is accepted."""
    entity = stock(ledger, "FIRST")
    watchlist(ledger.pools, entity, ledger.snapshots)
    bootstrap = report(ledger, entity, ReportKind.BOOTSTRAP_THESIS)
    update = report(ledger, entity, ReportKind.EARNINGS_UPDATE)
    with pytest.raises(errors.CheckViolation, match="no bootstrap thesis version"):
        ledger.draft(update)
    ledger.draft(bootstrap)
    assert ledger.draft(update)


def test_a_panel_import_off_the_watchlist_is_accepted(ledger: Ledger) -> None:
    """Imports of sealed history run as the panel, outside the gate."""
    entity = stock(ledger, "IMPORTED")
    assert ledger.imported(report(ledger, entity, ReportKind.EARNINGS_UPDATE, PgRole.PANEL))


def test_a_draft_that_saw_add_loses_to_a_committing_remove(
    ledger: Ledger, pg_db: PgTestDatabase
) -> None:
    """The owner's REMOVE holds the WATCHLIST lock; a runtime draft that read the stock as
    watchlisted waits on it, then rereads after the commit and is refused."""
    draft = ledger.version_draft(ledger.report())
    outcome: list[Any] = []
    with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as drafter:
        assert drafter.execute("SELECT eqos.watchlisted(%s)", (ledger.entity_id,)).fetchone() == (
            True,
        )
        with ledger.pools[PgRole.OWNER].connection() as owner, owner.transaction():
            head = store.chain_head(owner.cursor(), W, ledger.entity_id)
            store.insert_decision(
                owner.cursor(),
                subject_kind=W,
                subject_id=ledger.entity_id,
                kind=DecisionKind.REMOVE,
                predecessor_id=None if head is None else head.id,
                ruling=SEED_RULING,
            )

            def race() -> None:
                try:
                    outcome.append(store.create_version(drafter.cursor(), draft))
                except psycopg.Error as refused:
                    outcome.append(refused)

            racer = threading.Thread(target=race)
            racer.start()
            racer.join(timeout=1)
            assert racer.is_alive()
        racer.join(timeout=20)
    assert len(outcome) == 1 and isinstance(outcome[0], errors.CheckViolation)
    assert OFF in str(outcome[0])
