"""The measurement key shared by adapters, storage, formulas and comparison (data spec §4)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, model_validator

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, ValueKind
from equity_os.contracts.measurement.observation import AccountingFramework

MONTHS_PER_YEAR = 12
_KIND_BY_MONTHS: Mapping[int, PeriodKind] = {
    3: PeriodKind.QUARTER,
    6: PeriodKind.HALF_YEAR,
    9: PeriodKind.NINE_MONTH,
    12: PeriodKind.YEAR,
}
_BAD_SHAPE = "a period is either start and end, or an instant alone"
_REVERSED = "period start {start} is after its end {end}"
_BAD_MONTH = "fiscal year end month must be 1..12, got {month}"
_UNSORTED = "dimension pairs must be sorted by axis with each axis once: {pairs}"


class PeriodInterval(BaseModel):
    """An exact inclusive date interval, or an instant; exactly one shape is valid."""

    model_config = ConfigDict(frozen=True)

    start: date | None = None
    end: date | None = None
    instant: date | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> PeriodInterval:
        """Refuse half-open, mixed or empty shapes."""
        duration = self.start is not None and self.end is not None
        if duration == (self.instant is not None) or (self.start is None) != (self.end is None):
            raise ValueError(_BAD_SHAPE)
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError(_REVERSED.format(start=self.start, end=self.end))
        return self

    @classmethod
    def duration(cls, start: date, end: date) -> PeriodInterval:
        """Build an inclusive duration."""
        return cls(start=start, end=end)

    @classmethod
    def at(cls, instant: date) -> PeriodInterval:
        """Build an instant."""
        return cls(instant=instant)

    def kind(self, fiscal_year_end_month: int) -> PeriodKind:
        """Derive the period kind from the interval and the entity's fiscal calendar.

        A duration must run from the first day of a month to the last day of a
        month. Quarters, halves and nine months must start on a fiscal quarter or
        fiscal-year boundary; a 12-month duration is ``YEAR`` when it starts the
        fiscal year and ``TTM`` when it starts on any other fiscal quarter.
        Anything else is ``OTHER``.
        """
        if not 1 <= fiscal_year_end_month <= MONTHS_PER_YEAR:
            raise ValueError(_BAD_MONTH.format(month=fiscal_year_end_month))
        if self.instant is not None:
            return PeriodKind.INSTANT
        assert self.start is not None and self.end is not None
        if self.start.day != 1 or (self.end + timedelta(days=1)).day != 1:
            return PeriodKind.OTHER
        months = _month_index(self.end) - _month_index(self.start) + 1
        offset = (self.start.month - fiscal_year_end_month - 1) % MONTHS_PER_YEAR
        if offset % 3 != 0 or months not in _KIND_BY_MONTHS:
            return PeriodKind.OTHER
        if months == 3:
            return PeriodKind.QUARTER
        if months == 6 and offset in (0, 6):
            return PeriodKind.HALF_YEAR
        if months == 9 and offset == 0:
            return PeriodKind.NINE_MONTH
        if months == MONTHS_PER_YEAR:
            return PeriodKind.YEAR if offset == 0 else PeriodKind.TTM
        return PeriodKind.OTHER

    def canonical(self) -> dict[str, str | None]:
        """Return the period as ISO strings for hashing and storage."""
        return {
            "start": _iso(self.start),
            "end": _iso(self.end),
            "instant": _iso(self.instant),
        }


class DimensionSet(BaseModel):
    """Normalised (axis, member) pairs, sorted by axis; the empty set is explicit."""

    model_config = ConfigDict(frozen=True)

    pairs: tuple[tuple[str, str], ...] = ()

    @model_validator(mode="after")
    def _sorted_unique(self) -> DimensionSet:
        """Refuse unsorted pairs or a repeated axis, so equal sets have one form."""
        axes = [axis for axis, _ in self.pairs]
        if axes != sorted(set(axes)):
            raise ValueError(_UNSORTED.format(pairs=self.pairs))
        return self

    @classmethod
    def of(cls, members: Mapping[str, str]) -> DimensionSet:
        """Build a set from an axis-to-member mapping."""
        return cls(pairs=tuple(sorted(members.items())))

    def digest(self) -> str:
        """Return the SHA-256 of the canonical pair list."""
        return _sha256([list(pair) for pair in self.pairs])


class MeasurementKey(BaseModel):
    """Everything two values must share before they can be compared."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    canonical_id: str
    period: PeriodInterval
    basis: Basis
    framework: AccountingFramework
    currency: str | None
    value_kind: ValueKind
    dimensions: DimensionSet

    def digest(self) -> str:
        """Return the SHA-256 of every key part in a fixed canonical form."""
        return _sha256(
            {
                "entity_id": self.entity_id,
                "canonical_id": self.canonical_id,
                "period": self.period.canonical(),
                "basis": self.basis.value,
                "framework": self.framework.value,
                "currency": self.currency,
                "value_kind": self.value_kind.value,
                "dimensions": [list(pair) for pair in self.dimensions.pairs],
            }
        )


def _month_index(day: date) -> int:
    """Return a month ordinal so month spans can be subtracted."""
    return day.year * MONTHS_PER_YEAR + day.month


def _iso(day: date | None) -> str | None:
    """Return a date as ISO text, keeping absence as ``None``."""
    return None if day is None else day.isoformat()


def _sha256(payload: object) -> str:
    """Hash a JSON-serialisable payload in sorted, compact form."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
