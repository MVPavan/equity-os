"""VENDOR-1 P1 review finding 4: an admission's second witness is held like its first.

Why: a vendors-agree admission rests on two witnesses, so a report citing the fact, or a
calculation over it however deeply nested, must keep both captures. The purge hold graph and the
capture walk (``row_captures``) are separate consumers; each must reach the witness.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from ledger_support import ledger
from memory_support import memory
from pg_evidence_schema_support import _insert, runtime, seeded
from retention_support import facts_of, later, verdict
from test_retention_holds import VERSION, World, world

from equity_os.contracts.publication.ledger import Citation, CitationKind
from equity_os.contracts.storage.retention import EligibilityKind

pytestmark = pytest.mark.pg

__all__ = ["ledger", "memory", "runtime", "seeded", "world"]

ROW_CAPTURES = (
    "SELECT unnest(eqos.row_captures('numeric_claims', to_jsonb(k))) FROM eqos.numeric_claims k "
    "WHERE k.version_id = %s"
)
# A built case: the version citing the root, the witness capture, the write admitting the fact.
Case = tuple[int, int, Callable[[], object]]


def _admission(w: World) -> tuple[tuple[str, int], int, int, Callable[[], object]]:
    """A fact, its admitted interpretation, its witness capture and the admitting write."""
    fact, interpretation, witness = w.fact(), w.interpretation(w.capture()), w.capture()
    row = {"store_id": fact[0], "row_handle": fact[1], "fact_origin": fact[0]}
    row |= {"fact_origin_id": fact[1], "run_id": w.run, "result_id": w.result}
    row |= {
        "interpretation_id": interpretation,
        "occurrence_id": w.one(
            "SELECT occurrence_id FROM eqos.interpretations WHERE id = %s", interpretation
        ),
    }
    row |= {"overlay_position": later(), "bridge_version": "admission-bridge/1"}
    row |= {"label": "VENDORS_AGREE_NOT_CHECKED", "eligibility_version": "eligibility/1"}
    row |= {"witness_interpretation_id": w.interpretation(witness), "class_digest": "c" * 64}
    return fact, interpretation, witness, lambda: _insert(w.rt, "fact_admissions", row)


def direct_fact(w: World) -> Case:
    """A version citing the admitted fact."""
    fact, _, witness, admit = _admission(w)
    cite = Citation(kind=CitationKind.FIGURE, fact_origin=fact[0], fact_origin_id=fact[1])
    return w.draft(cite), witness, admit


def nested_calculation(w: World) -> Case:
    """A version citing only a calculation whose operand trace holds the admitted operand."""
    _, interpretation, witness, admit = _admission(w)
    inner, outer = w.trace(), w.trace()
    w.operand(inner, interpretation_id=interpretation)
    w.operand(outer, operand_trace_id=inner)
    cite = Citation(kind=CitationKind.CALCULATION, calculation_trace_id=outer)
    return w.draft(cite), witness, admit


@pytest.mark.parametrize("build", [direct_fact, nested_calculation])
def test_the_second_witness_is_held_and_walked_once_admitted(
    world: World, build: Callable[[World], Case]
) -> None:
    """Before the admission the witness is eligible and outside the claim's captures; after it,
    the citing version holds the witness and the capture walk reaches it."""
    version, witness, admit = build(world)

    def walked() -> bool:
        return witness in {row[0] for row in world.rt.execute(ROW_CAPTURES, (version,))}

    assert facts_of(world.rt, witness).holds == set() and not walked()
    assert verdict(world.rt, witness).kind is EligibilityKind.ELIGIBLE
    admit()
    held = verdict(world.rt, witness)
    assert held.kind is EligibilityKind.HELD and held.held_by == {VERSION}
    assert walked()
