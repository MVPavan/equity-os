"""One parser registry and response-independent context for retained bytes."""

from __future__ import annotations

import hashlib
import inspect
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr

from fundamentals.ingest import vendor_surface_series as series
from fundamentals.ingest.screener_session_models import Basis, BasisTopology, IdentityMismatchError
from fundamentals.ingest.screener_session_page import (
    assert_logged_in,
    parse_document,
    read_identity,
    read_page_evidence,
)
from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_readers import (
    SCREENER_SURFACES,
    TIJORI_SURFACES,
    make_reader,
)
from fundamentals.ingest.vendor_surface_series import screener_chart
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, ParseGroup, Scope, SurfaceSpec
from fundamentals.store.vendor_values_store import VendorValue


class CompanyIds(BaseModel):
    """Verified request identity; nothing here is inferred from a response."""

    model_config = ConfigDict(frozen=True)
    nse_symbol: str
    isin: str
    tijori_slug: str | None
    tijori_company_id: int | None
    screener_company_id: int | None
    topology: BasisTopology | None


class ParseContext(BaseModel):
    """The capture's clock, identity and parent inputs supplied to a parser."""

    model_config = ConfigDict(frozen=True)
    ids: CompanyIds | None
    basis: Basis | None
    url: str
    retrieved_at: datetime
    body_sha256: str
    capture_id: str
    parent: Mapping[str, Any] | None = None


class Body(BaseModel):
    """Retained bytes with one lazily parsed document for all section readers."""

    model_config = ConfigDict(frozen=True)
    raw: bytes
    _tree: Any = PrivateAttr(default=None)

    def tree(self) -> Any:
        """Parse HTML once for all consumers of this body."""
        if self._tree is None:
            # lxml rejects a str that keeps its XML encoding declaration (sitemap.xml).
            text = re.sub(r"^\s*<\?xml[^>]*\?>", "", self.raw.decode("utf-8"))
            self._tree = parse_document(text)
        return self._tree


Parser = Callable[[Body, ParseContext], tuple[VendorValue, ...]]


class ParserEntry(BaseModel):
    """One namespaced version bound to its own function's source."""

    model_config = ConfigDict(frozen=True)
    version: str
    parse: Parser


@cache
def parser_sha256(parser: Parser) -> str:
    """Pin this function only; unrelated parser additions cannot alter the hash."""
    return hashlib.sha256(inspect.getsource(parser).encode()).hexdigest()


def company_page(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Prove login, request identity and any configured basis before keeping a page."""
    assert context.ids is not None and context.basis is not None
    assert_logged_in(body.tree())
    identifier, _ = read_identity(body.tree())
    if identifier != context.ids.screener_company_id:
        raise IdentityMismatchError("company id differs from verified request")
    if context.ids.topology is not None:
        read_page_evidence(
            body.raw.decode("utf-8"), basis_requested=context.basis, topology=context.ids.topology
        )
    return ()


PARSERS: dict[tuple[Site, str], ParserEntry] = {
    (Site.SCREENER, "chart-api"): ParserEntry(
        version="screener:chart-api.v1", parse=screener_chart
    ),
    (Site.SCREENER, "company-page"): ParserEntry(
        version="screener:company-page.v1", parse=company_page
    ),
}


# Task 9: Tijori company series.
PARSERS.update(
    {
        (Site.TIJORI, surface): ParserEntry(
            # Statement compare advanced for live ratio rows and the quarterly growth axis.
            version=f"tijori:{surface}.v{2 if surface == 'financial-statement-compare-api' else 1}",
            parse=parser,
        )
        for surface, parser in {
            "chartdata-price-api": series.tijori_price,
            "chartdata-valuation-api": series.tijori_valuation,
            "chartdata-median-pe-api": series.tijori_median_pe,
            "capex-api": series.tijori_capex,
            "debt-api": series.tijori_debt,
            "revenue-mix-history-api": series.tijori_revenue_mix,
            "financials-popup-chart-api": series.tijori_popup,
            "financial-statement-compare-api": series.tijori_statement_compare,
        }.items()
    }
)

# Task 12: Market series.
PARSERS.update(
    {
        (site, surface): ParserEntry(version=f"{name}:{surface}.v1", parse=parser)
        for site, name, surface, parser in (
            (Site.SCREENER, "screener", "fii-api", series.screener_fii),
            (Site.SCREENER, "screener", "hs-data-api", series.screener_hs),
            (Site.TIJORI, "tijori", "macro-chart-api", series.tijori_macro),
            (Site.TIJORI, "tijori", "sector-ms-chart-api", series.tijori_sector_ms),
            (Site.TIJORI, "tijori", "sector-company-opm-api", series.tijori_sector_opm),
            (Site.TIJORI, "tijori", "index-data-api", series.tijori_index),
            (Site.TIJORI, "tijori", "index-metric-data-api", series.tijori_index_metric),
        )
    }
)
# Task 8: G0 retained-reader adapters.
# Shared reader/converter changes require bumping every affected caller version (pin rule).
for _site, _name, _surfaces in (
    (Site.SCREENER, "screener", SCREENER_SURFACES),
    (Site.TIJORI, "tijori", TIJORI_SURFACES),
):
    for _surface in _surfaces:
        # Shared sanitization and series conversion advance every reader pin.
        _version = (
            {"quarterly-results": 5, "company-timeline-api": 7}.get(_surface, 4)
            if _name == "tijori"
            else 4
        )
        PARSERS[_site, _surface] = ParserEntry(
            version=f"{_name}:{_surface}.reader.v{_version}",
            parse=make_reader(_name, _surface),
        )

# Task 15: G3 positional cells (imports kept in this merge-local block).
from fundamentals.ingest import vendor_surface_cells as cells  # noqa: E402

PARSERS.update(
    {
        (site, surface): ParserEntry(
            version=f"{name}:{surface}.v4",
            parse=parser,
        )
        for site, name, surface, parser in (
            (Site.SCREENER, "screener", "section-insights", cells.screener_insights),
            (Site.SCREENER, "screener", "company-compare", cells.screener_compare),
            (
                Site.TIJORI,
                "tijori",
                "benchmarking-benchmarking-financial",
                cells.benchmark_financial,
            ),
            (Site.TIJORI, "tijori", "benchmarking-benchmarking-business", cells.benchmark_business),
        )
    }
)


# Task 13: G2 market tables and feed metadata.
def register_tables(specs: tuple[SurfaceSpec, ...]) -> None:
    """Bind company and market selectors supplied by the composition root."""
    from fundamentals.ingest.vendor_surface_tables import company_parser, market_parser

    for spec in specs:
        if spec.group is ParseGroup.TABLE:
            # Numeric table roles advance both company and market parser pins.
            version = "v5" if spec.scope is Scope.MARKET else "v3"
            PARSERS[spec.site, spec.id] = ParserEntry(
                version=f"{SITE_NAME[spec.site]}:{spec.id}.{version}",
                parse=(market_parser if spec.scope is Scope.MARKET else company_parser)(spec),
            )


# Task 7: retained-only sections and discovery; numeric readers belong to Tasks 8-10.
def kept_section(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """Keep a declared nonnumeric section without manufacturing observations."""
    return ()


for _site, _section_names in (
    (Site.SCREENER, "section-chart section-analysis section-peers"),
    (
        Site.TIJORI,
        "company-benchmarking "
        "overview-quick-view overview-company-timeline-sidepanel overview-knowledgebase "
        "overview-popular-queries overview-discussions-and-analysis overview-operationalmetrics "
        "financials-price financials-reverse-dcf financials-faqfinancials "
        "financials-balance-sheet-snapshot financials-fundflow-analysis "
        "financials-cash-flow-analysis "
        "shareholding-faqshareholding",
    ),
):
    for _surface in _section_names.split():
        PARSERS[_site, _surface] = ParserEntry(
            version=f"{('screener' if _site is Site.SCREENER else 'tijori')}:{_surface}.v1",
            parse=kept_section,
        )
