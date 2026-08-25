"""Fixture-only coverage for Tijori's ancillary analysis JSON APIs.

Every test parses committed bytes; no test opens a socket. The fixtures mirror
the owner's structure capture of TITAN (company_id 81, 2026-08-25) and add the
shapes that capture proves possible but did not itself contain: a waterfall sum
row that omits its value entirely, a window key outside the published set, a
modeled key published in an unreadable shape, and a malformed series point.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_analysis import (
    build_tijori_analysis,
    reject_duplicate_anchors,
)
from fundamentals.ingest.tijori_analysis_models import (
    EMPTY_DOCUMENT_NOTE,
    TijoriAnalysisAmount,
    TijoriAnalysisError,
    TijoriAnalysisMetadata,
    TijoriAnalysisMetricIdError,
    TijoriAnalysisOutcome,
    TijoriAnalysisResponseStatusError,
    TijoriAnalysisSchemaError,
    TijoriAnalysisSection,
    TijoriAnalysisSectionBase,
    TijoriAnalysisWindow,
    TijoriBalanceSheetSnapshotSection,
    TijoriCashFlowWaterfallSection,
    TijoriFlowItem,
    TijoriFundFlowSection,
    TijoriIdentityStrength,
    TijoriOpMetricsSection,
    parse_analysis_section,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "tijori_api"
_SLUG = "titan-company-limited"
_SYMBOL = "TITAN"
_COMPANY_ID = 81
_METRIC_ID = 2448
_RETRIEVED_AT = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)
_SHA = "f" * 64
_BASE = "https://www.tijorifinance.com"

_FIXTURE_FILES = {
    TijoriAnalysisSection.FUND_FLOW: "fund_flow_analysis_data.json",
    TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT: "balance_sheet_snap_shot.json",
    TijoriAnalysisSection.CASH_FLOW_WATERFALL: "cash_flow_waterfall.json",
    TijoriAnalysisSection.OP_METRICS: "company_op_metrics.json",
}


def _body(section: TijoriAnalysisSection) -> bytes:
    """The committed synthetic response body for one API."""
    return (_FIXTURES / _FIXTURE_FILES[section]).read_bytes()


def _build(
    section: TijoriAnalysisSection,
    raw: bytes | None = None,
    *,
    metric_id: int | None = None,
    symbol: str = _SYMBOL,
    slug: str = _SLUG,
) -> TijoriAnalysisSectionBase:
    """Build one analysis artifact from committed bytes."""
    return build_tijori_analysis(
        _body(section) if raw is None else raw,
        section=section,
        slug=slug,
        symbol=symbol,
        company_id=_COMPANY_ID,
        source_url=f"{_BASE}/api/v1/ind/x/{_COMPANY_ID}/",
        content_sha256=_SHA,
        retrieved_at=_RETRIEVED_AT,
        metric_id=metric_id,
    )


def _fund_flow() -> TijoriFundFlowSection:
    """The fund-flow artifact built from the committed fixture."""
    built = _build(TijoriAnalysisSection.FUND_FLOW)
    assert isinstance(built, TijoriFundFlowSection)
    return built


def _waterfall() -> TijoriCashFlowWaterfallSection:
    """The cash-flow waterfall artifact built from the committed fixture."""
    built = _build(TijoriAnalysisSection.CASH_FLOW_WATERFALL)
    assert isinstance(built, TijoriCashFlowWaterfallSection)
    return built


def _snapshot() -> TijoriBalanceSheetSnapshotSection:
    """The balance-sheet snapshot artifact built from the committed fixture."""
    built = _build(TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT)
    assert isinstance(built, TijoriBalanceSheetSnapshotSection)
    return built


def _op_metrics() -> TijoriOpMetricsSection:
    """The op-metric artifact built from the committed fixture."""
    built = _build(TijoriAnalysisSection.OP_METRICS, metric_id=_METRIC_ID)
    assert isinstance(built, TijoriOpMetricsSection)
    return built


def test_identity_is_recorded_as_url_borne_never_as_a_response_assertion() -> None:
    """These responses assert no identity, so the artifact must not imply one."""
    metadata = _fund_flow().metadata

    assert metadata.symbol == _SYMBOL
    assert metadata.company_id == _COMPANY_ID
    assert "company_id in the request URL" in metadata.identity_basis
    assert "no identity field" in metadata.identity_basis
    # The body carries no symbol at all, so nothing in the document could have
    # corroborated the configured one.
    assert _SYMBOL not in _body(TijoriAnalysisSection.FUND_FLOW).decode("utf-8")


def test_fund_flow_keeps_every_window_key_exactly_as_published() -> None:
    """A window label is source text: renaming or normalizing it would lose the source."""
    sources = _fund_flow().groups[0]

    assert sources.name == "sources"
    assert [window.window for window in sources.windows] == ["1yr", "3yr", "15yr"]


def test_an_unpublished_window_key_is_recorded_as_drift_but_never_dropped() -> None:
    """Drift must be visible without discarding the data the source did send."""
    sources = _fund_flow().groups[0]

    assert sources.unknown_windows == ("15yr",)
    unknown = next(window for window in sources.windows if window.window == "15yr")
    assert unknown.items[0].amount.value == Decimal("51230.0")


def test_every_analysis_anchor_is_an_api_document_anchor() -> None:
    """The retrieval procedure for these values is a GET, not a page island read."""
    item = _fund_flow().groups[0].windows[0].items[0]
    anchor = item.amount.provenance

    assert anchor.anchor_type is SourceAnchorType.API_DOCUMENT
    assert anchor.document_id == "api:fund_flow_analysis_data"
    assert anchor.island_id is None
    assert anchor.table_key == "1yr"
    assert anchor.row_label == "0/sources/0/Cash from Operations"
    assert anchor.column_label == "y"


def test_position_leads_the_element_path_so_a_repeated_name_stays_addressable() -> None:
    """Nothing guarantees a unique item name, so the index must lead the address."""
    duplicated = json.dumps(
        {
            "data": {
                "1yr": [
                    {"name": "WCC", "y": 1.0},
                    {"name": "WCC", "y": 2.0},
                ]
            }
        }
    ).encode("utf-8")

    built = _build(TijoriAnalysisSection.CASH_FLOW_WATERFALL, duplicated)
    assert isinstance(built, TijoriCashFlowWaterfallSection)
    labels = [item.amount.provenance.row_label for item in built.windows[0].items]
    assert labels == ["0/WCC", "1/WCC"]


def test_the_same_item_in_two_windows_is_not_reported_as_an_anchor_collision() -> None:
    """Window is part of the address, so one item per window is two distinct values."""
    waterfall = _waterfall()

    first = waterfall.windows[0].items[0].amount.provenance
    second = waterfall.windows[1].items[0].amount.provenance
    assert first.row_label == second.row_label
    assert (first.table_key, second.table_key) == ("1yr", "3yr")


def test_two_elements_sharing_a_complete_anchor_are_fatal() -> None:
    """The backstop must make any future addressing change that collapses two
    distinct elements onto one anchor loud rather than silent."""
    metadata = TijoriAnalysisMetadata(
        section=TijoriAnalysisSection.CASH_FLOW_WATERFALL,
        document_id="api:cash_flow_waterfall",
        slug=_SLUG,
        symbol=_SYMBOL,
        company_id=_COMPANY_ID,
        metric_id=None,
        source_url=f"{_BASE}/api/v1/ind/cash_flow_waterfall/{_COMPANY_ID}/",
        file_sha256=_SHA,
        retrieved_at=_RETRIEVED_AT,
    )
    collided = _waterfall().model_copy(
        update={
            "windows": (
                TijoriAnalysisWindow(window="1yr", items=(_collided_item(metadata),)),
                TijoriAnalysisWindow(window="1yr", items=(_collided_item(metadata),)),
            )
        }
    )

    with pytest.raises(TijoriAnalysisSchemaError, match="anchors two elements identically"):
        reject_duplicate_anchors(collided)


def _collided_item(metadata: TijoriAnalysisMetadata) -> TijoriFlowItem:
    """One flow item whose anchor is deliberately not unique."""
    return TijoriFlowItem(
        name="OCF",
        amount=TijoriAnalysisAmount(
            value=Decimal("1"),
            raw_text="1",
            provenance=Provenance(
                source_id="tijori",
                file_sha256=_SHA,
                anchor_type=SourceAnchorType.API_DOCUMENT,
                context_ref=f"{metadata.source_url}#{metadata.document_id}/1yr/0/OCF/y",
                document_id=metadata.document_id,
                table_key="1yr",
                row_label="0/OCF",
                column_label="y",
                retrieved_at=_RETRIEVED_AT,
            ),
        ),
        amount_published=True,
        is_sum=False,
    )


def test_a_sum_row_without_a_value_is_never_completed_by_this_adapter() -> None:
    """The waterfall omits ``y`` on derived totals; computing one would invent data."""
    total = _waterfall().windows[0].items[2]

    assert total.name == "OCF"
    assert total.is_sum is True
    assert total.amount_published is False
    assert total.amount.value is None
    assert total.amount.raw_text == ""


def test_a_published_value_is_distinguishable_from_an_omitted_one() -> None:
    """``amount_published`` exists so a null reading never hides which case it was."""
    window = _waterfall().windows[0]

    assert [item.amount_published for item in window.items] == [True, True, False, True]


def test_a_modeled_key_published_unreadably_is_retained_not_coerced() -> None:
    """Reading ``isSum: "yes"`` as a boolean would invent a source claim."""
    dividends = _fund_flow().groups[1].windows[0].items[1]

    assert dividends.is_sum is False
    assert dividends.invalid_fields_json is not None
    assert json.loads(dividends.invalid_fields_json) == {"isSum": "yes"}


def test_an_unmodeled_item_key_is_preserved_verbatim() -> None:
    """Drift the day it appears, rather than a key silently dropped on the floor."""
    debt = _fund_flow().groups[0].windows[1].items[1]

    assert debt.unmodeled_fields_json is not None
    assert json.loads(debt.unmodeled_fields_json) == {"segment": "borrowings"}


def test_an_unmodeled_envelope_key_is_preserved_verbatim() -> None:
    """Top-level drift matters as much as element drift."""
    built = _fund_flow()

    assert built.unmodeled_fields_json is not None
    assert json.loads(built.unmodeled_fields_json) == {"generated_at": "2026-08-25T00:00:00Z"}


def test_the_body_status_field_is_recorded_beside_the_transport_status() -> None:
    """Tijori publishes its own status; it is metadata, never a substitute for HTTP."""
    assert _fund_flow().metadata.response_status == 200
    assert _op_metrics().metadata.response_status is None


def test_snapshot_numbers_read_through_the_shared_tijori_cell_rule() -> None:
    """A thousands comma reads; anything else keeps its lexeme beside a null value."""
    assets = _snapshot().sides[0]

    assert assets.field_name == "assets"
    assert assets.entries[1].amount.value == Decimal("1205.50")
    assert assets.entries[1].amount.raw_text == "1,205.50"
    assert assets.entries[2].amount.value is None
    assert assets.entries[2].amount.raw_text == "NA"


def test_snapshot_anchors_name_the_side_they_were_read_from() -> None:
    """A line means nothing without knowing which side of the sheet it sat on."""
    anchor = _snapshot().sides[1].entries[0].amount.provenance

    assert anchor.document_id == "api:balance_sheet_snap_shot"
    assert anchor.table_key == "1/liabilities"
    assert anchor.row_label == "0/Equity"
    assert anchor.column_label == "value"


def test_op_metrics_keeps_a_malformed_point_and_counts_it() -> None:
    """A point whose shape is not [timestamp, value] is recorded, never dropped."""
    built = _op_metrics()

    assert built.metric_id == _METRIC_ID
    assert built.element_count == 4
    assert built.malformed_point_count == 1
    assert built.points[0].timestamp_ms == 1767139200000
    assert built.points[0].value == Decimal("8.0")
    assert built.points[3].timestamp_ms is None
    assert built.points[3].raw_value_text == '["not-a-point"]'


def test_op_metrics_anchors_the_whole_series_under_its_metric_id() -> None:
    """One anchor per series; a point stays traceable by its index within it."""
    anchor = _op_metrics().series_provenance

    assert anchor.document_id == "api:company_op_metrics"
    assert anchor.table_key == f"metric:{_METRIC_ID}"
    assert anchor.row_label == "series"
    assert anchor.column_label == "data"


def test_op_metrics_without_a_metric_id_is_refused_before_anything_is_built() -> None:
    """The URL needs the id, so an artifact without one could not be re-found."""
    with pytest.raises(TijoriAnalysisMetricIdError, match="needs --metric-id"):
        _build(TijoriAnalysisSection.OP_METRICS)


@pytest.mark.parametrize(
    ("section", "body"),
    [
        (TijoriAnalysisSection.FUND_FLOW, b'{"data": [], "status": 200}'),
        (TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT, b'{"data": [], "status": 200}'),
        (TijoriAnalysisSection.CASH_FLOW_WATERFALL, b'{"data": {}, "status": 200}'),
        # Structurally present but empty: the window exists and holds no items.
        (TijoriAnalysisSection.CASH_FLOW_WATERFALL, b'{"data": {"1yr": []}, "status": 200}'),
        (
            TijoriAnalysisSection.FUND_FLOW,
            b'{"data": [{"name": "sources", "data": {"1yr": []}}], "status": 200}',
        ),
        (
            TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT,
            b'{"data": [{"field_name": "assets", "data": []}], "status": 200}',
        ),
    ],
)
def test_an_empty_document_is_an_answer_not_a_failure(
    section: TijoriAnalysisSection, body: bytes
) -> None:
    """Tijori serves an empty document for a company it has no such data for.

    Emptiness is decided by the element count, so a container that exists but
    holds nothing reports the same outcome as one that was served empty.
    """
    built = _build(section, body)

    assert built.element_count == 0
    assert built.outcome is TijoriAnalysisOutcome.OK_EMPTY
    assert built.note == EMPTY_DOCUMENT_NOTE


@pytest.mark.parametrize(
    ("section", "body"),
    [
        (TijoriAnalysisSection.FUND_FLOW, b'{"status": 200}'),
        (TijoriAnalysisSection.BALANCE_SHEET_SNAPSHOT, b'{"status": 200}'),
        (TijoriAnalysisSection.CASH_FLOW_WATERFALL, b'{"status": 200}'),
        (TijoriAnalysisSection.OP_METRICS, b'{"peers": []}'),
    ],
)
def test_a_document_with_no_data_key_is_drift_not_an_empty_result(
    section: TijoriAnalysisSection, body: bytes
) -> None:
    """An omitted payload must never be reported as a successful empty answer."""
    with pytest.raises(TijoriAnalysisSchemaError, match="an absent payload is drift"):
        _build(section, body, metric_id=_METRIC_ID)


@pytest.mark.parametrize("status", [500, 403, 404, 302])
def test_a_non_success_body_status_is_refused_and_named(status: int) -> None:
    """Tijori answers some failures with HTTP 200 and a failing status in the body."""
    body = json.dumps({"status": status, "data": []}).encode("utf-8")

    with pytest.raises(TijoriAnalysisResponseStatusError, match=f"status {status}"):
        _build(TijoriAnalysisSection.FUND_FLOW, body)


@pytest.mark.parametrize("status", ['"200"', "true", "null", "{}"])
def test_a_malformed_body_status_is_refused_rather_than_ignored(status: str) -> None:
    """Reading an unparseable status as absent would re-open the error-envelope hole."""
    body = f'{{"status": {status}, "data": []}}'.encode()

    with pytest.raises(TijoriAnalysisResponseStatusError, match="non-integer"):
        _build(TijoriAnalysisSection.FUND_FLOW, body)


def test_a_group_that_omits_its_payload_is_drift_not_an_empty_group() -> None:
    """The same wrong-but-plausible empty applies one level below the envelope."""
    body = b'{"data": [{"name": "sources"}], "status": 200}'

    with pytest.raises(TijoriAnalysisSchemaError, match="an absent payload is drift"):
        _build(TijoriAnalysisSection.FUND_FLOW, body)


def test_a_populated_document_reports_the_ok_outcome() -> None:
    """The outcome must distinguish a real acquisition from a verified empty one."""
    built = _fund_flow()

    assert built.outcome is TijoriAnalysisOutcome.OK
    assert built.note is None


def test_identity_strength_records_that_only_the_url_bound_this_document() -> None:
    """A consumer must not treat URL-only identity as page-verified identity."""
    assert _fund_flow().metadata.identity_strength is TijoriIdentityStrength.CONFIGURED_URL_ONLY


def test_an_empty_op_metric_series_is_an_answer_not_a_failure() -> None:
    """A metric with no history is data about the company, not a broken fetch."""
    built = _build(TijoriAnalysisSection.OP_METRICS, b'{"peers": [], "data": []}', metric_id=1)

    assert isinstance(built, TijoriOpMetricsSection)
    assert built.element_count == 0
    assert built.outcome is TijoriAnalysisOutcome.OK_EMPTY
    assert built.note == EMPTY_DOCUMENT_NOTE


def test_an_unnameable_element_is_fatal() -> None:
    """Every downstream selection on an unaddressable element would be ambiguous."""
    nameless = b'{"data": {"1yr": [{"y": 1.0}]}, "status": 200}'

    with pytest.raises(TijoriAnalysisSchemaError, match="name must be a non-empty string"):
        _build(TijoriAnalysisSection.CASH_FLOW_WATERFALL, nameless)


@pytest.mark.parametrize(
    ("section", "body", "match"),
    [
        (TijoriAnalysisSection.FUND_FLOW, b'{"data": {}, "status": 200}', "data must be a list"),
        (
            TijoriAnalysisSection.CASH_FLOW_WATERFALL,
            b'{"data": [], "status": 200}',
            "data must be an object",
        ),
        (TijoriAnalysisSection.FUND_FLOW, b"[]", "document .* must be an object"),
    ],
)
def test_a_document_shaped_against_the_contract_is_fatal(
    section: TijoriAnalysisSection, body: bytes, match: str
) -> None:
    """A shape this contract cannot address must fail loudly, not parse to nothing."""
    with pytest.raises(TijoriAnalysisSchemaError, match=match):
        _build(section, body)


def test_a_non_json_body_is_refused_with_the_document_named() -> None:
    """An HTML error page served with HTTP 200 must not be read as an empty result."""
    with pytest.raises(TijoriAnalysisSchemaError, match="is not decodable JSON"):
        _build(TijoriAnalysisSection.FUND_FLOW, b"<html>login</html>")


@pytest.mark.parametrize(("slug", "symbol"), [("", _SYMBOL), (_SLUG, " ")])
def test_an_empty_configured_identifier_is_refused(slug: str, symbol: str) -> None:
    """The URL identity is the only identity here, so a blank one cannot be trusted."""
    with pytest.raises(TijoriAnalysisSchemaError, match="is empty"):
        _build(TijoriAnalysisSection.FUND_FLOW, slug=slug, symbol=symbol)


def test_an_unsupported_section_name_names_the_supported_set() -> None:
    """A caller typo must not silently select a different API."""
    with pytest.raises(TijoriAnalysisError, match="supported sections"):
        parse_analysis_section("fund_flows")


def test_every_modeled_section_parses_its_committed_fixture() -> None:
    """Breadth guard: a new section must ship with a fixture that actually parses."""
    for section in TijoriAnalysisSection:
        built = _build(section, metric_id=_METRIC_ID)
        assert built.section is section


def test_both_tijori_surfaces_read_a_series_through_the_same_reader() -> None:
    """A point read from a page and one read from an API must not drift apart.

    The overview family and the analysis family both delegate to
    ``tijori_series``; this pins that they still do, so a future fix to epoch or
    value handling cannot land on one surface only.
    """
    from fundamentals.ingest import tijori_analysis, tijori_overview_common, tijori_series

    assert tijori_analysis.read_series is tijori_series.read_series
    assert tijori_overview_common.read_series is tijori_series.read_series
    assert not hasattr(tijori_analysis, "_series_point")
    assert not hasattr(tijori_overview_common, "_series_point")

    raw = [[1767139200000, "1,205.50"], "malformed"]
    overview_points, overview_malformed = tijori_overview_common.series(raw, label="overview")
    api_points, api_malformed = tijori_series.read_series(
        raw, label="api", drift_event="tijori_analysis_series_points_unmodeled"
    )
    assert overview_points == api_points
    assert overview_malformed == api_malformed == 1
