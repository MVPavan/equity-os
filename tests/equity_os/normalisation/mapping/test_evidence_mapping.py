"""Mapping-set loading, matching, constructions and qualification (D1a Task 5).

Loader refusals need neither a database nor retained files; matching and constructions
run over retained Apar and marked copies through ingestion.
"""

from __future__ import annotations

import decimal
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from evidence_support import (
    CAPMKT,
    EPS_DISCONTINUED_FOURD,
    EPS_DISCONTINUED_ONED,
    Q2_HALF,
    Q2_QUARTER,
    XBRL_ONLY,
    Ingest,
    by_occurrence,
    constructed,
    demonstrate_eps,
    dictionary,
    entry_of,
    ingest,
    mapping_set,
    marked_xbrl,
    one,
    pdf_context,
    policy,
    replace_entry,
    rows_of,
    temp_mapping,
)
from retained_support import MarkedEdit

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, Representation
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationReason,
    InterpretationStatus,
    Occurrence,
    exact_decimal,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.qualification import QualificationContext
from equity_os.normalisation.dictionary.dictionary import CanonicalDictionary
from equity_os.normalisation.mapping.interpret import interpret, prove_conditions
from equity_os.normalisation.mapping.mapping import (
    CONTEXT_LOCAL_NAME,
    CONTEXT_NAMESPACE,
    MappingDefect,
    MappingLoadError,
    MappingSet,
)

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

PBT_ONED = (
    b'<in-capmkt:ProfitBeforeTax contextRef="OneD" decimals="-5" unitRef="INR">3405600000'
    b"</in-capmkt:ProfitBeforeTax>"
)
ASSOCIATES_ONED = (
    b"<in-capmkt:ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod "
    b'contextRef="OneD" decimals="-5" unitRef="INR">-300000<'
)
FOREIGN_NAMESPACE = "http://example.com/xbrl/not-a-sebi-taxonomy"
INCL_ASSOCIATES_RULE = "capmkt.profit_before_tax_incl_associates"
PDF_LAYOUTS = "pdf/v1/results_layout.yaml"
CONSTRUCTIONS = "constructions/v1.yaml"


def _expect_refusal(
    tmp_path: Path,
    dictionary: CanonicalDictionary,
    edit: Callable[[dict[str, Any]], None],
    defect: MappingDefect,
    member: str = "xbrl/v1/in_capmkt.yaml",
) -> None:
    """Loading the edited copy fails with exactly this defect."""
    with pytest.raises(MappingLoadError) as raised:
        temp_mapping(tmp_path, dictionary, edit, member=member)
    assert raised.value.defect is defect


def _twin(entry_id: str, twin_id: str, **changes: Any) -> Callable[[dict[str, Any]], None]:
    """Edit: append a copy of one entry under another id with some fields changed."""

    def edit(data: dict[str, Any]) -> None:
        data["entries"].append({**entry_of(data, entry_id), "entry_id": twin_id, **changes})

    return edit


def _xbrl_context(kind: PeriodKind) -> QualificationContext:
    """An XBRL qualification context with no proofs."""
    return QualificationContext(
        schema_identity=CAPMKT,
        surface="NSE_XBRL_INSTANCE",
        basis=Basis.CONSOLIDATED,
        period_kind=kind,
        proven={},
    )


def _interpret(
    ingest: Ingest,
    occurrence: Occurrence,
    qualification: QualificationContext,
    mapping_set: MappingSet | None = None,
) -> Interpretation:
    """Interpret one stored occurrence under the v1 pins (or another mapping set)."""
    return interpret(
        occurrence,
        entity_id=ingest.entity_id,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        mapping_set=mapping_set or ingest.mapping_set,
        policy=ingest.policy,
        dictionary=ingest.dictionary,
        fiscal_year_end_month=3,
        qualification=qualification,
        recorded_at=datetime.now(UTC),
    )


# --- loader refusals (no database, no retained files) -------------------------------------


def test_duplicate_selector_is_refused(tmp_path: Path, dictionary: CanonicalDictionary) -> None:
    """Two entries matching the same native field and context predicate cannot both load."""
    edit = _twin("capmkt.eps_basic", "capmkt.eps_basic_twin", canonical_id="eps_diluted")
    _expect_refusal(tmp_path, dictionary, edit, MappingDefect.DUPLICATE_SELECTOR)


def test_template_emitting_one_measurement_twice_is_refused(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    """Two segment templates resolving to the same canonical measurement cannot both load."""

    def edit(data: dict[str, Any]) -> None:
        twin = entry_of(data, "capmkt.segment_revenue")
        selector = {**twin["selector"], "native_field": "SegmentRevenueRestated"}
        data["entries"].append(
            {**twin, "entry_id": "capmkt.segment_revenue_twin", "selector": selector}
        )

    _expect_refusal(tmp_path, dictionary, edit, MappingDefect.DUPLICATE_SELECTOR)


def test_unknown_canonical_id_is_refused(tmp_path: Path, dictionary: CanonicalDictionary) -> None:
    """An entry naming no dictionary row is DANGLING_CANONICAL_ID."""

    def edit(data: dict[str, Any]) -> None:
        entry = entry_of(data, "capmkt.eps_basic")
        replace_entry(data, "capmkt.eps_basic", {**entry, "canonical_id": "no_such_measure"})

    _expect_refusal(tmp_path, dictionary, edit, MappingDefect.DANGLING_CANONICAL_ID)


def test_same_native_name_under_two_schemas_loads(mapping_set: MappingSet) -> None:
    """``in-capmkt`` and ``in-bse-fin`` may each map the same element name."""
    field = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
    schemas = {
        entry.schema_identity
        for entry in mapping_set.entries
        if entry.selector.native_field == field
    }
    assert len(schemas) == 2


def test_source_specific_and_generic_overlap_is_refused(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    """A source-specific entry or construction overlapping a source-generic one is refused:
    which applies is never decided by file order.
    """
    entry = _twin(
        "capmkt.current_tax", "capmkt.current_tax_nse", source="nse-indas-xbrl-consolidated"
    )
    _expect_refusal(tmp_path, dictionary, entry, MappingDefect.DUPLICATE_SELECTOR)

    def rule(data: dict[str, Any]) -> None:
        (tax,) = [item for item in data["constructions"] if item["rule_id"] == "pdf.tax_expense"]
        data["constructions"].append(
            {**tax, "rule_id": "pdf.tax_expense_issuer", "source": "aparinds-fy26-q2-results-pdf"}
        )

    _expect_refusal(tmp_path, dictionary, rule, MappingDefect.DUPLICATE_SELECTOR, CONSTRUCTIONS)


def test_overlapping_pdf_selectors_are_refused(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    """An unrestricted "(a) Current tax" entry overlaps the section-restricted one: both
    would match the printed line, so the set is refused whatever their canonical ids.
    """

    def edit(data: dict[str, Any]) -> None:
        current = entry_of(data, "pdf.current_tax")
        selector = {key: value for key, value in current["selector"].items() if key != "section"}
        data["entries"].append(
            {
                **current,
                "entry_id": "pdf.current_tax_unrestricted",
                "selector": selector,
                "canonical_id": "tax_discontinued",
            }
        )

    _expect_refusal(tmp_path, dictionary, edit, MappingDefect.DUPLICATE_SELECTOR, PDF_LAYOUTS)


def test_two_distinct_contains_sections_are_refused(
    tmp_path: Path, dictionary: CanonicalDictionary
) -> None:
    """The same Tax exp context can satisfy Tax and exp simultaneously."""

    def edit(data: dict[str, Any]) -> None:
        current = entry_of(data, "pdf.current_tax")
        replace_entry(
            data,
            "pdf.current_tax",
            {
                **current,
                "selector": {
                    **current["selector"],
                    "section": "Tax",
                },
            },
        )
        data["entries"].append(
            {
                **current,
                "entry_id": "pdf.tax_twin",
                "canonical_id": "tax_discontinued",
                "selector": {**current["selector"], "section": "exp"},
            }
        )

    _expect_refusal(tmp_path, dictionary, edit, MappingDefect.DUPLICATE_SELECTOR, PDF_LAYOUTS)


def test_exact_decimal_ignores_ambient_precision() -> None:
    """Rationals convert exactly even when the ambient Decimal context keeps six digits."""
    with decimal.localcontext(prec=6):
        assert exact_decimal(Fraction(3405600001, 10)) == Decimal("340560000.1")
        long = Fraction(123456789012345678901234567891, 10)
        assert exact_decimal(long) == Decimal("12345678901234567890123456789.1")
        assert exact_decimal(Fraction(-3, 8)) == Decimal("-0.375")
    with pytest.raises(ValueError):
        exact_decimal(Fraction(1, 3))


# --- matching over retained Apar ----------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_interpretation_ignores_ambient_precision(ingest: Ingest) -> None:
    """A filed value with more digits than the ambient precision is interpreted exactly."""
    report = ingest.run(ingest.intake(XBRL_ONLY))
    pbt = one(ingest.interpretations(report), "profit_before_tax", Q2_QUARTER, Representation.XBRL)
    assert pbt.occurrence_id is not None
    occurrence = ingest.occurrences(report)[pbt.occurrence_id]
    for raw in ("3405600001", "123456789012345678901234567891"):
        filed = occurrence.model_copy(update={"raw_value_text": raw})
        with decimal.localcontext(prec=6):
            row = _interpret(ingest, filed, _xbrl_context(PeriodKind.QUARTER))
        assert row.value == Decimal(raw)


@pytest.mark.pg
@pytest.mark.retained
def test_foreign_namespace_element_is_unmapped(ingest: Ingest) -> None:
    """``ProfitBeforeTax`` in a namespace outside the SEBI taxonomy never maps to PBT."""
    foreign = (
        f'<other:ProfitBeforeTax xmlns:other="{FOREIGN_NAMESPACE}" contextRef="OneD" '
        f'decimals="-5" unitRef="INR">9990000000</other:ProfitBeforeTax>'
    ).encode()
    edit = MarkedEdit(label="foreign-pbt", find=PBT_ONED, replace=PBT_ONED + foreign)
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    rows = ingest.interpretations(report)
    assert one(rows, "profit_before_tax", Q2_QUARTER, Representation.XBRL).value == Decimal(
        "3405600000"
    )
    direct = by_occurrence(rows)
    foreign_occurrences = [
        item
        for item in ingest.occurrences(report).values()
        if item.native_context.get(CONTEXT_NAMESPACE) == FOREIGN_NAMESPACE
    ]
    assert foreign_occurrences
    for item in foreign_occurrences:
        assert item.native_context[CONTEXT_LOCAL_NAME] == "ProfitBeforeTax"
        assert item.occurrence_id is not None
        assert direct[item.occurrence_id].status is InterpretationStatus.UNMAPPED
    assert not [row for row in rows if row.value == Decimal("9990000000")]


@pytest.mark.pg
@pytest.mark.retained
def test_entry_for_another_source_does_not_match(
    ingest: Ingest, dictionary: CanonicalDictionary
) -> None:
    """An entry naming another source never maps this source's facts: CurrentTax is UNMAPPED."""

    def other_source(data: dict[str, Any]) -> None:
        entry = entry_of(data, "capmkt.current_tax")
        replace_entry(data, "capmkt.current_tax", {**entry, "source": "bse-xbrl"})

    scoped = temp_mapping(ingest.tmp_path, dictionary, other_source, version="v1-test-bse-only")
    report = ingest.run(ingest.intake(XBRL_ONLY), mapping_set=scoped)
    rows = ingest.interpretations(report)
    assert not rows_of(rows, "current_tax", Q2_QUARTER, Representation.XBRL)
    direct = by_occurrence(rows)
    current_tax = [
        item
        for item in ingest.occurrences(report).values()
        if item.native_context[CONTEXT_LOCAL_NAME] == "CurrentTax"
    ]
    assert current_tax
    for item in current_tax:
        assert item.occurrence_id is not None
        assert direct[item.occurrence_id].status is InterpretationStatus.UNMAPPED


@pytest.mark.pg
@pytest.mark.retained
def test_two_matching_entries_are_ambiguous_at_runtime(ingest: Ingest) -> None:
    """Should two entries still match one line, the line is INVALID and ambiguous — never
    mapped by whichever entry comes first.
    """
    report = ingest.run(ingest.intake({Representation.PDF: "results"}))
    current = ingest.mapping_set.entry("pdf.current_tax")
    unrestricted = current.model_copy(
        update={
            "entry_id": "pdf.current_tax_unrestricted",
            "canonical_id": "tax_discontinued",
            "selector": current.selector.model_copy(update={"section": None}),
        }
    )
    both = ingest.mapping_set.model_copy(
        update={"entries": (*ingest.mapping_set.entries, unrestricted)}
    )
    (cell,) = [
        item
        for item in ingest.occurrences(report).values()
        if item.native_field == "(a) Current tax" and item.raw_value_text == "89.13"
    ]
    row = _interpret(ingest, cell, pdf_context(PeriodKind.QUARTER), both)
    assert row.status is InterpretationStatus.INVALID
    assert row.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS
    assert row.canonical_id is None and row.mapping_entry_id is None and row.value is None
    assert set(row.transform_trace["matched_entry_ids"]) == {  # type: ignore[arg-type]
        "pdf.current_tax",
        "pdf.current_tax_unrestricted",
    }


# --- constructions over marked copies -----------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_invalid_operand_makes_the_construction_invalid(ingest: Ingest) -> None:
    """Associates filed per share cannot be added to PBT: the operand is INVALID and so is
    the construction (invalid beats missing) — it is not reported as not presented.
    """
    edit = MarkedEdit(
        label="associates-per-share",
        find=ASSOCIATES_ONED,
        replace=ASSOCIATES_ONED.replace(b'unitRef="INR"', b'unitRef="INRPerShare"'),
    )
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    rows = ingest.interpretations(report)
    (associates,) = [
        row
        for row in rows
        if row.mapping_entry_id == "capmkt.share_of_profit_associates_jv"
        and row.period == Q2_QUARTER
    ]
    assert associates.status is InterpretationStatus.INVALID and associates.key is None
    incl = constructed(rows, INCL_ASSOCIATES_RULE, Q2_QUARTER)
    assert incl.status is InterpretationStatus.INVALID and incl.value is None
    assert associates.interpretation_id in incl.operand_interpretation_ids


@pytest.mark.pg
@pytest.mark.retained
def test_duplicate_operand_makes_the_construction_ambiguous(ingest: Ingest) -> None:
    """Two Q2 PBT facts leave the construction INVALID and ambiguous, naming both, never
    built from one of them.
    """
    duplicated = PBT_ONED.replace(b">3405600000<", b">3405700000<")
    edit = MarkedEdit(label="two-pbt-facts", find=PBT_ONED, replace=PBT_ONED + duplicated)
    report = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, edit)})
    )
    rows = ingest.interpretations(report)
    pbts = rows_of(rows, "profit_before_tax", Q2_QUARTER, Representation.XBRL)
    assert {row.value for row in pbts} == {Decimal("3405600000"), Decimal("3405700000")}
    incl = constructed(rows, INCL_ASSOCIATES_RULE, Q2_QUARTER)
    assert incl.status is InterpretationStatus.INVALID
    assert incl.reason is InterpretationReason.INTERPRETATION_AMBIGUOUS and incl.value is None
    assert {row.interpretation_id for row in pbts} <= set(incl.operand_interpretation_ids)


# --- qualification ------------------------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_qualification_needs_its_condition_proven(
    ingest: Ingest, dictionary: CanonicalDictionary
) -> None:
    """A same-capture zero proves the condition but cannot replace measured company fixtures."""
    demonstrated = temp_mapping(
        ingest.tmp_path,
        dictionary,
        demonstrate_eps(["QUARTER", "HALF_YEAR"]),
        version="v1-test-demonstrated",
    )
    report = ingest.run(ingest.intake(XBRL_ONLY), mapping_set=demonstrated)
    rows = ingest.interpretations(report)
    eps = one(rows, "eps_basic", Q2_QUARTER, Representation.XBRL)
    assert eps.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert eps.qualification_ref is None and not eps.condition_evidence
    scope = demonstrated.entry("capmkt.eps_basic").qualification
    assert scope is not None
    (proof,) = prove_conditions(
        scope.conditions, interpretations=rows, period=Q2_QUARTER, basis=Basis.CONSOLIDATED
    ).values()
    assert proof.holds
    (evidence,) = ingest.repository.get_interpretations(proof.evidence_interpretation_ids)
    assert evidence.canonical_id == "eps_basic_discontinued"
    assert evidence.capture_ref_id == eps.capture_ref_id and evidence.value == 0
    withheld = MarkedEdit(label="no-discontinued-eps", find=EPS_DISCONTINUED_ONED, replace=b"")
    marked = ingest.run(
        ingest.intake(
            XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, withheld)}
        ),
        mapping_set=demonstrated,
    )
    unproven = one(ingest.interpretations(marked), "eps_basic", Q2_QUARTER, Representation.XBRL)
    assert unproven.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert unproven.qualification_ref is None and not unproven.condition_evidence


@pytest.mark.pg
@pytest.mark.retained
def test_qualification_is_per_measurement(ingest: Ingest, dictionary: CanonicalDictionary) -> None:
    """Each key is judged on its own period's proof and kind, never the package's."""
    demonstrated = temp_mapping(
        ingest.tmp_path,
        dictionary,
        demonstrate_eps(["QUARTER", "HALF_YEAR"]),
        version="v1-test-demonstrated",
    )
    nonzero = MarkedEdit(
        label="h1-discontinued-eps",
        find=EPS_DISCONTINUED_FOURD,
        replace=EPS_DISCONTINUED_FOURD.replace(b">0<", b">1.5<"),
    )
    report = ingest.run(
        ingest.intake(
            XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, nonzero)}
        ),
        mapping_set=demonstrated,
    )
    rows = ingest.interpretations(report)
    quarter = one(rows, "eps_basic", Q2_QUARTER, Representation.XBRL)
    half = one(rows, "eps_basic", Q2_HALF, Representation.XBRL)
    assert quarter.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert half.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    scope = demonstrated.entry("capmkt.eps_basic").qualification
    assert scope is not None
    quarter_proofs = prove_conditions(
        scope.conditions, interpretations=rows, period=Q2_QUARTER, basis=Basis.CONSOLIDATED
    )
    half_proofs = prove_conditions(
        scope.conditions, interpretations=rows, period=Q2_HALF, basis=Basis.CONSOLIDATED
    )
    assert all(proof.holds for proof in quarter_proofs.values())
    assert all(not proof.holds for proof in half_proofs.values())
    quarter_only = temp_mapping(
        ingest.tmp_path, dictionary, demonstrate_eps(["QUARTER"]), version="v1-test-quarter-only"
    )
    original = ingest.run(ingest.intake(XBRL_ONLY), mapping_set=quarter_only)
    assert ingest.package(original).reporting_kind is PeriodKind.HALF_YEAR
    rows = ingest.interpretations(original)
    assert one(rows, "eps_basic", Q2_QUARTER, Representation.XBRL).tier is (
        EvidenceTier.EQUIVALENCE_UNPROVEN
    )
    assert one(rows, "eps_basic", Q2_HALF, Representation.XBRL).tier is (
        EvidenceTier.EQUIVALENCE_UNPROVEN
    )
