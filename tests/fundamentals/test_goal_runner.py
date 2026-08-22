"""Goal-runner tests: deterministic multi-source reconciliation and the DoD.

The core is a DETERMINISTIC run for one synthetic stock over two committed
first-party fixtures (an NSE-style and a BSE-style Ind AS XBRL for the same
issuer/quarter). It proves the runner reuses the real ingest/parse/reconcile
components: reconciliation runs, a gold file is written, facts classify AGREE,
and the Definition of Done is evaluated. A CONFLICT is classified and surfaced,
a derived aggregator corroborates without counting as first-party, and a stock
with no reachable source is reported BLOCKED (never crashes, never loops).

A live variant (real Wave-1 fetch) is opt-in behind FUNDAMENTALS_LIVE_VALIDATION
so the default suite stays offline and deterministic.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from fundamentals.api.config import ConceptsConfig, SourceFileConfig
from fundamentals.api.goal_runner import (
    CollectedSource,
    QuarterMode,
    RunMode,
    SourceKind,
    SourceStatus,
    StockOutcome,
    _collect_pdf,
    reconcile_stock,
    run_stock,
)
from fundamentals.api.watchlist_config import (
    FixturePaths,
    SourceIdentifiers,
    StockConfig,
    StockQuarter,
    load_watchlist_config,
)
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.pdf_ocr_recovery import DEFAULT_OCR_DPI
from fundamentals.ingest.ocr_engine import OcrEngineUnavailableError, OcrToken
from fundamentals.reconcile.agreement import AgreementStatus

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NSE_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_nse_q3fy25_consolidated.xml"
_BSE_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_bse_q3fy25_consolidated.xml"
_BSE_SUMMARY_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_bse_summary_latest.json"

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_KNOWLEDGE_CUTOFF = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
PAT = "in-bse-fin:ProfitLossForPeriod"
EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

NSE_SOURCE_ID = "nse-indas-xbrl-consolidated"
BSE_SOURCE_ID = "bse-xbrl"
BSE_SUMMARY_SOURCE_ID = "bse-summary"
SCREENER_SOURCE_ID = "screener"


def _stock(*, fixtures: FixturePaths | None = None) -> StockConfig:
    """Build a synthetic Wave-1 stock config (defaults to the committed fixtures)."""
    return StockConfig(
        name="Synthetic Test Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            tijori_slug="synthetic-test-corp",
        ),
        quarter=StockQuarter(
            label="Q3FY25",
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            knowledge_cutoff=_KNOWLEDGE_CUTOFF,
        ),
        fixtures=fixtures
        if fixtures is not None
        else FixturePaths(nse=_NSE_FIXTURE, bse=_BSE_FIXTURE),
    )


def _summary_stock(
    *, quarter: StockQuarter | None = None, bse_fixture: str | None = _BSE_SUMMARY_FIXTURE
) -> StockConfig:
    """A stock cross-checked by NSE XBRL + the BSE resultsSnapshot summary source.

    BSE summary only carries Revenue / Net Profit / EPS, so the cross-check set is
    scoped to those three shared material facts (the identities remain default so
    NSE-only cross-footing still runs).
    """
    return StockConfig(
        name="Synthetic Summary Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            tijori_slug="synthetic-summary-corp",
        ),
        quarter=quarter
        if quarter is not None
        else StockQuarter(
            label="Q3FY25",
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            knowledge_cutoff=_KNOWLEDGE_CUTOFF,
        ),
        fixtures=FixturePaths(nse=_NSE_FIXTURE, bse=bse_fixture),
        concepts=ConceptsConfig(cross_check=(REVENUE, PAT, EPS)),
    )


# --- deterministic fixture run -------------------------------------------------


def test_two_first_party_fixtures_reconcile_to_done(tmp_path: Path) -> None:
    stock = _stock()
    report = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )

    # Reconciliation ran across both first-party hosts.
    assert set(report.available_sources) == {NSE_SOURCE_ID, BSE_SOURCE_ID}
    assert report.facts, "expected reconciled material facts"
    assert all(fact.status is AgreementStatus.AGREE for fact in report.facts)
    revenue = next(fact for fact in report.facts if fact.concept_qname == REVENUE)
    assert revenue.first_party_source_count == 2
    assert set(revenue.agreed_sources) == {NSE_SOURCE_ID, BSE_SOURCE_ID}
    assert revenue.agreed_value == "1000.00"

    # A gold file was written for the stock-quarter.
    gold_path = tmp_path / "SYNTH-Q3FY25.json"
    assert report.gold_file_path == str(gold_path)
    assert gold_path.is_file()

    # The Definition of Done was evaluated and met.
    assert report.dod.material_facts_agreed is True
    assert report.dod.gold_file_written is True
    assert report.dod.no_unsourced_number is True
    assert report.dod.met is True
    assert report.outcome is StockOutcome.DONE
    assert report.discrepancies == ()


def test_fixture_run_is_deterministic(tmp_path: Path) -> None:
    stock = _stock()
    first = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )
    gold_first = (tmp_path / "SYNTH-Q3FY25.json").read_bytes()
    second = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )
    gold_second = (tmp_path / "SYNTH-Q3FY25.json").read_bytes()
    assert gold_first == gold_second
    assert first.model_dump() == second.model_dump()


# --- BSE resultsSnapshot summary as the second first-party source --------------


def test_nse_and_bse_summary_reconcile_to_agree(tmp_path: Path) -> None:
    # NSE Ind AS XBRL + BSE resultsSnapshot summary for the SAME quarter: two
    # independent first-party sources must reconcile Revenue/NetProfit/EPS to AGREE.
    stock = _summary_stock()
    report = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )

    assert set(report.available_sources) == {NSE_SOURCE_ID, BSE_SUMMARY_SOURCE_ID}
    assert {fact.concept_qname for fact in report.facts} == {REVENUE, PAT, EPS}
    for fact in report.facts:
        assert fact.status is AgreementStatus.AGREE, fact.concept_qname
        assert fact.first_party_source_count == 2
        assert set(fact.agreed_sources) == {NSE_SOURCE_ID, BSE_SUMMARY_SOURCE_ID}

    revenue = next(fact for fact in report.facts if fact.concept_qname == REVENUE)
    assert revenue.agreed_value == "1000.00"

    assert report.dod.material_facts_agreed is True
    assert report.dod.met is True
    assert report.outcome is StockOutcome.DONE


def test_latest_quarter_mode_aligns_nse_and_bse_summary(tmp_path: Path) -> None:
    # --quarter latest: resolve the newest completed quarter BSE publishes (Dec-24),
    # then cross-check NSE and the BSE summary on that same aligned quarter.
    stock = _summary_stock()
    report = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
        quarter_mode=QuarterMode.LATEST,
    )

    assert report.quarter == "Dec-24"
    assert set(report.available_sources) == {NSE_SOURCE_ID, BSE_SUMMARY_SOURCE_ID}
    assert all(fact.status is AgreementStatus.AGREE for fact in report.facts)
    assert report.dod.material_facts_agreed is True
    assert report.outcome is StockOutcome.DONE


def test_latest_quarter_mode_blocks_when_bse_cannot_align(tmp_path: Path) -> None:
    # No BSE source to resolve the latest quarter from -> fail closed (never fabricate).
    stock = _summary_stock(bse_fixture=None)
    report = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
        quarter_mode=QuarterMode.LATEST,
    )
    assert report.outcome is StockOutcome.BLOCKED
    assert any("latest quarter" in blocker for blocker in report.blockers)


def test_latest_live_mode_picks_common_quarter_when_nse_lags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # LIVE latest: BSE's newest column (Jun-26) is not yet indexed by NSE, but the
    # prior quarter (Mar-26) is on both hosts -> resolve to the latest COMMON quarter.
    from fundamentals.api import goal_runner
    from fundamentals.ingest.xbrl_source import NseXbrlSource

    stock = _summary_stock()
    kinds = frozenset({SourceKind.NSE, SourceKind.BSE})

    monkeypatch.setattr(
        goal_runner,
        "_bse_available_periods",
        lambda *_args, **_kwargs: ("Jun-26", "Mar-26", "FY25-26"),
    )
    monkeypatch.setattr(
        NseXbrlSource,
        "available_consolidated_quarters",
        lambda self: frozenset({(date(2026, 1, 1), date(2026, 3, 31))}),
    )

    resolved, reason = goal_runner._resolve_latest_stock(stock, RunMode.LIVE, _REPO_ROOT, kinds)

    assert reason == ""
    assert resolved is not None
    assert resolved.quarter.label == "Mar-26"


def test_latest_live_mode_blocks_when_no_common_quarter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # LIVE latest: BSE and NSE share no completed quarter -> fail closed with reason.
    from fundamentals.api import goal_runner
    from fundamentals.ingest.xbrl_source import NseXbrlSource

    stock = _summary_stock()
    kinds = frozenset({SourceKind.NSE, SourceKind.BSE})

    monkeypatch.setattr(
        goal_runner,
        "_bse_available_periods",
        lambda *_args, **_kwargs: ("Jun-26", "Mar-26"),
    )
    monkeypatch.setattr(
        NseXbrlSource,
        "available_consolidated_quarters",
        lambda self: frozenset(),
    )

    resolved, reason = goal_runner._resolve_latest_stock(stock, RunMode.LIVE, _REPO_ROOT, kinds)

    assert resolved is None
    assert "no quarter common to BSE and NSE" in reason


def test_historical_quarter_records_bse_summary_skipped(tmp_path: Path) -> None:
    # A quarter BSE no longer publishes: the summary source SKIPS with a note
    # (skippable fail-closed) rather than crashing or blocking the stock.
    historical = StockQuarter(
        label="Q1FY25",
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        knowledge_cutoff=_KNOWLEDGE_CUTOFF,
    )
    stock = _summary_stock(quarter=historical)
    report = run_stock(
        stock,
        mode=RunMode.FIXTURE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )

    bse = next(src for src in report.sources if src.kind is SourceKind.BSE)
    assert bse.status is SourceStatus.SKIPPED
    assert bse.source_id == BSE_SUMMARY_SOURCE_ID
    assert "not available" in bse.note


# --- conflict + derived corroboration ------------------------------------------


def _xbrl_prov(source_id: str) -> Provenance:
    return Provenance(
        source_id=source_id,
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_KNOWLEDGE_CUTOFF,
    )


def _obs(
    concept: str,
    value: Decimal,
    source_id: str,
    *,
    scheme: str,
    entity: str,
    basis: AccountingFramework = AccountingFramework.IND_AS,
    unit: str = "INR crore",
    scale: int = 10_000_000,
    decimals: int = -7,
) -> Observation:
    return Observation(
        concept_qname=concept,
        raw_value=str(int(value) * scale),
        normalized_value=value,
        normalized_unit=unit,
        context_ref="OneD",
        entity_scheme=scheme,
        entity_id=entity,
        scope=Scope.CONSOLIDATED,
        accounting_basis=basis,
        period_type=PeriodType.DURATION,
        period_start=_PERIOD_START,
        period_end=_PERIOD_END,
        currency="INR",
        scale=scale,
        decimals=decimals,
        provenance=_xbrl_prov(source_id),
    )


def test_conflict_is_classified_and_surfaced(tmp_path: Path) -> None:
    # NSE and BSE agree on revenue but materially disagree on profit for the period.
    nse_obs = (
        _obs(REVENUE, Decimal(1000), NSE_SOURCE_ID, scheme="nse-symbol", entity="SYNTH"),
        _obs(PAT, Decimal(150), NSE_SOURCE_ID, scheme="nse-symbol", entity="SYNTH"),
    )
    bse_obs = (
        _obs(REVENUE, Decimal(1000), BSE_SOURCE_ID, scheme="bse-scrip", entity="999999"),
        _obs(PAT, Decimal(300), BSE_SOURCE_ID, scheme="bse-scrip", entity="999999"),
    )
    sources = [
        CollectedSource(
            kind=SourceKind.NSE,
            source_id=NSE_SOURCE_ID,
            status=SourceStatus.OK,
            observations=nse_obs,
        ),
        CollectedSource(
            kind=SourceKind.BSE,
            source_id=BSE_SOURCE_ID,
            status=SourceStatus.OK,
            observations=bse_obs,
        ),
    ]
    report = reconcile_stock(_stock(), sources, out_dir=tmp_path)

    revenue = next(fact for fact in report.facts if fact.concept_qname == REVENUE)
    pat = next(fact for fact in report.facts if fact.concept_qname == PAT)
    assert revenue.status is AgreementStatus.AGREE
    assert pat.status is AgreementStatus.CONFLICT
    assert pat.agreed_value is None
    assert pat in report.discrepancies

    # A conflict is surfaced for human adjudication, not silently marked done.
    assert report.dod.material_facts_agreed is False
    assert report.dod.met is False
    assert report.outcome is StockOutcome.NEEDS_ADJUDICATION
    # The reference file is still written (records what every source said).
    assert report.gold_file_path is not None


def test_derived_source_corroborates_without_counting_as_first_party(tmp_path: Path) -> None:
    nse_obs = (_obs(REVENUE, Decimal(1000), NSE_SOURCE_ID, scheme="nse-symbol", entity="SYNTH"),)
    bse_obs = (_obs(REVENUE, Decimal(1000), BSE_SOURCE_ID, scheme="bse-scrip", entity="999999"),)
    screener_obs = (
        _obs(
            "screener:Sales",
            Decimal(1000),
            SCREENER_SOURCE_ID,
            scheme="screener-slug",
            entity="SYNTH",
            basis=AccountingFramework.UNKNOWN,
        ),
    )
    sources = [
        CollectedSource(
            kind=SourceKind.NSE,
            source_id=NSE_SOURCE_ID,
            status=SourceStatus.OK,
            observations=nse_obs,
        ),
        CollectedSource(
            kind=SourceKind.BSE,
            source_id=BSE_SOURCE_ID,
            status=SourceStatus.OK,
            observations=bse_obs,
        ),
        CollectedSource(
            kind=SourceKind.SCREENER,
            source_id=SCREENER_SOURCE_ID,
            status=SourceStatus.OK,
            observations=screener_obs,
        ),
    ]
    report = reconcile_stock(_stock(), sources, out_dir=tmp_path)

    revenue = next(fact for fact in report.facts if fact.concept_qname == REVENUE)
    assert revenue.status is AgreementStatus.AGREE
    assert revenue.first_party_source_count == 2
    assert SCREENER_SOURCE_ID in revenue.corroborating_sources
    assert SCREENER_SOURCE_ID not in revenue.agreed_sources


# --- blocked stock -------------------------------------------------------------


def test_blocked_stock_with_no_sources_is_reported_not_crashed(tmp_path: Path) -> None:
    # A stock with no configured fixtures: every source skips, none reachable.
    stock = _stock(fixtures=FixturePaths())
    report = run_stock(stock, mode=RunMode.FIXTURE, repo_root=_REPO_ROOT, out_dir=tmp_path)

    assert report.outcome is StockOutcome.BLOCKED
    assert report.facts == ()
    assert report.gold_file_path is None
    assert report.available_sources == ()
    assert all(src.status is not SourceStatus.OK for src in report.sources)
    # No gold file was written for a stock with no reachable first-party source.
    assert not (tmp_path / "SYNTH-Q3FY25.json").exists()


def test_empty_source_list_reconciles_to_blocked(tmp_path: Path) -> None:
    report = reconcile_stock(_stock(), [], out_dir=tmp_path)
    assert report.outcome is StockOutcome.BLOCKED
    assert report.dod.met is False


# --- watchlist config ----------------------------------------------------------


def test_watchlist_config_loads_wave1_stocks() -> None:
    config = load_watchlist_config(_REPO_ROOT / "config" / "watchlist.yaml")
    symbols = {stock.identifiers.nse_symbol for stock in config.stocks}
    # Wave-1 stocks must remain present; the watchlist also carries the Wave-2
    # expansion, so this is a subset check rather than an exact-set assertion.
    assert {"LAURUSLABS", "MTARTECH", "SONACOMS", "THERMAX", "TITAN"} <= symbols
    # Uncertain identifiers are marked for verification, never silently trusted.
    titan = config.stock("TITAN")
    assert "tijori_slug" in titan.identifiers.needs_verification


# --- opt-in live variant -------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("FUNDAMENTALS_LIVE_VALIDATION"),
    reason="live validation is opt-in (set FUNDAMENTALS_LIVE_VALIDATION=1)",
)
def test_live_single_stock_validation(tmp_path: Path) -> None:  # pragma: no cover - opt-in
    config = load_watchlist_config(_REPO_ROOT / "config" / "watchlist.yaml")
    stock = config.stock(os.environ.get("FUNDAMENTALS_LIVE_SYMBOL", "TITAN"))
    report = run_stock(
        stock,
        mode=RunMode.LIVE,
        repo_root=_REPO_ROOT,
        kinds=frozenset({SourceKind.NSE, SourceKind.BSE}),
        out_dir=tmp_path,
    )
    assert report.symbol == stock.symbol
    assert report.outcome in set(StockOutcome)


# --- PDF OCR recovery wired into the goal runner (Task 2) -----------------------
#
# The deterministic tests drive the PDF collection with a FAKE local OCR engine (no
# engine dependency, no bytes leaving the process): a garbled statement recovers, a
# missing concept is filled while the text lane wins on concepts it already read, an
# unavailable extra fails closed, and a complete text lane never invokes OCR.

INCOME = "in-bse-fin:Income"
PBT = "in-bse-fin:ProfitBeforeTax"

_OCR_SCALE = DEFAULT_OCR_DPI / 72.0


def _tok(
    text: str, x_pt: float, y_pt: float, *, conf: float = 0.97, w_pt: float = 40.0
) -> OcrToken:
    """One OCR token at a point position, converted to the image pixels the lane expects."""
    return OcrToken(
        text=text,
        x0=x_pt * _OCR_SCALE,
        y0=y_pt * _OCR_SCALE,
        x1=(x_pt + w_pt) * _OCR_SCALE,
        y1=(y_pt + 8.0) * _OCR_SCALE,
        confidence=conf,
    )


def _self_consistent_tokens(*, total_income: str = "1050.00") -> tuple[OcrToken, ...]:
    """Tokens for a self-consistent consolidated statement (cross-foot identities hold)."""
    tokens: list[OcrToken] = [
        _tok("(Rs. in Crore)", 60.0, 40.0),
        _tok("Consolidated", 200.0, 52.0),
        _tok("Dec31,2024", 240.0, 90.0),
        _tok("Dec31,2023", 340.0, 90.0),
    ]
    body: tuple[tuple[str, str], ...] = (
        ("Revenue from operations", "1000.00"),
        ("Other income", "50.00"),
        ("Total income", total_income),
        ("Total expenses", "800.00"),
        ("Profit before tax", "250.00"),
        ("Total tax expense", "60.00"),
        ("Net profit for the period", "190.00"),
        ("Total other comprehensive income", "10.00"),
        ("Total comprehensive income for the period", "200.00"),
        ("Basic", "5.00"),
    )
    y = 120.0
    for label, value in body:
        tokens.append(_tok(label, 60.0, y, w_pt=len(label) * 4.0))
        tokens.append(_tok(value, 240.0, y))
        tokens.append(_tok("0.00", 340.0, y))
        y += 15.0
    return tuple(tokens)


class _FakeOcrEngine:
    """Deterministic OCR engine that returns fixed tokens, ignoring the image bytes."""

    def __init__(self, tokens: tuple[OcrToken, ...]) -> None:
        self._tokens = tokens

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:  # noqa: ARG002 - fixed tokens
        return self._tokens


class _UnavailableOcrEngine:
    """Simulates a missing ``ocr`` extra: fails closed when the lane actually uses it."""

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:  # noqa: ARG002 - always raises
        raise OcrEngineUnavailableError("ocr extra not installed")


class _SpyOcrEngine:
    """Records invocations so a complete text lane can be proven never to render/OCR."""

    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:  # noqa: ARG002 - counted
        self.calls += 1
        return ()


def _write_pl_pdf(path: Path, *, split_revenue: bool = False) -> str:
    """Write a clean SEBI consolidated statement PDF; ``split_revenue`` drops the total."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (60, 80),
        "STATEMENT OF CONSOLIDATED UNAUDITED FINANCIAL RESULTS "
        "FOR THE QUARTER ENDED 31 DECEMBER 2024",
        fontsize=9,
    )
    page.insert_text((60, 100), "(Rs. in crore)", fontsize=9)
    page.insert_text((250, 140), "31-12-2024", fontsize=9)
    page.insert_text((320, 140), "31-12-2023", fontsize=9)

    def row(y: float, label: str, value: str | None) -> None:
        page.insert_text((60, y), label, fontsize=9)
        if value is not None:
            page.insert_text((250, y), value, fontsize=9)
            page.insert_text((320, y), "0", fontsize=9)

    if split_revenue:
        row(170, "Revenue from operations", None)
        row(185, "- Sale of products", "960")
    else:
        row(170, "Revenue from operations", "1000")
    row(205, "Total income", "1010")
    row(225, "Profit before tax", "200")
    row(245, "Profit for the period", "150")
    row(275, "Basic", "5.00")
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_garbled_pdf(path: Path) -> str:
    """Write a P&L-shaped page whose consolidated text layer is too garbled to parse."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 60), "Statement of unaudited financial results", fontsize=9)
    page.insert_text((60, 75), "Consolidut<-d", fontsize=9)
    page.insert_text((60, 95), "1 Income:", fontsize=9)
    page.insert_text((60, 110), "Rc,·cnue from opcrations 999.00", fontsize=9)
    page.insert_text((60, 125), "2 Expenses:", fontsize=9)
    page.insert_text((60, 140), "Total expcrucs 888.00", fontsize=9)
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdf_ocr_stock(path: Path, sha: str) -> StockConfig:
    """A stock whose only source is a results PDF at ``path`` for the reviewed quarter."""
    return StockConfig(
        name="Synthetic OCR Corp",
        domain="Test",
        identifiers=SourceIdentifiers(
            nse_symbol="SYNTH",
            bse_scrip="999999",
            screener_slug="SYNTH",
            tijori_slug="synthetic-ocr-corp",
        ),
        quarter=StockQuarter(
            label="Q3FY25",
            period_start=_PERIOD_START,
            period_end=_PERIOD_END,
            knowledge_cutoff=_KNOWLEDGE_CUTOFF,
        ),
        results_pdf=SourceFileConfig(
            source_id="bse-results-pdf", filename="results.pdf", sha256=sha
        ),
        fixtures=FixturePaths(results_pdf=str(path)),
    )


def _collect(path: Path, sha: str, engine: object) -> CollectedSource:
    """Collect the PDF source through the goal runner's fixture path with an injected engine."""
    return _collect_pdf(
        _pdf_ocr_stock(path, sha),
        RunMode.FIXTURE,
        _REPO_ROOT,
        _KNOWLEDGE_CUTOFF,
        ocr_engine=engine,  # type: ignore[arg-type]
    )


def _obs_by_concept(source: CollectedSource) -> dict[str, Decimal]:
    return {obs.concept_qname: obs.normalized_value for obs in source.observations}


def test_pdf_ocr_recovers_garbled_statement_via_injected_engine(tmp_path: Path) -> None:
    # THERMAX-like garbled text layer fails the deterministic lane closed; the injected
    # (fake) local OCR engine recovers a self-consistent statement, so the PDF source is OK.
    pdf = tmp_path / "results.pdf"
    sha = _write_garbled_pdf(pdf)
    source = _collect(pdf, sha, _FakeOcrEngine(_self_consistent_tokens()))
    assert source.status is SourceStatus.OK
    got = _obs_by_concept(source)
    assert got[REVENUE] == Decimal("1000.00")
    assert got[INCOME] == Decimal("1050.00")
    assert got[PAT] == Decimal("190.00")
    assert got[EPS] == Decimal("5.00")


def test_pdf_ocr_fills_only_missing_concepts_text_lane_wins(tmp_path: Path) -> None:
    # Text lane reads income/PBT/PFP/EPS but not the split revenue; OCR fills revenue.
    # The OCR total-income (1050) must NOT overwrite the text-lane total-income (1010).
    pdf = tmp_path / "results.pdf"
    sha = _write_pl_pdf(pdf, split_revenue=True)
    source = _collect(pdf, sha, _FakeOcrEngine(_self_consistent_tokens(total_income="1050.00")))
    assert source.status is SourceStatus.OK
    got = _obs_by_concept(source)
    assert got[REVENUE] == Decimal("1000.00")  # filled from OCR (text lane lacked it)
    assert got[INCOME] == Decimal("1010")  # text lane wins on a concept it already read
    assert got[PBT] == Decimal("200")


def test_pdf_ocr_unavailable_keeps_text_lane_fail_closed(tmp_path: Path) -> None:
    # The ``ocr`` extra is absent: the coverage gap is left unfilled rather than
    # fabricated, and the text-lane facts still stand (source OK, revenue simply absent).
    pdf = tmp_path / "results.pdf"
    sha = _write_pl_pdf(pdf, split_revenue=True)
    source = _collect(pdf, sha, _UnavailableOcrEngine())
    assert source.status is SourceStatus.OK
    got = _obs_by_concept(source)
    assert REVENUE not in got
    assert got[INCOME] == Decimal("1010")


def test_complete_text_lane_never_invokes_ocr(tmp_path: Path) -> None:
    # When the text lane already covers every target concept, OCR is never rendered or
    # recognized (no needless work, no regression risk).
    pdf = tmp_path / "results.pdf"
    sha = _write_pl_pdf(pdf)
    spy = _SpyOcrEngine()
    source = _collect(pdf, sha, spy)
    assert source.status is SourceStatus.OK
    assert spy.calls == 0
    assert set(_obs_by_concept(source)) == {REVENUE, INCOME, PBT, PAT, EPS}


def test_fixture_mode_without_engine_runs_no_ocr(tmp_path: Path) -> None:
    # Default fixture collection (no injected engine) stays deterministic: a split
    # revenue with no OCR simply remains missing, never fabricated.
    pdf = tmp_path / "results.pdf"
    sha = _write_pl_pdf(pdf, split_revenue=True)
    source = _collect(pdf, sha, None)
    assert source.status is SourceStatus.OK
    assert REVENUE not in _obs_by_concept(source)


def _thermax_results_pdf() -> Path | None:
    matches = sorted(Path("data/raw/watchlist/thermax/bse_pdf").glob("*.pdf"))
    return matches[0] if matches else None


def test_collect_pdf_recovers_thermax_with_real_local_engine() -> None:
    # End-to-end goal-runner PDF wiring with the REAL local engine on the real garbled
    # THERMAX filing (both gitignored/optional, so skipped in a minimal checkout): the
    # text lane fails closed and OCR recovers the consolidated figures through _collect_pdf.
    pytest.importorskip("rapidocr_onnxruntime")
    pdf_path = _thermax_results_pdf()
    if pdf_path is None:
        pytest.skip("THERMAX results PDF not present (gitignored)")
    from fundamentals.ingest.ocr_engine import RapidOcrEngine
    from fundamentals.ingest.pdf_source import compute_file_sha256

    stock = _pdf_ocr_stock(pdf_path, compute_file_sha256(pdf_path))
    source = _collect_pdf(
        stock, RunMode.FIXTURE, _REPO_ROOT, _KNOWLEDGE_CUTOFF, ocr_engine=RapidOcrEngine()
    )
    assert source.status is SourceStatus.OK
    got = _obs_by_concept(source)
    assert got[INCOME] == Decimal("2539.27")
    assert got[PAT] == Decimal("113.73")
    assert got[EPS] == Decimal("10.29")
