"""D3.1 acceptance: ledger seal, decision chain, transitions, approval binding and roles.

Every case runs on its own ``eqos_test_*`` database through the real runtime, panel and owner
login pools (plan D3, decisions D1-D4, D2, D11). The triggers are authoritative, so each
refusal is provoked by direct inserts, never by a Python pre-check.
"""

from __future__ import annotations

import hashlib
import os
import threading
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from ledger_support import COVERAGE_TABLES, LEDGER_TABLES, RULING, Ledger, ledger, validation
from pg_evidence_schema_support import _insert, _update_column, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from retention_support import RETENTION_TABLES

from fundamentals.api.cli import main
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    ClaimState,
    DecisionKind,
    PolicyValue,
    SubjectKind,
    VersionState,
)
from fundamentals.ledger import store
from fundamentals.pg.role_secrets import (
    MissingRoleSecretError,
    RoleSecretError,
    load_login,
)
from fundamentals.pg.settings import GROUP_ROLES, PgRole

__all__ = ["ledger", "runtime", "seeded"]
pytestmark = pytest.mark.pg

SEALED = "is sealed"
ILLEGAL = "illegal decision"
UNBOUND = "latest passing AS_KNOWN validation"
RUNTIME_ROLE, PANEL_ROLE, OWNER_ROLE = "eqos_runtime", "eqos_panel", "eqos_owner"
OWNER = PgRole.OWNER


# --- D1 encoding and the chain digest (test-local recompute)


def enc(value: str | None) -> str:
    """The D1 field encoding: 'N' for null, else 'S' || utf8 length || ':' || value."""
    return "N" if value is None else f"S{len(value.encode())}:{value}"


def _sha(*fields: str | None) -> str:
    return hashlib.sha256("".join(map(enc, fields)).encode()).hexdigest()


def _utc(moment: datetime | None) -> str | None:
    return None if moment is None else moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def chain_digest(row: dict[str, Any], predecessor_digest: str | None) -> str:
    """A decision's digest from its read-back row, in the trigger's documented field order."""
    fields = [_text(row[name]) for name in ("id", "subject_kind", "subject_id", "kind", "sequence")]
    fields += [_text(row[name]) for name in ("predecessor_id", "sealed_digest", "validation_id")]
    fields += [_text(row[name]) for name in ("panel_review_id", "original_approval_sha256")]
    fields += [row["ruling"], None if row["decided_on"] is None else row["decided_on"].isoformat()]
    fields += [_text(row[name]) for name in ("policy_key", "policy_value", "policy_unit")]
    return _sha(*fields, row["decider"], _utc(row["recorded_at"]), predecessor_digest)


def test_the_encoding_separates_separators_null_empty_and_multibyte_text(ledger: Ledger) -> None:
    """Length-prefixed, null-tagged fields: no two field lists share an encoding, and SQL's
    ``eqos.enc`` is byte-identical to the documented rule."""
    assert _sha("a\x1fb", "c") != _sha("a", "b\x1fc")
    assert _sha("a:b", "c") != _sha("a", "b:c")
    assert _sha(None) != _sha("") and _sha(None, "") != _sha("", None)
    assert enc("₹ crore") == "S9:₹ crore"  # 9 UTF-8 bytes, 7 characters
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        for value in ("₹ crore", "", None, "a\x1fb:c", "S3:abc"):
            (encoded,) = conn.execute("SELECT eqos.enc(%s::text)", (value,)).fetchone() or ()
            assert encoded == enc(value), value


def test_the_chain_digest_recomputes_from_read_back_rows(ledger: Ledger) -> None:
    """Each SET_POLICY on one report chains to its predecessor; the digest covers the
    trigger-set decider and time, and a tampered field no longer recomputes."""
    report = ledger.report()
    units = ("₹ crore", "", "%")
    for unit, ruling in zip(units, ("keep 11.55", "a\x1fb:c", "₹ ruling"), strict=True):
        ledger.decide(
            PgRole.OWNER,
            report,
            DecisionKind.SET_POLICY,
            subject_kind=SubjectKind.REPORT,
            ruling=ruling,
            policy=PolicyValue(key="F1", value=Decimal("11.55"), unit=unit),
        )
    pool = ledger.pools[PgRole.RUNTIME]
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT * FROM eqos.decisions WHERE subject_id = %s ORDER BY sequence", (report,)
        ).fetchall()
    assert [row["sequence"] for row in rows] == [1, 2, 3]
    predecessor = None
    for row in rows:
        assert row["decider"] == "OWNER" and row["predecessor_id"] == (
            None if predecessor is None else rows[row["sequence"] - 2]["id"]
        )
        assert chain_digest(row, predecessor) == row["decision_sha256"]
        tampered = {**row, "policy_unit": row["policy_unit"] + " "}
        assert chain_digest(tampered, predecessor) != row["decision_sha256"]
        predecessor = row["decision_sha256"]


def test_a_subject_decision_takes_the_one_chain_stamp(
    ledger: Ledger, seeded: dict[str, int]
) -> None:
    """An owner decision on an interpretation (0013's trigger) carries the same chain digest
    as a report decision (0012's): one stamp for every subject."""
    interpretation = seeded["interpretations"]
    accepted = ledger.decide(
        PgRole.OWNER,
        interpretation,
        DecisionKind.ACCEPT,
        subject_kind=SubjectKind.INTERPRETATION,
        sealed_digest=_subject_digest(ledger, SubjectKind.INTERPRETATION, interpretation),
    )
    pool = ledger.pools[PgRole.RUNTIME]
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute("SELECT * FROM eqos.decisions WHERE id = %s", (accepted.id,)).fetchone()
    assert row is not None and chain_digest(row, None) == row["decision_sha256"]


def _subject_digest(ledger: Ledger, kind: SubjectKind, subject_id: int) -> str:
    with ledger.pools[PgRole.OWNER].connection() as conn:
        return store.subject_digest(conn.cursor(), kind, subject_id)


def test_version_numbers_and_validation_result_digests(ledger: Ledger) -> None:
    """A version's number is its place in its report's chain; a validation's result digest is
    the D1 digest of its row and its states (claim keys in order, version-level states last),
    so another result digests differently."""
    report, other = ledger.report(), ledger.report()
    v1 = ledger.draft(report)
    v2 = ledger.draft(report, v1)
    v3 = ledger.draft(other)
    passing = ledger.validate(v1)
    blocked = ledger.validate(
        v1,
        state=ClaimState.VALUE_MISMATCH,
        version_states=(VersionState.UNREGISTERED_NUMBER,),
    )
    pool = ledger.pools[PgRole.RUNTIME]
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        numbers = [
            cur.execute("SELECT eqos.version_number(%s) AS n", (v,)).fetchone()
            for v in (v1, v2, v3, 10**9)
        ]
        digests = {}
        for validation in (passing, blocked):
            row = cur.execute(
                "SELECT *, eqos.validation_result_digest(id) AS digest FROM eqos.validations "
                "WHERE id = %s",
                (validation,),
            ).fetchone()
            states = cur.execute(
                "SELECT c.claim_key, s.state FROM eqos.validation_claim_states s "
                "LEFT JOIN eqos.numeric_claims c ON c.id = s.claim_id WHERE s.validation_id = %s "
                'ORDER BY c.claim_key COLLATE "C" NULLS LAST, s.state COLLATE "C"',
                (validation,),
            ).fetchall()
            assert row is not None
            header = [_text(row[name]) for name in ("id", "version_id", "checker_version", "mode")]
            header += [_utc(row["overlay_position"]), row["pinned_input_sha256"]]
            header += [row["sealed_digest"], _utc(row["recorded_at"]), str(len(states))]
            pairs = [field for state in states for field in (state["claim_key"], state["state"])]
            assert _sha(*header, *pairs) == row["digest"]
            digests[validation] = row["digest"]
    assert [n and n["n"] for n in numbers] == [1, 2, 1, None]
    assert digests[passing] != digests[blocked]


# --- Seal


@pytest.mark.parametrize("path", ["SUBMIT", "IMPORT_SEAL"])
def test_the_seal_refuses_content_and_a_wrong_digest(ledger: Ledger, path: str) -> None:
    """A seal with a wrong digest is refused; after the seal every content insert is refused;
    a later validation leaves the digest unchanged."""
    report = ledger.report()
    if path == "SUBMIT":
        version = ledger.draft(report)
        with pytest.raises(errors.CheckViolation, match="sealed digest"):
            ledger.decide(PgRole.RUNTIME, version, DecisionKind.SUBMIT, sealed_digest="0" * 64)
        seal = ledger.submit(version)
    else:
        with pytest.raises(errors.CheckViolation, match="sealed digest"):
            ledger.imported(report, digest="0" * 64)
        version = ledger.imported(report)
        seal = ledger.head(version)
    assert seal.sealed_digest is not None
    inserts = (
        ("report_sections", {"ordinal": 1, "section_key": "late", "body": "late"}),
        ("import_sources", {"source_path": "late.md", "body": b"late"}),
    )
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        for table, row in inserts:
            with pytest.raises(errors.CheckViolation, match=SEALED), conn.transaction():
                _insert(conn, table, {"version_id": version, **row})
        with pytest.raises(errors.CheckViolation, match=SEALED), conn.transaction():
            _add_claim(conn, version)
    ledger.validate(version, mode=RunMode.RETROSPECTIVE)
    with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.cursor() as cursor:
        assert store.sealed_digest(cursor, version) == seal.sealed_digest


def _add_claim(conn: psycopg.Connection, version: int) -> None:
    """Insert, by direct SQL, a copy of the version's first claim under a new key."""
    with conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(
            "SELECT * FROM eqos.numeric_claims WHERE version_id = %s LIMIT 1", (version,)
        ).fetchone()
    assert row is not None
    del row["id"]
    late = {"claim_key": "calc.late", "measurement_key": Jsonb(row["measurement_key"])}
    _insert(conn, "numeric_claims", row | late)


# --- Chain: stale head, trigger-set fields


def test_a_stale_head_is_refused_and_trigger_fields_are_never_caller_supplied(
    ledger: Ledger,
) -> None:
    """A decision naming an old head is refused. A caller's recorded-at, decider, sequence
    and digest are overwritten by the trigger."""
    version = ledger.draft(ledger.report())
    started = datetime.now(UTC)
    with ledger.pools[PgRole.RUNTIME].connection() as conn, conn.cursor() as cursor:
        digest = store.sealed_digest(cursor, version)
        _insert(
            conn,
            "decisions",
            {
                "subject_kind": "REPORT_VERSION",
                "subject_id": version,
                "kind": "SUBMIT",
                "sealed_digest": digest,
                "sequence": 7,
                "decider": "OWNER",
                "recorded_at": datetime(2000, 1, 1, tzinfo=UTC),
                "created_xid": 1,
                "decision_sha256": "forged",
            },
        )
    submitted = ledger.head(version)
    assert (submitted.sequence, submitted.decider.value) == (1, "RUNTIME")
    assert submitted.recorded_at >= started and submitted.decision_sha256 != "forged"
    with pytest.raises(errors.CheckViolation, match="stale head"):
        ledger.decide(PgRole.OWNER, version, DecisionKind.REJECT, predecessor_id=None)
    rejected = ledger.decide(PgRole.OWNER, version, DecisionKind.REJECT)
    assert (rejected.sequence, rejected.predecessor_id) == (2, submitted.id)


# --- D3 transitions


def test_illegal_transitions_are_refused(ledger: Ledger) -> None:
    """Approve before submit, a repeated SUBMIT and SUBMIT of a version with import sources."""
    version = ledger.draft(ledger.report())
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.approve(version)
    ledger.submit(version)
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.submit(version)
    with_sources = ledger.draft(ledger.report(), import_sources=(("x.md", b"x"),))
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.submit(with_sources)


@pytest.mark.parametrize(
    "terminal", [DecisionKind.REJECT, DecisionKind.REQUEST_CHANGES, DecisionKind.WITHDRAW]
)
def test_nothing_follows_a_terminal_decision(ledger: Ledger, terminal: DecisionKind) -> None:
    """After REJECT, REQUEST_CHANGES or WITHDRAW every further decision is refused."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    if terminal is DecisionKind.WITHDRAW:
        ledger.approve(version)
    ledger.decide(PgRole.OWNER, version, terminal)
    for kind in (DecisionKind.APPROVE, DecisionKind.REJECT, DecisionKind.WITHDRAW):
        extra = {"validation_id": ledger.validate(version)} if kind is DecisionKind.APPROVE else {}
        with pytest.raises(errors.CheckViolation, match=ILLEGAL):
            ledger.decide(PgRole.OWNER, version, kind, **extra)
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.submit(version)


def test_withdrawing_an_unapproved_import_needs_an_approved_successor(ledger: Ledger) -> None:
    """An IMPORT_SEAL-only version is withdrawn only once a successor's chain holds APPROVE."""
    report = ledger.report()
    imported = ledger.imported(report)
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.decide(PgRole.OWNER, imported, DecisionKind.WITHDRAW)
    successor = ledger.draft(report, imported)
    ledger.submit(successor)
    ledger.approve(successor)
    withdrawn = ledger.decide(PgRole.OWNER, imported, DecisionKind.WITHDRAW)
    assert withdrawn.decider.value == "OWNER"


# --- D4 version chain


@pytest.mark.parametrize("path", ["SUBMIT", "IMPORT_SEAL"])
def test_one_root_and_earlier_same_report_predecessors(ledger: Ledger, path: str) -> None:
    """A second root, another report's predecessor, a self-link and a forward link are
    refused, whichever seal the version would take."""
    report, other = ledger.report(), ledger.report()
    ledger.draft(report)
    first_other = ledger.draft(other)

    def create(predecessor: int | None) -> int:
        if path == "IMPORT_SEAL":
            return ledger.imported(report, predecessor)
        return ledger.draft(report, predecessor)

    with pytest.raises(errors.UniqueViolation, match="report_versions_one_root"):
        create(None)
    with pytest.raises(errors.ForeignKeyViolation):
        create(first_other)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        (taken,) = conn.execute("SELECT nextval('eqos.report_versions_id_seq')").fetchone() or ()
    for link in (taken + 1, taken + 2):  # the next id itself, then a later one
        with pytest.raises(errors.CheckViolation, match="report_versions_check"):
            create(link)


def test_two_concurrent_roots_commit_exactly_one(ledger: Ledger, pg_db: PgTestDatabase) -> None:
    """Two transactions each insert a root of one report: the second waits, then fails."""
    report = ledger.report()
    draft = ledger.version_draft(report)
    outcome: list[BaseException | int] = []
    with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as first:
        store.create_version(first.cursor(), draft)

        def second() -> None:
            try:
                with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as conn:
                    outcome.append(store.create_version(conn.cursor(), draft))
            except psycopg.Error as refused:
                outcome.append(refused)

        racer = threading.Thread(target=second)
        racer.start()
        racer.join(timeout=1)
        assert racer.is_alive()
        first.commit()
    racer.join(timeout=20)
    assert len(outcome) == 1 and isinstance(outcome[0], errors.UniqueViolation)
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        roots = conn.execute(
            "SELECT count(*) FROM eqos.report_versions WHERE report_id = %s", (report,)
        ).fetchone()
    assert roots == (1,)


# --- D4 approval binding

UNBINDABLE = {
    "non-latest": {},
    "retrospective": {"mode": RunMode.RETROSPECTIVE},
    "version-level-flagged": {"version_states": (VersionState.UNREGISTERED_NUMBER,)},
    "incomplete": {"state": None},
    "failing": {"state": ClaimState.VALUE_MISMATCH},
}


@pytest.mark.parametrize("case", sorted(UNBINDABLE))
def test_approval_binds_only_the_latest_passing_as_known_validation(
    ledger: Ledger, case: str
) -> None:
    """Each unbindable validation the owner writes in its approving transaction refuses
    APPROVE; the same version then approves on a passing one."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    with pytest.raises(errors.CheckViolation, match=UNBOUND), ledger._cursor(OWNER) as cursor:  # noqa: SLF001
        bad = validation(cursor, version, **UNBINDABLE[case])
        if case == "non-latest":
            validation(cursor, version)
        ledger._decide(cursor, OWNER, version, DecisionKind.APPROVE, validation_id=bad)  # noqa: SLF001
    assert ledger.approve(version).kind is DecisionKind.APPROVE


@pytest.mark.parametrize("writer", ["runtime", "earlier owner transaction"])
def test_an_approval_binds_only_its_deciders_own_validation(ledger: Ledger, writer: str) -> None:
    """A passing latest validation the runtime wrote, or the owner wrote in an earlier
    transaction, cannot establish eligibility: the trigger refuses the APPROVE naming it."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    passing = ledger.validate(version, PgRole.RUNTIME if writer == "runtime" else OWNER)
    with pytest.raises(errors.CheckViolation, match="its decider wrote in this transaction"):
        ledger.decide(OWNER, version, DecisionKind.APPROVE, validation_id=passing)
    assert ledger.head(version).kind is DecisionKind.SUBMIT


def test_a_bound_validation_takes_no_further_state(ledger: Ledger) -> None:
    """The decider writes a passing validation, approves on it, then appends a failing state
    to it in the same transaction: refused, and nothing commits."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    with (
        pytest.raises(errors.CheckViolation, match="is bound by a decision"),
        ledger._cursor(OWNER) as cursor,  # noqa: SLF001
    ):
        bound = validation(cursor, version)
        ledger._decide(cursor, OWNER, version, DecisionKind.APPROVE, validation_id=bound)  # noqa: SLF001
        cursor.execute(
            "INSERT INTO eqos.validation_claim_states (validation_id, version_id, state) "
            "VALUES (%s, %s, 'UNREGISTERED_NUMBER')",
            (bound, version),
        )
    assert ledger.head(version).kind is DecisionKind.SUBMIT


def test_submit_needs_a_terminal_predecessor(ledger: Ledger) -> None:
    """By direct SQL: a successor's SUBMIT while its predecessor is a draft or in review is
    refused; once the predecessor is rejected it is sealed."""
    report = ledger.report()
    v1 = ledger.draft(report)
    v2 = ledger.draft(report, v1)
    with pytest.raises(errors.CheckViolation, match="predecessor is not terminal"):
        ledger.submit(v2)
    ledger.submit(v1)
    with pytest.raises(errors.CheckViolation, match="predecessor is not terminal"):
        ledger.submit(v2)
    ledger.decide(OWNER, v1, DecisionKind.REJECT)
    assert ledger.submit(v2).kind is DecisionKind.SUBMIT


def test_a_failing_validation_committed_after_the_read_refuses_the_approval(
    ledger: Ledger, pg_db: PgTestDatabase
) -> None:
    """The decider reads a passing latest validation; another transaction commits a failing
    one; the decider's APPROVE naming the one it read is refused."""
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    ledger.validate(version)
    with psycopg.connect(pg_db.conninfo(PgRole.OWNER)) as owner, owner.cursor() as cursor:
        read = store.latest_validation(cursor, version)
        assert read is not None and read.id is not None
        ledger.validate(version, state=ClaimState.VALUE_MISMATCH)
        head = store.chain_head(cursor, SubjectKind.REPORT_VERSION, version)
        with pytest.raises(errors.CheckViolation, match=UNBOUND):
            store.insert_decision(
                cursor,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=version,
                kind=DecisionKind.APPROVE,
                predecessor_id=None if head is None else head.id,
                sealed_digest=read.sealed_digest,
                validation_id=read.id,
                ruling=RULING,
            )


# --- Roles (D2, D11)


def test_the_runtime_role_may_submit_only(ledger: Ledger, seeded: dict[str, int]) -> None:
    """Runtime decisions other than SUBMIT, any runtime disposition, and runtime UPDATE or
    DELETE on any ledger table are refused."""
    report = ledger.report()
    version = ledger.draft(report)
    ledger.submit(version)
    validation = ledger.validate(version)
    for kind, extra in (
        (DecisionKind.APPROVE, {"validation_id": validation}),
        (DecisionKind.REJECT, {}),
        (DecisionKind.REQUEST_CHANGES, {}),
        (DecisionKind.WITHDRAW, {}),
    ):
        with pytest.raises(errors.CheckViolation, match=ILLEGAL):
            ledger.decide(PgRole.RUNTIME, version, kind, **extra)
    with pytest.raises(errors.CheckViolation, match=ILLEGAL):
        ledger.decide(
            PgRole.RUNTIME,
            report,
            DecisionKind.SET_POLICY,
            subject_kind=SubjectKind.REPORT,
            ruling=RULING,
            policy=PolicyValue(key="F1", value=Decimal(1), unit="%"),
        )
    disposition = {
        "item_id": seeded["queue_items"],
        "kind": "DISMISSED",
        "reason": "r",
        "decider": "d",
        "evidence_ref": "e",
    }
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        with (
            pytest.raises(errors.InsufficientPrivilege, match="may not dispose"),
            conn.transaction(),
        ):
            _insert(conn, "queue_dispositions", disposition)
        for table in sorted(LEDGER_TABLES):
            column = sql.Identifier(_update_column(conn, table))
            for statement in ("UPDATE {0} SET {1} = {1}", "DELETE FROM {0}"):
                with pytest.raises(errors.InsufficientPrivilege), conn.transaction():
                    conn.execute(sql.SQL(statement).format(sql.Identifier("eqos", table), column))


GATED = LEDGER_TABLES | COVERAGE_TABLES | {"queue_dispositions", "capture_refs"}
INSERTERS = {
    RUNTIME_ROLE: (LEDGER_TABLES - {"qa_records", "legacy_acquisitions", "panel_reviews"})
    | {"queue_dispositions", "capture_refs"},
    PANEL_ROLE: (LEDGER_TABLES - {"disposition_proposals"}) | {"queue_dispositions"},
    OWNER_ROLE: {"decisions", "queue_dispositions", "validations", "validation_claim_states"}
    | COVERAGE_TABLES
    | {"capture_refs"},
}


def test_privileges_match_the_d2_matrix(ledger: Ledger) -> None:
    """SELECT on every eqos table for all three roles; INSERT (and its sequence) exactly per
    the matrix, the runtime keeping its evidence grants; no UPDATE, DELETE or TRUNCATE; the
    clock and queue lock executable; panel and owner logins act as their group roles."""
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        tables = [
            row[0]
            for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'eqos'")
            if row[0] not in RETENTION_TABLES  # test_retention_classes.py
        ]
        for role, inserts in INSERTERS.items():
            for table in tables:
                qualified = f"eqos.{table}"
                granted = conn.execute(
                    "SELECT has_table_privilege(%(r)s, %(t)s, 'SELECT'), "
                    "has_table_privilege(%(r)s, %(t)s, 'INSERT'), "
                    "has_table_privilege(%(r)s, %(t)s, 'UPDATE, DELETE, TRUNCATE')",
                    {"r": role, "t": qualified},
                ).fetchone()
                insert = table in inserts if table in GATED else role == RUNTIME_ROLE
                assert granted == (True, insert, False), (role, table)
                if table in GATED:
                    assert conn.execute(
                        "SELECT has_sequence_privilege(%s, %s, 'USAGE')",
                        (role, qualified + "_id_seq"),
                    ).fetchone() == (insert,), (role, table)
            for function in ("eqos.store_now()", "eqos.lock_queue()"):
                assert conn.execute(
                    "SELECT has_function_privilege(%s, %s, 'EXECUTE')", (role, function)
                ).fetchone() == (True,)
    for role, group in GROUP_ROLES.items():
        if role not in ledger.pools:
            continue  # the reader: test_views_readonly_role.py
        with ledger.pools[role].connection() as conn:
            assert conn.execute("SELECT current_user").fetchone() == (group,)


def test_load_login_reads_the_harness_file_and_refuses_unsafe_ones(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The randomized login and password come back from their 0600 file. A missing, foreign,
    group-readable, symlinked, FIFO or malformed file is refused, naming the path only."""
    assert pg_db.secrets_dir is not None
    for role, expected in pg_db.logins.items():
        assert load_login(role, pg_db.secrets_dir) == expected
    path = tmp_path / "eqos_owner.login"
    with pytest.raises(MissingRoleSecretError, match="eqos_owner.login"):
        load_login(PgRole.OWNER, tmp_path)
    for body in ("owner_x", "owner_x:", "Owner:s3cr3t", "owner_x:s3cr3t\nmore", ":s3cr3t"):
        path.unlink(missing_ok=True)
        path.write_text(body + "\n")
        path.chmod(0o600)
        with pytest.raises(RoleSecretError, match="malformed") as refused:
            load_login(PgRole.OWNER, tmp_path)
        assert "s3cr3t" not in str(refused.value)
    path.write_text("owner_x:s3cr3t\n")
    path.chmod(0o640)
    with pytest.raises(RoleSecretError, match="unsafe"):
        load_login(PgRole.OWNER, tmp_path)
    path.chmod(0o600)
    assert load_login(PgRole.OWNER, tmp_path).login == "owner_x"
    real_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)
    with pytest.raises(RoleSecretError, match="unsafe"):
        load_login(PgRole.OWNER, tmp_path)
    monkeypatch.undo()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "eqos_owner.login").symlink_to(path)
    with pytest.raises(RoleSecretError, match="unsafe"):
        load_login(PgRole.OWNER, linked)
    piped = tmp_path / "piped"
    piped.mkdir()
    os.mkfifo(piped / "eqos_owner.login", 0o600)  # a blocking open would hang here
    with pytest.raises(RoleSecretError, match="unsafe"):
        load_login(PgRole.OWNER, piped)


def test_queue_dispose_runs_as_the_owner_login(
    pg_db: PgTestDatabase,
    seeded: dict[str, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``compare queue dispose`` succeeds as the randomized owner login given only
    ``EQOS_SECRETS_DIR``; with no owner file it refuses, naming the missing file."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    dispose = [
        *("compare", "queue", "dispose", "--item", str(seeded["queue_items"])),
        *("--kind", "DISMISSED", "--reason", "fixture", "--decider", "owner"),
        *("--evidence-ref", "fixture"),
    ]
    assert main(dispose) == 0
    with psycopg.connect(pg_db.conninfo(PgRole.RUNTIME)) as conn:
        assert conn.execute(
            "SELECT count(*) FROM eqos.queue_dispositions WHERE item_id = %s",
            (seeded["queue_items"],),
        ).fetchone() == (2,)
    capsys.readouterr()
    monkeypatch.setenv("EQOS_SECRETS_DIR", str(tmp_path))
    assert main(dispose) != 0
    captured = capsys.readouterr()
    assert str(tmp_path / "eqos_owner.login") in captured.out + captured.err
