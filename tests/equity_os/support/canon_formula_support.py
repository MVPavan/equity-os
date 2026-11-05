"""Shared constructions for the canonical formula and period-aggregation tests.

Keys are consolidated Ind AS keys for entity 1. A monetary key carries the INR reporting
currency and a dimensionless one (percentage, ratio, days, count) carries none, as the
evaluator requires (ruling R2).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, ValueKind
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.qualification import ProvenCondition, QualificationContext
from equity_os.contracts.verification.comparison import SelectionSource, SourceState
from equity_os.normalisation.derivation.formula import (
    CalculationResult,
    OperandValue,
    evaluate_formula,
)
from equity_os.normalisation.derivation.interval import (
    Interval,
    RoundingPolicy,
    load_rounding_policy,
)
from equity_os.normalisation.dictionary.dictionary import (
    CanonicalDictionary,
    DictionaryRow,
    load_dictionary,
)

REPO = Path(__file__).resolve().parents[3]
INR = "INR"
DEMONSTRATED = EvidenceTier.EQUIVALENCE_DEMONSTRATED
UNPROVEN = EvidenceTier.EQUIVALENCE_UNPROVEN
NO_DIMENSIONS = DimensionSet()
MONETARY_KINDS = frozenset({ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT})
# Apar fiscal periods (fiscal year ends in March).
Q2_FY26 = PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30))
H1_FY26 = PeriodInterval.duration(date(2025, 4, 1), date(2025, 9, 30))
FY25 = PeriodInterval.duration(date(2024, 4, 1), date(2025, 3, 31))
NINE_M_FY25 = PeriodInterval.duration(date(2024, 4, 1), date(2024, 12, 31))
H1_FY25 = PeriodInterval.duration(date(2024, 4, 1), date(2024, 9, 30))
Q4_FY25 = PeriodInterval.duration(date(2025, 1, 1), date(2025, 3, 31))
H2_FY25 = PeriodInterval.duration(date(2024, 10, 1), date(2025, 3, 31))
FY25_QUARTERS = (
    PeriodInterval.duration(date(2024, 4, 1), date(2024, 6, 30)),
    PeriodInterval.duration(date(2024, 7, 1), date(2024, 9, 30)),
    PeriodInterval.duration(date(2024, 10, 1), date(2024, 12, 31)),
    Q4_FY25,
)
HOLDS = ProvenCondition(
    condition_id="discontinued_zero", holds=True, evidence_interpretation_ids=(7,)
)


def load_v1_dictionary() -> CanonicalDictionary:
    """Dictionary v1 as committed."""
    return load_dictionary(REPO / "config" / "normalisation/dictionary", "v1")


def load_v1_policy() -> RoundingPolicy:
    """Rounding policy v1 as committed."""
    return load_rounding_policy(REPO / "config" / "normalisation/rounding_policy" / "v1.yaml")


def key(
    canonical_id: str,
    period: PeriodInterval,
    kind: ValueKind = ValueKind.CURRENCY_AMOUNT,
    dimensions: DimensionSet = NO_DIMENSIONS,
) -> MeasurementKey:
    """A consolidated Ind AS key for entity 1: INR when monetary, no currency otherwise."""
    return MeasurementKey(
        entity_id=1,
        canonical_id=canonical_id,
        period=period,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency=INR if kind in MONETARY_KINDS else None,
        value_kind=kind,
        dimensions=dimensions,
    )


def leaf(
    measurement: MeasurementKey,
    value: str | None,
    *,
    state: SourceState = SourceState.VALUE,
    decimals: int | None = None,
    tier: EvidenceTier = DEMONSTRATED,
    precision_supported: bool = True,
    reasons: tuple[str, ...] = (),
    interpretation_id: int | None = 1,
    selection_source: SelectionSource | None = SelectionSource.PACKAGE_AS_REPORTED,
) -> OperandValue:
    """A selected interpretation value; ``decimals=None`` means exact."""
    number = None if value is None else Decimal(value)
    interval = None
    if number is not None and precision_supported:
        interval = (
            Interval.exact(number)
            if decimals is None
            else Interval.from_precision(number, decimals)
        )
    return OperandValue(
        key=measurement,
        state=state,
        exact=None if number is None else Fraction(number),
        value=number,
        interval=interval,
        interpretation_id=interpretation_id if number is not None else None,
        package_id=10,
        calculation_trace_id=None,
        child_trace=None,
        alignment_proof_id=None,
        mapping_entry_id="xbrl:test",
        qualification_ref=None,
        scoped_tier=tier,
        selection_source=selection_source,
        precision_supported=precision_supported,
        reasons=reasons,
    )


def quarter_context(
    *,
    basis: Basis = Basis.CONSOLIDATED,
    schema: str = "in-capmkt",
    proven: dict[str, ProvenCondition] | None = None,
) -> QualificationContext:
    """The qualification context of a quarter measurement."""
    return QualificationContext(
        schema_identity=schema,
        surface="NSE_XBRL_INSTANCE",
        basis=basis,
        period_kind=PeriodKind.QUARTER,
        proven={"discontinued_zero": HOLDS} if proven is None else proven,
    )


def evaluate_inr(
    dictionary: CanonicalDictionary,
    policy: RoundingPolicy,
    row: DictionaryRow | str,
    output: MeasurementKey,
    operands: dict[str, OperandValue],
    *,
    qualification: QualificationContext | None = None,
) -> CalculationResult:
    """Evaluate a row (or a dictionary row id) for an INR filing in a quarter context."""
    return evaluate_formula(
        dictionary.row(row) if isinstance(row, str) else row,
        output,
        operands,
        policy,
        dictionary=dictionary,
        reporting_currency=INR,
        qualification=quarter_context() if qualification is None else qualification,
    )
