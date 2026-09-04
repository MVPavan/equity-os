"""The parts of the sensitivity harness a reader sees, and the arithmetic under them.

The acceptance halves pin the measurement and the first line of the table. What
they do not pin is the shape of the rest of that table, and the TSV is the
artifact a human reads first — a total that disagreed with the lines above it,
or a coverage line that silently vanished, would be believed. These tests cover
that, the ``skipped`` list P6 requires when a company a run was asked for is not
in the root it was given, and two pieces of arithmetic that are easy to get
subtly wrong: truncation toward zero, and a row with nothing published on it.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from tests.fundamentals.laneb_sensitivity_fixtures import (
    BALANCE_TIER_TWO_ROW,
    BASIS,
    INCOME_ONLY_PERIOD,
    NEWEST_PERIOD,
    OLDEST_PERIOD,
    PAGE_PERIODS_WITH_INCOME_ONLY,
    SYMBOL,
    TIER_ONE_AGREEING_ROW,
    TITAN_ISIN,
    cells,
    cli_args,
    income_only_bodies,
    report,
    screener_root,
    sections,
    with_newer_income_column,
)
from tests.fundamentals.upstox_fixtures import statement_bodies, statement_fetch

from fundamentals.api.upstox_sensitivity_cli import (
    TSV_HEADER,
    SensitivityInputError,
    dispatch_upstox_sensitivity_command,
    render_sensitivity,
    run_upstox_sensitivity_command,
)
from fundamentals.ingest.screener_crosscheck import CrosscheckOutcome, EvidenceTier
from fundamentals.ingest.upstox_crosscheck import ScreenerSection
from fundamentals.ingest.upstox_source import UpstoxSurface
from fundamentals.ingest.upstox_statements import (
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)
from fundamentals.verify.laneb_sensitivity import (
    Classification,
    MutationClass,
    SensitivityCell,
    SensitivityReport,
    SkippedCompany,
    SkipReason,
    is_applicable,
    measure_sensitivity,
    mutate,
    touched,
)

ISIN = TITAN_ISIN
# The same identifier with a check digit that does not verify, which is why it
# is never looked up: an unknown ISIN answers 200 with an empty payload.
UNVERIFIABLE_ISIN = "INE280A01029"
OTHER_SYMBOL = "NOSUCH"
SECTION = "profit-loss"

_TIER_ONE = EvidenceTier.EQUIVALENCE_DEMONSTRATED
_MAPPED_ROW = "Profit before tax"
_UNMAPPED_ROW = "Tax"


def _cell(
    *,
    row_label: str,
    mutation: MutationClass,
    tier: EvidenceTier | None,
    classification: Classification,
    baseline: CrosscheckOutcome | None = None,
    mutated: CrosscheckOutcome | None = None,
    period: str = NEWEST_PERIOD,
    period_compared: bool = True,
    symbol: str = SYMBOL,
) -> SensitivityCell:
    """One record of the synthetic reports below, stated coordinate by coordinate."""
    return SensitivityCell(
        isin=ISIN,
        symbol=symbol,
        basis=StatementBasis.STANDALONE.value,
        section=SECTION,
        row_label=row_label,
        period=period,
        mutation=mutation,
        tier=tier,
        period_compared=period_compared,
        baseline_outcome=baseline,
        mutated_outcome=mutated,
        classification=classification,
    )


def _report() -> SensitivityReport:
    """One detected cell, one undetected, one unmapped row, one uncompared period."""
    return SensitivityReport.from_cells(
        (
            _cell(
                row_label=_MAPPED_ROW,
                mutation=MutationClass.DROP_ROW,
                tier=_TIER_ONE,
                baseline=CrosscheckOutcome.AGREE,
                mutated=CrosscheckOutcome.MISSING_SCREENER,
                classification=Classification.DETECTED,
            ),
            _cell(
                row_label=_MAPPED_ROW,
                mutation=MutationClass.SIGN_FLIP,
                tier=_TIER_ONE,
                baseline=CrosscheckOutcome.AGREE,
                mutated=CrosscheckOutcome.AGREE,
                classification=Classification.UNDETECTED,
            ),
            _cell(
                row_label=_MAPPED_ROW,
                mutation=MutationClass.DROP_ROW,
                tier=_TIER_ONE,
                period=OLDEST_PERIOD,
                period_compared=False,
                classification=Classification.BLIND_NO_UPSTOX,
            ),
            _cell(
                row_label=_UNMAPPED_ROW,
                mutation=MutationClass.DROP_ROW,
                tier=None,
                classification=Classification.BLIND_UNMAPPED,
            ),
        )
    )


def test_the_tsv_states_every_group_then_a_total_that_reconciles_with_them() -> None:
    """Each (class, tier) line, the unmapped group beside them, the total, both coverages.

    The unmapped group has to appear as its own line: P3 keeps those cells out of
    ``by_tier``, so a table built from tiers alone would drop the blind third of
    this report and still foot to a total that no longer matched its own lines.
    The ``blind`` column sums all three kinds of blindness, which is why the
    detected/undetected columns and it cannot be read as a partition of the row.
    """
    lines = render_sensitivity(_report()).splitlines()

    assert lines == [
        TSV_HEADER,
        "DROP_ROW\tEQUIVALENCE_DEMONSTRATED\t1\t0\t0\t1\t0\t1.0000",
        "DROP_ROW\tUNMAPPED\t0\t0\t0\t1\t0\t-",
        "SIGN_FLIP\tEQUIVALENCE_DEMONSTRATED\t0\t1\t0\t0\t0\t0.0000",
        "TOTAL\tALL\t1\t1\t0\t2\t0\t0.5000",
        f"COVERAGE\t{SECTION}\t1\t2\t\t\t\t0.5000",
        f"PERIOD_COVERAGE\t{SECTION}\t1\t2\t\t\t\t0.5000",
    ]


def test_a_group_with_nothing_scorable_reports_no_ratio_rather_than_zero() -> None:
    """A blind group is not a comparator that missed everything, and must not read as one."""
    report = _report()

    assert report.sensitivity == Decimal(1) / Decimal(2)
    assert report.by_mutation[MutationClass.COLUMN_SHIFT].sensitivity is None
    assert report.by_tier[_TIER_ONE].sensitivity == Decimal(1) / Decimal(2)
    assert report.by_tier[_TIER_ONE].blind_no_upstox == 1
    assert report.coverage_by_section == {SECTION: Decimal(1) / Decimal(2)}
    assert report.period_coverage_by_section == {SECTION: Decimal(1) / Decimal(2)}


def test_by_company_partitions_the_cells_rather_than_pooling_them() -> None:
    """A sweep covers many companies, and one blind company must not hide behind the rest."""
    report = SensitivityReport.from_cells(
        (
            _cell(
                row_label=_MAPPED_ROW,
                mutation=MutationClass.DROP_ROW,
                tier=_TIER_ONE,
                baseline=CrosscheckOutcome.AGREE,
                mutated=CrosscheckOutcome.MISSING_SCREENER,
                classification=Classification.DETECTED,
            ),
            _cell(
                row_label=_MAPPED_ROW,
                mutation=MutationClass.DROP_ROW,
                tier=_TIER_ONE,
                baseline=CrosscheckOutcome.AGREE,
                mutated=CrosscheckOutcome.AGREE,
                classification=Classification.UNDETECTED,
                symbol=OTHER_SYMBOL,
            ),
        )
    )

    assert set(report.by_company) == {SYMBOL, OTHER_SYMBOL}
    assert report.by_company[SYMBOL].sensitivity == Decimal(1)
    assert report.by_company[OTHER_SYMBOL].sensitivity == Decimal(0)
    assert report.sensitivity == Decimal(1) / Decimal(2)


def _one_row_section(*values: str, published: bool = True) -> ScreenerSection:
    """A single-row, two-column section stating exactly the values a test needs."""
    return ScreenerSection.model_validate(
        {
            "periods": [
                {"index": 0, "label": OLDEST_PERIOD},
                {"index": 1, "label": NEWEST_PERIOD},
            ],
            "rows": [
                {
                    "label": _MAPPED_ROW,
                    "cells": [
                        {"period_index": index, "value": value, "published": published}
                        for index, value in enumerate(values)
                    ],
                }
            ],
        }
    )


def test_thousands_truncation_drops_the_tail_on_a_negative_row_too() -> None:
    """A separator misread as a decimal point loses digits; it does not round down.

    Pinned because the obvious implementation is wrong on exactly one side:
    Python's integer ``//`` floors, so -1234 would become -2 and the seeded
    defect would be a different one on every negative row a cash-flow page
    carries. Decimal division truncates toward zero, which is what a lost tail
    actually looks like.
    """
    section = _one_row_section("-1234", "1234")

    mutated = mutate(section, row_label=_MAPPED_ROW, mutation=MutationClass.THOUSANDS_TRUNCATED)

    values = {cell.period_index: cell.value for cell in mutated.rows[0].cells}
    assert values == {0: Decimal("-1"), 1: Decimal("1")}


def test_a_row_with_nothing_published_cannot_carry_a_value_defect() -> None:
    """No published figure means no figure to corrupt, so the class does not apply.

    Reported as inapplicable rather than as a mutation that changed nothing:
    an unpublished row is a gap in the page, and scoring it ``UNDETECTED`` would
    blame the comparator for not noticing a defect nobody could seed.
    """
    section = _one_row_section("100", "200", published=False)

    assert not is_applicable(section, row_label=_MAPPED_ROW, mutation=MutationClass.SCALE_10)
    assert (
        mutate(section, row_label=_MAPPED_ROW, mutation=MutationClass.SCALE_10).model_dump_json()
        == section.model_dump_json()
    )


def test_a_company_absent_from_both_bases_is_skipped_once_per_basis(tmp_path: Path) -> None:
    """P6's skip path, per basis, and what kind of gap each one was.

    Two bases are requested from roots that hold neither, so ``skipped`` is the
    only place the gap is recorded. Without it a reader cannot tell a company
    nobody measured from a company where nothing was found — and without the
    reason, cannot tell a retention gap from an identifier that never verified.
    """
    isin_file = tmp_path / "isins.tsv"
    isin_file.write_text(
        f"{ISIN}\t{SYMBOL}\n{UNVERIFIABLE_ISIN}\t{OTHER_SYMBOL}\n", encoding="utf-8"
    )
    screener_root = tmp_path / "screener"
    upstox_root = tmp_path / "upstox"
    screener_root.mkdir()
    upstox_root.mkdir()

    report = run_upstox_sensitivity_command(
        isin_file=isin_file,
        screener_root=screener_root,
        upstox_root=upstox_root,
        bases=(StatementBasis.STANDALONE, StatementBasis.CONSOLIDATED),
    )

    assert report.cells == ()
    assert report.skipped == (
        SkippedCompany(symbol=SYMBOL, basis="standalone", reason=SkipReason.NO_SCREENER_SECTIONS),
        SkippedCompany(symbol=SYMBOL, basis="consolidated", reason=SkipReason.NO_SCREENER_SECTIONS),
        SkippedCompany(symbol=OTHER_SYMBOL, basis="standalone", reason=SkipReason.INVALID_ISIN),
        SkippedCompany(symbol=OTHER_SYMBOL, basis="consolidated", reason=SkipReason.INVALID_ISIN),
    )


def test_a_company_whose_page_is_held_but_whose_bodies_are_not_is_a_retention_gap(
    tmp_path: Path,
) -> None:
    """Sections on disk and nothing retained beside them is the third kind of gap.

    A retention tree assembled over several runs will not cover every company a
    later join file lists. That is a hole in the inputs, not a company without a
    Screener page, and the two call for different work.
    """
    isin_file = tmp_path / "isins.tsv"
    isin_file.write_text(f"{ISIN}\t{SYMBOL}\n", encoding="utf-8")
    empty_upstox_root = tmp_path / "upstox-empty"
    empty_upstox_root.mkdir()

    report = run_upstox_sensitivity_command(
        isin_file=isin_file,
        screener_root=screener_root(tmp_path),
        upstox_root=empty_upstox_root,
        bases=(StatementBasis.STANDALONE,),
    )

    assert report.cells == ()
    assert report.skipped == (
        SkippedCompany(symbol=SYMBOL, basis="standalone", reason=SkipReason.NO_RETAINED_BODIES),
    )


def test_a_join_file_this_command_cannot_read_raises_its_own_error(tmp_path: Path) -> None:
    """The refusal is typed, so the caller decides the exit code rather than the reader.

    The join reader ends the process on a malformed line, which is right for the
    command that owns it and wrong here: this one has to answer 3 (P6) and must
    not catch every deliberate exit inside a whole run to do it.
    """
    isin_file = tmp_path / "isins.tsv"
    isin_file.write_text("one-column-only\n", encoding="utf-8")
    root = tmp_path / "either-root"
    root.mkdir()

    with pytest.raises(SensitivityInputError):
        run_upstox_sensitivity_command(
            isin_file=isin_file,
            screener_root=root,
            upstox_root=root,
            bases=(StatementBasis.STANDALONE,),
        )


def test_a_company_whose_upstox_response_cannot_be_read_is_not_measured() -> None:
    """An unreadable response is a gap, not a comparator that noticed nothing.

    Scoring its rows ``UNDETECTED`` would blame Lane B for a parse failure
    upstream of it and would report exactly the blind instrument this whole
    measurement exists to detect.
    """
    bodies = statement_bodies(StatementBasis.STANDALONE.value)
    drifted = {"status": "success", "data": {"type": "standalone", "time_period": "yearly"}}

    report = measure_sensitivity(
        isin=ISIN,
        symbol=SYMBOL,
        basis=StatementBasis.STANDALONE,
        sections={},
        income=read_income_statement(
            statement_fetch(drifted, surface=UpstoxSurface.INCOME_STATEMENT),
            requested_basis=StatementBasis.STANDALONE,
        ),
        balance=read_balance_sheet(
            statement_fetch(
                bodies[UpstoxSurface.BALANCE_SHEET], surface=UpstoxSurface.BALANCE_SHEET
            ),
            requested_basis=StatementBasis.STANDALONE,
        ),
        cash=read_cash_flow(
            statement_fetch(bodies[UpstoxSurface.CASH_FLOW], surface=UpstoxSurface.CASH_FLOW),
            requested_basis=StatementBasis.STANDALONE,
        ),
    )

    assert report.cells == ()
    assert report.skipped == (
        SkippedCompany(symbol=SYMBOL, basis="standalone", reason=SkipReason.UPSTOX_UNREADABLE),
    )
    assert report.sensitivity is None


def _with_unpublished_newest(row_label: str) -> ScreenerSection:
    """The profit-loss section with one row's newest column present but unpublished."""
    section = sections()["profit-loss"]
    row = next(candidate for candidate in section.rows if candidate.label == row_label)
    newest = max(cell.period_index for cell in row.cells)
    hidden = row.model_copy(
        update={
            "cells": tuple(
                cell.model_copy(update={"published": False})
                if cell.period_index == newest
                else cell
                for cell in row.cells
            )
        }
    )
    return section.model_copy(
        update={
            "rows": tuple(
                hidden if candidate.label == row_label else candidate for candidate in section.rows
            )
        }
    )


def test_stale_period_passes_over_a_newest_column_the_comparator_would_not_read() -> None:
    """An unpublished cell is skipped by the comparison, so re-keying it is a no-op.

    The class would still be *scored* on that column, and would report a
    guaranteed miss as evidence about Lane B. It has to fall back to the newest
    column a comparison actually reads.
    """
    section = _with_unpublished_newest(TIER_ONE_AGREEING_ROW)

    assert touched(
        section, row_label=TIER_ONE_AGREEING_ROW, mutation=MutationClass.STALE_PERIOD
    ) == frozenset({OLDEST_PERIOD})


def test_stale_period_aims_at_a_period_this_mapping_was_scored_in() -> None:
    """The three surfaces do not answer for the same periods, and a target is per mapping.

    On this page the income statement reaches one column further than the
    balance sheet. Aiming every row at the newest period *any* surface answered
    for lands the balance-sheet rows on a cell that is ``BLIND_NO_UPSTOX``, so
    the class would move nothing and — worse — the column it could have been
    caught in would be reported as untouched.
    """
    measured = report(
        rows=with_newer_income_column(),
        periods=PAGE_PERIODS_WITH_INCOME_ONLY,
        payloads=income_only_bodies(),
    )

    balance = {
        cell.period: cell.classification
        for cell in cells(
            measured, row_label=BALANCE_TIER_TWO_ROW, mutation=MutationClass.STALE_PERIOD
        )
    }
    assert balance == {
        OLDEST_PERIOD: Classification.NOT_APPLICABLE,
        NEWEST_PERIOD: Classification.DETECTED,
        INCOME_ONLY_PERIOD: Classification.BLIND_NO_UPSTOX,
    }
    # The same page, one section over: the income statement *was* scored in the
    # newer column, so that is where its own row is caught.
    income = {
        cell.period: cell.classification
        for cell in cells(
            measured, row_label=TIER_ONE_AGREEING_ROW, mutation=MutationClass.STALE_PERIOD
        )
    }
    assert income[INCOME_ONLY_PERIOD] is Classification.DETECTED
    assert income[NEWEST_PERIOD] is Classification.NOT_APPLICABLE


def test_a_retained_body_the_filesystem_will_not_hand_over_exits_three(
    tmp_path: Path,
) -> None:
    """A tree that answers ``is_file()`` and then refuses the read is an unreadable input.

    P6 says exit 3, and a traceback out of a measurement command is not a
    refusal — it is an unhandled error that a caller cannot tell from a crash.
    """
    args = cli_args(tmp_path)
    body = (
        Path(str(args.upstox_root))
        / SYMBOL
        / BASIS.value
        / f"{UpstoxSurface.INCOME_STATEMENT.value}.raw.json"
    )
    body.chmod(0o000)
    try:
        assert dispatch_upstox_sensitivity_command(args) == 3
    finally:
        body.chmod(0o644)

    assert not (tmp_path / "out").exists()  # a refusal leaves nothing behind
