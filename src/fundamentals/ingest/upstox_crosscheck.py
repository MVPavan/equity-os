"""The pure half of Lane B's differential check: compare one company, decide nothing.

Nothing here reads a file, opens a socket or asks for a credential. Given the
Screener sections a company published and the three Upstox statement documents
read from its responses, :func:`compare_company` returns what disagreed — and
that is the whole of the comparison ``upstox-crosscheck`` performs. The command
around it keeps argument parsing, the pre-call guards, retention, replay and
rendering.

The seam exists so the same comparison can be re-run on inputs no fetch
produced. A sweep whose bodies were retained can be replayed offline, and a
harness can mutate one Screener row and ask whether this comparison would have
noticed — a question the command's I/O made unaskable when the comparison lived
inside it.

**Nothing this module produces is a fact.** Upstox and Screener share upstream
lineage, so a disagreement is a triage direction, never a diagnosis, and no
outcome here may reach the fact store or the reconciler.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from fundamentals.ingest.screener_crosscheck import (
    INCOME_STATEMENT_MAP,
    CrosscheckOutcome,
    CrosscheckReport,
    CrosscheckRow,
    LineMapping,
    StatedValue,
    compare_line,
)
from fundamentals.ingest.upstox_source import AcquisitionOutcome
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    StatementBasis,
)

COMPARED_SECTIONS: tuple[str, ...] = ("profit-loss", "balance-sheet", "cash-flow")

EXIT_OK = 0
EXIT_UNREADABLE = 3

SUMMARY_HEADER = (
    "isin\tsymbol\tbasis\tstatus\tagree\tmismatch\tanomaly\tnot_comparable\tunmet_tier3"
)

AMBIGUOUS_ROW_MESSAGE = (
    "screener row {label!r} appears in both {first} and {second}; refusing to guess"
)


class AmbiguousScreenerRowError(ValueError):
    """One row label is carried by two compared sections.

    Which section a value came from would then depend on file order, and the
    comparison keys on the label alone. Raised here rather than only at the
    command's loader so every caller of :func:`compare_company` — a replay, a
    harness feeding sections it built itself — inherits the same refusal.
    """


class ScreenerCell(BaseModel):
    """One Screener cell, narrowed to what a comparison needs from it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    period_index: int = Field(ge=0)
    value: Decimal | None
    published: bool


class ScreenerRow(BaseModel):
    """One Screener row, narrowed to its label and its cells."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    label: str = Field(min_length=1)
    cells: tuple[ScreenerCell, ...] = ()


class ScreenerPeriod(BaseModel):
    """One Screener column, narrowed to the index and label a value is addressed by."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    index: int = Field(ge=0)
    label: str = Field(min_length=1)


class ScreenerSection(BaseModel):
    """The part of a ``section_*.json`` artifact Lane B actually reads.

    Deliberately narrower than :class:`SectionTable`. Validating the whole
    artifact coupled the comparator to ``schedules``, ``growth_tables`` and
    ``quarantined`` — blocks no comparison touches — so a change in any of them
    made a log-only lane refuse rows it could read perfectly well. What is read
    stays strict; what is not read is not a dependency.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    periods: tuple[ScreenerPeriod, ...] = ()
    rows: tuple[ScreenerRow, ...] = ()


class CompanyStatus(StrEnum):
    """What happened to one company on one basis."""

    COMPARED = "COMPARED"
    SKIPPED_INVALID_ISIN = "SKIPPED_INVALID_ISIN"
    SKIPPED_NO_SCREENER_DATA = "SKIPPED_NO_SCREENER_DATA"
    SKIPPED_NO_UPSTOX_DATA = "SKIPPED_NO_UPSTOX_DATA"
    UPSTOX_UNREADABLE = "UPSTOX_UNREADABLE"


class CompanyCrosscheck(BaseModel):
    """One company on one basis: what was compared, or why nothing was."""

    model_config = ConfigDict(frozen=True)

    isin: str
    symbol: str
    basis: str
    status: CompanyStatus
    detail: str | None = None
    # What the Upstox responses said about themselves. Chiefly the parse-time
    # finding that a summary category contradicts the ``full_statement``
    # particular it is identical to, inside one HTTP response. Carried here
    # because the two halves are only a diagnosis together: an internal
    # contradiction and a Screener disagreement on the same line and period
    # place the fault on Upstox and exonerate our Screener parse. Recorded even
    # for lines this run did not compare — the note is about the response.
    upstox_anomalies: tuple[str, ...] = ()
    reports: tuple[CrosscheckReport, ...] = ()


class CrosscheckRunReport(BaseModel):
    """Every company one invocation looked at. Carries no fact or provenance type."""

    model_config = ConfigDict(frozen=True)

    companies: tuple[CompanyCrosscheck, ...] = ()
    # Which run this was. A replay reads bodies retained by an earlier run and
    # retains nothing itself, so exactly one of these is set and a reader can
    # tell the two apart without re-deriving it from the counts.
    upstox_root: str | None = None
    retained_under: str | None = None

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
            if _is_unmet_tier3(row)
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
                    if _is_unmet_tier3(row):
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


def _is_unmet_tier3(row: CrosscheckRow) -> bool:
    """Whether a tier-3 line's two values differ beyond the tolerance derived for them."""
    return (
        row.outcome is CrosscheckOutcome.NOT_COMPARABLE
        and row.difference is not None
        and row.tolerance is not None
        and row.difference > row.tolerance
    )


def compare_company(
    *,
    isin: str,
    symbol: str,
    basis: StatementBasis,
    sections: Mapping[str, ScreenerSection],
    income: IncomeStatementDocument,
    balance: BalanceSheetDocument,
    cash: CashFlowDocument,
) -> CompanyCrosscheck:
    """Compare one company's Upstox documents against its Screener sections.

    A document this repo could not read ends the comparison for that company:
    there is no value to disagree with, and reporting the readable two thirds as
    agreement would understate what happened.
    """
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

    anomalies = tuple(
        f"{document.surface.value}: {note}"
        for document in (income, balance, cash)
        for note in document.anomalies
    )
    screener = _screener_values(sections)
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
        upstox_anomalies=anomalies,
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


def _screener_values(
    sections: Mapping[str, ScreenerSection],
) -> dict[str, dict[str, StatedValue]]:
    """Index one company's sections by row label, then by period label.

    Sections are read in :data:`COMPARED_SECTIONS` order rather than the
    mapping's, so the index does not depend on how the caller assembled it.
    """
    by_label: dict[str, dict[str, StatedValue]] = {}
    origin: dict[str, str] = {}
    for section in COMPARED_SECTIONS:
        table = sections.get(section)
        if table is None:
            continue
        labels = {period.index: period.label for period in table.periods}
        for row in table.rows:
            if origin.setdefault(row.label, section) != section:
                raise AmbiguousScreenerRowError(
                    AMBIGUOUS_ROW_MESSAGE.format(
                        label=row.label, first=origin[row.label], second=section
                    )
                )
            slot = by_label.setdefault(row.label, {})
            for cell in row.cells:
                label = labels.get(cell.period_index)
                if label is None or cell.value is None or not cell.published:
                    continue
                slot[label] = _stated(cell.value, row.label)
    return by_label


def _stated(amount: Decimal, raw_label: str) -> StatedValue:
    """Wrap one number with the precision the source stated it to."""
    exponent = amount.as_tuple().exponent
    decimals = -exponent if isinstance(exponent, int) else 0
    return StatedValue(amount=amount, decimals=max(decimals, 0), raw_label=raw_label)
