"""Fix-round contract: the transport header, part-level failure, and the gates.

Each test here encodes a way the first cut of Slice 2 was wrong against the live
source or against its own honesty rules, so each states WHY rather than what.
No test opens a socket.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import screener_company_support as support

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.api.screener_company_cli import (
    DOCUMENTS_DIRNAME,
    FAILURES_FILENAME,
    META_FILENAME,
    PAGE_RAW_FILENAME,
    render_screener_company_summary,
    run_screener_company_command,
)
from fundamentals.ingest.screener_company_models import (
    MAX_SUB_REQUESTS,
    Acquisition,
    Binding,
    CompanyPart,
    SegmentOutcome,
    Validation,
    ValidationStatus,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import XHR_HEADER, XHR_HEADER_VALUE

BARE_PAGE = support.FIXTURES / "synthetic_screener_company_bare.html"


def _argv(tmp_path: Path, config: Path, *extra: str) -> list[str]:
    return [
        "screener-company",
        "--stock",
        support.SYMBOL,
        "--out",
        str(tmp_path / "out"),
        "--config",
        str(config),
        *extra,
    ]


def _document(run: object, part: CompanyPart, document_id: str) -> object:
    outcome = support.outcome(run, part)  # type: ignore[arg-type]
    return next(document for document in outcome.documents if document.document_id == document_id)


# --------------------------------------------------------------------------
# A. The XHR header
# --------------------------------------------------------------------------


def test_sub_documents_carry_the_xhr_header_and_the_page_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without it ``/company/actions/<id>/`` answers 302 to the company page.

    Screener treats these paths as XHR endpoints: the browser sends
    ``X-Requested-With: XMLHttpRequest`` on every one of them, and without it the
    modal routes redirect instead of returning a body — which this adapter
    refuses to follow, so the whole part fails. The company page is a real
    navigation and must NOT carry the header, because that is not what a browser
    sends for it and the response differs.
    """
    built = support.capture_requests(monkeypatch)
    source = ScreenerSessionSource(support.config())
    source.fetch_document(url="https://www.screener.in/company/actions/991001/")
    assert built[-1].get_header(XHR_HEADER.capitalize()) == XHR_HEADER_VALUE

    source.fetch_company_page(
        symbol=support.SYMBOL,
        slug=support.SYMBOL,
        basis=support.Basis.CONSOLIDATED,
        expected_company_id=support.COMPANY_ID,
        topology=support.BasisTopology(
            consolidated_warehouse_id=support.CONSOLIDATED_WAREHOUSE_ID,
            standalone_warehouse_id=support.STANDALONE_WAREHOUSE_ID,
        ),
    )
    assert built[-1].get_header(XHR_HEADER.capitalize()) is None


# --------------------------------------------------------------------------
# B. A sub-document transport refusal is a part failure, not a run abort
# --------------------------------------------------------------------------


def test_a_redirected_sub_document_fails_its_part_and_the_run_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A refusal that escapes discards every body already paid for.

    The live smoke lost twelve to eighteen fetched sub-documents and wrote an
    empty output directory because one modal redirected. A rate limit is the
    only refusal that means "stop asking"; every other one is a fact about one
    document, and the documents around it are still good.
    """
    support.serve(monkeypatch, redirect_at=2)
    config = support.watchlist(tmp_path)
    exit_code = main(_argv(tmp_path, config))
    out_dir = tmp_path / "out"
    assert exit_code == EXIT_REFUSED
    assert (out_dir / META_FILENAME).exists()
    assert (out_dir / PAGE_RAW_FILENAME).exists()
    names = sorted(path.name for path in (out_dir / DOCUMENTS_DIRNAME).iterdir())
    assert len(names) == 13
    assert "investors__promoters-quarterly.raw.json" in names
    assert "peers__peers.raw.html" in names
    failures = json.loads((out_dir / FAILURES_FILENAME).read_text(encoding="utf-8"))
    assert [failure["refusal"] for failure in failures] == ["ScreenerRedirectError"]
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["complete"] is True
    assert metadata["all_admitted"] is False
    assert metadata["acquisition"] == Acquisition.REFUSED.value


# --------------------------------------------------------------------------
# C. Orthogonal evidence semantics
# --------------------------------------------------------------------------


def test_binding_and_validation_are_recorded_separately_per_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "How do we know this is theirs" and "did its numbers check out" are two questions.

    One ``verified`` flag forced them together, so a promoters body whose sum
    held read the same as a related-party modal nothing could check. Recording
    the binding and the validation apart means neither can borrow the other's
    credibility.
    """
    run = support.run_only(monkeypatch)
    promoters = _document(
        run, CompanyPart.INVESTORS, "/api/3/991001/investors/promoters/quarterly/"
    )
    assert promoters.binding is Binding.CONFIGURED_URL_ONLY  # type: ignore[attr-defined]
    assert promoters.validation is Validation.EQUALITY  # type: ignore[attr-defined]
    assert promoters.validation_status is ValidationStatus.PASSED  # type: ignore[attr-defined]

    public = _document(run, CompanyPart.INVESTORS, "/api/3/991001/investors/public/quarterly/")
    assert public.validation is Validation.UPPER_BOUND  # type: ignore[attr-defined]

    modal = _document(run, CompanyPart.RELATED_PARTY, "/results/rpt/991001/consolidated/")
    assert modal.validation is Validation.NONE  # type: ignore[attr-defined]
    assert modal.validation_status is ValidationStatus.NOT_APPLICABLE  # type: ignore[attr-defined]


def test_an_equality_proof_counts_as_proven_but_a_one_sided_bound_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An equality that holds establishes the document; a bound that holds does not.

    The promoter sum is the check that catches a response fetched for the wrong
    company: 410 holders adding to the exact figure a proven page states cannot
    plausibly be another issuer's promoters. That is a proof, and burying it with
    the unprovable documents made ``proven_documents`` the same three page tables
    for every company forever.

    An upper bound is different in kind. TITAN's DIIs disclose 8.07 against a
    page row of 15.15 and both numbers are right, so passing says only "not
    larger than the whole" — true of any subset, including one from the wrong
    company. Peers is weaker still: its body asserts whose list it is, but the
    figures a consumer reads off it are the *other* rows', which nothing checks.
    """
    run = support.run_only(monkeypatch)
    metadata = run.artifact.metadata
    assert metadata.proven_documents == (
        "shareholding:quarterly",
        "shareholding:yearly",
        "/api/3/991001/investors/promoters/quarterly/",
        "/api/3/991001/investors/promoters/yearly/",
        "page:#top-ratios",
    )
    for weak in (
        "/api/3/991001/investors/public/quarterly/",
        "/api/segments/991001/quarters/1/?consolidated=true",
        "/api/company/992001/peers/",
        "/results/rpt/991001/consolidated/",
    ):
        assert weak in metadata.weak_documents

    peers = _document(run, CompanyPart.PEERS, "/api/company/992001/peers/")
    assert peers.binding is Binding.BODY_ASSERTED  # type: ignore[attr-defined]
    assert peers.identity_assertion.value == "passed"  # type: ignore[attr-defined]


def test_acquisition_state_is_separate_from_whether_everything_was_admitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "We stopped early" and "something failed a check" are different repairs.

    One is a budget problem that a later re-run fixes; the other is a
    correctness problem that re-running reproduces. Collapsing them into one
    boolean told a caller neither.
    """
    clean = support.run_only(monkeypatch)
    assert clean.artifact.metadata.acquisition is Acquisition.COMPLETE
    assert clean.artifact.metadata.complete is True
    assert clean.artifact.metadata.all_admitted is True

    limited = support.run_only(monkeypatch, rate_limit_after=2)
    assert limited.artifact.metadata.acquisition is Acquisition.INCOMPLETE
    assert limited.artifact.metadata.complete is False
    assert limited.artifact.metadata.all_admitted is True


# --------------------------------------------------------------------------
# D. The three escape hatches
# --------------------------------------------------------------------------


def test_an_unaligned_investor_body_is_refused_not_downgraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recording it as a weaker class let a body about other periods be admitted.

    The page header is the only thing binding these percentages to periods. A
    response carrying a column the page does not have is not a softer version of
    the same document — it is one this contract cannot place in time at all.
    """
    run = support.run_only(monkeypatch, swap=("investors__promoters_quarterly", ".unaligned"))
    failure = next(found for found in run.artifact.failures if found.name == "promoters_quarterly")
    assert failure.refusal == "HoldingReconciliationError"
    assert "Jun 2026" in failure.detail


def test_a_segments_table_with_nothing_to_compare_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page offered the button, so a fragment with no comparable Sales is drift.

    ``NOT_COMPARABLE`` was an exemption reachable four ways — no Sales line, no
    overlapping period, unreadable Sales rows, or a missing page section — and
    each of them would have let a wrong-basis body through the one gate that
    catches it.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".no_sales"))
    failure = next(found for found in run.artifact.failures if found.name == "quarters_1")
    assert failure.refusal == "SegmentReconciliationError"


def test_not_offered_requires_the_owning_section_to_be_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absence of a section is not evidence about the company; it is drift.

    "The page rendered the Balance Sheet and no Corporate actions button" is a
    fact about the issuer. "The page has no Balance Sheet at all" means the page
    changed shape under us, and reporting that as NOT_OFFERED would file a
    layout change as an issuer property.
    """
    run = support.run_only(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_sectionless.html"
    )
    refusals = {failure.part: failure.refusal for failure in run.artifact.failures}
    assert refusals[CompanyPart.INVESTORS] == "DocumentUnreadableError"
    assert refusals[CompanyPart.CORPORATE_ACTIONS] == "DocumentUnreadableError"


# --------------------------------------------------------------------------
# E. Segments are always weak, and report variance in both directions
# --------------------------------------------------------------------------


def test_segments_are_never_presented_as_basis_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The newest-period rule is a trap for a wrong basis, not evidence of a right one.

    It fires on every wrong-basis capture and on no correct one, which makes it
    worth keeping — but passing it says only that the body did not undershoot
    the newest quarter. Nothing on a segments fragment names the company or the
    basis, so it stays configured-URL-only however well its Sales line adds up.
    """
    run = support.run_only(monkeypatch)
    segments = _document(
        run, CompanyPart.SEGMENTS, "/api/segments/991001/quarters/1/?consolidated=true"
    )
    assert segments.binding is Binding.CONFIGURED_URL_ONLY  # type: ignore[attr-defined]
    assert segments.validation is Validation.LOWER_BOUND_NEWEST  # type: ignore[attr-defined]
    assert segments.validation_status is ValidationStatus.PASSED  # type: ignore[attr-defined]
    assert "/api/segments/991001/quarters/1/?consolidated=true" in (
        run.artifact.metadata.weak_documents
    )


def test_variance_in_both_directions_is_reported_in_both_directions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Letting the overshoot win hid the periods that fell short.

    TITAN's yearly table exceeds the page in eleven periods and falls 90 crore
    short in Mar 2017; HFCL's exceeds in two and is 261 short in Mar 2016. A
    reader told only "exceeds_page" would never learn a period was missing a
    segment.
    """
    run = support.run_only(monkeypatch, swap=("segments__quarters_1", ".mixed"))
    quarters = support.segments_table(run, "quarters")
    assert quarters.outcome is SegmentOutcome.MIXED_VARIANCE
    assert "1 period(s) above" in quarters.note
    assert "1 period(s) below" in quarters.note


# --------------------------------------------------------------------------
# F. Promoter tolerance and body integrity
# --------------------------------------------------------------------------


def test_a_missing_promoter_is_refused_despite_the_holder_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-holder rounding band scaled to 410 holders swallows a whole holder.

    TITAN publishes 410 promoters, so ``0.005 x (n + 1)`` is 2.055 percentage
    points — wide enough to admit a body missing a 1.5 % shareholder, which is
    the exact failure the sum exists to catch. Observed diffs are 0.00, 0.01 and
    0.02, so an absolute cap of 0.10 keeps every real body and refuses that one.
    """
    exact = support.run_only(
        monkeypatch, body=("investors__promoters_quarterly", support.promoters_body())
    )
    assert not exact.artifact.failures

    missing = support.run_only(
        monkeypatch,
        body=(
            "investors__promoters_quarterly",
            support.promoters_body(drop="Fixture Anchor Holding"),
        ),
    )
    failure = next(
        found for found in missing.artifact.failures if found.name == "promoters_quarterly"
    )
    assert failure.refusal == "HoldingReconciliationError"


def test_a_repeated_holder_key_is_refused_rather_than_silently_collapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``json.loads`` keeps the last of two identical keys and says nothing.

    A body naming one holder twice would lose a holding and still sum to
    whatever the surviving copy says, so the loss is invisible to the very check
    that is supposed to detect it.
    """
    run = support.run_only(
        monkeypatch,
        body=(
            "investors__promoters_quarterly",
            support.promoters_body(duplicate="Fixture Anchor Holding"),
        ),
    )
    failure = next(found for found in run.artifact.failures if found.name == "promoters_quarterly")
    assert failure.refusal == "DocumentUnreadableError"
    assert "Fixture Anchor Holding" in failure.detail


def test_an_unreadable_holding_is_refused_not_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A value that does not parse is dropped from the sum, which lowers it silently.

    Skipping it makes the total smaller, which an upper-bound check reads as
    "fine" and an equality check reads as a shortfall of unknown size. Either
    way the artifact would carry a total that no set of published holdings adds
    up to.
    """
    body = json.loads(support.promoters_body())
    body["Fixture Anchor Holding"]["Sep 2025"] = "n/a"
    run = support.run_only(
        monkeypatch,
        body=("investors__promoters_quarterly", json.dumps(body).encode("utf-8")),
    )
    failure = next(found for found in run.artifact.failures if found.name == "promoters_quarterly")
    assert failure.refusal == "DocumentUnreadableError"
    assert "n/a" in failure.detail


# --------------------------------------------------------------------------
# G. Orchestration boundaries
# --------------------------------------------------------------------------


def test_a_structural_refusal_inside_one_part_leaves_the_others_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate table in one fragment says nothing about the next fragment.

    These refusals come from the shared table reader, not from this slice's own
    error base, so they were escaping the part boundary and taking the run with
    them — discarding bodies that had already been paid for.
    """
    run = support.run_only(monkeypatch, swap=("peers", ".two_tables"))
    failure = next(found for found in run.artifact.failures if found.name == "peers")
    assert failure.refusal == "AmbiguousStructureError"
    assert run.artifact.corporate_actions is not None
    assert len(run.artifact.quick_ratios) == 2


def test_a_request_plan_over_the_cap_is_refused_before_anything_is_fetched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The budget has to be checked against the plan, not discovered by spending it.

    Screener rate-limits at ~40 authenticated GETs. A page that suddenly offers
    fifty drill-downs would otherwise be discovered one 429 at a time, after
    most of the budget was already gone.
    """
    run, requested = support.read(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_oversized.html"
    )
    assert len(requested) == 1
    assert run.artifact.metadata.acquisition is Acquisition.REFUSED
    assert any(str(MAX_SUB_REQUESTS) in failure.detail for failure in run.artifact.failures)


def test_a_page_supplied_modal_path_off_the_expected_shape_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``data-url`` is page-controlled input that becomes an authenticated request.

    The session cookie rides on whatever this builds. Traversal, an absolute
    URL, or a path outside the prefix this part means would all still be
    on-origin and would all still be sent.
    """
    run = support.run_only(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_hostile.html"
    )
    refusals = {failure.part: failure.refusal for failure in run.artifact.failures}
    assert refusals[CompanyPart.RELATED_PARTY] == "DiscoveryAmbiguousError"
    assert refusals[CompanyPart.CORPORATE_ACTIONS] == "DiscoveryAmbiguousError"


def test_a_symlinked_documents_directory_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Retained bodies must land inside the output directory this run was given.

    A ``documents`` symlink planted beforehand would write every retained
    response somewhere the caller never named, and no-clobber does not help
    because the files inside it are new.
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (out_dir / DOCUMENTS_DIRNAME).symlink_to(elsewhere, target_is_directory=True)
    support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(_argv(tmp_path, config))
    assert DOCUMENTS_DIRNAME in str(excinfo.value)
    assert not list(elsewhere.iterdir())


def test_a_bucket_with_no_page_row_to_compare_against_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A drill-down nothing can be held to is the last way to skip the only check.

    The investors API names no company, no basis and no bucket, so the page row
    the drill-down expands is the entire assertion available. A hook whose
    bucket has no row — a control rendered outside the tables, or a tab whose
    table did not render — leaves a response admitted on the strength of its URL
    alone, while every other bucket in the same run was checked. Recording that
    as "the check did not run" was an exemption in the one place the slice
    cannot afford one.
    """
    run = support.run_only(
        monkeypatch,
        page=support.FIXTURES / "synthetic_screener_company_orphan_bucket.html",
    )
    failure = next(found for found in run.artifact.failures if found.name == "custodians_quarterly")
    assert failure.refusal == "HoldingReconciliationError"
    assert "custodians" in failure.detail
    # The buckets that do have rows are unaffected.
    assert {bucket.bucket for bucket in run.artifact.investors} == {
        "promoters",
        "foreign_institutions",
        "government",
        "public",
    }


def test_no_validation_status_means_a_check_silently_did_not_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every applicable check either passes or refuses; there is no third outcome.

    A ``not_run`` status would be a value that reads as neither success nor
    failure, which is exactly the shape a reader skims past. With the last
    producer gone the member is deleted rather than left as a value nothing can
    emit, so the vocabulary cannot drift back into offering one.
    """
    assert not hasattr(ValidationStatus, "NOT_RUN")
    run = support.run_only(monkeypatch)
    statuses = {
        document.validation_status
        for outcome in run.artifact.outcomes
        for document in outcome.documents
    }
    assert statuses == {ValidationStatus.PASSED, ValidationStatus.NOT_APPLICABLE}


# --------------------------------------------------------------------------
# Round 3: the part boundary, the summary's wording, hook validation, budgets
# --------------------------------------------------------------------------


def test_a_duplicated_page_table_column_fails_only_its_own_part(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The page tables are read inside the part, so their refusals belong to it.

    A repeated column label in the Shareholding header makes every drill-down's
    period binding ambiguous, and the table reader rightly refuses it. But that
    read happened before the part's own try, so the refusal escaped as a
    whole-command abort — the same shape as the live-smoke bug, and with the
    same cost: five perfectly good parts and their fetched bodies discarded, and
    nothing published.
    """
    support.serve(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_duplicate_period.html"
    )
    config = support.watchlist(tmp_path)
    exit_code = main(_argv(tmp_path, config))
    out_dir = tmp_path / "out"
    assert exit_code == EXIT_REFUSED
    assert (out_dir / META_FILENAME).exists()
    failures = json.loads((out_dir / FAILURES_FILENAME).read_text(encoding="utf-8"))
    assert [failure["part"] for failure in failures] == ["investors"]
    assert failures[0]["refusal"] == "AmbiguousStructureError"
    published = json.loads((out_dir / "part_peers.json").read_text(encoding="utf-8"))
    assert published["peers"] is not None
    assert sorted(path.name for path in (out_dir / DOCUMENTS_DIRNAME).iterdir()) == [
        "corporate-actions__corporate-actions.raw.html",
        "peers__peers.raw.html",
        "quick-ratios__quick-ratios.raw.html",
        "related-party__related-party.raw.html",
        "segments__profit-loss-1.raw.html",
        "segments__quarters-1.raw.html",
    ]


def test_the_summary_never_calls_a_segments_check_a_flat_sum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Printing "flat_sum reconciled" claimed a proof the check does not make.

    The segments relation is one-sided and covers one period: the newest Sales
    total may not fall below the page's. A human reading "flat_sum reconciled"
    would reasonably conclude the whole table reconciled and the basis was
    confirmed, when TITAN's real consolidated table exceeds its page row in every
    period and nothing on the fragment names the company at all.
    """
    support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    from fundamentals.api.cli_parser import build_parser

    published = run_screener_company_command(
        build_parser().parse_args(_argv(tmp_path, config)),
        credentials=support.config().credentials,  # type: ignore[arg-type]
    )
    summary = render_screener_company_summary(published)  # type: ignore[arg-type]
    segment_lines = [line for line in summary.splitlines() if line.startswith("segments ")]
    assert segment_lines, summary
    assert not any("flat_sum" in line for line in segment_lines)
    assert all("lower_bound_newest" in line for line in segment_lines)
    assert any("newest_period_not_below" in line for line in segment_lines)


def test_an_absolute_modal_url_is_refused_rather_than_read_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filtering a hostile hook out turned an attack into a clean exit zero.

    The candidate was dropped for not starting with the expected prefix, so the
    part reported "this company publishes no Related Party" and the run exited
    zero. A control that names this part and points off-site is the opposite of
    absent: it is the page trying to send an authenticated request somewhere
    this adapter never meant to.
    """
    run = support.run_only(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_absolute_url.html"
    )
    failure = next(
        found for found in run.artifact.failures if found.part is CompanyPart.RELATED_PARTY
    )
    assert failure.refusal == "DiscoveryAmbiguousError"
    assert "evil.example" in failure.detail
    assert not any(
        outcome.part is CompanyPart.RELATED_PARTY and not outcome.offered
        for outcome in run.artifact.outcomes
    )


def test_the_segments_basis_query_is_refused_on_every_other_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One allowance shared by every part is an allowance nobody scoped.

    ``?consolidated=true`` means something only to the segments endpoint. Letting
    it through on a related-party path lets a page append a query this adapter
    would then send, and the modal routes have no basis parameter for it to
    mean anything by.
    """
    run = support.run_only(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_query_url.html"
    )
    failure = next(
        found for found in run.artifact.failures if found.part is CompanyPart.RELATED_PARTY
    )
    assert failure.refusal == "DiscoveryAmbiguousError"
    assert "consolidated=true" in failure.detail


def test_an_over_cap_plan_is_recorded_as_an_incomplete_refused_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run that fetched nothing is not a complete one.

    Reporting ``complete=true`` for a plan that was refused before its first
    sub-request says every planned request was attempted, when none was. The
    reason has to name the plan against the cap, because that is the only thing
    that tells the next person whether the page grew or the cap is wrong.
    """
    run, requested = support.read(
        monkeypatch, page=support.FIXTURES / "synthetic_screener_company_oversized.html"
    )
    metadata = run.artifact.metadata
    assert len(requested) == 1
    assert metadata.acquisition is Acquisition.REFUSED
    assert metadata.complete is False
    assert metadata.incomplete_reason is not None
    assert str(metadata.planned_sub_requests) in metadata.incomplete_reason
    assert str(MAX_SUB_REQUESTS) in metadata.incomplete_reason


def test_the_attempt_that_hit_the_rate_limit_is_counted_and_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request that earned the 429 was made, so leaving it uncounted is wrong.

    ``request_count`` is the politeness ledger — what this run actually asked
    the source for — and the refused attempt is the one that mattered most. The
    reason has to measure against the planned total too: "after 2 of 3" reads as
    a nearly finished run when fourteen sub-documents were planned.
    """
    run, requested = support.read(monkeypatch, rate_limit_after=2)
    metadata = run.artifact.metadata
    assert metadata.request_count == len(requested)
    assert len(run.documents) == 2
    assert metadata.incomplete_reason is not None
    assert "2 of 14" in metadata.incomplete_reason
    assert metadata.planned_sub_requests == 14
