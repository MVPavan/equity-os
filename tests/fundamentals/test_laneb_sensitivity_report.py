"""Lane B step 5(b): the aggregates the measurement is read through, and the command.

The second half of the Part B acceptance tests (B-05, B-06 of
``scratchpad/laneb-5b/plan.md``, plus P3, P5 and P6). The mutations and the
per-cell classification are in ``test_laneb_sensitivity``; the company both
halves measure is built in ``laneb_sensitivity_fixtures``. Split from that file
when it outgrew the 800-line ceiling; the assertions moved verbatim.

**Names this half pins**: ``SensitivityReport`` with ``cells`` / ``by_mutation``
/ ``by_tier`` / ``by_section`` / ``sensitivity`` / ``coverage_by_section``; each
aggregate's ``detected``, ``undetected``, ``masked``, ``blind_tier3``,
``blind_unmapped``, ``blind_no_upstox``, ``not_applicable`` and ``sensitivity``;
and on the CLI ``UPSTOX_SENSITIVITY_COMMAND``, ``REPORT_FILENAME``,
``add_upstox_sensitivity_parser`` and ``dispatch_upstox_sensitivity_command``.

No test here opens a socket, and the harness is required not to open one either.
"""

from __future__ import annotations

import argparse
import json
import socket
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tests.fundamentals.laneb_sensitivity_fixtures import (
    BASIS,
    SYMBOL,
    cells,
    cli_args,
    report,
)

from fundamentals.api.upstox_sensitivity_cli import (
    REPORT_FILENAME,
    UPSTOX_SENSITIVITY_COMMAND,
    add_upstox_sensitivity_parser,
    dispatch_upstox_sensitivity_command,
)
from fundamentals.ingest.upstox_crosscheck import COMPARED_SECTIONS
from fundamentals.verify.laneb_sensitivity import (
    Classification,
    MutationClass,
    SensitivityReport,
)

TSV_HEADER = "mutation\ttier\tdetected\tundetected\tmasked\tblind\tnot_applicable\tsensitivity"


def _classifications(counted: list[Any]) -> Counter[Any]:
    return Counter(cell.classification for cell in counted)


def _assert_counts(counts: Any, expected: Counter[Any]) -> None:
    """An aggregate must be the tally of the cells it claims to summarise."""
    assert counts.detected == expected[Classification.DETECTED]
    assert counts.undetected == expected[Classification.UNDETECTED]
    assert counts.masked == expected[Classification.MASKED]
    assert counts.blind_tier3 == expected[Classification.BLIND_TIER3]
    assert counts.blind_unmapped == expected[Classification.BLIND_UNMAPPED]
    assert counts.blind_no_upstox == expected[Classification.BLIND_NO_UPSTOX]
    assert counts.not_applicable == expected[Classification.NOT_APPLICABLE]


def test_the_aggregates_are_recomputable_from_the_cells() -> None:
    # B-05
    """Every aggregate is a tally of the per-cell records and of nothing else.

    An aggregate computed on a second pass over the data can disagree with the
    cells it sits beside, and a reader has no way to tell which half is wrong.
    """
    measured = report()
    assert set(measured.by_mutation) == set(MutationClass)
    for mutation, counts in measured.by_mutation.items():
        _assert_counts(counts, _classifications(cells(measured, mutation=mutation)))

    tiers = {cell.tier for cell in measured.cells if cell.tier is not None}
    assert set(measured.by_tier) == tiers  # P3: an unmapped cell has no tier to be counted under
    for tier, counts in measured.by_tier.items():
        _assert_counts(
            counts, _classifications([cell for cell in measured.cells if cell.tier is tier])
        )

    assert set(measured.by_section) == set(COMPARED_SECTIONS)
    for section, counts in measured.by_section.items():
        _assert_counts(
            counts, _classifications([cell for cell in measured.cells if cell.section == section])
        )


def test_sensitivity_excludes_masked_and_blind_cells_from_its_denominator() -> None:
    # B-05
    """Only cells that could have been noticed are scored.

    A denominator that swept in the masked and blind cells would read as a
    catastrophically insensitive comparator while measuring mostly coverage,
    and the two are different findings with different remedies. P5 keeps the
    ratio an exact, unquantized Decimal.
    """
    measured = report()
    tally = _classifications(list(measured.cells))
    detected = tally[Classification.DETECTED]
    undetected = tally[Classification.UNDETECTED]
    assert detected > 0 and undetected > 0  # the fixture must exercise both sides
    assert detected + undetected < len(measured.cells)  # and must leave masked/blind out

    assert measured.sensitivity == Decimal(detected) / Decimal(detected + undetected)
    assert measured.sensitivity != Decimal(detected) / Decimal(len(measured.cells))

    for mutation, counts in measured.by_mutation.items():
        scored = counts.detected + counts.undetected
        expected = None if scored == 0 else Decimal(counts.detected) / Decimal(scored)
        assert counts.sensitivity == expected, mutation


def test_a_class_that_moved_every_column_it_could_scores_a_full_sensitivity() -> None:
    # B-05, M4
    """``STALE_PERIOD`` reaches one column per row, and is caught on every one of them.

    The aggregate is where M4 shows up as a number: while the untouched columns
    were charged as ``UNDETECTED`` this class read as the least sensitive one in
    the sweep, which is a statement about the harness rather than about Lane B.
    """
    counts = report().by_mutation[MutationClass.STALE_PERIOD]

    assert counts.undetected == 0
    assert counts.detected > 0
    assert counts.sensitivity == Decimal(1)
    assert counts.not_applicable > 0  # the columns it never moved, reported as such


def test_the_aggregates_cannot_be_edited_by_a_reader() -> None:
    # B-05
    """A report is evidence; a reader that could edit its tallies is not reading one."""
    measured = report()

    with pytest.raises(TypeError):
        measured.by_section["profit-loss"] = measured.by_section["balance-sheet"]  # type: ignore[index]
    with pytest.raises(TypeError):
        measured.coverage_by_section["cash-flow"] = Decimal(0)  # type: ignore[index]


def test_coverage_per_section_is_mapped_rows_over_all_rows() -> None:
    # B-05
    """Coverage says how much of each section Lane B reads at all."""
    assert report().coverage_by_section == {
        "profit-loss": Decimal(4) / Decimal(5),
        "balance-sheet": Decimal(3) / Decimal(4),
        "cash-flow": Decimal(1),
    }


def test_the_command_and_its_flags_are_declared() -> None:
    # B-06
    """The measurement is invoked by name, from files, with no live inputs."""
    assert UPSTOX_SENSITIVITY_COMMAND == "upstox-crosscheck-sensitivity"
    assert REPORT_FILENAME == "laneb_sensitivity_report.json"

    parser = argparse.ArgumentParser()
    add_upstox_sensitivity_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(
        [
            UPSTOX_SENSITIVITY_COMMAND,
            "--isin-file",
            "isins.tsv",
            "--screener-root",
            "screener",
            "--upstox-root",
            "upstox",
            "--basis",
            "standalone",
            "--out",
            "out",
        ]
    )
    assert args.command == UPSTOX_SENSITIVITY_COMMAND
    assert (args.isin_file, args.screener_root, args.upstox_root, args.basis, args.out) == (
        "isins.tsv",
        "screener",
        "upstox",
        "standalone",
        "out",
    )


def test_the_cli_writes_the_report_prints_the_tsv_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # B-06
    """It is a measurement, not a gate: a blind comparator still exits zero.

    The exit code has to stay uninformative here for the same reason Lane B's
    does — a number nobody has measured yet cannot be a threshold.
    """
    args = cli_args(tmp_path)

    assert dispatch_upstox_sensitivity_command(args) == 0

    assert capsys.readouterr().out.splitlines()[0] == TSV_HEADER
    written = (tmp_path / "out" / REPORT_FILENAME).read_text(encoding="utf-8")
    payload = json.loads(written)
    assert isinstance(payload, dict)
    assert SYMBOL in written
    assert Classification.BLIND_UNMAPPED.value in written
    assert MutationClass.UNIT_DRIFT.value in written


def test_the_cli_opens_no_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # B-06
    """Zero requests, ever. The harness replays retained bytes and nothing else."""
    args = cli_args(tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the sensitivity harness opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)

    assert dispatch_upstox_sensitivity_command(args) == 0


def test_the_cli_exits_three_when_the_screener_root_cannot_be_read(tmp_path: Path) -> None:
    # B-06
    """Unreadable inputs are a refusal, not a measurement of zero sensitivity.

    A run that quietly reported nothing would be indistinguishable from a run
    that found nothing, which is the same failure mode the sweep exists to
    close. P6 names both cases: a root that is not there and a section that
    cannot be parsed.
    """
    assert (
        dispatch_upstox_sensitivity_command(
            cli_args(tmp_path, screener_root=str(tmp_path / "nowhere"))
        )
        == 3
    )

    args = cli_args(tmp_path)
    section = Path(str(args.screener_root)) / SYMBOL / BASIS.value / "section_profit-loss.json"
    section.write_text("{not json at all", encoding="utf-8")
    assert dispatch_upstox_sensitivity_command(args) == 3


def test_a_company_the_screener_root_does_not_hold_is_skipped_and_the_run_continues(
    tmp_path: Path,
) -> None:
    # B-06
    """P6's other half: a missing company is a gap in coverage, not a bad input.

    Without this, a harness that answered 3 to every imperfection would pass
    the refusal test above while refusing to measure anything at all.
    """
    empty_root = tmp_path / "empty-screener"
    empty_root.mkdir()

    assert (
        dispatch_upstox_sensitivity_command(cli_args(tmp_path, screener_root=str(empty_root))) == 0
    )

    assert (tmp_path / "out" / REPORT_FILENAME).is_file()


def test_the_report_is_the_only_place_a_reader_needs_to_look() -> None:
    # B-05
    """A serialized report carries its own aggregates, not just its cells.

    The measurement doc is written from the JSON artifact, so anything a reader
    needs must survive ``model_dump_json`` — a ratio recomputed by hand from a
    round-tripped report is a second implementation nobody checks.
    """
    measured = report()

    restored = SensitivityReport.model_validate_json(measured.model_dump_json())

    assert restored.sensitivity == measured.sensitivity
    assert restored.coverage_by_section == measured.coverage_by_section
    assert restored.period_coverage_by_section == measured.period_coverage_by_section
    assert restored.by_tier == measured.by_tier
