"""Pure witnessed replay closure using actual immutable retained generation records."""

from datetime import timedelta
from pathlib import Path

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from retained_intake_witness_support import witnessed_reverse_fixture
from test_compare_vendor_handoffs import _request

from fundamentals.compare.resolve import recompute
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.retained_intake_replay import (
    require_witness_manifest_closure,
    require_witness_replay_context,
)
from fundamentals.compare.run_models import RunInputDisposition, RunInputKind
from fundamentals.compare.vendor_handoffs import (
    FirstPartyHandoffError,
    validate_first_party_handoff,
)
from fundamentals.contracts.evidence import VersionPin
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.retained_intake_models import RetainedIntakeWitnessError

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def _closed(ingest: Ingest, tmp_path: Path):
    root, config, handoff = witnessed_reverse_fixture(ingest, tmp_path)
    request = _request(ingest, config, handoff)
    scope = validate_first_party_handoff(
        handoff, request=request, config=config, config_root=root, repository=ingest.repository
    )
    # The pure guard does not evaluate or publish this definition set. Full resolver
    # integration separately supplies its actually pinned definition_set_id.
    inputs = ResolvedInputs(
        definition_set_id=1,
        capture_refs=scope.capture_refs,
        packages=(scope.package,),
        occurrences=scope.occurrences,
        interpretations=scope.interpretations,
        attempts=scope.attempts,
        proofs=scope.proofs,
        evidence_inputs=scope.evidence_inputs,
        settings=scope.settings,
        inputs=scope.inputs,
    )
    return root, config, handoff, request, scope, inputs


def test_witnessed_pure_replay_reads_no_originals_repository_or_latest(
    ingest: Ingest, tmp_path: Path, monkeypatch
) -> None:
    _, config, _, request, _, inputs = _closed(ingest, tmp_path)
    before = ingest.table_counts()

    def forbidden(*args, **kwargs):
        raise AssertionError("pure witness replay reached a filesystem or repository read")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    for method in (
        "list_attempts",
        "get_packages",
        "get_capture_refs",
        "get_evidence_inputs",
        "get_settings_records",
        "get_attempts",
        "issuer_identifiers",
    ):
        monkeypatch.setattr(EvidenceRepository, method, forbidden)
    require_witness_manifest_closure(inputs)
    require_witness_replay_context(inputs, request, config=config)
    assert ingest.table_counts() == before


@pytest.mark.parametrize(
    "kind",
    (
        RunInputKind.EVIDENCE_INPUT,
        RunInputKind.SETTINGS_RECORD,
        RunInputKind.PACKAGE,
        RunInputKind.CAPTURE_REF,
        RunInputKind.ATTEMPT,
        RunInputKind.OCCURRENCE,
        RunInputKind.INTERPRETATION,
    ),
)
def test_witness_required_association_cannot_escape_tagged_manifest(
    ingest: Ingest, tmp_path: Path, kind: RunInputKind
) -> None:
    _, _, _, _, _, inputs = _closed(ingest, tmp_path)
    removed = next(row for row in inputs.inputs if row.kind is kind)
    forged = inputs.model_copy(
        update={"inputs": tuple(row for row in inputs.inputs if row != removed)}
    )
    before = ingest.table_counts()
    with pytest.raises(RetainedIntakeWitnessError, match="escapes manifest"):
        require_witness_manifest_closure(forged)
    assert ingest.table_counts() == before


def test_manifest_named_id_without_loaded_row_cannot_supply_witness_closure(
    ingest: Ingest, tmp_path: Path
) -> None:
    _, _, _, _, _, inputs = _closed(ingest, tmp_path)
    forged = inputs.model_copy(update={"attempts": inputs.attempts[1:]})
    with pytest.raises(RetainedIntakeWitnessError, match="escapes manifest"):
        require_witness_manifest_closure(forged)


def test_later_witness_is_valid_but_not_selected_before_its_seal(
    ingest: Ingest, tmp_path: Path
) -> None:
    root, config, handoff, _, _, inputs = _closed(ingest, tmp_path)
    witness_record = next(
        row for row in inputs.evidence_inputs if row.id == handoff.retained_intake_witness_id
    )
    witness = witness_record.retained_intake_witness
    assert witness is not None
    request = _request(
        ingest, config, handoff, cutoff=witness.sealed_at - timedelta(microseconds=1)
    )
    scope = validate_first_party_handoff(
        handoff, request=request, config=config, config_root=root, repository=ingest.repository
    )
    assert not scope.package_eligible
    assert scope.eligible_occurrence_ids == scope.eligible_interpretation_ids == ()
    assert scope.eligible_attempt_ids == ()
    assert (
        next(
            row.disposition
            for row in scope.inputs
            if row.kind is RunInputKind.EVIDENCE_INPUT and row.ref_id == witness.evidence_input_id
        )
        is RunInputDisposition.NOT_SELECTED
    )
    old = inputs.model_copy(update={"inputs": scope.inputs})
    with pytest.raises(RetainedIntakeWitnessError, match="future witness"):
        require_witness_replay_context(old, request, config=config)
    with pytest.raises(RetainedIntakeWitnessError, match="future witness"):
        require_witness_replay_context(inputs, request, config=config)


def test_unavailable_witness_cannot_reenter_engine_through_recompute(
    ingest: Ingest, tmp_path: Path, monkeypatch
) -> None:
    root, config, handoff, _, _, inputs = _closed(ingest, tmp_path)
    record = next(
        row for row in inputs.evidence_inputs if row.id == handoff.retained_intake_witness_id
    )
    witness = record.retained_intake_witness
    assert witness is not None
    request = _request(
        ingest, config, handoff, cutoff=witness.sealed_at - timedelta(microseconds=1)
    )
    scope = validate_first_party_handoff(
        handoff, request=request, config=config, config_root=root, repository=ingest.repository
    )
    old = inputs.model_copy(update={"inputs": scope.inputs})
    calls = []

    class ObservedEngine:
        def __init__(self, *args, **kwargs):
            calls.append(True)

        def rows(self):
            return ()

    monkeypatch.setattr("fundamentals.compare.resolve.RunEngine", ObservedEngine)
    with pytest.raises(RetainedIntakeWitnessError, match="future witness"):
        recompute(old, request, config=config)
    assert calls == []


def test_witness_envelope_cannot_be_relabelled_even_with_same_domain_ids(
    ingest: Ingest, tmp_path: Path
) -> None:
    _, _, handoff, _, _, inputs = _closed(ingest, tmp_path)
    altered = tuple(
        row.model_copy(update={"label": "another-original-material"})
        if row.id == handoff.retained_intake_witness_id
        else row
        for row in inputs.evidence_inputs
    )
    with pytest.raises(RetainedIntakeWitnessError, match="envelope"):
        require_witness_manifest_closure(inputs.model_copy(update={"evidence_inputs": altered}))


def test_legacy_inputs_without_new_evidence_kind_require_no_witness() -> None:
    require_witness_manifest_closure(ResolvedInputs(definition_set_id=1))


@pytest.mark.parametrize(
    "changed",
    ("package", "publication", "setting", "context", "kind", "attempt", "member", "pin"),
)
def test_witnessed_handoff_substitution_refuses_without_writes(
    ingest: Ingest, tmp_path: Path, changed: str
) -> None:
    root, config, handoff, request, _, _ = _closed(ingest, tmp_path)
    updates = {
        "package": {"package_id": handoff.package_id + 100000},
        "publication": {"publication_sha256": "0" * 64},
        "setting": {"fiscal_year_end_setting_id": handoff.fiscal_year_end_setting_id + 100000},
        "context": {"qualification_context_sha256": "0" * 64},
        "kind": {"retained_intake_witness_id": handoff.fiscal_year_end_setting_evidence_input_id},
        "attempt": {"attempt_ids": handoff.attempt_ids[1:]},
        "member": {"members": (handoff.members[0].model_copy(update={"blob_sha256": "0" * 64}),)},
        "pin": {
            "mapping_set_pin": VersionPin(
                version=handoff.mapping_set_pin.version, content_sha256="0" * 64
            )
        },
    }[changed]
    before = ingest.table_counts()
    with pytest.raises(FirstPartyHandoffError):
        validate_first_party_handoff(
            handoff.model_copy(update=updates),
            request=request,
            config=config,
            config_root=root,
            repository=ingest.repository,
        )
    assert ingest.table_counts() == before


@pytest.mark.parametrize("changed", ("schema", "input", "clock"))
def test_transport_material_substitution_cannot_gain_replay_authority(
    ingest: Ingest, tmp_path: Path, changed: str
) -> None:
    _, config, handoff, request, _, inputs = _closed(ingest, tmp_path)
    record = next(
        row for row in inputs.evidence_inputs if row.id == handoff.retained_intake_witness_id
    )
    witness = record.retained_intake_witness
    assert witness is not None
    if changed in {"schema", "input"}:
        prepared = witness.payload.prepared
        updated = (
            {"schema_version": "another_schema"}
            if changed == "schema"
            else {
                "requests": tuple(
                    row.model_copy(update={"expected_input_sha256": "0" * 64})
                    for row in prepared.requests
                )
            }
        )
        payload = witness.payload.model_copy(
            update={"prepared": prepared.model_copy(update=updated)}
        )
        altered = witness.model_copy(update={"payload": payload})
        altered_record = record.model_copy(update={"retained_intake_witness": altered})
    else:
        future = request.cutoff + timedelta(days=1)
        altered = witness.model_copy(update={"recorded_at": future, "sealed_at": future})
        altered_record = record.model_copy(
            update={
                "recorded_at": future,
                "retained_intake_witness": altered,
            }
        )
    altered_inputs = inputs.model_copy(
        update={
            "evidence_inputs": tuple(
                altered_record if row.id == record.id else row for row in inputs.evidence_inputs
            )
        }
    )
    before = ingest.table_counts()
    with pytest.raises(ValueError):
        require_witness_replay_context(altered_inputs, request, config=config)
    assert ingest.table_counts() == before


def test_unrelated_parser_context_does_not_invalidate_sealed_original_witness(
    ingest: Ingest, tmp_path: Path
) -> None:
    root, config, handoff, request, scope, _ = _closed(ingest, tmp_path)
    peer = next(row for row in scope.attempts if row.package_id is None)
    assert peer.capture is not None
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as connection:
        connection.execute(
            "INSERT INTO eqos.acquisition_attempts (stage,source_id,surface,entity_id,period_end,"
            "basis,framework,representation,statement_family,package_id,capture_ref_id,input_sha256,"
            "extractor_version,outcome,reason,extraction_context_sha256) "
            "VALUES ('EXTRACTION',%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,%s,%s,%s)",
            (
                peer.source_id,
                peer.surface,
                peer.entity_id,
                peer.period_end,
                peer.basis.value,
                peer.framework.value,
                peer.representation.value,
                peer.capture.capture_ref_id,
                peer.input_sha256,
                peer.extractor_version,
                peer.outcome.value,
                "constructed unrelated parser-context record; no financial observation",
                "f" * 64,
            ),
        )
    before = ingest.table_counts()
    after = validate_first_party_handoff(
        handoff,
        request=request,
        config=config,
        config_root=root,
        repository=ingest.repository,
    )
    assert after.attempts == scope.attempts
    assert after.capture_refs == scope.capture_refs
    assert ingest.table_counts() == before
