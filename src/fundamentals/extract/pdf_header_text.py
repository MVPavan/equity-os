"""Shared PDF-header token normalization and quarter-marker vocabulary."""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_HOMOGLYPH_TRANSLATION = str.maketrans(
    {
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "H",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Υ": "Y",
        "Χ": "X",
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "У": "Y",
        "Х": "X",
        "І": "I",
        "Ј": "J",
        "Ѕ": "S",
    }
)
QUARTER_HEADER_MARKERS: tuple[tuple[str, ...], ...] = (
    ("quarter", "ended"),
    ("3", "months", "ended"),
    ("three", "months", "ended"),
)
NON_QUARTER_HEADER_MARKERS: tuple[tuple[str, ...], ...] = (
    ("nine", "months"),
    ("9", "months"),
    ("six", "months"),
    ("half", "year"),
    ("year", "ended"),
)


def normalize_text_tokens(text: str) -> list[str]:
    """Split ordinary text into lowercase alphanumeric tokens without OCR repair."""
    return _NON_ALNUM.sub(" ", text.lower()).split()


def normalize_header_tokens(text: str) -> list[str]:
    """Normalize OCR homoglyphs, then split header text into keyword tokens."""
    return normalize_text_tokens(text.translate(_HOMOGLYPH_TRANSLATION))
