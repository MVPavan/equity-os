"""Combined standalone-and-consolidated results table: scope-confined column choice.

Some filers (e.g. HFCL) print the standalone and consolidated column groups side by
side in one table, under spread-out ``Standalone`` / ``Consolidated`` super-headers.
The current-quarter end date then appears in BOTH groups, so the naive "leftmost
period-end column" would bind the STANDALONE quarter while the observation is stamped
``scope=CONSOLIDATED`` — a wrong-scope value that pollutes provenance. These tests
drive the parser on a synthetic combined table (mirroring the real HFCL geometry:
standalone revenue 960.94 vs consolidated 1011.95) and assert the CONSOLIDATED
column is chosen, the standalone value is never emitted, and a consolidated block
that carries no current quarter fails closed rather than falling back to standalone.
No bytes leave the process.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from fundamentals.api.config import PdfParseConfig
from fundamentals.contracts.observation import AccountingFramework, Scope
from fundamentals.extract.pdf_number_parser import (
    NumberParseError,
    PdfParseSpec,
    extract_consolidated_pl,
)
from fundamentals.ingest.pdf_source import load_pdf

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_RETRIEVED_AT = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
INCOME = "in-bse-fin:Income"
PBT = "in-bse-fin:ProfitBeforeTax"

# Standalone (left block) and consolidated (right block) current-quarter values, taken
# from the real HFCL Q3FY25 filing so the test pins the exact wrong-scope regression.
_STANDALONE_VALUES = {
    "revenue": "960.94",
    "income": "981.95",
    "pbt": "106.87",
    "pfp": "80.00",
    "eps": "0.54",
}
_CONSOLIDATED_VALUES = {
    "revenue": "1011.95",
    "income": "1031.99",
    "pbt": "100.26",
    "pfp": "75.00",
    "eps": "2.19",
}

# Column x-centres: standalone block on the left, consolidated block on the right, each
# with a quarter and a year-to-date column that share the same period-end date.
_SA_Q3_X = 250.0
_SA_YTD_X = 330.0
_CONS_Q3_X = 520.0
_CONS_YTD_X = 600.0


def _spec() -> PdfParseSpec:
    config = PdfParseConfig()
    return PdfParseSpec(
        scope_marker=config.scope_marker,
        statement_confirmations=config.statement_confirmations,
        anchor_label=config.anchor_label,
        target_lines=config.target_lines,
        entity_scheme="nse-symbol",
        entity_id="HFCLLIKE",
        currency="INR",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
    )


def _write_combined_statement(
    path: Path, *, cons_q3_date: str = "31-12-2024", cons_ytd_date: str = "31-12-2024"
) -> str:
    """Write a synthetic combined standalone+consolidated SEBI statement; return its sha256.

    The title names both scopes (and carries title words, so it is not mistaken for a
    column-header row); a super-header row prints ``Standalone`` centred over the left
    block and ``Consolidated`` over the right; each block has a quarter and a
    year-to-date column whose printed date is the current quarter end. The consolidated
    dates are overridable so a test can make the consolidated block carry no current
    quarter and prove the parser fails closed.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text(
        (60, 60),
        "STATEMENT OF UNAUDITED STANDALONE AND CONSOLIDATED FINANCIAL RESULTS "
        "FOR THE QUARTER AND NINE MONTHS ENDED 31 DECEMBER 2024",
        fontsize=8,
    )
    page.insert_text((60, 80), "(Rs. in crore)", fontsize=8)
    page.insert_text((270, 100), "Standalone", fontsize=8)
    page.insert_text((535, 100), "Consolidated", fontsize=8)
    dates = {
        _SA_Q3_X: "31-12-2024",
        _SA_YTD_X: "31-12-2024",
        _CONS_Q3_X: cons_q3_date,
        _CONS_YTD_X: cons_ytd_date,
    }
    for x, text in dates.items():
        page.insert_text((x, 120), text, fontsize=8)

    rows: tuple[tuple[float, str, str], ...] = (
        (150, "Revenue from operations", "revenue"),
        (170, "Total income", "income"),
        (190, "Profit before tax", "pbt"),
        (210, "Profit for the period", "pfp"),
        (240, "Basic", "eps"),
    )
    for y, label, key in rows:
        page.insert_text((60, y), label, fontsize=8)
        page.insert_text((_SA_Q3_X, y), _STANDALONE_VALUES[key], fontsize=8)
        page.insert_text((_SA_YTD_X, y), "0", fontsize=8)
        page.insert_text((_CONS_Q3_X, y), _CONSOLIDATED_VALUES[key], fontsize=8)
        page.insert_text((_CONS_YTD_X, y), "0", fontsize=8)
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(path: Path, sha: str) -> list:  # type: ignore[type-arg]
    loaded = load_pdf(source_id="synth-combined", path=path, expected_sha256=sha)
    return extract_consolidated_pl(loaded, spec=_spec(), retrieved_at=_RETRIEVED_AT)


def test_combined_table_binds_consolidated_current_quarter_not_standalone(tmp_path: Path) -> None:
    pdf = tmp_path / "combined.pdf"
    sha = _write_combined_statement(pdf)
    by_concept = {obs.concept_qname: obs.normalized_value for obs in _extract(pdf, sha)}
    # The consolidated current-quarter column is chosen, never the standalone one.
    assert by_concept[REVENUE] == Decimal("1011.95")
    assert by_concept[INCOME] == Decimal("1031.99")
    assert by_concept[PBT] == Decimal("100.26")


def test_combined_table_never_emits_a_standalone_value_under_consolidated_scope(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "combined.pdf"
    sha = _write_combined_statement(pdf)
    emitted = {obs.normalized_value for obs in _extract(pdf, sha)}
    standalone_values = {Decimal(value) for value in _STANDALONE_VALUES.values()}
    # No standalone-column value may appear among the emitted consolidated observations.
    assert emitted.isdisjoint(standalone_values), emitted & standalone_values


def test_combined_table_fails_closed_when_consolidated_block_has_no_current_quarter(
    tmp_path: Path,
) -> None:
    # The standalone block still prints the Dec-2024 quarter, but the consolidated block
    # does not: the parser must fail closed (no consolidated current column) rather than
    # fall back to the standalone quarter it can see.
    pdf = tmp_path / "combined.pdf"
    sha = _write_combined_statement(pdf, cons_q3_date="31-12-2023", cons_ytd_date="31-03-2024")
    with pytest.raises(NumberParseError, match="current-quarter column"):
        _extract(pdf, sha)
