"""Pair, extraction, derived-extraction and first-party corroboration tables (data spec §5).

Each table is a first-match-wins sequence in the spec's row order. Two sides agree iff their
uncertainty intervals intersect; difference and gap are reported from the stored values and
intervals. Nothing here estimates a number: a derived side is re-evaluated only through
``evaluate_formula``, with evidenced tagging adjustments applied to its operands.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.canon.dictionary import CanonicalDictionary, DictionaryRow
from fundamentals.canon.formula import OperandValue, evaluate_formula
from fundamentals.canon.interval import Interval, RoundingPolicy
from fundamentals.compare.definitions import DefinitionRecord, DefinitionScope, DefinitionSet
from fundamentals.compare.policy import ComparisonPolicy
from fundamentals.compare.triage import triage
from fundamentals.contracts.canonical import ApplicabilityStatus, Representation, ValueKind
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    ReasonCode,
    SourceRef,
    SourceRole,
    SourceState,
    Triage,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.qualification import ProvenCondition, QualificationContext

_VALUE_NEEDS_NUMBER = "a VALUE side carries its value"
_NUMBER_WITHOUT_VALUE = "a {state} side carries no value or interval"
_NO_PAIR = "a pair needs two VALUE or INVALID sides, got {first} and {other}"
_OTHER_ENTITY = "a pair compares one entity, got {first} and {other}"
_ZERO_DIRECTION = "direction is +1 or -1"
_UNKNOWN_OPERAND = "adjustment names operand {name!r}, which the formula does not have"
_OTHER_PACKAGE = "extraction compares XBRL and PDF of one package, got packages {xbrl} and {pdf}"

# Row-1 reasons a side may carry while still holding a value (data spec §5 pair row 1).
_VALUE_SIDE_REFUSALS = (
    ReasonCode.PERIOD_AMBIGUOUS,
    ReasonCode.PRECISION_UNSUPPORTED,
    ReasonCode.VENDOR_INTERNAL_CONFLICT,
)
_PAIRABLE = (SourceState.VALUE, SourceState.INVALID)
_OUTSIDE = (PairOutcome.MISMATCH, PairOutcome.ANOMALY)
_PAIR_TO_EXTRACTION: Mapping[PairOutcome, ExtractionStatus] = {
    PairOutcome.NOT_COMPARABLE: ExtractionStatus.NOT_COMPARABLE,
    PairOutcome.AGREE: ExtractionStatus.AGREE,
    PairOutcome.AGREE_UNQUALIFIED: ExtractionStatus.AGREE_UNQUALIFIED,
    PairOutcome.DEFINITION_DIFFERENCE: ExtractionStatus.TAGGING_DIFFERENCE,
    PairOutcome.MISMATCH: ExtractionStatus.DISAGREE,
    PairOutcome.ANOMALY: ExtractionStatus.DISAGREE,
}

# Each key part in the plan's check order, with the reason its mismatch carries.
_KEY_PARTS: tuple[tuple[Callable[[MeasurementKey], object], ReasonCode], ...] = (
    (lambda key: key.period, ReasonCode.PERIOD_MISMATCH),
    (lambda key: key.basis, ReasonCode.BASIS_MISMATCH),
    (lambda key: key.framework, ReasonCode.FRAMEWORK_MISMATCH),
    (lambda key: key.currency, ReasonCode.CURRENCY_MISMATCH),
    (lambda key: key.value_kind, ReasonCode.KIND_MISMATCH),
    (lambda key: key.dimensions, ReasonCode.DIMENSION_UNRESOLVED),
)


class EvidencedRelationship(BaseModel):
    """An evidenced statement that two different canonical ids measure the same thing."""

    model_config = ConfigDict(frozen=True)

    left_canonical_id: str = Field(min_length=1)
    right_canonical_id: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)

    def names(self, left: str, right: str) -> bool:
        """Whether this relationship covers the two ids, in either order."""
        return {left, right} == {self.left_canonical_id, self.right_canonical_id}


class ComparisonSide(BaseModel):
    """One side of a pair: a reported or derived value with its state, tier and scope refs.

    ``tier`` is already scoped (or proven by alignment). ``interval`` is ``None`` for a value
    without supported precision.
    """

    model_config = ConfigDict(frozen=True)

    key: MeasurementKey
    state: SourceState
    value: Decimal | None
    interval: Interval | None
    tier: EvidenceTier
    aligned_by_proof: bool
    mapping_entry_ids: tuple[str, ...]
    package_id: int | None
    calculation_state: CalculationState | None
    reasons: tuple[ReasonCode, ...]
    condition_evidence: tuple[ProvenCondition, ...] = ()  # scope conditions that held

    @model_validator(mode="after")
    def _value_only_when_valued(self) -> ComparisonSide:
        """A ``VALUE`` side carries its value; every other state carries none."""
        if self.state is SourceState.VALUE:
            if self.value is None:
                raise ValueError(_VALUE_NEEDS_NUMBER)
        elif self.value is not None or self.interval is not None:
            raise ValueError(_NUMBER_WITHOUT_VALUE.format(state=self.state))
        return self


class PairResult(BaseModel):
    """A pair outcome; ``difference`` is first minus other, ``interval_gap`` never negative."""

    model_config = ConfigDict(frozen=True)

    outcome: PairOutcome
    reason: ReasonCode | None
    triage: Triage | None
    difference: Decimal | None
    interval_gap: Decimal | None
    definition_record_id: str | None


class SourceQualifiedSide(BaseModel):
    """One declared source/surface and its already resolved financial state.

    Source authority and mapping qualification must be evidenced upstream. Constructing
    this model does not establish either, nor does a synthetic table test qualify a vendor.
    """

    model_config = ConfigDict(frozen=True)
    ref: SourceRef
    side: ComparisonSide
    occurrence_ids: tuple[int, ...] = ()
    interpretation_ids: tuple[int, ...] = ()
    attempt_ids: tuple[int, ...] = ()


class SourceQualifiedPair(BaseModel):
    """One independently reportable pair, with every source and evidence reference."""

    model_config = ConfigDict(frozen=True)
    pair_kind: PairKind
    left: SourceRef
    right: SourceRef
    result: PairResult
    evidence_occurrence_ids: tuple[int, ...] = ()
    evidence_interpretation_ids: tuple[int, ...] = ()
    attempt_ids: tuple[int, ...] = ()

    @model_validator(mode="after")
    def _roles_match_kind(self) -> SourceQualifiedPair:
        if self.pair_kind is PairKind.CORROBORATION and (
            self.left.source_role is not SourceRole.FIRST_PARTY
            or self.right.source_role is not SourceRole.INDEPENDENT_VENDOR
        ):
            raise ValueError("corroboration compares first-party and independent-vendor sources")
        if self.pair_kind is not PairKind.DIAGNOSTIC and any(
            ref.source_role is SourceRole.DIAGNOSTIC for ref in (self.left, self.right)
        ):
            raise ValueError("a diagnostic source belongs only to diagnostic pairs")
        return self


class CorroborationResult(BaseModel):
    """Ordered status plus all independent pairs and non-diagnostic source states."""

    model_config = ConfigDict(frozen=True)
    status: CorroborationStatus
    reason: ReasonCode | None
    pairs: tuple[SourceQualifiedPair, ...] = ()
    sources: tuple[SourceQualifiedSide, ...] = ()
    unavailable_sources: tuple[SourceRef, ...] = ()


class TaggingAdjustment(BaseModel):
    """Shift one representation's operand by ``direction × amount`` under a cited record.

    ``amount`` is a positive magnitude, as on the record, so ``direction`` alone is the sign.
    """

    model_config = ConfigDict(frozen=True)

    operand_name: str = Field(min_length=1)
    representation: Representation
    direction: int = Field(ge=-1, le=1)
    amount: Decimal = Field(gt=0)
    unit: ValueKind
    definition_record_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _non_zero_direction(self) -> TaggingAdjustment:
        """Direction is +1 or −1."""
        if self.direction == 0:
            raise ValueError(_ZERO_DIRECTION)
        return self


class AdjustmentRejection(BaseModel):
    """An offered adjustment the evidence does not support; recorded, never applied."""

    model_config = ConfigDict(frozen=True)

    adjustment: TaggingAdjustment
    reason: ReasonCode


class ExtractionResult(BaseModel):
    """An extraction status with its pair and any adjustments applied or rejected."""

    model_config = ConfigDict(frozen=True)

    status: ExtractionStatus
    reason: ReasonCode | None
    pair: PairResult | None
    adjustments: tuple[TaggingAdjustment, ...] = ()
    rejected_adjustments: tuple[AdjustmentRejection, ...] = ()


class OperandExtraction(BaseModel):
    """One formula operand's own extraction outcome, with both representations' values."""

    model_config = ConfigDict(frozen=True)

    operand_name: str
    xbrl: OperandValue
    pdf: OperandValue
    result: ExtractionResult

    def side(self, representation: Representation) -> OperandValue:
        """The operand value of one representation."""
        return self.xbrl if representation is Representation.XBRL else self.pdf


def pair_outcome(
    first: ComparisonSide,
    other: ComparisonSide,
    *,
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
    relationship: EvidencedRelationship | None = None,
) -> PairResult:
    """The pair table for a first-party side against one other side; first row wins."""
    if first.state not in _PAIRABLE or other.state not in _PAIRABLE:
        raise ValueError(_NO_PAIR.format(first=first.state, other=other.state))
    if first.key.entity_id != other.key.entity_id:
        raise ValueError(_OTHER_ENTITY.format(first=first.key.entity_id, other=other.key.entity_id))
    refusal = _row_one_reason(first, other, relationship)
    if refusal is not None:
        return _result(PairOutcome.NOT_COMPARABLE, reason=refusal)
    assert first.value is not None and other.value is not None
    assert first.interval is not None and other.interval is not None
    difference = first.value - other.value
    gap = _decimal(first.interval.gap(other.interval))
    qualified = _qualified(first, other)
    if first.interval.intersects(other.interval):
        outcome = PairOutcome.AGREE if qualified else PairOutcome.AGREE_UNQUALIFIED
        return _result(outcome, difference=difference, gap=gap)
    reconciling = _reconciling_record(first, other, definitions)
    if reconciling is not None:
        return _result(
            PairOutcome.DEFINITION_DIFFERENCE,
            difference=difference,
            gap=gap,
            record_id=reconciling.record_id,
        )
    outcome = PairOutcome.MISMATCH if qualified else PairOutcome.ANOMALY
    return _result(
        outcome,
        difference=difference,
        gap=gap,
        triage_class=triage(first.value, other.value, policy),
    )


def extraction_status(
    *,
    family_has_pair: bool,
    xbrl: ComparisonSide,
    pdf: ComparisonSide,
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
) -> ExtractionResult:
    """The extraction table (XBRL against PDF of one package); first row wins."""
    if not family_has_pair:
        return ExtractionResult(status=ExtractionStatus.NOT_APPLICABLE, reason=None, pair=None)
    _require_one_package(xbrl, pdf)
    sides = (xbrl, pdf)
    if any(side.state is SourceState.UNAVAILABLE for side in sides):
        return ExtractionResult(status=ExtractionStatus.UNAVAILABLE, reason=None, pair=None)
    invalid = next((side for side in sides if side.state is SourceState.INVALID), None)
    if invalid is not None:
        return ExtractionResult(
            status=ExtractionStatus.NOT_COMPARABLE, reason=_invalid_reason(invalid), pair=None
        )
    has_xbrl, has_pdf = xbrl.state is SourceState.VALUE, pdf.state is SourceState.VALUE
    if not has_xbrl and not has_pdf:
        return ExtractionResult(status=ExtractionStatus.NONE, reason=None, pair=None)
    if has_xbrl != has_pdf:
        one_side = ExtractionStatus.ONE_SIDE_XBRL if has_xbrl else ExtractionStatus.ONE_SIDE_PDF
        return ExtractionResult(status=one_side, reason=None, pair=None)
    pair = pair_outcome(xbrl, pdf, definitions=definitions, policy=policy)
    return ExtractionResult(status=_PAIR_TO_EXTRACTION[pair.outcome], reason=pair.reason, pair=pair)


def validate_adjustment(
    adjustment: TaggingAdjustment,
    *,
    operand: OperandExtraction,
    definitions: DefinitionSet,
) -> TaggingAdjustment | AdjustmentRejection:
    """Accept an adjustment only when its operand's own evidence supports it exactly.

    Scope failures (wrong operand, record not cited by the operand's own tagging difference,
    record for another row, operand or scope) are ``ADJUSTMENT_OUT_OF_SCOPE``; a unit,
    amount or direction that differs from the record is ``ADJUSTMENT_MISMATCH``.
    """
    out_of_scope = AdjustmentRejection(
        adjustment=adjustment, reason=ReasonCode.ADJUSTMENT_OUT_OF_SCOPE
    )
    mismatch = AdjustmentRejection(adjustment=adjustment, reason=ReasonCode.ADJUSTMENT_MISMATCH)
    own = operand.result
    definition = definitions.record(adjustment.definition_record_id)
    if (
        definition is None
        or adjustment.operand_name != operand.operand_name
        or own.status is not ExtractionStatus.TAGGING_DIFFERENCE
        or own.pair is None
        or own.pair.definition_record_id != definition.record_id
        or definition.operand_name != operand.operand_name
        or definition.canonical_id != operand.xbrl.key.canonical_id
        or not _operand_in_scope(definition, operand)
    ):
        return out_of_scope
    named = operand.side(adjustment.representation)
    counterpart = operand.side(_other(adjustment.representation))
    if (
        adjustment.unit is not named.key.value_kind
        or adjustment.unit is not definition.unit
        or adjustment.amount != definition.explained_amount
        or not _moves_toward(adjustment.direction, named, counterpart)
    ):
        return mismatch
    return adjustment


def derived_extraction_status(
    *,
    row: DictionaryRow,
    output: MeasurementKey,
    every_operand_single_representation: bool,
    operands: Mapping[str, OperandExtraction],
    xbrl: ComparisonSide,
    pdf: ComparisonSide,
    adjustments: Sequence[TaggingAdjustment],
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
    rounding: RoundingPolicy,
    qualification: QualificationContext,
    dictionary: CanonicalDictionary,
    reporting_currency: str,
) -> ExtractionResult:
    """The extraction table over a formula evaluated per representation.

    If the unadjusted pair is ``DISAGREE``, each accepted adjustment shifts its operand and
    both representations are re-evaluated with ``evaluate_formula``; the status is
    ``TAGGING_DIFFERENCE`` only if the re-evaluated intervals intersect, else ``DISAGREE``.
    """
    unadjusted = extraction_status(
        family_has_pair=not every_operand_single_representation,
        xbrl=xbrl,
        pdf=pdf,
        definitions=definitions,
        policy=policy,
    )
    if unadjusted.status is not ExtractionStatus.DISAGREE or not adjustments:
        return unadjusted
    accepted: list[TaggingAdjustment] = []
    rejected: list[AdjustmentRejection] = []
    offered: set[tuple[str, str]] = set()
    for adjustment in adjustments:
        operand = operands.get(adjustment.operand_name)
        if operand is None:
            raise ValueError(_UNKNOWN_OPERAND.format(name=adjustment.operand_name))
        # A record's amount is applied to an operand at most once, on either representation
        # (the pair_adjustments key); a repeat would apply an amount the record does not hold.
        application = (adjustment.definition_record_id, adjustment.operand_name)
        if application in offered:
            rejected.append(
                AdjustmentRejection(adjustment=adjustment, reason=ReasonCode.ADJUSTMENT_MISMATCH)
            )
            continue
        offered.add(application)
        verdict = validate_adjustment(adjustment, operand=operand, definitions=definitions)
        if isinstance(verdict, AdjustmentRejection):
            rejected.append(verdict)
        else:
            accepted.append(verdict)
    status = ExtractionStatus.DISAGREE
    if accepted:
        intervals = [
            _re_evaluated(
                representation,
                row=row,
                output=output,
                operands=operands,
                accepted=accepted,
                rounding=rounding,
                qualification=qualification,
                dictionary=dictionary,
                reporting_currency=reporting_currency,
            )
            for representation in (Representation.XBRL, Representation.PDF)
        ]
        left, right = intervals
        if left is not None and right is not None and left.intersects(right):
            status = ExtractionStatus.TAGGING_DIFFERENCE
    return unadjusted.model_copy(
        update={
            "status": status,
            "adjustments": tuple(accepted),
            "rejected_adjustments": tuple(rejected),
        }
    )


def corroboration_result(
    *,
    applicability: ApplicabilityStatus,
    first_party: SourceQualifiedSide,
    vendors: Sequence[SourceQualifiedSide],
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
) -> CorroborationResult:
    """All fifteen ordered conditions; diagnostics enter neither states nor pairs."""
    if first_party.ref.source_role is not SourceRole.FIRST_PARTY:
        raise ValueError("the representative is a first-party source")
    if any(
        source.ref.source_role not in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)
        for source in vendors
    ):
        raise ValueError("vendor inputs are independent or diagnostic sources")
    if applicability is ApplicabilityStatus.NOT_APPLICABLE:
        return CorroborationResult(status=CorroborationStatus.NOT_APPLICABLE, reason=None)
    independent = tuple(
        source for source in vendors if source.ref.source_role is SourceRole.INDEPENDENT_VENDOR
    )
    if len({source.ref.model_dump_json() for source in independent}) != len(independent):
        raise ValueError("each independent vendor surface has exactly one resolved state")
    pairs = tuple(
        _qualified_pair(first_party, source, PairKind.CORROBORATION, definitions, policy)
        for source in independent
        if first_party.side.state in _PAIRABLE and source.side.state in _PAIRABLE
    )
    status, reason = _corroboration_decision(
        applicability,
        first_party.side,
        tuple(source.side for source in independent),
        tuple(pair.result for pair in pairs),
    )
    sources = (first_party, *independent)
    return CorroborationResult(
        status=status,
        reason=reason,
        pairs=pairs,
        sources=sources,
        unavailable_sources=tuple(
            source.ref for source in sources if source.side.state is SourceState.UNAVAILABLE
        ),
    )


def diagnostic_pair(
    first: SourceQualifiedSide,
    other: SourceQualifiedSide,
    *,
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
) -> SourceQualifiedPair | None:
    """A diagnostic uses the same refusal-first pair table, with no status contribution."""
    if first.side.state not in _PAIRABLE or other.side.state not in _PAIRABLE:
        return None
    return _qualified_pair(first, other, PairKind.DIAGNOSTIC, definitions, policy)


def _qualified_pair(
    first: SourceQualifiedSide,
    other: SourceQualifiedSide,
    kind: PairKind,
    definitions: DefinitionSet,
    policy: ComparisonPolicy,
) -> SourceQualifiedPair:
    return SourceQualifiedPair(
        pair_kind=kind,
        left=first.ref,
        right=other.ref,
        result=pair_outcome(first.side, other.side, definitions=definitions, policy=policy),
        evidence_occurrence_ids=tuple(sorted(set(first.occurrence_ids + other.occurrence_ids))),
        evidence_interpretation_ids=tuple(
            sorted(set(first.interpretation_ids + other.interpretation_ids))
        ),
        attempt_ids=tuple(sorted(set(first.attempt_ids + other.attempt_ids))),
    )


def corroboration_status(
    *, applicability: ApplicabilityStatus, first_party: ComparisonSide
) -> tuple[CorroborationStatus, ReasonCode | None]:
    """The corroboration table for an empty vendor set: rows 1, 2, 2a, 5 and 7."""
    return _corroboration_decision(applicability, first_party, (), ())


def _corroboration_decision(
    applicability: ApplicabilityStatus,
    first_party: ComparisonSide,
    vendors: Sequence[ComparisonSide],
    pairs: Sequence[PairResult],
) -> tuple[CorroborationStatus, ReasonCode | None]:
    if applicability is ApplicabilityStatus.NOT_APPLICABLE:
        return CorroborationStatus.NOT_APPLICABLE, None
    if first_party.state is SourceState.UNAVAILABLE:
        return CorroborationStatus.UNAVAILABLE, None
    if first_party.state is SourceState.INVALID:
        return CorroborationStatus.NOT_COMPARABLE, _invalid_reason(first_party)
    states = {source.state for source in vendors}
    if first_party.state is SourceState.NO_VALUE:
        if SourceState.VALUE in states:
            return CorroborationStatus.VENDOR_ONLY, None
        if SourceState.UNAVAILABLE in states:
            return CorroborationStatus.UNAVAILABLE, None
        invalid = next((source for source in vendors if source.state is SourceState.INVALID), None)
        if invalid is not None:
            return CorroborationStatus.NOT_COMPARABLE, _invalid_reason(invalid)
        return CorroborationStatus.NO_SOURCE, None
    if not states.intersection(_PAIRABLE):
        return (
            CorroborationStatus.UNAVAILABLE
            if SourceState.UNAVAILABLE in states
            else CorroborationStatus.FILING_ONLY
        ), None
    precedence = (
        (PairOutcome.MISMATCH, CorroborationStatus.CONFLICT),
        (PairOutcome.AGREE, CorroborationStatus.CORROBORATED),
        (PairOutcome.AGREE_UNQUALIFIED, CorroborationStatus.AGREES_UNQUALIFIED),
        (PairOutcome.ANOMALY, CorroborationStatus.ANOMALY),
        (PairOutcome.DEFINITION_DIFFERENCE, CorroborationStatus.DEFINITION_DIFFERENCE),
    )
    for outcome, status in precedence:
        if any(pair.outcome is outcome for pair in pairs):
            return status, None
    return CorroborationStatus.NOT_COMPARABLE, next(
        (pair.reason for pair in pairs if pair.reason is not None), ReasonCode.SIDE_INVALID
    )


def _row_one_reason(
    first: ComparisonSide, other: ComparisonSide, relationship: EvidencedRelationship | None
) -> ReasonCode | None:
    """The pair-table row-1 reason, if any: key parts first, then each side's own refusal."""
    left, right = first.key, other.key
    if left.canonical_id != right.canonical_id and not (
        relationship is not None and relationship.names(left.canonical_id, right.canonical_id)
    ):
        return ReasonCode.CANONICAL_MISMATCH
    for part, reason in _KEY_PARTS:
        if part(left) != part(right):
            return reason
    for side in (first, other):
        if side.state is SourceState.INVALID:
            return _invalid_reason(side)
        refusal = next((code for code in side.reasons if code in _VALUE_SIDE_REFUSALS), None)
        if refusal is not None:
            return refusal
        if side.interval is None:
            return ReasonCode.PRECISION_UNSUPPORTED
    return None


def _require_one_package(xbrl: ComparisonSide, pdf: ComparisonSide) -> None:
    """Refuse an extraction across packages; a side read from a capture names its package."""
    named = {xbrl.package_id, pdf.package_id}
    read = any(side.state in _PAIRABLE for side in (xbrl, pdf))
    if len(named - {None}) > 1 or (read and None in named):
        raise ValueError(_OTHER_PACKAGE.format(xbrl=xbrl.package_id, pdf=pdf.package_id))


def _invalid_reason(side: ComparisonSide) -> ReasonCode:
    """An ``INVALID`` side's own first reason, else the generic one."""
    return side.reasons[0] if side.reasons else ReasonCode.SIDE_INVALID


def _qualified(first: ComparisonSide, other: ComparisonSide) -> bool:
    """Both sides demonstrated within scope, or both aligned by a filing-specific proof."""
    demonstrated = EvidenceTier.EQUIVALENCE_DEMONSTRATED
    both_demonstrated = first.tier is demonstrated and other.tier is demonstrated
    return both_demonstrated or (first.aligned_by_proof and other.aligned_by_proof)


def _reconciling_record(
    first: ComparisonSide, other: ComparisonSide, definitions: DefinitionSet
) -> DefinitionRecord | None:
    """The first in-scope record whose explained amount closes the gap to within tolerance.

    The amount is applied to ``first`` toward ``other``; shifting either side by the same
    amount toward the other is the same test.
    """
    assert first.value is not None and other.value is not None
    assert first.interval is not None and other.interval is not None
    toward = 1 if other.value > first.value else -1
    for definition in definitions.records:
        if not _pair_in_scope(definition, first, other):
            continue
        shift = Fraction(definition.explained_amount) * toward
        if first.interval.shift(shift).intersects(other.interval):
            return definition
    return None


def _pair_in_scope(
    definition: DefinitionRecord, first: ComparisonSide, other: ComparisonSide
) -> bool:
    """Whether a record applies to this pair: its row and unit, and its own scope."""
    canonical_ids = {first.key.canonical_id, other.key.canonical_id}
    if definition.canonical_id not in canonical_ids or definition.unit is not first.key.value_kind:
        return False
    if definition.scope is DefinitionScope.MAPPING:
        return definition.scope_ref in first.mapping_entry_ids + other.mapping_entry_ids
    if definition.scope is DefinitionScope.MEASUREMENT:
        return definition.scope_ref in {first.key.digest(), other.key.digest()}
    return first.package_id is not None and definition.package_id() == first.package_id


def _operand_in_scope(definition: DefinitionRecord, operand: OperandExtraction) -> bool:
    """Whether a record's scope names this operand's mapping entry, key or package."""
    values = (operand.xbrl, operand.pdf)
    if definition.scope is DefinitionScope.MAPPING:
        return definition.scope_ref in {value.mapping_entry_id for value in values}
    if definition.scope is DefinitionScope.MEASUREMENT:
        return definition.scope_ref in {value.key.digest() for value in values}
    return definition.package_id() in {value.package_id for value in values} - {None}


def _moves_toward(direction: int, named: OperandValue, counterpart: OperandValue) -> bool:
    """Whether ``direction`` moves the named value toward the other representation's value."""
    if named.exact is None or counterpart.exact is None or named.exact == counterpart.exact:
        return False
    return direction == (1 if counterpart.exact > named.exact else -1)


def _other(representation: Representation) -> Representation:
    """The other first-party representation."""
    return Representation.PDF if representation is Representation.XBRL else Representation.XBRL


def _re_evaluated(
    representation: Representation,
    *,
    row: DictionaryRow,
    output: MeasurementKey,
    operands: Mapping[str, OperandExtraction],
    accepted: Sequence[TaggingAdjustment],
    rounding: RoundingPolicy,
    qualification: QualificationContext,
    dictionary: CanonicalDictionary,
    reporting_currency: str,
) -> Interval | None:
    """One representation's formula interval with its accepted adjustments applied."""
    values = {name: operand.side(representation) for name, operand in operands.items()}
    for adjustment in accepted:
        if adjustment.representation is representation:
            values[adjustment.operand_name] = _shifted(
                values[adjustment.operand_name], Fraction(adjustment.amount) * adjustment.direction
            )
    result = evaluate_formula(
        row,
        output,
        values,
        rounding,
        dictionary=dictionary,
        reporting_currency=reporting_currency,
        qualification=qualification,
    )
    return result.interval


def _shifted(value: OperandValue, amount: Fraction) -> OperandValue:
    """An operand moved by ``amount``: its exact value, interval and displayed value."""
    assert value.exact is not None and value.value is not None
    return value.model_copy(
        update={
            "exact": value.exact + amount,
            "value": value.value + _decimal(amount),
            "interval": None if value.interval is None else value.interval.shift(amount),
        }
    )


def _decimal(value: Fraction) -> Decimal:
    """A rational as a Decimal for reporting (exact when the denominator divides a power of 10)."""
    return Decimal(value.numerator) / Decimal(value.denominator)


def _result(
    outcome: PairOutcome,
    *,
    reason: ReasonCode | None = None,
    difference: Decimal | None = None,
    gap: Decimal | None = None,
    record_id: str | None = None,
    triage_class: Triage | None = None,
) -> PairResult:
    """A pair result; triage only accompanies ``MISMATCH`` and ``ANOMALY``."""
    assert triage_class is None or outcome in _OUTSIDE
    return PairResult(
        outcome=outcome,
        reason=reason,
        triage=triage_class,
        difference=difference,
        interval_gap=gap,
        definition_record_id=record_id,
    )
