"""Covered-universe cadence: what is due, oldest first, computed from stored outcomes only."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest.screener_financials_models import MAX_SCHEDULE_DEPTH
from fundamentals.ingest.screener_session_models import Basis, ScreenerSessionError
from fundamentals.ingest.screener_session_page import read_identity
from fundamentals.ingest.vendor_surface_capture import (
    TOPOLOGY_UNKNOWN,
    WATCHLIST,
    Request,
    RunReport,
    capture,
    company_ids,
    company_requests,
)
from fundamentals.ingest.vendor_surface_expand import EXPANSIONS, MARKET_PARENTS, child
from fundamentals.ingest.vendor_surface_fetch import Site, SiteBusy, SiteStopped, VendorFetcher
from fundamentals.ingest.vendor_surface_market import capture_market, market_requests, traversal_key
from fundamentals.ingest.vendor_surface_parse import Body, CompanyIds, ParseContext
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, Cadence, Scope, SurfaceSpec
from fundamentals.ingest.vendor_surface_tables import feed_rows
from fundamentals.ingest.vendor_surface_topology import bind_topology
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import USABLE, VendorValue, VendorValuesStore

MAX_ATTEMPTS = 10
RESULTS_FEEDS = ("results-latest", "quarterly-results-api")
# The company expansion parents `capture_company` dispatches inline, by child id or expansion.
COMPANY_PARENTS = {
    "screener_schedules": "company-page",
    "screener_investors": "company-page",
    "screener_segments": "company-page",
    "screener_compare_peers": "company-page",
    "quarter-source-pdf": "company-page",
    "tijori_op_metrics": "company-overview",
    "tijori_revenue_mix_items": "company-overview",
    "market-share-peer-companies-api": "company-overview",
    "tijori_popup_fields": "company-financials",
    "tijori_compare_selector": "company-financials",
    "shareholding-detail-chart-api": "company-shareholding",
}
HISTORY = """SELECT c.*, a.url,
    bool_or(o.status = ANY(%(usable)s))
        AND bool_and(o.traversal_key IS NULL OR o.traversal_done) AS usable,
    coalesce(bool_or(o.detail = %(gated)s), false) AS gated,
    CASE WHEN c.surface = ANY(%(statements)s) THEN (SELECT max(to_date(v.column_label, 'Mon YYYY'))
        FROM eqos.vendor_values v WHERE v.capture_ref_id = c.id
        AND v.column_label ~ '^[A-Z][a-z]{2} [0-9]{4}$') END AS period
FROM eqos.capture_refs c JOIN eqos.capture_addresses a ON a.capture_ref_id = c.id
JOIN eqos.vendor_outcomes o ON o.capture_ref_id = c.id AND 'vs.' || o.surface = c.surface
    AND o.parser_version NOT LIKE '%%.slug.v1'
WHERE c.surface LIKE 'vs.%%' GROUP BY c.id, a.url ORDER BY c.registered_at"""
OUTCOMES_USABLE = (
    "SELECT bool_and(status = ANY(%s)) FROM eqos.vendor_outcomes WHERE capture_ref_id=%s"
)
FEED_VALUES = """SELECT v.*, o.surface AS feed, c.registered_at FROM eqos.vendor_values v
JOIN eqos.vendor_outcomes o ON o.id = v.outcome_id
JOIN eqos.capture_refs c ON c.id = v.capture_ref_id
WHERE o.surface = ANY(%s) AND o.status = ANY(%s) AND v.table_key = o.surface || ':feed'
ORDER BY c.registered_at, v.outcome_id"""
COVERED = """SELECT e.id, v.trading_symbol, v.isin FROM eqos.reporting_entities e
JOIN eqos.securities s ON s.entity_id = e.id
JOIN eqos.registry_view v ON v.isin = s.isin AND v.segment = 'NSE_EQ' AND v.status = 'LISTED'
WHERE eqos.watchlisted(e.id) ORDER BY e.id"""


class ObligationState(StrEnum):
    """Where one surface and basis stands against a results trigger."""

    PENDING = "PENDING"
    SATISFIED = "SATISFIED"
    EXHAUSTED = "EXHAUSTED"


class Obligation(BaseModel):
    """One statement surface and basis that must show the new period."""

    model_config = ConfigDict(frozen=True)
    site: Site
    surface: str
    basis: Basis | None
    attempts: int
    state: ObligationState


class Trigger(BaseModel):
    """A results-feed row for the company and the statement refresh it still requires."""

    model_config = ConfigDict(frozen=True)
    row_id: str
    first_seen: datetime
    obligations: tuple[Obligation, ...]


class Seen(BaseModel):
    """One registered capture of a request identity, as stored outcomes classify it."""

    model_config = ConfigDict(frozen=True)
    ref: CaptureReference
    registered_at: datetime
    usable: bool
    gated: bool
    period: date | None


def is_due(
    spec: SurfaceSpec, last_usable: datetime | None, now: datetime, trigger_pending: bool
) -> bool:
    """Apply the surface cadence to its latest usable capture."""
    if last_usable is None or trigger_pending:
        return True
    if spec.cadence is Cadence.DAILY:
        return last_usable < datetime.combine(now.date(), time(), UTC)
    return spec.cadence is Cadence.WEEKLY and last_usable <= now - timedelta(days=7)


def history(pool: ConnectionPool, specs: tuple[SurfaceSpec, ...]) -> dict[str, list[Seen]]:
    """Every configured capture, oldest first, keyed by its traversal identity."""
    by_id = {(spec.site, spec.id): spec for spec in specs}
    statements = ["vs." + s.id for s in specs if s.cadence is Cadence.AFTER_RESULTS]
    params = {"usable": list(USABLE), "gated": TOPOLOGY_UNKNOWN, "statements": statements}
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(HISTORY, params).fetchall()
    found: dict[str, list[Seen]] = {}
    for row in rows:
        if spec := by_id.get((Site(row["source_id"]), row["surface"][3:])):
            key = traversal_key(Request(spec=spec, url=row["url"], ids=None, due_since=None))
            found.setdefault(key, []).append(Seen.model_validate({**row, "ref": capture_of(row)}))
    return found


def children(
    request: Request,
    seen: Seen,
    store: SnapshotStore,
    specs: tuple[SurfaceSpec, ...],
    peers: tuple[int, ...],
) -> tuple[Request, ...]:
    """Re-expand a retained parent capture into the child requests it advertises."""
    ref = seen.ref
    record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
    body = Body(raw=store.read_body(record))
    context = ParseContext(
        ids=request.ids,
        basis=request.basis,
        url=request.url,
        retrieved_at=record.retrieved_at,
        body_sha256=ref.blob_sha256,
        capture_id=record.capture_id,
        parent=request.parent,
    )
    page = request.spec.id == "company-page"
    found: list[Request] = []
    for spec in specs:
        name = spec.expand or ""
        parents = (
            COMPANY_PARENTS.get(spec.id) or COMPANY_PARENTS.get(name),
            *MARKET_PARENTS.get(name, ()),
        )
        try:
            if spec.site is not request.spec.site:
                continue
            if page and spec.id == "chart-api":
                plain = context.model_copy(update={"basis": None})
                metrics = body.tree().xpath('//*[@id="chart"]//*[@name="metrics"]/@value')
                found.extend(
                    child(spec, plain, **{"metric-set": m}) for m in dict.fromkeys(metrics) if m
                )
            elif page and "{warehouse_id}" in spec.path:
                if (warehouse := read_identity(body.tree())[1]) is not None:
                    found.append(child(spec, context, warehouse_id=warehouse))
            elif request.spec.id in parents or request.spec.id == spec.id == "schedules-api":
                if request.spec.id == "schedules-api":
                    name = "screener_nested_schedules"
                    if (request.parent or {}).get("depth", 2) >= MAX_SCHEDULE_DEPTH:
                        continue
                parent = {**(request.parent or {}), "spec": spec.model_dump(), "peers": peers}
                found.extend(EXPANSIONS[name](body, context.model_copy(update={"parent": parent})))
        except (ValueError, KeyError, IndexError, TypeError, ScreenerSessionError):
            continue
    return tuple(found)


def covered_universe(pool: ConnectionPool, store: SnapshotStore) -> tuple[CompanyIds, ...]:
    """Watchlisted entities listed on NSE, with configured vendor ids and bound topology."""
    stocks = {stock.symbol: stock for stock in load_watchlist_config(WATCHLIST).stocks}
    with pool.connection() as conn:
        rows = conn.execute(COVERED).fetchall()
    universe = []
    for entity, symbol, isin in rows:
        if symbol in stocks:
            ids = company_ids(stocks[symbol]).model_copy(update={"isin": isin})
            topology = bind_topology(pool, store, ids, entity, {})
            universe.append(ids.model_copy(update={"topology": topology}))
    return tuple(universe)


def pending_triggers(
    pool: ConnectionPool, store: SnapshotStore, ids: CompanyIds, specs: tuple[SurfaceSpec, ...]
) -> tuple[Trigger, ...]:
    """Results rows for this company whose statement obligations are not all satisfied."""
    seen = history(pool, specs)
    feeds = {spec.id: spec for spec in specs if spec.id in RESULTS_FEEDS}
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(FEED_VALUES, (list(feeds), list(USABLE))).fetchall()
    outcomes: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        outcomes.setdefault(row["outcome_id"], []).append(row)
    first: dict[str, datetime] = {}
    for group in outcomes.values():
        cells = tuple(VendorValue.model_validate(row) for row in group)
        for item in feed_rows(feeds[group[0]["feed"]], cells):
            if urlsplit(item.company).path.split("/")[2:3] in ([ids.nse_symbol], [ids.tijori_slug]):
                first.setdefault(item.row_id, group[0]["registered_at"])
    roots = {(r.spec.id, r.basis): r for r in company_requests(specs, ids)}
    triggers = []
    for row_id, at in first.items():
        obligations = []
        for spec in specs:
            if spec.cadence is not Cadence.AFTER_RESULTS or spec.scope is not Scope.COMPANY:
                continue
            bases = (None,) if spec.site is Site.TIJORI else tuple(Basis) if ids.topology else ()
            for basis in bases:
                parent = COMPANY_PARENTS.get(spec.expand or "", "")
                if not (root := roots.get((spec.id, basis)) or roots.get((parent, basis))):
                    continue
                hist = seen.get(traversal_key(root), [])
                old = [s.period for s in hist if s.usable and s.registered_at <= at and s.period]
                done = [
                    s
                    for s in hist
                    if s.usable
                    and s.registered_at > at
                    and s.period
                    and s.period > max(old, default=date.min)
                ]
                kids = [
                    seen.get(traversal_key(r), [])
                    for r in (children(root, done[0], store, specs, ()) if done else ())
                    if r.spec.id == spec.id and root.spec.id != spec.id
                ]
                after = done[0].registered_at if done else at
                refreshed = all(any(s.usable and s.registered_at > after for s in h) for h in kids)
                attempts = max(sum(s.registered_at > at for s in h) for h in kids or [hist])
                state = ObligationState.SATISFIED if done and refreshed else ObligationState.PENDING
                if state is ObligationState.PENDING and attempts >= MAX_ATTEMPTS:
                    state = ObligationState.EXHAUSTED
                obligations.append(
                    Obligation(
                        site=spec.site, surface=spec.id, basis=basis, attempts=attempts, state=state
                    )
                )
        if any(o.state is not ObligationState.SATISFIED for o in obligations):
            triggers.append(Trigger(row_id=row_id, first_seen=at, obligations=tuple(obligations)))
    return tuple(triggers)


def due_requests(
    pool: ConnectionPool, store: SnapshotStore, specs: tuple[SurfaceSpec, ...], now: datetime
) -> tuple[tuple[Request, ...], tuple[str, ...]]:
    """Due requests oldest first (never-captured first), plus standing incomplete work."""
    seen = history(pool, specs)
    today = datetime.combine(now.date(), time(), UTC)
    universe = covered_universe(pool, store)
    due: list[Request] = []
    notes: list[str] = []
    visited: set[str] = set()

    def visit(
        request: Request, parent_at: datetime | None, pending: bool, peers: tuple[int, ...]
    ) -> None:
        """Queue a due request; children inherit the time of the parent they came from."""
        if (key := traversal_key(request)) in visited:
            return
        visited.add(key)
        hist, spec = seen.get(key, []), request.spec
        usable = [s for s in hist if s.usable]
        if request.basis is not None and request.ids is not None and request.ids.topology is None:
            spec = spec.model_copy(update={"cadence": Cadence.WEEKLY})
            usable = [s for s in hist if s.usable or s.gated]
        last = usable[-1].registered_at if usable else None
        retry = pending and not any(s.registered_at >= today for s in hist)
        if is_due(spec, last, now, retry) or (parent_at and (last is None or last < parent_at)):
            due.append(request.model_copy(update={"due_since": last or parent_at}))
        if base := next((s for s in reversed(hist) if s.usable or s.gated), None):
            for item in children(request, base, store, specs, peers):
                visit(item, base.registered_at, False, peers)

    for request in market_requests(specs, pool):
        visit(request, None, False, ())
    for ids in universe:
        triggers = pending_triggers(pool, store, ids, specs)
        states = {(o.site, o.surface, o.basis): o.state for t in triggers for o in t.obligations}
        notes.extend(
            f"{ids.nse_symbol}:{SITE_NAME[site]}:{surface}:{basis or '-'}: INCOMPLETE"
            for (site, surface, basis), state in states.items()
            if state is ObligationState.EXHAUSTED
        )
        notes.extend(
            f"{ids.nse_symbol}: {gap}"
            for gap, missing in (
                (TOPOLOGY_UNKNOWN, ids.topology),
                ("tijori:missing slug", ids.tijori_slug),
            )
            if missing is None
        )
        peers = tuple(o.screener_company_id for o in universe if o != ids and o.screener_company_id)
        for request in company_requests(specs, ids):
            pending = states.get((request.spec.site, request.spec.id, request.basis))
            visit(request, None, pending is ObligationState.PENDING, peers)
    due.sort(key=lambda r: (r.due_since is not None, r.due_since or now))
    return tuple(due), tuple(notes)


def capture_due(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    specs: tuple[SurfaceSpec, ...],
    now: datetime,
) -> RunReport:
    """Capture due work in rounds, market feeds first, until nothing new is due this run."""
    tried: set[str] = set()
    reports: list[RunReport] = []
    feeds_first = True
    while True:
        due, notes = due_requests(pool, store, specs, now)
        batch = [r for r in due if r.url not in tried]
        batch, feeds_first = (
            ([r for r in batch if r.spec.feed] if feeds_first else []) or batch,
            False,
        )
        if not batch:
            break
        for request in batch:
            tried.add(request.url)
            if request.spec.scope is Scope.MARKET or request.spec.id == "company-timeline-api":
                report = capture_market(
                    fetcher, store, pool, values, (), requests=(request,), today=now.date()
                )
            else:
                report = capture_company_request(fetcher, store, pool, values, request)
            reports.append(report)
    return RunReport(
        expected=sum(r.expected for r in reports),
        completed=sum(r.completed for r in reports),
        refused=tuple(url for r in reports for url in r.refused),
        incomplete=(*(url for r in reports for url in r.incomplete), *dict.fromkeys(notes)),
        stopped_sites=tuple(dict.fromkeys(site for r in reports for site in r.stopped_sites)),
    )


def capture_company_request(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    request: Request,
) -> RunReport:
    """One company capture: usable, held by the budget, refused, or stopped."""
    completed, url = 0, request.url
    stopped: tuple[Site, ...] = ()
    try:
        ref, _ = capture(fetcher, store, pool, values, request)
        with pool.connection() as conn:
            row = conn.execute(OUTCOMES_USABLE, (list(USABLE), ref.capture_ref_id)).fetchone()
        completed = int(bool(row and row[0]))
    except SiteStopped as error:
        stopped = (error.site,)
    except (SiteBusy, ValueError):
        if fetcher.remaining(request.spec.site) > 0:
            return RunReport(
                expected=1, completed=0, refused=(url,), incomplete=(), stopped_sites=()
            )
    return RunReport(
        expected=1,
        completed=completed,
        refused=(),
        incomplete=() if completed else (url,),
        stopped_sites=stopped,
    )
