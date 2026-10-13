"""R1 regressions for the reviewed source-native construction contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from evidence_support import dictionary, policy
from pydantic import ValidationError
from test_native_construction import _native_mapping, _occurrence
from test_native_construction_store import _qualification, _run, _scope

from fundamentals.canon.dictionary import CanonicalDictionary, FormulaNode
from fundamentals.contracts.canonical import (
    Basis,
    PeriodKind,
    PeriodNature,
    Representation,
    ValueKind,
)
from fundamentals.contracts.evidence import (
    InterpretationReason,
    InterpretationStatus,
    MissingValueState,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.capture_interpretation import CaptureScope
from fundamentals.evidence.interpret import interpret
from fundamentals.evidence.mapping import (
    ConstructionRule,
    MappingLoadError,
    MappingSet,
    NormalisationPolicy,
    Selector,
    UnitRule,
    load_mapping_set,
)
from fundamentals.evidence.native_construction import (
    NativeConstructionDefect,
    NativeConstructionError,
    NativeOperandReading,
    NativeReadingState,
    construct_native,
    read_native_operand,
)

__all__ = ["dictionary", "policy"]


def _rewrite_mapping(
    root: Path,
    dictionary: CanonicalDictionary,
    mutate: Callable[[dict[str, Any]], None],
) -> MappingSet:
    _native_mapping(root, dictionary)
    path = root / "constructions.yaml"
    document = yaml.safe_load(path.read_text())
    mutate(document["constructions"][0])
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    return load_mapping_set(root, "native-v2", dictionary=dictionary)


def _rule_payload(tmp_path: Path, dictionary: CanonicalDictionary) -> dict[str, Any]:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    return mappings.constructions[0].model_dump(mode="json", exclude_none=True)


def _readings(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> tuple[ConstructionRule, CaptureScope, Mapping[str, tuple[NativeOperandReading, ...]]]:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    occurrences = [
        _occurrence(1, "Borrowings", "10.25"),
        _occurrence(2, "Other Liabilities", "20.50"),
    ]
    rows = _run(occurrences, scope=scope)
    rule = mappings.constructions[0]
    readings = {
        operand.name: (
            read_native_operand(
                occurrence,
                direct,
                operand=operand,
                rule=rule,
                scope=scope,
            ),
        )
        for operand, occurrence, direct in zip(rule.operands, occurrences, rows[:2], strict=True)
    }
    return rule, scope, readings


def _construct(
    rule: ConstructionRule,
    scope: CaptureScope,
    readings: Mapping[str, tuple[NativeOperandReading, ...]],
) -> tuple[Any, ...]:
    return construct_native(
        rule,
        readings,
        scope=scope,
        qualification_for=lambda period, dimensions: _qualification(period, scope),
        recorded_at=scope.capture.registered_at,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"native_field": "", "period_shape": "INSTANT"},
        {"native_field": "   ", "period_shape": "INSTANT"},
        {"statement_family": "BALANCE_SHEET", "labels": ["   "]},
        {
            "statement_family": "BALANCE_SHEET",
            "labels": ["Borrowings"],
            "section_equals": "   ",
        },
    ],
)
def test_blank_native_selector_evidence_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Selector.model_validate(payload)


def test_native_dimension_members_are_immutable_and_serialize_stably(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    rule = _native_mapping(tmp_path / "mappings", dictionary).constructions[0]
    spec = rule.operands[0].native
    assert spec is not None
    before = spec.model_dump(mode="json")
    with pytest.raises(TypeError):
        spec.dimension_members["invented_axis"] = "invented_member"  # type: ignore[index]
    assert spec.model_dump(mode="json") == before


@pytest.mark.parametrize(
    ("amount", "interval"),
    [(Fraction(1), None), (None, Interval.exact(Fraction(1)))],
)
def test_nonvalue_native_reading_rejects_half_populated_amounts(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    amount: Fraction | None,
    interval: Interval | None,
) -> None:
    rule, scope, readings = _readings(tmp_path, dictionary, policy)
    del rule, scope
    valid = readings["borrowings"][0]
    payload = valid.model_dump()
    payload.update(
        state=NativeReadingState.INVALID,
        amount=amount,
        interval=interval,
        reason=InterpretationReason.UNIT_MISMATCH,
    )
    with pytest.raises(ValidationError):
        NativeOperandReading.model_validate(payload)


def test_public_native_read_refuses_an_occurrence_for_another_selector(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    occurrence = _occurrence(1, "Other Liabilities", "20.50")
    direct = _run([occurrence], scope=scope)[0]
    rule = mappings.constructions[0]

    with pytest.raises(NativeConstructionError) as raised:
        read_native_operand(
            occurrence,
            direct,
            operand=rule.operands[0],
            rule=rule,
            scope=scope,
        )
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_public_native_construct_refuses_a_swapped_reading(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    rule, scope, readings = _readings(tmp_path, dictionary, policy)
    swapped = readings["borrowings"][0].model_copy(update={"operand_name": "other_liabilities"})

    with pytest.raises(NativeConstructionError) as raised:
        _construct(rule, scope, {"other_liabilities": (swapped,)})
    assert raised.value.defect is NativeConstructionDefect.NATIVE_METADATA_INVALID


def test_native_candidates_from_two_representations_are_refused(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    json_operand = _occurrence(2, "Other Liabilities", "20.50").model_copy(
        update={"representation": Representation.JSON}
    )

    with pytest.raises(NativeConstructionError) as raised:
        _run(
            [_occurrence(1, "Borrowings", "10.25"), json_operand],
            scope=_scope(mappings, dictionary, policy),
        )
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


@pytest.mark.parametrize(
    ("tier", "qualification"),
    [
        (EvidenceTier.RELATED_NOT_EQUIVALENT.value, None),
        (EvidenceTier.EQUIVALENCE_DEMONSTRATED.value, None),
    ],
)
def test_native_rule_rejects_unqualified_authority_tiers(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    tier: str,
    qualification: object,
) -> None:
    raw = _rule_payload(tmp_path, dictionary)
    raw.update(tier=tier, qualification=qualification)
    with pytest.raises(ValidationError):
        ConstructionRule.model_validate(raw)


def test_programmatic_related_native_rule_is_clamped_to_unproven(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    rule, scope, readings = _readings(tmp_path, dictionary, policy)
    related = rule.model_copy(update={"tier": EvidenceTier.RELATED_NOT_EQUIVALENT})
    (constructed,) = _construct(related, scope, readings)
    assert constructed.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert constructed.qualification_ref is None


@pytest.mark.parametrize("scope_kind", ["basis", "period"])
def test_native_rule_requires_a_nonempty_common_operand_scope(
    tmp_path: Path, dictionary: CanonicalDictionary, scope_kind: str
) -> None:
    raw = _rule_payload(tmp_path, dictionary)
    if scope_kind == "basis":
        raw["operands"][0]["native"]["bases"] = [Basis.CONSOLIDATED.value]
        raw["operands"][1]["native"]["bases"] = [Basis.STANDALONE.value]
    else:
        for operand in raw["operands"]:
            operand["native"]["period_nature"] = PeriodNature.DURATION.value
        raw["operands"][0]["native"]["period_kinds"] = [PeriodKind.QUARTER.value]
        raw["operands"][1]["native"]["period_kinds"] = [PeriodKind.YEAR.value]
    with pytest.raises(ValidationError):
        ConstructionRule.model_validate(raw)


@pytest.mark.parametrize(
    "members",
    [
        {"wrong_axis": "power", "elimination_basis": "PRE_ELIMINATION"},
        {"segment": "power"},
        {
            "segment": "power",
            "elimination_basis": "PRE_ELIMINATION",
            "extra_axis": "extra",
        },
        {"segment": "power", "elimination_basis": "NOT_DECLARED"},
    ],
)
def test_native_loader_rejects_incompatible_target_dimensions(
    tmp_path: Path, dictionary: CanonicalDictionary, members: dict[str, str]
) -> None:
    def mutate(rule: dict[str, Any]) -> None:
        rule["canonical_id"] = "segment_assets"
        for operand in rule["operands"]:
            operand["native"]["dimension_members"] = members

    with pytest.raises(MappingLoadError):
        _rewrite_mapping(tmp_path / "mappings", dictionary, mutate)


def test_programmatic_native_rule_rechecks_target_dimensions(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    raw = mappings.constructions[0].model_dump(mode="json", exclude_none=True)
    raw["canonical_id"] = "segment_assets"
    for operand in raw["operands"]:
        operand["native"]["dimension_members"] = {
            "segment": "power",
            "elimination_basis": "NOT_DECLARED",
        }
    rule = ConstructionRule.model_validate(raw)
    occurrence = _occurrence(1, "Borrowings", "10.25").model_copy(
        update={
            "native_context": {
                **_occurrence(1, "Borrowings", "10.25").native_context,
                "dimensions": {
                    "segment": "power",
                    "elimination_basis": "NOT_DECLARED",
                },
            }
        }
    )
    direct = interpret(
        occurrence,
        entity_id=scope.entity_id,
        basis=scope.basis,
        framework=scope.framework,
        mapping_set=mappings,
        policy=scope.policy,
        dictionary=scope.dictionary,
        fiscal_year_end_month=scope.fiscal_year_end_month,
        qualification=_qualification(occurrence.period, scope),  # type: ignore[arg-type]
        recorded_at=scope.capture.registered_at,
    ).model_copy(update={"interpretation_id": 100})

    reading = read_native_operand(
        occurrence,
        direct,
        operand=rule.operands[0],
        rule=rule,
        scope=scope,
    )
    assert reading.state is NativeReadingState.INVALID
    assert reading.reason is InterpretationReason.UNIT_MISMATCH
    assert reading.amount is None and reading.interval is None


@pytest.mark.parametrize("denominator", ["3", "0"])
def test_native_loader_rejects_nonclosed_literal_division(
    tmp_path: Path, dictionary: CanonicalDictionary, denominator: str
) -> None:
    def mutate(rule: dict[str, Any]) -> None:
        rule["expression"] = {
            "op": "DIV",
            "args": [
                {
                    "op": "ADD",
                    "args": [
                        {"op": "OPERAND", "operand": "borrowings"},
                        {"op": "OPERAND", "operand": "other_liabilities"},
                    ],
                },
                {"op": "LITERAL", "value": denominator},
            ],
        }

    with pytest.raises(MappingLoadError):
        _rewrite_mapping(tmp_path / "mappings", dictionary, mutate)


def test_native_loader_rejects_variable_divisor_even_when_unit_power_is_one(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    def mutate(rule: dict[str, Any]) -> None:
        rule["expression"] = {
            "op": "DIV",
            "args": [
                {
                    "op": "MUL",
                    "args": [
                        {"op": "OPERAND", "operand": "borrowings"},
                        {"op": "OPERAND", "operand": "other_liabilities"},
                    ],
                },
                {"op": "OPERAND", "operand": "other_liabilities"},
            ],
        }

    with pytest.raises(MappingLoadError):
        _rewrite_mapping(tmp_path / "mappings", dictionary, mutate)


def test_native_literal_division_by_two_preserves_finite_precision_bounds(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    def mutate(rule: dict[str, Any]) -> None:
        rule["expression"] = {
            "op": "DIV",
            "args": [rule["expression"], {"op": "LITERAL", "value": "2"}],
        }

    mappings = _rewrite_mapping(tmp_path / "mappings", dictionary, mutate)
    rows = _run(
        [
            _occurrence(1, "Borrowings", "10.25"),
            _occurrence(2, "Other Liabilities", "20.50"),
        ],
        scope=_scope(mappings, dictionary, policy),
    )
    constructed = rows[-1]
    assert constructed.value == Fraction(153_750_000)
    assert constructed.interval == Interval(
        lower=Fraction(153_700_000), upper=Fraction(153_800_000)
    )


def test_programmatic_nondecimal_native_arithmetic_fails_closed(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    rule, scope, readings = _readings(tmp_path, dictionary, policy)
    expression = FormulaNode.model_validate(
        {
            "op": "DIV",
            "args": [rule.expression.model_dump(mode="json"), {"op": "LITERAL", "value": "7"}],
        }
    )
    unsafe = rule.model_copy(update={"expression": expression})
    with pytest.raises(NativeConstructionError) as raised:
        _construct(unsafe, scope, readings)
    assert raised.value.defect is NativeConstructionDefect.NATIVE_METADATA_INVALID


@pytest.mark.parametrize(
    ("raw_unit", "unit"),
    [
        (
            "COUNT",
            UnitRule(
                raw_unit="COUNT",
                value_kind=ValueKind.COUNT,
                currency=None,
                evidence_ref="known count unit",
            ),
        ),
        (
            "USD",
            UnitRule(
                raw_unit="USD",
                value_kind=ValueKind.CURRENCY_AMOUNT,
                currency="USD",
                evidence_ref="known USD unit",
            ),
        ),
    ],
)
def test_known_incompatible_native_unit_is_invalid_without_a_key(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    raw_unit: str,
    unit: UnitRule,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    amended_policy = policy.model_copy(update={"units": {**policy.units, raw_unit: unit}})
    bad = _occurrence(1, "Borrowings", "10.25").model_copy(update={"raw_unit": raw_unit})
    missing = _occurrence(2, "Other Liabilities", "-").model_copy(
        update={"missing_state": MissingValueState.DASH, "raw_value_text": None}
    )
    constructed = _run([bad, missing], scope=_scope(mappings, dictionary, amended_policy))[-1]
    assert constructed.status is InterpretationStatus.INVALID
    assert constructed.reason is InterpretationReason.UNIT_MISMATCH
    assert constructed.key is None and constructed.value is None


def test_native_loader_rejects_an_incompatible_target(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    def mutate(rule: dict[str, Any]) -> None:
        rule["canonical_id"] = "revenue"

    with pytest.raises(MappingLoadError):
        _rewrite_mapping(tmp_path / "mappings", dictionary, mutate)


def test_native_raw_and_spec_signs_each_participate_once(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    raw_root = tmp_path / "raw"
    raw_mappings = _native_mapping(raw_root, dictionary)
    raw_negative = _occurrence(1, "Borrowings", "10.25").model_copy(update={"raw_sign": -1})
    other = _occurrence(2, "Other Liabilities", "2.50")
    assert _run([raw_negative, other], scope=_scope(raw_mappings, dictionary, policy))[
        -1
    ].value == Fraction(-77_500_000)

    def negate_spec(rule: dict[str, Any]) -> None:
        rule["operands"][0]["native"]["sign"] = -1

    spec_mappings = _rewrite_mapping(tmp_path / "spec", dictionary, negate_spec)
    positive = _occurrence(1, "Borrowings", "10.25")
    assert _run([positive, other], scope=_scope(spec_mappings, dictionary, policy))[
        -1
    ].value == Fraction(-77_500_000)
    assert _run([raw_negative, other], scope=_scope(spec_mappings, dictionary, policy))[
        -1
    ].value == Fraction(127_500_000)


@pytest.mark.parametrize(("field", "value"), [("raw_sign", True), ("raw_scale", True)])
def test_native_boolean_numeric_metadata_is_refused(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    field: str,
    value: bool,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    malformed = _occurrence(1, "Borrowings", "10.25").model_copy(update={field: value})

    with pytest.raises(NativeConstructionError) as raised:
        _run(
            [malformed, _occurrence(2, "Other Liabilities", "20.50")],
            scope=_scope(mappings, dictionary, policy),
        )
    assert raised.value.defect is NativeConstructionDefect.NATIVE_METADATA_INVALID


def test_native_replay_is_independent_of_mapping_and_candidate_insertion_order(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    occurrences = [
        _occurrence(1, "Borrowings", "10.25"),
        _occurrence(2, "Other Liabilities", "20.50"),
        _occurrence(3, "Borrowings", "30.25").model_copy(
            update={"period": PeriodInterval.at(date(2026, 6, 30))}
        ),
        _occurrence(4, "Other Liabilities", "40.50").model_copy(
            update={"period": PeriodInterval.at(date(2026, 6, 30))}
        ),
    ]
    direct = _run(occurrences, scope=scope)[:4]
    rule = mappings.constructions[0]
    readings: dict[str, list[NativeOperandReading]] = {
        "borrowings": [],
        "other_liabilities": [],
    }
    for occurrence, interpreted in zip(occurrences, direct, strict=True):
        operand = rule.operands[0] if occurrence.native_field == "Borrowings" else rule.operands[1]
        readings[operand.name].append(
            read_native_operand(
                occurrence,
                interpreted,
                operand=operand,
                rule=rule,
                scope=scope,
            )
        )
    forward = {name: tuple(items) for name, items in readings.items()}
    reverse = {
        "other_liabilities": tuple(reversed(readings["other_liabilities"])),
        "borrowings": tuple(reversed(readings["borrowings"])),
    }
    first = _construct(rule, scope, forward)
    replay = _construct(rule, scope, reverse)
    assert [item.model_dump(mode="json") for item in replay] == [
        item.model_dump(mode="json") for item in first
    ]


def test_genuinely_qualified_native_rule_may_be_demonstrated(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    def qualify(rule: dict[str, Any]) -> None:
        rule["tier"] = EvidenceTier.EQUIVALENCE_DEMONSTRATED.value
        rule["qualification"] = {
            "scope_id": "reviewed-native-scope",
            "schema_identities": [rule["schema_identity"]],
            "surfaces": [rule["surface"]],
            "bases": [Basis.CONSOLIDATED.value],
            "period_kinds": [PeriodKind.INSTANT.value],
            "fixture_evidence": [
                {
                    "capture_id": f"capture-{index}",
                    "capture_sha256": f"{index:x}" * 64,
                    "entity_id": index,
                    "discriminating": index == 1,
                }
                for index in range(1, 6)
            ],
            "sample_rule": "five independent companies including one discriminating case",
        }

    mappings = _rewrite_mapping(tmp_path / "mappings", dictionary, qualify)
    constructed = _run(
        [
            _occurrence(1, "Borrowings", "10.25"),
            _occurrence(2, "Other Liabilities", "20.50"),
        ],
        scope=_scope(mappings, dictionary, policy),
    )[-1]
    assert constructed.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    assert constructed.qualification_ref == "reviewed-native-scope"
