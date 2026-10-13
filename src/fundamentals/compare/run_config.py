"""Load every content-pinned artifact a run uses and pin it in the store (design decision 7).

Each loader hashes its own resolved content; the extractor pins hash the extractor version
constant together with the adapter and parser source bytes, so an unbumped extractor edit
is refused as drift rather than silently reusing a run. ``pin_config`` records every pin in
``eqos.version_pins`` (and publishes the definition set) before any run is resolved: the
same version string with other content raises ``VersionContentDriftError``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from pathlib import Path

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

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
from fundamentals.evidence.vendor_config import (
    PublicationState,
    PublishedVendorConfig,
    VendorConfigPublicationError,
    code_bundle_pin,
    load_published_vendor_config,
    mapping_requires_publication,
    validate_mapping_member_paths,
)
from fundamentals.evidence.vendor_config_files import (
    UnsafeVendorConfigPathError,
    read_safe,
)
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

    @field_validator("*")
    @classmethod
    def _single_component(cls, value: str) -> str:
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or value.endswith(".yaml")
        ):
            raise ValueError("config version must be one canonical filename component")
        return value

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
    vendor_config: PublishedVendorConfig | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    _loaded_config_root: Path | None = PrivateAttr(default=None)


def extractor_pin(representation: Representation, *, version: str | None = None) -> Pin:
    """The chosen extractor version plus its current source files' bytes.

    Ingestion may explicitly name a re-extraction version; comparison defaults to the
    current adapter version. Both paths use the same content hashing contract.
    """
    chosen = EXTRACTOR_VERSIONS[representation] if version is None else version
    return code_bundle_pin(
        chosen,
        EXTRACTOR_SOURCES[representation],
        source_root=_SOURCE_ROOT,
    )


def load_run_config(
    config_root: Path,
    versions: ConfigVersions | None = None,
    *,
    extractor_pins: Mapping[Representation, Pin] | None = None,
    allow_synthetic_vendor_config: bool = False,
) -> LoadedConfig:
    """Load every artifact at its version and compute its pin (nothing is stored here)."""
    chosen = versions or ConfigVersions()
    read_bytes = _config_snapshot_reader(config_root)
    dictionary = load_dictionary(
        config_root / DICTIONARY_DIR,
        chosen.dictionary,
        read_bytes=read_bytes,
    )
    validate_mapping_member_paths(
        config_root / MAPPINGS_DIR,
        chosen.mapping_set,
        read_bytes=read_bytes,
    )
    mapping_set = load_mapping_set(
        config_root / MAPPINGS_DIR,
        chosen.mapping_set,
        dictionary=dictionary,
        read_bytes=read_bytes,
    )
    normalisation = load_normalisation_policy(
        _file(config_root, NORMALISATION_POLICY_DIR, chosen.normalisation_policy),
        read_bytes=read_bytes,
    )
    vendor_config = None
    if mapping_requires_publication(mapping_set):
        vendor_config = load_published_vendor_config(
            config_root,
            chosen.mapping_set,
            dictionary=dictionary,
            mapping_set=mapping_set,
            normalisation_policy=normalisation,
            allow_synthetic=allow_synthetic_vendor_config,
            read_bytes=read_bytes,
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
        vendor_extractors=vendor_config.extractor_pins if vendor_config is not None else (),
        source_authority=(
            vendor_config.source_authority.pin if vendor_config is not None else None
        ),
        vendor_publication=(
            Pin(version=vendor_config.version, content_sha256=vendor_config.content_sha256)
            if vendor_config is not None
            else None
        ),
    )
    loaded = LoadedConfig(
        dictionary=dictionary,
        mapping_set=mapping_set,
        normalisation_policy=normalisation,
        rounding=rounding,
        definition_set=definitions,
        comparison_policy=comparison,
        alignment_rules=alignment,
        pinned=pinned,
        vendor_config=vendor_config,
    )
    loaded._loaded_config_root = config_root.absolute()
    return loaded


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
    if pinned.vendor_extractors != config.pinned.vendor_extractors:
        raise VersionContentDriftError(
            artifact="vendor_extractors",
            version=",".join(pin.version for pin in pinned.vendor_extractors),
            pinned_sha256=_vendor_pins_sha256(pinned),
            actual_sha256=_vendor_pins_sha256(config.pinned),
        )
    if pinned.source_authority != config.pinned.source_authority:
        expected = pinned.source_authority or Pin(version="absent", content_sha256="absent")
        actual = config.pinned.source_authority or Pin(version="absent", content_sha256="absent")
        raise VersionContentDriftError(
            artifact="source_authority",
            version=expected.version,
            pinned_sha256=expected.content_sha256,
            actual_sha256=actual.content_sha256,
        )
    if pinned.vendor_publication != config.pinned.vendor_publication:
        expected = pinned.vendor_publication or Pin(version="absent", content_sha256="absent")
        actual = config.pinned.vendor_publication or Pin(version="absent", content_sha256="absent")
        raise VersionContentDriftError(
            artifact="vendor_publication",
            version=expected.version,
            pinned_sha256=expected.content_sha256,
            actual_sha256=actual.content_sha256,
        )


def require_published_generation(
    config: LoadedConfig, *, config_root: Path
) -> PublishedVendorConfig:
    """Reverify the fixed publication path; public model construction grants no authority."""
    _require_publication_consistency(config)
    publication = config.vendor_config
    if publication is None:
        raise VendorConfigPublicationError(
            "authoritative v2 generation requires a verified vendor publication"
        )
    fresh = load_run_config(
        config_root,
        ConfigVersions.of(config.pinned),
        extractor_pins={
            Representation.XBRL: config.pinned.extractor_xbrl,
            Representation.PDF: config.pinned.extractor_pdf,
        },
        allow_synthetic_vendor_config=publication.state is PublicationState.SYNTHETIC,
    )
    require_pins(fresh, config.pinned)
    if fresh != config or fresh.vendor_config is None:
        raise VendorConfigPublicationError(
            "supplied config differs from the freshly verified fixed publication"
        )
    return fresh.vendor_config


def pin_published_generation(
    config: LoadedConfig,
    *,
    config_root: Path,
    repository: EvidenceRepository,
) -> PublishedVendorConfig:
    """Reverify and atomically pin the joined publication before a generation write."""
    publication = require_published_generation(config, config_root=config_root)
    repository.pin_versions_guarded(
        _repository_pins(config),
        required_database_prefix=(
            "eqos_test_" if publication.state is PublicationState.SYNTHETIC else None
        ),
    )
    return publication


def pin_config(
    config: LoadedConfig,
    *,
    repository: EvidenceRepository,
    pool: ConnectionPool,
    config_root: Path | None = None,
) -> int:
    """Pin every artifact on first use and publish the definition set; return the set's id.

    A version already pinned (or published) with other content raises
    ``VersionContentDriftError`` before anything of the run is written. The pins are stored
    before the definition set's connection is taken, so one pooled connection suffices.
    """
    if not repository.uses_pool(pool):
        raise ValueError("repository and comparison runner must use the same connection pool")
    _require_publication_consistency(config)
    if mapping_requires_publication(config.mapping_set):
        assert config.vendor_config is not None
        origin = config_root or config._loaded_config_root
        if origin is None:
            raise VendorConfigPublicationError(
                "published config must be reloaded from its fixed artifact root before pinning"
            )
        require_published_generation(config, config_root=origin)
    repository.pin_versions_guarded(
        _repository_pins(config),
        required_database_prefix=(
            "eqos_test_"
            if config.vendor_config is not None
            and config.vendor_config.state is PublicationState.SYNTHETIC
            else None
        ),
    )
    with pool.connection() as conn:
        return publish_definition_set(conn, config.definition_set)


def _require_publication_consistency(config: LoadedConfig) -> None:
    """Refuse every inconsistent mapping/publication/pin combination before persistence."""
    required = mapping_requires_publication(config.mapping_set)
    publication = config.vendor_config
    if required and publication is None:
        raise VendorConfigPublicationError(
            "vendor mapping persistence requires a verified publication"
        )
    if not required and publication is not None:
        raise VendorConfigPublicationError(
            "a vendor publication cannot be attached to a first-party-only mapping set"
        )
    if publication is None:
        if (
            config.pinned.vendor_extractors
            or config.pinned.source_authority is not None
            or config.pinned.vendor_publication is not None
        ):
            raise VendorConfigPublicationError(
                "vendor pins require the matching verified publication model"
            )
        return
    expected_publication = Pin(
        version=publication.version,
        content_sha256=publication.content_sha256,
    )
    if config.pinned.vendor_publication != expected_publication:
        raise VendorConfigPublicationError(
            "vendor publication model differs from its persisted publication pin"
        )
    if config.pinned.source_authority != publication.source_authority.pin:
        raise VendorConfigPublicationError(
            "vendor publication model differs from its source-authority pin"
        )
    if config.pinned.vendor_extractors != publication.extractor_pins:
        raise VendorConfigPublicationError(
            "vendor publication model differs from its extractor pins"
        )


def _repository_pins(config: LoadedConfig) -> list[VersionPin]:
    """The exact joined pins written before any run or published generation."""
    pins = [
        VersionPin(artifact=name, version=pin.version, content_sha256=pin.content_sha256)
        for name in _PIN_FIELDS
        for pin in (getattr(config.pinned, name),)
    ]
    if config.vendor_config is not None:
        publication = config.vendor_config
        pins.extend(
            [
                VersionPin(
                    artifact="vendor_publication",
                    version=publication.version,
                    content_sha256=publication.content_sha256,
                ),
                VersionPin(
                    artifact="source_authority",
                    version=publication.source_authority.pin.version,
                    content_sha256=publication.source_authority.pin.content_sha256,
                ),
                *(
                    VersionPin(
                        artifact=_vendor_extractor_artifact(pin.source_id, pin.surface),
                        version=pin.version,
                        content_sha256=pin.content_sha256,
                    )
                    for pin in publication.extractor_pins
                ),
            ]
        )
    return pins


def _file(config_root: Path, directory: str, version: str) -> Path:
    """``<config_root>/<directory>/<version>.yaml``."""
    return config_root / directory / f"{version}{YAML_SUFFIX}"


def _config_snapshot_reader(config_root: Path) -> Callable[[Path], bytes]:
    """Cache bounded no-follow descriptor snapshots for one complete config load."""
    root = config_root.absolute()
    snapshots: dict[str, bytes] = {}

    def read_bytes(path: Path) -> bytes:
        try:
            relative = path.absolute().relative_to(root).as_posix()
            if relative not in snapshots:
                snapshots[relative] = read_safe(root, relative)
            return snapshots[relative]
        except (UnsafeVendorConfigPathError, ValueError) as error:
            raise VendorConfigPublicationError(str(error)) from error

    return read_bytes


def _vendor_pins_sha256(pinned: PinnedVersions) -> str:
    digest = hashlib.sha256()
    for pin in pinned.vendor_extractors:
        digest.update(pin.source_id.encode("utf-8") + b"\0")
        digest.update(pin.surface.encode("utf-8") + b"\0")
        digest.update(pin.version.encode("utf-8") + b"\0")
        digest.update(pin.content_sha256.encode("ascii") + b"\n")
    return digest.hexdigest()


def _vendor_extractor_artifact(source_id: str, surface: str) -> str:
    identity = hashlib.sha256(source_id.encode() + b"\0" + surface.encode()).hexdigest()
    return f"vendor_extractor:{identity}"
