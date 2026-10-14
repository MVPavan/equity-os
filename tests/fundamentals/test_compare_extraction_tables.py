"""D1a.5 acceptance: pair, extraction, derived-extraction and corroboration tables (spec §5).

Every expected status is read from the data spec §5 tables, first matching row wins, or from
hand arithmetic noted beside the case. Operands are constructed (pure table functions); the
derived cases evaluate real dictionary v1 formulas from actual operand states. Fixtures and
each table's parametrized rows live in ``compare_tables_support``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fundamentals.canon.dictionary import DictionaryRow
from fundamentals.compare.definitions import (
    DefinitionRecord,
    DefinitionScope,
    DefinitionSet,
    load_definition_set,
    publish_definition_set,
)
from fundamentals.compare.policy import ComparisonPolicy
from fundamentals.compare.tables import (
    AdjustmentRejection,
    ComparisonSide,
    EvidencedRelationship,
    TaggingAdjustment,
    corroboration_status,
    derived_extraction_status,
    extraction_status,
    pair_outcome,
    validate_adjustment,
)
from fundamentals.compare.triage import structural_class, triage
from fundamentals.contracts.canonical import ApplicabilityStatus, Basis, Representation, ValueKind
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairOutcome,
    ReasonCode,
    SourceState,
    Triage,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.verify.laneb_sensitivity_model import MutationClass

from .canon_formula_support import INR, Q2_FY26, UNPROVEN, key, quarter_context
from .compare_tables_support import (
    DICTIONARY,
    EMPTY,
    EXTRACTION_ROWS,
    FINANCE_RECORD,
    OPEX,
    OPEX_OPERANDS,
    OPEX_PDF_FINANCE,
    OPEX_XBRL,
    PACKAGE,
    PAIR_ROWS,
    PBT_MARGIN,
    PBT_OPERANDS,
    PBT_RECORD,
    PDF_FINANCE_DOWN,
    PDF_REVENUE_ENTRY,
    POLICY,
    REJECTED_ADJUSTMENTS,
    REPO,
    REVENUE,
    ROUNDING,
    SCOPE_CASES,
    TOTAL_RECORD,
    DerivedCase,
    OperandState,
    definitions,
    demonstrated_opex_row,
    derived_side,
    opex_case,
    pdf,
    record,
    side,
)
from .pg_support import PgTestDatabase


@pytest.mark.parametrize(("first", "other", "outcome", "reason"), PAIR_ROWS)
def test_pair_table_rows(
    first: ComparisonSide,
    other: ComparisonSide,
    outcome: PairOutcome,
    reason: ReasonCode | None,
) -> None:
    """Each row of the pair table, first matching row wins."""
    result = pair_outcome(first, other, definitions=EMPTY, policy=POLICY)
    assert (result.outcome, result.reason) == (outcome, reason)
    if outcome in (PairOutcome.MISMATCH, PairOutcome.ANOMALY):
        assert result.triage is not None
    else:
        assert result.triage is None


def test_pair_row4_definition_record_reconciles_and_reports_difference_and_gap() -> None:
    """Row 4: an in-scope record that explains the gap to within tolerance."""
    reconciling = record("R1", DefinitionScope.MAPPING, PDF_REVENUE_ENTRY, "10")
    result = pair_outcome(
        side("1000.0"), pdf("1010.0"), definitions=definitions(reconciling), policy=POLICY
    )
    assert result.outcome is PairOutcome.DEFINITION_DIFFERENCE
    assert result.definition_record_id == "R1"
    assert result.triage is None
    assert result.difference == Decimal("-10.0")
    assert result.interval_gap == Decimal("9.9")


def test_pair_record_that_explains_too_little_does_not_reconcile() -> None:
    """A record explaining 5 of a 9.9 gap leaves the pair outside tolerance (row 5)."""
    partial = record("R1", DefinitionScope.MAPPING, PDF_REVENUE_ENTRY, "5")
    result = pair_outcome(
        side("1000.0"), pdf("1010.0"), definitions=definitions(partial), policy=POLICY
    )
    assert result.outcome is PairOutcome.MISMATCH
    assert result.definition_record_id is None


@pytest.mark.parametrize(
    ("amount", "outcome"),
    [
        pytest.param("10", PairOutcome.DEFINITION_DIFFERENCE, id="explains-exactly"),
        # 1000 + 10.0000000000000000000000000001 is not 1010: the exact intervals do not meet.
        pytest.param("10.0000000000000000000000000001", PairOutcome.MISMATCH, id="overshoots"),
    ],
)
def test_record_amount_is_applied_exactly(amount: str, outcome: PairOutcome) -> None:
    """A record's amount shifts an exact interval exactly, never rounded to Decimal precision."""
    exact = side("1000", decimals=None)
    other = side("1010", decimals=None, entries=(PDF_REVENUE_ENTRY,))
    reconciling = record("R1", DefinitionScope.MAPPING, PDF_REVENUE_ENTRY, amount)
    result = pair_outcome(exact, other, definitions=definitions(reconciling), policy=POLICY)
    assert result.outcome is outcome


def test_evidenced_relationship_is_the_only_way_two_canonical_ids_pair() -> None:
    """Different canonical ids pair only when a relationship names them."""
    other = pdf("1000.0", measurement=key("other_income", Q2_FY26))
    relationship = EvidencedRelationship(
        left_canonical_id="revenue_from_operations",
        right_canonical_id="other_income",
        evidence_ref="disposition:rel-1",
    )
    result = pair_outcome(
        side("1000.0"), other, definitions=EMPTY, policy=POLICY, relationship=relationship
    )
    assert result.outcome is PairOutcome.AGREE


def test_pair_refuses_a_side_without_a_value() -> None:
    """A side with no value is a source state, never a pair outcome."""
    with pytest.raises(ValueError):
        pair_outcome(
            side("1000.0"), pdf(None, state=SourceState.NO_VALUE), definitions=EMPTY, policy=POLICY
        )


# --- Definition scope ---------------------------------------------------------------------------


@pytest.mark.parametrize(("definition", "outcome"), SCOPE_CASES)
def test_definition_records_apply_only_within_scope(
    definition: DefinitionRecord, outcome: PairOutcome
) -> None:
    """A record explains a pair only for its own mapping entry, key or package and row."""
    result = pair_outcome(
        side("1000.0"), pdf("1010.0"), definitions=definitions(definition), policy=POLICY
    )
    assert result.outcome is outcome


def test_out_of_scope_record_leaves_an_unproven_pair_anomalous() -> None:
    """The FILING record for another package does not turn an ANOMALY into a difference."""
    other_package = record("F-other", DefinitionScope.FILING, "99", "10")
    result = pair_outcome(
        side("1000.0"),
        pdf("1010.0", tier=UNPROVEN),
        definitions=definitions(other_package),
        policy=POLICY,
    )
    assert result.outcome is PairOutcome.ANOMALY


# --- Extraction table ---------------------------------------------------------------------------


@pytest.mark.parametrize(("has_pair", "xbrl", "pdf_side", "status", "reason"), EXTRACTION_ROWS)
def test_extraction_table_rows(
    has_pair: bool,
    xbrl: ComparisonSide,
    pdf_side: ComparisonSide,
    status: ExtractionStatus,
    reason: ReasonCode | None,
) -> None:
    """Each row of the extraction table, first matching row wins."""
    result = extraction_status(
        family_has_pair=has_pair, xbrl=xbrl, pdf=pdf_side, definitions=EMPTY, policy=POLICY
    )
    assert (result.status, result.reason) == (status, reason)


def test_extraction_row8_definition_difference_is_a_tagging_difference() -> None:
    """Row 8: a reconciled pair is a tagging difference citing its record."""
    reconciling = record("R1", DefinitionScope.FILING, str(PACKAGE), "10")
    result = extraction_status(
        family_has_pair=True,
        xbrl=side("1000.0"),
        pdf=pdf("1010.0"),
        definitions=definitions(reconciling),
        policy=POLICY,
    )
    assert result.status is ExtractionStatus.TAGGING_DIFFERENCE
    assert result.pair is not None and result.pair.definition_record_id == "R1"


@pytest.mark.parametrize(
    ("xbrl_state", "pdf_state"),
    [
        pytest.param(SourceState.VALUE, SourceState.VALUE, id="identical-values"),
        pytest.param(SourceState.NO_VALUE, SourceState.NO_VALUE, id="neither-has-a-value"),
    ],
)
def test_extraction_refuses_representations_from_different_packages(
    xbrl_state: SourceState, pdf_state: SourceState
) -> None:
    """Extraction compares XBRL and PDF of one package (spec §5); two packages never pair."""
    value = {SourceState.VALUE: "1000.0", SourceState.NO_VALUE: None}
    xbrl = side(value[xbrl_state], state=xbrl_state, package_id=PACKAGE)
    other = side(
        value[pdf_state], state=pdf_state, entries=(PDF_REVENUE_ENTRY,), package_id=PACKAGE + 89
    )
    with pytest.raises(ValueError, match="package"):
        extraction_status(
            family_has_pair=True, xbrl=xbrl, pdf=other, definitions=EMPTY, policy=POLICY
        )


def test_single_representation_family_is_not_applicable_even_with_one_value() -> None:
    """A family with no paired representation never reports ONE_SIDE_* (row 1 before row 4)."""
    result = extraction_status(
        family_has_pair=False,
        xbrl=side("1000.0"),
        pdf=pdf(None, state=SourceState.NO_VALUE),
        definitions=EMPTY,
        policy=POLICY,
    )
    assert result.status is ExtractionStatus.NOT_APPLICABLE
    assert result.pair is None


def test_adjacent_integer_counts_never_agree() -> None:
    """An exact count's interval is a singleton, so n and n+1 are outside tolerance."""
    shares = key("shares_outstanding", Q2_FY26, ValueKind.COUNT)
    n = side("1000", measurement=shares, decimals=None)
    n_plus_one = side("1001", measurement=shares, decimals=None, entries=(PDF_REVENUE_ENTRY,))
    result = pair_outcome(n, n_plus_one, definitions=EMPTY, policy=POLICY)
    assert result.outcome is PairOutcome.MISMATCH
    assert result.interval_gap == Decimal("1")
    extraction = extraction_status(
        family_has_pair=True, xbrl=n, pdf=n_plus_one, definitions=EMPTY, policy=POLICY
    )
    assert extraction.status is ExtractionStatus.DISAGREE


# --- Triage -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        pytest.param("1000", "995", Triage.MAGNITUDE, id="exactly-0.5pct"),
        pytest.param("1000", "995.001", Triage.NOISE, id="just-below-0.5pct"),
        # |1000 - 995.0000000000000000000000000001| / 1000 is just under 0.005.
        pytest.param(
            "1000", "995.0000000000000000000000000001", Triage.NOISE, id="just-below-28-digits"
        ),
        # 1000 against 1.0000000000000000000000000001: not exactly ×1000, a 99.9% difference.
        pytest.param(
            "1000", "1.0000000000000000000000000001", Triage.MAGNITUDE, id="near-x1000-not-scale"
        ),
        pytest.param("1000", "1", Triage.STRUCTURAL, id="x1000"),
        pytest.param("1000", "-1000", Triage.STRUCTURAL, id="sign-flip"),
    ],
)
def test_triage_threshold_and_structural_classes(left: str, right: str, expected: Triage) -> None:
    """Policy v1: STRUCTURAL first, then MAGNITUDE at or above 0.5%, else NOISE."""
    assert POLICY.magnitude_threshold == Decimal("0.005")
    assert triage(Decimal(left), Decimal(right), POLICY) is expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("10", "100", MutationClass.SCALE_10),
        ("100", "1", MutationClass.SCALE_100),
        ("1", "1000", MutationClass.THOUSANDS_TRUNCATED),
        ("-7", "7", MutationClass.SIGN_FLIP),
        ("1000", "1010", None),
        ("0", "10", None),
        ("1000", "1.0000000000000000000000000001", None),
        ("1", "-1.0000000000000000000000000001", None),
    ],
)
def test_structural_class(left: str, right: str, expected: MutationClass | None) -> None:
    """Scale factor 10, 100 or 1000, or a sign flip; nothing else is structural."""
    assert structural_class(Decimal(left), Decimal(right)) is expected


def test_mismatch_carries_magnitude_triage() -> None:
    """A 10 on 1010 gap (0.99%) is MAGNITUDE under the 0.5% threshold."""
    result = pair_outcome(side("1000.0"), pdf("1010.0"), definitions=EMPTY, policy=POLICY)
    assert result.triage is Triage.MAGNITUDE


def test_subtraction_formula_reconciles_through_an_operand_tagging_adjustment() -> None:
    """Opex: the PDF finance-cost tagging difference explains the derived disagreement."""
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD)
    assert case.operands["finance_costs"].result.status is ExtractionStatus.TAGGING_DIFFERENCE
    unadjusted = case.status()
    assert unadjusted.status is ExtractionStatus.DISAGREE
    result = case.status(PDF_FINANCE_DOWN)
    assert result.status is ExtractionStatus.TAGGING_DIFFERENCE
    assert result.adjustments == (PDF_FINANCE_DOWN,)
    assert result.rejected_adjustments == ()
    assert result.pair is not None and result.pair.outcome is PairOutcome.ANOMALY


def test_xbrl_side_adjustment_toward_pdf_also_reconciles() -> None:
    """The same record applied upward to the XBRL operand reconciles too."""
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD)
    up = PDF_FINANCE_DOWN.model_copy(update={"representation": Representation.XBRL, "direction": 1})
    assert case.status(up).status is ExtractionStatus.TAGGING_DIFFERENCE


def test_percentage_formula_reconciles_only_after_re_evaluation() -> None:
    """PBT margin: a currency adjustment to PBT propagates through ÷ revenue × 100."""
    xbrl_values = {"pbt": "4000.0", "revenue": "57154.2"}
    case = DerivedCase(
        DICTIONARY.row("pbt_margin_pct"),
        PBT_MARGIN,
        PBT_OPERANDS,
        xbrl_values,
        {**xbrl_values, "pbt": "3990.0"},
        definitions(PBT_RECORD),
    )
    assert case.operands["pbt"].result.status is ExtractionStatus.TAGGING_DIFFERENCE
    assert case.operands["revenue"].result.status is ExtractionStatus.AGREE
    # The raw 10 (a currency amount) applied to the percentage itself would not reconcile.
    assert case.xbrl_result.interval is not None and case.pdf_result.interval is not None
    assert not case.pdf_result.interval.shift(Fraction(10)).intersects(case.xbrl_result.interval)
    adjustment = TaggingAdjustment(
        operand_name="pbt",
        representation=Representation.PDF,
        direction=1,
        amount=Decimal("10"),
        unit=ValueKind.CURRENCY_AMOUNT,
        definition_record_id="PBT-1",
    )
    assert case.status().status is ExtractionStatus.DISAGREE
    result = case.status(adjustment)
    assert result.status is ExtractionStatus.TAGGING_DIFFERENCE
    assert result.adjustments == (adjustment,)


def test_tagging_difference_plus_unrelated_operand_discrepancy_disagrees() -> None:
    """A valid finance-cost adjustment cannot explain an unexplained D&A difference (HIGH)."""
    case = opex_case({**OPEX_PDF_FINANCE, "depreciation_amortisation": "408.8"}, FINANCE_RECORD)
    assert case.operands["depreciation_amortisation"].result.status is ExtractionStatus.DISAGREE
    result = case.status(PDF_FINANCE_DOWN)
    assert result.status is ExtractionStatus.DISAGREE
    assert result.rejected_adjustments == ()


@pytest.mark.parametrize(("adjustment", "reason"), REJECTED_ADJUSTMENTS)
def test_invalid_adjustments_are_rejected_and_the_status_stays_disagree(
    adjustment: TaggingAdjustment, reason: ReasonCode
) -> None:
    """An adjustment the evidence does not support is recorded as rejected, never applied."""
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD, TOTAL_RECORD)
    result = case.status(adjustment)
    assert result.status is ExtractionStatus.DISAGREE
    assert result.adjustments == ()
    assert result.rejected_adjustments == (
        AdjustmentRejection(adjustment=adjustment, reason=reason),
    )


def test_one_record_is_applied_to_an_operand_at_most_once() -> None:
    """A record's explained amount is consumed once; a repeat cannot hide another discrepancy.

    PDF finance costs 1089.0 vs 1079.0 (FC-1 explains 10) and PDF D&A 408.8 vs 398.8
    (unexplained): opex XBRL 52545.1, PDF 52525.1. One application leaves PDF at 52535.1,
    still 10 apart; a second would close the gap with an amount the record does not evidence.
    """
    case = opex_case({**OPEX_PDF_FINANCE, "depreciation_amortisation": "408.8"}, FINANCE_RECORD)
    result = case.status(PDF_FINANCE_DOWN, PDF_FINANCE_DOWN)
    assert result.status is ExtractionStatus.DISAGREE
    assert result.adjustments == (PDF_FINANCE_DOWN,)
    assert result.rejected_adjustments == (
        AdjustmentRejection(adjustment=PDF_FINANCE_DOWN, reason=ReasonCode.ADJUSTMENT_MISMATCH),
    )


def test_one_record_is_not_applied_to_both_representations() -> None:
    """Moving XBRL up and PDF down by FC-1 would apply its 10 twice to one operand."""
    case = opex_case({**OPEX_PDF_FINANCE, "depreciation_amortisation": "408.8"}, FINANCE_RECORD)
    up = PDF_FINANCE_DOWN.model_copy(update={"representation": Representation.XBRL, "direction": 1})
    result = case.status(PDF_FINANCE_DOWN, up)
    assert result.status is ExtractionStatus.DISAGREE
    assert result.adjustments == (PDF_FINANCE_DOWN,)
    assert [rejection.adjustment for rejection in result.rejected_adjustments] == [up]


def test_amounts_are_positive_magnitudes_and_direction_carries_the_sign() -> None:
    """A negative amount with direction −1 would move PDF finance costs 1089 to 1099 (away).

    Amounts are magnitudes on both the record and the adjustment, so the reviewer's
    sign-cancelling pair cannot be built and the signed shift is always direction × amount.
    """
    with pytest.raises(ValidationError):
        record(
            "FC-NEG",
            DefinitionScope.MAPPING,
            "pdf:finance_costs",
            "-10",
            canonical_id="finance_costs",
            operand_name="finance_costs",
        )
    for amount in ("-10", "0"):
        with pytest.raises(ValidationError):
            TaggingAdjustment.model_validate({**PDF_FINANCE_DOWN.model_dump(), "amount": amount})


def test_filing_record_for_another_package_is_rejected() -> None:
    """A FILING record scoped to another package cannot adjust this package's operand.

    The operand's result is constructed as if it cited that record, so the scope check itself
    must refuse the adjustment.
    """
    other_package = record(
        "FC-OTHER",
        DefinitionScope.FILING,
        "99",
        "10",
        canonical_id="finance_costs",
        operand_name="finance_costs",
    )
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD, other_package)
    finance = case.operands["finance_costs"]
    assert finance.result.pair is not None
    forged_pair = finance.result.pair.model_copy(update={"definition_record_id": "FC-OTHER"})
    forged = finance.model_copy(
        update={"result": finance.result.model_copy(update={"pair": forged_pair})}
    )
    adjustment = PDF_FINANCE_DOWN.model_copy(update={"definition_record_id": "FC-OTHER"})
    verdict = validate_adjustment(
        adjustment, operand=forged, definitions=definitions(FINANCE_RECORD, other_package)
    )
    assert verdict == AdjustmentRejection(
        adjustment=adjustment, reason=ReasonCode.ADJUSTMENT_OUT_OF_SCOPE
    )
    case.operands["finance_costs"] = forged
    result = case.status(adjustment)
    assert result.status is ExtractionStatus.DISAGREE
    assert result.rejected_adjustments == (verdict,)


def test_valid_adjustment_is_accepted_unchanged() -> None:
    """The positive control for the rejection cases."""
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD)
    verdict = validate_adjustment(
        PDF_FINANCE_DOWN,
        operand=case.operands["finance_costs"],
        definitions=definitions(FINANCE_RECORD),
    )
    assert verdict == PDF_FINANCE_DOWN


@pytest.mark.parametrize(
    ("row", "tiers", "status"),
    [
        pytest.param(
            demonstrated_opex_row(),
            {},
            ExtractionStatus.AGREE,
            id="demonstrated-formula-and-operands",
        ),
        pytest.param(
            demonstrated_opex_row(),
            {"finance_costs": UNPROVEN},
            ExtractionStatus.AGREE_UNQUALIFIED,
            id="one-unproven-operand",
        ),
        pytest.param(
            DICTIONARY.row("opex_excl_finance_and_da"),
            {},
            ExtractionStatus.AGREE_UNQUALIFIED,
            id="unproven-formula",
        ),
    ],
)
def test_computed_match_is_only_as_strong_as_its_weakest_tier(
    row: DictionaryRow, tiers: Mapping[str, EvidenceTier], status: ExtractionStatus
) -> None:
    """A computed match agrees only when the formula and every operand are demonstrated."""
    case = DerivedCase(row, OPEX, OPEX_OPERANDS, OPEX_XBRL, OPEX_XBRL, EMPTY, tiers=tiers)
    assert case.status().status is status


def test_derived_not_applicable_when_every_operand_family_is_single_representation() -> None:
    """No operand has a second representation, so there is no extraction pair to report."""
    case = opex_case(OPEX_PDF_FINANCE, FINANCE_RECORD)
    result = derived_extraction_status(
        row=case.row,
        output=OPEX,
        every_operand_single_representation=True,
        operands=case.operands,
        xbrl=derived_side(case.xbrl_result, OPEX),
        pdf=derived_side(case.pdf_result, OPEX),
        adjustments=(PDF_FINANCE_DOWN,),
        definitions=case.defs,
        policy=POLICY,
        rounding=ROUNDING,
        qualification=quarter_context(),
        dictionary=DICTIONARY,
        reporting_currency=INR,
    )
    assert result.status is ExtractionStatus.NOT_APPLICABLE
    assert result.adjustments == ()


UNAVAILABLE_READ = OperandState(SourceState.UNAVAILABLE)
UNREADABLE_READ = OperandState(SourceState.INVALID, reasons=(ReasonCode.UNREADABLE_CELL.value,))
NO_PRECISION_READ = OperandState(precision_supported=False)
MISSING_READ = OperandState(SourceState.NO_VALUE)
FINANCE = "finance_costs"


@pytest.mark.parametrize(
    ("reads", "pdf_basis", "states", "status", "reason"),
    [
        pytest.param(
            {(Representation.PDF, FINANCE): UNAVAILABLE_READ},
            Basis.CONSOLIDATED,
            (CalculationState.COMPUTED, CalculationState.OPERAND_UNAVAILABLE),
            ExtractionStatus.UNAVAILABLE,
            None,
            id="row2-operand-unavailable",
        ),
        pytest.param(
            {(Representation.XBRL, FINANCE): UNREADABLE_READ},
            Basis.CONSOLIDATED,
            (CalculationState.OPERAND_INVALID, CalculationState.COMPUTED),
            ExtractionStatus.NOT_COMPARABLE,
            ReasonCode.UNREADABLE_CELL,
            id="row2a-operand-invalid",
        ),
        pytest.param(
            {(Representation.PDF, FINANCE): NO_PRECISION_READ},
            Basis.CONSOLIDATED,
            (CalculationState.COMPUTED, CalculationState.OPERAND_INVALID),
            ExtractionStatus.NOT_COMPARABLE,
            ReasonCode.PRECISION_UNSUPPORTED,
            id="row2a-operand-without-precision",
        ),
        pytest.param(
            {
                (Representation.XBRL, FINANCE): MISSING_READ,
                (Representation.PDF, FINANCE): MISSING_READ,
            },
            Basis.CONSOLIDATED,
            (CalculationState.OPERAND_MISSING, CalculationState.OPERAND_MISSING),
            ExtractionStatus.NONE,
            None,
            id="row3-neither-has-a-value",
        ),
        pytest.param(
            {(Representation.PDF, FINANCE): MISSING_READ},
            Basis.CONSOLIDATED,
            (CalculationState.COMPUTED, CalculationState.OPERAND_MISSING),
            ExtractionStatus.ONE_SIDE_XBRL,
            None,
            id="row4-pdf-operand-missing",
        ),
        pytest.param(
            {(Representation.XBRL, FINANCE): MISSING_READ},
            Basis.CONSOLIDATED,
            (CalculationState.OPERAND_MISSING, CalculationState.COMPUTED),
            ExtractionStatus.ONE_SIDE_PDF,
            None,
            id="row4-xbrl-operand-missing",
        ),
        pytest.param(
            {},
            Basis.STANDALONE,
            (CalculationState.COMPUTED, CalculationState.COMPUTED),
            ExtractionStatus.NOT_COMPARABLE,
            ReasonCode.BASIS_MISMATCH,
            id="row5-pair-refused",
        ),
    ],
)
def test_derived_extraction_rows_follow_each_sides_calculation_state(
    reads: Mapping[tuple[Representation, str], OperandState],
    pdf_basis: Basis,
    states: tuple[CalculationState, CalculationState],
    status: ExtractionStatus,
    reason: ReasonCode | None,
) -> None:
    """Rows 2–5 from real operand states evaluated per representation (calculation table)."""
    values = {
        rep: {
            name: None
            if reads.get((rep, name), OperandState()).state is not SourceState.VALUE
            else number
            for name, number in OPEX_XBRL.items()
        }
        for rep in (Representation.XBRL, Representation.PDF)
    }
    case = DerivedCase(
        DICTIONARY.row("opex_excl_finance_and_da"),
        OPEX,
        OPEX_OPERANDS,
        values[Representation.XBRL],
        values[Representation.PDF],
        EMPTY,
        reads=reads,
        pdf_basis=pdf_basis,
    )
    assert (case.xbrl_result.state, case.pdf_result.state) == states
    result = case.status()
    assert (result.status, result.reason) == (status, reason)


# --- First-party-only corroboration -------------------------------------------------------------

APPLICABLE = ApplicabilityStatus.APPLICABLE


@pytest.mark.parametrize(
    ("applicability", "first_party", "expected"),
    [
        pytest.param(
            ApplicabilityStatus.NOT_APPLICABLE,
            side(None, state=SourceState.UNAVAILABLE),
            (CorroborationStatus.NOT_APPLICABLE, None),
            id="row1-not-applicable",
        ),
        pytest.param(
            APPLICABLE,
            side(None, state=SourceState.UNAVAILABLE),
            (CorroborationStatus.UNAVAILABLE, None),
            id="row2-unavailable",
        ),
        pytest.param(
            APPLICABLE,
            side(None, state=SourceState.INVALID, reasons=(ReasonCode.UNREADABLE_CELL,)),
            (CorroborationStatus.NOT_COMPARABLE, ReasonCode.UNREADABLE_CELL),
            id="row2a-invalid",
        ),
        pytest.param(
            APPLICABLE,
            side(None, state=SourceState.NO_VALUE),
            (CorroborationStatus.NO_SOURCE, None),
            id="row5-no-source",
        ),
        pytest.param(
            APPLICABLE,
            side("1000.0"),
            (CorroborationStatus.FILING_ONLY, None),
            id="row7-filing-only",
        ),
    ],
)
def test_first_party_only_corroboration_rows(
    applicability: ApplicabilityStatus,
    first_party: ComparisonSide,
    expected: tuple[CorroborationStatus, ReasonCode | None],
) -> None:
    """Rows 1, 2, 2a, 5 and 7 with no mapped vendor."""
    assert corroboration_status(applicability=applicability, first_party=first_party) == expected


# --- Policy and definition set ------------------------------------------------------------------


def test_comparison_policy_v1_is_pinned_by_content() -> None:
    """Policy v1: 0.5% threshold, content hash of the file bytes."""
    path = REPO / "config" / "comparison_policy" / "v1.yaml"
    assert POLICY.version == "v1"
    assert POLICY.content_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert isinstance(POLICY, ComparisonPolicy)


def test_definition_set_v1_is_empty() -> None:
    """D1a publishes definition set v1 with no records."""
    assert EMPTY.version == "v1"
    assert EMPTY.records == ()


@pytest.mark.pg
def test_publish_definition_set_is_idempotent_and_refuses_drift(pg_db: PgTestDatabase) -> None:
    """Same version and content reuses the row; same version, other content is refused."""
    mapped = DefinitionSet(
        version="t1",
        content_sha256="a" * 64,
        records=(
            record("R1", DefinitionScope.MAPPING, PDF_REVENUE_ENTRY, "10"),
            record("R2", DefinitionScope.MEASUREMENT, REVENUE.digest(), "2.5"),
        ),
    )
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        first = publish_definition_set(conn, EMPTY)
        assert publish_definition_set(conn, EMPTY) == first
        mapped_id = publish_definition_set(conn, mapped)
        assert publish_definition_set(conn, mapped) == mapped_id
        with pytest.raises(VersionContentDriftError):
            publish_definition_set(conn, EMPTY.model_copy(update={"content_sha256": "b" * 64}))
        rows = conn.execute(
            "SELECT d.version, r.record_id, r.scope, r.mapping_entry_id, r.key_digest, "
            "r.explained_amount FROM eqos.definition_sets d "
            "LEFT JOIN eqos.definition_records r ON r.definition_set_id = d.id "
            "ORDER BY d.version, r.record_id"
        ).fetchall()
    assert rows == [
        ("t1", "R1", "MAPPING", PDF_REVENUE_ENTRY, None, Decimal("10")),
        ("t1", "R2", "MEASUREMENT", None, REVENUE.digest(), Decimal("2.5")),
        ("v1", None, None, None, None, None),
    ]


def test_definition_set_loader_refuses_a_record_in_an_unknown_scope(tmp_path: Path) -> None:
    """A record's scope is one of MAPPING, MEASUREMENT or FILING."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        "version: bad\nrecords:\n- record_id: X\n  scope: LABEL\n  scope_ref: x\n"
        "  canonical_id: revenue_from_operations\n  evidence_ref: e\n"
        "  explained_amount: '1'\n  unit: CURRENCY_AMOUNT\n"
    )
    with pytest.raises(ValueError):
        load_definition_set(path)
