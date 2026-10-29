"""G2 retained captures keep every cell and duplicate row under positional identities."""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from vendor_surface_support import capture_response

from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_parse import PARSERS, Body, ParseContext, register_tables
from fundamentals.ingest.vendor_surface_specs import load_specs
from fundamentals.ingest.vendor_surface_tables import feed_rows, read_html_table, read_js_var
from fundamentals.store.snapshot_store import SnapshotStore

SURFACES = {
    "screener": {
        "section-documents": "company-page",
        "company-trades": "company-trades",
        "company-announcements": "company-announcements",
    },
    "tijori": {
        **dict.fromkeys(
            (
                "overview-company-filings",
                "overview-customers",
                "overview-suppliers",
                "overview-brands",
                "overview-connections",
            ),
            "company-overview",
        ),
        **dict.fromkeys(("shareholding-overview", "shareholding-trend"), "company-shareholding"),
    },
}


# Two checked retained rows per surface; suppliers needs RELIANCE (APARINDS has one).
CHECKED = {
    "section-documents": ("documents:1", 0, ["Annual Report 2026", "Annual Report 2025"]),
    "company-trades": ("trades-insider-trades", 1, ["-1,942", "-1,000"]),
    "company-announcements": (
        "Announcements",
        0,
        [
            "Announcement under Regulation 30 (LODR)-Allotment",
            "Outcome Of The Meeting Of The Share Issue Committee Of Directors",
        ],
    ),
    "overview-company-filings": ("companyFilings", 0, ["Annual Report", "Earnings Release"]),
    "overview-customers": ("overview-customers", 0, ["ABB India Ltd.", "KEC International Ltd."]),
    "overview-suppliers": (
        "overview-suppliers",
        0,
        ["CG Power and Industrial Solutions Ltd.", "Indus Towers Ltd."],
    ),
    "overview-brands": (
        "overview-brands",
        0,
        ["Eni Lubricant (Global Brand)", "POWEROIL (Transformer Oil)"],
    ),
    "overview-connections": (
        "overview-connections",
        0,
        ["Kkalpana lndustries (India) Ltd.", "ABB India Ltd."],
    ),
    "shareholding-overview": ("overview", 1, ["57.77", "57.77"]),
    "shareholding-trend": ("trendData", 0, ["59.97", "59.97"]),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "symbol,ragged",
    [
        ("APARINDS", False),
        ("ETERNAL", False),
        ("KIRANVYPAR", False),
        ("HDFCLIFE", False),
        ("RELIANCE", False),
        ("APARINDS", True),
    ],
)
def test_retained_tables_are_registered_and_stored(pg_db, tmp_path, monkeypatch, symbol, ragged):
    rows = json.loads(Path("docs/research/vendor-surface/kinds-index.json").read_text())
    specs = load_specs(
        Path("config/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    store = SnapshotStore(tmp_path / "captures")
    with pg_db.runtime_pool() as pool:
        for site_name, surfaces in SURFACES.items():
            site = Site.SCREENER if site_name == "screener" else Site.TIJORI
            for surface, parent in surfaces.items():
                retained = [
                    r
                    for r in rows
                    if (r["site"], r["symbol"], r["id"], r["status"])
                    == (site_name, symbol, parent, 200)
                    and "/search/" not in r["url"]
                ]
                if not retained:
                    continue
                row = retained[0]
                raw = Path(row["path"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == row["sha256"]
                if ragged and surface == "company-trades":
                    from lxml import html

                    tree = Body(raw=raw).tree()
                    cell = tree.xpath("//table/tbody/tr[not(td/@colspan)]/td[2]")[0]
                    cell.getparent().remove(cell)
                    raw = html.tostring(tree, encoding="utf-8")
                entry = PARSERS[site, surface]
                spec = next(s for s in specs if (s.site, s.id) == (site, surface))

                ref = capture_response(
                    pool,
                    store,
                    tmp_path / "stops",
                    Request(spec=spec, url=row["url"], ids=None, due_since=None),
                    raw,
                )
                with pool.connection() as conn:
                    status, count = conn.execute(
                        "SELECT status,row_count FROM eqos.vendor_outcomes "
                        "WHERE capture_ref_id=%s AND surface=%s",
                        (ref.capture_ref_id, surface),
                    ).fetchone()
                    absent = (
                        surface
                        in {"overview-customers", "overview-suppliers", "overview-connections"}
                        and symbol in {"ETERNAL", "KIRANVYPAR", "HDFCLIFE"}
                    ) or (surface == "overview-brands" and symbol in {"KIRANVYPAR", "HDFCLIFE"})
                    absent |= surface == "overview-customers" and symbol == "RELIANCE"
                    failed = ragged and surface == "company-trades"
                    partial = surface == "company-trades" and symbol == "APARINDS" and not failed
                    assert status == (
                        "FAILED"
                        if failed
                        else "EMPTY"
                        if absent
                        else "PARTIAL"
                        if partial
                        else "OK"
                    )
                    if partial:
                        assert conn.execute(
                            (
                                "SELECT count(*) FROM eqos.vendor_values "
                                "WHERE capture_ref_id=%s AND "
                                "expected_numeric AND value IS NULL AND column_label='Percent'"
                            ),
                            (ref.capture_ref_id,),
                        ).fetchone() == (1,)
                    if failed:
                        assert count == 0
                    stored = conn.execute(
                        "SELECT table_key,row_index,column_index,row_label "
                        "FROM eqos.vendor_values "
                        "WHERE capture_ref_id=%s AND outcome_id IN "
                        "(SELECT id FROM eqos.vendor_outcomes WHERE surface=%s)",
                        (ref.capture_ref_id, surface),
                    ).fetchall()
                    assert len(stored) == count
                    assert len({r[:3] for r in stored}) == count
                    if surface == "company-trades" and symbol == "APARINDS" and not ragged:
                        assert len({r[1] for r in stored if r[0] == "trades-insider-trades"}) == 37
                        assert max(Counter((r[0], r[3]) for r in stored if r[2] == 0).values()) > 1
                    checked_symbol = "RELIANCE" if surface == "overview-suppliers" else "APARINDS"
                    if symbol == checked_symbol and not failed:
                        key, column, expected = CHECKED[surface]
                        samples = conn.execute(
                            "SELECT raw_text FROM eqos.vendor_values WHERE capture_ref_id=%s "
                            "AND table_key=%s AND column_index=%s ORDER BY row_index LIMIT 2",
                            (ref.capture_ref_id, key, column),
                        ).fetchall()
                        assert [r[0] for r in samples] == expected
                    if surface == "overview-connections" and symbol == "APARINDS":
                        assert conn.execute(
                            "SELECT DISTINCT column_label FROM eqos.vendor_values "
                            "WHERE capture_ref_id=%s ORDER BY column_label",
                            (ref.capture_ref_id,),
                        ).fetchall() == [("Customers",), ("Suppliers",)]
                    if surface == "section-documents":
                        expected_blocks = {"Announcements", "Annual reports"}
                        if symbol != "KIRANVYPAR":
                            expected_blocks.add("Concalls")
                        if symbol not in {"KIRANVYPAR", "ETERNAL"}:
                            expected_blocks.add("Credit ratings")
                        assert {r[3] for r in stored} == expected_blocks
                        assert all(r[0].startswith("documents:") for r in stored)
                assert entry.version == f"{site_name}:{surface}.v1"


def test_table_cells_keep_labels_links_and_reject_ragged_rows():
    tree = Body(
        raw=b"<table><thead><tr><th>Name</th><th>Amount</th></tr></thead>"
        b'<tbody><tr><td><a href="/fixture">Repeat</a></td><td>1,234.50</td></tr>'
        b"<tr><td>Repeat</td><td>-5%</td></tr></tbody></table>"
    ).tree()
    cells = read_html_table(tree, ".", "fixture")
    assert [(v.row_index, v.column_index, v.raw_text, v.value) for v in cells] == [
        (0, 0, "Repeat", None),
        (0, 1, "1,234.50", Decimal("1234.50")),
        (1, 0, "Repeat", None),
        (1, 1, "-5%", Decimal("-5")),
    ]
    assert cells[0].link == "/fixture" and cells[1].column_label == "Amount"
    for cell in cells:
        assert tree.xpath(cell.locator)
    tree.xpath("./tbody/tr[2]")[0].remove(tree.xpath("./tbody/tr[2]/td[2]")[0])
    with pytest.raises(ValueError, match="ragged"):
        read_html_table(tree, ".", "fixture")


def test_script_literals_preserve_decimals_and_never_execute_code():
    body = (
        b"<script>var fixture = [['quoted; label', 1.234567890123456789], "
        b"['second', null]];</script>"
    )
    assert read_js_var(body, "fixture") == [
        ["quoted; label", Decimal("1.234567890123456789")],
        ["second", None],
    ]
    with pytest.raises(ValueError):
        read_js_var(b"<script>var fixture = alert('forbidden');</script>", "fixture")


MARKET_INDEX = json.loads(Path("docs/research/vendor-surface/snapshots-index.json").read_text())
MARKET_SPECS = load_specs(
    Path("config/vendor_surface/surfaces.yaml"), Path("docs/research/vendor-surface/catalog.yaml")
)
register_tables(MARKET_SPECS)
MARKET_NONFEEDS = (
    "market-pulse market-level index-page person-page screen-raw raw-materials idea-card-body"
).split()
MARKET_ROWS = {
    "results-latest": ("Info Edg.(India)", "K P R Mill Ltd"),
    "upcoming-results": ("TNA Solutions", "Vishal Nirmiti"),
    "concalls-feed": ("Cholaman.Inv.&Fn", "Kalyani Cast-Tec"),
    "annual-reports-feed": ("Powergrid Infra.", "Interise"),
    "announcements-feed": ("Adani Enterp.", "Kalyani Steels"),
    "market-pulse": ("Announcements", "Industries Overview"),
    "corporate-actions-feed": ("Genus Power", "Auto.Corp.of Goa"),
    "trades-feed": ("TVS Holdings", "TVS Holdings"),
    "ipo": ("EAAA India", "BLS Polymers"),
    "ratings-feed": ("IDBI Bank Limited", "IIFL Capital Services Limited"),
    "market-level": ("HDFC Bank", "ICICI Bank"),
    "index-page": ("Reliance Industries", "Bharti Airtel"),
    "person-page": ("Multi Comm. Exc. 08 Jul, 2014", "Orient Cement 15 May, 2014"),
    "screen-raw": ("ICICI AMC", "Nestle India"),
    "quarterly-results-api": ("Kkalpana Plastick", "Hindustan Unilever"),
    "upcoming-events-api": ("Adjia Technologies", "Vishal Nirmiti"),
    "raw-materials": ("Acetone", "Caustic Soda Lye"),
    "idea-page": (),
    "idea-card-body": ("Seshasayee Paper", "Shakti Pumps (India)"),
}


@pytest.mark.retained
@pytest.mark.parametrize("surface", MARKET_ROWS)
def test_market_tables_and_feed_rows(surface):
    row = next(r for r in MARKET_INDEX if r["id"] == surface and r["status"] == 200)
    site = Site.SCREENER if row["site"] == "screener" else Site.TIJORI
    entry = PARSERS[site, surface]
    spec = next(s for s in MARKET_SPECS if (s.site, s.id) == (site, surface))
    raw = Path(row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    context = ParseContext(
        ids=None,
        basis=None,
        url=row["url"],
        retrieved_at=datetime(2026, 10, 28, tzinfo=UTC),
        body_sha256=row["sha256"],
        capture_id="retained-market",
    )
    cells = entry.parse(Body(raw=raw), context)
    tree = Body(raw=raw).tree()
    for cell in cells:
        source = tree.xpath(cell.locator)[0]
        text = " ".join(source.text_content().split())
        assert cell.raw_text in text or cell.raw_text == source.get("datetime")
    assert len({(v.table_key, v.row_index, v.column_index) for v in cells}) == len(cells)
    for expected in MARKET_ROWS[surface]:
        assert any(v.raw_text == expected for v in cells)
    if surface == "idea-page":
        assert cells == ()  # The only retained 200 explicitly reports no data.
        with pytest.raises(ValueError):
            entry.parse(Body(raw=raw.replace(b"card_tj no_data", b"card_tj changed")), context)
    elif surface not in MARKET_NONFEEDS:
        events = feed_rows(spec, cells)
        assert len(events) >= 2 and all(e.row_id and e.company for e in events)
        # Two retained trades differ only by value; the market run reports that page.
        assert len({e.row_id for e in events}) == len(events) - (surface == "trades-feed")
        assert events == feed_rows(spec, tuple(reversed(cells)))
        if surface in {"annual-reports-feed", "ratings-feed", "ipo", "results-latest"}:
            assert all(e.row_date is None for e in events)
        elif surface == "quarterly-results-api":
            assert events[0].row_date is None and any(e.row_date for e in events)
        else:
            assert all(e.row_date is not None for e in events)
        if surface == "upcoming-results":
            assert events[0].row_date == date(2026, 10, 28)
        if surface == "annual-reports-feed":
            assert any("2026" in v.raw_text for v in cells)
        if surface == "ratings-feed":
            assert [e.company for e in events[:2]] == list(MARKET_ROWS[surface])
    else:
        with pytest.raises(ValueError, match="feed"):
            feed_rows(spec, cells)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("broken", [False, True])
def test_market_feed_date_failure_is_recorded(pg_db, tmp_path, monkeypatch, broken):
    row = next(r for r in MARKET_INDEX if r["id"] == "upcoming-results" and r["status"] == 200)
    raw = Path(row["path"]).read_bytes()
    if broken:
        raw = raw.replace(b"28 October 2026", b"invalid full date", 1)
    spec = next(s for s in MARKET_SPECS if s.id == "upcoming-results")

    store = SnapshotStore(tmp_path / "captures")
    with pg_db.runtime_pool() as pool:
        ref = capture_response(
            pool, store, tmp_path, Request(spec=spec, url=row["url"], ids=None, due_since=None), raw
        )
        with pool.connection() as conn:
            status, count = conn.execute(
                "SELECT status,row_count FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchone()
            assert status == ("FAILED" if broken else "OK")
            assert (count == 0) if broken else (count > 0)


def test_registry_import_does_not_read_configuration(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import fundamentals.ingest.vendor_surface_parse"],
        cwd=tmp_path,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_unreadable_numeric_column_remains_expected():
    tree = Body(
        raw=(
            b"<table><thead><tr><th>Name</th><th>Amount</th></tr></thead><tbody><t"
            b"r><td>Label</td><td>unreadable</td></tr></tbody></table>"
        )
    ).tree()
    cell = read_html_table(tree, ".", "fixture")[1]
    assert cell.value is None and cell.expected_numeric


def test_missing_trade_markup_fails():
    context = ParseContext(
        ids=None,
        basis=None,
        url="",
        retrieved_at=datetime.now(UTC),
        body_sha256="fixture",
        capture_id="fixture",
    )
    with pytest.raises(ValueError, match="trade"):
        PARSERS[Site.SCREENER, "company-trades"].parse(Body(raw=b"<p>unrelated</p>"), context)


def test_filing_cell_keeps_every_link():
    cells = read_html_table(
        Body(
            raw=(
                b"<table><tr><th>Year</th><th>Files</th></tr><tr><td>2026</td><td><a h"
                b'ref="/one">One</a><a href="/two">Two</a><a href="/three">Three</a></'
                b"td></tr></table>"
            )
        ).tree(),
        ".",
        "filings",
    )
    assert {v.link for v in cells if v.link} == {"/one", "/two", "/three"}
    assert len({(v.table_key, v.row_index, v.column_index) for v in cells}) == len(cells)


def test_document_heading_is_label_not_identity():
    context = ParseContext(
        ids=None,
        basis=None,
        url="",
        retrieved_at=datetime.now(UTC),
        body_sha256="fixture",
        capture_id="fixture",
    )
    raw = (
        b'<section id="documents"><div class="documents"><h3>Original</h3><ul '
        b'class="list-links"><li><a href="/report">Report</a></li></ul></div><'
        b"/section>"
    )
    parser = PARSERS[Site.SCREENER, "section-documents"].parse
    before = parser(Body(raw=raw), context)
    after = parser(Body(raw=raw.replace(b"Original", b"Renamed")), context)
    assert [(v.table_key, v.row_index, v.column_index) for v in before] == [
        (v.table_key, v.row_index, v.column_index) for v in after
    ]
    assert any(v.row_label == "Renamed" for v in after)


def test_shareholding_series_preserves_numeric_lexeme():
    context = ParseContext(
        ids=None,
        basis=None,
        url="",
        retrieved_at=datetime.now(UTC),
        body_sha256="fixture",
        capture_id="fixture",
    )
    values = PARSERS[Site.TIJORI, "shareholding-trend"].parse(
        Body(raw=b"<script>var trendData = [{'name':'Fixture','data':[[123,1e-8]]}];</script>"),
        context,
    )
    assert values[0].raw_text == "1e-8"
    assert values[0].value == Decimal("0.00000001")


@pytest.mark.retained
@pytest.mark.parametrize(
    ("surface", "mutable"),
    [("trades-feed", {"Value"}), ("corporate-actions-feed", {"Max Price", "Amount in Cr"})],
)
def test_unlinked_feed_rows_keep_identity_when_amounts_change(surface, mutable):
    from lxml import html

    row = next(r for r in MARKET_INDEX if r["id"] == surface and r["status"] == 200)
    spec = next(s for s in MARKET_SPECS if s.id == surface)
    raw = Path(row["path"]).read_bytes()
    context = ParseContext(
        ids=None,
        basis=None,
        url=row["url"],
        retrieved_at=datetime(2026, 10, 28, tzinfo=UTC),
        body_sha256=row["sha256"],
        capture_id="retained-market",
    )
    tree = html.fromstring(raw)
    table = tree.xpath(spec.selector)[0]
    headers = [" ".join(th.text_content().split()) for th in table.xpath("./thead/tr/th")]
    for tr in table.xpath("./tbody/tr[td]"):
        for cell, label in zip(tr.xpath("./td | ./th"), headers, strict=True):
            if label in mutable:
                cell.text, cell[:] = "999", []
    events = feed_rows(spec, PARSERS[spec.site, surface].parse(Body(raw=raw), context))
    edited = PARSERS[spec.site, surface].parse(Body(raw=html.tostring(tree)), context)
    # A revised amount or price is the same corporate action or trade, not a new event.
    assert feed_rows(spec, edited) == events
    unkeyed = tuple(v for v in edited if not v.column_label.startswith("Key"))
    with pytest.raises(ValueError, match="stable identity"):
        feed_rows(spec, unkeyed)


# Sources pinned at 4cb5a9f2 (before Phase 3 round 1): a version must never change its source.
BASE_MARKET_TABLE = "f032e0eac43296a6d720e62143d32395f799c8ff09c777dc42b080b8946d495d"
BASE_TRAVERSAL = "01fa2b3748b0976921db4e56b76946606239c0e0d0e33e94875288241c82d121"


def test_changed_parsers_never_reuse_a_base_revision_pin():
    from fundamentals.ingest import vendor_surface_market as market
    from fundamentals.ingest.vendor_surface_parse import parser_sha256
    from fundamentals.ingest.vendor_surface_specs import SITE_NAME, ParseGroup, Scope

    pins = {
        f"{SITE_NAME[s.site]}:{s.id}.v1": BASE_MARKET_TABLE
        for s in MARKET_SPECS
        if s.scope is Scope.MARKET and s.group is ParseGroup.TABLE
    }
    found = {
        entry.version: parser_sha256(entry.parse)
        for s in MARKET_SPECS
        if (entry := PARSERS.get((s.site, s.id)))
    }
    found |= {
        f"{SITE_NAME[s.site]}:{s.id}.{market.TRAVERSAL_VERSION}": parser_sha256(market.continuation)
        for s in MARKET_SPECS
    }
    pins |= {f"{SITE_NAME[s.site]}:{s.id}.traversal.v1": BASE_TRAVERSAL for s in MARKET_SPECS}
    # A drifted pin raises ParserVersionDrift on every capture already recorded under it.
    assert {v for v, sha in found.items() if pins.get(v, sha) != sha} == set()


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "surface,header",
    [
        ("corporate-actions-feed", "Amount in Cr"),
        ("market-level", "CMP Rs."),
        ("results-latest", "YOY"),
        ("quarterly-results-api", "YoY Growth"),
        ("ipo", "ROCE"),
        ("raw-materials", "1W"),
    ],
)
def test_unreadable_numeric_g2_column_remains_expected(pg_db, tmp_path, surface, header):
    from lxml import etree
    from vendor_surface_support import load_request_index

    specs = load_specs(
        Path("config/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    register_tables(specs)
    spec = next(s for s in specs if s.id == surface)
    for row in load_request_index().values():
        if row["id"] != surface or row.get("status") != 200:
            continue
        context = ParseContext(
            ids=None,
            basis=None,
            url=row["url"],
            retrieved_at=datetime.now(UTC),
            body_sha256="",
            capture_id="fixture",
        )
        body = Body(raw=Path(row["path"]).read_bytes())
        cells = PARSERS[spec.site, surface].parse(body, context)
        target = next((c for c in cells if c.column_label == header), None)
        if target is not None:
            break
    assert target is not None
    node = body.tree().xpath(target.locator)[0]
    for child in list(node):
        node.remove(child)
    node.text = "unreadable"
    with pg_db.runtime_pool() as pool:
        ref = capture_response(
            pool,
            SnapshotStore(tmp_path / "captures"),
            tmp_path / "stops",
            Request(spec=spec, url=context.url, ids=None, due_since=None),
            etree.tostring(body.tree()),
        )
        with pool.connection() as conn:
            flagged = conn.execute(
                "SELECT expected_numeric FROM eqos.vendor_values "
                "WHERE capture_ref_id=%s AND raw_text='unreadable'",
                (ref.capture_ref_id,),
            ).fetchall()
            assert flagged == [(True,)]
            assert conn.execute(
                "SELECT status FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                (ref.capture_ref_id,),
            ).fetchall() == [("PARTIAL",)]
