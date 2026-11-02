"""PREP-6 acceptance, split from ``test_prep6_review.py`` at the 800-line ceiling: the end-to-end
review of a submitted pilot version and the seeded-error drill (``docs/plans/PREP-6.md``).
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Collection, Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import Ingest
from pg_support import PgTestDatabase
from prep2b_support import QUARTERS, RULING, STOCK, Pilot
from retained_support import REPO_ROOT
from test_prep5_rework import CONDUCTOR, QOQ, _correct
from test_prep6_review import (
    _EVENT_ROWS,
    _SESSION_ROW,
    _TELEMETRY_COUNTS,
    ACCEPTED,
    DEFERRED,
    EDITED,
    GUIDE,
    HANDLE,
    PBT,
    REJECTED,
    REVENUE,
    T0,
    V,
    _claim,
    _event,
    _finish,
    _scripted,
    _start,
    _summary,
    _ticking,
    dictionary,
    ingest,
    ledger,
    mapping_set,
    policy,
    runtime,
    seeded,
)
from test_transcript_admission import issuer_config

from fundamentals.api import review_cli
from fundamentals.api.ledger_cli import DEFAULT_WATCHLIST
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    ClaimState,
    DecisionKind,
    NumericClaim,
    ReportKind,
    Validation,
    VersionDraft,
    VersionStatus,
)
from fundamentals.ledger import display, lifecycle, review, store
from fundamentals.ledger.review import CorrectionCategory, Disposition

__all__ = ["dictionary", "ingest", "ledger", "mapping_set", "policy", "runtime", "seeded"]


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


@pytest.mark.pg
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
    assert {REVENUE, GUIDE, PBT} <= set(keys) and len(keys) < 100
    none, wrong_value, wording = (
        CorrectionCategory.NONE,
        CorrectionCategory.WRONG_VALUE,
        CorrectionCategory.WORDING,
    )
    special = {REVENUE: (REJECTED, wrong_value), PBT: (DEFERRED, none)}
    plan = [(key, *special.get(key, (ACCEPTED, none))) for key in keys] + [(GUIDE, EDITED, wording)]
    gaps = [timedelta(seconds=15 + i % 5) for i in range(len(plan))]
    finished = T0 + timedelta(minutes=30)
    reads = _scripted(monkeypatch, _times(T0, gaps, finished))
    session = tmp_path / "review-n"
    assert _start(version, session) == 0
    for key, disposition, category in plan:
        assert _claim(session, key, disposition, category, seconds=(3, 2)) == 0
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
    events = pilot.query(_EVENT_ROWS, version)
    assert events == [
        (i, key, d.value, c.value, gap // timedelta(milliseconds=1), 3, 2)
        for i, ((key, d, c), gap) in enumerate(zip(plan, gaps, strict=True))
    ]
    assert {row[1]: row[3] for row in events if row[2] in ("edited", "rejected")} == {
        REVENUE: "wrong_value",
        GUIDE: "wording",
    }
    last = {key: _event(key, d, category=c) for key, d, c in plan}
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
    assert {c: n for c, n in summary["category_counts"].items() if n} == {
        "none": len(keys) - 2,
        "wrong_value": 1,
        "wording": 1,
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
    scripted, check, lag = review_cli._now, lifecycle.approval_check, [timedelta()]

    def checking(*args: Any, **kwargs: Any) -> Validation:
        """The approval check inside ``record_decision``, taking 4 s."""
        lag[0] += timedelta(seconds=4)
        return check(*args, **kwargs)

    monkeypatch.setattr(review_cli, "_now", lambda: scripted() + lag[0])
    monkeypatch.setattr(lifecycle, "approval_check", checking)
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
    # finish's 4 s approval check counts towards its handling time.
    assert summary["command_handling_seconds"] == 0.25 * (len(rereview) + 2) + 4
    assert summary["claim_count"] == len(keys) and summary["review_set_count"] == 3


@pytest.mark.pg
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


@pytest.mark.pg
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


# Task 3 ---------------------------------------------------------------------------------------

PAT, EXPENSES, GAP = "fact.profit_for_period", "fact.total_expenses", "calc.1"
INCOME_QOQ, INCOME_YOY = "cmp.total_income.qoq.prior", "cmp.total_income.yoy.prior"
YOY_PRIOR = "cmp.revenue.yoy.prior"
# Every seeded claim key (decision 7) and the state the check must give it.
ANSWER = {
    EXPENSES: ClaimState.VALUE_MISMATCH,  # G1 value
    INCOME_QOQ: ClaimState.KEY_MISMATCH,  # G2 period
    GAP: ClaimState.VALUE_MISMATCH,  # G3 calculation
    CONDUCTOR: ClaimState.QUOTE_MEANING_MISMATCH,  # G4 guidance bounds
    PBT: ClaimState.MATCH,  # R1 swapped lines
    PAT: ClaimState.MATCH,  # R1
    QOQ[0]: ClaimState.MATCH,  # R2 wrong comparator
    GUIDE: ClaimState.MATCH,  # R3 guidance labelled observed
}
R1 = {f"{{{{c:{PBT}|": f"{{{{c:{PAT}|", f"{{{{c:{PAT}|": f"{{{{c:{PBT}|"}
G5 = {"Reported consolidated figures:": "Reported consolidated figures across 3 segments:"}
# Script name: the seeded keys it accepts.
SCRIPTS = {"perfect": frozenset[str](), "misses_r1": frozenset({PBT, PAT})}


class Outcome(StrEnum):
    """A drill claim's score against the answer key."""

    CAUGHT = "CAUGHT"
    MISSED = "MISSED"
    FALSE_REJECT = "FALSE_REJECT"
    CORRECT = "CORRECT"
    FALSE_DEFER = "FALSE_DEFER"


def _seeds(clean: Mapping[str, NumericClaim]) -> dict[str, dict[str, Any]]:
    """Decision 7's claim mutations of the clean draft (R1 is a text seed)."""
    yoy, income = clean[YOY_PRIOR], clean[INCOME_QOQ].measurement_key
    assert income is not None and clean[INCOME_YOY].measurement_key is not None
    return {
        EXPENSES: {"value": (clean[EXPENSES].value or 0) + 1},
        INCOME_QOQ: {
            "measurement_key": income.model_copy(
                update={"period": clean[INCOME_YOY].measurement_key.period}
            )
        },
        GAP: {"value": (clean[GAP].value or 0) + Decimal("0.01")},
        CONDUCTOR: {"upper_bound": (clean[CONDUCTOR].upper_bound or 0) + 1},
        QOQ[0]: {
            "value": yoy.value,
            "measurement_key": yoy.measurement_key,
            "citation": yoy.citation,
        },
        GUIDE: {"epistemic_class": EpistemicClass.OBSERVED},
    }


def _shadow(
    cursor: psycopg.Cursor[Any],
    draft: VersionDraft,
    entity_id: int,
    period: str,
    claims: Mapping[str, Mapping[str, Any]],
    text: Mapping[str, str],
) -> int:
    """A copy of ``draft`` with ``claims`` updated and ``text`` replaced in every section, as
    the root of a new report of ``entity_id`` for ``period``, under a recomputed content hash."""
    pattern = re.compile("|".join(map(re.escape, text)))
    sections = tuple(
        s.model_copy(update={"body": pattern.sub(lambda m: text[m[0]], s.body)})
        for s in draft.sections
    )
    seeded = tuple(c.model_copy(update=claims.get(c.claim_key, {})) for c in draft.claims)
    report = store.create_report(
        cursor, entity_id=entity_id, period=period, kind=ReportKind.EARNINGS_UPDATE
    )
    shadow = draft.model_copy(
        update={
            "report_id": report,
            "predecessor_id": None,
            "sections": sections,
            "claims": seeded,
            "content_hash": display.content_hash(sections, seeded),
        }
    )
    return store.create_version(cursor, shadow)


def _score(answer: Collection[str], dispositions: Mapping[str, Disposition]) -> dict[str, Outcome]:
    """Each claim's outcome: a seed must be edited or rejected, a clean claim accepted."""

    def outcome(key: str, disposition: Disposition) -> Outcome:
        corrected = disposition in (EDITED, REJECTED)
        if key in answer:
            return Outcome.CAUGHT if corrected else Outcome.MISSED
        if corrected:
            return Outcome.FALSE_REJECT
        return Outcome.FALSE_DEFER if disposition is DEFERRED else Outcome.CORRECT

    return {key: outcome(key, d) for key, d in dispositions.items()}


def _verdict(outcomes: Mapping[str, Outcome]) -> tuple[bool, list[str]]:
    """Whether the drill passes, and the keys failing it."""
    failing = sorted(k for k, o in outcomes.items() if o not in (Outcome.CAUGHT, Outcome.CORRECT))
    return not failing, failing


# (seeded, disposition, outcome): every scoring rule; only CAUGHT and CORRECT pass.
SCORING = [
    (True, EDITED, Outcome.CAUGHT),
    (True, REJECTED, Outcome.CAUGHT),
    (True, ACCEPTED, Outcome.MISSED),
    (True, DEFERRED, Outcome.MISSED),
    (False, EDITED, Outcome.FALSE_REJECT),
    (False, REJECTED, Outcome.FALSE_REJECT),
    (False, ACCEPTED, Outcome.CORRECT),
    (False, DEFERRED, Outcome.FALSE_DEFER),
]


@pytest.mark.parametrize(("seeded", "disposition", "outcome"), SCORING)
def test_drill_scores_every_disposition_of_a_seeded_and_a_clean_claim(
    seeded: bool, disposition: Disposition, outcome: Outcome
) -> None:
    """The drill's verdict is only as good as its scoring: a seed must be corrected and a clean
    claim accepted, and every other outcome fails the drill naming the claim."""
    outcomes = _score({"k"} if seeded else set(), {"k": disposition})
    assert outcomes == {"k": outcome}
    passes = outcome in (Outcome.CAUGHT, Outcome.CORRECT)
    assert _verdict(outcomes) == (passes, [] if passes else ["k"])


@pytest.mark.pg
@pytest.mark.parametrize("script", SCRIPTS)
def test_drill_gate_seeds_are_caught_review_seeds_scored_and_a_miss_fails(
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ingest: Ingest,
    script: str,
) -> None:
    """Decision 7's seeded-error drill. This is an instrumentation regression, not a detection
    test: the scripted reviewer holds the answer key, so it proves that gate seeds are caught
    by the deterministic checks, that review seeds pass them (or the drill tests nothing the
    checks don't), that the shadow cannot be approved, and that every disposition and time is
    recorded and scored with REQUEST_CHANGES naming exactly the seeds. A script missing R1 must
    score FAIL, or the drill cannot fail. Detection of review-only seeds is not demonstrated
    (eqos-4j2.30). Everything is written to the disposable test database and ``tmp_path``."""
    pilot = Pilot(pg_db, tmp_path, monkeypatch, ingest)
    version = pilot.run("FY26_Q2").draft_version_id
    assert version is not None
    draft = pilot.version(version)
    clean = {c.claim_key: c for c in draft.claims}
    with pg_db.runtime_pool() as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            shadow = _shadow(cursor, draft, pilot.entity_id, "FY26_Q2_DRILL", _seeds(clean), R1)
            bare = _shadow(cursor, draft, pilot.entity_id, "FY26_Q2_DRILL_G5", {}, G5)
        lifecycle.submit(pool, shadow, **pilot.sources())
        with pytest.raises(lifecycle.DecisionRefusedError, match="UNREGISTERED_NUMBER"):
            lifecycle.submit(pool, bare, **pilot.sources())
    # (a) the checks flag exactly the gate seeds.
    assert any(state is not ClaimState.MATCH for state in ANSWER.values())
    states = dict(pilot.validate(shadow).claim_states)
    assert states == {key: ANSWER.get(key, ClaimState.MATCH) for key in clean}
    # (b) the owner's approval is refused by the check.
    with pg_db.owner_pool() as owner, pytest.raises(lifecycle.DecisionRefusedError):
        lifecycle.decide(
            owner,
            subject_kind=V,
            subject_id=shadow,
            kind=DecisionKind.APPROVE,
            ruling=RULING,
            **pilot.sources(),
        )
    assert _status(pilot, shadow) is VersionStatus.IN_REVIEW
    # (d)/(e) the scripted review through the CLI, scored from the stored rows.
    _ticking(monkeypatch, T0)
    session = tmp_path / "drill"
    assert _start(shadow, session) == 0
    for key in _review_set(pilot, shadow):
        caught = key in ANSWER and key not in SCRIPTS[script]
        assert _claim(session, key, REJECTED if caught else ACCEPTED) == 0
    assert _finish(monkeypatch, session, DecisionKind.REQUEST_CHANGES) == 0
    events = pilot.query(_EVENT_ROWS, shadow)
    assert sorted(key for _, key, *_ in events) == sorted(clean)
    assert all(elapsed > 0 for *_, elapsed, _, _ in events)
    ((*_, kind, rejected),) = pilot.query(_SESSION_ROW, shadow)
    assert (kind, sorted(rejected)) == ("REQUEST_CHANGES", sorted(set(ANSWER) - SCRIPTS[script]))
    outcomes = _score(ANSWER, {key: Disposition(d) for _, key, d, *_ in events})
    assert _verdict(outcomes) == (not SCRIPTS[script], sorted(SCRIPTS[script]))
    expected = {k: Outcome.MISSED if k in SCRIPTS[script] else Outcome.CAUGHT for k in (PBT, PAT)}
    assert {k: outcomes[k] for k in (PBT, PAT)} == expected
    by_class = Counter((clean[k].epistemic_class, o) for k, o in outcomes.items())
    if script == "perfect":
        assert {pair: n for pair, n in by_class.items() if pair[1] is not Outcome.CORRECT} == {
            (EpistemicClass.OBSERVED, Outcome.CAUGHT): 5,
            (EpistemicClass.COMPUTED, Outcome.CAUGHT): 1,
            (EpistemicClass.FORECAST, Outcome.CAUGHT): 2,
        }
