"""D9.9: the ledger Stage 5 end-to-end (plan D9 Task 9), D9's exit gate.

One ``eqos_test_*`` database and one ``tmp_path`` snapshot root follow the frozen manifest's
script through the CLI: intake and runs at instant A, ``retention classify``, ``db backup``
copied aside, the store clock at B, the dry-run, a purge crashed at ``FILES_DELETED`` and rerun,
three re-fetches, two ``db restore --replay-runs --backup-dir`` and the Tijori licence end.
Every manifest section is compared with what the system stored; the manifest is the only source
of expected values. Fetches are fakes over the retained bytes and no socket opens. The plan's
mutations (an extra eligible blob, a tombstoned value left set, ``island_value`` kept, a changed
first-party value) make the same comparisons fail.
"""

from __future__ import annotations

import copy
import hashlib
import shutil
import socket
from collections.abc import Callable, Iterator
from datetime import UTC
from pathlib import Path
from typing import Any

import psycopg
import pytest
from pg_support import PgTestDatabase, drop_database, mint_name
from retention_support import retention_cli, set_store_clock
from stage5_checks import (
    ATTEMPT,
    check_bodies,
    check_dry_run,
    check_eligibility,
    check_fixtures,
    check_incidents,
    check_mapping_sets,
    check_nonempty,
    check_preservation,
    check_probes,
    check_records,
    check_records_kept,
    check_set,
    check_tombstones,
    expected_journal,
    facts,
    journal,
    probe_incidents,
    published,
    refetch_id,
    restore,
    store_now,
)
from stage5_support import (
    FIX,
    INCIDENTS,
    REASON,
    RECORDS,
    M,
    World,
    build,
    cli,
    fetcher,
    held_config,
    preserved,
    tombstone_rows,
)

from fundamentals.contracts.retention import CaptureFacts, Eligibility
from fundamentals.contracts.retention_purge import PurgeStep
from fundamentals.evidence.xbrl_adapter import anchor_key_of, parse_instance
from fundamentals.pg.backup import BackupError, verify_set, write_backup
from fundamentals.pg.retention_io import EXPIRY_JOURNAL_FILE, LICENCE_ENDS_FILE, read_authority
from fundamentals.retention import purge as purge_module
from fundamentals.retention.eligibility import add_months, eligibility
from fundamentals.retention.refetch import ATTEMPT_PARAMETER
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

OPEN_RUNS = "SELECT r.id FROM eqos.purge_runs r WHERE NOT EXISTS "
OPEN_RUNS += "(SELECT 1 FROM eqos.purge_run_closures c WHERE c.run_id = r.id) ORDER BY r.id"
INTENTS = "SELECT DISTINCT capture_ref_id FROM eqos.capture_states "
INTENTS += "WHERE state = 'PURGE_PENDING' AND purge_run_id = %s"
ANCHORS = "SELECT anchor_key FROM eqos.occurrences WHERE capture_ref_id = %s"
PAYLOAD = "SELECT (SELECT count(*) FROM eqos.occurrences WHERE capture_ref_id = %(c)s), "
PAYLOAD += "(SELECT count(*) FROM eqos.interpretations WHERE capture_ref_id = %(c)s)"
ENDS = "SELECT source_id FROM eqos.licence_ends ORDER BY 1"
CLOSED = "SELECT run_id, closed_at FROM eqos.purge_run_closures ORDER BY run_id"
STARTED = "SELECT id, started_at FROM eqos.purge_runs ORDER BY id"
VENDOR_LABELS = ["A-SCR", "U-APQ", "L-TIJ", "N-TIJ", "N-UPC"]


class CrashError(Exception):
    """The raised crash at a purge checkpoint (recovery.crash)."""


@pytest.fixture
def targets(pg_db: PgTestDatabase) -> Iterator[Callable[[], str]]:
    """Fresh restore-target names, every one dropped afterwards."""
    names: list[str] = []

    def new() -> str:
        names.append(mint_name(pg_db.settings))
        return names[-1]

    yield new
    for name in names:
        drop_database(pg_db.settings, name)


def test_ledger_stage5_matches_the_frozen_manifest(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    targets: Callable[[], str],
) -> None:
    """The scripted Stage 5 flow stores exactly what the frozen manifest decides, and the plan's
    four mutations make the same comparisons fail."""
    connects: list[Any] = []

    def refuse(*args: Any) -> None:
        connects.append(args)
        raise OSError("socket guard")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    cfg = held_config(tmp_path)
    with pg_db.runtime_pool() as pool, pg_db.owner_pool() as owner:
        world = World(pg_db, pool, owner, tmp_path)
        build(world, monkeypatch)
        registered = [label for label in FIX if "arises" not in FIX[label]]
        assert sorted(world.ids) == sorted(registered)
        assert all(
            FIX[k]["licence"] == ("tijori" if FIX[k]["source"] == "tijori" else "none")
            for k in registered
        )
        check_mapping_sets(world)
        assert world.replays() == {n: r["at_A"] for n, r in M["replay"]["runs"].items()}

        # steps 8: classify, S0 aside, t_A
        assert retention_cli(monkeypatch, pg_db, "classify")[0] == 0
        code, out = cli(
            "db", "backup", "--out", str(world.sets), "--snapshot-root", str(world.root)
        )
        assert code == 0, out
        s0 = Path(out.split("\t")[1].strip())
        backup = M["backup"]
        assert (world.sets / LICENCE_ENDS_FILE).is_file()
        assert (world.sets / EXPIRY_JOURNAL_FILE).is_file()
        check_set(world, s0, backup["S0"])
        s0_aside = Path(shutil.copytree(s0, tmp_path / "aside" / "S0"))
        t_a = store_now(world)

        # steps 9: B, the dry-run, D0
        b = add_months(t_a, 13)
        with pg_db.migrator_connection() as migrator:
            set_store_clock(migrator, b)
        at_b = facts(world, cfg)
        check_fixtures(world, at_b, registered)
        check_eligibility(M["eligibility"]["at_B"], at_b, store_now(world), {})
        code, out = retention_cli(
            monkeypatch, pg_db, "purge", "--dry-run", "--config-root", str(cfg)
        )
        assert code == M["dry_run"]["exit"], out
        lines = [line.split("\t") for line in out.splitlines()]
        eligible = {(line[1], line[2]) for line in lines if line[0] == "eligible"}
        check_dry_run(eligible)
        assert [line for line in lines if line[0] == "incident"] == M["dry_run"]["open_incidents"]
        d0 = preserved(world)
        check_nonempty(world, d0)
        before = tombstone_rows(world, VENDOR_LABELS)
        tombstone_rows_d0 = tombstone_rows(world, ["U-INS", "W-CSV"])

        # steps 10: the purge crashed at FILES_DELETED, then rerun
        args = ["--snapshot-root", str(world.root), "--backup-dir", str(world.sets)]
        args += ["--config-root", str(cfg)]
        monkeypatch.setattr("fundamentals.api.retention_cli.live_fetch", fetcher(world, False))

        def crash(step: PurgeStep) -> None:
            if step is PurgeStep[M["recovery"]["crash"]]:
                raise CrashError(step)

        with monkeypatch.context() as patch:
            patch.setattr("fundamentals.api.retention_cli._no_checkpoint", crash)
            with pytest.raises(CrashError):
                retention_cli(monkeypatch, pg_db, "purge", *args)
        world.name_purge_runs()
        p1 = world.probes(0)
        crashed = M["recovery"]["after_crash"]
        assert world.states() == crashed["states"]
        assert sorted(set(world.ids) - world.blobs()) == sorted(crashed["blobs_absent"])
        assert [e["id"] for e in journal(world)] == crashed["journal"]
        assert world.sql(RECORDS) == crashed["purge_records"]
        assert [world.purge_runs[r[0]] for r in world.sql(OPEN_RUNS)] == crashed["open_runs"]
        assert published(world.sets) == {s0.name} and crashed["sets_present"] == ["S0"]
        failed = {FIX[world.label(r[1])]["source"] for r in p1 if r[3] == "FAILED"}
        check_probes(world, "P1", p1, sorted(failed))
        assert not {
            label
            for label, s in world.states().items()
            if s == "PURGE_PENDING" and FIX[label]["source"] in failed
        }
        with (
            pytest.raises(psycopg.Error, match="fundamentals retention purge"),
            pool.connection() as conn,
        ):  # recovery.after_crash.refused: claim insert (the guard refuses first)
            conn.execute("INSERT INTO eqos.numeric_claims DEFAULT VALUES")
        backup_args = ("db", "backup", "--out", str(world.sets), "--snapshot-root", str(world.root))
        assert cli(*backup_args)[0] == 2
        with pytest.raises(BackupError, match="fundamentals retention purge"):
            write_backup(
                pg_db.settings, database=pg_db.dbname, snapshot_root=world.root, out_dir=world.sets
            )
        last = world.last_probe()
        code, out = retention_cli(monkeypatch, pg_db, "purge", *args)
        assert code == M["purge"]["exit"], out
        world.name_purge_runs()
        rerun = world.probes(last)
        halted = [line.split("\t")[1] for line in out.splitlines() if line.startswith("halted\t")]
        check_probes(world, "rerun", rerun, halted)
        assert min(r[0] for r in rerun) > max(r[0] for r in p1)
        purge = M["purge"]
        assert world.states() == purge["states"]
        check_records(world, purge["records"], {"rerun": rerun}, "P1", b)
        assert not [r for r in world.sql(RECORDS) if world.purge_runs[r[1]] != "P1"]
        assert sorted(world.blobs()) == sorted(purge["blobs"]["present"])
        assert sorted(set(world.ids) - world.blobs()) == sorted(purge["blobs"]["absent"])
        after = tombstone_rows(world, VENDOR_LABELS)
        check_tombstones(purge["tombstones"]["labels"], before, after)
        untouched = tombstone_rows(world, ["U-INS", "W-CSV"])  # purge.tombstones.not_tombstoned
        assert untouched == tombstone_rows_d0
        assert (
            not untouched["W-CSV"]["occurrences"] and not untouched["W-CSV"]["acquisition_attempts"]
        )
        check_records_kept(world)
        rerun_spec = M["recovery"]["after_rerun"]
        assert [e["id"] for e in journal(world)] == rerun_spec["journal"]
        assert world.sql(OPEN_RUNS) == rerun_spec["open_runs"]
        closed, started = dict(world.sql(CLOSED)), dict(world.sql(STARTED))
        assert all(started[run] >= closed[run - 1] for run in started if run - 1 in closed)
        assert journal(world) == expected_journal(backup["journal"])
        sets = published(world.sets)
        assert s0.name not in sets and len(sets) == len(backup["after_rerun"]["sets_present"])
        by_mark = {verify_set(world.sets / name).journal_watermark: name for name in sets}
        for name in backup["after_rerun"]["sets_present"]:
            spec = backup["after_rerun"][name]
            check_set(world, world.sets / by_mark[spec["journal_watermark"]], spec)
        check_bodies(world)
        d1 = preserved(world)
        check_preservation(d0, d1)
        assert world.replays() == {n: r["D1"] for n, r in M["replay"]["runs"].items()}

        # steps 11: three re-fetches, X-Q2P's re-extraction, D2
        monkeypatch.setattr("fundamentals.api.retention_cli.live_fetch", fetcher(world, True))
        refetched = M["refetch"]
        capture_row = "SELECT * FROM eqos.capture_refs WHERE id = %s"
        unchanged = world.sql(capture_row, (world.ids["X-Q2P"],))  # refetch.X-Q2P.unchanged
        for label in ("X-Q2P", "X-Q4", "X-Q5"):
            count = len(world.sql("SELECT id FROM eqos.capture_refs"))
            want = refetched[label]
            code, out = retention_cli(
                monkeypatch,
                pg_db,
                "refetch",
                "--capture",
                str(world.ids[label]),
                "--snapshot-root",
                str(world.root),
            )
            assert code == want["command"]["exit"], (label, out)
            ((attempt, *got),) = world.sql(ATTEMPT, (world.ids[label],))
            spec = want["attempt"]
            assert got == [
                spec["outcome"],
                spec["category"],
                spec["http_status"],
                spec["fetched_sha256"],
                spec.get("severity"),
            ], label
            assert world.states()[label] == want["command"]["state"], label
            new = len(world.sql("SELECT id FROM eqos.capture_refs")) - count
            assert new == (1 if "new_capture" in want["command"] else 0), label
            if spec.get("code"):
                assert out.startswith(spec["code"]) and ("REFETCH", attempt) in world.sql(INCIDENTS)
            if "new_capture" in want["command"]:
                world.bind()
                record = SnapshotStore(world.root).read_record(
                    *world.ref(want["command"]["new_capture"]), world.records["M-Q4"]
                )
                assert (
                    f'"{ATTEMPT_PARAMETER}"' in record.decode() and str(attempt) in record.decode()
                )
        assert world.sql(capture_row, (world.ids["X-Q2P"],)) == unchanged
        assert set(world.ids) - world.blobs() >= {"X-Q4", "X-Q5"} and "X-Q2P" in world.blobs()
        body = SnapshotStore(world.root).read_capture_verified(*world.ref("X-Q2P"))[1]
        assert hashlib.sha256(body).hexdigest() == FIX["X-Q2P"]["blob_sha256"]
        instance = parse_instance(body, mapping_set=world.stage.config.mapping_set)
        stored = {row[0] for row in world.sql(ANCHORS, (world.ids["X-Q2P"],))}
        assert {anchor_key_of(fact) for fact in instance.facts} == stored  # reextract
        assert world.sql(PAYLOAD, {"c": world.ids["M-Q4"]}) == [(0, 0)]  # preservation.m_q4
        incidents = probe_incidents(world, p1 + rerun) | {("REFETCH", refetch_id(world))}
        assert set(world.sql(INCIDENTS)) == incidents  # refetch.open_incidents
        at_d2 = facts(world, cfg)
        assert at_d2["X-Q2P"].verified_at == at_b["X-Q2P"].verified_at  # anchor kept (R10)
        check_fixtures(world, at_d2, ["M-Q4"])
        before_end = M["eligibility"]["before_licence_end"]
        assert sorted(at_d2) == sorted(k for k in before_end if k != "at")
        check_eligibility(before_end, at_d2, store_now(world), {})
        d2 = preserved(world)
        check_preservation(d0, d2)
        check_records_kept(world)

        # steps 12: restore S0'
        restore(world, monkeypatch, s0_aside, targets(), M["restore"]["pre_purge"])

        # steps 13: S2 aside
        code, out = cli(*backup_args)
        assert code == 0, out
        s2 = Path(out.split("\t")[1].strip())
        check_set(world, s2, backup["S2"])
        s2_aside = Path(shutil.copytree(s2, tmp_path / "aside" / "S2"))

        # steps 14: the Tijori licence end, D3
        ended = M["licence_end"]
        verdicts: dict[str, Eligibility] = {}
        spied: dict[str, CaptureFacts] = {}

        def spy(fact: CaptureFacts, now: Any) -> Eligibility:
            verdict = eligibility(fact, now)
            spied[world.label(fact.capture_ref_id)] = fact
            verdicts[world.label(fact.capture_ref_id)] = verdict
            return verdict

        monkeypatch.setattr("fundamentals.api.retention_cli.live_fetch", fetcher(world, False))
        last = world.last_probe()
        with monkeypatch.context() as patch:
            patch.setattr(purge_module, "eligibility", spy)
            code, out = retention_cli(
                monkeypatch,
                pg_db,
                "licence-end",
                "--source",
                "tijori",
                "--ended-on",
                str(b.astimezone(UTC).date()),
                "--reason",
                REASON,
                *args,
            )
        assert code == ended["command"]["exit"], out
        world.name_purge_runs()
        assert sorted(world.purge_runs.values())[-1] == ended["command"]["run"]
        assert (world.root / ".retention" / "licence-ended" / "tijori").is_file()
        assert [e.source_id for e in read_authority(world.sets).licence_ends] == ["tijori"]
        assert world.sql(ENDS) == [("tijori",)]
        p3 = world.probes(last)
        halted = [line.split("\t")[1] for line in out.splitlines() if line.startswith("halted\t")]
        check_probes(world, "P3", p3, halted)
        check_eligibility(M["eligibility"]["after_licence_end"], spied, None, verdicts)
        assert spied["N-TIJ"].licence_ended_at is not None
        assert spied["N-TIJ"].licence_ended_at.date() == b.astimezone(UTC).date()
        run_id = next(r for r, name in world.purge_runs.items() if name == "P3")
        assert sorted(world.label(r[0]) for r in world.sql(INTENTS, (run_id,))) == sorted(
            ended["intents"]
        )
        assert world.states() == ended["states"]
        check_records(world, ended["records"], {"P3": p3}, "P3", b)
        counts = {label: 0 for label in ended["record_counts"]}
        for row in world.sql(RECORDS):
            label = world.label(row[2])
            counts[label] = counts.get(label, 0) + 1
        assert {k: counts[k] for k in ended["record_counts"]} == ended["record_counts"]
        assert sorted(world.blobs()) == sorted(ended["blobs"]["present"])
        assert sorted(set(world.ids) - world.blobs()) == sorted(ended["blobs"]["absent"])
        check_tombstones(ended["tombstones"]["labels"], before, tombstone_rows(world, ["N-TIJ"]))
        assert journal(world)[-2:] == expected_journal(ended["journal"])
        sets = published(world.sets)
        assert not sets & {s2.name, *by_mark.values()}  # S1a, S1b and S2 deleted
        (s3,) = sets
        check_set(world, world.sets / s3, ended["S3"])
        check_bodies(world)
        check_records_kept(world)
        incidents = probe_incidents(world, p1 + rerun + p3) | {("REFETCH", refetch_id(world))}
        assert set(world.sql(INCIDENTS)) == incidents  # licence_end.open_incidents
        check_incidents(world, [("P1", p1), ("rerun", rerun), ("P3", p3)])
        undisposed = world.sql(
            "SELECT count(*) FROM eqos.queue_items q WHERE run_id = %s AND "
            "NOT EXISTS (SELECT 1 FROM eqos.queue_dispositions d "
            "WHERE d.item_id = q.id)",
            (world.runs["RUN-N"],),
        )
        assert undisposed == [(1,)]  # holds notwithstanding: the open item stays open
        d3 = preserved(world)
        check_preservation(d0, d3)
        assert world.replays() == {n: r["D3"] for n, r in M["replay"]["runs"].items()}

        # steps 15: restore S2'
        restore(world, monkeypatch, s2_aside, targets(), M["restore"]["licence_end"])
    assert connects == []

    # The plan's mutations: each comparison fails once the state drifts.
    with pytest.raises(AssertionError):  # an extra eligible blob
        check_dry_run(eligible | {(FIX["X-Q1"]["source"], FIX["X-Q1"]["blob_sha256"])})
    left = copy.deepcopy(after)
    left["A-SCR"]["occurrences"][0]["raw_value_text"] = before["A-SCR"]["occurrences"][0][
        "raw_value_text"
    ]
    labels = M["purge"]["tombstones"]["labels"]
    with pytest.raises(AssertionError):  # a value left set
        check_tombstones(labels, before, left)
    kept = copy.deepcopy(after)
    island = before["L-TIJ"]["occurrences"][0]["native_context"]["island_value"]
    kept["L-TIJ"]["occurrences"][0]["native_context"]["island_value"] = island
    with pytest.raises(AssertionError):  # island_value kept
        check_tombstones(labels, before, kept)
    changed = copy.deepcopy(d3)
    changed["non_vendor_occurrences"][1][0]["raw_value_text"] = "1" + str(
        changed["non_vendor_occurrences"][1][0]["raw_value_text"]
    )
    with pytest.raises(AssertionError):  # one changed first-party value
        check_preservation(d0, changed)
