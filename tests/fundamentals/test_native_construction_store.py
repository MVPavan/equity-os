"""Native construction failure states, replay determinism, and SQL persistence."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from evidence_support import dictionary, policy
from pg_evidence_schema_support import _insert
from pg_support import PgTestDatabase
from test_native_construction import (
    CAPTURE,
    NOW,
    SCHEMA,
    SOURCE,
    SURFACE,
    _native_mapping,
    _occurrence,
)

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    MissingValueState,
    Occurrence,
    PrecisionKind,
    VendorExtractorPin,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.mapping import (
    ConstructionRule,
    MappingDefect,
    MappingLoadError,
    NormalisationPolicy,
    load_mapping_set,
)
from fundamentals.evidence.native_construction import (
    NativeConstructionDefect,
    NativeConstructionError,
    construct_native,
    read_native_operand,
)
from fundamentals.evidence.repository import EvidenceRepository

__all__ = ["dictionary", "policy"]


def _pin(content: str = "3") -> VendorExtractorPin:
    return VendorExtractorPin(
        source_id=SOURCE,
        surface=SURFACE,
        version="screener-extractor-v2",
        content_sha256=content * 64,
    )


def _scope(
    mappings: Any,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    *,
    capture: Any = CAPTURE,
    basis: Basis = Basis.CONSOLIDATED,
    extractor_pin: VendorExtractorPin | None = None,
    entity_id: int = 7,
) -> CaptureScope:
    return CaptureScope(
        capture=capture,
        entity_id=entity_id,
        basis=basis,
        framework=AccountingFramework.IND_AS,
        mapping_set=mappings,
        policy=policy,
        dictionary=dictionary,
        fiscal_year_end_month=3,
        expected_extractor_pin=extractor_pin or _pin(),
    )


def _reserver(start: int = 100) -> Callable[[int], tuple[int, ...]]:
    next_id = start

    def reserve(count: int) -> tuple[int, ...]:
        nonlocal next_id
        found = tuple(range(next_id, next_id + count))
        next_id += count
        return found

    return reserve


def _run(
    occurrences: Sequence[Occurrence],
    *,
    scope: CaptureScope,
    start: int = 100,
) -> tuple[Interpretation, ...]:
    return interpret_generation(
        occurrences,
        scope=scope,
        prior=(),
        prior_anchor_keys={},
        reserve_ids=_reserver(start),
        recorded_at=NOW,
    )


@pytest.mark.parametrize(
    "missing_state",
    [
        MissingValueState.NIL,
        MissingValueState.DASH,
        MissingValueState.BLANK,
        MissingValueState.NOT_PRESENTED,
        MissingValueState.SOURCE_NULL,
    ],
)
def test_native_missing_markers_are_never_zero_filled(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    missing_state: MissingValueState,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    missing = _occurrence(2, "Other Liabilities", "-").model_copy(
        update={"missing_state": missing_state, "raw_value_text": None}
    )
    rows = _run(
        [_occurrence(1, "Borrowings", "10.25"), missing],
        scope=_scope(mappings, dictionary, policy),
    )

    (constructed,) = rows[2:]
    assert constructed.status is InterpretationStatus.MAPPED
    assert constructed.value is None and constructed.interval is None
    assert constructed.reason is None
    assert constructed.operand_interpretation_ids == (100, 101)
    assert constructed.transform_trace["missing_operands"] == ["other_liabilities"]


def test_absent_native_operand_is_missing_without_an_invented_id(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    rows = _run(
        [_occurrence(1, "Borrowings", "10.25")],
        scope=_scope(mappings, dictionary, policy),
    )

    (constructed,) = rows[1:]
    assert constructed.status is InterpretationStatus.MAPPED and constructed.value is None
    assert constructed.operand_interpretation_ids == (100,)
    assert constructed.transform_trace["missing_operands"] == ["other_liabilities"]


def test_printed_zero_is_the_only_native_zero(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    printed = _occurrence(1, "Borrowings", "0").model_copy(
        update={"missing_state": MissingValueState.ZERO_PRINTED}
    )
    rows = _run(
        [printed, _occurrence(2, "Other Liabilities", "2.50")],
        scope=_scope(mappings, dictionary, policy),
    )
    (constructed,) = rows[2:]
    assert constructed.value == 25_000_000
    assert constructed.transform_trace["operands"]["borrowings"]["candidates"][0]["amount"] == "0"


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (
            _occurrence(1, "Borrowings", "unreadable"),
            InterpretationReason.UNREADABLE_CELL,
        ),
        (
            _occurrence(1, "Borrowings", "10.25").model_copy(
                update={"precision_kind": PrecisionKind.UNSUPPORTED, "declared_precision": None}
            ),
            InterpretationReason.PRECISION_UNSUPPORTED,
        ),
        (
            _occurrence(1, "Borrowings", "10.25").model_copy(update={"raw_unit": "USD"}),
            InterpretationReason.UNIT_MISMATCH,
        ),
        (
            _occurrence(1, "Borrowings", "1").model_copy(
                update={"missing_state": MissingValueState.ZERO_PRINTED}
            ),
            InterpretationReason.UNREADABLE_CELL,
        ),
    ],
)
def test_invalid_native_value_beats_a_missing_other_operand(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    bad: Occurrence,
    reason: InterpretationReason,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    missing = _occurrence(2, "Other Liabilities", "-").model_copy(
        update={"missing_state": MissingValueState.DASH, "raw_value_text": None}
    )
    rows = _run([bad, missing], scope=_scope(mappings, dictionary, policy))

    (constructed,) = rows[2:]
    assert constructed.status is InterpretationStatus.INVALID
    assert constructed.reason is reason
    assert constructed.value is None
    assert constructed.operand_interpretation_ids == (100, 101)
    if reason is InterpretationReason.UNIT_MISMATCH:
        assert constructed.key is None


@pytest.mark.parametrize(
    ("change", "defect"),
    [
        ({"period": None}, NativeConstructionDefect.PERIOD_UNRESOLVED),
        (
            {"period": PeriodInterval.duration(date(2026, 1, 1), date(2026, 3, 31))},
            NativeConstructionDefect.PERIOD_MISMATCH,
        ),
        (
            {
                "native_context": {
                    "schema_identity": SCHEMA,
                    "basis": "CONSOLIDATED",
                    "statement_family": "BALANCE_SHEET",
                    "label": "Borrowings",
                    "section": "balance-sheet",
                    "dimensions": {"segment": "power"},
                }
            },
            NativeConstructionDefect.DIMENSION_MISMATCH,
        ),
        ({"raw_sign": 0}, NativeConstructionDefect.NATIVE_METADATA_INVALID),
        ({"raw_scale": "7"}, NativeConstructionDefect.NATIVE_METADATA_INVALID),
    ],
)
def test_unsafe_native_metadata_refuses_the_generation(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    change: dict[str, object],
    defect: NativeConstructionDefect,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    bad = _occurrence(1, "Borrowings", "10.25").model_copy(update=change)
    with pytest.raises(NativeConstructionError) as raised:
        _run(
            [bad, _occurrence(2, "Other Liabilities", "2.50")],
            scope=_scope(mappings, dictionary, policy),
        )
    assert raised.value.defect is defect


def test_duplicate_native_candidate_is_invalid_and_keeps_every_real_id(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    rows = _run(
        [
            _occurrence(1, "Borrowings", "10.25"),
            _occurrence(2, "Borrowings", "10.50"),
            _occurrence(3, "Other Liabilities", "2.50"),
        ],
        scope=_scope(mappings, dictionary, policy),
    )
    (constructed,) = rows[3:]
    assert constructed.status is InterpretationStatus.INVALID
    assert constructed.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert constructed.operand_interpretation_ids == (100, 101, 102)


def test_native_dates_form_separate_incomplete_groups(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    later = _occurrence(2, "Other Liabilities", "2.50").model_copy(
        update={"period": PeriodInterval.at(date(2026, 6, 30))}
    )
    rows = _run(
        [_occurrence(1, "Borrowings", "10.25"), later],
        scope=_scope(mappings, dictionary, policy),
    )
    constructed = rows[2:]
    assert [item.period for item in constructed] == [
        PeriodInterval.at(date(2026, 3, 31)),
        PeriodInterval.at(date(2026, 6, 30)),
    ]
    assert all(
        item.status is InterpretationStatus.MAPPED and item.value is None for item in constructed
    )


def test_nonmatching_and_inapplicable_native_rules_emit_no_aggregate(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    nonmatching = _run(
        [_occurrence(1, "Unrelated", "10")],
        scope=_scope(mappings, dictionary, policy),
    )
    standalone_context = dict(_occurrence(2, "Borrowings", "10").native_context)
    standalone_context["basis"] = Basis.STANDALONE.value
    standalone = _run(
        [
            _occurrence(2, "Borrowings", "10").model_copy(
                update={"native_context": standalone_context}
            )
        ],
        scope=_scope(mappings, dictionary, policy, basis=Basis.STANDALONE),
    )
    assert len(nonmatching) == len(standalone) == 1
    assert nonmatching[0].status is standalone[0].status is InterpretationStatus.UNMAPPED


def test_nonmatching_native_row_still_requires_generation_provenance(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    other_capture = CAPTURE.model_copy(update={"capture_ref_id": 18})
    unrelated = _occurrence(1, "Unrelated", "10").model_copy(update={"capture": other_capture})

    with pytest.raises(NativeConstructionError) as raised:
        _run([unrelated], scope=_scope(mappings, dictionary, policy))
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_native_replay_is_deterministic_and_pins_every_content_bundle(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    root = tmp_path / "mappings"
    mappings = _native_mapping(root, dictionary)
    occurrences = [
        _occurrence(1, "Borrowings", "10.25"),
        _occurrence(2, "Other Liabilities", "2.50"),
    ]
    first = _run(occurrences, scope=_scope(mappings, dictionary, policy))[-1]
    second = _run(occurrences, scope=_scope(mappings, dictionary, policy))[-1]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert json.loads(json.dumps(dict(first.transform_trace))) == first.transform_trace
    assert first.transform_trace["pins"] == {
        "dictionary": {
            "version": dictionary.version,
            "content_sha256": dictionary.content_sha256,
        },
        "mapping_set": {
            "version": mappings.version,
            "content_sha256": mappings.content_sha256,
        },
        "normalisation_policy": {
            "version": policy.version,
            "content_sha256": policy.content_sha256,
        },
        "extractor": _pin().model_dump(mode="json"),
    }

    data = yaml.safe_load((root / "constructions.yaml").read_text())
    data["constructions"][0]["operands"][0]["native"]["evidence_ref"] += " amended"
    (root / "constructions.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    amended = load_mapping_set(root, "native-v2", dictionary=dictionary)
    assert amended.content_sha256 != mappings.content_sha256

    changed_pin = _run(
        occurrences,
        scope=_scope(mappings, dictionary, policy, extractor_pin=_pin("4")),
    )[-1]
    assert changed_pin.input_digest != first.input_digest
    assert changed_pin.transform_trace["pins"]["extractor"]["content_sha256"] == "4" * 64


@pytest.mark.parametrize(
    "update",
    [
        {"occurrence_id": 999},
        {"capture_ref_id": 999},
        {"representation": Representation.JSON},
        {"origin": InterpretationOrigin.CONSTRUCTED},
        {"status": InterpretationStatus.MAPPED},
        {"mapping_entry_id": "invented"},
        {"canonical_id": "invented"},
        {"operand_interpretation_ids": (999,)},
        {"entity_id": 999},
        {"basis": Basis.STANDALONE},
        {"framework": AccountingFramework.IFRS},
        {"dictionary_version": "old"},
        {"mapping_set_version": "old"},
        {"normalisation_policy_version": "old"},
        {"extractor_version": "old"},
        {"input_digest": "old"},
    ],
)
def test_wrong_direct_identity_or_pin_is_refused(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    update: dict[str, object],
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    occurrence = _occurrence(1, "Borrowings", "10.25")
    direct = _run([occurrence], scope=scope)[0].model_copy(update=update)
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


@pytest.mark.parametrize(
    ("occurrence_update", "context_update", "pin_update"),
    [
        ({"capture": CAPTURE.model_copy(update={"source_id": "wrong"})}, {}, {}),
        ({"capture": CAPTURE.model_copy(update={"surface": "wrong"})}, {}, {}),
        ({"representation": Representation.JSON}, {}, {}),
        ({"extractor_version": "old"}, {}, {}),
        ({}, {"schema_identity": "wrong"}, {}),
        ({}, {"basis": Basis.STANDALONE.value}, {}),
        ({}, {}, {"source_id": "wrong"}),
        ({}, {}, {"surface": "wrong"}),
        ({}, {}, {"version": "old"}),
    ],
)
def test_wrong_occurrence_scope_or_expected_pin_is_refused(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
    occurrence_update: dict[str, object],
    context_update: dict[str, object],
    pin_update: dict[str, object],
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy)
    original = _occurrence(1, "Borrowings", "10.25")
    direct = _run([original], scope=scope)[0]
    context = {**original.native_context, **context_update}
    occurrence = original.model_copy(update={**occurrence_update, "native_context": context})
    checked_scope = scope.model_copy(
        update={"expected_extractor_pin": _pin().model_copy(update=pin_update)}
    )
    rule = mappings.constructions[0]

    with pytest.raises(NativeConstructionError) as raised:
        read_native_operand(
            occurrence,
            direct,
            operand=rule.operands[0],
            rule=rule,
            scope=checked_scope,
        )
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_native_generation_requires_distinct_direct_ids(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)

    with pytest.raises(NativeConstructionError) as raised:
        interpret_generation(
            [
                _occurrence(1, "Borrowings", "10.25"),
                _occurrence(2, "Other Liabilities", "2.50"),
            ],
            scope=_scope(mappings, dictionary, policy),
            prior=(),
            prior_anchor_keys={},
            reserve_ids=lambda count: (100,) * count,
            recorded_at=NOW,
        )
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_native_generation_requires_expected_extractor_pin(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    scope = _scope(mappings, dictionary, policy).model_copy(update={"expected_extractor_pin": None})

    with pytest.raises(NativeConstructionError) as raised:
        _run([_occurrence(1, "Borrowings", "10.25")], scope=scope)
    assert raised.value.defect is NativeConstructionDefect.PROVENANCE_MISMATCH


def test_runtime_selector_collision_is_invalid_and_links_the_row_once(
    tmp_path: Path, dictionary: CanonicalDictionary, policy: NormalisationPolicy
) -> None:
    root = tmp_path / "mappings"
    original = _native_mapping(root, dictionary).constructions[0]
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
    scope = _scope(mappings, dictionary, policy)
    occurrence = _occurrence(1, "Borrowings", "10.25")
    occurrence = occurrence.model_copy(
        update={
            "native_context": {
                **occurrence.native_context,
                "local_name": "Borrowings",
                "namespace_uri": original.schema_identity,
            }
        }
    )
    direct = _run([occurrence], scope=scope)[0]
    original = mappings.constructions[0]
    reading = read_native_operand(
        occurrence,
        direct,
        operand=original.operands[0],
        rule=original,
        scope=scope,
    )
    second = read_native_operand(
        occurrence,
        direct,
        operand=original.operands[1],
        rule=original,
        scope=scope,
    )
    (constructed,) = construct_native(
        original,
        {"borrowings": (reading,), "other_liabilities": (second,)},
        scope=scope,
        qualification_for=lambda period, dimensions: _qualification(period, scope),
        recorded_at=NOW,
    )
    assert constructed.status is InterpretationStatus.INVALID
    assert constructed.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert constructed.operand_interpretation_ids == (100,)


def _qualification(period: PeriodInterval, scope: CaptureScope) -> Any:
    from fundamentals.contracts.qualification import QualificationContext

    return QualificationContext(
        schema_identity=SCHEMA,
        surface=SURFACE,
        basis=scope.basis,
        period_kind=period.kind(3),
        proven={},
    )


@pytest.mark.pg
def test_native_construction_round_trips_relational_unmapped_operands(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    policy: NormalisationPolicy,
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    with pg_db.migrator_connection() as conn:
        evidence = _insert(
            conn,
            "evidence_inputs",
            {"kind": "ISSUER_IDENTITY", "label": "native test", "content_sha256": "a" * 64},
        )
        entity_id = _insert(
            conn,
            "reporting_entities",
            {
                "entity_key": "NATIVE-TEST",
                "market": "IN",
                "display_name": "Native test entity",
                "evidence_input_id": evidence,
            },
        )
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        clock = repository.store_clock()
        capture = repository.put_capture_ref(
            CAPTURE.model_copy(
                update={
                    "capture_ref_id": None,
                    "registered_at": clock,
                    "first_seen_at": clock,
                }
            )
        )
        occurrences = repository.put_occurrences(
            tuple(
                _occurrence(index, label, value).model_copy(
                    update={
                        "occurrence_id": None,
                        "capture": capture,
                        "knowledge_time": clock,
                        "first_seen_at": clock,
                    }
                )
                for index, label, value in (
                    (1, "Borrowings", "10.25"),
                    (2, "Other Liabilities", "2.50"),
                )
            )
        )
        scope = _scope(
            mappings,
            dictionary,
            policy,
            capture=capture,
            entity_id=entity_id,
        )
        generated = interpret_generation(
            occurrences,
            scope=scope,
            prior=(),
            prior_anchor_keys={},
            reserve_ids=repository.reserve_interpretation_ids,
            recorded_at=repository.store_clock(),
        )
        repository.put_interpretations(generated)
        ids = tuple(item.interpretation_id for item in generated)
        assert all(item is not None for item in ids)
        saved = repository.get_interpretations(tuple(int(item) for item in ids))
        assert saved == generated
        direct = saved[:2]
        constructed = saved[2]
        assert all(
            item.origin is InterpretationOrigin.DIRECT
            and item.status is InterpretationStatus.UNMAPPED
            and item.canonical_id is None
            for item in direct
        )
        assert constructed.operand_interpretation_ids == tuple(
            item.interpretation_id for item in direct
        )
        assert constructed.transform_trace["pins"]["extractor"] == _pin().model_dump(mode="json")

        other_capture = repository.put_capture_ref(
            capture.model_copy(
                update={
                    "capture_ref_id": None,
                    "request_key": "other-request",
                    "capture_id": "other-capture",
                    "blob_sha256": "5" * 64,
                    "record_sha256": "6" * 64,
                }
            )
        )
        (other_occurrence,) = repository.put_occurrences(
            (
                _occurrence(3, "Borrowings", "1").model_copy(
                    update={"occurrence_id": None, "capture": other_capture}
                ),
            )
        )
        (other_direct,) = interpret_generation(
            (other_occurrence,),
            scope=_scope(
                mappings,
                dictionary,
                policy,
                capture=other_capture,
                entity_id=entity_id,
            ),
            prior=(),
            prior_anchor_keys={},
            reserve_ids=repository.reserve_interpretation_ids,
            recorded_at=repository.store_clock(),
        )[:1]
        repository.put_interpretations((other_direct,))
        bad_id = repository.reserve_interpretation_ids(1)[0]
        cross_capture = constructed.model_copy(
            update={
                "interpretation_id": bad_id,
                "input_digest": "cross-capture-native-test",
                "operand_interpretation_ids": (other_direct.interpretation_id,),
            }
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="share the capture"):
            repository.put_interpretations((cross_capture,))


def test_native_configuration_rejects_mixed_missing_and_overlapping_branches(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    mappings = _native_mapping(tmp_path / "mappings", dictionary)
    raw = mappings.constructions[0].model_dump(mode="json", exclude_none=True)
    native = raw["operands"][0]["native"]
    invalid_rules = [
        {
            **raw,
            "operands": [
                raw["operands"][0],
                {"name": "other_liabilities", "mapping_entry_id": "test.unused_assets"},
            ],
        },
        {**raw, "operands": [{"name": "borrowings"}, raw["operands"][1]]},
        {**raw, "operands": [raw["operands"][0], {"name": "other_liabilities", "native": native}]},
    ]
    for invalid in invalid_rules:
        with pytest.raises(ValueError):
            ConstructionRule.model_validate(invalid)


def test_native_loader_rejects_unit_incompatible_expression(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    root = tmp_path / "mappings"
    _native_mapping(root, dictionary)
    path = root / "constructions.yaml"
    raw = yaml.safe_load(path.read_text())
    expression = raw["constructions"][0]["expression"]
    expression["op"] = "MUL"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(MappingLoadError) as raised:
        load_mapping_set(root, "native-v2", dictionary=dictionary)
    assert raised.value.defect is MappingDefect.SCHEMA
