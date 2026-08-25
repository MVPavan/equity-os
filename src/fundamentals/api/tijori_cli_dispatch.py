"""Dispatch for the Tijori acquisition commands of the Fundamentals CLI.

Extracted verbatim from :mod:`fundamentals.api.cli` so the composition root
stays inside its file-size bound as Tijori surfaces are added. Credentials are
still resolved by the composition root — the factory is called only once a
Tijori command is actually selected, so an unrelated command is never failed by
partial Tijori auth material in the environment.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from fundamentals.api.tijori_analysis_cli import (
    TIJORI_ANALYSIS_COMMAND,
    render_tijori_analysis_summary,
    run_tijori_analysis_command,
)
from fundamentals.api.tijori_overview_cli import (
    TIJORI_OVERVIEW_COMMAND,
    render_tijori_overview_summary,
    run_tijori_overview_command,
)
from fundamentals.api.tijori_shareholding_cli import (
    TIJORI_SHAREHOLDING_COMMAND,
    render_tijori_shareholding_summary,
    run_tijori_shareholding_command,
)
from fundamentals.api.tijori_tables_cli import (
    TIJORI_TABLES_COMMAND,
    render_tijori_tables_summary,
    run_tijori_tables_command,
)
from fundamentals.ingest.tijori_source import TijoriCredentials

TIJORI_COMMANDS = (
    TIJORI_TABLES_COMMAND,
    TIJORI_SHAREHOLDING_COMMAND,
    TIJORI_OVERVIEW_COMMAND,
    TIJORI_ANALYSIS_COMMAND,
)

_CLI_LOGGER_NAME = "fundamentals.cli"
_SESSION_REQUIRED = "TIJORI_SESSION_COOKIE is required for {command}"


def _required_credentials(
    command: str, credentials_factory: Callable[[], TijoriCredentials | None]
) -> TijoriCredentials:
    """Resolve injected credentials, refusing the command before any fetch."""
    credentials = credentials_factory()
    if credentials is None:
        raise SystemExit(_SESSION_REQUIRED.format(command=command))
    return credentials


def dispatch_tijori_command(
    args: argparse.Namespace,
    *,
    credentials_factory: Callable[[], TijoriCredentials | None],
) -> int | None:
    """Run the selected Tijori command, or return ``None`` for any other command."""
    if args.command not in TIJORI_COMMANDS:
        return None
    logger = structlog.get_logger(_CLI_LOGGER_NAME)
    credentials = _required_credentials(args.command, credentials_factory)

    if args.command == TIJORI_TABLES_COMMAND:
        logger.info(
            "tijori_tables_invoked",
            stock=args.stock,
            table=args.table,
            started_at=datetime.now(UTC).isoformat(),
        )
        tables = run_tijori_tables_command(args, credentials=credentials)
        sys.stdout.write(render_tijori_tables_summary(tables) + "\n")
        return 0

    if args.command == TIJORI_SHAREHOLDING_COMMAND:
        logger.info(
            "tijori_shareholding_invoked",
            stock=args.stock,
            started_at=datetime.now(UTC).isoformat(),
        )
        shareholding = run_tijori_shareholding_command(args, credentials=credentials)
        sys.stdout.write(render_tijori_shareholding_summary(shareholding) + "\n")
        return 0

    if args.command == TIJORI_OVERVIEW_COMMAND:
        logger.info(
            "tijori_overview_invoked",
            stock=args.stock,
            section=args.section,
            started_at=datetime.now(UTC).isoformat(),
        )
        sections = run_tijori_overview_command(args, credentials=credentials)
        sys.stdout.write(render_tijori_overview_summary(sections) + "\n")
        return 0

    logger.info(
        "tijori_analysis_invoked",
        stock=args.stock,
        section=args.section,
        metric_ids=args.metric_ids,
        started_at=datetime.now(UTC).isoformat(),
    )
    run = run_tijori_analysis_command(args, credentials=credentials)
    sys.stdout.write(render_tijori_analysis_summary(run) + "\n")
    return 0
