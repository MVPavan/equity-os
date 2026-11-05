"""D9 phase-end fixes to purge deletion and recovery (plan D9 R8, RP4, RP5).

Why: a purge removes bytes nobody can recreate (invariant 13). A licence end must refuse before
it removes anything, a deletion must remove only the blob it names, recovery must finish what it
already deleted, residue must go even beside retained users, a cancelled intent must return to
the state it came from, and deleting many links must not exhaust descriptors. Captures here are
SYNTHETIC bytes in ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

import pytest
from purge_support import XBRL, CrashError, Env, crash_at, entity, env, ids, ref_of
from retention_support import (
    blob_path,
    capture_dir,
    ids_of,
    later,
    link_of,
    package,
    record_of,
    verify,
)

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.sourcing.snapshot import CaptureRecord
from equity_os.contracts.storage.retention import BlobDeletion, HoldRoot
from equity_os.contracts.storage.retention_purge import (
    IncompleteKind,
    PurgeRefusedError,
    PurgeStep,
    RefetchOutcome,
)
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.capture_retention import capture_registration
from equity_os.storage.raw_files.snapshot_store import RECORD_FILENAME, SnapshotStore
from equity_os.storage.retention.purge import record_licence_end
from equity_os.storage.retention.refetch import refetch
from equity_os.storage.retention.retention_io import read_authority

pytestmark = pytest.mark.pg

__all__ = ["env"]

ARCHIVE = "https://nsearchives.nseindia.com/corporate/"
TIJORI = ("tijori", "financials")
FD_LIMIT = 128
SHARED_LINKS = 120  # each link once held five descriptors: far over FD_LIMIT
DELETER = """import resource, sys
from pathlib import Path
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
root, sha, links = Path(sys.argv[1]), sys.argv[2], [tuple(a.split("/")) for a in sys.argv[3:]]
resource.setrlimit(resource.RLIMIT_NOFILE, (%d, %d))
store = SnapshotStore(root)
with store.writer_held():
    print(store.delete_blob("nse", sha, tuple(links), lambda: None).value)
"""


def bodies(root: Path, record: CaptureRecord) -> list[str]:
    """The non-record file names in a capture's directory."""
    return [p.name for p in capture_dir(root, record).iterdir() if p.name != RECORD_FILENAME]


def exchange(env: Env, body: bytes) -> tuple[CaptureReference, str]:
    """SYNTHETIC: an addressed XBRL capture verified for an unwatched entity; its address."""
    url = f"{ARCHIVE}{uuid.uuid4().hex}"
    ref = env.capture(body, XBRL, url=url)
    with env.db.migrator_connection() as conn:
        verify(conn, package(conn, entity(conn), int(ref.capture_ref_id or 0)))
    return ref, url


def test_delete_blob_unlinks_only_the_bodies_of_its_own_blob(tmp_path: Path) -> None:
    """F2: given links of two blobs, deleting one removes only its own body and blob."""
    root = tmp_path / "store"
    store = SnapshotStore(root)
    first = store.put_capture(record_of(b"first"), b"first")
    second = store.put_capture(record_of(b"second"), b"second")
    sha = hashlib.sha256(b"first").hexdigest()
    links = (link_of(first), link_of(second))
    assert store.delete_blob("nse", sha, links, lambda: None) is BlobDeletion.DELETED
    assert bodies(root, first) == [] and not blob_path(root, first).exists()
    assert store.read_capture_verified(*ids_of(second))[1] == b"second"


def test_a_licence_end_refuses_before_any_deletion(env: Env) -> None:
    """F2, RP5: an outside link on any one blob of the source refuses the licence-end purge
    before a single body or blob is removed."""
    first = env.store.get_capture(*ids(env.capture(b"tj-first")))
    second = env.store.get_capture(*ids(env.capture(b"tj-second")))
    outside = env.root.parent / "outside"
    outside.mkdir()
    os.link(blob_path(env.root, second), outside / "copy")
    with pytest.raises(PurgeRefusedError, match="outside"):
        record_licence_end(
            env.db.settings,
            env.db.logins[PgRole.PURGE],
            source_id=TIJORI[0],
            ended_on=date(2026, 10, 1),
            reason="fixture",
            database=env.db.dbname,
            snapshot_root=env.root,
            backup_dir=env.sets,
            pinned={},
            fetch=lambda url: b"",
            final_backup=None,
            checkpoint=lambda step: None,
        )
    for record in (first, second):
        assert bodies(env.root, record) and blob_path(env.root, record).exists()


def test_recovery_finishes_a_deleted_intent_a_new_hold_names(env: Env) -> None:
    """F7, R8: a crash after deletion, then a manifest hold on the blob: the rerun still
    expires the intent with its original reason instead of refusing."""
    ref, url = exchange(env, b"held-later")
    env.age()
    with pytest.raises(CrashError):
        env.purge({url: b"held-later"}.__getitem__, crash_at(PurgeStep.FILES_DELETED, []))
    pinned = {HoldRoot.MANIFEST_INPUT: frozenset({ref.blob_sha256})}
    env.purge(final=False, pinned=pinned)
    assert env.state(ref) == "EXPIRED"
    reason = "SELECT reason FROM eqos.purge_records WHERE capture_ref_id = %s"
    assert env.sql(reason, ref.capture_ref_id) == [("WINDOW",)]


def test_residue_links_go_even_beside_a_retained_user(env: Env) -> None:
    """F8, R8 residue: an expired capture's relinked body is removed although a new retained
    capture shares the blob; the blob and the retained capture's body stay."""
    expired = env.capture(b"shared-residue")
    env.age()
    env.purge(final=False)
    record = env.store.get_capture(*ids(expired))
    env.store.relink(record, b"shared-residue")  # an uncommitted re-fetch's residue
    fresh = ref_of(env.store.put_capture(record_of(b"shared-residue", *TIJORI), b"shared-residue"))
    with capture_registration(env.pool) as registration:  # registered at the aged clock
        kept = registration.insert(fresh.model_copy(update={"registered_at": later()}), url=None)
    env.purge(final=False)
    assert env.state(expired) == "EXPIRED" and bodies(env.root, record) == []
    assert env.state(kept) == "RETAINED" and env.has_body(kept)


def test_a_cancelled_intent_returns_to_restored(env: Env) -> None:
    """F13: a restored capture whose next purge is cancelled (an unknown link) is RESTORED
    again, and the run's COMPLETE lists it cancelled."""
    ref, url = exchange(env, b"restored-once")
    env.age()
    fetch = {url: b"restored-once"}.__getitem__
    env.purge(fetch, final=False)
    assert refetch(env.pool, env.store, int(ref.capture_ref_id or 0), fetch) is (
        RefetchOutcome.RESTORED
    )
    env.store.put_capture(record_of(b"restored-once"), b"restored-once")  # never registered
    report = env.purge(fetch, final=False)
    assert [b.kind for b in report.incomplete] == [IncompleteKind.UNKNOWN_LINK]
    assert env.state(ref) == "RESTORED" and env.has_body(ref)
    (complete,) = [e for e in read_authority(env.sets).journal if e.run_id == report.run_id][1:]
    assert complete.cancelled == (ref.capture_ref_id,)


def test_deleting_many_links_to_one_blob_keeps_descriptors_bounded(tmp_path: Path) -> None:
    """F17: under a lowered descriptor limit, deleting a blob shared by many captures while the
    writer lock is held succeeds and removes every link."""
    root, body = tmp_path / "store", b"many-links"
    store = SnapshotStore(root)
    records = [store.put_capture(record_of(body), body) for _ in range(SHARED_LINKS)]
    args = ["/".join(link_of(record)) for record in records]
    script = DELETER % (FD_LIMIT, FD_LIMIT)
    sha = hashlib.sha256(body).hexdigest()
    done = subprocess.run(  # noqa: S603 - this interpreter, a fixed script
        [sys.executable, "-c", script, str(root), sha, *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == BlobDeletion.DELETED.value
    assert not blob_path(root, records[0]).exists()
    assert all(bodies(root, record) == [] for record in records)
