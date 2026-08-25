"""Fixture-only coverage for typed Tijori overview-section acquisition.

Every test parses committed bytes; no test opens a socket. The fixture mirrors
the owner's structure-only capture of TITAN's live overview page, including one
island the page does not publish, one malformed series point, one unaligned
custom-financial row, and drifted keys inside three different sections.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.tijori_overview import build_tijori_overview
from fundamentals.ingest.tijori_overview_common import reject_duplicate_anchors
from fundamentals.ingest.tijori_overview_models import (
    DOM_SECTION_ELEMENT_IDS,
    PRICE_RETURNS_SEMANTICS,
    REVENUE_MIX_ELEMENT_ID,
    REVERSE_DCF_EXCLUSION,
    SECTION_ISLAND_IDS,
    SECTION_SOURCE_IDS,
    TijoriCompanyDetailsSection,
    TijoriCorporateActionsSection,
    TijoriCustomFinancialsSection,
    TijoriMarketShareSection,
    TijoriOverviewIdentityError,
    TijoriOverviewSchemaError,
    TijoriOverviewSection,
    TijoriOverviewSectionAbsentError,
    TijoriOverviewSectionBase,
    TijoriOverviewSectionsAbsentError,
    TijoriOverviewSourceKind,
    TijoriPeersSection,
    TijoriPriceChartPeersSection,
    TijoriPriceReturnsSection,
    TijoriPriceSeriesSection,
    TijoriRatiosSection,
    TijoriRevenueMixSection,
    parse_section,
)
from fundamentals.ingest.tijori_tables import TijoriIslandStatus, TijoriParseError

_FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_tijori_overview.html"
_SLUG = "titan-company-limited"
_SYMBOL = "TITAN"
_COMPANY_ID = 81
_SOURCE_URL = f"https://www.tijorifinance.com/company/{_SLUG}/"
_RETRIEVED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)


def _page() -> bytes:
    """The committed synthetic overview page."""
    return _FIXTURE.read_bytes()


def _replace_island(island_id: str, body: str) -> bytes:
    """Rewrite one island body, keeping the rest of the page byte-identical."""
    pattern = re.compile(
        rf'(<script id="{re.escape(island_id)}" type="application/json">)(.*?)(</script>)',
        re.DOTALL,
    )
    # Every occurrence is rewritten: the fixture repeats is_auth the way the live
    # template does, and the repeats must stay identical to each other.
    page, count = pattern.subn(rf"\g<1>{body}\g<3>", _page().decode("utf-8"))
    assert count >= 1, f"island {island_id!r} not found in fixture"
    return page.encode("utf-8")


def _build(
    raw: bytes | None = None,
    *,
    section: TijoriOverviewSection | None = None,
    expected_symbol: str = _SYMBOL,
    expected_company_id: int = _COMPANY_ID,
) -> tuple[TijoriOverviewSectionBase, ...]:
    """Build overview sections from committed bytes with the verified identity."""
    return build_tijori_overview(
        _page() if raw is None else raw,
        slug=_SLUG,
        expected_symbol=expected_symbol,
        expected_company_id=expected_company_id,
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        section=section,
    )


def _one(section: TijoriOverviewSection, raw: bytes | None = None) -> Any:
    """Build exactly one requested section."""
    built = _build(raw, section=section)
    assert len(built) == 1
    return built[0]


def test_breadth_run_builds_every_published_section() -> None:
    """A default run builds one artifact per published island, in section order."""
    sections = _build()

    assert [built.section.value for built in sections] == [
        "corporate_actions",
        "ratios",
        "custom_financials",
        "market_share",
        "peers",
        "price_returns",
        "price_chart",
        "price_chart_peers",
        "company_details",
        "revenue_mix",
    ]


def test_the_page_renders_the_auth_island_twice_and_still_parses() -> None:
    """The live overview template repeats is_auth verbatim; that must not fail the run."""
    assert _page().decode("utf-8").count('<script id="is_auth"') == 2

    sections = _build()

    assert sections, "an identically repeated island must collapse, not refuse the page"


def test_identity_is_bound_to_both_islands_the_page_publishes() -> None:
    """The overview page corroborates identity twice, and both are recorded."""
    metadata = _build()[0].metadata

    assert metadata.identity_island_ids == ("company_details_data", "companyId")
    assert metadata.company_id == _COMPANY_ID
    assert metadata.symbol == _SYMBOL
    assert metadata.company_status == "Active"
    assert metadata.is_banking is False
    assert metadata.access.plan_tier == "free"
    # The overview page's lock island is overview_locks, and the recorded id must
    # be the island that was actually read.
    assert metadata.access.locks_island_id == "overview_locks"


@pytest.mark.parametrize(
    ("expected_symbol", "expected_company_id", "match"),
    [
        ("THERMAX", _COMPANY_ID, "requested symbol 'THERMAX'"),
        (_SYMBOL, 301, "requested company ID 301"),
    ],
)
def test_identity_mismatch_refuses_the_response(
    expected_symbol: str, expected_company_id: int, match: str
) -> None:
    """A page served for another issuer is refused before any section is built."""
    with pytest.raises(TijoriOverviewIdentityError, match=match):
        _build(expected_symbol=expected_symbol, expected_company_id=expected_company_id)


@pytest.mark.parametrize("body", ["4242", '"81"'])
def test_company_id_island_must_agree_with_the_identity_island(body: str) -> None:
    """A present-but-disagreeing companyId island is drift on an identity marker."""
    with pytest.raises(TijoriOverviewIdentityError, match="companyId"):
        _build(_replace_island("companyId", body))


def test_unauthenticated_page_is_refused() -> None:
    """Acquisition never proceeds against a logged-out render."""
    with pytest.raises(TijoriParseError, match="not authenticated"):
        _build(_replace_island("is_auth", "false"))


def test_absent_island_is_a_recorded_outcome_for_a_breadth_run() -> None:
    """An island the page does not publish is metadata, not a failed run."""
    sections = _build()
    outcomes = {outcome.section: outcome for outcome in sections[0].metadata.section_outcomes}

    assert len(outcomes) == len(TijoriOverviewSection)
    intraday = outcomes[TijoriOverviewSection.INTRADAY_PRICE]
    assert intraday.status is TijoriIslandStatus.ABSENT
    assert intraday.island_id == "intraday_price"
    assert intraday.detail == "island not present on the page"
    assert TijoriOverviewSection.INTRADAY_PRICE not in {built.section for built in sections}


def test_explicitly_requested_absent_section_is_a_typed_refusal() -> None:
    """Asking for a section the page lacks is an error, not a silent empty file."""
    with pytest.raises(TijoriOverviewSectionAbsentError, match="'intraday_price' is absent"):
        _build(section=TijoriOverviewSection.INTRADAY_PRICE)


def test_null_island_is_recorded_as_absent_with_its_own_reason() -> None:
    """A JSON-null island and a missing island never serialize alike."""
    raw = _replace_island("ms-charts", "null")
    outcomes = {outcome.section: outcome for outcome in _build(raw)[0].metadata.section_outcomes}

    market_share = outcomes[TijoriOverviewSection.MARKET_SHARE]
    assert market_share.status is TijoriIslandStatus.ABSENT
    assert market_share.detail == "island published as JSON null"
    with pytest.raises(TijoriOverviewSectionAbsentError, match="JSON null"):
        _build(raw, section=TijoriOverviewSection.MARKET_SHARE)


def test_unparseable_island_is_recorded_and_refused_when_requested() -> None:
    """An undecodable island is neither parsed nor confused with an absent one."""
    raw = _replace_island("price_returns", "{not json,}")
    outcomes = {outcome.section: outcome for outcome in _build(raw)[0].metadata.section_outcomes}

    price_returns = outcomes[TijoriOverviewSection.PRICE_RETURNS]
    assert price_returns.status is TijoriIslandStatus.UNPARSEABLE
    assert price_returns.detail
    with pytest.raises(TijoriOverviewSectionAbsentError, match="unparseable"):
        _build(raw, section=TijoriOverviewSection.PRICE_RETURNS)


def test_a_page_with_only_its_identity_header_is_not_an_acquisition() -> None:
    """Writing just the header the caller already knew would look like success."""
    stripped = _page().decode("utf-8")
    for island_id in (
        "corporate_actions",
        "ratios_table",
        "custom_fin_table",
        "ms-charts",
        "peers_table_data",
        "price_returns",
        "price_chart",
        "price_chart_peers",
    ):
        stripped = re.sub(
            rf'<script id="{re.escape(island_id)}" type="application/json">.*?</script>',
            "",
            stripped,
            flags=re.DOTALL,
        )
    # The revenue mix is a data section too, so stripping only the islands would
    # leave one behind and the page would no longer be header-only.
    stripped = re.sub(r'<section id="revenuemix">.*?</section>', "", stripped, flags=re.DOTALL)

    with pytest.raises(TijoriOverviewSectionsAbsentError, match="no modeled data section"):
        _build(stripped.encode("utf-8"))

    # The identity header alone is still buildable when it is asked for by name.
    assert _one(TijoriOverviewSection.COMPANY_DETAILS, stripped.encode("utf-8")) is not None


def test_corporate_actions_group_by_type_and_preserve_drifted_keys() -> None:
    """Actions keep their source lexemes, their ISO reading, and unmodeled keys."""
    section = _one(TijoriOverviewSection.CORPORATE_ACTIONS)
    assert isinstance(section, TijoriCorporateActionsSection)

    assert section.empty_action_types == ("Bonus", "Rights")
    assert section.action_types == ("Bonus", "Dividend", "Rights", "Split")
    dividends = [action for action in section.actions if action.action_type == "Dividend"]
    assert dividends[0].event_details == "Dividend of Rs.15 per share"
    assert dividends[0].ex_date == "2026-07-09"
    assert dividends[0].ex_date_iso is not None
    assert dividends[0].ex_date_iso.isoformat() == "2026-07-09"
    assert dividends[0].event_date_iso == datetime(2026, 7, 9, tzinfo=UTC)
    assert dividends[1].unmodeled_fields_json == '{"record_date": "2025-07-09"}'
    # A date lexeme Tijori did not publish in ISO form keeps its text and derives
    # nothing, rather than being coerced into a wrong date.
    unparsed = [action for action in section.actions if action.ex_date == "not-a-date"]
    assert len(unparsed) == 1
    assert unparsed[0].ex_date_iso is None
    assert unparsed[0].event_date_iso is None


def test_corporate_actions_keep_an_unmodeled_group_verbatim() -> None:
    """An action type published in an unmodeled shape is retained, not dropped."""
    raw = _replace_island(
        "corporate_actions", '{"Bonus": [], "Dividend": "not-a-list", "Split": []}'
    )
    section = _one(TijoriOverviewSection.CORPORATE_ACTIONS, raw)
    assert isinstance(section, TijoriCorporateActionsSection)

    assert section.actions == ()
    assert section.unmodeled_fields_json == '{"Dividend": "not-a-list"}'


def test_ratios_read_decimals_and_keep_placeholder_lexemes() -> None:
    """A ratio value reads as Decimal when it is numeric, and always keeps its text."""
    section = _one(TijoriOverviewSection.RATIOS)
    assert isinstance(section, TijoriRatiosSection)

    by_name = {ratio.name: ratio for ratio in section.ratios}
    assert by_name["mcap"].amount.value == Decimal("449713.00")
    assert by_name["mcap"].amount.raw_text == "449713.00"
    assert by_name["mcap"].unit == "Cr"
    assert by_name["mcap"].source_metric_id == 2022
    assert by_name["div_yield"].amount.value is None
    assert by_name["div_yield"].amount.raw_text == "-"


def test_duplicate_element_addresses_are_fatal() -> None:
    """Two elements sharing one address would make every selection ambiguous."""
    raw = _replace_island(
        "ratios_table",
        '[{"name":"pe","value":"10"},{"name":"pe","value":"11"}]',
    )
    with pytest.raises(TijoriOverviewSchemaError, match="duplicate element paths: pe"):
        _one(TijoriOverviewSection.RATIOS, raw)


def test_custom_financial_rows_align_to_report_dates_or_are_quarantined() -> None:
    """An unalignable KPI row keeps its lexemes instead of guessing a period."""
    section = _one(TijoriOverviewSection.CUSTOM_FINANCIALS)
    assert isinstance(section, TijoriCustomFinancialsSection)

    assert [block.column for block in section.blocks] == ["bs_s_d", "bs_c_d"]
    standalone = section.blocks[0]
    assert standalone.report_dates == ("Mar 2017", "Mar 2018")
    assert standalone.rows[0].label == "Stores"
    assert [cell.value for cell in standalone.rows[0].cells] == [Decimal(2200), Decimal(2450)]
    consolidated = section.blocks[1]
    assert consolidated.cardinality_mismatch_rows == ("Stores",)
    quarantined = consolidated.rows[0]
    assert quarantined.cells == ()
    assert quarantined.unaligned_raw_values == ("2200",)
    # Thousands commas read through the shared Tijori cell rule.
    gold = consolidated.rows[1]
    assert [cell.value for cell in gold.cells] == [Decimal(1234), Decimal(5678)]
    assert [cell.raw_text for cell in gold.cells] == ["1,234", "5,678"]
    assert gold.unmodeled_fields_json == '{"unit": "INR/gm"}'


def test_market_share_charts_carry_series_and_one_series_anchor() -> None:
    """A chart's latest reading is anchored; its series is anchored once, as a series."""
    section = _one(TijoriOverviewSection.MARKET_SHARE)
    assert isinstance(section, TijoriMarketShareSection)

    jewellery = section.charts[0]
    assert jewellery.name == "Jewellery  Segment Market Share"
    assert jewellery.chart_id == 574
    assert jewellery.unit == "%"
    assert jewellery.latest_value.value == Decimal("8.5")
    assert jewellery.sample_size_json is None
    assert len(jewellery.series) == 3
    # Tijori publishes market-share stamps as whole floats; they read as epoch ms.
    assert jewellery.series[0].timestamp_ms == 1519862400000
    assert jewellery.series[0].timestamp_iso == datetime(2018, 3, 1, tzinfo=UTC)
    assert jewellery.series[0].value == Decimal("6.1")
    assert jewellery.series_provenance.column_label == "series"
    assert jewellery.series_provenance.row_label == jewellery.name


def test_peers_align_by_declared_column_and_name_absent_metrics() -> None:
    """A peer that omits a column is recorded as missing it, never as a null value."""
    section = _one(TijoriOverviewSection.PEERS)
    assert isinstance(section, TijoriPeersSection)

    assert [column.name for column in section.columns] == ["Latest Price", "PE", "Market Capital"]
    titan = section.rows[0]
    assert titan.slug == _SLUG
    assert [cell.value for cell in titan.cells] == [
        Decimal("5079.0"),
        Decimal("78.08"),
        Decimal("449713.0"),
    ]
    assert titan.missing_columns == ()
    assert section.rows[1].unmodeled_fields_json == '{"Promoter": "60.6"}'
    third = section.rows[2]
    assert third.missing_columns == ("PE",)
    assert third.cells[1].value is None
    assert third.cells[1].raw_text == ""


def test_peers_refuse_to_guess_which_block_is_which() -> None:
    """The columns and rows blocks are told apart by key, never by position."""
    raw = _replace_island("peers_table_data", '[{"columns":[{"name":"PE"}]}]')
    with pytest.raises(TijoriOverviewSchemaError, match="exactly one 'columns' block"):
        _one(TijoriOverviewSection.PEERS, raw)


def test_price_returns_are_addressed_by_window() -> None:
    """Every trailing window keeps its own anchored reading."""
    section = _one(TijoriOverviewSection.PRICE_RETURNS)
    assert isinstance(section, TijoriPriceReturnsSection)

    by_window = {entry.window: entry.amount for entry in section.returns}
    assert by_window["1d"].value == Decimal("-0.14")
    assert by_window["max"].value == Decimal("12255.41")
    assert by_window["1d"].provenance.row_label == "1d"


def test_price_returns_artifact_states_its_as_of_retrieval_semantics() -> None:
    """The note ships in the artifact because that is where a reader compares it.

    These island values are server-computed and frozen at retrieval, while the
    page header recomputes its own percentage from the live tick — so a header
    comparison that looks like a mismatch usually is not one.
    """
    section = _one(TijoriOverviewSection.PRICE_RETURNS)
    assert isinstance(section, TijoriPriceReturnsSection)

    assert section.semantics_note == PRICE_RETURNS_SEMANTICS
    assert "retrieved_at" in section.semantics_note
    assert '"semantics_note"' in section.model_dump_json()


def test_reverse_dcf_is_a_documented_exclusion_not_a_missing_section() -> None:
    """Its numbers are computed in the browser, so there is nothing to acquire.

    Pinning the exclusion in a test keeps a future reader from "fixing" the gap
    by scraping the rendered widget, which would record a viewer's slider
    positions as an issuer fact.
    """
    assert not any("dcf" in section.value for section in TijoriOverviewSection)
    assert not any("dcf" in island_id for island_id in SECTION_ISLAND_IDS.values())
    assert "reverse-dcf.js" in REVERSE_DCF_EXCLUSION
    assert "client-side" in REVERSE_DCF_EXCLUSION


def test_price_series_keeps_a_malformed_point_instead_of_dropping_it() -> None:
    """A point whose source shape is not [timestamp, value] survives with nulls."""
    section = _one(TijoriOverviewSection.PRICE_CHART)
    assert isinstance(section, TijoriPriceSeriesSection)

    assert len(section.points) == 6
    assert section.malformed_point_count == 1
    first = section.points[0]
    assert first.timestamp_ms == 1223577000000
    assert first.timestamp_iso == datetime(2008, 10, 9, 18, 30, tzinfo=UTC)
    assert first.value == Decimal("41.1075")
    malformed = section.points[-1]
    assert malformed.timestamp_ms is None
    assert malformed.value is None
    assert malformed.raw_value_text == "[1224181800000]"
    assert section.series_provenance.row_label == "price_chart"


def test_price_chart_peers_model_the_optional_symbol() -> None:
    """A peer entry without a symbol is modeled as having none, not as invalid."""
    section = _one(TijoriOverviewSection.PRICE_CHART_PEERS)
    assert isinstance(section, TijoriPriceChartPeersSection)

    assert [peer.name for peer in section.peers] == [
        "Titan Company",
        "Kalyan Jewell.India",
        "Nifty 50",
    ]
    assert section.peers[0].symbol is None
    assert section.peers[1].symbol == "KALYANKJIL"
    assert section.peers[2].peer_type == "index"


def test_company_details_model_headline_numbers() -> None:
    """The overview header's valuation lexemes read as Decimals and keep their text."""
    section = _one(TijoriOverviewSection.COMPANY_DETAILS)
    assert isinstance(section, TijoriCompanyDetailsSection)

    assert section.company == "Titan Company Ltd."
    assert section.market_cap.value == Decimal("449713.0")
    assert section.market_cap_display == "₹4,49,713"
    assert section.price_earnings.value == Decimal("78.08")
    assert section.price_earnings_growth.value == Decimal("3.67")
    assert section.has_price_earnings_growth is True


def test_quick_look_models_counts_categories_and_keeps_table_data_verbatim() -> None:
    """LIVE shape: quick_look is an object whose categories carry the flags.

    The flags sit under ``data[].factories``, one level deeper than the
    depth-capped structure capture suggested; ``table_data``'s content is not yet
    known, so it is preserved rather than modeled.
    """
    section = _one(TijoriOverviewSection.COMPANY_DETAILS)
    assert isinstance(section, TijoriCompanyDetailsSection)
    quick_look = section.quick_look

    assert quick_look.counts is not None
    assert (quick_look.counts.green, quick_look.counts.red, quick_look.counts.total) == (14, 2, 17)
    assert quick_look.counts.gray == 0
    assert quick_look.counts.unmodeled_counts_json is None
    assert [category.name for category in quick_look.categories] == [
        "Accounting & Shareholding",
        "Growth & Returns",
    ]
    assert quick_look.flag_count == 3
    assert section.element_count == 3
    receivables = quick_look.categories[0].flags[0]
    assert receivables.name == "Receivable Days"
    assert receivables.flag == "AMBER"
    assert receivables.sentence is not None
    assert receivables.sentence.startswith("Receivable days rose")
    # A drifted flag key is preserved by the always-retained raw JSON.
    assert '"severity_rank": 2' in quick_look.categories[0].flags[1].raw_json
    assert quick_look.table_data_json is not None
    assert "shape not yet modeled" in quick_look.table_data_json
    assert quick_look.note is None


def test_quick_look_flag_anchors_stay_distinct_when_two_categories_share_a_name() -> None:
    """Nothing guarantees category names are unique, so position leads the address.

    Two same-named categories must still anchor their flags distinctly; otherwise
    two different findings would carry one identical, and therefore useless,
    complete anchor.
    """
    raw = _replace_island(
        "company_details_data",
        '{"company_id":81,"symbol":"TITAN","quick_look":{"data":['
        '{"name":"Accounting","factories":[{"name":"Receivable Days","flag":"AMBER"}]},'
        '{"name":"Accounting","factories":[{"name":"Auditor Change","flag":"RED"}]}]}}',
    )
    section = _one(TijoriOverviewSection.COMPANY_DETAILS, raw)
    assert isinstance(section, TijoriCompanyDetailsSection)

    first = section.quick_look.categories[0].flags[0].provenance
    second = section.quick_look.categories[1].flags[0].provenance
    assert first.row_label == "quick_look/0/Accounting/0"
    assert second.row_label == "quick_look/1/Accounting/0"
    assert (first.row_label, first.column_label) != (second.row_label, second.column_label)
    assert first.column_label == "flag"


def test_price_chart_peer_anchors_stay_distinct_when_two_peers_share_a_name() -> None:
    """The peer island guarantees no unique name, so the address is position-led."""
    raw = _replace_island(
        "price_chart_peers",
        '[{"name":"Titan Company","id":81,"type":"company"},'
        '{"name":"Titan Company","id":9999,"type":"index"}]',
    )
    section = _one(TijoriOverviewSection.PRICE_CHART_PEERS, raw)
    assert isinstance(section, TijoriPriceChartPeersSection)

    assert [peer.provenance.row_label for peer in section.peers] == [
        "0/Titan Company",
        "1/Titan Company",
    ]


def test_a_section_anchoring_two_elements_identically_is_fatal() -> None:
    """Backstop: a future addressing change must never collapse two elements silently."""
    section = _one(TijoriOverviewSection.PRICE_CHART_PEERS)
    assert isinstance(section, TijoriPriceChartPeersSection)
    collided = section.model_copy(
        update={
            "peers": (
                section.peers[0],
                section.peers[1].model_copy(update={"provenance": section.peers[0].provenance}),
            )
        }
    )

    with pytest.raises(TijoriOverviewSchemaError, match="anchors two elements identically"):
        reject_duplicate_anchors(collided, section.section.value)


def test_quick_look_records_a_count_key_tijori_added_later() -> None:
    """An unknown tally colour is recorded, not dropped and not fatal."""
    raw = _replace_island(
        "company_details_data",
        '{"company_id":81,"symbol":"TITAN","quick_look":'
        '{"count":{"green":1,"amber":4,"total":5},"data":[]}}',
    )
    section = _one(TijoriOverviewSection.COMPANY_DETAILS, raw)
    assert isinstance(section, TijoriCompanyDetailsSection)

    counts = section.quick_look.counts
    assert counts is not None
    assert counts.green == 1
    assert counts.total == 5
    assert counts.unmodeled_counts_json == '{"amber": 4}'


@pytest.mark.parametrize(
    ("island_json", "expected_note"),
    [
        ('{"company_id":81,"symbol":"TITAN"}', "island published no quick_look"),
        (
            '{"company_id":81,"symbol":"TITAN","quick_look":null}',
            "quick_look published as JSON null",
        ),
    ],
)
def test_quick_look_absent_or_null_is_an_empty_checklist_with_a_note(
    island_json: str, expected_note: str
) -> None:
    """A stock without the checklist still yields its header, never an error."""
    section = _one(
        TijoriOverviewSection.COMPANY_DETAILS, _replace_island("company_details_data", island_json)
    )
    assert isinstance(section, TijoriCompanyDetailsSection)

    assert section.quick_look.categories == ()
    assert section.quick_look.counts is None
    assert section.quick_look.note == expected_note
    assert section.element_count == 0


def test_unreadable_factories_are_retained_verbatim_on_their_category() -> None:
    """``factories`` is a modeled key, so its unreadable value needs its own slot.

    Excluding known keys from the unmodeled map would otherwise discard the
    source value and leave only a note claiming it was preserved.
    """
    raw = _replace_island(
        "company_details_data",
        '{"company_id":81,"symbol":"TITAN","quick_look":{"data":['
        '{"name":"Accounting","factories":"pending"}]}}',
    )
    section = _one(TijoriOverviewSection.COMPANY_DETAILS, raw)
    assert isinstance(section, TijoriCompanyDetailsSection)

    category = section.quick_look.categories[0]
    assert category.flags == ()
    assert category.invalid_fields_json == '{"factories": "pending"}'
    assert section.quick_look.note == "one category published no factories list; preserved verbatim"


@pytest.mark.parametrize(
    ("event_json", "unreadable_field"),
    [
        (
            '{"ex_date":{"y":2026},"event_details":"D","event_date":"2026-07-09T00:00:00Z"}',
            "ex_date",
        ),
        ('{"ex_date":"2026-07-09","event_details":"D","event_date":20260709}', "event_date"),
    ],
)
def test_an_action_with_an_unreadable_date_is_quarantined_not_blanked(
    event_json: str, unreadable_field: str
) -> None:
    """A blank-but-counted action would misreport the issuer's corporate history."""
    raw = _replace_island("corporate_actions", f'{{"Dividend":[{event_json}]}}')
    section = _one(TijoriOverviewSection.CORPORATE_ACTIONS, raw)
    assert isinstance(section, TijoriCorporateActionsSection)

    assert section.actions == ()
    assert section.element_count == 0
    assert len(section.quarantined_actions) == 1
    quarantined = section.quarantined_actions[0]
    assert quarantined.action_type == "Dividend"
    assert quarantined.element_path == "Dividend/0"
    assert unreadable_field in quarantined.reason
    assert unreadable_field in quarantined.raw_json


def test_an_action_with_an_unreadable_payload_field_is_kept_with_the_value_retained() -> None:
    """``event_details`` is payload, not identity, so the action survives beside it."""
    raw = _replace_island(
        "corporate_actions",
        '{"Dividend":[{"ex_date":"2026-07-09","event_details":{"text":"D"},'
        '"event_date":"2026-07-09T00:00:00Z"}]}',
    )
    section = _one(TijoriOverviewSection.CORPORATE_ACTIONS, raw)
    assert isinstance(section, TijoriCorporateActionsSection)

    assert section.quarantined_actions == ()
    action = section.actions[0]
    assert action.ex_date == "2026-07-09"
    assert action.event_details == ""
    assert action.invalid_fields_json == '{"event_details": {"text": "D"}}'


def test_a_wrong_typed_optional_field_is_retained_rather_than_read_as_absent() -> None:
    """A published value that cannot be read is a source claim, not missing data."""
    raw = _replace_island(
        "ratios_table",
        '[{"name":"pe","short_name":42,"unit":"","value":"78.08","id":"1"}]',
    )
    section = _one(TijoriOverviewSection.RATIOS, raw)
    assert isinstance(section, TijoriRatiosSection)

    ratio = section.ratios[0]
    assert ratio.short_name is None
    assert ratio.source_metric_id is None
    assert ratio.invalid_fields_json == '{"id": "1", "short_name": 42}'


def test_quick_look_of_an_unmodeled_shape_is_preserved_not_fatal() -> None:
    """This subtree was already wrong once, so an unexpected shape is retained.

    The pre-live contract modeled quick_look as a list; a page that published one
    must be recorded verbatim rather than failing the whole header.
    """
    raw = _replace_island(
        "company_details_data",
        '{"company_id":81,"symbol":"TITAN","quick_look":[{"name":"Legacy Flag"}]}',
    )
    section = _one(TijoriOverviewSection.COMPANY_DETAILS, raw)
    assert isinstance(section, TijoriCompanyDetailsSection)

    assert section.quick_look.note == "quick_look was not an object; preserved verbatim"
    assert section.quick_look.unmodeled_fields_json is not None
    assert "Legacy Flag" in section.quick_look.unmodeled_fields_json


def test_every_anchor_names_the_island_and_the_section_it_came_from() -> None:
    """No dishonest anchors: island_id is the island, table_key is the section.

    A rendered-HTML section is held to the matching honesty rule for ITS
    retrieval procedure — an HTML_TABLE anchor naming a DOM location — rather
    than being exempted from the check.
    """
    for section in _build():
        anchors = _anchors(section)
        assert anchors, f"{section.section.value} exposed no anchor"
        html_backed = section.source_kind is TijoriOverviewSourceKind.RENDERED_HTML
        for anchor in anchors:
            assert anchor["file_sha256"] == section.metadata.file_sha256
            assert anchor["retrieved_at"] == _RETRIEVED_AT
            assert anchor["row_label"]
            assert anchor["column_label"]
            if html_backed:
                # An island id here would misdescribe how to re-find the value.
                assert anchor["anchor_type"] is SourceAnchorType.HTML_TABLE
                assert anchor["island_id"] is None
                assert anchor["table_key"] is None
                assert anchor["table_id"]
                assert anchor["context_ref"].startswith(f"{_SOURCE_URL}#{anchor['table_id']}/")
                continue
            assert anchor["anchor_type"] is SourceAnchorType.JSON_ISLAND
            assert anchor["island_id"] == section.island_id
            assert anchor["table_key"] == section.section.value
            assert anchor["context_ref"].startswith(
                f"{_SOURCE_URL}#{section.island_id}/{section.section.value}/"
            )


def _anchors(section: TijoriOverviewSectionBase) -> list[dict[str, Any]]:
    """Collect every provenance the section exposes, at any nesting depth."""
    found: list[dict[str, Any]] = []
    _walk(section.model_dump(mode="python"), found)
    return found


def _walk(node: Any, found: list[dict[str, Any]]) -> None:
    """Depth-first walk collecting serialized provenance mappings."""
    if isinstance(node, dict):
        if "anchor_type" in node and "island_id" in node:
            found.append(node)
            return
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _walk(value, found)


def test_parse_section_rejects_an_unsupported_name() -> None:
    """A section name outside the modeled set is refused with the supported list.

    ``reverse_dcf`` is the pointed example: it is a real widget on the page and
    a deliberate non-section here, so asking for it must be refused rather than
    quietly acquired from somewhere.
    """
    with pytest.raises(TijoriOverviewSectionAbsentError, match="unsupported Tijori overview"):
        parse_section("reverse_dcf")


def _revenue_mix(raw: bytes | None = None) -> TijoriRevenueMixSection:
    """Build the revenue-mix section on its own."""
    section = _one(TijoriOverviewSection.REVENUE_MIX, raw)
    assert isinstance(section, TijoriRevenueMixSection)
    return section


def _without_revenue_mix() -> bytes:
    """Return the fixture with the whole revenue-mix section removed."""
    stripped = re.sub(
        r'<section id="revenuemix">.*?</section>',
        "",
        _page().decode("utf-8"),
        flags=re.DOTALL,
    )
    assert "revenuemix" not in stripped
    return stripped.encode("utf-8")


def test_revenue_mix_is_read_from_rendered_markup_not_an_island() -> None:
    """Its data lives in an entity-encoded attribute, so it needs a DOM reader."""
    section = _revenue_mix()

    assert section.source_kind is TijoriOverviewSourceKind.RENDERED_HTML
    assert section.island_id == REVENUE_MIX_ELEMENT_ID
    assert '"revenuemix"' not in _page().decode("utf-8").split("<section")[0]
    product = section.break_ups[0]
    assert product.title == "Product Wise Break-Up"
    assert product.status is TijoriIslandStatus.PRESENT
    assert [(entry.label, entry.value) for entry in product.entries] == [
        ("Jewelry", Decimal("88.37")),
        ("Watches", Decimal("8.12")),
        ("Others", Decimal("3.51")),
    ]


def test_every_declared_break_up_is_acquired_in_rendered_order() -> None:
    """A page publishes several break-ups; reading only the first would lose data."""
    section = _revenue_mix()

    assert [break_up.title for break_up in section.break_ups] == [
        "Product Wise Break-Up",
        "Location Wise Break-Up",
        "Operating Profit Break-Up (Historic)",
        "Asset Break-Up",
    ]
    assert section.element_count == 5


def test_revenue_mix_slices_anchor_to_their_chart_element() -> None:
    """The retrieval procedure is 'read this attribute of this element', so HTML_TABLE."""
    location = _revenue_mix().break_ups[1]

    assert location.table_id == "rmix:4281"
    first = location.entries[0].provenance
    assert first.anchor_type is SourceAnchorType.HTML_TABLE
    assert first.table_id == "rmix:4281"
    assert first.column_label == "value"
    assert first.column_index == 0
    assert first.island_id is None
    assert first.table_key is None
    # The block position leads the address: two break-ups may share a label.
    assert [entry.provenance.row_path for entry in location.entries] == [
        "1/0/India",
        "1/1/Overseas",
    ]


def test_a_block_with_no_chart_data_at_all_is_retained_with_a_status() -> None:
    """Historic wrappers sit beside the current blocks; dropping one hides drift.

    A block carrying no ``chart-data`` has nothing to read, so it gets a typed
    status and full retention rather than being silently skipped — including
    the chart id it declared elsewhere and its misnamed company-id attribute.
    """
    historic = _revenue_mix().break_ups[2]

    assert historic.status is TijoriIslandStatus.UNPARSEABLE
    assert historic.entries == ()
    assert historic.detail == "the block carries no chart-data attribute"
    assert historic.company_id_attribute == "4282"
    assert historic.raw_block_json is not None
    assert "4282" in historic.raw_block_json


def test_a_drifted_chart_attribute_is_refused_whole() -> None:
    """A break-up is a split of one total, so a partial read would not add up."""
    asset = _revenue_mix().break_ups[3]

    assert asset.status is TijoriIslandStatus.UNPARSEABLE
    assert asset.entries == ()
    assert asset.detail is not None
    assert "not a 2-element pair" in asset.detail


def test_the_block_company_id_attribute_is_never_treated_as_identity() -> None:
    """LIVE FACT: ``company-id`` duplicates ``chart-id`` and is NOT the issuer.

    On the real page every block declares company-id 4280/4281/... while the
    page itself is verified as company 81. Checking that attribute against the
    page identity refused every live break-up, which is exactly the regression
    this test exists to prevent. Identity is proven once by the island gate;
    this attribute is source data with a misleading name, nothing more.
    """
    section = _revenue_mix()
    product = section.break_ups[0]

    assert section.metadata.company_id == _COMPANY_ID
    assert product.company_id_attribute == "4280"
    assert product.company_id_attribute != str(_COMPANY_ID)
    # It duplicates the chart id — that is what it actually is.
    assert product.company_id_attribute == product.chart_id
    # And it changes nothing about whether the block parses.
    assert product.status is TijoriIslandStatus.PRESENT
    assert product.entries
    assert all(break_up.company_id_attribute != str(_COMPANY_ID) for break_up in section.break_ups)


def test_an_absent_revenue_mix_section_is_typed_absence_not_failure() -> None:
    """Some companies publish no revenue mix; that is data about the company."""
    raw = _without_revenue_mix()
    outcomes = {outcome.section: outcome for outcome in _build(raw)[0].metadata.section_outcomes}

    revenue_mix = outcomes[TijoriOverviewSection.REVENUE_MIX]
    assert revenue_mix.status is TijoriIslandStatus.ABSENT
    assert revenue_mix.source_kind is TijoriOverviewSourceKind.RENDERED_HTML
    assert revenue_mix.island_id == REVENUE_MIX_ELEMENT_ID
    assert revenue_mix.detail == "no element with this id is rendered on the page"
    with pytest.raises(TijoriOverviewSectionAbsentError, match="absent"):
        _build(raw, section=TijoriOverviewSection.REVENUE_MIX)


def test_a_rendered_but_unreadable_revenue_mix_is_drift_not_absence() -> None:
    """An empty section and a missing one are different facts about the page."""
    raw = (
        _page()
        .decode("utf-8")
        .replace('<div class="rmix_graph_block', '<div class="rmix_other_block')
    )
    outcomes = {
        outcome.section: outcome
        for outcome in _build(raw.encode("utf-8"))[0].metadata.section_outcomes
    }

    revenue_mix = outcomes[TijoriOverviewSection.REVENUE_MIX]
    assert revenue_mix.status is TijoriIslandStatus.UNPARSEABLE
    assert revenue_mix.detail == "the element is rendered but carries no recognizable block"


def test_every_section_declares_exactly_one_page_source() -> None:
    """A section read from neither an island nor a DOM element could not be built."""
    assert set(SECTION_SOURCE_IDS) == set(TijoriOverviewSection)
    assert not set(SECTION_ISLAND_IDS) & set(DOM_SECTION_ELEMENT_IDS)
