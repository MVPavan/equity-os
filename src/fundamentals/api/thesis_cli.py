"""Argument-parser registration for the thesis CLI surface."""

from __future__ import annotations

import argparse
from pathlib import Path

from fundamentals.api.watchlist_config import Wave

_WAVE_CHOICES: tuple[str, ...] = tuple(wave.value for wave in Wave)


def add_wave_arg(subparser: argparse.ArgumentParser) -> None:
    """Add the shared ``--wave`` filter to a watchlist-capable command."""
    subparser.add_argument(
        "--wave",
        choices=_WAVE_CHOICES,
        default=None,
        help="scope a run to one wave, e.g. Wave-1 (per-wave roll-ups never collide)",
    )


def add_thesis_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    command: str,
    default_watchlist_path: Path,
) -> None:
    """Register the ``thesis`` parser without growing the composition root."""
    thesis = subparsers.add_parser(
        command,
        help="draft the non-authoritative cross-verified thesis from validated gold facts",
    )
    thesis_scope = thesis.add_mutually_exclusive_group()
    thesis_scope.add_argument(
        "--watchlist", action="store_true", help="draft a thesis for every watchlist stock"
    )
    thesis_scope.add_argument(
        "--symbol", default=None, help="draft a thesis for a single stock, e.g. MTARTECH"
    )
    add_wave_arg(thesis)
    thesis.add_argument(
        "--quarter",
        required=True,
        help="the reviewed quarter label, e.g. Q3FY25 (keys the gold file)",
    )
    thesis.add_argument(
        "--config",
        default=str(default_watchlist_path),
        help="path to watchlist.yaml (default: repo config/watchlist.yaml); resolves name/domain",
    )
    thesis.add_argument(
        "--thesis-config",
        default=None,
        help="path to non-secret thesis model settings YAML (default: built-in settings)",
    )
    thesis.add_argument(
        "--gold-dir",
        default=None,
        help="directory of <SYM>-<QUARTER>.json gold files (default: data/gold)",
    )
    thesis.add_argument(
        "--out-dir",
        default=None,
        help="directory for rendered thesis .md (default: docs/research/validation/thesis)",
    )
    thesis.add_argument(
        "--done-only",
        action="store_true",
        help="with --watchlist, draft only stocks whose local gold file exists",
    )
