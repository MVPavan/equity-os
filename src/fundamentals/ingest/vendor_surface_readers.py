"""Thin retained-body adapters around the existing subscriber readers."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from fundamentals.entity.verification import screener_candidate, tijori_candidate
from fundamentals.ingest import screener_company_fragments as fragments
from fundamentals.ingest.screener_company_artifacts import CorporateAction, QuickRatio
from fundamentals.ingest.screener_company_models import Binding, Periodicity
from fundamentals.ingest.screener_financials_models import GrowthRow, IdentityStrength, Section
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
from fundamentals.ingest.tijori_events_models import TijoriEventsCell, TijoriEventsSurface
from fundamentals.ingest.tijori_overview import build_tijori_overview
from fundamentals.ingest.tijori_overview_models import (
    TijoriCorporateAction,
    TijoriOverviewSection,
    TijoriQuickLookCounts,
    TijoriQuickLookFlag,
)
from fundamentals.ingest.tijori_series import TijoriSeriesPoint
from fundamentals.ingest.tijori_shareholding import build_tijori_shareholding
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriTable, TijoriTableCell
from fundamentals.store.vendor_values_store import VendorValue

if TYPE_CHECKING:
    from fundamentals.ingest.vendor_surface_parse import Body, ParseContext, Parser

SCREENER_SURFACES = (
    "company-consolidated-empty-shell",
    "section-quarters",
    "section-profit-loss",
    "section-balance-sheet",
    "section-cash-flow",
    "section-ratios",
    "section-shareholding",
    "schedules-api",
    "investors-api",
    "segments-api",
    "quick-ratios-api",
    "peers-api",
    "related-party",
    "corporate-actions-modal",
    "company-search-api",
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
    "financials-balance-sheet-snapshot",
    "financials-fundflow-analysis",
    "financials-cash-flow-analysis",
)


class ReaderError(ValueError):
    """A G0 reader could not run; its message must survive in the outcome."""


def reader_values(document: Any, basis: str | None = None) -> tuple[VendorValue, ...]:
    """Convert typed reader cells, keeping structural positions and source anchors."""
    values: list[VendorValue] = []

    def walk(
        node: Any,
        path: str,
        table: str,
        unit: str | None,
        scope: str | None,
        padding: frozenset[int] = frozenset(),
        source_row: int | None = None,
    ) -> None:
        """Walk reader output only; no source bytes are interpreted here."""
        if isinstance(node, (tuple, list)):
            for index, item in enumerate(node):
                walk(item, f"{path}/{index}", table, unit, scope, padding, source_row)
            return
        if not isinstance(node, BaseModel):
            return
        source_row = getattr(node, "position", source_row)
        table = str(getattr(node, "key", getattr(node, "table_id", table)))
        unit = getattr(node, "unit", getattr(node, "unit_label", unit))
        scope = getattr(node, "scope", scope)
        if isinstance(node, TijoriTable) and node.key.startswith("qt_"):
            # Evidenced SME shape: Jun/Dec columns are zero throughout the statement.
            off_cycle = frozenset(
                i
                for i, label in enumerate(node.column_period_labels)
                if label.startswith(("Jun ", "Dec "))
            )
            padding = (
                off_cycle
                if off_cycle
                and node.rows
                and all(
                    row.cells and all(row.cells[i].value == 0 for i in off_cycle)
                    for row in node.rows
                )
                and any(cell.value for row in node.rows for cell in row.cells)
                else frozenset()
            )
        unaligned = getattr(node, "unaligned_raw_values", getattr(node, "raw_cells", ()))
        for column, raw in enumerate(unaligned):
            values.append(
                VendorValue(
                    table_key=f"{table}/{path}",
                    row_index=0,
                    column_index=column,
                    locator=f"{path}/{column}",
                    row_label=path,
                    column_label=str(column),
                    raw_text=raw,
                    value=None,
                    unit=unit,
                    basis=scope,
                    expected_numeric=True,
                )
            )
        provenance: Any = getattr(node, "provenance", None)
        if hasattr(node, "raw_text") and hasattr(node, "value"):
            parts = path.split("/")
            column = (
                0
                if isinstance(node, GrowthRow)
                else getattr(node, "period_index", int(parts[-1]) if parts[-1].isdigit() else 0)
            )
            row_path = "/".join(parts[:-2]) if parts[-1].isdigit() else path
            expected = not isinstance(node, TijoriEventsCell) or node.value is not None
            match = re.fullmatch(r"(.*)/(?:rows|sub_rows|holders)/(\d+)(?:/cells/\d+)?", path)
            table_path, row_index = (match[1], int(match[2])) if match else (row_path, 0)
            values.append(
                VendorValue(
                    table_key=f"{table}/{table_path}",
                    row_index=source_row if source_row is not None else row_index,
                    column_index=column,
                    locator=provenance.context_ref
                    or (
                        f"#{provenance.table_id}/{provenance.row_path}"
                        f"/column[{provenance.column_index}]"
                    ),
                    row_label=provenance.row_label or provenance.row_path or row_path,
                    column_label=provenance.column_label or str(column),
                    raw_text=node.raw_text,
                    value=node.value,
                    unit=unit,
                    basis=scope,
                    padded=column in padding
                    or isinstance(node, TijoriTableCell)
                    and not node.published,
                    expected_numeric=expected and column not in padding,
                )
            )
            return
        if isinstance(node, (TijoriCorporateAction, TijoriQuickLookCounts)):
            fields = (
                ("ex_date", "event_details", "event_date")
                if isinstance(node, TijoriCorporateAction)
                else ("green", "red", "neutral", "gray", "total")
            )
            for column, name in enumerate(fields):
                raw = getattr(node, name)
                if raw is not None:
                    values.append(
                        VendorValue(
                            table_key=f"{table}/{path}",
                            row_index=0,
                            column_index=column,
                            locator=f"{path}/{name}",
                            row_label=path,
                            column_label=name,
                            raw_text=str(raw),
                            value=Decimal(raw) if isinstance(raw, int) else None,
                        )
                    )
            return
        if isinstance(node, TijoriQuickLookFlag):
            values.append(
                VendorValue(
                    table_key=f"{table}/{path.rsplit('/', 1)[0]}",
                    row_index=int(path.rsplit("/", 1)[1]),
                    column_index=0,
                    locator=node.provenance.context_ref or path,
                    row_label=node.name or path,
                    column_label="flag",
                    raw_text=node.raw_json,
                    value=None,
                )
            )
            return
        if isinstance(node, (QuickRatio, CorporateAction, TijoriSeriesPoint)):
            readings = (
                node.values
                if isinstance(node, QuickRatio)
                else (node.amount if isinstance(node, CorporateAction) else node.value,)
            )
            raw = (
                node.title
                if isinstance(node, CorporateAction)
                else node.raw_value_text
                if isinstance(node, TijoriSeriesPoint)
                else node.raw_text
            )
            for column, value in enumerate(readings):
                values.append(
                    VendorValue(
                        table_key=f"{table}/{path.rsplit('/', 1)[0]}",
                        row_index=int(path.rsplit("/", 1)[1]),
                        column_index=column,
                        locator=path,
                        row_label=path,
                        column_label=str(column),
                        raw_text=raw,
                        value=value,
                        unit=unit,
                        basis=scope,
                        expected_numeric=not isinstance(node, CorporateAction),
                    )
                )
            return
        for name in type(node).model_fields:
            if name not in {"metadata", "comparisons", "provenance"}:
                walk(getattr(node, name), f"{path}/{name}", table, unit, scope, padding, source_row)

    walk(document, "", "reader", None, basis)
    return tuple(values)


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
        return (
            VendorValue(
                table_key="candidate",
                row_index=0,
                column_index=0,
                locator="/id",
                row_label=ids.nse_symbol,
                column_label="id",
                raw_text=str(candidate),
                value=Decimal(candidate),
            ),
        )
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
        reader = read_nested_schedule if "expands" in parent else read_schedule
        return reader(body.raw, basis=context.basis, **parent, **fragment)
    if surface == "investors-api":
        return read_investor_bucket(body.raw, **parent, **fragment)
    if surface == "segments-api":
        return read_segments(body.raw, parse=parse_document, **parent, **fragment)
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
        return (
            VendorValue(
                table_key="candidate",
                row_index=0,
                column_index=0,
                locator="/slug",
                row_label="company",
                column_label="slug",
                raw_text=candidate,
                value=None,
            ),
        )
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
        try:
            document = (screener_reader if site == "screener" else tijori_reader)(
                surface, body, context
            )
            if isinstance(document, tuple) and all(
                isinstance(item, VendorValue) for item in document
            ):
                return document
            return reader_values(document, context.basis.value if context.basis else None)
        except Exception as error:
            raise ReaderError(f"{type(error).__name__}: {error}") from error

    return parse
