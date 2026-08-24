"""Tests for the raw Tijori financial-table acquisition contract.

Legacy quarterly P&L observation coverage lives in ``test_tijori.py``; this
module covers the breadth tables, their row/cell model, and access metadata.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.ingest.tijori_tables import (
    MAX_SUB_SECTION_DEPTH,
    TijoriCapabilityFlag,
    TijoriIslandStatus,
    TijoriRowSelectionError,
    TijoriTableAbsentError,
    TijoriTableDepthError,
    TijoriTableKey,
    TijoriTableKeyError,
    TijoriTablesAbsentError,
    TijoriTableSchemaError,
    build_tijori_table,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_HTML_FIXTURE = _FIXTURES / "synthetic_tijori_financials.html"
_FIXTURE_BYTES = _HTML_FIXTURE.read_bytes()
_TITAN_SLUG = "titan-company-limited"
_TITAN_SYMBOL = "TITAN"
_TITAN_URL = "https://www.tijorifinance.com/company/titan-company-limited/financials/"


def _source(**config: Any) -> TijoriSource:
    """Build a live source with a synthetic, redacted session cookie."""
    return TijoriSource(
        TijoriSourceConfig(
            credentials=TijoriCredentials(session_cookie="session-token"),
            **config,
        )
    )


def test_fetch_table_preserves_rows_and_sibling_date_metadata() -> None:
    """Raw quarterly breadth keeps source labels, nulls, and the sibling date lists."""
    source = _source()

    table = source.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="qt_s",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        source_url=_TITAN_URL,
    )

    assert table.key == "qt_s"
    assert table.scope.value == "standalone"
    assert table.column_period_labels == ("Sep 2024", "Dec 2024")
    assert table.comparative_period_labels == ("Sep 2023", "Dec 2023")
    assert table.skipped_period_labels == ("Mar 2023",)
    assert table.row("net_sales").cells[0].value == Decimal("15000.25")
    assert table.row("Net Profit").cells[1].value is None


@pytest.mark.parametrize(
    ("key", "expected_scope", "selector", "expected_value"),
    [
        ("pl_c_s", "consolidated", "revenue", Decimal("51000.875")),
        ("bs_c_s", "consolidated", "assets", Decimal("34000.0")),
        ("cf_c", "consolidated", "cfo", Decimal("3100.0")),
        ("fr_c", "consolidated", "roe_operational", Decimal("24.375")),
    ],
)
def test_fetch_table_preserves_every_statement_family(
    key: str,
    expected_scope: str,
    selector: str,
    expected_value: Decimal,
) -> None:
    """Every statement family uses the same raw, unmapped acquisition contract."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key=key,
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        source_url=_TITAN_URL,
    )

    assert table.scope.value == expected_scope
    assert table.column_period_labels == ("Mar 2023", "Mar 2024")
    assert table.row(selector).cells[1].value == expected_value


def test_capability_flags_never_discard_present_table_data() -> None:
    """Plan capability state is metadata: data present in the island is always parsed."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="growth",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    locks = {lock.feature: lock for lock in table.metadata.access.feature_locks}

    assert locks["growth"].flags == (TijoriCapabilityFlag(name="compare", enabled=False),)
    assert table.metadata.access.plan_name == "free"
    assert table.metadata.access.plan_tier == "free"
    assert table.rows
    assert table.row("share_price_cagr").cells[1].value == Decimal("21.25")


def test_financials_locks_are_feature_capabilities_not_table_keys() -> None:
    """The lock island is a UI-capability namespace and must never gate a table key."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="qt_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    features = {lock.feature for lock in table.metadata.access.feature_locks}

    assert {"rdcf", "qtly_results", "bs_snapshot"} <= features
    assert features.isdisjoint({key.value for key in TijoriTableKey} - {"growth"})
    assert {lock.feature: lock for lock in table.metadata.access.feature_locks}[
        "bs_snapshot"
    ].flags == (
        TijoriCapabilityFlag(name="chart", enabled=False),
        TijoriCapabilityFlag(name="compare", enabled=False),
    )


def test_missing_plan_islands_do_not_block_table_acquisition() -> None:
    """Plan metadata is optional: a page without it still yields its tables."""
    raw = re.sub(
        rb'<script id="(financials_locks|plan_details)".*?</script>',
        b"",
        _HTML_FIXTURE.read_bytes(),
        flags=re.DOTALL,
    )

    table = TijoriSource.parse_table_bytes(
        raw,
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    access = table.metadata.access

    assert access.plan_name is None
    assert access.feature_locks == ()
    assert access.financials_locks_status is TijoriIslandStatus.ABSENT
    assert access.plan_details_status is TijoriIslandStatus.ABSENT
    assert access.locks_island_id is None
    assert access.plan_island_id is None
    assert access.financials_locks_error is None
    assert table.row("debt_to_equity").cells[1].value == Decimal("0.625")


def test_unparseable_optional_island_is_distinct_from_absent_and_empty() -> None:
    """Absent, undecodable, and genuinely empty islands must not serialize alike."""
    unparseable = _FIXTURE_BYTES.replace(
        b'{"rdcf":{"editable":false}', b'{"rdcf":{"editable":false' * 2
    )
    empty = re.sub(
        rb'(<script id="financials_locks" type="application/json">)(.*?)(</script>)',
        rb"\1{}\3",
        _FIXTURE_BYTES,
        flags=re.DOTALL,
    )

    broken_access = TijoriSource.parse_table_bytes(
        unparseable, key="fr_c", slug=_TITAN_SLUG, expected_symbol=_TITAN_SYMBOL
    ).metadata.access
    empty_access = TijoriSource.parse_table_bytes(
        empty, key="fr_c", slug=_TITAN_SLUG, expected_symbol=_TITAN_SYMBOL
    ).metadata.access

    assert broken_access.financials_locks_status is TijoriIslandStatus.UNPARSEABLE
    assert broken_access.financials_locks_error is not None
    assert "line" in broken_access.financials_locks_error
    assert "column" in broken_access.financials_locks_error
    assert broken_access.locks_island_id is None
    assert broken_access.feature_locks == ()

    assert empty_access.financials_locks_status is TijoriIslandStatus.PRESENT
    assert empty_access.financials_locks_error is None
    assert empty_access.locks_island_id == "financials_locks"
    assert empty_access.feature_locks == ()
    assert empty_access.plan_details_status is TijoriIslandStatus.PRESENT


def test_unknown_sibling_island_key_is_recorded_not_fatal() -> None:
    """Only the requested key is validated; sibling drift is metadata, not failure."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert table.metadata.observed_unknown_table_keys == ("fundflow_c",)
    assert table.rows


def test_absent_supported_table_raises_typed_absence() -> None:
    """A supported key with no island data must never collapse to an empty table."""
    with pytest.raises(TijoriTableAbsentError, match="'bs_s_d'.*absent"):
        TijoriSource.parse_table_bytes(
            _HTML_FIXTURE.read_bytes(),
            key="bs_s_d",
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
        )


def test_null_table_is_skipped_and_recorded_as_not_offered() -> None:
    """A standalone-only issuer ships null consolidated tables; that is not failure."""
    tables = TijoriSource.parse_all_tables_bytes(
        _HTML_FIXTURE.read_bytes(),
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert "cf_s" not in {table.key.value for table in tables}
    assert tables[0].metadata.null_table_keys == ("cf_s",)


def test_explicit_fetch_of_a_null_table_reports_it_as_not_offered() -> None:
    """A null table is distinguishable from a key the island never carried."""
    with pytest.raises(TijoriTableAbsentError, match="present but null.*not offered"):
        TijoriSource.parse_table_bytes(
            _HTML_FIXTURE.read_bytes(),
            key="cf_s",
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
        )


def test_unknown_requested_table_key_fails_before_page_parsing() -> None:
    """A caller-supplied key outside the published schema is a typed key error."""
    with pytest.raises(TijoriTableKeyError, match="unsupported.*'mystery'"):
        TijoriSource.parse_table_bytes(
            b"not even HTML",
            key="mystery",
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
        )


def test_raw_cell_provenance_and_json_decimal_preserve_source_text() -> None:
    """Every cell has a complete JSON-island anchor and serializes Decimal as text."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        source_url=_TITAN_URL,
    )
    cell = table.row("debt_to_equity").cells[1]

    assert cell.provenance.anchor_type is SourceAnchorType.JSON_ISLAND
    assert cell.provenance.island_id == "fin_tables_data"
    assert cell.provenance.table_key == "fr_c"
    assert cell.provenance.row_label == "Debt to Equity"
    assert cell.provenance.column_label == "Mar 2024"
    assert cell.provenance.context_ref == (
        f"{_TITAN_URL}#fin_tables_data/fr_c/Operational Ratios/Debt to Equity/col/1/Mar 2024"
    )
    assert cell.raw_text == "0.625"
    assert '"value":"0.625"' in table.model_dump_json()


def test_nested_subsection_rows_keep_field_id_parent_path_and_depth() -> None:
    """Nested breadth rows stay addressable by Tijori's own machine identifier."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="qt_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    eps = table.row("adj_eps_abs")

    assert eps.label == "EPS"
    assert eps.field_id == "adj_eps_abs"
    assert eps.parent_labels == ("Quarterly Ratios",)
    assert eps.depth == 1
    assert eps.cells[1].value == Decimal("11.764")


def test_duplicate_labels_under_different_parents_stay_distinguishable() -> None:
    """Tijori repeats a display label under two sections; only selection may be fatal."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert table.row("Operational Ratios/Return on Equity").field_id == "roe_operational"
    assert table.row("Profitability Ratios/Return on Equity").field_id == "roe_profitability"
    assert table.row("operational_ratios").cells == ()
    with pytest.raises(TijoriRowSelectionError, match="has no row matching"):
        table.row("Return on Equity")


def test_one_field_id_under_two_parents_is_a_row_key_not_a_collision() -> None:
    """fr_c publishes 'ebit' in two derivation contexts; both rows must survive."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    coverage = table.row("Operational Ratios/Interest Coverage Ratio")
    roce = table.row("Profitability Ratios/ROCE (%)")

    assert coverage.field_id == "ebit"
    assert roce.field_id == "ebit"
    assert coverage.cells[1].value == Decimal("9.25")
    assert roce.cells[1].value == Decimal("21.75")
    with pytest.raises(TijoriRowSelectionError, match="ambiguous"):
        table.row("ebit")


def test_non_numeric_cells_survive_as_raw_text_without_killing_the_table() -> None:
    """A percent, a placeholder, and a grouped number never fail the acquisition."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    percent, placeholder = table.row("roe_profitability").cells
    grouped = table.row("Profitability Ratios/Working Capital")

    assert (percent.value, percent.raw_text) == (None, "12.5%")
    assert (placeholder.value, placeholder.raw_text) == (None, "-")
    assert grouped.cells[0].value == Decimal("1234")
    assert grouped.cells[0].raw_text == "1,234"
    assert grouped.cells[1].value == Decimal("2468.5")
    assert len(table.rows) == 8


def test_short_and_long_rows_are_quarantined_not_fatal() -> None:
    """A row whose value count disagrees with the columns must not kill the table."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="pl_c_s",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    short = table.row("Raw Material/Steel")
    long_row = table.row("Raw Material/Gems & Jewellery")

    assert len(table.rows) == 5
    assert table.row("revenue").cells[1].value == Decimal("51000.875")
    assert table.row("pat").cells[0].value == Decimal("3200.25")
    assert short.cells == ()
    assert short.unaligned_raw_values == ("120.5",)
    assert long_row.cells == ()
    assert long_row.unaligned_raw_values == ("80.25", "90.75", "100.0")
    assert table.cardinality_mismatch_rows == (
        "Raw Material/Steel",
        "Raw Material/Gems & Jewellery",
    )


def test_zero_length_value_row_is_a_header_not_a_quarantine() -> None:
    """A section header carries no values at all and is not a cardinality fault."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    header = table.row("operational_ratios")

    assert header.cells == ()
    assert header.unaligned_raw_values == ()
    assert table.cardinality_mismatch_rows == ()


def test_sentinel_field_ids_never_become_row_keys() -> None:
    """Detailed statements set field="NA" on every row; that must not collide keys."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="bs_c_d",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert all(row.field_id is None for row in table.rows)
    assert tuple(row.row_key for row in table.rows) == (
        "Assets",
        "Assets/Fixed Assets",
        "Assets/Current Assets",
        "Liabilities",
    )
    assert table.row("Assets/Fixed Assets").cells[0].value == Decimal("12000.0")
    assert table.row("Assets/Current Assets").cells[1].value == Decimal("21000.0")


def test_empty_string_sub_section_parses_as_a_leaf_row() -> None:
    """Leaf rows report no children as "" rather than []; both mean the same."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="bs_c_d",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )
    leaf = table.row("Assets/Fixed Assets")

    assert len(table.rows) == 4
    assert leaf.parent_labels == ("Assets",)
    assert leaf.depth == 1
    assert table.row("Liabilities").depth == 0


def test_unique_field_ids_are_a_lookup_not_the_row_key() -> None:
    """A row is addressed by its label path; a unique field id still finds it."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="qt_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert table.row("adj_eps_abs").row_key == "Quarterly Ratios/EPS"
    assert table.row("adj_eps_abs").field_id == "adj_eps_abs"
    assert table.row("net_sales").row_key == "Net Sales"
    assert table.row("Net Sales").field_id == "net_sales"


def test_unexpected_sub_section_shape_stays_fatal() -> None:
    """Only "" and null mean childless; another shape could hide real structure."""
    financials = {
        "growth": {
            "report_dates": ["1yr"],
            "data": [{"name": "Share Price CAGR", "value": [Decimal("1")], "sub_section": {}}],
        }
    }

    with pytest.raises(TijoriTableSchemaError, match="sub_section must be a"):
        build_tijori_table(
            financials=financials,
            financials_locks=None,
            plan_details=None,
            key="growth",
            content_sha256="0" * 64,
            source_url=_TITAN_URL,
            retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
            slug=_TITAN_SLUG,
            symbol=_TITAN_SYMBOL,
            company_id=81,
        )


def test_table_is_frozen_and_hashable() -> None:
    """Acquired tables are immutable values usable as dictionary or set members."""
    table = TijoriSource.parse_table_bytes(
        _HTML_FIXTURE.read_bytes(),
        key="fr_c",
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    with pytest.raises(ValidationError):
        table.rows = ()
    assert isinstance(hash(table), int)


def test_structurally_empty_table_data_raises_typed_schema_error() -> None:
    """Empty row data is malformed structure, not a successful empty acquisition."""
    raw = _HTML_FIXTURE.read_bytes().replace(
        b'{"name":"Share Price CAGR","field":"share_price_cagr","value":[18.5,21.25]},\n'
        b'            {"name":"TTM EPS CAGR","field":"ttm_eps_cagr","value":[12.0,15.75]}',
        b"",
    )

    with pytest.raises(TijoriTableSchemaError, match="'growth' data must be a non-empty"):
        TijoriSource.parse_table_bytes(
            raw,
            key="growth",
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
        )


def test_sub_section_recursion_is_bounded_by_a_typed_error() -> None:
    """Pathological nesting fails with a typed depth error instead of recursing."""
    row: dict[str, Any] = {"name": "leaf", "value": [Decimal("1")]}
    for level in range(MAX_SUB_SECTION_DEPTH + 1):
        row = {"name": f"level-{level}", "value": [Decimal("1")], "sub_section": [row]}

    with pytest.raises(TijoriTableDepthError, match="deeper than"):
        build_tijori_table(
            financials={"growth": {"report_dates": ["1yr"], "data": [row]}},
            financials_locks=None,
            plan_details=None,
            key="growth",
            content_sha256="0" * 64,
            source_url=_TITAN_URL,
            retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
            slug=_TITAN_SLUG,
            symbol=_TITAN_SYMBOL,
            company_id=81,
        )


def _island_replaced(island_json: bytes) -> bytes:
    """Return the fixture with its financials island body swapped out."""
    return re.sub(
        rb'(<script id="fin_tables_data" type="application/json">)(.*?)(</script>)',
        rb"\1" + island_json + rb"\3",
        _FIXTURE_BYTES,
        flags=re.DOTALL,
    )


@pytest.mark.parametrize(
    ("island_json", "expected_observed"),
    [
        (b"{}", "none"),
        (b'{"fundflow_c": {"report_dates": ["Mar 2024"], "data": []}}', "fundflow_c"),
        (b'{"qt_c": null, "pl_c_s": null}', "pl_c_s, qt_c"),
    ],
)
def test_island_without_supported_tables_fails_loudly(
    island_json: bytes, expected_observed: str
) -> None:
    """A breadth run that can acquire nothing must never look like an empty success."""
    with pytest.raises(TijoriTablesAbsentError, match=f"observed keys: {expected_observed}"):
        TijoriSource.parse_all_tables_bytes(
            _island_replaced(island_json),
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
        )


def _one_table_financials(report_dates: list[str], data: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal one-table financials island for contract-level tests."""
    return {"growth": {"report_dates": report_dates, "data": data}}


def _build_growth(financials: dict[str, Any]) -> Any:
    """Build the growth table from a synthetic island through the public builder."""
    return build_tijori_table(
        financials=financials,
        financials_locks=None,
        plan_details=None,
        key="growth",
        content_sha256="0" * 64,
        source_url=_TITAN_URL,
        retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        slug=_TITAN_SLUG,
        symbol=_TITAN_SYMBOL,
        company_id=81,
    )


def test_duplicate_column_labels_still_yield_unique_cell_anchors() -> None:
    """Cell provenance carries the column index, so repeated labels stay addressable."""
    table = _build_growth(
        _one_table_financials(
            ["1yr", "1yr"],
            [{"name": "Share Price CAGR", "value": [Decimal("1"), Decimal("2")]}],
        )
    )
    anchors = tuple(cell.provenance.context_ref for cell in table.rows[0].cells)

    assert table.column_period_labels == ("1yr", "1yr")
    assert len(set(anchors)) == 2
    assert anchors[0] is not None and anchors[0].endswith("/col/0/1yr")
    assert anchors[1] is not None and anchors[1].endswith("/col/1/1yr")


def test_duplicate_row_keys_within_a_table_are_fatal() -> None:
    """Two rows sharing one address would make every selection ambiguous."""
    financials = _one_table_financials(
        ["1yr"],
        [
            {"name": "CFO CAGR", "value": [Decimal("1")]},
            {"name": "CFO CAGR", "value": [Decimal("2")]},
        ],
    )

    with pytest.raises(TijoriTableSchemaError, match="duplicate row keys: CFO CAGR"):
        _build_growth(financials)


def test_fetch_all_tables_covers_every_present_published_key() -> None:
    """One page parse returns each published key that carries data, in key order."""
    tables = TijoriSource.parse_all_tables_bytes(
        _HTML_FIXTURE.read_bytes(),
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
    )

    assert tuple(table.key.value for table in tables) == (
        "bs_c_d",
        "bs_c_s",
        "cf_c",
        "fr_c",
        "growth",
        "pl_c_s",
        "qt_c",
        "qt_s",
    )
    assert all(table.rows for table in tables)
    first = tables[0]
    assert first.metadata.observed_unknown_table_keys == ("fundflow_c",)
    assert first.metadata.access.plan_name == "free"
    assert first.metadata.slug == _TITAN_SLUG
    assert first.metadata.symbol == _TITAN_SYMBOL
    assert first.metadata.company_id == 81
    assert len(first.metadata.file_sha256) == 64
