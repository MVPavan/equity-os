"""D1a.3 acceptance: formulas, temporal roles, intervals, aggregation and traces.

These are the rules every derived financial figure obeys (data spec §1, §2, §5): only the
role-aligned key at its dictionary value kind is ever used, intermediates stay exact so a
rounded child can never turn a computable value into ``UNDEFINED``, uncertainty bounds
propagate through every operator, an incomplete member list is ``OPERAND_MISSING`` rather
than a smaller total, a percentage of rupees carries no currency, and a trace never records
a selection that did not happen. Operands are constructed: these are pure functions. Period
derivation lives in ``test_canon_period_aggregation.py``; calculation states and the
effective tier in ``test_canon_calculation_state.py``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest
from canon_formula_support import (
    H1_FY26,
    INR,
    Q2_FY26,
    UNPROVEN,
    evaluate_inr,
    key,
    leaf,
    load_v1_dictionary,
    load_v1_policy,
)
from pydantic import ValidationError

from fundamentals.canon.dictionary import (
    CanonicalDictionary,
    DictionaryRow,
    DimensionalAggregation,
    Formula,
    FormulaNode,
    FormulaOp,
    FormulaOperand,
)
from fundamentals.canon.formula import (
    CalculationResult,
    CurrencyMismatchError,
    OperandKeyMismatchError,
    OperandValue,
    TraceKind,
    aggregate_members,
    average_operand,
    operand_from_result,
    resolve_operand_keys,
)
from fundamentals.canon.interval import Interval, RoundingPolicy
from fundamentals.contracts.canonical import (
    TemporalRole,
    ValueIdentity,
    ValueKind,
)
from fundamentals.contracts.comparison import CalculationState, SelectionSource, SourceState
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Dictionary v1 as committed."""
    return load_v1_dictionary()


@pytest.fixture(scope="module")
def policy() -> RoundingPolicy:
    """Rounding policy v1 as committed."""
    return load_v1_policy()


def _ratio_over_average_receivables(dictionary: CanonicalDictionary) -> DictionaryRow:
    """A constructed turnover ratio: revenue ÷ average current trade receivables."""
    row = dictionary.row("receivable_days")
    formula = Formula(
        formula_id="test_receivables_turnover",
        version="1",
        operands=(
            FormulaOperand(
                name="revenue",
                canonical_id="revenue_from_operations",
                temporal_role=TemporalRole.DURATION,
            ),
            FormulaOperand(
                name="receivables",
                canonical_id="trade_receivables_current",
                temporal_role=TemporalRole.AVERAGE,
            ),
        ),
        expression=FormulaNode(
            op=FormulaOp.DIV,
            args=(
                FormulaNode(op=FormulaOp.OPERAND, operand="revenue"),
                FormulaNode(op=FormulaOp.OPERAND, operand="receivables"),
            ),
        ),
        output_kind=ValueKind.RATIO,
        evidence="test-only construction",
    )
    return row.model_copy(
        update={
            "canonical_id": "test_receivables_turnover",
            "value_kind": ValueKind.RATIO,
            "formula": formula,
        }
    )


# --- temporal roles ------------------------------------------------------------------------


def test_closing_role_reads_the_instant_at_the_output_end(dictionary: CanonicalDictionary) -> None:
    """Receivable days uses only the period-end receivables instant."""
    formula = dictionary.row("receivable_days").formula
    assert formula is not None
    receivables = next(op for op in formula.operands if op.name == "receivables")
    output = key("receivable_days", Q2_FY26, ValueKind.DAYS)
    (resolved,) = resolve_operand_keys(
        output, receivables, dictionary=dictionary, reporting_currency=INR
    )
    assert resolved == key("trade_receivables_current", PeriodInterval.at(date(2025, 9, 30)))


def test_opening_role_is_the_instant_before_the_start(dictionary: CanonicalDictionary) -> None:
    """Apar H1 FY26 opening cash is the 31 March 2025 instant (data spec §1)."""
    operand = FormulaOperand(
        name="opening_cash",
        canonical_id="cash_and_cash_equivalents",
        temporal_role=TemporalRole.OPENING,
    )
    output = key("test_cash_movement", H1_FY26)
    (resolved,) = resolve_operand_keys(
        output, operand, dictionary=dictionary, reporting_currency=INR
    )
    assert resolved.period == PeriodInterval.at(date(2025, 3, 31))
    assert resolved.canonical_id == "cash_and_cash_equivalents"


def test_average_role_is_the_opening_and_closing_pair(dictionary: CanonicalDictionary) -> None:
    """An average reads exactly two instants: the preceding close and the period end."""
    operand = FormulaOperand(
        name="receivables",
        canonical_id="trade_receivables_current",
        temporal_role=TemporalRole.AVERAGE,
    )
    output = key("test_receivables_turnover", H1_FY26, ValueKind.RATIO)
    opening, closing = resolve_operand_keys(
        output, operand, dictionary=dictionary, reporting_currency=INR
    )
    assert opening.period == PeriodInterval.at(date(2025, 3, 31))
    assert closing.period == PeriodInterval.at(date(2025, 9, 30))


def test_duration_role_keeps_the_output_interval(dictionary: CanonicalDictionary) -> None:
    """A duration operand is the same interval as the output, with the operand's own kind."""
    operand = FormulaOperand(
        name="revenue", canonical_id="revenue_from_operations", temporal_role=TemporalRole.DURATION
    )
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    (resolved,) = resolve_operand_keys(
        output, operand, dictionary=dictionary, reporting_currency=INR
    )
    assert resolved == key("revenue_from_operations", Q2_FY26)


def test_receivable_days_uses_actual_days_in_the_output_interval(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Closing receivables ÷ revenue × 92 days (Q2 FY26 has 92 days), exact then half-even.

    Both operands are ± 0.5, so the bounds are 999.5 ÷ 3000.5 × 92 and 1000.5 ÷ 2999.5 × 92.
    """
    output = key("receivable_days", Q2_FY26, ValueKind.DAYS)
    operands = {
        "receivables": leaf(
            key("trade_receivables_current", PeriodInterval.at(date(2025, 9, 30))),
            "1000",
            decimals=0,
        ),
        "revenue": leaf(key("revenue_from_operations", Q2_FY26), "3000", decimals=0),
    }
    result = evaluate_inr(dictionary, policy, "receivable_days", output, operands)
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(92, 3)
    assert result.value == Decimal("30.67")
    assert result.interval == Interval(lower=Fraction(183908, 6001), upper=Fraction(184092, 5999))
    assert result.trace.value_identity is ValueIdentity.DERIVED
    assert result.trace.rounding_policy_id == policy.policy_id
    assert result.trace.key_digest == output.digest()
    assert output.currency is None


def test_an_operand_at_a_non_role_aligned_date_is_never_used(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A receivables instant at the opening date is not the closing value: OPERAND_MISSING.

    Nothing was selected at the closing date, so the trace records no selection source.
    """
    output = key("receivable_days", Q2_FY26, ValueKind.DAYS)
    operands = {
        "receivables": leaf(
            key("trade_receivables_current", PeriodInterval.at(date(2025, 6, 30))), "1000"
        ),
        "revenue": leaf(key("revenue_from_operations", Q2_FY26), "3000"),
    }
    result = evaluate_inr(dictionary, policy, "receivable_days", output, operands)
    assert result.state is CalculationState.OPERAND_MISSING
    assert result.exact is None and result.value is None
    receivables = next(op for op in result.trace.operands if op.name == "receivables")
    assert receivables.source_state is SourceState.NO_VALUE
    assert receivables.interpretation_id is None
    assert receivables.selection_source is None
    expected = key("trade_receivables_current", PeriodInterval.at(date(2025, 9, 30)))
    assert receivables.key_digest == expected.digest()


def test_an_operand_for_another_entity_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Key parts other than the period never differ silently; that is a caller defect."""
    output = key("receivable_days", Q2_FY26, ValueKind.DAYS)
    stranger = key("revenue_from_operations", Q2_FY26).model_copy(update={"entity_id": 2})
    operands = {
        "receivables": leaf(
            key("trade_receivables_current", PeriodInterval.at(date(2025, 9, 30))), "1000"
        ),
        "revenue": leaf(stranger, "3000"),
    }
    with pytest.raises(OperandKeyMismatchError):
        evaluate_inr(dictionary, policy, "receivable_days", output, operands)


def _opm_operands(ebitda: MeasurementKey) -> dict[str, OperandValue]:
    """OPM operands: EBITDA 5 at ``ebitda`` and INR revenue 50."""
    return {
        "ebitda": leaf(ebitda, "5"),
        "revenue": leaf(key("revenue_from_operations", Q2_FY26), "50"),
    }


def test_an_operand_at_another_value_kind_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """EBITDA is a currency amount: an EBITDA keyed as a count is a caller defect, not 10%."""
    ebitda = key("ebitda_excl_other_income", Q2_FY26).model_copy(
        update={"value_kind": ValueKind.COUNT}
    )
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    with pytest.raises(OperandKeyMismatchError) as refused:
        evaluate_inr(dictionary, policy, "opm_pct", output, _opm_operands(ebitda))
    assert not isinstance(refused.value, CurrencyMismatchError)


def test_a_percentage_of_rupee_operands_carries_no_currency(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """OPM over INR EBITDA and revenue is a currency-free 10% (ruling R2)."""
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    assert output.currency is None
    operands = _opm_operands(key("ebitda_excl_other_income", Q2_FY26))
    result = evaluate_inr(dictionary, policy, "opm_pct", output, operands)
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(10)
    assert result.trace.key_digest == output.digest()
    assert [op.key_digest for op in result.trace.operands] == [
        key("ebitda_excl_other_income", Q2_FY26).digest(),
        key("revenue_from_operations", Q2_FY26).digest(),
    ]


def test_a_percentage_keyed_in_a_currency_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A dimensionless output in INR would never match a vendor's percentage; refuse it."""
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE).model_copy(update={"currency": INR})
    operands = _opm_operands(key("ebitda_excl_other_income", Q2_FY26))
    with pytest.raises(CurrencyMismatchError):
        evaluate_inr(dictionary, policy, "opm_pct", output, operands)


def test_operands_in_different_currencies_are_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """USD EBITDA over INR revenue is not a margin; D1a refuses rather than converts."""
    usd = key("ebitda_excl_other_income", Q2_FY26).model_copy(update={"currency": "USD"})
    output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
    with pytest.raises(CurrencyMismatchError):
        evaluate_inr(dictionary, policy, "opm_pct", output, _opm_operands(usd))


# --- exact intermediates, averages and interval propagation ---------------------------------


def _average(opening: str, closing: str, policy: RoundingPolicy) -> OperandValue:
    """Average H1 FY26 current trade receivables from opening and closing values ± 0.0005."""
    instant = "trade_receivables_current"
    return average_operand(
        leaf(key(instant, PeriodInterval.at(date(2025, 3, 31))), opening, decimals=3),
        leaf(key(instant, PeriodInterval.at(date(2025, 9, 30))), closing, decimals=3),
        output=key(instant, H1_FY26),
        policy=policy,
    )


def test_parent_uses_the_exact_average_not_its_stored_rounding(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """The average of 0 and 0.01 INR is exactly 0.005: it stores as 0.00 but divides fine.

    Its interval is [(−0.0005 + 0.0095) ÷ 2, (0.0005 + 0.0105) ÷ 2] = [0.0045, 0.0055], which
    stores outward as [0.00, 0.01] — a stored denominator that would contain zero. Revenue 3
    over the exact interval is [3 ÷ 0.0055, 3 ÷ 0.0045] = [6000/11, 2000/3].
    """
    average = _average("0", "0.01", policy)
    assert average.exact == Fraction(1, 200)
    assert average.value == Decimal("0.00")
    assert average.interval == Interval(lower=Fraction(9, 2000), upper=Fraction(11, 2000))
    assert average.child_trace is not None
    assert average.child_trace.trace_kind is TraceKind.AVERAGE
    assert average.child_trace.exact_value == Fraction(1, 200)
    assert (average.child_trace.lower, average.child_trace.upper) == (
        Decimal("0.00"),
        Decimal("0.01"),
    )
    assert [op.key_digest for op in average.child_trace.operands] == [
        key("trade_receivables_current", PeriodInterval.at(date(2025, 3, 31))).digest(),
        key("trade_receivables_current", PeriodInterval.at(date(2025, 9, 30))).digest(),
    ]

    row = _ratio_over_average_receivables(dictionary)
    output = key(row.canonical_id, H1_FY26, ValueKind.RATIO)
    revenue = leaf(key("revenue_from_operations", H1_FY26), "3")
    result = evaluate_inr(
        dictionary, policy, row, output, {"revenue": revenue, "receivables": average}
    )
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(600)
    assert result.interval == Interval(lower=Fraction(6000, 11), upper=Fraction(2000, 3))
    receivables = next(op for op in result.trace.operands if op.name == "receivables")
    assert receivables.exact_value == Fraction(1, 200)
    assert receivables.exact_interval == average.interval


def test_a_denominator_interval_containing_zero_is_undefined(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """An average of 0 and 0 ± 0.0005 may be zero: UNDEFINED, source INVALID."""
    row = _ratio_over_average_receivables(dictionary)
    output = key(row.canonical_id, H1_FY26, ValueKind.RATIO)
    revenue = leaf(key("revenue_from_operations", H1_FY26), "3")
    result = evaluate_inr(
        dictionary,
        policy,
        row,
        output,
        {"revenue": revenue, "receivables": _average("0", "0", policy)},
    )
    assert result.state is CalculationState.UNDEFINED
    assert result.source_state is SourceState.INVALID
    assert result.exact is None and result.value is None


def test_computed_operands_pass_their_exact_value_up_a_chain(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """OPM over EBITDA over opex keeps exact intermediates (Apar Q2 FY26 figures cited in v1).

    Every input is ± 50 000 (half of 10^5). Opex = 54022.9 − 1079.0 − 398.8 million is
    52 545 100 000 ± 150 000; EBITDA = 57 154 200 000 − opex is 4 609 100 000 ± 200 000;
    OPM lies in [4 608 900 000 ÷ 57 154 250 000, 4 609 300 000 ÷ 57 154 150 000] × 100.
    """
    million = Decimal(10) ** 6

    def amount(canonical_id: str, millions: str) -> OperandValue:
        return leaf(key(canonical_id, Q2_FY26), str(Decimal(millions) * million), decimals=-5)

    revenue = amount("revenue_from_operations", "57154.2")
    opex = evaluate_inr(
        dictionary,
        policy,
        "opex_excl_finance_and_da",
        key("opex_excl_finance_and_da", Q2_FY26),
        {
            "total_expenses": amount("total_expenses", "54022.9"),
            "finance_costs": amount("finance_costs", "1079.0"),
            "depreciation_amortisation": amount("depreciation_amortisation", "398.8"),
        },
    )
    assert opex.exact == Fraction(52545100000)
    assert opex.interval == Interval(lower=Fraction(52544950000), upper=Fraction(52545250000))
    ebitda = evaluate_inr(
        dictionary,
        policy,
        "ebitda_excl_other_income",
        key("ebitda_excl_other_income", Q2_FY26),
        {"revenue": revenue, "opex": _computed(opex, key("opex_excl_finance_and_da", Q2_FY26))},
    )
    assert ebitda.exact == Fraction(4609100000)
    assert ebitda.interval == Interval(lower=Fraction(4608900000), upper=Fraction(4609300000))
    opm = evaluate_inr(
        dictionary,
        policy,
        "opm_pct",
        key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE),
        {
            "ebitda": _computed(ebitda, key("ebitda_excl_other_income", Q2_FY26)),
            "revenue": revenue,
        },
    )
    assert opm.state is CalculationState.COMPUTED
    assert opm.exact == Fraction(46091, 571542) * 100
    assert opm.value == Decimal("8.06")
    assert opm.interval == Interval(
        lower=Fraction(9217800, 1143085), upper=Fraction(9218600, 1143083)
    )
    assert (opm.trace.lower, opm.trace.upper) == (Decimal("8.06"), Decimal("8.07"))


def _computed(result: CalculationResult, measurement: MeasurementKey) -> OperandValue:
    """A computed result handed to its parent formula with its exact value and trace."""
    return operand_from_result(
        result, key=measurement, selection_source=SelectionSource.PACKAGE_AS_REPORTED
    )


def _binary_row(dictionary: CanonicalDictionary, op: FormulaOp, kind: ValueKind) -> DictionaryRow:
    """A constructed ``revenue <op> other_income`` row with output kind ``kind``."""
    formula = Formula(
        formula_id="test_binary",
        version="1",
        operands=(
            FormulaOperand(
                name="x",
                canonical_id="revenue_from_operations",
                temporal_role=TemporalRole.DURATION,
            ),
            FormulaOperand(
                name="y", canonical_id="other_income", temporal_role=TemporalRole.DURATION
            ),
        ),
        expression=FormulaNode(
            op=op,
            args=(
                FormulaNode(op=FormulaOp.OPERAND, operand="x"),
                FormulaNode(op=FormulaOp.OPERAND, operand="y"),
            ),
        ),
        output_kind=kind,
        evidence="test-only construction",
    )
    row = dictionary.row("revenue_from_operations")
    return row.model_copy(
        update={"canonical_id": "test_binary", "value_kind": kind, "formula": formula}
    )


@pytest.mark.parametrize(
    ("op", "kind", "y", "exact", "bounds"),
    [
        # x = 3 ± 0.5 = [5/2, 7/2]; y = −2 ± 0.5 = [−5/2, −3/2].
        pytest.param(FormulaOp.ADD, ValueKind.CURRENCY_AMOUNT, "-2", "1", ("0", "2"), id="add"),
        pytest.param(FormulaOp.SUB, ValueKind.CURRENCY_AMOUNT, "-2", "5", ("4", "6"), id="sub"),
        pytest.param(FormulaOp.MUL, ValueKind.RATIO, "-2", "-6", ("-35/4", "-15/4"), id="mul"),
        # 1/y = [−2/3, −2/5]; corners 5/2·−2/3, 5/2·−2/5, 7/2·−2/3, 7/2·−2/5.
        pytest.param(
            FormulaOp.DIV, ValueKind.RATIO, "-2", "-3/2", ("-7/3", "-1"), id="div-negative"
        ),
    ],
)
def test_every_operator_propagates_uncertain_bounds(
    dictionary: CanonicalDictionary,
    policy: RoundingPolicy,
    op: FormulaOp,
    kind: ValueKind,
    y: str,
    exact: str,
    bounds: tuple[str, str],
) -> None:
    """The evaluator carries each operand's interval through + − × ÷, not just the point."""
    row = _binary_row(dictionary, op, kind)
    operands = {
        "x": leaf(key("revenue_from_operations", Q2_FY26), "3", decimals=0),
        "y": leaf(key("other_income", Q2_FY26), y, decimals=0),
    }
    result = evaluate_inr(dictionary, policy, row, key("test_binary", Q2_FY26, kind), operands)
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(exact)
    assert result.interval == Interval(lower=Fraction(bounds[0]), upper=Fraction(bounds[1]))


def test_a_nonzero_denominator_whose_interval_contains_zero_is_undefined(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """0.4 ± 0.5 = [−0.1, 0.9] may be zero, so 3 ÷ 0.4 has no bound even though 0.4 ≠ 0."""
    row = _binary_row(dictionary, FormulaOp.DIV, ValueKind.RATIO)
    operands = {
        "x": leaf(key("revenue_from_operations", Q2_FY26), "3", decimals=0),
        "y": leaf(key("other_income", Q2_FY26), "0.4", decimals=0),
    }
    result = evaluate_inr(
        dictionary, policy, row, key("test_binary", Q2_FY26, ValueKind.RATIO), operands
    )
    assert result.state is CalculationState.UNDEFINED
    assert result.exact is None and result.interval is None


# --- dimensional aggregation ---------------------------------------------------------------

MEMBERS = ("segment_a", "segment_b", "segment_c")


def _segment_key(member: str) -> MeasurementKey:
    """Q2 FY26 pre-elimination segment revenue for one member."""
    return key(
        "segment_revenue",
        Q2_FY26,
        dimensions=DimensionSet.of({"elimination_basis": "PRE_ELIMINATION", "segment": member}),
    )


def _segment_total(
    dictionary: CanonicalDictionary, policy: RoundingPolicy, values: dict[str, str | None]
) -> tuple[DictionaryRow, MeasurementKey, OperandValue]:
    """Aggregate segment revenue over the bound members (missing ones passed as ``None``)."""
    row = dictionary.row("segment_revenue_members_total")
    assert row.formula is not None
    aggregation = row.formula.operands[0].aggregation
    assert aggregation is not None
    bound = aggregation.bind_members(MEMBERS)
    total_key = _segment_key("reportable_segments_total")
    members = {
        member: None if value is None else leaf(_segment_key(member), value, interpretation_id=i)
        for i, (member, value) in enumerate(values.items(), start=1)
    }
    aggregate = aggregate_members(bound, members, output=total_key, policy=policy)
    output = total_key.model_copy(update={"canonical_id": row.canonical_id})
    return row, output, aggregate


def test_aggregation_over_every_member_computes(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A segment total over all evidenced members is their exact sum, with every member traced."""
    values: dict[str, str | None] = {"segment_a": "100.5", "segment_b": "200.25", "segment_c": "0"}
    row, output, aggregate = _segment_total(dictionary, policy, values)
    assert aggregate.state is SourceState.VALUE
    assert aggregate.exact == Fraction("300.75")
    assert aggregate.child_trace is not None
    assert aggregate.child_trace.trace_kind is TraceKind.DIMENSIONAL_AGGREGATE
    assert [op.interpretation_id for op in aggregate.child_trace.operands] == [1, 2, 3]
    result = evaluate_inr(dictionary, policy, row, output, {"segment_revenue": aggregate})
    assert result.state is CalculationState.COMPUTED
    assert result.value == Decimal("300.75")


def test_aggregation_with_a_missing_member_is_operand_missing(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A missing listed member never yields a smaller total; its absence stays in the trace."""
    values: dict[str, str | None] = {"segment_a": "100", "segment_b": None, "segment_c": "50"}
    row, output, aggregate = _segment_total(dictionary, policy, values)
    assert aggregate.state is SourceState.NO_VALUE
    assert aggregate.exact is None
    assert aggregate.child_trace is not None
    traced = {op.name: op for op in aggregate.child_trace.operands}
    assert set(traced) == set(MEMBERS)
    assert traced["segment_b"].source_state is SourceState.NO_VALUE
    assert traced["segment_b"].interpretation_id is None
    assert traced["segment_b"].key_digest == _segment_key("segment_b").digest()
    assert traced["segment_b"].selection_source is None
    assert traced["segment_b"].scoped_tier is UNPROVEN
    assert aggregate.selection_source is None
    result = evaluate_inr(dictionary, policy, row, output, {"segment_revenue": aggregate})
    assert result.state is CalculationState.OPERAND_MISSING
    assert result.source_state is SourceState.NO_VALUE


def test_aggregate_tier_is_the_weakest_member_tier(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """One unproven member makes the whole aggregate unproven."""
    aggregate = aggregate_members(
        _bound_segments(dictionary, MEMBERS[:2]),
        {
            "segment_a": leaf(_segment_key("segment_a"), "1"),
            "segment_b": leaf(_segment_key("segment_b"), "2", tier=UNPROVEN),
        },
        output=_segment_key("reportable_segments_total"),
        policy=policy,
    )
    assert aggregate.scoped_tier is UNPROVEN
    assert aggregate.child_trace is not None
    assert aggregate.child_trace.effective_tier is UNPROVEN


def _bound_segments(
    dictionary: CanonicalDictionary, members: tuple[str, ...]
) -> DimensionalAggregation:
    """The segment-revenue aggregation bound to ``members``."""
    row = dictionary.row("segment_revenue_members_total")
    assert row.formula is not None and row.formula.operands[0].aggregation is not None
    return row.formula.operands[0].aggregation.bind_members(members)


def test_aggregate_records_a_shared_selection_source_and_never_invents_one(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Members selected one way pass that source up; mixed sources pass none (ruling R3),
    each member keeping its own source in the child trace."""
    historical = SelectionSource.HISTORICAL_PACKAGE

    def total(second: SelectionSource) -> OperandValue:
        return aggregate_members(
            _bound_segments(dictionary, MEMBERS[:2]),
            {
                "segment_a": leaf(_segment_key("segment_a"), "1"),
                "segment_b": leaf(_segment_key("segment_b"), "2", selection_source=second),
            },
            output=_segment_key("reportable_segments_total"),
            policy=policy,
        )

    assert total(SelectionSource.PACKAGE_AS_REPORTED).selection_source is (
        SelectionSource.PACKAGE_AS_REPORTED
    )
    mixed = total(historical)
    assert mixed.state is SourceState.VALUE
    assert mixed.selection_source is None
    assert mixed.child_trace is not None
    assert [op.selection_source for op in mixed.child_trace.operands] == [
        SelectionSource.PACKAGE_AS_REPORTED,
        historical,
    ]


def test_a_selected_value_without_a_selection_source_is_refused() -> None:
    """Only a missing or computed operand may leave its selection source empty."""
    with pytest.raises(ValidationError):
        leaf(key("revenue_from_operations", Q2_FY26), "1", selection_source=None)
    missing = leaf(
        key("revenue_from_operations", Q2_FY26),
        None,
        state=SourceState.NO_VALUE,
        selection_source=None,
    )
    assert missing.selection_source is None


def test_a_member_at_another_value_kind_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Rupees and a count are never summed into one segment total."""
    count = _segment_key("segment_b").model_copy(update={"value_kind": ValueKind.COUNT})
    with pytest.raises(OperandKeyMismatchError):
        aggregate_members(
            _bound_segments(dictionary, MEMBERS[:2]),
            {"segment_a": leaf(_segment_key("segment_a"), "1"), "segment_b": leaf(count, "2")},
            output=_segment_key("reportable_segments_total"),
            policy=policy,
        )


def test_an_average_over_another_value_kind_is_refused(policy: RoundingPolicy) -> None:
    """An opening amount and a closing count are not averaged."""
    instant = "trade_receivables_current"
    closing = key(instant, PeriodInterval.at(date(2025, 9, 30))).model_copy(
        update={"value_kind": ValueKind.COUNT}
    )
    with pytest.raises(OperandKeyMismatchError):
        average_operand(
            leaf(key(instant, PeriodInterval.at(date(2025, 3, 31))), "1"),
            leaf(closing, "3"),
            output=key(instant, H1_FY26),
            policy=policy,
        )


# --- trace content -------------------------------------------------------------------------


def test_trace_hash_covers_exact_values(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Two evaluations that store the same rounding but differ exactly have different traces."""

    def opm(revenue: str) -> CalculationResult:
        operands = {
            "ebitda": leaf(key("ebitda_excl_other_income", Q2_FY26), "1"),
            "revenue": leaf(key("revenue_from_operations", Q2_FY26), revenue),
        }
        output = key("opm_pct", Q2_FY26, ValueKind.PERCENTAGE)
        return evaluate_inr(dictionary, policy, "opm_pct", output, operands)

    first, second = opm("300"), opm("300.0001")
    assert first.value == second.value
    assert first.trace.content_sha256() != second.trace.content_sha256()
    assert first.trace.content_sha256() == opm("300").trace.content_sha256()
