"""Per-run resolution over loaded inputs: context, attempt states, selection, derivation.

Pure over ``ResolvedInputs``: the same inputs, request and config give the same result rows,
so execution and replay share this code. The only side effect is through the injected trace
store (the repository when a run executes; a read-only index of the run's own traces when it
replays). Order, per (entity, basis, period end):

1. Context before any value: the package per statement family (a formula row's: its leaf
   operands' families), the fiscal calendar, the basis status and segment evidence decide
   applicability per row (``decide_applicability``). Only members on the scope's requested
   sources (first-party surfaces) are read.
2. Attempt-to-state before presence: the latest available generation under the pinned
   extractor (or a failed acquisition with no member) decides a representation and family.
3. Selection under the pins (Task 6), alignment-scoped tiers and derived evaluation (Task 7).
4. A ``YEAR`` package also yields Q4 = FY − 9M for every additive duration amount, stored as
   its own ``DERIVED`` row and paired with the reported Q4, never merged.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from fundamentals.canon.applicability import (
    REPORTING_KINDS,
    ApplicabilityContext,
    ApplicabilityDecision,
    decide_applicability,
)
from fundamentals.canon.dictionary import DictionaryRow, PeriodAggregationKind
from fundamentals.canon.period_aggregation import (
    AggregationOperand,
    PeriodDerivation,
    derive_period_value,
)
from fundamentals.compare.engine_attempts import (
    AttemptStates,
    RunResolutionError,
    bare_selection,
    fiscal_periods,
    nine_months,
    pdf_contexts_conflict,
)
from fundamentals.compare.engine_context import (
    basis_status,
    fiscal_year_end,
    segment_bases,
    segment_members,
)
from fundamentals.compare.engine_formula import FormulaRows
from fundamentals.compare.engine_rows import (
    MONETARY,
    REPRESENTATIONS,
    Cell,
    Side,
    as_counterpart,
    calculated_side,
    not_applicable_row,
    pair_record,
    pairable,
    ref,
    representative,
    selected_side,
    sorted_values,
)
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import (
    PairRecord,
    ResultRow,
    RunRequest,
    SourceRole,
    row_id,
)
from fundamentals.compare.tables import (
    ExtractionResult,
    corroboration_status,
    extraction_status,
    pair_outcome,
)
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    DocumentType,
    PeriodKind,
    PeriodNature,
    ReportingRegime,
    Representation,
    StatementFamily,
    TemporalRole,
    ValueIdentity,
    ValueKind,
)
from fundamentals.contracts.comparison import (
    PairKind,
    SourceState,
)
from fundamentals.contracts.evidence import (
    EligibilityBoundary,
    FilingFamily,
    FilingPackage,
    Interpretation,
    InterpretationStatus,
    KeySelection,
    Occurrence,
    PackageMember,
    RunMode,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.derived import TraceStore, operand_value
from fundamentals.evidence.repository import SegmentMemberRecord
from fundamentals.evidence.selection import (
    differing_restatement,
    period_end,
    select_key,
    select_package,
)

__all__ = ["REPRESENTATIONS", "RUN_FAMILY", "RUN_FRAMEWORK", "RunEngine"]

RUN_FRAMEWORK = AccountingFramework.IND_AS
RUN_FAMILY = FilingFamily.FINANCIAL_RESULTS
_OUTSIDE_RESULTS = frozenset({StatementFamily.SHAREHOLDING})
OPENING_NOT_RESOLVED = "OPENING_NOT_RESOLVED"
SOURCE_NOT_REQUESTED = "SOURCE_NOT_REQUESTED"
_KINDS = "statement families {families} come from packages of reporting kinds {kinds}"
_CURRENCY = "entity {entity_id} period {period_end}: evidenced reporting currencies {found}"
_DUPLICATE_ROWS = "row ids repeat within one run: {ids}"

Key = tuple[str, Representation]


class RunEngine:
    """Resolve one request's result rows from its loaded inputs (see module docstring)."""

    def __init__(
        self,
        inputs: ResolvedInputs,
        request: RunRequest,
        *,
        config: LoadedConfig,
        traces: TraceStore,
    ) -> None:
        self._inputs = inputs
        self._request = request
        self._config = config
        self._traces = traces
        self._cutoff = request.cutoff
        self._boundary = EligibilityBoundary.at(request.cutoff)
        self._triple = request.pinned.triple()
        self._surfaces = frozenset(request.scope.sources)
        self._rows = {row.canonical_id: row for row in config.dictionary.rows}
        self._occurrences: dict[int, Occurrence] = {}
        self._witness_occurrence: dict[int, Occurrence] = {}
        for occurrence in inputs.occurrences:
            assert occurrence.occurrence_id is not None
            self._occurrences[occurrence.occurrence_id] = occurrence
            capture = occurrence.capture.capture_ref_id or 0
            if occurrence.extractor_version == self._triple.extractor(occurrence.representation):
                held = self._witness_occurrence.get(capture)
                if held is None or (held.occurrence_id or 0) > occurrence.occurrence_id:
                    self._witness_occurrence[capture] = occurrence
        self._by_capture: dict[int, list[Interpretation]] = defaultdict(list)
        self._by_digest: dict[str, list[Interpretation]] = defaultdict(list)
        for item in sorted(inputs.interpretations, key=lambda row: row.interpretation_id or 0):
            self._by_capture[item.capture_ref_id].append(item)
            if item.key is not None:
                digest = item.key.digest()
                self._by_digest[digest].append(item)
        self._member_of: dict[int, list[FilingPackage]] = defaultdict(list)
        for package in inputs.packages:
            for member in package.members.values():
                if member.capture.surface in self._surfaces:
                    self._member_of[member.capture.capture_ref_id or 0].append(package)
        self._proofs = inputs.proofs
        self._attempt_states = AttemptStates(
            inputs.attempts,
            member_captures=self._member_of,
            cutoff=request.cutoff,
            mode=request.mode,
            triple=self._triple,
            surfaces=self._surfaces,
        )
        self._package_cache: dict[tuple[int, Basis, date, StatementFamily], FilingPackage | None]
        self._package_cache = {}
        self._cells: dict[Key, Cell] = {}
        self._reported_sides: dict[str, dict[Representation, Side]] = {}
        self._formulas = FormulaRows(self, config=config, traces=traces, proofs=inputs.proofs)
        self.selected_package_ids: set[int] = set()

    @property
    def bound_segment_member_ids(self) -> set[int]:
        """Segment-member records an entity-bound aggregation bound."""
        return self._formulas.bound_member_ids

    @property
    def selected_condition_ids(self) -> set[int]:
        """Pinned interpretations consulted for formula qualification conditions."""
        return self._formulas.selected_condition_ids

    def rows(self) -> tuple[ResultRow, ...]:
        """Every result row of the request, sorted by row id."""
        rows: list[ResultRow] = []
        for entity_id, basis, end in self._groups():
            rows.extend(self._group_rows(entity_id, basis, end))
        ids = [row.row_id for row in rows]
        repeated = sorted({item for item in ids if ids.count(item) > 1})
        if repeated:
            raise RunResolutionError(_DUPLICATE_ROWS.format(ids=repeated[:5]))
        return tuple(sorted(rows, key=lambda row: row.row_id))

    def package_selections(
        self,
    ) -> list[tuple[FilingPackage, dict[Key, KeySelection]]]:
        """Every selected package with its reported keys' selections (for alignment proofs)."""
        found: dict[int, tuple[FilingPackage, dict[Key, KeySelection]]] = {}
        for entity_id, basis, end in self._groups():
            periods = fiscal_periods(end, self._fiscal_year_end(entity_id))
            currency = self._currency(entity_id, basis, end)
            for row in self._result_rows():
                if row.formula is not None:
                    continue
                package = self.package(entity_id, basis, end, row.family)
                if package is None or package.package_id is None:
                    continue
                entry = found.setdefault(package.package_id, (package, {}))
                for key in self._keys(row, entity_id, basis, end, periods, currency):
                    for representation in REPRESENTATIONS:
                        selection = self.cell(key, representation).selection
                        entry[1][(key.digest(), representation)] = selection
        return [found[package_id] for package_id in sorted(found)]

    def comparative_digests(self) -> set[str]:
        """Digests of every reported key the run selects, Q4 operands included."""
        found: set[str] = set()
        for entity_id, basis, end in self._groups():
            periods = fiscal_periods(end, self._fiscal_year_end(entity_id))
            currency = self._currency(entity_id, basis, end)
            for row in self._result_rows():
                if row.formula is not None:
                    continue
                for key in self._keys(row, entity_id, basis, end, periods, currency):
                    found.add(key.digest())
                    if len(periods) == 2 and key.period == periods[0]:
                        nine = nine_months(periods)
                        found.add(key.model_copy(update={"period": nine}).digest())
        return found

    def _groups(self) -> Iterable[tuple[int, Basis, date]]:
        """Every (entity, basis, period end) of the scope."""
        scope = self._request.scope
        for entity_id in scope.entity_ids:
            for basis in scope.bases:
                for end in scope.period_ends:
                    yield entity_id, basis, end

    def _result_rows(self) -> Iterable[DictionaryRow]:
        """Dictionary rows a results run reports: current rows outside shareholding."""
        for row in self._config.dictionary.rows:
            if row.family not in _OUTSIDE_RESULTS and row.deprecated_by is None:
                yield row

    def _group_rows(self, entity_id: int, basis: Basis, end: date) -> list[ResultRow]:
        """Every row of one (entity, basis, period end)."""
        fiscal_month = self._fiscal_year_end(entity_id)
        periods = fiscal_periods(end, fiscal_month)
        currency = self._currency(entity_id, basis, end)
        contexts: dict[frozenset[StatementFamily], ApplicabilityContext] = {}
        rows: list[ResultRow] = []
        for row in self._result_rows():
            families = (
                frozenset({row.family}) if row.formula is None else self._formulas.families(row)
            )
            if families not in contexts:
                contexts[families] = self._context(entity_id, basis, end, families, periods)
            for key in self._keys(row, entity_id, basis, end, periods, currency):
                decision = decide_applicability(row, contexts[families])
                if row.formula is not None:
                    rows.append(self._derived_row(row, key, decision, fiscal_month, currency))
                    continue
                reported = self._reported_row(row, key, decision)
                rows.append(reported)
                if self._derives_q4(row, key, decision, periods):
                    rows.append(self._q4_row(row, key, periods, reported))
        return rows

    def _keys(
        self,
        row: DictionaryRow,
        entity_id: int,
        basis: Basis,
        end: date,
        periods: tuple[PeriodInterval, ...],
        currency: str,
    ) -> list[MeasurementKey]:
        """The row's keys: each fiscal period (or the instant), each evidenced member set."""
        chosen = (
            periods if row.period_nature is PeriodNature.DURATION else (PeriodInterval.at(end),)
        )
        keys = []
        for period in chosen:
            dimension_sets = (
                [DimensionSet()]
                if row.dimension_template is None
                else self._evidence_dimensions(row, entity_id, basis, end, period)
            )
            for dimensions in dimension_sets:
                keys.append(
                    MeasurementKey(
                        entity_id=entity_id,
                        canonical_id=row.canonical_id,
                        period=period,
                        basis=basis,
                        framework=RUN_FRAMEWORK,
                        currency=currency if row.value_kind in MONETARY else None,
                        value_kind=row.value_kind,
                        dimensions=dimensions,
                    )
                )
        return keys

    def _evidence_dimensions(
        self, row: DictionaryRow, entity_id: int, basis: Basis, end: date, period: PeriodInterval
    ) -> list[DimensionSet]:
        """Member sets the selected package evidences for a dimensioned row and period.

        A formula row takes its operands' member sets (an aggregated operand's axis becomes
        its output member). Members are never invented: no evidence, no dimensioned key.
        """
        found: set[DimensionSet] = set()
        if row.formula is None:
            package = self.package(entity_id, basis, end, row.family)
            for representation in REPRESENTATIONS:
                for item in self._member_interpretations(package, representation):
                    if (
                        self._current_triple(item)
                        and item.canonical_id == row.canonical_id
                        and item.period == period
                        and item.basis is basis
                        and item.dimensions is not None
                        and item.dimensions.pairs
                    ):
                        found.add(item.dimensions)
            return sorted(found, key=lambda dimensions: dimensions.pairs)
        for operand in row.formula.operands:
            if operand.temporal_role in (TemporalRole.OPENING, TemporalRole.AVERAGE):
                continue
            operand_row = self._rows[operand.canonical_id]
            if operand_row.dimension_template is None:
                continue
            operand_period = (
                PeriodInterval.at(end) if operand.temporal_role is TemporalRole.CLOSING else period
            )
            for dimensions in self._evidence_dimensions(
                operand_row, entity_id, basis, end, operand_period
            ):
                if operand.aggregation is not None:
                    members = dict(dimensions.pairs)
                    members[operand.aggregation.axis] = operand.aggregation.output_member
                    dimensions = DimensionSet.of(members)
                found.add(dimensions)
        return sorted(found, key=lambda dimensions: dimensions.pairs)

    def _context(
        self,
        entity_id: int,
        basis: Basis,
        end: date,
        families: frozenset[StatementFamily],
        periods: tuple[PeriodInterval, ...],
    ) -> ApplicabilityContext:
        """What the families' selected packages tell before any value is read."""
        selected = (self.package(entity_id, basis, end, family) for family in sorted(families))
        packages = [package for package in selected if package is not None]
        fiscal_month = self._fiscal_year_end(entity_id)
        kinds = sorted({package.reporting_kind for package in packages})
        if len(kinds) > 1:
            raise RunResolutionError(_KINDS.format(families=sorted(families), kinds=kinds))
        kind = kinds[0] if kinds else periods[-1].kind(fiscal_month)
        if kind not in REPORTING_KINDS:
            raise RunResolutionError(f"package reporting kind {kind} is not a reporting kind")
        disclosed = {
            item.key.canonical_id
            for package in packages
            for representation in REPRESENTATIONS
            for item in self._member_interpretations(package, representation)
            if item.key is not None
            and item.status is InterpretationStatus.MAPPED
            and self._current_triple(item)
        }
        present: set[StatementFamily] = set()
        for package in packages:
            present.update(package.statements_present)
        return ApplicabilityContext(
            regime=ReportingRegime.IN_LODR,
            document_type=DocumentType.FINANCIAL_RESULTS,
            statements_present=frozenset(present),
            period_kind=kind,
            requested_basis=basis,
            entity_basis_status=basis_status(self._inputs.basis_statuses, entity_id, self._cutoff),
            evidenced_segment_bases=segment_bases(
                self.segment_members_of(entity_id), self._occurrences
            ),
            disclosed_rows=frozenset(disclosed),
        )

    def _fiscal_year_end(self, entity_id: int) -> int:
        """The fiscal-year-end month recorded latest by the cutoff."""
        return fiscal_year_end(self._inputs.settings, entity_id, self._cutoff)

    def segment_members_of(self, entity_id: int) -> tuple[SegmentMemberRecord, ...]:
        """The entity's segment members recorded by the cutoff."""
        return segment_members(self._inputs.segment_members, entity_id, self._cutoff)

    def _currency(self, entity_id: int, basis: Basis, end: date) -> str:
        """The one reporting currency the eligible packages' monetary lines evidence."""
        found = {
            item.key.currency
            for package in self._inputs.packages
            if self._in_group(package, entity_id, basis, end)
            for member in package.members.values()
            if member.capture.surface in self._surfaces
            for item in self._by_capture.get(member.capture.capture_ref_id or 0, ())
            if item.key is not None
            and item.key.value_kind is ValueKind.CURRENCY_AMOUNT
            and item.key.currency is not None
            and (self._request.mode is RunMode.RETROSPECTIVE or item.recorded_at <= self._cutoff)
        }
        if len(found) != 1:
            raise RunResolutionError(
                _CURRENCY.format(entity_id=entity_id, period_end=end, found=sorted(found))
            )
        return str(next(iter(found)))

    def _in_group(self, package: FilingPackage, entity_id: int, basis: Basis, end: date) -> bool:
        """Whether a package is an eligible results package of one group."""
        return (
            package.entity_id == entity_id
            and package.basis is basis
            and package.framework is RUN_FRAMEWORK
            and package.family is RUN_FAMILY
            and package.reporting_period_end == end
            and package.eligible(self._boundary)
        )

    def package(
        self, entity_id: int, basis: Basis, end: date, family: StatementFamily
    ) -> FilingPackage | None:
        """The package supplying one statement family for one period end (Task 6)."""
        cache_key = (entity_id, basis, end, family)
        if cache_key not in self._package_cache:
            package = select_package(
                [
                    candidate
                    for candidate in self._inputs.packages
                    if any(
                        member.capture.surface in self._surfaces
                        for member in candidate.members.values()
                    )
                ],
                entity_id=entity_id,
                family=RUN_FAMILY,
                statement_family=family,
                basis=basis,
                framework=RUN_FRAMEWORK,
                period_end=end,
                boundary=self._boundary,
            )
            self._package_cache[cache_key] = package
            if package is not None and package.package_id is not None:
                self.selected_package_ids.add(package.package_id)
        return self._package_cache[cache_key]

    def member(
        self, package: FilingPackage | None, representation: Representation
    ) -> PackageMember | None:
        """A package's member for one representation, if it is on a requested source."""
        found = None if package is None else package.members.get(representation)
        return found if found is not None and found.capture.surface in self._surfaces else None

    def witness(
        self, package: FilingPackage | None, representation: Representation
    ) -> Occurrence | None:
        """The member capture's witness occurrence under the pinned extractor, if any."""
        member = self.member(package, representation)
        if member is None:
            return None
        return self._witness_occurrence.get(member.capture.capture_ref_id or 0)

    def _member_interpretations(
        self, package: FilingPackage | None, representation: Representation
    ) -> list[Interpretation]:
        """Every loaded interpretation of a package member capture."""
        member = self.member(package, representation)
        if member is None:
            return []
        return self._by_capture.get(member.capture.capture_ref_id or 0, [])

    def _current_triple(self, item: Interpretation) -> bool:
        """Under the pinned triple and, in ``AS_KNOWN``, recorded by the cutoff."""
        return (
            item.mapping_set_version == self._triple.mapping_set
            and item.normalisation_policy_version == self._triple.normalisation_policy
            and item.extractor_version == self._triple.extractor(item.representation)
            and (self._request.mode is RunMode.RETROSPECTIVE or item.recorded_at <= self._cutoff)
        )

    def cell(self, key: MeasurementKey, representation: Representation) -> Cell:
        """One key's state in one representation: attempt-to-state first, then selection."""
        cache_key = (key.digest(), representation)
        if cache_key in self._cells:
            return self._cells[cache_key]
        end = period_end(key.period)
        family = self._rows[key.canonical_id].family
        package = self.package(key.entity_id, key.basis, end, family)
        decided = self._attempt_states.state(key, representation, family, package)
        if decided is None:
            decided = Cell(selection=self._select(key, representation, package), attempt_id=None)
        self._cells[cache_key] = decided
        return decided

    def _select(
        self, key: MeasurementKey, representation: Representation, package: FilingPackage | None
    ) -> KeySelection:
        """Selection under the pins; a member on an unrequested source is never read."""
        member = self.member(package, representation)
        if member is None and package is not None and representation in package.members:
            return bare_selection(
                key,
                representation,
                SourceState.NO_VALUE,
                package=package,
                reason=SOURCE_NOT_REQUESTED,
            )
        capture = None if member is None else (member.capture.capture_ref_id or 0)
        witness_occurrence = None if capture is None else self._witness_occurrence.get(capture)
        # Selection needs full capture history for cross-key revisions and partial INVALID keys.
        candidates = [] if capture is None else self._by_capture.get(capture, [])
        return select_key(
            key,
            representation,
            package=package,
            occurrences=() if witness_occurrence is None else (witness_occurrence,),
            interpretations=candidates,
            boundary=self._boundary,
            mode=self._request.mode,
            pinned=self._triple,
        )

    def resolve(
        self, key: MeasurementKey, role: TemporalRole, *, representation: Representation
    ) -> KeySelection:
        """A derived operand's selection; opening balances fail closed in D1a."""
        if role is TemporalRole.OPENING:
            return bare_selection(
                key, representation, SourceState.UNAVAILABLE, reason=OPENING_NOT_RESOLVED
            )
        return self.cell(key, representation).selection

    def _comparatives(self, key: MeasurementKey) -> list[Interpretation]:
        """The current comparative of this key in each eligible other-period package."""
        end = period_end(key.period)
        by_capture: dict[int, list[Interpretation]] = defaultdict(list)
        for item in self._by_digest.get(key.digest(), ()):
            packages = self._member_of.get(item.capture_ref_id, ())
            if any(
                package.reporting_period_end != end
                and package.entity_id == key.entity_id
                and package.basis is key.basis
                and package.eligible(self._boundary)
                for package in packages
            ):
                by_capture[item.capture_ref_id].append(item)
        found = []
        for capture in sorted(by_capture):
            representation = by_capture[capture][0].representation
            if representation is Representation.PDF and pdf_contexts_conflict(
                self._inputs.attempts,
                capture_ref_id=capture,
                cutoff=self._cutoff,
                mode=self._request.mode,
                extractor=self._triple.extractor(representation),
            ):
                continue
            package = next(
                package
                for package in self._member_of[capture]
                if package.reporting_period_end != end
                and package.entity_id == key.entity_id
                and package.basis is key.basis
                and package.eligible(self._boundary)
            )
            witness = self._witness_occurrence.get(capture)
            selected = select_key(
                key,
                representation,
                package=package,
                occurrences=() if witness is None else (witness,),
                interpretations=self._by_capture[capture],
                boundary=self._boundary,
                mode=self._request.mode,
                pinned=self._triple,
            )
            if selected.state is SourceState.VALUE and selected.interpretation is not None:
                found.append(selected.interpretation)
        return found

    def _surfaced(self, cell: Cell) -> tuple[int, ...]:
        """Comparatives whose interval misses the selected interval (Task 6)."""
        return differing_restatement(cell.selection, self._comparatives(cell.selection.key))

    def _reported_row(
        self, row: DictionaryRow, key: MeasurementKey, decision: ApplicabilityDecision
    ) -> ResultRow:
        """A reported row: both representations, extraction and corroboration."""
        if decision.status is ApplicabilityStatus.NOT_APPLICABLE:
            return not_applicable_row(
                key, ValueIdentity.REPORTED, decision, self._config.dictionary.version
            )
        package = self.package(key.entity_id, key.basis, period_end(key.period), row.family)
        package_id = None if package is None else package.package_id
        cells = {rep: self.cell(key, rep) for rep in REPRESENTATIONS}
        sides = {
            rep: selected_side(cells[rep], rep, proofs=self._proofs, package_id=package_id)
            for rep in REPRESENTATIONS
        }
        self._reported_sides[key.digest()] = sides
        surfaced = sorted({item for cell in cells.values() for item in self._surfaced(cell)})
        return self._compared(key, ValueIdentity.REPORTED, decision, sides, surfaced=surfaced)

    def _derived_row(
        self,
        row: DictionaryRow,
        key: MeasurementKey,
        decision: ApplicabilityDecision,
        fiscal_month: int,
        currency: str,
    ) -> ResultRow:
        """A formula row evaluated per representation with stored traces (Task 7)."""
        if decision.status is ApplicabilityStatus.NOT_APPLICABLE:
            return not_applicable_row(
                key, ValueIdentity.DERIVED, decision, self._config.dictionary.version
            )
        evaluated = self._formulas.evaluate(row, key, fiscal_month=fiscal_month, currency=currency)
        return self._compared(
            key,
            ValueIdentity.DERIVED,
            decision,
            evaluated.sides,
            surfaced=[],
            extraction=evaluated.extraction,
        )

    def _derives_q4(
        self,
        row: DictionaryRow,
        key: MeasurementKey,
        decision: ApplicabilityDecision,
        periods: tuple[PeriodInterval, ...],
    ) -> bool:
        """Whether a reported row also gets Q4 = FY − 9M (a ``YEAR`` package's quarter)."""
        if (
            len(periods) != 2
            or key.period != periods[0]
            or decision.status is not ApplicabilityStatus.APPLICABLE
            or row.period_aggregation is not PeriodAggregationKind.ADDITIVE_DURATION
            or row.period_nature is not PeriodNature.DURATION
            or row.value_kind is not ValueKind.CURRENCY_AMOUNT
        ):
            return False
        package = self.package(key.entity_id, key.basis, period_end(key.period), row.family)
        return package is not None and package.reporting_kind is PeriodKind.YEAR

    def _q4_row(
        self,
        row: DictionaryRow,
        key: MeasurementKey,
        periods: tuple[PeriodInterval, ...],
        reported: ResultRow,
    ) -> ResultRow:
        """Q4 derived from the FY and the same fiscal year's 9M, paired with the reported Q4."""
        year = periods[1]
        nine = nine_months(periods)
        package = self.package(key.entity_id, key.basis, period_end(key.period), row.family)
        sides: dict[Representation, Side] = {}
        surfaced: set[int] = set()
        for rep in REPRESENTATIONS:
            operands = []
            for period in (year, nine):
                cell = self.cell(key.model_copy(update={"period": period}), rep)
                differing = self._surfaced(cell)
                surfaced.update(differing)
                operands.append(
                    AggregationOperand(
                        operand=operand_value(cell.selection, proofs=self._proofs),
                        has_differing_restatement=bool(differing),
                    )
                )
            result = derive_period_value(
                PeriodDerivation.Q4_FROM_FY_MINUS_9M, row, key, operands, self._config.rounding
            )
            sides[rep] = calculated_side(
                result,
                key=key,
                representation=rep,
                trace_id=self._traces.put_calculation_trace(result.trace),
                package_id=None if package is None else package.package_id,
            )
        decision = ApplicabilityDecision(
            status=reported.applicability, rule_id=reported.applicability_rule_id
        )
        derived = self._compared(key, ValueIdentity.DERIVED, decision, sides, surfaced=surfaced)
        counterparts = tuple(
            as_counterpart(value)
            for value in reported.source_values
            if value.source_role is SourceRole.FIRST_PARTY
        )
        reported_sides = self._reported_sides[key.digest()]
        pairs = list(derived.pairs)
        for rep in REPRESENTATIONS:
            left, right = reported_sides[rep].comparison, sides[rep].comparison
            if pairable(left) and pairable(right):
                outcome = pair_outcome(
                    left,
                    right,
                    definitions=self._config.definition_set,
                    policy=self._config.comparison_policy,
                )
                pairs.append(
                    pair_record(
                        PairKind.REPORTED_VS_DERIVED,
                        ref(SourceRole.REPORTED_COUNTERPART, rep),
                        ref(SourceRole.FIRST_PARTY, rep),
                        outcome,
                    )
                )
        return derived.model_copy(
            update={
                "source_values": sorted_values((*derived.source_values, *counterparts)),
                "pairs": tuple(pairs),
            }
        )

    def _compared(
        self,
        key: MeasurementKey,
        identity: ValueIdentity,
        decision: ApplicabilityDecision,
        sides: dict[Representation, Side],
        *,
        surfaced: Iterable[int],
        extraction: ExtractionResult | None = None,
    ) -> ResultRow:
        """Extraction (unless already decided) and corroboration over the two sides."""
        xbrl, pdf = sides[Representation.XBRL].comparison, sides[Representation.PDF].comparison
        if extraction is None:
            extraction = extraction_status(
                family_has_pair=True,
                xbrl=xbrl,
                pdf=pdf,
                definitions=self._config.definition_set,
                policy=self._config.comparison_policy,
            )
        corroboration, reason = corroboration_status(
            applicability=decision.status, first_party=representative(xbrl, pdf)
        )
        pairs: tuple[PairRecord, ...] = ()
        if extraction.pair is not None:
            pairs = (
                pair_record(
                    PairKind.EXTRACTION,
                    ref(SourceRole.FIRST_PARTY, Representation.XBRL),
                    ref(SourceRole.FIRST_PARTY, Representation.PDF),
                    extraction.pair,
                    extraction.adjustments,
                ),
            )
        return ResultRow(
            row_id=row_id(key, identity),
            key=key,
            dictionary_version=self._config.dictionary.version,
            value_identity=identity,
            applicability=decision.status,
            applicability_rule_id=decision.rule_id,
            extraction_status=extraction.status,
            extraction_reason=extraction.reason,
            corroboration_status=corroboration,
            corroboration_reason=reason,
            source_values=sorted_values(tuple(side.stored for side in sides.values())),
            pairs=pairs,
            surfaced_restatements=tuple(sorted(set(surfaced))),
        )
