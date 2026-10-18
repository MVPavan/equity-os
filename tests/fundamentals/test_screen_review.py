"""D7-screen-export Task 5: review items, other-vendor reads, dispositions and holds (plan S5).

Why: a member found on one side only, or unresolved, must surface to the owner with its evidence
held until disposed, and the cross-vendor values beside it must be the vendors' own retained text,
read only for verified watchlist stocks. One module database: the 2026-09-04 registry and two
``coverage export`` runs over SYNTHETIC responses where TITAN is Screener-only, HFCL and RELIANCE
are Tijori-only and one Tijori row has no NSE symbol but TITAN's BSE code. No socket opens.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import INSTRUMENTS, coverage
from onboarding_support import fresh_db, rows
from retention_support import later
from screen_export_support import HTML_TYPE, RESULTS_PATH, default_replies, fixture, serve

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.retention import EligibilityKind, EligibleReason, HoldRoot
from fundamentals.coverage import screen_review
from fundamentals.coverage.screen_review import FIELD_NOT_EXPOSED, READ_NOT_RECORDED
from fundamentals.ingest import screen_export
from fundamentals.ingest.tijori_overview_models import TijoriCompanyDetailsSection
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.pg.settings import PgRole
from fundamentals.retention.eligibility import eligibility
from fundamentals.retention.holds import capture_facts

pytestmark = [pytest.mark.pg, pytest.mark.retained]

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = Path(__file__).parents[2] / "config" / "screens.yaml"
COOKIES = {"SCREENER_SESSION_COOKIE": "screener-cookie", "TIJORI_SESSION_COOKIE": "tijori-cookie"}
OVERVIEW_PATH = "/company/titan-company-limited/"  # TITAN's verified Tijori slug
HFCL_PAGE_PATH = "/company/HFCL/consolidated/"
MCAP = "<span>latest</span>Mcap<span>Cr</span>"
OVERVIEW = (FIXTURES / "synthetic_tijori_overview.html").read_bytes()  # TITAN, Tijori id 81
WRONG_PAGE = (FIXTURES / "synthetic_screener_company.html").read_bytes()  # not HFCL's company id
_TIJORI_ROWS = [
    {"name": "Hfcl", "slug": "hfcl", "scripcode": 0, "nse symbol": "HFCL", MCAP: 20006.0},
    {"name": "Reliance", "slug": "reliance", "scripcode": 0, "nse symbol": "RELIANCE"},
    {"name": "Titan Unlisted", "slug": "", "scripcode": 500114, "nse symbol": ""},
]
_ITEMS = "SELECT member_id, status FROM eqos.screen_review_items WHERE pair_id = %s"
_READS = (
    "SELECT m.nse_code, c.source_id, c.surface, o.gap FROM eqos.screen_other_vendor_reads o "
    "JOIN eqos.screen_members m ON m.id = o.member_id "
    "LEFT JOIN eqos.capture_refs c ON c.id = o.capture_ref_id WHERE o.pair_id = %s"
)
_PAIR_CAPTURES = (
    "SELECT c FROM eqos.screen_run_pairs p JOIN eqos.screen_runs r "
    "ON r.id IN (p.screener_run_id, p.tijori_run_id), "
    "LATERAL (VALUES (r.definition_capture_ref_id), (r.capture_ref_id)) v(c) WHERE p.id = %s "
    "UNION SELECT capture_ref_id FROM eqos.screen_other_vendor_reads "
    "WHERE pair_id = %s AND capture_ref_id IS NOT NULL"
)


def _replies() -> Any:
    """One export where TITAN is Screener-only and Tijori adds three rows of its own."""
    results = json.loads(fixture("tijori-results.json"))
    results["data"] = [r for r in results["data"] if r["nse symbol"] != "TITAN"] + _TIJORI_ROWS
    results["total_results"] = len(results["data"])
    json_type = {"Content-Type": "application/json"}
    return default_replies() | {
        ("GET", RESULTS_PATH): [(200, json.dumps(results).encode(), json_type)],
        ("GET", OVERVIEW_PATH): [(200, OVERVIEW, HTML_TYPE)],
        ("GET", HFCL_PAGE_PATH): [(200, WRONG_PAGE, HTML_TYPE)],
    }


def _cli(*args: str) -> tuple[int, list[list[str]]]:
    """``main(["coverage", …])`` and its stdout's tab-separated fields per line."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["coverage", *args])
    return code, [line.split("\t") for line in out.getvalue().splitlines()]


def _served(*args: str) -> tuple[int, list[list[str]], list[str]]:
    """``_cli(*args)`` over :func:`_replies`, unpaced; its exit, output and the paths requested."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(screen_export, "SPACING_SECONDS", 0.0)
        web = serve(patch, _replies())
        code, lines = _cli(*args)
    return code, lines, [url.split("/", 3)[3] for _, url, _ in web.requests]


def _export(snaps: str) -> tuple[list[list[str]], list[str]]:
    """One ``coverage export`` over :func:`_replies`; its output and the paths requested."""
    args = ("export", "--screen", "d7-stage4", "--screens", str(CONFIG), "--snapshot-root", snaps)
    code, lines, requested = _served(*args)
    assert code == EXIT_OK, lines
    return lines, requested


@pytest.fixture(scope="module")
def world(pg_template: Any, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """Registry and two identical exports, each through the owner CLI behind a socket guard."""
    snaps = str(tmp_path_factory.mktemp("review") / "snapshots")

    def refuse(*args: Any) -> None:
        raise OSError("socket guard")

    with fresh_db(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in (db.cli_env() | COOKIES).items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", refuse)
        assert (
            coverage("registry", "--instruments", str(INSTRUMENTS), "--snapshot-root", snaps)[0]
            == 0
        )
        first, second = _export(snaps), _export(snaps)
        yield {"db": db, "snaps": snaps, "first": first, "second": second}


def _pair(lines: list[list[str]]) -> int:
    return int(next(line[1] for line in lines if line[0] == "pair"))


def _member(db: Any, pair: int, vendor: str, nse: str) -> int:
    """The member id of ``nse`` (or blank) in the pair's ``vendor`` run."""
    query = (
        "SELECT m.id FROM eqos.screen_run_pairs p JOIN eqos.screen_runs r "
        "ON r.id IN (p.screener_run_id, p.tijori_run_id) AND r.vendor = %s "
        "JOIN eqos.screen_members m ON m.screen_run_id = r.id "
        "WHERE p.id = %s AND coalesce(m.nse_code, '') = %s"
    )
    return int(rows(db, query, vendor, pair, nse)[0][0])


def _verdicts(db: Any, pair: int) -> list[Any]:
    """The eligibility, a year and a month on, of every capture the pair holds, as purge sees it."""
    with db.role_pool(PgRole.PURGE) as pool, pool.connection() as conn:
        held = {c for (c,) in conn.execute(_PAIR_CAPTURES, (pair, pair))}
        facts = [f for f in capture_facts(conn, {}) if f.capture_ref_id in held]
    assert len(facts) == len(held) == 4  # Screener page and CSV, Tijori results, one overview read
    return [eligibility(fact, later()) for fact in facts]


def test_items_reads_and_values_side_by_side(world: Any) -> None:
    """Exactly S5's items; reads only for verified watchlist stocks, gated by identity; each
    member's values are its retained row verbatim beside the other vendor's own text."""
    db, (lines, requested) = world["db"], world["first"]
    pair = _pair(lines)
    titan, unlisted = _member(db, pair, "SCREENER", "TITAN"), _member(db, pair, "TIJORI", "")
    hfcl, reliance = _member(db, pair, "TIJORI", "HFCL"), _member(db, pair, "TIJORI", "RELIANCE")
    assert sorted(rows(db, _ITEMS, pair)) == sorted(
        [(titan, "NOT_PROVEN"), (unlisted, "UNRESOLVED"), (hfcl, "ABSENT"), (reliance, "ABSENT")]
    )
    items = {int(line[1]): line[2:] for line in lines if line[0] == "item"}
    assert items[titan] == ["SCREENER", "NOT_PROVEN", "", str(unlisted)]
    assert items[unlisted] == ["TIJORI", "UNRESOLVED", "NO_CODE", ""]
    assert sorted(rows(db, _READS, pair), key=str) == sorted(
        [
            ("TITAN", "tijori", "overview", None),
            ("HFCL", None, None, "READ_REFUSED"),
            ("RELIANCE", None, None, "NOT_VERIFIED"),
            (None, None, None, "MEMBER_UNRESOLVED"),
        ],
        key=str,
    )
    # One overview and one company page after the three export requests; none for RELIANCE.
    assert requested[3:] == [OVERVIEW_PATH.lstrip("/"), HFCL_PAGE_PATH.lstrip("/")]
    shown = [line[1:] for line in lines if line[0] == "value"]
    values = {(int(m), column): (own, other) for m, column, own, other in shown}
    (titan_row,) = [
        r
        for r in csv.DictReader(io.StringIO(fixture("screener.csv").decode()))
        if r["NSE Code"] == "TITAN"
    ]
    assert {column: own for (m, column), (own, _) in values.items() if m == titan} == titan_row
    sections = TijoriSource.parse_overview_bytes(
        OVERVIEW, slug="titan-company-limited", expected_symbol="TITAN", expected_company_id=81
    )
    (details,) = [s for s in sections if isinstance(s, TijoriCompanyDetailsSection)]
    assert values[titan, "Market Capitalization"][1] == details.market_cap.raw_text != ""
    assert values[titan, "Price to Earning"][1] == details.price_earnings.raw_text != ""
    assert values[titan, "Name"][1] == values[titan, "EPS"][1] == FIELD_NOT_EXPOSED
    assert values[hfcl, MCAP] == ("20006.0", "READ_REFUSED")
    assert values[reliance, "name"] == ("Reliance", "NOT_VERIFIED")
    assert values[unlisted, "scripcode"] == ("500114", "MEMBER_UNRESOLVED")
    code, reviewed = _cli("review", "--pair", str(pair), "--snapshot-root", world["snaps"])
    assert code == EXIT_OK
    assert reviewed == [line for line in lines if line[0] in ("item", "value")]


def test_dispositions_clear_items_and_release_their_holds(world: Any) -> None:
    """Pending items hold every pair capture past the vendor window; each item takes one owner
    disposition with a reason and evidence; once all are disposed the window applies."""
    db = world["db"]
    pair, other = _pair(world["first"][0]), _pair(world["second"][0])
    held = _verdicts(db, pair)
    assert {(v.kind, v.held_by) for v in held} == {
        (EligibilityKind.HELD, frozenset({HoldRoot.OPEN_SCREEN_REVIEW}))
    }
    items = [int(m) for m, _ in rows(db, _ITEMS, pair)]
    dispose = ("dispose", "--pair", str(pair), "--kind", "DISMISSED", "--evidence", "probe:1")
    refused = [
        (*dispose, "--member", str(items[0]), "--reason", ""),
        (*dispose, "--member", str(_member(db, other, "TIJORI", "")), "--reason", "foreign"),
        (*dispose, "--member", str(_member(db, pair, "SCREENER", "ETERNAL")), "--reason", "both"),
    ]
    assert [_cli(*args)[0] for args in refused] == [EXIT_REFUSED] * 3
    with db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO eqos.screen_member_dispositions (pair_id, member_id, kind, reason, "
                "evidence_ref) VALUES (%s, %s, 'DISMISSED', 'r', 'e')",
                (pair, items[0]),
            )
    for member in items:
        assert _cli(*dispose, "--member", str(member), "--reason", "boundary")[0] == EXIT_OK
    assert _cli(*dispose, "--member", str(items[0]), "--reason", "again")[0] == EXIT_REFUSED
    assert _cli("review", "--pair", str(pair), "--snapshot-root", world["snaps"]) == (EXIT_OK, [])
    assert {(v.kind, v.reason) for v in _verdicts(db, pair)} == {
        (EligibilityKind.ELIGIBLE, EligibleReason.WINDOW)
    }


def test_an_interrupted_read_step_shows_its_pair_and_completes(world: Any) -> None:
    """Reads interrupted after the first: the committed pair was printed already; its review
    shows every member, the unread ones ``READ_NOT_RECORDED``; ``review --read`` requests only
    those, after which the review shows what an uninterrupted export does."""
    snaps, real = world["snaps"], screen_review.record_read
    recorded: list[object] = []

    def interrupted(*args: Any) -> None:
        if recorded:
            raise RuntimeError("interrupted")
        recorded.append(real(*args))

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(screen_review, "record_read", interrupted)
        args = ("export", "--screen", "d7-stage4", "--screens", str(CONFIG))
        code, lines, _ = _served(*args, "--snapshot-root", snaps)
    assert code == EXIT_REFUSED
    review = ("review", "--pair", str(_pair(lines)), "--snapshot-root", snaps)
    code, partial = _cli(*review)
    assert code == EXIT_OK
    unread = {line[1] for line in partial if line[0] == "value" and line[4] == READ_NOT_RECORDED}
    items = {line[1] for line in partial if line[0] == "item"}
    assert len(items) == 4 and len(unread) == 3 and unread < items
    code, completed, requested = _served(*review, "--read")
    assert code == EXIT_OK and requested == [HFCL_PAGE_PATH.lstrip("/")]
    shown = sorted(line[2:] for line in completed if line[0] == "value")
    assert shown == sorted(line[2:] for line in world["first"][0] if line[0] == "value")
    assert _served(*review, "--read")[2] == []


def test_licence_end_wins_over_an_open_review(world: Any) -> None:
    """A vendor's licence end makes its captures eligible even while the review is open."""
    db = world["db"]
    pair = _pair(world["second"][0])
    with db.owner_pool() as pool, pool.connection() as conn:
        conn.execute("INSERT INTO eqos.licence_ends (source_id) VALUES ('tijori')")
    verdicts = _verdicts(db, pair)
    assert {v.reason for v in verdicts if v.kind is EligibilityKind.ELIGIBLE} == {
        EligibleReason.LICENCE_END
    }
    assert {v.held_by for v in verdicts if v.kind is EligibilityKind.HELD} == {
        frozenset({HoldRoot.OPEN_SCREEN_REVIEW})
    }


def test_a_review_refuses_an_expired_read(world: Any) -> None:
    """The review reads captures through the retention-aware reader: once the pair's overview
    read is EXPIRED, printing its values refuses instead of reading purged bytes. Last: it
    expires a capture the other tests count."""
    db, pair = world["db"], _pair(world["second"][0])
    query = (
        "SELECT capture_ref_id FROM eqos.screen_other_vendor_reads "
        "WHERE pair_id = %s AND capture_ref_id IS NOT NULL"
    )
    ((read,),) = rows(db, query, pair)
    review = ("review", "--pair", str(pair), "--snapshot-root", world["snaps"])
    assert _cli(*review)[0] == EXIT_OK
    with db.migrator_connection() as conn:
        conn.execute("INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, %s)",
                     (read, "EXPIRED"))  # fmt: skip
    assert _cli(*review)[0] == EXIT_REFUSED
