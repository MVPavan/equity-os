"""No-clobber artifact writing shared by the acquisition CLI commands.

An acquisition command must never replace an artifact it did not create, and
must never follow a symlink into a path outside its output directory.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

REFUSE_OVERWRITE = "refusing to overwrite existing table artifact"


def preflight_out_paths(out_paths: tuple[Path, ...]) -> None:
    """Refuse the whole write when any target path already exists."""
    colliding = tuple(str(path) for path in out_paths if os.path.lexists(path))
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
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=out_path.parent,
        prefix=f".{out_path.stem}-",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, out_path, follow_symlinks=False)
        except FileExistsError as error:
            raise SystemExit(f"{REFUSE_OVERWRITE}: {out_path}") from error
    finally:
        temp_path.unlink(missing_ok=True)
