"""Company breadth over retained bodies, with HTTP as the only fake boundary."""

import hashlib
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest
import yaml
from pydantic import SecretStr
from vendor_surface_support import load_request_index

from fundamentals.ingest.screener_session_models import BasisTopology
from fundamentals.ingest.screener_session_page import parse_document, read_identity
from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, Site, SiteSession, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import CompanyIds
from fundamentals.ingest.vendor_surface_specs import load_specs
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import VendorValuesStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]


class CompanyOpener(OpenerDirector):
    """Serve exact retained addresses and keep unretained requests as explicit refusals."""

    def __init__(self, symbol):
        super().__init__()
        rows = json.loads(Path("docs/research/vendor-surface/kinds-index.json").read_text())
        self.rows = {r["url"]: r for r in rows if r["symbol"] == symbol}
        self.rows.update(
            {url: row for url, row in load_request_index().items() if url not in self.rows}
        )
        self.calls, self.overrides = [], {}

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        row = self.rows.get(request.full_url)
        raw, status = b"unretained", 404
        if row and row.get("path"):
            raw, status = Path(row["path"]).read_bytes(), row.get("status", 200)
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        raw, status = self.overrides.get(request.full_url, (raw, status))
        return HTTPError(request.full_url, status, "fixture", {}, io.BytesIO(raw))


@pytest.fixture
def company_rig(pg_db, tmp_path):
    def run(symbol, unknown=False, slug=True):
        opener = CompanyOpener(symbol)
        pages = [
            r
            for r in opener.rows.values()
            if r["id"] == "company-page" and r.get("symbol") == symbol
        ]
        company, warehouse = read_identity(
            parse_document(
                Path(next(r for r in pages if r["basis"] == "standalone")["path"]).read_text()
            )
        )
        consolidated = read_identity(
            parse_document(
                Path(next(r for r in pages if r["basis"] == "consolidated")["path"]).read_text()
            )
        )[1]
        overview = next(
            r
            for r in opener.rows.values()
            if r["id"] == "company-overview" and r.get("symbol") == symbol
        )
        tree = parse_document(Path(overview["path"]).read_text())
        tijori = json.loads(tree.xpath('//script[@id="company_details_data"]/text()')[0])
        ids = CompanyIds(
            nse_symbol=symbol,
            isin="synthetic-isin",
            screener_company_id=company,
            tijori_company_id=tijori["company_id"],
            tijori_slug=urlsplit(overview["url"]).path.split("/")[2] if slug else None,
            topology=None
            if unknown
            else BasisTopology(
                standalone_warehouse_id=warehouse, consolidated_warehouse_id=consolidated
            ),
        )
        with pg_db.runtime_pool() as pool, pool.connection() as conn:
            evidence = conn.execute(
                "INSERT INTO eqos.evidence_inputs "
                "(kind,label,content_sha256) VALUES ('ENTITY_MAP','fixture',%s) RETURNING id",
                (hashlib.sha256(symbol.encode()).hexdigest(),),
            ).fetchone()[0]
            entity = conn.execute(
                "INSERT INTO eqos.reporting_entities "
                "(entity_key,market,display_name,evidence_input_id) "
                "VALUES (%s,'IN',%s,%s) RETURNING id",
                (symbol, symbol, evidence),
            ).fetchone()[0]
            security = conn.execute(
                "INSERT INTO eqos.securities "
                "(entity_id,isin,share_class,evidence_input_id) "
                "VALUES (%s,%s,'EQ',%s) RETURNING id",
                (entity, ids.isin, evidence),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO eqos.listings "
                "(security_id,venue,symbol,evidence_input_id) VALUES (%s,'NSE',%s,%s)",
                (security, symbol, evidence),
            )
        return opener, ids

    return run


@pytest.fixture
def run_company(pg_db, tmp_path):
    def run(opener, ids, selected=None):
        from fundamentals.ingest.vendor_surface_capture import capture_company

        specs = load_specs(
            Path("config/vendor_surface/surfaces.yaml"),
            Path("docs/research/vendor-surface/catalog.yaml"),
        )
        store = SnapshotStore(tmp_path / "raw")
        with pg_db.runtime_pool() as pool:
            locks = PgSiteLock(pool)
            fetcher = VendorFetcher(
                store,
                {
                    s: SiteSession(
                        site=s, session_cookie=SecretStr("fake"), cookie_name="sessionid"
                    )
                    for s in Site
                },
                opener,
                tmp_path,
                locks,
                spacing_seconds=0,
            )
            try:
                report = capture_company(
                    fetcher, store, pool, VendorValuesStore(pool), selected or specs, ids
                )
            finally:
                locks.close()
            with pool.connection() as conn:
                captures = conn.execute(
                    "SELECT substr(surface,4), count(*) FROM eqos.capture_refs GROUP BY surface"
                ).fetchall()
                outcomes = conn.execute(
                    "SELECT surface,status,detail FROM eqos.vendor_outcomes"
                ).fetchall()
                bindings = conn.execute(
                    "SELECT basis,evidence FROM eqos.vendor_basis_bindings"
                ).fetchall()
                assert (
                    conn.execute(
                        "SELECT count(*) FROM eqos.capture_refs c WHERE NOT EXISTS "
                        "(SELECT 1 FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id)"
                    ).fetchone()[0]
                    == 0
                )
        return report, dict(captures), outcomes, bindings

    return run


@pytest.mark.parametrize("symbol", ["APARINDS", "HDFCBANK", "NETWEB", "ANONDITA"])
def test_company_breadth(company_rig, run_company, symbol):
    opener, ids = company_rig(symbol)
    report, captures, outcomes, _ = run_company(opener, ids)
    actual = set(captures)
    catalog = yaml.safe_load(Path("docs/research/vendor-surface/catalog.yaml").read_text())
    expected = {
        entry["id"]
        for site in ("screener", "tijori")
        for entry in catalog[site]["entries"]
        if entry["scope"] == "company"
        and "#" not in entry["url_pattern"]
        and entry["id"] not in ("pre-listing-company", "company-consolidated-empty-shell")
    }
    if symbol not in ("APARINDS", "HDFCBANK"):
        expected.remove("segments-api")
    gaps = {
        item.split(":")[1]
        for item in report.incomplete
        if item.startswith(("screener:", "tijori:"))
    }
    assert actual | (gaps & expected) == expected
    if symbol in ("APARINDS", "HDFCBANK"):
        assert {
            "op-metrics-api",
            "revenue-mix-history-api",
            "financials-popup-chart-api",
            "financial-statement-compare-api",
        } <= actual
    assert (
        "segments-api" in actual
        if symbol in ("APARINDS", "HDFCBANK")
        else "segments-api" not in actual
    )
    assert dict(captures)["company-page"] == 2
    if symbol == "NETWEB":
        assert "company-consolidated-empty-shell" in {row[0] for row in outcomes}
    assert {
        "section-documents",
        "section-quarters",
        "overview-custom-ratios",
        "shareholding-overview",
    } <= {r[0] for r in outcomes}
    assert len(opener.calls) == len(set(opener.calls))
    assert report.expected >= len(opener.calls)
    assert report.expected == report.completed + len(report.refused) + len(report.incomplete)
    assert any("company-compare" in item for item in report.incomplete)


@pytest.mark.parametrize("symbol,binding_count", [("HDFCBANK", 2), ("NETWEB", 0)])
def test_unknown_topology_and_reuse(company_rig, run_company, symbol, binding_count):
    opener, ids = company_rig(symbol, unknown=True)
    first, captures, outcomes, bindings = run_company(opener, ids)
    assert len(bindings) == binding_count
    assert all(evidence == "FIRST_CAPTURE" for _, evidence in bindings)
    assert captures["company-page"] == 2 and "company-timeline-api" in captures
    assert any(detail == "topology unknown" for _, _, detail in outcomes) == (binding_count == 0)
    assert any(
        surface == "chart-api" and status in ("OK", "UNUSABLE") for surface, status, _ in outcomes
    )
    opener.calls.clear()
    second, _, _, reused = run_company(opener, ids)
    assert reused == bindings
    assert first.expected == second.expected


@pytest.mark.parametrize("site", ["tijori", "screener", "screener-later"])
def test_wrong_identity_stops_company(company_rig, run_company, site):
    opener, ids = company_rig("HDFCBANK")
    surface = "company-financials" if site == "tijori" else "company-page"
    suffix = (
        "/hdfc-bank-limited/financials/"
        if site == "tijori"
        else ("/HDFCBANK/" if site.endswith("later") else "/HDFCBANK/consolidated/")
    )
    wrong = next(
        r
        for r in load_request_index().values()
        if r["id"] == surface
        and r.get("path")
        and (
            "apar-industries" in r["url"]
            if site == "tijori"
            else "/APARINDS/consolidated/" in r["url"]
        )
    )
    url = next(url for url in opener.rows if url.endswith(suffix))
    opener.overrides[url] = Path(wrong["path"]).read_bytes(), 200
    report, _, outcomes, _ = run_company(opener, ids)
    authority = "tijorifinance" if site == "tijori" else "screener.in"
    calls = [url for url in opener.calls if authority in url]
    assert len(calls) == (2 if site.endswith("later") else 1)
    assert any(name == surface and status == "UNUSABLE" for name, status, _ in outcomes)
    assert report.refused


def test_schedule_whitespace_nested_and_depth(company_rig, run_company):
    opener, ids = company_rig("APARINDS")
    for url, row in opener.rows.items():
        if row["id"] == "company-page" and "/APARINDS/" in url:
            opener.overrides[url] = (
                Path(row["path"]).read_bytes().replace(b"showSchedule(", b"showSchedule ("),
                200,
            )
    # The retained response supplies a genuine nested advertisement. A depth-3 reply
    # advertises one additional synthetic child, proving the acquisition bound.
    row = next(
        r
        for r in opener.rows.values()
        if r["id"] == "schedules-api"
        and r.get("symbol") == "APARINDS"
        and b"isExpandable" in Path(r["path"]).read_bytes()
    )
    raw = Path(row["path"]).read_bytes()
    import re

    call = next(
        value["isExpandable"] for value in json.loads(raw).values() if value.get("isExpandable")
    )
    label, section = re.findall(r'"([^"]+)"', call)[:2]
    from urllib.parse import quote

    nested = (
        f"https://www.screener.in/api/company/{ids.screener_company_id}/schedules/"
        f"?parent={quote(label, safe='')}&section={section}&consolidated="
    )
    opener.overrides[nested] = (
        json.dumps(
            {
                "sub_rows": [
                    {
                        "nested_schedule_call": (
                            'Company.showSchedule("depth-four", "profit-loss", this)'
                        )
                    }
                ]
            }
        ).encode(),
        200,
    )
    report, captures, _, _ = run_company(opener, ids)
    assert captures["schedules-api"] > 0
    assert opener.calls.count(nested) == 1
    assert any("schedule depth limit" in item for item in report.incomplete)
    assert not any("parent=depth-four" in url for url in opener.calls)


@pytest.mark.parametrize("resolved", [False, True])
def test_missing_slug_retries(company_rig, run_company, resolved):
    opener, ids = company_rig("HDFCBANK", slug=False)
    ids = ids.model_copy(update={"tijori_company_id": None})
    search = "https://www.tijorifinance.com/api/v1/ind/company_search/?q=synthetic-isin"
    slug = "hdfc-bank-limited"
    opener.overrides[search] = (
        json.dumps([{"type": "companies", "slug": slug}] if resolved else []).encode(),
        200,
    )
    for _ in range(2):
        report, captures, _, _ = run_company(opener, ids)
        assert any("missing slug" in item for item in report.incomplete) != resolved
        assert ("company-overview" in captures) == resolved
    assert opener.calls.count(search) == 2


def test_basis_refusal_covers_sections_and_children(company_rig, run_company, pg_db):
    opener, ids = company_rig("APARINDS")
    standalone = next(
        r
        for r in opener.rows.values()
        if r["id"] == "company-page"
        and r.get("symbol") == "APARINDS"
        and r["basis"] == "standalone"
    )
    consolidated = next(
        r
        for r in opener.rows.values()
        if r["id"] == "company-page"
        and r.get("symbol") == "APARINDS"
        and r["basis"] == "consolidated"
    )
    opener.overrides[consolidated["url"]] = Path(standalone["path"]).read_bytes(), 200
    run_company(opener, ids)
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM eqos.vendor_values v JOIN eqos.capture_refs c ON c.id=v.capture_ref_id WHERE basis='consolidated' AND c.source_id='screener-subscriber'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT status FROM eqos.vendor_outcomes o JOIN eqos.capture_addresses a ON a.capture_ref_id=o.capture_ref_id WHERE a.url=%s AND o.surface='section-quarters'",
                (consolidated["url"],),
            ).fetchone()[0]
            == "UNUSABLE"
        )


@pytest.mark.parametrize("raw,status", [(b"missing", 404), (b"", 200), (b"\xff", 200)])
def test_identity_acquisition_failure_is_recorded(company_rig, run_company, raw, status):
    opener, ids = company_rig("APARINDS")
    specs = load_specs(
        Path("config/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    selected = tuple(
        s for s in specs if s.site is Site.SCREENER and s.id in ("company-page", "company-trades")
    )
    for url, row in opener.rows.items():
        if row["id"] == "company-page" and row.get("symbol") == "APARINDS":
            opener.overrides[url] = raw, status
    report, captures, outcomes, _ = run_company(opener, ids, selected)
    assert "company-trades" not in captures
    assert any(surface == "company-page" and state == "UNUSABLE" for surface, state, _ in outcomes)
    assert report.refused


def test_shareholder_whitespace_uses_matched_control(company_rig, run_company):
    opener, ids = company_rig("APARINDS")
    for url, row in opener.rows.items():
        if row["id"] == "company-page" and row.get("symbol") == "APARINDS":
            opener.overrides[url] = (
                Path(row["path"]).read_bytes().replace(b"showShareholders(", b"showShareholders ("),
                200,
            )
    _, captures, outcomes, _ = run_company(opener, ids)
    assert captures["investors-api"] > 0
    assert any(surface == "investors-api" and status == "OK" for surface, status, _ in outcomes)
