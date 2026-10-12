"""Capture bytes to lossless PDF occurrences per statement family (D1a Task 5).

One occurrence per banded row × requested-basis column of each located block (Task 11).
Unit and scale come from each row's own resolved unit context, never one page-wide value.
Only recognised markers get a missing state: a lone dash glyph ``DASH``, an empty cell
``BLANK``, a printed zero ``ZERO_PRINTED``; any other printed text is ``VALUE`` with its raw
text kept, and text outside the numeric grammar later interprets ``INVALID``.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    CaptureReference,
    MissingValueState,
    Occurrence,
    PackageMember,
    PrecisionKind,
    RevisionCause,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.mapping import (
    CONTEXT_BASIS,
    CONTEXT_COLUMN_HEADER,
    CONTEXT_LABEL,
    CONTEXT_LABEL_ORDINAL,
    CONTEXT_SCHEMA_IDENTITY,
    CONTEXT_SECTION,
    CONTEXT_STATEMENT_FAMILY,
)
from fundamentals.extract.pdf_header_text import normalize_header_tokens
from fundamentals.extract.pdf_statement_pages import (
    DASH_GLYPHS,
    PdfCell,
    PdfStatementRow,
    StatementLocation,
    StatementPageNotFoundError,
    StatementPageSpec,
    extract_statement_rows,
    locate_statement,
)
from fundamentals.ingest.pdf_source import LoadedPdf

PDF_EXTRACTOR_VERSION = "pdf-occurrences/1"
PDF_SCHEMA_IDENTITY = "sebi-lodr-results-layout"
CONTEXT_HEADER_MONTHS = "header_months"
NO_NUMERIC_ROW = "no banded numeric row parses"
# Optional parentheses or minus; plain digits, or digit groups whose last group before the
# decimal point has three digits (Indian two-digit groups allowed before it). Fail closed.
_NUMBER = re.compile(r"(?P<digits>\d{1,3}(?:,\d{2,3})*,\d{3}|\d+)(?P<fraction>\.\d+)?")
_DMY = re.compile(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})")
_MDY = re.compile(r"([A-Za-z]{3,9})\.?\s*(\d{1,2})\s*,\s*(\d{4})")
_MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}
_MONTH_MARKERS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("half", "year"), 6),
    (("six", "months"), 6),
    (("nine", "months"), 9),
    (("9", "months"), 9),
    (("quarter", "ended"), 3),
    (("three", "months"), 3),
    (("3", "months"), 3),
    (("year", "ended"), 12),
)


class ParsedNumber(BaseModel):
    """A printed number under the grammar: magnitude, sign and printed decimals."""

    model_config = ConfigDict(frozen=True)

    magnitude: Decimal
    sign: int
    decimals: int


class PdfReadResult(BaseModel):
    """Every occurrence read, where each family's block was found, and family failures."""

    model_config = ConfigDict(frozen=True)

    occurrences: tuple[Occurrence, ...]
    locations: Mapping[StatementFamily, StatementLocation | None]
    family_failures: Mapping[StatementFamily, str]
    location_errors: Mapping[StatementFamily, str]


def parse_printed_number(text: str) -> ParsedNumber | None:
    """Parse printed text under the numeric grammar, or ``None`` (commas never stripped freely)."""
    body = text.strip()
    sign = 1
    if body.startswith("(") and body.endswith(")"):
        body, sign = body[1:-1].strip(), -1
    elif body.startswith("-"):
        body, sign = body[1:].strip(), -1
    match = _NUMBER.fullmatch(body)
    if match is None:
        return None
    fraction = match.group("fraction") or ""
    magnitude = Decimal(match.group("digits").replace(",", "") + fraction)
    return ParsedNumber(magnitude=magnitude, sign=sign, decimals=max(len(fraction) - 1, 0))


def header_period(text: str) -> tuple[PeriodInterval, int] | None:
    """A column header's period and its month count (0 for an instant), or ``None``.

    The header must print exactly one date candidate, and it must be a calendar date (an
    invalid candidate such as ``31-Feb-2025`` makes the header undeterminable, never
    ignored). A duration phrase ("quarter ended", "half year", "nine months", "year
    ended") makes it a duration of that many months ending on the date, which must be a
    month end; no phrase makes it an instant.
    """
    dates = [_dmy(match) for match in _DMY.finditer(text)]
    dates += [_mdy(match) for match in _MDY.finditer(text)]
    if len(dates) != 1 or dates[0] is None:
        return None
    end = dates[0]
    months = _header_months(normalize_header_tokens(text))
    if months == 0:
        return PeriodInterval.at(end), 0
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        return None
    index = end.year * 12 + end.month - 1 - (months - 1)
    start = date(index // 12, index % 12 + 1, 1)
    return PeriodInterval.duration(start, end), months


def read_pdf_occurrences(
    pdf: LoadedPdf,
    *,
    capture: CaptureReference,
    member: PackageMember,
    basis: Basis,
    specs: Mapping[StatementFamily, StatementPageSpec],
) -> PdfReadResult:
    """Locate each family's block for the basis and emit one occurrence per banded cell."""
    occurrences: list[Occurrence] = []
    locations: dict[StatementFamily, StatementLocation | None] = {}
    failures: dict[StatementFamily, str] = {}
    errors: dict[StatementFamily, str] = {}
    for family, spec in specs.items():
        try:
            location = locate_statement(pdf, spec, basis=basis)
        except StatementPageNotFoundError as error:
            locations[family] = None
            errors[family] = str(error)
            continue
        locations[family] = location
        try:
            rows = extract_statement_rows(pdf, location)
        except StatementPageNotFoundError as error:
            failures[family] = str(error)
            continue
        if not any(parse_printed_number(cell.raw_text) for row in rows for cell in row.cells):
            failures[family] = NO_NUMERIC_ROW
        for row in rows:
            for cell in row.cells:
                occurrences.append(
                    _occurrence(row, cell, location, capture=capture, member=member, basis=basis)
                )
    return PdfReadResult(
        occurrences=tuple(occurrences),
        locations=locations,
        family_failures=failures,
        location_errors=errors,
    )


def _occurrence(
    row: PdfStatementRow,
    cell: PdfCell,
    location: StatementLocation,
    *,
    capture: CaptureReference,
    member: PackageMember,
    basis: Basis,
) -> Occurrence:
    """One banded cell as an occurrence."""
    text = cell.raw_text.strip()
    parsed = parse_printed_number(text)
    header_text = f"{cell.super_header_text} {cell.column_header}".strip()
    period = header_period(header_text)
    column = next(column for column in location.columns if column.index == cell.column_index)
    finite = parsed is not None
    return Occurrence(
        occurrence_id=None,
        capture=capture,
        representation=Representation.PDF,
        extractor_version=PDF_EXTRACTOR_VERSION,
        native_field=row.label,
        raw_value_text=text or None,
        raw_unit=row.unit.raw_unit if row.unit is not None else "",
        raw_scale=row.unit.raw_scale if row.unit is not None else 0,
        raw_sign=parsed.sign if parsed is not None else 1,
        precision_kind=PrecisionKind.FINITE if finite else PrecisionKind.UNSUPPORTED,
        declared_precision=parsed.decimals if parsed is not None else None,
        native_context={
            CONTEXT_SCHEMA_IDENTITY: PDF_SCHEMA_IDENTITY,
            CONTEXT_BASIS: basis.value,
            CONTEXT_STATEMENT_FAMILY: row.family.value,
            CONTEXT_LABEL: row.label,
            CONTEXT_SECTION: row.section,
            CONTEXT_LABEL_ORDINAL: row.label_ordinal,
            CONTEXT_COLUMN_HEADER: cell.column_header,
            "super_header_text": cell.super_header_text,
            CONTEXT_HEADER_MONTHS: period[1] if period is not None else None,
            "unit_marker": row.unit.text if row.unit is not None else None,
            "unit_line": row.unit_line,
        },
        period=period[0] if period is not None else None,
        missing_state=_missing_state(text, parsed),
        disclosure={
            "layout": PDF_SCHEMA_IDENTITY,
            "statement_family": row.family.value,
            "value_kind": row.unit.value_kind.value if row.unit is not None else None,
        },
        anchor={
            "page": row.page,
            "line": row.line,
            "column_index": cell.column_index,
            "column_x0": column.x0,
            "column_x1": column.x1,
            "super_header_text": column.super_header_text,
            "super_header_x0": column.super_header_x0,
            "super_header_x1": column.super_header_x1,
        },
        anchor_key=f"pdf:{row.family.value}:p{row.page}:l{row.line}:c{cell.column_index}",
        knowledge_time=member.knowledge_time,
        knowledge_time_status=member.knowledge_time_status,
        first_seen_at=capture.first_seen_at,
        revision_cause=RevisionCause.ORIGINAL,
    )


def _missing_state(text: str, parsed: ParsedNumber | None) -> MissingValueState:
    """Only recognised markers get a missing state; other printed text is ``VALUE``."""
    if not text:
        return MissingValueState.BLANK
    if text in DASH_GLYPHS:
        return MissingValueState.DASH
    if parsed is not None and parsed.magnitude == 0:
        return MissingValueState.ZERO_PRINTED
    return MissingValueState.VALUE


def _header_months(tokens: list[str]) -> int:
    """Months of the first duration phrase in the header, 0 when none."""
    for phrase, months in _MONTH_MARKERS:
        width = len(phrase)
        if any(tuple(tokens[i : i + width]) == phrase for i in range(len(tokens) - width + 1)):
            return months
    return 0


def _dmy(match: re.Match[str]) -> date | None:
    """A ``30-Sep-2025`` date."""
    return _date(int(match.group(3)), match.group(2), int(match.group(1)))


def _mdy(match: re.Match[str]) -> date | None:
    """A ``Sep 30, 2025`` date."""
    return _date(int(match.group(3)), match.group(1), int(match.group(2)))


def _date(year: int, month_name: str, day: int) -> date | None:
    """A calendar date from a month name, or ``None`` if it is not one."""
    month = _MONTHS.get(month_name[:3].lower())
    if month is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None
