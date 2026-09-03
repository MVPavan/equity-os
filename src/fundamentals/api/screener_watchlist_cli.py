"""CLI composition and evidence-first publication for core-watchlist acquisition."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from fundamentals.api.artifact_writer import (
    preflight_out_paths,
    write_bytes_no_clobber,
    write_json_no_clobber,
)
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_models import ScreenerCredentials, ScreenerSessionConfig
from fundamentals.ingest.screener_watchlist import acquire_watchlist
from fundamentals.ingest.screener_watchlist_models import (
    ScreenerWatchlistCliRun,
    WatchlistOutcome,
)

SCREENER_WATCHLIST_COMMAND = "screener-watchlist"
ARTIFACT_FILENAME = "screener_watchlist.json"
DOCUMENT_FILENAMES = ("watchlist.raw.html", "watchlist.raw.csv")
SUMMARY_HEADER = "outcome\trows\tcolumns\tartifact"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT_ROOT = _REPO_ROOT / "data" / "raw" / "screener-watchlist"
_DEFAULT_LIST_DIRNAME = "default"
_WATCHLIST_ID_FLAG = "--watchlist-id"
_OUT_FLAG = "--out"
_HELP = "acquire one authenticated Screener watchlist beside its export"
_NOT_POSITIVE = "watchlist id must be a positive integer"
_HASH_MISMATCH = "retained watchlist body hash mismatch: {path}"


def _positive_watchlist_id(raw: str) -> int:
    """Parse ``--watchlist-id`` as a positive integer, refusing before any request."""
    try:
        parsed = int(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError(_NOT_POSITIVE) from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError(_NOT_POSITIVE)
    return parsed


def add_screener_watchlist_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register ``screener-watchlist``, whose only optional input is which list to fetch.

    The id is typed rather than a bare int so a zero, a negative or a word is
    refused by argparse before a single authenticated request is spent. The
    flags of the other Screener commands are deliberately absent: a caller
    passing ``--query`` here has been told nothing if the default list is
    acquired anyway.
    """
    parser = subparsers.add_parser(SCREENER_WATCHLIST_COMMAND, help=_HELP)
    parser.add_argument(_WATCHLIST_ID_FLAG, type=_positive_watchlist_id, default=None)
    parser.add_argument(_OUT_FLAG, default=None)


def run_screener_watchlist_command(
    args: argparse.Namespace, *, credentials: ScreenerCredentials
) -> ScreenerWatchlistCliRun:
    """Acquire one watchlist, retaining both bodies beside the artifact, or leaving nothing.

    The artifact is written last, so a reader that finds it finds both bodies
    already on disk and hashing to what it records. Each body is read back and
    re-hashed against what the fetch reported, so a truncated write is a failure
    rather than silent evidence. A run that refused is still published: the pair
    of responses that disagreed is what explains the disagreement, and rolling
    it back would delete exactly that.
    """
    out_dir = Path(args.out).resolve() if args.out else _default_out_dir(args.watchlist_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / ARTIFACT_FILENAME
    preflight_out_paths((artifact_path, *(out_dir / name for name in DOCUMENT_FILENAMES)))
    source = ScreenerSessionSource(ScreenerSessionConfig(credentials=credentials))
    created: list[Path] = []
    try:
        run = acquire_watchlist(source=source, watchlist_id=args.watchlist_id)
        for name, document in zip(DOCUMENT_FILENAMES, run.documents, strict=False):
            path = out_dir / name
            write_bytes_no_clobber(path, document.raw_body)
            created.append(path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != document.content_sha256:
                raise SystemExit(_HASH_MISMATCH.format(path=path))
        write_json_no_clobber(artifact_path, run.artifact.model_dump_json(indent=2) + "\n")
        created.append(artifact_path)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return ScreenerWatchlistCliRun(
        run=run, artifact_path=artifact_path, document_paths=tuple(created[:-1])
    )


def render_screener_watchlist_summary(published: ScreenerWatchlistCliRun) -> str:
    """Render the run as a two-line TSV: header, then the counts and the artifact path.

    The counts are what the source published, never a claim about the list: what
    the run proves is cross-render consistency at fetch time, and nothing here
    may read as a completeness guarantee.
    """
    artifact = published.run.artifact
    return "\n".join(
        (
            SUMMARY_HEADER,
            "\t".join(
                (
                    artifact.outcome.value,
                    str(len(artifact.rows)),
                    str(len(artifact.columns)),
                    str(published.artifact_path.resolve()),
                )
            ),
        )
    )


def is_incomplete(published: ScreenerWatchlistCliRun) -> bool:
    """Report whether the run stopped short, which the dispatcher exits non-zero for."""
    return published.run.artifact.outcome is WatchlistOutcome.INCOMPLETE


def other_watchlists(published: ScreenerWatchlistCliRun) -> tuple[str, ...]:
    """The other lists the selector offered, which this invocation did not acquire."""
    return published.run.artifact.other_watchlist_names


def _default_out_dir(watchlist_id: int | None) -> Path:
    """Derive the retained-body directory under the gitignored raw data root.

    ``data/raw`` is gitignored, which is what keeps the retained page's CSRF
    token out of any commit; the id names the list so two lists never collide.
    """
    name = _DEFAULT_LIST_DIRNAME if watchlist_id is None else str(watchlist_id)
    return _DEFAULT_OUT_ROOT / name
