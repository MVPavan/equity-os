"""D1a.3 acceptance: exact rational intervals, half-even storage and outward bounds.

Every computed financial figure passes through these operations. Arithmetic must stay
exact so a value is never re-rounded mid-calculation, and storage must round the point
value half-even while widening (never narrowing) its uncertainty bounds, so an interval
read back from storage still contains the exact value it was computed from.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from equity_os.contracts.measurement.canonical import ValueKind
from equity_os.normalisation.derivation.interval import (
    Interval,
    RoundingPolicy,
    RoundingPolicyError,
    UndefinedDivisionError,
    load_rounding_policy,
    store_bounds,
    store_value,
)

POLICY_PATH = (
    Path(__file__).resolve().parents[4] / "config" / "normalisation/rounding_policy" / "v1.yaml"
)


@pytest.fixture(scope="module")
def policy() -> RoundingPolicy:
    """Rounding policy v1 as committed."""
    return load_rounding_policy(POLICY_PATH)


def _iv(lower: str, upper: str) -> Interval:
    """An interval from rational literals."""
    return Interval(lower=Fraction(lower), upper=Fraction(upper))


def test_policy_pins_its_content() -> None:
    """The run manifest pins the policy by content, so the hash must be of the file bytes."""
    loaded = load_rounding_policy(POLICY_PATH)
    assert loaded.policy_id == "v1"
    assert loaded.content_sha256 == hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def test_policy_without_a_scale_for_every_kind_is_refused(tmp_path: Path) -> None:
    """A value kind with no pinned scale could not be stored; the loader refuses up front."""
    partial = tmp_path / "v1.yaml"
    partial.write_text("policy_id: v1\nscale:\n  CURRENCY_AMOUNT: 2\n", encoding="utf-8")
    with pytest.raises(RoundingPolicyError):
        load_rounding_policy(partial)


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("add", ("-1/2", "5")),
        ("sub", ("-7/2", "2")),
        ("mul", ("-3", "6")),
        ("div", ("-3/2", "3")),
    ],
)
def test_interval_arithmetic_is_exact(operation: str, expected: tuple[str, str]) -> None:
    """Bounds follow interval arithmetic exactly; mul and div take the extreme products."""
    left = _iv("-3/2", "3")
    right = _iv("1", "2")
    result = getattr(left, operation)(right)
    assert result == _iv(*expected)


def test_mul_of_two_straddling_intervals_takes_every_corner() -> None:
    """With signs mixed on both sides the extremes are not the like-for-like products."""
    assert _iv("-2", "3").mul(_iv("-5", "1")) == _iv("-15", "10")


def test_shift_moves_both_bounds() -> None:
    """A definition record's explained amount moves the whole interval."""
    assert _iv("1", "2").shift(Fraction(-5, 2)) == _iv("-3/2", "-1/2")


@pytest.mark.parametrize(("lower", "upper"), [("-1", "1"), ("0", "1"), ("-1", "0"), ("0", "0")])
def test_division_by_an_interval_containing_zero_is_undefined(lower: str, upper: str) -> None:
    """A denominator that may be zero gives no bound at all; the result is UNDEFINED."""
    with pytest.raises(UndefinedDivisionError):
        _iv("1", "2").div(_iv(lower, upper))


def test_from_precision_is_half_a_unit_either_side() -> None:
    """A native value's interval is value ± half its declared precision (data spec §5)."""
    assert Interval.from_precision(Decimal("57154.2"), 1) == _iv("57154.15", "57154.25")
    assert Interval.from_precision(Decimal("1200000"), -5) == _iv("1150000", "1250000")


@pytest.mark.parametrize("value", [Decimal("12500"), Fraction(7, 3)])
def test_exact_values_are_singletons(value: Decimal | Fraction) -> None:
    """An exact count or an XBRL INF value has no width, so adjacent counts never agree."""
    interval = Interval.exact(value)
    assert interval.lower == interval.upper == Fraction(value)
    assert not interval.intersects(Interval.exact(Fraction(value) + 1))


def test_intersects_and_gap() -> None:
    """Overlapping intervals have no gap; disjoint ones report the distance between them."""
    assert _iv("1", "2").intersects(_iv("2", "3"))
    assert _iv("1", "2").gap(_iv("3/2", "5")) == 0
    assert _iv("1", "2").gap(_iv("5/2", "3")) == Fraction(1, 2)
    assert _iv("5/2", "3").gap(_iv("1", "2")) == Fraction(1, 2)


def test_interval_refuses_floats_and_reversed_bounds() -> None:
    """A float would smuggle binary rounding into exact arithmetic; reversed bounds are refused."""
    with pytest.raises(ValidationError):
        Interval(lower=0.1, upper=Fraction(1))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        _iv("2", "1")


@pytest.mark.parametrize(
    ("kind", "value", "stored"),
    [
        (ValueKind.CURRENCY_AMOUNT, "1/8", "0.12"),
        (ValueKind.CURRENCY_AMOUNT, "27/200", "0.14"),
        (ValueKind.CURRENCY_AMOUNT, "-1/8", "-0.12"),
        (ValueKind.PER_SHARE_AMOUNT, "5/8", "0.62"),
        (ValueKind.PERCENTAGE, "1613/200", "8.06"),
        (ValueKind.DAYS, "4567/200", "22.84"),
        (ValueKind.COUNT, "5/2", "2"),
        (ValueKind.COUNT, "7/2", "4"),
        (ValueKind.RATIO, "1/2000000", "0.000000"),
        (ValueKind.RATIO, "3/2000000", "0.000002"),
    ],
)
def test_store_value_rounds_half_even_at_the_pinned_scale(
    policy: RoundingPolicy, kind: ValueKind, value: str, stored: str
) -> None:
    """Exactly-half values go to the even digit at each kind's v1 scale; nothing else rounds."""
    result = store_value(Fraction(value), kind, policy)
    assert result == Decimal(stored)
    assert result.as_tuple().exponent == Decimal(stored).as_tuple().exponent


@pytest.mark.parametrize(
    ("interval", "kind", "stored"),
    [
        (("1/3", "2/3"), ValueKind.CURRENCY_AMOUNT, ("0.33", "0.67")),
        (("-2/3", "-1/3"), ValueKind.CURRENCY_AMOUNT, ("-0.67", "-0.33")),
        (("1/8", "1/8"), ValueKind.PERCENTAGE, ("0.12", "0.13")),
        (("5/2", "7/2"), ValueKind.COUNT, ("2", "4")),
        (("1/4", "3/4"), ValueKind.RATIO, ("0.250000", "0.750000")),
    ],
)
def test_store_bounds_round_outward(
    policy: RoundingPolicy,
    interval: tuple[str, str],
    kind: ValueKind,
    stored: tuple[str, str],
) -> None:
    """Lower bounds round down and upper bounds up, so stored bounds contain the exact ones."""
    lower, upper = store_bounds(_iv(*interval), kind, policy)
    assert (lower, upper) == (Decimal(stored[0]), Decimal(stored[1]))
    assert Fraction(lower) <= Fraction(interval[0]) and Fraction(upper) >= Fraction(interval[1])


_LARGE = "1234567890123456789012345678.91"


def test_storage_never_rounds_through_the_decimal_context(policy: RoundingPolicy) -> None:
    """A stored figure keeps every digit: the default 28-digit context must not cut a large
    amount, and a caller's low-precision context must not cut an ordinary one."""
    large = Fraction(_LARGE)
    assert str(store_value(large, ValueKind.CURRENCY_AMOUNT, policy)) == _LARGE
    lower, upper = store_bounds(
        Interval(lower=large - Fraction(1, 200), upper=large + Fraction(1, 200)),
        ValueKind.CURRENCY_AMOUNT,
        policy,
    )
    assert (str(lower), str(upper)) == (
        "1234567890123456789012345678.90",
        "1234567890123456789012345678.92",
    )
    with localcontext() as context:
        context.prec = 3
        value = store_value(Fraction("123.45"), ValueKind.CURRENCY_AMOUNT, policy)
        bounds = store_bounds(_iv("12344/100", "12346/100"), ValueKind.CURRENCY_AMOUNT, policy)
    assert str(value) == "123.45"
    assert tuple(str(bound) for bound in bounds) == ("123.44", "123.46")


def test_policy_with_a_negative_scale_is_refused(tmp_path: Path) -> None:
    """A negative scale would round to tens through a float factor; v1 uses none (ruling R1)."""
    text = POLICY_PATH.read_text(encoding="utf-8").replace("COUNT: 0", "COUNT: -1")
    assert "COUNT: -1" in text
    negative = tmp_path / "v1.yaml"
    negative.write_text(text, encoding="utf-8")
    with pytest.raises(RoundingPolicyError):
        load_rounding_policy(negative)


def test_policy_scale_cannot_be_changed_after_loading(policy: RoundingPolicy) -> None:
    """The policy is pinned by content hash, so its scales must not change under that hash."""
    with pytest.raises(TypeError):
        policy.scale[ValueKind.COUNT] = 5  # type: ignore[index]
    assert policy.scale[ValueKind.COUNT] == 0


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: Interval.exact(0.1), id="exact-float"),  # type: ignore[arg-type]
        pytest.param(
            lambda: Interval.from_precision(0.1, 1),  # type: ignore[arg-type]
            id="from-precision-float",
        ),
    ],
)
def test_interval_factories_refuse_floats(build: Callable[[], Interval]) -> None:
    """``Fraction(0.1)`` is the binary float, not one tenth; the factories refuse it."""
    with pytest.raises(TypeError):
        build()
