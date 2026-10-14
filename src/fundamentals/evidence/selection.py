"""Package, key and interpretation selection under an eligibility boundary and mode (D1a Task 6).

A package is eligible when it was filed by the knowledge cutoff and every member was stored
by the first-seen cutoff (design decision 5). Within one family the newest eligible package
heads its lineage; a correction naming replaced statements is selected only for those
statements, and the walk falls back through ``supersedes_package_id`` for the rest. A
package reaches occurrences and interpretations only through its member captures.
Candidates are interpretations under the pinned (mapping set, normalisation policy,
extractor) triple — in ``AS_KNOWN`` also recorded by the cutoff — minus any superseded by
another candidate. Nothing here is ever zero-filled: absence is ``NO_VALUE`` or
``UNAVAILABLE`` with a reason.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime

from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.comparison import SelectionSource, SourceState
from fundamentals.contracts.evidence import (
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationStatus,
    InterpretationTriple,
    KeySelection,
    KnowledgeTimeStatus,
    Occurrence,
    PinnedVersions,
    RunMode,
)
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework

INTERPRETATION_AMBIGUOUS = "INTERPRETATION_AMBIGUOUS"
NO_ELIGIBLE_PACKAGE = "NO_ELIGIBLE_PACKAGE"
NOT_EXTRACTED_UNDER_PINS = "NOT_EXTRACTED_UNDER_PINS"
NOT_INTERPRETED_UNDER_PINS = "NOT_INTERPRETED_UNDER_PINS"

Pins = PinnedVersions | InterpretationTriple
SelectionOutcome = tuple[SourceState, Interpretation | None, str | None]


def is_eligible(occurrence: Occurrence, boundary: EligibilityBoundary) -> bool:
    """Filed by the knowledge cutoff and stored by the first-seen cutoff.

    A source with no publication time (knowledge time ``UNKNOWN``, spec §4) is available
    from its verified capture registration time, never earlier.
    """
    if occurrence.knowledge_time_status is KnowledgeTimeStatus.UNKNOWN:
        available = max(occurrence.capture.registered_at, occurrence.first_seen_at)
        return available <= min(boundary.knowledge_cutoff, boundary.first_seen_cutoff)
    return (
        occurrence.knowledge_time is not None
        and occurrence.knowledge_time_status is KnowledgeTimeStatus.KNOWN
        and occurrence.knowledge_time <= boundary.knowledge_cutoff
        and occurrence.first_seen_at <= boundary.first_seen_cutoff
    )


def select_package(
    packages: Sequence[FilingPackage],
    *,
    entity_id: int,
    family: FilingFamily,
    statement_family: StatementFamily,
    basis: Basis,
    framework: AccountingFramework,
    period_end: date,
    boundary: EligibilityBoundary,
) -> FilingPackage | None:
    """The package supplying ``statement_family`` for one period end, or ``None``.

    The head is the newest eligible package no eligible package supersedes (knowledge
    time, then latest member first-seen, then id). Its lineage is walked back until a
    package replaces the whole package (no named statements) or names this statement.
    A broken lineage (predecessor not eligible) selects nothing.
    """
    eligible = [
        package
        for package in packages
        if package.entity_id == entity_id
        and package.family is family
        and package.basis is basis
        and package.framework is framework
        and package.reporting_period_end == period_end
        and package.eligible(boundary)
        and all(
            member.knowledge_time_status is KnowledgeTimeStatus.KNOWN
            and member.knowledge_time <= boundary.knowledge_cutoff
            for member in package.members.values()
        )
    ]
    superseded = {package.supersedes_package_id for package in eligible}
    heads = [package for package in eligible if package.package_id not in superseded]
    if not heads:
        return None
    by_id = {package.package_id: package for package in eligible}
    current: FilingPackage | None = max(heads, key=_recency)
    while current is not None:
        if not current.replaced_statements or statement_family in current.replaced_statements:
            return current
        predecessor = current.supersedes_package_id
        current = None if predecessor is None else by_id.get(predecessor)
    return None


def as_reported_periods(
    package: FilingPackage, occurrences: Sequence[Occurrence]
) -> frozenset[PeriodInterval]:
    """Periods of the package's own occurrences that end on its reporting-period end."""
    captures = _member_captures(package)
    return frozenset(
        occurrence.period
        for occurrence in occurrences
        if occurrence.capture.capture_ref_id in captures
        and occurrence.period is not None
        and period_end(occurrence.period) == package.reporting_period_end
    )


def select_interpretation(
    candidates: Sequence[Interpretation],
    *,
    boundary: EligibilityBoundary,
    mode: RunMode,
    pinned: Pins,
) -> SelectionOutcome:
    """The one current candidate under the pins, its source state and reason.

    No candidate left gives ``NO_VALUE`` (the caller decides whether the capture was
    interpreted under the pins at all); two or more give ``INVALID`` with
    ``INTERPRETATION_AMBIGUOUS`` and no interpretation, never a first match.
    """
    triple = _triple(pinned)
    available = [
        item
        for item in candidates
        if _under(item, triple) and _known(item.recorded_at, boundary, mode)
    ]
    current = _current(available)
    if not current:
        return SourceState.NO_VALUE, None, None
    if len(current) > 1:
        return SourceState.INVALID, None, INTERPRETATION_AMBIGUOUS
    (chosen,) = current
    if chosen.status is InterpretationStatus.MAPPED:
        state = SourceState.VALUE if chosen.value is not None else SourceState.NO_VALUE
        return state, chosen, None
    reason = chosen.reason.value if chosen.reason is not None else chosen.status.value
    return SourceState.INVALID, chosen, reason


def select_key(
    key: MeasurementKey,
    representation: Representation,
    *,
    package: FilingPackage | None,
    occurrences: Sequence[Occurrence],
    interpretations: Sequence[Interpretation],
    boundary: EligibilityBoundary,
    mode: RunMode,
    pinned: Pins,
) -> KeySelection:
    """One key's selection in one representation of a selected package.

    No package: ``NO_VALUE`` (``NO_ELIGIBLE_PACKAGE``). No member for the representation:
    ``NO_VALUE``. A member capture with no occurrence under the pinned extractor is
    ``UNAVAILABLE`` (``NOT_EXTRACTED_UNDER_PINS``); one with no available interpretation
    under the pinned triple is ``UNAVAILABLE`` (``NOT_INTERPRETED_UNDER_PINS``); an
    interpreted capture lacking the line is ``NO_VALUE``.
    """
    if package is None:
        return _selection(key, representation, SourceState.NO_VALUE, reason=NO_ELIGIBLE_PACKAGE)
    member = package.members.get(representation)
    if member is None:
        return _selection(key, representation, SourceState.NO_VALUE, package=package)
    capture_ref_id = member.capture.capture_ref_id
    triple = _triple(pinned)
    owned = [item for item in interpretations if item.capture_ref_id == capture_ref_id]
    considered = _ids([item for item in owned if matches_key(item, key)])
    available = [
        item for item in owned if _under(item, triple) and _known(item.recorded_at, boundary, mode)
    ]
    candidates = [item for item in _current(available) if matches_key(item, key)]
    extractor = triple.extractor(representation)
    if not any(
        item.capture.capture_ref_id == capture_ref_id and item.extractor_version == extractor
        for item in occurrences
    ):
        return _selection(
            key,
            representation,
            SourceState.UNAVAILABLE,
            package=package,
            reason=NOT_EXTRACTED_UNDER_PINS,
            considered=considered,
        )
    if not any(_under(item, triple) and _known(item.recorded_at, boundary, mode) for item in owned):
        return _selection(
            key,
            representation,
            SourceState.UNAVAILABLE,
            package=package,
            reason=NOT_INTERPRETED_UNDER_PINS,
            considered=considered,
        )
    state, chosen, reason = select_interpretation(
        candidates, boundary=boundary, mode=mode, pinned=triple
    )
    return KeySelection(
        key=key,
        representation=representation,
        state=state,
        interpretation=chosen,
        package_id=package.package_id,
        source=SelectionSource.PACKAGE_AS_REPORTED,
        reason=reason,
        considered_interpretation_ids=tuple(
            item for item in considered if chosen is None or item != chosen.interpretation_id
        ),
        surfaced_restatements=(),
    )


def select_opening_operand(
    key: MeasurementKey,
    representation: Representation,
    *,
    output_package: FilingPackage,
    package_occurrences: Sequence[Occurrence],
    package_interpretations: Sequence[Interpretation],
    boundary: EligibilityBoundary,
    mode: RunMode,
    pinned: Pins,
    fallback: Callable[[], KeySelection],
) -> KeySelection:
    """An opening instant from the output package's own disclosure, else the fallback.

    Only an absent disclosure (no candidate under the pins, or no member) falls back. A
    disclosed line that is nil, invalid, ambiguous or uninterpreted under the pins keeps
    the package's own state: another package's value never silently replaces it.
    """
    own = select_key(
        key,
        representation,
        package=output_package,
        occurrences=package_occurrences,
        interpretations=package_interpretations,
        boundary=boundary,
        mode=mode,
        pinned=pinned,
    )
    if own.state is SourceState.NO_VALUE and own.interpretation is None:
        return fallback()
    return own.model_copy(update={"source": SelectionSource.PACKAGE_OPENING_DISCLOSURE})


def differing_restatement(
    selected: KeySelection, comparatives: Sequence[Interpretation]
) -> tuple[int, ...]:
    """Ids of comparatives for the selected key whose interval misses the selected interval.

    A selection without a value and interval, or a comparative without an interval,
    names nothing: a difference is only claimed between two bounded values.
    """
    chosen = selected.interpretation
    if selected.state is not SourceState.VALUE or chosen is None or chosen.interval is None:
        return ()
    return tuple(
        sorted(
            item.interpretation_id
            for item in comparatives
            if item.interpretation_id is not None
            and item.interpretation_id != chosen.interpretation_id
            and item.key == selected.key
            and item.interval is not None
            and not item.interval.intersects(chosen.interval)
        )
    )


def period_end(period: PeriodInterval) -> date:
    """The last day a period covers: a duration's end, or the instant."""
    end = period.instant if period.instant is not None else period.end
    assert end is not None
    return end


def _triple(pinned: Pins) -> InterpretationTriple:
    """The interpretation versions of either pin form."""
    return pinned.triple() if isinstance(pinned, PinnedVersions) else pinned


def _current(items: Sequence[Interpretation]) -> list[Interpretation]:
    """Remove superseded interpretations across the entire eligible pinned generation."""
    superseded = {item.supersedes_interpretation_id for item in items}
    return [item for item in items if item.interpretation_id not in superseded]


def matches_key(item: Interpretation, key: MeasurementKey) -> bool:
    """Match a complete key, or every evidenced part of an invalid incomplete key.

    Unknown unit semantics never become an invented currency or value kind. A partial
    key must still establish its canonical row, period and dimensions to match here.
    """
    if item.key is not None:
        return item.key == key
    partial = (
        item.status is InterpretationStatus.INVALID
        and item.entity_id == key.entity_id
        and item.canonical_id == key.canonical_id
        and item.period == key.period
        and item.basis is key.basis
        and item.framework is key.framework
        and item.dimensions == key.dimensions
    )
    if partial or item.status is not InterpretationStatus.INVALID:
        return partial
    candidates = item.transform_trace.get("ambiguous_candidate_keys", ())
    expected = key.model_dump(mode="json")
    return isinstance(candidates, list | tuple) and any(
        isinstance(candidate, dict)
        and all(
            candidate.get(part) == expected[part]
            for part in (
                "entity_id",
                "canonical_id",
                "period",
                "basis",
                "framework",
                "dimensions",
            )
        )
        and (
            candidate.get("value_kind") is None
            or (
                candidate.get("value_kind") == expected["value_kind"]
                and candidate.get("currency") == expected["currency"]
            )
        )
        for candidate in candidates
    )


def _under(item: Interpretation, triple: InterpretationTriple) -> bool:
    """Whether an interpretation is under the pinned triple for its representation."""
    return (
        item.mapping_set_version == triple.mapping_set
        and item.normalisation_policy_version == triple.normalisation_policy
        and item.extractor_version == triple.extractor(item.representation)
    )


def _known(recorded_at: datetime, boundary: EligibilityBoundary, mode: RunMode) -> bool:
    """``AS_KNOWN`` sees only records stored by the cutoff; ``RETROSPECTIVE`` sees all."""
    return mode is RunMode.RETROSPECTIVE or recorded_at <= boundary.first_seen_cutoff


def _recency(package: FilingPackage) -> tuple[datetime, datetime, int]:
    """Order packages by knowledge time, then latest member first-seen, then id."""
    first_seen = max(member.capture.first_seen_at for member in package.members.values())
    return package.knowledge_time, first_seen, package.package_id or 0


def _member_captures(package: FilingPackage) -> frozenset[int | None]:
    """The capture ids of a package's members."""
    return frozenset(member.capture.capture_ref_id for member in package.members.values())


def _ids(items: Sequence[Interpretation]) -> tuple[int, ...]:
    """Stored ids, sorted."""
    return tuple(sorted(item.interpretation_id for item in items if item.interpretation_id))


def _selection(
    key: MeasurementKey,
    representation: Representation,
    state: SourceState,
    *,
    package: FilingPackage | None = None,
    reason: str | None = None,
    considered: tuple[int, ...] = (),
) -> KeySelection:
    """A selection with no interpretation."""
    return KeySelection(
        key=key,
        representation=representation,
        state=state,
        interpretation=None,
        package_id=None if package is None else package.package_id,
        source=SelectionSource.PACKAGE_AS_REPORTED,
        reason=reason,
        considered_interpretation_ids=considered,
        surfaced_restatements=(),
    )
