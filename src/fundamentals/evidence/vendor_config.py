"""Load one immutable joined vendor configuration release.

``RELEASED`` requires the fixed committed config root plus a coordinator receipt that binds the
reviewed candidate, exact selected bytes and review result through first-parent history. Reviewer
identity remains an operational repository-workflow fact. Test releases are explicitly
``SYNTHETIC`` and are refused from the committed root.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from enum import StrEnum
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fundamentals.canon.dictionary import KNOWN_FILES, CanonicalDictionary
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import VendorExtractorPin, VersionPin
from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SourceDescriptor,
    SurfaceAuthority,
    UnknownSourceError,
)
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.mapping import MappingSet, NormalisationPolicy
from fundamentals.evidence.mapping_models import ConstructionRule, MappingEntry
from fundamentals.evidence.vendor_config_files import (
    PublishedAuthority,
    SourceAuthorityArtifact,
    SourceAuthorityReference,
    UnsafeVendorConfigPathError,
    VendorAuthorityEvidenceError,
    canonical_relative_path,
    canonical_version,
    read_safe,
    selected_release_members,
    validate_authority_evidence,
)
from fundamentals.evidence.vendor_publication_receipt import (
    ReleaseReviewReceipt as _ReleaseReviewReceipt,
)
from fundamentals.evidence.vendor_publication_receipt import (
    VendorPublicationReceiptError,
    verify_release_receipt,
)
from fundamentals.evidence.vendor_screener import PAGE_SCHEMA, SCHEDULE_SCHEMA

__all__ = [
    "ContentMember",
    "PublicationState",
    "PublishedVendorConfig",
    "SCREENER_EXTRACTOR_SOURCES",
    "SCREENER_EXTRACTOR_VERSION",
    "SurfaceDisposition",
    "VendorConfigPublicationError",
    "code_bundle_pin",
    "load_published_vendor_config",
    "vendor_extractor_pin",
]

PUBLICATION_DIR = "vendor_publication"
SOURCE_AUTHORITY_DIR = "source_authority"
REVIEW_RECEIPT_SUFFIX = ".review.yaml"
SCREENER_EXTRACTOR_VERSION = "screener-v1"
SCREENER_EXTRACTOR_SOURCES = (
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
SCREENER_SOURCE = "screener-subscriber"
SCREENER_SURFACES = frozenset({"SCREENER_FINANCIALS", "SCREENER_SCHEDULE"})
FIRST_PARTY_MAPPING_SURFACES = frozenset({"NSE_XBRL_INSTANCE", "NSE_RESULTS_PDF"})
SCREENER_SCHEMA_IDENTITIES = {
    "SCREENER_FINANCIALS": frozenset({PAGE_SCHEMA}),
    "SCREENER_SCHEDULE": frozenset({SCHEDULE_SCHEMA}),
}
A05_SUBSCRIBER_DECISION = "docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md"
UPSTOX_ROLE_DECISION = (
    "docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md"
)
PRIVATE_SUBSCRIBER_BOUNDARY = "PRIVATE_PERSONAL_NON_COMMERCIAL_INTERNAL"

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_COMMITTED_CONFIG_ROOT = _REPOSITORY_ROOT / "config"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _canonical_relative_path(value: str) -> str:
    return canonical_relative_path(value)


def _canonical_version(value: str) -> str:
    try:
        return canonical_version(value)
    except ValueError as error:
        raise VendorConfigPublicationError(str(error)) from error


class VendorConfigPublicationError(ValueError):
    """The joined release is missing, incomplete, unsafe or internally inconsistent."""


class PublicationState(StrEnum):
    """Whether a release is committed production config or an isolated test artifact."""

    RELEASED = "RELEASED"
    SYNTHETIC = "SYNTHETIC"


class SurfaceDisposition(StrEnum):
    """Whether one source surface is usable in this release."""

    INCLUDED = "INCLUDED"
    UNAVAILABLE = "UNAVAILABLE"
    EXCLUDED = "EXCLUDED"


class ContentMember(BaseModel):
    """One exact repository/config-relative file in a joined artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return _canonical_relative_path(value)


class SurfaceLedgerEntry(BaseModel):
    """One explicit included, unavailable or excluded vendor surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    representation: Representation
    disposition: SurfaceDisposition
    reason: str = Field(min_length=1)


class ExtractorBundle(VendorExtractorPin):
    """A vendor extractor pin plus every source file that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    members: tuple[ContentMember, ...] = Field(min_length=1)
    supported_schema_identities: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_members(self) -> ExtractorBundle:
        paths = [member.path for member in self.members]
        if len(paths) != len(set(paths)):
            raise ValueError("extractor bundle contains duplicate members")
        if len(self.supported_schema_identities) != len(set(self.supported_schema_identities)):
            raise ValueError("extractor bundle contains duplicate schema identities")
        return self


class _PublicationFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    state: PublicationState
    dictionary: VersionPin
    formula_set: VersionPin
    mapping_set: VersionPin
    normalisation_policy: VersionPin
    mapping_members: tuple[ContentMember, ...] = Field(min_length=1)
    source_authority: SourceAuthorityReference
    surface_ledger: tuple[SurfaceLedgerEntry, ...] = Field(min_length=1)
    extractor_bundles: tuple[ExtractorBundle, ...] = ()

    @model_validator(mode="after")
    def _unique_identities(self) -> _PublicationFile:
        member_paths = [member.path for member in self.mapping_members]
        surfaces = [(item.source_id, item.surface) for item in self.surface_ledger]
        extractors = [(item.source_id, item.surface) for item in self.extractor_bundles]
        if len(member_paths) != len(set(member_paths)):
            raise ValueError("publication contains duplicate mapping members")
        if len(surfaces) != len(set(surfaces)):
            raise ValueError("publication contains conflicting surface declarations")
        if len(extractors) != len(set(extractors)):
            raise ValueError("publication contains conflicting extractor bundles")
        return self


class PublishedVendorConfig(BaseModel):
    """A fully resolved mapping/authority/policy/extractor publication."""

    model_config = ConfigDict(frozen=True)

    version: str
    state: PublicationState
    content_sha256: str
    dictionary: VersionPin
    formula_set: VersionPin
    mapping_set: VersionPin
    normalisation_policy: VersionPin
    mapping_members: tuple[ContentMember, ...]
    source_authority: PublishedAuthority
    surface_ledger: tuple[SurfaceLedgerEntry, ...]
    extractor_bundles: tuple[ExtractorBundle, ...]
    authorities: tuple[SurfaceAuthority, ...]
    catalog: SourceCatalog

    @property
    def published_config_sha256(self) -> str:
        """The receipt-verified publication digest bound into generation handoffs."""
        return self.content_sha256

    @property
    def extractor_pins(self) -> tuple[VendorExtractorPin, ...]:
        """The source-qualified pins persisted in run manifests."""
        return tuple(
            VendorExtractorPin(
                source_id=bundle.source_id,
                surface=bundle.surface,
                version=bundle.version,
                content_sha256=bundle.content_sha256,
            )
            for bundle in self.extractor_bundles
        )


def code_bundle_pin(
    version: str,
    relative_files: Sequence[str],
    *,
    source_root: Path = _SOURCE_ROOT,
) -> VersionPin:
    """Hash a version and exact source bytes using the shared extractor-pin algorithm."""
    if not version or not relative_files:
        raise ValueError("a code bundle requires a version and at least one source file")
    paths = tuple(ContentMember(path=name, content_sha256="0" * 64).path for name in relative_files)
    if len(paths) != len(set(paths)):
        raise ValueError("a code bundle cannot contain duplicate source files")
    digest = hashlib.sha256(version.encode("utf-8") + b"\0")
    for relative in paths:
        body = _read_safe(source_root, relative)
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(body).digest())
    return VersionPin(version=version, content_sha256=digest.hexdigest())


def vendor_extractor_pin(
    source_id: str,
    surface: str,
    version: str,
    relative_files: Sequence[str],
    *,
    source_root: Path = _SOURCE_ROOT,
) -> VendorExtractorPin:
    """Return the source-qualified pin of one real vendor adapter/parser bundle."""
    code_pin = code_bundle_pin(version, relative_files, source_root=source_root)
    return VendorExtractorPin(
        source_id=source_id,
        surface=surface,
        version=code_pin.version,
        content_sha256=code_pin.content_sha256,
    )


def mapping_requires_publication(mapping_set: MappingSet) -> bool:
    """Whether any mapping is not source-qualified for the first-party package boundary."""
    return any(not _legacy_first_party_mapping(item) for item in mapping_set.entries) or any(
        not _legacy_first_party_mapping(item) for item in mapping_set.constructions
    )


def _legacy_first_party_mapping(item: MappingEntry | ConstructionRule) -> bool:
    if item.surface not in FIRST_PARTY_MAPPING_SURFACES:
        return False
    if item.source is None:
        return True
    try:
        return BUILTIN_SOURCES.describe(item.source).source_class is SourceClass.FIRST_PARTY
    except UnknownSourceError:
        return False


def validate_mapping_member_paths(
    mapping_root: Path,
    version: str,
    *,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> tuple[str, ...]:
    """Return the exact member list after refusing escapes and malformed indexes."""
    _canonical_version(version)
    index_relative = f"{version}.yaml"
    try:
        index = yaml.safe_load(_read_member(mapping_root, index_relative, read_bytes))
        if not isinstance(index, dict):
            raise TypeError("mapping index is not an object")
        if index.get("version") != version:
            raise ValueError("mapping index version mismatch")
        allowed = {
            "version",
            "normalisation_policy_version",
            "entry_files",
            "construction_files",
            "statement_anchor_files",
        }
        if set(index) - allowed:
            raise ValueError("mapping index contains unsupported fields")
        names = [
            *index["entry_files"],
            *index.get("construction_files", ()),
            *index.get("statement_anchor_files", ()),
        ]
        if not names or not all(isinstance(name, str) for name in names):
            raise ValueError("mapping index members are nonempty relative paths")
        members = tuple(ContentMember(path=name, content_sha256="0" * 64).path for name in names)
        if len(members) != len(set(members)):
            raise ValueError("mapping index contains duplicate members")
        for member in members:
            _read_member(mapping_root, member, read_bytes)
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as error:
        raise VendorConfigPublicationError(
            f"unsafe or invalid mapping index {version!r}: {error}"
        ) from error
    return (f"mappings/{version}.yaml", *(f"mappings/{name}" for name in members))


def load_published_vendor_config(
    config_root: Path,
    version: str,
    *,
    dictionary: CanonicalDictionary,
    mapping_set: MappingSet,
    normalisation_policy: NormalisationPolicy,
    allow_synthetic: bool = False,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> PublishedVendorConfig:
    """Resolve and validate every member of one joined vendor release."""
    _canonical_version(version)
    publication_relative = f"{PUBLICATION_DIR}/{version}.yaml"
    try:
        publication_body = _read_member(config_root, publication_relative, read_bytes)
    except (FileNotFoundError, VendorConfigPublicationError) as error:
        raise VendorConfigPublicationError(
            f"published vendor configuration {version!r} is required before runtime use"
        ) from error
    try:
        document = _PublicationFile.model_validate(yaml.safe_load(publication_body))
    except (ValidationError, yaml.YAMLError) as error:
        raise VendorConfigPublicationError(
            f"invalid vendor publication {version!r}: {error}"
        ) from error
    publication_sha256 = hashlib.sha256(publication_body).hexdigest()
    receipt = _require_state(
        document,
        config_root,
        publication_sha256=publication_sha256,
        allow_synthetic=allow_synthetic,
        read_bytes=read_bytes,
    )
    if document.version != version or document.mapping_set.version != version:
        raise VendorConfigPublicationError("publication and mapping-set versions must match")
    if PurePosixPath(document.source_authority.path).parts[0] != SOURCE_AUTHORITY_DIR:
        raise VendorConfigPublicationError("source authority must resolve under source_authority/")

    actual_dictionary = VersionPin(
        version=dictionary.version, content_sha256=dictionary.content_sha256
    )
    actual_formula = VersionPin(
        version=dictionary.formula_set_version,
        content_sha256=dictionary.formula_set_sha256,
    )
    actual_mapping = VersionPin(
        version=mapping_set.version, content_sha256=mapping_set.content_sha256
    )
    actual_normalisation = VersionPin(
        version=normalisation_policy.version,
        content_sha256=normalisation_policy.content_sha256,
    )
    _require_pin("dictionary", document.dictionary, actual_dictionary)
    _require_pin("formula_set", document.formula_set, actual_formula)
    _require_pin("mapping_set", document.mapping_set, actual_mapping)
    _require_pin("normalisation_policy", document.normalisation_policy, actual_normalisation)
    if mapping_set.normalisation_policy_version != normalisation_policy.version:
        raise VendorConfigPublicationError(
            "mapping set and normalisation policy versions are incompatible"
        )

    expected_members = validate_mapping_member_paths(
        config_root / "mappings", version, read_bytes=read_bytes
    )
    if tuple(member.path for member in document.mapping_members) != expected_members:
        raise VendorConfigPublicationError(
            "publication mapping members differ from the index and every resolved member"
        )
    for member in document.mapping_members:
        _require_content(
            config_root,
            member,
            artifact="mapping member",
            read_bytes=read_bytes,
        )

    authority_body = _read_member(config_root, document.source_authority.path, read_bytes)
    authority_actual = VersionPin(
        version=document.source_authority.version,
        content_sha256=hashlib.sha256(authority_body).hexdigest(),
    )
    _require_pin("source_authority", document.source_authority, authority_actual)
    try:
        authority = SourceAuthorityArtifact.model_validate(yaml.safe_load(authority_body))
    except (ValidationError, yaml.YAMLError) as error:
        raise VendorConfigPublicationError(f"invalid source authority artifact: {error}") from error
    if authority.version != document.source_authority.version:
        raise VendorConfigPublicationError(
            "source authority version differs from its publication pin"
        )

    authority_evidence = _validate_authority_evidence(authority, state=document.state)
    catalog = _catalog(authority)
    _validate_surfaces(document, authority, catalog)
    _validate_mapping_surfaces(mapping_set, document, catalog)
    for bundle in document.extractor_bundles:
        _validate_bundle(bundle, state=document.state)
    if receipt is not None:
        selected = _selected_release_members(
            document,
            publication_relative=publication_relative,
            authority_evidence=authority_evidence,
        )
        _verify_release_receipt(
            receipt,
            version=version,
            selected_paths=selected,
            receipt_relative=f"config/{PUBLICATION_DIR}/{version}{REVIEW_RECEIPT_SUFFIX}",
        )

    return PublishedVendorConfig(
        version=document.version,
        state=document.state,
        content_sha256=publication_sha256,
        dictionary=document.dictionary,
        formula_set=document.formula_set,
        mapping_set=document.mapping_set,
        normalisation_policy=document.normalisation_policy,
        mapping_members=document.mapping_members,
        source_authority=PublishedAuthority(
            path=document.source_authority.path,
            pin=VersionPin(
                version=document.source_authority.version,
                content_sha256=document.source_authority.content_sha256,
            ),
        ),
        surface_ledger=document.surface_ledger,
        extractor_bundles=document.extractor_bundles,
        authorities=authority.surfaces,
        catalog=catalog,
    )


def _require_state(
    document: _PublicationFile,
    config_root: Path,
    *,
    publication_sha256: str,
    allow_synthetic: bool,
    read_bytes: Callable[[Path], bytes] | None,
) -> _ReleaseReviewReceipt | None:
    committed = config_root.absolute() == _COMMITTED_CONFIG_ROOT.absolute()
    if document.state is PublicationState.SYNTHETIC:
        if not allow_synthetic or committed:
            raise VendorConfigPublicationError(
                "synthetic vendor configuration is allowed only in an isolated test root"
            )
        return None
    if not committed:
        raise VendorConfigPublicationError(
            "a released vendor configuration must come from the committed repository config root"
        )
    relative = f"{PUBLICATION_DIR}/{document.version}{REVIEW_RECEIPT_SUFFIX}"
    try:
        body = _read_member(config_root, relative, read_bytes)
        receipt = _ReleaseReviewReceipt.model_validate(yaml.safe_load(body))
    except (OSError, ValidationError, yaml.YAMLError, VendorConfigPublicationError) as error:
        raise VendorConfigPublicationError(
            f"commit-backed review receipt {relative!r} is required for RELEASED"
        ) from error
    if (
        receipt.publication_version != document.version
        or receipt.publication_sha256 != publication_sha256
    ):
        raise VendorConfigPublicationError(
            "review receipt subject differs from the selected publication"
        )
    return receipt


def _catalog(authority: SourceAuthorityArtifact) -> SourceCatalog:
    catalog = BUILTIN_SOURCES
    for declaration in authority.sources:
        if declaration.source_id == "upstox" and (
            declaration.source_class is not SourceClass.DERIVED
            or declaration.evidence_role is not EvidenceRole.DIAGNOSTIC_ONLY
        ):
            raise VendorConfigPublicationError(
                "Upstox may be declared only as derived and diagnostic-only"
            )
        try:
            existing = catalog.describe(declaration.source_id)
        except UnknownSourceError:
            catalog = catalog.extend(
                SourceDescriptor(
                    source_id=declaration.source_id,
                    source_class=declaration.source_class,
                    evidence_role=declaration.evidence_role,
                )
            )
            continue
        if (
            existing.source_id != declaration.source_id
            or existing.source_class is not declaration.source_class
            or existing.evidence_role is not declaration.evidence_role
        ):
            raise VendorConfigPublicationError(
                f"source declaration {declaration.source_id!r} would reclassify a built-in source"
            )
    return catalog


def _validate_surfaces(
    document: _PublicationFile,
    authority: SourceAuthorityArtifact,
    catalog: SourceCatalog,
) -> None:
    ledger = {(item.source_id, item.surface): item for item in document.surface_ledger}
    authorities = {(item.source_id, item.surface): item for item in authority.surfaces}
    bundles = {(item.source_id, item.surface): item for item in document.extractor_bundles}
    if any(item.source_id == "upstox" for item in authority.surfaces):
        raise VendorConfigPublicationError(
            "Upstox role classification grants no SurfaceAuthority or retention rights"
        )
    for identity, item in ledger.items():
        try:
            descriptor = catalog.describe(item.source_id)
        except UnknownSourceError as error:
            raise VendorConfigPublicationError(
                f"surface ledger names unknown source {item.source_id!r}"
            ) from error
        if descriptor.source_class is not SourceClass.DERIVED:
            raise VendorConfigPublicationError(
                "vendor surface ledger cannot redefine first-party identity"
            )
        surface_authority = authorities.get(identity)
        if item.disposition is SurfaceDisposition.EXCLUDED:
            if surface_authority is not None or identity in bundles:
                raise VendorConfigPublicationError(
                    "an excluded surface cannot carry usable authority or extractor pins"
                )
            continue
        if surface_authority is None:
            raise VendorConfigPublicationError(
                f"{item.disposition.value.lower()} surface {identity!r} lacks authority"
            )
        if (
            surface_authority.representation is not item.representation
            or surface_authority.evidence_role is not descriptor.evidence_role
        ):
            raise VendorConfigPublicationError(
                "surface authority conflicts with its ledger or role"
            )
        if item.disposition is SurfaceDisposition.INCLUDED and identity not in bundles:
            raise VendorConfigPublicationError("an included surface lacks an extractor content pin")
    for identity in authorities:
        if identity not in ledger or ledger[identity].disposition is SurfaceDisposition.EXCLUDED:
            raise VendorConfigPublicationError(
                "surface authority is omitted or excluded by the ledger"
            )
    for identity in bundles:
        if identity not in ledger or ledger[identity].disposition is SurfaceDisposition.EXCLUDED:
            raise VendorConfigPublicationError(
                "extractor bundle is omitted or excluded by the ledger"
            )


def _validate_mapping_surfaces(
    mapping_set: MappingSet,
    document: _PublicationFile,
    catalog: SourceCatalog,
) -> None:
    ledger = {(item.source_id, item.surface): item for item in document.surface_ledger}
    bundles = {(item.source_id, item.surface): item for item in document.extractor_bundles}
    for entry in mapping_set.entries:
        _validate_mapping_surface(entry, ledger, bundles, catalog, state=document.state)
    for construction in mapping_set.constructions:
        _validate_mapping_surface(construction, ledger, bundles, catalog, state=document.state)


def _validate_mapping_surface(
    item: MappingEntry | ConstructionRule,
    ledger: dict[tuple[str, str], SurfaceLedgerEntry],
    bundles: dict[tuple[str, str], ExtractorBundle],
    catalog: SourceCatalog,
    *,
    state: PublicationState,
) -> None:
    if _legacy_first_party_mapping(item):
        return
    if item.source is None:
        raise VendorConfigPublicationError("vendor mappings require an explicit source identity")
    try:
        descriptor = catalog.describe(item.source)
    except UnknownSourceError as error:
        raise VendorConfigPublicationError(
            f"vendor mapping names unknown source {item.source!r}"
        ) from error
    declaration = ledger.get((item.source, item.surface))
    if (
        descriptor.source_class is not SourceClass.DERIVED
        or declaration is None
        or declaration.disposition is not SurfaceDisposition.INCLUDED
    ):
        raise VendorConfigPublicationError(
            f"vendor mapping surface {(item.source, item.surface)!r} is not included"
        )
    bundle = bundles.get((item.source, item.surface))
    if bundle is None:
        raise VendorConfigPublicationError(
            f"vendor mapping surface {(item.source, item.surface)!r} lacks an extractor bundle"
        )
    supported = _supported_schemas(bundle, state=state)
    if item.schema_identity not in supported:
        raise VendorConfigPublicationError(
            f"mapping schema {item.schema_identity!r} is unsupported by extractor bundle "
            f"{(item.source, item.surface)!r}"
        )


def _validate_bundle(bundle: ExtractorBundle, *, state: PublicationState) -> None:
    paths = tuple(member.path for member in bundle.members)
    if bundle.source_id == SCREENER_SOURCE and bundle.surface in SCREENER_SURFACES:
        if bundle.version != SCREENER_EXTRACTOR_VERSION or paths != SCREENER_EXTRACTOR_SOURCES:
            raise VendorConfigPublicationError(
                "Screener extractor bundle omits or reorders semantic parser sources"
            )
    _supported_schemas(bundle, state=state)
    for member in bundle.members:
        _require_content(_SOURCE_ROOT, member, artifact="extractor member", read_bytes=None)
    actual = vendor_extractor_pin(bundle.source_id, bundle.surface, bundle.version, paths)
    if actual.content_sha256 != bundle.content_sha256:
        raise VendorConfigPublicationError(
            f"extractor content drift for {(bundle.source_id, bundle.surface)!r}"
        )


def _supported_schemas(bundle: ExtractorBundle, *, state: PublicationState) -> frozenset[str]:
    """Return the closed schemas emitted by one pinned extractor bundle."""
    declared = frozenset(bundle.supported_schema_identities)
    expected = SCREENER_SCHEMA_IDENTITIES.get(bundle.surface)
    if bundle.source_id == SCREENER_SOURCE and expected is not None:
        if state is PublicationState.RELEASED and not declared:
            raise VendorConfigPublicationError(
                "released Screener extractor bundles require explicit supported schemas"
            )
        if declared and declared != expected:
            raise VendorConfigPublicationError(
                "Screener extractor schema declaration differs from its sealed implementation"
            )
        return expected
    if not declared or any(not value.strip() for value in declared):
        raise VendorConfigPublicationError(
            f"extractor bundle {(bundle.source_id, bundle.surface)!r} has no supported schemas"
        )
    return declared


def _validate_authority_evidence(
    authority: SourceAuthorityArtifact, *, state: PublicationState
) -> tuple[str, ...]:
    """Resolve the two approved decision projections; unknown grants fail closed."""
    try:
        return validate_authority_evidence(
            authority,
            released=state is PublicationState.RELEASED,
            repository_root=_REPOSITORY_ROOT,
            private_boundary=PRIVATE_SUBSCRIBER_BOUNDARY,
            upstox_decision=UPSTOX_ROLE_DECISION,
            subscriber_decision=A05_SUBSCRIBER_DECISION,
            screener_source=SCREENER_SOURCE,
        )
    except (UnsafeVendorConfigPathError, VendorAuthorityEvidenceError) as error:
        raise VendorConfigPublicationError(str(error)) from error


def _selected_release_members(
    document: _PublicationFile,
    *,
    publication_relative: str,
    authority_evidence: Sequence[str],
) -> tuple[str, ...]:
    """All repository paths whose exact bytes make up candidate release A."""
    try:
        return selected_release_members(
            repository_root=_REPOSITORY_ROOT,
            publication_relative=publication_relative,
            authority_path=document.source_authority.path,
            normalisation_version=document.normalisation_policy.version,
            mapping_member_paths=tuple(member.path for member in document.mapping_members),
            dictionary_version=document.dictionary.version,
            dictionary_files=tuple(sorted(KNOWN_FILES)),
            authority_evidence=tuple(authority_evidence),
            extractor_member_paths=tuple(
                member.path for bundle in document.extractor_bundles for member in bundle.members
            ),
        )
    except (UnsafeVendorConfigPathError, ValueError) as error:
        raise VendorConfigPublicationError(str(error)) from error


def _verify_release_receipt(
    receipt: _ReleaseReviewReceipt,
    *,
    version: str,
    selected_paths: Sequence[str],
    receipt_relative: str,
) -> None:
    """Verify immutable candidate A, introduction C, and current first-parent HEAD H."""
    try:
        verify_release_receipt(
            receipt,
            repository_root=_REPOSITORY_ROOT,
            version=version,
            selected_paths=selected_paths,
            receipt_relative=receipt_relative,
        )
    except VendorPublicationReceiptError as error:
        raise VendorConfigPublicationError(str(error)) from error


def _require_content(
    root: Path,
    member: ContentMember,
    *,
    artifact: str,
    read_bytes: Callable[[Path], bytes] | None,
) -> None:
    try:
        body = _read_member(root, member.path, read_bytes)
    except VendorConfigPublicationError as error:
        raise VendorConfigPublicationError(
            f"{artifact} content drift or unsafe path: {member.path!r}"
        ) from error
    actual = hashlib.sha256(body).hexdigest()
    if actual != member.content_sha256:
        raise VendorConfigPublicationError(
            f"{artifact} content drift: {member.path!r} differs from pinned content "
            f"{member.content_sha256}"
        )


def _require_pin(artifact: str, expected: VersionPin, actual: VersionPin) -> None:
    if (expected.version, expected.content_sha256) != (actual.version, actual.content_sha256):
        raise VersionContentDriftError(
            artifact=artifact,
            version=expected.version,
            pinned_sha256=expected.content_sha256,
            actual_sha256=actual.content_sha256,
        )


def _read_safe(root: Path, relative: str) -> bytes:
    """Translate internal descriptor-safe path failures to the stable public error."""
    try:
        return read_safe(root, relative)
    except (UnsafeVendorConfigPathError, ValueError) as error:
        raise VendorConfigPublicationError(str(error)) from error


def _read_member(
    root: Path,
    relative: str,
    read_bytes: Callable[[Path], bytes] | None,
) -> bytes:
    """Read one member through the supplied immutable snapshot cache or safe descriptors."""
    return _read_safe(root, relative) if read_bytes is None else read_bytes(root / relative)
