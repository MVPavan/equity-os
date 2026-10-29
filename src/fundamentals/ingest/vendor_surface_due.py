"""Covered-universe cadence: what is due, oldest first, computed from stored outcomes only."""

from __future__ import annotations

from collections.abc import Iterable
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
from fundamentals.ingest.vendor_surface_market import capture_market, market_requests, traversal_key
from fundamentals.ingest.vendor_surface_parse import Body, CompanyIds
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, Cadence, Scope, SurfaceSpec
from fundamentals.ingest.vendor_surface_tables import feed_rows
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import USABLE, VendorValue, VendorValuesStore

MAX_ATTEMPTS = 10
RESULTS_FEEDS = ("results-latest", "quarterly-results-api")
# The latest outcome per logical surface supersedes earlier parses of the same capture.
HISTORY = """SELECT DISTINCT ON (c.id, o.surface, o.traversal_key IS NULL) c.*, a.url,
    o.surface AS logical, o.status, o.detail, o.traversal_key IS NOT NULL AS traversal,
    o.traversal_key IS NULL OR o.traversal_done AS done
FROM eqos.capture_refs c JOIN eqos.capture_addresses a ON a.capture_ref_id = c.id
JOIN eqos.vendor_outcomes o ON o.capture_ref_id = c.id AND o.parser_version NOT LIKE '%%.slug.v1'
WHERE c.surface LIKE 'vs.%%' ORDER BY c.id, o.surface, o.traversal_key IS NULL, o.id DESC"""
PERIODS = """SELECT v.capture_ref_id, max(to_date(v.column_label, 'Mon YYYY'))
FROM eqos.vendor_values v JOIN eqos.capture_refs c ON c.id = v.capture_ref_id
WHERE c.surface = ANY(%s) AND v.column_label ~ '^[A-Z][a-z]{2} [0-9]{4}$' GROUP BY 1"""
FEED_VALUES = """SELECT v.*, o.surface AS feed, c.capture_id AS retrieved FROM eqos.vendor_values v
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
    retry: tuple[str, ...]  # Traversal keys of the instances still to capture.


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


class Node(BaseModel):
    """One request instance of the retained tree, its parent and its expansion gaps."""

    model_config = ConfigDict(frozen=True)
    request: Request
    parent: str | None
    gaps: tuple[str, ...]


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
    statements = ["vs." + s.id for s in specs if s.cadence is Cadence.AFTER_RESULTS]
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(HISTORY).fetchall()
        periods: dict[int, date] = dict(conn.execute(PERIODS, (statements,)).fetchall())
    found: dict[str, list[Seen]] = {}
    for _, group in groupby(rows, key=lambda row: row["id"]):
        outcomes = list(group)
        row = outcomes[0]
        if not (spec := by_id.get((Site(row["source_id"]), row["surface"][3:]))):
            continue
        parsed = {o["logical"]: o for o in outcomes if not o["traversal"]}
        key = traversal_key(Request(spec=spec, url=row["url"], ids=None, due_since=None))
        found.setdefault(key, []).append(
            Seen(
                ref=capture_of(row),
                retrieved_at=retrieved_at(row["capture_id"]),
                usable={spec.id, *spec.sections} <= parsed.keys()
                and all(o["status"] in USABLE and o["done"] for o in outcomes),
                gated=parsed.get(spec.id, {}).get("detail") == TOPOLOGY_UNKNOWN,
                period=periods.get(row["id"]),
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
        for item in feed_rows(feeds[cells[0]["feed"]], values):
            company = "/".join(urlsplit(item.company).path.split("/")[2:3])
            first.setdefault((company, item.row_id), retrieved_at(cells[0]["retrieved"]))
    return first


def tree(
    roots: Iterable[Request],
    seen: dict[str, list[Seen]],
    store: SnapshotStore,
    specs: tuple[SurfaceSpec, ...],
    peers: tuple[int, ...],
) -> dict[str, Node]:
    """The bounded request tree that the latest retained parent captures advertise."""
    nodes: dict[str, Node] = {}
    queue: list[tuple[Request, str | None]] = [(root, None) for root in roots]
    while queue:
        request, parent = queue.pop(0)
        if (key := traversal_key(request)) in nodes:
            continue
        children: tuple[Request, ...] = ()
        gaps: tuple[str, ...] = ()
        if base := latest(seen, key):
            ref = base.ref
            record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
            body = Body(raw=store.read_body(record))
            context = request.context(record, ref.blob_sha256)
            children, gaps = advertised(request, body, context, specs, peers)
        nodes[key] = Node(request=request, parent=parent, gaps=gaps)
        queue.extend((item, key) for item in children)
    return nodes


def latest(seen: dict[str, list[Seen]], key: str) -> Seen | None:
    """The newest capture a parent's children can be read from."""
    return next((s for s in reversed(seen.get(key, [])) if s.usable or s.gated), None)


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
    nodes: dict[str, Node],
    seen: dict[str, list[Seen]],
    rows: dict[tuple[str, str], datetime],
) -> tuple[Trigger, ...]:
    """Results rows for this company whose statement obligations are not all satisfied."""
    triggers = []
    for (company, row), first in rows.items():
        if company not in (ids.nse_symbol, ids.tijori_slug):
            continue
        found = (
            obligation(spec, basis, first, nodes, seen)
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
    nodes: dict[str, Node],
    seen: dict[str, list[Seen]],
) -> Obligation | None:
    """Every required instance of one surface and basis, with its expansion parents."""
    keys = [
        key
        for key, node in nodes.items()
        if node.request.basis == basis
        and (
            node.request.spec.id == spec.id
            or node.parent is None
            and expansion_name(spec, node.request.spec.id) is not None
        )
    ]
    if not keys:
        return None

    def headed(key: str) -> bool:
        """Roots and instances with a period header compare against their own baseline."""
        return nodes[key].parent is None or any(s.period for s in seen.get(key, []))

    def since(key: str) -> datetime | None:
        """Headed instances count from the trigger; the others from their parent's refresh."""
        parent = nodes[key].parent
        return first if headed(key) or parent is None else refreshed(parent)

    def refreshed(key: str) -> datetime | None:
        """The first capture meeting the refresh rule: a newer period, or after the parent."""
        usable = [s for s in seen.get(key, []) if s.usable]
        if headed(key):
            old = max(
                (s.period for s in usable if s.retrieved_at <= first and s.period), default=date.min
            )
            usable = [s for s in usable if s.period and s.period > old]
        start = since(key)
        return next((s.retrieved_at for s in usable if start and s.retrieved_at > start), None)

    open_ = [key for key in keys if refreshed(key) is None]
    attempts = {
        key: sum(s.retrieved_at > start for s in seen.get(key, []))
        for key in open_
        if (start := since(key)) is not None
    }
    prefix = f"{SITE_NAME[spec.site]}:{spec.id}:"
    gaps = any(gap.startswith(prefix) for key in keys for gap in nodes[key].gaps)
    state = ObligationState.PENDING
    if not open_ and not gaps:
        state = ObligationState.SATISFIED
    elif open_ and all(attempts.get(key, 0) >= MAX_ATTEMPTS for key in open_):
        state = ObligationState.EXHAUSTED
    return Obligation(
        site=spec.site,
        surface=spec.id,
        basis=basis,
        attempts=max(attempts.values(), default=0),
        state=state,
        retry=tuple(key for key, count in attempts.items() if count < MAX_ATTEMPTS),
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

    def queue(nodes: dict[str, Node], pending: set[str], label: str) -> None:
        """Queue due instances; children take their parent capture's time as priority."""
        for key, node in nodes.items():
            request, hist, spec = node.request, seen.get(key, []), node.request.spec
            usable = [s for s in hist if s.usable]
            if request.basis and request.ids and request.ids.topology is None:
                spec = spec.model_copy(update={"cadence": Cadence.WEEKLY})
                usable = [s for s in hist if s.usable or s.gated]
            last = usable[-1].retrieved_at if usable else None
            retry = key in pending and not any(s.retrieved_at >= today for s in hist)
            if is_due(spec, last, now, retry):
                parent = latest(seen, node.parent) if node.parent else None
                since = parent.retrieved_at if parent else last
                due.append(request.model_copy(update={"due_since": since}))
            notes.extend(label + gap for gap in node.gaps)

    queue(tree(market_requests(specs, pool), seen, store, specs, ()), set(), "")
    for ids in universe:
        peers = tuple(o.screener_company_id for o in universe if o != ids and o.screener_company_id)
        nodes = tree(company_requests(specs, ids), seen, store, specs, peers)
        triggers = pending_triggers(ids, specs, nodes, seen, rows)
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
        pending = {k for o in obligations if o.state is ObligationState.PENDING for k in o.retry}
        queue(nodes, pending, f"{ids.nse_symbol}: ")
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
    """Capture due work in rounds, market feeds first, until nothing new is due this run."""
    tried: set[str] = set()
    reports: list[RunReport] = []
    feeds_first = True
    # An unresolved slug is retried once every run, whether or not anything else is due.
    discovery = {i.nse_symbol: i for i in covered_universe(pool, store) if i.tijori_slug is None}
    while True:
        due, notes = due_requests(pool, store, specs, now)
        batch = [r for r in due if r.url not in tried]
        batch = ([r for r in batch if r.spec.feed] if feeds_first else []) or batch
        feeds_first = False
        if not batch and not discovery:
            break
        groups: dict[str, list[Request]] = {name: [] for name in discovery}
        for request in batch:
            tried.add(request.url)
            name = request.ids.nse_symbol if request.ids else request.url
            groups.setdefault(name, []).append(request)
        for name, group in groups.items():
            company = discovery.pop(name, None) or group[0].ids
            reports.append(
                capture_company(fetcher, store, pool, values, specs, company, tuple(group))
                if company
                else capture_market(
                    fetcher, store, pool, values, specs, requests=tuple(group), today=now.date()
                )
            )
    return RunReport(
        expected=sum(r.expected for r in reports),
        completed=sum(r.completed for r in reports),
        refused=tuple(url for r in reports for url in r.refused),
        incomplete=tuple(dict.fromkeys((*(i for r in reports for i in r.incomplete), *notes))),
        stopped_sites=tuple(dict.fromkeys(site for r in reports for site in r.stopped_sites)),
    )
