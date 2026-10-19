"""D2.8: the Stage 2 end-to-end (plan D2, Task 8).

One test runs the D2 operations in their legal order on one ``eqos_test_*`` database and compares
each outcome with the frozen Stage 2 manifest. It orchestrates; the task tests own the internals.
The 8 originals are registered once; the Apar Q2 FY26 run reuses A-X2/A-P2 and no vendor capture.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from evidence_support import CONFIG as EVIDENCE_CONFIG
from evidence_support import Ingest, policy
from ledger_support import COVERAGE_TABLES, IDENTITY_TABLES, LEDGER_TABLES, MEMORY_TABLES
from legacy_support import LEGACY_PATH, LEGACY_SHA256, baseline_rows, file_sha256, second_store
from pg_support import PgTestDatabase, drop_database, mint_name
from prep2b_support import XBRLS, Pilot
from retained_support import APAR_ISSUER_CONFIG, APAR_MANIFEST
from retention_support import RETENTION_TABLES, restore_args
from stage1_e2e_support import CONFIG, RUNS, Stage, row_key
from temporal_fixture_support import install_trusted_fixture_cli
from test_cutover_rollback import Window
from test_frozen_manifests import REPO, load
from test_legacy_import import Rig
from test_store import _fact

import fundamentals.pg.cutover as cutover
from fundamentals.api.cli import main
from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.compare.run import load_results
from fundamentals.contracts.evidence import RunMode
from fundamentals.evidence.admission import admit_run, key_identity, read_selected, select_admitted
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy, load_mapping_set
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.run_draft import RUN_AUTHOR
from fundamentals.pg.approvals import GatedOperation
from fundamentals.pg.backup import restore_backup, verify_set, write_backup
from fundamentals.pg.cutover import FactStoreState, store_status
from fundamentals.store.fact_store import FactStore
from fundamentals.store.pg_fact_store import FactStoreFrozenError, PgFactStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]
__all__ = ["policy"]

MANIFEST = load(REPO / "tests/fundamentals/fixtures/data_foundation/stage2_manifest.yaml")
(STORE,) = MANIFEST["import"]["stores"]
CUTOFFS = [(datetime.fromisoformat(cut["at"]), cut["row_ids"]) for cut in MANIFEST["cutoffs"]]
RESULT_COUNT = 441
# The frozen backup inventory is 0001-0011's; the tables later migrations add, by name (plan D3,
# finding 14). Each migration adding a table extends this in the same reviewed change.
POST_0011_TABLES = (
    LEDGER_TABLES | MEMORY_TABLES | IDENTITY_TABLES | COVERAGE_TABLES | RETENTION_TABLES
)
# The two cells Stage 1 marks not applicable by rule (outside the manifest's 439) and their refusal.
EXCLUDED = {
    "excise_duty|Q|-|REPORTED": "NOT_SINGLE_REPRESENTATION",
    "excise_duty|Y|-|REPORTED": "NOT_SINGLE_REPRESENTATION",
}
ROWS = "SELECT handle, content_identity, value_hash FROM eqos.fact_rows WHERE target_store = %s"
SELECTIONS = (
    "SELECT handle, row_handle, selected_at, selection_sha256, sequence, predecessor_handle, "
    "legacy_baseline, synthesized, reason FROM eqos.fact_selections WHERE target_store = %s"
)
BINDINGS = "SELECT DISTINCT file_sha256 FROM eqos.legacy_evidence_bindings WHERE target_store = %s"
# The Q2 FY26 run's own XBRL and its comparators (YoY, QoQ), evidence-ingested for its draft.
COMPARATORS = tuple(row for row in XBRLS if row[0] in ("FY26_Q2", "FY25_Q2", "FY26_Q1"))
EVENTS = (
    "SELECT state, last_row_handle, last_selection_handle FROM eqos.fact_store_events "
    "WHERE store_id = %s ORDER BY id"
)


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(EVIDENCE_CONFIG / "dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v5: maps the run's comparator XBRLs (PREP-1)."""
    return load_mapping_set(EVIDENCE_CONFIG / "mappings", "v5", dictionary=dictionary)


def imported(rig: Rig, store: str) -> tuple[list[Any], list[Any], set[Any], set[str]]:
    """A store's rows and selections in the manifest's shape, its selection constants and its
    bound file hashes."""
    rows = [
        {"row_id": row[0], "content_identity": row[1], "value_hash": row[2]}
        for row in sorted(rig.query(ROWS, store))
    ]
    selections = sorted(rig.query(SELECTIONS, store))
    shaped = [
        {"selection_id": s[0], "row_id": s[1], "selected_at": s[2], "selection_sha256": s[3]}
        for s in selections
    ]
    constants = {tuple(s[4:]) for s in selections}
    return rows, shaped, constants, {row[0] for row in rig.query(BINDINGS, store)}


def pipeline_config(tmp_path: Path, rig: Rig, store: str) -> Path:
    """The Apar Q2 FY26 config routed to ``store``, with repo-absolute paths."""
    body = yaml.safe_load(APAR_ISSUER_CONFIG.read_text(encoding="utf-8"))
    body["raw_dir"] = str(REPO / body["raw_dir"])
    body["xbrl"]["local_path"] = str(REPO / body["xbrl"]["local_path"])
    for comparator in body["comparators"].values():
        comparator["local_path"] = str(REPO / comparator["local_path"])
    body |= {"store_db": str(rig.legacy), "fact_store_id": store}
    path = tmp_path / "config" / APAR_ISSUER_CONFIG.name
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
    return path


def test_stage2_end_to_end(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    policy: NormalisationPolicy,
) -> None:
    rig = Rig(pg_db, tmp_path)
    constants = STORE["selection_constants"]
    want_constants = (
        constants["sequence"],
        constants["predecessor_id"],
        constants["legacy_baseline"],
        constants["synthesized"],
        constants["reason"],
    )

    # 1-2. Register the 8 originals; preflight, approve and import the copy and second_store.
    window = Window(rig, ("aparinds", rig.legacy), ("aparinds-migrated", second_store(tmp_path)))
    legacy, migrated = window.stores
    assert legacy == STORE["origin_id"] and file_sha256(rig.legacy) == STORE["fingerprint"]
    expected = (STORE["rows"], STORE["selections"])
    assert imported(rig, legacy) == (*expected, {want_constants}, set(MANIFEST["bindings"]))
    assert imported(rig, migrated)[:3] == (
        *expected,
        {(*want_constants[:3], False, constants["reason"])},
    )
    with pg_db.runtime_pool() as pool:
        for store in (legacy, migrated):
            reader = PgFactStore(pool, store)
            for cutoff, row_ids in CUTOFFS:
                assert [row["row_id"] for row in baseline_rows(reader, cutoff)] == row_ids

    # 3. Reconcile (the window approved it).
    assert window.reconciled.equal()
    first_report = window.reconciled.to_yaml()

    # 4. Cutover, then a frozen put persists nothing.
    window.move(GatedOperation.CUTOVER)
    counts = rig.query("SELECT count(*) FROM eqos.fact_rows")
    with pg_db.runtime_pool() as pool, pytest.raises(FactStoreFrozenError):
        PgFactStore(pool, legacy).put(_fact())
    assert rig.query("SELECT count(*) FROM eqos.fact_rows") == counts

    # 5. Rollback; the baseline is read on a further disposable copy, never the routed file.
    window.move(GatedOperation.ROLLBACK)
    disposable = tmp_path / "rolled-back.sqlite"
    shutil.copyfile(rig.legacy, disposable)
    sqlite = FactStore(disposable)
    assert [[r["row_id"] for r in baseline_rows(sqlite, at)] for at, _ in CUTOFFS] == [
        ids for _, ids in CUTOFFS
    ]
    sqlite.close()

    # 6. Reconcile again (byte-equal, so its approval binds), cutover from ROLLED_BACK, reopen.
    with pg_db.runtime_pool() as pool:
        again = cutover.reconcile(window.manifest, root=tmp_path, pool=pool, settings=rig.settings)
    assert again.to_yaml() == first_report
    window.move(GatedOperation.CUTOVER)
    window.move(GatedOperation.REOPEN)
    sequence = MANIFEST["states"]["sequence"]
    states = [step["to"] for step in sequence if "to" in step]
    marker = MANIFEST["states"]["marker"]
    want_marker = (marker["last_row_handle"], marker["last_selection_handle"])
    for store in window.stores:
        events = rig.query(EVENTS, store)
        assert [event[0] for event in events] == states
        cutovers = [event[1:] for event in events if event[0] == FactStoreState.CUTOVER_FROZEN]
        assert cutovers == [want_marker, want_marker]
    with pg_db.runtime_pool() as pool:
        assert store_status(pool, window.stores) == dict.fromkeys(
            window.stores, FactStoreState.OPEN
        )

        # 7. The Apar Q2 FY26 run; admission, selection and the admitted-fact read.
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.first_party()
        run_id = stage.execute(vendors=[]).run_id
        # Cells as Stage 1 projects them: not-applicable-by-rule rows are not manifest cells.
        rules = stage.run["applicability"]["not_applicable_by_rule"].values()
        ruled = {canonical_id for ids in rules for canonical_id in ids}
        actual = {row.row_id: row for row in load_results(run_id, pool=pool)}
        excluded = {
            row_id
            for row_id, row in actual.items()
            if row.key.canonical_id in ruled and row.applicability.value == "NOT_APPLICABLE"
        }
        results = {row_id: row for row_id, row in actual.items() if row_id not in excluded}
        outcome = admit_run(run_id, pool=pool, store_id=legacy)
        # Every actual result gets exactly one outcome; the excluded cells are refused as pinned.
        by_side = {v.interpretation_id: row for row in actual.values() for v in row.source_values}
        outcomes = [row_id for row_id, _ in outcome.refusals]
        outcomes += [by_side[record.interpretation_id].row_id for record in outcome.records]
        assert len(actual) == RESULT_COUNT and sorted(outcomes) == sorted(actual)
        assert {
            row_key(stage.run, actual[row_id]): reason.value
            for row_id, reason in outcome.refusals
            if row_id in excluded
        } == EXCLUDED
        admission = MANIFEST["admission"]
        assert (len(results), len(outcome.records)) == (
            admission["counts"]["cells"],
            admission["counts"]["admitted"],
        )
        refused: dict[str, list[str]] = {}
        for row_id, reason in outcome.refusals:
            if row_id in results:
                refused.setdefault(reason.value, []).append(row_key(stage.run, results[row_id]))
        assert {reason: sorted(keys) for reason, keys in refused.items()} == {
            reason: sorted(keys) for reason, keys in admission["refused"].items()
        }
        store = PgFactStore(pool, legacy)
        read: dict[str, Any] = {}
        for record in outcome.records:
            row = by_side[record.interpretation_id]
            history = store.get_selection_history(key_identity(row.key))
            selected = select_admitted(
                pool,
                store_id=legacy,
                admission_id=record.admission_id,
                reason="stage2 e2e",
                expected_selection_id=history[-1].selection_id if history else 0,
            )
            assert selected.canonical_selected_at is not None
            cutoff = selected.canonical_selected_at + timedelta(microseconds=1)
            fact = read_selected(store, row.key, cutoff=cutoff, mode=RunMode.AS_KNOWN)
            assert fact is not None
            read[row_key(stage.run, row)] = (
                str(fact.value),
                fact.unit,
                fact.provenance.context_ref,
            )
        assert read == {
            item["key"]: (item["value"], item["unit"], item["xbrl"]["ctx"])
            for item in admission["admitted"]
        }

    # 8. Matched backup, then restore with replay into a fresh test database.
    sets = write_backup(
        rig.settings, database=pg_db.dbname, snapshot_root=rig.snapshots, out_dir=tmp_path / "sets"
    )
    backup, written = MANIFEST["backup"], verify_set(sets)
    assert (len(written.captures), len(written.run_ids)) == (backup["captures"], backup["runs"])
    assert sorted(written.table_counts) == sorted([*backup["tables"], *POST_0011_TABLES])
    fresh = mint_name(rig.settings)
    try:
        check = restore_backup(
            sets,
            rig.settings,
            database=fresh,
            snapshot_root=tmp_path / "restored",
            replay_runs=True,
            config_root=CONFIG,
            **restore_args(pg_db, sets, tmp_path / "restored", live=None),
        )
        assert check.ok, check
    finally:
        drop_database(rig.settings, fresh)
    # 9. The pipeline routes through open_fact_store to the OPEN store; no FactStore is built.
    # It writes its earnings update as a DRAFT (PREP-2b Task 6), which needs the sealed imports,
    # the watchlist, the transcript and the comparator XBRLs; set up after the backup, whose
    # frozen counts cover the D2 operations only.
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    install_trusted_fixture_cli(monkeypatch)

    def no_sqlite(*_: object) -> FactStore:
        raise AssertionError("an OPEN store must not construct a SQLite FactStore")

    monkeypatch.setattr(cutover, "FactStore", no_sqlite)
    config, out = pipeline_config(tmp_path, rig, legacy), tmp_path / "run.json"
    with pg_db.runtime_pool() as pool:
        ingest = Ingest(pg_db, EvidenceRepository(pool), tmp_path, dictionary, mapping_set, policy)
        Pilot(pg_db, tmp_path, monkeypatch, ingest, COMPARATORS, rig=rig, transcripts=("FY26_Q2",))
    args = ["--config", str(config), "--out-json", str(out), "--out", str(tmp_path / "run.md")]
    args += ["--retrospective", str(APAR_MANIFEST), "--snapshot-root", str(rig.snapshots)]
    assert main(["run", "--issuer", "APARINDS", "--quarter", "Q2-FY26", *args]) == 0
    (version,) = rig.query("SELECT id FROM eqos.report_versions WHERE author = %s", RUN_AUTHOR)
    assert version
    calculations = {
        calc["label"]: calc["result"]
        for calc in json.loads(out.read_text(encoding="utf-8"))["calculations"]
    }
    markdown = (tmp_path / "run.md").read_text(encoding="utf-8")
    for line in MANIFEST["consumer_report"]:
        if line["line"] in calculations:
            assert calculations[line["line"]] == line.get("rendered", line.get("v"))
        else:
            assert f"| {line['line']} | {line['v']} |" in markdown

    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256


def test_compose_publishes_on_loopback_only() -> None:
    """The live service's static ports entry binds 127.0.0.1 at the configured port."""
    compose = yaml.safe_load((REPO / "compose.yaml").read_text(encoding="utf-8"))
    (port,) = compose["services"]["postgres"]["ports"]
    assert port.startswith("127.0.0.1:${EQOS_PG_PORT")
