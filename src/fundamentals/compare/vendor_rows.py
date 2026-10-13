"""Pure source-qualified row assembly and routing over one closed run input set.

The caller revalidates publication and handoffs before loading these immutable rows.
Availability uses logical scope; financial selection additionally requires the exact
declared request and capture. Execution and by-id replay call these same functions.
"""

from __future__ import annotations

from datetime import datetime

from fundamentals.canon.applicability import ApplicabilityContext, decide_applicability
from fundamentals.compare.engine_attempts import RunResolutionError, attempt_available
from fundamentals.compare.engine_context import basis_status, segment_bases, segment_members
from fundamentals.compare.engine_rows import pair_record, reason_codes
from fundamentals.compare.resolve_models import ResolvedInputs
from fundamentals.compare.routing import (
    route_pair_draft,
    route_status_draft,
    route_unmapped_occurrence_draft,
)
from fundamentals.compare.run_config import LoadedConfig
from fundamentals.compare.run_models import (
    ResultRow,
    RunRequest,
    SourceValue,
    VendorSurfaceRequest,
    row_id,
)
from fundamentals.compare.tables import (
    ComparisonSide,
    PairResult,
    SourceQualifiedPair,
    SourceQualifiedSide,
    corroboration_result,
    diagnostic_pair,
)
from fundamentals.compare.vendor_request import ScreenerComposerContext, request_from_declaration
from fundamentals.compare.vendor_row_evidence import RowEvidence
from fundamentals.contracts.acquisition_outcome import outcome_source_state
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    DocumentType,
    ReportingRegime,
    Representation,
    StatementFamily,
    ValueIdentity,
)
from fundamentals.contracts.comparison import (
    CorroborationStatus,
    ExtractionStatus,
    PairKind,
    SourceRef,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    KnowledgeTimeStatus,
    Occurrence,
    RunMode,
    VendorExtractorPin,
    exact_decimal,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.review_queue import QueueItemDraft
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.contracts.source_catalog import EvidenceRole, SourceClass
from fundamentals.evidence.selection import INTERPRETATION_AMBIGUOUS, _matches, period_end
from fundamentals.evidence.vendor_config import SurfaceDisposition


def attach_vendor_rows(
    rows: tuple[ResultRow, ...],
    *,
    inputs: ResolvedInputs,
    request: RunRequest,
    config: LoadedConfig,
) -> tuple[ResultRow, ...]:
    """Append actual vendor sides and pairs; diagnostics never decide corroboration."""
    if not request.scope.vendor_sources:
        return rows
    return _Assembly(inputs, request, config).attach(rows)


def queue_drafts(
    rows: tuple[ResultRow, ...],
    *,
    inputs: ResolvedInputs,
    request: RunRequest,
    config: LoadedConfig,
) -> tuple[QueueItemDraft, ...]:
    """Route actual pair/status/unmapped evidence without inventing store identity."""
    return _Assembly(inputs, request, config).drafts(rows)


class _Assembly(RowEvidence):
    def __init__(self, inputs: ResolvedInputs, request: RunRequest, config: LoadedConfig) -> None:
        super().__init__(inputs, request, config)
        self.declarations = request.scope.vendor_sources
        self.vendor_refs: dict[str, SourceRef] = {}
        self.vendor_pins: dict[str, VendorExtractorPin] = {}
        for declaration in self.declarations:
            self._authority(declaration)

    def _authority(self, declaration: VendorSurfaceRequest) -> None:
        declared = request_from_declaration(declaration)
        publication = self.config.vendor_config
        if publication is None:
            raise RunResolutionError("vendor assembly requires the loader-verified publication")
        identity = (declared.source_id, declared.surface, declared.representation)
        ledger = [
            row
            for row in publication.surface_ledger
            if (row.source_id, row.surface, row.representation) == identity
        ]
        authorities = [
            row
            for row in publication.authorities
            if (row.source_id, row.surface, row.representation) == identity
        ]
        pins = [
            pin
            for pin in publication.extractor_pins
            if (pin.source_id, pin.surface) == identity[:2]
        ]
        descriptor = publication.catalog.describe(declared.source_id)
        if (
            len(ledger) != 1
            or ledger[0].disposition is SurfaceDisposition.EXCLUDED
            or len(authorities) != 1
            or len(pins) != 1
            or descriptor.source_class is not SourceClass.DERIVED
            or authorities[0].evidence_role is not descriptor.evidence_role
        ):
            raise RunResolutionError("vendor assembly lacks one exact published surface authority")
        role = (
            SourceRole.DIAGNOSTIC
            if descriptor.evidence_role is EvidenceRole.DIAGNOSTIC_ONLY
            else SourceRole.INDEPENDENT_VENDOR
        )
        token = self._token(declaration)
        self.vendor_refs[token] = SourceRef(
            source_role=role,
            representation=declared.representation,
            source_id=declared.source_id,
            surface=declared.surface,
        )
        self.vendor_pins[token] = pins[0]

    @staticmethod
    def _token(declaration: VendorSurfaceRequest) -> str:
        return canonical_sha256(declaration.model_dump(mode="json"))

    def _attempts(self, declaration: VendorSurfaceRequest) -> tuple[AcquisitionAttempt, ...]:
        declared = request_from_declaration(declaration)
        pin = self.vendor_pins[self._token(declaration)]
        return tuple(
            row
            for row in self.inputs.attempts
            if (
                row.source_id,
                row.surface,
                row.entity_id,
                row.period_end,
                row.basis,
                row.framework,
                row.representation,
                row.statement_family,
                row.package_id,
                row.extractor_version,
                row.extraction_context_sha256,
            )
            == (
                declared.source_id,
                declared.surface,
                declared.entity_id,
                period_end(declared.period),
                declared.basis,
                declared.framework,
                declared.representation,
                declared.statement_family,
                None,
                pin.version,
                declaration.expected_logical_scope_sha256,
            )
            and row.attempted_at is not None
            and attempt_available(
                row, cutoff=self.request.cutoff, mode=self.request.mode, extractor=pin.version
            )
        )

    def _occurrence_matches(
        self, occurrence: Occurrence, declaration: VendorSurfaceRequest
    ) -> bool:
        declared = request_from_declaration(declaration)
        context = occurrence.native_context
        if (
            occurrence.capture.capture_ref_id != declaration.capture_ref_id
            or (occurrence.capture.source_id, occurrence.capture.surface, occurrence.representation)
            != (declared.source_id, declared.surface, declared.representation)
            or occurrence.extractor_version != self.vendor_pins[self._token(declaration)].version
            or context.get("schema_identity") != declared.schema_identity
            or context.get("statement_family") != declared.statement_family.value
            or context.get("basis") != declared.basis.value
        ):
            return False
        composer = declaration.composer_context
        if isinstance(composer, ScreenerComposerContext):
            section = composer.section.value
            if composer.parent is not None:
                section = f"{section}/{composer.parent}"
            if context.get("section") != section:
                return False
        return True

    def _vendor_group(self, declaration: VendorSurfaceRequest) -> tuple[Interpretation, ...]:
        declared = request_from_declaration(declaration)
        pin = self.vendor_pins[self._token(declaration)]
        capture = (
            self.captures.get(declaration.capture_ref_id)
            if declaration.capture_ref_id is not None
            else None
        )
        if capture is None or capture.first_seen_at > self.request.cutoff:
            return ()
        rows = []
        for row in self.inputs.interpretations:
            if (
                row.capture_ref_id,
                row.representation,
                row.entity_id,
                row.basis,
                row.framework,
                row.dictionary_version,
                row.mapping_set_version,
                row.normalisation_policy_version,
                row.extractor_version,
            ) != (
                declaration.capture_ref_id,
                declared.representation,
                declared.entity_id,
                declared.basis,
                declared.framework,
                self.request.pinned.dictionary.version,
                self.request.pinned.mapping_set.version,
                self.request.pinned.normalisation_policy.version,
                pin.version,
            ):
                continue
            if self.request.mode is RunMode.AS_KNOWN and row.recorded_at > self.request.cutoff:
                continue
            ids, occurrence_ids = self._interpretation_closure(row.interpretation_id)
            if not occurrence_ids:
                raise RunResolutionError("vendor interpretation has no native occurrence closure")
            if any(
                self.interpretations[ref].capture_ref_id != row.capture_ref_id
                or self.interpretations[ref].representation is not row.representation
                or self.interpretations[ref].entity_id != row.entity_id
                or self.interpretations[ref].basis is not row.basis
                or self.interpretations[ref].framework is not row.framework
                or self.interpretations[ref].period != row.period
                or self.interpretations[ref].dictionary_version != row.dictionary_version
                or self.interpretations[ref].mapping_set_version != row.mapping_set_version
                or self.interpretations[ref].normalisation_policy_version
                != row.normalisation_policy_version
                or self.interpretations[ref].extractor_version != row.extractor_version
                for ref in ids
            ):
                raise RunResolutionError(
                    "native vendor construction crosses source or entity scope"
                )
            if any(
                not self._occurrence_matches(self.occurrences[ref], declaration)
                for ref in occurrence_ids
            ):
                continue
            if row.origin is InterpretationOrigin.CONSTRUCTED:
                rules = [
                    rule
                    for rule in self.config.mapping_set.constructions
                    if (
                        rule.rule_id,
                        rule.source,
                        rule.surface,
                        rule.schema_identity,
                        rule.canonical_id,
                    )
                    == (
                        row.construction_rule_id,
                        declared.source_id,
                        declared.surface,
                        declared.schema_identity,
                        row.canonical_id,
                    )
                ]
                if len(rules) != 1 or not row.operand_interpretation_ids:
                    raise RunResolutionError(
                        "vendor construction lacks one exact published rule and operands"
                    )
            occurrences = [self.occurrences[ref] for ref in occurrence_ids]
            if any(
                occurrence.first_seen_at > self.request.cutoff
                or (
                    occurrence.knowledge_time_status is KnowledgeTimeStatus.KNOWN
                    and (
                        occurrence.knowledge_time is None
                        or occurrence.knowledge_time > self.request.cutoff
                    )
                )
                for occurrence in occurrences
            ):
                continue
            rows.append(row)
        superseded = {row.supersedes_interpretation_id for row in rows}
        return tuple(row for row in rows if row.interpretation_id not in superseded)

    def _declarations_for(self, key: MeasurementKey) -> tuple[VendorSurfaceRequest, ...]:
        declarations = tuple(
            row
            for row in self.declarations
            if (row.entity_id, row.period, row.basis, row.framework)
            == (key.entity_id, key.period, key.basis, key.framework)
            and row.statement_family in self._measurement_families(key, row)
        )
        refs = [self.vendor_refs[self._token(row)].model_dump_json() for row in declarations]
        if len(refs) != len(set(refs)):
            raise RunResolutionError("ambiguous declarations share one vendor result-side identity")
        return declarations

    def _measurement_families(
        self, key: MeasurementKey, declaration: VendorSurfaceRequest
    ) -> set[StatementFamily]:
        """A source-native aggregate can belong to a DERIVED dictionary row."""
        families = {self.config.dictionary.row(key.canonical_id).family}
        identity = (declaration.source_id, declaration.surface, declaration.schema_identity)
        for entry in self.config.mapping_set.entries:
            if (
                entry.canonical_id == key.canonical_id
                and (entry.source, entry.surface, entry.schema_identity) == identity
            ):
                if entry.selector.statement_family is not None:
                    families.add(entry.selector.statement_family)
        for rule in self.config.mapping_set.constructions:
            if (
                rule.canonical_id != key.canonical_id
                or (rule.source, rule.surface, rule.schema_identity) != identity
            ):
                continue
            for operand in rule.operands:
                selector = (
                    operand.native.selector
                    if operand.native is not None
                    else self.config.mapping_set.entry(operand.mapping_entry_id or "").selector
                )
                if selector.statement_family is not None:
                    families.add(selector.statement_family)
        return families

    def _vendor_side(
        self, key: MeasurementKey, declaration: VendorSurfaceRequest
    ) -> tuple[SourceQualifiedSide, SourceValue]:
        declared = request_from_declaration(declaration)
        ref = self.vendor_refs[self._token(declaration)]
        attempts = self._attempts(declaration)
        latest = max(attempts, key=_attempt_order, default=None)
        candidates: tuple[Interpretation, ...] = ()
        chosen: Interpretation | None = None
        state = SourceState.UNAVAILABLE
        reason: str | None = "NO_AVAILABLE_VENDOR_ATTEMPT"
        if latest is not None:
            imposed = outcome_source_state(latest.outcome)
            if imposed is not None:
                state, reason = imposed, latest.outcome.value
            elif (
                latest.input_sha256 != declared.identity_sha256()
                or latest.capture is None
                or latest.capture.capture_ref_id != declaration.capture_ref_id
            ):
                reason = "UNHANDED_VENDOR_GENERATION"
            else:
                candidates = tuple(
                    row for row in self._vendor_group(declaration) if _matches(row, key)
                )
                state, reason = SourceState.NO_VALUE, None
                if len(candidates) > 1:
                    state, reason = SourceState.INVALID, INTERPRETATION_AMBIGUOUS
                elif candidates:
                    chosen = candidates[0]
                    if chosen.status is InterpretationStatus.MAPPED:
                        state = (
                            SourceState.VALUE if chosen.value is not None else SourceState.NO_VALUE
                        )
                    else:
                        state = SourceState.INVALID
                        reason = chosen.reason.value if chosen.reason else chosen.status.value
        interpretation_ids, occurrence_ids = set(), set()
        for candidate in candidates:
            ids, occurrences = self._interpretation_closure(candidate.interpretation_id)
            interpretation_ids.update(ids)
            occurrence_ids.update(occurrences)
        valued = state is SourceState.VALUE
        interval = chosen.interval if valued and chosen is not None else None
        comparison = ComparisonSide(
            key=key,
            state=state,
            value=chosen.value if valued and chosen is not None else None,
            interval=interval,
            tier=chosen.tier if chosen is not None else EvidenceTier.EQUIVALENCE_UNPROVEN,
            aligned_by_proof=False,
            mapping_entry_ids=tuple(
                sorted(
                    {
                        entry
                        for ref_id in interpretation_ids
                        if (entry := self.interpretations[ref_id].mapping_entry_id) is not None
                    }
                )
            ),
            package_id=None,
            calculation_state=None,
            reasons=reason_codes([reason]),
        )
        qualified = SourceQualifiedSide(
            ref=ref,
            side=comparison,
            occurrence_ids=tuple(sorted(occurrence_ids)),
            interpretation_ids=tuple(sorted(interpretation_ids)),
            attempt_ids=() if latest is None or latest.attempt_id is None else (latest.attempt_id,),
        )
        stored = SourceValue(
            **ref.model_dump(),
            state=state,
            reason=reason,
            value=comparison.value,
            lower=None if interval is None else exact_decimal(interval.lower),
            upper=None if interval is None else exact_decimal(interval.upper),
            interpretation_id=None if chosen is None else chosen.interpretation_id,
            calculation_trace_id=None,
            attempt_id=None if latest is None else latest.attempt_id,
            calculation_state=None,
        )
        return qualified, stored

    def attach(self, rows: tuple[ResultRow, ...]) -> tuple[ResultRow, ...]:
        assembled = list(rows)
        keys = {row.key.digest() for row in rows}
        for declaration in self.declarations:
            for item in self._vendor_group(declaration):
                if (
                    item.key is not None
                    and item.key.period == declaration.period
                    and item.key.digest() not in keys
                ):
                    assembled.append(self._vendor_only_row(item.key))
                    keys.add(item.key.digest())
        result = []
        for row in assembled:
            declarations = self._declarations_for(row.key)
            if row.applicability is ApplicabilityStatus.NOT_APPLICABLE or not declarations:
                result.append(row)
                continue
            first, values = self._first_party(row)
            vendor_sides, vendor_values = [], []
            for declaration in declarations:
                side, value = self._vendor_side(row.key, declaration)
                vendor_sides.append(side)
                vendor_values.append(value)
            corroboration = corroboration_result(
                applicability=row.applicability,
                first_party=first,
                vendors=vendor_sides,
                definitions=self.config.definition_set,
                policy=self.config.comparison_policy,
            )
            pairs = list(corroboration.pairs)
            for vendor in vendor_sides:
                if vendor.ref.source_role is SourceRole.DIAGNOSTIC:
                    diagnostic = diagnostic_pair(
                        first,
                        vendor,
                        definitions=self.config.definition_set,
                        policy=self.config.comparison_policy,
                    )
                    if diagnostic is not None:
                        pairs.append(diagnostic)
            first_party_sides = [self._fp_side(row.key, value) for value in values]
            previous = tuple(
                pair.model_copy(
                    update={
                        "left": self._named_side(first_party_sides, pair.left).ref,
                        "right": self._named_side(first_party_sides, pair.right).ref,
                    }
                )
                for pair in row.pairs
                if pair.pair_kind not in (PairKind.CORROBORATION, PairKind.DIAGNOSTIC)
            )
            result.append(
                row.model_copy(
                    update={
                        "source_values": tuple(
                            sorted(
                                (*values, *vendor_values),
                                key=lambda value: (
                                    value.source_role.value,
                                    value.representation.value,
                                    value.source_id or "",
                                    value.surface or "",
                                ),
                            )
                        ),
                        "pairs": (
                            *previous,
                            *(
                                pair_record(pair.pair_kind, pair.left, pair.right, pair.result)
                                for pair in pairs
                            ),
                        ),
                        "corroboration_status": corroboration.status,
                        "corroboration_reason": corroboration.reason,
                    }
                )
            )
        return tuple(sorted(result, key=lambda row: row.row_id))

    def _vendor_only_row(self, key: MeasurementKey) -> ResultRow:
        dictionary_row = self.config.dictionary.row(key.canonical_id)
        packages = [
            package
            for package in self.inputs.packages
            if (package.entity_id, package.basis, package.framework, package.reporting_period_end)
            == (key.entity_id, key.basis, key.framework, period_end(key.period))
        ]
        if len(packages) != 1:
            raise RunResolutionError(
                "vendor-only row needs one evidenced first-party applicability context"
            )
        package = packages[0]
        decision = decide_applicability(
            dictionary_row,
            ApplicabilityContext(
                regime=ReportingRegime.IN_LODR,
                document_type=DocumentType.FINANCIAL_RESULTS,
                statements_present=package.statements_present,
                period_kind=package.reporting_kind,
                requested_basis=key.basis,
                entity_basis_status=basis_status(
                    self.inputs.basis_statuses, key.entity_id, self.request.cutoff
                ),
                evidenced_segment_bases=segment_bases(
                    segment_members(
                        self.inputs.segment_members, key.entity_id, self.request.cutoff
                    ),
                    self.occurrences,
                ),
                disclosed_rows=frozenset(
                    item.canonical_id
                    for item in self.inputs.interpretations
                    if item.capture_ref_id
                    in {member.capture.capture_ref_id for member in package.members.values()}
                    and item.canonical_id is not None
                ),
            ),
        )
        absent = SourceValue(
            source_role=SourceRole.FIRST_PARTY,
            representation=Representation.XBRL,
            state=SourceState.NO_VALUE,
            reason="NO_FIRST_PARTY_ROW_FOR_EXACT_KEY",
            value=None,
            lower=None,
            upper=None,
            interpretation_id=None,
            calculation_trace_id=None,
            attempt_id=None,
            calculation_state=None,
        )
        return ResultRow(
            row_id=row_id(key, ValueIdentity.REPORTED),
            key=key,
            dictionary_version=self.config.dictionary.version,
            value_identity=ValueIdentity.REPORTED,
            applicability=decision.status,
            applicability_rule_id=decision.rule_id,
            extraction_status=ExtractionStatus.NONE,
            extraction_reason=None,
            corroboration_status=CorroborationStatus.NO_SOURCE,
            corroboration_reason=None,
            source_values=(absent,),
            pairs=(),
            surfaced_restatements=(),
        )

    def drafts(self, rows: tuple[ResultRow, ...]) -> tuple[QueueItemDraft, ...]:
        drafts: list[QueueItemDraft] = []
        for row in rows:
            sides = [
                self._fp_side(row.key, value)
                for value in row.source_values
                if value.source_role not in (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)
            ]
            sides.extend(
                self._vendor_side(row.key, declaration)[0]
                for declaration in self._declarations_for(row.key)
            )
            for record in row.pairs:
                left, right = (
                    self._named_side(sides, record.left),
                    self._named_side(sides, record.right),
                )
                pair = SourceQualifiedPair(
                    pair_kind=record.pair_kind,
                    left=record.left,
                    right=record.right,
                    result=PairResult(
                        outcome=record.outcome,
                        reason=record.reason,
                        triage=record.triage,
                        difference=record.difference,
                        interval_gap=record.interval_gap,
                        definition_record_id=record.definition_record_id,
                    ),
                    attempt_ids=tuple(sorted(set(left.attempt_ids + right.attempt_ids))),
                    evidence_interpretation_ids=tuple(
                        sorted(set(left.interpretation_ids + right.interpretation_ids))
                    ),
                    evidence_occurrence_ids=tuple(
                        sorted(set(left.occurrence_ids + right.occurrence_ids))
                    ),
                )
                draft = route_pair_draft(pair, key=row.key)
                if draft is not None:
                    drafts.append(draft)
            for status, reason, selected in (
                (
                    row.extraction_status,
                    row.extraction_reason,
                    [side for side in sides if side.ref.source_role is SourceRole.FIRST_PARTY],
                ),
                (
                    row.corroboration_status,
                    row.corroboration_reason,
                    [
                        side
                        for side in sides
                        if side.ref.source_role
                        in (SourceRole.FIRST_PARTY, SourceRole.INDEPENDENT_VENDOR)
                    ],
                ),
            ):
                draft = route_status_draft(
                    status,
                    key=row.key,
                    reason_code=reason,
                    source_refs=tuple(side.ref for side in selected),
                    attempt_ids=tuple(
                        sorted({ref for side in selected for ref in side.attempt_ids})
                    ),
                    evidence_interpretation_ids=tuple(
                        sorted({ref for side in selected for ref in side.interpretation_ids})
                    ),
                    evidence_occurrence_ids=tuple(
                        sorted({ref for side in selected for ref in side.occurrence_ids})
                    ),
                )
                if draft is not None:
                    drafts.append(draft)
        member_captures = {
            member.capture.capture_ref_id
            for package in self.inputs.packages
            for member in package.members.values()
        }
        for item in self.inputs.interpretations:
            if item.status is not InterpretationStatus.UNMAPPED or item.occurrence_id is None:
                continue
            occurrence = self.occurrences[item.occurrence_id]
            ref: SourceRef | None = None
            if item.representation in (Representation.XBRL, Representation.PDF):
                if item.capture_ref_id in member_captures:
                    ref = SourceRef(
                        source_role=SourceRole.FIRST_PARTY,
                        representation=item.representation,
                        source_id=occurrence.capture.source_id,
                        surface=occurrence.capture.surface,
                    )
            else:
                declarations = [
                    row
                    for row in self.declarations
                    if self._occurrence_matches(occurrence, row)
                    and occurrence.period in (None, row.period)
                ]
                if len(declarations) > 1:
                    raise RunResolutionError(
                        "unmapped vendor occurrence has ambiguous declarations"
                    )
                if declarations:
                    ref = self.vendor_refs[self._token(declarations[0])]
            if ref is not None:
                drafts.append(
                    route_unmapped_occurrence_draft(
                        occurrence_id=item.occurrence_id, source_ref=ref
                    )
                )
        unique = {canonical_sha256(draft.model_dump(mode="json")): draft for draft in drafts}
        return tuple(unique[digest] for digest in sorted(unique))

    @staticmethod
    def _named_side(sides: list[SourceQualifiedSide], ref: SourceRef) -> SourceQualifiedSide:
        found = [
            side
            for side in sides
            if side.ref.source_role is ref.source_role
            and side.ref.representation is ref.representation
            and (
                ref.source_id is None
                or (side.ref.source_id, side.ref.surface) == (ref.source_id, ref.surface)
            )
        ]
        if len(found) != 1:
            raise RunResolutionError("pair reference does not name one actual resolved source side")
        return found[0]


def _attempt_order(attempt: AcquisitionAttempt) -> tuple[datetime, int]:
    assert attempt.attempted_at is not None and attempt.attempt_id is not None
    return attempt.attempted_at, attempt.attempt_id
