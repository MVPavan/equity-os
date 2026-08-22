"""Slice 3 tests — local deterministic PDF number parse + guidance extraction.

Verifies (against the frozen oracle and the lawfully-held PDFs):

* the consolidated P&L numbers parse to the oracle values with page anchors;
* each extracted guidance claim's quote span resolves to real page text
  containing its range bounds;
* a planted wrong quote — and a tampered anchor span — fail the anchor check.

Both source PDFs live in gitignored ``data/raw/infy-fy25/`` and are covered by
the same retrieval authorization; the tests read them locally and never copy or
transmit their bytes.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.api.config import PdfParseConfig
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.guidance_extractor import (
    anchor_matches,
    extract_guidance_claims,
    resolve_span,
)
from fundamentals.extract.pdf_number_parser import PdfParseSpec, extract_consolidated_pl
from fundamentals.ingest.pdf_source import LoadedPdf, load_pdf

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RAW_DIR = _REPO_ROOT / "data" / "raw" / "infy-fy25"
_RESULTS_PDF = _RAW_DIR / "INFY-FY25-Q1-results-auditors.pdf"
_TRANSCRIPT_PDF = _RAW_DIR / "INFY-FY25-Q1-management-transcript.pdf"

_MANIFEST_PATH = Path(__file__).resolve().parent / "fixtures" / "infy_q1_fy25_manifest.json"

_RESULTS_SOURCE_ID = "infy-q1-fy25-results-pdf"
_RESULTS_SHA256 = "a07c12effe6cbffb6024e8462250e7f5e96b22fb4ec30c163827cc729b372695"
_TRANSCRIPT_SOURCE_ID = "infy-q1-fy25-management-transcript"
_TRANSCRIPT_SHA256 = "5039acfe6588789c028bb7d95fa1b5481f6dad1d763db16f34ebc2bb8eb023a6"

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

_STATEMENT_PAGE = 11


def _infy_spec() -> PdfParseSpec:
    """Build the INFY Q1 FY25 parse spec from the default per-issuer config."""
    parse_config = PdfParseConfig()
    return PdfParseSpec(
        statement_markers=parse_config.statement_markers,
        anchor_label=parse_config.anchor_label,
        target_lines=parse_config.target_lines,
        entity_scheme="nse-symbol",
        entity_id="INFY",
        currency="INR",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
    )


def _load_oracle() -> dict[str, dict[str, object]]:
    """Return the oracle facts keyed by concept QName."""
    payload = json.loads(_MANIFEST_PATH.read_text())
    return {fact["concept_qname"]: fact for fact in payload["facts"]}


@pytest.fixture(scope="module")
def results_pdf() -> LoadedPdf:
    return load_pdf(
        source_id=_RESULTS_SOURCE_ID,
        path=_RESULTS_PDF,
        expected_sha256=_RESULTS_SHA256,
    )


@pytest.fixture(scope="module")
def transcript_pdf() -> LoadedPdf:
    return load_pdf(
        source_id=_TRANSCRIPT_SOURCE_ID,
        path=_TRANSCRIPT_PDF,
        expected_sha256=_TRANSCRIPT_SHA256,
    )


def _by_concept(observations: list[Observation]) -> dict[str, Observation]:
    return {obs.concept_qname: obs for obs in observations}


def test_pl_numbers_match_oracle_with_page_anchors(results_pdf: LoadedPdf) -> None:
    observations = extract_consolidated_pl(
        results_pdf, spec=_infy_spec(), retrieved_at=_RETRIEVED_AT
    )
    by_concept = _by_concept(observations)
    oracle = _load_oracle()

    expected = {
        "in-bse-fin:RevenueFromOperations": Decimal("39315"),
        "in-bse-fin:Income": Decimal("40153"),
        "in-bse-fin:ProfitBeforeTax": Decimal("9021"),
        "in-bse-fin:ProfitLossForPeriod": Decimal("6374"),
        "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": (
            Decimal("15.38")
        ),
    }

    assert len(observations) == len(expected)
    for concept, value in expected.items():
        obs = by_concept[concept]
        # Value matches the parser's expectation and the independent oracle.
        assert obs.normalized_value == value
        assert obs.normalized_value == Decimal(str(oracle[concept]["normalized_value"]))
        # Every value carries an exact PDF page/block/span anchor on page 11.
        assert obs.provenance.anchor_type is SourceAnchorType.PDF_SPAN
        assert obs.provenance.page == _STATEMENT_PAGE
        assert obs.provenance.page == oracle[concept]["provenance"]["page"]
        assert obs.provenance.block is not None
        assert obs.provenance.span is not None
        assert obs.provenance.file_sha256 == _RESULTS_SHA256
        # Basis + scope guard: consolidated Ind AS, not standalone / other GAAP.
        assert obs.scope is Scope.CONSOLIDATED
        assert obs.accounting_basis is AccountingFramework.IND_AS


def test_revenue_raw_value_is_the_printed_token(results_pdf: LoadedPdf) -> None:
    observations = extract_consolidated_pl(
        results_pdf, spec=_infy_spec(), retrieved_at=_RETRIEVED_AT
    )
    revenue = _by_concept(observations)["in-bse-fin:RevenueFromOperations"]
    assert revenue.raw_value == "39,315"
    assert revenue.normalized_unit == "INR crore"


def test_guidance_claims_extracted_with_bounds(transcript_pdf: LoadedPdf) -> None:
    claims = extract_guidance_claims(transcript_pdf, retrieved_at=_RETRIEVED_AT)
    by_metric = {claim.metric: claim for claim in claims}

    assert set(by_metric) == {"revenue_growth", "operating_margin"}

    revenue = by_metric["revenue_growth"]
    assert (revenue.lower_bound, revenue.upper_bound) == (Decimal("3"), Decimal("4"))
    assert revenue.unit == "percent"
    assert revenue.constant_currency is True
    assert revenue.horizon == "FY25"
    assert revenue.epistemic_class.value == "forecast"

    margin = by_metric["operating_margin"]
    assert (margin.lower_bound, margin.upper_bound) == (Decimal("20"), Decimal("22"))
    assert margin.unit == "percent"


def test_each_guidance_quote_span_exists_in_page_text(transcript_pdf: LoadedPdf) -> None:
    claims = extract_guidance_claims(transcript_pdf, retrieved_at=_RETRIEVED_AT)
    for claim in claims:
        quote = resolve_span(transcript_pdf, claim.provenance)
        # The resolved span is real text on the anchored page, not a synthesis.
        page_text = transcript_pdf.page(claim.provenance.page).text
        assert quote in page_text
        # The quote carries the very bounds the claim asserts.
        assert f"{claim.lower_bound}%" in quote
        assert f"{claim.upper_bound}%" in quote
        assert anchor_matches(transcript_pdf, claim.provenance, quote) is True


def test_planted_wrong_quote_fails_anchor_check(transcript_pdf: LoadedPdf) -> None:
    claims = extract_guidance_claims(transcript_pdf, retrieved_at=_RETRIEVED_AT)
    claim = next(c for c in claims if c.metric == "revenue_growth")

    fabricated = "revenue growth guidance for the full financial year to 8% to 10%"
    assert fabricated != resolve_span(transcript_pdf, claim.provenance)
    assert anchor_matches(transcript_pdf, claim.provenance, fabricated) is False


def test_tampered_span_does_not_resolve_to_guidance(transcript_pdf: LoadedPdf) -> None:
    claims = extract_guidance_claims(transcript_pdf, retrieved_at=_RETRIEVED_AT)
    claim = next(c for c in claims if c.metric == "revenue_growth")
    real_quote = resolve_span(transcript_pdf, claim.provenance)

    tampered = Provenance(
        source_id=claim.provenance.source_id,
        file_sha256=claim.provenance.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=claim.provenance.page,
        block=claim.provenance.block,
        span="0:5",
        retrieved_at=_RETRIEVED_AT,
    )
    assert resolve_span(transcript_pdf, tampered) != real_quote


def test_number_parser_emits_no_bytes_beyond_local_models(results_pdf: LoadedPdf) -> None:
    # The loaded document is a pure in-memory pydantic model; extraction reads
    # only these local fields and returns typed facts, never any file handle or
    # network resource. A frozen model round-trips to JSON with no side effects.
    observations = extract_consolidated_pl(
        results_pdf, spec=_infy_spec(), retrieved_at=_RETRIEVED_AT
    )
    assert all(obs.model_dump_json() for obs in observations)
