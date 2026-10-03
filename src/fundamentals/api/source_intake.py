"""Operator-only composition for approved local originals; no authority discovery.

Python/filesystem execution as the operator is trusted. These objects are not
JSON import contracts, model tools, source-use grants or hostile-admin controls.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fundamentals.api.config import FundamentalsConfig
from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    RequestMethod,
    SnapshotError,
    SnapshotRights,
    canonical_sha256,
)
from fundamentals.contracts.source_registration import (
    SourceRegistration,
    SourceRegistrationError,
    SourceRole,
    require_utc,
)
from fundamentals.store.snapshot_store import (
    MAX_BODY_BYTES,
    MAX_METADATA_BYTES,
    DescriptorTree,
    DirectoryAnchor,
    SnapshotStore,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ApprovedIntakeBinding:
    role: SourceRole
    source_id: str
    expected_sha256: str
    rights: SnapshotRights

    def __post_init__(self) -> None:
        if not isinstance(self.role, SourceRole) or not isinstance(self.rights, SnapshotRights):
            raise SourceRegistrationError("binding requires trusted runtime types")
        if (
            not self.source_id
            or self.source_id in (".", "..")
            or "/" in self.source_id
            or not re.fullmatch(r"[0-9a-f]{64}", self.expected_sha256)
        ):
            raise SourceRegistrationError("invalid exact source/content binding")


@dataclass(frozen=True)
class ApprovedIntakeContext:
    bindings: tuple[ApprovedIntakeBinding, ...]
    approved_config_sha256: str
    store_anchor: DirectoryAnchor
    input_anchor: DirectoryAnchor

    def __post_init__(self) -> None:
        if (
            not isinstance(self.bindings, tuple)
            or len(self.bindings) != 3
            or not all(isinstance(binding, ApprovedIntakeBinding) for binding in self.bindings)
            or {binding.role for binding in self.bindings} != set(SourceRole)
        ):
            raise SourceRegistrationError("context requires exactly three vetted role bindings")
        if not re.fullmatch(r"[0-9a-f]{64}", self.approved_config_sha256):
            raise SourceRegistrationError("context requires an approved configuration-byte digest")
        if not isinstance(self.store_anchor, DirectoryAnchor) or not isinstance(
            self.input_anchor, DirectoryAnchor
        ):
            raise SourceRegistrationError("context requires operator-pinned directories")

    def binding(self, role: SourceRole) -> ApprovedIntakeBinding:
        if not isinstance(role, SourceRole):
            raise SourceRegistrationError("role requires a trusted runtime SourceRole")
        for binding in self.bindings:
            if binding.role == role:
                return binding
        raise SourceRegistrationError("role is outside the approved context")

    def check_store(self, store: SnapshotStore) -> None:
        if store._root.absolute() != self.store_anchor.path:
            raise SourceRegistrationError("store differs from approved operator binding")
        if store._anchor is not None and store._anchor != self.store_anchor:
            raise SourceRegistrationError("store anchor differs from approved operator identity")
        try:
            with DescriptorTree(self.store_anchor) as tree:
                tree.verify()
        except (SnapshotError, OSError) as error:
            raise SourceRegistrationError(f"unsafe approved store: {error}") from error
        store._anchor = self.store_anchor


def stage_local_source(
    store: SnapshotStore, *, approved_intake: ApprovedIntakeContext, role: SourceRole, path: Path
) -> SourceRegistration:
    """Read one bounded pinned local original and register its honest v2 capture."""
    from fundamentals.store.source_intake_store import SourceIntakeStore

    approved_intake.check_store(store)
    binding = approved_intake.binding(role)
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise SourceRegistrationError("input must be relative to the operator-pinned directory")
    try:
        with DescriptorTree(approved_intake.input_anchor) as tree:
            parent = tree.descend(tuple(path.parts[:-1]))
            body = tree.read(parent, path.name, MAX_BODY_BYTES)
            if not body or hashlib.sha256(body).hexdigest() != binding.expected_sha256:
                raise SourceRegistrationError("local original differs from approved content pin")
            completed = require_utc(_utc_now())
            tree.verify()
        request = RequestIdentity(
            source_id=binding.source_id,
            surface=f"local_{role.value}",
            request_key=canonical_sha256({"role": role.value, "sha256": binding.expected_sha256}),
            method=RequestMethod.LOCAL_READ,
            parameters=(),
        )
        record = CaptureRecord.make(
            request=request,
            retrieved_at=completed,
            http_status=None,
            media_type="application/xml" if role is SourceRole.XBRL else "application/pdf",
            content_encoding=None,
            body=BlobRef(
                source_id=binding.source_id,
                content_sha256=binding.expected_sha256,
                byte_count=len(body),
            ),
            outcome=OutcomeRecord(
                code=OutcomeCode.OK, native_kind="LOCAL_READ", native_value="complete"
            ),
            rights=binding.rights,
            schema_version=CAPTURE_SCHEMA_VERSION,
            body_completeness=BodyCompleteness.COMPLETE,
            body_read_issue=None,
        )
        store.put_capture(record, body)
        return SourceIntakeStore(store, approved_intake=approved_intake).register_capture(
            role=role,
            source_id=binding.source_id,
            surface=request.surface,
            request_key=request.request_key,
            capture_id=record.capture_id,
            source_sha256=binding.expected_sha256,
            record_sha256=record.record_sha256,
        )
    except SourceRegistrationError:
        raise
    except (OSError, ValueError, SnapshotError) as error:
        # Snapshot refusals remain chained for the trusted operator; nothing is repaired.
        raise SourceRegistrationError(f"local source staging refused: {error}") from error


def load_approved_config(
    config_path: Path, *, approved_intake: ApprovedIntakeContext
) -> FundamentalsConfig:
    """Validate approved bytes with protected descriptors retained through parsing.

    The guarded interval starts after opening the directory descriptors, before
    reading, and ends at the final verification after model validation. Ancestor
    ctime is sampled only for this operation: concurrent directory changes,
    including unrelated entry changes, conservatively refuse without retry.
    These samples confer no persistent authority or temporal eligibility.
    """
    import yaml

    try:
        # Do not resolve: symlinks and non-plain ancestors must reach no-follow checks.
        with DescriptorTree(DirectoryAnchor(config_path.absolute().parent)) as tree:
            ancestor_changes = tuple((fd, os.fstat(fd).st_ctime_ns) for fd in tree.fds)
            payload = tree.read(tree.root, config_path.name, MAX_METADATA_BYTES)
            if hashlib.sha256(payload).hexdigest() != approved_intake.approved_config_sha256:
                raise SourceRegistrationError("configuration bytes differ from approved digest")

            def verify() -> None:
                tree.verify()
                # Restoring a directory inode cannot erase its operation-local change.
                for index, (fd, before_ctime) in enumerate(ancestor_changes):
                    if os.fstat(fd).st_ctime_ns != before_ctime:
                        raise SourceRegistrationError(
                            f"configuration ancestor changed during operation: "
                            f"{Path(*tree.anchor.path.parts[: index + 1])}"
                        )
                # A rename away and back changes ctime even if the original inode returns.
                for _, name, fd, before in tree.read_files:
                    if os.fstat(fd).st_ctime_ns != before.st_ctime_ns:
                        raise SourceRegistrationError(f"configuration changed during parse: {name}")

            verify()
            config = FundamentalsConfig.model_validate(yaml.safe_load(payload))
            verify()
            return config
    except (SnapshotError, OSError) as error:
        raise SourceRegistrationError(f"approved configuration read refused: {error}") from error


def register_sources(
    *,
    config_path: Path,
    manifest_path: Path,
    store_root: Path,
    out_manifest: Path,
    approved_intake: ApprovedIntakeContext | None,
) -> None:
    """Register three existing locators under independently approved runtime pins."""
    import uuid

    from fundamentals.api.source_admission import load_source_manifest
    from fundamentals.store.source_intake_store import SourceIntakeStore

    if approved_intake is None:
        raise SourceRegistrationError("trusted approved intake context required")
    store = SnapshotStore(store_root)
    approved_intake.check_store(store)
    config = load_approved_config(config_path, approved_intake=approved_intake)
    refs = load_source_manifest(manifest_path)
    # Preflight all independent pins before any individual receipt is issued.
    for role in SourceRole:
        ref = getattr(refs, role.value)
        binding = approved_intake.binding(role)
        configured = getattr(config, role.value)
        if ref.source_id != configured.source_id or (ref.source_id, ref.source_sha256) != (
            binding.source_id,
            binding.expected_sha256,
        ):
            raise SourceRegistrationError("source/content differs from approved role/configuration")
        if role is not SourceRole.XBRL and ref.source_sha256 != configured.sha256:
            raise SourceRegistrationError("PDF content differs from approved configuration")
    ledger = SourceIntakeStore(store, approved_intake=approved_intake)
    # Existing operator-protected output directory; no pathname writes after anchoring.
    with DescriptorTree(DirectoryAnchor(out_manifest.absolute().parent)) as tree:
        if tree.exists(tree.root, out_manifest.name):
            raise SourceRegistrationError("refusing to overwrite locator manifest")
        for role in SourceRole:
            ledger.register_capture(role=role, **getattr(refs, role.value).model_dump())
        tree.verify()
        locator = (refs.model_dump_json(indent=2) + "\n").encode()
        temporary = ".intake-locator-" + uuid.uuid4().hex
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=tree.root,
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(locator)
                stream.flush()
                os.fsync(stream.fileno())
                tree.verify()
                before = os.fstat(stream.fileno())
                opened = os.stat(temporary, dir_fd=tree.root, follow_symlinks=False)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    raise SourceRegistrationError("locator temporary was replaced")
                os.link(
                    temporary,
                    out_manifest.name,
                    src_dir_fd=tree.root,
                    dst_dir_fd=tree.root,
                    follow_symlinks=False,
                )
                installed = os.stat(out_manifest.name, dir_fd=tree.root, follow_symlinks=False)
                if (before.st_dev, before.st_ino) != (installed.st_dev, installed.st_ino):
                    raise SourceRegistrationError("locator publication was replaced")
                os.fsync(tree.root)
                tree.verify()
        finally:
            os.unlink(temporary, dir_fd=tree.root)
            os.fsync(tree.root)
