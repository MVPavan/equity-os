"""Slice 3 reading contract: one authenticated ``/screen/raw/`` query.

Every fixture here is synthetic — invented queries, companies, slugs, ids and
numbers — built from the structure the live surface was verified to have. The
facts that were expensive to learn are the ones the fixtures encode: the header
row repeats inside one ``tbody``, the column set follows the query,
``.pagination`` holds a second ``options`` block that is a page-size selector,
``Previous`` and ``Next`` are anchors that are not pages, a zero-result page has
no header row and no pagination anchors at all, and one company in 150 is
addressed by ``/company/id/<n>/`` because it has no slug.

Each test states the requirement id it pins and why that behaviour matters. The
transport seam and the builders live in :mod:`screener_screen_support`; the walk
itself, its terminal refusals and the frozen model seam live in
:mod:`test_screener_screen_acquire`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import screener_company_support as company_support
import screener_screen_support as support

from fundamentals.api.screener_cli_dispatch import EXIT_OK
from fundamentals.contracts.provenance import SourceAnchorType

_QUERY_ENCODED = "Alpha+ratio+%3E+11+AND+Beta+score+%3C+3"
_SCREEN_BASE = "https://www.screener.in/screen/raw/?sort=&order=&source=&query="
_PEERS_URL = "https://www.screener.in/api/company/992001/peers/"


def _screen_url(page_number: int) -> str:
    """The exact URL this slice is contracted to build for one page."""
    return f"{_SCREEN_BASE}{_QUERY_ENCODED}&page={page_number}"


# --------------------------------------------------------------------------
# Transport and URL
# --------------------------------------------------------------------------


def test_every_page_of_one_query_goes_through_one_navigation_shaped_session_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-01: one injected session carries every page, and none of them is an XHR.

    Screener rate-limits this account after ~40 authenticated GETs, so a second
    source would be a second unpaced conversation with the same host. And
    ``X-Requested-With`` is exactly what a browser never sends on a navigation:
    putting it on a screen page asks for a response no browser ever receives,
    while dropping it from the sub-document fetches turns the modals back into
    the 302s this adapter refuses to follow.

    The identity of the receiver is asserted, not just the count of calls: a walk
    that builds a fresh source per page issues exactly the same requests while
    resetting the spacing clock and the 429 budget on every one of them.
    """
    with monkeypatch.context() as patcher:
        injected = support.source()
        run, recorder = support.acquire(patcher, support.walk(2), injected=injected)
        assert recorder.urls == [_screen_url(1), _screen_url(2)]
        assert recorder.xhr == [False, False]
        assert [seen is injected for seen in recorder.sources] == [True, True]
        assert len(run.artifact.pages) == 2

    built = company_support.capture_requests(monkeypatch)
    source = support.source()
    source.fetch_screen_page(url=support.models.screen_url(support.QUERY, 1))
    source.fetch_document(url=_PEERS_URL)

    assert built[0].full_url == _screen_url(1)
    assert built[0].get_header("Cookie") == f"sessionid={support.SESSION_TOKEN}"
    assert built[0].get_header("X-requested-with") is None
    assert built[1].get_header("X-requested-with") == "XMLHttpRequest"


@pytest.mark.parametrize("query", ["", "   ", "\t\n "])
def test_a_query_that_is_blank_or_only_whitespace_never_becomes_a_url(query: str) -> None:
    """SL3-01: an unaddressable query is refused here, not answered by the host.

    ``/screen/raw/?query=`` is a live URL: it returns a real page for the empty
    filter set, so a blank query that reaches the transport spends a request out
    of a ~40-request budget and comes back looking like a successful screen of
    every listed company. Refusing before the URL exists keeps that answer from
    ever being attributed to the caller's query.
    """
    with pytest.raises(support.models.ScreenQueryError):
        support.models.screen_url(query, 1)


@pytest.mark.parametrize("page_number", [0, -1])
def test_a_page_number_below_one_never_becomes_a_url(page_number: int) -> None:
    """SL3-01: pages are one-based, and the walk's own arithmetic must be checked.

    Every offered page in this slice comes from anchor text starting at ``1``, so
    a zero or negative page is always a caller or traversal defect rather than a
    site fact. The host answers ``page=0`` with page one, which would let an
    off-by-one walk re-admit page one's rows under a different position instead
    of failing the global-serial check.
    """
    with pytest.raises(support.models.ScreenQueryError):
        support.models.screen_url(support.QUERY, page_number)


@pytest.mark.parametrize(
    "table",
    [
        # A bare ``th`` inside ``tbody``: lxml does not invent a ``tr`` around it,
        # so the table has zero ``./tbody/tr`` and still declares a schema.
        "<tbody><th>Alpha Ratio %</th></tbody>",
        # The same cell one level higher, directly inside ``table``.
        "<th>Alpha Ratio %</th>",
        # A real header row parked in ``thead`` beside an empty ``tbody``.
        "<thead><tr><th>Alpha Ratio %</th></tr></thead><tbody></tbody>",
    ],
)
def test_a_rowless_screen_table_that_still_declares_a_header_is_refused(table: str) -> None:
    """SL3-03: rowlessness alone does not make a table the evidenced empty shape.

    The zero-result page carries no header at all, so a table with no
    ``tbody/tr`` but a surviving ``th`` is a third thing: a schema with nothing
    under it. Reading it as zero results would publish "this query matched
    nothing" for a page that in fact declared columns, which is the same wrong
    answer as a half-read table and is indistinguishable downstream from a real
    empty result.
    """
    body = support.page(
        f'<table class="{support.TABLE_CLASS}">{table}</table>', support.empty_pagination()
    )

    with pytest.raises(support.models.ScreenStructureError):
        support.read_table(body)


# --------------------------------------------------------------------------
# Schema, table shape, cells and identity
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "labels"),
    [
        (support.QUERY, support.NARROW_LABELS),
        (support.WIDE_QUERY, support.WIDE_LABELS),
    ],
)
def test_the_columns_are_whatever_the_returned_header_row_says_they_are(
    monkeypatch: pytest.MonkeyPatch, query: str, labels: tuple[str, ...]
) -> None:
    """SL3-02: the column set follows the query, so only the header may declare it.

    The two live queries returned 18 and 20 columns — the same 18 plus the two
    ratios the second query named. A parser holding a registry of columns would
    silently mis-attribute every value of the wider result. The labels also sit
    inside sort anchors, so a cell's own ``.text`` is empty and only
    ``text_content()`` recovers them.
    """
    run, _ = support.acquire(monkeypatch, support.walk(1, labels=labels), query=query)

    assert tuple((column.index, column.label) for column in run.artifact.columns) == tuple(
        enumerate(labels)
    )
    assert run.artifact.query == query
    assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS


def test_the_result_table_is_found_by_one_class_token_and_its_repeated_headers_are_not_data() -> (
    None
):
    """SL3-03: the header repeats four times per page and every repeat is a header.

    Verified on every populated capture: 54 ``tr`` inside one ``tbody``, of which
    four are byte-identical header rows. A reader that treats the first row as
    the only header and refuses later ``th`` refuses every live populated page;
    one that treats them as data invents four companies per page. The five
    presentational class tokens are deliberately not pinned — a stylesheet
    refresh dropping one must not turn every query into a structure error — and
    each shape below parses cleanly into *something*, which is why refusing it
    has to be explicit: a half-read table publishes numbers under the wrong
    column labels, and downstream that is indistinguishable from real data.
    """
    live = support.live_page(1, offered=(1, 2))
    headers, data_rows = support.row_shapes(live)
    assert len(headers) == support.LIVE_HEADER_COUNT
    assert len(set(headers)) == 1
    assert data_rows == support.LIVE_ROWS_PER_PAGE
    assert len(headers) + data_rows == support.LIVE_ROW_COUNT

    columns, rows = support.read_table(live)
    assert len(columns) == len(support.NARROW_LABELS)
    assert len(rows) == support.LIVE_ROWS_PER_PAGE
    assert tuple(row.serial_number for row in rows) == tuple(
        range(1, support.LIVE_ROWS_PER_PAGE + 1)
    )
    assert all(row.company.display_name.startswith("Synthetic Holdings") for row in rows)

    # The same rows under one required class token, out of its live position and
    # beside tokens no capture carries: identifying the table by the class string
    # rather than by the token would read this page differently, or not at all.
    minimal = support.single_page(
        support.results_table(
            support.NARROW_LABELS,
            support.rows_for(1, count=support.LIVE_ROWS_PER_PAGE),
            block=support.LIVE_HEADER_BLOCK,
            class_attribute=support.MINIMAL_TABLE_CLASS,
        )
    )
    minimal_columns, minimal_rows = support.read_table(minimal)
    assert minimal_columns == columns
    assert tuple(row.company for row in minimal_rows) == tuple(row.company for row in rows)
    assert tuple(row.serial_number for row in minimal_rows) == tuple(
        row.serial_number for row in rows
    )
    assert [[(cell.value, cell.raw_text) for cell in row.cells] for row in minimal_rows] == [
        [(cell.value, cell.raw_text) for cell in row.cells] for row in rows
    ]

    for body in support.malformed_pages():
        with pytest.raises(support.models.ScreenStructureError):
            support.read_table(body)


def test_a_cell_keeps_its_lexeme_when_empty_or_unreadable_and_says_where_it_came_from() -> None:
    """SL3-04: empty and unreadable are different facts, and both are aligned data.

    An empty cell is "this company has no such figure"; an unreadable one is
    "the site printed something this reader does not understand". Collapsing
    them would make a parser change look like an issuer fact. Neither aborts the
    row, and the anchor beside each value is what lets someone return to the
    exact bytes it came from — which is the whole point of retaining them.
    """
    row = support.one_row(
        serial=51, company_id=770051, values=("1,234.50", "", "not available", "-8.75")
    )
    body = support.page_of(row)

    columns, rows = support.read_table(body, page_number=2)

    parsed = rows[0]
    assert parsed.page_number == 2
    assert parsed.serial_number == 51
    assert tuple(cell.column_index for cell in parsed.cells) == (2, 3, 4, 5)
    assert [(cell.value, cell.raw_text) for cell in parsed.cells] == [
        (Decimal("1234.50"), "1,234.50"),
        (None, ""),
        (None, "not available"),
        (Decimal("-8.75"), "-8.75"),
    ]

    provenance = parsed.cells[0].provenance
    assert provenance.source_id == support.SOURCE_ID
    assert provenance.file_sha256 == support.fetch(body, page_number=2).content_sha256
    assert provenance.retrieved_at == support.FETCHED_AT
    assert provenance.anchor_type is SourceAnchorType.HTML_TABLE
    assert provenance.table_id == support.TABLE_ID
    assert provenance.row_path == "row[51]"
    assert provenance.column_index == 2
    assert provenance.column_label == columns[2].label
    assert (
        provenance.document_id,
        provenance.island_id,
        provenance.table_key,
        provenance.row_label,
        provenance.page,
    ) == (None, None, None, None, None)


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/company/SYNTHONE/", ("SYNTHONE", False)),
        ("/company/SYNTHONE/consolidated/", ("SYNTHONE", True)),
        # An invented six-digit scrip code stands in for a company with no NSE
        # symbol: an all-numeric slug is legitimate on the live surface and must
        # not be pattern-checked away.
        ("/company/770042/", ("770042", False)),
        ("/company/id/770001/", (None, False)),
        # The id route must agree with the row's own id, or the link and the row
        # describe two different companies.
        ("/company/id/770099/", None),
        # ``id`` is reserved for the three-segment numeric route.
        ("/company/id/", None),
        ("/company/id/consolidated/", None),
        ("/company/SYNTHONE/standalone/", None),
        ("/company/SYNTHONE/consolidated/extra/", None),
        ("https://www.screener.in/company/SYNTHONE/", None),
        ("/company/SYNTHONE/?basis=consolidated", None),
        ("/company/SYNTHONE/#top", None),
        ("/screen/raw/SYNTHONE/", None),
    ],
)
def test_a_company_is_identified_by_one_of_three_link_shapes_and_nothing_else(
    href: str, expected: tuple[str | None, bool] | None
) -> None:
    """SL3-05: three href shapes are real, and the identity fields stay distinct.

    The consolidated form is the *majority* on some live pages, so requiring a
    single path segment refuses most rows; ``/company/id/<n>/`` appeared once in
    150 links and is how a company with no slug is addressed, so missing it
    refuses a real page. The slug is the join key to the earlier slices, the
    display name is not, and the row id is the one identity every shape carries
    — conflating any two of them joins on the wrong thing.
    """
    body = support.page_of(support.one_row(href=href))

    if expected is None:
        with pytest.raises(support.models.ScreenStructureError):
            support.read_table(body)
        return

    _, rows = support.read_table(body)
    company = rows[0].company
    assert (company.slug, company.consolidated) == expected
    assert company.display_name == "Synthetic Holdings 001"
    assert company.data_row_company_id == 770001


@pytest.mark.parametrize(
    ("failing_page", "account", "logout"),
    [(1, False, True), (1, True, False), (2, False, True), (2, True, False)],
)
def test_a_page_that_does_not_prove_a_subscriber_session_is_never_admitted(
    monkeypatch: pytest.MonkeyPatch, failing_page: int, account: bool, logout: bool
) -> None:
    """SL3-06: an expired cookie yields a valid anonymous page, not an error.

    That is the failure mode that is wrong-but-plausible: the run would record a
    logged-out page as subscriber evidence. Both markers are required on *every*
    fetched page, not only the first, because a session can expire mid-walk and
    the later pages are where a partial result looks most complete.
    """
    bodies = support.walk(2)
    bodies[failing_page] = support.results_page(
        failing_page, offered=(1, 2), account=account, logout=logout
    )

    run, _ = support.acquire(monkeypatch, bodies)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "AnonymousPageError"
    assert run.artifact.failure.page_number == failing_page
    assert len(run.artifact.pages) == failing_page - 1
    assert all(row.page_number != failing_page for row in run.artifact.rows)


# --------------------------------------------------------------------------
# Pagination, traversal, serials and schema across pages
# --------------------------------------------------------------------------


def test_only_the_first_page_block_offers_pages_and_the_walk_advances_one_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-07: ``.pagination`` holds two ``options`` blocks and only the first is pages.

    The second is a page-size selector (10 / 25 / 50, with 50 active). Reading
    every ``.options`` anchor yields two active anchors and offers pages 10, 25
    and 50 — under which no multi-page walk can ever terminate. ``Previous`` and
    ``Next`` are anchors too, and both duplicate an adjacent page's href, so the
    offered set comes from numeric anchor *text* and never from an href — every
    href in these fixtures points at page 999 to prove it. The anchor set is
    elided for long results, so the highest visible number is not the last page
    and must never be jumped to; the one gap that refuses is a higher offered
    page with no ``current + 1``. A missing, duplicated, unscoped, unmarked,
    doubly-marked or mispositioned block refuses inside this reader, which owns
    every anchor-bearing failure; acquisition owns only the table-and-pagination
    pairings, including an empty table on a page the walk was told to expect.
    """
    scoped = support.results_page(2, offered=(1, 2, 3, 4))
    assert support.read_pagination(scoped, requested_page_number=2) == (1, 2, 3, 4)

    elided = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=2)),
        support.pagination((1, 2, 3, 4, 12, 13), active=1, next_page=True, elided_after=4),
    )
    assert support.read_pagination(elided, requested_page_number=1) == (1, 2, 3, 4, 12, 13)

    with monkeypatch.context() as patcher:
        run, recorder = support.acquire(patcher, support.walk(3))
        assert [support.requested_page(url) for url in recorder.urls] == [1, 2, 3]
        assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS

    gapped = {number: support.results_page(number, offered=(1, 2, 12)) for number in (1, 2)}
    run, recorder = support.acquire(monkeypatch, gapped)

    assert [support.requested_page(url) for url in recorder.urls] == [1, 2]
    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"

    # Every way the block itself can stop being readable. None of these is a
    # shape the live page has rendered, and each would otherwise be answered by a
    # guess: a walk that guesses its own position re-fetches or skips pages
    # silently, and both look like a smaller result rather than a broken one.
    table = support.results_table(support.NARROW_LABELS, support.rows_for(1, count=2))
    for pagination_html, requested in (
        ("", 1),
        (support.pagination((1, 2), active=1) * 2, 1),
        (support.pagination((1, 2), active=1, scoped=False), 1),
        (support.pagination((1, 2), active=None), 1),
        (support.pagination((1, 2, 3), active=1, also_active=3), 1),
        (support.pagination((1, 2), active=2, previous=True), 1),
    ):
        with pytest.raises(support.models.ScreenPaginationError):
            support.read_pagination(
                support.page(table, pagination_html), requested_page_number=requested
            )

    # An empty table on a page the walk was told to expect: the query had results
    # on page 1, so a rowless page 2 is a changed answer, not a zero result.
    later_empty = support.walk(2)
    later_empty[2] = support.zero_result_page()
    run, _ = support.acquire(monkeypatch, later_empty)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"
    assert run.artifact.failure.page_number == 2
    assert len(run.artifact.pages) == 1


def test_serials_run_globally_from_one_and_no_row_company_id_may_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-08: ``S.No.`` is global, which is the cheapest paging assertion available.

    Page 1 starts at ``1.`` and page 2 at ``51.``, so a paginator that silently
    re-fetched page 1 shows ``1.`` twice and is caught for free.
    ``data-row-company-id`` is unique per page and present on every row shape,
    including the slug-less id route, so a repeat across the walk means the same
    company was admitted twice — the same defect seen from the identity side. A
    zero-result page has neither serials nor ids, so neither check may run.
    """
    fifty = {number: support.live_page(number, offered=(1, 2)) for number in (1, 2)}
    with monkeypatch.context() as patcher:
        run, _ = support.acquire(patcher, fifty)
        rows = run.artifact.rows
        assert len(rows) == 100
        assert rows[50].serial_number == 51
        assert rows[50].page_number == 2
        assert len({row.company.data_row_company_id for row in rows}) == 100

    duplicate_id = support.one_row(serial=9, company_id=770001, href="/company/id/770001/")
    broken_pages = (
        support.rows_for(1),  # page 2 restarts the serials at 1
        support.rows_for(2)[1:],  # page 2 skips serial 9
        (duplicate_id, *support.rows_for(2)[1:]),  # page 2 re-admits a page-1 id
    )
    for broken in broken_pages:
        with monkeypatch.context() as patcher:
            bodies = support.walk(2)
            bodies[2] = support.results_page(2, offered=(1, 2), rows=broken)
            run, _ = support.acquire(patcher, bodies)
            assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
            assert run.artifact.failure is not None
            assert run.artifact.failure.refusal == "ScreenPaginationError"

    empty, _ = support.acquire(
        monkeypatch, {1: support.zero_result_page()}, query=support.EMPTY_QUERY
    )
    assert empty.artifact.outcome is support.models.ScreenOutcome.ZERO_RESULTS
    assert empty.artifact.rows == ()


def test_one_schema_holds_for_every_repeated_header_and_every_later_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL3-09: one equality rule at two scopes, and the scope decides the refusal.

    A header that changes *within* a page means the table itself is malformed; a
    header that changes *between* pages means the two pages answer different
    queries and their rows cannot be concatenated. Both must stop, but a caller
    branching on the refusal class needs to know which one happened.
    """
    drifted = support.single_page(
        support.results_table(
            support.NARROW_LABELS,
            support.rows_for(1, count=2),
            trailing_header=support.header_row(support.WIDE_LABELS),
        )
    )
    with pytest.raises(support.models.ScreenStructureError):
        support.read_table(drifted)

    bodies = support.walk(2)
    bodies[2] = support.results_page(
        2,
        offered=(1, 2),
        labels=support.WIDE_LABELS,
        rows=support.rows_for(2, labels=support.WIDE_LABELS),
    )
    run, _ = support.acquire(monkeypatch, bodies)

    assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
    assert run.artifact.failure is not None
    assert run.artifact.failure.refusal == "ScreenPaginationError"
    assert tuple(column.label for column in run.artifact.columns) == support.NARROW_LABELS


def test_a_query_that_matches_nothing_is_an_answer_and_not_a_structure_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SL3-10: the empty result has no header row and no pagination anchors at all.

    Verified 2026-09-02: HTTP 200, a table carrying all six class tokens with
    zero ``tr`` and zero ``th``, and a ``.pagination`` holding nothing but
    whitespace. The header is the only schema authority on a populated page, so
    a rule requiring one refuses every legitimate empty query; and a rule
    requiring exactly one active pagination anchor makes this outcome
    unreachable on the live surface. Zero results is data, and data must not
    fail closed — while neither pairing below is this shape, and an empty table
    beside real anchors must not be read as it.
    """
    zero = support.zero_result_page()
    assert support.read_pagination(zero, requested_page_number=1) == ()

    with monkeypatch.context() as patcher:
        run, recorder = support.acquire(patcher, {1: zero}, query=support.EMPTY_QUERY)
        assert run.artifact.outcome is support.models.ScreenOutcome.ZERO_RESULTS
        assert run.artifact.columns == ()
        assert run.artifact.rows == ()
        assert len(run.artifact.pages) == 1
        assert run.artifact.pages[0].offered_pages == ()
        assert run.artifact.incomplete_reason is None
        assert run.artifact.failure is None
        assert len(run.documents) == 1
        assert len(recorder.urls) == 1

    anchored_empty = support.page(
        support.empty_table(), support.pagination((1, 2), active=1, next_page=True)
    )
    with monkeypatch.context() as patcher:
        run, _ = support.acquire(patcher, {1: anchored_empty})
        assert run.artifact.outcome is support.models.ScreenOutcome.INCOMPLETE
        assert run.artifact.failure is not None
        assert run.artifact.failure.refusal == "ScreenPaginationError"

    # The mirror image is NOT a refusal, and the frozen plan had it backwards.
    # Screener renders no pagination controls at all when a result fits on one
    # page, so refusing a populated anchor-less page refuses every legitimate
    # 1-to-50-row screen. The table decides the outcome; pagination only decides
    # whether to walk on. Verified live 2026-09-02 against a 7-row query.
    populated_unanchored = support.page(
        support.results_table(support.NARROW_LABELS, support.rows_for(1, count=2)),
        support.empty_pagination(),
    )
    with monkeypatch.context() as patcher:
        run, recorder = support.acquire(patcher, {1: populated_unanchored})
        assert run.artifact.outcome is support.models.ScreenOutcome.RESULTS
        assert run.artifact.failure is None
        assert run.artifact.incomplete_reason is None
        assert len(run.artifact.rows) == 2
        assert run.artifact.pages[0].offered_pages == ()
        # The absent anchor must stop the walk, not merely be tolerated.
        assert len(recorder.urls) == 1

    exit_code, out_dir, _ = support.run_cli(
        monkeypatch, tmp_path, {1: zero}, query=support.EMPTY_QUERY
    )
    assert exit_code == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        support.TSV_HEADER,
        f"zero_results\t1\t0\t0\t{support.artifact_of(out_dir).resolve()}",
    ]
