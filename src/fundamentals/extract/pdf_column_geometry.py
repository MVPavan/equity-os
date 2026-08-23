"""Shared fail-closed PDF statement geometry for the text and OCR lanes."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import AccountingFramework, Scope
from fundamentals.extract.pdf_header_text import (
    NON_QUARTER_HEADER_MARKERS,
    QUARTER_HEADER_MARKERS,
    normalize_header_tokens,
    normalize_text_tokens,
)
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

DEFAULT_ROW_BAND_TOLERANCE_PT = 4.0
DEFAULT_COLUMN_X_TOLERANCE_PT = 40.0
# Bullet glyphs marking printed sub-component rows (hyphen, en/em dash, or bullet).
DEFAULT_SUBCOMPONENT_MARKERS: tuple[str, ...] = ("-", "–", "—", "•")
# Intra-statement residual allowed when validating a summed sub-component total
# against the statement's own reconciliation identity (crore units).
DEFAULT_SUMMATION_TOLERANCE = Decimal("0.5")
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

# Monetary values are normalized to crore so they share the XBRL comparison key.
_CRORE_PER_UNIT: dict[str, Decimal] = {
    "crore": Decimal(1),
    "lakh": Decimal("0.01"),
    "million": Decimal("0.1"),
}

_NUMERIC_TOKEN = re.compile(r"^\(-?[\d,]+(?:\.\d+)?\)$|^-?[\d,]+(?:\.\d+)?$")
_ORDINAL = re.compile(r"(\d)(st|nd|rd|th)\b", re.IGNORECASE)
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})$")
_ABBREV_DATE = re.compile(r"^(\d{1,2})[-./]([A-Za-z]{3,})[-./](\d{2,4})$")
# OCR may drop spaces from a month-name date ("Dec 31, 2024" -> "Dec31,2024").
_MERGED_MONTH_DATE = re.compile(r"^([A-Za-z]{3,})\.?(\d{1,2})[,.]?(\d{4})$")
_MERGED_DAY_MONTH_DATE = re.compile(r"^(\d{1,2})([A-Za-z]{3,})\.?[,]?(\d{2,4})$")
_MONTH_DAY_YEAR = re.compile(r"^([A-Za-z]{3,})\.?\s+(\d{1,2})[,.]?\s+(\d{4})$")
_DAY_MONTH_YEAR = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,})\.?[,]?\s+(\d{4})$")
_DAY_YEAR_TOKEN = re.compile(r"^(\d{1,2})[,.\s]+(\d{4})$")
_YEAR_MIN = 2000
_CENTURY = 2000
_MAX_DAY = 31
_FRAGMENT_COLUMN_FRACTION = 0.5

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


class LabelMatch(StrEnum):
    """How a configured label variant is matched against a printed row label.

    ``SUBSEQUENCE`` (the deterministic text-layer default) requires the variant's
    normalized tokens to appear as a contiguous run of *whole* tokens, so a leading
    enumerator or trailing wording is tolerated but ``"profit before tax"`` never
    matches ``"profit before share of ... and tax"``. ``CONCATENATED`` compares the
    alnum-joined strings (a substring test), which additionally tolerates the
    spurious word-joins an OCR text layer introduces (``"fromoperations"``); it is
    used only on the OCR lane, never on the byte-exact text layer.
    """

    SUBSEQUENCE = "subsequence"
    CONCATENATED = "concatenated"


class SubcomponentSummation(BaseModel):
    """Reconstruct a split line-item total by summing its printed sub-components.

    Some filers print no single total for a line — only dashed sub-component rows
    beneath a value-less header (e.g. TITAN's ``Revenue from operations`` above
    ``- Sale of products`` / ``- Other operating revenues``). When a
    :class:`PdfTargetLine` carries this config and matched only such a header, the
    parser sums the contiguous sub-component rows (leading with one of ``markers``)
    between the header and the reconciliation-total row, and accepts the total
    **only** if the statement's own arithmetic validates it:
    ``sum(sub-components) + sum(other lines) == reconciliation total`` within
    ``tolerance``. ``other_labels`` names the non-sub-component block line(s) (e.g.
    ``"Other income"``); any *other* valued line inside the block makes the split
    ambiguous and fails closed. The check is intra-statement only — never against
    another source — so it cannot launder a cross-source disagreement.
    """

    model_config = ConfigDict(frozen=True)

    other_labels: tuple[str, ...]
    markers: tuple[str, ...] = DEFAULT_SUBCOMPONENT_MARKERS
    tolerance: Decimal = DEFAULT_SUMMATION_TOLERANCE


class ConditionalLabel(BaseModel):
    """A label that matches a row only when a second marker is *also* present.

    Resolves the consolidated profit-for-the-period in the layout (e.g. LAURUSLABS)
    that prints associates *below* tax: a pre-associate ``"Net Profit after tax"``
    line and, below it, the associate-inclusive profit-for-the-period line
    ``"Net profit after tax(es) and share of ... associates"``. Matching the head
    (``"Net profit after"``) alone would also capture the pre-associate line, so a
    match additionally requires an ``also_contains`` token (``"associates"``) — the
    two survive the glyph garble in between, and the pre-associate line (no
    ``associates``) can never bind. A conditional match takes precedence over the
    plain ``labels``: when present it *is* the group profit for the period.
    """

    model_config = ConfigDict(frozen=True)

    heads: tuple[str, ...]
    also_contains: tuple[str, ...]


class PdfTargetLine(BaseModel):
    """A P&L line to extract: its accepted printed labels and how it is typed.

    ``labels`` holds one or more accepted label variants; matching is
    case/spacing/punctuation-insensitive and tolerant of a leading enumerator and
    trailing wording (so a configured ``"Total income"`` also matches a printed
    ``"III. Total income (I+II)"``). ``line_unit`` decides whether the printed
    figure is rescaled by the statement's monetary unit marker.

    ``conditional_labels`` (see :class:`ConditionalLabel`) are higher-precedence
    matches used to pick the associate-inclusive profit-for-the-period without ever
    binding the pre-associate line; when none matches, the plain ``labels`` decide,
    first valued row winning.
    """

    model_config = ConfigDict(frozen=True)

    labels: tuple[str, ...]
    concept_qname: str
    normalized_unit: str
    unit_ref: str
    scale: int
    decimals: int
    line_unit: PdfLineUnit = PdfLineUnit.MONETARY
    conditional_labels: tuple[ConditionalLabel, ...] = ()
    subcomponent_summation: SubcomponentSummation | None = None
    is_reconciliation_total: bool = False


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
    return normalize_text_tokens(text)


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


def _variant_hits(variant: str, row_tokens: list[str], mode: LabelMatch) -> bool:
    """Whether one label variant matches a row's normalized tokens under ``mode``."""
    variant_tokens = _normalize_tokens(variant)
    if not variant_tokens:
        return False
    if mode is LabelMatch.SUBSEQUENCE:
        return _is_subsequence(variant_tokens, row_tokens)
    return "".join(variant_tokens) in "".join(row_tokens)


def _label_matches(
    row_label: str, target: PdfTargetLine, mode: LabelMatch = LabelMatch.SUBSEQUENCE
) -> bool:
    """Whether a printed row label contains any of a target's accepted variants.

    Under the default ``SUBSEQUENCE`` mode a leading enumerator
    (``"iii total income i ii"``) or trailing wording does not defeat a variant
    while a distinct line stays distinct (``"profit before tax"`` does not match
    ``"profit before share of profit of an associate and tax"``). ``CONCATENATED``
    additionally tolerates OCR word-joins and is used only on the OCR lane.
    """
    row_tokens = _normalize_tokens(row_label)
    return any(_variant_hits(variant, row_tokens, mode) for variant in target.labels)


def _label_has_any(
    row_label: str, phrases: tuple[str, ...], match_mode: LabelMatch = LabelMatch.SUBSEQUENCE
) -> bool:
    """Whether a printed row label contains any phrase under ``match_mode``."""
    row_tokens = _normalize_tokens(row_label)
    return any(_variant_hits(phrase, row_tokens, match_mode) for phrase in phrases)


def _parse_number(token: str) -> Decimal:
    """Parse a printed figure into a Decimal (commas stripped, parens negate)."""
    negative = token.startswith("(") and token.endswith(")")
    digits = token.strip("()").replace(",", "")
    value = Decimal(digits)
    return -value if negative else value


def _parse_number_or_none(token: str) -> Decimal | None:
    """Parse a printed figure, or ``None`` if the token is not a clean number."""
    try:
        return _parse_number(token)
    except InvalidOperation:
        return None


def _first_index(
    rows: list[list[PageWord]], predicate: Callable[[list[PageWord]], bool]
) -> int | None:
    """Return the index of the first row satisfying ``predicate``, or ``None``."""
    for index, row in enumerate(rows):
        if predicate(row):
            return index
    return None


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
    # "cror"/"lakh"/"million" are distinctive enough to match without a leading word
    # boundary, so an OCR word-join ("incrores") is still detected; the short,
    # ambiguous "lac" keeps its boundaries (else it would match inside "black").
    present = {
        "crore": bool(re.search(r"cror", text)),
        "lakh": bool(re.search(r"lakh|\blac\b|\blacs\b", text)),
        "million": bool(re.search(r"million", text)),
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
    """Parse a single-token date.

    Handles ``31-12-2024`` / ``31.12.2024``, ``31-Dec-24``, and the OCR-merged
    month-name form ``Dec31,2024`` (spaces dropped by the OCR text layer).
    """
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
    merged = _MERGED_MONTH_DATE.match(text)
    if merged is not None:
        month = _month_index(merged[1], month_names) or 0
        if month:
            return _safe_date(int(merged[3]), month, int(merged[2]))
    merged_day_first = _MERGED_DAY_MONTH_DATE.match(text)
    if merged_day_first is not None:
        month = _month_index(merged_day_first[2], month_names) or 0
        if month:
            return _safe_date(int(merged_day_first[3]), month, int(merged_day_first[1]))
    month_first = _MONTH_DAY_YEAR.match(text)
    if month_first is not None:
        month = _month_index(month_first[1], month_names) or 0
        if month:
            return _safe_date(int(month_first[3]), month, int(month_first[2]))
    day_first = _DAY_MONTH_YEAR.match(text)
    if day_first is not None:
        month = _month_index(day_first[2], month_names) or 0
        if month:
            return _safe_date(int(day_first[3]), month, int(day_first[1]))
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
        for token in normalize_header_tokens(text):
            if any(marker in token for marker in _TITLE_MARKER_WORDS):
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
    """Return each header date at its centre, excluding prose-title dates."""
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
            columns.append(((word.x0 + word.x1) / 2, parsed))
    columns.extend(_inline_fragment_columns(bands, spec))
    columns.extend(_stacked_fragment_columns(eligible, spec))
    columns.extend(_month_name_columns(eligible, spec))
    return columns


def _inline_fragment_columns(
    bands: list[list[PageWord]], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Assemble tightly adjacent horizontal date fragments without crossing columns."""
    columns: list[tuple[float, date]] = []
    maximum_spread = spec.column_x_tolerance_pt * _FRAGMENT_COLUMN_FRACTION
    for band in bands:
        for start in range(len(band)):
            for size in (2, 3):
                fragments = band[start : start + size]
                if len(fragments) != size or any(
                    abs(_word_center(right) - _word_center(left)) > maximum_spread
                    for left, right in zip(fragments, fragments[1:], strict=False)
                ):
                    continue
                parsed = _parse_date_token(
                    " ".join(word.text for word in fragments), spec.month_names
                )
                if parsed is not None:
                    columns.append((_word_center(fragments[0]), parsed))
    return columns


def _stacked_fragment_columns(
    eligible: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Assemble vertically stacked date fragments from one physical column only."""
    columns: list[tuple[float, date]] = []
    for column in _header_fragment_columns(eligible, spec):
        for start in range(len(column)):
            for size in (2, 3):
                fragments = column[start : start + size]
                if len(fragments) != size:
                    continue
                parsed = _parse_date_token(
                    " ".join(fragment.text for fragment in fragments), spec.month_names
                )
                if parsed is None:
                    continue
                columns.append((_word_center(fragments[0]), parsed))
    return columns


def _header_fragment_columns(
    eligible: tuple[PageWord, ...], spec: PdfParseSpec, *, require_unique_bands: bool = True
) -> list[list[PageWord]]:
    """Partition header fragments into narrow, unambiguous physical columns."""
    maximum_spread = spec.column_x_tolerance_pt * _FRAGMENT_COLUMN_FRACTION
    columns: list[list[PageWord]] = []
    for word in sorted(eligible, key=_word_center):
        if not columns or _word_center(word) - _word_center(columns[-1][0]) > maximum_spread:
            columns.append([word])
        else:
            columns[-1].append(word)
    if require_unique_bands:
        columns = [
            column
            for column in columns
            if all(len(band) == 1 for band in _band_rows(tuple(column), spec.row_band_tolerance_pt))
        ]
    return [sorted(column, key=lambda word: (word.y0, word.x0)) for column in columns]


def _word_center(word: PageWord) -> float:
    """Return the horizontal centre of one PDF word box."""
    return (word.x0 + word.x1) / 2


def _header_integers(eligible: tuple[PageWord, ...]) -> list[tuple[float, int]]:
    """Return every standalone or merged day/year integer with its word centre."""
    integers: list[tuple[float, int]] = []
    for word in eligible:
        text = _strip_ordinals(word.text.strip().strip(","))
        if text.isdigit():
            integers.append((_word_center(word), int(text)))
            continue
        merged = _DAY_YEAR_TOKEN.match(word.text.strip())
        if merged is not None:
            integers.append((_word_center(word), int(merged[1])))
            integers.append((_word_center(word), int(merged[2])))
    return integers


def _month_name_columns(
    eligible: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Reassemble vertically separated month-name dates inside a physical column."""
    columns: list[tuple[float, date]] = []
    for column in _header_fragment_columns(eligible, spec, require_unique_bands=False):
        if any(
            len(band) > 1
            and not (
                len(band) == 2
                and sum(
                    _month_index(word.text.strip().strip(","), spec.month_names) is not None
                    for word in band
                )
                == 1
                and len(_header_integers(tuple(band))) == 1
            )
            for band in _band_rows(tuple(column), spec.row_band_tolerance_pt)
        ):
            continue
        integers = _header_integers(tuple(column))
        for anchor in column:
            month = _month_index(anchor.text.strip().strip(","), spec.month_names)
            if month is None:
                continue
            days = [value for _, value in integers if 1 <= value <= _MAX_DAY]
            years = [value for _, value in integers if value >= _YEAR_MIN]
            if len(days) != 1 or len(years) != 1:
                continue
            built = _safe_date(years[0], month, days[0])
            if built is not None:
                columns.append((_word_center(anchor), built))
    return columns


def _alternate_scope_word(spec: PdfParseSpec) -> str:
    """The scope word that marks the *other* scope's section on a combined page."""
    return "standalone" if spec.scope is Scope.CONSOLIDATED else "consolidated"


def _band_has_title_marker(band: list[PageWord]) -> bool:
    """Whether a band carries a statement-title word (so it is a title, not a header)."""
    return any(
        token in _TITLE_MARKER_WORDS
        for word in band
        for token in normalize_header_tokens(word.text)
    )


def _scope_header_centers(
    header_words: tuple[PageWord, ...], spec: PdfParseSpec
) -> tuple[list[float], list[float]]:
    """Return (requested-scope, alternate-scope) super-header x-centres.

    On a combined page the two scope words print as spread-out super-headers, each
    centred over its column group, in a band that carries no statement-title words.
    The title sentence (which also names both scopes) is excluded via the title
    markers, so only the true super-header positions are returned. Two empty lists
    mean the page is single-scope (one scope word, or none outside the title) — the
    signal the caller uses to leave column selection unconfined.
    """
    requested = spec.scope_marker.lower()
    alternate = _alternate_scope_word(spec)
    requested_centers: list[float] = []
    alternate_centers: list[float] = []
    for band in _band_rows(header_words, spec.row_band_tolerance_pt):
        if _band_has_title_marker(band):
            continue
        for word in band:
            lowered = " ".join(normalize_header_tokens(word.text))
            center = (word.x0 + word.x1) / 2.0
            if requested in lowered:
                requested_centers.append(center)
            elif alternate in lowered:
                alternate_centers.append(center)
    return requested_centers, alternate_centers


def _confine_to_scope_block(
    columns: list[tuple[float, date]], header_words: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[tuple[float, date]]:
    """Restrict date columns to the requested scope's block on a combined table.

    A combined statement prints a standalone and a consolidated column group side by
    side under spread-out scope super-headers. Keeping every period-end match would
    let the leftmost (standalone) column win for a consolidated request; instead each
    date column is assigned to whichever scope super-header is horizontally nearer,
    and only the requested scope's columns are kept. A single-scope page (no
    alternate-scope super-header) is returned unchanged. Fails closed (empty) when a
    combined table is detected but no column lands in the requested block.
    """
    requested_centers, alternate_centers = _scope_header_centers(header_words, spec)
    if not requested_centers or not alternate_centers:
        return columns
    requested_center = sum(requested_centers) / len(requested_centers)
    alternate_center = sum(alternate_centers) / len(alternate_centers)
    return [
        (x, when) for x, when in columns if abs(x - requested_center) <= abs(x - alternate_center)
    ]


def _current_column_center(header_words: tuple[PageWord, ...], spec: PdfParseSpec) -> float:
    """Locate the current-quarter value column's x-position from its printed date.

    The current quarter is a three-month period ending at ``period_end``; that end
    date may also label a nine-month year-to-date column. Nearby aliases for one
    physical column are coalesced and combined tables are confined to the requested
    scope. Readable markers must select exactly one quarter and always exclude
    nine-month/year-ended columns; with no readable marker, the existing leftmost
    equal-period-end rule applies. Missing or ambiguous columns fail closed.
    """
    columns = _confine_to_scope_block(_header_date_columns(header_words, spec), header_words, spec)
    matching: list[float] = []
    for center in sorted({round(x, 3) for x, when in columns if when == spec.period_end}):
        if not matching or center - matching[-1] > spec.column_x_tolerance_pt / 2:
            matching.append(center)
    if not matching:
        raise NumberParseError(
            f"current-quarter column (period end {spec.period_end.isoformat()}) "
            "not found on statement page"
        )
    eligible: list[tuple[float, list[str]]] = []
    for center in matching:
        tokens = _column_header_tokens(center, header_words, spec)
        if _has_header_marker(tokens, NON_QUARTER_HEADER_MARKERS):
            continue
        eligible.append((center, tokens))
    quarter_marked = [
        center for center, tokens in eligible if _has_header_marker(tokens, QUARTER_HEADER_MARKERS)
    ]
    if len(quarter_marked) == 1:
        return quarter_marked[0]
    if len(quarter_marked) > 1:
        raise NumberParseError(
            f"current-quarter column (period end {spec.period_end.isoformat()}) "
            "is ambiguous across multiple quarter-marked columns"
        )
    if not eligible:
        raise NumberParseError(
            f"current-quarter column (period end {spec.period_end.isoformat()}) "
            "has only year-to-date or year-ended headers"
        )
    return min(center for center, _ in eligible)


def _column_header_tokens(
    center: float, header_words: tuple[PageWord, ...], spec: PdfParseSpec
) -> list[str]:
    """Return keyword tokens geometrically belonging to one date column."""
    tokens: list[str] = []
    for band in _band_rows(header_words, spec.row_band_tolerance_pt):
        if not _is_header_date_band(band, spec.month_names):
            continue
        for word in band:
            word_center = (word.x0 + word.x1) / 2
            if abs(word_center - center) <= spec.column_x_tolerance_pt:
                tokens.extend(normalize_header_tokens(word.text))
    return tokens


def _has_header_marker(tokens: list[str], markers: tuple[tuple[str, ...], ...]) -> bool:
    """Whether a normalized column-header group contains a marker phrase."""
    joined = "".join(tokens)
    return any(
        _is_subsequence(list(marker), tokens) or "".join(marker) in joined for marker in markers
    )


def _column_value(row: list[PageWord], center: float, tolerance_pt: float) -> PageWord | None:
    """Return the numeric cell whose horizontal centre is nearest ``center`` (or ``None``).

    Matching on the cell **centre** rather than its left edge tracks a right-aligned
    money column correctly: a narrow cell (an EPS ``0.51``) and a wide cell
    (``1,011.95``) in the same column share a centre near the column's header-date
    centre, so a short cell no longer drifts to a neighbouring column's value. The
    nearest qualifying cell within ``tolerance_pt`` wins.
    """
    candidates = [
        (abs((word.x0 + word.x1) / 2 - center), word)
        for word in _numeric_cells(row)
        if abs((word.x0 + word.x1) / 2 - center) <= tolerance_pt
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _labelled_value_word(
    rows: list[list[PageWord]],
    labels: tuple[str, ...],
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch,
) -> PageWord | None:
    """First current-quarter value cell on a row whose label matches any of ``labels``.

    Scans top-to-bottom for a row whose printed label contains one of ``labels`` and
    that carries a clean numeric cell under the current-quarter column; value-less
    header rows are skipped. Shared by both lanes to read a line by plain label
    (unit detection, cross-foot terms, and derivation), independent of a
    :class:`PdfTargetLine`.
    """
    for row in rows:
        if not _label_has_any(_row_label(row), labels, match_mode):
            continue
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is not None and _parse_number_or_none(value_word.text) is not None:
            return value_word
    return None
