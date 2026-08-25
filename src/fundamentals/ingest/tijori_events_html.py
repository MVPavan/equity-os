"""Rendered-HTML collection for Tijori's site-level and timeline event surfaces.

Three of the five event surfaces are server-rendered markup rather than JSON
islands, and two of them nest a table inside a cell of another table. A flat
stream reader cannot address that, so this module builds a trimmed element tree
once and then reads each surface off it declaratively. The tree is parser state,
not a contract: only the reduced, frozen per-surface shapes below leave here.

Two deliberate omissions keep this layer honest:

* ``<svg>`` subtrees are dropped while parsing. They are decoration, they are the
  bulk of these documents, and nothing addressable is inside them.
* JSON island BODIES are not read here. This parser converts character
  references — the markup IS the data on these pages — which would corrupt a JSON
  payload. Island ids found inside an event are recorded, and the bodies are
  decoded by the committed island loader in :mod:`fundamentals.ingest.tijori_page`.

The typed contracts, anchors, and identity/auth gates live in
:mod:`fundamentals.ingest.tijori_events`.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.tijori_events_models import (
    MAX_ELEMENT_DEPTH,
    TijoriEventsSchemaError,
)

TABLE_TAG = "table"
ROW_TAG = "tr"
HEADER_CELL_TAG = "th"
DATA_CELL_TAG = "td"
ANCHOR_TAG = "a"
DIV_TAG = "div"
SPAN_TAG = "span"
SCRIPT_TAG = "script"

RESULTS_CONTAINER_ID = "results"
RESULT_ITEM_CLASS = "result_item"
TABLE_LOADER_CLASS = "table_loader"
LOADER_ROW_CLASS = "loader_row"
PAGINATION_CLASS = "pagination"
CURRENT_STATE_CLASS = "current_state"
DESKTOP_CLASS = "desktop"

_SLUG_ATTRIBUTE = "data-slug"
_ROW_ID_ATTRIBUTE = "data-id"
_GROUP_ATTRIBUTE = "data-grp"
_EVENT_NAME_ATTRIBUTE = "data-name"
_COMPANY_ID_ATTRIBUTE = "company-id"
_CLASS_ATTRIBUTE = "class"
_ID_ATTRIBUTE = "id"
_HREF_ATTRIBUTE = "href"
_TYPE_ATTRIBUTE = "type"

_COLLAPSED_ROW_CLASS = "collapsedrow"
_COMPANY_CELL_CLASS = "company"
_EVENT_CELL_CLASS = "event"
_CONTENT_CELL_CLASS = "content"
_TIMESTAMP_CELL_CLASS = "timestamp"
_COMPANY_LINK_CLASS = "comp-link"
_COMPANY_DATE_CLASS = "company_date"
_EVENT_DATE_CLASS = "event_date"
_METRICS_CLASS = "metrics"
_LABEL_CLASS = "label"
_VALUE_CLASS = "value"
_ITEM_FOOTER_CLASS = "result_item__footer"
_SYMBOL_CLASS = "symbol"
_JSON_CONTENT_TYPE = "application/json"

_SVG_TAG = "svg"
_STYLE_TAG = "style"
_UNRENDERED_TEXT_TAGS = frozenset({SCRIPT_TAG, _STYLE_TAG})
_PAGE_SHELL_TAGS = frozenset({"html", "body", "head"})
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_ROOT_TAG = "#document"
_COMPANY_HREF = re.compile(r"^/company/([^/#?]+)")


class _El:
    """One retained element of the trimmed tree. Mutable parser state, not data."""

    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_El | str] = []

    def attr(self, name: str) -> str | None:
        """Read one attribute value, or ``None`` when the element lacks it."""
        return self.attrs.get(name)

    def classes(self) -> frozenset[str]:
        """Read this element's CSS class tokens."""
        raw = self.attrs.get(_CLASS_ATTRIBUTE)
        return frozenset() if raw is None else frozenset(raw.split())


class _TreeParser(HTMLParser):
    """Build a trimmed element tree, dropping ``<svg>`` subtrees entirely.

    Character references are converted because this markup is the data: a
    quarter label carries ``&#x27;`` and a detail link carries ``&rarr;``.

    Nesting is bounded at :data:`MAX_ELEMENT_DEPTH`. Every reader below walks
    this tree recursively, so an unbounded document — malicious, or merely
    pathological through unclosed tags — would exhaust the interpreter stack
    somewhere downstream and surface as an untyped ``RecursionError``. Refusing
    at a documented depth turns that into a named refusal at the boundary, the
    same way the financial tables bound their sub-section nesting.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _El(_ROOT_TAG, {})
        self._open: list[_El] = [self.root]
        self._svg_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open one element, or enter/deepen a dropped ``<svg>`` subtree."""
        if self._svg_depth or tag == _SVG_TAG:
            self._svg_depth += 1
            return
        if len(self._open) > MAX_ELEMENT_DEPTH:
            raise TijoriEventsSchemaError(
                f"tijori event document nests elements more than {MAX_ELEMENT_DEPTH} deep "
                f"at <{tag}>; refusing to walk a document this adapter cannot bound"
            )
        element = _El(tag, {key: value or "" for key, value in attrs})
        self._open[-1].children.append(element)
        if tag not in _VOID_TAGS:
            self._open.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add one self-closing element without opening it."""
        if self._svg_depth or tag == _SVG_TAG:
            return
        self._open[-1].children.append(_El(tag, {key: value or "" for key, value in attrs}))

    def handle_endtag(self, tag: str) -> None:
        """Close the innermost matching element, tolerating unbalanced markup."""
        if self._svg_depth:
            self._svg_depth -= 1
            return
        for depth in range(len(self._open) - 1, 0, -1):
            if self._open[depth].tag == tag:
                del self._open[depth:]
                return

    def handle_data(self, data: str) -> None:
        """Attach one text run to the element currently open."""
        if self._svg_depth or not data.strip():
            return
        self._open[-1].children.append(data)


def parse_tree(document: str) -> _El:
    """Parse one document or fragment into its trimmed element tree."""
    parser = _TreeParser()
    parser.feed(document)
    parser.close()
    return parser.root


def collapse(text: str) -> str:
    """Collapse rendered whitespace without altering the visible lexeme."""
    return " ".join(text.split())


def text_of(element: _El) -> str:
    """Read one element's whole rendered text, collapsed."""
    parts: list[str] = []
    _text_into(element, parts)
    return collapse("".join(parts))


def _text_into(element: _El, parts: list[str]) -> None:
    """Accumulate every text run below one element, in rendered order.

    ``<script>`` and ``<style>`` bodies are excluded: a stylesheet is not
    rendered text, and an island payload is already retained verbatim beside its
    own anchor, so folding it into an event's text would duplicate it as prose.
    """
    if element.tag in _UNRENDERED_TEXT_TAGS:
        return
    for child in element.children:
        if isinstance(child, str):
            parts.append(child)
            parts.append(" ")
        else:
            _text_into(child, parts)


def elements(element: _El) -> tuple[_El, ...]:
    """The element children of one element, in rendered order."""
    return tuple(child for child in element.children if isinstance(child, _El))


def find_all(element: _El, tag: str | None = None, css_class: str | None = None) -> tuple[_El, ...]:
    """Every descendant matching a tag name and/or a CSS class token."""
    found: list[_El] = []
    _find_into(element, tag, css_class, found)
    return tuple(found)


def _find_into(element: _El, tag: str | None, css_class: str | None, found: list[_El]) -> None:
    """Depth-first collection of descendants matching tag and class."""
    for child in elements(element):
        if (tag is None or child.tag == tag) and (
            css_class is None or css_class in child.classes()
        ):
            found.append(child)
        _find_into(child, tag, css_class, found)


def find_first(element: _El, tag: str | None = None, css_class: str | None = None) -> _El | None:
    """The first descendant matching a tag name and/or a CSS class token."""
    found = find_all(element, tag, css_class)
    return found[0] if found else None


def find_by_id(element: _El, element_id: str) -> _El | None:
    """The first descendant carrying one rendered DOM id."""
    for child in elements(element):
        if child.attr(_ID_ATTRIBUTE) == element_id:
            return child
        found = find_by_id(child, element_id)
        if found is not None:
            return found
    return None


def carries_page_shell(root: _El) -> bool:
    """True when a supposed fragment actually rendered a whole page.

    Only the ROOT's own children are inspected. FACT (owner capture,
    2026-08-25): Tijori embeds a complete ``<!DOCTYPE html>`` document inside the
    content cell of some timeline events, so a document-wide search for a shell
    tag would condemn a perfectly good fragment. A real page puts its shell at
    the top; an embedded one never can.
    """
    return any(element.tag in _PAGE_SHELL_TAGS for element in elements(root))


def company_slug(href: str | None) -> str | None:
    """Read the company slug out of one ``/company/<slug>/`` link."""
    if href is None:
        return None
    match = _COMPANY_HREF.match(href.strip())
    return match.group(1) if match is not None else None


class RawCompanyLink(BaseModel):
    """One rendered company reference: its display name and its link."""

    model_config = ConfigDict(frozen=True)

    name: str
    href: str | None = None
    slug: str | None = None
    symbol_text: str | None = None


class RawListingRow(BaseModel):
    """One rendered listing row reduced to its company and its cell lexemes."""

    model_config = ConfigDict(frozen=True)

    company: RawCompanyLink
    cell_texts: tuple[str, ...]
    alternate_texts: tuple[str, ...] = ()


class RawPagination(BaseModel):
    """The listing's own declared counts, as rendered."""

    model_config = ConfigDict(frozen=True)

    shown: int | None = None
    total: int | None = None


class RawListing(BaseModel):
    """One market-wide listing table reduced to what can be addressed."""

    model_config = ConfigDict(frozen=True)

    column_labels: tuple[str, ...]
    rows: tuple[RawListingRow, ...]
    malformed_rows: tuple[str, ...] = ()
    pagination: RawPagination = RawPagination()
    lazy_tables: tuple[str, ...] = ()


class RawResultTable(BaseModel):
    """One rendered comparison table: header labels and label-led rows."""

    model_config = ConfigDict(frozen=True)

    column_labels: tuple[str, ...] = ()
    row_labels: tuple[str, ...] = ()
    row_values: tuple[tuple[str, ...], ...] = ()


class RawResultItem(BaseModel):
    """One announced result reduced to its header, metrics, and table."""

    model_config = ConfigDict(frozen=True)

    company: RawCompanyLink
    announced_text: str
    metric_labels: tuple[str, ...] = ()
    metric_values: tuple[str, ...] = ()
    table: RawResultTable = RawResultTable()
    detail_href: str | None = None


class RawResultsPage(BaseModel):
    """The quarterly-results listing reduced to its items and its counts."""

    model_config = ConfigDict(frozen=True)

    items: tuple[RawResultItem, ...]
    pagination: RawPagination = RawPagination()
    lazy_tables: tuple[str, ...] = ()


class RawDetailTable(BaseModel):
    """One table rendered inside a timeline event's content cell."""

    model_config = ConfigDict(frozen=True)

    table_class: str | None = None
    column_labels: tuple[str, ...] = ()
    row_values: tuple[tuple[str, ...], ...] = ()


class RawTimelineEvent(BaseModel):
    """One rendered timeline event row reduced to its addressable parts."""

    model_config = ConfigDict(frozen=True)

    row_id: str
    group_id: str | None = None
    is_grouped_child: bool = False
    company: RawCompanyLink
    event_name: str
    event_company_id_text: str | None = None
    announced_text: str | None = None
    detail_tables: tuple[RawDetailTable, ...] = ()
    island_ids: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    content_text: str = ""


class RawTimelineFragment(BaseModel):
    """The per-company timeline fragment reduced to its event rows.

    ``page_shell`` is True when the response was a whole HTML document rather
    than the bare fragment. That is not a fragment with no events — it is a
    different response, and the caller refuses it rather than reporting empty.

    ``row_count`` counts every ``tr[data-id]`` the fragment rendered, whether it
    survived as an event or was quarantined. It is the POSITIVE evidence the
    caller gates on: a response with no such row proves nothing about the
    company's timeline, so it is refused rather than reported as empty.
    """

    model_config = ConfigDict(frozen=True)

    events: tuple[RawTimelineEvent, ...]
    malformed_rows: tuple[str, ...] = ()
    page_shell: bool = False
    row_count: int = 0


def _lazy_table_classes(root: _El) -> tuple[str, ...]:
    """Name every hidden pagination loader shell the page also rendered."""
    return tuple(
        table.attr(_CLASS_ATTRIBUTE) or ""
        for table in find_all(root, TABLE_TAG, TABLE_LOADER_CLASS)
    )


def _pagination(root: _El) -> RawPagination:
    """Read the listing's declared 'showing N of M' counts when it renders them."""
    block = find_first(root, DIV_TAG, PAGINATION_CLASS)
    if block is None:
        return RawPagination()
    state = find_first(block, DIV_TAG, CURRENT_STATE_CLASS)
    if state is None:
        return RawPagination()
    counts = [_as_count(text_of(span)) for span in find_all(state, SPAN_TAG)]
    shown = counts[0] if counts else None
    total = counts[1] if len(counts) > 1 else None
    return RawPagination(shown=shown, total=total)


def _as_count(text: str) -> int | None:
    """Read one rendered count, tolerating thousands commas only."""
    candidate = text.replace(",", "").strip()
    return int(candidate) if candidate.isdigit() else None


def _company_link(cell: _El) -> RawCompanyLink:
    """Read one company reference out of a rendered cell."""
    anchor = find_first(cell, ANCHOR_TAG)
    symbol = find_first(cell, DIV_TAG, _SYMBOL_CLASS)
    href = None if anchor is None else anchor.attr(_HREF_ATTRIBUTE)
    return RawCompanyLink(
        name=text_of(cell) if anchor is None else text_of(anchor),
        href=href,
        slug=company_slug(href),
        symbol_text=None if symbol is None else text_of(symbol),
    )


def _cell_texts(cells: tuple[_El, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split each rendered cell into its primary lexeme and its alternates.

    A cell may render the same value twice — a desktop and a mobile date, a
    company name and its symbol badge. The primary reading is the desktop
    variant, or the linked name, or the whole cell; every other rendered block is
    kept as an alternate rather than concatenated into the primary or dropped.
    """
    primaries: list[str] = []
    alternates: list[str] = []
    for cell in cells:
        desktop = find_first(cell, DIV_TAG, DESKTOP_CLASS)
        anchor = find_first(cell, ANCHOR_TAG)
        primary_element = desktop if desktop is not None else anchor
        whole = text_of(cell)
        if primary_element is None:
            primaries.append(whole)
            continue
        primary = text_of(primary_element)
        primaries.append(primary)
        remainder = collapse(whole.replace(primary, " ", 1))
        if remainder:
            alternates.append(remainder)
    return tuple(primaries), tuple(alternates)


def collect_upcoming(document: str) -> RawListing:
    """Reduce the upcoming-events page to its one visible listing table.

    The visible table carries no id of its own, so it is selected by the
    ``#results`` container it is rendered into — the hidden ``*_loader`` shells
    are siblings of that container, not descendants, which is exactly what makes
    the container a usable selector.
    """
    root = parse_tree(document)
    container = find_by_id(root, RESULTS_CONTAINER_ID)
    if container is None:
        raise TijoriEventsSchemaError(
            f"tijori upcoming-events page has no #{RESULTS_CONTAINER_ID} container"
        )
    table = find_first(container, TABLE_TAG)
    if table is None:
        raise TijoriEventsSchemaError(
            f"tijori upcoming-events #{RESULTS_CONTAINER_ID} container renders no table"
        )
    column_labels = tuple(text_of(header) for header in find_all(table, HEADER_CELL_TAG))
    rows: list[RawListingRow] = []
    malformed: list[str] = []
    for row in find_all(table, ROW_TAG):
        cells = find_all(row, DATA_CELL_TAG)
        if not cells:
            continue
        slug = row.attr(_SLUG_ATTRIBUTE)
        if slug is None:
            malformed.append(f"{text_of(row)!r} (missing {_SLUG_ATTRIBUTE})")
            continue
        primaries, alternates = _cell_texts(cells)
        rows.append(
            RawListingRow(
                company=_company_link(cells[0]),
                cell_texts=primaries,
                alternate_texts=alternates,
            )
        )
    return RawListing(
        column_labels=column_labels,
        rows=tuple(rows),
        malformed_rows=tuple(malformed),
        pagination=_pagination(container),
        lazy_tables=_lazy_table_classes(root),
    )


def _result_table(item: _El) -> RawResultTable:
    """Reduce one result item's comparison table to labels and lexemes."""
    table = find_first(item, TABLE_TAG)
    if table is None:
        return RawResultTable()
    column_labels = tuple(text_of(header) for header in find_all(table, HEADER_CELL_TAG))
    labels: list[str] = []
    values: list[tuple[str, ...]] = []
    for row in find_all(table, ROW_TAG):
        cells = find_all(row, DATA_CELL_TAG)
        if not cells:
            continue
        labels.append(text_of(cells[0]))
        values.append(tuple(text_of(cell) for cell in cells[1:]))
    return RawResultTable(
        column_labels=column_labels, row_labels=tuple(labels), row_values=tuple(values)
    )


def collect_quarterly_results(document: str) -> RawResultsPage:
    """Reduce the quarterly-results page to one entry per announced result."""
    root = parse_tree(document)
    items: list[RawResultItem] = []
    for item in find_all(root, DIV_TAG, RESULT_ITEM_CLASS):
        header = find_first(item, DIV_TAG, _COMPANY_DATE_CLASS)
        if header is None:
            raise TijoriEventsSchemaError(
                "tijori quarterly-results item renders no company/date header"
            )
        announced = find_first(header, SPAN_TAG, _EVENT_DATE_CLASS)
        metrics = find_first(item, DIV_TAG, _METRICS_CLASS)
        footer = find_first(item, DIV_TAG, _ITEM_FOOTER_CLASS)
        detail_anchor = None if footer is None else find_first(footer, ANCHOR_TAG)
        items.append(
            RawResultItem(
                company=_company_link(header),
                announced_text="" if announced is None else text_of(announced),
                metric_labels=(
                    ()
                    if metrics is None
                    else tuple(text_of(span) for span in find_all(metrics, SPAN_TAG, _LABEL_CLASS))
                ),
                metric_values=(
                    ()
                    if metrics is None
                    else tuple(text_of(span) for span in find_all(metrics, SPAN_TAG, _VALUE_CLASS))
                ),
                table=_result_table(item),
                detail_href=(
                    None if detail_anchor is None else detail_anchor.attr(_HREF_ATTRIBUTE)
                ),
            )
        )
    return RawResultsPage(
        items=tuple(items), pagination=_pagination(root), lazy_tables=_lazy_table_classes(root)
    )


def _detail_tables(content: _El) -> tuple[RawDetailTable, ...]:
    """Reduce every table rendered inside one event's content cell.

    No label column is assumed: Tijori's ``dict-table`` renders a header row of
    period names beside a row-spanning title, and its value row carries no title
    at all. Every rendered cell is therefore kept as a cell, in rendered order.
    """
    tables: list[RawDetailTable] = []
    for table in find_all(content, TABLE_TAG):
        rows: list[tuple[str, ...]] = []
        for row in find_all(table, ROW_TAG):
            cells = find_all(row, DATA_CELL_TAG)
            if cells:
                rows.append(tuple(text_of(cell) for cell in cells))
        tables.append(
            RawDetailTable(
                table_class=table.attr(_CLASS_ATTRIBUTE),
                column_labels=tuple(text_of(header) for header in find_all(table, HEADER_CELL_TAG)),
                row_values=tuple(rows),
            )
        )
    return tuple(tables)


def _island_ids(content: _El) -> tuple[str, ...]:
    """Name every JSON island rendered inside one event's content cell."""
    return tuple(
        island_id
        for script in find_all(content, SCRIPT_TAG)
        if (script.attr(_TYPE_ATTRIBUTE) or "").strip().lower() == _JSON_CONTENT_TYPE
        and (island_id := script.attr(_ID_ATTRIBUTE) or "")
    )


def _timeline_cells(row: _El) -> tuple[_El | None, _El | None, _El | None, _El | None]:
    """Locate one event row's company, event, content, and timestamp cells."""
    company_cell: _El | None = None
    event_cell: _El | None = None
    content_cell: _El | None = None
    timestamp_cell: _El | None = None
    for cell in find_all(row, DATA_CELL_TAG):
        classes = cell.classes()
        if company_cell is None and _COMPANY_CELL_CLASS in classes:
            company_cell = cell
        elif event_cell is None and _EVENT_CELL_CLASS in classes:
            event_cell = cell
        elif content_cell is None and _CONTENT_CELL_CLASS in classes:
            content_cell = cell
        elif timestamp_cell is None and _TIMESTAMP_CELL_CLASS in classes:
            timestamp_cell = cell
    return company_cell, event_cell, content_cell, timestamp_cell


def collect_company_timeline(fragment: str) -> RawTimelineFragment:
    """Reduce the per-company timeline fragment to its rendered event rows.

    Only rows carrying ``data-id`` are events: the fragment nests a presentation
    table inside each event row, and those inner rows are unaddressable layout.
    """
    root = parse_tree(fragment)
    events: list[RawTimelineEvent] = []
    malformed: list[str] = []
    row_count = 0
    for row in find_all(root, ROW_TAG):
        row_id = row.attr(_ROW_ID_ATTRIBUTE)
        if row_id is None:
            continue
        row_count += 1
        company_cell, event_cell, content_cell, timestamp_cell = _timeline_cells(row)
        if company_cell is None or event_cell is None or content_cell is None:
            malformed.append(f"{row_id!r} (missing company, event, or content cell)")
            continue
        event_name = event_cell.attr(_EVENT_NAME_ATTRIBUTE)
        if event_name is None or not event_name.strip():
            malformed.append(f"{row_id!r} (missing {_EVENT_NAME_ATTRIBUTE})")
            continue
        company_anchor = find_first(company_cell, ANCHOR_TAG, _COMPANY_LINK_CLASS)
        href = None if company_anchor is None else company_anchor.attr(_HREF_ATTRIBUTE)
        timestamp_text = None if timestamp_cell is None else text_of(timestamp_cell)
        events.append(
            RawTimelineEvent(
                row_id=row_id,
                group_id=row.attr(_GROUP_ATTRIBUTE),
                is_grouped_child=_COLLAPSED_ROW_CLASS in row.classes(),
                company=RawCompanyLink(
                    name=(
                        text_of(company_cell) if company_anchor is None else text_of(company_anchor)
                    ),
                    href=href,
                    slug=company_slug(href),
                ),
                event_name=event_name.strip(),
                event_company_id_text=content_cell.attr(_COMPANY_ID_ATTRIBUTE),
                announced_text=timestamp_text or None,
                detail_tables=_detail_tables(content_cell),
                island_ids=_island_ids(content_cell),
                links=tuple(
                    href
                    for anchor in find_all(content_cell, ANCHOR_TAG)
                    if (href := anchor.attr(_HREF_ATTRIBUTE))
                ),
                content_text=text_of(content_cell),
            )
        )
    return RawTimelineFragment(
        events=tuple(events),
        malformed_rows=tuple(malformed),
        page_shell=carries_page_shell(root),
        row_count=row_count,
    )


def json_island_ids(document: str) -> tuple[str, ...]:
    """Name every JSON island the document renders, in rendered order.

    The company fragment keys its islands by numeric EVENT id, so the ids cannot
    be known before the document is read. This discovery pass supplies them to
    the committed island loader, which owns the decoding.
    """
    root = parse_tree(document)
    return _island_ids(root)
