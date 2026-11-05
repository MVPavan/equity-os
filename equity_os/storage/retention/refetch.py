"""Fetching an expired exchange original back from its address (plan D9 R8 step 1, R10):
:func:`live_fetch` (the one network path), :func:`probe` before deletion, :func:`refetch`."""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from equity_os.contracts.measurement.evidence import CaptureReference
from equity_os.contracts.sourcing.snapshot import (
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    MissingSnapshotError,
    RequestParameter,
    derive_capture_id,
)
from equity_os.contracts.storage.retention import CaptureFacts
from equity_os.contracts.storage.retention_purge import (
    FetchFailure,
    FetchFailureCategory,
    ProbeOutcome,
    RefetchOutcome,
)
from equity_os.sourcing.transport.http_session import NoRedirectHandler, read_bounded_capture
from equity_os.storage.raw_files.capture_retention import capture_registration
from equity_os.storage.raw_files.snapshot_store import MAX_BODY_BYTES, SnapshotStore

Fetch = Callable[[str], bytes]
# The exchange hosts first-party captures are fetched from; any other address is refused.
APPROVED_HOSTS = frozenset(
    {"www.nseindia.com", "nsearchives.nseindia.com", "www.bseindia.com", "api.bseindia.com"}
)
REFETCH_TIMEOUT_SECONDS = 60.0
PROBE_SAMPLE = 3
_INSERT_PROBE: LiteralString = (
    "INSERT INTO eqos.retention_probes (source_id, capture_ref_id, url, outcome, category, "
    "http_status, fetched_sha256, severity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
ATTEMPT_PARAMETER = "refetch_attempt"
# A capture with its address and latest attempt; ``finished`` when that attempt's new
# capture (route key suffixed with the attempt, see ``_register``) is registered.
_CAPTURE: LiteralString = (
    "SELECT r.source_id, r.surface, r.request_key, r.capture_id, r.blob_sha256, "
    "r.record_sha256, d.url, l.id, l.outcome, l.fetched_sha256, l.recorded_at, "
    "eqos.capture_state(r.id) = 'EXPIRED' AND NOT eqos.is_vendor_source(r.source_id) "
    "AND d.url IS NOT NULL AS refetchable, EXISTS (SELECT 1 FROM eqos.capture_refs n "
    "WHERE (n.source_id, n.surface) = (r.source_id, r.surface) "
    "AND n.request_key = r.request_key || '.refetch_attempt-' || l.id) AS finished "
    "FROM eqos.capture_refs r LEFT JOIN eqos.capture_addresses d ON d.capture_ref_id = r.id "
    "LEFT JOIN LATERAL (SELECT * FROM eqos.refetch_attempts WHERE capture_ref_id = r.id "
    "ORDER BY id DESC LIMIT 1) l ON true WHERE r.id = %s"
)
_INSERT_ATTEMPT: LiteralString = (
    "INSERT INTO eqos.refetch_attempts (capture_ref_id, url, outcome, category, http_status, "
    "fetched_sha256, severity) VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "RETURNING id, url, outcome, fetched_sha256, recorded_at"
)
_RETENTION_SHARED: LiteralString = "SELECT eqos.retention_shared()"
_RESTORE: LiteralString = "SELECT eqos.restore_capture(%s)"


def live_fetch(url: str) -> bytes:
    """The complete HTTP 200 body at an approved ``url``, else :class:`FetchFailure`."""
    _approve(url)
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(url, timeout=REFETCH_TIMEOUT_SECONDS) as response:
            if response.status != http.client.OK:
                raise FetchFailure(FetchFailureCategory.HTTP_STATUS, response.status)
            length = response.headers.get("Content-Length")
            if length is not None and not length.isdecimal():
                raise FetchFailure(FetchFailureCategory.INCOMPLETE)
            read = read_bounded_capture(
                response,
                MAX_BODY_BYTES,
                timeout_seconds=REFETCH_TIMEOUT_SECONDS,
                expected_bytes=int(length) if length is not None else None,
            )
    except urllib.error.HTTPError as error:
        raise FetchFailure(FetchFailureCategory.HTTP_STATUS, error.code) from error
    except http.client.IncompleteRead as error:
        raise FetchFailure(FetchFailureCategory.INCOMPLETE) from error
    except OSError as error:  # a URLError carries its cause as ``reason``
        timed_out = isinstance(getattr(error, "reason", error), TimeoutError)
        category = FetchFailureCategory.TIMEOUT if timed_out else FetchFailureCategory.CONNECTION
        raise FetchFailure(category) from error
    if read.completeness is not BodyCompleteness.COMPLETE or read.raw_body is None:
        raise FetchFailure(FetchFailureCategory.INCOMPLETE)
    return read.raw_body


def _approve(url: str) -> None:
    """Refuse, before opening it, an address other than HTTPS to an approved host (no port or
    user) that resolves to public addresses only."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc not in APPROVED_HOSTS:
        raise FetchFailure(FetchFailureCategory.REFUSED_ADDRESS)
    try:
        addresses = socket.getaddrinfo(parts.netloc, 443, proto=socket.IPPROTO_TCP)
    except OSError as error:
        raise FetchFailure(FetchFailureCategory.CONNECTION) from error
    if not all(ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise FetchFailure(FetchFailureCategory.REFUSED_ADDRESS)


def probe(
    conn: psycopg.Connection[Any], facts: tuple[CaptureFacts, ...], fetch: Fetch
) -> dict[str, ProbeOutcome]:
    """Fetch up to :data:`PROBE_SAMPLE` captures per source (lowest ids) and record each;
    the first mismatch or failure halts that source with a HIGH row (R8 step 1, R9)."""
    samples: defaultdict[str, list[tuple[CaptureFacts, str]]] = defaultdict(list)
    for fact in sorted(facts, key=lambda f: f.capture_ref_id):
        if fact.url is not None and len(samples[fact.source_id]) < PROBE_SAMPLE:
            samples[fact.source_id].append((fact, fact.url))
    outcomes: dict[str, ProbeOutcome] = {}
    for source_id, sample in samples.items():
        for fact, url in sample:
            category, status, fetched = None, None, None
            try:
                fetched = hashlib.sha256(fetch(url)).hexdigest()
            except FetchFailure as failure:
                category, status = failure.category, failure.http_status
            matched = fetched == fact.blob_sha256
            outcome = "MATCH" if matched else "FAILED" if category else "MISMATCH"
            params = (source_id, fact.capture_ref_id, url, outcome, category, status, fetched)
            with conn.transaction():
                row = conn.execute(_INSERT_PROBE, (*params, None if matched else "HIGH"))
                (probe_id,) = row.fetchall()[0]
            outcomes[source_id] = ProbeOutcome(matched=matched, probe_id=probe_id)
            if not matched:
                break
    return outcomes


def refetch(
    pool: ConnectionPool,
    store: SnapshotStore,
    capture_ref_id: int,
    fetch: Fetch,
    *,
    retry: bool = False,
) -> RefetchOutcome:
    """Fetch an expired exchange capture from its address: equal bytes restore it (same id and
    times), different bytes become a new capture under a HIGH ``MISMATCH`` attempt (R10). A
    rerun finishes the latest attempt before fetching again; after a completed mismatch only
    ``retry`` fetches again."""
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(_CAPTURE, (capture_ref_id,)).fetchone()
    if row is None or not row["refetchable"]:
        return RefetchOutcome.NOT_REFETCHABLE
    ids = (row["source_id"], row["surface"], row["request_key"], row["capture_id"])
    record = CaptureRecord.model_validate_json(store.read_record(*ids, row["record_sha256"]))
    if row["outcome"] == "MISMATCH" and row["finished"] and not retry:
        return RefetchOutcome.REFETCH_MISMATCH

    def attempt(outcome: str, fetched: str | None, failed: tuple[Any, ...] = (None, None)) -> Any:
        """Transaction A: one committed attempt row, before any store write."""
        severity = "HIGH" if outcome == "MISMATCH" else None
        params = (capture_ref_id, row["url"], outcome, *failed, fetched, severity)
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(_INSERT_ATTEMPT, params).fetchone()

    body = None
    if row["outcome"] == "MATCH":
        with contextlib.suppress(MissingSnapshotError):  # a relink before a crash survives
            body = store.read_body(record)
    if body is None:
        try:
            body = fetch(row["url"])
        except FetchFailure as failure:
            attempt("FAILED", None, (failure.category, failure.http_status))
            return RefetchOutcome.FAILED
        sha256 = hashlib.sha256(body).hexdigest()
        if sha256 != row["blob_sha256"]:
            unfinished = row["outcome"] == "MISMATCH" and not row["finished"]
            reused = unfinished and row["fetched_sha256"] == sha256
            _register(pool, store, record, row if reused else attempt("MISMATCH", sha256), body)
            return RefetchOutcome.REFETCH_MISMATCH
        attempt("MATCH", sha256)
    with pool.connection() as conn, conn.transaction():  # transaction B
        conn.execute(_RETENTION_SHARED)
        store.relink(record, body)
        conn.execute(_RESTORE, (capture_ref_id,))  # admitted only after a matching attempt
    return RefetchOutcome.RESTORED


def _register(
    pool: ConnectionPool,
    store: SnapshotStore,
    original: CaptureRecord,
    attempt: dict[str, Any],
    body: bytes,
) -> None:
    """Publish and register mismatching bytes as the attempt's new capture at its address: the
    original route naming the attempt (invariant 13), retrieved at the attempt's time so a rerun
    republishes the same record."""
    request, attempt_id = original.request, attempt["id"]
    key = f"{request.request_key}.{ATTEMPT_PARAMETER}-{attempt_id}"
    params = (*request.parameters, RequestParameter(name=ATTEMPT_PARAMETER, value=str(attempt_id)))
    named = request.model_copy(update={"request_key": key, "parameters": params})
    sha256, at = hashlib.sha256(body).hexdigest(), attempt["recorded_at"].astimezone(UTC)
    blob = BlobRef(source_id=request.source_id, content_sha256=sha256, byte_count=len(body))
    update = {"request": named, "retrieved_at": at, "http_status": 200, "body": blob}
    fresh = original.model_copy(update=update | {"capture_id": derive_capture_id(at, blob)})
    record = store.put_capture(CaptureRecord.model_validate(fresh.model_dump()), body)
    ref = CaptureReference(
        capture_ref_id=None,
        source_id=named.source_id,
        surface=named.surface,
        request_key=named.request_key,
        capture_id=record.capture_id,
        blob_sha256=sha256,
        record_sha256=record.record_sha256,
        registered_at=at,
        first_seen_at=at,
    )
    with capture_registration(pool) as registration:
        registration.insert(ref, url=attempt["url"])
