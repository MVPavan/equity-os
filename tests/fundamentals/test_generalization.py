"""Generalization tests — the pipeline works on a non-Infosys Indian filer.

A hardening review found the increment aborted on any issuer but Infosys because
issuer specifics were hard-coded. These tests pin the fix on a fully synthetic
filer ("GenFiler") that differs from Infosys on every previously-hard-coded axis:

* **no non-controlling interest** — the PAT = attributable + NCI identity must be
  *skipped*, not fail closed;
* **an unaudited statement marker** (quarterly limited-review wording);
* **different label wording** ("Total income", "Profit / (loss) for the period",
  "Basic (in Rs. per share)") resolved by config-driven fuzzy label matching;
* **a different column order** — the current-quarter column is the *middle*
  column, so it is located by its printed header date, not a fixed x-coordinate;
* **no numeric guidance disclosed** — guidance extraction is non-fatal and the
  render shows the "no guidance" placeholder instead of aborting.

Everything is generated in-memory; no bytes leave the process. GenFiler reuses
the general Ind-AS config defaults, proving Infosys is now one config, not the
only supported issuer.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from fundamentals.api.config import (
    FundamentalsConfig,
    IssuerConfig,
    QuarterConfig,
    SourceFileConfig,
    XbrlConfig,
    XbrlMode,
)
from fundamentals.api.pipeline import XbrlInput, _claim_range_quote, run_pipeline
from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.store.fact_store import FactStore
from fundamentals.verify.quote_anchor import SourceBlock, SourceDocument, verify_quote_anchor

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

_NS = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
_EPS_CONCEPT = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

# A GenFiler filing: consolidated, attributable == PAT, and crucially NO
# non-controlling-interest tag. Values (INR crore) cross-foot: PBT = income −
# expenses (1,100 − 800 = 300).
_XBRL_FACTS: tuple[tuple[str, str, str, str], ...] = (
    ("RevenueFromOperations", "INR", "-7", "10000000000.00"),
    ("Income", "INR", "-7", "11000000000.00"),
    ("Expenses", "INR", "-7", "8000000000.00"),
    ("ProfitBeforeTax", "INR", "-7", "3000000000.00"),
    ("ProfitLossForPeriod", "INR", "-7", "2200000000.00"),
    ("ProfitOrLossAttributableToOwnersOfParent", "INR", "-7", "2200000000.00"),
    (_EPS_CONCEPT, "INRPerShare", "2", "5.50"),
)


def _genfiler_xbrl() -> bytes:
    """Build the synthetic GenFiler XBRL instance (no NCI tag present)."""
    fact_lines = [
        f'  <in-bse-fin:{name} contextRef="OneD" unitRef="{unit}" '
        f'decimals="{decimals}">{value}</in-bse-fin:{name}>'
        for name, unit, decimals, value in _XBRL_FACTS
    ]
    body = "\n".join(fact_lines)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        f'    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        f'    xmlns:in-bse-fin="{_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity>\n"
        '      <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">'
        "GENFILER</xbrli:identifier>\n"
        "    </xbrli:entity>\n"
        "    <xbrli:period>\n"
        "      <xbrli:startDate>2024-04-01</xbrli:startDate>\n"
        "      <xbrli:endDate>2024-06-30</xbrli:endDate>\n"
        "    </xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        '  <xbrli:unit id="INRPerShare"><xbrli:divide>'
        "<xbrli:unitNumerator><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator>"
        "<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure>"
        "</xbrli:unitDenominator></xbrli:divide></xbrli:unit>\n"
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        f"{body}\n"
        "</xbrli:xbrl>\n"
    ).encode()


def _write_results_pdf(path: Path) -> str:
    """Write a GenFiler results PDF (unaudited, current column in the middle)."""
    doc = pymupdf.open()
    page = doc.new_page()

    def put(x: float, y: float, text: str) -> None:
        page.insert_text((x, y), text, fontsize=9)

    put(
        60,
        90,
        "Statement of Consolidated Unaudited Results of GenFiler Limited "
        "for the quarter ended June 30, 2024",
    )
    put(60, 120, "Particulars")
    # Column order: prior-year | CURRENT QUARTER | prior-quarter.
    put(300, 140, "June 30, 2023")
    put(400, 140, "June 30, 2024")
    put(500, 140, "March 31, 2024")
    put(300, 160, "Unaudited")
    put(400, 160, "Unaudited")
    put(500, 160, "Unaudited")

    def row(y: float, label: str, prior_year: str, current: str, prior_q: str) -> None:
        put(60, y, label)
        put(310, y, prior_year)
        put(410, y, current)
        put(510, y, prior_q)

    row(190, "Revenue from operations", "900", "1,000", "950")
    row(210, "Other income", "50", "100", "60")
    row(230, "Total income", "950", "1,100", "1,010")
    row(250, "Total expenses", "700", "800", "760")
    row(270, "Profit / (loss) before tax", "250", "300", "250")
    row(290, "Profit / (loss) for the period", "180", "220", "185")
    row(310, "Basic (in Rs. per share)", "4.50", "5.50", "4.60")

    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_transcript_pdf(path: Path) -> str:
    """Write a transcript PDF that discloses NO numeric guidance ranges."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (60, 90),
        "Management remains focused on execution and cost discipline. "
        "No specific numeric guidance was provided for the year.",
        fontsize=9,
    )
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _genfiler_config() -> FundamentalsConfig:
    """A GenFiler config that reuses the general Ind-AS defaults (pdf/concepts)."""
    return FundamentalsConfig(
        issuer=IssuerConfig(
            name="GenFiler Limited", nse_symbol="GENFILER", entity_scheme="nse-symbol"
        ),
        quarter=QuarterConfig(
            issuer_quarter="FY25_Q1",
            program_quarter="QUARTER_1",
            label="Q1 FY25 (quarter ended 2024-06-30)",
            period_start=date(2024, 4, 1),
            period_end=date(2024, 6, 30),
            knowledge_cutoff=datetime(2024, 7, 18, tzinfo=UTC),
        ),
        raw_dir="data/raw/genfiler",
        store_db=":memory:",
        results_pdf=SourceFileConfig(
            source_id="genfiler-results", filename="results.pdf", sha256="0" * 64
        ),
        transcript_pdf=SourceFileConfig(
            source_id="genfiler-transcript", filename="transcript.pdf", sha256="0" * 64
        ),
        xbrl=XbrlConfig(
            source_id="genfiler-xbrl",
            mode=XbrlMode.LOCAL,
            local_path="unused.xml",
            symbol="GENFILER",
        ),
    )


@pytest.fixture()
def genfiler_run(tmp_path: Path) -> tuple[FundamentalsConfig, str, str, str, str]:
    results_path = tmp_path / "genfiler-results.pdf"
    transcript_path = tmp_path / "genfiler-transcript.pdf"
    results_sha = _write_results_pdf(results_path)
    transcript_sha = _write_transcript_pdf(transcript_path)
    return (
        _genfiler_config(),
        str(results_path),
        results_sha,
        str(transcript_path),
        transcript_sha,
    )


def _run(
    genfiler_run: tuple[FundamentalsConfig, str, str, str, str],
) -> tuple[FundamentalsConfig, object]:
    config, results_path, results_sha, transcript_path, transcript_sha = genfiler_run
    xbrl_bytes = _genfiler_xbrl()
    xbrl_input = XbrlInput(
        xml_bytes=xbrl_bytes,
        file_sha256=hashlib.sha256(xbrl_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=_RETRIEVED_AT,
    )
    store = FactStore(":memory:")
    try:
        result = run_pipeline(
            config=config,
            xbrl_input=xbrl_input,
            results_pdf_path=results_path,
            results_pdf_sha256=results_sha,
            transcript_pdf_path=transcript_path,
            transcript_pdf_sha256=transcript_sha,
            store=store,
        )
    finally:
        store.close()
    return config, result


def test_non_infosys_filer_runs_end_to_end_without_aborting(
    genfiler_run: tuple[FundamentalsConfig, str, str, str, str],
) -> None:
    _config, result = _run(genfiler_run)
    markdown = result.markdown  # type: ignore[attr-defined]

    # The current-quarter (middle) column figures are rendered, not the leftmost.
    assert "1,000" in markdown
    assert "1,100" in markdown
    assert "220" in markdown
    assert "5.50" in markdown
    # Prior-year (leftmost) and prior-quarter figures are NOT selected.
    assert "900" not in markdown
    assert "950" not in markdown


def test_nci_absent_skips_the_dependent_identity_instead_of_failing(
    genfiler_run: tuple[FundamentalsConfig, str, str, str, str],
) -> None:
    _config, result = _run(genfiler_run)
    foot_results = result.cross_foot_results  # type: ignore[attr-defined]
    names = {foot.identity for foot in foot_results}

    # Only the PBT identity ran; the PAT = attributable + NCI identity was skipped
    # (no minority interest) rather than aborting the pipeline.
    assert len(foot_results) == 1
    assert all(foot.passed for foot in foot_results)
    assert any("before tax" in name for name in names)
    assert not any("Non-controlling" in name for name in names)


def test_cross_check_still_matches_every_headline_figure(
    genfiler_run: tuple[FundamentalsConfig, str, str, str, str],
) -> None:
    _config, result = _run(genfiler_run)
    checks = result.cross_check_results  # type: ignore[attr-defined]
    assert len(checks) == 5
    assert all(check.matched for check in checks)


def test_missing_numeric_guidance_renders_placeholder_not_abort(
    genfiler_run: tuple[FundamentalsConfig, str, str, str, str],
) -> None:
    _config, result = _run(genfiler_run)
    markdown = result.markdown  # type: ignore[attr-defined]
    assert "No management-guidance ranges were extracted" in markdown


def _guidance_claim(span: str) -> GuidanceClaim:
    return GuidanceClaim(
        metric="revenue_growth",
        lower_bound=Decimal("3"),
        upper_bound=Decimal("4"),
        unit="percent",
        constant_currency=True,
        horizon="FY25",
        scope=Scope.CONSOLIDATED,
        provenance=Provenance(
            source_id="t",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=1,
            block=0,
            span=span,
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def test_quote_anchor_gate_can_actually_fail() -> None:
    # Regression for the quote-anchor no-op: the gate verifies the claim's OWN
    # asserted range against the recorded span, so a span that does not contain it
    # fails — the check is no longer a tautological re-read of the same span.
    text = "For the year the company guides revenue growth guidance of 3% to 4%."
    document = SourceDocument(blocks=(SourceBlock(page=1, block=0, text=text),))
    quote = _claim_range_quote(_guidance_claim("0:0"))
    assert quote == "3% to 4%"

    good_start = text.index("3% to 4%")
    good_span = f"{good_start}:{good_start + len('3% to 4%')}"
    assert verify_quote_anchor(_guidance_claim(good_span), quote, document).anchored is True

    # A span pointing at the start of the block does not contain "3% to 4%".
    assert verify_quote_anchor(_guidance_claim("0:10"), quote, document).anchored is False
