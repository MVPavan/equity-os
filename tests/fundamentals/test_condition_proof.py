"""Qualification conditions: the zero proof rule, and a stored proof re-proven under the run."""

from decimal import Decimal
from fractions import Fraction

import pytest
from selection_support import QUARTER, at, interpretation, key, member

from fundamentals.compare.engine_rows import with_current_proofs
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    MissingValueState,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.qualification import (
    ConditionPredicate,
    ProvenCondition,
    QualificationCondition,
)
from fundamentals.evidence.interpret import TRACE_MISSING_STATE, prove_conditions

from .compare_tables_support import side

CONDITION = QualificationCondition(
    condition_id="discontinued-zero",
    canonical_id="profit_discontinued",
    predicate=ConditionPredicate.EQUALS_ZERO,
)
OWNER = member(Representation.XBRL, 1, at(1), at(1))


def _row(
    value: str, lower: int, upper: int, *, origin: InterpretationOrigin, state: MissingValueState
) -> Interpretation:
    """A discontinued-profit interpretation with the given value, interval and provenance."""
    return interpretation(1, OWNER, measurement=key(CONDITION.canonical_id)).model_copy(
        update={
            "origin": origin,
            "value": Decimal(value),
            "interval": Interval(lower=Fraction(lower), upper=Fraction(upper)),
            "transform_trace": {TRACE_MISSING_STATE: state.value},
        }
    )


@pytest.mark.parametrize(
    ("value", "lower", "upper", "origin", "state", "holds"),
    [
        # A filed 0 at decimals=-7 reports zero despite its ±5,000,000 interval.
        (
            "0",
            -5_000_000,
            5_000_000,
            InterpretationOrigin.DIRECT,
            MissingValueState.ZERO_PRINTED,
            True,
        ),
        # A constructed zero carries no filed lexeme: its wide interval leaves it unproven.
        ("0", -1, 1, InterpretationOrigin.CONSTRUCTED, MissingValueState.VALUE, None),
        # A constructed zero whose interval is exactly [0, 0] is proven zero.
        ("0", 0, 0, InterpretationOrigin.CONSTRUCTED, MissingValueState.VALUE, True),
        # A nonzero filed value whose interval spans zero proves nothing.
        ("1", -1, 3, InterpretationOrigin.DIRECT, MissingValueState.VALUE, None),
        # An interval excluding zero proves nonzero, so EQUALS_ZERO fails.
        ("5", 4, 6, InterpretationOrigin.DIRECT, MissingValueState.VALUE, False),
    ],
)
def test_zero_proof_needs_a_filed_zero_or_an_interval_excluding_zero(
    value: str,
    lower: int,
    upper: int,
    origin: InterpretationOrigin,
    state: MissingValueState,
    holds: bool | None,
) -> None:
    """Spec §4 zero exception: a reported 0 lexeme, never a constructed or nonzero value."""
    row = _row(value, lower, upper, origin=origin, state=state)
    proofs = prove_conditions(
        (CONDITION,), interpretations=[row], period=QUARTER, basis=Basis.CONSOLIDATED
    )
    proof = proofs.get(CONDITION.condition_id)
    assert (None if proof is None else proof.holds) is holds


STORED = ProvenCondition(
    condition_id=CONDITION.condition_id, holds=True, evidence_interpretation_ids=(1,)
)


@pytest.mark.parametrize(
    ("current", "aligned", "tier", "evidence"),
    [
        # Re-proven the same way from the current selection (a newer interpretation id).
        ({"holds": True, "ids": (2,)}, False, EvidenceTier.EQUIVALENCE_DEMONSTRATED, (2,)),
        # The current selection proves it false, or proves nothing: qualification withheld.
        ({"holds": False, "ids": (2,)}, False, EvidenceTier.EQUIVALENCE_UNPROVEN, None),
        (None, False, EvidenceTier.EQUIVALENCE_UNPROVEN, None),
        # An alignment proof is its own demonstration; only the stale proofs are dropped.
        (None, True, EvidenceTier.EQUIVALENCE_DEMONSTRATED, None),
    ],
)
def test_a_stored_proof_counts_only_if_the_run_reproves_it(
    current: dict[str, object] | None,
    aligned: bool,
    tier: EvidenceTier,
    evidence: tuple[int, ...] | None,
) -> None:
    """Spec §2: a superseded condition proof never keeps a side qualified."""
    filed = side("90.61", aligned=aligned).model_copy(update={"condition_evidence": (STORED,)})
    proven = (
        {}
        if current is None
        else {
            STORED.condition_id: STORED.model_copy(
                update={
                    "holds": current["holds"],
                    "evidence_interpretation_ids": current["ids"],
                }
            )
        }
    )
    checked = with_current_proofs(filed, proven)
    assert checked.tier is tier
    assert [proof.evidence_interpretation_ids for proof in checked.condition_evidence] == (
        [] if evidence is None else [evidence]
    )
