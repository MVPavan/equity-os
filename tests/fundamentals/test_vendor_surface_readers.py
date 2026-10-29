"""G0 adapters exercised through the registry on retained subscriber responses."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from vendor_surface_support import INDEX, capture_response, retained

from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_parse import PARSERS, Body
from fundamentals.ingest.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from fundamentals.store.snapshot_store import SnapshotStore


def parse(site, surface, body, context):
    return PARSERS[Site.SCREENER if site == "screener" else Site.TIJORI, surface].parse(
        body, context
    )


@pytest.mark.parametrize("symbol", ["APARINDS", "ANONDITA"])
@pytest.mark.parametrize(
    "surface",
    [
        "section-quarters",
        "section-profit-loss",
        "section-balance-sheet",
        "section-cash-flow",
        "section-ratios",
        "section-shareholding",
    ],
)
def test_statement_readers(surface, symbol):
    body, context = retained("screener", "company-page", symbol)
    values = parse("screener", surface, body, context)
    assert values and any(cell.value is not None for cell in values)
    assert all(cell.basis == "standalone" for cell in values)
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)
    if symbol == "APARINDS" and surface == "section-quarters":
        assert values[0].value == Decimal("3500")
        assert values[1].value == Decimal("3644")


@pytest.mark.parametrize(
    "surface",
    [
        "quick-ratios-api",
        "peers-api",
        "related-party",
        "schedules-api",
        "investors-api",
        "segments-api",
    ],
)
@pytest.mark.pg
def test_fragment_readers(surface, pg_db, tmp_path):
    body, context = retained("screener", surface)
    if surface == "peers-api":
        context = context.model_copy(update={"basis": Basis.CONSOLIDATED})
    if surface in ("schedules-api", "segments-api", "investors-api"):
        from fundamentals.ingest.vendor_surface_expand import EXPANSIONS
        from fundamentals.ingest.vendor_surface_specs import load_specs

        basis = "consolidated"
        page, page_context = retained("screener", "company-page", context.ids.nse_symbol, basis)
        spec = next(
            s
            for s in load_specs(
                Path("config/vendor_surface/surfaces.yaml"),
                Path("docs/research/vendor-surface/catalog.yaml"),
            )
            if s.id == surface and s.site is Site.SCREENER
        )
        requests = EXPANSIONS[spec.expand](
            page, page_context.model_copy(update={"parent": {"spec": spec.model_dump()}})
        )
        request = next(r for r in requests if r.url == context.url)
        context = context.model_copy(update={"parent": request.parent, "basis": request.basis})
    values = parse("screener", surface, body, context)
    assert values
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)

    checked = {
        "schedules-api": ("reader/sub_rows", 0, (0, 1), (Decimal("171"), Decimal("287"))),
        "investors-api": ("reader/holders", 0, (0, 1), (Decimal("11.20"), Decimal("11.20"))),
        "segments-api": ("reader/lines/0", 1, (5, 6), (Decimal("451355"), Decimal("320008"))),
    }
    if surface in checked:
        from fundamentals.ingest.vendor_surface_capture import Request

        with pg_db.runtime_pool() as pool:
            ref = capture_response(
                pool,
                SnapshotStore(tmp_path),
                tmp_path,
                Request(
                    spec=spec,
                    url=context.url,
                    ids=context.ids,
                    basis=context.basis,
                    parent=context.parent,
                    due_since=None,
                ),
                body.raw,
            )
            with pool.connection() as conn:
                status = conn.execute(
                    "SELECT status FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                    (ref.capture_ref_id,),
                ).fetchone()[0]
                assert status in ("OK", "PARTIAL")
                key, row, columns, expected = checked[surface]
                actual = conn.execute(
                    (
                        "SELECT value FROM eqos.vendor_values WHERE capture_ref_id=%s AND tab"
                        "le_key=%s AND row_index=%s AND column_index=ANY(%s) ORDER BY column_"
                        "index"
                    ),
                    (ref.capture_ref_id, key, row, list(columns)),
                ).fetchall()
                assert actual == [(value,) for value in expected]


@pytest.mark.parametrize("symbol", ["APARINDS", "ANONDITA"])
@pytest.mark.parametrize(
    "surface",
    [
        "company-overview",
        "overview-custom-ratios",
        "overview-custom-financials",
        "overview-forensics",
        "overview-marketshare",
        "overview-revenuemix",
        "overview-competitors",
        "overview-corporateactions",
        "company-financials",
        "financials-growth-table",
        "financials-balance-sheet",
        "financials-profit-and-loss",
        "financials-cash-flow",
        "financials-ratios",
        "financials-quarterly-results",
        "company-shareholding",
        "shareholding-detailed",
    ],
)
def test_tijori_page_readers(surface, symbol):
    parent = (
        "company-overview"
        if surface in ("company-overview",) or surface.startswith("overview-")
        else "company-shareholding"
        if surface in ("company-shareholding", "shareholding-detailed")
        else "company-financials"
    )
    body, context = retained("tijori", parent, symbol)
    if symbol == "ANONDITA" and surface in (
        "overview-marketshare",
        "company-shareholding",
        "shareholding-detailed",
    ):
        from fundamentals.ingest.tijori_overview_models import TijoriOverviewSectionAbsentError
        from fundamentals.ingest.tijori_shareholding_table import TijoriShareholdingSchemaError

        refusal = (
            TijoriOverviewSectionAbsentError
            if surface == "overview-marketshare"
            else TijoriShareholdingSchemaError
        )
        reason = "not available" if surface == "overview-marketshare" else "repeats node id"
        with pytest.raises(refusal, match=reason):
            parse("tijori", surface, body, context)
        return
    values = parse("tijori", surface, body, context.model_copy(update={"basis": None}))
    assert values
    assert len({(v.table_key, v.row_index, v.column_index) for v in values}) == len(values)
    if symbol == "ANONDITA" and surface == "financials-quarterly-results":
        assert any(v.padded and v.value == 0 for v in values)


@pytest.mark.parametrize(
    "surface",
    [
        "fund-flow-api",
        "cash-flow-waterfall-api",
        "balance-sheet-snapshot-api",
        "op-metrics-api",
        "company-timeline-api",
        "quarterly-results",
        "upcoming-events",
    ],
)
def test_tijori_api_readers(surface):
    body, context = retained("tijori", surface)
    context = context.model_copy(update={"parent": {"metric_id": 126}, "basis": None})
    assert parse("tijori", surface, body, context)


def record(pg_db, tmp_path, site, surface, body, context, status=200):
    store = SnapshotStore(tmp_path)
    with pg_db.runtime_pool() as pool:
        capture_response(
            pool,
            store,
            tmp_path,
            Request(
                spec=SurfaceSpec(
                    site=site,
                    id=surface,
                    scope=Scope.COMPANY,
                    path="/fixture/",
                    group=ParseGroup.READER,
                    cadence=Cadence.DAILY,
                ),
                url=context.url,
                ids=context.ids,
                basis=context.basis,
                parent=context.parent,
                due_since=None,
            ),
            body.raw,
            status,
        )
        with pool.connection() as conn:
            return conn.execute(
                "SELECT status,detail,parser_version FROM eqos.vendor_outcomes ORDER BY id"
            ).fetchall()


@pytest.mark.pg
def test_namespaced_search_outcomes(pg_db, tmp_path):
    for site in (Site.SCREENER, Site.TIJORI):
        body, context = retained(
            "screener" if site == Site.SCREENER else "tijori", "company-search-api"
        )
        outcomes = record(
            pg_db,
            tmp_path,
            site,
            "company-search-api",
            body,
            context.model_copy(update={"basis": None}),
        )
    assert [(s, v) for s, _, v in outcomes] == [
        ("OK", "screener:company-search-api.reader.v1"),
        ("FAILED", "tijori:company-search-api.reader.v1"),
    ]
    assert (Site.TIJORI, "filter-advanced-search-api") not in PARSERS
    assert (
        PARSERS[Site.TIJORI, "overview-company-timeline-sidepanel"].version
        == "tijori:overview-company-timeline-sidepanel.v1"
    )


@pytest.mark.pg
@pytest.mark.parametrize("case", ["empty", "missing", "unreadable"])
def test_recorded_reader_states(pg_db, tmp_path, case):
    if case == "empty":
        body, context = retained("screener", "company-page", "NETWEB", "consolidated")
        site, surface, expected = Site.SCREENER, "company-consolidated-empty-shell", "EMPTY"
    elif case == "missing":
        body, context = retained("tijori", "company-overview", "APARINDS")
        context = context.model_copy(
            update={
                "ids": context.ids.model_copy(update={"tijori_company_id": None}),
                "basis": None,
            }
        )
        site, surface, expected = Site.TIJORI, "company-overview", "FAILED"
    else:
        body, context = retained("screener", "company-page", "APARINDS")
        root = body.tree()
        cell = root.xpath(
            "//section[@id='quarters']//table[contains(@class,'data-table')]//tr[td]/td[2]"
        )[0]
        cell.clear()
        cell.text = "unreadable"
        from lxml import etree

        body = Body(raw=etree.tostring(root))
        site, surface, expected = Site.SCREENER, "section-quarters", "PARTIAL"
    outcomes = record(pg_db, tmp_path, site, surface, body, context)
    assert outcomes[0][0] == expected
    if case == "missing":
        assert outcomes[0][1] == "ReaderError"


def test_cell_addresses_survive_label_changes():
    from lxml import etree

    body, context = retained("screener", "company-page", "APARINDS")
    before = parse("screener", "section-quarters", body, context)
    label = body.tree().xpath("//section[@id='quarters']//tr[td]/td[1]")[0]
    label.clear()
    label.text = "Renamed row"
    after = parse("screener", "section-quarters", Body(raw=etree.tostring(body.tree())), context)
    assert [(v.table_key, v.row_index, v.column_index) for v in before] == [
        (v.table_key, v.row_index, v.column_index) for v in after
    ]
    assert before[0].locator.startswith("#quarters:data-table/")
    assert before[0].row_label != after[0].row_label


@pytest.mark.pg
@pytest.mark.parametrize(
    "surface",
    [
        "financials-balance-sheet-snapshot",
        "financials-fundflow-analysis",
        "financials-cash-flow-analysis",
    ],
)
def test_widget_shells_are_kept_not_parsed(pg_db, tmp_path, surface):
    """Empty chart containers on the page; their data is the analysis APIs (G4)."""
    body, context = retained("tijori", "company-financials", "APARINDS")
    outcomes = record(
        pg_db, tmp_path, Site.TIJORI, surface, body, context.model_copy(update={"basis": None})
    )
    assert outcomes[0][0] == "KEPT"


@pytest.mark.pg
def test_corporate_action_modal_requires_retained_200(pg_db, tmp_path):
    rows = [r for r in json.loads(INDEX.read_text()) if r["id"] == "corporate-actions-modal"]
    assert not any(r["status"] == 200 and r["kind"] == "response" for r in rows)
    _, context = retained("screener", "company-page", "HDFCBANK", "consolidated")
    context = context.model_copy(update={"url": rows[0]["url"]})
    outcomes = record(
        pg_db,
        tmp_path,
        Site.SCREENER,
        "corporate-actions-modal",
        Body(raw=b""),
        context,
        status=302,
    )
    assert outcomes[0][0] == "UNUSABLE"


def test_growth_rows_keep_source_positions():
    body, context = retained("screener", "company-page", "APARINDS")
    values = parse("screener", "section-profit-loss", body, context)
    growth = [v for v in values if "ranges-table" in v.table_key]
    assert growth
    assert all(v.column_index == 0 for v in growth)
    assert growth[0].row_index == 1


def test_popup_expands_nested_financial_rows():
    from fundamentals.ingest.vendor_surface_expand import tijori_popup_fields
    from fundamentals.ingest.vendor_surface_specs import load_specs

    body, context = retained("tijori", "company-financials", "HDFCBANK")
    spec = next(
        s
        for s in load_specs(
            Path("config/vendor_surface/surfaces.yaml"),
            Path("docs/research/vendor-surface/catalog.yaml"),
        )
        if s.id == "financials-popup-chart-api"
    )
    requests = tijori_popup_fields(
        body, context.model_copy(update={"parent": {"spec": spec.model_dump()}})
    )
    assert len(requests) == 20
    assert len({r.url for r in requests}) == 20


def test_reader_logs_exclude_vendor_text():
    import structlog.testing

    body, context = retained("tijori", "company-overview", "APARINDS")
    body = Body(
        raw=body.raw.replace(b'"company_id":', b'"vendor-private-sentinel":1,"company_id":')
    )
    with structlog.testing.capture_logs() as logs:
        assert parse("tijori", "company-overview", body, context)
    assert logs
    assert "vendor-private-sentinel" not in str(logs)
    assert all(set(event) <= {"event", "site", "surface", "log_level"} for event in logs)


def test_retained_hdfc_segment_reconciliation_refusal():
    from fundamentals.ingest.screener_company_models import SegmentReconciliationError
    from fundamentals.ingest.vendor_surface_expand import screener_segments
    from fundamentals.ingest.vendor_surface_specs import load_specs

    body, context = retained("screener", "segments-api", "HDFCBANK", "consolidated")
    page, parent = retained("screener", "company-page", "HDFCBANK", "consolidated")
    spec = next(
        s
        for s in load_specs(
            Path("config/vendor_surface/surfaces.yaml"),
            Path("docs/research/vendor-surface/catalog.yaml"),
        )
        if s.id == "segments-api"
    )
    request = next(
        r
        for r in screener_segments(
            page, parent.model_copy(update={"parent": {"spec": spec.model_dump()}})
        )
        if r.url == context.url
    )
    with pytest.raises(SegmentReconciliationError):
        parse(
            "screener",
            "segments-api",
            body,
            context.model_copy(update={"parent": request.parent, "basis": request.basis}),
        )


def outcome(values):
    """The capture's reader-outcome rule, applied to converted values."""
    if any(v.expected_numeric and v.value is None for v in values):
        return "PARTIAL"
    return "OK" if values else "EMPTY"


def unreadable(cell):
    return cell.model_copy(update={"raw_text": "unreadable", "value": None})


@pytest.mark.parametrize("surface", ["quarterly-results", "company-timeline-api"])
def test_event_measurements_expect_numbers(surface):
    from fundamentals.ingest.vendor_surface_readers import reader_values, tijori_reader

    body, context = retained("tijori", surface)
    document = tijori_reader(surface, body, context.model_copy(update={"basis": None}))
    if surface == "quarterly-results":
        item, metric = next(
            (i, m) for i in document.items for m in i.headline_metrics if m.cell.value is not None
        )
        metric = metric.model_copy(update={"cell": unreadable(metric.cell)})
        item = item.model_copy(update={"headline_metrics": (metric,), "rows": ()})
        document = document.model_copy(update={"items": (item,)})
    else:
        event, table, row, cell = next(
            (e, t, r, c)
            for e in document.events
            for t in e.detail_tables
            for r in t.rows
            for c in r.cells
            if t.column_labels and c.value is not None
        )
        row = row.model_copy(update={"cells": (unreadable(cell),)})
        table = table.model_copy(update={"rows": (row,)})
        event = event.model_copy(update={"detail_tables": (table,)})
        document = document.model_copy(update={"events": (event,)})
    values = reader_values(document)
    assert [v.expected_numeric for v in values if v.raw_text == "unreadable"] == [True]
    assert outcome(values) == "PARTIAL"


def test_quarantined_screener_row_is_kept():
    from lxml import etree

    body, context = retained("screener", "company-page", "APARINDS")
    root = body.tree()
    row = root.xpath("//section[@id='quarters']//table[contains(@class,'data-table')]//tr[td]")[0]
    etree.SubElement(row, "td").text = "1"
    values = parse("screener", "section-quarters", Body(raw=etree.tostring(root)), context)
    kept = [v for v in values if v.table_key.endswith(":quarantined")]
    assert len(kept) == len(row.xpath("td")) - 1  # every period lexeme, the label excluded
    assert all(v.value is None and v.expected_numeric for v in kept)
    assert outcome(values) == "PARTIAL"


def test_unaligned_tijori_shareholding_is_partial():
    from fundamentals.ingest.vendor_surface_readers import reader_values, tijori_reader

    body, context = retained("tijori", "company-shareholding", "APARINDS")
    document = tijori_reader("company-shareholding", body, context)
    row = document.rows[0]
    row = row.model_copy(
        update={"cells": (), "unaligned_raw_values": tuple(c.raw_text for c in row.cells)}
    )
    values = reader_values(document.model_copy(update={"rows": (row,)}))
    assert len(values) == len(document.rows[0].cells)
    assert outcome(values) == "PARTIAL"


def test_absent_forensic_count_keeps_positions():
    from fundamentals.ingest.vendor_surface_readers import reader_values, tijori_reader

    body, context = retained("tijori", "company-overview", "APARINDS")
    (document,) = tijori_reader("overview-forensics", body, context)
    counts = document.quick_look.counts
    assert counts is not None and counts.green is not None and counts.red is not None
    absent = document.model_copy(
        update={
            "quick_look": document.quick_look.model_copy(
                update={"counts": counts.model_copy(update={"green": None})}
            )
        }
    )

    def red(doc):
        return next(
            v.column_index
            for v in reader_values((doc,))
            if v.table_key == "reader/0/counts" and v.value == counts.red
        )

    assert red(absent) == red(document) == 1
    assert outcome(reader_values((absent,))) == outcome(reader_values((document,)))


# Exact positional cells read by code from the retained event bodies.
EVENT_CELLS = {
    "quarterly-results": [
        ("reader/items/0/metrics", 0, 0, "₹30.00 Cr.", Decimal("30.00"), "₹ Cr.", True),
        ("reader/items/0/rows", 1, 0, "24.27%", Decimal("24.27"), "%", True),
        ("reader/items/1/rows", 4, 0, "-135 bps", Decimal("-135"), "bps", True),
        ("reader/items/0/rows", 0, 0, "-", None, None, False),
    ],
    "company-timeline-api": [
        ("reader/events/10/tables/0", 0, 1, "9.35%", Decimal("9.35"), "%", True),
        ("reader/events/10/tables/0", 0, 3, "95131", Decimal("95131"), None, True),
        ("reader/events/17/tables/0", 0, 1, "-", None, None, False),
        ("reader/events/10/tables/0", 0, 0, "Sales", None, None, False),
    ],
}


@pytest.mark.pg
@pytest.mark.parametrize("surface", ["quarterly-results", "company-timeline-api"])
def test_retained_event_measurements_are_ok(pg_db, tmp_path, surface):
    body, context = retained("tijori", surface)
    context = context.model_copy(update={"basis": None})
    values = parse("tijori", surface, body, context)
    assert outcome(values) == "OK"
    assert PARSERS[Site.TIJORI, surface].version == f"tijori:{surface}.reader.v2"
    assert record(pg_db, tmp_path, Site.TIJORI, surface, body, context)[0][0] == "OK"
    positions = {(v.table_key, v.row_index, v.column_index): v for v in values}
    for table, row, column, raw, value, unit, numeric in EVENT_CELLS[surface]:
        cell = positions[table, row, column]
        assert (cell.raw_text, cell.value, cell.unit, cell.expected_numeric) == (
            raw,
            value,
            unit,
            numeric,
        )


@pytest.mark.pg
@pytest.mark.parametrize("surface", ["quarterly-results", "company-timeline-api"])
def test_unreadable_event_measurement_stays_partial(pg_db, tmp_path, surface):
    body, context = retained("tijori", surface)
    context = context.model_copy(update={"basis": None})
    original = next(
        v.raw_text
        for v in parse("tijori", surface, body, context)
        if v.expected_numeric and v.raw_text.endswith("%")
    )
    assert original.encode() in body.raw
    body = Body(raw=body.raw.replace(original.encode(), b"12?3%", 1))
    values = parse("tijori", surface, body, context)
    (cell,) = [v for v in values if v.raw_text == "12?3%"]
    assert cell.value is None and cell.expected_numeric
    assert record(pg_db, tmp_path, Site.TIJORI, surface, body, context)[0][0] == "PARTIAL"
