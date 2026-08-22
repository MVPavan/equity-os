"""Robustness-hardening tests for the Sol pipeline review (findings H4–H6, M7–M11).

Each test proves a gate now *bites*: a case that previously slipped through (a
silent drop, an un-sourced number, a trusted caller string, an inflated
tolerance, a mis-anchored quote, a wrong-issuer filing, a retried hard block, or
canonical facts left behind by a failed run) is now rejected fail-closed.

Everything is generated in-memory; no source bytes leave the process.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from fundamentals.api.config import (
    FundamentalsConfig,
    IssuerConfig,
    QuarterConfig,
    SourceFileConfig,
    XbrlConfig,
    XbrlMode,
)
from fundamentals.api.pipeline import (
    PipelineError,
    XbrlInput,
    _guidance_quote_holds,
    run_pipeline,
)
from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.xbrl_parser import (
    TaxonomySpec,
    XbrlParseError,
    parse_instance,
    parse_observations,
    select_observation,
)
from fundamentals.ingest.xbrl_source import (
    NseXbrlSource,
    XbrlFetchError,
    XbrlHardBlockError,
)
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedFact,
    RenderError,
    VerificationOutcome,
    render_earnings_update,
)
from fundamentals.store.fact_store import FactStore
from fundamentals.verify.comparison_key import explain_comparability
from fundamentals.verify.crossfoot import Identity, SignedTerm, check_identity

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)
_NS = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
_Q_START = date(2024, 4, 1)
_Q_END = date(2024, 6, 30)


# --------------------------------------------------------------------------- #
# Shared builders                                                             #
# --------------------------------------------------------------------------- #


def _xbrl_provenance() -> Provenance:
    return Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_RETRIEVED_AT,
    )


def _pdf_provenance() -> Provenance:
    return Provenance(
        source_id="results-pdf",
        file_sha256="a" * 64,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=11,
        block=4,
        span="0:5",
        retrieved_at=_RETRIEVED_AT,
    )


def _observation(
    concept: str,
    value: Decimal,
    *,
    scale: int = 10_000_000,
    decimals: int = -7,
    unit: str = "INR crore",
    taxonomy_namespace: str | None = _NS,
    registry_version: str | None = "in-bse-fin/2020-03-31",
    provenance: Provenance | None = None,
) -> Observation:
    return Observation(
        concept_qname=concept,
        taxonomy_namespace=taxonomy_namespace,
        registry_version=registry_version,
        raw_value=str(int(value) * scale),
        normalized_value=value,
        normalized_unit=unit,
        context_ref="OneD",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=_Q_START,
        period_end=_Q_END,
        currency="INR",
        scale=scale,
        decimals=decimals,
        provenance=provenance or _xbrl_provenance(),
    )


def _rendered_fact(role: FactRole, concept: str, value: Decimal, unit: str) -> RenderedFact:
    from fundamentals.contracts.fact import ReconciliationStatus

    return RenderedFact(
        role=role,
        concept_qname=concept,
        value=value,
        unit=unit,
        reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
        sources=(_pdf_provenance(),),
    )


def _all_roles(
    value_overrides: dict[FactRole, tuple[Decimal, str]] | None = None,
) -> list[RenderedFact]:
    defaults: dict[FactRole, tuple[Decimal, str]] = {
        FactRole.REVENUE: (Decimal("39315"), "INR crore"),
        FactRole.TOTAL_INCOME: (Decimal("40153"), "INR crore"),
        FactRole.TOTAL_EXPENSES: (Decimal("31132"), "INR crore"),
        FactRole.PROFIT_BEFORE_TAX: (Decimal("9021"), "INR crore"),
        FactRole.PROFIT_FOR_PERIOD: (Decimal("6374"), "INR crore"),
        FactRole.BASIC_EPS: (Decimal("15.38"), "INR per share"),
    }
    if value_overrides:
        defaults.update(value_overrides)
    concept_by_role = {
        FactRole.REVENUE: "in-bse-fin:RevenueFromOperations",
        FactRole.TOTAL_INCOME: "in-bse-fin:Income",
        FactRole.TOTAL_EXPENSES: "in-bse-fin:Expenses",
        FactRole.PROFIT_BEFORE_TAX: "in-bse-fin:ProfitBeforeTax",
        FactRole.PROFIT_FOR_PERIOD: "in-bse-fin:ProfitLossForPeriod",
        FactRole.BASIC_EPS: "in-bse-fin:BasicEPS",
    }
    return [
        _rendered_fact(role, concept_by_role[role], *defaults[role])
        for role, concept in concept_by_role.items()
    ]


def _earnings_update(
    facts: list[RenderedFact],
    *,
    cross_check: VerificationOutcome | None = None,
    cross_foot: VerificationOutcome | None = None,
) -> EarningsUpdate:
    return EarningsUpdate(
        issuer_name="Infosys Limited",
        nse_symbol="INFY",
        issuer_quarter_label="Q1 FY25",
        period_start="2024-04-01",
        period_end="2024-06-30",
        knowledge_cutoff="2024-07-18",
        facts=tuple(facts),
        guidance=(),
        calculations=(),
        cross_check=cross_check or VerificationOutcome(passed_count=5, total_count=5),
        cross_foot=cross_foot or VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="n/a",
    )


# --------------------------------------------------------------------------- #
# H5 — the render is truly fail-closed                                        #
# --------------------------------------------------------------------------- #


def test_h5a_render_rejects_a_fact_with_empty_sources() -> None:
    facts = _all_roles()
    # Strip the sources off one required fact — an un-sourced number.
    facts[0] = facts[0].model_copy(update={"sources": ()})
    with pytest.raises(RenderError):
        render_earnings_update(_earnings_update(facts))


def test_h5b_renderer_does_not_trust_a_caller_supplied_pass() -> None:
    # The cross-check actually FAILED (0 of 5 matched); the renderer must derive
    # the state from the counts, never print a caller-forced PASS.
    update = _earnings_update(
        _all_roles(),
        cross_check=VerificationOutcome(passed_count=0, total_count=5),
    )
    markdown = render_earnings_update(update)
    cross_check_line = next(
        line for line in markdown.splitlines() if "XBRL ↔ PDF cross-check" in line
    )
    assert "FAIL" in cross_check_line
    assert "PASS" not in cross_check_line


def test_h5c_crore_precision_is_preserved_not_truncated() -> None:
    facts = _all_roles({FactRole.REVENUE: (Decimal("123.75"), "INR crore")})
    markdown = render_earnings_update(_earnings_update(facts))
    assert "123.75" in markdown
    # The old int() truncation would have emitted a bare 123 in the value cell.
    revenue_line = next(line for line in markdown.splitlines() if "Revenue from operations" in line)
    assert "| 123 |" not in revenue_line


# --------------------------------------------------------------------------- #
# H4b — dimensions parsed from scenario, not just segment                     #
# --------------------------------------------------------------------------- #

_REVENUE = "in-bse-fin:RevenueFromOperations"


def _scenario_instance() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        '    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"\n'
        '    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        f'    xmlns:in-bse-fin="{_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        'scheme="http://www.nseindia.com/NSESymbol">INFY</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:context id="Seg">\n'
        "    <xbrli:entity><xbrli:identifier "
        'scheme="http://www.nseindia.com/NSESymbol">INFY</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "    <xbrli:scenario>\n"
        '      <xbrldi:explicitMember dimension="in-bse-fin:ReportableSegmentsAxis">'
        "in-bse-fin:FinancialServicesSegmentMember</xbrldi:explicitMember>\n"
        "    </xbrli:scenario>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        '  <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" '
        'decimals="-7">393150000000.00</in-bse-fin:RevenueFromOperations>\n'
        '  <in-bse-fin:RevenueFromOperations contextRef="Seg" unitRef="INR" '
        'decimals="-7">13160000000.00</in-bse-fin:RevenueFromOperations>\n'
        "</xbrli:xbrl>\n"
    ).encode()


def test_h4b_scenario_dimension_fact_is_not_treated_as_the_total() -> None:
    observations = parse_observations(
        _scenario_instance(),
        source_id="x",
        file_sha256="0" * 64,
        retrieved_at=_RETRIEVED_AT,
    )
    revenue = [obs for obs in observations if obs.concept_qname == _REVENUE]
    assert len(revenue) == 2
    # The scenario-dimensioned occurrence carries a dimension (is NOT dimension-free).
    assert any(obs.dimensions for obs in revenue)

    # A segment-free selection returns the OneD total, never the segment 1,316.
    total = select_observation(
        observations,
        concept_qname=_REVENUE,
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=_Q_START,
        period_end=_Q_END,
    )
    assert total.normalized_value == Decimal("39315")
    assert total.dimensions == ()


# --------------------------------------------------------------------------- #
# H4a / M11 — taxonomy dispatch + no silent data loss                         #
# --------------------------------------------------------------------------- #


def _unknown_taxonomy_instance() -> bytes:
    ns = "http://example.com/xbrl/in-capmkt/2099"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        '    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        f'    xmlns:in-capmkt="{ns}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        'scheme="http://www.nseindia.com/NSESymbol">INFY</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        '  <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>\n"
        '  <in-capmkt:Income contextRef="OneD" unitRef="INR" '
        'decimals="-7">401530000000.00</in-capmkt:Income>\n'
        "</xbrli:xbrl>\n"
    ).encode(), ns


def test_h4a_unknown_taxonomy_fails_closed_not_empty() -> None:
    xml_bytes, _ = _unknown_taxonomy_instance()
    with pytest.raises(XbrlParseError, match="no supported taxonomy"):
        parse_observations(
            xml_bytes, source_id="x", file_sha256="0" * 64, retrieved_at=_RETRIEVED_AT
        )


def test_h4a_registered_taxonomy_is_dispatched_and_resolves() -> None:
    xml_bytes, ns = _unknown_taxonomy_instance()
    registry = (TaxonomySpec(namespace=ns, prefix="in-capmkt", registry_version="in-capmkt/2099"),)
    observations = parse_observations(
        xml_bytes,
        source_id="x",
        file_sha256="0" * 64,
        retrieved_at=_RETRIEVED_AT,
        taxonomies=registry,
    )
    incomes = [obs for obs in observations if obs.concept_qname == "in-capmkt:Income"]
    assert len(incomes) == 1
    assert incomes[0].registry_version == "in-capmkt/2099"


def _instance_with_income_value(value_text: str, *, include_income: bool = True) -> bytes:
    income_line = (
        f'  <in-bse-fin:Income contextRef="OneD" unitRef="INR" decimals="-7">'
        f"{value_text}</in-bse-fin:Income>\n"
        if include_income
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        '    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        f'    xmlns:in-bse-fin="{_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        'scheme="http://www.nseindia.com/NSESymbol">INFY</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        f"{income_line}"
        '  <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" '
        'decimals="-7">393150000000.00</in-bse-fin:RevenueFromOperations>\n'
        "</xbrli:xbrl>\n"
    ).encode()


def test_m11_malformed_required_line_aborts() -> None:
    xml_bytes = _instance_with_income_value("not-a-number")
    with pytest.raises(XbrlParseError, match="malformed occurrence"):
        parse_observations(
            xml_bytes,
            source_id="x",
            file_sha256="0" * 64,
            retrieved_at=_RETRIEVED_AT,
            required_concepts=frozenset({"in-bse-fin:Income"}),
        )


def test_m11_absent_required_concept_fails_completeness() -> None:
    xml_bytes = _instance_with_income_value("", include_income=False)
    with pytest.raises(XbrlParseError, match="required concepts absent"):
        parse_observations(
            xml_bytes,
            source_id="x",
            file_sha256="0" * 64,
            retrieved_at=_RETRIEVED_AT,
            required_concepts=frozenset({"in-bse-fin:Income"}),
        )


def test_m11_non_required_malformed_line_becomes_a_rejection_not_a_drop() -> None:
    xml_bytes = _instance_with_income_value("not-a-number")
    result = parse_instance(
        xml_bytes,
        source_id="x",
        file_sha256="0" * 64,
        retrieved_at=_RETRIEVED_AT,
    )
    assert any(rej.concept_qname == "in-bse-fin:Income" for rej in result.rejections)


# --------------------------------------------------------------------------- #
# M7 — taxonomy identity in the comparison key                                #
# --------------------------------------------------------------------------- #


def test_m7_same_qname_different_registry_version_is_not_comparable() -> None:
    left = _observation("in-bse-fin:Income", Decimal("40153"))
    right = _observation(
        "in-bse-fin:Income",
        Decimal("40153"),
        registry_version="in-bse-fin/2022-09-30",
    )
    result = explain_comparability(left, right)
    assert result.comparable is False
    assert any("taxonomy" in reason for reason in result.reasons)


def test_m7_xbrl_vs_taxonomy_less_pdf_remains_comparable() -> None:
    xbrl = _observation("in-bse-fin:Income", Decimal("40153"))
    pdf = _observation(
        "in-bse-fin:Income",
        Decimal("40153"),
        taxonomy_namespace=None,
        registry_version=None,
        provenance=_pdf_provenance(),
    )
    # A PDF read has no taxonomy identity and cannot contradict one.
    assert explain_comparability(xbrl, pdf).comparable is True


# --------------------------------------------------------------------------- #
# M8 — precision bounds + tolerance cap                                       #
# --------------------------------------------------------------------------- #


def test_m8_absurd_decimals_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _observation("in-bse-fin:Income", Decimal("40153"), decimals=-99)


def test_m8_non_positive_scale_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _observation("in-bse-fin:Income", Decimal("40153"), scale=0)


def test_m8_overly_coarse_fact_is_flagged_and_not_auto_passed() -> None:
    # decimals=-12 with crore scale manufactures a ~50,000-crore half-ULP; a
    # 1,000-crore residual would "pass" on that inflated tolerance. The cap flags
    # it for review and refuses the auto-pass.
    lhs = _observation("in-bse-fin:ProfitBeforeTax", Decimal("1000"), decimals=-12)
    term = _observation("in-bse-fin:Income", Decimal("0"), decimals=-12)
    identity = Identity(
        name="coarse",
        lhs_concept="in-bse-fin:ProfitBeforeTax",
        terms=(SignedTerm(sign=1, concept_qname="in-bse-fin:Income"),),
    )
    result = check_identity(
        identity, {"in-bse-fin:ProfitBeforeTax": lhs, "in-bse-fin:Income": term}
    )
    assert result.flagged_for_review is True
    assert result.derived_tolerance > result.tolerance
    assert result.passed is False


# --------------------------------------------------------------------------- #
# M9 — stronger quote-anchor                                                  #
# --------------------------------------------------------------------------- #

_SOURCE_QUOTE = "revenue growth guidance for the year of 3% to 4%"


def _guidance_claim(lower: str, upper: str, source_quote: str | None) -> GuidanceClaim:
    return GuidanceClaim(
        metric="revenue_growth",
        lower_bound=Decimal(lower),
        upper_bound=Decimal(upper),
        unit="percent",
        constant_currency=True,
        horizon="FY25",
        scope=Scope.CONSOLIDATED,
        source_quote=source_quote,
        provenance=Provenance(
            source_id="t",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=1,
            block=0,
            span="0:10",
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def test_m9_original_claim_quote_holds() -> None:
    claim = _guidance_claim("3", "4", _SOURCE_QUOTE)
    assert _guidance_quote_holds(claim, _SOURCE_QUOTE) is True


def test_m9_mutated_bounds_with_old_provenance_fails() -> None:
    # 3–4% changed to 8–10% while keeping the extraction-time quote.
    claim = _guidance_claim("8", "10", _SOURCE_QUOTE)
    assert _guidance_quote_holds(claim, _SOURCE_QUOTE) is False


def test_m9_repointed_span_fails() -> None:
    # Provenance re-pointed to a span whose text differs from the stored quote.
    claim = _guidance_claim("3", "4", _SOURCE_QUOTE)
    assert _guidance_quote_holds(claim, "some other sentence with 3% to 4%") is False


# --------------------------------------------------------------------------- #
# M10 — ingestion proves issuer + classifies retries                          #
# --------------------------------------------------------------------------- #


def _issuer_instance(symbol: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        f'    xmlns:in-bse-fin="{_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        f'scheme="http://www.nseindia.com/NSESymbol">{symbol}</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        "</xbrli:xbrl>\n"
    ).encode()


def test_m10_wrong_issuer_download_is_rejected(tmp_path: Path) -> None:
    source = NseXbrlSource(tmp_path, symbol="INFY", retry_backoff_seconds=0.0)
    # Another company's filing for the SAME dates and scope must not pass.
    with pytest.raises(XbrlFetchError, match="does not match requested issuer"):
        source._verify(_issuer_instance("TCS"), from_date=_Q_START, to_date=_Q_END)


def test_m10_matching_issuer_download_passes(tmp_path: Path) -> None:
    source = NseXbrlSource(tmp_path, symbol="INFY", retry_backoff_seconds=0.0)
    source._verify(_issuer_instance("INFY"), from_date=_Q_START, to_date=_Q_END)


def test_m10_hard_block_is_terminal_and_not_retried(tmp_path: Path) -> None:
    source = NseXbrlSource(tmp_path, symbol="INFY", max_retries=3, retry_backoff_seconds=0.0)
    calls: list[int] = []

    def blocked() -> None:
        calls.append(1)
        raise RuntimeError("HTTP Error 403: Forbidden")

    with pytest.raises(XbrlHardBlockError):
        source._retry("download", blocked)
    assert len(calls) == 1  # a hard block is not retried


def test_m10_transient_error_is_retried(tmp_path: Path) -> None:
    source = NseXbrlSource(tmp_path, symbol="INFY", max_retries=3, retry_backoff_seconds=0.0)
    calls: list[int] = []

    def flaky() -> None:
        calls.append(1)
        raise TimeoutError("connection timed out")

    with pytest.raises(XbrlFetchError):
        source._retry("download", flaky)
    assert len(calls) == 3  # transient failures exhaust the retry budget


# --------------------------------------------------------------------------- #
# H6 — a failed run commits no canonical facts                                #
# --------------------------------------------------------------------------- #

# A filing whose Income == Expenses makes PBT == 0: it cross-foots and
# cross-checks, then fails in the effective-tax calculation (division guard).
_ZERO_PBT_FACTS: tuple[tuple[str, str, str, str], ...] = (
    ("RevenueFromOperations", "INR", "-7", "10000000000.00"),
    ("Income", "INR", "-7", "10000000000.00"),
    ("Expenses", "INR", "-7", "10000000000.00"),
    ("ProfitBeforeTax", "INR", "-7", "0.00"),
    ("ProfitLossForPeriod", "INR", "-7", "0.00"),
    ("ProfitOrLossAttributableToOwnersOfParent", "INR", "-7", "0.00"),
    (
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "INRPerShare",
        "2",
        "0.00",
    ),
)


def _zero_pbt_xbrl() -> bytes:
    fact_lines = "\n".join(
        f'  <in-bse-fin:{name} contextRef="OneD" unitRef="{unit}" '
        f'decimals="{decimals}">{value}</in-bse-fin:{name}>'
        for name, unit, decimals, value in _ZERO_PBT_FACTS
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        '    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        f'    xmlns:in-bse-fin="{_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        'scheme="http://www.nseindia.com/NSESymbol">ZEROCORP</xbrli:identifier></xbrli:entity>\n'
        "    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>"
        "<xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        '  <xbrli:unit id="INRPerShare"><xbrli:divide>'
        "<xbrli:unitNumerator><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator>"
        "<xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure>"
        "</xbrli:unitDenominator></xbrli:divide></xbrli:unit>\n"
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        f"{fact_lines}\n"
        "</xbrli:xbrl>\n"
    ).encode()


def _write_zero_pbt_pdf(path: Path) -> str:
    doc = pymupdf.open()
    page = doc.new_page()

    def put(x: float, y: float, text: str) -> None:
        page.insert_text((x, y), text, fontsize=9)

    put(
        60,
        90,
        "Statement of Consolidated Unaudited Results of ZeroCorp Limited "
        "for the quarter ended June 30, 2024",
    )
    put(60, 120, "Particulars")
    put(400, 140, "June 30, 2024")
    put(400, 160, "Unaudited")

    def row(y: float, label: str, value: str) -> None:
        put(60, y, label)
        put(410, y, value)

    row(190, "Revenue from operations", "1,000")
    row(210, "Total income", "1,000")
    row(230, "Total expenses", "1,000")
    row(250, "Profit / (loss) before tax", "0")
    row(270, "Profit / (loss) for the period", "0")
    row(290, "Basic (in Rs. per share)", "0.00")

    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_no_guidance_pdf(path: Path) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 90), "No numeric guidance was provided.", fontsize=9)
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zero_pbt_config() -> FundamentalsConfig:
    return FundamentalsConfig(
        issuer=IssuerConfig(
            name="ZeroCorp Limited", nse_symbol="ZEROCORP", entity_scheme="nse-symbol"
        ),
        quarter=QuarterConfig(
            issuer_quarter="FY25_Q1",
            program_quarter="QUARTER_1",
            label="Q1 FY25 (quarter ended 2024-06-30)",
            period_start=_Q_START,
            period_end=_Q_END,
            knowledge_cutoff=_RETRIEVED_AT,
        ),
        raw_dir="data/raw/zerocorp",
        store_db=":memory:",
        results_pdf=SourceFileConfig(
            source_id="zerocorp-results", filename="results.pdf", sha256="0" * 64
        ),
        transcript_pdf=SourceFileConfig(
            source_id="zerocorp-transcript", filename="transcript.pdf", sha256="0" * 64
        ),
        xbrl=XbrlConfig(
            source_id="zerocorp-xbrl",
            mode=XbrlMode.LOCAL,
            local_path="unused.xml",
            symbol="ZEROCORP",
        ),
    )


def test_h6_failed_run_commits_no_canonical_facts(tmp_path: Path) -> None:
    config = _zero_pbt_config()
    results_path = tmp_path / "results.pdf"
    transcript_path = tmp_path / "transcript.pdf"
    results_sha = _write_zero_pbt_pdf(results_path)
    transcript_sha = _write_no_guidance_pdf(transcript_path)

    xbrl_bytes = _zero_pbt_xbrl()
    xbrl_input = XbrlInput(
        xml_bytes=xbrl_bytes,
        file_sha256=hashlib.sha256(xbrl_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=_RETRIEVED_AT,
    )
    store = FactStore(":memory:")
    try:
        # Gates pass; the effective-tax division guard fails the run after them.
        with pytest.raises(PipelineError, match="profit before tax is zero"):
            run_pipeline(
                config=config,
                xbrl_input=xbrl_input,
                results_pdf_path=str(results_path),
                results_pdf_sha256=results_sha,
                transcript_pdf_path=str(transcript_path),
                transcript_pdf_sha256=transcript_sha,
                store=store,
            )
        # The failed run left NO canonical facts behind.
        assert store.query_canonical() == ()
    finally:
        store.close()
