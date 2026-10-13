"""Descriptor-safe path and file operations for joined vendor publications."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, NoReturn

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fundamentals.contracts.evidence import VersionPin
from fundamentals.contracts.source_catalog import EvidenceRole, SourceClass, SurfaceAuthority

MAX_CONFIG_BYTES = 64 * 1024 * 1024


class UnsafeVendorConfigPathError(ValueError):
    """A publication path is missing, unsafe, nonregular, oversized, or unstable."""


class VendorAuthorityEvidenceError(ValueError):
    """A released source-role or surface-rights projection is unsupported."""


class SourceDeclaration(BaseModel):
    """A derived source classification, distinct from surface retention authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    source_class: Literal[SourceClass.DERIVED]
    evidence_role: EvidenceRole
    classification_ref: str = Field(min_length=1)
    classification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceAuthorityArtifact(BaseModel):
    """Parsed source-role and per-surface rights artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    use_boundary: str | None = None
    sources: tuple[SourceDeclaration, ...] = ()
    surfaces: tuple[SurfaceAuthority, ...] = ()

    @model_validator(mode="after")
    def _unique_identities(self) -> SourceAuthorityArtifact:
        source_ids = [item.source_id for item in self.sources]
        surfaces = [(item.source_id, item.surface) for item in self.surfaces]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source authority contains conflicting source declarations")
        if len(surfaces) != len(set(surfaces)):
            raise ValueError("source authority contains conflicting surface declarations")
        return self


class SourceAuthorityReference(VersionPin):
    """The exact authority file joined into the release."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return canonical_relative_path(value)


class PublishedAuthority(BaseModel):
    """The resolved authority path and its immutable version pin."""

    model_config = ConfigDict(frozen=True)

    path: str
    pin: VersionPin


def canonical_relative_path(value: str) -> str:
    """Validate one canonical POSIX path contained by an already selected root."""
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("artifact member paths are canonical safe relative paths")
    return value


def canonical_version(value: str) -> str:
    """Validate one version used as a filename component."""
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or value.endswith(".yaml")
    ):
        raise ValueError("artifact version must be one canonical filename component")
    return value


@dataclass(frozen=True)
class _Snapshot:
    body: bytes
    directories: tuple[tuple[int, int], ...]
    file_identity: tuple[int, int, int, int, int]


def read_safe(root: Path, relative: str) -> bytes:
    """Read stable bounded bytes twice through fresh no-follow descriptor walks."""
    canonical_relative_path(relative)
    first = _snapshot(root, relative)
    second = _snapshot(root, relative)
    if first != second:
        raise UnsafeVendorConfigPathError(
            f"artifact path {relative!r} changed during its guarded read"
        )
    return second.body


def validate_authority_evidence(
    authority: SourceAuthorityArtifact,
    *,
    released: bool,
    repository_root: Path,
    private_boundary: str,
    upstox_decision: str,
    subscriber_decision: str,
    screener_source: str,
) -> tuple[str, ...]:
    """Resolve the two approved decision projections; unknown grants fail closed."""
    if not released:
        return ()
    if authority.use_boundary != private_boundary:
        raise VendorAuthorityEvidenceError(
            "released subscriber authority must carry the private-use boundary"
        )
    evidence_paths: set[str] = set()
    for declaration in authority.sources:
        if (
            declaration.source_id != "upstox"
            or declaration.source_class is not SourceClass.DERIVED
            or declaration.evidence_role is not EvidenceRole.DIAGNOSTIC_ONLY
            or declaration.classification_ref != upstox_decision
        ):
            raise VendorAuthorityEvidenceError(
                "unknown source-classification evidence or unsupported role projection"
            )
        body = read_safe(repository_root, declaration.classification_ref)
        if hashlib.sha256(body).hexdigest() != declaration.classification_sha256:
            raise VendorAuthorityEvidenceError("Upstox classification evidence content drift")
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise VendorAuthorityEvidenceError(
                "Upstox classification evidence must be UTF-8 text"
            ) from error
        if (
            "owner decision 2026-09-03" not in text
            or "registered diagnostic-only" not in text
            or "never a vote" not in text
        ):
            raise VendorAuthorityEvidenceError(
                "Upstox evidence does not establish the exact diagnostic-only role decision"
            )
        evidence_paths.add(declaration.classification_ref)

    for surface in authority.surfaces:
        if (
            surface.source_id not in {screener_source, "tijori"}
            or surface.evidence_role is not EvidenceRole.RECONCILABLE
            or surface.authority_ref != subscriber_decision
        ):
            raise VendorAuthorityEvidenceError(
                "unknown rights evidence or authority outside the approved subscriber sources"
            )
        body = read_safe(repository_root, surface.authority_ref)
        if hashlib.sha256(body).hexdigest() != surface.authority_sha256:
            raise VendorAuthorityEvidenceError("subscriber authority evidence content drift")
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise VendorAuthorityEvidenceError(
                "subscriber authority evidence must be UTF-8 text"
            ) from error
        if (
            "A05-DECISION-005" not in text
            or "AUTHORIZE_PRIVATE_SUBSCRIBER_USE" not in text
            or "PRIVATE / PERSONAL / NON-COMMERCIAL ONLY" not in text
            or "Screener.in" not in text
            or "Tijori Finance" not in text
        ):
            raise VendorAuthorityEvidenceError(
                "subscriber evidence does not establish the exact private-use decision"
            )
        evidence_paths.add(surface.authority_ref)
    return tuple(sorted(evidence_paths))


def selected_release_members(
    *,
    repository_root: Path,
    publication_relative: str,
    authority_path: str,
    normalisation_version: str,
    mapping_member_paths: tuple[str, ...],
    dictionary_version: str,
    dictionary_files: tuple[str, ...],
    authority_evidence: tuple[str, ...],
    extractor_member_paths: tuple[str, ...],
) -> tuple[str, ...]:
    """Return and validate every repository path whose bytes make candidate A."""
    selected = {
        f"config/{publication_relative}",
        f"config/{authority_path}",
        f"config/normalisation_policy/{canonical_version(normalisation_version)}.yaml",
        *(f"config/{path}" for path in mapping_member_paths),
        *(
            f"config/dictionary/{canonical_version(dictionary_version)}/{name}"
            for name in dictionary_files
        ),
        *authority_evidence,
        *(f"src/fundamentals/{path}" for path in extractor_member_paths),
    }
    paths = tuple(sorted(selected))
    for path in paths:
        read_safe(repository_root, path)
    return paths


def _snapshot(root: Path, relative: str) -> _Snapshot:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    open_fds: list[int] = []
    try:
        directory_fd, directories = _open_absolute_directory(root, directory_flags, open_fds)
        parts = PurePosixPath(relative).parts
        for component in parts[:-1]:
            directory_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            open_fds.append(directory_fd)
            info = os.fstat(directory_fd)
            directories.append((info.st_dev, info.st_ino))
        file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        open_fds.append(file_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            _unsafe(f"artifact path {relative!r} is not a regular file")
        if before.st_size > MAX_CONFIG_BYTES:
            _unsafe(f"artifact path {relative!r} exceeds the safe read limit")
        body = _bounded_read(file_fd)
        after = os.fstat(file_fd)
        before_identity = _identity(before)
        after_identity = _identity(after)
        if before_identity != after_identity:
            _unsafe(f"artifact path {relative!r} changed during its guarded read")
        return _Snapshot(
            body=body,
            directories=tuple(directories),
            file_identity=after_identity,
        )
    except UnsafeVendorConfigPathError:
        raise
    except (OSError, ValueError) as error:
        raise UnsafeVendorConfigPathError(
            f"artifact path {relative!r} is unsafe, missing, or symlinked"
        ) from error
    finally:
        for descriptor in reversed(open_fds):
            os.close(descriptor)


def _open_absolute_directory(
    root: Path, flags: int, open_fds: list[int]
) -> tuple[int, list[tuple[int, int]]]:
    absolute = root.absolute()
    anchor = absolute.anchor
    if not anchor:
        raise UnsafeVendorConfigPathError(f"artifact root {root!s} is not absolute")
    descriptor = os.open(anchor, flags)
    open_fds.append(descriptor)
    info = os.fstat(descriptor)
    identities = [(info.st_dev, info.st_ino)]
    for component in absolute.parts[1:]:
        descriptor = os.open(component, flags, dir_fd=descriptor)
        open_fds.append(descriptor)
        info = os.fstat(descriptor)
        identities.append((info.st_dev, info.st_ino))
    return descriptor, identities


def _bounded_read(file_fd: int) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_CONFIG_BYTES + 1
    while remaining:
        chunk = os.read(file_fd, min(1024 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    body = b"".join(chunks)
    if len(body) > MAX_CONFIG_BYTES:
        raise UnsafeVendorConfigPathError("artifact grew beyond the safe read limit")
    return body


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _unsafe(message: str) -> NoReturn:
    raise UnsafeVendorConfigPathError(message)
