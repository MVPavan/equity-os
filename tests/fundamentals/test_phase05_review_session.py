"""Slice phase05-sE — review-session telemetry and the approval record (B-04, B-13, A-13).

Every claim an assisted report makes must be dispositioned by a human, and the review itself
must be measured: how long it took, how many claims there were, what was corrected and why,
and what the instrumentation of that measurement cost. Nothing records any of this today, so
this module is RED by design against two seams that do not exist yet:
``fundamentals.output.review_session`` (claim enumeration, the pure session transitions, the
summary, the persisted session, the §11 approval record) and the ``review`` subcommand in
``fundamentals.api.review_cli``, reached here only through ``fundamentals.api.cli.main``.

Both are imported INSIDE each test (never at module scope), so a missing seam fails each test
on its own line instead of collapsing the file into one collection error; the ``TYPE_CHECKING``
block is for annotations only and never runs.

Everything is synthetic: issuer SYNTH, made-up quarter, dates and values, and a report artifact
built inline and dumped to ``tmp_path``. No fixture file, no pipeline, no network. The session
``clock`` returns one fixed instant, so ``total_minutes`` is exact however many times the
implementation calls it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from fundamentals.api.cli import _configure_logging, main
from fundamentals.contracts.comparative import ComparativeChange, ComparatorKind, ConceptComparative
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    RenderedCalculation,
    RenderedFact,
    RenderedGuidance,
    VerificationOutcome,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only, never imported at runtime
    from fundamentals.output.review_session import (
        ApprovalDecision,
        ClaimReview,
        CorrectionCategory,
        Disposition,
        ReviewSession,
    )

REVIEW_COMMAND = "review"
CRORE_UNIT, PER_SHARE_UNIT, PERCENT_UNIT = "INR crore", "INR per share", "percent"
EXIT_OK, EXIT_REFUSED = 0, 2
SYMBOL, ISSUER_NAME, QUARTER_LABEL = "SYNTH", "Synthetic Industries Limited", "Q2FY28"
PERIOD_START, PERIOD_END, KNOWLEDGE_CUTOFF = "2027-07-01", "2027-09-30", "2027-10-20"
SOURCE_ID, FILE_SHA256 = "synthetic-xbrl", "0" * 63 + "1"
RETRIEVED_AT = datetime(2027, 10, 20, 6, 0, tzinfo=UTC)
STARTED_AT = datetime(2027, 10, 21, 9, 0, tzinfo=UTC)
RECORDED_AT = datetime(2027, 10, 21, 9, 15, tzinfo=UTC)
FINISHED_AT = datetime(2027, 10, 21, 9, 30, tzinfo=UTC)
TOTAL_MINUTES = 30.0
DECIDER = "A. Synth (portfolio manager)"
VERBATIM = "Approved: every claim traced to a held source anchor."
EDIT_NOTE = "restated against the held anchor"
REVENUE_CONCEPT, PAT_CONCEPT = "syn-fin:RevenueFromOperations", "syn-fin:ProfitLossForPeriod"
QOQ_PERIOD = (date(2027, 4, 1), date(2027, 6, 30))
YOY_PERIOD = (date(2026, 7, 1), date(2026, 9, 30))
REVENUE_QOQ_VALUES = (Decimal("480"), Decimal("32"), Decimal("6.7"))
PAT_YOY_VALUES = (Decimal("80"), Decimal("16"), Decimal("20.0"))

# Facts first, then only the AVAILABLE comparator changes, then guidance, then calculations.
# These ids are the contract: a session recorded against one report must still address the
# same claims when that report is enumerated again.
EXPECTED_CLAIM_IDS: tuple[str, ...] = (
    "fact:RevenueFromOperations",
    "fact:TotalIncome",
    "fact:TotalExpenses",
    "fact:ProfitBeforeTax",
    "fact:ProfitLossForPeriod",
    "fact:BasicEarningsPerShare",
    "comparative:RevenueFromOperations:qoq",
    "comparative:ProfitLossForPeriod:yoy",
    "guidance:margin:fy2028",
    "calc:pat-margin",
    "calc:yield",
)
FIRST_CLAIM_ID, EDITED_CLAIM_ID, DEFERRED_CLAIM_ID = EXPECTED_CLAIM_IDS[0], *EXPECTED_CLAIM_IDS[-2:]
UNKNOWN_CLAIM_ID = "fact:NotAClaimInThisReport"
ACCEPTED_SECONDS, EDITED_SECONDS = 10, 25
EXPECTED_SECONDS_RECORDED = ACCEPTED_SECONDS * 9 + EDITED_SECONDS

FACT_SPECS: tuple[tuple[FactRole, str, Decimal, str], ...] = (
    (FactRole.REVENUE, REVENUE_CONCEPT, Decimal("512"), CRORE_UNIT),
    (FactRole.TOTAL_INCOME, "syn-fin:TotalIncome", Decimal("528"), CRORE_UNIT),
    (FactRole.TOTAL_EXPENSES, "syn-fin:TotalExpenses", Decimal("401"), CRORE_UNIT),
    (FactRole.PROFIT_BEFORE_TAX, "syn-fin:ProfitBeforeTax", Decimal("127"), CRORE_UNIT),
    (FactRole.PROFIT_FOR_PERIOD, PAT_CONCEPT, Decimal("96"), CRORE_UNIT),
    (FactRole.BASIC_EPS, "syn-fin:BasicEarningsPerShare", Decimal("4.25"), PER_SHARE_UNIT),
)


@pytest.fixture(autouse=True)
def _stderr_logging() -> None:
    """Route structlog to stderr exactly as ``main`` does, keeping stdout assertions stable."""
    _configure_logging()


def _fixed_clock(moment: datetime) -> Callable[[], datetime]:
    """A clock returning one instant, so session totals never depend on the call count."""
    return lambda: moment


def _provenance(context_ref: str) -> Provenance:
    """One synthetic XBRL context anchor."""
    return Provenance(
        source_id=SOURCE_ID,
        file_sha256=FILE_SHA256,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref=context_ref,
        retrieved_at=RETRIEVED_AT,
    )


def _change(
    kind: ComparatorKind,
    period: tuple[date, date],
    values: tuple[Decimal, Decimal, Decimal] | None = None,
) -> ComparativeChange:
    """A comparator: sourced with its traces when values are given, else explicitly unavailable."""
    if values is None:
        return ComparativeChange(
            kind=kind,
            period_start=period[0],
            period_end=period[1],
            unavailable_reason="no comparator filing retained for this synthetic period",
        )
    prior, delta, percent = values
    return ComparativeChange(
        kind=kind,
        period_start=period[0],
        period_end=period[1],
        prior_value=prior,
        absolute_change=delta,
        percent_change=percent,
        absolute_trace=f"current − {prior}",
        percent_trace=f"(current − {prior}) / {prior} × 100",
        prior_source=_provenance(f"synthetic-{kind.value.lower()}"),
    )


def _synthetic_update() -> EarningsUpdate:
    """The synthetic SYNTH report the whole module reviews."""
    sources = (_provenance("synthetic-current"),)
    facts = tuple(
        RenderedFact(
            role=role,
            concept_qname=concept,
            value=value,
            unit=unit,
            reconciliation_status=ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
            sources=sources,
        )
        for role, concept, value, unit in FACT_SPECS
    )
    revenue = ConceptComparative(
        concept_qname=REVENUE_CONCEPT,
        current_value=Decimal("512"),
        unit=CRORE_UNIT,
        current_sources=sources,
        qoq=_change(ComparatorKind.QOQ, QOQ_PERIOD, REVENUE_QOQ_VALUES),
        yoy=_change(ComparatorKind.YOY, YOY_PERIOD),
    )
    profit = ConceptComparative(
        concept_qname=PAT_CONCEPT,
        current_value=Decimal("96"),
        unit=CRORE_UNIT,
        current_sources=sources,
        qoq=_change(ComparatorKind.QOQ, QOQ_PERIOD),
        yoy=_change(ComparatorKind.YOY, YOY_PERIOD, PAT_YOY_VALUES),
    )
    guidance = RenderedGuidance(
        metric_label="margin",
        lower_bound=Decimal("18.0"),
        upper_bound=Decimal("19.5"),
        unit=PERCENT_UNIT,
        constant_currency=False,
        horizon="fy2028",
        quote="We expect margin of 18 to 19.5 percent for fy2028.",
        source=_provenance("synthetic-guidance"),
    )
    return EarningsUpdate(
        issuer_name=ISSUER_NAME,
        nse_symbol=SYMBOL,
        issuer_quarter_label=QUARTER_LABEL,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        facts=facts,
        comparatives=(revenue, profit),
        comparatives_attempted=True,
        guidance=(guidance,),
        calculations=(
            RenderedCalculation(label="PAT margin", result="18.8%", trace="96 ÷ 512 × 100"),
            RenderedCalculation(label="yield", result="1.2%", trace="6 ÷ 512 × 100"),
        ),
        cross_check=VerificationOutcome(passed_count=6, total_count=6),
        cross_foot=VerificationOutcome(passed_count=2, total_count=2),
        sec_cross_check_note="not applicable to this synthetic issuer",
    )


REPORT_JSON = _synthetic_update().model_dump_json()
REPORT_SHA256 = hashlib.sha256(REPORT_JSON.encode("utf-8")).hexdigest()


def _write_report_json(directory: Path) -> Path:
    """Write the fixed report artifact the CLI reviews, and return its path."""
    path = directory / "earnings_update.json"
    path.write_text(REPORT_JSON, encoding="utf-8")
    return path


def _claim_review(
    claim_id: str,
    disposition: Disposition,
    category: CorrectionCategory,
    seconds: int | None = None,
    note: str | None = None,
) -> ClaimReview:
    """One recorded disposition, timestamped deterministically."""
    from fundamentals.output.review_session import ClaimReview

    return ClaimReview(
        claim_id=claim_id,
        disposition=disposition,
        category=category,
        seconds=seconds,
        note=note,
        recorded_at=RECORDED_AT,
    )


def _started_session() -> ReviewSession:
    """A session opened against the synthetic report at the fixed start instant."""
    from fundamentals.output.review_session import start_session

    return start_session(
        _synthetic_update(), report_json_sha256=REPORT_SHA256, clock=_fixed_clock(STARTED_AT)
    )


def _decision() -> ApprovalDecision:
    """The approval the finished session carries."""
    from fundamentals.output.review_session import ApprovalDecision, ApprovalState

    return ApprovalDecision(
        state=ApprovalState.APPROVED, decider=DECIDER, verbatim=VERBATIM, decided_at=FINISHED_AT
    )


def _every_review() -> tuple[ClaimReview, ...]:
    """One review per claim: nine accepted, one edited for a wrong value, one deferred."""
    from fundamentals.output.review_session import CorrectionCategory, Disposition

    special = {
        EDITED_CLAIM_ID: (Disposition.EDITED, CorrectionCategory.WRONG_VALUE, EDITED_SECONDS),
        DEFERRED_CLAIM_ID: (Disposition.DEFERRED, CorrectionCategory.NONE, None),
    }
    default = (Disposition.ACCEPTED, CorrectionCategory.NONE, ACCEPTED_SECONDS)
    reviews = []
    for claim_id in EXPECTED_CLAIM_IDS:
        disposition, category, seconds = special.get(claim_id, default)
        note = EDIT_NOTE if claim_id == EDITED_CLAIM_ID else None
        reviews.append(_claim_review(claim_id, disposition, category, seconds=seconds, note=note))
    return tuple(reviews)


def _fully_reviewed_session() -> ReviewSession:
    """A started session with every claim dispositioned, not yet finished."""
    from fundamentals.output.review_session import record_review

    session = _started_session()
    for review in _every_review():
        session = record_review(session, review)
    return session


def _finished_session() -> ReviewSession:
    """A session closed with an approval at the fixed finish instant."""
    from fundamentals.output.review_session import finish_session

    return finish_session(_fully_reviewed_session(), _decision(), clock=_fixed_clock(FINISHED_AT))


def _run_cli(argv: list[str]) -> int:
    """Call the composition root, normalising a refusal that exits instead of returning."""
    try:
        return main(argv)
    except SystemExit as exit_error:
        code = exit_error.code
        assert isinstance(code, int), f"a refusal must carry an integer exit code, got {code!r}"
        return code


def _loaded(session_dir: Path) -> ReviewSession:
    """Read the persisted session back."""
    from fundamentals.output.review_session import load_session

    return load_session(session_dir)


def _start_argv(session_dir: Path, report: Path) -> list[str]:
    """The ``review start`` argv binding one session directory to one report artifact."""
    return [REVIEW_COMMAND, "start", "--report-json", str(report), "--session", str(session_dir)]


def _claim_argv(session_dir: Path, claim_id: str) -> list[str]:
    """The ``review claim`` argv mirroring :func:`_every_review` for one claim id."""
    argv = [REVIEW_COMMAND, "claim", "--session", str(session_dir), "--claim", claim_id]
    if claim_id == EDITED_CLAIM_ID:
        edit = ("--disposition", "edited", "--category", "wrong_value")
        return [*argv, *edit, "--seconds", str(EDITED_SECONDS), "--note", EDIT_NOTE]
    if claim_id == DEFERRED_CLAIM_ID:
        return [*argv, "--disposition", "deferred"]
    return [*argv, "--disposition", "accepted", "--seconds", str(ACCEPTED_SECONDS)]


def _count(counts: Mapping[Any, int], member: str) -> int:
    """Read one bucket whether the summary keys by enum member or by its string value."""
    for key, value in counts.items():
        if key == member:
            return value
    return 0


def test_claim_ids_are_stable_and_ordered() -> None:
    # A review recorded yesterday must still address the same claim today, so ids come from the
    # report's own identifiers and the order is fixed rather than incidental.
    from fundamentals.output.review_session import ClaimKind, enumerate_claims

    claims = enumerate_claims(_synthetic_update())
    assert tuple(claim.claim_id for claim in claims) == EXPECTED_CLAIM_IDS
    assert claims == enumerate_claims(_synthetic_update())

    facts_then_changes = (ClaimKind.FACT,) * 6 + (ClaimKind.COMPARATIVE,) * 2
    expected_kinds = facts_then_changes + (ClaimKind.GUIDANCE,) + (ClaimKind.CALCULATION,) * 2
    assert tuple(claim.kind for claim in claims) == expected_kinds

    by_id = {claim.claim_id: claim for claim in claims}
    assert "512" in by_id[FIRST_CLAIM_ID].text
    assert CRORE_UNIT in by_id[FIRST_CLAIM_ID].text
    assert "480" in by_id["comparative:RevenueFromOperations:qoq"].text
    assert "32" in by_id["comparative:RevenueFromOperations:qoq"].text
    assert "margin" in by_id["guidance:margin:fy2028"].text
    assert "18.8" in by_id["calc:pat-margin"].text
    assert all(claim.sources for claim in claims)
    assert all(SOURCE_ID in source for claim in claims for source in claim.sources)


def test_disposition_category_rules() -> None:
    # A correction is only telemetry if it names its category, and an ACCEPTED claim carrying one
    # would inflate the correction counts B-04 reports.
    from fundamentals.output.review_session import CorrectionCategory, Disposition

    accepted = _claim_review(
        FIRST_CLAIM_ID, Disposition.ACCEPTED, CorrectionCategory.NONE, seconds=ACCEPTED_SECONDS
    )
    assert accepted.category is CorrectionCategory.NONE
    edited = _claim_review(FIRST_CLAIM_ID, Disposition.EDITED, CorrectionCategory.WORDING)
    assert edited.category is CorrectionCategory.WORDING

    invalid = (
        (Disposition.ACCEPTED, CorrectionCategory.WRONG_SOURCE),
        (Disposition.EDITED, CorrectionCategory.NONE),
        (Disposition.REJECTED, CorrectionCategory.NONE),
    )
    for disposition, category in invalid:
        with pytest.raises(ValueError):
            _claim_review(FIRST_CLAIM_ID, disposition, category)


def test_record_replaces_and_keeps_lineage() -> None:
    # A-13 wants corrections superseded WITH lineage: one current disposition per claim, and the
    # replaced one still readable rather than overwritten away.
    from fundamentals.output.review_session import CorrectionCategory, Disposition, record_review

    session = _started_session()
    first = _claim_review(
        FIRST_CLAIM_ID, Disposition.ACCEPTED, CorrectionCategory.NONE, seconds=ACCEPTED_SECONDS
    )
    second = _claim_review(
        FIRST_CLAIM_ID,
        Disposition.EDITED,
        CorrectionCategory.WRONG_VALUE,
        seconds=EDITED_SECONDS,
        note=EDIT_NOTE,
    )

    once = record_review(session, first)
    twice = record_review(once, second)

    assert tuple(review.claim_id for review in twice.reviews) == (FIRST_CLAIM_ID,)
    assert twice.reviews[0].disposition is Disposition.EDITED
    assert twice.superseded == (first,)
    assert once.reviews == (first,)
    assert once.superseded == ()
    assert session.reviews == ()

    unknown = _claim_review(UNKNOWN_CLAIM_ID, Disposition.ACCEPTED, CorrectionCategory.NONE)
    with pytest.raises(ValueError):
        record_review(twice, unknown)


def test_finish_requires_every_claim_reviewed() -> None:
    # An approval over partly-reviewed claims is a false assurance, so the refusal must name the
    # claims still missing — and a DEFERRED claim counts as reviewed.
    from fundamentals.output.review_session import finish_session, record_review

    session, decision = _started_session(), _decision()

    with pytest.raises(ValueError) as empty_error:
        finish_session(session, decision, clock=_fixed_clock(FINISHED_AT))
    assert FIRST_CLAIM_ID in str(empty_error.value)
    assert DEFERRED_CLAIM_ID in str(empty_error.value)

    partial = session
    for review in _every_review()[:-1]:
        partial = record_review(partial, review)
    with pytest.raises(ValueError) as partial_error:
        finish_session(partial, decision, clock=_fixed_clock(FINISHED_AT))
    message = str(partial_error.value)
    assert DEFERRED_CLAIM_ID in message
    assert FIRST_CLAIM_ID not in message

    finished = finish_session(_fully_reviewed_session(), decision, clock=_fixed_clock(FINISHED_AT))
    assert finished.finished_at == FINISHED_AT
    assert finished.decision == decision
    assert session.finished_at is None


def test_summary_totals_without_percentiles() -> None:
    # At n=3 reports a percentile is noise dressed as a measurement: the summary carries totals
    # and counts only, and no percentile key may ever appear in it.
    from fundamentals.output.review_session import (
        CorrectionCategory,
        Disposition,
        summarize_session,
    )

    summary = summarize_session(_finished_session())

    assert summary.claim_count == len(EXPECTED_CLAIM_IDS)
    assert float(summary.total_minutes) == pytest.approx(TOTAL_MINUTES)
    assert _count(summary.disposition_counts, Disposition.ACCEPTED) == 9
    assert _count(summary.disposition_counts, Disposition.EDITED) == 1
    assert _count(summary.disposition_counts, Disposition.DEFERRED) == 1
    assert _count(summary.disposition_counts, Disposition.REJECTED) == 0
    assert _count(summary.category_counts, CorrectionCategory.WRONG_VALUE) == 1
    assert _count(summary.category_counts, CorrectionCategory.WORDING) == 0
    assert int(summary.seconds_recorded) == EXPECTED_SECONDS_RECORDED
    assert float(summary.instrumentation_seconds) == pytest.approx(0.0)

    dumped = summary.model_dump_json().lower()
    assert "p90" not in dumped
    assert "percentile" not in dumped


def test_instrumentation_seconds_accumulate(tmp_path: Path) -> None:
    # B-13 requires the overhead of measuring to be reported too, so every command adds its own
    # wall time to the session it just wrote.
    session_dir, report = tmp_path / "session", _write_report_json(tmp_path)

    assert _run_cli(_start_argv(session_dir, report)) == EXIT_OK
    after_start = float(_loaded(session_dir).instrumentation_seconds)
    assert after_start > 0.0

    assert _run_cli(_claim_argv(session_dir, FIRST_CLAIM_ID)) == EXIT_OK
    after_first_claim = float(_loaded(session_dir).instrumentation_seconds)
    assert after_first_claim > after_start

    assert _run_cli(_claim_argv(session_dir, EDITED_CLAIM_ID)) == EXIT_OK
    after_second_claim = float(_loaded(session_dir).instrumentation_seconds)
    assert after_second_claim > after_first_claim
    assert after_second_claim < 60.0


def test_session_round_trip_and_atomic_save(tmp_path: Path) -> None:
    # The session is the only record of the review and four commands rewrite it: it must round
    # trip exactly and never leave a half-written or temporary file behind.
    from fundamentals.output.review_session import (
        CorrectionCategory,
        Disposition,
        record_review,
        save_session,
    )

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session = _started_session()

    save_session(session, session_dir)
    assert _loaded(session_dir) == session
    assert sorted(path.name for path in session_dir.iterdir()) == ["session.json"]

    accepted = _claim_review(
        FIRST_CLAIM_ID, Disposition.ACCEPTED, CorrectionCategory.NONE, seconds=ACCEPTED_SECONDS
    )
    updated = record_review(session, accepted)
    save_session(updated, session_dir)
    assert _loaded(session_dir) == updated
    assert sorted(path.name for path in session_dir.iterdir()) == ["session.json"]


def test_cli_start_claim_finish_flow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The reviewer's whole loop runs through one command surface, and its artifacts are what B-04
    # is measured from, so the session must bind to the exact report bytes it reviewed.
    from fundamentals.output.review_session import Disposition

    session_dir, report = tmp_path / "session", _write_report_json(tmp_path)

    assert _run_cli(_start_argv(session_dir, report)) == EXIT_OK
    started = _loaded(session_dir)
    assert started.report_json_sha256 == REPORT_SHA256
    assert started.symbol == SYMBOL
    assert started.issuer_quarter == QUARTER_LABEL
    assert tuple(claim.claim_id for claim in started.claims) == EXPECTED_CLAIM_IDS

    for claim_id in EXPECTED_CLAIM_IDS:
        assert _run_cli(_claim_argv(session_dir, claim_id)) == EXIT_OK

    capsys.readouterr()
    assert _run_cli([REVIEW_COMMAND, "list", "--session", str(session_dir)]) == EXIT_OK
    listed = capsys.readouterr().out.lower()
    for claim_id in EXPECTED_CLAIM_IDS:
        assert claim_id.lower() in listed
    assert str(Disposition.DEFERRED).lower() in listed

    finish = [REVIEW_COMMAND, "finish", "--session", str(session_dir), "--decision", "approved"]
    assert _run_cli([*finish, "--decider", DECIDER, "--verbatim", VERBATIM]) == EXIT_OK

    finished = _loaded(session_dir)
    assert finished.finished_at is not None
    assert finished.decision is not None
    assert finished.decision.decider == DECIDER

    summary = json.loads((session_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["claim_count"] == len(EXPECTED_CLAIM_IDS)
    assert summary["seconds_recorded"] == EXPECTED_SECONDS_RECORDED

    record = (session_dir / "approval_record.md").read_text(encoding="utf-8")
    assert DECIDER in record
    assert VERBATIM in record
    assert REPORT_SHA256 in record


def test_cli_refuses_existing_session_and_unknown_claim(tmp_path: Path) -> None:
    # Re-starting over a live session would silently discard recorded review time, and a typo'd
    # claim id must not create a review that addresses nothing in the report.
    session_dir, report = tmp_path / "session", _write_report_json(tmp_path)

    assert _run_cli(_start_argv(session_dir, report)) == EXIT_OK
    assert _run_cli(_claim_argv(session_dir, FIRST_CLAIM_ID)) == EXIT_OK
    assert _run_cli(_start_argv(session_dir, report)) == EXIT_REFUSED
    assert _run_cli(_claim_argv(session_dir, UNKNOWN_CLAIM_ID)) == EXIT_REFUSED

    session = _loaded(session_dir)
    assert tuple(review.claim_id for review in session.reviews) == (FIRST_CLAIM_ID,)


def test_approval_record_markdown_shape() -> None:
    # The §11 approval record is the human-signed face of the review: it must state who approved
    # what, in their own words, against the exact report bytes and the review's own totals.
    from fundamentals.output.review_session import approval_record_markdown, summarize_session

    finished = _finished_session()
    decision = finished.decision
    assert decision is not None
    summary = summarize_session(finished)

    record = approval_record_markdown(summary, decision)
    rows = [line for line in record.splitlines() if line.startswith("|")]
    headers = [
        row for row in rows if all(word in row for word in ("Approval", "Authority", "State"))
    ]
    assert len(headers) == 1
    assert "APPROVED" in record.upper()
    assert DECIDER in record
    assert VERBATIM in record
    assert REPORT_SHA256 in record
    assert FINISHED_AT.date().isoformat() in record
    assert str(summary.claim_count) in record
    assert str(EXPECTED_SECONDS_RECORDED) in record
