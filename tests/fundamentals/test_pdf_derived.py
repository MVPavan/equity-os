"""THERMAX-style derived revenue: recover a garbled-label revenue by the income identity.

When a consolidated results PDF prints its revenue line with a glyph-garbled label
(THERMAX Q3FY25 OCRs ``Revenue from operations`` as ``Revenuc from operations``) the
label matches no row, so neither the direct read nor the sub-component summation can
recover it. But if the statement's ``Total income`` and ``Other income`` read cleanly
on the same current-quarter column, revenue is the rearrangement of the statement's
own identity ``Income = Revenue + Other income`` — i.e. ``Income − Other income``.

These tests drive the OCR recovery lane with a deterministic mock engine (no bytes
leave the process): a garbled-label statement whose income and other-income read
cleanly derives revenue with a computed trace and a two-anchor provenance; the same
statement missing either input stays fail-closed (revenue absent, never guessed); and
a clean-label statement reads revenue directly rather than deriving it. The fail-
closed guard against a *present but non-reconciling* split lives in the summation
suite (``test_bse_pdf``); here the revenue line is genuinely unreadable.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf

from fundamentals.api.config import PdfParseConfig
from fundamentals.contracts.observation import AccountingFramework, Observation, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.pdf_number_parser import PdfParseSpec
from fundamentals.extract.pdf_ocr_recovery import DEFAULT_OCR_DPI, extract_consolidated_pl_via_ocr
from fundamentals.ingest.ocr_engine import OcrToken
from fundamentals.ingest.pdf_source import load_pdf

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_RETRIEVED_AT = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
INCOME = "in-bse-fin:Income"
PFP = "in-bse-fin:ProfitLossForPeriod"

_SCALE = DEFAULT_OCR_DPI / 72.0
_CUR_X = 240.0  # current-quarter column (points)
_CMP_X = 340.0  # a comparative column
_LBL_X = 60.0

# The real THERMAX Q3FY25 figures: the printed revenue cell reads 2507.76 but its
# label is garbled, while Total income 2539.27 and Other income 31.51 read cleanly —
# and 2539.27 - 31.51 == 2507.76.
_GARBLED_REVENUE_LABEL = "Revenuc from operations"
_REVENUE_CELL = "2507.76"
_OTHER_INCOME = "31.51"
_TOTAL_INCOME = "2539.27"


def _spec() -> PdfParseSpec:
    config = PdfParseConfig()
    return PdfParseSpec(
        scope_marker=config.scope_marker,
        statement_confirmations=config.statement_confirmations,
        anchor_label=config.anchor_label,
        target_lines=config.target_lines,
        entity_scheme="nse-symbol",
        entity_id="SYNTH",
        currency="INR",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
    )


def _tok(
    text: str, x_pt: float, y_pt: float, *, conf: float = 0.97, w_pt: float = 40.0
) -> OcrToken:
    """Build one OCR token at a point position, converted to image pixels."""
    return OcrToken(
        text=text,
        x0=x_pt * _SCALE,
        y0=y_pt * _SCALE,
        x1=(x_pt + w_pt) * _SCALE,
        y1=(y_pt + 8.0) * _SCALE,
        confidence=conf,
    )


def _statement_tokens(
    *,
    revenue_label: str = _GARBLED_REVENUE_LABEL,
    revenue: str = _REVENUE_CELL,
    include_other_income: bool = True,
    other_income: str = _OTHER_INCOME,
    total_income: str = _TOTAL_INCOME,
    total_income_conf: float = 0.97,
) -> tuple[OcrToken, ...]:
    """Tokens for a self-consistent consolidated statement with a (default) garbled revenue.

    ``Income - Total expenses = first profit subtotal`` and ``TCI = net profit + OCI``
    both hold, so the OCR page passes its own cross-foot gate even though the income
    build-up identity is not computable (revenue's label is garbled). A caller may
    unglitch the revenue label, drop other income, or lower the income confidence to
    exercise the derive / fail-closed branches.
    """
    tokens: list[OcrToken] = [
        _tok("(Rs. in Crore)", _LBL_X, 40.0),
        _tok("Consolidated", 200.0, 52.0),
        _tok("Dec31,2024", _CUR_X, 90.0),
        _tok("Dec31,2023", _CMP_X, 90.0),
    ]
    body: list[tuple[str, str, float]] = [(revenue_label, revenue, 0.95)]
    if include_other_income:
        body.append(("Other income", other_income, 0.95))
    body.extend(
        [
            ("Total income", total_income, total_income_conf),
            ("Total expenses", "2400.00", 0.95),
            ("Profit before tax exceptional items", "139.27", 0.95),
            ("Profit before tax", "139.27", 0.95),
            ("Total tax expense", "25.54", 0.95),
            ("Net profit for the period", "100.00", 0.95),
            ("Total other comprehensive income", "10.00", 0.95),
            ("Total comprehensive income for the period", "110.00", 0.95),
            ("Basic", "8.86", 0.95),
        ]
    )
    y = 120.0
    for label, value, conf in body:
        tokens.append(_tok(label, _LBL_X, y, w_pt=len(label) * 4.0))
        tokens.append(_tok(value, _CUR_X, y, conf=conf))
        tokens.append(_tok("0.00", _CMP_X, y))
        y += 15.0
    return tuple(tokens)


class _MockOcrEngine:
    """Deterministic OCR engine that returns fixed tokens, ignoring the image bytes."""

    def __init__(self, tokens: tuple[OcrToken, ...]) -> None:
        self._tokens = tokens

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:  # noqa: ARG002 - fixed tokens
        return self._tokens


def _write_garbled_pdf(path: Path) -> str:
    """Write a 1-page PDF whose text layer is too garbled to parse but is P&L-shaped.

    The scope word and labels are glyph-mangled so the text lane fails closed, but the
    page carries clean ``Income:``/``Expenses:`` section words so the OCR lane's page
    locator selects it (mirroring the real THERMAX detailed statement).
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((_LBL_X, 60), "Statement of unaudited financial results", fontsize=9)
    page.insert_text((_LBL_X, 75), "Consolidut<-d", fontsize=9)
    page.insert_text((_LBL_X, 95), "1 Income:", fontsize=9)
    page.insert_text((_LBL_X, 110), "Rc,·cnue from opcrations 2507.76", fontsize=9)
    page.insert_text((_LBL_X, 125), "2 Expenses:", fontsize=9)
    page.insert_text((_LBL_X, 140), "Total expcrucs 2400.00", fontsize=9)
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recover(path: Path, sha: str, engine: _MockOcrEngine) -> list[Observation]:
    loaded = load_pdf(source_id="bse-results-pdf", path=path, expected_sha256=sha)
    return extract_consolidated_pl_via_ocr(
        loaded,
        path,
        spec=_spec(),
        ocr_engine=engine,
        retrieved_at=_RETRIEVED_AT,
    )


def _by_concept(observations: list[Observation]) -> dict[str, Observation]:
    return {obs.concept_qname: obs for obs in observations}


def test_ocr_derives_revenue_from_income_less_other_when_label_garbled(tmp_path: Path) -> None:
    # Revenue's label is garbled (matches no row) so it is neither read nor summable,
    # but Total income and Other income read cleanly: revenue is recovered as
    # Income - Other income == 2539.27 - 31.51 == 2507.76.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    by_concept = _by_concept(_recover(pdf, sha, _MockOcrEngine(_statement_tokens())))

    assert INCOME in by_concept  # the derivation's total input was cleanly read
    assert REVENUE in by_concept
    revenue = by_concept[REVENUE]
    assert revenue.normalized_value == Decimal("2507.76")
    assert revenue.normalized_value == by_concept[INCOME].normalized_value - Decimal(_OTHER_INCOME)


def test_derived_revenue_carries_computed_trace_and_both_source_anchors(tmp_path: Path) -> None:
    # The derived observation records its computed trace ("2539.27 - 31.51") and a
    # provenance that references BOTH contributing cells and marks the value derived,
    # while remaining a first-party PDF fact (a PDF_SPAN anchor on the results page).
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    revenue = _by_concept(_recover(pdf, sha, _MockOcrEngine(_statement_tokens())))[REVENUE]

    assert revenue.raw_value == f"{_TOTAL_INCOME} - {_OTHER_INCOME}"
    provenance = revenue.provenance
    assert provenance.anchor_type is SourceAnchorType.PDF_SPAN
    assert provenance.source_id == "bse-results-pdf"  # first-party host, not a derived aggregator
    assert provenance.span is not None
    assert provenance.span.startswith("derive(")
    # Both contributing cells' printed values appear in the two-anchor span trace.
    assert _TOTAL_INCOME in provenance.span
    assert _OTHER_INCOME in provenance.span


def test_ocr_revenue_fails_closed_when_other_income_absent(tmp_path: Path) -> None:
    # Total income reads but there is no Other income line: the second derivation
    # input is missing, so revenue stays fail-closed (never Income taken as revenue).
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    by_concept = _by_concept(
        _recover(pdf, sha, _MockOcrEngine(_statement_tokens(include_other_income=False)))
    )
    assert INCOME in by_concept
    assert REVENUE not in by_concept


def test_ocr_revenue_fails_closed_when_total_income_unreadable(tmp_path: Path) -> None:
    # Other income reads but Total income's cell is below the confidence floor and is
    # dropped: with no clean total the identity cannot be closed, so revenue stays
    # fail-closed. The page still passes its gate via the TCI = net profit + OCI check.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    by_concept = _by_concept(
        _recover(pdf, sha, _MockOcrEngine(_statement_tokens(total_income_conf=0.30)))
    )
    assert INCOME not in by_concept
    assert REVENUE not in by_concept
    # The rest of the statement still recovers, so the page was not wholly rejected.
    assert PFP in by_concept


def test_ocr_reads_revenue_directly_and_does_not_derive_when_label_clean(tmp_path: Path) -> None:
    # With a clean revenue label the value is read directly from its own cell, not
    # derived: its raw value is the printed token and its anchor is a single cell span.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    revenue = _by_concept(
        _recover(
            pdf, sha, _MockOcrEngine(_statement_tokens(revenue_label="Revenue from operations"))
        )
    )[REVENUE]
    assert revenue.normalized_value == Decimal(_REVENUE_CELL)
    assert revenue.raw_value == _REVENUE_CELL
    assert revenue.provenance.span is not None
    assert not revenue.provenance.span.startswith("derive(")
