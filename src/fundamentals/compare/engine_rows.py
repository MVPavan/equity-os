"""Comparison sides, stored source values and pair records for one result row (D1a Task 9).

Pure conversions between the selection and calculation contracts and the run's stored
shapes. A side that is not ``VALUE`` never carries a number; absence stays absence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.applicability import ApplicabilityDecision
from fundamentals.canon.dictionary import DictionaryRow
from fundamentals.canon.formula import CalculationResult
from fundamentals.compare.run_models import (
    PairRecord,
    ResultRow,
    SourceRef,
    SourceRole,
    SourceValue,
    row_id,
)
from fundamentals.compare.tables import ComparisonSide, PairResult, TaggingAdjustment
from fundamentals.contracts.canonical import Representation, ValueIdentity, ValueKind
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    ReasonCode,
    SourceState,
)
from fundamentals.contracts.evidence import (
    FilingPackage,
    Interpretation,
    KeySelection,
    Occurrence,
    PackageMember,
    exact_decimal,
)
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.qualification import QualificationContext, qualification_context
from fundamentals.evidence.alignment import AlignmentProof
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.derived import operand_value
from fundamentals.evidence.interpret import prove_conditions
from fundamentals.evidence.mapping import CONTEXT_SCHEMA_IDENTITY

REPRESENTATIONS = (Representation.XBRL, Representation.PDF)
MONETARY = frozenset({ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT})
_REASON_CODES = frozenset(code.value for code in ReasonCode)
# A non-value side's precedence when no side holds a value: unavailable is never hidden.
_ABSENCE_ORDER = (SourceState.UNAVAILABLE, SourceState.INVALID, SourceState.NO_VALUE)


class Cell(BaseModel):
    """One representation's selection for one key, and the attempt that decided it, if any."""

    model_config = ConfigDict(frozen=True)

    selection: KeySelection
    attempt_id: int | None


class Side(BaseModel):
    """One representation's side of a row: the comparison input and the stored value."""

    model_config = ConfigDict(frozen=True)

    comparison: ComparisonSide
    stored: SourceValue


def reason_codes(reasons: Sequence[str | None]) -> tuple[ReasonCode, ...]:
    """The reasons that are table reason codes, in order (others stay on the stored value)."""
    return tuple(ReasonCode(item) for item in reasons if item in _REASON_CODES)


def family_has_pair(package: FilingPackage | None, cells: Mapping[Representation, Cell]) -> bool:
    """Extraction table row 1: a package with a representation that is neither a member nor
    attempted (an XBRL-only package) has no paired first-party representation."""
    return package is None or all(
        rep in package.members or cells[rep].attempt_id is not None for rep in REPRESENTATIONS
    )


def selected_side(
    cell: Cell,
    representation: Representation,
    *,
    proofs: Sequence[AlignmentProof],
    package_id: int | None,
    role: SourceRole = SourceRole.FIRST_PARTY,
    source_id: str | None = None,
    surface: str | None = None,
) -> Side:
    """A reported side: the selection's value, scoped tier (or proof) and provenance."""
    selection = cell.selection
    operand = operand_value(selection, proofs=proofs)
    chosen = selection.interpretation
    valued = selection.state is SourceState.VALUE
    interval = operand.interval if valued else None
    comparison = ComparisonSide(
        key=selection.key,
        state=selection.state,
        value=operand.value if valued else None,
        interval=interval,
        tier=operand.scoped_tier,
        aligned_by_proof=operand.alignment_proof_id is not None,
        mapping_entry_ids=() if operand.mapping_entry_id is None else (operand.mapping_entry_id,),
        package_id=package_id,
        calculation_state=None,
        reasons=reason_codes([selection.reason]),
        condition_evidence=() if chosen is None else chosen.condition_evidence,
    )
    stored = SourceValue(
        source_role=role,
        representation=representation,
        source_id=source_id,
        surface=surface,
        state=selection.state,
        reason=selection.reason,
        value=operand.value if valued else None,
        lower=None if interval is None else exact_decimal(interval.lower),
        upper=None if interval is None else exact_decimal(interval.upper),
        interpretation_id=None if chosen is None else chosen.interpretation_id,
        calculation_trace_id=None,
        attempt_id=cell.attempt_id,
        calculation_state=None,
    )
    return Side(comparison=comparison, stored=stored)


def calculated_side(
    result: CalculationResult,
    *,
    key: MeasurementKey,
    representation: Representation,
    trace_id: int,
    package_id: int | None,
) -> Side:
    """A derived side: the calculation's state, stored rounding, exact interval and trace."""
    valued = result.source_state is SourceState.VALUE
    comparison = ComparisonSide(
        key=key,
        state=result.source_state,
        value=result.value if valued else None,
        interval=result.interval if valued else None,
        tier=result.effective_tier,
        aligned_by_proof=False,
        mapping_entry_ids=(),
        package_id=package_id,
        calculation_state=result.state,
        reasons=reason_codes(result.reasons),
    )
    stored = SourceValue(
        source_role=SourceRole.FIRST_PARTY,
        representation=representation,
        state=result.source_state,
        reason=result.reasons[0] if result.reasons else None,
        value=result.value if valued else None,
        lower=result.trace.lower if valued else None,
        upper=result.trace.upper if valued else None,
        interpretation_id=None,
        calculation_trace_id=trace_id,
        attempt_id=None,
        calculation_state=result.state,
    )
    return Side(comparison=comparison, stored=stored)


def representative(xbrl: ComparisonSide, pdf: ComparisonSide) -> ComparisonSide:
    """The first-party side for corroboration: XBRL if it holds a value, else PDF.

    With no value on either side, an unavailable side decides first, then an invalid one,
    so a failed read is never reported as absence.
    """
    for side in (xbrl, pdf):
        if side.state is SourceState.VALUE:
            return side
    for state in _ABSENCE_ORDER:
        for side in (xbrl, pdf):
            if side.state is state:
                return side
    return xbrl


def pair_record(
    kind: PairKind,
    left: SourceRef,
    right: SourceRef,
    pair: PairResult,
    adjustments: Sequence[TaggingAdjustment] = (),
) -> PairRecord:
    """One pair outcome as stored, between two source values of the same row."""
    return PairRecord(
        pair_kind=kind,
        left=left,
        right=right,
        outcome=pair.outcome,
        reason=pair.reason,
        triage=pair.triage,
        difference=pair.difference,
        interval_gap=pair.interval_gap,
        definition_record_id=pair.definition_record_id,
        adjustments=tuple(adjustments),
    )


def ref(role: SourceRole, representation: Representation) -> SourceRef:
    """A pair side reference."""
    return SourceRef(source_role=role, representation=representation)


def pairable(side: ComparisonSide) -> bool:
    """Whether a side may enter the pair table (``VALUE`` or ``INVALID``)."""
    return side.state in (SourceState.VALUE, SourceState.INVALID)


def as_counterpart(value: SourceValue) -> SourceValue:
    """A reported value restated on a derived row so a pair there can name it."""
    return value.model_copy(update={"source_role": SourceRole.REPORTED_COUNTERPART})


def sorted_values(values: tuple[SourceValue, ...]) -> tuple[SourceValue, ...]:
    """Source values in one order: role, then representation."""
    return tuple(sorted(values, key=lambda item: (item.source_role.value, item.representation)))


def not_applicable_row(
    key: MeasurementKey,
    identity: ValueIdentity,
    decision: ApplicabilityDecision,
    dictionary_version: str,
) -> ResultRow:
    """A row decided inapplicable from context alone: no value is read."""
    return ResultRow(
        row_id=row_id(key, identity),
        key=key,
        dictionary_version=dictionary_version,
        value_identity=identity,
        applicability=decision.status,
        applicability_rule_id=decision.rule_id,
        extraction_status=ExtractionStatus.NOT_APPLICABLE,
        extraction_reason=None,
        corroboration_status=CorroborationStatus.NOT_APPLICABLE,
        corroboration_reason=None,
        source_values=(),
        pairs=(),
        surfaced_restatements=(),
    )


def output_context(
    row: DictionaryRow,
    key: MeasurementKey,
    member: PackageMember | None,
    *,
    representation: Representation,
    witness: Occurrence | None,
    interpretations: Sequence[Interpretation],
    fiscal_month: int,
) -> QualificationContext:
    """A derived output's own context in one representation (Task 7)."""
    schema = "" if witness is None else str(witness.native_context.get(CONTEXT_SCHEMA_IDENTITY, ""))
    scope = row.formula.qualification if row.formula is not None else None
    conditions = () if scope is None else (*scope.conditions, *scope.exclusions)
    proven = prove_conditions(
        conditions, interpretations=interpretations, period=key.period, basis=key.basis
    )
    return qualification_context(
        key,
        schema_identity=schema,
        surface=member.capture.surface if member else SURFACE_OF[representation].value,
        fiscal_year_end_month=fiscal_month,
        proven=proven,
    )
