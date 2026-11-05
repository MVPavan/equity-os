"""D1a Task 11: statement-page discovery on the retained Apar Q2 FY26 results PDF.

The locator must find the consolidated P&L, balance sheet, cash flow and segment
blocks, keep only the consolidated columns of side-by-side pages, and give every
row its own unit context. The XBRL comparisons below prove the locator read the
right cells; they are not alignment proofs.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from retained_support import (
    CONSOLIDATED_X_MAX,
    REPO_ROOT,
    PdfRedaction,
    apar_original,
    manifest_entry,
    marked_pdf,
)

from equity_os.contracts.measurement.canonical import Basis, StatementFamily, ValueKind
from equity_os.contracts.measurement.interval import Interval
from equity_os.extraction.results_pdf.pdf_header_text import normalize_text_tokens
from equity_os.extraction.results_pdf.pdf_source import LoadedPdf, compute_file_sha256, load_pdf
from equity_os.extraction.results_pdf.pdf_statement_pages import (
    PdfStatementRow,
    StatementLocation,
    UnitScope,
    extract_statement_rows,
    locate_statement_pages,
    specs_from_config,
)
from equity_os.extraction.xbrl.xbrl_parser import RawXbrlFact, iter_raw_facts
from equity_os.extraction.xbrl.xbrl_taxonomies import _ALL_TAXONOMIES
from equity_os.interface.entry.config import PdfParseConfig, load_config

pytestmark = pytest.mark.retained

Q2 = "FY26_Q2"
Q3 = "FY26_Q3"
RESULTS = "results"
XBRL = "xbrl-consolidated"
CONSOLIDATED_MARKER = "Consolidated"
CRORE_DECIMALS = 2
CRORE_SCALE = 7
SIDE_BY_SIDE_PAGES = {
    StatementFamily.PL: 3,
    StatementFamily.BALANCE_SHEET: 6,
    StatementFamily.CASH_FLOW: 7,
}
# Rows of the consolidated P&L block on page 3 of the retained Q2 FY26 PDF, counted by hand
# from the printed statement (header and audit-status lines excluded).
Q2_PL_ROWS = 36


def _pdf(quarter: str) -> LoadedPdf:
    """Load a retained results PDF against its pinned hash."""
    entry = manifest_entry(quarter, RESULTS)
    return load_pdf(
        source_id=f"aparinds-{quarter}-results",
        path=apar_original(quarter, RESULTS),
        expected_sha256=entry["sha256"],
    )


def _issuer_parse(quarter: str) -> PdfParseConfig:
    """The issuer config's ``pdf_parse`` block for one quarter."""
    name = f"aparinds-{quarter.lower().replace('_', '-')}.yaml"
    return load_config(REPO_ROOT / "config" / "runs" / name).pdf_parse


@pytest.fixture(scope="module")
def q2_pdf() -> LoadedPdf:
    """The retained Q2 FY26 results PDF."""
    return _pdf(Q2)


@pytest.fixture(scope="module")
def q2_locations(q2_pdf: LoadedPdf) -> dict[StatementFamily, StatementLocation | None]:
    """Consolidated locations under the issuer's declared markers."""
    specs = specs_from_config(_issuer_parse(Q2))
    return dict(locate_statement_pages(q2_pdf, specs, basis=Basis.CONSOLIDATED))


@pytest.fixture(scope="module")
def q2_facts() -> tuple[RawXbrlFact, ...]:
    """Every fact of the retained Q2 FY26 consolidated XBRL instance."""
    body = Path(apar_original(Q2, XBRL)).read_bytes()
    return iter_raw_facts(body, taxonomies=_ALL_TAXONOMIES).facts


def _rows(
    pdf: LoadedPdf,
    locations: dict[StatementFamily, StatementLocation | None],
    family: StatementFamily,
) -> tuple[PdfStatementRow, ...]:
    """Rows of one located family, failing when it was not located."""
    location = locations[family]
    assert location is not None, f"{family} not located"
    return extract_statement_rows(pdf, location)


def _row(rows: tuple[PdfStatementRow, ...], label: str) -> PdfStatementRow:
    """The single row whose label tokens contain ``label``'s tokens."""
    wanted = " ".join(normalize_text_tokens(label))
    found = [row for row in rows if wanted in " ".join(normalize_text_tokens(row.label))]
    assert len(found) == 1, f"{label!r} matched {[row.label for row in found]}"
    return found[0]


def _fact(facts: tuple[RawXbrlFact, ...], concept: str, context: str) -> RawXbrlFact:
    """The single fact for a concept local name in one context."""
    found = [
        f for f in facts if f.concept_qname.endswith(f":{concept}") and f.context_ref == context
    ]
    assert len(found) == 1
    return found[0]


def _matches_xbrl(cell_text: str, fact: RawXbrlFact) -> bool:
    """Whether a crore cell, normalised to INR, lies within the XBRL fact's interval."""
    printed = Decimal(cell_text.replace(",", "")) * Decimal(10) ** CRORE_SCALE
    pdf_interval = Interval.from_precision(printed, CRORE_DECIMALS - CRORE_SCALE)
    assert fact.raw_text is not None and fact.decimals_raw is not None
    xbrl_interval = Interval.from_precision(Decimal(fact.raw_text), int(fact.decimals_raw))
    return pdf_interval.intersects(xbrl_interval)


def test_all_four_consolidated_blocks_are_located(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None]
) -> None:
    """P&L, BS, CF and segment are each found on a page carrying the consolidated marker."""
    pages = {family: location.page for family, location in q2_locations.items() if location}
    assert pages == {**SIDE_BY_SIDE_PAGES, StatementFamily.SEGMENT: 4}
    for page in pages.values():
        assert CONSOLIDATED_MARKER.lower() in q2_pdf.page(page).text.lower()


def test_side_by_side_pages_return_only_consolidated_columns(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None]
) -> None:
    """Basis binds per column: standalone columns are counted as excluded, never returned."""
    for family, page in SIDE_BY_SIDE_PAGES.items():
        location = q2_locations[family]
        assert location is not None and location.page == page
        assert location.excluded_columns == len(location.columns)
        for column in location.columns:
            assert column.basis is Basis.CONSOLIDATED
            assert CONSOLIDATED_MARKER in column.super_header_text
    current_tax = _row(_rows(q2_pdf, q2_locations, StatementFamily.PL), "(a) Current tax")
    assert current_tax.cells[0].raw_text == "89.13"
    assert "88.15" not in {cell.raw_text for cell in current_tax.cells}


def test_cash_flow_is_found_by_its_page_seven_title(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None]
) -> None:
    """The retained page-7 wording "Statement of cash flows" is a title marker."""
    location = q2_locations[StatementFamily.CASH_FLOW]
    assert location is not None and location.page == 7
    spec = specs_from_config(_issuer_parse(Q2))[StatementFamily.CASH_FLOW]
    by_title = {
        title: locate_statement_pages(
            q2_pdf,
            {StatementFamily.CASH_FLOW: spec.model_copy(update={"title_markers": (title,)})},
            basis=Basis.CONSOLIDATED,
        )[StatementFamily.CASH_FLOW]
        for title in ("Statement of cash flows", "Cash Flow Statement")
    }
    assert by_title["Statement of cash flows"] == location
    # "cash flow statement" appears on page 7 only inside the notes, below the block.
    assert by_title["Cash Flow Statement"] is None


def test_pl_rows_carry_crore_and_eps_rows_rupees_per_share(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None]
) -> None:
    """Units resolve per row: crore above the EPS marker, rupees per share under it."""
    rows = _rows(q2_pdf, q2_locations, StatementFamily.PL)
    basic = _row(rows, "Basic")
    assert basic.unit is not None and basic.unit.scope is UnitScope.SUBSECTION
    assert (basic.unit.raw_scale, basic.unit.value_kind) == (0, ValueKind.PER_SHARE_AMOUNT)
    assert basic.cells[0].raw_text == "62.66"
    above = [row for row in rows if row.line < (basic.unit_line or 0)]
    assert above
    for row in above:
        assert row.unit is not None and row.unit.scope is UnitScope.PAGE
        assert (row.unit.raw_scale, row.unit.value_kind) == (CRORE_SCALE, ValueKind.CURRENCY_AMOUNT)


def test_balance_sheet_unit_needs_the_declared_variant(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None]
) -> None:
    """Page 6 prints "(Rs. in crones)": declared, every row has it; undeclared, none has a unit."""
    declared = _rows(q2_pdf, q2_locations, StatementFamily.BALANCE_SHEET)
    assert declared and all(
        row.unit is not None and row.unit.text == "Rs. in crones" for row in declared
    )
    default_specs = specs_from_config(PdfParseConfig())
    bare = locate_statement_pages(q2_pdf, default_specs, basis=Basis.CONSOLIDATED)
    location = bare[StatementFamily.BALANCE_SHEET]
    assert location is not None
    assert all(row.unit is None for row in extract_statement_rows(q2_pdf, location))


def test_balance_sheet_total_assets_matches_xbrl(
    q2_pdf: LoadedPdf,
    q2_locations: dict[StatementFamily, StatementLocation | None],
    q2_facts: tuple[RawXbrlFact, ...],
) -> None:
    """The "TOTAL ASSETS" row at 2025-09-30 matches XBRL ``Assets`` 113,125,300,000 INR."""
    total = _row(_rows(q2_pdf, q2_locations, StatementFamily.BALANCE_SHEET), "TOTAL ASSETS")
    assets = _fact(q2_facts, "Assets", "OneI")
    assert assets.raw_text == "113125300000"
    assert "30-Sep-2025" in total.cells[0].column_header
    assert _matches_xbrl(total.cells[0].raw_text, assets)


def test_cash_flow_opening_and_closing_cash_match_xbrl(
    q2_pdf: LoadedPdf,
    q2_locations: dict[StatementFamily, StatementLocation | None],
    q2_facts: tuple[RawXbrlFact, ...],
) -> None:
    """Closing cash matches 2025-09-30 (3,093,900,000 INR), opening 2025-03-31 (6,864,200,000)."""
    rows = _rows(q2_pdf, q2_locations, StatementFamily.CASH_FLOW)
    closing = _row(rows, "Cash and cash equivalents at the end of the year")
    opening = _row(rows, "Cash and cash equivalents at the beginning of the year")
    concept = "CashAndCashEquivalentsCashFlowStatement"
    closing_fact = _fact(q2_facts, concept, "OneI")
    opening_fact = _fact(q2_facts, concept, "PY_I")
    assert (closing_fact.raw_text, opening_fact.raw_text) == ("3093900000", "6864200000")
    assert _matches_xbrl(closing.cells[0].raw_text, closing_fact)
    assert _matches_xbrl(opening.cells[0].raw_text, opening_fact)


def test_segment_revenue_rows_match_xbrl_members(
    q2_pdf: LoadedPdf,
    q2_locations: dict[StatementFamily, StatementLocation | None],
    q2_facts: tuple[RawXbrlFact, ...],
) -> None:
    """One revenue row per evidenced segment plus the inter-segment line; quarter values match."""
    rows = _rows(q2_pdf, q2_locations, StatementFamily.SEGMENT)
    total_line = _row(rows, "Total segment revenue").line
    revenue_rows = [row for row in rows if row.line < total_line]
    members = {
        (fact.raw_text or "").strip(): fact.context_ref
        for fact in q2_facts
        if fact.concept_qname.endswith(":DescriptionOfReportableSegment")
        and fact.context_ref.startswith("OneReportable")
        and fact.context_ref.removeprefix("OneReportable")[:-1].isdigit()
        and len(fact.context_ref) == len("OneReportable1D")
    }
    assert len(members) == 4
    assert sorted(row.label for row in revenue_rows) == sorted(members)
    for row in revenue_rows:
        fact = _fact(q2_facts, "SegmentRevenue", members[row.label])
        assert _matches_xbrl(row.cells[0].raw_text, fact), row.label
    inter = _row(rows, "Less: Inter-segment revenue")
    assert inter.cells[0].raw_text == "(295.37)"


def test_q3_results_pdf_has_no_balance_sheet_or_cash_flow_block() -> None:
    """The Q3 FY26 results PDF prints neither statement."""
    locations = locate_statement_pages(
        _pdf(Q3), specs_from_config(_issuer_parse(Q3)), basis=Basis.CONSOLIDATED
    )
    assert locations[StatementFamily.BALANCE_SHEET] is None
    assert locations[StatementFamily.CASH_FLOW] is None
    assert locations[StatementFamily.PL] is not None


def test_unreadable_and_blank_rows_are_kept(
    q2_pdf: LoadedPdf, q2_locations: dict[StatementFamily, StatementLocation | None], tmp_path: Path
) -> None:
    """A row whose cells read ``???`` keeps its text, and a printed row with blank cells
    stays a row: dropping either would make an unreadable line look absent.
    """
    original = _rows(q2_pdf, q2_locations, StatementFamily.PL)
    assert len(original) == Q2_PL_ROWS
    balance_sheet = _rows(q2_pdf, q2_locations, StatementFamily.BALANCE_SHEET)
    (financial_assets,) = [row for row in balance_sheet if row.label == "Financial assets"]
    assert financial_assets.cells and all(not cell.raw_text for cell in financial_assets.cells)
    path = marked_pdf(
        tmp_path,
        "unreadable-current-tax",
        PdfRedaction(page=3, row_of="89.13", x_max=CONSOLIDATED_X_MAX, replace="???"),
    )
    marked = load_pdf(source_id="marked-pdf", path=path, expected_sha256=compute_file_sha256(path))
    specs = specs_from_config(_issuer_parse(Q2))
    location = locate_statement_pages(marked, specs, basis=Basis.CONSOLIDATED)[StatementFamily.PL]
    assert location is not None
    rows = extract_statement_rows(marked, location)
    assert len(rows) == Q2_PL_ROWS
    assert [cell.raw_text for cell in _row(rows, "(a) Current tax").cells] == ["???"] * 6


def test_labelled_row_blank_in_both_bases_is_retained(tmp_path: Path) -> None:
    """Removing every figure preserves the current-tax label and ambiguous blank cells."""
    path = marked_pdf(
        tmp_path,
        "blank-current-tax-both-bases",
        PdfRedaction(page=3, row_of="89.13", x_max=CONSOLIDATED_X_MAX),
        PdfRedaction(page=3, row_of="88.15", x_min=570),
    )
    pdf = load_pdf(source_id="marked", path=path, expected_sha256=compute_file_sha256(path))
    location = locate_statement_pages(
        pdf, specs_from_config(_issuer_parse(Q2)), basis=Basis.CONSOLIDATED
    )[StatementFamily.PL]
    assert location is not None
    current = _row(extract_statement_rows(pdf, location), "(a) Current tax")
    assert all(not cell.raw_text for cell in current.cells)
    assert current.classification_ambiguous
