"""D3.9: the ledger Stage 1 end-to-end (plan D3, Task 8).

One ``eqos_test_*`` database holds the Stage 1 captures and run and the D2 legacy import; the
retained Apar versions are imported through ``ledger import`` as the panel login, and every
stored inventory is compared with the frozen ledger manifest, the only source of expected values.
A corrective FY27_Q1 version is drafted, submitted and ``AS_KNOWN``-checked as runtime; every
version is exported through the CLI; the database is backed up and restored (no replay).
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from coverage_support import watchlist
from ledger_support import COVERAGE_TABLES, IDENTITY_TABLES, LEDGER_TABLES, MEMORY_TABLES
from pg_support import PgTestDatabase, drop_database, mint_name
from retention_support import RETENTION_TABLES, restore_args
from stage1_e2e_support import CONFIG, RUNS, Stage
from test_frozen_manifests import LEDGER, REPO, load
from test_ledger_import import CONFIG as IMPORT_CONFIG
from test_legacy_import import Rig

from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST
from fundamentals.api.screener_cli_dispatch import EXIT_OK
from fundamentals.api.watchlist_config import load_watchlist_config, stock_catalog
from fundamentals.contracts.canonical import Basis, ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    NumericClaim,
    ReportSection,
    VersionDraft,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.ledger import lifecycle, store
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.display import (
    content_hash,
    parse_style,
    render_claim,
    render_section,
    rounded,
)
from fundamentals.ledger.importer import load_import_config
from fundamentals.pg.backup import restore_backup, verify_set, write_backup
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

MANIFEST = load(LEDGER)
STAGE2 = load(REPO / "tests/fundamentals/fixtures/data_foundation/stage2_manifest.yaml")
# Manifest fields that locate or explain a value rather than state a stored one.
PROVENANCE = {"key", "from", "aliases", "concept", "change", "at"}
SELF_CITED = "self (import record)"  # a POLICY claim citing its own import (notation)
DECIMALS = ("v", "lo", "hi")
_VERSIONS = (
    "SELECT r.period, r.kind, v.id FROM eqos.reports r "
    "JOIN eqos.report_versions v ON v.report_id = r.id ORDER BY v.id"
)
_DECISIONS = (
    "SELECT kind, ruling, decided_on, original_approval_sha256 FROM eqos.decisions "
    "WHERE subject_kind = 'REPORT_VERSION' AND subject_id = %s ORDER BY sequence"
)
_QA = "SELECT gate, result FROM eqos.qa_records WHERE version_id = %s ORDER BY id"
_FIRST_SEEN = "SELECT min(retrieved_at) FROM eqos.legacy_acquisitions WHERE blob_sha256 = %s"
_REPORT = (
    "SELECT e.entity_key, r.period, r.kind FROM eqos.report_versions v "
    "JOIN eqos.reports r ON r.id = v.report_id "
    "JOIN eqos.reporting_entities e ON e.id = r.entity_id WHERE v.id = %s"
)
_REPORTS = (
    "SELECT e.entity_key, r.period, r.kind FROM eqos.reports r "
    "JOIN eqos.reporting_entities e ON e.id = r.entity_id"
)
# The record a claim's foreign key cites: a legacy fact's file and translated key, a capture's
# blob.
_CITED_FACT = """SELECT f.file_sha256, t.entity_id, t.canonical_id, t.period_start, t.period_end,
    t.period_instant, t.basis, t.framework, t.currency, t.value_kind, t.dimension_set
FROM eqos.fact_rows f JOIN eqos.legacy_fact_translations t
    ON t.target_store = f.target_store AND t.row_handle = f.handle
WHERE f.origin = %s AND f.origin_id = %s"""
_CITED_CAPTURE = "SELECT blob_sha256 FROM eqos.capture_refs WHERE id = %s"


def differences(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Every path where ``actual`` differs from ``expected``: a missing or extra mapping key, a
    list of another length, or an unequal leaf."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = [f"{path}.{k}: missing" for k in expected.keys() - actual.keys()]
        found += [f"{path}.{k}: extra" for k in actual.keys() - expected.keys()]
        for k in expected.keys() & actual.keys():
            found += differences(expected[k], actual[k], f"{path}.{k}")
        return sorted(found)
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return [
            d
            for i, pair in enumerate(zip(expected, actual, strict=True))
            for d in differences(*pair, f"{path}[{i}]")
        ]
    return [] if expected == actual else [f"{path}: expected {expected!r}, got {actual!r}"]


def expected_version(version: dict[str, Any], entity_ids: dict[str, int]) -> dict[str, Any]:
    """The manifest version in the stored shape: provenance dropped, nulls dropped from claims,
    bounds as ``Decimal`` and the symbolic entity resolved."""

    def claim(item: dict[str, Any]) -> dict[str, Any]:
        shaped = {k: v for k, v in item.items() if k not in PROVENANCE and v is not None}
        shaped |= {k: Decimal(shaped[k]) for k in DECIMALS if k in shaped}
        if "mkey" in shaped:
            mkey = shaped["mkey"]
            shaped["mkey"] = mkey | {"entity_id": entity_ids[mkey["entity_id"]]}
        return shaped

    evidence = version.get("evidence")
    return {
        "report": version["report"],
        "cutoff": datetime.fromisoformat(version["cutoff"]["instant"]),
        "status": version["status"],
        "decisions": version["decisions"],
        "evidence": evidence
        and {
            "commit": evidence["commit"],
            "original_approval_hash": evidence["original_approval_hash"],
            "decided_on": str(evidence["decided_on"]),
            "ruling": evidence["ruling"],
        },
        "content_sha256": version["content_sha256"],
        "import_sources": version["import_sources"],
        "qa_records": [{k: v for k, v in q.items() if k != "at"} for q in version["qa_records"]],
        "acquisitions": {
            a["blob"]: datetime.fromisoformat(a["first_seen"]) for a in version["acquisitions"]
        },
        "sections": {
            s["key"]: {"ordinal": s["ordinal"], "sha256": s["sha256"]} for s in version["sections"]
        },
        "claims": {c["key"]: claim(c) for c in version["claims"]},
    }


def stored_claim(rig: Rig, item: NumericClaim, state: ClaimState) -> dict[str, Any]:
    """One stored claim and its state in the manifest's claim shape, nulls dropped. A resolved
    citation's source SHA-256 and key are the cited record's, so a claim whose declared ones
    differ from what it cites shows the difference."""
    citation = item.citation
    sha, key = cited(rig, item)
    shaped = {
        "section": item.section_key,
        "kind": citation.kind.value,
        "value_kind": item.value_kind.value,
        "unit": item.unit,
        "currency": item.currency,
        "scale": item.scale,
        "v": item.value,
        "lo": item.lower_bound,
        "hi": item.upper_bound,
        "horizon": item.horizon,
        "precision": item.precision,
        "rounding": item.rounding.value,
        "qualifiers": list(item.qualifiers),
        "epistemic": item.epistemic_class.value,
        "metric": item.metric,
        "metric_label": item.metric_label,
        "scope": item.scope,
        "constant_currency": item.constant_currency,
        "mkey": _agreed(item.measurement_key and _key(item.measurement_key), key and _key(key)),
        "source_sha256": _agreed(citation.source_sha256, sha),
        "anchor": citation.anchor,
        "quote": citation.quote,
        "citation": SELF_CITED
        if citation.kind is CitationKind.POLICY and citation.policy_decision_id is None
        else None,
        "state": state.value,
    }
    return {k: v for k, v in shaped.items() if v is not None}


def cited(rig: Rig, item: NumericClaim) -> tuple[str | None, MeasurementKey | None]:
    """The source SHA-256 and measurement key of the record the claim's foreign key names; an
    unresolved claim names none and keeps its declared ones."""
    citation = item.citation
    if citation.fact_origin_id is not None:
        ((sha, entity, canonical, start, end, instant, *kinds, pairs),) = rig.query(
            _CITED_FACT, citation.fact_origin, citation.fact_origin_id
        )
        basis, framework, currency, value_kind = kinds
        period = PeriodInterval.at(instant) if instant else PeriodInterval.duration(start, end)
        return sha, MeasurementKey(
            entity_id=entity,
            canonical_id=canonical,
            period=period,
            basis=Basis(basis),
            framework=AccountingFramework(framework),
            currency=currency,
            value_kind=ValueKind(value_kind),
            dimensions=DimensionSet(pairs=tuple(tuple(pair) for pair in pairs)),
        )
    if citation.capture_ref_id is not None:
        ((sha,),) = rig.query(_CITED_CAPTURE, citation.capture_ref_id)
        return sha, item.measurement_key
    return citation.source_sha256, item.measurement_key


def _agreed(declared: Any, cited_value: Any) -> Any:
    """The cited value when the claim declares the same, else both, so the comparison names it."""
    return cited_value if declared == cited_value else {"declared": declared, "cited": cited_value}


def _key(key: MeasurementKey) -> dict[str, Any]:
    """All eight measurement-key fields, as the manifest writes them."""
    period = key.period
    return {
        "entity_id": key.entity_id,
        "canonical_id": key.canonical_id,
        "period": {
            k: None if day is None else day.isoformat()
            for k, day in (
                ("start", period.start),
                ("end", period.end),
                ("instant", period.instant),
            )
        },
        "basis": key.basis.value,
        "framework": key.framework.value,
        "currency": key.currency,
        "value_kind": key.value_kind.value,
        "dimensions": [list(pair) for pair in key.dimensions.pairs],
    }


def stored_version(rig: Rig, version_id: int) -> dict[str, Any]:
    """One stored version in the shape :func:`expected_version` gives, its report identity and
    every claim's cited source read from the stored rows."""
    with rig.pg_db.runtime_pool() as pool, pool.connection() as conn:
        cursor = conn.cursor()
        draft = store.read_version(cursor, version_id)
        status = lifecycle.version_status(cursor, version_id)
        validation = store.latest_validation(cursor, version_id)
    assert validation is not None and validation.mode is RunMode.RETROSPECTIVE
    states = dict(validation.claim_states)
    decisions = rig.query(_DECISIONS, version_id)
    approval = next((d for d in decisions if d[0] == "IMPORTED_APPROVAL"), None)
    blobs = {c.citation.source_sha256 for c in draft.claims} - {None}
    ((stock, period, kind),) = rig.query(_REPORT, version_id)
    return {
        "report": {"stock": stock, "period": period, "kind": kind},
        "cutoff": draft.knowledge_cutoff,
        "status": status.value,
        "decisions": [d[0] for d in decisions],
        "evidence": approval
        and {
            "commit": load_import_config(IMPORT_CONFIG).q0.evidence_commit,
            "original_approval_hash": approval[3].split(","),
            "decided_on": approval[2].isoformat(),
            "ruling": approval[1],
        },
        "content_sha256": draft.content_hash,
        "import_sources": [
            {"path": path, "sha256": hashlib.sha256(body).hexdigest()}
            for path, body in draft.import_sources
        ],
        "qa_records": [{"gate": gate, **result} for gate, result in rig.query(_QA, version_id)],
        "acquisitions": {blob: rig.query(_FIRST_SEEN, blob)[0][0] for blob in blobs},
        "sections": {
            s.section_key: {"ordinal": s.ordinal, "sha256": _rendered_sha256(s, draft.claims)}
            for s in draft.sections
        },
        "claims": {c.claim_key: stored_claim(rig, c, states[c.claim_key]) for c in draft.claims},
    }


def _rendered_sha256(section: ReportSection, claims: Iterable[NumericClaim]) -> str:
    """SHA-256 of the section's stored body with its placeholders filled: its source bytes."""
    return hashlib.sha256(render_section(section.body, claims).encode()).hexdigest()


@pytest.mark.pg
@pytest.mark.retained
def test_ledger_stage1_end_to_end(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = datetime.now(UTC)
    # 1. Stage 1 captures and run, the D2 legacy import.
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    with pg_db.runtime_pool() as pool:
        stage = Stage(pg_db, pool, tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.first_party()
        stage.execute(vendors=[])
    ((entity_id,),) = rig.query(
        "SELECT id FROM eqos.reporting_entities WHERE entity_key = 'APARINDS'"
    )

    # 2. ``ledger import`` as the panel login.
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    command = ["ledger", "import", "--config", str(IMPORT_CONFIG), "--repo", str(REPO)]
    assert main([*command, "--snapshot-root", str(rig.snapshots)]) == EXIT_OK

    # 3. Every version's inventories and payloads equal the manifest's.
    ids = {(period, kind): vid for period, kind, vid in rig.query(_VERSIONS)}
    by_name = {}
    for version in MANIFEST["versions"]:
        report = version["report"]
        version_id = ids.pop((report["period"], report["kind"]))
        by_name[version["id"]] = version_id
        expected = expected_version(version, {"APARINDS": entity_id})
        assert differences(expected, stored_version(rig, version_id)) == [], version["id"]
    assert ids == {}
    reports = [
        (r["stock"], r["period"], r["kind"]) for r in (v["report"] for v in MANIFEST["versions"])
    ]
    assert sorted(rig.query(_REPORTS)) == sorted(reports)
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        claims = {
            name: {c.claim_key: c for c in store.read_version(conn.cursor(), vid).claims}
            for name, vid in by_name.items()
        }
    shown = [
        render_claim(claims[d["version"]][d["claim"]], parse_style(d["style"]))
        for d in MANIFEST["displays"]
    ]
    assert shown == [d["expect"] for d in MANIFEST["displays"]]
    retro, corrective, policy, rendered = MANIFEST["scenarios"]
    revenue = claims[retro["version"]][retro["claim"]]
    assert rig.query(_FIRST_SEEN, revenue.citation.source_sha256) == [
        (datetime.fromisoformat(retro["first_seen"]),)
    ]
    pct = claims[rendered["version"]][rendered["claim"]]
    assert pct.value is not None and pct.rounding.value == rendered["rounding"]
    assert rounded(pct.value, pct) == Decimal(rendered["rendered"])
    assert claims[policy["version"]][policy["claim"]].value == Decimal(policy["v"])

    # 4. The corrective version, drafted, submitted and AS_KNOWN-checked as runtime.
    catalog = stock_catalog(load_watchlist_config(DEFAULT_WATCHLIST).stock("APARINDS"))
    paths = {"catalog": catalog, "snapshots": SnapshotStore(rig.snapshots)}
    section = ReportSection(
        ordinal=0,
        section_key=revenue.section_key,
        body=f"{{{{e:observed}}}} Revenue was {{{{c:{revenue.claim_key}|group-intl}}}} crore.\n",
    )
    predecessor = by_name[corrective["predecessor"]]
    ((report_id,),) = rig.query(
        "SELECT report_id FROM eqos.report_versions WHERE id = %s", predecessor
    )
    draft = VersionDraft(
        report_id=report_id,
        predecessor_id=predecessor,
        author="ledger-stage1-e2e",
        knowledge_cutoff=datetime.fromisoformat(corrective["cutoff"]),
        content_hash=content_hash((section,), (revenue,)),
        sections=(section,),
        claims=(revenue,),
    )
    with pg_db.runtime_pool() as pool:
        with pg_db.owner_pool() as owner:
            watchlist({PgRole.RUNTIME: pool, PgRole.OWNER: owner}, entity_id, paths["snapshots"])
        with pool.connection() as conn, conn.transaction():
            successor = store.create_version(conn.cursor(), draft)
        lifecycle.submit(pool, successor, **paths)
        checked = lifecycle.validate(pool, successor, mode=RunMode(corrective["mode"]), **paths)
        # The same stored claim declaring another source file's hash cites nothing.
        forged = revenue.citation.model_copy(update={"source_sha256": "0" * 64})
        with pool.connection() as conn:
            assert (
                resolve_citation(
                    conn.cursor(),
                    revenue.model_copy(update={"citation": forged}),
                    entity_id=entity_id,
                    overlay_position=checked.overlay_position,
                    **paths,
                )
                is None
            )
    assert checked.claim_states == ((corrective["claim"], ClaimState(corrective["expect"])),)

    # 5. Export reproduces every imported content hash.
    out = tmp_path / "export.md"
    for version in MANIFEST["versions"]:
        assert main(["ledger", "export", str(by_name[version["id"]]), "--out", str(out)]) == EXIT_OK
        assert hashlib.sha256(out.read_bytes()).hexdigest() == version["content_sha256"]

    # No ledger row was recorded before the test started.
    for table in sorted(LEDGER_TABLES):
        columns = rig.query(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = 'eqos' "
            "AND table_name = %s AND column_name = 'recorded_at'",
            table,
        )
        if columns:
            ((earliest,),) = rig.query(f"SELECT min(recorded_at) FROM eqos.{table}")
            assert earliest is None or earliest >= started, table

    # 6. Backup and restore, no replay.
    sets = write_backup(
        rig.settings, database=pg_db.dbname, snapshot_root=rig.snapshots, out_dir=tmp_path / "sets"
    )
    tables = [*STAGE2["backup"]["tables"], *(t["table"] for t in MANIFEST["backup_tables"])]
    tables += MEMORY_TABLES | IDENTITY_TABLES | COVERAGE_TABLES | RETENTION_TABLES
    assert sorted(verify_set(sets).table_counts) == sorted(tables)
    fresh = mint_name(rig.settings)
    try:
        check = restore_backup(
            sets,
            rig.settings,
            database=fresh,
            snapshot_root=tmp_path / "restored",
            replay_runs=False,
            config_root=CONFIG,
            **restore_args(pg_db, sets, tmp_path / "restored"),
        )
        assert check.ok, check
    finally:
        drop_database(rig.settings, fresh)


def _mutate(manifest: dict[str, Any], change: str) -> None:
    """One field of FY27_Q1's ``fact.revenue`` changed in place."""
    (claim,) = (c for c in manifest["versions"][3]["claims"] if c["key"] == "fact.revenue")
    if change == "value":
        claim["v"] = str(Decimal(claim["v"]) + Decimal("0.01"))
    elif change == "citation":
        claim["source_sha256"] = "0" * 64
    elif change == "dropped":
        del claim["unit"]
    else:
        claim["mkey"]["canonical_id"] = "revenue"


@pytest.mark.parametrize(
    ("change", "path"),
    [
        ("value", ".claims.fact.revenue.v"),
        ("citation", ".claims.fact.revenue.source_sha256"),
        ("dropped", ".claims.fact.revenue.unit"),
        ("canonical_id", ".claims.fact.revenue.mkey.canonical_id"),
    ],
)
def test_comparison_reports_a_mutated_manifest(change: str, path: str) -> None:
    """The one comparison helper names the field a mutated manifest copy changes, and finds
    nothing between a version and itself."""
    entity = {"APARINDS": 1}
    stored = expected_version(MANIFEST["versions"][3], entity)
    mutated = copy.deepcopy(MANIFEST)
    _mutate(mutated, change)
    assert differences(stored, stored) == []
    (found,) = differences(expected_version(mutated["versions"][3], entity), stored)
    assert found.startswith(f"{path}:")
