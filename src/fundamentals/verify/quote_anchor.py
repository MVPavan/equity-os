"""Quote-anchor: bind a claim to an exact page/block/span in the held source.

Provenance for a PDF-sourced claim names a page, a block index, and a
``start:end`` character span within that block. Verification resolves that exact
span and checks the claimed quote appears there — it does not scan the page for
the substring, because substring presence anywhere is not proof that the claim
was read from the cited location. A missing page/block, a malformed or
out-of-range span, or a quote absent from the resolved span all fail closed.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.pdf_source import LoadedPdf


class HasProvenance(Protocol):
    """Anything carrying provenance — an Observation or a GuidanceClaim."""

    @property
    def provenance(self) -> Provenance: ...


class QuotedBounds(Protocol):
    """Anything quoting a range: a GuidanceClaim, or a ledger quote claim."""

    @property
    def source_quote(self) -> str | None: ...

    @property
    def lower_bound(self) -> Decimal: ...

    @property
    def upper_bound(self) -> Decimal: ...


class SourceBlock(BaseModel):
    """One extracted text block located by page and block index."""

    model_config = ConfigDict(frozen=True)

    page: int
    block: int
    text: str


class SourceDocument(BaseModel):
    """The held source's extracted text, addressable by page and block."""

    model_config = ConfigDict(frozen=True)

    blocks: tuple[SourceBlock, ...]

    def find(self, page: int, block: int) -> SourceBlock | None:
        """Return the block at ``(page, block)`` or ``None`` if absent."""
        for candidate in self.blocks:
            if candidate.page == page and candidate.block == block:
                return candidate
        return None


class QuoteAnchorResult(BaseModel):
    """Whether the claim's quote resolves at its exact provenance span."""

    model_config = ConfigDict(frozen=True)

    anchored: bool
    reason: str | None = None
    resolved_text: str | None = None


def _parse_span(span: str) -> tuple[int, int] | None:
    """Parse a ``start:end`` character span; ``None`` if malformed."""
    parts = span.split(":")
    if len(parts) != 2:
        return None
    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError:
        return None
    if start < 0 or end < start:
        return None
    return start, end


def verify_quote_anchor(
    claim: HasProvenance, expected_quote: str, source: SourceDocument
) -> QuoteAnchorResult:
    """Verify the claim's quote resolves at its exact page/block/span."""
    provenance = claim.provenance
    if provenance.anchor_type is not SourceAnchorType.PDF_SPAN:
        return QuoteAnchorResult(
            anchored=False,
            reason=f"anchor_type {provenance.anchor_type} is not a PDF span",
        )
    if provenance.page is None or provenance.block is None or provenance.span is None:
        return QuoteAnchorResult(
            anchored=False, reason="PDF span anchor missing page, block, or span"
        )

    block = source.find(provenance.page, provenance.block)
    if block is None:
        return QuoteAnchorResult(
            anchored=False,
            reason=f"no block at page {provenance.page} block {provenance.block}",
        )

    parsed = _parse_span(provenance.span)
    if parsed is None:
        return QuoteAnchorResult(anchored=False, reason=f"malformed span {provenance.span!r}")
    start, end = parsed
    if end > len(block.text):
        return QuoteAnchorResult(
            anchored=False,
            reason=(f"span {provenance.span} out of range for block of length {len(block.text)}"),
        )

    resolved = block.text[start:end]
    if expected_quote not in resolved:
        return QuoteAnchorResult(
            anchored=False,
            reason="claimed quote is not present at the resolved span",
            resolved_text=resolved,
        )
    return QuoteAnchorResult(anchored=True, resolved_text=resolved)


def guidance_quote_holds(claim: QuotedBounds, resolved_span_text: str) -> bool:
    """Verify the anchored span still carries the claim captured at extraction.

    The resolved span must equal the ``source_quote`` stored at extraction (so a
    re-pointed provenance fails), and the claim's numeric bounds must be
    represented in that quote (so mutating 3–4% to 8–10% while keeping the old
    provenance fails).
    """
    if claim.source_quote is None:
        return False
    if resolved_span_text != claim.source_quote:
        return False
    numbers = {
        Decimal(value.replace(",", ""))
        for value in re.findall(r"\d[\d,]*(?:\.\d+)?", claim.source_quote)
    }
    return claim.lower_bound in numbers and claim.upper_bound in numbers


def source_document(pdf: LoadedPdf) -> SourceDocument:
    """Reconstruct a page/block-addressable SourceDocument from a loaded PDF."""
    blocks = tuple(
        SourceBlock(page=page.page_number, block=block.number, text=block.text)
        for page in pdf.pages
        for block in page.blocks
    )
    return SourceDocument(blocks=blocks)
