"""Extractor pins are shared by ingestion and comparison, including re-extraction versions."""

from pathlib import Path

import pytest

from fundamentals.compare import run_config
from fundamentals.compare.run_config import EXTRACTOR_VERSIONS, extractor_pin, vendor_extractor_pin
from fundamentals.contracts.canonical import FIRST_PARTY_REPRESENTATIONS, Representation


def test_extractor_pin_hashes_the_selected_version_with_current_sources() -> None:
    """Ingesting under another version gets a content pin for that version's actual code."""
    for representation in FIRST_PARTY_REPRESENTATIONS:
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
    before = {
        representation: extractor_pin(representation)
        for representation in FIRST_PARTY_REPRESENTATIONS
    }
    (tmp_path / "evidence/member_identity.py").write_text(
        "changed issuer and basis verifier\n", encoding="utf-8"
    )
    for representation in FIRST_PARTY_REPRESENTATIONS:
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


@pytest.mark.parametrize(
    ("source", "relative"),
    [
        ("PDF", "extract/pdf_figure_columns.py"),
        ("screener-subscriber", "ingest/screener_session_page.py"),
        ("screener-subscriber", "ingest/screener_financials_tables.py"),
        ("tijori", "ingest/tijori_tables.py"),
        ("tijori", "ingest/tijori_common.py"),
        ("upstox", "ingest/upstox_source.py"),
    ],
)
def test_parser_and_identity_dependencies_are_in_the_extractor_pins(
    source: str, relative: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing a file an extractor reads its occurrences or verifies identity through must
    change that extractor's content pin (a stale extraction is otherwise silently reused)."""
    real = Path(run_config.__file__).resolve().parents[1]
    names = {name for paths in run_config.EXTRACTOR_SOURCES.values() for name in paths}
    names |= {name for _, paths in run_config.VENDOR_EXTRACTORS.values() for name in paths}
    for name in names | {relative}:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes((real / name).read_bytes())
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", tmp_path)

    def pin() -> str:
        if source == "PDF":
            return extractor_pin(Representation.PDF).content_sha256
        return vendor_extractor_pin(source, "surface").content_sha256

    before = pin()
    (tmp_path / relative).write_bytes(b"mutated\n")
    assert pin() != before
