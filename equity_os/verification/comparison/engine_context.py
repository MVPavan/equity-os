"""Entity facts a run reads before any value: calendar, basis status, segments (D1a Task 9).

Pure over the run's loaded records and cutoff, so execution and replay decide them alike.
Each read takes the record recorded latest by the cutoff (the fiscal year end: the one
governing the period); none is recorded → the run fails
closed with ``RunResolutionError``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.companies.basis_status import BasisStatus
from equity_os.contracts.measurement.canonical import Basis, ValueKind
from equity_os.contracts.measurement.evidence import Interpretation, Occurrence
from equity_os.normalisation.mapping.interpret import SEGMENT_AXIS
from equity_os.normalisation.mapping.mapping import CONTEXT_BASIS
from equity_os.storage.records.repository import (
    BasisStatusRecord,
    SegmentMemberRecord,
    SettingsRecord,
)
from equity_os.verification.comparison.engine_attempts import RunResolutionError

_NO_FISCAL_YEAR_END = "entity {entity_id} has no fiscal-year-end month recorded by the cutoff"
_NO_BASIS_STATUS = "entity {entity_id} has no basis status recorded by the cutoff"
_BASES = frozenset(basis.value for basis in Basis)
_CURRENCY = "entity {entity_id} period {period_end}: evidenced reporting currencies {found}"


def reporting_currency(
    items: Iterable[Interpretation],
    statuses: Sequence[BasisStatusRecord],
    entity_id: int,
    basis: Basis,
    end: date,
    cutoff: datetime,
) -> str | None:
    """The one reporting currency the group's monetary lines evidence.

    ``None`` for a consolidated request of an evidenced standalone-only entity with no
    consolidated package: no currency is evidenced (none is borrowed from standalone) and
    every row is ``NOT_APPLICABLE`` before any value is read.
    """
    found = {
        item.key.currency
        for item in items
        if item.key is not None
        and item.key.value_kind is ValueKind.CURRENCY_AMOUNT
        and item.key.currency is not None
    }
    if (
        not found
        and basis is Basis.CONSOLIDATED
        and basis_status(statuses, entity_id, cutoff) is BasisStatus.STANDALONE_ONLY
    ):
        return None
    if len(found) != 1:
        raise RunResolutionError(
            _CURRENCY.format(entity_id=entity_id, period_end=end, found=sorted(found))
        )
    return str(next(iter(found)))


def fiscal_year_end(
    settings: Sequence[SettingsRecord], entity_id: int, cutoff: datetime, period_end: date
) -> int:
    """The fiscal-year-end month governing the period by the cutoff: latest ``valid_from``
    on or before it (null last), then latest recorded (``settings_as_of``'s rule, D6 D5)."""
    records = [
        record
        for record in settings
        if record.entity_id == entity_id
        and record.setting_key is SettingKey.FISCAL_YEAR_END_MONTH
        and record.recorded_at <= cutoff
        and (record.valid_from is None or record.valid_from <= period_end)
    ]
    if not records:
        raise RunResolutionError(_NO_FISCAL_YEAR_END.format(entity_id=entity_id))
    return int(
        max(
            records,
            key=lambda record: (
                record.valid_from is not None,
                record.valid_from or date.min,
                record.recorded_at,
                record.id,
            ),
        ).value_text
    )


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
