"""Anchored directory descriptors: pinned ancestry and short-lived fd trees."""

from __future__ import annotations

import fcntl
import os
import stat
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from fundamentals.contracts.snapshot import (
    RELATIVE_COMPONENTS,
    CaptureConflictError,
    IntegrityError,
    MissingSnapshotError,
    SnapshotIOError,
    UnsafePathError,
)

UNSAFE_COMPONENT = "refusing a path component that is not one plain directory name: {name}"

MAX_METADATA_BYTES = 64 * 1024
READ_BUDGET_SECONDS = 5.0
LOCK_FILENAME = ".snapshot-writer.lock"


def _check_component(name: str) -> None:
    """Refuse a name that is anything other than one plain directory entry."""
    if not name or name in RELATIVE_COMPONENTS or "/" in name or os.sep in name:
        raise UnsafePathError(UNSAFE_COMPONENT.format(name=name))


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _protected(info: os.stat_result, label: str, *, private: bool = False) -> None:
    forbidden = 0o077 if private else 0o022
    if info.st_uid != os.getuid() or info.st_mode & forbidden:
        raise UnsafePathError(f"unsafe ownership or permissions: {label}")


@dataclass(frozen=True)
class DirectoryAnchor:
    """Operator-pinned directory and ancestry; never imported from source JSON.

    This detects substitution, not malicious same-account administrator rewrites.
    """

    path: Path
    identities: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        path = self.path.absolute()
        if self.identities:
            raise UnsafePathError("directory identities must be observed locally")
        fds = [os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
        identities = [_identity(os.fstat(fds[0]))]
        try:
            for name in path.parts[1:]:
                _check_component(name)
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1])
                fds.append(fd)
                identities.append(_identity(os.fstat(fd)))
            for fd in fds[-2:]:
                _protected(os.fstat(fd), str(path))
        except OSError as error:
            raise UnsafePathError(f"unsafe directory anchor: {path}") from error
        finally:
            for fd in reversed(fds):
                os.close(fd)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "identities", tuple(identities))


class DescriptorTree:
    """Short-lived descriptors for one anchored operation, including durability."""

    def __init__(self, anchor: DirectoryAnchor) -> None:
        self.anchor = anchor
        self.fds: list[int] = []
        self.edges: list[tuple[int, str, int]] = []
        self.files: list[int] = []
        self.read_files: list[tuple[int, str, int, os.stat_result]] = []
        self.root = -1

    def __enter__(self) -> DescriptorTree:
        try:
            fd = os.open(self.anchor.path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.fds.append(fd)
            for index, name in enumerate(self.anchor.path.parts[1:], 1):
                parent = fd
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                self.fds.append(fd)
                self.edges.append((parent, name, fd))
                if _identity(os.fstat(fd)) != self.anchor.identities[index]:
                    raise UnsafePathError(f"substituted anchor: {self.anchor.path}")
            self.root = fd
            for protected_fd in self.fds[-2:]:
                _protected(os.fstat(protected_fd), str(self.anchor.path))
            self.verify()
            return self
        except OSError as error:
            self.close()
            raise UnsafePathError(f"cannot open protected anchor: {self.anchor.path}") from error
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        for fd in reversed(self.files + self.fds):
            os.close(fd)
        self.files.clear()
        self.fds.clear()

    def verify(self) -> None:
        for parent, name, fd in self.edges:
            try:
                found = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise UnsafePathError(f"detached directory: {name}") from error
            if not stat.S_ISDIR(found.st_mode) or _identity(found) != _identity(os.fstat(fd)):
                raise UnsafePathError(f"substituted directory: {name}")
        for parent, name, fd, before in self.read_files:
            try:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise UnsafePathError(f"detached file: {name}") from error
            opened = os.fstat(fd)
            if (
                not stat.S_ISREG(current.st_mode)
                or _identity(current) != _identity(before)
                or opened.st_mtime_ns != before.st_mtime_ns
                or opened.st_size != before.st_size
            ):
                raise IntegrityError(f"file changed during operation: {name}")
        root_index = self.fds.index(self.root)
        for fd in self.fds[max(0, root_index - 1) :]:
            _protected(os.fstat(fd), "store directory")

    def flush(self) -> None:
        self.verify()
        for fd in self.files:
            os.fsync(fd)
        # Flush authoritative children and all parent entries through the anchor's parent.
        root_index = self.fds.index(self.root)
        for fd in reversed(self.fds[max(0, root_index - 1) :]):
            os.fsync(fd)
        self.verify()

    def exists(self, parent: int, name: str) -> bool:
        _check_component(name)
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def child(self, parent: int, name: str, *, create: bool = False, private: bool = False) -> int:
        _check_component(name)
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
        try:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError as error:
            raise MissingSnapshotError(f"missing directory: {name}") from error
        except OSError as error:
            raise UnsafePathError(f"unsafe directory: {name}") from error
        self.fds.append(fd)
        self.edges.append((parent, name, fd))
        _protected(os.fstat(fd), name, private=private)
        if create:
            os.fsync(fd)
            os.fsync(parent)
        self.verify()
        return fd

    def descend(
        self, names: tuple[str, ...], *, create: bool = False, private: bool = False
    ) -> int:
        fd = self.root
        for name in names:
            fd = self.child(fd, name, create=create, private=private)
        return fd

    def relocate(self, fd: int, parent: int, name: str) -> None:
        self.edges = [(p, n, child) for p, n, child in self.edges if child != fd]
        self.edges.append((parent, name, fd))

    def read(self, parent: int, name: str, cap: int, *, private: bool = False) -> bytes:
        _check_component(name)
        deadline = time.monotonic() + READ_BUDGET_SECONDS
        try:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise UnsafePathError(f"nonregular file: {name}")
            _protected(before, name, private=private)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            self.files.append(fd)
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
                raise UnsafePathError(f"substituted/nonregular file: {name}")
            _protected(opened, name, private=private)
            self.read_files.append((parent, name, fd, opened))
            if opened.st_size > cap:
                raise IntegrityError(f"oversize file: {name}")
            data = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise SnapshotIOError(f"read budget exceeded: {name}")
                chunk = os.read(fd, min(64 * 1024, cap + 1 - len(data)))
                if time.monotonic() > deadline:
                    raise SnapshotIOError(f"read budget exceeded: {name}")
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > cap:
                    raise IntegrityError(f"oversize/growing file: {name}")
            after = os.fstat(fd)
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                _identity(current) != _identity(opened)
                or after.st_size != len(data)
                or opened.st_mtime_ns != after.st_mtime_ns
                or opened.st_ctime_ns != after.st_ctime_ns
            ):
                raise IntegrityError(f"file changed during read: {name}")
            self.verify()
            return bytes(data)
        except FileNotFoundError as error:
            raise MissingSnapshotError(f"missing file: {name}") from error
        except OSError as error:
            raise SnapshotIOError(f"cannot read file: {name}") from error

    def publish_file(self, parent: int, name: str, data: bytes) -> None:
        _check_component(name)
        if self.exists(parent, name):
            if self.read(parent, name, max(len(data), 1)) != data:
                raise CaptureConflictError(f"conflicting publication: {name}")
            os.fsync(parent)
            return
        temporary = ".tmp-" + uuid.uuid4().hex
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        self.files.append(fd)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise SnapshotIOError("short publication write")
            view = view[written:]
        os.fsync(fd)
        self.verify()
        written_info = os.fstat(fd)
        temp_info = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(temp_info.st_mode) or _identity(temp_info) != _identity(written_info):
            raise UnsafePathError(f"substituted temporary publication: {name}")
        try:
            os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError as error:
            raise CaptureConflictError(f"publication already exists: {name}") from error
        installed_info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(installed_info.st_mode) or _identity(installed_info) != _identity(
            written_info
        ):
            raise UnsafePathError(f"substituted final publication: {name}")
        self.read_files.append((parent, name, fd, written_info))
        os.fsync(parent)
        os.unlink(temporary, dir_fd=parent)
        os.fsync(parent)
        self.verify()

    @contextmanager
    def writer_lock(self) -> Iterator[None]:
        if not self.exists(self.root, LOCK_FILENAME):
            try:
                self.publish_file(self.root, LOCK_FILENAME, b"local snapshot writer\n")
            except CaptureConflictError:
                pass
        self.read(self.root, LOCK_FILENAME, MAX_METADATA_BYTES, private=True)
        fd = self.files[-1]
        deadline = time.monotonic() + READ_BUDGET_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise SnapshotIOError("store writer lock deadline exceeded") from error
                time.sleep(0.01)
        try:
            self.verify()
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
