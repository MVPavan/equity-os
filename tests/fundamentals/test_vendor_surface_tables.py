"""G2 retained captures keep every cell and duplicate row under positional identities."""

import hashlib
import io
import json
from collections import Counter
from decimal import Decimal
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr

from fundamentals.ingest.vendor_surface_capture import Request, capture
from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import PARSERS, Body
from fundamentals.ingest.vendor_surface_specs import load_specs
from fundamentals.ingest.vendor_surface_tables import read_html_table, read_js_var
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

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
    "section-documents": ("Annual reports", 0, ["Annual Report 2026", "Annual Report 2025"]),
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
        locks = PgSiteLock(pool)
        values = VendorValuesStore(pool)
        try:
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

                    def opened(self, request, timeout, row=row, raw=raw):
                        assert request.full_url == row["url"] and timeout > 0
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
                    ref, _ = capture(
                        fetcher,
                        store,
                        pool,
                        values,
                        Request(spec=spec, url=row["url"], ids=None, due_since=None),
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
                        assert status == ("FAILED" if failed else "EMPTY" if absent else "OK")
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
                            assert (
                                len({r[1] for r in stored if r[0] == "trades-insider-trades"}) == 37
                            )
                            assert (
                                max(Counter((r[0], r[3]) for r in stored if r[2] == 0).values()) > 1
                            )
                        checked_symbol = (
                            "RELIANCE" if surface == "overview-suppliers" else "APARINDS"
                        )
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
                            assert {r[0] for r in stored} == expected_blocks
                    assert entry.version == f"{site_name}:{surface}.v1"
        finally:
            locks.close()


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
