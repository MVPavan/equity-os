"""The ``entity-map`` command: publish the identity map, or verify the pins.

    entity-map build  --artifact <path> --config <path> --out <dir>
    entity-map verify --artifact <path> --config <path>

Both read files already on disk and make no request of any kind. ``verify`` is
read-only toward both sources: it reports a wrong pin, it never repairs one, and
it fails the run only on a genuine disagreement — a pin the watchlist simply
does not cover is information, and failing on it would make the command
permanently red and therefore permanently ignored.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import structlog

from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.contracts.entity_identity import (
    EntityMap,
    EntityMapError,
    VerificationReport,
)
from fundamentals.entity.entity_map import build_entity_map, verify_pins
from fundamentals.entity.entity_map_sources import load_s1_records, load_s2_records

ENTITY_MAP_COMMAND = "entity-map"
BUILD_ACTION = "build"
VERIFY_ACTION = "verify"
ARTIFACT_FILENAME = "entity_map.json"
BUILD_SUMMARY_HEADER = "entities\tconflicted\tartifact"
VERIFY_SUMMARY_HEADER = "symbol\toutcome\tdisagreements"

_ACTION_DEST = "entity_map_action"
_ARTIFACT_FLAG = "--artifact"
_CONFIG_FLAG = "--config"
_OUT_FLAG = "--out"
_HELP = "build or verify the current-state entity identity map from files on disk"
_BUILD_HELP = "publish one deterministic entity-map artifact"
_VERIFY_HELP = "report every hand-pinned identifier as confirmed, conflicted or not covered"
_ARTIFACT_HELP = "path to a published screener-watchlist artifact JSON"
_CONFIG_HELP = "path to the hand-pinned watchlist YAML"
_OUT_HELP = "directory the entity-map artifact is written into"
_UNSAFE_OUT = "refusing unsafe entity-map artifact path: {path}"
_REFUSED_EVENT = "entity_map_refused"


class UnsafeArtifactPathError(EntityMapError):
    """The build was asked to publish through a symlink or a non-file."""


def add_entity_map_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``entity-map`` and its two actions, both wholly offline.

    Every path is required rather than defaulted: this command joins two sources
    into one published identity, and a caller who mistyped one of them must be
    told, not quietly given the repository's own config.
    """
    parser = subparsers.add_parser(ENTITY_MAP_COMMAND, help=_HELP)
    actions = parser.add_subparsers(dest=_ACTION_DEST, required=True)
    build = actions.add_parser(BUILD_ACTION, help=_BUILD_HELP)
    _add_source_args(build)
    build.add_argument(_OUT_FLAG, required=True, help=_OUT_HELP)
    verify = actions.add_parser(VERIFY_ACTION, help=_VERIFY_HELP)
    _add_source_args(verify)


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    """Add the two source paths both actions read."""
    parser.add_argument(_ARTIFACT_FLAG, required=True, help=_ARTIFACT_HELP)
    parser.add_argument(_CONFIG_FLAG, required=True, help=_CONFIG_HELP)


def dispatch_entity_map_command(args: argparse.Namespace) -> int:
    """Run the selected action and return its process exit code.

    Every refusal this command can reach is typed, so a malformed ISIN, an
    incomplete artifact or two companies claiming one ticker leaves the same
    ``EXIT_REFUSED`` every sibling command uses — not a stack trace on exit 1,
    which reads to a caller as a crash rather than as the designed answer.
    """
    artifact_path = Path(args.artifact)
    config_path = Path(args.config)
    try:
        if getattr(args, _ACTION_DEST) == BUILD_ACTION:
            built = run_entity_map_build(artifact_path, config_path, Path(args.out))
            sys.stdout.write(render_build_summary(built, Path(args.out)) + "\n")
            return EXIT_OK
        report = verify_pins(artifact_path, config_path)
    except EntityMapError as refusal:
        structlog.get_logger("fundamentals.entity_map").warning(
            _REFUSED_EVENT, refusal=type(refusal).__name__, detail=str(refusal)
        )
        return EXIT_REFUSED
    sys.stdout.write(render_verify_summary(report) + "\n")
    return EXIT_REFUSED if report.has_conflict() else EXIT_OK


def run_entity_map_build(artifact_path: Path, config_path: Path, out_dir: Path) -> EntityMap:
    """Build the map from both sources and publish it into ``out_dir``.

    The artifact is replaced rather than refused on a re-run: it is derived, not
    evidence, and the point of a deterministic build is that re-running it over
    unchanged inputs leaves the bytes exactly as they were.
    """
    built = build_entity_map(load_s1_records(artifact_path) + load_s2_records(config_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_replacing(out_dir / ARTIFACT_FILENAME, built.model_dump_json(indent=2) + "\n")
    return built


def render_build_summary(built: EntityMap, out_dir: Path) -> str:
    """Render the build as a two-line TSV: header, then the counts and the path."""
    return "\n".join(
        (
            BUILD_SUMMARY_HEADER,
            "\t".join(
                (
                    str(len(built.entities)),
                    str(len(built.conflicts)),
                    str((out_dir / ARTIFACT_FILENAME).resolve()),
                )
            ),
        )
    )


def render_verify_summary(report: VerificationReport) -> str:
    """Render one report row per pinned stock, naming what disagreed."""
    return "\n".join(
        (
            VERIFY_SUMMARY_HEADER,
            *(
                "\t".join(
                    (
                        entry.symbol,
                        entry.outcome.value,
                        ",".join(namespace.value for namespace in entry.disagreements),
                    )
                )
                for entry in report.entries
            ),
        )
    )


def _write_replacing(out_path: Path, payload: str) -> None:
    """Atomically write one artifact, never through a symlink."""
    if out_path.is_symlink() or (out_path.exists() and not out_path.is_file()):
        raise UnsafeArtifactPathError(_UNSAFE_OUT.format(path=out_path))
    descriptor, temp_name = tempfile.mkstemp(
        dir=out_path.parent, prefix=f".{out_path.stem}-", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, out_path)
    finally:
        temp_path.unlink(missing_ok=True)
