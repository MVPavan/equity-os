"""Public native construction reattests every supplied reading."""

from __future__ import annotations

from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from evidence_support import dictionary, policy
from test_native_construction import NOW, SCHEMA, _native_mapping, _occurrence
from test_native_construction_store import _qualification, _run, _scope

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.evidence import InterpretationReason
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import DimensionSet, PeriodInterval
from fundamentals.evidence.mapping import (
    ConstructionRule,
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
)
from fundamentals.evidence.native_construction import (
    NativeConstructionDefect,
    NativeConstructionError,
    NativeOperandReading,
    construct_native,
    read_native_operand,
)

__all__ = ["dictionary", "policy"]


def _native_readings(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> tuple[MappingSet, Any, ConstructionRule, dict[str, tuple[NativeOperandReading, ...]]]:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    occurrences = (
        _occurrence(1, "Borrowings", "10.25"),
        _occurrence(2, "Other Liabilities", "20.50"),
    )
    direct = _run(occurrences, scope=scope)[:2]
    rule = mappings.constructions[0]
    readings = {
        operand.name: (
            read_native_operand(
                occurrence,
                interpreted,
                operand=operand,
                rule=rule,
                scope=scope,
            ),
        )
        for operand, occurrence, interpreted in zip(rule.operands, occurrences, direct, strict=True)
    }
    return mappings, scope, rule, readings


def _construct(
    rule: ConstructionRule,
    scope: Any,
    readings: dict[str, tuple[NativeOperandReading, ...]],
) -> tuple[Any, ...]:
    return construct_native(
        rule,
        readings,
        scope=scope,
        qualification_for=lambda period, dimensions: _qualification(period, scope),
        recorded_at=NOW,
    )


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("amount", Fraction(999_000_000)),
        ("interval", Interval.exact(Fraction(999_000_000))),
        ("period", PeriodInterval.at(date(2027, 3, 31))),
        ("dimensions", DimensionSet.of({"invented_axis": "invented_member"})),
    ],
)
def test_construct_refuses_forged_derived_reading_fields(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    field: str,
    forged: object,
) -> None:
    _, scope, rule, readings = _native_readings(tmp_path, dictionary, policy)
    original = readings["borrowings"][0]
    payload = {name: getattr(original, name) for name in NativeOperandReading.model_fields}
    payload[field] = forged
    replacement = NativeOperandReading.model_validate(payload)
    supplied = {**readings, "borrowings": (replacement,)}

    with pytest.raises(NativeConstructionError) as caught:
        _construct(rule, scope, supplied)
    assert caught.value.defect is NativeConstructionDefect.NATIVE_METADATA_INVALID


def test_construct_refuses_reading_from_same_selector_rule_with_another_sign(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> None:
    _, scope, rule, readings = _native_readings(tmp_path, dictionary, policy)
    changed = rule.model_dump(mode="json", exclude_none=True)
    changed["rule_id"] = "screener.liabilities_incl_nci.negative_borrowings"
    changed["operands"][0]["native"]["sign"] = -1
    opposite_sign_rule = ConstructionRule.model_validate(changed)

    with pytest.raises(NativeConstructionError) as caught:
        _construct(opposite_sign_rule, scope, readings)
    assert caught.value.defect is NativeConstructionDefect.NATIVE_METADATA_INVALID


def test_construct_refuses_a_false_collision_from_a_nonmatching_selector(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> None:
    _, scope, rule, readings = _native_readings(tmp_path, dictionary, policy)
    first = readings["borrowings"][0]
    payload = {name: getattr(first, name) for name in NativeOperandReading.model_fields}
    payload["operand_name"] = "other_liabilities"
    false_alias = NativeOperandReading.model_validate(payload)

    with pytest.raises(NativeConstructionError) as caught:
        _construct(
            rule,
            scope,
            {"borrowings": (first,), "other_liabilities": (false_alias,)},
        )
    assert caught.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_construct_preserves_a_collision_that_genuinely_matches_both_selectors(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> None:
    root = tmp_path / "mappings"
    _native_mapping(root, dictionary)
    path = root / "constructions.yaml"
    document = yaml.safe_load(path.read_text())
    operands = document["constructions"][0]["operands"]
    operands[0]["native"]["selector"] = {
        "native_field": "Borrowings",
        "period_shape": "INSTANT",
    }
    operands[1]["native"]["selector"] = {
        "statement_family": "BALANCE_SHEET",
        "labels": ["Borrowings"],
        "section_equals": "balance-sheet",
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    mappings = load_mapping_set(root, "native-v2", dictionary=dictionary)
    occurrence = _occurrence(1, "Borrowings", "10.25")
    occurrence = occurrence.model_copy(
        update={
            "native_context": {
                **occurrence.native_context,
                "local_name": "Borrowings",
                "namespace_uri": SCHEMA,
            }
        }
    )

    rows = _run([occurrence], scope=_scope(mappings, dictionary, policy))
    assert len(rows) == 2
    constructed = rows[-1]
    assert constructed.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert constructed.operand_interpretation_ids == (100,)
