"""Statement column extents, including figure columns whose header the text layer lost.

A scanned page can print a column group's figures while its header words are missing
from the text layer (Apar FY26 Q3 results p3: the standalone quarter columns). Such a
column is recovered from its figures alone so they never join a row label; it has no
header, so it is never bound to a basis and yields no occurrences.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.pdf_source import PageWord

# A printed figure with a fraction, optionally negative: never a Sr No or a note number.
_FIGURE = re.compile(r"\(?-?\d[\d,]*\.\d+\)?")


class HeaderColumn(BaseModel):
    """A header-row column before basis binding.

    ``header_x0``/``header_x1`` are the printed header's extent; ``x0``/``x1`` widen
    it to the figures printed under it, which are often right-aligned past it.
    """

    model_config = ConfigDict(frozen=True)

    x0: float
    x1: float
    header_x0: float
    header_x1: float
    date_text: str


def unheaded_columns(
    words: Sequence[PageWord], column_of: Callable[[PageWord], int | None]
) -> list[HeaderColumn]:
    """Columns of figures under no header column, each overlapping in x.

    A column must hold at least half as many figures as the sparsest header column, so
    a few formula references in the label column (``(11-12)`` read as ``(11.12)``) never
    form one.
    """
    figures = [word for word in words if _FIGURE.fullmatch(word.text)]
    placed = [column_of(word) for word in figures]
    counts = Counter(index for index in placed if index is not None)
    loose = sorted(
        (word for word, index in zip(figures, placed, strict=True) if index is None), key=_x0
    )
    bands: list[tuple[float, float, int]] = []
    for word in loose:
        if bands and word.x0 <= bands[-1][1]:
            x0, x1, count = bands.pop()
            bands.append((x0, max(x1, word.x1), count + 1))
        else:
            bands.append((word.x0, word.x1, 1))
    return [
        HeaderColumn(x0=x0, x1=x1, header_x0=x0, header_x1=x1, date_text="")
        for x0, x1, count in bands
        if counts and 2 * count >= min(counts.values())
    ]


def _x0(word: PageWord) -> float:
    """A word's left edge."""
    return word.x0
