"""Fixed coordinator receipt and Git-history verification for vendor publications."""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal, NoReturn

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fundamentals.evidence.vendor_config_files import (
    canonical_relative_path,
    canonical_version,
    read_safe,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"


class VendorPublicationReceiptError(ValueError):
    """The fixed receipt, review result, selected bytes, or Git history is invalid."""


class ReceiptContentMember(BaseModel):
    """One exact repository-relative file pinned by the coordinator receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return canonical_relative_path(value)


class ReleaseReviewReceipt(BaseModel):
    """Coordinator record committed after review; callers never select its path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    publication_version: str = Field(min_length=1)
    publication_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewed_commit: str = Field(pattern=COMMIT_PATTERN)
    selected_members_sha256: str = Field(pattern=SHA256_PATTERN)
    review_result: ReceiptContentMember
    verdict: Literal["APPROVE"]
    coordinator_recorded_at: datetime

    @model_validator(mode="after")
    def _aware_recorded_at(self) -> ReleaseReviewReceipt:
        if self.coordinator_recorded_at.tzinfo is None:
            raise ValueError("coordinator receipt timestamp must be timezone-aware")
        return self


def verify_release_receipt(
    receipt: ReleaseReviewReceipt,
    *,
    repository_root: Path,
    version: str,
    selected_paths: Sequence[str],
    receipt_relative: str,
) -> None:
    """Verify immutable candidate A, introduction C, and current first-parent HEAD H."""
    try:
        canonical_version(version)
        canonical_relative_path(receipt_relative)
        if receipt.review_result.path in {*selected_paths, receipt_relative}:
            _invalid("review result and receipt are records, not candidate release members")
        if _selected_members_sha256(repository_root, selected_paths) != (
            receipt.selected_members_sha256
        ):
            _invalid("review receipt selected-member digest differs")

        receipt_body = read_safe(repository_root, receipt_relative)
        try:
            fixed_receipt = ReleaseReviewReceipt.model_validate(yaml.safe_load(receipt_body))
        except (ValidationError, yaml.YAMLError) as error:
            raise VendorPublicationReceiptError("fixed receipt bytes are invalid") from error
        if fixed_receipt != receipt:
            _invalid("verified receipt model differs from the fresh fixed receipt bytes")
        review_body = read_safe(repository_root, receipt.review_result.path)
        if hashlib.sha256(review_body).hexdigest() != receipt.review_result.content_sha256:
            _invalid("review result content differs from its receipt pin")
        _require_approving_review(review_body)

        head = _git_text(repository_root, "rev-parse", "HEAD")
        history = tuple(_git_text(repository_root, "rev-list", "--first-parent", head).splitlines())
        if receipt.reviewed_commit not in history:
            _invalid("reviewed candidate commit is not on HEAD's first-parent history")
        _verify_selected_bytes(receipt, repository_root, selected_paths, head)
        if _git_blob(repository_root, receipt.reviewed_commit, receipt_relative) is not None or (
            _git_blob(repository_root, receipt.reviewed_commit, receipt.review_result.path)
            is not None
        ):
            _invalid("candidate release commit must precede its receipt and review result")
        _verify_introduction_history(
            receipt,
            repository_root=repository_root,
            receipt_relative=receipt_relative,
            receipt_body=receipt_body,
            review_body=review_body,
            head=head,
        )
    except VendorPublicationReceiptError:
        raise
    except (OSError, ValueError) as error:
        raise VendorPublicationReceiptError(str(error)) from error


def _selected_members_sha256(repository_root: Path, paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        body = read_safe(repository_root, path)
        digest.update(path.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(body).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def _verify_selected_bytes(
    receipt: ReleaseReviewReceipt,
    repository_root: Path,
    selected_paths: Sequence[str],
    head: str,
) -> None:
    for path in selected_paths:
        current = read_safe(repository_root, path)
        if _git_blob(repository_root, receipt.reviewed_commit, path) != current:
            _invalid(f"selected release member {path!r} differs from reviewed candidate commit")
        if _git_blob(repository_root, head, path) != current:
            _invalid(f"selected release member {path!r} is dirty or untracked at HEAD")


def _verify_introduction_history(
    receipt: ReleaseReviewReceipt,
    *,
    repository_root: Path,
    receipt_relative: str,
    receipt_body: bytes,
    review_body: bytes,
    head: str,
) -> None:
    commits = tuple(
        line
        for line in _git_text(
            repository_root,
            "rev-list",
            "--first-parent",
            "--reverse",
            f"{receipt.reviewed_commit}..{head}",
        ).splitlines()
        if line
    )
    introductions: list[str] = []
    for commit in commits:
        parent = _git_text(repository_root, "rev-parse", f"{commit}^")
        if (
            _git_blob(repository_root, commit, receipt_relative) == receipt_body
            and _git_blob(repository_root, commit, receipt.review_result.path) == review_body
            and _git_blob(repository_root, parent, receipt_relative) is None
            and _git_blob(repository_root, parent, receipt.review_result.path) is None
        ):
            introductions.append(commit)
    if len(introductions) != 1:
        _invalid(
            "receipt and review result require one unambiguous first-parent introduction commit"
        )
    introduced = introductions[0]
    later = tuple(
        line
        for line in _git_text(
            repository_root,
            "rev-list",
            "--first-parent",
            "--reverse",
            f"{introduced}..{head}",
        ).splitlines()
        if line
    )
    for commit in (introduced, *later):
        if (
            _git_blob(repository_root, commit, receipt_relative) != receipt_body
            or _git_blob(repository_root, commit, receipt.review_result.path) != review_body
        ):
            _invalid("receipt or review result changed after approval")
    if (
        _git_blob(repository_root, head, receipt_relative) != receipt_body
        or _git_blob(repository_root, head, receipt.review_result.path) != review_body
    ):
        _invalid("receipt or review result is dirty or untracked at HEAD")


def _git_text(repository_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=repository_root,
            check=True,
            capture_output=True,
            env=_git_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise VendorPublicationReceiptError(
            f"Git release verification failed for {args!r}"
        ) from error
    try:
        return completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise VendorPublicationReceiptError("Git returned a non-ASCII object identity") from error


def _require_approving_review(review_body: bytes) -> None:
    """Require one exact top-level approval as the review's final nonblank line."""
    try:
        lines = review_body.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VendorPublicationReceiptError("review result must be UTF-8 text") from error
    nonblank = [line for line in lines if line.strip()]
    verdicts = [
        line for line in nonblank if line == line.lstrip() and line.upper().startswith("VERDICT:")
    ]
    expected = "VERDICT: APPROVE"
    if (
        len(verdicts) != 1
        or verdicts[0].strip().upper() != expected
        or nonblank[-1].strip().upper() != expected
    ):
        _invalid("review result requires one unambiguous final VERDICT: APPROVE")


def _git_blob(repository_root: Path, commit: str, path: str) -> bytes | None:
    canonical_relative_path(path)
    try:
        completed = subprocess.run(
            ("git", "show", f"{commit}:{path}"),
            cwd=repository_root,
            check=False,
            capture_output=True,
            env=_git_environment(),
        )
    except OSError as error:
        raise VendorPublicationReceiptError("Git blob verification could not run") from error
    if completed.returncode == 0:
        return completed.stdout
    if completed.returncode == 128:
        return None
    raise VendorPublicationReceiptError(f"Git blob verification failed for {path!r}")


def _git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment


def _invalid(message: str) -> NoReturn:
    raise VendorPublicationReceiptError(message)
