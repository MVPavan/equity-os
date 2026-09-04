"""The synthetic company the Lane B sensitivity acceptance tests measure.

Shared by ``test_laneb_sensitivity`` (mutations and classification) and
``test_laneb_sensitivity_report`` (aggregates and the command), which were one
file until it outgrew the 800-line ceiling. Held here rather than duplicated so
the two halves cannot drift on what they are measuring — a fixture that differed
between them would make the aggregates a summary of a different company than the
one the classification tests pin.

**What the fixture is built to make measurable.** A sensitivity number is only
as honest as the baseline it is measured against, so the company below
deliberately carries one of each baseline the classification has to tell apart:

* ``Profit before tax`` — tier 1, agreeing, and **zero in Mar 2025**, so a sign
  flip on a zero can be recorded as ``UNDETECTED`` rather than hidden;
* ``Net Profit`` — tier 1 and already ``MISMATCH`` before any mutation, so
  ``MASKED`` is reachable;
* the three cash-flow rows — tier 3, ``NOT_COMPARABLE`` whatever the values,
  so ``BLIND_TIER3`` is reachable;
* ``Tax`` and ``Total Liabilities`` — rows the name map never names, so
  ``BLIND_UNMAPPED`` is reachable and coverage is below 1.

The last row of ``profit-loss`` and of ``balance-sheet`` is a mapped, agreeing
row on purpose: ``ROW_SWAP`` has no next row there, and P1 ranks the blind
classifications above ``NOT_APPLICABLE``, so a last row that were unmapped or
tier 3 could not show ``NOT_APPLICABLE`` at all.

**Columns run oldest-first**, which is how Screener publishes them and what the
column-addressing mutations assume. ``upstox_fixtures`` states the same two
periods newest-first for the crosscheck's own tests, so they are reversed here
rather than restated — one source for the labels, one statement of the
orientation.

The variants at the end carry the two things the first real measurement found
(amendments M1 and M2): a page column Upstox never answers for, and a response
that does not carry one of the mapped categories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tests.fundamentals.upstox_fixtures import (
    FIXTURE_STAMP,
    SCREENER_PERIODS,
    income_statement_body,
    statement_bodies,
    statement_fetch,
)

from fundamentals.api.upstox_sensitivity_cli import UPSTOX_SENSITIVITY_COMMAND
from fundamentals.ingest.screener_crosscheck import INCOME_STATEMENT_MAP
from fundamentals.ingest.upstox_crosscheck import COMPARED_SECTIONS, ScreenerSection
from fundamentals.ingest.upstox_source import DEFAULT_ROUTE_KEY, UpstoxSurface, route_for
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    StatementBasis,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
)
from fundamentals.verify.laneb_sensitivity import SensitivityReport, measure_sensitivity

# A real check digit, used as an identifier only — the guard that decides
# whether a company is looked at at all is the ISIN's, not this fixture's.
TITAN_ISIN = "INE280A01028"
SYMBOL = "TITAN"
BASIS = StatementBasis.STANDALONE

# Oldest first, as a Screener page publishes them.
PAGE_PERIODS: tuple[str, ...] = tuple(reversed(SCREENER_PERIODS))
OLDEST_PERIOD, NEWEST_PERIOD = PAGE_PERIODS

# The trailing-twelve-month column a real profit-loss page leads with and Upstox
# never answers for. It repeats the newest annual figure, so a mutation that
# targeted it instead of Mar 2026 would change nothing the comparator reads —
# which is exactly the false zero M2 records.
TTM_PERIOD = "TTM"
PAGE_PERIODS_WITH_TTM: tuple[str, ...] = (*PAGE_PERIODS, TTM_PERIOD)

# A newer annual column that only the income statement answers for. The three
# surfaces do not always reach back — or forward — equally far, so a period can
# carry a report for one mapping and MISSING_UPSTOX for another.
INCOME_ONLY_PERIOD = "Mar 2027"
PAGE_PERIODS_WITH_INCOME_ONLY: tuple[str, ...] = (*PAGE_PERIODS, INCOME_ONLY_PERIOD)

# Four annual columns, all of them answered for by the income statement: the
# page a per-cell applicability rule has to be measured on, since a two-column
# page cannot tell "scored one of two" from "scored the only one it touched".
# Extended at the new end rather than the old one, so no label collides with the
# numeric identifiers the security rail harvests from private captures.
FOUR_PERIODS: tuple[str, ...] = (*PAGE_PERIODS, INCOME_ONLY_PERIOD, "Mar 2028")

# The nine seeded defects of B-02, named rather than imported: a parametrize
# decorator runs at collection time and the enum is what these files are testing.
MUTATION_NAMES = (
    "DROP_ROW",
    "COLUMN_SHIFT",
    "SIGN_FLIP",
    "SCALE_10",
    "SCALE_100",
    "THOUSANDS_TRUNCATED",
    "ROW_SWAP",
    "UNIT_DRIFT",
    "STALE_PERIOD",
)

# The Screener side of the sensitivity fixture, oldest period first. It differs
# from the shared crosscheck fixture on purpose — see the module docstring — so
# it is stated here rather than borrowed.
SENSITIVITY_ROWS: dict[str, tuple[tuple[str, tuple[str, str]], ...]] = {
    "profit-loss": (
        ("Sales", ("142", "190")),  # tier 2, with Other Income, agrees
        ("Other Income", ("8", "10")),  # tier 2, with Sales, agrees
        ("Tax", ("8", "10")),  # named by no mapping
        ("Net Profit", ("9", "11")),  # tier 1, already MISMATCH against 22 / 30
        ("Profit before tax", ("0", "40")),  # tier 1, agrees; zero in Mar 2025
    ),
    "balance-sheet": (
        ("Total Assets", ("500", "600")),  # tier 2, agrees
        ("Total Liabilities", ("380", "440")),  # named by no mapping
        ("Borrowings", ("260", "300")),  # tier 2, with Other Liabilities
        ("Other Liabilities", ("120", "140")),  # tier 2, agrees at 380 / 440
    ),
    "cash-flow": (
        ("Cash from Operating Activity", ("40", "55")),  # tier 3
        ("Cash from Investing Activity", ("-25", "-30")),  # tier 3
        ("Cash from Financing Activity", ("-9", "-12")),  # tier 3
    ),
}

ROW_COUNT = sum(len(rows) for rows in SENSITIVITY_ROWS.values())
CELL_COUNT = ROW_COUNT * len(MUTATION_NAMES) * len(PAGE_PERIODS)

# The last row of each section, which is where ROW_SWAP runs out of a partner.
# Cash flow's last row is not here: it is tier 3, and P1 ranks BLIND_TIER3
# above NOT_APPLICABLE.
LAST_MAPPED_ROWS = ("Profit before tax", "Other Liabilities")

TIER_ONE_AGREEING_ROW = "Profit before tax"
TIER_ONE_MISMATCHING_ROW = "Net Profit"
TIER_TWO_ROW = "Sales"
TIER_TWO_PARTNER_ROW = "Other Income"
BALANCE_TIER_TWO_ROW = "Total Assets"
UNMAPPED_ROWS = ("Tax", "Total Liabilities")
TIER_THREE_ROWS = tuple(label for label, _ in SENSITIVITY_ROWS["cash-flow"])

MAPPING_BY_ROW = {
    label: mapping for mapping in INCOME_STATEMENT_MAP for label in mapping.screener_rows
}

SectionRows = dict[str, tuple[tuple[str, tuple[str, ...]], ...]]


def with_ttm_column(rows: SectionRows = SENSITIVITY_ROWS) -> SectionRows:
    """The same page with a trailing TTM column repeating each row's newest figure."""
    return {
        section: tuple((label, (*texts, texts[-1])) for label, texts in section_rows)
        for section, section_rows in rows.items()
    }


def with_newer_income_column(rows: SectionRows = SENSITIVITY_ROWS) -> SectionRows:
    """The same page with a newer column, repeating each row's newest figure.

    Paired with :func:`income_only_bodies`, which answers for that column on the
    income statement alone.
    """
    return with_ttm_column(rows)


def with_two_newer_columns(rows: SectionRows = SENSITIVITY_ROWS) -> SectionRows:
    """The same page with two further columns at the new end, repeating the newest."""
    return {
        section: tuple((label, (*texts, texts[-1], texts[-1])) for label, texts in section_rows)
        for section, section_rows in rows.items()
    }


def with_flat_row(label: str, rows: SectionRows = SENSITIVITY_ROWS) -> SectionRows:
    """The same page with one row repeating a single figure in every column.

    The page a value-coincidence looks like: shifting a flat row's columns writes
    each cell the number it already held.
    """
    return {
        section: tuple(
            (row_label, tuple([texts[0]] * len(texts)) if row_label == label else texts)
            for row_label, texts in section_rows
        )
        for section, section_rows in rows.items()
    }


def hiding_newest_cell(section: ScreenerSection, row_label: str) -> ScreenerSection:
    """The same section with one row's newest cell present but unpublished.

    A cell ``_screener_values`` skips: it is on the page, so a class that
    addresses columns still reaches it, but no comparison reads it.
    """
    row = next(candidate for candidate in section.rows if candidate.label == row_label)
    newest = max(cell.period_index for cell in row.cells)
    hidden = row.model_copy(
        update={
            "cells": tuple(
                cell.model_copy(update={"published": False})
                if cell.period_index == newest
                else cell
                for cell in row.cells
            )
        }
    )
    return section.model_copy(
        update={
            "rows": tuple(
                hidden if candidate.label == row_label else candidate for candidate in section.rows
            )
        }
    )


def without_row(label: str, rows: SectionRows = SENSITIVITY_ROWS) -> SectionRows:
    """The same page with one row missing, as a parser that lost it would render."""
    return {
        section: tuple(row for row in section_rows if row[0] != label)
        for section, section_rows in rows.items()
    }


def section_payload(
    section: str,
    *,
    rows: SectionRows | None = None,
    periods: tuple[str, ...] = PAGE_PERIODS,
) -> dict[str, Any]:
    """One ``section_*.json`` body carrying only what ``ScreenerSection`` reads.

    The narrow model ignores everything else by design — that narrowness is
    already pinned by ``test_upstox_crosscheck_cli`` — so a fixture that states
    only periods, labels and cells states exactly what this harness depends on.
    """
    table = SENSITIVITY_ROWS if rows is None else rows
    return {
        "section": section,
        "periods": [{"index": index, "label": label} for index, label in enumerate(periods)],
        "rows": [
            {
                "label": label,
                "cells": [
                    {"period_index": index, "value": text, "published": True}
                    for index, text in enumerate(texts)
                ],
            }
            for label, texts in table[section]
        ],
    }


def sections(
    *,
    rows: SectionRows | None = None,
    periods: tuple[str, ...] = PAGE_PERIODS,
) -> dict[str, ScreenerSection]:
    """The three compared sections of the synthetic company, in memory."""
    return {
        section: ScreenerSection.model_validate(
            section_payload(section, rows=rows, periods=periods)
        )
        for section in COMPARED_SECTIONS
    }


def income_over(
    periods_newest_first: tuple[str, ...],
    *,
    revenue: tuple[float, ...],
    operating_profit: tuple[float, ...],
    net_profit: tuple[float, ...],
) -> dict[str, Any]:
    """An income-statement body whose summary carries exactly these periods.

    The envelope is the verified live one; only the summary block — the block
    every mapped income line is read from — is restated, so a fixture can give
    one surface a period the others do not have without hand-building a body.
    Upstox states its histories newest-first.
    """
    body = income_statement_body(basis=BASIS.value)
    body["data"]["income_statement"] = [
        {
            "category": category,
            "history": [
                {"value": value, "period": period}
                for period, value in zip(periods_newest_first, values, strict=True)
            ],
        }
        for category, values in (
            ("revenue", revenue),
            ("operating_profit", operating_profit),
            ("net_profit", net_profit),
        )
    ]
    return body


def income_only_bodies() -> dict[UpstoxSurface, dict[str, Any]]:
    """Bodies whose income statement reaches one column further than the others."""
    return bodies(
        income=income_over(
            (INCOME_ONLY_PERIOD, NEWEST_PERIOD, OLDEST_PERIOD),
            revenue=(200.0, 200.0, 150.0),
            operating_profit=(40.0, 40.0, 0.0),
            net_profit=(30.0, 30.0, 22.0),
        )
    )


def four_period_bodies() -> dict[UpstoxSurface, dict[str, Any]]:
    """Bodies whose income statement answers for all four columns of the page."""
    return bodies(
        income=income_over(
            tuple(reversed(FOUR_PERIODS)),
            revenue=(200.0, 200.0, 200.0, 150.0),
            operating_profit=(40.0, 40.0, 40.0, 0.0),
            net_profit=(30.0, 30.0, 30.0, 22.0),
        )
    )


def bodies(
    *,
    drop_category: str | None = None,
    income: dict[str, Any] | None = None,
) -> dict[UpstoxSurface, dict[str, Any]]:
    """The Upstox side: the shared bodies, with a zero in the oldest tier-1 period.

    ``drop_category`` removes one summary series, which is how a response that
    simply does not carry a mapped line looks — the ``MISSING_UPSTOX`` baseline
    M1 requires, distinct from a period with no row at all. ``income`` replaces
    the income statement outright, for the fixtures that need it to answer for a
    different set of periods than the balance sheet and cash flow.
    """
    payloads = statement_bodies(BASIS.value)
    statement = (
        income_statement_body(basis=BASIS.value, operating_profit=(40.0, 0.0))
        if income is None
        else income
    )
    if drop_category is not None:
        statement["data"]["income_statement"] = [
            series
            for series in statement["data"]["income_statement"]
            if series["category"] != drop_category
        ]
    payloads[UpstoxSurface.INCOME_STATEMENT] = statement
    return payloads


def documents(
    payloads: dict[UpstoxSurface, dict[str, Any]] | None = None,
) -> tuple[IncomeStatementDocument, BalanceSheetDocument, CashFlowDocument]:
    """Parse the three synthetic bodies exactly as a replay run would."""
    payloads = bodies() if payloads is None else payloads
    return (
        read_income_statement(
            statement_fetch(
                payloads[UpstoxSurface.INCOME_STATEMENT], surface=UpstoxSurface.INCOME_STATEMENT
            ),
            requested_basis=BASIS,
        ),
        read_balance_sheet(
            statement_fetch(
                payloads[UpstoxSurface.BALANCE_SHEET], surface=UpstoxSurface.BALANCE_SHEET
            ),
            requested_basis=BASIS,
        ),
        read_cash_flow(
            statement_fetch(payloads[UpstoxSurface.CASH_FLOW], surface=UpstoxSurface.CASH_FLOW),
            requested_basis=BASIS,
        ),
    )


def report(
    *,
    rows: SectionRows | None = None,
    periods: tuple[str, ...] = PAGE_PERIODS,
    drop_category: str | None = None,
    payloads: dict[UpstoxSurface, dict[str, Any]] | None = None,
) -> SensitivityReport:
    """The whole sweep over the synthetic company: every row, every class.

    A plain function rather than a pytest fixture: a fixture that raised would be
    recorded as a setup error instead of as a failing behaviour.
    """
    income, balance, cash = documents(
        bodies(drop_category=drop_category) if payloads is None else payloads
    )
    return measure_sensitivity(
        isin=TITAN_ISIN,
        symbol=SYMBOL,
        basis=BASIS,
        sections=sections(rows=rows, periods=periods),
        income=income,
        balance=balance,
        cash=cash,
    )


def cells(
    measured: SensitivityReport,
    *,
    row_label: str | None = None,
    mutation: Any = None,
    period: str | None = None,
) -> list[Any]:
    """Every cell matching the stated coordinates, in report order."""
    return [
        cell
        for cell in measured.cells
        if (row_label is None or cell.row_label == row_label)
        and (mutation is None or cell.mutation is mutation)
        and (period is None or cell.period == period)
    ]


def one_cell(measured: SensitivityReport, *, row_label: str, mutation: Any, period: str) -> Any:
    """The single cell at one coordinate, refusing a harness that emits none or two."""
    found = cells(measured, row_label=row_label, mutation=mutation, period=period)
    assert len(found) == 1
    return found[0]


def screener_root(tmp_path: Path) -> Path:
    """The synthetic company on disk, in ``screener-financials``' own layout."""
    root = tmp_path / "screener"
    directory = root / SYMBOL / BASIS.value
    directory.mkdir(parents=True, exist_ok=True)
    for section in COMPARED_SECTIONS:
        (directory / f"section_{section}.json").write_text(
            json.dumps(section_payload(section)), encoding="utf-8"
        )
    return root


def upstox_root(tmp_path: Path) -> Path:
    """The retained bodies in Part A's replay layout, each beside its metadata."""
    root = tmp_path / "upstox"
    directory = root / SYMBOL / BASIS.value
    directory.mkdir(parents=True, exist_ok=True)
    for surface, body in bodies().items():
        payload = json.dumps(body).encode("utf-8")
        route = route_for(surface)
        (directory / f"{surface.value}.raw.json").write_bytes(payload)
        (directory / f"{surface.value}.meta.json").write_text(
            json.dumps(
                {
                    "source_url": f"{route.origin}{route.path_template}",
                    "content_sha256": hashlib.sha256(payload).hexdigest(),
                    "byte_count": len(payload),
                    "retrieved_at": FIXTURE_STAMP.isoformat(),
                    "route_key": DEFAULT_ROUTE_KEY,
                }
            ),
            encoding="utf-8",
        )
    return root


def cli_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    """A parsed command line for one replayed company on one basis."""
    isin_file = tmp_path / "isins.tsv"
    isin_file.write_text(f"{TITAN_ISIN}\t{SYMBOL}\n", encoding="utf-8")
    values: dict[str, object] = {
        "command": UPSTOX_SENSITIVITY_COMMAND,
        "isin_file": str(isin_file),
        "screener_root": str(screener_root(tmp_path)),
        "upstox_root": str(upstox_root(tmp_path)),
        "basis": BASIS.value,
        "out": str(tmp_path / "out"),
    }
    values.update(overrides)
    return argparse.Namespace(**values)
