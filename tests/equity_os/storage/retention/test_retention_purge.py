"""D9 Task 5: purge with recovery and tombstones (plan D9 R7, R8, RP4b, RP5, cases U1-U15).

Why: purge is the only code that destroys evidence (invariant 13). It may delete exactly what
the dry-run lists, never an exchange original whose address no longer serves the same bytes, and
a crash at any point must leave a state that blocks writers and converges on rerun with no
retained capture missing its bytes and no expired capture keeping them. Vendor payload becomes
the A-05 tombstones while every outcome stays. Captures are SYNTHETIC bytes in ``tmp_path``
unless the case names retained fixtures (copied into ``tmp_path``); fetches are fakes.
"""

from __future__ import annotations

import http.client
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from ledger_support import Ledger, ledger
from memory_support import memory
from pg_evidence_schema_support import _insert, runtime, seeded
from pg_support import PgTestDatabase
from purge_support import (
    A05,
    EXPIRED_REFUSAL,
    KILLER,
    OPEN_RUNS,
    PDF,
    VENDOR,
    XBRL,
    CrashError,
    Env,
    FakeResponse,
    assert_converged,
    crash_at,
    entity,
    env,
    ids,
    no_fetch,
    pause_at,
    ref_of,
    vendor_copy,
)
from retention_support import (
    PAUSE,
    dispose,
    draft_claim,
    in_thread,
    later,
    locks,
    package,
    record_of,
    retention_cli,
    set_store_clock,
    verify,
    wait_for,
)
from stage1_e2e_support import RUNS, Stage
from test_retention_holds import World, _figure, _quote, world

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.publication.ledger import Citation, CitationKind
from equity_os.contracts.storage.retention import (
    JournalEventKind,
    OriginalExpiredError,
    RefusalCode,
)
from equity_os.contracts.storage.retention_purge import (
    FetchFailure,
    FetchFailureCategory,
    IncompleteKind,
    PurgeReport,
    PurgeStep,
)
from equity_os.storage.backup.backup import DEFAULT_CLIENT_PREFIX, BackupError, verify_set
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.capture_retention import capture_registration
from equity_os.storage.raw_files.snapshot_store import BLOBS_DIRNAME, STAGING_DIRNAME, SnapshotStore
from equity_os.storage.retention import refetch
from equity_os.storage.retention.eligibility import add_months, eligible_blobs
from equity_os.storage.retention.holds import capture_facts
from equity_os.storage.retention.retention_io import init_authority, read_authority
from equity_os.verification.comparison.run import load_results
from equity_os.verification.comparison.run_store import RunStore

pytestmark = pytest.mark.pg

__all__ = ["env", "ledger", "memory", "runtime", "seeded", "world"]


def test_a_purge_deletes_the_dry_run_set_and_sanitizes_older_sets(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U1, U14: the purge expires exactly the captures the dry-run lists; the pre-purge set
    that archived their bytes is removed at step 5 and the final backup lists them expired,
    with purge records and the ``COMPLETE`` event as its watermark; no remnant is left."""
    gone = [env.capture(b"gone-1"), env.capture(b"gone-2")]
    kept = env.capture(b"address-less exchange: kept", XBRL)
    old = env.backup()
    env.age()
    with env.db.migrator_connection() as conn:
        listed = eligible_blobs(capture_facts(conn, {}), later())
    code, out = retention_cli(monkeypatch, env.db, "purge", "--dry-run")
    assert code == 0 and out.count("eligible\t") == len(listed) == 2
    report = env.purge()
    assert set(report.expired) == {c for blob in listed for c in blob.capture_ref_ids}
    assert set(report.expired) == {ref.capture_ref_id for ref in gone}
    assert env.has_body(kept) and not any(env.has_body(ref) for ref in gone)
    assert not old.exists()
    manifest = verify_set(env.sets / str(report.backup_id))
    complete = read_authority(env.sets).journal[-1]
    assert complete.kind is JournalEventKind.COMPLETE
    assert manifest.journal_watermark == complete.id
    expired = {e.capture[0]: e.purge_record_id for e in manifest.expired}
    assert set(expired) == set(report.expired) and None not in expired.values()
    assert sorted(p.name for p in env.sets.iterdir() if p.is_dir()) == [report.backup_id]


def test_a_failing_probe_halts_its_source_with_a_high_incident(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U2: a matching XBRL probe lets its source's blobs expire with purge records naming
    the probe; a mismatching and a timing-out PDF source keep every byte with a HIGH probe
    row each, open incidents, and ``retention purge`` exits 3."""
    served: dict[str, Any] = {}
    refs = []
    with env.db.migrator_connection() as conn:
        unwatched = entity(conn)
    for name, body, answer in (
        ("x1", b"xbrl-1", b"xbrl-1"),
        ("x2", b"xbrl-2", b"xbrl-2"),
        ("pa", b"pdf-a", b"changed"),
        ("pb", b"pdf-b", FetchFailure(FetchFailureCategory.TIMEOUT)),
    ):
        url = f"https://nsearchives.nseindia.com/corporate/{name}"
        kind = XBRL if name.startswith("x") else (f"pdf-{name}", PDF)
        ref = env.capture(body, kind, url=url)
        with env.db.migrator_connection() as conn:
            verify(conn, package(conn, unwatched, int(ref.capture_ref_id or 0)))
        served[url], refs = answer, [*refs, ref]

    def fetch(url: str) -> bytes:
        answer = served[url]
        if isinstance(answer, Exception):
            raise answer
        return bytes(answer)

    env.age()
    monkeypatch.setattr("equity_os.interface.commands.storage.retention_cli.live_fetch", fetch)
    args = ("purge", "--snapshot-root", str(env.root), "--backup-dir", str(env.sets))
    code, out = retention_cli(monkeypatch, env.db, *args)
    assert code == 3 and "halted\tpdf-pa" in out and "halted\tpdf-pb" in out
    assert [env.state(ref) for ref in refs] == ["EXPIRED", "EXPIRED", "RETAINED", "RETAINED"]
    assert [env.has_body(ref) for ref in refs] == [False, False, True, True]
    probes = env.sql(
        "SELECT p.outcome FROM eqos.purge_records r JOIN eqos.retention_probes p "
        "ON p.id = r.probe_id ORDER BY r.capture_ref_id"
    )
    assert probes == [("MATCH",), ("MATCH",)]
    high = env.sql(
        "SELECT source_id, outcome, category FROM eqos.retention_probes "
        "WHERE severity = 'HIGH' ORDER BY source_id"
    )
    assert high == [("pdf-pa", "MISMATCH", None), ("pdf-pb", "FAILED", "TIMEOUT")]
    assert len(env.sql("SELECT * FROM eqos.retention_incidents")) == 2
    assert retention_cli(monkeypatch, env.db, "purge", "--dry-run")[1].count("incident\t") == 2


@pytest.mark.parametrize("step", list(PurgeStep))
def test_a_crash_at_any_step_blocks_writers_and_converges(env: Env, step: PurgeStep) -> None:
    """U3: after a crash at each step a registration and a backup refuse, naming the purge
    command; a rerun converges with one FENCE (before any unlink) and one COMPLETE for the
    crashed run, no capture lacking bytes it should have, and its final backup published."""
    refs = [env.capture(b"one"), env.capture(b"two")]
    env.backup()  # a set archiving the bytes the purge expires, for SET_RENAMED
    env.age()
    seen: list[PurgeStep] = []
    fenced_before_unlink: list[bool] = []

    def checkpoint(at: PurgeStep) -> None:
        if at is PurgeStep.LINK_DELETED:
            fenced_before_unlink.append(JournalEventKind.FENCE in env.journal(crashed))
        crash_at(step, seen)(at)

    crashed = env.sql("SELECT coalesce(max(id), 0) + 1 FROM eqos.purge_runs")[0][0]
    with pytest.raises(CrashError):
        env.purge(checkpoint=checkpoint)
    assert seen[-1] is step and all(fenced_before_unlink)
    with pytest.raises(EXPIRED_REFUSAL, match="retention purge"):
        env.capture(b"a registration while the run is open")
    with pytest.raises(BackupError, match="retention purge"):
        env.backup()
    report = env.purge()
    assert report.backup_id is not None and report.run_id == crashed + 1
    assert_converged(env, refs, crashed)
    assert all(env.state(ref) == "EXPIRED" for ref in refs)


def test_a_crashed_purge_refuses_claims_until_rerun(env: Env, ledger: Ledger) -> None:
    """U3: a claim insert after a crash is refused naming the purge command, and passes once
    a rerun has converged."""
    env.capture(b"claims")
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(PurgeStep.FENCE_WRITTEN, []), final=False)

    def claim() -> int:
        with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
            return draft_claim(ledger, conn)

    with pytest.raises(EXPIRED_REFUSAL, match="fundamentals retention purge"):
        claim()
    env.purge(final=False)
    assert claim() > 0


def test_an_all_cancelled_run_completes_after_a_crash(env: Env) -> None:
    """U3b, U9: a blob with an unregistered link of the same bytes keeps every byte; its
    intent is cancelled (UNKNOWN_LINK, exit 3); a crash after step 4 leaves the run open and
    the rerun appends COMPLETE with no expired ids, takes the final backup and closes it."""
    ref = env.capture(b"shared")
    env.store.put_capture(record_of(b"shared", *VENDOR), b"shared")  # never registered
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(PurgeStep.EXPIRED_COMMITTED, []))
    report = env.purge()
    run = report.run_id - 1
    (complete,) = [
        e
        for e in read_authority(env.sets).journal
        if e.kind is JournalEventKind.COMPLETE and e.run_id == run
    ]
    assert (complete.expired, complete.cancelled) == ((), (ref.capture_ref_id,))
    assert env.state(ref) == "RETAINED" and env.has_body(ref)
    assert [b.kind for b in report.incomplete] == [IncompleteKind.UNKNOWN_LINK]
    assert report.high and report.backup_id is not None
    assert_converged(env, [ref], run)


@pytest.mark.parametrize("step", [PurgeStep.LINK_DELETED, PurgeStep.SET_RENAMED])
def test_a_killed_purge_converges_on_rerun(env: Env, step: PurgeStep) -> None:
    """U4: SIGKILL in a subprocess mid-unlink or mid-sanitize; the rerun converges."""
    refs = [env.capture(b"k-one"), env.capture(b"k-two")]
    env.backup()
    env.age()
    argv = [sys.executable, "-c", KILLER, env.db.dbname, str(env.root), str(env.sets), step]
    killed = subprocess.run(argv, env=os.environ | env.db.cli_env(), timeout=300, check=False)
    assert killed.returncode == -9
    assert env.sql(OPEN_RUNS) == [(1,)]
    env.purge()
    assert_converged(env, refs, 1)


def test_a_purge_starts_only_after_a_running_backup_is_published(env: Env) -> None:
    """U5: a backup paused before its dump holds the shared lock; the purge's run row is
    created only once the set is published."""
    env.capture(b"u5")
    env.age()
    gate = env.sets / "gate"
    prefix = ("sh", "-c", PAUSE, str(gate), *DEFAULT_CLIENT_PREFIX)
    backup, published = in_thread(lambda: env.backup(client_prefix=prefix))
    wait_for(Path(f"{gate}.paused").exists)
    purging, report = in_thread(lambda: env.purge(final=False))
    with env.db.migrator_connection() as conn:
        wait_for(lambda: ("ExclusiveLock", False) in locks(conn))
    assert env.sql("SELECT count(*) FROM eqos.purge_runs") == [(0,)]
    Path(f"{gate}.go").touch()
    backup.join()
    purging.join()
    assert isinstance(published[0], Path) and isinstance(report[0], PurgeReport), report


def test_writes_during_a_purge_wait_then_follow_what_it_expired(
    world: World, pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """U6: while the purge holds the lock, a SOURCE_QUOTE claim, a location-marker section and
    a legacy binding on the purged exchange capture wait and are refused ORIGINAL_EXPIRED;
    FIGURE and COMPARISON claims on its interpretation wait and succeed."""
    url = "https://nsearchives.nseindia.com/corporate/u6.xml"
    with pg_db.runtime_pool() as pool:
        env = Env(pg_db, pool, tmp_path)
        init_authority(env.sets)
        ref = env.capture(b"u6-xbrl", XBRL, url=url)
        c = int(ref.capture_ref_id or 0)
        verify(world.rt, package(world.rt, world.entity_of_its_own(), c))
        interpretation = world.interpretation(c)
        side = {"result_id": world.result, "source_role": "FIRST_PARTY", "surface": "x"}
        side |= {"source_id": "nse", "source_state": "VALUE", "interpretation_id": interpretation}
        left = _insert(world.rt, "result_source_values", side | {"representation": "XBRL"})
        right = _insert(world.rt, "result_source_values", side | {"representation": "PDF"})
        pair = {"result_id": world.result, "pair_kind": "EXTRACTION", "outcome": "AGREE"}
        pair_id = _insert(world.rt, "pair_outcomes", pair | {"left_value_id": left} | {
            "right_value_id": right})  # fmt: skip
        fact = world.fact()
        env.age()
        reports = [world.ledger.report() for _ in range(4)]
        world.ledger.report = reports.pop  # type: ignore[method-assign]  # one per thread
        reached, go = threading.Event(), threading.Event()
        checkpoint = pause_at(PurgeStep.INTENTS_COMMITTED, reached, go)
        purging, _ = in_thread(lambda: env.purge(lambda _: b"u6-xbrl", checkpoint, final=False))
        assert reached.wait(60)
        writes = {
            "quote": lambda: world.draft(_quote(c)),
            "marker": lambda: world.draft(body=f"Marked {{{{s:{c}|p1}}}}"),
            "binding": lambda: world.bind(fact, c),
            "figure": lambda: world.draft(_figure(interpretation, world)),
            "comparison": lambda: world.draft(
                Citation(kind=CitationKind.COMPARISON, run_id=world.run, pair_outcome_id=pair_id)
            ),
        }
        started = {name: in_thread(write) for name, write in writes.items()}
        # Drafts also serialise on the WATCHLIST lock (0026): one draft and the binding wait
        # on the retention lock, the other drafts behind that draft; none can finish.
        wait_for(lambda: locks(world.owner).count(("ShareLock", False)) == 2)
        assert all(thread.is_alive() for thread, _ in started.values())
        go.set()
        purging.join()
        for thread, _ in started.values():
            thread.join()
    outcome = {name: result[0] for name, (_, result) in started.items()}
    for name in ("quote", "marker", "binding"):
        assert isinstance(outcome[name], psycopg.Error), (name, outcome[name])
        assert RefusalCode.ORIGINAL_EXPIRED in str(outcome[name])
    assert isinstance(outcome["figure"], int) and isinstance(outcome["comparison"], int)
    assert env.state(ref) == "EXPIRED"


@pytest.mark.retained
@pytest.mark.parametrize("paused", ["extraction", "interpretations", "publication"])
def test_vendor_writes_paused_across_a_purge_are_refused(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, paused: str
) -> None:
    """U7: a vendor ingest paused after registration (or before its interpretations) and a
    run paused before publication, across a purge that expires the Tijori capture: the write
    is refused ORIGINAL_EXPIRED and no Tijori value exists."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        env = Env(pg_db, pool, tmp_path)
        init_authority(env.sets)
        vendor_copy(stage, "tijori/financials", env.root)

        def expire() -> None:
            stage_clock = stage.repository.store_clock()
            with pg_db.migrator_connection() as migrator:
                set_store_clock(migrator, add_months(stage_clock, 13))
            env.purge(final=False)

        def before(original: Callable[..., Any]) -> Callable[..., Any]:
            return lambda *a, **k: (expire(), original(*a, **k))[1]

        def after(original: Callable[..., Any]) -> Callable[..., Any]:
            return lambda *a, **k: (original(*a, **k), expire())[0]

        repository = stage.repository
        if paused == "extraction":
            monkeypatch.setattr(repository, "put_capture_ref", after(repository.put_capture_ref))
        elif paused == "interpretations":
            hooked = before(repository.put_interpretations)
            monkeypatch.setattr(repository, "put_interpretations", hooked)
        label = stage.run["vendor_inputs"]["tijori/financials"]
        if paused == "publication":
            stage.first_party()
            stage.vendor("tijori/financials", label, store=env.root)
            monkeypatch.setattr(RunStore, "publish", before(RunStore.publish))
        with pytest.raises(EXPIRED_REFUSAL, match=RefusalCode.ORIGINAL_EXPIRED):
            if paused == "publication":
                stage.execute(vendors=["tijori/financials"])
            else:
                stage.vendor("tijori/financials", label, store=env.root)
    values = env.sql(
        "SELECT count(o.raw_value_text) + count(i.value) FROM eqos.capture_refs c "
        "LEFT JOIN eqos.occurrences o ON o.capture_ref_id = c.id "
        "LEFT JOIN eqos.interpretations i ON i.capture_ref_id = c.id WHERE c.source_id = 'tijori'"
    )
    assert values == [(0,)]
    assert env.sql("SELECT count(*) FROM eqos.result_source_values WHERE value IS NOT NULL "
                   "AND source_id = 'tijori'") == [(0,)]  # fmt: skip


INTERPS = "interpretation_id IN (SELECT id FROM eqos.interpretations WHERE capture_ref_id IN ({v}))"
VENDOR_ROWS = {  # the A-05 row selections, for the vendor captures of the run
    "occurrences": "capture_ref_id IN ({v})",
    "interpretations": "capture_ref_id IN ({v})",
    "acquisition_attempts": "stage = 'EXTRACTION' AND capture_ref_id IN ({v})",
    "result_source_values": f"source_role IN ('INDEPENDENT_VENDOR', 'DIAGNOSTIC') AND {INTERPS}",
    "calculation_traces": "id IN (SELECT calculation_trace_id FROM eqos.calculation_trace_operands "
    f"WHERE {INTERPS})",
}
EXCHANGE_ROWS = "capture_ref_id NOT IN ({v})"
VENDORS = "SELECT id FROM eqos.capture_refs WHERE eqos.is_vendor_source(source_id)"
SOURCES = "SELECT id, source_id FROM eqos.capture_refs"
UNDISPOSED = (
    "SELECT id FROM eqos.queue_items q WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.queue_dispositions d WHERE d.item_id = q.id)"
)
OUTCOMES = ("pair_outcomes", "queue_items", "queue_dispositions", "fact_rows")


def inventory() -> dict[str, Any]:
    """The A-05 record's tombstone inventory, read from its approved front matter."""
    front = yaml.safe_load(A05.read_text().split("---")[1])
    (record,) = [a for a in front["amendments"] if a["id"] == "redaction-inventory"]
    return dict(record["tombstone"])


def rows(env: Env, table: str, where: str = "true") -> list[dict[str, Any]]:
    """Every row of one table matching ``where`` (over the vendor captures), as JSON."""
    vendors = ",".join(str(c) for (c,) in env.sql(VENDORS)) or "NULL"
    order = "(to_jsonb(t) ->> 'id')::bigint, to_jsonb(t)::text"
    query = (
        f"SELECT to_jsonb(t) FROM eqos.{table} t WHERE {where.format(v=vendors)} ORDER BY {order}"
    )
    return [row[0] for row in env.sql(query)]


@pytest.mark.retained
def test_vendor_payload_is_tombstoned_and_outcomes_remain(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Precondition, U11-U13 over the Apar run with all three vendors: before the purge every
    value column and dropped JSON path of the inventory is populated; after it the vendor
    rows keep only their kept columns and allowlisted keys, outcomes, queue and fact rows equal
    a pre-purge read, by-id reads of an expired row raise OriginalExpiredError while list
    reads and results load, and exchange rows are untouched."""
    tombstone = inventory()
    with pg_db.runtime_pool() as pool, pg_db.owner_pool() as owner:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        env = Env(pg_db, pool, tmp_path)
        env.root = tmp_path / "staged"  # where the harness stages Screener
        env.store = SnapshotStore(env.root)
        init_authority(env.sets)
        stage.first_party()
        for flag in ("tijori/financials", "upstox/income-statement"):
            stage.vendor(flag, vendor_copy(stage, flag, env.root), store=env.root)
        stage.vendor("screener-subscriber/SCREENER_FINANCIALS", "A-SCR")
        run = stage.execute()
        with owner.connection() as conn:
            for (item,) in env.sql(UNDISPOSED):
                dispose(conn, item)
        before = {t: rows(env, t, w) for t, w in VENDOR_ROWS.items()}
        kept = {t: rows(env, t) for t in OUTCOMES}
        exchange = {t: rows(env, t, EXCHANGE_ROWS) for t in ("occurrences", "interpretations")}
        source_of = dict(env.sql(SOURCES))
        for name in ("screener-subscriber", "tijori", "upstox"):
            mine = [r for r in before["occurrences"] if source_of[r["capture_ref_id"]] == name]
            assert any(r["raw_value_text"] for r in mine) and any(r["raw_sign"] for r in mine), name
        assert all(
            any(r[c] is not None for r in before["interpretations"])
            for c in ("value", "lower", "upper")
        )
        assert any(r["value"] is not None for r in before["result_source_values"])
        assert any(r["value"] is not None for r in before["calculation_traces"])
        dropped = [
            p.split(".") for s in tombstone.values() for p in s.get("json_dropped_known", [])
        ]
        assert any(key in r[column] for r in before["occurrences"] for column, key in dropped)
        env.age()
        report = env.purge(offline, final=False)  # exchange captures halt; vendors need no probe
        assert {c for (c,) in env.sql(VENDORS)} <= set(report.expired)
        for table, where in VENDOR_ROWS.items():
            spec = tombstone[table]
            changed = (
                set(spec.get("clear", []))
                | set(spec.get("reset", {}))
                | set(spec.get("json_keep", {}))
            )
            after = rows(env, table, where)
            assert [{k: v for k, v in r.items() if k not in changed} for r in after] == [
                {k: v for k, v in r.items() if k not in changed} for r in before[table]
            ], table
            for row in after:
                assert all(row[c] is None for c in spec.get("clear", [])), table
                assert all(row[c] == yaml.safe_load(v) for c, v in spec.get("reset", {}).items())
                for column, keys in spec.get("json_keep", {}).items():
                    assert set(row[column]) <= set(keys), (table, column)
        assert {t: rows(env, t) for t in OUTCOMES} == kept
        assert {t: rows(env, t, EXCHANGE_ROWS) for t in exchange} == exchange
        expired = before["interpretations"][0]
        with pytest.raises(OriginalExpiredError):
            stage.repository.get_interpretations([expired["id"]])
        with pytest.raises(OriginalExpiredError):
            stage.repository.get_occurrences([before["occurrences"][0]["id"]])
        assert stage.repository.list_capture_interpretations(expired["capture_ref_id"]) == ()
        assert stage.repository.list_capture_occurrences(expired["capture_ref_id"]) == ()
        assert load_results(run.run_id, pool=pool)


def offline(url: str) -> bytes:
    """A fetcher whose every address is unreachable."""
    raise FetchFailure(FetchFailureCategory.CONNECTION)


def test_same_bytes_registered_during_a_purge_land_as_a_new_capture(env: Env) -> None:
    """U8: a new capture of the expiring bytes, published while the purge is paused after
    step 4, registers once the purge ends and has its body; the expired one keeps none."""
    old = env.capture(b"same")
    env.age()
    reached, go = threading.Event(), threading.Event()
    checkpoint = pause_at(PurgeStep.EXPIRED_COMMITTED, reached, go)
    purging, _ = in_thread(lambda: env.purge(checkpoint=checkpoint, final=False))
    assert reached.wait(60)
    intake, new = in_thread(lambda: env.capture(b"same"))
    with env.db.migrator_connection() as conn:
        wait_for(lambda: ("ShareLock", False) in locks(conn))
    go.set()
    purging.join()
    intake.join()
    assert isinstance(new[0], CaptureReference), new
    assert env.state(old) == "EXPIRED" and not env.has_body(old)
    assert env.state(new[0]) == "RETAINED" and env.has_body(new[0])


def test_a_publisher_during_step_three_waits_for_the_store_lock(env: Env) -> None:
    """U9: a standalone publication of the same bytes during the unlinks waits for the
    writer lock and lands after the expiry as its own body."""
    old = env.capture(b"step-three")
    env.age()
    reached, go = threading.Event(), threading.Event()
    checkpoint = pause_at(PurgeStep.LINK_DELETED, reached, go)
    purging, _ = in_thread(lambda: env.purge(checkpoint=checkpoint, final=False))
    assert reached.wait(60)
    record = record_of(b"step-three", *VENDOR)
    writer, _ = in_thread(lambda: SnapshotStore(env.root).put_capture(record, b"step-three"))
    writer.join(0.5)
    assert writer.is_alive()  # waiting on the flock purge holds through step 4
    go.set()
    purging.join()
    writer.join()
    assert env.state(old) == "EXPIRED" and not env.has_body(old)
    assert env.store.read_capture_verified(*ids(ref_of(record)))[1] == b"step-three"


def test_unregistered_blobs_keep_their_bytes_until_resolved(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """U10: a standalone publication of new bytes and a leftover staging link to another
    unregistered blob are each reported UNREGISTERED (exit 3) and kept; registered and
    removed respectively, the next purge reports neither."""
    loose = env.store.put_capture(record_of(b"standalone", *VENDOR), b"standalone")
    staged = env.store.put_capture(record_of(b"interrupted", *VENDOR), b"interrupted")
    capture_dir = env.root.joinpath(*ids(ref_of(staged)))
    (env.root / STAGING_DIRNAME).mkdir(exist_ok=True)
    capture_dir.rename(env.root / STAGING_DIRNAME / "left-over")
    monkeypatch.setattr("equity_os.interface.commands.storage.retention_cli.live_fetch", no_fetch)
    args = ("purge", "--snapshot-root", str(env.root), "--backup-dir", str(env.sets))
    code, out = retention_cli(monkeypatch, env.db, *args)
    assert code == 3 and out.count("incomplete\tUNREGISTERED") == 2
    assert "register or remove it" in out
    assert env.store.read_capture_verified(*ids(ref_of(loose)))[1] == b"standalone"
    with capture_registration(env.pool) as registration:
        registration.insert(ref_of(loose), url=None)
    shutil.rmtree(env.root / STAGING_DIRNAME / "left-over")
    sha = ref_of(staged).blob_sha256
    (env.root / BLOBS_DIRNAME / VENDOR[0] / sha[:2] / sha).unlink()
    assert retention_cli(monkeypatch, env.db, *args)[0] == 0


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (FakeResponse(100, [b"x" * 60]), (FetchFailureCategory.INCOMPLETE, None)),
        (
            FakeResponse(None, [http.client.IncompleteRead(b"x")]),
            (FetchFailureCategory.INCOMPLETE, None),
        ),
        (
            urllib.error.HTTPError("u", 404, "nf", Message(), None),
            (FetchFailureCategory.HTTP_STATUS, 404),
        ),
        (urllib.error.URLError(TimeoutError()), (FetchFailureCategory.TIMEOUT, None)),
        (FakeResponse(5, [b"whole"]), b"whole"),
    ],
    ids=["short", "incomplete-read", "http-404", "timeout", "complete"],
)
def test_live_fetch_counts_only_a_complete_body(
    monkeypatch: pytest.MonkeyPatch, answer: Any, expected: Any
) -> None:
    """U15: a body short of its Content-Length or cut by IncompleteRead is INCOMPLETE; an
    HTTP error carries its status; a complete body returns unchanged."""

    def fake_open(self: Any, url: str, timeout: float) -> Any:
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("8.8.8.8", 443))])
    if isinstance(expected, bytes):
        assert refetch.live_fetch("https://nsearchives.nseindia.com/x") == expected
        return
    with pytest.raises(FetchFailure) as failure:
        refetch.live_fetch("https://nsearchives.nseindia.com/x")
    assert (failure.value.category, failure.value.http_status) == expected
