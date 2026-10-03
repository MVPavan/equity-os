"""Crosscheck dispatch retains synthetic HTTP evidence through the real source."""

import argparse
import email.message
import io
import json
import urllib.request
from pathlib import Path

import pytest
from pydantic import SecretStr
from upstox_fixtures import FIXTURE_STAMP, NSE_ISIN, screener_root, statement_bodies

from fundamentals.api import upstox_crosscheck_cli as cli
from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.ingest.upstox_source import UpstoxConfig, UpstoxCredentials, UpstoxSource
from fundamentals.store.snapshot_store import SnapshotStore


def test_dispatch_retains_statement_bytes_and_metadata_in_shared_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies = {surface: json.dumps(body).encode() for surface, body in statement_bodies().items()}
    responses = iter(bodies[surface] for surface in cli.STATEMENT_SURFACES)

    class Response(io.BytesIO):
        def __init__(self, payload: bytes) -> None:
            super().__init__(payload)
            self.headers = email.message.Message()
            self.headers["Content-Type"] = "application/json"

        def getcode(self) -> int:
            return 200

    class Opener:
        def open(self, request: object, timeout: float) -> Response:
            return Response(next(responses))

    def source_factory(
        config: UpstoxConfig, *, snapshot_store: SnapshotStore | None = None
    ) -> UpstoxSource:
        return UpstoxSource(
            config.model_copy(
                update={"min_request_spacing_seconds": 0, "retrieved_at": lambda: FIXTURE_STAMP}
            ),
            snapshot_store=snapshot_store,
        )

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(cli, "UpstoxSource", source_factory)
    isin_file = tmp_path / "isins.tsv"
    isin_file.write_text(f"{NSE_ISIN}\tFIXTURECO\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    args = argparse.Namespace(
        command=cli.UPSTOX_CROSSCHECK_COMMAND,
        isin_file=str(isin_file),
        screener_root=str(screener_root(tmp_path, "FIXTURECO")),
        out_dir=str(out_dir),
        basis="standalone",
        upstox_root=None,
        triage_config="config/laneb_triage.yaml",
        warn_exit=False,
    )
    assert (
        cli.dispatch_upstox_crosscheck_command(
            args,
            credentials_factory=lambda: UpstoxCredentials(
                access_token=SecretStr("synthetic-token")
            ),
        )
        == 0
    )
    store = SnapshotStore(out_dir / "snapshots")
    retained = [
        CaptureRecord.model_validate_json(path.read_text())
        for path in (out_dir / "snapshots").rglob("record.json")
    ]
    assert len(retained) == 3
    for surface, body in bodies.items():
        records = [record for record in retained if record.request.surface == surface.value]
        assert len(records) == 1
        record = records[0]
        assert store.read_body(record) == body
        assert record.http_status == 200
        assert record.media_type == "application/json"
        assert record.retrieved_at == FIXTURE_STAMP
        assert record.outcome.code is OutcomeCode.OK
        parameters = {item.name: item.value for item in record.request.parameters}
        assert parameters["type"] == "standalone"
        assert parameters["fs"] == "true"
        assert NSE_ISIN in parameters["path"]
    assert (out_dir / cli.REPORT_FILENAME).is_file()
    assert len(list((out_dir / cli.RETENTION_DIRNAME).rglob("*.raw.json"))) == 3


@pytest.fixture
def instruments_transport(monkeypatch: pytest.MonkeyPatch) -> tuple[bytes, list[object]]:
    """Synthetic wire boundary; the real source and stores remain in the lane."""
    from upstox_fixtures import gzip_body, nse_equity_row

    from fundamentals.api import upstox_cli

    body = gzip_body([nse_equity_row()])
    calls: list[object] = []

    class Response(io.BytesIO):
        def __init__(self) -> None:
            super().__init__(body)
            self.headers = email.message.Message()
            self.headers["Content-Type"] = "application/json"
            self.headers["Content-Encoding"] = "gzip"

        def getcode(self) -> int:
            return 200

    class Opener:
        def open(self, request: object, timeout: float) -> Response:
            calls.append(request)
            return Response()

    def source_factory(
        config: UpstoxConfig, *, snapshot_store: SnapshotStore | None = None
    ) -> UpstoxSource:
        return UpstoxSource(
            config.model_copy(
                update={"min_request_spacing_seconds": 0, "retrieved_at": lambda: FIXTURE_STAMP}
            ),
            snapshot_store=snapshot_store,
        )

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(upstox_cli, "UpstoxSource", source_factory)
    return body, calls


def _dispatch_instruments(out_dir: Path) -> int | None:
    """Exercise the public instruments command with no credentials or network."""
    from fundamentals.api.upstox_cli import dispatch_upstox_command

    return dispatch_upstox_command(
        argparse.Namespace(
            command="upstox", out=str(out_dir), surface="instruments", include_suspended=False
        ),
        credentials_factory=lambda: None,
    )


def test_instruments_fresh_nested_output_retains_exact_bytes_and_compatibility(
    tmp_path: Path, instruments_transport: tuple[bytes, list[object]]
) -> None:
    """A first capture must survive when every declared output component is new."""
    body, calls = instruments_transport
    out_dir = tmp_path / "new-parent" / "new-child" / "output"
    assert not out_dir.exists()
    try:
        result = _dispatch_instruments(out_dir)
    except Exception:
        assert len(calls) == 1
        assert not list(tmp_path.rglob("record.json"))
        raise
    assert result == 0
    assert len(calls) == 1
    store = SnapshotStore(out_dir / "snapshots")
    records = store.list_captures("upstox", "instruments", "complete")
    assert len(records) == 1
    record, retained = store.read_capture_verified(
        "upstox", "instruments", "complete", records[0].capture_id
    )
    assert retained == body
    assert record.outcome.code is OutcomeCode.OK
    compatibility = list((out_dir / "upstox").rglob("*_meta.json"))
    assert len(compatibility) == 1
    directory = compatibility[0].parent
    assert {path.name for path in directory.iterdir()} == {
        "upstox_instruments.raw.json.gz",
        "upstox_instruments_meta.json",
        "upstox_instruments.parsed.json",
        "review.json",
    }
    assert (directory / "upstox_instruments.raw.json.gz").read_bytes() == body
    assert json.loads((directory / "review.json").read_text())["record_count"] == 1


@pytest.mark.parametrize(
    "unsafe",
    [
        "final-symlink",
        "ancestor-symlink",
        "output-file",
        "ancestor-file",
        "output-writable",
        "ancestor-writable",
        "store-symlink",
        "store-file",
        "store-writable",
        "parent-component",
    ],
)
def test_instruments_unsafe_output_refuses_before_acquisition(
    tmp_path: Path, instruments_transport: tuple[bytes, list[object]], unsafe: str
) -> None:
    """An unsafe operator path cannot spend the first acquisition."""
    import os

    _, calls = instruments_transport
    parent = tmp_path / "parent"
    out_dir = parent / "output"
    destination = tmp_path / "destination"
    destination.mkdir(mode=0o700)
    if unsafe == "ancestor-symlink":
        parent.symlink_to(destination, target_is_directory=True)
    elif unsafe == "ancestor-file":
        parent.write_bytes(b"synthetic obstruction")
    elif unsafe == "ancestor-writable":
        previous = os.umask(0)
        try:
            parent.mkdir(mode=0o777)
        finally:
            os.umask(previous)
    else:
        parent.mkdir(mode=0o700)
        if unsafe == "final-symlink":
            out_dir.symlink_to(destination, target_is_directory=True)
        elif unsafe == "output-file":
            out_dir.write_bytes(b"synthetic obstruction")
        elif unsafe == "output-writable":
            previous = os.umask(0)
            try:
                out_dir.mkdir(mode=0o777)
            finally:
                os.umask(previous)
        elif unsafe.startswith("store-"):
            out_dir.mkdir(mode=0o700)
            store_dir = out_dir / "snapshots"
            if unsafe == "store-symlink":
                store_dir.symlink_to(destination, target_is_directory=True)
            elif unsafe == "store-file":
                store_dir.write_bytes(b"synthetic obstruction")
            else:
                previous = os.umask(0)
                try:
                    store_dir.mkdir(mode=0o777)
                finally:
                    os.umask(previous)
        elif unsafe == "parent-component":
            out_dir = parent / ".." / "output"
    assert _dispatch_instruments(out_dir) == 2
    assert calls == []
    assert not list(tmp_path.rglob("record.json"))
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("failure", ["fsync", "substitution"])
def test_instruments_bootstrap_failure_refuses_before_acquisition(
    tmp_path: Path,
    instruments_transport: tuple[bytes, list[object]],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """A new directory's durability or identity failure prevents acquisition."""
    import os

    _, calls = instruments_transport
    parent = tmp_path / "new-parent"
    out_dir = parent / "new-child" / "output"
    destination = tmp_path / "destination"
    destination.mkdir(mode=0o700)
    detached = tmp_path / "detached"
    original_fsync = os.fsync
    injected = False

    def fsync(descriptor: int) -> None:
        nonlocal injected
        opened = os.fstat(descriptor)
        if not injected and parent.exists() and opened.st_ino == parent.stat().st_ino:
            injected = True
            if failure == "fsync":
                raise OSError("synthetic bootstrap directory fsync failure")
            original_fsync(descriptor)
            parent.rename(detached)
            parent.symlink_to(destination, target_is_directory=True)
            return
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fsync)
    assert _dispatch_instruments(out_dir) == 2
    assert injected
    assert calls == []
    assert not list(tmp_path.rglob("record.json"))
    assert list(destination.iterdir()) == []
    if detached.exists():
        assert list(detached.iterdir()) == []
