"""Public capture and replay boundaries; every response is synthetic."""

import email.message
import hashlib
import http.client
import io
import json
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from upstox_fixtures import instruments_fetch, nse_equity_row

from fundamentals.api.upstox_cli import run_instruments_command
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.ingest.upstox_candle_retention import (
    CandleReplayError,
    candle_versions,
    compose_series,
    replay_candle_versions,
)
from fundamentals.ingest.upstox_source import (
    UpstoxBlockedError,
    UpstoxConfig,
    UpstoxCredentials,
    UpstoxFetch,
    UpstoxFetchError,
    UpstoxSource,
    UpstoxSurface,
    route_for,
)
from fundamentals.store.snapshot_store import SnapshotStore


@pytest.mark.parametrize(
    ("cap", "expected", "issue"),
    [(100, b"abcde", "read_interrupted"), (4, b"abcd", "limit_exceeded")],
)
def test_chunked_http_response_preserves_outer_and_inner_disjoint_partials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cap: int, expected: bytes, issue: str
) -> None:
    """Real urllib chunk framing must retain available bytes without retrying a block."""

    class Socket:
        def makefile(self, mode: str) -> io.BytesIO:
            return io.BytesIO(
                b"HTTP/1.1 403 Forbidden\r\nTransfer-Encoding: chunked\r\n"
                b"Content-Type: text/html\r\n\r\n3\r\nabc\r\n4\r\nde"
            )

    response = http.client.HTTPResponse(Socket())
    response.begin()
    error = urllib.error.HTTPError(
        "https://assets.upstox.com", 403, "blocked", response.headers, response
    )
    opener = Opener(error)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    store = SnapshotStore(tmp_path)
    source = UpstoxSource(
        UpstoxConfig(max_compressed_bytes=cap, min_request_spacing_seconds=0), snapshot_store=store
    )
    with pytest.raises(UpstoxBlockedError) as refused:
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    assert refused.value.raw_body == expected
    assert refused.value.http_status == 403
    assert not refused.value.retryable
    assert opener.calls == source.requests_made == 1
    assert response.closed
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert record.schema_version == 2
    assert record.body_completeness == "partial"
    assert record.body_read_issue == issue
    assert record.outcome.native_value == "CLIENT_BLOCKED"
    assert store.read_evidence_body(record) == expected


def test_cli_retains_raw_capture_and_provenance_in_shared_store(tmp_path: Path) -> None:
    """Compatibility exports cannot be the only retained evidence."""
    fetch = instruments_fetch([nse_equity_row()])

    class Source:
        def fetch(self, *args: object, **kwargs: object) -> UpstoxFetch:
            return fetch

        def redact(self, text: str) -> str:
            return text

    result = run_instruments_command(tmp_path, source=Source())
    store = SnapshotStore(tmp_path / "snapshots")
    records = store.list_captures("upstox", "instruments", "complete")
    assert len(records) == 1
    record = records[0]
    assert store.read_body(record) == fetch.raw_body
    assert record.body is not None
    assert record.body.content_sha256 == fetch.capture.content_sha256
    assert record.retrieved_at == fetch.capture.retrieved_at
    assert record.http_status == 200
    assert record.outcome.code is OutcomeCode.OK
    assert record.outcome.native_value == "OK"
    assert record.rights.authority_refs == ("owner-decision-2026-09-04",)
    assert {parameter.name: parameter.value for parameter in record.request.parameters} == {
        "origin": "https://assets.upstox.com",
        "route_key": "complete",
        "path": "/market-quote/instruments/exchange/complete.json.gz",
    }
    assert result.captures[0].snapshot_record_sha256 == record.record_sha256
    assert store.put_capture(record, fetch.raw_body) == record
    assert len(store.list_captures("upstox", "instruments", "complete")) == 1


class Response(io.BytesIO):
    """A synthetic urllib response with the vendor's complete envelope."""

    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "application/json"

    def getcode(self) -> int:
        return 200


class Opener:
    """Replay responses only at the outbound network boundary."""

    def __init__(self, *responses: bytes | Exception) -> None:
        self.responses = list(responses)
        self.calls = 0

    def open(self, request: object, timeout: float) -> Response:
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return Response(result)


def source_with_responses(
    store: SnapshotStore, monkeypatch: pytest.MonkeyPatch, *responses: bytes | Exception
) -> tuple[UpstoxSource, Opener]:
    """Use the production source and store with synthetic HTTP and clock."""
    opener = Opener(*responses)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    stamps = iter(datetime(2026, 9, 4, tzinfo=UTC) + timedelta(seconds=i) for i in range(50))
    source = UpstoxSource(
        UpstoxConfig(
            credentials=UpstoxCredentials(access_token=SecretStr("fixture-analytics-token")),
            min_request_spacing_seconds=0,
            rate_limit_backoff_seconds=0,
            retrieved_at=lambda: next(stamps),
        ),
        snapshot_store=store,
    )
    return source, opener


def candle_body(*rows: tuple[str, int]) -> bytes:
    """Vendor rows have timestamp, OHLC, integer volume and open interest."""
    return json.dumps(
        {
            "status": "success",
            "data": {
                "candles": [
                    [stamp + "T00:00:00+05:30", price, price, price, price, 100, 0]
                    for stamp, price in rows
                ]
            },
        }
    ).encode()


def test_revised_series_retains_old_version_and_tail_only_claims_observed_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A split-like revision and incremental tail never rewrite old evidence."""
    original = candle_body(("2026-09-01", 100), ("2026-09-02", 120))
    revised = candle_body(("2026-09-01", 50), ("2026-09-02", 60))
    tail = candle_body(("2026-09-04", 65))
    store = SnapshotStore(tmp_path)
    source, _ = source_with_responses(store, monkeypatch, original, original, revised, tail)
    route = route_for(UpstoxSurface.CANDLES)
    params = dict(
        instrument_key="NSE_EQ|INE999Z01012",
        unit="days",
        interval="1",
        from_date="2026-09-01",
        to_date="2026-09-04",
    )
    for _ in range(4):
        source.fetch(
            route,
            instrument_key=params["instrument_key"],
            unit=params["unit"],
            interval=params["interval"],
            from_date=params["from_date"],
            to_date=params["to_date"],
        )
    versions = candle_versions(store, params["instrument_key"])
    replay = replay_candle_versions(store, params["instrument_key"])
    assert replay.versions == versions
    assert replay.failures == ()
    assert len(versions) == 4
    assert versions[0].version_sha256 == versions[1].version_sha256
    assert versions[0].version_sha256 != versions[2].version_sha256
    assert versions[0].candles[0].close == Decimal("100")
    assert versions[2].candles[0].close == Decimal("50")
    assert versions[3].coverage.observed_dates == (date(2026, 9, 4),)
    assert versions[0].coverage.observed_dates == (date(2026, 9, 1), date(2026, 9, 2))
    assert store.read_body(versions[0].capture) == original
    assert store.read_body(versions[2].capture) == revised
    assert versions[0].capture.body is not None
    assert versions[0].coverage.capture_sha256 == versions[0].capture.body.content_sha256
    assert [candle.close for candle in compose_series(tuple(reversed(versions)))] == [
        Decimal("50"),
        Decimal("60"),
        Decimal("65"),
    ]


def test_blocked_body_and_native_outcome_are_retained_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal Cloudflare body remains evidence, distinct from a transport failure."""
    body = b"Cloudflare error 1010: client blocked"
    headers = email.message.Message()
    headers["Content-Type"] = "text/html; charset=UTF-8"
    error = urllib.error.HTTPError(
        "https://assets.upstox.com", 403, "blocked", headers, io.BytesIO(body)
    )
    store = SnapshotStore(tmp_path)
    source, opener = source_with_responses(store, monkeypatch, error)
    with pytest.raises(UpstoxBlockedError):
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert store.read_body(record) == body
    assert record.http_status == 403
    assert record.media_type == "text/html"
    assert record.outcome.code is OutcomeCode.CLIENT_BLOCKED
    assert record.outcome.native_value == "CLIENT_BLOCKED"
    assert not record.outcome.retryable
    assert opener.calls == 1


def test_transport_failure_is_retained_with_no_invented_body_or_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network failure is an attempt, never a false empty response."""
    store = SnapshotStore(tmp_path)
    source, _ = source_with_responses(store, monkeypatch, urllib.error.URLError("offline"))
    with pytest.raises(UpstoxFetchError) as refusal:
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert record.body is None
    assert record.http_status is None
    assert record.outcome.code is OutcomeCode.TRANSPORT_ERROR
    assert record.outcome.native_value == "TRANSPORT_ERROR"
    assert record.outcome.retryable
    assert refusal.value.capture_record == record


@pytest.mark.parametrize("body", [b"not json", candle_body(("2026-09-05", 99))])
def test_invalid_or_wrong_window_candles_keep_bytes_but_emit_no_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    """Parsing failure never discards raw capture or falsely asserts date coverage."""
    from fundamentals.ingest.upstox_retention import candle_request_key

    store = SnapshotStore(tmp_path)
    source, _ = source_with_responses(store, monkeypatch, body)
    source.fetch(
        route_for(UpstoxSurface.CANDLES),
        instrument_key="NSE_EQ|INE999Z01012",
        unit="days",
        interval="1",
        from_date="2026-09-01",
        to_date="2026-09-04",
    )
    with pytest.raises(CandleReplayError):
        candle_versions(store, "NSE_EQ|INE999Z01012")
    (record,) = store.list_captures(
        "upstox", "candles", candle_request_key("NSE_EQ|INE999Z01012", "days", "1")
    )
    assert store.read_body(record) == body
    assert record.outcome.code is OutcomeCode.OK  # Acquisition succeeded; replay failed.


def test_cli_schema_drift_is_retained_before_catalog_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed catalog keeps its acquisition evidence, even when CLI refuses it."""
    store = SnapshotStore(tmp_path / "snapshots")
    source, _ = source_with_responses(store, monkeypatch, b"not gzip")
    result = run_instruments_command(tmp_path, source=source)
    assert result.refused
    assert result.outcome_value == "SCHEMA_DRIFT"
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert store.read_body(record) == b"not gzip"
    assert record.outcome.code is OutcomeCode.OK


def test_rate_limit_retry_retains_each_body_before_a_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retried attempts remain inspectable without changing the bounded retry policy."""
    headers = email.message.Message()
    headers["Content-Type"] = "application/json"
    error = urllib.error.HTTPError(
        "https://assets.upstox.com", 429, "limited", headers, io.BytesIO(b'{"error":"limited"}')
    )
    store = SnapshotStore(tmp_path)
    source, opener = source_with_responses(store, monkeypatch, error, b"success bytes")
    source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    records = store.list_captures("upstox", "instruments", "complete")
    assert [record.outcome.code for record in records] == [OutcomeCode.RATE_LIMITED, OutcomeCode.OK]
    assert [store.read_body(record) for record in records] == [
        b'{"error":"limited"}',
        b"success bytes",
    ]
    assert opener.calls == 2


def test_cli_binds_actual_bytes_when_input_metadata_has_a_stale_hash(tmp_path: Path) -> None:
    """A drifted input retains its actual digest and preserves CLI refusal behavior."""
    from fundamentals.ingest.upstox_source import UpstoxFetch

    original = instruments_fetch([nse_equity_row()])
    tampered = UpstoxFetch(raw_body=b"different bytes", capture=original.capture)

    class Source:
        def fetch(self, *args: object, **kwargs: object) -> UpstoxFetch:
            return tampered

        def redact(self, text: str) -> str:
            return text

    result = run_instruments_command(tmp_path, source=Source())
    store = SnapshotStore(tmp_path / "snapshots")
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert record.body is not None
    assert record.body.content_sha256 == hashlib.sha256(tampered.raw_body).hexdigest()
    assert store.read_body(record) == tampered.raw_body
    assert result.refused


@pytest.mark.parametrize(
    ("bad", "expected_error"),
    [
        (b"not json", "Expecting value"),
        (b'{"status":"success","data":{"candles":[[]]}}', "exactly seven fields"),
        (candle_body(("2026-09-05", 99)), "outside the requested window"),
        (
            b'{"status":"success","data":{"candles":'
            b'[["2026-09-01T00:00:00+05:30",100,100,100,100,100,0],[]]}}',
            "exactly seven fields",
        ),
    ],
)
def test_replay_reports_bad_capture_and_preserves_later_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: bytes, expected_error: str
) -> None:
    """Malformed HTTP success cannot hide valid revisions and tail evidence."""
    from fundamentals.ingest.upstox_retention import candle_request_key

    store = SnapshotStore(tmp_path)
    original = candle_body(("2026-09-01", 100), ("2026-09-02", 120))
    revised = candle_body(("2026-09-01", 50), ("2026-09-02", 60))
    tail = candle_body(("2026-09-04", 65))
    source, _ = source_with_responses(store, monkeypatch, bad, original, revised, tail)
    instrument = "NSE_EQ|INE999Z01012"
    for _ in range(4):
        source.fetch(
            route_for(UpstoxSurface.CANDLES),
            instrument_key=instrument,
            unit="days",
            interval="1",
            from_date="2026-09-01",
            to_date="2026-09-04",
        )
    captures = store.list_captures("upstox", "candles", candle_request_key(instrument, "days", "1"))
    result = replay_candle_versions(store, instrument)
    assert tuple(version.capture for version in result.versions) == captures[1:]
    (failure,) = result.failures
    assert failure.capture == captures[0]
    assert failure.capture.body is not None
    assert failure.capture.body.content_sha256 == hashlib.sha256(bad).hexdigest()
    assert store.read_body(failure.capture) == bad
    assert failure.error.startswith(f"capture {captures[0].capture_id}: ")
    assert expected_error in failure.error
    assert result.versions[0].candles[0].close == Decimal("100")
    assert result.versions[2].coverage.observed_dates == (date(2026, 9, 4),)
    assert [c.close for c in compose_series(result.versions)] == [
        Decimal("50"),
        Decimal("60"),
        Decimal("65"),
    ]
    with pytest.raises(CandleReplayError):
        candle_versions(store, instrument)


def test_parseable_partial_json_cannot_become_candle_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fundamentals.contracts.snapshot import BodyCompleteness, BodyReadIssue
    from fundamentals.ingest.upstox_candle_retention import candle_version
    from fundamentals.ingest.upstox_retention import seal_capture
    from fundamentals.ingest.upstox_source import AcquisitionOutcome, to_outcome_record

    body = candle_body(("2026-09-01", 100))
    record = seal_capture(
        surface="candles",
        route_key="default",
        url="https://api.upstox.com/v3/historical-candle/NSE_EQ%7CINE999Z01012/days/1/2026-09-04/2026-09-01",
        retrieved_at=datetime(2026, 9, 4, tzinfo=UTC),
        http_status=200,
        media_type="application/json",
        content_encoding=None,
        raw_body=body,
        outcome=to_outcome_record(AcquisitionOutcome.TRANSPORT_ERROR),
        body_completeness=BodyCompleteness.PARTIAL,
        body_read_issue=BodyReadIssue.READ_INTERRUPTED,
    )
    store = SnapshotStore(tmp_path)
    store.put_capture(record, body)
    assert store.read_evidence_body(record) == body
    # Defensive seam: even inconsistent success metadata must be refused before any read.
    inconsistent = record.model_copy(update={"outcome": to_outcome_record(AcquisitionOutcome.OK)})

    def forbidden_read(*args: object) -> bytes:
        raise AssertionError("incomplete evidence reached parser input")

    monkeypatch.setattr(store, "read_body", forbidden_read)
    with pytest.raises(CandleReplayError, match="incomplete"):
        candle_version(store, inconsistent)


class FailingBody(Response):
    def __init__(self, *parts: object) -> None:
        super().__init__(b"")
        self.parts = iter(parts)
        self.read_calls = 0

    def read(self, amount: int = -1) -> bytes:
        self.read_calls += 1
        part = next(self.parts)
        if isinstance(part, Exception):
            raise part
        return part  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("status", "native"),
    [
        (403, "CLIENT_BLOCKED"),
        (451, "CLIENT_BLOCKED"),
        (401, "AUTH_EXPIRED"),
        (404, "REQUEST_REJECTED"),
    ],
)
@pytest.mark.parametrize(
    ("kind", "expected", "state", "issue"),
    [
        ("limit", b"abcd", "partial", "limit_exceeded"),
        ("interrupt", b"ab", "partial", "read_interrupted"),
        ("nonbytes", b"ab", "partial", "non_bytes"),
        ("empty", None, "absent", "read_interrupted"),
        ("none", None, "absent", None),
    ],
)
def test_terminal_status_wins_over_each_body_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    native: str,
    kind: str,
    expected: bytes | None,
    state: str,
    issue: str | None,
) -> None:
    stream = (
        None
        if kind == "none"
        else FailingBody(
            *{
                "limit": (b"abcde",),
                "interrupt": (b"ab", TimeoutError()),
                "nonbytes": (b"ab", "bad"),
                "empty": (TimeoutError(),),
            }[kind]
        )
    )
    headers = email.message.Message()
    headers["Content-Type"] = "text/html"
    error = urllib.error.HTTPError("https://assets.upstox.com", status, "refused", headers, stream)
    if stream is None:
        error.fp = None
    opener = Opener(error)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    store = SnapshotStore(tmp_path)
    source = UpstoxSource(
        UpstoxConfig(max_compressed_bytes=4, min_request_spacing_seconds=0), snapshot_store=store
    )
    with pytest.raises(UpstoxFetchError) as refusal:
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert (record.http_status, record.outcome.native_value) == (status, native)
    assert (record.body_completeness, record.body_read_issue) == (state, issue)
    assert refusal.value.raw_body == expected
    assert opener.calls == 1
    assert not refusal.value.retryable
    if stream is not None:
        assert stream.closed
    if expected is not None:
        assert store.read_evidence_body(record) == expected


@pytest.mark.parametrize(
    ("parts", "expected", "state", "issue", "native"),
    [
        ((b"ab", TimeoutError()), b"ab", "partial", "read_interrupted", "TRANSPORT_ERROR"),
        ((TimeoutError(),), None, "absent", "read_interrupted", "TRANSPORT_ERROR"),
        ((b"ab", "bad"), b"ab", "partial", "non_bytes", "SCHEMA_DRIFT"),
    ],
)
def test_200_interruption_retains_status_and_prefix_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parts: tuple[object, ...],
    expected: bytes | None,
    state: str,
    issue: str,
    native: str,
) -> None:
    response = FailingBody(*parts)

    class OneResponse:
        calls = 0

        def open(self, request: object, timeout: float) -> Response:
            self.calls += 1
            return response

    opener = OneResponse()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    store = SnapshotStore(tmp_path)
    source = UpstoxSource(UpstoxConfig(min_request_spacing_seconds=0), snapshot_store=store)
    with pytest.raises(UpstoxFetchError) as refusal:
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert (refusal.value.http_status, refusal.value.raw_body) == (200, expected)
    assert (record.body_completeness, record.body_read_issue) == (state, issue)
    assert record.outcome.native_value == native
    assert opener.calls == 1
    assert response.closed


@pytest.mark.parametrize("succeed", [False, True])
def test_incomplete_429_preserves_exact_existing_retry_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, succeed: bool
) -> None:
    from fundamentals.ingest.upstox_source import UpstoxRateLimitedError

    headers = email.message.Message()
    streams = [FailingBody(b"ab", TimeoutError()) for _ in range(3)]
    errors = [
        urllib.error.HTTPError("https://assets.upstox.com", 429, "limited", headers, stream)
        for stream in streams
    ]
    responses = errors[:2] + ([b"ok"] if succeed else errors[2:])
    store = SnapshotStore(tmp_path)
    source, opener = source_with_responses(store, monkeypatch, *responses)
    stamps = iter(datetime(2026, 9, 4, tzinfo=UTC) + timedelta(seconds=i) for i in range(4))
    source = UpstoxSource(
        UpstoxConfig(
            min_request_spacing_seconds=0,
            rate_limit_backoff_seconds=0,
            max_rate_limit_retries=2,
            retrieved_at=lambda: next(stamps),
        ),
        snapshot_store=store,
    )
    if succeed:
        assert source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete")).raw_body == b"ok"
    else:
        with pytest.raises(UpstoxRateLimitedError) as refusal:
            source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
        assert refusal.value.http_status == 429
        assert refusal.value.raw_body == b"ab"
        assert refusal.value.body_completeness == "partial"
        assert refusal.value.body_read_issue == "read_interrupted"
    records = store.list_captures("upstox", "instruments", "complete")
    assert len(records) == opener.calls == 3
    assert [r.outcome.native_value for r in records] == [
        "RATE_LIMITED",
        "RATE_LIMITED",
        "OK" if succeed else "RATE_LIMITED",
    ]
    assert all(s.closed for s in streams[: 2 if succeed else 3])


def test_storage_failure_stops_retry_and_preserves_refusal_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from fundamentals.ingest.upstox_source import UpstoxRateLimitedError

    stream = FailingBody(b"ab", TimeoutError())
    headers = email.message.Message()
    error = urllib.error.HTTPError("https://assets.upstox.com", 429, "limited", headers, stream)
    store = SnapshotStore(tmp_path)
    source, opener = source_with_responses(store, monkeypatch, error, b"never fetched")

    def fail_publish(*args: object, **kwargs: object) -> None:
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(os, "rename", fail_publish)
    with pytest.raises(OSError) as failure:
        source.fetch(route_for(UpstoxSurface.INSTRUMENTS, "complete"))
    assert isinstance(failure.value.__context__, UpstoxRateLimitedError)
    assert failure.value.__context__.http_status == 429
    assert opener.calls == 1
    assert stream.closed
    assert store.list_captures("upstox", "instruments", "complete") == ()


@pytest.mark.parametrize("setting", ["max_compressed_bytes", "max_decompressed_bytes"])
def test_config_refuses_body_limits_above_hard_ceilings(setting: str) -> None:
    from pydantic import ValidationError

    maximum = 32 * 1024 * 1024 if setting == "max_compressed_bytes" else 192 * 1024 * 1024
    with pytest.raises(ValidationError):
        UpstoxConfig(**{setting: maximum + 1})


def test_incomplete_attempt_keeps_later_complete_series_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fundamentals.ingest.upstox_retention import candle_request_key

    body = candle_body(("2026-09-01", 100))
    responses = iter([FailingBody(body, TimeoutError()), Response(body)])

    class Opener:
        def open(self, request: object, timeout: float) -> Response:
            return next(responses)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    stamps = iter([datetime(2026, 9, 4, tzinfo=UTC), datetime(2026, 9, 5, tzinfo=UTC)])
    store = SnapshotStore(tmp_path)
    source = UpstoxSource(
        UpstoxConfig(
            credentials=UpstoxCredentials(access_token=SecretStr("fixture-token")),
            min_request_spacing_seconds=0,
            retrieved_at=lambda: next(stamps),
        ),
        snapshot_store=store,
    )
    params = dict(
        instrument_key="NSE_EQ|INE999Z01012",
        unit="days",
        interval="1",
        from_date="2026-09-01",
        to_date="2026-09-04",
    )
    with pytest.raises(UpstoxFetchError):
        source.fetch(route_for(UpstoxSurface.CANDLES), **params)
    source.fetch(route_for(UpstoxSurface.CANDLES), **params)
    records = store.list_captures(
        "upstox", "candles", candle_request_key(params["instrument_key"], "days", "1")
    )
    assert len(records) == 2
    assert records[0].body_completeness == "partial"
    assert records[1].body_completeness == "complete"
    assert records[0].body == records[1].body
    replay = replay_candle_versions(store, params["instrument_key"])
    assert len(replay.versions) == 1
    assert replay.failures == ()
    assert replay.versions[0].capture == records[1]
    assert replay.versions[0].coverage.observed_dates == (date(2026, 9, 1),)
    assert compose_series(replay.versions)[0].close == Decimal("100")


def test_partial_capture_is_translated_to_unreadable_tijori_input(tmp_path: Path) -> None:
    from fundamentals.contracts.snapshot import (
        BodyCompleteness,
        BodyReadIssue,
        IncompleteSnapshotError,
    )
    from fundamentals.ingest.upstox_retention import seal_capture
    from fundamentals.ingest.upstox_source import AcquisitionOutcome, to_outcome_record
    from fundamentals.verify.three_source_inputs import UnreadableInputError, read_tijori_capture

    record = seal_capture(
        surface="instruments",
        route_key="complete",
        url="https://assets.upstox.com/fixture",
        retrieved_at=datetime(2026, 9, 4, tzinfo=UTC),
        http_status=200,
        media_type="text/html",
        content_encoding=None,
        raw_body=b"<html>",
        outcome=to_outcome_record(AcquisitionOutcome.TRANSPORT_ERROR),
        body_completeness=BodyCompleteness.PARTIAL,
        body_read_issue=BodyReadIssue.READ_INTERRUPTED,
    )
    store = SnapshotStore(tmp_path)
    store.put_capture(record, b"<html>")
    inconsistent = record.model_copy(update={"outcome": to_outcome_record(AcquisitionOutcome.OK)})
    with pytest.raises(UnreadableInputError) as refused:
        read_tijori_capture(
            store,
            inconsistent,
            slug="fixture",
            expected_symbol="FIXTURE",
            expected_company_id=None,
            period_end=date(2026, 6, 30),
        )
    assert isinstance(refused.value.__cause__, IncompleteSnapshotError)


def test_cli_failed_capture_republication_preserves_completeness_and_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gzip

    prefix = gzip.compress(b"[]", mtime=0)[:-2]
    response = FailingBody(prefix, TimeoutError())
    response.headers["Content-Encoding"] = "gzip"

    class Opener:
        def open(self, request: object, timeout: float) -> Response:
            return response

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    store = SnapshotStore(tmp_path / "snapshots")
    source = UpstoxSource(UpstoxConfig(min_request_spacing_seconds=0), snapshot_store=store)
    with pytest.raises(UpstoxFetchError) as refusal:
        run_instruments_command(tmp_path, source=source)
    assert refusal.value.outcome.value == "TRANSPORT_ERROR"
    (record,) = store.list_captures("upstox", "instruments", "complete")
    assert record.body_completeness == "partial"
    assert record.body_read_issue == "read_interrupted"
    assert record.complete_body_sha256 is None
    assert refusal.value.capture_record == record
    assert record.content_encoding == "gzip"
    assert store.read_evidence_body(record) == prefix
    assert store.put_capture(record, prefix).record_sha256 == record.record_sha256
    assert len(store.list_captures("upstox", "instruments", "complete")) == 1
