"""Lane B step 5(c) at the command: the triage file, the ``warn`` column, the exit.

Acceptance tests T15 and T16 of ``scratchpad/laneb-5c/plan.md``, covering C-07
and the command changes the plan lists for
``fundamentals.api.upstox_crosscheck_cli``. The per-row rules themselves are in
``test_laneb_triage``.

Both tests drive the command **offline**, through the retention-and-replay seam
the earlier steps built: one stub-transport run retains synthetic bodies, and the
assertions are made against a replay of that tree, which reaches no surface and
never asks for a credential.

Every value is synthetic. The counts asserted here are the fixture's, not the
live sweep's; the sweep's own figures are cited in prose only.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

import pytest
from tests.fundamentals.upstox_fixtures import (
    DUAL_ISIN,
    NSE_ISIN,
    NSE_SYMBOL,
    SCREENER_SECTION_ROWS,
    StubSource,
    screener_section_payload,
    statement_bodies,
)

from fundamentals.api.cli import _configure_logging
from fundamentals.api.upstox_crosscheck_cli import (
    EXIT_UNREADABLE,
    REPORT_FILENAME,
    RETENTION_DIRNAME,
    SUMMARY_HEADER,
    UPSTOX_CROSSCHECK_COMMAND,
    add_upstox_crosscheck_parser,
    dispatch_upstox_crosscheck_command,
    run_upstox_crosscheck_command,
)
from fundamentals.ingest.upstox_source import UpstoxSurface
from fundamentals.ingest.upstox_statements import StatementBasis

BASIS = StatementBasis.STANDALONE
OTHER_ISIN = DUAL_ISIN
OTHER_SYMBOL = "OTHERCO"

WARN_RATIO = "0.20"
REVIEW_OWNER = "test-owner"
CONFIG_FILENAME = "laneb_triage.yaml"

# What C-07 fixes: eleven columns, so a reviewer can sort the queue by class and
# still see both stated amounts and the measure the class was decided on.
EXPECTED_WARNINGS_HEADER = (
    "isin\tsymbol\tbasis\tperiod\tupstox_category\ttier\toutcome\tupstox_amount\t"
    "screener_amount\trelative_difference\ttriage"
)

# The columns this test pins by position: everything except the two stated
# amounts, whose rendering C-07 does not fix for a missing side.
PINNED_COLUMNS = (0, 1, 2, 3, 4, 5, 6, 9, 10)

# A body no reader can interpret: the envelope itself is wrong, so the company
# comes back UPSTOX_UNREADABLE and the run's own exit code is already non-zero.
UNREADABLE_BODY: dict[str, Any] = {"status": "error", "data": {}}


def _triage() -> ModuleType:
    """Import the module under test at call time, not at collection time."""
    from fundamentals.verify import laneb_triage

    return laneb_triage


def _refusing_credentials() -> NoReturn:
    """A credentials factory that fails the test if a replay ever calls it."""
    raise AssertionError("replay asked for upstox credentials")


def _config_file(tmp_path: Path) -> Path:
    """A triage config with the approved bar and no acknowledgements.

    The command's default path is asserted separately (T19); a test that read it
    would depend on the shipped file's contents to decide a fixture's counts.
    """
    path = tmp_path / CONFIG_FILENAME
    path.write_text(
        f"magnitude_warn_ratio: '{WARN_RATIO}'\nreview_owner: {REVIEW_OWNER}\nacknowledged: []\n",
        encoding="utf-8",
    )
    return path


def _isin_file(tmp_path: Path, name: str, pairs: tuple[tuple[str, str], ...]) -> Path:
    path = tmp_path / f"{name}.tsv"
    path.write_text("".join(f"{isin}\t{symbol}\n" for isin, symbol in pairs), encoding="utf-8")
    return path


def _screener_root(
    tmp_path: Path,
    *symbols: str,
    mutate: Callable[[str, dict[str, Any]], None] | None = None,
) -> Path:
    """A Screener tree for each symbol, optionally with one row rewritten.

    Built here rather than taken from ``screener_root`` because both tests need a
    section that disagrees with the Upstox side in a stated way.
    """
    root = tmp_path / "screener"
    for symbol in symbols:
        directory = root / symbol / BASIS.value
        directory.mkdir(parents=True, exist_ok=True)
        for section in SCREENER_SECTION_ROWS:
            payload = screener_section_payload(section)
            if mutate is not None:
                mutate(section, payload)
            (directory / f"section_{section}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
    return root


def _profit_before_tax_restated(section: str, payload: dict[str, Any]) -> None:
    """Restate one tier-1 Screener cell far enough to clear the 20% bar."""
    if section != "profit-loss":
        return
    for row in payload["rows"]:
        if row["label"] == "Profit before tax":
            row["cells"][0]["value"] = "28"
            row["cells"][0]["raw_text"] = "28"


def _liabilities_published(section: str, payload: dict[str, Any]) -> None:
    """Publish the two rows the ``total_liability`` mapping names.

    Without them that mapped line is ``MISSING_SCREENER`` on every period, which
    is a structural warn — correct, and exactly what a zero-warn fixture must
    not carry.
    """
    if section != "balance-sheet":
        return
    for label, texts in (("Borrowings", ("400", "350")), ("Other Liabilities", ("40", "30"))):
        payload["rows"].append(
            {
                "position": len(payload["rows"]),
                "label": label,
                "status": "modeled",
                "unit": "rs_crore",
                "cells": [
                    {"period_index": index, "value": text, "raw_text": text, "published": True}
                    for index, text in enumerate(texts)
                ],
            }
        )


def _args(config: Path, **kwargs: object) -> argparse.Namespace:
    """The namespace a live retention run is driven with, carrying the new flags."""
    defaults: dict[str, object] = {
        "basis": BASIS.value,
        "triage_config": str(config),
        "warn_exit": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _retain(
    tmp_path: Path,
    name: str,
    *,
    pairs: tuple[tuple[str, str], ...],
    screener: Path,
    config: Path,
    bodies: dict[UpstoxSurface, dict[str, Any]] | None = None,
) -> Path:
    """One stub-transport run, whose only purpose is to leave a retention tree."""
    out_dir = tmp_path / name
    run_upstox_crosscheck_command(
        _args(config),
        isin_file=_isin_file(tmp_path, name, pairs),
        screener_root=screener,
        out_dir=out_dir,
        source=StubSource(bodies if bodies is not None else statement_bodies(BASIS.value)),
    )
    return out_dir / RETENTION_DIRNAME


def _replay(
    tmp_path: Path,
    name: str,
    *,
    pairs: tuple[tuple[str, str], ...],
    screener: Path,
    upstox_root: Path,
    config: Path,
    warn_exit: bool,
) -> tuple[int | None, Path]:
    """Dispatch a replay through the command's own parser, and return its exit code."""
    out_dir = tmp_path / f"{name}-replay"
    parser = argparse.ArgumentParser()
    add_upstox_crosscheck_parser(parser.add_subparsers(dest="command"))
    argv = [
        UPSTOX_CROSSCHECK_COMMAND,
        "--isin-file",
        str(_isin_file(tmp_path, f"{name}-replay", pairs)),
        "--screener-root",
        str(screener),
        "--out-dir",
        str(out_dir),
        "--basis",
        BASIS.value,
        "--upstox-root",
        str(upstox_root),
        "--triage-config",
        str(config),
    ]
    if warn_exit:
        argv.append("--warn-exit")
    code = dispatch_upstox_crosscheck_command(
        parser.parse_args(argv), credentials_factory=_refusing_credentials
    )
    return code, out_dir


def test_the_command_writes_the_triage_queue_and_counts_it_in_the_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T15/C-07: a warn nobody can read is a log line, so the queue is an artifact.

    Decision A keeps this lane log-only, which means the whole product of a warn
    is a file the review owner can work through — one line per listed row,
    carrying both stated amounts, the measure the class was decided on and the
    class itself, sorted so the warning classes come first. The summary gains a
    single ``warn`` column for the same reason the report gained counts: the
    monthly telemetry that a block decision was deferred until has to be readable
    off the run's own output without re-deriving it from the JSON.

    ``main`` sends structlog to stderr before dispatching, so this test does the
    same — otherwise it would assert against a logging setup the product never
    runs under.
    """
    module = _triage()
    _configure_logging()
    config = _config_file(tmp_path)
    pairs = ((NSE_ISIN, NSE_SYMBOL),)
    screener = _screener_root(tmp_path, NSE_SYMBOL, mutate=_profit_before_tax_restated)
    retained = _retain(tmp_path, "live", pairs=pairs, screener=screener, config=config)
    capsys.readouterr()

    code, out_dir = _replay(
        tmp_path,
        "warned",
        pairs=pairs,
        screener=screener,
        upstox_root=retained,
        config=config,
        warn_exit=False,
    )
    assert code == 0

    summary = capsys.readouterr().out.splitlines()
    assert SUMMARY_HEADER.endswith("\twarn")
    assert summary[0] == SUMMARY_HEADER
    assert summary[1].split("\t")[-1] == "3"

    assert module.WARNINGS_FILENAME == "warnings.tsv"
    lines = (out_dir / module.WARNINGS_FILENAME).read_text(encoding="utf-8").splitlines()
    assert module.WARNINGS_HEADER == EXPECTED_WARNINGS_HEADER
    assert lines[0] == EXPECTED_WARNINGS_HEADER
    assert len(lines) == 4

    fields = [line.split("\t") for line in lines[1:]]
    assert [tuple(row[index] for index in PINNED_COLUMNS) for row in fields] == [
        (
            NSE_ISIN,
            NSE_SYMBOL,
            BASIS.value,
            "Mar 2025",
            "total_liability",
            "RELATED_NOT_EQUIVALENT",
            "MISSING_SCREENER",
            "-",
            "STRUCTURAL",
        ),
        (
            NSE_ISIN,
            NSE_SYMBOL,
            BASIS.value,
            "Mar 2026",
            "total_liability",
            "RELATED_NOT_EQUIVALENT",
            "MISSING_SCREENER",
            "-",
            "STRUCTURAL",
        ),
        (
            NSE_ISIN,
            NSE_SYMBOL,
            BASIS.value,
            "Mar 2026",
            "operating_profit",
            "EQUIVALENCE_DEMONSTRATED",
            "MISMATCH",
            "0.3000",
            "MAGNITUDE",
        ),
    ]
    assert (Decimal(fields[2][7]), Decimal(fields[2][8])) == (Decimal("40"), Decimal("28"))

    report = json.loads((out_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
    triaged = [
        row
        for company in report["companies"]
        for crosscheck in company["reports"]
        for row in crosscheck["rows"]
        if row["upstox_category"] == "operating_profit" and crosscheck["period"] == "Mar 2026"
    ]
    assert triaged[0]["triage"] == "MAGNITUDE"
    assert Decimal(str(triaged[0]["relative_difference"])) == Decimal("0.3")


def test_only_warn_exit_turns_a_warning_into_a_non_zero_exit(tmp_path: Path) -> None:
    """T16: decision A stays the default, and a real refusal still outranks a warn.

    The owner approved ``--warn-exit`` as opt-in precisely so the default run
    keeps exiting zero however many rows it lists: the live base rate is one
    measurement old, and a check that starts failing builds on an unmeasured rate
    is switched off within a week — which would destroy the telemetry the block
    decision is waiting on. The flag exists for the operator's own manual runs,
    where a non-zero exit is the point. It must also never mask a response this
    repo could not read: an unreadable body means the comparison did not happen,
    which is a stronger statement than any number of disagreements, so its exit
    code wins.
    """
    _triage()
    from fundamentals.ingest.upstox_crosscheck import EXIT_WARN

    assert EXIT_WARN == 1
    config = _config_file(tmp_path)
    pairs = ((NSE_ISIN, NSE_SYMBOL),)

    warned = _screener_root(tmp_path / "a", NSE_SYMBOL)
    retained = _retain(tmp_path / "a", "live", pairs=pairs, screener=warned, config=config)
    for name, warn_exit, expected in (("silent", False, 0), ("flagged", True, 1)):
        code, _ = _replay(
            tmp_path / "a",
            name,
            pairs=pairs,
            screener=warned,
            upstox_root=retained,
            config=config,
            warn_exit=warn_exit,
        )
        assert code == expected, name

    clean = _screener_root(tmp_path / "b", NSE_SYMBOL, mutate=_liabilities_published)
    clean_retained = _retain(tmp_path / "b", "live", pairs=pairs, screener=clean, config=config)
    code, _ = _replay(
        tmp_path / "b",
        "clean",
        pairs=pairs,
        screener=clean,
        upstox_root=clean_retained,
        config=config,
        warn_exit=True,
    )
    assert code == 0

    both = ((NSE_ISIN, NSE_SYMBOL), (OTHER_ISIN, OTHER_SYMBOL))
    unreadable_screener = _screener_root(tmp_path / "c", NSE_SYMBOL, OTHER_SYMBOL)
    good = _retain(tmp_path / "c", "good", pairs=pairs, screener=unreadable_screener, config=config)
    bodies = statement_bodies(BASIS.value)
    bodies[UpstoxSurface.INCOME_STATEMENT] = UNREADABLE_BODY
    broken = _retain(
        tmp_path / "c",
        "broken",
        pairs=((OTHER_ISIN, OTHER_SYMBOL),),
        screener=unreadable_screener,
        config=config,
        bodies=bodies,
    )
    shutil.copytree(broken / OTHER_SYMBOL, good / OTHER_SYMBOL)
    code, _ = _replay(
        tmp_path / "c",
        "unreadable",
        pairs=both,
        screener=unreadable_screener,
        upstox_root=good,
        config=config,
        warn_exit=True,
    )
    assert code == 3


def test_a_triage_config_the_run_cannot_justify_refuses_instead_of_reporting(
    tmp_path: Path,
) -> None:
    """T13/T16: an unread config is a run that did not happen, not a warn.

    Every threshold and every exclusion in the config is a measurement, and the
    run's counts mean nothing until they have been applied — an acknowledgement
    that failed to load turns a documented definitional line into a warn, and a
    missing file would otherwise leave a report on disk that reads as if it had
    been triaged. So the config is read before the first request, and a config
    this repo cannot read ends the run with the code it uses for a response it
    could not read: the comparison did not happen. Never ``EXIT_WARN``, which
    says the opposite — that a comparison happened and found something — and the
    flag is set here to prove the two cannot be confused.
    """
    config = _config_file(tmp_path)
    pairs = ((NSE_ISIN, NSE_SYMBOL),)
    screener = _screener_root(tmp_path, NSE_SYMBOL)
    retained = _retain(tmp_path, "live", pairs=pairs, screener=screener, config=config)

    code, out_dir = _replay(
        tmp_path,
        "unjustified",
        pairs=pairs,
        screener=screener,
        upstox_root=retained,
        config=tmp_path / "absent.yaml",
        warn_exit=True,
    )
    assert code == EXIT_UNREADABLE
    assert not (out_dir / REPORT_FILENAME).exists()
    assert not (out_dir / _triage().WARNINGS_FILENAME).exists()
