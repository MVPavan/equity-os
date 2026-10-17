"""The ``retention`` command (plan D9), run as the purge login from its credential file.

retention classify
    (classify every capture registered before migration 0027 once; a rerun writes nothing;
    exits ``EXIT_REFUSED`` listing any (source, surface) still unclassified)
retention purge --dry-run
    (read-only: print each eligible blob with the captures using it; refused, listing them,
    while any capture is unclassified. The deleting purge is not implemented yet: refused)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.retention.eligibility import eligible_blobs
from fundamentals.retention.holds import capture_facts, pinned_roots

RETENTION_COMMAND = "retention"
CLASSIFY_ACTION = "classify"
PURGE_ACTION = "purge"
CONFIG_ROOT = Path("config")
_ACTION_DEST = "retention_action"
_HELP = "capture retention: classes and purge"
_CLASSIFY_HELP = "classify the captures registered before retention classes existed"
_PURGE_HELP = "list (--dry-run) the blobs eligible for purge"
_DRY_RUN_HELP = "only list the eligible blobs"
_PURGE_UNAVAILABLE = "retention purge: only --dry-run is available\n"
_NOW = "SELECT eqos.store_now()"
_CLASSIFY = "SELECT eqos.classify_existing()"
_UNCLASSIFIED = (
    "SELECT DISTINCT source_id, surface FROM eqos.capture_refs r WHERE NOT EXISTS "
    "(SELECT 1 FROM eqos.retention_classes c WHERE c.capture_ref_id = r.id) ORDER BY 1, 2"
)
_FAILED_EVENT = "retention_command_failed"


def add_retention_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``retention`` with its ``classify`` and ``purge`` actions."""
    parser = subparsers.add_parser(RETENTION_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    actions.add_parser(CLASSIFY_ACTION, help=_CLASSIFY_HELP)
    purge = actions.add_parser(PURGE_ACTION, help=_PURGE_HELP)
    purge.add_argument("--dry-run", action="store_true", help=_DRY_RUN_HELP)


def dispatch_retention_command(args: argparse.Namespace) -> int | None:
    """Run a ``retention`` action, or return ``None`` for any other command."""
    if args.command != RETENTION_COMMAND:
        return None
    if args.retention_action == PURGE_ACTION and not args.dry_run:
        sys.stderr.write(_PURGE_UNAVAILABLE)
        return EXIT_REFUSED
    try:
        return _classify() if args.retention_action == CLASSIFY_ACTION else _dry_run()
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


def _dry_run() -> int:
    """Print each blob eligible now (source, SHA-256, since, capture ids); read-only."""
    pinned = pinned_roots(CONFIG_ROOT)
    login = load_login(PgRole.PURGE, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.PURGE, login=login) as pool, pool.connection() as conn:
        with conn.transaction():
            left = conn.execute(_UNCLASSIFIED).fetchall()
            ((now,),) = conn.execute(_NOW).fetchall()
            blobs = () if left else eligible_blobs(capture_facts(conn, pinned), now)
    if left:
        sys.stdout.write("".join(f"unclassified\t{s}\t{f}\n" for s, f in left))
        return EXIT_REFUSED
    lines = [
        f"eligible\t{b.source_id}\t{b.blob_sha256}\t{b.since.isoformat()}\t"
        + ",".join(map(str, b.capture_ref_ids))
        for b in blobs
    ]
    sys.stdout.write("".join(f"{line}\n" for line in [*lines, f"eligible_blobs\t{len(blobs)}"]))
    return EXIT_OK
