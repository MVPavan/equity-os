"""Entity facts a run reads before any value: calendar, basis status, segments (D1a Task 9).

Pure over the run's loaded records and cutoff, so execution and replay decide them alike.
Each read takes the record recorded latest by the cutoff; none is recorded → the run fails
closed with ``RunResolutionError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.evidence import Occurrence
from fundamentals.evidence.interpret import SEGMENT_AXIS
from fundamentals.evidence.mapping import CONTEXT_BASIS
from fundamentals.evidence.repository import (
    BasisStatusRecord,
    SegmentMemberRecord,
    SettingsRecord,
)
from fundamentals.pg.identity_seed import SettingKey

_NO_FISCAL_YEAR_END = "entity {entity_id} has no fiscal-year-end month recorded by the cutoff"
_NO_BASIS_STATUS = "entity {entity_id} has no basis status recorded by the cutoff"
_BASES = frozenset(basis.value for basis in Basis)


def fiscal_year_end(settings: Sequence[SettingsRecord], entity_id: int, cutoff: datetime) -> int:
    """The fiscal-year-end month recorded latest by the cutoff."""
    records = [
        record
        for record in settings
        if record.entity_id == entity_id
        and record.setting_key is SettingKey.FISCAL_YEAR_END_MONTH
        and record.recorded_at <= cutoff
    ]
    if not records:
        raise RunResolutionError(_NO_FISCAL_YEAR_END.format(entity_id=entity_id))
    return int(max(records, key=lambda record: (record.recorded_at, record.id)).value_text)


def basis_status(
    statuses: Sequence[BasisStatusRecord], entity_id: int, cutoff: datetime
) -> BasisStatus:
    """The basis status recorded latest by the cutoff."""
    records = [
        record
        for record in statuses
        if record.entity_id == entity_id and record.recorded_at <= cutoff
    ]
    if not records:
        raise RunResolutionError(_NO_BASIS_STATUS.format(entity_id=entity_id))
    return max(records, key=lambda record: (record.recorded_at, record.id)).basis_status


def segment_members(
    members: Sequence[SegmentMemberRecord], entity_id: int, cutoff: datetime
) -> tuple[SegmentMemberRecord, ...]:
    """The entity's segment members recorded by the cutoff."""
    return tuple(
        record
        for record in members
        if record.entity_id == entity_id
        and record.axis == SEGMENT_AXIS
        and record.recorded_at <= cutoff
    )


def segment_bases(
    members: Sequence[SegmentMemberRecord], occurrences: Mapping[int, Occurrence]
) -> frozenset[Basis]:
    """Bases on which segment members are evidenced by segment-note facts."""
    bases = set()
    for record in members:
        for occurrence_id in record.evidence_occurrence_ids:
            occurrence = occurrences.get(occurrence_id)
            stated = None if occurrence is None else occurrence.native_context.get(CONTEXT_BASIS)
            if stated in _BASES:
                bases.add(Basis(str(stated)))
    return frozenset(bases)
