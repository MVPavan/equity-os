"""D2.8: the Stage 2 end-to-end (plan D2, Task 8).

One test runs the D2 operations in their legal order on one ``eqos_test_*`` database and compares
each outcome with the frozen Stage 2 manifest. It orchestrates; the task tests own the internals.
The 8 originals are registered once; the Apar Q2 FY26 run reuses A-X2/A-P2 and no vendor value
capture. Its reports then carry the vendor summary block (VENDOR-1 P2 Task 5): Apar's retained
concall summary and a synthetic feed page, extracted by a scripted model whose spans are chosen
by offsets at run time; no vendor text is written here or printed.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from evidence_support import CONFIG as EVIDENCE_CONFIG
from evidence_support import Ingest, policy
from ledger_support import (
    COVERAGE_TABLES,
    DOCUMENT_TABLES,
    IDENTITY_TABLES,
    LEDGER_TABLES,
    MEMORY_TABLES,
    REVIEW_TABLES,
    RULING,
    VENDOR_FIRST_TABLES,
)
from legacy_support import LEGACY_PATH, LEGACY_SHA256, baseline_rows, file_sha256, second_store
from pg_support import PgTestDatabase, drop_database, mint_name
from prep2b_support import XBRLS, Pilot
from retained_support import APAR_ISSUER_CONFIG, APAR_MANIFEST
from retention_support import RETENTION_TABLES, record_of, restore_args
from stage1_e2e_support import CONFIG, RUNS, Stage, row_key
from temporal_fixture_support import install_trusted_fixture_cli
from test_cutover_rollback import Window
from test_frozen_manifests import REPO, load
from test_legacy_import import Rig
from test_store import _fact
from test_vendor_surface_claims import (
    RETAINED,
    SCREENER,
    registered_addresses,
    retained_bodies,
    retained_texts,
)
from test_vendor_text_citation import BINDING, SETTINGS, SOURCE, entity, free
from test_vendor_values_store import outcome

import equity_os.storage.facts.cutover as cutover
from equity_os.contracts.measurement.evidence import CaptureReference, RunMode
from equity_os.contracts.publication.ledger import DecisionKind, SubjectKind, VersionState
from equity_os.contracts.sourcing.snapshot import CaptureRecord
from equity_os.extraction.model.vendor_surface_claims import extract_text
from equity_os.extraction.model.vendor_surface_model import ModelReply
from equity_os.extraction.surfaces.vendor_text_readers import read_text
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
)
from equity_os.interface.entry.cli import main
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.mapping import (
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
)
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.citations import resolve_location
from equity_os.publication.checking.numeral_scan import LOCATION_MARKER, has_numeral
from equity_os.publication.drafting.display import content_hash
from equity_os.publication.drafting.run_draft import RUN_AUTHOR
from equity_os.publication.drafting.vendor_summary import VENDOR_SUMMARY, vendor_summary_section
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site
from equity_os.storage.backup.backup import restore_backup, verify_set, write_backup
from equity_os.storage.database.approvals import GatedOperation
from equity_os.storage.facts.cutover import FactStoreState, store_status
from equity_os.storage.facts.fact_store import FactStore
from equity_os.storage.facts.pg_fact_store import FactStoreFrozenError, PgFactStore
from equity_os.storage.raw_files.capture_retention import capture_registration
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store as ledger_store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.storage.records.vendor_values_store import VENDOR_TABLES, VendorValuesStore
from equity_os.verification.admission.admission import (
    AdmissionRefusal,
    admit_run,
    key_identity,
    read_selected,
    select_admitted,
)
from equity_os.verification.admission.vendor_first import filing_admissible
from equity_os.verification.comparison.run import load_results

pytestmark = [pytest.mark.pg, pytest.mark.retained]
__all__ = ["policy"]

MANIFEST = load(REPO / "tests/fundamentals/fixtures/data_foundation/stage2_manifest.yaml")
(STORE,) = MANIFEST["import"]["stores"]
CUTOFFS = [(datetime.fromisoformat(cut["at"]), cut["row_ids"]) for cut in MANIFEST["cutoffs"]]
RESULT_COUNT = 441
# The frozen backup inventory is 0001-0011's; the tables later migrations add, by name (plan D3,
# finding 14). Each migration adding a table extends this in the same reviewed change.
POST_0011_TABLES = (
    LEDGER_TABLES
    | MEMORY_TABLES
    | IDENTITY_TABLES
    | COVERAGE_TABLES
    | RETENTION_TABLES
    | REVIEW_TABLES
    | DOCUMENT_TABLES
    | VENDOR_FIRST_TABLES
    | VENDOR_TABLES
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
LATEST = "SELECT max(id) FROM eqos.report_versions WHERE author = %s"
_RUN = yaml.safe_load(APAR_ISSUER_CONFIG.read_text(encoding="utf-8"))
SOURCE_CUTOFF = datetime.fromisoformat(_RUN["quarter"]["knowledge_cutoff"])
# Apar's feed item shows a valid claim key (so it is never eligible); the other issuer's does not.
FEED = (
    '<div class="announcement-item"><a href="/company/APARINDS/">A</a>'
    '<a href="/doc">Order {{c:fact.revenue|}} won</a></div>'
    '<div class="announcement-item"><a href="/company/OTHERCO/">B</a>'
    '<a href="/doc">Plant opens</a></div>'
)
FEED_URL = SCREENER + "/announcements/"
PERIOD = re.compile(r"\b\d{4}-\d{2}-\d{2}|\bFY\d{2,4}|\b[QH][1-4]\b")
HEADING = "### Screener — concall-summary, captured {day} — vendor summary — guidance, not evidence"


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(EVIDENCE_CONFIG / "normalisation/dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v5: maps the run's comparator XBRLs (PREP-1)."""
    return load_mapping_set(EVIDENCE_CONFIG / "normalisation/mappings", "v5", dictionary=dictionary)


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


class VendorText:
    """Apar's and another issuer's vendor text, registered as held by the run's source cutoff
    (the fixture's stand-in for an earlier capture) and extracted by a scripted model. Each span
    is a ``CLAIM`` row chosen by offsets: ``marker`` (Apar's feed item, holding a claim key),
    ``other`` (the other issuer's item); after ``concall``, ``claim`` (numeral-free), ``digit``,
    ``word`` (a number word) and ``period`` (a date or period label) in the concall summary."""

    def __init__(self, pool: Any, snapshots: Path, entity_id: int) -> None:
        self.store = SnapshotStore(snapshots)
        self.spans: dict[str, tuple[CaptureReference, int, int, str]] = {}
        self.replies: dict[str, list[dict[str, Any]]] = {}
        *_, (key, capture, page) = retained_bodies("company-page")
        company_id, _ = read_identity(parse_document(page.decode()))
        page_ref = self._retained(pool, "company-page", key, capture)
        body = FEED.encode()
        record = record_of(body, SOURCE, "vs.announcements-feed")
        self.store.put_capture(record, body)
        feed = self._register(pool, record, FEED_URL)
        read = read_text(Site.SCREENER, "announcements-feed", body, FEED_URL)
        apar, other = read.items
        words = [m.span() for m in re.finditer(r"\S+", read.text) if m.end() <= apar.end]
        self._span("marker", feed, read.text, words[0][0], words[-1][1])
        self._span("other", feed, read.text, *free(read.text, other.start, other.end))
        assert "{{c:" in self.spans["marker"][3]
        stub = record_of(b"other", SOURCE, "vs.company-page")
        stub_ref = self._register(pool, stub, f"{SCREENER}/company/OTHERCO/")
        with pool.connection() as conn:
            self.other = entity(conn, "OTHER", entity_id)
            conn.execute(BINDING, (entity_id, "CONSOLIDATED", company_id, page_ref.capture_ref_id))
            conn.execute(
                BINDING, (self.other, "CONSOLIDATED", 999_999_999, stub_ref.capture_ref_id)
            )
        self._extract(pool, feed, "announcements-feed")

    def concall(self, pool: Any) -> None:
        """Register and extract Apar's first retained concall summary with text."""
        key, capture, read = next(
            (k, c, r) for k, c, r in retained_texts("concall-summary") if r.text
        )
        ref, text = self._retained(pool, "concall-summary", key, capture), read.text
        tokens = list(re.finditer(r"\S+", text))
        self._span("claim", ref, text, *free(text, 0, len(text)))
        period = next(m for m in tokens if PERIOD.search(m.group()))
        digits = (m for m in tokens if m is not period and not PERIOD.search(m.group()))
        digit = next(m for m in digits if any(c.isnumeric() for c in m.group()))
        word = next(
            m
            for m in tokens
            if has_numeral(m.group()) and not any(c.isnumeric() for c in m.group())
        )
        for role, found in (("period", period), ("digit", digit), ("word", word)):
            self._span(role, ref, text, *found.span())
        self._extract(pool, ref, "concall-summary")

    def marker(self, role: str) -> tuple[str, str]:
        """A span's location marker parts."""
        ref, start, end, _ = self.spans[role]
        return str(ref.capture_ref_id), f"vt:{start}-{end}:{ref.blob_sha256}"

    def paragraph(self, role: str) -> str:
        """A span's paragraph as the block shows it."""
        capture, anchor = self.marker(role)
        text = " ".join(self.spans[role][3].split())
        return f"{{{{e:inferred}}}} {text} {{{{s:{capture}|{anchor}}}}}"

    def _retained(self, pool: Any, surface: str, key: str, capture: str) -> CaptureReference:
        """One retained Apar capture copied into the run's store and registered."""
        record = SnapshotStore(RETAINED.parent).get_capture(SOURCE, f"vs.{surface}", key, capture)
        self.store.put_capture(record, SnapshotStore(RETAINED.parent).read_body(record))
        return self._register(pool, record, registered_addresses()[key])

    def _register(self, pool: Any, record: CaptureRecord, url: str) -> CaptureReference:
        """Register a capture as registered and first seen at the run's source cutoff."""
        assert record.body is not None
        with capture_registration(pool) as registration:
            return registration.insert(
                CaptureReference(
                    capture_ref_id=None,
                    source_id=record.request.source_id,
                    surface=record.request.surface,
                    request_key=record.request.request_key,
                    capture_id=record.capture_id,
                    blob_sha256=record.body.content_sha256,
                    record_sha256=record.record_sha256,
                    registered_at=SOURCE_CUTOFF,
                    first_seen_at=SOURCE_CUTOFF,
                ),
                url=url,
            )

    def _span(self, role: str, ref: CaptureReference, text: str, start: int, end: int) -> None:
        """Script one ``CLAIM`` selection."""
        self.spans[role] = (ref, start, end, text[start:end])
        self.replies.setdefault(text, []).append({"kind": "CLAIM", "start": start, "end": end})

    def _extract(self, pool: Any, ref: CaptureReference, surface: str) -> None:
        """``extract_text`` over the one new capture, with the scripted replies."""
        values = VendorValuesStore(pool)
        values.record(ref, outcome(version="kept.v1", surface=surface, values=()), row_count=0)

        def complete(system: str, source: str) -> ModelReply:
            reply = json.dumps(self.replies.get(source, []))
            return ModelReply(text=reply, input_tokens=1, output_tokens=1)

        model = Mock(model_id="fake", complete=Mock(side_effect=complete))
        assert extract_text(pool, self.store, model, SETTINGS) == 1


def vendor_block(pilot: Pilot, version_id: int) -> str | None:
    """The version's vendor summary body, if it has one."""
    bodies = {s.section_key: s.body for s in pilot.version(version_id).sections}
    return bodies.get(VENDOR_SUMMARY)


def latest(pilot: Pilot) -> int:
    """The latest run draft."""
    ((version_id,),) = pilot.query(LATEST, RUN_AUTHOR)
    return int(version_id)


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
        # The manifest names first-party reasons (reading 4): a failed filing's detail; for a
        # cell the filing does not hold (row 6), or one an open item now refuses first (row 0a),
        # the first-party rule's own failure, which the pre-VENDOR-1 order checked first.
        failures = dict(outcome.filing_failures)
        first_party = (AdmissionRefusal.VENDOR_UNMAPPED, AdmissionRefusal.REVIEW_OPEN)
        reasons = {
            row_id: failures.get(row_id)
            or (filing_admissible(actual[row_id], {}, {}) if refusal in first_party else refusal)
            for row_id, refusal in outcome.refusals
        }
        by_side = {v.interpretation_id: row for row in actual.values() for v in row.source_values}
        outcomes = list(reasons)
        outcomes += [by_side[record.interpretation_id].row_id for record in outcome.records]
        assert len(actual) == RESULT_COUNT and sorted(outcomes) == sorted(actual)
        assert {
            row_key(stage.run, actual[row_id]): reason.value
            for row_id, reason in reasons.items()
            if row_id in excluded
        } == EXCLUDED
        admission = MANIFEST["admission"]
        assert (len(results), len(outcome.records)) == (
            admission["counts"]["cells"],
            admission["counts"]["admitted"],
        )
        refused: dict[str, list[str]] = {}
        for row_id, reason in reasons.items():
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
            fact = read_selected(store, row.key, cutoff=cutoff, mode=RunMode.AS_KNOWN, pool=pool)
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
    # the watchlist, the transcript, the comparator XBRLs and the quarter's comparison run (its
    # facts are admitted from it); set up after the backup, whose frozen counts cover the D2
    # operations only.
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    install_trusted_fixture_cli(monkeypatch)

    def no_sqlite(*_: object) -> FactStore:
        raise AssertionError("an OPEN store must not construct a SQLite FactStore")

    monkeypatch.setattr(cutover, "FactStore", no_sqlite)
    config, out = pipeline_config(tmp_path, rig, legacy), tmp_path / "run.json"
    with pg_db.runtime_pool() as pool:
        ingest = Ingest(pg_db, EvidenceRepository(pool), tmp_path, dictionary, mapping_set, policy)
        pilot = Pilot(
            pg_db, tmp_path, monkeypatch, ingest, COMPARATORS, rig=rig, transcripts=("FY26_Q2",)
        )
    args = ["run", "--issuer", "APARINDS", "--quarter", "Q2-FY26", "--config", str(config)]
    args += ["--compare-run", str(pilot.compare_run("FY26_Q2"))]
    args += ["--retrospective", str(APAR_MANIFEST), "--snapshot-root", str(rig.snapshots)]

    def run(name: str) -> int:
        """The quarter's ``run``, writing its artifacts under ``name``."""
        outs = ["--out-json", str(tmp_path / f"{name}.json"), "--out", str(tmp_path / f"{name}.md")]
        return main([*args, *outs])

    with pg_db.runtime_pool() as pool:
        vendor = VendorText(pool, rig.snapshots, pilot.entity_id)
    assert run("run") == 0
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

    # 10. The vendor summary block (VENDOR-1 P2 Task 5). Another issuer's span exists, and Apar's
    # only span shows a claim key, so Apar's report has no vendor section; it seals.
    (version_id,) = version
    assert vendor_block(pilot, version_id) is None
    with pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        assert vendor_summary_section(
            cursor,
            entity_id=vendor.other,
            source_cutoff=SOURCE_CUTOFF,
            knowledge_cutoff=EvidenceRepository(pool).store_clock(),
            snapshots=pilot.snapshots,
        )
    pilot.approve(version_id)
    # With the concall summary, the next run shows only its numeral-free span, under its heading.
    with pg_db.runtime_pool() as pool:
        vendor.concall(pool)
    assert run("vendor") == 0
    drafted = latest(pilot)
    block = vendor_block(pilot, drafted)
    assert block is not None
    assert pilot.validate(drafted).version_states == ()  # the draft validates AS_KNOWN
    heading = HEADING.format(day=SOURCE_CUTOFF.date())
    shown = heading in block and vendor.paragraph("claim") in block
    assert shown, "the numeral-free span is not under its heading"  # never printed
    assert LOCATION_MARKER.findall(block) == [vendor.marker("claim")]
    # Rejecting a results claim reworks it; the block is regenerated, the same, and seals.
    with pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, drafted, **pilot.sources())
    with pg_db.owner_pool() as owner:
        lifecycle.decide(
            owner,
            subject_kind=SubjectKind.REPORT_VERSION,
            subject_id=drafted,
            kind=DecisionKind.REQUEST_CHANGES,
            ruling=RULING,
            claims=("fact.revenue",),
        )
    assert run("rework") == 0
    reworked = latest(pilot)
    same = reworked != drafted and vendor_block(pilot, reworked) == block
    assert same, "the rework did not regenerate the same vendor section"
    pilot.approve(reworked)
    sealed = pilot.version(reworked)
    assert sealed.source_cutoff == SOURCE_CUTOFF
    # A revision adding the number-word, period or claim-key span, each with its valid marker,
    # fails checking and sealing: the span does not resolve (the vendor citation refusal).
    added = "".join(vendor.paragraph(role) + "\n\n" for role in ("word", "period", "marker"))
    sections = tuple(
        s.model_copy(update={"body": s.body + added}) if s.section_key == VENDOR_SUMMARY else s
        for s in sealed.sections
    )
    revised = sealed.model_copy(
        update={
            "predecessor_id": reworked,
            "sections": sections,
            "content_hash": content_hash(sections, sealed.claims),
        }
    )
    with pg_db.runtime_pool() as pool, pool.connection() as conn, conn.cursor() as cursor:
        revision = ledger_store.create_version(cursor, revised)
        resolved = {
            role: resolve_location(
                cursor,
                *vendor.marker(role),
                entity_id=pilot.entity_id,
                cutoff=sealed.knowledge_cutoff,
                catalog=pilot.catalog,
                snapshots=pilot.snapshots,
                source_cutoff=sealed.source_cutoff,
            )
            for role in ("claim", "word", "period", "marker")
        }
    assert resolved == {"claim": True, "word": False, "period": False, "marker": False}
    assert VersionState.UNCITED_PROSE in pilot.validate(revision).version_states
    with pg_db.runtime_pool() as runtime, pytest.raises(DecisionRefusedError, match="UNCITED"):
        lifecycle.submit(runtime, revision, **pilot.sources())

    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256


def test_compose_publishes_on_loopback_only() -> None:
    """The live service's static ports entry binds 127.0.0.1 at the configured port."""
    compose = yaml.safe_load((REPO / "compose.yaml").read_text(encoding="utf-8"))
    (port,) = compose["services"]["postgres"]["ports"]
    assert port.startswith("127.0.0.1:${EQOS_PG_PORT")
