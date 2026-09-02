"""Synthetic fixtures and seams for the ``screener-screen`` test modules.

No test opens a socket and no fixture here is a captured page: every body below
is built from the *structure* the live surface was verified to have (a repeating
header row inside ``tbody``, a query-dependent column set, two ``options`` blocks
inside ``.pagination``, three company-link shapes) with invented queries,
companies, slugs, ids and numbers. The captures themselves are orchestrator-only
and never reach a fixture.

Two conventions are inherited from :mod:`screener_company_support` on purpose:
the transport seam is pinned at ``_fetch_bytes`` so the production code still
builds its own URLs — which makes every value assertion also a URL assertion —
and header-level questions reach one level lower, through
:func:`screener_company_support.capture_requests`.

The Slice 3 modules are reached through :class:`_Module` rather than imported at
the top. These are acceptance tests written before the implementation exists, so
a top-level import would collapse fourteen independently red tests into one
collection error and hide which requirement each of them pins.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from fundamentals.api.cli import main
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import (
    ScreenerCredentials,
    ScreenerDocumentFetch,
    ScreenerSessionConfig,
    ScreenerSessionError,
)
from fundamentals.ingest.screener_session_page import parse_document


class _Module:
    """Deferred attribute access into a Slice 3 module.

    Every lookup happens at call time, so a module that does not exist yet fails
    the one test that asked for it instead of the whole file.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        """Resolve one public name out of the named module."""
        return getattr(importlib.import_module(self._name), attribute)


models = _Module("fundamentals.ingest.screener_screen_models")
screen = _Module("fundamentals.ingest.screener_screen")
screen_cli = _Module("fundamentals.api.screener_screen_cli")

COMMAND = "screener-screen"
SESSION_ENV = "SCREENER_SESSION_COOKIE"
SESSION_TOKEN = "fixture-session-token"

# Two invented queries of different widths. The seam-defining fact of this slice
# is that the column set follows the query, so the fixtures must differ in it.
QUERY = "Alpha ratio > 11 AND Beta score < 3"
WIDE_QUERY = "Alpha ratio > 11 AND Beta score < 3 AND Zeta var 5Years > 4"
EMPTY_QUERY = "Alpha ratio > 8642086420"

NARROW_LABELS = ("S.No.", "Name", "Alpha Ratio %", "Beta Score", "Gamma Cr.", "Delta Var %")
WIDE_LABELS = (*NARROW_LABELS, "Epsilon Rs.", "Zeta Var 5Yrs %")

TABLE_ID = "screen-results"
SOURCE_ID = "screener-subscriber"
FETCHED_AT = datetime(2026, 9, 2, tzinfo=UTC)
TSV_HEADER = "outcome\tpages\trows\tcolumns\tartifact"
ARTIFACT_FILENAME = "screener_screen.json"
PAGES_DIRNAME = "pages"
PAGE_FILENAME_TEMPLATE = "page_{number:04d}.raw.html"

# All six class tokens the live table carries. Five are presentational and the
# reader must not pin them; they are here so a fixture cannot accidentally prove
# a rule that only holds for a bare ``data-table``.
TABLE_CLASS = "data-table text-nowrap striped mark-visited no-scroll-right highlight-on-hover"

# The other end of the same rule: one required token, in a position it does not
# hold on the live page, beside tokens no capture has ever carried. A reader that
# pins the class *string* — or its order, or its length — accepts every table
# above and refuses this one, which is the drift the rule exists to survive.
MINIMAL_TABLE_CLASS = "responsive-holder data-table future-token"

# The verified live page shape: four byte-identical header rows at row positions
# 0, 15, 30 and 45, fifty data rows, fifty-four ``tr`` in one ``tbody``.
LIVE_ROWS_PER_PAGE = 50
LIVE_HEADER_BLOCK = 15
LIVE_HEADER_COUNT = 4
LIVE_ROW_COUNT = LIVE_ROWS_PER_PAGE + LIVE_HEADER_COUNT

# The account nav is the only proof a subscriber session served the page.
ACCOUNT_LINK = '<a href="/user/account/">My Account</a>'
LOGOUT_FORM = '<form action="/logout/" method="post"><button>Logout</button></form>'

# Deliberately wrong: every offered-page anchor points at a page number the walk
# must never visit, so a reader that follows hrefs instead of reading anchor text
# fails loudly rather than accidentally passing.
_DECOY_HREF = "?sort=&amp;order=&amp;source=&amp;query=decoy&amp;page=999"

# The invented query as it is spelled inside a selector href, and the fixed
# prefix every anchor in the live pagination carries ahead of its own parameters.
SELECTOR_QUERY = "Alpha+ratio+%3E+11+AND+Beta+score+%3C+3"
_SELECTOR_BASE = f"?sort=&amp;order=&amp;source=&amp;query={SELECTOR_QUERY}"


def selector_href(limit: int, *, page: int = 1) -> str:
    """One page-size href in the full shape the live selector serves.

    The live anchor carries the whole query string — ``sort``, ``order``,
    ``source``, ``query``, ``page`` and ``limit`` — not a bare ``?limit=``. A
    fixture that omits ``page=`` leaves the "every offered page is page 1" half
    of the classification rule vacuously satisfied, so the accepting case would
    never exercise it against the shape the site actually returns.
    """
    return f"{_SELECTOR_BASE}&amp;page={page}&amp;limit={limit}"


# The page-size selector, nested one level down inside a flex wrapper exactly as
# the live page renders it. Its anchors are bare numerals, indistinguishable from
# page numbers by text alone; only ``limit=`` in the href separates them.
PAGE_SIZE_ANCHORS = (
    f'<a href="{selector_href(10)}">10</a>'
    f'<a href="{selector_href(25)}">25</a>'
    f'<a href="{selector_href(50)}" class="active">50</a>'
)

# A page-size link that is *outside* every ``options`` block. Its href is a
# perfectly good selector href, so containment is the only thing it fails.
STRAY_PAGE_SIZE_ANCHOR = f'<a href="{selector_href(25)}">25</a>'

# What a moved page-number block would look like once it also preserves the
# chosen page size: nested, bare numerals, ``limit=`` on every anchor, and page
# values that are not all 1. Only the page check separates this from the
# selector — and mistaking it truncates a real walk at page 1 in silence.
MOVED_PAGE_ANCHORS = (
    f'<a href="{selector_href(50, page=1)}" class="active">1</a>'
    f'<a href="{selector_href(50, page=2)}">2</a>'
)

# A nested ``options`` block that is some *other* control — export links for the
# page being viewed. Contained, and every href stays on page 1, so ``limit=`` is
# the only thing separating it from the selector. It says nothing at all about
# how many pages there are, which is why its presence cannot end a walk.
_EXPORT_HREF = f"{_SELECTOR_BASE}&amp;page=1&amp;format="
NESTED_EXPORT_ANCHORS = f'<a href="{_EXPORT_HREF}csv">1</a><a href="{_EXPORT_HREF}xlsx">2</a>'

# What a moved page-number block would look like: same nesting, same bare
# numerals, ``page=`` instead of ``limit=``. Reading text alone cannot tell this
# from the selector above, and mistaking it truncates a real walk at page 1.
NESTED_PAGE_ANCHORS = (
    f'<a href="#" class="active">1</a><a href="{_DECOY_HREF}">2</a><a href="{_DECOY_HREF}">3</a>'
)


class SyntheticRow(BaseModel):
    """One invented result row: its serial, its identity, its link and its cells."""

    model_config = ConfigDict(frozen=True)

    serial: int
    company_id: int
    href: str
    name: str
    values: tuple[str, ...]


class Recorder:
    """Every screen request the pinned transport saw, how it was marked, and by whom.

    ``sources`` holds the receiver of each call rather than a count of them.
    Discarding it would let an implementation build a fresh
    :class:`ScreenerSessionSource` per page and still pass — and a new source is a
    new spacing clock and a new 429 budget, which is precisely the sharing this
    slice depends on.
    """

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.xhr: list[bool] = []
        self.sources: list[ScreenerSessionSource] = []


def header_row(labels: tuple[str, ...]) -> str:
    """One all-``th`` header row whose labels sit inside sort anchors.

    The anchors are the point: on the live surface every header label is wrapped
    in one, so ``.text`` on the cell is empty and only ``text_content()`` sees
    the label.
    """
    cells = "".join(
        f'<th class="text"><a href="?sort={index}&amp;order=asc">{label}</a></th>'
        for index, label in enumerate(labels)
    )
    return f"<tr>{cells}</tr>"


def data_row(
    row: SyntheticRow,
    *,
    serial_cell: str | None = None,
    company_cell: str | None = None,
    row_id: str | None = None,
) -> str:
    """One data row: serial cell, company link cell, then one cell per column.

    Each override replaces exactly one of the three things a data row is
    contracted to carry, so a refusal case can state which boundary it crosses.
    ``row_id=""`` omits the identity attribute outright.
    """
    written_id = str(row.company_id) if row_id is None else row_id
    identity = f' data-row-company-id="{written_id}"' if written_id else ""
    serial = f"{row.serial}." if serial_cell is None else serial_cell
    company = (
        f'<a href="{row.href}" target="_blank">{row.name}</a>'
        if company_cell is None
        else company_cell
    )
    cells = "".join(f"<td>{value}</td>" for value in row.values)
    return (
        f'<tr{identity}><td class="text">{serial}</td><td class="text">{company}</td>{cells}</tr>'
    )


def results_table(
    labels: tuple[str, ...],
    rows: tuple[SyntheticRow, ...],
    *,
    block: int = 2,
    trailing_header: str | None = None,
    class_attribute: str = TABLE_CLASS,
) -> str:
    """A populated result table whose header repeats every ``block`` data rows.

    The live pages repeat an identical header four times inside one ``tbody``;
    ``trailing_header`` appends a differing one, which is the in-page schema
    drift the reader has to tell apart from a repeat. ``class_attribute`` exists
    so a fixture can carry the one required token without the five
    presentational ones.
    """
    body: list[str] = []
    for position, row in enumerate(rows):
        if position % block == 0:
            body.append(header_row(labels))
        body.append(data_row(row))
    if trailing_header is not None:
        body.append(trailing_header)
    return f'<table class="{class_attribute}"><tbody>{"".join(body)}</tbody></table>'


def empty_table() -> str:
    """The zero-result table: the same six class tokens, no ``tr`` and no ``th``."""
    return f'<table class="{TABLE_CLASS}"><tbody></tbody></table>'


def row_shapes(body: str) -> tuple[tuple[str, ...], int]:
    """The header rows and the data-row count of one body's result table.

    Counted off the fixture's own markup rather than off what the reader made of
    it, so a test can prove the fixture really has the live shape before it
    asserts anything about how that shape is read.
    """
    headers: list[str] = []
    data = 0
    for element in parse_document(body).xpath(".//table//tr"):
        tags = {child.tag for child in element}
        if tags == {"th"}:
            headers.append("|".join(cell.text_content() for cell in element))
        else:
            data += 1
    return tuple(headers), data


def _page_size_block(anchors: str) -> str:
    """The wrapper the live page nests its ``div.options`` inside."""
    return (
        '<div class="flex flex-baseline flex-gap-16">'
        '<span class="ink-600 sub">Results per page</span>'
        f'<div class="options">{anchors}</div>'
        "</div>"
    )


def nested_options_pagination(anchors: str = PAGE_SIZE_ANCHORS, *, stray: str = "") -> str:
    """A ``.pagination`` whose only ``div.options`` is *not* a direct child.

    The verified single-page-populated shape: no page-number controls at all, and
    the page-size selector one level down inside a flex wrapper. ``anchors``
    replaces what that nested block holds and ``stray`` adds an anchor outside
    every ``options`` block — the two ways the same nesting can instead mean a
    page-number block has moved, which is a walk to continue and not a walk that
    is over.
    """
    return f'<div class="pagination">{stray}{_page_size_block(anchors)}</div>'


def pagination(
    offered: tuple[int, ...],
    *,
    active: int | None,
    previous: bool = False,
    next_page: bool = False,
    page_size: bool = True,
    elided_after: int | None = None,
    also_active: int | None = None,
    scoped: bool = True,
) -> str:
    """The two-block pagination the live page renders.

    The second block is a *page-size* selector carrying its own ``active``
    anchor, so a reader that takes every ``.options`` anchor sees two active
    anchors and offers pages 10, 25 and 50 — under which no walk terminates.

    ``active=None`` marks no anchor current, ``also_active`` marks a second one,
    and ``scoped=False`` drops the ``options`` token from the first block while
    leaving its anchors in place: three shapes that are each unreadable for a
    different reason, and none of which the live page has ever rendered.
    """
    anchors: list[str] = []
    if previous:
        anchors.append(f'<a href="{_DECOY_HREF}" class="ink-900"> Previous </a>')
    for number in offered:
        if number in (active, also_active):
            anchors.append(f'<a href="#" class="active">{number}</a>')
        else:
            anchors.append(f'<a href="{_DECOY_HREF}" class="ink-900">{number}</a>')
        if elided_after is not None and number == elided_after:
            anchors.append('<span class="ink-600">&hellip;</span>')
    if next_page:
        anchors.append(f'<a href="{_DECOY_HREF}" class="ink-900"> Next </a>')
    selector = ""
    if page_size:
        selector = _page_size_block(PAGE_SIZE_ANCHORS)
    block_class = "flex-baseline options" if scoped else "flex-baseline"
    return (
        '<div class="pagination">'
        f'<div class="{block_class}">{"".join(anchors)}</div>'
        f"{selector}</div>"
    )


def empty_pagination() -> str:
    """The zero-result pagination block: whitespace and a comment, no anchors."""
    return '<div class="pagination">\n   <!-- no pages -->\n</div>'


def page(table: str, pagination_html: str, *, account: bool = True, logout: bool = True) -> str:
    """Wrap one table and one pagination block in the page around them."""
    nav = f"<nav>{ACCOUNT_LINK if account else ''}{LOGOUT_FORM if logout else ''}</nav>"
    return (
        "<html><body>"
        f"{nav}<main>{table}{pagination_html}"
        '<a href="/screen/save/">Save this screen</a>'
        "</main></body></html>"
    )


def rows_for(
    page_number: int,
    *,
    count: int = 8,
    labels: tuple[str, ...] = NARROW_LABELS,
) -> tuple[SyntheticRow, ...]:
    """``count`` invented rows whose serials continue globally across pages."""
    width = len(labels) - 2
    first = (page_number - 1) * count + 1
    return tuple(
        SyntheticRow(
            serial=serial,
            company_id=770000 + serial,
            href=f"/company/SYNTH{serial:03d}/",
            name=f"Synthetic Holdings {serial:03d}",
            values=tuple(f"{serial}{index}.25" for index in range(width)),
        )
        for serial in range(first, first + count)
    )


def results_page(
    page_number: int,
    *,
    offered: tuple[int, ...],
    labels: tuple[str, ...] = NARROW_LABELS,
    rows: tuple[SyntheticRow, ...] | None = None,
    block: int = 2,
    account: bool = True,
    logout: bool = True,
) -> str:
    """One populated page of a walk, with its own header repeats and pagination."""
    body = rows if rows is not None else rows_for(page_number, labels=labels)
    return page(
        results_table(labels, body, block=block),
        pagination(
            offered,
            active=page_number,
            previous=page_number > min(offered),
            next_page=page_number < max(offered),
        ),
        account=account,
        logout=logout,
    )


def live_page(page_number: int, *, offered: tuple[int, ...]) -> str:
    """One page in the exact shape the live surface was verified to serve.

    ``1H 15D · 1H 15D · 1H 15D · 1H 5D``: fifty-four ``tr`` inside one ``tbody``,
    four byte-identical header rows and fifty data rows. The smaller fixtures
    elsewhere repeat the header more often for brevity, which is legal but is not
    what the site returns — so the rules that turn on the repeat are pinned here,
    against the real proportions.
    """
    return results_page(
        page_number,
        offered=offered,
        rows=rows_for(page_number, count=LIVE_ROWS_PER_PAGE),
        block=LIVE_HEADER_BLOCK,
    )


def zero_result_page() -> str:
    """The verified empty shape: a rowless table beside an anchor-less pagination."""
    return page(empty_table(), empty_pagination())


def walk(pages: int, *, labels: tuple[str, ...] = NARROW_LABELS) -> dict[int, str]:
    """A complete ``pages``-page walk whose last page offers no successor."""
    offered = tuple(range(1, pages + 1))
    return {
        number: results_page(number, offered=offered, labels=labels)
        for number in range(1, pages + 1)
    }


def one_row(**overrides: Any) -> SyntheticRow:
    """One invented data row, with named fields overridden per case."""
    fields: dict[str, Any] = {
        "serial": 1,
        "company_id": 770001,
        "href": "/company/SYNTHONE/",
        "name": "Synthetic Holdings 001",
        "values": ("110.25", "12.50", "31.75", "-4.00"),
    }
    fields.update(overrides)
    return SyntheticRow(**fields)


def table_of(rows_html: str, *, class_attribute: str = TABLE_CLASS) -> str:
    """One result table around hand-written row markup."""
    return f'<table class="{class_attribute}"><tbody>{rows_html}</tbody></table>'


def single_page(table: str) -> str:
    """One page whose pagination offers exactly the page it is."""
    return page(table, pagination((1,), active=1))


def page_of(row: SyntheticRow) -> str:
    """A one-row populated page, for the per-row rules."""
    return single_page(results_table(NARROW_LABELS, (row,)))


def row_page(
    *,
    serial_cell: str | None = None,
    company_cell: str | None = None,
    row_id: str | None = None,
    labels: tuple[str, ...] = NARROW_LABELS,
) -> str:
    """A header plus one data row carrying exactly one crossed boundary."""
    row = data_row(one_row(), serial_cell=serial_cell, company_cell=company_cell, row_id=row_id)
    return single_page(table_of(header_row(labels) + row))


def malformed_pages() -> tuple[str, ...]:
    """Every table shape the reader is contracted to refuse, one page each.

    Each parses cleanly into *something*, which is why refusing has to be
    explicit: a half-read table publishes numbers under the wrong column labels,
    and downstream that is indistinguishable from real data.
    """
    header = header_row(NARROW_LABELS)
    pair = results_table(NARROW_LABELS, rows_for(1, count=2))
    return (
        # ``data-tables`` is a different class token, and a substring match on
        # ``data-table`` would accept it.
        single_page('<table class="data-tables"><tbody></tbody></table>'),
        # Two result tables: which one answers the query becomes document order.
        single_page(pair + pair),
        # A header with no data row is neither legal shape: the evidenced empty
        # result carries no header at all.
        single_page(table_of(header)),
        # A populated table whose first row is data: nothing declares the schema.
        single_page(table_of(data_row(one_row()))),
        # A row that is neither all ``th`` nor all ``td``.
        single_page(table_of(header + "<tr><th>1.</th><td>x</td></tr>")),
        # A data row narrower than the header: its cells no longer align to the
        # columns that name them.
        single_page(table_of(header + data_row(one_row(values=("110.25", "12.50"))))),
        # The two literal header labels. Position 0 and 1 are the cells this
        # reader interprets rather than records, so a page that renames either is
        # not the table this slice knows how to read.
        row_page(labels=("Sr.", *NARROW_LABELS[1:])),
        row_page(labels=(NARROW_LABELS[0], "Company", *NARROW_LABELS[2:])),
        # A numeric column with no label: its values would be published under a
        # name nothing supplied.
        row_page(labels=(*NARROW_LABELS[:2], "", *NARROW_LABELS[3:])),
        # The serial lexeme is canonical. Anything else is a different rendering
        # than the one the global-continuity check is defined over.
        row_page(serial_cell="1"),
        row_page(serial_cell="01."),
        row_page(serial_cell="0."),
        row_page(serial_cell=""),
        row_page(serial_cell="1.2."),
        # The row identity: absent, non-positive, or not a number at all. It is
        # the one identity every admitted row carries, so it cannot be inferred.
        row_page(row_id=""),
        row_page(row_id="0"),
        row_page(row_id="-3"),
        row_page(row_id="SYNTHONE"),
        # Exactly one company link with a non-empty name. Zero leaves the row
        # unidentified, two leave the choice to document order, and an empty name
        # would publish a company called "".
        row_page(company_cell="Synthetic Holdings 001"),
        row_page(
            company_cell=(
                '<a href="/company/SYNTHONE/">Synthetic Holdings 001</a>'
                '<a href="/company/SYNTHTWO/">Synthetic Holdings 002</a>'
            )
        ),
        row_page(company_cell='<a href="/company/SYNTHONE/"></a>'),
    )


# What each frozen model carries, and nothing else. Held as data because the
# risk is not a wrong field but an extra one: a derived ``complete`` flag, a
# second copy of the raw serial, or a ``logged_in`` boolean that can disagree
# with the admission rule that produced it.
MODEL_FIELDS = {
    "ScreenAcquisitionConfig": {"max_pages"},
    "ScreenColumn": {"index", "label"},
    "ScreenCell": {"column_index", "value", "raw_text", "provenance"},
    "ScreenCompany": {"slug", "display_name", "data_row_company_id", "consolidated"},
    "ScreenRow": {"page_number", "serial_number", "company", "cells"},
    "ScreenPageMetadata": {
        "page_number",
        "source_url",
        "http_status",
        "offered_pages",
        "content_sha256",
        "byte_count",
        "fetched_at",
    },
    "ScreenFailure": {"page_number", "source_url", "refusal", "detail", "content_sha256"},
    "ScreenArtifact": {
        "source_id",
        "query",
        "outcome",
        "columns",
        "rows",
        "pages",
        "incomplete_reason",
        "failure",
    },
    "ScreenRun": {"artifact", "documents"},
    "ScreenerScreenCliRun": {"run", "artifact_path", "page_paths"},
}


def rebuilt(model: Any, **overrides: Any) -> Any:
    """The same model built again through validation with one field replaced."""
    return type(model)(**{**model.model_dump(), **overrides})


def config() -> ScreenerSessionConfig:
    """A config carrying a fixture cookie; the seam never reads its value."""
    return ScreenerSessionConfig(
        credentials=ScreenerCredentials(session_cookie=SecretStr(SESSION_TOKEN)),
        min_request_spacing_seconds=0,
    )


def source() -> ScreenerSessionSource:
    """One subscriber source, shared by every page of a walk."""
    return ScreenerSessionSource(config())


def serve(
    monkeypatch: pytest.MonkeyPatch,
    bodies: dict[int, str],
    *,
    refusals: dict[int, ScreenerSessionError] | None = None,
) -> Recorder:
    """Pin the transport seam to synthetic bodies keyed by requested page number.

    Keying on the ``page`` value the production code encodes makes every body
    assertion also an assertion that the URL was built correctly. A request for
    a page no fixture offers fails here rather than being answered, because
    probing an unoffered page is itself the defect.
    """
    recorder = Recorder()

    def fetch_bytes(
        source: ScreenerSessionSource,
        url: str,
        credentials: ScreenerCredentials,
        *,
        xhr: bool = False,
    ) -> tuple[int, bytes]:
        del credentials
        recorder.urls.append(url)
        recorder.xhr.append(xhr)
        recorder.sources.append(source)
        number = requested_page(url)
        if refusals is not None and number in refusals:
            raise refusals[number]
        if number not in bodies:
            raise AssertionError(f"page {number} was requested but never offered: {url}")
        return 200, bodies[number].encode("utf-8")

    monkeypatch.setenv(SESSION_ENV, SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", fetch_bytes)
    return recorder


def requested_page(url: str) -> int:
    """The page number one built screen URL asks for."""
    return int(parse_qs(urlsplit(url).query)["page"][0])


def acquire(
    monkeypatch: pytest.MonkeyPatch,
    bodies: dict[int, str],
    *,
    query: str = QUERY,
    max_pages: int | None = None,
    refusals: dict[int, ScreenerSessionError] | None = None,
    injected: ScreenerSessionSource | None = None,
) -> tuple[Any, Recorder]:
    """Acquire one query through the real code path against the pinned seam."""
    recorder = serve(monkeypatch, bodies, refusals=refusals)
    settings = {} if max_pages is None else {"max_pages": max_pages}
    run = screen.acquire_screen(
        query,
        source=injected if injected is not None else source(),
        config=models.ScreenAcquisitionConfig(**settings),
    )
    return run, recorder


def fetch(body: str, *, page_number: int = 1, query: str = QUERY) -> ScreenerDocumentFetch:
    """The retained response record one pure reader is handed for a body."""
    raw = body.encode("utf-8")
    return ScreenerDocumentFetch(
        raw_body=raw,
        source_url=models.screen_url(query, page_number),
        http_status=200,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        byte_count=len(raw),
        fetched_at=FETCHED_AT,
    )


def read_table(body: str, *, page_number: int = 1) -> tuple[Any, Any]:
    """Read one body through the pure table reader."""
    columns, rows = screen.read_screen_table(
        parse_document(body),
        fetch=fetch(body, page_number=page_number),
        page_number=page_number,
    )
    return columns, rows


def read_pagination(body: str, *, requested_page_number: int = 1) -> Any:
    """Read one body through the pure pagination reader."""
    return screen.read_screen_pagination(parse_document(body), requested_page=requested_page_number)


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bodies: dict[int, str],
    *extra: str,
    query: str = QUERY,
    refusals: dict[int, ScreenerSessionError] | None = None,
    out_dir: Path | None = None,
) -> tuple[int, Path, Recorder]:
    """Run ``fundamentals screener-screen`` end to end against the pinned seam."""
    recorder = serve(monkeypatch, bodies, refusals=refusals)
    target = out_dir if out_dir is not None else tmp_path / "out"
    exit_code = main([COMMAND, "--query", query, "--out", str(target), *extra])
    return exit_code, target, recorder


def artifact_of(out_dir: Path) -> Path:
    """The published artifact path inside one output directory."""
    return out_dir / ARTIFACT_FILENAME


def page_file(out_dir: Path, number: int) -> Path:
    """The retained body path for one fetched page position."""
    return out_dir / PAGES_DIRNAME / PAGE_FILENAME_TEMPLATE.format(number=number)


def payload_of(out_dir: Path) -> dict[str, Any]:
    """The published artifact of one output directory, parsed."""
    loaded: dict[str, Any] = json.loads(artifact_of(out_dir).read_text(encoding="utf-8"))
    return loaded


def artifact_body(payload: dict[str, Any]) -> dict[str, Any]:
    """The artifact record inside a published payload.

    The plan freezes the artifact's file name and its fields, not the envelope
    the file writes them in, so both shapes are accepted here rather than pinning
    a detail the contract leaves open.
    """
    if "outcome" in payload:
        return payload
    nested: dict[str, Any] = payload["artifact"]
    return nested


def artifact_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The per-page metadata records inside a published payload."""
    return list(artifact_body(payload)["pages"])


class FirstCreationError(Exception):
    """Raised in place of the first directory an invocation tries to create."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path = path


def intercept_first_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop an invocation at the first directory it creates, naming that path.

    The default output root is derived from the repository, not from the working
    directory, so a test of the default-path algorithm cannot be contained by
    ``chdir`` and must never be allowed to reach the disk. Preflight establishes
    the output directory before the first request, so the first creation attempt
    *is* the resolved destination — which makes the frozen excerpt, truncation,
    fallback and digest observable without writing a byte.
    """

    def refuse(
        self: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
    ) -> None:
        del mode, parents, exist_ok
        raise FirstCreationError(self)

    monkeypatch.setattr(Path, "mkdir", refuse)


def record_publications(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Every destination the no-clobber writer creates, in the order it created them.

    ``write_bytes_no_clobber`` publishes by linking a temporary file onto its
    target, so that link *is* the moment a file becomes visible. Recording the
    order is the only way to tell "the artifact was written last" from "the
    artifact was written first and then rolled back" — the two leave the same
    directory behind.
    """
    destinations: list[Path] = []
    linked = os.link

    def record(source_path: Any, target: Any, *, follow_symlinks: bool = True) -> None:
        destinations.append(Path(target))
        linked(source_path, target, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "link", record)
    return destinations
