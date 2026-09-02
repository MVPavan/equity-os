"""The four Slice 3 defects found at sign-off, each pinned before it is fixed.

Companion to :mod:`test_screener_screen` and :mod:`test_screener_screen_acquire`.
Kept apart from both because these tests are red on purpose: every one of them
states a behaviour the shipped implementation does not have, and the reason it
went unseen by a fully green gate. The builders and the transport seam are the
same ones those files use, reached through :mod:`screener_screen_support`.
"""

from __future__ import annotations

import hashlib

import pytest
import screener_screen_support as support
from pydantic import ValidationError


def test_a_populated_table_whose_rows_sit_outside_tbody_is_never_zero_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-18: the missing tag must not turn a refusal into "nothing matched".

    ``read_screen_table`` selects ``./tbody/tr``. libxml2, unlike a browser, does
    not synthesise a ``tbody``, so a table whose rows are direct children of
    ``<table>`` has zero of them and is read as the evidenced empty shape. The
    two rows below are ordinary result rows: inside a ``tbody`` they are already
    refused for declaring no schema, and moving nothing but the tag turns that
    refusal into a published ``ZERO_RESULTS`` — a real answer replaced by "this
    query matched nothing", with no refusal and no log anywhere.
    """
    rows = support.rows_for(1, count=2)
    inside = support.table_of("".join(support.data_row(row) for row in rows))
    outside = support.table_without_tbody(support.NARROW_LABELS, rows, header=False)
    for table in (inside, outside):
        with pytest.raises(support.models.ScreenStructureError):
            support.read_table(support.page(table, support.empty_pagination()))

    run, _ = support.acquire(monkeypatch, {1: support.page(outside, support.empty_pagination())})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.rows == ()
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenStructureError"


@pytest.mark.parametrize("section", ["tfoot", "table"], ids=["in-tfoot", "loose-under-table"])
def test_a_data_row_outside_tbody_is_never_dropped_from_a_published_result(
    monkeypatch: pytest.MonkeyPatch, section: str
) -> None:
    """SL3-18: a row the reader cannot see is under-reporting, not a clean result.

    libxml2 keeps ``tfoot`` a separate section and leaves a loose ``tr`` where it
    found it, so neither third row below is a ``./tbody/tr``. The two the reader
    does walk carry serials 1 and 2, so every continuity, identity and schema
    check still passes and the run publishes ``RESULTS`` — short one company,
    with nothing recording that a row existed. Downstream that is
    indistinguishable from a query that really returned two.
    """
    rows = support.rows_for(1, count=3)
    body = support.single_page(
        support.table_with_displaced_row(support.NARROW_LABELS, rows[:2], rows[2], section=section)
    )

    with pytest.raises(support.models.ScreenStructureError):
        support.read_table(body)

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.rows == ()
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenStructureError"


def test_an_incomplete_artifact_that_proves_nothing_cannot_be_built() -> None:
    """SL3-19: ``incomplete`` is a claim about evidence, so it must carry some.

    The ``INCOMPLETE`` branch of the validator asks only that
    ``incomplete_reason`` is set, which admits an artifact with no pages, no rows
    and no failure — a run that reports it stopped short while proving it ever
    started. Every other branch binds the outcome to the fields that justify it.
    An incomplete run either refused a page, and then it has a failure, or it
    stopped at the caller's bound, and then it has pages; there is no third way
    to reach this outcome, and both legitimate shapes must keep building.
    """
    artifact = support.models.ScreenArtifact
    outcome = support.models.ScreenOutcome.INCOMPLETE
    common = {"query": support.QUERY, "outcome": outcome, "incomplete_reason": "stopped"}

    with pytest.raises(ValidationError, match="do not match its outcome"):
        artifact(**common)

    refused = support.models.ScreenFailure(
        page_number=2,
        source_url=support.models.screen_url(support.QUERY, 2),
        refusal="ScreenStructureError",
        detail="stopped",
        content_sha256=None,
    )
    assert artifact(**common, failure=refused).failure is refused


def test_a_bounded_walk_still_builds_the_other_legitimate_incomplete_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-19's second half: the page-bound shape must survive the tightening.

    A walk stopped by ``max_pages`` has no failure at all — nothing refused it —
    and its evidence is the pages it did fetch. Requiring a failure outright
    would make this outcome unreachable, so the rule has to be the disjunction,
    and this is the half a too-strict fix would break.
    """
    run, _ = support.acquire(monkeypatch, support.walk(2), max_pages=1)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is None
    assert len(run.artifact.pages) == 1


@pytest.mark.parametrize(
    "body",
    [support.xml_declared_page(), ""],
    ids=["xml-declaration", "empty-body"],
)
def test_no_exception_may_leave_acquire_once_a_body_has_been_retained(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """SL3-16 REVISED: the invariant is the retention, not the exception class.

    The first fix caught ``etree.ParserError``. A body opening with an XML
    declaration raises ``ValueError`` instead — lxml refuses an encoding
    declaration on a unicode string — so it still escapes ``acquire_screen``,
    and because the CLI writes nothing until that call returns, the whole run's
    retained evidence dies with it. Once a fetch has been appended to
    ``documents`` no failure may leave this function unhandled, whatever it is:
    both bodies below are 2xx answers the host really can return.
    """
    raw = body.encode("utf-8")
    run, _ = support.acquire(monkeypatch, {1: support.results_page(1, offered=(1, 2)), 2: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.page_number == 2
    assert run.artifact.failure.content_sha256 == hashlib.sha256(raw).hexdigest()
    assert len(run.documents) == 2


def test_a_pagination_carrying_a_non_anchor_control_is_not_a_complete_single_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-20: the anchor-less return must demand the shape that was observed.

    Below the smallest page size the live block is ``<div class="pagination">``
    with no element children at all; above it, the nested page-size selector that
    SL3-10a makes prove itself with three clauses. The anchor-less branch still
    accepts merely "no ``<a>`` descendants", which is weaker than either, so a
    block that grows some new non-anchor control reads as a finished one-page
    result and the walk stops on evidence nothing supplied. The verified empty
    block must keep returning ``()``, so the tightening cannot simply be
    "refuse anything unfamiliar".
    """
    assert support.read_pagination(support.zero_result_page()) == ()

    table = support.results_table(support.NARROW_LABELS, support.rows_for(1, count=3))
    body = support.page(table, support.non_anchor_pagination())

    with pytest.raises(support.models.ScreenPaginationError):
        support.read_pagination(body)

    run, _ = support.acquire(monkeypatch, {1: body})

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.rows == ()
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"
