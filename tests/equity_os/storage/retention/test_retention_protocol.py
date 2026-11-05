"""D9 Task 4: the retention protocol, store operations and backup (plan D9 cases P1-P14).

Why: a purge deletes bytes nobody can recreate (invariant 13), so every write that could make a
capture needed must serialise against it, a writer whose snapshot predates a purge must retry
rather than cite what the purge just removed, a backup must never archive expired bytes nor
lose an expired capture's record, and the expiry history that restore relies on must survive
concurrent writers and refuse tampering. Captures here are SYNTHETIC bytes in ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from ledger_support import Ledger, ledger
from pg_evidence_schema_support import _insert, _occurrence, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import IsolationLevel, errors
from psycopg_pool import ConnectionPool
from retention_support import (
    PAUSE,
    blob_path,
    capture_dir,
    draft_claim,
    ids_of,
    in_thread,
    link_of,
    locks,
    record_of,
    register,
    synthetic,
    wait_for,
)
from test_retention_classes import _queue_item

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.sourcing.snapshot import (
    IntegrityError,
)
from equity_os.contracts.storage.retention import (
    BlobDeletion,
    BlobEntry,
    FencedCapture,
    JournalEvent,
    JournalEventKind,
    LicenceEnd,
    LicenceEndedError,
    OriginalExpiredError,
    RefusalCode,
)
from equity_os.storage.backup.backup import (
    CAPTURES_DIR,
    DEFAULT_CLIENT_PREFIX,
    BackupError,
    ExpiredCapture,
    verify_set,
    write_backup,
)
from equity_os.storage.database.settings import PgRole
from equity_os.storage.facts.pg_fact_store import create_native_store, run_serializable
from equity_os.storage.raw_files.capture_retention import capture_registration, read_retained
from equity_os.storage.raw_files.snapshot_store import (
    RECORD_FILENAME,
    RETENTION_DIRNAME,
    SnapshotStore,
)
from equity_os.storage.records import repository_rows as rows_sql
from equity_os.storage.retention.retention_io import (
    EXPIRY_JOURNAL_FILE,
    JOURNAL_HEAD_FILE,
    LICENCE_ENDS_FILE,
    AuthorityError,
    append_authority,
    expiries_after,
    init_authority,
    read_authority,
    session_exclusive,
)

pytestmark = pytest.mark.pg

__all__ = ["ledger", "runtime", "seeded"]

URL = "https://nsearchives.nseindia.com/corporate/xbrl/p-case.xml"
PURGE_RUN = (
    "INSERT INTO eqos.purge_runs (id) OVERRIDING SYSTEM VALUE "
    "SELECT coalesce(max(id), 0) + 1 FROM eqos.purge_runs RETURNING id"
)
CLOSE_RUN = "INSERT INTO eqos.purge_run_closures (run_id) VALUES (%s)"
EXPIRE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, 'EXPIRED')"
APPENDER = (
    "import sys\nfrom pathlib import Path\n"
    "from equity_os.contracts.storage.retention import JournalEvent, JournalEventKind\n"
    "from equity_os.storage.retention.retention_io import append_authority\n"
    "for _ in range(25):\n"
    "    append_authority(Path(sys.argv[1]), "
    "JournalEvent(kind=JournalEventKind.COMPLETE, run_id=int(sys.argv[2])))\n"
)
# RP3: every R4 edge table, capture_refs, the payload tables, dispositions and watchlist ADDs.
GUARDED = frozenset(
    {"capture_refs", "numeric_claims", "report_sections", "memory_supports", "queue_item_inputs"}
    | {"queue_item_traces", "queue_dispositions", "legacy_evidence_bindings", "fact_admissions"}
    | {"evidence_input_captures", "identity_events", "onboarding_records", "decisions"}
    | {"namespace_verifications", "occurrences", "interpretations", "interpretation_operands"}
    | {"interpretation_condition_evidence", "construction_traces", "calculation_trace_operands"}
    | {"result_source_values", "run_inputs", "acquisition_attempts", "package_members"}
    | {"vendor_parser_versions", "vendor_outcomes", "vendor_values", "vendor_basis_bindings"}
    | {"vendor_label_proposals", "vendor_text_claims"}
)
GUARD_TABLES = (
    "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
    "WHERE t.tgname = 'a0_retention_guard'"
)


def publish(pool: ConnectionPool, store: SnapshotStore, body: bytes) -> CaptureReference:
    """Store and register one capture with an address, as an exchange intake would."""
    record = store.put_capture(record_of(body), body)
    assert record.body is not None
    now = datetime.now(UTC)
    ref = CaptureReference(
        capture_ref_id=None,
        source_id=record.request.source_id,
        surface=record.request.surface,
        request_key=record.request.request_key,
        capture_id=record.capture_id,
        blob_sha256=record.body.content_sha256,
        record_sha256=record.record_sha256,
        registered_at=now,
        first_seen_at=now,
    )
    with capture_registration(pool) as registration:
        return registration.insert(ref, url=URL)


def purge_run(migrator: psycopg.Connection, *, close: bool = True) -> int:
    """SEED: a committed purge run (its epoch taken), closed unless ``close`` is false."""
    row = migrator.execute(PURGE_RUN).fetchone()
    assert row is not None
    if close:
        migrator.execute(CLOSE_RUN, (row[0],))
    return int(row[0])


@pytest.fixture
def migrator(pg_db: PgTestDatabase) -> Iterator[psycopg.Connection]:
    """An autocommit migrator connection (owner of every table)."""
    with pg_db.migrator_connection() as conn:
        yield conn


def test_writers_hold_the_lock_shared_for_their_transaction(
    ledger: Ledger, migrator: psycopg.Connection
) -> None:
    """P1: a paused registration and a paused claim insert show the shared lock; it is gone
    after commit."""
    pool = ledger.pools[PgRole.RUNTIME]
    with capture_registration(pool) as registration:
        registration.insert(synthetic("nse", "NSE_XBRL_INSTANCE"), url=URL)
        assert locks(migrator) == [("ShareLock", True)]
    assert locks(migrator) == []
    with pool.connection() as conn, conn.transaction():
        draft_claim(ledger, conn)
        assert locks(migrator) == [("ShareLock", True)]
    assert locks(migrator) == []


def test_a_writer_with_a_snapshot_older_than_a_purge_retries(
    ledger: Ledger, pg_db: PgTestDatabase, migrator: psycopg.Connection
) -> None:
    """P2: no purge yet → writes pass (NULL = NULL); REPEATABLE READ and SERIALIZABLE writers
    whose snapshot predates a committed purge get STALE_SNAPSHOT (40001), a session variable
    changes nothing, and one begun after passes (a capture registration: drafting refuses any
    level but READ COMMITTED, 0026); a READ COMMITTED writer waiting on the
    exclusive lock passes once the purge commits; a rolled-back epoch refuses writes until a
    purge commits."""
    epoch = "SELECT pg_sequence_last_value('eqos.retention_epoch')"
    assert migrator.execute(epoch).fetchone() == (None,)
    stale = pytest.raises(errors.SerializationFailure, match=RefusalCode.STALE_SNAPSHOT)
    for level in (IsolationLevel.REPEATABLE_READ, IsolationLevel.SERIALIZABLE):
        with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as conn:
            conn.isolation_level = level
            with stale, conn.transaction():
                conn.execute("SET LOCAL eqos.retention_bypass = 'on'")
                conn.execute("SELECT 1")  # takes the transaction snapshot
                purge_run(migrator)
                register(conn, "nse", "NSE_XBRL_INSTANCE")
            with conn.transaction():
                assert register(conn, "nse", "NSE_XBRL_INSTANCE") > 0

    with psycopg.connect(pg_db.conninfo(PgRole.MIGRATOR), autocommit=True) as purge:
        session_exclusive(purge)
        run = purge_run(purge, close=False)

        def waiting_writer() -> int:
            with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as conn, conn.transaction():
                return draft_claim(ledger, conn)

        thread, outcome = in_thread(waiting_writer)
        wait_for(lambda: ("ShareLock", False) in locks(migrator))
        purge.execute(CLOSE_RUN, (run,))
    thread.join()
    assert isinstance(outcome[0], int), outcome

    with migrator.transaction(force_rollback=True):
        migrator.execute("SELECT nextval('eqos.retention_epoch')")
    with stale, ledger.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        draft_claim(ledger, conn)
    purge_run(migrator)
    with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        assert draft_claim(ledger, conn) > 0


def test_a_stale_fact_store_write_is_retried_by_its_handler(
    pg_db: PgTestDatabase, migrator: psycopg.Connection
) -> None:
    """P3: a SERIALIZABLE fact-store write refused 40001 is retried by ``run_serializable``
    (its existing handler) and succeeds on a fresh snapshot."""
    attempts: list[int] = []
    insert = rows_sql.INSERT_CAPTURE_REF + " RETURNING id"

    def operation(cursor: Any) -> int:
        attempts.append(len(attempts))
        if len(attempts) == 1:
            purge_run(migrator)
        cursor.execute(insert, rows_sql.capture_params(synthetic("nse", "NSE_XBRL_INSTANCE")))
        return int(cursor.fetchone()["id"])

    with pg_db.runtime_pool() as pool:
        assert run_serializable(pool, create_native_store(pool, "p3"), operation) > 0
    assert len(attempts) == 2


def test_guard_v2_covers_rp3_and_refuses_payload_on_an_expired_capture(
    seeded: dict[str, int], runtime: psycopg.Connection, migrator: psycopg.Connection
) -> None:
    """RP3: the guard sits on every RP3 table; a new occurrence on an ``EXPIRED`` capture is
    refused ORIGINAL_EXPIRED, while a queue input on its existing occurrence proceeds."""
    assert {row[0] for row in migrator.execute(GUARD_TABLES)} == GUARDED
    capture = register(runtime, "nse", "NSE_XBRL_INSTANCE")
    occurrence = _insert(runtime, "occurrences", _occurrence(capture, "p-1"))
    runtime.execute(
        "INSERT INTO eqos.vendor_parser_versions (parser_version, parser_sha256) VALUES (%s, %s)",
        ("expiry-test.v1", "a" * 64),
    )
    outcome = _insert(
        runtime,
        "vendor_outcomes",
        {
            "capture_ref_id": capture,
            "surface": "chart-api",
            "parser_version": "expiry-test.v1",
            "status": "OK",
            "row_count": 1,
        },
    )
    migrator.execute(EXPIRE, (capture,))
    expired = pytest.raises(errors.ObjectNotInPrerequisiteState, match=RefusalCode.ORIGINAL_EXPIRED)
    with expired:
        _insert(runtime, "occurrences", _occurrence(capture, "p-2"))
    with pytest.raises(errors.ObjectNotInPrerequisiteState, match=RefusalCode.ORIGINAL_EXPIRED):
        runtime.execute(
            "INSERT INTO eqos.vendor_values "
            "(outcome_id, capture_ref_id, table_key, row_index, column_index, locator) "
            "VALUES (%s, %s, 'price', 0, 0, '/0')",
            (outcome, capture),
        )
    with runtime.transaction():
        item = _insert(runtime, "queue_items", _queue_item(seeded["runs"]))
        assert _insert(runtime, "queue_item_inputs", {"item_id": item, "occurrence_id": occurrence})


def test_a_backup_holds_the_lock_shared_until_its_set_is_published(
    pg_db: PgTestDatabase, tmp_path: Path, migrator: psycopg.Connection
) -> None:
    """P4: a backup paused before its dump holds the lock shared; an exclusive attempt waits
    until the set is published."""
    gate, out = tmp_path / "gate", tmp_path / "sets"
    prefix = ("sh", "-c", PAUSE, str(gate), *DEFAULT_CLIENT_PREFIX)
    backup, published = in_thread(
        lambda: write_backup(
            pg_db.settings,
            database=pg_db.dbname,
            snapshot_root=tmp_path / "store",
            out_dir=out,
            client_prefix=prefix,
        )
    )
    wait_for(Path(f"{gate}.paused").exists)
    assert locks(migrator) == [("ShareLock", True)]

    def exclusive() -> list[str]:
        with psycopg.connect(pg_db.conninfo(PgRole.MIGRATOR), autocommit=True) as conn:
            session_exclusive(conn)
            return [p.name for p in out.iterdir() if p.is_dir() and not p.name.startswith(".")]

    purge, seen = in_thread(exclusive)
    wait_for(lambda: ("ExclusiveLock", False) in locks(migrator))
    Path(f"{gate}.go").touch()
    backup.join()
    purge.join()
    assert isinstance(published[0], Path), published
    assert seen == [[published[0].name]]


def test_a_backup_archives_only_the_record_of_an_expired_capture(
    pg_db: PgTestDatabase, tmp_path: Path, migrator: psycopg.Connection
) -> None:
    """P5: an expired capture is listed with its URL and hashes, its ``record.json`` archived
    byte-identical and no body; retained bodies hash-match; the watermark is the journal's last
    event id."""
    root, out = tmp_path / "store", tmp_path / "sets"
    store = SnapshotStore(root)
    with pg_db.runtime_pool() as pool:
        gone, kept = publish(pool, store, b'{"gone": 1}'), publish(pool, store, b'{"kept": 2}')
    write_backup(pg_db.settings, database=pg_db.dbname, snapshot_root=root, out_dir=out)
    gone_record = store.get_capture(gone.source_id, gone.surface, gone.request_key, gone.capture_id)
    links = (link_of(gone_record),)
    deleted = store.delete_blob(gone.source_id, gone.blob_sha256, links, lambda: None)
    assert deleted is BlobDeletion.DELETED
    run = purge_run(migrator)
    migrator.execute(EXPIRE, (gone.capture_ref_id,))
    append_authority(out, JournalEvent(kind=JournalEventKind.FENCE, run_id=run))
    append_authority(out, JournalEvent(kind=JournalEventKind.COMPLETE, run_id=run))

    set_dir = write_backup(pg_db.settings, database=pg_db.dbname, snapshot_root=root, out_dir=out)
    manifest = verify_set(set_dir)
    (expired,) = manifest.expired
    assert expired == ExpiredCapture(capture=expired.capture, url=URL)
    assert expired.capture[0] == gone.capture_ref_id
    assert expired.capture[5:] == (gone.blob_sha256, gone.record_sha256)
    assert [c[0] for c in manifest.captures] == [kept.capture_ref_id]
    assert manifest.journal_watermark == 2
    archived = capture_dir(set_dir / CAPTURES_DIR, gone_record)
    assert [p.name for p in archived.iterdir()] == [RECORD_FILENAME]
    original = capture_dir(root, gone_record) / RECORD_FILENAME
    assert (archived / RECORD_FILENAME).read_bytes() == original.read_bytes()
    _, body = SnapshotStore(set_dir / CAPTURES_DIR).read_capture_verified(*ids_of_ref(kept))
    assert hashlib.sha256(body).hexdigest() == kept.blob_sha256


def ids_of_ref(ref: CaptureReference) -> tuple[str, str, str, str]:
    """A registered capture's store identity."""
    return ref.source_id, ref.surface, ref.request_key, ref.capture_id


def test_authority_files_gate_a_backup(
    pg_db: PgTestDatabase, tmp_path: Path, migrator: psycopg.Connection
) -> None:
    """P6: a directory with sets but no licence-ends file refuses, writing nothing; a new
    directory publishes and initialises both files; with a database licence end a new
    directory refuses."""

    def backup(out: Path) -> Path:
        return write_backup(
            pg_db.settings, database=pg_db.dbname, snapshot_root=tmp_path / "s", out_dir=out
        )

    fresh = tmp_path / "fresh"
    backup(fresh)
    assert read_authority(fresh).journal == () and read_authority(fresh).licence_ends == ()
    assert {p.name for p in fresh.iterdir()} >= {LICENCE_ENDS_FILE, EXPIRY_JOURNAL_FILE}
    (fresh / LICENCE_ENDS_FILE).unlink()
    before = sorted(p.name for p in fresh.iterdir())
    with pytest.raises(BackupError, match="authority"):
        backup(fresh)
    assert sorted(p.name for p in fresh.iterdir()) == before
    migrator.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('tijori')")
    with pytest.raises(BackupError, match="authority"):
        backup(tmp_path / "after-licence-end")
    assert not (tmp_path / "after-licence-end").exists()


def test_authority_appends_are_serialised_and_append_only(tmp_path: Path) -> None:
    """P7: two processes appending concurrently keep every entry with consecutive ids; a file
    with a dropped or renumbered event refuses the next append and is left as found."""
    init_authority(tmp_path)
    appenders = [
        subprocess.Popen([sys.executable, "-c", APPENDER, str(tmp_path), str(run)])
        for run in (1, 2)
    ]
    assert [process.wait(timeout=120) for process in appenders] == [0, 0]
    journal = read_authority(tmp_path).journal
    assert [event.id for event in journal] == list(range(1, 51))
    assert sorted(event.run_id for event in journal) == [1] * 25 + [2] * 25
    stamp = datetime.now(UTC)
    licence = LicenceEnd(source_id="tijori", ended_on=stamp.date(), reason="x", recorded_at=stamp)
    assert append_authority(tmp_path, licence).id == 1

    path = tmp_path / EXPIRY_JOURNAL_FILE
    event = JournalEvent(kind=JournalEventKind.COMPLETE, run_id=3)
    original = path.read_text()
    for tampered in (original.replace('"id": 2,', '"id": 7,'), dropped(original)):
        path.write_text(tampered)
        with pytest.raises(AuthorityError, match="dropped or renumbered"):
            append_authority(tmp_path, event)
        assert path.read_text() == tampered


@pytest.mark.parametrize("head", [None, "[1, 2]", "{"])
def test_a_missing_or_malformed_head_refuses_a_journal(tmp_path: Path, head: str | None) -> None:
    """H1 (R11): beside a live store a missing head passes only an empty journal, so a lost
    witness never passes silently, and a malformed head refuses rather than crashing."""
    init_authority(tmp_path)
    live = tmp_path / "live" / RETENTION_DIRNAME
    assert read_authority(tmp_path, live.parent).journal == ()
    append_authority(tmp_path, JournalEvent(kind=JournalEventKind.COMPLETE, run_id=1))
    if head is not None:
        live.mkdir(parents=True)
        (live / JOURNAL_HEAD_FILE).write_text(head)
    with pytest.raises(AuthorityError, match="missing or unreadable"):
        read_authority(tmp_path, live.parent)


def dropped(journal_text: str) -> str:
    """The journal text with its second event removed."""
    events = json.loads(journal_text)
    return json.dumps(events[:1] + events[2:])


def test_delete_blob_removes_links_then_the_blob_and_keeps_unknown_links(
    tmp_path: Path,
) -> None:
    """P8: the blob and its named links go, records stay, ``checkpoint`` runs after each
    unlink; a second call is a no-op; an extra unregistered link keeps every byte."""
    root, body = tmp_path / "store", b'{"shared": 1}'
    store = SnapshotStore(root)
    first = store.put_capture(record_of(body), body)
    second = store.put_capture(record_of(body), body)
    calls: list[None] = []
    links = (link_of(first), link_of(second))
    source, sha = first.request.source_id, hashlib.sha256(body).hexdigest()
    assert store.delete_blob(source, sha, links, lambda: calls.append(None)) is BlobDeletion.DELETED
    assert len(calls) == 3 and not blob_path(root, first).exists()
    for record in (first, second):
        assert [p.name for p in capture_dir(root, record).iterdir()] == [RECORD_FILENAME]
    assert store.delete_blob(source, sha, links, lambda: calls.append(None)) is BlobDeletion.DELETED
    assert len(calls) == 3

    named = store.put_capture(record_of(body), body)
    store.put_capture(record_of(body), body)  # unregistered: not named below
    outcome = store.delete_blob(source, sha, (link_of(named),), lambda: calls.append(None))
    assert outcome is BlobDeletion.UNKNOWN_LINK and len(calls) == 3
    assert store.read_capture_verified(*ids_of(named))[1] == body


def test_blob_inventory_lists_unregistered_and_staged_blobs(tmp_path: Path) -> None:
    """P9: a standalone publication's blob and a blob whose only other link is a ``.staging``
    entry are both listed with their link counts."""
    root = tmp_path / "store"
    store = SnapshotStore(root)
    store.put_capture(record_of(b"standalone"), b"standalone")
    staged = store.put_capture(record_of(b"staged"), b"staged")
    remnant = root / ".staging" / f"{staged.capture_id}-crashed"
    remnant.mkdir(parents=True)
    body = next(p for p in capture_dir(root, staged).iterdir() if p.name != RECORD_FILENAME)
    body.rename(remnant / body.name)
    assert set(store.blob_inventory()) == {
        BlobEntry(source_id="nse", blob_sha256=hashlib.sha256(b"standalone").hexdigest(), links=2),
        BlobEntry(source_id="nse", blob_sha256=hashlib.sha256(b"staged").hexdigest(), links=2),
    }


def test_relink_restores_the_body_and_never_rewrites_the_record(tmp_path: Path) -> None:
    """P10: after the blob is deleted, ``relink`` brings the verified body back and leaves
    ``record.json`` byte-identical."""
    root, body = tmp_path / "store", b'{"relinked": 1}'
    store = SnapshotStore(root)
    record = store.put_capture(record_of(body), body)
    record_path = capture_dir(root, record) / RECORD_FILENAME
    before = record_path.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    store.delete_blob("nse", sha, (link_of(record),), lambda: None)
    assert store.relink(record, body) == record
    assert store.read_capture_verified(*ids_of(record))[1] == body
    assert record_path.read_bytes() == before


def test_a_licence_marker_closes_the_source_except_hash_checked_records(tmp_path: Path) -> None:
    """P11: with a ``tijori`` marker, its publish, record, listing and byte reads refuse;
    ``read_record`` returns the record on a hash match only; other sources are unaffected."""
    root = tmp_path / "store"
    store = SnapshotStore(root)
    tijori = store.put_capture(record_of(b"tj", "tijori", "financials"), b"tj")
    nse = store.put_capture(record_of(b"nse"), b"nse")
    store.mark_licence_ended("tijori")
    store.mark_licence_ended("tijori")
    with pytest.raises(LicenceEndedError):
        store.put_capture(record_of(b"tj2", "tijori", "financials"), b"tj2")
    with pytest.raises(LicenceEndedError):
        store.get_capture(*ids_of(tijori))
    with pytest.raises(LicenceEndedError):
        store.read_capture_verified(*ids_of(tijori))
    for read in (store.read_body, store.read_evidence_body):  # F5: every byte reader
        with pytest.raises(LicenceEndedError):
            read(tijori)
    with pytest.raises(LicenceEndedError):
        store.list_captures(*ids_of(tijori)[:3])
    kept = store.read_record(*ids_of(tijori), tijori.record_sha256)
    assert kept == (capture_dir(root, tijori) / RECORD_FILENAME).read_bytes()
    with pytest.raises(IntegrityError):
        store.read_record(*ids_of(tijori), "0" * 64)
    assert store.get_capture(*ids_of(nse)) == nse
    assert store.read_capture_verified(*ids_of(nse))[1] == b"nse"
    store.put_capture(record_of(b"nse2"), b"nse2")


def test_read_retained_tells_expiry_from_corruption(
    pg_db: PgTestDatabase, tmp_path: Path, migrator: psycopg.Connection
) -> None:
    """P12: a retained capture reads; its missing body is corruption (``IntegrityError``); once
    ``EXPIRED`` the same read is ``OriginalExpiredError``."""
    root = tmp_path / "store"
    store = SnapshotStore(root)
    with pg_db.runtime_pool() as pool:
        ref = publish(pool, store, b'{"retained": 1}')
        assert read_retained(pool, store, ref)[1] == b'{"retained": 1}'
        record = store.get_capture(*ids_of_ref(ref))
        body = next(p for p in capture_dir(root, record).iterdir() if p.name != RECORD_FILENAME)
        body.unlink()
        with pytest.raises(IntegrityError):
            read_retained(pool, store, ref)
        migrator.execute(EXPIRE, (ref.capture_ref_id,))
        with pytest.raises(OriginalExpiredError):
            read_retained(pool, store, ref)


def fenced(capture_ref_id: int) -> FencedCapture:
    """SYNTHETIC: a fenced intent capture."""
    sha = f"{capture_ref_id:064x}"
    return FencedCapture(
        capture_ref_id=capture_ref_id, source_id="nse", surface="NSE_XBRL_INSTANCE",
        request_key="k", capture_id="c", blob_sha256=sha, record_sha256=sha, url=None,
    )  # fmt: skip


JOURNAL = (
    JournalEvent(id=1, kind=JournalEventKind.FENCE, run_id=1, captures=(fenced(1), fenced(2))),
    JournalEvent(id=2, kind=JournalEventKind.COMPLETE, run_id=1, expired=(1,), cancelled=(2,)),
    JournalEvent(id=3, kind=JournalEventKind.FENCE, run_id=2, captures=(fenced(3), fenced(4))),
    JournalEvent(id=4, kind=JournalEventKind.FENCE, run_id=3, captures=(fenced(5),)),
    JournalEvent(id=5, kind=JournalEventKind.COMPLETE, run_id=3, expired=(5,)),
)


@pytest.mark.parametrize(
    ("watermark", "expected"),
    [(0, {1, 3, 4, 5}), (1, {1, 3, 4, 5}), (2, {3, 4, 5}), (3, {5}), (5, set())],
)
def test_expiries_after_a_watermark(watermark: int, expected: set[int]) -> None:
    """P13: completed runs give their expired ids (cancelled excluded), an unresolved fence all
    its captures; runs with no event above the watermark are ignored."""
    assert expiries_after(JOURNAL, watermark) == expected


def test_a_held_backup_waits_for_its_runs_completion(pg_db: PgTestDatabase, tmp_path: Path) -> None:
    """P14: ``held=`` refuses before the run's ``COMPLETE`` and succeeds after, with the
    watermark at that event; ``held=`` on a connection without the exclusive lock refuses."""
    out, conninfo = tmp_path / "sets", pg_db.conninfo(PgRole.MIGRATOR)

    def backup(held: psycopg.Connection | None = None) -> Path:
        return write_backup(
            pg_db.settings,
            database=pg_db.dbname,
            snapshot_root=tmp_path / "s",
            out_dir=out,
            held=held,
        )

    backup()
    with psycopg.connect(conninfo, autocommit=True) as purge:
        session_exclusive(purge)
        run = purge_run(purge, close=False)
        append_authority(out, JournalEvent(kind=JournalEventKind.FENCE, run_id=run))
        with pytest.raises(BackupError, match="unfinished"):
            backup(purge)
        append_authority(out, JournalEvent(kind=JournalEventKind.COMPLETE, run_id=run))
        assert verify_set(backup(purge)).journal_watermark == 2
        with psycopg.connect(conninfo, autocommit=True) as other:
            with pytest.raises(BackupError, match="exclusive"):
                backup(other)
        purge.execute(CLOSE_RUN, (run,))
