"""D1a.3 acceptance: period derivation (Q4 = FY − 9M, H2 = FY − H1, TTM; data spec §1).

A derived quarter is only trustworthy when its operands nest exactly in time, share one
revision basis, value kind and currency, and are additive amounts: Q4 = FY − 9M is refused
when it would mix restated and original bases, EPS is never summed, and a key at another
kind or currency is a caller defect rather than a number.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from fractions import Fraction

import pytest
from canon_formula_support import (
    FY25,
    FY25_QUARTERS,
    H1_FY25,
    H2_FY25,
    NINE_M_FY25,
    Q4_FY25,
    key,
    leaf,
    load_v1_dictionary,
    load_v1_policy,
)

from equity_os.contracts.measurement.canonical import ValueIdentity, ValueKind
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.verification.comparison import CalculationState, SourceState
from equity_os.normalisation.derivation.formula import (
    CurrencyMismatchError,
    OperandKeyMismatchError,
    TraceKind,
)
from equity_os.normalisation.derivation.interval import Interval, RoundingPolicy
from equity_os.normalisation.derivation.period_aggregation import (
    AggregationOperand,
    NonAdditiveAggregationError,
    PeriodAlignmentError,
    PeriodDerivation,
    derive_period_value,
)
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary

REVENUE = "revenue_from_operations"


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Dictionary v1 as committed."""
    return load_v1_dictionary()


@pytest.fixture(scope="module")
def policy() -> RoundingPolicy:
    """Rounding policy v1 as committed."""
    return load_v1_policy()


def _amount(
    period: PeriodInterval,
    value: str,
    restated: bool = False,
    kind: ValueKind = ValueKind.CURRENCY_AMOUNT,
) -> AggregationOperand:
    """A revenue operand for one period, flagged when it has a differing eligible restatement."""
    return AggregationOperand(
        operand=leaf(key(REVENUE, period, kind), value, decimals=-5),
        has_differing_restatement=restated,
    )


def test_q4_is_fy_minus_nine_months(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Q4 = FY − 9M is DERIVED, exact, and keeps both operands in its trace."""
    result = derive_period_value(
        PeriodDerivation.Q4_FROM_FY_MINUS_9M,
        dictionary.row(REVENUE),
        key(REVENUE, Q4_FY25),
        [_amount(FY25, "1850000000"), _amount(NINE_M_FY25, "1300000000")],
        policy,
    )
    assert result.state is CalculationState.COMPUTED
    assert result.exact == Fraction(550000000)
    # Each operand is ± 50 000 (half of 10^5), so the difference is ± 100 000.
    assert result.interval == Interval(lower=Fraction(549900000), upper=Fraction(550100000))
    assert result.trace.value_identity is ValueIdentity.DERIVED
    assert result.trace.trace_kind is TraceKind.PERIOD_DERIVATION
    assert [op.key_digest for op in result.trace.operands] == [
        key(REVENUE, FY25).digest(),
        key(REVENUE, NINE_M_FY25).digest(),
    ]


def test_q4_over_a_restated_nine_months_is_revision_incompatible(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """A 9M with a differing eligible restatement would mix bases; the derivation is refused."""
    result = derive_period_value(
        PeriodDerivation.Q4_FROM_FY_MINUS_9M,
        dictionary.row(REVENUE),
        key(REVENUE, Q4_FY25),
        [_amount(FY25, "1850000000"), _amount(NINE_M_FY25, "1300000000", restated=True)],
        policy,
    )
    assert result.state is CalculationState.REVISION_INCOMPATIBLE
    assert result.source_state is SourceState.INVALID
    assert result.exact is None and result.value is None


def test_h2_and_ttm_derive(dictionary: CanonicalDictionary, policy: RoundingPolicy) -> None:
    """H2 = FY − H1, and TTM sums four contiguous quarters ending at the output end."""
    row = dictionary.row(REVENUE)
    h2 = derive_period_value(
        PeriodDerivation.H2_FROM_FY_MINUS_H1,
        row,
        key(REVENUE, H2_FY25),
        [_amount(FY25, "1850000000"), _amount(H1_FY25, "800000000")],
        policy,
    )
    assert h2.exact == Fraction(1050000000)
    ttm = derive_period_value(
        PeriodDerivation.TTM_FROM_FOUR_QUARTERS,
        row,
        key(REVENUE, FY25),
        [_amount(period, "400000000") for period in FY25_QUARTERS],
        policy,
    )
    assert ttm.state is CalculationState.COMPUTED
    assert ttm.exact == Fraction(1600000000)
    # Four operands at ± 50 000 each.
    assert ttm.interval == Interval(lower=Fraction(1599800000), upper=Fraction(1600200000))


@pytest.mark.parametrize(
    ("derivation", "output", "periods"),
    [
        pytest.param(
            PeriodDerivation.Q4_FROM_FY_MINUS_9M,
            Q4_FY25,
            (FY25, PeriodInterval.duration(date(2024, 5, 1), date(2025, 1, 31))),
            id="nine-months-not-starting-at-fy-start",
        ),
        pytest.param(
            PeriodDerivation.Q4_FROM_FY_MINUS_9M,
            PeriodInterval.duration(date(2024, 12, 1), date(2025, 3, 31)),
            (FY25, NINE_M_FY25),
            id="output-not-the-remainder",
        ),
        pytest.param(
            PeriodDerivation.TTM_FROM_FOUR_QUARTERS,
            FY25,
            (FY25_QUARTERS[0], FY25_QUARTERS[1], FY25_QUARTERS[3]),
            id="three-quarters-with-a-gap",
        ),
        pytest.param(
            PeriodDerivation.TTM_FROM_FOUR_QUARTERS,
            PeriodInterval.duration(date(2024, 7, 1), date(2025, 6, 30)),
            (
                FY25_QUARTERS[1],
                FY25_QUARTERS[3],
                PeriodInterval.duration(date(2025, 4, 1), date(2025, 6, 30)),
                PeriodInterval.duration(date(2025, 4, 1), date(2025, 6, 30)),
            ),
            id="four-quarters-with-a-gap",
        ),
        pytest.param(
            PeriodDerivation.TTM_FROM_FOUR_QUARTERS,
            FY25,
            (FY25_QUARTERS[0], FY25_QUARTERS[2], FY25_QUARTERS[1], FY25_QUARTERS[3]),
            id="quarters-out-of-order",
        ),
    ],
)
def test_misaligned_period_operands_are_refused(
    dictionary: CanonicalDictionary,
    policy: RoundingPolicy,
    derivation: PeriodDerivation,
    output: PeriodInterval,
    periods: Sequence[PeriodInterval],
) -> None:
    """Only a nested subtrahend with the exact remainder, or four contiguous quarters, derive."""
    with pytest.raises(PeriodAlignmentError):
        derive_period_value(
            derivation,
            dictionary.row(REVENUE),
            key(REVENUE, output),
            [_amount(period, "1") for period in periods],
            policy,
        )


def test_eps_is_never_derived_across_periods(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Per-share values are reported or not available; TTM or Q4 EPS is never summed."""
    eps = dictionary.row("eps_basic")

    def operand(period: PeriodInterval) -> AggregationOperand:
        measurement = key("eps_basic", period, ValueKind.PER_SHARE_AMOUNT)
        return AggregationOperand(operand=leaf(measurement, "10"), has_differing_restatement=False)

    with pytest.raises(NonAdditiveAggregationError):
        derive_period_value(
            PeriodDerivation.Q4_FROM_FY_MINUS_9M,
            eps,
            key("eps_basic", Q4_FY25, ValueKind.PER_SHARE_AMOUNT),
            [operand(FY25), operand(NINE_M_FY25)],
            policy,
        )


def test_an_output_keyed_at_another_kind_than_the_row_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """Revenue is a currency amount; Q4 revenue keyed as a count would store at the wrong
    scale and compare against counts, even with operands keyed the same way."""
    with pytest.raises(OperandKeyMismatchError):
        derive_period_value(
            PeriodDerivation.Q4_FROM_FY_MINUS_9M,
            dictionary.row(REVENUE),
            key(REVENUE, Q4_FY25, ValueKind.COUNT),
            [
                _amount(FY25, "1850000000", kind=ValueKind.COUNT),
                _amount(NINE_M_FY25, "1300000000", kind=ValueKind.COUNT),
            ],
            policy,
        )


def test_an_operand_in_another_currency_is_refused(
    dictionary: CanonicalDictionary, policy: RoundingPolicy
) -> None:
    """FY in INR minus a 9M in USD is not a quarter; D1a refuses rather than converts."""
    usd = leaf(key(REVENUE, NINE_M_FY25).model_copy(update={"currency": "USD"}), "1300000000")
    with pytest.raises(CurrencyMismatchError):
        derive_period_value(
            PeriodDerivation.Q4_FROM_FY_MINUS_9M,
            dictionary.row(REVENUE),
            key(REVENUE, Q4_FY25),
            [
                _amount(FY25, "1850000000"),
                AggregationOperand(operand=usd, has_differing_restatement=False),
            ],
            policy,
        )
