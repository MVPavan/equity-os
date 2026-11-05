"""D3.4 acceptance: the single-reviewer approval panel, disposition proposals and role gating of
the D1b queue commands (plan Task 4; D2, D3, D4, D10, D11).

Decisions run through ``panel.review`` and ``lifecycle.decide`` on the real role pools, with a
fake reviewer (provider and model are data) that records its calls and can run a callback
during one; the triggers are probed by direct SQL as the panel, owner and runtime logins. The
cited cell is one result of a fixture run under a real measurement key, with two first-party
values and two ``REPORTED_VS_DERIVED`` pairs of different identity and difference.

Gap G2: a disposition only closes an item, so "a disposition making a cited cell untrusted" is
tested as its overlay equivalent, a blocking HIGH item linked to the cited run.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from evidence_support import BOTH, dictionary, ingest, mapping_set, policy
from ledger_cited_support import RESULT, RUN, _figure
from ledger_support import RULING, Ledger, ledger
from pg_evidence_schema_support import (
    PERIOD_END,
    PERIOD_START,
    _insert,
    _interpretation,
    runtime,
    seeded,
)
from pg_support import PgTestDatabase
from psycopg import errors, sql
from pydantic import ValidationError
from run_support import Runner, runner
from selection_support import key

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.publication.ledger import (
    ClaimState,
    DecisionKind,
    NumericClaim,
    PanelReview,
    ReportSection,
    ReviewOutput,
    SubjectKind,
    Verdict,
    VersionStatus,
)
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.contracts.verification.comparison import PairKind, SourceRef, SourceRole
from equity_os.contracts.verification.review_queue import (
    DispositionKind,
    QueueItemDraft,
    QueueSeverity,
)
from equity_os.interface.entry.cli import main
from equity_os.publication.approval import lifecycle, panel
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.citations import resolve_citation
from equity_os.publication.drafting.display import content_hash, narrative
from equity_os.storage.database.settings import PgRole
from equity_os.storage.database.test_databases import MAINTENANCE_DB
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store
from equity_os.verification.comparison.run import RunExitStatus
from equity_os.verification.review_queue.queue import (
    insert_disposition,
    lock_queue,
    propose_disposition,
    publish_queue_drafts,
    record_disposition,
)
from equity_os.verification.review_queue.routing import pair_identity

__all__ = ["dictionary", "ingest", "ledger", "mapping_set", "policy", "runner", "runtime", "seeded"]
pytestmark = pytest.mark.pg

V, P = SubjectKind.REPORT_VERSION, SubjectKind.DISPOSITION_PROPOSAL
INTERP = SubjectKind.INTERPRETATION
ACCEPTED = DispositionKind.ACCEPTED_AS_DEFINITION
XBRL = SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.XBRL)
PDF = SourceRef(source_role=SourceRole.FIRST_PARTY, representation=Representation.PDF)
PAIR_A = pair_identity(PairKind.REPORTED_VS_DERIVED, XBRL, PDF)
PAIR_B = pair_identity(PairKind.REPORTED_VS_DERIVED, PDF, XBRL)
DATA = {"provider": "fake", "model": "model-1", "effort": "fixture-effort", "brief_version": "b1"}
SECTION = ReportSection(
    ordinal=0,
    section_key="results",
    body="{{e:observed}} Profit before tax was {{c:fact.cited|group-intl}} crore.",
)


class FakeReviewer:
    """A reviewer that records each call, may act during it, and returns a fixed verdict."""

    provider, model, effort, brief_version = DATA.values()

    def __init__(self, verdict: Verdict = Verdict.APPROVE, during: Callable[[], Any] = list):
        self.verdict, self.during = verdict, during
        self.calls: list[tuple[str, str]] = []

    def review(self, subject_text: str, sealed_digest: str) -> ReviewOutput:
        self.calls.append((subject_text, sealed_digest))
        self.during()
        return ReviewOutput(verdict=self.verdict, rationale=f"fixture rationale {self.verdict}")


class Desk:
    """A seeded ledger with a cited run cell, its pairs and the panel's direct-SQL probes."""

    def __init__(
        self, ledger: Ledger, conn: psycopg.Connection, seeded: dict[str, int], snapshots: Path
    ) -> None:
        self.ledger, self.pools, self.seeded = ledger, ledger.pools, seeded
        self.paths: dict[str, Any] = {
            "catalog": BUILTIN_SOURCES,
            "snapshots": SnapshotStore(snapshots),
        }
        cell_key = key("profit_before_tax", PeriodInterval.duration(PERIOD_START, PERIOD_END))
        self.key = cell_key.model_copy(update={"entity_id": seeded["_entity"]})
        with conn.transaction():
            self.run = _insert(conn, "runs", RUN)
            result = _insert(
                conn,
                "results",
                RESULT
                | {"run_id": self.run, "entity_id": seeded["_entity"]}
                | {"key_digest": self.key.digest(), "corroboration_status": "CORROBORATED"},
            )
            xbrl, pdf = (
                _insert(
                    conn,
                    "result_source_values",
                    {"result_id": result, "source_role": "FIRST_PARTY", "representation": side}
                    | {"source_state": "VALUE", "value": Decimal("3405600000")}
                    | {"interpretation_id": seeded["interpretations"]},
                )
                for side in ("XBRL", "PDF")
            )
            self.pairs = {
                identity: _insert(
                    conn,
                    "pair_outcomes",
                    {"result_id": result, "pair_kind": "REPORTED_VS_DERIVED"}
                    | {"left_value_id": left, "right_value_id": right, "outcome": "MISMATCH"}
                    | {"difference": difference, "pair_identity": identity},
                )
                for identity, left, right, difference in (
                    (PAIR_A, xbrl, pdf, Decimal("-5.25")),
                    (PAIR_B, pdf, xbrl, Decimal("7")),
                )
            }
        with self.cursor(PgRole.RUNTIME) as cursor:
            (self.cutoff,) = cursor.execute("SELECT eqos.store_now()").fetchone() or ()
        cited = _figure(self.key, interpretation_id=seeded["interpretations"], run_id=self.run)
        self.claim = cited.model_copy(update={"value": Decimal("340.56")})

    def cursor(self, role: PgRole) -> Any:
        return self.ledger._cursor(role)  # noqa: SLF001 - the support driver's own transaction

    def item(self, severity: QueueSeverity = QueueSeverity.HIGH) -> int:
        """The cited cell's open item for pair A, linked to the cited run (one per severity)."""
        draft = QueueItemDraft(
            key=self.key,
            pair_identity=PAIR_A,
            outcome="MISMATCH",
            severity=severity,
            routing_reason="MAPPING_DEFINITION_OR_SOURCE_ERROR",
            evidence_interpretation_ids=(self.seeded["interpretations"],),
        )
        with self.cursor(PgRole.RUNTIME) as cursor:
            lock_queue(cursor)
            (item_id,) = publish_queue_drafts(cursor, run_id=self.run, drafts=(draft,))
        return item_id

    def propose(self, item_id: int, kind: DispositionKind = ACCEPTED, pair: str = PAIR_A) -> int:
        pair_id = self.pairs[pair] if kind is ACCEPTED else None
        return propose_disposition(
            self.pools[PgRole.RUNTIME],
            item_id=item_id,
            kind=kind,
            reason="fixture definition",
            evidence_ref="fixture",
            pair_outcome_id=pair_id,
        )

    def version(
        self, *, submit: bool = True, validate: bool = True, claim: NumericClaim | None = None
    ) -> int:
        """A runtime draft on a new report citing the cell (``claim``, else the matching
        one), optionally submitted and checked."""
        claims = (claim or self.claim,)
        draft = self.ledger.version_draft(
            self.ledger.report(),
            knowledge_cutoff=self.cutoff,
            sections=(SECTION,),
            claims=claims,
            content_hash=content_hash((SECTION,), claims),
        )
        with self.cursor(PgRole.RUNTIME) as cursor:
            version_id = store.create_version(cursor, draft)
        if submit:
            lifecycle.submit(self.pools[PgRole.RUNTIME], version_id, **self.paths)
        if validate:
            self.validate(version_id)
        return version_id

    def validate(self, version_id: int) -> Any:
        return lifecycle.validate(
            self.pools[PgRole.RUNTIME], version_id, mode=RunMode.AS_KNOWN, **self.paths
        )

    def review(self, kind: SubjectKind, subject_id: int, reviewer: FakeReviewer) -> Any:
        pool = self.pools[PgRole.PANEL]
        return panel.review(
            pool, subject_kind=kind, subject_id=subject_id, reviewer=reviewer, **self.paths
        )

    def review_row(self, kind: SubjectKind, subject_id: int, **update: Any) -> PanelReview:
        """A panel review of the subject's current digest, with any field replaced."""
        with self.cursor(PgRole.RUNTIME) as cursor:
            digest = store.subject_digest(cursor, kind, subject_id)
        verdict = Verdict.APPROVE if kind is P else Verdict.REJECT
        return PanelReview(
            subject_kind=kind,
            subject_id=subject_id,
            sealed_digest=digest,
            verdict=verdict,
            rationale="direct",
            **DATA,
        ).model_copy(update=update)

    def panel_sql(
        self,
        kind: SubjectKind,
        subject_id: int,
        decision: DecisionKind,
        review: PanelReview | int | None,
        then: Callable[[Any, Any], Any] = lambda cursor, decided: None,
    ) -> Any:
        """One panel transaction: the queue lock (proposals), the review, the decision, then
        ``then``; raises whatever the triggers refuse."""
        with self.cursor(PgRole.PANEL) as cursor:
            if kind is P:
                lock_queue(cursor)
            review_id = (
                store.insert_panel_review(cursor, review)
                if isinstance(review, PanelReview)
                else review
            )
            head = store.chain_head(cursor, kind, subject_id)
            decided = store.insert_decision(
                cursor,
                subject_kind=kind,
                subject_id=subject_id,
                kind=decision,
                predecessor_id=None if head is None else head.id,
                sealed_digest=store.subject_digest(cursor, kind, subject_id),
                panel_review_id=review_id,
            )
            then(cursor, decided)
            return decided

    def owner(self, kind: SubjectKind, subject_id: int, decision: DecisionKind) -> Any:
        fields = {"subject_kind": kind, "subject_id": subject_id, "kind": decision}
        return lifecycle.decide(self.pools[PgRole.OWNER], ruling=RULING, **fields)

    def rows(self, query: str, *params: object) -> list[tuple[Any, ...]]:
        with self.cursor(PgRole.RUNTIME) as cursor:
            return cursor.execute(query, params).fetchall()  # type: ignore[arg-type]


@pytest.fixture
def desk(
    ledger: Ledger, runtime: psycopg.Connection, seeded: dict[str, int], tmp_path: Path
) -> Desk:
    return Desk(ledger, runtime, seeded, tmp_path / "snapshots")


# --- verdict rules (unit)


@pytest.mark.parametrize(
    ("kind", "verdict", "decision"),
    [
        (V, Verdict.APPROVE, DecisionKind.APPROVE),
        (V, Verdict.REQUEST_CHANGES, DecisionKind.REQUEST_CHANGES),
        (V, Verdict.REJECT, DecisionKind.REJECT),
        (P, Verdict.APPROVE, DecisionKind.ACCEPT),
        (P, Verdict.REJECT, DecisionKind.REJECT),
        (P, Verdict.REQUEST_CHANGES, None),
        (INTERP, Verdict.APPROVE, None),
        (SubjectKind.REPORT, Verdict.APPROVE, None),
    ],
)
def test_verdict_rules(kind: SubjectKind, verdict: Verdict, decision: DecisionKind | None) -> None:
    """A verdict maps to one decision kind per subject; a proposal cannot be sent back and the
    panel decides no interpretation or report. A reviewer's output can carry no amount."""
    if decision is None:
        with pytest.raises(DecisionRefusedError):
            panel.verdict_decision(kind, verdict)
    else:
        assert panel.verdict_decision(kind, verdict) is decision
    with pytest.raises(ValidationError):
        ReviewOutput.model_validate({"verdict": verdict, "rationale": "r", "amount": "1"})


# --- report versions


def test_panel_approves_a_version_and_an_overlay_change_leaves_the_approval_bound(
    desk: Desk,
) -> None:
    """A reviewer APPROVE approves, binding the panel's own check written in the deciding
    transaction; its text, provider and model are stored as data. A blocking HIGH item later
    linked to the cited run makes a new validation MATCH_UNTRUSTED; the bound validation, its
    trust at its overlay position and the approval stand."""
    version = desk.version()
    with desk.cursor(PgRole.RUNTIME) as cursor:
        advisory = store.latest_validation(cursor, version)
        draft = store.read_version(cursor, version)
    reviewer = FakeReviewer()
    decision = desk.review(V, version, reviewer)
    assert (decision.kind, decision.decider.value) == (DecisionKind.APPROVE, "PANEL")
    with desk.cursor(PgRole.RUNTIME) as cursor:
        validation = store.latest_validation(cursor, version)
    assert advisory is not None and validation is not None
    assert decision.validation_id == validation.id != advisory.id
    assert validation.claim_states == (("fact.cited", ClaimState.MATCH),)
    assert desk.rows(
        "SELECT v.creator, v.created_xid = d.created_xid FROM eqos.validations v "
        "JOIN eqos.decisions d ON d.validation_id = v.id WHERE d.id = %s",
        decision.id,
    ) == [("PANEL", True)]
    assert reviewer.calls == [
        (narrative(draft.sections, draft.claims).decode(), decision.sealed_digest)
    ]
    rationale = "fixture rationale APPROVE"
    ((stored,),) = desk.rows(
        "SELECT to_jsonb(r) FROM eqos.panel_reviews r WHERE id = %s", decision.panel_review_id
    )
    assert (
        stored.items()
        >= (
            DATA
            | {"verdict": "APPROVE", "rationale": rationale}
            | {"rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest()}
        ).items()
    )

    desk.item()
    later = desk.validate(version)
    assert later.claim_states == (("fact.cited", ClaimState.MATCH_UNTRUSTED),)
    assert desk.rows(
        "SELECT state FROM eqos.validation_claim_states WHERE validation_id = %s", validation.id
    ) == [("MATCH",)]
    with desk.cursor(PgRole.RUNTIME) as cursor:
        then = resolve_citation(
            cursor,
            desk.claim,
            entity_id=desk.seeded["_entity"],
            overlay_position=validation.overlay_position,
            **desk.paths,
        )
        assert then is not None and then.trusted is True
        assert store.chain_head(cursor, V, version) == decision
        assert lifecycle.version_status(cursor, version) is VersionStatus.APPROVED


def test_version_gates_refuse_before_and_after_the_reviewer_call(desk: Desk) -> None:
    """The cited cell holds 340.56, the claim 999999.99: the panel's own check fails and the
    review is refused with no reviewer call, though the runtime wrote a newer forged MATCH
    validation. A check result that changes during the call (a blocking item makes the cell
    untrusted) refuses the review with no review or decision row."""
    wrong = desk.claim.model_copy(update={"value": Decimal("999999.99")})
    unchecked = desk.version(claim=wrong)
    genuine = store_latest(desk, unchecked)
    assert genuine.claim_states == (("fact.cited", ClaimState.VALUE_MISMATCH),)
    forged = genuine.model_copy(
        update={"claim_states": (("fact.cited", ClaimState.MATCH),), "id": None}
    )
    with desk.cursor(PgRole.RUNTIME) as cursor:
        store.insert_validation(cursor, forged)
    reviewer = FakeReviewer()
    with pytest.raises(DecisionRefusedError, match="claim check does not pass"):
        desk.review(V, unchecked, reviewer)
    assert reviewer.calls == []

    version = desk.version(validate=False)
    stale = FakeReviewer(during=desk.item)
    with pytest.raises(panel.ReviewStaleError):
        desk.review(V, version, stale)
    assert len(stale.calls) == 1
    assert desk.ledger.head(version).kind is DecisionKind.SUBMIT
    assert desk.rows("SELECT count(*) FROM eqos.panel_reviews") == [(0,)]


def store_latest(desk: Desk, version: int) -> Any:
    """The version's latest validation."""
    with desk.cursor(PgRole.RUNTIME) as cursor:
        return store.latest_validation(cursor, version)


def test_direct_panel_decisions_need_their_own_fresh_review(desk: Desk) -> None:
    """By direct SQL: no review, another digest, another subject, a review committed earlier,
    a reused review, a verdict that disagrees with the kind, and a panel decision after an
    owner decision are refused."""
    version, other = desk.version(), desk.version()
    reject = DecisionKind.REJECT
    with desk.cursor(PgRole.PANEL) as cursor:
        earlier = store.insert_panel_review(cursor, desk.review_row(V, version))
    unbound = "does not bind"
    for review, kind, reason in (
        (None, reject, "needs a panel review"),
        (desk.review_row(V, version, sealed_digest="0" * 64), reject, unbound),
        (desk.review_row(V, other), reject, unbound),
        (earlier, reject, unbound),
        (desk.review_row(V, version), DecisionKind.REQUEST_CHANGES, unbound),
    ):
        with pytest.raises(errors.CheckViolation, match=reason):
            desk.panel_sql(V, version, kind, review)
    used = desk.panel_sql(V, version, reject, desk.review_row(V, version))
    for subject in (version, other):
        with pytest.raises(errors.CheckViolation, match="illegal|does not bind"):
            desk.panel_sql(V, subject, reject, used.panel_review_id)
    desk.owner(V, other, reject)
    with pytest.raises(errors.CheckViolation, match="illegal decision: REJECT by PANEL"):
        desk.panel_sql(V, other, reject, desk.review_row(V, other))


# --- disposition proposals


def test_panel_accepts_a_proposal_with_its_derived_amount_under_a_lock_timeout(
    desk: Desk,
    pg_db: PgTestDatabase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The runtime proposes through ``compare queue propose`` and may not ``dispose``. The
    panel's acceptance, whose final gate reads the overlay inside the deciding transaction,
    completes under a 5 s lock_timeout and records the pair's absolute difference as the
    amount; a second proposal on the now-closed item is refused with no reviewer call."""
    item = desk.item()
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    command = ["compare", "queue", "propose", "--item", str(item), "--kind", ACCEPTED.value]
    args = ["--reason", "fixture definition", "--evidence-ref", "fixture"]
    assert main([*command, *args, "--pair-outcome", str(desk.pairs[PAIR_A])]) == 0
    proposal = int(capsys.readouterr().out.split("\t")[1])
    monkeypatch.setenv("EQOS_SECRETS_DIR", str(tmp_path))
    dispose = ["compare", "queue", "dispose", "--item", str(item), "--kind", "DISMISSED"]
    assert main([*dispose, "--reason", "r", "--decider", "d", "--evidence-ref", "e"]) == int(
        RunExitStatus.FAILURE
    )

    admin = pg_db.settings.conninfo(PgRole.ADMIN, dbname=MAINTENANCE_DB)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET lock_timeout = '5s'").format(
                sql.Identifier(pg_db.dbname)
            )
        )
    reviewer = FakeReviewer()
    with pg_db.panel_pool() as pool:
        with pool.connection() as conn:
            assert conn.execute("SHOW lock_timeout").fetchone() == ("5s",)
        decision = panel.review(
            pool, subject_kind=P, subject_id=proposal, reviewer=reviewer, **desk.paths
        )
    assert (decision.kind, decision.decider.value, len(reviewer.calls)) == (
        DecisionKind.ACCEPT,
        "PANEL",
        1,
    )
    assert desk.rows(
        "SELECT item_id, kind, decider, explained_amount FROM eqos.queue_dispositions "
        "WHERE evidence_ref = %s",
        f"decision:{decision.id}",
    ) == [(item, ACCEPTED.value, "PANEL", Decimal("5.25"))]

    late, refused = desk.propose(item), FakeReviewer()
    with pytest.raises(DecisionRefusedError, match="not open"):
        desk.review(P, late, refused)
    assert refused.calls == []


def test_pair_binding_and_panel_dispositions_by_direct_sql(desk: Desk) -> None:
    """The other pair of the item's result (same run and key, other difference) cannot be
    bound. A panel disposition without its same-transaction ACCEPT, with another kind or
    another amount, and an ACCEPT without its disposition, are refused."""
    item = desk.item()
    with pytest.raises(errors.CheckViolation, match="is not the pair"):
        desk.propose(item, pair=PAIR_B)
    proposal = desk.propose(item)

    def dispose(**update: Any) -> Callable[[Any, Any], Any]:
        fields = {"item_id": item, "kind": ACCEPTED, "reason": "fixture definition"}
        fields |= {"decider": "PANEL", "explained_amount": Decimal("5.25")}

        def then(cursor: Any, decided: Any) -> None:
            ref = {"evidence_ref": f"decision:{decided and decided.id}"}
            insert_disposition(cursor, **(fields | ref | update))

        return then

    with desk.cursor(PgRole.PANEL) as cursor, pytest.raises(errors.InsufficientPrivilege):
        lock_queue(cursor)
        dispose(evidence_ref="direct")(cursor, None)
    unfollowed = "does not follow its accepted proposal"
    for then, reason in (
        (dispose(kind=DispositionKind.DISMISSED), unfollowed),
        (dispose(explained_amount=Decimal("5.26")), unfollowed),
        (lambda cursor, decided: None, "has no disposition"),
    ):
        with pytest.raises(errors.CheckViolation, match=reason):
            desk.panel_sql(P, proposal, DecisionKind.ACCEPT, desk.review_row(P, proposal), then)
    assert desk.rows(
        "SELECT count(*) FROM eqos.decisions WHERE subject_kind = 'DISPOSITION_PROPOSAL'"
    ) == [(0,)]
    desk.panel_sql(P, proposal, DecisionKind.ACCEPT, desk.review_row(P, proposal), dispose())


def test_owner_decisions_outrank_the_panel(desk: Desk) -> None:
    """An owner disposition, then a fresh proposal: the panel's acceptance is refused, by gate
    with no reviewer call and by trigger. Likewise on proposal B after the owner REJECTs
    proposal A of the same item."""
    disposed, contested = desk.item(), desk.item(QueueSeverity.MEDIUM)
    owner = dict.fromkeys(("reason", "decider", "evidence_ref"), "owner")
    record_disposition(
        desk.pools[PgRole.OWNER], item_id=disposed, kind=DispositionKind.DISMISSED, **owner
    )
    first, second = desk.propose(contested), desk.propose(contested, DispositionKind.DISMISSED)
    desk.owner(P, first, DecisionKind.REJECT)
    for proposal, gate in ((desk.propose(disposed), "not open"), (second, "owner decision")):
        reviewer = FakeReviewer()
        with pytest.raises(DecisionRefusedError, match=gate):
            desk.review(P, proposal, reviewer)
        assert reviewer.calls == []
        with pytest.raises(errors.CheckViolation, match="owner"):
            desk.panel_sql(P, proposal, DecisionKind.ACCEPT, desk.review_row(P, proposal))


def test_an_uncommitted_owner_reject_blocks_the_panel_then_refuses_it(
    desk: Desk, pg_db: PgTestDatabase
) -> None:
    """Two transactions: the owner's uncommitted REJECT of A holds the queue lock, so the
    panel's decision on B waits; once A commits, the panel is refused."""
    item = desk.item()
    first, second = desk.propose(item), desk.propose(item, DispositionKind.DISMISSED)
    review = desk.review_row(P, second)
    outcome: list[BaseException | None] = []

    def panel_decides() -> None:
        try:
            desk.panel_sql(P, second, DecisionKind.ACCEPT, review)
            outcome.append(None)
        except psycopg.Error as error:
            outcome.append(error)

    with psycopg.connect(pg_db.conninfo(PgRole.OWNER)) as owner, owner.cursor() as cursor:
        lifecycle.append_decision(cursor, P, first, DecisionKind.REJECT, ruling=RULING)
        racer = threading.Thread(target=panel_decides)
        racer.start()
        racer.join(timeout=1.0)
        assert racer.is_alive() and outcome == []
        owner.commit()
    racer.join(timeout=30)
    assert len(outcome) == 1 and isinstance(outcome[0], errors.CheckViolation)
    assert "owner" in str(outcome[0])
    with desk.cursor(PgRole.RUNTIME) as cursor:
        assert store.chain_head(cursor, P, second) is None


# --- interpretations and roles


def test_interpretations_are_owner_only_and_sealed_by_their_decision(
    desk: Desk, runtime: psycopg.Connection
) -> None:
    """The panel is refused by trigger and by ``review()`` (no reviewer call), the runtime by
    ``decide``; the owner's ACCEPT succeeds, also on a MANUAL_CORRECTION. An operand insert
    before the decision invalidates the digest it read; one after it is refused."""
    constructed, direct = desk.seeded["_constructed"], desk.seeded["interpretations"]
    for kind in (DecisionKind.ACCEPT, DecisionKind.REJECT):
        with pytest.raises(errors.CheckViolation, match="illegal"):
            desk.panel_sql(INTERP, constructed, kind, None)
    reviewer = FakeReviewer()
    with pytest.raises(DecisionRefusedError, match="does not decide"):
        desk.review(INTERP, constructed, reviewer)
    assert reviewer.calls == []
    fields = {"subject_kind": INTERP, "subject_id": constructed, "ruling": RULING}
    with pytest.raises(DecisionRefusedError, match="by RUNTIME"):
        lifecycle.decide(desk.pools[PgRole.RUNTIME], kind=DecisionKind.ACCEPT, **fields)

    def operand(ordinal: int) -> None:
        row = {"interpretation_id": constructed, "ordinal": ordinal}
        _insert(runtime, "interpretation_operands", row | {"operand_interpretation_id": direct})

    with desk.cursor(PgRole.OWNER) as cursor:
        before = store.subject_digest(cursor, INTERP, constructed)
    operand(1)
    with desk.cursor(PgRole.OWNER) as cursor, pytest.raises(errors.CheckViolation, match="digest"):
        store.insert_decision(
            cursor, kind=DecisionKind.ACCEPT, predecessor_id=None, sealed_digest=before, **fields
        )
    accepted = desk.owner(INTERP, constructed, DecisionKind.ACCEPT)
    assert (accepted.decider.value, accepted.panel_review_id) == ("OWNER", None)
    with pytest.raises(errors.CheckViolation, match="decided"):
        operand(2)

    seeded = desk.seeded
    manual = _insert(
        runtime,
        "interpretations",
        _interpretation(seeded["_entity"], seeded["_capture"], None, origin="CONSTRUCTED")
        | {"construction_rule_id": "manual", "input_digest": "manual", "mapping_entry_id": None}
        | {"revision_cause": "MANUAL_CORRECTION"},
    )
    assert desk.owner(INTERP, manual, DecisionKind.ACCEPT).kind is DecisionKind.ACCEPT


def test_the_comparison_writer_stores_each_pairs_identity(runner: Runner) -> None:
    """Every pair outcome a real run writes carries ``pair_identity`` of its kind and ordered
    sides, the same function that routes queue items (D11 mechanism)."""
    runner.ingest.run(runner.ingest.intake(BOTH))
    record = runner.run()
    expected = sorted(
        pair_identity(pair.pair_kind, pair.left, pair.right)
        for row in runner.results(record.run_id)
        for pair in row.pairs
    )
    with runner.pool.connection() as conn:
        stored = conn.execute(
            "SELECT p.pair_identity FROM eqos.pair_outcomes p "
            "JOIN eqos.results r ON r.id = p.result_id WHERE r.run_id = %s",
            (record.run_id,),
        ).fetchall()
    assert expected and sorted(identity for (identity,) in stored) == expected
