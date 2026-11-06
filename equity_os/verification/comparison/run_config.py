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

from equity_os.contracts.measurement.canonical import FIRST_PARTY_REPRESENTATIONS, Representation
from equity_os.contracts.measurement.evidence import (
    FilingFamily,
    PinnedVersions,
    VendorExtractorPin,
)
from equity_os.contracts.measurement.evidence import VersionPin as Pin
from equity_os.contracts.sourcing import source_catalog as catalog
from equity_os.contracts.verification.config_versions import DEFAULT_VERSION as DEFAULT_VERSION
from equity_os.contracts.verification.config_versions import ConfigVersions as ConfigVersions
from equity_os.contracts.verification.versioning import VersionContentDriftError
from equity_os.extraction.results_pdf.pdf_adapter import PDF_EXTRACTOR_VERSION
from equity_os.extraction.surfaces import vendor_shareholding
from equity_os.extraction.vendors.screener import vendor_screener
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.extraction.vendors.upstox import vendor_upstox
from equity_os.extraction.xbrl.shareholding_filing import SHP_EXTRACTOR_VERSION
from equity_os.extraction.xbrl.xbrl_adapter import XBRL_EXTRACTOR_VERSION
from equity_os.normalisation.derivation.interval import RoundingPolicy, load_rounding_policy
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary, load_dictionary
from equity_os.normalisation.mapping.alignment import AlignmentRuleSet, load_alignment_rules
from equity_os.normalisation.mapping.mapping import (
    MappingSet,
    NormalisationPolicy,
    load_mapping_set,
    load_normalisation_policy,
)
from equity_os.storage.records.repository import EvidenceRepository, VersionPin
from equity_os.verification.admission.vendor_first import (
    VendorFirstPolicy,
    load_vendor_first_policy,
)
from equity_os.verification.comparison.definitions import (
    DefinitionSet,
    load_definition_set,
    publish_definition_set,
)
from equity_os.verification.comparison.policy import ComparisonPolicy, load_comparison_policy

DICTIONARY_DIR = "normalisation/dictionary"
MAPPINGS_DIR = "normalisation/mappings"
NORMALISATION_POLICY_DIR = "normalisation/normalisation_policy"
ROUNDING_POLICY_DIR = "normalisation/rounding_policy"
DEFINITION_SETS_DIR = "verification/definition_sets"
COMPARISON_POLICY_DIR = "verification/comparison_policy"
ALIGNMENT_DIR = "alignment"
VENDOR_FIRST_POLICY_DIR = "verification/vendor_first/policy"
ELIGIBILITY_DIR = "verification/vendor_first/eligibility"
YAML_SUFFIX = ".yaml"
_SOURCE_ROOT = Path(__file__).resolve().parents[2]
# Extractor content sources (design decision 7), relative to the ``equity_os`` package.
EXTRACTOR_SOURCES: Mapping[Representation, tuple[str, ...]] = {
    Representation.XBRL: (
        "extraction/xbrl/xbrl_adapter.py",
        "extraction/xbrl/xbrl_parser.py",
        "extraction/xbrl/xbrl_taxonomies.py",
        "extraction/xbrl/xbrl_dimensions.py",
        "extraction/packages/first_party_extract.py",
        "extraction/packages/member_identity.py",
    ),
    Representation.PDF: (
        "extraction/results_pdf/pdf_adapter.py",
        "extraction/results_pdf/pdf_statement_pages.py",
        "extraction/results_pdf/pdf_figure_columns.py",
        "extraction/results_pdf/pdf_header_text.py",
        "extraction/results_pdf/pdf_printed_unit.py",
        "extraction/packages/first_party_extract.py",
        "extraction/packages/member_identity.py",
        "extraction/results_pdf/pdf_source.py",
    ),
}
# The SHP adapter (``nse-shp-v4``) and every parser and identity module it imports (plan D8 R6).
SHP_EXTRACTOR_SOURCES = (
    "extraction/xbrl/shareholding_filing.py",
    "extraction/xbrl/xbrl_adapter.py",
    "extraction/xbrl/xbrl_parser.py",
    "extraction/xbrl/xbrl_dimensions.py",
    "extraction/packages/member_identity.py",
    "extraction/xbrl/xbrl_identity.py",
)
EXTRACTOR_VERSIONS: Mapping[Representation, str] = {
    Representation.XBRL: XBRL_EXTRACTOR_VERSION,
    Representation.PDF: PDF_EXTRACTOR_VERSION,
}
_VENDOR_INGEST = "extraction/surfaces/vendor_ingest.py"
_SCREENER_SHP = (
    vendor_shareholding.SCREENER_VERSION,
    (
        "extraction/surfaces/vendor_shareholding.py",
        *(
            f"extraction/vendors/screener/screener_{name}.py"
            for name in ("shareholding", "company_artifacts")
        ),
        *(
            f"extraction/vendors/screener/screener_{name}.py"
            for name in ("company_discovery", "company_models")
        ),
        *(
            f"extraction/vendors/screener/screener_{name}.py"
            for name in ("financials_models", "financials_tables")
        ),
        *(
            f"extraction/vendors/screener/screener_{name}.py"
            for name in ("session_models", "session_page")
        ),
        _VENDOR_INGEST,
    ),
)
_TIJORI_SHP = ("shareholding", "shareholding_table", "shareholding_breakup", "page", "tables")
# Per ``(source, surface)``, else per source: the version and the files hashed (adapter, parser
# and any config the extractor reads).
VENDOR_EXTRACTORS: Mapping[str | tuple[str, str], tuple[str, tuple[str, ...]]] = {
    catalog.SCREENER_SHAREHOLDING: _SCREENER_SHP,
    catalog.SCREENER_INVESTORS: _SCREENER_SHP,
    catalog.TIJORI_SHAREHOLDING: (
        vendor_shareholding.TIJORI_VERSION,
        (
            "extraction/surfaces/vendor_shareholding.py",
            *(f"extraction/vendors/tijori/tijori_{name}.py" for name in (*_TIJORI_SHP, "common")),
            _VENDOR_INGEST,
        ),
    ),
    catalog.UPSTOX_SHAREHOLDING: (
        vendor_shareholding.UPSTOX_VERSION,
        (
            "extraction/surfaces/vendor_shareholding.py",
            "sourcing/vendors/upstox/upstox_retention.py",
            _VENDOR_INGEST,
        ),
    ),
    vendor_screener.SOURCE: (
        vendor_screener.EXTRACTOR_VERSION,
        (
            "extraction/vendors/screener/vendor_screener.py",
            "extraction/vendors/screener/screener_financials_models.py",
            "extraction/vendors/screener/screener_financials_schedules.py",
            "extraction/vendors/screener/screener_financials_shapes.py",
            "extraction/vendors/screener/screener_financials_tables.py",
            "extraction/vendors/screener/screener_session_models.py",
            "extraction/vendors/screener/screener_session_page.py",
            _VENDOR_INGEST,
        ),
    ),
    vendor_tijori.SOURCE_ID: (
        vendor_tijori.EXTRACTOR_VERSION,
        (
            "extraction/vendors/tijori/vendor_tijori.py",
            "sourcing/vendors/tijori/tijori_source.py",
            "extraction/vendors/tijori/tijori_page.py",
            "extraction/vendors/tijori/tijori_tables.py",
            "extraction/vendors/tijori/tijori_common.py",
            _VENDOR_INGEST,
            "../config/normalisation/mappings/tijori/v5/display.yaml",  # the extractor's rules
        ),
    ),
    vendor_upstox.SOURCE_ID: (
        vendor_upstox.EXTRACTOR_VERSION,
        (
            "extraction/vendors/upstox/vendor_upstox.py",
            "extraction/vendors/upstox/upstox_statements.py",
            "sourcing/vendors/upstox/upstox_source.py",
            "sourcing/vendors/upstox/upstox_retention.py",
            "verification/comparison/crossfoot.py",
            _VENDOR_INGEST,
        ),
    ),
}
# Digest of each moved source set -> the digest already stored for it.
MOVED_PINS: Mapping[str, str] = {
    "1ee784a53b5ce4081349dbdb4a7436d31a6277c1fad1b4b1b589f82a17e8d97a": "cd34d844054ae9f79201765b55bf376f9fb159937fc73ae17082c573d26a088c",  # noqa: E501
    "3b2e2dbcc9ecf5e79ea438e4f5642cb092879041b6d56ccb54f95205a6f3f7fa": "dfd1d76afa25525643aebf435b5fa4ae93ffa74483a13fb3fd221b18697c0caa",  # noqa: E501
    "378b4eb101817ce2119a1a3bfb6e2740a20e13f85140bd337c297788414b6c32": "9ffad9ac400ba8913edf7bdc69151ce24448ed53311ee4d9c7e82f64d90b15a0",  # noqa: E501
    "97884887a035309623a94c16402aa0245e8d45ef5ee8c08cf012d77e5fa25ac4": "f7f3689c338667cae8a99adcc2ba4bf0fade9294a3ccea690c3b63c57f099901",  # noqa: E501
    "53f96f8d9c650d80ed4b431fbb397ddb5b405fad221cc8fa98666269bb3b1270": "351b2aed43565d6191d1afb5ffeeb568f9d03ede9cd55a41ba96b06611249478",  # noqa: E501
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
# Pinned only when the run names a version (VENDOR-1 §6.4, §6.6).
_OPTIONAL_PINS = ("vendor_first_policy", "eligibility")


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
    vendor_first_policy: VendorFirstPolicy | None
    pinned: PinnedVersions


def extractor_pin(
    representation: Representation,
    *,
    version: str | None = None,
    family: FilingFamily = FilingFamily.FINANCIAL_RESULTS,
) -> Pin:
    """The chosen extractor version plus its current source files' bytes.

    Ingestion may explicitly name a re-extraction version; comparison defaults to the
    current adapter version. Both paths use the same content hashing contract. The
    shareholding family has its own XBRL extractor (plan D8 R6).
    """
    if family is FilingFamily.SHAREHOLDING:
        if representation is not Representation.XBRL:
            raise ValueError(f"the shareholding family has no {representation} extractor")
        chosen = SHP_EXTRACTOR_VERSION if version is None else version
        return Pin(version=chosen, content_sha256=_sources_sha256(chosen, SHP_EXTRACTOR_SOURCES))
    chosen = EXTRACTOR_VERSIONS[representation] if version is None else version
    return Pin(
        version=chosen, content_sha256=_sources_sha256(chosen, EXTRACTOR_SOURCES[representation])
    )


def vendor_extractor_pin(
    source_id: str, surface: str, *, version: str | None = None
) -> VendorExtractorPin:
    """A vendor surface's extractor version (current unless named) plus its sources' bytes."""
    current, sources = VENDOR_EXTRACTORS.get((source_id, surface)) or VENDOR_EXTRACTORS[source_id]
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
    return MOVED_PINS.get(digest.hexdigest(), digest.hexdigest())


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
    policy = (
        None
        if chosen.vendor_first_policy is None
        else load_vendor_first_policy(
            _file(config_root, VENDOR_FIRST_POLICY_DIR, chosen.vendor_first_policy)
        )
    )
    eligibility = (
        None
        if chosen.eligibility is None
        else Pin(
            version=chosen.eligibility,
            content_sha256=hashlib.sha256(
                _file(config_root, ELIGIBILITY_DIR, chosen.eligibility).read_bytes()
            ).hexdigest(),
        )
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
        vendor_first_policy=None
        if policy is None
        else Pin(version=policy.version, content_sha256=policy.content_sha256),
        eligibility=eligibility,
    )
    return LoadedConfig(
        dictionary=dictionary,
        mapping_set=mapping_set,
        normalisation_policy=normalisation,
        rounding=rounding,
        definition_set=definitions,
        comparison_policy=comparison,
        alignment_rules=alignment,
        vendor_first_policy=policy,
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
    for name in (*_PIN_FIELDS, "definition_set", *_OPTIONAL_PINS):
        expected: Pin | None = getattr(pinned, name)
        actual: Pin | None = getattr(config.pinned, name)
        if expected != actual:
            raise VersionContentDriftError(
                artifact=name,
                version=str(expected and expected.version),
                pinned_sha256=str(expected and expected.content_sha256),
                actual_sha256=str(actual and actual.content_sha256),
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
            for name in (*_PIN_FIELDS, *_OPTIONAL_PINS)
            for pin in (getattr(config.pinned, name),)
            if pin is not None
        ]
        + [vendor_version_pin(pin) for pin in config.pinned.vendor_extractors]
    )
    with pool.connection() as conn:
        return publish_definition_set(conn, config.definition_set)


def _file(config_root: Path, directory: str, version: str) -> Path:
    """``<config_root>/<directory>/<version>.yaml``."""
    return config_root / directory / f"{version}{YAML_SUFFIX}"
