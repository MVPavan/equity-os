"""Structure of the frozen ledger Stage 5 manifest (plan D9 Task 8).

A leaf module: it imports no ``fundamentals`` code, so frozen-oracle validation never loads the
retention implementation it judges.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import Any

HEX = re.compile(r"[0-9a-f]{64}")
RUNTIME_BINDING = "RUNTIME_BINDING"  # header.notation.record_sha256
SECTIONS = {"header", "fixtures", "eligibility", "dry_run", "probe", "purge", "preservation"}
SECTIONS |= {"backup", "refetch", "licence_end", "recovery", "replay", "restore"}
HEADER = {"manifest", "spec", "hand_verification", "approval", "notation", "arithmetic", "rules"}
HEADER |= {"clock", "script", "derived_blobs", "sources"}
FIELDS = {"entity", "source", "surface", "base_class", "effective_class", "url", "blob_sha256"}
FIELDS |= {"verified", "licence", "record_sha256"}
RECORD = {"run", "class", "reason", "url", "probe"}
CLASSES = {"COVERED", "EXCHANGE_REFETCHABLE", "VENDOR", "IDENTITY"}
REASONS = {"WINDOW", "CATALOG_CEILING", "LICENCE_END"}
ROOTS = {"OPEN_QUEUE_ITEM", "QUALIFICATION_FIXTURE"}
REFETCHED = ("X-Q2P", "X-Q4", "X-Q5")  # Task 9: same bytes, other bytes, failure
STATES = {"RETAINED", "RESTORED", "PURGE_PENDING", "EXPIRED"}
TOMBSTONE = {"occurrences", "interpretations", "result_source_values", "extraction_attempts"}
TOMBSTONE |= {"cleared_before", "json_dropped"}
LABEL = re.compile(r"[A-Z]-[A-Z0-9]+")
RUN = re.compile(r"RUN-[A-Z0-9]+")
PURGE_RUN = re.compile(r"P\d+")
SET_NAME = re.compile(r"S\d[ab]?")
PRESERVED = {"nonempty", "nonempty_for", "nonempty_for_runs"}
REQUIRED = (  # the Task 8 inventory: each path names a non-empty value
    "header.sources header.script.steps header.script.runs header.script.purge_runs fixtures "
    "eligibility.at_B eligibility.before_licence_end eligibility.after_licence_end dry_run.blobs "
    "probe.invocations.P1.rows probe.invocations.rerun.rows probe.invocations.P3.rows "
    "purge.states purge.records purge.blobs.present purge.blobs.absent purge.tombstones.labels "
    "purge.tombstones.inventory preservation.checkpoints preservation.sets preservation.rule "
    "backup.S0 backup.after_rerun.S1a backup.after_rerun.S1b backup.S2 backup.journal "
    "backup.set_contents licence_end.command licence_end.intents licence_end.states "
    "licence_end.records licence_end.blobs.absent licence_end.tombstones.labels "
    "licence_end.journal licence_end.S3 recovery.crash recovery.after_crash.states "
    "recovery.after_crash.blobs_absent recovery.after_crash.journal recovery.after_crash.open_runs "
    "recovery.after_rerun.journal replay.runs restore.pre_purge.phase1_hash_match "
    "restore.pre_purge.expired_after_purge_first restore.pre_purge.retained_hash_match "
    "restore.pre_purge.replay_expired restore.licence_end.phase1_hash_match "
    "restore.licence_end.expired_after_purge_first restore.licence_end.retained_hash_match "
    "restore.licence_end.tijori restore.licence_end.replay_expired"
).split()
Mutation = Callable[[dict[str, Any]], object]


def nodes(node: Any) -> Iterator[dict[str, Any]]:
    """Every mapping in the manifest, depth first."""
    if isinstance(node, dict):
        yield node
        node = list(node.values())
    if isinstance(node, list):
        for item in node:
            yield from nodes(item)


def check_required(manifest: dict[str, Any]) -> None:
    """Every inventory path is present and non-empty; every preservation set is well formed."""
    for path in REQUIRED:
        node = manifest
        for key in path.split("."):
            node = node[key]
        assert node, path
    for name, preserved in manifest["preservation"]["sets"].items():
        assert preserved["table"] and preserved["order"] and PRESERVED & preserved.keys(), name


def check_references(manifest: dict[str, Any]) -> None:
    """Every capture label, run, purge run, backup set and source any section names is declared."""
    header = manifest["header"]
    holders = (manifest["backup"], manifest["backup"]["after_rerun"], manifest["licence_end"])
    declared = (
        (LABEL, set(manifest["fixtures"])),
        (RUN, set(header["script"]["runs"])),
        (PURGE_RUN, set(header["script"]["purge_runs"])),
        (SET_NAME, {name for holder in holders for name in holder if SET_NAME.fullmatch(name)}),
    )
    sources = {entry["label"] for entry in header["sources"]}
    for node in nodes({k: v for k, v in manifest.items() if k != "header"}):
        for key, value in node.items():
            values = value if isinstance(value, list) else [value]
            if key == "src":
                assert value in sources, value
                continue
            for name in [key, *values]:
                for pattern, names in declared:
                    if isinstance(name, str) and pattern.fullmatch(name.rstrip("'")):
                        assert name.rstrip("'") in names, (key, name)
        if "label" in node:
            assert node["label"] in manifest["fixtures"], node


def check_fixtures(manifest: dict[str, Any]) -> None:
    """Each fixture declares every field, a bound blob, a bound or runtime record and its holds."""
    header = manifest["header"]
    hashes = {entry["label"]: entry["sha256"] for entry in header["sources"]}
    assert len(hashes) == len(header["sources"])
    assert all(HEX.fullmatch(str(digest)) for digest in hashes.values())
    derived, runs = header["derived_blobs"], {"none", *header["script"]["runs"]}
    for label, fixture in manifest["fixtures"].items():
        assert FIELDS <= fixture.keys(), (label, FIELDS - fixture.keys())
        assert {fixture["base_class"], fixture["effective_class"]} <= CLASSES, label
        bound = derived[label]["sha256"] if label in derived else hashes[label]
        assert HEX.fullmatch(str(bound)) and fixture["blob_sha256"] == bound, label
        assert fixture["verified"].split()[0] in runs, label
        record = fixture["record_sha256"]
        assert record == RUNTIME_BINDING or record == hashes[f"{label}-REC"], label
        if "holds" in fixture:
            assert set(fixture["holds"]) <= ROOTS and "holds_include" not in fixture, label
        else:
            assert set(fixture["holds_include"]) | set(fixture["holds_exclude"]) <= ROOTS, label


def check_record(manifest: dict[str, Any], label: str, record: dict[str, Any], reason: str) -> None:
    """A purge record's fields follow from its fixture, its eligibility, the invocation that wrote
    it and that invocation's probes."""
    fixture = manifest["fixtures"][label]
    assert RECORD <= record.keys() and record["reason"] in REASONS, label
    assert (record["class"], record["url"]) == (fixture["base_class"], fixture["url"]), label
    assert record["reason"] == reason, label
    if record["class"] != "EXCHANGE_REFETCHABLE":
        assert record["probe"] == "NOT_REQUIRED", label
        return
    probe = record["probe"]
    writer = manifest["header"]["script"]["purge_runs"][record["run"]]["records_by"]
    assert probe["invocation"] == writer, label
    rows = manifest["probe"]["invocations"][probe["invocation"]]["rows"]
    matched = {manifest["fixtures"][r["label"]]["source"] for r in rows if r["outcome"] == "MATCH"}
    assert probe["latest_match"] == fixture["source"] in matched, label


def check_probes(manifest: dict[str, Any], eligible: set[str]) -> None:
    """Samples are eligible exchange captures; a source halts exactly when one row failed."""
    fixtures = manifest["fixtures"]
    for name, invocation in manifest["probe"]["invocations"].items():
        failed = set()
        for row in invocation["rows"]:
            assert fixtures[row["label"]]["base_class"] == "EXCHANGE_REFETCHABLE", name
            assert row["outcome"] in {"MATCH", "FAILED"} and row["incident"] == (
                row["outcome"] == "FAILED"
            ), name
            if row["outcome"] == "FAILED":
                assert row["category"] and row["severity"] == "HIGH", name
                failed.add(fixtures[row["label"]]["source"])
        assert set(invocation["halted"]) == failed, name
    assert {row["label"] for row in manifest["probe"]["invocations"]["P1"]["rows"]} <= eligible


def check_ledger_stage5(manifest: dict[str, Any]) -> None:
    """Every section and field is present, labels resolve, the dry-run is the eligible set,
    every expired label has a purge record with a valid reason and probe, nothing COVERED is
    eligible, and every licence-ended label ends expired with its record hash."""
    assert SECTIONS <= manifest.keys(), SECTIONS - manifest.keys()
    assert HEADER <= manifest["header"].keys(), HEADER - manifest["header"].keys()
    check_required(manifest)
    check_references(manifest)
    fixtures, runs = manifest["fixtures"], set(manifest["header"]["script"]["runs"])
    check_fixtures(manifest)
    registered = {label for label, fixture in fixtures.items() if "arises" not in fixture}
    at_b = manifest["eligibility"]["at_B"]
    assert at_b.keys() == registered == manifest["purge"]["states"].keys()
    eligible = {label for label, verdict in at_b.items() if verdict["kind"] == "ELIGIBLE"}
    assert all(fixtures[label]["effective_class"] != "COVERED" for label in eligible)
    assert all(at_b[label]["reason"] in REASONS for label in eligible)
    blobs = manifest["dry_run"]["blobs"]
    assert sorted(blob["label"] for blob in blobs) == sorted(eligible)
    for blob in blobs:
        fixture = fixtures[blob["label"]]
        assert (blob["source"], blob["sha256"]) == (fixture["source"], fixture["blob_sha256"])
    check_probes(manifest, eligible)
    purge = manifest["purge"]
    assert set(purge["states"].values()) <= STATES
    expired = {label for label, state in purge["states"].items() if state == "EXPIRED"}
    halted = set(manifest["probe"]["invocations"]["rerun"]["halted"])
    assert expired == {label for label in eligible if fixtures[label]["source"] not in halted}
    assert expired == purge["records"].keys() == set(purge["blobs"]["absent"])
    assert set(purge["blobs"]["present"]) == registered - expired
    for label, record in purge["records"].items():
        check_record(manifest, label, record, at_b[label]["reason"])
    for label, rows in purge["tombstones"]["labels"].items():
        assert label in expired and TOMBSTONE <= rows.keys(), label
    crashed = manifest["recovery"]["after_crash"]
    pending = {label for label, state in crashed["states"].items() if state == "PURGE_PENDING"}
    assert crashed["states"].keys() == registered and pending == expired
    assert set(crashed["blobs_absent"]) == expired
    journal = manifest["backup"]["journal"]
    completed = set().union(*(event["expired"] for event in journal if event["kind"] == "COMPLETE"))
    assert (
        completed == expired == set(manifest["restore"]["pre_purge"]["expired_after_purge_first"])
    )
    check_refetch(manifest, expired)
    check_licence_end(manifest, expired)
    writers = {run["records_by"] for run in manifest["header"]["script"]["purge_runs"].values()}
    assert writers <= manifest["probe"]["invocations"].keys()
    ended = manifest["licence_end"]
    for records, events in ((purge["records"], journal), (ended["records"], ended["journal"])):
        for event in events:
            for label in event.get("expired", []):
                assert records[label]["run"] == event["run"], (label, event["id"])
    replay = manifest["replay"]["runs"]
    assert replay.keys() == runs
    checkpoints = {"at_A", "D1", "D3", "restore_pre_purge", "restore_licence_end"}
    assert all(checkpoints <= result.keys() for result in replay.values())


def check_refetch(manifest: dict[str, Any], expired: set[str]) -> None:
    """Each re-fetch targets an expired exchange label; attempt outcome fixes the command's."""
    commands = {"MATCH": ("RESTORED", 0), "MISMATCH": ("EXPIRED", 3), "FAILED": ("EXPIRED", 2)}
    for label in REFETCHED:
        fetch = manifest["refetch"][label]
        assert label in expired, label
        outcome, command = fetch["attempt"]["outcome"], fetch["command"]
        assert (command["state"], command["exit"]) == commands[outcome], label
        assert (fetch["attempt"]["fetched_sha256"] is None) == (outcome == "FAILED"), label
        if outcome == "MISMATCH":
            new = manifest["fixtures"][command["new_capture"]]
            assert new["blob_sha256"] == fetch["attempt"]["fetched_sha256"], label


def check_licence_end(manifest: dict[str, Any], expired: set[str]) -> None:
    """The licence end expires every licensed label and the re-expired ones, with records."""
    fixtures, ended = manifest["fixtures"], manifest["licence_end"]
    final = {label for label, state in ended["states"].items() if state == "EXPIRED"}
    assert ended["states"].keys() == fixtures.keys()
    licensed = {label for label, fixture in fixtures.items() if fixture["licence"] == "tijori"}
    refetched = manifest["refetch"]
    restored = {label for label in REFETCHED if refetched[label]["command"]["state"] == "RESTORED"}
    newly = (final - expired) | (final & restored)  # a RESTORED capture expires again (R5)
    assert licensed <= final and set(ended["intents"]) == newly
    (complete,) = [event for event in ended["journal"] if event["kind"] == "COMPLETE"]
    assert set(complete["expired"]) == newly == ended["records"].keys()
    after = manifest["eligibility"]["after_licence_end"]
    assert all(after[label]["reason"] == "LICENCE_END" for label in licensed - expired)
    before = manifest["eligibility"]["before_licence_end"]
    for label, record in ended["records"].items():
        check_record(manifest, label, record, (after.get(label) or before[label])["reason"])
    assert set(ended["blobs"]["absent"]) == final
    restored = manifest["restore"]["licence_end"]
    assert set(restored["expired_after_purge_first"]) == final
    assert restored["tijori"].keys() == licensed
    for label in licensed:
        expected = {"state": "EXPIRED", "record_sha256": fixtures[label]["record_sha256"]}
        assert restored["tijori"][label] == expected, label


STAGE5_MUTATIONS: dict[str, Mutation] = {
    "null-record-hash": lambda m: m["fixtures"]["L-TIJ"].update(record_sha256=None),
    "unknown-journal-label": lambda m: m["backup"]["journal"][0]["captures"].append("X-Q9"),
    "missing-section": lambda m: m.pop("refetch"),
    "reason-none": lambda m: m["purge"]["records"]["A-SCR"].update(reason="none"),
    "undeclared-purge-run": lambda m: m["purge"]["records"]["X-Q4"].update(run="P99"),
    "undeclared-preservation-capture": lambda m: m["preservation"]["sets"][
        "non_vendor_occurrences"
    ]["capture_of"].append("X-Q9"),
    "empty-tombstone-labels": lambda m: m["purge"]["tombstones"]["labels"].clear(),
    "empty-preservation": lambda m: m["preservation"].clear(),
    "empty-recovery": lambda m: m["recovery"].clear(),
    "probe-invocation-swap": lambda m: m["purge"]["records"]["X-Q2P"]["probe"].update(
        invocation="P1"
    ),
}
