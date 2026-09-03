"""Read and acquire one authenticated Screener watchlist beside its CSV export.

The page states no total of its own, so the Slice 3 completeness oracle does not
exist here. What exists instead is two independent server renderings of one list:
the HTML table and the CSV its own export form produces. This module fetches both
— the GET authorises the POST, which is why this is one seam and not two — and
refuses to publish a row unless the two agree on membership, on the column
correspondence the page states, on identity and on every value. The comparison
itself lives in :mod:`fundamentals.ingest.screener_watchlist_crosscheck`; what
is here is the two readers, the page evidence and the acquisition around them.
"""

from __future__ import annotations

import csv
import email.message
import io
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from pydantic import SecretStr

from fundamentals.ingest.screener_financials_tables import normalize_text
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    SESSION_COOKIE_NAME,
    ScreenerBlockedError,
    ScreenerDocumentFetch,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import assert_logged_in, parse_document
from fundamentals.ingest.screener_watchlist_crosscheck import cross_check
from fundamentals.ingest.screener_watchlist_models import (
    CREATE_WATCHLIST_PATH,
    CSRF_COOKIE_NAME,
    CSRF_FORM_FIELD,
    EXPORT_ENCODING,
    EXPORT_MEDIA_TYPE,
    EXPORT_PATH,
    NEXT_PARAMETER,
    STOCKS_EDITOR_PATH,
    SUBLIST_ID_PARAMETER,
    WatchlistArtifact,
    WatchlistCrossCheck,
    WatchlistCrossCheckError,
    WatchlistExportError,
    WatchlistFailure,
    WatchlistOutcome,
    WatchlistPageError,
    WatchlistPageEvidence,
    WatchlistRun,
    WatchlistStructureError,
    WatchlistTable,
    WatchlistTableRow,
    watchlist_url,
)

_RESULTS_CONTAINER = ".//*[@data-page-results]"
_TABLE = ".//table"
_TBODY_ROWS = "./tbody/tr"
_ALL_ROWS = ".//tr"
_ROW_CELLS = "./th|./td"
_PAGINATION = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' pagination ')]"
_PAGE_INFO = ".//*[@data-page-info]"
_FORMS = ".//form"
_NAMED_INPUTS = ".//input[@name]"
# Scoped to the selector's own menu, never to `dropdown-content` alone: the page
# carries several of those and only this one lists watchlists. Matching them all
# still finds the right selected name, so the failure is silent — the artifact
# looks correct while the advisory names the site's nav copy as skipped lists.
_DROPDOWN_ENTRIES = (
    ".//*[contains(concat(' ', normalize-space(@class), ' '), ' dropdown-watchlist ')]"
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' dropdown-content ')]//li"
)
_SELECTED_ICON = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' icon-ok-circled-1 ')]"
_ENTRY_LINKS = ".//a"

_ROW_ID_ATTRIBUTE = "data-row-company-id"
_TOOLTIP_ATTRIBUTE = "data-tooltip"
_COLSPAN_ATTRIBUTE = "colspan"
_HREF_ATTRIBUTE = "href"
_ACTION_ATTRIBUTE = "action"
_NAME_ATTRIBUTE = "name"
_VALUE_ATTRIBUTE = "value"

_COMPANY_SEGMENT = "company"
_ID_SEGMENT = "id"
_CONSOLIDATED_SEGMENT = "consolidated"

_SERIAL = re.compile(r"^([1-9][0-9]*)\.$")
_NUMBER = re.compile(r"^[1-9][0-9]*$")
_WATCHLIST_NEXT = re.compile(r"^/watchlist/([1-9][0-9]*)/$")

_ONE_CONTAINER = "watchlist page must render exactly one results container"
_ONE_TABLE = "watchlist results container must hold exactly one table"
_UNADMITTED_ROW = "watchlist table has a row outside tbody"
_UNCLASSIFIABLE_ROW = "watchlist row is neither an all-th header nor an all-td member row"
_ROW_BEFORE_HEADER = "watchlist member row appears before any header row"
_HEADER_CHANGED = "repeated watchlist header declares a different column sequence"
_NARROW_HEADER = "watchlist header must declare a serial, a name and at least one value column"
_IDENTITY_HEADER_TOOLTIP = "watchlist serial or name header carries a value column's tooltip"
_VALUE_HEADER_TOOLTIP = "watchlist value header declares no data-tooltip metric name"
_BAD_COLSPAN = "watchlist header colspan is not a positive integer"
_COLSPAN_DISAGREES = "watchlist header spans {span} columns but a member row carries {cells} cells"
_VALUE_COUNT_DISAGREES = (
    "watchlist header declares {labels} value column(s) but a member row carries {values} value "
    "cell(s); the colspan sum agreeing means the widths were balanced elsewhere"
)
_BAD_SERIAL = "watchlist serial cell is malformed"
_SERIALS_NOT_CONTIGUOUS = "watchlist serials are not exactly 1..N in rendered order"
_BAD_ROW_ID = "watchlist row company id is malformed"
_REPEATED_ROW_ID = "watchlist renders the same company id on more than one row"
_ONE_COMPANY_LINK = "watchlist company cell requires exactly one link"
_BLANK_COMPANY_NAME = "watchlist company name is blank"
_UNSUPPORTED_LINK = "watchlist company link has an unsupported path"
_NO_HEADER = "watchlist table renders no header row"
_NO_MEMBER_ROWS = "watchlist table renders no member rows, which no evidence tells from a shell"
_PAGINATED = "watchlist page renders a pagination control this reader would silently truncate"
_ONE_EXPORT_FORM = "watchlist page must render exactly one export form, not {count}"
_ONE_FORM_TOKEN = "watchlist export form must carry exactly one non-empty {field} field"
_ID_NOT_CONFIRMED = "watchlist page reports list {seen!r} but list {requested} was requested"
_AMBIGUOUS_SELECTION = "watchlist selector marks more than one list as the selected one"

_NO_CSRF_COOKIE = "the page set no csrftoken cookie; the form token is never used as one"
_UNREADABLE_CSRF_COOKIE = (
    "the page sent a csrftoken Set-Cookie header this reader could not read as a name=value pair"
)
_EMPTY_CSRF_COOKIE = (
    "the page sent an empty csrftoken cookie, which is how the session's token is deleted"
)
_CONTROL_IN_COOKIE_NAME = "the page set a cookie whose name carries a control character"
_CONTROL_IN_COOKIE_VALUE = "the page set a {name} cookie whose value carries a control character"
_SESSION_REISSUED = "the page re-issued the session cookie, which this adapter did not mint"
_EXPORT_REFUSED = (
    "screener refused the export POST ({error}): an HTTP 403 here may be a stale CSRF token "
    "rather than a terminal block on the account, so re-fetch the page before concluding "
    "either; any other terminal status is not a stale-token candidate"
)

_BAD_EXPORT_STATUS = "watchlist export returned HTTP {status}, not 200"
_BAD_EXPORT_MEDIA_TYPE = "watchlist export media type is {media_type!r}, not {expected!r}"
_NO_EXPORT_FILENAME = "watchlist export carries no Content-Disposition filename"
_EMPTY_EXPORT = "watchlist export carries no header record"
_RAGGED_EXPORT = "watchlist export record {position} has {width} fields, not {expected}"


def read_watchlist_table(root: Any) -> WatchlistTable:
    """Read the rendered member table, admitting every ``tr`` or refusing the page.

    The header repeats inside one ``tbody`` rather than sitting in a ``thead``, so
    a reader taking the first row as the only header admits every later repeat as
    a company. ``S.No.`` spans the unlabelled notebook column, so what must hold
    is the colspan-expanded header width against the member row's cell count —
    never two pinned numbers, since the column set is the user's configuration.

    That total is not sufficient on its own: a wider ``S.No.`` span beside one
    extra ``td`` keeps the two totals equal while the row carries a value no
    header names, so the value counts are checked as well.
    """
    table = _one_table(root)
    elements = table.xpath(_TBODY_ROWS)
    if len(elements) != len(table.xpath(_ALL_ROWS)):
        raise WatchlistStructureError(_UNADMITTED_ROW)
    header: tuple[tuple[str, ...], tuple[str, ...], int] | None = None
    rows: list[WatchlistTableRow] = []
    for element in elements:
        cells = element.xpath(_ROW_CELLS)
        tags = {cell.tag for cell in cells}
        row_id_raw = element.get(_ROW_ID_ATTRIBUTE)
        if row_id_raw is None:
            if not cells or tags != {"th"}:
                raise WatchlistStructureError(_UNCLASSIFIABLE_ROW)
            declared = _read_header(cells)
            if header is None:
                header = declared
            elif declared != header:
                raise WatchlistStructureError(_HEADER_CHANGED)
            continue
        if not cells or tags != {"td"}:
            raise WatchlistStructureError(_UNCLASSIFIABLE_ROW)
        if header is None:
            raise WatchlistStructureError(_ROW_BEFORE_HEADER)
        if header[2] != len(cells):
            raise WatchlistStructureError(
                _COLSPAN_DISAGREES.format(span=header[2], cells=len(cells))
            )
        member = _member_row(cells, row_id_raw=row_id_raw)
        if len(member.values) != len(header[0]):
            raise WatchlistStructureError(
                _VALUE_COUNT_DISAGREES.format(labels=len(header[0]), values=len(member.values))
            )
        rows.append(member)
    if header is None:
        raise WatchlistStructureError(_NO_HEADER)
    if not rows:
        raise WatchlistStructureError(_NO_MEMBER_ROWS)
    if tuple(row.serial_number for row in rows) != tuple(range(1, len(rows) + 1)):
        raise WatchlistStructureError(_SERIALS_NOT_CONTIGUOUS)
    if len({row.data_row_company_id for row in rows}) != len(rows):
        raise WatchlistStructureError(_REPEATED_ROW_ID)
    return WatchlistTable(value_labels=header[0], visible_labels=header[1], rows=tuple(rows))


def read_watchlist_page(root: Any) -> WatchlistPageEvidence:
    """Read what the page supplies about the list and about how to export it.

    The export goes to the action of the one export form the page renders, read
    verbatim: the two page shapes carry different actions and the selector
    exposes no id, so a constructed URL would be one the page never offered. The
    id is provenance, from that action's ``sublist_id`` or the stocks link.
    """
    if root.xpath(_PAGINATION) or root.xpath(_PAGE_INFO):
        raise WatchlistPageError(_PAGINATED)
    action, token = _export_form(root)
    selected, others = _dropdown(root)
    return WatchlistPageEvidence(
        export_action=action,
        csrf_form_token=SecretStr(token),
        watchlist_id=_watchlist_id(action, root),
        watchlist_name=selected,
        other_watchlist_names=others,
    )


def read_watchlist_export(
    raw: bytes,
    *,
    http_status: int,
    content_type: str | None,
    content_disposition: str | None,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Read one export response, after it has proved it is the export.

    A 200 that is a login page parses as a one-column CSV of markup, so the media
    type and the attachment filename are checked before a byte is parsed. The
    body is decoded with ``utf-8-sig`` so a BOM never becomes part of the first
    header label, and a ragged record refuses rather than shifting every later
    field under the wrong label.
    """
    if http_status != 200:
        raise WatchlistExportError(_BAD_EXPORT_STATUS.format(status=http_status))
    media_type = None if content_type is None else content_type.split(";", 1)[0].strip().lower()
    if media_type != EXPORT_MEDIA_TYPE:
        raise WatchlistExportError(
            _BAD_EXPORT_MEDIA_TYPE.format(media_type=media_type, expected=EXPORT_MEDIA_TYPE)
        )
    if not _export_filename(content_disposition):
        raise WatchlistExportError(_NO_EXPORT_FILENAME)
    parsed = list(csv.reader(io.StringIO(raw.decode(EXPORT_ENCODING))))
    if not parsed:
        raise WatchlistExportError(_EMPTY_EXPORT)
    header = tuple(parsed[0])
    records: list[tuple[str, ...]] = []
    for position, record in enumerate(parsed[1:], start=1):
        if len(record) != len(header):
            raise WatchlistExportError(
                _RAGGED_EXPORT.format(position=position, width=len(record), expected=len(header))
            )
        records.append(tuple(record))
    return header, tuple(records)


def acquire_watchlist(
    *, source: ScreenerSessionSource, watchlist_id: int | None = None
) -> WatchlistRun:
    """Acquire one watchlist and prove cross-render consistency at fetch time.

    Two requests, and only two: a GET of the page, then a POST of the export form
    that page embeds. The GET is what authorises the POST — it carries the CSRF
    cookie and the form token — so the export is not independently addressable.

    The published artifact claims only that the page and the export agreed, when
    they were fetched, on membership, on the column correspondence the page
    states in ``data-tooltip``, on the exchange code behind each slug, and on
    every value cell. It is never a claim that the list contains nothing else: a
    cap or a stale snapshot shared by both renderings is invisible here, and a
    disagreement is reported once, with both raw strings, and never retried. The
    remaining identity fields are the export's word alone — see
    :class:`~fundamentals.ingest.screener_watchlist_models.WatchlistArtifact`.
    """
    documents: list[ScreenerDocumentFetch] = []
    page_url = watchlist_url(watchlist_id)
    attempted = page_url
    evidence: WatchlistPageEvidence | None = None
    # Every secret this run learns, so the retention handler can strip them from
    # a message it did not write. The session cookie is not here: the source
    # holds it and redacts it itself, without ever handing it out.
    secrets: list[str] = []
    try:
        page_fetch, set_cookies = source.fetch_navigation(url=page_url)
        documents.append(page_fetch)
        root = parse_document(page_fetch.raw_body.decode("utf-8", errors="replace"))
        assert_logged_in(root)
        evidence = read_watchlist_page(root)
        secrets.append(evidence.csrf_form_token.get_secret_value())
        if watchlist_id is not None and evidence.watchlist_id != watchlist_id:
            raise WatchlistPageError(
                _ID_NOT_CONFIRMED.format(seen=evidence.watchlist_id, requested=watchlist_id)
            )
        table = read_watchlist_table(root)
        cookies = _cookie_state(set_cookies)
        secrets.append(cookies[CSRF_COOKIE_NAME])
        attempted = urljoin(page_url, evidence.export_action)
        try:
            export_fetch, content_type, content_disposition = source.post_form(
                url=attempted,
                fields={CSRF_FORM_FIELD: evidence.csrf_form_token.get_secret_value()},
                referer=page_url,
                cookies=cookies,
            )
        except ScreenerBlockedError as error:
            raise WatchlistExportError(_EXPORT_REFUSED.format(error=error)) from error
        documents.append(export_fetch)
        header, records = read_watchlist_export(
            export_fetch.raw_body,
            http_status=export_fetch.http_status,
            content_type=content_type,
            content_disposition=content_disposition,
        )
        record, reason, columns, rows = cross_check(
            table,
            header=header,
            records=records,
            page_fetch=page_fetch,
            export_fetch=export_fetch,
            content_type=content_type,
            content_disposition=content_disposition,
        )
        if reason is not None:
            return _incomplete(
                evidence,
                documents,
                refusal=WatchlistCrossCheckError.__name__,
                detail=reason,
                source_url=attempted,
                content_sha256=export_fetch.content_sha256,
                cross_check=record,
            )
        return WatchlistRun(
            artifact=WatchlistArtifact(
                watchlist_id=evidence.watchlist_id,
                watchlist_name=evidence.watchlist_name,
                other_watchlist_names=evidence.other_watchlist_names,
                outcome=WatchlistOutcome.RESULTS,
                columns=columns,
                rows=rows,
                cross_check=record,
            ),
            documents=tuple(documents),
        )
    # Once a body is retained, no exception may discard it: the response that was
    # refused is usually the most useful thing the run produced. ``BaseException``
    # is deliberately not caught — cancellation and interrupts must propagate.
    #
    # No untyped exception's message is persisted as written. ``http.client``
    # raises a ``ValueError`` quoting the whole outbound ``Cookie`` header when a
    # cookie is malformed, and that message would otherwise reach the artifact
    # and stderr carrying both authentication secrets. Enumerating which
    # exception types can do that is how this was missed once already, so the
    # type is recorded and the secrets are removed from the message instead.
    except Exception as error:
        if not documents:
            raise
        refusal = type(error).__name__
        written = str(error) if isinstance(error, ScreenerSessionError) else f"{refusal}: {error}"
        detail = source.redact(written, extra=secrets)
        return _incomplete(
            evidence,
            documents,
            refusal=refusal,
            detail=detail,
            source_url=attempted,
            content_sha256=documents[-1].content_sha256,
        )


def _one_table(root: Any) -> Any:
    """Return the single results table, scoped to the single results container."""
    containers = root.xpath(_RESULTS_CONTAINER)
    if len(containers) != 1:
        raise WatchlistStructureError(_ONE_CONTAINER)
    tables = containers[0].xpath(_TABLE)
    if len(tables) != 1:
        raise WatchlistStructureError(_ONE_TABLE)
    return tables[0]


def _read_header(cells: list[Any]) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    """Read one header row as ``(tooltips, visible labels, colspan-expanded width)``.

    Value positions are structural — every cell after the serial and the name —
    so a tooltip where the page renders none can only refuse, never shift the map.
    """
    if len(cells) < 3:
        raise WatchlistStructureError(_NARROW_HEADER)
    if any(cell.get(_TOOLTIP_ATTRIBUTE) is not None for cell in cells[:2]):
        raise WatchlistStructureError(_IDENTITY_HEADER_TOOLTIP)
    tooltips: list[str] = []
    visible: list[str] = []
    for cell in cells[2:]:
        tooltip = cell.get(_TOOLTIP_ATTRIBUTE)
        if tooltip is None or not tooltip.strip():
            raise WatchlistStructureError(_VALUE_HEADER_TOOLTIP)
        tooltips.append(normalize_text(tooltip))
        visible.append(normalize_text(cell.text_content()))
    return tuple(tooltips), tuple(visible), sum(_colspan(cell) for cell in cells)


def _colspan(cell: Any) -> int:
    """The number of columns one header cell covers; an absent ``colspan`` covers one."""
    raw = cell.get(_COLSPAN_ATTRIBUTE)
    if raw is None:
        return 1
    if not _NUMBER.fullmatch(raw.strip()):
        raise WatchlistStructureError(_BAD_COLSPAN)
    return int(raw.strip())


def _member_row(cells: list[Any], *, row_id_raw: str) -> WatchlistTableRow:
    """Read one member row: serial, notebook cell, company link, then its values."""
    serial = _SERIAL.fullmatch(normalize_text(cells[0].text_content()))
    if serial is None:
        raise WatchlistStructureError(_BAD_SERIAL)
    if not _NUMBER.fullmatch(row_id_raw.strip()):
        raise WatchlistStructureError(_BAD_ROW_ID)
    row_id = int(row_id_raw.strip())
    links = cells[2].xpath(_ENTRY_LINKS)
    if len(links) != 1:
        raise WatchlistStructureError(_ONE_COMPANY_LINK)
    name = normalize_text(links[0].text_content())
    if not name:
        raise WatchlistStructureError(_BLANK_COMPANY_NAME)
    slug, consolidated = _company_link(links[0].get(_HREF_ATTRIBUTE), row_id=row_id)
    return WatchlistTableRow(
        serial_number=int(serial.group(1)),
        data_row_company_id=row_id,
        slug=slug,
        consolidated=consolidated,
        display_name=name,
        values=tuple(normalize_text(cell.text_content()) for cell in cells[3:]),
    )


def _company_link(href: str | None, *, row_id: int) -> tuple[str | None, bool]:
    """Resolve the company link into ``(slug, consolidated)``, admitting four shapes.

    Both id-routed shapes carry the literal segment ``id`` then the numeric
    company id, which must equal the row's own identifier — reading the first
    segment as the slug would record a company called ``id``. The
    ``/consolidated/`` suffix is a basis signal, and its absence is not a defect.
    """
    if href is None:
        raise WatchlistStructureError(_UNSUPPORTED_LINK)
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise WatchlistStructureError(_UNSUPPORTED_LINK)
    segments = href.split("/")
    if (
        len(segments) < 2
        or segments[0] != ""
        or segments[-1] != ""
        or segments[1] != _COMPANY_SEGMENT
    ):
        raise WatchlistStructureError(_UNSUPPORTED_LINK)
    route = segments[2:-1]
    if route and route[0] == _ID_SEGMENT:
        if (
            len(route) in (2, 3)
            and _NUMBER.fullmatch(route[1])
            and int(route[1]) == row_id
            and (len(route) == 2 or route[2] == _CONSOLIDATED_SEGMENT)
        ):
            return None, len(route) == 3
        raise WatchlistStructureError(_UNSUPPORTED_LINK)
    if len(route) == 1 and route[0]:
        return route[0], False
    if len(route) == 2 and route[0] and route[1] == _CONSOLIDATED_SEGMENT:
        return route[0], True
    raise WatchlistStructureError(_UNSUPPORTED_LINK)


def _export_form(root: Any) -> tuple[str, str]:
    """Return the one export form's verbatim action and its CSRF form token."""
    forms = [
        form
        for form in root.xpath(_FORMS)
        if urlsplit(form.get(_ACTION_ATTRIBUTE) or "").path == EXPORT_PATH
    ]
    if len(forms) != 1:
        raise WatchlistPageError(_ONE_EXPORT_FORM.format(count=len(forms)))
    tokens = [
        (field.get(_VALUE_ATTRIBUTE) or "")
        for field in forms[0].xpath(_NAMED_INPUTS)
        if field.get(_NAME_ATTRIBUTE) == CSRF_FORM_FIELD
    ]
    if len(tokens) != 1 or not tokens[0].strip():
        raise WatchlistPageError(_ONE_FORM_TOKEN.format(field=CSRF_FORM_FIELD))
    return forms[0].get(_ACTION_ATTRIBUTE), tokens[0]


def _watchlist_id(action: str, root: Any) -> int | None:
    """Read the list id from the export action, or else from the membership-editor link."""
    values = parse_qs(urlsplit(action).query).get(SUBLIST_ID_PARAMETER, ())
    if len(values) == 1 and _NUMBER.fullmatch(values[0]):
        return int(values[0])
    for link in root.xpath(_ENTRY_LINKS):
        href = link.get(_HREF_ATTRIBUTE) or ""
        parts = urlsplit(href)
        if parts.path != STOCKS_EDITOR_PATH:
            continue
        for target in parse_qs(parts.query).get(NEXT_PARAMETER, ()):
            match = _WATCHLIST_NEXT.fullmatch(target)
            if match is not None:
                return int(match.group(1))
    return None


def _dropdown(root: Any) -> tuple[str | None, tuple[str, ...]]:
    """Read the selector's selected name and the names of every other list it offers.

    The dropdown carries no id, so it supplies provenance only, and an unmarked
    one leaves the name unset rather than refusing: the name binds nothing. Two
    marked entries are different: the selector then says two lists are the one
    on screen, and quietly keeping the first would record a name for a list this
    page may not be rendering.
    """
    selected: str | None = None
    others: list[str] = []
    for entry in root.xpath(_DROPDOWN_ENTRIES):
        if any(
            urlsplit(link.get(_HREF_ATTRIBUTE) or "").path == CREATE_WATCHLIST_PATH
            for link in entry.xpath(_ENTRY_LINKS)
        ):
            continue
        name = normalize_text(entry.text_content())
        if not name:
            continue
        if not entry.xpath(_SELECTED_ICON):
            others.append(name)
            continue
        if selected is not None:
            raise WatchlistPageError(_AMBIGUOUS_SELECTION)
        selected = name
    return selected, tuple(others)


def _cookie_state(set_cookies: tuple[str, ...]) -> dict[str, str]:
    """Fold the GET's ``Set-Cookie`` headers into the state the export POST must carry.

    Held locally and serialised by hand rather than by a cookie jar: CPython's jar
    adds nothing to a request that already carries a ``Cookie`` header, so a jar
    would drop the CSRF cookie silently and the site's 403 would read as a
    terminal block. A missing token refuses locally, before the POST.

    The pair is read directly rather than through :class:`http.cookies.SimpleCookie`,
    for two reasons. That parser is not an RFC 6265 reader: an unknown valueless
    attribute — CHIPS ``Partitioned`` is the obvious next one — makes it discard
    the whole header silently, and the run then reports that no token was sent
    when one was. And it *decodes* ``\\012`` in a quoted value into a real
    newline, which ``http.client`` refuses with a ``ValueError`` naming the whole
    ``Cookie`` header — both secrets — so the value never becomes a header at all.
    """
    state: dict[str, str] = {}
    unreadable = False
    for header in set_cookies:
        name, separator, value = header.split(";", 1)[0].partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not name:
            unreadable = unreadable or header.strip().lower().startswith(CSRF_COOKIE_NAME)
            continue
        _refuse_control_characters(name, value)
        state[name] = value
    if SESSION_COOKIE_NAME in state:
        raise WatchlistPageError(_SESSION_REISSUED)
    if CSRF_COOKIE_NAME not in state:
        raise WatchlistPageError(_UNREADABLE_CSRF_COOKIE if unreadable else _NO_CSRF_COOKIE)
    if not state[CSRF_COOKIE_NAME]:
        raise WatchlistPageError(_EMPTY_CSRF_COOKIE)
    return state


def _refuse_control_characters(name: str, value: str) -> None:
    """Refuse a cookie carrying a control character before it can reach a header.

    A newline or a NUL inside a cookie makes ``http.client`` raise a
    ``ValueError`` whose message quotes the entire outbound ``Cookie`` header —
    the session cookie and the CSRF token together — and that message would be
    written into the artifact and onto the terminal. For the same reason no
    refusal here echoes the offending text, and a cookie name is named only once
    it has itself been cleared.
    """
    if any(character < " " or character == "\x7f" for character in name):
        raise WatchlistPageError(_CONTROL_IN_COOKIE_NAME)
    if any(character < " " or character == "\x7f" for character in value):
        raise WatchlistPageError(_CONTROL_IN_COOKIE_VALUE.format(name=name))


def _export_filename(content_disposition: str | None) -> str:
    """The filename an export's ``Content-Disposition`` names, quoted or not."""
    if content_disposition is None:
        return ""
    message = email.message.Message()
    message["Content-Disposition"] = content_disposition
    return (message.get_filename() or "").strip()


def _incomplete(
    evidence: WatchlistPageEvidence | None,
    documents: list[ScreenerDocumentFetch],
    *,
    refusal: str,
    detail: str,
    source_url: str,
    content_sha256: str | None,
    cross_check: WatchlistCrossCheck | None = None,
) -> WatchlistRun:
    """Close a run that stopped short, keeping every body it received.

    No row is published: in a disagreement each side looks internally coherent,
    so publishing the part that "agreed" would publish the defect.
    """
    return WatchlistRun(
        artifact=WatchlistArtifact(
            watchlist_id=None if evidence is None else evidence.watchlist_id,
            watchlist_name=None if evidence is None else evidence.watchlist_name,
            other_watchlist_names=() if evidence is None else evidence.other_watchlist_names,
            outcome=WatchlistOutcome.INCOMPLETE,
            incomplete_reason=detail,
            cross_check=cross_check,
            failure=WatchlistFailure(
                source_url=source_url,
                refusal=refusal,
                detail=detail,
                content_sha256=content_sha256,
            ),
        ),
        documents=tuple(documents),
    )
