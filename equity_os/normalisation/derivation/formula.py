"""Formula evaluation: temporal-role keys, dimensional aggregation, calculation states and traces.

All arithmetic is exact (``Fraction`` points, :class:`Interval` bounds). A computed operand
hands its parent its exact value and interval, never its stored rounding (data spec l.200);
rounding happens only through ``store_value`` and ``store_bounds``. Every evaluation ends in
one calculation state, first matching row of the spec table wins (data spec §5), and stores
a trace naming every operand, including the ones that had no value.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, model_validator

from equity_os.contracts.measurement.canonical import TemporalRole, ValueIdentity, ValueKind
from equity_os.contracts.measurement.evidence_tier import EvidenceTier, weakest
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)
from equity_os.contracts.measurement.qualification import (
    QualificationContext,
    ScopedTier,
    scoped_tier,
)
from equity_os.contracts.verification.comparison import (
    CalculationState,
    SelectionSource,
    SourceState,
)
from equity_os.normalisation.derivation.interval import (
    ExactValue,
    Interval,
    RoundingPolicy,
    UndefinedDivisionError,
    store_bounds,
    store_value,
)
from equity_os.normalisation.dictionary.dictionary import (
    CanonicalDictionary,
    DictionaryRow,
    DimensionalAggregation,
    FormulaNode,
    FormulaOp,
    FormulaOperand,
)

# Data spec §5: a value without declared precision is refused with this reason.
PRECISION_UNSUPPORTED = "PRECISION_UNSUPPORTED"

_ONE_DAY = timedelta(days=1)
_HALF = Interval.exact(Fraction(1, 2))
_OPENING = "opening"
_CLOSING = "closing"
_VALUE_NEEDS_NUMBER = "a VALUE operand carries its exact value"
_PRECISION_NEEDS_INTERVAL = "a VALUE operand with supported precision carries its interval"
_OUTSIDE_INTERVAL = "exact value {value} lies outside its interval [{lower}, {upper}]"
_NO_FORMULA = "row {canonical_id!r} has no formula"
_OUTPUT_MISMATCH = "output key {canonical_id!r}/{kind} does not match row {row_id!r}/{row_kind}"
_OPERAND_SET = "operands {given} do not match the formula's operands {declared}"
_KEY_MISMATCH = "operand {name!r} key {given} is not the expected key {expected}"
_NEEDS_DURATION = "temporal role {role} needs a duration output, got {period}"
_UNBOUND = "aggregation over axis {axis!r} has no bound member list"
_UNLISTED = "values given for unlisted members {members}"
_NOT_AGGREGATE_KEY = "output key has no {axis!r} = {member!r} dimension"
_DIGEST_MISMATCH = "result trace is for key digest {trace}, not {key}"
_CURRENCY_MISMATCH = "{name!r} is in currency {given}, not {expected}; D1a never converts"
_NO_CURRENCY = "a {kind} key needs a reporting currency and none is evidenced"
_SELECTION_NEEDS_SOURCE = (
    "a selected VALUE operand names its selection source; only a missing operand or a "
    "computed one whose constituents are in its child trace may leave it empty"
)
_COMPUTED_NEEDS_POINT = "a COMPUTED result carries its exact value and interval"
_POINT_WITHOUT_COMPUTED = "a {state} result carries no value"

# Kinds measured in a currency; every other kind is dimensionless and keyed with no currency.
_MONETARY_KINDS = frozenset({ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT})

_SOURCE_STATE_BY_CALCULATION: Mapping[CalculationState, SourceState] = {
    CalculationState.OPERAND_UNAVAILABLE: SourceState.UNAVAILABLE,
    CalculationState.OPERAND_INVALID: SourceState.INVALID,
    CalculationState.OPERAND_MISSING: SourceState.NO_VALUE,
    CalculationState.REVISION_INCOMPATIBLE: SourceState.INVALID,
    CalculationState.UNDEFINED: SourceState.INVALID,
    CalculationState.COMPUTED: SourceState.VALUE,
}


class TraceKind(StrEnum):
    """What produced a calculation trace (``calculation_traces.trace_kind``)."""

    FORMULA = "FORMULA"
    DIMENSIONAL_AGGREGATE = "DIMENSIONAL_AGGREGATE"
    AVERAGE = "AVERAGE"
    PERIOD_DERIVATION = "PERIOD_DERIVATION"


class OperandKeyMismatchError(ValueError):
    """An operand's key differs from its expected key in more than the period: a caller defect."""


class CurrencyMismatchError(OperandKeyMismatchError):
    """A key is in another currency than the calculation's; D1a refuses rather than converts."""


class TraceOperand(BaseModel):
    """One operand row of a trace (``calculation_trace_operands``)."""

    model_config = ConfigDict(frozen=True)

    name: str
    key_digest: str
    temporal_role: TemporalRole
    interpretation_id: int | None
    operand_trace_id: int | None
    alignment_proof_id: int | None
    mapping_entry_id: str | None
    qualification_ref: str | None
    scoped_tier: EvidenceTier
    # Empty only for a missing operand or a computed one whose constituents' sources are in
    # the child trace; the database CHECK enforces that once ``operand_trace_id`` is attached.
    selection_source: SelectionSource | None
    source_state: SourceState
    value: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    exact_value: ExactValue | None
    exact_interval: Interval | None


class CalculationTrace(BaseModel):
    """A stored calculation (``calculation_traces`` plus its operand rows)."""

    model_config = ConfigDict(frozen=True)

    trace_kind: TraceKind
    formula_id: str | None
    formula_version: str | None
    formula_tier: EvidenceTier | None
    formula_qualification_ref: str | None
    rounding_policy_id: str
    key_digest: str
    value_identity: ValueIdentity
    operands: tuple[TraceOperand, ...]
    state: CalculationState
    value: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    exact_value: ExactValue | None
    exact_interval: Interval | None
    effective_tier: EvidenceTier

    def content_sha256(self) -> str:
        """SHA-256 of every field, exact rationals as reduced ``p/q``; the trace's identity."""
        text = json.dumps(_canonical(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class OperandValue(BaseModel):
    """A formula operand: a selected value, an absence, or a computed child with its trace."""

    model_config = ConfigDict(frozen=True)

    key: MeasurementKey
    state: SourceState
    exact: ExactValue | None
    value: Decimal | None
    interval: Interval | None
    interpretation_id: int | None
    package_id: int | None
    calculation_trace_id: int | None
    child_trace: CalculationTrace | None
    alignment_proof_id: int | None
    mapping_entry_id: str | None
    qualification_ref: str | None
    scoped_tier: EvidenceTier
    selection_source: SelectionSource | None
    precision_supported: bool
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> OperandValue:
        """A value carries its exact number, its interval when precision is supported, and the
        selection source that chose it unless it is computed."""
        if self.state is SourceState.VALUE:
            if self.exact is None:
                raise ValueError(_VALUE_NEEDS_NUMBER)
            if self.precision_supported and self.interval is None:
                raise ValueError(_PRECISION_NEEDS_INTERVAL)
            computed = self.child_trace is not None or self.calculation_trace_id is not None
            if self.selection_source is None and not computed:
                raise ValueError(_SELECTION_NEEDS_SOURCE)
        if self.exact is not None and self.interval is not None:
            if not self.interval.contains(self.exact):
                raise ValueError(
                    _OUTSIDE_INTERVAL.format(
                        value=self.exact, lower=self.interval.lower, upper=self.interval.upper
                    )
                )
        return self


class CalculationResult(BaseModel):
    """The outcome of one evaluation; ``exact`` and ``interval`` are set only when computed."""

    model_config = ConfigDict(frozen=True)

    state: CalculationState
    source_state: SourceState
    exact: ExactValue | None
    value: Decimal | None
    interval: Interval | None
    trace: CalculationTrace
    effective_tier: EvidenceTier
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def _value_only_when_computed(self) -> CalculationResult:
        """``COMPUTED`` carries an exact value inside its interval; every other state none."""
        if self.state is CalculationState.COMPUTED:
            if self.exact is None or self.interval is None or self.value is None:
                raise ValueError(_COMPUTED_NEEDS_POINT)
            if not self.interval.contains(self.exact):
                raise ValueError(
                    _OUTSIDE_INTERVAL.format(
                        value=self.exact, lower=self.interval.lower, upper=self.interval.upper
                    )
                )
        elif self.exact is not None or self.interval is not None or self.value is not None:
            raise ValueError(_POINT_WITHOUT_COMPUTED.format(state=self.state))
        return self


def resolve_operand_keys(
    output: MeasurementKey,
    operand: FormulaOperand,
    *,
    dictionary: CanonicalDictionary,
    reporting_currency: str | None,
) -> tuple[MeasurementKey, ...]:
    """The role-aligned key(s) an operand reads for ``output``.

    ``DURATION`` is the output interval; ``CLOSING`` the instant at its end; ``OPENING`` the
    instant on the day before its start; ``AVERAGE`` the opening and closing pair. Keys
    share the output's entity, basis, framework and dimensions, take the operand row's value
    kind, and carry ``reporting_currency`` (the currency evidenced for the filing) when that
    kind is monetary, else no currency. An aggregated operand's members replace the
    aggregation axis (see :func:`aggregate_members`).
    """
    kind = dictionary.row(operand.canonical_id).value_kind
    return tuple(
        _operand_key(output, operand.canonical_id, period, kind, reporting_currency)
        for period in _role_periods(output.period, operand.temporal_role)
    )


def check_output_key(output: MeasurementKey, canonical_id: str, kind: ValueKind) -> None:
    """Refuse an output key that is not for ``canonical_id`` with value kind ``kind``."""
    if output.canonical_id != canonical_id or output.value_kind is not kind:
        raise OperandKeyMismatchError(
            _OUTPUT_MISMATCH.format(
                canonical_id=output.canonical_id,
                kind=output.value_kind,
                row_id=canonical_id,
                row_kind=kind,
            )
        )


def check_currency(name: str, key: MeasurementKey, currency: str | None) -> None:
    """Refuse a key in another currency than ``currency`` (no conversion in D1a)."""
    if key.currency != currency:
        raise CurrencyMismatchError(
            _CURRENCY_MISMATCH.format(name=name, given=key.currency, expected=currency)
        )


def calculation_state(
    operands: Sequence[OperandValue],
    *,
    revision_incompatible: bool,
    denominator_contains_zero: bool,
) -> CalculationState:
    """The spec's calculation-state table, first matching row wins (data spec §5)."""
    if any(operand.state is SourceState.UNAVAILABLE for operand in operands):
        return CalculationState.OPERAND_UNAVAILABLE
    if any(_invalid(operand) for operand in operands):
        return CalculationState.OPERAND_INVALID
    if any(operand.state is not SourceState.VALUE for operand in operands):
        return CalculationState.OPERAND_MISSING
    if revision_incompatible:
        return CalculationState.REVISION_INCOMPATIBLE
    if denominator_contains_zero:
        return CalculationState.UNDEFINED
    return CalculationState.COMPUTED


def state_to_source_state(state: CalculationState) -> SourceState:
    """The source state a derived side takes from its calculation state."""
    return _SOURCE_STATE_BY_CALCULATION[state]


def evaluate_formula(
    row: DictionaryRow,
    output: MeasurementKey,
    operands: Mapping[str, OperandValue],
    policy: RoundingPolicy,
    *,
    dictionary: CanonicalDictionary,
    reporting_currency: str | None,
    qualification: QualificationContext,
    value_identity: ValueIdentity = ValueIdentity.DERIVED,
    revision_incompatible: bool = False,
) -> CalculationResult:
    """Evaluate a row's formula for ``output`` from one value per declared operand.

    Each operand must be at its dictionary row's value kind; a monetary operand must be in
    ``reporting_currency`` (the currency evidenced for the package or filing) and a
    dimensionless one, like the output of a dimensionless formula, carries no currency.
    An operand at a non-role-aligned period is never used: it is traced as absent, so the
    result is ``OPERAND_MISSING``. The effective tier is the weakest of the formula's scoped
    tier and every operand's scoped tier; no formula is exempt.
    """
    formula = row.formula
    if formula is None:
        raise ValueError(_NO_FORMULA.format(canonical_id=row.canonical_id))
    check_output_key(output, row.canonical_id, formula.output_kind)
    check_currency(output.canonical_id, output, _currency(formula.output_kind, reporting_currency))
    declared = {operand.name for operand in formula.operands}
    if set(operands) != declared:
        raise ValueError(_OPERAND_SET.format(given=sorted(operands), declared=sorted(declared)))
    entries = [
        (
            operand.name,
            operand.temporal_role,
            _aligned(
                operand.name,
                operands[operand.name],
                _operand_key(
                    output,
                    operand.canonical_id,
                    _evaluated_period(output, operand),
                    dictionary.row(operand.canonical_id).value_kind,
                    reporting_currency,
                ),
            ),
        )
        for operand in formula.operands
    ]
    values = [value for _, _, value in entries]
    state = calculation_state(
        values, revision_incompatible=revision_incompatible, denominator_contains_zero=False
    )
    point: tuple[Fraction, Interval] | None = None
    if state is CalculationState.COMPUTED:
        try:
            point = _evaluate(formula.expression, {name: _point(v) for name, _, v in entries})
        except UndefinedDivisionError:
            state = calculation_state(
                values, revision_incompatible=False, denominator_contains_zero=True
            )
    if point is not None and formula.day_count is not None:
        days = Fraction(_days(output.period))
        point = (point[0] * days, point[1].mul(Interval.exact(days)))
    return conclude(
        TraceKind.FORMULA,
        output,
        entries,
        state,
        point,
        policy,
        value_identity=value_identity,
        formula_id=formula.formula_id,
        formula_version=formula.version,
        formula_scoped=scoped_tier(formula.tier, formula.qualification, qualification),
    )


def aggregate_members(
    aggregation: DimensionalAggregation,
    values: Mapping[str, OperandValue | None],
    *,
    output: MeasurementKey,
    policy: RoundingPolicy,
) -> OperandValue:
    """Sum every listed member of one axis into ``output`` (the aggregate member's key).

    Every listed member needs a value, else ``OPERAND_MISSING``; a member given as ``None``
    is traced with its key, ``NO_VALUE`` and null ids. The aggregate's tier is the weakest
    member tier, and its ``child_trace`` (``DIMENSIONAL_AGGREGATE``) lists every member.
    """
    members = aggregation.input_members
    if not members:
        raise ValueError(_UNBOUND.format(axis=aggregation.axis))
    unlisted = sorted(set(values) - set(members))
    if unlisted:
        raise ValueError(_UNLISTED.format(members=unlisted))
    axes = dict(output.dimensions.pairs)
    if axes.get(aggregation.axis) != aggregation.output_member:
        raise OperandKeyMismatchError(
            _NOT_AGGREGATE_KEY.format(axis=aggregation.axis, member=aggregation.output_member)
        )
    role = _own_role(output.period)
    entries = []
    for member in members:
        expected = output.model_copy(
            update={"dimensions": DimensionSet.of({**axes, aggregation.axis: member})}
        )
        given = values.get(member)
        value = _absent(expected) if given is None else _aligned(member, given, expected)
        entries.append((member, role, value))
    constituents = [value for _, _, value in entries]
    state = calculation_state(
        constituents, revision_incompatible=False, denominator_contains_zero=False
    )
    point = None
    if state is CalculationState.COMPUTED:
        points = [_point(value) for value in constituents]
        point = (
            sum((exact for exact, _ in points), Fraction(0)),
            _sum_intervals([interval for _, interval in points]),
        )
    result = conclude(TraceKind.DIMENSIONAL_AGGREGATE, output, entries, state, point, policy)
    return _child_operand(result, output, constituents)


def average_operand(
    opening: OperandValue,
    closing: OperandValue,
    *,
    output: MeasurementKey,
    policy: RoundingPolicy,
) -> OperandValue:
    """The mean of the opening and closing instants of ``output``'s duration.

    ``output`` is the averaged key: the instant row's canonical id over the duration. Its
    ``child_trace`` (``AVERAGE``) lists both instants; an instant at any other date is absent.
    """
    entries = [
        (
            _OPENING,
            TemporalRole.OPENING,
            _aligned(_OPENING, opening, _keyed(output, TemporalRole.OPENING)),
        ),
        (
            _CLOSING,
            TemporalRole.CLOSING,
            _aligned(_CLOSING, closing, _keyed(output, TemporalRole.CLOSING)),
        ),
    ]
    constituents = [value for _, _, value in entries]
    state = calculation_state(
        constituents, revision_incompatible=False, denominator_contains_zero=False
    )
    point = None
    if state is CalculationState.COMPUTED:
        (open_exact, open_interval), (close_exact, close_interval) = map(_point, constituents)
        point = ((open_exact + close_exact) / 2, open_interval.add(close_interval).mul(_HALF))
    result = conclude(TraceKind.AVERAGE, output, entries, state, point, policy)
    return _child_operand(result, output, constituents)


def operand_from_result(
    result: CalculationResult,
    *,
    key: MeasurementKey,
    selection_source: SelectionSource | None,
    package_id: int | None = None,
) -> OperandValue:
    """Hand a computed result to a parent formula: exact value and interval, trace attached."""
    if key.digest() != result.trace.key_digest:
        raise OperandKeyMismatchError(
            _DIGEST_MISMATCH.format(trace=result.trace.key_digest, key=key.digest())
        )
    return OperandValue(
        key=key,
        state=result.source_state,
        exact=result.exact,
        value=result.value,
        interval=result.interval,
        interpretation_id=None,
        package_id=package_id,
        calculation_trace_id=None,
        child_trace=result.trace,
        alignment_proof_id=None,
        mapping_entry_id=None,
        qualification_ref=None,
        scoped_tier=result.effective_tier,
        selection_source=selection_source,
        precision_supported=result.state is CalculationState.COMPUTED,
        reasons=result.reasons,
    )


def conclude(
    trace_kind: TraceKind,
    output: MeasurementKey,
    entries: Sequence[tuple[str, TemporalRole, OperandValue]],
    state: CalculationState,
    point: tuple[Fraction, Interval] | None,
    policy: RoundingPolicy,
    *,
    value_identity: ValueIdentity = ValueIdentity.DERIVED,
    formula_id: str | None = None,
    formula_version: str | None = None,
    formula_scoped: ScopedTier | None = None,
) -> CalculationResult:
    """Round for storage, take the weakest tier and build the trace for one evaluation."""
    exact, interval = (None, None) if point is None else point
    value = None if exact is None else store_value(exact, output.value_kind, policy)
    lower, upper = (
        (None, None) if interval is None else store_bounds(interval, output.value_kind, policy)
    )
    tiers = [value.scoped_tier for _, _, value in entries]
    if formula_scoped is not None:
        tiers.append(formula_scoped.tier)
    effective = weakest(*tiers)
    reasons = (
        _invalid_reasons([value for _, _, value in entries])
        if state is CalculationState.OPERAND_INVALID
        else (state.value,)
        if state in (CalculationState.REVISION_INCOMPATIBLE, CalculationState.UNDEFINED)
        else ()
    )
    trace = CalculationTrace(
        trace_kind=trace_kind,
        formula_id=formula_id,
        formula_version=formula_version,
        formula_tier=None if formula_scoped is None else formula_scoped.tier,
        formula_qualification_ref=None
        if formula_scoped is None
        else formula_scoped.qualification_ref,
        rounding_policy_id=policy.policy_id,
        key_digest=output.digest(),
        value_identity=value_identity,
        operands=tuple(_trace_operand(name, role, op, policy) for name, role, op in entries),
        state=state,
        value=value,
        lower=lower,
        upper=upper,
        exact_value=exact,
        exact_interval=interval,
        effective_tier=effective,
    )
    return CalculationResult(
        state=state,
        source_state=state_to_source_state(state),
        exact=exact,
        value=value,
        interval=interval,
        trace=trace,
        effective_tier=effective,
        reasons=reasons,
    )


def _invalid(operand: OperandValue) -> bool:
    """Row 1a: refused, or a value without supported precision."""
    return operand.state is SourceState.INVALID or (
        operand.state is SourceState.VALUE and not operand.precision_supported
    )


def _invalid_reasons(operands: Sequence[OperandValue]) -> tuple[str, ...]:
    """Reasons of every row-1a operand, in operand order, each once."""
    reasons: list[str] = []
    for operand in operands:
        if not _invalid(operand):
            continue
        own = operand.reasons if operand.state is SourceState.INVALID else (PRECISION_UNSUPPORTED,)
        reasons.extend(reason for reason in own if reason not in reasons)
    return tuple(reasons)


def _role_periods(period: PeriodInterval, role: TemporalRole) -> tuple[PeriodInterval, ...]:
    """The period(s) an operand at ``role`` reads for an output over ``period``."""
    if role is TemporalRole.DURATION:
        return (period,)
    if role is TemporalRole.CLOSING:
        return (PeriodInterval.at(period.instant or _end(period)),)
    if period.start is None:
        raise ValueError(_NEEDS_DURATION.format(role=role, period=period))
    opening = PeriodInterval.at(period.start - _ONE_DAY)
    if role is TemporalRole.OPENING:
        return (opening,)
    return (opening, PeriodInterval.at(_end(period)))


def _evaluated_period(output: MeasurementKey, operand: FormulaOperand) -> PeriodInterval:
    """The period of the value a formula consumes; an average is keyed over the output interval."""
    if operand.temporal_role is TemporalRole.AVERAGE:
        if output.period.start is None:
            raise ValueError(
                _NEEDS_DURATION.format(role=operand.temporal_role, period=output.period)
            )
        return output.period
    (period,) = _role_periods(output.period, operand.temporal_role)
    return period


def _keyed(output: MeasurementKey, role: TemporalRole) -> MeasurementKey:
    """``output`` moved to the single period of ``role``."""
    (period,) = _role_periods(output.period, role)
    return output.model_copy(update={"period": period})


def _operand_key(
    output: MeasurementKey,
    canonical_id: str,
    period: PeriodInterval,
    kind: ValueKind,
    reporting_currency: str | None,
) -> MeasurementKey:
    """An operand key sharing the output's entity, basis, framework and dimensions."""
    return output.model_copy(
        update={
            "canonical_id": canonical_id,
            "period": period,
            "value_kind": kind,
            "currency": _currency(kind, reporting_currency),
        }
    )


def _currency(kind: ValueKind, reporting_currency: str | None) -> str | None:
    """The reporting currency for a monetary kind (refused, never invented, when there is
    none: plan D8 R6); no currency for a dimensionless one."""
    if kind not in _MONETARY_KINDS:
        return None
    if reporting_currency is None:
        raise CurrencyMismatchError(_NO_CURRENCY.format(kind=kind))
    return reporting_currency


def _aligned(name: str, given: OperandValue, expected: MeasurementKey) -> OperandValue:
    """``given`` if it is at the expected key; absent if only its period differs; else refuse.

    A different currency is a :class:`CurrencyMismatchError`; any other difference beyond
    the period (value kind included) is an :class:`OperandKeyMismatchError`.
    """
    check_currency(name, given.key, expected.currency)
    if given.key == expected:
        return given
    if given.key.model_copy(update={"period": expected.period}) == expected:
        return _absent(expected)
    raise OperandKeyMismatchError(
        _KEY_MISMATCH.format(name=name, given=given.key, expected=expected)
    )


def _absent(key: MeasurementKey) -> OperandValue:
    """No role-aligned value at ``key``: ``NO_VALUE``, null ids and no selection source."""
    return OperandValue(
        key=key,
        state=SourceState.NO_VALUE,
        exact=None,
        value=None,
        interval=None,
        interpretation_id=None,
        package_id=None,
        calculation_trace_id=None,
        child_trace=None,
        alignment_proof_id=None,
        mapping_entry_id=None,
        qualification_ref=None,
        scoped_tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
        selection_source=None,
        precision_supported=False,
        reasons=(),
    )


def _child_operand(
    result: CalculationResult, output: MeasurementKey, constituents: Sequence[OperandValue]
) -> OperandValue:
    """Wrap an aggregate or average as an operand.

    A computed parent records the source and package its constituents share; mixed sources,
    or no value at all, record none (never an invented one), each constituent's own source
    staying in the child trace.
    """
    computed = result.state is CalculationState.COMPUTED
    sources = {value.selection_source for value in constituents}
    packages = {value.package_id for value in constituents}
    return operand_from_result(
        result,
        key=output,
        selection_source=sources.pop() if computed and len(sources) == 1 else None,
        package_id=packages.pop() if computed and len(packages) == 1 else None,
    )


def _own_role(period: PeriodInterval) -> TemporalRole:
    """The role of a constituent at the trace's own period: a duration, or its closing instant."""
    return TemporalRole.CLOSING if period.instant is not None else TemporalRole.DURATION


def _point(operand: OperandValue) -> tuple[Fraction, Interval]:
    """The exact value and interval of an operand that passed rows 1–2."""
    assert operand.exact is not None and operand.interval is not None
    return operand.exact, operand.interval


def _evaluate(
    node: FormulaNode, values: Mapping[str, tuple[Fraction, Interval]]
) -> tuple[Fraction, Interval]:
    """Evaluate a formula tree exactly, point and interval together."""
    if node.op is FormulaOp.OPERAND:
        assert node.operand is not None
        return values[node.operand]
    if node.op is FormulaOp.LITERAL:
        assert node.value is not None
        literal = Fraction(node.value)
        return literal, Interval.exact(literal)
    args = [_evaluate(arg, values) for arg in node.args]
    if node.op is FormulaOp.ADD:
        return sum((a for a, _ in args), Fraction(0)), _sum_intervals([i for _, i in args])
    (left, left_interval), (right, right_interval) = args
    if node.op is FormulaOp.SUB:
        return left - right, left_interval.sub(right_interval)
    if node.op is FormulaOp.MUL:
        return left * right, left_interval.mul(right_interval)
    quotient = left_interval.div(right_interval)  # raises before the point could divide by zero
    return left / right, quotient


def _sum_intervals(intervals: Sequence[Interval]) -> Interval:
    """Sum of one or more intervals."""
    total = intervals[0]
    for interval in intervals[1:]:
        total = total.add(interval)
    return total


def _end(period: PeriodInterval) -> date:
    """The last day of a duration."""
    assert period.end is not None
    return period.end


def _days(period: PeriodInterval) -> int:
    """Actual days in an inclusive duration."""
    if period.start is None or period.end is None:
        raise ValueError(_NEEDS_DURATION.format(role="day count", period=period))
    return (period.end - period.start).days + 1


def _trace_operand(
    name: str, role: TemporalRole, operand: OperandValue, policy: RoundingPolicy
) -> TraceOperand:
    """One trace operand row; bounds stored outward at the operand kind's scale."""
    lower, upper = (
        (None, None)
        if operand.interval is None
        else store_bounds(operand.interval, operand.key.value_kind, policy)
    )
    return TraceOperand(
        name=name,
        key_digest=operand.key.digest(),
        temporal_role=role,
        interpretation_id=operand.interpretation_id,
        operand_trace_id=operand.calculation_trace_id,
        alignment_proof_id=operand.alignment_proof_id,
        mapping_entry_id=operand.mapping_entry_id,
        qualification_ref=operand.qualification_ref,
        scoped_tier=operand.scoped_tier,
        selection_source=operand.selection_source,
        source_state=operand.state,
        value=operand.value,
        lower=lower,
        upper=upper,
        exact_value=operand.exact,
        exact_interval=operand.interval,
    )


def _canonical(node: object) -> object:
    """A JSON-ready form: rationals as reduced ``p/q``, decimals as text, enums as values."""
    if isinstance(node, BaseModel):
        return {name: _canonical(getattr(node, name)) for name in type(node).model_fields}
    if isinstance(node, Fraction):
        return f"{node.numerator}/{node.denominator}"
    if isinstance(node, Decimal):
        return str(node)
    if isinstance(node, Enum):
        return node.value
    if isinstance(node, tuple | list):
        return [_canonical(item) for item in node]
    return node
