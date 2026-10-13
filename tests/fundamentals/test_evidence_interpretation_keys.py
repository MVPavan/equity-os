"""What an interpretation that cannot complete its key keeps, and how it reaches constructions.

Over marked copies of the retained Apar Q2 FY26 captures: an INVALID interpretation keeps every
key part its evidence establishes and never invents unit semantics; a unit whose prefix is
rebound to a foreign namespace is not ISO 4217; a line two entries match makes every
construction it could feed INVALID rather than "operand not presented".
"""

from __future__ import annotations

import pytest
from evidence_support import (
    Q2_QUARTER,
    XBRL_ONLY,
    Ingest,
    constructed,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    policy,
)
from retained_support import MarkedEdit

from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import InterpretationReason, InterpretationStatus
from fundamentals.contracts.measurement_key import DimensionSet
from fundamentals.contracts.observation import AccountingFramework

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

# Q2 FY26 instance (sha256 90baae0b): Conductors segment revenue, OneReportable1D, whose
# DescriptionOfReportableSegment is "Conductors".
CONDUCTORS_REVENUE = (
    b'<in-capmkt:SegmentRevenue contextRef="OneReportable1D" decimals="-5" unitRef="INR">'
)
ISO4217_BINDING = b'xmlns:iso4217="http://www.xbrl.org/2003/iso4217"'
TAX_EXPENSE_RULE = "pdf.tax_expense"


def test_unit_mismatch_keeps_the_evidenced_key_parts(ingest: Ingest) -> None:
    """Conductors revenue filed per share: INVALID UNIT_MISMATCH that still names its
    canonical id, quarter, basis, framework, entry and segment member, with no key (so no
    currency or value kind is claimed) and no value.
    """
    edit = MarkedEdit(
        label="conductors-revenue-per-share",
        find=CONDUCTORS_REVENUE,
        replace=CONDUCTORS_REVENUE.replace(b'unitRef="INR"', b'unitRef="INRPerShare"'),
    )
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    (row,) = [
        item
        for item in ingest.interpretations(report)
        if item.mapping_entry_id == "capmkt.segment_revenue"
        and item.period == Q2_QUARTER
        and item.status is InterpretationStatus.INVALID
    ]
    assert row.reason is InterpretationReason.UNIT_MISMATCH
    assert row.canonical_id == "segment_revenue"
    assert (row.basis, row.framework) == (Basis.CONSOLIDATED, AccountingFramework.IND_AS)
    assert row.dimensions == DimensionSet.of(
        {"elimination_basis": "PRE_ELIMINATION", "segment": "conductors"}
    )
    assert row.key is None and row.value is None


def test_rebound_iso4217_prefix_is_not_a_currency(ingest: Ingest) -> None:
    """With ``iso4217`` bound to a foreign URI, "iso4217:INR" names no ISO currency: Q2
    revenue (filed 57,154,200,000 under unit INR) is INVALID UNIT_MISMATCH, never INR.
    """
    edit = MarkedEdit(
        label="iso4217-rebound",
        find=ISO4217_BINDING,
        replace=b'xmlns:iso4217="http://example.com/not-iso4217"',
    )
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    occurrences = ingest.occurrences(report)
    (revenue,) = [
        item
        for item in ingest.interpretations(report)
        if item.mapping_entry_id == "capmkt.revenue_from_operations"
        and item.period == Q2_QUARTER
        and item.occurrence_id is not None
        and occurrences[item.occurrence_id].native_context["context_ref"] == "OneD"
    ]
    assert revenue.status is InterpretationStatus.INVALID
    assert revenue.reason is InterpretationReason.UNIT_MISMATCH
    assert revenue.key is None and revenue.value is None
    assert occurrences[revenue.occurrence_id or 0].raw_unit == "{http://example.com/not-iso4217}INR"


def test_ambiguous_operand_makes_the_construction_invalid(ingest: Ingest) -> None:
    """ "(a) Current tax" (Q2 quarter 89.13) matched by two entries is ambiguous, so the tax
    expense construction 89.13 + (0.30) + "-" is INVALID — not MAPPED with the current-tax
    operand reported as not presented.
    """
    current = ingest.mapping_set.entry("pdf.current_tax")
    unrestricted = current.model_copy(
        update={
            "entry_id": "pdf.current_tax_unrestricted",
            "canonical_id": "tax_discontinued",
            "selector": current.selector.model_copy(update={"section": None}),
        }
    )
    both = ingest.mapping_set.model_copy(
        update={
            "version": "v1-test-ambiguous-operand",
            "entries": (*ingest.mapping_set.entries, unrestricted),
        }
    )
    report = ingest.run(ingest.intake({Representation.PDF: "results"}), mapping_set=both)
    rows = ingest.interpretations(report)
    occurrences = ingest.occurrences(report)
    (ambiguous,) = [
        item
        for item in rows
        if item.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
        and item.occurrence_id is not None
        and occurrences[item.occurrence_id].native_field == "(a) Current tax"
        and occurrences[item.occurrence_id].raw_value_text == "89.13"
    ]
    tax = constructed(rows, TAX_EXPENSE_RULE, Q2_QUARTER)
    assert tax.status is InterpretationStatus.INVALID and tax.value is None
    assert tax.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert ambiguous.interpretation_id in tax.operand_interpretation_ids
