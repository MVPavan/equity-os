"""How one Screener company page and its schedules are read.

No test opens a socket. What these pin is the set of ways this source can hand
back a wrong number that looks right — a basis chosen by the presence of a query
key, a sub-row family that is analysis rather than components, a TTM column that
is not a date, a row that quietly stopped fitting its header, and a schedule
shape nobody has verified.

The transport seam and the synthetic bodies live in
:mod:`screener_financials_support`, shared with
:mod:`test_screener_financials_cli`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from screener_financials_support import (
    _family,
    _read,
    _row,
    _run,
    _section,
)

from fundamentals.ingest.screener_financials_models import (
    KNOWN_SCHEDULE_FAMILIES,
    IdentityStrength,
    PeriodKind,
    ReconciliationStatus,
    RowStatus,
    ScheduleStrategy,
    Section,
    Unit,
    schedule_path,
)
from fundamentals.ingest.screener_financials_shapes import MIXED_FAMILY_SHAPES
from fundamentals.ingest.screener_session_models import (
    Basis,
)

# --------------------------------------------------------------------------
# The basis trap: the schedules API reads the KEY, never its value.
# --------------------------------------------------------------------------


def test_consolidated_basis_is_selected_by_the_presence_of_the_key_not_its_value() -> None:
    """A caller who writes ``consolidated=false`` gets consolidated figures.

    Screener returns byte-identical consolidated bodies for ``consolidated=``,
    ``consolidated=true`` and ``consolidated=false``, and the standalone body
    only when the key is absent entirely. Encoding basis as a value anywhere in
    this repo would therefore silently acquire the wrong numbers, so the exact
    query string is pinned here rather than left to a URL builder's discretion.
    """
    consolidated = schedule_path(
        3437, parent="Other Income", section=Section.QUARTERS, basis=Basis.CONSOLIDATED
    )
    standalone = schedule_path(
        3437, parent="Other Income", section=Section.QUARTERS, basis=Basis.STANDALONE
    )
    assert consolidated == (
        "/api/company/3437/schedules/?parent=Other+Income&section=quarters&consolidated="
    )
    assert standalone == "/api/company/3437/schedules/?parent=Other+Income&section=quarters"
    assert "consolidated" not in standalone
    assert "false" not in consolidated and "true" not in consolidated


def test_the_page_and_its_schedules_are_requested_on_the_basis_that_was_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every request of one run must carry the same basis, or the artifact mixes two."""
    _, requested = _read(monkeypatch)
    schedules = [url for url in requested if "/schedules/" in url]
    assert schedules, "the fixture page offers schedule families"
    assert all(url.endswith("&consolidated=") for url in schedules)


# --------------------------------------------------------------------------
# Reading the page.
# --------------------------------------------------------------------------


def test_ttm_is_kept_as_a_typed_column_and_never_given_a_fabricated_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTM is a trailing-twelve-month aggregate, not a period the company reported.

    Screener stamps that header ``data-date-key="TTM"``. Coercing it to a date
    would invent a period end and let TTM be compared against, or joined to, a
    real quarter as if it were one.
    """
    run = _run(monkeypatch)
    periods = _section(run, Section.PROFIT_LOSS).periods
    ttm = periods[-1]
    assert ttm.label == "TTM"
    assert ttm.kind is PeriodKind.TTM
    assert ttm.period_end is None
    assert [period.kind for period in periods[:-1]] == [PeriodKind.DATE, PeriodKind.DATE]


def test_a_blank_cell_is_unpublished_while_a_reported_zero_is_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A period the company did not report must not read as a reported zero.

    Both render as a falsy value downstream; only ``published`` separates "no
    interest expense was disclosed" from "interest expense was nil".
    """
    interest = _row(run := _run(monkeypatch), Section.QUARTERS, "Interest")
    assert [cell.raw_text for cell in interest.cells] == ["-5", "0", ""]
    assert [cell.published for cell in interest.cells] == [True, True, False]
    assert interest.cells[1].value == Decimal("0")
    assert interest.cells[2].value is None
    assert run is not None


def test_a_negative_cell_reads_as_a_negative_decimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sign is data: an outflow read as its magnitude would flip a cash-flow total."""
    investing = _row(_run(monkeypatch), Section.CASH_FLOW, "Cash from Investing Activity")
    assert [cell.value for cell in investing.cells] == [Decimal("-300"), Decimal("-360")]


def test_a_percent_row_and_an_amount_row_carry_different_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A margin and a crore figure are not addable, so the unit must survive parsing."""
    run = _run(monkeypatch)
    assert _row(run, Section.QUARTERS, "OPM %").unit is Unit.PERCENT
    assert _row(run, Section.QUARTERS, "Sales").unit is Unit.RS_CRORE
    assert _row(run, Section.QUARTERS, "EPS in Rs").unit is Unit.RUPEES


def test_a_ratio_row_is_not_labelled_crores_by_its_sections_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ratios section carries the crores note but holds day counts.

    Applying the section's unit statement there would publish a confident wrong
    unit, so a ratios row that declares no unit of its own stays UNKNOWN.
    """
    run = _run(monkeypatch)
    assert _row(run, Section.RATIOS, "Debtor Days").unit is Unit.DAYS
    assert _row(run, Section.RATIOS, "ROCE %").unit is Unit.PERCENT
    assert _row(run, Section.RATIOS, "Cash Conversion Cycle").unit is Unit.UNKNOWN


def test_an_unknown_row_is_retained_with_its_values_rather_than_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new row on the page is drift to record, never a reason to fail or to lose data."""
    unknown = _row(_run(monkeypatch), Section.QUARTERS, "Segment Mix Index")
    assert unknown.status is RowStatus.UNMODELED
    assert [cell.value for cell in unknown.cells] == [
        Decimal("11"),
        Decimal("12"),
        Decimal("13"),
    ]


def test_a_row_that_no_longer_fits_the_header_is_quarantined_with_its_lexemes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropping an unalignable row would make a broken table look complete.

    A row whose cell count stopped matching the header cannot be anchored to
    periods, but its numbers still exist and are the evidence of what changed.
    """
    ratios = _section(_run(monkeypatch), Section.RATIOS)
    assert [row.label for row in ratios.quarantined] == ["Working Capital Days"]
    assert ratios.quarantined[0].raw_cells == ("52",)
    assert "1 cells" in ratios.quarantined[0].reason
    assert "Working Capital Days" not in [row.label for row in ratios.rows]


def test_a_data_table_outside_the_financial_sections_is_never_read_as_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The peer-comparison table carries other companies' numbers in the same markup.

    Selection is scoped to the section element, so a decoy outside every section
    cannot contribute a row no matter where it sits in the document.
    """
    run = _run(monkeypatch)
    labels = {row.label for table in run.artifact.sections for row in table.rows}
    assert "Decoy Peer Ltd" not in labels


def test_the_raw_pdf_row_retains_its_hrefs_and_nothing_follows_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Those links redirect off-site to BSE; they are evidence, not a fetch plan."""
    run, requested = _read(monkeypatch)
    raw_pdf = _row(run, Section.QUARTERS, "Raw PDF")
    assert raw_pdf.unit is Unit.DOCUMENT_LINK
    assert [link.href for link in raw_pdf.links] == [
        "/company/source/quarter/991001/6/2025/",
        "/company/source/quarter/991001/9/2025/",
        "/company/source/quarter/991001/12/2025/",
    ]
    assert not any("/company/source/" in url for url in requested)


def test_the_growth_ranges_tables_are_read_as_their_own_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """They live inside #profit-loss but have windows, not period columns.

    Folding them into the P&L table would mean inventing columns for them.
    """
    growth = _section(_run(monkeypatch), Section.GROWTH)
    assert [table.title for table in growth.growth_tables] == [
        "Compounded Sales Growth",
        "Compounded Profit Growth",
        "Stock Price CAGR",
        "Return on Equity",
    ]
    first = growth.growth_tables[0]
    assert [row.window for row in first.rows] == ["10 Years", "5 Years", "3 Years", "TTM"]
    assert first.rows[0].value == Decimal("23")
    assert first.rows[0].unit is Unit.PERCENT
    assert not _section(_run(monkeypatch), Section.PROFIT_LOSS).growth_tables


def test_the_schedule_families_come_from_the_pages_own_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hardcoded family list goes stale silently; the page's buttons cannot.

    ``showSchedule``'s first argument is the exact ``parent=`` the API expects,
    which is why it is read from the call rather than rebuilt from the label.
    """
    run = _run(monkeypatch)
    fetched = set(run.artifact.metadata.schedule_families_fetched)
    assert fetched == {
        "quarters/Sales",
        "quarters/Expenses",
        "quarters/Other Income",
        "quarters/Net Profit",
        "profit-loss/Sales",
        "balance-sheet/Borrowings",
        "balance-sheet/Other Liabilities",
        "balance-sheet/Fixed Assets",
        "cash-flow/Cash from Investing Activity",
    }
    assert fetched <= {f"{section.value}/{parent}" for section, parent in KNOWN_SCHEDULE_FAMILIES}


def test_the_known_family_list_records_the_fifteen_families_seen_live() -> None:
    """A drift signal, not a gate: the runtime list always comes off the page."""
    assert len(KNOWN_SCHEDULE_FAMILIES) == 15
    assert len({family for family in KNOWN_SCHEDULE_FAMILIES}) == 15


# --------------------------------------------------------------------------
# Classifying and reconciling the schedules.
# --------------------------------------------------------------------------


def test_a_family_of_percent_rows_is_analytical_and_never_summed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Sales +`` expands to a growth rate, not to the components of sales.

    Summing rates would produce a number with no meaning that a reconciliation
    gate would then reject as if the data were wrong.
    """
    family = _family(_run(monkeypatch), Section.QUARTERS, "Sales")
    assert family.strategy is ScheduleStrategy.ALL_PERCENT
    assert family.reconciliation is ReconciliationStatus.NOT_APPLICABLE
    assert family.comparisons == ()
    assert "YOY Sales Growth %" in family.reconciliation_note


def test_a_hierarchical_family_is_proven_against_its_page_row_not_exempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Net Fixed Assets is ``Gross Block`` less ``Accumulated Depreciation``.

    The relation is arithmetic, so it is checked rather than waved through:
    verified against all three live captures (worst gap 1 crore on TITAN and
    HFCL, 0.41 on NETWEB — inside the two-addend band) before being enforced.
    An exemption that can be turned into a proof should be.
    """
    family = _family(_run(monkeypatch), Section.BALANCE_SHEET, "Fixed Assets")
    assert family.strategy is ScheduleStrategy.HIERARCHICAL
    assert family.reconciliation is ReconciliationStatus.RECONCILED
    assert [comparison.sub_row_total for comparison in family.comparisons] == [
        Decimal("600"),
        Decimal("700"),
    ]
    assert all(comparison.difference == 0 for comparison in family.comparisons)


def test_a_registered_family_must_carry_every_row_that_identifies_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Being a subset of ``allowed`` says a row is familiar, not that the shape is.

    ``{"Land": 999}`` is a perfectly valid subset of Fixed Assets' allowed set,
    so subset-only checking inherited the exemption and reported not_applicable
    with exit 0 — while the body carried 999 against a page showing 600. The
    required rows are what make the body *this* family.
    """
    run = _run(monkeypatch, swap=("balance-sheet__fixed-assets", ".allowed-subset-only"))
    family = _family(run, Section.BALANCE_SHEET, "Fixed Assets")
    assert family.strategy is ScheduleStrategy.UNVERIFIED
    assert family.reconciliation is ReconciliationStatus.UNVERIFIED
    assert family.reconciliation is not ReconciliationStatus.NOT_APPLICABLE
    assert "Gross Block" in family.reconciliation_note
    assert "Accumulated Depreciation" in family.reconciliation_note


def test_a_registered_family_missing_one_required_row_is_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hierarchy cannot be checked without both operands, so it is not exempt either."""
    run = _run(monkeypatch, swap=("balance-sheet__fixed-assets", ".missing-required"))
    family = _family(run, Section.BALANCE_SHEET, "Fixed Assets")
    assert family.strategy is ScheduleStrategy.UNVERIFIED
    assert "Accumulated Depreciation" in family.reconciliation_note


def test_a_registered_family_admits_a_strict_subset_of_its_allowed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Companies carry different optional rows, so ``allowed`` must not demand equality.

    NETWEB's quarterly Net Profit has four sub-rows where TITAN's has six.
    Requiring the full allowed set would refuse every company but the one the
    capture came from; the required rows are what carry the guard instead.
    """
    family = _family(_run(monkeypatch), Section.QUARTERS, "Net Profit")
    shape = MIXED_FAMILY_SHAPES[(Section.QUARTERS, "Net Profit")]
    observed = {(row.label, row.kind) for row in family.sub_rows}
    assert observed < shape.allowed
    assert shape.required <= observed
    assert family.strategy is ScheduleStrategy.KNOWN_MIXED
    assert family.reconciliation is ReconciliationStatus.NOT_APPLICABLE


def test_a_flat_amount_family_is_summed_and_reconciled_against_the_page_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This is the gate the basis trap has to get past, so it must actually run."""
    family = _family(_run(monkeypatch), Section.BALANCE_SHEET, "Borrowings")
    assert family.strategy is ScheduleStrategy.FLAT_SUM
    assert family.reconciliation is ReconciliationStatus.RECONCILED
    assert [comparison.period_label for comparison in family.comparisons] == [
        "Mar 2025",
        "Mar 2026",
    ]
    assert [comparison.sub_row_total for comparison in family.comparisons] == [
        Decimal("1000"),
        Decimal("1200"),
    ]
    assert all(comparison.difference == 0 for comparison in family.comparisons)


def test_independent_rounding_of_whole_crores_is_not_treated_as_a_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Screener rounds the page row and each sub-row separately, so exact equality fails.

    Two addends and a total each rounded to whole crores can differ by up to
    1.5; the tolerance is that arithmetic, not a fudge factor, and it is orders
    of magnitude tighter than the basis error it has to catch.
    """
    family = _family(_run(monkeypatch), Section.QUARTERS, "Other Income")
    assert family.reconciliation is ReconciliationStatus.RECONCILED
    differences = [comparison.difference for comparison in family.comparisons]
    assert differences == [Decimal("1"), Decimal("0"), Decimal("1")]
    assert all(comparison.tolerance == Decimal("1.5") for comparison in family.comparisons)


def test_a_body_of_the_wrong_basis_is_refused_by_the_reconciliation_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of the gate.

    A standalone body served against a consolidated page parses perfectly and
    aligns to every period label; only the sum betrays it. The refusal names the
    query-key rule because that is the mistake that produces this body.
    """
    run = _run(monkeypatch, swap=("balance-sheet__borrowings", ".wrong-basis"))
    failure = next(item for item in run.artifact.failures if item.parent == "Borrowings")
    assert failure.refusal == "ScheduleReconciliationError"
    assert "presence of the 'consolidated' key" in failure.detail
    assert "Mar 2025" in failure.detail
    assert run.artifact.metadata.verified is False


def test_an_empty_response_is_unverified_rather_than_benign(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty HTTP 200 proves nothing, so it cannot be recorded as a clean result.

    None of the fifteen live families is ever empty, and an empty body carries
    no session, issuer or basis marker — it is byte-indistinguishable from what
    an expired cookie or a soft block would produce. Treating it as "this
    company publishes no breakdown" would launder a failed request into a fact.
    This stays until an empty response is captured live with positive proof.
    """
    run = _run(monkeypatch, swap=("profit-loss__sales", ".empty"))
    family = _family(run, Section.PROFIT_LOSS, "Sales")
    assert family.sub_rows == ()
    assert family.reconciliation is ReconciliationStatus.UNVERIFIED_EMPTY
    assert run.artifact.metadata.verified is False


def test_a_period_the_page_header_does_not_carry_blocks_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial alignment cannot prove the response describes the page's periods.

    The reading is retained by name, but reconciling on the columns that happen
    to match would let a body covering a different span of periods pass by
    agreeing on the overlap alone.
    """
    run = _run(monkeypatch, swap=("balance-sheet__borrowings", ".unaligned"))
    family = _family(run, Section.BALANCE_SHEET, "Borrowings")
    assert family.unaligned_periods == ("Mar 2019",)
    assert family.reconciliation is ReconciliationStatus.UNVERIFIED
    assert family.comparisons == ()


def test_page_cells_and_schedule_cells_carry_different_anchors_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A schedule body asserts no identity at all, so it must not borrow the page's.

    The page proves whose company it is; a schedules response is a bare
    label-to-value map whose only binding is the URL that was requested.
    Recording both as equally strong evidence would erase that difference.
    """
    run = _run(monkeypatch)
    page_cell = _row(run, Section.BALANCE_SHEET, "Borrowings").cells[0]
    assert page_cell.provenance.anchor_type.value == "HTML_TABLE"
    assert page_cell.provenance.table_id == "balance-sheet:data-table"
    assert page_cell.provenance.column_label == "Mar 2025"
    assert page_cell.provenance.column_index == 0
    assert "Borrowings" in (page_cell.provenance.row_path or "")
    assert _section(run, Section.BALANCE_SHEET).identity_strength is IdentityStrength.PAGE_ASSERTED

    family = _family(run, Section.BALANCE_SHEET, "Borrowings")
    schedule_cell = family.sub_rows[0].cells[0]
    assert schedule_cell.provenance.anchor_type.value == "API_DOCUMENT"
    assert schedule_cell.provenance.document_id == family.document_id
    assert schedule_cell.provenance.context_ref == "Mar 2025"
    assert schedule_cell.provenance.row_label == "Long term Borrowings"
    assert family.identity_strength is IdentityStrength.CONFIGURED_URL_ONLY
