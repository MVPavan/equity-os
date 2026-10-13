"""Execution and replay pins must describe the same immutable bytes that were parsed."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pg_support import PgTestDatabase

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.evidence.mapping import load_mapping_set
from fundamentals.pg.migrations import apply_migrations

CONFIG = Path(__file__).resolve().parents[2] / "config"


@pytest.mark.parametrize("filename", ["pl.yaml", "derived.yaml", "applicability.yaml"])
def test_dictionary_pin_uses_the_parsed_bytes(
    filename: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file changing after its first read cannot alter the hash of the loaded model."""
    expected = load_dictionary(CONFIG / "dictionary", "v1")
    target = CONFIG / "dictionary" / "v1" / filename
    original = target.read_bytes()
    read_bytes = Path.read_bytes
    reads = 0

    def changing_read(path: Path) -> bytes:
        nonlocal reads
        if path != target:
            return read_bytes(path)
        reads += 1
        return original if reads == 1 else original + b"\n# changed after parsing\n"

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    actual = load_dictionary(CONFIG / "dictionary", "v1")
    assert actual == expected
    assert reads == 1


def test_mapping_pin_uses_the_parsed_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """An entry file replacement cannot produce a pin for bytes the loader never parsed."""
    dictionary = load_dictionary(CONFIG / "dictionary", "v1")
    expected = load_mapping_set(CONFIG / "mappings", "v1", dictionary=dictionary)
    target = CONFIG / "mappings" / "pdf" / "v1" / "results_layout.yaml"
    original = target.read_bytes()
    read_bytes = Path.read_bytes
    reads = 0

    def changing_read(path: Path) -> bytes:
        nonlocal reads
        if path != target:
            return read_bytes(path)
        reads += 1
        return original if reads == 1 else original + b"\n# changed after parsing\n"

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    actual = load_mapping_set(CONFIG / "mappings", "v1", dictionary=dictionary)
    assert actual == expected
    assert reads == 1


@pytest.mark.pg
def test_migration_executes_the_bytes_it_records(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A replacement between checksum and execution cannot execute unpinned SQL."""
    target = tmp_path / "0001_pinned_probe.sql"
    original = b"CREATE TABLE eqos.pinned_sql_probe (id int);"
    replacement = b"CREATE TABLE eqos.unpinned_sql_probe (id int);"
    target.write_bytes(original)
    read_bytes = Path.read_bytes
    reads = 0

    def changing_read(path: Path) -> bytes:
        nonlocal reads
        if path != target:
            return read_bytes(path)
        reads += 1
        return original if reads == 1 else replacement

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    with pg_db.migrator_connection() as connection:
        (applied,) = apply_migrations(connection, tmp_path)
        assert applied.sha256 == hashlib.sha256(original).hexdigest()
        assert connection.execute("SELECT to_regclass('eqos.pinned_sql_probe')").fetchone() == (
            "eqos.pinned_sql_probe",
        )
        assert connection.execute("SELECT to_regclass('eqos.unpinned_sql_probe')").fetchone() == (
            None,
        )
    assert reads == 1
