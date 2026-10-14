"""The ``compare`` command: execute and report comparison runs (D1a Task 9).

    compare run --entity <entity_key> --period-end <YYYY-MM-DD> --basis consolidated
        [--cutoff <ISO-8601 with offset>] [--mode as_known|retrospective] [--config-root config]
        [--vendor <source>/<surface> ...] [--dictionary v1] [--mapping-set v1]
    compare report (--run <id> | --entity <key> --period-end <date> --basis <basis>)
        [--as-of <ISO-8601 with offset>] [--config-root config]
    compare queue list --run <id> [--as-of <ISO-8601 with offset>]
        [--severity HIGH|MEDIUM|LOW ...] [--status open|disposed|all]
    compare queue show --run <id> --item <id> [--as-of <ISO-8601 with offset>]
    compare queue dispose --item <id> --kind <kind> --reason <text> --decider <name>
        --evidence-ref <ref> [--explained-amount <decimal>]

The composition root: ``PgSettings`` and the runtime pool are built here and nowhere else.
The default cutoff is the store clock, never the host clock. Any database, configuration or
resolution failure before commit exits ``FAILURE`` with a structlog error that names no
credential. A report refuses a dictionary whose content differs from the run's pin.
``run`` exits ``SUCCESS_WITH_OPEN_HIGH`` when the run's queue holds an open ``HIGH`` item.
Queue reads default to the current overlay boundary; ``--as-of`` may not be later. A
disposition's time is the store clock's; role gating is D3's.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
import structlog
import yaml
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from fundamentals.canon.dictionary import DictionaryLoadError, load_dictionary
from fundamentals.canon.interval import RoundingPolicyError
from fundamentals.compare.definitions import DefinitionSetError
from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.compare.policy import ComparisonPolicyError
from fundamentals.compare.queue import (
    item_inputs,
    overlay_boundary,
    read_overlay,
    record_disposition,
)
from fundamentals.compare.report import (
    disposition_line,
    evidence_lines,
    queue_line,
    render_report,
    source_anchors,
)
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
from fundamentals.compare.run_config import DEFAULT_VERSION, DICTIONARY_DIR, ConfigVersions
from fundamentals.compare.run_store import PublishRetriesExhaustedError, RunReadError, RunStore
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.review_queue import DispositionKind, QueueOverlay, QueueSeverity
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.alignment import AlignmentLoadError
from fundamentals.evidence.mapping import MappingLoadError
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings

COMPARE_COMMAND = "compare"
RUN_ACTION = "run"
REPORT_ACTION = "report"
QUEUE_ACTION = "queue"
LIST_ACTION = "list"
SHOW_ACTION = "show"
DISPOSE_ACTION = "dispose"
DEFAULT_CONFIG_ROOT = "config"
UNKNOWN_CODE_VERSION = "UNKNOWN"
GIT_TIMEOUT_S = 5
_GIT_HEAD = ("git", "rev-parse", "HEAD")
_ACTION_DEST = "compare_action"
_HELP = "execute and report immutable comparison runs"
_RUN_HELP = "resolve, compare and publish one run (prints the run id and status)"
_REPORT_HELP = "print a stored run"
_QUEUE_HELP = "list open review items and record dispositions"
_LIST_HELP = "a run's items as of a time, by severity, with their dispositions"
_SHOW_HELP = "one item of a run with its evidence and dispositions"
_NO_ITEM = "item {item} is not in run {run_id}"
OPEN, DISPOSED, ALL = _STATUSES = ("open", "disposed", "all")
_DISPOSE_HELP = "record a disposition (prints its id)"
_QUEUE_DEST = "queue_action"
_LATE_AS_OF = "--as-of {as_of} is later than the overlay boundary {boundary}"
_NO_AMOUNT = "ACCEPTED_AS_DEFINITION needs --explained-amount"
_NOT_DECIMAL = "{value!r} is not a decimal amount"
_NOT_VENDOR = "{value!r} is not <source>/<surface>"
_LIST_HEADER = "run\t{run_id}\nas_of\t{as_of}"
_DISPOSED = "disposition\t{disposition}"
_SEVERITY_ORDER = {severity: index for index, severity in enumerate(QueueSeverity)}
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
    """Register ``compare`` with its ``run``, ``report`` and ``queue`` actions."""
    parser = subparsers.add_parser(COMPARE_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    run = actions.add_parser(RUN_ACTION, help=_RUN_HELP)
    run.add_argument("--entity", required=True)
    run.add_argument("--period-end", required=True, type=date.fromisoformat)
    run.add_argument("--basis", required=True, choices=sorted(_BASES))
    run.add_argument("--cutoff", type=_aware_cutoff)
    run.add_argument("--mode", choices=sorted(_MODES), default=RunMode.AS_KNOWN.value.lower())
    run.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    run.add_argument("--vendor", action="append", default=[], type=_vendor)
    run.add_argument("--dictionary", default=DEFAULT_VERSION)
    run.add_argument("--mapping-set", default=DEFAULT_VERSION)
    report = actions.add_parser(REPORT_ACTION, help=_REPORT_HELP)
    report.add_argument("--run", type=int)
    report.add_argument("--entity")
    report.add_argument("--period-end", type=date.fromisoformat)
    report.add_argument("--basis", choices=sorted(_BASES))
    report.add_argument("--as-of", type=_aware_cutoff)
    report.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    queue = actions.add_parser(QUEUE_ACTION, help=_QUEUE_HELP).add_subparsers(
        dest=_QUEUE_DEST, required=True
    )
    listing = queue.add_parser(LIST_ACTION, help=_LIST_HELP)
    listing.add_argument("--run", type=int, required=True)
    listing.add_argument("--as-of", type=_aware_cutoff)
    listing.add_argument("--severity", action="append", choices=[s.value for s in QueueSeverity])
    listing.add_argument("--status", choices=_STATUSES, default=OPEN)
    show = queue.add_parser(SHOW_ACTION, help=_SHOW_HELP)
    show.add_argument("--run", type=int, required=True)
    show.add_argument("--item", type=int, required=True)
    show.add_argument("--as-of", type=_aware_cutoff)
    dispose = queue.add_parser(DISPOSE_ACTION, help=_DISPOSE_HELP)
    dispose.add_argument("--item", type=int, required=True)
    dispose.add_argument("--kind", required=True, choices=[kind.value for kind in DispositionKind])
    dispose.add_argument("--reason", required=True)
    dispose.add_argument("--decider", required=True)
    dispose.add_argument("--evidence-ref", required=True)
    dispose.add_argument("--explained-amount", type=_amount)


def dispatch_compare_command(args: argparse.Namespace) -> int | None:
    """Run a ``compare`` action, or return ``None`` for any other command."""
    if args.command != COMPARE_COMMAND:
        return None
    try:
        if args.compare_action == RUN_ACTION:
            return _run(args)
        if args.compare_action == QUEUE_ACTION:
            queue_actions = {LIST_ACTION: _list, SHOW_ACTION: _show, DISPOSE_ACTION: _dispose}
            return queue_actions[args.queue_action](args)
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
        ComparisonPolicyError,
        DefinitionSetError,
        DictionaryLoadError,
        RoundingPolicyError,
        MappingLoadError,
        AlignmentLoadError,
        yaml.YAMLError,
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
            vendors=tuple(args.vendor),
            versions=ConfigVersions(dictionary=args.dictionary, mapping_set=args.mapping_set),
        )
        record = execute_run(request, pool=pool, config_root=args.config_root)
        overlay = read_overlay(pool, run_id=record.run_id, as_of=overlay_boundary(pool))
    sys.stdout.write(
        _SUMMARY.format(
            run_id=record.run_id,
            status=record.manifest.status.value,
            created=str(record.created).lower(),
        )
        + "\n"
    )
    return int(exit_status(record, overlay))


def _report(args: argparse.Namespace) -> int:
    """Print one stored run."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        run_id = args.run if args.run is not None else _latest(pool, args)
        store = RunStore(pool)
        record = RunRecord(run_id=run_id, manifest=store.read_manifest(run_id), created=False)
        results = load_results(run_id, pool=pool)
        anchors = source_anchors(EvidenceRepository(pool), results)
        overlay = read_overlay(pool, run_id=run_id, as_of=_as_of(pool, args.as_of))
    dictionary = load_dictionary(
        args.config_root / DICTIONARY_DIR, record.manifest.pinned.dictionary.version
    )
    report = render_report(record, results, dictionary=dictionary, anchors=anchors, overlay=overlay)
    sys.stdout.write(report)
    return int(RunExitStatus.SUCCESS)


def _list(args: argparse.Namespace) -> int:
    """Print one run's items as of a time, HIGH first, each disposed one with its records."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        RunStore(pool).read_manifest(args.run)
        overlay = read_overlay(pool, run_id=args.run, as_of=_as_of(pool, args.as_of))
    status = {
        OPEN: overlay.open_items,
        DISPOSED: overlay.disposed_items,
        ALL: (*overlay.open_items, *overlay.disposed_items),
    }[args.status]
    items = sorted(
        (item for item in status if not args.severity or item.severity.value in args.severity),
        key=lambda item: (_SEVERITY_ORDER[item.severity], item.item_id),
    )
    lines = [_LIST_HEADER.format(run_id=args.run, as_of=overlay.as_of.isoformat())]
    for item in items:
        lines.append(queue_line(item))
        lines.extend(_dispositions(overlay, item.item_id))
    sys.stdout.write("\n".join(lines) + "\n")
    return int(RunExitStatus.SUCCESS)


def _show(args: argparse.Namespace) -> int:
    """Print one item of a run with its evidence and dispositions."""
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        RunStore(pool).read_manifest(args.run)
        overlay = read_overlay(pool, run_id=args.run, as_of=_as_of(pool, args.as_of))
        found = [
            item
            for item in (*overlay.open_items, *overlay.disposed_items)
            if item.item_id == args.item
        ]
        if not found:
            raise CompareCommandError(_NO_ITEM.format(item=args.item, run_id=args.run))
        inputs = item_inputs(pool, args.item)
        occurrences = EvidenceRepository(pool).get_occurrences(inputs["occurrence_id"])
    lines = [queue_line(found[0]), *evidence_lines(inputs, occurrences)]
    lines.extend(_dispositions(overlay, args.item))
    sys.stdout.write("\n".join(lines) + "\n")
    return int(RunExitStatus.SUCCESS)


def _dispositions(overlay: QueueOverlay, item_id: int) -> list[str]:
    """One item's disposition records as of the overlay."""
    return [disposition_line(item) for item in overlay.dispositions if item.item_id == item_id]


def _dispose(args: argparse.Namespace) -> int:
    """Record one disposition at the store clock's time."""
    kind = DispositionKind(args.kind)
    if kind is DispositionKind.ACCEPTED_AS_DEFINITION and args.explained_amount is None:
        raise CompareCommandError(_NO_AMOUNT)
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        disposition = record_disposition(
            pool,
            item_id=args.item,
            kind=kind,
            reason=args.reason,
            decider=args.decider,
            evidence_ref=args.evidence_ref,
            explained_amount=args.explained_amount,
        )
    sys.stdout.write(_DISPOSED.format(disposition=disposition) + "\n")
    return int(RunExitStatus.SUCCESS)


def _as_of(pool: ConnectionPool, requested: datetime | None) -> datetime:
    """The requested overlay time, refused past the current boundary; else the boundary."""
    boundary = overlay_boundary(pool)
    if requested is None:
        return boundary
    if requested > boundary:
        raise CompareCommandError(_LATE_AS_OF.format(as_of=requested, boundary=boundary))
    return requested


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


def _vendor(value: str) -> tuple[str, str]:
    """A ``source/surface`` vendor entry."""
    source_id, separator, surface = value.partition("/")
    if not (source_id and separator and surface):
        raise argparse.ArgumentTypeError(_NOT_VENDOR.format(value=value))
    return source_id, surface


def _amount(value: str) -> Decimal:
    """A finite decimal amount."""
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError(_NOT_DECIMAL.format(value=value)) from error
    if not amount.is_finite():
        raise argparse.ArgumentTypeError(_NOT_DECIMAL.format(value=value))
    return amount


def _code_version() -> str:
    """The checked-out commit, or ``UNKNOWN`` outside a work tree."""
    try:
        found = subprocess.run(
            _GIT_HEAD, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_CODE_VERSION
    return found.stdout.strip() or UNKNOWN_CODE_VERSION
