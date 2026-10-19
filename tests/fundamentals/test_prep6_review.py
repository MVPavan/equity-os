"""PREP-6 acceptance: owner review telemetry on ledger versions (plan ``docs/plans/PREP-6.md``).

Task 1: migration 0040 stores a review session only beside the owner's review decision on its
version, and a claim review only for a claim of that version. Refusals are provoked by direct
inserts through the real role logins, so the triggers and grants are what is under test.
Task 2: ``fundamentals review`` reviews a submitted version claim by claim and finishes with its
decision, writing the decision and every event in one owner transaction; a successor whose
section bodies are its predecessor's is reviewed only where it changed or was not accepted.
Times come from a scripted ``review_cli._now``, so every persisted duration is exact.
"""

from __future__ import annotations

import io
import itertools
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple

import psycopg
import pytest
from evidence_support import Ingest, ingest, policy
from ledger_support import CONTENT_HASH, CUTOFF, SECTION, Ledger, claim, ledger
from pg_evidence_schema_support import _insert, runtime, seeded
from pg_support import PgTestDatabase
from prep2b_support import QUARTERS, STOCK, Pilot
from psycopg import errors
from retained_support import REPO_ROOT
from test_prep2b_run_draft import dictionary, mapping_set
from test_prep5_rework import QOQ, _correct
from test_transcript_admission import issuer_config

from fundamentals.api import review_cli
from fundamentals.api.cli import main
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    DecisionKind,
    NumericClaim,
    PanelReview,
    ReportSection,
    SubjectKind,
    Verdict,
    VersionDraft,
    VersionStatus,
)
from fundamentals.ledger import lifecycle, review, store
from fundamentals.ledger.review import ClaimEvent, CorrectionCategory, Disposition
from fundamentals.ledger.run_draft import HEADING
from fundamentals.pg.pool import DatabaseUnavailableError
from fundamentals.pg.settings import PgRole

__all__ = ["dictionary", "ingest", "ledger", "mapping_set", "policy", "runtime", "seeded"]
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


# Task 2 ---------------------------------------------------------------------------------------

T0 = datetime(2026, 10, 1, 9, tzinfo=UTC)
HANDLE = timedelta(milliseconds=250)  # every scripted command's handling interval
ACCEPTED, EDITED = Disposition.ACCEPTED, Disposition.EDITED
REJECTED, DEFERRED = Disposition.REJECTED, Disposition.DEFERRED
REVENUE, PBT = "fact.revenue", "fact.profit_before_tax"
GUIDE = "ledger.cables_revenue_growth.annual.consolidated"
LINE_A, LINE_B, LINE_X = "Revenue {{c:a|}}.", "Gap {{c:b|}}.", "The order book is strong."
HEAD = (HEADING, "# Run draft. Prior: version 1.\n\n")
OUTLOOK = ("outlook", "Outlook {{c:g|}}.\n")
CLAIMS = tuple(claim(1, key) for key in "abg")


def _results(*lines: str) -> tuple[str, str]:
    """A results section of ``lines``."""
    return ("results", "\n".join(lines) + "\n")


BASE = (HEAD, _results(LINE_A, LINE_B, LINE_X), OUTLOOK)


def _version(
    sections: tuple[tuple[str, str], ...], claims: tuple[NumericClaim, ...]
) -> VersionDraft:
    """A version of ``(section_key, body)`` sections in ordinal order."""
    return VersionDraft(
        report_id=1,
        author="runtime",
        knowledge_cutoff=CUTOFF,
        content_hash=CONTENT_HASH,
        sections=tuple(
            ReportSection(ordinal=ordinal, section_key=key, body=body)
            for ordinal, (key, body) in enumerate(sections)
        ),
        claims=claims,
    )


def _with(key: str, **update: Any) -> tuple[NumericClaim, ...]:
    """``CLAIMS`` with claim ``key`` changed."""
    return tuple(c.model_copy(update=update) if c.claim_key == key else c for c in CLAIMS)


def _event(key: str, disposition: Disposition, at: datetime = T0) -> ClaimEvent:
    """A disposition with a category it takes and no self-reported time."""
    corrected = disposition in (EDITED, REJECTED)
    category = CorrectionCategory.WORDING if corrected else CorrectionCategory.NONE
    return ClaimEvent(
        claim_key=key,
        disposition=disposition,
        category=category,
        locate_seconds=0,
        check_seconds=0,
        at=at,
    )


ALL = (("a", ACCEPTED), ("b", ACCEPTED), ("g", ACCEPTED))
# name: (prior sections, prior events in order, current sections, current claims, expected).
UNCHANGED: dict[str, tuple[Any, ...]] = {
    "base": (BASE, ALL, BASE, CLAIMS, {"a", "b", "g"}),
    "value": (BASE, ALL, BASE, _with("a", value=Decimal("12.35")), {"b", "g"}),
    "epistemic_class": (
        BASE,
        ALL,
        BASE,
        _with("a", epistemic_class=EpistemicClass.OBSERVED),
        {"b", "g"},
    ),
    "citation_id": (
        BASE,
        ALL,
        BASE,
        _with("a", citation=Citation(kind=CitationKind.CALCULATION, calculation_trace_id=2)),
        {"b", "g"},
    ),
    "new_key": (BASE, ALL, BASE, (*CLAIMS, claim(1, "n")), {"a", "b", "g"}),
    "deferred": (BASE, (*ALL, ("a", DEFERRED)), BASE, CLAIMS, {"b", "g"}),
    "accepted_then_edited": (BASE, (*ALL, ("a", EDITED)), BASE, CLAIMS, {"b", "g"}),
    "heading_only": (
        BASE,
        ALL,
        ((HEADING, "# Run draft. Prior: version 2.\n\n"), *BASE[1:]),
        CLAIMS,
        {"a", "b", "g"},
    ),
    # Any other section difference: every key is reviewed.
    "line_text": (
        BASE,
        ALL,
        (HEAD, _results("Sales {{c:a|}}.", LINE_B, LINE_X), OUTLOOK),
        CLAIMS,
        set(),
    ),
    "explanatory_line": (
        BASE,
        ALL,
        (HEAD, _results(LINE_A, LINE_B, "Orders grew."), OUTLOOK),
        CLAIMS,
        set(),
    ),
    "deleted_rejected_line": (
        BASE,
        (("a", ACCEPTED), ("b", REJECTED), ("g", ACCEPTED)),
        (HEAD, _results(LINE_A, LINE_X), OUTLOOK),
        (CLAIMS[0], CLAIMS[2]),
        set(),
    ),
    "swapped_lines": (BASE, ALL, (HEAD, _results(LINE_B, LINE_A, LINE_X), OUTLOOK), CLAIMS, set()),
    "moved_across_line": (
        BASE,
        ALL,
        (HEAD, _results(LINE_B, LINE_X, LINE_A), OUTLOOK),
        CLAIMS,
        set(),
    ),
    "swapped_sections": (BASE, ALL, (HEAD, OUTLOOK, BASE[1]), CLAIMS, set()),
    **{
        f"ordinal_0_{key}": (
            ((key, LINE_A + "\n"), _results(LINE_B, LINE_X), OUTLOOK),
            ALL,
            ((key, "Sales {{c:a|}}.\n"), _results(LINE_B, LINE_X), OUTLOOK),
            CLAIMS,
            set(),
        )
        for key in (SECTION.section_key, HEADING)
    },
}


@pytest.mark.parametrize("case", UNCHANGED)
def test_unchanged_is_only_an_accepted_identical_claim_of_identical_sections(case: str) -> None:
    """A claim wrongly treated as unchanged is approved unseen: only a claim whose last prior
    disposition is accepted and whose whole row is the prior's is skipped, and only when every
    section body but a claim-free run-draft heading (which names the pinned prior) is the
    prior's in order; a heading-keyed section carrying a claim is compared like any other."""
    prior_sections, events, sections, claims, expected = UNCHANGED[case]
    session = review.Session(
        version_id=1,
        instrument_version=review.INSTRUMENT_VERSION,
        started_at=T0,
        events=tuple(_event(key, disposition) for key, disposition in events),
    )
    accepted = frozenset(k for k, e in review.current(session).items() if e.disposition is ACCEPTED)
    prior = _version(prior_sections, CLAIMS)
    assert review.unchanged(prior, _version(sections, claims), accepted) == expected


def _env(pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI at the test database."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)


def _cli(*argv: str) -> int:
    """``fundamentals review …``."""
    return main(["review", *argv])


def _start(version: int, session: Path) -> int:
    """``review start``."""
    return _cli("start", "--version", str(version), "--session", str(session))


def _claim(
    session: Path, key: str, disposition: Disposition, *, seconds: tuple[int, int] = (0, 0)
) -> int:
    """``review claim`` with the category ``_event`` gives and ``seconds`` (locate, check)."""
    event = _event(key, disposition)
    locate, check = seconds
    return _cli(
        "claim",
        "--session",
        str(session),
        "--claim",
        key,
        "--disposition",
        disposition.value,
        "--category",
        event.category.value,
        "--locate-seconds",
        str(locate),
        "--check-seconds",
        str(check),
    )


def _finish(
    monkeypatch: pytest.MonkeyPatch, session: Path, kind: DecisionKind, *sources: str
) -> int:
    """``review finish`` with the ruling on stdin."""
    monkeypatch.setattr("sys.stdin", io.StringIO("TEST: review ruling"))
    return _cli("finish", "--session", str(session), "--decision", kind.value, *sources)


def _summary(capsys: pytest.CaptureFixture[str], version: int) -> dict[str, Any]:
    """``review summary`` as parsed JSON."""
    capsys.readouterr()
    assert _cli("summary", "--version", str(version)) == 0
    found: dict[str, Any] = json.loads(capsys.readouterr().out)
    return found


def _ticking(monkeypatch: pytest.MonkeyPatch, start: datetime) -> None:
    """A review clock one second later at every read."""
    ticks = itertools.count()
    monkeypatch.setattr(review_cli, "_now", lambda: start + timedelta(seconds=next(ticks)))


def _scripted(monkeypatch: pytest.MonkeyPatch, times: list[datetime]) -> Iterator[datetime]:
    """A review clock reading ``times`` in order; the iterator is returned to check it ran out."""
    reads = iter(times)
    monkeypatch.setattr(review_cli, "_now", lambda: next(reads))
    return reads


_TELEMETRY_COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.decisions), (SELECT count(*) FROM eqos.validations), "
    "(SELECT count(*) FROM eqos.validation_claim_states), "
    "(SELECT count(*) FROM eqos.review_sessions), (SELECT count(*) FROM eqos.claim_reviews)"
)
_SESSION_ROW = (
    "SELECT s.instrument_version, s.started_at, s.finished_at, s.command_handling_ms, d.kind, "
    "d.rejected_claims FROM eqos.review_sessions s JOIN eqos.decisions d ON d.id = s.decision_id "
    "WHERE s.version_id = %s"
)
_EVENT_ROWS = (
    "SELECT r.ordinal, r.claim_key, r.disposition, r.category, r.elapsed_ms, r.locate_seconds, "
    "r.check_seconds FROM eqos.claim_reviews r JOIN eqos.review_sessions s "
    "ON s.id = r.session_id WHERE s.version_id = %s ORDER BY r.ordinal"
)


def test_review_cli_bounds_time_and_instrument_version(
    ledger: Ledger, pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-claim time is derived, so it must not run backwards, a self-reported locate and
    check time must fit inside it, and the finish must not precede the last event; a session
    from another instrument version breaks B-13's one-instrument symmetry. Each refusal writes
    nothing; the boundary values are accepted."""
    _env(pg_db, monkeypatch)
    version = ledger.draft(ledger.report())
    ledger.submit(version)
    moment = [T0]
    monkeypatch.setattr(review_cli, "_now", lambda: moment[0])
    session = tmp_path / "session"
    assert _start(version, session) == 0

    def at(seconds: int) -> Path:
        moment[0] = T0 + timedelta(seconds=seconds)
        return session

    assert _claim(at(10), "calc.1", ACCEPTED, seconds=(6, 5)) == 2  # 11 s spent in 10
    assert _claim(at(10), "calc.1", ACCEPTED, seconds=(5, 5)) == 0
    assert _claim(at(9), "calc.1", ACCEPTED) == 2  # before the last event
    path = session / review.SESSION_FILE
    good = path.read_text()
    path.write_text(good.replace(review.INSTRUMENT_VERSION, "ledger-review-v0"))
    assert _claim(at(20), "calc.1", ACCEPTED) == 2
    assert _finish(monkeypatch, at(20), DecisionKind.REQUEST_CHANGES) == 2
    path.write_text(good)
    assert _finish(monkeypatch, at(9), DecisionKind.REQUEST_CHANGES) == 2
    assert ledger.head(version).kind is DecisionKind.SUBMIT
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        assert conn.execute("SELECT count(*) FROM eqos.review_sessions").fetchone() == (0,)
    assert _finish(monkeypatch, at(10), DecisionKind.REQUEST_CHANGES) == 0
    with ledger.pools[PgRole.RUNTIME].connection() as conn:
        found = conn.execute(_SESSION_ROW, (version,)).fetchall()
        events = conn.execute(_EVENT_ROWS, (version,)).fetchall()
    assert found == [
        (review.INSTRUMENT_VERSION, T0, T0 + timedelta(seconds=10), 0, "REQUEST_CHANGES", None)
    ]
    assert events == [(0, "calc.1", "accepted", "none", 10_000, 5, 5)]


@pytest.mark.parametrize("failure", ["unknown_version", "database_unavailable"])
def test_review_cli_refuses_without_a_traceback(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    """The review CLI shares the ledger CLI's exception boundary: an unknown version and an
    unreachable database exit 2 with a logged refusal and open no session."""
    _env(pg_db, monkeypatch)
    expected = "LookupError"
    if failure == "database_unavailable":
        expected = "DatabaseUnavailableError"

        def down(*args: Any, **kwargs: Any) -> Any:
            raise DatabaseUnavailableError("no connection")

        monkeypatch.setattr(review_cli, "open_pool", down)
    session = tmp_path / "session"
    assert _start(2**40, session) == 2
    assert expected in capsys.readouterr().err
    assert not session.exists()


@pytest.fixture
def submitted(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ingest: Ingest
) -> tuple[Pilot, int]:
    """The pilot with FY26_Q2's run draft submitted (``IN_REVIEW``)."""
    pilot = Pilot(pg_db, tmp_path, monkeypatch, ingest)
    version = pilot.run("FY26_Q2").draft_version_id
    assert version is not None
    with pg_db.runtime_pool() as runtime_pool:
        lifecycle.submit(runtime_pool, version, **pilot.sources())
    return pilot, version


def _review_set(pilot: Pilot, version: int) -> tuple[str, ...]:
    """The version's review set, read as the runtime role."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return review.review_set(conn.cursor(), version)


def _status(pilot: Pilot, version: int) -> VersionStatus:
    """The version's status."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return lifecycle.version_status(conn.cursor(), version)


def _sources(pilot: Pilot) -> list[str]:
    """The ``finish`` flags giving the pilot's catalog and snapshots, for an approval check."""
    flags = ["--stock", STOCK, "--snapshot-root", str(pilot.rig.snapshots)]
    flags += ["--watchlist", str(REPO_ROOT / DEFAULT_WATCHLIST)]
    return flags + [flag for q in QUARTERS for flag in ("--issuer-config", str(issuer_config(q)))]


def _times(start: datetime, gaps: list[timedelta], finished: datetime) -> list[datetime]:
    """Every clock read of ``start``, one ``claim`` per gap and ``finish``: each command's entry
    then its entry plus ``HANDLE``."""
    claims = list(itertools.accumulate(gaps, initial=start))[1:]
    entries = [start, *claims, finished]
    return [moment for entry in entries for moment in (entry, entry + HANDLE)]


def test_review_records_telemetry_with_its_decision_and_rereviews_only_what_was_not_accepted(
    submitted: tuple[Pilot, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The roadmap acceptance: every disposition, category and derived time is stored with the
    decision, exactly as the scripted clock implies, and the edited and rejected claims drive
    PREP-5's rework. The unchanged successor is reviewed only on the claims not accepted in N,
    and B-04's report time is the whole report's review (30 + 5 minutes), not its last
    version's."""
    pilot, version = submitted
    keys = _review_set(pilot, version)
    assert {REVENUE, GUIDE, PBT} <= set(keys) and len(keys) < 60
    special = {REVENUE: REJECTED, PBT: DEFERRED}
    plan = [(key, special.get(key, ACCEPTED)) for key in keys] + [(GUIDE, EDITED)]
    gaps = [timedelta(seconds=20 + i % 5) for i in range(len(plan))]
    finished = T0 + timedelta(minutes=30)
    reads = _scripted(monkeypatch, _times(T0, gaps, finished))
    session = tmp_path / "review-n"
    assert _start(version, session) == 0
    for key, disposition in plan:
        assert _claim(session, key, disposition, seconds=(3, 2)) == 0
    assert _finish(monkeypatch, session, DecisionKind.REQUEST_CHANGES) == 0
    assert next(reads, None) is None
    ((instrument, started, ended, handling_ms, kind, rejected),) = pilot.query(
        _SESSION_ROW, version
    )
    assert (instrument, started, ended, kind) == (
        review.INSTRUMENT_VERSION,
        T0,
        finished,
        "REQUEST_CHANGES",
    )
    assert handling_ms == 250 * (len(plan) + 2)
    assert sorted(rejected) == sorted({REVENUE, GUIDE})
    assert pilot.query(_EVENT_ROWS, version) == [
        (i, key, d.value, _event(key, d).category.value, gap // timedelta(milliseconds=1), 3, 2)
        for i, ((key, d), gap) in enumerate(zip(plan, gaps, strict=True))
    ]
    last = {key: _event(key, d) for key, d in plan}
    summary = _summary(capsys, version)
    assert summary == {
        "version_id": version,
        "instrument_version": review.INSTRUMENT_VERSION,
        "decision": "REQUEST_CHANGES",
        "claim_count": len(keys),
        "review_set_count": len(keys),
        "disposition_counts": {
            d.value: sum(e.disposition is d for e in last.values()) for d in Disposition
        },
        "category_counts": {
            c.value: sum(e.category is c for e in last.values()) for c in CorrectionCategory
        },
        "session_wall_clock_minutes": 30.0,
        "report_wall_clock_minutes": 30.0,
        "elapsed_seconds": sum(gaps, timedelta()).total_seconds(),
        "locate_seconds_self_reported": 3 * len(plan),
        "check_seconds_self_reported": 2 * len(plan),
        "command_handling_seconds": 0.25 * (len(plan) + 2),
    }
    assert summary["disposition_counts"] == {
        "accepted": len(keys) - 3,
        "edited": 1,
        "rejected": 1,
        "deferred": 1,
    }
    # The rework run with no correction: section bodies and re-derived rows are N's.
    successor = pilot.run("FY26_Q2").draft_version_id
    assert successor is not None
    with pilot.pg_db.runtime_pool() as runtime_pool:
        lifecycle.submit(runtime_pool, successor, **pilot.sources())
    rereview = _review_set(pilot, successor)
    assert set(rereview) == {REVENUE, GUIDE, PBT}
    restart = finished + timedelta(hours=1)
    gaps = [timedelta(seconds=60)] * len(rereview)
    _scripted(monkeypatch, _times(restart, gaps, restart + timedelta(minutes=5)))
    session = tmp_path / "review-n1"
    assert _start(successor, session) == 0
    for key in rereview:
        assert _claim(session, key, ACCEPTED) == 0
    assert _finish(monkeypatch, session, DecisionKind.APPROVE, *_sources(pilot)) == 0
    assert _status(pilot, successor) is VersionStatus.APPROVED
    summary = _summary(capsys, successor)
    assert (summary["session_wall_clock_minutes"], summary["report_wall_clock_minutes"]) == (
        5.0,
        35.0,
    )
    assert summary["claim_count"] == len(keys) and summary["review_set_count"] == 3


def test_review_refusals_write_nothing_and_a_reject_keeps_its_review(
    submitted: tuple[Pilot, int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A key outside the review set, an unreviewed key and an APPROVE over a rejected claim are
    refused before any write; a telemetry insert failing after the decision insert rolls the
    decision and its validation back too, so telemetry exists only with its decision and the
    reverse. A REJECT carries no keys (0039) yet stores the whole review; a version no longer
    IN_REVIEW cannot be finished."""
    pilot, version = submitted
    keys = _review_set(pilot, version)
    _ticking(monkeypatch, T0)
    session = tmp_path / "session"
    assert _start(version, session) == 0
    before = pilot.query(_TELEMETRY_COUNTS)
    assert _claim(session, "fact.not_a_claim", ACCEPTED) == 2
    for key in keys:
        if key != REVENUE:
            assert _claim(session, key, ACCEPTED) == 0
    assert _finish(monkeypatch, session, DecisionKind.REQUEST_CHANGES) == 2
    assert _claim(session, REVENUE, REJECTED) == 0
    assert _finish(monkeypatch, session, DecisionKind.APPROVE, *_sources(pilot)) == 2
    assert _claim(session, REVENUE, ACCEPTED) == 0
    assert pilot.query(_TELEMETRY_COUNTS) == before
    original = review._EVENT
    monkeypatch.setattr(review, "_EVENT", original.replace("%(claim_key)s", "'fact.not_a_claim'"))
    capsys.readouterr()
    assert _finish(monkeypatch, session, DecisionKind.APPROVE, *_sources(pilot)) == 2
    assert "is not a claim of session" in capsys.readouterr().err
    assert pilot.query(_TELEMETRY_COUNTS) == before
    assert _status(pilot, version) is VersionStatus.IN_REVIEW
    monkeypatch.setattr(review, "_EVENT", original)
    assert _claim(session, REVENUE, REJECTED) == 0
    assert _claim(session, GUIDE, EDITED) == 0
    assert _finish(monkeypatch, session, DecisionKind.REJECT) == 0
    events = len(review.load(session).events)
    ((*_, kind, rejected),) = pilot.query(_SESSION_ROW, version)
    assert (kind, rejected) == ("REJECT", None)
    assert len(pilot.query(_EVENT_ROWS, version)) == events
    after = pilot.query(_TELEMETRY_COUNTS)
    assert _finish(monkeypatch, session, DecisionKind.REJECT) == 2
    assert pilot.query(_TELEMETRY_COUNTS) == after


def test_review_correction_rereviews_exactly_the_changed_and_rejected_claims(
    submitted: tuple[Pilot, int],
    ingest: Ingest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PREP-5 OQ3: a successor is reviewed on everything that changed or was not accepted.
    Rejecting the revenue QoQ prior and rerunning on the corrected comparator changes the
    three QoQ values; every other claim and every line is N's, so only those three return."""
    pilot, version = submitted
    _ticking(monkeypatch, T0)
    session = tmp_path / "session"
    assert _start(version, session) == 0
    for key in _review_set(pilot, version):
        assert _claim(session, key, REJECTED if key == QOQ[0] else ACCEPTED) == 0
    assert _finish(monkeypatch, session, DecisionKind.REQUEST_CHANGES) == 0
    _, rerun = _correct(pilot, ingest)
    successor = rerun().draft_version_id
    assert successor is not None
    assert set(_review_set(pilot, successor)) == set(QOQ)
