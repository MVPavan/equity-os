"""Importable multiprocessing entry point for synthetic source-intake concurrency tests.

Pytest importlib collection names are not importable in a spawned interpreter.
This ordinary support module retains the same fixture construction and assertions.
"""

from pathlib import Path
from typing import Any

from equity_os.contracts.sourcing.snapshot import CaptureRecord
from equity_os.contracts.sourcing.source_registration import SourceRegistrationError, SourceRole
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.raw_files.source_intake_store import SourceIntakeStore


def register_process(
    root: str, inputs: str, record_data: str, role: str, barrier: Any, queue: Any
) -> None:
    from test_source_intake_store import context, ref

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
