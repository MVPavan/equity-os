"""The ``entity-map`` command surface: what it writes and what exit code it returns.

The flags are the ones amendment A9 fixed::

    entity-map build  --artifact <path> --config <path> --out <dir>
    entity-map verify --artifact <path> --config <path>

Every test here parses the invocation through :func:`build_parser` **before**
running it. That guard is what keeps the exit-code tests honest: argparse itself
exits ``2`` on an unregistered command, which is the same code the repo uses for
a refusal, so a test that only asserted "non-zero" would pass today for entirely
the wrong reason and keep passing against a command that was never wired up.

The synthetic sources are written into ``tmp_path`` by
:mod:`entity_map_fixtures`; nothing here opens a socket or reads a captured page.
"""

from __future__ import annotations

import json
from pathlib import Path

import entity_map_fixtures as fx
import test_entity_map_sources as source_tests

from fundamentals.api.cli import main
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.screener_cli_dispatch import EXIT_OK

COMMAND = "entity-map"
BUILD = "build"
VERIFY = "verify"


def _verify_argv(artifact: Path, config: Path) -> list[str]:
    """The ``entity-map verify`` invocation A9 specifies."""
    return [COMMAND, VERIFY, "--artifact", str(artifact), "--config", str(config)]


def _agreeing_sources(tmp_path: Path) -> tuple[Path, Path]:
    """One pin S1 confirms and one pin S1 does not carry — no conflict anywhere."""
    artifact = fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING])
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN, fx.DELTA_PIN])
    return artifact, config


def _conflicting_sources(tmp_path: Path) -> tuple[Path, Path]:
    """The same shape plus one pin that disagrees with S1 on the BSE scrip."""
    artifact = fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING, source_tests.CHARLIE_LISTING])
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN, source_tests.CHARLIE_PIN, fx.DELTA_PIN])
    return artifact, config


def test_verify_exits_zero_when_a_pin_is_merely_not_covered_by_the_watchlist(
    tmp_path: Path,
) -> None:
    """A9: ``NOT_COVERED`` is information, not failure.

    Nine of the ten pinned stocks are absent from the Core Watchlist today, so
    an implementation that failed the run on ``NOT_COVERED`` would make ``verify``
    permanently red and therefore permanently ignored. ``DELTA_PIN`` is absent
    from S1 and ``ALPHA_PIN`` is confirmed by it, so this invocation covers both
    zero-exit outcomes at once.
    """
    artifact, config = _agreeing_sources(tmp_path)
    parsed = build_parser().parse_args(_verify_argv(artifact, config))
    assert parsed.command == COMMAND

    assert main(_verify_argv(artifact, config)) == EXIT_OK


def test_verify_exits_non_zero_when_a_pin_conflicts_with_the_watchlist(
    tmp_path: Path,
) -> None:
    """A9: a conflicted pin, and only a conflicted pin, fails the run.

    The sibling test above proves the same command exits zero on a config whose
    only difference is that no pin disagrees, so a non-zero here cannot be
    explained by a bad path, an unparsed flag or a command that always fails.
    ``CHARLIE_PIN`` disagrees with S1 on the BSE scrip alone.
    """
    artifact, config = _conflicting_sources(tmp_path)
    parsed = build_parser().parse_args(_verify_argv(artifact, config))
    assert parsed.command == COMMAND

    assert main(_verify_argv(artifact, config)) != EXIT_OK


def test_build_writes_one_artifact_and_rebuilding_it_changes_no_byte(
    tmp_path: Path,
) -> None:
    """EM-11 / A9: the published file is what a human diffs, so a re-run must not churn.

    ``EM-11`` is pinned in :mod:`test_entity_map` at the model level; this
    proves it survives serialisation to disk through the real command. The
    output directory is globbed rather than matched against a hardcoded name,
    because A9 fixes the flags and not the filename. The file is parsed so a
    build that wrote an empty or truncated document cannot pass.
    """
    artifact, config = _agreeing_sources(tmp_path)
    out = tmp_path / "out"
    argv = [COMMAND, BUILD, "--artifact", str(artifact), "--config", str(config), "--out", str(out)]
    parsed = build_parser().parse_args(argv)
    assert parsed.command == COMMAND

    assert main(argv) == EXIT_OK
    written = sorted(out.glob("*.json"))
    assert len(written) == 1
    first = written[0].read_bytes()
    assert json.loads(first)["entities"]

    assert main(argv) == EXIT_OK
    assert written[0].read_bytes() == first
