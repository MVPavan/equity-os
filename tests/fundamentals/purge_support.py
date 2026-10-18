"""Shared seams of the D9 Task 5 purge tests (plan D9 R8, U1-U15): an environment of a test
database, a store and a backup directory under ``tmp_path``; crash, pause and kill seams; seeds;
and a fake HTTP response. Captures are SYNTHETIC bytes unless copied from retained fixtures.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any

import psycopg
import pytest
from pg_evidence_schema_support import _insert
from pg_support import REPO_ROOT, PgTestDatabase
from retention_support import record_of, set_store_clock
from stage1_e2e_support import MANIFEST, SNAPSHOTS, Stage
from test_frozen_manifests import source

from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.retention import HoldRoot, JournalEventKind
from fundamentals.contracts.retention_purge import PurgeReport, PurgeStep
from fundamentals.contracts.snapshot import CaptureRecord, MissingSnapshotError
from fundamentals.evidence.capture_retention import capture_registration
from fundamentals.pg.backup import write_backup
from fundamentals.pg.retention_io import init_authority, read_authority
from fundamentals.pg.settings import PgRole
from fundamentals.retention.eligibility import add_months
from fundamentals.retention.purge import purge
from fundamentals.store.snapshot_store import SnapshotStore

VENDOR = ("tijori", "financials")
XBRL = ("nse", "NSE_XBRL_INSTANCE")
PDF = "NSE_RESULTS_PDF"
EXPIRED_REFUSAL = (psycopg.errors.ObjectNotInPrerequisiteState, psycopg.errors.RaiseException)
A05 = REPO_ROOT / "docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md"
STATE = "SELECT eqos.capture_state(%s)"
OPEN_RUNS = "SELECT count(*) FROM eqos.purge_runs r WHERE NOT EXISTS (SELECT 1 FROM " + (
    "eqos.purge_run_closures c WHERE c.run_id = r.id)"
)
KILLER = """import os, signal, sys
from pathlib import Path
from fundamentals.pg.backup import write_backup
from fundamentals.pg.role_secrets import load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.retention.purge import purge
db, root, sets, step = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
settings = PgSettings()
def kill(at):
    if at == step:
        os.kill(os.getpid(), signal.SIGKILL)
purge(settings, load_login(PgRole.PURGE, secrets_dir(os.environ)), database=db,
      snapshot_root=root, backup_dir=sets, pinned={}, fetch=None, checkpoint=kill,
      final_backup=lambda conn: write_backup(settings, database=db, snapshot_root=root,
                                             out_dir=sets, held=conn))
"""


class CrashError(Exception):
    """A raised crash at a purge checkpoint."""


class Env:
    """A test database, a snapshot store and a backup directory under ``tmp_path``."""

    def __init__(self, db: PgTestDatabase, pool: Any, tmp_path: Path) -> None:
        self.db, self.pool = db, pool
        self.root, self.sets = tmp_path / "store", tmp_path / "sets"
        self.store = SnapshotStore(self.root)

    def capture(
        self, body: bytes, kind: tuple[str, str] = VENDOR, url: str | None = None
    ) -> CaptureReference:
        """Store and register one capture, as an intake would."""
        record = self.store.put_capture(record_of(body, *kind), body)
        with capture_registration(self.pool) as registration:
            return registration.insert(ref_of(record), url=url)

    def sql(self, query: str, *params: object) -> list[tuple[Any, ...]]:
        """Rows of one statement as the migrator."""
        with self.db.migrator_connection() as conn:
            return conn.execute(query, params).fetchall()

    def age(self, months: int = 13) -> None:
        """Move the store clock past every class window."""
        with self.db.migrator_connection() as migrator:
            set_store_clock(migrator, add_months(datetime.now(UTC), months))

    def backup(self, held: psycopg.Connection | None = None, **options: Any) -> Path:
        """One backup set of the database and store into the backup directory."""
        return write_backup(
            self.db.settings,
            database=self.db.dbname,
            snapshot_root=self.root,
            out_dir=self.sets,
            held=held,
            **options,
        )

    def purge(
        self,
        fetch: Callable[[str], bytes] | None = None,
        checkpoint: Callable[[PurgeStep], None] = lambda step: None,
        *,
        final: bool = True,
        pinned: dict[HoldRoot, frozenset[str]] | None = None,
    ) -> PurgeReport:
        """One purge as the purge login, with a held final backup unless ``final`` is false."""
        return purge(
            self.db.settings,
            self.db.logins[PgRole.PURGE],
            database=self.db.dbname,
            snapshot_root=self.root,
            backup_dir=self.sets,
            pinned=pinned or {},
            fetch=fetch or no_fetch,
            final_backup=self.backup if final else None,
            checkpoint=checkpoint,
        )

    def state(self, ref: CaptureReference) -> str:
        """A capture's retention state."""
        return str(self.sql(STATE, ref.capture_ref_id)[0][0])

    def has_body(self, ref: CaptureReference) -> bool:
        """Whether the capture's body is in the store and verifies."""
        try:
            self.store.read_capture_verified(*ids(ref))
        except MissingSnapshotError:
            return False
        return True

    def journal(self, run_id: int) -> list[JournalEventKind]:
        """The expiry-journal event kinds of one run, in order."""
        return [e.kind for e in read_authority(self.sets).journal if e.run_id == run_id]


def ref_of(record: CaptureRecord) -> CaptureReference:
    """The unregistered reference of a stored capture."""
    assert record.body is not None
    now = datetime.now(UTC)
    request = record.request
    return CaptureReference(
        capture_ref_id=None,
        source_id=request.source_id,
        surface=request.surface,
        request_key=request.request_key,
        capture_id=record.capture_id,
        blob_sha256=record.body.content_sha256,
        record_sha256=record.record_sha256,
        registered_at=now,
        first_seen_at=now,
    )


def ids(ref: CaptureReference) -> tuple[str, str, str, str]:
    """A capture's store identity."""
    return ref.source_id, ref.surface, ref.request_key, ref.capture_id


def no_fetch(url: str) -> bytes:
    """A fetcher for purges with no eligible exchange capture."""
    raise AssertionError(f"unexpected fetch of {url}")


def crash_at(step: PurgeStep, seen: list[PurgeStep]) -> Callable[[PurgeStep], None]:
    """A checkpoint recording each step and raising at ``step``."""

    def checkpoint(at: PurgeStep) -> None:
        seen.append(at)
        if at is step:
            raise CrashError(step)

    return checkpoint


def pause_at(step: PurgeStep, reached: threading.Event, go: threading.Event) -> Any:
    """A checkpoint that signals ``reached`` at ``step`` and waits for ``go``."""

    def checkpoint(at: PurgeStep) -> None:
        if at is step and not reached.is_set():
            reached.set()
            assert go.wait(30)

    return checkpoint


@pytest.fixture
def env(pg_db: PgTestDatabase, tmp_path: Path) -> Iterator[Env]:
    """A fresh store and a new backup directory with its authority files."""
    with pg_db.runtime_pool() as pool:
        environment = Env(pg_db, pool, tmp_path)
        init_authority(environment.sets)
        yield environment


def assert_converged(env: Env, refs: list[CaptureReference], crashed_run: int) -> None:
    """U3: every capture has bytes iff it is not expired, the crashed run has exactly one
    FENCE then one COMPLETE, no run is open and no set remnant is left."""
    for ref in refs:
        assert env.has_body(ref) is (env.state(ref) != "EXPIRED"), ref.capture_ref_id
    assert env.journal(crashed_run) == [JournalEventKind.FENCE, JournalEventKind.COMPLETE]
    assert env.sql(OPEN_RUNS) == [(0,)]
    assert not [p for p in env.sets.iterdir() if p.is_dir() and p.name.startswith(".")]


def entity(conn: psycopg.Connection) -> int:
    """SEED: a reporting entity nobody has added to the watchlist."""
    evidence = {"kind": "ISSUER_IDENTITY", "label": "u2", "content_sha256": "e" * 64}
    row = {"entity_key": "u2-entity", "market": "IN", "display_name": "Unwatched"}
    return _insert(conn, "reporting_entities", row | {
        "evidence_input_id": _insert(conn, "evidence_inputs", evidence)})  # fmt: skip


def vendor_copy(stage: Stage, flag: str, root: Path) -> str:
    """Copy one retained vendor capture of the run into ``root``; return its label."""
    label = stage.run["vendor_inputs"][flag].split()[0]
    path = source(MANIFEST, label)[0]
    record, body = SnapshotStore(SNAPSHOTS).read_capture_verified(
        *path.relative_to(SNAPSHOTS).parts[:4]
    )
    SnapshotStore(root).put_capture(record, body)
    return label


class FakeResponse:
    """A response stand-in: announced length, chunks, then EOF or a raised read error."""

    def __init__(self, length: int | None, chunks: list[bytes | Exception]) -> None:
        self.headers = Message()
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self.chunks, self.status = chunks, 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int) -> bytes:
        chunk = self.chunks.pop(0) if self.chunks else b""
        if isinstance(chunk, Exception):
            raise chunk
        return chunk
