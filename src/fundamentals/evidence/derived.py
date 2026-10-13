"""Scoped operand tiers and derived evaluation with stored traces (D1a Task 7).

Each derived row is evaluated per representation over Task 6 selections. An operand's tier
is ``EQUIVALENCE_DEMONSTRATED`` only through a holding alignment proof for its own package,
key and interpretation; otherwise it is the interpretation's stored scoped tier. Every
computed operand — a nested derived row, a dimensional aggregate, an average — has its
trace stored first, and its id is attached to the parent's operand before the parent is
hashed and stored (the 0002 CHECK refuses a computed operand without it). The parent
consumes the child's exact value and interval, never its stored rounding.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from fractions import Fraction
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import (
    CanonicalDictionary,
    DictionaryRow,
    DimensionalAggregation,
    FormulaOperand,
    MemberBinding,
)
from fundamentals.canon.formula import (
    CalculationResult,
    CalculationTrace,
    OperandValue,
    aggregate_members,
    average_operand,
    evaluate_formula,
    operand_from_result,
    resolve_operand_keys,
)
from fundamentals.canon.interval import RoundingPolicy
from fundamentals.contracts.canonical import Representation, TemporalRole
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import KeySelection
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.qualification import QualificationContext
from fundamentals.evidence.alignment import AlignmentProof
from fundamentals.evidence.repository import SegmentMemberRecord

Resolve = Callable[[MeasurementKey, TemporalRole], KeySelection]
QualificationFor = Callable[[DictionaryRow, MeasurementKey], QualificationContext]


@runtime_checkable
class TraceStore(Protocol):
    """Where evaluated traces go: the repository, or a run replay's read-only trace index."""

    def put_calculation_trace(self, trace: CalculationTrace) -> int:
        """Store (or find) one trace by content hash and return its id."""
        ...


_NO_FORMULA = "row {canonical_id!r} has no formula"
_NO_MEMBERS = "no evidenced {axis!r} member is valid for {period}"


class DerivedSide(BaseModel):
    """One representation's evaluation of a derived row, with its stored trace id.

    ``representation`` is ``None`` for shared single-representation operands.
    ``bound_member_ids`` are the segment-member records an entity-bound aggregation used.
    """

    model_config = ConfigDict(frozen=True)

    representation: Representation | None
    result: CalculationResult
    trace_id: int
    bound_member_ids: tuple[int, ...] = ()


class _Evaluation(BaseModel):
    """What every nested evaluation of one derived side shares.

    Process-local only: it carries the trace store (not a Pydantic model), so arbitrary
    types are allowed here and nowhere else in this module; it never crosses a boundary.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    resolve: Resolve
    proofs: tuple[AlignmentProof, ...]
    qualification: QualificationContext
    qualification_for: QualificationFor | None
    output: MeasurementKey
    fiscal_year_end_month: int
    policy: RoundingPolicy
    repository: TraceStore
    dictionary: CanonicalDictionary
    reporting_currency: str
    segment_members: tuple[SegmentMemberRecord, ...]


def operand_value(selection: KeySelection, *, proofs: Sequence[AlignmentProof]) -> OperandValue:
    """A selection as a formula operand with its scoped tier and selection source.

    A holding proof for the selection's package naming this exact interpretation gives
    ``EQUIVALENCE_DEMONSTRATED`` with the proof id; anything else keeps the
    interpretation's own stored scoped tier and qualification ref (direct and constructed
    alike). A value without an interval has no supported precision.
    """
    chosen = selection.interpretation
    valued = (
        selection.state is SourceState.VALUE and chosen is not None and chosen.value is not None
    )
    proof = _proof_for(selection, proofs)
    if proof is not None:
        tier, proof_id, ref = EvidenceTier.EQUIVALENCE_DEMONSTRATED, proof.proof_id, None
    elif chosen is not None:
        tier, proof_id, ref = chosen.tier, None, chosen.qualification_ref
    else:
        tier, proof_id, ref = EvidenceTier.EQUIVALENCE_UNPROVEN, None, None
    interval = chosen.interval if valued and chosen is not None else None
    return OperandValue(
        key=selection.key,
        state=selection.state,
        exact=Fraction(chosen.value) if valued and chosen and chosen.value is not None else None,
        value=chosen.value if valued and chosen is not None else None,
        interval=interval,
        interpretation_id=None if chosen is None else chosen.interpretation_id,
        package_id=selection.package_id,
        calculation_trace_id=None,
        child_trace=None,
        alignment_proof_id=proof_id,
        mapping_entry_id=None if chosen is None else chosen.mapping_entry_id,
        qualification_ref=ref,
        scoped_tier=tier,
        selection_source=selection.source,
        precision_supported=interval is not None,
        reasons=() if selection.reason is None else (selection.reason,),
    )


def evaluate_derived(
    row: DictionaryRow,
    output: MeasurementKey,
    *,
    representation: Representation | None,
    resolve: Resolve,
    proofs: Sequence[AlignmentProof],
    qualification: QualificationContext,
    policy: RoundingPolicy,
    repository: TraceStore,
    dictionary: CanonicalDictionary,
    reporting_currency: str,
    segment_members: Sequence[SegmentMemberRecord] = (),
    qualification_for: QualificationFor | None = None,
    fiscal_year_end_month: int = 3,
) -> DerivedSide:
    """Evaluate one derived row for ``output`` and store its trace (children first).

    ``qualification`` is the output measurement's own context and scopes the formula's
    tier. ``segment_members`` are the entity's knowledge-cutoff member records; an
    entity-bound aggregation binds those valid for the output period and pins their ids.
    ``qualification_for`` supplies context and condition proofs separately for every
    nested row/key. Without it nested conditions stay unproven; period kinds are still
    resolved using ``fiscal_year_end_month`` (March by default for existing callers).
    """
    context = _Evaluation(
        resolve=resolve,
        proofs=tuple(proofs),
        qualification=qualification,
        qualification_for=qualification_for,
        output=output,
        fiscal_year_end_month=fiscal_year_end_month,
        policy=policy,
        repository=repository,
        dictionary=dictionary,
        reporting_currency=reporting_currency,
        segment_members=tuple(segment_members),
    )
    bound: list[int] = []
    result, trace_id = _evaluate(row, output, context, bound)
    return DerivedSide(
        representation=representation,
        result=result,
        trace_id=trace_id,
        bound_member_ids=tuple(sorted(set(bound))),
    )


def bind_entity_members(
    aggregation: DimensionalAggregation,
    records: Sequence[SegmentMemberRecord],
    *,
    entity_id: int,
    period: PeriodInterval,
) -> tuple[DimensionalAggregation, tuple[int, ...]] | None:
    """Bind an entity-evidence aggregation to the members valid for ``period``.

    A record is valid when it starts on or before the period's first day and has not
    ended before its last day. Returns the bound aggregation and the record ids used, or
    ``None`` when no member is evidenced for the period.
    """
    first = period.start or period.instant
    last = period.end or period.instant
    assert first is not None and last is not None
    valid = [
        record
        for record in records
        if record.entity_id == entity_id
        and record.axis == aggregation.axis
        and record.valid_from <= first
        and (record.valid_to is None or record.valid_to >= last)
    ]
    if not valid:
        return None
    members = sorted({record.member for record in valid})
    return aggregation.bind_members(members), tuple(sorted(record.id for record in valid))


def _evaluate(
    row: DictionaryRow, output: MeasurementKey, context: _Evaluation, bound: list[int]
) -> tuple[CalculationResult, int]:
    """Evaluate a formula row, storing every child trace before its own."""
    formula = row.formula
    if formula is None:
        raise ValueError(_NO_FORMULA.format(canonical_id=row.canonical_id))
    operands = {
        operand.name: _operand(operand, output, context, bound) for operand in formula.operands
    }
    result = evaluate_formula(
        row,
        output,
        operands,
        context.policy,
        dictionary=context.dictionary,
        reporting_currency=context.reporting_currency,
        qualification=_qualification_for(row, output, context),
    )
    return result, context.repository.put_calculation_trace(result.trace)


def _qualification_for(
    row: DictionaryRow, output: MeasurementKey, context: _Evaluation
) -> QualificationContext:
    """Resolve scope and condition evidence for this particular nested output key."""
    if context.qualification_for is not None:
        return context.qualification_for(row, output)
    return context.qualification.model_copy(
        update={
            "basis": output.basis,
            "period_kind": output.period.kind(context.fiscal_year_end_month),
            "proven": context.qualification.proven if output == context.output else {},
        }
    )


def _operand(
    operand: FormulaOperand, output: MeasurementKey, context: _Evaluation, bound: list[int]
) -> OperandValue:
    """One formula operand: selected, aggregated, averaged or a nested derived row."""
    keys = resolve_operand_keys(
        output,
        operand,
        dictionary=context.dictionary,
        reporting_currency=context.reporting_currency,
    )
    if operand.aggregation is not None:
        (key,) = keys
        return _aggregate(operand, key, context, bound)
    if operand.temporal_role is TemporalRole.AVERAGE:
        opening_key, closing_key = keys
        averaged = average_operand(
            _constituent(opening_key, TemporalRole.OPENING, context, bound),
            _constituent(closing_key, TemporalRole.CLOSING, context, bound),
            output=opening_key.model_copy(update={"period": output.period}),
            policy=context.policy,
        )
        return _stored_child(averaged, context)
    (key,) = keys
    return _constituent(key, operand.temporal_role, context, bound)


def _constituent(
    key: MeasurementKey, role: TemporalRole, context: _Evaluation, bound: list[int]
) -> OperandValue:
    """Resolve a leaf or recursively evaluate a derived constituent at its own key."""
    nested = context.dictionary.row(key.canonical_id)
    if nested.formula is None:
        return _selected(key, role, context)
    result, trace_id = _evaluate(nested, key, context, bound)
    child = operand_from_result(result, key=key, selection_source=None)
    return child.model_copy(update={"calculation_trace_id": trace_id})


def _aggregate(
    operand: FormulaOperand, key: MeasurementKey, context: _Evaluation, bound: list[int]
) -> OperandValue:
    """Sum the bound members of one axis; the child trace lists every bound member."""
    aggregation = operand.aggregation
    assert aggregation is not None
    if aggregation.member_binding is MemberBinding.ENTITY_EVIDENCE:
        binding = bind_entity_members(
            aggregation, context.segment_members, entity_id=key.entity_id, period=key.period
        )
        if binding is None:
            return _absent(key, _NO_MEMBERS.format(axis=aggregation.axis, period=key.period))
        aggregation, member_ids = binding
        bound.extend(member_ids)
    axes = dict(key.dimensions.pairs)
    values = {
        member: _constituent(
            key.model_copy(
                update={"dimensions": DimensionSet.of({**axes, aggregation.axis: member})}
            ),
            operand.temporal_role,
            context,
            bound,
        )
        for member in aggregation.input_members
    }
    aggregated = aggregate_members(aggregation, values, output=key, policy=context.policy)
    return _stored_child(aggregated, context)


def _selected(key: MeasurementKey, role: TemporalRole, context: _Evaluation) -> OperandValue:
    """The caller's selection for one key at one role, as an operand."""
    return operand_value(context.resolve(key, role), proofs=context.proofs)


def _stored_child(operand: OperandValue, context: _Evaluation) -> OperandValue:
    """Store a computed operand's child trace and attach its id before the parent hashes."""
    assert operand.child_trace is not None
    trace_id = context.repository.put_calculation_trace(operand.child_trace)
    return operand.model_copy(update={"calculation_trace_id": trace_id})


def _absent(key: MeasurementKey, reason: str) -> OperandValue:
    """An operand with no value and no selection: ``NO_VALUE`` with the reason traced."""
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
        reasons=(reason,),
    )


def _proof_for(selection: KeySelection, proofs: Sequence[AlignmentProof]) -> AlignmentProof | None:
    """The first holding proof for this package and key that names this interpretation."""
    chosen = selection.interpretation
    if chosen is None or chosen.interpretation_id is None or selection.package_id is None:
        return None
    matches = [
        proof
        for proof in proofs
        if proof.holds
        and proof.proof_id is not None
        and proof.package_id == selection.package_id
        and proof.key == selection.key
        and chosen.interpretation_id in (proof.xbrl_interpretation_id, proof.pdf_interpretation_id)
    ]
    return min(matches, key=lambda proof: proof.proof_id or 0, default=None)
