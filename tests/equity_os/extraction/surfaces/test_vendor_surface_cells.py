"""Retained G3 cells survive registration with positional identity and label evidence."""

import hashlib
import io
import json
from decimal import Decimal
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr

from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS
from equity_os.sourcing.surfaces.vendor_surface_capture import Request, capture
from equity_os.sourcing.surfaces.vendor_surface_fetch import (
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from equity_os.sourcing.surfaces.vendor_surface_specs import Cadence, ParseGroup, Scope, SurfaceSpec
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import VendorValuesStore

# Hand-read from the retained bodies' DOM: (table, row, column, label, raw text, value, unit).
EXACT = {
    ("APARINDS", "section-insights"): (
        "yearly-insights",
        0,
        1,
        "Conductor Division Order Book",
        "1,751",
        Decimal("1751"),
        "₹ crores",
    ),
    ("HDFCBANK", "benchmarking-benchmarking-financial"): (
        "benchmark-financial",
        2,
        1,
        "Cost To Income Ratio",
        "39.1 %",
        Decimal("39.1"),
        "%",
    ),
    ("HDFCLIFE", "benchmarking-benchmarking-business"): (
        "business-charts:0",
        0,
        1,
        "Non Participating Funds",
        "51.6",
        Decimal("51.6"),
        None,
    ),
    ("CREDITACC", "company-compare"): ("compare:2", 4, 2, "OPM %", "68%", Decimal("68"), "%"),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("symbol", ["APARINDS", "HDFCBANK", "HDFCLIFE", "CREDITACC"])
def test_retained_cells_and_label_evidence(pg_db, tmp_path, monkeypatch, symbol):
    rows = json.loads(Path("docs/research/vendor-surface/kinds-index.json").read_text())
    rows += json.loads(Path("docs/research/vendor-surface/snapshots-index.json").read_text())
    store = SnapshotStore(tmp_path / "captures")
    with pg_db.runtime_pool() as pool:
        locks = PgSiteLock(pool)
        try:
            for site, surface, parent in [
                (Site.SCREENER, "section-insights", "company-page"),
                (Site.TIJORI, "benchmarking-benchmarking-financial", "company-benchmarking"),
                (Site.TIJORI, "benchmarking-benchmarking-business", "company-benchmarking"),
                (Site.SCREENER, "company-compare", "company-compare"),
            ]:
                entry = PARSERS[site, surface]
                row = next(
                    r
                    for r in rows
                    if r["site"] == ("screener" if site == Site.SCREENER else "tijori")
                    and r["id"] == parent
                    and (r.get("symbol") == symbol or parent == "company-compare")
                )
                raw = Path(row["path"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == row["sha256"]

                def opened(self, request, timeout, row=row, raw=raw):
                    return HTTPError(row["url"], 200, "fixture", Message(), io.BytesIO(raw))

                monkeypatch.setattr(OpenerDirector, "open", opened)
                session = SiteSession(
                    site=site, session_cookie=SecretStr("synthetic"), cookie_name="sessionid"
                )
                fetcher = VendorFetcher(
                    store,
                    {site: session},
                    OpenerDirector(),
                    tmp_path / "stops",
                    locks,
                    spacing_seconds=0,
                )
                spec = SurfaceSpec(
                    site=site,
                    id=surface,
                    scope=Scope.COMPANY,
                    path="/",
                    group=ParseGroup.CELLS,
                    cadence=Cadence.WEEKLY,
                )
                ref, _ = capture(
                    fetcher,
                    store,
                    pool,
                    VendorValuesStore(pool),
                    Request(spec=spec, url=row["url"], ids=None, due_since=None),
                )
                with pool.connection() as conn:
                    status, count = conn.execute(
                        "SELECT status,row_count FROM eqos.vendor_outcomes "
                        "WHERE capture_ref_id=%s AND surface=%s",
                        (ref.capture_ref_id, surface),
                    ).fetchone()
                    cells = conn.execute(
                        "SELECT table_key,row_index,column_index,raw_text,value,"
                        "expected_numeric,basis "
                        "FROM eqos.vendor_values WHERE capture_ref_id=%s AND outcome_id IN "
                        "(SELECT id FROM eqos.vendor_outcomes WHERE surface=%s)",
                        (ref.capture_ref_id, surface),
                    ).fetchall()
                    if (symbol, surface) in EXACT:
                        table, row_index, column, *expected = EXACT[symbol, surface]
                        assert conn.execute(
                            "SELECT row_label,raw_text,value,unit FROM eqos.vendor_values "
                            "WHERE capture_ref_id=%s AND table_key=%s AND row_index=%s "
                            "AND column_index=%s",
                            (ref.capture_ref_id, table, row_index, column),
                        ).fetchone() == tuple(expected)
                # The compound "High / Low" peer cells cannot be read as one scalar.
                assert status == ("PARTIAL" if surface == "company-compare" else "OK")
                assert count == len(cells) > 0
                assert len({c[:3] for c in cells}) == count
                assert any(c[4] is not None for c in cells)
                assert all(c[4] is None and not c[5] for c in cells if c[3].lower() == "n/a")
                from equity_os.extraction.surfaces.vendor_surface_cells import cell_labels

                samples = cell_labels(pool, site, surface)
                assert samples and entry.version.endswith(f":{surface}.v4")
                if surface == "company-compare":
                    assert any(s.per_share for s in samples)
                if surface == "section-insights":
                    assert {c[0] for c in cells} == {"yearly-insights"}
                    assert any(s.units for s in samples)
                    if symbol == "HDFCBANK":
                        assert {c[6] for c in cells} == {"standalone"}
                    if symbol == "HDFCLIFE":
                        assert any("Persistency" in s.label for s in samples)
                if surface == "benchmarking-benchmarking-business":
                    assert {c[0].split(":")[0] for c in cells} == {
                        "business-cards",
                        "business-charts",
                    }
        finally:
            locks.close()


def test_business_positions_keep_duplicate_labels_and_missing_cells():
    from equity_os.extraction.surfaces.vendor_surface_cells import benchmark_business_cards
    from equity_os.extraction.surfaces.vendor_surface_parse import Body

    tree = Body(
        raw=b'<section id="benchmarking-business"><table><thead><tr><th></th>'
        b"<th>Peer</th></tr></thead><tbody><tr><td>Repeat</td><td>12.50</td></tr>"
        b"<tr><td>Repeat</td><td>n/a</td></tr></tbody></table></section>"
    ).tree()
    cells = benchmark_business_cards(tree)
    assert [(c.row_index, c.column_index) for c in cells] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert {c.row_label for c in cells} == {"Repeat"}
    assert [c.value for c in cells] == [None, Decimal("12.50"), None, None]
    assert cells[3].raw_text == "n/a" and not cells[3].expected_numeric


def test_descriptor_columns_and_missing_markers_stay_out_of_label_units():
    from equity_os.extraction.surfaces.vendor_surface_cells import (
        LabelSample,
        label_samples,
        screener_compare,
    )
    from equity_os.extraction.surfaces.vendor_surface_parse import Body

    body = Body(
        raw=b'<table><thead><tr><th class="text"></th><th class="text"></th><th>Mar 2025</th>'
        b'</tr></thead><tbody><tr><td class="text">OPM %</td><td>Acme</td><td>12%</td></tr>'
        b'<tr><td class="text">OPM %</td><td>Beta</td><td>n/a</td></tr>'
        b'<tr><td class="text">Tax %</td><td>Acme</td><td>12?3%</td></tr></tbody></table>'
    )
    cells = screener_compare(body, None)
    assert [(c.column_index, c.value, c.expected_numeric) for c in cells if c.column_index] == [
        (1, None, False),
        (2, Decimal("12"), True),
        (1, None, False),
        (2, None, False),
        (1, None, False),
        (2, None, True),
    ]
    assert label_samples((c.row_label, c.unit, c.expected_numeric) for c in cells) == (
        LabelSample(label="OPM %", units=frozenset({"%"}), per_share=False),
        LabelSample(label="Tax %", units=frozenset({""}), per_share=False),
    )


def test_business_chart_preserves_numeric_token():
    from equity_os.extraction.surfaces.vendor_surface_cells import benchmark_business_charts
    from equity_os.extraction.surfaces.vendor_surface_parse import Body

    body = Body(
        raw=b'<section id="benchmarking-business"><table><thead><tr><th>Metric</th></tr>'
        b'</thead><tbody><tr><td><div chartdata="[[&quot;period&quot;,1e-8]]">'
        b"</div></td></tr></tbody></table></section>"
    )
    assert [cell.raw_text for cell in benchmark_business_charts(body)] == ["1e-8"]
