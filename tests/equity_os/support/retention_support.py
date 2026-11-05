"""Shared fixtures of the D9 retention tests (plan D9, verification cases).

Captures written here are SYNTHETIC registrations (random hashes, no stored bytes) unless a test
publishes real bytes through an intake path.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from ledger_support import Ledger
from pg_support import (
    MIGRATIONS_DIR,
    REPO_ROOT,
    PgTestDatabase,
    create_database,
    drop_database,
    mint_name,
)
from psycopg import sql

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.sourcing.acquisition_outcome import OutcomeCode, OutcomeRecord
from equity_os.contracts.sourcing.snapshot import (
    A05_DECISION_005,
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
)
from equity_os.contracts.storage.retention import CaptureFacts, Eligibility, HoldRoot
from equity_os.interface.entry.cli import main
from equity_os.storage.backup.restore_check import Rows
from equity_os.storage.database.migrations import apply_migrations
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import BLOBS_DIRNAME, SnapshotStore
from equity_os.storage.records import repository_rows as rows_sql
from equity_os.storage.records import store as ledger_store
from equity_os.storage.retention.eligibility import add_months, eligibility
from equity_os.storage.retention.holds import capture_facts
from equity_os.storage.retention.purge_first import restore_purge_first

# The tables the retention migrations add; each D9 migration extends this in its own change.
RETENTION_TABLES = frozenset(
    {"retention_classes", "capture_addresses", "licence_ends"}
    | {"capture_states", "purge_runs", "purge_run_closures"}
    | {"purge_records", "retention_probes"}
    | {"refetch_attempts"}
)
FIRST_RETENTION_MIGRATION = "0027_retention_classes.sql"
CLASS_OF = (
    "SELECT r.source_id, r.surface, c.retention_class, c.cause FROM eqos.capture_refs r "
    "LEFT JOIN eqos.retention_classes c ON c.capture_ref_id = r.id WHERE r.id = %s"
)
ADDRESS_OF = "SELECT url FROM eqos.capture_addresses WHERE capture_ref_id = %s"
CONFIG = REPO_ROOT / "config"
LATER_MONTHS = 13  # the cases' clock: past every class window
NO_PINS: dict[HoldRoot, frozenset[str]] = {}
_ADDRESS = "INSERT INTO eqos.capture_addresses (capture_ref_id, url) VALUES (%s, %s)"
_PACKAGE = """WITH p AS (
    INSERT INTO eqos.filing_packages (entity_id, family, reporting_period_end, basis, framework,
        reporting_kind, knowledge_time, evidence_sha256)
    VALUES (%(entity)s, 'FINANCIAL_RESULTS', '2025-09-30', 'CONSOLIDATED', 'IND_AS', 'QUARTER',
        now(), %(nonce)s) RETURNING id)
INSERT INTO eqos.package_members (package_id, capture_ref_id, representation, knowledge_time,
    knowledge_time_raw, knowledge_time_status)
SELECT id, %(capture)s, 'XBRL', now(), 'fixture', 'KNOWN' FROM p RETURNING package_id"""
_VERIFY = """WITH r AS (
    INSERT INTO eqos.runs (identity_hash, cutoff, mode, status, code_version, manifest,
        manifest_sha256)
    VALUES (%(nonce)s, now(), 'AS_KNOWN', 'COMPLETE', 'fixture', '{}', %(nonce)s) RETURNING id)
INSERT INTO eqos.run_inputs (run_id, input_kind, disposition, package_id)
SELECT id, 'PACKAGE', 'SELECTED', %(package)s FROM r"""
_ITEM = """INSERT INTO eqos.queue_items (run_id, pair_identity, outcome, input_sha256, severity,
    diagnostic, routing_reason, source_refs)
VALUES (%s, %s, 'UNMAPPED', %s, 'HIGH', false, 'MAPPING_DEFINITION_OR_SOURCE_ERROR', '[]')
RETURNING id"""
_DISPOSE = """INSERT INTO eqos.queue_dispositions (item_id, kind, reason, decider, evidence_ref)
VALUES (%s, 'DISMISSED', 'fixture', 'fixture-owner', 'fixture')"""
_SET_CLOCK = "SELECT setval('eqos.store_clock_us', %s, true)"
OUTCOME = OutcomeRecord(code=OutcomeCode.OK, native_kind="synthetic.Kind", native_value="OK")
RETRIEVED = datetime(2026, 10, 1, tzinfo=UTC)
LOCKS = (
    "SELECT mode, granted FROM pg_locks WHERE locktype = 'advisory' AND objsubid = 1 "
    "AND database = (SELECT oid FROM pg_database WHERE datname = current_database()) "
    "AND (classid::bigint << 32 | objid::bigint) = eqos.retention_lock_key() ORDER BY mode"
)
PAUSE = 'touch "$0.paused"; while [ ! -e "$0.go" ]; do sleep 0.05; done; exec "$@"'


def synthetic(source_id: str, surface: str) -> CaptureReference:
    """SYNTHETIC: an unregistered capture reference with random hashes, registered now."""
    now = datetime.now(UTC)
    return CaptureReference(
        capture_ref_id=None,
        source_id=source_id,
        surface=surface,
        request_key=uuid.uuid4().hex,
        capture_id=uuid.uuid4().hex,
        blob_sha256=uuid.uuid4().hex * 2,
        record_sha256=uuid.uuid4().hex * 2,
        registered_at=now,
        first_seen_at=now,
    )


def class_of(conn: psycopg.Connection, capture_ref_id: int | None) -> tuple[str | None, str | None]:
    """A capture's stored class and cause, ``(None, None)`` when unclassified."""
    row = conn.execute(CLASS_OF, (capture_ref_id,)).fetchone()
    assert row is not None
    return row[2], row[3]


def address_of(conn: psycopg.Connection, capture_ref_id: int | None) -> str | None:
    """A capture's recorded address, if any."""
    row = conn.execute(ADDRESS_OF, (capture_ref_id,)).fetchone()
    return None if row is None else str(row[0])


@pytest.fixture
def pre_retention_db(
    pg_template: PgTestDatabase, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[PgTestDatabase, psycopg.Connection]]:
    """A database migrated up to, not including, 0027, with an open migrator connection; the
    caller applies the rest through :func:`finish_migrations`."""
    settings = pg_template.settings
    name = mint_name(settings)
    create_database(settings, name)
    earlier = tmp_path_factory.mktemp("pre_retention_migrations")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name < FIRST_RETENTION_MIGRATION:
            shutil.copy(path, earlier / path.name)
    database = pg_template.model_copy(update={"dbname": name})
    try:
        with psycopg.connect(
            settings.conninfo(PgRole.MIGRATOR, dbname=name), autocommit=True
        ) as migrator:
            apply_migrations(migrator, earlier)
            yield database, migrator
    finally:
        drop_database(settings, name)


def finish_migrations(migrator: psycopg.Connection) -> None:
    """Apply every remaining migration, 0027 included."""
    apply_migrations(migrator, MIGRATIONS_DIR)


def register(
    conn: psycopg.Connection,
    source_id: str,
    surface: str,
    *,
    blob: str | None = None,
    url: str | None = None,
) -> int:
    """SYNTHETIC: register a capture now (``blob`` if given), with an address if ``url``."""
    ref = synthetic(source_id, surface)
    ref = ref if blob is None else ref.model_copy(update={"blob_sha256": blob})
    row = conn.execute(rows_sql.INSERT_CAPTURE_REF + " RETURNING id", rows_sql.capture_params(ref))
    ((capture_ref_id,),) = row.fetchall()
    if url is not None:
        conn.execute(_ADDRESS, (capture_ref_id, url))
    return int(capture_ref_id)


def package(conn: psycopg.Connection, entity_id: int, capture_ref_id: int) -> int:
    """SEED: a filing package of ``entity_id`` whose XBRL member is the capture."""
    nonce = uuid.uuid4().hex * 2
    params = {"entity": entity_id, "capture": capture_ref_id, "nonce": nonce}
    ((package_id,),) = conn.execute(_PACKAGE, params).fetchall()
    return int(package_id)


def verify(conn: psycopg.Connection, package_id: int) -> None:
    """SEED: a ``COMPLETE`` run selecting the package, which verifies its members now (R5)."""
    conn.execute(_VERIFY, {"nonce": uuid.uuid4().hex * 2, "package": package_id})


def open_item(conn: psycopg.Connection, run_id: int, **evidence: int) -> int:
    """SEED: an undisposed queue item of ``run_id`` sealed in its transaction with one evidence
    row: an ``occurrence_id``/``interpretation_id``/``attempt_id`` input or a trace."""
    table = "queue_item_traces" if "calculation_trace_id" in evidence else "queue_item_inputs"
    columns = sql.SQL(", ").join(map(sql.Identifier, ["item_id", *evidence]))
    insert = sql.SQL("INSERT INTO eqos.{} ({}) VALUES (%s, %s)").format(
        sql.Identifier(table), columns
    )
    with conn.transaction():
        row = conn.execute(_ITEM, (run_id, uuid.uuid4().hex, uuid.uuid4().hex)).fetchone()
        assert row is not None
        conn.execute(insert, (row[0], *evidence.values()))
    return int(row[0])


def dispose(owner: psycopg.Connection, item_id: int) -> None:
    """The owner's disposition of a queue item."""
    owner.execute(_DISPOSE, (item_id,))


def facts_of(
    conn: psycopg.Connection, capture_ref_id: int, pinned: dict[HoldRoot, frozenset[str]] = NO_PINS
) -> CaptureFacts:
    """One capture's retention facts."""
    return next(f for f in capture_facts(conn, pinned) if f.capture_ref_id == capture_ref_id)


def later() -> datetime:
    """The cases' evaluation time: :data:`LATER_MONTHS` from now."""
    return add_months(datetime.now(UTC), LATER_MONTHS)


def verdict(
    conn: psycopg.Connection, capture_ref_id: int, pinned: dict[HoldRoot, frozenset[str]] = NO_PINS
) -> Eligibility:
    """One capture's eligibility at :func:`later`."""
    return eligibility(facts_of(conn, capture_ref_id, pinned), later())


def set_store_clock(migrator: psycopg.Connection, at: datetime) -> None:
    """Advance the store clock to ``at`` (R5: tests move ``eqos.store_clock_us``)."""
    migrator.execute(_SET_CLOCK, (int(at.timestamp() * 1_000_000),))


def retention_cli(
    monkeypatch: pytest.MonkeyPatch, database: PgTestDatabase, *argv: str
) -> tuple[int, str]:
    """``fundamentals retention <argv>`` against ``database``: exit code and stdout."""
    for name, value in database.cli_env().items():
        monkeypatch.setenv(name, value)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["retention", *argv])
    return code, out.getvalue()


def restore_args(
    database: PgTestDatabase,
    set_dir: Path,
    snapshot_root: Path,
    backup_dir: Path | None = None,
    *,
    live: Path | None,
) -> dict[str, Any]:
    """Restore's retention arguments (plan D9 R12): the authority directory (default the set's
    parent), the live head witness (``None``: unwitnessed), the session purge login and the
    composed purge-first."""
    backup_dir = backup_dir or set_dir.parent
    return {
        "backup_dir": backup_dir,
        "live_snapshot_root": live,
        "purge_login": database.logins[PgRole.PURGE],
        "purge_first": restore_purge_first(set_dir, backup_dir, snapshot_root, live),
    }


def register_body_absent(conn: psycopg.Connection, root: Path) -> int:
    """SYNTHETIC: publish under ``root`` and register a body-absent transport failure the way the
    VS fetcher records one (no body, ``blob_sha256`` of no bytes); returns its capture ref id."""
    request = RequestIdentity(
        source_id="screener-subscriber", surface="vs.market-level", request_key=uuid.uuid4().hex,
        parameters=(),
    )  # fmt: skip
    failed = OutcomeRecord(
        code=OutcomeCode.TRANSPORT_ERROR, native_kind="synthetic.Kind", native_value="timeout"
    )
    record = CaptureRecord.make(
        request, RETRIEVED, None, None, None, None, failed,
        SnapshotRights(authority_refs=(A05_DECISION_005,)),
        schema_version=CAPTURE_SCHEMA_VERSION, body_completeness=BodyCompleteness.ABSENT,
    )  # fmt: skip
    SnapshotStore(root).put_capture(record, None)
    ref = synthetic(request.source_id, request.surface).model_copy(
        update={
            "request_key": request.request_key,
            "capture_id": record.capture_id,
            "blob_sha256": hashlib.sha256(b"").hexdigest(),
            "record_sha256": record.record_sha256,
        }
    )
    row = conn.execute(rows_sql.INSERT_CAPTURE_REF + " RETURNING id", rows_sql.capture_params(ref))
    ((capture_ref_id,),) = row.fetchall()
    return int(capture_ref_id)


def record_of(body: bytes, source_id: str = "nse", surface: str = "NSE_XBRL_INSTANCE") -> Any:
    """SYNTHETIC: a capture record of ``body`` on a fresh route."""
    request = RequestIdentity(
        source_id=source_id, surface=surface, request_key=uuid.uuid4().hex, parameters=()
    )
    blob = BlobRef(
        source_id=source_id, content_sha256=hashlib.sha256(body).hexdigest(), byte_count=len(body)
    )
    return CaptureRecord.make(
        request=request,
        retrieved_at=RETRIEVED,
        http_status=200,
        media_type="application/json",
        content_encoding=None,
        body=blob,
        outcome=OUTCOME,
        rights=SnapshotRights(authority_refs=(A05_DECISION_005,)),
    )


def link_of(record: CaptureRecord) -> tuple[str, str, str]:
    """A capture's ``(surface, request_key, capture_id)`` body-link key."""
    return record.request.surface, record.request.request_key, record.capture_id


def ids_of(record: CaptureRecord) -> tuple[str, str, str, str]:
    """A capture's store identity."""
    return (record.request.source_id, *link_of(record))


def capture_dir(root: Path, record: CaptureRecord) -> Path:
    """A capture's directory under ``root``."""
    return root.joinpath(*ids_of(record))


def blob_path(root: Path, record: CaptureRecord) -> Path:
    """A capture's content-addressed blob under ``root``."""
    assert record.body is not None
    sha = record.body.content_sha256
    return root / BLOBS_DIRNAME / record.request.source_id / sha[:2] / sha


def locks(conn: psycopg.Connection) -> list[tuple[str, bool]]:
    """The retention lock's holders and waiters in this database."""
    return [(str(mode), bool(granted)) for mode, granted in conn.execute(LOCKS).fetchall()]


def wait_for(check: Callable[[], bool], seconds: float = 20.0) -> None:
    """Poll ``check`` until it holds, failing after ``seconds``."""
    deadline = time.monotonic() + seconds
    while not check():
        assert time.monotonic() < deadline, "condition never held"
        time.sleep(0.05)


def in_thread(target: Callable[[], Any]) -> tuple[threading.Thread, list[Any]]:
    """Start ``target`` in a thread; the list receives its result or exception."""
    outcome: list[Any] = []

    def run() -> None:
        try:
            outcome.append(target())
        except Exception as error:  # noqa: BLE001 - handed to the asserting thread
            outcome.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def draft_claim(ledger: Ledger, conn: psycopg.Connection) -> int:
    """A draft version with one claim, inserted on ``conn`` in its open transaction."""
    draft = ledger.version_draft(ledger.report())
    with conn.cursor() as cursor:
        return ledger_store.create_version(cursor, draft)


DELTA_DAMAGE = {
    "unrelated trace": ("calculation_traces", 2),
    "unrelated operand": ("calculation_trace_operands", 2),
    "unrelated result value": ("result_source_values", 2),
    "omitted closure trace": ("calculation_traces", 11),
    "not vendor": ("retention_classes", 1),
}


def delta_world(damage: str) -> tuple[Rows, Rows]:
    """SYNTHETIC: VENDOR captures 1 (expired) and 2 (kept), each with an interpretation, its
    construction trace, trace 10 + c fed from it through an operand and a vendor result value.
    Returns the pre-purge rows and the rows with exactly capture 1's tombstones (0029), then
    ``damage`` applied."""
    pay, both = {"value": 1, "lower": 0, "upper": 2}, (1, 2)
    exact = pay | {"exact_value": 1, "exact_lower": 0, "exact_upper": 2}
    operand = {"interpretation_id": None}
    vendor = {"source_role": "INDEPENDENT_VENDOR", "calculation_trace_id": None}
    before: Rows = {
        "occurrences": {},
        "acquisition_attempts": {},
        "retention_classes": {c: {"capture_ref_id": c, "retention_class": "VENDOR"} for c in both},
        "interpretations": {
            c: pay | {"capture_ref_id": c, "transform_trace": {"k": c}} for c in both
        },
        "construction_traces": {
            c: {"interpretation_id": c, "calculation_trace_id": c} for c in both
        },
        "calculation_traces": {t: exact for t in (1, 2, 11, 12)},
        "calculation_trace_operands": {
            c: exact | operand | {"calculation_trace_id": 10 + c, "operand_trace_id": c}
            for c in both
        },
        "result_source_values": {c: pay | vendor | {"interpretation_id": c} for c in both},
    }
    after = {table: dict(rows) for table, rows in before.items()}
    blank = {"interpretations": dict.fromkeys(pay) | {"transform_trace": {}}}
    blank["result_source_values"] = dict.fromkeys(pay)
    for table in ("interpretations", "calculation_traces", "calculation_trace_operands"):
        after[table][1] = before[table][1] | blank.get(table, dict.fromkeys(exact))
    after["calculation_traces"][11] = exact | dict.fromkeys(exact)
    after["result_source_values"][1] = (
        before["result_source_values"][1] | blank["result_source_values"]
    )
    table, key = DELTA_DAMAGE.get(damage, ("", 0))
    if damage.startswith("unrelated"):
        after[table][key] = before[table][key] | blank.get(table, dict.fromkeys(exact))
    elif damage == "omitted closure trace":
        after[table][key] = before[table][key]
    elif damage == "not vendor":
        before[table][key] = after[table][key] = {
            "capture_ref_id": 1,
            "retention_class": "EXCHANGE",
        }
    return before, after
