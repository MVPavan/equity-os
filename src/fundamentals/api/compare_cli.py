"""The ``compare`` command: execute and report comparison runs (D1a Task 9).

    compare run --entity <entity_key> --period-end <YYYY-MM-DD> --basis consolidated
        [--cutoff <ISO-8601 with offset>] [--mode as_known|retrospective] [--config-root config]
    compare report (--run <id> | --entity <key> --period-end <date> --basis <basis>)
        [--config-root config]

The composition root: ``PgSettings`` and the runtime pool are built here and nowhere else.
The default cutoff is the store clock, never the host clock. Any database or resolution
failure before commit exits ``FAILURE`` with a structlog error that names no credential.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg
import structlog
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.compare.report import render_report
from fundamentals.compare.resolve import ReplayMismatchError
from fundamentals.compare.run import (
    DatabaseIdentity,
    RunExitStatus,
    RunRecord,
    execute_run,
    exit_status,
    load_results,
    request_for,
)
from fundamentals.compare.run_config import DICTIONARY_DIR
from fundamentals.compare.run_store import PublishRetriesExhaustedError, RunReadError, RunStore
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings

COMPARE_COMMAND = "compare"
RUN_ACTION = "run"
REPORT_ACTION = "report"
DEFAULT_CONFIG_ROOT = "config"
UNKNOWN_CODE_VERSION = "UNKNOWN"
GIT_TIMEOUT_S = 5
_GIT_HEAD = ("git", "rev-parse", "HEAD")
_ACTION_DEST = "compare_action"
_HELP = "execute and report immutable comparison runs"
_RUN_HELP = "resolve, compare and publish one run (prints the run id and status)"
_REPORT_HELP = "print a stored run"
_NAIVE_CUTOFF = "--cutoff {value!r} carries no UTC offset"
_UNKNOWN_ENTITY = "entity {entity!r} is not seeded"
_NO_RUN = "no run for {entity} {period_end} {basis}"
_REPORT_SCOPE = "name --run, or all of --entity, --period-end and --basis"
_FAILED_EVENT = "compare_command_failed"
_SUMMARY = "run\t{run_id}\nstatus\t{status}\ncreated\t{created}"
_BASES = {basis.value.lower(): basis for basis in Basis}
_MODES = {mode.value.lower(): mode for mode in RunMode}


class CompareCommandError(ValueError):
    """The command line cannot form a run or report request."""


def add_compare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``compare`` with its ``run`` and ``report`` actions."""
    parser = subparsers.add_parser(COMPARE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    run = actions.add_parser(RUN_ACTION, help=_RUN_HELP)
    run.add_argument("--entity", required=True)
    run.add_argument("--period-end", required=True, type=date.fromisoformat)
    run.add_argument("--basis", required=True, choices=sorted(_BASES))
    run.add_argument("--cutoff", type=_aware_cutoff)
    run.add_argument("--mode", choices=sorted(_MODES), default=RunMode.AS_KNOWN.value.lower())
    run.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    report = actions.add_parser(REPORT_ACTION, help=_REPORT_HELP)
    report.add_argument("--run", type=int)
    report.add_argument("--entity")
    report.add_argument("--period-end", type=date.fromisoformat)
    report.add_argument("--basis", choices=sorted(_BASES))
    report.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))


def dispatch_compare_command(args: argparse.Namespace) -> int | None:
    """Run a ``compare`` action, or return ``None`` for any other command."""
    if args.command != COMPARE_COMMAND:
        return None
    try:
        if args.compare_action == RUN_ACTION:
            return _run(args)
        return _report(args)
    except (
        CompareCommandError,
        DatabaseUnavailableError,
        psycopg.Error,
        RunResolutionError,
        ReplayMismatchError,
        RunReadError,
        PublishRetriesExhaustedError,
        VersionContentDriftError,
        ValidationError,
        OSError,
        LookupError,
    ) as failure:
        structlog.get_logger("fundamentals.compare").error(
            _FAILED_EVENT, failure=type(failure).__name__, detail=str(failure)
        )
        return int(RunExitStatus.FAILURE)


def _run(args: argparse.Namespace) -> int:
    """Execute one run and print its id and status."""
    settings = PgSettings()
    with open_pool(settings, PgRole.RUNTIME) as pool:
        repository = EvidenceRepository(pool)
        entity_id = _entity_id(repository, args.entity)
        request = request_for(
            entity_id,
            args.period_end,
            _BASES[args.basis],
            cutoff=args.cutoff or repository.store_clock(),
            config_root=args.config_root,
            code_version=_code_version(),
            database_identity=DatabaseIdentity(
                host=settings.host, port=settings.port, name=settings.db
            ),
            mode=_MODES[args.mode],
        )
        record = execute_run(request, pool=pool, config_root=args.config_root)
    sys.stdout.write(
        _SUMMARY.format(
            run_id=record.run_id,
            status=record.manifest.status.value,
            created=str(record.created).lower(),
        )
        + "\n"
    )
    return int(exit_status(record))


def _report(args: argparse.Namespace) -> int:
    """Print one stored run."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        run_id = args.run if args.run is not None else _latest(pool, args)
        store = RunStore(pool)
        record = RunRecord(run_id=run_id, manifest=store.read_manifest(run_id), created=False)
        results = load_results(run_id, pool=pool)
    dictionary = load_dictionary(
        args.config_root / DICTIONARY_DIR, record.manifest.pinned.dictionary.version
    )
    sys.stdout.write(render_report(record, results, dictionary=dictionary))
    return int(RunExitStatus.SUCCESS)


def _latest(pool: ConnectionPool, args: argparse.Namespace) -> int:
    """The latest run of one entity, period end and basis."""
    if args.entity is None or args.period_end is None or args.basis is None:
        raise CompareCommandError(_REPORT_SCOPE)
    entity_id = _entity_id(EvidenceRepository(pool), args.entity)
    run_id = RunStore(pool).latest_run(entity_id, args.period_end, _BASES[args.basis])
    if run_id is None:
        raise CompareCommandError(
            _NO_RUN.format(entity=args.entity, period_end=args.period_end, basis=args.basis)
        )
    return run_id


def _entity_id(repository: EvidenceRepository, entity_key: str) -> int:
    """A seeded entity's id."""
    entity_id = repository.entity_id(entity_key)
    if entity_id is None:
        raise CompareCommandError(_UNKNOWN_ENTITY.format(entity=entity_key))
    return entity_id


def _aware_cutoff(value: str) -> datetime:
    """An ISO-8601 cutoff that carries its UTC offset."""
    cutoff = datetime.fromisoformat(value)
    if cutoff.tzinfo is None:
        raise argparse.ArgumentTypeError(_NAIVE_CUTOFF.format(value=value))
    return cutoff


def _code_version() -> str:
    """The checked-out commit, or ``UNKNOWN`` outside a work tree."""
    try:
        found = subprocess.run(
            _GIT_HEAD, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_CODE_VERSION
    return found.stdout.strip() or UNKNOWN_CODE_VERSION
