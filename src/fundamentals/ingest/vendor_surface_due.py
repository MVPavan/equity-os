"""Covered-universe cadence: what is due, oldest first, computed from stored outcomes only."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from itertools import groupby
from urllib.parse import urlsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.snapshot import CAPTURE_ID_TIME_FORMAT
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.vendor_surface_capture import (
    TOPOLOGY_UNKNOWN,
    WATCHLIST,
    Request,
    RunReport,
    capture_company,
    company_ids,
    company_requests,
    registered_ids,
)
from fundamentals.ingest.vendor_surface_expand import advertised, expansion_name
from fundamentals.ingest.vendor_surface_fetch import Site, VendorFetcher
from fundamentals.ingest.vendor_surface_market import (
    capture_market,
    market_requests,
    progress,
    traversal_key,
)
from fundamentals.ingest.vendor_surface_parse import Body, CompanyIds
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, Cadence, Scope, SurfaceSpec
from fundamentals.ingest.vendor_surface_tables import feed_rows
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import USABLE, VendorValue, VendorValuesStore

MAX_ATTEMPTS = 10
RESULTS_FEEDS = ("results-latest", "quarterly-results-api")
PARENTS = ("company-page", "company-financials")  # capture_company moves these to the front.
# The latest outcome per logical surface supersedes earlier parses of the same capture.
HISTORY = """SELECT DISTINCT ON (c.id, o.surface, o.traversal_key IS NULL) c.*, a.url,
    o.id AS outcome, o.surface AS logical, o.status, o.detail,
    o.traversal_key IS NOT NULL AS traversal, o.traversal_page AS page,
    o.traversal_key IS NULL OR o.traversal_done AS done
FROM eqos.capture_refs c JOIN eqos.capture_addresses a ON a.capture_ref_id = c.id
JOIN eqos.vendor_outcomes o ON o.capture_ref_id = c.id AND o.parser_version NOT LIKE '%%.slug.v1'
WHERE c.surface LIKE 'vs.%%' AND NOT starts_with(o.parser_version,'claims:') ORDER BY c.id, o.surface, o.traversal_key IS NULL, o.id DESC"""
PERIODS = """SELECT outcome_id, max(to_date(column_label, 'Mon YYYY')) FROM eqos.vendor_values
WHERE outcome_id = ANY(%s) AND column_label ~ '^[A-Z][a-z]{2} [0-9]{4}$' GROUP BY 1"""
FEED_VALUES = """SELECT v.*, o.surface AS feed, o.parser_version, c.capture_id AS retrieved
FROM eqos.vendor_values v
JOIN eqos.vendor_outcomes o ON o.id = v.outcome_id
JOIN eqos.capture_refs c ON c.id = v.capture_ref_id
WHERE o.surface = ANY(%s) AND o.status = ANY(%s) AND v.table_key = o.surface || ':feed'
ORDER BY c.capture_id, v.outcome_id"""
COVERED = """SELECT v.trading_symbol, v.isin FROM eqos.reporting_entities e
JOIN eqos.securities s ON s.entity_id = e.id
JOIN eqos.registry_view v ON v.isin = s.isin AND v.segment = 'NSE_EQ' AND v.status = 'LISTED'
WHERE eqos.watchlisted(e.id) ORDER BY e.id"""
VENDOR_FIELDS = ("tijori_slug", "tijori_company_id", "screener_company_id", "topology")


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
    retry: tuple[Request, ...]  # Open instances still to capture, at their parent's priority.
    spent: tuple[str, ...]  # Traversal keys of open instances out of attempts.
    starts: dict[str, datetime]  # Retry eligibility begins after this instant, per instance.


class Trigger(BaseModel):
    """A results-feed row for the company and the statement refresh it still requires."""

    model_config = ConfigDict(frozen=True)
    row_id: str
    first_seen: datetime
    obligations: tuple[Obligation, ...]


class Seen(BaseModel):
    """One registered capture of a request identity, as its latest outcomes classify it."""

    model_config = ConfigDict(frozen=True)
    ref: CaptureReference
    retrieved_at: datetime
    usable: bool
    gated: bool
    period: date | None
    expandable: bool = True  # A traversal's first page, kept or gated: what advertises children.


class Node(BaseModel):
    """One request instance of the retained tree and its expansion gaps."""

    model_config = ConfigDict(frozen=True)
    request: Request
    gaps: tuple[str, ...]


Expand = Callable[[Request, Seen], tuple[tuple[Request, ...], tuple[str, ...]]]


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
    """Every configured capture, oldest retrieval first, keyed by its traversal identity."""
    by_id = {(spec.site, spec.id): spec for spec in specs}
    statements = {"vs." + s.id for s in specs if s.cadence is Cadence.AFTER_RESULTS}
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(HISTORY).fetchall()
        selected = [r["outcome"] for r in rows if r["surface"] in statements and not r["traversal"]]
        periods: dict[int, date] = dict(conn.execute(PERIODS, (selected,)).fetchall())
    found: dict[str, list[Seen]] = {}
    for _, group in groupby(rows, key=lambda row: row["id"]):
        outcomes = list(group)
        row = outcomes[0]
        if not (spec := by_id.get((Site(row["source_id"]), row["surface"][3:]))):
            continue
        parsed = {o["logical"]: o for o in outcomes if not o["traversal"]}
        complete = {spec.id, *spec.sections} <= parsed.keys() and all(
            o["status"] in USABLE for o in outcomes
        )
        gated = parsed.get(spec.id, {}).get("detail") == TOPOLOGY_UNKNOWN
        key = traversal_key(Request(spec=spec, url=row["url"], ids=None, due_since=None))
        found.setdefault(key, []).append(
            Seen(
                ref=capture_of(row),
                retrieved_at=retrieved_at(row["capture_id"]),
                usable=complete and all(o["done"] for o in outcomes),
                gated=gated,
                period=max(
                    (periods[o["outcome"]] for o in outcomes if o["outcome"] in periods),
                    default=None,
                ),
                expandable=(complete or gated) and all(o["page"] in (None, 1) for o in outcomes),
            )
        )
    for seen in found.values():
        seen.sort(key=lambda s: s.retrieved_at)
    return found


def retrieved_at(capture_id: str) -> datetime:
    """The retrieval instant every capture id begins with."""
    return datetime.strptime(capture_id.split("-")[0], CAPTURE_ID_TIME_FORMAT).replace(tzinfo=UTC)


def results_rows(
    pool: ConnectionPool, specs: tuple[SurfaceSpec, ...]
) -> dict[tuple[str, str], datetime]:
    """Each results-feed row, by company path and row id, with its first retrieval."""
    feeds = {spec.id: spec for spec in specs if spec.id in RESULTS_FEEDS}
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(FEED_VALUES, (list(feeds), list(USABLE))).fetchall()
    first: dict[tuple[str, str], datetime] = {}
    for _, group in groupby(rows, key=lambda row: row["outcome_id"]):
        cells = list(group)
        values = tuple(VendorValue.model_validate(row) for row in cells)
        legacy = cells[0]["parser_version"].endswith(".v1")
        for item in feed_rows(feeds[cells[0]["feed"]], values, legacy):
            company = "/".join(urlsplit(item.company).path.split("/")[2:3])
            first.setdefault((company, item.row_id), retrieved_at(cells[0]["retrieved"]))
    return first


def expander(
    store: SnapshotStore, specs: tuple[SurfaceSpec, ...], peers: tuple[int, ...]
) -> Expand:
    """Read a retained parent capture's advertised children and gaps, once per capture."""
    cache: dict[tuple[str, str], tuple[tuple[Request, ...], tuple[str, ...]]] = {}

    def expand(request: Request, base: Seen) -> tuple[tuple[Request, ...], tuple[str, ...]]:
        """Children carry the parent capture's retrieval as their priority."""
        ref = base.ref
        if (marker := (request.url, ref.capture_id)) not in cache:
            record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
            context = request.context(record, ref.blob_sha256)
            children, gaps = advertised(
                request, Body(raw=store.read_body(record)), context, specs, peers
            )
            update = {"due_since": base.retrieved_at}
            cache[marker] = tuple(c.model_copy(update=update) for c in children), gaps
        return cache[marker]

    return expand


def tree(roots: Iterable[Request], seen: dict[str, list[Seen]], expand: Expand) -> dict[str, Node]:
    """The bounded request tree that each instance's latest first-page capture advertises."""
    nodes: dict[str, Node] = {}
    queue = list(roots)
    while queue:
        request = queue.pop(0)
        if (key := traversal_key(request)) in nodes:
            continue
        base = next((s for s in reversed(seen.get(key, [])) if s.expandable), None)
        children, gaps = expand(request, base) if base else ((), ())
        nodes[key] = Node(request=request, gaps=gaps)
        queue.extend(children)
    return nodes


def covered_universe(pool: ConnectionPool, store: SnapshotStore) -> tuple[CompanyIds, ...]:
    """Every watchlisted NSE listing, with configured or retained-evidence vendor ids."""
    stocks = {stock.symbol: stock for stock in load_watchlist_config(WATCHLIST).stocks}
    with pool.connection() as conn:
        rows = conn.execute(COVERED).fetchall()
    universe = []
    for symbol, isin in rows:
        try:
            ids = registered_ids(pool, store, symbol)
        except ValueError:
            ids = CompanyIds(nse_symbol=symbol, isin=isin, **dict.fromkeys(VENDOR_FIELDS))
        if symbol in stocks:
            config = company_ids(stocks[symbol])
            update = {field: getattr(config, field) for field in VENDOR_FIELDS}
            ids = ids.model_copy(update={k: v for k, v in update.items() if v is not None})
        universe.append(ids)
    return tuple(universe)


def pending_triggers(
    ids: CompanyIds,
    specs: tuple[SurfaceSpec, ...],
    roots: tuple[Request, ...],
    seen: dict[str, list[Seen]],
    rows: dict[tuple[str, str], datetime],
    expand: Expand,
) -> tuple[Trigger, ...]:
    """Results rows for this company whose statement obligations are not all satisfied."""
    triggers = []
    for (company, row), first in rows.items():
        if company not in (ids.nse_symbol, ids.tijori_slug):
            continue
        found = (
            obligation(spec, basis, first, roots, seen, expand)
            for spec in specs
            if spec.cadence is Cadence.AFTER_RESULTS and spec.scope is Scope.COMPANY
            for basis in (
                (None,)
                if spec.site is Site.TIJORI
                else tuple(b for b in Basis if ids.topology and ids.topology.warehouse_id_for(b))
            )
        )
        obligations = tuple(o for o in found if o is not None)
        if any(o.state is not ObligationState.SATISFIED for o in obligations):
            triggers.append(Trigger(row_id=row, first_seen=first, obligations=obligations))
    return tuple(triggers)


def obligation(
    spec: SurfaceSpec,
    basis: Basis | None,
    first: datetime,
    roots: tuple[Request, ...],
    seen: dict[str, list[Seen]],
    expand: Expand,
) -> Obligation | None:
    """Every instance that the satisfying parent captures advertise, frozen capture by capture.

    An instance is satisfied by its first refreshing capture whose expansion has no gap for this
    surface; only that capture's children are required, so a later parent never changes the tree
    and descendants of an unsatisfied instance do not exist. An open instance has one attempt per
    day with a capture since its start, and is out of attempts at MAX_ATTEMPTS.
    """
    queue = [
        r
        for r in roots
        if r.basis == basis and (r.spec.id == spec.id or expansion_name(spec, r.spec.id))
    ]
    if not queue:
        return None
    prefix = f"{SITE_NAME[spec.site]}:{spec.id}:"
    visited: set[str] = set()
    open_: dict[str, tuple[Request, int]] = {}
    starts: dict[str, datetime] = {}
    while queue:
        request = queue.pop(0)
        if (key := traversal_key(request)) in visited:
            continue
        visited.add(key)
        captures = seen.get(key, [])
        usable = [s for s in captures if s.usable]
        start = request.due_since or first  # A headerless child counts from its parent's capture.
        if request.due_since is None or any(s.period for s in captures):
            old = max(
                (s.period for s in usable if s.retrieved_at <= first and s.period), default=date.min
            )
            usable, start = [s for s in usable if s.period and s.period > old], first
        for base in (s for s in usable if s.retrieved_at > start):
            children, gaps = expand(request, base)
            if not any(gap.startswith(prefix) for gap in gaps):
                queue.extend(c for c in children if c.spec.id == spec.id)
                break
        else:
            days = {s.retrieved_at.date() for s in captures if s.retrieved_at > start}
            open_[key] = request, len(days)
            if len(days) < MAX_ATTEMPTS:
                starts[key] = start
    state = ObligationState.SATISFIED
    if open_:
        spent = all(n >= MAX_ATTEMPTS for _, n in open_.values())
        state = ObligationState.EXHAUSTED if spent else ObligationState.PENDING
    return Obligation(
        site=spec.site,
        surface=spec.id,
        basis=basis,
        attempts=max((n for _, n in open_.values()), default=0),
        state=state,
        retry=tuple(r for r, n in open_.values() if n < MAX_ATTEMPTS),
        spent=tuple(k for k, (_, n) in open_.items() if n >= MAX_ATTEMPTS),
        starts=starts,
    )


def due_requests(
    pool: ConnectionPool, store: SnapshotStore, specs: tuple[SurfaceSpec, ...], now: datetime
) -> tuple[tuple[Request, ...], tuple[str, ...]]:
    """Due requests oldest first (never-captured first), plus standing incomplete work."""
    seen, rows = history(pool, specs), results_rows(pool, specs)
    today = datetime.combine(now.date(), time(), UTC)
    universe = covered_universe(pool, store)
    due: list[Request] = []
    notes: list[str] = []

    def queue(
        nodes: dict[str, Node],
        pending: dict[str, Request],
        starts: dict[str, datetime],
        spent: set[str],
        label: str,
    ) -> None:
        """Queue due instances: obligation instances at most once a day, never when spent."""
        for key, node in {
            **nodes,
            **{k: Node(request=r, gaps=()) for k, r in pending.items()},
        }.items():
            request, hist, spec = node.request, seen.get(key, []), node.request.spec
            notes.extend(label + gap for gap in nodes.get(key, node).gaps)
            if spec.feed and progress(pool, key).resume_page is not None:
                notes.append(f"{label}{SITE_NAME[spec.site]}:{spec.id}: INCOMPLETE")
            if (
                key in spent
                or key in pending
                and any(s.retrieved_at >= today and s.retrieved_at > starts[key] for s in hist)
            ):
                continue
            usable = [s for s in hist if s.usable]
            if request.basis and request.ids and request.ids.topology is None:
                spec = spec.model_copy(update={"cadence": Cadence.WEEKLY})
                usable = [s for s in hist if s.usable or s.gated]
            last = usable[-1].retrieved_at if usable else None
            if is_due(spec, last, now, key in pending):
                due.append(request.model_copy(update={"due_since": request.due_since or last}))

    queue(tree(market_requests(specs, pool), seen, expander(store, specs, ())), {}, {}, set(), "")
    for ids in universe:
        peers = tuple(o.screener_company_id for o in universe if o != ids and o.screener_company_id)
        expand, roots = expander(store, specs, peers), company_requests(specs, ids)
        triggers = pending_triggers(ids, specs, roots, seen, rows, expand)
        obligations = [o for t in triggers for o in t.obligations]
        notes.extend(
            f"{ids.nse_symbol}:{SITE_NAME[o.site]}:{o.surface}:{o.basis or '-'}: INCOMPLETE"
            for o in obligations
            if o.state is ObligationState.EXHAUSTED
        )
        notes.extend(
            f"{ids.nse_symbol}: {gap}"
            for gap, missing in (
                (TOPOLOGY_UNKNOWN, ids.topology),
                ("tijori:missing slug", ids.tijori_slug),
                ("screener:missing company id", ids.screener_company_id),
            )
            if missing is None
        )
        pending: dict[str, Request] = {}
        for request in sorted(
            (r for o in obligations for r in o.retry),
            key=lambda r: r.due_since or datetime.min.replace(tzinfo=UTC),
        ):
            pending.setdefault(traversal_key(request), request)
        starts = {k: max(o.starts[k] for o in obligations if k in o.starts) for k in pending}
        spent = {k for o in obligations for k in o.spent} - pending.keys()
        nodes = tree(roots, seen, expand)
        unsettled = {
            (o.site, o.surface, o.basis)
            for o in obligations
            if o.state is not ObligationState.SATISFIED
        }
        spent |= {
            k
            for k, n in nodes.items()
            if (n.request.spec.site, n.request.spec.id, n.request.basis) in unsettled
            and k not in pending
        }
        queue(nodes, pending, starts, spent, f"{ids.nse_symbol}: ")
    due.sort(key=lambda r: (r.due_since is not None, r.due_since or now))
    return tuple(due), tuple(dict.fromkeys(notes))


def capture_due(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    specs: tuple[SurfaceSpec, ...],
    now: datetime,
) -> RunReport:
    """Capture due work in rounds, market feeds first, until nothing new is due this run.

    Consecutive requests of one company (or the market) form one call, in global due order; a
    parent after a non-parent starts a new call, since capture_company moves parents first.
    """
    tried: set[str] = set()
    reports: list[RunReport] = []
    feeds_first = True
    # An unresolved slug is retried once every run, whether or not anything else is due.
    discovery = {i.nse_symbol: i for i in covered_universe(pool, store) if i.tijori_slug is None}
    without_tijori = tuple(s for s in specs if s.site is not Site.TIJORI)
    while True:
        due, notes = due_requests(pool, store, specs, now)
        batch = [r for r in due if r.url not in tried]
        batch = ([r for r in batch if r.spec.feed] if feeds_first else []) or batch
        feeds_first = False
        if not batch and not discovery:
            break
        runs: list[list[Request]] = []
        for request in batch:
            tried.add(request.url)
            last = runs[-1][-1] if runs else None
            if (
                last is None
                or last.ids != request.ids
                or request.spec.id in PARENTS
                and last.spec.id not in PARENTS
            ):
                runs.append([])
            runs[-1].append(request)
        listed = {r.ids.nse_symbol for r in batch if r.ids}
        calls: list[tuple[CompanyIds | None, list[Request]]] = [(r[0].ids, r) for r in runs]
        calls += [(ids, []) for name, ids in discovery.items() if name not in listed]
        for company, run in calls:
            if company is None:
                report = capture_market(
                    fetcher,
                    store,
                    pool,
                    values,
                    specs,
                    requests=tuple(run),
                    today=now.date(),
                    scheduled=True,
                )
            else:
                found = discovery.pop(company.nse_symbol, None)
                scoped = specs if found or company.tijori_slug else without_tijori
                report = capture_company(fetcher, store, pool, values, scoped, company, tuple(run))
            reports.append(report)
    return RunReport(
        expected=sum(r.expected for r in reports),
        completed=sum(r.completed for r in reports),
        refused=tuple(url for r in reports for url in r.refused),
        incomplete=tuple(dict.fromkeys((*(i for r in reports for i in r.incomplete), *notes))),
        stopped_sites=tuple(dict.fromkeys(site for r in reports for site in r.stopped_sites)),
    )
