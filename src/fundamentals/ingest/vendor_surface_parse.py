"""One parser registry and response-independent context for retained bytes."""

from __future__ import annotations

import hashlib
import inspect
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
from fundamentals.ingest.vendor_surface_series import screener_chart
from fundamentals.ingest.vendor_surface_tables import (
    screener_announcements,
    screener_documents,
    screener_trades,
    tijori_brands,
    tijori_connections,
    tijori_customers,
    tijori_filings,
    tijori_shareholding_overview,
    tijori_shareholding_trend,
    tijori_suppliers,
)
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
            self._tree = parse_document(self.raw.decode("utf-8"))
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
        (Site.TIJORI, surface): ParserEntry(version=f"tijori:{surface}.v1", parse=parser)
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

# Task 10: G2 company tables and lists.
PARSERS[Site.SCREENER, "section-documents"] = ParserEntry(
    version="screener:section-documents.v1", parse=screener_documents
)
PARSERS[Site.SCREENER, "company-trades"] = ParserEntry(
    version="screener:company-trades.v1", parse=screener_trades
)
PARSERS[Site.SCREENER, "company-announcements"] = ParserEntry(
    version="screener:company-announcements.v1", parse=screener_announcements
)
PARSERS[Site.TIJORI, "overview-company-filings"] = ParserEntry(
    version="tijori:overview-company-filings.v1", parse=tijori_filings
)
PARSERS[Site.TIJORI, "overview-customers"] = ParserEntry(
    version="tijori:overview-customers.v1", parse=tijori_customers
)
PARSERS[Site.TIJORI, "overview-suppliers"] = ParserEntry(
    version="tijori:overview-suppliers.v1", parse=tijori_suppliers
)
PARSERS[Site.TIJORI, "overview-brands"] = ParserEntry(
    version="tijori:overview-brands.v1", parse=tijori_brands
)
PARSERS[Site.TIJORI, "overview-connections"] = ParserEntry(
    version="tijori:overview-connections.v1", parse=tijori_connections
)
PARSERS[Site.TIJORI, "shareholding-overview"] = ParserEntry(
    version="tijori:shareholding-overview.v1", parse=tijori_shareholding_overview
)
PARSERS[Site.TIJORI, "shareholding-trend"] = ParserEntry(
    version="tijori:shareholding-trend.v1", parse=tijori_shareholding_trend
)

# Task 15: G3 positional cells (imports kept in this merge-local block).
from fundamentals.ingest import vendor_surface_cells as cells  # noqa: E402

PARSERS.update(
    {
        (site, surface): ParserEntry(version=f"{name}:{surface}.v1", parse=parser)
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
