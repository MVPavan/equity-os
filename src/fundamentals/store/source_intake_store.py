"""Metadata-only append-only ledger beside existing originals.

Only the trusted operator/producer writes this tree. Digests detect corruption;
they do not authenticate an imported receipt or resist operator rewrites.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import (
    CAPTURE_SCHEMA_VERSION,
    BodyCompleteness,
    CaptureRecord,
    RequestMethod,
    SnapshotError,
    canonical_json,
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
    SnapshotStore,
)

if TYPE_CHECKING:
    from fundamentals.api.source_intake import ApprovedIntakeContext


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SourceIntakeStore:
    def __init__(
        self, snapshot_store: SnapshotStore, *, approved_intake: ApprovedIntakeContext
    ) -> None:
        approved_intake.check_store(snapshot_store)
        self.snapshot_store = snapshot_store
        self.approved_intake = approved_intake

    def register_capture(
        self,
        *,
        role: SourceRole,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        source_sha256: str,
        record_sha256: str,
    ) -> SourceRegistration:
        return self._resolve(
            role=role,
            source_id=source_id,
            surface=surface,
            request_key=request_key,
            capture_id=capture_id,
            source_sha256=source_sha256,
            record_sha256=record_sha256,
            register=True,
        )[0]

    def get_registration(
        self,
        *,
        role: SourceRole,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        source_sha256: str,
        record_sha256: str,
    ) -> SourceRegistration:
        return self.resolve_verified(
            role=role,
            source_id=source_id,
            surface=surface,
            request_key=request_key,
            capture_id=capture_id,
            source_sha256=source_sha256,
            record_sha256=record_sha256,
        )[0]

    def resolve_verified(
        self,
        *,
        role: SourceRole,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        source_sha256: str,
        record_sha256: str,
    ) -> tuple[SourceRegistration, bytes]:
        """Return one verified receipt and immutable source buffer for Task 2."""
        return self._resolve(
            role=role,
            source_id=source_id,
            surface=surface,
            request_key=request_key,
            capture_id=capture_id,
            source_sha256=source_sha256,
            record_sha256=record_sha256,
            register=False,
        )

    def _resolve(
        self,
        *,
        role: SourceRole,
        source_id: str,
        surface: str,
        request_key: str,
        capture_id: str,
        source_sha256: str,
        record_sha256: str,
        register: bool,
    ) -> tuple[SourceRegistration, bytes]:
        binding = self.approved_intake.binding(role)
        if (source_id, source_sha256) != (binding.source_id, binding.expected_sha256):
            raise SourceRegistrationError("source/content differs from approved role binding")
        coordinates = dict(
            source_id=source_id, surface=surface, request_key=request_key, capture_id=capture_id
        )
        installed = dict(
            schema_version=1,
            **coordinates,
            role=role.value,
            source_sha256=source_sha256,
            record_sha256=record_sha256,
        )
        binding_id = canonical_sha256(coordinates)
        try:
            with DescriptorTree(self.approved_intake.store_anchor) as tree, tree.writer_lock():
                record, body = self.snapshot_store._read_from_tree(
                    tree, source_id, surface, request_key, capture_id, max_bytes=MAX_BODY_BYTES
                )
                completed = require_utc(_utc_now())
                if (
                    record.request.method is RequestMethod.LOCAL_READ
                    and completed < record.retrieved_at
                ):
                    raise SourceRegistrationError(
                        "producer clock moved backward after local completion"
                    )
                previous_sample = completed

                def sample_now() -> datetime:
                    nonlocal previous_sample
                    sampled = require_utc(_utc_now())
                    if sampled < previous_sample:
                        raise SourceRegistrationError("producer clock moved backward")
                    previous_sample = sampled
                    return sampled

                self._check_record(record, role, source_sha256, record_sha256, body)
                observed = sample_now()
                if observed < completed:
                    raise SourceRegistrationError("producer clock moved backward")
                directory = tree.descend(
                    (".source-intake", binding_id), create=register, private=True
                )
                installed_bytes = (canonical_json(installed) + "\n").encode()
                has_install = tree.exists(directory, "installed.json")
                has_receipt = tree.exists(directory, "registration.json")
                if has_install:
                    if (
                        tree.read(directory, "installed.json", MAX_METADATA_BYTES, private=True)
                        != installed_bytes
                    ):
                        raise SourceRegistrationError("capture slot is already bound differently")
                elif has_receipt or not register:
                    raise SourceRegistrationError("registration installation is missing")
                if has_receipt:
                    receipt = SourceRegistration.model_validate_json(
                        tree.read(directory, "registration.json", MAX_METADATA_BYTES, private=True)
                    )
                    for key, value in installed.items():
                        if getattr(receipt, key) != value:
                            raise SourceRegistrationError("receipt differs from installed binding")
                    if receipt.registered_at > sample_now():
                        raise SourceRegistrationError("registration is in the future")
                    again, pinned = self.snapshot_store._read_from_tree(
                        tree, source_id, surface, request_key, capture_id, MAX_BODY_BYTES
                    )
                    if again != record or pinned != body:
                        raise SourceRegistrationError("original changed during registration")
                    tree.flush()
                    # Reopening flushes .staging as the original rename's other parent too.
                    if tree.exists(tree.root, ".staging"):
                        tree.child(tree.root, ".staging")
                        tree.flush()
                    ceiling = sample_now()
                    if ceiling < observed or ceiling < receipt.registered_at:
                        raise SourceRegistrationError("producer clock moved backward during reopen")
                    tree.verify()
                    return receipt, body
                if not register:
                    raise SourceRegistrationError("installation alone is not registration proof")
                tree.flush()
                if tree.exists(tree.root, ".staging"):
                    tree.child(tree.root, ".staging")
                if not has_install:
                    tree.publish_file(directory, "installed.json", installed_bytes)
                else:
                    # Orphan recovery must make its observations after renewed durability.
                    tree.flush()
                    completed = sample_now()
                    observed = sample_now()
                again, pinned = self.snapshot_store._read_from_tree(
                    tree, source_id, surface, request_key, capture_id, MAX_BODY_BYTES
                )
                if again != record or pinned != body:
                    raise SourceRegistrationError("original changed during installation")
                tree.flush()
                registered = sample_now()
                if not completed <= observed <= registered:
                    raise SourceRegistrationError("producer clock moved backward")
                payload = dict(
                    **installed,
                    capture_completed_at=completed.isoformat().replace("+00:00", "Z"),
                    first_observed_at=observed.isoformat().replace("+00:00", "Z"),
                    registered_at=registered.isoformat().replace("+00:00", "Z"),
                )
                receipt = SourceRegistration.model_validate(
                    dict(payload, receipt_sha256=canonical_sha256(payload))
                )
                tree.publish_file(
                    directory,
                    "registration.json",
                    (canonical_json(receipt.model_dump(mode="json")) + "\n").encode(),
                )
                tree.flush()
                if registered > sample_now():
                    raise SourceRegistrationError("producer clock moved backward after publication")
                tree.verify()
                return receipt, body
        except SourceRegistrationError:
            raise
        except (OSError, SnapshotError, ValidationError) as error:
            raise SourceRegistrationError(f"registration refused: {error}") from error

    def _check_record(
        self,
        record: CaptureRecord,
        role: SourceRole,
        source_sha256: str,
        record_sha256: str,
        body: bytes,
    ) -> None:
        binding = self.approved_intake.binding(role)
        if (
            record.schema_version != CAPTURE_SCHEMA_VERSION
            or record.body_completeness is not BodyCompleteness.COMPLETE
            or record.outcome.code is not OutcomeCode.OK
            or not body
        ):
            raise SourceRegistrationError(
                "registration requires explicit v2 nonempty COMPLETE OK evidence"
            )
        if (
            record.record_sha256 != record_sha256
            or record.body is None
            or record.body.content_sha256 != source_sha256
            or record.rights != binding.rights
        ):
            raise SourceRegistrationError("record/content/rights differ from trusted binding")
