"""What one Lane B sensitivity measurement records, and how it is tallied.

The record half of :mod:`fundamentals.verify.laneb_sensitivity`, split from it
when the two together crossed the 800-line ceiling. This module knows what a
measured cell *is* and how a run of them adds up; it knows nothing about
mutating a Screener section or about running a comparison, which is what keeps
the split honest rather than arbitrary. It takes one name from the comparator's
module — the ``COMPARED_SECTIONS`` constant, so a report can order its sections
the way the lane reads them — and never :func:`compare_company` or any of the
Screener models it works on.

Everything is re-exported from ``laneb_sensitivity``, which stays the one import
site for the harness, so a reader never has to know which half a name lives in.

**Nothing here is a fact.** A cell records what the comparator said before and
after a defect injected on purpose; it carries no fact, observation or
provenance type, and a measurement is all it may ever become.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer

from fundamentals.ingest.screener_crosscheck import CrosscheckOutcome, EvidenceTier
from fundamentals.ingest.upstox_crosscheck import COMPARED_SECTIONS


def _freeze[KeyT, ValueT](value: Mapping[KeyT, ValueT]) -> Mapping[KeyT, ValueT]:
    """Take a read-only view of one aggregate, so a report cannot be edited in place."""
    return MappingProxyType(dict(value))


def _as_dict[KeyT, ValueT](value: Mapping[KeyT, ValueT]) -> dict[KeyT, ValueT]:
    """Hand the serialiser a plain mapping, keeping the JSON shape unchanged."""
    return dict(value)


# An aggregate a reader cannot edit. ``MappingProxyType`` is not serialisable on
# its own, so the alias pairs the freeze with a serialiser that hands Pydantic a
# plain dict — the JSON is byte-identical to the mutable form it replaced.
type _Frozen[KeyT, ValueT] = Annotated[
    Mapping[KeyT, ValueT], AfterValidator(_freeze), PlainSerializer(_as_dict)
]


class MutationClass(StrEnum):
    """One seeded parser defect, each a pure function of one named row.

    Every member names a defect a real extractor can have rather than an
    arbitrary perturbation: a lost row, an off-by-one column read, a sign, a
    dropped digit, lakhs read as crores, a thousands separator truncating the
    value, two rows exchanged, a unit adrift by one crore, and a figure filed
    under a period the page never published.
    """

    DROP_ROW = "DROP_ROW"
    COLUMN_SHIFT = "COLUMN_SHIFT"
    SIGN_FLIP = "SIGN_FLIP"
    SCALE_10 = "SCALE_10"
    SCALE_100 = "SCALE_100"
    THOUSANDS_TRUNCATED = "THOUSANDS_TRUNCATED"
    ROW_SWAP = "ROW_SWAP"
    UNIT_DRIFT = "UNIT_DRIFT"
    STALE_PERIOD = "STALE_PERIOD"


class Classification(StrEnum):
    """What one seeded defect established about the comparator, at one cell."""

    DETECTED = "DETECTED"
    UNDETECTED = "UNDETECTED"
    MASKED = "MASKED"
    BLIND_TIER3 = "BLIND_TIER3"
    BLIND_UNMAPPED = "BLIND_UNMAPPED"
    BLIND_NO_UPSTOX = "BLIND_NO_UPSTOX"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SkipReason(StrEnum):
    """Why a company and basis a run was asked for produced no measurement."""

    INVALID_ISIN = "INVALID_ISIN"
    NO_SCREENER_SECTIONS = "NO_SCREENER_SECTIONS"
    NO_RETAINED_BODIES = "NO_RETAINED_BODIES"
    UPSTOX_UNREADABLE = "UPSTOX_UNREADABLE"


class SkippedCompany(BaseModel):
    """One company and basis a run could not measure, and which gap it was.

    The kind matters to a reader: a company nobody retained is a hole in the
    inputs, while one whose responses would not parse is a finding about the
    vendor. Reporting both as a bare name made them the same line.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    reason: SkipReason


class SensitivityCell(BaseModel):
    """One (company, section, row, period, mutation): what the comparator said, twice.

    Carries no fact, observation or provenance type — it is a measurement of the
    comparator, and a measurement is all it may ever become.
    """

    model_config = ConfigDict(frozen=True)

    isin: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    section: str = Field(min_length=1)
    row_label: str = Field(min_length=1)
    period: str = Field(min_length=1)
    mutation: MutationClass
    # ``None`` where the name map never names this row: an unmapped cell has no
    # tier, and P3 keeps it out of ``by_tier`` rather than inventing one.
    tier: EvidenceTier | None = None
    # Whether the unmutated comparison produced any row at all for this period.
    # False for the two thirds of a Screener page Upstox does not answer with,
    # and the only thing that separates a blind period from a quiet one.
    period_compared: bool = False
    baseline_outcome: CrosscheckOutcome | None = None
    # ``None`` means the mutated comparison was never run for this row: a blind
    # or inapplicable row is classified before any outcome is consulted, so
    # there is nothing to record. It does NOT mean the mutation had no effect —
    # a period this class did not address, on a row that *was* re-compared,
    # carries a real outcome here, normally the baseline's own.
    mutated_outcome: CrosscheckOutcome | None = None
    classification: Classification


class ClassificationCounts(BaseModel):
    """The tally of one slice of the cells, with the ratio that slice supports.

    Build these through :meth:`tally`. ``sensitivity`` is a stored field rather
    than a derived one so it survives serialization, and :meth:`tally` is the
    only place it is computed.
    """

    model_config = ConfigDict(frozen=True)

    detected: int = 0
    undetected: int = 0
    masked: int = 0
    blind_tier3: int = 0
    blind_unmapped: int = 0
    blind_no_upstox: int = 0
    not_applicable: int = 0
    # DETECTED / (DETECTED + UNDETECTED), exact and unquantized (P5). ``None``
    # when nothing in this slice could have been noticed — a ratio of zero would
    # read as a blind comparator rather than as an unmeasured one.
    sensitivity: Decimal | None = None

    @classmethod
    def tally(cls, cells: Iterable[SensitivityCell]) -> ClassificationCounts:
        """Count one slice of the cells by classification."""
        counted = Counter(cell.classification for cell in cells)
        detected = counted[Classification.DETECTED]
        undetected = counted[Classification.UNDETECTED]
        scored = detected + undetected
        return cls(
            detected=detected,
            undetected=undetected,
            masked=counted[Classification.MASKED],
            blind_tier3=counted[Classification.BLIND_TIER3],
            blind_unmapped=counted[Classification.BLIND_UNMAPPED],
            blind_no_upstox=counted[Classification.BLIND_NO_UPSTOX],
            not_applicable=counted[Classification.NOT_APPLICABLE],
            sensitivity=None if scored == 0 else Decimal(detected) / Decimal(scored),
        )

    @property
    def blind(self) -> int:
        """Cells no mutation could have been noticed at, for any of the three reasons."""
        return self.blind_tier3 + self.blind_unmapped + self.blind_no_upstox


class SensitivityReport(BaseModel):
    """Every seeded defect of one measurement run, and what each established.

    Every aggregate is a tally of :attr:`cells` and of nothing else — see
    :meth:`from_cells`. An aggregate computed on a second pass over the source
    data can disagree with the cells it sits beside, and a reader has no way to
    tell which half is wrong.
    """

    model_config = ConfigDict(frozen=True)

    cells: tuple[SensitivityCell, ...] = ()
    by_mutation: _Frozen[MutationClass, ClassificationCounts] = Field(default_factory=dict)
    by_tier: _Frozen[EvidenceTier, ClassificationCounts] = Field(default_factory=dict)
    by_section: _Frozen[str, ClassificationCounts] = Field(default_factory=dict)
    by_company: _Frozen[str, ClassificationCounts] = Field(default_factory=dict)
    # Mapped rows over all rows, per section: how much of the page Lane B reads
    # at all. The other half of the finding, and the one with a different remedy.
    # A tier-3 row counts as mapped here — the map names it — even though no
    # value of it can ever be concluded from; that is what ``blind_tier3`` is for.
    coverage_by_section: _Frozen[str, Decimal] = Field(default_factory=dict)
    # Periods the comparison produced a row for, over periods on the page (M1).
    # The measure of how much of a Screener page Upstox answers about at all.
    period_coverage_by_section: _Frozen[str, Decimal] = Field(default_factory=dict)
    sensitivity: Decimal | None = None
    # Every company and basis a run was asked for and could not measure.
    skipped: tuple[SkippedCompany, ...] = ()

    @classmethod
    def from_cells(
        cls,
        cells: Sequence[SensitivityCell],
        *,
        skipped: Sequence[SkippedCompany] = (),
    ) -> SensitivityReport:
        """Aggregate one run's cells. The single constructor of a report."""
        tiers = tuple(tier for tier in EvidenceTier if any(cell.tier is tier for cell in cells))
        return cls(
            cells=tuple(cells),
            by_mutation=_tally_by(cells, lambda cell: cell.mutation, MutationClass),
            by_tier=_tally_by(cells, lambda cell: cell.tier, tiers),
            by_section=_tally_by(cells, lambda cell: cell.section, _sections_of(cells)),
            by_company=_tally_by(
                cells, lambda cell: cell.symbol, _distinct(cells, lambda cell: cell.symbol)
            ),
            coverage_by_section=_ratios(cells, row_counts),
            period_coverage_by_section=_ratios(cells, period_counts),
            sensitivity=ClassificationCounts.tally(cells).sensitivity,
            skipped=tuple(skipped),
        )


def row_counts(cells: Sequence[SensitivityCell], section: str) -> tuple[int, int]:
    """Mapped rows and all rows of one section, counted per company and basis."""
    rows = {
        (cell.isin, cell.basis, cell.row_label, cell.tier is not None)
        for cell in cells
        if cell.section == section
    }
    return sum(1 for row in rows if row[-1]), len(rows)


def period_counts(cells: Sequence[SensitivityCell], section: str) -> tuple[int, int]:
    """Compared periods and all periods of one section, per company and basis."""
    periods = {
        (cell.isin, cell.basis, cell.period, cell.period_compared)
        for cell in cells
        if cell.section == section
    }
    return sum(1 for period in periods if period[-1]), len(periods)


def _tally_by[KeyT](
    cells: Sequence[SensitivityCell],
    key: Callable[[SensitivityCell], KeyT | None],
    keys: Iterable[KeyT],
) -> dict[KeyT, ClassificationCounts]:
    """Tally the cells under each of the given keys, in the order given.

    A cell whose key is ``None`` belongs to no group and is counted in none: an
    unmapped cell has no tier, and P3 keeps it out of ``by_tier`` entirely.
    """
    grouped: dict[KeyT, list[SensitivityCell]] = {name: [] for name in keys}
    for cell in cells:
        name = key(cell)
        if name is None:
            continue
        group = grouped.get(name)
        if group is not None:
            group.append(cell)
    return {name: ClassificationCounts.tally(group) for name, group in grouped.items()}


def _distinct[ValueT](
    cells: Sequence[SensitivityCell],
    of: Callable[[SensitivityCell], ValueT],
) -> tuple[ValueT, ...]:
    """The distinct values of one coordinate, in the order the cells state them."""
    return tuple(dict.fromkeys(of(cell) for cell in cells))


def _sections_of(cells: Sequence[SensitivityCell]) -> tuple[str, ...]:
    """The sections these cells cover, compared sections first."""
    present = _distinct(cells, lambda cell: cell.section)
    ordered = tuple(name for name in COMPARED_SECTIONS if name in present)
    return ordered + tuple(name for name in present if name not in ordered)


def _ratios(
    cells: Sequence[SensitivityCell],
    counter: Callable[[Sequence[SensitivityCell], str], tuple[int, int]],
) -> dict[str, Decimal]:
    """One counted ratio per section, skipping a section with nothing to divide by."""
    ratios: dict[str, Decimal] = {}
    for section in _sections_of(cells):
        covered, total = counter(cells, section)
        if total:
            ratios[section] = Decimal(covered) / Decimal(total)
    return ratios
