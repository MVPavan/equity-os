"""Witnessed reverse-source fixture, added after the original guard RED was recorded."""

import hashlib
from pathlib import Path

import retained_support
from evidence_support import BOTH, Q2_FY26, Ingest
from test_compare_vendor_handoffs import _pdf_only_with_failed_xbrl

from fundamentals.compare.run_config import LoadedConfig
from fundamentals.evidence.capture_intake import RetainedIntake, retained_intake_from_manifest
from fundamentals.evidence.first_party_generation import FirstPartyGenerationHandoff


def original_witness_intake(ingest: Ingest) -> RetainedIntake:
    """Declare safe private copies of exact metadata; financial original handling is unchanged."""
    base = ingest.intake()
    metadata = ingest.tmp_path / "witness-original-metadata"
    metadata.mkdir(mode=0o700, exist_ok=True)
    manifest = metadata / "retrieval-manifest.json"
    issuer = metadata / "issuer.yaml"
    for original, private, expected in (
        (retained_support.APAR_MANIFEST, manifest, base.retrieval_manifest_sha256),
        (retained_support.APAR_ISSUER_CONFIG, issuer, base.issuer_config_sha256),
    ):
        body = original.read_bytes()
        assert hashlib.sha256(body).hexdigest() == expected
        if private.exists():
            assert private.read_bytes() == body
        else:
            private.write_bytes(body)
    intake = retained_intake_from_manifest(
        manifest,
        issuer="APARINDS",
        quarter=Q2_FY26,
        kinds={binding.representation: BOTH[binding.representation] for binding in base.bindings},
        store_root=base.store_anchor.path,
        input_root=base.input_anchor.path,
        issuer_config=issuer,
    )
    assert intake.bindings == base.bindings
    assert intake.retrieval_manifest_sha256 == base.retrieval_manifest_sha256
    assert intake.issuer_config_sha256 == base.issuer_config_sha256
    assert intake.metadata_source is not None
    return intake


def witnessed_reverse_fixture(
    ingest: Ingest, tmp_path: Path
) -> tuple[Path, LoadedConfig, FirstPartyGenerationHandoff]:
    from test_retained_intake_witness_source import _append_witness

    root, config, _ = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    return root, config, _append_witness(ingest, root, config)
