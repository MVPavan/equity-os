"""Lane B comparator: the name map, the evidence tiers, and what may be claimed.

Lane B exists to detect Screener *scraping* error, not to adjudicate truth. The
independence test proved these Upstox endpoints share upstream lineage with
Screener, which disqualifies them as a third opinion and is exactly what makes
them usable as a differential check. Nothing here votes, and nothing here
becomes a fact.

The first test in this file is the red proof the bead demands, and it is the
reason the whole module exists: Upstox's ``operating_profit`` is **not**
Screener's operating profit. It is Screener's *profit before tax*. A comparator
built on matching names would report a false mismatch on every company, every
quarter, and would read as a catastrophic parser defect that is not there.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from fundamentals.ingest.screener_crosscheck import (
    INCOME_STATEMENT_MAP,
    CrosscheckOutcome,
    EvidenceTier,
    StatedValue,
    compare_line,
    mapping_for,
)

# Real figures from the 2026-09-03 independence probe, quoted in
# docs/research/upstox-integration-plan.md section 1 and section 6.9. They are
# load-bearing: the whole tier scheme was chosen because of them, and synthetic
# numbers would make every assertion below vacuous.
_TITAN_SEP25_SCREENER_OPERATING_PROFIT = Decimal("1875")
_TITAN_SEP25_SCREENER_PBT = Decimal("1522")
_TITAN_SEP25_UPSTOX_OPERATING_PROFIT = Decimal("1522.0")


def _screener(amount: str, label: str) -> StatedValue:
    """One Screener cell: integer crore as the page displays it."""
    return StatedValue(amount=Decimal(amount), decimals=0, raw_label=label)


def _upstox(amount: str, label: str) -> StatedValue:
    """One Upstox value: crore carrying two decimal places."""
    return StatedValue(amount=Decimal(amount), decimals=2, raw_label=label)


# --- the red proof ----------------------------------------------------------


def test_operating_profit_maps_to_screener_profit_before_tax() -> None:
    """The mapping is a declaration, and it contradicts the vendor's own label."""
    mapping = mapping_for("operating_profit")
    assert mapping.screener_rows == ("Profit before tax",)
    assert "before tax" in mapping.means.lower()


def test_a_naive_same_name_mapping_would_report_a_false_mismatch() -> None:
    """Why the map exists, demonstrated rather than asserted.

    TITAN Sep-2025: Screener's operating profit is 1,875 and its profit before
    tax is 1,522. Upstox's ``operating_profit`` is 1522.0. Compared against the
    same-named Screener row it is out by 353 crore — a screaming false positive.
    Compared against the row it actually means, it is exact.
    """
    mapping = mapping_for("operating_profit")
    upstox = _upstox(str(_TITAN_SEP25_UPSTOX_OPERATING_PROFIT), "operating_profit")

    correct = compare_line(
        mapping,
        upstox=upstox,
        screener=(_screener(str(_TITAN_SEP25_SCREENER_PBT), "Profit before tax"),),
    )
    assert correct.outcome is CrosscheckOutcome.AGREE

    naive = compare_line(
        mapping,
        upstox=upstox,
        screener=(_screener(str(_TITAN_SEP25_SCREENER_OPERATING_PROFIT), "Operating Profit"),),
    )
    assert naive.outcome is CrosscheckOutcome.MISMATCH
    assert naive.difference == Decimal("353.0")


def test_the_report_retains_the_raw_vendor_label_beside_the_mapped_one() -> None:
    """Mapping drift must be visible in the report, never absorbed by it."""
    row = compare_line(
        mapping_for("operating_profit"),
        upstox=_upstox("1522.0", "operating_profit"),
        screener=(_screener("1522", "Profit before tax"),),
    )
    assert row.upstox_raw_label == "operating_profit"
    assert row.screener_raw_labels == ("Profit before tax",)


# --- tier 1: equivalence demonstrated ---------------------------------------


def test_a_decimal_against_an_integer_agrees_inside_the_derived_half_ulp() -> None:
    """HFCL Jun-2026: Screener displays 332, Upstox returns 331.52. That is rounding.

    Under the *exact* equality this decision originally chose, every company
    whose figures are not whole crore would report ~100% mismatch. The tolerance
    is derived from each side's declared precision, not guessed.
    """
    row = compare_line(
        mapping_for("operating_profit"),
        upstox=_upstox("331.52", "operating_profit"),
        screener=(_screener("332", "Profit before tax"),),
    )
    assert row.outcome is CrosscheckOutcome.AGREE
    assert row.tolerance == Decimal("0.505")


@pytest.mark.parametrize(
    ("screener_value", "upstox_value"),
    [("106", "106.34"), ("95", "94.82"), ("332", "331.52"), ("228", "227.93")],
)
def test_every_recorded_rounding_gap_from_the_probe_agrees(
    screener_value: str, upstox_value: str
) -> None:
    """The four real gaps the probe recorded must not be reported as defects."""
    row = compare_line(
        mapping_for("operating_profit"),
        upstox=_upstox(upstox_value, "operating_profit"),
        screener=(_screener(screener_value, "Profit before tax"),),
    )
    assert row.outcome is CrosscheckOutcome.AGREE


def test_a_tier_one_difference_beyond_the_tolerance_is_a_mismatch() -> None:
    """Tier 1 is the only tier permitted to say MISMATCH, because equivalence is shown."""
    row = compare_line(
        mapping_for("net_profit"),
        upstox=_upstox("1600.00", "net_profit"),
        screener=(_screener("1777", "Net Profit"),),
    )
    assert row.tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
    assert row.outcome is CrosscheckOutcome.MISMATCH


# --- tier 2: related, not equivalent ----------------------------------------


def test_revenue_sums_two_screener_rows_and_widens_the_interval_accordingly() -> None:
    """Upstox ``revenue`` is Total Revenue; Screener shows Sales and Other Income apart.

    Each rounded addend contributes its own half-ULP, which is how rounding
    error propagates through addition. Two integer addends give ±1.0, not ±0.5.
    """
    row = compare_line(
        mapping_for("revenue"),
        upstox=_upstox("18837.00", "revenue"),
        screener=(_screener("18000", "Sales"), _screener("838", "Other Income")),
    )
    assert row.tier is EvidenceTier.RELATED_NOT_EQUIVALENT
    assert row.tolerance == Decimal("1.005")
    assert row.outcome is CrosscheckOutcome.AGREE


def test_the_recorded_revenue_gap_is_an_anomaly_and_never_a_mismatch() -> None:
    """TITAN Dec-2025: Screener 25,415 against Upstox 25,567 — 152 crore apart.

    Far outside any rounding interval, so it is real. But the revenue mapping is
    *approximate*: Sales + Other Income is a reconstruction of Total Revenue, not
    a demonstrated identity. Calling this a MISMATCH would claim more than the
    evidence supports.
    """
    row = compare_line(
        mapping_for("revenue"),
        upstox=_upstox("25567.00", "revenue"),
        screener=(_screener("25000", "Sales"), _screener("415", "Other Income")),
    )
    assert row.difference == Decimal("152.00")
    assert row.outcome is CrosscheckOutcome.ANOMALY


def test_no_tier_two_line_can_ever_report_a_mismatch() -> None:
    """The tier constrains the claim, whatever the size of the gap."""
    row = compare_line(
        mapping_for("revenue"),
        upstox=_upstox("1.00", "revenue"),
        screener=(_screener("99999", "Sales"), _screener("1", "Other Income")),
    )
    assert row.outcome is not CrosscheckOutcome.MISMATCH


# --- tier 3: equivalence unproven -------------------------------------------


def test_an_unproven_line_is_not_comparable_even_when_the_values_match() -> None:
    """Tier 3 makes no claim in either direction.

    Cash-flow lineage was never tested, ratios are derived and
    formula-dependent, and shareholding buckets may be defined differently.
    Counting a tier-3 agreement as evidence of correctness would be the same
    error as counting a tier-3 difference as evidence of a defect.
    """
    mapping = mapping_for("operating")
    row = compare_line(
        mapping,
        upstox=_upstox("500.00", "operating"),
        screener=(_screener("500", "Cash from Operating Activity"),),
    )
    assert row.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert row.outcome is CrosscheckOutcome.NOT_COMPARABLE
    assert row.values_equal is True


def test_an_unproven_line_records_the_difference_without_adjudicating_it() -> None:
    """Recorded and compared, never adjudicated — so the number is still kept."""
    row = compare_line(
        mapping_for("operating"),
        upstox=_upstox("300.00", "operating"),
        screener=(_screener("500", "Cash from Operating Activity"),),
    )
    assert row.outcome is CrosscheckOutcome.NOT_COMPARABLE
    assert row.difference == Decimal("200.00")
    assert row.values_equal is False


# --- missing sides ----------------------------------------------------------


def test_a_line_absent_from_screener_is_recorded_as_missing_not_as_a_difference() -> None:
    """An uncovered cell is a coverage gap; scoring it as agreement would be a lie."""
    row = compare_line(
        mapping_for("net_profit"), upstox=_upstox("1777.00", "net_profit"), screener=()
    )
    assert row.outcome is CrosscheckOutcome.MISSING_SCREENER
    assert row.difference is None


def test_a_line_absent_from_upstox_is_recorded_as_missing() -> None:
    """Upstox exposes a rolling four-period window; older periods simply are not there."""
    row = compare_line(
        mapping_for("net_profit"),
        upstox=None,
        screener=(_screener("1777", "Net Profit"),),
    )
    assert row.outcome is CrosscheckOutcome.MISSING_UPSTOX


def test_a_partially_covered_sum_is_missing_rather_than_silently_short() -> None:
    """Summing one of two addends would manufacture a 100% mismatch out of a gap."""
    row = compare_line(
        mapping_for("revenue"),
        upstox=_upstox("18837.00", "revenue"),
        screener=(_screener("18000", "Sales"),),
    )
    assert row.outcome is CrosscheckOutcome.MISSING_SCREENER


# --- the bar ----------------------------------------------------------------


def test_the_map_is_frozen_and_every_entry_declares_a_tier() -> None:
    """No line may be compared without first saying how much its comparison proves."""
    assert isinstance(INCOME_STATEMENT_MAP, tuple)
    assert all(entry.tier in EvidenceTier for entry in INCOME_STATEMENT_MAP)
    assert len({entry.upstox_category for entry in INCOME_STATEMENT_MAP}) == len(
        INCOME_STATEMENT_MAP
    )


def test_an_unmapped_vendor_category_is_refused_rather_than_guessed() -> None:
    """A category with no declared meaning has no comparison anyone can defend."""
    with pytest.raises(LookupError):
        mapping_for("ebitda")


def test_no_outcome_can_block_a_run() -> None:
    """Decision A is log-only: a difference is recorded, and nothing downstream moves.

    The base disagreement rate is unmeasured. Blocking on an unknown rate either
    halts the pipeline or gets switched off within a day.
    """
    from fundamentals.ingest.screener_crosscheck import CrosscheckReport

    report = CrosscheckReport(
        isin="INE999Z01012",
        basis="consolidated",
        period="Dec 2025",
        rows=(
            compare_line(
                mapping_for("net_profit"),
                upstox=_upstox("1.00", "net_profit"),
                screener=(_screener("99999", "Net Profit"),),
            ),
        ),
    )
    assert report.exit_code == 0
    assert report.mismatch_count == 1


class TestMapKeysMatchTheLiveContract:
    """Every mapped key must be a category name Upstox actually sends.

    Five of the eight were written from the vendor's documentation and none of
    them existed on the wire. A mapping keyed on a name that never arrives does
    not fail loudly — it raises `UnmappedCategoryError` on the first real
    payload, which reads as a comparator defect rather than as stale mapping.
    """

    def test_the_income_summary_categories_are_the_three_upstox_sends(self) -> None:
        keys = {entry.upstox_category for entry in INCOME_STATEMENT_MAP}
        assert {"revenue", "operating_profit", "net_profit"} <= keys

    def test_the_balance_sheet_keys_are_singular_as_the_wire_states_them(self) -> None:
        keys = {entry.upstox_category for entry in INCOME_STATEMENT_MAP}
        assert {"total_asset", "total_liability"} <= keys
        assert not {"total_assets", "total_liabilities"} & keys

    def test_the_cash_flow_keys_are_the_bare_category_words(self) -> None:
        keys = {entry.upstox_category for entry in INCOME_STATEMENT_MAP}
        assert {"operating", "investing", "financing"} <= keys
        assert not {k for k in keys if k.startswith("cash_flow_")}

    def test_every_mapped_key_is_reachable(self) -> None:
        for entry in INCOME_STATEMENT_MAP:
            assert mapping_for(entry.upstox_category) is entry


class TestTotalLiabilityIsNotScreenersTotalLiabilities:
    """Screener's `Total Liabilities` row is the balancing total, not liabilities.

    On every period of every company checked it equals Screener's `Total
    Assets`. Mapping Upstox's `total_liability` onto that name — which is what a
    same-name comparator does — produced a five-figure false ANOMALY on all four
    TITAN periods while the underlying numbers agreed to the crore.
    """

    def test_it_maps_to_the_two_rows_that_actually_sum_to_it(self) -> None:
        mapping = mapping_for("total_liability")
        assert mapping.screener_rows == ("Borrowings", "Other Liabilities")
        assert "NOT" in mapping.means

    def test_the_reconstruction_agrees_on_live_titan_mar_2026(self) -> None:
        """Upstox 44858.0 against Screener's 30621 + 14237. Exact."""
        row = compare_line(
            mapping_for("total_liability"),
            upstox=StatedValue(amount=Decimal("44858.0"), decimals=1, raw_label="total_liability"),
            screener=(
                StatedValue(amount=Decimal("30621"), decimals=0, raw_label="Borrowings"),
                StatedValue(amount=Decimal("14237"), decimals=0, raw_label="Other Liabilities"),
            ),
        )
        assert row.outcome is CrosscheckOutcome.AGREE
        assert row.difference == Decimal("0.0")

    def test_screeners_own_total_liabilities_row_would_have_been_nonsense(self) -> None:
        """The row it used to map to carries 60561 for the same period."""
        row = compare_line(
            mapping_for("total_liability"),
            upstox=StatedValue(amount=Decimal("44858.0"), decimals=1, raw_label="total_liability"),
            screener=(
                StatedValue(amount=Decimal("60561"), decimals=0, raw_label="Total Liabilities"),
            ),
        )
        # One row supplied where the mapping names two: scored as a coverage gap
        # rather than as a difference, which is what stops a partial sum
        # manufacturing a mismatch.
        assert row.outcome is CrosscheckOutcome.MISSING_SCREENER
