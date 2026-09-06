"""The statement's printed monetary unit and the shared fail-closed parse error.

Split out of :mod:`fundamentals.extract.pdf_column_geometry` (which re-exports both
names, so importers are unaffected) when the per-issuer declared unit pushed that
module past the file-size ceiling. The unit is what every monetary value on a
statement is scaled by, so reading it wrong is a silent factor-of-100 error — hence
the fail-closed contract lives here with it.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum

from fundamentals.ingest.pdf_source import PageWord


class NumberParseError(RuntimeError):
    """Raised when a required statement page, column, unit, or line item is missing."""


class PdfPrintedUnit(StrEnum):
    """The unit a statement prints its monetary values in.

    Declared per issuer only where a scanned text layer garbles the printed marker;
    it never overrides a legible printed unit.
    """

    CRORE = "crore"
    LAKH = "lakh"
    MILLION = "million"


# Monetary values are normalized to crore so they share the XBRL comparison key.
_CRORE_PER_UNIT: dict[str, Decimal] = {
    PdfPrintedUnit.CRORE.value: Decimal(1),
    PdfPrintedUnit.LAKH.value: Decimal("0.01"),
    PdfPrintedUnit.MILLION.value: Decimal("0.1"),
}


def _detect_unit_factor(
    header_words: tuple[PageWord, ...], *, declared: PdfPrintedUnit | None = None
) -> Decimal:
    """Return the crore-conversion factor for the statement's printed unit.

    The unit is read from the statement header (above the value rows), glyph- and
    OCR-tolerant: the ``₹`` symbol is frequently mangled in the text layer, so only
    the unit word (``crore``/``crores``/OCR ``crorc``, ``lakh``/``lac``,
    ``million``) is matched. Exactly one unit family must be present; a missing or
    ambiguous marker raises :class:`NumberParseError` rather than assuming a scale.

    ``declared`` is the per-issuer declaration for a scanned statement whose marker
    is garbled beyond recognition. It only fills a *missing* marker: a declaration
    that disagrees with a legible printed unit raises rather than silently rescaling
    every value on the statement.
    """
    text = " ".join(word.text for word in header_words).lower()
    # "cror"/"lakh"/"million" are distinctive enough to match without a leading word
    # boundary, so an OCR word-join ("incrores") is still detected; the short,
    # ambiguous "lac" keeps its boundaries (else it would match inside "black").
    present = {
        PdfPrintedUnit.CRORE.value: bool(re.search(r"cror", text)),
        PdfPrintedUnit.LAKH.value: bool(re.search(r"lakh|\blac\b|\blacs\b", text)),
        PdfPrintedUnit.MILLION.value: bool(re.search(r"million", text)),
    }
    families = [family for family, found in present.items() if found]
    if len(families) == 1:
        printed = families[0]
        if declared is not None and declared.value != printed:
            raise NumberParseError(
                f"declared printed unit {declared.value!r} conflicts with the unit printed on "
                f"the statement ({printed!r})"
            )
        return _CRORE_PER_UNIT[printed]
    if not families and declared is not None:
        return _CRORE_PER_UNIT[declared.value]
    raise NumberParseError(
        f"statement printed-unit marker is missing or ambiguous (found: {families})"
    )
