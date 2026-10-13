"""Published-config first-party generation handoff behavior (D1b Task 11)."""

from __future__ import annotations

from pathlib import Path

import pytest
from evidence_support import (
    Q2_END,
    Ingest,
    apar_pdf_specs,
    dictionary,
    ingest,
    mapping_set,
    policy,
)
from psycopg_pool import ConnectionPool
from retained_support import apar_store
from test_vendor_config_publication import _draft_root, _publish_synthetic

from fundamentals.compare.run_config import (
    ConfigVersions,
    LoadedConfig,
    extractor_pin,
    load_run_config,
)
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import (
    AttemptStage,
    EligibilityBoundary,
    FilingFamily,
    InterpretationStatus,
    InterpretationTriple,
    RunMode,
    VersionPin,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.evidence.first_party_context import (
    QUALIFICATION_CONTEXT_TRACE_KEY,
    FirstPartyGenerationContext,
)
from fundamentals.evidence.first_party_generation import (
    FirstPartyGenerationError,
    FirstPartyGenerationHandoff,
    append_first_party_generation,
)
from fundamentals.evidence.selection import NOT_INTERPRETED_UNDER_PINS, select_key
from fundamentals.evidence.vendor_config import VendorConfigPublicationError
from fundamentals.pg.identity_seed import EvidenceInputKind, SettingKey

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CHANGED_XBRL_EXTRACTOR = "xbrl-publication-reprocess-test-v2"


def _published_config(tmp_path: Path) -> tuple[Path, LoadedConfig]:
    """A loader-validated synthetic publication confined to this test's config root."""
    config_root = _draft_root(tmp_path)
    _publish_synthetic(config_root)
    return config_root, load_run_config(
        config_root,
        ConfigVersions(mapping_set="v2"),
        allow_synthetic_vendor_config=True,
    )


def _append(
    ingest: Ingest,
    config_root: Path,
    config: LoadedConfig,
    pool: ConnectionPool,
    *,
    intake=None,
) -> FirstPartyGenerationHandoff:
    """Append the publication's first-party generation for retained Apar Q2 FY26."""
    return append_first_party_generation(
        intake=intake or ingest.intake(),
        snapshot_store=apar_store(ingest.tmp_path),
        pool=pool,
        config=config,
        config_root=config_root,
        entity_id=ingest.entity_id,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        family=FilingFamily.FINANCIAL_RESULTS,
        reporting_period_end=Q2_END,
        pdf_specs=apar_pdf_specs(),
    )


def test_published_generation_handoff_names_only_exact_stored_rows(
    ingest: Ingest, tmp_path: Path
) -> None:
    """v2 appends interpretations while preserving the v1 package, captures and occurrences."""
    v1_report = ingest.run(ingest.intake())
    v1_ids = tuple(
        interpretation_id
        for member in v1_report.members
        for interpretation_id in member.interpretation_ids
    )
    v1_by_id = ingest.repository.get_interpretations(v1_ids)
    v1_occurrences = {member.representation: member.occurrence_ids for member in v1_report.members}
    config_root, loaded = _published_config(tmp_path)

    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, config_root, loaded, pool)

    publication = loaded.vendor_config
    assert publication is not None
    assert handoff.publication_version == publication.version
    assert handoff.publication_sha256 == publication.published_config_sha256
    assert handoff.package_id == v1_report.package_id
    assert handoff.dictionary_pin == loaded.pinned.dictionary
    assert handoff.formula_set_pin == loaded.pinned.formula_set
    assert handoff.mapping_set_pin == loaded.pinned.mapping_set
    assert handoff.normalisation_policy_pin == loaded.pinned.normalisation_policy
    assert handoff.alignment_rules_pin == loaded.pinned.alignment_rules
    assert ingest.repository.get_interpretations(v1_ids) == v1_by_id
    assert handoff.qualification_context_trace_stored is True
    assert handoff.qualification_context_foreign_key_stored is False
    (setting,) = ingest.repository.get_settings_records([handoff.fiscal_year_end_setting_id])
    assert setting.evidence_input_id == handoff.fiscal_year_end_setting_evidence_input_id
    assert setting.recorded_at == handoff.fiscal_year_end_setting_recorded_at
    assert int(setting.value_text) == handoff.fiscal_year_end_month
    qualification_context = FirstPartyGenerationContext.from_record(setting)
    assert qualification_context.record_sha256 == handoff.qualification_context_sha256

    all_interpretation_ids = {
        interpretation_id
        for member in handoff.members
        for interpretation_id in member.interpretation_ids
    }
    assert all_interpretation_ids
    assert all_interpretation_ids.isdisjoint(v1_ids)
    assert set(handoff.attempt_ids) == {
        attempt_id for member in handoff.members for attempt_id in member.attempt_ids
    }
    assert not handoff.capture_free_attempt_ids

    for member in handoff.members:
        assert member.occurrence_ids == v1_occurrences[member.representation]
        assert member.attempted_at_min is not None
        assert member.attempted_at_max is not None
        assert member.interpretation_recorded_at_min <= member.interpretation_recorded_at_max
        (capture,) = ingest.repository.get_capture_refs([member.capture_ref_id])
        assert capture.source_id == member.source_id
        assert capture.surface == member.surface
        assert capture.blob_sha256 == member.blob_sha256
        assert capture.record_sha256 == member.record_sha256
        assert capture.registered_at == member.capture_registered_at
        assert capture.first_seen_at == member.capture_first_seen_at
        expected_extractor = (
            loaded.pinned.extractor_xbrl
            if member.representation is Representation.XBRL
            else loaded.pinned.extractor_pdf
        )
        assert member.extractor_pin == expected_extractor

        rows = ingest.repository.get_interpretations(member.interpretation_ids)
        assert {row.interpretation_id for row in rows} == set(member.interpretation_ids)
        assert all(row.capture_ref_id == member.capture_ref_id for row in rows)
        assert all(row.dictionary_version == loaded.pinned.dictionary.version for row in rows)
        assert all(row.mapping_set_version == loaded.pinned.mapping_set.version for row in rows)
        assert all(
            row.normalisation_policy_version == loaded.pinned.normalisation_policy.version
            for row in rows
        )
        assert all(row.extractor_version == member.extractor_pin.version for row in rows)
        assert all(
            row.transform_trace[QUALIFICATION_CONTEXT_TRACE_KEY]
            == qualification_context.trace_payload()
            for row in rows
        )
        qualified = {row.interpretation_id for row in rows if row.qualification_ref is not None}
        assert set(member.qualified_interpretation_ids) == qualified
        assert set(member.qualification_evidence_interpretation_ids) <= all_interpretation_ids

    proofs = ingest.repository.get_alignment_proofs(handoff.alignment_proof_ids)
    assert proofs
    assert {proof.proof_id for proof in proofs} == set(handoff.alignment_proof_ids)
    assert all(proof.package_id == handoff.package_id for proof in proofs)
    assert all(proof.rule_set_version == handoff.alignment_rules_pin.version for proof in proofs)
    assert all(
        {interpretation_id for interpretation_id, _ in proof.participants} <= all_interpretation_ids
        for proof in proofs
    )


def test_same_published_generation_returns_same_handoff(ingest: Ingest, tmp_path: Path) -> None:
    """A repeat under identical publication and retained bytes adds no evidence rows."""
    config_root, loaded = _published_config(tmp_path)
    with ingest.pg_db.runtime_pool() as pool:
        first = _append(ingest, config_root, loaded, pool)
        after_first = ingest.table_counts()
        second = _append(ingest, config_root, loaded, pool)

    assert second == first
    assert ingest.table_counts() == after_first


def test_cutoff_and_mode_never_fall_back_from_v2_to_v1(ingest: Ingest, tmp_path: Path) -> None:
    """An old v2 cutoff is unavailable; retrospective sees v2 while v1 remains replayable."""
    v1_report = ingest.run(ingest.intake())
    v1_rows = ingest.repository.get_interpretations(
        tuple(
            interpretation_id
            for member in v1_report.members
            for interpretation_id in member.interpretation_ids
        )
    )
    v1_occurrences = ingest.repository.get_occurrences(
        tuple(
            occurrence_id for member in v1_report.members for occurrence_id in member.occurrence_ids
        )
    )
    config_root, loaded = _published_config(tmp_path)
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, config_root, loaded, pool)
    v2_rows = ingest.repository.get_interpretations(
        tuple(
            interpretation_id
            for member in handoff.members
            for interpretation_id in member.interpretation_ids
        )
    )
    (package,) = ingest.repository.get_packages([handoff.package_id])
    target = next(
        row for row in v2_rows if row.status is InterpretationStatus.MAPPED and row.key is not None
    )
    early = EligibilityBoundary(
        knowledge_cutoff=package.knowledge_time,
        first_seen_cutoff=max(row.recorded_at for row in v1_rows),
    )
    later = early.model_copy(update={"first_seen_cutoff": max(row.recorded_at for row in v2_rows)})
    all_rows = (*v1_rows, *v2_rows)
    occurrences = tuple({row.occurrence_id: row for row in v1_occurrences}.values())

    unavailable = select_key(
        target.key,
        target.representation,
        package=package,
        occurrences=occurrences,
        interpretations=all_rows,
        boundary=early,
        mode=RunMode.AS_KNOWN,
        pinned=loaded.pinned,
    )
    retrospective = select_key(
        target.key,
        target.representation,
        package=package,
        occurrences=occurrences,
        interpretations=all_rows,
        boundary=early,
        mode=RunMode.RETROSPECTIVE,
        pinned=loaded.pinned,
    )
    current = select_key(
        target.key,
        target.representation,
        package=package,
        occurrences=occurrences,
        interpretations=all_rows,
        boundary=later,
        mode=RunMode.AS_KNOWN,
        pinned=loaded.pinned,
    )
    v1_members = {member.representation: member for member in v1_report.members}
    v1_pins = InterpretationTriple(
        mapping_set=ingest.mapping_set.version,
        normalisation_policy=ingest.policy.version,
        extractor_xbrl=v1_members[Representation.XBRL].extractor_version,
        extractor_pdf=v1_members[Representation.PDF].extractor_version,
    )
    historical = select_key(
        target.key,
        target.representation,
        package=package,
        occurrences=occurrences,
        interpretations=all_rows,
        boundary=early,
        mode=RunMode.AS_KNOWN,
        pinned=v1_pins,
    )

    assert unavailable.state is SourceState.UNAVAILABLE
    assert unavailable.reason == NOT_INTERPRETED_UNDER_PINS
    assert unavailable.interpretation is None
    assert retrospective.interpretation is not None
    assert retrospective.interpretation.interpretation_id in {
        row.interpretation_id for row in v2_rows
    }
    assert current.interpretation == retrospective.interpretation
    assert historical.interpretation is not None
    assert historical.interpretation.interpretation_id in {row.interpretation_id for row in v1_rows}


def test_extractor_change_creates_only_its_matching_generation(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A changed XBRL extractor cannot reuse XBRL occurrences or interpretations."""
    config_root, original = _published_config(tmp_path)
    changed = load_run_config(
        config_root,
        ConfigVersions(mapping_set="v2"),
        extractor_pins={
            Representation.XBRL: extractor_pin(Representation.XBRL, version=CHANGED_XBRL_EXTRACTOR),
            Representation.PDF: original.pinned.extractor_pdf,
        },
        allow_synthetic_vendor_config=True,
    )
    with ingest.pg_db.runtime_pool() as pool:
        first = _append(ingest, config_root, original, pool)
        second = _append(ingest, config_root, changed, pool)

    first_members = {member.representation: member for member in first.members}
    second_members = {member.representation: member for member in second.members}
    old_xbrl = first_members[Representation.XBRL]
    new_xbrl = second_members[Representation.XBRL]
    assert second.package_id == first.package_id
    assert new_xbrl.capture_ref_id == old_xbrl.capture_ref_id
    assert new_xbrl.extractor_pin.version == CHANGED_XBRL_EXTRACTOR
    assert set(new_xbrl.occurrence_ids).isdisjoint(old_xbrl.occurrence_ids)
    assert set(new_xbrl.interpretation_ids).isdisjoint(old_xbrl.interpretation_ids)
    assert (
        second_members[Representation.PDF].occurrence_ids
        == first_members[Representation.PDF].occurrence_ids
    )
    assert (
        second_members[Representation.PDF].interpretation_ids
        == first_members[Representation.PDF].interpretation_ids
    )


def test_partial_member_failure_remains_an_exact_capture_free_attempt(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A refused PDF stays in the handoff even though the package contains only XBRL."""
    config_root, loaded = _published_config(tmp_path)
    intake = ingest.intake().model_copy(update={"results_pdf_source_id": None})
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, config_root, loaded, pool, intake=intake)

    assert {member.representation for member in handoff.members} == {Representation.XBRL}
    (refused_id,) = handoff.capture_free_attempt_ids
    assert refused_id in handoff.attempt_ids
    (refused,) = ingest.repository.get_attempts([refused_id])
    assert refused.representation is Representation.PDF
    assert refused.stage is AttemptStage.ACQUISITION
    assert refused.outcome is ExtractionOutcome.NOT_AUTHORISED
    assert refused.capture is None


def test_forged_loaded_config_refuses_before_any_generation_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A caller-consistent model with a forged publication pin has no write authority."""
    config_root, loaded = _published_config(tmp_path)
    assert loaded.pinned.vendor_publication is not None
    forged = loaded.model_copy(
        update={
            "pinned": loaded.pinned.model_copy(
                update={
                    "vendor_publication": VersionPin(
                        version=loaded.pinned.vendor_publication.version,
                        content_sha256="0" * 64,
                    )
                }
            )
        }
    )
    before = ingest.table_counts()

    try:
        with ingest.pg_db.runtime_pool() as pool:
            with pytest.raises(
                (VersionContentDriftError, VendorConfigPublicationError),
                match=(
                    "vendor_publication|vendor publication model differs from its persisted "
                    "publication pin"
                ),
            ):
                _append(ingest, config_root, forged, pool)
    finally:
        assert ingest.table_counts() == before


def test_changed_qualification_setting_identity_refuses_unversioned_reuse(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Rows cannot be reused after a setting change they have no stored identity for."""
    config_root, loaded = _published_config(tmp_path)
    with ingest.pg_db.runtime_pool() as pool:
        _append(ingest, config_root, loaded, pool)
        current = ingest.repository.settings_as_of(
            ingest.entity_id,
            SettingKey.FISCAL_YEAR_END_MONTH,
            ingest.repository.store_clock(),
        )
        assert current is not None
        evidence_id = ingest.repository.put_evidence_input(
            EvidenceInputKind.ISSUER_CONFIG,
            "synthetic changed qualification-setting identity",
            "1" * 64,
        )
        ingest.repository.put_settings_record(
            ingest.entity_id,
            SettingKey.FISCAL_YEAR_END_MONTH,
            current.value_text,
            evidence_id,
        )
        before = ingest.table_counts()

        with pytest.raises(FirstPartyGenerationError, match="predate the current qualification"):
            _append(ingest, config_root, loaded, pool)

    assert ingest.table_counts() == before
