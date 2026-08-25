"""Tests for the Tijori detailed shareholding acquisition contract.

Shareholding is the one verified Tijori surface rendered as HTML rather than a
JSON island, so these tests pin the shape assertion that rejects the page's
sample-report modal templates, the attribute-driven category tree, and the
fail-closed heading comp_id gate that stands in for the page's absent identity
island.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_common import TijoriIslandStatus
from fundamentals.ingest.tijori_shareholding import (
    IDENTITY_ISLAND_IDS,
    MAX_SHAREHOLDING_DEPTH,
    SHAREHOLDING_TABLE_ID,
    TijoriShareholding,
    TijoriShareholdingAbsentError,
    TijoriShareholdingAmbiguousError,
    TijoriShareholdingDepthError,
    TijoriShareholdingIdentityError,
    TijoriShareholdingRowSelectionError,
    TijoriShareholdingSchemaError,
)
from fundamentals.ingest.tijori_shareholding_breakup import MAX_LITERAL_CHARS
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriFetchError,
    TijoriParseError,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.output.earnings_update import anchor_label

_FIXTURES = Path(__file__).parent / "fixtures"
_HTML_FIXTURE = _FIXTURES / "synthetic_tijori_shareholding.html"
_FIXTURE_TEXT = _HTML_FIXTURE.read_text(encoding="utf-8")
_TITAN_SLUG = "titan-company-limited"
_TITAN_SYMBOL = "TITAN"
_TITAN_COMPANY_ID = 81
_TITAN_URL = "https://www.tijorifinance.com/company/titan-company-limited/shareholding/"


def _parse(raw: bytes | None = None, **overrides: Any) -> TijoriShareholding:
    """Parse one shareholding fixture through the adapter's public seam."""
    arguments: dict[str, Any] = {
        "slug": _TITAN_SLUG,
        "expected_symbol": _TITAN_SYMBOL,
        "expected_company_id": _TITAN_COMPANY_ID,
        "source_url": _TITAN_URL,
    }
    arguments.update(overrides)
    return TijoriSource.parse_shareholding_bytes(
        _HTML_FIXTURE.read_bytes() if raw is None else raw, **arguments
    )


def _mutated(original: str, replacement: str) -> bytes:
    """Return the fixture with exactly one verified substring replaced."""
    assert _FIXTURE_TEXT.count(original) == 1, original
    return _FIXTURE_TEXT.replace(original, replacement).encode("utf-8")


def _stripped_headings() -> bytes:
    """Return the fixture with both company headings' comp_id attribute removed."""
    stripped = _FIXTURE_TEXT.replace(' comp_id="81"', "")
    assert "comp_id" not in stripped
    return stripped.encode("utf-8")


class _Response(BytesIO):
    """Controllable HTTP response for the shareholding transport boundary."""

    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        super().__init__(payload)
        self._status = status
        self.headers: dict[str, str] = {}

    def getcode(self) -> int:
        """Return the configured HTTP status code."""
        return self._status


class _Opener:
    """Injectable urllib opener that records outbound requests."""

    def __init__(self, outcome: _Response | Exception) -> None:
        self._outcome = outcome
        self.calls: list[tuple[urllib.request.Request, float]] = []

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        """Record the one outbound request and return or raise the configured outcome."""
        self.calls.append((request, timeout))
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _install_opener(monkeypatch: pytest.MonkeyPatch, opener: _Opener) -> None:
    """Patch opener construction so no test can reach the network."""

    def build_opener(handler: urllib.request.HTTPRedirectHandler) -> _Opener:
        del handler
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)


def test_category_tree_keeps_depth_parent_path_and_source_node_ids() -> None:
    """The rendered nesting attributes reconstruct the SEBI category tree exactly."""
    shareholding = _parse()

    fund = shareholding.row("Public Shareholding/Institutions/Synthetic Large Cap Fund")
    assert fund.depth == 2
    assert fund.source_depth == 3
    assert fund.parent_labels == ("Public Shareholding", "Institutions")
    assert fund.source_node_id == "SyntheticLargeCapFund"
    assert fund.source_parent_id == "Institutions"
    assert shareholding.row("Promoter").parent_labels == ()
    assert shareholding.row("Promoter").source_parent_id == "1"


def test_quarter_labels_decode_entities_and_preserve_rendered_text() -> None:
    """Column labels keep Tijori's exact rendered text with entities decoded."""
    shareholding = _parse()

    assert shareholding.column_period_labels == ("Mar'24", "Jun'24", "Sep'24")
    assert shareholding.unit_label == "in %"


@pytest.mark.parametrize(
    ("row_key", "column", "expected_value", "expected_raw"),
    [
        ("Promoter", 0, Decimal("52.90"), "52.90"),
        # An em dash is Tijori's rendered "not disclosed"; the lexeme must survive.
        ("Promoter/Foreign Promoters", 0, None, "—"),
        # The shareholder count is the one comma-grouped integer row on the page.
        ("No. of Shareholders", 0, Decimal("749319"), "749,319"),
        ("Public Shareholding/Non-Institutions/Individual < 2 lac", 2, Decimal("13.88"), "13.88"),
    ],
)
def test_cell_readings_apply_the_shared_decimal_rule(
    row_key: str, column: int, expected_value: Decimal | None, expected_raw: str
) -> None:
    """Percentages, absent values, and comma-grouped counts all read one way."""
    cell = _parse().row(row_key).cells[column]

    assert cell.value == expected_value
    assert cell.raw_text == expected_raw


def test_sample_report_modal_tables_never_contribute_rows() -> None:
    """The decoy modal templates share the row macro but not the unit header."""
    shareholding = _parse()

    node_ids = {row.source_node_id for row in shareholding.rows}
    assert "SampleScenario" not in node_ids
    assert "SampleEstimate" not in node_ids
    assert len(shareholding.column_period_labels) == 3


def test_a_sample_table_wearing_the_shareholding_shape_is_not_selected() -> None:
    """Shape alone is spoofable, so the DOM id decides which table is authoritative."""
    shareholding = _parse()

    # The peg-sample decoy carries the 'in %' unit cell, quarter columns, and
    # rowN/myid rows — everything the structural predicate asks for.
    node_ids = {row.source_node_id for row in shareholding.rows}
    assert "SampleScenario" not in node_ids
    assert shareholding.row("Promoter").cells[0].value == Decimal("52.90")


def test_a_second_table_with_the_shareholding_id_is_refused_not_guessed() -> None:
    """Two elements claiming the id make authority undecidable."""
    with pytest.raises(TijoriShareholdingAmbiguousError, match="2 tables with id"):
        _parse(
            _mutated(
                '<div class="modal sample-report">\n      <table class="peg-sample__table">',
                '<div class="modal sample-report">\n      '
                '<table id="company_detailed" class="peg-sample__table">',
            )
        )


def test_absent_shareholding_table_fails_closed_naming_the_expected_id() -> None:
    """A page without the identified table yields a typed absent error."""
    with pytest.raises(TijoriShareholdingAbsentError, match="no <table id='company_detailed'>"):
        _parse(_mutated('<table id="company_detailed" class="display', '<table class="display'))


def test_the_identified_table_must_still_prove_its_shape() -> None:
    """The id finds the table; the structural assertions prove it is the right one."""
    # The decoy carries the same unit cell at a different indent, so anchor on
    # the real table's indentation to change only its header.
    real_unit_cell = '\n          <th class="firstcol unit_val"> in % </th>'
    with pytest.raises(
        TijoriShareholdingSchemaError, match=r"unit header is 'in Cr', expected 'in %'"
    ):
        _parse(_mutated(real_unit_cell, real_unit_cell.replace(" in % ", " in Cr ")))


def test_unknown_parent_id_fails_closed_naming_the_dangling_reference() -> None:
    """Machine nesting that names a parent the page never defined is fatal."""
    with pytest.raises(TijoriShareholdingSchemaError, match="unknown parent 'NoSuchNode'"):
        _parse(
            _mutated(
                'parent="IndianPromoters" data-parent="IndianPromoters"',
                'parent="NoSuchNode" data-parent="NoSuchNode"',
            )
        )


def test_depth_jump_against_the_declared_parent_fails_closed() -> None:
    """A row whose class depth skips a level cannot be placed in the tree."""
    with pytest.raises(TijoriShareholdingSchemaError, match="declares depth 4 under parent"):
        _parse(
            _mutated(
                '<tr class="row3" parent="IndianPromoters"',
                '<tr class="row4" parent="IndianPromoters"',
            )
        )


def test_a_root_row_at_a_non_root_depth_fails_closed() -> None:
    """``data-parent="1"`` means root, so any other depth is inconsistent."""
    with pytest.raises(TijoriShareholdingSchemaError, match="declares depth 2, expected 1"):
        _parse(
            _mutated(
                '<tr class="row1" parent="1" data-parent="1" myid="Promoter"',
                '<tr class="row2" parent="1" data-parent="1" myid="Promoter"',
            )
        )


def test_a_reclassified_shareholder_may_appear_under_two_parents() -> None:
    """One entity legitimately sits in two category buckets; row keys separate them."""
    shareholding = _parse()

    institutional = shareholding.row(
        "Public Shareholding/Institutions/Synthetic Crossover Holdings Ltd"
    )
    retail = shareholding.row(
        "Public Shareholding/Non-Institutions/Synthetic Crossover Holdings Ltd"
    )
    assert institutional.source_node_id == retail.source_node_id
    assert institutional.source_parent_id == "Institutions"
    assert retail.source_parent_id == "NonInstitutions"
    assert institutional.cells[0].value == Decimal("1.05")
    assert retail.cells[0].value is None


def test_a_repeated_node_id_used_as_a_parent_fails_closed() -> None:
    """A reused id that some row names as its parent cannot resolve to one node."""
    with pytest.raises(
        TijoriShareholdingSchemaError,
        match="repeats a node id that is used as a parent: 'IndianPromoters'",
    ):
        _parse(_mutated('myid="ForeignPromoters"', 'myid="IndianPromoters"'))


def test_a_repeated_node_id_under_the_same_parent_fails_closed() -> None:
    """Twice under one parent is a true duplicate, not a reclassification."""
    with pytest.raises(
        TijoriShareholdingSchemaError,
        match="repeats node id 'SyntheticCrossoverHoldings' under one parent 'Institutions'",
    ):
        _parse(
            _mutated(
                'parent="NonInstitutions" data-parent="NonInstitutions" '
                'myid="SyntheticCrossoverHoldings"',
                'parent="Institutions" data-parent="Institutions" '
                'myid="SyntheticCrossoverHoldings"',
            )
        )


def test_a_row_without_a_display_name_fails_closed() -> None:
    """The label path is the address, so an unnamed row cannot be addressed."""
    with pytest.raises(TijoriShareholdingSchemaError, match="empty display name"):
        _parse(_mutated("<span>Foreign Promoters</span>", "<span></span>"))


def test_a_data_row_without_nesting_attributes_fails_closed_naming_it() -> None:
    """A value row the parser cannot place is an error, never a silent drop."""
    with pytest.raises(
        TijoriShareholdingSchemaError,
        match=r"data rows without rowN/myid/data-parent: 'No\. of Shareholders'",
    ):
        _parse(
            _mutated(
                '<tr class="row1" parent="1" data-parent="1" myid="NoOfShareholders" index=\'13\'',
                "<tr index='13'",
            )
        )


def test_a_table_with_no_aligned_cells_is_drift_not_data() -> None:
    """Quarter columns with nothing under them means the page changed shape."""
    stripped = _FIXTURE_TEXT.replace('class="knowledge numericvalue', 'class="knowledge dropped')
    with pytest.raises(TijoriShareholdingSchemaError, match="carries no aligned cells"):
        _parse(stripped.encode("utf-8"))


def test_cardinality_mismatch_quarantines_the_row_and_keeps_its_lexemes() -> None:
    """Alignment is never guessed: the row loses cells but keeps its raw values."""
    shareholding = _parse()

    row = shareholding.row("Unaligned Legacy Row")
    assert row.cells == ()
    assert row.unaligned_raw_values == ("1.11", "2.22")
    assert shareholding.cardinality_mismatch_rows == ("Unaligned Legacy Row",)


def test_identity_is_proved_by_the_heading_comp_id_not_by_an_island() -> None:
    """The live page carries no identity island; the heading comp_id is the marker."""
    shareholding = _parse()

    assert shareholding.metadata.company_id == _TITAN_COMPANY_ID
    assert shareholding.metadata.symbol == _TITAN_SYMBOL
    # metrics is a chart-metric catalogue and peersList names peers, so neither
    # corroborates identity — the tuple being empty is the live-page fact.
    assert shareholding.metadata.identity_island_ids == ()


def test_heading_comp_id_mismatch_fails_closed_naming_both_ids() -> None:
    """A page for another issuer must never be parsed as the requested one."""
    with pytest.raises(
        TijoriShareholdingIdentityError, match="requested company ID 999, page <h1 comp_id> 81"
    ):
        _parse(expected_company_id=999)


def test_a_page_without_a_heading_comp_id_is_refused() -> None:
    """Identity is never skipped: with no marker the response cannot be bound."""
    with pytest.raises(TijoriShareholdingIdentityError, match="publishes no <h1 comp_id> marker"):
        _parse(
            _stripped_headings(),
        )


def test_disagreeing_duplicate_headings_fail_closed() -> None:
    """The page renders the heading twice; a self-contradicting page is refused."""
    with pytest.raises(TijoriShareholdingIdentityError, match="disagreeing <h1 comp_id> values"):
        _parse(_mutated('<h1 comp_id="81">Titan Company Ltd.</h1>', '<h1 comp_id="99">X</h1>'))


def test_a_non_numeric_heading_comp_id_is_refused() -> None:
    """An unreadable marker is named, never silently ignored."""
    with pytest.raises(TijoriShareholdingIdentityError, match="is not a company ID: 'titan'"):
        _parse(
            _mutated(
                '<h1 class="company_main_heading" comp_id="81">',
                '<h1 class="company_main_heading" comp_id="titan">',
            ).replace(b'<h1 comp_id="81">', b'<h1 comp_id="titan">')
        )


def test_an_island_that_does_publish_an_identity_must_still_agree() -> None:
    """Island checks are conjunctive with the heading gate, not a substitute for it."""
    with pytest.raises(TijoriShareholdingIdentityError, match="island 'company_details'"):
        _parse(
            _mutated(
                '<script id="is_auth" type="application/json">true</script>',
                '<script id="is_auth" type="application/json">true</script>\n'
                '<script id="company_details" type="application/json">'
                '{"symbol":"INFY","company_id":42}</script>',
            )
        )


def test_a_corroborating_island_is_recorded_when_it_agrees() -> None:
    """A future page that does publish an identity has it verified and recorded."""
    shareholding = _parse(
        _mutated(
            '<script id="is_auth" type="application/json">true</script>',
            '<script id="is_auth" type="application/json">true</script>\n'
            '<script id="company_details" type="application/json">'
            '{"symbol":"TITAN","company_id":81}</script>',
        )
    )

    assert shareholding.metadata.identity_island_ids == ("company_details",)


def test_unauthenticated_page_fails_closed_before_any_row_is_parsed() -> None:
    """A logged-out render is refused by the shared authentication gate."""
    with pytest.raises(TijoriParseError, match="not authenticated"):
        _parse(
            _mutated(
                '<script id="is_auth" type="application/json">true</script>',
                '<script id="is_auth" type="application/json">false</script>',
            )
        )


def test_plan_metadata_is_carried_beside_the_table_and_never_gates_it() -> None:
    """Plan state is page metadata reused from the tables contract."""
    access = _parse().metadata.access

    assert access.plan_tier == "pro"
    assert access.plan_name == "Owner Research"


def test_cell_provenance_binds_the_rendered_html_table_location() -> None:
    """Every cell anchors to table, row path, and positional column."""
    shareholding = _parse()

    cell = shareholding.row("No. of Shareholders").cells[1]
    assert cell.provenance.anchor_type is SourceAnchorType.HTML_TABLE
    assert cell.provenance.table_id == SHAREHOLDING_TABLE_ID
    assert cell.provenance.row_path == "No. of Shareholders"
    assert cell.provenance.column_index == 1
    assert cell.provenance.column_label == "Jun'24"
    assert cell.provenance.file_sha256 == sha256(_HTML_FIXTURE.read_bytes()).hexdigest()
    assert cell.provenance.context_ref is not None
    assert cell.provenance.context_ref.startswith(_TITAN_URL)


def test_row_selector_reports_an_unknown_row_rather_than_returning_nothing() -> None:
    """Selection failure is typed, never a silent empty result."""
    with pytest.raises(TijoriShareholdingRowSelectionError, match="no row matching"):
        _parse().row("Promoter/Nonexistent")


def test_nesting_bound_and_identity_candidates_are_declared_not_implicit() -> None:
    """The bound and the supplementary island set are contract, not incidental behavior."""
    assert MAX_SHAREHOLDING_DEPTH > 0
    assert issubclass(TijoriShareholdingDepthError, TijoriShareholdingSchemaError)
    # Tijori names its identity island per surface; none appears on shareholding
    # today, so these only ever corroborate the required heading gate.
    assert IDENTITY_ISLAND_IDS == ("company_details", "company_details_data", "metrics")


def test_fetch_targets_the_shareholding_url_and_refuses_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live acquisition reuses the polite fetcher against the shareholding path."""
    opener = _Opener(_Response(_HTML_FIXTURE.read_bytes()))
    _install_opener(monkeypatch, opener)
    source = TijoriSource(
        TijoriSourceConfig(credentials=TijoriCredentials(session_cookie="session-token"))
    )

    shareholding = source.fetch_shareholding(
        slug=_TITAN_SLUG,
        expected_symbol=_TITAN_SYMBOL,
        expected_company_id=_TITAN_COMPANY_ID,
    )

    request, _ = opener.calls[0]
    assert request.full_url == _TITAN_URL
    assert len(shareholding.rows) == 14


def test_redirected_shareholding_slug_is_a_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown slug redirecting to the home page never becomes a parse."""
    _install_opener(monkeypatch, _Opener(_Response(b"", status=302)))
    source = TijoriSource(
        TijoriSourceConfig(credentials=TijoriCredentials(session_cookie="session-token"))
    )

    with pytest.raises(TijoriFetchError, match="redirect response"):
        source.fetch_shareholding(
            slug=_TITAN_SLUG,
            expected_symbol=_TITAN_SYMBOL,
            expected_company_id=_TITAN_COMPANY_ID,
        )


def test_html_table_anchor_requires_its_full_location() -> None:
    """An HTML_TABLE anchor without a resolvable location is not constructible."""
    with pytest.raises(ValidationError, match="HTML_TABLE anchor requires table_id"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.HTML_TABLE,
            column_index=0,
            column_label="Mar'24",
            retrieved_at=datetime.now(tz=UTC),
        )


def test_html_table_anchor_requires_a_non_negative_column_index() -> None:
    """The positional column index is what keeps repeated labels distinguishable."""
    with pytest.raises(ValidationError, match="non-negative column_index"):
        Provenance(
            source_id="tijori",
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.HTML_TABLE,
            table_id=SHAREHOLDING_TABLE_ID,
            row_path="Promoter",
            column_label="Mar'24",
            retrieved_at=datetime.now(tz=UTC),
        )


def test_the_anchor_renderer_describes_the_html_table_location() -> None:
    """A new anchor type must render a resolvable location, not fall through."""
    provenance = _parse().row("Promoter").cells[0].provenance

    rendered = anchor_label(provenance)
    assert "HTML table detailed_shareholding" in rendered
    assert "row Promoter" in rendered
    assert "column 0 (Mar'24)" in rendered


def _breakup(subcategory: str, shareholding: TijoriShareholding | None = None) -> Any:
    """Select one break-up chart by the subcategory its script declared."""
    built = shareholding if shareholding is not None else _parse()
    return next(entry for entry in built.breakups if entry.subcategory == subcategory)


def test_breakup_charts_are_read_from_the_inline_script_literal() -> None:
    """The aggregate charts are JS array literals, not JSON islands or table rows."""
    overview = _breakup("overview")

    assert overview.status is TijoriIslandStatus.PRESENT
    assert overview.table_id == "chartData:overview"
    assert [(entry.label, entry.value) for entry in overview.entries] == [
        ("Promoter", Decimal("52.9")),
        ("Mutual Funds", Decimal("8.73")),
        ("Foreign Institutions", Decimal("17.42")),
        ("Others", Decimal("20.95")),
    ]


def test_breakup_slices_are_anchored_by_position_in_their_chart() -> None:
    """Nothing guarantees unique slice labels, so the index leads the address."""
    entries = _breakup("overview").entries

    first = entries[0].provenance
    assert first.anchor_type is SourceAnchorType.HTML_TABLE
    assert first.table_id == "chartData:overview"
    assert first.row_path == "0/Promoter"
    assert first.column_index == 0
    assert first.column_label == "value"
    assert first.island_id is None
    assert [entry.provenance.column_index for entry in entries] == [0, 1, 2, 3]


def test_every_declared_subcategory_is_acquired() -> None:
    """The page declares more than one chart; acquiring only the first would lose data."""
    trend = _breakup("trend")

    assert trend.table_id == "chartData:trend"
    assert [entry.label for entry in trend.entries] == ["Promoter", "Institutions"]


def test_an_identical_repeat_of_one_chart_collapses_to_a_single_breakup() -> None:
    """The template renders one chart in two layout slots; that is not two charts."""
    built = _parse()

    assert [entry.subcategory for entry in built.breakups] == [
        "overview",
        "trend",
        "category",
    ]


def test_disagreeing_charts_are_refused_without_killing_the_detailed_table() -> None:
    """A self-contradicting chart script is a fact about that chart, not the page.

    Neither literal can be read as the subcategory's chart, so both are retained
    and the break-up is refused — but the detailed shareholding table is this
    page's authoritative payload and must survive it intact.
    """
    raw = _mutated("['Promoter', 52.9], ['Institutions', 26.15]", "['Promoter', 99.9]").replace(
        b'var subcategory = "trend";', b'var subcategory = "overview";'
    )
    built = _parse(raw)
    overview = _breakup("overview", built)

    # The table is untouched by the conflict beside it.
    assert built.row("Promoter").cells[0].value == Decimal("52.9")
    assert len(built.rows) == 14
    assert built.column_period_labels == ("Mar'24", "Jun'24", "Sep'24")

    assert overview.status is TijoriIslandStatus.UNPARSEABLE
    assert overview.entries == ()
    assert overview.detail is not None
    assert "disagreeing chartData" in overview.detail
    # BOTH competing literals survive, so the conflict can be inspected rather
    # than one of them being silently promoted to the truth.
    assert len(overview.raw_literals) == 2
    assert any("52.9], ['Mutual Funds'" in literal for literal in overview.raw_literals)
    assert any("['Promoter', 99.9]" in literal for literal in overview.raw_literals)


def test_a_drifted_chart_literal_is_retained_not_partially_read() -> None:
    """A chart is a split of one total; reading the rows that parse would misstate it."""
    category = _breakup("category")

    assert category.status is TijoriIslandStatus.UNPARSEABLE
    assert category.entries == ()
    assert category.detail is not None
    assert "not a 2-element pair" in category.detail
    assert len(category.raw_literals) == 1
    assert "'Promoter', 52.9, 'extra'" in category.raw_literals[0]


@pytest.mark.parametrize(
    ("literal", "expected_detail"),
    [
        ("__import__('os').system('id')", "not a readable"),
        ("{'Promoter': 52.9}", "not a non-empty list"),
        ("[[52.9, 'Promoter']]", "no readable label"),
        ("[['Promoter', [1, 2]]]", "value is not a number"),
        ("[['Promoter', True]]", "value is not a number"),
        ("[['Promoter', 52.9]", "not a readable"),
    ],
)
def test_hostile_chart_literals_are_refused_by_the_shape_gate(
    literal: str, expected_detail: str
) -> None:
    """Page content is untrusted: only a list of [label, number] pairs is accepted."""
    raw = _mutated(
        "[['Promoter', 52.9], ['Institutions', 26.15]]",
        literal,
    )
    built = _parse(raw)
    trend = _breakup("trend", built)

    assert trend.status is TijoriIslandStatus.UNPARSEABLE
    assert trend.detail is not None
    assert expected_detail in trend.detail
    assert built.row("Promoter").cells[0].value == Decimal("52.9")


def test_a_deeply_nested_chart_literal_never_takes_the_page_down() -> None:
    """Nesting is a resource-exhaustion vector, so its failure mode is a refusal.

    Which exception CPython raises at depth is a version detail; that the table
    still parses and the chart is marked unreadable is the contract.
    """
    built = _parse(_mutated("[['Promoter', 52.9], ['Institutions', 26.15]]", "[" * 400 + "]" * 400))
    trend = _breakup("trend", built)

    assert trend.status is TijoriIslandStatus.UNPARSEABLE
    assert trend.entries == ()
    assert built.row("Promoter").cells[0].value == Decimal("52.9")


def test_an_oversized_chart_literal_is_refused_unparsed() -> None:
    """A literal above the parse limit is never handed to literal_eval at all."""
    oversized = "[" + ", ".join(f"['Slice {index}', 1.0]" for index in range(20000)) + "]"
    assert len(oversized) > MAX_LITERAL_CHARS
    built = _parse(_mutated("[['Promoter', 52.9], ['Institutions', 26.15]]", oversized))
    trend = _breakup("trend", built)

    assert trend.status is TijoriIslandStatus.UNPARSEABLE
    assert trend.detail is not None
    assert "above the" in trend.detail


def test_a_page_with_no_chart_scripts_still_yields_the_detailed_table() -> None:
    """The charts are additive; a page without them is not a degraded acquisition."""
    stripped = re.sub(
        r"<section id=\"(overview|trend|overview-mobile|category)\">.*?</section>",
        "",
        _FIXTURE_TEXT,
        flags=re.DOTALL,
    )
    built = _parse(stripped.encode("utf-8"))

    assert built.breakups == ()
    assert built.row("Promoter").cells[0].value == Decimal("52.9")
