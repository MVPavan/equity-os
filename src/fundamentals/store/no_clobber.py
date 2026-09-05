"""Creating a file without ever replacing or following what is already there.

This is the core the acquisition CLI commands have always written artifacts
through, moved down beside the stores that now need it too. Its rules are the
same three: a target that exists is never overwritten, a component that is a
symlink is never followed, and a multi-file write is refused whole rather than
half-applied.

It raises typed errors so a component can catch them. The CLI wrapper in
``api/artifact_writer.py`` translates each one back into the ``SystemExit`` an
operator reads.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fundamentals.contracts.snapshot import CaptureConflictError, UnsafePathError

PATH_EXISTS = "refusing to overwrite an existing path: {path}"
PATHS_EXIST = "refusing to overwrite existing paths: {paths}"
UNSAFE_DIRECTORY = "refusing an unsafe directory: {path}"
_TEMP_SUFFIX = ".tmp"


def safe_subdirectory(parent: Path, name: str) -> Path:
    """Create or accept one plain child directory without following a symlink."""
    path = parent / name
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise UnsafePathError(UNSAFE_DIRECTORY.format(path=path))
    path.mkdir(parents=True, exist_ok=True)
    if path.resolve().parent != parent.resolve():
        raise UnsafePathError(UNSAFE_DIRECTORY.format(path=path))
    return path


def existing_paths(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Every target that already exists, symlinks included."""
    return tuple(str(path) for path in paths if os.path.lexists(path))


def preflight_paths(paths: tuple[Path, ...]) -> None:
    """Refuse the whole write when any target path already exists."""
    colliding = existing_paths(paths)
    if colliding:
        raise CaptureConflictError(PATHS_EXIST.format(paths=", ".join(colliding)))


def write_bytes_no_clobber(out_path: Path, payload: bytes) -> None:
    """Atomically create one file without following or replacing a target.

    Retained bytes are written through this path rather than through a
    decode-and-re-encode, so what lands on disk stays identical to the bytes
    whose sha256 the record beside them states.
    """
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=out_path.parent,
        prefix=f".{out_path.stem}-",
        suffix=_TEMP_SUFFIX,
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
            raise CaptureConflictError(PATH_EXISTS.format(path=out_path)) from error
    finally:
        temp_path.unlink(missing_ok=True)


def fsync_directory(path: Path) -> None:
    """Flush a directory entry, so a created name survives a crash."""
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
