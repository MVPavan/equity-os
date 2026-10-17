"""D4.5: the ledger Stage 2 end-to-end (plan D4, Task 5; M8, M9), the D4 exit.

One ``eqos_test_*`` database holds the ledger Stage 1 state (Stage 1 captures and run, the D2
legacy import, ``ledger import`` as the panel). Staging the cables EBITDA-margin
``MANAGEMENT_TRACK_RECORD`` from the imported ``HISTORICAL`` quote claims is refused. Both
transcripts are admitted; one corrective successor per quarter cites its transcript capture,
binds its guidance contract from the sealed management ledger (M9, no contract passed in) and is
approved by the panel on its own ``AS_KNOWN`` check. The item is staged on the two corrective
claims and retrieved only after a panel ``PROMOTE``. The frozen ledger Stage 2 manifest is the
only source of expected values; the fake reviewer only returns a verdict.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from ledger_support import COVERAGE_TABLES, IDENTITY_TABLES
from pg_support import PgTestDatabase
from psycopg import errors
from retained_support import apar_store
from stage1_e2e_support import RUNS, Stage
from test_frozen_manifests import LEDGER, LEDGER2, REPO, load
from test_ledger_import import CONFIG as IMPORT_CONFIG
from test_ledger_panel import FakeReviewer
from test_ledger_stage1_e2e import DECIMALS, PROVENANCE, STAGE2, differences, stored_claim
from test_legacy_import import Rig
from test_memory_promotion import REFUSED
from test_transcript_admission import issuer_config, transcript_intake

from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST, ledger_catalog
from fundamentals.api.screener_cli_dispatch import EXIT_OK
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    ClaimState,
    DecisionKind,
    GuidanceContract,
    NumericClaim,
    ReportKind,
    ReportSection,
    SubjectKind,
    VersionDraft,
    VersionStatus,
)
from fundamentals.contracts.memory import (
    MemoryItemDraft,
    MemoryKind,
    MemoryStatus,
    SupportDraft,
    SupportTarget,
)
from fundamentals.evidence.first_party_ingest import admit_transcript
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle, panel, store
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.import_mapping import UPDATE_FILES
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.memory.store import MemoryStore
from fundamentals.pg.backup import verify_set, write_backup
from fundamentals.store.snapshot_store import SnapshotStore

MANIFEST = load(LEDGER2)
SOURCES = {source["label"]: source for source in MANIFEST["header"]["sources"]}
CONTRACT_FIELDS = tuple(GuidanceContract.model_fields)
_VERSION = (
    "SELECT v.id, v.report_id FROM eqos.reports r JOIN eqos.report_versions v "
    "ON v.report_id = r.id WHERE r.period = %s AND r.kind = %s AND v.predecessor_id IS NULL"
)
_DECISION_KINDS = (
    "SELECT kind FROM eqos.decisions WHERE subject_kind = 'REPORT_VERSION' AND subject_id = %s "
    "ORDER BY sequence"
)
_VALIDATION = "SELECT mode, creator FROM eqos.validations WHERE id = %s"
_BEFORE = "SELECT recorded_at - interval '1 microsecond' FROM eqos.{} WHERE id = %s"
_NOW = "SELECT eqos.store_now()"
_CLAIM_ID = "SELECT id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = %s"


def expected_claim(claim: dict[str, Any]) -> dict[str, Any]:
    """A manifest claim in :func:`stored_claim`'s shape: provenance and the capture label
    dropped, nulls dropped, bounds as ``Decimal``."""
    shaped = {k: v for k, v in claim.items() if k not in PROVENANCE | {"capture"} and v is not None}
    return shaped | {k: Decimal(shaped[k]) for k in DECIMALS if k in shaped}


def contract_of(claim: dict[str, Any]) -> dict[str, Any]:
    """The manifest claim's five guidance-contract fields."""
    return {field: claim[field] for field in CONTRACT_FIELDS}


def flipped(ledger: bytes) -> bytes:
    """A management ledger with every entry's constant_currency negated."""
    book = json.loads(ledger)
    for entry in book["entries"]:
        entry["constant_currency"] = not entry["constant_currency"]
    return json.dumps(book).encode()


def section(claim: NumericClaim) -> ReportSection:
    """The corrective's one management-ledger section: labelled, the quote by placeholder, no
    bare numeral."""
    body = (
        f"{{{{e:forecast}}}} Management guided its annual cables EBITDA margin "
        f"{{{{c:{claim.claim_key}|quote}}}}.\n"
    )
    return ReportSection(ordinal=0, section_key=claim.section_key, body=body)


def successor(predecessor: tuple[int, int], claim: NumericClaim, cutoff: datetime) -> VersionDraft:
    """A corrective successor of the imported version carrying the one quote claim."""
    sections = (section(claim),)
    return VersionDraft(
        report_id=predecessor[1],
        predecessor_id=predecessor[0],
        author=MANIFEST["versions"][0]["author"],
        knowledge_cutoff=cutoff,
        content_hash=content_hash(sections, (claim,)),
        sections=sections,
        claims=(claim,),
    )


class Stage2(NamedTuple):
    """The ledger Stage 2 state's handles and ids, valid while its pools are open."""

    rig: Rig
    entity_id: int
    memory: MemoryStore
    item_id: int
    promotion_id: int
    correctives: dict[str, int]
    claim_ids: dict[str, int]
    captures: dict[str, int]
    cutoffs: dict[str | None, datetime | None]
    check_retrievals: Callable[[str], None]


@contextmanager
def stage2_state(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Stage2]:
    """Build the ledger Stage 2 state through the panel ``PROMOTE``, checking each step, and
    yield its ids with its pools open."""
    # 1. The ledger Stage 1 state: Stage 1 captures and run, legacy import, ``ledger import``.
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    catalog = ledger_catalog(
        DEFAULT_WATCHLIST, "APARINDS", [issuer_config(v["id"]) for v in MANIFEST["versions"]]
    )
    paths = {"catalog": catalog, "snapshots": SnapshotStore(rig.snapshots)}
    item_spec = MANIFEST["item"]
    with pg_db.runtime_pool() as runtime, pg_db.panel_pool() as panel_pool:
        stage = Stage(pg_db, runtime, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.first_party()
        stage.execute(vendors=[])
        command = ["ledger", "import", "--config", str(IMPORT_CONFIG), "--repo", str(REPO)]
        assert main([*command, "--snapshot-root", str(rig.snapshots)]) == EXIT_OK
        ((entity_id,),) = rig.query(
            "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s", item_spec["stock"]
        )
        stocks = {item_spec["stock"]: entity_id}
        memory: MemoryStore = PgMemoryStore(runtime)

        def draft(supports: tuple[int, ...]) -> MemoryItemDraft:
            """The manifest's item on claim supports."""
            return MemoryItemDraft(
                entity_id=stocks[item_spec["stock"]],
                kind=MemoryKind(item_spec["kind"]),
                statement=item_spec["statement"],
                epistemic_class=EpistemicClass(item_spec["epistemic_class"]),
                valid_from=date.fromisoformat(item_spec["valid_from"]),
                valid_to=item_spec["valid_to"],
                supersedes_item_id=item_spec["supersedes"],
                supports=tuple(
                    SupportDraft(target=SupportTarget.CLAIM, target_id=claim_id)
                    for claim_id in supports
                ),
            )

        imported: dict[str, tuple[int, int]] = {}
        imported_claims: dict[str, NumericClaim] = {}
        with runtime.connection() as conn:
            for version in MANIFEST["versions"]:
                report = version["report"]
                ((version_id, report_id),) = rig.query(_VERSION, report["period"], report["kind"])
                imported[version["id"]] = (version_id, report_id)
                (claim_spec,) = version["claims"]
                (imported_claims[version["id"]],) = (
                    c
                    for c in store.read_version(conn.cursor(), version_id).claims
                    if c.claim_key == claim_spec["key"]
                )
                status = lifecycle.version_status(conn.cursor(), version_id)
                assert status is VersionStatus(version["predecessor"]["status_before"])

        # 2. Staging from the imported HISTORICAL quote claims is refused.
        (refusal,) = MANIFEST["refusals"]
        assert refusal["expect"] == "REFUSED"
        historical = [s["imported"] for s in refusal["supports"]]
        assert [imported_claims[name].claim_key for name in historical] == [
            s["claim"] for s in refusal["supports"]
        ]
        assert refusal["kind"] == item_spec["kind"] and refusal["statement"] == "as item"
        with pytest.raises(errors.CheckViolation, match=REFUSED):
            memory.stage(
                draft(
                    tuple(
                        rig.query(_CLAIM_ID, imported[n][0], imported_claims[n].claim_key)[0][0]
                        for n in historical
                    )
                )
            )
        assert rig.query("SELECT count(*) FROM eqos.memory_items") == [(0,)]

        # 3. Both transcripts admitted under their issuer configs.
        repository = EvidenceRepository(runtime)
        captures = {}
        for version in MANIFEST["versions"]:
            (claim_spec,) = version["claims"]
            intake = transcript_intake(tmp_path, version["id"])
            ref = admit_transcript(repository, apar_store(tmp_path), intake, catalog=catalog)
            ((blob,),) = rig.query(
                "SELECT blob_sha256 FROM eqos.capture_refs WHERE id = %s", ref.capture_ref_id
            )
            assert blob == SOURCES[claim_spec["capture"]]["sha256"] == claim_spec["source_sha256"]
            captures[version["id"]] = ref.capture_ref_id

        def corrective(name: str, **contract: Any) -> NumericClaim:
            """The imported quote claim cited to its transcript capture, contract replaced."""
            claim = imported_claims[name]
            citation = claim.citation.model_copy(update={"capture_ref_id": captures[name]})
            update = {"citation": citation, "unresolved": False} | contract
            return claim.model_copy(update=update)

        # 3a. M9 on real bytes (FY26_Q3): a wrong or absent contract never binds as MATCH.
        first = MANIFEST["versions"][0]
        cutoff = datetime.fromisoformat(first["cutoff"]["instant"])
        variants = {
            "metric": ({"metric": "cables_revenue_growth"}, ClaimState.QUOTE_MEANING_MISMATCH),
            "horizon": ({"horizon": "quarterly"}, ClaimState.QUOTE_MEANING_MISMATCH),
            "scope": ({"scope": "standalone"}, ClaimState.QUOTE_MEANING_MISMATCH),
            "all-null": (dict.fromkeys(CONTRACT_FIELDS), ClaimState.QUOTE_MEANING_MISMATCH),
            "as-copied": ({}, ClaimState(first["claims"][0]["state"])),
        }
        for name, (contract, expected) in variants.items():
            claim = corrective(first["id"], **contract)
            with runtime.connection() as conn, conn.transaction(force_rollback=True):
                cursor = conn.cursor()
                version_id = store.create_version(
                    cursor, successor(imported[first["id"]], claim, cutoff)
                )
                ((now,),) = cursor.execute(_NOW).fetchall()
                checked = lifecycle.check_version(
                    cursor, version_id, mode=RunMode.AS_KNOWN, boundary=now, **paths
                )
            assert checked.claim_states == ((claim.claim_key, expected),), name

        # 3a'. A rival sealed import binding the quote the other constant_currency leaves no
        # unique contract, so even an all-null drafted contract fails closed.
        claim = corrective(first["id"], **dict.fromkeys(CONTRACT_FIELDS))
        with panel_pool.connection() as conn, conn.transaction(force_rollback=True):
            cursor = conn.cursor()
            source = store.read_version(cursor, imported[first["id"]][0])
            rival_report = store.create_report(
                cursor,
                entity_id=entity_id,
                period="FY99_Q1",
                kind=ReportKind(first["report"]["kind"]),
            )
            rival = store.create_version(
                cursor,
                source.model_copy(
                    update={
                        "report_id": rival_report,
                        "import_sources": tuple(
                            (path, body if Path(path).name in UPDATE_FILES else flipped(body))
                            for path, body in source.import_sources
                        ),
                    }
                ),
            )
            store.insert_decision(
                cursor,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=rival,
                kind=DecisionKind.IMPORT_SEAL,
                predecessor_id=None,
                sealed_digest=store.sealed_digest(cursor, rival),
            )
            version_id = store.create_version(
                cursor, successor(imported[first["id"]], claim, cutoff)
            )
            ((now,),) = cursor.execute(_NOW).fetchall()
            checked = lifecycle.check_version(
                cursor, version_id, mode=RunMode.AS_KNOWN, boundary=now, **paths
            )
        assert checked.claim_states == ((claim.claim_key, ClaimState.QUOTE_MEANING_MISMATCH),)

        # 3b. One corrective per quarter, submitted and approved by the panel.
        correctives: dict[str, int] = {}
        for version in MANIFEST["versions"]:
            (claim_spec,) = version["claims"]
            claim = corrective(version["id"])
            cutoff = datetime.fromisoformat(version["cutoff"]["instant"])
            assert cutoff.date() == date.fromisoformat(version["cutoff"]["date"])
            assert datetime.fromisoformat(version["cutoff"]["first_seen"]) < cutoff
            with runtime.connection() as conn, conn.transaction():
                version_id = store.create_version(
                    conn.cursor(), successor(imported[version["id"]], claim, cutoff)
                )
            correctives[version["id"]] = version_id
            lifecycle.submit(runtime, version_id, **paths)
            approval = panel.review(
                panel_pool,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=version_id,
                reviewer=FakeReviewer(),
                **paths,
            )
            assert approval.kind is DecisionKind.APPROVE
            mode, creator = version["validation"]["mode"], version["validation"]["creator"]
            assert rig.query(_VALIDATION, approval.validation_id) == [(mode, creator)]
            with runtime.connection() as conn:
                cursor = conn.cursor()
                validation = store.latest_validation(cursor, version_id)
                assert validation is not None and validation.id == approval.validation_id
                (stored,) = store.read_version(cursor, version_id).claims
                assert stored.citation.capture_ref_id == captures[version["id"]]
                states = dict(validation.claim_states)
                shaped = stored_claim(rig, stored, states[stored.claim_key])
                assert differences(expected_claim(claim_spec), shaped) == [], version["id"]
                status = lifecycle.version_status(cursor, version_id)
                assert status is VersionStatus(version["status"])
                prior = lifecycle.version_status(cursor, imported[version["id"]][0])
                assert prior is VersionStatus(version["predecessor"]["status_after"])
            assert [k for (k,) in rig.query(_DECISION_KINDS, version_id)] == version["decisions"]

        # 4. Staged as runtime on the two corrective claims: a candidate, not yet promoted.
        claim_ids = {
            s["version"]: rig.query(_CLAIM_ID, correctives[s["version"]], s["claim"])[0][0]
            for s in item_spec["supports"]
        }
        item_id = memory.stage(draft(tuple(claim_ids.values())))
        promoted_store: MemoryStore = PgMemoryStore(panel_pool)
        cutoffs: dict[str | None, datetime | None] = {None: None}

        def check_retrievals(after: str) -> None:
            """Every manifest retrieval at the ``after`` lifecycle point (at least one)."""
            selected = [r for r in MANIFEST["retrievals"] if r["after"] == after]
            assert selected, after
            for retrieval in selected:
                found = memory.retrieve(
                    retrieval["query"],
                    stock=stocks[retrieval["stock"]],
                    kinds=None,
                    statuses=frozenset(MemoryStatus(s) for s in retrieval["statuses"]),
                    cutoff=cutoffs[retrieval["cutoff"]],
                )
                expected = [
                    (item_id, MemoryStatus(e["status"]), e["needs_revalidation"])
                    for e in retrieval["expect"]
                ]
                assert [(i.id, i.status, i.needs_revalidation) for i in found] == expected, (
                    retrieval
                )

        check_retrievals("stage")

        # 5. The panel PROMOTE; its reviewer reads the resolved quotes and bound contracts.
        reviewer = FakeReviewer()
        promotion = promoted_store.decide(item_id, DecisionKind.PROMOTE, reviewer=reviewer)
        assert promotion.kind is DecisionKind.PROMOTE
        ((text, _),) = reviewer.calls
        shown = json.loads(text)
        assert shown["item"]["statement"] == item_spec["statement"]
        specs = {v["id"]: v["claims"][0] for v in MANIFEST["versions"]}
        for support, payload in zip(item_spec["supports"], shown["supports"], strict=True):
            spec = specs[support["version"]]
            assert payload["citation"]["quote"] == spec["quote"]
            assert payload["citation"]["anchor"] == spec["anchor"]
            assert (payload["lower_bound"], payload["upper_bound"]) == (spec["lo"], spec["hi"])
            assert payload["blob_sha256"] == spec["source_sha256"]
            assert payload["bound_contract"] == payload["contract"] == contract_of(spec)
            bound = {b["source_sha256"] for b in payload["bindings"]}
            assert bound == {SOURCES["MLEDGER"]["sha256"]}
        yield Stage2(
            rig,
            entity_id,
            memory,
            item_id,
            promotion.id,
            correctives,
            claim_ids,
            captures,
            cutoffs,
            check_retrievals,
        )


@pytest.mark.pg
@pytest.mark.retained
def test_ledger_stage2_end_to_end(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item_spec = MANIFEST["item"]
    specs = {v["id"]: v["claims"][0] for v in MANIFEST["versions"]}
    with stage2_state(pg_db, tmp_path, monkeypatch) as built:
        (
            rig,
            entity_id,
            memory,
            item_id,
            promotion_id,
            correctives,
            claim_ids,
            captures,
            cutoffs,
            check_retrievals,
        ) = built

        # 6. Retrieved after PROMOTE with its supports and provenance; absent before it.
        table = {
            "before-promote": ("decisions", promotion_id),
            "before-item": ("memory_items", item_id),
        }
        for name, (source, row_id) in table.items():
            ((cutoffs[name],),) = rig.query(_BEFORE.format(source), row_id)
        check_retrievals("promote")
        (item,) = memory.retrieve(
            "cables margin",
            stock=entity_id,
            kinds=None,
            statuses=frozenset({MemoryStatus.PROMOTED}),
            cutoff=None,
        )
        assert (item.kind, item.statement, item.valid_from, item.valid_to) == (
            MemoryKind(item_spec["kind"]),
            item_spec["statement"],
            date.fromisoformat(item_spec["valid_from"]),
            item_spec["valid_to"],
        )
        assert item.epistemic_class is EpistemicClass(item_spec["epistemic_class"])
        assert item.supersedes_item_id == item_spec["supersedes"]
        for support, ref in zip(item_spec["supports"], item.supports, strict=True):
            spec = specs[support["version"]]
            assert (ref.target, ref.target_id) == (
                SupportTarget.CLAIM,
                claim_ids[support["version"]],
            )
            assert (ref.version_id, ref.claim_key) == (correctives[support["version"]], spec["key"])
            assert ref.version_status is VersionStatus.APPROVED
            assert (ref.lower_bound, ref.upper_bound) == (Decimal(spec["lo"]), Decimal(spec["hi"]))
            assert (ref.unit, list(ref.qualifiers)) == (spec["unit"], spec["qualifiers"])
            assert ref.citation is not None and ref.citation.quote == spec["quote"]
            assert ref.citation.anchor == spec["anchor"]
            assert ref.citation.capture_ref_id == captures[support["version"]]
            assert ref.blob_sha256 == spec["source_sha256"]
            assert ref.contract is not None
            assert ref.contract.model_dump() == contract_of(spec)
        assert memory.provenance(item_id) == (item,)

    # 7. Backup inventory: the Stage 2 data tables and both ledger manifests' tables.
    sets = write_backup(
        rig.settings, database=pg_db.dbname, snapshot_root=rig.snapshots, out_dir=tmp_path / "sets"
    )
    tables = [*STAGE2["backup"]["tables"]]
    tables += [t["table"] for m in (load(LEDGER), MANIFEST) for t in m["backup_tables"]]
    tables += IDENTITY_TABLES | COVERAGE_TABLES
    assert sorted(verify_set(sets).table_counts) == sorted(tables)
