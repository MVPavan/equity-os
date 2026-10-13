"""Interpret one capture's occurrence generation in two qualification passes (D1a Task 5).

Values never depend on tiers. The first pass interprets every occurrence and builds every
construction with no proofs; ids are reserved so proofs can cite them; conditions are
proven per (period, basis) from this capture's own mapped rows; the second pass resolves
each measurement's scoped tier against its own period kind and proofs. Each new row's
revision cause follows design decision 10 (reprocessing, else ``ORIGINAL``; Task 6 adds the
comparative check).

Constructions apply to the capture's source (a source-named rule to that source only) and
group operands by (period, dimensions). An ``INVALID`` operand joins its group even without
a key, so the construction is ``INVALID``, never "line absent"; an operand matched twice in
one group makes the construction ``INVALID`` (``INTERPRETATION_AMBIGUOUS``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import CanonicalDictionary
from fundamentals.contracts.canonical import Basis, PeriodKind
from fundamentals.contracts.evidence import (
    CaptureReference,
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    Occurrence,
    RevisionCause,
)
from fundamentals.contracts.measurement_key import DimensionSet, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import (
    ProvenCondition,
    QualificationCondition,
    QualificationContext,
    qualification_context,
    scoped_tier,
)
from fundamentals.evidence.interpret import (
    TRACE_MATCHED_ENTRY_IDS,
    construct,
    interpret,
    prove_conditions,
)
from fundamentals.evidence.mapping import (
    CONTEXT_SCHEMA_IDENTITY,
    ConstructionRule,
    MappingSet,
    NormalisationPolicy,
    applies_to_source,
)

_LOG = structlog.get_logger(__name__)
_DUPLICATE_OPERAND = "construction operand matched twice in one group; construction INVALID"
_UNGROUPED = "invalid operand has no resolvable group; it joins no construction"

ReserveIds = Callable[[int], tuple[int, ...]]
ProofKey = tuple[PeriodInterval, Basis]
GroupKey = tuple[PeriodInterval, DimensionSet]
Alternatives = Mapping[int, tuple[tuple[str, GroupKey], ...]]


class CaptureScope(BaseModel):
    """What every interpretation of one capture shares."""

    model_config = ConfigDict(frozen=True)

    capture: CaptureReference
    entity_id: int
    basis: Basis
    framework: AccountingFramework
    mapping_set: MappingSet
    policy: NormalisationPolicy
    dictionary: CanonicalDictionary
    fiscal_year_end_month: int


def interpret_generation(
    occurrences: Sequence[Occurrence],
    *,
    scope: CaptureScope,
    prior: Sequence[Interpretation],
    prior_anchor_keys: Mapping[int, str],
    reserve_ids: ReserveIds,
    recorded_at: datetime,
) -> tuple[Interpretation, ...]:
    """Every direct and constructed interpretation of one generation, ids reserved, causes set.

    ``prior`` is the capture's interpretations under other triples and
    ``prior_anchor_keys`` maps their occurrence ids to anchor keys.
    """
    first = [
        interpret(
            occurrence,
            entity_id=scope.entity_id,
            basis=scope.basis,
            framework=scope.framework,
            mapping_set=scope.mapping_set,
            policy=scope.policy,
            dictionary=scope.dictionary,
            fiscal_year_end_month=scope.fiscal_year_end_month,
            qualification=_unproven(occurrence, scope),
            recorded_at=recorded_at,
        )
        for occurrence in occurrences
    ]
    direct_ids = reserve_ids(len(first))
    first = [
        item.model_copy(update={"interpretation_id": reserved})
        for item, reserved in zip(first, direct_ids, strict=True)
    ]
    schemas = frozenset(
        str(occurrence.native_context.get(CONTEXT_SCHEMA_IDENTITY, ""))
        for occurrence in occurrences
    )
    alternatives = _ambiguous_alternatives(first, occurrences, scope, recorded_at)
    first_constructed = _constructions(
        first,
        scope,
        schemas=schemas,
        proofs={},
        alternatives=alternatives,
        recorded_at=recorded_at,
    )
    constructed_ids = reserve_ids(len(first_constructed))
    first_constructed = [
        item.model_copy(update={"interpretation_id": reserved})
        for item, reserved in zip(first_constructed, constructed_ids, strict=True)
    ]
    proofs = _proofs([*first, *first_constructed], scope)
    second = [
        _qualified(item, occurrence, scope, proofs)
        for item, occurrence in zip(first, occurrences, strict=True)
    ]
    second_constructed = _constructions(
        second,
        scope,
        schemas=schemas,
        proofs=proofs,
        alternatives=alternatives,
        recorded_at=recorded_at,
    )
    second_constructed = [
        item.model_copy(update={"interpretation_id": reserved})
        for item, reserved in zip(second_constructed, constructed_ids, strict=True)
    ]
    anchors = {occurrence.occurrence_id: occurrence.anchor_key for occurrence in occurrences}
    return tuple(
        _with_cause(item, scope, prior, prior_anchor_keys, anchors)
        for item in (*second, *second_constructed)
    )


def _unproven(occurrence: Occurrence, scope: CaptureScope) -> QualificationContext:
    """A first-pass context: the occurrence's own period kind and no proofs."""
    period = occurrence.period
    return QualificationContext(
        schema_identity=str(occurrence.native_context.get(CONTEXT_SCHEMA_IDENTITY, "")),
        surface=scope.capture.surface,
        basis=scope.basis,
        period_kind=(
            period.kind(scope.fiscal_year_end_month) if period is not None else PeriodKind.OTHER
        ),
        proven={},
    )


def _conditions(mapping_set: MappingSet) -> tuple[QualificationCondition, ...]:
    """Every condition and exclusion any entry or construction scope names, once each."""
    found: dict[str, QualificationCondition] = {}
    scopes = [entry.qualification for entry in mapping_set.entries]
    scopes += [rule.qualification for rule in mapping_set.constructions]
    for scope in scopes:
        if scope is None:
            continue
        for condition in (*scope.conditions, *scope.exclusions):
            found.setdefault(condition.condition_id, condition)
    return tuple(found.values())


def _proofs(
    interpretations: Sequence[Interpretation], scope: CaptureScope
) -> Mapping[ProofKey, Mapping[str, ProvenCondition]]:
    """Proofs per distinct (period, basis) of the mapped first-pass rows."""
    conditions = _conditions(scope.mapping_set)
    if not conditions:
        return {}
    keys = {(item.key.period, item.key.basis) for item in interpretations if item.key is not None}
    return {
        (period, basis): prove_conditions(
            conditions, interpretations=interpretations, period=period, basis=basis
        )
        for period, basis in keys
    }


def _qualified(
    item: Interpretation,
    occurrence: Occurrence,
    scope: CaptureScope,
    proofs: Mapping[ProofKey, Mapping[str, ProvenCondition]],
) -> Interpretation:
    """A direct row's tier resolved for its own key; key, value and interval unchanged."""
    if item.key is None or item.mapping_entry_id is None:
        return item
    entry = scope.mapping_set.entry(item.mapping_entry_id)
    context = qualification_context(
        item.key,
        schema_identity=str(occurrence.native_context.get(CONTEXT_SCHEMA_IDENTITY, "")),
        surface=scope.capture.surface,
        fiscal_year_end_month=scope.fiscal_year_end_month,
        proven=proofs.get((item.key.period, item.key.basis), {}),
    )
    scoped = scoped_tier(entry.tier, entry.qualification, context)
    return item.model_copy(
        update={
            "tier": scoped.tier,
            "qualification_ref": scoped.qualification_ref,
            "condition_evidence": scoped.condition_evidence,
        }
    )


def _ambiguous_alternatives(
    direct: Sequence[Interpretation],
    occurrences: Sequence[Occurrence],
    scope: CaptureScope,
    recorded_at: datetime,
) -> Alternatives:
    """Each ambiguous line's group under every entry it matched, keyed by occurrence id.

    The line is read as if each candidate entry alone matched, only to find the
    construction group it would join; the reading itself is never stored.
    """
    alternatives: dict[int, tuple[tuple[str, GroupKey], ...]] = {}
    for item, occurrence in zip(direct, occurrences, strict=True):
        entry_ids = item.transform_trace.get(TRACE_MATCHED_ENTRY_IDS)
        if item.mapping_entry_id is not None or not isinstance(entry_ids, Sequence):
            continue
        found: list[tuple[str, GroupKey]] = []
        for entry_id in entry_ids:
            reading = interpret(
                occurrence,
                entity_id=scope.entity_id,
                basis=scope.basis,
                framework=scope.framework,
                mapping_set=scope.mapping_set,
                policy=scope.policy,
                dictionary=scope.dictionary,
                fiscal_year_end_month=scope.fiscal_year_end_month,
                qualification=_unproven(occurrence, scope),
                recorded_at=recorded_at,
                as_entry=scope.mapping_set.entry(str(entry_id)),
            )
            group_key = _group_key(reading)
            if group_key is not None:
                found.append((str(entry_id), group_key))
        assert occurrence.occurrence_id is not None
        alternatives[occurrence.occurrence_id] = tuple(found)
    return alternatives


def _constructions(
    direct: Sequence[Interpretation],
    scope: CaptureScope,
    *,
    schemas: frozenset[str],
    proofs: Mapping[ProofKey, Mapping[str, ProvenCondition]],
    alternatives: Alternatives,
    recorded_at: datetime,
) -> list[Interpretation]:
    """Every construction of the capture, one per rule and (period, dimensions) group."""
    built: list[Interpretation] = []
    for rule in scope.mapping_set.constructions:
        if (
            not applies_to_source(rule.source, scope.capture.source_id)
            or rule.surface != scope.capture.surface
            or rule.schema_identity not in schemas
        ):
            continue
        for group_key, found in sorted(
            _groups(rule, direct, alternatives).items(), key=lambda pair: _group_order(pair[0])
        ):
            operands = {name: items[0] for name, items in found.items() if len(items) == 1}
            duplicates = {name: items for name, items in found.items() if len(items) > 1}
            if duplicates:
                _LOG.warning(
                    _DUPLICATE_OPERAND, rule_id=rule.rule_id, period=group_key[0].canonical()
                )
            context = _construction_context(rule, [*found.values()], scope, proofs)
            built.append(
                construct(
                    rule,
                    operands,
                    dash_rules=scope.policy,
                    qualification=context,
                    recorded_at=recorded_at,
                    duplicates=duplicates,
                    group=group_key,
                )
            )
    return built


def _groups(
    rule: ConstructionRule, direct: Sequence[Interpretation], alternatives: Alternatives
) -> Mapping[GroupKey, Mapping[str, tuple[Interpretation, ...]]]:
    """Every operand candidate per (period, dimensions) group and operand name.

    An ambiguous line joins the group of every operand entry it matched, so the
    construction is ``INVALID`` (invalid beats missing), never built without it.
    """
    names = {operand.mapping_entry_id: operand.name for operand in rule.operands}
    groups: dict[GroupKey, dict[str, tuple[Interpretation, ...]]] = {}

    def join(group_key: GroupKey, name: str, item: Interpretation) -> None:
        group = groups.setdefault(group_key, {})
        group[name] = (*group.get(name, ()), item)

    for item in direct:
        occurrence_id = item.occurrence_id
        if (
            item.mapping_entry_id is None
            and occurrence_id is not None
            and occurrence_id in alternatives
        ):
            for entry_id, alternative_group in alternatives[occurrence_id]:
                if entry_id in names:
                    join(alternative_group, names[entry_id], item)
            continue
        if item.mapping_entry_id not in names:
            continue
        group_key = _group_key(item)
        if group_key is None:
            if item.status is InterpretationStatus.INVALID:
                _LOG.warning(
                    _UNGROUPED, rule_id=rule.rule_id, interpretation=item.interpretation_id
                )
            continue
        join(group_key, names[item.mapping_entry_id], item)
    return groups


def _group_key(item: Interpretation) -> GroupKey | None:
    """A keyed row's (period, dimensions); an ``INVALID`` keyless row's evidenced ones.

    A unit-mismatched row keeps its key period and dimensions; other keyless rows join
    no group.
    """
    if item.key is not None:
        return item.key.period, item.key.dimensions
    if (
        item.status is not InterpretationStatus.INVALID
        or item.period is None
        or item.dimensions is None
    ):
        return None
    return item.period, item.dimensions


def _group_order(group_key: GroupKey) -> tuple[str, str]:
    """A deterministic order of groups, so reserved ids map the same way in both passes."""
    period, dimensions = group_key
    return str(period.canonical()), dimensions.digest()


def _construction_context(
    rule: ConstructionRule,
    candidates: Sequence[tuple[Interpretation, ...]],
    scope: CaptureScope,
    proofs: Mapping[ProofKey, Mapping[str, ProvenCondition]],
) -> QualificationContext:
    """The constructed measurement's own context (its key is any keyed operand's).

    A group with no keyed operand (every operand ``INVALID`` and keyless) builds an
    ``INVALID`` construction, so its context is the unproven one of its period.
    """
    key = next((item.key for items in candidates for item in items if item.key), None)
    if key is None:
        first = candidates[0][0]
        assert first.period is not None
        return QualificationContext(
            schema_identity=rule.schema_identity,
            surface=scope.capture.surface,
            basis=scope.basis,
            period_kind=first.period.kind(scope.fiscal_year_end_month),
            proven={},
        )
    return qualification_context(
        key,
        schema_identity=rule.schema_identity,
        surface=scope.capture.surface,
        fiscal_year_end_month=scope.fiscal_year_end_month,
        proven=proofs.get((key.period, key.basis), {}),
    )


def _with_cause(
    item: Interpretation,
    scope: CaptureScope,
    prior: Sequence[Interpretation],
    prior_anchor_keys: Mapping[int, str],
    anchors: Mapping[int | None, str],
) -> Interpretation:
    """Reprocessing cause and predecessor when a prior-triple row of the same identity exists."""
    predecessor = _predecessor(item, prior, prior_anchor_keys, anchors)
    if predecessor is None:
        return item
    if predecessor.extractor_version != item.extractor_version:
        cause = RevisionCause.PARSER_REEXTRACTION
    elif predecessor.normalisation_policy_version != scope.policy.version:
        cause = RevisionCause.NORMALISATION_POLICY_CHANGE
    else:
        return item
    return item.model_copy(
        update={
            "revision_cause": cause,
            "supersedes_interpretation_id": predecessor.interpretation_id,
        }
    )


def _predecessor(
    item: Interpretation,
    prior: Sequence[Interpretation],
    prior_anchor_keys: Mapping[int, str],
    anchors: Mapping[int | None, str],
) -> Interpretation | None:
    """The latest prior-triple row of the same anchor and entry (or rule and key)."""
    if item.origin is InterpretationOrigin.DIRECT:
        anchor = anchors.get(item.occurrence_id)
        matches = [
            candidate
            for candidate in prior
            if candidate.occurrence_id is not None
            and prior_anchor_keys.get(candidate.occurrence_id) == anchor
            and candidate.mapping_entry_id == item.mapping_entry_id
        ]
    else:
        digest = item.key.digest() if item.key is not None else None
        matches = [
            candidate
            for candidate in prior
            if candidate.construction_rule_id == item.construction_rule_id
            and candidate.key is not None
            and candidate.key.digest() == digest
        ]
    return max(matches, key=lambda candidate: candidate.interpretation_id or 0, default=None)
