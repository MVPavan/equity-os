"""The ledger Stage 5 world (plan D9 Task 9): the frozen manifest's ``header.script`` steps 1-7
in one test database and one ``tmp_path`` snapshot root, and the readers the e2e compares with
the manifest. Retained bytes are copied into ``tmp_path`` (never written under ``data/``); W-CSV
is the bound SYNTHETIC-FORMAT screen export.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from coverage_support import _COMPLETE, _KEYS, _OWNER_ROWS, _RECORD, INSTRUMENTS, coverage
from pg_support import PgTestDatabase
from purge_support import vendor_copy
from retention_support import open_item
from stage1_e2e_support import CONFIG, RUNS, SCREENER, SECTIONS, Stage
from test_evidence_vendor import screener
from test_frozen_manifests import LEDGER5, REPO, load
from test_retention_purge import INTERPS, VENDOR_ROWS
from vendor_retained_support import retained_page, stage_registered

from equity_os.companies.onboarding.discovery import OK, Capture, Request, Response, store_captures
from equity_os.contracts.companies.onboarding import ONBOARDING_VERSIONS, VerificationUnit
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.publication.ledger import DecisionKind, SubjectKind
from equity_os.contracts.sourcing.source_catalog import SCREEN_EXPORT
from equity_os.contracts.storage.retention import OriginalExpiredError
from equity_os.contracts.storage.retention_purge import FetchFailure, FetchFailureCategory
from equity_os.contracts.verification.review_queue import DispositionKind
from equity_os.interface.entry.cli import main
from equity_os.publication.approval import lifecycle
from equity_os.storage.database.settings import PgRole
from equity_os.storage.facts.pg_fact_store import _INSERT_STORE, _OPEN_EVENT
from equity_os.storage.raw_files.snapshot_store import RECORD_FILENAME, SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import admit_run
from equity_os.verification.comparison.run import load_results, replay_run
from equity_os.verification.comparison.run_config import load_run_config
from equity_os.verification.review_queue.queue import record_disposition

M = load(LEDGER5)
FIX: dict[str, dict[str, Any]] = M["fixtures"]
SCRIPT = M["header"]["script"]
DIGESTS = M["header"]["record_digests"]
SOURCES = {entry["label"]: REPO / entry["path"] for entry in M["header"]["sources"]}
TAG = "ledger-stage5-synthetic"  # header.script steps 5: W-CSV's url and the batch tag
STORE_ID = "ledger-stage5"  # steps 7
REASON = "ledger Stage 5 e2e"
TIJORI_FLAG, UPSTOX_FLAG = "tijori/financials", "upstox/income-statement"
QUARTERS = {  # RUN-Q2, RUN-Q4, RUN-Q5 and X-Q1 (steps 2): quarter, members, period end
    "X-Q1": ("FY26_Q1", {Representation.XBRL: "xbrl-consolidated-comparator"}, "2025-06-30"),
    "RUN-Q2": ("FY25_Q2", {Representation.XBRL: "xbrl-consolidated-comparator"}, "2024-09-30"),
    "RUN-Q4": (
        "FY26_Q4",
        {Representation.XBRL: "xbrl-consolidated", Representation.PDF: "results"},
        "2026-03-31",
    ),
    "RUN-Q5": ("FY27_Q1", {Representation.XBRL: "xbrl-consolidated"}, "2026-06-30"),
}
WHERE = {  # preservation set rows (manifest notation) as SQL
    "all": "true",
    f"target_store '{STORE_ID}'": f"target_store = '{STORE_ID}'",
    f"store_id '{STORE_ID}'": f"store_id = '{STORE_ID}'",
}
TOMBSTONE_ROWS = VENDOR_ROWS | {"calculation_trace_operands": INTERPS}
COUNTED = {  # tombstone count keys and their A-05 tables
    "occurrences": "occurrences",
    "interpretations": "interpretations",
    "result_source_values": "result_source_values",
    "extraction_attempts": "acquisition_attempts",
}
CAPTURES = "SELECT id, source_id, surface, request_key, capture_id, blob_sha256, record_sha256, "
CAPTURES += "registered_at, first_seen_at FROM eqos.capture_refs ORDER BY id"
STATE = "SELECT eqos.capture_state(%s)"
ENTITY = (
    "SELECT e.entity_key FROM eqos.capture_entities c JOIN eqos.reporting_entities e "
    "ON e.id = c.entity_id WHERE c.capture_ref_id = %(c)s UNION SELECT e.entity_key "
    "FROM eqos.screen_runs s JOIN eqos.capture_batches b ON b.screen_run_id = s.id "
    "JOIN eqos.batch_member_results m ON m.batch_id = b.id "
    "JOIN eqos.reporting_entities e ON e.id = m.entity_id WHERE s.capture_ref_id = %(c)s"
)
PROBES = "SELECT id, capture_ref_id, source_id, outcome, category, severity FROM "
PROBES += "eqos.retention_probes WHERE id > %s ORDER BY id"
RECORDS = "SELECT id, purge_run_id, capture_ref_id, retention_class, reason, url, blob_sha256, "
RECORDS += "probe_id, purged_at FROM eqos.purge_records ORDER BY id"
INCIDENTS = "SELECT kind, id FROM eqos.retention_incidents ORDER BY kind, id"
EXTRACTION = (
    "SELECT id FROM eqos.acquisition_attempts WHERE stage = 'EXTRACTION' AND capture_ref_id = %s"
)
CREATED = "SELECT created_at FROM eqos.runs WHERE id = %s"
EXPIRED_IDS = re.compile(r"captures \[([\d, ]*)\]")


class World:
    """One test database and snapshot root holding the manifest's captures, runs and seeds."""

    def __init__(self, db: PgTestDatabase, pool: Any, owner: Any, tmp_path: Path) -> None:
        self.db, self.pool, self.owner, self.tmp = db, pool, owner, tmp_path
        self.root, self.sets = tmp_path / "store", tmp_path / "sets"
        self.ids: dict[str, int] = {}  # capture label -> capture_refs.id
        self.records: dict[str, str] = {}  # label -> bound record_sha256
        self.runs: dict[str, int] = {}  # RUN-* -> runs.id
        self.purge_runs: dict[int, str] = {}  # purge_runs.id -> P1, P2, P3
        self.stage: Stage

    def sql(self, query: str, params: Any = None, dbname: str | None = None) -> list[Any]:
        """Rows of one statement as the migrator (or as admin on a restored database)."""
        if dbname is None:
            with self.db.migrator_connection() as conn:
                return conn.execute(query, params).fetchall()
        with psycopg.connect(self.db.settings.conninfo(PgRole.ADMIN, dbname=dbname)) as conn:
            return conn.execute(query, params).fetchall()

    def label(self, capture_ref_id: int) -> str:
        """The fixture label of a capture id."""
        return next(label for label, cid in self.ids.items() if cid == capture_ref_id)

    def bind(self) -> None:
        """Map every registered capture to its label by blob and bind its record hash: the
        canonical-JSON digest, i.e. ``record.json`` without its one trailing LF
        (header.notation.record_sha256); a literal also equals header.record_digests."""
        literals = {k for k, f in FIX.items() if f["record_sha256"] != "RUNTIME_BINDING"}
        assert set(DIGESTS) == literals
        blobs = {fixture["blob_sha256"]: label for label, fixture in FIX.items()}
        for cid, source, surface, key, capture, blob, record, *_ in self.sql(CAPTURES):
            label = blobs[blob]
            assert FIX[label]["source"] == source and FIX[label]["surface"] == surface, label
            data = (self.root / source / surface / key / capture / RECORD_FILENAME).read_bytes()
            assert data.endswith(b"}\n"), label
            assert hashlib.sha256(data.removesuffix(b"\n")).hexdigest() == record, label
            literal = FIX[label]["record_sha256"]
            if literal != "RUNTIME_BINDING":  # copied verbatim
                assert record == literal == DIGESTS[label]["sha256"], label
            self.ids.setdefault(label, cid)
            self.records.setdefault(label, record)
            assert (self.ids[label], self.records[label]) == (cid, record), label

    def states(self, dbname: str | None = None) -> dict[str, str]:
        """Every bound capture's retention state (of those the database registers)."""
        ids = {row[0] for row in self.sql("SELECT id FROM eqos.capture_refs", dbname=dbname)}
        return {
            label: self.sql(STATE, (cid,), dbname)[0][0]
            for label, cid in self.ids.items()
            if cid in ids
        }

    def blobs(self, root: Path | None = None) -> set[str]:
        """The labels whose blob is in the store (``blob_inventory``)."""
        found = {entry.blob_sha256 for entry in SnapshotStore(root or self.root).blob_inventory()}
        return {label for label in self.ids if FIX[label]["blob_sha256"] in found}

    def ref(self, label: str) -> tuple[str, str, str, str]:
        """A capture's store identity."""
        row = next(r for r in self.sql(CAPTURES) if r[0] == self.ids[label])
        return row[1], row[2], row[3], row[4]

    def probes(self, after: int) -> list[tuple[Any, ...]]:
        """Probe rows with ids above ``after``."""
        return self.sql(PROBES, (after,))

    def last_probe(self) -> int:
        """The greatest probe id so far (0 before any)."""
        return int(self.sql("SELECT coalesce(max(id), 0) FROM eqos.retention_probes")[0][0])

    def name_purge_runs(self) -> None:
        """Name the purge runs P1, P2, P3 in id order (header.script.purge_runs)."""
        ids = [row[0] for row in self.sql("SELECT id FROM eqos.purge_runs ORDER BY id")]
        self.purge_runs = {run: f"P{n}" for n, run in enumerate(ids, start=1)}

    def replays(self) -> dict[str, Any]:
        """Each run's direct replay: ``identical`` or ``{ORIGINAL_EXPIRED: labels}``."""
        found: dict[str, Any] = {}
        for name, run in self.runs.items():
            try:
                same = replay_run(run, pool=self.pool, config_root=CONFIG)
                assert same == load_results(run, pool=self.pool), name
                found[name] = "identical"
            except OriginalExpiredError as error:
                match = EXPIRED_IDS.search(str(error))
                assert match, str(error)
                ids = [int(i) for i in match.group(1).split(",") if i.strip()]
                found[name] = {"ORIGINAL_EXPIRED": sorted(self.label(i) for i in ids)}
        return found


def cli(*argv: str) -> tuple[int, str]:
    """``fundamentals <argv>`` in process: exit code and stdout."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def build(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """``header.script`` steps 1-7 at instant A (wall time)."""
    db, pool, root = world.db, world.pool, world.root
    laurus = Stage(db, pool, world.tmp, RUNS["LAURUSLABS-Q3FY25"])  # steps 1: seeds

    def seeded(run: str) -> Stage:
        stage = copy.copy(laurus)  # one tmp root: Stage binds its store to tmp_path
        stage.run, stage.end = RUNS[run], date.fromisoformat(RUNS[run]["period_end"])
        stage.entity_id = stage._seed()
        return stage

    apar, netweb = seeded("APARINDS-Q2FY26"), seeded("NETWEB-Q3FY25")
    # Mapping set v5 reads the 2026-01-31 in-capmkt taxonomy of X-Q4 and X-Q5 (v4 refuses it).
    apar.versions = ONBOARDING_VERSIONS
    apar.config = load_run_config(CONFIG, apar.versions)
    world.stage = apar
    laurus.first_party()  # steps 2: L-X, then the Apar packages
    for quarter, members, end in QUARTERS.values():
        apar.first_party(quarter=quarter, members=members, end=date.fromisoformat(end))
    laurus.vendor(TIJORI_FLAG, vendor_copy(laurus, TIJORI_FLAG, root), store=root)  # steps 3
    request, _, _ = retained_page("APARINDS")
    store = SnapshotStore(root)
    page = stage_registered(request, apar.repository, store)
    for section in SECTIONS:
        adapter = screener("APARINDS", Basis.CONSOLIDATED, section)
        capture = (*SCREENER, page.request_key, page.capture_id)
        apar._ingest(capture, store, adapter, None, Basis.CONSOLIDATED)
    apar.vendor(UPSTOX_FLAG, vendor_copy(apar, UPSTOX_FLAG, root), store=root)
    for flag in (TIJORI_FLAG, UPSTOX_FLAG):
        netweb.vendor(flag, vendor_copy(netweb, flag, root), store=root)
    code, _ = coverage("registry", "--instruments", str(INSTRUMENTS), "--snapshot-root", str(root))
    assert code == 0
    world.runs["RUN-L"] = laurus.execute(vendors=[TIJORI_FLAG]).run_id  # steps 4
    world.runs["RUN-N"] = netweb.execute().run_id
    with monkeypatch.context() as patch:  # header.script.verification_publish
        patch.setattr("equity_os.verification.comparison.run.route_run", lambda *args: ())
        for name in ("RUN-Q2", "RUN-Q4", "RUN-Q5"):
            apar.end = date.fromisoformat(QUARTERS[name][2])
            record = apar.execute(vendors=[])
            assert record.manifest.status.value == "COMPLETE", name
            world.runs[name] = record.run_id
    watchlist(world, laurus.entity_id)  # steps 5
    for (item,) in world.sql(
        "SELECT id FROM eqos.queue_items WHERE run_id = %s ORDER BY id", (world.runs["RUN-L"],)
    ):
        record_disposition(
            world.owner,
            item_id=item,
            kind=DispositionKind.DISMISSED,
            reason=REASON,
            decider="owner",
            evidence_ref="ledger-stage5",
        )
    world.bind()
    ((attempt,),) = world.sql(EXTRACTION, (world.ids["N-TIJ"],))  # steps 6: the R4 edge
    with db.migrator_connection() as conn:
        open_item(conn, world.runs["RUN-N"], attempt_id=attempt)
    with pool.connection() as conn, conn.transaction():  # steps 7
        conn.execute(_INSERT_STORE, (STORE_ID,))
        conn.execute(_OPEN_EVENT, (STORE_ID, "00000000-0000-0000-0000-000000000005"))
    assert admit_run(world.runs["RUN-Q5"], pool=pool, store_id=STORE_ID).created >= 1


def watchlist(world: World, entity_id: int) -> None:
    """Steps 5: W-CSV registered through discovery, coverage_support.batched's runtime and owner
    rows with the fixed tag and RUN-L as the batch result's run, then the owner's ADD."""
    source_id, surface = SCREEN_EXPORT
    export = Capture(
        request=Request(
            unit=VerificationUnit.SCREENER, source_id=source_id, surface=surface, url=TAG
        ),
        response=Response(
            outcome=OK, body=SOURCES["W-CSV"].read_bytes(), retrieved_at=datetime.now(UTC)
        ),
    )
    snapshots = SnapshotStore(world.root)
    with snapshots.prepare_ordinary_output():
        ((_, ref),) = store_captures(snapshots, EvidenceRepository(world.owner), [export])
    with world.pool.connection() as conn, conn.transaction():
        ((isin,),) = conn.execute(
            "SELECT isin FROM eqos.securities WHERE entity_id = %s AND isin IS NOT NULL",
            (entity_id,),
        ).fetchall()
        ((record,),) = conn.execute(_RECORD, (entity_id,)).fetchall()
    ids: dict[str, object] = {"tag": TAG, "isin": isin, "entity": entity_id, "record": record}
    ids |= {"capture": ref.capture_ref_id, "compare": world.runs["RUN-L"]}
    with world.owner.connection() as conn, conn.transaction():
        for key, query in zip(_KEYS, _OWNER_ROWS, strict=True):
            row = conn.execute(query, ids).fetchone()
            ids[key] = None if row is None else row[0]
        conn.execute(_COMPLETE, (ids["batch"],))
    lifecycle.decide(
        world.owner,
        subject_kind=SubjectKind.WATCHLIST,
        subject_id=entity_id,
        kind=DecisionKind.ADD,
        ruling=REASON,
    )


def held_config(tmp_path: Path) -> Path:
    """header.script.config_root: a copy of config/ whose holds list is empty."""
    root = Path(shutil.copytree(CONFIG, tmp_path / "config"))
    (root / "storage/retention/holds.yaml").write_text("manifests: []\n")
    return root


def fetcher(world: World, refetch: bool) -> Any:
    """header.script.fetch_purge / fetch_refetch, by the URL's fixture."""
    by_url = {FIX[label]["url"]: label for label in world.ids}

    def fetch(url: str) -> bytes:
        label = by_url[url]
        if label == "P-Q4" and not refetch:
            raise FetchFailure(FetchFailureCategory.TIMEOUT)
        if label == "X-Q5" and refetch:
            raise FetchFailure(FetchFailureCategory.HTTP_STATUS, 404)
        body = SOURCES[label].read_bytes()
        return body + b"\n" if label == "X-Q4" and refetch else body

    return fetch


def preserved(world: World) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    """Each preservation set's digest (header.notation.digest) and its rows."""
    found = {}
    for name, spec in M["preservation"]["sets"].items():
        if "capture_of" in spec:
            ids = ",".join(str(world.ids[label]) for label in spec["capture_of"])
            where = f"capture_ref_id IN ({ids})"
        else:
            where = WHERE[spec["rows"]]
        query = f"SELECT to_jsonb(t)::text FROM eqos.{spec['table']} t WHERE {where} "
        texts = [row[0] for row in world.sql(query + f"ORDER BY {spec['order']}")]
        found[name] = (digest(texts), [json.loads(text) for text in texts])
    return found


def digest(texts: list[str]) -> str:
    """SHA-256 over the rows' jsonb text joined by LF."""
    return hashlib.sha256("\n".join(texts).encode()).hexdigest()


def tombstone_rows(world: World, labels: list[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Per label, every row each A-05 selection picks for its capture, by id."""
    found: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for label in labels:
        found[label] = {}
        for table, where in TOMBSTONE_ROWS.items():
            query = f"SELECT to_jsonb(t) FROM eqos.{table} t WHERE "
            query += where.format(v=world.ids[label]) + " ORDER BY id"
            found[label][table] = [row[0] for row in world.sql(query)]
    return found
