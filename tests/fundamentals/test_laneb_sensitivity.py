"""Lane B step 5(b): does the comparator notice a parser defect it was handed?

Acceptance tests for Part B of ``scratchpad/laneb-5b/plan.md`` (B-01..B-04,
B-07), the P1..P6 decisions recorded there on 2026-09-04, and amendments M1 and
M2 from the first real measurement. This half covers the mutations themselves
and the classification of a single cell; the aggregates and the command are in
``test_laneb_sensitivity_report``. The company both halves measure is built in
``laneb_sensitivity_fixtures`` and explained there.

**Names this half pins** (the implementation must match them): ``MutationClass``,
``Classification``, ``mutate``, ``is_applicable``, ``measure_sensitivity``, and
on each cell ``section``, ``row_label``, ``period``, ``mutation``, ``tier``,
``period_compared``, ``baseline_outcome``, ``mutated_outcome`` and
``classification``.

No test here opens a socket, and the harness is required not to open one either.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.fundamentals.laneb_sensitivity_fixtures import (
    BALANCE_TIER_TWO_ROW,
    BASIS,
    CELL_COUNT,
    FOUR_PERIODS,
    LAST_MAPPED_ROWS,
    MAPPING_BY_ROW,
    MUTATION_NAMES,
    NEWEST_PERIOD,
    OLDEST_PERIOD,
    PAGE_PERIODS,
    PAGE_PERIODS_WITH_TTM,
    ROW_COUNT,
    SENSITIVITY_ROWS,
    SYMBOL,
    TIER_ONE_AGREEING_ROW,
    TIER_ONE_MISMATCHING_ROW,
    TIER_THREE_ROWS,
    TIER_TWO_PARTNER_ROW,
    TIER_TWO_ROW,
    TITAN_ISIN,
    TTM_PERIOD,
    UNMAPPED_ROWS,
    cells,
    documents,
    four_period_bodies,
    hiding_newest_cell,
    one_cell,
    report,
    sections,
    with_flat_row,
    with_ttm_column,
    with_two_newer_columns,
    without_row,
)

from fundamentals.ingest.screener_crosscheck import CrosscheckOutcome, EvidenceTier
from fundamentals.ingest.upstox_crosscheck import compare_company
from fundamentals.verify.laneb_sensitivity import (
    Classification,
    MutationClass,
    is_applicable,
    mutate,
    touched,
)


def test_the_baseline_of_every_mapped_row_is_the_unmutated_comparison() -> None:
    # B-01
    """Every cell's baseline is what ``compare_company`` says with nothing mutated.

    Recorded rather than assumed: a harness that derived the baseline from its
    own arithmetic could report a sensitivity for a comparator that never ran.
    """
    measured = report()
    income, balance, cash = documents()
    company = compare_company(
        isin=TITAN_ISIN,
        symbol=SYMBOL,
        basis=BASIS,
        sections=sections(),
        income=income,
        balance=balance,
        cash=cash,
    )
    unmutated = {
        (crosscheck.period, row.upstox_category): row.outcome
        for crosscheck in company.reports
        for row in crosscheck.rows
    }
    assert {
        unmutated[(NEWEST_PERIOD, "operating_profit")],
        unmutated[(NEWEST_PERIOD, "net_profit")],
        unmutated[(NEWEST_PERIOD, "operating")],
    } == {CrosscheckOutcome.AGREE, CrosscheckOutcome.MISMATCH, CrosscheckOutcome.NOT_COMPARABLE}

    for cell in measured.cells:
        mapping = MAPPING_BY_ROW.get(cell.row_label)
        if mapping is None:
            assert cell.tier is None
            continue
        assert cell.tier is mapping.tier
        assert cell.baseline_outcome is unmutated[(cell.period, mapping.upstox_category)]


@pytest.mark.parametrize("mutation_name", MUTATION_NAMES)
def test_mutating_one_row_leaves_every_other_row_and_the_input_untouched(
    mutation_name: str,
) -> None:
    # B-02
    """A mutation is a seeded defect in one row, not a rewrite of the section.

    If a class quietly disturbed a neighbouring row, every detection it scored
    would be unattributable — the measurement would be of the harness, not of
    the comparator. P4 adds the column headings to what stays untouched: every
    class is row-scoped, so ``periods`` is never rewritten.
    """
    mutation = getattr(MutationClass, mutation_name)
    section = sections()["profit-loss"]
    before = section.model_dump_json()

    mutated = mutate(section, row_label=TIER_ONE_MISMATCHING_ROW, mutation=mutation)

    assert section.model_dump_json() == before
    assert mutated.periods == section.periods
    addressed_rows = {TIER_ONE_MISMATCHING_ROW}
    if mutation is MutationClass.ROW_SWAP:
        addressed_rows.add(TIER_ONE_AGREEING_ROW)  # the next row, which ROW_SWAP swaps with
    original = {row.label: row.model_dump_json() for row in section.rows}
    after = {row.label: row.model_dump_json() for row in mutated.rows}
    assert set(original) - set(after) <= {TIER_ONE_MISMATCHING_ROW}
    assert set(after) <= set(original)
    for label, dumped in after.items():
        if label not in addressed_rows:
            assert dumped == original[label], f"{mutation} disturbed {label}"


def test_column_shift_gives_each_period_the_previous_periods_value() -> None:
    # B-02
    """The off-by-one column read: period i takes period i-1, and i=0 goes unpublished.

    Pinned as an arithmetic fact rather than through its outcome, because a
    shift that moved values the other way would still be *detected* on this
    fixture while seeding a different defect than the one being measured. The
    page runs oldest-first, so the value that arrives in Mar 2026 is Mar 2025's
    and the earliest column is the one left with nothing.
    """
    section = sections()["profit-loss"]

    mutated = mutate(section, row_label=TIER_TWO_ROW, mutation=MutationClass.COLUMN_SHIFT)

    row = next(row for row in mutated.rows if row.label == TIER_TWO_ROW)
    shifted = {cell.period_index: cell for cell in row.cells}
    assert shifted[0].published is False
    assert shifted[0].value is None
    assert shifted[1].value == Decimal("142")
    assert tuple(period.label for period in mutated.periods) == PAGE_PERIODS


def test_stale_period_rekeys_the_newest_cell_to_a_period_the_section_does_not_carry() -> None:
    # B-02
    """P4: the newest cell aligns to nothing, and the page's own columns are left alone.

    A stale period that rewrote the section's headings would move every row at
    once, which is a different defect from the one this class names — one row
    whose newest figure is filed under a period the page never published.

    Which cell moves is asserted, not just that one did: columns run oldest-first,
    so a harness that took the lowest index would file the *earliest* figure
    under a phantom column and leave the newest — the one a comparison is most
    likely to read — exactly where it was.
    """
    section = sections()["profit-loss"]

    mutated = mutate(section, row_label=TIER_ONE_AGREEING_ROW, mutation=MutationClass.STALE_PERIOD)

    assert mutated.periods == section.periods
    row = next(row for row in mutated.rows if row.label == TIER_ONE_AGREEING_ROW)
    published = {period.index for period in mutated.periods}
    assert not {cell.period_index for cell in row.cells} <= published
    adrift = {cell.period_index: cell.value for cell in row.cells}
    assert set(adrift) == {0, len(PAGE_PERIODS)}
    assert adrift[0] == Decimal("0")  # the oldest column stayed where it was
    assert adrift[len(PAGE_PERIODS)] == Decimal("40")  # the newest figure is the one adrift


def test_stale_period_moves_the_newest_column_upstox_actually_answered_for() -> None:
    # B-02, M2
    """A page column nobody compares is the wrong target — the class would fire blank.

    Profit-loss leads with a TTM column Upstox never carries. Re-keying that one
    moves a figure no comparison reads, which is why the first real measurement
    recorded ``STALE_PERIOD`` as detecting nothing in 600 mapped cells. The class
    must reach the newest column that *has* an Upstox row, so this fails both for
    a harness that takes the oldest column and for one that takes the newest on
    the page.
    """
    measured = report(rows=with_ttm_column(), periods=PAGE_PERIODS_WITH_TTM)

    cell = one_cell(
        measured,
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.STALE_PERIOD,
        period=NEWEST_PERIOD,
    )
    assert cell.baseline_outcome is CrosscheckOutcome.AGREE
    assert cell.mutated_outcome is CrosscheckOutcome.MISSING_SCREENER
    assert cell.classification is Classification.DETECTED


# What each class addresses on ``Net Profit``: a row whose two columns are both
# published, followed by a row that publishes both of its own. Every class
# reaches both columns here except ``STALE_PERIOD``, which re-keys one.
ADDRESSED_COLUMNS: dict[str, tuple[str, ...]] = {name: PAGE_PERIODS for name in MUTATION_NAMES} | {
    "STALE_PERIOD": (NEWEST_PERIOD,)
}

# The same row with its newest cell present but unpublished, which is where the
# three rules stop agreeing: no comparison reads that column any more, so the
# value classes and DROP_ROW fall back to the older one and STALE_PERIOD re-keys
# it instead, while COLUMN_SHIFT still rewrites it and ROW_SWAP still reaches it
# through the next row.
ADDRESSED_WITH_NEWEST_HIDDEN: dict[str, tuple[str, ...]] = {
    name: (OLDEST_PERIOD,) for name in MUTATION_NAMES
} | {"COLUMN_SHIFT": PAGE_PERIODS, "ROW_SWAP": PAGE_PERIODS}


@pytest.mark.parametrize("mutation_name", MUTATION_NAMES)
def test_each_class_addresses_the_columns_its_own_rule_names(mutation_name: str) -> None:
    # B-03, M4
    """Applicability is per cell, and each class states which cells by its own rule.

    Pinned directly rather than only through the classifications it produces:
    the set is what separates ``NOT_APPLICABLE`` from ``UNDETECTED``, so a class
    that quietly claimed a column it never moves would report the comparator as
    blind to a defect that was never seeded there, and one that under-claimed
    would excuse a real miss.
    """
    mutation = getattr(MutationClass, mutation_name)
    section = sections()["profit-loss"]

    addressed = touched(section, row_label=TIER_ONE_MISMATCHING_ROW, mutation=mutation)

    assert addressed == frozenset(ADDRESSED_COLUMNS[mutation_name])
    assert is_applicable(section, row_label=TIER_ONE_MISMATCHING_ROW, mutation=mutation)


@pytest.mark.parametrize("mutation_name", MUTATION_NAMES)
def test_a_column_no_comparison_reads_is_addressed_only_by_the_column_movers(
    mutation_name: str,
) -> None:
    # B-03, M4
    """An unpublished cell is one ``_screener_values`` skips, not one off the page.

    Rewriting it is a guaranteed no-op, so the classes that only rewrite values
    must fall back to the column a comparison does read. ``COLUMN_SHIFT`` and
    ``ROW_SWAP`` still address it, because both move the *published* value of a
    neighbour into or out of it — which a comparison can see.
    """
    mutation = getattr(MutationClass, mutation_name)
    section = hiding_newest_cell(sections()["profit-loss"], TIER_ONE_MISMATCHING_ROW)

    addressed = touched(section, row_label=TIER_ONE_MISMATCHING_ROW, mutation=mutation)

    assert addressed == frozenset(ADDRESSED_WITH_NEWEST_HIDDEN[mutation_name])


def test_a_column_whose_seeded_value_coincides_is_still_addressed() -> None:
    # B-07, P2
    """Addressed, not changed: a coincidence of values is ``UNDETECTED``, never inapplicable.

    ``touched`` is the set of columns a class addresses by its own rule. Dropping
    the ones whose seeded value happens to equal the value already there — a
    flat row under ``COLUMN_SHIFT``, a zero under ``SIGN_FLIP`` — would be a
    comparison of values, which P2 forbids, and it would contradict B-07: the
    defect was seeded in that cell and the comparator could not see it, which is
    exactly what ``UNDETECTED`` records.
    """
    flat = sections(rows=with_flat_row(TIER_ONE_MISMATCHING_ROW))["profit-loss"]
    row = next(candidate for candidate in flat.rows if candidate.label == TIER_ONE_MISMATCHING_ROW)
    assert len({cell.value for cell in row.cells}) == 1  # a shift here rewrites nothing visible

    assert touched(
        flat, row_label=TIER_ONE_MISMATCHING_ROW, mutation=MutationClass.COLUMN_SHIFT
    ) == frozenset(PAGE_PERIODS)
    # The same rule on the zero of B-07: a sign flip that cannot show is not an
    # excuse, it is the miss the measurement is there to record.
    assert OLDEST_PERIOD in touched(
        sections()["profit-loss"],
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.SIGN_FLIP,
    )


def test_stale_period_is_not_applicable_when_no_column_was_compared() -> None:
    # B-03, M2
    """With nothing comparable to move, the class does not fire and says so.

    Reported as inapplicable rather than run against a column no comparison
    reads: a mutation that could not have been noticed is not evidence about the
    comparator, and P2 requires the no-op to come with an explicit rule.
    """
    section = sections()["profit-loss"]

    assert not is_applicable(
        section,
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.STALE_PERIOD,
        comparable_periods=frozenset(),
    )
    assert (
        mutate(
            section,
            row_label=TIER_ONE_AGREEING_ROW,
            mutation=MutationClass.STALE_PERIOD,
            comparable_periods=frozenset(),
        ).model_dump_json()
        == section.model_dump_json()
    )


@pytest.mark.parametrize("row_label", LAST_MAPPED_ROWS)
def test_row_swap_on_the_last_row_of_a_section_is_not_applicable(row_label: str) -> None:
    # B-03
    """There is no next row to exchange with, so nothing was measured there.

    Reported as ``NOT_APPLICABLE`` rather than silently as ``UNDETECTED``: a
    mutation that never happened is not evidence that the comparator is blind.
    P2 makes the mutation itself a no-op, so the verdict has to come from an
    applicability rule rather than from an unchanged outcome.
    """
    measured = report()
    section_name = next(name for name, rows in SENSITIVITY_ROWS.items() if rows[-1][0] == row_label)
    section = sections()[section_name]
    assert (
        mutate(section, row_label=row_label, mutation=MutationClass.ROW_SWAP).model_dump_json()
        == section.model_dump_json()
    )

    swapped = cells(measured, row_label=row_label, mutation=MutationClass.ROW_SWAP)
    assert len(swapped) == len(PAGE_PERIODS)
    assert {cell.classification for cell in swapped} == {Classification.NOT_APPLICABLE}


def test_every_row_of_every_section_is_mutated_by_every_class_in_every_period() -> None:
    # B-04
    """Coverage is the measurement, so unmapped and inapplicable cells are reported.

    Skipping the rows Lane B never reads would raise the sensitivity number by
    deleting its own worst cases; skipping ``NOT_APPLICABLE`` would hide how
    much of the sweep never ran.
    """
    measured = report()
    keys = {(cell.section, cell.row_label, cell.period, cell.mutation) for cell in measured.cells}
    assert len(measured.cells) == CELL_COUNT
    assert keys == {
        (section, label, period, mutation)
        for section, rows in SENSITIVITY_ROWS.items()
        for label, _ in rows
        for period in PAGE_PERIODS
        for mutation in MutationClass
    }
    assert any(cell.classification is Classification.NOT_APPLICABLE for cell in measured.cells)
    assert any(cell.classification is Classification.BLIND_UNMAPPED for cell in measured.cells)


def test_dropping_a_tier_one_row_is_detected_as_a_missing_screener_side() -> None:
    # B-07
    """A row the parser lost leaves the mapping's Screener side incomplete."""
    measured = report()
    for period in PAGE_PERIODS:
        cell = one_cell(
            measured,
            row_label=TIER_ONE_AGREEING_ROW,
            mutation=MutationClass.DROP_ROW,
            period=period,
        )
        assert cell.baseline_outcome is CrosscheckOutcome.AGREE
        assert cell.mutated_outcome is CrosscheckOutcome.MISSING_SCREENER
        assert cell.classification is Classification.DETECTED


def test_scaling_a_tier_one_row_by_ten_is_detected() -> None:
    # B-07
    """A dropped digit is a factor of ten, and 400 against 40 is far outside tolerance.

    Only the newest period is asserted: the oldest carries zero, where a factor
    of ten changes nothing and honestly cannot be detected.
    """
    cell = one_cell(
        report(),
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.SCALE_10,
        period=NEWEST_PERIOD,
    )
    assert cell.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    assert cell.baseline_outcome is CrosscheckOutcome.AGREE
    assert cell.mutated_outcome is CrosscheckOutcome.MISMATCH
    assert cell.classification is Classification.DETECTED


def test_one_crore_of_unit_drift_on_a_tier_one_row_clears_the_derived_tolerance() -> None:
    # B-07
    """The floor of the instrument: +1 crore against a tolerance of ~0.55 is seen.

    This is the smallest seeded defect the harness offers. If it were absorbed,
    every sensitivity number above it would be measuring a coarser instrument
    than the report claims. M3 records where it genuinely is absorbed: a
    two-addend tier-2 mapping tolerates 1.005 crore, so the same drift is
    invisible there and is reported as ``UNDETECTED`` rather than tuned away.
    """
    cell = one_cell(
        report(),
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.UNIT_DRIFT,
        period=NEWEST_PERIOD,
    )
    assert cell.baseline_outcome is CrosscheckOutcome.AGREE
    assert cell.mutated_outcome is CrosscheckOutcome.MISMATCH
    assert cell.classification is Classification.DETECTED


@pytest.mark.parametrize("row_label", UNMAPPED_ROWS)
def test_any_mutation_of_an_unmapped_row_is_blind_unmapped(row_label: str) -> None:
    # B-07
    """Lane B never reads these rows, so no mutation of one can be noticed.

    This is the coverage number, and it is the honest part of the measurement:
    a parser defect in a row nothing compares is invisible by construction.
    """
    unmapped = cells(report(), row_label=row_label)
    assert len(unmapped) == len(MutationClass) * len(PAGE_PERIODS)
    assert {cell.classification for cell in unmapped} == {Classification.BLIND_UNMAPPED}
    assert {cell.tier for cell in unmapped} == {None}


@pytest.mark.parametrize("row_label", TIER_THREE_ROWS)
def test_any_mutation_of_a_tier_three_row_is_blind_tier3(row_label: str) -> None:
    # B-07
    """Tier 3 answers ``NOT_COMPARABLE`` whatever the numbers, so nothing can be seen.

    The section's last row is included: P1 puts ``BLIND_TIER3`` above
    ``NOT_APPLICABLE``, so even the ``ROW_SWAP`` that cannot run there is
    reported as blindness rather than as an inapplicable case.
    """
    unprovable = cells(report(), row_label=row_label)
    assert len(unprovable) == len(MutationClass) * len(PAGE_PERIODS)
    assert {cell.classification for cell in unprovable} == {Classification.BLIND_TIER3}
    assert {cell.tier for cell in unprovable} == {EvidenceTier.EQUIVALENCE_UNPROVEN}


def test_flipping_the_sign_of_a_zero_is_undetected() -> None:
    # B-07
    """A zero cannot flip, and the harness must say so rather than score a pass.

    Counting this as detected — or dropping it — would inflate the sensitivity
    number with a mutation that never changed a value.
    """
    cell = one_cell(
        report(),
        row_label=TIER_ONE_AGREEING_ROW,
        mutation=MutationClass.SIGN_FLIP,
        period=OLDEST_PERIOD,
    )
    assert cell.baseline_outcome is CrosscheckOutcome.AGREE
    assert cell.mutated_outcome is CrosscheckOutcome.AGREE
    assert cell.classification is Classification.UNDETECTED


def test_a_mutation_of_an_already_mismatching_row_is_masked() -> None:
    # B-07, M4
    """The line was already disagreeing, so the mutation changes nothing observable.

    Scoring it as detected would credit the comparator for a disagreement that
    predates the defect.

    ``MASKED`` is claimed only where the mutation actually reached, though:
    ``STALE_PERIOD`` moves one column, so the column it left alone is
    ``NOT_APPLICABLE`` even here (M4, and P1 ranks it above ``MASKED``). A
    harness that reported the untouched column as masked would be describing a
    defect it never seeded.
    """
    mismatching = cells(report(), row_label=TIER_ONE_MISMATCHING_ROW)
    assert len(mismatching) == len(MutationClass) * len(PAGE_PERIODS)
    assert {cell.baseline_outcome for cell in mismatching} == {CrosscheckOutcome.MISMATCH}
    assert {
        cell.classification
        for cell in mismatching
        if cell.mutation is not MutationClass.STALE_PERIOD
    } == {Classification.MASKED}
    assert {
        cell.period: cell.classification
        for cell in mismatching
        if cell.mutation is MutationClass.STALE_PERIOD
    } == {
        NEWEST_PERIOD: Classification.MASKED,
        OLDEST_PERIOD: Classification.NOT_APPLICABLE,
    }


def test_a_class_is_scored_only_on_the_columns_it_moved() -> None:
    # M4
    """One re-keyed column is one measurement, not one measurement and three misses.

    ``STALE_PERIOD`` moves a single column. Charging the three it never touched
    as ``UNDETECTED`` describes the comparator as blind to a defect that was
    never seeded there, and it is how the provisional real measurement came to
    read 17 detected against 48 undetected on tier 1 while every row it could
    move, it moved. Four columns, because a two-column page cannot tell "scored
    one of two" from "scored the only one it touched".
    """
    measured = report(
        rows=with_two_newer_columns(),
        periods=FOUR_PERIODS,
        payloads=four_period_bodies(),
    )

    stale = cells(measured, row_label=TIER_ONE_AGREEING_ROW, mutation=MutationClass.STALE_PERIOD)
    assert len(stale) == len(FOUR_PERIODS)
    assert {cell.baseline_outcome for cell in stale} == {CrosscheckOutcome.AGREE}
    assert {cell.period: cell.classification for cell in stale} == {
        FOUR_PERIODS[0]: Classification.NOT_APPLICABLE,
        FOUR_PERIODS[1]: Classification.NOT_APPLICABLE,
        FOUR_PERIODS[2]: Classification.NOT_APPLICABLE,
        FOUR_PERIODS[3]: Classification.DETECTED,
    }


def test_a_period_upstox_never_answered_for_is_blind_rather_than_undetected() -> None:
    # M1
    """A Screener page runs 12 or 13 columns and Upstox answers 4 or 5.

    Nothing can be detected in a period that has no Upstox row at all, and the
    first real measurement showed what counting those cells as ``UNDETECTED``
    costs: 136 of 140 tier-1 misses were this, deflating tier-1 sensitivity from
    ~1.0 to 0.32. That is a number about the vendor's history depth reported as
    if it were a number about the comparator.
    """
    measured = report(rows=with_ttm_column(), periods=PAGE_PERIODS_WITH_TTM)

    unanswered = cells(measured, period=TTM_PERIOD)
    assert len(unanswered) == ROW_COUNT * len(MutationClass)
    assert {cell.period_compared for cell in unanswered} == {False}
    assert {
        cell.classification
        for cell in unanswered
        if cell.tier is not None and cell.tier is not EvidenceTier.EQUIVALENCE_UNPROVEN
    } == {Classification.BLIND_NO_UPSTOX}
    assert {cell.period_compared for cell in cells(measured, period=NEWEST_PERIOD)} == {True}


def test_a_line_upstox_did_not_carry_is_blind_even_where_the_period_was_compared() -> None:
    # M1
    """``MISSING_UPSTOX`` is the same blindness as a missing period, one line down.

    The period has an Upstox row and other lines in it are scored, so this is not
    a history-depth gap; the vendor simply did not carry that category. Either
    way there is nothing on the other side to disagree with.
    """
    measured = report(drop_category="net_profit")

    absent = cells(measured, row_label=TIER_ONE_MISMATCHING_ROW)
    assert len(absent) == len(MutationClass) * len(PAGE_PERIODS)
    assert {cell.baseline_outcome for cell in absent} == {CrosscheckOutcome.MISSING_UPSTOX}
    assert {cell.classification for cell in absent} == {Classification.BLIND_NO_UPSTOX}
    assert {cell.period_compared for cell in absent} == {True}


def test_a_mapping_whose_screener_side_was_already_incomplete_is_masked() -> None:
    # M1
    """``MISSING_SCREENER`` at baseline is a line already flagged, so a defect is masked.

    The comparator had refused to score this mapping before anything was seeded.
    Counting a further defect there as detected would credit it for a refusal
    that predates the defect, exactly as an existing mismatch would.
    """
    measured = report(rows=without_row(TIER_TWO_PARTNER_ROW))

    incomplete = cells(measured, row_label=TIER_TWO_ROW)
    assert {cell.baseline_outcome for cell in incomplete} == {CrosscheckOutcome.MISSING_SCREENER}
    # Every column the mutation reached; the one STALE_PERIOD left alone is
    # NOT_APPLICABLE, which M4 ranks above MASKED for the same reason.
    assert {
        cell.classification
        for cell in incomplete
        if cell.mutation is not MutationClass.STALE_PERIOD or cell.period == NEWEST_PERIOD
    } == {Classification.MASKED}
    # The rest of the page still measures: this is one mapping, not a broken run.
    assert any(
        cell.classification is Classification.DETECTED
        for cell in cells(measured, row_label=BALANCE_TIER_TWO_ROW)
    )
