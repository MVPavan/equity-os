"""Tijori adapter — DERIVED quarterly P&L cross-check.

Deterministic tests parse a committed synthetic Tijori-shaped JSON fixture and
assert the resulting observations are flagged derived (``source_id="tijori"``,
``accounting_basis`` UNKNOWN, ``tijori:`` concept prefix), that annual columns
are excluded, and that missing credentials raise a *skippable* typed error. An
opt-in ``RUN_TIJORI_LIVE`` test exercises the real authenticated fetch only when
credentials are present in the environment.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.tijori_source import (
    SOURCE_ID,
    TijoriConcept,
    TijoriCredentials,
    TijoriCredentialsError,
    TijoriSource,
    TijoriSourceConfig,
    is_tijori_derived,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_tijori_pl.json"

# Two quarterly columns (Mar'26, Jun'26) x four mapped headline concepts.
_EXPECTED_QUARTER_COUNT = 8


@pytest.fixture(scope="module")
def observations() -> tuple:
    return TijoriSource.parse_pl_bytes(_FIXTURE.read_bytes())


def test_parses_only_quarterly_headline_observations(observations: tuple) -> None:
    assert len(observations) == _EXPECTED_QUARTER_COUNT
    # The annual Mar'25 column is excluded, so no full-year period appears.
    for obs in observations:
        assert obs.period_type is PeriodType.DURATION
        assert obs.period_start is not None and obs.period_end is not None
        assert (obs.period_end - obs.period_start).days < 100


def test_every_observation_is_flagged_derived(observations: tuple) -> None:
    for obs in observations:
        assert obs.provenance.source_id == SOURCE_ID
        assert obs.accounting_basis is AccountingFramework.UNKNOWN
        assert obs.concept_qname.startswith("tijori:")
        assert is_tijori_derived(obs) is True


def test_concepts_and_periods_are_the_two_quarters(observations: tuple) -> None:
    by_key = {(obs.concept_qname, obs.period_end): obs for obs in observations}
    expected_concepts = {c.value for c in TijoriConcept}
    got_concepts = {concept for concept, _ in by_key}
    assert got_concepts == expected_concepts
    expected_ends = {date(2026, 3, 31), date(2026, 6, 30)}
    assert {end for _, end in by_key} == expected_ends
    # Mar'26 quarter runs Jan-Mar 2026.
    sales_q4 = by_key[(TijoriConcept.SALES.value, date(2026, 3, 31))]
    assert sales_q4.period_start == date(2026, 1, 1)


def test_monetary_and_per_share_normalization(observations: tuple) -> None:
    by_key = {(obs.concept_qname, obs.period_end): obs for obs in observations}
    sales = by_key[(TijoriConcept.SALES.value, date(2026, 6, 30))]
    assert sales.raw_value == "48,500"
    assert sales.normalized_value == Decimal("48500")
    assert sales.normalized_unit == "INR crore"
    assert sales.currency == "INR"
    assert sales.scale == 10_000_000

    eps = by_key[(TijoriConcept.EPS.value, date(2026, 6, 30))]
    assert eps.normalized_value == Decimal("24.6")
    assert eps.normalized_unit == "INR"
    assert eps.scale == 1
    assert eps.decimals == 2


def test_provenance_binds_url_period_and_content_hash(observations: tuple) -> None:
    for obs in observations:
        prov = obs.provenance
        assert prov.anchor_type is SourceAnchorType.XBRL_CONTEXT
        assert prov.context_ref is not None
        assert "tijorifinance.com/company/infosys-limited" in prov.context_ref
        assert obs.concept_qname in prov.context_ref
        assert prov.filed_at is None  # derived aggregator: no filing-level anchor
        assert len(prov.file_sha256) == 64
        assert all(ch in "0123456789abcdef" for ch in prov.file_sha256)
    # One shared content hash for the whole payload.
    assert len({obs.provenance.file_sha256 for obs in observations}) == 1


def test_observations_use_consolidated_scope(observations: tuple) -> None:
    for obs in observations:
        assert obs.scope is Scope.CONSOLIDATED
        assert obs.entity_scheme == "tijori-slug"
        assert obs.entity_id == "infosys-limited"


def test_missing_credentials_raises_skippable_error() -> None:
    source = TijoriSource(TijoriSourceConfig())  # no credentials injected
    with pytest.raises(TijoriCredentialsError, match="credentials not provided"):
        source.fetch_pl("infosys-limited")


def test_missing_cell_is_skipped_not_emitted() -> None:
    # "Other Income" is unmapped and one cell is "-"; neither yields an
    # observation, so the count is unaffected by the missing marker.
    observations = TijoriSource.parse_pl_bytes(_FIXTURE.read_bytes())
    assert all("other_income" not in obs.concept_qname for obs in observations)
    assert len(observations) == _EXPECTED_QUARTER_COUNT


@pytest.mark.skipif(
    os.environ.get("RUN_TIJORI_LIVE") != "1"
    or not os.environ.get("TIJORI_EMAIL")
    or not os.environ.get("TIJORI_PASSWORD"),
    reason="live Tijori fetch is opt-in: set RUN_TIJORI_LIVE=1 + TIJORI_EMAIL/TIJORI_PASSWORD",
)
def test_live_fetch_returns_derived_observations() -> None:
    # Composition root reads env; the adapter itself never touches os.environ.
    credentials = TijoriCredentials(
        email=os.environ["TIJORI_EMAIL"],
        password=os.environ["TIJORI_PASSWORD"],
        session_cookie=os.environ.get("TIJORI_SESSION_COOKIE"),
    )
    source = TijoriSource(TijoriSourceConfig(credentials=credentials))
    observations = source.fetch_pl("infosys-limited")
    assert observations
    for obs in observations:
        assert is_tijori_derived(obs)
