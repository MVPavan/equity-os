"""Joined vendor configuration is the only runtime path to vendor mappings."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from pg_support import PgTestDatabase

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.compare.run_config import ConfigVersions, load_run_config, pin_config
from fundamentals.contracts.source_catalog import EvidenceRole
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy
from fundamentals.evidence.repository import EvidenceRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config"
SOURCE_ROOT = REPO_ROOT / "src" / "fundamentals"
SCREENER_SOURCE = "screener-subscriber"
FINANCIALS = "SCREENER_FINANCIALS"
SCHEDULE = "SCREENER_SCHEDULE"
SCREENER_VERSION = "screener-v1"
SCREENER_FILES = (
    "evidence/vendor_common.py",
    "evidence/vendor_screener.py",
    "evidence/interpret.py",
    "ingest/screener_financials_models.py",
    "ingest/screener_financials_schedules.py",
    "ingest/screener_financials_shapes.py",
    "ingest/screener_financials_tables.py",
    "ingest/screener_session_models.py",
    "ingest/screener_session_page.py",
)


def _pin(version: str, content_sha256: str) -> dict[str, str]:
    return {"version": version, "content_sha256": content_sha256}


def _member(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _bundle(source_root: Path, files: tuple[str, ...]) -> tuple[list[dict[str, str]], str]:
    members = [_member(source_root / name, source_root) for name in files]
    digest = hashlib.sha256(SCREENER_VERSION.encode() + b"\0")
    for item in members:
        digest.update(item["path"].encode() + b"\0")
        digest.update(bytes.fromhex(item["content_sha256"]))
    return members, digest.hexdigest()


def _write_yaml(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _draft_root(tmp_path: Path, *, version: str = "v2") -> Path:
    root = tmp_path / f"config-{version}"
    shutil.copytree(CONFIG, root, ignore=shutil.ignore_patterns("vendor_publication"))
    vendor_member = root / "mappings" / "publication-test" / version / "financials.yaml"
    _write_yaml(
        vendor_member,
        {
            "source": SCREENER_SOURCE,
            "surface": FINANCIALS,
            "schema_identity": "screener-financials-html-v1",
            "defaults": {"tier": "EQUIVALENCE_UNPROVEN"},
            "entries": [
                {
                    "entry_id": f"publication.{version}.revenue",
                    "selector": {
                        "statement_family": "PL",
                        "labels": ["Sales"],
                        "section_equals": "quarters",
                    },
                    "canonical_id": "revenue_from_operations",
                    "period_rule": "COLUMN_DURATION",
                    "period_kinds": ["QUARTER"],
                    "evidence_ref": "synthetic publication contract fixture",
                }
            ],
        },
    )
    index = yaml.safe_load((root / "mappings" / "v1.yaml").read_bytes())
    index["version"] = version
    index["entry_files"].append(vendor_member.relative_to(root / "mappings").as_posix())
    _write_yaml(root / "mappings" / f"{version}.yaml", index)
    return root


def _mapping_member_paths(root: Path, version: str) -> tuple[Path, ...]:
    index_path = root / "mappings" / f"{version}.yaml"
    index = yaml.safe_load(index_path.read_bytes())
    names = (
        list(index["entry_files"])
        + list(index.get("construction_files", ()))
        + list(index.get("statement_anchor_files", ()))
    )
    return (index_path, *(root / "mappings" / name for name in names))


def _publish_synthetic(root: Path, *, version: str = "v2") -> Path:
    dictionary = load_dictionary(root / "dictionary", "v1")
    mappings = load_mapping_set(root / "mappings", version, dictionary=dictionary)
    normalisation = load_normalisation_policy(root / "normalisation_policy" / "v1.yaml")

    authority_path = root / "source_authority" / "synthetic-v1.yaml"
    _write_yaml(
        authority_path,
        {
            "version": "synthetic-v1",
            "sources": [
                {
                    "source_id": "upstox",
                    "source_class": "derived",
                    "evidence_role": "diagnostic_only",
                    "classification_ref": "synthetic role-only fixture; data spec section 3",
                    "classification_sha256": "1" * 64,
                }
            ],
            "surfaces": [
                {
                    "source_id": SCREENER_SOURCE,
                    "surface": FINANCIALS,
                    "representation": "HTML",
                    "evidence_role": "reconcilable",
                    "authority_ref": "synthetic A05-DECISION-005 fixture",
                    "authority_sha256": "2" * 64,
                },
                {
                    "source_id": SCREENER_SOURCE,
                    "surface": SCHEDULE,
                    "representation": "JSON",
                    "evidence_role": "reconcilable",
                    "authority_ref": "synthetic A05-DECISION-005 fixture",
                    "authority_sha256": "2" * 64,
                },
                {
                    "source_id": "tijori",
                    "surface": "TIJORI_FINANCIALS",
                    "representation": "HTML",
                    "evidence_role": "reconcilable",
                    "authority_ref": "synthetic A05-DECISION-005 fixture",
                    "authority_sha256": "2" * 64,
                },
            ],
        },
    )
    bundle_members, bundle_sha = _bundle(SOURCE_ROOT, SCREENER_FILES)
    publication = {
        "version": version,
        "state": "SYNTHETIC",
        "dictionary": _pin(dictionary.version, dictionary.content_sha256),
        "formula_set": _pin(dictionary.formula_set_version, dictionary.formula_set_sha256),
        "mapping_set": _pin(mappings.version, mappings.content_sha256),
        "normalisation_policy": _pin(normalisation.version, normalisation.content_sha256),
        "mapping_members": [_member(path, root) for path in _mapping_member_paths(root, version)],
        "source_authority": {
            **_pin("synthetic-v1", hashlib.sha256(authority_path.read_bytes()).hexdigest()),
            "path": authority_path.relative_to(root).as_posix(),
        },
        "surface_ledger": [
            {
                "source_id": SCREENER_SOURCE,
                "surface": FINANCIALS,
                "representation": "HTML",
                "disposition": "INCLUDED",
                "reason": "synthetic retained-page contract fixture",
            },
            {
                "source_id": SCREENER_SOURCE,
                "surface": SCHEDULE,
                "representation": "JSON",
                "disposition": "INCLUDED",
                "reason": "synthetic separately retained schedule fixture",
            },
            {
                "source_id": "tijori",
                "surface": "TIJORI_FINANCIALS",
                "representation": "HTML",
                "disposition": "UNAVAILABLE",
                "reason": "authorized surface has no retained body",
            },
            {
                "source_id": "upstox",
                "surface": "income-statement",
                "representation": "JSON",
                "disposition": "EXCLUDED",
                "reason": "diagnostic role does not establish capture or retention rights",
            },
        ],
        "extractor_bundles": [
            {
                "source_id": SCREENER_SOURCE,
                "surface": surface,
                "version": SCREENER_VERSION,
                "content_sha256": bundle_sha,
                "members": bundle_members,
            }
            for surface in (FINANCIALS, SCHEDULE)
        ],
    }
    path = root / "vendor_publication" / f"{version}.yaml"
    _write_yaml(path, publication)
    return path


def _publication_document(root: Path, version: str = "v2") -> tuple[Path, dict[str, Any]]:
    path = root / "vendor_publication" / f"{version}.yaml"
    return path, yaml.safe_load(path.read_bytes())


def test_unpublished_vendor_mapping_loads_low_level_but_run_config_refuses_it(
    tmp_path: Path,
) -> None:
    """A valid mutable mapping draft cannot become a runtime config without publication."""
    root = _draft_root(tmp_path)
    dictionary = load_dictionary(root / "dictionary", "v1")
    assert load_mapping_set(root / "mappings", "v2", dictionary=dictionary).version == "v2"

    with pytest.raises(ValueError, match="published vendor configuration"):
        load_run_config(root, ConfigVersions(mapping_set="v2"))


def test_synthetic_publication_joins_exact_members_authority_surfaces_and_bundles(
    tmp_path: Path,
) -> None:
    root = _draft_root(tmp_path)
    publication_path = _publish_synthetic(root)

    loaded = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    published = loaded.vendor_config
    assert published is not None
    assert published.content_sha256 == hashlib.sha256(publication_path.read_bytes()).hexdigest()
    assert {item.path for item in published.mapping_members} == {
        path.relative_to(root).as_posix() for path in _mapping_member_paths(root, "v2")
    }
    assert {(pin.source_id, pin.surface) for pin in loaded.pinned.vendor_extractors} == {
        (SCREENER_SOURCE, FINANCIALS),
        (SCREENER_SOURCE, SCHEDULE),
    }
    assert loaded.pinned.source_authority == published.source_authority.pin
    assert {
        (item.source_id, item.surface, item.disposition.value) for item in published.surface_ledger
    } == {
        (SCREENER_SOURCE, FINANCIALS, "INCLUDED"),
        (SCREENER_SOURCE, SCHEDULE, "INCLUDED"),
        ("tijori", "TIJORI_FINANCIALS", "UNAVAILABLE"),
        ("upstox", "income-statement", "EXCLUDED"),
    }
    assert published.catalog.describe("upstox").evidence_role is EvidenceRole.DIAGNOSTIC_ONLY
    assert all(item.source_id != "upstox" for item in published.authorities)


@pytest.mark.parametrize("target", ["dictionary", "mapping", "normalisation", "authority"])
def test_publication_refuses_joined_artifact_drift(tmp_path: Path, target: str) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    paths = {
        "dictionary": root / "dictionary" / "v1" / "pl.yaml",
        "mapping": root / "mappings" / "publication-test" / "v2" / "financials.yaml",
        "normalisation": root / "normalisation_policy" / "v1.yaml",
        "authority": root / "source_authority" / "synthetic-v1.yaml",
    }
    with paths[target].open("ab") as changed:
        changed.write(b"\n# drift after publication\n")

    with pytest.raises((ValueError, VersionContentDriftError), match="drift|pinned|differs"):
        load_run_config(
            root,
            ConfigVersions(mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )


def test_publication_refuses_extractor_source_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    copied_source_root = tmp_path / "fundamentals-source"
    for relative in SCREENER_FILES:
        copied = copied_source_root / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE_ROOT / relative, copied)
    target = copied_source_root / "evidence" / "vendor_screener.py"
    target.write_bytes(target.read_bytes() + b"\n# parser drift\n")
    monkeypatch.setattr("fundamentals.evidence.vendor_config._SOURCE_ROOT", copied_source_root)

    with pytest.raises(ValueError, match="extractor.*drift"):
        load_run_config(
            root,
            ConfigVersions(mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )


@pytest.mark.parametrize("defect", ["omitted_member", "unknown_surface", "conflict", "state"])
def test_publication_refuses_incomplete_or_unsupported_release(tmp_path: Path, defect: str) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    path, document = _publication_document(root)
    if defect == "omitted_member":
        document["mapping_members"].pop()
    elif defect == "unknown_surface":
        document["surface_ledger"][0]["source_id"] = "undeclared-vendor"
    elif defect == "conflict":
        document["surface_ledger"].append(
            {**document["surface_ledger"][0], "disposition": "EXCLUDED"}
        )
    else:
        document["state"] = "DRAFT"
    _write_yaml(path, document)

    with pytest.raises(ValueError):
        load_run_config(
            root,
            ConfigVersions(mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )


def test_publication_refuses_incompatible_dictionary_mapping_pair(tmp_path: Path) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    shutil.rmtree(root / "dictionary" / "v2")
    shutil.copytree(root / "dictionary" / "v1", root / "dictionary" / "v2")
    metadata = yaml.safe_load((root / "dictionary" / "v2" / "metadata.yaml").read_bytes())
    metadata["version"] = "v2"
    _write_yaml(root / "dictionary" / "v2" / "metadata.yaml", metadata)

    with pytest.raises(ValueError, match="dictionary.*drift|dictionary.*pinned"):
        load_run_config(
            root,
            ConfigVersions(dictionary="v2", mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )


def test_later_publication_has_distinct_identity_and_old_release_stays_resolvable(
    tmp_path: Path,
) -> None:
    old_root = _draft_root(tmp_path / "old", version="v2")
    _publish_synthetic(old_root, version="v2")
    new_root = _draft_root(tmp_path / "new", version="v3")
    _publish_synthetic(new_root, version="v3")

    old = load_run_config(
        old_root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    new = load_run_config(
        new_root,
        ConfigVersions(mapping_set="v3"),
        allow_synthetic_vendor_config=True,
    )
    assert old.vendor_config is not None and new.vendor_config is not None
    assert old.vendor_config.content_sha256 != new.vendor_config.content_sha256
    assert old.pinned.mapping_set.version == "v2"
    assert (
        load_run_config(
            old_root,
            ConfigVersions(mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )
        == old
    )


def test_legacy_v1_load_and_dump_remain_unchanged() -> None:
    loaded = load_run_config(CONFIG)
    assert loaded.vendor_config is None
    assert ConfigVersions().model_dump(mode="json") == {
        "dictionary": "v1",
        "mapping_set": "v1",
        "normalisation_policy": "v1",
        "rounding_policy": "v1",
        "definition_set": "v1",
        "comparison_policy": "v1",
        "alignment_rules": "v1",
    }
    assert "vendor_extractors" not in loaded.pinned.model_dump(mode="json")
    assert "source_authority" not in loaded.pinned.model_dump(mode="json")


@pytest.mark.pg
def test_publication_pin_roundtrips_and_same_version_ledger_drift_is_refused(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    root = _draft_root(tmp_path)
    _publish_synthetic(root)
    original = load_run_config(
        root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        pin_config(original, repository=repository, pool=pool)

        path, document = _publication_document(root)
        document["surface_ledger"][2]["reason"] = "same version, changed unavailable reason"
        _write_yaml(path, document)
        drifted = load_run_config(
            root,
            ConfigVersions(mapping_set="v2"),
            allow_synthetic_vendor_config=True,
        )
        with pytest.raises(VersionContentDriftError, match="vendor_publication"):
            pin_config(drifted, repository=repository, pool=pool)
