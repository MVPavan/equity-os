"""Retained HTTP responses served through the real CLI and disposable PG harness."""

import hashlib
import io
import json
from email.message import Message
from functools import partial
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import SecretStr

from fundamentals.store.snapshot_store import SnapshotStore

INDEX = Path("docs/research/vendor-surface/snapshots-index.json")


def load_request_index():
    """Read only explicitly indexed reference bodies, verifying every returned body."""
    return json.loads(INDEX.read_text())


class RetainedOpener:
    """A finite fake: the retained page, one chart metric set, otherwise 404."""

    def __init__(self, stop=False):
        self.rows, self.calls, self.stop = load_request_index(), [], stop

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        parts = urlsplit(request.full_url)
        metric = parse_qs(parts.query).get("q", [""])[0]
        identifier = "chart-api" if "/chart/" in parts.path else "company-page"
        row = next(
            item
            for item in self.rows
            if item["site"] == "screener"
            and item["id"] == identifier
            and item["kind"] == "response"
        )
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
        sessions_factory=lambda: {Site.SCREENER: session},
    )
    monkeypatch.setattr(cli, "dispatch_vendor_command", dispatch)
    monkeypatch.setattr("fundamentals.ingest.http_session.time.sleep", lambda _: None)
    return opener, root
