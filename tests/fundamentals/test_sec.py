"""Slice 5 — SEC annual adapter (retrospective cross-check only).

Live test: fetches the Infosys FY25 20-F IFRS annual facts from SEC EDGAR under
fair-access limits and asserts they load onto the frozen ``Observation``
contract with IFRS basis, USD currency, and the 20-F filing date as knowledge
time. It also proves the batch is marked annual (not quarterly) and is excluded
from the Q1 evidence package by ``knowledge_time > Q1 cutoff``.

The EPS assertion reads the normalized DataFrame-derived value, guarding the
``edgartools`` rendered-table bug that shows per-share values as ``0.00``.

On network unavailability the test skips rather than failing spuriously.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.sec_source import (
    FY25_PERIOD_END,
    FY25_PERIOD_START,
    Q1_UPDATE_CUTOFF,
    SecAnnualResult,
    SecAnnualSource,
    SecConcept,
    SecFetchError,
    SecSourceConfig,
    is_annual,
    is_excluded_from_q1,
)

TEST_USER_AGENT = "EquityOS Research (mvpavan42@gmail.com)"
FY25_ACCESSION = "0000950170-25-091925"
FILING_DATE = datetime(2025, 7, 1, tzinfo=UTC)

# Confirmed FY25 IFRS values (US$ millions; EPS in US$), per bake-off §3c.
EXPECTED_NORMALIZED = {
    SecConcept.REVENUE.value: Decimal("19277"),
    SecConcept.OPERATING_PROFIT.value: Decimal("4071"),
    SecConcept.PROFIT_FOR_PERIOD.value: Decimal("3162"),
    SecConcept.BASIC_EPS.value: Decimal("0.76"),
}


@pytest.fixture(scope="module")
def result() -> SecAnnualResult:
    source = SecAnnualSource(SecSourceConfig(user_agent=TEST_USER_AGENT))
    try:
        return source.fetch()
    except SecFetchError as error:
        pytest.skip(f"SEC EDGAR unreachable: {error}")


def _by_concept(result: SecAnnualResult) -> dict[str, object]:
    return {obs.concept_qname: obs for obs in result.observations}


def test_loads_four_fy25_annual_facts(result: SecAnnualResult) -> None:
    observations = _by_concept(result)
    assert set(observations) == set(EXPECTED_NORMALIZED)
    for concept_qname, expected in EXPECTED_NORMALIZED.items():
        # normalized_value comes from the fact value (DataFrame path), not the
        # rendered table — this is what guards the EPS 0.00 display bug.
        assert observations[concept_qname].normalized_value == expected, concept_qname


def test_facts_carry_ifrs_basis_and_usd_currency(result: SecAnnualResult) -> None:
    for obs in result.observations:
        assert obs.accounting_basis is AccountingFramework.IFRS
        assert obs.currency == "USD"
        assert obs.scope is Scope.CONSOLIDATED


def test_knowledge_time_is_the_20f_filing_date(result: SecAnnualResult) -> None:
    assert result.knowledge_time == FILING_DATE
    for obs in result.observations:
        filed_at = obs.provenance.filed_at
        assert filed_at is not None
        assert (filed_at.year, filed_at.month) == (2025, 7)


def test_facts_are_marked_annual_not_quarterly(result: SecAnnualResult) -> None:
    for obs in result.observations:
        assert obs.period_type is PeriodType.DURATION
        assert obs.period_start == FY25_PERIOD_START
        assert obs.period_end == FY25_PERIOD_END
        # A full fiscal year, not a ~90-day quarter.
        assert (obs.period_end - obs.period_start).days > 300
        assert is_annual(obs) is True


def test_facts_are_excluded_from_q1_evidence(result: SecAnnualResult) -> None:
    assert result.cross_check_only is True
    assert result.excluded_from_q1 is True
    assert result.knowledge_time > Q1_UPDATE_CUTOFF
    assert Q1_UPDATE_CUTOFF == datetime(2024, 7, 18, tzinfo=UTC)
    for obs in result.observations:
        assert is_excluded_from_q1(obs) is True


def test_eps_dataframe_value_guards_render_bug(result: SecAnnualResult) -> None:
    eps = _by_concept(result)[SecConcept.BASIC_EPS.value]
    assert eps.normalized_value == Decimal("0.76")
    assert eps.normalized_value != Decimal("0.00")


def test_provenance_binds_accession_and_file_hash(result: SecAnnualResult) -> None:
    for obs in result.observations:
        provenance = obs.provenance
        assert provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
        assert provenance.context_ref is not None
        assert FY25_ACCESSION in provenance.context_ref
        assert obs.concept_qname in provenance.context_ref
        assert FY25_ACCESSION in provenance.source_id
        assert len(provenance.file_sha256) == 64
        assert all(char in "0123456789abcdef" for char in provenance.file_sha256)


def test_fy25_period_constants_are_a_full_year() -> None:
    assert FY25_PERIOD_START == date(2024, 4, 1)
    assert FY25_PERIOD_END == date(2025, 3, 31)
