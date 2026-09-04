"""The ``upstox-crosscheck`` command: Lane B's log-only differential check.

    upstox-crosscheck --isin-file <path> --screener-root <dir> --out-dir <dir>
                      [--basis standalone|consolidated|both]

**Nothing this command produces is a fact.** Upstox and Screener share upstream
lineage, which disqualifies Upstox from corroborating Screener and is exactly
what makes it useful for detecting *extraction drift*. A disagreement gives a
triage direction, never a diagnosis, so the exit code ignores every mismatch it
finds. Only a parse failure — a response this repo could not read — is non-zero.

**Two guards decide whether to call at all, and both exist because of one live
finding.** An unknown ISIN answers ``{"status":"success","data":[]}`` with HTTP
200, byte-identical to a real company with nothing to report. No envelope check
can separate them, so the separation has to happen before the request:

1. the ISIN must carry a valid ISO 6166 check digit, and
2. the ``--screener-root`` must already hold that company's sections.

A company failing either is recorded as skipped and never requested. The second
guard also happens to be the honest one: there is nothing to compare against.

**``--isin-file`` is a two-column TSV**, ``<isin>\\t<symbol>``. Screener knows
companies by NSE symbol and Upstox by ISIN, and neither artifact carries the
other's key, so the join is stated explicitly in a file a human can audit rather
than inferred at run time.

**Screener layout** follows ``screener-financials``' own default:
``<screener-root>/<symbol>/<basis>/section_<name>.json``. Three sections are
read — ``profit-loss``, ``balance-sheet``, ``cash-flow`` — and a row label
appearing in more than one of them is refused rather than resolved, because
which section a value came from would then depend on file order.

Only annual figures are compared. ``balance-sheet`` and ``cash-flow`` discard
``time_period`` outright, and under a quarterly ``income-statement`` request the
two blocks of one payload carry different periodicities under the same period
labels — so a quarterly comparison would need a different alignment than this
one and is deliberately not offered.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fundamentals.api.artifact_writer import preflight_out_paths, write_json_no_clobber
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.api.upstox_cli import SourceLike
from fundamentals.ingest.screener_crosscheck import (
    INCOME_STATEMENT_MAP,
    CrosscheckOutcome,
    CrosscheckReport,
    CrosscheckRow,
    LineMapping,
    StatedValue,
    compare_line,
)
from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxConfig,
    UpstoxCredentials,
    UpstoxError,
    UpstoxSource,
    UpstoxSurface,
    route_for,
)
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)

_LOGGER = structlog.get_logger(__name__)

UPSTOX_CROSSCHECK_COMMAND = "upstox-crosscheck"
REPORT_FILENAME = "upstox_crosscheck_report.json"

BOTH_BASES = "both"
BASIS_QUERY_KEY = "type"
FULL_STATEMENT_QUERY_KEY = "fs"
FULL_STATEMENT_QUERY_VALUE = "true"

SECTION_FILENAME_TEMPLATE = "section_{section}.json"
COMPARED_SECTIONS: tuple[str, ...] = ("profit-loss", "balance-sheet", "cash-flow")

_ISIN_LENGTH = 12
_ISIN_COUNTRY_LENGTH = 2
_ALPHABET_OFFSET = 55  # ord("A") - 10, so "A" expands to 10 and "Z" to 35.

EXIT_OK = 0
EXIT_UNREADABLE = 3
_REFUSED_EVENT = "upstox_crosscheck_refused"

SUMMARY_HEADER = (
    "isin\tsymbol\tbasis\tstatus\tagree\tmismatch\tanomaly\tnot_comparable\tunmet_tier3"
)

_HELP = "compare Upstox statement values against Screener's, log-only"
_ISIN_FILE_HELP = "two-column TSV: <isin>\\t<nse symbol>, one company per line"
_SCREENER_ROOT_HELP = "root of screener-financials output: <root>/<symbol>/<basis>/"
_OUT_DIR_HELP = "directory the disagreement report is written to"
_BASIS_HELP = "which set of books to compare (default: consolidated)"

_BAD_LINE = "{path} line {number}: expected <isin>\\t<symbol>, got {line!r}"
_REPEATED = "{path} line {number}: isin {isin} is repeated"
_EMPTY_FILE = "{path} holds no isin/symbol lines"
_AMBIGUOUS_ROW = "screener row {label!r} appears in both {first} and {second}; refusing to guess"
_UNREADABLE_SECTION = "{path} is not readable as a screener section: {reason}"


class _ScreenerCell(BaseModel):
    """One Screener cell, narrowed to what a comparison needs from it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    period_index: int = Field(ge=0)
    value: Decimal | None
    published: bool


class _ScreenerRow(BaseModel):
    """One Screener row, narrowed to its label and its cells."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    label: str = Field(min_length=1)
    cells: tuple[_ScreenerCell, ...] = ()


class _ScreenerPeriod(BaseModel):
    """One Screener column, narrowed to the index and label a value is addressed by."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    index: int = Field(ge=0)
    label: str = Field(min_length=1)


class _ScreenerSection(BaseModel):
    """The part of a ``section_*.json`` artifact Lane B actually reads.

    Deliberately narrower than :class:`SectionTable`. Validating the whole
    artifact coupled the comparator to ``schedules``, ``growth_tables`` and
    ``quarantined`` — blocks no comparison touches — so a change in any of them
    made a log-only lane refuse rows it could read perfectly well. What is read
    stays strict; what is not read is not a dependency.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    periods: tuple[_ScreenerPeriod, ...] = ()
    rows: tuple[_ScreenerRow, ...] = ()


class CompanyStatus(StrEnum):
    """What happened to one company on one basis."""

    COMPARED = "COMPARED"
    SKIPPED_INVALID_ISIN = "SKIPPED_INVALID_ISIN"
    SKIPPED_NO_SCREENER_DATA = "SKIPPED_NO_SCREENER_DATA"
    UPSTOX_UNREADABLE = "UPSTOX_UNREADABLE"


class CompanyCrosscheck(BaseModel):
    """One company on one basis: what was compared, or why nothing was."""

    model_config = ConfigDict(frozen=True)

    isin: str
    symbol: str
    basis: str
    status: CompanyStatus
    detail: str | None = None
    reports: tuple[CrosscheckReport, ...] = ()


class CrosscheckRunReport(BaseModel):
    """Every company one invocation looked at. Carries no fact or provenance type."""

    model_config = ConfigDict(frozen=True)

    companies: tuple[CompanyCrosscheck, ...] = ()

    @property
    def mismatch_count(self) -> int:
        """Tier-1 lines that breached their derived tolerance."""
        return self._count(CrosscheckOutcome.MISMATCH)

    @property
    def anomaly_count(self) -> int:
        """Tier-2 lines that breached their derived interval."""
        return self._count(CrosscheckOutcome.ANOMALY)

    @property
    def unmet_tier3_count(self) -> int:
        """Tier-3 lines whose two values differ beyond their derived tolerance.

        ``NOT_COMPARABLE`` is the honest verdict for a line whose equivalence
        was never demonstrated, and it is returned whatever the numbers say. But
        a tier-3 line can still be the largest disagreement in a run — on the
        first live replay, NETWEB's Mar-2026 operating cash flow read 789.92
        against Screener's 171 — and counting only mismatches and anomalies
        would leave it invisible in every summary. This counts them without
        claiming anything about them: it says which tier-3 lines are worth a
        reviewer's time, which is the input the graduation procedure needs.
        """
        return sum(
            1
            for company in self.companies
            for report in company.reports
            for row in report.rows
            if row.outcome is CrosscheckOutcome.NOT_COMPARABLE
            and row.difference is not None
            and row.tolerance is not None
            and row.difference > row.tolerance
        )

    @property
    def unreadable_count(self) -> int:
        """Companies whose Upstox response this repo could not read."""
        return sum(
            1 for company in self.companies if company.status is CompanyStatus.UPSTOX_UNREADABLE
        )

    @property
    def exit_code(self) -> int:
        """Zero however many disagreements were found; non-zero only on a parse failure.

        Decision A is log-only and this is where that is enforced. The base
        disagreement rate is unmeasured, and a check that blocks on an unknown
        rate is switched off within a day.
        """
        return EXIT_UNREADABLE if self.unreadable_count else EXIT_OK

    def _count(self, outcome: CrosscheckOutcome) -> int:
        return sum(
            1
            for company in self.companies
            for report in company.reports
            for row in report.rows
            if row.outcome is outcome
        )

    def render(self) -> str:
        """Render the run as TSV: one header, then one row per company and basis."""
        lines = [SUMMARY_HEADER]
        for company in self.companies:
            counts = {outcome: 0 for outcome in CrosscheckOutcome}
            unmet = 0
            for report in company.reports:
                for row in report.rows:
                    counts[row.outcome] += 1
                    if (
                        row.outcome is CrosscheckOutcome.NOT_COMPARABLE
                        and row.difference is not None
                        and row.tolerance is not None
                        and row.difference > row.tolerance
                    ):
                        unmet += 1
            lines.append(
                "\t".join(
                    (
                        company.isin,
                        company.symbol,
                        company.basis,
                        company.status.value,
                        str(counts[CrosscheckOutcome.AGREE]),
                        str(counts[CrosscheckOutcome.MISMATCH]),
                        str(counts[CrosscheckOutcome.ANOMALY]),
                        str(counts[CrosscheckOutcome.NOT_COMPARABLE]),
                        str(unmet),
                    )
                )
            )
        return "\n".join(lines)


def add_upstox_crosscheck_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``upstox-crosscheck`` and its four flags."""
    parser = subparsers.add_parser(UPSTOX_CROSSCHECK_COMMAND, help=_HELP)
    parser.add_argument("--isin-file", required=True, help=_ISIN_FILE_HELP)
    parser.add_argument("--screener-root", required=True, help=_SCREENER_ROOT_HELP)
    parser.add_argument("--out-dir", required=True, help=_OUT_DIR_HELP)
    parser.add_argument(
        "--basis",
        choices=(StatementBasis.STANDALONE.value, StatementBasis.CONSOLIDATED.value, BOTH_BASES),
        default=StatementBasis.CONSOLIDATED.value,
        help=_BASIS_HELP,
    )


def is_valid_isin(isin: str) -> bool:
    """Whether a string is a well-formed ISIN with a correct ISO 6166 check digit.

    The only guard that can precede the request. An unknown ISIN answers with a
    successful empty payload, so a malformed one must never reach the wire —
    the response would look exactly like a real company with nothing to report.
    """
    if len(isin) != _ISIN_LENGTH or not isin.isalnum() or not isin.isupper():
        return False
    if not isin[:_ISIN_COUNTRY_LENGTH].isalpha() or not isin[-1].isdigit():
        return False
    digits = "".join(
        character if character.isdigit() else str(ord(character) - _ALPHABET_OFFSET)
        for character in isin[:-1]
    )
    total = 0
    for position, digit in enumerate(reversed(digits)):
        value = int(digit)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (10 - total % 10) % 10 == int(isin[-1])


def read_isin_file(path: Path) -> tuple[tuple[str, str], ...]:
    """Read the ``<isin>\\t<symbol>`` join, refusing anything it cannot read exactly.

    A repeated ISIN is refused rather than de-duplicated: the same company under
    two symbols is a mistake in the join, and comparing it twice would double
    its weight in every count the report carries.
    """
    pairs: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise SystemExit(_BAD_LINE.format(path=path, number=number, line=line))
        isin, symbol = parts[0].strip(), parts[1].strip()
        if isin in seen:
            raise SystemExit(_REPEATED.format(path=path, number=number, isin=isin))
        seen[isin] = number
        pairs.append((isin, symbol))
    if not pairs:
        raise SystemExit(_EMPTY_FILE.format(path=path))
    return tuple(pairs)


def run_upstox_crosscheck_command(
    args: argparse.Namespace,
    *,
    isin_file: Path,
    screener_root: Path,
    out_dir: Path,
    source: SourceLike,
) -> CrosscheckRunReport:
    """Compare every listed company on every requested basis and write one report."""
    bases = _requested_bases(str(args.basis))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_FILENAME
    preflight_out_paths((report_path,))

    companies: list[CompanyCrosscheck] = []
    for isin, symbol in read_isin_file(isin_file):
        for basis in bases:
            companies.append(
                _crosscheck_company(
                    isin=isin,
                    symbol=symbol,
                    basis=basis,
                    screener_root=screener_root,
                    source=source,
                )
            )
    run = CrosscheckRunReport(companies=tuple(companies))
    write_json_no_clobber(report_path, run.model_dump_json(indent=2) + "\n")
    _LOGGER.info(
        "upstox_crosscheck_written",
        companies=len(run.companies),
        mismatches=run.mismatch_count,
        anomalies=run.anomaly_count,
        unmet_tier3=run.unmet_tier3_count,
        unreadable=run.unreadable_count,
    )
    return run


def _requested_bases(requested: str) -> tuple[StatementBasis, ...]:
    """Expand ``--basis``, keeping a stable order so the report is comparable."""
    if requested == BOTH_BASES:
        return (StatementBasis.STANDALONE, StatementBasis.CONSOLIDATED)
    return (StatementBasis(requested),)


def _crosscheck_company(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    screener_root: Path,
    source: SourceLike,
) -> CompanyCrosscheck:
    """Run both pre-call guards, then compare — or say why nothing was requested."""
    if not is_valid_isin(isin):
        return CompanyCrosscheck(
            isin=isin,
            symbol=symbol,
            basis=basis.value,
            status=CompanyStatus.SKIPPED_INVALID_ISIN,
            detail="check digit does not verify; an unknown ISIN answers 200 with an "
            "empty payload, so it is never requested",
        )
    directory = screener_root / symbol / basis.value
    screener = _load_screener_values(directory)
    if screener is None:
        return CompanyCrosscheck(
            isin=isin,
            symbol=symbol,
            basis=basis.value,
            status=CompanyStatus.SKIPPED_NO_SCREENER_DATA,
            detail=f"no screener sections under {directory}",
        )

    query = {BASIS_QUERY_KEY: basis.value, FULL_STATEMENT_QUERY_KEY: FULL_STATEMENT_QUERY_VALUE}
    income = read_income_statement(
        source.fetch(route_for(UpstoxSurface.INCOME_STATEMENT), query, isin=isin),
        requested_basis=basis,
    )
    balance = read_balance_sheet(
        source.fetch(route_for(UpstoxSurface.BALANCE_SHEET), query, isin=isin),
        requested_basis=basis,
    )
    cash = read_cash_flow(
        source.fetch(route_for(UpstoxSurface.CASH_FLOW), query, isin=isin),
        requested_basis=basis,
    )
    unreadable = tuple(
        f"{document.surface.value}: {'; '.join(document.anomalies)}"
        for document in (income, balance, cash)
        if document.outcome is AcquisitionOutcome.SCHEMA_DRIFT
    )
    if unreadable:
        return CompanyCrosscheck(
            isin=isin,
            symbol=symbol,
            basis=basis.value,
            status=CompanyStatus.UPSTOX_UNREADABLE,
            detail=" | ".join(unreadable),
        )

    upstox = _upstox_values(income, balance, cash)
    reports = tuple(
        CrosscheckReport(
            isin=isin,
            basis=basis.value,
            period=period,
            rows=_rows_for_period(upstox.get(period, {}), screener, period),
        )
        for period in sorted(upstox, reverse=True)
    )
    return CompanyCrosscheck(
        isin=isin,
        symbol=symbol,
        basis=basis.value,
        status=CompanyStatus.COMPARED,
        reports=reports,
    )


def _rows_for_period(
    upstox: Mapping[str, StatedValue],
    screener: Mapping[str, Mapping[str, StatedValue]],
    period: str,
) -> tuple[CrosscheckRow, ...]:
    """Compare every mapped line for one period, in the map's declared order."""
    return tuple(
        compare_line(
            mapping,
            upstox=upstox.get(mapping.upstox_category),
            screener=_screener_side(mapping, screener, period),
        )
        for mapping in INCOME_STATEMENT_MAP
    )


def _screener_side(
    mapping: LineMapping,
    screener: Mapping[str, Mapping[str, StatedValue]],
    period: str,
) -> tuple[StatedValue, ...]:
    """Collect the Screener rows one mapping names, dropping any it did not publish.

    A partial set is returned as-is rather than padded. ``compare_line`` refuses
    to score an incomplete side, which is the point: summing some of the addends
    would manufacture a mismatch out of a coverage gap.
    """
    values: list[StatedValue] = []
    for label in mapping.screener_rows:
        stated = screener.get(label, {}).get(period)
        if stated is not None:
            values.append(stated)
    return tuple(values)


def _upstox_values(
    income: IncomeStatementDocument,
    balance: BalanceSheetDocument,
    cash: CashFlowDocument,
) -> dict[str, dict[str, StatedValue]]:
    """Index every Upstox summary value by period, then by the category it was stated under."""
    by_period: dict[str, dict[str, StatedValue]] = {}
    for document in (income, cash):
        for series in document.summary:
            for point in series.history:
                by_period.setdefault(point.period, {})[series.category] = _stated(
                    point.value, series.category
                )
    for entry in balance.history:
        slot = by_period.setdefault(entry.period, {})
        slot["total_asset"] = _stated(entry.total_asset, "total_asset")
        slot["total_liability"] = _stated(entry.total_liability, "total_liability")
    return by_period


def _load_screener_values(
    directory: Path,
) -> dict[str, dict[str, StatedValue]] | None:
    """Index one company's Screener sections by row label, then period label.

    ``None`` means no section was found at all, which is the second pre-call
    guard: there is nothing to compare against, so nothing is requested.
    """
    by_label: dict[str, dict[str, StatedValue]] = {}
    origin: dict[str, str] = {}
    found = False
    for section in COMPARED_SECTIONS:
        path = directory / SECTION_FILENAME_TEMPLATE.format(section=section)
        if not path.is_file():
            continue
        found = True
        try:
            table = _ScreenerSection.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            raise SystemExit(
                _UNREADABLE_SECTION.format(path=path, reason=error.errors()[0]["msg"])
            ) from error
        labels = {period.index: period.label for period in table.periods}
        for row in table.rows:
            if row.label in origin and origin[row.label] != section:
                raise SystemExit(
                    _AMBIGUOUS_ROW.format(label=row.label, first=origin[row.label], second=section)
                )
            origin[row.label] = section
            slot = by_label.setdefault(row.label, {})
            for cell in row.cells:
                label = labels.get(cell.period_index)
                if label is None or cell.value is None or not cell.published:
                    continue
                slot[label] = _stated(cell.value, row.label)
    return by_label if found else None


def _stated(amount: Decimal, raw_label: str) -> StatedValue:
    """Wrap one number with the precision the source stated it to."""
    exponent = amount.as_tuple().exponent
    decimals = -exponent if isinstance(exponent, int) else 0
    return StatedValue(amount=amount, decimals=max(decimals, 0), raw_label=raw_label)


def dispatch_upstox_crosscheck_command(
    args: argparse.Namespace,
    *,
    credentials_factory: Callable[[], UpstoxCredentials | None],
) -> int | None:
    """Run ``upstox-crosscheck`` and return its exit code, or ``None`` for another command.

    Every Lane B surface is authenticated, so a token-free run refuses here
    rather than issuing ten requests that will each come back 401.
    """
    if getattr(args, "command", None) != UPSTOX_CROSSCHECK_COMMAND:
        return None
    source = UpstoxSource(UpstoxConfig(credentials=credentials_factory()))
    try:
        run = run_upstox_crosscheck_command(
            args,
            isin_file=Path(args.isin_file),
            screener_root=Path(args.screener_root),
            out_dir=Path(args.out_dir),
            source=source,
        )
    except UpstoxError as refusal:
        _LOGGER.warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=source.redact(str(refusal))
        )
        return EXIT_REFUSED
    sys.stdout.write(run.render() + "\n")
    return run.exit_code
