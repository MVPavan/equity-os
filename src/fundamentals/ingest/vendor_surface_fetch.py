"""One bounded, raw-first GET boundary for the two vendor sites."""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request

import structlog
from psycopg import Connection
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, SecretStr

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
)
from fundamentals.ingest.http_session import NoRedirectHandler, RequestPacer, read_bounded_capture
from fundamentals.ingest.tijori_capture import (
    TIJORI_RIGHTS,
    classify_http_status,
    transport_failure_outcome,
)
from fundamentals.store.snapshot_store import SnapshotStore


class Site(StrEnum):
    """Registered vendor source ids."""

    SCREENER = "screener-subscriber"
    TIJORI = "tijori"


SITE_AUTHORITY: Mapping[Site, str] = {
    Site.SCREENER: "www.screener.in",
    Site.TIJORI: "www.tijorifinance.com",
}
DENY_WORDS = frozenset(
    (
        "logout delete remove add create rename save edit follow unfollow subscribe toggle upgrade "
        "payment alert connect sync reset refresh ai flag ask mark share-by-email"
    ).split()
)
DENY_KEYS = DENY_WORDS | frozenset(
    "ack acked mark mark_read mark_as_seen seen read dismiss".split()
)
NAMED_PATHS = (
    "/in/watchlist/",
    "/watchlist/",
    "/api/portfolio/task-status/",
    "/api/portfolio/refresh-status/",
    "/concalls/summary/",
    "/results/concall-summaries/",
)
LOG = structlog.get_logger()


class SiteSession(BaseModel):
    """A session injected at the composition root; never serialized to captures."""

    model_config = ConfigDict(frozen=True)
    site: Site
    session_cookie: SecretStr
    cookie_name: str


class Fetched(BaseModel):
    """The durable capture and response address, before registration."""

    model_config = ConfigDict(frozen=True)
    record: CaptureRecord
    url: str
    location: str | None


class SiteStopped(Exception):  # noqa: N818 - plan interface
    """A durable site stop, optionally carrying the response that caused it."""

    def __init__(self, site: Site, fetched: Fetched | None = None) -> None:
        self.site, self.fetched = site, fetched
        super().__init__(f"site stopped: {site}")


class SiteBusy(Exception):  # noqa: N818 - plan interface
    """Another command owns this site's session lock."""


class SiteLock(Protocol):
    """Command-lifetime exclusivity per source."""

    def acquire(self, site: Site) -> bool:
        """Acquire or retain this command's lock."""
        ...


class PgSiteLock:
    """Hold one pooled connection per site until command completion."""

    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool
        self.connections: dict[Site, Connection[Any]] = {}

    def acquire(self, site: Site) -> bool:
        """Try a session advisory lock without waiting for another command."""
        if site in self.connections:
            return True
        conn = self.pool.getconn()
        row = conn.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ("eqos.vendor_surface." + site,)
        ).fetchone()
        conn.commit()
        if row is not None and row[0]:
            self.connections[site] = conn
            return True
        self.pool.putconn(conn)
        return False

    def close(self) -> None:
        """Release locks before returning their sessions to the pool."""
        for site, conn in self.connections.items():
            try:
                conn.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s))", ("eqos.vendor_surface." + site,)
                )
                conn.commit()
            finally:
                self.pool.putconn(conn)
        self.connections.clear()


def normalise(url: str) -> str:
    """Decode the path once and collapse slash and dot segments."""
    parts = urlsplit(url)
    path = posixpath.normpath("/" + unquote(parts.path).lstrip("/"))
    if parts.path.endswith("/") and path != "/":
        path += "/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def is_denied(url: str) -> bool:
    """Apply runbook §1 to a normalized URL, exempting company slugs."""
    parts = urlsplit(url)
    path = parts.path.lower().rstrip("/") + "/"
    if any(key.lower() in DENY_KEYS for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
        return True
    if path == "/in/edit-columns/" or re.fullmatch(r"/capsules/[0-9]+/stock-alerts/", path):
        return False
    if path.startswith(NAMED_PATHS) or (
        path.startswith("/annual-reports/") and path.endswith("/summary/")
    ):
        return True
    segments = path.strip("/").split("/")
    return any(
        segment == word
        or segment.startswith((word + "-", word + "_"))
        or segment.endswith(("-" + word, "_" + word))
        for index, segment in enumerate(segments)
        if index == 0 or segments[index - 1] != "company"
        for word in DENY_WORDS
    )


def request_key(url: str) -> str:
    """The address identity shared by capture registrations and canaries."""
    return hashlib.sha256(url.encode()).hexdigest()


class VendorFetcher:
    """Keep every response before any parsing, and stop a site durably on refusal."""

    def __init__(
        self,
        store: SnapshotStore,
        sessions: Mapping[Site, SiteSession],
        opener: OpenerDirector,
        stop_dir: Path,
        lock: SiteLock,
        *,
        spacing_seconds: float = 1.5,
        site_budget: int = 350,
        timeout_seconds: float = 30.0,
        max_bytes: int = 20_000_000,
    ) -> None:
        # Returning None from NoRedirectHandler does not suppress a second redirect handler.
        # urllib initializes this registry; its type stubs omit the attribute.
        handlers: dict[str, dict[int | str, list[object]]] = vars(opener)["handle_error"]
        for chain in handlers.get("http", {}).values():
            chain[:] = [
                handler for handler in chain if not isinstance(handler, HTTPRedirectHandler)
            ]
        opener.add_handler(NoRedirectHandler())
        self.store, self.sessions, self.opener = store, sessions, opener
        self.stop_dir, self.lock = stop_dir, lock
        self.budget, self.timeout, self.max_bytes = site_budget, timeout_seconds, max_bytes
        self.counts = dict.fromkeys(Site, 0)
        self.pacers = {site: RequestPacer(spacing_seconds) for site in Site}

    def remaining(self, site: Site) -> int:
        """Requests remaining for this site's command budget."""
        return self.budget - self.counts[site]

    def get(self, site: Site, surface: str, url: str, *, xhr: bool = False) -> Fetched:
        """Validate before opening; store before raising a durable stop."""
        url = normalise(url)
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != SITE_AUTHORITY[site] or is_denied(url):
            raise ValueError("refused vendor URL")
        marker = self.stop_dir / f"STOP-{site}"
        if marker.exists():
            raise SiteStopped(site)
        if self.remaining(site) <= 0:
            raise ValueError("site request budget exhausted")
        if not self.lock.acquire(site):
            raise SiteBusy(site)
        session = self.sessions[site]
        headers = {"Cookie": f"{session.cookie_name}={session.session_cookie.get_secret_value()}"}
        if xhr:
            headers["X-Requested-With"] = "XMLHttpRequest"
        self.pacers[site].wait_for_slot()
        self.counts[site] += 1
        LOG.info("vendor_surface_fetch", site=site, url=urlunsplit((*parts[:3], "", "")))
        retrieved_at = datetime.now(UTC)
        status, location, media, encoding, raw, completeness, issue = (
            None,
            None,
            None,
            None,
            None,
            BodyCompleteness.ABSENT,
            None,
        )
        try:
            try:
                response = self.opener.open(
                    Request(url, headers=headers, method="GET"), timeout=self.timeout
                )
            except HTTPError as error:
                response = error
            with response:
                status = response.code
                location = response.headers.get("Location")
                media, encoding = (
                    response.headers.get("Content-Type"),
                    response.headers.get("Content-Encoding"),
                )
                length = response.headers.get("Content-Length")
                read = read_bounded_capture(
                    response,
                    self.max_bytes,
                    timeout_seconds=self.timeout,
                    expected_bytes=int(length) if length and length.isdigit() else None,
                )
                raw, completeness, issue = read.raw_body, read.completeness, read.issue
            outcome = (
                OutcomeRecord(
                    code=OutcomeCode.OK, native_kind="vendor_http", native_value="HTTP_200"
                )
                if status == 200
                else classify_http_status(status)
            )
        except (URLError, TimeoutError, OSError) as error:
            outcome = transport_failure_outcome(error)
        if issue is not None:
            outcome = OutcomeRecord(
                code=OutcomeCode.TRANSPORT_ERROR,
                native_kind="vendor_http",
                native_value=issue.value,
            )
        body = (
            None
            if raw is None
            else BlobRef(
                source_id=site, content_sha256=hashlib.sha256(raw).hexdigest(), byte_count=len(raw)
            )
        )
        record = CaptureRecord.make(
            RequestIdentity(source_id=site, surface="vs." + surface, request_key=request_key(url)),
            retrieved_at,
            status,
            media,
            encoding,
            body,
            outcome,
            TIJORI_RIGHTS,
            schema_version=CAPTURE_SCHEMA_VERSION,
            body_completeness=completeness,
            body_read_issue=issue,
        )
        self.store.put_capture(record, raw)
        fetched = Fetched(record=record, url=url, location=location)
        target = urlsplit(normalise(urljoin(url, location or "")))
        login = target.netloc.lower() == parts.netloc.lower() and any(
            word in target.path.lower() for word in ("login", "signin")
        )
        if status in (403, 429, 503) or (status is not None and 300 <= status < 400 and login):
            self.stop_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"{record.capture_id} {status}\n")
            raise SiteStopped(site, fetched)
        return fetched
