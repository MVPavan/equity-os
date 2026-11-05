"""Slice phase05-sC — the §5 management-ledger renderer and the addendum-A2 guidance rules
(a per-rule ``unit`` and one- or two-group patterns). PREP-2b Task 7 removed the JSON ledger's
persistence; cross-quarter guidance status is the run draft's (``test_prep2b_run_draft``).

All ledger data is synthetic: symbol ``SYNTH``, quarters ``FY27_Q1``/``FY27_Q3``, invented
metrics and quotes, 2027 dates.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from equity_os.contracts.measurement.fact import ReconciliationStatus
from equity_os.contracts.measurement.guidance_claim import GuidanceClaim
from equity_os.contracts.measurement.observation import Scope
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.measurement.role import FactRole
from equity_os.extraction.results_pdf.pdf_source import LoadedPdf, PdfBlock, PdfPage
from equity_os.interface.entry.config import GuidanceRuleConfig
from equity_os.publication.drafting.earnings_update import (
    EarningsUpdate,
    RenderedFact,
    VerificationOutcome,
    render_earnings_update,
)

_SYMBOL = "SYNTH"
_ISSUER_NAME = "Synthetic Test Corp"
_Q1 = "FY27_Q1"
_Q3 = "FY27_Q3"
_HORIZON = "FY27"
_MARGIN = "synth_margin"
_GROWTH = "synth_growth"
_PERCENT = "%"
_RETRIEVED_AT = datetime(2027, 7, 25, tzinfo=UTC)

_CRORE = "INR crore"
_PER_SHARE = "INR per share"
_ROLE_QNAMES: dict[FactRole, str] = {
    FactRole.REVENUE: "in-bse-fin:RevenueFromOperations",
    FactRole.TOTAL_INCOME: "in-bse-fin:Income",
    FactRole.TOTAL_EXPENSES: "in-bse-fin:Expenses",
    FactRole.PROFIT_BEFORE_TAX: "in-bse-fin:ProfitBeforeTax",
    FactRole.PROFIT_FOR_PERIOD: "in-bse-fin:ProfitLossForPeriod",
    FactRole.BASIC_EPS: "in-bse-fin:BasicEarningsLossPerShare",
}
_FACT_VALUES: dict[FactRole, Decimal] = {
    FactRole.REVENUE: Decimal("1000"),
    FactRole.TOTAL_INCOME: Decimal("1020"),
    FactRole.TOTAL_EXPENSES: Decimal("820"),
    FactRole.PROFIT_BEFORE_TAX: Decimal("200"),
    FactRole.PROFIT_FOR_PERIOD: Decimal("150"),
    FactRole.BASIC_EPS: Decimal("12.50"),
}

_Q1_MARGIN_QUOTE = "we expect a synthetic margin of 10% to 12% for FY27"
_Q1_GROWTH_QUOTE = "synthetic growth guidance of 5% to 7% for FY27"


# --- synthetic builders over contracts that already exist (safe at module scope) ---


def _provenance(quarter: str, *, page: int = 4, block: int = 2) -> Provenance:
    """One synthetic transcript span anchor, distinct per quarter."""
    return Provenance(
        source_id=f"synth-transcript-{quarter.lower()}",
        file_sha256=hashlib.sha256(quarter.encode()).hexdigest(),
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page,
        block=block,
        span="0:48",
        retrieved_at=_RETRIEVED_AT,
    )


def _fact(role: FactRole) -> RenderedFact:
    """One rendered P&L fact so the §5 render is reachable through a valid update."""
    return RenderedFact(
        role=role,
        concept_qname=_ROLE_QNAMES[role],
        value=_FACT_VALUES[role],
        unit=_PER_SHARE if role is FactRole.BASIC_EPS else _CRORE,
        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
        sources=(_provenance(_Q3, page=1, block=int(role is FactRole.BASIC_EPS)),),
    )


def _guidance_pdf(sentence: str) -> LoadedPdf:
    """A one-block synthetic transcript page carrying ``sentence``."""
    block = PdfBlock(number=3, text=sentence)
    page = PdfPage(page_number=2, text=sentence, words=(), blocks=(block,))
    return LoadedPdf(
        source_id="synth-transcript-fy27_q1",
        file_sha256="ab" * 32,
        page_count=1,
        pages=(page,),
    )


def _section_five(markdown: str) -> list[str]:
    """Return the body lines of the rendered §5 management_ledger section."""
    lines = markdown.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "## 5. management_ledger")
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _line_with(lines: list[str], token: str) -> str:
    """The single §5 bullet carrying ``token`` — one entry per status by construction."""
    matches = [line for line in lines if token in line]
    assert len(matches) == 1, f"expected exactly one §5 line containing {token!r}: {matches}"
    return matches[0]


# --- helpers touching names that do not exist yet (never imported at module scope) ---


def _rule_from_config(rule_config: GuidanceRuleConfig) -> Any:
    """Build the extractor rule from config the way the pipeline must, unit included."""
    from equity_os.extraction.guidance.guidance_extractor import GuidanceRule

    return GuidanceRule(
        metric=rule_config.metric,
        pattern=rule_config.pattern,
        horizon=rule_config.horizon,
        unit=rule_config.unit,
    )


def _extract_one(rule_config: GuidanceRuleConfig, sentence: str) -> GuidanceClaim:
    """Extract the single claim ``rule_config`` yields from ``sentence``."""
    from equity_os.extraction.guidance.guidance_extractor import extract_guidance_claims

    claims = extract_guidance_claims(
        _guidance_pdf(sentence),
        rules=(_rule_from_config(rule_config),),
        retrieved_at=_RETRIEVED_AT,
    )
    assert len(claims) == 1, f"rule {rule_config.metric!r} did not match once: {claims}"
    return claims[0]


def _ledger_for_render() -> Any:
    """A four-entry ledger, one per status, as of FY27_Q3."""
    from equity_os.publication.drafting.management_ledger import (
        LedgerAnchor,
        LedgerEntry,
        LedgerRevision,
        LedgerStatus,
        ManagementLedger,
    )

    def anchor(quarter: str, quote: str) -> Any:
        return LedgerAnchor(issuer_quarter=quarter, quote=quote, source=_provenance(quarter))

    def entry(
        metric: str,
        lower: str,
        upper: str,
        status: Any,
        first: Any,
        latest: Any,
        history: tuple[Any, ...] = (),
    ) -> Any:
        return LedgerEntry(
            claim_key=f"{metric}|{_HORIZON}|{Scope.CONSOLIDATED}",
            metric=metric,
            lower_bound=Decimal(lower),
            upper_bound=Decimal(upper),
            unit=_PERCENT,
            constant_currency=False,
            horizon=_HORIZON,
            scope=Scope.CONSOLIDATED,
            first=first,
            latest=latest,
            status=status,
            history=history,
        )

    q1_margin = anchor(_Q1, _Q1_MARGIN_QUOTE)
    q3_margin = anchor(_Q3, "we now see a synthetic margin of 13% to 15% for FY27")
    q1_growth = anchor(_Q1, _Q1_GROWTH_QUOTE)
    q3_growth = anchor(_Q3, "synthetic growth guidance stays at 5% to 7% for FY27")
    q1_capex = anchor(_Q1, "synthetic capex intensity of 3% to 4% of revenue")
    q3_new = anchor(_Q3, "a new synthetic utilisation target of 8% to 9%")
    return ManagementLedger(
        symbol=_SYMBOL,
        version=3,
        updated_quarter=_Q3,
        entries=(
            entry("synth_utilisation", "8", "9", LedgerStatus.NEW, q3_new, q3_new),
            entry(_GROWTH, "5", "7", LedgerStatus.REAFFIRMED, q1_growth, q3_growth),
            entry(
                _MARGIN,
                "13",
                "15",
                LedgerStatus.MODIFIED,
                q1_margin,
                q3_margin,
                (
                    LedgerRevision(
                        issuer_quarter=_Q1,
                        lower_bound=Decimal("10"),
                        upper_bound=Decimal("12"),
                        status=LedgerStatus.NEW,
                    ),
                ),
            ),
            entry("synth_capex", "3", "4", LedgerStatus.CARRIED, q1_capex, q1_capex),
        ),
    )


def _update_with_ledger(ledger: Any) -> EarningsUpdate:
    """A synthetic earnings update whose §5 must render from ``ledger``."""
    return EarningsUpdate(
        issuer_name=_ISSUER_NAME,
        nse_symbol=_SYMBOL,
        issuer_quarter_label="Q3 FY27",
        period_start="2026-10-01",
        period_end="2026-12-31",
        knowledge_cutoff="2027-01-20",
        facts=tuple(_fact(role) for role in _ROLE_QNAMES),
        guidance=(),
        calculations=(),
        cross_check=VerificationOutcome(passed_count=6, total_count=6),
        cross_foot=VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="not applicable for this synthetic issuer",
        ledger=ledger,
    )


def test_renderer_section_five_shows_status_and_both_anchors() -> None:
    # §5 is the reader-facing contract: every carried commitment shows its status and
    # both ends of its evidence, so no status claim is made without an anchor.
    markdown = render_earnings_update(_update_with_ledger(_ledger_for_render()))
    section = _section_five(markdown)

    new_line = _line_with(section, "NEW")
    assert "8–9%" in new_line
    assert f"first quoted {_Q3}" in new_line

    reaffirmed = _line_with(section, "REAFFIRMED")
    assert f"first quoted {_Q1}" in reaffirmed
    assert f"restated {_Q3}" in reaffirmed
    markers = re.findall(r"\[\^\d+\]", reaffirmed)
    assert len(markers) == 2, f"both anchors must be footnoted: {reaffirmed}"
    assert markers[0] != markers[1], "first and latest anchors are distinct sources"

    modified = _line_with(section, "MODIFIED")
    assert "13–15%" in modified
    assert "(was 10–12)" in modified

    carried = _line_with(section, "CARRIED")
    assert f"not restated in {_Q3}" in carried


def test_point_guidance_rule_yields_equal_bounds_with_unit() -> None:
    # Real filers commit to a point ("about 30,000 per MT"), not always a range: one
    # capture group must yield lower == upper, thousands separators stripped, unit kept.
    rule_config = GuidanceRuleConfig(
        metric="synth_realisation",
        label="Synthetic realisation guidance",
        pattern=r"realisation guidance of about ([\d,]+) per MT",
        horizon=_HORIZON,
        unit="INR per MT",
    )
    sentence = "Management sees a realisation guidance of about 30,000 per MT through FY27."

    claim = _extract_one(rule_config, sentence)

    assert claim.lower_bound == Decimal("30000")
    assert claim.upper_bound == Decimal("30000")
    assert claim.unit == "INR per MT"


def test_two_group_rule_keeps_percent_default() -> None:
    # Adding the unit must not change the existing two-group behaviour: a rule that
    # omits ``unit`` still reports both bounds as a percentage range.
    rule_config = GuidanceRuleConfig(
        metric=_MARGIN,
        label="Synthetic margin guidance",
        pattern=r"synthetic margin guidance.*?(\d+)% to (\d+)%",
        horizon=_HORIZON,
    )
    sentence = "Our synthetic margin guidance stays at 10% to 12% for the year."

    claim = _extract_one(rule_config, sentence)

    assert claim.lower_bound == Decimal("10")
    assert claim.upper_bound == Decimal("12")
    assert claim.unit == _PERCENT
