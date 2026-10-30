"""PREP-2b Task 6 proving tests: a PostgreSQL run reads its prior and writes a validated DRAFT.

Each run registers its quarter's originals through the intake at real times and runs
``--retrospective`` on the pinned retrieval manifest (contract a-b); nothing is backdated.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from evidence_support import CONFIG, ingest, policy
from prep2b_support import COMPARATOR_KIND, COUNTS, RULING, TABLES, XBRLS, Pilot
from structlog.testing import capture_logs
from test_transcript_admission import issuer_config
from tests.fundamentals.test_source_intake_cli import INTAKE_TIME, intake_fixture

import fundamentals.api.cli as cli
from fundamentals.api import compare_cli, source_admission
from fundamentals.api.cli import _build_parser, main, run_command
from fundamentals.api.config import load_config
from fundamentals.api.source_admission import RETROSPECTIVE, SourceAdmissionError
from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.compare.queue import lock_queue, publish_queue_drafts
from fundamentals.compare.run import load_results
from fundamentals.contracts.canonical import Representation, ValueIdentity
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    DecisionKind,
    NumericClaim,
    ReportKind,
    SubjectKind,
    VersionStatus,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.memory import MemoryItemDraft, MemoryKind, SupportDraft, SupportTarget
from fundamentals.contracts.review_queue import QueueItemDraft, QueueSeverity
from fundamentals.evidence.admission import key_identity
from fundamentals.evidence.mapping import MappingSet, load_mapping_set
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle, store
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import check_claim, cutoff_instant
from fundamentals.ledger.export import export_version
from fundamentals.ledger.lifecycle import DecisionRefusedError, version_status
from fundamentals.ledger.run_draft import (
    _LOCK,
    _READ_COMMITTED,
    GUIDANCE,
    GUIDANCE_KEY,
    RUN_AUTHOR,
    Prior,
    RunDraft,
    _status,
    write_run_draft,
)
from fundamentals.ledger.run_traces import RunDraftError
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.output.earnings_update import RETROSPECTIVE_LABEL
from fundamentals.output.management_ledger import LedgerStatus
from fundamentals.store.pg_fact_store import PgFactStore

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

SEQUENCE = ("FY26_Q2", "FY26_Q3", "FY26_Q4", "FY27_Q1")
Q2_TRANSCRIPT = "c9ed50d30185"  # the FY26_Q2 transcript every FY26_Q3 carried claim cites
WAIT_SECONDS = 10
IST = ZoneInfo("Asia/Kolkata")
# A guidance line's claim key and status, as the version body stores it.
GUIDED = re.compile(r"\{\{c:([^|}]+)\|[^}]*\}\} for [^\n]*? — ([A-Z]+)(?: \([^)]*\))?: \"")
# FY26_Q3's open-ended CAGR quote: a lower bound only, and not comparable to FY26_Q2's
# year-on-year guidance (the approval panel's correction, eqos-dna.2).
CAGR_LINE = re.compile(
    r"- Cables revenue: management's description of a CAGR trajectory \(lower bound only\): "
    r"\d+%-plus for annual \(target period not specified by the extracted guidance\) — "
    r"MODIFIED \(comparability not established\): \""
)
STATUS_FIELDS = ("lower_bound", "upper_bound", "unit", "constant_currency", "qualifiers")
FAMILIES = "SELECT DISTINCT revision_family FROM eqos.fact_rows WHERE target_store = %s"
ADMITTED_FAMILY = "admitted:"
MAPPED_VERSIONS = (
    "SELECT DISTINCT mapping_set_version FROM eqos.interpretations WHERE status = 'MAPPED'"
)
VERSIONS = TABLES.index("report_versions")  # its column in ``_counts``
Q2_QUARTER = PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30))


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v6, the pilot comparison pin: maps every pilot run and comparator XBRL."""
    return load_mapping_set(CONFIG / "mappings", "v6", dictionary=dictionary)


def _pilot(request: pytest.FixtureRequest, **options: Any) -> Pilot:
    """A fresh pilot database (``options`` as :class:`Pilot` takes them)."""
    fixtures = ("pg_db", "tmp_path", "monkeypatch", "ingest")
    return Pilot(*(request.getfixturevalue(name) for name in fixtures), **options)


@pytest.fixture
def pilot(request: pytest.FixtureRequest) -> Pilot:
    """The pilot database, ready for PostgreSQL runs."""
    return _pilot(request)


@pytest.fixture
def approved_q2(pilot: Pilot) -> Pilot:
    """The pilot with FY26_Q2's run draft approved: FY26_Q3's prior."""
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    pilot.approve(version_id)
    return pilot


def _counts(pilot: Pilot) -> tuple[Any, ...]:
    """Rows of every table a run writes (``TABLES``)."""
    return pilot.query(COUNTS)[0]


def _refuses(pilot: Pilot, quarter: str, match: str, **options: Any) -> None:
    """The quarter's run, its originals and comparison run in place, refuses
    (``RunDraftError`` unless ``error``) and writes no row to any table a run writes."""
    error = options.pop("error", RunDraftError)
    pilot.registered(quarter)
    before = _counts(pilot)
    with pytest.raises(error, match=match):
        pilot.run(quarter, **options)
    assert _counts(pilot) == before


def _intercept(monkeypatch: pytest.MonkeyPatch, before: Callable[[Prior, RunDraft], Any]) -> None:
    """Run ``before`` between the run's preflight and its draft write; a ``RunDraft`` it
    returns replaces the run's."""

    def intercepted(pool: Any, prior: Prior, run: RunDraft, **kwargs: Any) -> int:
        return write_run_draft(pool, prior, before(prior, run) or run, **kwargs)

    monkeypatch.setattr(cli, "write_run_draft", intercepted)


def _head(pilot: Pilot, period: str) -> int:
    """The period's latest earnings-update version."""
    ((head,),) = pilot.query(
        "SELECT max(v.id) FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id "
        "WHERE r.period = %s AND r.kind = 'EARNINGS_UPDATE'",
        period,
    )
    return int(head)


def test_prior_refusals(request: pytest.FixtureRequest) -> None:
    """Preflight refuses before the pipeline writes anything (counts unchanged): an empty
    ledger, a HISTORICAL-only predecessor, a DRAFT predecessor head over a HISTORICAL or an
    APPROVED version (a DRAFT-only predecessor is the same refusal), an open current head and
    a missing transcript capture. Ordinary admission refuses originals registered now."""
    pilot = _pilot(request, imported=False, transcripts=SEQUENCE[1:])
    _refuses(pilot, "FY26_Q3", r"FY26_Q2 has no APPROVED head \(head None")
    pilot.import_ledger()
    _refuses(pilot, "FY26_Q2", "exceeds cutoff", retrospective=False, error=SourceAdmissionError)
    _refuses(pilot, "FY26_Q2", "has no first-party capture")
    with pilot.pg_db.runtime_pool() as runtime:
        pilot.admit_transcript("FY26_Q2", runtime)
    _refuses(pilot, "FY26_Q3", "HISTORICAL")
    first = pilot.run("FY26_Q2").draft_version_id
    assert first is not None
    _refuses(pilot, "FY26_Q3", r"FY26_Q2 has no APPROVED head \(head \d+: DRAFT")
    _refuses(pilot, "FY26_Q2", "FY26_Q2's head version .* is open")
    pilot.approve(first)
    assert pilot.run("FY26_Q2").draft_version_id is not None
    _refuses(pilot, "FY26_Q3", r"FY26_Q2 has no APPROVED head \(head \d+: DRAFT")


def test_bootstrap_period_and_carried_captures(
    approved_q2: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preflight refuses before anything is written: a carried guidance capture the catalog
    does not hold first-party (FY26_Q2's transcript config omitted), and — the FY26_Q2 prior
    withdrawn — a FY26_Q3 bootstrap report with no version, which is no bootstrap period. A
    second bootstrap version arriving after preflight makes the write refuse under the
    WATCHLIST lock; then every run refuses the ambiguous bootstrap period."""
    pilot = approved_q2
    argv = pilot.registered("FY26_Q3")[1]
    kept, at = list(argv), argv.index(str(issuer_config("FY26_Q2")))
    del argv[at - 1 : at + 1]
    _refuses(pilot, "FY26_Q3", f"original {Q2_TRANSCRIPT}.* has no first-party capture")
    argv[:] = kept
    q2 = _head(pilot, "FY26_Q2")
    _withdraw(pilot, q2)
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
        bootstrap = store.create_report(
            conn.cursor(),
            entity_id=pilot.entity_id,
            period="FY26_Q3",
            kind=ReportKind.BOOTSTRAP_THESIS,
        )
    _refuses(pilot, "FY26_Q3", "FY26_Q2 has no APPROVED head")

    def second(prior: Prior, _: RunDraft) -> None:
        pinned = prior.model_copy(update={"version_id": q2})
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
            _append(pilot, pinned, conn, bootstrap)

    _intercept(monkeypatch, second)
    with pytest.raises(RunDraftError, match="ambiguous bootstrap period: FY26_Q2, FY26_Q3"):
        pilot.run("FY26_Q2")
    monkeypatch.setattr(cli, "write_run_draft", write_run_draft)
    _refuses(pilot, "FY26_Q3", "ambiguous bootstrap period")


def test_an_unbindable_comparator_refuses_before_any_write(
    request: pytest.FixtureRequest, mapping_set: MappingSet
) -> None:
    """FY26_Q2's YoY comparator ingested under a mapping without profit for the period: the
    run refuses before it stores a fact or selection."""
    pilot = _pilot(request, xbrls=tuple(xbrl for xbrl in XBRLS if xbrl[0] != "FY25_Q2"))
    ingest = request.getfixturevalue("ingest")
    entries = tuple(e for e in mapping_set.entries if e.canonical_id != "profit_for_period")
    partial = mapping_set.model_copy(update={"entries": entries})
    comparator = ingest.intake({Representation.XBRL: COMPARATOR_KIND}, "FY25_Q2")
    ingest.run(comparator, date(2024, 9, 30), mapping_set=partial)
    _refuses(pilot, "FY26_Q2", "no single mapped interpretation of profit_for_period")


def _compare_run(pilot: Pilot, quarter: str) -> int:
    """The comparison run the quarter's run argv names."""
    argv = pilot.registered(quarter)[1]
    return int(argv[argv.index("--compare-run") + 1])


def _name(pilot: Pilot, quarter: str, run_id: int | None) -> None:
    """The quarter's run argv names comparison run ``run_id`` (none when ``None``)."""
    argv = pilot.registered(quarter)[1]
    if "--compare-run" in argv:
        at = argv.index("--compare-run")
        del argv[at : at + 2]
    if run_id is not None:
        argv += ["--compare-run", str(run_id)]


def test_a_run_needs_its_pinned_comparison_run(pilot: Pilot, tmp_path: Path) -> None:
    """Without ``--compare-run``, naming a run that is not stored, or naming a comparison run
    whose pins differ from the pilot's only in the rounding policy (a test-local v2 copy), the
    run refuses before any write."""
    _name(pilot, "FY26_Q2", None)
    _refuses(pilot, "FY26_Q2", "needs --compare-run")
    _name(pilot, "FY26_Q2", 0)
    _refuses(pilot, "FY26_Q2", "comparison run 0: .*is not stored")
    drift = tmp_path / "drift"
    drift.mkdir()
    for item in CONFIG.iterdir():
        if item.name != "rounding_policy":
            (drift / item.name).symlink_to(item)
    (drift / "rounding_policy").mkdir()
    policy = (CONFIG / "rounding_policy" / "v1.yaml").read_text(encoding="utf-8")
    assert policy.count("policy_id: v1\n") == 1
    (drift / "rounding_policy" / "v2.yaml").write_text(policy.replace("v1\n", "v2\n", 1))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(compare_cli, "ConfigVersions", partial(ConfigVersions, rounding_policy="v2"))
        drifted = pilot.compare_run("FY26_Q2", drift)
    _name(pilot, "FY26_Q2", drifted)
    _refuses(pilot, "FY26_Q2", f"comparison run {drifted}: .*rounding_policy")


def test_an_open_high_on_a_required_role_refuses_unselected(pilot: Pilot) -> None:
    """An open non-diagnostic HIGH on the quarter's profit for the period: the run refuses
    naming the role and its refusal; it selects nothing and writes no version."""
    run_id = _compare_run(pilot, "FY26_Q2")
    with pilot.pg_db.runtime_pool() as pool:
        (row,) = [
            r
            for r in load_results(run_id, pool=pool)
            if r.key.canonical_id == "profit_for_period"
            and r.key.period == Q2_QUARTER
            and not r.key.dimensions.pairs
            and r.value_identity is ValueIdentity.REPORTED
        ]
        (xbrl,) = [
            v.interpretation_id
            for v in row.source_values
            if v.source_role is SourceRole.FIRST_PARTY and v.representation is Representation.XBRL
        ]
        assert xbrl is not None
        draft = QueueItemDraft(
            key=row.key,
            pair_identity="test-high",
            outcome="MISMATCH",
            severity=QueueSeverity.HIGH,
            evidence_interpretation_ids=(xbrl,),
        )
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            lock_queue(cursor)
            publish_queue_drafts(cursor, run_id=run_id, drafts=[draft])
    unselected = "SELECT (SELECT count(*) FROM eqos.fact_selections), "
    unselected += "(SELECT count(*) FROM eqos.report_versions)"
    before = pilot.query(unselected)
    with (
        capture_logs() as logs,
        pytest.raises(RunDraftError, match="profit_for_period not admitted .*: OPEN_HIGH"),
    ):
        pilot.run("FY26_Q2")
    assert pilot.query(unselected) == before
    (summary,) = [log for log in logs if log["event"] == "admission_refusals"]
    assert summary["run_id"] == run_id and summary["OPEN_HIGH"] >= 1


@pytest.mark.parametrize(
    ("representation", "late"),
    [(Representation.PDF, False), (Representation.PDF, True), (Representation.XBRL, False)],
    ids=["pdf-other-capture", "pdf-after-cutoff", "xbrl-other-capture"],
)
def test_a_package_not_the_runs_own_refuses_before_any_write(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch, representation: Representation, late: bool
) -> None:
    """The comparison run's package keeps the run's other member but this one is another
    capture, or was published after the source cutoff: the run refuses before it writes."""
    cutoff = load_config(pilot.config("FY26_Q2")).quarter.knowledge_cutoff
    real = EvidenceRepository.get_packages

    def swapped(self: EvidenceRepository, ids: Any) -> Any:
        found = []
        for package in real(self, ids):
            member = package.members[representation]
            change: dict[str, Any] = {"knowledge_time": cutoff + timedelta(seconds=1)}
            if not late:
                capture = member.capture.model_copy(update={"blob_sha256": "0" * 64})
                change = {"capture": capture}
            members = package.members | {representation: member.model_copy(update=change)}
            found.append(package.model_copy(update={"members": members}))
        return found

    pilot.registered("FY26_Q2")
    monkeypatch.setattr(EvidenceRepository, "get_packages", swapped)
    _refuses(pilot, "FY26_Q2", f"'s {representation.value} member is not the run's own")


def _append(pilot: Pilot, prior: Prior, conn: Any, report_id: int | None = None) -> None:
    """A runtime copy of the prior version, appended to its report (or as the root of
    ``report_id``), under the WATCHLIST lock."""
    assert prior.version_id is not None
    cursor = conn.cursor()
    cursor.execute(_READ_COMMITTED)
    cursor.execute(_LOCK, (SubjectKind.WATCHLIST.value, prior.entity_id))
    draft = store.read_version(cursor, prior.version_id)
    placed: dict[str, int | None] = {"predecessor_id": prior.version_id}
    if report_id is not None:
        placed = {"report_id": report_id, "predecessor_id": None}
    store.create_version(cursor, draft.model_copy(update=placed))


def _withdraw(pilot: Pilot, version_id: int | None) -> None:
    """The owner withdraws the version."""
    assert version_id is not None
    with pilot.pg_db.owner_pool() as owner:
        lifecycle.decide(
            owner,
            subject_kind=SubjectKind.REPORT_VERSION,
            subject_id=version_id,
            kind=DecisionKind.WITHDRAW,
            ruling="TEST: withdraw the prior",
        )


@pytest.mark.parametrize("race", ["append", "withdraw", "concurrent"])
def test_write_time_races(approved_q2: Pilot, monkeypatch: pytest.MonkeyPatch, race: str) -> None:
    """After preflight pins FY26_Q2's head: (a) a runtime version appended to its report or
    (b) the owner's WITHDRAW makes the write refuse; (c) a writer holding WATCHLIST makes the
    draft write wait, and once it commits its append the write refuses."""
    pilot = approved_q2
    versions: list[int] = []

    def append(prior: Prior, _: RunDraft) -> None:
        with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn, conn.transaction():
            _append(pilot, prior, conn)
        versions.append(1)

    actions = {"append": append, "withdraw": lambda prior, _: _withdraw(pilot, prior.version_id)}
    if race == "concurrent":
        _concurrent_write(pilot, monkeypatch, versions)
    else:
        _intercept(monkeypatch, actions[race])
    before = _counts(pilot)[VERSIONS]
    with pytest.raises(RunDraftError, match="the pinned prior version .* changed"):
        pilot.run("FY26_Q3")
    assert _counts(pilot)[VERSIONS] == before + len(versions)


def _watch_lock_wait(pilot: Pilot) -> None:
    """Return once some session waits on a lock (bounded)."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not pilot.query("SELECT 1 FROM pg_locks WHERE NOT granted"):
        assert time.monotonic() < deadline, "the draft write never waited on WATCHLIST"
        time.sleep(0.05)


def _concurrent_write(pilot: Pilot, monkeypatch: pytest.MonkeyPatch, versions: list[int]) -> None:
    """Between preflight and the write: A takes WATCHLIST and appends; the write (B, its own
    thread) blocks on WATCHLIST until A commits."""

    def intercepted(pool: Any, prior: Prior, run: RunDraft, **kwargs: Any) -> int:
        outcome: dict[str, Any] = {}

        def b() -> None:
            try:
                outcome["id"] = write_run_draft(pool, prior, run, **kwargs)
            except RunDraftError as error:
                outcome["error"] = error

        with pilot.pg_db.runtime_pool() as own, own.connection() as conn:
            with conn.transaction():
                _append(pilot, prior, conn)
                thread = threading.Thread(target=b)
                thread.start()
                _watch_lock_wait(pilot)
                assert thread.is_alive()
            versions.append(1)
        thread.join(WAIT_SECONDS)
        if "error" in outcome:
            raise outcome["error"]
        return int(outcome["id"])

    monkeypatch.setattr(cli, "write_run_draft", intercepted)


def test_ordinary_admission_refuses_inside_the_cutoff_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An original first seen after the exact source cutoff but within its date refuses: the
    cutoff is the instant, not the day."""
    cutoff = INTAKE_TIME - timedelta(minutes=1)
    fixture = intake_fixture(tmp_path, monkeypatch, cutoff=cutoff)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    assert cutoff < INTAKE_TIME <= cutoff_instant(cutoff.astimezone(IST).date())
    (fixture["config"].parent.parent / "output").mkdir(exist_ok=True)
    with pytest.raises(SourceAdmissionError, match="exceeds cutoff"):
        run_command(_build_parser().parse_args(fixture["run"]), intake_context=fixture["context"])


def test_source_cutoff_at_write(approved_q2: Pilot, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every capture behind every claim, carried ones included, is checked against the source
    cutoff at write time: ordinary — every capture is first seen at its 2026-09 retrieval, the
    carried FY26_Q2 transcript among those named; retrospective — the carried transcript alone,
    published after the cutoff or inside the old 5h30 window. Nothing persists."""
    for published in (None, timedelta(seconds=1), timedelta(hours=5)):

        def late(_: Prior, run: RunDraft, published: timedelta | None = published) -> RunDraft:
            if published is None:
                return run.model_copy(update={"retrospective": None})
            assert run.retrospective is not None and run.update.source_cutoff is not None
            times = dict(run.retrospective.published)
            (carried,) = (sha for sha in times if sha.startswith(Q2_TRANSCRIPT))
            times[carried] = run.update.source_cutoff + published
            designation = run.retrospective.model_copy(update={"published": times})
            return run.model_copy(update={"retrospective": designation})

        _intercept(monkeypatch, late)
        before = _counts(approved_q2)[VERSIONS]
        with pytest.raises(RunDraftError, match="past the source cutoff") as refused:
            approved_q2.run("FY26_Q3")
        named = str(refused.value).split(": ", 1)[1].split(", ")
        assert Q2_TRANSCRIPT in str(refused.value)
        assert len(named) > 1 if published is None else len(named) == 1
        assert _counts(approved_q2)[VERSIONS] == before


def test_draft_negatives(pilot: Pilot, monkeypatch: pytest.MonkeyPatch) -> None:
    """A duplicate guidance key refuses; a guidance label with a stray numeral fails the
    in-transaction ``AS_KNOWN`` check and the draft rolls back."""
    edits: list[Callable[[RunDraft], RunDraft]] = [
        lambda run: run.model_copy(
            update={
                "guidance": run.guidance * 2,
                "update": run.update.model_copy(update={"guidance": run.update.guidance * 2}),
            }
        ),
        lambda run: run.model_copy(
            update={
                "update": run.update.model_copy(
                    update={
                        "guidance": (
                            run.update.guidance[0].model_copy(
                                update={"metric_label": "Revenue growth 7"}
                            ),
                            *run.update.guidance[1:],
                        )
                    }
                )
            }
        ),
    ]
    for edit, match in zip(
        edits, ("duplicate claim key", "does not validate AS_KNOWN"), strict=True
    ):
        _intercept(monkeypatch, lambda _, run, edit=edit: edit(run))
        before = _counts(pilot)[VERSIONS]
        with pytest.raises(RunDraftError, match=match):
            pilot.run("FY26_Q2")
        assert _counts(pilot)[VERSIONS] == before


def _guidance(**changes: Any) -> Any:
    """A minimal stated guidance claim (only the compared fields matter)."""
    from fundamentals.contracts.ledger import Citation, NumericClaim

    stated = {
        "claim_key": "ledger.revenue.FY27.consolidated",
        "section_key": GUIDANCE,
        "citation": Citation(kind=CitationKind.SOURCE_QUOTE, anchor="p1.b1.0:1", quote="q"),
        "value_kind": "PERCENTAGE",
        "lower_bound": "10",
        "upper_bound": "15",
        "qualifiers": ("approximately",),
        "precision": 0,
        "rounding": "ROUND_HALF_EVEN",
        "epistemic_class": "forecast",
        "unit": "%",
        "constant_currency": False,
        "unresolved": True,
    }
    return NumericClaim.model_validate(stated | changes)


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({}, LedgerStatus.REAFFIRMED),
        ({"citation": None}, LedgerStatus.REAFFIRMED),  # a new quote of the same contract
        ({"unit": "INR crore", "value_kind": "CURRENCY_AMOUNT"}, LedgerStatus.MODIFIED),
        ({"constant_currency": True}, LedgerStatus.MODIFIED),
        ({"qualifiers": ()}, LedgerStatus.MODIFIED),
        ({"upper_bound": "16"}, LedgerStatus.MODIFIED),
    ],
)
def test_guidance_status_rule(changes: dict[str, Any], status: LedgerStatus) -> None:
    """``REAFFIRMED`` only when bounds, unit, constant currency and qualifiers all equal the
    prior's (F11): equal bounds with any of the others changed is ``MODIFIED``."""
    from fundamentals.contracts.ledger import Citation

    if changes.get("citation", 0) is None:
        changes["citation"] = Citation(
            kind=CitationKind.SOURCE_QUOTE, anchor="p2.b3.0:9", quote="other"
        )
    assert _status(_guidance(**changes), _guidance()) is status
    assert _status(_guidance(), None) is LedgerStatus.NEW


def test_four_quarter_sequence(pilot: Pilot) -> None:
    """FY26_Q2 → FY26_Q3 → FY26_Q4 (-pg) → FY27_Q1: each run writes a DRAFT pinning the prior
    approved version, every claim checks ``MATCH``; submit, validate and owner APPROVE
    supersede the import; a second run while a draft is open refuses before the pipeline."""
    previous: tuple[int, str] | None = None
    carried = 0
    seen: set[str] = set()
    for quarter in SEQUENCE:
        result = pilot.run(quarter)
        version_id = result.draft_version_id
        assert version_id is not None
        version, update = pilot.version(version_id), result.update
        assert update.retrospective and update.source_cutoff and update.derivation_cutoff
        assert version.knowledge_cutoff == update.derivation_cutoff
        assert version.knowledge_cutoff.tzinfo is not None
        heading = version.sections[0].body
        for cutoff in (update.source_cutoff, update.derivation_cutoff):
            assert cutoff.isoformat() in heading and cutoff.isoformat() in result.markdown
        assert "Retrospective workflow demonstration" in heading
        assert RETROSPECTIVE_LABEL in result.markdown
        emitted = json.loads(update.model_dump_json())
        assert emitted["retrospective"] is True
        assert emitted["source_cutoff"] and emitted["derivation_cutoff"]
        if previous is None:
            assert "Prior: none (bootstrap period)." in heading
        else:
            assert f"Prior: version:{previous[0]} digest {previous[1]}." in heading
        claims = {claim.claim_key: claim for claim in version.claims}
        prior = {} if previous is None else _guidance_claims(pilot.version(previous[0]).claims)
        (body,) = (s.body for s in version.sections if s.section_key == GUIDANCE)
        statuses = dict(GUIDED.findall(body))
        assert statuses.keys() == _guidance_claims(version.claims).keys()
        for key, status in statuses.items():
            entry, claim = prior.get(key), claims[key]
            if entry is None:
                expected = LedgerStatus.NEW
            elif claim.citation == entry.citation:
                expected = LedgerStatus.CARRIED
            elif all(getattr(claim, f) == getattr(entry, f) for f in STATUS_FIELDS):
                expected = LedgerStatus.REAFFIRMED
            else:
                expected = LedgerStatus.MODIFIED
            assert status == expected.value, key
        seen |= set(statuses.values())
        for key, claim in claims.items():
            if (
                key.startswith("calc.")
                and claim.citation.interpretation_id is None
                or (key.startswith("cmp.") and not key.endswith(".prior"))
            ):
                assert claim.citation.kind is CitationKind.CALCULATION
                assert claim.citation.calculation_trace_id is not None
        if previous is not None:
            stated = {
                GUIDANCE_KEY.format(metric=g.metric, horizon=g.horizon, scope=g.scope.value)
                for g in result.guidance_claims
            }
            for prior_claim in pilot.version(previous[0]).claims:
                if prior_claim.section_key == GUIDANCE and prior_claim.claim_key not in stated:
                    assert claims[prior_claim.claim_key].citation == prior_claim.citation
                    carried += 1
        with pilot.pg_db.runtime_pool() as runtime, runtime.connection() as conn:
            exported = export_version(conn.cursor(), version_id)
        assert hashlib.sha256(exported).hexdigest() == version.content_hash
        if quarter == "FY26_Q3":
            assert CAGR_LINE.search(exported.decode())
            _refuses(pilot, quarter, "FY26_Q3's head version .* is open")
        with pilot.pg_db.runtime_pool() as runtime:
            lifecycle.submit(runtime, version_id, **pilot.sources())
        states = dict(pilot.validate(version_id).claim_states)
        assert states and set(states.values()) == {ClaimState.MATCH}
        pilot.admitted(version_id)
        pilot.approve(version_id, submit=False)
        with pilot.pg_db.runtime_pool() as runtime, runtime.connection() as conn:
            cursor = conn.cursor()
            assert version_status(cursor, version_id) is VersionStatus.APPROVED
            assert version.predecessor_id is not None
            assert version_status(cursor, version.predecessor_id) is VersionStatus.SUPERSEDED
            previous = (version_id, store.sealed_digest(cursor, version_id))
    assert carried > 0
    assert {LedgerStatus.NEW, LedgerStatus.CARRIED} <= {LedgerStatus(s) for s in seen}
    # Every fact the runs wrote is admitted, from interpretations made only under v6.
    families = pilot.query(FAMILIES, pilot.store_id)
    assert families and all(family.startswith(ADMITTED_FAMILY) for (family,) in families)
    assert pilot.query(MAPPED_VERSIONS) == [("v6",)]
    assert seen & {LedgerStatus.REAFFIRMED.value, LedgerStatus.MODIFIED.value}


def test_a_lagging_process_clock_still_passes_as_known(
    pilot: Pilot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """eqos-4j2.23: the store stamps every write, so a process clock behind the store's must not
    put the run's own facts after its derivation cutoff (``POST_CUTOFF``)."""
    lag = timedelta(seconds=2)

    class Lagging(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Lagging:
            return super().now(tz) - lag  # type: ignore[return-value]

    monkeypatch.setattr(cli, "datetime", Lagging)
    monkeypatch.setattr(source_admission, "actual_clock", lambda: Lagging.now(UTC))
    version_id = pilot.run("FY26_Q2").draft_version_id
    assert version_id is not None
    states = pilot.validate(version_id).claim_states
    assert [key for key, state in states if state is not ClaimState.MATCH] == []


def _guidance_claims(claims: tuple[NumericClaim, ...]) -> dict[str, NumericClaim]:
    """A version's guidance claims by key."""
    return {claim.claim_key: claim for claim in claims if claim.section_key == GUIDANCE}


def test_real_clock_retrospective(pilot: Pilot) -> None:
    """Real clocks, no trusted fixture: the run admits its registered originals
    ``retrospective_registered`` at real times; its draft passes ``AS_KNOWN`` at the derivation
    cutoff; a ``RETROSPECTIVE`` validation cannot bind approval; and nothing the run created —
    fact rows, selections, versions, the draft's claims and a memory item promoted on them — is
    visible at the historical source cutoffs."""
    started = datetime.now(UTC)
    result = pilot.run("FY26_Q2")
    version_id = result.draft_version_id
    assert version_id is not None
    cutoff = result.update.source_cutoff
    assert cutoff is not None
    for source in result.temporal_evidence.sources:
        assert source.mode == RETROSPECTIVE and source.registration is not None
        assert source.acquired_at >= source.registration.capture_completed_at > cutoff
        assert source.registration.registered_at > cutoff
    with pilot.pg_db.runtime_pool() as runtime:
        lifecycle.submit(runtime, version_id, **pilot.sources())
    assert pilot.validate(version_id, RunMode.RETROSPECTIVE).mode is RunMode.RETROSPECTIVE
    with pilot.pg_db.owner_pool() as owner, pytest.raises(DecisionRefusedError, match="AS_KNOWN"):
        lifecycle.decide(
            owner,
            subject_kind=SubjectKind.REPORT_VERSION,
            subject_id=version_id,
            kind=DecisionKind.APPROVE,
            ruling="TEST: bind the RETROSPECTIVE validation",
        )
    as_known = pilot.validate(version_id)
    assert as_known.overlay_position >= result.update.derivation_cutoff  # type: ignore[operator]
    assert all(state is ClaimState.MATCH for _, state in as_known.claim_states)
    pilot.approve(version_id, submit=False)
    cutoffs = [load_config(pilot.config(quarter)).quarter.knowledge_cutoff for quarter in SEQUENCE]
    assert max(cutoffs) < started
    pilot.admitted(version_id)
    claims = pilot.version(version_id).claims
    revisions = [key_identity(c.measurement_key) for c in claims if c.claim_key.startswith("fact.")]
    with pilot.pg_db.runtime_pool() as runtime:
        facts = PgFactStore(runtime, pilot.store_id)
        for identity in revisions:
            assert facts.get_canonical(identity) is not None
            assert [facts.get_canonical(identity, cutoff=at) for at in cutoffs] == [None] * 4
    ((first_created, first_cutoff),) = pilot.query(
        "SELECT min(created_at), min(knowledge_cutoff) FROM eqos.report_versions WHERE author = %s",
        RUN_AUTHOR,
    )
    assert min(first_created, first_cutoff) > max(cutoffs)
    with pilot.pg_db.runtime_pool() as runtime, runtime.connection() as conn:
        for at in (cutoff, *cutoffs):
            for claim in claims:
                resolved = resolve_citation(
                    conn.cursor(),
                    claim,
                    entity_id=pilot.entity_id,
                    overlay_position=at,
                    run_ids=pilot.version(version_id).pinned_run_ids,
                    **pilot.sources(),
                )
                state = check_claim(
                    claim, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False
                )
                assert state is ClaimState.POST_CUTOFF, claim.claim_key
        (claim_id,) = conn.execute(
            "SELECT min(id) FROM eqos.numeric_claims WHERE version_id = %s", (version_id,)
        ).fetchone() or (None,)
    supports = ((SupportTarget.VERSION, version_id), (SupportTarget.CLAIM, claim_id))
    item = MemoryItemDraft(
        entity_id=pilot.entity_id,
        kind=MemoryKind.COMPANY_UNDERSTANDING,
        statement="The run's FY26_Q2 update is approved",
        epistemic_class=EpistemicClass.OBSERVED,
        valid_from=date(2025, 9, 30),
        valid_to=None,
        supersedes_item_id=None,
        supports=tuple(SupportDraft(target=target, target_id=id_) for target, id_ in supports),
    )
    with pilot.pg_db.runtime_pool() as runtime, pilot.pg_db.owner_pool() as owner:
        item_id = PgMemoryStore(runtime).stage(item)
        PgMemoryStore(owner).decide(item_id, DecisionKind.PROMOTE, ruling=RULING)
        memory = PgMemoryStore(runtime)
        assert [found.id for found in memory.retrieve("", stock=pilot.entity_id)] == [item_id]
        for at in (cutoff, *cutoffs):
            assert memory.retrieve("", stock=pilot.entity_id, cutoff=at) == ()
