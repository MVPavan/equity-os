"""Byte copies of the legacy SQLite store and its canonical-selection baseline (D2 Task 1).

The legacy file ``data/store/aparinds.sqlite`` is gitignored and pinned by SHA-256.
It is never opened: tests copy its bytes under ``tmp_path`` and work on the copy.
A missing or mismatched file **fails** the test and never skips it.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fundamentals.store.fact_store import FactStore, FactStoreLike

REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_PATH = REPO_ROOT / "data" / "store" / "aparinds.sqlite"
LEGACY_SHA256 = "cb02b0f12a1708d07f4e8f1dbaefd59bb89762897b6de242c03da9f9a8157bd8"
LEGACY_NAME = "aparinds.sqlite"
SECOND_DIR = "second"

BASELINE_CUTOFFS: tuple[datetime, ...] = (
    # Before the store's first knowledge time (2025-11-06T12:05:34Z, the pre-IST-fix cutoff).
    datetime(2025, 11, 1, tzinfo=UTC),
    # After the store's last knowledge time (2026-07-31T15:44:41Z), before the first selection.
    datetime(2026, 8, 15, tzinfo=UTC),
    # The 12th stored canonical_selected_at.
    datetime(2026, 9, 7, 4, 58, 28, 240083, tzinfo=UTC),
    # One microsecond after the last selection (04:58:30.843102Z).
    datetime(2026, 9, 7, 4, 58, 30, 843103, tzinfo=UTC),
    datetime(2100, 1, 1, tzinfo=UTC),
)


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_copy(tmp_path: Path) -> Path:
    """A SHA-checked byte copy of the legacy store under ``tmp_path``, or fail."""
    if not LEGACY_PATH.is_file():
        pytest.fail(f"legacy store missing: {LEGACY_PATH}")
    copy = tmp_path / LEGACY_NAME
    shutil.copyfile(LEGACY_PATH, copy)
    if file_sha256(copy) != LEGACY_SHA256:
        pytest.fail(f"legacy store SHA-256 mismatch: {LEGACY_PATH}")
    return copy


def second_store(tmp_path: Path) -> Path:
    """A legacy copy migrated once by ``FactStore`` from its stored selection times."""
    folder = tmp_path / SECOND_DIR
    folder.mkdir()
    path = legacy_copy(folder)
    FactStore(path).close()
    return path


def baseline_rows(store: FactStoreLike, cutoff: datetime) -> list[dict[str, str | int]]:
    """The canonical revision and its effective selection, per identity, at ``cutoff``."""
    rows: list[dict[str, str | int]] = []
    for revision in store.query_canonical(cutoff=cutoff):
        history = store.get_selection_history(revision.content_identity)
        decision = [item for item in history if item.selected_at <= cutoff][-1]
        rows.append(
            {
                "row_id": revision.row_id,
                "content_identity": revision.content_identity,
                "value_hash": revision.value_hash,
                "selection_id": decision.selection_id,
                "selection_sha256": decision.selection_sha256,
            }
        )
    return rows
