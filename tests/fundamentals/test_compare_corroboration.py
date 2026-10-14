"""Synthetic typed rule examples; these never qualify any real vendor or financial mapping."""

from datetime import UTC, datetime
from importlib import import_module

import pytest

from fundamentals.compare.definitions import DefinitionScope
from fundamentals.contracts.canonical import ApplicabilityStatus, Representation
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairOutcome,
    ReasonCode,
    SourceState,
)
from fundamentals.contracts.evidence_tier import EvidenceTier

from .compare_tables_support import EMPTY, POLICY, REVENUE, record, side

NOW = datetime(2026, 10, 13, tzinfo=UTC)


def qualified(
    value="1000.0",
    *,
    source="synthetic-vendor-1",
    role="INDEPENDENT_VENDOR",
    state=SourceState.VALUE,
    tier=EvidenceTier.EQUIVALENCE_DEMONSTRATED,
    reasons=(),
    occurrence_ids=(),
):
    """Constructed source identity and financial states, not source-authority evidence."""
    tables = import_module("fundamentals.compare.tables")
    contracts = import_module("fundamentals.contracts.comparison")
    ref = contracts.SourceRef(
        source_role=contracts.SourceRole(role),
        representation=Representation.XBRL if role == "FIRST_PARTY" else Representation.HTML,
        source_id=None if role == "FIRST_PARTY" else source,
        surface=None if role == "FIRST_PARTY" else "SYNTHETIC_HTML",
    )
    return tables.SourceQualifiedSide(
        ref=ref,
        side=side(
            value if state is SourceState.VALUE else None,
            state=state,
            tier=tier,
            reasons=reasons,
            entries=(f"{source}:metric",),
        ),
        occurrence_ids=occurrence_ids,
    )


def evaluate(first, vendors, applicability=ApplicabilityStatus.APPLICABLE, definitions=EMPTY):
    return import_module("fundamentals.compare.tables").corroboration_result(
        applicability=applicability,
        first_party=first,
        vendors=vendors,
        definitions=definitions,
        policy=POLICY,
    )


# State tuples are (state, literal value, tier). Expected results are literal spec rows.
V = SourceState.VALUE
N = SourceState.NO_VALUE
U = SourceState.UNAVAILABLE
INVALID = SourceState.INVALID
D = EvidenceTier.EQUIVALENCE_DEMONSTRATED
P = EvidenceTier.EQUIVALENCE_UNPROVEN


@pytest.mark.parametrize(
    ("row_id", "applicability", "first", "vendors", "expected", "reason"),
    [
        ("1", ApplicabilityStatus.NOT_APPLICABLE, V, [(V, "1000", D)], "NOT_APPLICABLE", None),
        ("2", ApplicabilityStatus.APPLICABLE, U, [(V, "1000", D)], "UNAVAILABLE", None),
        (
            "2a",
            ApplicabilityStatus.APPLICABLE,
            INVALID,
            [(V, "1000", D)],
            "NOT_COMPARABLE",
            ReasonCode.UNREADABLE_CELL,
        ),
        (
            "3",
            ApplicabilityStatus.APPLICABLE,
            N,
            [(V, "1000", D), (U, None, P), (INVALID, None, P)],
            "VENDOR_ONLY",
            None,
        ),
        (
            "4",
            ApplicabilityStatus.APPLICABLE,
            N,
            [(U, None, P), (INVALID, None, P)],
            "UNAVAILABLE",
            None,
        ),
        (
            "4a",
            ApplicabilityStatus.APPLICABLE,
            N,
            [(INVALID, None, P)],
            "NOT_COMPARABLE",
            ReasonCode.PERIOD_AMBIGUOUS,
        ),
        ("5", ApplicabilityStatus.APPLICABLE, N, [], "NO_SOURCE", None),
        ("6", ApplicabilityStatus.APPLICABLE, V, [(N, None, P), (U, None, P)], "UNAVAILABLE", None),
        ("7", ApplicabilityStatus.APPLICABLE, V, [(N, None, P)], "FILING_ONLY", None),
        (
            "8",
            ApplicabilityStatus.APPLICABLE,
            V,
            [(V, "1250", D), (V, "1000", D)],
            "CONFLICT",
            None,
        ),
        (
            "9",
            ApplicabilityStatus.APPLICABLE,
            V,
            [(V, "1000", D), (INVALID, None, P)],
            "CORROBORATED",
            None,
        ),
        (
            "10",
            ApplicabilityStatus.APPLICABLE,
            V,
            [(V, "1000", P), (INVALID, None, P)],
            "AGREES_UNQUALIFIED",
            None,
        ),
        ("11", ApplicabilityStatus.APPLICABLE, V, [(V, "1250", P)], "ANOMALY", None),
        ("12", ApplicabilityStatus.APPLICABLE, V, [(V, "1020", D)], "DEFINITION_DIFFERENCE", None),
        (
            "13",
            ApplicabilityStatus.APPLICABLE,
            V,
            [(INVALID, None, P)],
            "NOT_COMPARABLE",
            ReasonCode.PERIOD_AMBIGUOUS,
        ),
    ],
    ids=lambda value: (
        value
        if isinstance(value, str)
        and value
        in {"1", "2", "2a", "3", "4", "4a", "5", "6", "7", "8", "9", "10", "11", "12", "13"}
        else None
    ),
)
def test_all_fifteen_first_match_conditions(
    row_id, applicability, first, vendors, expected, reason
):
    fp = qualified(
        role="FIRST_PARTY",
        state=first,
        reasons=(ReasonCode.UNREADABLE_CELL,) if first is INVALID else (),
    )
    vendor_sides = tuple(
        qualified(
            value,
            source=f"synthetic-vendor-{index}",
            state=state,
            tier=tier,
            reasons=(ReasonCode.PERIOD_AMBIGUOUS,) if state is INVALID else (),
        )
        for index, (state, value, tier) in enumerate(vendors, 1)
    )
    definitions = EMPTY
    if row_id == "12":
        definitions = EMPTY.model_copy(
            update={
                "records": (
                    record(
                        "synthetic-definition",
                        DefinitionScope.MAPPING,
                        "synthetic-vendor-1:metric",
                        "20",
                    ),
                )
            }
        )
    result = evaluate(fp, vendor_sides, applicability, definitions)
    assert result.status.value == expected
    assert result.reason == reason
    assert all(pair.pair_kind.value == "CORROBORATION" for pair in result.pairs)


def test_mismatch_dominates_agreement_and_both_pairs_survive():
    result = evaluate(
        qualified(role="FIRST_PARTY"),
        (qualified("1250"), qualified("1000", source="synthetic-vendor-2")),
    )
    assert result.status is CorroborationStatus.CONFLICT
    assert [pair.result.outcome for pair in result.pairs] == [
        PairOutcome.MISMATCH,
        PairOutcome.AGREE,
    ]
    assert len({pair.right.source_id for pair in result.pairs}) == 2


def test_agreement_does_not_hide_invalid_pair_routing():
    result = evaluate(
        qualified(role="FIRST_PARTY"),
        (
            qualified(occurrence_ids=(1,)),
            qualified(
                None,
                source="synthetic-vendor-2",
                state=INVALID,
                reasons=(ReasonCode.UNREADABLE_CELL,),
                occurrence_ids=(2,),
            ),
        ),
    )
    assert result.status is CorroborationStatus.CORROBORATED
    routing = import_module("fundamentals.compare.routing")
    items = tuple(
        filter(None, (routing.route_pair_draft(pair, key=REVENUE) for pair in result.pairs))
    )
    assert len(items) == 1
    assert items[0].severity.value == "MEDIUM"
    assert items[0].reason_code is ReasonCode.UNREADABLE_CELL


def test_unavailable_vendor_remains_operational_when_another_vendor_agrees():
    unavailable = qualified(None, source="synthetic-vendor-2", state=U)
    result = evaluate(qualified(role="FIRST_PARTY"), (qualified(), unavailable))
    assert result.status is CorroborationStatus.CORROBORATED
    assert result.unavailable_sources == (unavailable.ref,)
    assert (
        import_module("fundamentals.compare.routing").route_status_draft(
            CorroborationStatus.UNAVAILABLE, key=REVENUE, evidence_occurrence_ids=(1,)
        )
        is None
    )


@pytest.mark.parametrize(
    ("extraction", "severity"),
    [
        (ExtractionStatus.DISAGREE, "HIGH"),
        (ExtractionStatus.NOT_COMPARABLE, "MEDIUM"),
        (ExtractionStatus.ONE_SIDE_XBRL, "LOW"),
        (ExtractionStatus.ONE_SIDE_PDF, "LOW"),
    ],
)
def test_extraction_routing(extraction, severity):
    item = import_module("fundamentals.compare.routing").route_status_draft(
        extraction, key=REVENUE, evidence_occurrence_ids=(1,)
    )
    assert item is not None and item.severity.value == severity


@pytest.mark.parametrize("status", [CorroborationStatus.VENDOR_ONLY, CorroborationStatus.NO_SOURCE])
def test_missing_source_routes_to_alternate_read(status):
    item = import_module("fundamentals.compare.routing").route_status_draft(
        status, key=REVENUE, evidence_occurrence_ids=(1,)
    )
    assert item is not None
    assert item.severity.value == "MEDIUM" and item.routing_reason == "ALTERNATE_READ_REQUIRED"


@pytest.mark.parametrize(
    ("value", "severity"), [("10000", "HIGH"), ("1250", "MEDIUM"), ("1000.2", None)]
)
def test_independent_anomaly_routes_by_exact_triage(value, severity):
    result = evaluate(
        qualified(role="FIRST_PARTY"), (qualified(value, tier=P, occurrence_ids=(1,)),)
    )
    (pair,) = result.pairs
    assert pair.result.outcome is PairOutcome.ANOMALY
    item = import_module("fundamentals.compare.routing").route_pair_draft(pair, key=REVENUE)
    assert (None if item is None else item.severity.value) == severity
