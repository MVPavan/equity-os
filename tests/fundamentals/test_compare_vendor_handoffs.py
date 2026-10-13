"""Exact first-party consumer closure and forged-handoff refusal (D1b Task 6).

These are new-API characterization tests. Missing imports are not behavioral
RED evidence. All positive fixtures use the accepted synthetic producer inside
the guarded PostgreSQL harness, without granting real release authority.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

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
from retained_support import apar_store
from test_first_party_generation import _append, _published_config
from test_vendor_config_publication import _draft_root, _publish_synthetic

from fundamentals.api.config import FundamentalsConfig
from fundamentals.compare.run_config import ConfigVersions, LoadedConfig, load_run_config
from fundamentals.compare.run_models import (
    FIRST_PARTY_SOURCES,
    DatabaseIdentity,
    RunInputDisposition,
    RunInputKind,
    RunRequest,
    RunScope,
)
from fundamentals.compare.vendor_handoffs import (
    FirstPartyHandoffError,
    validate_first_party_handoff,
)
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import AttemptStage, FilingFamily, RunMode, VersionPin
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.first_party_context import FirstPartyGenerationContext
from fundamentals.evidence.first_party_extract import pdf_statement_specs_sha256
from fundamentals.evidence.first_party_generation import (
    FirstPartyGenerationHandoff,
    append_first_party_generation,
)
from fundamentals.extract.pdf_statement_pages import specs_from_config
from fundamentals.pg.identity_seed import EvidenceInputKind, SettingKey

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def _fixture(
    ingest: Ingest, tmp_path: Path
) -> tuple[Path, LoadedConfig, FirstPartyGenerationHandoff]:
    root, config = _published_config(tmp_path)
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, root, config, pool)
    return root, config, handoff


def _request(
    ingest: Ingest,
    config: LoadedConfig,
    handoff: FirstPartyGenerationHandoff,
    *,
    cutoff: datetime | None = None,
    mode: RunMode = RunMode.AS_KNOWN,
) -> RunRequest:
    return RunRequest(
        scope=RunScope(
            entity_ids=(ingest.entity_id,),
            period_ends=(handoff.reporting_period_end,),
            bases=(handoff.basis,),
            sources=FIRST_PARTY_SOURCES,
        ),
        cutoff=cutoff or ingest.repository.store_clock(),
        mode=mode,
        pinned=config.pinned,
        code_version="synthetic-handoff-characterization",
        database_identity=DatabaseIdentity(
            host=ingest.pg_db.settings.host,
            port=ingest.pg_db.settings.port,
            name=ingest.pg_db.dbname,
        ),
    )


def test_exact_handoff_reloads_and_closes_all_rows_without_writes(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Validated manifest inputs include context and every exact evidence identity."""
    root, config, handoff = _fixture(ingest, tmp_path)
    request = _request(ingest, config, handoff)
    before = ingest.table_counts()
    scope = validate_first_party_handoff(
        handoff, request=request, config=config, config_root=root, repository=ingest.repository
    )

    assert scope.package.package_id == handoff.package_id
    assert scope.package_eligible
    assert set(scope.eligible_interpretation_ids) == {
        item for member in handoff.members for item in member.interpretation_ids
    }
    assert set(scope.eligible_occurrence_ids) == {
        item for member in handoff.members for item in member.occurrence_ids
    }
    inputs = {(item.kind, item.ref_id): item.disposition for item in scope.inputs}
    assert inputs[RunInputKind.PACKAGE, handoff.package_id] is RunInputDisposition.SELECTED
    assert (
        inputs[RunInputKind.SETTINGS_RECORD, handoff.fiscal_year_end_setting_id]
        is RunInputDisposition.SELECTED
    )
    assert (
        inputs[RunInputKind.EVIDENCE_INPUT, handoff.fiscal_year_end_setting_evidence_input_id]
        is RunInputDisposition.SELECTED
    )
    for member in handoff.members:
        assert (
            inputs[RunInputKind.CAPTURE_REF, member.capture_ref_id] is RunInputDisposition.SELECTED
        )
        for interpretation_id in member.interpretation_ids:
            assert (
                inputs[RunInputKind.INTERPRETATION, interpretation_id]
                is RunInputDisposition.SELECTED
            )
        for condition_id in member.qualification_evidence_interpretation_ids:
            assert (RunInputKind.INTERPRETATION, condition_id) in inputs
    assert {item.ref_id for item in scope.inputs if item.kind is RunInputKind.ATTEMPT} == set(
        handoff.attempt_ids
    )
    assert {
        item.ref_id for item in scope.inputs if item.kind is RunInputKind.ALIGNMENT_PROOF
    } == set(handoff.alignment_proof_ids)
    assert not any(item.kind is RunInputKind.CALCULATION_TRACE for item in scope.inputs)
    assert ingest.table_counts() == before


def test_forged_handoff_ids_pins_bounds_context_and_scope_refuse_without_writes(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A caller-built object cannot turn summaries or IDs into authority."""
    root, config, handoff = _fixture(ingest, tmp_path)
    request = _request(ingest, config, handoff)
    before = ingest.table_counts()
    member = handoff.members[0]
    changed_member = member.model_copy(update={"record_sha256": "0" * 64})
    for updates in (
        {"package_id": 999999999},
        {"package_evidence_sha256": "0" * 64},
        {"publication_sha256": "0" * 64},
        {"dictionary_pin": VersionPin(version="v1", content_sha256="0" * 64)},
        {"formula_set_pin": VersionPin(version="v1", content_sha256="0" * 64)},
        {"mapping_set_pin": VersionPin(version="v2", content_sha256="0" * 64)},
        {"extractor_pins": handoff.extractor_pins[:1]},
        {"members": (changed_member, *handoff.members[1:])},
        {"members": handoff.members[:1]},
        {"attempt_ids": handoff.attempt_ids[:-1]},
        {"capture_free_attempt_ids": handoff.attempt_ids[:1]},
        {"alignment_proof_ids": handoff.alignment_proof_ids[:-1]},
        {"fiscal_year_end_setting_evidence_input_id": 999999999},
        {"fiscal_year_end_month": 12},
        {"qualification_context_sha256": "0" * 64},
        {"qualification_context_trace_stored": False},
        {"basis": Basis.STANDALONE},
    ):
        claimed = handoff.model_copy(update=updates)
        with pytest.raises(FirstPartyHandoffError):
            validate_first_party_handoff(
                claimed,
                request=request,
                config=config,
                config_root=root,
                repository=ingest.repository,
            )
        assert ingest.table_counts() == before


def test_jointly_omitted_occurrence_and_direct_interpretation_cannot_hide_evidence(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Closing supplied IDs is insufficient: the whole pinned capture set must agree."""
    root, config, handoff = _fixture(ingest, tmp_path)
    member = next(item for item in handoff.members if item.representation is Representation.XBRL)
    rows = ingest.repository.get_interpretations(member.interpretation_ids)
    # An unqualified unused direct row is deliberately removable without breaking operands.
    dependencies = {item for row in rows for item in row.operand_interpretation_ids}
    victim = next(
        row
        for row in rows
        if row.occurrence_id is not None
        and row.qualification_ref is None
        and row.interpretation_id not in dependencies
        and row.interpretation_id not in member.qualification_evidence_interpretation_ids
    )
    changed = member.model_copy(
        update={
            "occurrence_ids": tuple(
                item for item in member.occurrence_ids if item != victim.occurrence_id
            ),
            "interpretation_ids": tuple(
                item for item in member.interpretation_ids if item != victim.interpretation_id
            ),
            "interpretation_recorded_at_min": min(
                row.recorded_at for row in rows if row.interpretation_id != victim.interpretation_id
            ),
            "interpretation_recorded_at_max": max(
                row.recorded_at for row in rows if row.interpretation_id != victim.interpretation_id
            ),
        }
    )
    claimed = handoff.model_copy(
        update={"members": tuple(changed if item == member else item for item in handoff.members)}
    )
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="complete occurrence"):
        validate_first_party_handoff(
            claimed,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


@pytest.mark.parametrize("change", ["whitespace", "month", "symlink"])
def test_settings_artifact_bytes_and_descriptor_identity_are_reproved(
    ingest: Ingest, tmp_path: Path, change: str
) -> None:
    """Matching database time/month/hash claims cannot authorize changed source bytes."""
    root, config, handoff = _fixture(ingest, tmp_path)
    path = root / "identity" / "aparinds.yaml"
    body = path.read_bytes()
    if change == "whitespace":
        path.write_bytes(body + b"\n")
    elif change == "month":
        path.write_bytes(body.replace(b"fiscal_year_end_month: 3", b"fiscal_year_end_month: 12"))
    else:
        outside = tmp_path / "identity-outside.yaml"
        outside.write_bytes(body)
        path.unlink()
        path.symlink_to(outside)
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="artifact|symlink|unsafe|regular|path"):
        validate_first_party_handoff(
            handoff,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


@pytest.mark.parametrize(
    ("kind", "label", "content_sha256"),
    [
        (EvidenceInputKind.ISSUER_CONFIG, "APARINDS", None),
        (EvidenceInputKind.ISSUER_IDENTITY, "../../identity/aparinds.yaml", "0" * 64),
        (EvidenceInputKind.ISSUER_IDENTITY, "APARINDS", "1" * 64),
    ],
)
def test_exact_settings_record_still_needs_actual_kind_label_and_content_source(
    ingest: Ingest,
    tmp_path: Path,
    kind: EvidenceInputKind,
    label: str,
    content_sha256: str | None,
) -> None:
    """A self-consistent new settings row with forged source metadata is refused."""
    root, config, handoff = _fixture(ingest, tmp_path)
    content = (
        content_sha256
        or hashlib.sha256((root / "identity" / "aparinds.yaml").read_bytes()).hexdigest()
    )
    evidence_id = ingest.repository.put_evidence_input(kind, label, content)
    record_id = ingest.repository.put_settings_record(
        ingest.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, "3", evidence_id
    )
    (record,) = ingest.repository.get_settings_records([record_id])
    context = FirstPartyGenerationContext.from_record(record)
    claimed = handoff.model_copy(
        update={
            "fiscal_year_end_setting_id": record.id,
            "fiscal_year_end_setting_evidence_input_id": evidence_id,
            "fiscal_year_end_setting_recorded_at": record.recorded_at,
            "qualification_context_sha256": context.record_sha256,
        }
    )
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="kind/label/content"):
        validate_first_party_handoff(
            claimed,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def test_as_known_excludes_later_v2_rows_while_retrospective_uses_only_that_handoff(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Cutoff eligibility never obtains a v1 fallback or silently discards manifest rows."""
    ingest.run(ingest.intake())
    cutoff = ingest.repository.store_clock()
    root, config, handoff = _fixture(ingest, tmp_path)
    before = ingest.table_counts()
    known = validate_first_party_handoff(
        handoff,
        request=_request(ingest, config, handoff, cutoff=cutoff),
        config=config,
        config_root=root,
        repository=ingest.repository,
    )
    retrospective = validate_first_party_handoff(
        handoff,
        request=_request(ingest, config, handoff, cutoff=cutoff, mode=RunMode.RETROSPECTIVE),
        config=config,
        config_root=root,
        repository=ingest.repository,
    )
    assert known.package_eligible
    assert not known.eligible_interpretation_ids
    assert all(
        item.disposition is RunInputDisposition.NOT_SELECTED
        for item in known.inputs
        if item.kind is RunInputKind.INTERPRETATION
    )
    assert set(retrospective.eligible_interpretation_ids) == {
        item for member in handoff.members for item in member.interpretation_ids
    }
    assert known.interpretations == retrospective.interpretations
    assert ingest.table_counts() == before


def test_changed_publication_is_refused_before_any_evidence_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A once-loaded config cannot authorize rows after publication content changes."""
    root, config, handoff = _fixture(ingest, tmp_path)
    publication_path = root / "vendor_publication" / "v2.yaml"
    publication_path.write_bytes(publication_path.read_bytes() + b"\n")
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError):
        validate_first_party_handoff(
            handoff,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def _partial_acquisition(
    ingest: Ingest, tmp_path: Path
) -> tuple[Path, LoadedConfig, FirstPartyGenerationHandoff]:
    root, config = _published_config(tmp_path)
    intake = ingest.intake().model_copy(update={"results_pdf_source_id": None})
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, root, config, pool, intake=intake)
    (failure,) = ingest.repository.get_attempts(handoff.capture_free_attempt_ids)
    assert failure.stage is AttemptStage.ACQUISITION
    assert failure.extractor_version == ""
    assert failure.outcome is ExtractionOutcome.NOT_AUTHORISED
    assert failure.capture is None
    assert failure.package_id == handoff.package_id
    return root, config, handoff


def test_partial_package_accepts_real_capture_free_acquisition_and_closes_failure(
    ingest: Ingest, tmp_path: Path
) -> None:
    """The real first-party acquisition contract has no extractor or captured body."""
    root, config, handoff = _partial_acquisition(ingest, tmp_path)
    before = ingest.table_counts()
    try:
        scope = validate_first_party_handoff(
            handoff,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    except FirstPartyHandoffError as error:
        pytest.fail(f"legitimate capture-free first-party acquisition was refused: {error}")
    (failure_id,) = handoff.capture_free_attempt_ids
    assert {row.attempt_id for row in scope.attempts} == set(handoff.attempt_ids)
    assert any(
        item.kind is RunInputKind.ATTEMPT
        and item.ref_id == failure_id
        and item.disposition is RunInputDisposition.FAILED_ATTEMPT
        for item in scope.inputs
    )
    assert {member.representation for member in handoff.members} == {Representation.XBRL}
    assert scope.package_eligible
    assert ingest.table_counts() == before


def test_joint_omission_of_real_capture_free_acquisition_is_refused(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Removing a true failed acquisition from both handoff sets cannot hide a peer."""
    root, config, handoff = _partial_acquisition(ingest, tmp_path)
    claimed = handoff.model_copy(
        update={
            "attempt_ids": tuple(
                item for item in handoff.attempt_ids if item not in handoff.capture_free_attempt_ids
            ),
            "capture_free_attempt_ids": (),
        }
    )
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="complete.*attempt"):
        validate_first_party_handoff(
            claimed,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def _captured_failure_fixture(
    ingest: Ingest, tmp_path: Path
) -> tuple[Path, LoadedConfig, FirstPartyGenerationHandoff]:
    """A real stored PDF failure under explicit source-derived private parser settings."""
    root, config = _published_config(tmp_path)
    path = root / "aparinds-fy26-q2.yaml"
    document = yaml.safe_load(path.read_bytes())
    for family in ("PL", "BALANCE_SHEET", "CASH_FLOW", "SEGMENT"):
        document["pdf_parse"]["statement_pages"].setdefault(family, {})["title_markers"] = [
            "missing statement heading for explicit parser-refusal fixture"
        ]
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    issuer = FundamentalsConfig.model_validate(document)
    with ingest.pg_db.runtime_pool() as pool:
        handoff = append_first_party_generation(
            intake=ingest.intake(),
            snapshot_store=apar_store(ingest.tmp_path),
            pool=pool,
            config=config,
            config_root=root,
            entity_id=ingest.entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=Q2_END,
            pdf_specs=specs_from_config(issuer.pdf_parse),
        )
    assert {member.representation for member in handoff.members} == {Representation.XBRL}
    return root, config, handoff


def test_captured_unusable_pdf_peer_keeps_exact_failure_and_capture_closure(
    ingest: Ingest, tmp_path: Path
) -> None:
    """A configured PDF whose statement blocks cannot be found is still deciding evidence."""
    root, config, handoff = _captured_failure_fixture(ingest, tmp_path)
    failures = tuple(
        row
        for row in ingest.repository.get_attempts(handoff.attempt_ids)
        if row.representation is Representation.PDF
    )
    assert failures and all(row.outcome is not ExtractionOutcome.COMPLETE for row in failures)
    assert all(row.capture is not None for row in failures)
    deciding_capture_ids = {
        row.capture.capture_ref_id for row in failures if row.capture is not None
    }
    before = ingest.table_counts()
    try:
        scope = validate_first_party_handoff(
            handoff,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    except FirstPartyHandoffError as error:
        pytest.fail(f"legitimate captured failed peer was refused: {error}")
    assert deciding_capture_ids <= {row.capture_ref_id for row in scope.capture_refs}
    assert deciding_capture_ids <= {
        item.ref_id for item in scope.inputs if item.kind is RunInputKind.CAPTURE_REF
    }
    assert {row.attempt_id for row in failures} <= {
        item.ref_id
        for item in scope.inputs
        if item.kind is RunInputKind.ATTEMPT
        and item.disposition is RunInputDisposition.FAILED_ATTEMPT
    }
    (member,) = handoff.members
    early = validate_first_party_handoff(
        handoff,
        request=_request(ingest, config, handoff, cutoff=member.capture_first_seen_at),
        config=config,
        config_root=root,
        repository=ingest.repository,
    )
    assert deciding_capture_ids.isdisjoint(
        item.ref_id
        for item in early.inputs
        if item.kind is RunInputKind.CAPTURE_REF
        and item.disposition is RunInputDisposition.SELECTED
    )
    assert {row.attempt_id for row in failures}.isdisjoint(early.eligible_attempt_ids)
    assert ingest.table_counts() == before


def test_joint_omission_of_captured_failed_pdf_peer_is_refused(
    ingest: Ingest, tmp_path: Path
) -> None:
    """The failure cannot disappear merely because its capture is not a package member."""
    root, config, handoff = _captured_failure_fixture(ingest, tmp_path)
    failed_ids = {
        row.attempt_id
        for row in ingest.repository.get_attempts(handoff.attempt_ids)
        if row.representation is Representation.PDF
    }
    assert failed_ids and not handoff.capture_free_attempt_ids
    claimed = handoff.model_copy(
        update={
            "attempt_ids": tuple(item for item in handoff.attempt_ids if item not in failed_ids)
        }
    )
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="complete.*attempt"):
        validate_first_party_handoff(
            claimed,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def test_failed_peer_cannot_substitute_foreign_captured_source_or_context(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Foreign capture and semantic context claims cannot become deciding PDF evidence."""
    root, config, handoff = _captured_failure_fixture(ingest, tmp_path)
    attempts = ingest.repository.get_attempts(handoff.attempt_ids)
    peer = next(
        row
        for row in attempts
        if row.representation is Representation.PDF and row.statement_family is None
    )
    (member,) = handoff.members
    (foreign_capture,) = ingest.repository.get_capture_refs([member.capture_ref_id])
    for updates in (
        {
            "capture": foreign_capture,
            "input_sha256": foreign_capture.blob_sha256,
            "source_id": foreign_capture.source_id,
            "surface": foreign_capture.surface,
        },
        {"extraction_context_sha256": "0" * 64},
    ):
        forged_row = peer.model_copy(
            update={
                **updates,
                "attempt_id": None,
                "attempted_at": None,
            }
        )
        (stored,) = ingest.repository.put_attempts([forged_row])
        claimed = handoff.model_copy(
            update={
                "attempt_ids": tuple(sorted((*handoff.attempt_ids, stored.attempt_id))),
            }
        )
        before = ingest.table_counts()
        with pytest.raises(FirstPartyHandoffError):
            validate_first_party_handoff(
                claimed,
                request=_request(ingest, config, handoff),
                config=config,
                config_root=root,
                repository=ingest.repository,
            )
        assert ingest.table_counts() == before


@pytest.mark.parametrize("insertion", ["before", "after"])
def test_other_pdf_spec_context_package_attempt_does_not_contaminate_exact_handoff(
    ingest: Ingest, tmp_path: Path, insertion: str
) -> None:
    """Earlier or later attempts in another real PDF semantic context stay outside closure."""
    root, config = _published_config(tmp_path)
    legacy = ingest.run(ingest.intake())
    (package,) = ingest.repository.get_packages([legacy.package_id])
    capture = package.members[Representation.PDF].capture
    base = next(
        row
        for row in legacy.attempts
        if row.representation is Representation.PDF and row.statement_family is None
    )
    alternative_specs = dict(apar_pdf_specs())
    alternative_specs[StatementFamily.BALANCE_SHEET] = alternative_specs[
        StatementFamily.BALANCE_SHEET
    ].model_copy(update={"title_markers": ("another explicit PDF statement specification",)})
    other_context = pdf_statement_specs_sha256(alternative_specs)
    assert other_context != base.extraction_context_sha256
    other = base.model_copy(
        update={
            "attempt_id": None,
            "attempted_at": None,
            "package_id": package.package_id,
            "statement_family": StatementFamily.BALANCE_SHEET,
            "outcome": ExtractionOutcome.PARSE_FAILED,
            "extraction_context_sha256": other_context,
            "reason": "another source-derived PDF specification did not locate this family",
        }
    )
    if insertion == "before":
        (stored_other,) = ingest.repository.put_attempts([other])
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, root, config, pool)
    historical_request = _request(ingest, config, handoff)
    if insertion == "after":
        (stored_other,) = ingest.repository.put_attempts([other])
    assert stored_other.capture == capture
    assert stored_other.attempt_id not in handoff.attempt_ids
    before = ingest.table_counts()
    try:
        scope = validate_first_party_handoff(
            handoff,
            request=historical_request,
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    except FirstPartyHandoffError as error:
        pytest.fail(f"another PDF context invalidated the exact handoff: {error}")
    assert stored_other.attempt_id not in {
        item.ref_id for item in scope.inputs if item.kind is RunInputKind.ATTEMPT
    }
    assert {row.attempt_id for row in scope.attempts} == set(handoff.attempt_ids)
    forged = handoff.model_copy(
        update={
            "attempt_ids": tuple(
                sorted(
                    (
                        *handoff.attempt_ids,
                        stored_other.attempt_id,
                    )
                )
            )
        }
    )
    with pytest.raises(FirstPartyHandoffError):
        validate_first_party_handoff(
            forged,
            request=historical_request,
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def _pdf_only_with_failed_xbrl(
    ingest: Ingest, tmp_path: Path
) -> tuple[Path, LoadedConfig, FirstPartyGenerationHandoff]:
    """Retained XML honestly fails schema support; the unchanged PDF remains usable."""
    root = _draft_root(tmp_path)
    path = root / "mappings" / "v2.yaml"
    document = yaml.safe_load(path.read_bytes())
    document["entry_files"].remove("xbrl/v1/in_capmkt.yaml")
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    construction_path = root / "mappings" / "constructions" / "v1.yaml"
    constructions = yaml.safe_load(construction_path.read_bytes())
    constructions["constructions"] = [
        rule
        for rule in constructions["constructions"]
        if rule["rule_id"] != "capmkt.profit_before_tax_incl_associates"
    ]
    construction_path.write_text(yaml.safe_dump(constructions, sort_keys=False), encoding="utf-8")
    _publish_synthetic(root)
    config = load_run_config(
        root, ConfigVersions(mapping_set="v2"), allow_synthetic_vendor_config=True
    )
    with ingest.pg_db.runtime_pool() as pool:
        handoff = _append(ingest, root, config, pool)
    assert {member.representation for member in handoff.members} == {Representation.PDF}
    failures = tuple(
        row
        for row in ingest.repository.get_attempts(handoff.attempt_ids)
        if row.representation is Representation.XBRL
    )
    assert len(failures) == 1
    assert failures[0].outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
    assert failures[0].capture is not None
    assert failures[0].package_id is None
    return root, config, handoff


def test_pdf_only_failed_xbrl_refuses_without_independent_retained_intake_binding(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Failed-peer IDs and their own hashes cannot supply the missing source witness."""
    root, config, handoff = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="XBRL.*binding|XBRL.*witness"):
        validate_first_party_handoff(
            handoff,
            request=_request(ingest, config, handoff),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


def test_different_failed_xbrl_body_ids_cannot_manufacture_missing_source_binding(
    ingest: Ingest, tmp_path: Path
) -> None:
    """Combining actual failure records from two physical bodies grants no source authority."""
    root, config, first = _pdf_only_with_failed_xbrl(ingest, tmp_path)
    # This explicit private malformed input produces a failure only, never a financial fact.
    path = tmp_path / "marked-unreadable-xbrl.xml"
    path.write_bytes(b"explicit second malformed XBRL fixture; no financial observations\n")
    intake = ingest.intake(marked={Representation.XBRL: path})
    original_source = next(
        row.source_id
        for row in ingest.repository.get_attempts(first.attempt_ids)
        if row.representation is Representation.XBRL
    )
    intake = intake.model_copy(
        update={
            "bindings": tuple(
                binding.model_copy(update={"source_id": original_source})
                if binding.representation is Representation.XBRL
                else binding
                for binding in intake.bindings
            ),
        }
    )
    with ingest.pg_db.runtime_pool() as pool:
        second = _append(ingest, root, config, pool, intake=intake)
    first_failure = next(
        row
        for row in ingest.repository.get_attempts(first.attempt_ids)
        if row.representation is Representation.XBRL
    )
    second_failure = next(
        row
        for row in ingest.repository.get_attempts(second.attempt_ids)
        if row.representation is Representation.XBRL
    )
    assert first.package_id == second.package_id
    assert first_failure.capture is not None and second_failure.capture is not None
    assert first_failure.input_sha256 != second_failure.input_sha256
    assert first_failure.capture.capture_ref_id != second_failure.capture.capture_ref_id
    assert second_failure.outcome is ExtractionOutcome.PARSE_FAILED
    expanded = first.model_copy(
        update={"attempt_ids": tuple(sorted(set(first.attempt_ids) | set(second.attempt_ids)))}
    )
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError, match="XBRL.*binding|XBRL.*witness"):
        validate_first_party_handoff(
            expanded,
            request=_request(ingest, config, first),
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before
