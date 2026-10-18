"""D9 Task 7: licence ends and restore with purge-first (plan D9 R11, R12, cases R1-R13).

Why: a vendor licence end must remove all that vendor's bytes at once, holds notwithstanding,
and a restore must never bring back what a purge or a licence end removed: the restored target
stays closed to every other role until expired bytes are purged again, the expired captures
carry purge records, the retained ones hash-match and older sets that archived expired bytes
are removed. Captures are SYNTHETIC bytes in ``tmp_path`` unless a case names retained fixtures;
fetches are fakes. A set "aside" is a copy taken before a purge, since sanitize removes it.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from pg_evidence_schema_support import _insert, _interpretation, _occurrence
from pg_support import PgTestDatabase, drop_database, mint_name
from purge_support import (
    OPEN_RUNS,
    STATE,
    VENDOR,
    XBRL,
    CrashError,
    Env,
    assert_converged,
    crash_at,
    entity,
    env,
    ids,
    no_fetch,
    vendor_copy,
)
from restore_support import (
    QUOTED,
    REPLICA,
    TAMPER,
    PurgeFirst,
    aside,
    on,
    quote,
    restore,
    runtime_refused,
)
from retention_support import (
    CONFIG,
    DELTA_DAMAGE,
    delta_world,
    dispose,
    open_item,
    package,
    retention_cli,
    verdict,
    verify,
)
from stage1_e2e_support import RUNS, Stage
from test_backup_restore import databases, use_env
from test_retention_protocol import in_thread, record_of
from test_retention_purge import offline
from test_retention_refetch import ARCHIVE, serve

from fundamentals.api.cli import main
from fundamentals.contracts.retention import (
    EligibilityKind,
    JournalEventKind,
    LicenceEnd,
    LicenceEndedError,
)
from fundamentals.contracts.retention_purge import PurgeReport, PurgeStep, RestoreDelta
from fundamentals.pg.backup import MANIFEST_FILE, BackupError
from fundamentals.pg.restore_check import delta_problems
from fundamentals.pg.retention_io import (
    EXPIRY_JOURNAL_FILE,
    LICENCE_ENDS_FILE,
    append_authority,
    init_authority,
    read_authority,
)
from fundamentals.pg.settings import PgRole
from fundamentals.retention import purge as purge_module
from fundamentals.retention.purge import record_licence_end
from fundamentals.retention.refetch import refetch
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg

__all__ = ["env"]

TIJORI = VENDOR[0]
TIJORI_FLAG = "/".join(VENDOR)
RUN = (
    "INSERT INTO eqos.runs (identity_hash, cutoff, mode, status, code_version, manifest, "
    "manifest_sha256) VALUES (%(n)s, now(), 'AS_KNOWN', 'COMPLETE', 'fixture', '{}', %(n)s) "
    "RETURNING id"
)
ENDS = "SELECT source_id FROM eqos.licence_ends ORDER BY 1"
RECORDED = "SELECT count(*) FROM eqos.purge_records WHERE capture_ref_id = %s"
STATES = "SELECT count(*) FROM eqos.capture_states"
UNDISPOSED = (
    "SELECT id FROM eqos.queue_items q WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.queue_dispositions d WHERE d.item_id = q.id)"
)


@pytest.fixture
def mint(pg_db: PgTestDatabase) -> Iterator[Callable[[], str]]:
    """Fresh restore-target names, every one dropped afterwards."""
    names: list[str] = []

    def new() -> str:
        names.append(mint_name(pg_db.settings))
        return names[-1]

    yield new
    for name in names:
        drop_database(pg_db.settings, name)


def hold(env: Env, capture: int) -> int:
    """SEED: an open queue item on an occurrence of the capture (the one hold a vendor capture
    keeps, R3); returns the item."""
    with env.db.migrator_connection() as conn:
        occurrence = _insert(conn, "occurrences", _occurrence(capture, uuid.uuid4().hex))
        ((run,),) = conn.execute(RUN, {"n": uuid.uuid4().hex * 2}).fetchall()
        return open_item(conn, run, occurrence_id=occurrence)


def licence_end(env: Env, source: str = TIJORI) -> PurgeReport:
    """``record_licence_end`` as the purge login, with a held final backup."""
    return record_licence_end(
        env.db.settings,
        env.db.logins[PgRole.PURGE],
        source_id=source,
        ended_on=date(2026, 10, 1),
        reason="fixture",
        database=env.db.dbname,
        snapshot_root=env.root,
        backup_dir=env.sets,
        pinned={},
        fetch=no_fetch,
        final_backup=env.backup,
        checkpoint=lambda step: None,
    )


def boom(*args: object, **kwargs: object) -> Any:
    """A crash seam patched over a step."""
    raise CrashError(args)


def bodies(root: Path, source: str) -> list[Path]:
    """Every body file and blob of ``source`` under a store root."""
    blobs = [p for p in (root / "blobs" / source).rglob("*") if p.is_file()]
    return list((root / source).rglob("body*")) + blobs


def test_a_licence_end_purges_the_vendor_and_restores_expire_it(
    env: Env, mint: Callable[[], str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1: ``licence-end`` writes the marker, one file entry and one row, then removes every
    Tijori body and blob (one held by an open item, one unregistered), keeping every record;
    the captures are EXPIRED with purge records; later Tijori publication is refused. R2: its
    final backup lists them expired and restores them EXPIRED with their records and no body.
    R9: a set from before the licence end gets the marker before purge-first and restores
    every Tijori capture EXPIRED, refusing later publication."""
    held, plain = env.capture(b"r1-held"), env.capture(b"r1-plain")
    kept = env.capture(b"r1-kept: an address-less exchange capture", XBRL)
    tijori = [int(ref.capture_ref_id or 0) for ref in (held, plain)]
    hold(env, tijori[0])
    with env.db.migrator_connection() as conn:
        assert verdict(conn, tijori[0]).kind is EligibilityKind.HELD
    env.store.put_capture(record_of(b"r1-unregistered", *VENDOR), b"r1-unregistered")
    before = aside(env.backup(), tmp_path)
    args = ["--source", TIJORI, "--ended-on", "2026-10-01", "--reason", "r1"]
    args += ["--snapshot-root", str(env.root), "--backup-dir", str(env.sets)]
    code, out = retention_cli(
        monkeypatch, env.db, "licence-end", *args, "--config-root", str(CONFIG)
    )
    assert code == 0, out
    assert (env.root / ".retention" / "licence-ended" / TIJORI).is_file()
    assert [e.source_id for e in read_authority(env.sets).licence_ends] == [TIJORI]
    assert env.sql(ENDS) == [(TIJORI,)]
    assert [env.state(ref) for ref in (held, plain)] == ["EXPIRED", "EXPIRED"]
    assert [env.sql(RECORDED, c)[0][0] for c in tijori] == [1, 1]
    assert bodies(env.root, TIJORI) == [] and env.has_body(kept)
    assert len(list((env.root / TIJORI).rglob("record.json"))) == 3
    with pytest.raises(LicenceEndedError):
        env.store.put_capture(record_of(b"r1-later", *VENDOR), b"r1-later")
    (final,) = [line.split("\t")[1] for line in out.splitlines() if line.startswith("backup\t")]

    check, root = restore(env, env.sets / final, (target := mint()))
    assert check.ok, check
    for ref in (held, plain):
        assert on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)]
        SnapshotStore(root).read_record(*ids(ref), ref.record_sha256)
    assert bodies(root, TIJORI) == []

    def marked(inner: PurgeFirst) -> PurgeFirst:
        def first(conn: psycopg.Connection) -> RestoreDelta:
            assert (store_root / ".retention" / "licence-ended" / TIJORI).is_file()
            return inner(conn)

        return first

    target = mint()
    store_root = env.root.parent / f"restored-{target}"
    check, root = restore(env, before, target, first=marked)
    assert check.ok, check
    assert [on(env, target, STATE, c)[0][0] for c in tijori] == ["EXPIRED", "EXPIRED"]
    assert bodies(root, TIJORI) == []
    with pytest.raises(LicenceEndedError):
        SnapshotStore(root).put_capture(record_of(b"r9-later", *VENDOR), b"r9-later")


@pytest.mark.parametrize("crash", ["append_authority", "reconcile_licence_ends", "purge"])
def test_a_crashed_licence_end_blocks_the_source_until_it_completes(
    env: Env, monkeypatch: pytest.MonkeyPatch, crash: str
) -> None:
    """R3: a crash after the marker, after the file append, or after the row leaves Tijori
    publication refused; a rerun (after the marker) or the next purge completes it with one
    file entry and one row."""
    ref = env.capture(b"r3")
    env.backup()
    with monkeypatch.context() as patch:
        patch.setattr(purge_module, crash, boom)
        with pytest.raises(CrashError):
            licence_end(env)
    with pytest.raises(LicenceEndedError):
        env.store.put_capture(record_of(b"r3-new", *VENDOR), b"r3-new")
    if crash == "append_authority":
        licence_end(env)
    else:
        env.purge()
    assert env.state(ref) == "EXPIRED" and env.sql(ENDS) == [(TIJORI,)]
    assert [e.source_id for e in read_authority(env.sets).licence_ends] == [TIJORI]


def test_concurrent_licence_ends_both_persist(env: Env) -> None:
    """R3: two licence ends recorded at once both reach the file and the database."""
    refs = [env.capture(b"r3-tijori"), env.capture(b"r3-upstox", ("upstox", "income-statement"))]
    env.backup()
    runs = [in_thread(lambda s=source: licence_end(env, s)) for source in ("tijori", "upstox")]
    for thread, outcome in runs:
        thread.join(120)
        assert isinstance(outcome[0], PurgeReport), outcome
    ends = read_authority(env.sets).licence_ends
    assert sorted(e.source_id for e in ends) == ["tijori", "upstox"]
    assert [e.id for e in ends] == [1, 2]
    assert env.sql(ENDS) == [("tijori",), ("upstox",)]
    assert [env.state(ref) for ref in refs] == ["EXPIRED", "EXPIRED"]


def test_a_pre_purge_set_restores_closed_then_purged(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """R4: restoring a set taken before a purge: the runtime role is refused from creation
    until access is granted, phase 1 passes before any state row, the purged captures come
    back EXPIRED with purge records and the retained one hash-matches. R5: a capture the old
    set held only through a since-disposed item is expired too."""
    gone, held = env.capture(b"r4-gone"), env.capture(b"r5-held")
    kept = env.capture(b"r4-kept: an address-less exchange capture", XBRL)
    item = hold(env, int(held.capture_ref_id or 0))
    old = aside(env.backup(), tmp_path)
    with env.db.owner_pool() as owner, owner.connection() as conn:
        dispose(conn, item)
    env.age()
    assert set(env.purge().expired) == {gone.capture_ref_id, held.capture_ref_id}
    states = yaml.safe_load((old / MANIFEST_FILE).read_text())["table_counts"]["capture_states"]
    target = mint()

    def closed(inner: PurgeFirst) -> PurgeFirst:
        def first(conn: psycopg.Connection) -> RestoreDelta:
            assert runtime_refused(env, target)
            assert conn.execute(STATES).fetchall() == [(states,)]
            return inner(conn)

        return first

    check, root = restore(env, old, target, first=closed)
    assert check.ok and check.faithful and check.delta_ok, check
    for ref in (gone, held):
        assert on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)]
        assert on(env, target, RECORDED, ref.capture_ref_id) == [(1,)]
    assert SnapshotStore(root).read_capture_verified(*ids(kept))[1].startswith(b"r4-kept")
    assert not runtime_refused(env, target)


@pytest.mark.parametrize("step", [PurgeStep.FILES_DELETED, PurgeStep.EXPIRED_COMMITTED])
def test_a_set_restored_during_a_crashed_purge_expires_the_fence(
    env: Env, mint: Callable[[], str], tmp_path: Path, step: PurgeStep
) -> None:
    """R6: with the primary purge crashed after its fence and before ``COMPLETE``, a pre-purge
    set restores its fenced captures EXPIRED with purge records and no body; the primary rerun
    then converges and appends ``COMPLETE``."""
    refs = [env.capture(b"r6-1"), env.capture(b"r6-2")]
    old = aside(env.backup(), tmp_path)
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(step, []))
    ((crashed,),) = env.sql("SELECT max(id) FROM eqos.purge_runs")
    assert env.journal(crashed) == [JournalEventKind.FENCE]
    check, root = restore(env, old, (target := mint()))
    assert check.ok, check
    for ref in refs:
        assert on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)]
        assert on(env, target, RECORDED, ref.capture_ref_id) == [(1,)]
    assert bodies(root, TIJORI) == []
    env.purge()
    assert_converged(env, refs, crashed)


def test_restoration_survives_only_in_later_sets(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """R7: expire, then RESTORED by a matching re-fetch, then a backup: that set restores the
    capture RESTORED with its body; a set from before the first expiry restores it EXPIRED.
    R8: a second purge expires it again (two fence/complete pairs); its sanitize removes the
    later set, whose copy restores the capture EXPIRED."""
    body, url = b"r7-xbrl", f"{ARCHIVE}{uuid.uuid4().hex}"
    ref = env.capture(body, XBRL, url=url)
    with env.db.migrator_connection() as conn:
        verify(conn, package(conn, entity(conn), int(ref.capture_ref_id or 0)))
    first = aside(env.backup(), tmp_path)
    env.age()
    env.purge(serve(body))
    assert env.state(ref) == "EXPIRED"
    assert refetch(env.pool, env.store, int(ref.capture_ref_id or 0), serve(body)) == "RESTORED"
    restored = env.backup()
    check, root = restore(env, restored, (target := mint()))
    assert check.ok, check
    assert on(env, target, STATE, ref.capture_ref_id) == [("RESTORED",)]
    assert SnapshotStore(root).read_capture_verified(*ids(ref))[1] == body
    check, _ = restore(env, first, (target := mint()))
    assert check.ok and on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)], check

    later = aside(restored, tmp_path)
    env.purge(serve(body))
    kinds = [e.kind for e in read_authority(env.sets).journal]
    assert kinds == [JournalEventKind.FENCE, JournalEventKind.COMPLETE] * 2
    assert env.state(ref) == "EXPIRED" and not restored.exists()
    check, _ = restore(env, later, (target := mint()))
    assert check.ok and on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)], check


def test_restore_removes_sets_with_expired_bytes_or_stays_closed(
    env: Env, mint: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R10: restoring a set inside the backup directory that still archives bytes a crashed
    purge expired removes it; a crash before that removal leaves the restored run open and
    the target closed."""
    env.capture(b"r10")
    old = env.backup()
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(PurgeStep.COMPLETION_WRITTEN, []))
    with monkeypatch.context() as patch:
        patch.setattr(purge_module, "sanitize", boom)
        with pytest.raises(CrashError):
            restore(env, old, (target := mint()))
    assert old.exists() and on(env, target, OPEN_RUNS) == [(1,)] and runtime_refused(env, target)
    check, _ = restore(env, old, mint())
    assert check.ok and not old.exists(), check


@pytest.mark.retained
def test_restore_reports_runs_over_expired_vendor_inputs(
    pg_db: PgTestDatabase, tmp_path: Path, mint: Callable[[], str]
) -> None:
    """R11: replaying a restored run whose Tijori input a purge expired is reported under
    ``replay_expired``, apart from mismatches; the restore is still ``ok``."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        env = Env(pg_db, pool, tmp_path)
        init_authority(env.sets)
        stage.first_party()
        stage.vendor(TIJORI_FLAG, vendor_copy(stage, TIJORI_FLAG, env.root), store=env.root)
        run = stage.execute()
        with pg_db.owner_pool() as owner, owner.connection() as conn:
            for (item,) in env.sql(UNDISPOSED):
                dispose(conn, item)
        env.age()
        report = env.purge(offline)  # exchange captures halt; vendors need no probe
        check, _ = restore(env, env.sets / str(report.backup_id), mint(), replay=True)
    assert check.ok and check.replay_expired == (run.run_id,), check
    assert check.replay_mismatches == ()


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_unreadable_authority_refuses_every_command(
    env: Env, mint: Callable[[], str], monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    """R12: a missing or corrupt ``licence-ends.json`` makes restore, purge, backup and
    licence-end exit 2, writing nothing."""
    env.capture(b"r12")
    set_dir = env.backup()
    path = env.sets / LICENCE_ENDS_FILE
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("[{")
    before, target = sorted(env.sets.iterdir()), mint()
    use_env(monkeypatch, env.db, env.db.dbname)
    restored, root, sets = env.root.parent / "r12-restored", str(env.root), str(env.sets)
    retention = ["--snapshot-root", root, "--backup-dir", sets, "--config-root", str(CONFIG)]
    commands = {
        "restore": ["db", "restore", "--set", str(set_dir), "--database", target]
        + ["--snapshot-root", str(restored)],
        "backup": ["db", "backup", "--out", sets, "--snapshot-root", root],
        "purge": ["retention", "purge", *retention],
        "licence-end": ["retention", "licence-end", "--source", TIJORI]
        + ["--ended-on", "2026-10-01", "--reason", "r12", *retention],
    }
    for name, command in commands.items():
        assert main(command) == 2, name
    assert sorted(env.sets.iterdir()) == before and target not in databases(env.db.settings)
    assert not (env.root / ".retention").exists() and not restored.exists()


def test_a_set_older_than_0030_is_refused(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """R13: a set whose dump predates migration 0030 is refused before any database exists
    (an absent-schema set restores as in D2: ``test_backup_restore.py``)."""
    old = aside(env.backup(), tmp_path)
    data = yaml.safe_load((old / MANIFEST_FILE).read_text())
    del data["table_counts"]["refetch_attempts"]
    (old / MANIFEST_FILE).write_text(yaml.safe_dump(data))
    target = mint()
    with pytest.raises(BackupError, match="predates migration 0030"):
        restore(env, old, target)
    assert target not in databases(env.db.settings)


def test_a_quoted_restored_capture_restores_with_its_claim(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """R7, quote-bearing: expire, RESTORED by a matching re-fetch, then a SOURCE_QUOTE claim and
    a backup: that set restores the capture RESTORED with its body and the claim, and the claim
    holds it through a later purge. A set from before the first expiry restores it EXPIRED
    with no body: restore expires the bytes the claim's later set keeps."""
    body, url = b"r7-quote: revenue 7 crore", f"{ARCHIVE}{uuid.uuid4().hex}"
    ref = env.capture(body, XBRL, url=url)
    capture = int(ref.capture_ref_id or 0)
    with env.db.migrator_connection() as conn:
        verify(conn, package(conn, owner := entity(conn), capture))
    first = aside(env.backup(), tmp_path)
    env.age()
    env.purge(serve(body))
    assert refetch(env.pool, env.store, capture, serve(body)) == "RESTORED"
    claim = quote(env, owner, capture, "revenue 7 crore")
    later = env.backup()
    env.purge(serve(body))
    assert env.state(ref) == "RESTORED"
    check, root = restore(env, later, (target := mint()))
    assert check.ok, check
    assert on(env, target, STATE, capture) == [("RESTORED",)]
    assert on(env, target, QUOTED, claim) == [(capture, "revenue 7 crore")]
    assert b"revenue 7 crore" in SnapshotStore(root).read_capture_verified(*ids(ref))[1]
    check, root = restore(env, first, (target := mint()))
    assert check.ok and on(env, target, STATE, capture) == [("EXPIRED",)], check
    assert on(env, target, RECORDED, capture) == [(1,)] and bodies(root, XBRL[0]) == []


@pytest.mark.parametrize("damage", ["emptied", "truncated", "rewritten", "beyond its end"])
def test_a_truncated_or_rewritten_journal_is_refused(
    env: Env, mint: Callable[[], str], tmp_path: Path, damage: str
) -> None:
    """F1 (R11, R12): the published sets witness the journal's head, so after a purge an
    emptied, truncated or rewritten journal (one dropping the expiry) refuses restore of a
    pre-purge set before any database exists, and backup too; with no set left beside it, the
    restored set's own watermark past the journal's end refuses. Otherwise the old set would
    restore the expired bytes RETAINED."""
    env.capture(b"f1")
    old = aside(env.backup(), tmp_path)
    env.age()
    final = env.sets / str(env.purge().backup_id)
    journal = env.sets / EXPIRY_JOURNAL_FILE
    events = json.loads(journal.read_text())
    assert [e["kind"] for e in events] == ["FENCE", "COMPLETE"]
    if damage == "beyond its end":
        old = aside(final, tmp_path)
        shutil.rmtree(final)
    kept = {"truncated": events[:1], "rewritten": [events[0], events[1] | {"expired": []}]}
    journal.write_text(json.dumps(kept.get(damage, [])))
    target = mint()
    with pytest.raises(BackupError, match="retention authority refused"):
        restore(env, old, target)
    assert target not in databases(env.db.settings)
    if damage != "beyond its end":
        with pytest.raises(BackupError, match="truncated or rolled back|differs from the history"):
            env.backup()


def test_a_journal_rolled_back_before_the_final_backup_is_refused(
    env: Env, mint: Callable[[], str]
) -> None:
    """G1 (R11, R12): a purge witnesses the journal's head in the live store before it deletes.
    After a crash past the deletion and before the final backup, an emptied journal (what a
    rollback of the whole backup directory leaves) agrees with every set, so only that witness
    refuses restore of the pre-purge set, which would bring the deleted vendor bytes back."""
    env.capture(b"g1")
    old = env.backup()
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(PurgeStep.FILES_DELETED, []))
    (env.sets / EXPIRY_JOURNAL_FILE).write_text("[]")
    with pytest.raises(BackupError, match="truncated or rolled back"):
        restore(env, old, (target := mint()))
    assert target not in databases(env.db.settings)


@pytest.mark.parametrize("damage", ["none", *DELTA_DAMAGE])
def test_the_delta_is_exactly_the_expired_vendor_tombstone_closure(damage: str) -> None:
    """G2 (R12, A-05): the rows purge-first may change are derived from the pre-purge rows as
    ``tombstone_vendor_capture`` selects them, so a tombstone of an unrelated trace, operand or
    result value, an omitted closure trace and a non-vendor capture's tombstone each fail."""
    before, after = delta_world(damage)
    problems = delta_problems(before, after, RestoreDelta(expired=(1,), rows={}))
    assert bool(problems) is (damage != "none"), problems


def test_a_licence_end_filed_during_restore_is_marked_and_purged(
    env: Env, mint: Callable[[], str]
) -> None:
    """F6 (R12, RP4a): a licence end filed after restore first read the authority files is
    marked and purged from the one authority snapshot purge-first consumes, so the restored
    store refuses later Tijori publication instead of accepting it."""
    ref = env.capture(b"f6")
    set_dir = env.backup()
    end = LicenceEnd(
        source_id=TIJORI, ended_on=date(2026, 10, 1), reason="f6", recorded_at=datetime.now(UTC)
    )

    def late(inner: PurgeFirst) -> PurgeFirst:
        def first(conn: psycopg.Connection) -> RestoreDelta:
            append_authority(env.sets, end)
            return inner(conn)

        return first

    check, root = restore(env, set_dir, (target := mint()), first=late)
    assert check.ok, check
    assert on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)]
    with pytest.raises(LicenceEndedError):
        SnapshotStore(root).put_capture(record_of(b"f6-later", *VENDOR), b"f6-later")


@pytest.mark.parametrize("tamper", ["none", *TAMPER])
def test_the_restore_delta_allows_only_tombstones_of_expired_captures(
    env: Env, mint: Callable[[], str], tmp_path: Path, tamper: str
) -> None:
    """F9, G2, G3 (R12 phase 2, A-05 redaction inventory): purge-first may change a preserved
    row only into its tombstone image and only for a capture it expired. One more change that
    leaves every row count equal - a kept column of the tombstoned occurrence, the inventory
    columns of a retained capture's occurrence, an expired occurrence left with its payload or
    a retained interpretation's numeric moved at its 18th decimal - fails the delta and keeps
    the target closed."""
    gone = env.capture(b"f9-gone")
    kept = env.capture(b"f9-kept: an address-less exchange capture", XBRL)
    with env.db.migrator_connection() as conn:
        for ref in (gone, kept):
            row = _occurrence(capture := int(ref.capture_ref_id or 0), uuid.uuid4().hex)
            occurrence = _insert(conn, "occurrences", row)
        exact = {"upper": Decimal("3405600000.000000000000000001")}
        _insert(
            conn, "interpretations", _interpretation(entity(conn), capture, occurrence, **exact)
        )
    old = aside(env.backup(), tmp_path)
    env.age()
    assert env.purge().expired == (gone.capture_ref_id,)

    def tampered(inner: PurgeFirst) -> PurgeFirst:
        def first(conn: psycopg.Connection) -> RestoreDelta:
            delta = inner(conn)
            if tamper in TAMPER:
                admin = env.db.settings.conninfo(PgRole.ADMIN, dbname=conn.info.dbname)
                with psycopg.connect(admin, autocommit=True) as other:
                    other.execute(REPLICA)
                    ref = gone if tamper in ("kept column", "untouched payload") else kept
                    other.execute(TAMPER[tamper], (ref.capture_ref_id,))
            return delta

        return first

    check, _ = restore(env, old, (target := mint()), first=tampered)
    assert check.delta_ok is check.ok is (tamper == "none"), check
    assert runtime_refused(env, target) is (tamper != "none")
