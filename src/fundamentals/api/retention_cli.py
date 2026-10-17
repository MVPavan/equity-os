"""The ``retention`` command (plan D9), run as the purge login from its credential file.

retention classify
    (classify every capture registered before migration 0027 once; a rerun writes nothing;
    exits ``EXIT_REFUSED`` listing any (source, surface) still unclassified)
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings

RETENTION_COMMAND = "retention"
CLASSIFY_ACTION = "classify"
_ACTION_DEST = "retention_action"
_HELP = "capture retention: classes"
_CLASSIFY_HELP = "classify the captures registered before retention classes existed"
_CLASSIFY = "SELECT eqos.classify_existing()"
_UNCLASSIFIED = (
    "SELECT DISTINCT source_id, surface FROM eqos.capture_refs r WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.retention_classes c WHERE c.capture_ref_id = r.id) ORDER BY 1, 2"
)
_FAILED_EVENT = "retention_command_failed"


def add_retention_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``retention`` with its ``classify`` action."""
    parser = subparsers.add_parser(RETENTION_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    actions.add_parser(CLASSIFY_ACTION, help=_CLASSIFY_HELP)


def dispatch_retention_command(args: argparse.Namespace) -> int | None:
    """Run a ``retention`` action, or return ``None`` for any other command."""
    if args.command != RETENTION_COMMAND:
        return None
    try:
        return _classify()
    except (DatabaseUnavailableError, psycopg.Error, RoleSecretError, OSError) as failure:
        structlog.get_logger("fundamentals.retention").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=str(failure)
        )
        return EXIT_REFUSED


def _classify() -> int:
    """Classify the unclassified captures; print the count and any surface left unclassified."""
    login = load_login(PgRole.PURGE, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.PURGE, login=login) as pool, pool.connection() as conn:
        with conn.transaction():
            ((written,),) = conn.execute(_CLASSIFY).fetchall()
        left = conn.execute(_UNCLASSIFIED).fetchall()
    lines = [f"classified\t{written}", *(f"unclassified\t{s}\t{f}" for s, f in left)]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_REFUSED if left else EXIT_OK
