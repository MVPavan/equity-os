"""SQL and row conversions for alignment proofs and calculation traces (D1a Task 7).

Kept apart from :mod:`fundamentals.evidence.repository` so the repository class stays a
thin list of operations. Every statement is parameterised. Exact rationals are stored as
reduced ``p/q`` text, so a re-read trace hashes to the content hash it was stored under.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any, LiteralString

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.formula import CalculationTrace, TraceKind, TraceOperand
from fundamentals.contracts.canonical import Representation, TemporalRole, ValueIdentity
from fundamentals.contracts.comparison import CalculationState, SelectionSource, SourceState
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.evidence.alignment import AlignmentProof

Row = Mapping[str, Any]

_TRACE_COLUMNS: LiteralString = (
    "content_sha256, trace_kind, formula_id, formula_version, formula_tier, "
    "formula_qualification_ref, rounding_policy_id, key_digest, value_identity, state, value, "
    "lower, upper, exact_value, exact_lower, exact_upper, effective_tier"
)
INSERT_TRACE: LiteralString = (
    "INSERT INTO eqos.calculation_traces (" + _TRACE_COLUMNS + ") VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT DO NOTHING RETURNING id"
)
SELECT_TRACE_ID: LiteralString = "SELECT id FROM eqos.calculation_traces WHERE content_sha256 = %s"
TRACES_BY_ID: LiteralString = (
    "SELECT id, " + _TRACE_COLUMNS + " FROM eqos.calculation_traces WHERE id = ANY(%s) ORDER BY id"
)
_OPERAND_COLUMNS: LiteralString = (
    "calculation_trace_id, ordinal, operand_name, key_digest, temporal_role, interpretation_id, "
    "operand_trace_id, alignment_proof_id, mapping_entry_id, qualification_ref, scoped_tier, "
    "selection_source, source_state, value, lower, upper, exact_value, exact_lower, exact_upper"
)
INSERT_TRACE_OPERAND: LiteralString = (
    "INSERT INTO eqos.calculation_trace_operands (" + _OPERAND_COLUMNS + ") VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
OPERANDS_OF_TRACES: LiteralString = (
    "SELECT " + _OPERAND_COLUMNS + " FROM eqos.calculation_trace_operands "
    "WHERE calculation_trace_id = ANY(%s) ORDER BY calculation_trace_id, ordinal"
)
# A selector construction carries its trace in ``transform_trace`` under this key, as JSON.
CONSTRUCTION_TRACE = "calculation_trace"
INSERT_CONSTRUCTION_TRACE: LiteralString = (
    "INSERT INTO eqos.construction_traces (interpretation_id, calculation_trace_id) VALUES (%s, %s)"
)
CONSTRUCTION_TRACES: LiteralString = (
    "SELECT interpretation_id, calculation_trace_id FROM eqos.construction_traces "
    "WHERE interpretation_id = ANY(%s)"
)
_PROOF_COLUMNS: LiteralString = (
    "package_id, key_digest, canonical_id, rule_id, rule_set_version, xbrl_interpretation_id, "
    "pdf_interpretation_id, participants_digest, holds"
)
INSERT_PROOF: LiteralString = (
    "INSERT INTO eqos.alignment_proofs (" + _PROOF_COLUMNS + ") VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id"
)
SELECT_PROOF_ID: LiteralString = (
    "SELECT id FROM eqos.alignment_proofs WHERE package_id = %s AND key_digest = %s "
    "AND rule_id = %s AND rule_set_version = %s AND participants_digest = %s"
)
INSERT_PARTICIPANT: LiteralString = (
    "INSERT INTO eqos.alignment_proof_participants "
    "(alignment_proof_id, interpretation_id, representation) VALUES (%s, %s, %s)"
)
_PROOF_SELECT: LiteralString = (
    "SELECT p.id, p.package_id, p.key_digest, p.rule_id, p.rule_set_version, "
    "p.xbrl_interpretation_id, p.pdf_interpretation_id, p.participants_digest, p.holds, "
    "array_agg(a.interpretation_id ORDER BY a.representation, a.interpretation_id) AS ids, "
    "array_agg(a.representation ORDER BY a.representation, a.interpretation_id) AS reps "
    "FROM eqos.alignment_proofs p "
    "JOIN eqos.alignment_proof_participants a ON a.alignment_proof_id = p.id "
)
PROOFS_BY_ID: LiteralString = _PROOF_SELECT + "WHERE p.id = ANY(%s) GROUP BY p.id ORDER BY p.id"
PROOFS_OF_PACKAGE: LiteralString = (
    _PROOF_SELECT + "WHERE p.package_id = %s GROUP BY p.id ORDER BY p.id"
)

_DIGEST_DRIFT = "stored {what} {stored} does not match {expected}"


class StoredTrace(BaseModel):
    """A stored trace with its id and the child traces its operands reference, in order."""

    model_config = ConfigDict(frozen=True)

    trace_id: int
    trace: CalculationTrace
    children: tuple[StoredTrace, ...]


class ProvenanceMismatchError(RuntimeError):
    """A stored trace or proof does not read back as written: refuse it."""


def exact_text(value: Fraction | None) -> str | None:
    """A rational as reduced ``p/q`` text."""
    return None if value is None else f"{value.numerator}/{value.denominator}"


def _fraction(text: str | None) -> Fraction | None:
    """Parse ``p/q`` text."""
    return None if text is None else Fraction(text)


def _interval(lower: str | None, upper: str | None) -> Interval | None:
    """An exact interval from its stored bounds."""
    low, high = _fraction(lower), _fraction(upper)
    if low is None or high is None:
        return None
    return Interval(lower=low, upper=high)


def trace_params(trace: CalculationTrace) -> tuple[object, ...]:
    """Column values of one trace row, in ``_TRACE_COLUMNS`` order."""
    interval = trace.exact_interval
    return (
        trace.content_sha256(),
        trace.trace_kind.value,
        trace.formula_id,
        trace.formula_version,
        None if trace.formula_tier is None else trace.formula_tier.value,
        trace.formula_qualification_ref,
        trace.rounding_policy_id,
        trace.key_digest,
        trace.value_identity.value,
        trace.state.value,
        trace.value,
        trace.lower,
        trace.upper,
        exact_text(trace.exact_value),
        exact_text(None if interval is None else interval.lower),
        exact_text(None if interval is None else interval.upper),
        trace.effective_tier.value,
    )


def operand_params(trace_id: int, ordinal: int, operand: TraceOperand) -> tuple[object, ...]:
    """Column values of one operand row, in ``_OPERAND_COLUMNS`` order."""
    interval = operand.exact_interval
    return (
        trace_id,
        ordinal,
        operand.name,
        operand.key_digest,
        operand.temporal_role.value,
        operand.interpretation_id,
        operand.operand_trace_id,
        operand.alignment_proof_id,
        operand.mapping_entry_id,
        operand.qualification_ref,
        operand.scoped_tier.value,
        None if operand.selection_source is None else operand.selection_source.value,
        operand.source_state.value,
        operand.value,
        operand.lower,
        operand.upper,
        exact_text(operand.exact_value),
        exact_text(None if interval is None else interval.lower),
        exact_text(None if interval is None else interval.upper),
    )


def operand_of(row: Row) -> TraceOperand:
    """One operand row as a model."""
    return TraceOperand(
        name=row["operand_name"],
        key_digest=row["key_digest"],
        temporal_role=TemporalRole(row["temporal_role"]),
        interpretation_id=row["interpretation_id"],
        operand_trace_id=row["operand_trace_id"],
        alignment_proof_id=row["alignment_proof_id"],
        mapping_entry_id=row["mapping_entry_id"],
        qualification_ref=row["qualification_ref"],
        scoped_tier=EvidenceTier(row["scoped_tier"]),
        selection_source=(
            None if row["selection_source"] is None else SelectionSource(row["selection_source"])
        ),
        source_state=SourceState(row["source_state"]),
        value=row["value"],
        lower=row["lower"],
        upper=row["upper"],
        exact_value=_fraction(row["exact_value"]),
        exact_interval=_interval(row["exact_lower"], row["exact_upper"]),
    )


def trace_of(row: Row, operands: Sequence[TraceOperand]) -> CalculationTrace:
    """One trace row and its operand rows as a model."""
    return CalculationTrace(
        trace_kind=TraceKind(row["trace_kind"]),
        formula_id=row["formula_id"],
        formula_version=row["formula_version"],
        formula_tier=None if row["formula_tier"] is None else EvidenceTier(row["formula_tier"]),
        formula_qualification_ref=row["formula_qualification_ref"],
        rounding_policy_id=row["rounding_policy_id"],
        key_digest=row["key_digest"],
        value_identity=ValueIdentity(row["value_identity"]),
        operands=tuple(operands),
        state=CalculationState(row["state"]),
        value=row["value"],
        lower=row["lower"],
        upper=row["upper"],
        exact_value=_fraction(row["exact_value"]),
        exact_interval=_interval(row["exact_lower"], row["exact_upper"]),
        effective_tier=EvidenceTier(row["effective_tier"]),
    )


def trace_from_json(payload: Mapping[str, Any]) -> CalculationTrace:
    """A trace from its ``model_dump(mode="json")`` form: rationals back from ``p/q`` text."""

    def exact(item: Mapping[str, Any]) -> dict[str, Any]:
        interval = item["exact_interval"]
        return {
            **item,
            "exact_value": _fraction(item["exact_value"]),
            "exact_interval": None if interval is None else _interval(**interval),
        }

    return CalculationTrace.model_validate(
        {**exact(payload), "operands": [exact(operand) for operand in payload["operands"]]}
    )


def proof_params(proof: AlignmentProof) -> tuple[object, ...]:
    """Column values of one proof row, in ``_PROOF_COLUMNS`` order."""
    return (
        proof.package_id,
        proof.key.digest(),
        proof.key.canonical_id,
        proof.rule_id,
        proof.rule_set_version,
        proof.xbrl_interpretation_id,
        proof.pdf_interpretation_id,
        proof.participants_digest(),
        proof.holds,
    )


def proof_of(row: Row, key: MeasurementKey) -> AlignmentProof:
    """One proof row with its participants, keyed by its XBRL target's measurement key."""
    if key.digest() != row["key_digest"]:
        raise ProvenanceMismatchError(
            _DIGEST_DRIFT.format(what="proof key", stored=row["key_digest"], expected=key.digest())
        )
    proof = AlignmentProof(
        proof_id=row["id"],
        package_id=row["package_id"],
        key=key,
        rule_id=row["rule_id"],
        rule_set_version=row["rule_set_version"],
        xbrl_interpretation_id=row["xbrl_interpretation_id"],
        pdf_interpretation_id=row["pdf_interpretation_id"],
        participants=tuple(
            (int(item_id), Representation(rep))
            for item_id, rep in zip(row["ids"], row["reps"], strict=True)
        ),
        holds=row["holds"],
    )
    if proof.participants_digest() != row["participants_digest"]:
        raise ProvenanceMismatchError(
            _DIGEST_DRIFT.format(
                what="participants digest",
                stored=row["participants_digest"],
                expected=proof.participants_digest(),
            )
        )
    return proof


def check_trace_digest(stored: CalculationTrace, expected: str) -> None:
    """Refuse a trace whose re-read content does not hash to its stored identity."""
    actual = stored.content_sha256()
    if actual != expected:
        raise ProvenanceMismatchError(
            _DIGEST_DRIFT.format(what="trace content", stored=actual, expected=expected)
        )
