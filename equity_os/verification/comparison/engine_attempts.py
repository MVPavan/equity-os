"""Fiscal periods and attempt-to-state for one run (D1a Task 9).

Attempt-to-state is decided per (entity, period end, basis, representation, statement family)
before member presence: a failed or missing attempt imposes ``UNAVAILABLE`` or ``INVALID``
whatever the package holds, so a failed read is never reported as absence. Only attempts and
members on the run's requested sources (first-party surfaces) may decide a side.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta

from equity_os.contracts.measurement.canonical import Representation, StatementFamily
from equity_os.contracts.measurement.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    FilingPackage,
    InterpretationTriple,
    KeySelection,
    PackageMember,
    RunMode,
)
from equity_os.contracts.measurement.measurement_key import MeasurementKey, PeriodInterval
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome, outcome_source_state
from equity_os.contracts.verification.comparison import SelectionSource, SourceState
from equity_os.extraction.packages.first_party_extract import unsupported_schema_context
from equity_os.verification.comparison.engine_rows import Cell
from equity_os.verification.comparison.selection import NOT_EXTRACTED_UNDER_PINS, period_end

_ONE_DAY = timedelta(days=1)
_MONTHS = 12
_QUARTER_MONTHS = 3
_NOT_MONTH_END = "period end {period_end} is not a month end"
_NOT_QUARTER_END = "period end {period_end} is not a fiscal quarter end for year-end month {month}"
INCOMPATIBLE_EXTRACTION_CONTEXTS = "INCOMPATIBLE_EXTRACTION_CONTEXTS"


class RunResolutionError(RuntimeError):
    """A run cannot be resolved from the evidence it may read (fail closed, nothing stored)."""


def fiscal_periods(period_end_: date, fiscal_year_end_month: int) -> tuple[PeriodInterval, ...]:
    """The fiscal quarter ending at ``period_end_`` and the fiscal year-to-date, if longer."""
    if (period_end_ + _ONE_DAY).day != 1:
        raise RunResolutionError(_NOT_MONTH_END.format(period_end=period_end_))
    months = (period_end_.month - fiscal_year_end_month) % _MONTHS or _MONTHS
    if months % _QUARTER_MONTHS:
        raise RunResolutionError(
            _NOT_QUARTER_END.format(period_end=period_end_, month=fiscal_year_end_month)
        )
    quarter = PeriodInterval.duration(_month_start(period_end_, _QUARTER_MONTHS - 1), period_end_)
    year_to_date = PeriodInterval.duration(_month_start(period_end_, months - 1), period_end_)
    return (quarter,) if quarter == year_to_date else (quarter, year_to_date)


def attempt_available(
    attempt: AcquisitionAttempt, *, cutoff: datetime, mode: RunMode, extractor: str
) -> bool:
    """Availability under a cutoff, mode and pinned extractor (data spec l.400–407).

    Acquisition attempts by ``attempted_at`` in both modes; extraction attempts only under
    the pinned extractor, by ``attempted_at`` in ``AS_KNOWN`` and by capture eligibility in
    ``RETROSPECTIVE``.
    """
    attempted_at = attempt.attempted_at
    assert attempted_at is not None
    if attempt.stage is AttemptStage.ACQUISITION:
        return attempted_at <= cutoff
    if attempt.extractor_version != extractor:
        return False
    if mode is RunMode.AS_KNOWN:
        return attempted_at <= cutoff
    return attempt.capture is not None and attempt.capture.first_seen_at <= cutoff


def pdf_contexts_conflict(
    attempts: Sequence[AcquisitionAttempt],
    *,
    capture_ref_id: int,
    cutoff: datetime,
    mode: RunMode,
    extractor: str,
) -> bool:
    """Whether PDF occurrences cannot be bound to one available location context.

    Occurrences currently carry no generation context. Different context hashes, including
    legacy unknown context alongside a known one, cannot safely share those occurrences.
    """
    contexts = {
        attempt.extraction_context_sha256
        for attempt in attempts
        if attempt.representation is Representation.PDF
        and attempt.stage is AttemptStage.EXTRACTION
        and attempt.statement_family is None
        and _capture_id(attempt) == capture_ref_id
        and attempt_available(attempt, cutoff=cutoff, mode=mode, extractor=extractor)
    }
    return len(contexts) > 1


class AttemptStates:
    """The state an attempt imposes on one request side (data spec l.353, 400–425)."""

    def __init__(
        self,
        attempts: Sequence[AcquisitionAttempt],
        *,
        member_captures: Iterable[int],
        cutoff: datetime,
        mode: RunMode,
        triple: InterpretationTriple,
        surfaces: Iterable[str],
        prerequisites: Iterable[tuple[Representation, str]] = (),
    ) -> None:
        self._attempts = tuple(attempts)
        self._surfaces = frozenset(surfaces)
        self._prerequisites = frozenset(prerequisites)
        self._member_captures = frozenset(member_captures)
        self._cutoff = cutoff
        self._mode = mode
        self._triple = triple

    def state(
        self,
        key: MeasurementKey,
        representation: Representation,
        family: StatementFamily,
        package: FilingPackage | None,
    ) -> Cell | None:
        """The imposed cell, or ``None`` when selection decides.

        First match wins: a failed latest prerequisite acquisition (the SHP listing, plan D8
        R8) or a failed latest acquisition with no member; a non-``COMPLETE`` overall attempt
        of the latest pinned-extractor generation; a non-``COMPLETE`` family attempt in that
        generation; a member with no available generation.
        """
        member = self._member(package, representation)
        prerequisite = [
            attempt
            for attempt in self._attempts
            if (representation, attempt.surface) in self._prerequisites
            and attempt.stage is AttemptStage.ACQUISITION
            and (attempt.entity_id, attempt.period_end) == (key.entity_id, period_end(key.period))
            and attempt.basis is key.basis
            and attempt_available(attempt, cutoff=self._cutoff, mode=self._mode, extractor="")
        ]
        if member is None and prerequisite:
            latest = max(prerequisite, key=_attempt_order)
            if latest.outcome is not ExtractionOutcome.COMPLETE:
                return _imposed(key, representation, package, latest)
        candidates = [
            attempt
            for attempt in self._attempts
            if self._candidate(attempt, key, representation, package)
        ]
        acquisitions = [item for item in candidates if item.stage is AttemptStage.ACQUISITION]
        if member is None and acquisitions:
            latest = max(acquisitions, key=_attempt_order)
            if latest.outcome is not ExtractionOutcome.COMPLETE:
                return _imposed(key, representation, package, latest)
        extractions = [item for item in candidates if item.stage is AttemptStage.EXTRACTION]
        overall = [item for item in extractions if item.statement_family is None]
        if (
            representation is Representation.PDF
            and member is not None
            and pdf_contexts_conflict(
                overall,
                capture_ref_id=member.capture.capture_ref_id or 0,
                cutoff=self._cutoff,
                mode=self._mode,
                extractor=self._triple.extractor(representation),
            )
        ):
            return Cell(
                selection=bare_selection(
                    key,
                    representation,
                    SourceState.UNAVAILABLE,
                    package=package,
                    reason=INCOMPATIBLE_EXTRACTION_CONTEXTS,
                ),
                attempt_id=max(overall, key=_attempt_order).attempt_id,
            )
        if overall:
            generation = max(overall, key=_attempt_order)
            if generation.outcome is not ExtractionOutcome.COMPLETE:
                return _imposed(key, representation, package, generation)
            failed = [
                item
                for item in extractions
                if item.statement_family is family
                and _capture_id(item) == _capture_id(generation)
                and item.extraction_context_sha256 == generation.extraction_context_sha256
                and (
                    item.attempted_at == generation.attempted_at
                    or (package is not None and item.package_id == package.package_id)
                )
                and item.outcome is not ExtractionOutcome.COMPLETE
            ]
            if failed:
                return _imposed(key, representation, package, min(failed, key=_attempt_order))
        elif member is not None:
            return Cell(
                selection=bare_selection(
                    key,
                    representation,
                    SourceState.UNAVAILABLE,
                    package=package,
                    reason=NOT_EXTRACTED_UNDER_PINS,
                ),
                attempt_id=None,
            )
        return None

    def _candidate(
        self,
        attempt: AcquisitionAttempt,
        key: MeasurementKey,
        representation: Representation,
        package: FilingPackage | None,
    ) -> bool:
        """Whether an attempt may decide this request side."""
        if (
            attempt.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
            and attempt.extraction_context_sha256 is not None
            and attempt.extraction_context_sha256
            != unsupported_schema_context(self._triple.mapping_set)
        ):
            return False
        if (
            attempt.surface not in self._surfaces
            or attempt.entity_id != key.entity_id
            or attempt.period_end != period_end(key.period)
            or attempt.basis is not key.basis
            or attempt.framework is not key.framework
            or attempt.representation is not representation
            or not attempt_available(
                attempt,
                cutoff=self._cutoff,
                mode=self._mode,
                extractor=self._triple.extractor(representation),
            )
        ):
            return False
        member = self._member(package, representation)
        own_package = package is not None and attempt.package_id == package.package_id
        if member is not None:
            capture = member.capture
            return (
                attempt.source_id == capture.source_id
                and attempt.surface == capture.surface
                and (own_package or _capture_id(attempt) == capture.capture_ref_id)
            )
        if own_package:
            return True
        captured = _capture_id(attempt)
        return attempt.package_id is None and (
            captured is None or captured not in self._member_captures
        )

    def _member(
        self, package: FilingPackage | None, representation: Representation
    ) -> PackageMember | None:
        """A package's member on a requested source, if any."""
        member = None if package is None else package.members.get(representation)
        return member if member is not None and member.capture.surface in self._surfaces else None


def _imposed(
    key: MeasurementKey,
    representation: Representation,
    package: FilingPackage | None,
    attempt: AcquisitionAttempt,
) -> Cell:
    """A cell whose state the attempt's outcome decides."""
    state = outcome_source_state(attempt.outcome)
    assert state is not None
    return Cell(
        selection=bare_selection(
            key, representation, state, package=package, reason=attempt.outcome.value
        ),
        attempt_id=attempt.attempt_id,
    )


def _month_start(day: date, months_back: int) -> date:
    """The first day of the month ``months_back`` months before ``day``'s month."""
    index = day.year * _MONTHS + day.month - 1 - months_back
    return date(index // _MONTHS, index % _MONTHS + 1, 1)


def nine_months(periods: tuple[PeriodInterval, ...]) -> PeriodInterval:
    """The fiscal year's first nine months, given (Q4, FY)."""
    quarter, year = periods
    assert quarter.start is not None and year.start is not None
    return PeriodInterval.duration(year.start, quarter.start - _ONE_DAY)


def _attempt_order(attempt: AcquisitionAttempt) -> tuple[datetime, int]:
    """Attempts by time, then id."""
    assert attempt.attempted_at is not None
    return attempt.attempted_at, attempt.attempt_id or 0


def _capture_id(attempt: AcquisitionAttempt) -> int | None:
    """The capture an attempt read, if any."""
    return None if attempt.capture is None else attempt.capture.capture_ref_id


def bare_selection(
    key: MeasurementKey,
    representation: Representation,
    state: SourceState,
    *,
    package: FilingPackage | None = None,
    reason: str | None = None,
) -> KeySelection:
    """A selection decided without reading an interpretation."""
    return KeySelection(
        key=key,
        representation=representation,
        state=state,
        interpretation=None,
        package_id=None if package is None else package.package_id,
        source=SelectionSource.PACKAGE_AS_REPORTED,
        reason=reason,
        considered_interpretation_ids=(),
        surfaced_restatements=(),
    )
