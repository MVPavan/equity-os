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

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.api.goal_runner import (
    CollectedSource,
    RunMode,
    SourceKind,
    SourceStatus,
    StockOutcome,
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
from fundamentals.reconcile.agreement import AgreementStatus

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NSE_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_nse_q3fy25_consolidated.xml"
_BSE_FIXTURE = "tests/fundamentals/fixtures/synthetic_wave1_bse_q3fy25_consolidated.xml"

_PERIOD_START = date(2024, 10, 1)
_PERIOD_END = date(2024, 12, 31)
_KNOWLEDGE_CUTOFF = datetime(2025, 2, 15, tzinfo=UTC)

REVENUE = "in-bse-fin:RevenueFromOperations"
PAT = "in-bse-fin:ProfitLossForPeriod"

NSE_SOURCE_ID = "nse-indas-xbrl-consolidated"
BSE_SOURCE_ID = "bse-xbrl"
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


def test_watchlist_config_loads_five_wave1_stocks() -> None:
    config = load_watchlist_config(_REPO_ROOT / "config" / "watchlist.yaml")
    symbols = {stock.identifiers.nse_symbol for stock in config.stocks}
    assert symbols == {"LAURUSLABS", "MTARTECH", "SONACOMS", "THERMAX", "TITAN"}
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
