"""Acceptance tests for the snapshot store (Phase 3, S2).

The seam is a capture-record contract (``fundamentals.contracts.snapshot``) plus
one filesystem store (``fundamentals.store.snapshot_store``) that publishes the
record last, hard-links content-addressed bodies, and verifies every byte it
hands back. What it protects is evidence: a capture silently overwritten,
truncated or half-published is worse than no capture at all.

Nothing here touches the network; every timestamp, byte string and outcome is
synthetic. The modules under test do not exist yet, so each test imports them at
call time, which keeps collection green and puts the failure inside the test
that names the behaviour.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_upstox_scope_guards import _imported_modules

from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord

SOURCE_ID = "synthetic_source"
SURFACE = "financials"
REQUEST_KEY = "SYNTH-0001"
SYNTHETIC_BODY = b'{"synthetic": true}\n'
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
RETRIEVED_AT = datetime(2027, 1, 15, 10, 20, 30, 123456, tzinfo=UTC)
CAPTURE_ID_PREFIX = "20270115T102030.123456Z"
OUTCOME = OutcomeRecord(code=OutcomeCode.OK, native_kind="synthetic.Kind", native_value="OK")

LANES = ("ingest", "store", "reconcile", "api")
CONTRACT_BARRED = tuple(f"fundamentals.{lane}" for lane in LANES)
STORE_BARRED = ("fundamentals.api", "fundamentals.reconcile", "fundamentals.store.fact_store")


def _at(seconds: int) -> datetime:
    """The fixed synthetic capture time, advanced for a second attempt."""
    return RETRIEVED_AT + timedelta(seconds=seconds)


def _rights() -> Any:
    """The only rights a Screener/Tijori capture may carry."""
    from fundamentals.contracts import snapshot

    return snapshot.SnapshotRights(authority_refs=(snapshot.A05_DECISION_005,))


def _request(request_key: str = REQUEST_KEY, parameters: tuple[Any, ...] = ()) -> Any:
    """One synthetic route identity."""
    from fundamentals.contracts import snapshot

    return snapshot.RequestIdentity(
        source_id=SOURCE_ID, surface=SURFACE, request_key=request_key, parameters=parameters
    )


def _record(
    payload: bytes | None = SYNTHETIC_BODY,
    *,
    seconds: int = 0,
    http_status: int | None = 200,
    media_type: str | None = "application/json",
    content_encoding: str | None = None,
) -> Any:
    """A valid ``CaptureRecord`` whose ``capture_id`` the contract derives."""
    from fundamentals.contracts import snapshot

    body = (
        None
        if payload is None
        else snapshot.BlobRef(
            source_id=SOURCE_ID,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
    )
    return snapshot.CaptureRecord.make(
        request=_request(),
        retrieved_at=_at(seconds),
        http_status=http_status,
        media_type=media_type,
        content_encoding=content_encoding,
        body=body,
        outcome=OUTCOME,
        rights=_rights(),
    )


def _store(root: Path) -> Any:
    """A store rooted at a throwaway directory."""
    from fundamentals.store import snapshot_store

    return snapshot_store.SnapshotStore(root=root)


def _route(root: Path) -> Path:
    """The directory that IS the request index for the synthetic route."""
    return root / SOURCE_ID / SURFACE / REQUEST_KEY


def _blob_files(root: Path) -> list[Path]:
    """Every content-addressed blob under the store root."""
    return sorted(path for path in (root / "blobs").rglob("*") if path.is_file())


def _secret_refusal(build: Any) -> BaseException:
    """The ``SecretParameterError`` a refusal carries, raw or wrapped by pydantic."""
    from fundamentals.contracts import snapshot

    try:
        build()
    except snapshot.SecretParameterError as raw:
        return raw
    except ValidationError as wrapped:
        causes = [entry.get("ctx", {}).get("error") for entry in wrapped.errors()]
        typed = [cause for cause in causes if isinstance(cause, snapshot.SecretParameterError)]
        assert typed, wrapped.errors()
        return typed[0]
    raise AssertionError("the secret-shaped parameter was accepted")


def test_identical_bytes_on_two_attempts_share_one_blob_and_keep_both_records(
    tmp_path: Path,
) -> None:
    """Attempt history is evidence; identical bytes are not two facts.

    A second attempt that overwrote the first would lose the proof we asked
    twice and got the same answer — the only thing separating a stale vendor
    page from one we never re-checked. Dedupe makes that history affordable.
    """
    store = _store(tmp_path)
    first = _record(seconds=0)
    second = _record(seconds=1)
    store.put_capture(first, SYNTHETIC_BODY)
    store.put_capture(second, SYNTHETIC_BODY)

    assert first.capture_id != second.capture_id
    assert len(_blob_files(tmp_path)) == 1
    capture_dirs = sorted(path.name for path in _route(tmp_path).iterdir() if path.is_dir())
    assert capture_dirs == sorted([first.capture_id, second.capture_id])
    assert store.read_body(first) == SYNTHETIC_BODY
    assert store.read_body(second) == SYNTHETIC_BODY


def test_republishing_a_capture_id_is_idempotent_but_a_changed_record_conflicts(
    tmp_path: Path,
) -> None:
    """A retried publish must be safe; a contradicting one must never be.

    The writing command can crash between the blob and the record, so a re-run
    must converge rather than fail. But one ``capture_id`` carrying a different
    outcome is two claims about one moment, and keeping either silently leaves
    a record no reader can trust to be the one that was sealed.
    """
    from fundamentals.contracts import snapshot

    store = _store(tmp_path)
    record = _record()
    store.put_capture(record, SYNTHETIC_BODY)
    again = store.put_capture(record, SYNTHETIC_BODY)
    assert again.record_sha256 == record.record_sha256
    assert len([path for path in _route(tmp_path).iterdir() if path.is_dir()]) == 1

    conflicting = _record(http_status=500)
    assert conflicting.capture_id == record.capture_id
    with pytest.raises(snapshot.CaptureConflictError):
        store.put_capture(conflicting, SYNTHETIC_BODY)
    on_disk = json.loads((_route(tmp_path) / record.capture_id / "record.json").read_text())
    assert on_disk["http_status"] == 200


def test_a_crash_before_the_final_publish_leaves_no_readable_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A half-written capture read as whole is the worst failure this store has.

    A directory holding a body but no record, listed as a capture, presents
    bytes nobody sealed an outcome for. Publishing the record last by an atomic
    rename leaves at worst an orphan blob, which claims nothing.
    """
    from fundamentals.store import snapshot_store

    def _crash(*args: Any, **kwargs: Any) -> None:
        raise OSError("simulated crash before the record is published")

    store = _store(tmp_path)
    record = _record()
    monkeypatch.setattr(snapshot_store.os, "rename", _crash)
    with pytest.raises(OSError, match="simulated crash"):
        store.put_capture(record, SYNTHETIC_BODY)

    assert store.list_captures(SOURCE_ID, SURFACE, REQUEST_KEY) == ()
    published = [path for path in tmp_path.rglob("record.json") if ".staging" not in path.parts]
    assert published == []
    assert len(_blob_files(tmp_path)) == 1


def test_a_body_that_does_not_match_its_hash_is_refused_on_write_and_on_read(
    tmp_path: Path,
) -> None:
    """The hash is the only thing that makes a retained body evidence.

    Bytes on disk decay, and a reader trusting the path instead of the digest
    would hand a reconciler a body the record does not describe — a mismatch
    then blamed on the vendor. Verifying on read keeps that failure local.
    """
    from fundamentals.contracts import snapshot

    store = _store(tmp_path)
    record = _record()
    store.put_capture(record, SYNTHETIC_BODY)
    blob = _blob_files(tmp_path)[0]
    blob.chmod(0o644)
    blob.write_bytes(b'{"synthetic": tampered}\n')
    with pytest.raises(snapshot.IntegrityError):
        store.read_body(record)

    second_root = tmp_path / "second"
    mismatched = _record(seconds=1)
    with pytest.raises(snapshot.IntegrityError):
        _store(second_root).put_capture(mismatched, b"different synthetic bytes")
    assert list(second_root.rglob("record.json")) == []


def test_a_symlinked_component_and_a_traversing_request_key_are_refused(
    tmp_path: Path,
) -> None:
    """The store writes paths built from vendor-shaped strings.

    A ``request_key`` is a directory name, so anything that climbs out of the
    root — ``../``, or a component replaced with a symlink — turns a write into
    a write anywhere reachable and a read into an exfiltration. Refused, not
    sanitised: a rewritten path files a capture under a false identity.
    """
    from fundamentals.contracts import snapshot

    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / SOURCE_ID).symlink_to(outside, target_is_directory=True)
    with pytest.raises(snapshot.UnsafePathError):
        _store(root).put_capture(_record(), SYNTHETIC_BODY)

    with pytest.raises(ValidationError):
        _request(request_key="../x")


def test_secret_shaped_parameters_are_refused_and_the_request_hash_is_stable() -> None:
    """A request identity is stored and read back; a session cookie must never be.

    A subscriber session's CSRF token or bearer would make every capture a
    credential at rest, replayable by anyone who can read the tree. The hash
    must also be a function of the route alone — unstable, it splits one
    request into many for dedupe and for every later coverage reference.
    """
    from fundamentals.contracts import snapshot

    _secret_refusal(lambda: snapshot.RequestParameter(name="csrfmiddlewaretoken", value="x"))
    _secret_refusal(lambda: snapshot.RequestParameter(name="basis", value="A1b2C3d4" * 6))

    ordinary = snapshot.RequestParameter(name="basis", value="consolidated")
    changed = snapshot.RequestParameter(name="basis", value="standalone")
    stable = _request(parameters=(ordinary,)).request_sha256
    assert stable == _request(parameters=(ordinary,)).request_sha256
    assert stable != _request(parameters=(changed,)).request_sha256


def test_gzip_bytes_round_trip_and_an_absent_body_stays_distinct_from_an_empty_one(
    tmp_path: Path,
) -> None:
    """An absent body and a zero-byte body are different findings.

    A payload decoded on the way in could never be re-hashed against what the
    vendor sent. And an attempt that returned nothing is evidence of a refusal,
    a zero-byte response evidence the route is empty; collapsing the two erases
    the distinction coverage is built on.
    """
    from fundamentals.contracts import snapshot

    store = _store(tmp_path)
    compressed = gzip.compress(SYNTHETIC_BODY)
    gzipped = _record(compressed, content_encoding="gzip")
    store.put_capture(gzipped, compressed)
    names = sorted(path.name for path in (_route(tmp_path) / gzipped.capture_id).iterdir())
    assert "body.gz" in names
    assert store.read_body(gzipped) == compressed

    absent = _record(None, seconds=1)
    store.put_capture(absent, None)
    assert absent.capture_id.endswith("-nobody")
    with pytest.raises(snapshot.MissingSnapshotError):
        store.read_body(absent)

    empty = _record(b"", seconds=2)
    store.put_capture(empty, b"")
    assert empty.body.byte_count == 0
    assert empty.body.content_sha256 == EMPTY_SHA256
    assert empty.capture_id != absent.capture_id
    assert store.read_body(empty) == b""


def test_list_captures_is_time_ordered_and_never_lists_unpublished_work(
    tmp_path: Path,
) -> None:
    """Listing a route is how a reader finds the latest capture of a page.

    "Latest" must mean latest — an out-of-order listing hands a reconciler a
    stale body. A directory with no ``record.json`` is a crash remnant and
    ``.staging`` is in progress; either presents an unsealed capture as real.
    """
    store = _store(tmp_path)
    payloads = {n: f'{{"synthetic": {n}}}\n'.encode() for n in (2, 0, 1)}
    records = {n: _record(payload, seconds=n) for n, payload in payloads.items()}
    for number, record in records.items():
        store.put_capture(record, payloads[number])

    (_route(tmp_path) / f"{CAPTURE_ID_PREFIX}-000000000000").mkdir()
    staging = tmp_path / ".staging" / "leftover"
    staging.mkdir(parents=True)
    (staging / "record.json").write_bytes(
        (_route(tmp_path) / records[0].capture_id / "record.json").read_bytes()
    )

    listed = store.list_captures(SOURCE_ID, SURFACE, REQUEST_KEY)
    assert [record.capture_id for record in listed] == sorted(
        record.capture_id for record in records.values()
    )


def test_capture_id_binds_the_retrieved_timestamp_to_the_body_hash() -> None:
    """The id is the store's primary key, so it may not be assignable by hand.

    Derived, it is self-checking: a record filed under a mistyped id — or one
    whose naive timestamp is ambiguous about the hour it names — cannot be
    constructed. A hand-set id lets two attempts collide silently.
    """
    from fundamentals.contracts import snapshot

    record = _record()
    digest = hashlib.sha256(SYNTHETIC_BODY).hexdigest()
    assert record.capture_id == f"{CAPTURE_ID_PREFIX}-{digest[:12]}"

    with pytest.raises(ValidationError):
        snapshot.CaptureRecord.make(
            request=_request(),
            retrieved_at=RETRIEVED_AT.replace(tzinfo=None),
            http_status=200,
            media_type="application/json",
            content_encoding=None,
            body=record.body,
            outcome=OUTCOME,
            rights=_rights(),
        )
    with pytest.raises(ValidationError):
        snapshot.CaptureRecord(
            capture_id=f"{CAPTURE_ID_PREFIX}-ffffffffffff",
            request=_request(),
            retrieved_at=RETRIEVED_AT,
            http_status=200,
            media_type="application/json",
            content_encoding=None,
            body=record.body,
            outcome=OUTCOME,
            rights=_rights(),
        )


def test_the_artifact_writer_shim_keeps_its_messages_while_the_core_moves(
    tmp_path: Path,
) -> None:
    """Fourteen CLI commands depend on these exact refusals; the move must be invisible.

    Its ``SystemExit`` strings are what operators and tests of fourteen commands
    read. Moving the core under ``store/`` so components can raise typed errors
    is safe only if the shim stays byte-identical, so this pins today's messages
    and checks the new home refuses the same inputs typed.
    """
    from fundamentals.api import artifact_writer

    target = tmp_path / "artifact.json"
    artifact_writer.write_bytes_no_clobber(target, b'{"synthetic": true}\n')
    with pytest.raises(SystemExit) as clobber:
        artifact_writer.write_bytes_no_clobber(target, b'{"synthetic": false}\n')
    assert str(clobber.value) == f"{artifact_writer.REFUSE_OVERWRITE}: {target}"
    assert str(clobber.value).startswith("refusing to overwrite existing table artifact")

    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(SystemExit) as unsafe:
        artifact_writer.safe_subdirectory(tmp_path, "linked")
    assert str(unsafe.value) == f"refusing unsafe artifact directory: {linked}"
    assert target.read_bytes() == b'{"synthetic": true}\n'

    from fundamentals.contracts import snapshot
    from fundamentals.store import no_clobber

    with pytest.raises(snapshot.CaptureConflictError):
        no_clobber.write_bytes_no_clobber(target, b'{"synthetic": false}\n')
    with pytest.raises(snapshot.UnsafePathError):
        no_clobber.safe_subdirectory(tmp_path, "linked")


def test_the_snapshot_modules_import_nothing_from_the_lanes_above_them() -> None:
    """Every acquisition lane will import this contract, so it may import none back.

    One import the other way makes the dependency cyclic and drags a transport
    module into anything that only wanted to read a stored capture. The store
    may not reach the reconciler either — retained evidence never votes.
    """
    from fundamentals.contracts import snapshot
    from fundamentals.store import snapshot_store

    assert snapshot.__file__ is not None
    contract_imports = _imported_modules(Path(snapshot.__file__))
    assert not sorted(name for name in contract_imports if name.startswith(CONTRACT_BARRED))

    assert snapshot_store.__file__ is not None
    store_imports = _imported_modules(Path(snapshot_store.__file__))
    assert not sorted(name for name in store_imports if name.startswith(STORE_BARRED))


def test_rights_default_to_private_internal_and_demand_an_authority_ref() -> None:
    """A retained subscriber page carries no licence; the record must say so.

    Screener and Tijori bytes are held under one internal decision and grant
    nothing. Empty ``authority_refs`` would be a retained document with no
    stated basis for holding it, so the empty case is a construction error.
    """
    from fundamentals.contracts import snapshot

    with pytest.raises(ValidationError):
        snapshot.SnapshotRights()
    with pytest.raises(ValidationError):
        snapshot.SnapshotRights(authority_refs=())

    rights = snapshot.SnapshotRights(authority_refs=(snapshot.A05_DECISION_005,))
    assert rights.use is snapshot.SnapshotUse.PRIVATE_INTERNAL
    assert rights.redistribution is snapshot.Redistribution.PROHIBITED
    assert snapshot.A05_DECISION_005 == "A05-DECISION-005"
