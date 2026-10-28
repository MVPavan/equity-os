"""Onboarding discovery: fetch, verify, record (plan D6 D4.2-D4.4, D3.4).

``discover`` walks the fixed request sequence for one NSE symbol through a ``Fetch`` (replay of
a discovery generation, or an acquiring transport), checking each surface's authority and the
URL's approved origin before its request. A denied request is kept as a capture-less
``NOT_AUTHORISED`` entry, and replay serves that recorded denial rather than today's table.
Anchor requests that fail or are not authorised abort with no record; a conflict or an anchor
refusal stops discovery and leaves the remaining units stopped. ``record`` keeps every fetched
body as a capture under one ``DISCOVERY`` input per unit and, in one transaction, locks the
verified identifier values, re-resolves them, re-checks each filing's identity at its filed
date against the owner, and writes a new issuer's identity rows, the onboarding record and its
unit states.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, LiteralString, NoReturn
from urllib.parse import parse_qsl, urlencode, urlsplit

import psycopg
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.onboarding import (
    ANCHOR_UNITS,
    OnboardingOutcome,
    OnboardingReason,
    Verdict,
    VerificationState,
    VerificationUnit,
    as_of_for,
)
from fundamentals.contracts.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
)
from fundamentals.contracts.source_catalog import (
    BSE_PEER_SEARCH,
    DOCUMENT_LISTINGS,
    DOCUMENT_ORIGINS,
    NSE_INTEGRATED_LISTING,
    NSE_MASTER,
    NSE_RESULTS_LISTING,
    NSE_XBRL_INSTANCE,
    SCREENER_PAGE,
    SCREENER_SEARCH,
    TIJORI_PAGE,
    TIJORI_SEARCH,
    UPSTOX_INSTRUMENTS,
    UPSTOX_ROUTED,
    UPSTOX_STATEMENT,
    SurfaceAuthority,
    SurfaceNotAuthorisedError,
    surface_authority,
)
from fundamentals.entity.identity_layers import (
    IdentifierRef,
    issuer_values,
    lock_identifiers,
    resolve_owner,
)
from fundamentals.entity.verification import (
    VERIFIED,
    Expected,
    FilingIdentity,
    conflict,
    deciding,
    exchange_state,
    filing_codes,
    filing_identity,
    financial_rule,
    framework_state,
    ingest_identity_state,
    instance_state,
    master_rows,
    outcome,
    screener_candidate,
    screener_page_state,
    tijori_candidate,
    tijori_page_state,
    upstox_rows_state,
    upstox_statement_state,
    xbrl_entity_state,
)
from fundamentals.evidence.capture_retention import Registration, capture_registration
from fundamentals.evidence.mapping import MappingSet, UnsupportedSchemaError
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.xbrl_adapter import parse_instance
from fundamentals.ingest.http_session import ResponseTooLargeError
from fundamentals.ingest.nse_filings import (
    EQUITY_MASTER_URL,
    INTEGRATED_LISTING,
    LEGACY_LISTING,
    filing_window,
    listing_rows,
    listing_url,
)
from fundamentals.ingest.upstox_retention import request_identity as upstox_request_identity
from fundamentals.pg.identity_seed import (
    MARKET_IN,
    SHARE_CLASS_EQUITY,
    EvidenceInputKind,
    ListingVenue,
)
from fundamentals.store.snapshot_store import SnapshotStore

MANIFEST_NAME = "discovery-manifest.json"
OK = "OK"
NOT_AUTHORISED = "NOT_AUTHORISED"
UPSTOX_ROUTE = "default"
TIMEOUT = "TIMEOUT"
TRANSPORT_ERROR = "TRANSPORT_ERROR"
TOO_LARGE = "TOO_LARGE"
FILINGS_CHECKED = 2
_IN = "IN"
_HTTPS = "https"
_NSE_WWW, _NSE_ARCHIVES = "www.nseindia.com", "nsearchives.nseindia.com"
_SCREENER, _TIJORI = "www.screener.in", "www.tijorifinance.com"
# The only origin each surface may be requested from (https, exact host): a listing's XBRL link
# or any other evidenced URL cannot send an authorised request elsewhere.
ORIGINS = {
    NSE_MASTER: _NSE_ARCHIVES,
    NSE_RESULTS_LISTING: _NSE_WWW,
    NSE_INTEGRATED_LISTING: _NSE_WWW,
    NSE_XBRL_INSTANCE: _NSE_ARCHIVES,
    BSE_PEER_SEARCH: "api.bseindia.com",
    SCREENER_SEARCH: _SCREENER,
    SCREENER_PAGE: _SCREENER,
    TIJORI_SEARCH: _TIJORI,
    TIJORI_PAGE: _TIJORI,
    UPSTOX_INSTRUMENTS: "assets.upstox.com",
    UPSTOX_STATEMENT: "api.upstox.com",
}
ORIGINS |= DOCUMENT_ORIGINS | {("nse", surface): _NSE_WWW for surface in DOCUMENT_LISTINGS}
_BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text={isin}"
_SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/?{query}"
_SCREENER_PAGE_URL = "https://www.screener.in/company/{symbol}/consolidated/"
_TIJORI_SEARCH_URL = "https://www.tijorifinance.com/api/v1/ind/company_search/?q={isin}"
_TIJORI_PAGE_URL = "https://www.tijorifinance.com/company/{slug}/financials/"
_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
_STATEMENT_URL = (
    "https://api.upstox.com/v2/fundamentals/{isin}/income-statement"
    "?fs=true&time_period=quarterly&type=consolidated"
)
_MEDIA_TYPE = "application/octet-stream"
_NATIVE_KIND = "onboarding-discovery"
_INPUT_LABEL = "discovery:{symbol}:{unit}"
_HIGH = "HIGH"
_MOVED = "the identity layers changed during onboarding; re-run"
_MANY_MASTER = "the NSE master lists {count} EQ rows for {symbol}"
_TIED = "two filings tie on the latest broadcast"
_ABORT_HTTP = "{surface} returned {outcome}"
_ABORT_AUTH = "{surface} is not authorised"
_BAD_REPLAY = "replay generation {folder}: {why}"


def screener_search_url(symbol: str) -> str:
    """The Screener search request for ``symbol``, its query URL-encoded (``M&M`` is one value)."""
    return _SCREENER_SEARCH_URL.format(query=urlencode({"q": symbol, "v": 3, "fts": 1}))


class Recorded(BaseModel):
    """What ``record`` wrote: the outcome, an admitted issuer's entity and each unit's input."""

    model_config = ConfigDict(frozen=True)

    outcome: OnboardingOutcome
    reason: str | None
    entity_id: int | None
    inputs: dict[VerificationUnit, int]


class OnboardingAbortError(RuntimeError):
    """An anchor request was unobservable or unauthorised: no record is written."""


class Request(BaseModel):
    """One discovery request."""

    model_config = ConfigDict(frozen=True)

    unit: VerificationUnit
    source_id: str
    surface: str
    url: str

    @property
    def key(self) -> str:
        """The manifest request key."""
        return request_key(self.surface, self.url)


class Response(BaseModel):
    """One response: ``OK`` with its body, or a failure outcome with none."""

    model_config = ConfigDict(frozen=True)

    outcome: str
    body: bytes | None
    retrieved_at: datetime


Fetch = Callable[[Request, bool], Response]  # (request, authorised) -> response
Send = Callable[[Request], tuple[int, bytes]]


class ManifestEntry(BaseModel):
    """One request of a discovery generation and where its body is kept."""

    model_config = ConfigDict(frozen=True)

    request_key: str
    source_id: str
    surface: str
    unit: VerificationUnit
    url: str
    filename: str | None
    sha256: str | None
    bytes: int | None
    retrieved_at: datetime
    outcome: str


class DiscoveryManifest(BaseModel):
    """A discovery generation: every request in order, and the window's ``as_of``."""

    model_config = ConfigDict(frozen=True)

    issuer: str
    authorization: str
    generation: int
    as_of: date
    entries: tuple[ManifestEntry, ...]


class Capture(BaseModel):
    """A fetched body kept as evidence of its unit."""

    model_config = ConfigDict(frozen=True)

    request: Request
    response: Response


class Discovery(BaseModel):
    """What discovery established, and for a resolved issuer its entity."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str | None
    isin: str | None
    scrip: str | None
    entity_id: int | None
    states: dict[VerificationUnit, Verdict]
    captures: tuple[Capture, ...]
    filings: tuple[tuple[FilingIdentity, date | None], ...] = ()


def request_key(surface: str, url: str) -> str:
    """``surface|`` and the sorted ``k=v`` pairs of the URL path and query."""
    parts = urlsplit(url)
    pairs = sorted([("path", parts.path), *parse_qsl(parts.query, keep_blank_values=True)])
    return f"{surface}|" + "&".join(f"{key}={value}" for key, value in pairs)


def authorised(request: Request, table: tuple[SurfaceAuthority, ...]) -> bool:
    """The surface is registered in ``table`` and the URL is on its approved https origin."""
    pair = (request.source_id, request.surface)
    try:
        surface_authority(*pair, table=table)
    except SurfaceNotAuthorisedError:
        return False
    parts = urlsplit(request.url)
    return parts.scheme == _HTTPS and parts.netloc == ORIGINS.get(pair)


def replay_fetch(folder: Path) -> Fetch:
    """Serve each recorded response only to its exact request (key, unit, source, surface, URL),
    a recorded denial included (today's authority table is not consulted); bodies are checked."""
    manifest = DiscoveryManifest.model_validate_json((folder / MANIFEST_NAME).read_bytes())
    served: dict[tuple[str, Request], Response] = {}
    for entry in manifest.entries:
        body = None
        if entry.filename is not None:
            body = (folder / entry.filename).read_bytes()
            if hashlib.sha256(body).hexdigest() != entry.sha256 or len(body) != entry.bytes:
                raise ValueError(_BAD_REPLAY.format(folder=folder, why=f"{entry.filename} altered"))
        recorded = entry.request_key, Request.model_validate(entry, from_attributes=True)
        if recorded in served or (entry.outcome == OK) != (body is not None):
            raise ValueError(_BAD_REPLAY.format(folder=folder, why=entry.request_key))
        served[recorded] = Response(
            outcome=entry.outcome, body=body, retrieved_at=entry.retrieved_at
        )
    master = [e for e in manifest.entries if (e.source_id, e.surface) == NSE_MASTER]
    if len(master) != 1 or as_of_for(master[0].retrieved_at) != manifest.as_of:
        raise ValueError(_BAD_REPLAY.format(folder=folder, why="as_of"))

    def fetch(request: Request, allowed: bool) -> Response:
        del allowed
        return served[request.key, request]

    return fetch


def acquiring_fetch(send: Send, clock: Callable[[], datetime], log: list[Capture]) -> Fetch:
    """Fetch through a live transport, logging every exchange (failures keep no body); a request
    not authorised is logged ``NOT_AUTHORISED`` and never sent."""

    def fetch(request: Request, allowed: bool) -> Response:
        body, result = None, NOT_AUTHORISED
        if allowed:
            try:
                status, body = send(request)
                result = OK if status == 200 else f"HTTP_{status}"
            except ResponseTooLargeError:
                result = TOO_LARGE
            except TimeoutError:
                result = TIMEOUT
            except OSError:
                result = TRANSPORT_ERROR
        response = Response(
            outcome=result, body=body if result == OK else None, retrieved_at=clock()
        )
        log.append(Capture(request=request, response=response))
        return response

    return fetch


def write_generation(
    folder: Path, issuer: str, authorization: str, generation: int, log: Sequence[Capture]
) -> None:
    """Write a generation's bodies and manifest (the master's retrieval fixes ``as_of``)."""
    folder.mkdir(parents=True)
    entries = []
    for index, item in enumerate(log):
        body, name = item.response.body, None
        if body is not None:
            name = f"{index:02d}.bin"
            (folder / name).write_bytes(body)
        entries.append(
            ManifestEntry(
                request_key=item.request.key,
                source_id=item.request.source_id,
                surface=item.request.surface,
                unit=item.request.unit,
                url=item.request.url,
                filename=name,
                sha256=hashlib.sha256(body).hexdigest() if body is not None else None,
                bytes=len(body) if body is not None else None,
                retrieved_at=item.response.retrieved_at,
                outcome=item.response.outcome,
            )
        )
    master = next(e for e in entries if (e.source_id, e.surface) == NSE_MASTER)
    manifest = DiscoveryManifest(
        issuer=issuer,
        authorization=authorization,
        generation=generation,
        as_of=as_of_for(master.retrieved_at),
        entries=tuple(entries),
    )
    (folder / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=1))


class _StopError(Exception):
    """Discovery stops: a conflict, or an anchor that cannot be verified."""


class _UnavailableError(Exception):
    """A vendor request failed."""


class _Run:
    """One discovery walk's requests, captures and unit states."""

    def __init__(self, symbol: str, fetch: Fetch, table: tuple[SurfaceAuthority, ...]) -> None:
        self.symbol, self.fetch, self.table = symbol, fetch, table
        self.states: dict[VerificationUnit, Verdict] = {
            VerificationUnit.RESULTS_PDF: (
                VerificationState.UNAVAILABLE,
                OnboardingReason.EXCLUDED_BY_RULE.value,
            )
        }
        self.captures: list[Capture] = []
        self.name: str | None = None
        self.isin: str | None = None
        self.scrip: str | None = None
        self.entity_id: int | None = None
        self.filings: list[tuple[FilingIdentity, date | None]] = []

    def get(self, unit: VerificationUnit, pair: tuple[str, str], url: str) -> bytes:
        """The body of one authorised, successful request."""
        anchor = unit in ANCHOR_UNITS
        request = Request(unit=unit, source_id=pair[0], surface=pair[1], url=url)
        response = self.fetch(request, authorised(request, self.table))
        if response.outcome == NOT_AUTHORISED:
            raise SurfaceNotAuthorisedError(_ABORT_AUTH.format(surface=pair[1]))
        if response.outcome != OK or response.body is None:
            if anchor:
                detail = _ABORT_HTTP.format(surface=pair[1], outcome=response.outcome)
                raise OnboardingAbortError(detail)
            raise _UnavailableError
        self.captures.append(Capture(request=request, response=response))
        return response.body

    def anchor(self, unit: VerificationUnit, pair: tuple[str, str], url: str) -> bytes:
        """An anchor body; an unauthorised anchor surface aborts."""
        try:
            return self.get(unit, pair, url)
        except SurfaceNotAuthorisedError as error:
            raise OnboardingAbortError(_ABORT_AUTH.format(surface=pair[1])) from error

    def set(self, unit: VerificationUnit, verdict: Verdict) -> None:
        """Record a unit; a conflict, or an anchor not verified, stops discovery."""
        self.states[unit] = verdict
        state = verdict[0]
        if state is VerificationState.CONFLICT or (
            unit in ANCHOR_UNITS and state is not VerificationState.VERIFIED
        ):
            raise _StopError

    def refuse(self, unit: VerificationUnit, reason: OnboardingReason) -> NoReturn:
        """An anchor is unsupported for ``reason``: discovery stops."""
        self.states[unit] = VerificationState.UNVERIFIED, reason.value
        raise _StopError

    def vendor(self, unit: VerificationUnit, check: Callable[[], Verdict]) -> None:
        """A vendor unit's verdict; unauthorised or failed requests are recorded, not fatal."""
        try:
            verdict = check()
        except SurfaceNotAuthorisedError:
            verdict = VerificationState.NOT_AUTHORISED, OnboardingReason.NOT_AUTHORISED.value
        except _UnavailableError:
            verdict = VerificationState.UNAVAILABLE, OnboardingReason.ACCESS_FAILED.value
        self.set(unit, verdict)

    def result(self) -> Discovery:
        """The states, every unit not reached stopped by the first conflict or refusal."""
        stopped = OnboardingReason.STOPPED_ON_REFUSAL
        if any(state is VerificationState.CONFLICT for state, _ in self.states.values()):
            stopped = OnboardingReason.STOPPED_ON_CONFLICT
        states = {
            unit: self.states.get(unit, (VerificationState.UNVERIFIED, stopped.value))
            for unit in VerificationUnit
        }
        return Discovery(
            symbol=self.symbol,
            name=self.name,
            isin=self.isin,
            scrip=self.scrip,
            entity_id=self.entity_id,
            states=states,
            captures=tuple(self.captures),
            filings=tuple(self.filings),
        )


def discover(
    symbol: str,
    fetch: Fetch,
    conn: psycopg.Connection[Any],
    table: tuple[SurfaceAuthority, ...],
    mapping_set: MappingSet,
) -> Discovery:
    """Verify one NSE symbol's units in the D4.2 order."""
    run = _Run(symbol, fetch, table)
    try:
        _anchors(run, conn, mapping_set)
        _vendors(run)
    except _StopError:
        pass
    return run.result()


def _anchors(run: _Run, conn: psycopg.Connection[Any], mapping_set: MappingSet) -> None:
    """Master, stable-id resolution, filing window, the two instances, then BSE."""
    exchange, xbrl = VerificationUnit.EXCHANGE, VerificationUnit.XBRL_ENTITY
    rows = master_rows(run.anchor(exchange, NSE_MASTER, EQUITY_MASTER_URL), run.symbol)
    if not rows:
        run.refuse(exchange, OnboardingReason.NOT_LISTED)
    if len(rows) > 1:
        run.set(exchange, conflict(_MANY_MASTER.format(count=len(rows), symbol=run.symbol)))
    run.name, run.isin = rows[0]
    if not run.isin.startswith(_IN):
        run.refuse(exchange, OnboardingReason.FOREIGN_ISIN)
    run.entity_id = _resolve(run, conn, None)
    listings = [
        run.anchor(exchange, pair, listing_url(path, run.symbol, period))
        for pair, (path, period) in (
            (NSE_RESULTS_LISTING, LEGACY_LISTING),
            (NSE_INTEGRATED_LISTING, INTEGRATED_LISTING),
        )
    ]
    master_retrieved = run.captures[0].response.retrieved_at
    window = filing_window(listing_rows(*listings), as_of_for(master_retrieved))
    if window.tied:
        run.set(exchange, conflict(_TIED))
    if not window.consolidated:
        standalone = OnboardingReason.STANDALONE_BASIS
        run.refuse(exchange, standalone if window.standalone else OnboardingReason.NO_IND_AS_FILING)
    if len(window.filings) < FILINGS_CHECKED:
        run.refuse(exchange, OnboardingReason.INSUFFICIENT_FILINGS)
    filings = window.filings[:FILINGS_CHECKED]
    bodies = [run.anchor(xbrl, NSE_XBRL_INSTANCE, row.xbrl_url or "") for row in filings]
    if not all(financial_rule(body) for body in bodies):
        run.refuse(xbrl, OnboardingReason.FINANCIAL_OR_UNKNOWN_SECTOR)
    try:
        instances = [parse_instance(body, mapping_set=mapping_set) for body in bodies]
    except UnsupportedSchemaError:
        run.refuse(xbrl, OnboardingReason.UNSUPPORTED_SCHEMA)
    run.filings = [
        (filing_identity(instance), row.broadcast.date() if row.broadcast else None)
        for instance, row in zip(instances, filings, strict=True)
    ]
    checked = [
        (filing, _expected(conn, run.entity_id, run.isin, run.symbol, filed))
        for filing, filed in run.filings
    ]
    verdicts = [
        verdict
        for instance, row, (filing, expected) in zip(instances, filings, checked, strict=True)
        for verdict in (
            instance_state(instance, row.period_end),
            xbrl_entity_state(filing, run.name, expected),
            ingest_identity_state(instance, filing, expected),
        )
    ] + [framework_state(instance, body) for instance, body in zip(instances, bodies, strict=True)]
    run.set(xbrl, deciding(verdicts))
    peer = run.anchor(exchange, BSE_PEER_SEARCH, _BSE_URL.format(isin=run.isin))
    verdict, run.scrip = exchange_state(peer, run.isin, checked)
    run.set(exchange, verdict)
    _resolve(run, conn, run.scrip)


def _vendors(run: _Run) -> None:
    """Screener, Tijori and Upstox, each against the verified anchors."""
    symbol, isin, scrip = run.symbol, run.isin or "", run.scrip or ""
    screener, tijori, upstox = (
        VerificationUnit.SCREENER,
        VerificationUnit.TIJORI,
        VerificationUnit.UPSTOX,
    )

    def screener_check() -> Verdict:
        search = run.get(screener, SCREENER_SEARCH, screener_search_url(symbol))
        found = screener_candidate(search, symbol)
        if not isinstance(found, int):
            return found
        page = run.get(screener, SCREENER_PAGE, _SCREENER_PAGE_URL.format(symbol=symbol))
        return screener_page_state(page, found, symbol, scrip)

    def tijori_check() -> Verdict:
        found = tijori_candidate(
            run.get(tijori, TIJORI_SEARCH, _TIJORI_SEARCH_URL.format(isin=isin))
        )
        if not isinstance(found, str):
            return found
        page = run.get(tijori, TIJORI_PAGE, _TIJORI_PAGE_URL.format(slug=found))
        return tijori_page_state(page, found, symbol)

    def upstox_check() -> Verdict:
        rows = run.get(upstox, UPSTOX_INSTRUMENTS, _INSTRUMENTS_URL)
        verdict = upstox_rows_state(rows, isin, symbol, scrip)
        if verdict != VERIFIED:
            return verdict
        url = _STATEMENT_URL.format(isin=isin)
        return upstox_statement_state(run.get(upstox, UPSTOX_STATEMENT, url), url)

    run.vendor(screener, screener_check)
    run.vendor(tijori, tijori_check)
    run.vendor(upstox, upstox_check)


def _resolve(run: _Run, conn: psycopg.Connection[Any], scrip: str | None) -> int | None:
    """D3.4 after the master (``scrip`` None) and again once the BSE scrip is verified."""
    owner, detail, _ = resolve_owner(conn, run.symbol, run.isin or "", scrip)
    if detail is not None:
        run.set(VerificationUnit.EXCHANGE, conflict(detail))
    return owner


def _locked_owner(conn: psycopg.Connection[Any], found: Discovery) -> int | None:
    """D3.4 inside the writing transaction: lock the verified values and every target holding
    them (as the identity writers do), re-resolve, and refuse a resolution that moved since
    discovery. Every filing is re-checked against the resolved owner's identity at its filed
    date; only then are a new issuer's ids created meanwhile by a concurrent onboarding reused."""
    isin, scrip = found.isin or "", found.scrip or ""
    values = [
        (IdentifierNamespace.ISIN, isin),
        (IdentifierNamespace.NSE_SYMBOL, found.symbol),
        (IdentifierNamespace.BSE_SCRIP, scrip),
    ]
    locked: set[IdentifierRef] = set()
    while True:
        lock_identifiers(conn, list(locked), values)
        owner, detail, held = resolve_owner(conn, found.symbol, isin, scrip)
        if held <= locked:
            break
        locked |= held
    if detail is not None or found.entity_id not in (None, owner):
        raise OnboardingAbortError(_MOVED)
    for filing, filed in found.filings if owner is not None else ():
        try:
            expected = _expected(conn, owner, isin, found.symbol, filed)
        except LookupError as error:
            raise OnboardingAbortError(_MOVED) from error
        verdicts = (
            xbrl_entity_state(filing, found.name or "", expected),
            filing_codes(filing, expected, scrip),
        )
        if any(verdict != VERIFIED for verdict in verdicts):
            raise OnboardingAbortError(_MOVED)
    return owner


def _expected(
    conn: psycopg.Connection[Any],
    entity_id: int | None,
    isin: str | None,
    symbol: str,
    filed: date | None,
) -> Expected:
    """The identity a filing must carry on its filed date (C8); a new issuer's from the master."""
    if entity_id is None or filed is None:
        return Expected(isin=isin or "", symbol=symbol, scrip=None)
    held = issuer_values(conn, entity_id, filed)
    return Expected(isin=held[0].value, symbol=held[1].value, scrip=held[2].value)


def store_captures(
    store: SnapshotStore, repository: EvidenceRepository, captures: Sequence[Capture]
) -> list[tuple[VerificationUnit, CaptureReference]]:
    """Publish and register each body in its own registration (with its URL): ``(unit, ref)``."""
    registered = []
    for item in captures:
        with capture_registration(repository._pool) as registration:
            registered.append(register_capture(store, registration, item))
    return registered


def register_capture(
    store: SnapshotStore, registration: Registration, item: Capture
) -> tuple[VerificationUnit, CaptureReference]:
    """Publish one body and register it inside ``registration``'s transaction. Upstox requests
    keep their route and query; others are keyed by their key digest."""
    body = item.response.body or b""
    request, sha = item.request, hashlib.sha256(body).hexdigest()
    source, surface = request.source_id, request.surface
    authority = surface_authority(source, surface)
    key = hashlib.sha256(request.key.encode()).hexdigest()
    identity = RequestIdentity(source_id=source, surface=surface, request_key=key)
    if (source, surface) in UPSTOX_ROUTED:
        identity = upstox_request_identity(surface, UPSTOX_ROUTE, request.url)
    blob = BlobRef(source_id=source, content_sha256=sha, byte_count=len(body))
    ok = OutcomeRecord(code=OutcomeCode.OK, native_kind=_NATIVE_KIND, native_value=OK)
    record = store.put_capture(
        CaptureRecord.make(
            request=identity,
            retrieved_at=item.response.retrieved_at,
            http_status=200,
            media_type=_MEDIA_TYPE,
            content_encoding=None,
            body=blob,
            outcome=ok,
            rights=SnapshotRights(authority_refs=(authority.retention_authority,)),
            schema_version=CAPTURE_SCHEMA_VERSION,
            body_completeness=BodyCompleteness.COMPLETE,
        ),
        body,
    )
    now = registration.store_clock()
    ref = registration.insert(
        CaptureReference(
            capture_ref_id=None,
            source_id=source,
            surface=surface,
            request_key=record.request.request_key,
            capture_id=record.capture_id,
            blob_sha256=sha,
            record_sha256=record.record_sha256,
            registered_at=now,
            first_seen_at=now,
        ),
        url=request.url,
    )
    return request.unit, ref


def record(
    conn: psycopg.Connection[Any],
    found: Discovery,
    captures: Sequence[tuple[VerificationUnit, CaptureReference]],
) -> Recorded:
    """Write the record, its unit states and inputs, and a new issuer's identity, atomically;
    an admitted issuer's identity is re-resolved under lock first."""
    result, reason = outcome(found.states)
    admitted = result in (OnboardingOutcome.ONBOARDED, OnboardingOutcome.PARTIAL)
    with conn.transaction():
        entity_id = _locked_owner(conn, found) if admitted else None
        inputs: dict[VerificationUnit, int] = {}
        for unit in VerificationUnit:
            ids = sorted(ref.capture_ref_id or 0 for owner, ref in captures if owner is unit)
            if not ids:
                continue
            content = json.dumps([found.symbol, unit.value, ids]).encode()
            label = _INPUT_LABEL.format(symbol=found.symbol, unit=unit.value)
            inputs[unit] = _input(conn, label, hashlib.sha256(content).hexdigest())
            for ref in ids:
                conn.execute(_LINK_SQL, (inputs[unit], ref))
        if admitted and entity_id is None:
            entity_id = _new_issuer(conn, found, inputs[VerificationUnit.EXCHANGE])
        record_id = _one(
            conn,
            _RECORD_SQL,
            (
                found.symbol,
                IdentifierNamespace.NSE_SYMBOL.value,
                result.value,
                _HIGH if result is OnboardingOutcome.IDENTITY_CONFLICT else None,
                reason,
                entity_id if admitted else None,
                inputs.get(VerificationUnit.EXCHANGE),
            ),
        )
        for unit, (state, why) in found.states.items():
            conn.execute(
                _VERIFICATION_SQL, (record_id, unit.value, state.value, why, inputs.get(unit))
            )
    return Recorded(
        outcome=result, reason=reason, entity_id=entity_id if admitted else None, inputs=inputs
    )


def _new_issuer(conn: psycopg.Connection[Any], found: Discovery, input_id: int) -> int:
    """Entity, security and listings for a verified new issuer, under the first free key."""
    conn.execute(_LOCK_SQL)
    key, suffix = found.symbol, 1
    while conn.execute(_KEY_TAKEN_SQL, (key,)).fetchall():
        suffix += 1
        key = f"{found.symbol}-{suffix}"
    entity_id = _one(conn, _ENTITY_SQL, (key, MARKET_IN, found.name, input_id))
    security_id = _one(conn, _SECURITY_SQL, (entity_id, found.isin, SHARE_CLASS_EQUITY, input_id))
    for venue, code in ((ListingVenue.NSE, found.symbol), (ListingVenue.BSE, found.scrip)):
        conn.execute(_LISTING_SQL, (security_id, venue.value, code, input_id))
    return entity_id


def _input(conn: psycopg.Connection[Any], label: str, sha: str) -> int:
    """The DISCOVERY input for this content, created on first use."""
    kind = EvidenceInputKind.DISCOVERY.value
    conn.execute(_INPUT_SQL, (kind, label, sha))
    return _one(conn, _SELECT_INPUT_SQL, (kind, sha))


def _one(conn: psycopg.Connection[Any], query: LiteralString, params: tuple[object, ...]) -> int:
    """The single id a statement returns."""
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return int(row[0])


_INPUT_SQL: LiteralString = (
    "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) VALUES (%s, %s, %s) "
    "ON CONFLICT (kind, content_sha256) DO NOTHING"
)
_SELECT_INPUT_SQL: LiteralString = (
    "SELECT id FROM eqos.evidence_inputs WHERE kind = %s AND content_sha256 = %s"
)
_LINK_SQL: LiteralString = (
    "INSERT INTO eqos.evidence_input_captures (evidence_input_id, capture_ref_id) "
    "VALUES (%s, %s) ON CONFLICT DO NOTHING"
)
_LOCK_SQL: LiteralString = "SELECT pg_advisory_xact_lock(hashtext('eqos.entity_key'))"
_KEY_TAKEN_SQL: LiteralString = "SELECT 1 FROM eqos.reporting_entities WHERE entity_key = %s"
_ENTITY_SQL: LiteralString = (
    "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) RETURNING id"
)
_SECURITY_SQL: LiteralString = (
    "INSERT INTO eqos.securities (entity_id, isin, share_class, evidence_input_id) "
    "VALUES (%s, %s, %s, %s) RETURNING id"
)
_LISTING_SQL: LiteralString = (
    "INSERT INTO eqos.listings (security_id, venue, symbol, evidence_input_id) "
    "VALUES (%s, %s, %s, %s)"
)
_RECORD_SQL: LiteralString = (
    "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, outcome, severity, "
    "reason, entity_id, evidence_input_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
)
_VERIFICATION_SQL: LiteralString = (
    "INSERT INTO eqos.namespace_verifications (onboarding_record_id, unit, state, reason, "
    "evidence_input_id) VALUES (%s, %s, %s, %s, %s)"
)
