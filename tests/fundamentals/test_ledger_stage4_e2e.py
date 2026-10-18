"""D7.6: the ledger Stage 4 end-to-end (plan D7 Task 6 as amended by D7-screen-export Task 7).

One ``eqos_test_*`` database, socket guard on throughout. ``coverage registry`` loads the
2026-09-04 snapshot twice; the derived Stage 4 fixture (both vendors' responses reduced to the
five development companies, plan S6) is recorded through ``record_screen_run`` as one pair, not
re-exported, since it still states the full result counts; ``coverage batch`` onboards and
compares ETERNAL, POLYCAB and TITAN from pinned copies. Then the SYNTHETIC ETERNAL -> ZOMATO
capture loads, and the watchlist and drafting steps run through ``ledger decide`` and the runtime
role. The frozen ledger Stage 4 manifest is the only source of expected values.
"""

from __future__ import annotations

import gzip
import io
import json
import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from coverage_support import INSTRUMENTS, capture, coverage, pinned_copies, remark
from ledger_support import CONTENT_HASH, CUTOFF
from manifest_support import failure_surface
from onboarding_support import fresh_db, rows
from psycopg import errors
from test_coverage_registry import IDENTITY
from test_coverage_watchlist import _SECTION, OFF
from test_frozen_manifests import LEDGER4, REPO, load

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.ledger import ReportKind, ReportSection, VersionDraft
from fundamentals.coverage import screens
from fundamentals.entity.identity_layers import latest_slice
from fundamentals.ingest.screen_export import ScreenFetch, ScreenVendor, VendorExport
from fundamentals.ledger import store
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

MANIFEST = load(LEDGER4)
SCREEN, BATCH, REGISTRY = MANIFEST["screen"], MANIFEST["batch"], MANIFEST["registry"]
MEMBERS = {member["symbol"]: member for member in BATCH["members"]}
SOURCES = {s["label"]: REPO / s["path"] for s in MANIFEST["header"]["sources"]}
FIXTURE = {  # vendor -> (definition, results) labels of the derived fixture
    ScreenVendor.SCREENER: ("SCREENER-PAGE", "SCREENER-CSV"),
    ScreenVendor.TIJORI: ("TIJORI-JSON", "TIJORI-JSON"),
}
RETRIEVED = datetime(2026, 10, 18, tzinfo=UTC)  # SYNTHETIC: the derived fixture has no fetch time
XBRL, XBRL_SURFACE, VALUE = "xbrl", "NSE_XBRL_INSTANCE", "VALUE"
REFUSED, ACCEPTED = "REFUSED", "ACCEPTED"
_BY_ENTITY = "JOIN eqos.reporting_entities e ON e.id = "
_SCOPED = f"{_BY_ENTITY}(r.manifest -> 'scope' -> 'entity_ids' ->> 0)::bigint"
_MEMBERS = (
    "SELECT m.row_number, m.nse_code, l.segment, l.isin, m.reason, m.slug "
    "FROM eqos.screen_members m LEFT JOIN eqos.registry_listings l ON l.id = m.listing_id "
    "WHERE m.screen_run_id = %s ORDER BY m.row_number"
)
_RUN_SCREEN = (
    "SELECT s.screen_text, d.blob_sha256, c.blob_sha256 FROM eqos.screen_runs r "
    "JOIN eqos.screens s ON s.id = r.screen_id "
    "JOIN eqos.capture_refs d ON d.id = r.definition_capture_ref_id "
    "JOIN eqos.capture_refs c ON c.id = r.capture_ref_id WHERE r.id = %s"
)
_REVIEW = "SELECT pair_id, member_id FROM eqos.{} WHERE pair_id = %s"
_RESULT = (
    "SELECT r.outcome, s.isin, r.onboarding_record_id FROM eqos.batch_member_results r "
    "JOIN eqos.screen_members m ON m.id = r.member_id "
    "JOIN eqos.securities s ON s.entity_id = r.entity_id WHERE m.nse_code = %s"
)
_UNITS = (
    "SELECT unit, state, reason FROM eqos.namespace_verifications WHERE onboarding_record_id = %s"
)
_RUN = (
    f"SELECT e.entity_key, r.status, r.manifest, b.exit_code FROM eqos.runs r {_SCOPED} "
    "JOIN eqos.batch_member_results b ON b.run_id = r.id WHERE r.id = %s"
)
_PACKAGE = (
    "SELECT p.reporting_kind, array_agg(s.statement_family ORDER BY s.statement_family) "
    "FROM eqos.run_inputs i JOIN eqos.filing_packages p ON p.id = i.package_id "
    "JOIN eqos.package_statements s ON s.package_id = p.id AND s.role = 'PRESENT' "
    "WHERE i.run_id = %s AND i.input_kind = 'PACKAGE' GROUP BY 1"
)
# The captures a run's persisted inputs bind (each capture once, however reached): directly, as
# an input package's members, or as an input evidence record's captures.
_INPUTS = (
    "SELECT DISTINCT c.source_id, c.surface, c.blob_sha256, c.id FROM eqos.run_inputs i "
    "LEFT JOIN eqos.package_members m ON m.package_id = i.package_id "
    "LEFT JOIN eqos.evidence_input_captures x ON x.evidence_input_id = i.evidence_input_id "
    "JOIN eqos.capture_refs c ON c.id IN (i.capture_ref_id, m.capture_ref_id, x.capture_ref_id) "
    "WHERE i.run_id = %s ORDER BY 1, 2, 3"
)
# Every run in the database and every result of the batch, at batch completion.
_RUN_CENSUS = (
    f"SELECT r.id, e.entity_key, r.manifest -> 'scope' FROM eqos.runs r {_SCOPED} ORDER BY r.id"
)
_RESULT_CENSUS = (
    "SELECT m.nse_code, r.run_id FROM eqos.batch_member_results r "
    "JOIN eqos.screen_members m ON m.id = r.member_id WHERE r.batch_id = %s ORDER BY 1"
)
_VALUES = (
    "SELECT r.canonical_id, r.period_start, r.period_end, r.period_instant, v.source_id, "
    "v.surface, v.representation, r.value_identity, v.source_state FROM eqos.results r "
    "JOIN eqos.result_source_values v ON v.result_id = r.id "
    "WHERE r.run_id = %s AND r.dimension_set = '[]'::jsonb"
)
_OTHERS = {  # batch.others_expect field -> its row for a symbol
    "onboarding_record": "SELECT id FROM eqos.onboarding_records WHERE identifier = %s",
    "capture": "SELECT id FROM eqos.evidence_inputs WHERE label LIKE 'discovery:' || %s || ':%%'",
    "entity": "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s",
    "run": f"SELECT r.id FROM eqos.runs r {_SCOPED} WHERE e.entity_key = %s",
    "batch_result": (
        "SELECT r.id FROM eqos.batch_member_results r "
        "JOIN eqos.screen_members m ON m.id = r.member_id WHERE m.nse_code = %s"
    ),
}
_ENTITY = "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s"
_EVENTS = (
    "SELECT l.segment || '|' || l.isin, e.previous_symbol, e.observed_symbol "
    "FROM eqos.registry_candidate_events e JOIN eqos.registry_listings l ON l.id = e.listing_id"
)
_CURRENT = "SELECT trading_symbol FROM eqos.registry_view WHERE segment || '|' || isin = %s"


def exports() -> list[VendorExport]:
    """Both vendors' exports of the derived fixture (the test loader of plan Task 7)."""
    built = []
    for vendor, labels in FIXTURE.items():
        definition, results = (
            ScreenFetch(url=label, body=SOURCES[label].read_bytes(), retrieved_at=RETRIEVED)
            for label in labels
        )
        text = SCREEN["screen_text"][vendor.lower()]
        built.append(VendorExport(vendor=vendor, screen_text=text, definition=definition,
                                  results=results))  # fmt: skip
    return built


def identity(db: Any) -> dict[str, Any]:
    """The identity layers verbatim and the held latest slice."""
    held = {table: rows(db, f"SELECT * FROM eqos.{table} ORDER BY id") for table in IDENTITY}
    with db.runtime_pool() as pool, pool.connection() as conn:
        return held | {"slice": latest_slice(conn)}


@pytest.fixture(scope="module")
def world(pg_template: Any, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """Registry twice, the recorded pair and the three-member batch; the others' state at
    batch completion (``batch.others_checkpoint``)."""
    root = tmp_path_factory.mktemp("stage4")
    raw = pinned_copies(root / "raw", (*BATCH["declared"], *BATCH["others"]))
    snaps = str(root / "snapshots")
    connects: list[Any] = []

    def refuse(*args: Any) -> None:
        connects.append(args)
        raise OSError("socket guard")

    with fresh_db(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", refuse)
        loads = [
            coverage("registry", "--instruments", str(INSTRUMENTS), "--snapshot-root", snaps)
            for _ in range(2)
        ]
        with db.owner_pool() as pool:
            pair = screens.record_screen_run(pool, *exports(), SnapshotStore(Path(snaps)))
        code, batched = coverage(
            "batch", "--screen-run", str(pair.screener.run_id), "--raw-root", str(raw),
            "--members", ",".join(BATCH["declared"]), "--snapshot-root", snaps,
        )  # fmt: skip
        assert code == EXIT_OK, batched
        others = {
            symbol: {
                field: (rows(db, q, symbol) or [(None,)])[0][0] for field, q in _OTHERS.items()
            }
            for symbol in BATCH["others"]
        }
        runs = {symbol: int(batched[symbol].split()[-1]) for symbol in BATCH["declared"]}
        census = (rows(db, _RUN_CENSUS), rows(db, _RESULT_CENSUS, int(batched["batch"])))
        yield {"db": db, "root": root, "raw": raw, "snaps": snaps, "loads": loads, "pair": pair,
               "batch": int(batched["batch"]), "runs": runs, "others": others,
               "census": census, "connects": connects}  # fmt: skip


def test_the_registry_loads_once_and_replays(world: Any) -> None:
    """``registry.loads`` 1-2: the first load registers every listing, its replay nothing."""
    db, (first, replay) = world["db"], world["loads"]
    shown = [
        {"created": out["created"] == "True", "new_listings": int(out["new_listings"]),
         "candidate_events": int(out["candidate_events"])}
        for _, out in (first, replay)
    ]  # fmt: skip
    assert (first[0], replay[0]) == (EXIT_OK, EXIT_OK)
    expected = [{k: load[k] for k in shown[0]} for load in REGISTRY["loads"][:2]]
    assert shown == expected and first[1]["load"] == replay[1]["load"]
    counts = REGISTRY["counts"]
    segments = dict(rows(db, "SELECT segment, count(*) FROM eqos.registry_listings GROUP BY 1"))
    assert segments == {"NSE_EQ": counts["NSE_EQ"], "BSE_EQ": counts["BSE_EQ"]}


@pytest.mark.parametrize("vendor", list(ScreenVendor))
def test_each_screen_run_holds_the_manifest_members(world: Any, vendor: ScreenVendor) -> None:
    """``screen.<vendor>``: each member's row (Screener ``row``; Tijori ``data_index + 1``),
    symbol, listing, reason and slug; the run's screen text and both captures are the fixture's;
    the pair has exactly ``screen.review_items`` and ``screen.review_pending``."""
    db, pair = world["db"], world["pair"]
    run = pair.screener if vendor is ScreenVendor.SCREENER else pair.tijori
    name = vendor.lower()
    expected = []
    for member in SCREEN[name]:
        listing = member["expect"]["listing"] or {"segment": None, "isin": None}
        row = member["row"] if vendor is ScreenVendor.SCREENER else member["data_index"] + 1
        expected.append((row, member["symbol"], listing["segment"], listing["isin"],
                         member["expect"]["reason"], member.get("slug")))  # fmt: skip
    assert rows(db, _MEMBERS, run.run_id) == expected
    hashes = MANIFEST["header"]["derived_fixture"]["fixture_sha256"]
    files = [hashes[SOURCES[label].name] for label in FIXTURE[vendor]]
    assert rows(db, _RUN_SCREEN, run.run_id) == [(SCREEN["screen_text"][name], *files)]
    for view, key in (
        ("screen_review_items", "review_items"),
        ("screen_review_pending", "review_pending"),
    ):
        assert rows(db, _REVIEW.format(view), pair.pair_id) == SCREEN[key]


def inventory(found: list[tuple[Any, ...]], keys: dict[str, str]) -> dict[str, Any]:
    """``comparison.sources`` as stored: XBRL REPORTED values, and each vendor's sides and
    values by its stored ``source_id/surface``, as canonical ids per period-key alias."""
    alias = {str(value): name for name, value in keys.items()}
    sources: dict[str, dict[str, dict[str, set[str]]]] = {}
    for canonical, start, end, instant, source, surface, representation, kind, state in found:
        raw = str(instant) if instant else f"{start}..{end}"
        key = alias.get(raw, raw)
        if source is None:
            if (representation, kind, state) != ("XBRL", "REPORTED", VALUE):
                continue
            name, sets = XBRL, ["value"]
        else:
            name, sets = f"{source}/{surface}", ["sides"] + (["value"] if state == VALUE else [])
        held = sources.setdefault(name, {"value": {}} | ({} if source is None else {"sides": {}}))
        for inventory_set in sets:
            held[inventory_set].setdefault(key, set()).add(canonical)
    return {
        name: {kind: {k: sorted(ids) for k, ids in by.items()} for kind, by in source.items()}
        for name, source in sources.items()
    }


EXCHANGES = ("nse", "bse")
Keep = Callable[[tuple[Any, ...]], bool]
Edit = Callable[[list[tuple[Any, ...]]], list[tuple[Any, ...]]]


def everything(row: tuple[Any, ...]) -> bool:
    """Keep every row."""
    return True


def observed_run(
    db: Any,
    run_id: int,
    keys: dict[str, str],
    keep: Keep = everything,
    *,
    inputs_of: int | None = None,
    edit_inputs: Edit = list,
) -> dict[str, Any]:
    """A member run as stored, in ``batch.members[].run``'s shape (comparison counts aside);
    its retained inputs are every capture its own persisted inputs bind (``inputs_of`` another
    run's instead), by source surface, a surface bound more than once listing each, except an
    exchange's single identity capture (onboarding's, which the manifest does not pin); ``keep``
    filters its comparison rows and ``edit_inputs`` edits its input rows."""
    ((entity, status, manifest, exit_code),) = rows(db, _RUN, run_id)
    scope, pinned = manifest["scope"], manifest["pinned"]
    found = edit_inputs(rows(db, _INPUTS, run_id if inputs_of is None else inputs_of))
    bound: dict[str, list[str]] = {XBRL: []}
    for source, surface, blob, _ in found:
        name = XBRL if surface == XBRL_SURFACE else f"{source}/{surface}"
        bound.setdefault(name, []).append(blob)
    inputs = {name: blobs[0] if len(blobs) == 1 and name != XBRL else sorted(blobs)
              for name, blobs in bound.items()}  # fmt: skip
    inputs = {name: blob for name, blob in inputs.items()
              if not (isinstance(blob, str) and name.split("/")[0] in EXCHANGES)}  # fmt: skip
    ((package_kind, statements),) = rows(db, _PACKAGE, run_id) or [(None, [])]
    found = [row for row in rows(db, _VALUES, run_id) if keep(row)]
    failures = sorted({failure_surface(f) for f in manifest["operational_failures"]})
    return {
        "entity": entity,
        "period_end": "|".join(scope["period_ends"]),
        "basis": "|".join(scope["bases"]),
        "config": {name: pinned[name]["version"] for name in ("dictionary", "mapping_set")},
        "status": status,
        "exit": exit_code,
        "operational_failures": failures,
        "inputs": inputs,
        "comparison": {"package_kind": package_kind, "statements_present": statements,
                       "keys": keys, "sources": inventory(found, keys)},
    }  # fmt: skip


def expected_run(member: dict[str, Any]) -> dict[str, Any]:
    """``batch.members[].run`` without the inventory counts (sizes of the compared sets)."""
    run = member["run"]
    comparison = run["comparison"] | {
        "sources": {
            name: {kind: ids for kind, ids in source.items() if kind != "counts"}
            for name, source in run["comparison"]["sources"].items()
        }
    }
    inputs = run["inputs"] | {XBRL: sorted(run["inputs"][XBRL])}
    return run | {"period_end": str(run["period_end"]), "inputs": inputs, "comparison": comparison}


@pytest.mark.parametrize("symbol", BATCH["declared"])
def test_each_batch_member_is_admitted_with_its_own_comparison(world: Any, symbol: str) -> None:
    """``batch.members[]``: outcome, verified ISIN, unit states and the member's own run: entity,
    period, basis, config pins, status, exit, failures, retained inputs, package and the exact
    per-source comparison inventory over undimensioned results."""
    db, member = world["db"], MEMBERS[symbol]
    ((outcome, isin, record),) = rows(db, _RESULT, symbol)
    units = {u: {"state": s} | ({"reason": r} if r else {}) for u, s, r in rows(db, _UNITS, record)}
    assert (outcome, isin, units) == (member["outcome"], member["isin"], member["units"])
    keys, expected = member["run"]["comparison"]["keys"], expected_run(member)
    assert all(isinstance(blob, str) for name, blob in expected["inputs"].items() if name != XBRL)
    assert observed_run(db, world["runs"][symbol], keys) == expected


MUTATIONS: dict[str, dict[str, Any]] = {
    # the observed state, not the store: whose run is read as ETERNAL's, whose persisted inputs
    # are read as its inputs, which comparison and input rows are kept
    "run-swapped-for-another-entity": {"whose": "TITAN"},
    "comparison-rows-removed": {"keep": lambda row: False},
    "one-vendor-rows-removed": {"keep": lambda row: row[4] != "tijori"},
    "inputs-of-another-run": {"inputs_of": "TITAN"},
    "one-input-missing": {"edit_inputs": lambda found: [r for r in found if r[0] != "tijori"]},
    "duplicate-input": {
        "edit_inputs": lambda found: found + [next(r[:3] + (0,) for r in found if r[0] == "tijori")]
    },
    "unexpected-source": {"edit_inputs": lambda found: found + [("tijori", "overview", "0", 0)]},
}


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_a_mutated_observation_fails_the_member_assertion(world: Any, mutation: str) -> None:
    """ETERNAL's unmutated observation matches its manifest run; swapped for TITAN's, with its
    comparison rows (all, or one vendor's) removed, with TITAN's inputs, one input missing, one
    bound twice or one from an unexpected source, it no longer does."""
    change, runs = MUTATIONS[mutation], world["runs"]
    member = MEMBERS["ETERNAL"]
    keys = member["run"]["comparison"]["keys"]
    expected = expected_run(member)
    assert observed_run(world["db"], runs["ETERNAL"], keys) == expected
    mutated = observed_run(
        world["db"],
        runs[change.get("whose", "ETERNAL")],
        keys,
        change.get("keep", everything),
        inputs_of=runs[change["inputs_of"]] if "inputs_of" in change else None,
        edit_inputs=change.get("edit_inputs", list),
    )
    assert mutated != expected


def expected_census(world: Any) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """``batch.declared``'s runs exactly: one per member, its manifest entity, period end and
    basis, and the batch result naming it."""
    runs = sorted((world["runs"][symbol], symbol) for symbol in BATCH["declared"])
    scoped = [(run, symbol, str(MEMBERS[symbol]["run"]["period_end"]),
               MEMBERS[symbol]["run"]["basis"]) for run, symbol in runs]  # fmt: skip
    return scoped, sorted((symbol, run) for run, symbol in runs)


def observed_census(census: tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]) -> Any:
    """The census rows in :func:`expected_census`'s shape."""
    runs, results = census
    scoped = [(run, entity, "|".join(scope["period_ends"]), "|".join(scope["bases"]))
              for run, entity, scope in runs]  # fmt: skip
    return scoped, list(results)


CENSUS_MUTATIONS: dict[str, Callable[[Any], Any]] = {
    "extra-run-for-a-declared-member": lambda c: (c[0] + [(99, "TITAN", c[0][0][2])], c[1]),
    "result-names-another-run": lambda c: (c[0], [(c[1][0][0], 99), *c[1][1:]]),
}


def test_the_batch_ran_exactly_the_declared_scoped_runs(world: Any) -> None:
    """D7 Task 6: at batch completion the database holds exactly three runs, one per declared
    member with its manifest entity, period and basis, each named by that member's result; an
    extra run or a result naming another run fails the comparison."""
    expected = expected_census(world)
    assert observed_census(world["census"]) == expected
    for mutate in CENSUS_MUTATIONS.values():
        assert observed_census(mutate(world["census"])) != expected


def test_the_batch_is_complete_and_the_others_have_nothing(world: Any) -> None:
    """``batch.completed``; ``batch.others_expect`` at batch completion."""
    db, batch = world["db"], world["batch"]
    declared = "SELECT cardinality(member_ids) FROM eqos.capture_batches WHERE id = %s"
    assert rows(db, declared, batch) == [(len(BATCH["declared"]),)]
    completed = "SELECT count(*) = 1 FROM eqos.batch_completions WHERE batch_id = %s"
    assert rows(db, completed, batch) == [(BATCH["completed"],)]
    assert world["others"] == BATCH["others_expect"]


def test_a_symbol_change_is_a_candidate_event_only(world: Any) -> None:
    """``registry.loads`` 3: the SYNTHETIC ZOMATO capture is a new load with one candidate event
    and ZOMATO current on NSE; the identity layers (ETERNAL verified) do not change."""
    db, later = world["db"], REGISTRY["loads"][2]
    body = INSTRUMENTS.read_bytes()
    equity = [
        r for r in json.loads(gzip.decompress(body)) if r.get("segment") in ("NSE_EQ", "BSE_EQ")
    ]
    assert not [r for r in equity if r.get("trading_symbol") == "ZOMATO"], "precondition"
    path = capture(world["root"] / "zomato", remark(body, "NSE_EQ", "ETERNAL", "ZOMATO"),
                   datetime(2026, 10, 1, 6, 0, tzinfo=UTC))  # fmt: skip
    before = identity(db)
    code, out = coverage("registry", "--instruments", str(path), "--snapshot-root", world["snaps"])
    assert code == EXIT_OK
    assert (out["created"] == "True", int(out["new_listings"])) == (
        later["created"],
        later["new_listings"],
    )
    events = [(e["listing"], e["from"], e["to"]) for e in later["candidate_events"]]
    assert int(out["candidate_events"]) == len(events) and rows(db, _EVENTS) == events
    assert {key: rows(db, _CURRENT, key)[0][0] for key in later["current"]} == later["current"]
    assert identity(db) == before


def draft(db: Any, entity: int, kind: ReportKind, period: str) -> int:
    """A runtime report of ``kind`` and its first version (one plain section)."""
    with db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
        cursor = conn.cursor()
        report = store.create_report(cursor, entity_id=entity, period=period, kind=kind)
        section = ReportSection(ordinal=0, section_key="thesis", body="thesis")
        return store.create_version(cursor, VersionDraft(
            report_id=report, author="stage4-e2e", knowledge_cutoff=CUTOFF,
            content_hash=CONTENT_HASH, sections=(section,),
        ))  # fmt: skip


def append_section(db: Any, version: int) -> None:
    """A runtime section appended to an existing version."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        conn.execute(_SECTION, {"version": version, "ordinal": 1, "key": "late"})


def test_watchlist_and_drafting_follow_the_manifest(world: Any) -> None:
    """``watchlist`` steps 1-8 in order: ``fundamentals onboard CGPOWER`` outside a batch, then
    ``ledger decide`` ADD/REMOVE as the owner and runtime drafts, each ACCEPTED or REFUSED."""
    db, raw, snaps = world["db"], world["raw"], world["snaps"]
    main(["onboard", "CGPOWER", "--raw-root", str(raw / "CGPOWER"), "--snapshot-root", snaps])
    entity = {s: rows(db, _ENTITY, s)[0][0] for s in ("CGPOWER", "ETERNAL", "TITAN")}
    shown: list[str] = []
    version: list[int] = []

    def decide(symbol: str, kind: str) -> None:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("sys.stdin", io.StringIO(f"Stage 4 e2e: {kind} {symbol}\n"))
            code = main(["ledger", "decide", "WATCHLIST", str(entity[symbol]), kind])
        shown.append({EXIT_OK: ACCEPTED, EXIT_REFUSED: REFUSED}[code])

    def runtime(step: Callable[[], Any], refusal: str) -> None:
        try:
            version.append(step())
        except errors.CheckViolation as refused:
            assert refusal in str(refused)
            shown.append(REFUSED)
        else:
            shown.append(ACCEPTED)

    decide("CGPOWER", "ADD")
    decide("ETERNAL", "ADD")
    runtime(lambda: draft(db, entity["TITAN"], ReportKind.BOOTSTRAP_THESIS, "FY27_Q1"), OFF)
    eternal = entity["ETERNAL"]
    runtime(lambda: draft(db, eternal, ReportKind.EARNINGS_UPDATE, "FY27_Q1"), "no bootstrap")
    runtime(lambda: draft(db, eternal, ReportKind.BOOTSTRAP_THESIS, "FY27_Q1"), OFF)
    decide("ETERNAL", "REMOVE")
    runtime(lambda: draft(db, eternal, ReportKind.EARNINGS_UPDATE, "FY27_Q2"), OFF)
    runtime(lambda: append_section(db, version[0]), OFF)
    assert shown == [step["expect"] for step in MANIFEST["watchlist"]]


def test_no_socket_opened(world: Any) -> None:
    """The guard saw no connection attempt."""
    assert world["connects"] == []
