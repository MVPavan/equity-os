"""Formula rows of one run: package context, condition evidence, derived extraction (Task 9).

A formula row reads its statement context from its operands' statement families, each through
that family's own selected package (Task 6), never a ``DERIVED`` package walk: a statement
correction reaches the formulas over it. Its qualification conditions are proven only from
the condition keys' own selections under the run's pins and revision rules, exactly as an
operand is read. Each row is evaluated per representation with stored traces (Task 7), and
its extraction status comes from ``derived_extraction_status`` over every operand's own
extraction and the tagging adjustments its evidenced definition records support.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import partial
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.dictionary import DictionaryRow
from fundamentals.canon.formula import OperandValue, operand_from_result, resolve_operand_keys
from fundamentals.compare.definitions import DefinitionScope, DefinitionSet
from fundamentals.compare.engine_rows import (
    MONETARY,
    REPRESENTATIONS,
    Cell,
    Side,
    calculated_side,
    family_has_pair,
    output_context,
    selected_side,
    still_proven,
    with_current_proofs,
)
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.tables import (
    ExtractionResult,
    OperandExtraction,
    TaggingAdjustment,
    derived_extraction_status,
    extraction_status,
)
from fundamentals.contracts.canonical import (
    Basis,
    Representation,
    StatementFamily,
    TemporalRole,
)
from fundamentals.contracts.comparison import ExtractionStatus, SourceState
from fundamentals.contracts.evidence import (
    FilingPackage,
    Interpretation,
    KeySelection,
    Occurrence,
    PackageMember,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey
from fundamentals.contracts.qualification import (
    ProvenCondition,
    QualificationContext,
    QualificationScope,
)
from fundamentals.evidence.alignment import AlignmentProof
from fundamentals.evidence.derived import DerivedSide, TraceStore, evaluate_derived, operand_value
from fundamentals.evidence.interpret import prove_conditions
from fundamentals.evidence.repository import SegmentMemberRecord
from fundamentals.evidence.selection import period_end

# Operands whose own extraction is not one reported pair: no adjustment is offered for them.
_NOT_PAIRED_ROLES = frozenset({TemporalRole.OPENING, TemporalRole.AVERAGE})


class FormulaHost(Protocol):
    """What formula evaluation reads from the run engine (all decided under the run's pins)."""

    def cell(self, key: MeasurementKey, representation: Representation) -> Cell:
        """One reported key's state in one representation."""
        ...

    def resolve(
        self, key: MeasurementKey, role: TemporalRole, *, representation: Representation
    ) -> KeySelection:
        """A formula operand's selection."""
        ...

    def package(
        self, entity_id: int, basis: Basis, end: date, family: StatementFamily
    ) -> FilingPackage | None:
        """The package supplying one statement family for one period end."""
        ...

    def member(
        self, package: FilingPackage | None, representation: Representation
    ) -> PackageMember | None:
        """A package's member on a requested source, if any."""
        ...

    def witness(
        self, package: FilingPackage | None, representation: Representation
    ) -> Occurrence | None:
        """The member capture's witness occurrence under the pinned extractor."""
        ...

    def segment_members_of(self, entity_id: int) -> tuple[SegmentMemberRecord, ...]:
        """The entity's segment members recorded by the cutoff."""
        ...


class FormulaEvaluation(BaseModel):
    """One formula key evaluated in both representations, with its extraction result."""

    model_config = ConfigDict(frozen=True)

    sides: dict[Representation, Side]
    results: dict[Representation, DerivedSide]
    extraction: ExtractionResult


class FormulaRows:
    """Evaluate formula keys once each (nested formulas reuse their own evaluation)."""

    def __init__(
        self,
        host: FormulaHost,
        *,
        config: LoadedConfig,
        traces: TraceStore,
        proofs: tuple[AlignmentProof, ...],
    ) -> None:
        self._host = host
        self._config = config
        self._traces = traces
        self._proofs = proofs
        self._rows = {row.canonical_id: row for row in config.dictionary.rows}
        self._evaluated: dict[tuple[str, bool], FormulaEvaluation] = {}
        self.bound_member_ids: set[int] = set()
        self.selected_condition_ids: set[int] = set()

    def families(self, row: DictionaryRow) -> frozenset[StatementFamily]:
        """The statement families of a formula's reported (leaf) operands."""
        return frozenset(self._leaf_families(row))

    def package(self, row: DictionaryRow, key: MeasurementKey) -> FilingPackage | None:
        """The package of the formula's first leaf operand family (its output's own context)."""
        family = self._leaf_families(row)[0]
        return self._host.package(key.entity_id, key.basis, period_end(key.period), family)

    def evaluate(
        self,
        row: DictionaryRow,
        key: MeasurementKey,
        *,
        fiscal_month: int,
        currency: str | None,
        shared: bool = False,
    ) -> FormulaEvaluation:
        """Both representations' traced values and the derived extraction result.

        ``shared`` evaluates a nested operand as its parent did: sharing single-representation
        operands even when every one of its own is single-representation.
        """
        package = self.package(row, key)
        package_id = None if package is None else package.package_id
        # Every operand single-representation: NOT_APPLICABLE, and nothing is shared into a
        # representation the filing lacks.
        single = all(
            self._sole_representation(leaf) is not None
            for leaf in self._leaf_keys(row, key, currency)
        )
        shared = shared or not single
        digest = (key.digest(), shared)
        if digest in self._evaluated:
            return self._evaluated[digest]
        resolve = partial(self._operand, shared=shared)
        results: dict[Representation, DerivedSide] = {}
        sides: dict[Representation, Side] = {}
        contexts = {}
        for rep in REPRESENTATIONS:
            context_for = partial(
                self.qualification_for,
                representation=rep,
                fiscal_month=fiscal_month,
                currency=currency,
            )
            contexts[rep] = context_for(row, key)
            results[rep] = evaluate_derived(
                row,
                key,
                representation=rep,
                resolve=partial(resolve, representation=rep),
                proofs=self._proofs,
                qualification=contexts[rep],
                qualification_for=context_for,
                fiscal_year_end_month=fiscal_month,
                policy=self._config.rounding,
                repository=self._traces,
                dictionary=self._config.dictionary,
                reporting_currency=currency,
                segment_members=self._host.segment_members_of(key.entity_id),
            )
            self.bound_member_ids.update(results[rep].bound_member_ids)
            sides[rep] = calculated_side(
                results[rep].result,
                key=key,
                representation=rep,
                trace_id=results[rep].trace_id,
                package_id=package_id,
            )
        operands = (
            None
            if single
            else self._operand_extractions(row, key, fiscal_month=fiscal_month, currency=currency)
        )
        definitions = self._config.definition_set
        extraction = derived_extraction_status(
            row=row,
            output=key,
            every_operand_single_representation=single,
            operands=operands or {},
            xbrl=sides[Representation.XBRL].comparison,
            pdf=sides[Representation.PDF].comparison,
            adjustments=() if operands is None else tagging_adjustments(operands, definitions),
            definitions=definitions,
            policy=self._config.comparison_policy,
            rounding=self._config.rounding,
            qualification=contexts[Representation.XBRL],
            dictionary=self._config.dictionary,
            reporting_currency=currency,
        )
        evaluation = FormulaEvaluation(sides=sides, results=results, extraction=extraction)
        self._evaluated[digest] = evaluation
        return evaluation

    def qualification_for(
        self,
        row: DictionaryRow,
        key: MeasurementKey,
        *,
        representation: Representation,
        fiscal_month: int,
        currency: str | None,
    ) -> QualificationContext:
        """The actual formula key's selected statement package and pinned conditions.

        Nested formulas can have another period, basis or statement family. Derivation
        requests this context at each recursion level rather than inheriting its parent's.
        """
        package = self.package(row, key)
        return output_context(
            row,
            key,
            self._host.member(package, representation),
            representation=representation,
            witness=self._host.witness(package, representation),
            interpretations=self.condition_evidence(
                row.formula.qualification if row.formula is not None else None,
                key,
                representation,
                currency,
            ),
            fiscal_month=fiscal_month,
        )

    def revalidated(self, side: Side, key: MeasurementKey, rep: Representation) -> Side:
        """A reported side whose stored condition proofs are re-proven under the run."""
        own = side.comparison
        if not own.condition_evidence or not own.mapping_entry_ids:
            return side
        proven = self._proven(own.mapping_entry_ids[0], key, rep)
        return side.model_copy(update={"comparison": with_current_proofs(own, proven)})

    def _proven(
        self, entry_id: str, key: MeasurementKey, rep: Representation
    ) -> Mapping[str, ProvenCondition]:
        """A mapping entry's conditions proven from the run's current condition selections."""
        scope = self._config.mapping_set.entry(entry_id).qualification
        conditions = () if scope is None else (*scope.conditions, *scope.exclusions)
        evidence = self.condition_evidence(scope, key, rep, key.currency)
        return prove_conditions(
            conditions, interpretations=evidence, period=key.period, basis=key.basis
        )

    def _operand(
        self,
        key: MeasurementKey,
        role: TemporalRole,
        *,
        representation: Representation,
        shared: bool,
    ) -> KeySelection:
        """An operand's selection, its stored qualification re-proven as a reported side's is.

        When shared, a single-representation family's selection is shared (spec §5).
        """
        if shared:
            representation = self._sole_representation(key) or representation
        selection = self._host.resolve(key, role, representation=representation)
        chosen = selection.interpretation
        if chosen is None or not chosen.condition_evidence or chosen.mapping_entry_id is None:
            return selection
        proven = self._proven(chosen.mapping_entry_id, key, selection.representation)
        if still_proven(chosen.condition_evidence, proven):
            return selection
        unproven = {
            "tier": EvidenceTier.EQUIVALENCE_UNPROVEN,
            "qualification_ref": None,
            "condition_evidence": (),
        }
        return selection.model_copy(update={"interpretation": chosen.model_copy(update=unproven)})

    def _sole_representation(self, key: MeasurementKey) -> Representation | None:
        """A reported key's only representation when its family has no paired one (table row 1).

        A representation that was attempted (even failed) still pairs, unlike one never attempted.
        """
        family = self._rows[key.canonical_id].family
        package = self._host.package(key.entity_id, key.basis, period_end(key.period), family)
        cells = {rep: self._host.cell(key, rep) for rep in REPRESENTATIONS}
        if package is None or family_has_pair(package, cells):
            return None
        return next(rep for rep in REPRESENTATIONS if rep in package.members)

    def _leaf_keys(
        self, row: DictionaryRow, key: MeasurementKey, currency: str | None
    ) -> list[MeasurementKey]:
        """Every reported operand key under a formula key: nested, aggregated and role keys."""
        assert row.formula is not None
        found: list[MeasurementKey] = []
        for operand in row.formula.operands:
            nested = self._rows[operand.canonical_id]
            for operand_key in resolve_operand_keys(
                key, operand, dictionary=self._config.dictionary, reporting_currency=currency
            ):
                found += (
                    self._leaf_keys(nested, operand_key, currency)
                    if nested.formula
                    else [operand_key]
                )
        return found

    def _leaf_families(self, row: DictionaryRow) -> list[StatementFamily]:
        """Leaf operand families in formula order, depth first, each once."""
        assert row.formula is not None
        found: list[StatementFamily] = []
        for operand in row.formula.operands:
            nested = self._rows[operand.canonical_id]
            for family in self._leaf_families(nested) if nested.formula else [nested.family]:
                if family not in found:
                    found.append(family)
        return found

    def condition_evidence(
        self,
        scope: QualificationScope | None,
        key: MeasurementKey,
        rep: Representation,
        currency: str | None,
    ) -> list[Interpretation]:
        """Each condition key's selected interpretation under the pins, when it holds a value."""
        if scope is None:
            return []
        found = []
        for condition in (*scope.conditions, *scope.exclusions):
            condition_row = self._rows.get(condition.canonical_id)
            if condition_row is None:
                continue
            condition_key = MeasurementKey(
                entity_id=key.entity_id,
                canonical_id=condition.canonical_id,
                period=key.period,
                basis=key.basis,
                framework=key.framework,
                currency=currency if condition_row.value_kind in MONETARY else None,
                value_kind=condition_row.value_kind,
                dimensions=DimensionSet(),
            )
            selection = self._host.cell(condition_key, rep).selection
            if selection.state is SourceState.VALUE and selection.interpretation is not None:
                found.append(selection.interpretation)
                if selection.interpretation.interpretation_id is not None:
                    self.selected_condition_ids.add(selection.interpretation.interpretation_id)
        return found

    def _operand_extractions(
        self, row: DictionaryRow, key: MeasurementKey, *, fiscal_month: int, currency: str | None
    ) -> dict[str, OperandExtraction] | None:
        """Every operand's two values, shared as evaluated, and own extraction; ``None`` if one is
        not a plain pair.

        Aggregated, opening and averaged operands are not one reported pair, so a formula
        holding one is compared without adjustments.
        """
        assert row.formula is not None
        found: dict[str, OperandExtraction] = {}
        for operand in row.formula.operands:
            if operand.aggregation is not None or operand.temporal_role in _NOT_PAIRED_ROLES:
                return None
            (operand_key,) = resolve_operand_keys(
                key, operand, dictionary=self._config.dictionary, reporting_currency=currency
            )
            nested = self._rows[operand.canonical_id]
            if nested.formula is not None:
                inner = self.evaluate(
                    nested, operand_key, fiscal_month=fiscal_month, currency=currency, shared=True
                )
                values = {
                    rep: _computed(inner.results[rep], operand_key) for rep in REPRESENTATIONS
                }
                own = inner.extraction
            else:
                end = period_end(operand_key.period)
                package = self._host.package(key.entity_id, key.basis, end, nested.family)
                package_id = None if package is None else package.package_id
                cells = {rep: self._host.cell(operand_key, rep) for rep in REPRESENTATIONS}
                sole = self._sole_representation(operand_key)
                values = {
                    rep: operand_value(cells[sole or rep].selection, proofs=self._proofs)
                    for rep in REPRESENTATIONS
                }
                read = {
                    rep: selected_side(
                        cells[rep], rep, proofs=self._proofs, package_id=package_id
                    ).comparison
                    for rep in REPRESENTATIONS
                }
                own = extraction_status(
                    family_has_pair=family_has_pair(package, cells),
                    xbrl=read[Representation.XBRL],
                    pdf=read[Representation.PDF],
                    definitions=self._config.definition_set,
                    policy=self._config.comparison_policy,
                )
            found[operand.name] = OperandExtraction(
                operand_name=operand.name,
                xbrl=values[Representation.XBRL],
                pdf=values[Representation.PDF],
                result=own,
            )
        return found


def tagging_adjustments(
    operands: Mapping[str, OperandExtraction], definitions: DefinitionSet
) -> tuple[TaggingAdjustment, ...]:
    """The adjustment each operand's own tagging difference evidences, by its record.

    The record's amount moves one representation toward the other: the representation whose
    mapping entry a ``MAPPING`` record names, otherwise the PDF (XBRL is the representative
    side). ``derived_extraction_status`` validates every adjustment again before applying it.
    """
    found = []
    for name, operand in operands.items():
        own = operand.result
        if (
            own.status is not ExtractionStatus.TAGGING_DIFFERENCE
            or own.pair is None
            or own.pair.definition_record_id is None
        ):
            continue
        record = definitions.record(own.pair.definition_record_id)
        if record is None:
            continue
        named_xbrl = (
            record.scope is DefinitionScope.MAPPING
            and record.scope_ref == operand.xbrl.mapping_entry_id
        )
        rep = Representation.XBRL if named_xbrl else Representation.PDF
        named = operand.side(rep)
        other = operand.xbrl if rep is Representation.PDF else operand.pdf
        if named.exact is None or other.exact is None or named.exact == other.exact:
            continue
        found.append(
            TaggingAdjustment(
                operand_name=name,
                representation=rep,
                direction=1 if other.exact > named.exact else -1,
                amount=record.explained_amount,
                unit=record.unit,
                definition_record_id=record.record_id,
            )
        )
    return tuple(found)


def _computed(side: DerivedSide, key: MeasurementKey) -> OperandValue:
    """A nested formula's stored result as its parent's operand."""
    value = operand_from_result(side.result, key=key, selection_source=None)
    return value.model_copy(update={"calculation_trace_id": side.trace_id})
