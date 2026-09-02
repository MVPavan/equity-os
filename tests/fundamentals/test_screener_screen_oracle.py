"""SL3-22 and SL3-21: the page states its own total, and that is the oracle.

Five defects in this slice were the same failure — a pagination or table rule
that was internally coherent and wrong against the live surface, letting a walk
end early or drop a row while publishing a *complete* result. Four of the five
fixes were another inference about markup, and four of those inferences were
wrong.

Every shape this slice has ever seen, the zero-result page included, carries one
line of the form ``<N> results found: Showing page <p> of <q>``. That is a
number the source publishes about itself, and comparing it against what was
admitted catches the whole defect class without understanding the pagination
markup at all. The tests below are written against that comparison, not against
any anchor rule, which is why they still hold whichever markup inference turns
out to be wrong next.
"""

from __future__ import annotations

import pytest
import screener_screen_support as support


def test_a_page_that_states_no_total_at_all_is_refused_rather_than_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 1: a missing oracle is not permission to trust the walk.

    Every captured shape carries the line, so a page without one is not a page
    this reader has ever seen. Falling back to "the pagination looked finished"
    is exactly the reasoning that shipped five defects: the fallback is silent,
    it always says complete, and nothing downstream records that the only
    completeness evidence the surface publishes was absent.
    """
    body = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3)),
        support.pagination((1,), active=1),
        stated="",
    )

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.rows == ()
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenStructureError"


@pytest.mark.parametrize(
    ("total", "pages"),
    [(24, 2), (16, 3)],
    ids=["page-two-states-a-different-total", "page-two-states-a-different-page-count"],
)
def test_two_pages_that_disagree_about_the_result_set_are_never_one_result(
    monkeypatch: pytest.MonkeyPatch, total: int, pages: int
) -> None:
    """SL3-22 rule 2: a result set that moved under the walk is not complete.

    Page 1 states sixteen results across two pages. If page 2 states anything
    else, the two bodies describe different queries — a row was inserted or
    removed between the requests — and concatenating them produces a row set
    that never existed at any instant. That is not a refusal about markup; the
    pages are individually well formed and only their claims conflict.
    """
    bodies = support.walk(2)
    bodies[2] = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(2)),
        support.pagination((1, 2), active=2, previous=True),
        stated=support.results_found_line(total, 2, pages),
    )

    run, _ = support.acquire(monkeypatch, bodies)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.incomplete_reason is not None


def test_a_page_that_says_it_is_a_page_we_did_not_ask_for_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 3: the stated page number must be the requested one.

    The active anchor already claims this, but from inside the pagination block
    every amendment in this slice has been about. The stated line makes the same
    claim from an independent place on the page, so a cache, a redirect, or a
    template serving page 1's body under page 2's URL is caught even when the
    anchors are perfectly consistent with themselves.
    """
    bodies = support.walk(2)
    bodies[2] = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(2)),
        support.pagination((1, 2), active=2, previous=True),
        stated=support.results_found_line(16, 1, 2),
    )

    run, _ = support.acquire(monkeypatch, bodies)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None


def test_a_walk_the_pagination_calls_finished_still_refuses_when_rows_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 4, and the reason this file exists.

    The pagination markup here is complete, self-consistent and terminal: one
    numeric anchor, marked active, matching the requested page, no ``Next``,
    nothing nested, nothing stray. Every pagination rule in this slice — the four
    that were wrong and the ones that replaced them — agrees the walk is over
    after page 1, and today the run publishes ``RESULTS`` with three rows.

    The page says there are five. Revert every pagination amendment and this test
    still fails, which is the property none of the others have: it does not
    depend on any inference about markup, only on the arithmetic of what was
    admitted against what the source claimed.
    """
    body = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3)),
        support.pagination((1,), active=1),
        total=5,
    )
    assert support.read_pagination(body) == (1,)

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is not support.models.ScreenOutcome.RESULTS
    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"


def test_a_walk_that_visited_fewer_pages_than_the_page_claims_exist_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 4, the other conjunct: pages walked must equal ``<q>``.

    A row count can agree by coincidence — a page that dropped one row and
    gained another states a total the walk still matches. The page count cannot:
    it is the walk's own trip report against the number of pages the source says
    it published, and it is the check that survives a page-size change or a
    result set whose rows happen to balance.
    """
    body = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3)),
        support.pagination((1,), active=1),
        stated=support.results_found_line(3, 1, 2),
    )

    run, recorder = support.acquire(monkeypatch, {1: body})

    assert [support.requested_page(url) for url in recorder.urls] == [1]
    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"


def test_the_callers_own_page_bound_stops_short_without_becoming_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 5: stopping early on purpose is not stopping early by accident.

    Every other rule here turns a short walk into a refusal, so the bounded walk
    is the shape a too-eager fix breaks: nothing is wrong with these pages, the
    caller simply asked for two of the three. It stays ``INCOMPLETE`` with no
    failure — and the artifact has to say how far short of the stated total it
    stopped, because "incomplete" without that number is the same unfalsifiable
    claim the stated total exists to replace.
    """
    run, recorder = support.acquire(monkeypatch, support.walk(3), max_pages=2)

    assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is None
    assert len(run.artifact.rows) == 16
    assert run.artifact.incomplete_reason is not None
    assert "24" in run.artifact.incomplete_reason


def test_a_next_anchor_naming_a_page_nobody_offered_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-21: ``Next`` is a claim that a successor exists, and it must be honoured.

    ``read_screen_pagination`` discards every non-numeric anchor, so a block
    holding an active ``1`` and a ``Next`` linking page 2 — with no numeric ``2``
    beside it — offers ``(1,)``, the walk sees no higher page and publishes
    ``RESULTS`` complete after one request. The stated total here agrees with the
    three admitted rows and with one page, so SL3-22 does not fire and this
    anchor is the only thing wrong with the body.
    """
    body = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3)),
        support.pagination((1,), active=1, next_page=True, next_href_page=2),
    )

    with pytest.raises(support.models.ScreenPaginationError):
        support.read_pagination(body)

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"


def test_the_terminal_page_carries_no_next_and_must_not_be_caught_by_that_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-21's other half, verified rather than assumed: the last page omits ``Next``.

    Across the retained 3-page smoke, pages 1 and 2 carry ``Next`` and page 3
    does not. So a rule phrased as "``Next`` must be corroborated" is safe, and a
    rule phrased as "``Next`` must be present while pages remain" or "a missing
    ``Next`` is suspicious" refuses every completed walk. This is the test that
    fails if the SL3-21 fix reaches for the absent anchor.
    """
    bodies = support.walk(2)
    assert "Next" in bodies[1]
    assert "Next" not in bodies[2]
    assert support.read_pagination(bodies[2], requested_page_number=2) == (1, 2)

    run, recorder = support.acquire(monkeypatch, bodies)

    assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
    assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS
    assert len(run.artifact.rows) == 16


def test_the_stated_total_is_read_from_data_page_info_not_from_its_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-22 rule 6: the hook is the semantic attribute, never the styling.

    The live line is ``<div class="sub" data-page-info> … </div>`` inside a flex
    wrapper. ``sub`` and the wrapper's flex tokens are presentational — the same
    kind of token this slice was already told not to pin on the result table —
    and a restyle drops them without touching the sentence. ``data-page-info`` is
    the attribute the template author put there on purpose, and it is identical
    on the zero-result page and on page 4 of 18.

    So this body carries the same sentence under the same attribute with the
    class gone. A reader keyed on ``data-page-info`` reads five, admits three and
    refuses the walk. A reader keyed on the class finds no line at all: it either
    refuses as a *structural* fault under rule 1, or falls back to the pagination
    and publishes a complete three-row result — the exact silent under-report
    this file exists to catch. Neither reaches ``ScreenPaginationError``, so a
    fragile implementation cannot pass this while passing the rest.
    """
    body = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3)),
        support.pagination((1,), active=1),
        stated=support.results_found_line(5, 1, 1, class_attr=None),
    )
    assert support.PAGE_INFO_ATTRIBUTE in body
    assert 'class="sub"' not in body

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"


def test_every_page_of_a_walk_records_the_total_and_page_count_it_stated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-23: rule 2 is auditable only if each page's own claim is retained.

    The walk reads the stated line from all three pages and compares them, then
    throws all three away. A consumer holding the artifact sees twenty-four rows
    and ``RESULTS`` and has to take "every page agreed" on faith — or re-parse
    the retained bytes and reimplement the reader to check. Recording the pair
    per page, not once on the artifact, is what turns the agreement into an
    observed fact: a reader can see the same ``24`` and ``3`` on page 1, page 2
    and page 3 rather than a summary asserting they matched.
    """
    run, _ = support.acquire(monkeypatch, support.walk(3))

    assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS
    assert len(run.artifact.rows) == 24
    assert [page.page_number for page in run.artifact.pages] == [1, 2, 3]
    assert [(page.stated_total, page.stated_pages) for page in run.artifact.pages] == [
        (24, 3),
        (24, 3),
        (24, 3),
    ]


def test_a_single_page_run_records_the_total_and_page_count_that_page_stated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-23: the one-page walk states its own numbers and must record them.

    This is the shape where the oracle looks redundant — the row count is right
    there and there is only one page to disagree with. It is also the shape that
    a fix keying the recording off "more than one page walked", or off the
    presence of pagination the single page barely has, would leave blank. An
    artifact whose completeness evidence is present for long runs and absent for
    short ones is worse than none: the absence reads as a fact about the page.
    """
    run, _ = support.acquire(monkeypatch, support.walk(1))

    assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS
    assert len(run.artifact.rows) == 8
    assert [(page.stated_total, page.stated_pages) for page in run.artifact.pages] == [(8, 1)]


def test_a_zero_result_run_records_the_nothing_the_page_stated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-23: ``0 results found: Showing page 1 of 1`` is a claim, not a blank.

    The empty page carries the line like every other shape, and it is the only
    evidence distinguishing "the query genuinely matched nothing" from "the
    table was read as empty". Left unrecorded, or recorded as ``None`` because
    zero looked like an absence, the artifact says ``zero_results`` with nothing
    behind it — which is exactly the unfalsifiable completeness claim SL3-22
    exists to replace.
    """
    run, _ = support.acquire(
        monkeypatch, {1: support.zero_result_page()}, query=support.EMPTY_QUERY
    )

    assert run.artifact.outcome is support.models.ScreenOutcome.ZERO_RESULTS
    assert run.artifact.rows == ()
    assert [(page.stated_total, page.stated_pages) for page in run.artifact.pages] == [(0, 1)]
