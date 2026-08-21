"""Slice 1 acceptance tests: context-aware NSE Ind AS XBRL parsing.

Two deterministic suites run against hand-built synthetic fixtures (the real NSE
bytes are held gitignored and never committed):

* **Q1 FY25** — pins the consolidated ProfitLossForPeriod to 6,374 Cr bound to
  the Apr-Jun 2024 duration context, and proves the four distractors
  (standalone, segment-dimensioned revenue, prior-year, attributable-to-owners)
  are not selected as the consolidated quarter fact.
* **Q3 FY25** — the trap Q1 cannot exercise: within one consolidated file,
  ProfitLossForPeriod appears under quarter / nine-month YTD / prior-year
  contexts; the parser must pick the quarter (6,822 Cr) and reject the rest.

A separate opt-in live test (``RUN_NSE_LIVE=1``) re-fetches the real filing and
asserts its sha256 matches the value re-pinned in the oracle manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.observation import Observation, PeriodType, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    parse_observations,
    select_observation,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
Q1_CONSOLIDATED = FIXTURES / "synthetic_q1_fy25_consolidated.xml"
Q1_STANDALONE = FIXTURES / "synthetic_q1_fy25_standalone.xml"
Q3_CONSOLIDATED = FIXTURES / "synthetic_q3_fy25_consolidated.xml"
MANIFEST = FIXTURES / "infy_q1_fy25_manifest.json"

REAL_CONSOLIDATED_SHA256 = "ef270eb3c5513fd033008c67d28310f325da95eec1d445923b924b6125c62419"

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

PROFIT_LOSS_FOR_PERIOD = "in-bse-fin:ProfitLossForPeriod"
REVENUE = "in-bse-fin:RevenueFromOperations"
ATTRIBUTABLE_TO_OWNERS = "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
NON_CONTROLLING = "in-bse-fin:ProfitOrLossAttributableToNonControllingInterests"
INCOME = "in-bse-fin:Income"
EXPENSES = "in-bse-fin:Expenses"
PROFIT_BEFORE_TAX = "in-bse-fin:ProfitBeforeTax"

Q1_START = date(2024, 4, 1)
Q1_END = date(2024, 6, 30)
Q3_START = date(2024, 10, 1)
Q3_END = date(2024, 12, 31)
NINE_MONTH_START = date(2024, 4, 1)
NINE_MONTH_END = date(2024, 12, 31)
PRIOR_YEAR_Q3_START = date(2023, 10, 1)
PRIOR_YEAR_Q3_END = date(2023, 12, 31)


def _parse(path: Path, source_id: str) -> tuple[Observation, ...]:
    """Parse a fixture instance, stamping provenance with the fixture's own sha."""
    xml_bytes = path.read_bytes()
    return parse_observations(
        xml_bytes,
        source_id=source_id,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        retrieved_at=_RETRIEVED_AT,
    )


def _select_quarter(
    observations: tuple[Observation, ...],
    concept: str,
    start: date,
    end: date,
    *,
    scope: Scope = Scope.CONSOLIDATED,
) -> Observation:
    return select_observation(
        observations,
        concept_qname=concept,
        scope=scope,
        period_type=PeriodType.DURATION,
        period_start=start,
        period_end=end,
    )


# --------------------------------------------------------------------------- #
# Q1 FY25 acceptance                                                          #
# --------------------------------------------------------------------------- #


def test_q1_consolidated_profit_for_period_is_6374_bound_to_apr_jun_2024() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    profit = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END)

    assert profit.normalized_value == Decimal("6374")
    assert profit.normalized_unit == "INR crore"
    assert profit.scope is Scope.CONSOLIDATED
    assert profit.period_type is PeriodType.DURATION
    assert profit.period_start == Q1_START
    assert profit.period_end == Q1_END
    assert profit.context_ref == "OneD"
    assert profit.provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
    assert profit.provenance.context_ref == "OneD"
    assert profit.provenance.file_sha256


def test_q1_consolidated_revenue_is_39315() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    revenue = _select_quarter(observations, REVENUE, Q1_START, Q1_END)
    assert revenue.normalized_value == Decimal("39315")


def test_q1_cross_foot_identities_hold() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    income = _select_quarter(observations, INCOME, Q1_START, Q1_END).normalized_value
    expenses = _select_quarter(observations, EXPENSES, Q1_START, Q1_END).normalized_value
    pbt = _select_quarter(observations, PROFIT_BEFORE_TAX, Q1_START, Q1_END).normalized_value
    profit = _select_quarter(
        observations, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END
    ).normalized_value
    owners = _select_quarter(
        observations, ATTRIBUTABLE_TO_OWNERS, Q1_START, Q1_END
    ).normalized_value
    nci = _select_quarter(observations, NON_CONTROLLING, Q1_START, Q1_END).normalized_value

    # PBT = Total income - Total expenses
    assert pbt == income - expenses == Decimal("9021")
    # Profit for the period = attributable to owners + non-controlling interests
    assert profit == owners + nci == Decimal("6374")


def test_q1_standalone_distractor_not_selected_as_consolidated() -> None:
    consolidated = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    standalone = _parse(Q1_STANDALONE, "nse-indas-xbrl-standalone")
    # Both files reuse the SAME OneD context id; only file-level scope separates them.
    combined = consolidated + standalone

    profit = _select_quarter(combined, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END)
    assert profit.normalized_value == Decimal("6374")  # not the standalone 5,768

    standalone_profit = _select_quarter(
        combined, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END, scope=Scope.STANDALONE
    )
    assert standalone_profit.normalized_value == Decimal("5768")
    assert standalone_profit.context_ref == "OneD"


def test_q1_segment_dimensioned_revenue_not_selected() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    # The same RevenueFromOperations element appears segment-free (OneD) and
    # under a segment-dimensioned context.
    revenue_obs = [obs for obs in observations if obs.concept_qname == REVENUE]
    assert len(revenue_obs) == 2
    assert any(obs.dimensions for obs in revenue_obs)

    # A segment-free selection returns the 39,315 total, never the 1,316 segment.
    revenue = _select_quarter(observations, REVENUE, Q1_START, Q1_END)
    assert revenue.normalized_value == Decimal("39315")
    assert revenue.dimensions == ()


def test_q1_attributable_to_owners_is_a_distinct_concept() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    profit = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END)
    owners = _select_quarter(observations, ATTRIBUTABLE_TO_OWNERS, Q1_START, Q1_END)

    assert profit.normalized_value == Decimal("6374")
    assert owners.normalized_value == Decimal("6368")
    assert profit.concept_qname != owners.concept_qname


def test_q1_file_carries_no_prior_year_context() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    for obs in observations:
        if obs.period_start is not None:
            assert obs.period_start.year == 2024
        if obs.period_instant is not None:
            assert obs.period_instant.year == 2024


def test_q1_parser_output_matches_oracle_manifest() -> None:
    payload = json.loads(MANIFEST.read_text())
    by_concept = {fact["concept_qname"]: fact for fact in payload["facts"]}
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")

    for concept, entry in by_concept.items():
        selected = _select_quarter(observations, concept, Q1_START, Q1_END)
        assert selected.normalized_value == Decimal(entry["normalized_value"]), concept
        assert selected.raw_value.startswith(entry["raw_value"])
        assert selected.scope.value == entry["scope"]


# --------------------------------------------------------------------------- #
# Q3 FY25 context-selection (the real Gotcha-1)                               #
# --------------------------------------------------------------------------- #


def test_q3_parses_three_profit_contexts() -> None:
    observations = _parse(Q3_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    profit_obs = [obs for obs in observations if obs.concept_qname == PROFIT_LOSS_FOR_PERIOD]
    assert len(profit_obs) == 3  # quarter, nine-month YTD, prior-year quarter


def test_q3_selects_quarter_6822_and_rejects_ytd_and_prior_year() -> None:
    observations = _parse(Q3_CONSOLIDATED, "nse-indas-xbrl-consolidated")

    quarter = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q3_START, Q3_END)
    assert quarter.normalized_value == Decimal("6822")
    assert quarter.period_start == Q3_START
    assert quarter.period_end == Q3_END

    ytd = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, NINE_MONTH_START, NINE_MONTH_END)
    prior_year = _select_quarter(
        observations, PROFIT_LOSS_FOR_PERIOD, PRIOR_YEAR_Q3_START, PRIOR_YEAR_Q3_END
    )
    # The distractors exist and are distinct — the quarter value is none of them.
    assert ytd.normalized_value == Decimal("19973")
    assert prior_year.normalized_value == Decimal("6106")
    assert quarter.normalized_value not in {ytd.normalized_value, prior_year.normalized_value}


def test_q3_attributable_to_owners_6358_not_confused_with_profit_6822() -> None:
    observations = _parse(Q3_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    profit = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q3_START, Q3_END)
    owners = _select_quarter(observations, ATTRIBUTABLE_TO_OWNERS, Q3_START, Q3_END)

    assert profit.normalized_value == Decimal("6822")
    assert owners.normalized_value == Decimal("6358")
    assert profit.concept_qname != owners.concept_qname


# --------------------------------------------------------------------------- #
# Fail-closed selection                                                       #
# --------------------------------------------------------------------------- #


def test_selection_fails_closed_when_no_match() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    with pytest.raises(FactSelectionError):
        _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, date(2023, 4, 1), date(2023, 6, 30))


def test_selection_fails_closed_when_period_omitted_is_ambiguous() -> None:
    observations = _parse(Q3_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    # Without a period key, the three ProfitLossForPeriod contexts are ambiguous.
    with pytest.raises(FactSelectionError):
        select_observation(
            observations,
            concept_qname=PROFIT_LOSS_FOR_PERIOD,
            scope=Scope.CONSOLIDATED,
            period_type=PeriodType.DURATION,
        )


# --------------------------------------------------------------------------- #
# Opt-in live NSE ingestion (skipped by default; polite, single filing)       #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("RUN_NSE_LIVE") != "1",
    reason="live NSE fetch is opt-in; set RUN_NSE_LIVE=1 to run",
)
def test_live_fetch_matches_pinned_sha(tmp_path: Path) -> None:
    from fundamentals.ingest.xbrl_source import NseXbrlSource

    source = NseXbrlSource(tmp_path, symbol="INFY")
    retrieval = source.fetch_consolidated_quarter(from_date=Q1_START, to_date=Q1_END)

    assert retrieval.file_sha256 == REAL_CONSOLIDATED_SHA256
    assert retrieval.consolidated is True

    observations = _parse(retrieval.local_path, retrieval.source_id)
    profit = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q1_START, Q1_END)
    assert profit.normalized_value == Decimal("6374")
