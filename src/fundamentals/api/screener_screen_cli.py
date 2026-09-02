"""CLI composition and evidence-first publication for raw screen acquisition."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    safe_subdirectory,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.ingest.screener_screen import acquire_screen
from fundamentals.ingest.screener_screen_models import (
    MAX_SCREEN_PAGES,
    ScreenAcquisitionConfig,
    ScreenerScreenCliRun,
    ScreenOutcome,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import ScreenerCredentials, ScreenerSessionConfig

SCREENER_SCREEN_COMMAND = "screener-screen"
ARTIFACT_FILENAME = "screener_screen.json"
PAGES_DIRNAME = "pages"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "screener-screen"


def add_screener_screen_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``screener-screen``, whose only required input is the query itself.

    ``--max-pages`` is a ``choices`` range rather than a bare int so an
    out-of-range walk is refused by argparse before a single authenticated
    request is spent against the rate-limit budget.
    """
    parser = subparsers.add_parser(
        SCREENER_SCREEN_COMMAND, help="acquire one authenticated raw Screener screen query"
    )
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--max-pages", type=int, choices=range(1, MAX_SCREEN_PAGES + 1), default=MAX_SCREEN_PAGES
    )
    parser.add_argument("--out", default=None)


def run_screener_screen_command(
    args: argparse.Namespace, *, credentials: ScreenerCredentials
) -> ScreenerScreenCliRun:
    """Acquire one screen and retain every page beside the artifact, or leave nothing.

    Each retained page is read back and re-hashed against what the fetch
    reported, so a truncated write is a failure rather than silent evidence.
    Any failure — including the acquisition itself — unlinks what this
    invocation wrote and removes the ``pages/`` directory if this invocation
    created it, so a refused run never leaves a half-populated directory that
    a later reader could mistake for a complete one.
    """
    out_dir = Path(args.out).resolve() if args.out else _default_out_dir(args.query)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / ARTIFACT_FILENAME
    preflight_out_paths((artifact_path,))
    pages_dir_path = out_dir / PAGES_DIRNAME
    pages_dir_was_new = not pages_dir_path.exists()
    pages_dir = safe_subdirectory(out_dir, PAGES_DIRNAME)
    source = ScreenerSessionSource(ScreenerSessionConfig(credentials=credentials))
    created: list[Path] = []
    page_paths: list[Path] = []
    try:
        run = acquire_screen(
            args.query, source=source, config=ScreenAcquisitionConfig(max_pages=args.max_pages)
        )
        for number, document in enumerate(run.documents, start=1):
            path = pages_dir / f"page_{number:04d}.raw.html"
            write_bytes_no_clobber(path, document.raw_body)
            created.append(path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != document.content_sha256:
                raise SystemExit(f"retained screen page hash mismatch: {path}")
            page_paths.append(path)
        write_json_no_clobber(artifact_path, run.artifact.model_dump_json(indent=2) + "\n")
        created.append(artifact_path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        if pages_dir_was_new:
            try:
                pages_dir.rmdir()
            except OSError:
                pass
        raise
    return ScreenerScreenCliRun(run=run, artifact_path=artifact_path, page_paths=tuple(page_paths))


def render_screener_screen_summary(published: ScreenerScreenCliRun) -> str:
    """Render the run as a two-line TSV: header, then one row of counts and the path."""
    artifact = published.run.artifact
    return "\n".join(
        (
            "outcome\tpages\trows\tcolumns\tartifact",
            "\t".join(
                (
                    artifact.outcome.value,
                    str(len(artifact.pages)),
                    str(len(artifact.rows)),
                    str(len(artifact.columns)),
                    str(published.artifact_path.resolve()),
                )
            ),
        )
    )


def is_incomplete(published: ScreenerScreenCliRun) -> bool:
    """Report whether the walk stopped short, which the dispatcher exits non-zero for.

    Zero results is not incomplete: an empty answer is an answer.
    """
    return published.run.artifact.outcome is ScreenOutcome.INCOMPLETE


def _default_out_dir(query: str) -> Path:
    """Derive a stable, filesystem-safe directory from the query text.

    The readable excerpt is for a human scanning ``data/raw``; the digest is
    what actually makes the name unique, since two different queries can easily
    share their first 48 sanitised characters.
    """
    excerpt = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:48].strip("-") or "query"
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
    return _DEFAULT_OUT_ROOT / f"{excerpt}-{digest}"
