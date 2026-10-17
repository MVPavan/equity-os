"""The ``retention`` command (plan D9), run as the purge login from its credential file.

retention classify
    (classify every capture registered before migration 0027 once; a rerun writes nothing;
    exits ``EXIT_REFUSED`` listing any (source, surface) still unclassified)
retention purge --dry-run
    (read-only: print each eligible blob with the captures using it, then each open HIGH
    incident; refused, listing them, while any capture is unclassified)
retention purge --snapshot-root PATH --backup-dir PATH [--config-root PATH]
    (recover any unfinished run, then delete every eligible blob; exit 0, ``EXIT_REFUSED``
    when a precondition fails, ``EXIT_HIGH`` when a probe halted a source or a blob must be
    registered or removed)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.retention_purge import PurgeRefusedError, PurgeStep
from fundamentals.pg.backup import BackupError, write_backup
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.retention_io import AuthorityError
from fundamentals.pg.role_secrets import RoleSecretError, load_login, secrets_dir
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.retention.holds import pinned_roots
from fundamentals.retention.purge import INCIDENTS, UNCLASSIFIED, dry_run, purge
from fundamentals.retention.refetch import live_fetch

RETENTION_COMMAND = "retention"
CLASSIFY_ACTION = "classify"
PURGE_ACTION = "purge"
CONFIG_ROOT = Path("config")
EXIT_HIGH = 3  # SUCCESS_WITH_OPEN_HIGH (compare/run_models.py)
_ACTION_DEST = "retention_action"
_HELP = "capture retention: classes and purge"
_CLASSIFY_HELP = "classify the captures registered before retention classes existed"
_PURGE_HELP = "delete the blobs eligible for purge, or list them (--dry-run)"
_DRY_RUN_HELP = "only list the eligible blobs and open incidents"
_PURGE_NEEDS = "retention purge: --snapshot-root and --backup-dir are required\n"
_CLASSIFY = "SELECT eqos.classify_existing()"
_FAILED_EVENT = "retention_command_failed"


def add_retention_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``retention`` with its ``classify`` and ``purge`` actions."""
    parser = subparsers.add_parser(RETENTION_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    actions.add_parser(CLASSIFY_ACTION, help=_CLASSIFY_HELP)
    purge_parser = actions.add_parser(PURGE_ACTION, help=_PURGE_HELP)
    purge_parser.add_argument("--dry-run", action="store_true", help=_DRY_RUN_HELP)
    purge_parser.add_argument("--snapshot-root", type=Path)
    purge_parser.add_argument("--backup-dir", type=Path)
    purge_parser.add_argument("--config-root", type=Path, default=CONFIG_ROOT)


def dispatch_retention_command(args: argparse.Namespace) -> int | None:
    """Run a ``retention`` action, or return ``None`` for any other command."""
    if args.command != RETENTION_COMMAND:
        return None
    try:
        if args.retention_action == CLASSIFY_ACTION:
            return _classify()
        if args.dry_run:
            return _dry_run(args.config_root)
        if args.snapshot_root is None or args.backup_dir is None:
            sys.stderr.write(_PURGE_NEEDS)
            return EXIT_REFUSED
        return _purge(args.config_root, args.snapshot_root, args.backup_dir)
    except (
        DatabaseUnavailableError,
        psycopg.Error,
        RoleSecretError,
        OSError,
        PurgeRefusedError,
        AuthorityError,
        BackupError,
    ) as failure:
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
        left = conn.execute(UNCLASSIFIED).fetchall()
    lines = [f"classified\t{written}", *(f"unclassified\t{s}\t{f}" for s, f in left)]
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_REFUSED if left else EXIT_OK


def _dry_run(config_root: Path) -> int:
    """Print each blob eligible now (source, SHA-256, since, capture ids) and each open
    incident; read-only."""
    pinned = pinned_roots(config_root)
    login = load_login(PgRole.PURGE, secrets_dir(os.environ))
    with open_pool(PgSettings(), PgRole.PURGE, login=login) as pool, pool.connection() as conn:
        left = conn.execute(UNCLASSIFIED).fetchall()
        if left:
            sys.stdout.write("".join(f"unclassified\t{s}\t{f}\n" for s, f in left))
            return EXIT_REFUSED
        blobs = dry_run(conn, pinned)
        incidents = conn.execute(INCIDENTS).fetchall()
    lines = [
        f"eligible\t{b.source_id}\t{b.blob_sha256}\t{b.since.isoformat()}\t"
        + ",".join(map(str, b.capture_ref_ids))
        for b in blobs
    ]
    lines += ["\t".join(["incident", *map(str, row)]) for row in incidents]
    sys.stdout.write("".join(f"{line}\n" for line in [*lines, f"eligible_blobs\t{len(blobs)}"]))
    return EXIT_OK


def _purge(config_root: Path, snapshot_root: Path, backup_dir: Path) -> int:
    """Run one purge with the live fetcher and a held final backup; print what it did."""
    settings = PgSettings()
    login = load_login(PgRole.PURGE, secrets_dir(os.environ))

    def final_backup(conn: psycopg.Connection[Any]) -> Path:
        return write_backup(
            settings,
            database=settings.db,
            snapshot_root=snapshot_root,
            out_dir=backup_dir,
            held=conn,
        )

    report = purge(
        settings,
        login,
        database=settings.db,
        snapshot_root=snapshot_root,
        backup_dir=backup_dir,
        pinned=pinned_roots(config_root),
        fetch=live_fetch,
        final_backup=final_backup,
        checkpoint=_no_checkpoint,
    )
    lines = [f"run\t{report.run_id}", f"backup\t{report.backup_id}"]
    lines += [f"expired\t{capture}" for capture in report.expired]
    lines += [f"cancelled\t{capture}\t{reason}" for capture, reason in report.cancelled]
    lines += [f"halted\t{source}" for source in report.halted_sources]
    lines += [
        f"incomplete\t{b.kind}\t{b.source_id}\t{b.blob_sha256}\tregister or remove it"
        for b in report.incomplete
    ]
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    return EXIT_HIGH if report.high else EXIT_OK


def _no_checkpoint(step: PurgeStep) -> None:
    """Production purges have no crash seam."""
    del step
