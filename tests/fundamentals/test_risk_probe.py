"""RESEARCH-3 S1 Task 3: the risk probe's guards, rules, statuses and section text (pure).

A row's status is a pure function of its statement's filed values, the matching prior's value
and the falsifier rows: an adverse input is never an ordinary ``PASSED``, a missing input names
what is missing, and trend and limit rules fire only in their own direction. The rendered body
holds no number outside a placeholder, a date or a check id (spec §1 rules 1 and 5; §2). The last
tests bind over an in-memory store: rules read the policy's stored precision, a window comes from
the run's own measurement context, and an interval reaching zero is a gap, not an aborted report.
``fundamentals.ledger.risk_probe`` is imported inside each test so the file collects before it
exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import Interpretation, InterpretationStatus
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import DimensionSet, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION
from fundamentals.ledger.claim_check import CRORE
from fundamentals.ledger.display import render_section
from fundamentals.ledger.falsifier_status import FalsifierRow
from fundamentals.ledger.import_mapping import measurement_key
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.verify.thesis_predicates import Disposition, FalsifierPredicate, PredicateOp

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
    merged: dict[str, str | None] = {**BASE, **(changes or {})}
    values = {key: Decimal(value) for key, value in merged.items() if value is not None}
    return _probe().Statement(
        balance_date=balance,
        window=None if window is None else PeriodInterval.duration(*window),
        stale=stale,
        values=values,
        lows={key: Fraction(value) for key, value in values.items()},
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
        (
            (date(2024, 2, 29), (date(2023, 3, 1), date(2024, 2, 29))),
            (date(2023, 2, 28), (date(2022, 3, 1), date(2023, 2, 28))),
            False,
        ),
    ],
    ids=["annual-on-annual", "half-year-on-annual", "leap-year-prior", "feb-29-has-no-prior"],
)
def test_a_trend_needs_the_same_window_one_year_earlier(
    current: tuple[date, tuple[date, date]],
    prior: tuple[date, tuple[date, date]],
    matched: bool,
) -> None:
    """(g) A trend compares like with like: the balance date one year earlier, the same
    duration class and start month. A half-year against a full year is not a trend; a prior
    with a 366-day window still matches (each statement keeps its own D); a February 29 balance
    has no same month-day a year earlier, so it has no prior rather than aborting the report."""
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


def _flag_sentence(row: Any, statement: Any) -> str:
    """The explanation's sentence for a flagged row."""
    body = str(_probe().body(statement, (row,), {}))
    (paragraph,) = (part for part in body.split("\n\n") if f"{row.check_id} is flagged" in part)
    return paragraph.split(". ")[0]


@pytest.mark.parametrize(
    ("check_id", "changes", "value", "prior", "limits", "says", "never"),
    [
        (
            "R4",
            {"cfo": "150", "profit_for_period": "100"},
            "150.00",
            "200.00",
            (),
            "fell against the same window a year earlier",
            ("not matched", "below reported profit", "large"),
        ),
        (
            "R4",
            {"cfo": "50"},
            "50.00",
            None,
            (),
            "operating cash was below reported profit",
            ("fell", "limit"),
        ),
        (
            "R6",
            {"borrowings_current": "0", "borrowings_noncurrent": "0", "total_equity": "-5"},
            None,
            None,
            (),
            "non-positive equity",
            ("borrowings are high", "high against"),
        ),
        (
            "R1",
            {},
            "90.00",
            "80.00",
            (),
            "rose against the same window a year earlier",
            ("large share", "customers owe"),
        ),
        (
            "R3",
            {},
            "40.00",
            None,
            ("R3",),
            "breached the approved thesis limit",
            ("large share", "are carrying"),
        ),
    ],
    ids=["t-with-cash-above-profit", "s", "guard-zero-borrowings", "t-receivables", "l"],
)
def test_an_explanation_states_only_what_its_rule_established(
    check_id: str,
    changes: dict[str, str],
    value: str | None,
    prior: str | None,
    limits: tuple[str, ...],
    says: str,
    never: tuple[str, ...],
) -> None:
    """A flag's sentence names the condition that fired it, so a reader is never told something
    the figures contradict: conversion falling while cash still exceeds profit is not profit
    unmatched by cash, negative equity with no debt is not high borrowings, and rising
    receivable days are not a large share of revenue. No sentence claims misconduct."""
    probe = _probe()
    statement = _statement(changes)
    row = probe.assess(
        check_id,
        statement,
        None if value is None else Decimal(value),
        None if prior is None else Decimal(prior),
        None,
        tuple(_limit(limit, Disposition.WEAKENED) for limit in limits),
    )
    assert row.status is probe.ProbeStatus.FLAGGED
    sentence = _flag_sentence(row, statement)
    assert says in sentence, sentence
    for phrase in (*never, "fraud", "manipulat", "misstat", "mislead", "conceal"):
        assert phrase not in sentence.lower(), sentence


@pytest.mark.parametrize("selected", [False, True], ids=["no-statement", "no-evaluable-row"])
def test_an_empty_section_still_names_every_non_evaluated_source(selected: bool) -> None:
    """(l) The one-paragraph fallbacks are where silence is likeliest to read as a clean bill, so
    they name the same sources in that paragraph, and stay free of stray numerals."""
    probe = _probe()
    statement = _statement({key: None for key in BASE}) if selected else None
    rows = (
        tuple(probe.assess(c, statement, None, None, None, ()) for c in probe.CHECKS)
        if selected
        else ()
    )
    text = str(probe.body(statement, rows, {}))
    (heading, paragraph) = (part for part in text.split("\n\n") if part)
    assert heading.startswith("## ")
    for source in SOURCES:
        assert f"NOT_ASSESSED: {source} not assessed by this probe" in paragraph
    assert scan_section(text, resolves=lambda *_: True) == ()


# Bound over an in-memory store ------------------------------------------------------------------

VERSIONS = ConfigVersions()
PRIOR_H1 = (date(2024, 4, 1), date(2024, 9, 30))
UNCERTAIN = "denominator's uncertainty interval reaches zero"
_OWN_SHA, _PRIOR_SHA = "a" * 64, "b" * 64


def _mapped(
    canonical_id: str, amount: str, period: PeriodInterval, half_width: str | None, **key_parts: Any
) -> Interpretation:
    """A ``MAPPED`` interpretation under the run's pins, ± ``half_width`` around ``amount``."""
    value = Decimal(amount)
    width = Decimal(half_width or 0)
    key = measurement_key(canonical_id, CRORE, 1, *H1).model_copy(
        update={"period": period, **key_parts}
    )
    return Interpretation.model_construct(
        status=InterpretationStatus.MAPPED,
        key=key,
        value=value,
        interval=Interval(lower=Fraction(value - width), upper=Fraction(value + width)),
        interpretation_id=1,
        mapping_entry_id=None,
        qualification_ref=None,
        dictionary_version=VERSIONS.dictionary,
        mapping_set_version=VERSIONS.mapping_set,
        normalisation_policy_version=VERSIONS.normalisation_policy,
        extractor_version=XBRL_EXTRACTOR_VERSION,
    )


def _filing(
    balance: date,
    window: tuple[date, date],
    changes: Mapping[str, str] | None = None,
    widths: Mapping[str, str] | None = None,
) -> tuple[Interpretation, ...]:
    """``BASE`` with ``changes``: balances at ``balance``, flows at ``window``."""
    instant, flow = PeriodInterval.at(balance), PeriodInterval.duration(*window)
    return tuple(
        _mapped(
            line,
            amount,
            instant if line in _probe().BALANCES else flow,
            (widths or {}).get(line),
        )
        for line, amount in {**BASE, **(changes or {})}.items()
    )


class _Store:
    """The reads ``_Binder`` makes of a capture's interpretations; traces are collected."""

    def __init__(self, filings: Mapping[str, tuple[Interpretation, ...]]) -> None:
        self.filings, self.traces = filings, list[Any]()

    def find_capture_ref(self, source_id: str, surface: str, sha: str) -> SimpleNamespace:
        return SimpleNamespace(capture_ref_id=sha)

    def list_capture_interpretations(self, sha: str) -> tuple[Interpretation, ...]:
        return self.filings[sha]

    def put_calculation_trace(self, trace: Any) -> int:
        self.traces.append(trace)
        return len(self.traces)


def _source(sha: str) -> Provenance:
    return Provenance(
        source_id="filing",
        file_sha256=sha,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="ctx",
        retrieved_at=datetime.now(UTC),
    )


def _bind(store: _Store, end: date = BALANCE) -> Any:
    """``bind_probe`` of a run ending ``end`` on its own filing, the YoY prior one if filed."""
    prior_end = date(end.year - 1, end.month, end.day)
    yoy = (_source(_PRIOR_SHA), prior_end) if _PRIOR_SHA in store.filings else (None, None)
    update = SimpleNamespace(
        period_start=date(end.year, end.month, 1).isoformat(),
        period_end=end.isoformat(),
        facts=[SimpleNamespace(role=FactRole.PROFIT_BEFORE_TAX, sources=[_source(_OWN_SHA)])],
        comparatives=[
            SimpleNamespace(
                qoq=SimpleNamespace(kind=ComparatorKind.QOQ, prior_source=None, period_end=None),
                yoy=SimpleNamespace(
                    kind=ComparatorKind.YOY, prior_source=yoy[0], period_end=yoy[1]
                ),
            )
        ],
    )
    return _probe().bind_probe(
        store, update, entity_id=1, versions=VERSIONS, fiscal_year_end_month=3
    )


def _rendered_row(probe: Any, rows: tuple[FalsifierRow, ...], check_id: str) -> str:
    """A check's row, placeholders filled."""
    _, body = _probe().probe_section(probe, rows)
    (line,) = (x for x in body.splitlines() if x.startswith(f"- {{{{e:computed}}}} {check_id} "))
    return render_section(line, probe.claims)


def test_a_breach_and_a_rise_inside_one_displayed_hundredth_still_flag() -> None:
    """Leverage of 0.1249 against a limit of 0.123, up from 0.1210: both read 0.12 at two places,
    which would report a held limit and no trend on a real breach and a real rise. Rules read the
    value at the policy's stored scale, and the report shows that same value."""
    levered = {"borrowings_current": "12.49", "borrowings_noncurrent": "0"}
    before = {"borrowings_current": "12.10", "borrowings_noncurrent": "0"}
    store = _Store(
        {
            _OWN_SHA: _filing(BALANCE, H1, levered),
            _PRIOR_SHA: _filing(date(2024, 9, 30), PRIOR_H1, before),
        }
    )
    probe = _bind(store)
    claims = {claim.claim_key: claim for claim in probe.claims}
    measured = claims["probe.R6"]
    assert (measured.value, claims["probe.R6.prior"].value) == (
        Decimal("0.124900"),
        Decimal("0.121000"),
    )
    assert {key: claims[key].precision for key in ("probe.R1", "probe.R4", "probe.R6")} == {
        "probe.R1": 2,
        "probe.R4": 2,
        "probe.R6": 6,
    }
    limit = FalsifierPredicate(metric_id="m", op=PredicateOp.GT, threshold=Decimal("0.123"))
    assert limit.holds(measured.value)
    row = _rendered_row(probe, (_limit("R6", Disposition.WEAKENED),), "R6")
    assert "FLAGGED by L, T" in row, row
    assert "0.124900" in row and "0.121000" in row, row


@pytest.mark.parametrize(
    "foreign",
    [
        {"basis": Basis.STANDALONE},
        {"dimensions": DimensionSet(pairs=(("segment", "cables"),))},
        {"currency": "USD"},
        {"framework": AccountingFramework.IFRS},
    ],
    ids=["standalone", "dimensional", "other-currency", "other-framework"],
)
def test_a_window_from_another_measurement_context_is_not_chosen(foreign: dict[str, Any]) -> None:
    """Complete consolidated half-year flows beside one annual revenue key of another basis,
    segment, currency or framework: taking that longer window would lose every consolidated flow
    and report filed lines as missing when they are there."""
    end = date(2026, 3, 31)
    half = (date(2025, 10, 1), end)
    year = PeriodInterval.duration(date(2025, 4, 1), end)
    stray = _mapped("revenue_from_operations", "5000", year, None, **foreign)
    probe = _bind(_Store({_OWN_SHA: (*_filing(end, half), stray)}), end)
    assert probe.statement.window == PeriodInterval.duration(*half)
    assert {f"probe.R{number}" for number in range(1, 7)} <= {c.claim_key for c in probe.claims}


def test_a_current_denominator_interval_reaching_zero_is_not_assessed() -> None:
    """Materials cost 100 + 1 − 100, each ± 0.5, has a positive point but cannot bound a quotient.
    R2 and R3 say so and store nothing; the report and its other checks go on. The five traces are
    R1, R4, R5, R6 and R6's borrowings sum."""
    lines = ("cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories")
    amounts = dict(zip(lines, ("100", "1", "-100"), strict=True))
    store = _Store({_OWN_SHA: _filing(BALANCE, H1, amounts, dict.fromkeys(lines, "0.5"))})
    probe = _bind(store)
    for check_id in ("R2", "R3"):
        row = _rendered_row(probe, (), check_id)
        assert f"NOT_ASSESSED ({UNCERTAIN})" in row, row
    assert not [c for c in probe.claims if c.claim_key.startswith(("probe.R2", "probe.R3"))]
    assert "probe.R1" in {c.claim_key for c in probe.claims}
    assert len(store.traces) == 5


def test_a_prior_denominator_interval_reaching_zero_leaves_only_its_trend_unevaluable() -> None:
    """A prior that cannot be divided must not cost the current figures: R2 and R6 stay computed,
    say why their trend is not evaluable and store no prior trace, and R1's own prior still holds.
    The thirteen traces are the six current ratios, their five sums, and R1's and R4's priors."""
    lines = ("cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories")
    weak = {**dict(zip(lines, ("100", "1", "-100"), strict=True)), "total_equity": "1"}
    widths = {**dict.fromkeys(lines, "0.5"), "total_equity": "2"}
    store = _Store(
        {
            _OWN_SHA: _filing(BALANCE, H1),
            _PRIOR_SHA: _filing(date(2024, 9, 30), PRIOR_H1, weak, widths),
        }
    )
    probe = _bind(store)
    keys = {c.claim_key for c in probe.claims}
    assert {"probe.R2", "probe.R6", "probe.R1.prior", "probe.R4.prior"} <= keys
    assert not {"probe.R2.prior", "probe.R6.prior"} & keys
    for check_id in ("R2", "R6"):
        row = _rendered_row(probe, (), check_id)
        assert f"COMPUTED (trend not evaluable: prior {UNCERTAIN})" in row, row
    assert len(store.traces) == 13
