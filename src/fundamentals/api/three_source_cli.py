"""The ``three-source-crosscheck`` command: one stock-quarter, three retained sides.

    three-source-crosscheck --stock SYMBOL --out-dir <dir>
                            [--config <watchlist.yaml>] [--screener-root <dir>]
                            [--basis consolidated|standalone] [--gold-dir <dir>]
                            [--snapshot-root <dir>] [--capture-id <id>]
                            [--include-values] [--warn-exit]

This is a composition root and nothing else. It resolves one watchlist stock,
reads the three offline sides — the XBRL spine out of a gold file, the retained
Screener sections, the retained Tijori capture — hands them to the S5 comparator,
and turns the one report that comes back into one JSON artifact, one
tab-separated summary and one exit code. Nothing here fetches, and nothing here
decides what a difference means: that is
:mod:`fundamentals.verify.three_source`'s business.

**One stock per run.** The orchestrator loops; a command that looped internally
would have to decide what a half-failed sweep exits with, and the first
measurement needs each stock's refusal attributable to that stock.

**An absent Tijori side is MISSING, not a failure.** The approved first
measurement runs before any Tijori body has been acquired, so no retained
capture is the normal case. A run with no capture still compares XBRL against
Screener, which is the entire content of Part 1 of that measurement.

**No amount leaves the process by default.** The vendor bodies are private-use
only, so the report and the summary carry counts and outcomes; ``--include-values``
is the operator's explicit request for the figures. Redaction is a projection of
the serialized report, never a mutation of the :class:`TripleReport` the
comparator returned — the same run asked for values states exactly the figures
its sides were built from.

**An unreadable input outranks a warn.** A gold source value with no declared
precision, sections whose metadata names another company, or a capture this repo
cannot re-read all mean the comparison did not happen, which is a stronger
statement than a comparison that happened and found something. Those exit
``EXIT_UNREADABLE`` even under ``--warn-exit``. A report path that already exists
is a store refusal instead: the numbers quoted in a research doc must still be
readable beside the run that replaced them.

The four exit codes are declared here rather than imported so a Tijori/Screener
command does not depend on an Upstox module; their equality with Lane B's is
pinned by a test.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import (
    CaptureConflictError,
    CaptureRecord,
    SnapshotError,
)
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.tijori_capture import financials_request
from fundamentals.reconcile.gold_file import gold_file_path
from fundamentals.store.no_clobber import write_bytes_no_clobber
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify.three_source import (
    PairOutcome,
    PairResult,
    PairTriage,
    TripleReport,
    TripleRow,
    compare_triple,
)
from fundamentals.verify.three_source_inputs import (
    InputError,
    Side,
    SideValue,
    read_gold_spine,
    read_screener_sections,
    read_tijori_capture,
    screener_side_values,
)

_LOGGER = structlog.get_logger(__name__)

THREE_SOURCE_COMMAND: Final = "three-source-crosscheck"
REPORT_FILENAME: Final = "three_source_report.json"

# The value every redacted amount and label is stated as, so a reader of the
# report can tell "not published" from "not present".
REDACTED_LABEL: Final = "<redacted>"
REDACTED_AMOUNT: Final = None

# Lane B's codes, restated: 0 always unless asked otherwise, 1 only under
# --warn-exit, 2 for a store refusal, 3 for an input this repo could not read.
EXIT_OK: Final = 0
EXIT_WARN: Final = 1
EXIT_REFUSED: Final = 2
EXIT_UNREADABLE: Final = 3

SUMMARY_COLUMNS: Final[tuple[str, ...]] = (
    "concept",
    "xbrl_screener",
    "xbrl_tijori",
    "screener_tijori",
    "triage",
)
# Appended to every line only under --include-values.
VALUE_COLUMNS: Final[tuple[str, ...]] = (Side.XBRL.value, Side.SCREENER.value, Side.TIJORI.value)

SUMMARY_SEPARATOR: Final = "\t"
MISSING_CELL: Final = "-"
TOTALS_LABEL: Final = "totals"
COUNT_SEPARATOR: Final = " "
WARN_FIELD: Final = "warn"

AMOUNT_FIELD: Final = "amount"
RAW_LABEL_FIELD: Final = "raw_label"
ROWS_FIELD: Final = "rows"
PAIRS_FIELD: Final = "pairs"
_ROW_SIDE_FIELDS: Final[tuple[str, ...]] = (Side.XBRL.value, Side.SCREENER.value, Side.TIJORI.value)
_PAIR_SIDE_FIELDS: Final[tuple[str, ...]] = ("left", "right")

# The three comparisons one row carries, in the order the summary states them.
_SUMMARY_PAIRS: Final[tuple[tuple[Side, Side], ...]] = (
    (Side.XBRL, Side.SCREENER),
    (Side.XBRL, Side.TIJORI),
    (Side.SCREENER, Side.TIJORI),
)

_REFUSED_EVENT: Final = "three_source_refused"
_WRITTEN_EVENT: Final = "three_source_report_written"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WATCHLIST_PATH = _REPO_ROOT / "config" / "watchlist.yaml"
_DEFAULT_SCREENER_ROOT = _REPO_ROOT / "data" / "raw" / "watchlist" / "screener-financials"
_DEFAULT_GOLD_DIR = _REPO_ROOT / "data" / "gold"
_DEFAULT_SNAPSHOT_ROOT = _REPO_ROOT / "data" / "raw" / "snapshots" / "v1"

_HELP = "compare one stock-quarter across XBRL, Screener and Tijori from retained evidence"
_STOCK_HELP = "watchlist NSE symbol, e.g. TITAN (one stock per run)"
_CONFIG_HELP = "path to watchlist.yaml"
_SCREENER_ROOT_HELP = "root of screener-financials output: <root>/<symbol>/<basis>/"
_BASIS_HELP = "which set of books to compare (default: consolidated)"
_GOLD_DIR_HELP = "directory holding <symbol>-<quarter>.json gold files (default: data/gold)"
_SNAPSHOT_ROOT_HELP = "retained-capture tree root (default: data/raw/snapshots/v1)"
_CAPTURE_ID_HELP = "pin the Tijori side to one capture (default: the newest OK capture)"
_OUT_DIR_HELP = "directory the comparison report is written to"
_INCLUDE_VALUES_HELP = "state raw amounts and labels; off by default (counts and outcomes only)"
_WARN_EXIT_HELP = "exit non-zero when a readable run warned; off by default (log-only)"


class ThreeSourceRun(BaseModel):
    """What one ``three-source-crosscheck`` run produced.

    ``warn_count`` is telemetry; the report's own ``warn`` flag is what the exit
    code is decided on, so the two can never disagree about the process status.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    report: TripleReport
    report_path: Path
    warn_count: int
    tijori_capture_id: str | None


def add_three_source_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``three-source-crosscheck`` and its ten flags."""
    parser = subparsers.add_parser(THREE_SOURCE_COMMAND, help=_HELP)
    parser.add_argument("--stock", required=True, help=_STOCK_HELP)
    parser.add_argument("--out-dir", required=True, help=_OUT_DIR_HELP)
    parser.add_argument("--config", default=str(_DEFAULT_WATCHLIST_PATH), help=_CONFIG_HELP)
    parser.add_argument(
        "--screener-root", default=str(_DEFAULT_SCREENER_ROOT), help=_SCREENER_ROOT_HELP
    )
    parser.add_argument(
        "--basis",
        choices=(Basis.CONSOLIDATED.value, Basis.STANDALONE.value),
        default=Basis.CONSOLIDATED.value,
        help=_BASIS_HELP,
    )
    parser.add_argument("--gold-dir", default=str(_DEFAULT_GOLD_DIR), help=_GOLD_DIR_HELP)
    parser.add_argument(
        "--snapshot-root", default=str(_DEFAULT_SNAPSHOT_ROOT), help=_SNAPSHOT_ROOT_HELP
    )
    parser.add_argument("--capture-id", default=None, help=_CAPTURE_ID_HELP)
    parser.add_argument("--include-values", action="store_true", help=_INCLUDE_VALUES_HELP)
    parser.add_argument("--warn-exit", action="store_true", help=_WARN_EXIT_HELP)


def _resolve_stock(config_path: Path, symbol: str) -> StockConfig:
    """The watchlist entry for one symbol, or an argparse-level refusal.

    A symbol nobody configured is an operator typo, not a comparison outcome, so
    it fails the way every sibling command's unknown stock does.
    """
    watchlist = load_watchlist_config(config_path)
    try:
        return watchlist.stock(symbol)
    except ValueError as error:
        raise SystemExit(str(error)) from error


def select_tijori_capture(
    store: SnapshotStore, *, slug: str, capture_id: str | None
) -> CaptureRecord | None:
    """The retained Tijori capture this run reads, or ``None`` when none exists.

    Pinned, the named capture is returned whatever state it sealed — refusing a
    non-OK body is the reader's job, and silently falling back to another
    capture would publish a number the operator did not ask for. Unpinned, the
    newest OK capture wins, so an unpinned re-run reproduces the vendor's
    current page.
    """
    route = financials_request(slug)
    if capture_id is not None:
        return store.get_capture(route.source_id, route.surface, route.request_key, capture_id)
    published = store.list_captures(route.source_id, route.surface, route.request_key)
    usable = [record for record in published if record.outcome.code is OutcomeCode.OK]
    return usable[-1] if usable else None


def _warns(pair: PairResult) -> bool:
    """Whether one pair earns the report's warn flag.

    Restates the rule :func:`fundamentals.verify.three_source.compare_triple`
    raised ``TripleReport.warn`` under, so ``warn_count`` counts the same pairs
    the flag was raised by. The flag, not this count, decides the exit code.
    """
    if pair.outcome is PairOutcome.MISMATCH:
        return True
    return pair.outcome is PairOutcome.ANOMALY and pair.triage in (
        PairTriage.MAGNITUDE,
        PairTriage.STRUCTURAL,
    )


def _warn_count(report: TripleReport) -> int:
    """How many of the report's pairs earned its warn flag."""
    return sum(1 for row in report.rows for pair in row.pairs if _warns(pair))


def _redacted_side(side: dict[str, Any]) -> dict[str, Any]:
    """One serialized side value with its figure and vendor label withheld."""
    return {**side, AMOUNT_FIELD: REDACTED_AMOUNT, RAW_LABEL_FIELD: REDACTED_LABEL}


def _redacted_pair(pair: dict[str, Any]) -> dict[str, Any]:
    """One serialized pair with both of its side values withheld."""
    redacted = dict(pair)
    for field in _PAIR_SIDE_FIELDS:
        if redacted.get(field) is not None:
            redacted[field] = _redacted_side(redacted[field])
    return redacted


def _redacted_row(row: dict[str, Any]) -> dict[str, Any]:
    """One serialized row with every side value on it, and in its pairs, withheld."""
    redacted = dict(row)
    for field in _ROW_SIDE_FIELDS:
        if redacted.get(field) is not None:
            redacted[field] = _redacted_side(redacted[field])
    redacted[PAIRS_FIELD] = [_redacted_pair(pair) for pair in row[PAIRS_FIELD]]
    return redacted


def report_payload(report: TripleReport, *, include_values: bool) -> dict[str, Any]:
    """Serialize one report, withholding every raw figure unless asked for them.

    A projection of the serialized document rather than a second, narrower
    comparison: outcomes, counts, tiers, tolerances and origins are identical
    either way, so a redacted report and a full one are the same measurement.
    """
    payload: dict[str, Any] = report.model_dump(mode="json")
    if include_values:
        return payload
    return {**payload, ROWS_FIELD: [_redacted_row(row) for row in payload[ROWS_FIELD]]}


def run_three_source_command(
    args: argparse.Namespace,
    *,
    config_path: Path,
    screener_root: Path,
    gold_dir: Path,
    snapshot_root: Path,
    out_dir: Path,
) -> ThreeSourceRun:
    """Read the three retained sides of one stock-quarter and write one report.

    Every side is read before anything is written, so a run that refuses an
    input leaves no partial report behind to be quoted. The report is created
    no-clobber: a second run into the same directory refuses rather than
    replacing evidence an earlier measurement was read out of.
    """
    stock = _resolve_stock(config_path, str(args.stock))
    basis = str(args.basis)
    period_end = stock.quarter.period_end
    symbol = stock.symbol

    spine = read_gold_spine(
        gold_file_path(symbol, stock.quarter.label, gold_dir), symbol=symbol, period_end=period_end
    )
    screener = screener_side_values(
        read_screener_sections(screener_root, symbol=symbol, basis=basis), period_end=period_end
    )

    store = SnapshotStore(snapshot_root)
    slug = stock.identifiers.tijori_slug
    capture_id = str(args.capture_id) if args.capture_id else None
    record = select_tijori_capture(store, slug=slug, capture_id=capture_id)
    tijori: tuple[SideValue, ...] = ()
    if record is not None:
        tijori = read_tijori_capture(
            store,
            record,
            slug=slug,
            expected_symbol=symbol,
            expected_company_id=stock.identifiers.tijori_company_id,
            period_end=period_end,
        )

    report = compare_triple(
        spine,
        screener,
        tijori,
        symbol=symbol,
        period_end=period_end,
        capture_ids=() if record is None else (record.capture_id,),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_FILENAME
    include_values = bool(args.include_values)
    document = json.dumps(report_payload(report, include_values=include_values), indent=2) + "\n"
    write_bytes_no_clobber(report_path, document.encode("utf-8"))

    warn_count = _warn_count(report)
    _LOGGER.info(
        _WRITTEN_EVENT,
        stock=symbol,
        period_end=period_end.isoformat(),
        rows=len(report.rows),
        warn=report.warn,
        warn_count=warn_count,
        capture_id=None if record is None else record.capture_id,
        include_values=include_values,
        path=str(report_path),
    )
    return ThreeSourceRun(
        report=report,
        report_path=report_path,
        warn_count=warn_count,
        tijori_capture_id=None if record is None else record.capture_id,
    )


def _outcome_cell(row: TripleRow, left: Side, right: Side) -> str:
    """The outcome of one named comparison on this row."""
    for pair in row.pairs:
        if (pair.left_side, pair.right_side) == (left, right):
            return pair.outcome.value
    return MISSING_CELL


def _triage_cell(row: TripleRow) -> str:
    """The first pair triage on this row worth a reviewer's attention."""
    for pair in row.pairs:
        if pair.triage is not PairTriage.NONE:
            return pair.triage.value
    return PairTriage.NONE.value


def _amount_cell(value: SideValue | None) -> str:
    """One side's figure, or the marker for a side that stated none."""
    return MISSING_CELL if value is None else str(value.amount)


def _summary_row(row: TripleRow, *, include_values: bool) -> str:
    """One concept's line: its three outcomes, its triage, and its figures if asked."""
    cells = [
        row.concept_qname,
        *(_outcome_cell(row, left, right) for left, right in _SUMMARY_PAIRS),
        _triage_cell(row),
    ]
    if include_values:
        cells.extend(_amount_cell(value) for value in (row.xbrl, row.screener, row.tijori))
    return SUMMARY_SEPARATOR.join(cells)


def _totals_row(report: TripleReport) -> str:
    """The closing line: every outcome count, and whether the run warned.

    Counts are stated for every outcome including the zeroes, so a reader
    comparing two runs does not have to know which outcomes a run can produce.
    """
    counts = COUNT_SEPARATOR.join(
        f"{outcome.value}={report.counts.get(outcome, 0)}" for outcome in PairOutcome
    )
    return SUMMARY_SEPARATOR.join((TOTALS_LABEL, counts, f"{WARN_FIELD}={report.warn}"))


def render_three_source_summary(run: ThreeSourceRun, *, include_values: bool = False) -> str:
    """Render one run as a header, one line per concept, and a totals line.

    No figure appears unless ``include_values`` asks for one, so the default
    stdout of a sweep can be pasted into a research doc without publishing a
    vendor's numbers.
    """
    columns = SUMMARY_COLUMNS + VALUE_COLUMNS if include_values else SUMMARY_COLUMNS
    lines = [SUMMARY_SEPARATOR.join(columns)]
    lines.extend(_summary_row(row, include_values=include_values) for row in run.report.rows)
    lines.append(_totals_row(run.report))
    return "\n".join(lines)


def dispatch_three_source_command(args: argparse.Namespace) -> int | None:
    """Run ``three-source-crosscheck`` and return its exit code, or ``None`` for another command.

    This is the only place ``--warn-exit`` acts, and the only place a refusal
    becomes a status. A report path that already exists is the store's own
    refusal; every unreadable input — an unstated precision, a mismatched
    identity, a capture that will not re-read — outranks any number of
    disagreements, because it says the comparison did not happen at all.
    """
    if getattr(args, "command", None) != THREE_SOURCE_COMMAND:
        return None
    try:
        run = run_three_source_command(
            args,
            config_path=Path(args.config),
            screener_root=Path(args.screener_root),
            gold_dir=Path(args.gold_dir),
            snapshot_root=Path(args.snapshot_root),
            out_dir=Path(args.out_dir),
        )
    except CaptureConflictError as refusal:
        _LOGGER.warning(_REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal))
        return EXIT_REFUSED
    except (InputError, SnapshotError) as refusal:
        _LOGGER.warning(_REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal))
        return EXIT_UNREADABLE
    sys.stdout.write(
        render_three_source_summary(run, include_values=bool(args.include_values)) + "\n"
    )
    if args.warn_exit and run.report.warn:
        return EXIT_WARN
    return EXIT_OK
