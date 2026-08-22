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

The primary (text-layer) lane makes no model calls and no network I/O: values are
reproducible byte-for-byte. A second, optional **OCR lane**
(:func:`extract_consolidated_pl_via_ocr`) recovers a statement whose text layer is
glyph-garbled or has a corrupt cell: it renders the page to an image, runs an
*injected local* :class:`OcrEngine` (nothing is transmitted — no hosted model, no
upload), rebuilds word geometry from the recognized tokens, and re-runs this same
extractor with OCR-tolerant label matching. Its two fail-closed guards act at
different granularities: **per cell**, a recovered token below the OCR confidence
floor is dropped, so that line fails closed; **per page**, the recovered statement
must satisfy its own cross-foot identities or the whole page is rejected (a mis-read
that breaks a computable identity is caught here). A cell that participates in a
holding identity is thus cross-checked; a cell no identity references (e.g. EPS)
rests on the confidence floor alone.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

import pymupdf
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
# Bullet glyphs that mark a printed sub-component row (ASCII hyphen, en/em dash,
# bullet). A statement that prints a line only as sub-components leads each with one.
DEFAULT_SUBCOMPONENT_MARKERS: tuple[str, ...] = ("-", "–", "—", "•")
# Intra-statement residual allowed when validating a summed sub-component total
# against the statement's own reconciliation identity (crore units).
DEFAULT_SUMMATION_TOLERANCE = Decimal("0.5")
# OCR-lane tunables. 300 DPI renders numerals crisply for a local OCR engine; a
# recovered cell is trusted only above the confidence floor, and the recovered
# statement must satisfy at least this many of its own cross-foot identities.
DEFAULT_OCR_DPI = 300
DEFAULT_OCR_MIN_CONFIDENCE = 0.80
# At least this many of the statement's own cross-foot identities must be
# *computable and hold* (and every computable identity must hold — a broken one
# rejects the page). One holding identity proves the OCR read a coherent statement
# rather than noise; a fully OCR'd statement typically exercises three.
DEFAULT_OCR_MIN_IDENTITIES = 1
DEFAULT_OCR_CROSSFOOT_TOLERANCE = Decimal("0.75")
_PDF_POINTS_PER_INCH = 72.0
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
# An OCR text layer drops the spaces of a month-name date ("Dec 31, 2024" ->
# "Dec31,2024"); the same day/month/year is recovered from the merged token.
_MERGED_MONTH_DATE = re.compile(r"^([A-Za-z]{3,})\.?(\d{1,2})[,.]?(\d{4})$")
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


class OcrToken(BaseModel):
    """One recognized text region from a local OCR engine: text, box, confidence.

    The box is the axis-aligned bounding box in image pixels; ``confidence`` is the
    engine's per-region score in ``[0, 1]``. Engine-agnostic so Tesseract (word
    boxes) or an ONNX PP-OCR engine (line/cell boxes) both map onto it.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float


class OcrEngine(Protocol):
    """A LOCAL, deterministic OCR engine: page-image bytes -> recognized tokens.

    Implementations must run entirely on this machine and transmit nothing — the
    hard constraint of this lane is that a rendered statement image is never sent to
    a hosted/remote model. ``recognize`` takes PNG bytes and returns every detected
    region with its box (image pixels) and confidence.
    """

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:
        """Recognize text regions in a rendered page image (PNG bytes)."""
        ...


class OcrCrossFootTerm(BaseModel):
    """One signed addend of an OCR self-consistency identity, matched by label."""

    model_config = ConfigDict(frozen=True)

    sign: Literal[-1, 1]
    labels: tuple[str, ...]


class OcrCrossFootIdentity(BaseModel):
    """An intra-statement identity ``lhs == sum(sign * term)`` used to gate OCR.

    Labels are matched on the OCR'd rows with the OCR-tolerant (concatenated) mode;
    an identity is *computable* only when its lhs and every term resolve to a
    current-quarter value, and it *holds* when the residual is within tolerance.
    Acceptance requires enough computable identities to hold — see
    :func:`extract_consolidated_pl_via_ocr`.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    lhs_labels: tuple[str, ...]
    terms: tuple[OcrCrossFootTerm, ...]


# Universal SEBI Ind-AS consolidated identities that survive the associate /
# exceptional-item structural variation (unlike a rigid "income-expenses=PBT=PAT"
# chain). Each is checked only when every label resolves on the OCR'd page.
DEFAULT_OCR_CROSSFOOT: tuple[OcrCrossFootIdentity, ...] = (
    OcrCrossFootIdentity(
        name="Total income = Revenue from operations + Other income",
        lhs_labels=("Total income",),
        terms=(
            OcrCrossFootTerm(sign=1, labels=("Revenue from operations",)),
            OcrCrossFootTerm(sign=1, labels=("Other income",)),
        ),
    ),
    OcrCrossFootIdentity(
        # The first "Profit before ..." line after expenses is always income minus
        # expenses (before any associate/exceptional item), whatever its exact
        # wording — so this holds across layouts that differ only in that middle.
        name="First profit subtotal = Total income - Total expenses",
        lhs_labels=("Profit before",),
        terms=(
            OcrCrossFootTerm(sign=1, labels=("Total income",)),
            OcrCrossFootTerm(sign=-1, labels=("Total expenses",)),
        ),
    ),
    OcrCrossFootIdentity(
        name="Total comprehensive income = Net profit for the period + Total OCI",
        lhs_labels=("Total comprehensive income for the period", "Total comprehensive income"),
        terms=(
            OcrCrossFootTerm(sign=1, labels=("Net profit for the period", "Profit for the period")),
            OcrCrossFootTerm(sign=1, labels=("Total other comprehensive income",)),
        ),
    ),
    OcrCrossFootIdentity(
        name="Net profit = attributable to owners + non-controlling interests",
        lhs_labels=("Net profit for the period", "Profit for the period"),
        terms=(
            OcrCrossFootTerm(sign=1, labels=("Equity holders", "Owners of the")),
            OcrCrossFootTerm(sign=1, labels=("Non-controlling interests", "controlling interests")),
        ),
    ),
)


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


def _build_observation(
    target: PdfTargetLine,
    *,
    raw_value: str,
    normalized_value: Decimal,
    provenance: Provenance,
    spec: PdfParseSpec,
) -> Observation:
    """Assemble a typed Observation from a target's typing and the run's identity.

    Shared by the single-cell (:func:`_observation_for`) and summed
    (:func:`_summed_observation`) builders so the comparison-key fields stay in one
    place; each caller supplies only the value, its lexical form, and the anchor.
    """
    return Observation(
        concept_qname=target.concept_qname,
        raw_value=raw_value,
        normalized_value=normalized_value,
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
    return _build_observation(
        target,
        raw_value=value_word.text,
        normalized_value=_parse_number(value_word.text) * factor,
        provenance=provenance,
        spec=spec,
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

    A target carrying :class:`SubcomponentSummation` that matched only a value-less
    header is not failed in the first pass: after the direct lines are read, its
    total is reconstructed by validated summation (a split revenue with no printed
    total), and only then does ``require_all`` decide whether an irrecoverable line
    fails the extraction.
    """
    page = _find_statement_page(pdf, spec)
    rows = _band_rows(page.words, spec.row_band_tolerance_pt)
    anchor_top = _anchor_row_top(rows, spec)
    header_words = tuple(word for word in page.words if word.y0 < anchor_top)
    unit_factor = _detect_unit_factor(header_words)
    center = _current_column_center(header_words, spec)
    return _extract_lines(
        rows,
        center=center,
        unit_factor=unit_factor,
        page=page,
        pdf=pdf,
        spec=spec,
        retrieved_at=retrieved_at,
        require_all=require_all,
        match_mode=LabelMatch.SUBSEQUENCE,
    )


def _extract_lines(
    rows: list[list[PageWord]],
    *,
    center: float,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
    require_all: bool,
    match_mode: LabelMatch,
) -> list[Observation]:
    """Read every target line from pre-banded rows, then reconstruct split totals.

    Shared by the deterministic text-layer path (``SUBSEQUENCE`` matching) and the
    OCR lane (``CONCATENATED`` matching), so both honour the same fail-closed
    contract and summation logic over the geometry they each produced.
    """
    observations: list[Observation] = []
    extracted_values: dict[str, Decimal] = {}
    for target in spec.target_lines:
        value_word = _match_target_value(rows, target, center, spec, match_mode)
        if value_word is None:
            if target.subcomponent_summation is None and require_all:
                raise NumberParseError(
                    f"line item {target.labels!r} not found with a current-quarter value "
                    f"on page {page.page_number}"
                )
            continue
        observation = _observation_for(
            target,
            value_word,
            unit_factor=unit_factor,
            page=page,
            pdf=pdf,
            spec=spec,
            retrieved_at=retrieved_at,
        )
        observations.append(observation)
        extracted_values[target.concept_qname] = observation.normalized_value

    _append_summed_lines(
        observations,
        extracted_values,
        rows=rows,
        spec=spec,
        center=center,
        unit_factor=unit_factor,
        page=page,
        pdf=pdf,
        retrieved_at=retrieved_at,
        require_all=require_all,
        match_mode=match_mode,
    )
    return observations


def _append_summed_lines(
    observations: list[Observation],
    extracted_values: dict[str, Decimal],
    *,
    rows: list[list[PageWord]],
    spec: PdfParseSpec,
    center: float,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    retrieved_at: datetime,
    require_all: bool,
    match_mode: LabelMatch,
) -> None:
    """Reconstruct split-total targets by validated summation, appending any recovered.

    Runs after the direct pass so the reconciliation total (already read as a
    normal line) is available. A target whose total is neither printed directly nor
    reconstructable fails closed under ``require_all``.
    """
    total_target = next((t for t in spec.target_lines if t.is_reconciliation_total), None)
    for target in spec.target_lines:
        if target.subcomponent_summation is None or target.concept_qname in extracted_values:
            continue
        summed = _summed_line(
            rows,
            target,
            total_target=total_target,
            extracted_values=extracted_values,
            center=center,
            unit_factor=unit_factor,
            spec=spec,
            page=page,
            pdf=pdf,
            retrieved_at=retrieved_at,
            match_mode=match_mode,
        )
        if summed is not None:
            observations.append(summed)
        elif require_all:
            raise NumberParseError(
                f"line item {target.labels!r} has no printed total and could not be "
                f"reconstructed from self-consistent sub-components on page {page.page_number}"
            )


def _first_index(
    rows: list[list[PageWord]], predicate: Callable[[list[PageWord]], bool]
) -> int | None:
    """Return the index of the first row satisfying ``predicate``, or ``None``."""
    for index, row in enumerate(rows):
        if predicate(row):
            return index
    return None


def _starts_with_marker(row_label: str, markers: tuple[str, ...]) -> bool:
    """Whether a printed label begins with a sub-component bullet/dash marker."""
    stripped = row_label.strip()
    return any(stripped.startswith(marker) for marker in markers)


def _summed_line(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    *,
    total_target: PdfTargetLine | None,
    extracted_values: dict[str, Decimal],
    center: float,
    unit_factor: Decimal,
    spec: PdfParseSpec,
    page: PdfPage,
    pdf: LoadedPdf,
    retrieved_at: datetime,
    match_mode: LabelMatch,
) -> Observation | None:
    """Reconstruct a split total by summing its sub-components, or fail closed.

    The sub-components are the marker-led valued rows between the target's
    value-less header and the reconciliation-total row; the reconstruction is
    accepted only when ``sum(sub-components) + sum(other block lines)`` equals the
    already-read reconciliation total within tolerance. Any unexpected valued line
    in the block, a missing other-line, or a residual beyond tolerance returns
    ``None`` (never a guessed total).
    """
    cfg = target.subcomponent_summation
    if cfg is None or total_target is None:
        return None
    total_value = extracted_values.get(total_target.concept_qname)
    if total_value is None:
        return None
    header_idx = _first_index(rows, lambda row: _label_matches(_row_label(row), target, match_mode))
    total_idx = _first_index(
        rows,
        lambda row: (
            _label_matches(_row_label(row), total_target, match_mode)
            and _column_value(row, center, spec.column_x_tolerance_pt) is not None
        ),
    )
    if header_idx is None or total_idx is None or total_idx <= header_idx:
        return None

    factor = unit_factor if target.line_unit is PdfLineUnit.MONETARY else Decimal(1)
    components: list[PageWord] = []
    other_total = Decimal(0)
    other_found = False
    for row in rows[header_idx + 1 : total_idx]:
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is None or _parse_number_or_none(value_word.text) is None:
            continue
        label = _row_label(row)
        if _starts_with_marker(label, cfg.markers):
            components.append(value_word)
        elif _label_has_any(label, cfg.other_labels, match_mode):
            other_total += _parse_number(value_word.text) * factor
            other_found = True
        else:
            return None
    if not components or not other_found:
        return None
    subtotal = Decimal(0)
    for value_word in components:
        subtotal += _parse_number(value_word.text) * factor
    if abs(subtotal + other_total - total_value) > cfg.tolerance:
        return None
    return _summed_observation(
        target, components, subtotal, page=page, pdf=pdf, spec=spec, retrieved_at=retrieved_at
    )


def _summed_observation(
    target: PdfTargetLine,
    components: list[PageWord],
    subtotal: Decimal,
    *,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for a summed total, tracing each summed component.

    ``raw_value`` is the printed components joined by ``+`` (the computed trace);
    the provenance span lists every component cell's box so each summed input is
    independently anchored. ``subtotal`` is already unit-scaled.
    """
    first = min(components, key=lambda word: (word.y0, word.x0))
    raw_value = " + ".join(word.text for word in components)
    trace = "; ".join(
        f"{word.text}@{word.x0:.1f},{word.y0:.1f},{word.x1:.1f},{word.y1:.1f}"
        for word in components
    )
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=first.block,
        span=f"sum({trace})",
        retrieved_at=retrieved_at,
    )
    return _build_observation(
        target,
        raw_value=raw_value,
        normalized_value=subtotal,
        provenance=provenance,
        spec=spec,
    )


def _match_target_value(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch = LabelMatch.SUBSEQUENCE,
) -> PageWord | None:
    """Return the current-quarter value cell for a target, skipping value-less rows.

    A label may appear first as a section header carrying no value cell (e.g.
    ``"Revenue from operations"`` above its sub-components, or the ``"(a) Revenue
    from operations"`` sub-header above a ``"Total revenue from operations"``
    total). Such matches are skipped so only rows that both match and carry a
    current-quarter value are candidates; if none do, the caller fails closed.

    A :class:`ConditionalLabel` match takes precedence over the plain ``labels`` —
    it binds the associate-inclusive profit-for-the-period and, crucially, the
    pre-associate line (which lacks the ``also_contains`` token) can never match any
    label, so it is never emitted. Among plain-label matches the first (top-to-
    bottom) valued row wins.
    """
    conditional = _conditional_value(rows, target, center, spec, match_mode)
    if conditional is not None:
        return conditional
    return next(
        (
            value_word
            for row in rows
            if _label_matches(_row_label(row), target, match_mode)
            for value_word in (_column_value(row, center, spec.column_x_tolerance_pt),)
            if value_word is not None and _parse_number_or_none(value_word.text) is not None
        ),
        None,
    )


def _conditional_value(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch,
) -> PageWord | None:
    """First valued row matching a conditional label (head AND co-token), else None."""
    for conditional in target.conditional_labels:
        for row in rows:
            label = _row_label(row)
            if not _label_has_any(label, conditional.heads, match_mode):
                continue
            if not _label_has_any(label, conditional.also_contains, match_mode):
                continue
            value_word = _column_value(row, center, spec.column_x_tolerance_pt)
            if value_word is not None and _parse_number_or_none(value_word.text) is not None:
                return value_word
    return None


def _label_has_any(
    row_label: str, phrases: tuple[str, ...], match_mode: LabelMatch = LabelMatch.SUBSEQUENCE
) -> bool:
    """Whether a printed row label contains any phrase under ``match_mode``."""
    row_tokens = _normalize_tokens(row_label)
    return any(_variant_hits(phrase, row_tokens, match_mode) for phrase in phrases)


def _parse_number_or_none(token: str) -> Decimal | None:
    """Parse a printed figure, or ``None`` if the token is not a clean number."""
    try:
        return _parse_number(token)
    except InvalidOperation:
        return None


# --- OCR lane: recover a garbled/OCR-only consolidated statement ----------------
#
# When a filer's consolidated P&L text layer is glyph-garbled (labels and/or
# values unreadable) or a single cell is corrupt, the deterministic text lane
# fails closed. This lane renders the identified statement page to an image,
# runs a LOCAL OCR engine, rebuilds word geometry from the recognized tokens, and
# re-runs the SAME band-row/label/column extractor over them. It never uploads the
# image anywhere, and it accepts a recovered value only when (1) the OCR token
# clears a confidence floor and (2) the recovered statement satisfies its own
# cross-foot identities — so a mis-read digit fails closed rather than passing.


def render_page_image(pdf_path: Path, page_number: int, *, dpi: int = DEFAULT_OCR_DPI) -> bytes:
    """Render one 1-based page of a held PDF to PNG bytes, entirely locally."""
    document: Any = pymupdf.open(str(pdf_path))  # type: ignore[no-untyped-call]
    try:
        page = document[page_number - 1]
        pixmap = page.get_pixmap(dpi=dpi)
        payload: bytes = pixmap.tobytes("png")
    finally:
        document.close()
    return payload


def _ocr_words_from_tokens(
    tokens: Sequence[OcrToken], *, dpi: int, confidence_threshold: float
) -> tuple[PageWord, ...]:
    """Convert confident OCR tokens into PDF-point word geometry for the extractor.

    Sub-threshold tokens are dropped (an unreadable cell then fails closed rather
    than contributing a guess), and pixel boxes are scaled back to PDF points so
    the existing point tolerances apply unchanged.
    """
    scale = dpi / _PDF_POINTS_PER_INCH
    words: list[PageWord] = []
    for index, token in enumerate(tokens):
        if token.confidence < confidence_threshold:
            continue
        text = token.text.strip()
        if not text:
            continue
        words.append(
            PageWord(
                x0=token.x0 / scale,
                y0=token.y0 / scale,
                x1=token.x1 / scale,
                y1=token.y1 / scale,
                text=text,
                block=0,
                line=0,
                word_no=index,
            )
        )
    return tuple(words)


def _scope_bounded_rows(rows: list[list[PageWord]], spec: PdfParseSpec) -> list[list[PageWord]]:
    """Trim rows at the alternate-scope section so a combined page stays in scope.

    A single page often prints the consolidated statement above the standalone one;
    cutting at the first alternate-scope marker ("standalone" for a consolidated
    request) keeps extraction (which takes the first matching row) inside the
    requested scope. This handles the common consolidated-first layout; a
    standalone-first page would be trimmed to nothing and recover no consolidated
    line — a fail-closed miss, never a wrong-scope value.
    """
    other_word = "standalone" if spec.scope is Scope.CONSOLIDATED else "consolidated"
    end = _first_index(rows, lambda row: other_word in _row_label(row).lower())
    return rows if end is None else rows[:end]


def _ocr_header_words(
    words: tuple[PageWord, ...], rows: list[list[PageWord]], spec: PdfParseSpec
) -> tuple[PageWord, ...]:
    """Return the words above (and including) the column-date band as the header.

    The OCR text layer lacks a clean anchor label, so the header/value boundary is
    the first row carrying two or more parseable column dates; unit detection and
    current-column location then run over the header just as on the text lane.
    """
    split_y: float | None = None
    for row in rows:
        dated = sum(1 for word in row if _parse_date_token(word.text, spec.month_names) is not None)
        if dated >= 2:
            split_y = max(word.y1 for word in row)
            break
    if split_y is None:
        return words
    return tuple(word for word in words if word.y0 <= split_y)


def _row_value_by_label(
    rows: list[list[PageWord]],
    labels: tuple[str, ...],
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch,
) -> Decimal | None:
    """First current-quarter value on a row matching any of ``labels``, else ``None``."""
    for row in rows:
        if not _label_has_any(_row_label(row), labels, match_mode):
            continue
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is not None:
            parsed = _parse_number_or_none(value_word.text)
            if parsed is not None:
                return parsed
    return None


def _ocr_self_consistent(
    rows: list[list[PageWord]],
    *,
    center: float,
    unit_factor: Decimal,
    spec: PdfParseSpec,
    identities: tuple[OcrCrossFootIdentity, ...],
    tolerance: Decimal,
    min_identities: int,
) -> bool:
    """Whether the OCR'd current-quarter column satisfies enough of its own identities.

    Each identity is evaluated only when its lhs and all terms resolve to a
    current-quarter value. A computable identity whose residual exceeds tolerance
    rejects the whole page (a mis-read digit shows up as a broken identity);
    acceptance needs at least ``min_identities`` computable identities to hold, so a
    page that cannot be self-validated fails closed.
    """
    holding = 0
    for identity in identities:
        lhs = _row_value_by_label(rows, identity.lhs_labels, center, spec, LabelMatch.CONCATENATED)
        if lhs is None:
            continue
        rhs = Decimal(0)
        resolved = True
        for term in identity.terms:
            value = _row_value_by_label(rows, term.labels, center, spec, LabelMatch.CONCATENATED)
            if value is None:
                resolved = False
                break
            rhs += Decimal(term.sign) * value
        if not resolved:
            continue
        if abs((lhs - rhs) * unit_factor) > tolerance:
            return False
        holding += 1
    return holding >= min_identities


def _locate_ocr_page(pdf: LoadedPdf, spec: PdfParseSpec) -> int | None:
    """Pick the page to OCR: the clean text-layer match, else the detailed P&L page.

    When the text layer is clean enough, its located statement page is reused. When
    it is too garbled for :func:`_find_statement_page` (the case this lane exists
    for), the fallback is the numeric-densest page that prints both an income and an
    expenses section — the detailed P&L — regardless of the garble in its labels.
    """
    try:
        return _find_statement_page(pdf, spec).page_number
    except ConsolidatedStatementNotFoundError:
        pass
    best_page: int | None = None
    best_numeric = 0
    for page in pdf.pages:
        lowered = page.text.lower()
        if "expens" not in lowered or "income" not in lowered:
            continue
        numeric = sum(1 for word in page.words if _NUMERIC_TOKEN.match(word.text))
        if numeric > best_numeric:
            best_numeric = numeric
            best_page = page.page_number
    return best_page


def extract_consolidated_pl_via_ocr(
    pdf: LoadedPdf,
    pdf_path: Path,
    *,
    spec: PdfParseSpec,
    ocr_engine: OcrEngine,
    retrieved_at: datetime,
    dpi: int = DEFAULT_OCR_DPI,
    min_confidence: float = DEFAULT_OCR_MIN_CONFIDENCE,
    crossfoot_identities: tuple[OcrCrossFootIdentity, ...] = DEFAULT_OCR_CROSSFOOT,
    min_identities: int = DEFAULT_OCR_MIN_IDENTITIES,
    crossfoot_tolerance: Decimal = DEFAULT_OCR_CROSSFOOT_TOLERANCE,
    require_all: bool = False,
) -> list[Observation]:
    """Recover a garbled consolidated P&L by local OCR, or fail closed.

    Renders the identified statement page, runs the injected LOCAL ``ocr_engine``,
    rebuilds word geometry from the confident tokens, and re-runs the deterministic
    extractor with OCR-tolerant (concatenated) label matching. Returns ``[]``
    (fail closed) when the page cannot be located/OCR'd, when the header (unit or
    current-quarter column) is unrecoverable, or when the recovered statement does
    not satisfy enough of its own cross-foot identities. Nothing is transmitted:
    the rendered image never leaves this process.

    The gates act at two granularities (see the module docstring): sub-confidence
    cells are dropped per cell, and the cross-foot check validates the page as a
    whole — a monetary cell not referenced by any holding identity (and EPS, which
    no identity references) is trusted on the confidence floor, not cross-footed.
    """
    page_number = _locate_ocr_page(pdf, spec)
    if page_number is None:
        return []
    image_png = render_page_image(pdf_path, page_number, dpi=dpi)
    tokens = ocr_engine.recognize(image_png)
    words = _ocr_words_from_tokens(tokens, dpi=dpi, confidence_threshold=min_confidence)
    if not words:
        return []

    synthetic_page = PdfPage(
        page_number=page_number,
        text=" ".join(word.text for word in words),
        words=words,
        blocks=(),
    )
    synthetic_pdf = LoadedPdf(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        page_count=pdf.page_count,
        pages=(synthetic_page,),
    )
    rows = _scope_bounded_rows(_band_rows(words, spec.row_band_tolerance_pt), spec)
    header_words = _ocr_header_words(words, rows, spec)
    try:
        unit_factor = _detect_unit_factor(header_words)
        center = _current_column_center(header_words, spec)
    except NumberParseError:
        return []
    if not _ocr_self_consistent(
        rows,
        center=center,
        unit_factor=unit_factor,
        spec=spec,
        identities=crossfoot_identities,
        tolerance=crossfoot_tolerance,
        min_identities=min_identities,
    ):
        return []
    return _extract_lines(
        rows,
        center=center,
        unit_factor=unit_factor,
        page=synthetic_page,
        pdf=synthetic_pdf,
        spec=spec,
        retrieved_at=retrieved_at,
        require_all=require_all,
        match_mode=LabelMatch.CONCATENATED,
    )
