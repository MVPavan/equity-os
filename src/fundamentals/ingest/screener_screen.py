"""Read and acquire one authenticated raw Screener screen query."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

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
    ScreenQueryError,
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
_SERIAL = re.compile(r"^([1-9][0-9]*)\.$")
_NUMBER = re.compile(r"^[1-9][0-9]*$")


def read_screen_table(
    root: Any, *, fetch: ScreenerDocumentFetch, page_number: int
) -> tuple[tuple[ScreenColumn, ...], tuple[ScreenRow, ...]]:
    """Read a dynamic screen schema and its data rows from one parsed document."""
    tables = root.xpath(_TABLE)
    if len(tables) != 1:
        raise ScreenStructureError("screen requires exactly one data-table")
    rows = tables[0].xpath("./tbody/tr")
    if not rows:
        if tables[0].xpath(".//th"):
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
    """Read only the first direct page-options block, never page-size controls."""
    paginations = root.xpath(_PAGINATION)
    if len(paginations) != 1:
        raise ScreenPaginationError("screen requires exactly one pagination block")
    pagination = paginations[0]
    if not pagination.xpath(".//a"):
        return ()
    options = pagination.xpath(_OPTIONS)
    if not options:
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
    return tuple(number for number, _ in numeric)


def acquire_screen(
    query: str, *, source: ScreenerSessionSource, config: ScreenAcquisitionConfig
) -> ScreenRun:
    """Acquire every offered consecutive page, retaining even an unadmitted body."""
    if not query.strip():
        raise ScreenQueryError("screen query must not be blank")
    documents: list[ScreenerDocumentFetch] = []
    pages: list[ScreenPageMetadata] = []
    all_rows: list[ScreenRow] = []
    expected_columns: tuple[ScreenColumn, ...] | None = None
    identifiers: set[int] = set()
    page = 1
    while True:
        url = screen_url(query, page)
        fetch: ScreenerDocumentFetch | None = None
        try:
            fetch = source.fetch_screen_page(url=url)
            documents.append(fetch)
            root = parse_document(fetch.raw_body.decode("utf-8", errors="replace"))
            assert_logged_in(root)
            columns, rows = read_screen_table(root, fetch=fetch, page_number=page)
            offered = read_screen_pagination(root, requested_page=page)
            if not rows:
                if page != 1 or offered:
                    raise ScreenPaginationError("empty screen table is not the zero-result shape")
                return ScreenRun(
                    artifact=ScreenArtifact(
                        query=query,
                        outcome=ScreenOutcome.ZERO_RESULTS,
                        pages=(_metadata(page, fetch, offered),),
                    ),
                    documents=tuple(documents),
                )
            if not offered:
                raise ScreenPaginationError("populated screen has anchorless pagination")
            if expected_columns is None:
                expected_columns = columns
            elif columns != expected_columns:
                raise ScreenPaginationError("screen schema changed across pages")
            _check_rows(rows, all_rows=all_rows, identifiers=identifiers)
            pages.append(_metadata(page, fetch, offered))
            all_rows.extend(rows)
            if page + 1 in offered:
                if page == config.max_pages:
                    return _incomplete(
                        query,
                        expected_columns,
                        all_rows,
                        pages,
                        documents,
                        f"configured page bound {config.max_pages} stopped before page {page + 1}",
                    )
                page += 1
                continue
            if any(number > page for number in offered):
                raise ScreenPaginationError("screen pagination omits the next offered page")
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
            )


def _row_cells(row: Any) -> list[Any]:
    return list(row.xpath("./th|./td"))


def _columns(cells: list[Any]) -> tuple[ScreenColumn, ...]:
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
    if (
        href is None
        or urlsplit(href).scheme
        or urlsplit(href).netloc
        or urlsplit(href).query
        or urlsplit(href).fragment
    ):
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
    return token in element.get("class", "").split()


def _metadata(
    page: int, fetch: ScreenerDocumentFetch, offered: tuple[int, ...]
) -> ScreenPageMetadata:
    return ScreenPageMetadata(
        page_number=page,
        source_url=fetch.source_url,
        http_status=fetch.http_status,
        offered_pages=offered,
        content_sha256=fetch.content_sha256,
        byte_count=fetch.byte_count,
        fetched_at=fetch.fetched_at,
    )


def _check_rows(
    rows: tuple[ScreenRow, ...], *, all_rows: list[ScreenRow], identifiers: set[int]
) -> None:
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
) -> ScreenRun:
    failure = (
        None
        if error is None
        else ScreenFailure(
            page_number=page or 1,
            source_url=url or "",
            refusal=type(error).__name__,
            detail=str(error),
            content_sha256=content_sha256,
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
