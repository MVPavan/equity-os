"""Raw-first registration, parse dispatch and replay of registered vendor responses."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from lxml.etree import ParserError  # type: ignore[import-untyped]
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.screener_page_cli import basis_topology
from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.snapshot import BodyCompleteness, CaptureRecord
from fundamentals.entity.identity_layers import latest_slice, resolve_owner
from fundamentals.entity.verification import tijori_candidate, tijori_page_state
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest.screener_session_models import Basis, ScreenerSessionError
from fundamentals.ingest.screener_session_page import assert_logged_in, read_identity
from fundamentals.ingest.tijori_capture import classify_financials_body
from fundamentals.ingest.vendor_surface_fetch import (
    Site,
    SiteBusy,
    SiteStopped,
    VendorFetcher,
    request_key,
)
from fundamentals.ingest.vendor_surface_parse import (
    PARSERS,
    Body,
    CompanyIds,
    ParseContext,
    ParserEntry,
    company_page,
    kept_section,
    parser_sha256,
)
from fundamentals.ingest.vendor_surface_readers import sanitized_reader_logs
from fundamentals.ingest.vendor_surface_specs import (
    SITE_NAME,
    Cadence,
    ParseGroup,
    Scope,
    SurfaceSpec,
)
from fundamentals.ingest.vendor_surface_topology import bind_topology
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import (
    USABLE,
    Outcome,
    OutcomeStatus,
    VendorValue,
    VendorValuesStore,
    register,
)

WATCHLIST = Path("config/watchlist.yaml")
TOPOLOGY_UNKNOWN = "topology unknown"
IDENTITY_PAGES = ("company-page", "company-financials")
BASIS_SECTIONS = frozenset(
    "section-quarters section-profit-loss section-balance-sheet "
    "section-cash-flow section-ratios company-consolidated-empty-shell".split()
)


class Request(BaseModel):
    """One expected request, carrying only verified context."""

    model_config = ConfigDict(frozen=True)
    spec: SurfaceSpec
    url: str
    ids: CompanyIds | None
    basis: Basis | None = None
    parent: Mapping[str, Any] | None = None
    due_since: datetime | None

    @property
    def report_key(self) -> str:
        """Identify the request without copied URL path or query text."""
        return f"{SITE_NAME[self.spec.site]}:{self.spec.id}:{request_key(self.url)}"

    def context(self, record: CaptureRecord, body_sha256: str) -> ParseContext:
        """The same verified request context for dispatch, expansion and retained replay."""
        return ParseContext(
            ids=self.ids,
            basis=self.basis,
            url=self.url,
            retrieved_at=record.retrieved_at,
            body_sha256=body_sha256,
            capture_id=record.capture_id,
            parent=self.parent,
        )


class RunReport(BaseModel):
    """All expected work, including refusals and missing usable outcomes."""

    model_config = ConfigDict(frozen=True)
    expected: int
    completed: int
    refused: tuple[str, ...]
    incomplete: tuple[str, ...]
    stopped_sites: tuple[Site, ...]


def company_ids(stock: StockConfig) -> CompanyIds:
    """Copy configured bindings; unverified fields never become response expectations."""
    ids = stock.identifiers
    return CompanyIds(
        nse_symbol=ids.nse_symbol,
        isin=ids.isin or "",
        tijori_slug=None if ids.unverified_tijori_fields() else ids.tijori_slug,
        tijori_company_id=None if ids.unverified_tijori_fields() else ids.tijori_company_id,
        screener_company_id=None
        if "screener_company_id" in ids.needs_verification
        else ids.screener_company_id,
        topology=None
        if any(field.startswith("screener_warehouse_id_") for field in ids.needs_verification)
        else basis_topology(stock),
    )


def registered_ids(pool: ConnectionPool, store: SnapshotStore, symbol: str) -> CompanyIds:
    """Resolve registry anchors and vendor ids proved by retained onboarding evidence."""
    with pool.connection() as conn:
        held = [
            r for r in latest_slice(conn) if r.value == symbol and r.namespace.value == "NSE_SYMBOL"
        ]
        if len(held) != 1:
            rows = conn.execute(
                (
                    "SELECT isin FROM eqos.registry_view WHERE segment='NSE_EQ' AND tradi"
                    "ng_symbol=%s AND status='LISTED'"
                ),
                (symbol,),
            ).fetchall()
            if len(rows) != 1:
                raise ValueError("verified registry identity unavailable")
            isin = rows[0][0]
            entity_id, _, _ = resolve_owner(conn, symbol, isin, None)
        else:
            entity_id = held[0].entity_id
            isin = next(
                r.value
                for r in latest_slice(conn)
                if r.security_id == held[0].security_id and r.namespace.value == "ISIN"
            )
        with conn.cursor(row_factory=dict_row) as cursor:
            proofs = cursor.execute(
                (
                    "SELECT c.*, a.url, v.unit FROM eqos.onboarding_records o JOIN eqos.n"
                    "amespace_verifications v ON v.onboarding_record_id=o.id JOIN eqos.ev"
                    "idence_input_captures e ON e.evidence_input_id=v.evidence_input_id J"
                    "OIN eqos.capture_refs c ON c.id=e.capture_ref_id JOIN eqos.capture_a"
                    "ddresses a ON a.capture_ref_id=c.id WHERE o.entity_id=%s AND v.state"
                    "='VERIFIED' AND v.unit IN ('SCREENER','TIJORI') AND eqos.capture_sta"
                    "te(c.id) IN ('RETAINED','RESTORED') ORDER BY c.id"
                ),
                (entity_id,),
            ).fetchall()
        with conn.cursor(row_factory=dict_row) as cursor:
            proofs += cursor.execute(
                (
                    "SELECT c.*, a.url, CASE c.source_id WHEN 'screener-subscriber' THEN "
                    "'SCREENER' ELSE 'TIJORI' END AS unit FROM eqos.capture_refs c JOIN e"
                    "qos.capture_addresses a ON a.capture_ref_id=c.id WHERE eqos.capture_"
                    "state(c.id) IN ('RETAINED','RESTORED') AND EXISTS (SELECT 1 FROM eqo"
                    "s.vendor_outcomes o WHERE o.capture_ref_id=c.id AND o.symbol=%s AND "
                    "o.surface IN ('company-page','company-financials') AND o.status IN ("
                    "'KEPT','OK','PARTIAL')) ORDER BY c.id"
                ),
                (symbol,),
            ).fetchall()
    ids = CompanyIds(
        nse_symbol=symbol,
        isin=isin,
        screener_company_id=None,
        tijori_slug=None,
        tijori_company_id=None,
        topology=None,
    )
    pages: dict[Basis, CaptureReference] = {}
    for proof in proofs:
        record = store.get_capture(
            proof["source_id"], proof["surface"], proof["request_key"], proof["capture_id"]
        )
        if (
            record.http_status != 200
            or record.effective_body_completeness is not BodyCompleteness.COMPLETE
        ):
            continue
        body = Body(raw=store.read_body(record))
        if proof["unit"] == "SCREENER" and "/company/" in proof["url"]:
            assert_logged_in(body.tree())
            ids = ids.model_copy(update={"screener_company_id": read_identity(body.tree())[0]})
            pages[Basis.CONSOLIDATED if "/consolidated/" in proof["url"] else Basis.STANDALONE] = (
                capture_of(proof)
            )
        elif (
            proof["unit"] == "TIJORI"
            and "/financials/" in proof["url"]
            and classify_financials_body(
                body.raw, expected_symbol=symbol, expected_company_id=None
            ).code
            is OutcomeCode.OK
        ):
            details = json.loads(body.tree().xpath('//script[@id="company_details"]/text()')[0])
            ids = ids.model_copy(
                update={
                    "tijori_slug": urlsplit(proof["url"]).path.split("/")[2],
                    "tijori_company_id": details["company_id"],
                }
            )
    if entity_id is not None:
        ids = ids.model_copy(update={"topology": bind_topology(pool, store, ids, entity_id, pages)})
    return ids


def parse_and_record(
    store: SnapshotStore,
    values: VendorValuesStore,
    ref: CaptureReference,
    record: CaptureRecord,
    request: Request,
    body: Body | None = None,
    refusal: str | None = None,
) -> tuple[OutcomeStatus, ...]:
    """Read registered bytes and atomically store each logical surface's parse result."""
    context = request.context(record, ref.blob_sha256)
    states = []
    basis_refusal = None
    for surface in (request.spec.id, *request.spec.sections):
        entry = parser_entry(request.spec, surface)
        version, digest = entry.version, parser_sha256(entry.parse)
        parsed: tuple[VendorValue, ...] = ()
        status, detail = OutcomeStatus.UNUSABLE, None
        try:
            if refusal is not None or basis_refusal is not None:
                version = f"{SITE_NAME[request.spec.site]}:gate.identity.v1"
                digest = parser_sha256(identity_gate)
                detail = refusal or basis_refusal
            elif record.http_status != 200:
                detail = record.outcome.code.value
            elif record.effective_body_completeness is not BodyCompleteness.COMPLETE:
                detail = record.effective_body_completeness.value
            else:
                if body is None:
                    body = Body(raw=store.read_body(record))
                # A page proves login and identity even when its topology is unknown.
                if surface == "company-page":
                    parsed = entry.parse(body, context)
                if (
                    (surface == request.spec.id or surface in BASIS_SECTIONS)
                    and request.basis is not None
                    and (request.ids is None or request.ids.topology is None)
                ):
                    version = f"{SITE_NAME[request.spec.site]}:gate.topology.v1"
                    digest = parser_sha256(topology_gate)
                    detail = TOPOLOGY_UNKNOWN
                elif (
                    request.spec.group is ParseGroup.NONE and surface == request.spec.id
                ) or entry.parse is kept_section:
                    status = OutcomeStatus.KEPT
                else:
                    parsed = entry.parse(body, context)
                    status = (
                        OutcomeStatus.PARTIAL
                        if any(v.expected_numeric and v.value is None for v in parsed)
                        else (OutcomeStatus.OK if parsed else OutcomeStatus.EMPTY)
                    )
        except ScreenerSessionError as error:
            detail = type(error).__name__
            if surface == "company-page":
                basis_refusal = detail
        except Exception as error:
            status, detail = OutcomeStatus.FAILED, type(error).__name__
        assert ref.capture_ref_id is not None
        if not values.has_outcome(ref.capture_ref_id, surface, version):
            values.record(
                ref,
                Outcome(
                    surface=surface,
                    parser_version=version,
                    parser_sha256=digest,
                    status=status,
                    symbol=request.ids.nse_symbol if request.ids else None,
                    detail=detail,
                    values=parsed,
                ),
                row_count=len(parsed),
            )
        states.append(status)
    return tuple(states)


def topology_gate(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """The versioned refusal when the request has no bound basis topology."""
    return ()


def identity_gate(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """The versioned refusal when retained chart bytes have no matching company binding."""
    return ()


def identity_refusal(request: Request, body: Body) -> str | None:
    """Why a retained identity page does not prove its request's company, or None."""
    assert request.ids is not None
    try:
        if request.spec.id == "company-page":
            assert_logged_in(body.tree())
            same = read_identity(body.tree())[0] == request.ids.screener_company_id
            return None if same else "company identity mismatch"
        gate = classify_financials_body(
            body.raw,
            expected_symbol=request.ids.nse_symbol,
            expected_company_id=request.ids.tijori_company_id,
        )
        return None if gate.code is OutcomeCode.OK else gate.native_value
    except (ScreenerSessionError, ParserError, UnicodeDecodeError) as error:
        return type(error).__name__


def covered_peers(pool: ConnectionPool, store: SnapshotStore, ids: CompanyIds) -> tuple[int, ...]:
    """Covered NSE peers, using registry evidence with configuration overrides."""
    from fundamentals.ingest.vendor_surface_due import covered_universe

    return tuple(
        peer.screener_company_id
        for peer in covered_universe(pool, store)
        if peer.nse_symbol != ids.nse_symbol and peer.screener_company_id is not None
    )


def retained_graph(
    store: SnapshotStore,
    pool: ConnectionPool,
    specs: tuple[SurfaceSpec, ...],
    ids: CompanyIds,
    retained: list[dict[str, Any]],
) -> dict[str, Request]:
    """The company requests its retained captures admit, gated as live capture gates them.

    Identity pages must prove the company (and Screener pages their basis); fixed requests need
    their site and basis proven; children need an admitted, retained parent advertising them.
    """
    from fundamentals.ingest.vendor_surface_expand import advertised, expansion_name

    captures: dict[str, list[tuple[CaptureRecord, str]]] = {}
    for row in retained:
        if row["symbol"] != ids.nse_symbol:
            continue
        record = store.get_capture(
            row["source_id"], row["surface"], row["request_key"], row["capture_id"]
        )
        if (
            record.http_status == 200
            and record.effective_body_completeness is BodyCompleteness.COMPLETE
        ):
            captures.setdefault(row["url"], []).append((record, row["blob_sha256"]))
    fixed = company_requests(specs, ids)
    admitted: dict[str, Request] = {}
    proven: set[Site | Basis] = set()
    verified_captures: set[str] = set()
    for request in (r for r in fixed if r.spec.id in IDENTITY_PAGES):
        for record, sha in captures.get(request.url, []):
            body = Body(raw=store.read_body(record))
            if identity_refusal(request, body) is not None:
                continue
            if request.basis is not None:
                try:
                    company_page(body, request.context(record, sha))
                except ScreenerSessionError:
                    continue
                proven.add(request.basis)
            proven.add(request.spec.site)
            verified_captures.add(record.capture_id)
            admitted[request.url] = request
    admitted.update(
        (r.url, r)
        for r in fixed
        if r.spec.site in proven
        and (r.basis is None or r.basis in proven)
        and r.spec.id not in IDENTITY_PAGES
    )
    queue, peers = list(admitted.values()), covered_peers(pool, store, ids)
    while queue:
        request = queue.pop()
        if request.spec.id != "company-page" and not any(
            expansion_name(spec, request.spec.id) for spec in specs
        ):
            continue
        for record, sha in captures.get(request.url, []):
            if request.spec.id in IDENTITY_PAGES and record.capture_id not in verified_captures:
                continue
            body = Body(raw=store.read_body(record))
            children, _ = advertised(request, body, request.context(record, sha), specs, peers)
            fresh = [child for child in children if child.url not in admitted]
            admitted.update((child.url, child) for child in fresh)
            queue.extend(fresh)
    return admitted


def capture(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    request: Request,
    *,
    parse: bool = True,
) -> tuple[CaptureReference, Body | None]:
    """Register before parsing, including the response that durably stops a site."""
    try:
        fetched = fetcher.get(request.spec.site, request.spec.id, request.url, xhr=request.spec.xhr)
    except SiteStopped as error:
        if error.fetched is not None:
            try:
                ref = register(pool, error.fetched)
                parse_and_record(store, values, ref, error.fetched.record, request)
            finally:
                fetcher.stop_dir.mkdir(parents=True, exist_ok=True)
                (fetcher.stop_dir / f"STOP-{error.site}").write_text(
                    f"{error.fetched.record.capture_id} {error.fetched.record.http_status}\n"
                )
        raise
    ref = register(pool, fetched)
    body = (
        Body(raw=store.read_body(fetched.record))
        if fetched.record.http_status == 200
        and fetched.record.effective_body_completeness is BodyCompleteness.COMPLETE
        else None
    )
    if parse:
        parse_and_record(store, values, ref, fetched.record, request, body)
    return ref, body


def reparse(
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    spec: SurfaceSpec,
    specs: tuple[SurfaceSpec, ...],
) -> int:
    """Recover logical parents and expansion inputs entirely from registered evidence."""
    owner = next((s for s in specs if s.site == spec.site and spec.id in s.sections), spec)
    entry = parser_entry(spec, spec.id)
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        retained = cursor.execute(
            "SELECT c.*, a.url, (SELECT o.symbol FROM eqos.vendor_outcomes o "
            "WHERE o.capture_ref_id=c.id AND o.symbol IS NOT NULL ORDER BY o.id LIMIT 1) AS symbol "
            "FROM eqos.capture_refs c JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id "
            "WHERE c.source_id=%s AND eqos.capture_state(c.id) IN ('RETAINED','RESTORED') "
            "ORDER BY c.id",
            (spec.site,),
        ).fetchall()
    rows = [row for row in retained if row["surface"] == "vs." + owner.id]
    bindings = [company_ids(stock) for stock in load_watchlist_config(WATCHLIST).stocks]
    count = 0
    for row in rows:
        ref = capture_of(row)
        assert ref.capture_ref_id is not None
        if values.has_outcome(ref.capture_ref_id, spec.id, entry.version):
            continue
        count += 1
        ids = next(
            (
                binding
                for binding in bindings
                if binding.nse_symbol == row["symbol"]
                or f"/company/{binding.nse_symbol}/" in row["url"]
                or spec.id == "chart-api"
                and row["symbol"] is None
                and urlsplit(row["url"]).path
                == f"/api/company/{binding.screener_company_id}/chart/"
            ),
            None,
        )
        if ids is None and row["symbol"] is not None:
            try:
                ids = registered_ids(pool, store, row["symbol"])
            except ValueError:
                pass
        if ids is not None and ids.topology is None:
            with pool.connection() as conn:
                entity_id, _, _ = resolve_owner(conn, ids.nse_symbol, ids.isin, None)
            if entity_id is not None:
                ids = ids.model_copy(
                    update={"topology": bind_topology(pool, store, ids, entity_id, {})}
                )
        graph = (
            retained_graph(
                store,
                pool,
                specs,
                ids,
                sorted(
                    (r for r in retained if r["capture_id"][:23] <= row["capture_id"][:23]),
                    key=lambda r: r["capture_id"],
                    reverse=True,
                ),
            )
            if ids
            else {}
        )
        request = graph.get(row["url"])
        refusal = None
        if spec.scope is Scope.COMPANY and request is None:
            refusal = "verified company binding unavailable"
        if request is None:
            request = Request(spec=owner, url=row["url"], ids=ids, due_since=None)
        if owner.id != spec.id:
            request = request.model_copy(
                update={"spec": owner.model_copy(update={"sections": (spec.id,)})}
            )
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parse_and_record(store, values, ref, record, request, refusal=refusal)
    return count


def unavailable(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Keep a missing reader explicit until its owning task registers it."""
    raise ValueError("parser unavailable")


def parser_entry(spec: SurfaceSpec, surface: str) -> ParserEntry:
    """Use installed readers; only declared G4 surfaces and discovery may be kept empty."""
    return PARSERS.get((spec.site, surface)) or ParserEntry(
        version=f"{SITE_NAME[spec.site]}:{surface}.unavailable.v1",
        parse=topology_gate
        if surface == spec.id and spec.group in (ParseGroup.NONE, ParseGroup.DISCOVERY)
        else unavailable,
    )


def company_requests(specs: tuple[SurfaceSpec, ...], ids: CompanyIds) -> tuple[Request, ...]:
    """Build parents before fixed endpoints; parameterized children await retained parents."""
    from fundamentals.ingest.vendor_surface_expand import child

    result: list[Request] = []
    context = ParseContext(
        ids=ids, basis=None, url="", retrieved_at=datetime.min, body_sha256="", capture_id=""
    )
    for spec in sorted(
        specs, key=lambda spec: spec.id not in ("company-page", "company-financials")
    ):
        if (
            spec.scope is not Scope.COMPANY
            or spec.expand
            or spec.id == "chart-api"
            or "#" in spec.path
        ):
            continue
        if any(
            token in spec.path
            for token in ("{warehouse_id}", "{month}", "{chart_company_id}", "{field}")
        ):
            continue
        if spec.site is Site.TIJORI and (
            ids.tijori_slug is None
            or (
                ids.tijori_company_id is None
                and any(token in spec.path for token in ("{company_id}", "{id}"))
            )
        ):
            continue
        bases = (
            tuple(Basis)
            if spec.site is Site.SCREENER
            and ("[consolidated/]" in spec.path or "consolidated=" in spec.path)
            else (None,)
        )
        alternative = re.search(r"\{([^{}]*\|[^{}]*)\}", spec.path)
        variants = (
            [part for part in alternative[1].split("|") if part != "..."] if alternative else [""]
        )
        for basis in bases:
            for variant in variants:
                parameters: dict[str, Any] = {alternative[1]: variant} if alternative else {}
                result.append(
                    child(
                        spec,
                        context.model_copy(update={"basis": basis}),
                        **parameters,
                    )
                )
    return tuple(result)


def resolve_tijori_slug(
    fetcher: VendorFetcher,
    ids: CompanyIds,
    *,
    pool: ConnectionPool,
    values: VendorValuesStore,
    cached: dict[str, tuple[CaptureReference, Body | None, Request]],
) -> tuple[str | None, int]:
    """Register ISIN search and candidate page before existing identity verification."""
    search_spec = SurfaceSpec(
        site=Site.TIJORI,
        id="company-search-api",
        scope=Scope.MARKET,
        path="/api/v1/ind/company_search/?q={q}",
        group=ParseGroup.DISCOVERY,
        cadence=Cadence.DAILY,
    )
    _, search = capture(
        fetcher,
        fetcher.store,
        pool,
        values,
        Request(
            spec=search_spec,
            url="https://www.tijorifinance.com/api/v1/ind/company_search/?q="
            + quote(ids.isin, safe=""),
            ids=ids,
            due_since=None,
        ),
    )
    slug = tijori_candidate(search.raw) if search is not None else None
    if not isinstance(slug, str):
        return None, 0
    spec = search_spec.model_copy(update={"id": "company-financials"})
    request = Request(
        spec=spec,
        url=f"https://www.tijorifinance.com/company/{quote(slug, safe='')}/financials/",
        ids=ids,
        due_since=None,
    )
    ref, page = capture(fetcher, fetcher.store, pool, values, request, parse=False)
    with sanitized_reader_logs("tijori", spec.id):
        state = (
            tijori_page_state(page.raw, slug, ids.nse_symbol)[0].value if page is not None else ""
        )
    values.record(
        ref,
        Outcome(
            surface=spec.id,
            parser_version="tijori:company-financials.slug.v1",
            parser_sha256=parser_sha256(identity_gate),
            status=OutcomeStatus.KEPT if state == "VERIFIED" else OutcomeStatus.UNUSABLE,
            symbol=ids.nse_symbol,
            detail="slug verification",
        ),
        row_count=0,
    )
    if state == "VERIFIED":
        cached[request.url] = ref, page, request
        return slug, 2
    return None, 1


def capture_company(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    specs: tuple[SurfaceSpec, ...],
    ids: CompanyIds,
    requests: tuple[Request, ...] | None = None,
) -> RunReport:
    """Capture company obligations, or a scheduled subset, through the site gates.

    A scheduled subset captures only its requests (plus those a newly verified slug or company id
    makes possible); advertised children wait for the scheduler's next round.
    """
    from fundamentals.ingest.vendor_surface_expand import advertised

    incomplete: list[str] = []
    refused: list[str] = []
    stopped: list[Site] = []
    blocked: set[Site] = set()
    pages: dict[Basis, CaptureReference] = {}
    cached: dict[str, tuple[CaptureReference, Body | None, Request]] = {}
    deferred: list[Request] = []
    basis_refusals: dict[Basis, str] = {}
    with pool.connection() as conn:
        entity_id, _, _ = resolve_owner(conn, ids.nse_symbol, ids.isin, None)
    peers = covered_peers(pool, store, ids)
    if not peers and any(s.id == "company-compare" for s in specs):
        incomplete.append("screener:company-compare: no other covered stocks")
    known = {r.url for r in company_requests(specs, ids)} if requests is not None else set()
    discovery_expected = discovery_completed = 0
    if any(s.site is Site.TIJORI for s in specs) and ids.tijori_slug is None:
        before = fetcher.counts[Site.TIJORI]
        try:
            slug, discovery_completed = resolve_tijori_slug(
                fetcher, ids, pool=pool, values=values, cached=cached
            )
        except SiteStopped as error:
            stopped.append(error.site)
            blocked.add(error.site)
            slug = None
        except (SiteBusy, ValueError):
            slug = None
        discovery_expected = fetcher.counts[Site.TIJORI] - before
        if slug is None:
            discovery_completed = max(discovery_completed, discovery_expected - 1)
        ids = ids.model_copy(update={"tijori_slug": slug})
        if slug is None:
            incomplete.append("tijori:missing slug")
    pending = sorted(
        (*(requests or ()), *(r for r in company_requests(specs, ids) if r.url not in known)),
        key=lambda r: r.spec.id not in ("company-page", "company-financials"),
    )
    expected = len(pending) + len(incomplete) + discovery_expected - len(cached)
    completed = discovery_completed - len(cached)
    incomplete.extend(
        ["tijori:slug resolution request"] * (discovery_expected - discovery_completed)
    )
    seen: set[str] = set()
    while pending:
        request = pending.pop(0).model_copy(update={"ids": ids})
        if request.url in seen:
            expected -= 1
            continue
        if request.spec.site in blocked:
            seen.add(request.url)
            if request.url not in cached:
                refused.append(request.report_key)
            continue
        if request.spec.id == "company-timeline-api":
            from fundamentals.ingest.vendor_surface_market import capture_market

            report = capture_market(fetcher, store, pool, values, specs, requests=(request,))
            seen.add(request.url)
            expected += report.expected - 1
            completed += report.completed
            incomplete.extend(report.incomplete)
            refused.extend(report.refused)
            stopped.extend(report.stopped_sites)
            blocked.update(report.stopped_sites)
            continue
        try:
            ref, body = (
                cached.pop(request.url)[:2]
                if request.url in cached
                else capture(fetcher, store, pool, values, request, parse=False)
            )
        except SiteStopped as error:
            seen.add(request.url)
            stopped.append(error.site)
            blocked.add(error.site)
            incomplete.append(request.report_key)
            continue
        except (SiteBusy, ValueError):
            # An identity page that was never read proves nothing: its site's dependents wait.
            if request.spec.id in ("company-page", "company-financials"):
                blocked.add(request.spec.site)
            (incomplete if fetcher.remaining(request.spec.site) == 0 else refused).append(
                request.report_key
            )
            continue
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        refusal = basis_refusals.get(request.basis) if request.basis else None
        if body is None and request.spec.id in IDENTITY_PAGES:
            refusal = "company identity acquisition failed"
        elif body is not None and request.spec.id in IDENTITY_PAGES:
            refusal = identity_refusal(request, body) or refusal
        if body is not None and request.spec.id == "company-page":
            if (
                refusal is None
                and request.basis is Basis.CONSOLIDATED
                and read_identity(body.tree())[1] is None
            ):
                request = request.model_copy(
                    update={
                        "spec": request.spec.model_copy(
                            update={
                                "sections": (
                                    *request.spec.sections,
                                    "company-consolidated-empty-shell",
                                )
                            }
                        )
                    }
                )
            if refusal is None and request.basis is not None:
                pages[request.basis] = ref
                if any(r.spec.id == "company-page" for r in pending) and not deferred:
                    cached[request.url] = (ref, body, request)
                    deferred.append(request)
                    continue
        if (
            body is not None
            and request.spec.id == "company-financials"
            and refusal is None
            and ids.tijori_company_id is None
        ):
            details = json.loads(body.tree().xpath('//script[@id="company_details"]/text()')[0])
            locked = {r.url for r in company_requests(specs, ids)}
            ids = ids.model_copy(update={"tijori_company_id": details["company_id"]})
            discovered = [r for r in company_requests(specs, ids) if r.url not in locked]
            pending.extend(discovered)
            expected += len(discovered)
        if (
            request.spec.id == "company-page"
            and deferred
            and not any(r.spec.id == "company-page" for r in pending)
        ):
            if entity_id is not None and refusal is None:
                ids = ids.model_copy(
                    update={"topology": bind_topology(pool, store, ids, entity_id, pages)}
                )
            pending[0:0] = deferred
            deferred.clear()
        if refusal is not None and request.basis not in basis_refusals:
            blocked.add(request.spec.site)
        seen.add(request.url)
        states = parse_and_record(
            store, values, ref, record, request.model_copy(update={"ids": ids}), body, refusal
        )
        usable = all(state in USABLE for state in states)
        if (
            request.spec.id == "company-page"
            and not usable
            and ids.topology is not None
            and request.basis is not None
        ):
            basis_refusals[request.basis] = "page basis refused"
        completed += int(usable)
        if not usable:
            incomplete.append(
                request.report_key
                + (": topology unknown" if request.basis and ids.topology is None else "")
            )
        if body is None or refusal is not None:
            continue
        request = request.model_copy(update={"ids": ids})
        children, gaps = advertised(
            request, body, request.context(record, ref.blob_sha256), specs, peers
        )
        incomplete.extend(gaps)
        expected += len(gaps)
        if requests is None:
            expected += len(children)
            pending.extend(children)
    for ref, body, request in cached.values():
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parse_and_record(store, values, ref, record, request, body, "company identity unverified")
        incomplete.append(request.report_key)
    return RunReport(
        expected=expected,
        completed=completed,
        refused=tuple(refused),
        incomplete=tuple(incomplete),
        stopped_sites=tuple(dict.fromkeys(stopped)),
    )
