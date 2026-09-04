"""Shared fixtures and seams for the ``screener-financials`` test modules.

No test opens a socket: the transport seam defined here is replaced with
committed synthetic bodies, and every helper below exists so the two test
modules exercise the same one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr

from fundamentals.ingest.screener_financials import (
    ALL_SECTIONS,
    read_financials,
)
from fundamentals.ingest.screener_financials_models import (
    Section,
)
from fundamentals.ingest.screener_financials_tables import read_section
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    Basis,
    BasisTopology,
    ScreenerCredentials,
    ScreenerRateLimitedError,
    ScreenerSessionConfig,
)
from fundamentals.ingest.screener_session_page import parse_document

_FIXTURES = Path(__file__).parent / "fixtures"
_SCHEDULES = _FIXTURES / "screener_schedules"
_PAGE = _FIXTURES / "synthetic_screener_financials.html"
_SHELL_PAGE = _FIXTURES / "synthetic_screener_session_basis_unavailable.html"
_SESSION_ENV = "SCREENER_SESSION_COOKIE"
_SESSION_TOKEN = "fixture-session-token"
_COMPANY_ID = 991001

_WATCHLIST_YAML = """
raw_dir: "data/raw/watchlist"
stocks:
  - name: "Fixture Consolidated Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "FIXTURECO"
      bse_scrip: "500999"
      screener_slug: "FIXTURECO"
      screener_company_id: 991001
      screener_warehouse_id_consolidated: 992001
      screener_warehouse_id_standalone: 992002
      tijori_slug: "fixture-consolidated-ltd"
      tijori_company_id: 81
      needs_verification: [{flagged}]
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
  - name: "Fixture Standalone Only Ltd"
    domain: "Fixture"
    identifiers:
      nse_symbol: "SOLOCO"
      bse_scrip: "500998"
      screener_slug: "SOLOCO"
      screener_company_id: 991002
      screener_warehouse_id_standalone: 992003
      tijori_slug: "fixture-standalone-only-ltd"
      tijori_company_id: 82
    quarter:
      label: "Q3FY25"
      period_start: "2024-10-01"
      period_end: "2024-12-31"
      knowledge_cutoff: "2025-02-15T00:00:00Z"
"""

_SLUG_SAFE = str.maketrans({" ": "-"})


def _watchlist(tmp_path: Path, *, flagged: str = "") -> Path:
    """Write the fixture watchlist, optionally flagging one identifier unverified."""
    path = tmp_path / "watchlist.yaml"
    path.write_text(_WATCHLIST_YAML.format(flagged=flagged), encoding="utf-8")
    return path


def _schedule_fixture(url: str, *, swap: tuple[str, str] | None = None) -> bytes:
    """Serve the committed body for the family one schedule URL names.

    ``swap`` replaces exactly one family's body with a named variant, which is
    how a single wrong-basis response is injected into an otherwise correct run.
    """
    query = parse_qs(urlsplit(url).query)
    section = query["section"][0]
    parent = query["parent"][0].lower().translate(_SLUG_SAFE)
    name = f"{section}__{parent}"
    variant = swap[1] if swap is not None and swap[0] == name else ""
    return (_SCHEDULES / f"{name}{variant}.json").read_bytes()


def _schedule_key(url: str) -> tuple[str, str]:
    """The ``(section, parent)`` one schedule URL addresses, verbatim.

    Verbatim rather than slugged, because a level-3 parent is a sub-row label
    the body supplied (``Material Cost %``) and the point of the level-3 tests
    is which exact label was requested.
    """
    query = parse_qs(urlsplit(url).query)
    return query["section"][0], query["parent"][0]


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    swap: tuple[str, str] | None = None,
    rate_limit_after: int | None = None,
    page: bytes | None = None,
    bodies: dict[tuple[str, str], bytes] | None = None,
) -> list[str]:
    """Pin the transport seam to committed bodies and record every URL requested.

    ``page`` and ``bodies`` replace the committed fixtures with in-memory ones,
    which is how the nested-schedule tests serve a page and a body set that no
    other module needs — through this one seam rather than a second mechanism.
    """
    requested: list[str] = []

    def fetch_bytes(
        source: ScreenerSessionSource,
        url: str,
        credentials: ScreenerCredentials,
        *,
        xhr: bool = False,
    ) -> tuple[int, bytes]:
        del source, credentials, xhr
        requested.append(url)
        if "/schedules/" not in url:
            if page is not None:
                return 200, page
            return 200, (_SHELL_PAGE if "SOLOCO" in url else _PAGE).read_bytes()
        schedules_so_far = sum(1 for seen in requested if "/schedules/" in seen)
        if rate_limit_after is not None and schedules_so_far > rate_limit_after:
            raise ScreenerRateLimitedError(f"screener rate-limited {url}")
        if bodies is not None:
            return 200, bodies[_schedule_key(url)]
        return 200, _schedule_fixture(url, swap=swap)

    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)
    return requested


def _config() -> ScreenerSessionConfig:
    """A config carrying a fixture cookie; the seam never reads its value."""
    return ScreenerSessionConfig(
        credentials=ScreenerCredentials(session_cookie=SecretStr(_SESSION_TOKEN)),
        min_request_spacing_seconds=0,
    )


def _read(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> tuple[Any, list[str]]:
    """Read the fixture page and its schedules through the real code path."""
    requested = _serve(monkeypatch, **kwargs)
    source = ScreenerSessionSource(_config())
    page = source.fetch_company_page(
        symbol="FIXTURECO",
        slug="FIXTURECO",
        basis=Basis.CONSOLIDATED,
        expected_company_id=_COMPANY_ID,
        topology=BasisTopology(consolidated_warehouse_id=992001, standalone_warehouse_id=992002),
    )
    run = read_financials(page, company_id=_COMPANY_ID, sections=ALL_SECTIONS, source=source)
    return run, requested


def _run(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> Any:
    """The run alone, for the tests that do not inspect the request log."""
    return _read(monkeypatch, **kwargs)[0]


# Minimal single-section pages for the ambiguity refusals. Inline rather than
# committed fixtures: each is one deliberate structural defect, and the defect
# is easier to see beside the assertion than in a separate file.
_PAGE_SHELL = """<html><body><main>
  <div data-company-id="991001" data-warehouse-id="992001" id="company-info"></div>
  <section id="balance-sheet"><p class="sub">Consolidated Figures in Rs. Crores</p>
  {body}
  </section></main></body></html>"""

_DUPLICATE_COLUMN_SECTION = """
  <table class="data-table">
    <thead><tr><th class="text"></th>
      <th data-date-key="2026-03-31">Mar 2026</th>
      <th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
    <tbody><tr><td class="text">Borrowings</td><td>100</td><td>999</td></tr></tbody>
  </table>"""

_DUPLICATE_EXPANDER_SECTION = """
  <table class="data-table">
    <thead><tr><th class="text"></th><th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
    <tbody>
      <tr><td class="text"><button
        onclick="Company.showSchedule('Borrowings', 'balance-sheet', this)"
        >Borrowings&nbsp;+</button></td><td>100</td></tr>
      <tr><td class="text"><button
        onclick="Company.showSchedule('Borrowings', 'balance-sheet', this)"
        >Borrowings&nbsp;+</button></td><td>999</td></tr>
    </tbody>
  </table>"""

_DUPLICATE_PARENT_ROW_SECTION = _DUPLICATE_EXPANDER_SECTION


def _page_with(section_body: str) -> str:
    """Wrap one deliberately defective section in the minimum page around it."""
    return _PAGE_SHELL.format(body=section_body)


def _balance_sheet_table() -> Any:
    """The parsed balance-sheet table of the committed fixture page."""
    return read_section(
        parse_document(_PAGE.read_text(encoding="utf-8")),
        Section.BALANCE_SHEET,
        source_id="screener-subscriber",
        file_sha256="0" * 64,
        retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
    )


def _schedule_kwargs(table: Any) -> dict[str, Any]:
    """The fixed arguments for a direct ``read_schedule`` call on that table."""
    return {
        "section": Section.BALANCE_SHEET,
        "parent": "Borrowings",
        "basis": Basis.CONSOLIDATED,
        "url": "https://www.screener.in/api/company/991001/schedules/?parent=Borrowings",
        "document_id": "/api/company/991001/schedules/?parent=Borrowings",
        "body_sha256": "0" * 64,
        "periods": table.periods,
        "source_id": "screener-subscriber",
        "retrieved_at": datetime(2026, 8, 26, tzinfo=UTC),
    }


def _section(run: Any, section: Section) -> Any:
    """The parsed table for one section of a run."""
    return next(table for table in run.artifact.sections if table.section is section)


def _row(run: Any, section: Section, label: str) -> Any:
    """One parsed row by its label."""
    return next(row for row in _section(run, section).rows if row.label == label)


def _family(run: Any, section: Section, parent: str) -> Any:
    """One schedule family by the parent row it expands."""
    return next(family for family in _section(run, section).schedules if family.parent == parent)


# --------------------------------------------------------------------------
# Level-3 nested schedules.
#
# A page whose level-2 bodies advertise schedules of their own, served through
# the same seam as the committed fixtures. Inline rather than committed because
# every level-3 test varies one body or one row of the page, and the variation
# is the point of the test. Every figure is invented; only the shapes follow the
# live captures.
# --------------------------------------------------------------------------

NESTED_TRADE_RECEIVABLES = "Trade receivables"
NESTED_MATERIAL_COST = "Material Cost %"

_NESTED_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><title>Fixture Consolidated Ltd</title></head><body>
  <nav class="navbar"><div id="account-dropdown" class="dropdown-menu">
    <a href="/user/account/">Profile</a>
    <form action="/logout/" method="post"><button type="submit">Logout</button></form>
  </div></nav>
  <main>
  <div data-company-id="991001" data-warehouse-id="992001" id="company-info"></div>
  <section id="quarters" class="card card-large">
    <p class="sub">Consolidated Figures in Rs. Crores</p>
    <table class="data-table"><thead><tr><th class="text"></th>
      <th data-date-key="2025-12-31">Dec 2025</th></tr></thead>
      <tbody><tr><td class="text">Sales</td><td>40</td></tr></tbody></table>
  </section>
  <section id="profit-loss" class="card card-large">
    <p class="sub">Consolidated Figures in Rs. Crores</p>
    <table class="data-table"><thead><tr><th class="text"></th>
      <th data-date-key="2025-03-31">Mar 2025</th>
      <th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
      <tbody>
        <tr><td class="text">{sales_cell}</td><td>156</td><td>160</td></tr>
        <tr><td class="text"><button class="button-plain"
          onclick="Company.showSchedule('Expenses', 'profit-loss', this)"
          >Expenses&nbsp;<span class="blue-icon">+</span></button></td><td>130</td><td>134</td></tr>
        <tr><td class="text">Operating Profit</td><td>26</td><td>26</td></tr>
      </tbody></table>
  </section>
  <section id="balance-sheet" class="card card-large">
    <p class="sub">Consolidated Figures in Rs. Crores</p>
    <table class="data-table"><thead><tr><th class="text"></th>
      <th data-date-key="2025-03-31">Mar 2025</th>
      <th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
      <tbody>
        <tr><td class="text"><button class="button-plain"
          onclick="Company.showSchedule('Other Assets', 'balance-sheet', this)"
          >Other Assets&nbsp;<span class="blue-icon">+</span></button></td>
          <td>900</td><td>1,000</td></tr>
        <tr><td class="text"><button class="button-plain"
          onclick="Company.showSchedule('Borrowings', 'balance-sheet', this)"
          >Borrowings&nbsp;<span class="blue-icon">+</span></button></td>
          <td>500</td><td>500</td></tr>
        <tr><td class="text">Total Assets</td><td>1,400</td><td>1,500</td></tr>
      </tbody></table>
  </section>
  <section id="cash-flow" class="card card-large">
    <p class="sub">Consolidated Figures in Rs. Crores</p>
    <table class="data-table"><thead><tr><th class="text"></th>
      <th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
      <tbody><tr><td class="text">Net Cash Flow</td><td>55</td></tr></tbody></table>
  </section>
  <section id="ratios" class="card card-large">
    <p class="sub">Consolidated Figures in Rs. Crores</p>
    <table class="data-table"><thead><tr><th class="text"></th>
      <th data-date-key="2026-03-31">Mar 2026</th></tr></thead>
      <tbody><tr><td class="text">Debtor Days</td><td>28</td></tr></tbody></table>
  </section>
  </main></body></html>"""

_SALES_EXPANDER = (
    '<button class="button-plain" onclick="Company.showSchedule(\'Sales\', '
    '\'profit-loss\', this)">Sales&nbsp;<span class="blue-icon">+</span></button>'
)


def _nested_page(*, sales_expandable: bool = True) -> bytes:
    """The nested-schedule fixture page.

    ``sales_expandable`` false drops the P&L ``Sales`` expander, which is how a
    section with no ``schedule_parent == "Sales"`` row is served — the shape
    that leaves a percent-of-sales identity with no denominator.
    """
    cell = _SALES_EXPANDER if sales_expandable else "Sales"
    return _NESTED_PAGE_TEMPLATE.format(sales_cell=cell).encode("utf-8")


def _nested_call(label: str, section: Section) -> str:
    """The ``isExpandable`` value a level-2 sub-row carries, as the API writes it.

    Double quotes inside the JSON string, unlike the single quotes the page HTML
    uses for its own ``showSchedule`` buttons.
    """
    return f'Company.showSchedule("{label}", "{section.value}", this)'


def _nested_bodies(
    overrides: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[tuple[str, str], bytes]:
    """Every level-2 and level-3 body the nested fixture page's families answer with.

    Keyed by the verbatim ``(section, parent)`` of the request, so a level-3 key
    is the level-2 sub-row label. ``overrides`` replaces or adds one body.
    """
    bodies: dict[tuple[str, str], dict[str, Any]] = {
        ("profit-loss", "Sales"): {"Sales Growth %": {"Mar 2025": "18%", "Mar 2026": "12%"}},
        ("profit-loss", "Expenses"): {
            NESTED_MATERIAL_COST: {
                "Mar 2025": "82%",
                "Mar 2026": "78%",
                "isExpandable": _nested_call(NESTED_MATERIAL_COST, Section.PROFIT_LOSS),
            }
        },
        ("profit-loss", NESTED_MATERIAL_COST): {
            "Raw material cost": {"Mar 2025": "130", "Mar 2026": "128"},
            "Change in inventory": {"Mar 2025": "-3", "Mar 2026": "-3"},
        },
        ("balance-sheet", "Other Assets"): {
            NESTED_TRADE_RECEIVABLES: {
                "Mar 2025": "500",
                "Mar 2026": "560",
                "isExpandable": _nested_call(NESTED_TRADE_RECEIVABLES, Section.BALANCE_SHEET),
            },
            "Inventories": {"Mar 2025": "400", "Mar 2026": "440"},
        },
        ("balance-sheet", NESTED_TRADE_RECEIVABLES): {
            "Receivables over 6m": {"Mar 2025": "120", "Mar 2026": "130"},
            "Receivables under 6m": {"Mar 2025": "400", "Mar 2026": "450"},
            "Prov for Doubtful": {"Mar 2025": "-20", "Mar 2026": "-20"},
        },
        ("balance-sheet", "Borrowings"): {
            "Long term Borrowings": {"Mar 2025": "300", "Mar 2026": "320"},
            "Short term Borrowings": {"Mar 2025": "200", "Mar 2026": "180"},
        },
    }
    bodies.update(overrides or {})
    return {key: json.dumps(body).encode("utf-8") for key, body in bodies.items()}


def _nested_read(
    monkeypatch: pytest.MonkeyPatch,
    *,
    overrides: dict[tuple[str, str], dict[str, Any]] | None = None,
    sales_expandable: bool = True,
    **kwargs: Any,
) -> tuple[Any, list[str]]:
    """Read the nested fixture page and its schedules, with the request log."""
    return _read(
        monkeypatch,
        page=_nested_page(sales_expandable=sales_expandable),
        bodies=_nested_bodies(overrides),
        **kwargs,
    )


def _nested(family: Any, parent: str) -> Any:
    """One nested family of a level-2 family, by the sub-row label it expands."""
    return next(child for child in family.nested if child.parent == parent)
