"""Queue routing evidence: what a draft names decides whether a changed input reopens an item.

Constructed rows and interpretations (``selection_support``); nothing here is a filed value.
"""

from __future__ import annotations

from decimal import Decimal

from selection_support import TRIPLE, at, interpretation, key, member, occurrence

from equity_os.contracts.measurement.canonical import (
    ApplicabilityStatus,
    Representation,
    ValueIdentity,
)
from equity_os.contracts.measurement.evidence import (
    InterpretationStatus,
    PinnedVersions,
    VersionPin,
)
from equity_os.contracts.verification.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    PairOutcome,
    SourceRef,
    SourceRole,
    SourceState,
)
from equity_os.verification.comparison.resolve_models import ResolvedInputs
from equity_os.verification.comparison.run_models import (
    PairRecord,
    ResultRow,
    RunInput,
    RunInputDisposition,
    RunInputKind,
    SourceValue,
)
from equity_os.verification.comparison.selection import INTERPRETATION_AMBIGUOUS
from equity_os.verification.review_queue.routing import route_run

XBRL = Representation.XBRL
OWNER = member(XBRL, 11, at(29), at(30))
PINS = PinnedVersions.model_validate(
    {
        name: VersionPin(version="fixture", content_sha256="0" * 64)
        for name in PinnedVersions.model_fields
        if name != "vendor_extractors"
    }
    | {
        "mapping_set": VersionPin(version=TRIPLE.mapping_set, content_sha256="0" * 64),
        "normalisation_policy": VersionPin(
            version=TRIPLE.normalisation_policy, content_sha256="0" * 64
        ),
        "extractor_xbrl": VersionPin(version=TRIPLE.extractor_xbrl, content_sha256="0" * 64),
    }
)
INPUTS = ResolvedInputs(
    definition_set_id=1,
    occurrences=(occurrence(1, OWNER), occurrence(2, OWNER)),
    capture_refs=(OWNER.capture,),
    inputs=(
        RunInput(
            kind=RunInputKind.CAPTURE_REF, ref_id=11, disposition=RunInputDisposition.SELECTED
        ),
    ),
)


def _value(role: SourceRole, state: SourceState, **fields: object) -> SourceValue:
    return SourceValue.model_validate(
        {
            "source_role": role,
            "representation": XBRL,
            "state": state,
            "reason": None,
            "value": None,
            "lower": None,
            "upper": None,
            "interpretation_id": None,
            "calculation_trace_id": None,
            "attempt_id": 3,
            "calculation_state": None,
        }
        | fields
    )


def _derived(value: str, trace_id: int) -> ResultRow:
    """A derived row whose computed side disagrees with the reported counterpart (101)."""
    derived = _value(SourceRole.FIRST_PARTY, SourceState.VALUE, value=Decimal(value))
    derived = derived.model_copy(update={"calculation_trace_id": trace_id, "attempt_id": None})
    reported = _value(SourceRole.REPORTED_COUNTERPART, SourceState.VALUE, value=Decimal(101))
    pair = PairRecord(
        pair_kind=PairKind.REPORTED_VS_DERIVED,
        left=SourceRef(source_role=SourceRole.FIRST_PARTY, representation=XBRL),
        right=SourceRef(source_role=SourceRole.REPORTED_COUNTERPART, representation=XBRL),
        outcome=PairOutcome.MISMATCH,
        reason=None,
        triage=None,
        difference=None,
        interval_gap=None,
        definition_record_id=None,
    )
    return _row((derived, reported), (pair,), ValueIdentity.DERIVED)


def _row(
    values: tuple[SourceValue, ...],
    pairs: tuple[PairRecord, ...] = (),
    identity: ValueIdentity = ValueIdentity.REPORTED,
) -> ResultRow:
    return ResultRow(
        row_id=f"row-{identity.value}",
        key=key(),
        dictionary_version="v1",
        value_identity=identity,
        applicability=ApplicabilityStatus.APPLICABLE,
        applicability_rule_id="",
        extraction_status=ExtractionStatus.NONE,
        extraction_reason=None,
        corroboration_status=CorroborationStatus.FILING_ONLY,
        corroboration_reason=None,
        source_values=values,
        pairs=pairs,
        surfaced_restatements=(),
    )


def test_a_corrected_derived_dispute_with_the_same_attempts_is_a_new_input() -> None:
    """Derived 100 vs 101, then corrected 200 vs 101: the traces differ, so the drafts do."""
    (before,) = [
        d for d in route_run(INPUTS, [_derived("100", 7)], PINS) if d.outcome == "MISMATCH"
    ]
    (after,) = [d for d in route_run(INPUTS, [_derived("200", 8)], PINS) if d.outcome == "MISMATCH"]
    assert (before.calculation_trace_ids, after.calculation_trace_ids) == ((7,), (8,))
    assert before.attempt_ids == after.attempt_ids and before != after


def test_an_ambiguous_side_names_every_candidate() -> None:
    """An ambiguous selection has no interpretation: its candidates are its evidence."""
    candidates = (interpretation(1, OWNER), interpretation(2, OWNER, crore="99.00"))
    inputs = INPUTS.model_copy(update={"interpretations": candidates})
    ambiguous = _value(SourceRole.FIRST_PARTY, SourceState.INVALID, reason=INTERPRETATION_AMBIGUOUS)
    row = _row((ambiguous,)).model_copy(
        update={"extraction_status": ExtractionStatus.NOT_COMPARABLE}
    )
    drafts = route_run(inputs, [row], PINS)
    assert drafts and all(
        draft.evidence_interpretation_ids == (1, 2) for draft in drafts if draft.key
    )


def test_a_superseded_unmapped_line_is_not_queued() -> None:
    """An UNMAPPED reading a later interpretation of the same occurrence supersedes is history."""
    unmapped = interpretation(1, OWNER, status=InterpretationStatus.UNMAPPED, measurement=None)
    unmapped = unmapped.model_copy(update={"key": None, "canonical_id": None, "value": None})
    mapped = interpretation(2, OWNER, supersedes=1).model_copy(update={"occurrence_id": 1})
    current = INPUTS.model_copy(update={"interpretations": (unmapped,)})
    superseded = INPUTS.model_copy(update={"interpretations": (unmapped, mapped)})
    assert [d.outcome for d in route_run(current, [], PINS)] == ["UNMAPPED"]
    assert route_run(superseded, [], PINS) == ()
