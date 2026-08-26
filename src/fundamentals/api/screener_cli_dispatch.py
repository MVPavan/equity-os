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

from fundamentals.api.screener_page_cli import (
    SCREENER_PAGE_COMMAND,
    basis_unavailable_message,
    is_basis_unavailable,
    render_screener_page_summary,
    run_screener_page_command,
)
from fundamentals.ingest.screener_session_models import ScreenerCredentials, ScreenerSessionError

SCREENER_COMMANDS = (SCREENER_PAGE_COMMAND,)

# Distinct, documented exit codes: a caller (or a shell loop over the watchlist)
# can tell "this company has no such basis" from "the fetch was refused" without
# parsing text, and neither prints a traceback — these are expected outcomes.
EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_BASIS_UNAVAILABLE = 3

_CLI_LOGGER_NAME = "fundamentals.cli"
_SESSION_REQUIRED = "SCREENER_SESSION_COOKIE is required for {command}"
_REFUSAL_LINE = "{command} refused ({refusal}): {detail}"


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
        "screener_page_invoked",
        stock=args.stock,
        basis=args.basis,
        started_at=datetime.now(UTC).isoformat(),
    )
    try:
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
