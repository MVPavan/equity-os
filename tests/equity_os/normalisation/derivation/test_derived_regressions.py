"""Nested derived rows use their own measurement scope and persist constituent traces."""

from fractions import Fraction
from pathlib import Path

from selection_support import at, interpretation, key, member

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, Representation
from equity_os.contracts.measurement.evidence import KeySelection
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import DimensionSet
from equity_os.contracts.measurement.qualification import (
    QualificationContext,
    QualificationFixture,
    QualificationScope,
    scoped_tier,
)
from equity_os.contracts.verification.comparison import SelectionSource, SourceState
from equity_os.normalisation.derivation.derived import evaluate_derived
from equity_os.normalisation.derivation.formula import CalculationTrace
from equity_os.normalisation.derivation.interval import load_rounding_policy
from equity_os.normalisation.dictionary.dictionary import Formula, load_dictionary

CONFIG = Path(__file__).resolve().parents[4] / "config"


class Traces:
    def __init__(self) -> None:
        self.items: list[CalculationTrace] = []

    def put_calculation_trace(self, trace: CalculationTrace) -> int:
        self.items.append(trace)
        return len(self.items)


def context(kind: PeriodKind = PeriodKind.QUARTER) -> QualificationContext:
    return QualificationContext(
        schema_identity="schema",
        surface="surface",
        basis=Basis.CONSOLIDATED,
        period_kind=kind,
        proven={},
    )


def selected(measurement, role) -> KeySelection:
    owner = member(Representation.XBRL, 1, at(29), at(30))
    item = interpretation(1, owner, measurement=measurement).model_copy(
        update={"tier": EvidenceTier.EQUIVALENCE_DEMONSTRATED}
    )
    return KeySelection(
        key=measurement,
        representation=Representation.XBRL,
        state=SourceState.VALUE,
        interpretation=item,
        package_id=1,
        source=SelectionSource.PACKAGE_AS_REPORTED,
        reason=None,
        considered_interpretation_ids=(),
        surfaced_restatements=(),
    )


def test_nested_closing_formula_does_not_inherit_the_parent_quarter_scope() -> None:
    dictionary = load_dictionary(CONFIG / "normalisation/dictionary", "v1")
    child = dictionary.row("net_current_assets")
    scope = QualificationScope(
        scope_id="quarter-only",
        schema_identities=frozenset({"schema"}),
        surfaces=frozenset({"surface"}),
        bases=frozenset({Basis.CONSOLIDATED}),
        period_kinds=frozenset({PeriodKind.QUARTER}),
        fixture_evidence=tuple(
            QualificationFixture(
                capture_id=f"constructed-{index}",
                capture_sha256=f"{index:064x}",
                entity_id=index,
                discriminating=index == 1,
            )
            for index in range(1, 6)
        ),
        sample_rule="D3: constructed five-company sample including discriminating case",
    )
    assert scoped_tier(EvidenceTier.EQUIVALENCE_DEMONSTRATED, scope, context()).tier is (
        EvidenceTier.EQUIVALENCE_DEMONSTRATED
    )
    assert child.formula is not None
    child = child.model_copy(
        update={
            "formula": child.formula.model_copy(
                update={
                    "tier": EvidenceTier.EQUIVALENCE_DEMONSTRATED,
                    "qualification": scope,
                }
            )
        }
    )
    parent = dictionary.row("ebitda_excl_other_income").model_copy(
        update={
            "canonical_id": "closing_net_assets",
            "formula": Formula.model_validate(
                {
                    "formula_id": "closing_net_assets",
                    "version": "1",
                    "evidence": "test",
                    "output_kind": "CURRENCY_AMOUNT",
                    "operands": [
                        {
                            "name": "assets",
                            "canonical_id": child.canonical_id,
                            "temporal_role": "CLOSING",
                        }
                    ],
                    "expression": {"op": "OPERAND", "operand": "assets"},
                }
            ),
        }
    )
    dictionary = dictionary.model_copy(
        update={
            "rows": tuple(
                child if row.canonical_id == child.canonical_id else row for row in dictionary.rows
            )
            + (parent,)
        }
    )
    traces = Traces()
    evaluate_derived(
        parent,
        key(parent.canonical_id),
        representation=Representation.XBRL,
        resolve=selected,
        proofs=(),
        qualification=context(),
        policy=load_rounding_policy(CONFIG / "normalisation/rounding_policy" / "v1.yaml"),
        repository=traces,
        dictionary=dictionary,
        reporting_currency="INR",
    )
    assert traces.items[0].formula_tier is EvidenceTier.EQUIVALENCE_UNPROVEN


def test_aggregate_evaluates_derived_segment_constituents_before_summing() -> None:
    dictionary = load_dictionary(CONFIG / "normalisation/dictionary", "v1")
    parent = dictionary.row("segment_capital_employed").model_copy(
        update={
            "canonical_id": "segment_capital_total",
            "formula": Formula.model_validate(
                {
                    "formula_id": "segment_capital_total",
                    "version": "1",
                    "evidence": "test",
                    "output_kind": "CURRENCY_AMOUNT",
                    "operands": [
                        {
                            "name": "capital",
                            "canonical_id": "segment_capital_employed",
                            "temporal_role": "CLOSING",
                            "aggregation": {
                                "axis": "segment",
                                "member_binding": "DECLARED",
                                "input_members": ["a", "b"],
                                "output_member": "reportable_segments_total",
                            },
                        }
                    ],
                    "expression": {"op": "OPERAND", "operand": "capital"},
                }
            ),
        }
    )
    dictionary = dictionary.model_copy(update={"rows": dictionary.rows + (parent,)})
    output = key(parent.canonical_id).model_copy(
        update={
            "dimensions": DimensionSet.of(
                {
                    "segment": "reportable_segments_total",
                    "elimination_basis": "PRE_ELIMINATION",
                }
            )
        }
    )

    def resolve(measurement, role):
        item = selected(measurement, role)
        if measurement.canonical_id == "segment_capital_employed":
            return item.model_copy(update={"state": SourceState.NO_VALUE, "interpretation": None})
        crore = "20" if measurement.canonical_id == "segment_assets" else "5"
        chosen = interpretation(
            1, member(Representation.XBRL, 1, at(29), at(30)), measurement=measurement, crore=crore
        )
        return item.model_copy(update={"interpretation": chosen})

    traces = Traces()
    side = evaluate_derived(
        parent,
        output,
        representation=Representation.XBRL,
        resolve=resolve,
        proofs=(),
        qualification=context(),
        policy=load_rounding_policy(CONFIG / "normalisation/rounding_policy" / "v1.yaml"),
        repository=traces,
        dictionary=dictionary,
        reporting_currency="INR",
    )
    assert side.result.exact == Fraction(300000000)
    assert len(traces.items) == 4  # two member formulas, aggregate, parent
    assert {item.operand_trace_id for item in traces.items[2].operands} == {1, 2}
    assert traces.items[3].operands[0].operand_trace_id == 3


def test_average_evaluates_both_derived_instant_constituents() -> None:
    dictionary = load_dictionary(CONFIG / "normalisation/dictionary", "v1")
    parent = dictionary.row("ebitda_excl_other_income").model_copy(
        update={
            "canonical_id": "average_net_assets",
            "formula": Formula.model_validate(
                {
                    "formula_id": "average_net_assets",
                    "version": "1",
                    "evidence": "test",
                    "output_kind": "CURRENCY_AMOUNT",
                    "operands": [
                        {
                            "name": "assets",
                            "canonical_id": "net_current_assets",
                            "temporal_role": "AVERAGE",
                        }
                    ],
                    "expression": {"op": "OPERAND", "operand": "assets"},
                }
            ),
        }
    )
    dictionary = dictionary.model_copy(update={"rows": dictionary.rows + (parent,)})

    def resolve(measurement, role):
        item = selected(measurement, role)
        if measurement.canonical_id == "net_current_assets":
            return item.model_copy(update={"state": SourceState.NO_VALUE, "interpretation": None})
        crore = "20" if measurement.canonical_id == "current_assets_total" else "5"
        chosen = interpretation(
            1, member(Representation.XBRL, 1, at(29), at(30)), measurement=measurement, crore=crore
        )
        return item.model_copy(update={"interpretation": chosen})

    traces = Traces()
    seen = []

    def qualification_for(row, measurement):
        seen.append((row.canonical_id, measurement.period))
        return context(measurement.period.kind(3))

    side = evaluate_derived(
        parent,
        key(parent.canonical_id),
        representation=Representation.XBRL,
        resolve=resolve,
        proofs=(),
        qualification=context(),
        qualification_for=qualification_for,
        policy=load_rounding_policy(CONFIG / "normalisation/rounding_policy" / "v1.yaml"),
        repository=traces,
        dictionary=dictionary,
        reporting_currency="INR",
    )
    assert side.result.exact == Fraction(150000000)
    assert len(traces.items) == 4
    assert [row_id for row_id, _ in seen] == [
        "net_current_assets",
        "net_current_assets",
        "average_net_assets",
    ]
    assert seen[0][1].instant.isoformat() == "2025-06-30"
    assert seen[1][1].instant.isoformat() == "2025-09-30"
    assert {item.operand_trace_id for item in traces.items[2].operands} == {1, 2}
