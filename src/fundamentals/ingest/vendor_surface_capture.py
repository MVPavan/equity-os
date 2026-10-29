"""Raw-first registration, parse dispatch and replay of registered vendor responses."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

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
    kept_section,
    parser_sha256,
)
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
    context = ParseContext(
        ids=request.ids,
        basis=request.basis,
        url=request.url,
        retrieved_at=record.retrieved_at,
        body_sha256=ref.blob_sha256,
        capture_id=record.capture_id,
        parent=request.parent,
    )
    states = []
    for surface in (request.spec.id, *request.spec.sections):
        entry = parser_entry(request.spec, surface)
        version, digest = entry.version, parser_sha256(entry.parse)
        parsed: tuple[VendorValue, ...] = ()
        status, detail = OutcomeStatus.UNUSABLE, None
        try:
            if refusal is not None:
                version = f"{SITE_NAME[request.spec.site]}:gate.identity.v1"
                digest = parser_sha256(identity_gate)
                detail = refusal
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
    store: SnapshotStore, pool: ConnectionPool, values: VendorValuesStore, spec: SurfaceSpec
) -> int:
    """Append outcomes under the current version using registered addresses and retained bytes."""
    entry = parser_entry(spec, spec.id)
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """SELECT c.*, a.url, (SELECT o.symbol FROM eqos.vendor_outcomes o
                WHERE o.capture_ref_id=c.id AND o.symbol IS NOT NULL ORDER BY o.id LIMIT 1)
                AS symbol FROM eqos.capture_refs c
            JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id
            WHERE c.source_id=%s AND c.surface=%s
            AND eqos.capture_state(c.id) IN ('RETAINED','RESTORED')
            AND NOT EXISTS (SELECT 1 FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id
                AND o.surface=%s AND o.parser_version=%s) ORDER BY c.id""",
            (spec.site, "vs." + spec.id, spec.id, entry.version),
        ).fetchall()
    bindings = [company_ids(stock) for stock in load_watchlist_config(WATCHLIST).stocks]
    for row in rows:
        ref = capture_of(row)
        ids = next(
            (
                binding
                for binding in bindings
                if binding.nse_symbol == row["symbol"]
                or f"/company/{binding.nse_symbol}/" in row["url"]
            ),
            None,
        )
        if ids is not None and ids.topology is None:
            with pool.connection() as conn:
                entity_id, _, _ = resolve_owner(conn, ids.nse_symbol, ids.isin, None)
            if entity_id is not None:
                ids = ids.model_copy(
                    update={"topology": bind_topology(pool, store, ids, entity_id, {})}
                )
        if ids is None and row["symbol"] is None and spec.id == "chart-api":
            matches = [
                binding
                for binding in bindings
                if binding.screener_company_id is not None
                and urlsplit(row["url"]).path
                == f"/api/company/{binding.screener_company_id}/chart/"
            ]
            ids = matches[0] if len(matches) == 1 else None
        if spec.id == "chart-api" and (
            ids is None
            or ids.screener_company_id is None
            or urlsplit(row["url"]).path != f"/api/company/{ids.screener_company_id}/chart/"
        ):
            version = f"{SITE_NAME[spec.site]}:gate.identity.v1"
            assert ref.capture_ref_id is not None
            if not values.has_outcome(ref.capture_ref_id, spec.id, version):
                values.record(
                    ref,
                    Outcome(
                        surface=spec.id,
                        parser_version=version,
                        parser_sha256=parser_sha256(identity_gate),
                        status=OutcomeStatus.UNUSABLE,
                        symbol=None,
                        detail="verified company binding unavailable",
                    ),
                    row_count=0,
                )
            continue
        basis = (
            (Basis.CONSOLIDATED if "/consolidated/" in row["url"] else Basis.STANDALONE)
            if spec.id == "company-page"
            else None
        )
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parse_and_record(
            store,
            values,
            ref,
            record,
            Request(spec=spec, url=row["url"], ids=ids, basis=basis, due_since=None),
        )
    return len(rows)


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
                result.append(
                    child(
                        spec,
                        context.model_copy(update={"basis": basis}),
                        **({alternative[1]: variant} if alternative else {}),
                    )
                )
    return tuple(result)


def resolve_tijori_slug(
    fetcher: VendorFetcher,
    ids: CompanyIds,
    *,
    pool: ConnectionPool,
    values: VendorValuesStore,
) -> str | None:
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
        return None
    spec = search_spec.model_copy(update={"id": "company-financials"})
    ref, page = capture(
        fetcher,
        fetcher.store,
        pool,
        values,
        Request(
            spec=spec,
            url=f"https://www.tijorifinance.com/company/{quote(slug, safe='')}/financials/",
            ids=ids,
            due_since=None,
        ),
        parse=False,
    )
    state = tijori_page_state(page.raw, slug, ids.nse_symbol)[0].value if page is not None else ""
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
    return slug if state == "VERIFIED" else None


def capture_company(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    specs: tuple[SurfaceSpec, ...],
    ids: CompanyIds,
) -> RunReport:
    """Capture finite company obligations with site gates and retained expansions."""
    from fundamentals.ingest.screener_financials_models import MAX_SCHEDULE_DEPTH
    from fundamentals.ingest.vendor_surface_expand import EXPANSIONS, child

    incomplete: list[str] = []
    refused: list[str] = []
    stopped: list[Site] = []
    blocked: set[Site] = set()
    pages: dict[Basis, CaptureReference] = {}
    cached: dict[str, tuple[CaptureReference, Body | None, Request]] = {}
    deferred: list[Request] = []
    with pool.connection() as conn:
        entity_id, _, _ = resolve_owner(conn, ids.nse_symbol, ids.isin, None)
        covered = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM eqos.reporting_entities WHERE eqos.watchlisted(id)"
            )
        }
        peer_symbols = {
            row.value
            for row in latest_slice(conn)
            if row.entity_id in covered and row.value != ids.nse_symbol
        }
    peers = tuple(
        binding.screener_company_id
        for stock in load_watchlist_config(WATCHLIST).stocks
        if stock.symbol in peer_symbols
        and (binding := company_ids(stock)).screener_company_id is not None
    )
    if not peers:
        incomplete.append("screener:company-compare: no other covered stocks")
    discovery_expected = discovery_completed = 0
    if any(s.site is Site.TIJORI for s in specs) and ids.tijori_slug is None:
        before = fetcher.counts[Site.TIJORI]
        try:
            slug = resolve_tijori_slug(fetcher, ids, pool=pool, values=values)
        except SiteStopped as error:
            stopped.append(error.site)
            blocked.add(error.site)
            slug = None
        except (SiteBusy, ValueError):
            slug = None
        discovery_expected = fetcher.counts[Site.TIJORI] - before
        if discovery_expected:
            with pool.connection() as conn:
                status = conn.execute(
                    "SELECT o.status FROM eqos.vendor_outcomes o JOIN eqos.capture_refs c "
                    "ON c.id=o.capture_ref_id WHERE c.source_id='tijori' AND c.request_key=%s "
                    "ORDER BY o.id DESC LIMIT 1",
                    (
                        request_key(
                            "https://www.tijorifinance.com/api/v1/ind/company_search/?q="
                            + quote(ids.isin, safe="")
                        ),
                    ),
                ).fetchone()
            discovery_completed = int(status is not None and status[0] in USABLE) + int(
                slug is not None
            )
        ids = ids.model_copy(update={"tijori_slug": slug})
        if slug is None:
            incomplete.append("tijori:missing slug")
    pending = list(company_requests(specs, ids))
    expected = len(pending) + len(incomplete) + discovery_expected
    completed = discovery_completed
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
                refused.append(request.url)
            continue
        if request.spec.id == "company-timeline-api":
            from fundamentals.ingest.vendor_surface_market import capture_market

            report = capture_market(fetcher, store, pool, values, (), requests=(request,))
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
            stopped.append(error.site)
            blocked.add(error.site)
            incomplete.append(request.url)
            continue
        except (SiteBusy, ValueError):
            (incomplete if fetcher.remaining(request.spec.site) == 0 else refused).append(
                request.url
            )
            continue
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        refusal = None
        if body is not None and request.spec.id == "company-page":
            try:
                assert_logged_in(body.tree())
                if read_identity(body.tree())[0] != ids.screener_company_id:
                    refusal = "company identity mismatch"
            except ScreenerSessionError as error:
                refusal = type(error).__name__
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
        elif body is not None and request.spec.id == "company-financials":
            gate = classify_financials_body(
                body.raw, expected_symbol=ids.nse_symbol, expected_company_id=ids.tijori_company_id
            )
            if gate.code is not OutcomeCode.OK:
                refusal = gate.native_value
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
        if refusal is not None:
            blocked.add(request.spec.site)
        seen.add(request.url)
        states = parse_and_record(
            store, values, ref, record, request.model_copy(update={"ids": ids}), body, refusal
        )
        usable = all(state in USABLE for state in states)
        completed += int(usable)
        if not usable:
            incomplete.append(
                request.url
                + (": topology unknown" if request.basis and ids.topology is None else "")
            )
        if body is None or refusal is not None:
            continue
        context = ParseContext(
            ids=ids,
            basis=request.basis,
            url=request.url,
            retrieved_at=record.retrieved_at,
            body_sha256=ref.blob_sha256,
            capture_id=record.capture_id,
            parent=request.parent,
        )
        children: list[Request] = []
        if request.spec.id == "company-financials" and ids.tijori_company_id is None:
            details = json.loads(body.tree().xpath('//script[@id="company_details"]/text()')[0])
            ids = ids.model_copy(update={"tijori_company_id": details["company_id"]})
            context = context.model_copy(update={"ids": ids})
            queued = {r.url for r in pending} | seen
            children.extend(r for r in company_requests(specs, ids) if r.url not in queued)

        for spec in specs:
            parent = {
                "screener_schedules": "company-page",
                "screener_investors": "company-page",
                "screener_segments": "company-page",
                "tijori_op_metrics": "company-overview",
                "tijori_revenue_mix_items": "company-overview",
                "tijori_popup_fields": "company-financials",
                "tijori_compare_selector": "company-financials",
            }.get(spec.expand or "")
            if spec.expand == "advertised_links":
                parent = {
                    "quarter-source-pdf": "company-page",
                    "shareholding-detail-chart-api": "company-shareholding",
                    "market-share-peer-companies-api": "company-overview",
                }[spec.id]
            if spec.expand == "screener_compare_peers":
                parent = "company-page"
            expansion = (
                "screener_nested_schedules"
                if request.spec.id == "schedules-api" and spec.id == "schedules-api"
                else spec.expand
            )
            if parent != request.spec.id and expansion != "screener_nested_schedules":
                continue
            assert expansion is not None
            ctx = context.model_copy(
                update={
                    "parent": {**(request.parent or {}), "spec": spec.model_dump(), "peers": peers}
                }
            )
            try:
                expanded = EXPANSIONS[expansion](body, ctx)
                if (
                    expansion == "screener_nested_schedules"
                    and (request.parent or {}).get("depth", 2) >= MAX_SCHEDULE_DEPTH
                ):
                    incomplete.extend(r.url + ": schedule depth limit" for r in expanded)
                    expected += len(expanded)
                    continue
                children.extend(expanded)
                if (
                    not expanded
                    and expansion != "screener_nested_schedules"
                    and spec.id not in ("segments-api", "company-compare")
                ):
                    incomplete.append(f"{SITE_NAME[spec.site]}:{spec.id}: no advertised children")
                    expected += 1
            except (ValueError, KeyError, IndexError, TypeError, ScreenerSessionError):
                incomplete.append(f"{SITE_NAME[spec.site]}:{spec.id}: expansion failed")
                expected += 1
        if request.spec.id == "company-page":
            for spec in specs:
                if spec.id == "chart-api":
                    children.extend(
                        child(
                            spec,
                            context.model_copy(update={"basis": None}),
                            **{"metric-set": metric},
                        )
                        for metric in dict.fromkeys(
                            body.tree().xpath('//*[@id="chart"]//*[@name="metrics"]/@value')
                        )
                        if metric
                    )
                elif "{warehouse_id}" in spec.path and read_identity(body.tree())[1] is not None:
                    children.append(
                        child(spec, context, warehouse_id=read_identity(body.tree())[1])
                    )
        expected += len(children)
        pending.extend(children)
    for url, (ref, body, request) in cached.items():
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parse_and_record(store, values, ref, record, request, body, "company identity unverified")
        incomplete.append(url)
    return RunReport(
        expected=expected,
        completed=completed,
        refused=tuple(refused),
        incomplete=tuple(incomplete),
        stopped_sites=tuple(dict.fromkeys(stopped)),
    )
