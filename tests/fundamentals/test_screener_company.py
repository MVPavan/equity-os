"""Slice 2 reading contract: what each sub-document proves, and what it refuses.

Every test below states WHY the behaviour matters, because most of them encode a
way this source is known to mislead rather than a preference about output shape.
No test opens a socket; the transport seam is pinned in
:mod:`screener_company_support`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import screener_company_support as support

from fundamentals.ingest.screener_company_discovery import (
    investor_hooks,
    modal_url,
    segment_hooks,
)
from fundamentals.ingest.screener_company_models import (
    Binding,
    BucketOutcome,
    CompanyPart,
    DiscoveryAmbiguousError,
    Periodicity,
    SumStrategy,
    Validation,
    ValidationStatus,
    investors_path,
    segments_path,
)
from fundamentals.ingest.screener_financials_models import (
    Basis,
    PeriodKind,
    Unit,
    schedule_path,
)
from fundamentals.ingest.screener_financials_models import Section as FinancialSection
from fundamentals.ingest.screener_session_page import parse_document
from fundamentals.ingest.screener_shareholding import read_shareholding_table

BARE_PAGE = support.FIXTURES / "synthetic_screener_company_bare.html"


# --------------------------------------------------------------------------
# Discovery: the page decides what exists
# --------------------------------------------------------------------------


def test_investor_buckets_come_from_the_pages_own_buttons() -> None:
    """The API bucket key is not the rendered label, so it must be read, not derived.

    Screener renders "FIIs" and answers to ``foreign_institutions``. Building an
    endpoint from the visible label would request a bucket that does not exist,
    and bucket sets vary per company (NETWEB has no government row, ETERNAL no
    promoters row), so a hard-coded list would go stale silently.
    """
    hooks = investor_hooks(support.page_root())
    assert [(hook.bucket, hook.periodicity.value) for hook in hooks] == [
        ("promoters", "quarterly"),
        ("foreign_institutions", "quarterly"),
        ("government", "quarterly"),
        ("public", "quarterly"),
        ("promoters", "yearly"),
        ("foreign_institutions", "yearly"),
        ("government", "yearly"),
        ("public", "yearly"),
    ]
    assert hooks[1].row_label == "FIIs"


def test_related_party_url_is_taken_verbatim_from_the_page() -> None:
    """The page decides whether the modal path carries the ``consolidated/`` suffix.

    A consolidated page links ``/results/rpt/<id>/consolidated/`` and a
    standalone one links ``/results/rpt/<id>/``. Rebuilding that path here would
    mean re-deciding a basis rule the proven page has already decided, on a
    fragment that carries no basis marker to catch the mistake.
    """
    assert (
        modal_url(support.page_root(), "profit-loss", "/results/rpt/")
        == "/results/rpt/991001/consolidated/"
    )


def test_two_conflicting_segment_hooks_are_refused() -> None:
    """Which segments table is "the" one must not depend on document order.

    Two ``showSegment`` calls naming one section with different types would make
    the request a coin flip between two different documents, and nothing on
    either says they describe the same thing.
    """
    html = support.PAGE.read_text(encoding="utf-8").replace(
        "Segment.showSegment('quarters', '1')",
        "Segment.showSegment('quarters', '1')\" type=\"button\">A</button>"
        "<button onclick=\"Segment.showSegment('quarters', '2')",
        1,
    )
    with pytest.raises(DiscoveryAmbiguousError, match="segments"):
        segment_hooks(parse_document(html))


def test_a_page_without_controls_offers_nothing_and_costs_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent control is positive proof of absence, not a reason to probe.

    NETWEB genuinely publishes no Product Segments. Requesting the endpoint
    anyway would spend a rate-limited request to learn from a shell response
    what the page already said, and a shell response is indistinguishable from a
    wrong-id one.
    """
    run, requested = support.read(monkeypatch, page=BARE_PAGE)
    absent = {outcome.part for outcome in run.artifact.outcomes if not outcome.offered}
    assert absent == {
        CompanyPart.INVESTORS,
        CompanyPart.SEGMENTS,
        CompanyPart.RELATED_PARTY,
        CompanyPart.CORPORATE_ACTIONS,
    }
    assert not any("/api/segments/" in url for url in requested)
    assert not any("/investors/" in url for url in requested)


# --------------------------------------------------------------------------
# URL construction
# --------------------------------------------------------------------------


def test_segments_selects_basis_by_value_where_schedules_selects_by_key_presence() -> None:
    """The two Screener APIs invert each other, and confusing them is silent.

    The schedules API reads only whether ``consolidated`` is present; the
    segments API reads only whether its value is ``true``. So a caller who
    disables consolidation by sending ``consolidated=false`` gets consolidated
    schedules and standalone segments — both parse, both align, both are wrong.
    Asserting them side by side is what keeps one rule from being copied onto
    the other.
    """
    consolidated = segments_path(
        991001, section="quarters", segment_type="1", basis=Basis.CONSOLIDATED
    )
    standalone = segments_path(991001, section="quarters", segment_type="1", basis=Basis.STANDALONE)
    assert consolidated == "/api/segments/991001/quarters/1/?consolidated=true"
    assert standalone == "/api/segments/991001/quarters/1/"

    schedules_consolidated = schedule_path(
        991001, parent="Sales", section=FinancialSection.QUARTERS, basis=Basis.CONSOLIDATED
    )
    schedules_standalone = schedule_path(
        991001, parent="Sales", section=FinancialSection.QUARTERS, basis=Basis.STANDALONE
    )
    assert schedules_consolidated.endswith("&consolidated=")
    assert "consolidated" not in schedules_standalone


def test_investors_url_is_basis_free_because_the_endpoint_is() -> None:
    """Shareholding is not basis-scoped, so inventing a basis query would be a lie.

    A holding in the parent company is the same holding whichever set of figures
    the page shows, and this endpoint takes the company id rather than the
    per-basis warehouse id. Both bases therefore build the identical URL.
    """
    for basis in Basis:
        assert (
            investors_path(991001, bucket="promoters", periodicity=Periodicity.QUARTERLY)
            == "/api/3/991001/investors/promoters/quarterly/"
        ), basis


def test_peers_and_quick_ratios_use_the_warehouse_id_not_the_company_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Screener runs two numeric namespaces through one path template.

    ``/api/company/<id>/peers/`` takes the basis-scoped warehouse id while
    ``/api/company/<id>/schedules/`` takes the company id. Passing the wrong one
    returns another company's page-shaped answer, which is why the id is read
    from ``#company-info`` rather than from the watchlist entry's company id.
    """
    _, requested = support.read(monkeypatch, parts=(CompanyPart.PEERS, CompanyPart.QUICK_RATIOS))
    assert "https://www.screener.in/api/company/992001/peers/" in requested
    assert "https://www.screener.in/api/company/992001/quick_ratios/" in requested
    assert not any(f"/api/company/{support.COMPANY_ID}/" in url for url in requested)


def test_the_full_run_requests_exactly_what_the_page_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rate-limited source makes the request budget part of the contract.

    Screener returned 429 after ~40 authenticated GETs. One page plus its
    sub-documents must stay well inside that, and every request must trace to a
    control the page rendered — no ``/2/`` geographic segments probe that no
    page links, and no follow of a holder's ``data-person-url``.
    """
    run, requested = support.read(monkeypatch)
    assert [url.replace("https://www.screener.in", "") for url in requested[1:]] == list(
        support.EXPECTED_DOCUMENT_PATHS
    )
    assert run.artifact.metadata.request_count == len(requested) == 15
    assert not any("/people/" in url for url in requested)
    assert not any("/2/" in url for url in requested)


# --------------------------------------------------------------------------
# Shareholding page tables
# --------------------------------------------------------------------------


def test_shareholding_tables_are_found_through_their_wrapper_divs() -> None:
    """``quarterly-shp`` and ``yearly-shp`` are DIV ids, not table ids.

    The tables themselves are bare ``table.data-table`` elements, and the page
    carries other ``data-table`` elements (the peer comparison among them), so a
    class-wide search would pick up a table that is not shareholding at all.
    """
    root = support.page_root()
    quarterly = read_shareholding_table(
        root,
        Periodicity.QUARTERLY,
        source_id=support.SOURCE_ID,
        file_sha256=support.ZERO_SHA,
        retrieved_at=support.RETRIEVED_AT,
    )
    assert quarterly is not None
    assert [period.label for period in quarterly.periods] == ["Sep 2025", "Dec 2025", "Mar 2026"]
    assert [row.bucket for row in quarterly.rows] == [
        "promoters",
        "foreign_institutions",
        "government",
        "public",
        None,
    ]
    assert quarterly.unit_statement == "Numbers in percentages"


def test_shareholding_columns_carry_no_fabricated_period_end() -> None:
    """The header publishes "Mar 2026" and no ``data-date-key``, so there is no date.

    The financial sections stamp an ISO ``data-date-key`` on every column; these
    tables do not. Parsing the label into a date would publish a period end the
    site never stated, and the same label shape means different things in the
    quarterly and yearly tabs.
    """
    root = support.page_root()
    table = read_shareholding_table(
        root,
        Periodicity.YEARLY,
        source_id=support.SOURCE_ID,
        file_sha256=support.ZERO_SHA,
        retrieved_at=support.RETRIEVED_AT,
    )
    assert table is not None
    assert all(period.kind is PeriodKind.UNTYPED for period in table.periods)
    assert all(period.period_end is None for period in table.periods)


def test_shareholder_count_row_is_not_published_as_a_percentage() -> None:
    """The section note says "Numbers in percentages" and one row is not.

    ``No. of Shareholders`` is an Indian-grouped integer under the same note.
    Applying the note to it would publish 1,30,111 percent, so the row's own
    ``tr.sub`` class decides — a renamed row is still counts.
    """
    root = support.page_root()
    table = read_shareholding_table(
        root,
        Periodicity.QUARTERLY,
        source_id=support.SOURCE_ID,
        file_sha256=support.ZERO_SHA,
        retrieved_at=support.RETRIEVED_AT,
    )
    assert table is not None
    counts = table.rows[-1]
    assert counts.label == "No. of Shareholders"
    assert counts.unit is Unit.COUNT
    assert counts.cells[-1].value == Decimal("130111")
    assert all(row.unit is Unit.PERCENT for row in table.rows[:-1])


# --------------------------------------------------------------------------
# Investor drill-downs
# --------------------------------------------------------------------------


def test_promoters_sum_to_the_page_row_and_that_is_the_only_proof_here(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promoters are disclosed in full, so equality is checkable and is the check.

    The investors response names no company, no basis and no bucket; the page
    row it expands is the only thing that can catch a body fetched for the wrong
    one. Promoters are the one bucket where every holder is published, so their
    sum must equal the row within two-decimal rounding.
    """
    run = support.run_only(monkeypatch)
    promoters = support.bucket(run, "promoters", "quarterly")
    assert promoters.strategy is SumStrategy.FLAT_SUM
    assert promoters.outcome is BucketOutcome.SUM_MATCHED
    assert promoters.validation is Validation.EQUALITY
    assert promoters.validation_status is ValidationStatus.PASSED
    assert promoters.binding is Binding.CONFIGURED_URL_ONLY
    assert [comparison.difference for comparison in promoters.comparisons] == [Decimal(0)] * 3


def test_promoters_that_do_not_sum_are_refused_with_the_body_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gap in a fully-disclosed bucket means the response is not this bucket.

    This is the only assertion available on the investors API, so failing it has
    to stop the document being admitted. The body is kept because a response
    that fails this gate is the most useful evidence the run produces — it is
    what a wrong company id actually looks like.
    """
    run = support.run_only(monkeypatch, swap=("investors__promoters_quarterly", ".mismatch"))
    assert run.artifact.metadata.all_admitted is False
    failure = next(found for found in run.artifact.failures if found.name == "promoters_quarterly")
    assert failure.refusal == "HoldingReconciliationError"
    assert "50.00" in failure.detail and "60.00" in failure.detail
    retained = next(
        document for document in run.documents if document.name == "promoters_quarterly"
    )
    assert b"30.00" in retained.raw_body


def test_a_threshold_bucket_is_bounded_and_never_called_proven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Below the page row is the *normal* state, so equality is unprovable here.

    Every bucket except promoters lists only holders at or above 1 %. TITAN's
    DIIs disclose 8.07 against a page row of 15.15 and both numbers are right.
    Passing the one-sided check bounds the bucket; calling that SUM_PROVEN would
    claim a completeness the source never offers.
    """
    run = support.run_only(monkeypatch)
    fiis = support.bucket(run, "foreign_institutions", "quarterly")
    assert fiis.strategy is SumStrategy.UPPER_BOUND
    assert fiis.outcome is BucketOutcome.WITHIN_BOUND
    assert fiis.validation is Validation.UPPER_BOUND
    assert fiis.validation_status is ValidationStatus.PASSED
    assert all(comparison.difference < 0 for comparison in fiis.comparisons)


def test_a_threshold_bucket_larger_than_its_own_page_row_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subset cannot exceed the whole it is drawn from.

    That is the one direction the threshold disclosure still makes checkable, so
    it is the one that fails closed: disclosed holders summing above the bucket
    row means the response does not belong to this bucket.
    """
    run = support.run_only(
        monkeypatch, swap=("investors__foreign_institutions_quarterly", ".exceeds")
    )
    failure = next(
        found for found in run.artifact.failures if found.name == "foreign_institutions_quarterly"
    )
    assert failure.refusal == "HoldingReconciliationError"
    assert "exceed" in failure.detail


def test_an_empty_bucket_body_is_legitimate_and_still_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``{}`` here means "no holder crosses 1 %", not "the request failed".

    TITAN's government bucket holds 0.19 % across many holders and returns an
    empty object. Slice 1 refuses an empty schedules body because none of its
    fifteen families is ever empty; here emptiness is the expected answer for a
    small bucket, and it still satisfies the upper bound.
    """
    run = support.run_only(monkeypatch)
    government = support.bucket(run, "government", "quarterly")
    assert government.holders == ()
    assert government.outcome is BucketOutcome.WITHIN_BOUND
    assert government.validation is Validation.UPPER_BOUND
    assert government.validation_status is ValidationStatus.PASSED
    assert not run.artifact.failures


def test_a_holder_that_did_not_hold_in_a_period_has_no_cell_for_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent key means the holder was not in the bucket, not that it held zero.

    Holders enter and exit; the response simply omits the periods they were
    absent for. Filling them with zero would publish a holding of zero that the
    source never stated and would make an exit look like a disposal to nil.
    """
    run = support.run_only(monkeypatch)
    public = support.bucket(run, "public", "quarterly")
    holder = public.holders[0]
    assert [cell.provenance.column_label for cell in holder.cells] == ["Sep 2025", "Mar 2026"]


def test_holder_person_urls_are_retained_and_never_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The person page is evidence of who a holder is, not a document to acquire.

    Following it would multiply the request count by the holder count — 410 on
    TITAN's promoters alone — against a source that rate-limits at ~40.
    """
    run, requested = support.read(monkeypatch)
    promoters = support.bucket(run, "promoters", "quarterly")
    assert promoters.holders[0].person_url == "/people/701/fixture-holdings-private-limited/"
    assert not any("/people/" in url for url in requested)
