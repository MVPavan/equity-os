"""Append-only JSONL persistence for news observations and quarantine."""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import structlog

from fundamentals.contracts.news import NewsObservation

_LOGGER = structlog.get_logger(__name__)
_SYMBOL_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9&.-]{0,31}")
_QUARANTINE_FILENAME = "_unresolved.jsonl"
_CORRUPT_SUFFIX = ".corrupt"


class NewsStoreError(RuntimeError):
    """A provenance-store failure that must not be called a source outage."""


class NewsObservationStore:
    """Persist immutable source occurrences without overwriting prior rows."""

    def __init__(self, root: Path) -> None:
        """Configure the gitignored root without creating it until a write."""
        self._root = root

    def _symbol_path(self, symbol: str) -> Path:
        """Resolve a validated stock JSONL path beneath the configured root."""
        normalized = symbol.strip().upper()
        if _SYMBOL_PATTERN.fullmatch(normalized) is None:
            raise NewsStoreError(f"invalid news-store symbol: {symbol!r}")
        return self._root / f"{normalized}.jsonl"

    def _path_for(self, observation: NewsObservation) -> Path:
        """Route a resolved occurrence to its stock and all others to quarantine."""
        if observation.resolved and observation.symbol is not None:
            return self._symbol_path(observation.symbol)
        return self._root / _QUARANTINE_FILENAME

    @staticmethod
    @contextmanager
    def _locked_path(path: Path) -> Iterator[None]:
        """Hold one advisory lock across a complete JSONL read-modify-write operation."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = path.with_name(f".{path.name}.lock")
            with lock_path.open("a+b") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise NewsStoreError(f"could not lock news store {path}: {error}") from error

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        """Atomically replace a JSONL file after fsyncing its complete contents."""
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            raise NewsStoreError(
                f"could not atomically write news store {path}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _append_corrupt(path: Path, lines: list[bytes]) -> None:
        """Durably retain unreadable JSONL bytes in the adjacent corrupt sidecar."""
        sidecar = path.with_name(f"{path.name}{_CORRUPT_SUFFIX}")
        try:
            with sidecar.open("ab") as handle:
                for line in lines:
                    handle.write(line if line.endswith(b"\n") else line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise NewsStoreError(
                f"could not retain corrupt news row in {sidecar}: {error}"
            ) from error

    @classmethod
    def _read_locked(cls, path: Path) -> tuple[NewsObservation, ...]:
        """Load valid rows and isolate malformed bytes while the caller holds the lock."""
        if not path.is_file():
            return ()
        try:
            lines = path.read_bytes().splitlines(keepends=True)
        except OSError as error:
            raise NewsStoreError(f"could not read news store {path}: {error}") from error
        observations: list[NewsObservation] = []
        valid_lines: list[bytes] = []
        corrupt_lines: list[bytes] = []
        for line_number, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                valid_lines.append(raw_line)
                continue
            try:
                observation = NewsObservation.model_validate_json(raw_line)
            except (UnicodeDecodeError, ValueError) as error:
                corrupt_lines.append(raw_line)
                _LOGGER.warning(
                    "news_store_corrupt_row",
                    path=str(path),
                    line_number=line_number,
                    error=str(error),
                )
                continue
            observations.append(observation)
            valid_lines.append(raw_line if raw_line.endswith(b"\n") else raw_line + b"\n")
        if corrupt_lines:
            cls._append_corrupt(path, corrupt_lines)
            cls._atomic_write(path, b"".join(valid_lines))
        return tuple(observations)

    def append(self, observations: tuple[NewsObservation, ...]) -> int:
        """Append unseen identities through one locked durable replacement per target file."""
        grouped: dict[Path, list[NewsObservation]] = {}
        for observation in observations:
            grouped.setdefault(self._path_for(observation), []).append(observation)

        written = 0
        for path, candidates in grouped.items():
            with self._locked_path(path):
                existing = self._read_locked(path)
                existing_ids = {item.observation_id for item in existing}
                new_items: list[NewsObservation] = []
                for observation in candidates:
                    if observation.observation_id in existing_ids:
                        continue
                    existing_ids.add(observation.observation_id)
                    new_items.append(observation)
                if not new_items:
                    continue
                payload = b"".join(
                    item.model_dump_json().encode("utf-8") + b"\n"
                    for item in (*existing, *new_items)
                )
                self._atomic_write(path, payload)
                written += len(new_items)
        return written

    def read(self, symbol: str) -> tuple[NewsObservation, ...]:
        """Return every retained observation for one validated stock symbol."""
        path = self._symbol_path(symbol)
        with self._locked_path(path):
            return self._read_locked(path)

    def read_quarantine(self) -> tuple[NewsObservation, ...]:
        """Return every retained unresolved occurrence."""
        path = self._root / _QUARANTINE_FILENAME
        with self._locked_path(path):
            return self._read_locked(path)

    def source_had_data(self, source_id: str, *, symbol: str | None = None) -> bool:
        """Whether the store has any prior retained occurrence from a source prefix."""
        candidates = self.read(symbol) if symbol is not None else ()
        candidates += self.read_quarantine()
        return any(item.source_id.startswith(source_id) for item in candidates)
