"""Thin retained-body adapters around the existing subscriber readers."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

from fundamentals.entity.verification import screener_candidate, tijori_candidate
from fundamentals.ingest import screener_company_artifacts as sc
from fundamentals.ingest import screener_company_fragments as fragments
from fundamentals.ingest import screener_financials_models as sf
from fundamentals.ingest import tijori_analysis_models as ta
from fundamentals.ingest import tijori_events_models as te
from fundamentals.ingest import tijori_overview_models as to
from fundamentals.ingest.screener_company_models import Binding, Periodicity
from fundamentals.ingest.screener_financials_models import IdentityStrength, Section
from fundamentals.ingest.screener_financials_nested import read_nested_schedule
from fundamentals.ingest.screener_financials_schedules import read_schedule
from fundamentals.ingest.screener_financials_tables import read_growth_section, read_section
from fundamentals.ingest.screener_segments import read_segments
from fundamentals.ingest.screener_session_models import PageOutcome
from fundamentals.ingest.screener_session_page import parse_document, read_page_evidence
from fundamentals.ingest.screener_shareholding import read_investor_bucket, read_shareholding_table
from fundamentals.ingest.tijori_analysis import build_tijori_analysis
from fundamentals.ingest.tijori_analysis_models import TijoriAnalysisSection
from fundamentals.ingest.tijori_events import build_tijori_events
from fundamentals.ingest.tijori_events_models import TijoriEventsSurface
from fundamentals.ingest.tijori_overview import build_tijori_overview
from fundamentals.ingest.tijori_overview_models import (
    TijoriOverviewSection,
)
from fundamentals.ingest.tijori_shareholding import (
    TijoriShareholding,
    TijoriShareholdingRow,
    build_tijori_shareholding,
)
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriTable, TijoriTableCell, TijoriTableRow
from fundamentals.ingest.vendor_surface_cells import measurement
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext, Parser

SCREENER_SURFACES = tuple(
    "company-consolidated-empty-shell section-quarters section-profit-loss "
    "section-balance-sheet section-cash-flow section-ratios "
    "section-shareholding schedules-api investors-api "
    "segments-api quick-ratios-api peers-api "
    "related-party corporate-actions-modal company-search-api ".split()
)
OVERVIEW = {
    "company-overview": None,
    "overview-custom-ratios": TijoriOverviewSection.RATIOS,
    "overview-custom-financials": TijoriOverviewSection.CUSTOM_FINANCIALS,
    "overview-forensics": TijoriOverviewSection.COMPANY_DETAILS,
    "overview-marketshare": TijoriOverviewSection.MARKET_SHARE,
    "overview-revenuemix": TijoriOverviewSection.REVENUE_MIX,
    "overview-competitors": TijoriOverviewSection.PEERS,
    "overview-corporateactions": TijoriOverviewSection.CORPORATE_ACTIONS,
}
FINANCIALS = {
    "company-financials": "",
    "financials-growth-table": "growth",
    "financials-balance-sheet": "bs_",
    "financials-profit-and-loss": "pl_",
    "financials-cash-flow": "cf_",
    "financials-ratios": "fr_",
    "financials-quarterly-results": "qt_",
}
ANALYSIS = {
    "fund-flow-api": TijoriAnalysisSection.FUND_FLOW,
    "cash-flow-waterfall-api": TijoriAnalysisSection.CASH_FLOW_WATERFALL,
    "balance-sheet-snapshot-api": TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT,
    "op-metrics-api": TijoriAnalysisSection.OP_METRICS,
}
EVENTS = {
    "company-timeline-api": TijoriEventsSurface.COMPANY_TIMELINE,
    "quarterly-results": TijoriEventsSurface.QUARTERLY_RESULTS,
    "upcoming-events": TijoriEventsSurface.UPCOMING,
}
TIJORI_SURFACES = (
    *OVERVIEW,
    *FINANCIALS,
    *ANALYSIS,
    *EVENTS,
    "company-shareholding",
    "shareholding-detailed",
    "company-search-api",
)


class ReaderError(ValueError):
    """A G0 reader could not run."""


def reader_values(document: Any, basis: str | None = None) -> tuple[VendorValue, ...]:
    """Convert the declared reader output types, sharing one positional cell emitter."""
    result: list[VendorValue] = []

    def emit(
        items: Any,
        key: str,
        row: int = 0,
        unit: str | None = None,
        scope: str | None = basis,
        padding: frozenset[int] = frozenset(),
    ) -> None:
        for column, (raw, value, provenance, numeric) in enumerate(items):
            locator, label, header = f"{key}/{row}/{column}", str(row), str(column)
            if provenance is not None:
                locator = provenance.context_ref or (
                    f"#{provenance.table_id}/{provenance.row_path}"
                    f"/column[{provenance.column_index}]"
                )
                label = provenance.row_label or provenance.row_path or label
                header = provenance.column_label or header
            if isinstance(document, te.TijoriCompanyTimeline) and header == "col0":
                numeric = False
            cell = VendorValue(
                table_key=key,
                row_index=row,
                column_index=column,
                raw_text=raw,
                value=value,
                locator=locator,
                row_label=label,
                column_label=header,
                unit=unit,
                basis=scope,
                padded=column in padding,
                expected_numeric=numeric and column not in padding,
            )
            if (
                isinstance(document, (te.TijoriQuarterlyResults, te.TijoriCompanyTimeline))
                and cell.expected_numeric
                and value is None
            ):
                cell = measurement(cell, raw, unit)
            result.append(cell)

    def cells(
        items: Any,
        key: str,
        row: int = 0,
        unit: str | None = None,
        scope: str | None = basis,
        padding: frozenset[int] = frozenset(),
        numeric: bool = True,
    ) -> None:
        padding = padding | frozenset(
            i for i, c in enumerate(items) if isinstance(c, TijoriTableCell) and not c.published
        )
        emit(
            ((c.raw_text, c.value, c.provenance, numeric) for c in items),
            key,
            row,
            unit,
            scope,
            padding,
        )

    def rows(
        items: Any,
        key: str,
        scope: str | None = basis,
        padding: frozenset[int] = frozenset(),
        numeric: bool = True,
        default_unit: str | None = None,
    ) -> None:
        for index, row in enumerate(items):
            positioned = (
                sf.TableRow,
                sc.BucketRow,
                sf.ScheduleSubRow,
                sc.InvestorHolding,
                sc.SegmentRow,
                sc.RelatedPartyLine,
                sc.PeerRow,
            )
            index = row.position if isinstance(row, positioned) else index
            unit = row.unit if isinstance(row, (sf.TableRow, sc.BucketRow)) else default_unit
            cells(row.cells, key, index, unit, scope, padding, numeric)
            if isinstance(
                row,
                (
                    TijoriTableRow,
                    TijoriShareholdingRow,
                    to.TijoriCustomFinancialRow,
                    te.TijoriListingRow,
                    te.TijoriResultRow,
                    te.TijoriEventDetailRow,
                ),
            ):
                emit(
                    ((raw, None, None, numeric) for raw in row.unaligned_raw_values),
                    key + ":unaligned",
                    index,
                    unit,
                    scope,
                )

    def quarantine(items: tuple[sf.QuarantinedRow, ...], key: str) -> None:
        for row in items:
            emit(
                ((raw, None, None, True) for raw in row.raw_cells),
                key + ":quarantined",
                row.position,
            )

    def series(items: Any, key: str, unit: str | None = None) -> None:
        for index, point in enumerate(items):
            emit(((point.raw_value_text, point.value, None, True),), key, index, unit)

    def windows(items: Any, key: str) -> None:
        for index, window in enumerate(items):
            cells(tuple(item.amount for item in window.items), f"{key}/windows/{index}")

    def convert(node: Any, key: str) -> None:
        match node:
            case tuple():
                for index, item in enumerate(node):
                    convert(item, f"{key}/{index}")
            case sf.SectionTable(table_id=table, rows=items, growth_tables=growth):
                rows(items, table)
                quarantine(node.quarantined, table)
                convert(growth, table + "/ranges-table")
            case sc.ShareholdingTable(rows=items) | sc.PeersTable(rows=items):
                rows(items, key)
                quarantine(node.quarantined, key)
            case sf.GrowthTable(rows=items):
                for growth_row in items:
                    cells((growth_row,), key, growth_row.position, growth_row.unit)
            case sf.ScheduleFamily(sub_rows=items, basis=scope):
                rows(items, key + "/sub_rows", scope)
            case sc.InvestorBucket(holders=items):
                rows(items, key + "/holders")
            case sc.SegmentTable(lines=items):
                for line in items:
                    rows(line.rows, f"{key}/lines/{line.position}")
                    quarantine(line.quarantined, f"{key}/lines/{line.position}")
            case sc.RelatedPartyTable(parties=items):
                for party in items:
                    rows(party.lines, f"{key}/parties/{party.position}")
                    quarantine(party.quarantined, f"{key}/parties/{party.position}")
            case sc.CorporateActionsTable(tabs=items):
                for tab in items:
                    emit(
                        ((a.title, a.amount, a.provenance, False) for a in tab.actions),
                        f"{key}/tabs/{tab.position}",
                    )
            case sc.QuickRatioList(ratios=items, table_id=table):
                for ratio in items:
                    readings = (
                        (ratio.raw_text, value, ratio.provenances[i], True)
                        for i, value in enumerate(ratio.values)
                    )
                    emit(readings, table, ratio.position, ratio.unit)
            case TijoriTable(rows=items, key=table, scope=scope):
                off = frozenset(
                    i
                    for i, label in enumerate(node.column_period_labels)
                    if label.startswith(("Jun ", "Dec "))
                )
                all_zero = all(
                    row.cells and all(row.cells[i].value == 0 for i in off) for row in items
                )
                has_values = any(cell.value for row in items for cell in row.cells)
                padded = (
                    off
                    if table.startswith("qt_") and items and off and all_zero and has_values
                    else frozenset()
                )
                rows(items, table, scope, padded)
            case TijoriShareholding(rows=items):
                rows(items, key, default_unit=node.unit_label)
            case to.TijoriRatiosSection(ratios=items):
                for index, overview_ratio in enumerate(items):
                    cells((overview_ratio.amount,), key, index, overview_ratio.unit)
            case to.TijoriCustomFinancialsSection(blocks=items):
                for index, block in enumerate(items):
                    rows(block.rows, f"{key}/blocks/{index}")
            case to.TijoriMarketShareSection(charts=items):
                for index, chart in enumerate(items):
                    cells((chart.latest_value,), key + "/charts", index, chart.unit)
                    series(chart.series, f"{key}/charts/{index}/series", chart.unit)
            case to.TijoriPeersSection(rows=items):
                rows(items, key)
            case te.TijoriUpcomingEvents(rows=items):
                rows(items, key, numeric=False)
            case to.TijoriPriceReturnsSection(returns=items):
                cells(tuple(item.amount for item in items), key)
            case (
                to.TijoriPriceSeriesSection(points=items) | ta.TijoriOpMetricsSection(points=items)
            ):
                series(items, key)
            case to.TijoriPriceChartPeersSection():
                pass
            case to.TijoriRevenueMixSection(break_ups=items):
                for index, breakup in enumerate(items):
                    cells(breakup.entries, f"{key}/break_ups/{index}")
            case to.TijoriCompanyDetailsSection():
                cells((node.market_cap, node.price_earnings, node.price_earnings_growth), key)
                counts = node.quick_look.counts
                if counts:
                    numbers = (counts.green, counts.red, counts.neutral, counts.gray, counts.total)
                    counts_data = (
                        ("", None, None, False) if n is None else (str(n), Decimal(n), None, True)
                        for n in numbers
                    )
                    emit(counts_data, key + "/counts")
                for index, category in enumerate(node.quick_look.categories):
                    flags = ((f.raw_json, None, f.provenance, False) for f in category.flags)
                    emit(flags, f"{key}/flags/{index}")
            case to.TijoriCorporateActionsSection(actions=items):
                for index, action in enumerate(items):
                    raw = (action.ex_date, action.event_details, action.event_date)
                    emit(((r, None, action.provenance, False) for r in raw), key, index)
            case ta.TijoriFundFlowSection(groups=items):
                for index, group in enumerate(items):
                    windows(group.windows, f"{key}/groups/{index}")
            case ta.TijoriCashFlowWaterfallSection(windows=items):
                windows(items, key)
            case ta.TijoriBalanceSheetSnapshotSection(sides=items):
                for index, side in enumerate(items):
                    cells(tuple(entry.amount for entry in side.entries), f"{key}/sides/{index}")
            case te.TijoriQuarterlyResults(items=items):
                for item in items:
                    item_key = f"{key}/items/{item.position}"
                    cells((item.company_cell, item.announced), item_key + "/header", numeric=False)
                    cells(
                        tuple(metric.cell for metric in item.headline_metrics),
                        item_key + "/metrics",
                    )
                    rows(item.rows, item_key + "/rows")
            case te.TijoriCompanyTimeline(events=items):
                for event in items:
                    event_key = f"{key}/events/{event.position}"
                    header = (
                        event.company_cell,
                        event.event_cell,
                        event.content_cell,
                        *event.link_cells,
                    )
                    cells(header, event_key, numeric=False)
                    for detail_table in event.detail_tables:
                        rows(
                            detail_table.rows,
                            f"{event_key}/tables/{detail_table.position}",
                            numeric=bool(detail_table.column_labels),
                        )
            case _:
                raise ReaderError("unsupported reader output")

    convert(document, "reader")
    return tuple(result)


def candidate_value(raw: str, value: Decimal | None, locator: str) -> tuple[VendorValue, ...]:
    """One verified search candidate under a positional address."""
    return (
        VendorValue(
            table_key="candidate",
            row_index=0,
            column_index=0,
            locator=locator,
            row_label="company",
            column_label=locator[1:],
            raw_text=raw,
            value=value,
        ),
    )


def screener_reader(surface: str, body: Body, context: ParseContext) -> Any:
    """Supply the existing Screener readers with their capture and parent inputs."""
    ids, parent = context.ids, dict(context.parent or {})
    assert ids is not None
    common: dict[str, Any] = dict(
        source_id="screener-subscriber", retrieved_at=context.retrieved_at
    )
    page: dict[str, Any] = dict(**common, file_sha256=context.body_sha256)
    fragment: dict[str, Any] = dict(
        **common, url=context.url, document_id=context.capture_id, body_sha256=context.body_sha256
    )
    if surface == "company-search-api":
        candidate = screener_candidate(body.raw, ids.nse_symbol)
        if not isinstance(candidate, int):
            raise ReaderError(str(candidate))
        return candidate_value(str(candidate), Decimal(candidate), "/id")
    if surface == "company-consolidated-empty-shell":
        assert context.basis is not None and ids.topology is not None
        _, outcome = read_page_evidence(
            body.raw.decode(), basis_requested=context.basis, topology=ids.topology
        )
        if outcome is not PageOutcome.BASIS_UNAVAILABLE:
            raise ReaderError("expected unavailable basis")
        return ()
    if surface == "section-shareholding":
        return tuple(read_shareholding_table(body.tree(), period, **page) for period in Periodicity)
    if surface.startswith("section-"):
        section = Section(surface.removeprefix("section-"))
        table = read_section(body.tree(), section, **page)
        return (
            (table, read_growth_section(body.tree(), **page))
            if section is Section.PROFIT_LOSS
            else table
        )
    if surface == "schedules-api":
        assert context.basis is not None
        reader = read_nested_schedule if "outer_parent" in parent else read_schedule
        return reader(
            body.raw,
            basis=context.basis,
            section=Section(parent["section"]),
            parent=parent.get("outer_parent", parent["row"]),
            periods=parent["periods"],
            **(
                {
                    "expands": parent["row"],
                    "reference_row": parent["reference_row"],
                    "sales_row": parent["sales_row"],
                }
                if "outer_parent" in parent
                else {"page_row": parent["page_row"]}
            ),
            **fragment,
        )
    if surface == "investors-api":
        return read_investor_bucket(
            body.raw, hook=parent["hook"], table=parent["table"], **fragment
        )
    if surface == "segments-api":
        return read_segments(
            body.raw,
            parse=parse_document,
            hook=parent["hook"],
            page_section=parent["page_section"],
            **fragment,
        )
    if surface == "quick-ratios-api":
        return fragments.read_quick_ratios(
            body.raw,
            element=None,
            parse=parse_document,
            configured_by_account=True,
            identity_strength=IdentityStrength.CONFIGURED_URL_ONLY,
            binding=Binding.CONFIGURED_URL_ONLY,
            **fragment,
        )
    if surface == "peers-api":
        assert ids.screener_company_id is not None and context.basis is not None
        return fragments.read_peers(
            body.raw,
            company_id=ids.screener_company_id,
            basis=context.basis,
            parse=parse_document,
            **fragment,
        )
    fragment_reader = (
        fragments.read_related_party
        if surface == "related-party"
        else fragments.read_corporate_actions
    )
    return fragment_reader(body.raw, parse=parse_document, **fragment)


def tijori_reader(surface: str, body: Body, context: ParseContext) -> Any:
    """Supply the existing Tijori readers with the capture clock and verified ids."""
    if surface == "company-search-api":
        candidate = tijori_candidate(body.raw)
        if not isinstance(candidate, str):
            raise ReaderError(str(candidate))
        return candidate_value(candidate, None, "/slug")
    ids = context.ids
    if surface in {"quarterly-results", "upcoming-events"}:
        return build_tijori_events(
            body.raw,
            surface=EVENTS[surface],
            source_url=context.url,
            content_sha256=context.body_sha256,
            retrieved_at=context.retrieved_at,
        )
    if ids is None or ids.tijori_slug is None or ids.tijori_company_id is None:
        raise ReaderError("verified Tijori slug and company id required")
    common: dict[str, Any] = dict(
        slug=ids.tijori_slug,
        expected_symbol=ids.nse_symbol,
        expected_company_id=ids.tijori_company_id,
        source_url=context.url,
        retrieved_at=context.retrieved_at,
    )
    if surface in OVERVIEW:
        return build_tijori_overview(body.raw, section=OVERVIEW[surface], **common)
    if surface in FINANCIALS:
        tables = TijoriSource.parse_all_tables_bytes(body.raw, **common)
        selected = tuple(table for table in tables if table.key.startswith(FINANCIALS[surface]))
        if not selected:
            raise ReaderError("no reader table")
        return selected
    if surface in {"company-shareholding", "shareholding-detailed"}:
        return build_tijori_shareholding(body.raw, **common)
    api: dict[str, Any] = dict(
        slug=ids.tijori_slug,
        symbol=ids.nse_symbol,
        company_id=ids.tijori_company_id,
        source_url=context.url,
        content_sha256=context.body_sha256,
        retrieved_at=context.retrieved_at,
    )
    if surface in ANALYSIS:
        return build_tijori_analysis(
            body.raw,
            section=ANALYSIS[surface],
            metric_id=(context.parent or {}).get("metric_id"),
            **api,
        )
    if surface in EVENTS:
        return build_tijori_events(body.raw, surface=EVENTS[surface], **api)
    raise ReaderError("no reader")


def make_reader(site: str, surface: str) -> Parser:
    """Bind one logical surface to a namespaced retained-body adapter."""

    def parse(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
        """Run a reader without allowing its failures to become kept captures."""
        config = structlog.get_config()

        def sanitize(logger: Any, method: str, event: Any) -> dict[str, str]:
            return {"event": "vendor_surface_reader", "site": site, "surface": surface}

        structlog.configure(processors=[sanitize, *config["processors"]])
        try:
            document = (screener_reader if site == "screener" else tijori_reader)(
                surface, body, context
            )
            if isinstance(document, tuple) and all(
                isinstance(item, VendorValue) for item in document
            ):
                return document
            return reader_values(document, context.basis.value if context.basis else None)
        finally:
            structlog.configure(**config)

    return parse
