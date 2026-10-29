"""G0 adapters exercised through the registry on retained subscriber responses."""

import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr
from vendor_surface_support import INDEX

from fundamentals.ingest.screener_company_models import InvestorHook, Periodicity, SegmentHook
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_financials_tables import read_section
from fundamentals.ingest.screener_session_models import Basis, BasisTopology
from fundamentals.ingest.screener_shareholding import read_shareholding_table
from fundamentals.ingest.vendor_surface_capture import Request, capture
from fundamentals.ingest.vendor_surface_fetch import Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import PARSERS, Body, CompanyIds, ParseContext
from fundamentals.ingest.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

IDS = {
    "APARINDS": (211, 2446, 6594631, "apar-industries-limited", 4290),
    "ANONDITA": (1285614, 142778403, 142927483, "anondita-medicare-ltd", 58631),
    "RELIANCE": (2726, 811, 6598251, "reliance-industries-limited", 242),
    "NETWEB": (1284419, 104235517, None, "netweb-technologies-india-ltd", 0),
    "HDFCBANK": (1298, 1789, 6596237, "hdfc-bank-limited", 129),
}


def retained(site, surface, symbol=None, basis="standalone"):
    rows = (
        json.loads(INDEX.with_name("kinds-index.json").read_text())
        if symbol
        else json.loads(INDEX.read_text())
    )
    row = next(
        r
        for r in rows
        if r["site"] == site
        and r["id"] == surface
        and r["kind"] == "response"
        and r["status"] == 200
        and (symbol is None or r["symbol"] == symbol and (r["basis"] in (basis, "na")))
    )
    raw = Path(row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    symbol = symbol or (
        "HDFCBANK"
        if surface in ("peers-api", "company-timeline-api")
        else "RELIANCE"
        if site == "tijori" or surface in ("segments-api", "investors-api")
        else "HDFCBANK"
        if surface == "company-search-api"
        else "APARINDS"
    )
    company, standalone, consolidated, slug, tijori = IDS[symbol]
    ids = CompanyIds(
        nse_symbol=symbol,
        isin="",
        tijori_slug=slug,
        tijori_company_id=tijori,
        screener_company_id=company,
        topology=BasisTopology(
            standalone_warehouse_id=standalone, consolidated_warehouse_id=consolidated
        ),
    )
    return Body(raw=raw), ParseContext(
        ids=ids,
        basis=Basis(basis),
        url=row["url"],
        retrieved_at=datetime(2026, 10, 28, tzinfo=UTC),
        body_sha256=row["sha256"],
        capture_id="retained-g0",
    )


def parse(site, surface, body, context):
    return PARSERS[Site.SCREENER if site == "screener" else Site.TIJORI, surface].parse(
        body, context
    )


@pytest.mark.parametrize("symbol", ["APARINDS", "ANONDITA"])
@pytest.mark.parametrize(
    "surface",
    [
        "section-quarters",
        "section-profit-loss",
        "section-balance-sheet",
        "section-cash-flow",
        "section-ratios",
        "section-shareholding",
    ],
)
def test_statement_readers(surface, symbol):
    body, context = retained("screener", "company-page", symbol)
    values = parse("screener", surface, body, context)
    assert values and any(cell.value is not None for cell in values)
    assert all(cell.basis == "standalone" for cell in values)
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)
    if symbol == "APARINDS" and surface == "section-quarters":
        assert values[0].value == Decimal("3500")
        assert values[1].value == Decimal("3644")


@pytest.mark.parametrize(
    "surface",
    [
        "quick-ratios-api",
        "peers-api",
        "related-party",
        "schedules-api",
        "investors-api",
        "segments-api",
    ],
)
def test_fragment_readers(surface):
    body, context = retained("screener", surface)
    if surface == "peers-api":
        context = context.model_copy(update={"basis": Basis.CONSOLIDATED})
    if surface in ("schedules-api", "segments-api", "investors-api"):
        basis = "consolidated" if surface != "schedules-api" else "standalone"
        page, page_context = retained("screener", "company-page", context.ids.nse_symbol, basis)
        inputs = dict(
            source_id="screener-subscriber",
            file_sha256=page_context.body_sha256,
            retrieved_at=context.retrieved_at,
        )
        if surface == "investors-api":
            parent = dict(
                hook=InvestorHook(
                    bucket="promoters", periodicity=Periodicity.QUARTERLY, row_label="Promoters"
                ),
                table=read_shareholding_table(page.tree(), Periodicity.QUARTERLY, **inputs),
            )
        else:
            section = Section.CASH_FLOW if surface == "schedules-api" else Section.PROFIT_LOSS
            table = read_section(page.tree(), section, **inputs)
            parent = (
                dict(
                    section=section,
                    parent="Cash from Operating Activity",
                    periods=table.periods,
                    page_row=next(
                        r for r in table.rows if r.schedule_parent == "Cash from Operating Activity"
                    ),
                )
                if surface == "schedules-api"
                else dict(
                    hook=SegmentHook(section="profit-loss", segment_type="1"), page_section=table
                )
            )
        context = context.model_copy(update={"parent": parent, "basis": Basis(basis)})
    values = parse("screener", surface, body, context)
    assert values
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)


@pytest.mark.parametrize("symbol", ["APARINDS", "ANONDITA"])
@pytest.mark.parametrize(
    "surface",
    [
        "company-overview",
        "overview-custom-ratios",
        "overview-custom-financials",
        "overview-forensics",
        "overview-marketshare",
        "overview-revenuemix",
        "overview-competitors",
        "overview-corporateactions",
        "company-financials",
        "financials-growth-table",
        "financials-balance-sheet",
        "financials-profit-and-loss",
        "financials-cash-flow",
        "financials-ratios",
        "financials-quarterly-results",
        "company-shareholding",
        "shareholding-detailed",
    ],
)
def test_tijori_page_readers(surface, symbol):
    parent = (
        "company-overview"
        if surface in ("company-overview",) or surface.startswith("overview-")
        else "company-shareholding"
        if surface in ("company-shareholding", "shareholding-detailed")
        else "company-financials"
    )
    body, context = retained("tijori", parent, symbol)
    if symbol == "ANONDITA" and surface in (
        "overview-marketshare",
        "company-shareholding",
        "shareholding-detailed",
    ):
        from fundamentals.ingest.vendor_surface_readers import ReaderError

        reason = "not available" if surface == "overview-marketshare" else "repeats node id"
        with pytest.raises(ReaderError, match=reason):
            parse("tijori", surface, body, context)
        return
    values = parse("tijori", surface, body, context.model_copy(update={"basis": None}))
    assert values
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)
    if symbol == "ANONDITA" and surface == "financials-quarterly-results":
        assert any(v.padded and v.value == 0 for v in values)


@pytest.mark.parametrize(
    "surface",
    [
        "fund-flow-api",
        "cash-flow-waterfall-api",
        "balance-sheet-snapshot-api",
        "op-metrics-api",
        "company-timeline-api",
        "quarterly-results",
        "upcoming-events",
    ],
)
def test_tijori_api_readers(surface):
    body, context = retained("tijori", surface)
    context = context.model_copy(update={"parent": {"metric_id": 126}, "basis": None})
    assert parse("tijori", surface, body, context)


class Opener(OpenerDirector):
    def __init__(self, raw, status):
        super().__init__()
        self.raw, self.status = raw, status

    def open(self, request, timeout):
        return HTTPError(request.full_url, self.status, "retained", Message(), io.BytesIO(self.raw))


class Lock:
    def acquire(self, site):
        return True


def record(pg_db, tmp_path, site, surface, body, context, status=200):
    store = SnapshotStore(tmp_path)
    session = SiteSession(site=site, session_cookie=SecretStr("synthetic"), cookie_name="sessionid")
    fetcher = VendorFetcher(
        store, {site: session}, Opener(body.raw, status), tmp_path, Lock(), spacing_seconds=0
    )
    with pg_db.runtime_pool() as pool:
        capture(
            fetcher,
            store,
            pool,
            VendorValuesStore(pool),
            Request(
                spec=SurfaceSpec(
                    site=site,
                    id=surface,
                    scope=Scope.COMPANY,
                    path="/fixture/",
                    group=ParseGroup.READER,
                    cadence=Cadence.DAILY,
                ),
                url=context.url,
                ids=context.ids,
                basis=context.basis,
                parent=context.parent,
                due_since=None,
            ),
        )
        with pool.connection() as conn:
            return conn.execute(
                "SELECT status,detail,parser_version FROM eqos.vendor_outcomes ORDER BY id"
            ).fetchall()


@pytest.mark.pg
def test_namespaced_search_outcomes(pg_db, tmp_path):
    for site in (Site.SCREENER, Site.TIJORI):
        body, context = retained(
            "screener" if site == Site.SCREENER else "tijori", "company-search-api"
        )
        outcomes = record(
            pg_db,
            tmp_path,
            site,
            "company-search-api",
            body,
            context.model_copy(update={"basis": None}),
        )
    assert [(s, v) for s, _, v in outcomes] == [
        ("OK", "screener:company-search-api.reader.v1"),
        ("FAILED", "tijori:company-search-api.reader.v1"),
    ]
    assert (Site.TIJORI, "filter-advanced-search-api") not in PARSERS
    assert (Site.TIJORI, "overview-company-timeline-sidepanel") not in PARSERS


@pytest.mark.pg
@pytest.mark.parametrize("case", ["empty", "missing", "unreadable"])
def test_recorded_reader_states(pg_db, tmp_path, case):
    if case == "empty":
        body, context = retained("screener", "company-page", "NETWEB", "consolidated")
        site, surface, expected = Site.SCREENER, "company-consolidated-empty-shell", "EMPTY"
    elif case == "missing":
        body, context = retained("tijori", "company-overview", "APARINDS")
        context = context.model_copy(
            update={
                "ids": context.ids.model_copy(update={"tijori_company_id": None}),
                "basis": None,
            }
        )
        site, surface, expected = Site.TIJORI, "company-overview", "FAILED"
    else:
        body, context = retained("screener", "company-page", "APARINDS")
        root = body.tree()
        cell = root.xpath(
            "//section[@id='quarters']//table[contains(@class,'data-table')]//tr[td]/td[2]"
        )[0]
        cell.clear()
        cell.text = "unreadable"
        from lxml import etree

        body = Body(raw=etree.tostring(root))
        site, surface, expected = Site.SCREENER, "section-quarters", "PARTIAL"
    outcomes = record(pg_db, tmp_path, site, surface, body, context)
    assert outcomes[0][0] == expected
    if case == "missing":
        assert "company id required" in outcomes[0][1]


def test_cell_addresses_survive_label_changes():
    from lxml import etree

    body, context = retained("screener", "company-page", "APARINDS")
    before = parse("screener", "section-quarters", body, context)
    label = body.tree().xpath("//section[@id='quarters']//tr[td]/td[1]")[0]
    label.clear()
    label.text = "Renamed row"
    after = parse("screener", "section-quarters", Body(raw=etree.tostring(body.tree())), context)
    assert [(v.table_key, v.row_index, v.column_index) for v in before] == [
        (v.table_key, v.row_index, v.column_index) for v in after
    ]
    assert before[0].locator.startswith("#quarters:data-table/")
    assert before[0].row_label != after[0].row_label


@pytest.mark.pg
@pytest.mark.parametrize(
    "surface",
    [
        "financials-balance-sheet-snapshot",
        "financials-fundflow-analysis",
        "financials-cash-flow-analysis",
    ],
)
def test_widget_shells_fail_with_reader_detail(pg_db, tmp_path, surface):
    body, context = retained("tijori", "company-financials", "APARINDS")
    outcomes = record(
        pg_db, tmp_path, Site.TIJORI, surface, body, context.model_copy(update={"basis": None})
    )
    assert outcomes[0][0:2] == ("FAILED", "ReaderError: no reader")


@pytest.mark.pg
def test_corporate_action_modal_requires_retained_200(pg_db, tmp_path):
    rows = [r for r in json.loads(INDEX.read_text()) if r["id"] == "corporate-actions-modal"]
    assert not any(r["status"] == 200 and r["kind"] == "response" for r in rows)
    _, context = retained("screener", "company-page", "HDFCBANK", "consolidated")
    context = context.model_copy(update={"url": rows[0]["url"]})
    outcomes = record(
        pg_db,
        tmp_path,
        Site.SCREENER,
        "corporate-actions-modal",
        Body(raw=b""),
        context,
        status=302,
    )
    assert outcomes[0][0] == "UNUSABLE"


def test_growth_rows_keep_source_positions():
    body, context = retained("screener", "company-page", "APARINDS")
    values = parse("screener", "section-profit-loss", body, context)
    growth = [v for v in values if "ranges-table" in v.table_key]
    assert growth
    assert all(v.column_index == 0 for v in growth)
    assert growth[0].row_index == 1
