"""Retained HTTP responses served through the real CLI and disposable PG harness."""

import hashlib
import io
import json
from datetime import UTC, datetime
from email.message import Message
from functools import partial
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr

from fundamentals.ingest.screener_session_models import Basis, BasisTopology
from fundamentals.ingest.vendor_surface_parse import Body, CompanyIds, ParseContext
from fundamentals.store.snapshot_store import SnapshotStore

INDEX = Path("docs/research/vendor-surface/snapshots-index.json")


def load_request_index():
    """Read both indexes by URL, preserving the original fixtures on duplicates."""
    rows = json.loads(INDEX.read_text()) + json.loads(
        INDEX.with_name("kinds-index.json").read_text()
    )
    requests = {}
    for row in rows:
        requests.setdefault(row["url"], row)
    return requests


class RetainedResponseOpener(OpenerDirector):
    """Serve retained bodies and explicit synthetic pagination at the HTTP boundary."""

    def __init__(self):
        super().__init__()
        self.rows, self.calls, self.overrides = load_request_index(), [], {}

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        row = self.rows.get(request.full_url)
        raw, status = b"unretained", 404
        if row and row.get("path"):
            raw, status = Path(row["path"]).read_bytes(), row.get("status", 200)
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        raw, status = self.overrides.get(request.full_url, (raw, status))
        return HTTPError(request.full_url, status, "fixture", {}, io.BytesIO(raw))


class RetainedOpener(OpenerDirector):
    """A finite fake: the retained page, one chart metric set, otherwise 404."""

    def __init__(self, stop=False):
        super().__init__()
        self.rows, self.calls, self.stop = load_request_index(), [], stop

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        parts = urlsplit(request.full_url)
        metric = parse_qs(parts.query).get("q", [""])[0]
        identifier = "chart-api" if "/chart/" in parts.path else "company-page"
        row = next(
            item
            for item in self.rows.values()
            if item["site"] == "screener"
            and item["id"] == identifier
            and item["kind"] == "response"
        )
        if identifier == "company-page":
            row = self.rows[request.full_url]
        status = 429 if self.stop and len(self.calls) == 3 else 200
        if identifier == "chart-api" and metric != "Price-DMA50-DMA200-Volume" and status == 200:
            status = 404
        raw = Path(row["path"]).read_bytes() if status == 200 else b"fixture refusal"
        if status == 200:
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        headers = Message()
        headers["Content-Type"] = "application/json" if identifier == "chart-api" else "text/html"
        response = HTTPError(request.full_url, status, "fixture", headers, io.BytesIO(raw))
        if status != 200:
            raise response
        return response


@pytest.fixture
def rig(pg_db, tmp_path, monkeypatch):
    """Inject only external factories; exercise the production coordinator and stores."""
    from fundamentals.api import cli, vendor_surface_cli
    from fundamentals.ingest.vendor_surface_fetch import Site, SiteSession
    from fundamentals.ingest.vendor_surface_specs import load_specs

    def tracer_specs(path, catalog):
        """Keep the Phase 1 rig's two-surface contract as production breadth grows."""
        return tuple(
            spec.model_copy(update={"sections": ()})
            for spec in load_specs(path, catalog)
            if spec.id in ("company-page", "chart-api")
        )

    monkeypatch.setattr(vendor_surface_cli, "load_specs", tracer_specs)
    monkeypatch.setattr("fundamentals.ingest.vendor_surface_canary.load_specs", tracer_specs)
    monkeypatch.setattr(vendor_surface_cli, "STOP_DIR", tmp_path / "stops", raising=False)
    opener = RetainedOpener()
    root = tmp_path / "captures"
    session = SiteSession(
        site=Site.SCREENER, session_cookie=SecretStr("synthetic"), cookie_name="sessionid"
    )
    dispatch = partial(
        vendor_surface_cli.dispatch_vendor_command,
        opener_factory=lambda: opener,
        pool_factory=pg_db.runtime_pool,
        store_factory=SnapshotStore,
        sessions_factory=lambda sites: {Site.SCREENER: session},
    )
    monkeypatch.setattr(cli, "dispatch_vendor_command", dispatch)
    monkeypatch.setattr("fundamentals.ingest.http_session.time.sleep", lambda _: None)
    return opener, root


def capture_response(pool, store, stop_dir, request, raw, status=200):
    """Serve one retained or deliberately corrupted response through real capture/storage."""
    from fundamentals.ingest.vendor_surface_capture import capture
    from fundamentals.ingest.vendor_surface_fetch import PgSiteLock, SiteSession, VendorFetcher
    from fundamentals.store.vendor_values_store import VendorValuesStore

    class ResponseOpener(OpenerDirector):
        def open(self, outbound, timeout):
            assert outbound.full_url == request.url and timeout > 0
            return HTTPError(outbound.full_url, status, "fixture", Message(), io.BytesIO(raw))

    locks = PgSiteLock(pool)
    try:
        site = request.spec.site
        session = SiteSession(site=site, session_cookie=SecretStr("fixture"), cookie_name="sid")
        fetcher = VendorFetcher(
            store, {site: session}, ResponseOpener(), stop_dir, locks, spacing_seconds=0
        )
        return capture(fetcher, store, pool, VendorValuesStore(pool), request)[0]
    finally:
        locks.close()


IDS = {
    "APARINDS": (211, 2446, 6594631, "apar-industries-limited", 4290),
    "ANONDITA": (1285614, 142778403, 142927483, "anondita-medicare-ltd", 58631),
    "RELIANCE": (2726, 811, 6598251, "reliance-industries-limited", 242),
    "NETWEB": (1284419, 104235517, None, "netweb-technologies-india-ltd", 55416),
    "HDFCBANK": (1298, 1789, 6596237, "hdfc-bank-limited", 129),
}


def retained(site, surface, symbol=None, basis="standalone"):
    rows = (
        json.loads(INDEX.with_name("kinds-index.json").read_text())
        if symbol
        else json.loads(INDEX.read_text())
    )
    row = next(
        r
        for r in rows
        if r["site"] == site
        and r["id"] == surface
        and r["kind"] == "response"
        and r["status"] == 200
        and (symbol is None or r["symbol"] == symbol and (r["basis"] in (basis, "na")))
    )
    raw = Path(row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    symbol = symbol or (
        "HDFCBANK"
        if surface in ("peers-api", "company-timeline-api")
        else "RELIANCE"
        if site == "tijori" or surface in ("segments-api", "investors-api")
        else "HDFCBANK"
        if surface == "company-search-api"
        else "APARINDS"
    )
    company, standalone, consolidated, slug, tijori = IDS[symbol]
    ids = CompanyIds(
        nse_symbol=symbol,
        isin="",
        tijori_slug=slug,
        tijori_company_id=tijori,
        screener_company_id=company,
        topology=BasisTopology(
            standalone_warehouse_id=standalone, consolidated_warehouse_id=consolidated
        ),
    )
    return Body(raw=raw), ParseContext(
        ids=ids,
        basis=Basis(basis),
        url=row["url"],
        retrieved_at=datetime(2026, 10, 28, tzinfo=UTC),
        body_sha256=row["sha256"],
        capture_id="retained-g0",
    )
