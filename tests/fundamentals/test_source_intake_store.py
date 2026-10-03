"""Private-safe local intake: current producer clocks and durable exact bindings."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from fundamentals.api.source_intake import (
    ApprovedIntakeBinding,
    ApprovedIntakeContext,
    stage_local_source,
)
from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import (
    BlobRef,
    BodyCompleteness,
    BodyReadIssue,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
    canonical_sha256,
)
from fundamentals.contracts.source_registration import SourceRegistrationError, SourceRole
from fundamentals.store.snapshot_store import DirectoryAnchor, SnapshotStore
from fundamentals.store.source_intake_store import SourceIntakeStore

BODY = b'<synthetic revenue="123" />\n'
HASH = hashlib.sha256(BODY).hexdigest()
OLD = datetime(2001, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)


def context(root: Path, inputs: Path, *, shared: bool = False) -> ApprovedIntakeContext:
    rights = SnapshotRights(authority_refs=("SYNTHETIC-PRIVATE-USE", "SYNTHETIC-SCOPE"))
    return ApprovedIntakeContext(
        bindings=tuple(
            ApprovedIntakeBinding(
                role=role,
                source_id="same" if shared else role.value,
                expected_sha256=HASH,
                rights=rights,
            )
            for role in SourceRole
        ),
        approved_config_sha256="c" * 64,
        store_anchor=DirectoryAnchor(root),
        input_anchor=DirectoryAnchor(inputs),
    )


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SnapshotStore, ApprovedIntakeContext]:
    import fundamentals.api.source_intake as api
    import fundamentals.store.source_intake_store as ledger

    root, inputs = tmp_path / "store", tmp_path / "inputs"
    root.mkdir(mode=0o700)
    inputs.mkdir(mode=0o700)
    (inputs / "source.xml").write_bytes(BODY)
    monkeypatch.setattr(api, "_utc_now", lambda: NOW)
    monkeypatch.setattr(ledger, "_utc_now", lambda: NOW)
    return SnapshotStore(root), context(root, inputs)


def capture(
    store: SnapshotStore,
    ctx: ApprovedIntakeContext,
    *,
    schema: int = 2,
    state: BodyCompleteness = BodyCompleteness.COMPLETE,
    outcome: OutcomeCode = OutcomeCode.OK,
    payload: bytes | None = BODY,
    rights: SnapshotRights | None = None,
) -> CaptureRecord:
    binding = ctx.binding(SourceRole.XBRL)
    record = CaptureRecord.make(
        request=RequestIdentity(
            source_id=binding.source_id, surface="synthetic", request_key="source"
        ),
        retrieved_at=OLD,
        http_status=200,
        media_type="application/xml",
        content_encoding=None,
        body=None
        if payload is None
        else BlobRef(
            source_id=binding.source_id,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        ),
        outcome=OutcomeRecord(code=outcome, native_kind="SYNTHETIC", native_value="test"),
        rights=rights or binding.rights,
        schema_version=schema,
        body_completeness=None if schema == 1 else state,
        body_read_issue=BodyReadIssue.READ_INTERRUPTED
        if state is BodyCompleteness.PARTIAL
        else None,
    )
    store.put_capture(record, payload)
    return record


def ref(record: CaptureRecord, *, role: SourceRole = SourceRole.XBRL) -> dict[str, Any]:
    return dict(
        role=role,
        source_id=record.request.source_id,
        surface=record.request.surface,
        request_key=record.request.request_key,
        capture_id=record.capture_id,
        source_sha256=HASH,
        record_sha256=record.record_sha256,
    )


def test_local_staging_is_current_complete_local_read_and_reopens(setup: Any) -> None:
    store, ctx = setup
    receipt = stage_local_source(
        store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
    )
    record, body = store.read_capture_verified(
        receipt.source_id, receipt.surface, receipt.request_key, receipt.capture_id
    )
    assert record.request.method.value == "LOCAL_READ"
    assert record.http_status is None and record.request.parameters == ()
    assert record.outcome.native_kind == "LOCAL_READ"
    assert record.schema_version == 2 and record.body_completeness is BodyCompleteness.COMPLETE
    assert record.retrieved_at == NOW and receipt.registered_at == NOW
    assert record.body_read_issue is None and record.content_encoding is None
    assert body == BODY
    restarted = SourceIntakeStore(SnapshotStore(store._root), approved_intake=ctx)
    assert restarted.get_registration(**ref(record)) == receipt
    assert restarted.resolve_verified(**ref(record)) == (receipt, BODY)
    ledger = store._root / ".source-intake" / receipt.binding_id
    assert ledger.stat().st_mode & 0o777 == 0o700
    assert (ledger / "registration.json").stat().st_mode & 0o777 == 0o600


def test_old_capture_claims_never_supply_registration_clocks(setup: Any) -> None:
    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    with pytest.raises(SourceRegistrationError):
        ledger.get_registration(**ref(record))
    receipt = ledger.register_capture(**ref(record))
    assert receipt.capture_completed_at == NOW
    assert receipt.first_observed_at == NOW and receipt.registered_at == NOW
    assert (
        store.get_capture(
            record.request.source_id, "synthetic", "source", record.capture_id
        ).retrieved_at
        == OLD
    )
    assert ledger.register_capture(**ref(record)) == receipt


@pytest.mark.parametrize(
    "schema,state,outcome,payload",
    [
        (1, BodyCompleteness.COMPLETE, OutcomeCode.OK, BODY),
        (2, BodyCompleteness.PARTIAL, OutcomeCode.TRANSPORT_ERROR, BODY),
        (2, BodyCompleteness.ABSENT, OutcomeCode.TRANSPORT_ERROR, None),
        (2, BodyCompleteness.COMPLETE, OutcomeCode.TRANSPORT_ERROR, BODY),
        (2, BodyCompleteness.COMPLETE, OutcomeCode.OK_EMPTY, BODY),
        (2, BodyCompleteness.COMPLETE, OutcomeCode.OK, b""),
    ],
)
def test_incomplete_legacy_failed_and_empty_captures_refuse(
    setup: Any, schema: int, state: BodyCompleteness, outcome: OutcomeCode, payload: bytes | None
) -> None:
    store, ctx = setup
    record = capture(store, ctx, schema=schema, state=state, outcome=outcome, payload=payload)
    with pytest.raises(SourceRegistrationError):
        SourceIntakeStore(store, approved_intake=ctx).register_capture(**ref(record))
    assert not (store._root / ".source-intake").exists()


def test_record_rights_require_ordered_exact_operator_representation(setup: Any) -> None:
    store, ctx = setup
    record = capture(
        store,
        ctx,
        rights=SnapshotRights(authority_refs=("SYNTHETIC-SCOPE", "SYNTHETIC-PRIVATE-USE")),
    )
    with pytest.raises(SourceRegistrationError, match="rights"):
        SourceIntakeStore(store, approved_intake=ctx).register_capture(**ref(record))


@pytest.mark.parametrize("kind", ["fifo", "socket", "directory", "symlink"])
def test_nonregular_local_inputs_refuse_without_waiting(setup: Any, kind: str) -> None:
    store, ctx = setup
    path = ctx.input_anchor.path / "bad"
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "socket":
        os.mknod(path, stat.S_IFSOCK | 0o600)
    elif kind == "directory":
        path.mkdir()
    else:
        path.symlink_to(ctx.input_anchor.path / "source.xml")
    with pytest.raises(SourceRegistrationError):
        stage_local_source(store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("bad"))
    assert not (store._root / ".source-intake").exists()


@pytest.mark.parametrize("target", ["registration.json", "installed.json", "blob", "record"])
def test_corruption_refuses_without_repair(setup: Any, target: str) -> None:
    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    receipt = ledger.register_capture(**ref(record))
    if target == "blob":
        path = store._root / "blobs" / receipt.source_id / HASH[:2] / HASH
    elif target == "record":
        path = (
            store._root
            / receipt.source_id
            / receipt.surface
            / receipt.request_key
            / receipt.capture_id
            / "record.json"
        )
    else:
        path = store._root / ".source-intake" / receipt.binding_id / target
    path.write_bytes(b"corrupt")
    with pytest.raises(SourceRegistrationError):
        ledger.get_registration(**ref(record))
    assert path.read_bytes() == b"corrupt"


def test_clock_naive_backward_and_future_reopen_refuse(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.source_intake_store as module

    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW.replace(tzinfo=None))
    with pytest.raises(SourceRegistrationError, match="UTC"):
        ledger.register_capture(**ref(record))
    times = iter((NOW, NOW - timedelta(seconds=1)))
    monkeypatch.setattr(module, "_utc_now", lambda: next(times))
    with pytest.raises(SourceRegistrationError, match="backward"):
        ledger.register_capture(**ref(record))
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    ledger.register_capture(**ref(record))
    monkeypatch.setattr(module, "_utc_now", lambda: NOW - timedelta(seconds=1))
    with pytest.raises(SourceRegistrationError, match="future"):
        ledger.get_registration(**ref(record))


def test_installation_orphan_remains_unavailable_and_recovers_currently(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.snapshot_store as disk
    import fundamentals.store.source_intake_store as clock

    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    link = disk.os.link

    def fail_receipt(src: Any, dst: Any, **kwargs: Any) -> None:
        if dst == "registration.json":
            raise OSError("synthetic receipt publication failure")
        link(src, dst, **kwargs)

    monkeypatch.setattr(disk.os, "link", fail_receipt)
    with pytest.raises(SourceRegistrationError):
        ledger.register_capture(**ref(record))
    monkeypatch.setattr(disk.os, "link", link)
    with pytest.raises(SourceRegistrationError, match="installation alone"):
        ledger.get_registration(**ref(record))
    monkeypatch.setattr(clock, "_utc_now", lambda: NOW + timedelta(seconds=10))
    receipt = ledger.register_capture(**ref(record))
    assert receipt.registered_at == NOW + timedelta(seconds=10)
    assert receipt.capture_completed_at == NOW + timedelta(seconds=10)


def test_orphan_recovery_clock_rollback_refuses_before_receipt_publication(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.api.source_intake as api
    import fundamentals.store.snapshot_store as disk
    import fundamentals.store.source_intake_store as clock

    store, ctx = setup
    link = disk.os.link

    def fail_receipt(src: Any, dst: Any, **kwargs: Any) -> None:
        if dst == "registration.json":
            raise OSError("synthetic receipt publication failure")
        link(src, dst, **kwargs)

    monkeypatch.setattr(api, "_utc_now", lambda: NOW + timedelta(seconds=10))
    monkeypatch.setattr(clock, "_utc_now", lambda: NOW + timedelta(seconds=12))
    monkeypatch.setattr(disk.os, "link", fail_receipt)
    with pytest.raises(SourceRegistrationError, match="receipt publication failure"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    monkeypatch.setattr(disk.os, "link", link)
    (record,) = store.list_captures(
        "xbrl", "local_xbrl", canonical_sha256({"role": "xbrl", "sha256": HASH})
    )
    assert record.retrieved_at == NOW + timedelta(seconds=10)
    (installed,) = (store._root / ".source-intake").glob("*/installed.json")
    original_installation = installed.read_bytes()
    receipt_path = installed.with_name("registration.json")
    assert not receipt_path.exists()
    restarted = SourceIntakeStore(SnapshotStore(store._root), approved_intake=ctx)
    with pytest.raises(SourceRegistrationError, match="installation alone"):
        restarted.get_registration(**ref(record))

    # Actual samples: LOCAL_READ 10; initial 11/12; recovery 1/2; final 3/4.
    samples = iter(NOW + timedelta(seconds=s) for s in (11, 12, 1, 2, 3, 4))
    monkeypatch.setattr(clock, "_utc_now", lambda: next(samples))
    with pytest.raises(SourceRegistrationError, match="backward"):
        restarted.register_capture(**ref(record))
    assert not receipt_path.exists()
    assert installed.read_bytes() == original_installation
    assert store.read_body(record) == BODY


def test_receipt_with_self_consistent_future_digest_refuses(setup: Any) -> None:
    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    receipt = ledger.register_capture(**ref(record))
    path = store._root / ".source-intake" / receipt.binding_id / "registration.json"
    data = json.loads(path.read_bytes())
    data["registered_at"] = "2030-01-01T00:00:00Z"
    data["receipt_sha256"] = canonical_sha256(
        {k: v for k, v in data.items() if k != "receipt_sha256"}
    )
    path.write_text(json.dumps(data))
    with pytest.raises(SourceRegistrationError, match="future"):
        ledger.get_registration(**ref(record))


def _register_process(
    root: str, inputs: str, record_data: str, role: str, barrier: Any, queue: Any
) -> None:
    store = SnapshotStore(Path(root))
    ctx = context(Path(root), Path(inputs), shared=True)
    record = CaptureRecord.model_validate_json(record_data)
    barrier.wait(timeout=5)
    try:
        receipt = SourceIntakeStore(store, approved_intake=ctx).register_capture(
            **ref(record, role=SourceRole(role))
        )
        queue.put(("ok", receipt.receipt_sha256))
    except SourceRegistrationError as error:
        queue.put(("refused", str(error)))


@pytest.mark.parametrize("conflict", [False, True])
def test_two_processes_identical_or_conflicting_registration(setup: Any, conflict: bool) -> None:
    store, old_ctx = setup
    ctx = context(store._root, old_ctx.input_anchor.path, shared=True)
    record = capture(store, ctx)
    mp = multiprocessing.get_context("spawn")
    barrier, queue = mp.Barrier(2), mp.Queue()
    roles = ["xbrl", "results_pdf" if conflict else "xbrl"]
    processes = [
        mp.Process(
            target=_register_process,
            args=(
                str(store._root),
                str(ctx.input_anchor.path),
                record.model_dump_json(),
                role,
                barrier,
                queue,
            ),
        )
        for role in roles
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert not process.is_alive() and process.exitcode == 0
    results = [queue.get(timeout=1), queue.get(timeout=1)]
    if conflict:
        assert sorted(value[0] for value in results) == ["ok", "refused"]
    else:
        assert results[0] == results[1] and results[0][0] == "ok"


def test_stat_open_fifo_swap_refuses_before_any_data_read(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    path = ctx.input_anchor.path / "source.xml"
    original_open, original_read = disk.os.open, disk.os.read
    opened_fifo = False
    fifo_descriptor = -1

    def open_file(name: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal opened_fifo, fifo_descriptor
        if name == "source.xml" and "dir_fd" in kwargs:
            path.unlink()
            os.mkfifo(path)
            assert flags & os.O_NONBLOCK and flags & os.O_NOFOLLOW
            opened_fifo = True
            fifo_descriptor = original_open(name, flags, *args, **kwargs)
            return fifo_descriptor
        return original_open(name, flags, *args, **kwargs)

    def read_file(fd: int, count: int) -> bytes:
        assert fd != fifo_descriptor, "nonregular input reached a data read"
        return original_read(fd, count)

    monkeypatch.setattr(disk.os, "open", open_file)
    monkeypatch.setattr(disk.os, "read", read_file)
    with pytest.raises(SourceRegistrationError, match="nonregular"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    assert opened_fifo


@pytest.mark.parametrize("target", ["input", "record", "body", "receipt", "root"])
def test_symlink_substitution_of_each_authoritative_read_refuses(setup: Any, target: str) -> None:
    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    receipt = ledger.register_capture(**ref(record))
    if target == "input":
        path = ctx.input_anchor.path / "source.xml"
    elif target == "receipt":
        path = store._root / ".source-intake" / receipt.binding_id / "registration.json"
    elif target == "root":
        path = store._root
    else:
        path = (
            store._root
            / receipt.source_id
            / receipt.surface
            / receipt.request_key
            / receipt.capture_id
            / ("record.json" if target == "record" else "body.bin")
        )
    moved = path.with_name(path.name + ".original")
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=target == "root")
    with pytest.raises(SourceRegistrationError):
        if target == "input":
            stage_local_source(
                store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
            )
        else:
            ledger.get_registration(**ref(record))


@pytest.mark.parametrize("kind", ["body", "metadata", "growing"])
def test_bounded_files_and_cap_plus_one_growth_refuse(
    setup: Any, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    record = capture(store, ctx)
    ledger = SourceIntakeStore(store, approved_intake=ctx)
    if kind == "metadata":
        path = (
            store._root
            / record.request.source_id
            / "synthetic"
            / "source"
            / record.capture_id
            / "record.json"
        )
        with path.open("wb") as handle:
            handle.truncate(64 * 1024 + 1)
        with pytest.raises(SourceRegistrationError, match="oversize"):
            ledger.register_capture(**ref(record))
        return
    path = ctx.input_anchor.path / "source.xml"
    if kind == "body":
        with path.open("wb") as handle:
            handle.truncate(32 * 1024 * 1024 + 1)
    else:
        original_read = disk.os.read
        did_grow = False

        def read(fd: int, count: int) -> bytes:
            nonlocal did_grow
            if not did_grow and os.readlink(f"/proc/self/fd/{fd}") == str(path):
                did_grow = True
                with path.open("ab") as handle:
                    handle.truncate(32 * 1024 * 1024 + 1)
            return original_read(fd, count)

        monkeypatch.setattr(disk.os, "read", read)
    with pytest.raises(SourceRegistrationError, match="oversize"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )


def test_protected_context_store_and_content_mismatch_issue_no_receipt(
    setup: Any, tmp_path: Path
) -> None:
    store, ctx = setup
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    with pytest.raises(SourceRegistrationError, match="store"):
        stage_local_source(
            SnapshotStore(other), approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    (ctx.input_anchor.path / "source.xml").write_bytes(b"different approved-looking content")
    with pytest.raises(SourceRegistrationError, match="content"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    store._root.chmod(0o777)
    with pytest.raises(SourceRegistrationError):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    assert not (store._root / ".source-intake").exists()


def test_every_fsync_failure_refuses_and_uncertain_publication_reopens(
    setup: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail every observed durability syscall in a real local staging operation."""
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    original_fsync = disk.os.fsync
    calls: list[str] = []

    def observed(fd: int) -> None:
        calls.append(os.readlink(f"/proc/self/fd/{fd}"))
        original_fsync(fd)

    monkeypatch.setattr(disk.os, "fsync", observed)
    stage_local_source(store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml"))
    assert any("installed.json" in name or ".tmp-" in name for name in calls)
    count = len(calls)
    receipts_seen = 0
    for failure_at in range(count):
        root = tmp_path / f"failure-{failure_at}"
        root.mkdir(mode=0o700)
        trial = SnapshotStore(root)
        trial_ctx = context(root, ctx.input_anchor.path)
        counter = 0

        def fail_one(fd: int, failure_at: int = failure_at) -> None:
            nonlocal counter
            current = counter
            counter += 1
            if current == failure_at:
                raise OSError(f"synthetic fsync failure #{failure_at}")
            original_fsync(fd)

        monkeypatch.setattr(disk.os, "fsync", fail_one)
        with pytest.raises(SourceRegistrationError, match="fsync failure"):
            stage_local_source(
                trial, approved_intake=trial_ctx, role=SourceRole.XBRL, path=Path("source.xml")
            )
        monkeypatch.setattr(disk.os, "fsync", original_fsync)
        files = list((root / ".source-intake").glob("*/registration.json"))
        if files:
            receipts_seen += 1
            from fundamentals.contracts.source_registration import SourceRegistration

            published = SourceRegistration.model_validate_json(files[0].read_bytes())
            reopened = SourceIntakeStore(trial, approved_intake=trial_ctx).get_registration(
                role=published.role,
                source_id=published.source_id,
                surface=published.surface,
                request_key=published.request_key,
                capture_id=published.capture_id,
                source_sha256=published.source_sha256,
                record_sha256=published.record_sha256,
            )
            assert reopened == published
    assert receipts_seen > 0
    print(
        f"durability injection: {count} fsync boundaries, "
        f"{receipts_seen} published receipts safely reopened"
    )


def test_character_device_swap_is_refused_before_read(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    original_open, original_read = disk.os.open, disk.os.read
    device_fd = -1

    def open_file(name: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal device_fd
        if name == "source.xml" and "dir_fd" in kwargs:
            device_fd = original_open("/dev/null", flags)
            return device_fd
        return original_open(name, flags, *args, **kwargs)

    def read_file(fd: int, count: int) -> bytes:
        assert fd != device_fd, "device reached a data read"
        return original_read(fd, count)

    monkeypatch.setattr(disk.os, "open", open_file)
    monkeypatch.setattr(disk.os, "read", read_file)
    with pytest.raises(SourceRegistrationError, match="nonregular"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    assert device_fd >= 0


@pytest.mark.parametrize("target", ["source.xml", "record.json", "body.bin"])
def test_aba_read_keeps_original_pinned_bytes_or_refuses(
    setup: Any, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    record = capture(store, ctx)
    original_read = disk.os.read
    swapped = False

    def read(fd: int, count: int) -> bytes:
        nonlocal swapped
        path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        if not swapped and path.name == target:
            swapped = True
            held = path.with_name(path.name + ".held")
            path.rename(held)
            path.write_bytes(b"substituted bytes")
            data = original_read(fd, count)
            path.unlink()
            held.rename(path)
            return data
        return original_read(fd, count)

    monkeypatch.setattr(disk.os, "read", read)
    try:
        if target == "source.xml":
            receipt = stage_local_source(
                store, approved_intake=ctx, role=SourceRole.XBRL, path=Path(target)
            )
            _, body = store.read_capture_verified(
                receipt.source_id, receipt.surface, receipt.request_key, receipt.capture_id
            )
        else:
            _, body = store.read_capture_verified(
                record.request.source_id, "synthetic", "source", record.capture_id
            )
        assert body == BODY
    except (SourceRegistrationError, disk.IntegrityError):
        pass
    assert swapped


def test_deadline_expiry_refuses_bounded_local_read(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    ticks = iter((0.0, 6.0))
    monkeypatch.setattr(disk.time, "monotonic", lambda: next(ticks))
    with pytest.raises(SourceRegistrationError, match="budget"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )


def test_receipt_temp_substitution_refuses_durable_success(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fundamentals.store.snapshot_store as disk

    store, ctx = setup
    record = capture(store, ctx)
    original_link = disk.os.link

    def link(src: Any, dst: Any, **kwargs: Any) -> None:
        if dst == "registration.json":
            parent = kwargs["src_dir_fd"]
            os.unlink(src, dir_fd=parent)
            os.symlink("installed.json", src, dir_fd=parent)
        original_link(src, dst, **kwargs)

    monkeypatch.setattr(disk.os, "link", link)
    with pytest.raises(SourceRegistrationError, match="publication"):
        SourceIntakeStore(store, approved_intake=ctx).register_capture(**ref(record))


def test_registered_bound_follows_original_installation_and_all_parent_flushes(
    setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.store.snapshot_store as disk
    import fundamentals.store.source_intake_store as clock

    store, ctx = setup
    record = capture(store, ctx)
    flushed: list[tuple[int, int]] = []
    original_fsync = disk.os.fsync
    at_registered: list[tuple[int, int]] = []
    clock_calls = 0

    def fsync(fd: int) -> None:
        info = os.fstat(fd)
        original_fsync(fd)
        flushed.append((info.st_dev, info.st_ino))

    def now() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls == 3:
            at_registered.extend(flushed)
        return NOW + timedelta(seconds=clock_calls)

    monkeypatch.setattr(disk.os, "fsync", fsync)
    monkeypatch.setattr(clock, "_utc_now", now)
    receipt = SourceIntakeStore(store, approved_intake=ctx).register_capture(**ref(record))
    assert receipt.registered_at == NOW + timedelta(seconds=3)
    root = store._root
    directories = [
        root / "xbrl" / "synthetic" / "source" / record.capture_id,
        root / "xbrl" / "synthetic" / "source",
        root / "xbrl" / "synthetic",
        root / "xbrl",
        root / "blobs" / "xbrl" / HASH[:2],
        root / "blobs" / "xbrl",
        root / "blobs",
        root / ".staging",
        root / ".source-intake" / receipt.binding_id,
        root / ".source-intake",
        root,
    ]
    for child in directories:
        child_info, parent_info = child.stat(), child.parent.stat()
        child_identity = (child_info.st_dev, child_info.st_ino)
        parent_identity = (parent_info.st_dev, parent_info.st_ino)
        child_index = at_registered.index(child_identity)
        assert parent_identity in at_registered[child_index + 1 :], child
    for path in (
        directories[0] / "record.json",
        root / "blobs" / "xbrl" / HASH[:2] / HASH,
        root / ".source-intake" / receipt.binding_id / "installed.json",
    ):
        info = path.stat()
        assert (info.st_dev, info.st_ino) in at_registered


def test_clock_backward_between_local_completion_and_registration_refuses(
    setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.store.source_intake_store as clock

    store, ctx = setup
    monkeypatch.setattr(clock, "_utc_now", lambda: NOW - timedelta(seconds=1))
    with pytest.raises(SourceRegistrationError, match="backward"):
        stage_local_source(
            store, approved_intake=ctx, role=SourceRole.XBRL, path=Path("source.xml")
        )
    assert not (store._root / ".source-intake").exists()
