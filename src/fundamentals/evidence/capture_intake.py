"""Package-shaped first-party intake of retained originals (D1a design decision 12).

The operator names files; authority comes only from the injected :class:`SourceCatalog`.
Bindings come only from retrieval-manifest entries matching issuer, quarter and kind, with
paths resolved under the pinned input root and never absolute.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.snapshot import SnapshotError, SnapshotRights, canonical_sha256
from fundamentals.contracts.source_catalog import SourceCatalog, SourceClass, UnknownSourceError
from fundamentals.store.capture_local import capture_local_original
from fundamentals.store.snapshot_store import DescriptorTree, DirectoryAnchor, SnapshotStore

NSE_XBRL_SOURCE_ID = "nse-indas-xbrl-consolidated"
# Test-only first-party namespace for marked copies (plan Constraints). The CLI never
# declares it, so a marked id there is undeclared and refused.
MARKED_SOURCE_PREFIX = "marked-"
XBRL_INPUT_DIR = "nse"
PDF_INPUT_DIR = "nse_pdf"
XBRL_KIND_PREFIX = "xbrl-"
NSE_WALL_ZONE = ZoneInfo("Asia/Kolkata")
NSE_FILED_AT_FORMAT = "%d-%b-%Y %H:%M:%S"
_NSE_FILED_AT_SHAPE = re.compile(r"\d{2}-[A-Z][a-z]{2}-\d{4} \d{2}:\d{2}:\d{2}")
_ISO_WITH_OFFSET_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}")
MEDIA_TYPES: Mapping[Representation, str] = {
    Representation.XBRL: "application/xml",
    Representation.PDF: "application/pdf",
}

_FILED_AT_REFUSED = "filed-at {raw!r} is neither 'DD-Mon-YYYY HH:MM:SS' nor ISO with an offset"
_NO_ENTRY = "retrieval manifest has {count} entries for {issuer} {quarter} {kind}, expected 1"
_WRONG_ISSUER = "retrieval manifest is for {found!r}, not {issuer!r}"
_NO_ISSUER_CONFIG = "a PDF member needs the issuer config's results_pdf declaration"
_PDF_PIN_CONFLICT = "issuer config pins the results PDF to {config}, the manifest to {manifest}"
_STORE_MISMATCH = "snapshot store differs from the intake's pinned store anchor"
_NOT_A_BINDING = "intake has no {representation} binding"


class FiledAtFormatError(ValueError):
    """A filed-at string has neither of the two evidenced shapes (design decision 5)."""


class IntakeError(ValueError):
    """The manifest, issuer config or store cannot form a retained intake."""


class FirstPartySurface(StrEnum):
    """The authorised first-party surfaces of a results package."""

    NSE_XBRL_INSTANCE = "NSE_XBRL_INSTANCE"
    NSE_RESULTS_PDF = "NSE_RESULTS_PDF"


SURFACE_OF: Mapping[Representation, FirstPartySurface] = {
    Representation.XBRL: FirstPartySurface.NSE_XBRL_INSTANCE,
    Representation.PDF: FirstPartySurface.NSE_RESULTS_PDF,
}


class RetainedCaptureBinding(BaseModel):
    """One package member as named by the retrieval manifest."""

    model_config = ConfigDict(frozen=True)

    representation: Representation
    source_id: str = Field(min_length=1)
    relative_path: Path
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    filed_at_raw: str


class RetainedIntake(BaseModel):
    """Every member binding of one package, with the pinned store and input directories.

    ``authority_ref`` is the manifest's recorded retrieval authority; it becomes the
    capture's :class:`SnapshotRights` reference. ``results_pdf_source_id`` is the issuer
    config's declared results-PDF source (decision 12's only permitted PDF source).
    """

    # DirectoryAnchor is the store layer's operator-pinned identity (a dataclass that
    # observes the filesystem); this model is process-local and never serialised.
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    bindings: tuple[RetainedCaptureBinding, ...] = Field(min_length=1)
    retrieval_manifest_sha256: str
    issuer_config_sha256: str | None
    authority_ref: str = Field(min_length=1)
    results_pdf_source_id: str | None = None
    store_anchor: DirectoryAnchor
    input_anchor: DirectoryAnchor

    def binding(self, representation: Representation) -> RetainedCaptureBinding:
        """The binding of one representation."""
        for binding in self.bindings:
            if binding.representation is representation:
                return binding
        raise IntakeError(_NOT_A_BINDING.format(representation=representation))


class _ResultsPdf(BaseModel):
    """The issuer config's ``results_pdf`` block, as far as intake needs it."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    sha256: str


def parse_filed_at(raw: str) -> datetime:
    """A manifest filed-at string as a UTC instant (design decision 5).

    ``DD-Mon-YYYY HH:MM:SS`` is naive NSE wall time in Asia/Kolkata; an ISO string with
    an offset keeps its offset as written. Any other shape raises
    :class:`FiledAtFormatError`.
    """
    if _NSE_FILED_AT_SHAPE.fullmatch(raw):
        wall = datetime.strptime(raw, NSE_FILED_AT_FORMAT)
        return wall.replace(tzinfo=NSE_WALL_ZONE).astimezone(UTC)
    if _ISO_WITH_OFFSET_SHAPE.fullmatch(raw):
        return datetime.fromisoformat(raw).astimezone(UTC)
    raise FiledAtFormatError(_FILED_AT_REFUSED.format(raw=raw))


def retained_intake_from_manifest(
    manifest_path: Path,
    *,
    issuer: str,
    quarter: str,
    kinds: Mapping[Representation, str],
    store_root: Path,
    input_root: Path,
    issuer_config: Path | None,
) -> RetainedIntake:
    """Bind one package's members from the retrieval manifest; nothing is staged here."""
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("issuer") != issuer:
        raise IntakeError(_WRONG_ISSUER.format(found=manifest.get("issuer"), issuer=issuer))
    results_pdf = _results_pdf(issuer_config) if issuer_config is not None else None
    bindings = []
    for representation, kind in kinds.items():
        entry = _manifest_entry(manifest["entries"], issuer=issuer, quarter=quarter, kind=kind)
        folder = XBRL_INPUT_DIR if kind.startswith(XBRL_KIND_PREFIX) else PDF_INPUT_DIR
        bindings.append(
            RetainedCaptureBinding(
                representation=representation,
                source_id=_source_id(representation, entry["sha256"], results_pdf),
                relative_path=Path(folder) / entry["filename"],
                expected_sha256=entry["sha256"],
                filed_at_raw=entry["filed_at_nse"],
            )
        )
    return RetainedIntake(
        bindings=tuple(bindings),
        retrieval_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        issuer_config_sha256=(
            hashlib.sha256(issuer_config.read_bytes()).hexdigest() if issuer_config else None
        ),
        authority_ref=str(manifest["authorization"]),
        results_pdf_source_id=results_pdf.source_id if results_pdf is not None else None,
        store_anchor=DirectoryAnchor(store_root),
        input_anchor=DirectoryAnchor(input_root),
    )


def authorise(
    binding: RetainedCaptureBinding,
    *,
    catalog: SourceCatalog,
    results_pdf_source_id: str | None = None,
) -> FirstPartySurface | None:
    """The binding's surface when the catalog authorises it, else ``None``.

    Authorised iff the source resolves to a reconcilable first-party declaration and the
    (representation, source) pair is in the decision-12 table: the builtin NSE XBRL source
    for XBRL, the issuer config's declared results PDF (``results_pdf_source_id``) for PDF,
    or a declared marked copy of either. A first-party source of the other surface, or any
    other first-party PDF, is not authorised.
    """
    try:
        descriptor = catalog.describe(binding.source_id)
    except UnknownSourceError:
        return None
    if descriptor.source_class is not SourceClass.FIRST_PARTY or not descriptor.may_reconcile:
        return None
    permitted = (
        NSE_XBRL_SOURCE_ID
        if binding.representation is Representation.XBRL
        else results_pdf_source_id
    )
    if binding.source_id != permitted and not binding.source_id.startswith(MARKED_SOURCE_PREFIX):
        return None
    return SURFACE_OF[binding.representation]


def stage_retained_member(
    store: SnapshotStore, intake: RetainedIntake, representation: Representation
) -> CaptureReference:
    """Stage one authorised member's pinned bytes as a capture (no database write)."""
    _check_store(store, intake.store_anchor)
    binding = intake.binding(representation)
    surface = SURFACE_OF[representation]
    record = capture_local_original(
        store,
        input_anchor=intake.input_anchor,
        source_id=binding.source_id,
        surface=surface.value,
        request_key=request_key_for(binding),
        expected_sha256=binding.expected_sha256,
        media_type=MEDIA_TYPES[representation],
        rights=SnapshotRights(authority_refs=(intake.authority_ref,)),
        path=binding.relative_path,
    )
    return CaptureReference(
        capture_ref_id=None,
        source_id=binding.source_id,
        surface=surface.value,
        request_key=record.request.request_key,
        capture_id=record.capture_id,
        blob_sha256=binding.expected_sha256,
        record_sha256=record.record_sha256,
        registered_at=record.retrieved_at,
        first_seen_at=record.retrieved_at,
    )


def request_key_for(binding: RetainedCaptureBinding) -> str:
    """The stable request key of one member: its representation and pinned content."""
    return canonical_sha256(
        {"representation": binding.representation.value, "sha256": binding.expected_sha256}
    )


def _check_store(store: SnapshotStore, anchor: DirectoryAnchor) -> None:
    """Refuse a store other than the pinned one, as ``ApprovedIntakeContext`` does."""
    if store._root.absolute() != anchor.path:
        raise IntakeError(_STORE_MISMATCH)
    if store._anchor is not None and store._anchor != anchor:
        raise IntakeError(_STORE_MISMATCH)
    try:
        with DescriptorTree(anchor) as tree:
            tree.verify()
    except (SnapshotError, OSError) as error:
        raise IntakeError(f"{_STORE_MISMATCH}: {error}") from error
    store._anchor = anchor


def _manifest_entry(
    entries: list[dict[str, object]], *, issuer: str, quarter: str, kind: str
) -> dict[str, str]:
    """The one manifest entry for a quarter and kind."""
    matches = [entry for entry in entries if entry["quarter"] == quarter and entry["kind"] == kind]
    if len(matches) != 1:
        raise IntakeError(
            _NO_ENTRY.format(count=len(matches), issuer=issuer, quarter=quarter, kind=kind)
        )
    return {key: str(value) for key, value in matches[0].items()}


def _results_pdf(issuer_config: Path) -> _ResultsPdf:
    """The issuer config's results-PDF declaration."""
    raw = yaml.safe_load(issuer_config.read_bytes())
    return _ResultsPdf.model_validate(raw["results_pdf"])


def _source_id(
    representation: Representation, manifest_sha256: str, results_pdf: _ResultsPdf | None
) -> str:
    """The source id a member is registered under."""
    if representation is Representation.XBRL:
        return NSE_XBRL_SOURCE_ID
    if results_pdf is None:
        raise IntakeError(_NO_ISSUER_CONFIG)
    if results_pdf.sha256 != manifest_sha256:
        raise IntakeError(
            _PDF_PIN_CONFLICT.format(config=results_pdf.sha256, manifest=manifest_sha256)
        )
    return results_pdf.source_id
