"""Screener.in adapter — DERIVED quarterly P&L cross-check source.

Deterministic tests parse a committed synthetic Screener-shaped HTML fixture
(NOT fetched from screener.in) and assert the parse yields ``Observation``s
flagged as derived cross-check values (``source_id="screener"``, Screener
namespaced concepts, ``UNKNOWN`` basis, URL-only anchor). The live path is
opt-in via ``RUN_SCREENER_LIVE=1`` and hits the credential-free Infosys page.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.screener_source import (
    SOURCE_ID,
    ScreenerConcept,
    ScreenerFetchError,
    ScreenerResult,
    ScreenerSource,
    ScreenerSourceConfig,
    is_derived,
    parse_quarterly_pnl,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_screener_quarters.html"
_FIXTURE_URL = "https://www.screener.in/company/INFY/consolidated/"
_ENTITY_ID = "INFY"

# Confirmed values from the synthetic fixture (Jun 2025 quarter column).
_JUN_2025_END = date(2025, 6, 30)
_JUN_2025_START = date(2025, 4, 1)
_EXPECTED_JUN_2025 = {
    ScreenerConcept.SALES.value: Decimal("42279"),
    ScreenerConcept.OPERATING_PROFIT.value: Decimal("10479"),
    ScreenerConcept.NET_PROFIT.value: Decimal("6921"),
    ScreenerConcept.EPS.value: Decimal("16.68"),
}


@pytest.fixture(scope="module")
def observations() -> tuple[Observation, ...]:
    html_text = _FIXTURE.read_text(encoding="utf-8")
    file_sha256 = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
    return parse_quarterly_pnl(
        html_text,
        source_url=_FIXTURE_URL,
        file_sha256=file_sha256,
        entity_id=_ENTITY_ID,
        consolidated=True,
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
    )


def _jun_2025(observations: tuple[Observation, ...]) -> dict[str, Observation]:
    return {
        obs.concept_qname: obs
        for obs in observations
        if obs.period_end == _JUN_2025_END
    }


def test_parses_four_headline_concepts_per_quarter(
    observations: tuple[Observation, ...],
) -> None:
    # 4 headline concepts x 3 quarter columns in the fixture.
    assert len(observations) == 12
    concepts = {obs.concept_qname for obs in observations}
    assert concepts == {concept.value for concept in ScreenerConcept}


def test_headline_values_match_fixture(observations: tuple[Observation, ...]) -> None:
    latest = _jun_2025(observations)
    assert set(latest) == set(_EXPECTED_JUN_2025)
    for concept_qname, expected in _EXPECTED_JUN_2025.items():
        assert latest[concept_qname].normalized_value == expected, concept_qname


def test_all_observations_flagged_derived(observations: tuple[Observation, ...]) -> None:
    for obs in observations:
        assert is_derived(obs) is True
        assert obs.provenance.source_id == SOURCE_ID
        # Screener-namespaced concept — never a first-party taxonomy qname.
        assert obs.concept_qname.startswith("screener:")
        # Screener restates: basis is unknown, never asserted as IND_AS/IFRS.
        assert obs.accounting_basis is AccountingFramework.UNKNOWN


def test_provenance_is_url_anchor_without_page_span(
    observations: tuple[Observation, ...],
) -> None:
    for obs in observations:
        provenance = obs.provenance
        # Aggregated value: URL context anchor, no exact page/block/span.
        assert provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
        assert provenance.context_ref is not None
        assert _FIXTURE_URL in provenance.context_ref
        assert provenance.page is None
        assert provenance.block is None
        assert provenance.span is None
        assert len(provenance.file_sha256) == 64


def test_raw_value_preserved_and_normalized(
    observations: tuple[Observation, ...],
) -> None:
    sales = _jun_2025(observations)[ScreenerConcept.SALES.value]
    # raw_value keeps the lexical Indian-grouped string; normalized strips commas.
    assert sales.raw_value == "42,279"
    assert sales.normalized_value == Decimal("42279")
    assert sales.currency == "INR"
    assert sales.normalized_unit == "INR crore"


def test_quarter_period_is_a_fiscal_quarter(
    observations: tuple[Observation, ...],
) -> None:
    sales = _jun_2025(observations)[ScreenerConcept.SALES.value]
    assert sales.period_type is PeriodType.DURATION
    assert sales.period_start == _JUN_2025_START
    assert sales.period_end == _JUN_2025_END
    # A ~90-day quarter, not a full year.
    assert (sales.period_end - sales.period_start).days < 100


def test_consolidated_flag_sets_scope(observations: tuple[Observation, ...]) -> None:
    for obs in observations:
        assert obs.scope is Scope.CONSOLIDATED


def test_standalone_flag_sets_scope() -> None:
    html_text = _FIXTURE.read_text(encoding="utf-8")
    file_sha256 = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
    standalone = parse_quarterly_pnl(
        html_text,
        source_url="https://www.screener.in/company/INFY/",
        file_sha256=file_sha256,
        entity_id=_ENTITY_ID,
        consolidated=False,
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
    )
    assert all(obs.scope is Scope.STANDALONE for obs in standalone)


def test_missing_quarters_table_fails_closed() -> None:
    with pytest.raises(ScreenerFetchError):
        parse_quarterly_pnl(
            "<html><body><p>no quarterly section here</p></body></html>",
            source_url=_FIXTURE_URL,
            file_sha256="0" * 64,
            entity_id=_ENTITY_ID,
            consolidated=True,
            retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
        )


def test_config_builds_public_urls_without_credentials() -> None:
    standalone = ScreenerSourceConfig(slug="INFY")
    consolidated = ScreenerSourceConfig(slug="INFY", consolidated=True)
    assert standalone.url == "https://www.screener.in/company/INFY/"
    assert consolidated.url == "https://www.screener.in/company/INFY/consolidated/"


@pytest.mark.skipif(
    os.environ.get("RUN_SCREENER_LIVE") != "1",
    reason="opt-in live Screener fetch; set RUN_SCREENER_LIVE=1",
)
def test_live_infosys_consolidated_is_derived() -> None:
    source = ScreenerSource(ScreenerSourceConfig(slug="INFY", consolidated=True))
    try:
        result: ScreenerResult = source.fetch()
    except ScreenerFetchError as error:
        pytest.skip(f"Screener unreachable: {error}")
    assert result.derived is True
    assert result.cross_check_only is True
    assert result.observations
    for obs in result.observations:
        assert is_derived(obs) is True
        assert obs.accounting_basis is AccountingFramework.UNKNOWN
