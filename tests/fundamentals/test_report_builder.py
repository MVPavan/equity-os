"""Bridge tests — StockReport -> source-verified EarningsUpdate markdown.

These pin the generalisation of the Infosys A-04 renderer to any reconciled
Wave-1 :class:`StockReport`. The bridge is generic over the report (no per-symbol
branch); it threads the provenance of every first-party observation that agreed
into the rendered fact, honours the reconciliation status (a single-source or
conflicting fact is never dressed as cross-source-confirmed), and fails closed
when a required P&L role has no retained first-party value.

Everything is synthetic and in-memory; no bytes leave the process.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from fundamentals.api.goal_runner import (
    CollectedSource,
    CrossFootOutcome,
    DodEvaluation,
    SourceKind,
    SourceStatus,
    StockOutcome,
    StockReport,
)
from fundamentals.api.report_builder import (
    ReportBuild,
    ReportBuildError,
    build_report,
    render_report,
)
from fundamentals.api.watchlist_config import (
    SourceIdentifiers,
    StockConfig,
    StockQuarter,
)
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.output.earnings_update import FactRole, RenderError, render_earnings_update

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_KNOWLEDGE_CUTOFF = datetime(2025, 2, 15, tzinfo=UTC)
_RETRIEVED_AT = datetime(2025, 2, 15, tzinfo=UTC)

_NSE_SOURCE_ID = "nse-indas-xbrl-consolidated"
_PDF_SOURCE_ID = "bse-results-pdf"

_CRORE_UNIT = "INR crore"
_PER_SHARE_UNIT = "INR per share"
_CRORE_SCALE = 10_000_000
_CRORE_DECIMALS = -7

REVENUE = "in-bse-fin:RevenueFromOperations"
INCOME = "in-bse-fin:Income"
EXPENSES = "in-bse-fin:Expenses"
PBT = "in-bse-fin:ProfitBeforeTax"
PAT = "in-bse-fin:ProfitLossForPeriod"
EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

# A structurally complete, internally consistent synthetic filing (crore):
# Income − Expenses = PBT (600 − 480 = 120); values chosen so cross-foot holds.
_ROLE_VALUES: dict[str, tuple[str, str]] = {
    REVENUE: ("580", _CRORE_UNIT),
    INCOME: ("600", _CRORE_UNIT),
    EXPENSES: ("480", _CRORE_UNIT),
    PBT: ("120", _CRORE_UNIT),
    PAT: ("90", _CRORE_UNIT),
    EPS: ("4.50", _PER_SHARE_UNIT),
}

# Concepts the shared Ind-AS config carries a second first-party (PDF) column for.
# Expenses is deliberately absent — the PDF parser extracts no expenses line, so
# Expenses is always single-source (NSE) in the real pipeline too.
_PDF_CONCEPTS = frozenset({REVENUE, INCOME, PBT, PAT, EPS})


def _xbrl_provenance(source_id: str, context_ref: str) -> Provenance:
    return Provenance(
        source_id=source_id,
        file_sha256="a" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=context_ref,
        retrieved_at=_RETRIEVED_AT,
    )


def _pdf_provenance(source_id: str) -> Provenance:
    return Provenance(
        source_id=source_id,
        file_sha256="b" * 64,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=6,
        block=10,
        span="271.5,248.0,300.9,259.4",
        retrieved_at=_RETRIEVED_AT,
    )


def _observation(concept: str, value: str, unit: str, provenance: Provenance) -> Observation:
    per_share = unit == _PER_SHARE_UNIT
    return Observation(
        concept_qname=concept,
        raw_value=value,
        normalized_value=Decimal(value),
        normalized_unit=unit,
        entity_scheme="nse-symbol",
        entity_id="SYNTH",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        currency="INR",
        scale=1 if per_share else _CRORE_SCALE,
        decimals=2 if per_share else _CRORE_DECIMALS,
        provenance=provenance,
    )


def _nse_obs(concept: str, value: str, unit: str) -> Observation:
    return _observation(concept, value, unit, _xbrl_provenance(_NSE_SOURCE_ID, "OneD"))


def _pdf_obs(concept: str, value: str, unit: str) -> Observation:
    return _observation(concept, value, unit, _pdf_provenance(_PDF_SOURCE_ID))


def _stock() -> StockConfig:
    """A synthetic Wave-1 stock reusing the shared Ind-AS concept defaults."""
    return StockConfig(
        name="Synthetic Test Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            tijori_slug="synthetic-test-corp",
            tijori_company_id=81,
        ),
        quarter=StockQuarter(
            label="Q3FY25",
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            knowledge_cutoff=_KNOWLEDGE_CUTOFF,
        ),
    )


def _sources(
    *,
    nse: dict[str, tuple[str, str]],
    pdf: dict[str, tuple[str, str]],
) -> tuple[CollectedSource, ...]:
    collected: list[CollectedSource] = []
    if nse:
        collected.append(
            CollectedSource(
                kind=SourceKind.NSE,
                source_id=_NSE_SOURCE_ID,
                status=SourceStatus.OK,
                observations=tuple(
                    _nse_obs(concept, value, unit) for concept, (value, unit) in nse.items()
                ),
            )
        )
    if pdf:
        collected.append(
            CollectedSource(
                kind=SourceKind.PDF,
                source_id=_PDF_SOURCE_ID,
                status=SourceStatus.OK,
                observations=tuple(
                    _pdf_obs(concept, value, unit) for concept, (value, unit) in pdf.items()
                ),
            )
        )
    return tuple(collected)


def _report(sources: tuple[CollectedSource, ...]) -> StockReport:
    """Wrap collected sources in a minimal but valid StockReport.

    The bridge re-derives facts from the sources, so the report's own projected
    ``facts`` are irrelevant here; only ``sources`` and identity/cross-foot carry.
    """
    dod = DodEvaluation(
        material_facts_agreed=False,
        cross_foot_holds=True,
        gold_file_written=True,
        no_unsourced_number=True,
        no_missing_material_concepts=True,
    )
    cross_foot = (
        CrossFootOutcome(
            identity="Profit before tax = Total income - Total expenses",
            passed=True,
            residual="0",
            tolerance="1.0",
            flagged_for_review=False,
        ),
    )
    return StockReport(
        symbol="SYNTH",
        name="Synthetic Test Corp",
        domain="Test",
        quarter="Q3FY25",
        outcome=StockOutcome.DONE,
        sources=sources,
        facts=(),
        discrepancies=(),
        missing_material_concepts=(),
        cross_foot=cross_foot,
        gold_file_path=None,
        dod=dod,
        blockers=(),
        identifiers_to_verify=(),
    )


def _full_sources() -> tuple[CollectedSource, ...]:
    """Both first-party columns present; PDF omits Expenses (single-source there)."""
    return _sources(
        nse=dict(_ROLE_VALUES),
        pdf={c: v for c, v in _ROLE_VALUES.items() if c in _PDF_CONCEPTS},
    )


def _rendered_fact(build: ReportBuild, role: FactRole):
    return next(fact for fact in build.update.facts if fact.role is role)


def test_two_first_party_agree_fact_carries_both_anchors() -> None:
    build = build_report(_report(_full_sources()), _stock())
    revenue = _rendered_fact(build, FactRole.REVENUE)

    assert revenue.value == Decimal("580")
    assert revenue.reconciliation_status is ReconciliationStatus.CROSS_SOURCE_CONFIRMED
    anchor_types = {source.anchor_type for source in revenue.sources}
    source_ids = {source.source_id for source in revenue.sources}
    assert anchor_types == {SourceAnchorType.PDF_SPAN, SourceAnchorType.XBRL_CONTEXT}
    assert source_ids == {_NSE_SOURCE_ID, _PDF_SOURCE_ID}


def test_single_source_fact_is_not_labelled_cross_source_confirmed() -> None:
    build = build_report(_report(_full_sources()), _stock())
    expenses = _rendered_fact(build, FactRole.TOTAL_EXPENSES)

    # Expenses exists only in NSE (the PDF parser extracts no expenses line).
    assert expenses.value == Decimal("480")
    assert expenses.reconciliation_status is not ReconciliationStatus.CROSS_SOURCE_CONFIRMED
    assert expenses.reconciliation_status is ReconciliationStatus.UNRECONCILED
    assert len(expenses.sources) == 1
    assert expenses.sources[0].source_id == _NSE_SOURCE_ID
    assert expenses.sources[0].anchor_type is SourceAnchorType.XBRL_CONTEXT


def test_fully_single_source_stock_confirms_nothing_cross_source() -> None:
    # A stock reachable only through NSE (no PDF column at all): every role is
    # single-source, so §11 cross-check must NOT report a pass.
    build = build_report(_report(_sources(nse=dict(_ROLE_VALUES), pdf={})), _stock())
    assert build.renderable
    for fact in build.update.facts:
        assert fact.reconciliation_status is ReconciliationStatus.UNRECONCILED
        assert len(fact.sources) == 1
    assert build.update.cross_check.passed_count == 0
    assert build.update.cross_check.total_count == 5


def test_fail_closed_when_a_required_role_has_no_observation() -> None:
    # Drop Expenses from every source: the required role is unresolved and the
    # render fails closed rather than fabricating or silently omitting it.
    sources = _sources(
        nse={c: v for c, v in _ROLE_VALUES.items() if c != EXPENSES},
        pdf={c: v for c, v in _ROLE_VALUES.items() if c in _PDF_CONCEPTS},
    )
    build = build_report(_report(sources), _stock())

    assert not build.renderable
    unresolved_roles = {item.role for item in build.unresolved}
    assert FactRole.TOTAL_EXPENSES in unresolved_roles
    with pytest.raises(RenderError):
        render_earnings_update(build.update)
    with pytest.raises(ReportBuildError):
        render_report(_report(sources), _stock())


def test_conflict_role_is_surfaced_not_fabricated() -> None:
    # NSE says PBT 120, PDF says PBT 300 — a true cross-source conflict. No value
    # is retained; the role is surfaced as unresolved (conflict), never invented.
    nse = dict(_ROLE_VALUES)
    pdf = {c: v for c, v in _ROLE_VALUES.items() if c in _PDF_CONCEPTS}
    pdf[PBT] = ("300", _CRORE_UNIT)
    build = build_report(_report(_sources(nse=nse, pdf=pdf)), _stock())

    assert not build.renderable
    conflict = next(item for item in build.unresolved if item.role is FactRole.PROFIT_BEFORE_TAX)
    assert "conflict" in conflict.reason.lower()
    assert all(fact.role is not FactRole.PROFIT_BEFORE_TAX for fact in build.update.facts)


def test_calculations_are_code_derived_from_sourced_inputs() -> None:
    build = build_report(_report(_full_sources()), _stock())
    labels = {calc.label: calc for calc in build.update.calculations}

    # Effective tax rate = (PBT - PAT) / PBT = (120 - 90) / 120 = 25.0%.
    tax = next(calc for label, calc in labels.items() if "tax rate" in label.lower())
    assert tax.result == "25.0"
    assert "120" in tax.trace and "90" in tax.trace

    # Other-income gap = Total income - Revenue = 600 - 580 = 20 (crore).
    gap = next(calc for label, calc in labels.items() if "income" in label.lower())
    assert gap.result == "20"


def test_full_report_renders_all_six_roles_with_sourced_anchors() -> None:
    markdown = render_report(_report(_full_sources()), _stock())

    assert "# Synthetic Test Corp (SYNTH) — Q3FY25" in markdown
    assert "## 2. facts" in markdown
    # Every required role appears in the facts table.
    for label in (
        "Revenue from operations",
        "Total income",
        "Total expenses",
        "Profit before tax",
        "Profit for the period (PAT)",
        "EPS basic",
    ):
        assert label in markdown
    # Footnotes carry the exact XBRL context and PDF page/block/span anchors.
    assert "context OneD" in markdown
    assert "page 6, block 10, span 271.5,248.0,300.9,259.4" in markdown
    # §11 approval record honestly reports 5/5 cross-checked headline figures.
    assert "5/5 headline figures agree" in markdown
    # Analyst-judgment sections stay deferred, never fabricated.
    assert "analyst" in markdown.lower()
    assert "Non-canonical" in markdown


def test_bridge_reports_no_unsourced_number() -> None:
    # Every rendered fact must carry at least one provenance anchor.
    build = build_report(_report(_full_sources()), _stock())
    assert build.renderable
    for fact in build.update.facts:
        assert fact.sources, f"{fact.role} rendered with no source anchor"
