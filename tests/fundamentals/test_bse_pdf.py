"""BSE results-PDF ingestion lane: fetch selection, download verification, the
SEBI-format-general parser generalizations, and NSE + BSE-PDF reconciliation.

Everything is offline and deterministic: the announcement-row selection and
download-verification logic are exercised on synthetic rows / a fake HTTP hook,
and the parser is exercised on synthetic PyMuPDF statements that reproduce the
real Wave-1 format variations (numeric dates, a three-months-vs-nine-months
year-to-date duplicate column, a leading serial-number column, million/lakh
units, a glyph-mangled ``₹``, an enumerated/formula label, split revenue, and a
standalone-only filing). No bytes leave the process.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from fundamentals.api.config import PdfParseConfig
from fundamentals.api.goal_runner import (
    RunMode,
    SourceKind,
    SourceStatus,
    StockOutcome,
    run_stock,
)
from fundamentals.api.watchlist_config import (
    FixturePaths,
    SourceIdentifiers,
    StockConfig,
    StockQuarter,
)
from fundamentals.contracts.observation import AccountingFramework, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.pdf_number_parser import (
    ConsolidatedStatementNotFoundError,
    NumberParseError,
    PdfParseSpec,
    extract_consolidated_pl,
)
from fundamentals.ingest.bse_pdf_source import (
    BseAnnouncement,
    BsePdfFetchError,
    BseResultsPdfSource,
    _parse_filed_at,
    _select_results_row,
    _to_announcement,
)
from fundamentals.ingest.pdf_source import compute_file_sha256, load_pdf
from fundamentals.reconcile.agreement import AgreementStatus

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NSE_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_nse_q3fy25_consolidated.xml"
_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_RETRIEVED_AT = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
INCOME = "in-bse-fin:Income"
PBT = "in-bse-fin:ProfitBeforeTax"
PFP = "in-bse-fin:ProfitLossForPeriod"
EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

# Column x-centres for a six-column SEBI statement: the current quarter is the
# leftmost, and its end date repeats as the nine-months year-to-date column.
_COL_X = {
    "q_current": 250.0,
    "q_prev": 310.0,
    "q_prior_year": 370.0,
    "ytd_current": 430.0,
    "ytd_prior": 490.0,
    "year": 550.0,
}
_SERIAL_X = 40.0
_LABEL_X = 60.0


def _spec(*, entity_id: str = "SYNTH") -> PdfParseSpec:
    """Build a parse spec from the shared Ind-AS defaults for the reviewed quarter."""
    config = PdfParseConfig()
    return PdfParseSpec(
        scope_marker=config.scope_marker,
        statement_confirmations=config.statement_confirmations,
        anchor_label=config.anchor_label,
        target_lines=config.target_lines,
        entity_scheme="nse-symbol",
        entity_id=entity_id,
        currency="INR",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
    )


def _put_row(
    page: pymupdf.Page,
    y: float,
    *,
    serial: str | None,
    label: str,
    values: dict[str, str],
) -> None:
    """Place one statement row: optional serial, a label, and six column cells."""
    if serial is not None:
        page.insert_text((_SERIAL_X, y), serial, fontsize=9)
    page.insert_text((_LABEL_X, y), label, fontsize=9)
    for column, value in values.items():
        page.insert_text((_COL_X[column], y), value, fontsize=9)


def _six(current: str, *, other: str = "0") -> dict[str, str]:
    """Six-column values with a distinct current-quarter cell and filler elsewhere."""
    return {
        "q_current": current,
        "q_prev": other,
        "q_prior_year": other,
        "ytd_current": other,
        "ytd_prior": other,
        "year": other,
    }


def _write_statement(
    path: Path,
    *,
    unit_line: str | None = "(₹ in crore)",
    scope_word: str = "CONSOLIDATED",
    include_serial: bool = True,
    split_revenue: bool = False,
    revenue_label: str = "Revenue from operations",
    values: dict[str, str] | None = None,
) -> str:
    """Write a synthetic SEBI consolidated statement PDF; return its sha256.

    Reproduces the real format: an all-caps title, a printed-unit line with a
    literal ``₹``, ``3 months ended`` / ``9 months ended`` / ``Year ended``
    super-headers, numeric ``DD-MM-YYYY`` column dates where the quarter-end date
    repeats for the year-to-date column, and an optional leading serial column.
    """
    figures = values or {
        "revenue": "1,000",
        "income": "1,010",
        "pbt": "200",
        "pfp": "150",
        "eps": "5.00",
    }
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (_LABEL_X, 80),
        f"STATEMENT OF {scope_word} UNAUDITED FINANCIAL RESULTS "
        "FOR THE QUARTER AND NINE MONTHS ENDED 31 DECEMBER 2024",
        fontsize=9,
    )
    if unit_line is not None:
        page.insert_text((_LABEL_X, 100), unit_line, fontsize=9)
    page.insert_text((_COL_X["q_current"], 120), "3 months ended", fontsize=9)
    page.insert_text((_COL_X["ytd_current"], 120), "9 months ended", fontsize=9)
    page.insert_text((_COL_X["year"], 120), "Year ended", fontsize=9)
    dates = {
        "q_current": "31-12-2024",
        "q_prev": "30-09-2024",
        "q_prior_year": "31-12-2023",
        "ytd_current": "31-12-2024",
        "ytd_prior": "31-12-2023",
        "year": "31-03-2024",
    }
    for column, text in dates.items():
        page.insert_text((_COL_X[column], 140), text, fontsize=9)

    def serial(number: int) -> str | None:
        return str(number) if include_serial else None

    if split_revenue:
        _put_row(page, 170, serial=serial(1), label=revenue_label, values={})
        _put_row(
            page, 185, serial=None, label="- Sale of products", values=_six(figures["revenue"])
        )
    else:
        _put_row(page, 170, serial=serial(1), label=revenue_label, values=_six(figures["revenue"]))
    _put_row(
        page,
        205,
        serial=serial(2),
        label="III. Total income (I+II)",
        values=_six(figures["income"]),
    )
    _put_row(
        page, 225, serial=serial(3), label="V. Profit before tax (1-2)", values=_six(figures["pbt"])
    )
    _put_row(
        page, 245, serial=serial(4), label="IX. Profit for the period", values=_six(figures["pfp"])
    )
    _put_row(
        page, 275, serial=serial(5), label="Basic (not annualised)", values=_six(figures["eps"])
    )
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> object:
    return load_pdf(source_id="synth", path=path, expected_sha256=compute_file_sha256(path))


def _by_concept(observations: list) -> dict[str, Decimal]:  # type: ignore[type-arg]
    return {obs.concept_qname: obs.normalized_value for obs in observations}


# --- parser: current-quarter column (numeric dates, 3-vs-9 month) --------------


def test_current_quarter_column_binds_three_month_not_ytd(tmp_path: Path) -> None:
    # The quarter-end date 31-12-2024 prints twice (3-months and 9-months YTD);
    # the current column must be the leftmost (three-months) one, not the YTD one.
    pdf_path = tmp_path / "stmt.pdf"
    values = {"revenue": "1,000", "income": "1,010", "pbt": "200", "pfp": "150", "eps": "5.00"}
    # Make the YTD current-date column carry a DIFFERENT value; if the parser bound
    # to it the numbers would be the YTD ones, so this pins the three-month choice.
    _write_statement(pdf_path, values=values)
    observations = extract_consolidated_pl(
        _load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT
    )
    got = _by_concept(observations)
    assert got[REVENUE] == Decimal("1000")
    assert got[INCOME] == Decimal("1010")
    assert got[PBT] == Decimal("200")
    assert got[PFP] == Decimal("150")
    assert got[EPS] == Decimal("5.00")


def test_current_quarter_value_is_the_leftmost_not_a_comparative(tmp_path: Path) -> None:
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path)  # comparatives are all "0"
    revenue = next(
        o
        for o in extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
        if o.concept_qname == REVENUE
    )
    # The current-quarter cell (1,000), never a "0" comparative column, is chosen,
    # and the anchor is a real PDF span on the statement page.
    assert revenue.normalized_value == Decimal("1000")
    assert revenue.provenance.anchor_type is SourceAnchorType.PDF_SPAN
    assert revenue.provenance.page == 1 and revenue.provenance.span


# --- parser: serial column, enumerator/formula labels --------------------------


def test_serial_number_column_does_not_blank_the_label(tmp_path: Path) -> None:
    # A leading "Sr. No." numeric column must not swallow the Particulars label:
    # PBT is labelled "V. Profit before tax (1-2)" with a serial "3" at the far left.
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, include_serial=True)
    got = _by_concept(
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
    )
    assert got[PBT] == Decimal("200")
    assert got[INCOME] == Decimal("1010")


def test_label_matches_enumerated_and_formula_variants(tmp_path: Path) -> None:
    # "III. Total income (I+II)" and "IX. Profit for the period" must match the
    # plain configured labels despite the leading enumerator and trailing formula.
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, include_serial=False)
    got = _by_concept(
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
    )
    assert got[INCOME] == Decimal("1010")
    assert got[PFP] == Decimal("150")


# --- parser: unit detection ----------------------------------------------------


def test_unit_marker_million_scales_to_crore(tmp_path: Path) -> None:
    # A statement printed "in millions" is rescaled to crore (÷10) so it reconciles
    # with the crore XBRL side; EPS (per share) is never rescaled.
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, unit_line="Amounts in INR in millions")
    got = _by_concept(
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
    )
    assert got[REVENUE] == Decimal("100.0")  # 1,000 million -> 100 crore
    assert got[INCOME] == Decimal("101.0")
    assert got[EPS] == Decimal("5.00")  # per-share unchanged


def test_unit_marker_lakh_scales_to_crore(tmp_path: Path) -> None:
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, unit_line="(Rs. in lakhs)")
    got = _by_concept(
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
    )
    assert got[REVENUE] == Decimal("10.00")  # 1,000 lakh -> 10 crore
    assert got[EPS] == Decimal("5.00")


def test_glyph_mangled_rupee_crore_marker_is_detected(tmp_path: Path) -> None:
    # The ₹ glyph is frequently mangled in the text layer; only the unit word matters.
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, unit_line="z in crores except earnings per share")
    got = _by_concept(
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)
    )
    assert got[REVENUE] == Decimal("1000")


def test_missing_unit_marker_fails_closed(tmp_path: Path) -> None:
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, unit_line=None)
    with pytest.raises(NumberParseError, match="printed-unit marker"):
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)


# --- parser: consolidated selection & partial extraction -----------------------


def test_standalone_only_pdf_fails_closed_for_consolidated(tmp_path: Path) -> None:
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, scope_word="STANDALONE")
    with pytest.raises(ConsolidatedStatementNotFoundError):
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)


def test_split_revenue_skipped_but_other_facts_emitted_when_partial(tmp_path: Path) -> None:
    # Revenue printed only as a section header (no total line) is skipped under
    # require_all=False; the other four material facts are still emitted.
    pdf_path = tmp_path / "stmt.pdf"
    _write_statement(pdf_path, split_revenue=True)
    partial = extract_consolidated_pl(
        _load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT, require_all=False
    )
    got = _by_concept(partial)
    assert REVENUE not in got
    assert got[INCOME] == Decimal("1010")
    assert got[PBT] == Decimal("200")
    # The same PDF fails closed as a whole under the default require_all=True.
    with pytest.raises(NumberParseError):
        extract_consolidated_pl(_load(pdf_path), spec=_spec(), retrieved_at=_RETRIEVED_AT)


# --- fetch: announcement row selection -----------------------------------------


def _row(name: str, size: int, subcat: str, news_dt: str) -> dict[str, object]:
    return {
        "ATTACHMENTNAME": name,
        "Fld_Attachsize": size,
        "SUBCATNAME": subcat,
        "HEADLINE": "Outcome of Board Meeting",
        "NEWS_DT": news_dt,
    }


def test_select_results_row_picks_financial_results_by_size_then_date() -> None:
    rows = [
        _row("small.pdf", 100, "Financial Results", "2025-02-05T10:00:00"),
        _row("intimation.pdf", 900, "Board Meeting", "2025-02-01T10:00:00"),
        _row("full.pdf", 6_000_000, "Financial Results", "2025-02-04T17:00:00"),
        _row("later.pdf", 6_000_000, "Financial Results", "2025-02-06T17:00:00"),
    ]
    chosen = _select_results_row(rows, "500114")
    # Largest attachment among the Financial Results PDFs; earliest on a size tie.
    assert chosen.attachment_name == "full.pdf"
    assert chosen.subcategory == "Financial Results"


def test_select_results_row_ignores_non_pdf_and_other_subcategories() -> None:
    rows = [
        _row("notice.txt", 6_000_000, "Financial Results", "2025-02-04T10:00:00"),
        _row("results.pdf", 500, "Financial Results", "2025-02-04T10:00:00"),
    ]
    assert _select_results_row(rows, "500114").attachment_name == "results.pdf"


def test_select_results_row_fails_closed_when_no_financial_results_pdf() -> None:
    rows = [_row("intimation.pdf", 900, "Board Meeting", "2025-02-01T10:00:00")]
    with pytest.raises(BsePdfFetchError, match="Financial Results"):
        _select_results_row(rows, "500114")


def test_to_announcement_rejects_non_pdf_and_parses_size() -> None:
    assert _to_announcement(_row("x.txt", 5, "Financial Results", "2025-02-04T10:00:00")) is None
    parsed = _to_announcement(_row("x.pdf", "6763365", "Financial Results", "2025-02-04T17:31:44"))
    assert parsed is not None
    assert parsed.attachment_size == 6763365
    assert parsed.filed_at == datetime(2025, 2, 4, 17, 31, 44, tzinfo=UTC)


def test_parse_filed_at_tolerates_bad_values() -> None:
    assert _parse_filed_at("not-a-date") is None
    assert _parse_filed_at(None) is None
    assert _parse_filed_at("2025-02-04T17:31:44.287") == datetime(
        2025, 2, 4, 17, 31, 44, 287000, tzinfo=UTC
    )


# --- download: magic-byte + size verification, AttachLive fallback -------------


def _source(tmp_path: Path) -> BseResultsPdfSource:
    return BseResultsPdfSource(tmp_path, scrip_code="500114")


def _announcement(size: int) -> BseAnnouncement:
    return BseAnnouncement(
        attachment_name="a.pdf",
        attachment_size=size,
        subcategory="Financial Results",
        headline="h",
        filed_at=None,
    )


def test_verify_accepts_matching_pdf(tmp_path: Path) -> None:
    payload = b"%PDF-1.7 body"
    _source(tmp_path)._verify(payload, _announcement(len(payload)))  # no raise


def test_verify_rejects_non_pdf_magic(tmp_path: Path) -> None:
    with pytest.raises(BsePdfFetchError, match="not a PDF"):
        _source(tmp_path)._verify(b"<html>nope", _announcement(10))


def test_verify_rejects_size_mismatch(tmp_path: Path) -> None:
    payload = b"%PDF-1.7 body"
    with pytest.raises(BsePdfFetchError, match="size"):
        _source(tmp_path)._verify(payload, _announcement(len(payload) + 1))


def test_download_falls_back_to_attachlive_on_404(tmp_path: Path) -> None:
    import urllib.error

    calls: list[str] = []

    def fake_get(url: str) -> bytes:
        calls.append(url)
        if "AttachHis" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return b"%PDF-live"

    source = _source(tmp_path)
    source._http_get = fake_get  # type: ignore[method-assign]
    payload, url = source._download_attachment("a.pdf")
    assert payload == b"%PDF-live"
    assert "AttachLive" in url
    assert any("AttachHis" in call for call in calls)


# --- reconciliation: NSE XBRL + BSE results PDF -> AGREE ------------------------


def _pdf_stock(pdf_path: Path, pdf_sha: str) -> StockConfig:
    from fundamentals.api.config import SourceFileConfig

    return StockConfig(
        name="Synthetic PDF Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            tijori_slug="synthetic-pdf-corp",
        ),
        quarter=StockQuarter(
            label="Q3FY25",
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            knowledge_cutoff=_RETRIEVED_AT,
        ),
        results_pdf=SourceFileConfig(
            source_id="bse-results-pdf", filename="results.pdf", sha256=pdf_sha
        ),
        fixtures=FixturePaths(nse=_NSE_FIXTURE, results_pdf=str(pdf_path)),
    )


def test_nse_xbrl_and_bse_results_pdf_reconcile_to_agree(tmp_path: Path) -> None:
    # The NSE Ind AS XBRL (crore) and the BSE results PDF (parsed to crore) are two
    # independent first-party readings of the same consolidated quarter: every
    # shared material fact must reconcile to AGREE on two first-party sources.
    pdf_path = tmp_path / "results.pdf"
    pdf_sha = _write_statement(pdf_path)
    report = run_stock(
        _pdf_stock(pdf_path, pdf_sha),
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.PDF}),
        out_dir=tmp_path,
    )

    assert set(report.available_sources) == {"nse-indas-xbrl-consolidated", "bse-results-pdf"}
    assert {fact.concept_qname for fact in report.facts} == {REVENUE, INCOME, PBT, PFP, EPS}
    for fact in report.facts:
        assert fact.status is AgreementStatus.AGREE, fact.concept_qname
        assert fact.first_party_source_count == 2
        assert set(fact.agreed_sources) == {"nse-indas-xbrl-consolidated", "bse-results-pdf"}
    assert report.outcome is StockOutcome.DONE


def test_pdf_split_revenue_yields_single_first_party_for_revenue(tmp_path: Path) -> None:
    # When the PDF cannot supply revenue (split with no total), revenue is confirmed
    # by only NSE -> SINGLE_FIRST_PARTY (surfaced), while the other facts still AGREE.
    pdf_path = tmp_path / "results.pdf"
    pdf_sha = _write_statement(pdf_path, split_revenue=True)
    report = run_stock(
        _pdf_stock(pdf_path, pdf_sha),
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.PDF}),
        out_dir=tmp_path,
    )
    by_concept = {fact.concept_qname: fact for fact in report.facts}
    assert by_concept[REVENUE].status is AgreementStatus.SINGLE_FIRST_PARTY
    assert by_concept[INCOME].status is AgreementStatus.AGREE
    assert by_concept[PBT].status is AgreementStatus.AGREE


def test_standalone_only_pdf_is_skipped_not_blocked(tmp_path: Path) -> None:
    pdf_path = tmp_path / "results.pdf"
    pdf_sha = _write_statement(pdf_path, scope_word="STANDALONE")
    report = run_stock(
        _pdf_stock(pdf_path, pdf_sha),
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.PDF}),
        out_dir=tmp_path,
    )
    pdf_source = next(src for src in report.sources if src.kind is SourceKind.PDF)
    assert pdf_source.status is SourceStatus.SKIPPED
    assert "consolidated statement absent" in pdf_source.note
