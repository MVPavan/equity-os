"""D7 Task 2 (eqos-3oq.2): screens, screen runs and capture batches, via the owner CLI.

One module database: the 2026-09-04 instrument snapshot, a screen run over the five-company
``SYNTHETIC-FORMAT`` export, and one batch over ETERNAL, POLYCAB and TITAN from pinned copies of
their retained generations. THERMAX and CGPOWER are screened but never chosen, so they must have
nothing. No socket opens throughout; the coverage package schedules nothing.
"""

from __future__ import annotations

import ast
import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import (
    INSTRUMENTS,
    SCREEN_CSV,
    SCREEN_HEADER,
    capture,
    coverage,
    pinned_copies,
    remark,
)
from onboarding_support import count, fresh_db, rows

from fundamentals.api import cli
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.contracts.onboarding import OnboardingOutcome
from fundamentals.coverage import screens

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
    "fundamentals.ingest.screener_screen",
}
BATCH_TABLES = ("capture_batches", "batch_member_results", "batch_completions")
_RESULTS = (
    "SELECT m.nse_code, r.outcome, r.entity_id, r.onboarding_record_id, r.run_id "
    "FROM eqos.batch_member_results r JOIN eqos.screen_members m ON m.id = r.member_id "
    "WHERE r.batch_id = %s ORDER BY m.nse_code"
)


def _csv(path: Path, *lines: str) -> Path:
    """A SYNTHETIC-FORMAT export under ``tmp_path``."""
    path.write_text("\n".join((SCREEN_HEADER, *lines)) + "\n")
    return path


@pytest.fixture(scope="module")
def world(pg_template: Any, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """Registry, screen run and the three-member batch, every step through the owner CLI."""
    root = tmp_path_factory.mktemp("batch")
    screen = root / "screen.txt"
    screen.write_text("SYNTHETIC screen: Market Capitalization > 20000")
    export = root / SCREEN_CSV.name
    export.write_bytes(SCREEN_CSV.read_bytes())
    raw = pinned_copies(root / "raw", (*CHOSEN, *OTHERS))
    connects: list[Any] = []

    def refuse(*args: Any) -> None:
        connects.append(args)
        raise OSError("socket guard")

    with fresh_db(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", refuse)
        snaps = str(root / "snapshots")
        registry, _ = coverage(
            "registry", "--instruments", str(INSTRUMENTS), "--snapshot-root", snaps
        )
        assert registry == 0
        common = ("--snapshot-root", snaps)
        code, screened = coverage(
            "screen-run", "--screen", str(screen), "--csv", str(export), *common
        )
        assert code == 0
        members = ",".join(CHOSEN)
        run = screened["screen_run"]
        code, batched = coverage(
            "batch", "--screen-run", run, "--members", members, "--raw-root", str(raw), *common
        )
        assert code == 0, batched
        yield {
            "db": db,
            "root": root,
            "snaps": snaps,
            "screen": screen,
            "screened": screened,
            "batched": batched,
            "connects": connects,
        }


def _listing(db: Any, segment: str, isin: str) -> int:
    """The registry listing id of (segment, ISIN)."""
    query = "SELECT id FROM eqos.registry_listings WHERE segment = %s AND isin = %s"
    return int(rows(db, query, segment, isin)[0][0])


def test_five_members_resolve_to_their_nse_listings(world: Any) -> None:
    """Every row of the export resolves to its company's NSE listing; the CSV is a capture."""
    db, screened = world["db"], world["screened"]
    run = int(screened["screen_run"])
    resolved = rows(
        db,
        "SELECT m.nse_code, l.segment, l.isin, m.reason FROM eqos.screen_members m "
        "JOIN eqos.registry_listings l ON l.id = m.listing_id WHERE m.screen_run_id = %s",
        run,
    )
    assert sorted(resolved) == sorted((sym, "NSE_EQ", isin, None) for sym, isin in ISINS.items())
    surface = rows(
        db,
        "SELECT c.source_id, c.surface FROM eqos.screen_runs r "
        "JOIN eqos.capture_refs c ON c.id = r.capture_ref_id WHERE r.id = %s",
        run,
    )
    assert surface == [("screener-subscriber", "SCREEN_EXPORT")]


def test_unresolved_rows_are_refused_before_any_batch_write(world: Any) -> None:
    """TITAN's NSE code with POLYCAB's BSE code conflicts; an unknown NSE code never falls back
    to BSE; a BSE-only row resolves but has no NSE listing. A batch over any is refused."""
    db, root = world["db"], world["root"]
    export = _csv(
        root / "conflicting.csv",
        "Mixed Ltd,542652,TITAN",
        "Unknown Ltd,500411,NOSUCHCODE",
        "Thermax Ltd,500411,",
    )
    snaps = ("--snapshot-root", world["snaps"])
    code, out = coverage(
        "screen-run", "--screen", str(world["screen"]), "--csv", str(export), *snaps
    )
    assert code == 0
    assert [out[name] for name in ("Mixed Ltd", "Unknown Ltd", "Thermax Ltd")] == [
        "CONFLICTING_CODES",
        "UNKNOWN_NSE_CODE",
        str(_listing(db, "BSE_EQ", ISINS["THERMAX"])),
    ]
    before = [count(db, table) for table in BATCH_TABLES]
    for member in ("TITAN", "THERMAX"):
        refused, _ = coverage(
            "batch", "--screen-run", out["screen_run"], "--members", member,
            "--raw-root", str(world["root"] / "raw"), *snaps,
        )  # fmt: skip
        assert refused == EXIT_REFUSED
    assert [count(db, table) for table in BATCH_TABLES] == before


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
        again = screens.declare_batch(pool, int(world["screened"]["screen_run"]), ["ETERNAL"])
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
        "batch", "--screen-run", world["screened"]["screen_run"], "--members", "ETERNAL,POLYCAB",
        "--raw-root", str(raw), "--snapshot-root", world["snaps"],
    )  # fmt: skip
    assert code == EXIT_REFUSED
    batch = int(out["batch"])
    assert [row[:2] for row in rows(db, _RESULTS, batch)] == [("ETERNAL", "PARTIAL")]
    assert rows(db, "SELECT id FROM eqos.batch_completions WHERE batch_id = %s", batch) == []


def test_legacy_screener_screen_refuses_before_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``fundamentals screener-screen`` refuses at dispatch: no credential read, no request."""

    def credentials() -> None:
        raise AssertionError("credentials were read")

    monkeypatch.setattr(cli, "_screener_credentials_from_env", credentials)
    assert cli.main(["screener-screen", "--query", "Market Capitalization > 1"]) == EXIT_REFUSED
    assert "coverage screen-run" in capsys.readouterr().err


def test_no_socket_opens_and_nothing_is_scheduled(world: Any) -> None:
    """The guard saw no connection; the coverage package imports no scheduler, thread, event
    loop, subprocess or the legacy screen acquisition."""
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
    """After a registry load re-marks ETERNAL as ZOMATO (SYNTHETIC), a row coded ZOMATO resolves
    to ETERNAL's listing by current sighting; the former code no longer resolves."""
    db, root = world["db"], world["root"]
    remarked = remark(INSTRUMENTS.read_bytes(), "NSE_EQ", "ETERNAL", "ZOMATO")
    later = capture(root / "zomato", remarked, datetime(2026, 10, 1, 6, 0, tzinfo=UTC))
    snaps = ("--snapshot-root", world["snaps"])
    assert coverage("registry", "--instruments", str(later), *snaps)[0] == 0
    export = _csv(root / "renamed.csv", "Eternal Ltd,543320,ZOMATO", "Former Ltd,,ETERNAL")
    code, out = coverage(
        "screen-run", "--screen", str(world["screen"]), "--csv", str(export), *snaps
    )
    assert code == 0
    assert (out["Eternal Ltd"], out["Former Ltd"]) == (
        str(_listing(db, "NSE_EQ", ISINS["ETERNAL"])),
        "UNKNOWN_NSE_CODE",
    )
