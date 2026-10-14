"""A header-less figure column is recovered whatever its figures print as, never a Sr No column."""

from __future__ import annotations

import pytest

from fundamentals.extract.pdf_figure_columns import unheaded_columns
from fundamentals.ingest.pdf_source import PageWord

_HEADED = (300.0, 340.0)
_LOOSE = (400.0, 440.0)
_SERIAL = (10.0, 20.0)


def _words(x: tuple[float, float], texts: list[str]) -> list[PageWord]:
    """One word per row at the given x extent."""
    return [
        PageWord(
            x0=x[0], y0=row * 10, x1=x[1], y1=row * 10 + 8, text=text, block=0, line=row, word_no=0
        )
        for row, text in enumerate(texts)
    ]


def _headed(word: PageWord) -> int | None:
    """The one header column holds words at its extent."""
    return 0 if word.x0 == _HEADED[0] else None


@pytest.mark.parametrize(
    "texts",
    [
        pytest.param(["1,234", "567", "(89)", "1,302"], id="integer"),
        pytest.param(["1,234.50", "-", "(89)", "1,145.50"], id="mixed"),
        pytest.param(["12.50", "3.75", "(0.25)", "16.00"], id="decimal"),
    ],
)
def test_a_figure_column_without_a_header_is_recovered(texts: list[str]) -> None:
    """Its cells must never join a row label, so the column is kept even with integer figures."""
    words = _words(_HEADED, ["1.00", "2.00", "3.00", "4.00"]) + _words(_LOOSE, texts)
    [column] = unheaded_columns(words, _headed)
    assert (column.x0, column.x1) == _LOOSE


def test_serial_and_note_numbers_never_form_a_figure_column() -> None:
    """A Sr No or note column prints only small integers, which must stay label words."""
    words = _words(_HEADED, ["1.00", "2.00", "3.00", "4.00"]) + _words(
        _SERIAL, ["1", "2", "3", "4"]
    )
    assert unheaded_columns(words, _headed) == []
