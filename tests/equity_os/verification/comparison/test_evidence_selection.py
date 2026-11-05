"""Package, key and interpretation selection under cutoff and mode (D1a Task 6 acceptance).

Selection decides which filed number every later phase sees, so each rule is pinned here:
both clocks, statement-family correction lineage, omitted lines, filing families, pins and
supersession, ``AS_KNOWN`` by ``recorded_at``, the opening-instant rule and the restatement
test. The integration half runs the first-party revision fixture over retained Apar
captures in both ingest orders, with every cutoff read from the store (no backdating).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from evidence_support import (
    FY25_Q2_QUARTER,
    Ingest,
    dictionary,
    ingest,
    mapping_set,
    one,
    policy,
)
from revision_support import (
    FY25_Q2_END,
    eligible_comparatives,
    ingest_fy25_q2,
    ingest_fy26_q2,
    ingest_marked,
    latest_recorded_at,
    marked_revenue_pdf,
    original_selection,
    packages,
    reverse_ingest,
    surfaced,
)
from selection_support import (
    PERIOD_END,
    TRIPLE,
    at,
    interpretation,
    key,
    member,
    occurrence,
    package,
)

from equity_os.contracts.measurement.canonical import Basis, Representation, StatementFamily
from equity_os.contracts.measurement.evidence import (
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationStatus,
    KeySelection,
    RevisionCause,
    RunMode,
)
from equity_os.contracts.measurement.measurement_key import MeasurementKey, PeriodInterval
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.verification.comparison import SelectionSource, SourceState
from equity_os.verification.comparison.selection import (
    INTERPRETATION_AMBIGUOUS,
    NO_ELIGIBLE_PACKAGE,
    NOT_EXTRACTED_UNDER_PINS,
    NOT_INTERPRETED_UNDER_PINS,
    differing_restatement,
    is_eligible,
    period_end,
    select_interpretation,
    select_key,
    select_opening_operand,
    select_package,
)

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "reverse_ingest"]

XBRL, PDF = Representation.XBRL, Representation.PDF
# Constructed clocks: PDF filed on the 29th at 08:00, XBRL at 15:00; both stored on the 30th.
PDF_MEMBER = member(PDF, 11, at(29, 8), at(30))
XBRL_MEMBER = member(XBRL, 12, at(29, 15), at(30))
ORIGINAL = package(1, XBRL_MEMBER, PDF_MEMBER)


def pick(
    packages: list[FilingPackage],
    boundary: EligibilityBoundary,
    statement_family: StatementFamily = StatementFamily.PL,
    family: FilingFamily = FilingFamily.FINANCIAL_RESULTS,
) -> FilingPackage | None:
    """Select for Apar-like entity 1, consolidated Ind AS, period end 2025-09-30."""
    return select_package(
        packages,
        entity_id=1,
        family=family,
        statement_family=statement_family,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        period_end=PERIOD_END,
        boundary=boundary,
    )


# --- eligibility --------------------------------------------------------------------------


def test_eligibility_needs_both_clocks() -> None:
    """Filed after the cutoff, or stored after it, is not yet knowable."""
    item = occurrence(1, PDF_MEMBER)
    assert is_eligible(item, EligibilityBoundary.at(at(30)))
    assert is_eligible(
        item, EligibilityBoundary(knowledge_cutoff=at(29, 8), first_seen_cutoff=at(30))
    )
    assert not is_eligible(
        item, EligibilityBoundary(knowledge_cutoff=at(29, 7), first_seen_cutoff=at(30))
    )
    assert not is_eligible(
        item, EligibilityBoundary(knowledge_cutoff=at(31), first_seen_cutoff=at(29, 23))
    )


def test_package_between_member_knowledge_times_is_not_eligible() -> None:
    """A half-visible submission never pairs: the PDF alone is knowable, the package is not."""
    boundary = EligibilityBoundary(knowledge_cutoff=at(29, 12), first_seen_cutoff=at(30))
    assert is_eligible(occurrence(1, PDF_MEMBER), boundary)
    assert not is_eligible(occurrence(2, XBRL_MEMBER), boundary)
    assert not ORIGINAL.eligible(boundary)
    assert pick([ORIGINAL], boundary) is None


# --- package selection --------------------------------------------------------------------


def test_whole_package_correction_supersedes_the_original() -> None:
    """The latest package in the family wins once it is knowable; before, the original."""
    correction = package(2, member(XBRL, 13, at(31), at(31, 1)), supersedes=1)
    assert pick([ORIGINAL, correction], EligibilityBoundary.at(at(31, 2))) == correction
    assert pick([ORIGINAL, correction], EligibilityBoundary.at(at(30, 12))) == ORIGINAL


def test_named_statement_correction_applies_only_to_its_statements() -> None:
    """A P&L-only correction is selected for P&L; balance sheet and cash flow fall through."""
    correction = package(
        2,
        member(PDF, 13, at(31), at(31, 1)),
        supersedes=1,
        replaced=frozenset({StatementFamily.PL}),
    )
    boundary = EligibilityBoundary.at(at(31, 2))
    assert pick([ORIGINAL, correction], boundary, StatementFamily.PL) == correction
    assert pick([ORIGINAL, correction], boundary, StatementFamily.BALANCE_SHEET) == ORIGINAL
    assert pick([ORIGINAL, correction], boundary, StatementFamily.CASH_FLOW) == ORIGINAL


def test_correction_omitting_a_line_gives_no_value() -> None:
    """An omitted line is absent from the selected package, never carried from the original."""
    corrected = member(XBRL, 13, at(31), at(31, 1))
    correction = package(2, corrected, supersedes=1)
    boundary = EligibilityBoundary.at(at(31, 2))
    chosen = pick([ORIGINAL, correction], boundary)
    selection = select_key(
        key(),
        XBRL,
        package=chosen,
        occurrences=[occurrence(1, XBRL_MEMBER), occurrence(2, corrected)],
        interpretations=[
            interpretation(1, XBRL_MEMBER),
            interpretation(2, corrected, measurement=key("other_income")),
        ],
        boundary=boundary,
        mode=RunMode.AS_KNOWN,
        pinned=TRIPLE,
    )
    assert (selection.state, selection.interpretation, selection.package_id) == (
        SourceState.NO_VALUE,
        None,
        2,
    )


def test_other_filing_families_never_interfere() -> None:
    """A later shareholding package leaves results keys alone, and the reverse."""
    shareholding = package(3, member(XBRL, 14, at(31), at(31, 1)), family=FilingFamily.SHAREHOLDING)
    boundary = EligibilityBoundary.at(at(31, 2))
    assert pick([ORIGINAL, shareholding], boundary) == ORIGINAL
    assert (
        pick(
            [ORIGINAL, shareholding],
            boundary,
            StatementFamily.SHAREHOLDING,
            FilingFamily.SHAREHOLDING,
        )
        == shareholding
    )


def test_no_eligible_package_is_no_value_with_reason() -> None:
    """Before anything is knowable every as-reported key is ``NO_VALUE``."""
    boundary = EligibilityBoundary.at(at(1))
    assert pick([ORIGINAL], boundary) is None
    selection = select_key(
        key(),
        XBRL,
        package=None,
        occurrences=[],
        interpretations=[],
        boundary=boundary,
        mode=RunMode.AS_KNOWN,
        pinned=TRIPLE,
    )
    assert (selection.state, selection.reason) == (SourceState.NO_VALUE, NO_ELIGIBLE_PACKAGE)


# --- interpretation selection -------------------------------------------------------------


def test_manual_correction_selected_by_mode_and_cutoff() -> None:
    """``RETROSPECTIVE`` and a later ``AS_KNOWN`` cutoff see the correction; earlier, the original
    is selected."""
    original = interpretation(1, XBRL_MEMBER, recorded_at=at(30))
    corrected = interpretation(
        2,
        XBRL_MEMBER,
        crore="101.00",
        recorded_at=at(31),
        cause=RevisionCause.MANUAL_CORRECTION,
        supersedes=1,
    )
    candidates = [original, corrected]

    def chosen(mode: RunMode, cutoff_day: int) -> object:
        _, item, _ = select_interpretation(
            candidates,
            boundary=EligibilityBoundary.at(at(cutoff_day, 12)),
            mode=mode,
            pinned=TRIPLE,
        )
        return item

    assert chosen(RunMode.RETROSPECTIVE, 30) == corrected
    assert chosen(RunMode.AS_KNOWN, 31) == corrected
    assert chosen(RunMode.AS_KNOWN, 30) == original


def test_two_unsuperseded_candidates_are_ambiguous() -> None:
    """Two current candidates are never resolved by order: ``INVALID``, no interpretation."""
    candidates = [interpretation(1, XBRL_MEMBER), interpretation(2, XBRL_MEMBER, crore="99.00")]
    assert select_interpretation(
        candidates, boundary=EligibilityBoundary.at(at(31)), mode=RunMode.AS_KNOWN, pinned=TRIPLE
    ) == (SourceState.INVALID, None, INTERPRETATION_AMBIGUOUS)


def test_two_current_readings_of_one_pdf_cell_stay_ambiguous() -> None:
    """Agreeing columns printing one instant are one reading; two current interpretations of
    the same cell are never collapsed, even when their values agree."""
    instant = key(period=PeriodInterval.at(PERIOD_END))
    cells = [
        occurrence(index, PDF_MEMBER, period=instant.period).model_copy(
            update={"anchor": {"page": 3, "line": 14, "column_index": column}}
        )
        for index, column in ((1, 0), (2, 2))
    ]
    first = interpretation(1, PDF_MEMBER, measurement=instant)
    columns = select_key(
        instant,
        PDF,
        package=ORIGINAL,
        occurrences=cells,
        interpretations=[first, interpretation(2, PDF_MEMBER, measurement=instant)],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.RETROSPECTIVE,
        pinned=TRIPLE,
    )
    assert (columns.state, columns.interpretation) == (SourceState.VALUE, first)
    twin = interpretation(2, PDF_MEMBER, measurement=instant).model_copy(
        update={"occurrence_id": 1}
    )
    same_cell = select_key(
        instant,
        PDF,
        package=ORIGINAL,
        occurrences=cells,
        interpretations=[first, twin],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.RETROSPECTIVE,
        pinned=TRIPLE,
    )
    assert (same_cell.state, same_cell.reason) == (SourceState.INVALID, INTERPRETATION_AMBIGUOUS)


def test_nil_line_is_no_value_and_invalid_line_is_invalid() -> None:
    """A mapped line without a value is ``NO_VALUE``, never zero; an invalid one ``INVALID``."""
    boundary = EligibilityBoundary.at(at(31))
    nil = interpretation(1, XBRL_MEMBER, crore=None)
    assert select_interpretation(
        [nil], boundary=boundary, mode=RunMode.AS_KNOWN, pinned=TRIPLE
    ) == (SourceState.NO_VALUE, nil, None)
    bad = interpretation(2, XBRL_MEMBER, crore=None, status=InterpretationStatus.INVALID)
    state, item, _ = select_interpretation(
        [bad], boundary=boundary, mode=RunMode.AS_KNOWN, pinned=TRIPLE
    )
    assert (state, item) == (SourceState.INVALID, bad)


def _select(interpretations: list, mode: RunMode, cutoff_day: int) -> KeySelection:  # type: ignore[type-arg]
    """Select the revenue key from the original package's XBRL member."""
    return select_key(
        key(),
        XBRL,
        package=ORIGINAL,
        occurrences=[occurrence(1, XBRL_MEMBER)],
        interpretations=interpretations,
        boundary=EligibilityBoundary.at(at(cutoff_day, 12)),
        mode=mode,
        pinned=TRIPLE,
    )


def test_unpinned_mapping_versions_are_ignored() -> None:
    """Only the pinned triple's rows are candidates; an interpreted capture lacking the line
    is ``NO_VALUE`` and a capture interpreted only under another triple is ``UNAVAILABLE``."""
    pinned = interpretation(1, XBRL_MEMBER, measurement=key("other_income"))
    other = interpretation(2, XBRL_MEMBER, mapping_set="v0")
    lacking = _select([pinned, other], RunMode.RETROSPECTIVE, 31)
    assert (lacking.state, lacking.reason) == (SourceState.NO_VALUE, None)
    assert lacking.considered_interpretation_ids == (2,)
    only_other = _select([other], RunMode.RETROSPECTIVE, 31)
    assert (only_other.state, only_other.reason) == (
        SourceState.UNAVAILABLE,
        NOT_INTERPRETED_UNDER_PINS,
    )


def test_pinned_triple_recorded_after_cutoff_is_unavailable_as_known() -> None:
    """``AS_KNOWN`` before the pinned rows were recorded is ``UNAVAILABLE``; ``RETROSPECTIVE``
    selects them."""
    old = interpretation(1, XBRL_MEMBER, mapping_set="v0", recorded_at=at(30))
    new = interpretation(2, XBRL_MEMBER, recorded_at=at(31))
    early = _select([old, new], RunMode.AS_KNOWN, 30)
    assert (early.state, early.reason) == (SourceState.UNAVAILABLE, NOT_INTERPRETED_UNDER_PINS)
    late = _select([old, new], RunMode.RETROSPECTIVE, 30)
    assert (late.state, late.interpretation) == (SourceState.VALUE, new)


def test_capture_without_pinned_extractor_generation_is_unavailable() -> None:
    """No occurrence under the pinned extractor: the capture was never read under the pins."""
    selection = select_key(
        key(),
        XBRL,
        package=ORIGINAL,
        occurrences=[occurrence(1, XBRL_MEMBER, extractor="x0")],
        interpretations=[interpretation(1, XBRL_MEMBER, extractor="x0")],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.RETROSPECTIVE,
        pinned=TRIPLE,
    )
    assert (selection.state, selection.reason) == (
        SourceState.UNAVAILABLE,
        NOT_EXTRACTED_UNDER_PINS,
    )


def test_absent_member_gives_no_value_for_that_representation() -> None:
    """An XBRL-only package has no PDF value (never borrowed from XBRL)."""
    xbrl_only = package(5, XBRL_MEMBER)
    selection = select_key(
        key(),
        PDF,
        package=xbrl_only,
        occurrences=[occurrence(1, XBRL_MEMBER)],
        interpretations=[interpretation(1, XBRL_MEMBER)],
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.AS_KNOWN,
        pinned=TRIPLE,
    )
    assert (selection.state, selection.interpretation, selection.package_id) == (
        SourceState.NO_VALUE,
        None,
        5,
    )


# --- opening operand and restatements -----------------------------------------------------

OPENING = PeriodInterval.at(date(2025, 3, 31))


def _opening(interpretations: list, fallback: KeySelection) -> KeySelection:  # type: ignore[type-arg]
    """The opening cash operand of the original package's XBRL member."""
    return select_opening_operand(
        key("cf_cash_closing", OPENING),
        XBRL,
        output_package=ORIGINAL,
        package_occurrences=[occurrence(1, XBRL_MEMBER, period=OPENING)],
        package_interpretations=interpretations,
        boundary=EligibilityBoundary.at(at(31)),
        mode=RunMode.AS_KNOWN,
        pinned=TRIPLE,
        fallback=lambda: fallback,
    )


def test_opening_operand_prefers_the_package_disclosure() -> None:
    """The package's own opening balance wins, recorded as its opening disclosure."""
    historical = KeySelection(
        key=key("cf_cash_closing", OPENING),
        representation=XBRL,
        state=SourceState.VALUE,
        interpretation=interpretation(9, XBRL_MEMBER, measurement=key("cf_cash_closing", OPENING)),
        package_id=9,
        source=SelectionSource.HISTORICAL_PACKAGE,
        reason=None,
        considered_interpretation_ids=(),
        surfaced_restatements=(),
    )
    disclosed = interpretation(1, XBRL_MEMBER, measurement=key("cf_cash_closing", OPENING))
    own = _opening([disclosed], historical)
    assert (own.source, own.interpretation, own.package_id) == (
        SelectionSource.PACKAGE_OPENING_DISCLOSURE,
        disclosed,
        1,
    )
    other_line = interpretation(1, XBRL_MEMBER, measurement=key("other_income"))
    assert _opening([other_line], historical) == historical
    nil = interpretation(1, XBRL_MEMBER, measurement=key("cf_cash_closing", OPENING), crore=None)
    kept = _opening([nil], historical)
    assert (kept.state, kept.source) == (
        SourceState.NO_VALUE,
        SelectionSource.PACKAGE_OPENING_DISCLOSURE,
    )


def test_differing_restatement_names_only_disjoint_comparatives() -> None:
    """A comparative whose interval misses the selection is a restatement; an overlap is not."""
    original = interpretation(1, XBRL_MEMBER)
    selected = _select([original], RunMode.AS_KNOWN, 31)
    assert selected.interpretation == original
    later = member(PDF, 21, at(31), at(31, 1))
    same = interpretation(2, later, crore="100.004")  # [99.999, 100.009] meets [99.995, 100.005]
    moved = interpretation(3, later, crore="100.02")
    elsewhere = interpretation(4, later, crore="200.00", measurement=key("other_income"))
    assert differing_restatement(selected, [same, moved, elsewhere]) == (3,)


# --- integration: the first-party revision fixture (pg, retained) ------------------------

PRE_CAPTURE = datetime(2025, 10, 15, tzinfo=UTC)


def _revenue_key(ingest: Ingest) -> MeasurementKey:
    """The Q2 FY25 consolidated revenue key, as the FY25 Q2 original keyed it."""
    (original,) = packages(ingest, FY25_Q2_END)
    capture_ref_id = original.members[XBRL].capture.capture_ref_id
    assert capture_ref_id is not None
    rows = list(ingest.repository.list_capture_interpretations(capture_ref_id))
    found = one(rows, "revenue_from_operations", FY25_Q2_QUARTER, XBRL).key
    assert found is not None
    return found


def _comparatives(ingest: Ingest, package_id: int | None) -> list[Interpretation]:
    """Mapped, valued rows of a package whose period does not end on its period end."""
    assert package_id is not None
    (stored,) = ingest.repository.get_packages([package_id])
    rows: list[Interpretation] = []
    for representation in stored.members:
        capture_ref_id = stored.members[representation].capture.capture_ref_id
        assert capture_ref_id is not None
        rows += ingest.repository.list_capture_interpretations(capture_ref_id)
    return [
        row
        for row in rows
        if row.key is not None
        and row.value is not None
        and period_end(row.key.period) != stored.reporting_period_end
    ]


@pytest.mark.pg
@pytest.mark.retained
def test_revision_fixture_in_both_ingest_orders(ingest: Ingest, reverse_ingest: Ingest) -> None:
    """Comparatives get honest causes at ingest and surface identically in either order.

    The stored cause depends on what was stored first; the surfaced set at run time never
    does, because it is recomputed from the eligible inputs.
    """
    marked = marked_revenue_pdf(ingest.tmp_path)
    # 1–2. The original, and a pre-capture cutoff at which nothing is eligible.
    fy25 = ingest_fy25_q2(ingest)
    (original,) = packages(ingest, FY25_Q2_END)
    first_seen = original.members[XBRL].capture.first_seen_at
    revenue = _revenue_key(ingest)
    assert not original.eligible(EligibilityBoundary.at(PRE_CAPTURE))
    early = original_selection(
        ingest, revenue, EligibilityBoundary.at(PRE_CAPTURE), RunMode.AS_KNOWN
    )
    assert (early.state, early.reason) == (SourceState.NO_VALUE, NO_ELIGIBLE_PACKAGE)
    # 3. FY26 Q2 registers strictly later.
    fy26 = ingest_fy26_q2(ingest)
    fy26_package = ingest.package(fy26)
    assert all(m.capture.first_seen_at > first_seen for m in fy26_package.members.values())
    # 4. At R1 only the original is eligible and no comparative surfaces.
    r1 = latest_recorded_at(ingest.interpretations(fy25))
    assert r1.first_seen_cutoff >= first_seen
    selected = {}
    for boundary, mode in (
        (r1, RunMode.AS_KNOWN),
        (EligibilityBoundary.at(first_seen), RunMode.RETROSPECTIVE),
    ):
        selection = original_selection(ingest, revenue, boundary, mode)
        assert selection.state is SourceState.VALUE and selection.package_id == fy25.package_id
        assert eligible_comparatives(ingest, revenue, boundary, mode) == []
        selected[mode] = selection.interpretation
    # 5. At R2 the FY26 Q2 PDF comparatives are eligible; the selection is unchanged.
    r2 = latest_recorded_at(ingest.interpretations(fy26))
    at_r2 = original_selection(ingest, revenue, r2, RunMode.AS_KNOWN)
    assert at_r2.interpretation == selected[RunMode.AS_KNOWN]
    comparatives = eligible_comparatives(ingest, revenue, r2, RunMode.AS_KNOWN)
    assert {row.representation for row in comparatives} == {PDF}
    # The real comparatives: COMPARATIVE_RESTATEMENT exactly when they differ from the original.
    real = _comparatives(ingest, fy26.package_id)
    differing = []
    for row in real:
        assert row.key is not None
        if period_end(row.key.period) != FY25_Q2_END:
            assert row.revision_cause is RevisionCause.ORIGINAL  # no original stored
            continue
        named = differing_restatement(
            original_selection(ingest, row.key, r2, RunMode.RETROSPECTIVE), [row]
        )
        expected = RevisionCause.COMPARATIVE_RESTATEMENT if named else RevisionCause.ORIGINAL
        assert row.revision_cause is expected, row.canonical_id
        differing += [row.canonical_id] if named else []
    print(f"real Q2 FY25 comparatives differing from the original: {sorted(differing)}")
    # 6. The marked copy's revenue comparative differs: stored as a restatement, surfaced.
    marked_report = ingest_marked(ingest, marked)
    (marked_revenue,) = [
        row for row in _comparatives(ingest, marked_report.package_id) if row.key == revenue
    ]
    assert marked_revenue.revision_cause is RevisionCause.COMPARATIVE_RESTATEMENT
    r3 = latest_recorded_at(ingest.interpretations(marked_report))
    at_r3 = original_selection(ingest, revenue, r3, RunMode.AS_KNOWN)
    assert at_r3.interpretation == selected[RunMode.AS_KNOWN]
    assert marked_revenue.interpretation_id in differing_restatement(
        at_r3, eligible_comparatives(ingest, revenue, r3, RunMode.AS_KNOWN)
    )
    counts = ingest.table_counts()
    again = ingest_marked(ingest, marked)
    assert ingest.table_counts() == counts
    (same,) = [row for row in _comparatives(ingest, again.package_id) if row.key == revenue]
    assert same == marked_revenue
    forward = surfaced(ingest, latest_recorded_at(ingest.interpretations(again)))
    # 7. Reverse order in a fresh database: every comparative is ORIGINAL, surfacing is equal.
    reverse = reverse_ingest
    reverse_fy26 = ingest_fy26_q2(reverse)
    reverse_marked = ingest_marked(reverse, marked)
    reverse_fy25 = ingest_fy25_q2(reverse)
    for report in (reverse_fy26, reverse_marked):
        assert {row.revision_cause for row in _comparatives(reverse, report.package_id)} == {
            RevisionCause.ORIGINAL
        }
    reverse_again = ingest_marked(reverse, marked)
    (kept,) = [
        row for row in _comparatives(reverse, reverse_again.package_id) if row.key == revenue
    ]
    assert kept.revision_cause is RevisionCause.ORIGINAL
    final = latest_recorded_at(
        [*reverse.interpretations(reverse_fy25), *reverse.interpretations(reverse_again)]
    )
    backward = surfaced(reverse, final)
    assert forward == backward
    assert len(forward) >= 1
