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

from fundamentals.compare.definitions import DefinitionSet
from fundamentals.compare.run_models import RunInput
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    CaptureReference,
    FilingPackage,
    Interpretation,
    Occurrence,
)
from fundamentals.evidence.alignment import AlignmentProof
from fundamentals.evidence.repository import (
    BasisStatusRecord,
    EvidenceInputRecord,
    SegmentMemberRecord,
    SettingsRecord,
)
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.evidence.repository_rows import PackageStatementRecord


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


def first_party_inputs(inputs: ResolvedInputs) -> ResolvedInputs:
    """Project the exact closed inputs into the existing first-party engine.

    Vendor native operands remain in the complete manifest and never enter a
    first-party selection or formula calculation.
    """
    first_party = (Representation.XBRL, Representation.PDF)
    capture_ids = {
        member.capture.capture_ref_id
        for package in inputs.packages
        for member in package.members.values()
    }
    capture_ids.update(
        item.capture.capture_ref_id
        for item in inputs.attempts
        if item.representation in first_party and item.capture is not None
    )
    return inputs.model_copy(
        update={
            "capture_refs": tuple(
                row for row in inputs.capture_refs if row.capture_ref_id in capture_ids
            ),
            "occurrences": tuple(
                row for row in inputs.occurrences if row.representation in first_party
            ),
            "interpretations": tuple(
                row for row in inputs.interpretations if row.representation in first_party
            ),
            "attempts": tuple(row for row in inputs.attempts if row.representation in first_party),
        }
    )


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
