"""D9 phase-end fixes F10-F12, F16: expired originals reach readers as ``OriginalExpiredError``
(plan D9 RP7, R13), and registration reads the store clock on its own connection.

Captures are SYNTHETIC bytes in ``tmp_path`` unless a case names the Apar fixtures. Reader cases
SEED the ``EXPIRED`` state directly where the bytes do not matter to the refusal.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from purge_support import PDF, XBRL, Env, env
from retention_support import dispose
from stage1_e2e_support import RUNS, SCREENER, Stage

from fundamentals.api import onboard_cli
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.retention_purge import FetchFailure, FetchFailureCategory
from fundamentals.contracts.snapshot import MissingSnapshotError
from fundamentals.contracts.source_catalog import BUILTIN_SOURCES, NSE_MASTER
from fundamentals.entity.discovery import Capture, Request, Response, store_captures
from fundamentals.evidence.capture_retention import read_retained
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.citations import resolve_location
from fundamentals.pg.retention_io import init_authority
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg

__all__ = ["env"]

SEED_STATE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, %s)"
UNDISPOSED = (
    "SELECT id FROM eqos.queue_items q WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.queue_dispositions d WHERE d.item_id = q.id)"
)
VENDOR_INTERPRETATIONS = (
    "SELECT id FROM eqos.interpretations WHERE eqos.is_vendor_source("
    "(SELECT source_id FROM eqos.capture_refs WHERE id = capture_ref_id))"
)
# Traces with a vendor interpretation operand; a trace without one nesting a child trace.
DIRECT = (
    "SELECT DISTINCT calculation_trace_id FROM eqos.calculation_trace_operands "
    f"WHERE interpretation_id IN ({VENDOR_INTERPRETATIONS}) ORDER BY 1"
)
NESTING = (
    "SELECT calculation_trace_id FROM eqos.calculation_trace_operands WHERE operand_trace_id "
    f"IS NOT NULL AND calculation_trace_id NOT IN ({DIRECT}) ORDER BY 1 LIMIT 1"
)


def test_an_expired_quoted_capture_is_refused_not_unresolved(env: Env) -> None:
    """F12 (RP7): resolving a quote location on an expired first-party PDF capture raises
    ``OriginalExpiredError`` naming it, instead of reading as an unresolved citation."""
    ref = env.capture(b"%PDF-1.4 synthetic", ("bse-results-pdf", PDF))
    with env.db.migrator_connection() as conn:
        conn.execute(SEED_STATE, (ref.capture_ref_id, "EXPIRED"))
    snapshots = env.store
    with env.pool.connection() as conn, conn.cursor() as cursor:
        with pytest.raises(OriginalExpiredError, match=f"capture {ref.capture_ref_id} is EXPIRED"):
            resolve_location(
                cursor,
                str(ref.capture_ref_id),
                "p1.b0.0:2",
                catalog=BUILTIN_SOURCES,
                snapshots=snapshots,
            )


def test_a_purge_racing_a_retained_read_is_expiry_not_corruption(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F12 (RP7): a purge expiring the capture between the state check and the byte read makes
    the read ``OriginalExpiredError``; the body vanished by policy, not by corruption."""
    ref = env.capture(b"f12-race", XBRL)

    def purged_meanwhile(store: SnapshotStore, *identity: str) -> Any:
        with env.db.migrator_connection() as conn:
            conn.execute(SEED_STATE, (ref.capture_ref_id, "EXPIRED"))
        raise MissingSnapshotError("body unlinked by a purge")

    monkeypatch.setattr(SnapshotStore, "read_capture_verified", purged_meanwhile)
    with pytest.raises(OriginalExpiredError, match="ORIGINAL_EXPIRED"):
        read_retained(env.pool, env.store, ref)


def over(repository: EvidenceRepository, nesting: int, child: int) -> int:
    """SYNTHETIC: a copy of the ``nesting`` trace whose child is ``child``, stored."""
    (stored,) = repository.get_calculation_traces([nesting])
    operands = tuple(
        o if o.operand_trace_id is None else o.model_copy(update={"operand_trace_id": child})
        for o in stored.trace.operands
    )
    assert child not in {o.operand_trace_id for o in stored.trace.operands}
    return repository.put_calculation_trace(stored.trace.model_copy(update={"operands": operands}))


def offline(url: str) -> bytes:
    """A fetcher whose every address is unreachable: exchange captures halt, vendors expire."""
    raise FetchFailure(FetchFailureCategory.CONNECTION)


@pytest.mark.retained
def test_a_tombstoned_trace_is_expired_not_a_provenance_mismatch(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """F10 (R13): after a purge tombstones the Screener capture, reading a trace over its
    interpretations (directly, or only through a child trace) raises ``OriginalExpiredError``
    before the trace is decoded and its content digest checked."""
    with pg_db.runtime_pool() as pool, pg_db.owner_pool() as owner:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        env = Env(pg_db, pool, tmp_path)
        env.root = tmp_path / "staged"  # where the harness stages Screener
        env.store = SnapshotStore(env.root)
        init_authority(env.sets)
        stage.first_party()
        stage.vendor("/".join(SCREENER), "A-SCR")
        stage.execute(vendors=["/".join(SCREENER)])
        with owner.connection() as conn:
            for (item,) in env.sql(UNDISPOSED):
                dispose(conn, item)
        direct = env.sql(DIRECT)[0][0]
        transitive = over(stage.repository, env.sql(NESTING)[0][0], direct)
        env.age()
        env.purge(offline, final=False)
        for trace in (direct, transitive):
            with pytest.raises(OriginalExpiredError, match="ORIGINAL_EXPIRED"):
                stage.repository.get_calculation_traces([trace])


def one_connection_pool(pg_db: PgTestDatabase) -> ConnectionPool:
    """A valid runtime pool of exactly one connection, failing fast on a second checkout."""
    return ConnectionPool(
        pg_db.conninfo(PgRole.RUNTIME), min_size=1, max_size=1, timeout=3, open=True
    )


def test_discovery_registration_needs_one_connection(pg_db: PgTestDatabase, tmp_path: Path) -> None:
    """F11: registering a discovery capture reads the store clock on the registration's own
    connection, so a one-connection pool completes."""
    body = b"SYMBOL,NAME OF COMPANY\nSYN,Synthetic Ltd\n"
    request = Request(
        unit=VerificationUnit.EXCHANGE,
        source_id=NSE_MASTER[0],
        surface=NSE_MASTER[1],
        url="https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    )
    response = Response(outcome="OK", body=body, retrieved_at=datetime(2026, 10, 1, tzinfo=UTC))
    with one_connection_pool(pg_db) as pool:
        store = SnapshotStore(tmp_path / "store")
        ((_, ref),) = store_captures(
            store, EvidenceRepository(pool), [Capture(request=request, response=response)]
        )
    assert ref.blob_sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.retained
def test_first_party_registration_needs_one_connection(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """F11: the Apar first-party package registers its captures on a one-connection pool."""
    with one_connection_pool(pg_db) as pool:
        Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"]).first_party()
        with pool.connection() as conn:
            assert conn.execute("SELECT count(*) FROM eqos.capture_refs").fetchone() != (0,)


def test_onboarding_refuses_an_expired_capture_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F16: an ``OriginalExpiredError`` raised during onboarding ends the command with the
    failure exit and a message naming the capture, not a traceback."""

    def expired(args: argparse.Namespace) -> Any:
        raise OriginalExpiredError("ORIGINAL_EXPIRED: capture 7 is EXPIRED")

    monkeypatch.setattr(onboard_cli, "onboard", expired)
    args = argparse.Namespace(command=onboard_cli.ONBOARD_COMMAND, symbol="SYN")
    assert onboard_cli.dispatch_onboard_command(args) == onboard_cli.RunExitStatus.FAILURE
    assert "onboard SYN refused: ORIGINAL_EXPIRED: capture 7 is EXPIRED" in capsys.readouterr().err
