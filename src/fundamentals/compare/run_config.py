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
from fundamentals.contracts.config_versions import DEFAULT_VERSION as DEFAULT_VERSION
from fundamentals.contracts.config_versions import ConfigVersions as ConfigVersions
from fundamentals.contracts.evidence import PinnedVersions, VendorExtractorPin
from fundamentals.contracts.evidence import VersionPin as Pin
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence import vendor_screener, vendor_tijori, vendor_upstox
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
        "extract/pdf_figure_columns.py",
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
_VENDOR_INGEST = "evidence/vendor_ingest.py"
# Per vendor source: the extractor version and the adapter, parser and identity/basis check
# source files it hashes.
VENDOR_EXTRACTORS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    vendor_screener.SOURCE: (
        vendor_screener.EXTRACTOR_VERSION,
        (
            "evidence/vendor_screener.py",
            "ingest/screener_financials_models.py",
            "ingest/screener_financials_schedules.py",
            "ingest/screener_financials_shapes.py",
            "ingest/screener_financials_tables.py",
            "ingest/screener_session_models.py",
            "ingest/screener_session_page.py",
            _VENDOR_INGEST,
        ),
    ),
    vendor_tijori.SOURCE_ID: (
        vendor_tijori.EXTRACTOR_VERSION,
        (
            "evidence/vendor_tijori.py",
            "ingest/tijori_source.py",
            "ingest/tijori_page.py",
            "ingest/tijori_tables.py",
            "ingest/tijori_common.py",
            _VENDOR_INGEST,
        ),
    ),
    vendor_upstox.SOURCE_ID: (
        vendor_upstox.EXTRACTOR_VERSION,
        (
            "evidence/vendor_upstox.py",
            "ingest/upstox_statements.py",
            "ingest/upstox_source.py",
            "ingest/upstox_retention.py",
            "verify/crossfoot.py",
            _VENDOR_INGEST,
        ),
    ),
}
# Bump on any change to how the engine turns pinned inputs into results: replay refuses a run
# recorded under other semantics rather than recomputing it differently.
_SEMANTICS_VERSION = "d1b"
COMPARISON_SEMANTICS = Pin(
    version=_SEMANTICS_VERSION,
    content_sha256=hashlib.sha256(_SEMANTICS_VERSION.encode("utf-8")).hexdigest(),
)
_SEMANTICS = "run was compared under semantics {recorded}; this code compares under {current}"
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


class ComparisonSemanticsError(ValueError):
    """A run's recorded comparison semantics are not the ones this code computes."""


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
    return Pin(
        version=chosen, content_sha256=_sources_sha256(chosen, EXTRACTOR_SOURCES[representation])
    )


def vendor_extractor_pin(
    source_id: str, surface: str, *, version: str | None = None
) -> VendorExtractorPin:
    """A vendor surface's extractor version (current unless named) plus its sources' bytes."""
    current, sources = VENDOR_EXTRACTORS[source_id]
    version = current if version is None else version
    return VendorExtractorPin(
        source_id=source_id,
        surface=surface,
        version=version,
        content_sha256=_sources_sha256(version, sources),
    )


def _sources_sha256(version: str, sources: tuple[str, ...]) -> str:
    """SHA-256 over a version and each named source file's path and bytes."""
    digest = hashlib.sha256(version.encode("utf-8") + b"\0")
    for relative in sources:
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256((_SOURCE_ROOT / relative).read_bytes()).digest())
    return digest.hexdigest()


def load_run_config(
    config_root: Path,
    versions: ConfigVersions | None = None,
    *,
    extractor_pins: Mapping[Representation, Pin] | None = None,
    vendors: tuple[tuple[str, str], ...] = (),
    vendor_pins: tuple[VendorExtractorPin, ...] | None = None,
) -> LoadedConfig:
    """Load every artifact at its version and compute its pin (nothing is stored here).

    Vendor extractor pins are computed for ``vendors`` unless ``vendor_pins`` stand.
    """
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
        vendor_extractors=(
            tuple(vendor_extractor_pin(*vendor) for vendor in vendors)
            if vendor_pins is None
            else vendor_pins
        ),
        comparison_semantics=COMPARISON_SEMANTICS,
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
    if pinned.comparison_semantics != config.pinned.comparison_semantics:
        recorded = pinned.comparison_semantics
        raise ComparisonSemanticsError(
            _SEMANTICS.format(
                recorded=recorded and recorded.version,
                current=_SEMANTICS_VERSION,
            )
        )
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
    if config.pinned.vendor_extractors != pinned.vendor_extractors:
        raise VersionContentDriftError(
            artifact="vendor_extractors",
            version=",".join(pin.version for pin in pinned.vendor_extractors),
            pinned_sha256=",".join(pin.content_sha256 for pin in pinned.vendor_extractors),
            actual_sha256=",".join(pin.content_sha256 for pin in config.pinned.vendor_extractors),
        )


def vendor_version_pin(pin: VendorExtractorPin) -> VersionPin:
    """A vendor extractor pin as its source-qualified ``eqos.version_pins`` row."""
    return VersionPin(
        artifact=f"vendor_extractor:{pin.source_id}",
        version=pin.version,
        content_sha256=pin.content_sha256,
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
        + [vendor_version_pin(pin) for pin in config.pinned.vendor_extractors]
    )
    with pool.connection() as conn:
        return publish_definition_set(conn, config.definition_set)


def _file(config_root: Path, directory: str, version: str) -> Path:
    """``<config_root>/<directory>/<version>.yaml``."""
    return config_root / directory / f"{version}{YAML_SUFFIX}"
