"""Vendor sides of one result row: selection, pairs and within-vendor conflicts (D1b.2).

Data spec §2, §4, §5. Per requested ``(source, surface)`` the latest available attempt of the
row's period end decides, with no fallback to an older capture: none recorded or any outcome
but ``COMPLETE`` / ``NOT_PUBLISHED`` is ``UNAVAILABLE``, ``NOT_PUBLISHED`` is ``NO_VALUE``. A
complete capture's one current interpretation under the pins decides the cell; a refused one
is ``INVALID``, a capture with nothing interpreted under the pins ``UNAVAILABLE``. Each
mapping table of a surface that maps the row (kind and basis included) is its own side, so
two tables of one vendor (Upstox summary and ``full_statement``) both survive.

Two sides of one vendor on the same key conflict when their intervals are disjoint or their
declared periodicity differs (no precedence between tables is ever recorded); both then carry
``VENDOR_INTERNAL_CONFLICT``, so their pairs are ``NOT_COMPARABLE``. Independent vendors pair
with the first-party representative for the corroboration status. Upstox pairs with it and
with Screener as a diagnostic, and when extraction is not ``AGREE`` every vendor also pairs
with the other first-party representation as a diagnostic. Diagnostics never enter a status.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from fundamentals.compare.engine_rows import Cell, pair_record, representative, selected_side
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import PairRecord, RunRequest, SourceValue
from fundamentals.compare.tables import (
    ComparisonSide,
    SourceQualifiedPair,
    SourceQualifiedSide,
    corroboration_result,
    diagnostic_pair,
)
from fundamentals.contracts.acquisition_outcome import outcome_source_state
from fundamentals.contracts.canonical import ApplicabilityStatus, Representation
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    ReasonCode,
    SelectionSource,
    SourceRef,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    Interpretation,
    InterpretationStatus,
    KeySelection,
    Occurrence,
    RunMode,
)
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.source_catalog import surface_authority
from fundamentals.evidence.selection import (
    INTERPRETATION_AMBIGUOUS,
    NOT_INTERPRETED_UNDER_PINS,
    matches_key,
    period_end,
)

SCREENER = "screener-subscriber"
NO_ATTEMPT = "NO_ATTEMPT"
PERIODICITY = "header_months"  # A JSON occurrence's declared periodicity (months).
_CONFLICT = ReasonCode.VENDOR_INTERNAL_CONFLICT
_REF_FIELDS = set(SourceRef.model_fields)


class VendorSide(BaseModel):
    """One vendor table's side of a row, with the occurrence behind its selection."""

    model_config = ConfigDict(frozen=True)

    qualified: SourceQualifiedSide
    stored: SourceValue
    occurrence: Occurrence | None


class VendorRow(BaseModel):
    """A row's vendor source values, corroboration and diagnostic pairs, and status."""

    model_config = ConfigDict(frozen=True)

    values: tuple[SourceValue, ...]
    pairs: tuple[PairRecord, ...]
    status: CorroborationStatus
    reason: ReasonCode | None


class VendorSides:
    """Vendor selection over one run's loaded inputs (pure, so replay reproduces it)."""

    def __init__(
        self, inputs: ResolvedInputs, request: RunRequest, *, config: LoadedConfig
    ) -> None:
        self._request = request
        self._config = config
        self._triple = request.pinned.triple()
        self._vendors = frozenset(request.scope.vendors)
        self._occurrences = {item.occurrence_id: item for item in inputs.occurrences}
        self._by_capture: dict[int, list[Interpretation]] = defaultdict(list)
        for item in inputs.interpretations:
            self._by_capture[item.capture_ref_id].append(item)
        self._attempts = [
            attempt
            for attempt in inputs.attempts
            if (attempt.source_id, attempt.surface) in self._vendors
        ]
        mapping = config.mapping_set
        tables = [
            (entry.entry_id, entry.source, entry.surface, entry.schema_identity)
            for entry in mapping.entries
        ]
        tables += [
            (rule.rule_id, rule.source, rule.surface, rule.schema_identity)
            for rule in mapping.constructions
        ]
        self._table_of = {rule_id: schema for rule_id, _, _, schema in tables}
        schemas: dict[tuple[str | None, str], set[str]] = defaultdict(set)
        for _, source, surface, schema in tables:
            schemas[(source, surface)].add(schema)
        self._shared = {surface for surface, found in schemas.items() if len(found) > 1}
        self.selected_captures: set[int] = set()

    def row(
        self,
        key: MeasurementKey,
        *,
        fiscal_month: int,
        applicability: ApplicabilityStatus,
        extraction: ExtractionStatus,
        first_party: Mapping[Representation, ComparisonSide],
        vendors: bool = True,
    ) -> VendorRow:
        """The row's vendor sides, pairs and corroboration status (module docstring)."""
        sides = self._sides(key, fiscal_month) if vendors else []
        xbrl, pdf = first_party[Representation.XBRL], first_party[Representation.PDF]
        chosen = representative(xbrl, pdf)
        rep = Representation.XBRL if chosen is xbrl else Representation.PDF
        qualified = [side.qualified for side in sides]
        result = corroboration_result(
            applicability=applicability,
            first_party=_first_party(rep, chosen),
            vendors=qualified,
            definitions=self._config.definition_set,
            policy=self._config.comparison_policy,
        )
        diagnostics = [
            *(
                (_first_party(rep, chosen), side)
                for side in qualified
                if side.ref.source_role is SourceRole.DIAGNOSTIC
            ),
            *(
                (screener, side)
                for side in qualified
                if side.ref.source_role is SourceRole.DIAGNOSTIC
                for screener in qualified
                if screener.ref.source_id == SCREENER
            ),
        ]
        if extraction is not ExtractionStatus.AGREE:
            other = Representation.PDF if rep is Representation.XBRL else Representation.XBRL
            diagnostics.extend(
                (_first_party(other, first_party[other]), side) for side in qualified
            )
        found: list[SourceQualifiedPair] = list(result.pairs)
        for left, right in diagnostics:
            pair = diagnostic_pair(
                left,
                right,
                definitions=self._config.definition_set,
                policy=self._config.comparison_policy,
            )
            if pair is not None:
                found.append(pair)
        return VendorRow(
            values=tuple(side.stored for side in sides),
            pairs=tuple(
                pair_record(pair.pair_kind, pair.left, pair.right, pair.result) for pair in found
            ),
            status=result.status,
            reason=result.reason,
        )

    def _sides(self, key: MeasurementKey, fiscal_month: int) -> list[VendorSide]:
        """One side per requested vendor table mapping the row, conflicts marked."""
        kind = key.period.kind(fiscal_month)
        tables = {
            (rule.source, rule.surface, rule.schema_identity)
            for rule in self._config.mapping_set.entries
            if rule.canonical_id == key.canonical_id
            and key.basis in rule.basis
            and kind in rule.period_kinds
        } | {
            (rule.source, rule.surface, rule.schema_identity)
            for rule in self._config.mapping_set.constructions
            if rule.canonical_id == key.canonical_id
            and (rule.bases is None or key.basis in rule.bases)
        }
        sides = [
            self._side(key, source, surface, schema)
            for source, surface, schema in sorted(
                (source, surface, schema)
                for source, surface, schema in tables
                if source is not None and (source, surface) in self._vendors
            )
        ]
        conflicted = {
            index
            for index, side in enumerate(sides)
            for other in sides
            if other is not side and _same_vendor_conflict(side, other)
        }
        return [
            _conflicted(side) if index in conflicted else side for index, side in enumerate(sides)
        ]

    def _side(self, key: MeasurementKey, source_id: str, surface: str, schema: str) -> VendorSide:
        """One table's state: the latest attempt first, then the capture's interpretation."""
        authority = surface_authority(source_id, surface)
        label = f"{surface}:{schema}" if (source_id, surface) in self._shared else surface
        attempt = self._latest(source_id, surface, key)
        chosen: Interpretation | None = None
        reason: str | None
        if attempt is None:
            state, reason = SourceState.UNAVAILABLE, NO_ATTEMPT
        elif (imposed := outcome_source_state(attempt.outcome)) is not None:
            state, reason = imposed, attempt.outcome.value
        else:
            state, chosen, reason = self._select(key, attempt, schema)
        selection = KeySelection(
            key=key,
            representation=authority.representation,
            state=state,
            interpretation=chosen,
            package_id=None,
            source=SelectionSource.VENDOR_CAPTURE,
            reason=reason,
            considered_interpretation_ids=(),
            surfaced_restatements=(),
        )
        side = selected_side(
            Cell(selection=selection, attempt_id=None if attempt is None else attempt.attempt_id),
            authority.representation,
            proofs=(),
            package_id=None,
            role=authority.role,
            source_id=source_id,
            surface=label,
        )
        return VendorSide(
            qualified=SourceQualifiedSide(
                ref=SourceRef.model_validate(side.stored.model_dump(include=_REF_FIELDS)),
                side=side.comparison,
                interpretation_ids=() if chosen is None else (chosen.interpretation_id or 0,),
                attempt_ids=() if attempt is None else (attempt.attempt_id or 0,),
            ),
            stored=side.stored,
            occurrence=None if chosen is None else self._occurrences.get(chosen.occurrence_id),
        )

    def _latest(
        self, source_id: str, surface: str, key: MeasurementKey
    ) -> AcquisitionAttempt | None:
        """The key's latest attempt whose capture (if any) is registered by the cutoff."""
        found = [
            attempt
            for attempt in self._attempts
            if (attempt.source_id, attempt.surface) == (source_id, surface)
            and attempt.entity_id == key.entity_id
            and attempt.basis is key.basis
            and attempt.period_end == period_end(key.period)
            and (attempt.capture is None or attempt.capture.registered_at <= self._request.cutoff)
        ]
        return max(found, key=lambda item: (item.attempted_at, item.attempt_id), default=None)

    def _select(
        self, key: MeasurementKey, attempt: AcquisitionAttempt, schema: str
    ) -> tuple[SourceState, Interpretation | None, str | None]:
        """The complete capture's one current interpretation of the key in one table."""
        assert attempt.capture is not None and attempt.capture.capture_ref_id is not None
        capture = attempt.capture.capture_ref_id
        self.selected_captures.add(capture)
        extractor = self._triple.extractor(
            attempt.representation, source_id=attempt.source_id, surface=attempt.surface
        )
        pinned = [
            item
            for item in self._by_capture[capture]
            if (item.mapping_set_version, item.normalisation_policy_version, item.extractor_version)
            == (self._triple.mapping_set, self._triple.normalisation_policy, extractor)
            and (
                self._request.mode is RunMode.RETROSPECTIVE
                or item.recorded_at <= self._request.cutoff
            )
        ]
        if not pinned:
            return SourceState.UNAVAILABLE, None, NOT_INTERPRETED_UNDER_PINS
        superseded = {item.supersedes_interpretation_id for item in pinned}
        current = [
            item
            for item in pinned
            if item.interpretation_id not in superseded
            and self._table_of.get(item.mapping_entry_id or item.construction_rule_id or "")
            == schema
            and matches_key(item, key)
        ]
        if not current:
            return SourceState.NO_VALUE, None, None
        if len(current) > 1:
            return SourceState.INVALID, None, INTERPRETATION_AMBIGUOUS
        (chosen,) = current
        if chosen.status is InterpretationStatus.MAPPED:
            state = SourceState.VALUE if chosen.value is not None else SourceState.NO_VALUE
            return state, chosen, None
        return SourceState.INVALID, chosen, (chosen.reason or chosen.status).value


def internal_conflict(
    first: ComparisonSide, other: ComparisonSide, periodicity: tuple[object, object]
) -> bool:
    """Two sides of one vendor's tables on one key contradict each other (spec §2): their
    intervals are disjoint, or their declared periodicities are evidenced and differ."""
    if first.interval is not None and other.interval is not None:
        if not first.interval.intersects(other.interval):
            return True
    return None not in periodicity and periodicity[0] != periodicity[1]


def _same_vendor_conflict(first: VendorSide, other: VendorSide) -> bool:
    """Whether two selected sides of the same vendor conflict."""
    if first.occurrence is None or other.occurrence is None:
        return False
    if first.stored.source_id != other.stored.source_id:
        return False
    return internal_conflict(
        first.qualified.side,
        other.qualified.side,
        (
            first.occurrence.native_context.get(PERIODICITY),
            other.occurrence.native_context.get(PERIODICITY),
        ),
    )


def _conflicted(side: VendorSide) -> VendorSide:
    """A side whose pairs are ``NOT_COMPARABLE`` with ``VENDOR_INTERNAL_CONFLICT``."""
    comparison = side.qualified.side
    return side.model_copy(
        update={
            "qualified": side.qualified.model_copy(
                update={
                    "side": comparison.model_copy(
                        update={"reasons": (_CONFLICT, *comparison.reasons)}
                    )
                }
            ),
            "stored": side.stored.model_copy(update={"reason": _CONFLICT.value}),
        }
    )


def _first_party(representation: Representation, side: ComparisonSide) -> SourceQualifiedSide:
    """A first-party representation as a pair side."""
    return SourceQualifiedSide(
        ref=SourceRef(source_role=SourceRole.FIRST_PARTY, representation=representation),
        side=side,
    )
