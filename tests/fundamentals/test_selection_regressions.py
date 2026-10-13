"""Selection regressions: corrections cannot leave a stale canonical number visible."""

from selection_support import TRIPLE, at, interpretation, key, member, occurrence, package

from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import (
    EligibilityBoundary,
    FilingFamily,
    InterpretationReason,
    InterpretationStatus,
    KnowledgeTimeStatus,
    RevisionCause,
    RunMode,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.selection import select_key, select_package


def test_correction_to_another_key_removes_the_old_key_under_current_pins() -> None:
    owner = member(Representation.XBRL, 1, at(29), at(30))
    old = interpretation(1, owner)
    corrected = interpretation(
        2,
        owner,
        measurement=key("other_income"),
        supersedes=1,
        cause=RevisionCause.MANUAL_CORRECTION,
        recorded_at=at(31),
    )
    for mode, cutoff, expected in (
        (RunMode.AS_KNOWN, at(30), SourceState.VALUE),
        (RunMode.AS_KNOWN, at(31), SourceState.NO_VALUE),
        (RunMode.RETROSPECTIVE, at(30), SourceState.NO_VALUE),
    ):
        selected = select_key(
            key(),
            Representation.XBRL,
            package=package(1, owner),
            occurrences=[occurrence(1, owner)],
            interpretations=[old, corrected],
            boundary=EligibilityBoundary.at(cutoff),
            mode=mode,
            pinned=TRIPLE,
        )
        assert selected.state is expected
        if expected is SourceState.NO_VALUE:
            assert selected.interpretation is None
            assert selected.considered_interpretation_ids == (1,)


def test_package_with_unknown_member_publication_is_not_selected() -> None:
    owner = member(Representation.XBRL, 1, at(29), at(30)).model_copy(
        update={"knowledge_time_status": KnowledgeTimeStatus.UNKNOWN}
    )
    candidate = package(1, owner)
    assert (
        select_package(
            [candidate],
            entity_id=1,
            family=FilingFamily.FINANCIAL_RESULTS,
            statement_family=StatementFamily.PL,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            period_end=candidate.reporting_period_end,
            boundary=EligibilityBoundary.at(at(31)),
        )
        is None
    )


def test_invalid_partial_key_is_invalid_only_for_its_evidenced_measurement() -> None:
    owner = member(Representation.XBRL, 1, at(29), at(30))
    invalid = interpretation(1, owner, crore=None).model_copy(
        update={
            "status": InterpretationStatus.INVALID,
            "key": None,
            "reason": InterpretationReason.UNIT_MISMATCH,
        }
    )
    for measurement, state in (
        (key(), SourceState.INVALID),
        (key("other_income"), SourceState.NO_VALUE),
        (key().model_copy(update={"basis": Basis.STANDALONE}), SourceState.NO_VALUE),
    ):
        selected = select_key(
            measurement,
            Representation.XBRL,
            package=package(1, owner),
            occurrences=[occurrence(1, owner)],
            interpretations=[invalid],
            boundary=EligibilityBoundary.at(at(31)),
            mode=RunMode.AS_KNOWN,
            pinned=TRIPLE,
        )
        assert selected.state is state
        if state is SourceState.INVALID:
            assert selected.interpretation == invalid
            assert selected.reason == "UNIT_MISMATCH"
