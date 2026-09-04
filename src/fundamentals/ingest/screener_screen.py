"""Read and acquire one authenticated raw Screener screen query."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fundamentals.ingest.screener_financials_tables import html_anchor, normalize_text, read_number
from fundamentals.ingest.screener_screen_models import (
    ScreenAcquisitionConfig,
    ScreenArtifact,
    ScreenCell,
    ScreenColumn,
    ScreenCompany,
    ScreenFailure,
    ScreenOutcome,
    ScreenPageMetadata,
    ScreenPaginationError,
    ScreenRow,
    ScreenRun,
    ScreenStructureError,
    screen_url,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    SOURCE_ID,
    ScreenerDocumentFetch,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import assert_logged_in, parse_document

_TABLE = ".//table[contains(concat(' ', normalize-space(@class), ' '), ' data-table ')]"
_PAGINATION = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' pagination ')]"
_OPTIONS = "./div[contains(concat(' ', normalize-space(@class), ' '), ' options ')]"
_NESTED_OPTIONS_ANCHORS = (
    ".//div[contains(concat(' ', normalize-space(@class), ' '), ' options ')]//a"
)
_PAGE_INFO = ".//*[@data-page-info]"
_SERIAL = re.compile(r"^([1-9][0-9]*)\.$")
_NUMBER = re.compile(r"^[1-9][0-9]*$")
_PAGE_INFO_TEXT = re.compile(
    r"^\s*(?P<total>[0-9]+)\s+results\s+found\s*:\s*"
    r"showing\s+page\s+(?P<page>[1-9][0-9]*)\s+of\s+(?P<pages>[1-9][0-9]*)\s*$",
    re.IGNORECASE,
)
_PAGE_SIZE_ONLY_AFTER_FIRST_PAGE = "screen page-size-only pagination is only valid on page one"
_UNFETCHED_OFFERED_PAGE = "screen pagination stopped before an earlier offered page"
_UNADMITTED_SCREEN_ROW = "screen table has a row outside tbody"
_ANCHORLESS_PAGINATION_HAS_ELEMENT_CHILDREN = "anchor-less screen pagination has element children"
_MISSING_PAGE_INFO = "screen page has no data-page-info completeness oracle"
_INVALID_PAGE_INFO = "screen data-page-info completeness oracle is malformed"
_PAGE_INFO_CHANGED = (
    "screen data-page-info changed across pages: page {page} states total {total} over "
    "{pages} pages, the walk started on total {expected_total} over {expected_pages} pages"
)
_PAGE_INFO_WRONG_PAGE = "screen data-page-info names page {stated}, requested page {requested}"
_PAGE_INFO_INCOMPLETE = "screen admitted rows or pages disagree with data-page-info"
_PAGE_BOUND_REASON = "configured page bound {bound} stopped at {rows} of stated total {total}"
_NEXT = "Next"
_PAGE_QUERY_PARAMETER = "page"
_LIMIT_QUERY_PARAMETER = "limit"
_FIRST_PAGE = "1"
_HREF_ATTRIBUTE = "href"
_EMPTY_HREF = ""
_PAGE_INFO_TOTAL_GROUP = "total"
_PAGE_INFO_PAGE_GROUP = "page"
_PAGE_INFO_PAGES_GROUP = "pages"
_NEXT_PAGE_NOT_OFFERED = "screen Next page is absent from numeric offers"
_EXCEPTION_DETAIL = "{refusal}: {detail}"


def read_screen_table(
    root: Any, *, fetch: ScreenerDocumentFetch, page_number: int
) -> tuple[tuple[ScreenColumn, ...], tuple[ScreenRow, ...]]:
    """Read a dynamic screen schema and its data rows from one parsed document."""
    tables = root.xpath(_TABLE)
    if len(tables) != 1:
        raise ScreenStructureError("screen requires exactly one data-table")
    table = tables[0]
    rows = table.xpath("./tbody/tr")
    if len(rows) != len(table.xpath(".//tr")):
        raise ScreenStructureError(_UNADMITTED_SCREEN_ROW)
    if not rows:
        if table.xpath(".//th"):
            raise ScreenStructureError("rowless screen table must be headerless")
        return (), ()
    first = _row_cells(rows[0])
    if not first or any(cell.tag != "th" for cell in first):
        raise ScreenStructureError("first screen row must be an all-th header")
    columns = _columns(first)
    parsed: list[ScreenRow] = []
    for element in rows:
        cells = _row_cells(element)
        if not cells or {cell.tag for cell in cells} not in ({"th"}, {"td"}):
            raise ScreenStructureError("screen row must be all th or all td")
        if cells[0].tag == "th":
            if _columns(cells) != columns:
                raise ScreenStructureError("repeated screen header changed")
            continue
        if len(cells) != len(columns):
            raise ScreenStructureError("screen data row width differs from header")
        parsed.append(
            _screen_row(
                cells, columns=columns, fetch=fetch, page_number=page_number, element=element
            )
        )
    if not parsed:
        raise ScreenStructureError("screen header has no data rows")
    return columns, tuple(parsed)


def read_screen_pagination(root: Any, *, requested_page: int) -> tuple[int, ...]:
    """Read only the first direct page-options block, never page-size controls.

    Nested selector hrefs are parsed only to classify a single-page result; this
    reader never follows them, so the no-following rule remains unchanged.
    """
    paginations = root.xpath(_PAGINATION)
    if len(paginations) != 1:
        raise ScreenPaginationError("screen requires exactly one pagination block")
    pagination = paginations[0]
    anchors = pagination.xpath(".//a")
    if not anchors:
        if pagination.xpath("./*"):
            raise ScreenPaginationError(_ANCHORLESS_PAGINATION_HAS_ELEMENT_CHILDREN)
        return ()
    options = pagination.xpath(_OPTIONS)
    if not options:
        # The nested anchors are by construction a subset of ``anchors``, so equal
        # node-set sizes say every anchor here is inside a nested options block —
        # the same question the removed identity check asked, without depending on
        # lxml handing back the same element proxy from a second xpath call.
        nested_anchors = pagination.xpath(_NESTED_OPTIONS_ANCHORS)
        if len(nested_anchors) == len(anchors) and all(
            _LIMIT_QUERY_PARAMETER in query
            and all(number == _FIRST_PAGE for number in query.get(_PAGE_QUERY_PARAMETER, ()))
            for query in (
                parse_qs(urlsplit(anchor.get(_HREF_ATTRIBUTE, _EMPTY_HREF)).query)
                for anchor in anchors
            )
        ):
            if requested_page != 1:
                raise ScreenPaginationError(_PAGE_SIZE_ONLY_AFTER_FIRST_PAGE)
            return ()
        raise ScreenPaginationError("screen pagination has no direct options block")
    anchors = options[0].xpath(".//a")
    numeric: list[tuple[int, Any]] = []
    for anchor in anchors:
        text = normalize_text(anchor.text_content())
        if _NUMBER.fullmatch(text):
            numeric.append((int(text), anchor))
    active = [number for number, anchor in numeric if _has_class(anchor, "active")]
    if len(active) != 1 or active[0] != requested_page:
        raise ScreenPaginationError("screen pagination has no matching active page")
    next_pages = [
        int(values[0])
        for anchor in anchors
        if normalize_text(anchor.text_content()) == _NEXT
        for values in [
            parse_qs(urlsplit(anchor.get(_HREF_ATTRIBUTE, _EMPTY_HREF)).query).get(
                _PAGE_QUERY_PARAMETER, ()
            )
        ]
        if len(values) == 1 and _NUMBER.fullmatch(values[0])
    ]
    if requested_page + 1 in next_pages and requested_page + 1 not in {
        number for number, _ in numeric
    }:
        raise ScreenPaginationError(_NEXT_PAGE_NOT_OFFERED)
    return tuple(number for number, _ in numeric)


def _read_page_info(root: Any) -> tuple[int, int, int]:
    """Read the source's completeness claim without relying on presentation markup.

    ``data-page-info`` is the semantic hook that survives the styling changes
    that made pagination inference unsafe as a completeness guarantee.
    """
    page_info = root.xpath(_PAGE_INFO)
    if len(page_info) != 1:
        raise ScreenStructureError(_MISSING_PAGE_INFO)
    match = _PAGE_INFO_TEXT.fullmatch(page_info[0].text_content())
    if match is None:
        raise ScreenStructureError(_INVALID_PAGE_INFO)
    total = int(match.group(_PAGE_INFO_TOTAL_GROUP))
    page = int(match.group(_PAGE_INFO_PAGE_GROUP))
    pages = int(match.group(_PAGE_INFO_PAGES_GROUP))
    if page > pages:
        raise ScreenStructureError(_INVALID_PAGE_INFO)
    return total, page, pages


def _require_complete(total: int, pages: int, *, row_count: int, page_count: int) -> None:
    """Refuse publication when admitted evidence disagrees with the page's claim.

    Pagination directs the walk, but only the independently stated totals prove
    that the walk captured the result set the source says it served.
    """
    if row_count != total or page_count != pages:
        raise ScreenPaginationError(_PAGE_INFO_INCOMPLETE)


def acquire_screen(
    query: str, *, source: ScreenerSessionSource, config: ScreenAcquisitionConfig
) -> ScreenRun:
    """Acquire every offered consecutive page, retaining even an unadmitted body."""
    documents: list[ScreenerDocumentFetch] = []
    pages: list[ScreenPageMetadata] = []
    all_rows: list[ScreenRow] = []
    expected_columns: tuple[ScreenColumn, ...] | None = None
    expected_page_info: tuple[int, int] | None = None
    identifiers: set[int] = set()
    highest_offered_page = 1
    page = 1
    while True:
        url = screen_url(query, page)
        fetch: ScreenerDocumentFetch | None = None
        stated: tuple[int, int] | None = None
        try:
            fetch = source.fetch_screen_page(url=url)
            documents.append(fetch)
            root = parse_document(fetch.raw_body.decode("utf-8", errors="replace"))
            assert_logged_in(root)
            stated_total, stated_page, stated_pages = _read_page_info(root)
            stated = (stated_total, stated_pages)
            if stated_page != page:
                raise ScreenPaginationError(
                    _PAGE_INFO_WRONG_PAGE.format(stated=stated_page, requested=page)
                )
            if expected_page_info is None:
                expected_page_info = stated
            elif expected_page_info != stated:
                raise ScreenPaginationError(
                    _PAGE_INFO_CHANGED.format(
                        page=page,
                        total=stated_total,
                        pages=stated_pages,
                        expected_total=expected_page_info[0],
                        expected_pages=expected_page_info[1],
                    )
                )
            columns, rows = read_screen_table(root, fetch=fetch, page_number=page)
            offered = read_screen_pagination(root, requested_page=page)
            highest_offered_page = max((highest_offered_page, *offered))
            if not rows:
                if page != 1 or offered:
                    raise ScreenPaginationError("empty screen table is not the zero-result shape")
                _require_complete(stated_total, stated_pages, row_count=0, page_count=1)
                return ScreenRun(
                    artifact=ScreenArtifact(
                        query=query,
                        outcome=ScreenOutcome.ZERO_RESULTS,
                        pages=(
                            _metadata(
                                page,
                                fetch,
                                offered,
                                stated_total=stated_total,
                                stated_pages=stated_pages,
                            ),
                        ),
                    ),
                    documents=tuple(documents),
                )
            if expected_columns is None:
                expected_columns = columns
            elif columns != expected_columns:
                raise ScreenPaginationError("screen schema changed across pages")
            _check_rows(rows, all_rows=all_rows, identifiers=identifiers)
            pages.append(
                _metadata(
                    page,
                    fetch,
                    offered,
                    stated_total=stated_total,
                    stated_pages=stated_pages,
                )
            )
            all_rows.extend(rows)
            if page == config.max_pages and stated_pages > page:
                return _incomplete(
                    query,
                    expected_columns,
                    all_rows,
                    pages,
                    documents,
                    _PAGE_BOUND_REASON.format(
                        bound=config.max_pages, rows=len(all_rows), total=stated_total
                    ),
                )
            if page + 1 in offered:
                page += 1
                continue
            if highest_offered_page > page:
                raise ScreenPaginationError(_UNFETCHED_OFFERED_PAGE)
            _require_complete(
                stated_total, stated_pages, row_count=len(all_rows), page_count=len(pages)
            )
            return ScreenRun(
                artifact=ScreenArtifact(
                    query=query,
                    outcome=ScreenOutcome.RESULTS,
                    columns=expected_columns or (),
                    rows=tuple(all_rows),
                    pages=tuple(pages),
                ),
                documents=tuple(documents),
            )
        except ScreenerSessionError as error:
            if not documents:
                raise
            return _incomplete(
                query,
                expected_columns,
                all_rows,
                pages,
                documents,
                str(error),
                page=page,
                url=url,
                error=error,
                content_sha256=None if fetch is None else fetch.content_sha256,
                stated=stated,
            )
        # Once a body is retained, no exception may discard it. Every refusal this
        # reader raises is a ScreenerSessionError and was caught above, so anything
        # arriving here is an unexpected type and is recorded under its own name: a
        # consumer filtering on refusal must not read a transport read error as a
        # malformed page.
        except Exception as error:
            if not documents:
                raise
            return _incomplete(
                query,
                expected_columns,
                all_rows,
                pages,
                documents,
                _EXCEPTION_DETAIL.format(refusal=type(error).__name__, detail=str(error)),
                page=page,
                url=url,
                error=error,
                content_sha256=None if fetch is None else fetch.content_sha256,
                stated=stated,
            )


def _row_cells(row: Any) -> list[Any]:
    """Return a row's own cells, header or data, without descending into nested tables."""
    return list(row.xpath("./th|./td"))


def _columns(cells: list[Any]) -> tuple[ScreenColumn, ...]:
    """Read the header row, which is the only schema authority for this query.

    The column set is query-dependent, so only the two fixed leading labels are
    asserted; the rest are accepted by name as published, and merely required to
    be non-blank.
    """
    labels = tuple(normalize_text(cell.text_content()) for cell in cells)
    if len(labels) < 3 or labels[:2] != ("S.No.", "Name") or any(not label for label in labels[2:]):
        raise ScreenStructureError("screen header is not an admitted schema")
    return tuple(ScreenColumn(index=index, label=label) for index, label in enumerate(labels))


def _screen_row(
    cells: list[Any],
    *,
    columns: tuple[ScreenColumn, ...],
    fetch: ScreenerDocumentFetch,
    page_number: int,
    element: Any,
) -> ScreenRow:
    """Read one data row into a typed row, anchoring every cell to its source.

    Every failure here is a structure error rather than a dropped row: a row
    this reader cannot fully account for must not be silently omitted from a
    result the caller will treat as complete.
    """
    serial_match = _SERIAL.fullmatch(normalize_text(cells[0].text_content()))
    if serial_match is None:
        raise ScreenStructureError("screen serial is malformed")
    row_id_raw = element.get("data-row-company-id")
    if row_id_raw is None or not _NUMBER.fullmatch(row_id_raw):
        raise ScreenStructureError("screen row company id is malformed")
    row_id = int(row_id_raw)
    links = cells[1].xpath(".//a")
    if len(links) != 1:
        raise ScreenStructureError("screen company cell requires exactly one link")
    name = normalize_text(links[0].text_content())
    if not name:
        raise ScreenStructureError("screen company name is blank")
    company = _company(links[0].get("href"), name=name, row_id=row_id)
    serial = int(serial_match.group(1))
    values: list[ScreenCell] = []
    for index, cell in enumerate(cells[2:], start=2):
        raw = normalize_text(cell.text_content())
        value = None if not raw else read_number(raw)[0]
        values.append(
            ScreenCell(
                column_index=index,
                value=value,
                raw_text=raw,
                provenance=html_anchor(
                    source_id=SOURCE_ID,
                    file_sha256=fetch.content_sha256,
                    retrieved_at=fetch.fetched_at,
                    table_id="screen-results",
                    row_path=f"row[{serial}]",
                    column_index=index,
                    column_label=columns[index].label,
                ),
            )
        )
    return ScreenRow(
        page_number=page_number, serial_number=serial, company=company, cells=tuple(values)
    )


def _company(href: str | None, *, name: str, row_id: int) -> ScreenCompany:
    """Resolve the company cell's link into an identity, admitting three link shapes.

    The live surface renders ``/company/<slug>/``, ``/company/<slug>/consolidated/``
    and ``/company/id/<numeric-id>/``. The id-routed shape must agree with the
    row's own ``data-row-company-id``, since two disagreeing identifiers on one
    row mean the page is not what this reader thinks it is.
    """
    if href is None:
        raise ScreenStructureError("screen company link must be a clean relative URL")
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ScreenStructureError("screen company link must be a clean relative URL")
    segments = href.split("/")
    if len(segments) < 2 or segments[0] != "" or segments[-1] != "" or segments[1] != "company":
        raise ScreenStructureError("screen company link has an unsupported path")
    route = segments[2:-1]
    if (
        len(route) == 2
        and route[0] == "id"
        and _NUMBER.fullmatch(route[1])
        and int(route[1]) == row_id
    ):
        return ScreenCompany(
            slug=None, display_name=name, data_row_company_id=row_id, consolidated=False
        )
    if len(route) == 1 and route[0] and route[0] != "id":
        return ScreenCompany(
            slug=route[0], display_name=name, data_row_company_id=row_id, consolidated=False
        )
    if len(route) == 2 and route[0] and route[0] != "id" and route[1] == "consolidated":
        return ScreenCompany(
            slug=route[0], display_name=name, data_row_company_id=row_id, consolidated=True
        )
    raise ScreenStructureError("screen company link has an unsupported path")


def _has_class(element: Any, token: str) -> bool:
    """Test one whitespace-separated class token, never a substring of the attribute."""
    return token in element.get("class", "").split()


def _metadata(
    page: int,
    fetch: ScreenerDocumentFetch,
    offered: tuple[int, ...],
    *,
    stated_total: int,
    stated_pages: int,
) -> ScreenPageMetadata:
    """Record one fetch's provenance and its own completeness claim."""
    return ScreenPageMetadata(
        page_number=page,
        source_url=fetch.source_url,
        http_status=fetch.http_status,
        stated_total=stated_total,
        stated_pages=stated_pages,
        offered_pages=offered,
        content_sha256=fetch.content_sha256,
        byte_count=fetch.byte_count,
        fetched_at=fetch.fetched_at,
    )


def _check_rows(
    rows: tuple[ScreenRow, ...], *, all_rows: list[ScreenRow], identifiers: set[int]
) -> None:
    """Refuse a walk whose serials skip or restart, or that repeats a company.

    Both are cross-page checks against the run so far: they are how a page
    served out of order, or served twice, is caught. ``identifiers`` is mutated
    as rows are admitted.
    """
    expected = len(all_rows) + 1
    for row in rows:
        if row.serial_number != expected or row.company.data_row_company_id in identifiers:
            raise ScreenPaginationError("screen serials or company ids are not globally continuous")
        identifiers.add(row.company.data_row_company_id)
        expected += 1


def _incomplete(
    query: str,
    columns: tuple[ScreenColumn, ...] | None,
    rows: list[ScreenRow],
    pages: list[ScreenPageMetadata],
    documents: list[ScreenerDocumentFetch],
    reason: str,
    *,
    page: int | None = None,
    url: str | None = None,
    error: Exception | None = None,
    content_sha256: str | None = None,
    stated: tuple[int, int] | None = None,
) -> ScreenRun:
    """Close a walk that stopped short, keeping everything it did prove.

    The pages already admitted, their rows, and every retained body stay in the
    run; only the outcome changes. A refused page's response is evidence, and
    discarding it would make the refusal unexaminable. ``stated`` is the
    completeness claim of the page the walk refused on, admitted or not.
    """
    failure = (
        None
        if error is None
        else ScreenFailure(
            page_number=page or 1,
            source_url=url or "",
            refusal=type(error).__name__,
            detail=str(error),
            content_sha256=content_sha256,
            stated_total=None if stated is None else stated[0],
            stated_pages=None if stated is None else stated[1],
        )
    )
    return ScreenRun(
        artifact=ScreenArtifact(
            query=query,
            outcome=ScreenOutcome.INCOMPLETE,
            columns=columns or (),
            rows=tuple(rows),
            pages=tuple(pages),
            incomplete_reason=reason,
            failure=failure,
        ),
        documents=tuple(documents),
    )
