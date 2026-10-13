"""Read source-native operands and build one evidenced canonical aggregate."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from fundamentals.canon.formula import _evaluate
from fundamentals.contracts.canonical import PeriodNature, ValueKind
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    MissingValueState,
    Occurrence,
    ReadOnlyJson,
    RevisionCause,
    exact_decimal,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval, UndefinedDivisionError
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.qualification import QualificationContext, scoped_tier
from fundamentals.evidence.interpret import (
    TRACE_MISSING_STATE,
    TRACE_REASON,
    input_digest,
    normalise_occurrence_value,
)
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_LOCAL_NAME,
    CONTEXT_NAMESPACE,
    CONTEXT_SCHEMA_IDENTITY,
    ConstructionOperand,
    ConstructionRule,
    PeriodShape,
    in_namespace,
    matches_dimensions,
    native_dimensions_compatible,
)
from fundamentals.evidence.mapping_models import selector_matches

if TYPE_CHECKING:
    from fundamentals.evidence.capture_interpretation import CaptureScope


class NativeConstructionDefect(StrEnum):
    """A generation-level defect that refuses every native construction write."""

    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    PERIOD_UNRESOLVED = "PERIOD_UNRESOLVED"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    NATIVE_METADATA_INVALID = "NATIVE_METADATA_INVALID"


class NativeConstructionError(ValueError):
    """Native evidence is unsafe to read; the generation must not be committed."""

    def __init__(self, defect: NativeConstructionDefect, detail: str) -> None:
        self.defect = defect
        super().__init__(f"native construction failed: {defect.value}: {detail}")


class NativeReadingState(StrEnum):
    """Whether a matched source-native cell supplies a usable amount."""

    VALUE = "VALUE"
    MISSING = "MISSING"
    INVALID = "INVALID"


class NativeOperandReading(BaseModel):
    """A typed in-memory reading that keeps its raw and relational evidence separate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operand_name: str
    occurrence: Occurrence
    direct_interpretation: Interpretation
    state: NativeReadingState
    amount: Fraction | None
    interval: Interval | None
    value_kind: ValueKind | None
    currency: str | None
    period: PeriodInterval | None
    dimensions: DimensionSet | None
    reason: InterpretationReason | None
    trace: ReadOnlyJson

    @model_validator(mode="after")
    def _state_shape(self) -> NativeOperandReading:
        if self.state is NativeReadingState.VALUE and (
            self.amount is None or self.interval is None
        ):
            raise ValueError("a VALUE native reading requires amount and interval")
        if self.state is not NativeReadingState.VALUE and (
            self.amount is not None or self.interval is not None
        ):
            raise ValueError("a non-VALUE native reading carries no amount or interval")
        if self.state is NativeReadingState.VALUE and (
            self.value_kind is None or self.period is None or self.dimensions is None
        ):
            raise ValueError("a VALUE native reading has a complete typed group")
        if self.state is not NativeReadingState.INVALID and self.reason is not None:
            raise ValueError("only an INVALID native reading carries a reason")
        return self


def native_selector_matches(occurrence: Occurrence, operand: ConstructionOperand) -> bool:
    """Whether an occurrence matches a native operand's exact selector."""
    spec = operand.native
    if spec is None:
        return False
    selector = spec.selector
    context = occurrence.native_context
    if selector.native_field is None:
        return selector_matches(selector, context)
    if (
        context.get(CONTEXT_LOCAL_NAME) != selector.native_field
        or not in_namespace(context, str(context.get(CONTEXT_SCHEMA_IDENTITY, "")))
        or occurrence.period is None
    ):
        return False
    is_instant = occurrence.period.instant is not None
    return is_instant == (selector.period_shape is PeriodShape.INSTANT) and matches_dimensions(
        context,
        str(context.get(CONTEXT_NAMESPACE, "")),
        selector.dimension_axis,
    )


def read_native_operand(
    occurrence: Occurrence,
    direct: Interpretation,
    *,
    operand: ConstructionOperand,
    rule: ConstructionRule,
    scope: CaptureScope,
) -> NativeOperandReading:
    """Read one exact current ``UNMAPPED`` direct row under its pinned native metadata."""
    spec = operand.native
    if spec is None:
        raise NativeConstructionError(
            NativeConstructionDefect.NATIVE_METADATA_INVALID, "operand is not native"
        )
    if not native_selector_matches(occurrence, operand):
        raise NativeConstructionError(
            NativeConstructionDefect.PROVENANCE_MISMATCH,
            f"occurrence {occurrence.occurrence_id!r} does not match operand {operand.name!r}",
        )
    validate_native_provenance(occurrence, direct, rule=rule, scope=scope)
    if scope.basis not in spec.bases:
        raise NativeConstructionError(
            NativeConstructionDefect.PROVENANCE_MISMATCH, "capture basis is outside operand scope"
        )
    period = occurrence.period
    if period is None:
        raise NativeConstructionError(
            NativeConstructionDefect.PERIOD_UNRESOLVED, "matched native row has no period"
        )
    period_kind = period.kind(scope.fiscal_year_end_month)
    actual_nature = PeriodNature.INSTANT if period.instant is not None else PeriodNature.DURATION
    if actual_nature is not spec.period_nature or period_kind not in spec.period_kinds:
        raise NativeConstructionError(
            NativeConstructionDefect.PERIOD_MISMATCH,
            f"{operand.name} has {actual_nature.value}/{period_kind.value}",
        )
    dimensions = _dimensions(occurrence, spec.dimension_members)
    if type(occurrence.raw_sign) is not int or occurrence.raw_sign not in (-1, 1):
        raise NativeConstructionError(
            NativeConstructionDefect.NATIVE_METADATA_INVALID, "raw sign must be +1 or -1"
        )
    if type(occurrence.raw_scale) is not int:
        raise NativeConstructionError(
            NativeConstructionDefect.NATIVE_METADATA_INVALID, "raw scale must be an integer"
        )

    trace: dict[str, object] = {
        "occurrence_id": occurrence.occurrence_id,
        "interpretation_id": direct.interpretation_id,
        TRACE_MISSING_STATE: occurrence.missing_state.value,
        "raw_value_text": occurrence.raw_value_text,
        "raw_unit": occurrence.raw_unit,
        "raw_scale": occurrence.raw_scale,
        "raw_sign": occurrence.raw_sign,
        "spec_sign": spec.sign,
    }
    unit = scope.policy.units.get(occurrence.raw_unit)
    if unit is None or (unit.value_kind, unit.currency) != (spec.value_kind, spec.currency):
        trace[TRACE_REASON] = "raw unit does not match the native operand contract"
        return _reading(
            operand,
            occurrence,
            direct,
            state=NativeReadingState.INVALID,
            value_kind=None if unit is None else unit.value_kind,
            currency=None if unit is None else unit.currency,
            period=period,
            dimensions=dimensions,
            reason=InterpretationReason.UNIT_MISMATCH,
            trace=trace,
        )
    target = scope.dictionary.row(rule.canonical_id)
    if (
        target.value_kind is not spec.value_kind
        or target.period_nature is not spec.period_nature
        or not native_dimensions_compatible(
            scope.dictionary, rule.canonical_id, spec.dimension_members
        )
    ):
        trace[TRACE_REASON] = "dictionary target is incompatible with native operand metadata"
        return _reading(
            operand,
            occurrence,
            direct,
            state=NativeReadingState.INVALID,
            value_kind=unit.value_kind,
            currency=unit.currency,
            period=period,
            dimensions=dimensions,
            reason=InterpretationReason.UNIT_MISMATCH,
            trace=trace,
        )
    amount, interval, reason = normalise_occurrence_value(occurrence, sign=spec.sign, trace=trace)
    if occurrence.missing_state is MissingValueState.ZERO_PRINTED and amount not in (None, 0):
        amount = None
        interval = None
        reason = InterpretationReason.UNREADABLE_CELL
        trace[TRACE_REASON] = "ZERO_PRINTED carries a nonzero lexeme"
    if reason is not None:
        return _reading(
            operand,
            occurrence,
            direct,
            state=NativeReadingState.INVALID,
            value_kind=unit.value_kind,
            currency=unit.currency,
            period=period,
            dimensions=dimensions,
            reason=reason,
            trace=trace,
        )
    if amount is None:
        return _reading(
            operand,
            occurrence,
            direct,
            state=NativeReadingState.MISSING,
            value_kind=unit.value_kind,
            currency=unit.currency,
            period=period,
            dimensions=dimensions,
            reason=None,
            trace=trace,
        )
    assert interval is not None
    trace["amount"] = _fraction_text(amount)
    trace["interval"] = _interval_json(interval)
    return _reading(
        operand,
        occurrence,
        direct,
        state=NativeReadingState.VALUE,
        value_kind=unit.value_kind,
        currency=unit.currency,
        period=period,
        dimensions=dimensions,
        reason=None,
        trace=trace,
        amount=amount,
        interval=interval,
    )


def construct_native(
    rule: ConstructionRule,
    readings: Mapping[str, tuple[NativeOperandReading, ...]],
    *,
    scope: CaptureScope,
    qualification_for: Callable[[PeriodInterval, DimensionSet], QualificationContext],
    recorded_at: datetime,
) -> tuple[Interpretation, ...]:
    """Build one deterministic construction per exact native period/dimension group."""
    verified = _validate_reading_bindings(rule, readings, scope)
    grouped: dict[
        tuple[PeriodInterval, DimensionSet], dict[str, tuple[NativeOperandReading, ...]]
    ] = {}
    for operand in rule.operands:
        candidates = sorted(
            verified.get(operand.name, ()),
            key=lambda item: (
                item.occurrence.occurrence_id or 0,
                item.direct_interpretation.interpretation_id or 0,
            ),
        )
        for candidate in candidates:
            if candidate.period is None or candidate.dimensions is None:
                continue
            group = grouped.setdefault((candidate.period, candidate.dimensions), {})
            group[operand.name] = (*group.get(operand.name, ()), candidate)
    built = [
        _construct_group(
            rule,
            found,
            group=group,
            scope=scope,
            qualification=qualification_for(*group),
            recorded_at=recorded_at,
        )
        for group, found in sorted(grouped.items(), key=lambda item: _group_order(item[0]))
    ]
    return tuple(built)


def _validate_reading_bindings(
    rule: ConstructionRule,
    readings: Mapping[str, tuple[NativeOperandReading, ...]],
    scope: CaptureScope,
) -> Mapping[str, tuple[NativeOperandReading, ...]]:
    """Reattest every public reading under its exact current rule operand."""
    operands = {operand.name: operand for operand in rule.operands if operand.native is not None}
    if len(operands) != len(rule.operands) or not set(readings) <= set(operands):
        raise NativeConstructionError(
            NativeConstructionDefect.NATIVE_METADATA_INVALID,
            "native readings name an operand outside the native rule",
        )
    occurrence_keys: dict[int, set[str]] = {}
    for key, candidates in readings.items():
        for candidate in candidates:
            occurrence_id = candidate.occurrence.occurrence_id
            if occurrence_id is not None:
                occurrence_keys.setdefault(occurrence_id, set()).add(key)
    verified: dict[str, tuple[NativeOperandReading, ...]] = {}
    representations = set()
    for key, candidates in readings.items():
        operand = operands[key]
        attested: list[NativeOperandReading] = []
        for candidate in candidates:
            if candidate.operand_name != key:
                raise NativeConstructionError(
                    NativeConstructionDefect.NATIVE_METADATA_INVALID,
                    f"reading {candidate.operand_name!r} was filed under operand {key!r}",
                )
            try:
                derived = read_native_operand(
                    candidate.occurrence,
                    candidate.direct_interpretation,
                    operand=operand,
                    rule=rule,
                    scope=scope,
                )
            except NativeConstructionError as error:
                occurrence_id = candidate.occurrence.occurrence_id
                collision = occurrence_id is not None and len(occurrence_keys[occurrence_id]) > 1
                if not collision and not native_selector_matches(candidate.occurrence, operand):
                    raise NativeConstructionError(
                        NativeConstructionDefect.NATIVE_METADATA_INVALID,
                        f"reading for {key!r} does not match that operand selector",
                    ) from error
                raise
            if candidate != derived:
                raise NativeConstructionError(
                    NativeConstructionDefect.NATIVE_METADATA_INVALID,
                    f"reading for {key!r} differs from its current evidenced derivation",
                )
            attested.append(derived)
            representations.add(derived.occurrence.representation)
        verified[key] = tuple(attested)
    if len(representations) > 1:
        raise NativeConstructionError(
            NativeConstructionDefect.PROVENANCE_MISMATCH,
            "native construction candidates have different representations",
        )
    return verified


def _construct_group(
    rule: ConstructionRule,
    found: Mapping[str, tuple[NativeOperandReading, ...]],
    *,
    group: tuple[PeriodInterval, DimensionSet],
    scope: CaptureScope,
    qualification: QualificationContext,
    recorded_at: datetime,
) -> Interpretation:
    period, dimensions = group
    operands_trace: dict[str, object] = {}
    values: dict[str, tuple[Fraction, Interval]] = {}
    missing: list[str] = []
    invalid: InterpretationReason | None = None
    ordered_readings: list[NativeOperandReading] = []
    seen_occurrences: dict[int, str] = {}
    collision = False
    for operand in rule.operands:
        candidates = found.get(operand.name, ())
        ordered_readings.extend(candidates)
        candidate_trace = [_reading_json(item) for item in candidates]
        operands_trace[operand.name] = {"candidates": candidate_trace}
        if not candidates:
            missing.append(operand.name)
            operands_trace[operand.name] = {
                "candidates": [],
                "state": MissingValueState.NOT_PRESENTED.value,
            }
            continue
        for candidate in candidates:
            occurrence_id = candidate.occurrence.occurrence_id
            assert occurrence_id is not None
            previous = seen_occurrences.setdefault(occurrence_id, operand.name)
            collision = collision or previous != operand.name
        if len(candidates) > 1:
            invalid = InterpretationReason.INTERPRETATION_AMBIGUOUS
            continue
        (candidate,) = candidates
        if candidate.state is NativeReadingState.INVALID:
            invalid = invalid or candidate.reason
        elif candidate.state is NativeReadingState.MISSING:
            missing.append(operand.name)
        else:
            assert candidate.amount is not None and candidate.interval is not None
            values[operand.name] = (candidate.amount, candidate.interval)
    if collision:
        invalid = InterpretationReason.INTERPRETATION_AMBIGUOUS

    unique_readings: list[NativeOperandReading] = []
    seen_ids: set[int] = set()
    for reading in ordered_readings:
        interpretation_id = reading.direct_interpretation.interpretation_id
        assert interpretation_id is not None
        if interpretation_id not in seen_ids:
            unique_readings.append(reading)
            seen_ids.add(interpretation_id)
    first = unique_readings[0]
    native_specs = {
        operand.name: operand.native for operand in rule.operands if operand.native is not None
    }
    target = scope.dictionary.row(rule.canonical_id)
    typed = all(
        (spec := native_specs.get(item.operand_name)) is not None
        and item.value_kind is spec.value_kind
        and item.currency == spec.currency
        for item in unique_readings
    ) and all(
        spec.value_kind is target.value_kind
        and spec.period_nature is target.period_nature
        and native_dimensions_compatible(
            scope.dictionary, rule.canonical_id, spec.dimension_members
        )
        for spec in native_specs.values()
    )
    if not typed:
        invalid = invalid or InterpretationReason.UNIT_MISMATCH
    key = (
        MeasurementKey(
            entity_id=scope.entity_id,
            canonical_id=rule.canonical_id,
            period=period,
            basis=scope.basis,
            framework=scope.framework,
            currency=first.currency,
            value_kind=first.value_kind,
            dimensions=dimensions,
        )
        if typed and first.value_kind is not None
        else None
    )
    status = (
        InterpretationStatus.INVALID
        if invalid is not None or key is None
        else InterpretationStatus.MAPPED
    )
    value = None
    interval = None
    arithmetic: dict[str, object] = {"expression": rule.expression.model_dump(mode="json")}
    if invalid is None and not missing and key is not None:
        try:
            amount, interval = _evaluate(rule.expression, values)
            value = exact_decimal(amount)
            exact_decimal(interval.lower)
            exact_decimal(interval.upper)
        except (UndefinedDivisionError, ZeroDivisionError, ValueError) as error:
            raise NativeConstructionError(
                NativeConstructionDefect.NATIVE_METADATA_INVALID,
                f"native arithmetic is not exactly persistable: {error}",
            ) from error
        arithmetic.update({"amount": _fraction_text(amount), "interval": _interval_json(interval)})
    trace: dict[str, object] = {
        "rule_id": rule.rule_id,
        "native": True,
        "pins": _pins(scope),
        "period": period.canonical(),
        "dimensions": [list(pair) for pair in dimensions.pairs],
        "operands": operands_trace,
        "arithmetic": arithmetic,
    }
    if invalid is not None:
        trace[TRACE_REASON] = invalid.value
    elif missing:
        trace["missing_operands"] = missing
        trace[TRACE_REASON] = f"operands without a value: {', '.join(missing)}"
    digest_payload = {
        "rule": _rule_json(rule),
        "pins": trace["pins"],
        "period": trace["period"],
        "dimensions": trace["dimensions"],
        "operands": operands_trace,
        "arithmetic": arithmetic,
    }
    scoped = scoped_tier(rule.tier, rule.qualification, qualification)
    demonstrated = scoped.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    operand_ids = tuple(_interpretation_id(item) for item in unique_readings)
    capture_ref_id = scope.capture.capture_ref_id
    assert capture_ref_id is not None
    return Interpretation(
        interpretation_id=None,
        origin=InterpretationOrigin.CONSTRUCTED,
        occurrence_id=None,
        capture_ref_id=capture_ref_id,
        representation=first.occurrence.representation,
        construction_rule_id=rule.rule_id,
        operand_interpretation_ids=operand_ids,
        input_digest=input_digest(digest_payload),
        status=status,
        entity_id=scope.entity_id,
        basis=scope.basis,
        framework=scope.framework,
        canonical_id=rule.canonical_id,
        period=period,
        dictionary_version=scope.dictionary.version,
        key=key,
        dimensions=dimensions,
        value=value,
        interval=interval,
        tier=(
            EvidenceTier.EQUIVALENCE_DEMONSTRATED
            if key is not None and demonstrated
            else EvidenceTier.EQUIVALENCE_UNPROVEN
        ),
        mapping_set_version=scope.mapping_set.version,
        mapping_entry_id=None,
        qualification_ref=scoped.qualification_ref if key is not None and demonstrated else None,
        condition_evidence=scoped.condition_evidence if key is not None and demonstrated else (),
        normalisation_policy_version=scope.policy.version,
        extractor_version=first.occurrence.extractor_version,
        transform_trace=trace,
        reason=invalid if status is InterpretationStatus.INVALID else None,
        revision_cause=RevisionCause.ORIGINAL,
        supersedes_interpretation_id=None,
        recorded_at=recorded_at,
    )


def validate_native_provenance(
    occurrence: Occurrence,
    direct: Interpretation,
    *,
    rule: ConstructionRule,
    scope: CaptureScope,
) -> None:
    """Refuse a native occurrence/direct pair outside the exact current generation."""
    validate_generation_provenance(occurrence, direct, scope=scope)
    occurrence_id = occurrence.occurrence_id
    context_schema = occurrence.native_context.get(CONTEXT_SCHEMA_IDENTITY)
    invalid = (
        direct.status is not InterpretationStatus.UNMAPPED
        or direct.mapping_entry_id is not None
        or direct.canonical_id is not None
        or direct.key is not None
        or direct.value is not None
        or direct.interval is not None
        or occurrence.capture.source_id != rule.source
        or occurrence.capture.surface != rule.surface
        or context_schema != rule.schema_identity
    )
    if invalid:
        raise NativeConstructionError(
            NativeConstructionDefect.PROVENANCE_MISMATCH,
            f"occurrence {occurrence_id!r} is not an unmapped input of this native rule",
        )


def validate_generation_provenance(
    occurrence: Occurrence,
    direct: Interpretation,
    *,
    scope: CaptureScope,
) -> None:
    """Validate the common current-generation identity of mapped or unmapped direct rows."""
    expected_pin = scope.expected_extractor_pin
    occurrence_id = occurrence.occurrence_id
    capture_id = occurrence.capture.capture_ref_id
    expected_direct_digest = (
        input_digest({"occurrence_id": occurrence_id}) if occurrence_id is not None else None
    )
    context_basis = occurrence.native_context.get(CONTEXT_BASIS)
    invalid = (
        occurrence_id is None
        or capture_id is None
        or scope.capture.capture_ref_id is None
        or direct.interpretation_id is None
        or direct.origin is not InterpretationOrigin.DIRECT
        or direct.occurrence_id != occurrence_id
        or direct.capture_ref_id != capture_id
        or capture_id != scope.capture.capture_ref_id
        or occurrence.capture != scope.capture
        or direct.representation is not occurrence.representation
        or direct.construction_rule_id is not None
        or direct.operand_interpretation_ids
        or direct.input_digest != expected_direct_digest
        or direct.entity_id != scope.entity_id
        or direct.basis is not scope.basis
        or direct.framework is not scope.framework
        or direct.dictionary_version != scope.dictionary.version
        or direct.mapping_set_version != scope.mapping_set.version
        or direct.normalisation_policy_version != scope.policy.version
        or direct.extractor_version != occurrence.extractor_version
        or context_basis != scope.basis.value
        or expected_pin is None
        or (expected_pin.source_id, expected_pin.surface)
        != (scope.capture.source_id, scope.capture.surface)
        or expected_pin.version != occurrence.extractor_version
    )
    if invalid:
        raise NativeConstructionError(
            NativeConstructionDefect.PROVENANCE_MISMATCH,
            f"occurrence {occurrence_id!r} is not its exact current direct interpretation",
        )


def _dimensions(occurrence: Occurrence, expected: Mapping[str, str]) -> DimensionSet:
    raw = occurrence.native_context.get("dimensions", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping) or not all(
        isinstance(axis, str) and isinstance(member, str) for axis, member in raw.items()
    ):
        raise NativeConstructionError(
            NativeConstructionDefect.DIMENSION_MISMATCH, "native dimensions are malformed"
        )
    if dict(raw) != dict(expected):
        raise NativeConstructionError(
            NativeConstructionDefect.DIMENSION_MISMATCH, "native dimensions differ from selector"
        )
    return DimensionSet.of(expected)


def _reading(
    operand: ConstructionOperand,
    occurrence: Occurrence,
    direct: Interpretation,
    *,
    state: NativeReadingState,
    value_kind: ValueKind | None,
    currency: str | None,
    period: PeriodInterval | None,
    dimensions: DimensionSet | None,
    reason: InterpretationReason | None,
    trace: Mapping[str, object],
    amount: Fraction | None = None,
    interval: Interval | None = None,
) -> NativeOperandReading:
    return NativeOperandReading(
        operand_name=operand.name,
        occurrence=occurrence,
        direct_interpretation=direct,
        state=state,
        amount=amount,
        interval=interval,
        value_kind=value_kind,
        currency=currency,
        period=period,
        dimensions=dimensions,
        reason=reason,
        trace=trace,
    )


def _interpretation_id(reading: NativeOperandReading) -> int:
    interpretation_id = reading.direct_interpretation.interpretation_id
    assert interpretation_id is not None
    return interpretation_id


def _pins(scope: CaptureScope) -> dict[str, object]:
    extractor = scope.expected_extractor_pin
    assert extractor is not None
    return {
        "dictionary": {
            "version": scope.dictionary.version,
            "content_sha256": scope.dictionary.content_sha256,
        },
        "mapping_set": {
            "version": scope.mapping_set.version,
            "content_sha256": scope.mapping_set.content_sha256,
        },
        "normalisation_policy": {
            "version": scope.policy.version,
            "content_sha256": scope.policy.content_sha256,
        },
        "extractor": extractor.model_dump(mode="json"),
    }


def _rule_json(rule: ConstructionRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "source": rule.source,
        "surface": rule.surface,
        "schema_identity": rule.schema_identity,
        "canonical_id": rule.canonical_id,
        "operands": [
            {
                "name": operand.name,
                "native": {
                    "selector": operand.native.selector.model_dump(mode="json", exclude_none=True),
                    "sign": operand.native.sign,
                    "unit_transform": operand.native.unit_transform.value,
                    "precision_rule": operand.native.precision_rule.value,
                    "value_kind": operand.native.value_kind.value,
                    "currency": operand.native.currency,
                    "period_nature": operand.native.period_nature.value,
                    "dimension_members": dict(sorted(operand.native.dimension_members.items())),
                    "bases": sorted(item.value for item in operand.native.bases),
                    "period_kinds": sorted(item.value for item in operand.native.period_kinds),
                    "evidence_ref": operand.native.evidence_ref,
                },
            }
            for operand in rule.operands
            if operand.native is not None
        ],
        "expression": rule.expression.model_dump(mode="json"),
        "evidence_ref": rule.evidence_ref,
    }


def _reading_json(reading: NativeOperandReading) -> dict[str, object]:
    return {
        "occurrence_id": reading.occurrence.occurrence_id,
        "interpretation_id": reading.direct_interpretation.interpretation_id,
        "state": reading.state.value,
        "amount": None if reading.amount is None else _fraction_text(reading.amount),
        "interval": None if reading.interval is None else _interval_json(reading.interval),
        "value_kind": None if reading.value_kind is None else reading.value_kind.value,
        "currency": reading.currency,
        "trace": dict(reading.trace),
    }


def _fraction_text(value: Fraction) -> str:
    try:
        return str(exact_decimal(value))
    except ValueError:
        return f"{value.numerator}/{value.denominator}"


def _interval_json(interval: Interval) -> dict[str, str]:
    return {"lower": _fraction_text(interval.lower), "upper": _fraction_text(interval.upper)}


def _group_order(group: tuple[PeriodInterval, DimensionSet]) -> tuple[str, str]:
    period, dimensions = group
    return json.dumps(period.canonical(), sort_keys=True), dimensions.digest()
