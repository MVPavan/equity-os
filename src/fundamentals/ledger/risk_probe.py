"""The risk probe: six checks on a filed statement, their guards and rules, and the section
(RESEARCH-3 S1, spec §2).

R1–R6 read closing balances and half-year or annual flows. Guards run first: a missing operand,
a non-positive flow denominator or a sign anomaly is ``NOT_ASSESSED``; a loss (R4) or
non-positive equity (R6) is ``FLAGGED`` without its ratio. Then S (cash below profit), L (a
weakened thesis limit) and T (a strict move in the arrow's direction against the same window one
year earlier). Status, first match wins: guard, a fired rule, an evaluated rule, ``COMPUTED``.
Labels, reasons and sentences hold no digits; every number is a claim placeholder.
``bind_probe`` reads the statement straight from its interpretations (``_Binder.filed``), stores
each ratio's trace (sums as child traces) and cites it; ``probe_section`` renders the rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import PeriodKind, ValueKind
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.comparison import SelectionSource
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.ledger import NumericClaim, Rounding
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.role import FactRole
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.claim_check import CRORE, PERCENT
from fundamentals.ledger.display import FILED
from fundamentals.ledger.falsifier_status import METRICS, RISK_PROBE, FalsifierRow
from fundamentals.ledger.import_mapping import _slot, _valued, refs
from fundamentals.ledger.run_traces import (
    _CRORE_SCALE,
    CRORE_UNIT,
    DAYS,
    OUTFLOW_PCT,
    RATIO,
    RATIO_PCT,
    SUM,
    _Binder,
    _Operand,
    cite,
)
from fundamentals.output.earnings_update import EarningsUpdate
from fundamentals.verify.thesis_predicates import Disposition


class ProbeStatus(StrEnum):
    """A probe row's status."""

    NOT_ASSESSED = "NOT_ASSESSED"
    FLAGGED = "FLAGGED"
    PASSED = "PASSED"
    COMPUTED = "COMPUTED"


class Check(BaseModel):
    """One probe check: its thesis metric, label, formula, operands (the denominator's ids are
    summed), trend arrow (+1 up is adverse, −1 down, ``None`` no trend), category, business
    meaning and its outcome when the denominator is not positive."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    label: str
    formula: str
    numerator: tuple[str, ...]
    denominator: tuple[str, ...]
    arrow: int | None
    category: str
    meaning: str
    nonpositive: tuple[ProbeStatus, str]


class Statement(BaseModel):
    """The filed statement a probe reads: its capture, balance date, flow window, whether it
    predates the run's period, and the exact base-unit amounts of the operands found."""

    model_config = ConfigDict(frozen=True)

    capture_sha256: str
    balance_date: date
    window: PeriodInterval | None
    stale: bool
    values: Mapping[str, Decimal]


class ProbeRow(BaseModel):
    """A check's outcome: status, reason, fired rules, weakened falsifiers, and whether its
    value and prior are shown."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    status: ProbeStatus
    reason: str | None
    rules: tuple[str, ...]
    falsifier_ids: tuple[str, ...]
    shown: bool
    prior_shown: bool


RECEIVABLES, INVENTORIES, PAYABLES = (
    "trade_receivables_current",
    "inventories",
    "trade_payables_current",
)
BORROWINGS = ("borrowings_current", "borrowings_noncurrent")
EQUITY, REVENUE, CFO, PROFIT, CAPEX = (
    "total_equity",
    "revenue_from_operations",
    "cfo",
    "profit_for_period",
    "cf_capex_ppe",
)
M = ("cost_of_materials_consumed", "purchases_of_stock_in_trade", "changes_in_inventories")
BALANCES = frozenset({RECEIVABLES, INVENTORIES, PAYABLES, *BORROWINGS, EQUITY})
# The sign a filed line must not oppose: balances other than equity, and capex (an outflow).
_SIGNS = {**dict.fromkeys(BALANCES - {EQUITY}, 1), CAPEX: -1}
_NO_REVENUE = (ProbeStatus.NOT_ASSESSED, "non-positive revenue")
_NO_MATERIALS = (ProbeStatus.NOT_ASSESSED, "non-positive materials cost")
ACCOUNTING, BUSINESS, LIQUIDITY, SOLVENCY = "accounting", "business", "liquidity", "solvency"
CATEGORIES = (ACCOUNTING, BUSINESS, LIQUIDITY, SOLVENCY)
CHECKS: Mapping[str, Check] = {
    "R1": Check(
        metric_id="probe_receivable_days",
        label="Receivable days",
        formula=DAYS,
        numerator=(RECEIVABLES,),
        denominator=(REVENUE,),
        arrow=1,
        category=ACCOUNTING,
        meaning="customers owe a large share of revenue, so revenue may run ahead of cash",
        nonpositive=_NO_REVENUE,
    ),
    "R2": Check(
        metric_id="probe_inventory_materials_days",
        label="Inventory days, materials-cost basis",
        formula=DAYS,
        numerator=(INVENTORIES,),
        denominator=M,
        arrow=1,
        category=BUSINESS,
        meaning="stock is heavy against materials used, so it may be slow-moving",
        nonpositive=_NO_MATERIALS,
    ),
    "R3": Check(
        metric_id="probe_payable_materials_days",
        label="Payable days, materials-cost basis",
        formula=DAYS,
        numerator=(PAYABLES,),
        denominator=M,
        arrow=None,
        category=LIQUIDITY,
        meaning="suppliers are carrying a large share of materials cost, so the company may "
        "lean on supplier credit",
        nonpositive=_NO_MATERIALS,
    ),
    "R4": Check(
        metric_id="probe_cash_conversion_pct",
        label="Cash conversion",
        formula=RATIO_PCT,
        numerator=(CFO,),
        denominator=(PROFIT,),
        arrow=-1,
        category=ACCOUNTING,
        meaning="reported profit was not matched by operating cash",
        nonpositive=(ProbeStatus.FLAGGED, "non-positive profit"),
    ),
    "R5": Check(
        metric_id="probe_capex_intensity_pct",
        label="Capex intensity",
        formula=OUTFLOW_PCT,
        numerator=(CAPEX,),
        denominator=(REVENUE,),
        arrow=None,
        category=BUSINESS,
        meaning="capital spending is heavy against revenue",
        nonpositive=_NO_REVENUE,
    ),
    "R6": Check(
        metric_id="probe_borrowings_to_equity_ratio",
        label="Borrowings to equity",
        formula=RATIO,
        numerator=BORROWINGS,
        denominator=(EQUITY,),
        arrow=1,
        category=SOLVENCY,
        meaning="borrowings are high against equity, so balance-sheet risk is higher",
        nonpositive=(ProbeStatus.FLAGGED, "non-positive equity"),
    ),
}
S_CHECK = "R4"
GUARD, S, L, T = "guard", "S", "L", "T"
# The first fired rule's phrase in a flagged row's sentence (P7).
PHRASES = {
    GUARD: "because its denominator is not positive",
    S: "within the same flow window",
    L: "against the approved thesis limit",
    T: "on its trend against the same window a year earlier",
}
NO_SHEET = "NOT_ASSESSED: no filed balance sheet in the run's package"
NO_WINDOW = "no half-year or annual flow window in the statement"
SIGN_ANOMALY = "sign anomaly in filed line"
NO_TREND = "trend not evaluable: no matching prior"
NO_RULE = "no rule evaluable: no prior, no limit"
STALE_NOTE = (
    "; stale: this statement predates the run's period, so its limits are not assessed here"
)
SOURCES = (
    "related parties",
    "pledges",
    "contingent liabilities",
    "auditor opinion",
    "capitalised intangibles",
    "rating remarks",
    "disclosure lapses",
)
PERCENT_FORMULAS = frozenset({RATIO_PCT, OUTFLOW_PCT})


def key(check_id: str) -> str:
    """A check's claim key."""
    return f"probe.{check_id}"


def guard(check_id: str, statement: Statement) -> tuple[ProbeStatus, str] | None:
    """The guard outcome of a check on ``statement``, or ``None`` when its ratio may be
    computed."""
    check = CHECKS[check_id]
    ids = check.numerator + check.denominator
    if statement.window is None and not BALANCES.issuperset(ids):
        return ProbeStatus.NOT_ASSESSED, NO_WINDOW
    values = statement.values
    if missing := [i for i in ids if i not in values]:
        return ProbeStatus.NOT_ASSESSED, f"missing filed line {', '.join(missing)}"
    if any(values[i] * _SIGNS.get(i, 0) < 0 for i in ids):
        return ProbeStatus.NOT_ASSESSED, SIGN_ANOMALY
    if sum(values[i] for i in check.denominator) <= 0:
        return check.nonpositive
    return None


def matches(current: Statement, prior: Statement) -> bool:
    """Whether ``prior`` is ``current``'s trend comparator: balance date one year earlier
    (same month-day), and a flow window of the same length class and start month."""
    now, then = current.window, prior.window
    if now is None or then is None or now.start is None or then.start is None:
        return False
    assert now.end is not None and then.end is not None
    months = (now.end.year - now.start.year) * 12 + now.end.month - now.start.month
    prior_months = (then.end.year - then.start.year) * 12 + then.end.month - then.start.month
    balance = current.balance_date
    return (
        prior.balance_date == balance.replace(year=balance.year - 1)
        and months == prior_months
        and now.start.month == then.start.month
    )


def assess(
    check_id: str,
    statement: Statement,
    value: Decimal | None,
    prior: Decimal | None,
    prior_note: str | None,
    falsifiers: Sequence[FalsifierRow],
) -> ProbeRow:
    """A check's row from its guard, its stored value and prior, and the falsifier rows;
    ``prior_note`` says why no trend is evaluable."""
    check = CHECKS[check_id]
    guarded = guard(check_id, statement)
    if guarded is not None and guarded[0] is ProbeStatus.NOT_ASSESSED:
        return ProbeRow(
            check_id=check_id,
            status=guarded[0],
            reason=guarded[1],
            rules=(),
            falsifier_ids=(),
            shown=False,
            prior_shown=False,
        )
    evaluated: list[str] = []
    fired: list[str] = []
    weakened: tuple[str, ...] = ()
    if check_id == S_CHECK:
        evaluated.append(S)
        if statement.values[CFO] < statement.values[PROFIT]:
            fired.append(S)
    shown = guarded is None and value is not None
    if shown and value is not None:
        limits = [row for row in falsifiers if row.claim_key == key(check_id)]
        weakened = tuple(
            row.falsifier_id for row in limits if row.disposition is Disposition.WEAKENED
        )
        evaluated += [L] if limits else []
        fired += [L] if weakened else []
        if check.arrow is not None and prior is not None:
            evaluated.append(T)
            fired += [T] if (value - prior) * check.arrow > 0 else []
    note = (prior_note or NO_TREND) if check.arrow is not None and T not in evaluated else None
    status, reason = (
        guarded
        if guarded is not None
        else (ProbeStatus.FLAGGED, note)
        if fired
        else (ProbeStatus.PASSED, note)
        if evaluated
        else (ProbeStatus.COMPUTED, NO_RULE)
    )
    return ProbeRow(
        check_id=check_id,
        status=status,
        reason=reason,
        rules=tuple(fired),
        falsifier_ids=weakened,
        shown=shown,
        prior_shown=shown and prior is not None,
    )


def body(
    statement: Statement | None,
    rows: Sequence[ProbeRow],
    claim_keys: Mapping[str, tuple[str, ...]],
) -> str:
    """The ``risk_probe`` section: one paragraph when there is no statement or no evaluable
    row; else the dated rows, the explanation and the sources the probe does not assess.
    ``claim_keys`` maps each check to the raw-figure claim keys it shows."""
    head = f"## {RISK_PROBE}\n\n"
    if statement is None:
        return f"{head}{{{{e:computed}}}} {NO_SHEET}\n\n"
    if all(row.status is ProbeStatus.NOT_ASSESSED for row in rows):
        reasons = "; ".join(f"{row.check_id} {row.reason}" for row in rows)
        return (
            f"{head}{{{{e:computed}}}} NOT_ASSESSED: no check is evaluable on the statement of "
            f"{statement.balance_date}: {reasons}.\n\n"
        )
    window = statement.window
    span = "no flow window" if window is None else f"flow window {window.start} to {window.end}"
    dated = f"closing balances at {statement.balance_date}, {span}"
    stale = STALE_NOTE if statement.stale else ""
    intro = (
        f"{{{{e:computed}}}} Risk probe on the filed statement of {statement.balance_date}"
        f"{stale}. Each value is computed in code from the filed amounts beside it."
    )
    lines = [_line(row, dated, claim_keys.get(row.check_id, ())) for row in rows]
    sources = "\n".join(
        f"- NOT_ASSESSED: {source} not assessed by this probe" for source in SOURCES
    )
    paragraphs = (
        intro,
        "\n".join(lines),
        f"{{{{e:computed}}}} {_explanation(rows)}",
        f"{{{{e:computed}}}} Sources outside this probe:\n{sources}",
    )
    return head + "".join(f"{paragraph}\n\n" for paragraph in paragraphs)


def _line(row: ProbeRow, dated: str, raw: tuple[str, ...]) -> str:
    """A check's row: label, dates, value, prior, filed amounts and status."""
    check, name = CHECKS[row.check_id], key(row.check_id)
    style = "unit" if check.formula in PERCENT_FORMULAS else ""
    shown = [name] if row.shown else []
    text = f"- {{{{e:computed}}}} {row.check_id} {check.label} ({dated})"
    if row.shown:
        text += f": {_slot(name, style)}"
    if row.prior_shown:
        shown.append(f"{name}.prior")
        text += f"; a year earlier {_slot(f'{name}.prior', style)}"
    if raw:
        amounts = ", ".join(
            f"{'closing ' if item in BALANCES else ''}{item} {_slot(claim, CRORE_UNIT)}"
            for claim in raw
            for item in (claim.rsplit(".", 1)[1],)
        )
        text += f"; {{{{e:observed}}}} filed {amounts}"
    text += f"; {row.status.value}"
    if row.rules:
        text += f" by {', '.join(row.rules)}"
    if row.falsifier_ids:
        text += f" (thesis limit {', '.join(row.falsifier_ids)} {{{{e:opinion}}}})"
    if row.reason:
        text += f" ({row.reason})"
    return f"{text} {refs([*shown, *raw])}".rstrip()


def _explanation(rows: Sequence[ProbeRow]) -> str:
    """One sentence per flagged row, then the flagged categories and the coverage gaps."""
    flagged = [row for row in rows if row.status is ProbeStatus.FLAGGED]
    sentences = [
        f"{row.check_id} is flagged {PHRASES[row.rules[0] if row.shown else GUARD]}: "
        f"{CHECKS[row.check_id].meaning}."
        for row in flagged
    ]
    categories = {CHECKS[row.check_id].category for row in flagged}
    named = ", ".join(category for category in CATEGORIES if category in categories)
    gaps = [row.check_id for row in rows if row.status is ProbeStatus.NOT_ASSESSED]
    sentences.append(
        (f"Flagged categories: {named}" if named else "No check is flagged")
        + "; coverage gaps: "
        + (f"{', '.join(gaps)} not assessed, and " if gaps else "")
        + "the sources below."
    )
    return " ".join(sentences)


class Probe(BaseModel):
    """A run's bound probe: the selected statement and its matching prior, the cited probe
    claims, each check's value and prior value, why a trend is not evaluable, and the measuring
    claim keys a stale statement withholds from falsifier evaluation."""

    model_config = ConfigDict(frozen=True)

    statement: Statement | None
    prior: Statement | None
    claims: tuple[NumericClaim, ...]
    values: Mapping[str, Decimal]
    priors: Mapping[str, Decimal]
    notes: Mapping[str, str]
    stale_keys: frozenset[str]


FLOWS = (
    frozenset(i for check in CHECKS.values() for i in check.numerator + check.denominator)
    - BALANCES
)
WINDOWS = frozenset({PeriodKind.HALF_YEAR, PeriodKind.YEAR})
PRIOR = ".prior"
_CENT = Decimal("0.01")
# A statement read from one capture: the statement, its operands and the capture's provenance.
_Read = tuple[Statement, Mapping[str, _Operand], Provenance]


def bind_probe(
    repo: EvidenceRepository,
    update: EarningsUpdate,
    *,
    entity_id: int,
    versions: ConfigVersions,
    fiscal_year_end_month: int,
) -> Probe:
    """The run's probe: the run's own statement, else its QoQ comparator's (stale), else none;
    a stored trace and claim per guarded-in check, a ``FILED`` figure per operand shown, and a
    prior claim on a matching package statement for each trend check."""
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    binder = _Binder(repo, entity_id, start, end, versions)
    (own,) = (fact.sources[0] for fact in update.facts if fact.role is FactRole.PROFIT_BEFORE_TAX)
    comparators = {
        change.kind: (change.prior_source, change.period_end)
        for comparative in update.comparatives
        for change in (comparative.qoq, comparative.yoy)
        if change.prior_source is not None
    }
    historical = SelectionSource.HISTORICAL_PACKAGE
    reads = [_read(binder, own, end, SelectionSource.PACKAGE_AS_REPORTED, fiscal_year_end_month)]
    reads += [
        _read(binder, source, at, historical, fiscal_year_end_month)
        for kind in (ComparatorKind.QOQ, ComparatorKind.YOY)
        if kind in comparators
        for source, at in (comparators[kind],)
        if source is not None
    ]
    selected = reads[0] or (reads[1] if ComparatorKind.QOQ in comparators else None)
    if selected is None:
        return Probe(
            statement=None,
            prior=None,
            claims=(),
            values={},
            priors={},
            notes={},
            stale_keys=frozenset(),
        )
    statement, operands, source = selected
    statement = statement.model_copy(update={"stale": selected is not reads[0]})
    prior = next((r for r in reads if r is not None and matches(statement, r[0])), None)
    claims: list[NumericClaim] = []
    values: dict[str, Decimal] = {}
    priors: dict[str, Decimal] = {}
    notes: dict[str, str] = {}
    for check_id, check in CHECKS.items():
        outcome = guard(check_id, statement)
        if outcome is not None and outcome[0] is ProbeStatus.NOT_ASSESSED:
            continue
        name = key(check_id)
        shown = [i for i in check.numerator + check.denominator if i in operands]
        claims += [_figure(f"{name}.{i}", operands[i], source) for i in shown]
        if outcome is not None:
            continue
        values[check_id], claim = _ratio(binder, check_id, operands, name)
        claims.append(claim)
        if check.arrow is None or prior is None:
            continue
        if (failed := guard(check_id, prior[0])) is not None:
            notes[check_id] = f"trend not evaluable: prior {failed[1]}"
            continue
        priors[check_id], claim = _ratio(binder, check_id, prior[1], name + PRIOR)
        claims.append(claim)
    return Probe(
        statement=statement,
        prior=None if prior is None else prior[0],
        claims=tuple(claims),
        values=values,
        priors=priors,
        notes=notes,
        stale_keys=frozenset(map(key, CHECKS)) if statement.stale else frozenset(),
    )


def probe_section(probe: Probe, rows: Sequence[FalsifierRow]) -> tuple[str, str]:
    """The ``risk_probe`` section as (key, body), its rows assessed against the falsifier
    rows."""
    statement, keys = probe.statement, [claim.claim_key for claim in probe.claims]
    assessed = (
        []
        if statement is None
        else [
            assess(
                check_id,
                statement,
                probe.values.get(check_id),
                probe.priors.get(check_id),
                probe.notes.get(check_id),
                rows,
            )
            for check_id in CHECKS
        ]
    )
    raw = {
        check_id: tuple(
            k for k in keys if k.startswith(f"{key(check_id)}.") and not k.endswith(PRIOR)
        )
        for check_id in CHECKS
    }
    return RISK_PROBE, body(statement, assessed, raw)


def _read(
    binder: _Binder,
    source: Provenance,
    balance: date,
    selection: SelectionSource,
    fiscal_year_end_month: int,
) -> _Read | None:
    """``source``'s statement at ``balance``: its closing balances and, at the longest
    half-year or annual window ending then, its flows; ``None`` with no balance at all."""

    def filed(canonical_id: str, period: PeriodInterval) -> _Operand | None:
        found = binder.key(canonical_id, CRORE).model_copy(update={"period": period})
        return binder.filed(source, found, selection)

    found = {i: filed(i, PeriodInterval.at(balance)) for i in sorted(BALANCES)}
    if all(operand is None for operand in found.values()):
        return None
    windows = [
        item.key.period
        for item in binder.mapped(source)
        if item.key is not None
        and item.key.period.end == balance
        and item.key.period.kind(fiscal_year_end_month) in WINDOWS
    ]
    window = min(windows, key=lambda period: period.start or balance, default=None)  # longest
    if window is not None:
        found |= {i: filed(i, window) for i in sorted(FLOWS)}
    operands = {i: operand for i, operand in found.items() if operand is not None}
    statement = Statement(
        capture_sha256=source.file_sha256,
        balance_date=balance,
        window=window,
        stale=False,
        values={i: held.value for i, (_, held) in operands.items() if held.value is not None},
    )
    return statement, operands, source


def _figure(name: str, operand: _Operand, source: Provenance) -> NumericClaim:
    """A probe operand's filed amount in crore, cited to its interpretation and labelled
    filed."""
    held = operand[1]
    assert held.value is not None and held.interpretation_id is not None
    claim = _valued(name, RISK_PROBE, held.value / _CRORE_SCALE, CRORE, held.key, source)
    claim = claim.model_copy(update={"qualifiers": tuple(sorted({*claim.qualifiers, FILED}))})
    return cite(claim, interpretation_id=held.interpretation_id)


def _ratio(
    binder: _Binder, check_id: str, operands: Mapping[str, _Operand], name: str
) -> tuple[Decimal, NumericClaim]:
    """A check's stored trace over ``operands`` and its claim ``name`` at two places,
    half-even; summed operands are child traces."""
    check, probe_key = CHECKS[check_id], key(check_id)
    numerator = _total(binder, probe_key, [operands[i] for i in check.numerator])
    denominator = _total(binder, probe_key, [operands[i] for i in check.denominator])
    kind = METRICS[check.metric_id][2]
    unit: str | ValueKind = PERCENT if kind is ValueKind.PERCENTAGE else kind
    output = binder.key(probe_key, unit).model_copy(update={"period": denominator[1].key.period})
    result = binder.evaluate(probe_key, check.formula, output, (numerator, denominator))
    trace_id = binder.store(probe_key, result)
    assert result.value is not None
    value = result.value.quantize(_CENT, ROUND_HALF_EVEN)
    claim = _valued(
        name, RISK_PROBE, value, unit, output, precision=2, rounding=Rounding.ROUND_HALF_EVEN
    )
    return value, cite(claim, calculation_trace_id=trace_id)


def _total(binder: _Binder, probe_key: str, leaves: Sequence[_Operand]) -> _Operand:
    """One operand, or the running sum of several as stored child traces."""
    total, names = leaves[0], [leaves[0][1].key.canonical_id]
    for leaf in leaves[1:]:
        names.append(leaf[1].key.canonical_id)
        canonical_id = f"{probe_key}.{'+'.join(names)}"
        output = total[1].key.model_copy(update={"canonical_id": canonical_id})
        total = binder.child(canonical_id, SUM, output, (total, leaf))
    return total
