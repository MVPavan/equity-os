"""Builders for the watchlist page markup the ``screener-watchlist`` fixtures serve.

Nothing here is captured markup. Every fragment is built from the *structure*
the live surface was verified to have — one ``tbody`` whose header row repeats
every sixteen data rows, an ``S.No.`` header spanning two columns, a notebook
button cell with no header of its own, value headers whose ``data-tooltip`` is
the full metric name, four company-link shapes, a page-embedded export form, and
a watchlist selector sitting among the site's own decoy dropdowns — with
invented names, codes, ids and numbers throughout.

Builders are self-checking: one that claims to render N rows parses its own
markup back and asserts it found N, because a Slice 3 fixture once produced zero
rows for months without any test noticing.

This is the HTML half of a pair split only because the two halves together
exceed this repo's per-file ceiling. The dependency runs one way, so the two
frozen fixture shapes both halves are built from — :class:`Column` and
:class:`Member` — and the constants used as markup defaults are defined here
rather than beside the CSV builders. :mod:`screener_watchlist_fixtures` holds
the CSV builders, the pinned transport and the acquisition helpers, and
re-exports every name here so test modules keep importing one module.
"""

from __future__ import annotations

import html
from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.screener_session_models import SCREENER_ORIGIN
from fundamentals.ingest.screener_session_page import parse_document

# The synthetic token the page embeds in its export form. Its counterpart cookie
# value lives beside the other cookie constants in ``screener_watchlist_fixtures``:
# the contract forbids ever using the form token as the cookie value, so the two
# must differ for a test to tell them apart.
CSRF_FORM_TOKEN = "fixture-csrf-form-token-9999"
CSRF_FORM_FIELD = "csrfmiddlewaretoken"

WATCHLIST_ID = 4040404
WATCHLIST_NAME = "Fixture Core List"
EXPORT_PATH = "/api/export/screen/"

# The verified live proportions: a header row every sixteen data rows, and
# eighty-three members on one page with no pagination control.
LIVE_MEMBER_COUNT = 83
LIVE_HEADER_BLOCK = 16

TABLE_CLASS = "data-table text-nowrap striped mark-visited no-scroll-right highlight-on-hover"
ACCOUNT_LINK = '<a href="/user/account/">My Account</a>'
LOGOUT_FORM = '<form action="/logout/" method="post"><button>Logout</button></form>'
PAGINATION_BLOCK = (
    '<div class="pagination"><div class="options"><a href="?page=2">2</a></div></div>'
)
PAGE_INFO_BLOCK = "<div data-page-info> 83 results found: Showing page 1 of 1 </div>"


class Column(BaseModel):
    """One value column: the abbreviated visible label and the full-name tooltip."""

    model_config = ConfigDict(frozen=True)

    html_label: str
    tooltip: str


DEFAULT_COLUMNS = (
    Column(html_label="Alpha Rs.", tooltip="Alpha price"),
    Column(html_label="Beta Rs.Cr.", tooltip="Beta capitalisation"),
    Column(html_label="Gamma %", tooltip="Gamma return on capital"),
    Column(html_label="Delta", tooltip="Delta ratio"),
    Column(html_label="Eps / BV", tooltip="Epsilon to book value"),
)
WIDE_COLUMNS = (
    *DEFAULT_COLUMNS,
    Column(html_label="Zeta Qtr Rs.Cr.", tooltip="Zeta latest quarter"),
    Column(html_label="Eta Var 3Yrs %", tooltip="Eta growth 3Years"),
)


class Member(BaseModel):
    """One invented watchlist member as both renderings would carry it."""

    model_config = ConfigDict(frozen=True)

    serial: int
    company_id: int
    name: str
    href: str
    nse_code: str
    bse_code: str
    isin_code: str
    industry_group: str
    industry: str
    values: tuple[str, ...]


def header_cell(column: Column, *, tooltip: bool = True) -> str:
    """One value header: the tooltip on the ``th``, the abbreviation inside a sort link."""
    attribute = f' data-tooltip="{html.escape(column.tooltip, quote=True)}"' if tooltip else ""
    head, _, tail = column.html_label.partition(" ")
    visible = head if not tail else f"{head} <span>{html.escape(tail)}</span>"
    sort_key = column.tooltip.lower().replace(" ", "+")
    return (
        f'<th{attribute} scope="colgroup">'
        f'<a href="?sort={sort_key}&amp;order=desc">{visible}</a></th>'
    )


def header_row(
    columns: tuple[Column, ...],
    *,
    serial_colspan: int | None = 2,
    untooltipped: int | None = None,
    name_tooltip: bool = False,
) -> str:
    """One header row in the live shape: ``S.No.`` spanning two columns, then ``Name``.

    ``serial_colspan=None`` drops the span, which is the shape whose header sum
    no longer equals the data-row cell count. ``untooltipped`` strips the tooltip
    from one value column, and ``name_tooltip`` puts one on ``Name``, which has
    none on the live page.
    """
    span = "" if serial_colspan is None else f' colspan="{serial_colspan}"'
    name_attribute = ' data-tooltip="Company"' if name_tooltip else ""
    cells = [
        f'<th class="text" scope="colgroup"{span}><a href="?sort=&amp;order=">S.No.</a></th>',
        f'<th class="text"{name_attribute} scope="colgroup">'
        '<a href="?sort=name&amp;order=asc">Name</a></th>',
    ]
    cells.extend(
        header_cell(column, tooltip=position != untooltipped)
        for position, column in enumerate(columns)
    )
    return f"<tr>\n{''.join(cells)}\n</tr>"


def value_cell(text: str) -> str:
    """One value cell, padded with the whitespace the live template emits."""
    return f"<td>\n      {html.escape(text)}\n    </td>"


def data_row(
    member: Member,
    *,
    serial_cell: str | None = None,
    row_id: str | None = None,
    href: str | None = None,
    name: str | None = None,
    values: tuple[str, ...] | None = None,
    extra_cell: bool = False,
) -> str:
    """One data row: serial, notebook button, company link, then one cell per column.

    Each override replaces exactly one thing a data row is contracted to carry.
    ``row_id=""`` omits the identity attribute; ``extra_cell`` appends a cell no
    header accounts for.
    """
    written_id = str(member.company_id) if row_id is None else row_id
    identity = f' data-row-company-id="{written_id}"' if written_id else ""
    serial = f"{member.serial}." if serial_cell is None else serial_cell
    link = member.href if href is None else href
    label = html.escape(member.name if name is None else name, quote=True)
    cells = "".join(value_cell(text) for text in (member.values if values is None else values))
    if extra_cell:
        cells += value_cell("0.00")
    return (
        f"<tr{identity}>\n"
        f'    <td class="text">{serial}</td>\n'
        f'    <td><button class="button-plain" data-url="/notebook/{660000 + member.serial}/"'
        ' title="Notebook">notes</button></td>\n'
        f'    <td class="text"><a href="{link}" target="_blank">{label}</a></td>\n'
        f"    {cells}\n"
        "</tr>"
    )


def table_of(rows_html: str) -> str:
    """One watchlist table around hand-written row markup, checked by nobody."""
    return f'<table class="{TABLE_CLASS}">\n<tbody>\n{rows_html}\n</tbody>\n</table>'


def row_shapes(markup: str) -> tuple[int, int, int]:
    """``(header rows, data rows, all rows)`` counted off a table's own markup.

    Read from the fixture rather than from what the reader made of it, so a test
    can prove a fixture really has the live shape before asserting anything about
    how that shape is read. A header row is one whose cells are all ``th``; a data
    row is one carrying ``data-row-company-id``.
    """
    root = parse_document(markup)
    headers = data = total = 0
    for element in root.xpath("(self::table | .//table)//tr"):
        total += 1
        tags = {child.tag for child in element}
        if tags == {"th"}:
            headers += 1
        elif element.get("data-row-company-id") is not None:
            data += 1
    return headers, data, total


def results_table(
    columns: tuple[Column, ...],
    roster: tuple[Member, ...],
    *,
    block: int = LIVE_HEADER_BLOCK,
    header: str | None = None,
    trailing: str = "",
) -> str:
    """A populated table whose header repeats every ``block`` data rows.

    ``header`` replaces every repeat with hand-written markup; ``trailing``
    appends raw row markup after the last member. The result is checked against
    the roster before it is returned.
    """
    head = header_row(columns) if header is None else header
    body: list[str] = []
    for position, member in enumerate(roster):
        if position % block == 0:
            body.append(head)
        body.append(data_row(member))
    markup = table_of("\n".join(body) + trailing)
    headers, data, _ = row_shapes(markup)
    expected_headers = -(-len(roster) // block) if roster else 0
    if not trailing and (headers, data) != (expected_headers, len(roster)):
        raise AssertionError(f"fixture built {headers} headers and {data} rows, not {len(roster)}")
    return markup


def export_action(watchlist_id: int | None = WATCHLIST_ID) -> str:
    """The export form action, unescaped, for one page shape.

    ``None`` is the ``/watchlist/`` default-list shape, whose form carries no id;
    an id is the ``/watchlist/<id>/`` shape.
    """
    if watchlist_id is None:
        return f"{EXPORT_PATH}?url_name=goto_watchlist"
    return f"{EXPORT_PATH}?url_name=goto_sublist&sublist_id={watchlist_id}"


def export_url(watchlist_id: int | None = WATCHLIST_ID) -> str:
    """The absolute URL a browser would post the export form of one page shape to."""
    return f"{SCREENER_ORIGIN}{export_action(watchlist_id)}"


def export_form(action: str, *, token: str = CSRF_FORM_TOKEN) -> str:
    """The page-embedded export form with its hidden CSRF field."""
    return (
        f'<form action="{html.escape(action, quote=True)}" method="post">'
        f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">'
        '<button type="submit">Export</button></form>'
    )


# The live page carries four `dropdown-content` blocks and only one of them is
# the watchlist selector; the others are the site's own nav and promo menus,
# whose <li> entries read as plausible list names. A fixture with a single clean
# dropdown cannot catch a reader that matches them all, so every page built here
# carries decoys, exactly as the source does.
DECOY_DROPDOWNS = (
    '<div class="dropdown-menu"><ul class="dropdown-content">'
    "<li>Create a stock screen Run queries on ten years of data</li>"
    "<li>Premium features</li></ul></div>"
    '<div class="dropdown-menu"><ul class="dropdown-content">'
    "<li>Company Announcements Search and filter the newest disclosures</li>"
    "<li>You are a premium subscriber</li></ul></div>"
)


def dropdown(names: tuple[str, ...], *, selected: int | None = 0) -> str:
    """The watchlist selector: plain entries, one marked by a check icon, plus the add link.

    Wrapped in the `dropdown-watchlist` container the live page uses, because
    that class is the only thing distinguishing this menu from the decoys.
    """
    entries = []
    for position, name in enumerate(names):
        icon = '<i class="icon-ok-circled-1"></i> ' if position == selected else ""
        entries.append(f"<li>{icon}{html.escape(name)}</li>")
    entries.append('<li><a href="/watchlist/add/">+ Create New Watchlist</a></li>')
    return (
        '<div class="dropdown-menu dropdown-watchlist">'
        f'<ul class="dropdown-content">{"".join(entries)}</ul></div>'
    )


def page(
    table: str,
    *,
    watchlist_id: int = WATCHLIST_ID,
    form_action: str | None = None,
    forms: int = 1,
    token: str = CSRF_FORM_TOKEN,
    names: tuple[str, ...] = (WATCHLIST_NAME,),
    selected: int | None = 0,
    account: bool = True,
    logout: bool = True,
    extra: str = "",
) -> str:
    """Wrap one table in the watchlist page around it.

    ``watchlist_id`` is written into the ``/dash/`` and ``/user/stocks/`` links,
    which is where the reader recovers it from on both page shapes.
    ``form_action`` defaults to the ``goto_sublist`` form carrying that id;
    ``forms`` repeats or removes the export form; ``extra`` is injected beside
    the results container, which is where a pagination block would appear.
    """
    action = export_action(watchlist_id) if form_action is None else form_action
    nav = (
        f"<nav>{ACCOUNT_LINK if account else ''}{LOGOUT_FORM if logout else ''}"
        f"{DECOY_DROPDOWNS}</nav>"
    )
    links = (
        f'<a href="/dash/{watchlist_id}/">Dash</a>'
        f'<a href="/user/stocks/?next=/watchlist/{watchlist_id}/">Edit stocks</a>'
        f'<a href="/user/columns/?next=/watchlist/{watchlist_id}/">Edit columns</a>'
    )
    export_forms = export_form(action, token=token) * forms
    container = f'<div class="responsive-holder fill-card-width" data-page-results>{table}</div>'
    return (
        "<html><body>"
        f"{nav}<main>{dropdown(names, selected=selected)}{links}{export_forms}"
        f"{container}{extra}</main></body></html>"
    )


def watchlist_page(
    roster: tuple[Member, ...],
    *,
    columns: tuple[Column, ...] = DEFAULT_COLUMNS,
    block: int = LIVE_HEADER_BLOCK,
    **page_options: Any,
) -> str:
    """A whole page for one roster, in the live shape unless told otherwise."""
    return page(results_table(columns, roster, block=block), **page_options)
