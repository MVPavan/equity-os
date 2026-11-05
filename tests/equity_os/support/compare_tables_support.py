"""Shared constructions for the D1a.5 decision-table tests (data spec §5).

Reported sides, definition records, each table's parametrized rows, and derived cases that
evaluate real dictionary v1 formulas per representation from actual operand states.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from canon_formula_support import (
    DEMONSTRATED,
    H1_FY26,
    INR,
    Q2_FY26,
    UNPROVEN,
    evaluate_inr,
    key,
    leaf,
    load_v1_dictionary,
    load_v1_policy,
    quarter_context,
)
from selection_support import at, interpretation, member, package

from equity_os.contracts.measurement.canonical import (
    Basis,
    PeriodKind,
    Representation,
    StatementFamily,
    TemporalRole,
    ValueKind,
)
from equity_os.contracts.measurement.evidence import (
    FilingPackage,
    KeySelection,
    Occurrence,
    PackageMember,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import DimensionSet, MeasurementKey
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.measurement.qualification import QualificationFixture, QualificationScope
from equity_os.contracts.verification.comparison import (
    ExtractionStatus,
    PairOutcome,
    ReasonCode,
    SelectionSource,
    SourceState,
)
from equity_os.normalisation.derivation.formula import (
    CalculationResult,
    CalculationTrace,
    OperandValue,
)
from equity_os.normalisation.derivation.interval import Interval
from equity_os.normalisation.dictionary.dictionary import DictionaryRow
from equity_os.storage.records.repository import SegmentMemberRecord
from equity_os.verification.comparison.definitions import (
    DefinitionRecord,
    DefinitionScope,
    DefinitionSet,
    load_definition_set,
)
from equity_os.verification.comparison.engine_attempts import bare_selection
from equity_os.verification.comparison.engine_rows import Cell
from equity_os.verification.comparison.policy import load_comparison_policy
from equity_os.verification.comparison.selection import period_end
from equity_os.verification.comparison.tables import (
    ComparisonSide,
    ExtractionResult,
    OperandExtraction,
    TaggingAdjustment,
    derived_extraction_status,
    extraction_status,
)

REPO = Path(__file__).resolve().parents[3]
POLICY = load_comparison_policy(REPO / "config" / "verification/comparison_policy" / "v1.yaml")
EMPTY = load_definition_set(REPO / "config" / "verification/definition_sets" / "v1.yaml")
DICTIONARY = load_v1_dictionary()
ROUNDING = load_v1_policy()
PACKAGE = 10
REVENUE = key("revenue_from_operations", Q2_FY26)
XBRL_REVENUE_ENTRY = "xbrl:revenue"
PDF_REVENUE_ENTRY = "pdf:revenue"


def side(
    value: str | None,
    *,
    measurement: MeasurementKey = REVENUE,
    decimals: int | None = 1,
    state: SourceState = SourceState.VALUE,
    tier: EvidenceTier = DEMONSTRATED,
    aligned: bool = False,
    entries: tuple[str, ...] = (XBRL_REVENUE_ENTRY,),
    package_id: int | None = PACKAGE,
    reasons: tuple[ReasonCode, ...] = (),
    precision_supported: bool = True,
) -> ComparisonSide:
    """A reported side; ``decimals=None`` is an exact value (a count)."""
    number = None if value is None else Decimal(value)
    interval = None
    if number is not None and precision_supported:
        interval = (
            Interval.exact(number)
            if decimals is None
            else Interval.from_precision(number, decimals)
        )
    return ComparisonSide(
        key=measurement,
        state=state,
        value=number,
        interval=interval,
        tier=tier,
        aligned_by_proof=aligned,
        mapping_entry_ids=entries,
        package_id=package_id,
        calculation_state=None,
        reasons=reasons,
    )


def pdf(
    value: str | None,
    *,
    measurement: MeasurementKey = REVENUE,
    state: SourceState = SourceState.VALUE,
    tier: EvidenceTier = DEMONSTRATED,
    aligned: bool = False,
    reasons: tuple[ReasonCode, ...] = (),
    precision_supported: bool = True,
) -> ComparisonSide:
    """A PDF-mapped reported side of the same package, at one decimal."""
    return side(
        value,
        measurement=measurement,
        state=state,
        tier=tier,
        aligned=aligned,
        entries=(PDF_REVENUE_ENTRY,),
        reasons=reasons,
        precision_supported=precision_supported,
    )


def record(
    record_id: str,
    scope: DefinitionScope,
    scope_ref: str,
    amount: str,
    *,
    canonical_id: str = "revenue_from_operations",
    operand_name: str | None = None,
    unit: ValueKind = ValueKind.CURRENCY_AMOUNT,
) -> DefinitionRecord:
    """An evidenced definition record."""
    return DefinitionRecord(
        record_id=record_id,
        scope=scope,
        scope_ref=scope_ref,
        canonical_id=canonical_id,
        operand_name=operand_name,
        evidence_ref=f"disposition:{record_id}",
        explained_amount=Decimal(amount),
        unit=unit,
    )


def definitions(*records: DefinitionRecord) -> DefinitionSet:
    """A pinned definition set holding ``records``."""
    return DefinitionSet(version="test", content_sha256="test", records=records)


def rekey(**update: object) -> MeasurementKey:
    """The revenue key with one part changed."""
    return REVENUE.model_copy(update=update)


# --- Pair table ---------------------------------------------------------------------------------

# 1000.0 and 1010.0 at one decimal: [999.95, 1000.05] and [1009.95, 1010.05], gap 9.9.
PAIR_ROWS = [
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=key("other_income", Q2_FY26)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.CANONICAL_MISMATCH,
        id="row1-canonical-mismatch",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(period=H1_FY26)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.PERIOD_MISMATCH,
        id="row1-period",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(basis=Basis.STANDALONE)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.BASIS_MISMATCH,
        id="row1-basis",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(framework=AccountingFramework.IFRS)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.FRAMEWORK_MISMATCH,
        id="row1-framework",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(currency="USD")),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.CURRENCY_MISMATCH,
        id="row1-currency",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(value_kind=ValueKind.PER_SHARE_AMOUNT)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.KIND_MISMATCH,
        id="row1-kind",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", measurement=rekey(dimensions=DimensionSet.of({"segment": "conductors"}))),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.DIMENSION_UNRESOLVED,
        id="row1-dimension",
    ),
    pytest.param(
        side("1000.0", reasons=(ReasonCode.PERIOD_AMBIGUOUS,)),
        pdf("1000.0"),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.PERIOD_AMBIGUOUS,
        id="row1-period-ambiguous",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", precision_supported=False),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.PRECISION_UNSUPPORTED,
        id="row1-precision-unsupported",
    ),
    pytest.param(
        side("1000.0"),
        pdf(None, state=SourceState.INVALID, reasons=(ReasonCode.UNREADABLE_CELL,)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.UNREADABLE_CELL,
        id="row1-invalid-unreadable-cell",
    ),
    pytest.param(
        side(None, state=SourceState.INVALID),
        pdf("1000.0"),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.SIDE_INVALID,
        id="row1-invalid-without-reason",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", reasons=(ReasonCode.VENDOR_INTERNAL_CONFLICT,)),
        PairOutcome.NOT_COMPARABLE,
        ReasonCode.VENDOR_INTERNAL_CONFLICT,
        id="row1-vendor-internal-conflict",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.1"),
        PairOutcome.AGREE,
        None,
        id="row2-demonstrated-touching-intervals",
    ),
    pytest.param(
        side("1000.0", tier=UNPROVEN, aligned=True),
        pdf("1000.0", tier=UNPROVEN, aligned=True),
        PairOutcome.AGREE,
        None,
        id="row2-alignment-proof",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1000.0", tier=UNPROVEN),
        PairOutcome.AGREE_UNQUALIFIED,
        None,
        id="row3-one-side-unproven",
    ),
    pytest.param(
        side("1000.0", aligned=True),
        pdf("1000.0", tier=UNPROVEN),
        PairOutcome.AGREE_UNQUALIFIED,
        None,
        id="row3-proof-on-one-side-only",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1010.0"),
        PairOutcome.MISMATCH,
        None,
        id="row5-demonstrated",
    ),
    pytest.param(
        side("1000.0"),
        pdf("1010.0", tier=EvidenceTier.RELATED_NOT_EQUIVALENT),
        PairOutcome.ANOMALY,
        None,
        id="row6-otherwise",
    ),
]


SCOPE_CASES = [
    pytest.param(
        record("F-other", DefinitionScope.FILING, "99", "10"),
        PairOutcome.MISMATCH,
        id="filing-record-for-another-package",
    ),
    pytest.param(
        record("F-this", DefinitionScope.FILING, str(PACKAGE), "10"),
        PairOutcome.DEFINITION_DIFFERENCE,
        id="filing-record-for-this-package",
    ),
    pytest.param(
        record("M-unused", DefinitionScope.MAPPING, "pdf:unused-entry", "10"),
        PairOutcome.MISMATCH,
        id="mapping-record-for-an-entry-neither-side-uses",
    ),
    pytest.param(
        record("M-xbrl", DefinitionScope.MAPPING, XBRL_REVENUE_ENTRY, "10"),
        PairOutcome.DEFINITION_DIFFERENCE,
        id="mapping-record-for-the-xbrl-entry",
    ),
    pytest.param(
        record("K-this", DefinitionScope.MEASUREMENT, REVENUE.digest(), "10"),
        PairOutcome.DEFINITION_DIFFERENCE,
        id="measurement-record-for-this-key",
    ),
    pytest.param(
        record("K-other", DefinitionScope.MEASUREMENT, rekey(period=H1_FY26).digest(), "10"),
        PairOutcome.MISMATCH,
        id="measurement-record-for-another-key",
    ),
    pytest.param(
        record(
            "F-other-row", DefinitionScope.FILING, str(PACKAGE), "10", canonical_id="other_income"
        ),
        PairOutcome.MISMATCH,
        id="record-for-another-canonical-id",
    ),
    pytest.param(
        record(
            "F-wrong-unit", DefinitionScope.FILING, str(PACKAGE), "10", unit=ValueKind.PERCENTAGE
        ),
        PairOutcome.MISMATCH,
        id="record-in-another-unit",
    ),
]


EXTRACTION_ROWS = [
    pytest.param(
        False,
        side("1000.0"),
        pdf("1010.0"),
        ExtractionStatus.NOT_APPLICABLE,
        None,
        id="row1-no-paired-representation",
    ),
    pytest.param(
        True,
        side(None, state=SourceState.UNAVAILABLE),
        pdf(None, state=SourceState.INVALID, reasons=(ReasonCode.UNREADABLE_CELL,)),
        ExtractionStatus.UNAVAILABLE,
        None,
        id="row2-unavailable-before-invalid",
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf(None, state=SourceState.UNAVAILABLE),
        ExtractionStatus.UNAVAILABLE,
        None,
        id="row2-pdf-unavailable",
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf(None, state=SourceState.INVALID, reasons=(ReasonCode.UNREADABLE_CELL,)),
        ExtractionStatus.NOT_COMPARABLE,
        ReasonCode.UNREADABLE_CELL,
        id="row2a-unreadable-cell",
    ),
    pytest.param(
        True,
        side(None, state=SourceState.NO_VALUE),
        pdf(None, state=SourceState.NO_VALUE),
        ExtractionStatus.NONE,
        None,
        id="row3-neither",
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf(None, state=SourceState.NO_VALUE),
        ExtractionStatus.ONE_SIDE_XBRL,
        None,
        id="row4-xbrl-only",
    ),
    pytest.param(
        True,
        side(None, state=SourceState.NO_VALUE),
        pdf("1000.0"),
        ExtractionStatus.ONE_SIDE_PDF,
        None,
        id="row4-pdf-only",
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf("1000.0", precision_supported=False),
        ExtractionStatus.NOT_COMPARABLE,
        ReasonCode.PRECISION_UNSUPPORTED,
        id="row5-pair-not-comparable",
    ),
    pytest.param(
        True, side("1000.0"), pdf("1000.0"), ExtractionStatus.AGREE, None, id="row6-agree"
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf("1000.0", tier=UNPROVEN),
        ExtractionStatus.AGREE_UNQUALIFIED,
        None,
        id="row7-agree-unqualified",
    ),
    pytest.param(
        True, side("1000.0"), pdf("1010.0"), ExtractionStatus.DISAGREE, None, id="row9-mismatch"
    ),
    pytest.param(
        True,
        side("1000.0"),
        pdf("1010.0", tier=UNPROVEN),
        ExtractionStatus.DISAGREE,
        None,
        id="row9-anomaly",
    ),
]


# --- Derived extraction -------------------------------------------------------------------------

OPEX = key("opex_excl_finance_and_da", Q2_FY26)
PBT_MARGIN = key("pbt_margin_pct", Q2_FY26, ValueKind.PERCENTAGE)
OPEX_OPERANDS = {
    "total_expenses": "total_expenses",
    "finance_costs": "finance_costs",
    "depreciation_amortisation": "depreciation_amortisation",
}
PBT_OPERANDS = {"pbt": "profit_before_tax_incl_associates", "revenue": "revenue_from_operations"}
FINANCE_RECORD = record(
    "FC-1",
    DefinitionScope.MAPPING,
    "pdf:finance_costs",
    "10",
    canonical_id="finance_costs",
    operand_name="finance_costs",
)
TOTAL_RECORD = record(
    "TE-1",
    DefinitionScope.MAPPING,
    "pdf:total_expenses",
    "10",
    canonical_id="total_expenses",
    operand_name="total_expenses",
)
PBT_RECORD = record(
    "PBT-1",
    DefinitionScope.FILING,
    str(PACKAGE),
    "10",
    canonical_id="profit_before_tax_incl_associates",
    operand_name="pbt",
)


class OperandState:
    """One representation's operand as read: a value, or an absence or refusal with reasons."""

    def __init__(
        self,
        state: SourceState = SourceState.VALUE,
        *,
        reasons: tuple[str, ...] = (),
        precision_supported: bool = True,
    ) -> None:
        self.state, self.reasons, self.precision_supported = state, reasons, precision_supported


def operand_value(
    canonical_id: str,
    value: str | None,
    representation: Representation,
    *,
    tier: EvidenceTier = DEMONSTRATED,
    kind: ValueKind = ValueKind.CURRENCY_AMOUNT,
    read: OperandState | None = None,
    basis: Basis = Basis.CONSOLIDATED,
) -> OperandValue:
    """One representation's selected operand, mapped by its own entry, at one decimal."""
    read = read or OperandState()
    measurement = key(canonical_id, Q2_FY26, kind).model_copy(update={"basis": basis})
    operand = leaf(
        measurement,
        value,
        state=read.state,
        decimals=1,
        tier=tier,
        precision_supported=read.precision_supported,
        reasons=read.reasons,
    )
    return operand.model_copy(
        update={"mapping_entry_id": f"{representation.value.lower()}:{canonical_id}"}
    )


def reason_codes(reasons: tuple[str, ...]) -> tuple[ReasonCode, ...]:
    """Typed reason codes from an operand's or a calculation's propagated reasons."""
    return tuple(ReasonCode(reason) for reason in reasons)


def operand_side(operand: OperandValue) -> ComparisonSide:
    """A reported operand as a comparison side."""
    return ComparisonSide(
        key=operand.key,
        state=operand.state,
        value=operand.value,
        interval=operand.interval,
        tier=operand.scoped_tier,
        aligned_by_proof=False,
        mapping_entry_ids=() if operand.mapping_entry_id is None else (operand.mapping_entry_id,),
        package_id=operand.package_id,
        calculation_state=None,
        reasons=reason_codes(operand.reasons),
    )


def derived_side(result: CalculationResult, output: MeasurementKey) -> ComparisonSide:
    """One representation's evaluated formula as a comparison side, state from its calculation."""
    return ComparisonSide(
        key=output,
        state=result.source_state,
        value=result.value,
        interval=result.interval,
        tier=result.effective_tier,
        aligned_by_proof=False,
        mapping_entry_ids=(),
        package_id=PACKAGE,
        calculation_state=result.state,
        reasons=reason_codes(result.reasons),
    )


class DerivedCase:
    """Both representations of a derived row, each operand's own extraction, both sides.

    ``reads`` overrides how one representation's operand was read (absent, invalid, without
    precision); ``pdf_basis`` evaluates the PDF side on another basis.
    """

    def __init__(
        self,
        row: DictionaryRow,
        output: MeasurementKey,
        names: Mapping[str, str],
        xbrl_values: Mapping[str, str | None],
        pdf_values: Mapping[str, str | None],
        defs: DefinitionSet,
        *,
        tiers: Mapping[str, EvidenceTier] | None = None,
        reads: Mapping[tuple[Representation, str], OperandState] | None = None,
        pdf_basis: Basis = Basis.CONSOLIDATED,
    ) -> None:
        tiers, reads = tiers or {}, reads or {}
        self.row, self.output, self.defs = row, output, defs
        self.operands: dict[str, OperandExtraction] = {}
        values = {Representation.XBRL: xbrl_values, Representation.PDF: pdf_values}
        bases = {Representation.XBRL: Basis.CONSOLIDATED, Representation.PDF: pdf_basis}
        by_rep: dict[Representation, dict[str, OperandValue]] = {rep: {} for rep in values}
        for name, canonical_id in names.items():
            kind = DICTIONARY.row(canonical_id).value_kind
            for rep in values:
                by_rep[rep][name] = operand_value(
                    canonical_id,
                    values[rep][name],
                    rep,
                    tier=tiers.get(name, DEMONSTRATED),
                    kind=kind,
                    read=reads.get((rep, name)),
                    basis=bases[rep],
                )
            xbrl, pdf_value = by_rep[Representation.XBRL][name], by_rep[Representation.PDF][name]
            own = extraction_status(
                family_has_pair=True,
                xbrl=operand_side(xbrl),
                pdf=operand_side(pdf_value),
                definitions=defs,
                policy=POLICY,
            )
            self.operands[name] = OperandExtraction(
                operand_name=name, xbrl=xbrl, pdf=pdf_value, result=own
            )
        self.pdf_output = output.model_copy(update={"basis": pdf_basis})
        self.xbrl_result = evaluate_inr(
            DICTIONARY, ROUNDING, row, output, by_rep[Representation.XBRL]
        )
        self.pdf_result = evaluate_inr(
            DICTIONARY, ROUNDING, row, self.pdf_output, by_rep[Representation.PDF]
        )

    def status(self, *adjustments: TaggingAdjustment) -> ExtractionResult:
        """The derived extraction status with ``adjustments`` offered."""
        return derived_extraction_status(
            row=self.row,
            output=self.output,
            every_operand_single_representation=False,
            operands=self.operands,
            xbrl=derived_side(self.xbrl_result, self.output),
            pdf=derived_side(self.pdf_result, self.pdf_output),
            adjustments=adjustments,
            definitions=self.defs,
            policy=POLICY,
            rounding=ROUNDING,
            qualification=quarter_context(),
            dictionary=DICTIONARY,
            reporting_currency=INR,
        )


OPEX_XBRL = {
    "total_expenses": "54022.9",
    "finance_costs": "1079.0",
    "depreciation_amortisation": "398.8",
}
# The PDF prints finance costs 10.0 higher, a tagging difference evidenced by FC-1.
OPEX_PDF_FINANCE = {**OPEX_XBRL, "finance_costs": "1089.0"}
PDF_FINANCE_DOWN = TaggingAdjustment(
    operand_name="finance_costs",
    representation=Representation.PDF,
    direction=-1,
    amount=Decimal("10"),
    unit=ValueKind.CURRENCY_AMOUNT,
    definition_record_id="FC-1",
)


def opex_case(pdf_values: Mapping[str, str | None], *records: DefinitionRecord) -> DerivedCase:
    """``opex_excl_finance_and_da`` over the XBRL operands and ``pdf_values``."""
    return DerivedCase(
        DICTIONARY.row("opex_excl_finance_and_da"),
        OPEX,
        OPEX_OPERANDS,
        OPEX_XBRL,
        pdf_values,
        definitions(*records),
    )


REJECTED_ADJUSTMENTS = [
    pytest.param(
        PDF_FINANCE_DOWN.model_copy(update={"unit": ValueKind.PERCENTAGE}),
        ReasonCode.ADJUSTMENT_MISMATCH,
        id="unit-mismatch",
    ),
    pytest.param(
        PDF_FINANCE_DOWN.model_copy(update={"definition_record_id": "TE-1"}),
        ReasonCode.ADJUSTMENT_OUT_OF_SCOPE,
        id="cites-another-operands-record",
    ),
    pytest.param(
        PDF_FINANCE_DOWN.model_copy(update={"amount": Decimal("9")}),
        ReasonCode.ADJUSTMENT_MISMATCH,
        id="amount-differs-from-record",
    ),
    pytest.param(
        PDF_FINANCE_DOWN.model_copy(update={"direction": 1}),
        ReasonCode.ADJUSTMENT_MISMATCH,
        id="direction-away-from-other-side",
    ),
    pytest.param(
        PDF_FINANCE_DOWN.model_copy(update={"definition_record_id": "MISSING"}),
        ReasonCode.ADJUSTMENT_OUT_OF_SCOPE,
        id="record-not-in-pinned-set",
    ),
]


def demonstrated_opex_row() -> DictionaryRow:
    """Constructed qualification metadata for pure table plumbing, not measured evidence."""
    row = DICTIONARY.row("opex_excl_finance_and_da")
    assert row.formula is not None
    scope = QualificationScope(
        scope_id="test-opex-scope",
        schema_identities=frozenset({"in-capmkt"}),
        surfaces=frozenset({"NSE_XBRL_INSTANCE"}),
        bases=frozenset({Basis.CONSOLIDATED}),
        period_kinds=frozenset({PeriodKind.QUARTER}),
        fixture_evidence=tuple(
            QualificationFixture(
                capture_id=f"constructed-table-{index}",
                capture_sha256=f"{index:064x}",
                entity_id=index,
                discriminating=index == 1,
            )
            for index in range(1, 6)
        ),
        sample_rule="constructed five-entity sample for pure decision-table plumbing",
    )
    formula = row.formula.model_copy(update={"tier": DEMONSTRATED, "qualification": scope})
    return row.model_copy(update={"formula": formula})


class ConstructedFormulaHost:
    """A run host over constructed selections: ``values`` holds each canonical id's XBRL and
    PDF crore (``None`` unfiled); ``xbrl_only`` families are packaged with no PDF member."""

    def __init__(
        self,
        values: Mapping[str, tuple[str, str | None]],
        xbrl_only: frozenset[StatementFamily] = frozenset(),
    ) -> None:
        both = (
            member(Representation.XBRL, 1, at(1), at(1)),
            member(Representation.PDF, 2, at(1), at(1)),
        )
        self._values = values
        self._xbrl_only = xbrl_only
        self._paired = package(PACKAGE, *both)
        self._single = package(PACKAGE + 1, both[0])

    def cell(self, key: MeasurementKey, representation: Representation) -> Cell:
        """The constructed value, or an unfiled ``NO_VALUE`` selection."""
        family = DICTIONARY.row(key.canonical_id).family
        owner = self.package(key.entity_id, key.basis, period_end(key.period), family)
        on_pdf = representation is Representation.PDF
        crore = self._values[key.canonical_id][on_pdf]
        if crore is None or representation not in owner.members:
            return Cell(
                selection=bare_selection(key, representation, SourceState.NO_VALUE), attempt_id=None
            )
        chosen = interpretation(
            2 * list(self._values).index(key.canonical_id)
            + 1
            + (representation is Representation.PDF),
            owner.members[representation],
            measurement=key,
            crore=crore,
        )
        selection = KeySelection(
            key=key,
            representation=representation,
            state=SourceState.VALUE,
            interpretation=chosen,
            package_id=owner.package_id,
            source=SelectionSource.PACKAGE_AS_REPORTED,
            reason=None,
            considered_interpretation_ids=(),
            surfaced_restatements=(),
        )
        return Cell(selection=selection, attempt_id=None)

    def resolve(
        self, key: MeasurementKey, role: TemporalRole, *, representation: Representation
    ) -> KeySelection:
        """The key's own selection."""
        return self.cell(key, representation).selection

    def package(
        self, entity_id: int, basis: Basis, end: date, family: StatementFamily
    ) -> FilingPackage:
        """The XBRL-only package for ``xbrl_only`` families, else the paired one."""
        return self._single if family in self._xbrl_only else self._paired

    def member(
        self, package: FilingPackage | None, representation: Representation
    ) -> PackageMember | None:
        """The package's member, if any."""
        return None if package is None else package.members.get(representation)

    def witness(
        self, package: FilingPackage | None, representation: Representation
    ) -> Occurrence | None:
        """No witness occurrence."""
        return None

    def segment_members_of(self, entity_id: int) -> tuple[SegmentMemberRecord, ...]:
        """No segment members."""
        return ()


class MemoryTraces:
    """Traces stored in memory by content hash."""

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}

    def put_calculation_trace(self, trace: CalculationTrace) -> int:
        """The trace's id, assigned on first sight."""
        return self._ids.setdefault(trace.content_sha256(), len(self._ids) + 1)
