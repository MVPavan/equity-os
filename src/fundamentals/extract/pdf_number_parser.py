"""Deterministic PDF number extraction of a consolidated quarterly P&L.

Reads the consolidated results statement printed in a held Indian filer's
quarterly results PDF and emits typed :class:`Observation`s with exact
page/block/span provenance. Extraction is by **word geometry** — words are
grouped into horizontal row bands and, for each configured target row, the
current-quarter value is the numeric cell aligned under the current-quarter
column. Naive ``get_text('text')`` reading order is unsafe here: a nil (``-``)
cell breaks label/value line pairing (see docs/research/pdf-extraction-bakeoff.md
§3a).

Nothing about a specific issuer is hard-coded. The statement-page markers (which
accept audited / unaudited / limited-review consolidated wording), the accepted
label variants for each line, the current-quarter column detection, the issuer
identity, and the reporting period all arrive through :class:`PdfParseSpec`. The
current-quarter column is found by its printed **column header** (period-end
month + year), not a fixed x-coordinate, so a filer that prints its columns in a
different order still resolves correctly.

No model calls, no network I/O: values are reproducible byte-for-byte.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

DEFAULT_ROW_BAND_TOLERANCE_PT = 3.0
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

_NUMERIC_TOKEN = re.compile(r"^\(-?[\d,]+(?:\.\d+)?\)$|^-?[\d,]+(?:\.\d+)?$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Structural words allowed in a column-header band. A band containing any other
# prose word (e.g. a title sentence "Statement of ... Results") is excluded, so a
# date mentioned in the title cannot be mistaken for a value-column header.
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
    }
)


class NumberParseError(RuntimeError):
    """Raised when a required statement page, column, or line item is missing."""


class PdfTargetLine(BaseModel):
    """A P&L line to extract: its accepted printed labels and how it is typed.

    ``labels`` holds one or more accepted label variants; matching is
    case/spacing/punctuation-insensitive and tolerant of trailing wording (so a
    configured ``"Profit for the period"`` also matches a printed
    ``"Profit for the period / (loss)"``).
    """

    model_config = ConfigDict(frozen=True)

    labels: tuple[str, ...]
    concept_qname: str
    normalized_unit: str
    unit_ref: str
    scale: int
    decimals: int


class PdfParseSpec(BaseModel):
    """Everything the parser needs, injected by the composition root.

    The static portion (markers, labels, tolerances, month names) comes from
    per-issuer config; the identity/period portion is stamped from the run so the
    parser records the real issuer, never a constant.
    """

    model_config = ConfigDict(frozen=True)

    statement_markers: tuple[str, ...]
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


def _normalize_label(text: str) -> str:
    """Normalize a label for tolerant matching (lower, punctuation-stripped)."""
    return " ".join(_NON_ALNUM.sub(" ", text.lower()).split())


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
    """Join the label words of a row (everything left of the first value cell)."""
    numeric = _numeric_cells(row)
    cutoff = min((word.x0 for word in numeric), default=float("inf"))
    label_words = [word for word in sorted(row, key=lambda w: w.x0) if word.x0 < cutoff]
    return " ".join(word.text for word in label_words).strip()


def _label_matches(row_label: str, target: PdfTargetLine) -> bool:
    """Whether a printed row label matches any of a target's accepted variants."""
    row_norm = _normalize_label(row_label)
    for variant in target.labels:
        variant_norm = _normalize_label(variant)
        if variant_norm and (row_norm == variant_norm or row_norm.startswith(variant_norm + " ")):
            return True
    return False


def _parse_number(token: str) -> Decimal:
    """Parse a printed figure into a Decimal (commas stripped, parens negate)."""
    negative = token.startswith("(") and token.endswith(")")
    digits = token.strip("()").replace(",", "")
    value = Decimal(digits)
    return -value if negative else value


def _find_statement_page(pdf: LoadedPdf, spec: PdfParseSpec) -> PdfPage:
    """Return the consolidated-P&L statement page, or raise if not found.

    A page qualifies when it carries the row anchor label and *any* of the
    configured statement markers (audited / unaudited / limited-review
    consolidated wording all being valid quarterly headings).
    """
    for page in pdf.pages:
        if spec.anchor_label not in page.text:
            continue
        if any(marker in page.text for marker in spec.statement_markers):
            return page
    raise NumberParseError(f"consolidated statement page not found in {pdf.source_id}")


def _anchor_row_top(rows: list[list[PageWord]], spec: PdfParseSpec) -> float:
    """Return the top y-coordinate of the anchor-label row (the value-rows start)."""
    anchor_norm = _normalize_label(spec.anchor_label)
    for row in rows:
        row_norm = _normalize_label(_row_label(row))
        if row_norm == anchor_norm or row_norm.startswith(anchor_norm + " "):
            return min(word.y0 for word in row)
    raise NumberParseError(f"anchor row {spec.anchor_label!r} not located on statement page")


def _is_header_eligible(text: str, month_tokens: frozenset[str]) -> bool:
    """Whether a header word is date-like/structural (not a prose title word)."""
    if _NUMERIC_TOKEN.match(text):
        return True
    norm = _normalize_label(text)
    if not norm:
        return True
    return norm in month_tokens or norm in _HEADER_KEYWORDS


def _header_column_words(
    header_words: tuple[PageWord, ...], spec: PdfParseSpec, month_tokens: frozenset[str]
) -> list[PageWord]:
    """Return words from column-header bands only (prose/title bands excluded)."""
    eligible: list[PageWord] = []
    for band in _band_rows(header_words, spec.row_band_tolerance_pt):
        if all(_is_header_eligible(word.text, month_tokens) for word in band):
            eligible.extend(band)
    return eligible


def _current_column_center(header_words: tuple[PageWord, ...], spec: PdfParseSpec) -> float:
    """Locate the current-quarter value column's x-center from its printed header.

    The column is identified by the period-end month name (or its 3-letter
    abbreviation) and 4-digit year appearing together (within the column
    tolerance) in the header region — never by a fixed x-coordinate. Title-line
    date mentions are excluded (only date-like header bands are searched). Fails
    closed when the current-quarter header cannot be uniquely located.
    """
    month = spec.month_names[spec.period_end.month - 1].lower()
    month_abbr = month[:3]
    year = str(spec.period_end.year)
    month_tokens = frozenset(name.lower() for name in spec.month_names) | frozenset(
        name.lower()[:3] for name in spec.month_names
    )

    eligible = _header_column_words(header_words, spec, month_tokens)
    month_xs = [word.x0 for word in eligible if _normalize_label(word.text) in (month, month_abbr)]
    year_xs = [word.x0 for word in eligible if _normalize_label(word.text) == year]

    centers = [
        (month_x + year_x) / 2
        for month_x in month_xs
        for year_x in year_xs
        if abs(month_x - year_x) <= spec.column_x_tolerance_pt
    ]
    if not centers:
        raise NumberParseError(
            f"current-quarter column header ({month} {year}) not found on statement page"
        )
    if len({round(center) for center in centers}) > 1:
        raise NumberParseError(
            f"current-quarter column header ({month} {year}) is ambiguous on statement page"
        )
    return centers[0]


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
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for one matched line, with exact provenance."""
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=value_word.block,
        span=f"{value_word.x0:.1f},{value_word.y0:.1f},{value_word.x1:.1f},{value_word.y1:.1f}",
        retrieved_at=retrieved_at,
    )
    return Observation(
        concept_qname=target.concept_qname,
        raw_value=value_word.text,
        normalized_value=_parse_number(value_word.text),
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
) -> list[Observation]:
    """Extract the consolidated quarterly P&L line items as typed Observations.

    Raises :class:`NumberParseError` if the statement page, the current-quarter
    column, or any configured target line item is missing, so a partial
    extraction never silently drops a fact.
    """
    page = _find_statement_page(pdf, spec)
    rows = _band_rows(page.words, spec.row_band_tolerance_pt)
    anchor_top = _anchor_row_top(rows, spec)
    header_words = tuple(word for word in page.words if word.y0 < anchor_top)
    center = _current_column_center(header_words, spec)

    observations: list[Observation] = []
    for target in spec.target_lines:
        row = next(
            (candidate for candidate in rows if _label_matches(_row_label(candidate), target)), None
        )
        if row is None:
            raise NumberParseError(
                f"line item {target.labels!r} not found on page {page.page_number}"
            )
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is None:
            raise NumberParseError(
                f"no current-quarter value for {target.labels!r} on page {page.page_number}"
            )
        observations.append(
            _observation_for(
                target,
                value_word,
                page=page,
                pdf=pdf,
                spec=spec,
                retrieved_at=retrieved_at,
            )
        )
    return observations
