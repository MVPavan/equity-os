"""Offline transport and raw-first assertions shared by the two Tijori CLIs."""

import argparse
import hashlib
import io
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector

import pytest
from lxml import etree, html

from fundamentals.api import tijori_overview_cli, tijori_shareholding_cli
from fundamentals.ingest.tijori_source import TijoriCredentials, TijoriSource, TijoriSourceConfig
from fundamentals.ingest.tijori_tables import TijoriParseError
from fundamentals.ingest.vendor_surface_canary import yield_drift
from fundamentals.ingest.vendor_surface_fetch import Site, SiteStopped
from fundamentals.ingest.vendor_surface_parse import PARSERS
from fundamentals.store.snapshot_store import SnapshotStore


class FixtureOpener(OpenerDirector):
    """Serve whichever bytes the characterization tests inject at the old transport seam."""

    status = 200

    def open(self, request, timeout):
        kind = "shareholding" if request.full_url.endswith("/shareholding/") else "overview"
        slug = urlsplit(request.full_url).path.split("/")[2]
        source = TijoriSource(TijoriSourceConfig())
        raw = getattr(source, f"_fetch_{kind}_bytes")(
            slug, TijoriCredentials(session_cookie="synthetic")
        )
        return HTTPError(request.full_url, self.status, "fixture", Message(), io.BytesIO(raw))


@pytest.fixture
def tijori_cli_capture(pg_db, tmp_path, monkeypatch):
    """Keep real capture/PG behavior while replacing HTTP and selecting isolated storage."""
    opener = FixtureOpener()
    monkeypatch.setattr(
        tijori_overview_cli, "open_pool", lambda *a: pg_db.runtime_pool(), raising=False
    )
    monkeypatch.setattr(tijori_overview_cli, "build_opener", lambda: opener, raising=False)
    monkeypatch.setattr(tijori_overview_cli, "_STOP_DIR", tmp_path / "stops", raising=False)
    monkeypatch.setattr(
        tijori_overview_cli,
        "SnapshotStore",
        lambda root: SnapshotStore(tmp_path / "snapshots"),
        raising=False,
    )
    return opener


def assert_raw_first(kind, case, opener, pg_db, tmp_path, monkeypatch):
    """A registered, readable response and outcome survive success, parse error, or 429."""
    tree = html.fromstring(
        (Path(__file__).parent / "fixtures" / f"synthetic_tijori_{kind}.html").read_bytes()
    )
    nodes = tree.xpath("//script[@id='is_auth'][1]")[:1]
    if kind == "overview":
        nodes += tree.xpath("//script[@id='company_details_data' or @id='ratios_table']")
        nodes[-1].text = '[{"name":"pe","value":"12"}]'
    else:
        nodes += tree.xpath("//h1 | //table[@id='company_detailed']")
        for row in nodes[-1].xpath("./tbody/tr[position()>1]"):
            row.getparent().remove(row)
    raw = b"<html><body>" + b"".join(etree.tostring(n) for n in nodes) + b"</body></html>"
    if case == "failed":
        raw = b"<html><body>unparseable fixture</body></html>"
    opener.status = 429 if case == "stopped" else 200
    clock = datetime(2026, 10, 28, tzinfo=UTC)
    monkeypatch.setattr(
        "fundamentals.ingest.vendor_surface_fetch.datetime", SimpleNamespace(now=lambda tz: clock)
    )
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", "synthetic")
    monkeypatch.setattr(TijoriSource, f"_fetch_{kind}_bytes", lambda *a: raw)
    entry = PARSERS[Site.TIJORI, f"company-{kind}"]
    parsed = []

    def parse(body, context):
        with pg_db.runtime_pool() as pool, pool.connection() as conn:
            assert conn.execute("SELECT count(*) FROM eqos.capture_refs").fetchone() == (1,)
        assert body.raw == raw and context.retrieved_at == clock
        parsed.append(True)
        return entry.parse(body, context)

    monkeypatch.setitem(
        PARSERS, (Site.TIJORI, f"company-{kind}"), entry.model_copy(update={"parse": parse})
    )
    out = tmp_path / "artifacts"
    module = tijori_overview_cli if kind == "overview" else tijori_shareholding_cli
    command = getattr(module, f"run_tijori_{kind}_command")
    args = argparse.Namespace(
        stock="TITAN",
        config="config/watchlist.yaml",
        out=str(out),
        section=None,
        snapshot_root=tmp_path / "snapshots",
    )
    credentials = TijoriCredentials(session_cookie="synthetic")
    if case == "ok":
        command(args, credentials=credentials)
    else:
        with pytest.raises(SiteStopped if case == "stopped" else TijoriParseError):
            command(args, credentials=credentials)
        assert not out.exists()
    assert len(parsed) == (0 if case == "stopped" else 1)
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        rows = conn.execute(
            "SELECT c.source_id,c.surface,c.request_key,c.capture_id,c.blob_sha256,"
            "c.record_sha256,o.status FROM eqos.capture_refs c JOIN eqos.vendor_outcomes o "
            "ON o.capture_ref_id=c.id WHERE o.surface=substring(c.surface from 4)"
        ).fetchall()
        assert len(rows) == 1
        source, surface, key, capture_id, digest, record_digest, status = rows[0]
        assert (source, surface, status) == (
            "tijori",
            f"vs.company-{kind}",
            {"ok": "OK", "failed": "FAILED", "stopped": "UNUSABLE"}[case],
        )
        store = SnapshotStore(tmp_path / "snapshots")
        record = store.get_capture(source, surface, key, capture_id)
        assert store.read_body(record) == raw
        assert digest == hashlib.sha256(raw).hexdigest()
        assert record.record_sha256 == record_digest
        assert record.retrieved_at == clock
        assert yield_drift(pool, datetime.min.replace(tzinfo=UTC)) == ()
    assert (tmp_path / "stops" / "STOP-tijori").exists() == (case == "stopped")
    if case == "ok":
        paths = list(out.glob("*.json"))
        assert paths
        for path in paths:
            metadata = json.loads(path.read_text())["metadata"]
            assert datetime.fromisoformat(metadata["retrieved_at"]) == clock
