"""A run's retained computed values as stored, interpretation-backed traces (PREP-2b Task 4).

Every operand is the one ``MAPPED`` interpretation of its key on the run's own (or the
comparator's) XBRL capture under ``RUN_CONTEXT`` (the onboarding pins and the XBRL extractor;
other versions' interpretations may sit beside it), and must equal the run's value. Each result
is computed exactly from those operands and packaged by ``conclude``; it must equal the run's
value at the trace's stored scale. Nothing is stored unless every value holds. Formulas
(version ``1``, operands ``DURATION`` under their own keys): ``run.difference`` a − b,
``run.sum`` a + b, ``run.change_pct`` (a − b) / b × 100 and the registered
``effective_tax_rate_pct`` tax / PBT × 100. Keys follow the import's (``measurement_key``,
``change_key``); claim keys are the import's claim keys. The bound claims come back as the
draft's changes and calculations lines.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.formula import CalculationTrace, OperandValue, TraceKind, conclude
from fundamentals.canon.interval import (
    Interval,
    RoundingPolicy,
    UndefinedDivisionError,
    load_rounding_policy,
    store_value,
)
from fundamentals.canon.role_translation import LEGACY_CONCEPTS
from fundamentals.contracts.canonical import Representation, TemporalRole, ValueKind
from fundamentals.contracts.comparative import RUN_PERCENT_PLACES
from fundamentals.contracts.comparison import CalculationState, SelectionSource, SourceState
from fundamentals.contracts.evidence import CaptureReference, Interpretation, InterpretationStatus
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.ledger import NumericClaim, Rounding
from fundamentals.contracts.measurement_key import MeasurementKey, PeriodInterval
from fundamentals.contracts.onboarding import ONBOARDING_VERSIONS
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.qualification import ScopedTier
from fundamentals.contracts.role import FactRole
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION
from fundamentals.ledger.claim_check import CRORE, PERCENT, UNITS
from fundamentals.ledger.import_mapping import ABS, PCT, _valued, change_key, measurement_key
from fundamentals.output.earnings_update import _ROLE_LABELS, EarningsUpdate
from fundamentals.output.pnl_lines import (
    ETR_LABEL,
    GAP_LABEL,
    HEADLINE_LABEL,
    OPERAND_MISSING,
    TAX_LABEL,
)

ROUNDING_POLICY = Path(__file__).resolve().parents[3] / "config" / "rounding_policy" / "v1.yaml"
DIFFERENCE, SUM, CHANGE_PCT = "run.difference", "run.sum", "run.change_pct"
ETR = "effective_tax_rate_pct"
FORMULA_VERSION = "1"
TAX, SHARE = "tax_expense", "share_of_profit_associates_jv"
CHANGES, CALCS = "changes", "calculations"
_HUNDRED = Interval.exact(Fraction(100))
_CRORE_SCALE = UNITS[CRORE][2] or 1
# The code-side formulas carry no equivalence proof.
_UNPROVEN = ScopedTier(
    tier=EvidenceTier.EQUIVALENCE_UNPROVEN, qualification_ref=None, condition_evidence=()
)
_Operand = tuple[str, OperandValue]
# Dictionary, mapping-set, normalisation-policy and extractor versions a run's operands carry.
RUN_CONTEXT = (
    ONBOARDING_VERSIONS.dictionary,
    ONBOARDING_VERSIONS.mapping_set,
    ONBOARDING_VERSIONS.normalisation_policy,
    XBRL_EXTRACTOR_VERSION,
)


class RunDraftError(RuntimeError):
    """The run's draft cannot be written; nothing of it is."""


class Line(BaseModel):
    """One changes or calculations line: its label, its bound claims in display order, each
    cited to its stored trace or interpretation, and why a value is not available."""

    model_config = ConfigDict(frozen=True)

    section: str
    label: str
    claims: tuple[NumericClaim, ...] = ()
    unavailable: str | None = None


class _Binder:
    """One run's operand lookups and trace writes."""

    def __init__(self, repo: EvidenceRepository, entity_id: int, start: date, end: date) -> None:
        self.repo, self.entity_id, self.start, self.end = repo, entity_id, start, end
        self.policy: RoundingPolicy = load_rounding_policy(ROUNDING_POLICY)
        self.pending: dict[str, CalculationTrace] = {}

    def key(self, canonical_id: str, unit: str) -> MeasurementKey:
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
        ``RUN_CONTEXT``, equal to the run's value."""
        capture = self.repo.find_capture_ref(
            source.source_id, SURFACE_OF[Representation.XBRL].value, source.file_sha256
        )
        found = [
            item
            for item in self._interpretations(capture)
            if item.status is InterpretationStatus.MAPPED
            and _context(item) == RUN_CONTEXT
            and item.key is not None
            and item.key.digest() == key.digest()
        ]
        where = f"{key.canonical_id} in {source.file_sha256[:12]}"
        if len(found) != 1:
            raise RunDraftError(f"no single mapped interpretation of {where}")
        (item,) = found
        if item.value is None or item.interval is None:
            raise RunDraftError(f"interpretation of {where} has no value with precision")
        if item.value != run_value * _scale(key):
            raise RunDraftError(f"interpretation of {where} is {item.value}, the run's {run_value}")
        return name, OperandValue(
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

    def _interpretations(self, capture: CaptureReference | None) -> tuple[Interpretation, ...]:
        """Every interpretation of a registered capture; none of an unregistered one."""
        if capture is None or capture.capture_ref_id is None:
            return ()
        return self.repo.list_capture_interpretations(capture.capture_ref_id)

    def figure(
        self,
        name: str,
        section: str,
        operand: _Operand,
        source: Provenance,
        run_value: Decimal,
        unit: str,
    ) -> NumericClaim:
        """A retained figure's claim at the run's value, cited to its interpretation."""
        held = operand[1]
        assert held.interpretation_id is not None
        claim = _valued(name, section, run_value, unit, held.key, source)
        return cite(claim, interpretation_id=held.interpretation_id)

    def trace(
        self,
        name: str,
        section: str,
        formula: str,
        output: MeasurementKey,
        operands: tuple[_Operand, _Operand],
        run_value: Decimal,
        unit: str,
        **options: Any,
    ) -> NumericClaim:
        """Compute one trace and check it against the run's value; its claim is cited once
        every trace holds and is stored."""
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
            else:
                point = (a.exact / b.exact * 100, a.interval.div(b.interval).mul(_HUNDRED))
        except (UndefinedDivisionError, ZeroDivisionError) as error:
            raise RunDraftError(f"{name}: {formula} is undefined: {error}") from error
        entries = [(operand, TemporalRole.DURATION, value) for operand, value in operands]
        result = conclude(
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
        expected = Fraction(run_value) * _scale(output)
        if result.value != store_value(expected, output.value_kind, self.policy):
            raise RunDraftError(f"{name}: computed {result.value}, the run's {run_value}")
        self.pending[name] = result.trace
        return _valued(name, section, run_value, unit, output, **options)


def bind_computed(
    repo: EvidenceRepository, update: EarningsUpdate, *, entity_id: int
) -> tuple[Line, ...]:
    """The run's changes and calculations lines: a stored trace per retained computed value and
    the interpretation of each comparator figure and the filed tax expense, all bound before
    any trace is stored; any missing interpretation or mismatch raises."""
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    binder = _Binder(repo, entity_id, start, end)
    facts = {fact.role: fact for fact in update.facts}
    by_concept = {fact.concept_qname: fact for fact in update.facts}
    lines: list[Line] = []
    for comparative in update.comparatives:
        fact = by_concept[comparative.concept_qname]
        key, unit = binder.key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit), fact.unit
        current = binder.operand("current", fact.sources[0], key, fact.value)
        for change in (comparative.qoq, comparative.yoy):
            label = f"{_ROLE_LABELS[fact.role]} {change.kind.value} vs "
            label += f"{change.period_start}..{change.period_end}"
            if change.prior_value is None or change.absolute_change is None:
                lines.append(
                    Line(section=CHANGES, label=label, unavailable=change.unavailable_reason)
                )
                continue
            assert change.prior_source is not None
            base = f"cmp.{fact.role.value}.{change.kind.value.lower()}"
            period = PeriodInterval.duration(change.period_start, change.period_end)
            prior = binder.operand(
                "prior",
                change.prior_source,
                key.model_copy(update={"period": period}),
                change.prior_value,
                SelectionSource.HISTORICAL_PACKAGE,
            )
            pair = (current, prior)
            abs_key = change_key(key, change.kind, ABS)
            claims = [
                binder.figure(
                    f"{base}.prior", CHANGES, prior, change.prior_source, change.prior_value, unit
                ),
                binder.trace(
                    f"{base}.abs", CHANGES, DIFFERENCE, abs_key, pair, change.absolute_change, unit
                ),
            ]
            if change.percent_change is not None:
                claims.append(
                    binder.trace(
                        f"{base}.pct",
                        CHANGES,
                        CHANGE_PCT,
                        change_key(key, change.kind, PCT),
                        pair,
                        change.percent_change,
                        PERCENT,
                        precision=RUN_PERCENT_PLACES,
                        rounding=Rounding.ROUND_HALF_EVEN,
                    )
                )
            reason = change.percent_unavailable_reason
            lines.append(
                Line(section=CHANGES, label=label, claims=tuple(claims), unavailable=reason)
            )
    xbrl = facts[FactRole.PROFIT_BEFORE_TAX].sources[0]

    def reported(name: str, role: FactRole) -> _Operand:
        fact = facts[role]
        canonical_id = LEGACY_CONCEPTS[fact.concept_qname]
        return binder.operand(name, fact.sources[0], binder.key(canonical_id, CRORE), fact.value)

    pbt = facts[FactRole.PROFIT_BEFORE_TAX].value
    tax: _Operand | None = None
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
            tax = binder.operand("tax", xbrl, binder.key(TAX, CRORE), value)
            claim = binder.figure(name, CALCS, tax, xbrl, value, CRORE)
        elif label == ETR_LABEL and tax is not None:
            operands = (tax, reported("pbt", FactRole.PROFIT_BEFORE_TAX))
            claim = binder.trace(
                name, CALCS, ETR, binder.key(label, PERCENT), operands, value, PERCENT
            )
        elif label == HEADLINE_LABEL:
            share_key = binder.key(SHARE, CRORE)
            share = binder.operand("share_of_associates", xbrl, share_key, value - pbt)
            operands = (reported("pbt", FactRole.PROFIT_BEFORE_TAX), share)
            claim = binder.trace(name, CALCS, SUM, binder.key(label, CRORE), operands, value, CRORE)
        else:
            raise RunDraftError(f"{name}: no formula for {label!r}")
        lines.append(Line(section=CALCS, label=label, claims=(claim,)))
    traces = {name: repo.put_calculation_trace(trace) for name, trace in binder.pending.items()}

    def stored(claim: NumericClaim) -> NumericClaim:
        trace_id = traces.get(claim.claim_key)
        return claim if trace_id is None else cite(claim, calculation_trace_id=trace_id)

    return tuple(
        line.model_copy(update={"claims": tuple(map(stored, line.claims))}) for line in lines
    )


def cite(claim: NumericClaim, **record: object) -> NumericClaim:
    """``claim`` cited to its stored record."""
    citation = claim.citation.model_copy(update=record)
    return claim.model_copy(update={"citation": citation, "unresolved": False})


def _context(item: Interpretation) -> tuple[str, str, str, str]:
    """The versions an interpretation was made under, in ``RUN_CONTEXT`` order."""
    return (
        item.dictionary_version,
        item.mapping_set_version,
        item.normalisation_policy_version,
        item.extractor_version,
    )


def _scale(key: MeasurementKey) -> int:
    """Base units per unit of a run value under ``key``: INR per crore for an amount, else 1."""
    return _CRORE_SCALE if key.value_kind is ValueKind.CURRENCY_AMOUNT else 1
