"""Runbook canaries and capture-yield drift over registered vendor evidence."""

import hashlib
import json
import re
import tokenize
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, LiteralString
from urllib.parse import quote

from lxml import html  # type: ignore[import-untyped]
from lxml.etree import ParserError  # type: ignore[import-untyped]
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.snapshot import BodyCompleteness, CaptureRecord
from fundamentals.ingest.screener_company_discovery import read_page_hooks
from fundamentals.ingest.screener_financials_tables import schedule_parents
from fundamentals.ingest.screener_session_models import ScreenerSessionError
from fundamentals.ingest.vendor_surface_fetch import (
    SITE_AUTHORITY,
    Site,
    SiteBusy,
    SiteStopped,
    VendorFetcher,
    request_key,
)
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
# Capture ids start with the fixed-width UTC retrieval timestamp (through microseconds).
_YIELD: LiteralString = """
WITH history AS (
    SELECT c.source_id, o.surface, c.request_key, o.row_count, o.recorded_at,
        lag(o.row_count) OVER (PARTITION BY c.source_id,c.request_key,o.surface,o.parser_version
            ORDER BY left(c.capture_id,23),o.id) AS previous,
        lag(o.parser_version) OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY left(c.capture_id,23),o.id) AS prior_version,
        row_number() OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY left(c.capture_id,23) DESC,o.id DESC) AS latest
    FROM eqos.vendor_outcomes o JOIN eqos.capture_refs c ON c.id=o.capture_ref_id
    WHERE o.status=ANY(%s) AND c.source_id=ANY(%s)
)
SELECT source_id,surface,request_key,row_count,previous FROM history
WHERE latest=1 AND recorded_at >= %s
    AND ((previous IS NULL AND prior_version IS NOT NULL) OR row_count * %s < previous)
ORDER BY source_id,surface,request_key
"""
_MISSING: LiteralString = """
SELECT c.source_id, substr(c.surface,4), c.request_key, c.id
FROM eqos.capture_refs c WHERE starts_with(c.surface,'vs.') AND c.source_id=ANY(%s)
    AND c.registered_at >= %s AND NOT EXISTS (
        SELECT 1 FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id)
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
        for site, surface, key, capture in conn.execute(_MISSING, (sites, since)).fetchall():
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


_PERIOD = re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}|TTM")
_TABLE = '//table[contains(concat(" ",normalize-space(@class)," ")," data-table ")]'
_SECTIONS = (
    "chart analysis peers quarters profit-loss balance-sheet cash-flow "
    "ratios insights shareholding documents"
).split()


def _text(node: Any) -> str:
    """Normalize markup whitespace for structural markers."""
    return " ".join(node.text_content().split())


def _periods(tree: Any, section: str) -> list[Any]:
    """Read period headings only from a section's data table."""
    return [
        node
        for node in tree.xpath(f'//*[@id="{section}"]' + _TABLE + "//th")
        if _PERIOD.fullmatch(_text(node))
    ]


def _markers(name: str, raw: bytes) -> dict[str, bool]:
    """Evaluate the runbook's structural markers without reading financial values."""
    if name in ("S4", "S5", "S6", "T4", "T5"):
        data = json.loads(raw)
        if name == "S4":
            return {
                "period_objects": bool(data)
                and isinstance(data, dict)
                and all(
                    isinstance(value, dict)
                    and bool(value)
                    and all(key != "TTM" and _PERIOD.fullmatch(key) for key in value)
                    for value in data.values()
                )
            }
        if name == "S5":
            return {
                "holders": isinstance(data, dict)
                and bool(data)
                and all(isinstance(value, dict) and value for value in data.values())
            }
        if name == "S6":
            datasets = data["datasets"]
            return {
                "datasets": all(
                    any(
                        d["metric"] == label and isinstance(d["values"], list) and d["values"]
                        for d in datasets
                    )
                    for label in ("Price", "DMA50", "DMA200", "Volume")
                )
            }
        payload = data["data"]
        payload = json.loads(payload) if isinstance(payload, str) else payload
        return {
            "envelope": data["status"] == 200,
            "eod_price" if name == "T4" else "fund_flow": isinstance(payload, dict)
            and isinstance(payload["eod_price"], list)
            and bool(payload["eod_price"])
            if name == "T4"
            else isinstance(payload, list)
            and bool(payload)
            and all(
                item["name"] and isinstance(item["data"], dict) and item["data"] for item in payload
            ),
        }
    tree = html.fromstring(raw)
    if name == "S1":
        hooks = read_page_hooks(tree)
        decoded = (len(schedule_parents(tree)), len(hooks.investors), len(hooks.segments))
        counts = tuple(
            sum(
                bool(re.search(r"\b" + handler + r"\s*\(", value))
                for value in tree.xpath("//*[@onclick]/@onclick")
            )
            for handler in ("showSchedule", "showShareholders", "showSegment")
        )
        checks = {
            "sections": tree.xpath("//section[@id]/@id") == _SECTIONS,
            "session": bool(tree.xpath('//a[@href="/user/account/"]'))
            and bool(tree.xpath('//form[@action="/logout/"]')),
            "identity_basis": bool(
                tree.xpath(
                    '//*[@data-company-id="211" and '
                    '@data-warehouse-id="6594631" and @data-consolidated="true"]'
                )
            ),
            "handlers": counts == decoded and counts[0] > 0 and counts[1] > 0,
            "documents": {"Announcements", "Annual reports", "Credit ratings", "Concalls"}
            <= {_text(n) for n in tree.xpath('//*[@id="documents"]//h3')},
            "growth_rows": all(
                len(row.xpath("./td | ./th")) == 2
                for row in tree.xpath(
                    '//*[@id="profit-loss"]//table[contains(@class,"ranges-table")]//tr[td]'
                )
            ),
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
    if name == "S2":
        return {
            "empty_shell": bool(tree.xpath('//section[@id="quarters"]' + _TABLE))
            and not _periods(tree, "quarters")
        }
    if name == "S3":
        periods = _periods(tree, "quarters")
        return {
            "half_yearly": any(
                "Half Yearly Results" in _text(n) for n in tree.xpath('//*[@id="quarters"]//h2')
            ),
            "months": bool(periods) and all(_text(n).split()[0] in ("Mar", "Sep") for n in periods),
        }
    if name == "S7":
        match = re.search(r"\bgetUrls\([^)]*\)\s*{(.*?)\n\s*}", raw.decode(), re.S)
        urls = match[1] if match else ""
        return {
            "getUrls": all(
                re.search(r"\b" + marker + r"\b", urls)
                for marker in ("getChartMetric", "tradeData", "getSegments")
            )
        }
    islands = {
        node.get("id"): json.loads(node.text or "null")
        for node in tree.xpath('//script[@type="application/json"]')
    }
    if name == "T1":
        custom = islands["custom_fin_table"]
        peers = islands["peers_table_data"]
        return {
            "company": bool(islands["company_details_data"]["company"])
            and bool(islands["company_details_data"]["company_id"]),
            "companyId": type(islands["companyId"]) is int and islands["companyId"] > 0,
            "ratios_table": isinstance(islands["ratios_table"], list)
            and bool(islands["ratios_table"])
            and all(
                row["name"] and row["value"] not in (None, "", [], {})
                for row in islands["ratios_table"]
            ),
            "custom_fin_table": isinstance(custom, list)
            and bool(custom)
            and all(
                table["report_dates"]
                and table["data"]["sub_rows"]
                and all(
                    isinstance(row["value"], list)
                    and len(row["value"]) == len(table["report_dates"])
                    for row in table["data"]["sub_rows"]
                )
                for table in custom
            ),
            "ms-charts": bool(islands["ms-charts"])
            and all(row["data"] for row in islands["ms-charts"]),
            "peers_table_data": isinstance(peers, list)
            and any(row.get("columns") for row in peers)
            and any(row.get("data") for row in peers),
            "corporate_actions": any(
                isinstance(v, list) and v for v in islands["corporate_actions"].values()
            ),
            "blocks": all(
                tree.xpath(f'//*[@id="{key}"]')
                for key in (
                    "custom_ratios",
                    "forensics",
                    "revenuemix",
                    "operationalmetrics",
                    "company_filings",
                )
            ),
            "op_metrics": b"company_op_metrics/4290/" in raw,
            "price_chart_absent": "price_chart" not in islands,
        }
    if name == "T2":
        tables = islands["fin_tables_data"]
        return {
            "tables": len(tables) == 15 and {"qt_c", "qt_s", "growth"} <= tables.keys(),
            "statement_rows": all(
                table["report_dates"]
                and table["data"]
                and all(
                    isinstance(row["value"], list)
                    and bool(row["value"])
                    and len(row["value"]) == len(table["report_dates"])
                    for row in table["data"]
                )
                for table in tables.values()
            ),
        }
    if name == "T3":
        chart, trend = (read_js_var(raw, key) for key in ("chartData", "trendData"))
        return {
            "sections": all(
                tree.xpath(f'//*[@id="{key}"]') for key in ("overview", "trend", "detailed")
            ),
            "chartData": isinstance(chart, list) and len(chart) >= 2,
            "trendData": isinstance(trend, list)
            and bool(trend)
            and all(row["data"] for row in trend),
            "detailed": bool(tree.xpath('//*[@id="detailed"]//table//tr[td]')),
        }
    if name == "T6":
        return {
            "events": bool(tree.xpath('//*[contains(concat(" ",@class," ")," event ")]')),
            "cursor": any(
                re.fullmatch(r"\d{2}/\d{2}/\d{6}:\d{2}:\d{2,8}", _text(n))
                for n in tree.xpath('//tr[contains(concat(" ",@class," ")," d-none ")]/td[1]')
            ),
        }
    return {
        "result_cards": bool(tree.xpath('//*[contains(concat(" ",@class," ")," result_item ")]'))
    }


def _check(name: str, record: CaptureRecord, raw: bytes) -> tuple[str, ...]:
    """Fail closed on status, truncated bodies and missing or malformed markers."""
    if record.http_status != (302 if name in ("S8", "T8") else 200):
        return (name + ".http_status",)
    if record.effective_body_completeness != BodyCompleteness.COMPLETE:
        return (name + ".body_completeness",)
    if name in ("S8", "T8"):
        return ()
    try:
        return tuple(name + "." + key for key, passed in _markers(name, raw).items() if not passed)
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        ParserError,
        ScreenerSessionError,
        tokenize.TokenError,
        SyntaxError,
    ):
        return (name + ".structure",)


class Canary(BaseModel):
    """A runbook request and its pure retained-body check."""

    model_config = ConfigDict(frozen=True)
    name: str
    site: Site
    url: str
    check: Callable[[CaptureRecord, bytes], tuple[str, ...]]


CANARIES: tuple[Canary, ...] = tuple(
    Canary(
        name=name,
        site=site,
        url=f"https://{SITE_AUTHORITY[site]}{path}",
        check=partial(_check, name),
    )
    for site, name, path in (
        (Site.SCREENER, "S1", "/company/APARINDS/consolidated/"),
        (Site.SCREENER, "S2", "/company/NETWEB/consolidated/"),
        (Site.SCREENER, "S3", "/company/ANONDITA/"),
        (
            Site.SCREENER,
            "S4",
            "/api/company/211/schedules/?parent={parent}&section=quarters&consolidated=true",
        ),
        (Site.SCREENER, "S5", "/api/3/211/investors/promoters/quarterly/"),
        (
            Site.SCREENER,
            "S6",
            "/api/company/211/chart/?q=Price-DMA50-DMA200-Volume&days=365&consolidated=true",
        ),
        (Site.SCREENER, "S7", "/static/js/{utils}"),
        (Site.SCREENER, "S8", "/company/actions/211/"),
        (Site.TIJORI, "T1", "/company/apar-industries-limited/"),
        (Site.TIJORI, "T2", "/company/apar-industries-limited/financials/"),
        (Site.TIJORI, "T3", "/company/apar-industries-limited/shareholding/"),
        (Site.TIJORI, "T4", "/api/v1/ind/chartdata/4290/price/"),
        (Site.TIJORI, "T5", "/api/v1/ind/fund_flow_analysis_data/4290/"),
        (Site.TIJORI, "T6", "/timeline/company/?company_id=4290&timestamp=0"),
        (
            Site.TIJORI,
            "T7",
            "/results/quarterly-results/api/?page=2&sort_by=latest&mcap=&timeline_type=all&sectors=&company_ids=&daterange={dates}",
        ),
        (Site.TIJORI, "T8", "/"),
    )
)


def run_canaries(
    fetcher: VendorFetcher, store: SnapshotStore, pool: ConnectionPool
) -> tuple[Drift, ...]:
    """Fetch fresh, register every response, record checks, then inspect capture yield."""
    found: list[Drift] = []
    end = datetime.now(UTC)
    variables: dict[str, str] = {
        "dates": (end - timedelta(days=7)).strftime("%m/%d/%Y") + "," + end.strftime("%m/%d/%Y")
    }
    values = VendorValuesStore(pool)
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for canary in CANARIES:
        url = canary.url
        try:
            url = url.format_map(variables)
        except KeyError:
            found.append(
                Drift(
                    site=canary.site,
                    surface=canary.name,
                    request_key=request_key(url),
                    check=canary.name + ".dependency",
                    detail="S1 hook unavailable",
                )
            )
            continue
        stopped = False
        fetched = None
        try:
            fetched = fetcher.get(canary.site, canary.name, url)
        except (SiteStopped, SiteBusy, ValueError) as error:
            fetched = error.fetched if isinstance(error, SiteStopped) else None
            stopped = isinstance(error, SiteStopped)
            if fetched is None:
                found.append(
                    Drift(
                        site=canary.site,
                        surface=canary.name,
                        request_key=request_key(url),
                        check=canary.name + ".fetch",
                        detail=type(error).__name__,
                    )
                )
                continue
        try:
            ref = register(pool, fetched)
            raw = (
                store.read_body(fetched.record)
                if fetched.record.effective_body_completeness == BodyCompleteness.COMPLETE
                else b""
            )
            checks = canary.check(fetched.record, raw)
            if canary.name == "T8" and fetched.location != "/dashboard/":
                checks += ("T8.location",)
            if canary.name == "S1" and raw:
                tree = html.fromstring(raw)
                parents = tree.xpath('//*[@id="quarters"]//*[@onclick]/@onclick')
                matches = [
                    re.search(r"showSchedule\s*\(\s*(['\"])(.*?)\1", value) for value in parents
                ]
                parent = next((match[2] for match in matches if match), None)
                if parent is not None:
                    variables["parent"] = quote(parent, safe="")
                scripts = [
                    re.fullmatch(r"https://cdn-static\.screener\.in/js/(utils\.[a-f0-9]+\.js)", src)
                    for src in tree.xpath("//script[@src]/@src")
                ]
                utils = [match[1] for match in scripts if match]
                if len(utils) == 1:
                    variables["utils"] = utils[0]
            values.record(
                ref,
                Outcome(
                    surface=canary.name,
                    parser_version=f"canary.{canary.name}.v1",
                    parser_sha256=digest,
                    status=OutcomeStatus.FAILED if checks else OutcomeStatus.OK,
                    symbol=None,
                    detail=", ".join(checks) if checks else None,
                ),
                row_count=0,
            )
            found.extend(
                Drift(
                    site=canary.site,
                    surface=canary.name,
                    request_key=fetched.record.request.request_key,
                    check=check,
                    detail="runbook marker failed",
                )
                for check in checks
            )
        finally:
            if stopped:
                fetcher.stop_dir.mkdir(parents=True, exist_ok=True)
                (fetcher.stop_dir / f"STOP-{canary.site}").write_text("canary refusal\n")
    return tuple(found) + yield_drift(pool, datetime.min.replace(tzinfo=UTC))
