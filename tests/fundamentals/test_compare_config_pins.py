"""Extractor pins are shared by ingestion and comparison, including re-extraction versions."""

from pathlib import Path

import pytest

from fundamentals.compare import run_config
from fundamentals.compare.run_config import EXTRACTOR_VERSIONS, extractor_pin
from fundamentals.contracts.canonical import Representation


def test_extractor_pin_hashes_the_selected_version_with_current_sources() -> None:
    """Ingesting under another version gets a content pin for that version's actual code."""
    for representation in Representation:
        current = extractor_pin(representation)
        assert extractor_pin(representation, version=EXTRACTOR_VERSIONS[representation]) == current
        reextracted = extractor_pin(representation, version="test-reextract")
        assert reextracted.version == "test-reextract"
        assert reextracted.content_sha256 != current.content_sha256
        assert extractor_pin(representation, version="test-reextract") == reextracted


def test_identity_verification_source_changes_both_extractor_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed issuer/basis verification must invalidate both extraction cache identities."""
    source_paths = {
        relative for paths in run_config.EXTRACTOR_SOURCES.values() for relative in paths
    }
    source_paths.add("evidence/member_identity.py")
    for relative in source_paths:
        source = tmp_path / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("test extraction source\n", encoding="utf-8")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", tmp_path)
    before = {representation: extractor_pin(representation) for representation in Representation}
    (tmp_path / "evidence/member_identity.py").write_text(
        "changed issuer and basis verifier\n", encoding="utf-8"
    )
    for representation in Representation:
        assert extractor_pin(representation) != before[representation]


@pytest.mark.parametrize("relative", ["extract/xbrl_taxonomies.py", "extract/xbrl_dimensions.py"])
def test_xbrl_semantic_sources_are_in_the_extractor_pin(
    relative: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Namespace/dimension interpretation changes require a new extraction content pin."""
    source_paths = set(run_config.EXTRACTOR_SOURCES[Representation.XBRL]) | {relative}
    for name in source_paths:
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"original semantic source\n")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", tmp_path)
    before = extractor_pin(Representation.XBRL)
    (tmp_path / relative).write_bytes(b"changed semantic source\n")
    assert extractor_pin(Representation.XBRL) != before
