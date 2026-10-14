"""Resolve and hash-verify the retained Apar originals (D1a design decision 4).

The originals live in gitignored ``data/raw/watchlist/aparinds/``, pinned by
SHA-256 in its ``retrieval-manifest.json``. A missing original or a hash mismatch
**fails** the test with a clear message and never skips it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pymupdf
import pytest
from pg_support import PgTestDatabase
from pydantic import BaseModel, ConfigDict, Field

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SourceDescriptor,
)
from fundamentals.evidence.capture_intake import (
    MARKED_SOURCE_PREFIX,
    RetainedIntake,
    retained_intake_from_manifest,
)
from fundamentals.ingest.pdf_source import compute_file_sha256
from fundamentals.pg.identity_seed import load_issuer_identity, seed_issuer_identity
from fundamentals.store.snapshot_store import SnapshotStore

REPO_ROOT = Path(__file__).resolve().parents[2]
APAR_RAW_ROOT = REPO_ROOT / "data" / "raw" / "watchlist" / "aparinds"
# v2 corrects four comparator filed_at_nse values (IST mislabelled UTC); see its "correction".
APAR_MANIFEST = APAR_RAW_ROOT / "retrieval-manifest-v2.json"
APAR_IDENTITY = REPO_ROOT / "config" / "identity" / "aparinds.yaml"
APAR_ISSUER_CONFIG = REPO_ROOT / "config" / "aparinds-fy26-q2.yaml"
XBRL_DIR = "nse"
PDF_DIR = "nse_pdf"
XBRL_KIND_PREFIX = "xbrl-"
STORE_DIR = "store"
INPUTS_DIR = "inputs"
PRIVATE_MODE = 0o700
APAR_RESULTS_PDF_SOURCE_ID = "aparinds-fy26-q2-results-pdf"
MARKED_PDF_QUARTER = "FY26_Q2"
MARKED_PDF_KIND = "results"
ROW_BAND_PT = 3.0
# Word boxes overlap the lines above and below; an inset keeps their glyphs.
REDACT_INSET_PT = 0.5
# Page 3 of the retained Q2 FY26 results PDF prints the consolidated columns left of the
# label column (labels start at x = 367 pt) and the standalone columns right of it.
CONSOLIDATED_X_MAX = 360.0


def manifest_entry(quarter: str, kind: str) -> dict[str, str]:
    """The single retrieval-manifest entry for one quarter and kind, or fail."""
    if not APAR_MANIFEST.is_file():
        pytest.fail(f"retained Apar retrieval manifest missing: {APAR_MANIFEST}")
    entries = json.loads(APAR_MANIFEST.read_text(encoding="utf-8"))["entries"]
    matches = [e for e in entries if e["quarter"] == quarter and e["kind"] == kind]
    if len(matches) != 1:
        pytest.fail(f"retrieval manifest has {len(matches)} entries for {quarter} {kind}")
    return {key: str(value) for key, value in matches[0].items()}


def relative_original_path(entry: dict[str, str]) -> Path:
    """Where a manifest entry's file lives under the raw root."""
    folder = XBRL_DIR if entry["kind"].startswith(XBRL_KIND_PREFIX) else PDF_DIR
    return Path(folder) / entry["filename"]


def apar_original(quarter: str, kind: str) -> Path:
    """Path of a retained Apar original after verifying its pinned SHA-256."""
    entry = manifest_entry(quarter, kind)
    path = APAR_RAW_ROOT / relative_original_path(entry)
    if not path.is_file():
        pytest.fail(f"retained Apar original missing: {path}")
    actual = compute_file_sha256(path)
    if actual != entry["sha256"]:
        pytest.fail(f"retained Apar original {path} hash {actual} != pinned {entry['sha256']}")
    return path


class MarkedEdit(BaseModel):
    """One test-only edit of a retained original: exact bytes to find and their replacement.

    ``find`` names the element, context or line being changed; ``count`` is how many
    times it must occur, so a stale edit fails instead of silently doing nothing. An
    empty ``find`` appends ``replace`` to the end of the file.
    """

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1)
    find: bytes
    replace: bytes
    count: int = 1


def marked_copy(source: Path, *, edit: MarkedEdit, tmp_path: Path) -> Path:
    """Write an edited copy of a retained original under ``tmp_path``; the original is untouched."""
    body = source.read_bytes()
    if edit.find:
        found = body.count(edit.find)
        if found != edit.count:
            pytest.fail(
                f"marked edit {edit.label}: {found} matches in {source.name}, want {edit.count}"
            )
        body = body.replace(edit.find, edit.replace)
    else:
        body += edit.replace
    target = tmp_path / f"{edit.label}-{source.name}"
    target.write_bytes(body)
    return target


class PdfRedaction(BaseModel):
    """One text-layer edit of a retained PDF page: words of one row removed or replaced.

    Only words lying between ``x_min`` and ``x_max`` are considered. ``row_of`` names a
    word occurring exactly once there and fixes the row band; ``words`` are the exact
    word texts to edit in that row (``None``: every word of the row). ``replace`` is
    printed in each edited word's box (``None`` removes the text).
    """

    model_config = ConfigDict(frozen=True)

    page: int = Field(ge=1)
    row_of: str
    words: tuple[str, ...] | None = None
    x_min: float = 0.0
    x_max: float = float("inf")
    replace: str | None = None
    fontsize: float = 8.0


def marked_pdf(
    tmp_path: Path, label: str, *redactions: PdfRedaction, quarter: str = MARKED_PDF_QUARTER
) -> Path:
    """A redacted copy of one quarter's retained results PDF (Q2 FY26 unless named); the
    original is untouched."""
    document = pymupdf.open(apar_original(quarter, MARKED_PDF_KIND))  # type: ignore[no-untyped-call]
    try:
        for redaction in redactions:
            page = document[redaction.page - 1]
            words = [
                word
                for word in page.get_text("words")
                if redaction.x_min <= word[0] and word[2] <= redaction.x_max
            ]
            anchors = [word for word in words if word[4] == redaction.row_of]
            if len(anchors) != 1:
                pytest.fail(f"{label}: {len(anchors)} '{redaction.row_of}' words in range")
            centre = (anchors[0][1] + anchors[0][3]) / 2
            band = [
                word
                for word in words
                if abs((word[1] + word[3]) / 2 - centre) <= ROW_BAND_PT
                and (redaction.words is None or word[4] in redaction.words)
            ]
            if redaction.words is not None and len(band) != len(redaction.words):
                pytest.fail(f"{label}: found {[word[4] for word in band]}")
            for word in band:
                x0, y0, x1, y1 = word[:4]
                box = pymupdf.Rect(x0, y0 + REDACT_INSET_PT, x1, y1 - REDACT_INSET_PT)
                page.add_redact_annot(box, text=redaction.replace, fontsize=redaction.fontsize)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE
            )
        target = tmp_path / f"{label}-results.pdf"
        document.save(target)
    finally:
        document.close()
    return target


def apar_catalog() -> SourceCatalog:
    """Builtin sources, the Q2 FY26 results PDF, and the test-only ``marked-`` namespace."""
    return BUILTIN_SOURCES.extend(
        SourceDescriptor(
            source_id=APAR_RESULTS_PDF_SOURCE_ID,
            source_class=SourceClass.FIRST_PARTY,
            evidence_role=EvidenceRole.RECONCILABLE,
        ),
        SourceDescriptor(
            source_id=MARKED_SOURCE_PREFIX,
            source_class=SourceClass.FIRST_PARTY,
            evidence_role=EvidenceRole.RECONCILABLE,
            is_namespace=True,
        ),
    )


def apar_store(tmp_path: Path) -> SnapshotStore:
    """The private snapshot store under ``tmp_path`` (created once)."""
    root = tmp_path / STORE_DIR
    if not root.exists():
        root.mkdir(mode=PRIVATE_MODE)
    return SnapshotStore(root)


def apar_intake(
    tmp_path: Path,
    quarter: str,
    members: Mapping[Representation, str],
    *,
    marked: Mapping[Representation, Path] | None = None,
    issuer_config: Path = APAR_ISSUER_CONFIG,
) -> RetainedIntake:
    """A retained intake over private copies of the originals (and any marked copies).

    A marked member keeps its manifest filed-at time but is bound to the marked bytes
    under a ``marked-`` source id, so it is never mistaken for the original.
    """
    inputs = tmp_path / INPUTS_DIR
    for folder in (inputs, inputs / XBRL_DIR, inputs / PDF_DIR):
        if not folder.exists():
            folder.mkdir(mode=PRIVATE_MODE)
    for kind in members.values():
        original = apar_original(quarter, kind)
        target = inputs / relative_original_path(manifest_entry(quarter, kind))
        if not target.exists():
            shutil.copyfile(original, target)
    apar_store(tmp_path)
    intake = retained_intake_from_manifest(
        APAR_MANIFEST,
        issuer="APARINDS",
        quarter=quarter,
        kinds=members,
        store_root=(tmp_path / STORE_DIR).absolute(),
        input_root=inputs.absolute(),
        issuer_config=issuer_config if Representation.PDF in members else None,
    )
    if not marked:
        return intake
    bindings = []
    for binding in intake.bindings:
        path = marked.get(binding.representation)
        if path is None:
            bindings.append(binding)
            continue
        folder = XBRL_DIR if binding.representation is Representation.XBRL else PDF_DIR
        target = inputs / folder / path.name
        shutil.copyfile(path, target)
        sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        bindings.append(
            binding.model_copy(
                update={
                    "source_id": f"{MARKED_SOURCE_PREFIX}{binding.representation.value.lower()}",
                    "relative_path": Path(folder) / path.name,
                    "expected_sha256": sha256,
                }
            )
        )
    return intake.model_copy(update={"bindings": tuple(bindings)})


def seed_apar(pg_db: PgTestDatabase) -> int:
    """Seed the evidenced APARINDS identity and return its entity id."""
    identity = load_issuer_identity(APAR_IDENTITY)
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        report = seed_issuer_identity(conn, identity)
    return report.entity_ids[identity.entity_key]
