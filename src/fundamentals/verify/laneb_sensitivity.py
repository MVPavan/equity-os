"""Would Lane B notice a parser defect it was handed? Seeded mutations, measured.

The 10-pair sweep gave Lane B a base *disagreement* rate. It says nothing about
detection: a comparator that reads four rows out of forty and one that reads all
forty produce the same quiet report when nothing is wrong. This module supplies
the missing number by seeding one known defect at a time into the Screener side
and asking :func:`~fundamentals.ingest.upstox_crosscheck.compare_company`
whether the outcome moved. **Nothing here is a fact or a gate:** it measures the
instrument, so the aggregate is a property of the name map and the tolerance
derivation, not of any issuer.

**Every row is mutated, not only the mapped ones.** The rows the name map never
names are the honest part of the measurement — a defect there is invisible by
construction — so they are reported as ``BLIND_UNMAPPED`` and counted into
``coverage_by_section`` rather than skipped. Skipping them would raise the
sensitivity number by deleting its own worst cases.

**A Screener page carries more columns than Upstox answers with** — 12 or 13
against 4 or 5 — and the first real measurement (2026-09-04) showed what
ignoring that costs: 136 of 140 tier-1 "undetected" cells had no Upstox row for
their period at all, and counting them deflated tier-1 sensitivity from ~1.0 to
0.32. Those cells are ``BLIND_NO_UPSTOX`` (amendment M1), out of the denominator
and reported as ``period_coverage_by_section`` beside it.

**A detection is not always a line an operator would see.** Most of the classes
here are caught as ``MISSING_SCREENER`` — the seeded defect makes a mapping's
Screener side incomplete, so the comparator refuses to score it. That refusal is
in ``upstox-crosscheck``'s row-level JSON report, but **not** in its summary
line, which prints only agree / mismatch / anomaly / not_comparable /
unmet_tier3. So a sensitivity number counts what the comparator *recorded*, and
a reader who watches only the summary table sees less than this measurement
credits it with.

**Classification precedence, first match wins** (P1, revised by M1):
``BLIND_UNMAPPED`` → ``BLIND_TIER3`` → ``BLIND_NO_UPSTOX`` → ``NOT_APPLICABLE``
→ ``MASKED`` → ``DETECTED``/``UNDETECTED``. Every form of blindness ranks above
applicability, and applicability above detection: a row Lane B never reads, a
tier it may not conclude from, and a period it never received are all invisible
whatever the mutation. ``NOT_APPLICABLE`` is decided per *cell* by
:func:`touched` (M4) and never by observing that an outcome did not move (P2):
most classes move only some of a row's columns, and charging the ones they never
reached as ``UNDETECTED`` reports the comparator as blind to a defect nobody
seeded there.

The record half of this harness — what a cell is, and how a run of them adds up
— lives in :mod:`fundamentals.verify.laneb_sensitivity_model` and is re-exported
here, so this stays the one import site.

**Column order is oldest-first**, as Screener publishes it: index 0 is the
earliest period on the page and the highest index is the newest. The classes
that address columns (``COLUMN_SHIFT``, ``STALE_PERIOD``) depend on that
orientation, and a fixture that reversed it would seed a different defect than
the one it names.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from decimal import Decimal
from types import MappingProxyType

from fundamentals.ingest.screener_crosscheck import (
    INCOME_STATEMENT_MAP,
    CrosscheckOutcome,
    EvidenceTier,
    LineMapping,
)
from fundamentals.ingest.upstox_crosscheck import (
    COMPARED_SECTIONS,
    CompanyCrosscheck,
    CompanyStatus,
    ScreenerCell,
    ScreenerRow,
    ScreenerSection,
    compare_company,
)
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    StatementBasis,
)

# The record half of this harness. Re-exported under this name so
# ``laneb_sensitivity`` stays the single import site: which half a name lives in
# is a fact about file length, not about the measurement.
from fundamentals.verify.laneb_sensitivity_model import (
    Classification as Classification,
)
from fundamentals.verify.laneb_sensitivity_model import (
    ClassificationCounts as ClassificationCounts,
)
from fundamentals.verify.laneb_sensitivity_model import (
    MutationClass as MutationClass,
)
from fundamentals.verify.laneb_sensitivity_model import (
    SensitivityCell as SensitivityCell,
)
from fundamentals.verify.laneb_sensitivity_model import (
    SensitivityReport as SensitivityReport,
)
from fundamentals.verify.laneb_sensitivity_model import (
    SkippedCompany as SkippedCompany,
)
from fundamentals.verify.laneb_sensitivity_model import (
    SkipReason as SkipReason,
)
from fundamentals.verify.laneb_sensitivity_model import (
    period_counts as period_counts,
)
from fundamentals.verify.laneb_sensitivity_model import (
    row_counts as row_counts,
)

# Which mapping reads each Screener row. Built the way a reader of
# ``INCOME_STATEMENT_MAP`` would build it: a label named by two mappings resolves
# to the later one, which is the only order the declaration states. Read-only,
# because it is derived from a frozen declaration and a caller that mutated it
# would silently change what every later measurement calls mapped.
MAPPING_BY_SCREENER_ROW: Mapping[str, LineMapping] = MappingProxyType(
    {label: mapping for mapping in INCOME_STATEMENT_MAP for label in mapping.screener_rows}
)


_SIGN_FLIP = Decimal(-1)
_TEN = Decimal(10)
_HUNDRED = Decimal(100)
_THOUSAND = Decimal(1000)
# One crore, just above the ~0.505 tolerance two integer-crore values derive. It
# is the smallest seeded defect on offer and therefore the floor of the
# instrument. M3: a two-addend tier-2 mapping tolerates 1.005 crore, so this
# class is genuinely invisible there — a finding about the tolerance, not a
# defect in the harness.
_ONE_CRORE = Decimal(1)

# The outcomes that show a line failing to agree. One set, read twice: as a
# *mutated* outcome it means the seeded defect was noticed, and as a *baseline*
# it means the line was already flagged before anything was seeded, so a further
# defect changes nothing observable. They were two identically-populated
# constants until 2026-09-04; one name is honest about that being one idea.
# ``MISSING_SCREENER`` belongs here for the same reason a mismatch does: a
# mapping whose Screener side went incomplete is a visible refusal to score, not
# a quiet agreement.
_DISAGREEING: frozenset[CrosscheckOutcome] = frozenset(
    {
        CrosscheckOutcome.MISMATCH,
        CrosscheckOutcome.ANOMALY,
        CrosscheckOutcome.MISSING_SCREENER,
    }
)

# The per-cell arithmetic of the value-rewriting classes. The structural classes
# (DROP_ROW, ROW_SWAP) and the addressing classes (COLUMN_SHIFT, STALE_PERIOD)
# need the row or the section, so they are handled separately.
_VALUE_MUTATIONS: Mapping[MutationClass, Callable[[Decimal], Decimal]] = MappingProxyType(
    {
        MutationClass.SIGN_FLIP: lambda value: value * _SIGN_FLIP,
        MutationClass.SCALE_10: lambda value: value * _TEN,
        MutationClass.SCALE_100: lambda value: value * _HUNDRED,
        # Truncating division, which rounds toward zero on both signs: a
        # thousands separator read as a decimal point loses the tail, it does
        # not round it, and a negative row must lose the same digits.
        MutationClass.THOUSANDS_TRUNCATED: lambda value: value // _THOUSAND,
        MutationClass.UNIT_DRIFT: lambda value: value + _ONE_CRORE,
    }
)


def mutate(
    section: ScreenerSection,
    *,
    row_label: str,
    mutation: MutationClass,
    comparable_periods: Collection[str] | None = None,
) -> ScreenerSection:
    """Seed one defect into one named row, leaving the rest of the section alone.

    Every other row comes back byte-identical and the column headings are never
    rewritten: each class is row-scoped, so a detection can be attributed to the
    defect it was seeded from. ``ROW_SWAP`` is the one class that necessarily
    touches a second row — the one it exchanges values with — so a detection it
    scores could have come from either row's mapping, and it is the one class
    whose attribution is not exact.

    ``comparable_periods`` names the period labels Upstox actually answered for.
    Only ``STALE_PERIOD`` reads it, to re-key the newest column that could have
    been compared rather than the newest column on the page (M2). ``None`` means
    every column on the page counts, which is what a caller mutating a section
    outside a comparison wants.

    A class that cannot apply here returns the section unchanged (P2).
    """
    index = _row_index(section, row_label)
    if index is None or not is_applicable(
        section, row_label=row_label, mutation=mutation, comparable_periods=comparable_periods
    ):
        return section
    if mutation is MutationClass.DROP_ROW:
        rows = tuple(row for position, row in enumerate(section.rows) if position != index)
    elif mutation is MutationClass.ROW_SWAP:
        rows = _swap_values(section.rows, index)
    else:
        rows = tuple(
            _mutated_row(section, row, mutation, comparable_periods) if position == index else row
            for position, row in enumerate(section.rows)
        )
    return section.model_copy(update={"rows": rows})


def is_applicable(
    section: ScreenerSection,
    *,
    row_label: str,
    mutation: MutationClass,
    comparable_periods: Collection[str] | None = None,
) -> bool:
    """Whether this class alters anything at all on this row of this section.

    Stated as a rule rather than inferred from an unchanged outcome: a mutation
    that never happened is not evidence that the comparator is blind, and from
    the outcomes alone the two look identical. The rules live in :func:`touched`,
    which says *which* columns move; this is the row-level question of whether
    any of them do.
    """
    return bool(
        touched(
            section,
            row_label=row_label,
            mutation=mutation,
            comparable_periods=comparable_periods,
        )
    )


def touched(
    section: ScreenerSection,
    *,
    row_label: str,
    mutation: MutationClass,
    comparable_periods: Collection[str] | None = None,
) -> frozenset[str]:
    """The period labels this class actually alters on this row (M4).

    Applicability is per cell, not per row. Every class is row-scoped, but most
    of them move only some of that row's columns, and charging the untouched
    ones as ``UNDETECTED`` reports the comparator as blind to a defect that was
    never seeded there. The first real measurement scored ``STALE_PERIOD`` at
    17 detected against 48 undetected that way, when in fact it had moved every
    column it was able to move.

    The rules, each derived from what the class does rather than from any
    outcome (P2 still holds):

    * ``ROW_SWAP`` needs a next row, and reaches every column either row
      publishes a value in;
    * ``COLUMN_SHIFT`` needs a second column, and reaches every column of the
      row — including the earliest, whose value it removes;
    * ``STALE_PERIOD`` reaches exactly the one column it re-keys, and needs that
      column to be one a comparison actually scored (M2);
    * the value-rewriting classes and ``DROP_ROW`` reach the columns a
      comparison reads, which excludes an unpublished or empty cell.

    Addressed, not changed: a column stays in this set even when the value the
    class writes there happens to equal the one already in it — a flat row under
    ``COLUMN_SHIFT``, two identical neighbours under ``ROW_SWAP``, a zero under
    ``SIGN_FLIP``. Dropping those would be a comparison of values, which P2
    forbids, and it would contradict B-07: the class did address the cell and
    the comparator could not see it, which is a true ``UNDETECTED`` rather than
    a ``NOT_APPLICABLE``. (Proposed in review 2026-09-04 and rejected for those
    two reasons.)
    """
    index = _row_index(section, row_label)
    if index is None:
        return frozenset()
    row = section.rows[index]
    labels = {period.index: period.label for period in section.periods}
    if mutation is MutationClass.ROW_SWAP:
        if index + 1 >= len(section.rows):
            return frozenset()
        return _read_columns(row, labels) | _read_columns(section.rows[index + 1], labels)
    if mutation is MutationClass.COLUMN_SHIFT:
        if len(section.periods) < 2:
            return frozenset()
        return frozenset(
            labels[cell.period_index] for cell in row.cells if cell.period_index in labels
        )
    if mutation is MutationClass.STALE_PERIOD:
        target = _stale_target(section, row, comparable_periods)
        return frozenset() if target is None else frozenset({labels[target]})
    return _read_columns(row, labels)


def _read_columns(row: ScreenerRow, labels: Mapping[int, str]) -> frozenset[str]:
    """The columns of one row a comparison would actually read.

    ``_screener_values`` skips a cell that is unpublished or carries no value, so
    a class that rewrites one of those changes nothing and must not be scored
    there.
    """
    return frozenset(
        labels[cell.period_index]
        for cell in row.cells
        if cell.period_index in labels and cell.published and cell.value is not None
    )


def measure_sensitivity(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    sections: Mapping[str, ScreenerSection],
    income: IncomeStatementDocument,
    balance: BalanceSheetDocument,
    cash: CashFlowDocument,
) -> SensitivityReport:
    """Seed every class into every row of every compared section, and classify.

    The baseline is what ``compare_company`` says with nothing mutated, recorded
    rather than derived: a harness that computed its own baseline would report a
    sensitivity for a comparator that never ran.

    A company whose Upstox responses this repo could not read yields no cells at
    all. There is no baseline to move, and scoring its rows ``UNDETECTED`` would
    blame the comparator for a parse failure upstream of it.
    """

    def compare(candidate: Mapping[str, ScreenerSection]) -> CompanyCrosscheck:
        """Run the lane's own comparison over one set of sections."""
        return compare_company(
            isin=isin,
            symbol=symbol,
            basis=basis,
            sections=candidate,
            income=income,
            balance=balance,
            cash=cash,
        )

    unmutated = compare(sections)
    if unmutated.status is not CompanyStatus.COMPARED:
        return SensitivityReport.from_cells(
            (),
            skipped=(
                SkippedCompany(
                    symbol=symbol, basis=basis.value, reason=SkipReason.UPSTOX_UNREADABLE
                ),
            ),
        )
    baseline = _outcomes(unmutated)
    compared_periods = frozenset(report.period for report in unmutated.reports)

    cells: list[SensitivityCell] = []
    for name in COMPARED_SECTIONS:
        table = sections.get(name)
        if table is None:
            continue
        for row in table.rows:
            mapping = MAPPING_BY_SCREENER_ROW.get(row.label)
            # The periods this row's own mapping was scored in — not every
            # period the run reported on. A period only the balance sheet
            # answered for is not somewhere a profit-loss row could be caught.
            scored = _scored_periods(baseline, mapping)
            for mutation in MutationClass:
                altered = touched(
                    table,
                    row_label=row.label,
                    mutation=mutation,
                    comparable_periods=scored,
                )
                # A blind or inapplicable row is not compared again: P1 fixes
                # every one of its cells before an outcome is consulted, and a
                # sweep over a real page would otherwise spend most of its work
                # deriving outcomes no classification reads. Tier 3 is in that
                # set — it answers NOT_COMPARABLE whatever the values.
                mutated: dict[tuple[str, str], CrosscheckOutcome] = {}
                if altered and mapping is not None and not _is_tier_three(mapping):
                    seeded = mutate(
                        table,
                        row_label=row.label,
                        mutation=mutation,
                        comparable_periods=scored,
                    )
                    mutated = _outcomes(compare({**sections, name: seeded}))
                for period in (column.label for column in table.periods):
                    key = None if mapping is None else (period, mapping.upstox_category)
                    before = None if key is None else baseline.get(key)
                    after = None if key is None else mutated.get(key)
                    cells.append(
                        SensitivityCell(
                            isin=isin,
                            symbol=symbol,
                            basis=basis.value,
                            section=name,
                            row_label=row.label,
                            period=period,
                            mutation=mutation,
                            tier=None if mapping is None else mapping.tier,
                            period_compared=period in compared_periods,
                            baseline_outcome=before,
                            mutated_outcome=after,
                            classification=_classify(
                                mapping=mapping,
                                applicable=period in altered,
                                baseline=before,
                                mutated=after,
                            ),
                        )
                    )
    return SensitivityReport.from_cells(cells)


def _scored_periods(
    baseline: Mapping[tuple[str, str], CrosscheckOutcome],
    mapping: LineMapping | None,
) -> frozenset[str]:
    """The periods in which this mapping was scored, and could therefore be caught.

    Narrower than "periods the run reported on": the three surfaces do not
    always answer for the same periods, so a period carried only by the balance
    sheet reports a row for the balance-sheet categories and ``MISSING_UPSTOX``
    for the income-statement ones. Aiming a mutation at such a period lands it
    on a cell that is ``BLIND_NO_UPSTOX`` anyway.
    """
    if mapping is None:
        return frozenset()
    return frozenset(
        period
        for (period, category), outcome in baseline.items()
        if category == mapping.upstox_category and outcome is not CrosscheckOutcome.MISSING_UPSTOX
    )


def _is_tier_three(mapping: LineMapping) -> bool:
    """Whether this mapping may conclude nothing from its values, whatever they say."""
    return mapping.tier is EvidenceTier.EQUIVALENCE_UNPROVEN


def _classify(
    *,
    mapping: LineMapping | None,
    applicable: bool,
    baseline: CrosscheckOutcome | None,
    mutated: CrosscheckOutcome | None,
) -> Classification:
    """Apply P1 as revised by M1: blindness, then applicability, then detection.

    By the last two lines the baseline can only be ``AGREE``: the three blind
    rules have taken the unmapped row, the unprovable tier and the period with
    no Upstox row, and ``MASKED`` has taken every baseline that already refused
    to agree. So a noticed outcome there is a real change of verdict.
    """
    if mapping is None:
        return Classification.BLIND_UNMAPPED
    if _is_tier_three(mapping):
        return Classification.BLIND_TIER3
    if baseline is None or baseline is CrosscheckOutcome.MISSING_UPSTOX:
        return Classification.BLIND_NO_UPSTOX
    if not applicable:
        return Classification.NOT_APPLICABLE
    if baseline in _DISAGREEING:
        return Classification.MASKED
    if mutated in _DISAGREEING:
        return Classification.DETECTED
    return Classification.UNDETECTED


def _outcomes(company: CompanyCrosscheck) -> dict[tuple[str, str], CrosscheckOutcome]:
    """Index one comparison's rows by (period label, Upstox category)."""
    return {
        (report.period, row.upstox_category): row.outcome
        for report in company.reports
        for row in report.rows
    }


def _row_index(section: ScreenerSection, row_label: str) -> int | None:
    """Where a label sits in the section, or ``None`` when the section lacks it."""
    for position, row in enumerate(section.rows):
        if row.label == row_label:
            return position
    return None


def _swap_values(rows: tuple[ScreenerRow, ...], index: int) -> tuple[ScreenerRow, ...]:
    """Exchange one row's values with the next row's, keeping both labels."""
    first, second = rows[index], rows[index + 1]
    swapped = list(rows)
    swapped[index] = _with_cells(first, second.cells)
    swapped[index + 1] = _with_cells(second, first.cells)
    return tuple(swapped)


def _with_cells(row: ScreenerRow, cells: Iterable[ScreenerCell]) -> ScreenerRow:
    """The same row under the same label, carrying different cells."""
    return row.model_copy(update={"cells": tuple(cells)})


def _mutated_row(
    section: ScreenerSection,
    row: ScreenerRow,
    mutation: MutationClass,
    comparable_periods: Collection[str] | None,
) -> ScreenerRow:
    """Apply one cell-level or addressing-level class to a single row."""
    if mutation is MutationClass.COLUMN_SHIFT:
        return _column_shift(row)
    if mutation is MutationClass.STALE_PERIOD:
        return _stale_period(section, row, comparable_periods)
    rewrite = _VALUE_MUTATIONS[mutation]
    return _with_cells(
        row,
        (
            cell if cell.value is None else cell.model_copy(update={"value": rewrite(cell.value)})
            for cell in row.cells
        ),
    )


def _column_shift(row: ScreenerRow) -> ScreenerRow:
    """Give every column the value of the column to its left, unpublishing the first.

    The off-by-one column read. Columns run oldest-first, so each period takes
    the *earlier* period's figure and the earliest column has no predecessor to
    take one from — the row simply does not publish it there.
    """
    by_index = {cell.period_index: cell for cell in row.cells}
    shifted = []
    for cell in row.cells:
        source = by_index.get(cell.period_index - 1)
        update = (
            {"value": None, "published": False}
            if source is None
            else {"value": source.value, "published": source.published}
        )
        shifted.append(cell.model_copy(update=update))
    return _with_cells(row, shifted)


def _stale_period(
    section: ScreenerSection,
    row: ScreenerRow,
    comparable_periods: Collection[str] | None,
) -> ScreenerRow:
    """Re-key the row's newest comparable cell to a period the section lacks (P4, M2).

    Row-scoped on purpose. A stale period that rewrote the section's headings
    would move every row at once, which is a different defect from the one this
    class names: one row whose newest figure is filed under a column the page
    never published, so it aligns to nothing.

    *Newest comparable*, not newest: profit-loss leads with a TTM column that
    Upstox never answers for, and re-keying that one moved a figure nothing was
    compared against — which is why the first real measurement recorded this
    class as detecting nothing at all, in 600 mapped cells.
    """
    target = _stale_target(section, row, comparable_periods)
    if target is None:
        return row
    unpublished = max((period.index for period in section.periods), default=-1) + 1
    return _with_cells(
        row,
        (
            cell.model_copy(update={"period_index": unpublished})
            if cell.period_index == target
            else cell
            for cell in row.cells
        ),
    )


def _stale_target(
    section: ScreenerSection,
    row: ScreenerRow,
    comparable_periods: Collection[str] | None,
) -> int | None:
    """The newest column index of this row that a comparison actually scored.

    Columns are oldest-first, so the newest is the highest index the row carries
    among the section's own columns. Two filters, and both were found missing by
    review: the cell must be one a comparison reads at all — an unpublished or
    empty cell is skipped by ``_screener_values``, so re-keying it is a
    guaranteed no-op — and its period must be one *this mapping* was scored in,
    not merely one some other surface answered for.
    """
    labels = {period.index: period.label for period in section.periods}
    candidates = [
        cell.period_index
        for cell in row.cells
        if cell.period_index in labels
        and cell.published
        and cell.value is not None
        and (comparable_periods is None or labels[cell.period_index] in comparable_periods)
    ]
    return max(candidates) if candidates else None
