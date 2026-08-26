"""Shared fixtures and seams for the ``screener-financials`` test modules.

No test opens a socket: the transport seam defined here is replaced with
committed synthetic bodies, and every helper below exists so the two test
modules exercise the same one.
"""

from __future__ import annotations

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


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    swap: tuple[str, str] | None = None,
    rate_limit_after: int | None = None,
) -> list[str]:
    """Pin the transport seam to committed bodies and record every URL requested."""
    requested: list[str] = []

    def fetch_bytes(
        source: ScreenerSessionSource, url: str, credentials: ScreenerCredentials
    ) -> tuple[int, bytes]:
        del source, credentials
        requested.append(url)
        if "/schedules/" not in url:
            return 200, (_SHELL_PAGE if "SOLOCO" in url else _PAGE).read_bytes()
        schedules_so_far = sum(1 for seen in requested if "/schedules/" in seen)
        if rate_limit_after is not None and schedules_so_far > rate_limit_after:
            raise ScreenerRateLimitedError(f"screener rate-limited {url}")
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
