"""Synthetic fixtures and seams for the ``screener-screen`` test modules.

No test opens a socket and no fixture here is a captured page: every body below
is built from the *structure* the live surface was verified to have (a repeating
header row inside ``tbody``, a query-dependent column set, two ``options`` blocks
inside ``.pagination``, three company-link shapes) with invented queries,
companies, slugs, ids and numbers. The captures themselves are orchestrator-only
and never reach a fixture.

Two conventions are inherited from :mod:`screener_company_support` on purpose:
the transport seam is pinned at ``_fetch_bytes`` so the production code still
builds its own URLs — which makes every value assertion also a URL assertion —
and header-level questions reach one level lower, through
:func:`screener_company_support.capture_requests`.

The Slice 3 modules are reached through :class:`_Module` rather than imported at
the top. These are acceptance tests written before the implementation exists, so
a top-level import would collapse fourteen independently red tests into one
collection error and hide which requirement each of them pins.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr

# The markup layer, re-exported so every ``support.<builder>`` reference in the
# test modules keeps resolving from here after the split.
from screener_screen_fixtures import (  # noqa: F401
    ACCOUNT_LINK,
    LIVE_HEADER_BLOCK,
    LIVE_HEADER_COUNT,
    LIVE_ROW_COUNT,
    LIVE_ROWS_PER_PAGE,
    LOGOUT_FORM,
    MINIMAL_TABLE_CLASS,
    MOVED_PAGE_ANCHORS,
    NARROW_LABELS,
    NESTED_EXPORT_ANCHORS,
    NESTED_PAGE_ANCHORS,
    NON_ANCHOR_CONTROL,
    PAGE_SIZE_ANCHORS,
    SELECTOR_QUERY,
    STRAY_PAGE_SIZE_ANCHOR,
    TABLE_CLASS,
    WIDE_LABELS,
    SyntheticRow,
    data_row,
    empty_pagination,
    empty_table,
    header_row,
    live_page,
    malformed_pages,
    nested_options_pagination,
    non_anchor_pagination,
    one_row,
    page,
    page_of,
    pagination,
    results_page,
    results_table,
    row_page,
    row_shapes,
    rows_for,
    selector_href,
    single_page,
    table_of,
    table_with_displaced_row,
    table_without_tbody,
    walk,
    xml_declared_page,
    zero_result_page,
)

from fundamentals.api.cli import main
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    ScreenerCredentials,
    ScreenerDocumentFetch,
    ScreenerSessionConfig,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import parse_document


class _Module:
    """Deferred attribute access into a Slice 3 module.

    Every lookup happens at call time, so a module that does not exist yet fails
    the one test that asked for it instead of the whole file.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        """Resolve one public name out of the named module."""
        return getattr(importlib.import_module(self._name), attribute)


models = _Module("fundamentals.ingest.screener_screen_models")
screen = _Module("fundamentals.ingest.screener_screen")
screen_cli = _Module("fundamentals.api.screener_screen_cli")

COMMAND = "screener-screen"
SESSION_ENV = "SCREENER_SESSION_COOKIE"
SESSION_TOKEN = "fixture-session-token"

# Two invented queries of different widths. The seam-defining fact of this slice
# is that the column set follows the query, so the fixtures must differ in it.
QUERY = "Alpha ratio > 11 AND Beta score < 3"
WIDE_QUERY = "Alpha ratio > 11 AND Beta score < 3 AND Zeta var 5Years > 4"
EMPTY_QUERY = "Alpha ratio > 8642086420"

TABLE_ID = "screen-results"
SOURCE_ID = "screener-subscriber"
FETCHED_AT = datetime(2026, 9, 2, tzinfo=UTC)
TSV_HEADER = "outcome\tpages\trows\tcolumns\tartifact"
ARTIFACT_FILENAME = "screener_screen.json"
PAGES_DIRNAME = "pages"
PAGE_FILENAME_TEMPLATE = "page_{number:04d}.raw.html"


class Recorder:
    """Every screen request the pinned transport saw, how it was marked, and by whom.

    ``sources`` holds the receiver of each call rather than a count of them.
    Discarding it would let an implementation build a fresh
    :class:`ScreenerSessionSource` per page and still pass — and a new source is a
    new spacing clock and a new 429 budget, which is precisely the sharing this
    slice depends on.
    """

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.xhr: list[bool] = []
        self.sources: list[ScreenerSessionSource] = []


# What each frozen model carries, and nothing else. Held as data because the
# risk is not a wrong field but an extra one: a derived ``complete`` flag, a
# second copy of the raw serial, or a ``logged_in`` boolean that can disagree
# with the admission rule that produced it.
MODEL_FIELDS = {
    "ScreenAcquisitionConfig": {"max_pages"},
    "ScreenColumn": {"index", "label"},
    "ScreenCell": {"column_index", "value", "raw_text", "provenance"},
    "ScreenCompany": {"slug", "display_name", "data_row_company_id", "consolidated"},
    "ScreenRow": {"page_number", "serial_number", "company", "cells"},
    "ScreenPageMetadata": {
        "page_number",
        "source_url",
        "http_status",
        "offered_pages",
        "content_sha256",
        "byte_count",
        "fetched_at",
    },
    "ScreenFailure": {"page_number", "source_url", "refusal", "detail", "content_sha256"},
    "ScreenArtifact": {
        "source_id",
        "query",
        "outcome",
        "columns",
        "rows",
        "pages",
        "incomplete_reason",
        "failure",
    },
    "ScreenRun": {"artifact", "documents"},
    "ScreenerScreenCliRun": {"run", "artifact_path", "page_paths"},
}


def rebuilt(model: Any, **overrides: Any) -> Any:
    """The same model built again through validation with one field replaced."""
    return type(model)(**{**model.model_dump(), **overrides})


def config() -> ScreenerSessionConfig:
    """A config carrying a fixture cookie; the seam never reads its value."""
    return ScreenerSessionConfig(
        credentials=ScreenerCredentials(session_cookie=SecretStr(SESSION_TOKEN)),
        min_request_spacing_seconds=0,
    )


def source() -> ScreenerSessionSource:
    """One subscriber source, shared by every page of a walk."""
    return ScreenerSessionSource(config())


def serve(
    monkeypatch: pytest.MonkeyPatch,
    bodies: dict[int, str],
    *,
    refusals: dict[int, ScreenerSessionError] | None = None,
) -> Recorder:
    """Pin the transport seam to synthetic bodies keyed by requested page number.

    Keying on the ``page`` value the production code encodes makes every body
    assertion also an assertion that the URL was built correctly. A request for
    a page no fixture offers fails here rather than being answered, because
    probing an unoffered page is itself the defect.
    """
    recorder = Recorder()

    def fetch_bytes(
        source: ScreenerSessionSource,
        url: str,
        credentials: ScreenerCredentials,
        *,
        xhr: bool = False,
    ) -> tuple[int, bytes]:
        del credentials
        recorder.urls.append(url)
        recorder.xhr.append(xhr)
        recorder.sources.append(source)
        number = requested_page(url)
        if refusals is not None and number in refusals:
            raise refusals[number]
        if number not in bodies:
            raise AssertionError(f"page {number} was requested but never offered: {url}")
        return 200, bodies[number].encode("utf-8")

    monkeypatch.setenv(SESSION_ENV, SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)
    return recorder


def serve_transport_failure(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> list[str]:
    """Fail every request inside the *real* transport, one level below ``_fetch_bytes``.

    The other helpers pin ``_fetch_bytes`` itself, which is above every log line
    and every message this slice's transport writes — so a question about what
    the transport says when a request fails has to be asked of the real one.
    Backoff sleeping is removed because the retry schedule is not what is being
    pinned here and two real backoffs would cost six seconds.
    """
    requested: list[str] = []

    class _FailingOpener:
        def open(self, request: Any, timeout: float | None = None) -> Any:
            del timeout
            requested.append(request.full_url)
            raise error

    monkeypatch.setenv(SESSION_ENV, SESSION_TOKEN)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: _FailingOpener())
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    return requested


def requested_page(url: str) -> int:
    """The page number one built screen URL asks for."""
    return int(parse_qs(urlsplit(url).query)["page"][0])


def acquire(
    monkeypatch: pytest.MonkeyPatch,
    bodies: dict[int, str],
    *,
    query: str = QUERY,
    max_pages: int | None = None,
    refusals: dict[int, ScreenerSessionError] | None = None,
    injected: ScreenerSessionSource | None = None,
) -> tuple[Any, Recorder]:
    """Acquire one query through the real code path against the pinned seam."""
    recorder = serve(monkeypatch, bodies, refusals=refusals)
    settings = {} if max_pages is None else {"max_pages": max_pages}
    run = screen.acquire_screen(
        query,
        source=injected if injected is not None else source(),
        config=models.ScreenAcquisitionConfig(**settings),
    )
    return run, recorder


def fetch(body: str, *, page_number: int = 1, query: str = QUERY) -> ScreenerDocumentFetch:
    """The retained response record one pure reader is handed for a body."""
    raw = body.encode("utf-8")
    return ScreenerDocumentFetch(
        raw_body=raw,
        source_url=models.screen_url(query, page_number),
        http_status=200,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        fetched_at=FETCHED_AT,
    )


def read_table(body: str, *, page_number: int = 1) -> tuple[Any, Any]:
    """Read one body through the pure table reader."""
    columns, rows = screen.read_screen_table(
        parse_document(body),
        fetch=fetch(body, page_number=page_number),
        page_number=page_number,
    )
    return columns, rows


def read_pagination(body: str, *, requested_page_number: int = 1) -> Any:
    """Read one body through the pure pagination reader."""
    return screen.read_screen_pagination(parse_document(body), requested_page=requested_page_number)


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bodies: dict[int, str],
    *extra: str,
    query: str = QUERY,
    refusals: dict[int, ScreenerSessionError] | None = None,
    out_dir: Path | None = None,
) -> tuple[int, Path, Recorder]:
    """Run ``fundamentals screener-screen`` end to end against the pinned seam."""
    recorder = serve(monkeypatch, bodies, refusals=refusals)
    target = out_dir if out_dir is not None else tmp_path / "out"
    exit_code = main([COMMAND, "--query", query, "--out", str(target), *extra])
    return exit_code, target, recorder


def artifact_of(out_dir: Path) -> Path:
    """The published artifact path inside one output directory."""
    return out_dir / ARTIFACT_FILENAME


def page_file(out_dir: Path, number: int) -> Path:
    """The retained body path for one fetched page position."""
    return out_dir / PAGES_DIRNAME / PAGE_FILENAME_TEMPLATE.format(number=number)


def payload_of(out_dir: Path) -> dict[str, Any]:
    """The published artifact of one output directory, parsed."""
    loaded: dict[str, Any] = json.loads(artifact_of(out_dir).read_text(encoding="utf-8"))
    return loaded


def artifact_body(payload: dict[str, Any]) -> dict[str, Any]:
    """The artifact record inside a published payload.

    The plan freezes the artifact's file name and its fields, not the envelope
    the file writes them in, so both shapes are accepted here rather than pinning
    a detail the contract leaves open.
    """
    if "outcome" in payload:
        return payload
    nested: dict[str, Any] = payload["artifact"]
    return nested


def artifact_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The per-page metadata records inside a published payload."""
    return list(artifact_body(payload)["pages"])


class FirstCreationError(Exception):
    """Raised in place of the first directory an invocation tries to create."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path = path


def intercept_first_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop an invocation at the first directory it creates, naming that path.

    The default output root is derived from the repository, not from the working
    directory, so a test of the default-path algorithm cannot be contained by
    ``chdir`` and must never be allowed to reach the disk. Preflight establishes
    the output directory before the first request, so the first creation attempt
    *is* the resolved destination — which makes the frozen excerpt, truncation,
    fallback and digest observable without writing a byte.
    """

    def refuse(
        self: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        del mode, parents, exist_ok
        raise FirstCreationError(self)

    monkeypatch.setattr(Path, "mkdir", refuse)


def record_publications(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Every destination the no-clobber writer creates, in the order it created them.

    ``write_bytes_no_clobber`` publishes by linking a temporary file onto its
    target, so that link *is* the moment a file becomes visible. Recording the
    order is the only way to tell "the artifact was written last" from "the
    artifact was written first and then rolled back" — the two leave the same
    directory behind.
    """
    destinations: list[Path] = []
    linked = os.link

    def record(source_path: Any, target: Any, *, follow_symlinks: bool = True) -> None:
        destinations.append(Path(target))
        linked(source_path, target, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "link", record)
    return destinations
