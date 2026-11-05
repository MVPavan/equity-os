"""D9 final review: purge recovery and restore across crashes and restores (plan D9 R8, R11, R12).

Why: recovery must never cancel an intent whose bytes are already gone (the capture would claim
bytes nobody holds), nor finish deleting bytes a failed probe now protects; a restored target's
purges must journal their expiries, a final purge backup must restore writable, and neither an
edited ``COMPLETE`` nor a rolled-back licence-end file may bring purged or ended bytes back.
Captures are SYNTHETIC bytes in ``tmp_path``; fetches are fakes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from purge_support import (
    STATE,
    XBRL,
    CrashError,
    Env,
    crash_at,
    entity,
    env,
)
from restore_support import aside, on, restore
from retention_support import package, record_of, verify
from test_backup_restore import databases
from test_retention_refetch import ARCHIVE, serve
from test_retention_restore import licence_end, mint

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.storage.retention import HoldRoot, JournalEventKind
from equity_os.contracts.storage.retention_purge import IncompleteKind, PurgeRefusedError, PurgeStep
from equity_os.storage.backup.backup import BackupError
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import RETENTION_DIRNAME
from equity_os.storage.retention.purge import NO_LONGER_ELIGIBLE, purge
from equity_os.storage.retention.retention_io import (
    EXPIRY_JOURNAL_FILE,
    JOURNAL_HEAD_FILE,
    LICENCE_ENDS_FILE,
    AuthorityError,
    read_authority,
)

pytestmark = pytest.mark.pg

__all__ = ["env", "mint"]

REVOKE_RUN_IDS = (  # undo 0032: the grants of a set migrated through 0031
    "DO $$ BEGIN EXECUTE format('REVOKE UPDATE ON SEQUENCE %s FROM eqos_purge', "
    "pg_get_serial_sequence('eqos.purge_runs', 'id')); END $$"
)


@pytest.mark.parametrize("pinned", [False, True])
def test_a_body_unlinked_before_a_crash_expires_beside_a_new_link(env: Env, pinned: bool) -> None:
    """K1 (R8): a crash after unlinking a pending body, then a standalone publication linking the
    surviving blob: the rerun expires the capture (also once a pin makes the blob ineligible)
    and reports the extra link, instead of cancelling an intent whose body is gone."""
    (ref,) = exchange(env, b"k1")
    env.age()
    with pytest.raises(CrashError):
        env.purge(echo, checkpoint=crash_at(PurgeStep.LINK_DELETED, []))
    assert not env.has_body(ref)
    env.store.put_capture(record_of(b"k1", *XBRL), b"k1")  # never registered
    pins = {HoldRoot.QUALIFICATION_FIXTURE: frozenset({ref.blob_sha256})} if pinned else None
    report = env.purge(echo, pinned=pins)
    assert env.state(ref) == "EXPIRED" and report.cancelled == ()
    assert {b.kind for b in report.incomplete} == {IncompleteKind.UNKNOWN_LINK}


def test_runs_after_a_restore_journal_past_the_primary(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """K2, L2 (R8, R11, R12): after the primary journals runs 1-2, a restored target's
    purge-first and its next purge take ids 3 and 4, so that purge journals its own fence and
    completion and a later restore of the same set expires what it purged; else it reuses run
    2's events. The set has 0031's grants (no purge-role privilege on the run id sequence),
    which a restore accepts, so run ids must not need one."""
    with env.db.migrator_connection() as conn:
        conn.execute(REVOKE_RUN_IDS)
    gone, kept = env.capture(b"k2-gone"), exchange(env, b"k2-kept")[0]
    env.age()
    old = aside(env.backup(), tmp_path)
    assert env.purge(serve(b"changed")).expired == (gone.capture_ref_id,)  # kept is halted
    assert env.purge(serve(b"changed")).expired == ()
    check, root = restore(env, old, (target := mint()))
    assert check.ok, check
    report = purge(
        env.db.settings,
        env.db.logins[PgRole.PURGE],
        database=target,
        snapshot_root=root,
        backup_dir=env.sets,
        pinned={},
        fetch=echo,
        final_backup=None,
        checkpoint=lambda step: None,
    )
    assert (report.run_id, report.expired) == (4, (kept.capture_ref_id,))
    kinds = [e.kind for e in read_authority(env.sets).journal if e.run_id == 4]
    assert kinds == [JournalEventKind.FENCE, JournalEventKind.COMPLETE]
    check, _ = restore(env, old, (again := mint()))
    assert check.ok and on(env, again, STATE, kept.capture_ref_id) == [("EXPIRED",)], check


@pytest.mark.parametrize(
    ("edit", "step"),
    [
        ("unpartitioned", PurgeStep.COMPLETION_WRITTEN),
        ("repartitioned", PurgeStep.SET_RENAMED),
        ("repartitioned", PurgeStep.COMPLETION_WRITTEN),
    ],
)
def test_an_edited_completion_is_refused_or_read_as_its_fence(
    env: Env, mint: Callable[[], str], tmp_path: Path, edit: str, step: PurgeStep
) -> None:
    """K3, L1 (R8, R11, R12): with a crash before the final backup, a ``COMPLETE`` edited to
    expire nothing is refused when it no longer partitions its fence, or once the live head
    witnesses it; written but unwitnessed, a rerun purge refuses to witness it against the
    database's EXPIRED, and it is read as its fence: the pre-purge set restores the capture
    EXPIRED. Else the purged bytes come back RETAINED."""
    ref = env.capture(b"k3")
    old = aside(env.backup(), tmp_path)
    env.age()
    with pytest.raises(CrashError):
        env.purge(checkpoint=crash_at(step, []), final=False)
    journal = env.sets / EXPIRY_JOURNAL_FILE
    fence, complete = json.loads(journal.read_text())
    cancelled = [] if edit == "unpartitioned" else [ref.capture_ref_id]
    journal.write_text(json.dumps([fence, complete | {"expired": [], "cancelled": cancelled}]))
    target = mint()
    if (edit, step) == ("repartitioned", PurgeStep.COMPLETION_WRITTEN):
        head = (env.root / RETENTION_DIRNAME / JOURNAL_HEAD_FILE).read_bytes()
        with pytest.raises(PurgeRefusedError, match="disagrees with its committed states"):
            env.purge(final=False)
        assert (env.root / RETENTION_DIRNAME / JOURNAL_HEAD_FILE).read_bytes() == head
        check, _ = restore(env, old, target)
        assert check.ok and on(env, target, STATE, ref.capture_ref_id) == [("EXPIRED",)], check
        return
    with pytest.raises((BackupError, AuthorityError), match="other captures|from the history"):
        restore(env, old, target)
    assert target not in databases(env.db.settings)


def test_a_final_purge_backup_restores_open_to_guarded_writes(
    env: Env, mint: Callable[[], str]
) -> None:
    """K4 (R8, R12): a purge's final backup holds its own run open; purge-first closes it as
    the journal completed it, so the restored target grants access with nothing pending and a
    guarded runtime write passes instead of failing PURGE_PENDING."""
    env.capture(b"k4")
    env.age()
    final = env.sets / str(env.purge().backup_id)
    check, _ = restore(env, final, (target := mint()))
    assert check.ok, check
    assert on(env, target, "SELECT count(*) FROM eqos.retention_pending") == [(0,)]
    with psycopg.connect(env.db.settings.conninfo(PgRole.RUNTIME, dbname=target)) as conn:
        conn.execute("SELECT eqos.retention_shared()")


@pytest.mark.parametrize(
    ("step", "expired"), [(PurgeStep.INTENTS_COMMITTED, 0), (PurgeStep.LINK_DELETED, 1)]
)
def test_a_probe_failing_on_recovery_keeps_the_intact_intents(
    env: Env, step: PurgeStep, expired: int
) -> None:
    """K5 (R8, R9): probes match, the purge crashes after its intents (or its first unlink);
    on the rerun the source's probe mismatches, so recovery cancels every intent whose bytes
    are intact and expires only the capture whose body is already gone."""
    refs = exchange(env, b"k5-1", b"k5-2")
    env.age()
    with pytest.raises(CrashError):
        env.purge(echo, checkpoint=crash_at(step, []))
    report = env.purge(serve(b"changed"))
    assert report.halted_sources == (XBRL[0],)
    states = [env.state(ref) for ref in refs]
    assert states.count("EXPIRED") == expired and states.count("RETAINED") == 2 - expired
    assert all(env.has_body(ref) is (env.state(ref) == "RETAINED") for ref in refs)
    assert {reason for _, reason in report.cancelled} == {NO_LONGER_ELIGIBLE}


def exchange(env: Env, *bodies: bytes) -> list[CaptureReference]:
    """SEED: verified exchange captures, each addressed by its body (see ``echo``), eligible
    three months on."""
    refs = [env.capture(body, XBRL, url=f"{ARCHIVE}{body.hex()}") for body in bodies]
    with env.db.migrator_connection() as conn:
        owner = entity(conn)
        for ref in refs:
            verify(conn, package(conn, owner, int(ref.capture_ref_id or 0)))
    return refs


def echo(url: str) -> bytes:
    """A fetcher serving each ``exchange`` address its own body."""
    return bytes.fromhex(url.removeprefix(ARCHIVE))


def test_a_rolled_back_licence_end_file_refuses_restore(
    env: Env, mint: Callable[[], str], tmp_path: Path
) -> None:
    """K6 (R11, R12): after a Tijori licence end, ``licence-ends.json`` rolled back to a valid
    prefix (here empty) while the live store keeps the Tijori marker refuses restore of a
    pre-end set before any database exists; else the target reopens Tijori publication."""
    env.capture(b"k6")
    old = aside(env.backup(), tmp_path)
    licence_end(env)
    (env.sets / LICENCE_ENDS_FILE).write_text("[]")
    target = mint()
    with pytest.raises(BackupError, match="are not filed"):
        restore(env, old, target)
    assert target not in databases(env.db.settings)
