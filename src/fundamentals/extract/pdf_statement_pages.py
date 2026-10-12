"""Locate first-party statement blocks in a results PDF and read their banded rows.

Family-specific discovery for the P&L, balance sheet, cash flow and segment
blocks (D1a Task 11). A page qualifies for a family when, case-insensitively, it
carries the requested basis's marker, one title marker and every confirmation.
Basis is bound per **column**, never per page: results PDFs print consolidated
and standalone columns side by side, so each numeric column belongs to the one
super-header covering its column group, and only the requested basis's columns
are returned. Rows are banded by vertical position; every banded row keeps its
raw cell text, and reading a number out of it is the interpretation's job.

Nothing here is fuzzy: markers match as exact token sequences, a column under no
super-header or two fails the family, and a page whose text layer lacks the
markers is simply not found. No OCR is run.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import Basis, StatementFamily, ValueKind
from fundamentals.extract.pdf_header_text import normalize_text_tokens
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

if TYPE_CHECKING:
    from fundamentals.api.config import PdfParseConfig

ROW_BAND_TOLERANCE_PT = 4.0
COLUMN_EDGE_TOLERANCE_PT = 3.0
HEADER_WORD_GAP_PT = 6.0
_YEAR_TOKEN = re.compile(r"(?:19|20)\d{2}")
_DIGIT = re.compile(r"\d")
DASH_GLYPHS: frozenset[str] = frozenset({"-", "–", "—"})

STANDALONE_MARKER = "Standalone"
INR = "INR"
INR_PER_SHARE = "INR per share"
CRORE_SCALE = 7

_PL_TITLES: tuple[str, ...] = ("Statement of financial results",)
_BS_TITLES: tuple[str, ...] = ("Statement of Assets and Liabilities",)
_CF_TITLES: tuple[str, ...] = ("Cash Flow Statement", "Statement of cash flows")
_SEGMENT_TITLES: tuple[str, ...] = ("Segment",)
_BS_CONFIRMATIONS: tuple[str, ...] = ("Total assets",)
_CF_CONFIRMATIONS: tuple[str, ...] = ("operating activities",)
_SEGMENT_CONFIRMATIONS: tuple[str, ...] = ("Inter-segment",)
_NOTES_MARKER = "Notes"


class UnitScope(StrEnum):
    """How far a printed unit marker reaches."""

    PAGE = "PAGE"
    SUBSECTION = "SUBSECTION"


class UnitMarker(BaseModel):
    """A printed unit marker, matched as an exact token sequence."""

    model_config = ConfigDict(frozen=True)

    text: str
    scope: UnitScope
    raw_unit: str
    raw_scale: int
    value_kind: ValueKind


# Both evidenced on the retained Apar Q2 FY26 results PDF (SHA-256 8be1b8de…4ae5):
# "(Rs. in crores)" on pages 3, 4 and 7; "Earnings per share (EPS) (Rs.)" on page 3.
DEFAULT_UNIT_MARKERS: tuple[UnitMarker, ...] = (
    UnitMarker(
        text="Rs. in crores",
        scope=UnitScope.PAGE,
        raw_unit=INR,
        raw_scale=CRORE_SCALE,
        value_kind=ValueKind.CURRENCY_AMOUNT,
    ),
    UnitMarker(
        text="Earnings per share (EPS) (Rs.)",
        scope=UnitScope.SUBSECTION,
        raw_unit=INR_PER_SHARE,
        raw_scale=0,
        value_kind=ValueKind.PER_SHARE_AMOUNT,
    ),
)


class StatementPageSpec(BaseModel):
    """Markers that identify and bound one statement family's block."""

    model_config = ConfigDict(frozen=True)

    family: StatementFamily
    basis_markers: Mapping[Basis, str]
    title_markers: tuple[str, ...]
    confirmations: tuple[str, ...]
    end_markers: tuple[str, ...]
    unit_markers: tuple[UnitMarker, ...]


class ColumnInterval(BaseModel):
    """One numeric column of a located block, bound to its basis super-header."""

    model_config = ConfigDict(frozen=True)

    index: int
    x0: float
    x1: float
    header_text: str
    basis: Basis
    super_header_text: str
    super_header_x0: float
    super_header_x1: float


class StatementLocation(BaseModel):
    """A bounded statement block on one page, with the requested basis's columns only."""

    model_config = ConfigDict(frozen=True)

    family: StatementFamily
    basis: Basis
    page: int
    top_line: int
    bottom_line: int
    columns: tuple[ColumnInterval, ...]
    excluded_columns: int
    unit_markers: tuple[UnitMarker, ...] = ()


class PdfCell(BaseModel):
    """Raw printed text of one row under one column (empty when nothing is printed)."""

    model_config = ConfigDict(frozen=True)

    column_index: int
    raw_text: str
    column_header: str
    super_header_text: str


class PdfStatementRow(BaseModel):
    """One banded row of a block: its label, resolved unit context and raw cells.

    ``section`` is the label of the nearest heading row above it in the block (a row
    with a label and no figures; empty when there is none); ``label_ordinal`` counts
    rows with the same normalised label in the block up to this one, from 1. Both
    disambiguate repeated labels (e.g. "Conductors" under each segment heading).
    """

    model_config = ConfigDict(frozen=True)

    family: StatementFamily
    page: int
    line: int
    label: str
    unit: UnitMarker | None
    unit_line: int | None
    cells: tuple[PdfCell, ...]
    section: str = ""
    label_ordinal: int = 1


class StatementPageNotFoundError(LookupError):
    """No page, or no unambiguous block layout, for a statement family."""


class _Row(BaseModel):
    """A vertical band of words on one page, in left-to-right order."""

    model_config = ConfigDict(frozen=True)

    index: int
    words: tuple[PageWord, ...]

    @property
    def tokens(self) -> list[str]:
        """Normalised tokens of the row's text."""
        return normalize_text_tokens(" ".join(word.text for word in self.words))


class _Column(BaseModel):
    """A header-row column before basis binding.

    ``header_x0``/``header_x1`` are the printed header's extent; ``x0``/``x1`` widen
    it to the figures printed under it, which are often right-aligned past it.
    """

    model_config = ConfigDict(frozen=True)

    x0: float
    x1: float
    header_x0: float
    header_x1: float
    date_text: str


class _Phrase(BaseModel):
    """Words sharing one text-layer line: a header phrase with its extent."""

    model_config = ConfigDict(frozen=True)

    row: int
    text: str
    x0: float
    x1: float
    word_keys: frozenset[tuple[int, int, int]]


def specs_from_config(pdf_parse: PdfParseConfig) -> Mapping[StatementFamily, StatementPageSpec]:
    """Per-family page specs: P&L from the existing parse block, the rest from defaults.

    An issuer's ``statement_pages`` entry replaces a family's title, confirmation
    or end markers when it sets them, and adds its unit markers to the defaults as
    exact variants (never fuzzy matching).
    """
    basis_markers = {
        Basis.CONSOLIDATED: pdf_parse.scope_marker,
        Basis.STANDALONE: STANDALONE_MARKER,
    }
    defaults: dict[StatementFamily, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
        StatementFamily.PL: (
            _PL_TITLES,
            (*pdf_parse.statement_confirmations, pdf_parse.anchor_label),
            (_NOTES_MARKER, *_SEGMENT_TITLES, *_BS_TITLES, *_CF_TITLES),
        ),
        StatementFamily.BALANCE_SHEET: (
            _BS_TITLES,
            _BS_CONFIRMATIONS,
            (_NOTES_MARKER, *_CF_TITLES),
        ),
        StatementFamily.CASH_FLOW: (_CF_TITLES, _CF_CONFIRMATIONS, (_NOTES_MARKER,)),
        StatementFamily.SEGMENT: (_SEGMENT_TITLES, _SEGMENT_CONFIRMATIONS, (_NOTES_MARKER,)),
    }
    specs: dict[StatementFamily, StatementPageSpec] = {}
    for family, (titles, confirmations, ends) in defaults.items():
        override = pdf_parse.statement_pages.get(family.value)
        specs[family] = StatementPageSpec(
            family=family,
            basis_markers=basis_markers,
            title_markers=(
                override.title_markers if override and override.title_markers else titles
            ),
            confirmations=(
                override.confirmations if override and override.confirmations else confirmations
            ),
            end_markers=override.end_markers if override and override.end_markers else ends,
            unit_markers=(*DEFAULT_UNIT_MARKERS, *(override.unit_markers if override else ())),
        )
    return specs


def locate_statement_pages(
    pdf: LoadedPdf, specs: Mapping[StatementFamily, StatementPageSpec], *, basis: Basis
) -> Mapping[StatementFamily, StatementLocation | None]:
    """Locate every family's block for one basis; ``None`` where it cannot be located."""
    locations: dict[StatementFamily, StatementLocation | None] = {}
    for family, spec in specs.items():
        try:
            locations[family] = locate_statement(pdf, spec, basis=basis)
        except StatementPageNotFoundError:
            locations[family] = None
    return locations


def locate_statement(pdf: LoadedPdf, spec: StatementPageSpec, *, basis: Basis) -> StatementLocation:
    """Locate one family's block, raising with the reason when it cannot be located."""
    marker = spec.basis_markers.get(basis)
    if marker is None:
        raise StatementPageNotFoundError(f"{spec.family}: no marker declared for basis {basis}")
    candidates = [page for page in pdf.pages if _page_qualifies(page, spec, marker)]
    if not candidates:
        raise StatementPageNotFoundError(
            f"{spec.family}: no page carries {marker!r}, a title marker and every confirmation"
        )
    if len(candidates) > 1:
        pages = [page.page_number for page in candidates]
        raise StatementPageNotFoundError(f"{spec.family}: several pages qualify {pages}")
    return _locate_on_page(candidates[0], spec, basis)


def extract_statement_rows(
    pdf: LoadedPdf, location: StatementLocation
) -> tuple[PdfStatementRow, ...]:
    """Every banded row of a located block, with raw text per requested column.

    A row is banded when anything is printed under a column of either basis; its cells keep
    their raw text, clean or not, and a cell with nothing printed is empty (a fully blank
    row in the requested basis is still a row). A row with a label and nothing under any
    column is a section heading.
    """
    page = pdf.page(location.page)
    rows = _page_rows(page)
    header_row, all_columns = _all_columns_for(rows, location)
    markers = _unit_marker_lines(rows, location)
    result: list[PdfStatementRow] = []
    section = ""
    seen_labels: dict[tuple[str, ...], int] = {}
    for row in rows:
        if not header_row < row.index <= location.bottom_line:
            continue
        assigned, label_words = _assign_words(row.words, all_columns)
        label = " ".join(word.text for word in label_words)
        cells = tuple(
            PdfCell(
                column_index=column.index,
                raw_text=" ".join(word.text for word in assigned.get(column.index, ())),
                column_header=column.header_text,
                super_header_text=column.super_header_text,
            )
            for column in location.columns
        )
        if not label and not seen_labels:
            # Unlabelled lines between the dated header and the first labelled row continue
            # the header (the audit-status line "Reviewed / Audited").
            continue
        if not assigned:
            # Nothing printed under any column of either basis: a heading row.
            section = label
            continue
        unit, unit_line = _unit_for_row(row.index, markers, location)
        label_key = tuple(normalize_text_tokens(label))
        seen_labels[label_key] = seen_labels.get(label_key, 0) + 1
        result.append(
            PdfStatementRow(
                family=location.family,
                page=location.page,
                line=row.index,
                label=label,
                unit=unit,
                unit_line=unit_line,
                cells=cells,
                section=section,
                label_ordinal=seen_labels[label_key],
            )
        )
    return tuple(result)


# --- page qualification and block bounds -------------------------------------


def _marker_tokens(text: str) -> list[str]:
    """Normalised tokens of a marker."""
    return normalize_text_tokens(text)


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    """Whether ``needle`` occurs as a contiguous token run in ``haystack``."""
    if not needle:
        return False
    width = len(needle)
    return any(
        list(haystack[i : i + width]) == list(needle) for i in range(len(haystack) - width + 1)
    )


def _page_qualifies(page: PdfPage, spec: StatementPageSpec, basis_marker: str) -> bool:
    """Basis marker, one title marker and every confirmation, all on the page."""
    tokens = normalize_text_tokens(page.text)
    return (
        _contains(tokens, _marker_tokens(basis_marker))
        and any(_contains(tokens, _marker_tokens(title)) for title in spec.title_markers)
        and all(_contains(tokens, _marker_tokens(item)) for item in spec.confirmations)
    )


def _page_rows(page: PdfPage) -> list[_Row]:
    """Band a page's words into rows by vertical centre, top to bottom."""
    ordered = sorted(page.words, key=lambda word: ((word.y0 + word.y1) / 2, word.x0))
    bands: list[list[PageWord]] = []
    anchor = 0.0
    for word in ordered:
        centre = (word.y0 + word.y1) / 2
        if bands and centre - anchor <= ROW_BAND_TOLERANCE_PT:
            bands[-1].append(word)
        else:
            bands.append([word])
            anchor = centre
    return [
        _Row(index=index, words=tuple(sorted(band, key=lambda word: word.x0)))
        for index, band in enumerate(bands)
    ]


def _first_row_matching(rows: Sequence[_Row], markers: Sequence[str], *, after: int) -> _Row | None:
    """The first row below ``after`` carrying any of the markers."""
    wanted = [_marker_tokens(marker) for marker in markers]
    for row in rows:
        if row.index > after and any(_contains(row.tokens, tokens) for tokens in wanted):
            return row
    return None


def _locate_on_page(page: PdfPage, spec: StatementPageSpec, basis: Basis) -> StatementLocation:
    """Bound the block, find its header row and bind columns to super-headers."""
    rows = _page_rows(page)
    title = _first_row_matching(rows, spec.title_markers, after=-1)
    if title is None:
        raise StatementPageNotFoundError(
            f"{spec.family}: page {page.page_number} has no single line with a title marker"
        )
    end = _first_row_matching(rows, spec.end_markers, after=title.index)
    bottom = end.index - 1 if end is not None else rows[-1].index
    block = [row for row in rows if title.index < row.index <= bottom]
    header_row, columns = _block_layout(block)
    if header_row is None:
        raise StatementPageNotFoundError(
            f"{spec.family}: page {page.page_number} has no dated column header row"
        )
    bound = _bind_columns(block, header_row, columns, spec, page.page_number)
    wanted = tuple(column for column in bound if column.basis is basis)
    if not wanted:
        raise StatementPageNotFoundError(
            f"{spec.family}: page {page.page_number} has no column under the {basis} super-header"
        )
    return StatementLocation(
        family=spec.family,
        basis=basis,
        page=page.page_number,
        top_line=title.index,
        bottom_line=bottom,
        columns=wanted,
        excluded_columns=len(bound) - len(wanted),
        unit_markers=spec.unit_markers,
    )


# --- columns ------------------------------------------------------------------


def _header_columns(block: Sequence[_Row]) -> tuple[_Row | None, list[_Column]]:
    """The first row with two or more dated column headers, and those columns.

    A column header is a run of adjacent words closed by a word carrying a year; a
    wide gap starts a new run, so a label word between groups never joins one.
    """
    for row in block:
        columns: list[_Column] = []
        run: list[PageWord] = []
        for word in row.words:
            if run and word.x0 - run[-1].x1 > HEADER_WORD_GAP_PT:
                run = []
            run.append(word)
            if _YEAR_TOKEN.search(word.text):
                columns.append(
                    _Column(
                        x0=run[0].x0,
                        x1=run[-1].x1,
                        header_x0=run[0].x0,
                        header_x1=run[-1].x1,
                        date_text=" ".join(item.text for item in run),
                    )
                )
                run = []
        if len(columns) >= 2:
            return row, columns
    return None, []


def _block_layout(block: Sequence[_Row]) -> tuple[_Row | None, list[_Column]]:
    """The block's header row and its columns, widened to the figures printed under them."""
    header_row, columns = _header_columns(block)
    if header_row is None:
        return None, []
    figures = [
        word
        for row in block
        if row.index > header_row.index
        for word in row.words
        if _DIGIT.search(word.text) or word.text in DASH_GLYPHS
    ]
    widened: list[_Column] = []
    for column in columns:
        under = [
            word
            for word in figures
            if column.header_x0 <= (word.x0 + word.x1) / 2 <= column.header_x1
        ]
        widened.append(
            column.model_copy(
                update={
                    "x0": min([column.header_x0, *(word.x0 for word in under)]),
                    "x1": max([column.header_x1, *(word.x1 for word in under)]),
                }
            )
        )
    return header_row, widened


def _column_of(word: PageWord, columns: Sequence[_Column | ColumnInterval]) -> int | None:
    """Index of the column holding the word's horizontal centre, if any."""
    centre = (word.x0 + word.x1) / 2
    best: tuple[float, int] | None = None
    for index, column in enumerate(columns):
        if column.x0 - COLUMN_EDGE_TOLERANCE_PT <= centre <= column.x1 + COLUMN_EDGE_TOLERANCE_PT:
            distance = abs(centre - (column.x0 + column.x1) / 2)
            if best is None or distance < best[0]:
                best = (distance, index)
    return None if best is None else best[1]


def _word_key(word: PageWord) -> tuple[int, int, int]:
    """Identity of one word in the page's text layer."""
    return (word.block, word.line, word.word_no)


def _phrases(rows: Sequence[_Row]) -> list[_Phrase]:
    """Header phrases: each text-layer line within a row, with its horizontal extent."""
    phrases: list[_Phrase] = []
    for row in rows:
        lines: dict[tuple[int, int], list[PageWord]] = {}
        for word in row.words:
            lines.setdefault((word.block, word.line), []).append(word)
        for words in lines.values():
            ordered = sorted(words, key=lambda word: word.x0)
            phrases.append(
                _Phrase(
                    row=row.index,
                    text=" ".join(word.text for word in ordered),
                    x0=ordered[0].x0,
                    x1=ordered[-1].x1,
                    word_keys=frozenset(_word_key(word) for word in ordered),
                )
            )
    return phrases


def _bind_columns(
    block: Sequence[_Row],
    header_row: _Row,
    columns: Sequence[_Column],
    spec: StatementPageSpec,
    page_number: int,
) -> list[ColumnInterval]:
    """Bind every column to the one basis super-header covering its column group."""
    first_data = next(
        (
            row
            for row in block
            if row.index > header_row.index
            and any(
                _is_numeric_text(" ".join(words))
                for words in _cell_texts(row.words, columns).values()
            )
        ),
        None,
    )
    data_rows = [row for row in block if first_data is not None and row.index >= first_data.index]
    header_rows = [
        row
        for row in block
        if row.index < (first_data.index if first_data is not None else block[-1].index + 1)
    ]
    groups = _column_groups(columns, data_rows)
    phrases = _phrases(header_rows)
    supers = _super_headers(phrases, spec)
    units = {
        key
        for phrase in phrases
        if any(
            _contains(normalize_text_tokens(phrase.text), _marker_tokens(m.text))
            for m in spec.unit_markers
        )
        for key in phrase.word_keys
    }
    excluded = units | {key for _, phrase in supers for key in phrase.word_keys}
    bound: list[ColumnInterval] = []
    for group in groups:
        x0, x1 = columns[group[0]].x0, columns[group[-1]].x1
        covering = [
            (basis, phrase)
            for basis, phrase in supers
            if x0 - COLUMN_EDGE_TOLERANCE_PT
            <= (phrase.x0 + phrase.x1) / 2
            <= x1 + COLUMN_EDGE_TOLERANCE_PT
        ]
        if len(covering) != 1:
            raise StatementPageNotFoundError(
                f"{spec.family}: page {page_number} column group {x0:.0f}-{x1:.0f} lies under "
                f"{len(covering)} basis super-headers"
            )
        basis, phrase = covering[0]
        for index in group:
            column = columns[index]
            bound.append(
                ColumnInterval(
                    index=index,
                    x0=column.x0,
                    x1=column.x1,
                    header_text=_column_header_text(column, header_row, phrases, excluded),
                    basis=basis,
                    super_header_text=phrase.text,
                    super_header_x0=phrase.x0,
                    super_header_x1=phrase.x1,
                )
            )
    return bound


def _column_groups(columns: Sequence[_Column], data_rows: Sequence[_Row]) -> list[list[int]]:
    """Runs of adjacent columns with no label word printed between them."""
    label_centres = [
        (word.x0 + word.x1) / 2
        for row in data_rows
        for word in row.words
        if _column_of(word, columns) is None
    ]
    groups: list[list[int]] = [[0]]
    for index in range(1, len(columns)):
        left, right = columns[index - 1].x1, columns[index].x0
        if any(left < centre < right for centre in label_centres):
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def _super_headers(
    phrases: Sequence[_Phrase], spec: StatementPageSpec
) -> list[tuple[Basis, _Phrase]]:
    """Header phrases naming exactly one basis marker."""
    found: list[tuple[Basis, _Phrase]] = []
    for phrase in phrases:
        tokens = normalize_text_tokens(phrase.text)
        named = [
            basis
            for basis, marker in spec.basis_markers.items()
            if _contains(tokens, _marker_tokens(marker))
        ]
        if len(named) == 1:
            found.append((named[0], phrase))
    return found


def _column_header_text(
    column: _Column,
    header_row: _Row,
    phrases: Sequence[_Phrase],
    excluded: frozenset[tuple[int, int, int]] | set[tuple[int, int, int]],
) -> str:
    """Header phrases overlapping the column, top to bottom, with its own date words."""
    parts: list[str] = []
    for phrase in sorted(phrases, key=lambda item: (item.row, item.x0)):
        if phrase.row == header_row.index:
            if not parts or parts[-1] != column.date_text:
                parts.append(column.date_text)
            continue
        if phrase.word_keys & excluded:
            continue
        if phrase.x0 <= column.header_x1 and column.header_x0 <= phrase.x1:
            parts.append(phrase.text)
    if column.date_text not in parts:
        parts.append(column.date_text)
    return " ".join(parts)


def _all_columns_for(
    rows: Sequence[_Row], location: StatementLocation
) -> tuple[int, list[_Column]]:
    """The block's header line and every header column (both bases).

    Excluded-basis columns are kept here so their cells never join a row label.
    """
    block = [row for row in rows if location.top_line < row.index <= location.bottom_line]
    header_row, columns = _block_layout(block)
    if header_row is None:
        raise StatementPageNotFoundError(f"{location.family}: located block lost its header row")
    return header_row.index, columns


def _cell_texts(words: Sequence[PageWord], columns: Sequence[_Column]) -> dict[int, list[str]]:
    """Word texts per column index for one row."""
    texts: dict[int, list[str]] = {}
    for word in words:
        index = _column_of(word, columns)
        if index is not None:
            texts.setdefault(index, []).append(word.text)
    return texts


def _assign_words(
    words: Sequence[PageWord], columns: Sequence[_Column]
) -> tuple[dict[int, list[PageWord]], list[PageWord]]:
    """Split a row's words into per-column cells and label words."""
    assigned: dict[int, list[PageWord]] = {}
    labels: list[PageWord] = []
    for word in words:
        index = _column_of(word, columns)
        if index is None:
            labels.append(word)
        else:
            assigned.setdefault(index, []).append(word)
    return assigned, labels


def _is_numeric_text(text: str) -> bool:
    """A cell that prints a figure: any digit, or a lone dash glyph."""
    stripped = text.strip()
    return bool(_DIGIT.search(stripped)) or stripped in DASH_GLYPHS


# --- units --------------------------------------------------------------------


def _unit_marker_lines(
    rows: Sequence[_Row], location: StatementLocation
) -> list[tuple[int, UnitMarker]]:
    """Unit markers found on the page: page markers anywhere, subsection markers in-block."""
    found: list[tuple[int, UnitMarker]] = []
    for row in rows:
        for marker in location.unit_markers:
            if not _contains(row.tokens, _marker_tokens(marker.text)):
                continue
            in_block = location.top_line < row.index <= location.bottom_line
            if marker.scope is UnitScope.PAGE or in_block:
                found.append((row.index, marker))
    return found


def _unit_for_row(
    line: int, markers: Sequence[tuple[int, UnitMarker]], location: StatementLocation
) -> tuple[UnitMarker | None, int | None]:
    """The nearest preceding unit marker for a row; a subsection marker wins a tie."""
    preceding = [
        (marker_line, marker)
        for marker_line, marker in markers
        if marker_line <= line
        and (marker.scope is UnitScope.PAGE or marker_line > location.top_line)
    ]
    if not preceding:
        return None, None
    marker_line, marker = max(
        preceding, key=lambda item: (item[0], item[1].scope is UnitScope.SUBSECTION)
    )
    return marker, marker_line
