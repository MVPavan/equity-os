"""Pure immutability checks for first-party qualification-context binding."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import pytest

from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import (
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    RevisionCause,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.first_party_context import (
    QUALIFICATION_CONTEXT_TRACE_KEY,
    FirstPartyContextError,
    FirstPartyGenerationContext,
    bind_first_party_generation_context,
)
from fundamentals.evidence.repository import SettingsRecord
from fundamentals.pg.identity_seed import SettingKey

RECORDED_AT = datetime(2026, 10, 13, tzinfo=UTC)


def _context(*, record_id: int, evidence_id: int) -> FirstPartyGenerationContext:
    return FirstPartyGenerationContext.from_record(
        SettingsRecord(
            id=record_id,
            entity_id=record_id,
            setting_key=SettingKey.FISCAL_YEAR_END_MONTH,
            value_text="3",
            evidence_input_id=evidence_id,
            recorded_at=RECORDED_AT,
        )
    )


def _unmapped_row(
    context: FirstPartyGenerationContext, *, trace: dict[str, object] | None = None
) -> Interpretation:
    return Interpretation(
        interpretation_id=context.settings_record_id,
        origin=InterpretationOrigin.DIRECT,
        occurrence_id=context.settings_record_id,
        capture_ref_id=context.settings_record_id,
        representation=Representation.XBRL,
        construction_rule_id=None,
        operand_interpretation_ids=(),
        input_digest="synthetic-unmapped-input",
        status=InterpretationStatus.UNMAPPED,
        entity_id=context.entity_id,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        canonical_id=None,
        period=None,
        dictionary_version="synthetic-dictionary-v1",
        key=None,
        dimensions=None,
        value=None,
        interval=None,
        tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
        mapping_set_version="synthetic-mapping-v2",
        mapping_entry_id=None,
        qualification_ref=None,
        condition_evidence=(),
        normalisation_policy_version="synthetic-normalisation-v1",
        extractor_version="synthetic-extractor-v1",
        transform_trace=trace or {"existing": "preserved"},
        reason=None,
        revision_cause=RevisionCause.ORIGINAL,
        supersedes_interpretation_id=None,
        recorded_at=RECORDED_AT,
    )


def test_bound_context_is_immutable_before_persistence_and_json_stable() -> None:
    """Binding validates the new row without changing its typed values or source row."""
    context = _context(record_id=11, evidence_id=12)
    source = _unmapped_row(context)
    source_before = source.model_dump(mode="json")

    bound = bind_first_party_generation_context(source, context)

    assert source.model_dump(mode="json") == source_before
    for name in type(source).model_fields:
        if name != "transform_trace":
            assert getattr(bound, name) == getattr(source, name)
    with pytest.raises(TypeError):
        cast(dict[str, object], bound.transform_trace)["changed"] = True
    stored_context = cast(dict[str, object], bound.transform_trace[QUALIFICATION_CONTEXT_TRACE_KEY])
    with pytest.raises(TypeError):
        stored_context["value_text"] = "12"

    expected_trace = {
        "existing": "preserved",
        QUALIFICATION_CONTEXT_TRACE_KEY: context.trace_payload(),
    }
    assert bound.model_dump(mode="json")["transform_trace"] == expected_trace
    assert json.loads(bound.model_dump_json())["transform_trace"] == expected_trace


def test_binding_refuses_a_different_reserved_context_without_mutation() -> None:
    """A valid but different reserved context remains a collision, never an overwrite."""
    expected = _context(record_id=21, evidence_id=22)
    different = _context(record_id=23, evidence_id=24)
    source = _unmapped_row(
        expected,
        trace={QUALIFICATION_CONTEXT_TRACE_KEY: different.trace_payload()},
    )
    source_before = source.model_dump(mode="json")

    with pytest.raises(FirstPartyContextError, match="conflicting reserved"):
        bind_first_party_generation_context(source, expected)

    assert source.model_dump(mode="json") == source_before
