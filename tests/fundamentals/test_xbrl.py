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
    ParseResult,
    XbrlParseError,
    parse_instance,
    parse_observations,
    select_observation,
)
from fundamentals.ingest.xbrl_source import NseXbrlSource, XbrlFetchError

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
# YTD period-labelling defect (multi-stock generalization, Q3 FY25)           #
# --------------------------------------------------------------------------- #
#
# All five Wave-1 NSE in-bse-fin filings (LAURUSLABS, MTARTECH, SONACOMS,
# THERMAX, TITAN) stamp the year-to-date context's <xbrli:period> with the
# QUARTER's own dates, identical to the quarter context — so selecting by
# <xbrli:period> alone matched BOTH the quarter and the cumulative YTD figure and
# failed closed for every material concept. The taxonomy still declares each
# context's true reporting period via DateOf{Start,End}OfReportingPeriod, which
# the parser honours to disambiguate them.

YTD_DEFECT = FIXTURES / "synthetic_ytd_period_defect_q3fy25_consolidated.xml"
BASIC_EPS_CONTINUING = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"


def test_ytd_defect_reperiodises_the_ytd_context_from_the_declared_period() -> None:
    observations = _parse(YTD_DEFECT, "nse-indas-xbrl-consolidated")
    revenue_obs = [obs for obs in observations if obs.concept_qname == REVENUE]
    periods = {(obs.period_start, obs.period_end): obs.normalized_value for obs in revenue_obs}

    # The quarter keeps its period; the YTD is corrected from the declared period
    # (2024-04-01..2024-12-31), so the two no longer collide on the quarter key.
    assert periods[(Q3_START, Q3_END)] == Decimal("17740")
    assert periods[(NINE_MONTH_START, NINE_MONTH_END)] == Decimal("45540")


def test_ytd_defect_selects_the_quarter_and_rejects_the_ytd_distractor() -> None:
    observations = _parse(YTD_DEFECT, "nse-indas-xbrl-consolidated")

    revenue = _select_quarter(observations, REVENUE, Q3_START, Q3_END)
    profit = _select_quarter(observations, PROFIT_LOSS_FOR_PERIOD, Q3_START, Q3_END)
    eps = _select_quarter(observations, BASIC_EPS_CONTINUING, Q3_START, Q3_END)

    assert revenue.normalized_value == Decimal("17740")  # not the YTD 45,540
    assert revenue.context_ref == "OneD"
    assert profit.normalized_value == Decimal("1047")  # not the YTD 2,466
    assert eps.normalized_value == Decimal("11.80")  # not the YTD 27.80

    # The YTD figure is still available at its true (declared) nine-month period.
    ytd_revenue = _select_quarter(observations, REVENUE, NINE_MONTH_START, NINE_MONTH_END)
    assert ytd_revenue.normalized_value == Decimal("45540")
    assert ytd_revenue.context_ref == "FourD"


def test_ytd_defect_every_material_concept_resolves_to_one_quarter_match() -> None:
    observations = _parse(YTD_DEFECT, "nse-indas-xbrl-consolidated")
    for concept in (REVENUE, PROFIT_LOSS_FOR_PERIOD, BASIC_EPS_CONTINUING):
        # Exactly one quarter match: no FactSelectionError, no YTD ambiguity.
        selected = _select_quarter(observations, concept, Q3_START, Q3_END)
        assert selected.period_start == Q3_START
        assert selected.period_end == Q3_END


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
# Dimensionless units and per-fact degradation                                #
# --------------------------------------------------------------------------- #
#
# The live 5-stock run surfaced this: Laurus Labs and Titan report EPS/ratio
# facts under ``xbrli:pure``. The parser used to raise on any non-monetary,
# non-per-share measure, so a single ``pure`` fact aborted the whole instance
# and blocked every other fact. These suites pin that ``pure`` and ``shares``
# now parse, and that an unknown unit degrades to a rejection rather than an
# abort (still failing closed for a required concept).

DIMENSIONLESS_UNITS = FIXTURES / "synthetic_dimensionless_units.xml"

BASIC_EPS = "in-bse-fin:BasicEPS"
SHARE_COUNT = "in-bse-fin:NumberOfShares"
ODD_RATIO = "in-bse-fin:CurrentRatio"


def _parse_dimensionless(required_concepts: frozenset[str] = frozenset()) -> ParseResult:
    xml_bytes = DIMENSIONLESS_UNITS.read_bytes()
    return parse_instance(
        xml_bytes,
        source_id="nse-indas-xbrl-consolidated",
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        retrieved_at=_RETRIEVED_AT,
        required_concepts=required_concepts,
    )


def test_pure_unit_eps_parses_as_dimensionless_ratio() -> None:
    result = _parse_dimensionless()
    eps = next(obs for obs in result.observations if obs.concept_qname == BASIC_EPS)
    assert eps.normalized_value == Decimal("9.28")
    assert eps.normalized_unit == "pure"
    assert eps.currency is None  # a pure ratio is not INR crore
    assert eps.scale == 1


def test_shares_unit_parses_as_dimensionless_count() -> None:
    result = _parse_dimensionless()
    shares = next(obs for obs in result.observations if obs.concept_qname == SHARE_COUNT)
    assert shares.normalized_value == Decimal("538900000")
    assert shares.normalized_unit == "shares"
    assert shares.currency is None
    assert shares.scale == 1


def test_one_odd_unit_does_not_abort_the_whole_instance() -> None:
    result = _parse_dimensionless()
    # The monetary, pure and shares facts all survive despite the odd unit.
    concepts = {obs.concept_qname for obs in result.observations}
    assert PROFIT_LOSS_FOR_PERIOD in concepts
    assert BASIC_EPS in concepts
    assert SHARE_COUNT in concepts
    # The odd unit degrades to a single recorded rejection, not an abort.
    assert ODD_RATIO not in concepts
    odd_rejections = [rej for rej in result.rejections if rej.concept_qname == ODD_RATIO]
    assert len(odd_rejections) == 1
    assert "xbrli:widget" in odd_rejections[0].reason


def test_required_concept_with_unparseable_unit_fails_closed() -> None:
    with pytest.raises(XbrlParseError):
        _parse_dimensionless(frozenset({ODD_RATIO}))


def test_infy_eps_still_parses_as_inr_per_share() -> None:
    observations = _parse(Q1_CONSOLIDATED, "nse-indas-xbrl-consolidated")
    eps = _select_quarter(
        observations,
        "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        Q1_START,
        Q1_END,
    )
    assert eps.normalized_value == Decimal("15.38")
    assert eps.normalized_unit == "INR per share"
    assert eps.currency == "INR"
    assert eps.scale == 1


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


# --------------------------------------------------------------------------- #
# Issuer-rename verification (ETERNAL / fmr ZOMATO): ISIN-anchored + alias      #
# --------------------------------------------------------------------------- #
#
# The Q3 FY25 NSE XBRL for Eternal was filed (Jan-2025) while the company was
# still Zomato, so its context entity identifier is NSESymbol="ZOMATO"; but
# ``financial_results`` now keys the row under the current symbol "ETERNAL",
# carrying the rename-stable ``isin`` INE758T01015 (the old symbol returns 0
# rows). The guard must accept the renamed issuer via the stable ISIN (or a
# configured alias) yet still reject a filing that genuinely belongs to a
# different company.

_FIN_NS = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
_ETERNAL_ISIN = "INE758T01015"


def _entity_instance(symbol: str, start: date, end: date) -> bytes:
    """A minimal consolidated Ind AS instance whose context entity is ``symbol``."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        f'    xmlns:in-bse-fin="{_FIN_NS}">\n'
        '  <xbrli:context id="OneD">\n'
        "    <xbrli:entity><xbrli:identifier "
        f'scheme="http://www.nseindia.com/NSESymbol">{symbol}</xbrli:identifier></xbrli:entity>\n'
        f"    <xbrli:period><xbrli:startDate>{start.isoformat()}</xbrli:startDate>"
        f"<xbrli:endDate>{end.isoformat()}</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="OneD">'
        "Consolidated</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        "</xbrli:xbrl>\n"
    ).encode()


def test_issuer_rename_verifies_via_isin_registry(tmp_path: Path) -> None:
    # As-filed entity is ZOMATO; the rename-stable ISIN from the row authorises it.
    source = NseXbrlSource(tmp_path, symbol="ETERNAL", retry_backoff_seconds=0.0)
    source._verify(
        _entity_instance("ZOMATO", Q3_START, Q3_END),
        from_date=Q3_START,
        to_date=Q3_END,
        isin=_ETERNAL_ISIN,
    )


def test_issuer_rename_verifies_via_injected_alias(tmp_path: Path) -> None:
    # A caller-injected alias set accepts the as-filed symbol (case-insensitive),
    # independent of the ISIN registry.
    source = NseXbrlSource(
        tmp_path, symbol="ETERNAL", accepted_entity_ids=("zomato",), retry_backoff_seconds=0.0
    )
    source._verify(
        _entity_instance("ZOMATO", Q3_START, Q3_END),
        from_date=Q3_START,
        to_date=Q3_END,
        isin=None,
    )


def test_wrong_company_rejected_even_with_known_isin(tmp_path: Path) -> None:
    # The ISIN authorises only ZOMATO, never a genuinely different company.
    source = NseXbrlSource(tmp_path, symbol="ETERNAL", retry_backoff_seconds=0.0)
    with pytest.raises(XbrlFetchError, match="does not match requested issuer"):
        source._verify(
            _entity_instance("RELIANCE", Q3_START, Q3_END),
            from_date=Q3_START,
            to_date=Q3_END,
            isin=_ETERNAL_ISIN,
        )


def test_unknown_isin_and_symbol_mismatch_fails_closed(tmp_path: Path) -> None:
    # An unrecognised ISIN with no configured alias must fail closed (no silent pass).
    source = NseXbrlSource(tmp_path, symbol="ETERNAL", retry_backoff_seconds=0.0)
    with pytest.raises(XbrlFetchError, match="does not match requested issuer"):
        source._verify(
            _entity_instance("ZOMATO", Q3_START, Q3_END),
            from_date=Q3_START,
            to_date=Q3_END,
            isin="INE000000000",
        )


class _FakeNseClient:
    """A context-manager NSE stand-in returning a canned row + downloaded file."""

    def __init__(self, rows: list[dict[str, str]], file_bytes: bytes) -> None:
        self._rows = rows
        self._file_bytes = file_bytes

    def __enter__(self) -> _FakeNseClient:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def financial_results(self, **_kwargs: object) -> list[dict[str, str]]:
        return self._rows

    def download_document(self, url: str, folder: Path) -> str:
        path = Path(folder) / "filing.xml"
        path.write_bytes(self._file_bytes)
        return str(path)


def _consolidated_row(isin: str) -> dict[str, str]:
    """A financial_results row shaped like NSE's, keyed under the current symbol."""
    return {
        "fromDate": "01-Oct-2024",
        "toDate": "31-Dec-2024",
        "consolidated": "Consolidated",
        "indAs": "Ind-AS New",
        "xbrl": "https://nsearchives.example/filing.xml",
        "isin": isin,
        "relatingTo": "Third Quarter",
        "broadCastDate": "20-Jan-2025 18:28:59",
    }


def test_fetch_verifies_renamed_issuer_via_row_isin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # End-to-end: request ETERNAL, NSE returns the row (isin INE758T01015) whose
    # XBRL was filed as ZOMATO — the fetch verifies and stamps the retrieval.
    fake = _FakeNseClient(
        [_consolidated_row(_ETERNAL_ISIN)], _entity_instance("ZOMATO", Q3_START, Q3_END)
    )
    monkeypatch.setattr("fundamentals.ingest.xbrl_source.NSE", lambda *_a, **_k: fake)
    source = NseXbrlSource(tmp_path, symbol="ETERNAL")
    retrieval = source.fetch_consolidated_quarter(from_date=Q3_START, to_date=Q3_END)
    assert retrieval.symbol == "ETERNAL"
    assert retrieval.consolidated is True


def test_fetch_rejects_wrong_company_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # End-to-end: the row is ETERNAL's, but the downloaded XBRL belongs to another
    # company — the fetch must fail closed rather than build facts from it.
    fake = _FakeNseClient(
        [_consolidated_row(_ETERNAL_ISIN)], _entity_instance("RELIANCE", Q3_START, Q3_END)
    )
    monkeypatch.setattr("fundamentals.ingest.xbrl_source.NSE", lambda *_a, **_k: fake)
    source = NseXbrlSource(tmp_path, symbol="ETERNAL")
    with pytest.raises(XbrlFetchError, match="does not match requested issuer"):
        source.fetch_consolidated_quarter(from_date=Q3_START, to_date=Q3_END)
