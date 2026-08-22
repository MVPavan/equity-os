"""OCR recovery lane for a garbled / OCR-only consolidated quarterly P&L.

When a filer's consolidated P&L text layer is glyph-garbled (labels and/or values
unreadable) or a single cell is corrupt, the deterministic text lane
(:mod:`fundamentals.extract.pdf_number_parser`) fails closed. This lane renders the
identified statement page to an image, runs an *injected LOCAL* :class:`OcrEngine`
(nothing is transmitted — no hosted model, no upload), rebuilds word geometry from
the recognized tokens, and re-runs the SAME band-row/label/column extractor with
OCR-tolerant (concatenated) label matching.

Its two fail-closed guards act at different granularities: **per cell**, a recovered
token below the OCR confidence floor is dropped, so that line fails closed; **per
page**, the recovered statement must satisfy at least ``min_identities`` of its own
cross-foot identities (and every computable identity must hold) or the whole page is
rejected — a mis-read that breaks a computable identity is caught here. A cell that
participates in a holding identity is thus cross-checked; a cell no identity
references (e.g. EPS) rests on the confidence floor alone.

This module reuses the shared geometry engine in
:mod:`fundamentals.extract.pdf_column_geometry` (band rows, header/date-column
detection, unit detection, tolerant label/value lookup) plus the text lane's
:func:`~fundamentals.extract.pdf_number_parser._extract_lines`, so both lanes honour
one fail-closed contract and one summation/derivation logic. It depends only
downward: on the extract layer's geometry and text lane and the ingest layer
(:mod:`fundamentals.ingest.pdf_source`, :mod:`fundamentals.ingest.ocr_engine`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pymupdf
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.observation import Observation
from fundamentals.extract.pdf_column_geometry import (
    _NUMERIC_TOKEN,
    ConsolidatedStatementNotFoundError,
    LabelMatch,
    NumberParseError,
    PdfParseSpec,
    _alternate_scope_word,
    _band_rows,
    _current_column_center,
    _detect_unit_factor,
    _find_statement_page,
    _first_index,
    _labelled_value_word,
    _parse_date_token,
    _parse_number_or_none,
    _row_label,
)
from fundamentals.extract.pdf_number_parser import _extract_lines
from fundamentals.ingest.ocr_engine import OcrEngine, OcrToken
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

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
    other_word = _alternate_scope_word(spec)
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
    value_word = _labelled_value_word(rows, labels, center, spec, match_mode)
    return None if value_word is None else _parse_number_or_none(value_word.text)


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
