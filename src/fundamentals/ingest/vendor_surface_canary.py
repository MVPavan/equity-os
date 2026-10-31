"""Runbook canaries and capture-yield drift over registered vendor evidence."""

import hashlib
import inspect
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tokenize import TokenError
from typing import Any, LiteralString
from urllib.parse import quote, urljoin, urlsplit

from lxml import html  # type: ignore[import-untyped]
from lxml.etree import ParserError  # type: ignore[import-untyped]
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.snapshot import BodyCompleteness
from fundamentals.ingest.screener_company_discovery import read_page_hooks
from fundamentals.ingest.screener_financials_tables import schedule_parents
from fundamentals.ingest.screener_session_models import ScreenerSessionError
from fundamentals.ingest.vendor_surface_capture import company_requests
from fundamentals.ingest.vendor_surface_due import covered_universe, history
from fundamentals.ingest.vendor_surface_fetch import (
    SITE_AUTHORITY,
    Fetched,
    Site,
    SiteBusy,
    SiteStopped,
    VendorFetcher,
    request_key,
)
from fundamentals.ingest.vendor_surface_market import traversal_key
from fundamentals.ingest.vendor_surface_specs import Cadence, SurfaceSpec, load_specs
from fundamentals.ingest.vendor_surface_tables import read_js_var
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import (
    USABLE,
    Outcome,
    OutcomeStatus,
    VendorValuesStore,
    register,
)

# A loss of more than half a request's rows is a strong signal of silent drift.
DROP_FACTOR = 2
NO_BASELINE = "NO_BASELINE"
ROW_COUNT_DROP = "ROW_COUNT_DROP"
MISSING_OUTCOME = "MISSING_OUTCOME"
COMPANY_OVERDUE = "COMPANY_OVERDUE"
# Operational policy (reviewed ruling, 2026-10-29): statements follow quarterly results, so a
# covered company with no usable AFTER_RESULTS capture in 92 days (one quarter plus a day) is
# overdue, whether or not a results trigger was seen.
PERIOD = {
    Cadence.DAILY: timedelta(days=1),
    Cadence.WEEKLY: timedelta(days=7),
    Cadence.AFTER_RESULTS: timedelta(days=92),
}
# Capture ids start with the fixed-width UTC retrieval timestamp (through microseconds).
_YIELD: LiteralString = """
WITH current AS (
    SELECT DISTINCT ON (capture_ref_id, surface) * FROM eqos.vendor_outcomes
    WHERE traversal_key IS NULL AND NOT starts_with(parser_version,'claims:')
        AND parser_version NOT LIKE '%%.slug.v1'
    ORDER BY capture_ref_id,surface,id DESC
), history AS (
    SELECT c.source_id, o.surface, c.request_key, o.row_count, o.recorded_at,
        lag(o.row_count) OVER (PARTITION BY c.source_id,c.request_key,o.surface,o.parser_version
            ORDER BY left(c.capture_id,23),o.id) AS previous,
        lag(o.parser_version) OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY left(c.capture_id,23),o.id) AS prior_version,
        row_number() OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY left(c.capture_id,23) DESC,o.id DESC) AS latest
    FROM current o JOIN eqos.capture_refs c ON c.id=o.capture_ref_id
    WHERE o.status=ANY(%s) AND c.source_id=ANY(%s) AND NOT starts_with(o.parser_version,'claims:')
)
SELECT source_id,surface,request_key,row_count,previous FROM history
WHERE latest=1 AND recorded_at >= %s
    AND ((previous IS NULL AND prior_version IS NOT NULL) OR row_count * %s < previous)
ORDER BY source_id,surface,request_key
"""
_MISSING: LiteralString = """
SELECT c.source_id, substr(c.surface,4), c.request_key, c.id,
    ARRAY(SELECT DISTINCT o.surface FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id
        AND NOT starts_with(o.parser_version,'claims:'))
FROM eqos.capture_refs c WHERE starts_with(c.surface,'vs.') AND c.source_id=ANY(%s)
    AND c.registered_at >= %s
ORDER BY c.source_id,c.surface,c.request_key,c.id
"""


class Drift(BaseModel):
    """A named check with enough request identity to diagnose its evidence."""

    model_config = ConfigDict(frozen=True)
    site: Site
    surface: str
    request_key: str
    check: str
    detail: str


def yield_drift(pool: ConnectionPool, since: datetime) -> tuple[Drift, ...]:
    """Compare the latest usable yield against its own version's previous yield."""
    found = []
    sites = [site.value for site in Site]
    with pool.connection() as conn:
        rows = conn.execute(
            _YIELD, ([status.value for status in USABLE], sites, since, DROP_FACTOR)
        ).fetchall()
        for site, surface, key, count, previous in rows:
            found.append(
                Drift(
                    site=site,
                    surface=surface,
                    request_key=key,
                    check=NO_BASELINE if previous is None else ROW_COUNT_DROP,
                    detail="first outcome under this parser version"
                    if previous is None
                    else f"{previous} -> {count} rows",
                )
            )
        required = {
            (spec.site, spec.id): (spec.id, *spec.sections)
            for spec in load_specs(
                Path("config/vendor_surface/surfaces.yaml"),
                Path("docs/research/vendor-surface/catalog.yaml"),
            )
        }
        for site, parent, key, capture, completed in conn.execute(
            _MISSING, (sites, since)
        ).fetchall():
            for surface in required.get((site, parent), (parent,)):
                if surface not in completed:
                    found.append(
                        Drift(
                            site=site,
                            surface=surface,
                            request_key=key,
                            check=MISSING_OUTCOME,
                            detail=f"capture {capture} has no outcome",
                        )
                    )
    return tuple(found)


def overdue(
    pool: ConnectionPool, store: SnapshotStore, specs: tuple[SurfaceSpec, ...], now: datetime
) -> tuple[Drift, ...]:
    """Covered companies' fixed requests with no usable capture within twice their cadence."""
    seen = history(pool, specs)
    return tuple(
        Drift(
            site=request.spec.site,
            surface=request.spec.id,
            request_key=request_key(request.url),
            check=COMPANY_OVERDUE,
            detail=f"no usable capture within twice its {request.spec.cadence} cadence",
        )
        for ids in covered_universe(pool, store)
        for request in company_requests(specs, ids)
        if not any(
            s.usable and s.retrieved_at > now - 2 * PERIOD[request.spec.cadence]
            for s in seen.get(traversal_key(request), [])
        )
    )


def _cls(name: str) -> str:
    """XPath predicate for one class token."""
    return f'contains(concat(" ",normalize-space(@class)," ")," {name} ")'


_PERIOD = re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}|TTM")
_TABLE = f"//table[{_cls('data-table')}]"
_SECTIONS = (
    "chart analysis peers quarters profit-loss balance-sheet cash-flow "
    "ratios insights shareholding documents"
).split()
_UTILS = re.compile(r"https://cdn-static\.screener\.in/js/(utils\.[a-f0-9]+\.js)")
_HANDLERS = ("showSchedule", "showShareholders", "showSegment")
_BASIS = '//*[@data-company-id="211"][@data-warehouse-id="6594631"][@data-consolidated="true"]'
_GROWTH = '//*[@id="profit-loss"]//table[contains(@class,"ranges-table")]//tr[td]'
_BLOCKS = "custom_ratios forensics revenuemix operationalmetrics company_filings".split()
# An event row pairs a populated event cell with populated content; a card has header and body.
_EVENT = (
    f"//tr[td[{_cls('event')}][normalize-space()] and td[{_cls('content')}][normalize-space()]]"
)
_CARD = (
    f"//*[{_cls('result_item')}][*[{_cls('result_item__header')}][normalize-space()]]"
    f"[*[{_cls('result_item__body')}][normalize-space()]]"
)
_MALFORMED = (
    ValueError,
    LookupError,
    TypeError,
    AttributeError,
    ParserError,
    ScreenerSessionError,
    TokenError,
)
Markers = Callable[[bytes], dict[str, bool]]


def _text(node: Any) -> str:
    """Normalize markup whitespace for structural markers."""
    return " ".join(node.text_content().split())


def _full(value: Any, kind: type = list) -> bool:
    """A non-empty container of the expected kind."""
    return isinstance(value, kind) and bool(value)


def _periods(tree: Any, section: str) -> list[Any]:
    """Read period headings only from a section's data table."""
    nodes = tree.xpath(f'//*[@id="{section}"]' + _TABLE + "//th")
    return [node for node in nodes if _PERIOD.fullmatch(_text(node))]


def _islands(tree: Any) -> dict[str, Any]:
    """Decode a page's JSON script islands by id."""
    nodes = tree.xpath('//script[@type="application/json"]')
    return {node.get("id"): json.loads(node.text or "null") for node in nodes}


def _aligned(table: Any, rows: Any) -> bool:
    """Every row's value list is as long as the table's non-empty report dates."""
    dates = table["report_dates"]
    return (
        bool(dates)
        and _full(rows)
        and all(_full(r["value"]) and len(r["value"]) == len(dates) for r in rows)
    )


def _envelope(raw: bytes) -> tuple[bool, Any]:
    """Read Tijori's `{data, status}` envelope, decoding string-encoded data."""
    data = json.loads(raw)
    payload = data["data"]
    ok = data.get("status", 200) == 200  # `status` absent since 2026-10-31
    return ok, json.loads(payload) if isinstance(payload, str) else payload


def _s1(raw: bytes) -> dict[str, bool]:
    """Company page: sections, session, basis, handlers, documents, growth and statements."""
    tree = html.fromstring(raw)
    hooks = read_page_hooks(tree)
    decoded = (len(schedule_parents(tree)), len(hooks.investors), len(hooks.segments))
    onclicks = tree.xpath("//*[@onclick]/@onclick")
    counts = tuple(sum(bool(re.search(rf"\b{h}\s*\(", v)) for v in onclicks) for h in _HANDLERS)
    checks = {
        "sections": tree.xpath("//section[@id]/@id") == _SECTIONS,
        "session": tree.xpath(
            'boolean(//a[@href="/user/account/"] and //form[@action="/logout/"])'
        ),
        "identity_basis": tree.xpath(f"boolean({_BASIS})"),
        "handlers": counts == decoded and counts[0] > 0 and counts[1] > 0,
        "documents": {"Announcements", "Annual reports", "Credit ratings", "Concalls"}
        <= {_text(n) for n in tree.xpath('//*[@id="documents"]//h3')},
        "growth_rows": all(len(row.xpath("./td | ./th")) == 2 for row in tree.xpath(_GROWTH)),
    }
    for section in ("quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios"):
        periods = _periods(tree, section)
        tables = tree.xpath(f'//*[@id="{section}"]' + _TABLE)
        rows = tables[0].xpath(".//tr[td]") if len(tables) == 1 else []
        cells = [row.xpath("./td")[1:] for row in rows]
        checks[section] = (
            bool(periods and cells)
            and all(len(row) == len(periods) for row in cells)
            and any(all(_text(cell) for cell in row) for row in cells)
        )
    return checks


def _s2(raw: bytes) -> dict[str, bool]:
    """Empty-shell company: a quarters table with no periods."""
    tree = html.fromstring(raw)
    shell = tree.xpath(f'boolean(//section[@id="quarters"]{_TABLE})')
    return {"empty_shell": shell and not _periods(tree, "quarters")}


def _s3(raw: bytes) -> dict[str, bool]:
    """Half-yearly company: Mar and Sep periods only."""
    tree = html.fromstring(raw)
    periods = _periods(tree, "quarters")
    headings = [_text(n) for n in tree.xpath('//*[@id="quarters"]//h2')]
    return {
        "half_yearly": any("Half Yearly Results" in heading for heading in headings),
        "months": bool(periods) and all(_text(n).split()[0] in ("Mar", "Sep") for n in periods),
    }


def _s4(raw: bytes) -> dict[str, bool]:
    """Schedule rows keyed by month periods."""
    data = json.loads(raw)
    months = (
        _full(v, dict) and all(k != "TTM" and _PERIOD.fullmatch(k) for k in v)
        for v in data.values()
    )
    return {"period_objects": _full(data, dict) and all(months)}


def _s5(raw: bytes) -> dict[str, bool]:
    """At least one holder, each a record of period-keyed holdings."""
    data = json.loads(raw)
    holders = (isinstance(v, dict) and any(_PERIOD.fullmatch(k) for k in v) for v in data.values())
    return {"holders": _full(data, dict) and all(holders)}


def _s6(raw: bytes) -> dict[str, bool]:
    """Price, moving averages and volume series."""
    series = {d["metric"] for d in json.loads(raw)["datasets"] if _full(d["values"])}
    return {"datasets": {"Price", "DMA50", "DMA200", "Volume"} <= series}


def _s7(raw: bytes) -> dict[str, bool]:
    """The utils script still names the chart, trade and segment endpoints."""
    match = re.search(r"\bgetUrls\([^)]*\)\s*{(.*?)\n\s*}", raw.decode(), re.S)
    names = set(re.findall(r"\w+", match[1])) if match else set()
    return {"getUrls": {"getChartMetric", "tradeData", "getSegments"} <= names}


def _t1(raw: bytes) -> dict[str, bool]:
    """Company page islands and blocks."""
    tree = html.fromstring(raw)
    islands = _islands(tree)
    company, ratios, custom, peers = (
        islands[key]
        for key in ("company_details_data", "ratios_table", "custom_fin_table", "peers_table_data")
    )
    return {
        "company": bool(company["company"] and company["company_id"]),
        "companyId": type(islands["companyId"]) is int and islands["companyId"] > 0,
        "ratios_table": _full(ratios)
        and all(r["name"] and r["value"] not in (None, "", [], {}) for r in ratios),
        "custom_fin_table": _full(custom)
        and all(_aligned(t, t["data"]["sub_rows"]) for t in custom),
        "ms-charts": bool(islands["ms-charts"]) and all(r["data"] for r in islands["ms-charts"]),
        "peers_table_data": isinstance(peers, list)
        and any(r.get("columns") for r in peers)
        and any(r.get("data") for r in peers),
        "corporate_actions": any(_full(v) for v in islands["corporate_actions"].values()),
        "blocks": all(tree.xpath(f'//*[@id="{key}"]') for key in _BLOCKS),
        "op_metrics": b"company_op_metrics/4290/" in raw,
        "price_chart_absent": "price_chart" not in islands,
    }


def _t2(raw: bytes) -> dict[str, bool]:
    """Fifteen financial tables with aligned statement rows."""
    tables = _islands(html.fromstring(raw))["fin_tables_data"]
    return {
        "tables": len(tables) == 15 and {"qt_c", "qt_s", "growth"} <= tables.keys(),
        "statement_rows": all(_aligned(t, t["data"]) for t in tables.values()),
    }


def _t3(raw: bytes) -> dict[str, bool]:
    """Shareholding sections, labelled chart slices, trend point series and the detailed table."""
    tree = html.fromstring(raw)
    chart, trend = (read_js_var(raw, key) for key in ("chartData", "trendData"))
    return {
        "sections": all(
            tree.xpath(f'//*[@id="{key}"]') for key in ("overview", "trend", "detailed")
        ),
        "chartData": _full(chart)
        and all(
            _full(r) and len(r) == 2 and _full(r[0], str) and isinstance(r[1], Decimal)
            for r in chart
        ),
        "trendData": _full(trend)
        and all(_full(s["data"]) and all(map(_full, s["data"])) for s in trend),
        "detailed": tree.xpath('boolean(//*[@id="detailed"]//table//tr[td])'),
    }


def _t4(raw: bytes) -> dict[str, bool]:
    """Daily prices inside the envelope."""
    envelope, payload = _envelope(raw)
    return {
        "envelope": envelope,
        "eod_price": isinstance(payload, dict) and _full(payload["eod_price"]),
    }


def _t5(raw: bytes) -> dict[str, bool]:
    """Named fund-flow series inside the envelope."""
    envelope, payload = _envelope(raw)
    series = (item["name"] and _full(item["data"], dict) for item in payload)
    return {"envelope": envelope, "fund_flow": _full(payload) and all(series)}


def _t6(raw: bytes) -> dict[str, bool]:
    """Populated timeline event rows and the next-page cursor."""
    tree = html.fromstring(raw)
    cursors = tree.xpath(f"//tr[{_cls('d-none')}]/td[1]")
    return {
        "events": tree.xpath(f"boolean({_EVENT})"),
        "cursor": any(re.fullmatch(r"\d{2}/\d{2}/\d{6}:\d{2}:\d{2,8}", _text(n)) for n in cursors),
    }


def _t7(raw: bytes) -> dict[str, bool]:
    """At least one populated result card."""
    return {"result_cards": html.fromstring(raw).xpath(f"boolean({_CARD})")}


class Canary(BaseModel):
    """A runbook request and its pure retained-body markers."""

    model_config = ConfigDict(frozen=True)
    name: str
    site: Site
    url: str
    status: int = 200
    # Redirect controls carry no body markers; `location` is a required redirect path.
    markers: Markers = lambda raw: {}
    location: str | None = None

    def check(self, fetched: Fetched, raw: bytes) -> tuple[str, ...]:
        """Fail closed on status, truncated bodies, redirect target and malformed markers."""
        record = fetched.record
        if record.http_status != self.status:
            return (self.name + ".http_status",)
        if record.effective_body_completeness != BodyCompleteness.COMPLETE:
            return (self.name + ".body_completeness",)
        if self.location:
            try:
                target = urlsplit(urljoin(fetched.url, fetched.location or ""))
            except ValueError:
                return (self.name + ".location",)
            if (target.netloc, target.path) != (urlsplit(fetched.url).netloc, self.location):
                return (self.name + ".location",)
        try:
            return tuple(f"{self.name}.{key}" for key, ok in self.markers(raw).items() if not ok)
        except _MALFORMED:
            return (self.name + ".structure",)


def _canary(
    name: str, path: str, markers: Markers | None = None, location: str | None = None
) -> Canary:
    """Bind a runbook row; S rows are Screener, T rows Tijori, and no markers means a redirect."""
    site = Site.SCREENER if name.startswith("S") else Site.TIJORI
    url = f"https://{SITE_AUTHORITY[site]}{path}"
    if markers is None:
        return Canary(name=name, site=site, url=url, status=302, location=location)
    return Canary(name=name, site=site, url=url, markers=markers)


CANARIES: tuple[Canary, ...] = (
    _canary("S1", "/company/APARINDS/consolidated/", _s1),
    _canary("S2", "/company/NETWEB/consolidated/", _s2),
    _canary("S3", "/company/ANONDITA/", _s3),
    _canary(
        "S4", "/api/company/211/schedules/?parent={parent}&section=quarters&consolidated=true", _s4
    ),
    _canary("S5", "/api/3/211/investors/promoters/quarterly/", _s5),
    _canary(
        "S6", "/api/company/211/chart/?q=Price-DMA50-DMA200-Volume&days=365&consolidated=true", _s6
    ),
    _canary("S7", "/static/js/{utils}", _s7),
    _canary("S8", "/company/actions/211/"),
    _canary("T1", "/company/apar-industries-limited/", _t1),
    _canary("T2", "/company/apar-industries-limited/financials/", _t2),
    _canary("T3", "/company/apar-industries-limited/shareholding/", _t3),
    _canary("T4", "/api/v1/ind/chartdata/4290/price/", _t4),
    _canary("T5", "/api/v1/ind/fund_flow_analysis_data/4290/", _t5),
    _canary("T6", "/timeline/company/?company_id=4290&timestamp=0", _t6),
    _canary(
        "T7",
        "/results/quarterly-results/api/?page=2&sort_by=latest&mcap=&timeline_type=all"
        "&sectors=&company_ids=&daterange={dates}",
        _t7,
    ),
)


def _dependencies(raw: bytes) -> dict[str, str]:
    """Read S4's schedule parent and S7's utils script, each only when its own hook is valid."""
    tree = html.fromstring(raw)
    parents = [
        match[1]
        for value in tree.xpath('//*[@id="quarters"]//*[@onclick]/@onclick')
        for match in re.findall(r"showSchedule\s*\(\s*(['\"])(.*?)\1", value)
    ]
    utils = [
        match[1] for src in tree.xpath("//script[@src]/@src") if (match := _UTILS.fullmatch(src))
    ]
    return ({"parent": quote(parents[0], safe="")} if parents else {}) | (
        {"utils": utils[0]} if len(utils) == 1 else {}
    )


def _drift(canary: Canary, key: str, check: str, detail: str) -> Drift:
    """Name one failed canary check against its request."""
    return Drift(site=canary.site, surface=canary.name, request_key=key, check=check, detail=detail)


def run_canaries(
    fetcher: VendorFetcher, store: SnapshotStore, pool: ConnectionPool
) -> tuple[Drift, ...]:
    """Fetch fresh, register every response, record checks, then inspect capture yield."""
    found: list[Drift] = []
    end = datetime.now(UTC)
    variables = {
        "dates": (end - timedelta(days=7)).strftime("%m/%d/%Y") + "," + end.strftime("%m/%d/%Y")
    }
    values = VendorValuesStore(pool)
    for canary in CANARIES:
        stopped, url = False, canary.url
        try:
            url = canary.url.format_map(variables)
            fetched = fetcher.get(canary.site, canary.name, url)
        except (KeyError, SiteStopped, SiteBusy, ValueError) as error:
            if not isinstance(error, SiteStopped) or error.fetched is None:
                # A missing S1 hook leaves a placeholder unformatted.
                check = ".dependency" if isinstance(error, KeyError) else ".fetch"
                found.append(
                    _drift(canary, request_key(url), canary.name + check, type(error).__name__)
                )
                continue
            fetched, stopped = error.fetched, True
        try:
            ref = register(pool, fetched)
            with pool.connection() as conn:
                [address] = conn.execute(
                    "SELECT url, location FROM eqos.capture_addresses WHERE capture_ref_id=%s",
                    (ref.capture_ref_id,),
                ).fetchall()
            registered = fetched.model_copy(update={"url": address[0], "location": address[1]})
            raw = (
                store.read_body(fetched.record)
                if fetched.record.effective_body_completeness == BodyCompleteness.COMPLETE
                else b""
            )
            # A stop is a named refusal whatever status the canary expected.
            checks = (canary.name + ".refused",) if stopped else canary.check(registered, raw)
            if canary.name == "S1" and raw:
                try:
                    variables |= _dependencies(raw)
                except _MALFORMED:
                    pass
            values.record(
                ref,
                Outcome(
                    surface=canary.name,
                    parser_version=f"canary.{canary.name}.v1",
                    parser_sha256=hashlib.sha256(
                        inspect.getsource(canary.markers).encode()
                    ).hexdigest(),
                    status=OutcomeStatus.UNUSABLE
                    if stopped
                    else OutcomeStatus.FAILED
                    if checks
                    else OutcomeStatus.OK,
                    symbol=None,
                    detail=", ".join(checks) if checks else None,
                ),
                row_count=0,
            )
            key = fetched.record.request.request_key
            detail = "site stopped" if stopped else "runbook marker failed"
            found.extend(_drift(canary, key, check, detail) for check in checks)
        finally:
            if stopped:
                fetcher.stop_dir.mkdir(parents=True, exist_ok=True)
                (fetcher.stop_dir / f"STOP-{canary.site}").write_text("canary refusal\n")
    return tuple(found) + yield_drift(pool, datetime.min.replace(tzinfo=UTC))
