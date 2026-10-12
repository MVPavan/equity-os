"""First-party ingest acceptance over retained Apar Q2 FY26 (D1a Task 5 entry point).

The stage's acceptance values — PBT 340.56 crore and PBT including associates 340.53 crore,
exact EPS, basis and unit isolation, row-aware PDF periods, the PDF tax construction —
plus periods, knowledge times, presence, missing values, the CLI and outcome translation.
Refusals, mapping, PDF marked copies and re-processing live in the sibling
``test_evidence_*`` modules; shared fixtures in ``evidence_support``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
import yaml
from derived_support import (
    ALIGNMENT_V1,
    BSE_FIN,
    FY25_Q4_END,
    OPENING_CASH,
    PROVEN,
    SEGMENT_TOTAL,
    SEGMENTS,
    WITHHELD_OPENING_CASH,
    WITHHELD_OTHERS,
    WITHHELD_REVENUE,
    PackageView,
    historical_fallback,
    marked_xbrl_package,
    operands_by_name,
    rounding,
    scope_entry,
    scope_formula,
    temp_dictionary,
    triple,
    xbrl_scope,
)
from evidence_support import (
    CONFIG,
    FY25_Q2_QUARTER,
    NO_VALUE_STATES,
    PDF_KIND,
    Q2_END,
    Q2_FY26,
    Q2_HALF,
    Q2_QUARTER,
    XBRL_KIND,
    XBRL_ONLY,
    Ingest,
    by_occurrence,
    dictionary,
    ingest,
    mapping_set,
    marked_xbrl,
    one,
    policy,
    rows_of,
    temp_mapping,
)
from pydantic import BaseModel, ConfigDict
from retained_support import APAR_MANIFEST, MarkedEdit

from fundamentals.api.cli import main
from fundamentals.canon.formula import average_operand
from fundamentals.contracts.acquisition_outcome import (
    ExtractionOutcome,
    OutcomeCode,
    OutcomeRecord,
    extraction_outcome_for,
    outcome_source_state,
)
from fundamentals.contracts.canonical import Basis, PeriodKind, Representation, StatementFamily
from fundamentals.contracts.comparison import CalculationState, SelectionSource, SourceState
from fundamentals.contracts.evidence import (
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    KeySelection,
    MissingValueState,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.snapshot import BodyCompleteness
from fundamentals.evidence.capture_intake import FiledAtFormatError, parse_filed_at
from fundamentals.evidence.derived import operand_value
from fundamentals.evidence.mapping import CONTEXT_LOCAL_NAME
from fundamentals.evidence.xbrl_adapter import CONTEXT_MEMBER_DESCRIPTIONS

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]


# --- values -------------------------------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_q2_fy26_profit_before_tax_and_construction(ingest: Ingest) -> None:
    """PBT 340.56 crore maps directly; PBT incl. associates 340.53 is constructed from both lines.

    The construction is a reported value assembled from the filing's own lines, so it must
    name both operand rows and never be assigned from the label "Profit before tax".
    """
    report = ingest.run(ingest.intake())
    rows = ingest.interpretations(report)
    pbt = one(rows, "profit_before_tax", Q2_QUARTER, Representation.XBRL)
    assert pbt.value == Decimal("3405600000")
    assert pbt.key is not None and pbt.key.basis is Basis.CONSOLIDATED
    incl = one(rows, "profit_before_tax_incl_associates", Q2_QUARTER, Representation.XBRL)
    assert incl.origin is InterpretationOrigin.CONSTRUCTED
    assert incl.value == Decimal("3405300000")
    associates = one(rows, "share_of_profit_associates_jv", Q2_QUARTER, Representation.XBRL)
    assert incl.operand_interpretation_ids == (pbt.interpretation_id, associates.interpretation_id)
    assert associates.value == Decimal("-300000")


@pytest.mark.pg
@pytest.mark.retained
def test_eps_is_exact_and_per_share(ingest: Ingest) -> None:
    """``INF`` EPS is a singleton 62.66; the PDF Basic line stays rupees per share."""
    report = ingest.run(ingest.intake())
    rows = ingest.interpretations(report)
    for canonical_id in ("eps_basic", "eps_basic_continuing"):
        eps = one(rows, canonical_id, Q2_QUARTER, Representation.XBRL)
        assert eps.value == Decimal("62.66")
        assert eps.interval is not None and eps.interval.lower == eps.interval.upper
    pdf_eps = one(rows, "eps_basic", Q2_QUARTER, Representation.PDF)
    assert pdf_eps.value == Decimal("62.66")
    # The PDF prints no discontinued line, so its scoped condition stays unproven.
    assert pdf_eps.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert pdf_eps.qualification_ref is None


@pytest.mark.pg
@pytest.mark.retained
def test_pdf_basis_and_unit_isolation(ingest: Ingest) -> None:
    """Only consolidated columns are read; crores scale by 10^7, per-share values do not."""
    report = ingest.run(ingest.intake())
    occurrences = ingest.occurrences(report)
    pdf = [item for item in occurrences.values() if item.representation is Representation.PDF]
    statement_pages = [item for item in pdf if item.anchor["page"] in (3, 6, 7)]
    assert statement_pages
    assert all("Consolidated" in str(item.anchor["super_header_text"]) for item in statement_pages)
    tax_cells = {item.raw_value_text for item in pdf if item.native_field == "(a) Current tax"}
    basic_cells = {item.raw_value_text for item in pdf if item.native_field == "Basic"}
    assert "89.13" in tax_cells and "88.15" not in tax_cells
    assert "62.66" in basic_cells and "63.20" not in basic_cells
    rows = ingest.interpretations(report)
    assert one(rows, "current_tax", Q2_QUARTER, Representation.PDF).value == Decimal("891300000")


@pytest.mark.pg
@pytest.mark.retained
def test_pdf_row_aware_periods(ingest: Ingest) -> None:
    """Cash-flow opening and closing cash come from half-year columns as instants."""
    report = ingest.run(ingest.intake())
    rows = ingest.interpretations(report)
    occurrences = ingest.occurrences(report)
    opening = one(rows, "cf_cash_opening", PeriodInterval.at(date(2025, 3, 31)), Representation.PDF)
    closing = one(rows, "cf_cash_closing", PeriodInterval.at(Q2_END), Representation.PDF)
    assert opening.value == Decimal("6864200000")
    assert closing.value == Decimal("3093900000")
    assert opening.occurrence_id is not None
    assert occurrences[opening.occurrence_id].period == Q2_HALF
    conductors = (("elimination_basis", "PRE_ELIMINATION"), ("segment", "conductors"))
    assets = rows_of(
        rows, "segment_assets", PeriodInterval.at(Q2_END), Representation.PDF, dimensions=conductors
    )
    revenue = one(rows, "segment_revenue", Q2_QUARTER, Representation.PDF, dimensions=conductors)
    assert assets and all(row.value == Decimal("59899600000") for row in assets)
    assert revenue.key is not None
    assert {row.key.digest() for row in assets if row.key is not None}.isdisjoint(
        {revenue.key.digest()}
    )


@pytest.mark.pg
@pytest.mark.retained
def test_pdf_tax_construction(ingest: Ingest) -> None:
    """Tax = current + deferred + earlier years; a printed dash counts as zero only by rule."""
    report = ingest.run(ingest.intake())
    rows = ingest.interpretations(report)
    q2 = one(rows, "tax_expense", Q2_QUARTER, Representation.PDF)
    assert q2.value == Decimal("888300000")
    earlier = q2.transform_trace["operands"]["earlier_years"]  # type: ignore[index]
    assert earlier["dash_rule_id"] == "apar-pdf-tax-earlier-years-dash"
    dash = one(rows, "tax_earlier_years", Q2_QUARTER, Representation.PDF)
    assert dash.value is None and dash.status is InterpretationStatus.MAPPED
    comparative = one(rows, "tax_expense", FY25_Q2_QUARTER, Representation.PDF)
    assert comparative.value == Decimal("628500000")


# --- periods, knowledge time, presence ------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_fy25_q2_declared_period_repair_and_one_member_package(ingest: Ingest) -> None:
    """OneD and FourD share raw dates; the declared periods tell them apart, raw kept."""
    report = ingest.run(
        ingest.intake({Representation.XBRL: "xbrl-consolidated-comparator"}, "FY25_Q2"),
        date(2024, 9, 30),
    )
    package = ingest.package(report)
    assert set(package.members) == {Representation.XBRL}
    assert all(attempt.representation is Representation.XBRL for attempt in report.attempts)
    occurrences = list(ingest.occurrences(report).values())
    quarter = [item for item in occurrences if item.native_context["context_ref"] == "OneD"]
    half = [item for item in occurrences if item.native_context["context_ref"] == "FourD"]
    assert quarter and half
    assert {item.period for item in quarter} == {FY25_Q2_QUARTER}
    assert {item.period for item in half} == {
        PeriodInterval.duration(date(2024, 4, 1), date(2024, 9, 30))
    }
    raw = {"start": "2024-07-01", "end": "2024-09-30", "instant": None}
    for item in (quarter[0], half[0]):
        assert item.native_context["raw_period"] == raw
        assert item.native_context["period_declaration"] is not None
    tax = one(ingest.interpretations(report), "tax_expense", FY25_Q2_QUARTER, Representation.XBRL)
    assert tax.value == Decimal("628500000")


def test_parse_filed_at_shapes() -> None:
    """NSE wall time is IST; an ISO offset is kept as written; any other shape is refused."""
    assert parse_filed_at("2024-10-30T10:47:06+00:00") == datetime(
        2024, 10, 30, 10, 47, 6, tzinfo=UTC
    )
    assert parse_filed_at("29-Oct-2025 20:58:58") == datetime(2025, 10, 29, 15, 28, 58, tzinfo=UTC)
    with pytest.raises(FiledAtFormatError):
        parse_filed_at("2025/10/29")


@pytest.mark.pg
@pytest.mark.retained
def test_member_knowledge_times(ingest: Ingest) -> None:
    """Each member keeps its own filed-at; the package's is the latest (the XBRL one)."""
    package = ingest.package(ingest.run(ingest.intake()))
    pdf, xbrl = package.members[Representation.PDF], package.members[Representation.XBRL]
    assert pdf.knowledge_time == datetime(2025, 10, 29, 8, 3, 43, tzinfo=UTC)
    assert xbrl.knowledge_time == datetime(2025, 10, 29, 15, 28, 58, tzinfo=UTC)
    assert (pdf.knowledge_time_raw, xbrl.knowledge_time_raw) == (
        "29-Oct-2025 13:33:43",
        "29-Oct-2025 20:58:58",
    )
    assert package.knowledge_time == xbrl.knowledge_time


@pytest.mark.pg
@pytest.mark.retained
def test_statement_presence_and_reporting_kind(ingest: Ingest) -> None:
    """Q2 presents balance sheet and cash flow (anchored at period end); Q3's XBRL does not."""
    report = ingest.run(ingest.intake())
    package = ingest.package(report)
    assert {StatementFamily.BALANCE_SHEET, StatementFamily.CASH_FLOW} <= package.statements_present
    assert package.reporting_kind is PeriodKind.HALF_YEAR
    assert report.package_id is not None
    statements = ingest.repository.get_package_statements_of([report.package_id])
    (balance_sheet,) = [
        s for s in statements if s.statement_family is StatementFamily.BALANCE_SHEET
    ]
    evidence = ingest.repository.get_occurrences(balance_sheet.evidence_occurrence_ids)
    anchors = {
        item.native_context[CONTEXT_LOCAL_NAME]
        for item in evidence
        if item.representation is Representation.XBRL and item.period == PeriodInterval.at(Q2_END)
    }
    assert {"Assets", "EquityAndLiabilities"} <= anchors
    q3 = ingest.package(ingest.run(ingest.intake(XBRL_ONLY, "FY26_Q3"), date(2025, 12, 31)))
    assert StatementFamily.BALANCE_SHEET not in q3.statements_present
    assert StatementFamily.CASH_FLOW not in q3.statements_present
    assert q3.reporting_kind is PeriodKind.NINE_MONTH


# --- missing values, unreadable cells ----------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_missing_markers_never_read_as_zero(ingest: Ingest) -> None:
    """Nil, dash and blank have no value; a nil fact is shown with a marked copy."""
    report = ingest.run(ingest.intake())
    occurrences = ingest.occurrences(report)
    rows = by_occurrence(ingest.interpretations(report))
    states = {item.missing_state for item in occurrences.values()}
    assert {MissingValueState.DASH, MissingValueState.BLANK} <= states
    for occurrence_id, occurrence in occurrences.items():
        if occurrence.missing_state in NO_VALUE_STATES:
            assert rows[occurrence_id].value is None
    nil = MarkedEdit(
        label="nil-current-tax",
        find=(
            b'<in-capmkt:CurrentTax contextRef="OneD" decimals="-5" unitRef="INR">891300000'
            b"</in-capmkt:CurrentTax>"
        ),
        replace=(
            b'<in-capmkt:CurrentTax xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            b'contextRef="OneD" unitRef="INR" xsi:nil="true"/>'
        ),
    )
    marked = ingest.run(
        ingest.intake(XBRL_ONLY, marked={Representation.XBRL: marked_xbrl(ingest.tmp_path, nil)})
    )
    nil_rows = by_occurrence(ingest.interpretations(marked))
    (nil_occurrence,) = [
        item
        for item in ingest.occurrences(marked).values()
        if item.missing_state is MissingValueState.NIL
    ]
    assert nil_occurrence.raw_value_text is None
    assert nil_occurrence.occurrence_id is not None
    nil_row = nil_rows[nil_occurrence.occurrence_id]
    assert nil_row.canonical_id == "current_tax" and nil_row.value is None


@pytest.mark.pg
@pytest.mark.retained
def test_unreadable_cell_is_invalid_not_a_parse_failure(ingest: Ingest) -> None:
    """The retained PDF's garbled H1 sales cell keeps its text and interprets INVALID."""
    report = ingest.run(ingest.intake())
    occurrences = ingest.occurrences(report)
    rows = by_occurrence(ingest.interpretations(report))
    (cell,) = [item for item in occurrences.values() if item.raw_value_text == "10,778,C0"]
    assert cell.missing_state is MissingValueState.VALUE and cell.occurrence_id is not None
    row = rows[cell.occurrence_id]
    assert row.status is InterpretationStatus.INVALID
    assert row.reason is InterpretationReason.UNREADABLE_CELL and row.value is None
    assert not [a for a in report.attempts if a.outcome is ExtractionOutcome.PARSE_FAILED]


# --- completeness, dimensions ---------------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_every_occurrence_is_interpreted_and_unmatched_lines_are_unmapped(ingest: Ingest) -> None:
    """One direct interpretation per occurrence; no matching entry means UNMAPPED, never dropped."""
    report = ingest.run(ingest.intake())
    occurrences = ingest.occurrences(report)
    rows = ingest.interpretations(report)
    direct = by_occurrence(rows)
    assert report.occurrence_count == len(occurrences) == len(direct)
    for occurrence_id, occurrence in occurrences.items():
        kind = occurrence.period.kind(3) if occurrence.period is not None else None
        if ingest.mapping_set.match(occurrence, period_kind=kind) is None:
            assert direct[occurrence_id].status is InterpretationStatus.UNMAPPED
            assert direct[occurrence_id].mapping_entry_id is None
    assert InterpretationStatus.UNMAPPED in {row.status for row in rows}


@pytest.mark.pg
@pytest.mark.retained
def test_segment_members_resolve_from_descriptions_not_ordinals(ingest: Ingest) -> None:
    """``Others`` is member 02 in FY25 and 04 in FY26, yet both resolve to one member."""
    q2 = ingest.run(ingest.intake(XBRL_ONLY))
    rows = ingest.interpretations(q2)
    others = (("elimination_basis", "PRE_ELIMINATION"), ("segment", "others"))
    revenue = one(rows, "segment_revenue", Q2_QUARTER, Representation.XBRL, dimensions=others)
    assert revenue.value == Decimal("334300000")
    post = one(
        rows,
        "segment_assets",
        PeriodInterval.at(Q2_END),
        Representation.XBRL,
        dimensions=(("elimination_basis", "POST_ELIMINATION"), ("segment", "conductors")),
    )
    pre = rows_of(
        rows,
        "segment_assets",
        PeriodInterval.at(Q2_END),
        Representation.XBRL,
        dimensions=(("elimination_basis", "PRE_ELIMINATION"), ("segment", "conductors")),
    )
    assert post.key is not None and not pre
    fy25 = ingest.run(
        ingest.intake({Representation.XBRL: "xbrl-consolidated-comparator"}, "FY25_Q2"),
        date(2024, 9, 30),
    )
    ordinals = {}
    for report in (q2, fy25):
        for occurrence in ingest.occurrences(report).values():
            descriptions = occurrence.native_context.get(CONTEXT_MEMBER_DESCRIPTIONS) or {}
            for found in descriptions.values():  # type: ignore[union-attr]
                if found["text"] == "Others":
                    ordinals.setdefault(report.package_id, set()).add(
                        str(occurrence.native_context["context_ref"])
                    )
    assert any("2" in ref for ref in ordinals[fy25.package_id])
    assert any("4" in ref for ref in ordinals[q2.package_id])
    members = ingest.repository.segment_members_as_of(
        ingest.entity_id, "segment", ingest.repository.store_clock()
    )
    others_rows = [member for member in members if member.member == "others"]
    assert {member.display_name for member in others_rows} == {"Others"}
    assert len({evidence for m in others_rows for evidence in m.evidence_occurrence_ids}) >= 2


# --- command line ---------------------------------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_cli_ingests_q2_fy26_and_is_idempotent(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``fundamentals evidence ingest`` composes the pins and writes the package once."""
    for key, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(key, value)
    ingest.intake()
    argv = [
        "evidence",
        "ingest",
        "--retrieval-manifest",
        str(APAR_MANIFEST),
        "--issuer",
        "APARINDS",
        "--quarter",
        Q2_FY26,
        "--period-end",
        Q2_END.isoformat(),
        "--basis",
        "consolidated",
        "--raw-root",
        str(ingest.tmp_path / "inputs"),
        "--snapshot-root",
        str(ingest.tmp_path / "store"),
        "--member",
        f"xbrl={XBRL_KIND}",
        "--member",
        f"pdf={PDF_KIND}",
        "--issuer-config",
        str(CONFIG / "aparinds-fy26-q2.yaml"),
        "--config-root",
        str(CONFIG),
    ]
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert first.splitlines()[0] == "package\t1"
    assert "attempt\tEXTRACTION\tPDF\t-\tCOMPLETE" in first
    before = ingest.table_counts()
    assert main(argv) == 0
    assert ingest.table_counts() == before
    # A PDF member with no issuer config cannot be read: refused before any write.
    config_flag = argv.index("--issuer-config")
    assert main([*argv[:config_flag], *argv[config_flag + 2 :]]) == 2
    assert ingest.table_counts() == before


# --- outcome translation ----------------------------------------------------------------------


class _Captured(BaseModel):
    """A stand-in capture record: only the two fields the translation reads."""

    model_config = ConfigDict(frozen=True)

    outcome: OutcomeRecord
    effective_body_completeness: BodyCompleteness


@pytest.mark.parametrize(
    ("code", "completeness", "flags", "expected"),
    [
        (OutcomeCode.OK_EMPTY, BodyCompleteness.ABSENT, (), ExtractionOutcome.NOT_PUBLISHED),
        (OutcomeCode.NOT_OFFERED, BodyCompleteness.ABSENT, (), ExtractionOutcome.NOT_PUBLISHED),
        (
            OutcomeCode.IDENTITY_MISMATCH,
            BodyCompleteness.COMPLETE,
            (),
            ExtractionOutcome.IDENTITY_REJECTED,
        ),
        (
            OutcomeCode.SCHEMA_DRIFT,
            BodyCompleteness.COMPLETE,
            (),
            ExtractionOutcome.UNSUPPORTED_SCHEMA,
        ),
        (OutcomeCode.PLAN_LOCKED, BodyCompleteness.ABSENT, (), ExtractionOutcome.FAILED),
        (OutcomeCode.OK, BodyCompleteness.PARTIAL, ("parse",), ExtractionOutcome.PARTIAL),
        (OutcomeCode.OK, BodyCompleteness.ABSENT, (), ExtractionOutcome.FAILED),
        (
            OutcomeCode.OK,
            BodyCompleteness.COMPLETE,
            ("schema", "parse"),
            ExtractionOutcome.UNSUPPORTED_SCHEMA,
        ),
        (
            OutcomeCode.OK,
            BodyCompleteness.COMPLETE,
            ("parse", "identity"),
            ExtractionOutcome.PARSE_FAILED,
        ),
        (
            OutcomeCode.OK,
            BodyCompleteness.COMPLETE,
            ("identity",),
            ExtractionOutcome.IDENTITY_REJECTED,
        ),
        (OutcomeCode.OK, BodyCompleteness.COMPLETE, (), ExtractionOutcome.COMPLETE),
    ],
)
def test_extraction_outcome_translation(
    code: OutcomeCode,
    completeness: BodyCompleteness,
    flags: tuple[str, ...],
    expected: ExtractionOutcome,
) -> None:
    """The capture decides first, then schema, parse and identity, in that order.

    Only an evidenced absence may become ``NO_VALUE``; every failure is ``UNAVAILABLE``.
    """
    record = _Captured(
        outcome=OutcomeRecord(code=code, native_kind="test", native_value="test"),
        effective_body_completeness=completeness,
    )
    outcome = extraction_outcome_for(
        record,
        parse_failed="parse" in flags,
        unsupported_schema="schema" in flags,
        identity_rejected="identity" in flags,
    )
    assert outcome is expected
    state = outcome_source_state(outcome)
    if outcome is ExtractionOutcome.COMPLETE:
        assert state is None
    elif outcome is ExtractionOutcome.NOT_PUBLISHED:
        assert state is SourceState.NO_VALUE
    else:
        assert state is SourceState.UNAVAILABLE


# --- Task 7: alignment proofs, scoped tiers, derived evaluation with stored traces --------


@pytest.mark.pg
@pytest.mark.retained
def test_opm_q2_fy26_evaluates_to_8_06_with_a_stored_trace(ingest: Ingest) -> None:
    """OPM per representation is the committed formula over filed lines, stored and re-read.

    Expected value by hand from the filed crore lines (revenue 5,715.42; total expenses
    5,402.29; finance costs 107.90; D&A 39.88): (5,715.42 - (5,402.29 - 107.90 - 39.88)) /
    5,715.42 x 100 = 8.0643...%, stored at scale 2 as 8.06. Finance costs and D&A have no
    alignment rule, so the effective tier stays unproven.
    """
    view = PackageView(ingest, ingest.run(ingest.intake()))
    proofs = view.stored_proofs()
    revenue, expenses, finance, amortisation = (
        Fraction(57154200000),
        Fraction(54022900000),
        Fraction(1079000000),
        Fraction(398800000),
    )
    expected = (revenue - (expenses - finance - amortisation)) / revenue * 100
    for representation in (Representation.XBRL, Representation.PDF):
        side = view.evaluate(
            "opm_pct", Q2_QUARTER, representation, dictionary=ingest.dictionary, proofs=proofs
        )
        assert side.result.state is CalculationState.COMPUTED
        assert side.result.exact == expected and side.result.value == Decimal("8.06")
        (stored,) = ingest.repository.get_calculation_traces([side.trace_id])
        trace = stored.trace
        assert trace == side.result.trace and trace.value == Decimal("8.06")
        assert (trace.formula_id, trace.formula_version, trace.rounding_policy_id) == (
            "opm_pct",
            "1",
            "v1",
        )
        assert trace.effective_tier is EvidenceTier.EQUIVALENCE_UNPROVEN
        top = operands_by_name(stored)
        (ebitda,) = stored.children
        (opex,) = ebitda.children
        assert top["ebitda"].operand_trace_id == ebitda.trace_id
        assert operands_by_name(ebitda)["opex"].operand_trace_id == opex.trace_id
        selected = top["revenue"]
        assert selected.scoped_tier is EvidenceTier.EQUIVALENCE_DEMONSTRATED
        assert selected.alignment_proof_id is not None
        assert selected.selection_source is SelectionSource.PACKAGE_AS_REPORTED
        opex_operands = operands_by_name(opex)
        for name in ("finance_costs", "depreciation_amortisation"):
            operand = opex_operands[name]
            assert operand.scoped_tier is EvidenceTier.EQUIVALENCE_UNPROVEN
            assert operand.alignment_proof_id is None and operand.interpretation_id
            assert operand.lower <= operand.value <= operand.upper
        print(f"OPM {representation.value}: {trace.value} (exact {trace.exact_value})")


@pytest.mark.pg
@pytest.mark.retained
def test_alignment_proofs_are_per_key_and_per_member(ingest: Ingest, tmp_path: Path) -> None:
    """Quarter and H1 keys are proven separately; a proof never names another key's rows."""
    view = PackageView(ingest, ingest.run(ingest.intake()))
    proofs = view.stored_proofs()
    assert ingest.repository.list_alignment_proofs(view.package.package_id or 0) == proofs
    holding = [proof for proof in proofs if proof.holds]
    for canonical_id in PROVEN:
        for period in (Q2_QUARTER, Q2_HALF):
            (proof,) = [
                p for p in holding if p.key.canonical_id == canonical_id and p.key.period == period
            ]
            participants = ingest.repository.get_interpretations(
                [pid for pid, _ in proof.participants]
            )
            assert {(row.key.period, row.key.dimensions) for row in participants if row.key} == {
                (period, proof.key.dimensions)
            }
    assert len({proof.proof_id for proof in holding}) == len(holding)
    rules = yaml.safe_load(ALIGNMENT_V1.read_text(encoding="utf-8"))
    rules["rules"].append(
        {
            "rule_id": "test.segment_revenue.layout",
            "kind": "LAYOUT_POSITION",
            "canonical_id": "segment_revenue",
            "layout_anchor": {"XBRL": "capmkt.segment_revenue", "PDF": "pdf.segment_revenue"},
            "evidence_ref": "temporary test rule",
        }
    )
    path = tmp_path / "alignment-with-segments.yaml"
    path.write_text(yaml.safe_dump(rules), encoding="utf-8")
    segment = [p for p in view.stored_proofs(path) if p.key.canonical_id == "segment_revenue"]
    by_member = {
        dict(p.key.dimensions.pairs)["segment"]: p for p in segment if p.key.period == Q2_QUARTER
    }
    assert set(by_member) == set(SEGMENTS)
    conductors, others = by_member["conductors"], by_member["others"]
    assert conductors.proof_id != others.proof_id
    for proof, member in ((conductors, "conductors"), (others, "others")):
        rows = ingest.repository.get_interpretations([pid for pid, _ in proof.participants])
        assert {dict(row.key.dimensions.pairs)["segment"] for row in rows if row.key} == {member}


@pytest.mark.pg
@pytest.mark.retained
def test_receivable_days_reads_the_closing_instant(ingest: Ingest) -> None:
    """H1 receivable days uses receivables at 2025-09-30, never the 2025-03-31 column."""
    view = PackageView(ingest, ingest.run(ingest.intake()))
    closing = view.key("trade_receivables_current", PeriodInterval.at(Q2_END), ingest.dictionary)
    for representation in (Representation.XBRL, Representation.PDF):
        side = view.evaluate(
            "receivable_days", Q2_HALF, representation, dictionary=ingest.dictionary
        )
        assert side.result.exact == Fraction(45845600000, 108195800000) * 183
        (stored,) = ingest.repository.get_calculation_traces([side.trace_id])
        receivables = operands_by_name(stored)["receivables"]
        chosen = view.select(closing, representation).interpretation
        assert chosen is not None and chosen.key == closing
        assert receivables.key_digest == closing.digest()
        assert receivables.interpretation_id == chosen.interpretation_id


@pytest.mark.pg
@pytest.mark.retained
def test_opening_cash_operand_source(ingest: Ingest) -> None:
    """The H1 cash-flow opening balance is the package's own disclosure; without it, the
    FY25 Q4 package supplies it as a historical package, with that package's row."""
    view = PackageView(ingest, ingest.run(ingest.intake()))
    key = view.key("cf_cash_closing", OPENING_CASH, ingest.dictionary)

    def unused() -> KeySelection:
        raise AssertionError("the package discloses its opening balance")

    own = operand_value(view.opening(key, Representation.XBRL, unused), proofs=())
    assert own.selection_source is SelectionSource.PACKAGE_OPENING_DISCLOSURE
    assert own.value == Decimal("6864200000") and own.package_id == view.package.package_id
    fy25_q4 = ingest.run(
        ingest.intake({Representation.XBRL: "xbrl-consolidated-comparator"}, "FY25_Q4"), FY25_Q4_END
    )
    marked = marked_xbrl_package(ingest, WITHHELD_OPENING_CASH)
    historical = PackageView(ingest, fy25_q4)

    def fallback() -> KeySelection:
        return historical_fallback(ingest, historical, key, marked.boundary)

    used = operand_value(marked.opening(key, Representation.XBRL, fallback), proofs=())
    expected = historical.select(key, Representation.XBRL).interpretation
    assert expected is not None and used.interpretation_id == expected.interpretation_id
    assert used.selection_source is SelectionSource.HISTORICAL_PACKAGE
    assert used.package_id == fy25_q4.package_id


@pytest.mark.pg
@pytest.mark.retained
def test_segment_total_and_average_child_traces(ingest: Ingest) -> None:
    """The segment total aggregates every evidenced member in a stored child trace; a
    withheld member leaves the total missing yet still listed; an average lists both instants."""
    view = PackageView(ingest, ingest.run(ingest.intake()))
    side = view.evaluate(
        "segment_revenue_members_total",
        Q2_QUARTER,
        Representation.XBRL,
        dictionary=ingest.dictionary,
        dimensions=SEGMENT_TOTAL,
    )
    assert side.result.value == Decimal("60107900000.00") and len(side.bound_member_ids) == 4
    marked = marked_xbrl_package(ingest, WITHHELD_OTHERS)
    missing = marked.evaluate(
        "segment_revenue_members_total",
        Q2_QUARTER,
        Representation.XBRL,
        dictionary=ingest.dictionary,
        dimensions=SEGMENT_TOTAL,
    )
    assert missing.result.state is CalculationState.OPERAND_MISSING and missing.result.value is None
    for derived, withheld in ((side, set()), (missing, {"others"})):
        (stored,) = ingest.repository.get_calculation_traces([derived.trace_id])
        (child,) = stored.children
        assert child.trace.trace_kind.value == "DIMENSIONAL_AGGREGATE"
        assert {operand.name for operand in child.trace.operands} == set(SEGMENTS)
        absent = {o.name for o in child.trace.operands if o.interpretation_id is None}
        assert absent == withheld
        assert all(
            o.source_state is SourceState.NO_VALUE
            for o in child.trace.operands
            if o.name in withheld
        )
    opening = view.key("trade_receivables_current", OPENING_CASH, ingest.dictionary)
    closing = opening.model_copy(update={"period": PeriodInterval.at(Q2_END)})
    averaged = average_operand(
        operand_value(view.select(opening, Representation.PDF), proofs=()),
        operand_value(view.select(closing, Representation.PDF), proofs=()),
        output=opening.model_copy(update={"period": Q2_HALF}),
        policy=rounding(),
    )
    assert averaged.child_trace is not None
    (stored,) = ingest.repository.get_calculation_traces(
        [ingest.repository.put_calculation_trace(averaged.child_trace)]
    )
    assert [o.key_digest for o in stored.trace.operands] == [opening.digest(), closing.digest()]
    assert all(o.interpretation_id is not None for o in stored.trace.operands)


@pytest.mark.pg
@pytest.mark.retained
def test_withheld_operand_gives_a_stored_missing_side(ingest: Ingest) -> None:
    """No revenue line: OPM is ``OPERAND_MISSING`` with no value and still a stored trace."""
    marked = marked_xbrl_package(ingest, WITHHELD_REVENUE)
    side = marked.evaluate("opm_pct", Q2_QUARTER, Representation.XBRL, dictionary=ingest.dictionary)
    assert side.result.state is CalculationState.OPERAND_MISSING
    assert side.result.value is None and side.result.exact is None
    (stored,) = ingest.repository.get_calculation_traces([side.trace_id])
    assert stored.trace.state is CalculationState.OPERAND_MISSING and stored.trace.value is None


@pytest.mark.pg
@pytest.mark.retained
def test_tiers_are_scoped_per_measurement(ingest: Ingest, tmp_path: Path) -> None:
    """A demonstrated entry or formula outside its scope is unproven; a QUARTER-scoped
    formula is demonstrated for the Q2 output and unproven for the H1 output."""

    in_bse_fin = xbrl_scope("test-bse-only", ["CONSOLIDATED"], ["QUARTER", "HALF_YEAR"], BSE_FIN)
    edit = scope_entry("capmkt.finance_costs", in_bse_fin)
    scoped = temp_mapping(tmp_path, ingest.dictionary, edit, version="v1-scope")
    view = PackageView(ingest, ingest.run(ingest.intake(XBRL_ONLY), mapping_set=scoped))
    view.pins = triple("v1-scope")
    finance_key = view.key("finance_costs", Q2_QUARTER, ingest.dictionary)
    operand = operand_value(view.select(finance_key, Representation.XBRL), proofs=())
    unproven = (EvidenceTier.EQUIVALENCE_UNPROVEN, None)
    assert (operand.scoped_tier, operand.qualification_ref) == unproven
    standalone_scope = xbrl_scope("test-standalone", ["STANDALONE"], ["QUARTER"])
    standalone = temp_dictionary(tmp_path, scope_formula("opm_pct", standalone_scope))
    quarter_scope = xbrl_scope("test-quarter", ["CONSOLIDATED"], ["QUARTER"])
    quarter = temp_dictionary(tmp_path, scope_formula("opm_pct", quarter_scope))
    out = view.evaluate("opm_pct", Q2_QUARTER, Representation.XBRL, dictionary=standalone)
    assert (out.result.trace.formula_tier, out.result.trace.formula_qualification_ref) == unproven
    q2 = view.evaluate("opm_pct", Q2_QUARTER, Representation.XBRL, dictionary=quarter).result.trace
    h1 = view.evaluate("opm_pct", Q2_HALF, Representation.XBRL, dictionary=quarter).result.trace
    assert (q2.formula_tier, q2.formula_qualification_ref) == (
        EvidenceTier.EQUIVALENCE_DEMONSTRATED,
        "test-quarter",
    )
    assert (h1.formula_tier, h1.formula_qualification_ref) == unproven
