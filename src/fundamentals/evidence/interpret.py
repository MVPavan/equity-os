"""Occurrence plus mapping to an interpretation; source-scoped constructions (D1a Task 5).

Values never depend on tiers: key, value and interval come from the occurrence, the
mapping entry and the normalisation policy only; the qualification context decides the
scoped tier alone. Nothing is zero-filled: a nil, dash, blank or absent line has no value.
Arithmetic is exact (``Fraction``), so no Decimal context precision ever rounds a value.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.canon.formula import _evaluate
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation, ValueKind
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    MissingValueState,
    Occurrence,
    PrecisionKind,
    RevisionCause,
    exact_decimal,
)
from fundamentals.contracts.evidence_tier import EvidenceTier, weakest
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import (
    ConditionPredicate,
    ProvenCondition,
    QualificationCondition,
    QualificationContext,
    scoped_tier,
)
from fundamentals.evidence.mapping import (
    ConstructionOperand,
    ConstructionRule,
    MappingEntry,
    MappingSet,
    MemberSource,
    NormalisationPolicy,
    PdfPeriodRule,
    matches_dimensions,
)
from fundamentals.evidence.pdf_adapter import CONTEXT_HEADER_MONTHS, parse_printed_number
from fundamentals.evidence.xbrl_adapter import (
    CONTEXT_MEMBER_DESCRIPTIONS,
    CONTEXT_PERIOD_AMBIGUOUS,
    member_slug,
)

TRACE_MISSING_STATE = "missing_state"
TRACE_REASON = "reason"
SEGMENT_AXIS = "segment"
_NO_VALUE_STATES = frozenset(
    {
        MissingValueState.NIL,
        MissingValueState.DASH,
        MissingValueState.BLANK,
        MissingValueState.NOT_PRESENTED,
        MissingValueState.SOURCE_NULL,
    }
)
_MONETARY = frozenset({ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT})
_HEADER_KINDS = {
    3: PeriodKind.QUARTER,
    6: PeriodKind.HALF_YEAR,
    9: PeriodKind.NINE_MONTH,
    12: PeriodKind.YEAR,
}
_NO_OPERANDS = "construction {rule_id} has no operand interpretation"
TRACE_MATCHED_ENTRY_IDS = "matched_entry_ids"
_AMBIGUOUS_ENTRIES = "entries {entry_ids} all match this native field"
_AMBIGUOUS_OPERANDS = "operands matched more than once: {names}"
_ZERO = Fraction(0)
_ONE_DAY = timedelta(days=1)


def input_digest(payload: object) -> str:
    """SHA-256 of a JSON payload in sorted compact form."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def interpret(
    occurrence: Occurrence,
    *,
    entity_id: int,
    basis: Basis,
    framework: AccountingFramework,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
    dictionary: CanonicalDictionary,
    fiscal_year_end_month: int,
    qualification: QualificationContext,
    recorded_at: datetime,
    as_entry: MappingEntry | None = None,
) -> Interpretation:
    """Map one stored occurrence under the pinned mapping set and normalisation policy.

    ``as_entry`` reads the occurrence as if that entry alone matched: what an ambiguous
    line would be under each candidate entry, never a stored interpretation.
    """
    assert occurrence.occurrence_id is not None and occurrence.capture.capture_ref_id is not None
    period_kind = (
        occurrence.period.kind(fiscal_year_end_month) if occurrence.period is not None else None
    )
    entries = (
        (as_entry,)
        if as_entry is not None
        else mapping_set.matches(occurrence, period_kind=period_kind)
    )
    trace: dict[str, object] = {
        TRACE_MISSING_STATE: occurrence.missing_state.value,
        "raw_value_text": occurrence.raw_value_text,
        "raw_unit": occurrence.raw_unit,
        "raw_scale": occurrence.raw_scale,
        "raw_sign": occurrence.raw_sign,
    }
    common = {
        "interpretation_id": None,
        "origin": InterpretationOrigin.DIRECT,
        "occurrence_id": occurrence.occurrence_id,
        "capture_ref_id": occurrence.capture.capture_ref_id,
        "representation": occurrence.representation,
        "construction_rule_id": None,
        "operand_interpretation_ids": (),
        "input_digest": input_digest({"occurrence_id": occurrence.occurrence_id}),
        "entity_id": entity_id,
        "basis": basis,
        "framework": framework,
        "dictionary_version": dictionary.version,
        "mapping_set_version": mapping_set.version,
        "normalisation_policy_version": policy.version,
        "extractor_version": occurrence.extractor_version,
        "revision_cause": RevisionCause.ORIGINAL,
        "supersedes_interpretation_id": None,
        "recorded_at": recorded_at,
    }
    if not entries:
        return _without_key(common, InterpretationStatus.UNMAPPED, None, occurrence.period, trace)
    if len(entries) > 1:
        ids = [candidate.entry_id for candidate in entries]
        trace[TRACE_MATCHED_ENTRY_IDS] = ids
        trace[TRACE_REASON] = _AMBIGUOUS_ENTRIES.format(entry_ids=ids)
        candidate_keys = []
        for candidate in entries:
            established = interpret(
                occurrence,
                entity_id=entity_id,
                basis=basis,
                framework=framework,
                mapping_set=mapping_set,
                policy=policy,
                dictionary=dictionary,
                fiscal_year_end_month=fiscal_year_end_month,
                qualification=qualification,
                recorded_at=recorded_at,
                as_entry=candidate,
            )
            identity = established.model_dump(
                mode="json",
                include={
                    "entity_id",
                    "canonical_id",
                    "period",
                    "basis",
                    "framework",
                    "dimensions",
                },
            )
            identity["currency"] = established.key.currency if established.key is not None else None
            identity["value_kind"] = (
                established.key.value_kind.value if established.key is not None else None
            )
            candidate_keys.append(identity)
        # These identify uncertainty only. No candidate value, interval, tier or
        # speculative interpretation is persisted or selected as evidence.
        trace["ambiguous_candidate_keys"] = candidate_keys
        return _without_key(
            common,
            InterpretationStatus.INVALID,
            None,
            occurrence.period,
            trace,
            reason=InterpretationReason.INTERPRETATION_AMBIGUOUS,
        )
    (entry,) = entries
    common["mapping_entry_id"] = entry.entry_id
    trace["entry_sign"] = entry.sign
    row = dictionary.row(entry.canonical_id)
    period = _key_period(occurrence, entry, fiscal_year_end_month, trace)
    # Resolved before the period check so an ambiguous row still traces its member.
    dimensions = _dimensions(occurrence, entry, trace)
    if period is None:
        return _without_key(
            common,
            InterpretationStatus.PERIOD_AMBIGUOUS,
            entry.canonical_id,
            occurrence.period,
            trace,
            dimensions=dimensions,
        )
    if dimensions is None:
        return _without_key(
            common, InterpretationStatus.UNMAPPED, entry.canonical_id, period, trace
        )
    unit = policy.units.get(occurrence.raw_unit)
    if unit is None or unit.value_kind is not row.value_kind:
        trace[TRACE_REASON] = f"raw unit {occurrence.raw_unit!r} is not a {row.value_kind} unit"
        return _without_key(
            common,
            InterpretationStatus.INVALID,
            entry.canonical_id,
            period,
            trace,
            reason=InterpretationReason.UNIT_MISMATCH,
            dimensions=dimensions,
        )
    key = MeasurementKey(
        entity_id=entity_id,
        canonical_id=entry.canonical_id,
        period=period,
        basis=basis,
        framework=framework,
        currency=unit.currency if row.value_kind in _MONETARY else None,
        value_kind=row.value_kind,
        dimensions=dimensions,
    )
    value, interval, reason = _value(occurrence, entry, trace)
    scoped = scoped_tier(entry.tier, entry.qualification, qualification)
    return Interpretation.model_validate(
        {
            **common,
            "status": (
                InterpretationStatus.INVALID if reason is not None else InterpretationStatus.MAPPED
            ),
            "canonical_id": entry.canonical_id,
            "period": period,
            "key": key,
            "value": value,
            "interval": interval,
            "tier": scoped.tier,
            "qualification_ref": scoped.qualification_ref,
            "condition_evidence": scoped.condition_evidence,
            "transform_trace": trace,
            "reason": reason,
        }
    )


def construct(
    rule: ConstructionRule,
    operands: Mapping[str, Interpretation],
    *,
    dash_rules: NormalisationPolicy,
    qualification: QualificationContext,
    recorded_at: datetime,
    duplicates: Mapping[str, Sequence[Interpretation]] | None = None,
    group: tuple[PeriodInterval, DimensionSet] | None = None,
) -> Interpretation:
    """Assemble one reported value from one capture's own operand interpretations.

    Exact interval arithmetic over the operands; a ``DASH`` operand with an evidenced
    dash rule contributes exact zero (rule id traced); any other operand without a value
    (absent line, blank, nil, unruled dash) gives no value; an ``INVALID`` operand gives
    ``INVALID`` (invalid beats missing). ``duplicates`` names operands matched more than
    once in the group (every candidate listed): the construction is ``INVALID``
    (``INTERPRETATION_AMBIGUOUS``), never built from one of them. The tier is the weakest
    of the rule's scoped tier and every operand's. Without a keyed operand, the period and
    dimensions are the operand ``group``'s (period, dimensions), when given.
    """
    extra = duplicates or {}
    present = [operands[operand.name] for operand in rule.operands if operand.name in operands]
    present += [item for name in sorted(extra) for item in extra[name] if item not in present]
    keyed = [item for item in present if item.key is not None]
    if not present:
        raise ValueError(_NO_OPERANDS.format(rule_id=rule.rule_id))
    first = present[0]
    values: dict[str, tuple[Fraction, Interval]] = {}
    operand_trace: dict[str, object] = {}
    missing: list[str] = []
    invalid: InterpretationReason | None = None
    for operand in rule.operands:
        item = operands.get(operand.name)
        if operand.name in extra:
            operand_trace[operand.name] = {
                "interpretation_ids": [found.interpretation_id for found in extra[operand.name]]
            }
            continue
        if item is None:
            operand_trace[operand.name] = {
                TRACE_MISSING_STATE: MissingValueState.NOT_PRESENTED.value
            }
            missing.append(operand.name)
            continue
        step: dict[str, object] = {
            "interpretation_id": item.interpretation_id,
            "status": item.status.value,
            TRACE_MISSING_STATE: item.transform_trace.get(TRACE_MISSING_STATE),
        }
        operand_trace[operand.name] = step
        if item.status is InterpretationStatus.INVALID:
            invalid = invalid or item.reason
        elif item.status is InterpretationStatus.MAPPED and item.value is not None:
            assert item.interval is not None
            values[operand.name] = (Fraction(item.value), item.interval)
        elif _dash_reads_zero(rule, operand, item, dash_rules):
            values[operand.name] = (_ZERO, Interval.exact(_ZERO))
            step["dash_rule_id"] = operand.dash_rule_id
        else:
            missing.append(operand.name)
    scoped = scoped_tier(rule.tier, rule.qualification, qualification)
    first_key = keyed[0].key if keyed else None
    key = (
        first_key.model_copy(update={"canonical_id": rule.canonical_id})
        if first_key is not None
        else None
    )
    trace: dict[str, object] = {"rule_id": rule.rule_id, "operands": operand_trace}
    value: Decimal | None = None
    interval: Interval | None = None
    status = InterpretationStatus.MAPPED
    if extra:
        invalid = InterpretationReason.INTERPRETATION_AMBIGUOUS
        trace["duplicate_operands"] = {
            name: [item.interpretation_id for item in extra[name]] for name in sorted(extra)
        }
        trace[TRACE_REASON] = _AMBIGUOUS_OPERANDS.format(names=", ".join(sorted(extra)))
    if invalid is not None or key is None:
        status = InterpretationStatus.INVALID
    elif missing:
        trace[TRACE_REASON] = f"operands without a value: {', '.join(missing)}"
    else:
        point, interval = _evaluate(rule.expression, values)
        value = exact_decimal(point)
    operand_ids = tuple(item.interpretation_id for item in present if item.interpretation_id)
    return Interpretation(
        interpretation_id=None,
        origin=InterpretationOrigin.CONSTRUCTED,
        occurrence_id=None,
        capture_ref_id=first.capture_ref_id,
        representation=first.representation,
        construction_rule_id=rule.rule_id,
        operand_interpretation_ids=operand_ids,
        input_digest=input_digest({"operands": list(operand_ids)}),
        status=status,
        entity_id=first.entity_id,
        basis=first.basis,
        framework=first.framework,
        canonical_id=rule.canonical_id,
        period=key.period if key is not None else (group[0] if group else first.period),
        dictionary_version=first.dictionary_version,
        key=key,
        dimensions=key.dimensions if key is not None else (group[1] if group else None),
        value=value,
        interval=interval,
        tier=weakest(scoped.tier, *(item.tier for item in present)),
        mapping_set_version=first.mapping_set_version,
        mapping_entry_id=None,
        qualification_ref=scoped.qualification_ref,
        condition_evidence=scoped.condition_evidence,
        normalisation_policy_version=dash_rules.version,
        extractor_version=first.extractor_version,
        transform_trace=trace,
        reason=invalid if status is InterpretationStatus.INVALID else None,
        revision_cause=RevisionCause.ORIGINAL,
        supersedes_interpretation_id=None,
        recorded_at=recorded_at,
    )


def _dash_reads_zero(
    rule: ConstructionRule,
    operand: ConstructionOperand,
    item: Interpretation,
    policy: NormalisationPolicy,
) -> bool:
    """Whether an evidenced dash rule reads this printed dash as zero for this operand."""
    if operand.dash_rule_id is None:
        return False
    dash_rule = policy.dash_rules.get(operand.dash_rule_id)
    return (
        dash_rule is not None
        and dash_rule.construction_rule_id == rule.rule_id
        and dash_rule.operand_name == operand.name
        and item.status is InterpretationStatus.MAPPED
        and item.transform_trace.get(TRACE_MISSING_STATE) == MissingValueState.DASH.value
    )


def prove_conditions(
    conditions: Sequence[QualificationCondition],
    *,
    interpretations: Sequence[Interpretation],
    period: PeriodInterval,
    basis: Basis,
) -> Mapping[str, ProvenCondition]:
    """Prove conditions from same-capture ``MAPPED`` interpretations of that period and basis.

    Interval exactly {0}: ``EQUALS_ZERO`` holds and ``NOT_EQUALS_ZERO`` fails; interval
    excluding 0: the reverse. An interval containing 0 and other values, no such
    interpretation, or one without a value leaves the condition unproven and absent.
    """
    proofs: dict[str, ProvenCondition] = {}
    for condition in conditions:
        evidence = [
            item
            for item in interpretations
            if item.status is InterpretationStatus.MAPPED
            and item.key is not None
            and item.key.canonical_id == condition.canonical_id
            and item.key.period == period
            and item.key.basis is basis
            and not item.key.dimensions.pairs
        ]
        if not evidence or any(
            item.interval is None or item.interpretation_id is None for item in evidence
        ):
            continue
        intervals = [item.interval for item in evidence if item.interval is not None]
        if all(interval.lower == interval.upper == _ZERO for interval in intervals):
            is_zero = True
        elif all(not interval.contains(_ZERO) for interval in intervals):
            is_zero = False
        else:
            continue
        holds = is_zero == (condition.predicate is ConditionPredicate.EQUALS_ZERO)
        proofs[condition.condition_id] = ProvenCondition(
            condition_id=condition.condition_id,
            holds=holds,
            evidence_interpretation_ids=tuple(
                item.interpretation_id for item in evidence if item.interpretation_id is not None
            ),
        )
    return proofs


def _without_key(
    common: Mapping[str, object],
    status: InterpretationStatus,
    canonical_id: str | None,
    period: PeriodInterval | None,
    trace: Mapping[str, object],
    *,
    reason: InterpretationReason | None = None,
    dimensions: DimensionSet | None = None,
) -> Interpretation:
    """An interpretation that could not complete its key: no key, no value, unproven tier.

    It keeps the key parts the evidence establishes (canonical id, period, dimensions) and
    never invents the rest (currency, value kind).
    """
    return Interpretation.model_validate(
        {
            "mapping_entry_id": None,
            **common,
            "status": status,
            "canonical_id": canonical_id,
            "period": period,
            "key": None,
            "dimensions": dimensions,
            "value": None,
            "interval": None,
            "tier": EvidenceTier.EQUIVALENCE_UNPROVEN,
            "qualification_ref": None,
            "condition_evidence": (),
            "transform_trace": trace,
            "reason": reason,
        }
    )


def _key_period(
    occurrence: Occurrence,
    entry: MappingEntry,
    fiscal_year_end_month: int,
    trace: dict[str, object],
) -> PeriodInterval | None:
    """The key period: XBRL's repaired period, or the PDF header plus the entry's rule."""
    period = occurrence.period
    context = occurrence.native_context
    if occurrence.representation is Representation.XBRL:
        if context.get(CONTEXT_PERIOD_AMBIGUOUS):
            trace[TRACE_REASON] = "undeclared context shares a raw period read two ways"
            return None
        return period
    rule = entry.period_rule
    trace["period_rule"] = rule.value if rule is not None else None
    if period is None or rule is None:
        trace[TRACE_REASON] = "column header period undeterminable"
        return None
    trace["header_period"] = period.canonical()
    if rule is PdfPeriodRule.COLUMN_INSTANT:
        if period.instant is None:
            _refuse(trace, rule)
            return None
        return period
    if period.start is None or period.end is None:
        _refuse(trace, rule)
        return None
    months = context.get(CONTEXT_HEADER_MONTHS)
    expected = _HEADER_KINDS.get(months) if isinstance(months, int) else None
    kind = period.kind(fiscal_year_end_month)
    if kind is not expected:
        trace[TRACE_REASON] = f"header duration is {kind}, not the fiscal {months}-month period"
        return None
    if rule is PdfPeriodRule.COLUMN_DURATION:
        return period
    if rule is PdfPeriodRule.COLUMN_OPENING_INSTANT:
        return PeriodInterval.at(period.start - _ONE_DAY)
    return PeriodInterval.at(period.end)


def _refuse(trace: dict[str, object], rule: PdfPeriodRule) -> None:
    """Record that a rule does not fit the header shape."""
    trace[TRACE_REASON] = f"period rule {rule} does not fit the column header"


def _dimensions(
    occurrence: Occurrence, entry: MappingEntry, trace: dict[str, object]
) -> DimensionSet | None:
    """The entry's fixed members plus the evidenced segment member, if the entry takes one."""
    members = dict(entry.dimension_members)
    if occurrence.representation is Representation.XBRL and not matches_dimensions(
        occurrence.native_context, entry.schema_identity, entry.selector.dimension_axis
    ):
        trace[TRACE_REASON] = "dimension namespace or member identity does not fit the mapping"
        return None
    if entry.member_source is MemberSource.XBRL_DESCRIPTION:
        descriptions = occurrence.native_context.get(CONTEXT_MEMBER_DESCRIPTIONS)
        axis = entry.selector.dimension_axis
        identity = f"{{{entry.schema_identity}}}{axis}"
        found = descriptions.get(identity) if isinstance(descriptions, Mapping) else None
        if not isinstance(found, Mapping) or not found.get("text"):
            trace[TRACE_REASON] = f"no evidenced description for axis {axis}"
            return None
        members[SEGMENT_AXIS] = member_slug(str(found["text"]))
        trace["member_description"] = dict(found)
    return DimensionSet.of(members)


def _value(
    occurrence: Occurrence, entry: MappingEntry, trace: dict[str, object]
) -> tuple[Decimal | None, Interval | None, InterpretationReason | None]:
    """Exact base-unit value and interval; no value for a missing marker."""
    amount, interval, reason = normalise_occurrence_value(occurrence, sign=entry.sign, trace=trace)
    return (exact_decimal(amount) if amount is not None else None), interval, reason


def normalise_occurrence_value(
    occurrence: Occurrence,
    *,
    sign: int,
    trace: dict[str, object],
) -> tuple[Fraction | None, Interval | None, InterpretationReason | None]:
    """Read exact base units and uncertainty with the shared direct/native policy."""
    if occurrence.native_context.get("pdf_row_ambiguous") is True:
        trace[TRACE_REASON] = "blank labelled PDF row has ambiguous data/heading attribution"
        return None, None, InterpretationReason.INTERPRETATION_AMBIGUOUS
    if occurrence.missing_state in _NO_VALUE_STATES:
        return None, None, None
    magnitude = _magnitude(occurrence)
    if magnitude is None:
        trace[TRACE_REASON] = "printed text is outside the numeric grammar"
        return None, None, InterpretationReason.UNREADABLE_CELL
    if occurrence.precision_kind is PrecisionKind.UNSUPPORTED:
        trace[TRACE_REASON] = "no usable declared precision"
        return None, None, InterpretationReason.PRECISION_UNSUPPORTED
    exact = Fraction(magnitude) * occurrence.raw_sign * sign * Fraction(10) ** occurrence.raw_scale
    value = exact_decimal(exact)
    if occurrence.precision_kind is PrecisionKind.EXACT:
        return exact, Interval.exact(value), None
    assert occurrence.declared_precision is not None
    places = occurrence.declared_precision - occurrence.raw_scale
    trace["interval_places"] = places
    return exact, Interval.from_precision(value, places), None


def _magnitude(occurrence: Occurrence) -> Decimal | None:
    """The unsigned printed magnitude, under the representation's own grammar."""
    text = (occurrence.raw_value_text or "").strip()
    if occurrence.representation is Representation.PDF:
        parsed = parse_printed_number(text)
        return parsed.magnitude if parsed is not None else None
    if occurrence.representation in (Representation.HTML, Representation.JSON):
        from fundamentals.ingest.screener_financials_tables import read_number

        vendor_number, _ = read_number(text)
        return None if vendor_number is None else vendor_number.copy_abs()
    try:
        filed = Decimal(text)
    except InvalidOperation:
        return None
    # copy_abs is exact; abs() would round to the ambient context precision.
    return filed.copy_abs() if filed.is_finite() else None
