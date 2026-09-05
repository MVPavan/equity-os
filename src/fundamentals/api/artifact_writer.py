"""No-clobber artifact writing shared by the acquisition CLI commands.

An acquisition command must never replace an artifact it did not create, and
must never follow a symlink into a path outside its output directory.

The rules themselves live in ``fundamentals.store.no_clobber``, where stores can
raise them typed. This module is the CLI face of that core: it keeps the exact
``SystemExit`` messages fourteen commands and their tests read.
"""

from __future__ import annotations

from pathlib import Path

from fundamentals.contracts.snapshot import CaptureConflictError, UnsafePathError
from fundamentals.store import no_clobber

REFUSE_OVERWRITE = "refusing to overwrite existing table artifact"
REFUSE_UNSAFE_DIRECTORY = "refusing unsafe artifact directory"


def safe_subdirectory(out_dir: Path, name: str) -> Path:
    """Create or accept one plain child directory without following a symlink."""
    try:
        return no_clobber.safe_subdirectory(out_dir, name)
    except UnsafePathError as error:
        raise SystemExit(f"{REFUSE_UNSAFE_DIRECTORY}: {out_dir / name}") from error


def preflight_out_paths(out_paths: tuple[Path, ...]) -> None:
    """Refuse the whole write when any target path already exists."""
    colliding = no_clobber.existing_paths(out_paths)
    if colliding:
        raise SystemExit(f"{REFUSE_OVERWRITE}s: {', '.join(colliding)}")


def write_json_no_clobber(out_path: Path, payload: str) -> None:
    """Atomically create one JSON artifact without following or replacing a target."""
    write_bytes_no_clobber(out_path, payload.encode("utf-8"))


def write_bytes_no_clobber(out_path: Path, payload: bytes) -> None:
    """Atomically create one binary artifact without following or replacing a target.

    Retained response bodies are written through this path rather than through a
    decode-and-re-encode, so the bytes on disk stay identical to the ones whose
    sha256 the artifact beside them records.
    """
    try:
        no_clobber.write_bytes_no_clobber(out_path, payload)
    except CaptureConflictError as error:
        raise SystemExit(f"{REFUSE_OVERWRITE}: {out_path}") from error
