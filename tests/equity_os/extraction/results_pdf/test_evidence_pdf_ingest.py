"""Results-PDF ingestion through marked copies of the retained Q2 FY26 PDF (D1a Task 5).

Each marked copy redacts words of the retained PDF's text layer under ``tmp_path`` and is
ingested end to end, so the outcome is what a real filing with that defect would store.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pymupdf
import pytest
from evidence_support import (
    Q2_QUARTER,
    Ingest,
    apar_pdf_specs,
    by_occurrence,
    constructed,
    dictionary,
    ingest,
    mapping_set,
    one,
    policy,
    rows_of,
)
from retained_support import CONSOLIDATED_X_MAX, PdfRedaction, apar_original, marked_pdf

from equity_os.contracts.measurement.canonical import Representation, StatementFamily
from equity_os.contracts.measurement.evidence import (
    AttemptStage,
    InterpretationReason,
    InterpretationStatus,
)
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.extraction.results_pdf.pdf_adapter import header_period
from equity_os.normalisation.mapping.interpret import TRACE_REASON

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

PDF = {Representation.PDF: "results"}
CURRENT_TAX_Q2 = "89.13"
UNREADABLE = "???"
# Page 7's consolidated cash-flow header prints this date once; the standalone header
# prints it as "30-Sep•2025".
CF_CONSOLIDATED_H1 = "30-Sep-2025"
OPENING_CASH_H1 = "686.42"
# As wide as the printed date, so the column keeps its extent and super-header.
IMPOSSIBLE_H1 = "on 31-Feb-2025"


def test_unreadable_row_is_kept_and_invalidates_its_construction(ingest: Ingest) -> None:
    """Current-tax cells reading ``???`` stay occurrences, interpret INVALID, and make the
    tax construction INVALID — an unreadable operand is never treated as absent or zero.
    """
    unreadable = marked_pdf(
        ingest.tmp_path,
        "unreadable-current-tax",
        PdfRedaction(page=3, row_of=CURRENT_TAX_Q2, x_max=CONSOLIDATED_X_MAX, replace=UNREADABLE),
    )
    report = ingest.run(ingest.intake(PDF, marked={Representation.PDF: unreadable}))
    occurrences = ingest.occurrences(report)
    rows = by_occurrence(ingest.interpretations(report))
    cells = [item for item in occurrences.values() if item.native_field == "(a) Current tax"]
    assert len(cells) == 6 and {item.raw_value_text for item in cells} == {UNREADABLE}
    for cell in cells:
        assert cell.occurrence_id is not None
        row = rows[cell.occurrence_id]
        assert row.status is InterpretationStatus.INVALID
        assert row.reason is InterpretationReason.UNREADABLE_CELL and row.value is None
    tax = constructed(ingest.interpretations(report), "pdf.tax_expense", Q2_QUARTER)
    assert tax.status is InterpretationStatus.INVALID and tax.value is None


def test_unlabelled_profit_attribution_is_invalid(ingest: Ingest) -> None:
    """The first owners row has no evidenced attribution heading; ordinal order cannot prove it."""
    report = ingest.run(ingest.intake(PDF))
    rows = by_occurrence(ingest.interpretations(report))
    cells = [
        item
        for item in ingest.occurrences(report).values()
        if item.native_field == "(a) Owners of the Company" and item.raw_value_text == "251.70"
    ]
    assert len(cells) == 1
    cell = cells[0]
    assert cell.occurrence_id is not None
    assert rows[cell.occurrence_id].status is InterpretationStatus.INVALID
    assert rows[cell.occurrence_id].reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    oci = one(
        ingest.interpretations(report), "oci_attributable_owners", Q2_QUARTER, Representation.PDF
    )
    assert oci.value == Decimal("229500000")


def test_removed_first_owner_row_cannot_relabel_oci_profit(ingest: Ingest) -> None:
    document = pymupdf.open(apar_original("FY26_Q2", "results"))
    page = document[2]
    words = page.get_text("words")
    # The same value also appears in profit after tax: remove the later owners row.
    centre = max((word[1] + word[3]) / 2 for word in words if word[4] == "251.70")
    for word in words:
        if abs((word[1] + word[3]) / 2 - centre) <= 3:
            page.add_redact_annot(pymupdf.Rect(word[0], word[1] + 0.5, word[2], word[3] - 0.5))
    page.apply_redactions(images=0, graphics=0)
    removed = ingest.tmp_path / "no-first-owner.pdf"
    document.save(removed)
    document.close()
    report = ingest.run(ingest.intake(PDF, marked={Representation.PDF: removed}))
    rows = ingest.interpretations(report)
    assert not [
        row
        for row in rows
        if row.canonical_id == "profit_attributable_owners" and row.value is not None
    ]
    assert one(rows, "oci_attributable_owners", Q2_QUARTER, Representation.PDF).value == Decimal(
        "229500000"
    )


def test_ambiguous_blank_row_invalidates_mapped_key_and_construction(ingest: Ingest) -> None:
    blank = marked_pdf(
        ingest.tmp_path,
        "blank-tax-both-bases",
        PdfRedaction(page=3, row_of="89.13", x_max=CONSOLIDATED_X_MAX),
        PdfRedaction(page=3, row_of="88.15", x_min=570),
    )
    report = ingest.run(ingest.intake(PDF, marked={Representation.PDF: blank}))
    rows = ingest.interpretations(report)
    current = one(rows, "current_tax", Q2_QUARTER, Representation.PDF)
    assert current.status is InterpretationStatus.INVALID and current.key is not None
    assert current.value is None
    assert constructed(rows, "pdf.tax_expense", Q2_QUARTER).status is InterpretationStatus.INVALID


def test_b7_pdf_lines_keep_separate_evidenced_context(ingest: Ingest) -> None:
    report = ingest.run(ingest.intake(PDF))
    rows = ingest.interpretations(report)
    instant = PeriodInterval.at(date(2025, 9, 30))
    expected = {
        "derivative_financial_assets_noncurrent": "24900000",
        "derivative_financial_assets_current": "796900000",
        "derivative_financial_liabilities_current": "250800000",
    }
    for canonical_id, value in expected.items():
        assert one(rows, canonical_id, instant, Representation.PDF).value == Decimal(value)
    liabilities = rows_of(rows, "inter_segment_liabilities", instant, Representation.PDF)
    assert len(liabilities) == 2 and {row.value for row in liabilities} == {Decimal("6565900000")}
    assert (
        one(rows, "derivative_financial_liabilities_noncurrent", instant, Representation.PDF).value
        is None
    )
    assert one(rows, "segment_other_elimination", Q2_QUARTER, Representation.PDF).value == Decimal(
        "-41100000"
    )


def test_removed_tax_line_leaves_the_construction_without_a_value(ingest: Ingest) -> None:
    """With the earlier-years line gone the tax construction has no value, never a zero."""
    removed = marked_pdf(
        ingest.tmp_path, "no-earlier-years", PdfRedaction(page=3, row_of="earlier")
    )
    report = ingest.run(ingest.intake(PDF, marked={Representation.PDF: removed}))
    rows = ingest.interpretations(report)
    assert not [row for row in rows if row.canonical_id == "tax_earlier_years"]
    tax = constructed(rows, "pdf.tax_expense", Q2_QUARTER)
    assert tax.value is None and tax.interval is None and tax.key is not None
    assert "earlier_years" in str(tax.transform_trace[TRACE_REASON])
    # The printed current and deferred lines still map: only the missing operand withholds.
    assert one(rows, "current_tax", Q2_QUARTER, Representation.PDF).value == Decimal("891300000")


def test_unreadable_header_leaves_its_cells_period_ambiguous(ingest: Ingest) -> None:
    """A cash-flow column header that reads no date gives its cells no period, so opening
    cash cannot be keyed to 31 March 2025 and is PERIOD_AMBIGUOUS through ingestion.
    """
    garbled = marked_pdf(
        ingest.tmp_path,
        "garbled-cf-header",
        PdfRedaction(
            page=7, row_of=CF_CONSOLIDATED_H1, words=(CF_CONSOLIDATED_H1,), replace=IMPOSSIBLE_H1
        ),
    )
    report = ingest.run(ingest.intake(PDF, marked={Representation.PDF: garbled}))
    rows = by_occurrence(ingest.interpretations(report))
    (cell,) = [
        item
        for item in ingest.occurrences(report).values()
        if item.anchor["page"] == 7 and item.raw_value_text == OPENING_CASH_H1
    ]
    assert cell.period is None and cell.occurrence_id is not None
    row = rows[cell.occurrence_id]
    assert row.status is InterpretationStatus.PERIOD_AMBIGUOUS
    assert row.key is None and row.value is None


def test_header_with_an_invalid_date_candidate_is_undeterminable() -> None:
    """A header naming a valid and an impossible date is not resolved to the valid one."""
    assert header_period("Quarter ended 30-Sep-2025 31-Feb-2025") is None
    assert header_period("30-Sep-20#5 Reviewed") is None
    assert header_period("Quarter ended 30-Sep-2025") == (Q2_QUARTER, 3)


def test_unlocated_present_family_is_a_package_owned_failure(ingest: Ingest) -> None:
    """XBRL establishes the P&L; a PDF whose P&L block cannot be found records the family
    failure for the assembled package, separately from capture-only extraction reuse.
    """
    specs = dict(apar_pdf_specs())
    specs[StatementFamily.PL] = specs[StatementFamily.PL].model_copy(
        update={"title_markers": ("no such statement title",)}
    )
    report = ingest.run(ingest.intake(), pdf_specs=specs)
    pdf = [a for a in report.attempts if a.representation is Representation.PDF]
    (overall,) = [a for a in pdf if a.statement_family is None]
    (failed,) = [a for a in pdf if a.statement_family is StatementFamily.PL]
    assert overall.stage is failed.stage is AttemptStage.EXTRACTION
    assert failed.outcome is ExtractionOutcome.PARSE_FAILED
    assert failed.attempted_at >= overall.attempted_at
    assert failed.package_id == report.package_id and overall.package_id is None
    assert failed.capture == overall.capture and overall.capture is not None
    assert overall.capture.capture_ref_id is not None
    generation = ingest.repository.list_generation_attempts(
        overall.capture.capture_ref_id,
        overall.extractor_version,
        entity_id=ingest.entity_id,
        period_end=overall.period_end,
        basis=overall.basis,
        framework=overall.framework,
    )
    assert failed.attempt_id not in {a.attempt_id for a in generation}
    assert StatementFamily.PL in ingest.package(report).statements_present
