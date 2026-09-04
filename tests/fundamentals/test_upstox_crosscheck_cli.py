"""The ``upstox-crosscheck`` command: log-only, and never asks about an ISIN blind.

An unknown ISIN returns `{"status":"success","data":[]}` with HTTP 200 —
indistinguishable from a real company with nothing to report. The command's only
defence is refusing to make the call, so the guards that decide *whether to ask*
carry as many tests here as the comparison itself.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from tests.fundamentals.upstox_fixtures import (
    balance_sheet_body,
    cash_flow_body,
    income_statement_body,
    statement_fetch,
)

from fundamentals.api.upstox_crosscheck_cli import (
    REPORT_FILENAME,
    UPSTOX_CROSSCHECK_COMMAND,
    CompanyStatus,
    add_upstox_crosscheck_parser,
    is_valid_isin,
    read_isin_file,
    run_upstox_crosscheck_command,
)
from fundamentals.ingest.screener_crosscheck import CrosscheckOutcome
from fundamentals.ingest.upstox_source import UpstoxFetch, UpstoxRoute, UpstoxSurface

# Real check digits: TITAN and NETWEB, both listed. Used as identifiers only.
TITAN_ISIN = "INE280A01028"
NETWEB_ISIN = "INE0NT901020"


class StubSource:
    """A transport that answers from a body table and records what was asked."""

    def __init__(self, bodies: Mapping[UpstoxSurface, dict[str, Any]]) -> None:
        self.bodies = bodies
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        self.calls.append((route.surface.value, query))
        return statement_fetch(self.bodies[route.surface], surface=route.surface)

    def redact(self, text: str) -> str:
        return text


def _bodies(basis: str = "standalone") -> dict[UpstoxSurface, dict[str, Any]]:
    return {
        UpstoxSurface.INCOME_STATEMENT: income_statement_body(basis=basis),
        UpstoxSurface.BALANCE_SHEET: balance_sheet_body(basis=basis),
        UpstoxSurface.CASH_FLOW: cash_flow_body(basis=basis),
    }


def _screener_root(tmp_path: Path, symbol: str, basis: str = "standalone") -> Path:
    """A Screener financials tree holding the three sections the map reads."""
    root = tmp_path / "screener"
    directory = root / symbol / basis
    directory.mkdir(parents=True)
    _write_section(
        directory,
        "profit-loss",
        [
            ("Sales", ["190", "142"]),
            ("Other Income", ["10", "8"]),
            ("Profit before tax", ["40", "30"]),
            ("Net Profit", ["30", "22"]),
        ],
    )
    _write_section(
        directory,
        "balance-sheet",
        [("Total Assets", ["600", "500"]), ("Total Liabilities", ["440", "380"])],
    )
    _write_section(
        directory,
        "cash-flow",
        [
            ("Cash from Operating Activity", ["55", "40"]),
            ("Cash from Investing Activity", ["-30", "-25"]),
            ("Cash from Financing Activity", ["-12", "-9"]),
        ],
    )
    return root


def _write_section(directory: Path, section: str, rows: list[tuple[str, list[str]]]) -> None:
    periods = ["Mar 2026", "Mar 2025"]
    payload = {
        "section": section,
        "table_id": f"{section}-table",
        "outcome": "ok",
        "unit_statement": "Consolidated Figures in Rs. Crores",
        "periods": [
            {"index": index, "label": label, "kind": "date"} for index, label in enumerate(periods)
        ],
        "rows": [
            {
                "position": position,
                "label": label,
                "status": "modeled",
                "unit": "rs_crore",
                "cells": [
                    {
                        "period_index": index,
                        "value": text,
                        "raw_text": text,
                        "published": True,
                        "provenance": {
                            "source_id": "screener",
                            "file_sha256": "0" * 64,
                            "anchor_type": "HTML_TABLE",
                            "table_id": f"{section}-table",
                            "row_path": label,
                            "column_index": index,
                            "column_label": periods[index],
                            "retrieved_at": "2026-09-04T06:30:00Z",
                        },
                    }
                    for index, text in enumerate(texts)
                ],
            }
            for position, (label, texts) in enumerate(rows)
        ],
    }
    (directory / f"section_{section}.json").write_text(json.dumps(payload), encoding="utf-8")


def _args(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"basis": "standalone"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestIsinValidation:
    """Finding 1's only real mitigation: never ask about an ISIN we cannot vouch for."""

    @pytest.mark.parametrize("isin", [TITAN_ISIN, NETWEB_ISIN, "INE999Z01012"])
    def test_a_correct_check_digit_passes(self, isin: str) -> None:
        assert is_valid_isin(isin) is True

    @pytest.mark.parametrize(
        "isin",
        [
            "INE280A01029",  # last digit changed
            "INE000X00000",  # the live invalid-ISIN probe
            "INE280A0102",  # too short
            "INE280A010288",  # too long
            "in280a01028",  # lowercase
            "XX280A01028INE",  # not an ISIN at all
            "",
        ],
    )
    def test_anything_else_is_refused(self, isin: str) -> None:
        assert is_valid_isin(isin) is False


class TestIsinFile:
    def test_a_two_column_file_is_read_as_isin_and_symbol(self, tmp_path: Path) -> None:
        path = tmp_path / "isins.tsv"
        path.write_text(
            f"# a comment\n\n{TITAN_ISIN}\tTITAN\n{NETWEB_ISIN}\tNETWEB\n", encoding="utf-8"
        )
        assert read_isin_file(path) == ((TITAN_ISIN, "TITAN"), (NETWEB_ISIN, "NETWEB"))

    def test_a_line_that_is_not_two_columns_is_refused_with_its_number(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "isins.tsv"
        path.write_text(f"{TITAN_ISIN}\tTITAN\nJUSTONECOLUMN\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="line 2"):
            read_isin_file(path)

    def test_a_repeated_isin_is_refused_rather_than_compared_twice(self, tmp_path: Path) -> None:
        path = tmp_path / "isins.tsv"
        path.write_text(f"{TITAN_ISIN}\tTITAN\n{TITAN_ISIN}\tTITAN2\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="repeated"):
            read_isin_file(path)


class TestRun:
    def test_a_clean_run_compares_every_mapped_line_and_exits_zero(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        source = StubSource(_bodies())
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=source,
        )
        assert result.exit_code == 0
        company = result.companies[0]
        assert company.status is CompanyStatus.COMPARED
        outcomes = {row.outcome for report in company.reports for row in report.rows}
        assert CrosscheckOutcome.AGREE in outcomes
        assert CrosscheckOutcome.NOT_COMPARABLE in outcomes

    def test_a_mismatch_does_not_change_the_exit_code(self, tmp_path: Path) -> None:
        """Decision A is log-only. This is the guard that keeps it that way."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        bodies = _bodies()
        bodies[UpstoxSurface.INCOME_STATEMENT] = income_statement_body(net_profit=(999.0, 22.0))
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(bodies),
        )
        assert result.mismatch_count > 0
        assert result.exit_code == 0

    def test_an_invalid_isin_is_never_requested(self, tmp_path: Path) -> None:
        """The empty 200 an unknown ISIN returns cannot be told from a real one."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text("INE000X00000\tGHOST\n", encoding="utf-8")
        source = StubSource(_bodies())
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "GHOST"),
            out_dir=tmp_path / "out",
            source=source,
        )
        assert source.calls == []
        assert result.companies[0].status is CompanyStatus.SKIPPED_INVALID_ISIN
        assert result.exit_code == 0

    def test_a_company_with_no_screener_data_is_never_requested(self, tmp_path: Path) -> None:
        """Nothing to compare against, and asking would spend a rate-limited call."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        source = StubSource(_bodies())
        empty_root = tmp_path / "screener"
        empty_root.mkdir()
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=empty_root,
            out_dir=tmp_path / "out",
            source=source,
        )
        assert source.calls == []
        assert result.companies[0].status is CompanyStatus.SKIPPED_NO_SCREENER_DATA

    def test_a_drifted_block_lane_b_never_reads_does_not_stop_the_comparison(
        self, tmp_path: Path
    ) -> None:
        """Lane B reads periods, row labels and cell values. Nothing else.

        Validating the whole `SectionTable` coupled the comparator to parts of
        the Screener artifact it ignores — `schedules`, `growth_tables`,
        `quarantined`. A retained capture written before those sub-models grew a
        required field then made the crosscheck refuse to read the rows it does
        need, which is the wrong failure for a log-only lane.
        """
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        root = _screener_root(tmp_path, "TITAN")
        path = root / "TITAN" / "standalone" / "section_profit-loss.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["schedules"] = [{"nothing": "this model has never declared"}]
        payload["growth_tables"] = [{"also": "unreadable"}]
        path.write_text(json.dumps(payload), encoding="utf-8")

        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=root,
            out_dir=tmp_path / "out",
            source=StubSource(_bodies()),
        )
        assert result.companies[0].status is CompanyStatus.COMPARED
        outcomes = {
            row.outcome
            for report in result.companies[0].reports
            for row in report.rows
            if row.upstox_category == "net_profit"
        }
        assert outcomes == {CrosscheckOutcome.AGREE}

    def test_a_row_that_lane_b_reads_but_cannot_type_is_refused(self, tmp_path: Path) -> None:
        """Narrow does not mean lenient: the fields it does read stay strict."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        root = _screener_root(tmp_path, "TITAN")
        path = root / "TITAN" / "standalone" / "section_profit-loss.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["rows"][0]["label"]
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SystemExit, match="section_profit-loss.json"):
            run_upstox_crosscheck_command(
                _args(),
                isin_file=isin_file,
                screener_root=root,
                out_dir=tmp_path / "out",
                source=StubSource(_bodies()),
            )

    def test_an_unreadable_upstox_response_makes_the_run_exit_non_zero(
        self, tmp_path: Path
    ) -> None:
        """A parse failure is not a mismatch, and only parse failures fail the run."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        bodies = _bodies()
        bodies[UpstoxSurface.BALANCE_SHEET] = {"status": "error", "data": {}}
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(bodies),
        )
        assert result.companies[0].status is CompanyStatus.UPSTOX_UNREADABLE
        assert result.exit_code != 0

    def test_the_requested_basis_reaches_the_query_of_every_surface(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        source = StubSource(_bodies("consolidated"))
        run_upstox_crosscheck_command(
            _args(basis="consolidated"),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN", "consolidated"),
            out_dir=tmp_path / "out",
            source=source,
        )
        assert len(source.calls) == 3
        assert all(
            query is not None and query["type"] == "consolidated" for _, query in source.calls
        )

    def test_both_bases_run_each_basis_separately(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        root = _screener_root(tmp_path, "TITAN")
        _screener_root(tmp_path, "TITAN", "consolidated")

        class BasisAwareSource(StubSource):
            def fetch(
                self,
                route: UpstoxRoute,
                query: Mapping[str, str] | None = None,
                **params: str,
            ) -> UpstoxFetch:
                self.calls.append((route.surface.value, query))
                basis = (query or {}).get("type", "standalone")
                return statement_fetch(_bodies(basis)[route.surface], surface=route.surface)

        result = run_upstox_crosscheck_command(
            _args(basis="both"),
            isin_file=isin_file,
            screener_root=root,
            out_dir=tmp_path / "out",
            source=BasisAwareSource({}),
        )
        assert {company.basis for company in result.companies} == {
            "standalone",
            "consolidated",
        }

    def test_the_report_is_written_once_and_never_clobbered(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        out_dir = tmp_path / "out"
        run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=out_dir,
            source=StubSource(_bodies()),
        )
        report = json.loads((out_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
        assert report["companies"][0]["symbol"] == "TITAN"
        with pytest.raises(SystemExit, match="refusing to overwrite"):
            run_upstox_crosscheck_command(
                _args(),
                isin_file=isin_file,
                screener_root=_screener_root(tmp_path, "TITAN2"),
                out_dir=out_dir,
                source=StubSource(_bodies()),
            )

    def test_the_report_carries_no_fact_or_provenance_type(self, tmp_path: Path) -> None:
        """Lane B is barred from reconciliation, and the artifact is the boundary."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        out_dir = tmp_path / "out"
        run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=out_dir,
            source=StubSource(_bodies()),
        )
        text = (out_dir / REPORT_FILENAME).read_text(encoding="utf-8")
        for forbidden in ("provenance", "anchor_type", "source_record", "observation"):
            assert forbidden not in text


class TestParser:
    def test_the_command_is_registered_with_its_four_flags(self) -> None:
        parser = argparse.ArgumentParser()
        add_upstox_crosscheck_parser(parser.add_subparsers(dest="command"))
        args = parser.parse_args(
            [
                UPSTOX_CROSSCHECK_COMMAND,
                "--isin-file",
                "isins.tsv",
                "--screener-root",
                "screener",
                "--out-dir",
                "out",
                "--basis",
                "both",
            ]
        )
        assert args.command == UPSTOX_CROSSCHECK_COMMAND
        assert args.basis == "both"


class TestTierThreeVisibility:
    """A tier-3 line can be the largest disagreement in a run and claim nothing."""

    def test_a_tier_three_difference_is_counted_without_being_named_a_mismatch(
        self, tmp_path: Path
    ) -> None:
        """NETWEB Mar-2026 operating cash flow: Upstox 789.92, Screener 171."""
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        bodies = _bodies()
        cash = bodies[UpstoxSurface.CASH_FLOW]
        cash["data"]["cash_flow"][0]["history"][0]["value"] = 789.92
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(bodies),
        )
        assert result.unmet_tier3_count == 1
        assert result.mismatch_count == 0
        assert result.anomaly_count == 0
        assert result.exit_code == 0
        assert "unmet_tier3" in result.render()

    def test_a_tier_three_line_that_agrees_is_not_counted(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(_bodies()),
        )
        assert result.unmet_tier3_count == 0


class TestUpstoxSelfContradictionReachesTheReport:
    """The convergence rule needs both halves in one artifact to be usable.

    When Upstox's summary block contradicts its own `full_statement` on the same
    line and period, and the Screener comparison also disagrees there, the fault
    is Upstox-side and our Screener parse is exonerated. That rule was earned on
    live data and was unusable from the report, which recorded only the second
    half.
    """

    def test_a_parse_anomaly_is_carried_into_the_company_record(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        bodies = _bodies()
        for row in bodies[UpstoxSurface.INCOME_STATEMENT]["data"]["full_statement"]:
            if row["particular"] == "Profit After Tax":
                row["history"][0]["value"] = 31.5
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(bodies),
        )
        company = result.companies[0]
        assert company.status is CompanyStatus.COMPARED
        assert any(
            "net_profit" in note and "Profit After Tax" in note for note in company.upstox_anomalies
        )

    def test_a_clean_company_carries_none(self, tmp_path: Path) -> None:
        isin_file = tmp_path / "isins.tsv"
        isin_file.write_text(f"{TITAN_ISIN}\tTITAN\n", encoding="utf-8")
        result = run_upstox_crosscheck_command(
            _args(),
            isin_file=isin_file,
            screener_root=_screener_root(tmp_path, "TITAN"),
            out_dir=tmp_path / "out",
            source=StubSource(_bodies()),
        )
        assert result.companies[0].upstox_anomalies == ()
