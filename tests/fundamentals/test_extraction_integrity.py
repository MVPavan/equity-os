"""Integrity regressions at the held-document and occurrence adapter boundaries."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from fundamentals.contracts.canonical import StatementFamily
from fundamentals.evidence.mapping import Selector
from fundamentals.ingest.pdf_source import load_pdf


def _pdf_bytes(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 50), text)
    body = document.tobytes()
    document.close()
    return body


def test_pdf_parser_reads_the_verified_buffer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replacing the pathname at parser entry cannot replace the already verified content."""
    original = _pdf_bytes("verified original")
    replacement = _pdf_bytes("unverified replacement")
    path = tmp_path / "held.pdf"
    path.write_bytes(original)
    open_document = pymupdf.open

    def replace_at_open(*args: Any, **kwargs: Any) -> Any:
        path.write_bytes(replacement)
        return open_document(*args, **kwargs)

    monkeypatch.setattr(pymupdf, "open", replace_at_open)
    pdf = load_pdf(
        source_id="held", path=path, expected_sha256=hashlib.sha256(original).hexdigest()
    )
    assert "verified original" in pdf.page(1).text
    assert "unverified replacement" not in pdf.page(1).text


def test_two_contains_predicates_can_share_a_context() -> None:
    """Tax and exp both match 'Tax exp' even though neither predicate contains the other."""
    left = Selector(statement_family=StatementFamily.PL, labels=("Tax",), section="Tax")
    right = Selector(statement_family=StatementFamily.PL, labels=("Tax",), section="exp")
    assert left.overlaps(right)
