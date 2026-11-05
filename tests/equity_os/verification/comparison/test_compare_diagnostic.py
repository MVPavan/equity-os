"""Constructed diagnostic and queue-overlay examples, never vendor acceptance evidence."""

from importlib import import_module

import pytest
from compare_tables_support import EMPTY, POLICY, REVENUE

from equity_os.contracts.verification.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairOutcome,
    ReasonCode,
    SourceState,
)

from .test_compare_corroboration import NOW, evaluate, qualified


def diagnostic(first, other):
    return import_module("equity_os.verification.comparison.tables").diagnostic_pair(
        first, other, definitions=EMPTY, policy=POLICY
    )


def overlay(*items, run_id=1):
    return import_module("equity_os.contracts.verification.review_queue").QueueOverlay(
        run_id=run_id, as_of=NOW, open_items=items, dispositions=()
    )


def stored(draft):
    """The draft as an open item created by run 1."""
    return import_module("equity_os.contracts.verification.review_queue").QueueItem(
        item_id=1,
        run_id=1,
        input_sha256="a" * 64,
        predecessor_item_id=None,
        recorded_at=NOW,
        **draft.model_dump(
            include={
                "key",
                "pair_identity",
                "outcome",
                "severity",
                "diagnostic",
                "routing_reason",
                "reason_code",
                "source_refs",
            }
        ),
    )


def trust(
    view,
    extraction=ExtractionStatus.AGREE,
    corroboration=CorroborationStatus.CORROBORATED,
    first_party_state=SourceState.VALUE,
):
    return import_module("equity_os.verification.review_queue.trust").trusted(
        run_id=1,
        key=REVENUE,
        extraction=extraction,
        corroboration=corroboration,
        first_party_state=first_party_state,
        overlay=view,
    )


@pytest.mark.parametrize("state", [SourceState.VALUE, SourceState.UNAVAILABLE, SourceState.INVALID])
def test_diagnostic_states_never_enter_corroboration_or_completeness(state):
    source = qualified("10000", role="DIAGNOSTIC", state=state)
    result = evaluate(qualified(role="FIRST_PARTY"), (qualified(), source))
    assert result.status is CorroborationStatus.CORROBORATED
    assert result.unavailable_sources == ()
    assert all(side.ref.source_role.value != "DIAGNOSTIC" for side in result.sources)
    assert len(result.pairs) == 1
    assert trust(overlay()).trusted


@pytest.mark.parametrize("qualified_tier", [True, False])
def test_diagnostic_scale_fault_is_medium_before_generic_structural_high(qualified_tier):
    from equity_os.contracts.measurement.evidence_tier import EvidenceTier

    tier = (
        EvidenceTier.EQUIVALENCE_DEMONSTRATED
        if qualified_tier
        else EvidenceTier.EQUIVALENCE_UNPROVEN
    )
    pair = diagnostic(
        qualified("10000", role="DIAGNOSTIC", tier=tier, occurrence_ids=(1,)), qualified()
    )
    assert pair is not None
    assert pair.result.outcome in (PairOutcome.MISMATCH, PairOutcome.ANOMALY)
    item = import_module("equity_os.verification.review_queue.routing").route_pair_draft(
        pair, key=REVENUE
    )
    assert item is not None
    assert item.severity.value == "MEDIUM"
    assert item.routing_reason == "PARSE_CHECK_DISAGREE"
    assert item.diagnostic
    assert trust(overlay(stored(item))).trusted


def test_diagnostic_internal_conflict_refuses_overlap_and_keeps_both_occurrences():
    source = qualified(
        "1000",
        role="DIAGNOSTIC",
        reasons=(ReasonCode.VENDOR_INTERNAL_CONFLICT,),
        occurrence_ids=(101, 102),
    )
    pair = diagnostic(source, qualified())
    assert pair is not None
    assert pair.result.outcome is PairOutcome.NOT_COMPARABLE
    assert pair.result.reason is ReasonCode.VENDOR_INTERNAL_CONFLICT
    item = import_module("equity_os.verification.review_queue.routing").route_pair_draft(
        pair, key=REVENUE
    )
    assert item is not None and item.severity.value == "MEDIUM"
    assert item.evidence_occurrence_ids == (101, 102)
    assert item.diagnostic


def test_diagnostic_unavailability_is_visible_without_a_cell_queue_item():
    assert (
        diagnostic(qualified(None, role="DIAGNOSTIC", state=SourceState.UNAVAILABLE), qualified())
        is None
    )


@pytest.mark.parametrize(
    ("extraction", "corroboration", "first_party", "expected"),
    [
        (ExtractionStatus.AGREE, CorroborationStatus.CORROBORATED, SourceState.VALUE, True),
        (
            ExtractionStatus.NOT_APPLICABLE,
            CorroborationStatus.CORROBORATED,
            SourceState.VALUE,
            True,
        ),
        (
            ExtractionStatus.NOT_APPLICABLE,
            CorroborationStatus.CORROBORATED,
            SourceState.NO_VALUE,
            False,
        ),
        (
            ExtractionStatus.AGREE_UNQUALIFIED,
            CorroborationStatus.CORROBORATED,
            SourceState.VALUE,
            False,
        ),
        (ExtractionStatus.AGREE, CorroborationStatus.AGREES_UNQUALIFIED, SourceState.VALUE, False),
        (ExtractionStatus.AGREE, CorroborationStatus.CONFLICT, SourceState.VALUE, False),
    ],
)
def test_trust_requires_both_checks_without_a_blended_score(
    extraction, corroboration, first_party, expected
):
    result = trust(overlay(), extraction, corroboration, first_party)
    assert result.trusted is expected
    assert result.run_id == 1
    assert result.overlay_as_of == NOW
    assert result.key_digest == REVENUE.digest()


def test_open_independent_high_blocks_only_its_cell_and_named_overlay():
    result = evaluate(qualified(role="FIRST_PARTY"), (qualified("1250", occurrence_ids=(1,)),))
    (pair,) = result.pairs
    item = import_module("equity_os.verification.review_queue.routing").route_pair_draft(
        pair, key=REVENUE
    )
    assert item is not None
    open_item = stored(item)
    assert not trust(overlay(open_item)).trusted
    assert trust(overlay()).trusted
    elsewhere = open_item.model_copy(
        update={"key": REVENUE.model_copy(update={"canonical_id": "total_income"})}
    )
    assert trust(overlay(elsewhere)).trusted


def test_trust_refuses_an_overlay_from_another_run():
    with pytest.raises(ValueError, match="run"):
        trust(overlay(run_id=2))


def test_unmapped_occurrence_routes_low_without_an_invented_measurement_key():
    item = import_module(
        "equity_os.verification.review_queue.routing"
    ).route_unmapped_occurrence_draft(occurrence_id=42, source_ref=qualified().ref)
    assert item.key is None
    assert item.severity.value == "LOW"
    assert item.evidence_occurrence_ids == (42,)
