"""Deterministic PDF number extraction of a consolidated quarterly P&L.

Reads the consolidated results statement printed in a held Indian filer's
quarterly results PDF and emits typed :class:`Observation`s with exact
page/block/span provenance. Extraction is by **word geometry** — words are
grouped into horizontal row bands and, for each configured target row, the
current-quarter value is the numeric cell aligned under the current-quarter
column. Naive ``get_text('text')`` reading order is unsafe here: a nil (``-``)
cell breaks label/value line pairing (see docs/research/pdf-extraction-bakeoff.md
§3a).

Nothing about a specific issuer is hard-coded. The consolidated scope marker, the
P&L confirmations, the accepted label variants for each line, the current-quarter
column detection, the printed-unit detection, the issuer identity, and the
reporting period all arrive through :class:`PdfParseSpec`. The design is
**SEBI-format-general**, validated against five structurally different Wave-1
issuers plus Infosys:

* Statement/scope markers and labels match **case-insensitively** and tolerate a
  leading enumerator (``"III. Total income (I+II)"`` matches ``"Total income"``)
  by contiguous-subsequence matching, so OCR-mangled roman numerals do not defeat
  a label.
* The current-quarter column is located by its printed **period-end date** —
  numeric (``31-12-2024``), abbreviated (``31-Dec-24``), or full month-name
  (``December 31, 2024`` / two-line ``31st December`` + ``2024``) — never a fixed
  x-coordinate, and the **leftmost** column whose date equals ``period_end`` is
  chosen, so the three-months-ended quarter column is taken rather than the
  nine-months-ended year-to-date column that shares the same end date.
* The printed monetary unit (``crore`` / ``lakh`` / ``million``) is detected from
  the statement header, glyph-independent (the ``₹`` symbol is frequently mangled
  to ``z`` / ``~`` / ``(`` in the text layer), and every monetary value is scaled
  to crore so it reconciles with the crore-normalized XBRL side. A missing or
  ambiguous unit marker fails closed rather than assuming a scale.

Fail-closed contract: if the consolidated statement page is absent a distinct
:class:`ConsolidatedStatementNotFoundError` is raised (the caller may treat that as a
skip); any other missing page, column, unit marker, or line item raises
:class:`NumberParseError`. A partial extraction never silently drops a fact.

No model calls, no network I/O: values are reproducible byte-for-byte.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

DEFAULT_ROW_BAND_TOLERANCE_PT = 4.0
DEFAULT_COLUMN_X_TOLERANCE_PT = 40.0
DEFAULT_MONTH_NAMES: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# One crore = 100 lakh = 10 million. A monetary value printed in a coarser unit is
# rescaled to crore so it shares the XBRL side's comparison key.
_CRORE_PER_UNIT: dict[str, Decimal] = {
    "crore": Decimal(1),
    "lakh": Decimal("0.01"),
    "million": Decimal("0.1"),
}

_NUMERIC_TOKEN = re.compile(r"^\(-?[\d,]+(?:\.\d+)?\)$|^-?[\d,]+(?:\.\d+)?$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ORDINAL = re.compile(r"(\d)(st|nd|rd|th)\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})$")
_ABBREV_DATE = re.compile(r"^(\d{1,2})[-./]([A-Za-z]{3,})[-./](\d{2,4})$")
_YEAR_MIN = 2000
_CENTURY = 2000
_MAX_DAY = 31

# Words allowed in a column-header band besides dates/numbers. A band with more
# than this many other ("prose") words is a title sentence, not a column-date row,
# and is excluded so a date in the title cannot be mistaken for a value column.
_HEADER_KEYWORDS = frozenset(
    {
        "quarter",
        "year",
        "half",
        "nine",
        "six",
        "three",
        "months",
        "month",
        "period",
        "ended",
        "ending",
        "audited",
        "unaudited",
        "reviewed",
        "review",
        "limited",
        "standalone",
        "consolidated",
        "and",
        "for",
        "the",
        "as",
        "at",
        "particulars",
        "sr",
        "no",
        "s",
    }
)
_MAX_PROSE_WORDS_IN_HEADER_BAND = 3

# Words that only ever appear in a statement title / section heading, never in a
# column-date row. A band carrying any of them is a title, so its printed date is
# excluded and cannot be mistaken for a value-column header.
_TITLE_MARKER_WORDS = frozenset({"statement", "results", "financial", "profit", "loss"})


class NumberParseError(RuntimeError):
    """Raised when a required statement page, column, unit, or line item is missing."""


class ConsolidatedStatementNotFoundError(NumberParseError):
    """The consolidated P&L statement page is absent (caller may treat as a skip)."""


class PdfLineUnit(StrEnum):
    """Whether a target line is a monetary amount or a per-share figure.

    Monetary lines scale with the statement's printed ``crore``/``lakh``/``million``
    marker; a per-share (EPS) figure is printed in rupees per share regardless of
    that marker and is never rescaled by it.
    """

    MONETARY = "monetary"
    PER_SHARE = "per_share"


class PdfTargetLine(BaseModel):
    """A P&L line to extract: its accepted printed labels and how it is typed.

    ``labels`` holds one or more accepted label variants; matching is
    case/spacing/punctuation-insensitive and tolerant of a leading enumerator and
    trailing wording (so a configured ``"Total income"`` also matches a printed
    ``"III. Total income (I+II)"``). ``line_unit`` decides whether the printed
    figure is rescaled by the statement's monetary unit marker.
    """

    model_config = ConfigDict(frozen=True)

    labels: tuple[str, ...]
    concept_qname: str
    normalized_unit: str
    unit_ref: str
    scale: int
    decimals: int
    line_unit: PdfLineUnit = PdfLineUnit.MONETARY


class PdfParseSpec(BaseModel):
    """Everything the parser needs, injected by the composition root.

    The static portion (scope marker, confirmations, labels, tolerances, month
    names) comes from per-issuer config; the identity/period portion is stamped
    from the run so the parser records the real issuer, never a constant.
    """

    model_config = ConfigDict(frozen=True)

    scope_marker: str
    statement_confirmations: tuple[str, ...]
    anchor_label: str
    target_lines: tuple[PdfTargetLine, ...]
    entity_scheme: str
    entity_id: str
    currency: str
    scope: Scope
    accounting_basis: AccountingFramework
    period_start: date
    period_end: date
    row_band_tolerance_pt: float = DEFAULT_ROW_BAND_TOLERANCE_PT
    column_x_tolerance_pt: float = DEFAULT_COLUMN_X_TOLERANCE_PT
    month_names: tuple[str, ...] = DEFAULT_MONTH_NAMES


def _normalize_tokens(text: str) -> list[str]:
    """Normalize text to lowercase alphanumeric tokens for tolerant matching."""
    return _NON_ALNUM.sub(" ", text.lower()).split()


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """Whether ``needle`` appears as a contiguous run of tokens in ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return False
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start : start + len(needle)] == needle:
            return True
    return False


def _band_rows(words: tuple[PageWord, ...], tolerance_pt: float) -> list[list[PageWord]]:
    """Group words into horizontal row bands within ``tolerance_pt``."""
    rows: list[list[PageWord]] = []
    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        for row in rows:
            if abs(row[0].y0 - word.y0) <= tolerance_pt:
                row.append(word)
                break
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


def _numeric_cells(row: list[PageWord]) -> list[PageWord]:
    """Return the numeric-token words of a row, left to right."""
    return [word for word in row if _NUMERIC_TOKEN.match(word.text)]


def _row_label(row: list[PageWord]) -> str:
    """Join a row's label words: the non-numeric words, left to right.

    Numeric cells are both the value columns *and* a leading serial-number column
    (``"Sr. No."``) that many SEBI statements print at the far left; dropping every
    numeric token yields the ``Particulars`` text (plus any formula ref such as
    ``"(1-2)"``) regardless of a serial column, so a serial number never blanks the
    label. Subsequence matching then tolerates the enumerator/formula tokens.
    """
    label_words = [
        word for word in sorted(row, key=lambda w: w.x0) if not _NUMERIC_TOKEN.match(word.text)
    ]
    return " ".join(word.text for word in label_words).strip()


def _label_matches(row_label: str, target: PdfTargetLine) -> bool:
    """Whether a printed row label contains any of a target's accepted variants.

    Matching is a contiguous-subsequence test on normalized tokens, so a leading
    enumerator (``"iii total income i ii"``) or trailing wording does not defeat a
    variant while a distinct line stays distinct (``"profit before tax"`` does not
    match ``"profit before share of profit of an associate and tax"``).
    """
    row_tokens = _normalize_tokens(row_label)
    return any(_is_subsequence(_normalize_tokens(variant), row_tokens) for variant in target.labels)


def _parse_number(token: str) -> Decimal:
    """Parse a printed figure into a Decimal (commas stripped, parens negate)."""
    negative = token.startswith("(") and token.endswith(")")
    digits = token.strip("()").replace(",", "")
    value = Decimal(digits)
    return -value if negative else value


def _find_statement_page(pdf: LoadedPdf, spec: PdfParseSpec) -> PdfPage:
    """Return the consolidated-P&L statement page, or fail closed.

    A page qualifies when, matched case-insensitively, it carries the consolidated
    scope marker, the anchor label, and every configured P&L confirmation — the
    signature that distinguishes the consolidated P&L from a standalone statement
    or a consolidated balance sheet / cash-flow / segment page. Raises
    :class:`ConsolidatedStatementNotFoundError` when no page qualifies, so a filer that
    files consolidated separately (or whose text layer is unreadable) is a skip,
    not a fabricated fact.
    """
    scope = spec.scope_marker.lower()
    anchor = spec.anchor_label.lower()
    confirmations = tuple(marker.lower() for marker in spec.statement_confirmations)
    for page in pdf.pages:
        text = page.text.lower()
        if scope not in text or anchor not in text:
            continue
        if all(marker in text for marker in confirmations):
            return page
    raise ConsolidatedStatementNotFoundError(
        f"consolidated P&L statement page not found in {pdf.source_id}"
    )


def _anchor_row_top(rows: list[list[PageWord]], spec: PdfParseSpec) -> float:
    """Return the top y-coordinate of the anchor-label row (value rows start here)."""
    anchor_tokens = _normalize_tokens(spec.anchor_label)
    for row in rows:
        if _is_subsequence(anchor_tokens, _normalize_tokens(_row_label(row))):
            return min(word.y0 for word in row)
    raise NumberParseError(f"anchor row {spec.anchor_label!r} not located on statement page")


def _detect_unit_factor(header_words: tuple[PageWord, ...]) -> Decimal:
    """Return the crore-conversion factor for the statement's printed unit.

    The unit is read from the statement header (above the value rows), glyph- and
    OCR-tolerant: the ``₹`` symbol is frequently mangled in the text layer, so only
    the unit word (``crore``/``crores``/OCR ``crorc``, ``lakh``/``lac``,
    ``million``) is matched. Exactly one unit family must be present; a missing or
    ambiguous marker raises :class:`NumberParseError` rather than assuming a scale.
    """
    text = " ".join(word.text for word in header_words).lower()
    present = {
        "crore": bool(re.search(r"\bcror", text)),
        "lakh": bool(re.search(r"\blakh|\blac\b|\blacs\b", text)),
        "million": bool(re.search(r"\bmillion", text)),
    }
    families = [family for family, found in present.items() if found]
    if len(families) != 1:
        raise NumberParseError(
            f"statement printed-unit marker is missing or ambiguous (found: {families})"
        )
    return _CRORE_PER_UNIT[families[0]]


def _strip_ordinals(text: str) -> str:
    """Drop English ordinal suffixes so ``31st`` reads as the day ``31``."""
    return _ORDINAL.sub(r"\1", text)


def _month_index(token: str, month_names: tuple[str, ...]) -> int | None:
    """Return the 1-based month for a full or 3-letter month token, else ``None``."""
    lowered = token.lower()
    for index, name in enumerate(month_names):
        if lowered == name.lower() or lowered == name.lower()[:3]:
            return index + 1
    return None


def _parse_date_token(token: str, month_names: tuple[str, ...]) -> date | None:
    """Parse a single-token date: ``31-12-2024``, ``31.12.2024``, or ``31-Dec-24``."""
    text = _strip_ordinals(token.strip().strip(","))
    numeric = _NUMERIC_DATE.match(text)
    if numeric is not None:
        day, month, year = int(numeric[1]), int(numeric[2]), int(numeric[3])
        return _safe_date(year, month, day)
    abbrev = _ABBREV_DATE.match(text)
    if abbrev is not None:
        month = _month_index(abbrev[2], month_names) or 0
        if month:
            return _safe_date(int(abbrev[3]), month, int(abbrev[1]))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    """Build a date, normalizing a 2-digit year, or ``None`` if out of range."""
    if year < 100:
        year += _CENTURY
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _is_header_date_band(band: list[PageWord], month_names: tuple[str, ...]) -> bool:
    """Whether a band is a column-date row (not a prose title), tolerating garble."""
    prose = 0
    for word in band:
        text = _strip_ordinals(word.text.strip().strip(","))
        if _NUMERIC_TOKEN.match(text) or _parse_date_token(text, month_names) is not None:
            continue
        for token in _normalize_tokens(text):
            if token in _TITLE_MARKER_WORDS:
                return False
            if token.isdigit() or token in _HEADER_KEYWORDS:
                continue
            if _month_index(token, month_names) is not None:
                continue
            prose += 1
    return prose <= _MAX_PROSE_WORDS_IN_HEADER_BAND


def _header_date_columns(
    header_words: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Return ``(x0, date)`` for every column-date cell in the header region.

    Single-token dates are read directly; multi-token and two-line month-name
    dates (``December 31, 2024`` / ``31st December`` above ``2024``) are
    reassembled by gathering the day and year within the column tolerance of the
    month token. Prose title bands are excluded so a title date is not counted.
    """
    bands = [
        band
        for band in _band_rows(header_words, spec.row_band_tolerance_pt)
        if _is_header_date_band(band, spec.month_names)
    ]
    eligible = tuple(word for band in bands for word in band)
    columns: list[tuple[float, date]] = []
    for word in eligible:
        parsed = _parse_date_token(word.text, spec.month_names)
        if parsed is not None:
            columns.append((word.x0, parsed))
    columns.extend(_month_name_columns(eligible, spec))
    return columns


def _month_name_columns(
    eligible: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Reassemble multi-token / multi-line month-name dates into ``(x0, date)``.

    Within one column the month, day, and year share an x even when they print on
    different header lines (``June 30,`` above ``2024``, or a ``Particulars`` row
    between them), so the day and year for a month token are the integer tokens
    nearest it in x within the column tolerance — never matched across columns.
    """
    integers = [
        (word.x0, int(_strip_ordinals(word.text.strip().strip(","))))
        for word in eligible
        if _strip_ordinals(word.text.strip().strip(",")).isdigit()
    ]
    columns: list[tuple[float, date]] = []
    for anchor in eligible:
        month = _month_index(anchor.text.strip().strip(","), spec.month_names)
        if month is None:
            continue
        near = sorted(
            ((abs(x0 - anchor.x0), value) for x0, value in integers),
            key=lambda item: item[0],
        )
        within = [value for distance, value in near if distance <= spec.column_x_tolerance_pt]
        day = next((value for value in within if 1 <= value <= _MAX_DAY), None)
        year = next((value for value in within if value >= _YEAR_MIN), None)
        if day is not None and year is not None:
            built = _safe_date(year, month, day)
            if built is not None:
                columns.append((anchor.x0, built))
    return columns


def _current_column_center(header_words: tuple[PageWord, ...], spec: PdfParseSpec) -> float:
    """Locate the current-quarter value column's x-position from its printed date.

    The current quarter is a three-month period ending at ``period_end``; that end
    date is printed both for the quarter column and, again, for the nine-months
    year-to-date column. The **leftmost** column whose header date equals
    ``period_end`` is the three-months-ended quarter column (SEBI orders the
    quarter block before the year-to-date block). Fails closed when no header date
    resolves to ``period_end``.
    """
    columns = _header_date_columns(header_words, spec)
    matching = [x0 for x0, when in columns if when == spec.period_end]
    if not matching:
        raise NumberParseError(
            f"current-quarter column (period end {spec.period_end.isoformat()}) "
            "not found on statement page"
        )
    return min(matching)


def _column_value(row: list[PageWord], center: float, tolerance_pt: float) -> PageWord | None:
    """Return the numeric cell of a row aligned under ``center`` (or ``None``)."""
    candidates = [
        (abs(word.x0 - center), word)
        for word in _numeric_cells(row)
        if abs(word.x0 - center) <= tolerance_pt
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _observation_for(
    target: PdfTargetLine,
    value_word: PageWord,
    *,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for one matched line, with exact provenance.

    A monetary value is rescaled to crore by ``unit_factor`` so it reconciles with
    the crore-normalized XBRL side; a per-share value is left as printed.
    """
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=value_word.block,
        span=f"{value_word.x0:.1f},{value_word.y0:.1f},{value_word.x1:.1f},{value_word.y1:.1f}",
        retrieved_at=retrieved_at,
    )
    factor = unit_factor if target.line_unit is PdfLineUnit.MONETARY else Decimal(1)
    return Observation(
        concept_qname=target.concept_qname,
        raw_value=value_word.text,
        normalized_value=_parse_number(value_word.text) * factor,
        normalized_unit=target.normalized_unit,
        entity_scheme=spec.entity_scheme,
        entity_id=spec.entity_id,
        scope=spec.scope,
        accounting_basis=spec.accounting_basis,
        period_type=PeriodType.DURATION,
        period_start=spec.period_start,
        period_end=spec.period_end,
        unit_ref=target.unit_ref,
        currency=spec.currency,
        scale=target.scale,
        decimals=target.decimals,
        provenance=provenance,
    )


def extract_consolidated_pl(
    pdf: LoadedPdf,
    *,
    spec: PdfParseSpec,
    retrieved_at: datetime,
    require_all: bool = True,
) -> list[Observation]:
    """Extract the consolidated quarterly P&L line items as typed Observations.

    Always raises :class:`ConsolidatedStatementNotFoundError` when the consolidated
    statement is absent, and :class:`NumberParseError` when the current-quarter
    column or the printed-unit marker is missing — those are document-level
    failures from which no fact can be trusted.

    A missing *line item* is governed by ``require_all``. With the default
    ``True`` the whole extraction fails closed (the single-issuer pipeline needs
    every headline line). With ``False`` a line item that cannot be located with a
    clean current-quarter value is skipped (never fabricated) and the lines that
    are present are still emitted — so a filer that splits revenue into
    sub-components, or whose EPS cell is OCR-corrupted, still contributes its
    other material facts as a cross-check source.
    """
    page = _find_statement_page(pdf, spec)
    rows = _band_rows(page.words, spec.row_band_tolerance_pt)
    anchor_top = _anchor_row_top(rows, spec)
    header_words = tuple(word for word in page.words if word.y0 < anchor_top)
    unit_factor = _detect_unit_factor(header_words)
    center = _current_column_center(header_words, spec)

    observations: list[Observation] = []
    for target in spec.target_lines:
        value_word = _match_target_value(rows, target, center, spec)
        if value_word is None:
            if require_all:
                raise NumberParseError(
                    f"line item {target.labels!r} not found with a current-quarter value "
                    f"on page {page.page_number}"
                )
            continue
        observations.append(
            _observation_for(
                target,
                value_word,
                unit_factor=unit_factor,
                page=page,
                pdf=pdf,
                spec=spec,
                retrieved_at=retrieved_at,
            )
        )
    return observations


def _match_target_value(
    rows: list[list[PageWord]], target: PdfTargetLine, center: float, spec: PdfParseSpec
) -> PageWord | None:
    """Return the current-quarter value cell for a target, skipping value-less rows.

    A label may appear first as a section header carrying no value cell (e.g.
    ``"Revenue from operations"`` above its sub-components, or the ``"(a) Revenue
    from operations"`` sub-header above a ``"Total revenue from operations"``
    total). Such matches are skipped so the first row that both matches and carries
    a current-quarter value wins; if none does, the caller fails closed.
    """
    for row in rows:
        if not _label_matches(_row_label(row), target):
            continue
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is not None and _parse_number_or_none(value_word.text) is not None:
            return value_word
    return None


def _parse_number_or_none(token: str) -> Decimal | None:
    """Parse a printed figure, or ``None`` if the token is not a clean number."""
    try:
        return _parse_number(token)
    except InvalidOperation:
        return None
