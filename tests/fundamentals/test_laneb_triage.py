"""Lane B step 5(c): does a per-field warn triage separate defects from disagreement?

Acceptance tests for ``scratchpad/laneb-5c/plan.md`` (C-01..C-10, tests T1..T12,
T14, T17, T18 and T20). The command-level half — ``warnings.tsv``, the summary's
``warn`` column and ``--warn-exit`` — is in ``test_laneb_triage_cli``; the config
half — what a threshold or an exclusion has to arrive with (T13) and the shipped
file itself (T19) — is in ``test_laneb_triage_config``.

**Why a triage exists at all.** The Part 2 sweep read 344 live lines and found 68
of 69 non-agreeing lines at or under 20% relative difference, while the Part 3
sensitivity harness found every seeded parser defect at 90% or more, or
structural (``DROP_ROW`` and ``STALE_PERIOD`` land as ``MISSING_SCREENER``). A
magnitude floor plus a structural class is therefore the only separation the two
measurements actually support, and everything below it is noise a reviewer must
not be paged for. Persistence across periods separates nothing — definitional
disagreements persist exactly as a parser defect would — so no rule here reads
period counts.

**Names this half pins** (the implementation must match them):
``fundamentals.verify.laneb_triage`` exporting ``TriageClass``, ``WARN_CLASSES``,
``LISTED_CLASSES``, ``relative_difference``, ``TriageConfig``,
``Acknowledgement``, ``TriageConfigError``, ``load_triage_config``,
``triage_run``, ``render_warnings``, ``WARNINGS_HEADER`` and
``WARNINGS_FILENAME``; ``CrosscheckRow.relative_difference`` and
``CrosscheckRow.triage``; ``CrosscheckRunReport.warn_count`` and
``.listed_count``; and ``upstox_statements.parse_identity_note``.

Every number here is invented. The real figures the rules were derived from are
cited in prose only — no value from the licensed sweep is committed to this
repository. Every name under test is imported *inside* a test so that a missing
module fails each behaviour on its own rather than collapsing collection.
"""

from __future__ import annotations

from decimal import Decimal
from types import ModuleType
from typing import Any

import pytest
from tests.fundamentals.upstox_fixtures import BSE_ISIN, NSE_ISIN, NSE_SYMBOL

from fundamentals.ingest.screener_crosscheck import (
    CRORE_SCALE,
    CrosscheckOutcome,
    CrosscheckReport,
    CrosscheckRow,
    mapping_for,
)
from fundamentals.ingest.upstox_crosscheck import (
    CompanyCrosscheck,
    CompanyStatus,
    CrosscheckRunReport,
)
from fundamentals.ingest.upstox_source import UpstoxSurface
from fundamentals.ingest.upstox_statements import (
    _SUMMARY_DISAGREES,
    FULL_STATEMENT_IS_ALWAYS_ANNUAL,
    INCOME_SUMMARY_IDENTITIES,
)
from fundamentals.verify.crossfoot import half_ulp

DEFAULT_WARN_RATIO = Decimal("0.20")

BASIS = "standalone"
NEWER = "Mar 2026"
OLDER = "Mar 2025"
OLDEST = "Mar 2024"

# A second synthetic issuer, so one run can carry two companies. Both ISINs use
# the ``999Z`` issuer block no real issuer holds and carry correct check digits.
OTHER_ISIN = BSE_ISIN
OTHER_SYMBOL = "OTHERCO"

TEST_OWNER = "test-owner"
TEST_REASON = "acknowledged for the test's own reason"
TEST_MEASURED_IN = "scratchpad/laneb-5c/proposal.md"

# Short local names for the outcomes a fixture row states. The comparison has
# already decided these; the triage only classifies what it was handed.
AGREE = CrosscheckOutcome.AGREE
MISMATCH = CrosscheckOutcome.MISMATCH
ANOMALY = CrosscheckOutcome.ANOMALY
NOT_COMPARABLE = CrosscheckOutcome.NOT_COMPARABLE
MISSING_UPSTOX = CrosscheckOutcome.MISSING_UPSTOX
MISSING_SCREENER = CrosscheckOutcome.MISSING_SCREENER

# ``(upstox category, outcome, upstox amount, screener amount)`` — amounts as the
# strings a source stated them in, so no fixture value is a binary float.
RowSpec = tuple[str, CrosscheckOutcome, str | None, str | None]


def _triage() -> ModuleType:
    """Import the module under test at call time, not at collection time."""
    from fundamentals.verify import laneb_triage

    return laneb_triage


def _tolerance(*stated: str | None) -> Decimal | None:
    """The interval the comparison would have derived for these stated values.

    Each rounded value contributes half a unit in its own last stated place, on
    both sides, which is how rounding error propagates through addition — the
    same derivation ``compare_line`` uses, so no fixture picks its own interval.
    A row one side did not cover was never scored and carries none.
    """
    if any(value is None for value in stated):
        return None
    return sum(
        (half_ulp(len(value.partition(".")[2]), CRORE_SCALE) for value in stated if value),
        Decimal(0),
    )


def _rows(*specs: RowSpec) -> tuple[CrosscheckRow, ...]:
    """Report rows for mapped categories, each carrying its declared tier.

    The tier and meaning come from the name map rather than from the test, so a
    fixture row can never claim a strength the mapping does not grant it.
    """
    built: list[CrosscheckRow] = []
    for category, outcome, upstox, screener in specs:
        mapping = mapping_for(category)
        built.append(
            CrosscheckRow(
                upstox_category=category,
                means=mapping.means,
                tier=mapping.tier,
                outcome=outcome,
                upstox_amount=None if upstox is None else Decimal(upstox),
                screener_amount=None if screener is None else Decimal(screener),
                tolerance=_tolerance(upstox, screener),
            )
        )
    return tuple(built)


def _company(
    periods: dict[str, tuple[CrosscheckRow, ...]],
    *,
    isin: str = NSE_ISIN,
    symbol: str = NSE_SYMBOL,
    anomalies: tuple[str, ...] = (),
) -> CompanyCrosscheck:
    """One compared company, newest period first as the comparison orders them."""
    return CompanyCrosscheck(
        isin=isin,
        symbol=symbol,
        basis=BASIS,
        status=CompanyStatus.COMPARED,
        upstox_anomalies=anomalies,
        reports=tuple(
            CrosscheckReport(isin=isin, basis=BASIS, period=period, rows=rows)
            for period, rows in periods.items()
        ),
    )


def _run(*companies: CompanyCrosscheck) -> CrosscheckRunReport:
    """A run report built in memory: no file, no socket, no fetch."""
    return CrosscheckRunReport(companies=companies)


def _one(
    *specs: RowSpec, period: str = NEWER, anomalies: tuple[str, ...] = ()
) -> CrosscheckRunReport:
    """A one-company, one-period run — the smallest fixture a per-row rule needs."""
    return _run(_company({period: _rows(*specs)}, anomalies=anomalies))


# How far the summary block sat from the ``full_statement`` particular in a
# note the reader writes. Any gap beyond the row's own interval will do.
IDENTITY_GAP = Decimal("0.97")


def _identity_note(category: str, period: str, *, full: str) -> str:
    """The self-contradiction note a company carries, in the form it is stored in.

    ``compare_company`` prefixes every parse note with the surface it came from,
    so this is what ``CompanyCrosscheck.upstox_anomalies`` actually holds — the
    string the convergence rule (C-03's UPSTOX_SIDE) has to recognise. ``full``
    is the figure the same response's ``full_statement`` stated, and the rule
    reads it rather than only the cell's name: the alibi is Screener agreeing
    with that figure, not the mere existence of a contradiction.
    """
    stated = Decimal(full)
    note = _SUMMARY_DISAGREES.format(
        category=category,
        period=period,
        summary=stated + IDENTITY_GAP,
        particular=dict(INCOME_SUMMARY_IDENTITIES)[category],
        full=stated,
    )
    return f"{UpstoxSurface.INCOME_STATEMENT.value}: {note}"


def _acknowledgement(
    module: ModuleType, category: str, *, isin: str = NSE_ISIN, symbol: str = NSE_SYMBOL
) -> Any:
    """One acknowledged (company, field) exclusion, carrying its reason and source."""
    return module.Acknowledgement(
        isin=isin,
        symbol=symbol,
        upstox_category=category,
        reason=TEST_REASON,
        measured_in=TEST_MEASURED_IN,
    )


def _config(
    module: ModuleType,
    *,
    ratio: Decimal = DEFAULT_WARN_RATIO,
    acknowledged: tuple[Any, ...] = (),
) -> Any:
    """A triage config built directly, so a pure test needs no YAML on disk."""
    return module.TriageConfig(
        magnitude_warn_ratio=ratio, review_owner=TEST_OWNER, acknowledged=acknowledged
    )


def _classes(report: CrosscheckRunReport) -> dict[tuple[str, str], Any]:
    """Every triaged row of a run, keyed by (period, upstox category)."""
    return {
        (crosscheck.period, row.upstox_category): row.triage
        for company in report.companies
        for crosscheck in company.reports
        for row in crosscheck.rows
    }


@pytest.mark.parametrize(
    ("upstox", "screener", "expected"),
    [
        ("100", "80", "0.20"),
        ("40", "28", "0.30"),
        ("-100", "-80", "0.20"),
        ("-50", "50", "2"),
        ("0", "5", "1"),
        (None, "10", None),
        ("10", None, None),
        ("0", "0", None),
    ],
)
def test_relative_difference_is_the_measure_both_thresholds_were_derived_from(
    upstox: str | None, screener: str | None, expected: str | None
) -> None:
    """T1/C-02: one scale-free measure, so the 20% bar means the same on every line.

    ``|U - S| / max(|U|, |S|)`` is the statistic both measurements were reported
    in — the sweep's "68 of 69 at or under 20%" and the harness's "scale and sign
    defects at 90% or more" are not comparable under any other denominator.
    Negatives take absolute values because cash-flow and expense lines are
    legitimately negative and a signed ratio would rank a sign flip below a
    rounding difference. A missing side is not a difference of zero: the row is
    already recorded as missing and scoring it would invent a comparison. Both
    sides at zero have no scale to divide by, so nothing is claimed.
    """
    result = _triage().relative_difference(
        None if upstox is None else Decimal(upstox),
        None if screener is None else Decimal(screener),
    )
    if expected is None:
        assert result is None
    else:
        assert isinstance(result, Decimal)
        assert result == Decimal(expected)


def test_a_tier_one_line_screener_never_published_is_structural() -> None:
    """T2/C-03: the class the sensitivity harness proved detectable at rate 1.0.

    ``DROP_ROW`` and ``STALE_PERIOD`` both surface as ``MISSING_SCREENER`` and
    both were caught on every seeded cell, while the 344-line live sweep produced
    no ``MISSING_SCREENER`` on a mapped tier-1 row at all. A class with a zero
    live base rate and a perfect detection rate is the one thing here worth a
    reviewer's attention unconditionally, whatever the numbers are — so it does
    not consult the magnitude bar and carries no relative difference.
    """
    module = _triage()
    triaged = module.triage_run(_one(("net_profit", MISSING_SCREENER, "30", None)), _config(module))
    row = triaged.companies[0].reports[0].rows[0]
    assert row.triage is module.TriageClass.STRUCTURAL
    assert row.relative_difference is None


def test_a_line_upstox_never_published_is_not_a_finding() -> None:
    """T3/C-03: a gap on the Upstox side says nothing about this repo's parse.

    ``MISSING_UPSTOX`` means the vendor's summary block did not carry that
    category for that period. Nothing about the Screener extraction is implicated
    and there is no value to measure, so it is not listed and never warns —
    otherwise every company Upstox covers thinly would fill the review queue.
    """
    module = _triage()
    triaged = module.triage_run(_one(("net_profit", MISSING_UPSTOX, None, "30")), _config(module))
    assert triaged.companies[0].reports[0].rows[0].triage is module.TriageClass.NONE


@pytest.mark.parametrize(("screener", "expected"), [("80", "MAGNITUDE"), ("80.01", "NOISE")])
def test_the_magnitude_bar_is_inclusive_at_the_ratio(screener: str, expected: str) -> None:
    """T4/C-03: the bar is a decision boundary, so which side it includes is a rule.

    20% is where the two measurements stop overlapping: the sweep put 68 of 69
    live disagreements at or under it, and every seeded scale, sign or truncation
    defect at 90% or more. A value landing exactly on the bar is therefore a warn
    — the sweep's one line above it was 32.5% and is handled as an acknowledged
    exclusion, not by moving the bar. One unit in the values' own last stated
    place (0.01 crore, the precision Upstox states) below the bar is noise, which
    pins the comparison as ``>=`` rather than ``>``.
    """
    module = _triage()
    triaged = module.triage_run(_one(("net_profit", MISMATCH, "100", screener)), _config(module))
    assert triaged.companies[0].reports[0].rows[0].triage is getattr(module.TriageClass, expected)


def test_a_tier_three_line_is_never_triaged_however_large_it_is() -> None:
    """T5/C-03: equivalence is unproven there, so a large gap proves nothing either.

    The first live replay's biggest single disagreement was a tier-3 operating
    cash-flow line, and it is still not evidence of a defect: the two sides were
    never shown to mean the same thing, so a difference is as consistent with the
    mapping being wrong as with the parse being wrong. ``unmet_tier3_count``
    already counts these for the graduation procedure; warning on them would
    convert an unproven mapping into a page for the review owner.
    """
    module = _triage()
    triaged = module.triage_run(_one(("operating", NOT_COMPARABLE, "250", "50")), _config(module))
    assert triaged.companies[0].reports[0].rows[0].triage is module.TriageClass.NONE


def test_a_line_within_its_derived_tolerance_is_not_listed() -> None:
    """T6/C-03: agreement is the overwhelming majority and must cost nothing.

    Agreeing lines sat at a median 0.008% relative difference in the sweep. If
    ``AGREE`` produced any class other than ``NONE`` the triage file would be the
    report again, and the queue it exists to create would be unreadable.
    """
    module = _triage()
    triaged = module.triage_run(_one(("net_profit", AGREE, "30", "30")), _config(module))
    assert triaged.companies[0].reports[0].rows[0].triage is module.TriageClass.NONE


def test_the_convergence_rule_needs_the_cell_and_the_full_statement_figure() -> None:
    """T7/C-03/A1: the alibi is one cell, and only where Screener matches the vendor.

    When one response states two different numbers for the same figure, "Upstox
    says X" is not well defined for that category and period, and a Screener
    disagreement on that same cell can be placed on the vendor rather than on
    this repo's parse. That reasoning is exactly as wide as the note: the same
    category in another period, or another category in the same period, has no
    such alibi and stays a magnitude finding. Widening it by category alone would
    silence a real defect for every period of an affected company.

    It is also narrower than the note's existence. The first real replay found a
    company whose response contradicted itself on revenue while Screener sat
    about 50 crore from *both* Upstox figures — the summary block being
    unreliable there says nothing about a third value that matches neither, and
    calling it Upstox-side would have exonerated exactly the case the lane exists
    to catch. The alibi holds only where Screener agrees with the figure the
    response's own ``full_statement`` stated, inside the row's derived interval.
    """
    module = _triage()
    triaged = module.triage_run(
        _run(
            _company(
                {
                    NEWER: _rows(("operating_profit", MISMATCH, "100", "70")),
                    OLDER: _rows(
                        ("revenue", AGREE, "200", "200"),
                        ("operating_profit", MISMATCH, "100", "70"),
                        ("net_profit", MISMATCH, "100", "70"),
                    ),
                    OLDEST: _rows(("revenue", ANOMALY, "11041", "11091")),
                },
                anomalies=(
                    _identity_note("operating_profit", OLDER, full="70"),
                    _identity_note("revenue", OLDEST, full="11041.49"),
                ),
            )
        ),
        _config(module),
    )
    classes = _classes(triaged)
    assert classes[(OLDER, "operating_profit")] is module.TriageClass.UPSTOX_SIDE
    assert classes[(OLDER, "net_profit")] is module.TriageClass.MAGNITUDE
    assert classes[(NEWER, "operating_profit")] is module.TriageClass.MAGNITUDE
    assert classes[(OLDEST, "revenue")] is module.TriageClass.NOISE


def test_an_acknowledged_field_is_listed_but_a_missing_row_on_it_still_warns() -> None:
    """T8/C-03: an exclusion covers a known definitional gap, not the whole line.

    Two tier-1 exclusions are documented in the name map's ``means`` — one where
    exceptional items are material, one where associates or minority interest sit
    differently — and the sweep's single above-bar line (32.5%) is one of them.
    Acknowledging them stops a known definitional difference from paging anyone
    every run, and they stay listed rather than suppressed so the queue still
    carries them. But the acknowledgement is about two numbers meaning different
    things; it says nothing about a Screener row that stopped existing, which is
    the structural class with a perfect detection rate. Letting an
    acknowledgement swallow that would be the one way this design could hide a
    real parser defect.
    """
    module = _triage()
    triaged = module.triage_run(
        _run(
            _company(
                {
                    NEWER: _rows(("operating_profit", MISMATCH, "100", "68")),
                    OLDER: _rows(("operating_profit", MISSING_SCREENER, "100", None)),
                }
            )
        ),
        _config(module, acknowledged=(_acknowledgement(module, "operating_profit"),)),
    )
    classes = _classes(triaged)
    assert classes[(NEWER, "operating_profit")] is module.TriageClass.ACKNOWLEDGED
    assert classes[(OLDER, "operating_profit")] is module.TriageClass.STRUCTURAL


@pytest.mark.parametrize(
    ("specs", "expected"),
    [
        pytest.param(
            (
                ("revenue", ANOMALY, "100", "75"),
                ("operating_profit", MISMATCH, "100", "95"),
                ("net_profit", MISMATCH, "100", "97"),
            ),
            {
                "revenue": "WHOLE_TABLE",
                "operating_profit": "WHOLE_TABLE",
                "net_profit": "WHOLE_TABLE",
            },
            id="every-category-disagrees-and-one-is-large",
        ),
        pytest.param(
            (
                ("revenue", AGREE, "100", "100"),
                ("operating_profit", MISMATCH, "100", "75"),
                ("net_profit", MISMATCH, "100", "97"),
            ),
            {"revenue": "NONE", "operating_profit": "MAGNITUDE", "net_profit": "NOISE"},
            id="one-category-agrees",
        ),
        pytest.param(
            (
                ("revenue", ANOMALY, "100", "95"),
                ("operating_profit", MISMATCH, "100", "97"),
                ("net_profit", MISMATCH, "100", "99"),
            ),
            {"revenue": "NOISE", "operating_profit": "NOISE", "net_profit": "NOISE"},
            id="all-disagree-but-none-reaches-the-bar",
        ),
        pytest.param(
            (("total_asset", ANOMALY, "100", "75"),),
            {"total_asset": "MAGNITUDE"},
            id="a-section-with-one-category-present",
        ),
    ],
)
def test_breadth_only_counts_when_a_magnitude_or_structural_row_is_in_it(
    specs: tuple[RowSpec, ...], expected: dict[str, str]
) -> None:
    """T9/C-04: breadth alone is a false alarm; breadth with a large row is a shift.

    The sweep settles both halves. No profit-and-loss period had all three mapped
    categories disagreeing, so breadth is rare — but the balance sheet has only
    two mapped categories and both disagreed in more than a third of periods from
    ordinary rounding, so breadth *without* a magnitude floor would warn on a
    third of all balance sheets forever. Breadth and a 20% row together occurred
    in no period of the live sweep, while a table-wide scale or column shift
    produces exactly that pattern. A section with a single category present has
    no breadth to observe and must never fire on it.
    """
    module = _triage()
    classes = _classes(module.triage_run(_one(*specs), _config(module)))
    assert {category: classes[(NEWER, category)] for category in expected} == {
        category: getattr(module.TriageClass, name) for category, name in expected.items()
    }


def test_a_whole_table_pass_never_overwrites_a_class_that_already_explains_a_row() -> None:
    """T10/C-04: breadth relabels only rows whose own class carries no explanation.

    Whole-table is a hypothesis about a section — one shift or rescale hitting
    every line at once. A row that is structurally missing, that an Upstox
    self-contradiction already accounts for, or that a documented definitional
    exclusion already accounts for, has a better explanation than the hypothesis,
    and overwriting it would delete the reason a reviewer needs. Only magnitude
    and noise rows — the ones whose own class says "large" or "small" and nothing
    else — are re-read as part of the table.
    """
    module = _triage()
    triaged = module.triage_run(
        _run(
            _company(
                {
                    NEWER: _rows(
                        ("revenue", ANOMALY, "100", "75"),
                        ("operating_profit", MISMATCH, "100", "70"),
                        ("net_profit", MISMATCH, "100", "68"),
                        ("total_asset", MISSING_SCREENER, "600", None),
                        ("total_liability", ANOMALY, "400", "300"),
                    )
                },
                anomalies=(_identity_note("operating_profit", NEWER, full="70"),),
            )
        ),
        _config(module, acknowledged=(_acknowledgement(module, "net_profit"),)),
    )
    classes = _classes(triaged)
    assert classes[(NEWER, "revenue")] is module.TriageClass.WHOLE_TABLE
    assert classes[(NEWER, "operating_profit")] is module.TriageClass.UPSTOX_SIDE
    assert classes[(NEWER, "net_profit")] is module.TriageClass.ACKNOWLEDGED
    assert classes[(NEWER, "total_asset")] is module.TriageClass.STRUCTURAL
    assert classes[(NEWER, "total_liability")] is module.TriageClass.WHOLE_TABLE


@pytest.mark.parametrize(
    ("spec", "noted", "acknowledged", "expected"),
    [
        pytest.param(
            ("operating_profit", MISSING_SCREENER, "100", None),
            True,
            True,
            "STRUCTURAL",
            id="structural-beats-everything",
        ),
        pytest.param(
            ("operating_profit", MISMATCH, "100", "68"),
            True,
            True,
            "UPSTOX_SIDE",
            id="upstox-side-beats-acknowledged-and-magnitude",
        ),
        pytest.param(
            ("operating_profit", MISMATCH, "100", "68"),
            False,
            True,
            "ACKNOWLEDGED",
            id="acknowledged-beats-magnitude",
        ),
        pytest.param(
            ("operating_profit", MISMATCH, "100", "68"),
            False,
            False,
            "MAGNITUDE",
            id="magnitude-above-the-bar",
        ),
        pytest.param(
            ("operating_profit", MISMATCH, "100", "95"),
            False,
            False,
            "NOISE",
            id="noise-below-the-bar",
        ),
        pytest.param(
            ("operating_profit", AGREE, "100", "100"),
            False,
            False,
            "NONE",
            id="agreement-is-not-a-class",
        ),
    ],
)
def test_one_row_gets_exactly_one_class_in_a_fixed_order(
    spec: RowSpec, noted: bool, acknowledged: bool, expected: str
) -> None:
    """T11/C-03: every row carries one class, and which one is not order-dependent.

    Each row here satisfies several rules at once — the same 32% line is above
    the magnitude bar, inside an acknowledgement and covered by an Upstox
    self-contradiction — so without a pinned precedence the class a reviewer sees
    would depend on evaluation order and could change between releases. The order
    encodes what each class is worth: structural first because it is the only one
    the sensitivity harness caught every time, then the two that place the fault
    somewhere other than this repo's parse, then magnitude.
    """
    module = _triage()
    config = _config(
        module, acknowledged=(_acknowledgement(module, spec[0]),) if acknowledged else ()
    )
    triaged = module.triage_run(
        _one(spec, anomalies=(_identity_note(spec[0], NEWER, full="68"),) if noted else ()),
        config,
    )
    assert triaged.companies[0].reports[0].rows[0].triage is getattr(module.TriageClass, expected)


def test_the_run_counts_what_warns_and_what_is_merely_listed_without_changing_exit() -> None:
    """T12/C-08: the counts are the telemetry the block decision was deferred on.

    No block is proposed anywhere in this step, because the live sweep produced
    zero parser defects in 344 lines and Lane B reads only part of every table.
    The number that could change that is how many rows warn per run over a month
    of real use, so warn and listed have to be countable — and separately, since
    acknowledged and Upstox-side rows belong in the queue but must never inflate
    the warn figure a future block would be argued from. The exit code stays the
    comparison's own: decision A is log-only and only the command may deviate.
    """
    module = _triage()
    triaged = module.triage_run(
        _run(
            _company(
                {
                    NEWER: _rows(
                        ("total_asset", MISSING_SCREENER, "600", None),
                        ("total_liability", ANOMALY, "400", "300"),
                    ),
                    OLDER: _rows(("operating_profit", MISMATCH, "100", "70")),
                }
            ),
            _company(
                {
                    NEWER: _rows(("net_profit", MISMATCH, "100", "68")),
                    OLDER: _rows(
                        ("operating_profit", MISMATCH, "100", "95"),
                        ("revenue", AGREE, "200", "200"),
                    ),
                },
                isin=OTHER_ISIN,
                symbol=OTHER_SYMBOL,
                anomalies=(_identity_note("operating_profit", OLDER, full="95"),),
            ),
        ),
        _config(
            module,
            acknowledged=(
                _acknowledgement(module, "net_profit", isin=OTHER_ISIN, symbol=OTHER_SYMBOL),
            ),
        ),
    )
    assert (triaged.warn_count, triaged.listed_count) == (3, 5)
    assert triaged.exit_code == 0
    assert set(module.WARN_CLASSES) == {
        module.TriageClass.STRUCTURAL,
        module.TriageClass.MAGNITUDE,
        module.TriageClass.WHOLE_TABLE,
    }
    assert set(module.LISTED_CLASSES) == set(module.WARN_CLASSES) | {
        module.TriageClass.UPSTOX_SIDE,
        module.TriageClass.ACKNOWLEDGED,
    }


def test_triage_leaves_the_comparison_it_read_exactly_as_it_found_it() -> None:
    """T14/C-06: the triage is an annotation, so re-running it can never drift.

    The report is the run's artifact and the comparison's outcomes are its
    evidence; a triage that could alter an outcome, a tolerance or a stated
    amount would make the queue and the evidence disagree with no way to tell
    which moved. Purity also makes the pass re-runnable over a stored report —
    the way a changed threshold will be evaluated against the sweep — and
    idempotence is what lets that happen without the second run reclassifying
    what the first one wrote.
    """
    module = _triage()
    config = _config(module, acknowledged=(_acknowledgement(module, "net_profit"),))
    original = _one(
        ("operating_profit", MISMATCH, "100", "70"), ("net_profit", MISMATCH, "100", "68")
    )
    before = original.model_dump()
    once = module.triage_run(original, config)
    twice = module.triage_run(once, config)

    assert original.model_dump() == before
    assert twice.model_dump() == once.model_dump()
    annotated = {"relative_difference", "triage"}
    for source, triaged in zip(original.companies, once.companies, strict=True):
        for was, now in zip(source.reports, triaged.reports, strict=True):
            for before_row, after_row in zip(was.rows, now.rows, strict=True):
                kept = after_row.model_dump()
                assert {
                    key: value for key, value in kept.items() if key not in annotated
                } == before_row.model_dump(exclude=annotated)


def test_the_triage_module_is_under_the_lane_b_scope_guards() -> None:
    """T17: a new Lane B module inherits the bar, or the bar is only historical.

    Nothing Upstox returns is a fact and no Lane B value may reach the fact store
    or the reconciler — Upstox shares upstream lineage with Screener, which is
    verified rather than assumed. The import scan enforcing that is driven by an
    explicit list because these files carry no ``upstox`` in their name, so a
    module absent from the list is a module outside the rail.
    """
    from tests.fundamentals.test_upstox_scope_guards import LANE_B_MODULES

    assert "verify/laneb_triage.py" in LANE_B_MODULES


def test_the_identity_note_is_parsed_by_the_module_that_writes_it() -> None:
    """T18/C-10: the convergence rule reads a string, so the format needs one owner.

    The note is produced by the statement reader and consumed by the triage. If
    the triage re-implemented the format, a change to the message would silently
    stop the exoneration rule from firing — the queue would fill with rows the
    vendor had already admitted were contradictory, and no test would fail. A
    parser living beside the format is the cheap way to make that a structural
    coupling instead of a textual one. Notes about the envelope or the response's
    shape carry no category or period and must parse to nothing, not to a guess.
    """
    from fundamentals.ingest.upstox_statements import parse_identity_note

    for category, particular in INCOME_SUMMARY_IDENTITIES:
        for period, summary, full in (
            ("Mar 2025", Decimal("153.0"), Decimal("153.97")),
            ("Jun 2026", Decimal("-4.5"), Decimal("-6.25")),
        ):
            note = _SUMMARY_DISAGREES.format(
                category=category,
                period=period,
                summary=summary,
                particular=particular,
                full=full,
            )
            parsed = parse_identity_note(note)
            assert parsed is not None, note
            assert (parsed.category, parsed.period) == (category, period)
            assert (parsed.summary, parsed.full) == (summary, full)

    for other in (
        FULL_STATEMENT_IS_ALWAYS_ANNUAL,
        "full_statement was null rather than a list; read as empty",
        "income_statement is not in the verified shape: field required",
    ):
        assert parse_identity_note(other) is None


def test_a_sweep_shaped_company_produces_a_queue_and_no_warning() -> None:
    """T20: on the live population's own shape, the triage must page nobody.

    This is the sweep in miniature: one acknowledged definitional line at 32%,
    one line the vendor's own response contradicts itself on, and one small
    tier-2 rounding difference. The real sweep produced no parser defect in 344
    lines, so a triage that warned on this shape would warn on a clean run and be
    switched off within a week. All three lines still reach the listed set —
    nothing is suppressed — and the breadth guard holds, since a section where
    every category disagrees but none is large must not fire.
    """
    module = _triage()
    triaged = module.triage_run(
        _one(
            ("revenue", ANOMALY, "200.50", "199.50"),
            ("operating_profit", MISMATCH, "100", "68"),
            ("net_profit", MISMATCH, "100", "99.50"),
            anomalies=(_identity_note("net_profit", NEWER, full="99.50"),),
        ),
        _config(module, acknowledged=(_acknowledgement(module, "operating_profit"),)),
    )
    classes = _classes(triaged)
    assert classes[(NEWER, "revenue")] is module.TriageClass.NOISE
    assert classes[(NEWER, "operating_profit")] is module.TriageClass.ACKNOWLEDGED
    assert classes[(NEWER, "net_profit")] is module.TriageClass.UPSTOX_SIDE
    assert (triaged.warn_count, triaged.listed_count) == (0, 2)
