"""D3.3 acceptance: version lifecycle, decisions and owner policy (plan Task 3; D3, D4, D12).

Every path runs through ``lifecycle.submit``, ``validate``, ``decide`` and ``version_status``
on the real role pools of a seeded ``eqos_test_*`` database. A version's one claim cites an
owner ``SET_POLICY`` decision on its report, so an ``AS_KNOWN`` check passes with no run data.
"""

from __future__ import annotations

import io
import threading
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest
from ledger_cited_support import RESULT, RUN
from ledger_support import RULING, Ledger, ledger
from pg_evidence_schema_support import PERIOD_END, PERIOD_START, _insert, runtime, seeded
from pg_support import PgTestDatabase
from psycopg import errors
from selection_support import key

from equity_os.contracts.measurement.canonical import ValueKind
from equity_os.contracts.measurement.evidence import RunMode
from equity_os.contracts.measurement.guidance_claim import EpistemicClass
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.publication.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    DecisionKind,
    DecisionRecord,
    GuidanceContract,
    NumericClaim,
    PolicyValue,
    ReportSection,
    Rounding,
    SubjectKind,
    VersionStatus,
)
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES
from equity_os.interface.entry.cli import main
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.drafting.display import content_hash
from equity_os.storage.database.settings import PgRole
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records import store

__all__ = ["ledger", "runtime", "seeded"]

V = SubjectKind.REPORT_VERSION
POLICY = PolicyValue(key="max_net_debt_to_equity", value=Decimal("0.5"), unit="x")
SECTION = ReportSection(
    ordinal=0, section_key="thesis", body="{{e:opinion}} Leverage stays under {{c:policy.cap|}}."
)
CELL_SECTION = ReportSection(
    ordinal=0,
    section_key="results",
    body="{{e:observed}} Profit before tax was {{c:fact.pbt|group-intl}} crore, "
    "not {{c:fact.pbt_wrong|group-intl}} crore.",
)


def policy_claim(decision_id: int) -> NumericClaim:
    """The thesis claim: the owner's policy value, cited by decision."""
    return NumericClaim(
        claim_key="policy.cap",
        section_key=SECTION.section_key,
        citation=Citation(kind=CitationKind.POLICY, policy_decision_id=decision_id),
        value_kind=ValueKind.RATIO,
        unit=POLICY.unit,
        value=POLICY.value,
        precision=2,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.OPINION,
    )


class Flow:
    """The lifecycle commands on one seeded ledger: runtime drafts, submits and checks; the
    owner sets policy and decides."""

    def __init__(self, ledger: Ledger, tmp_path: Path) -> None:
        self.ledger, self.pools = ledger, ledger.pools
        self.paths: dict[str, Any] = {
            "catalog": BUILTIN_SOURCES,
            "snapshots": SnapshotStore(tmp_path),
        }

    def report(self) -> tuple[int, DecisionRecord]:
        """A new report with the owner's policy on it."""
        report = self.ledger.report()
        kind = DecisionKind.SET_POLICY
        return report, self.decide(report, kind, subject_kind=SubjectKind.REPORT, policy=POLICY)

    def draft(
        self,
        report: int,
        policy: DecisionRecord,
        predecessor: int | None = None,
        *,
        section: ReportSection = SECTION,
        claims: tuple[NumericClaim, ...] | None = None,
        cutoff: Any = None,
    ) -> int:
        """A runtime draft citing ``policy``, known as of its recording unless ``cutoff``."""
        claims = (policy_claim(policy.id),) if claims is None else claims
        draft = self.ledger.version_draft(
            report,
            predecessor,
            knowledge_cutoff=cutoff or policy.recorded_at,
            sections=(section,),
            claims=claims,
            content_hash=content_hash((section,), claims),
        )
        with self.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
            return store.create_version(conn.cursor(), draft)

    def submit(self, version_id: int) -> DecisionRecord:
        return lifecycle.submit(self.pools[PgRole.RUNTIME], version_id, **self.paths)

    def validate(self, version_id: int, mode: RunMode = RunMode.AS_KNOWN) -> Any:
        return lifecycle.validate(self.pools[PgRole.RUNTIME], version_id, mode=mode, **self.paths)

    def decide(self, subject_id: int, kind: DecisionKind, **fields: Any) -> DecisionRecord:
        """An owner decision on a version unless ``fields`` name another subject kind."""
        fields = {"subject_kind": V, "ruling": RULING} | self.paths | fields
        return lifecycle.decide(
            self.pools[PgRole.OWNER], subject_id=subject_id, kind=kind, **fields
        )

    def approved(self, report: int, policy: DecisionRecord, predecessor: int | None = None) -> int:
        """A version drafted, submitted, checked ``AS_KNOWN`` and approved by the owner."""
        version_id = self.draft(report, policy, predecessor)
        self.submit(version_id)
        self.validate(version_id)
        self.decide(version_id, DecisionKind.APPROVE)
        return version_id

    def status(self, version_id: int, **as_of: Any) -> VersionStatus:
        with self.pools[PgRole.RUNTIME].connection() as conn:
            return lifecycle.version_status(conn.cursor(), version_id, **as_of)


@pytest.fixture
def flow(ledger: Ledger, tmp_path: Path) -> Flow:
    return Flow(ledger, tmp_path)


# --- status derivation and supersession


def test_rejected_successor_then_approved_supersedes_and_withdraw_shows(flow: Flow) -> None:
    """v1 approved, v2 rejected, v3 approved: v1 SUPERSEDED (not before v3's approval); a
    withdrawn superseded v1 shows WITHDRAWN and v3 stays APPROVED."""
    report, policy = flow.report()
    v1 = flow.approved(report, policy)
    v2 = flow.draft(report, policy, v1)
    flow.submit(v2)
    flow.decide(v2, DecisionKind.REJECT)
    v3 = flow.approved(report, policy, v2)
    statuses = [flow.status(v) for v in (v1, v2, v3)]
    assert statuses == [VersionStatus.SUPERSEDED, VersionStatus.REJECTED, VersionStatus.APPROVED]
    before = flow.ledger.head(v3).recorded_at - timedelta(microseconds=1)
    assert flow.status(v1, as_of=before) is VersionStatus.APPROVED
    flow.decide(v1, DecisionKind.WITHDRAW)
    assert (flow.status(v1), flow.status(v3)) == (VersionStatus.WITHDRAWN, VersionStatus.APPROVED)


def test_approved_successor_supersedes_approved_and_historical_ancestors(flow: Flow) -> None:
    """v1 approved, v2 HISTORICAL (imported), v3 approved: v1 and v2 SUPERSEDED."""
    report, policy = flow.report()
    v1 = flow.approved(report, policy)
    v2 = flow.ledger.imported(report, v1)
    assert flow.status(v2) is VersionStatus.HISTORICAL
    v3 = flow.approved(report, policy, v2)
    assert [flow.status(v) for v in (v1, v2, v3)] == [
        VersionStatus.SUPERSEDED,
        VersionStatus.SUPERSEDED,
        VersionStatus.APPROVED,
    ]


def test_owner_withdraws_an_imported_version_an_imported_successor_approved(flow: Flow) -> None:
    """v1 HISTORICAL (imported), v2 imported with ``IMPORTED_APPROVAL``: v1 is SUPERSEDED in
    both the Python status and the trigger's ``version_superseded``, so the owner may withdraw
    it."""
    report = flow.ledger.report()
    v1 = flow.ledger.imported(report)
    flow.ledger.imported(report, v1, approve=True)
    assert flow.status(v1) is VersionStatus.SUPERSEDED
    assert flow.decide(v1, DecisionKind.WITHDRAW).kind is DecisionKind.WITHDRAW
    assert flow.status(v1) is VersionStatus.WITHDRAWN


# --- successor refusals


def test_successor_submitted_while_predecessor_in_review_is_refused(flow: Flow) -> None:
    report, policy = flow.report()
    v1 = flow.draft(report, policy)
    flow.submit(v1)
    v2 = flow.draft(report, policy, v1)
    with pytest.raises(DecisionRefusedError, match="IN_REVIEW"):
        flow.submit(v2)
    assert flow.status(v2) is VersionStatus.DRAFT


def test_successor_links_outside_one_chain_are_refused(flow: Flow) -> None:
    """A predecessor from another report, a second successor and a second root (v1 approved,
    root v2 never reaches SUBMIT) are refused when the version is created."""
    report, policy = flow.report()
    other, _ = flow.report()
    v1 = flow.approved(report, policy)
    with pytest.raises(errors.ForeignKeyViolation):
        flow.draft(other, policy, v1)
    flow.draft(report, policy, v1)
    with pytest.raises(errors.UniqueViolation, match="predecessor_id"):
        flow.draft(report, policy, v1)
    with pytest.raises(errors.UniqueViolation, match="report_versions_one_root"):
        flow.draft(report, policy)


def test_two_concurrent_successors_commit_exactly_one(flow: Flow, pg_db: PgTestDatabase) -> None:
    """Two transactions each add a successor of v1: the second waits, then fails."""
    report, policy = flow.report()
    v1 = flow.approved(report, policy)
    draft = flow.ledger.version_draft(report, v1)  # never submitted: any content
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


# --- D3 transitions and D4 binding through decide


@pytest.mark.parametrize(
    ("before", "kind"),
    [
        ((), DecisionKind.APPROVE),  # approve before submit
        ((), DecisionKind.WITHDRAW),
        ((DecisionKind.SUBMIT,), DecisionKind.WITHDRAW),
        ((DecisionKind.SUBMIT, DecisionKind.REJECT), DecisionKind.APPROVE),
        ((DecisionKind.SUBMIT, DecisionKind.REQUEST_CHANGES), DecisionKind.REJECT),
        ((DecisionKind.SUBMIT, DecisionKind.APPROVE), DecisionKind.REQUEST_CHANGES),
        ((DecisionKind.SUBMIT,), DecisionKind.SUBMIT),  # and SUBMIT is never the owner's
    ],
)
def test_illegal_transitions_are_refused_through_decide(
    flow: Flow, before: tuple[DecisionKind, ...], kind: DecisionKind
) -> None:
    """Each D3 transition outside the table is refused before any row is written."""
    report, policy = flow.report()
    version_id = flow.draft(report, policy)
    for done in before:
        if done is DecisionKind.SUBMIT:
            flow.submit(version_id)
            flow.validate(version_id)
        else:
            flow.decide(version_id, done)
    head = None if not before else flow.ledger.head(version_id)
    with pytest.raises(DecisionRefusedError, match="illegal"):
        flow.decide(version_id, kind)
    assert (None if not before else flow.ledger.head(version_id)) == head


def test_approval_binds_the_deciders_own_check(flow: Flow) -> None:
    """Runtime validations are advisory: with a latest ``RETROSPECTIVE`` one, the owner's
    APPROVE binds the ``AS_KNOWN`` check the owner writes in the deciding transaction. With no
    catalog and snapshots to check with, an APPROVE is refused."""
    report, policy = flow.report()
    version_id = flow.draft(report, policy)
    flow.submit(version_id)
    retrospective = flow.validate(version_id, RunMode.RETROSPECTIVE)
    with pytest.raises(DecisionRefusedError, match="passing AS_KNOWN check"):
        flow.decide(version_id, DecisionKind.APPROVE, catalog=None)
    approval = flow.decide(version_id, DecisionKind.APPROVE)
    with flow.pools[PgRole.RUNTIME].connection() as conn:
        bound = store.latest_validation(conn.cursor(), version_id)
        written = conn.execute(
            "SELECT v.creator, v.created_xid = d.created_xid FROM eqos.validations v "
            "JOIN eqos.decisions d ON d.validation_id = v.id WHERE d.id = %s",
            (approval.id,),
        ).fetchone()
    assert bound is not None and bound.id == approval.validation_id != retrospective.id
    assert (bound.mode, bound.claim_states) == (
        RunMode.AS_KNOWN,
        (("policy.cap", ClaimState.MATCH),),
    )
    assert written == ("OWNER", True)


def test_a_forged_runtime_validation_cannot_make_a_version_eligible(flow: Flow) -> None:
    """The claim states 999999.99 against a policy of 0.5: its check is ``VALUE_MISMATCH``. A
    newer ``MATCH`` validation the runtime writes does not let the owner approve it."""
    report, policy = flow.report()
    wrong = policy_claim(policy.id).model_copy(update={"value": Decimal("999999.99")})
    version_id = flow.draft(report, policy, claims=(wrong,))
    flow.submit(version_id)
    genuine = flow.validate(version_id)
    assert genuine.claim_states == (("policy.cap", ClaimState.VALUE_MISMATCH),)
    forged = genuine.model_copy(
        update={"claim_states": (("policy.cap", ClaimState.MATCH),), "id": None}
    )
    with flow.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        store.insert_validation(conn.cursor(), forged)
    with pytest.raises(DecisionRefusedError, match="passing AS_KNOWN check"):
        flow.decide(version_id, DecisionKind.APPROVE)
    assert flow.status(version_id) is VersionStatus.IN_REVIEW


def test_a_narrative_that_misses_its_content_hash_cannot_be_approved(flow: Flow) -> None:
    """A version with a false content hash, sealed by direct SQL past ``lifecycle.submit``,
    is refused at the owner's APPROVE: its narrative does not reproduce the hash."""
    report, policy = flow.report()
    draft = flow.ledger.version_draft(
        report,
        knowledge_cutoff=policy.recorded_at,
        sections=(SECTION,),
        claims=(policy_claim(policy.id),),
        content_hash="f" * 64,
    )
    with flow.pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        version_id = store.create_version(conn.cursor(), draft)
    flow.ledger.submit(version_id)
    with pytest.raises(DecisionRefusedError, match="content hash"):
        flow.decide(version_id, DecisionKind.APPROVE)
    assert flow.status(version_id) is VersionStatus.IN_REVIEW


def test_a_draft_with_an_unresolved_claim_cannot_be_submitted(flow: Flow) -> None:
    """An unresolved claim (imports only) blocks ``SUBMIT``: the trigger refuses it."""
    report, policy = flow.report()
    unresolved = policy_claim(policy.id).model_copy(
        update={
            "claim_key": "calc.open",
            "citation": Citation(kind=CitationKind.CALCULATION),
            "measurement_key": key("open"),
            "unresolved": True,
        }
    )
    version_id = flow.draft(report, policy, claims=(policy_claim(policy.id), unresolved))
    with pytest.raises(errors.CheckViolation, match="illegal decision: SUBMIT"):
        flow.submit(version_id)
    assert flow.status(version_id) is VersionStatus.DRAFT


def test_only_an_import_binds_a_guidance_contract(flow: Flow) -> None:
    """``validate`` refuses a binding on a drafted version: it could replace what the claim
    is checked against. No validation is written."""
    report, policy = flow.report()
    version_id = flow.draft(report, policy)
    contract = GuidanceContract(
        metric=None, scope=None, horizon=None, unit=POLICY.unit, constant_currency=None
    )
    with pytest.raises(DecisionRefusedError, match="only an import binds"):
        lifecycle.validate(
            flow.pools[PgRole.RUNTIME],
            version_id,
            mode=RunMode.AS_KNOWN,
            bound={"policy.cap": contract},
            **flow.paths,
        )
    with flow.pools[PgRole.RUNTIME].connection() as conn:
        assert store.latest_validation(conn.cursor(), version_id) is None


# --- D12 owner policy and AS_KNOWN times


def test_owner_policy_end_to_end(flow: Flow) -> None:
    """Owner SET_POLICY, a draft citing it, SUBMIT, AS_KNOWN MATCH, owner APPROVE: APPROVED.
    A draft whose cutoff precedes the policy's recording is POST_CUTOFF and cannot be approved."""
    report, policy = flow.report()
    assert (policy.decider.value, policy.policy) == ("OWNER", POLICY)
    version_id = flow.draft(report, policy)
    assert flow.submit(version_id).kind is DecisionKind.SUBMIT
    assert flow.status(version_id) is VersionStatus.IN_REVIEW
    validation = flow.validate(version_id)
    assert (validation.mode, validation.claim_states, validation.version_states) == (
        RunMode.AS_KNOWN,
        (("policy.cap", ClaimState.MATCH),),
        (),
    )
    flow.decide(version_id, DecisionKind.APPROVE)
    assert flow.status(version_id) is VersionStatus.APPROVED

    later, _ = flow.report()
    early = flow.draft(later, policy, cutoff=policy.recorded_at - timedelta(microseconds=1))
    flow.submit(early)
    assert flow.validate(early).claim_states == (("policy.cap", ClaimState.POST_CUTOFF),)
    with pytest.raises(DecisionRefusedError):
        flow.decide(early, DecisionKind.APPROVE)


def test_interpretation_run_cell_in_crore(
    flow: Flow, runtime: psycopg.Connection, seeded: dict[str, int]
) -> None:
    """A crore claim on a run cell compares the cell's base-INR value at the claim's display
    scale and precision. The cell's interpretation was recorded after the draft's cutoff:
    ``POST_CUTOFF`` as known, while in hindsight the right figure matches (untrusted: filing
    only) and a wrong one is ``VALUE_MISMATCH``. The same number stated in USD crore is a
    ``UNIT_MISMATCH``: the cell carries no unit, so the claim's unit must be its key's."""
    cell_key = key("profit_before_tax", PeriodInterval.duration(PERIOD_START, PERIOD_END))
    cell_key = cell_key.model_copy(update={"entity_id": seeded["_entity"]})
    with runtime.transaction():
        run = _insert(runtime, "runs", RUN)
        row = RESULT | {"run_id": run, "entity_id": seeded["_entity"]}
        result = _insert(runtime, "results", row | {"key_digest": cell_key.digest()})
        _insert(
            runtime,
            "result_source_values",
            {"result_id": result, "source_role": "FIRST_PARTY", "representation": "XBRL"}
            | {"source_state": "VALUE", "value": Decimal("3405600000")}
            | {"interpretation_id": seeded["interpretations"]},
        )
    crore = NumericClaim(
        claim_key="fact.pbt",
        section_key=CELL_SECTION.section_key,
        citation=Citation(
            kind=CitationKind.FIGURE, interpretation_id=seeded["interpretations"], run_id=run
        ),
        measurement_key=cell_key,
        value_kind=ValueKind.CURRENCY_AMOUNT,
        unit="INR crore",
        currency="INR",
        scale=10_000_000,
        value=Decimal("340.56"),
        precision=2,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.OBSERVED,
    )
    wrong = crore.model_copy(update={"claim_key": "fact.pbt_wrong", "value": Decimal("340.57")})
    usd = crore.model_copy(update={"claim_key": "fact.pbt_usd", "unit": "USD crore"})
    report, policy = flow.report()
    (recorded,) = (
        runtime.execute(
            "SELECT recorded_at FROM eqos.interpretations WHERE id = %s",
            (seeded["interpretations"],),
        ).fetchone()
        or ()
    )
    cutoff = recorded - timedelta(microseconds=1)
    version_id = flow.draft(
        report, policy, section=CELL_SECTION, claims=(crore, wrong, usd), cutoff=cutoff
    )
    assert dict(flow.validate(version_id).claim_states) == {
        "fact.pbt": ClaimState.POST_CUTOFF,
        "fact.pbt_wrong": ClaimState.POST_CUTOFF,
        "fact.pbt_usd": ClaimState.POST_CUTOFF,
    }
    assert dict(flow.validate(version_id, RunMode.RETROSPECTIVE).claim_states) == {
        "fact.pbt": ClaimState.MATCH_UNTRUSTED,
        "fact.pbt_wrong": ClaimState.VALUE_MISMATCH,
        "fact.pbt_usd": ClaimState.UNIT_MISMATCH,
    }


# --- the owner's command


def test_ledger_decide_records_the_verbatim_ruling_from_stdin(
    flow: Flow,
    pg_db: PgTestDatabase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``ledger decide REPORT <id> SET_POLICY`` runs as the owner login and stores stdin."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    ruling = "Cap net debt to equity at 0.5x until the capex cycle ends.\n  (owner, verbatim)\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(ruling))
    report = flow.ledger.report()
    command = ["ledger", "decide", "REPORT", str(report), "SET_POLICY"]
    assert main([*command, "--key", POLICY.key, "--value", "0.5", "--unit", POLICY.unit]) == 0
    with flow.pools[PgRole.RUNTIME].connection() as conn:
        head = store.chain_head(conn.cursor(), SubjectKind.REPORT, report)
    assert head is not None
    assert (head.ruling, head.policy, head.decider.value) == (ruling, POLICY, "OWNER")
    assert f"decision\t{head.id}" in capsys.readouterr().out
