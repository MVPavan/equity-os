"""The ``review`` command: the owner reviews a submitted ledger version claim by claim (PREP-6).

    review start --version <id> --session <new dir>
    review claim --session <dir> --claim <key> --disposition D [--category C]
        --locate-seconds N --check-seconds M [--note TEXT]
    review list --session <dir>
    review finish --session <dir> --decision APPROVE|REQUEST_CHANGES|REJECT
        [--stock <symbol> --snapshot-root <dir> [--watchlist …] [--issuer-config <yaml>]...]
        (the verbatim ruling is read from stdin, as in ``ledger decide``)
    review summary --version <id>

``finish`` writes the decision and the review in one owner transaction; the rest run as the
runtime role. Time is read through :func:`_now` at command entry and just before the session
file is saved (or, at ``finish``, before the first insert); their difference over successful
commands is the command-handling time.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

from equity_os.contracts.publication.ledger import DecisionKind, VersionStatus
from equity_os.interface.commands.publication.ledger_cli import (
    DEFAULT_WATCHLIST,
    ISSUER_CONFIG_FLAG,
    LEDGER_FAILURES,
    decision_sources,
)
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from equity_os.publication.approval import review
from equity_os.publication.approval.lifecycle import version_status
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.role_secrets import load_login, secrets_dir
from equity_os.storage.database.settings import PgRole, PgSettings

REVIEW_COMMAND = "review"
_DECISIONS = (DecisionKind.APPROVE, DecisionKind.REQUEST_CHANGES, DecisionKind.REJECT)
_NOT_IN_REVIEW = "version {version_id} is {status}, not IN_REVIEW"
_EXISTS = "session directory already exists: {path}"
_LISTED = "{key}\t{disposition}"
_UNREVIEWED = "unreviewed"
_PER_CLAIM_NOTE = (
    "# a claim's elapsed time runs from the previous recorded claim: record each as you finish it"
)
_DECISION = "decision\t{id}"
_CLOCK_BACK = "the clock moved back {seconds}s during the command"
_CLI_LOGGER = structlog.get_logger("fundamentals.review")


def _now() -> datetime:
    """The review's one clock."""
    return datetime.now(UTC)


def add_review_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the review session commands."""
    parser = subparsers.add_parser(REVIEW_COMMAND, help="review a submitted ledger version")
    actions = parser.add_subparsers(dest="review_action", required=True)
    start = actions.add_parser("start", help="start reviewing an IN_REVIEW version")
    start.add_argument("--version", type=int, required=True)
    start.add_argument("--session", type=Path, required=True, help="new session directory")
    claim = actions.add_parser("claim", help="record one claim disposition")
    claim.add_argument("--session", type=Path, required=True)
    claim.add_argument("--claim", required=True, help="the claim key")
    claim.add_argument("--disposition", required=True, type=review.Disposition)
    claim.add_argument(
        "--category", type=review.CorrectionCategory, default=review.CorrectionCategory.NONE
    )
    claim.add_argument("--locate-seconds", type=int, required=True, help="self-reported")
    claim.add_argument("--check-seconds", type=int, required=True, help="self-reported")
    claim.add_argument("--note")
    listed = actions.add_parser("list", help="list the review set and current dispositions")
    listed.add_argument("--session", type=Path, required=True)
    finish = actions.add_parser("finish", help="decide the version; the ruling is read from stdin")
    finish.add_argument("--session", type=Path, required=True)
    finish.add_argument("--decision", type=DecisionKind, choices=_DECISIONS, required=True)
    finish.add_argument("--stock")
    finish.add_argument("--snapshot-root", type=Path)
    finish.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    finish.add_argument(ISSUER_CONFIG_FLAG, type=Path, action="append", default=[])
    summary = actions.add_parser("summary", help="print a reviewed version's totals as JSON")
    summary.add_argument("--version", type=int, required=True)


def _handled(session: review.Session, entry: datetime) -> review.Session:
    """The session with this command's handling time added; a backward clock is refused."""
    interval = (_now() - entry).total_seconds()
    if interval < 0:
        raise ValueError(_CLOCK_BACK.format(seconds=-interval))
    seconds = session.command_handling_seconds + interval
    return session.model_copy(update={"command_handling_seconds": seconds})


def _review_set(version_id: int) -> tuple[str, ...]:
    """The version's review set, read as the runtime role."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool, pool.connection() as conn:
        return review.review_set(conn.cursor(), version_id)


def _start(args: argparse.Namespace, entry: datetime) -> int:
    """Open a session on an ``IN_REVIEW`` version."""
    if args.session.exists():
        raise ValueError(_EXISTS.format(path=args.session))
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool, pool.connection() as conn:
        cursor = conn.cursor()
        review.review_set(cursor, args.version)
        status = version_status(cursor, args.version)
    if status is not VersionStatus.IN_REVIEW:
        raise ValueError(_NOT_IN_REVIEW.format(version_id=args.version, status=status))
    session = review.Session(
        version_id=args.version,
        instrument_version=review.INSTRUMENT_VERSION,
        started_at=entry,
    )
    session = _handled(session, entry)
    args.session.mkdir(parents=True)
    review.save(session, args.session)
    return EXIT_OK


def _claim(args: argparse.Namespace, entry: datetime) -> int:
    """Record one disposition at the command's entry time."""
    session = review.load(args.session)
    event = review.ClaimEvent(
        claim_key=args.claim,
        disposition=args.disposition,
        category=args.category,
        locate_seconds=args.locate_seconds,
        check_seconds=args.check_seconds,
        note=args.note,
        at=entry,
    )
    session = review.record(session, event, _review_set(session.version_id))
    review.save(_handled(session, entry), args.session)
    return EXIT_OK


def _list(args: argparse.Namespace, entry: datetime) -> int:
    """Print each review-set key with its current disposition."""
    session = review.load(args.session)
    review.check_instrument(session)
    now = review.current(session)
    lines = [
        _LISTED.format(key=key, disposition=now[key].disposition if key in now else _UNREVIEWED)
        for key in _review_set(session.version_id)
    ]
    sys.stdout.write("\n".join([*lines, _PER_CLAIM_NOTE]) + "\n")
    review.save(_handled(session, entry), args.session)
    return EXIT_OK


def _finish(args: argparse.Namespace, entry: datetime) -> int:
    """Decide the version and write the review with it, as the owner."""
    session = review.load(args.session)
    ruling = sys.stdin.read()
    sources = decision_sources(args) if args.stock and args.snapshot_root else {}
    login = load_login(PgRole.OWNER, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.OWNER, login=login) as pool:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            record = review.finish(
                cursor,
                session,
                args.decision,
                ruling,
                at=entry,
                handled=lambda checked: _handled(checked, entry),
                **sources,
            )
    sys.stdout.write(_DECISION.format(id=record.id) + "\n")
    return EXIT_OK


def _summary(args: argparse.Namespace) -> int:
    """Print the version's review totals as JSON."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool, pool.connection() as conn:
        found = review.summary(conn.cursor(), args.version)
    sys.stdout.write(found.model_dump_json(indent=2) + "\n")
    return EXIT_OK


def dispatch_review_command(args: argparse.Namespace) -> int | None:
    """Run a review command or return ``None`` when another command was selected."""
    if args.command != REVIEW_COMMAND:
        return None
    actions = {"start": _start, "claim": _claim, "list": _list, "finish": _finish}
    try:
        if args.review_action == "summary":
            return _summary(args)
        return actions[args.review_action](args, _now())
    except (*LEDGER_FAILURES, SystemExit) as failure:
        _CLI_LOGGER.warning("review_refused", failure=type(failure).__name__, detail=str(failure))
        return EXIT_REFUSED
