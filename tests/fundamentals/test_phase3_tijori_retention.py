"""Acceptance tests for retained Tijori financials captures (Phase 3, S3).

The seam is ``fundamentals.ingest.tijori_capture`` — the auth and identity gate
that seals one outcome BEFORE any parser runs — plus
``fundamentals.ingest.tijori_retention``, which commits the page (or the
failure) to the snapshot store first and parses the retained body afterwards.
What it protects is evidence: today ``tijori-tables`` keeps no bytes, so an
anonymous shell, a rate limit and a real schema change all reach the operator as
one parse exception with nothing kept to re-check them against.

Nothing here touches the network: the outbound transport is a scripted fake and
the real socket path is an error, so a missed patch fails loudly instead of
dialling out. Every byte is the committed synthetic fixture or a variant of it.
The new modules are imported at call time so collection stays green.
"""

from __future__ import annotations

import io
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from email.message import Message
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from fundamentals.api.cli import main
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.ingest import tijori_source as tijori_source_module
from fundamentals.ingest.tijori_common import TijoriIslandStatus
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.ingest.tijori_tables import TijoriTable, TijoriTableKey
from fundamentals.store.snapshot_store import SnapshotStore

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_tijori_financials.html"

SLUG = "titan-company-limited"
SYMBOL = "TITAN"
COMPANY_ID = 81
SESSION_COOKIE = "fixture-session-token"
MEDIA_TYPE = "text/html; charset=utf-8"
SINGLE_TABLE = TijoriTableKey.RATIOS_CONSOLIDATED
ERROR_BODY = b"<html><body>refused</body></html>"
QUARTER_END = date(2025, 3, 31)
RETRY_BACKOFF_SECONDS = 0.25
# Every supported key the fixture publishes, in the order the builder emits them.
PUBLISHED_TABLE_KEYS = (
    "bs_c_d",
    "bs_c_s",
    "cf_c",
    "fr_c",
    "growth",
    "pl_c_s",
    "pl_s_s",
    "qt_c",
    "qt_s",
)

_ISLAND_PATTERN = '(<script id="{island}" type="application/json">)(.*?)(</script>)'
_COMPANY_DETAILS = "company_details"
_IS_AUTH = "is_auth"
_FINANCIALS_ISLAND = "fin_tables_data"
_LOCKS_ISLAND = "financials_locks"

_DISABLED_LOCKS = (
    b'{"growth":{"compare":false},"ratios":{"compare":false},'
    b'"qtly_results":{"compare":false},"cash_flow_table":{"compare":false}}'
)
_OTHER_SYMBOL_DETAILS = b'{"company":"Synthetic Other Ltd.","company_id":81,"symbol":"OTHER"}'
_OTHER_ID_DETAILS = b'{"company":"Synthetic Other Ltd.","company_id":4242,"symbol":"TITAN"}'

_Step = tuple[int, bytes] | Exception


def _capture_module() -> Any:
    """The S3 capture seam, imported at call time so collection stays green."""
    return import_module("fundamentals.ingest.tijori_capture")


def _retention_module() -> Any:
    """The S3 retention seam, imported at call time so collection stays green."""
    return import_module("fundamentals.ingest.tijori_retention")


def _parsers() -> Any:
    """``TijoriSource`` as an untyped handle: S3 adds a keyword to its parsers."""
    return tijori_source_module.TijoriSource


def _fixture_bytes() -> bytes:
    """The committed synthetic financials page, exactly as retained."""
    return _FIXTURE_PATH.read_bytes()


def _variant(island: str, payload: bytes | None) -> bytes:
    """The fixture page with one island rewritten, or dropped when payload is None."""
    pattern = _ISLAND_PATTERN.format(island=island).encode("utf-8")
    replacement = b"" if payload is None else rb"\1" + payload + rb"\3"
    page, count = re.subn(pattern, replacement, _fixture_bytes(), flags=re.DOTALL)
    assert count == 1, f"island {island!r} is not in the fixture"
    return page


def _anonymous_page() -> bytes:
    """The logged-out shell: the same page with ``is_auth`` false."""
    return _variant(_IS_AUTH, b"false")


def _headers(body: bytes) -> Message:
    """The response headers a complete financials page carries."""
    message = Message()
    message["Content-Type"] = MEDIA_TYPE
    message["Content-Length"] = str(len(body))
    return message


class _FakeResponse:
    """One scripted HTTP response, readable exactly like a urllib response."""

    def __init__(self, status: int, body: bytes) -> None:
        self._status = status
        self._body = body
        self.headers = _headers(body)

    def getcode(self) -> int:
        """The status line of this scripted response."""
        return self._status

    def read(self, amount: int | None = None) -> bytes:
        """The scripted body, honouring the caller's read bound."""
        return self._body if amount is None else self._body[:amount]

    def __enter__(self) -> _FakeResponse:
        """Support the ``with opener.open(...)`` shape of the real transport."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Leave the response readable after the block, as urllib does."""
        return None


class _FakeTransport:
    """A scripted stand-in for the opener, counting every outbound attempt."""

    def __init__(self, steps: list[_Step]) -> None:
        self._steps = steps
        self.attempts = 0

    def open(self, fullurl: Any, data: Any = None, timeout: Any = None) -> _FakeResponse:
        """Answer one attempt from the script; the last step repeats."""
        del fullurl, data, timeout
        self.attempts += 1
        step = self._steps[min(self.attempts - 1, len(self._steps) - 1)]
        if isinstance(step, Exception):
            raise step
        status, body = step
        if status == 200:
            return _FakeResponse(status, body)
        raise urllib.error.HTTPError(
            "https://example.invalid/", status, "scripted", _headers(body), io.BytesIO(body)
        )


def _forbid_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the real socket path an error, so no patch gap can dial out."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("the real HTTP transport was opened")

    monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", refuse)


def _install_transport(monkeypatch: pytest.MonkeyPatch, steps: list[_Step]) -> _FakeTransport:
    """Replace only the outbound boundary with a scripted, counted fake."""
    transport = _FakeTransport(steps)

    def build_opener(*handlers: object) -> _FakeTransport:
        del handlers
        return transport

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(urllib.request, "urlopen", transport.open)
    _forbid_sockets(monkeypatch)
    return transport


def _forbid_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any outbound attempt an error, so 'never fetches' is provable."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("a fetch was attempted")

    monkeypatch.setattr(urllib.request, "build_opener", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    _forbid_sockets(monkeypatch)


def _forbid_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any parse an error, so 'sealed before parsing' is provable."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("a parser ran for a capture that was not OK")

    monkeypatch.setattr(TijoriSource, "parse_all_tables_bytes", refuse)
    monkeypatch.setattr(TijoriSource, "parse_table_bytes", refuse)
    monkeypatch.setattr(tijori_source_module, "build_all_tijori_tables", refuse)


def _record_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Capture every backoff delay instead of spending it."""
    delays: list[float] = []
    monkeypatch.setattr(time, "sleep", delays.append)
    return delays


def _source(*, max_retries: int = 3, expected_company_id: int | None = COMPANY_ID) -> TijoriSource:
    """One adapter with injected credentials and no environment reads."""
    return TijoriSource(
        TijoriSourceConfig(
            credentials=TijoriCredentials(session_cookie=SecretStr(SESSION_COOKIE)),
            expected_company_id=expected_company_id,
            max_retries=max_retries,
            retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
        )
    )


def _retain(store: SnapshotStore) -> Any:
    """Run one acquisition through the retention seam."""
    return _retention_module().retain_tijori_tables(
        _source(), store, slug=SLUG, expected_symbol=SYMBOL
    )


def _retain_page(
    monkeypatch: pytest.MonkeyPatch, root: Path, page: bytes
) -> tuple[SnapshotStore, Any]:
    """Serve one scripted 200 page and retain it."""
    _install_transport(monkeypatch, [(200, page)])
    store = SnapshotStore(root)
    return store, _retain(store)


def _captures(store: SnapshotStore) -> tuple[CaptureRecord, ...]:
    """Every capture retained for the financials route of this slug."""
    capture = _capture_module()
    return store.list_captures(capture.TIJORI_SOURCE_ID, capture.FINANCIALS_SURFACE, SLUG)


def _cli_failure_line(capsys: pytest.CaptureFixture[str]) -> str:
    """The one stderr line the command writes for a capture it could not use."""
    lines = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("tijori-tables: capture ")
    ]
    assert len(lines) == 1, lines
    return lines[0]


def _native(name: str) -> str:
    """One native outcome value, named as the seam declares it."""
    value: str = getattr(_capture_module(), name)
    return value


def test_ok_page_is_retained_verbatim_and_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An authenticated page is kept byte-for-byte and parsed from what was kept.

    Parsed tables and retained bytes must not drift apart: one instant, one record.
    """
    capture = _capture_module()
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", _fixture_bytes())

    record = retention.record
    assert record.outcome.code is OutcomeCode.OK
    assert record.outcome.native_kind == capture.FINANCIALS_PAGE_OUTCOME_KIND
    assert record.outcome.native_value == _native("AUTHENTICATED_PAGE")
    assert record.http_status == 200
    assert record.media_type == MEDIA_TYPE
    assert record.content_encoding is None
    assert store.read_body(record) == _fixture_bytes()
    assert record.body.byte_count == len(_fixture_bytes())
    assert retention.parse_error is None
    assert retention.tables
    assert all(table.metadata.retrieved_at == record.retrieved_at for table in retention.tables)
    assert [item.capture_id for item in _captures(store)] == [record.capture_id]


def test_anonymous_shell_seals_auth_expired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A logged-out shell is sealed as expired auth without any parser running.

    Today it arrives as a parse error, hiding a renewable credential inside schema drift.
    """
    _forbid_parsing(monkeypatch)
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", _anonymous_page())

    record = retention.record
    assert record.outcome.code is OutcomeCode.AUTH_EXPIRED
    assert record.outcome.native_value == _native("IS_AUTH_FALSE")
    assert store.read_body(record) == _anonymous_page()
    assert retention.tables == ()
    assert retention.parse_error is None


@pytest.mark.parametrize(
    ("details", "native_name"),
    [
        pytest.param(_OTHER_SYMBOL_DETAILS, "SYMBOL_MISMATCH", id="symbol"),
        pytest.param(_OTHER_ID_DETAILS, "COMPANY_ID_MISMATCH", id="company_id"),
    ],
)
def test_wrong_company_seals_identity_mismatch(
    details: bytes, native_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page about another company is sealed as a mismatch, bytes kept, nothing parsed.

    The retained body is the only proof of which company the vendor actually served.
    """
    page = _variant(_COMPANY_DETAILS, details)
    _forbid_parsing(monkeypatch)
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", page)

    record = retention.record
    assert record.outcome.code is OutcomeCode.IDENTITY_MISMATCH
    assert record.outcome.native_value == _native(native_name)
    assert store.read_body(record) == page
    assert retention.tables == ()
    assert retention.parse_error is None


def test_disabled_feature_locks_never_classify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabled UI feature locks are metadata on an OK capture, never a refusal.

    Reading them as a plan refusal would discard tables whose data is on the page.
    """
    page = _variant(_LOCKS_ISLAND, _DISABLED_LOCKS)
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", page)

    assert retention.record.outcome.code is OutcomeCode.OK
    assert retention.record.outcome.native_value == _native("AUTHENTICATED_PAGE")
    assert store.read_body(retention.record) == page
    access = retention.tables[0].metadata.access
    assert access.financials_locks_status is TijoriIslandStatus.PRESENT
    assert access.feature_locks
    assert all(not flag.enabled for lock in access.feature_locks for flag in lock.flags)


def test_parse_failure_keeps_committed_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A page the parser cannot read is still retained, and the CLI says so with exit 2.

    The bytes are kept so a parser gap is fixed and replayed, never re-fetched.
    """
    page = _variant(_FINANCIALS_ISLAND, None)
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", page)

    assert retention.record.outcome.code is OutcomeCode.OK
    assert store.read_body(retention.record) == page
    assert retention.tables == ()
    assert _FINANCIALS_ISLAND in (retention.parse_error or "")

    out_dir = tmp_path / "tables"
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", SESSION_COOKIE)
    assert _run_cli(out_dir, tmp_path / "cli-snapshots") == 2
    assert _FINANCIALS_ISLAND in _cli_failure_line(capsys)
    assert not out_dir.exists() or list(out_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("status", "code", "native_name"),
    [
        pytest.param(429, OutcomeCode.RATE_LIMITED, "HTTP_429", id="rate_limited"),
        pytest.param(403, OutcomeCode.CLIENT_BLOCKED, "HTTP_403", id="blocked"),
    ],
)
def test_http_429_is_terminal_and_retained(
    status: int,
    code: OutcomeCode,
    native_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rate limit or a block is retained once and never retried.

    Retrying either is how a polite client becomes an abusive one.
    """
    delays = _record_sleeps(monkeypatch)
    transport = _install_transport(monkeypatch, [(status, ERROR_BODY)])
    store = SnapshotStore(tmp_path / "snapshots")
    retention = _retain(store)

    record = retention.record
    assert record.outcome.code is code
    assert record.outcome.native_value == native_name
    assert record.http_status == status
    assert store.read_body(record) == ERROR_BODY
    assert transport.attempts == 1
    assert delays == []
    assert len(_captures(store)) == 1
    assert retention.tables == ()


def test_transport_failure_retains_every_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every attempt is committed, failures included, before the run succeeds.

    A retry that leaves no trace makes an intermittent vendor look healthy.
    """
    delays = _record_sleeps(monkeypatch)
    failure = urllib.error.URLError("synthetic transport failure")
    transport = _install_transport(monkeypatch, [failure, failure, (200, _fixture_bytes())])
    store = SnapshotStore(tmp_path / "snapshots")
    retention = _retain(store)

    records = _captures(store)
    assert transport.attempts == 3
    assert len(records) == 3
    assert [record.outcome.code for record in records] == [
        OutcomeCode.TRANSPORT_ERROR,
        OutcomeCode.TRANSPORT_ERROR,
        OutcomeCode.OK,
    ]
    assert all(record.outcome.native_value == "URLError" for record in records[:2])
    assert all(record.capture_id.endswith("-nobody") for record in records[:2])
    assert all(record.body is None and record.http_status is None for record in records[:2])
    assert retention.record.capture_id == records[-1].capture_id
    assert retention.tables
    assert len(delays) == 2
    assert 0 < delays[0] < delays[1]


def test_replay_never_fetches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retained capture reproduces its tables offline, stamped with its own instant.

    Re-deriving must work with the vendor unreachable, and must not restamp evidence.
    """
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", _fixture_bytes())
    record = retention.record

    _forbid_transport(monkeypatch)
    tables = _retention_module().replay_tijori_tables(
        store, record, expected_symbol=SYMBOL, expected_company_id=COMPANY_ID
    )

    assert [table.key for table in tables] == [table.key for table in retention.tables]
    assert [table.rows for table in tables] == [table.rows for table in retention.tables]
    assert all(table.metadata.retrieved_at == record.retrieved_at for table in tables)

    observations = _parsers().parse_pl_bytes(
        store.read_body(record),
        slug=SLUG,
        expected_symbol=SYMBOL,
        expected_company_id=COMPANY_ID,
        period_end=QUARTER_END,
        retrieved_at=record.retrieved_at,
    )
    assert observations
    assert all(item.provenance.retrieved_at == record.retrieved_at for item in observations)


def test_replay_refuses_non_ok_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replaying a sealed failure is refused by capture id, not parsed hopefully.

    Returning no tables would make a dead credential look like an empty company.
    """
    _forbid_parsing(monkeypatch)
    store, retention = _retain_page(monkeypatch, tmp_path / "snapshots", _anonymous_page())
    record = retention.record

    _forbid_transport(monkeypatch)
    with pytest.raises(ValueError, match=re.escape(record.capture_id)):
        _retention_module().replay_tijori_tables(
            store, record, expected_symbol=SYMBOL, expected_company_id=COMPANY_ID
        )


def _run_cli(out_dir: Path, snapshot_root: Path) -> int:
    """Run the tijori-tables command for one table against injected roots."""
    argv = ["tijori-tables", "--stock", SYMBOL, "--table", SINGLE_TABLE.value]
    argv += ["--out", str(out_dir), "--snapshot-root", str(snapshot_root)]
    return main(argv)


def test_cli_writes_json_and_capture_and_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command keeps its stdout and JSON contract while gaining a retained capture.

    A cut-over that changes artifacts, or exits 0 on a sealed refusal, is not safe.
    """
    _retention_module()
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", SESSION_COOKIE)
    _install_transport(monkeypatch, [(200, _fixture_bytes())])
    out_dir = tmp_path / "tables"
    snapshot_root = tmp_path / "snapshots"

    assert _run_cli(out_dir, snapshot_root) == 0
    assert capsys.readouterr().out == "table\trows\tcolumns\tplan_tier\nfr_c\t8\t2\tfree\n"

    record = _captures(SnapshotStore(snapshot_root))[0]
    capture_dir = snapshot_root / "tijori" / "financials" / SLUG / record.capture_id
    assert (capture_dir / "record.json").is_file()
    expected = _parsers().parse_table_bytes(
        SnapshotStore(snapshot_root).read_body(record),
        key=SINGLE_TABLE.value,
        slug=SLUG,
        expected_symbol=SYMBOL,
        expected_company_id=COMPANY_ID,
        retrieved_at=record.retrieved_at,
    )
    written = (out_dir / f"{SINGLE_TABLE.value}.json").read_text(encoding="utf-8")
    assert written == expected.model_dump_json(indent=2) + "\n"

    refused_out = tmp_path / "refused"
    _install_transport(monkeypatch, [(200, _anonymous_page())])
    assert _run_cli(refused_out, tmp_path / "refused-snapshots") == 2
    stderr_line = _cli_failure_line(capsys)
    assert OutcomeCode.AUTH_EXPIRED.value in stderr_line
    assert _native("IS_AUTH_FALSE") in stderr_line
    assert not refused_out.exists() or list(refused_out.iterdir()) == []


def test_request_identity_carries_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retained route names the slug only, and no record echoes the cookie.

    A capture tree holding the session cookie is replayable credentials at rest.
    """
    capture = _capture_module()
    request = capture.financials_request(SLUG)
    assert request.source_id == capture.TIJORI_SOURCE_ID
    assert request.surface == capture.FINANCIALS_SURFACE
    assert request.request_key == SLUG
    assert request.parameters == ()

    root = tmp_path / "snapshots"
    _retain_page(monkeypatch, root, _fixture_bytes())
    documents = [path.read_text(encoding="utf-8") for path in root.rglob("record.json")]
    assert documents
    assert all(SESSION_COOKIE not in document for document in documents)


def test_existing_fetchers_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding retention leaves the legacy fetchers, and their now-stamp, untouched.

    Every other Tijori surface still calls these; a silent change here is a regression.
    """
    _retention_module()

    def fetch_fixture(source: TijoriSource, slug: str, credentials: TijoriCredentials) -> bytes:
        del source, credentials
        assert slug == SLUG
        return _fixture_bytes()

    monkeypatch.setattr(TijoriSource, "_fetch_pl_bytes", fetch_fixture)
    _forbid_sockets(monkeypatch)
    before = datetime.now(tz=UTC)
    tables: tuple[TijoriTable, ...] = _source().fetch_all_tables(slug=SLUG, expected_symbol=SYMBOL)

    assert [table.key.value for table in tables] == list(PUBLISHED_TABLE_KEYS)
    assert all(table.metadata.retrieved_at >= before for table in tables)
    unused_root = tmp_path / "snapshots"
    assert not unused_root.exists()
