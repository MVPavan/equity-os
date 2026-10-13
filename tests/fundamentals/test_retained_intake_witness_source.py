"""Source and opt-in producer characterization, separate from the frozen behavioral RED."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from evidence_support import (
    Q2_END,
    Ingest,
    apar_pdf_specs,
    dictionary,
    ingest,
    mapping_set,
    policy,
)
from retained_intake_witness_support import original_witness_intake
from retained_support import apar_store
from test_compare_vendor_handoffs import _pdf_only_with_failed_xbrl

from fundamentals.compare.run_config import LoadedConfig
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import FilingFamily, VersionPin
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_intake import retained_intake_from_manifest
from fundamentals.evidence.first_party_generation import (
    FirstPartyGenerationHandoff,
    append_first_party_generation,
)
from fundamentals.evidence.retained_intake_models import (
    MAX_METADATA_BYTES,
    RetainedIntakeMaterial,
    RetainedIntakeMetadataSource,
    RetainedIntakeSelection,
    RetainedIntakeWitnessError,
)
from fundamentals.evidence.retained_intake_proof import require_prepared_material
from fundamentals.evidence.retained_intake_source import (
    derive_retained_intake_material,
    prepare_retained_intake_witness,
)
from fundamentals.evidence.retained_intake_store import RetainedIntakeWitnessStore
from fundamentals.pg.identity_seed import EvidenceInputKind
from fundamentals.store.snapshot_store import DirectoryAnchor

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]
CONFIG = Path(__file__).resolve().parents[2] / "config"


def _materials(*, filename: str = "private-result.pdf", filed_at: str = "29-Oct-2025 09:00:00"):
    """Explicitly synthetic metadata mechanics, with no claimed physical body observation."""
    config = yaml.safe_load((CONFIG / "aparinds-fy26-q2.yaml").read_bytes())
    config["results_pdf"]["sha256"] = "1" * 64
    config["results_pdf"]["filename"] = f"nse_pdf/{filename}"
    config["results_pdf"]["source_id"] = "private-original-pdf"
    manifest = {
        "issuer": "APARINDS",
        "authorization": "private synthetic metadata; no source authority grant",
        "entries": [
            {
                "quarter": "FY26_Q2",
                "kind": "results",
                "filename": filename,
                "sha256": "1" * 64,
                "filed_at_nse": filed_at,
            },
            {
                "quarter": "FY26_Q2",
                "kind": "xbrl-consolidated",
                "filename": "private-instance.xml",
                "sha256": "2" * 64,
                "filed_at_nse": filed_at,
            },
        ],
    }
    return manifest, config


def _derive(manifest=None, config=None):
    if manifest is None or config is None:
        manifest, config = _materials()
    return derive_retained_intake_material(
        manifest=RetainedIntakeMaterial.of(
            "retrieval-manifest.json", json.dumps(manifest).encode()
        ),
        issuer_config=RetainedIntakeMaterial.of("apar.yaml", yaml.safe_dump(config).encode()),
        issuer="APARINDS",
        quarter="FY26_Q2",
        selection=(
            RetainedIntakeSelection(representation=Representation.PDF, kind="results"),
            RetainedIntakeSelection(representation=Representation.XBRL, kind="xbrl-consolidated"),
        ),
        entity_id=1,
        family=FilingFamily.FINANCIAL_RESULTS,
        reporting_period_end=date(2025, 9, 30),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        extractor_pins={
            Representation.PDF: VersionPin(version="private-pdf", content_sha256="3" * 64),
            Representation.XBRL: VersionPin(version="private-xbrl", content_sha256="4" * 64),
        },
        mapping_set_version="private-mapping",
    )


def test_durable_original_material_rederives_both_requests_without_body_observation() -> None:
    prepared = _derive()
    assert tuple(request.representation for request in prepared.requests) == (
        Representation.PDF,
        Representation.XBRL,
    )
    pdf, xbrl = prepared.requests
    assert (pdf.source_id, pdf.relative_path, pdf.expected_input_sha256) == (
        "private-original-pdf",
        "nse_pdf/private-result.pdf",
        "1" * 64,
    )
    assert (xbrl.source_id, xbrl.relative_path, xbrl.expected_input_sha256) == (
        "nse-indas-xbrl-consolidated",
        "nse/private-instance.xml",
        "2" * 64,
    )
    assert pdf.knowledge_time == datetime(2025, 10, 29, 3, 30, tzinfo=UTC)
    assert prepared.manifest.sha256 == hashlib.sha256(prepared.manifest.body).hexdigest()
    assert prepared.manifest.size == len(prepared.manifest.body)
    require_prepared_material(prepared)


@pytest.mark.parametrize(
    "path", ["../private.pdf", "/private.pdf", "nested/private.pdf", "private\\bad.pdf"]
)
def test_material_refuses_manifest_filename_escape(path: str) -> None:
    manifest, config = _materials(filename=path)
    with pytest.raises(RetainedIntakeWitnessError, match="filename|unsafe"):
        _derive(manifest, config)


def test_original_metadata_refuses_duplicate_selection() -> None:
    manifest, config = _materials()
    manifest["entries"].append(dict(manifest["entries"][0]))
    with pytest.raises(RetainedIntakeWitnessError, match="one original"):
        _derive(manifest, config)


def test_original_config_refuses_pdf_hash_conflict() -> None:
    manifest, config = _materials()
    config["results_pdf"]["sha256"] = "9" * 64
    with pytest.raises(RetainedIntakeWitnessError, match="hash/path"):
        _derive(manifest, config)


def test_original_metadata_refuses_unknown_filed_time() -> None:
    manifest, config = _materials(filed_at="2025-10-29")
    with pytest.raises(RetainedIntakeWitnessError, match="filed-at"):
        _derive(manifest, config)


def test_prepared_model_copy_cannot_replace_original_binding_with_its_own_hash() -> None:
    prepared = _derive()
    altered = prepared.model_copy(
        update={
            "requests": (
                prepared.requests[0].model_copy(update={"expected_input_sha256": "9" * 64}),
                prepared.requests[1],
            )
        }
    )
    with pytest.raises(RetainedIntakeWitnessError, match="original metadata"):
        require_prepared_material(altered)


@pytest.mark.parametrize("unsafe_metadata", ["manifest", "issuer_config"])
def test_legacy_intake_preserves_binding_when_metadata_parent_cannot_be_anchored(
    tmp_path: Path, unsafe_metadata: str
) -> None:
    """Optional witness observation must not narrow the legacy factory's accepted inputs."""
    roots = {name: tmp_path / name for name in ("manifest", "issuer_config", "store", "input")}
    for root in roots.values():
        root.mkdir(mode=0o700)
    manifest, config = _materials()
    manifest_path = roots["manifest"] / "retrieval-manifest.json"
    config_path = roots["issuer_config"] / "issuer.yaml"
    manifest_path.write_text(json.dumps(manifest))
    config_path.write_text(yaml.safe_dump(config))

    def legacy_intake():
        return retained_intake_from_manifest(
            manifest_path,
            issuer="APARINDS",
            quarter="FY26_Q2",
            kinds={Representation.PDF: "results", Representation.XBRL: "xbrl-consolidated"},
            store_root=roots["store"],
            input_root=roots["input"],
            issuer_config=config_path,
        )

    original = legacy_intake()
    assert original.metadata_source is not None
    roots[unsafe_metadata].chmod(0o770)
    legacy = legacy_intake()
    assert legacy.bindings == original.bindings
    assert legacy.authority_ref == original.authority_ref
    assert legacy.retrieval_manifest_sha256 == original.retrieval_manifest_sha256
    assert legacy.issuer_config_sha256 == original.issuer_config_sha256
    assert legacy.metadata_source is None
    repository = Mock()
    with pytest.raises(RetainedIntakeWitnessError, match="locally observed original metadata"):
        prepare_retained_intake_witness(
            legacy,
            config=Mock(spec=LoadedConfig),
            config_root=tmp_path,
            repository=repository,
            entity_id=1,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=Q2_END,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            pdf_specs=None,
        )
    assert repository.mock_calls == []


def _append_witness(
    ingest: Ingest, root: Path, config: LoadedConfig, *, intake=None
) -> FirstPartyGenerationHandoff:
    """Opt in through the approved real producer, retaining actual original metadata."""
    with ingest.pg_db.runtime_pool() as pool:
        return append_first_party_generation(
            intake=intake or original_witness_intake(ingest),
            snapshot_store=apar_store(ingest.tmp_path),
            pool=pool,
            config=config,
            config_root=root,
            entity_id=ingest.entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=Q2_END,
            pdf_specs=apar_pdf_specs(),
            retain_intake_witness=True,
        )


@pytest.mark.pg
@pytest.mark.retained
def test_opt_in_producer_seals_original_reverse_xbrl_and_reuses_exact_ids(
    ingest: Ingest, tmp_path: Path
) -> None:
    root, config, old = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    assert "retained_intake_witness_id" not in old.model_dump(mode="json")
    handoff = _append_witness(ingest, root, config)
    assert handoff.retained_intake_witness_id is not None
    (record,) = ingest.repository.get_evidence_inputs([handoff.retained_intake_witness_id])
    assert record.kind is EvidenceInputKind.RETAINED_INTAKE
    witness = record.retained_intake_witness
    assert witness is not None
    assert witness.evidence_input_id == handoff.retained_intake_witness_id
    assert witness.payload.package_id == old.package_id == handoff.package_id
    assert witness.payload.prepared.issuer == "APARINDS"
    assert witness.payload.prepared.quarter == "FY26_Q2"
    assert len(witness.payload.prepared.requests) == 2
    assert witness.recorded_at == witness.sealed_at
    before = ingest.table_counts()
    repeat = _append_witness(ingest, root, config)
    assert repeat == handoff
    assert ingest.table_counts() == before
    assert RetainedIntakeWitnessStore(ingest.repository).get_by_evidence_ids(
        [handoff.retained_intake_witness_id]
    ) == (witness,)


@pytest.mark.pg
@pytest.mark.retained
def test_opt_in_producer_refuses_modified_binding_before_any_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    root, config, _ = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    intake = original_witness_intake(ingest)
    altered = intake.model_copy(
        update={
            "bindings": tuple(
                binding.model_copy(update={"expected_sha256": "9" * 64})
                if binding.representation is Representation.XBRL
                else binding
                for binding in intake.bindings
            )
        }
    )
    before = ingest.table_counts()
    with pytest.raises(RetainedIntakeWitnessError, match="independently derived"):
        _append_witness(ingest, root, config, intake=altered)
    assert ingest.table_counts() == before


@pytest.mark.pg
@pytest.mark.retained
def test_opt_in_producer_refuses_missing_original_source_before_any_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    root, config, _ = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    intake = ingest.intake().model_copy(update={"metadata_source": None})
    before = ingest.table_counts()
    with pytest.raises(RetainedIntakeWitnessError, match="locally observed"):
        _append_witness(ingest, root, config, intake=intake)
    assert ingest.table_counts() == before


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("abuse", ["symlink", "directory_replaced", "oversized"])
def test_original_metadata_descriptor_abuse_refuses_before_generation_writes(
    ingest: Ingest, tmp_path: Path, abuse: str
) -> None:
    """Only private metadata copies are perturbed; retained financial originals remain unchanged."""
    root, config, _ = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    intake = original_witness_intake(ingest)
    source = intake.metadata_source
    assert source is not None and source.issuer_config_anchor is not None
    assert source.issuer_config_relative_path is not None
    private = tmp_path / "private-metadata"
    private.mkdir(mode=0o700)
    manifest = private / "retrieval-manifest.json"
    issuer_config = private / "issuer.yaml"
    manifest.write_bytes((source.manifest_anchor.path / source.manifest_relative_path).read_bytes())
    issuer_config.write_bytes(
        (source.issuer_config_anchor.path / source.issuer_config_relative_path).read_bytes()
    )
    anchored = RetainedIntakeMetadataSource(
        manifest_anchor=DirectoryAnchor(private),
        manifest_relative_path=Path(manifest.name),
        issuer_config_anchor=DirectoryAnchor(private),
        issuer_config_relative_path=Path(issuer_config.name),
        issuer=source.issuer,
        quarter=source.quarter,
        selection=source.selection,
    )
    intake = intake.model_copy(update={"metadata_source": anchored})
    if abuse == "symlink":
        other = private / "same-material.json"
        other.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(other)
    elif abuse == "directory_replaced":
        private.rename(tmp_path / "previous-private-metadata")
        private.mkdir(mode=0o700)
        manifest.write_bytes(b"{}")
        issuer_config.write_bytes(b"{}")
    else:
        manifest.write_bytes(b" " * (MAX_METADATA_BYTES + 1))
    before = ingest.table_counts()
    with pytest.raises(RetainedIntakeWitnessError, match="metadata read refused"):
        _append_witness(ingest, root, config, intake=intake)
    assert ingest.table_counts() == before
