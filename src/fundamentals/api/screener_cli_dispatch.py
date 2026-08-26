"""Dispatch for the subscriber Screener commands of the Fundamentals CLI.

Mirrors :mod:`fundamentals.api.tijori_cli_dispatch`: credentials are resolved by
the composition root, and the factory is called only once a Screener command is
actually selected, so an unrelated command is never failed by a missing cookie.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from fundamentals.api.screener_financials_cli import (
    SCREENER_FINANCIALS_COMMAND,
    ScreenerFinancialsRefused,
    is_incomplete,
    refused_families,
    render_screener_financials_summary,
    run_screener_financials_command,
    unreconciled_families,
)
from fundamentals.api.screener_financials_cli import (
    basis_unavailable_message as financials_basis_unavailable_message,
)
from fundamentals.api.screener_page_cli import (
    SCREENER_PAGE_COMMAND,
    basis_unavailable_message,
    is_basis_unavailable,
    render_screener_page_summary,
    run_screener_page_command,
)
from fundamentals.ingest.screener_session_models import ScreenerCredentials, ScreenerSessionError

SCREENER_COMMANDS = (SCREENER_PAGE_COMMAND, SCREENER_FINANCIALS_COMMAND)

# Distinct, documented exit codes: a caller (or a shell loop over the watchlist)
# can tell "this company has no such basis" from "the fetch was refused" without
# parsing text, and neither prints a traceback — these are expected outcomes.
EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_BASIS_UNAVAILABLE = 3

_CLI_LOGGER_NAME = "fundamentals.cli"
_SESSION_REQUIRED = "SCREENER_SESSION_COOKIE is required for {command}"
_REFUSAL_LINE = "{command} refused ({refusal}): {detail}"
_INCOMPLETE_LINE = "{command} did not finish: {reason}"
_UNCHECKED_LINE = "{command}: schedules the reconciliation gate did not clear: {families}"
_REFUSED_LINE = "{command}: schedules refused, with their responses retained: {families}"


def dispatch_screener_command(
    args: argparse.Namespace,
    *,
    credentials_factory: Callable[[], ScreenerCredentials | None],
) -> int | None:
    """Run the selected Screener command, or return ``None`` for any other command.

    Every typed session refusal — an anonymous page, a refused redirect, a
    block or exhausted rate limit, an identity or basis failure, an off-origin
    URL — is an expected outcome of talking to this source, so it is reported as
    one line with a non-zero exit code rather than as a traceback.

    A page that did not carry the requested basis also exits non-zero after its
    evidence is written: the artifact records the fact, and the caller is never
    handed a standalone page in place of a consolidated one.
    """
    if args.command not in SCREENER_COMMANDS:
        return None
    credentials = credentials_factory()
    if credentials is None:
        raise SystemExit(_SESSION_REQUIRED.format(command=args.command))
    structlog.get_logger(_CLI_LOGGER_NAME).info(
        "screener_command_invoked",
        command=args.command,
        stock=args.stock,
        basis=args.basis,
        started_at=datetime.now(UTC).isoformat(),
    )
    try:
        if args.command == SCREENER_FINANCIALS_COMMAND:
            return _run_financials(args, credentials=credentials)
        run = run_screener_page_command(args, credentials=credentials)
    except ScreenerSessionError as error:
        sys.stderr.write(
            _REFUSAL_LINE.format(command=args.command, refusal=type(error).__name__, detail=error)
            + "\n"
        )
        return EXIT_REFUSED
    sys.stdout.write(render_screener_page_summary(run) + "\n")
    if is_basis_unavailable(run):
        sys.stderr.write(basis_unavailable_message(run) + "\n")
        return EXIT_BASIS_UNAVAILABLE
    return EXIT_OK


def _run_financials(args: argparse.Namespace, *, credentials: ScreenerCredentials) -> int:
    """Run ``screener-financials``, reporting what did and did not get proven.

    Three outcomes exit non-zero besides a transport refusal, because none is
    the thing the caller asked for: a sweep that stopped short leaves a partial
    artifact, a schedule that was refused leaves a hole in it, and a schedule
    the gate never cleared leaves the basis unproven. All three are reported by
    name on stderr while the artifact and its retained evidence are kept — the
    refused response is the most useful thing the run produced.
    """
    outcome = run_screener_financials_command(args, credentials=credentials)
    if isinstance(outcome, ScreenerFinancialsRefused):
        sys.stderr.write(financials_basis_unavailable_message(outcome) + "\n")
        return EXIT_BASIS_UNAVAILABLE
    sys.stdout.write(render_screener_financials_summary(outcome) + "\n")
    refused = refused_families(outcome)
    if refused:
        sys.stderr.write(
            _REFUSED_LINE.format(command=args.command, families=", ".join(refused)) + "\n"
        )
    unchecked = unreconciled_families(outcome)
    if unchecked:
        sys.stderr.write(
            _UNCHECKED_LINE.format(command=args.command, families=", ".join(unchecked)) + "\n"
        )
    if is_incomplete(outcome):
        sys.stderr.write(
            _INCOMPLETE_LINE.format(
                command=args.command,
                reason=outcome.run.artifact.metadata.incomplete_reason,
            )
            + "\n"
        )
        return EXIT_REFUSED
    return EXIT_REFUSED if (unchecked or refused) else EXIT_OK
