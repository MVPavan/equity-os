"""What a run read, and the only reads a replay may use (D1a Task 9).

``ResolvedInputs`` holds every evidence row a run's results depend on; ``recompute`` is a
pure function of it, so a replay that reloads the same rows by id reproduces the run.
``ReplayReader`` names one immutable by-id read per ``RunInputKind``: no as-of or list read
is reachable from replay.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    FilingPackage,
    Interpretation,
    Occurrence,
)
from equity_os.normalisation.mapping.alignment import AlignmentProof
from equity_os.storage.records.repository import (
    BasisStatusRecord,
    EvidenceInputRecord,
    SegmentMemberRecord,
    SettingsRecord,
)
from equity_os.storage.records.repository_calc import StoredTrace
from equity_os.storage.records.repository_rows import PackageStatementRecord
from equity_os.verification.comparison.definitions import DefinitionSet
from equity_os.verification.comparison.run_models import RunInput


class ResolvedInputs(BaseModel):
    """Every evidence row one run read, plus the dispositioned input list.

    ``definition_set_id`` is the published row of the pinned definition set.
    """

    model_config = ConfigDict(frozen=True)

    capture_refs: tuple[CaptureReference, ...] = ()
    packages: tuple[FilingPackage, ...] = ()
    package_statements: tuple[PackageStatementRecord, ...] = ()
    occurrences: tuple[Occurrence, ...] = ()
    interpretations: tuple[Interpretation, ...] = ()
    attempts: tuple[AcquisitionAttempt, ...] = ()
    proofs: tuple[AlignmentProof, ...] = ()
    traces: tuple[StoredTrace, ...] = ()
    evidence_inputs: tuple[EvidenceInputRecord, ...] = ()
    settings: tuple[SettingsRecord, ...] = ()
    basis_statuses: tuple[BasisStatusRecord, ...] = ()
    segment_members: tuple[SegmentMemberRecord, ...] = ()
    definition_set_id: int
    inputs: tuple[RunInput, ...] = ()


class ReplayReader(Protocol):
    """Immutable by-id reads, one per run input kind; ``EvidenceRepository`` satisfies it."""

    def get_capture_refs(self, ids: Sequence[int]) -> tuple[CaptureReference, ...]:
        """Capture registrations by id."""
        ...

    def get_packages(self, ids: Sequence[int]) -> tuple[FilingPackage, ...]:
        """Packages by id."""
        ...

    def get_package_statements(self, ids: Sequence[int]) -> tuple[PackageStatementRecord, ...]:
        """Package statement roles by id."""
        ...

    def get_occurrences(self, ids: Sequence[int]) -> tuple[Occurrence, ...]:
        """Occurrences by id."""
        ...

    def get_interpretations(self, ids: Sequence[int]) -> tuple[Interpretation, ...]:
        """Interpretations by id."""
        ...

    def get_attempts(self, ids: Sequence[int]) -> tuple[AcquisitionAttempt, ...]:
        """Attempts by id."""
        ...

    def get_alignment_proofs(self, ids: Sequence[int]) -> tuple[AlignmentProof, ...]:
        """Alignment proofs by id."""
        ...

    def get_calculation_traces(self, ids: Sequence[int]) -> tuple[StoredTrace, ...]:
        """Calculation traces by id, with their child traces."""
        ...

    def get_evidence_inputs(self, ids: Sequence[int]) -> tuple[EvidenceInputRecord, ...]:
        """Evidence inputs by id."""
        ...

    def get_settings_records(self, ids: Sequence[int]) -> tuple[SettingsRecord, ...]:
        """Settings records by id."""
        ...

    def get_basis_statuses(self, ids: Sequence[int]) -> tuple[BasisStatusRecord, ...]:
        """Basis-status records by id."""
        ...

    def get_segment_members(self, ids: Sequence[int]) -> tuple[SegmentMemberRecord, ...]:
        """Segment members by id."""
        ...

    def get_definition_set(self, definition_set_id: int) -> DefinitionSet:
        """One published definition set with its records."""
        ...
