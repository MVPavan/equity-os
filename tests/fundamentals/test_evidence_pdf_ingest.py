"""Results-PDF ingestion through marked copies of the retained Q2 FY26 PDF (D1a Task 5).

Each marked copy redacts words of the retained PDF's text layer under ``tmp_path`` and is
ingested end to end, so the outcome is what a real filing with that defect would store.
"""

from __future__ import annotations

from decimal import Decimal

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
)
from retained_support import CONSOLIDATED_X_MAX, PdfRedaction, marked_pdf

from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation, StatementFamily
from fundamentals.contracts.evidence import (
    AttemptStage,
    InterpretationReason,
    InterpretationStatus,
)
from fundamentals.evidence.interpret import TRACE_REASON
from fundamentals.evidence.pdf_adapter import header_period

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


def test_unlocated_present_family_fails_inside_the_pdf_generation(ingest: Ingest) -> None:
    """XBRL establishes the P&L; a PDF whose P&L block cannot be found records the family
    failure in the PDF's own attempt generation (same time, capture-owned, same capture).
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
    assert failed.attempted_at == overall.attempted_at
    assert failed.package_id is None and overall.package_id is None
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
    assert failed.attempt_id in {a.attempt_id for a in generation}
    assert StatementFamily.PL in ingest.package(report).statements_present
