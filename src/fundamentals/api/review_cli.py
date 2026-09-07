"""CLI commands for recording a human review of an earnings-update artifact."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import structlog
from pydantic import ValidationError

from fundamentals.api.artifact_writer import preflight_out_paths, write_bytes_no_clobber
from fundamentals.output.earnings_update import EarningsUpdate
from fundamentals.output.review_session import (
    ApprovalDecision,
    ApprovalState,
    ClaimReview,
    CorrectionCategory,
    Disposition,
    ReviewSession,
    approval_record_markdown,
    finish_session,
    load_session,
    record_review,
    save_session,
    start_session,
    summarize_session,
)

REVIEW_COMMAND = "review"
_CLI_LOGGER = structlog.get_logger("fundamentals.review")


def add_review_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the review session commands."""
    review = subparsers.add_parser(REVIEW_COMMAND, help="record an earnings-update review session")
    actions = review.add_subparsers(dest="review_action", required=True)
    start = actions.add_parser("start", help="start a review session for one JSON report")
    start.add_argument("--report-json", required=True, help="EarningsUpdate JSON artifact")
    start.add_argument("--session", required=True, help="new session directory")
    claim = actions.add_parser("claim", help="record one claim disposition")
    claim.add_argument("--session", required=True, help="session directory")
    claim.add_argument("--claim", required=True, help="stable claim identifier")
    claim.add_argument("--disposition", required=True, choices=[item.value for item in Disposition])
    claim.add_argument(
        "--category",
        default=CorrectionCategory.NONE.value,
        choices=[item.value for item in CorrectionCategory],
    )
    claim.add_argument("--seconds", type=int, default=None)
    claim.add_argument("--note", default=None)
    listed = actions.add_parser("list", help="list claims and current dispositions")
    listed.add_argument("--session", required=True, help="session directory")
    finish = actions.add_parser("finish", help="finish and approve or reject a review session")
    finish.add_argument("--session", required=True, help="session directory")
    finish.add_argument("--decision", required=True, choices=["approved", "rejected"])
    finish.add_argument("--decider", required=True)
    finish.add_argument("--verbatim", required=True)


def _with_elapsed(session: ReviewSession, started_at: datetime) -> ReviewSession:
    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    return session.model_copy(
        update={"instrumentation_seconds": session.instrumentation_seconds + elapsed}
    )


def _start(args: argparse.Namespace, command_started_at: datetime) -> int:
    session_dir = Path(args.session)
    if session_dir.exists():
        raise ValueError(f"session directory already exists: {session_dir}")
    report_bytes = Path(args.report_json).read_bytes()
    update = EarningsUpdate.model_validate_json(report_bytes)
    session = start_session(update, report_json_sha256=sha256(report_bytes).hexdigest())
    session_dir.mkdir(parents=True)
    save_session(_with_elapsed(session, command_started_at), session_dir)
    return 0


def _claim(args: argparse.Namespace, command_started_at: datetime) -> int:
    session_dir = Path(args.session)
    session = load_session(session_dir)
    review = ClaimReview(
        claim_id=args.claim,
        disposition=Disposition(args.disposition),
        category=CorrectionCategory(args.category),
        seconds=args.seconds,
        note=args.note,
        recorded_at=datetime.now(UTC),
    )
    save_session(_with_elapsed(record_review(session, review), command_started_at), session_dir)
    return 0


def _list(args: argparse.Namespace, command_started_at: datetime) -> int:
    session_dir = Path(args.session)
    session = load_session(session_dir)
    current = {review.claim_id: review.disposition.value for review in session.reviews}
    for claim in session.claims:
        print(f"{claim.claim_id}\t{current.get(claim.claim_id, 'unreviewed')}")
    save_session(_with_elapsed(session, command_started_at), session_dir)
    return 0


def _finish(args: argparse.Namespace, command_started_at: datetime) -> int:
    session_dir = Path(args.session)
    summary_path, record_path = session_dir / "summary.json", session_dir / "approval_record.md"
    preflight_out_paths((summary_path, record_path))
    session = load_session(session_dir)
    state = ApprovalState.APPROVED if args.decision == "approved" else ApprovalState.REJECTED
    decision = ApprovalDecision(
        state=state,
        decider=args.decider,
        verbatim=args.verbatim,
        decided_at=datetime.now(UTC),
    )
    finished = _with_elapsed(finish_session(session, decision), command_started_at)
    summary = summarize_session(finished)
    save_session(finished, session_dir)
    write_bytes_no_clobber(summary_path, summary.model_dump_json(indent=2).encode("utf-8"))
    write_bytes_no_clobber(record_path, approval_record_markdown(summary, decision).encode("utf-8"))
    return 0


def dispatch_review_command(args: argparse.Namespace) -> int | None:
    """Run a review command or return ``None`` when another command was selected."""
    if args.command != REVIEW_COMMAND:
        return None
    command_started_at = datetime.now(UTC)
    try:
        if args.review_action == "start":
            return _start(args, command_started_at)
        if args.review_action == "claim":
            return _claim(args, command_started_at)
        if args.review_action == "list":
            return _list(args, command_started_at)
        return _finish(args, command_started_at)
    except (OSError, ValidationError, ValueError, SystemExit) as error:
        _CLI_LOGGER.warning("review_refused", error=str(error))
        return 2
