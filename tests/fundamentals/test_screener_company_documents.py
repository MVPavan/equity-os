"""Slice 2 reading contract, part two: segments and the four page fragments.

Split from :mod:`test_screener_company` (which covers discovery, URL
construction, the Shareholding Pattern tables and the investor drill-downs) only
for size; both share the pinned transport seam in
:mod:`screener_company_support`, and every test here states WHY the behaviour
matters rather than what the output looks like.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import screener_company_support as support

from fundamentals.ingest.screener_company_models import (
    AssertionResult,
    Binding,
    CompanyPart,
    SegmentOutcome,
    Validation,
    ValidationStatus,
)
from fundamentals.ingest.screener_financials_models import Unit

BARE_PAGE = support.FIXTURES / "synthetic_screener_company_bare.html"


# --------------------------------------------------------------------------
# Segments
# --------------------------------------------------------------------------


def test_segment_periods_may_be_a_suffix_or_a_prefix_of_the_page_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which end of the page's header the fragment trims depends on the section.

    The quarters table shows one more quarter than its fragment, so the fragment
    is the *last* columns; the P&L table ends in a ``TTM`` column the fragment
    never carries, so there the fragment is the *first* columns. Requiring
    either end alone would refuse half the live captures, so the rule is a
    contiguous window.
    """
    run = support.run_only(monkeypatch)
    quarters = support.segments_table(run, "quarters")
    profit_loss = support.segments_table(run, "profit-loss")
    assert [period.label for period in quarters.periods] == [
        "Sep 2025",
        "Dec 2025",
        "Mar 2026",
    ]
    assert [period.label for period in profit_loss.periods] == [
        "Mar 2024",
        "Mar 2025",
        "Mar 2026",
    ]


def test_segment_periods_outside_the_page_window_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page header is the only thing binding these columns to real periods.

    A fragment whose labels are not a contiguous run of the page's own describes
    periods the page does not, so anchoring its figures to the page's columns
    would attach numbers to the wrong quarters.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".misaligned"))
    failure = next(found for found in run.artifact.failures if found.name == "quarters_1")
    assert failure.refusal == "PeriodAlignmentError"


def test_segment_sales_that_reconcile_are_the_only_sum_proven_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an actual match licenses a proof claim, elimination line included.

    ETERNAL publishes ``Less: Intersegment`` as a negative row and its segments
    sum exactly to the page's Sales row. That is the one shape where the sum is
    a proof rather than a description of a gap.
    """
    run = support.run_only(monkeypatch)
    quarters = support.segments_table(run, "quarters")
    assert quarters.outcome is SegmentOutcome.RECONCILED
    assert quarters.binding is Binding.CONFIGURED_URL_ONLY
    assert [comparison.difference for comparison in quarters.comparisons] == [Decimal(0)] * 3


def test_segments_above_the_page_row_are_bounded_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Screener omits eliminations for some companies, and that is not an error.

    TITAN's segment Sales exceed its page Sales row in every period of both
    tables because the table lists no elimination line. Refusing that would
    refuse correct consolidated data; calling it reconciled would claim the gap
    is explained. It is neither, so it is BOUNDED with the gap named.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".exceeds"))
    quarters = support.segments_table(run, "quarters")
    assert quarters.outcome is SegmentOutcome.EXCEEDS_PAGE
    assert quarters.validation_status is ValidationStatus.PASSED
    assert not run.artifact.failures
    assert all(comparison.difference > 0 for comparison in quarters.comparisons)


def test_segments_short_only_in_an_older_period_are_bounded_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Old periods fall short for honest reasons and refusing them refuses real data.

    HFCL's Mar 2016 segment Sales are 261 crore below its page row because it
    published four segment lines then and five now; ETERNAL is 17-23 short in two
    quarters where its elimination row deducts revenue the page does not. Both
    are correct consolidated bodies.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".historic_below"))
    quarters = support.segments_table(run, "quarters")
    assert quarters.outcome is SegmentOutcome.BELOW_PAGE
    assert quarters.validation_status is ValidationStatus.PASSED
    assert not run.artifact.failures


def test_segments_short_in_the_newest_period_are_refused_as_a_basis_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """That is the signature of a standalone body answering a consolidated request.

    The segments API selects basis by the query VALUE, so a wrong value returns
    a body that parses and aligns perfectly. TITAN's standalone segments run
    3,114 crore below its consolidated page in the newest quarter and below in
    every other, while no legitimate capture undershoots the newest period at
    all — which is what makes the newest period, and only it, a usable gate.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".below"))
    failure = next(found for found in run.artifact.failures if found.name == "quarters_1")
    assert failure.refusal == "SegmentReconciliationError"
    assert "consolidated=true" in failure.detail


def test_a_periodless_segments_shell_is_refused_rather_than_recorded_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page's own button is proof the company has segments.

    A header-only body is what a standalone-only company returns for
    ``?consolidated=true`` and what a wrong company id returns. Recording it as
    an empty table would publish "this company has no segments" on evidence that
    says nothing of the sort.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".shell"))
    failure = next(found for found in run.artifact.failures if found.name == "quarters_1")
    assert failure.refusal == "EmptyShellError"


def test_blank_growth_cells_are_published_readings_with_no_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare ``"%"`` is a rendering, and it is not the same as an unreported period.

    Screener renders ``%`` alone when a growth cell has nothing to compare
    against, and the empty string when a segment did not report at all.
    Collapsing the two would lose the distinction between "no prior period" and
    "no such segment then".
    """
    run = support.run_only(monkeypatch)
    quarters = support.segments_table(run, "quarters")
    growth = next(line for line in quarters.lines if line.line == "Sales Growth %")
    first = growth.rows[0].cells[0]
    assert first.raw_text == "%"
    assert first.published is True
    assert first.value is None


def test_a_segment_row_that_cannot_be_aligned_is_quarantined_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row that vanishes makes an incomplete artifact look complete.

    ETERNAL renders label-only rows for lines it has no figures for, so a row
    whose cell count does not match the header is a real shape the source uses.
    It is kept with its lexemes so drift is visible in the artifact.
    """
    run = support.run_only(monkeypatch)
    quarters = support.segments_table(run, "quarters")
    profit = next(line for line in quarters.lines if line.line == "Profit")
    assert [row.label for row in profit.quarantined] == ["Unallocated"]


def test_a_segment_lines_key_and_its_rendered_title_are_kept_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two lines render one heading, so the heading cannot address either.

    ``Profit`` and ``Profit Growth %`` both render "Profit before Tax & Int".
    The ``data-segment-line`` key is what addresses the block; the title is what
    a reader sees, and keeping only one of them loses either the address or the
    label.
    """
    run = support.run_only(monkeypatch)
    quarters = support.segments_table(run, "quarters")
    profit = next(line for line in quarters.lines if line.line == "Profit")
    assert profit.title == "Profit before Tax & Int"
    assert profit.table_id == "segments:quarters:Profit"


# --------------------------------------------------------------------------
# Related party, corporate actions
# --------------------------------------------------------------------------


def test_related_party_lines_are_addressed_by_position_not_by_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line labels repeat within one party with only a case difference.

    "Inter-corporate Deposit placed" and "Inter-corporate deposit placed" appear
    under one party in the live TITAN capture with different figures. A
    label-keyed map would silently collapse them into one row and lose a real
    transaction line.
    """
    run = support.run_only(monkeypatch)
    party = run.artifact.related_party
    assert party is not None
    labels = [line.label for line in party.parties[0].lines]
    assert labels == [
        "Inter-corporate Deposit placed",
        "Inter-corporate deposit placed",
        "Interest income",
    ]
    paths = {line.cells[0].provenance.row_path for line in party.parties[0].lines}
    assert len(paths) == 3


def test_related_party_tag_is_split_out_of_the_party_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The relationship tag renders inside the name cell and is not part of the name.

    Leaving "Parent Co." glued to the name would make the party unmatchable
    against any other source, and a party with no tag would then look like a
    different kind of entity than one with the same name and a tag.
    """
    run = support.run_only(monkeypatch)
    party = run.artifact.related_party
    assert party is not None
    assert party.parties[0].name == "Fixture Holdings Private Limited"
    assert party.parties[0].tag == "Parent Co."
    assert party.parties[1].name == "Fixture Logistics Ltd"
    assert party.parties[1].tag is None


def test_related_party_keeps_the_sources_own_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Screener flags this table experimental, and dropping that firms it up.

    The callout is the source's own statement about how far its numbers can be
    trusted. An artifact that keeps the numbers and loses the caveat presents
    them more confidently than the source does.
    """
    run = support.run_only(monkeypatch)
    party = run.artifact.related_party
    assert party is not None
    assert party.source_note is not None
    assert "Experimental new feature" in party.source_note
    assert party.binding is Binding.CONFIGURED_URL_ONLY


def test_an_empty_related_party_table_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The page linked the modal, so an empty one means the wrong URL was called.

    NETWEB's ``/results/rpt/<id>/consolidated/`` returns a header-only table and
    its page never links that path. Reaching it means a caller built the URL
    instead of taking the page's ``data-url``.
    """
    run = support.run_only(monkeypatch, swap=("related_party", ".empty"))
    failure = next(found for found in run.artifact.failures if found.name == "related_party")
    assert failure.refusal == "EmptyShellError"


def test_an_unfamiliar_corporate_action_tab_is_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tab sets vary per company, so an unknown tab is news rather than noise.

    TITAN renders equityhistory/dividend/bonus/split and NETWEB renders
    equityhistory/esops/prefissue/dividend. Dropping a tab this contract has not
    seen would silently discard a whole class of corporate events.
    """
    run = support.run_only(monkeypatch)
    actions = run.artifact.corporate_actions
    assert actions is not None
    assert [tab.tab for tab in actions.tabs] == ["dividend", "split", "mysterytab"]
    mystery = actions.tabs[-1]
    assert mystery.actions[0].title == "Something Screener Invented"


def test_a_dividend_amount_is_read_only_when_the_title_is_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A number pulled out of prose is a guess about what the number means.

    "₹ 15" is the dividend. "New face value: 1.00" is a face value and
    "EQUITY SHARES @ ₹4790" is an issue price; recording either as ``amount``
    would put three different quantities in one field.
    """
    run = support.run_only(monkeypatch)
    actions = run.artifact.corporate_actions
    assert actions is not None
    dividend = actions.tabs[0]
    assert [action.amount for action in dividend.actions] == [Decimal("15"), Decimal("2.50")]
    split = actions.tabs[1]
    assert split.actions[0].amount is None
    assert split.actions[0].title == "New face value: 1.00"


def test_corporate_action_dates_are_parsed_or_refused_never_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognised month is a change in how the site writes dates.

    Guessing would publish a confident wrong date on an event a reader would use
    to align a filing, so the month map is closed and anything outside it stops
    the document.
    """
    run = support.run_only(monkeypatch)
    actions = run.artifact.corporate_actions
    assert actions is not None
    assert actions.tabs[0].actions[0].event_date.isoformat() == "2026-07-09"

    refused = support.run_only(monkeypatch, swap=("corporate_actions", ".bad_date"))
    failure = next(
        found for found in refused.artifact.failures if found.name == "corporate_actions"
    )
    assert failure.refusal == "CorporateActionDateError"


# --------------------------------------------------------------------------
# Peers
# --------------------------------------------------------------------------


def test_the_peers_self_row_is_found_by_id_and_is_not_the_first_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HFCL and NETWEB sit third in their own peer lists.

    The list is ordered by market capitalisation, so the requesting company's
    position varies. Reading row one as "us" would assert another company's
    numbers are ours on two of the four live captures.
    """
    run = support.run_only(monkeypatch)
    peers = run.artifact.peers
    assert peers is not None
    assert peers.self_row_position == 3
    assert peers.rows[2].is_self is True
    assert peers.rows[0].is_self is False


def test_the_peers_fragment_proves_its_own_basis(monkeypatch: pytest.MonkeyPatch) -> None:
    """This is the only fragment whose body states which basis it carries.

    The peers API is scoped by the per-basis warehouse id and the self row's link
    ends in ``/consolidated/`` only on the consolidated one. That makes the
    fragment self-checking, so its class is PAGE_ASSERTED where the other
    fragments are URL_ONLY.
    """
    run = support.run_only(monkeypatch)
    peers = run.artifact.peers
    assert peers is not None
    assert peers.rows[2].href == "/company/FIXTURECO/consolidated/"
    assert peers.binding is Binding.BODY_ASSERTED
    assert peers.identity_assertion is AssertionResult.PASSED
    assert peers.peer_values_binding is Binding.CONFIGURED_URL_ONLY


def test_a_peers_self_row_on_the_wrong_basis_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A standalone peer list answering a consolidated request is silently wrong.

    Both bases return the same columns and nearly the same peers, differing only
    in figures — so nothing but the self row's own link catches a call made with
    the other basis's warehouse id.
    """
    run = support.run_only(monkeypatch, swap=("peers", ".wrong_basis"))
    failure = next(found for found in run.artifact.failures if found.name == "peers")
    assert failure.refusal == "PeerIdentityError"
    assert "consolidated" in failure.detail


def test_a_peers_fragment_that_does_not_name_this_company_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the self row the fragment is an anonymous table of other companies.

    Nothing else on it binds it to this issuer, so absence of the row removes
    the entire basis for filing it under this company.
    """
    run = support.run_only(monkeypatch, swap=("peers", ".missing"))
    failure = next(found for found in run.artifact.failures if found.name == "peers")
    assert failure.refusal == "PeerIdentityError"
    assert "0 rows" in failure.detail


def test_a_peers_fragment_naming_this_company_twice_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two self rows make "our" figures depend on which one is read first.

    The two rows need not agree, and the one read first is not necessarily the
    one a consumer would have chosen.
    """
    run = support.run_only(monkeypatch, swap=("peers", ".duplicate"))
    failure = next(found for found in run.artifact.failures if found.name == "peers")
    assert failure.refusal == "PeerIdentityError"
    assert "2 rows" in failure.detail


def test_peer_columns_keep_the_full_field_name_not_the_abbreviation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "ROCE %" is a header abbreviation; "Return on capital employed" is the field.

    The full name in ``data-tooltip`` is the identifier Screener's own query
    language uses, so it is what makes a peer column joinable to anything else.
    """
    run = support.run_only(monkeypatch)
    peers = run.artifact.peers
    assert peers is not None
    assert [column.field for column in peers.columns] == [
        "S.No.",
        "Name",
        "Current Price",
        "Return on capital employed",
    ]
    assert peers.columns[3].label == "ROCE %"


# --------------------------------------------------------------------------
# Quick ratios
# --------------------------------------------------------------------------


def test_quick_ratio_forms_keep_every_number_and_their_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "High / Low" renders two numbers in one value, and both are the reading.

    Splitting it into two ratios would invent names the site does not publish;
    keeping one would discard half. The rupee sign, the ``Cr.`` suffix and the
    ``%`` suffix are the only unit statements available, so they are read from
    the value's own text.
    """
    run = support.run_only(monkeypatch)
    api_list = next(entry for entry in run.artifact.quick_ratios if entry.configured_by_account)
    by_name = {ratio.name: ratio for ratio in api_list.ratios}
    assert by_name["Market Cap"].values == (Decimal("123456"),)
    assert by_name["Market Cap"].unit is Unit.RS_CRORE
    assert by_name["Current Price"].unit is Unit.RUPEES
    assert by_name["High / Low"].values == (Decimal("1590"), Decimal("910"))
    assert by_name["Dividend Payout"].unit is Unit.PERCENT
    assert by_name["Stock P/E"].unit is Unit.RATIO


def test_the_api_ratio_list_is_recorded_as_an_account_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which ratios the API returns is the owner's Manage-quick_ratios selection.

    That makes the list's membership a fact about this account rather than about
    the issuer, so a consumer must never read "Screener publishes these 51
    ratios for this company" out of it. The page's own ``#top-ratios`` block is
    the opposite: it is what every visitor sees.
    """
    run = support.run_only(monkeypatch)
    configured = [entry.configured_by_account for entry in run.artifact.quick_ratios]
    assert configured == [False, True]
    page_block, api_list = run.artifact.quick_ratios
    assert page_block.binding is Binding.PAGE_ASSERTED
    assert page_block.url is None
    assert api_list.binding is Binding.CONFIGURED_URL_ONLY


# --------------------------------------------------------------------------
# Evidence bookkeeping and the interrupted run
# --------------------------------------------------------------------------


def test_a_part_carries_no_verdict_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any single roll-up over a part either flatters the weakest or buries the strongest.

    The investors part holds two promoter documents held to equality and six
    threshold buckets that only have an upper bound. One class for the part
    would say every bucket is complete, or that none of them checked out —
    neither is true, so the part reports its documents and nothing else.
    """
    run = support.run_only(monkeypatch)
    documents = support.outcome(run, CompanyPart.INVESTORS).documents
    validations = {document.validation for document in documents}
    assert validations == {Validation.NONE, Validation.EQUALITY, Validation.UPPER_BOUND}
    assert not hasattr(support.outcome(run, CompanyPart.SEGMENTS), "evidence_class")


def test_a_passing_one_sided_check_does_not_make_a_document_proven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bound that holds is true of any subset, including the wrong company's.

    "No larger than the whole" and "the newest period does not undershoot" are
    both worth checking and neither identifies the response. The equality is the
    exception and is handled in :mod:`test_screener_company_hardening`: a sum
    that lands exactly on a figure the proven page states could not come from
    another issuer.
    """
    run = support.run_only(monkeypatch)
    metadata = run.artifact.metadata
    for document_id in (
        "/results/rpt/991001/consolidated/",
        "/api/3/991001/investors/public/quarterly/",
        "/api/segments/991001/quarters/1/?consolidated=true",
        "/api/company/992001/peers/",
    ):
        assert document_id in metadata.weak_documents
    assert "/api/3/991001/investors/promoters/quarterly/" in metadata.proven_documents
    assert set(metadata.documents_by_binding) == {
        "page_asserted",
        "body_asserted",
        "configured_url_only",
    }


def test_a_refusal_ends_its_own_part_and_not_the_rest_of_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """These parts are independent, unlike a company's fifteen schedule families.

    A schedules failure almost always means the whole run used the wrong basis,
    so Slice 1 stops. Here a peers fragment naming the wrong company says
    nothing about the corporate-actions modal, and abandoning the rest would
    discard documents that are perfectly good.
    """
    run = support.run_only(monkeypatch, swap=("peers", ".missing"))
    assert run.artifact.peers is None
    assert run.artifact.corporate_actions is not None
    assert run.artifact.related_party is not None
    assert len(run.artifact.quick_ratios) == 2
    assert run.artifact.metadata.all_admitted is False
    assert run.artifact.metadata.complete is True
    assert run.artifact.metadata.parts_refused == (CompanyPart.PEERS,)


def test_a_rate_limit_stops_the_sweep_and_keeps_what_was_already_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Screener rate-limits at ~40 requests, so a partial run is an expected outcome.

    Everything fetched before the 429 is still true and is retained with its
    bytes; what is missing is named in ``incomplete_reason`` rather than implied
    by a shorter list, so a partial artifact can never be mistaken for a company
    that publishes less.
    """
    run, requested = support.read(monkeypatch, rate_limit_after=3)
    metadata = run.artifact.metadata
    assert metadata.complete is False
    assert metadata.all_admitted is True
    assert metadata.incomplete_reason is not None
    assert "rate-limited" in metadata.incomplete_reason
    assert len(run.documents) == 3
    assert len(requested) == 5
    assert len(run.artifact.investors) == 3
    assert run.artifact.peers is None
