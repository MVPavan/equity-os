"""The ``upstox-crosscheck-sensitivity`` command: how much would Lane B notice?

    upstox-crosscheck-sensitivity --isin-file <path> --screener-root <dir>
                                  --upstox-root <dir> --out <dir>
                                  [--basis standalone|consolidated|both]

A quiet ``upstox-crosscheck`` report and a blind one look identical. This
command tells them apart by seeding one known parser defect at a time into the
Screener side and re-running the same comparison, then reporting how often the
comparison moved. It is a measurement of the instrument, not of the companies.

**Zero requests, ever.** Both sides are read from disk: the Screener sections
from ``screener-financials``' own layout, and the Upstox bodies from a retention
tree an earlier ``upstox-crosscheck --out-dir`` run wrote. The replay reader,
the ISIN join, the basis expansion and the section loader are the crosscheck
command's own, imported rather than re-implemented, so a sensitivity number can
never be measured against a slightly different reader than the lane uses.

**Exit 0 on a measurement, whatever it says.** A comparator that noticed nothing
still exits 0: the number this command produces is the one nobody has yet, and a
number nobody has measured cannot be a threshold. Exit 3 is reserved for inputs
that could not be read at all (decision P6) — a missing ``--screener-root``, a
section file that does not parse, a retained body that no longer matches the
hash recorded beside it. A company merely absent from a readable root is a gap
in coverage, recorded in ``skipped`` with its reason, and the run continues.

The ``--out`` artifact is refused *before* anything is measured: a sweep that
spent its whole run and then found the report path occupied would throw away the
measurement it had just made.

Nothing is logged on the measuring path. The TSV goes to stdout and the JSON to
``<out>/laneb_sensitivity_report.json``; a caller that has not configured
structlog would otherwise find a log line at the top of the table.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import structlog

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber

# The crosscheck command's own readers. Imported rather than copied: a
# sensitivity number measured against a second implementation of the replay
# loader or the section loader would be a number about that copy, not about the
# lane this command exists to measure.
from fundamentals.api.upstox_crosscheck_cli import (
    BOTH_BASES,
    is_valid_isin,
    load_screener_sections,
    read_isin_file,
    read_retained_bodies,
    requested_bases,
)
from fundamentals.ingest.screener_crosscheck import EvidenceTier
from fundamentals.ingest.upstox_crosscheck import EXIT_OK, EXIT_UNREADABLE, ScreenerSection
from fundamentals.ingest.upstox_source import UpstoxError, UpstoxSurface
from fundamentals.ingest.upstox_statements import (
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)
from fundamentals.verify.laneb_sensitivity import (
    ClassificationCounts,
    MutationClass,
    SensitivityCell,
    SensitivityReport,
    SkippedCompany,
    SkipReason,
    measure_sensitivity,
    period_counts,
    row_counts,
)

_LOGGER = structlog.get_logger(__name__)

UPSTOX_SENSITIVITY_COMMAND = "upstox-crosscheck-sensitivity"
REPORT_FILENAME = "laneb_sensitivity_report.json"

TSV_HEADER = "mutation\ttier\tdetected\tundetected\tmasked\tblind\tnot_applicable\tsensitivity"
TOTAL_LABEL = "TOTAL"
ALL_TIERS_LABEL = "ALL"
UNMAPPED_LABEL = "UNMAPPED"
COVERAGE_LABEL = "COVERAGE"
PERIOD_COVERAGE_LABEL = "PERIOD_COVERAGE"
_ABSENT = "-"
_EMPTY = ""
_RATIO_PLACES = Decimal("0.0001")

_HELP = "measure whether upstox-crosscheck would notice a seeded parser defect"
_ISIN_FILE_HELP = "two-column TSV: <isin>\\t<nse symbol>, one company per line"
_SCREENER_ROOT_HELP = "root of screener-financials output: <root>/<symbol>/<basis>/"
_UPSTOX_ROOT_HELP = "retention tree an earlier upstox-crosscheck run wrote"
_OUT_HELP = "directory the sensitivity report is written to"
_BASIS_HELP = "which set of books to measure (default: consolidated)"

_MISSING_ROOT = "{flag} {path} is not a readable directory"
_UNREADABLE_JOIN = "{path} could not be read as an isin/symbol join: {reason}"
_UNREADABLE_SECTIONS = "{directory} holds a screener section this run cannot read: {reason}"
_REFUSED_EVENT = "upstox_sensitivity_refused"
_SCREENER_ROOT_FLAG = "--screener-root"
_UPSTOX_ROOT_FLAG = "--upstox-root"


class SensitivityInputError(ValueError):
    """An input this command was given and could not read.

    A typed refusal rather than the ``SystemExit`` the readers raise on their own
    behalf: this command has to turn an unreadable input into exit 3 (P6), and
    catching ``SystemExit`` around a whole run would also swallow every other
    deliberate exit inside it.
    """


def add_upstox_sensitivity_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``upstox-crosscheck-sensitivity`` and its five flags."""
    parser = subparsers.add_parser(UPSTOX_SENSITIVITY_COMMAND, help=_HELP)
    parser.add_argument("--isin-file", required=True, help=_ISIN_FILE_HELP)
    parser.add_argument("--screener-root", required=True, help=_SCREENER_ROOT_HELP)
    parser.add_argument("--upstox-root", required=True, help=_UPSTOX_ROOT_HELP)
    parser.add_argument(
        "--basis",
        choices=(StatementBasis.STANDALONE.value, StatementBasis.CONSOLIDATED.value, BOTH_BASES),
        default=StatementBasis.CONSOLIDATED.value,
        help=_BASIS_HELP,
    )
    parser.add_argument("--out", required=True, help=_OUT_HELP)


def dispatch_upstox_sensitivity_command(args: argparse.Namespace) -> int | None:
    """Run the measurement and return its exit code, or ``None`` for another command."""
    if getattr(args, "command", None) != UPSTOX_SENSITIVITY_COMMAND:
        return None
    out_dir = Path(args.out)
    report_path = out_dir / REPORT_FILENAME
    # Refused before anything is measured, and the directory is not created
    # until there is something to put in it: a sweep that spent its whole run
    # and then found the path occupied would throw the measurement away, and a
    # run that refused its inputs should leave nothing behind.
    preflight_out_paths((report_path,))

    try:
        report = run_upstox_sensitivity_command(
            isin_file=Path(args.isin_file),
            screener_root=Path(args.screener_root),
            upstox_root=Path(args.upstox_root),
            bases=requested_bases(str(args.basis)),
        )
    # P6's unreadable input: a root that is not there, a section that will not
    # parse, a retained body that no longer hashes to its record
    # (``RetainedBodyError`` is an ``UpstoxError``), or one the filesystem simply
    # would not hand over — a retention tree on a disconnected volume answers
    # ``is_file()`` and then raises on the read. A refusal to measure, not a
    # measurement of zero sensitivity.
    except (OSError, SensitivityInputError, UpstoxError) as refusal:
        _LOGGER.warning(_REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal))
        return EXIT_UNREADABLE

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_no_clobber(report_path, report.model_dump_json(indent=2) + "\n")
    sys.stdout.write(render_sensitivity(report) + "\n")
    return EXIT_OK


def render_sensitivity(report: SensitivityReport) -> str:
    """Render one measurement as TSV: (class, tier) lines, a total, then coverage.

    The coverage lines share the header because they answer the other half of
    the same question, and a second table would be read as a second run. On a
    ``COVERAGE`` or ``PERIOD_COVERAGE`` line the ``detected`` and ``undetected``
    columns carry the covered and total counts — mapped rows over rows on the
    page, and periods the comparison produced a row for over periods on the page
    — and the remaining count columns are empty.

    A ``DETECTED`` cell is usually a ``MISSING_SCREENER``: the seeded defect
    leaves a mapping's Screener side incomplete and the comparator refuses to
    score it. That refusal reaches ``upstox-crosscheck``'s row-level JSON but
    not its summary line, which prints only agree / mismatch / anomaly /
    not_comparable / unmet_tier3 — so these numbers describe what the comparator
    records, not what its own table shows.

    Two things a reader must not misread. A tier-3 row counts as *mapped* in
    ``COVERAGE``: the name map names it, so it is not part of the blind fraction
    that coverage measures, even though nothing may be concluded from its values
    (that is what the ``BLIND_TIER3`` counts are for). And unmapped cells have
    no tier at all (P3), so their group is labelled ``UNMAPPED`` rather than
    filed under one. Ratios are shown to four places; the exact unquantized ones
    are in the JSON report.
    """
    lines = [TSV_HEADER]
    for mutation in MutationClass:
        for tier in (*EvidenceTier, None):
            group = [
                cell for cell in report.cells if cell.mutation is mutation and cell.tier is tier
            ]
            if group:
                label = UNMAPPED_LABEL if tier is None else tier.value
                lines.append(_count_line(mutation.value, label, ClassificationCounts.tally(group)))
    lines.append(
        _count_line(TOTAL_LABEL, ALL_TIERS_LABEL, ClassificationCounts.tally(report.cells))
    )
    for section, coverage in report.coverage_by_section.items():
        lines.append(
            _ratio_line(COVERAGE_LABEL, section, row_counts(report.cells, section), coverage)
        )
    for section, coverage in report.period_coverage_by_section.items():
        lines.append(
            _ratio_line(
                PERIOD_COVERAGE_LABEL, section, period_counts(report.cells, section), coverage
            )
        )
    return "\n".join(lines)


def _count_line(mutation: str, tier: str, counts: ClassificationCounts) -> str:
    """One TSV line of counts for a (class, tier) slice."""
    return "\t".join(
        (
            mutation,
            tier,
            str(counts.detected),
            str(counts.undetected),
            str(counts.masked),
            str(counts.blind),
            str(counts.not_applicable),
            _ratio(counts.sensitivity),
        )
    )


def _ratio_line(label: str, section: str, counted: tuple[int, int], ratio: Decimal) -> str:
    """One TSV line of a covered/total ratio for one section."""
    covered, total = counted
    return "\t".join(
        (label, section, str(covered), str(total), _EMPTY, _EMPTY, _EMPTY, _ratio(ratio))
    )


def _ratio(value: Decimal | None) -> str:
    """Render a ratio to four places, or the absent marker when it has no denominator."""
    if value is None:
        return _ABSENT
    return format(value.quantize(_RATIO_PLACES), "f")


def run_upstox_sensitivity_command(
    *,
    isin_file: Path,
    screener_root: Path,
    upstox_root: Path,
    bases: tuple[StatementBasis, ...],
) -> SensitivityReport:
    """Measure every listed company on every requested basis, from files only.

    Both roots are checked before any company is looked at: a root that is not
    there would otherwise present as every company being absent, which is P6's
    other case and carries the opposite verdict.
    """
    _require_directory(screener_root, _SCREENER_ROOT_FLAG)
    _require_directory(upstox_root, _UPSTOX_ROOT_FLAG)

    cells: list[SensitivityCell] = []
    skipped: list[SkippedCompany] = []
    for isin, symbol in _read_join(isin_file):
        for basis in bases:
            measured = _measure_company(
                isin=isin,
                symbol=symbol,
                basis=basis,
                screener_root=screener_root,
                upstox_root=upstox_root,
            )
            if isinstance(measured, SkipReason):
                skipped.append(SkippedCompany(symbol=symbol, basis=basis.value, reason=measured))
                continue
            cells.extend(measured.cells)
            skipped.extend(measured.skipped)
    return SensitivityReport.from_cells(cells, skipped=skipped)


def _measure_company(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    screener_root: Path,
    upstox_root: Path,
) -> SensitivityReport | SkipReason:
    """Measure one company on one basis, or say which gap stopped it.

    An invalid ISIN is skipped for the same reason the crosscheck never requests
    one: the identifier does not verify, so nothing keyed by it is trusted.
    """
    if not is_valid_isin(isin):
        return SkipReason.INVALID_ISIN
    sections = _read_sections(screener_root / symbol / basis.value)
    if sections is None:
        return SkipReason.NO_SCREENER_SECTIONS
    bodies = read_retained_bodies(upstox_root / symbol / basis.value)
    if bodies is None:
        return SkipReason.NO_RETAINED_BODIES
    return measure_sensitivity(
        isin=isin,
        symbol=symbol,
        basis=basis,
        sections=sections,
        income=read_income_statement(bodies[UpstoxSurface.INCOME_STATEMENT], requested_basis=basis),
        balance=read_balance_sheet(bodies[UpstoxSurface.BALANCE_SHEET], requested_basis=basis),
        cash=read_cash_flow(bodies[UpstoxSurface.CASH_FLOW], requested_basis=basis),
    )


def _read_join(isin_file: Path) -> tuple[tuple[str, str], ...]:
    """Read the ISIN/symbol join, restating its refusals as this command's own."""
    try:
        return read_isin_file(isin_file)
    except (OSError, SystemExit) as refusal:
        raise SensitivityInputError(
            _UNREADABLE_JOIN.format(path=isin_file, reason=refusal)
        ) from refusal


def _read_sections(directory: Path) -> dict[str, ScreenerSection] | None:
    """Read one company's sections, restating an unreadable one as this command's own.

    ``None`` — no sections at all — is a skip, not a refusal (P6). A section that
    exists and will not parse is the refusal.
    """
    try:
        return load_screener_sections(directory)
    except SystemExit as refusal:
        raise SensitivityInputError(
            _UNREADABLE_SECTIONS.format(directory=directory, reason=refusal)
        ) from refusal


def _require_directory(path: Path, flag: str) -> None:
    """Refuse a root that is not there, rather than reporting an empty measurement."""
    if not path.is_dir():
        raise SensitivityInputError(_MISSING_ROOT.format(flag=flag, path=path))


__all__ = [
    "REPORT_FILENAME",
    "TSV_HEADER",
    "UPSTOX_SENSITIVITY_COMMAND",
    "SensitivityInputError",
    "add_upstox_sensitivity_parser",
    "dispatch_upstox_sensitivity_command",
    "render_sensitivity",
    "run_upstox_sensitivity_command",
]
