"""Load every content-pinned artifact a run uses and pin it in the store (design decision 7).

Each loader hashes its own resolved content; the extractor pins hash the extractor version
constant together with the adapter and parser source bytes, so an unbumped extractor edit
is refused as drift rather than silently reusing a run. ``pin_config`` records every pin in
``eqos.version_pins`` (and publishes the definition set) before any run is resolved: the
same version string with other content raises ``VersionContentDriftError``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.canon.interval import RoundingPolicy, load_rounding_policy
from fundamentals.compare.definitions import (
    DefinitionSet,
    load_definition_set,
    publish_definition_set,
)
from fundamentals.compare.policy import ComparisonPolicy, load_comparison_policy
from fundamentals.contracts.canonical import FIRST_PARTY_REPRESENTATIONS, Representation
from fundamentals.contracts.evidence import PinnedVersions
from fundamentals.contracts.evidence import VersionPin as Pin
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.alignment import AlignmentRuleSet, load_alignment_rules
from fundamentals.evidence.mapping import (
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
    load_normalisation_policy,
)
from fundamentals.evidence.pdf_adapter import PDF_EXTRACTOR_VERSION
from fundamentals.evidence.repository import EvidenceRepository, VersionPin
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION

DICTIONARY_DIR = "dictionary"
MAPPINGS_DIR = "mappings"
NORMALISATION_POLICY_DIR = "normalisation_policy"
ROUNDING_POLICY_DIR = "rounding_policy"
DEFINITION_SETS_DIR = "definition_sets"
COMPARISON_POLICY_DIR = "comparison_policy"
ALIGNMENT_DIR = "alignment"
YAML_SUFFIX = ".yaml"
DEFAULT_VERSION = "v1"
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
# Extractor content sources (design decision 7), relative to the ``fundamentals`` package.
EXTRACTOR_SOURCES: Mapping[Representation, tuple[str, ...]] = {
    Representation.XBRL: (
        "evidence/xbrl_adapter.py",
        "extract/xbrl_parser.py",
        "extract/xbrl_taxonomies.py",
        "extract/xbrl_dimensions.py",
        "evidence/first_party_extract.py",
        "evidence/member_identity.py",
    ),
    Representation.PDF: (
        "evidence/pdf_adapter.py",
        "extract/pdf_statement_pages.py",
        "extract/pdf_header_text.py",
        "extract/pdf_printed_unit.py",
        "evidence/first_party_extract.py",
        "evidence/member_identity.py",
        "ingest/pdf_source.py",
    ),
}
EXTRACTOR_VERSIONS: Mapping[Representation, str] = {
    Representation.XBRL: XBRL_EXTRACTOR_VERSION,
    Representation.PDF: PDF_EXTRACTOR_VERSION,
}
_PIN_FIELDS = (
    "dictionary",
    "formula_set",
    "mapping_set",
    "normalisation_policy",
    "extractor_xbrl",
    "extractor_pdf",
    "rounding_policy",
    "comparison_policy",
    "alignment_rules",
)


class ConfigVersions(BaseModel):
    """Which version of each file-backed artifact a run loads."""

    model_config = ConfigDict(frozen=True)

    dictionary: str = DEFAULT_VERSION
    mapping_set: str = DEFAULT_VERSION
    normalisation_policy: str = DEFAULT_VERSION
    rounding_policy: str = DEFAULT_VERSION
    definition_set: str = DEFAULT_VERSION
    comparison_policy: str = DEFAULT_VERSION
    alignment_rules: str = DEFAULT_VERSION

    @classmethod
    def of(cls, pinned: PinnedVersions) -> ConfigVersions:
        """The file versions a pinned-version set names."""
        return cls(
            dictionary=pinned.dictionary.version,
            mapping_set=pinned.mapping_set.version,
            normalisation_policy=pinned.normalisation_policy.version,
            rounding_policy=pinned.rounding_policy.version,
            definition_set=pinned.definition_set.version,
            comparison_policy=pinned.comparison_policy.version,
            alignment_rules=pinned.alignment_rules.version,
        )


class LoadedConfig(BaseModel):
    """Every content-pinned artifact of one run, with the pins they resolve to."""

    model_config = ConfigDict(frozen=True)

    dictionary: CanonicalDictionary
    mapping_set: MappingSet
    normalisation_policy: NormalisationPolicy
    rounding: RoundingPolicy
    definition_set: DefinitionSet
    comparison_policy: ComparisonPolicy
    alignment_rules: AlignmentRuleSet
    pinned: PinnedVersions


def extractor_pin(representation: Representation, *, version: str | None = None) -> Pin:
    """The chosen extractor version plus its current source files' bytes.

    Ingestion may explicitly name a re-extraction version; comparison defaults to the
    current adapter version. Both paths use the same content hashing contract.
    """
    chosen = EXTRACTOR_VERSIONS[representation] if version is None else version
    digest = hashlib.sha256(chosen.encode("utf-8") + b"\0")
    for relative in EXTRACTOR_SOURCES[representation]:
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256((_SOURCE_ROOT / relative).read_bytes()).digest())
    return Pin(version=chosen, content_sha256=digest.hexdigest())


def load_run_config(
    config_root: Path,
    versions: ConfigVersions | None = None,
    *,
    extractor_pins: Mapping[Representation, Pin] | None = None,
) -> LoadedConfig:
    """Load every artifact at its version and compute its pin (nothing is stored here)."""
    chosen = versions or ConfigVersions()
    dictionary = load_dictionary(config_root / DICTIONARY_DIR, chosen.dictionary)
    mapping_set = load_mapping_set(
        config_root / MAPPINGS_DIR, chosen.mapping_set, dictionary=dictionary
    )
    normalisation = load_normalisation_policy(
        _file(config_root, NORMALISATION_POLICY_DIR, chosen.normalisation_policy)
    )
    rounding = load_rounding_policy(_file(config_root, ROUNDING_POLICY_DIR, chosen.rounding_policy))
    definitions = load_definition_set(
        _file(config_root, DEFINITION_SETS_DIR, chosen.definition_set)
    )
    comparison = load_comparison_policy(
        _file(config_root, COMPARISON_POLICY_DIR, chosen.comparison_policy)
    )
    alignment = load_alignment_rules(
        config_root / MAPPINGS_DIR / ALIGNMENT_DIR / f"{chosen.alignment_rules}{YAML_SUFFIX}"
    )
    extractors = {
        representation: (extractor_pins or {}).get(representation) or extractor_pin(representation)
        for representation in FIRST_PARTY_REPRESENTATIONS
    }
    pinned = PinnedVersions(
        dictionary=Pin(version=dictionary.version, content_sha256=dictionary.content_sha256),
        formula_set=Pin(
            version=dictionary.formula_set_version, content_sha256=dictionary.formula_set_sha256
        ),
        mapping_set=Pin(version=mapping_set.version, content_sha256=mapping_set.content_sha256),
        normalisation_policy=Pin(
            version=normalisation.version, content_sha256=normalisation.content_sha256
        ),
        extractor_xbrl=extractors[Representation.XBRL],
        extractor_pdf=extractors[Representation.PDF],
        rounding_policy=Pin(version=rounding.policy_id, content_sha256=rounding.content_sha256),
        definition_set=Pin(version=definitions.version, content_sha256=definitions.content_sha256),
        comparison_policy=Pin(version=comparison.version, content_sha256=comparison.content_sha256),
        alignment_rules=Pin(version=alignment.version, content_sha256=alignment.content_sha256),
    )
    return LoadedConfig(
        dictionary=dictionary,
        mapping_set=mapping_set,
        normalisation_policy=normalisation,
        rounding=rounding,
        definition_set=definitions,
        comparison_policy=comparison,
        alignment_rules=alignment,
        pinned=pinned,
    )


def require_pins(config: LoadedConfig, pinned: PinnedVersions) -> None:
    """Refuse a config whose resolved content differs from the pins a run names."""
    for name in (*_PIN_FIELDS, "definition_set"):
        expected: Pin = getattr(pinned, name)
        actual: Pin = getattr(config.pinned, name)
        if expected != actual:
            raise VersionContentDriftError(
                artifact=name,
                version=expected.version,
                pinned_sha256=expected.content_sha256,
                actual_sha256=actual.content_sha256,
            )


def pin_config(
    config: LoadedConfig, *, repository: EvidenceRepository, pool: ConnectionPool
) -> int:
    """Pin every artifact on first use and publish the definition set; return the set's id.

    A version already pinned (or published) with other content raises
    ``VersionContentDriftError`` before anything of the run is written. The pins are stored
    before the definition set's connection is taken, so one pooled connection suffices.
    """
    repository.pin_versions(
        [
            VersionPin(artifact=name, version=pin.version, content_sha256=pin.content_sha256)
            for name in _PIN_FIELDS
            for pin in (getattr(config.pinned, name),)
        ]
    )
    with pool.connection() as conn:
        return publish_definition_set(conn, config.definition_set)


def _file(config_root: Path, directory: str, version: str) -> Path:
    """``<config_root>/<directory>/<version>.yaml``."""
    return config_root / directory / f"{version}{YAML_SUFFIX}"
