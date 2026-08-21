"""Load a lawfully-held PDF locally and expose its text + word geometry.

This adapter is deliberately *local-only*: it opens a PDF that is already held
on disk, verifies its content hash, and eagerly extracts every page's text,
word geometry and block text into frozen pydantic models. No bytes are ever
transmitted anywhere — extraction downstream (numbers, guidance) reads only
these in-memory models, never an external service.

Fail-closed contract: if the file is missing, unreadable, or its sha256 does
not match the expected hash recorded in the retrieval manifest, loading raises
:class:`PdfIntegrityError` and yields no pages. A parser must never see a
document whose provenance cannot be proven.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pymupdf
from pydantic import BaseModel, ConfigDict

_SHA256_CHUNK_BYTES = 1 << 20
_TEXT_BLOCK_TYPE = 0


class PdfIntegrityError(RuntimeError):
    """Raised when the held PDF is missing or its content hash mismatches."""


class PageWord(BaseModel):
    """A single positioned word token from ``page.get_text('words')``.

    Coordinates are PDF points; ``block``/``line``/``word_no`` are PyMuPDF's
    structural indices, used for deterministic row banding and anchoring.
    """

    model_config = ConfigDict(frozen=True)

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int
    line: int
    word_no: int


class PdfBlock(BaseModel):
    """A text block's reconstructed text and its PyMuPDF block number."""

    model_config = ConfigDict(frozen=True)

    number: int
    text: str


class PdfPage(BaseModel):
    """One page's flat text, word geometry, and text-block reconstruction."""

    model_config = ConfigDict(frozen=True)

    page_number: int
    text: str
    words: tuple[PageWord, ...]
    blocks: tuple[PdfBlock, ...]

    def block_by_number(self, number: int) -> PdfBlock | None:
        """Return the text block with ``number``, or ``None`` if absent."""
        for block in self.blocks:
            if block.number == number:
                return block
        return None


class LoadedPdf(BaseModel):
    """A fully-extracted, hash-verified PDF held entirely in memory."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    file_sha256: str
    page_count: int
    pages: tuple[PdfPage, ...]

    def page(self, page_number: int) -> PdfPage:
        """Return the 1-based ``page_number`` page, or raise if out of range."""
        for candidate in self.pages:
            if candidate.page_number == page_number:
                return candidate
        raise PdfIntegrityError(f"page {page_number} not present in {self.source_id}")


def compute_file_sha256(path: Path) -> str:
    """Return the hex sha256 of the file at ``path``, read in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _block_text(block: dict[str, Any]) -> str:
    """Reconstruct a text block's content by joining its lines with newlines."""
    lines: list[str] = []
    for line in block.get("lines", []):
        lines.append("".join(span["text"] for span in line.get("spans", [])))
    return "\n".join(lines)


def _extract_page(document: Any, index: int) -> PdfPage:
    """Extract text, word geometry, and text blocks for one 0-based page."""
    page = document[index]
    words = tuple(
        PageWord(
            x0=float(word[0]),
            y0=float(word[1]),
            x1=float(word[2]),
            y1=float(word[3]),
            text=str(word[4]),
            block=int(word[5]),
            line=int(word[6]),
            word_no=int(word[7]),
        )
        for word in page.get_text("words")
    )
    layout: dict[str, Any] = page.get_text("dict")
    blocks = tuple(
        PdfBlock(number=int(block["number"]), text=_block_text(block))
        for block in layout.get("blocks", [])
        if block.get("type") == _TEXT_BLOCK_TYPE
    )
    return PdfPage(
        page_number=index + 1,
        text=str(page.get_text("text")),
        words=words,
        blocks=blocks,
    )


def load_pdf(*, source_id: str, path: Path, expected_sha256: str) -> LoadedPdf:
    """Load and hash-verify a held PDF, failing closed on any integrity gap.

    Raises :class:`PdfIntegrityError` when the file is absent or its content
    hash differs from ``expected_sha256`` — no pages are returned in that case.
    """
    if not path.is_file():
        raise PdfIntegrityError(f"held PDF not found: {path}")
    actual_sha256 = compute_file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise PdfIntegrityError(
            f"sha256 mismatch for {path}: expected {expected_sha256}, got {actual_sha256}"
        )
    document: Any = pymupdf.open(path)  # type: ignore[no-untyped-call]
    try:
        pages = tuple(_extract_page(document, index) for index in range(document.page_count))
        page_count = int(document.page_count)
    finally:
        document.close()
    return LoadedPdf(
        source_id=source_id,
        file_sha256=actual_sha256,
        page_count=page_count,
        pages=pages,
    )
