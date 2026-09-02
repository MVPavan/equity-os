"""The synthetic page fixtures the ``screener-screen`` tests are written against.

Split out of :mod:`screener_screen_support` when that module outgrew the file
ceiling. This half is the *markup* layer and nothing else: the invented labels,
class tokens, nav and pagination anchors, and every builder that assembles them
into a body. It knows nothing about the transport seam, the Slice 3 modules or
the CLI, which is why it can be read on its own.

No body here is a captured page: every one is built from the *structure* the
live surface was verified to have (a repeating header row inside ``tbody``, a
query-dependent column set, two ``options`` blocks inside ``.pagination``, three
company-link shapes) with invented companies, slugs, ids and numbers.

:mod:`screener_screen_support` re-exports every public name below, so tests keep
reaching all of it through ``support.``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_session_page import parse_document

NARROW_LABELS = ("S.No.", "Name", "Alpha Ratio %", "Beta Score", "Gamma Cr.", "Delta Var %")
WIDE_LABELS = (*NARROW_LABELS, "Epsilon Rs.", "Zeta Var 5Yrs %")

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


def table_without_tbody(
    labels: tuple[str, ...],
    rows: tuple[SyntheticRow, ...],
    *,
    header: bool = True,
    class_attribute: str = TABLE_CLASS,
) -> str:
    """A populated result table whose rows are direct children of ``<table>``.

    A browser inserts the missing ``tbody``; libxml2 does not, so this is what a
    template that stopped emitting the tag actually parses into. ``header=False``
    drops the header row, which is the shape that carries no ``th`` anywhere.
    """
    body = (header_row(labels) if header else "") + "".join(data_row(row) for row in rows)
    return f'<table class="{class_attribute}">{body}</table>'


def table_with_displaced_row(
    labels: tuple[str, ...],
    rows: tuple[SyntheticRow, ...],
    displaced: SyntheticRow,
    *,
    section: str = "tfoot",
    class_attribute: str = TABLE_CLASS,
) -> str:
    """A normal ``tbody`` table carrying one further data row outside that ``tbody``.

    ``section="tfoot"`` puts it in a sibling section libxml2 keeps separate;
    ``section="table"`` leaves it loose as a direct child of ``<table>``. Both
    are ordinary result rows that a reader walking only ``./tbody/tr`` cannot see.
    """
    body = header_row(labels) + "".join(data_row(row) for row in rows)
    extra = data_row(displaced)
    trailing = f"<tfoot>{extra}</tfoot>" if section == "tfoot" else extra
    return f'<table class="{class_attribute}"><tbody>{body}</tbody>{trailing}</table>'


# A pagination control that is not an anchor. The verified single-page block has
# no element children at all, so anything here is a shape no capture has shown —
# and "no ``<a>`` descendants" alone would read it as a finished one-page result.
NON_ANCHOR_CONTROL = '<span class="ink-600 sub">Showing 7 of 7</span>'


def non_anchor_pagination(control: str = NON_ANCHOR_CONTROL) -> str:
    """A ``.pagination`` holding an element child that is not, and holds no, anchor."""
    return f'<div class="pagination">{control}</div>'


def xml_declared_page() -> str:
    """A body whose first bytes are an XML declaration.

    ``parse_document`` is handed a ``str``, and lxml refuses a unicode string
    carrying an encoding declaration outright — a ``ValueError``, not a
    ``ParserError``. It is a real thing a host or proxy can return, and the
    reader has no way to know it is coming.
    """
    return '<?xml version="1.0" encoding="utf-8"?>' + zero_result_page()
