"""Deterministic PDF number extraction of the Q1 FY25 consolidated P&L.

Reads the consolidated Statement of Audited Results printed in the held Infosys
Q1 FY25 results PDF and emits typed :class:`Observation`s with exact
page/block/span provenance. Extraction is by **word geometry** — words are
grouped into horizontal row bands and the leftmost numeric cell of each target
row is taken as the current-quarter (Apr–Jun 2024) value. Naive
``get_text('text')`` reading order is unsafe here: a nil (``-``) cell breaks
label/value line pairing (see docs/research/pdf-extraction-bakeoff.md §3a). The
first data column is the quarter ended 30-Jun-2024 per the frozen oracle.

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

ROW_BAND_TOLERANCE_PT = 3.0
LABEL_MAX_X0_PT = 460.0
VALUE_MIN_X0_PT = 460.0

ENTITY_SCHEME = "nse-symbol"
ENTITY_ID = "INFY"
REPORTING_CURRENCY = "INR"

PERIOD_START = date(2024, 4, 1)
PERIOD_END = date(2024, 6, 30)

_STATEMENT_MARKER = "Statement of Consolidated Audited Results"
_ANCHOR_LABEL = "Revenue from operations"
_NUMERIC_TOKEN = re.compile(r"^\(-?[\d,]+(?:\.\d+)?\)$|^-?[\d,]+(?:\.\d+)?$")


class NumberParseError(RuntimeError):
    """Raised when a required statement page or line item cannot be located."""


class _TargetLine(BaseModel):
    """A P&L line to extract: how it is printed and how it is typed."""

    model_config = ConfigDict(frozen=True)

    printed_label: str
    concept_qname: str
    normalized_unit: str
    unit_ref: str
    scale: int
    decimals: int


TARGET_LINES: tuple[_TargetLine, ...] = (
    _TargetLine(
        printed_label="Revenue from operations",
        concept_qname="in-bse-fin:RevenueFromOperations",
        normalized_unit="INR crore",
        unit_ref="INR",
        scale=10_000_000,
        decimals=-7,
    ),
    _TargetLine(
        printed_label="Total Income",
        concept_qname="in-bse-fin:Income",
        normalized_unit="INR crore",
        unit_ref="INR",
        scale=10_000_000,
        decimals=-7,
    ),
    _TargetLine(
        printed_label="Profit before tax",
        concept_qname="in-bse-fin:ProfitBeforeTax",
        normalized_unit="INR crore",
        unit_ref="INR",
        scale=10_000_000,
        decimals=-7,
    ),
    _TargetLine(
        printed_label="Profit for the period",
        concept_qname="in-bse-fin:ProfitLossForPeriod",
        normalized_unit="INR crore",
        unit_ref="INR",
        scale=10_000_000,
        decimals=-7,
    ),
    _TargetLine(
        printed_label="Basic (in ₹ per share)",
        concept_qname="in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        normalized_unit="INR per share",
        unit_ref="INR_per_share",
        scale=1,
        decimals=2,
    ),
)


def _band_rows(words: tuple[PageWord, ...]) -> list[list[PageWord]]:
    """Group words into horizontal row bands (``ROW_BAND_TOLERANCE_PT``)."""
    rows: list[list[PageWord]] = []
    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        for row in rows:
            if abs(row[0].y0 - word.y0) <= ROW_BAND_TOLERANCE_PT:
                row.append(word)
                break
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


def _row_label(row: list[PageWord]) -> str:
    """Join the label-column words (left of the value region) of a row."""
    return " ".join(word.text for word in row if word.x0 < LABEL_MAX_X0_PT).strip()


def _leftmost_value(row: list[PageWord]) -> PageWord | None:
    """Return the leftmost numeric cell in the value region of a row.

    The leftmost value column is the current-quarter (Apr–Jun 2024) column per
    the oracle; a bare ``-`` nil cell is not a value.
    """
    numeric = [
        word
        for word in row
        if word.x0 >= VALUE_MIN_X0_PT and _NUMERIC_TOKEN.match(word.text)
    ]
    numeric.sort(key=lambda w: w.x0)
    return numeric[0] if numeric else None


def _parse_number(token: str) -> Decimal:
    """Parse a printed figure into a Decimal (commas stripped, parens negate)."""
    negative = token.startswith("(") and token.endswith(")")
    digits = token.strip("()").replace(",", "")
    value = Decimal(digits)
    return -value if negative else value


def _find_statement_page(pdf: LoadedPdf) -> PdfPage:
    """Return the consolidated-P&L statement page, or raise if not found."""
    for page in pdf.pages:
        if _STATEMENT_MARKER in page.text and _ANCHOR_LABEL in page.text:
            return page
    raise NumberParseError(
        f"consolidated statement page not found in {pdf.source_id}"
    )


def _observation_for(
    target: _TargetLine,
    value_word: PageWord,
    *,
    page: PdfPage,
    pdf: LoadedPdf,
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
        entity_scheme=ENTITY_SCHEME,
        entity_id=ENTITY_ID,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        unit_ref=target.unit_ref,
        currency=REPORTING_CURRENCY,
        scale=target.scale,
        decimals=target.decimals,
        provenance=provenance,
    )


def extract_consolidated_pl(
    pdf: LoadedPdf,
    *,
    retrieved_at: datetime,
) -> list[Observation]:
    """Extract the Q1 FY25 consolidated P&L line items as typed Observations.

    Raises :class:`NumberParseError` if the statement page or any target line
    item is missing, so a partial extraction never silently drops a fact.
    """
    page = _find_statement_page(pdf)
    rows = _band_rows(page.words)
    labelled = {_row_label(row): row for row in rows}

    observations: list[Observation] = []
    for target in TARGET_LINES:
        row = labelled.get(target.printed_label)
        if row is None:
            raise NumberParseError(
                f"line item {target.printed_label!r} not found on page {page.page_number}"
            )
        value_word = _leftmost_value(row)
        if value_word is None:
            raise NumberParseError(
                f"no numeric value for {target.printed_label!r} on page {page.page_number}"
            )
        observations.append(
            _observation_for(
                target,
                value_word,
                page=page,
                pdf=pdf,
                retrieved_at=retrieved_at,
            )
        )
    return observations
