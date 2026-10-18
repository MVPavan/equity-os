"""D7 Task 2 (eqos-3oq.2) and D7-screen-export Task 4: screens, paired screen runs and capture
batches, via the owner CLI.

One module database: the 2026-09-04 instrument snapshot, ``coverage export`` over the recorded
SYNTHETIC five-company responses of both vendors (``screen_export_support``), and one batch over
ETERNAL, POLYCAB and TITAN from pinned copies of their retained generations. THERMAX and CGPOWER
are screened but never chosen, so they must have nothing. No socket opens throughout; the
coverage package schedules nothing.
"""

from __future__ import annotations

import ast
import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import INSTRUMENTS, capture, coverage, pinned_copies, remark
from onboarding_support import count, fresh_db, rows
from pydantic import SecretStr
from screen_export_support import RESULTS_PATH, default_replies, serve

from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.contracts.onboarding import OnboardingOutcome
from fundamentals.coverage import screens
from fundamentals.ingest import screen_export
from fundamentals.ingest.screen_export import VendorExport
from fundamentals.ingest.screener_session_models import ScreenerCredentials
from fundamentals.ingest.tijori_source import TijoriCredentials
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CHOSEN = ("ETERNAL", "POLYCAB", "TITAN")
OTHERS = ("THERMAX", "CGPOWER")
ISINS = {
    "ETERNAL": "INE758T01015",
    "POLYCAB": "INE455K01017",
    "TITAN": "INE280A01028",
    "THERMAX": "INE152A01029",
    "CGPOWER": "INE067A01029",
}
FORBIDDEN_IMPORTS = {
    "sched",
    "threading",
    "asyncio",
    "subprocess",
}
BATCH_TABLES = ("capture_batches", "batch_member_results", "batch_completions")
_RESULTS = (
    "SELECT m.nse_code, r.outcome, r.entity_id, r.onboarding_record_id, r.run_id "
    "FROM eqos.batch_member_results r JOIN eqos.screen_members m ON m.id = r.member_id "
    "WHERE r.batch_id = %s ORDER BY m.nse_code"
)


CONFIG = Path(__file__).parents[2] / "config" / "screens.yaml"
COOKIES = {"SCREENER_SESSION_COOKIE": "screener-cookie", "TIJORI_SESSION_COOKIE": "tijori-cookie"}
RUN_TABLES = ("screens", "screen_runs", "screen_members", "screen_run_pairs", "capture_refs")
_RUN_CAPTURES = (
    "SELECT d.source_id, d.surface, c.source_id, c.surface FROM eqos.screen_runs r "
    "JOIN eqos.capture_refs c ON c.id = r.capture_ref_id "
    "JOIN eqos.capture_refs d ON d.id = r.definition_capture_ref_id WHERE r.id = %s"
)
_BSE_ONLY = (
    "SELECT isin, exchange_token, listing_id FROM eqos.registry_view b "
    "WHERE status = 'LISTED' AND segment = 'BSE_EQ' AND NOT EXISTS (SELECT 1 FROM "
    "eqos.registry_view n WHERE n.isin = b.isin AND n.segment = 'NSE_EQ' AND n.status = 'LISTED') "
    "ORDER BY isin LIMIT 1"
)


def _export(snaps: str, replies: Any = None) -> tuple[int, dict[str, str]]:
    """``coverage export`` of the configured screen over recorded responses."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(screen_export, "SPACING_SECONDS", 0.0)
        serve(patch, replies)
        return coverage(
            "export", "--screen", "d7-stage4", "--screens", str(CONFIG), "--snapshot-root", snaps
        )


@cache
def _recorded() -> tuple[VendorExport, VendorExport]:
    """Both vendors' exports of the recorded responses."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(screen_export, "SPACING_SECONDS", 0.0)
        serve(patch)
        screener, tijori = screen_export.screen_sources(
            ScreenerCredentials(session_cookie=SecretStr("c")),
            TijoriCredentials(session_cookie=SecretStr("c")),
        )
        return (
            screen_export.export_screener(screener, "d7-stage4"),
            screen_export.export_tijori(tijori, "d7-stage4"),
        )


def _record(
    world: Any, screener: tuple[dict[str, str], ...] = (), tijori: tuple[dict[str, str], ...] = ()
) -> screens.ExportResult:
    """Record one export as the owner: the recorded responses, with ``screener`` / ``tijori``
    rows instead of the fixture rows when given."""
    exports = [
        export.model_copy(update={"rows": replaced}) if replaced else export
        for export, replaced in zip(_recorded(), (screener, tijori), strict=True)
    ]
    with world["db"].owner_pool() as pool:
        return screens.record_screen_run(pool, *exports, SnapshotStore(Path(world["snaps"])))


def _screener_row(name: str, isin: str, nse: str = "", bse: str = "") -> dict[str, str]:
    return {"Name": name, "ISIN Code": isin, "NSE Code": nse, "BSE Code": bse}


def _tijori_row(name: str, nse: str, scripcode: str = "0", slug: str = "") -> dict[str, str]:
    return {"name": name, "nse symbol": nse, "scripcode": scripcode, "slug": slug}


def _bound(run: screens.ScreenRun) -> list[int | str | None]:
    """Each member's listing id, or its reason."""
    return [member.listing_id or member.reason for member in run.members]


@pytest.fixture(scope="module")
def world(pg_template: Any, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """Registry, one paired export and the three-member batch, every step through the owner
    CLI."""
    root = tmp_path_factory.mktemp("batch")
    raw = pinned_copies(root / "raw", (*CHOSEN, *OTHERS))
    connects: list[Any] = []

    def refuse(*args: Any) -> None:
        connects.append(args)
        raise OSError("socket guard")

    with fresh_db(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in (db.cli_env() | COOKIES).items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", refuse)
        snaps = str(root / "snapshots")
        registry, _ = coverage(
            "registry", "--instruments", str(INSTRUMENTS), "--snapshot-root", snaps
        )
        assert registry == 0
        code, screened = _export(snaps)
        assert code == 0, screened
        members = ",".join(CHOSEN)
        run = screened["screener_run"]
        code, batched = coverage(
            "batch", "--screen-run", run, "--members", members, "--raw-root", str(raw),
            "--snapshot-root", snaps,
        )  # fmt: skip
        assert code == 0, batched
        yield {
            "db": db,
            "root": root,
            "snaps": snaps,
            "screened": screened,
            "batched": batched,
            "connects": connects,
        }


def _listing(db: Any, segment: str, isin: str) -> int:
    """The registry listing id of (segment, ISIN)."""
    query = "SELECT id FROM eqos.registry_listings WHERE segment = %s AND isin = %s"
    return int(rows(db, query, segment, isin)[0][0])


def test_both_runs_bind_the_five_and_keep_every_response(world: Any) -> None:
    """Each vendor's five rows bind to their companies' NSE listings; each run's definition and
    results captures resolve to the recorded bytes; the pair links the two runs."""
    db, screened = world["db"], world["screened"]
    runs = (int(screened["screener_run"]), int(screened["tijori_run"]))
    expected = sorted((sym, "NSE_EQ", isin, None) for sym, isin in ISINS.items())
    for run in runs:
        resolved = rows(
            db,
            "SELECT m.nse_code, l.segment, l.isin, m.reason FROM eqos.screen_members m "
            "JOIN eqos.registry_listings l ON l.id = m.listing_id WHERE m.screen_run_id = %s",
            run,
        )
        assert sorted(resolved) == expected
    assert rows(db, _RUN_CAPTURES, runs[0]) == [
        ("screener-subscriber", "SCREEN_DEFINITION", "screener-subscriber", "SCREEN_EXPORT")
    ]
    assert rows(db, _RUN_CAPTURES, runs[1]) == [
        ("tijori", "screen_results", "tijori", "screen_results")
    ]
    assert rows(db, "SELECT screener_run_id, tijori_run_id FROM eqos.screen_run_pairs "
                "WHERE id = %s", int(screened["pair"])) == [runs]  # fmt: skip
    store = SnapshotStore(Path(world["snaps"]))
    refs = rows(
        db,
        "SELECT c.source_id, c.surface, c.request_key, c.capture_id FROM eqos.screen_runs r "
        "JOIN eqos.capture_refs c ON c.id IN (r.definition_capture_ref_id, r.capture_ref_id) "
        "WHERE r.id = ANY (%s) ORDER BY r.id, c.id",
        list(runs),
    )
    bodies = [store.read_capture_verified(*ref)[1] for ref in refs]
    assert bodies == [
        fetch.body for export in _recorded() for fetch in (export.definition, export.results)
    ]


def test_screener_rows_bind_by_isin_and_unresolved_rows_never_batch(world: Any) -> None:
    """A Screener row binds by ISIN to its NSE listing, else its BSE one; an unknown or blank ISIN,
    or a supplied code naming another listing, does not bind. A batch over any is refused."""
    db = world["db"]
    bse_isin, bse_code, bse_listing = rows(db, _BSE_ONLY)[0]
    done = _record(
        world,
        screener=(
            _screener_row("Unknown Ltd", "INE000000000", "TITAN"),
            _screener_row("Blank Ltd", ""),
            _screener_row("Mixed Ltd", ISINS["TITAN"], "POLYCAB"),
            _screener_row("Mixed Bse Ltd", ISINS["TITAN"], "TITAN", "542652"),
            _screener_row("Thermax Ltd", ISINS["THERMAX"]),
            _screener_row("Bse Only Ltd", bse_isin, "", bse_code),
        ),
    )
    assert _bound(done.screener) == [
        "UNKNOWN_ISIN",
        "NO_CODE",
        "CONFLICTING_CODES",
        "CONFLICTING_CODES",
        _listing(db, "NSE_EQ", ISINS["THERMAX"]),
        bse_listing,
    ]
    before = [count(db, table) for table in BATCH_TABLES]
    with pytest.raises(ValueError):
        with db.owner_pool() as pool:
            screens.declare_batch(pool, done.screener.run_id, ["TITAN"])
    assert [count(db, table) for table in BATCH_TABLES] == before


def test_tijori_rows_bind_by_unique_current_nse_symbol(world: Any) -> None:
    """A Tijori row binds by NSE symbol; a supplied scripcode naming another listing conflicts;
    a blank symbol does not bind on its scripcode alone. THERMAX has no verified Tijori slug."""
    db = world["db"]
    done = _record(
        world,
        tijori=(
            _tijori_row("Thermax", "THERMAX", "500411"),
            _tijori_row("Thermax No Scrip", "THERMAX", "0"),
            _tijori_row("Mixed", "THERMAX", "542652"),
            _tijori_row("Unknown", "NOSUCHCODE"),
            _tijori_row("Bse Only", "", "500411"),
        ),
    )
    thermax = _listing(db, "NSE_EQ", ISINS["THERMAX"])
    assert _bound(done.tijori) == [
        thermax, thermax, "CONFLICTING_CODES", "UNKNOWN_NSE_CODE", "NO_CODE",
    ]  # fmt: skip
    assert done.tijori.members[0].isin == ISINS["THERMAX"]


def test_a_verified_tijori_slug_vetoes_a_different_one(world: Any) -> None:
    """Where an onboarded entity's Tijori unit is VERIFIED, a row naming another slug does not
    bind; its verified slug does. Without one, the slug is unverified and binding passes."""
    db = world["db"]
    verified = {
        symbol: [slug for (slug,) in rows(db, screens._VERIFIED_SLUGS, ISINS[symbol])]
        for symbol in (*CHOSEN, *OTHERS)
    }
    symbol = next(symbol for symbol in CHOSEN if verified[symbol])
    assert not verified["THERMAX"]
    done = _record(
        world,
        tijori=(
            _tijori_row("Verified", symbol, slug=verified[symbol][0]),
            _tijori_row("Other slug", symbol, slug="another-company"),
            _tijori_row("Unverified", "THERMAX", slug="another-company"),
        ),
    )
    assert _bound(done.tijori) == [
        _listing(db, "NSE_EQ", ISINS[symbol]),
        "CONFLICTING_CODES",
        _listing(db, "NSE_EQ", ISINS["THERMAX"]),
    ]


def test_an_edited_definition_is_a_second_screen(world: Any) -> None:
    """The same definition text reuses its screen row; an edit under the same slug is a new one."""
    db = world["db"]
    before = count(db, "screens")
    _record(world)
    assert count(db, "screens") == before
    screener, tijori = _recorded()
    edited = screener.model_copy(update={"screen_text": screener.screen_text + " AND OPM > 10"})
    with db.owner_pool() as pool:
        screens.record_screen_run(pool, edited, tijori, SnapshotStore(Path(world["snaps"])))
    assert count(db, "screens") == before + 1


def test_a_tijori_failure_writes_nothing(world: Any) -> None:
    """A Tijori 503 refuses the export after Screener succeeded; no row and no capture is
    written."""
    db = world["db"]
    before = [count(db, table) for table in RUN_TABLES]
    replies = default_replies() | {("GET", RESULTS_PATH): [(503, b"", {})]}
    with pytest.MonkeyPatch.context() as patch:
        for name, value in (db.cli_env() | COOKIES).items():
            patch.setenv(name, value)
        code, _ = _export(world["snaps"], replies)
    assert code == EXIT_REFUSED
    assert [count(db, table) for table in RUN_TABLES] == before


def test_pairs_are_owner_written_and_link_one_run_of_each_vendor(world: Any) -> None:
    """The runtime role cannot write a pair; the owner cannot pair two Screener runs."""
    db, screened = world["db"], world["screened"]
    screener = int(screened["screener_run"])
    pair = "INSERT INTO eqos.screen_run_pairs (screener_run_id, tijori_run_id) VALUES (%s, %s)"
    with db.runtime_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(pair, (screener, int(screened["tijori_run"])))
    other = _record(world).screener.run_id
    with db.owner_pool() as pool, pool.connection() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(pair, (screener, other))


def test_batch_completes_with_three_partial_same_entity_runs(world: Any) -> None:
    """Each chosen member: PARTIAL, its own onboarding record and a same-entity INCOMPLETE run
    holding comparison rows; the batch declares exactly those three and is complete."""
    db, batched = world["db"], world["batched"]
    batch = int(batched["batch"])
    assert {symbol: batched[symbol].split()[0] for symbol in CHOSEN} == dict.fromkeys(
        CHOSEN, OnboardingOutcome.PARTIAL.value
    )
    (declared,) = rows(
        db, "SELECT cardinality(member_ids) FROM eqos.capture_batches WHERE id = %s", batch
    )
    assert declared == (3,)
    results = rows(db, _RESULTS, batch)
    assert [row[:2] for row in results] == [(symbol, "PARTIAL") for symbol in sorted(CHOSEN)]
    for symbol, _, entity, record, run in results:
        (isin,) = rows(db, "SELECT isin FROM eqos.securities WHERE entity_id = %s", entity)[0]
        assert isin == ISINS[symbol]
        assert rows(
            db, "SELECT identifier, entity_id FROM eqos.onboarding_records WHERE id = %s", record
        ) == [(symbol, entity)]
        scope = rows(
            db,
            "SELECT manifest -> 'scope' -> 'entity_ids', status FROM eqos.runs WHERE id = %s",
            run,
        )
        assert scope == [([entity], "INCOMPLETE")]
        assert rows(db, "SELECT count(*) FROM eqos.results WHERE run_id = %s", run)[0][0] > 0
    assert rows(db, "SELECT count(*) FROM eqos.batch_completions WHERE batch_id = %s", batch) == [
        (1,)
    ]


def test_the_others_have_nothing(world: Any) -> None:
    """THERMAX and CGPOWER were screened, not chosen: no onboarding record, capture input,
    entity or run."""
    db = world["db"]
    others = list(OTHERS)
    assert (
        rows(db, "SELECT id FROM eqos.onboarding_records WHERE identifier = ANY (%s)", others) == []
    )
    labels = [f"discovery:{symbol}:%" for symbol in OTHERS]
    assert rows(db, "SELECT id FROM eqos.evidence_inputs WHERE label LIKE ANY (%s)", labels) == []
    isins = [ISINS[symbol] for symbol in OTHERS]
    assert rows(db, "SELECT id FROM eqos.securities WHERE isin = ANY (%s)", isins) == []
    run_entities = rows(
        db,
        "SELECT DISTINCT s.isin FROM eqos.runs r JOIN eqos.securities s "
        "ON s.entity_id = (r.manifest -> 'scope' -> 'entity_ids' ->> 0)::bigint",
    )
    assert sorted(isin for (isin,) in run_entities) == sorted(ISINS[s] for s in CHOSEN)


def test_a_result_linking_another_entitys_run_or_record_is_refused(world: Any) -> None:
    """The database pins one entity across result, onboarding record, run and listing ISIN; a
    batch is not complete until every declared member has a result."""
    db, batch = world["db"], int(world["batched"]["batch"])
    pinned = {row[0]: row[1:] for row in rows(db, _RESULTS, batch)}
    eternal, titan = pinned["ETERNAL"], pinned["TITAN"]
    with db.owner_pool() as pool:
        again = screens.declare_batch(pool, int(world["screened"]["screener_run"]), ["ETERNAL"])
        member = again.members["ETERNAL"]

        def result(entity: int, record: int, run: int) -> None:
            screens.record_member_result(
                pool, again.batch_id, member, outcome=OnboardingOutcome.PARTIAL,
                entity_id=entity, onboarding_record_id=record, run_id=run, exit_code=4,
            )  # fmt: skip

        with pytest.raises(psycopg.errors.CheckViolation):
            screens.complete_batch(pool, again.batch_id)
        for entity, record, run in (
            (eternal[1], eternal[2], titan[3]),  # TITAN's run
            (eternal[1], titan[2], eternal[3]),  # TITAN's record
            (titan[1], titan[2], titan[3]),  # TITAN throughout, on ETERNAL's listing
        ):
            with pytest.raises(psycopg.errors.CheckViolation):
                result(entity, record, run)
        result(eternal[1], eternal[2], eternal[3])  # negative control: its own links pass
        screens.complete_batch(pool, again.batch_id)


def test_a_stopped_batch_has_no_completion(world: Any) -> None:
    """POLYCAB's generation is absent, so the batch stops after ETERNAL: one result, no
    completion."""
    db = world["db"]
    raw = pinned_copies(world["root"] / "raw-stopped", ("ETERNAL",))
    code, out = coverage(
        "batch", "--screen-run", world["screened"]["screener_run"], "--members", "ETERNAL,POLYCAB",
        "--raw-root", str(raw), "--snapshot-root", world["snaps"],
    )  # fmt: skip
    assert code == EXIT_REFUSED
    batch = int(out["batch"])
    assert [row[:2] for row in rows(db, _RESULTS, batch)] == [("ETERNAL", "PARTIAL")]
    assert rows(db, "SELECT id FROM eqos.batch_completions WHERE batch_id = %s", batch) == []


def test_no_socket_opens_and_nothing_is_scheduled(world: Any) -> None:
    """The guard saw no connection; the coverage package imports no scheduler, thread, event
    loop, subprocess."""
    assert world["connects"] == []
    package = Path(screens.__file__).parent
    for module in package.glob("*.py"):
        for node in ast.walk(ast.parse(module.read_text())):
            names = (
                [alias.name for alias in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )  # fmt: skip
            for name in names:
                assert not any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS)


def test_a_screen_naming_the_new_symbol_resolves_after_a_rename(world: Any) -> None:
    """After a registry load re-marks ETERNAL as ZOMATO (SYNTHETIC), a Tijori row coded ZOMATO
    binds to ETERNAL's listing by current sighting; the former symbol no longer binds. The
    Screener row binds by ISIN throughout."""
    db, root = world["db"], world["root"]
    ((slug,),) = rows(db, screens._VERIFIED_SLUGS, ISINS["ETERNAL"])
    remarked = remark(INSTRUMENTS.read_bytes(), "NSE_EQ", "ETERNAL", "ZOMATO")
    later = capture(root / "zomato", remarked, datetime(2026, 10, 1, 6, 0, tzinfo=UTC))
    assert (
        coverage("registry", "--instruments", str(later), "--snapshot-root", world["snaps"])[0] == 0
    )
    done = _record(
        world,
        screener=(_screener_row("Eternal Ltd", ISINS["ETERNAL"], "ZOMATO"),),
        tijori=(_tijori_row("Eternal", "ZOMATO", "543320", slug), _tijori_row("Former", "ETERNAL")),
    )
    eternal = _listing(db, "NSE_EQ", ISINS["ETERNAL"])
    assert _bound(done.screener) == [eternal]
    assert _bound(done.tijori) == [eternal, "UNKNOWN_NSE_CODE"]
