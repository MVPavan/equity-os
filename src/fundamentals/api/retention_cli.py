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
retention licence-end --source ID --ended-on DATE --reason TEXT --snapshot-root PATH
        --backup-dir PATH [--config-root PATH]
    (record a vendor licence end: store marker, licence-ends.json entry, database row, then a
    purge of all that source's material, holds notwithstanding; exit codes as purge)
retention refetch --capture ID --snapshot-root PATH [--retry]
    (as the runtime role: fetch an expired exchange capture from its address; exit 0 when
    restored, ``EXIT_HIGH`` on a mismatch, ``EXIT_REFUSED`` when the fetch failed or the
    capture is not refetchable; after a completed mismatch only ``--retry`` fetches again)
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.retention_purge import (
    PurgeRefusedError,
    PurgeReport,
    PurgeStep,
    RefetchOutcome,
)
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.pg.backup import BackupError, write_backup
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.retention_io import AuthorityError
from fundamentals.pg.role_secrets import (
    RoleSecretError,
    load_login,
    load_privileged,
    secrets_dir,
)
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.retention.holds import pinned_roots
from fundamentals.retention.purge import (
    INCIDENTS,
    UNCLASSIFIED,
    dry_run,
    purge,
    record_licence_end,
)
from fundamentals.retention.refetch import live_fetch, refetch
from fundamentals.store.snapshot_store import SnapshotStore

RETENTION_COMMAND = "retention"
CLASSIFY_ACTION = "classify"
PURGE_ACTION = "purge"
REFETCH_ACTION = "refetch"
LICENCE_END_ACTION = "licence-end"
CONFIG_ROOT = Path("config")
EXIT_HIGH = 3  # SUCCESS_WITH_OPEN_HIGH (compare/run_models.py)
_ACTION_DEST = "retention_action"
_HELP = "capture retention: classes, purge and re-fetch"
_CLASSIFY_HELP = "classify the captures registered before retention classes existed"
_PURGE_HELP = "delete the blobs eligible for purge, or list them (--dry-run)"
_DRY_RUN_HELP = "only list the eligible blobs and open incidents"
_REFETCH_HELP = "fetch an expired exchange capture back from its address"
_LICENCE_END_HELP = "record a vendor licence end and purge all that source's material"
_REFETCH_EXIT = {RefetchOutcome.RESTORED: EXIT_OK, RefetchOutcome.REFETCH_MISMATCH: EXIT_HIGH}
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
    refetch_parser = actions.add_parser(REFETCH_ACTION, help=_REFETCH_HELP)
    refetch_parser.add_argument("--capture", type=int, required=True)
    refetch_parser.add_argument("--snapshot-root", type=Path, required=True)
    refetch_parser.add_argument("--retry", action="store_true")
    ended = actions.add_parser(LICENCE_END_ACTION, help=_LICENCE_END_HELP)
    ended.add_argument("--source", required=True)
    ended.add_argument("--ended-on", required=True, type=date.fromisoformat)
    ended.add_argument("--reason", required=True)
    ended.add_argument("--snapshot-root", type=Path, required=True)
    ended.add_argument("--backup-dir", type=Path, required=True)
    ended.add_argument("--config-root", type=Path, default=CONFIG_ROOT)


def dispatch_retention_command(args: argparse.Namespace) -> int | None:
    """Run a ``retention`` action, or return ``None`` for any other command."""
    if args.command != RETENTION_COMMAND:
        return None
    try:
        if args.retention_action == CLASSIFY_ACTION:
            return _classify()
        if args.retention_action == REFETCH_ACTION:
            return _refetch(args.capture, args.snapshot_root, retry=args.retry)
        if args.retention_action == LICENCE_END_ACTION:
            ended = partial(
                record_licence_end,
                source_id=args.source,
                ended_on=args.ended_on,
                reason=args.reason,
            )
            return _purge(args.config_root, args.snapshot_root, args.backup_dir, ended)
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
        SnapshotError,
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
        blobs = dry_run(conn, pinned, config_root=config_root)
        incidents = conn.execute(INCIDENTS).fetchall()
    lines = [
        f"eligible\t{b.source_id}\t{b.blob_sha256}\t{b.since.isoformat()}\t"
        + ",".join(map(str, b.capture_ref_ids))
        for b in blobs
    ]
    lines += ["\t".join(["incident", *map(str, row)]) for row in incidents]
    sys.stdout.write("".join(f"{line}\n" for line in [*lines, f"eligible_blobs\t{len(blobs)}"]))
    return EXIT_OK


def _purge(
    config_root: Path,
    snapshot_root: Path,
    backup_dir: Path,
    run: Callable[..., PurgeReport] = purge,
) -> int:
    """Run one purge (or ``run``, a licence end) with the live fetcher and a held final backup;
    print what it did. The final backup dumps as the admin login (bead eqos-z53)."""
    settings = load_privileged(os.environ)
    login = load_login(PgRole.PURGE, secrets_dir(os.environ))

    def final_backup(conn: psycopg.Connection[Any]) -> Path:
        return write_backup(
            settings,
            database=settings.db,
            snapshot_root=snapshot_root,
            out_dir=backup_dir,
            held=conn,
        )

    report = run(
        settings,
        login,
        database=settings.db,
        snapshot_root=snapshot_root,
        backup_dir=backup_dir,
        pinned=pinned_roots(config_root),
        config_root=config_root,
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


def _refetch(capture_ref_id: int, snapshot_root: Path, *, retry: bool) -> int:
    """Re-fetch one capture with the live fetcher; print and exit by its outcome (R10)."""
    store = SnapshotStore(snapshot_root)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        outcome = refetch(pool, store, capture_ref_id, live_fetch, retry=retry)
    sys.stdout.write(f"{outcome}\t{capture_ref_id}\n")
    return _REFETCH_EXIT.get(outcome, EXIT_REFUSED)


def _no_checkpoint(step: PurgeStep) -> None:
    """Production purges have no crash seam."""
    del step
