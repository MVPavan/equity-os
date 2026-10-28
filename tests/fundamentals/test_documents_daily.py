"""DOCS-1 daily/backfill through real intake transactions and fake outbound boundaries."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import time
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from coverage_support import watchlist
from onboarding_support import seed
from pg_support import PgTestDatabase
from test_nse_documents import read_probe

from fundamentals.contracts.ledger import DecisionKind, SubjectKind
from fundamentals.entity.discovery import Request
from fundamentals.ledger.lifecycle import decide
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]


class Lane:
    """Controlled exchange, clock and bd process at the real CLI's external boundaries."""

    def __init__(self, db: PgTestDatabase, root: Path) -> None:
        self.db, self.root = db, root
        self.at = datetime(2026, 10, 27, 12, tzinfo=UTC)
        self.tick = 0
        self.entity = seed(db, "APARINDS", "INE372A01015", "APARINDS", "532259")
        self.rows = json.loads(read_probe("nse_announcements.json"))
        self.board = json.loads(read_probe("nse_board_meetings.json"))
        self.reports = read_probe("nse_annual_reports.json")
        self.page = read_probe("company_APARINDS_consolidated.html")
        self.sent: list[Request] = []
        self.status: dict[str, tuple[int, bytes] | Exception] = {}
        self.refs: set[str] = set()
        self.bd_calls: list[list[str]] = []
        self.lookup: tuple[int, str] = (0, "")
        self.create_failure = False
        self.args = argparse.Namespace(
            documents_command="daily", snapshot_root=root / "snapshots", lock_root=root / "locks"
        )

    def clock(self) -> datetime:
        """Unique real-fetch instants on a controlled calendar day."""
        self.tick += 1
        return self.at + timedelta(microseconds=self.tick)

    def send(self, request: Request) -> tuple[int, bytes]:
        """Serve retained listings, synthetic documents and scripted transport failures."""
        self.sent.append(request)
        value = self.status.get(request.url) or self.status.get(request.surface)
        if isinstance(value, Exception):
            raise value
        if value is not None:
            return value
        if request.surface == "EQUITY_L":
            return (
                200,
                b"SYMBOL,NAME OF COMPANY,SERIES,ISIN NUMBER\nAPARINDS,Synthetic,EQ,INE372A01015\n",
            )
        if request.surface == "ANNOUNCEMENTS_LISTING":
            return 200, json.dumps(self.rows).encode()
        if request.surface == "BOARD_MEETINGS_LISTING":
            return 200, json.dumps(self.board).encode()
        if request.surface == "ANNUAL_REPORTS_LISTING":
            return 200, self.reports
        if request.source_id == "screener-subscriber":
            return 200, self.page
        return 200, b"%PDF-SYNTHETIC identical document bytes"

    def bd(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Persist references independent of open/closed status, or fail the process boundary."""
        argv = list(args)
        self.bd_calls.append(argv)
        if argv[0] == "list":
            code, text = self.lookup
            return subprocess.CompletedProcess(
                argv,
                code,
                text
                or json.dumps(
                    [{"external_ref": ref, "status": "closed"} for ref in sorted(self.refs)]
                ),
                "",
            )
        if self.create_failure:
            raise subprocess.TimeoutExpired("bd", 30)
        ref = argv[argv.index("--external-ref") + 1]
        assert ref not in self.refs
        self.refs.add(ref)
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    def run(self) -> int:
        """Invoke the actual daily/backfill entry point with no external network or bd."""
        from fundamentals.api.documents_cli import run_documents

        return run_documents(self.args, send=self.send, clock=self.clock, bd=self.bd)

    def counts(self) -> tuple[int, int, int]:
        """Observe committed revisions, attempts and document registrations."""
        with self.db.runtime_pool() as pool, pool.connection() as conn:
            values = tuple(
                conn.execute(query).fetchall()[0][0]
                for query in (
                    "SELECT count(*) FROM eqos.document_observations",
                    "SELECT count(*) FROM eqos.document_attempts",
                    "SELECT count(*) FROM eqos.capture_refs WHERE source_id='nse-documents'",
                )
            )
            return values[0], values[1], values[2]


@pytest.fixture
def lane(pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Lane]:
    """A covered issuer in a fixture-created test DB; no real sleeps or network calls."""
    world = Lane(pg_db, tmp_path)
    for key, value in pg_db.cli_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with ExitStack() as stack:
        pools = {
            role: stack.enter_context(pg_db.role_pool(role))
            for role in (PgRole.RUNTIME, PgRole.OWNER)
        }
        watchlist(pools, world.entity, SnapshotStore(tmp_path / "seed"))
        yield world


def test_repeat_is_idempotent_and_future_meeting_amendments_are_seen(
    lane: Lane,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The future horizon is reread daily; shared document bytes retain both URL identities."""
    from fundamentals.pg.document_intake import DocumentIntake

    assert lane.run() == 0
    out = capsys.readouterr().out
    assert out.count("RESULTS_SCHEDULED\t") == 1 and "2026-10-29" in out
    assert len(lane.refs) == 3 and lane.counts() == (47, 4, 4)
    baseline = lane.counts()
    lane.sent.clear()
    assert lane.run() == 0 and lane.counts() == baseline
    assert not any(r.source_id.endswith("-documents") for r in lane.sent)
    assert capsys.readouterr().out.count("\texists") == 3
    assert (
        len(
            [
                b
                for b in SnapshotStore(lane.args.snapshot_root).blob_inventory()
                if b.source_id == "nse-documents"
            ]
        )
        == 1
    )
    future = next(row for row in lane.board if row["bm_date"] == "29-Oct-2026")
    for offset, meeting in ((1, "03-Nov-2026"), (2, "04-Nov-2026")):
        lane.at += timedelta(days=1)
        if offset == 1:
            lane.board.append(future | {"bm_timestamp": "27-Oct-2026 12:00:00", "bm_date": meeting})
        else:
            lane.board[-1]["bm_date"] = meeting
        assert lane.run() == 0
        assert lane.counts()[0] == baseline[0] + offset
        assert meeting in [r["bm_date"] for r in lane.board]
        with lane.db.runtime_pool() as pool, pool.connection() as conn:
            intake = DocumentIntake(conn)
            assert intake.coverage(lane.entity, "BOARD_MEETINGS_LISTING") == lane.at.date()
            assert date(2026, 11, 3 + (offset == 2)) in [
                datetime.strptime(o.payload["bm_date"], "%d-%b-%Y").date()
                for o in intake.latest(lane.entity, "BOARD_MEETINGS_LISTING")
            ]


def test_retries_are_bounded_per_revision_and_same_url_can_recover(
    lane: Lane,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A prior revision's terminal failure cannot poison a correction of the same URL."""
    lane.rows = [next(row for row in lane.rows if "about Transcript" in row["attchmntText"])]
    lane.board = []
    url = lane.rows[0]["attchmntFile"]
    lane.status[url] = TimeoutError()
    for count in range(1, 3):
        lane.run()
        assert lane.counts()[1] == count
    lane.status.pop(url)
    assert lane.run() == 0 and lane.counts()[1:] == (3, 1)
    lane.rows[0]["revision"] = 2
    lane.status[url] = (404, b"")
    assert lane.run() == 4 and "HTTP_404" in capsys.readouterr().out
    lane.rows[0]["revision"] = 3
    lane.status.pop(url)
    assert lane.run() == 0 and lane.counts()[1:] == (5, 2)
    lane.rows[0]["revision"] = 4
    lane.status[url] = TimeoutError()
    for _ in range(5):
        lane.run()
    before = len(lane.sent)
    assert lane.run() == 4
    assert not any(r.url == url for r in lane.sent[before:])
    assert "GAP\tAPARINDS\tTRANSCRIPT" in capsys.readouterr().out


def test_failed_initial_span_and_bounded_catchup_survive_later_days(
    lane: Lane,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Failures do not move the initial start, and a long outage cannot create an unbounded run."""
    lane.status["ANNOUNCEMENTS_LISTING"] = TimeoutError()
    for _ in range(3):
        assert lane.run() == 4
        sent = [r for r in lane.sent if r.surface == "ANNOUNCEMENTS_LISTING"][-1]
        assert parse_qs(urlsplit(sent.url).query)["from_date"] == ["24-10-2026"]
        lane.at += timedelta(days=1)
    lane.status.pop("ANNOUNCEMENTS_LISTING")
    assert lane.run() == 0
    lane.at += timedelta(days=400)
    lane.sent.clear()
    assert lane.run() == 4
    assert len([r for r in lane.sent if r.surface == "ANNOUNCEMENTS_LISTING"]) == 12
    assert "UNCOVERED\tAPARINDS" in capsys.readouterr().out


@pytest.mark.parametrize("method", ["record_listing", "record_attempt"])
def test_crash_rolls_back_registration_and_restart_recovers_document_without_network(
    lane: Lane,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    """Publishing a body before commit must neither advance state nor lose its fetch instant."""
    from fundamentals.pg.document_intake import DocumentIntake

    original = getattr(DocumentIntake, method)

    def crash(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("injected crash")

    monkeypatch.setattr(DocumentIntake, method, crash)
    with pytest.raises(RuntimeError, match="injected crash"):
        lane.run()
    if method == "record_listing":
        assert lane.counts() == (0, 0, 0)
    else:
        assert lane.counts()[1:] == (0, 0)
    monkeypatch.setattr(DocumentIntake, method, original)
    crashed = next((r for r in lane.sent if r.source_id.endswith("-documents")), None)
    lane.sent.clear()
    if method == "record_attempt":
        for surface in (
            "EQUITY_L",
            "ANNOUNCEMENTS_LISTING",
            "BOARD_MEETINGS_LISTING",
            "NSE_TRANSCRIPT",
            "NSE_PRESENTATION",
            "NSE_RESULTS",
            "NSE_CREDIT_RATING",
        ):
            lane.status[surface] = OSError()
        assert lane.run() == 4
        assert lane.counts()[2] == 1
        assert crashed is not None
        assert not any(r.url == crashed.url for r in lane.sent)
        import hashlib

        record = SnapshotStore(lane.args.snapshot_root).list_captures(
            crashed.source_id, crashed.surface, hashlib.sha256(crashed.key.encode()).hexdigest()
        )[0]
        with lane.db.runtime_pool() as pool, pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT attempted_at FROM eqos.document_attempts WHERE outcome='OK'"
                ).fetchall()[0][0]
                == record.retrieved_at
            )
    else:
        assert lane.run() == 0 and lane.counts() == (47, 4, 4)


def test_bd_failures_closed_refs_candidates_and_lock_are_reconciled(
    lane: Lane,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed lookup creates nothing; retry reconciles committed observations exactly once."""
    lane.lookup = (1, "[]")
    assert lane.run() == 5 and not lane.refs
    assert "BD_LOOKUP_FAILED" in capsys.readouterr().out
    lane.lookup = (0, "malformed")
    assert lane.run() == 5 and not lane.refs
    lane.lookup = (0, "")
    lane.create_failure = True
    assert lane.run() == 5 and not lane.refs
    lane.create_failure = False
    lane.rows.append(
        dict(
            seq_id="synthetic-candidate",
            sm_isin="INE372A01015",
            an_dt="27-Oct-2026 12:00:00",
            desc="Analysts/Institutional Investor Meet/Con. Call Updates",
            attchmntText="Issuer has informed the Exchange about Concall Transcript Submission",
            attchmntFile="https://nsearchives.nseindia.com/unresolved.pdf",
        )
    )
    assert lane.run() == 0 and len(lane.refs) == 4
    assert any(ref.startswith("docs-candidate:") for ref in lane.refs)
    assert not any(r.url.endswith("unresolved.pdf") for r in lane.sent)
    baseline = len(lane.refs)
    assert lane.run() == 0 and len(lane.refs) == baseline
    with (lane.args.lock_root / "documents.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = len(lane.sent)
        assert lane.run() == 5 and len(lane.sent) == before


def test_backfill_checks_screener_identity_never_fetches_agency_and_respects_coverage(
    lane: Lane,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Coverage is a ledger decision, and Screener is discovery rather than fetch authority."""
    lane.args = argparse.Namespace(
        documents_command="backfill",
        symbol="APARINDS",
        from_date=date(2026, 10, 24),
        to_date=date(2026, 10, 27),
        annual_reports=5,
        screener=True,
        config_root=Path("config"),
        snapshot_root=lane.args.snapshot_root,
        lock_root=lane.args.lock_root,
    )
    assert lane.run() == 0
    assert not any(
        urlsplit(r.url).hostname in {"www.careratings.com", "www.icra.in"} for r in lane.sent
    )
    lane.page = lane.page.replace(b'data-company-id="211"', b'data-company-id="212"')
    assert lane.run() == 4 and "refused screener identity" in capsys.readouterr().err
    with lane.db.owner_pool() as pool:
        decide(
            pool,
            subject_kind=SubjectKind.WATCHLIST,
            subject_id=lane.entity,
            kind=DecisionKind.REMOVE,
            ruling="synthetic test removal",
        )
    lane.sent.clear()
    assert lane.run() == 4 and not lane.sent
