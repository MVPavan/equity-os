"""Descriptor-safe preparation and pure rederivation of original intake material."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from fundamentals.api.config import FundamentalsConfig
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import FilingFamily, VersionPin
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    EvidenceRole,
    SourceClass,
    SourceDescriptor,
    UnknownSourceError,
)
from fundamentals.evidence.capture_intake import (
    NSE_XBRL_SOURCE_ID,
    PDF_INPUT_DIR,
    SURFACE_OF,
    XBRL_INPUT_DIR,
    RetainedCaptureBinding,
    RetainedIntake,
    authorise,
    parse_filed_at,
    request_key_for,
)
from fundamentals.evidence.first_party_extract import (
    pdf_statement_specs_sha256,
    unsupported_schema_context,
)
from fundamentals.evidence.retained_intake_models import (
    MAX_METADATA_BYTES,
    PreparedRetainedIntakeWitness,
    RetainedIntakeMaterial,
    RetainedIntakeRequest,
    RetainedIntakeSelection,
    RetainedIntakeWitnessError,
    safe_relative_label,
)
from fundamentals.extract.pdf_statement_pages import StatementPageSpec, specs_from_config
from fundamentals.store.snapshot_store import DescriptorTree, DirectoryAnchor

if TYPE_CHECKING:
    from fundamentals.compare.run_config import LoadedConfig
    from fundamentals.evidence.repository import EvidenceRepository


def canonical_document(document: object) -> str:
    """Deterministic JSON for immutable context and full-generation projections."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def derive_retained_intake_material(
    *,
    manifest: RetainedIntakeMaterial,
    issuer_config: RetainedIntakeMaterial,
    issuer: str,
    quarter: str,
    selection: tuple[RetainedIntakeSelection, ...],
    entity_id: int,
    family: FilingFamily,
    reporting_period_end: date,
    basis: Basis,
    framework: AccountingFramework,
    extractor_pins: Mapping[Representation, VersionPin],
    mapping_set_version: str,
) -> PreparedRetainedIntakeWitness:
    """Derive only from bounded durable bytes and typed scope; this function does no I/O."""
    try:
        # Revalidate copies too: model_copy is not a validation/authority boundary.
        manifest = RetainedIntakeMaterial.model_validate(manifest.model_dump())
        issuer_config = RetainedIntakeMaterial.model_validate(issuer_config.model_dump())
        document = json.loads(manifest.body)
        held = FundamentalsConfig.model_validate(yaml.safe_load(issuer_config.body))
        if document["issuer"] != issuer or held.issuer.nse_symbol != issuer:
            raise ValueError("retained manifest/config issuer differs from selection")
        if (
            held.quarter.issuer_quarter != quarter
            or held.quarter.period_end != reporting_period_end
        ):
            raise ValueError("retained issuer config quarter/period differs from requested scope")
        authority = document["authorization"]
        if not isinstance(authority, str) or not authority.strip():
            raise ValueError("retained manifest authorization must be recorded nonempty metadata")
        if held.results_pdf.source_class is not SourceClass.FIRST_PARTY:
            raise ValueError("retained issuer config PDF is not declared first-party")
        if held.xbrl.symbol != issuer or held.xbrl.source_id != NSE_XBRL_SOURCE_ID:
            raise ValueError("retained config XBRL source/issuer differs from original source")
        entries = document["entries"]
        if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise ValueError("retained manifest entries must be objects")
        requests: list[RetainedIntakeRequest] = []
        for selected in selection:
            representation = selected.representation
            if selected.kind.startswith("xbrl-") != (representation is Representation.XBRL):
                raise ValueError("retained selection kind and representation disagree")
            matches = [
                entry
                for entry in entries
                if entry.get("quarter") == quarter and entry.get("kind") == selected.kind
            ]
            if len(matches) != 1:
                raise ValueError("retained selection must identify one original manifest entry")
            entry = matches[0]
            filename = entry["filename"]
            if not isinstance(filename, str) or "/" in safe_relative_label(filename):
                raise ValueError("retained manifest filename must remain in its input folder")
            folder = XBRL_INPUT_DIR if representation is Representation.XBRL else PDF_INPUT_DIR
            relative = f"{folder}/{filename}"
            source = NSE_XBRL_SOURCE_ID
            specs = specs_from_config(held.pdf_parse)
            if representation is Representation.PDF:
                if (held.results_pdf.sha256, held.results_pdf.filename) != (
                    entry["sha256"],
                    relative,
                ):
                    raise ValueError("retained config PDF hash/path differs from original manifest")
                source = held.results_pdf.source_id
                material: dict[str, object] = {
                    item.value: spec.model_dump(mode="json") for item, spec in sorted(specs.items())
                }
                context_sha = pdf_statement_specs_sha256(specs)
            else:
                material = {"mapping_set_version": mapping_set_version}
                context_sha = unsupported_schema_context(mapping_set_version)
            binding = RetainedCaptureBinding(
                representation=representation,
                source_id=source,
                relative_path=Path(relative),
                expected_sha256=entry["sha256"],
                filed_at_raw=entry["filed_at_nse"],
            )
            pin = VersionPin.model_validate(extractor_pins[representation].model_dump())
            requests.append(
                RetainedIntakeRequest(
                    representation=representation,
                    source_id=source,
                    surface=SURFACE_OF[representation].value,
                    relative_path=relative,
                    expected_input_sha256=binding.expected_sha256,
                    request_key=request_key_for(binding),
                    filed_at_raw=binding.filed_at_raw,
                    knowledge_time=parse_filed_at(binding.filed_at_raw),
                    extractor_pin=pin,
                    extraction_context_sha256=context_sha,
                    context_material_json=canonical_document(material),
                )
            )
        return PreparedRetainedIntakeWitness(
            issuer=issuer,
            quarter=quarter,
            manifest=manifest,
            issuer_config=issuer_config,
            selection=selection,
            authority_ref=authority,
            results_pdf_source_id=held.results_pdf.source_id,
            entity_id=entity_id,
            family=family,
            reporting_period_end=reporting_period_end,
            basis=basis,
            framework=framework,
            requests=tuple(requests),
        )
    except (ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise RetainedIntakeWitnessError(f"original retained material is invalid: {exc}") from exc


def prepare_retained_intake_witness(
    intake: RetainedIntake,
    *,
    config: LoadedConfig,
    config_root: Path,
    repository: EvidenceRepository,
    entity_id: int,
    family: FilingFamily,
    reporting_period_end: date,
    basis: Basis,
    framework: AccountingFramework,
    pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None,
) -> PreparedRetainedIntakeWitness:
    """Independently rederive original metadata and reject caller-modified intakes before writes."""
    from fundamentals.compare.run_config import require_published_generation

    source = intake.metadata_source
    if (
        source is None
        or source.issuer_config_anchor is None
        or source.issuer_config_relative_path is None
    ):
        raise RetainedIntakeWitnessError(
            "witness requires locally observed original metadata/config"
        )
    publication = require_published_generation(config, config_root=config_root)
    manifest = _read(source.manifest_anchor, source.manifest_relative_path)
    held_config = _read(source.issuer_config_anchor, source.issuer_config_relative_path)
    prepared = derive_retained_intake_material(
        manifest=manifest,
        issuer_config=held_config,
        issuer=source.issuer,
        quarter=source.quarter,
        selection=source.selection,
        entity_id=entity_id,
        family=family,
        reporting_period_end=reporting_period_end,
        basis=basis,
        framework=framework,
        extractor_pins={
            Representation.XBRL: config.pinned.extractor_xbrl,
            Representation.PDF: config.pinned.extractor_pdf,
        },
        mapping_set_version=config.mapping_set.version,
    )
    actual = tuple(sorted(intake.bindings, key=lambda item: item.representation.value))
    expected = tuple(
        RetainedCaptureBinding(
            representation=request.representation,
            source_id=request.source_id,
            relative_path=Path(request.relative_path),
            expected_sha256=request.expected_input_sha256,
            filed_at_raw=request.filed_at_raw,
        )
        for request in prepared.requests
    )
    if (
        actual != expected
        or intake.retrieval_manifest_sha256 != manifest.sha256
        or intake.issuer_config_sha256 != held_config.sha256
        or intake.authority_ref != prepared.authority_ref
        or intake.results_pdf_source_id != prepared.results_pdf_source_id
    ):
        raise RetainedIntakeWitnessError(
            "intake differs from independently derived original metadata"
        )
    identifiers = repository.issuer_identifiers(entity_id)
    if identifiers.nse_symbol != prepared.issuer:
        raise RetainedIntakeWitnessError(
            "retained metadata issuer differs from verified database identity"
        )
    held = FundamentalsConfig.model_validate(yaml.safe_load(held_config.body))
    if Representation.PDF in {request.representation for request in prepared.requests} and (
        pdf_specs is None or dict(pdf_specs) != dict(specs_from_config(held.pdf_parse))
    ):
        raise RetainedIntakeWitnessError("actual PDF specs differ from original retained config")
    catalog = publication.catalog
    try:
        catalog.describe(prepared.results_pdf_source_id)
    except UnknownSourceError:
        catalog = catalog.extend(
            SourceDescriptor(
                source_id=prepared.results_pdf_source_id,
                source_class=SourceClass.FIRST_PARTY,
                evidence_role=EvidenceRole.RECONCILABLE,
            )
        )
    if any(
        authorise(binding, catalog=catalog, results_pdf_source_id=prepared.results_pdf_source_id)
        is None
        for binding in expected
    ):
        raise RetainedIntakeWitnessError(
            "original retained request is not source-catalog authorized"
        )
    return prepared


def _read(anchor: DirectoryAnchor, path: Path) -> RetainedIntakeMaterial:
    safe_relative_label(path.as_posix())
    try:
        with DescriptorTree(anchor) as tree:
            parent = tree.descend(path.parts[:-1])
            body = tree.read(parent, path.name, MAX_METADATA_BYTES)
            tree.verify()
        return RetainedIntakeMaterial.of(path.as_posix(), body)
    except (OSError, ValueError, RuntimeError, SnapshotError) as exc:
        raise RetainedIntakeWitnessError(f"original retained metadata read refused: {exc}") from exc
