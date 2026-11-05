"""D1a.3 acceptance: calculation states, the effective tier and well-formed conclusions.

Every derived side ends in exactly one calculation state, first matching spec row wins
(data spec §5), so an unavailable operand is never reported as merely missing. A derived
value is never stronger evidence than its weakest operand or its formula's recorded scope
(plan design decision 8), and a ``COMPUTED`` result always carries a value inside its
interval while no other state carries one.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from canon_formula_support import (
    DEMONSTRATED,
    Q2_FY26,
    UNPROVEN,
    evaluate_inr,
    key,
    leaf,
    load_v1_dictionary,
    load_v1_policy,
    quarter_context,
)

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, TemporalRole, ValueKind
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.qualification import (
    ConditionPredicate,
    QualificationCondition,
    QualificationContext,
    QualificationFixture,
    QualificationScope,
)
from equity_os.contracts.verification.comparison import CalculationState, SourceState
from equity_os.normalisation.derivation.formula import (
    CalculationResult,
    OperandValue,
    TraceKind,
    calculation_state,
    conclude,
    state_to_source_state,
)
from equity_os.normalisation.derivation.interval import Interval, RoundingPolicy
from equity_os.normalisation.dictionary.dictionary import (
    CanonicalDictionary,
    DictionaryRow,
    Formula,
)

SCOPE_ID = "test-opm-in-capmkt-quarter"
CONDITION = QualificationCondition(
    condition_id="discontinued_zero",
    canonical_id="profit_discontinued_after_tax",
    predicate=ConditionPredicate.EQUALS_ZERO,
)
SCOPE = QualificationScope(
    scope_id=SCOPE_ID,
    schema_identities=frozenset({"in-capmkt"}),
    surfaces=frozenset({"NSE_XBRL_INSTANCE"}),
    bases=frozenset({Basis.CONSOLIDATED}),
    period_kinds=frozenset({PeriodKind.QUARTER}),
    conditions=(CONDITION,),
    # Constructed evidence exercises the tier rule; it does not qualify a real mapping.
    fixture_evidence=tuple(
        QualificationFixture(
            capture_id=f"constructed-calculation-state-{index}",
            capture_sha256=f"{index:064x}",
            entity_id=index,
            discriminating=index == 1,
        )
        for index in range(1, 6)
    ),
    sample_rule="Constructed test cases: five companies and a discriminating case",
)


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Dictionary v1 as committed."""
    return load_v1_dictionary()


@pytest.fixture(scope="module")
def policy() -> RoundingPolicy:
    """Rounding policy v1 as committed."""
    return load_v1_policy()


def _with_formula(row: DictionaryRow, **changes: object) -> DictionaryRow:
    """A copy of a dictionary row whose formula has the given fields replaced."""
    assert row.formula is not None
    formula = Formula.model_validate({**row.formula.model_dump(), **changes})
    return row.model_copy(update={"formula": formula})


# --- calculation-state table ---------------------------------------------------------------

_K = key("revenue_from_operations", Q2_FY26)
_VALUE = leaf(_K, "1")
_NO_VALUE = leaf(_K, None, state=SourceState.NO_VALUE)
_UNAVAILABLE = leaf(_K, None, state=SourceState.UNAVAILABLE)
_INVALID_WITH_NUMBER = leaf(_K, "1", state=SourceState.INVALID, reasons=("SIGN_CONFLICT",))
_NO_PRECISION = leaf(_K, "1", precision_supported=False)


@pytest.mark.parametrize(
    ("operands", "revision_incompatible", "zero_denominator", "state", "source_state"),
    [
        pytest.param(
            [_UNAVAILABLE, _INVALID_WITH_NUMBER, _NO_VALUE],
            True,
            True,
            CalculationState.OPERAND_UNAVAILABLE,
            SourceState.UNAVAILABLE,
            id="row1-unavailable-wins",
        ),
        pytest.param(
            [_INVALID_WITH_NUMBER, _NO_VALUE],
            True,
            True,
            CalculationState.OPERAND_INVALID,
            SourceState.INVALID,
            id="row1a-invalid-operand-carrying-a-number",
        ),
        pytest.param(
            [_NO_PRECISION, _NO_VALUE],
            False,
            False,
            CalculationState.OPERAND_INVALID,
            SourceState.INVALID,
            id="row1a-value-without-supported-precision",
        ),
        pytest.param(
            [_VALUE, _NO_VALUE],
            True,
            True,
            CalculationState.OPERAND_MISSING,
            SourceState.NO_VALUE,
            id="row2-missing",
        ),
        pytest.param(
            [_VALUE, _VALUE],
            True,
            True,
            CalculationState.REVISION_INCOMPATIBLE,
            SourceState.INVALID,
            id="row3-revision-incompatible",
        ),
        pytest.param(
            [_VALUE, _VALUE],
            False,
            True,
            CalculationState.UNDEFINED,
            SourceState.INVALID,
            id="row4-undefined",
        ),
        pytest.param(
            [_VALUE, _VALUE],
            False,
            False,
            CalculationState.COMPUTED,
            SourceState.VALUE,
            id="row5-computed",
        ),
    ],
)
def test_calculation_state_table_first_match_wins(
    operands: list[OperandValue],
    revision_incompatible: bool,
    zero_denominator: bool,
    state: CalculationState,
    source_state: SourceState,
) -> None:
    """Each spec row in order (data spec §5); a later row never masks an earlier one."""
    result = calculation_state(
        operands,
        revision_incompatible=revision_incompatible,
        denominator_contains_zero=zero_denominator,
    )
    assert result is state
    assert state_to_source_state(result) is source_state


def test_invalid_operand_reasons_propagate(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """An INVALID operand still carrying a number gives OPERAND_INVALID with its reasons."""
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    operands = {
        "ebitda": leaf(
            key("ebitda_excl_other_income", Q2_FY26),
            "5",
            state=SourceState.INVALID,
            reasons=("SIGN_CONFLICT",),
        ),
        "revenue": leaf(key("revenue_from_operations", Q2_FY26), "50"),
    }
    result = evaluate_inr(dictionary, policy, "opm_pct", output, operands)
    assert result.state is CalculationState.OPERAND_INVALID
    assert result.source_state is SourceState.INVALID
    assert "SIGN_CONFLICT" in result.reasons
    assert result.exact is None


# --- effective tier ------------------------------------------------------------------------


def _opm(
    dictionary: CanonicalDictionary,
    policy: RoundingPolicy,
    *,
    formula_tier: EvidenceTier,
    ebitda_tier: EvidenceTier,
    context: QualificationContext,
) -> CalculationResult:
    """OPM with a chosen formula tier (scoped to quarters on in-capmkt) and EBITDA tier."""
    row = _with_formula(dictionary.row("opm_pct"), tier=formula_tier, qualification=SCOPE)
    operands = {
        "ebitda": leaf(key("ebitda_excl_other_income", Q2_FY26), "5", tier=ebitda_tier),
        "revenue": leaf(key("revenue_from_operations", Q2_FY26), "50"),
    }
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    return evaluate_inr(dictionary, policy, row, output, operands, qualification=context)


def test_demonstrated_formula_in_scope_over_demonstrated_operands_is_demonstrated(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """The one combination that stays demonstrated, with the scope recorded on the trace."""
    result = _opm(
        dictionary,
        policy,
        formula_tier=DEMONSTRATED,
        ebitda_tier=DEMONSTRATED,
        context=quarter_context(),
    )
    assert result.effective_tier is DEMONSTRATED
    assert result.trace.formula_tier is DEMONSTRATED
    assert result.trace.formula_qualification_ref == SCOPE_ID


def test_one_unproven_operand_makes_the_result_unproven(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A demonstrated, in-scope formula is only as strong as its weakest operand."""
    result = _opm(
        dictionary,
        policy,
        formula_tier=DEMONSTRATED,
        ebitda_tier=UNPROVEN,
        context=quarter_context(),
    )
    assert result.effective_tier is UNPROVEN
    assert result.trace.formula_qualification_ref == SCOPE_ID


def test_unproven_formula_over_demonstrated_operands_is_unproven(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """No formula is exempt from the weakest-tier rule (plan design decision 8)."""
    result = _opm(
        dictionary,
        policy,
        formula_tier=UNPROVEN,
        ebitda_tier=DEMONSTRATED,
        context=quarter_context(),
    )
    assert result.effective_tier is UNPROVEN


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(quarter_context(basis=Basis.STANDALONE), id="other-basis"),
        pytest.param(quarter_context(schema="in-bse-fin"), id="other-schema"),
        pytest.param(quarter_context(proven={}), id="condition-unproven"),
    ],
)
def test_demonstrated_formula_out_of_scope_is_unproven(
    dictionary: CanonicalDictionary, policy: RoundingPolicy, context: QualificationContext
) -> None:
    """Outside its recorded scope a demonstrated formula is unproven and carries no scope ref."""
    result = _opm(
        dictionary, policy, formula_tier=DEMONSTRATED, ebitda_tier=DEMONSTRATED, context=context
    )
    assert result.effective_tier is UNPROVEN
    assert result.trace.formula_tier is UNPROVEN
    assert result.trace.formula_qualification_ref is None


@pytest.mark.parametrize(
    ("state", "point", "message"),
    [
        pytest.param(
            CalculationState.COMPUTED, None, "carries its exact value", id="computed-without-value"
        ),
        pytest.param(
            CalculationState.OPERAND_MISSING,
            (Fraction(1), Interval.exact(Fraction(1))),
            "carries no value",
            id="missing-with-a-value",
        ),
        pytest.param(
            CalculationState.COMPUTED,
            (Fraction(3), Interval(lower=Fraction(1), upper=Fraction(2))),
            "outside its interval",
            id="value-outside-its-interval",
        ),
    ],
)
def test_a_contradictory_conclusion_is_refused(
    policy: RoundingPolicy,
    state: CalculationState,
    point: tuple[Fraction, Interval] | None,
    message: str,
) -> None:
    """COMPUTED always carries a value inside its interval; no other state carries one."""
    revenue = key("revenue_from_operations", Q2_FY26)
    entries = [("revenue", TemporalRole.DURATION, leaf(revenue, "1"))]
    with pytest.raises(ValueError, match=message):
        conclude(TraceKind.FORMULA, revenue, entries, state, point, policy)
