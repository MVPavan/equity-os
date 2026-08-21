"""Local rule-based extraction of management guidance ranges.

Management guidance for Infosys Q1 FY25 is stated in the held earnings
transcript (revenue growth 3%–4% constant currency; operating margin 20%–22%
for the financial year). This module extracts those ranges deterministically
from PyMuPDF block text using anchored regular expressions and binds each claim
to an exact page/block/span quote via :class:`Provenance`.

The extraction is entirely local: no model calls, no network, no external
transmission of any bytes. :func:`resolve_span` re-reads the exact block text at
a claim's anchor so the binding can be verified — a claim whose recorded span no
longer yields its quote fails the anchor check.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.guidance_claim import EpistemicClass, GuidanceClaim
from fundamentals.contracts.observation import Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.pdf_source import LoadedPdf

PERCENT_UNIT = "percent"
FINANCIAL_YEAR_HORIZON = "FY25"
CONSTANT_CURRENCY_QUALIFIER = "constant currency"
_CONSTANT_CURRENCY_MARKER = "constant"


class GuidanceExtractionError(RuntimeError):
    """Raised when an expected guidance range cannot be located in the PDF."""


class _GuidanceRule(BaseModel):
    """A deterministic rule mapping a guidance sentence to a typed claim."""

    model_config = ConfigDict(frozen=True)

    metric: str
    pattern: str
    horizon: str


GUIDANCE_RULES: tuple[_GuidanceRule, ...] = (
    _GuidanceRule(
        metric="revenue_growth",
        pattern=r"revenue growth guidance.*?(\d+)% to (\d+)%",
        horizon=FINANCIAL_YEAR_HORIZON,
    ),
    _GuidanceRule(
        metric="operating_margin",
        pattern=r"operating margin guidance.*?(\d+)% to (\d+)%",
        horizon=FINANCIAL_YEAR_HORIZON,
    ),
)


def _claim_for(
    rule: _GuidanceRule,
    pdf: LoadedPdf,
    *,
    retrieved_at: datetime,
) -> GuidanceClaim:
    """Find the first block matching ``rule`` and build an anchored claim."""
    matcher = re.compile(rule.pattern, re.IGNORECASE)
    for page in pdf.pages:
        for block in page.blocks:
            match = matcher.search(block.text)
            if match is None:
                continue
            constant_currency = _CONSTANT_CURRENCY_MARKER in block.text.lower()
            qualifiers = (CONSTANT_CURRENCY_QUALIFIER,) if constant_currency else ()
            provenance = Provenance(
                source_id=pdf.source_id,
                file_sha256=pdf.file_sha256,
                anchor_type=SourceAnchorType.PDF_SPAN,
                page=page.page_number,
                block=block.number,
                span=f"{match.start()}:{match.end()}",
                retrieved_at=retrieved_at,
            )
            return GuidanceClaim(
                metric=rule.metric,
                lower_bound=Decimal(match.group(1)),
                upper_bound=Decimal(match.group(2)),
                unit=PERCENT_UNIT,
                constant_currency=constant_currency,
                horizon=rule.horizon,
                scope=Scope.CONSOLIDATED,
                qualifiers=qualifiers,
                epistemic_class=EpistemicClass.FORECAST,
                provenance=provenance,
            )
    raise GuidanceExtractionError(
        f"guidance for {rule.metric!r} not found in {pdf.source_id}"
    )


def extract_guidance_claims(
    pdf: LoadedPdf,
    *,
    retrieved_at: datetime,
) -> list[GuidanceClaim]:
    """Extract all configured management-guidance ranges as typed claims.

    Raises :class:`GuidanceExtractionError` if any configured range is missing,
    so the pipeline fails closed rather than emitting a partial guidance set.
    """
    return [_claim_for(rule, pdf, retrieved_at=retrieved_at) for rule in GUIDANCE_RULES]


def resolve_span(pdf: LoadedPdf, provenance: Provenance) -> str:
    """Return the exact block text at a PDF_SPAN provenance's page/block/span.

    Raises :class:`GuidanceExtractionError` if the anchor is not a PDF span or
    its block/offsets no longer resolve — the fail-closed side of anchoring.
    """
    if provenance.anchor_type is not SourceAnchorType.PDF_SPAN:
        raise GuidanceExtractionError("provenance is not a PDF_SPAN anchor")
    if provenance.page is None or provenance.block is None or provenance.span is None:
        raise GuidanceExtractionError("PDF_SPAN provenance is missing page/block/span")
    page = pdf.page(provenance.page)
    block = page.block_by_number(provenance.block)
    if block is None:
        raise GuidanceExtractionError(
            f"block {provenance.block} not present on page {provenance.page}"
        )
    start_text, end_text = provenance.span.split(":")
    start, end = int(start_text), int(end_text)
    return block.text[start:end]


def anchor_matches(pdf: LoadedPdf, provenance: Provenance, expected_quote: str) -> bool:
    """Return whether the span in ``provenance`` resolves exactly to the quote."""
    try:
        return resolve_span(pdf, provenance) == expected_quote
    except GuidanceExtractionError:
        return False
