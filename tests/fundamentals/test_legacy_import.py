"""D2.2: approved preflight, gate and lossless legacy import (plan D2, Task 2).

Every case works on byte copies of the legacy store under ``tmp_path`` and an isolated
``eqos_test_*`` database; the 8 originals are registered by the existing first-party intake.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
import yaml
from legacy_support import LEGACY_PATH, LEGACY_SHA256, file_sha256, legacy_copy, second_store
from pg_support import PgTestDatabase
from retained_support import REPO_ROOT, STORE_DIR, apar_intake, apar_store, seed_apar

from fundamentals.api.cli import main
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.canon.role_translation import translate
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.fact import Fact
from fundamentals.evidence.capture_intake import stage_retained_member
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.approvals import (
    Approval,
    GatedOperation,
    GateRefusal,
    GateRefusedError,
    OwnerAuthorization,
    check_gate,
    is_test_database,
)
from fundamentals.pg.legacy_import import (
    ImportRefusal,
    LegacyImportRefusedError,
    import_legacy,
    origin_id_for,
    preflight,
    verify_import,
)
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

PDF_KIND = {"FY27_Q1": "results"}
QUARTERS = ("FY26_Q2", "FY26_Q3", "FY26_Q4", "FY27_Q1")
APPROVAL = (
    "approval: {{reviewer: {reviewer}, verdict: APPROVE, date: 2026-10-15, "
    'payload_sha256: "{sha}"}}\n'
)
FACT_COLUMNS = (
    "origin_id, content_identity, value_hash, revision_family, revision_ordinal, "
    "canonical_status, canonical_selected_at, canonical_reason, source_id, file_sha256, anchor, "
    "valid_time_start, valid_time_end, knowledge_time, first_seen_time, fact_json, created_at"
)
SELECTION_COLUMNS = (
    "origin_id, content_identity, row_handle, sequence, predecessor_handle, selected_at, "
    "reason, legacy_baseline::int, selection_sha256"
)
Attempt = Callable[[], object]


def approve(path: Path, payload: bytes | None = None, reviewer: str = "test-fixture") -> Path:
    """Append one approval line naming ``payload``'s hash (default: the file's bytes)."""
    body = path.read_bytes()
    sha = hashlib.sha256(body if payload is None else payload).hexdigest()
    path.write_bytes(body + APPROVAL.format(reviewer=reviewer, sha=sha).encode())
    return path


def unapprove(path: Path) -> Path:
    """Drop the approval line, keeping the payload."""
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b"".join(line for line in lines if not line.startswith(b"approval:")))
    return path


def sqlite_rows(path: Path, query: str) -> list[tuple[Any, ...]]:
    """Rows of a read-only SQLite query."""
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as conn:
        return conn.execute(query).fetchall()


def edit_copy(path: Path, statement: str) -> Path:
    """Apply one write to a test-owned copy."""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(statement)
    return path


class Rig:
    """A seeded test database, the registered originals and a legacy copy."""

    def __init__(self, pg_db: PgTestDatabase, tmp_path: Path) -> None:
        self.pg_db, self.tmp_path, self.settings = pg_db, tmp_path, pg_db.settings
        self.snapshots = (tmp_path / STORE_DIR).absolute()
        self.legacy = legacy_copy(tmp_path)
        seed_apar(pg_db)

    def register(self, skip: str | None = None) -> None:
        """Register each quarter's XBRL and PDF original through the intake, except ``skip``'s
        PDF."""
        with self.pg_db.runtime_pool() as pool:
            repository = EvidenceRepository(pool)
            for quarter in QUARTERS:
                members = {
                    Representation.XBRL: "xbrl-consolidated",
                    Representation.PDF: PDF_KIND.get(quarter, "press-release"),
                }
                config = REPO_ROOT / f"config/aparinds-{quarter.lower().replace('_', '-')}.yaml"
                intake = apar_intake(self.tmp_path, quarter, members, issuer_config=config)
                store = apar_store(self.tmp_path)
                for kind in members:
                    if (quarter, kind) != (skip, Representation.PDF):
                        staged = stage_retained_member(
                            store, intake, kind, clock=repository.store_clock
                        )
                        repository.put_capture_ref(staged)

    def manifest(self, *files: tuple[str, Path]) -> Path:
        """An approved manifest over ``(label, path)`` files (default: the legacy copy)."""
        entries = files or (("aparinds", self.legacy),)
        body = {
            "files": [
                {"label": label, "path": str(path), "sha256": file_sha256(path)}
                for label, path in entries
            ],
            "snapshot_root": str(self.snapshots),
        }
        path = self.tmp_path / f"manifest-{len(list(self.tmp_path.glob('manifest-*')))}.yaml"
        path.write_text(yaml.safe_dump(body, sort_keys=True))
        return approve(path)

    def preflight(self, manifest: Path) -> Path:
        """The approved preflight report of ``manifest``."""
        with self.pg_db.runtime_pool() as pool, pool.connection() as conn:
            report = preflight(manifest, root=self.tmp_path, conn=conn, settings=self.settings)
        path = self.tmp_path / f"preflight-{manifest.stem}.yaml"
        path.write_bytes(report.to_yaml())
        return approve(path)

    def pair(self, *files: tuple[str, Path]) -> tuple[Path, Path]:
        """An approved manifest and its approved preflight."""
        manifest = self.manifest(*files)
        return manifest, self.preflight(manifest)

    def run(self, manifest: Path, report: Path) -> Any:
        """Import under ``manifest`` and its approved preflight."""
        with self.pg_db.runtime_pool() as pool:
            return import_legacy(
                manifest, report, root=self.tmp_path, pool=pool, settings=self.settings
            )

    def query(self, statement: str, *params: object) -> list[tuple[Any, ...]]:
        """Rows of one runtime-role query."""
        conninfo = self.settings.conninfo(PgRole.RUNTIME, dbname=self.pg_db.dbname)
        with psycopg.connect(conninfo) as conn:
            return [tuple(row) for row in conn.execute(statement, params).fetchall()]

    def corrupt(self, table: str, column: str, value: str) -> Attempt:
        """Import, then (admin only, trigger bypassed) change one column of handle 1."""
        self.run(*self.pair())
        admin = self.settings.conninfo(PgRole.ADMIN, dbname=self.pg_db.dbname)
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f"ALTER TABLE eqos.{table} DISABLE TRIGGER reject_row_mutation")
            conn.execute(f"UPDATE eqos.{table} SET {column} = %s WHERE handle = 1", (value,))
            conn.execute(f"ALTER TABLE eqos.{table} ENABLE TRIGGER reject_row_mutation")
        store, snapshots = origin_id_for(LEGACY_SHA256), SnapshotStore(self.snapshots)

        def check() -> object:
            with self.pg_db.runtime_pool() as pool, pool.connection() as conn:
                return verify_import(conn, store, self.legacy, snapshots=snapshots)

        return check


@pytest.fixture
def rig(pg_db: PgTestDatabase, tmp_path: Path) -> Rig:
    """The shared setup of every database case."""
    return Rig(pg_db, tmp_path)


def _unapproved(index: int) -> Callable[[Rig], Attempt]:
    def case(rig: Rig) -> Attempt:
        pair = rig.pair()
        unapprove(pair[index])
        return lambda: rig.run(*pair)

    return case


def _edited_preflight(old: bytes, new: bytes, *, reapprove: bool) -> Callable[[Rig], Attempt]:
    def case(rig: Rig) -> Attempt:
        manifest, report = rig.pair()
        payload = unapprove(report).read_bytes()
        report.write_bytes(payload.replace(old, new, 1))
        approve(report, None if reapprove else payload)
        return lambda: rig.run(manifest, report)

    return case


def _edited_source(statement: str, *, after_manifest: bool = False) -> Callable[[Rig], Attempt]:
    def case(rig: Rig) -> Attempt:
        if not after_manifest:
            edit_copy(rig.legacy, statement)
        manifest = rig.manifest()
        if after_manifest:
            edit_copy(rig.legacy, statement)
        return lambda: rig.preflight(manifest)

    return case


def _conflict(rig: Rig) -> Attempt:
    rig.run(*rig.pair())
    (rig.tmp_path / "other").mkdir()
    changed = edit_copy(legacy_copy(rig.tmp_path / "other"), "PRAGMA user_version = 7")
    pair = rig.pair(("aparinds", changed))
    return lambda: rig.run(*pair)


CASES: dict[str, tuple[Callable[[Rig], Attempt], str]] = {
    "unapproved-manifest": (_unapproved(0), GateRefusal.UNAPPROVED),
    "unapproved-preflight": (_unapproved(1), GateRefusal.UNAPPROVED),
    "preflight-edited-after-approval": (
        _edited_preflight(b"rows: 43", b"rows: 42", reapprove=False),
        GateRefusal.PAYLOAD_MISMATCH,
    ),
    "approval-names-another-test-database": (
        _edited_preflight(b"name: eqos_test_", b"name: eqos_test_x", reapprove=True),
        GateRefusal.WRONG_DATABASE,
    ),
    "approved-preflight-no-longer-matches": (
        _edited_preflight(b"rows: 43", b"rows: 42", reapprove=True),
        GateRefusal.APPROVAL_STALE,
    ),
    "missing-original": (
        lambda rig: lambda: rig.run(*rig.pair()),
        ImportRefusal.PREFLIGHT_NOT_CLEAN,
    ),
    "bytes-differ-from-manifest": (
        _edited_source("PRAGMA user_version = 7", after_manifest=True),
        ImportRefusal.FINGERPRINT_CHANGED,
    ),
    "canonical-without-time": (
        _edited_source(
            "UPDATE facts SET canonical_selected_at = NULL WHERE row_id = "
            "(SELECT min(row_id) FROM facts WHERE canonical_status = 'canonical')"
        ),
        ImportRefusal.NO_BASELINE_TIME,
    ),
    "two-canonical-in-one-family": (
        _edited_source(
            "UPDATE facts SET canonical_status = 'canonical', canonical_selected_at = "
            "'2026-09-07T05:00:00+00:00' WHERE row_id = "
            "(SELECT max(row_id) FROM facts WHERE revision_ordinal = 2)"
        ),
        ImportRefusal.MULTIPLE_BASELINES,
    ),
    "new-fingerprint-under-label": (_conflict, ImportRefusal.FINGERPRINT_CONFLICT),
    "row-column-changed": (
        lambda rig: rig.corrupt("fact_rows", "canonical_reason", "edited"),
        ImportRefusal.ROW_MISMATCH,
    ),
    "selection-time-changed": (
        lambda rig: rig.corrupt("fact_selections", "selected_at", "2026-09-07T04:58:26+00:00"),
        ImportRefusal.CHAIN_INVALID,
    ),
}


@pytest.mark.parametrize("name", list(CASES))
def test_refusals_write_nothing(rig: Rig, name: str) -> None:
    """Each gate, preflight, source and lossless-proof refusal names its reason, adds no row."""
    build, reason = CASES[name]
    rig.register(skip="FY26_Q3" if name == "missing-original" else None)
    attempt = build(rig)
    before = rig.query("SELECT count(*) FROM eqos.fact_rows")
    with pytest.raises((GateRefusedError, LegacyImportRefusedError)) as refused:
        attempt()
    assert refused.value.reason == reason
    assert rig.query("SELECT count(*) FROM eqos.fact_rows") == before
    assert file_sha256(LEGACY_PATH) == LEGACY_SHA256


def _approval(reviewer: str = "gpt-6.1-sol", verdict: str = "APPROVE") -> Approval:
    return Approval(reviewer=reviewer, verdict=verdict, date=date(2026, 10, 15), payload_sha256="0")


def _owner(**changes: object) -> OwnerAuthorization:
    record = {"by": "PavanMV", "date": date(2026, 10, 15), "database": "equity_os"}
    record |= {"operations": ("IMPORT",), "approved_payload_sha256": "0"}
    return OwnerAuthorization.model_validate(record | changes)


SOL, FIXTURE, MISMATCH = _approval(), _approval("test-fixture"), GateRefusal.OWNER_RECORD_MISMATCH
GATE_TABLE: list[tuple[str, Approval, OwnerAuthorization | None, GateRefusal | None]] = [
    ("equity_os", SOL, _owner(), None),
    ("equity_os", SOL, None, GateRefusal.OWNER_RECORD_MISSING),
    ("equity_os", SOL, _owner(database="eqos_other"), GateRefusal.WRONG_DATABASE),
    ("equity_os", SOL, _owner(operations=("CUTOVER",)), MISMATCH),
    ("equity_os", SOL, _owner(approved_payload_sha256="1"), MISMATCH),
    # An IMPORT record must cite the preflight's payload hash, never the manifest's.
    ("equity_os", SOL, _owner(approved_payload_sha256="manifest"), MISMATCH),
    ("equity_os", FIXTURE, _owner(), GateRefusal.REVIEWER_NOT_ALLOWED),
    ("equity_os", _approval(verdict="REJECT"), _owner(), GateRefusal.UNAPPROVED),
    ("eqos_test_a", FIXTURE, None, None),
    *[
        (name, FIXTURE, None, GateRefusal.REVIEWER_NOT_ALLOWED)
        for name in ("eqos_testx_1", "eqos_test", "EQOS_TEST_a", "x_eqos_test_a")
    ],
]


@pytest.mark.parametrize(("database", "approval", "owner", "refusal"), GATE_TABLE)
def test_check_gate(
    database: str, approval: Approval, owner: OwnerAuthorization | None, refusal: str | None
) -> None:
    """Only the literal ``eqos_test_`` prefix relaxes the reviewer and owner rules."""
    assert is_test_database(database) == (database == "eqos_test_a")
    try:
        check_gate(GatedOperation.IMPORT, database=database, approval=approval, owner=owner)
    except GateRefusedError as refused:
        assert refused.reason == refusal
    else:
        assert refusal is None


def test_import_is_lossless_separate_and_repeatable(rig: Rig, tmp_path: Path) -> None:
    """Two colliding stores import byte for byte, stay apart, and re-import is a no-op."""
    rig.register()
    second = second_store(tmp_path)
    pair = rig.pair(("aparinds", rig.legacy), ("aparinds-migrated", second))
    result = rig.run(*pair)
    legacy, migrated = origin_id_for(LEGACY_SHA256), origin_id_for(file_sha256(second))
    assert (result.created, result.rows, result.selections) == (True, 86, 48)
    assert set(result.stores) == {legacy, migrated}
    facts = sqlite_rows(rig.legacy, "SELECT * FROM facts ORDER BY row_id")
    # FactStore's own migration of the second copy is the oracle for the synthesized chain.
    baseline = sqlite_rows(second, "SELECT * FROM canonical_selections ORDER BY selection_id")
    assert (len(facts), len(baseline)) == (43, 24)
    for store, synthesized in ((legacy, True), (migrated, False)):
        where = "WHERE target_store = %s ORDER BY handle"
        assert rig.query(f"SELECT {FACT_COLUMNS} FROM eqos.fact_rows {where}", store) == facts
        assert (
            rig.query(f"SELECT {SELECTION_COLUMNS} FROM eqos.fact_selections {where}", store)
            == baseline
        )
        assert rig.query(
            "SELECT DISTINCT synthesized FROM eqos.fact_selections WHERE target_store = %s", store
        ) == [(synthesized,)]
        assert rig.query(
            "SELECT count(*), count(DISTINCT capture_ref_id) FROM eqos.legacy_evidence_bindings "
            "WHERE target_store = %s",
            store,
        ) == [(43, 8)]
        events = "SELECT state FROM eqos.fact_store_events WHERE store_id = %s"
        assert rig.query(events, store) == [("IMPORTED",)]
    again = rig.run(*pair)
    assert (again.created, again.rows, again.selections) == (False, 86, 48)
    assert rig.query("SELECT count(*) FROM eqos.fact_rows") == [(86,)]
    assert file_sha256(rig.legacy) == file_sha256(LEGACY_PATH) == LEGACY_SHA256


def test_role_translation_maps_six_roles_to_dictionary_v2(tmp_path: Path) -> None:
    """Legacy ``ProfitBeforeTax`` is §1 ``profit_before_tax``, never the headline."""
    roles: dict[str, set[str]] = {}
    query = "SELECT revision_family, fact_json FROM facts"
    for family, fact_json in sqlite_rows(legacy_copy(tmp_path), query):
        key = translate(Fact.model_validate_json(fact_json), entity_id=1)
        assert key is not None and key.dimensions.pairs == ()
        roles.setdefault(family.split(":")[1], set()).add(key.canonical_id)
    assert roles == {
        "revenue": {"revenue_from_operations"},
        "total_income": {"total_income"},
        "total_expenses": {"total_expenses"},
        "profit_before_tax": {"profit_before_tax"},
        "profit_for_period": {"profit_for_period"},
        "basic_eps": {"eps_basic"},
    }
    dictionary = load_dictionary(REPO_ROOT / "config" / "dictionary", "v2")
    assert set().union(*roles.values()) <= {row.canonical_id for row in dictionary.rows}


def test_cli_preflight_import_status(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ``legacy`` commands run the same path against ``EQOS_PG_DB``."""
    rig.register()
    for name, value in rig.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(rig.tmp_path)
    manifest, report = str(rig.manifest()), rig.tmp_path / "cli-preflight.yaml"
    assert main(["legacy", "preflight", "--manifest", manifest, "--out", str(report)]) == 0
    approve(report)
    assert main(["legacy", "import", "--manifest", manifest, "--preflight", str(report)]) == 0
    capsys.readouterr()
    assert main(["legacy", "status", "--manifest", manifest]) == 0
    assert capsys.readouterr().out == f"aparinds\t{origin_id_for(LEGACY_SHA256)}\tIMPORTED\n"
