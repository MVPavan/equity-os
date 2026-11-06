"""A run's retained computed values as stored, interpretation-backed traces (PREP-2b Task 4).

Every operand is the one ``MAPPED`` interpretation of its key on the run's own (or the
comparator's) XBRL capture under the run's pins (its comparison run's dictionary, mapping set and
normalisation policy, and the XBRL extractor; other versions' interpretations may sit beside
it), or a required role's admitted interpretation (VENDOR-1 Task 9: a trace over one carries
the weakest admission label), and must equal the run's value. Each result is computed exactly
from those operands and packaged by ``conclude``; it must equal the run's value at the trace's
stored scale. Nothing is stored unless every value holds. Formulas
(version ``1``, operands ``DURATION`` under their own keys): ``run.difference`` a − b,
``run.sum`` a + b, ``run.change_pct`` (a − b) / b × 100, ``run.ratio_pct`` a / b × 100 (the PBT
margin, PBT before associates over revenue) and the registered ``effective_tax_rate_pct``
tax / PBT × 100. Keys follow the import's (``measurement_key``,
``change_key``); claim keys are the import's claim keys. The bound claims come back as the
draft's changes and calculations lines. With a ``Carry`` (a rework, PREP-5) each line is first
built unbound and only the lines it does not carry are bound; it is closed before any trace is
stored. A QoQ prior whose quarter's approved head admitted the role from the vendors (VENDOR-1
finding 3) is that admitted fact: its value, file, interpretation and label, the changes
computed from it. Each other interpretation figure is labelled ``FILED``; a ``check`` sees every
line's claims before any is bound.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from functools import cache, partial
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.measurement.canonical import Representation, TemporalRole, ValueKind
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    Interpretation,
    InterpretationStatus,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.measurement.measurement_key import MeasurementKey, PeriodInterval
from equity_os.contracts.measurement.provenance import Provenance
from equity_os.contracts.measurement.qualification import ScopedTier
from equity_os.contracts.measurement.role import FactRole
from equity_os.contracts.publication.ledger import NumericClaim, Rounding
from equity_os.contracts.verification.comparative import (
    RUN_PERCENT_PLACES,
    TAXONOMY_DRIFT_PREFIX,
    ComparatorKind,
)
from equity_os.contracts.verification.comparison import (
    CalculationState,
    SelectionSource,
    SourceState,
)
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import AdmissionLabel, weakest
from equity_os.extraction.packages.capture_intake import SURFACE_OF
from equity_os.extraction.xbrl.xbrl_adapter import XBRL_EXTRACTOR_VERSION
from equity_os.normalisation.derivation.formula import (
    CalculationResult,
    CalculationTrace,
    OperandValue,
    TraceKind,
    conclude,
    operand_from_result,
)
from equity_os.normalisation.derivation.interval import (
    Interval,
    RoundingPolicy,
    UndefinedDivisionError,
    load_rounding_policy,
    store_value,
)
from equity_os.normalisation.dictionary.role_translation import LEGACY_CONCEPTS
from equity_os.publication.checking.claim_check import CRORE, PERCENT, UNITS
from equity_os.publication.drafting.display import FILED
from equity_os.publication.drafting.earnings_update import (
    _ROLE_LABELS,
    AdmittedFact,
    EarningsUpdate,
    RenderedFact,
    predecessor_change,
)
from equity_os.publication.drafting.pnl_lines import (
    ETR_LABEL,
    GAP_LABEL,
    HEADLINE_LABEL,
    OPERAND_MISSING,
    TAX_LABEL,
)
from equity_os.publication.revision.import_mapping import (
    ABS,
    PCT,
    _slot,
    _valued,
    change_key,
    measurement_key,
    refs,
)
from equity_os.storage.records.repository import EvidenceRepository

ROUNDING_POLICY = (
    Path(__file__).resolve().parents[3] / "config" / "normalisation/rounding_policy" / "v1.yaml"
)
DIFFERENCE, SUM, CHANGE_PCT = "run.difference", "run.sum", "run.change_pct"
ETR = "effective_tax_rate_pct"
RATIO_PCT = "run.ratio_pct"
DAYS, RATIO, OUTFLOW_PCT = "run.days", "run.ratio", "run.outflow_pct"
MARGIN_KEY = "calc.pbt_margin"
MARGIN_LABEL = "PBT margin, PBT before associates over revenue (PBT / revenue × 100, %)"
FORMULA_VERSION = "1"
TAX, SHARE = "tax_expense", "share_of_profit_associates_jv"
CHANGES, CALCS = "changes", "calculations"
OPEN_QUESTIONS, NOT_PERFORMED = "open_questions", "not_performed"
DISCLOSED = frozenset({OPEN_QUESTIONS, NOT_PERFORMED})
_HUNDRED = Interval.exact(Fraction(100))
_NEG_HUNDRED = Interval.exact(Fraction(-100))
_CRORE_SCALE = UNITS[CRORE][2] or 1
# The code-side formulas carry no equivalence proof.
_UNPROVEN = ScopedTier(
    tier=EvidenceTier.EQUIVALENCE_UNPROVEN, qualification_ref=None, condition_evidence=()
)
_Operand = tuple[str, OperandValue]
_Lookup = Callable[[], _Operand]
CRORE_STYLE = "group-intl,trim"
CRORE_UNIT = f"{CRORE_STYLE},unit"
DRIFT_NOTE = (
    "taxonomy drift accepted in the issuer config: {drift}; both figures read as {canonical}"
)


class RunDraftError(RuntimeError):
    """The run's draft cannot be written; nothing of it is."""


class Line(BaseModel):
    """One changes or calculations line: its label, its bound claims in display order, each
    cited to its stored trace or interpretation, why a value is not available, and the basis of
    an accepted taxonomy drift."""

    model_config = ConfigDict(frozen=True)

    section: str
    label: str
    claims: tuple[NumericClaim, ...] = ()
    unavailable: str | None = None
    drift: str | None = None


class Carry(Protocol):
    """What a rework carries from its predecessor (``rework.Gate``)."""

    def line(
        self, section: str, text: str, claims: tuple[NumericClaim, ...]
    ) -> tuple[NumericClaim, ...] | None:
        """The predecessor's claims for a carried line, ``None`` for a line to rerun."""

    def close(self, blobs: frozenset[str]) -> None:
        """Refuse unless every line held; ``blobs`` are the rerun operands' sources."""


class _Binder:
    """One run's operand lookups and trace writes."""

    def __init__(
        self,
        repo: EvidenceRepository,
        entity_id: int,
        start: date,
        end: date,
        versions: ConfigVersions,
        admissions: Mapping[int, AdmissionLabel] | None = None,
    ) -> None:
        self.repo, self.entity_id, self.start, self.end = repo, entity_id, start, end
        self.admissions = admissions or {}
        self.context = (
            versions.dictionary,
            versions.mapping_set,
            versions.normalisation_policy,
            XBRL_EXTRACTOR_VERSION,
        )
        self.policy: RoundingPolicy = load_rounding_policy(ROUNDING_POLICY)
        self.pending: dict[str, CalculationTrace] = {}
        self.binds: dict[str, Callable[[], NumericClaim]] = {}
        self.blobs: set[str] = set()
        self.labels: dict[_Lookup, AdmissionLabel] = {}

    def key(self, canonical_id: str, unit: str | ValueKind) -> MeasurementKey:
        """A key of this run's quarter."""
        return measurement_key(canonical_id, unit, self.entity_id, self.start, self.end)

    def operand(
        self,
        name: str,
        source: Provenance,
        key: MeasurementKey,
        run_value: Decimal,
        selection: SelectionSource = SelectionSource.PACKAGE_AS_REPORTED,
    ) -> _Operand:
        """The single mapped interpretation of ``key`` in ``source``'s capture under
        the run's pins, equal to the run's value."""
        found = self.filed(source, key, selection)
        where = f"{key.canonical_id} in {source.file_sha256[:12]}"
        if found is None:
            raise RunDraftError(f"no single mapped interpretation of {where}")
        return name, self.checked(found[1], where, run_value)

    def checked(self, held: OperandValue, where: str, run_value: Decimal) -> OperandValue:
        """``held``, which must equal the run's value."""
        if held.value != run_value * _scale(held.key):
            raise RunDraftError(f"interpretation of {where} is {held.value}, the run's {run_value}")
        return held

    def admitted(
        self, name: str, fact: AdmittedFact, key: MeasurementKey, run_value: Decimal
    ) -> _Operand:
        """An admitted fact's operand from its own interpretation; no capture is read and no
        blob added."""
        (item,) = self.repo.get_interpretations([fact.interpretation_id])
        where = f"{key.canonical_id} admitted from interpretation {fact.interpretation_id}"
        if item.key is None or item.key.digest() != key.digest():
            raise RunDraftError(f"{where} is not of the key")
        held = _operand_value(key, item, SelectionSource.PACKAGE_AS_REPORTED, where)
        return name, self.checked(held, where, run_value)

    def admission(
        self, name: str, fact: AdmittedFact, key: MeasurementKey, run_value: Decimal
    ) -> _Lookup:
        """``admitted``, looked up once and only when needed, under the fact's label."""
        found = cache(partial(self.admitted, name, fact, key, run_value))
        self.labels[found] = fact.label
        return found

    def role(self, name: str, fact: RenderedFact, key: MeasurementKey) -> _Lookup:
        """A required role's operand: admitted, or filed."""
        if fact.admitted is not None:
            return self.admission(name, fact.admitted, key, fact.value)
        return self.lazy(name, fact.sources[0], key, fact.value)

    def filed(
        self, source: Provenance, key: MeasurementKey, selection: SelectionSource
    ) -> _Operand | None:
        """The single mapped interpretation of ``key`` in ``source``'s capture under the run's
        pins, named by its canonical id; ``None`` when there is none."""
        found = [
            item
            for item in self.mapped(source)
            if item.key is not None and item.key.digest() == key.digest()
        ]
        where = f"{key.canonical_id} in {source.file_sha256[:12]}"
        if not found:
            return None
        if len(found) > 1:
            raise RunDraftError(f"no single mapped interpretation of {where}")
        return key.canonical_id, _operand_value(key, found[0], selection, where)

    def mapped(self, source: Provenance) -> list[Interpretation]:
        """Every keyed ``MAPPED`` interpretation of ``source``'s capture under the run's pins."""
        self.blobs.add(source.file_sha256)
        capture = self.repo.find_capture_ref(
            source.source_id, SURFACE_OF[Representation.XBRL].value, source.file_sha256
        )
        return [
            item
            for item in self._interpretations(capture)
            if item.status is InterpretationStatus.MAPPED
            and _context(item) == self.context
            and item.key is not None
        ]

    def lazy(
        self,
        name: str,
        source: Provenance,
        key: MeasurementKey,
        run_value: Decimal,
        selection: SelectionSource = SelectionSource.PACKAGE_AS_REPORTED,
    ) -> _Lookup:
        """``operand``, looked up once and only when a bound line needs it."""
        return cache(partial(self.operand, name, source, key, run_value, selection))

    def _interpretations(self, capture: CaptureReference | None) -> tuple[Interpretation, ...]:
        """Every interpretation of a registered capture; none of an unregistered one."""
        if capture is None or capture.capture_ref_id is None:
            return ()
        return self.repo.list_capture_interpretations(capture.capture_ref_id)

    def figure(
        self,
        name: str,
        section: str,
        operand: _Lookup,
        key: MeasurementKey,
        source: Provenance,
        run_value: Decimal,
        unit: str,
    ) -> NumericClaim:
        """A retained figure's claim at the run's value, labelled with its admission label or
        filed; bound, it cites its interpretation."""
        claim = _valued(name, section, run_value, unit, key, source)
        label = self.labels[operand].value if operand in self.labels else FILED
        claim = claim.model_copy(update={"qualifiers": tuple(sorted({*claim.qualifiers, label}))})

        def bind() -> NumericClaim:
            held = operand()[1]
            assert held.interpretation_id is not None
            return cite(claim, interpretation_id=held.interpretation_id)

        self.binds[name] = bind
        return claim

    def trace(
        self,
        name: str,
        section: str,
        formula: str,
        output: MeasurementKey,
        operands: tuple[_Lookup, _Lookup],
        run_value: Decimal,
        unit: str,
        **options: Any,
    ) -> NumericClaim:
        """A computed value's claim, labelled with its admitted operands' weakest label; bound,
        its trace is computed and checked against the run's value, and the claim is cited once
        every trace holds and is stored."""
        claim = _valued(name, section, run_value, unit, output, **options)
        if labels := [self.labels[item] for item in operands if item in self.labels]:
            claim = claim.model_copy(update={"qualifiers": (weakest(labels).value,)})

        def bind() -> NumericClaim:
            self._compute(name, formula, output, (operands[0](), operands[1]()), run_value)
            return claim

        self.binds[name] = bind
        return claim

    def labelled(self, claim: NumericClaim, operands: Iterable[OperandValue]) -> NumericClaim:
        """``claim`` labelled with the weakest of its operands' admission labels under the pinned
        runs (``admissions``); unlabelled when none is admitted."""
        ids = [operand.interpretation_id for operand in operands]
        found = [self.admissions[i] for i in ids if i is not None and i in self.admissions]
        if not found:
            return claim
        return claim.model_copy(update={"qualifiers": (*claim.qualifiers, weakest(found).value)})

    def _compute(
        self,
        name: str,
        formula: str,
        output: MeasurementKey,
        operands: tuple[_Operand, _Operand],
        run_value: Decimal,
    ) -> None:
        """Compute one trace, check it against the run's value and hold it for storing."""
        result = self.evaluate(name, formula, output, operands)
        expected = Fraction(run_value) * _scale(output)
        if result.value != store_value(expected, output.value_kind, self.policy):
            raise RunDraftError(f"{name}: computed {result.value}, the run's {run_value}")
        self.pending[name] = result.trace

    def evaluate(
        self,
        name: str,
        formula: str,
        output: MeasurementKey,
        operands: tuple[_Operand, _Operand],
    ) -> CalculationResult:
        """One trace computed exactly from two operands; an instant operand is ``CLOSING``,
        a duration ``DURATION``. ``run.days`` scales by operand b's inclusive day count."""
        (_, a), (_, b) = operands
        assert a.exact is not None and a.interval is not None
        assert b.exact is not None and b.interval is not None
        try:
            if formula == DIFFERENCE:
                point = (a.exact - b.exact, a.interval.sub(b.interval))
            elif formula == SUM:
                point = (a.exact + b.exact, a.interval.add(b.interval))
            elif formula == CHANGE_PCT:
                ratio = a.interval.sub(b.interval).div(b.interval)
                point = ((a.exact - b.exact) / b.exact * 100, ratio.mul(_HUNDRED))
            elif formula in (ETR, RATIO_PCT):
                point = (a.exact / b.exact * 100, a.interval.div(b.interval).mul(_HUNDRED))
            elif formula == RATIO:
                point = (a.exact / b.exact, a.interval.div(b.interval))
            elif formula == OUTFLOW_PCT:
                point = (-a.exact / b.exact * 100, a.interval.div(b.interval).mul(_NEG_HUNDRED))
            elif formula == DAYS:
                period = b.key.period
                assert period.start is not None and period.end is not None
                days = Fraction((period.end - period.start).days + 1)
                ratio = a.interval.div(b.interval).mul(Interval.exact(days))
                point = (a.exact / b.exact * days, ratio)
            else:
                raise RunDraftError(f"{name}: unknown formula {formula}")
        except (UndefinedDivisionError, ZeroDivisionError) as error:
            raise RunDraftError(f"{name}: {formula} is undefined: {error}") from error
        entries = [(operand, _role(value.key.period), value) for operand, value in operands]
        return conclude(
            TraceKind.FORMULA,
            output,
            entries,
            CalculationState.COMPUTED,
            point,
            self.policy,
            formula_id=formula,
            formula_version=FORMULA_VERSION,
            formula_scoped=_UNPROVEN,
        )

    def child(
        self,
        name: str,
        formula: str,
        output: MeasurementKey,
        operands: tuple[_Operand, _Operand],
    ) -> _Operand:
        """A computed operand: its trace evaluated and stored, its id on the operand."""
        result = self.evaluate(name, formula, output, operands)
        held = operand_from_result(result, key=output, selection_source=None)
        return name, held.model_copy(update={"calculation_trace_id": self.store(name, result)})

    def store(self, name: str, result: CalculationResult) -> int:
        """Store ``name``'s computed trace; its id."""
        assert result.value is not None, name
        return self.repo.put_calculation_trace(result.trace)


def bind_computed(
    repo: EvidenceRepository,
    update: EarningsUpdate,
    *,
    entity_id: int,
    versions: ConfigVersions,
    carry: Carry | None = None,
    check: Callable[[tuple[NumericClaim, ...]], object] | None = None,
    predecessors: Mapping[FactRole, AdmittedFact] | None = None,
) -> tuple[Line, ...]:
    """The run's changes and calculations lines: a stored trace per retained computed value and
    the interpretation of each comparator figure and the filed tax expense, all bound before
    any trace is stored; any missing interpretation or mismatch raises. Operands are read under
    ``versions`` (the comparison run's pins). ``carry`` keeps the
    lines it carries unbound and is closed before any trace is stored; ``check`` refuses the
    unbound claims before any lookup. A role's QoQ prior in ``predecessors`` (the predecessor
    head's vendor-valued facts) is that fact."""
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    binder = _Binder(repo, entity_id, start, end, versions)
    facts = {fact.role: fact for fact in update.facts}
    by_concept = {fact.concept_qname: fact for fact in update.facts}
    lines: list[Line] = []
    for comparative in update.comparatives:
        fact = by_concept[comparative.concept_qname]
        key, unit = binder.key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit), fact.unit
        current = binder.role("current", fact, key)
        for change in (comparative.qoq, comparative.yoy):
            label = f"{_ROLE_LABELS[fact.role]} {change.kind.value} vs "
            label += f"{change.period_start}..{change.period_end}"
            if change.prior_value is None or change.absolute_change is None:
                lines.append(
                    Line(section=CHANGES, label=label, unavailable=change.unavailable_reason)
                )
                continue
            base = f"cmp.{fact.role.value}.{change.kind.value.lower()}"
            period = PeriodInterval.duration(change.period_start, change.period_end)
            prior_key = key.model_copy(update={"period": period})
            qoq = change.kind is ComparatorKind.QOQ
            admitted = (predecessors or {}).get(fact.role) if qoq else None
            if admitted is not None:
                change = predecessor_change(change, fact.value, admitted, unit)
            source, value = change.prior_source, change.prior_value
            absolute, percent = change.absolute_change, change.percent_change
            assert source is not None and value is not None and absolute is not None
            if admitted is not None:
                prior = binder.admission("prior", admitted, prior_key, value)
            else:
                historical = SelectionSource.HISTORICAL_PACKAGE
                prior = binder.lazy("prior", source, prior_key, value, historical)
            pair = (current, prior)
            abs_key = change_key(key, change.kind, ABS)
            claims = [
                binder.figure(f"{base}.prior", CHANGES, prior, prior_key, source, value, unit),
                binder.trace(f"{base}.abs", CHANGES, DIFFERENCE, abs_key, pair, absolute, unit),
            ]
            if percent is not None:
                claims.append(
                    binder.trace(
                        f"{base}.pct",
                        CHANGES,
                        CHANGE_PCT,
                        change_key(key, change.kind, PCT),
                        pair,
                        percent,
                        PERCENT,
                        precision=RUN_PERCENT_PLACES,
                        rounding=Rounding.ROUND_HALF_EVEN,
                    )
                )
            reason = change.percent_unavailable_reason
            drift = (change.taxonomy_drift or "").removeprefix(TAXONOMY_DRIFT_PREFIX)
            note = DRIFT_NOTE.format(drift=drift, canonical=key.canonical_id) if drift else None
            lines.append(
                Line(
                    section=CHANGES,
                    label=label,
                    claims=tuple(claims),
                    unavailable=reason,
                    drift=note,
                )
            )
    xbrl = facts[FactRole.PROFIT_BEFORE_TAX].sources[0]

    def reported(name: str, role: FactRole) -> _Lookup:
        fact = facts[role]
        key = binder.key(LEGACY_CONCEPTS[fact.concept_qname], CRORE)
        return binder.role(name, fact, key)

    pbt = facts[FactRole.PROFIT_BEFORE_TAX].value
    tax: _Lookup | None = None
    for number, calculation in enumerate(update.calculations, start=1):
        name, label = f"calc.{number}", calculation.label
        if calculation.result == OPERAND_MISSING:
            lines.append(Line(section=CALCS, label=label))
            continue
        value = Decimal(calculation.result.replace(",", ""))
        if label == GAP_LABEL:
            income = reported("total_income", FactRole.TOTAL_INCOME)
            operands = (income, reported("revenue", FactRole.REVENUE))
            claim = binder.trace(
                name, CALCS, DIFFERENCE, binder.key(label, CRORE), operands, value, CRORE
            )
        elif label == TAX_LABEL:
            tax_key = binder.key(TAX, CRORE)
            tax = binder.lazy("tax", xbrl, tax_key, value)
            claim = binder.figure(name, CALCS, tax, tax_key, xbrl, value, CRORE)
        elif label == ETR_LABEL and tax is not None:
            operands = (tax, reported("pbt", FactRole.PROFIT_BEFORE_TAX))
            claim = binder.trace(
                name, CALCS, ETR, binder.key(label, PERCENT), operands, value, PERCENT
            )
        elif label == HEADLINE_LABEL:
            share_key = binder.key(SHARE, CRORE)
            share = binder.lazy("share_of_associates", xbrl, share_key, value - pbt)
            operands = (reported("pbt", FactRole.PROFIT_BEFORE_TAX), share)
            claim = binder.trace(name, CALCS, SUM, binder.key(label, CRORE), operands, value, CRORE)
        else:
            raise RunDraftError(f"{name}: no formula for {label!r}")
        lines.append(Line(section=CALCS, label=label, claims=(claim,)))
    revenue = facts.get(FactRole.REVENUE)
    if revenue is None or not revenue.value:
        lines.append(Line(section=CALCS, label=MARGIN_LABEL))
    else:
        margin = (pbt / revenue.value * 100).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
        operands = (
            reported("pbt", FactRole.PROFIT_BEFORE_TAX),
            reported("revenue", FactRole.REVENUE),
        )
        claim = binder.trace(
            MARGIN_KEY,
            CALCS,
            RATIO_PCT,
            binder.key(MARGIN_LABEL, PERCENT),
            operands,
            margin,
            PERCENT,
            precision=RUN_PERCENT_PLACES,
            rounding=Rounding.ROUND_HALF_EVEN,
        )
        lines.append(Line(section=CALCS, label=MARGIN_LABEL, claims=(claim,)))
    if check is not None:
        check(tuple(claim for line in lines for claim in line.claims))
    bound = []
    for line in lines:
        held = None if carry is None else carry.line(line.section, _shown(line), line.claims)
        if held is None:
            held = tuple(binder.binds[claim.claim_key]() for claim in line.claims)
        bound.append(line.model_copy(update={"claims": held}))
    if carry is not None:
        carry.close(frozenset(binder.blobs))
    traces = {name: repo.put_calculation_trace(trace) for name, trace in binder.pending.items()}

    def stored(claim: NumericClaim) -> NumericClaim:
        trace_id = traces.get(claim.claim_key)
        return claim if trace_id is None else cite(claim, calculation_trace_id=trace_id)

    return tuple(
        line.model_copy(update={"claims": tuple(map(stored, line.claims))}) for line in bound
    )


def _operand_value(
    key: MeasurementKey, item: Interpretation, selection: SelectionSource, where: str
) -> OperandValue:
    """An interpretation as a ``key`` operand with its value and precision."""
    if item.value is None or item.interval is None:
        raise RunDraftError(f"interpretation of {where} has no value with precision")
    return OperandValue(
        key=key,
        state=SourceState.VALUE,
        exact=Fraction(item.value),
        value=item.value,
        interval=item.interval,
        interpretation_id=item.interpretation_id,
        package_id=None,
        calculation_trace_id=None,
        child_trace=None,
        alignment_proof_id=None,
        mapping_entry_id=item.mapping_entry_id,
        qualification_ref=item.qualification_ref,
        scoped_tier=EvidenceTier.EQUIVALENCE_UNPROVEN,
        selection_source=selection,
        precision_supported=True,
        reasons=(),
    )


def _shown(line: Line) -> str:
    """A changes or calculations line with its claims' placeholders."""
    keys = [claim.claim_key for claim in line.claims]
    if line.section == CALCS:
        if not keys:
            return f"- {line.label} = {OPERAND_MISSING}"
        style = CRORE_STYLE if line.claims[0].unit == CRORE else ""
        return f"- {line.label} = {_slot(keys[0], style)} {refs(keys)}"
    if not keys:
        return f"- {line.label}: not available ({line.unavailable})"
    prior, change, *percent = keys
    shown = f"- {line.label}: prior {_slot(prior, CRORE_UNIT)}"
    shown += f"; change {_slot(change, f'plus,{CRORE_UNIT}')}"
    if percent:
        shown += f", {_slot(percent[0], 'plus,unit')}"
    else:
        shown += f"; percent change not available ({line.unavailable})"
    if line.drift:
        shown += f"; {line.drift}"
    return f"{shown} {refs(keys)}"


def _fiscal_month(repository: EvidenceRepository, entity_id: int, update: EarningsUpdate) -> int:
    """The entity's fiscal-year-end month governing the run's period, as of the store clock."""
    period_end = date.fromisoformat(update.period_end)
    record = repository.settings_as_of(
        entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock(), period_end
    )
    if record is None:
        raise RunDraftError(f"entity {entity_id} has no fiscal-year-end month")
    return int(record.value_text)


def admitted_xbrl(
    update: EarningsUpdate,
) -> tuple[Provenance, dict[ComparatorKind, tuple[Provenance, date]]]:
    """The run's own XBRL and its comparators' with their period ends, QoQ before YoY."""
    (own,) = (fact.sources[0] for fact in update.facts if fact.role is FactRole.PROFIT_BEFORE_TAX)
    found = {
        change.kind: (change.prior_source, change.period_end)
        for comparative in update.comparatives
        for change in (comparative.qoq, comparative.yoy)
        if change.prior_source is not None
    }
    order = (ComparatorKind.QOQ, ComparatorKind.YOY)
    return own, {kind: found[kind] for kind in order if kind in found}


def cite(claim: NumericClaim, **record: object) -> NumericClaim:
    """``claim`` cited to its stored record."""
    citation = claim.citation.model_copy(update=record)
    return claim.model_copy(update={"citation": citation, "unresolved": False})


def _context(item: Interpretation) -> tuple[str, str, str, str]:
    """The versions an interpretation was made under, in ``_Binder.context`` order."""
    return (
        item.dictionary_version,
        item.mapping_set_version,
        item.normalisation_policy_version,
        item.extractor_version,
    )


def _role(period: PeriodInterval) -> TemporalRole:
    """An instant operand is a closing balance, a duration a flow."""
    return TemporalRole.DURATION if period.instant is None else TemporalRole.CLOSING


def _scale(key: MeasurementKey) -> int:
    """Base units per unit of a run value under ``key``: INR per crore for an amount, else 1."""
    return _CRORE_SCALE if key.value_kind is ValueKind.CURRENCY_AMOUNT else 1
