"""Commit-history mechanics for a fixed vendor-publication review receipt."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from fundamentals.evidence import vendor_config as publication

RELEASE = "config/vendor_publication/v2.yaml"
RECEIPT = "config/vendor_publication/v2.review.yaml"
REVIEW = "docs/reviews/vendor-v2.md"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(root: Path, message: str) -> str:
    paths = tuple(path for path in (RELEASE, RECEIPT, REVIEW) if (root / path).exists())
    _git(root, "add", *paths)
    _git(
        root,
        "-c",
        "user.name=Publication Test",
        "-c",
        "user.email=publication@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(root, "rev-parse", "HEAD")


def _write_approval(
    root: Path,
    candidate: str,
    *,
    review_body: bytes = b"Independent review\nVERDICT: APPROVE\n",
    recorded_at: str = "2026-10-13T09:00:00+00:00",
) -> publication._ReleaseReviewReceipt:
    release = root / RELEASE
    review = root / REVIEW
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_bytes(review_body)
    selected_digest = hashlib.sha256(
        RELEASE.encode("utf-8")
        + b"\0"
        + hashlib.sha256(release.read_bytes()).hexdigest().encode("ascii")
        + b"\n"
    ).hexdigest()
    receipt_document = {
        "publication_version": "v2",
        "publication_sha256": hashlib.sha256(release.read_bytes()).hexdigest(),
        "reviewed_commit": candidate,
        "selected_members_sha256": selected_digest,
        "review_result": {
            "path": REVIEW,
            "content_sha256": hashlib.sha256(review_body).hexdigest(),
        },
        "verdict": "APPROVE",
        "coordinator_recorded_at": recorded_at,
    }
    receipt = root / RECEIPT
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(yaml.safe_dump(receipt_document, sort_keys=False), encoding="utf-8")
    return publication._ReleaseReviewReceipt.model_validate(receipt_document)


def _fixture(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    review_body: bytes = b"Independent review\nVERDICT: APPROVE\n",
) -> publication._ReleaseReviewReceipt:
    _git(root, "init", "-q")
    release = root / RELEASE
    release.parent.mkdir(parents=True)
    release.write_text("version: v2\nstate: RELEASED\n", encoding="utf-8")
    candidate = _commit(root, "candidate A")
    receipt = _write_approval(root, candidate, review_body=review_body)
    _commit(root, "receipt C")
    unrelated = root / "notes.txt"
    unrelated.write_text("later progress log\n", encoding="utf-8")
    _git(root, "add", "notes.txt")
    _git(
        root,
        "-c",
        "user.name=Publication Test",
        "-c",
        "user.email=publication@example.invalid",
        "commit",
        "-m",
        "unrelated H",
    )
    monkeypatch.setattr(publication, "_REPOSITORY_ROOT", root)
    return receipt


def test_reviewed_candidate_and_immutable_receipt_accept_unrelated_later_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)

    publication._verify_release_receipt(
        receipt,
        version="v2",
        selected_paths=(RELEASE,),
        receipt_relative=RECEIPT,
    )


def test_review_result_final_request_changes_cannot_authorize_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(
        tmp_path,
        monkeypatch,
        review_body=(
            b"Earlier draft recorded VERDICT: APPROVE\n"
            b"The remaining security defect is unresolved.\n"
            b"VERDICT: REQUEST_CHANGES\n"
        ),
    )

    with pytest.raises(publication.VendorConfigPublicationError, match="final.*APPROVE"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


@pytest.mark.parametrize(
    "review_body",
    [
        b"The required literal would be VERDICT: APPROVE\n",
        b"VERDICT: APPROVE\nFurther unresolved analysis follows.\n",
        b"VERDICT: APPROVE\nVERDICT: APPROVE\n",
        b"Review completed without a decision record.\n",
    ],
)
def test_review_result_requires_one_standalone_final_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review_body: bytes,
) -> None:
    receipt = _fixture(tmp_path, monkeypatch, review_body=review_body)

    with pytest.raises(publication.VendorConfigPublicationError, match="final.*APPROVE"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_receipt_model_must_match_fresh_fixed_receipt_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)
    forged = receipt.model_copy(update={"coordinator_recorded_at": "2026-10-13T10:00:00+00:00"})

    with pytest.raises(publication.VendorConfigPublicationError, match="fixed receipt bytes"):
        publication._verify_release_receipt(
            forged,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_reviewed_candidate_off_first_parent_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init", "-q")
    release = tmp_path / RELEASE
    release.parent.mkdir(parents=True)
    release.write_text("version: v2\nstate: RELEASED\n", encoding="utf-8")
    candidate = _commit(tmp_path, "candidate A")
    main_branch = _git(tmp_path, "branch", "--show-current")
    _git(tmp_path, "checkout", "-q", "-b", "reviewed-side")
    (tmp_path / "side.txt").write_text("side candidate\n", encoding="utf-8")
    _git(tmp_path, "add", "side.txt")
    _git(
        tmp_path,
        "-c",
        "user.name=Publication Test",
        "-c",
        "user.email=publication@example.invalid",
        "commit",
        "-m",
        "off-first-parent candidate",
    )
    side_candidate = _git(tmp_path, "rev-parse", "HEAD")
    assert side_candidate != candidate
    _git(tmp_path, "checkout", "-q", main_branch)
    (tmp_path / "main.txt").write_text("main history\n", encoding="utf-8")
    _git(tmp_path, "add", "main.txt")
    _git(
        tmp_path,
        "-c",
        "user.name=Publication Test",
        "-c",
        "user.email=publication@example.invalid",
        "commit",
        "-m",
        "main divergence",
    )
    receipt = _write_approval(tmp_path, side_candidate)
    _commit(tmp_path, "receipt C")
    monkeypatch.setattr(publication, "_REPOSITORY_ROOT", tmp_path)

    with pytest.raises(publication.VendorConfigPublicationError, match="first-parent"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_uncommitted_receipt_has_no_introduction_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init", "-q")
    release = tmp_path / RELEASE
    release.parent.mkdir(parents=True)
    release.write_text("version: v2\nstate: RELEASED\n", encoding="utf-8")
    candidate = _commit(tmp_path, "candidate A")
    receipt = _write_approval(tmp_path, candidate)
    monkeypatch.setattr(publication, "_REPOSITORY_ROOT", tmp_path)

    with pytest.raises(publication.VendorConfigPublicationError, match="unambiguous"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_preexisting_approval_records_cannot_become_introduction_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init", "-q")
    release = tmp_path / RELEASE
    release.parent.mkdir(parents=True)
    release.write_text("version: v2\nstate: RELEASED\n", encoding="utf-8")
    candidate = _commit(tmp_path, "candidate A")
    _write_approval(
        tmp_path,
        candidate,
        review_body=b"Earlier review\nVERDICT: APPROVE\n",
        recorded_at="2026-10-13T08:00:00+00:00",
    )
    _commit(tmp_path, "preexisting approval records")
    receipt = _write_approval(tmp_path, candidate)
    _commit(tmp_path, "replacement approval records")
    monkeypatch.setattr(publication, "_REPOSITORY_ROOT", tmp_path)

    with pytest.raises(publication.VendorConfigPublicationError, match="unambiguous"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_changed_then_restored_approval_records_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)
    receipt_body = (tmp_path / RECEIPT).read_bytes()
    review_body = (tmp_path / REVIEW).read_bytes()
    (tmp_path / RECEIPT).write_text("changed: true\n", encoding="utf-8")
    (tmp_path / REVIEW).write_text("changed review\n", encoding="utf-8")
    _commit(tmp_path, "replace approval records")
    (tmp_path / RECEIPT).write_bytes(receipt_body)
    (tmp_path / REVIEW).write_bytes(review_body)
    _commit(tmp_path, "restore approval records")

    with pytest.raises(publication.VendorConfigPublicationError, match="changed after approval"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


@pytest.mark.parametrize("path", [RECEIPT, REVIEW])
def test_dirty_approval_records_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)
    with (tmp_path / path).open("ab") as dirty:
        dirty.write(b"dirty\n")

    with pytest.raises(publication.VendorConfigPublicationError):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_dirty_selected_release_member_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)
    (tmp_path / RELEASE).write_text("version: v2\nstate: MODIFIED\n", encoding="utf-8")

    with pytest.raises(publication.VendorConfigPublicationError, match="selected-member digest"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_deleted_and_reintroduced_receipt_history_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _fixture(tmp_path, monkeypatch)
    receipt_body = (tmp_path / RECEIPT).read_bytes()
    review_body = (tmp_path / REVIEW).read_bytes()
    (tmp_path / RECEIPT).unlink()
    (tmp_path / REVIEW).unlink()
    _git(tmp_path, "add", "-u", RECEIPT, REVIEW)
    _git(
        tmp_path,
        "-c",
        "user.name=Publication Test",
        "-c",
        "user.email=publication@example.invalid",
        "commit",
        "-m",
        "delete approval records",
    )
    (tmp_path / RECEIPT).write_bytes(receipt_body)
    (tmp_path / REVIEW).write_bytes(review_body)
    _commit(tmp_path, "reintroduce approval records")

    with pytest.raises(publication.VendorConfigPublicationError, match="unambiguous"):
        publication._verify_release_receipt(
            receipt,
            version="v2",
            selected_paths=(RELEASE,),
            receipt_relative=RECEIPT,
        )


def test_released_authority_projects_exact_repository_decisions() -> None:
    a05 = REPO_ROOT / publication.A05_SUBSCRIBER_DECISION
    upstox = REPO_ROOT / publication.UPSTOX_ROLE_DECISION
    authority = publication.SourceAuthorityArtifact.model_validate(
        {
            "version": "v1",
            "use_boundary": publication.PRIVATE_SUBSCRIBER_BOUNDARY,
            "sources": [
                {
                    "source_id": "upstox",
                    "source_class": "derived",
                    "evidence_role": "diagnostic_only",
                    "classification_ref": publication.UPSTOX_ROLE_DECISION,
                    "classification_sha256": hashlib.sha256(upstox.read_bytes()).hexdigest(),
                }
            ],
            "surfaces": [
                {
                    "source_id": "screener-subscriber",
                    "surface": "SCREENER_FINANCIALS",
                    "representation": "HTML",
                    "evidence_role": "reconcilable",
                    "authority_ref": publication.A05_SUBSCRIBER_DECISION,
                    "authority_sha256": hashlib.sha256(a05.read_bytes()).hexdigest(),
                }
            ],
        }
    )

    assert publication._validate_authority_evidence(
        authority, state=publication.PublicationState.RELEASED
    ) == tuple(sorted((publication.A05_SUBSCRIBER_DECISION, publication.UPSTOX_ROLE_DECISION)))


def test_released_authority_rejects_unknown_rights_evidence() -> None:
    upstox = REPO_ROOT / publication.UPSTOX_ROLE_DECISION
    authority = publication.SourceAuthorityArtifact.model_validate(
        {
            "version": "v1",
            "use_boundary": publication.PRIVATE_SUBSCRIBER_BOUNDARY,
            "sources": [
                {
                    "source_id": "upstox",
                    "source_class": "derived",
                    "evidence_role": "diagnostic_only",
                    "classification_ref": publication.UPSTOX_ROLE_DECISION,
                    "classification_sha256": hashlib.sha256(upstox.read_bytes()).hexdigest(),
                }
            ],
            "surfaces": [
                {
                    "source_id": "screener-subscriber",
                    "surface": "SCREENER_FINANCIALS",
                    "representation": "HTML",
                    "evidence_role": "reconcilable",
                    "authority_ref": publication.UPSTOX_ROLE_DECISION,
                    "authority_sha256": hashlib.sha256(upstox.read_bytes()).hexdigest(),
                }
            ],
        }
    )

    with pytest.raises(publication.VendorConfigPublicationError, match="unknown rights"):
        publication._validate_authority_evidence(
            authority, state=publication.PublicationState.RELEASED
        )


@pytest.mark.parametrize("defect", ["root", "directory", "nonregular"])
def test_code_bundle_refuses_unsafe_path_components(tmp_path: Path, defect: str) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "member.py").write_text("VALUE = 1\n", encoding="utf-8")
    root = real
    relative = "member.py"
    if defect == "root":
        root = tmp_path / "linked-root"
        root.symlink_to(real, target_is_directory=True)
    elif defect == "directory":
        nested = real / "nested"
        nested.symlink_to(tmp_path, target_is_directory=True)
        relative = "nested/real/member.py"
    else:
        (real / "not-a-file").mkdir()
        relative = "not-a-file"

    with pytest.raises(publication.VendorConfigPublicationError, match="unsafe|symlink|regular"):
        publication.code_bundle_pin("v1", (relative,), source_root=root)


def test_code_bundle_never_reopens_a_descriptor_read_member_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"VALUE = 1\n"
    (tmp_path / "member.py").write_bytes(body)
    called = False

    def insecure_reopen(_path: Path) -> bytes:
        nonlocal called
        called = True
        raise AssertionError("descriptor-validated member was reopened by name")

    monkeypatch.setattr(Path, "read_bytes", insecure_reopen)

    pin = publication.code_bundle_pin("v1", ("member.py",), source_root=tmp_path)
    expected = hashlib.sha256(b"v1\0")
    expected.update(b"member.py\0")
    expected.update(hashlib.sha256(body).digest())

    assert pin.content_sha256 == expected.hexdigest()
    assert not called


def test_code_bundle_refuses_member_changed_during_descriptor_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = tmp_path / "member.py"
    member.write_text("VALUE = 1\n", encoding="utf-8")
    original_read = os.read
    changed = False

    def changing_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        body = original_read(descriptor, size)
        if body and not changed:
            changed = True
            member.write_text("VALUE = 200\n", encoding="utf-8")
        return body

    monkeypatch.setattr(os, "read", changing_read)

    with pytest.raises(publication.VendorConfigPublicationError, match="changed"):
        publication.code_bundle_pin("v1", ("member.py",), source_root=tmp_path)


def test_code_bundle_refuses_symlink_swapped_between_descriptor_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = tmp_path / "member.py"
    member.write_text("VALUE = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 2\n", encoding="utf-8")
    original_read = os.read
    reached_eof = False

    def swapping_read(descriptor: int, size: int) -> bytes:
        nonlocal reached_eof
        body = original_read(descriptor, size)
        if not body and not reached_eof:
            reached_eof = True
            member.unlink()
            member.symlink_to(outside)
        return body

    monkeypatch.setattr(os, "read", swapping_read)

    with pytest.raises(publication.VendorConfigPublicationError, match="unsafe|symlink"):
        publication.code_bundle_pin("v1", ("member.py",), source_root=tmp_path)
