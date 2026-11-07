"""Company breadth over retained bodies, with HTTP as the only fake boundary."""

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr
from vendor_surface_support import RetainedResponseOpener, load_request_index, retained

from equity_os.extraction.surfaces.vendor_surface_parse import register_tables
from equity_os.sourcing.surfaces.vendor_surface_fetch import (
    PgSiteLock,
    Site,
    SiteSession,
    VendorFetcher,
)
from equity_os.sourcing.surfaces.vendor_surface_specs import load_specs
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import VendorValuesStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

SPECS = load_specs(
    Path("config/sourcing/vendor_surface/surfaces.yaml"),
    Path("docs/research/vendor-surface/catalog.yaml"),
)


class CompanyOpener(RetainedResponseOpener):
    """Serve exact retained addresses and keep unretained requests as explicit refusals."""

    def __init__(self, symbol):
        super().__init__()
        rows = json.loads(Path("docs/research/vendor-surface/kinds-index.json").read_text())
        self.rows = {r["url"]: r for r in rows if r["symbol"] == symbol}
        self.rows.update(
            {url: row for url, row in load_request_index().items() if url not in self.rows}
        )
        self.calls, self.overrides = [], {}


@pytest.fixture
def company_rig(pg_db, tmp_path):
    def run(symbol, unknown=False, slug=True):
        opener = CompanyOpener(symbol)
        _, context = retained("screener", "company-page", symbol)
        ids = context.ids.model_copy(update={"isin": "synthetic-isin"})
        if unknown:
            ids = ids.model_copy(update={"topology": None})
        if not slug:
            ids = ids.model_copy(update={"tijori_slug": None})
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
        from equity_os.sourcing.surfaces.vendor_surface_capture import capture_company

        specs = SPECS
        register_tables(specs)
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
def test_company_breadth(company_rig, run_company, pg_db, symbol):
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
        and entry["id"]
        not in (
            "pre-listing-company",
            "company-consolidated-empty-shell",
            # Dropped from the spec: docs/research/vendor-surface/not-capturable.md.
            "quarter-source-pdf",
            "company-benchmarking",
            "market-share-api",
        )
    }
    if symbol not in ("APARINDS", "HDFCBANK"):
        expected.remove("segments-api")
    expected.add("index-page")  # Market scope: advertised only by company-page benchmark tags.
    if symbol == "HDFCBANK":  # Market scope: only HDFCBANK's retained overview links a sector.
        expected |= {"sector-page", "sector-ms-chart-api", "sector-company-opm-api"}
        expected.add("sector-area-chart-api")
    gaps = {
        item.split(":")[1]
        for item in report.incomplete
        if re.match(r"(screener|tijori):[a-z0-9-]+: ", item)
    }
    # Only these catalog obligations can legitimately lack advertisements in this corpus.
    allowed_gaps = {
        "company-compare",
        "shareholding-detail-chart-api",
        "market-share-peer-companies-api",
        "op-metrics-api",
        "revenue-mix-history-api",
    }
    assert gaps <= allowed_gaps
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

    retained_200 = {
        url for url in opener.calls if url in opener.rows and opener.rows[url]["status"] == 200
    }
    allowed = set()
    if symbol == "HDFCBANK":
        allowed.add(("segments-api", "SegmentReconciliationError"))
    if symbol == "NETWEB":
        allowed.add(("overview-marketshare", "TijoriOverviewSectionAbsentError"))
    if symbol == "ANONDITA":
        allowed |= {
            ("overview-marketshare", "TijoriOverviewSectionAbsentError"),
            ("company-shareholding", "TijoriShareholdingSchemaError"),
            ("shareholding-detailed", "TijoriShareholdingSchemaError"),
        }
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        results = conn.execute(
            "SELECT o.surface,o.status,o.detail,a.url FROM eqos.vendor_outcomes o"
            " JOIN eqos.capture_addresses a ON a.capture_ref_id=o.capture_ref_id"
        ).fetchall()
        unexpected = {
            (surface, detail)
            for surface, status, detail, url in results
            if url in retained_200
            and status in ("FAILED", "UNUSABLE")
            and (surface, detail) not in allowed
            and not (
                symbol == "NETWEB"
                and "/NETWEB/consolidated/" in url
                and surface
                in {
                    "section-quarters",
                    "section-profit-loss",
                    "section-balance-sheet",
                    "section-cash-flow",
                    "section-ratios",
                }
            )
        }
        assert unexpected == set()
        if symbol == "APARINDS":
            # Every financials section has an explicit outcome. The three widget shells hold no
            # data on the page (their data is the analysis APIs), so they are kept, not parsed.
            sections = conn.execute(
                "SELECT o.surface, o.status, o.detail FROM eqos.vendor_outcomes o JOIN eqos.c"
                "apture_refs c ON c.id=o.capture_ref_id WHERE c.surface='vs.company-financials'"
            ).fetchall()
            shells = {
                "financials-balance-sheet-snapshot",
                "financials-fundflow-analysis",
                "financials-cash-flow-analysis",
            }
            assert len(sections) == 13
            assert all(
                status == "KEPT" if surface in shells else status in ("OK", "PARTIAL", "KEPT")
                for surface, status, detail in sections
            )
            assert conn.execute(
                "SELECT v.value FROM eqos.vendor_values v JOIN eqos.vendor_outcomes o"
                " ON o.id=v.outcome_id WHERE o.surface='section-quarters' AND v.basis"
                "='standalone' AND v.column_index IN (0,1) ORDER BY v.row_index,v.col"
                "umn_index LIMIT 2"
            ).fetchall() == [(3500,), (3644,)]


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
                "SELECT count(*) FROM eqos.vendor_values v JOIN eqos.capture_refs c O"
                "N c.id=v.capture_ref_id WHERE basis='consolidated' AND c.source_id='"
                "screener-subscriber'"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                (
                    "SELECT status FROM eqos.vendor_outcomes o JOIN eqos.capture_addresse"
                    "s a ON a.capture_ref_id=o.capture_ref_id WHERE a.url=%s AND o.surfac"
                    "e='section-quarters'"
                ),
                (consolidated["url"],),
            ).fetchone()[0]
            == "UNUSABLE"
        )


@pytest.mark.parametrize("raw,status", [(b"missing", 404), (b"", 200), (b"\xff", 200)])
def test_identity_acquisition_failure_is_recorded(company_rig, run_company, raw, status):
    opener, ids = company_rig("APARINDS")
    specs = load_specs(
        Path("config/sourcing/vendor_surface/surfaces.yaml"),
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


def test_busy_identity_acquisition_blocks_dependents(company_rig, run_company, monkeypatch):
    # Both identity pages meet a busy site lock; a dependent must not run once the lock frees.
    opener, ids = company_rig("APARINDS")
    specs = load_specs(
        Path("config/sourcing/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    selected = tuple(
        s for s in specs if s.site is Site.SCREENER and s.id in ("company-page", "company-trades")
    )
    acquire, busy = PgSiteLock.acquire, iter((True, True))
    monkeypatch.setattr(
        PgSiteLock, "acquire", lambda self, site: not next(busy, False) and acquire(self, site)
    )
    report, captures, _, _ = run_company(opener, ids, selected)
    assert captures == {}
    assert report.completed == 0
    assert report.expected == len(report.refused) + len(report.incomplete)


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


def test_financials_bootstraps_id_before_readers(company_rig, run_company, pg_db):
    opener, ids = company_rig("HDFCBANK")
    ids = ids.model_copy(update={"tijori_company_id": None})
    _, _, outcomes, _ = run_company(opener, ids)
    assert ("company-financials", "PARTIAL", None) in outcomes

    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE expected_numeric AND value I"
            "S NULL) FROM eqos.vendor_values v JOIN eqos.vendor_outcomes o ON o.i"
            "d=v.outcome_id WHERE o.surface='company-financials'"
        ).fetchone() == (3170, 268)


def test_slug_candidate_capture_is_reused(company_rig, run_company):
    opener, ids = company_rig("HDFCBANK", slug=False)
    ids = ids.model_copy(update={"tijori_company_id": None})
    opener.overrides[
        "https://www.tijorifinance.com/api/v1/ind/company_search/?q=synthetic-isin"
    ] = b'[{"type":"companies","slug":"hdfc-bank-limited"}]', 200
    _, _, outcomes, _ = run_company(opener, ids)
    assert (
        opener.calls.count("https://www.tijorifinance.com/company/hdfc-bank-limited/financials/")
        == 1
    )
    assert ("company-financials", "PARTIAL", None) in outcomes


@pytest.mark.parametrize(
    "surface,old,new",
    [
        ("segments-api", b"showSegment(", b"missingSegment("),
        ("chart-api", b'name="metrics"', b'name="missing-metrics"'),
    ],
)
def test_missing_expected_advertisement_is_a_gap(company_rig, run_company, surface, old, new):
    opener, ids = company_rig("APARINDS")
    for url, row in opener.rows.items():
        if row["id"] == "company-page" and row.get("symbol") == "APARINDS":
            opener.overrides[url] = Path(row["path"]).read_bytes().replace(old, new), 200
    report, _, _, _ = run_company(opener, ids)
    assert any(f"screener:{surface}:" in gap for gap in report.incomplete)


@pytest.mark.parametrize(
    "surface,parent",
    [
        ("screener:section-documents", "company/APARINDS/"),
        ("screener:schedules-api", "company/APARINDS/"),
        ("screener:company-trades", "company/APARINDS/"),
        ("tijori:op-metrics-api", "company/{slug}/"),
        ("tijori:revenue-mix-history-api", "company/{slug}/"),
        ("tijori:market-share-peer-companies-api", "company/{slug}/"),
        ("tijori:shareholding-detail-chart-api", "company/{slug}/shareholding/"),
    ],
)
def test_cli_selection_includes_identity_and_parents(
    company_rig, pg_db, tmp_path, monkeypatch, capsys, surface, parent
):
    from argparse import Namespace

    from equity_os.interface.commands.sourcing import vendor_surface_cli as cli

    opener, ids = company_rig("APARINDS")
    monkeypatch.setattr(cli, "STOP_DIR", tmp_path / "stops")
    monkeypatch.setattr("equity_os.sourcing.transport.http_session.time.sleep", lambda _: None)
    args = Namespace(
        command="vendor",
        vendor_command="capture",
        symbol=ids.nse_symbol,
        surface=[surface],
        snapshot_root=tmp_path / "cli",
        tijori_slug=None,
        market=False,
    )
    assert (
        cli.dispatch_vendor_command(
            args,
            opener_factory=lambda: opener,
            pool_factory=pg_db.runtime_pool,
            sessions_factory=lambda sites: {
                site: SiteSession(site=site, session_cookie=SecretStr("fixture"), cookie_name="sid")
                for site in sites
            },
        )
        == 0
    )
    capsys.readouterr()
    assert any(url.endswith("/" + parent.format(slug=ids.tijori_slug)) for url in opener.calls)
    assert all("#" not in url for url in opener.calls)
    if surface.startswith("tijori:"):
        return  # The corpus retains no APARINDS bodies for these Tijori children.
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert (
            conn.execute(
                (
                    "SELECT count(*) FROM eqos.vendor_outcomes WHERE surface=%s AND statu"
                    "s IN ('OK','PARTIAL')"
                ),
                (surface.split(":")[1],),
            ).fetchone()[0]
            > 0
        )


@pytest.mark.parametrize(
    "surface", ["section-quarters", "schedules-api", "investors-api", "segments-api"]
)
def test_offline_reparse_recovers_section_and_child_inputs(
    company_rig, run_company, pg_db, tmp_path, monkeypatch, surface
):
    opener, ids = company_rig("RELIANCE" if surface == "segments-api" else "APARINDS")
    replayed = replay_after_old_parser(
        run_company, opener, ids, pg_db, tmp_path, monkeypatch, surface
    )
    assert any(status in ("OK", "PARTIAL") and n > 0 for status, n in replayed)


def replay_after_old_parser(run, opener, ids, pg_db, tmp_path, monkeypatch, surface):
    """Capture with an old failing parser for `surface`, then replay it with no network."""
    from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS
    from equity_os.sourcing.surfaces.vendor_surface_capture import reparse

    key = Site.SCREENER, surface
    current = PARSERS[key]

    def broken(body, context):
        raise ValueError("test old parser")

    monkeypatch.setitem(
        PARSERS, key, current.model_copy(update={"version": "old", "parse": broken})
    )
    specs = load_specs(
        Path("config/sourcing/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    selected = tuple(
        s for s in specs if s.site is Site.SCREENER and s.id in ("company-page", surface)
    )
    run(opener, ids, selected)
    monkeypatch.setitem(PARSERS, key, current)
    before = list(opener.calls)
    with pg_db.runtime_pool() as pool:
        reparse(
            SnapshotStore(tmp_path / "raw"),
            pool,
            VendorValuesStore(pool),
            next(
                (s for s in specs if (s.site, s.id) == key),
                next(s for s in specs if s.id == "company-page").model_copy(
                    update={"id": surface, "sections": (), "group": "READER"}
                ),
            ),
            specs,
        )
        with pool.connection() as conn:
            replayed = conn.execute(
                "SELECT o.status, count(v.outcome_id) FROM eqos.vendor_outcomes o LEFT JOIN"
                " eqos.vendor_values v ON v.outcome_id=o.id WHERE o.surface=%s AND"
                " o.parser_version<>'old' GROUP BY o.id,o.status",
                (surface,),
            ).fetchall()
    assert opener.calls == before
    return replayed


def test_replay_applies_parent_basis_gate(company_rig, run_company, pg_db, tmp_path, monkeypatch):
    # Standalone bytes under the consolidated URL refuse that basis; replay must agree.
    opener, ids = company_rig("APARINDS")
    pages = {
        r["basis"]: r
        for r in opener.rows.values()
        if r["id"] == "company-page" and r.get("symbol") == "APARINDS"
    }
    opener.overrides[pages["consolidated"]["url"]] = (
        Path(pages["standalone"]["path"]).read_bytes(),
        200,
    )
    replayed = replay_after_old_parser(
        run_company, opener, ids, pg_db, tmp_path, monkeypatch, "schedules-api"
    )
    # The corpus retains only the consolidated schedules, so none may yield cells.
    assert replayed and not any(n for _, n in replayed)


def test_replay_refuses_chart_of_another_company(
    company_rig, run_company, pg_db, tmp_path, monkeypatch
):
    # A retained chart address bound to another Screener id never replays as this company.
    from equity_os.sourcing.surfaces import vendor_surface_expand as expand

    opener, ids = company_rig("APARINDS")
    real, forged = f"/{ids.screener_company_id}/chart/", "/999999999/chart/"
    chart = next(r for r in opener.rows.values() if r["id"] == "chart-api" and r.get("path"))
    opener.overrides[
        f"https://www.screener.in/api/company{forged}?q=Price-DMA50-DMA200-Volume&days=10000"
        "&consolidated="
    ] = Path(chart["path"]).read_bytes(), 200
    original = expand.advertised

    def forging(*args):
        children, gaps = original(*args)
        return tuple(
            c.model_copy(update={"url": c.url.replace(real, forged)}) for c in children
        ), gaps

    def forged_run(*args):
        monkeypatch.setattr(expand, "advertised", forging)
        run_company(*args)
        monkeypatch.setattr(expand, "advertised", original)

    replayed = replay_after_old_parser(
        forged_run, opener, ids, pg_db, tmp_path, monkeypatch, "chart-api"
    )
    assert replayed and all(status == "UNUSABLE" and n == 0 for status, n in replayed)


def test_cli_uses_verified_registry_identity_without_watchlist(
    company_rig, run_company, pg_db, tmp_path, monkeypatch, capsys
):
    from argparse import Namespace
    from types import SimpleNamespace

    from equity_os.interface.commands.sourcing import vendor_surface_cli as cli

    opener, ids = company_rig("ANONDITA")
    specs = load_specs(
        Path("config/sourcing/vendor_surface/surfaces.yaml"),
        Path("docs/research/vendor-surface/catalog.yaml"),
    )
    run_company(opener, ids, tuple(s for s in specs if s.id == "company-page"))
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        entity, evidence = conn.execute(
            "SELECT id,evidence_input_id FROM eqos.reporting_entities"
        ).fetchone()
        ref = conn.execute(
            "SELECT c.id FROM eqos.capture_refs c JOIN eqos.capture_addresses a O"
            "N a.capture_ref_id=c.id WHERE a.url LIKE '%/consolidated/' ORDER BY "
            "c.id LIMIT 1"
        ).fetchone()[0]
        conn.execute(
            (
                "INSERT INTO eqos.evidence_input_captures(evidence_input_id,capture_r"
                "ef_id) VALUES (%s,%s)"
            ),
            (evidence, ref),
        )
        onboarding = conn.execute(
            (
                "INSERT INTO eqos.onboarding_records(identifier,identifier_namespace,"
                "outcome,entity_id,evidence_input_id) VALUES ('ANONDITA','NSE_SYMBOL'"
                ",'PARTIAL',%s,%s) RETURNING id"
            ),
            (entity, evidence),
        ).fetchone()[0]
        conn.execute(
            (
                "INSERT INTO eqos.namespace_verifications(onboarding_record_id,unit,s"
                "tate,evidence_input_id) VALUES (%s,'SCREENER','VERIFIED',%s)"
            ),
            (onboarding, evidence),
        )
    monkeypatch.setattr(cli, "load_watchlist_config", lambda _: SimpleNamespace(stocks=[]))
    monkeypatch.setattr(cli, "STOP_DIR", tmp_path / "stops")
    monkeypatch.setattr("equity_os.sourcing.transport.http_session.time.sleep", lambda _: None)
    args = Namespace(
        command="vendor",
        vendor_command="capture",
        symbol="ANONDITA",
        surface=["screener:chart-api"],
        snapshot_root=tmp_path / "raw",
        tijori_slug=None,
        market=False,
    )
    assert (
        cli.dispatch_vendor_command(
            args,
            opener_factory=lambda: opener,
            pool_factory=pg_db.runtime_pool,
            sessions_factory=lambda sites: {
                Site.SCREENER: SiteSession(
                    site=Site.SCREENER, session_cookie=SecretStr("fixture"), cookie_name="sid"
                )
            },
        )
        == 0
    )
    capsys.readouterr()
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM eqos.vendor_outcomes WHERE surface='company-pag"
                "e' AND status='KEPT'"
            ).fetchone()[0]
            == 4
        )


def test_replay_expands_only_verified_captures_at_shared_url(
    company_rig, pg_db, tmp_path, monkeypatch
):
    from psycopg.rows import dict_row
    from vendor_surface_support import capture_response

    from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS
    from equity_os.extraction.vendors.screener.screener_session_models import Basis
    from equity_os.sourcing.surfaces.vendor_surface_capture import (
        company_requests,
        reparse,
        retained_graph,
    )

    _, ids = company_rig("APARINDS")
    specs = tuple(
        s
        for s in load_specs(
            Path("config/sourcing/vendor_surface/surfaces.yaml"),
            Path("docs/research/vendor-surface/catalog.yaml"),
        )
        if s.site is Site.SCREENER and s.id in ("company-page", "quick-ratios-api", "schedules-api")
    )
    page = next(r for r in company_requests(specs, ids) if r.basis is Basis.CONSOLIDATED)
    valid, _ = retained("screener", "company-page", "APARINDS", "consolidated")
    rejected, _ = retained("screener", "company-page", "APARINDS", "standalone")
    store = SnapshotStore(tmp_path / "raw")
    from equity_os.sourcing.surfaces.vendor_surface_capture import Request

    ratios = next(s for s in specs if s.id == "quick-ratios-api")
    current = PARSERS[Site.SCREENER, ratios.id]
    monkeypatch.setitem(
        PARSERS, (Site.SCREENER, ratios.id), current.model_copy(update={"version": "old"})
    )
    with pg_db.runtime_pool() as pool:
        # Rejected first: an admitted URL must not reuse its schedule inputs either.
        bad = capture_response(pool, store, tmp_path, page, rejected.raw)
        capture_response(pool, store, tmp_path, page, valid.raw)
        child = Request(
            spec=ratios,
            url="https://www.screener.in/api/company/2446/quick_ratios/",
            ids=ids,
            basis=Basis.CONSOLIDATED,
            due_since=None,
        )
        raw, _ = retained("screener", "quick-ratios-api")
        dependent = capture_response(pool, store, tmp_path, child, raw.raw)
        monkeypatch.setitem(PARSERS, (Site.SCREENER, ratios.id), current)
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT c.*, a.url, 'APARINDS' AS symbol FROM eqos.capture_refs c "
                "JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id ORDER BY c.id"
            ).fetchall()
        graph = retained_graph(store, pool, specs, ids, rows)
        reparse(store, pool, VendorValuesStore(pool), ratios, specs)
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT o.status, count(v.outcome_id) FROM eqos.vendor_outcomes o "
                "LEFT JOIN eqos.vendor_values v ON v.outcome_id=o.id "
                "WHERE o.capture_ref_id=%s AND o.parser_version<>'old' GROUP BY o.id",
                (dependent.capture_ref_id,),
            ).fetchall() == [("UNUSABLE", 0)]
            assert (
                conn.execute(
                    "SELECT count(*) FROM eqos.vendor_values WHERE capture_ref_id=%s "
                    "AND basis='consolidated'",
                    (bad.capture_ref_id,),
                ).fetchone()[0]
                == 0
            )
        assert child.url not in graph
        assert "https://www.screener.in/api/company/6594631/quick_ratios/" in graph
        schedules = [r for r in graph.values() if r.spec.id == "schedules-api"]
        assert schedules
        assert {
            cell.provenance.file_sha256
            for r in schedules
            for row in r.parent["page_section"].rows
            for cell in row.cells
        } == {hashlib.sha256(valid.raw).hexdigest()}


def test_replay_uses_each_captures_parent_not_oldest(
    company_rig, run_company, pg_db, tmp_path, monkeypatch
):
    from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS, ParserEntry
    from equity_os.sourcing.surfaces import vendor_surface_capture as cap
    from equity_os.storage.records.vendor_values_store import VendorValue

    opener, ids = company_rig("APARINDS")
    specs = tuple(
        s for s in SPECS if s.site is Site.SCREENER and s.id in ("company-page", "schedules-api")
    )
    key = Site.SCREENER, "schedules-api"

    # Tag the parent's capture id instead of printing vendor readings.
    def parent_stamp(body, context):
        stamp = context.parent["page_section"].rows[0].cells[0].provenance.retrieved_at.isoformat()
        return (
            VendorValue(
                table_key="review",
                row_index=0,
                column_index=0,
                locator="review",
                row_label="",
                column_label="",
                raw_text=stamp,
                value=None,
            ),
        )

    monkeypatch.setitem(PARSERS, key, ParserEntry(version="review:parents.v1", parse=parent_stamp))
    for _ in range(2):
        run_company(opener, ids, specs)
    monkeypatch.setitem(PARSERS, key, ParserEntry(version="review:parents.v2", parse=parent_stamp))
    with pg_db.runtime_pool() as pool:
        cap.reparse(
            SnapshotStore(tmp_path / "raw"),
            pool,
            VendorValuesStore(pool),
            next(s for s in specs if s.id == "schedules-api"),
            specs,
        )
        with pool.connection() as conn:
            changed = conn.execute(
                "SELECT count(*) FROM eqos.vendor_values a JOIN eqos.vendor_outcomes oa ON  "
                "oa.id=a.outcome_id JOIN eqos.vendor_outcomes ob ON  "
                "ob.capture_ref_id=oa.capture_ref_id AND ob.surface=oa.surface JOIN  "
                "eqos.vendor_values b ON b.outcome_id=ob.id WHERE  "
                "oa.parser_version='review:parents.v1' AND  "
                "ob.parser_version='review:parents.v2' AND a.raw_text<>b.raw_text"
            ).fetchone()[0]
        assert changed == 0, f"{changed} child captures replayed against another parent capture"


def test_slug_verifier_sanitizes_frozen_reader_logs(company_rig, run_company):
    import structlog.testing
    from lxml import etree

    from equity_os.extraction.surfaces.vendor_surface_parse import Body

    opener, ids = company_rig("HDFCBANK", slug=False)
    ids = ids.model_copy(update={"tijori_company_id": None})
    search = "https://www.tijorifinance.com/api/v1/ind/company_search/?q=synthetic-isin"
    opener.overrides[search] = (
        json.dumps([{"type": "companies", "slug": "hdfc-bank-limited"}]).encode(),
        200,
    )
    url = "https://www.tijorifinance.com/company/hdfc-bank-limited/financials/"
    tree = Body(raw=Path(opener.rows[url]["path"]).read_bytes()).tree()
    island = tree.xpath('//script[@id="fin_tables_data"]')[0]
    island.text = '{"review_private_sentinel":{},' + island.text.lstrip()[1:]
    opener.overrides[url] = etree.tostring(tree), 200
    specs = tuple(s for s in SPECS if s.site is Site.TIJORI and s.id == "company-financials")
    with structlog.testing.capture_logs() as logs:
        run_company(opener, ids, specs)
    leaked = sum("review_private_sentinel" in str(entry) for entry in logs)
    assert leaked == 0, f"{leaked} unsanitized reader log events during slug verification"


def test_claim_failure_does_not_change_capture_usability(company_rig, run_company, pg_db, tmp_path):
    from equity_os.sourcing.surfaces import vendor_surface_due as due
    from equity_os.storage.records.vendor_values_store import Outcome, OutcomeStatus

    opener, ids = company_rig("APARINDS")
    specs = tuple(s for s in SPECS if s.site is Site.SCREENER and s.id == "company-page")
    run_company(opener, ids, specs)
    with pg_db.runtime_pool() as pool:
        before = due.history(pool, specs)
        assert all(s.usable for items in before.values() for s in items)
        ref = next(iter(before.values()))[0].ref
        VendorValuesStore(pool).record(
            ref,
            Outcome(
                surface="company-page",
                parser_version="claims:fake:spans.v2:failed:1",
                parser_sha256="0" * 64,
                status=OutcomeStatus.FAILED,
                symbol=None,
                detail="TimeoutError",
            ),
            row_count=0,
        )
        after = due.history(pool, specs)
        assert all(s.usable for items in after.values() for s in items), (
            "claims failure overrides acquisition outcome"
        )


def test_unusable_company_surfaces_are_not_requested_and_redirects_are_corrected():
    """Live 2026-10-30/31 captures never returned a page for these requests (eqos-aa6.22)."""
    from equity_os.sourcing.surfaces.vendor_surface_expand import child

    # Off-host BSE PDF redirect, vendor move to /factors/, and an NSE-symbol 404 never
    # yield a usable page: requesting them only reports COMPANY_OVERDUE (not-capturable.md).
    assert not {s.id for s in SPECS} & {
        "quarter-source-pdf",
        "company-benchmarking",
        "market-share-api",
    }
    # The modal 302s to the company page unless sent as XHR, as the vendor page sends it.
    assert next(s for s in SPECS if s.id == "commentary-modal").xhr
    # The unslashed chart address 301s to its slashed form.
    _, context = retained("screener", "company-page", "APARINDS")
    spec = next(s for s in SPECS if s.id == "shareholding-detail-chart-api")
    assert child(spec, context, field="f", source="s").url.endswith("/f/s/")


def test_reparse_binds_timeline_continuation_through_its_root(
    company_rig, run_company, pg_db, tmp_path, monkeypatch
):
    # A continuation address names no company itself; capture binds it through its traversal
    # root, so a replay that refuses it as unbound would leave the traversal never usable.
    from equity_os.extraction.surfaces.vendor_surface_parse import PARSERS, Body
    from equity_os.sourcing.surfaces.vendor_surface_capture import reparse
    from equity_os.sourcing.surfaces.vendor_surface_market import query_url

    opener, ids = company_rig("HDFCBANK")
    row = next(r for r in opener.rows.values() if r["id"] == "company-timeline-api")
    body = Body(raw=Path(row["path"]).read_bytes())
    cursor = body.tree().xpath('//tr[contains(@class,"d-none")]/td')[0].text_content().strip()
    terminal = body.raw.replace(b"True</td>", b"False</td>")
    opener.overrides[query_url(row["url"], timestamp=cursor)] = terminal, 200
    specs = tuple(
        s
        for s in SPECS
        if s.site is Site.TIJORI and s.id in ("company-financials", "company-timeline-api")
    )
    run_company(opener, ids, specs)
    key = Site.TIJORI, "company-timeline-api"
    monkeypatch.setitem(PARSERS, key, PARSERS[key].model_copy(update={"version": "review.v1"}))
    with pg_db.runtime_pool() as pool:
        timeline = next(s for s in specs if s.id == key[1])
        assert (
            reparse(SnapshotStore(tmp_path / "raw"), pool, VendorValuesStore(pool), timeline, specs)
            == 2
        )
        with pool.connection() as conn:
            replayed = conn.execute(
                "SELECT status, parser_version FROM eqos.vendor_outcomes "
                "WHERE surface=%s AND traversal_key IS NULL AND id > (SELECT max(id) "
                "FROM eqos.vendor_outcomes WHERE parser_version LIKE %s) ORDER BY id",
                (key[1], "%traversal%"),
            ).fetchall()
    assert replayed == [("OK", "review.v1")] * 2


def test_concall_summary_spec_loads_and_expands_one_request_per_notes_button():
    from equity_os.sourcing.surfaces.vendor_surface_expand import EXPANSIONS, parent_surface

    spec = next(s for s in SPECS if s.id == "concall-summary")
    assert parent_surface(spec) == "company-page"
    body, context = retained("screener", "company-page", "APARINDS")
    notes = set(re.findall(rb'data-url="(/concalls/summary/[0-9]+/)"', body.raw))
    context = context.model_copy(update={"parent": {"spec": spec.model_dump()}})
    urls = [r.url for r in EXPANSIONS["screener_concall_summaries"](body, context)]
    assert notes and len(urls) == len(notes)
    assert {u.removeprefix("https://www.screener.in").encode() for u in urls} == notes
    # The same routes outside a concalls row's Notes button are not advertised summaries.
    for marker in (b"documents concalls flex-column", b"plausible-event-name=Concall+Notes"):
        moved = type(body)(raw=body.raw.replace(marker, b"documents other"))
        advertised = len(EXPANSIONS["screener_concall_summaries"](moved, context))
        assert advertised == 0, "routes outside a Notes button were advertised"


@pytest.fixture
def summary_cli(company_rig, pg_db, tmp_path, monkeypatch, capsys):
    """Run `vendor capture --surface screener:concall-summary` through the public CLI."""
    from argparse import Namespace

    from equity_os.interface.commands.sourcing import vendor_surface_cli as cli

    monkeypatch.setattr(cli, "STOP_DIR", tmp_path / "stops")
    monkeypatch.setattr("equity_os.sourcing.transport.http_session.time.sleep", lambda _: None)
    opener, ids = company_rig("APARINDS")

    def run(frozen=None, budget=None, market=False, surface="screener:concall-summary"):
        opener.calls.clear()
        file = None
        if frozen is not None:
            file = tmp_path / "frozen.txt"
            file.write_text("\n".join(sorted(frozen)) + "\n")
        args = Namespace(
            command="vendor",
            vendor_command="capture",
            symbol=None if market else ids.nse_symbol,
            surface=[surface],
            snapshot_root=tmp_path / "cli",
            tijori_slug=None,
            market=market,
            frozen=file,
            budget=budget,
        )
        code = cli.dispatch_vendor_command(
            args,
            opener_factory=lambda: opener,
            pool_factory=pg_db.runtime_pool,
            sessions_factory=lambda sites: {
                site: SiteSession(site=site, session_cookie=SecretStr("fixture"), cookie_name="sid")
                for site in sites
            },
        )
        capsys.readouterr()
        return code, set(opener.calls)

    run.opener = opener
    return run


def test_frozen_set_and_budget_through_the_public_cli(summary_cli):
    code, everything = summary_cli()
    summaries = {u for u in everything if "/concalls/summary/" in u}
    parents = everything - summaries
    assert code == 0 and summaries and parents

    assert summary_cli(frozen=everything) == (0, everything)

    # A summary missing from, or an address extra to, the frozen set stops before any child.
    for frozen in (everything - {min(summaries)}, everything | {"https://www.screener.in/x/"}):
        code, calls = summary_cli(frozen=frozen)
        assert code != 0 and calls == parents

    # A budget below the set stops at the budget and never leaves the frozen set.
    code, calls = summary_cli(frozen=everything, budget=len(parents) + 2)
    assert code != 0 and len(calls) == len(parents) + 2 and calls <= everything


def test_frozen_set_stops_without_children_or_for_unlisted_parents(summary_cli):
    _, everything = summary_cli()
    summaries = {u for u in everything if "/concalls/summary/" in u}
    parents = everything - summaries
    # Every advertised summary vanishing still stops nonzero once the parents are read.
    for url in parents:
        body = Path(summary_cli.opener.rows[url]["path"]).read_bytes()
        summary_cli.opener.overrides[url] = body.replace(b"Concall+Notes", b"gone"), 200
    assert summary_cli(frozen=everything) == (1, parents)
    summary_cli.opener.overrides.clear()
    # A parent missing from the set, or an empty set, stops before any request.
    for frozen in (everything - {min(parents)}, set()):
        assert summary_cli(frozen=frozen) == (1, set())


@pytest.mark.parametrize(
    ("market", "surface", "frozen", "budget"),
    [
        (True, "screener:concall-summary", {"https://www.screener.in/x/"}, None),
        (True, "screener:concall-summary", None, 5),
        (False, "tijori:company-financials", {"https://www.screener.in/x/"}, None),
        (False, "screener:schedules-api", {"https://www.screener.in/x/"}, None),
        (False, "screener:concall-summary", None, -1),
    ],
)
def test_capture_rejects_restrictions_a_path_cannot_honour(
    summary_cli, market, surface, frozen, budget
):
    assert summary_cli(frozen=frozen, budget=budget, market=market, surface=surface) == (2, set())
