"""Regressions for the reviewed joined-publication trust boundaries."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml
from test_vendor_config_publication import (
    CONFIG,
    FINANCIALS,
    SCHEDULE,
    SCREENER_SOURCE,
    _draft_root,
    _mapping_member_paths,
    _publication_document,
    _publish_synthetic,
    _write_yaml,
)

import fundamentals.compare.run_config as run_config_module
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.compare.run_config import ConfigVersions, load_run_config, require_pins
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy
from fundamentals.evidence.vendor_config import (
    VendorConfigPublicationError,
    code_bundle_pin,
    mapping_requires_publication,
)
from fundamentals.evidence.vendor_screener import SCHEDULE_SCHEMA


def _load_synthetic(root: Path):  # type: ignore[no-untyped-def]
    return load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )


def test_descriptor_snapshot_seam_preserves_legacy_v1_models_and_pins() -> None:
    direct_dictionary = load_dictionary(CONFIG / "dictionary", "v1")
    direct_mapping = load_mapping_set(CONFIG / "mappings", "v1", dictionary=direct_dictionary)
    direct_normalisation = load_normalisation_policy(CONFIG / "normalisation_policy" / "v1.yaml")

    loaded = load_run_config(CONFIG)

    assert loaded.dictionary == direct_dictionary
    assert loaded.mapping_set == direct_mapping
    assert loaded.normalisation_policy == direct_normalisation
    assert loaded.pinned.dictionary.content_sha256 == direct_dictionary.content_sha256
    assert loaded.pinned.mapping_set.content_sha256 == direct_mapping.content_sha256
    assert loaded.pinned.normalisation_policy.content_sha256 == direct_normalisation.content_sha256


def test_public_vendor_load_never_reopens_joined_members_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    original_read = Path.read_bytes
    named_reads: list[Path] = []
    joined_roots = (
        root / "dictionary",
        root / "normalisation_policy",
    )
    mapping_members = set(_mapping_member_paths(root, "v2"))

    def refuse_joined_named_read(path: Path) -> bytes:
        if path in mapping_members or any(
            path.is_relative_to(joined_root) for joined_root in joined_roots
        ):
            named_reads.append(path)
            raise AssertionError(f"joined member reopened by name: {path}")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", refuse_joined_named_read)

    loaded = _load_synthetic(root)

    assert loaded.vendor_config is not None
    assert named_reads == []


def test_missing_publication_refuses_before_unjoined_legacy_config_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    original_read = Path.read_bytes
    later_reads = {
        root / "rounding_policy" / "v1.yaml",
        root / "definition_sets" / "v1.yaml",
        root / "comparison_policy" / "v1.yaml",
        root / "mappings" / "alignment" / "v1.yaml",
    }

    def refuse_later_read(path: Path) -> bytes:
        if path in later_reads:
            raise AssertionError(f"unjoined config read preceded publication proof: {path}")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", refuse_later_read)

    with pytest.raises(VendorConfigPublicationError, match="published vendor configuration"):
        load_run_config(root, ConfigVersions(mapping_set="v2"))


@pytest.mark.parametrize(
    "defect",
    ["root", "directory", "member", "mapping_member", "policy", "nonregular"],
)
def test_public_vendor_load_refuses_unsafe_joined_paths_before_named_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    real = _draft_root(tmp_path)
    _publish_synthetic(real)
    root = real
    if defect == "root":
        root = tmp_path / "linked-config"
        root.symlink_to(real, target_is_directory=True)
    elif defect == "directory":
        dictionary = real / "dictionary" / "v1"
        moved = tmp_path / "dictionary-v1"
        dictionary.rename(moved)
        dictionary.symlink_to(moved, target_is_directory=True)
    elif defect == "member":
        member = real / "dictionary" / "v1" / "pl.yaml"
        moved = tmp_path / "pl.yaml"
        shutil.copyfile(member, moved)
        member.unlink()
        member.symlink_to(moved)
    elif defect == "mapping_member":
        member = real / "mappings" / "publication-test" / "v2" / "financials.yaml"
        moved = tmp_path / "financials.yaml"
        shutil.copyfile(member, moved)
        member.unlink()
        member.symlink_to(moved)
    elif defect == "policy":
        member = real / "normalisation_policy" / "v1.yaml"
        moved = tmp_path / "normalisation-v1.yaml"
        shutil.copyfile(member, moved)
        member.unlink()
        member.symlink_to(moved)
    else:
        member = real / "dictionary" / "v1" / "pl.yaml"
        member.unlink()
        member.mkdir()
    original_read = Path.read_bytes
    named_reads: list[Path] = []

    def observe_named_read(path: Path) -> bytes:
        if any(part in path.parts for part in ("dictionary", "mappings", "normalisation_policy")):
            named_reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", observe_named_read)

    with pytest.raises(VendorConfigPublicationError, match="unsafe|symlink|regular"):
        _load_synthetic(root)

    assert named_reads == []


def test_public_vendor_load_applies_bound_before_parsing_joined_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    monkeypatch.setattr(
        "fundamentals.evidence.vendor_config_files.MAX_CONFIG_BYTES",
        400,
    )

    with pytest.raises(
        VendorConfigPublicationError,
        match=r"dictionary/v1/.*safe read limit",
    ):
        _load_synthetic(root)


def test_public_vendor_load_parses_validated_snapshot_without_named_reopen_after_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    member = root / "mappings" / "publication-test" / "v2" / "financials.yaml"
    outside = tmp_path / "validated-financials.yaml"
    shutil.copyfile(member, outside)
    validate = run_config_module.validate_mapping_member_paths
    swapped = False

    def validate_then_swap(*args: object, **kwargs: object) -> tuple[str, ...]:
        nonlocal swapped
        paths = validate(*args, **kwargs)  # type: ignore[arg-type]
        if not swapped:
            swapped = True
            member.unlink()
            member.symlink_to(outside)
        return paths

    original_read = Path.read_bytes
    named_reads: list[Path] = []

    def observe_named_read(path: Path) -> bytes:
        if path == member:
            named_reads.append(path)
        return original_read(path)

    monkeypatch.setattr(run_config_module, "validate_mapping_member_paths", validate_then_swap)
    monkeypatch.setattr(Path, "read_bytes", observe_named_read)

    loaded = _load_synthetic(root)

    assert swapped
    assert loaded.vendor_config is not None
    assert named_reads == []


def test_released_state_without_commit_backed_review_receipt_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A RELEASED label under the configured root is not operational approval."""
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    path, document = _publication_document(root)
    document["state"] = "RELEASED"
    _write_yaml(path, document)
    monkeypatch.setattr("fundamentals.evidence.vendor_config._COMMITTED_CONFIG_ROOT", root)

    with pytest.raises(VendorConfigPublicationError, match="review receipt"):
        load_run_config(root, ConfigVersions(mapping_set="v2"))


def test_released_state_does_not_accept_an_alternate_receipt_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    path, document = _publication_document(root)
    document["state"] = "RELEASED"
    _write_yaml(path, document)
    _write_yaml(
        root / "vendor_publication" / "v2.approval.yaml",
        {"verdict": "APPROVE", "publication_sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
    )
    monkeypatch.setattr("fundamentals.evidence.vendor_config._COMMITTED_CONFIG_ROOT", root)

    with pytest.raises(VendorConfigPublicationError, match="review receipt"):
        load_run_config(root, ConfigVersions(mapping_set="v2"))


@pytest.mark.parametrize("source", [SCREENER_SOURCE, "undeclared-vendor"])
def test_derived_or_unknown_source_cannot_masquerade_as_first_party_surface(
    tmp_path: Path, source: str
) -> None:
    root = _draft_root(tmp_path)
    member = root / "mappings" / "publication-test" / "v2" / "financials.yaml"
    document = yaml.safe_load(member.read_bytes())
    document["source"] = source
    document["surface"] = "NSE_RESULTS_PDF"
    _write_yaml(member, document)
    dictionary = load_run_config(root).dictionary
    mapping = load_mapping_set(root / "mappings", "v2", dictionary=dictionary)

    assert mapping_requires_publication(mapping)


def test_upstox_reconcilable_role_declaration_is_refused(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    authority = root / "source_authority" / "synthetic-v1.yaml"
    document = yaml.safe_load(authority.read_bytes())
    document["sources"][0]["evidence_role"] = "reconcilable"
    _write_yaml(authority, document)
    publication_path, publication = _publication_document(root)
    publication["source_authority"]["content_sha256"] = hashlib.sha256(
        authority.read_bytes()
    ).hexdigest()
    _write_yaml(publication_path, publication)

    with pytest.raises(VendorConfigPublicationError, match="[Uu]pstox"):
        _load_synthetic(root)


def test_upstox_surface_authority_is_refused_even_when_internally_consistent(
    tmp_path: Path,
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    authority_path = root / "source_authority" / "synthetic-v1.yaml"
    authority = yaml.safe_load(authority_path.read_bytes())
    authority["surfaces"].append(
        {
            "source_id": "upstox",
            "surface": "income-statement",
            "representation": "JSON",
            "evidence_role": "diagnostic_only",
            "authority_ref": "synthetic role-only evidence",
            "authority_sha256": "3" * 64,
        }
    )
    _write_yaml(authority_path, authority)
    publication_path, publication = _publication_document(root)
    publication["source_authority"]["content_sha256"] = hashlib.sha256(
        authority_path.read_bytes()
    ).hexdigest()
    upstox = next(item for item in publication["surface_ledger"] if item["source_id"] == "upstox")
    upstox["disposition"] = "INCLUDED"
    copied_bundle = dict(publication["extractor_bundles"][0])
    copied_bundle.update(source_id="upstox", surface="income-statement")
    publication["extractor_bundles"].append(copied_bundle)
    _write_yaml(publication_path, publication)

    with pytest.raises(VendorConfigPublicationError, match="[Uu]pstox"):
        _load_synthetic(root)


def test_same_version_ledger_drift_is_refused_by_runtime_pins(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    original = _load_synthetic(root)
    path, document = _publication_document(root)
    document["surface_ledger"][2]["reason"] = "changed without a new publication version"
    _write_yaml(path, document)
    drifted = _load_synthetic(root)

    with pytest.raises(ValueError, match="vendor_publication"):
        require_pins(drifted, original.pinned)


@pytest.mark.parametrize(
    "field,value",
    [
        ("dictionary", "../v1"),
        ("mapping_set", "vendor/v2"),
        ("normalisation_policy", "."),
        ("rounding_policy", "v1.yaml"),
    ],
)
def test_config_versions_are_single_canonical_components(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="component"):
        ConfigVersions(**{field: value})


def test_code_bundle_pin_refuses_symlinked_member(tmp_path: Path) -> None:
    real = tmp_path / "real.py"
    real.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(real)

    with pytest.raises(VendorConfigPublicationError, match="symlink|regular|unsafe"):
        code_bundle_pin("v1", ("linked.py",), source_root=tmp_path)


def test_extractor_bundle_refuses_unsupported_mapping_schema(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    member = root / "mappings" / "publication-test" / "v2" / "financials.yaml"
    document = yaml.safe_load(member.read_bytes())
    document["schema_identity"] = "unsupported-shape-v99"
    _write_yaml(member, document)
    _publish_synthetic(root)

    with pytest.raises(VendorConfigPublicationError, match="schema"):
        _load_synthetic(root)


def test_synthetic_join_accepts_the_real_screener_schedule_schema(tmp_path: Path) -> None:
    actual_mapping = yaml.safe_load(
        (CONFIG / "mappings" / "screener" / "v2" / "financials.yaml").read_bytes()
    )
    actual_schedule_schemas = {
        item.get("schema_identity", actual_mapping["schema_identity"])
        for item in actual_mapping["entries"]
        if item.get("surface", actual_mapping["surface"]) == SCHEDULE
    }
    assert actual_schedule_schemas == {SCHEDULE_SCHEMA}

    root = _draft_root(tmp_path)
    financials = root / "mappings" / "publication-test" / "v2" / "financials.yaml"
    schedule = financials.with_name("schedule.yaml")
    document = yaml.safe_load(financials.read_bytes())
    document["surface"] = SCHEDULE
    document["schema_identity"] = SCHEDULE_SCHEMA
    document["entries"][0]["entry_id"] = "publication.v2.schedule.revenue"
    _write_yaml(schedule, document)
    index_path = root / "mappings" / "v2.yaml"
    index = yaml.safe_load(index_path.read_bytes())
    index["entry_files"].append(schedule.relative_to(root / "mappings").as_posix())
    _write_yaml(index_path, index)
    _publish_synthetic(root)

    loaded = _load_synthetic(root)

    assert loaded.vendor_config is not None
    assert any(entry.schema_identity == SCHEDULE_SCHEMA for entry in loaded.mapping_set.entries)


def test_released_bundle_requires_explicit_supported_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    publication_path, document = _publication_document(root)
    document["state"] = "RELEASED"
    assert all("supported_schema_identities" not in item for item in document["extractor_bundles"])
    _write_yaml(publication_path, document)
    monkeypatch.setattr(
        "fundamentals.evidence.vendor_config._require_state",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "fundamentals.evidence.vendor_config._validate_authority_evidence",
        lambda *_args, **_kwargs: (),
    )

    with pytest.raises(VendorConfigPublicationError, match="explicit.*schema"):
        load_run_config(root, ConfigVersions(mapping_set="v2"))


def test_formula_only_drift_is_refused(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    with (root / "dictionary" / "v1" / "derived.yaml").open("ab") as changed:
        changed.write(b"\n# formula-only drift\n")

    with pytest.raises(ValueError, match="formula_set.*drift|formula_set.*pinned"):
        _load_synthetic(root)


def test_publication_mapping_remains_source_and_surface_exact(tmp_path: Path) -> None:
    """A vendor release carries the actual source/surface, not only an allowed surface name."""
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    loaded = _load_synthetic(root)
    assert loaded.vendor_config is not None
    assert any(
        entry.source == SCREENER_SOURCE and entry.surface == FINANCIALS
        for entry in loaded.mapping_set.entries
    )
