"""The ``upstox`` command: acquire one approved surface and retain what came back.

    upstox --surface instruments --out <dir> [--include-suspended]

Slice 1 implements the instrument files, which need no token because
``assets.upstox.com`` serves them unauthenticated. Later slices add surfaces to
``--surface``; a surface with no reader is deliberately not offered as a choice,
so no run can half-execute one.

**Layout.** Each capture gets its own directory::

    <out>/upstox/<surface>/<route key>/<capture id>/
        upstox_<name>.raw.json.gz    the retained body, byte for byte
        upstox_<name>_meta.json      the capture record
        upstox_<name>.parsed.json    the typed catalog
        review.json                  outcome, unknown keys, anomalies

``capture_id`` is ``<YYYYMMDDTHHMMSSZ>-<content sha256 prefix>``, so append-only
holds as a filesystem property and no capture ever clobbers another. The
per-ISIN surfaces of later slices add a segment and key component below the
surface; the instrument files address no single security, so they use the route
key instead of inventing one.

The retained body goes through :func:`write_bytes_no_clobber` rather than a
decode-and-re-encode, so the bytes on disk stay identical to the ones the
recorded sha256 covers — the property the whole restatement check rests on.

Persistence is the artifact-writer pattern, not a store. The append-only
content-hashed snapshot store is ``eqos-kx4.4``'s deliverable and does not exist
yet; building an Upstox-specific ledger here would create a competing
persistence contract and an expensive migration (``eqos-f2m`` tracks the move).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED
from fundamentals.ingest.upstox_instruments import (
    UpstoxInstrumentCatalog,
    UpstoxSuspendedCatalog,
    read_instrument_catalog,
    read_suspended_catalog,
)
from fundamentals.ingest.upstox_source import (
    INSTRUMENTS_COMPLETE_KEY,
    INSTRUMENTS_SUSPENDED_KEY,
    AcquisitionOutcome,
    UpstoxConfig,
    UpstoxCredentials,
    UpstoxError,
    UpstoxFetch,
    UpstoxRoute,
    UpstoxSource,
    UpstoxSurface,
    route_for,
)

_LOGGER = structlog.get_logger(__name__)

UPSTOX_COMMAND = "upstox"
INSTRUMENTS_SURFACE = UpstoxSurface.INSTRUMENTS.value

# Only surfaces with a reader are offered. Slices 2-6 extend this tuple.
IMPLEMENTED_SURFACES: tuple[str, ...] = (INSTRUMENTS_SURFACE,)

ROOT_DIRECTORY = "upstox"
RAW_SUFFIX = ".raw.json.gz"
META_SUFFIX = "_meta.json"
PARSED_SUFFIX = ".parsed.json"
REVIEW_FILENAME = "review.json"
LISTED_STEM = "upstox_instruments"
SUSPENDED_STEM = "upstox_suspended"

SUMMARY_HEADER = "surface\troute\toutcome\trecords\tretained\tdirectory"

_SURFACE_FLAG = "--surface"
_OUT_FLAG = "--out"
_SUSPENDED_FLAG = "--include-suspended"
_HELP = "acquire one approved read-only Upstox surface and retain the response"
_SURFACE_HELP = "which approved surface to acquire"
_OUT_HELP = "directory the capture directories are written under"
_SUSPENDED_HELP = "also acquire the suspended-instrument file (retained evidence only)"
_REFUSED_EVENT = "upstox_refused"

# The token is read at the composition root only, never inside this module.
UPSTOX_TOKEN_ENV = "UPSTOX_ANALYTICS_TOKEN"


class SourceLike(Protocol):
    """The transport surface this command uses, so a test can supply its own."""

    def fetch(
        self,
        route: UpstoxRoute,
        query: Mapping[str, str] | None = None,
        **params: str,
    ) -> UpstoxFetch:
        """GET one approved route and retain its bytes."""
        ...

    def redact(self, text: str) -> str:
        """Return ``text`` with the access token removed."""
        ...


class CaptureSummary(BaseModel):
    """What one written capture reports back to the caller."""

    model_config = ConfigDict(frozen=True)

    surface: str
    route_key: str
    outcome_value: str
    record_count: int
    retained_count: int
    directory: str


class UpstoxRunResult(BaseModel):
    """Every capture one invocation wrote, in the order it wrote them."""

    model_config = ConfigDict(frozen=True)

    captures: tuple[CaptureSummary, ...]

    @property
    def outcome_value(self) -> str:
        """The first capture's outcome — the listed file, which drives the exit code."""
        return self.captures[0].outcome_value

    @property
    def refused(self) -> bool:
        """Whether any capture failed to produce a usable catalog."""
        return any(
            capture.outcome_value not in (AcquisitionOutcome.OK, AcquisitionOutcome.OK_EMPTY)
            for capture in self.captures
        )

    def render(self) -> str:
        """Render the run as TSV: one header, then one row per capture."""
        return "\n".join(
            (
                SUMMARY_HEADER,
                *(
                    "\t".join(
                        (
                            capture.surface,
                            capture.route_key,
                            capture.outcome_value,
                            str(capture.record_count),
                            str(capture.retained_count),
                            capture.directory,
                        )
                    )
                    for capture in self.captures
                ),
            )
        )


def add_upstox_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``upstox`` with the surfaces that actually have a reader."""
    parser = subparsers.add_parser(UPSTOX_COMMAND, help=_HELP)
    parser.add_argument(
        _SURFACE_FLAG, required=True, choices=IMPLEMENTED_SURFACES, help=_SURFACE_HELP
    )
    parser.add_argument(_OUT_FLAG, required=True, help=_OUT_HELP)
    parser.add_argument(_SUSPENDED_FLAG, action="store_true", help=_SUSPENDED_HELP)


def dispatch_upstox_command(
    args: argparse.Namespace,
    *,
    credentials_factory: Callable[[], UpstoxCredentials | None],
) -> int | None:
    """Run ``upstox`` and return its exit code, or ``None`` for another command."""
    if getattr(args, "command", None) != UPSTOX_COMMAND:
        return None
    source = UpstoxSource(UpstoxConfig(credentials=credentials_factory()))
    try:
        result = run_instruments_command(
            Path(args.out), source=source, include_suspended=bool(args.include_suspended)
        )
    except UpstoxError as refusal:
        _LOGGER.warning(
            _REFUSED_EVENT,
            refusal=type(refusal).__name__,
            detail=source.redact(str(refusal)),
        )
        return EXIT_REFUSED
    sys.stdout.write(result.render() + "\n")
    return EXIT_REFUSED if result.refused else EXIT_OK


def run_instruments_command(
    out_dir: Path, *, source: SourceLike, include_suspended: bool = False
) -> UpstoxRunResult:
    """Acquire the instrument files and write one capture directory per response.

    The suspended file is fetched only when asked. It emits no entity assertions
    and has no code consumer, so acquiring it stays an explicit decision each
    run rather than a default cost.
    """
    config = UpstoxConfig()
    listed_fetch = source.fetch(route_for(UpstoxSurface.INSTRUMENTS, INSTRUMENTS_COMPLETE_KEY))
    listed = read_instrument_catalog(
        listed_fetch, max_decompressed_bytes=config.max_decompressed_bytes
    )
    captures = [_write_capture(out_dir, listed_fetch, listed, stem=LISTED_STEM)]
    if include_suspended:
        suspended_fetch = source.fetch(
            route_for(UpstoxSurface.INSTRUMENTS, INSTRUMENTS_SUSPENDED_KEY)
        )
        suspended = read_suspended_catalog(
            suspended_fetch, max_decompressed_bytes=config.max_decompressed_bytes
        )
        captures.append(_write_capture(out_dir, suspended_fetch, suspended, stem=SUSPENDED_STEM))
    return UpstoxRunResult(captures=tuple(captures))


def _write_capture(
    out_dir: Path,
    fetch: UpstoxFetch,
    catalog: UpstoxInstrumentCatalog | UpstoxSuspendedCatalog,
    *,
    stem: str,
) -> CaptureSummary:
    """Write the four artifacts of one capture, refusing to clobber any of them.

    A drifted catalog is written exactly like a clean one. The bytes are the
    point: a reviewed parser upgrade can re-read them later, which is only
    possible if the failed attempt retained them instead of discarding the file.
    """
    capture = fetch.capture
    directory = out_dir / ROOT_DIRECTORY / capture.surface.value / capture.route_key
    directory = directory / capture.capture_id
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{stem}{RAW_SUFFIX}"
    meta_path = directory / f"{stem}{META_SUFFIX}"
    parsed_path = directory / f"{stem}{PARSED_SUFFIX}"
    review_path = directory / REVIEW_FILENAME
    preflight_out_paths((raw_path, meta_path, parsed_path, review_path))
    write_bytes_no_clobber(raw_path, fetch.raw_body)
    write_json_no_clobber(meta_path, capture.model_dump_json(indent=2) + "\n")
    write_json_no_clobber(parsed_path, catalog.model_dump_json(indent=2) + "\n")
    write_json_no_clobber(review_path, _review(catalog) + "\n")
    _LOGGER.info(
        "upstox_capture_written",
        surface=capture.surface.value,
        route_key=capture.route_key,
        outcome=catalog.outcome.value,
        records=catalog.record_count,
        retained=catalog.retained_count,
    )
    return CaptureSummary(
        surface=capture.surface.value,
        route_key=capture.route_key,
        outcome_value=catalog.outcome.value,
        record_count=catalog.record_count,
        retained_count=catalog.retained_count,
        directory=str(directory),
    )


def _review(catalog: UpstoxInstrumentCatalog | UpstoxSuspendedCatalog) -> str:
    """The review section: what a human should look at before trusting this capture."""
    return catalog.model_dump_json(
        include={"outcome", "unknown_keys", "anomalies", "record_count", "retained_count"},
        indent=2,
    )
