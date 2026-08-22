"""OCR recovery lane: acceptance/rejection gates and (optionally) a real engine.

The lane renders a statement page to an image, runs a LOCAL OCR engine, rebuilds
word geometry from the recognized tokens, and re-runs the same band-row/label/
column extractor with OCR-tolerant matching. These tests drive the gate logic
deterministically with a mock engine (no engine dependency, no bytes leaving the
process): a self-consistent recovered statement is accepted, a broken cross-foot
or a low-confidence key cell fails closed. A final test exercises a real local
engine end-to-end when one is installed, and is skipped otherwise.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from fundamentals.api.config import PdfParseConfig
from fundamentals.contracts.observation import AccountingFramework, Observation, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.pdf_number_parser import PdfParseSpec
from fundamentals.extract.pdf_ocr_recovery import (
    DEFAULT_OCR_DPI,
    extract_consolidated_pl_via_ocr,
)
from fundamentals.ingest.ocr_engine import OcrToken, RapidOcrEngine
from fundamentals.ingest.pdf_source import compute_file_sha256, load_pdf

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_RETRIEVED_AT = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
INCOME = "in-bse-fin:Income"
PBT = "in-bse-fin:ProfitBeforeTax"
PFP = "in-bse-fin:ProfitLossForPeriod"
EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

_SCALE = DEFAULT_OCR_DPI / 72.0
_CUR_X = 240.0  # current-quarter column (points)
_CMP_X = 340.0  # a comparative column
_LBL_X = 60.0


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
    revenue: str = "1000.00",
    other_income: str = "50.00",
    total_income: str = "1050.00",
    total_expenses: str = "800.00",
    subtotal: str = "250.00",
    pbt: str = "250.00",
    tax: str = "60.00",
    net_profit: str = "190.00",
    total_oci: str = "10.00",
    tci: str = "200.00",
    eps: str = "5.00",
    total_income_conf: float = 0.97,
    net_profit_conf: float = 0.97,
    eps_conf: float = 0.97,
) -> tuple[OcrToken, ...]:
    """Tokens for a self-consistent consolidated statement (identities hold by default).

    Income build-up (total = revenue + other), income-less-expenses = first
    subtotal, and TCI = net profit + OCI all hold with the defaults; a caller may
    perturb a value or a confidence to exercise the fail-closed gates.
    """
    tokens: list[OcrToken] = [
        _tok("(Rs. in Crore)", _LBL_X, 40.0),
        _tok("Consolidated", 200.0, 52.0),
        _tok("Dec31,2024", _CUR_X, 90.0),
        _tok("Dec31,2023", _CMP_X, 90.0),
    ]
    body: tuple[tuple[str, str, float], ...] = (
        ("Revenue from operations", revenue, 0.95),
        ("Other income", other_income, 0.95),
        ("Total income", total_income, total_income_conf),
        ("Total expenses", total_expenses, 0.95),
        ("Profit before tax exceptional items", subtotal, 0.95),
        ("Profit before tax", pbt, 0.95),
        ("Total tax expense", tax, 0.95),
        ("Net profit for the period", net_profit, net_profit_conf),
        ("Total other comprehensive income", total_oci, 0.95),
        ("Total comprehensive income for the period", tci, 0.95),
        ("Basic", eps, eps_conf),
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

    The scope word and labels are glyph-mangled so the text lane fails closed, but
    the page carries clean ``Income:``/``Expenses:`` section words so the OCR lane's
    page locator selects it (mirroring the real THERMAX detailed statement).
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((_LBL_X, 60), "Statement of unaudited financial results", fontsize=9)
    page.insert_text((_LBL_X, 75), "Consolidut<-d", fontsize=9)
    page.insert_text((_LBL_X, 95), "1 Income:", fontsize=9)
    page.insert_text((_LBL_X, 110), "Rc,·cnue from opcrations 999.00", fontsize=9)
    page.insert_text((_LBL_X, 125), "2 Expenses:", fontsize=9)
    page.insert_text((_LBL_X, 140), "Total expcrucs 888.00", fontsize=9)
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


def _by_concept(observations: list[Observation]) -> dict[str, Decimal]:
    return {obs.concept_qname: obs.normalized_value for obs in observations}


def test_ocr_recovers_all_targets_when_self_consistent(tmp_path: Path) -> None:
    # A garbled text layer fails the deterministic lane; OCR of the page yields a
    # self-consistent statement (income build-up, income-less-expenses, TCI all
    # cross-foot), so every target is recovered with a PDF span anchor.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    got = _recover(pdf, sha, _MockOcrEngine(_statement_tokens()))
    values = _by_concept(got)
    assert values[REVENUE] == Decimal("1000.00")
    assert values[INCOME] == Decimal("1050.00")
    assert values[PBT] == Decimal("250.00")
    assert values[PFP] == Decimal("190.00")
    assert values[EPS] == Decimal("5.00")
    anchor = next(o for o in got if o.concept_qname == INCOME)
    assert anchor.provenance.anchor_type is SourceAnchorType.PDF_SPAN
    assert anchor.provenance.page == 1


def test_ocr_fails_closed_when_crossfoot_residual_exceeds_tolerance(tmp_path: Path) -> None:
    # A mis-read digit breaks the statement's own arithmetic (total income no longer
    # equals revenue + other income, nor income - expenses = subtotal): the whole
    # OCR recovery is rejected rather than emitting a wrong number.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    got = _recover(pdf, sha, _MockOcrEngine(_statement_tokens(total_income="1080.00")))
    assert got == []


def test_ocr_skips_low_confidence_cell_but_recovers_consistent_rest(tmp_path: Path) -> None:
    # Only the EPS cell is low-confidence: it is dropped (fails closed for EPS)
    # while the statement still cross-foots, so the other targets are recovered.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    got = _recover(pdf, sha, _MockOcrEngine(_statement_tokens(eps_conf=0.40)))
    values = _by_concept(got)
    assert EPS not in values
    assert values[INCOME] == Decimal("1050.00")
    assert values[PFP] == Decimal("190.00")


def test_ocr_fails_closed_when_no_identity_is_computable(tmp_path: Path) -> None:
    # Losing total income and net profit (both low confidence) leaves no cross-foot
    # identity computable, so the statement cannot be self-validated at all and the
    # whole recovery fails closed (no partial guess), even though other cells read.
    pdf = tmp_path / "stmt.pdf"
    sha = _write_garbled_pdf(pdf)
    got = _recover(
        pdf, sha, _MockOcrEngine(_statement_tokens(total_income_conf=0.30, net_profit_conf=0.30))
    )
    assert got == []


def test_ocr_fails_closed_when_page_not_locatable(tmp_path: Path) -> None:
    # A PDF with neither a clean statement nor an income/expenses P&L page gives the
    # OCR locator nothing to render: the lane returns no observations.
    pdf = tmp_path / "stmt.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((_LBL_X, 60), "Cover letter to the exchange", fontsize=9)
    doc.save(str(pdf))
    doc.close()
    sha = compute_file_sha256(pdf)
    got = _recover(pdf, sha, _MockOcrEngine(_statement_tokens()))
    assert got == []


# --- real local engine (skipped unless installed) ------------------------------


def _thermax_pdf() -> Path | None:
    matches = sorted(Path("data/raw/watchlist/thermax/bse_pdf").glob("*.pdf"))
    return matches[0] if matches else None


def test_real_local_ocr_recovers_thermax_when_available() -> None:
    # End-to-end with a real local OCR engine on the real THERMAX filing (both
    # gitignored/optional, so skipped in a minimal checkout): the garbled
    # consolidated P&L is recovered and reconciles with the NSE figures.
    pytest.importorskip("rapidocr_onnxruntime")
    pdf_path = _thermax_pdf()
    if pdf_path is None:
        pytest.skip("THERMAX results PDF not present (gitignored)")
    loaded = load_pdf(
        source_id="bse-results-pdf", path=pdf_path, expected_sha256=compute_file_sha256(pdf_path)
    )
    got = _by_concept(
        extract_consolidated_pl_via_ocr(
            loaded,
            pdf_path,
            spec=_spec(),
            ocr_engine=RapidOcrEngine(),
            retrieved_at=_RETRIEVED_AT,
        )
    )
    assert got.get(INCOME) == Decimal("2539.27")
    assert got.get(PFP) == Decimal("113.73")
    assert got.get(EPS) == Decimal("10.29")
