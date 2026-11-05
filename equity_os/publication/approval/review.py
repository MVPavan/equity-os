"""The owner's review of a ledger version (PREP-6 decisions 2, 4–6, 8).

The reviewer works in a session file; ``finish`` writes the version's decision, the session and
every claim event in the caller's (owner) transaction, so telemetry exists only with its
decision. A successor whose section bodies are its predecessor's is reviewed only on claims not
accepted unchanged there; any other version is reviewed whole.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, LiteralString

from psycopg import Cursor
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from equity_os.contracts.publication.ledger import (
    DecisionKind,
    DecisionRecord,
    SubjectKind,
    VersionDraft,
)
from equity_os.contracts.sourcing.source_catalog import SourceCatalog
from equity_os.publication.approval.lifecycle import record_decision
from equity_os.publication.drafting.display import PLACEHOLDER
from equity_os.publication.drafting.run_draft import HEADING
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store

INSTRUMENT_VERSION = "ledger-review-v1"
SESSION_FILE = "session.json"
_MS = timedelta(milliseconds=1)
_ACCEPTED: LiteralString = (
    "SELECT claim_key FROM (SELECT DISTINCT ON (r.claim_key) r.claim_key, r.disposition "
    "FROM eqos.claim_reviews r JOIN eqos.review_sessions s ON s.id = r.session_id "
    "WHERE s.version_id = %s ORDER BY r.claim_key, r.ordinal DESC) last "
    "WHERE disposition = 'accepted'"
)
_SESSION: LiteralString = (
    "INSERT INTO eqos.review_sessions (version_id, decision_id, instrument_version, started_at, "
    "finished_at, command_handling_ms) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
)
_EVENT: LiteralString = (
    "INSERT INTO eqos.claim_reviews (session_id, ordinal, claim_key, disposition, category, "
    "elapsed_ms, locate_seconds, check_seconds, note) VALUES (%(session_id)s, %(ordinal)s, "
    "%(claim_key)s, %(disposition)s, %(category)s, %(elapsed_ms)s, %(locate_seconds)s, "
    "%(check_seconds)s, %(note)s)"
)
_SESSION_ROW: LiteralString = (
    "SELECT s.id, s.instrument_version, d.kind, s.command_handling_ms, "
    "(SELECT count(*) FROM eqos.numeric_claims c WHERE c.version_id = s.version_id) "
    "FROM eqos.review_sessions s JOIN eqos.decisions d ON d.id = s.decision_id "
    "WHERE s.version_id = %s"
)
_EVENTS: LiteralString = (
    "SELECT claim_key, disposition, category, elapsed_ms, locate_seconds, check_seconds "
    "FROM eqos.claim_reviews WHERE session_id = %s ORDER BY ordinal"
)
# Session durations, in seconds, of the version and of every version on its chain.
_DURATIONS: LiteralString = (
    "WITH RECURSIVE chain (id, predecessor_id) AS (SELECT id, predecessor_id "
    "FROM eqos.report_versions WHERE id = %(version)s UNION ALL SELECT v.id, v.predecessor_id "
    "FROM eqos.report_versions v JOIN chain ON v.id = chain.predecessor_id) "
    "SELECT sum(extract(epoch FROM s.finished_at - s.started_at)) "
    "FILTER (WHERE s.version_id = %(version)s), sum(extract(epoch FROM s.finished_at - "
    "s.started_at)) FROM chain JOIN eqos.review_sessions s ON s.version_id = chain.id"
)
_STALE = "session instrument {found!r} is not the running {expected!r}"
_OUTSIDE = "claim {key!r} is not in version {version_id}'s review set"
_BACKWARDS = "time {at} is before the session's last event at {last}"
_OVER = "locate + check seconds {spent} exceed the {elapsed}s elapsed since the last event"
_UNREVIEWED = "cannot finish: unreviewed claims {keys}"
_NOT_ACCEPTED = "cannot APPROVE: claims not accepted {keys}"
_NO_SESSION = "version {version_id} has no review session"


class Disposition(StrEnum):
    """The reviewer's decision for one claim."""

    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class CorrectionCategory(StrEnum):
    """The reason a claim was edited or rejected."""

    NONE = "none"
    WRONG_VALUE = "wrong_value"
    WRONG_SOURCE = "wrong_source"
    MISSING_CONTEXT = "missing_context"
    CALCULATION = "calculation"
    WORDING = "wording"
    OTHER = "other"


_CORRECTIONS = frozenset({Disposition.EDITED, Disposition.REJECTED})


class ClaimEvent(BaseModel):
    """One disposition of a claim at client time ``at``."""

    model_config = ConfigDict(frozen=True)

    claim_key: str
    disposition: Disposition
    category: CorrectionCategory
    locate_seconds: int = Field(ge=0)
    check_seconds: int = Field(ge=0)
    note: str | None = None
    at: AwareDatetime

    @model_validator(mode="after")
    def _category_matches(self) -> ClaimEvent:
        """Accepted takes ``none``; edited and rejected a correction; deferred either (0040)."""
        if self.disposition is not Disposition.DEFERRED and (
            (self.disposition is Disposition.ACCEPTED) != (self.category is CorrectionCategory.NONE)
        ):
            raise ValueError(f"{self.disposition} does not take category {self.category}")
        return self


class Session(BaseModel):
    """The reviewer's working session file: no record until ``finish``."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    instrument_version: str
    started_at: AwareDatetime
    events: tuple[ClaimEvent, ...] = ()
    command_handling_seconds: float = 0.0


class ReviewSummary(BaseModel):
    """B-04 totals of a version's review; totals only, since n=3 supports no percentile."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    instrument_version: str
    decision: DecisionKind
    claim_count: int
    review_set_count: int
    disposition_counts: dict[Disposition, int]
    category_counts: dict[CorrectionCategory, int]
    session_wall_clock_minutes: float
    report_wall_clock_minutes: float
    elapsed_seconds: float
    locate_seconds_self_reported: int
    check_seconds_self_reported: int
    command_handling_seconds: float


def _bodies(draft: VersionDraft) -> list[tuple[str, str]]:
    """The version's ``(section_key, body)`` pairs in order, less a claim-free run-draft
    heading, which names the pinned prior and so differs on every successor."""
    return [
        (s.section_key, s.body)
        for s in sorted(draft.sections, key=lambda section: section.ordinal)
        if not (s.ordinal == 0 and s.section_key == HEADING and not PLACEHOLDER.search(s.body))
    ]


def unchanged(
    prior: VersionDraft, current: VersionDraft, accepted: frozenset[str]
) -> frozenset[str]:
    """The current claims accepted in, and identical to, the prior version's; none unless the
    two versions' section bodies are equal."""
    if _bodies(prior) != _bodies(current):
        return frozenset()
    before = {claim.claim_key: claim for claim in prior.claims}
    return frozenset(
        c.claim_key
        for c in current.claims
        if c.claim_key in accepted and before.get(c.claim_key) == c
    )


def review_set(cursor: Cursor[Any], version_id: int) -> tuple[str, ...]:
    """The version's claim keys to review, in claim order (decision 6)."""
    current = store.read_version(cursor, version_id)
    keys = tuple(claim.claim_key for claim in current.claims)
    if current.predecessor_id is None:
        return keys
    accepted = frozenset(row[0] for row in cursor.execute(_ACCEPTED, (current.predecessor_id,)))
    if not accepted:
        return keys
    skipped = unchanged(store.read_version(cursor, current.predecessor_id), current, accepted)
    return tuple(key for key in keys if key not in skipped)


def check_instrument(session: Session) -> None:
    """Refuse a session recorded by another instrument version (B-13 symmetry)."""
    if session.instrument_version != INSTRUMENT_VERSION:
        raise ValueError(
            _STALE.format(found=session.instrument_version, expected=INSTRUMENT_VERSION)
        )


def _last(session: Session) -> datetime:
    """The time of the session's last event, or its start."""
    return session.events[-1].at if session.events else session.started_at


def record(session: Session, event: ClaimEvent, keys: tuple[str, ...]) -> Session:
    """The session with ``event`` appended, if its key is in the review set ``keys``, its time
    is not before the last event's and its locate and check time fit the elapsed time."""
    check_instrument(session)
    if event.claim_key not in keys:
        raise ValueError(_OUTSIDE.format(key=event.claim_key, version_id=session.version_id))
    last = _last(session)
    if event.at < last:
        raise ValueError(_BACKWARDS.format(at=event.at, last=last))
    elapsed = (event.at - last).total_seconds()
    spent = event.locate_seconds + event.check_seconds
    if spent > elapsed:
        raise ValueError(_OVER.format(spent=spent, elapsed=elapsed))
    return session.model_copy(update={"events": (*session.events, event)})


def current(session: Session) -> dict[str, ClaimEvent]:
    """Each claim's current disposition: its last event."""
    return {event.claim_key: event for event in session.events}


def finish(
    cursor: Cursor[Any],
    session: Session,
    kind: DecisionKind,
    ruling: str,
    *,
    at: datetime,
    handled: Callable[[Session], Session],
    catalog: SourceCatalog | None = None,
    snapshots: SnapshotStore | None = None,
) -> DecisionRecord:
    """Write the version's decision, the session and every event in the caller's transaction;
    a ``REQUEST_CHANGES`` rejects the claims currently edited or rejected (decision 5).
    ``handled`` adds this command's handling time just before the decision's first insert."""
    check_instrument(session)
    if at < _last(session):
        raise ValueError(_BACKWARDS.format(at=at, last=_last(session)))
    keys = review_set(cursor, session.version_id)
    now = current(session)
    missing = [key for key in keys if key not in now]
    if missing:
        raise ValueError(_UNREVIEWED.format(keys=missing))
    if kind is DecisionKind.APPROVE:
        refused = [key for key in keys if now[key].disposition is not Disposition.ACCEPTED]
        if refused:
            raise ValueError(_NOT_ACCEPTED.format(keys=refused))
    rejected = tuple(key for key in keys if now[key].disposition in _CORRECTIONS)

    def handle() -> None:
        nonlocal session
        session = handled(session)

    decision = record_decision(
        cursor,
        subject_kind=SubjectKind.REPORT_VERSION,
        subject_id=session.version_id,
        kind=kind,
        ruling=ruling,
        catalog=catalog,
        snapshots=snapshots,
        claims=rejected if kind is DecisionKind.REQUEST_CHANGES else (),
        before_insert=handle,
    )
    row = cursor.execute(
        _SESSION,
        (
            session.version_id,
            decision.id,
            session.instrument_version,
            session.started_at,
            at,
            round(session.command_handling_seconds * 1000),
        ),
    ).fetchone()
    assert row is not None
    previous = session.started_at
    for ordinal, event in enumerate(session.events):
        fields = event.model_dump(exclude={"at"})
        cursor.execute(
            _EVENT,
            {
                **fields,
                "session_id": row[0],
                "ordinal": ordinal,
                "elapsed_ms": (event.at - previous) // _MS,
            },
        )
        previous = event.at
    return decision


def summary(cursor: Cursor[Any], version_id: int) -> ReviewSummary:
    """The B-04 totals of the version's review session (decision 8)."""
    row = cursor.execute(_SESSION_ROW, (version_id,)).fetchone()
    if row is None:
        raise LookupError(_NO_SESSION.format(version_id=version_id))
    session_id, instrument, kind, handling_ms, claim_count = row
    events = cursor.execute(_EVENTS, (session_id,)).fetchall()
    durations = cursor.execute(_DURATIONS, {"version": version_id}).fetchone()
    assert durations is not None
    latest = {key: (Disposition(d), CorrectionCategory(c)) for key, d, c, *_ in events}
    return ReviewSummary(
        version_id=version_id,
        instrument_version=instrument,
        decision=DecisionKind(kind),
        claim_count=claim_count,
        review_set_count=len(latest),
        disposition_counts={d: sum(v[0] is d for v in latest.values()) for d in Disposition},
        category_counts={c: sum(v[1] is c for v in latest.values()) for c in CorrectionCategory},
        session_wall_clock_minutes=float(durations[0]) / 60,
        report_wall_clock_minutes=float(durations[1]) / 60,
        elapsed_seconds=sum(event[3] for event in events) / 1000,
        locate_seconds_self_reported=sum(event[4] for event in events),
        check_seconds_self_reported=sum(event[5] for event in events),
        command_handling_seconds=handling_ms / 1000,
    )


def save(session: Session, directory: Path) -> None:
    """Atomically replace the session file in an existing session directory."""
    if not directory.is_dir():
        raise ValueError(f"session directory does not exist: {directory}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".session-", suffix=".tmp", dir=directory)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(session.model_dump_json(indent=2).encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, directory / SESSION_FILE)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load(directory: Path) -> Session:
    """The session in its directory."""
    return Session.model_validate_json((directory / SESSION_FILE).read_bytes())
