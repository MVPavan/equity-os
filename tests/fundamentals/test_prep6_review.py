"""PREP-6 acceptance: owner review telemetry on ledger versions (plan ``docs/plans/PREP-6.md``).

Task 1: migration 0040 stores a review session only beside the owner's review decision on its
version, and a claim review only for a claim of that version. Refusals are provoked by direct
inserts through the real role logins, so the triggers and grants are what is under test.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, NamedTuple

import psycopg
import pytest
from ledger_support import SECTION, Ledger, claim, ledger
from pg_evidence_schema_support import _insert, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors

from fundamentals.contracts.ledger import DecisionKind, PanelReview, SubjectKind, Verdict
from fundamentals.ledger import store
from fundamentals.pg.settings import PgRole

__all__ = ["ledger", "runtime", "seeded"]
pytestmark = pytest.mark.pg

V = SubjectKind.REPORT_VERSION
STARTED = datetime(2026, 8, 1, 9, tzinfo=UTC)
FINISHED = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
OTHER_KEY = "calc.2"


class Rig(NamedTuple):
    """Versions with the decisions a session could name."""

    ledger: Ledger
    version: int
    submitted: int  # the version's SUBMIT
    decided: int  # the owner's REQUEST_CHANGES on the version
    other: int  # another version, whose only claim is OTHER_KEY
    other_decided: int  # the owner's REQUEST_CHANGES on it
    panel_version: int
    panel_decided: int  # the panel's REQUEST_CHANGES on it


@pytest.fixture
def rig(ledger: Ledger) -> Rig:
    """Three submitted versions: two decided by the owner, one by the panel."""
    version = ledger.draft(ledger.report())
    submitted = ledger.submit(version).id
    decided = ledger.decide(PgRole.OWNER, version, DecisionKind.REQUEST_CHANGES).id
    other = ledger.draft(
        ledger.report(),
        sections=(SECTION.model_copy(update={"body": f"{{{{c:{OTHER_KEY}|}}}}"}),),
        claims=(claim(ledger.trace_id, OTHER_KEY),),
    )
    ledger.submit(other)
    other_decided = ledger.decide(PgRole.OWNER, other, DecisionKind.REQUEST_CHANGES).id
    panel_version = ledger.draft(ledger.report())
    ledger.submit(panel_version)
    pool = ledger.pools[PgRole.PANEL]
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        digest = store.sealed_digest(cursor, panel_version)
        review = PanelReview(
            subject_kind=V,
            subject_id=panel_version,
            sealed_digest=digest,
            provider="fake",
            model="model-1",
            effort="fixture-effort",
            brief_version="b1",
            verdict=Verdict.REQUEST_CHANGES,
            rationale="direct",
        )
        head = store.chain_head(cursor, V, panel_version)
        assert head is not None
        panel_decided = store.insert_decision(
            cursor,
            subject_kind=V,
            subject_id=panel_version,
            kind=DecisionKind.REQUEST_CHANGES,
            predecessor_id=head.id,
            sealed_digest=digest,
            panel_review_id=store.insert_panel_review(cursor, review),
        ).id
    return Rig(
        ledger, version, submitted, decided, other, other_decided, panel_version, panel_decided
    )


def _session(version_id: int, decision_id: int) -> dict[str, Any]:
    """A review session row; ``recorded_at`` is the trigger's."""
    return {
        "version_id": version_id,
        "decision_id": decision_id,
        "instrument_version": "prep6-test",
        "started_at": STARTED,
        "finished_at": FINISHED,
        "command_handling_ms": 0,
    }


def _review(
    session_id: int, claim_key: str = "calc.1", disposition: str = "accepted", **row: Any
) -> dict[str, Any]:
    """A claim review row of ``session_id``."""
    return {
        "session_id": session_id,
        "ordinal": 0,
        "claim_key": claim_key,
        "disposition": disposition,
        "category": "none",
        "elapsed_ms": 1000,
        "locate_seconds": 0,
        "check_seconds": 0,
    } | row


def _rows(conn: psycopg.Connection) -> tuple[Any, ...]:
    """Every stored telemetry row, to show a refusal wrote nothing."""
    return (
        conn.execute("SELECT * FROM eqos.review_sessions ORDER BY id").fetchall(),
        conn.execute("SELECT * FROM eqos.claim_reviews ORDER BY id").fetchall(),
    )


def _write(conn: psycopg.Connection, session: dict[str, Any], key: str | None) -> None:
    """Insert ``session`` and, when ``key`` is given, one claim review of it."""
    session_id = _insert(conn, "review_sessions", session)
    if key is not None:
        _insert(conn, "claim_reviews", _review(session_id, key))


# Each case: (role, the refused write, expected error, message fragment).
Case = tuple[PgRole | None, Callable[[psycopg.Connection, Rig], Any], type[Exception], str]
REFUSALS: dict[str, Case] = {
    "claim_of_another_version": (
        PgRole.OWNER,
        lambda c, r: _write(c, _session(r.version, r.decided), OTHER_KEY),
        errors.CheckViolation,
        "is not a claim of session",
    ),
    "decision_on_another_version": (
        PgRole.OWNER,
        lambda c, r: _write(c, _session(r.version, r.other_decided), None),
        errors.CheckViolation,
        "is not an owner review decision",
    ),
    "submit_decision": (
        PgRole.OWNER,
        lambda c, r: _write(c, _session(r.version, r.submitted), None),
        errors.CheckViolation,
        "is not an owner review decision",
    ),
    "panel_decision": (
        PgRole.OWNER,
        lambda c, r: _write(c, _session(r.panel_version, r.panel_decided), None),
        errors.CheckViolation,
        "is not an owner review decision",
    ),
    "runtime_insert": (
        PgRole.RUNTIME,
        lambda c, r: _write(c, _session(r.version, r.decided), None),
        errors.InsufficientPrivilege,
        "review_sessions",
    ),
    "panel_insert": (
        PgRole.PANEL,
        lambda c, r: _write(c, _session(r.version, r.decided), None),
        errors.InsufficientPrivilege,
        "review_sessions",
    ),
    "migrator_update": (
        None,
        lambda c, r: c.execute("UPDATE eqos.review_sessions SET command_handling_ms = 1"),
        errors.RaiseException,
        "immutable",
    ),
}


@pytest.mark.parametrize("case", REFUSALS)
def test_telemetry_schema_refuses_all_but_the_owner_review_of_its_version(
    rig: Rig, pg_db: PgTestDatabase, case: str
) -> None:
    """Telemetry must describe the owner's review decision on the version it decided: a claim
    of another version, a decision on another version, a SUBMIT, a panel decision, a runtime or
    panel insert and any update are refused with nothing written. The SQLSTATE is asserted so an
    ACL error cannot pass for a missing trigger."""
    role, write, error, fragment = REFUSALS[case]
    with rig.ledger.pools[PgRole.OWNER].connection() as owner:
        if role is None:  # an existing row to update
            with owner.transaction():
                _write(owner, _session(rig.version, rig.decided), "calc.1")
        before = _rows(owner)
        if role is None:
            with pg_db.migrator_connection() as conn, pytest.raises(error, match=fragment):
                write(conn, rig)
        else:
            with rig.ledger.pools[role].connection() as conn:
                with pytest.raises(error, match=fragment), conn.transaction():
                    write(conn, rig)
        assert _rows(owner) == before


CATEGORY_CASES = [
    ("accepted", "wrong_value", "category_rule"),
    ("edited", "none", "category_rule"),
    ("rejected", "none", "category_rule"),
    ("ACCEPTED", "NONE", "claim_reviews_"),
    ("accepted", "none", None),
    ("edited", "wording", None),
    ("deferred", "none", None),
    ("deferred", "wrong_value", None),
]


@pytest.mark.parametrize(("disposition", "category", "refused_by"), CATEGORY_CASES)
def test_telemetry_schema_category_rule_matches_the_validator(
    rig: Rig, disposition: str, category: str, refused_by: str | None
) -> None:
    """The stored rule must equal the review validator's, or SQL and Python disagree on what a
    review may say: accepted takes ``none``, edited and rejected a correction category, deferred
    either; values are the enums' lowercase ones."""
    with rig.ledger.pools[PgRole.OWNER].connection() as conn:
        with conn.transaction():
            session_id = _insert(conn, "review_sessions", _session(rig.version, rig.decided))
        row = _review(session_id, disposition=disposition, category=category)
        if refused_by is None:
            with conn.transaction():
                _insert(conn, "claim_reviews", row)
            assert conn.execute(
                "SELECT disposition, category FROM eqos.claim_reviews WHERE session_id = %s",
                (session_id,),
            ).fetchall() == [(disposition, category)]
            return
        with pytest.raises(errors.CheckViolation) as refused, conn.transaction():
            _insert(conn, "claim_reviews", row)
        assert (refused.value.diag.constraint_name or "").startswith(refused_by)
        assert conn.execute("SELECT count(*) FROM eqos.claim_reviews").fetchone() == (0,)
