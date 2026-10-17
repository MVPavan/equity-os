"""D7 Task 1 (eqos-3oq.1): the universe registry and its idempotent refresh, via the owner CLI.

One module database: the 2026-09-04 snapshot, its replay, then three later SYNTHETIC captures
(ETERNAL re-marked ZOMATO on NSE, those bytes again, the original bytes again). The identity
layers hold ETERNAL throughout; the registry only observes.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import INSTRUMENTS, capture, coverage, remark
from ledger_support import REGISTRY_TABLES
from onboarding_support import fresh_db, rows, seed
from pg_support import PgTestDatabase

from fundamentals.entity.identity_layers import latest_slice

pytestmark = [pytest.mark.pg, pytest.mark.retained]

ETERNAL_ISIN = "INE758T01015"
REGISTRY = tuple(sorted(REGISTRY_TABLES))
IDENTITY = (
    "reporting_entities",
    "securities",
    "listings",
    "identifier_relationships",
    "identity_events",
    "identity_event_edges",
)
# The aid's census of the snapshot: company equity by segment and ISIN.
LISTINGS, NSE, BSE = 7845, 3132, 4713
SPOT = {
    ("NSE_EQ", "INE758T01015"): ("ETERNAL", "5097", "ETERNAL LIMITED"),
    ("BSE_EQ", "INE758T01015"): ("ETERNAL", "543320", "Eternal Limited"),
    ("NSE_EQ", "INE280A01028"): ("TITAN", "3506", "TITAN COMPANY LIMITED"),
    ("BSE_EQ", "INE455K01017"): ("POLYCAB", "542652", "Polycab India Limited"),
}


def _state(db: PgTestDatabase) -> dict[str, Any]:
    """Row counts of the registry and capture tables, and the identity layers verbatim."""
    counts = {
        table: rows(db, f"SELECT count(*) FROM eqos.{table}")[0][0]
        for table in (*REGISTRY, "capture_refs")
    }
    identity = {table: rows(db, f"SELECT * FROM eqos.{table} ORDER BY id") for table in IDENTITY}
    with db.runtime_pool() as pool, pool.connection() as conn:
        held = latest_slice(conn)
    return {"counts": counts, "identity": identity, "slice": held}


def _current(db: PgTestDatabase, segment: str, isin: str) -> str:
    """The listing's current symbol in the registry view."""
    query = "SELECT trading_symbol FROM eqos.registry_view WHERE segment = %s AND isin = %s"
    return str(rows(db, query, segment, isin)[0][0])


@pytest.fixture(scope="module")
def history(pg_template: PgTestDatabase, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """Run every load through the CLI once; keep each output and the state after it."""
    root = tmp_path_factory.mktemp("coverage")
    snapshots = str(root / "snapshots")
    original = INSTRUMENTS.read_bytes()
    remarked = remark(original, "NSE_EQ", "ETERNAL", "ZOMATO")
    later = [datetime(2026, 10, day, 6, 0, tzinfo=UTC) for day in (1, 2, 3)]
    steps = {
        "first": INSTRUMENTS,
        "replay": INSTRUMENTS,
        "zomato": capture(root / "zomato", remarked, later[0]),
        "zomato_again": capture(root / "zomato-again", remarked, later[1]),
        "restored": capture(root / "restored", original, later[2]),
    }
    with fresh_db(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        seed(db, "ETERNAL", ETERNAL_ISIN, "ETERNAL", "543320")
        before = _state(db)
        done: dict[str, Any] = {}
        for step, path in steps.items():
            code, out = coverage(
                "registry", "--instruments", str(path), "--snapshot-root", snapshots
            )
            assert code == 0, step
            files = sorted(p for p in Path(snapshots).rglob("*") if p.is_file())
            current = _current(db, "NSE_EQ", ETERNAL_ISIN)
            done[step] = {"out": out, "state": _state(db), "files": files, "current": current}
        yield db, before, done


def test_snapshot_gives_the_census_and_spot_rows(history: Any) -> None:
    """The first load registers every company-equity listing once, all LISTED, no events."""
    db, _, done = history
    assert done["first"]["out"] | {"load": "-"} == {
        "load": "-",
        "created": "True",
        "new_listings": str(LISTINGS),
        "candidate_events": "0",
    }
    by_segment = dict(rows(db, "SELECT segment, count(*) FROM eqos.registry_listings GROUP BY 1"))
    assert by_segment == {"NSE_EQ": NSE, "BSE_EQ": BSE}
    first_counts = done["first"]["state"]["counts"]
    assert first_counts["registry_sightings"] == LISTINGS
    assert first_counts["registry_candidate_events"] == 0
    for (segment, isin), expected in SPOT.items():
        query = (
            "SELECT trading_symbol, exchange_token, name FROM eqos.registry_sightings s "
            "JOIN eqos.registry_listings l ON l.id = s.listing_id "
            "WHERE s.load_id = %s AND l.segment = %s AND l.isin = %s"
        )
        assert rows(db, query, int(done["first"]["out"]["load"]), segment, isin) == [expected]


def test_replay_returns_the_same_load_and_writes_nothing(history: Any) -> None:
    """Replaying the retained capture keeps its identity (retrieval time from its record)."""
    _, _, done = history
    first, replay = done["first"], done["replay"]
    assert replay["out"] == {
        "load": first["out"]["load"],
        "created": "False",
        "new_listings": "0",
        "candidate_events": "0",
    }
    assert replay["state"] == first["state"]
    assert replay["files"] == first["files"]


def test_symbol_change_is_a_candidate_event_and_the_current_attribute(history: Any) -> None:
    """ETERNAL -> ZOMATO: one event; the same bytes again: none; the original again: one."""
    db, _, done = history
    outs = [done[step]["out"] for step in ("zomato", "zomato_again", "restored")]
    assert [(o["created"], o["new_listings"], o["candidate_events"]) for o in outs] == [
        ("True", "0", "1"),
        ("True", "0", "0"),
        ("True", "0", "1"),
    ]
    assert [done[step]["current"] for step in ("first", "zomato", "zomato_again", "restored")] == [
        "ETERNAL",
        "ZOMATO",
        "ZOMATO",
        "ETERNAL",
    ]
    events = rows(
        db,
        "SELECT l.segment, l.isin, e.previous_symbol, e.observed_symbol "
        "FROM eqos.registry_candidate_events e "
        "JOIN eqos.registry_listings l ON l.id = e.listing_id "
        "ORDER BY e.id",
    )
    assert events == [
        ("NSE_EQ", ETERNAL_ISIN, "ETERNAL", "ZOMATO"),
        ("NSE_EQ", ETERNAL_ISIN, "ZOMATO", "ETERNAL"),
    ]
    assert _current(db, "BSE_EQ", ETERNAL_ISIN) == "ETERNAL"
    shas = rows(db, "SELECT content_sha256 FROM eqos.registry_loads ORDER BY id")
    assert shas[0] == shas[3] != shas[1] == shas[2]
    statuses = rows(db, "SELECT status, count(*) FROM eqos.registry_view GROUP BY 1")
    assert statuses == [("LISTED", LISTINGS)]


def test_identity_layers_never_change(history: Any) -> None:
    """The registry observes; identity events, relationships, base rows and the slice stay."""
    _, before, done = history
    assert before["identity"]["reporting_entities"]
    assert {held.value for held in before["slice"]} == {ETERNAL_ISIN, "ETERNAL", "543320"}
    for step in done.values():
        assert step["state"]["identity"] == before["identity"]
        assert step["state"]["slice"] == before["slice"]


@pytest.mark.parametrize("table", REGISTRY)
def test_runtime_role_cannot_insert(history: Any, table: str) -> None:
    """Only the owner role writes coverage."""
    db, _, _ = history
    with (
        db.runtime_pool() as pool,
        pool.connection() as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(f"INSERT INTO eqos.{table} DEFAULT VALUES")  # type: ignore[arg-type]
