"""The ``legacy`` command: preflight, import and status of legacy SQLite fact stores.

    legacy preflight --manifest M --out P
    legacy import --manifest M --preflight P [--owner O]
    legacy status --manifest M

Like ``db``, every action targets the database in ``PgSettings`` (``EQOS_PG_DB``). Manifest
paths resolve against the working directory.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.pg.approvals import GateRefusedError
from fundamentals.pg.legacy_import import (
    LegacyImportRefusedError,
    import_legacy,
    load_manifest,
    origin_id_for,
    preflight,
    store_state,
)
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings

LEGACY_COMMAND = "legacy"
PREFLIGHT_ACTION = "preflight"
IMPORT_ACTION = "import"
STATUS_ACTION = "status"
NOT_IMPORTED = "NOT_IMPORTED"

_ACTION_DEST = "legacy_action"
_HELP = "preflight, import or inspect legacy SQLite fact stores"
_PREFLIGHT_LINE = "preflight\t{path}\t{clean}"
_IMPORT_LINE = "imported\t{stores}\trows={rows}\tselections={selections}\tcreated={created}"
_STATUS_LINE = "{label}\t{store}\t{state}"
_REFUSED_EVENT = "legacy_command_refused"


def add_legacy_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``legacy`` and its three actions."""
    parser = subparsers.add_parser(LEGACY_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    for name in (PREFLIGHT_ACTION, IMPORT_ACTION, STATUS_ACTION):
        action = actions.add_parser(name)
        action.add_argument("--manifest", required=True, type=Path)
    actions.choices[PREFLIGHT_ACTION].add_argument("--out", required=True, type=Path)
    actions.choices[IMPORT_ACTION].add_argument("--preflight", required=True, type=Path)
    actions.choices[IMPORT_ACTION].add_argument("--owner", type=Path)


def dispatch_legacy_command(args: argparse.Namespace) -> int | None:
    """Run the selected ``legacy`` action, or return ``None`` for any other command."""
    if args.command != LEGACY_COMMAND:
        return None
    settings, root, action = PgSettings(), Path.cwd(), getattr(args, _ACTION_DEST)
    try:
        with open_pool(settings, PgRole.RUNTIME) as pool:
            if action == IMPORT_ACTION:
                result = import_legacy(
                    args.manifest,
                    args.preflight,
                    root=root,
                    pool=pool,
                    settings=settings,
                    owner_path=args.owner,
                )
                line = _IMPORT_LINE.format(
                    stores=",".join(result.stores), **result.model_dump(exclude={"stores"})
                )
            elif action == PREFLIGHT_ACTION:
                with pool.connection() as conn:
                    report = preflight(args.manifest, root=root, conn=conn, settings=settings)
                args.out.write_bytes(report.to_yaml())
                line = _PREFLIGHT_LINE.format(path=args.out, clean=report.clean())
            else:
                with pool.connection() as conn:
                    lines = [
                        _STATUS_LINE.format(
                            label=file.label,
                            store=origin_id_for(file.sha256),
                            state=store_state(conn, origin_id_for(file.sha256)) or NOT_IMPORTED,
                        )
                        for file in load_manifest(args.manifest).files
                    ]
                line = "\n".join(lines)
    except (
        GateRefusedError,
        LegacyImportRefusedError,
        DatabaseUnavailableError,
        psycopg.OperationalError,
    ) as refusal:
        structlog.get_logger("fundamentals.legacy").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED
    sys.stdout.write(line + "\n")
    return EXIT_OK
