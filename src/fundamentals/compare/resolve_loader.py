"""The as-of and list reads one run makes before it computes (D1a Task 9).

Only execution reaches this module; replay reloads the stored ids instead. Per entity it
reads the fiscal calendar, basis status and segment members recorded by the cutoff; per
(entity, basis, period end) the eligible results packages (plus the same fiscal year's
nine-month package when a ``YEAR`` package is present), their member captures'
interpretations under the pinned triple, the witness and selected occurrences, and the
available attempts; and finally every eligible comparative of the selected keys. Only members
and attempts on the scope's requested sources (first-party surfaces) are read.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from fundamentals.compare.engine import RUN_FAMILY, RUN_FRAMEWORK
from fundamentals.compare.engine_attempts import attempt_available, fiscal_periods, nine_months
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_models import RunRequest
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    EligibilityBoundary,
    FilingPackage,
    Interpretation,
    Occurrence,
    RunMode,
)
from fundamentals.evidence.interpret import SEGMENT_AXIS
from fundamentals.evidence.repository import (
    BasisStatusRecord,
    EvidenceRepository,
    SegmentMemberRecord,
    SettingsRecord,
)
from fundamentals.evidence.repository_rows import PackageStatementRecord
from fundamentals.pg.identity_seed import SettingKey


class RunLoader:
    """Accumulates one request's evidence through the repository's current reads."""

    def __init__(self, request: RunRequest, repository: EvidenceRepository) -> None:
        self._request = request
        self._repository = repository
        self._boundary = EligibilityBoundary.at(request.cutoff)
        self._triple = request.pinned.triple()
        self._surfaces = frozenset(request.scope.sources)
        self._captures: dict[int, CaptureReference] = {}
        self._packages: dict[int, FilingPackage] = {}
        self._statements: dict[int, PackageStatementRecord] = {}
        self._occurrences: dict[int, Occurrence] = {}
        self._interpretations: dict[int, Interpretation] = {}
        self._attempts: dict[int, AcquisitionAttempt] = {}
        self._settings: dict[int, SettingsRecord] = {}
        self._basis: dict[int, BasisStatusRecord] = {}
        self._segments: dict[int, SegmentMemberRecord] = {}
        self._evidence_ids: set[int] = set()
        self._loaded_captures: set[int] = set()

    def load(self) -> None:
        """Read the request's scope (comparatives come later, from the selected keys)."""
        scope = self._request.scope
        for entity_id in scope.entity_ids:
            self._entity(entity_id)
            for basis in scope.bases:
                for end in scope.period_ends:
                    self._group(entity_id, basis, end)

    def comparatives(self, store: RunStore, digests: Iterable[str]) -> None:
        """Every eligible other-period package holding one of the selected keys."""
        candidates = [
            item
            for item in store.interpretations_by_key_digests(sorted(digests))
            if self._current(item)
        ]
        captures = sorted({item.capture_ref_id for item in candidates})
        package_ids = store.package_ids_of_captures(captures) if captures else ()
        known = set(self._packages)
        fresh = [item for item in package_ids if item not in known]
        added = {
            package.package_id or 0
            for package in self._repository.get_packages(sorted(set(fresh)))
            if self._in_scope(package) and self._add_package(package, interpretations=True)
        }
        # Context refusals and cross-key supersession require the comparative capture's
        # complete eligible evidence, not just interpretations matching the initial digest.
        for package_id in sorted(added):
            package = self._packages[package_id]
            self._period_attempts(package.entity_id, package.basis, package.reporting_period_end)
        self._occurrences_of_interpretations()

    def inputs(self, definition_set_id: int) -> ResolvedInputs:
        """Everything read so far."""
        evidence = self._repository.get_evidence_inputs(sorted(self._evidence_ids))
        return ResolvedInputs(
            capture_refs=_by_id(self._captures),
            packages=_by_id(self._packages),
            package_statements=_by_id(self._statements),
            occurrences=_by_id(self._occurrences),
            interpretations=_by_id(self._interpretations),
            attempts=_by_id(self._attempts),
            evidence_inputs=tuple(evidence),
            settings=_by_id(self._settings),
            basis_statuses=_by_id(self._basis),
            segment_members=_by_id(self._segments),
            definition_set_id=definition_set_id,
        )

    # --- scope ----------------------------------------------------------------------------

    def _entity(self, entity_id: int) -> None:
        """The entity's fiscal calendar, basis status and segment members by the cutoff."""
        cutoff = self._request.cutoff
        repository = self._repository
        settings = repository.settings_as_of(entity_id, SettingKey.FISCAL_YEAR_END_MONTH, cutoff)
        if settings is not None:
            self._settings[settings.id] = settings
            self._evidence_ids.add(settings.evidence_input_id)
        basis = repository.basis_status_as_of(entity_id, cutoff)
        if basis is not None:
            for record in repository.get_basis_statuses([basis[0]]):
                self._basis[record.id] = record
                self._evidence_ids.add(record.evidence_input_id)
        members = repository.segment_members_as_of(entity_id, SEGMENT_AXIS, cutoff)
        for member in members:
            self._segments[member.id] = member
        evidence = sorted({item for member in members for item in member.evidence_occurrence_ids})
        for occurrence in repository.get_occurrences(evidence) if evidence else ():
            assert occurrence.occurrence_id is not None
            self._occurrences[occurrence.occurrence_id] = occurrence

    def _group(self, entity_id: int, basis: Basis, end: date) -> None:
        """Eligible packages (and a ``YEAR`` package's nine-month package) and attempts."""
        ends = [end]
        packages = self._eligible(entity_id, basis, end)
        fiscal_month = self._fiscal_month(entity_id)
        if fiscal_month is not None and any(
            package.reporting_kind is PeriodKind.YEAR for package in packages
        ):
            periods = fiscal_periods(end, fiscal_month)
            if len(periods) == 2:
                nine = nine_months(periods)
                assert nine.end is not None
                ends.append(nine.end)
        for period_end in ends:
            for package in self._eligible(entity_id, basis, period_end):
                self._add_package(package, interpretations=True)
            self._period_attempts(entity_id, basis, period_end)
        self._occurrences_of_interpretations()

    def _period_attempts(self, entity_id: int, basis: Basis, period_end: date) -> None:
        """Attempts of one period end available under the cutoff, mode and pinned extractor."""
        for attempt in self._repository.list_attempts(entity_id, period_end):
            if (
                attempt.surface in self._surfaces
                and attempt.basis is basis
                and attempt.framework is RUN_FRAMEWORK
                and attempt_available(
                    attempt,
                    cutoff=self._request.cutoff,
                    mode=self._request.mode,
                    extractor=self._triple.extractor(attempt.representation),
                )
            ):
                assert attempt.attempt_id is not None
                self._attempts[attempt.attempt_id] = attempt
                capture = attempt.capture
                if capture is not None and capture.capture_ref_id is not None:
                    self._captures[capture.capture_ref_id] = capture

    def _fiscal_month(self, entity_id: int) -> int | None:
        """The loaded fiscal-year-end month, if one was recorded by the cutoff."""
        for record in self._settings.values():
            if record.entity_id == entity_id:
                return int(record.value_text)
        return None

    def _eligible(self, entity_id: int, basis: Basis, period_end: date) -> list[FilingPackage]:
        """Eligible results packages of one basis, framework and period end."""
        return [
            package
            for package in self._repository.list_packages(entity_id, RUN_FAMILY, period_end)
            if package.basis is basis
            and package.framework is RUN_FRAMEWORK
            and package.eligible(self._boundary)
            and any(member.capture.surface in self._surfaces for member in package.members.values())
        ]

    def _in_scope(self, package: FilingPackage) -> bool:
        """An eligible results package of a scoped entity and basis (a comparative's)."""
        scope = self._request.scope
        return (
            package.entity_id in scope.entity_ids
            and package.basis in scope.bases
            and package.framework is RUN_FRAMEWORK
            and package.family is RUN_FAMILY
            and package.eligible(self._boundary)
            and any(member.capture.surface in self._surfaces for member in package.members.values())
        )

    # --- accumulation -----------------------------------------------------------------------

    def _add_package(self, package: FilingPackage, *, interpretations: bool) -> bool:
        """One package, its statements and member captures (and their evidence if asked)."""
        assert package.package_id is not None
        if package.package_id in self._packages:
            return False
        self._packages[package.package_id] = package
        for statement in self._repository.get_package_statements_of([package.package_id]):
            self._statements[statement.id] = statement
        for representation, member in package.members.items():
            capture = member.capture
            assert capture.capture_ref_id is not None
            self._captures[capture.capture_ref_id] = capture
            if capture.surface not in self._surfaces:
                continue
            if interpretations and capture.capture_ref_id not in self._loaded_captures:
                self._loaded_captures.add(capture.capture_ref_id)
                self._capture_evidence(capture, representation)
        return True

    def _capture_evidence(self, capture: CaptureReference, representation: Representation) -> None:
        """A capture's witness occurrence and interpretations under the pinned triple."""
        assert capture.capture_ref_id is not None
        extractor = self._triple.extractor(representation)
        occurrences = self._repository.list_capture_occurrences(capture.capture_ref_id, extractor)
        if occurrences:
            witness = min(occurrences, key=lambda item: item.occurrence_id or 0)
            assert witness.occurrence_id is not None
            self._occurrences[witness.occurrence_id] = witness
        # Every triple known by the cutoff: the pins filter selection and condition evidence,
        # while the reporting currency stays evidenced when nothing is interpreted under them.
        for item in self._repository.list_capture_interpretations(capture.capture_ref_id):
            if self._known(item):
                self._add_interpretation(item)

    def _add_interpretation(self, item: Interpretation) -> None:
        """One interpretation."""
        assert item.interpretation_id is not None
        self._interpretations[item.interpretation_id] = item

    def _occurrences_of_interpretations(self) -> None:
        """The occurrences behind every loaded interpretation."""
        missing = sorted(
            {
                item.occurrence_id
                for item in self._interpretations.values()
                if item.occurrence_id is not None and item.occurrence_id not in self._occurrences
            }
        )
        for occurrence in self._repository.get_occurrences(missing) if missing else ():
            assert occurrence.occurrence_id is not None
            self._occurrences[occurrence.occurrence_id] = occurrence

    def _known(self, item: Interpretation) -> bool:
        """Recorded by the cutoff in ``AS_KNOWN``; any recorded one in ``RETROSPECTIVE``."""
        return (
            self._request.mode is RunMode.RETROSPECTIVE or item.recorded_at <= self._request.cutoff
        )

    def _current(self, item: Interpretation) -> bool:
        """Known by the cutoff and under the pinned triple."""
        return (
            self._known(item)
            and item.mapping_set_version == self._triple.mapping_set
            and item.normalisation_policy_version == self._triple.normalisation_policy
            and item.extractor_version == self._triple.extractor(item.representation)
        )


def _by_id[T](found: dict[int, T]) -> tuple[T, ...]:
    """Values in id order."""
    return tuple(found[item] for item in sorted(found))
