"""RESEARCH-3 S1 Task 3: the risk probe's guards, rules, statuses and section text (pure).

A row's status is a pure function of its statement's filed values, the matching prior's value
and the falsifier rows: an adverse input is never an ordinary ``PASSED``, a missing input names
what is missing, and trend and limit rules fire only in their own direction. The rendered body
holds no number outside a placeholder, a date or a check id (spec §1 rules 1 and 5; §2).
``fundamentals.ledger.risk_probe`` is imported inside each test so the file collects before it
exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import ModuleType
from typing import Any

import pytest

from fundamentals.ledger.falsifier_status import FalsifierRow
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.verify.thesis_predicates import Disposition, PredicateOp

H1 = (date(2025, 4, 1), date(2025, 9, 30))
BALANCE = date(2025, 9, 30)
# Filed amounts with every operand present and positive, cfo above profit: no guard and no S.
BASE = {
    "trade_receivables_current": "100",
    "inventories": "100",
    "trade_payables_current": "100",
    "borrowings_current": "10",
    "borrowings_noncurrent": "10",
    "total_equity": "100",
    "revenue_from_operations": "1000",
    "cost_of_materials_consumed": "800",
    "purchases_of_stock_in_trade": "10",
    "changes_in_inventories": "-10",
    "cfo": "120",
    "profit_for_period": "100",
    "cf_capex_ppe": "-50",
}
SOURCES = (
    "related parties",
    "pledges",
    "contingent liabilities",
    "auditor opinion",
    "capitalised intangibles",
    "rating remarks",
    "disclosure lapses",
)
NO_WINDOW = "no half-year or annual flow window in the statement"


def _probe() -> ModuleType:
    """The probe module, imported only when a test runs."""
    from fundamentals.ledger import risk_probe

    return risk_probe


def _statement(
    changes: Mapping[str, str | None] | None = None,
    *,
    window: tuple[date, date] | None = H1,
    balance: date = BALANCE,
    stale: bool = False,
) -> Any:
    """A statement of ``BASE`` with ``changes`` applied (``None`` drops an operand)."""
    from fundamentals.contracts.measurement_key import PeriodInterval

    merged: dict[str, str | None] = {**BASE, **(changes or {})}
    return _probe().Statement(
        capture_sha256="a" * 64,
        balance_date=balance,
        window=None if window is None else PeriodInterval.duration(*window),
        stale=stale,
        values={key: Decimal(value) for key, value in merged.items() if value is not None},
    )


def _limit(check_id: str, disposition: Disposition) -> FalsifierRow:
    """A thesis falsifier evaluated on the check's claim."""
    return FalsifierRow(
        falsifier_id="F6",
        label="Probe limit",
        op=PredicateOp.GT,
        claim_key=f"probe.{check_id}",
        disposition=disposition,
        reason=None,
    )


def test_cash_conversion_below_profit_is_flagged_by_s() -> None:
    """(a) Operating cash below reported profit in the same window flags R4 under S, with no
    prior and no limit: the two cited values are the whole rule."""
    probe = _probe()
    statement = _statement({"cfo": "50"})
    assert probe.guard("R4", statement) is None
    row = probe.assess("R4", statement, Decimal("50.00"), None, None, ())
    assert (row.status, row.rules, row.shown) == (probe.ProbeStatus.FLAGGED, ("S",), True)


@pytest.mark.parametrize(
    ("check_id", "changes", "reason"),
    [
        ("R4", {"profit_for_period": "-10", "cfo": "-20"}, "non-positive profit"),
        ("R6", {"total_equity": "-5"}, "non-positive equity"),
    ],
    ids=["loss", "negative-equity"],
)
def test_a_loss_or_negative_equity_is_flagged_without_its_ratio(
    check_id: str, changes: dict[str, str], reason: str
) -> None:
    """(b)(c) A loss or negative equity makes the ratio meaningless, but it is an adverse
    finding, not a gap: ``FLAGGED`` with the reason, the ratio not shown; R4's S is still
    evaluated (cash below the loss fires it)."""
    probe = _probe()
    statement = _statement(changes)
    assert probe.guard(check_id, statement) == (probe.ProbeStatus.FLAGGED, reason)
    row = probe.assess(check_id, statement, None, None, None, ())
    assert (row.status, row.reason, row.shown) == (probe.ProbeStatus.FLAGGED, reason, False)
    if check_id == "R4":
        assert "S" in row.rules


@pytest.mark.parametrize(
    ("check_id", "changes"),
    [
        ("R1", {"revenue_from_operations": "0"}),
        ("R5", {"revenue_from_operations": "-1"}),
        ("R2", {"changes_in_inventories": "-810"}),
        ("R3", {"cost_of_materials_consumed": "-100"}),
    ],
    ids=["zero-revenue", "negative-revenue", "zero-materials", "negative-materials"],
)
def test_a_non_positive_flow_denominator_is_not_assessed(
    check_id: str, changes: dict[str, str]
) -> None:
    """(d) Days or intensity over zero or negative revenue or materials cost (M = materials +
    purchases + change in inventories) say nothing: ``NOT_ASSESSED``, never a value."""
    probe = _probe()
    outcome = probe.guard(check_id, _statement(changes))
    assert outcome is not None and outcome[0] is probe.ProbeStatus.NOT_ASSESSED


@pytest.mark.parametrize(
    ("check_id", "missing"),
    [
        ("R1", "trade_receivables_current"),
        ("R2", "purchases_of_stock_in_trade"),
        ("R6", "total_equity"),
    ],
)
def test_a_missing_operand_is_not_assessed_naming_it(check_id: str, missing: str) -> None:
    """(e) The reader is told which filed line is missing, so the gap can be monitored."""
    probe = _probe()
    outcome = probe.guard(check_id, _statement({missing: None}))
    assert outcome is not None
    status, reason = outcome
    assert status is probe.ProbeStatus.NOT_ASSESSED and missing in reason


@pytest.mark.parametrize(
    ("check_id", "changes"),
    [("R1", {"trade_receivables_current": "-1"}), ("R5", {"cf_capex_ppe": "50"})],
    ids=["negative-receivable", "capex-inflow"],
)
def test_a_negative_balance_or_capex_inflow_is_a_sign_anomaly(
    check_id: str, changes: dict[str, str]
) -> None:
    """(f) A balance below zero or a capex line reading as an inflow is a filing or mapping
    fault, not a business signal."""
    probe = _probe()
    assert probe.guard(check_id, _statement(changes)) == (
        probe.ProbeStatus.NOT_ASSESSED,
        "sign anomaly in filed line",
    )


@pytest.mark.parametrize(
    ("current", "prior", "matched"),
    [
        (
            (date(2026, 3, 31), (date(2025, 4, 1), date(2026, 3, 31))),
            (date(2025, 3, 31), (date(2024, 4, 1), date(2025, 3, 31))),
            True,
        ),
        (
            (date(2025, 9, 30), H1),
            (date(2025, 3, 31), (date(2024, 4, 1), date(2025, 3, 31))),
            False,
        ),
        (
            (date(2025, 3, 31), (date(2024, 4, 1), date(2025, 3, 31))),
            (date(2024, 3, 31), (date(2023, 4, 1), date(2024, 3, 31))),
            True,
        ),
    ],
    ids=["annual-on-annual", "half-year-on-annual", "leap-year-prior"],
)
def test_a_trend_needs_the_same_window_one_year_earlier(
    current: tuple[date, tuple[date, date]],
    prior: tuple[date, tuple[date, date]],
    matched: bool,
) -> None:
    """(g) A trend compares like with like: the balance date one year earlier, the same
    duration class and start month. A half-year against a full year is not a trend; a prior
    with a 366-day window still matches (each statement keeps its own D)."""
    probe = _probe()
    now = _statement(balance=current[0], window=current[1])
    then = _statement(balance=prior[0], window=prior[1])
    assert probe.matches(now, then) is matched


@pytest.mark.parametrize(
    ("check_id", "value", "prior", "flagged"),
    [
        ("R1", "90.00", "80.00", True),
        ("R1", "70.00", "80.00", False),
        ("R4", "95.00", "130.00", True),
        ("R4", "140.00", "130.00", False),
        ("R6", "0.30", "0.20", True),
    ],
    ids=["receivables-up", "receivables-down", "conversion-down", "conversion-up", "debt-up"],
)
def test_a_trend_flags_only_in_its_arrow_direction(
    check_id: str, value: str, prior: str, flagged: bool
) -> None:
    """(h) Rising receivable days or leverage and falling cash conversion are adverse; the
    opposite move is an evaluated rule that holds (``PASSED``), not a flag."""
    probe = _probe()
    row = probe.assess(check_id, _statement(), Decimal(value), Decimal(prior), None, ())
    want = probe.ProbeStatus.FLAGGED if flagged else probe.ProbeStatus.PASSED
    assert (row.status, row.rules, row.prior_shown) == (want, ("T",) if flagged else (), True)


@pytest.mark.parametrize("disposition", [Disposition.WEAKENED, Disposition.HELD])
def test_a_weakened_limit_flags_the_row_and_names_it(disposition: Disposition) -> None:
    """(i) A breached thesis limit is evidence against the thesis: the row is flagged under L
    and names the falsifier; a held limit is an evaluated rule, so the row passes."""
    probe = _probe()
    row = probe.assess(
        "R3", _statement(), Decimal("40.00"), None, None, (_limit("R3", disposition),)
    )
    if disposition is Disposition.WEAKENED:
        assert (row.status, row.rules, row.falsifier_ids) == (
            probe.ProbeStatus.FLAGGED,
            ("L",),
            ("F6",),
        )
    else:
        assert (row.status, row.rules) == (probe.ProbeStatus.PASSED, ())


def test_no_prior_and_no_limit_is_computed() -> None:
    """(j) A value with no rule to test it is shown as computed, not as a pass."""
    probe = _probe()
    row = probe.assess("R3", _statement(), Decimal("40.00"), None, None, ())
    assert row.status is probe.ProbeStatus.COMPUTED and row.shown
    assert row.reason is not None and "no rule evaluable" in row.reason


def _rows(probe: ModuleType, statement: Any) -> tuple[Any, ...]:
    """One row of every status over ``statement``."""
    return (
        probe.assess("R1", statement, Decimal("36.50"), None, None, ()),
        probe.assess("R2", statement, Decimal("45.60"), Decimal("40.00"), None, ()),
        probe.assess(
            "R3", statement, Decimal("45.60"), None, None, (_limit("R3", Disposition.HELD),)
        ),
        probe.assess("R4", statement, Decimal("120.00"), None, None, ()),
        probe.assess("R5", _statement({"cf_capex_ppe": "50"}), None, None, None, ()),
        probe.assess(
            "R6", statement, Decimal("0.20"), None, None, (_limit("R6", Disposition.WEAKENED),)
        ),
    )


def _body(statement: Any) -> str:
    """The section body of every status over ``statement``."""
    probe = _probe()
    keys = {check_id: (f"probe.{check_id}.revenue_from_operations",) for check_id in probe.CHECKS}
    return str(probe.body(statement, _rows(probe, statement), keys))


@pytest.mark.parametrize("stale", [True, False])
def test_a_stale_statement_says_so(stale: bool) -> None:
    """(k) A comparator's statement shows its own balance date and is marked stale, so a
    reader does not take it for the run's period."""
    text = _body(_statement(stale=stale))
    assert BALANCE.isoformat() in text
    assert ("stale" in text.lower()) is stale


def test_every_non_evaluated_source_is_named() -> None:
    """(l) What the probe cannot see is listed, so silence is not read as a clean bill."""
    text = _body(_statement())
    for source in SOURCES:
        assert f"NOT_ASSESSED: {source} not assessed by this probe" in text


def test_the_rendered_body_raises_no_numeral_or_label_state() -> None:
    """(m) Every number in the section is a placeholder, a date or a check id, and every
    paragraph carries an epistemic label."""
    assert scan_section(_body(_statement()), resolves=lambda *_: True) == ()


def test_a_statement_with_no_flow_window_assesses_only_the_balance_check() -> None:
    """(n) Without a half-year or annual window the flow checks have no D or flow to divide
    by; borrowings to equity reads instants only and is still assessed."""
    probe = _probe()
    statement = _statement(window=None)
    for check_id in ("R1", "R2", "R3", "R4", "R5"):
        assert probe.guard(check_id, statement) == (probe.ProbeStatus.NOT_ASSESSED, NO_WINDOW)
    assert probe.guard("R6", statement) is None
