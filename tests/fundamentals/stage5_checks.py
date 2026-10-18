"""The ledger Stage 5 comparators (plan D9 Task 9): each checks one frozen manifest section
against what the system stored, so the e2e reads as the scripted flow and the mutations reuse
the same comparisons.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg
import pytest
from stage1_e2e_support import CONFIG
from stage5_support import (
    COUNTED,
    ENTITY,
    FIX,
    INCIDENTS,
    RECORDS,
    SCRIPT,
    M,
    World,
    cli,
    digest,
)
from test_backup_restore import use_env
from test_retention_purge import inventory

from fundamentals.api.db_cli import restore_purge_first
from fundamentals.contracts.retention import CaptureFacts, Eligibility
from fundamentals.pg.backup import CAPTURES_DIR, RestoreCheck, verify_set
from fundamentals.pg.retention_io import read_authority
from fundamentals.retention.eligibility import add_months, eligibility
from fundamentals.retention.holds import capture_facts, pinned_roots
from fundamentals.store.snapshot_store import SnapshotStore

ATTEMPT = "SELECT id, outcome, category, http_status, fetched_sha256, severity FROM "
ATTEMPT += "eqos.refetch_attempts WHERE capture_ref_id = %s ORDER BY id DESC LIMIT 1"
CLASS = "SELECT retention_class FROM eqos.retention_classes WHERE capture_ref_id = %s"
ADDRESS = "SELECT url FROM eqos.capture_addresses WHERE capture_ref_id = %s"
ENDS = "SELECT source_id FROM eqos.licence_ends ORDER BY 1"


def facts(world: World, cfg: Path) -> dict[str, CaptureFacts]:
    """Every non-expired capture's retention facts, by label, with the test-only holds list."""
    with world.db.migrator_connection() as conn:
        found = capture_facts(conn, pinned_roots(cfg))
    return {world.label(f.capture_ref_id): f for f in found}


def store_now(world: World) -> Any:
    """``eqos.store_now()``."""
    return world.sql("SELECT eqos.store_now()")[0][0]


def check_fixtures(world: World, at: dict[str, CaptureFacts], labels: list[str]) -> None:
    """fixtures: entity, class, effective class, address, holds and verification anchor."""
    for label in labels:
        want, got = FIX[label], at[label]
        cid = world.ids[label]
        if "arises" in want:  # no package or attempt: the entity of the capture it re-fetched
            origin = want["arises"].split()[0].removeprefix("refetch.")
            assert FIX[origin]["entity"] == want["entity"], label
        else:
            entities = {row[0] for row in world.sql(ENTITY, {"c": cid})}
            assert entities == (set() if want["entity"] == "none" else {want["entity"]}), label
        assert world.sql(CLASS, (cid,)) == [(want["base_class"],)], label
        effective = "COVERED" if got.covered else got.base_class.value
        assert effective == want["effective_class"], label
        if label != "M-Q4":  # url: not asserted
            assert [row[0] for row in world.sql(ADDRESS, (cid,))] == [
                u for u in [want["url"]] if u
            ], label
        holds = {h.value for h in got.holds}
        if "holds" in want:
            assert holds == set(want["holds"]), label
        else:
            assert set(want["holds_include"]) <= holds, label
            assert not holds & set(want["holds_exclude"]), label
        run = want["verified"].split()[0]
        if run == "none":
            assert got.verified_at is None, label
        elif label != "L-X":  # irrelevant: COVERED precedes the anchor
            ((created,),) = world.sql(
                "SELECT created_at FROM eqos.runs WHERE id = %s", (world.runs[run],)
            )
            assert got.verified_at == created, label


def check_eligibility(
    spec: dict[str, Any], at: dict[str, CaptureFacts], now: Any, got: dict[str, Eligibility]
) -> None:
    """eligibility: kind, roots, reason and ``since`` as anchor + rule (header.notation.since)."""
    for label, want in spec.items():
        if label == "at":
            continue
        fact, verdict = at[label], got.get(label) or eligibility(at[label], now)
        assert verdict.kind.value == want["kind"], (label, verdict)
        if want["kind"] == "HELD":
            assert sorted(h.value for h in verdict.held_by) == want["roots"], label
        if want["kind"] == "ELIGIBLE":
            assert verdict.reason is not None and verdict.reason.value == want["reason"], label
            since = want["since"]
            if since == "LICENCE_END":
                assert fact.licence_ended_at is not None
                expected = fact.licence_ended_at
            else:
                anchor = (
                    fact.verified_at if since["anchor"] == "verified_at" else fact.registered_at
                )
                assert anchor is not None, label
                expected = add_months(anchor, since["months"])
            assert verdict.since == expected, label
        if want.get("basis") == "COVERED":
            assert fact.covered, label
        if want.get("basis") == "no verification time":
            assert fact.verified_at is None, label


def check_probes(world: World, name: str, rows: list[Any], halted: list[str]) -> None:
    """probe.invocations: rows (label, outcome, category, severity), halted sources and the
    open incidents (checked at the end, when every listed incident is still open)."""
    want = M["probe"]["invocations"][name]
    got = sorted((world.label(r[1]), r[3], r[4], r[5]) for r in rows)
    expected = sorted(
        (w["label"], w["outcome"], w["category"], w.get("severity")) for w in want["rows"]
    )
    assert got == expected, name
    assert len(rows) == M["probe"]["row_count"][name]
    assert sorted(halted) == sorted(want["halted"]), name


def check_incidents(world: World, rows: list[Any]) -> None:
    """probe: a row's incident flag is whether retention_incidents shows it open."""
    open_ids = {i for kind, i in world.sql(INCIDENTS) if kind == "PROBE"}
    by_label = {
        name: {w["label"]: w["incident"] for w in inv["rows"]}
        for name, inv in M["probe"]["invocations"].items()
    }
    for name, probe_rows in rows:
        for row in probe_rows:
            assert (row[0] in open_ids) is by_label[name][world.label(row[1])], (name, row)


def check_records(
    world: World, spec: dict[str, Any], invocations: dict[str, list[Any]], run: str, b: Any
) -> None:
    """purge records of one purge run: fields, blob, store-clock time and the probe each
    cites, the latest MATCH of its source when it commits (header.rules.probe_record)."""
    rows = [r for r in world.sql(RECORDS) if world.purge_runs[r[1]] == run]
    assert sorted(world.label(r[2]) for r in rows) == sorted(spec), run
    for row in rows:
        label = world.label(row[2])
        want = spec[label]
        assert (world.purge_runs[row[1]], row[3], row[4], row[5]) == (
            want["run"],
            want["class"],
            want["reason"],
            want["url"],
        ), label
        assert row[6] == FIX[label]["blob_sha256"] and row[8] >= b, label
        if want["probe"] == "NOT_REQUIRED":
            assert row[7] is None, label
            continue
        probes = invocations[want["probe"]["invocation"]]
        matches = [
            p[0] for p in probes if p[2] == want["probe"]["latest_match"] and p[3] == "MATCH"
        ]
        everything = world.probes(0)
        latest = max(
            p[0]
            for p in everything
            if p[0] <= max(matches) and p[2] == FIX[label]["source"] and p[3] == "MATCH"
        )
        assert row[7] == max(matches) == latest, label


def check_records_kept(world: World) -> None:
    """record_sha256: every capture keeps its bound record hash and record.json bytes."""
    store = SnapshotStore(world.root)
    rows = world.sql("SELECT id, record_sha256 FROM eqos.capture_refs")
    for cid, record in rows:
        label = world.label(cid)
        assert record == world.records[label], label
        store.read_record(*world.ref(label), world.records[label])


def journal(world: World) -> list[dict[str, Any]]:
    """The expiry journal with labels and purge-run names."""
    found = []
    for event in read_authority(world.sets).journal:
        row: dict[str, Any] = {"id": event.id, "kind": event.kind.value}
        row["run"] = world.purge_runs[event.run_id]
        if event.kind.value == "FENCE":
            row["captures"] = sorted(world.label(c.capture_ref_id) for c in event.captures)
        else:
            row["expired"] = sorted(world.label(c) for c in event.expired)
            row["cancelled"] = sorted(world.label(c) for c in event.cancelled)
        found.append(row)
    return found


def expected_journal(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Manifest journal events with sorted label lists."""
    return [{k: sorted(v) if isinstance(v, list) else v for k, v in e.items()} for e in events]


def check_bodies(world: World) -> None:
    """recovery.after_rerun.bodies: no non-EXPIRED capture lacks its body, no EXPIRED one has a
    body link."""
    store, states = SnapshotStore(world.root), world.states()
    for label, state in states.items():
        source, surface, key, capture = world.ref(label)
        link = list((world.root / source / surface / key / capture).glob("body*"))
        assert bool(link) is (state != "EXPIRED"), label
        if state != "EXPIRED" and FIX[label]["licence"] == "none":
            body = store.read_capture_verified(source, surface, key, capture)[1]
            assert hashlib.sha256(body).hexdigest() == FIX[label]["blob_sha256"], label


def restore(
    world: World, monkeypatch: pytest.MonkeyPatch, set_dir: Path, target: str, spec: dict[str, Any]
) -> None:
    """restore: ``db restore --replay-runs --backup-dir`` of a set copied aside, phase 1, the
    markers (before purge-first), purge-first's expiries, hash matches, purge records, record
    hashes, the Tijori captures and the replay report."""
    root = world.tmp / f"restored-{target}"
    seen: list[set[str]] = []

    def observed(set_path: Path, backup_dir: Path, snapshot_root: Path) -> Any:
        inner = restore_purge_first(set_path, backup_dir, snapshot_root)

        def first(conn: psycopg.Connection) -> Any:
            marked = snapshot_root / ".retention" / "licence-ended"
            seen.append({p.name for p in marked.iterdir()} if marked.exists() else set())
            return inner(conn)

        return first

    monkeypatch.setattr("fundamentals.api.db_cli.restore_purge_first", observed)
    use_env(monkeypatch, world.db, world.db.settings.db)  # restore only names the target
    code, out = cli(
        "db",
        "restore",
        "--set",
        str(set_dir),
        "--database",
        target,
        "--snapshot-root",
        str(root),
        "--backup-dir",
        str(world.sets),
        "--replay-runs",
        "--config-root",
        str(CONFIG),
    )
    assert out.strip(), code
    use_env(monkeypatch, world.db, world.db.dbname)
    check = RestoreCheck.model_validate_json(out.strip().splitlines()[-1])
    assert code == 0 and check.ok is spec["ok"], check
    assert check.schema_equal and check.run_ids_equal and check.counts_equal and check.fk_valid
    assert check.faithful and not (check.missing_captures or check.extra_captures)
    assert not check.hash_mismatches and not check.unresolved_bindings
    archived = verify_set(set_dir)
    assert sorted(world.label(c[0]) for c in archived.captures) == sorted(spec["phase1_hash_match"])
    assert [r[0] for r in world.sql(ENDS, dbname=target)] == spec["licence_ends"]
    assert seen == [set(spec["markers"])]  # marker_before_purge_first
    states = world.states(target)
    expired = sorted(label for label, state in states.items() if state == "EXPIRED")
    assert expired == sorted(spec["expired_after_purge_first"])
    restored = SnapshotStore(root)
    retained = sorted(label for label in states if label not in expired)
    assert retained == sorted(spec["retained_hash_match"])
    for label in retained:
        body = restored.read_capture_verified(*world.ref(label))[1]
        assert hashlib.sha256(body).hexdigest() == FIX[label]["blob_sha256"], label
    recorded = {world.label(r[2]) for r in world.sql(RECORDS, dbname=target)}
    assert set(expired) <= recorded
    archive = [*archived.captures, *(item.capture for item in archived.expired)]
    for capture in archive:
        label = world.label(capture[0])
        restored.read_record(*capture[1:5], world.records[label])
        cid = world.ids[label]
        query = "SELECT record_sha256 FROM eqos.capture_refs WHERE id = %s"
        assert world.sql(query, (cid,), target) == [(world.records[label],)], label
    for label, want in spec.get("tijori", {}).items():
        assert states[label] == want["state"], label
        assert world.records[label] == want["record_sha256"], label
    runs = {run: name for name, run in world.runs.items()}
    assert sorted(runs[r] for r in check.replay_expired) == sorted(spec["replay_expired"])
    assert check.replay_mismatches == ()
    for name, result in M["replay"]["runs"].items():
        key = "restore_pre_purge" if spec is M["restore"]["pre_purge"] else "restore_licence_end"
        assert (world.runs[name] in check.replay_expired) is (result[key] == "replay_expired")


def check_preservation(d0: dict[str, Any], later: dict[str, Any]) -> None:
    """Every set's digest equals D0's; recomputed from the rows, so an edited row fails."""
    for name, (_, rows) in later.items():
        texts = [json.dumps(row) for row in rows]
        assert digest(texts) == digest([json.dumps(row) for row in d0[name][1]]), name
        assert later[name][0] == d0[name][0], name


def check_nonempty(world: World, sets: dict[str, Any]) -> None:
    """The preservation bounds at D0."""
    items = {row["id"]: row["run_id"] for row in sets["queue_items"][1]}
    for name, spec in M["preservation"]["sets"].items():
        rows = sets[name][1]
        if spec.get("nonempty"):
            assert rows, name
        for label in spec.get("nonempty_for", []):
            assert any(row["capture_ref_id"] == world.ids[label] for row in rows), (name, label)
        for run in spec.get("nonempty_for_runs", []):
            ran = {row.get("run_id", items.get(row.get("item_id"))) for row in rows}
            assert world.runs[run] in ran, (name, run)


def check_tombstones(spec: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> None:
    """purge.tombstones: counts and statuses at D0 and after (no row deleted), observed
    redactions, NULL values at D0 where frozen, and the A-05 inventory: clear columns NULL,
    resets, json_keep allowlists, every other column as D0."""
    rules = inventory()
    for label, expected in spec.items():
        old, new = before[label], after[label]
        for key, table in COUNTED.items():
            count, want = len(old[table]), expected[key]
            assert count > 0 if want == "nonempty" else count == want, (label, key, count)
            assert len(new[table]) == count, (label, table)
        if "interpretation_statuses" in expected:
            for rows in (old["interpretations"], new["interpretations"]):
                statuses = Counter(row["status"] for row in rows)
                assert statuses == expected["interpretation_statuses"], (label, statuses)
        if "interpretation_values" in expected:  # header.upstox_redaction
            assert all(row["value"] is None for row in old["interpretations"]), label
        for path in expected["cleared_before"]:
            table, column = path.split(".")
            assert any(row[column] is not None for row in old[table]), (label, path)
            assert all(row[column] is None for row in new[table]), (label, path)
        for path in expected["json_dropped"]:
            column, key = path.split(".")
            assert all(key in row[column] for row in old["occurrences"]), (label, path)
            assert not any(key in row[column] for row in new["occurrences"]), (label, path)
        for table, rule in rules.items():
            changed = set(rule.get("clear", [])) | set(rule.get("reset", {}))
            changed |= set(rule.get("json_keep", {}))
            for was, now in zip(old.get(table, []), new.get(table, []), strict=True):
                where = (label, table, now["id"])
                kept = {k: v for k, v in now.items() if k not in changed}
                assert kept == {k: v for k, v in was.items() if k not in changed}, where
                assert all(now[c] is None for c in rule.get("clear", [])), where
                assert all(now[c] == json.loads(v) for c, v in rule.get("reset", {}).items())
                for column, keys in rule.get("json_keep", {}).items():
                    assert set(now[column] or {}) <= set(keys), (*where, column)


def check_mapping_sets(world: World) -> None:
    """header.script.mapping_sets: every run pins, and every interpretation of a capture was
    made under, its entity's mapping set."""
    sets = SCRIPT["mapping_sets"]
    for name, run in world.runs.items():
        query = "SELECT version FROM eqos.run_versions WHERE run_id = %s AND pin = 'mapping_set'"
        assert world.sql(query, (run,)) == [(sets[SCRIPT["runs"][name]["entity"]],)], name
    query = (
        "SELECT DISTINCT mapping_set_version FROM eqos.interpretations WHERE capture_ref_id = %s"
    )
    for label, cid in world.ids.items():
        versions = [row[0] for row in world.sql(query, (cid,))]
        assert versions in ([], [sets.get(FIX[label]["entity"])]), (label, versions)


def check_set(world: World, set_dir: Path, spec: dict[str, Any]) -> None:
    """backup.set_contents: watermark, retained and expired labels, archived record hashes,
    retained bodies, expired urls, latest purge records and no expired body."""
    manifest = verify_set(set_dir)
    archive = SnapshotStore(set_dir / CAPTURES_DIR)
    assert manifest.journal_watermark == spec["journal_watermark"]
    retained = [world.label(capture[0]) for capture in manifest.captures]
    expired = {world.label(item.capture[0]): item for item in manifest.expired}
    assert sorted(retained) == sorted(spec["retained"]) and sorted(expired) == sorted(
        spec["expired"]
    )
    latest = {row[2]: row[0] for row in world.sql(RECORDS)}
    stored = {e.blob_sha256 for e in archive.blob_inventory()}
    for capture in (*manifest.captures, *(item.capture for item in manifest.expired)):
        label = world.label(capture[0])
        assert capture[6] == world.records[label], label
        archive.read_record(*capture[1:5], world.records[label])
        if label in expired:
            assert expired[label].url == FIX[label]["url"], label
            assert expired[label].purge_record_id == latest[capture[0]], label
            assert FIX[label]["blob_sha256"] not in stored, label
        else:
            body = archive.read_capture_verified(*capture[1:5])[1]
            assert hashlib.sha256(body).hexdigest() == FIX[label]["blob_sha256"], label


def published(sets: Path) -> set[str]:
    """The names of the backup directory's published sets; no remnant is left."""
    dirs = [p for p in sets.iterdir() if p.is_dir()]
    assert not [p for p in dirs if p.name.startswith(".") or p.name.endswith(".partial")]
    return {p.name for p in dirs}


def check_dry_run(eligible: set[tuple[str, str]]) -> None:
    """dry_run.blobs: exactly the eligible blobs (source, SHA-256)."""
    assert eligible == {(blob["source"], blob["sha256"]) for blob in M["dry_run"]["blobs"]}


def probe_incidents(world: World, rows: list[Any]) -> set[tuple[str, int]]:
    """The incident keys of the HIGH probe rows."""
    return {("PROBE", row[0]) for row in rows if row[5] == "HIGH"}


def refetch_id(world: World) -> int:
    """The X-Q4 MISMATCH attempt."""
    return int(world.sql(ATTEMPT, (world.ids["X-Q4"],))[0][0])
