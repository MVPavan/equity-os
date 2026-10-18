"""D9 Task 6: re-fetch, ``REFETCH_MISMATCH`` and ``ORIGINAL_EXPIRED`` replay (plan D9 R9, R10,
R13; cases F1-F13).

Captures are SYNTHETIC bytes expired by a real purge unless a case names the Apar fixtures
(copied into ``tmp_path``). Fetches are fakes. F9-F11 SEED a vendor capture's ``EXPIRED`` state
directly: two Screener captures of the one retained page share a blob, which a purge expires
for both or neither.
"""

from __future__ import annotations

import socket
import threading
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from email.message import Message
from pathlib import Path
from typing import Any

import psycopg
import pytest
from pg_support import PgTestDatabase
from purge_support import XBRL, CrashError, Env, FakeResponse, entity, env, ids, no_fetch
from retention_support import package, retention_cli, verify
from stage1_e2e_support import RUNS, SCREENER, Stage
from test_retention_protocol import CLOSE_RUN, in_thread, locks, purge_run

from fundamentals.compare import run as compare_run
from fundamentals.compare.run import RunInputKind, RunRecord, load_results, replay_run
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.retention_purge import (
    FetchFailure,
    FetchFailureCategory,
    RefetchOutcome,
)
from fundamentals.evidence.capture_retention import ingest_vendor_retained, read_retained
from fundamentals.evidence.vendor_ingest import VendorIngestRequest
from fundamentals.pg.retention_io import init_authority
from fundamentals.pg.settings import PgRole
from fundamentals.retention import refetch as refetch_module
from fundamentals.retention.purge import INCIDENTS
from fundamentals.retention.refetch import ATTEMPT_PARAMETER, refetch
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg

__all__ = ["env"]

ARCHIVE = "https://nsearchives.nseindia.com/corporate/"
APAR = RUNS["APARINDS-Q2FY26"]
SCREENER_FLAG = "/".join(SCREENER)
ATTEMPTS = "SELECT outcome, category, http_status, fetched_sha256, severity FROM " + (
    "eqos.refetch_attempts WHERE capture_ref_id = %s ORDER BY id"
)
CAPTURE = "SELECT * FROM eqos.capture_refs WHERE id = %s"
CAPTURES = "SELECT count(*) FROM eqos.capture_refs"
NEW_CAPTURES = "SELECT id FROM eqos.capture_refs WHERE request_key LIKE %s || '.%%' ORDER BY id"
OF_SURFACE = "SELECT id FROM eqos.capture_refs WHERE surface = %s ORDER BY id"
ADDRESSED = (
    "SELECT r.id, a.url FROM eqos.capture_refs r "
    "JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id"
)
OCCURRENCES = "SELECT id, anchor_key FROM eqos.occurrences ORDER BY id"
VENDOR_ATTEMPTS = "SELECT count(*) FROM eqos.acquisition_attempts WHERE source_id = %s"
RUNS_COUNT = "SELECT count(*) FROM eqos.runs"
SEED_STATE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, %s)"
SEED_MATCH = (
    "INSERT INTO eqos.refetch_attempts (capture_ref_id, url, outcome, fetched_sha256) "
    "SELECT r.id, 'seed', 'MATCH', r.blob_sha256 FROM eqos.capture_refs r WHERE r.id = %s"
)
LICENCE_END = "INSERT INTO eqos.licence_ends (source_id) VALUES (%s)"
RESTORE = "SELECT eqos.restore_capture(%s)"
Apar = tuple[Stage, Env, CaptureReference, RunRecord, dict[str, bytes]]


def expire(env: Env, *items: tuple[bytes, tuple[str, str]]) -> list[CaptureReference]:
    """SYNTHETIC captures with addresses (exchange ones verified for an unwatched entity),
    aged and purged with probes served their own bytes: every one ends ``EXPIRED``."""
    served: dict[str, bytes] = {}
    refs = []
    with env.db.migrator_connection() as conn:
        unwatched = entity(conn)
        for body, kind in items:
            url = f"{ARCHIVE}{uuid.uuid4().hex}"
            ref = env.capture(body, kind, url=url)
            if kind == XBRL:
                verify(conn, package(conn, unwatched, int(ref.capture_ref_id or 0)))
            served[url], refs = body, [*refs, ref]
    env.age()
    env.purge(served.__getitem__)
    assert [env.state(ref) for ref in refs] == ["EXPIRED"] * len(refs)
    return refs


def serve(body: bytes) -> Callable[[str], bytes]:
    """A fetcher answering every address with ``body``."""
    return lambda url: body


def refetch_cli(
    monkeypatch: pytest.MonkeyPatch, env: Env, capture: int, fetch: Any, *extra: str
) -> int:
    """``retention refetch`` of one capture with ``fetch`` as the live fetcher."""
    monkeypatch.setattr("fundamentals.api.retention_cli.live_fetch", fetch)
    args = ("refetch", "--capture", str(capture), "--snapshot-root", str(env.root), *extra)
    return retention_cli(monkeypatch, env.db, *args)[0]


def test_a_paused_relink_holds_the_shared_transaction_lock(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1: transaction B relinks under the retention lock held shared for its transaction."""
    (ref,) = expire(env, (b"f1-xbrl", XBRL))
    reached, go = threading.Event(), threading.Event()
    relink = SnapshotStore.relink

    def paused(store: SnapshotStore, record: Any, body: bytes) -> Any:
        reached.set()
        assert go.wait(30)
        return relink(store, record, body)

    monkeypatch.setattr(SnapshotStore, "relink", paused)
    thread, outcome = in_thread(
        lambda: refetch(env.pool, env.store, int(ref.capture_ref_id or 0), serve(b"f1-xbrl"))
    )
    assert reached.wait(30)
    with env.db.migrator_connection() as migrator:
        assert locks(migrator) == [("ShareLock", True)]
        go.set()
        thread.join(30)
        assert outcome == [RefetchOutcome.RESTORED]
        assert locks(migrator) == []


def test_different_bytes_are_a_high_mismatch_and_a_new_capture(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3, F4 (rerun), F13: different bytes leave the capture EXPIRED, record a HIGH
    ``MISMATCH`` and publish them as a new capture whose request names the attempt; the dry run
    lists the open incident and the command exits 3. A rerun fetches nothing and adds nothing.
    The incident stays open until ``--retry`` fetches the original bytes and RESTORES it."""
    (ref,) = expire(env, (b"f3-original", XBRL))
    capture = int(ref.capture_ref_id or 0)
    assert refetch_cli(monkeypatch, env, capture, serve(b"f3-changed")) == 3
    assert env.state(ref) == "EXPIRED" and not env.has_body(ref)
    ((outcome, category, status, fetched, severity),) = env.sql(ATTEMPTS, capture)
    assert (outcome, category, status, severity) == ("MISMATCH", None, None, "HIGH")
    ((new,),) = env.sql(NEW_CAPTURES, ref.request_key)
    (row,) = env.sql(CAPTURE, new)
    record = env.store.get_capture(*row[1:5])
    attempt_id = env.sql("SELECT id FROM eqos.refetch_attempts")[0][0]
    assert (ATTEMPT_PARAMETER, str(attempt_id)) in {
        (p.name, p.value) for p in record.request.parameters
    }
    assert record.body is not None and record.body.content_sha256 == fetched
    assert env.store.read_capture_verified(*row[1:5])[1] == b"f3-changed"
    incident = ("REFETCH", attempt_id, "nse", capture, "MISMATCH")
    assert env.sql(INCIDENTS) == [incident]
    code, out = retention_cli(monkeypatch, env.db, "purge", "--dry-run")
    assert code == 0 and "incident\t" + "\t".join(map(str, incident)) in out
    before = env.sql(CAPTURES)
    assert refetch(env.pool, env.store, capture, no_fetch) is RefetchOutcome.REFETCH_MISMATCH
    assert env.sql(CAPTURES) == before and len(env.sql(ATTEMPTS, capture)) == 1
    assert env.sql(INCIDENTS) == [incident]
    assert refetch_cli(monkeypatch, env, capture, serve(b"f3-original"), "--retry") == 0
    assert env.state(ref) == "RESTORED" and env.has_body(ref) and env.sql(INCIDENTS) == []
    assert [a[0] for a in env.sql(ATTEMPTS, capture)] == ["MISMATCH", "MATCH"]


def test_a_crash_before_registration_reruns_under_the_same_attempt(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F4: a crash between the ``MISMATCH`` commit and registration; the rerun with the same
    bytes registers the new capture under that attempt, with no second attempt."""
    (ref,) = expire(env, (b"f4-original", XBRL))
    capture = int(ref.capture_ref_id or 0)

    def crash(pool: Any) -> Any:
        raise CrashError("registration")

    with monkeypatch.context() as crashing:
        crashing.setattr(refetch_module, "capture_registration", crash)
        with pytest.raises(CrashError):
            refetch(env.pool, env.store, capture, serve(b"f4-changed"))
    assert env.sql(NEW_CAPTURES, ref.request_key) == []
    assert refetch(env.pool, env.store, capture, serve(b"f4-changed")) is (
        RefetchOutcome.REFETCH_MISMATCH
    )
    assert len(env.sql(ATTEMPTS, capture)) == 1 and len(env.sql(NEW_CAPTURES, ref.request_key)) == 1


def test_a_retry_after_a_completed_mismatch_records_its_fetch(env: Env) -> None:
    """G5 (R10): ``retry`` after a completed mismatch fetching the same changed bytes records a
    new ``MISMATCH`` attempt and its own capture, so the history keeps every fetch."""
    (ref,) = expire(env, (b"g5-original", XBRL))
    capture = int(ref.capture_ref_id or 0)
    for _ in range(2):
        assert refetch(env.pool, env.store, capture, serve(b"g5-changed"), retry=True) is (
            RefetchOutcome.REFETCH_MISMATCH
        )
    assert [a[0] for a in env.sql(ATTEMPTS, capture)] == ["MISMATCH", "MISMATCH"]
    assert len(env.sql(NEW_CAPTURES, ref.request_key)) == 2


@pytest.mark.parametrize("purged", [False, True], ids=["rerun", "purged"])
def test_a_crash_after_relink_commits_on_rerun_or_is_purged(
    env: Env, monkeypatch: pytest.MonkeyPatch, purged: bool
) -> None:
    """F4: a crash after the relink, before ``RESTORED`` commits, leaves the capture EXPIRED with
    a body; a rerun commits RESTORED without fetching or a new attempt. Alternatively a purge
    removes the residue and a rerun fetches again."""
    (ref,) = expire(env, (b"f4-relinked", XBRL))
    capture = int(ref.capture_ref_id or 0)
    relink = SnapshotStore.relink

    def relink_then_crash(store: SnapshotStore, record: Any, body: bytes) -> Any:
        relink(store, record, body)
        raise CrashError("relinked")

    with monkeypatch.context() as crashing:
        crashing.setattr(SnapshotStore, "relink", relink_then_crash)
        with pytest.raises(CrashError):
            refetch(env.pool, env.store, capture, serve(b"f4-relinked"))
    assert env.state(ref) == "EXPIRED" and env.has_body(ref)
    if purged:
        env.purge()
        assert env.state(ref) == "EXPIRED" and not env.has_body(ref)
    fetch = serve(b"f4-relinked")
    assert refetch(env.pool, env.store, capture, fetch if purged else no_fetch) is (
        RefetchOutcome.RESTORED
    )
    assert env.state(ref) == "RESTORED" and env.has_body(ref)
    assert [a[0] for a in env.sql(ATTEMPTS, capture)] == ["MATCH"] * (2 if purged else 1)


@pytest.mark.parametrize(
    "failure",
    [
        FetchFailure(FetchFailureCategory.TIMEOUT),
        FetchFailure(FetchFailureCategory.HTTP_STATUS, 404),
        FetchFailure(FetchFailureCategory.INCOMPLETE),
    ],
    ids=["timeout", "non-200", "truncated"],
)
def test_a_failed_fetch_records_an_attempt_and_publishes_nothing(
    env: Env, monkeypatch: pytest.MonkeyPatch, failure: FetchFailure
) -> None:
    """F5: each failure records a ``FAILED`` attempt (category, status, no SHA-256, not HIGH),
    publishes nothing and exits 2."""
    (ref,) = expire(env, (b"f5-xbrl", XBRL))
    capture = int(ref.capture_ref_id or 0)
    before = env.sql(CAPTURES)

    def failing(url: str) -> bytes:
        raise failure

    assert refetch_cli(monkeypatch, env, capture, failing) == 2
    assert env.sql(ATTEMPTS, capture) == [
        ("FAILED", failure.category.value, failure.http_status, None, None)
    ]
    assert env.state(ref) == "EXPIRED" and not env.has_body(ref)
    assert env.sql(CAPTURES) == before and env.sql(INCIDENTS) == []


class Response(FakeResponse):
    """A response stand-in with an HTTP status and a raw Content-Length header."""

    def __init__(self, status: int, length: str | None, chunks: list[bytes | Exception]) -> None:
        super().__init__(None, chunks)
        self.status = status
        if length is not None:
            self.headers["Content-Length"] = length


def resolving(monkeypatch: pytest.MonkeyPatch, address: str = "1.1.1.1") -> None:
    """Every host resolves to ``address`` (no DNS in tests)."""
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    answer = [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: answer)


def answering(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[str]:
    """Every request is answered with ``answer`` (raised if an exception); the opened URLs."""
    opened: list[str] = []

    def fake_open(self: Any, url: str, timeout: float) -> Any:
        opened.append(url)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    return opened


@pytest.mark.parametrize(
    ("url", "address"),
    [
        ("file:///etc/hostname", "1.1.1.1"),
        ("ftp://nsearchives.nseindia.com/x", "1.1.1.1"),
        ("http://nsearchives.nseindia.com/x", "1.1.1.1"),
        ("https://example.com/x", "1.1.1.1"),
        ("https://nsearchives.nseindia.com:8443/x", "1.1.1.1"),
        ("https://user@nsearchives.nseindia.com/x", "1.1.1.1"),
        ("https://nsearchives.nseindia.com/x", "127.0.0.1"),
        ("https://nsearchives.nseindia.com/x", "10.1.2.3"),
        ("https://nsearchives.nseindia.com/x", "169.254.169.254"),
        ("https://nsearchives.nseindia.com/x", "::1"),
    ],
)
def test_live_fetch_refuses_an_unapproved_address_before_opening_it(
    monkeypatch: pytest.MonkeyPatch, url: str, address: str
) -> None:
    """F4 (R10): only HTTPS to an approved exchange host, resolving to public addresses only,
    is opened; anything else (local files, other schemes, hosts, ports, private, loopback or
    link-local destinations) is ``REFUSED_ADDRESS`` with no request made."""
    resolving(monkeypatch, address)
    opened = answering(monkeypatch, Response(200, "1", [b"x"]))
    with pytest.raises(FetchFailure) as failure:
        refetch_module.live_fetch(url)
    assert failure.value.category is FetchFailureCategory.REFUSED_ADDRESS and opened == []


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (Response(206, "5", [b"whole"]), (FetchFailureCategory.HTTP_STATUS, 206)),
        (Response(200, "five", [b"whole"]), (FetchFailureCategory.INCOMPLETE, None)),
        (Response(200, "-5", [b"whole"]), (FetchFailureCategory.INCOMPLETE, None)),
        (
            urllib.error.HTTPError("u", 302, "Found", Message(), None),
            (FetchFailureCategory.HTTP_STATUS, 302),
        ),
    ],
    ids=["partial-content", "malformed-length", "negative-length", "redirect"],
)
def test_a_non_200_or_malformed_answer_is_a_failed_attempt(
    env: Env, monkeypatch: pytest.MonkeyPatch, answer: Any, expected: Any
) -> None:
    """F15 (R10): through the live fetcher, a non-200 status (206, a refused redirect) or an
    invalid Content-Length is a categorised ``FAILED`` attempt that publishes nothing; a
    complete 200 body restores."""
    (ref,) = expire(env, (b"whole", XBRL))
    capture = int(ref.capture_ref_id or 0)
    resolving(monkeypatch)
    answering(monkeypatch, answer)
    assert refetch_cli(monkeypatch, env, capture, refetch_module.live_fetch) == 2
    assert env.sql(ATTEMPTS, capture) == [("FAILED", expected[0].value, expected[1], None, None)]
    assert env.state(ref) == "EXPIRED" and not env.has_body(ref)
    answering(monkeypatch, Response(200, "5", [b"whole"]))
    assert refetch_cli(monkeypatch, env, capture, refetch_module.live_fetch) == 0
    assert env.state(ref) == "RESTORED"


@pytest.mark.parametrize("stale", [False, True], ids=["pending-run", "stale-snapshot"])
def test_restore_capture_takes_the_retention_protocol(env: Env, stale: bool) -> None:
    """F3 (RP1, RP2): runtime SQL restoring an expired capture with a matching attempt is
    refused while a purge run is open, and when its snapshot predates a committed purge; once
    neither holds, the same call restores."""
    (ref,) = expire(env, (b"f3-sql", XBRL))
    capture = int(ref.capture_ref_id or 0)
    refused = (
        pytest.raises(psycopg.errors.SerializationFailure, match="STALE_SNAPSHOT")
        if stale
        else pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="PURGE_PENDING")
    )
    with env.db.migrator_connection() as migrator:
        migrator.execute(SEED_MATCH, (capture,))
        run = None if stale else purge_run(migrator, close=False)
        with psycopg.connect(env.db.conninfo(PgRole.RUNTIME)) as conn:
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            with refused, conn.transaction():
                conn.execute("SELECT 1")  # takes the transaction snapshot
                if stale:
                    purge_run(migrator)
                conn.execute(RESTORE, (capture,))
        if run is not None:
            migrator.execute(CLOSE_RUN, (run,))
    assert env.state(ref) == "EXPIRED"
    with env.pool.connection() as conn:
        conn.execute(RESTORE, (capture,))
    assert env.state(ref) == "RESTORED"


def test_vendor_identity_and_licence_ended_captures_are_not_refetchable(env: Env) -> None:
    """F6: a vendor capture, an Upstox instrument capture and a licence-ended source's capture
    are ``NOT_REFETCHABLE`` without a fetch; a direct RESTORED insert without a matching
    attempt is refused for them and for an exchange capture."""
    refs = expire(
        env,
        (b"f6-screener", SCREENER),
        (b"f6-instruments", ("upstox", "instruments")),
        (b"f6-tijori", ("tijori", "financials")),
        (b"f6-xbrl", XBRL),
    )
    with env.db.migrator_connection() as conn:
        conn.execute(LICENCE_END, ("tijori",))
    for ref in refs[:3]:
        capture = int(ref.capture_ref_id or 0)
        assert refetch(env.pool, env.store, capture, no_fetch) is RefetchOutcome.NOT_REFETCHABLE
    for ref in refs:
        with (
            env.db.migrator_connection() as conn,
            pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="NOT_REFETCHABLE"),
        ):
            conn.execute(SEED_STATE, (ref.capture_ref_id, "RESTORED"))
    assert [env.state(ref) for ref in refs] == ["EXPIRED"] * 4


# --- Apar fixtures --------------------------------------------------------------------------


@pytest.fixture
def apar(pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Apar]:
    """The Apar first-party package and a first-party-only run that verifies it, then a purge
    (probes served the stored bytes) that expires the XBRL capture at its manifest address. The
    run routes no queue items: a queue item would hold the capture (R4)."""
    monkeypatch.setattr(compare_run, "route_run", lambda *_: ())
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, APAR)
        env = Env(pg_db, pool, tmp_path)
        init_authority(env.sets)
        stage.first_party()
        ((xbrl_id,),) = env.sql(OF_SURFACE, XBRL[1])
        (xbrl,) = stage.repository.get_capture_refs([xbrl_id])
        run = stage.execute(vendors=[])
        served = {
            url: env.store.read_capture_verified(*ids(ref))[1]
            for capture, url in env.sql(ADDRESSED)
            for ref in stage.repository.get_capture_refs([capture])
        }
        assert xbrl_id in dict(env.sql(ADDRESSED))
        env.age()
        env.purge(served.__getitem__)
        assert env.state(xbrl) == "EXPIRED" and not env.has_body(xbrl)
        yield stage, env, xbrl, run, served


@pytest.mark.retained
def test_equal_bytes_restore_the_capture_and_reingest_reuses_it(
    apar: Apar,
) -> None:
    """F2, F13: after the purge the same bytes give RESTORED for every expired member:
    ``capture_refs`` unchanged (ids, first-seen times), verified reads, and a first-party
    re-ingest reuses the captures, inserting no occurrence and keeping the stored anchor keys;
    the incident list is unchanged."""
    stage, env, xbrl, _, served = apar
    expired = [c for c, _ in env.sql(ADDRESSED)]
    rows, occurrences = [env.sql(CAPTURE, c) for c in expired], env.sql(OCCURRENCES)
    incidents = env.sql(INCIDENTS)
    fetch = served.__getitem__
    outcomes = {refetch(env.pool, env.store, capture, fetch) for capture in expired}
    assert outcomes == {RefetchOutcome.RESTORED} and xbrl.capture_ref_id in expired
    assert [env.sql(CAPTURE, c) for c in expired] == rows and env.state(xbrl) == "RESTORED"
    record, body = read_retained(env.pool, env.store, xbrl)
    assert record.body is not None and record.body.content_sha256 == xbrl.blob_sha256
    stage.first_party()
    assert env.sql(OF_SURFACE, XBRL[1]) == [(xbrl.capture_ref_id,)]
    assert env.sql(OCCURRENCES) == occurrences and env.sql(INCIDENTS) == incidents


@pytest.mark.retained
def test_first_party_intake_of_expired_bytes_is_a_new_capture(
    apar: Apar,
) -> None:
    """F8: intake of the expired capture's bytes registers a new capture with its body; the
    expired one stays EXPIRED without one."""
    stage, env, xbrl, *_ = apar
    stage.first_party()
    (old, new) = [capture for (capture,) in env.sql(OF_SURFACE, XBRL[1])]
    assert old == xbrl.capture_ref_id and env.state(xbrl) == "EXPIRED" and not env.has_body(xbrl)
    (fresh,) = stage.repository.get_capture_refs([new])
    assert fresh.blob_sha256 == xbrl.blob_sha256 and env.has_body(fresh)


@pytest.mark.retained
def test_a_first_party_run_over_the_expired_xbrl_replays(
    apar: Apar,
) -> None:
    """F12: exchange rows decode unchanged, so the first-party-only run replays equal."""
    stage, _, _, run, _ = apar
    replayed = replay_run(run.run_id, pool=stage.pool, config_root=stage.config_root)
    assert replayed == load_results(run.run_id, pool=stage.pool)


@pytest.mark.retained
def test_vendor_ingest_of_an_expired_capture_writes_nothing(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """F7: after a purge expires the Screener capture, ``ingest_vendor_retained`` over it
    raises ``ORIGINAL_EXPIRED`` before ``ingest_vendor`` writes an attempt."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, APAR)
        env = Env(pg_db, pool, tmp_path)
        env.root = tmp_path / "staged"  # where the harness stages Screener
        env.store = SnapshotStore(env.root)
        init_authority(env.sets)
        stage.vendor(SCREENER_FLAG, "A-SCR")
        ((capture,),) = env.sql(OF_SURFACE, SCREENER[1])
        (ref,) = stage.repository.get_capture_refs([capture])
        env.age()
        env.purge()
        assert env.state(ref) == "EXPIRED"
        before = env.sql(VENDOR_ATTEMPTS, SCREENER[0])
        request = VendorIngestRequest(
            source_id=ref.source_id,
            surface=ref.surface,
            request_key=ref.request_key,
            capture_id=ref.capture_id,
            representation=Representation.HTML,
            entity_id=stage.entity_id,
            period_end=stage.end,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
        )
        with pytest.raises(OriginalExpiredError, match=f"ORIGINAL_EXPIRED: capture {capture}"):
            ingest_vendor_retained(request, repository=stage.repository, extract=no_fetch)
        assert env.sql(VENDOR_ATTEMPTS, SCREENER[0]) == before


@pytest.fixture
def two_screener(
    pg_db: PgTestDatabase, tmp_path: Path
) -> Iterator[tuple[Stage, list[int], RunRecord]]:
    """The Apar package and two Screener captures (older, newer) of the one page, and a run
    selecting the newer."""
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, APAR)
        stage.first_party()
        stage.vendor(SCREENER_FLAG, "A-SCR")
        stage.vendor(SCREENER_FLAG, "A-SCR")
        with pg_db.migrator_connection() as conn:
            captures = [c for (c,) in conn.execute(OF_SURFACE, (SCREENER[1],)).fetchall()]
        run = stage.execute(vendors=[SCREENER_FLAG])
        chosen = {
            i.ref_id: i.disposition
            for i in run.manifest.inputs
            if i.kind is RunInputKind.CAPTURE_REF
        }
        assert [chosen[c] for c in captures] == ["NOT_SELECTED", "SELECTED"]
        yield stage, captures, run


def seed_expired(db: PgTestDatabase, capture: int) -> None:
    """SEED: one capture's ``EXPIRED`` state, its bytes left in place (see module docstring)."""
    with db.migrator_connection() as conn:
        conn.execute(SEED_STATE, (capture, "EXPIRED"))


@pytest.mark.retained
def test_an_expired_older_attempt_is_dropped_from_a_new_run(
    two_screener: tuple[Stage, list[int], RunRecord],
) -> None:
    """F9, F11 (not selected): with the older capture expired, replaying the run that read it
    raises; a new run selects the newer, its manifest holds neither the older capture nor its
    attempts, it publishes and replays equal to its results."""
    stage, (older, _), run = two_screener
    seed_expired(stage.pg_db, older)
    with pytest.raises(OriginalExpiredError, match=f"ORIGINAL_EXPIRED: run {run.run_id}"):
        replay_run(run.run_id, pool=stage.pool, config_root=stage.config_root)
    fresh = stage.execute(vendors=[SCREENER_FLAG])
    assert fresh.created and fresh.run_id != run.run_id
    older_attempts = {
        a.attempt_id
        for a in stage.repository.list_attempts(stage.entity_id, stage.end)
        if a.capture is not None and a.capture.capture_ref_id == older
    }
    assert older_attempts
    kept = {(i.kind, i.ref_id) for i in fresh.manifest.inputs}
    assert (RunInputKind.CAPTURE_REF, older) not in kept
    assert not {(RunInputKind.ATTEMPT, a) for a in older_attempts} & kept
    replayed = replay_run(fresh.run_id, pool=stage.pool, config_root=stage.config_root)
    assert replayed == load_results(fresh.run_id, pool=stage.pool)


@pytest.mark.retained
def test_an_expired_latest_attempt_refuses_the_run_without_fallback(
    two_screener: tuple[Stage, list[int], RunRecord],
) -> None:
    """F10, F11 (selected): with the newer capture expired and the older retained, a run
    raises ``OriginalExpiredError`` naming the newer and publishes nothing; replaying the run
    that selected it raises."""
    stage, (_, newer), run = two_screener
    seed_expired(stage.pg_db, newer)
    with stage.pg_db.migrator_connection() as conn:
        before = conn.execute(RUNS_COUNT).fetchall()
    with pytest.raises(OriginalExpiredError, match=rf"captures \[{newer}\]"):
        stage.execute(vendors=[SCREENER_FLAG])
    with stage.pg_db.migrator_connection() as conn:
        assert conn.execute(RUNS_COUNT).fetchall() == before
    with pytest.raises(OriginalExpiredError, match="ORIGINAL_EXPIRED"):
        replay_run(run.run_id, pool=stage.pool, config_root=stage.config_root)
