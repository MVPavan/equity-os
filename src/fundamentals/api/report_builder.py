"""Bridge a reconciled :class:`StockReport` into a source-verified earnings update.

The Infosys increment assembles an :class:`EarningsUpdate` inside
:mod:`fundamentals.api.pipeline`. This module mirrors that assembly for the
multi-stock validation path: it turns any Wave-1 ``StockReport`` — the output of
:func:`fundamentals.api.goal_runner.reconcile_stock` — into the same 11-section
``EarningsUpdate`` the frozen renderer consumes, and hands it to
:func:`render_earnings_update`.

Design:

* **Generic over the report, never per-symbol.** Every P&L render role is
  resolved the same way for every stock.
* **Provenance threaded from the winning observations.** For each render role the
  bridge reuses the goal runner's own gather (so the comparison column matches the
  reconciliation exactly) and the frozen agreement classifier, then footnotes the
  fact to the provenance of *every first-party observation that agreed* — two
  anchors (NSE XBRL context + BSE results-PDF page/block/span) for a confirmed
  fact, one for a single-source fact.
* **Honest status.** A single-source or conflicting fact is never dressed as
  cross-source-confirmed; the §2 reconciliation column and the §11 cross-check
  ratio both reflect the real agreement outcome.
* **Fail closed.** Only a role with a retained first-party value and provenance is
  rendered. A required role that is missing or conflicting is surfaced with its
  reason; the render then fails closed rather than emitting an un-sourced number.
* **Code is the calculator.** The §9 identities are computed by deterministic
  arithmetic over the sourced role values, each with a trace — never by a model,
  and skipped when an input is unavailable.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.api.watchlist_config import StockConfig, stock_catalog
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.output.earnings_update import (
    EarningsUpdate,
    FactRole,
    RenderedCalculation,
    RenderedFact,
    VerificationOutcome,
    render_earnings_update,
)
from fundamentals.reconcile.agreement import (
    AgreementResult,
    AgreementStatus,
)
from fundamentals.reconcile.fact_view import (
    derived_concept_map,
    role_agreement,
    winning_anchors,
)
from fundamentals.reconcile.report import StockReport

_LOGGER = structlog.get_logger("fundamentals.report_builder")

_PERCENT_QUANTUM = Decimal("0.1")

REASON_NO_OBSERVATION = "no first-party observation carries this required concept"
REASON_NO_RETAINED_VALUE = "cross-source {status}: no first-party value retained (fail-closed)"

_SEC_NOTE_US_LISTED = (
    "SEC 20-F is a retrospective annual source; not cross-footed against this quarter"
)
_SEC_NOTE_NOT_LISTED = "not applicable — issuer not US-listed (no SEC 20-F annual filing)"

# How a cross-source agreement outcome presents as a rendered reconciliation
# state. A single first-party source is UNRECONCILED (not confirmed across
# sources); a conflict is never mapped because it retains no value to render.
_STATUS_MAP: dict[AgreementStatus, ReconciliationStatus] = {
    AgreementStatus.AGREE: ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
    AgreementStatus.MINOR_DIFF: ReconciliationStatus.CROSS_SOURCE_CONFIRMED,
    AgreementStatus.SINGLE_FIRST_PARTY: ReconciliationStatus.UNRECONCILED,
    AgreementStatus.CONFLICT: ReconciliationStatus.CONFLICT,
}


class ReportBuildError(RuntimeError):
    """Raised when a stock cannot yield a complete, source-verified report."""


class UnresolvedRole(BaseModel):
    """A required render role with no retained first-party value, and why."""

    model_config = ConfigDict(frozen=True)

    role: FactRole
    concept_qname: str
    reason: str


class ReportBuild(BaseModel):
    """The assembled render input plus any required roles that could not resolve."""

    model_config = ConfigDict(frozen=True)

    update: EarningsUpdate
    unresolved: tuple[UnresolvedRole, ...]

    @property
    def renderable(self) -> bool:
        """Whether every required role resolved, so the update renders fail-closed-safe."""
        return not self.unresolved


def _rendered_fact(role: FactRole, concept: str, result: AgreementResult) -> RenderedFact:
    """Build the render-ready fact for a role from its retained agreement result."""
    assert result.agreed_value is not None  # guarded by the caller
    return RenderedFact(
        role=role,
        concept_qname=concept,
        value=result.agreed_value,
        unit=result.normalized_unit,
        reconciliation_status=_STATUS_MAP[result.status],
        sources=winning_anchors(result),
    )


def _format_crore(value: Decimal) -> str:
    """Format a crore value with thousands grouping, preserving real decimals."""
    if value == value.to_integral_value():
        return f"{value.to_integral_value():,}"
    return f"{value.normalize():,}"


def _calculations(role_values: dict[FactRole, Decimal]) -> tuple[RenderedCalculation, ...]:
    """Derive the sourced P&L identities in code, skipping any missing an input.

    Each calculation is deterministic arithmetic over already-sourced role values
    and carries a trace; the model is never the calculator. A calculation whose
    inputs are not all present is omitted rather than guessed.
    """
    calculations: list[RenderedCalculation] = []

    income = role_values.get(FactRole.TOTAL_INCOME)
    revenue = role_values.get(FactRole.REVENUE)
    if income is not None and revenue is not None:
        gap = income - revenue
        calculations.append(
            RenderedCalculation(
                label="Non-operating / other income gap (₹ crore)",
                result=_format_crore(gap),
                trace=(
                    f"Total income {_format_crore(income)} − "
                    f"Revenue from operations {_format_crore(revenue)}"
                ),
            )
        )

    pbt = role_values.get(FactRole.PROFIT_BEFORE_TAX)
    pat = role_values.get(FactRole.PROFIT_FOR_PERIOD)
    if pbt is not None and pat is not None and pbt != 0:
        net_tax = pbt - pat
        effective_tax = (net_tax / pbt * Decimal(100)).quantize(_PERCENT_QUANTUM)
        pbt_str = _format_crore(pbt)
        pat_str = _format_crore(pat)
        calculations.append(
            RenderedCalculation(
                label="Net tax expense (₹ crore)",
                result=_format_crore(net_tax),
                trace=f"Profit before tax {pbt_str} − Profit for the period {pat_str}",
            )
        )
        calculations.append(
            RenderedCalculation(
                label="Effective tax rate (%)",
                result=f"{effective_tax}",
                trace=f"(PBT {pbt_str} − PAT {pat_str}) / PBT {pbt_str}",
            )
        )

    return tuple(calculations)


def _cross_check_outcome(
    cross_check_concepts: tuple[str, ...],
    results: dict[str, AgreementResult | None],
) -> VerificationOutcome:
    """Count how many cross-checked headline figures reached cross-source AGREE."""
    passed = 0
    total = 0
    for concept in cross_check_concepts:
        result = results.get(concept)
        if result is None or result.agreed_value is None:
            continue
        total += 1
        if result.status is AgreementStatus.AGREE:
            passed += 1
    return VerificationOutcome(passed_count=passed, total_count=total)


def _cross_foot_outcome(report: StockReport) -> VerificationOutcome:
    """Project the report's cross-foot identities into the render verification gate."""
    passed = sum(
        1 for identity in report.cross_foot if identity.passed and not identity.flagged_for_review
    )
    return VerificationOutcome(passed_count=passed, total_count=len(report.cross_foot))


def _sec_note(stock: StockConfig) -> str:
    """The §11 SEC-cross-check note appropriate to the issuer's listing status."""
    if stock.identifiers.us_listed:
        return _SEC_NOTE_US_LISTED
    return _SEC_NOTE_NOT_LISTED


def build_report(report: StockReport, stock: StockConfig) -> ReportBuild:
    """Assemble the render input for one reconciled stock, surfacing unresolved roles.

    For every configured P&L render role the bridge re-derives the cross-source
    agreement from the report's collected observations (reusing the reconciliation's
    own gather and classifier), threads the winning first-party anchors, and maps
    the agreement status to an honest reconciliation state. A required role with no
    retained first-party value is recorded in ``unresolved`` (not fabricated), so
    the caller can fail closed with a reason.
    """
    concepts = stock.concepts
    derived_map = derived_concept_map(concepts.roles)

    needed: dict[str, None] = {role.concept_qname: None for role in concepts.roles}
    for concept in concepts.cross_check:
        needed.setdefault(concept, None)
    results: dict[str, AgreementResult | None] = {
        concept: role_agreement(
            concept,
            report.sources,
            symbol=stock.symbol,
            period_start=stock.quarter.period_start,
            period_end=stock.quarter.period_end,
            derived_map=derived_map,
            catalog=stock_catalog(stock),
        )
        for concept in needed
    }

    rendered_facts: list[RenderedFact] = []
    unresolved: list[UnresolvedRole] = []
    role_values: dict[FactRole, Decimal] = {}
    for role_concept in concepts.roles:
        role = role_concept.role
        concept = role_concept.concept_qname
        result = results[concept]
        if result is None:
            unresolved.append(
                UnresolvedRole(role=role, concept_qname=concept, reason=REASON_NO_OBSERVATION)
            )
            continue
        if result.agreed_value is None:
            unresolved.append(
                UnresolvedRole(
                    role=role,
                    concept_qname=concept,
                    reason=REASON_NO_RETAINED_VALUE.format(status=result.status.value),
                )
            )
            continue
        rendered_facts.append(_rendered_fact(role, concept, result))
        role_values[role] = result.agreed_value

    update = EarningsUpdate(
        issuer_name=stock.name,
        nse_symbol=stock.symbol,
        issuer_quarter_label=stock.quarter.label,
        period_start=stock.quarter.period_start.isoformat(),
        period_end=stock.quarter.period_end.isoformat(),
        knowledge_cutoff=stock.quarter.knowledge_cutoff.date().isoformat(),
        facts=tuple(rendered_facts),
        comparatives=report.comparatives,
        comparatives_attempted=True,
        guidance=(),
        calculations=_calculations(role_values),
        cross_check=_cross_check_outcome(concepts.cross_check, results),
        cross_foot=_cross_foot_outcome(report),
        sec_cross_check_note=_sec_note(stock),
    )

    _LOGGER.info(
        "report_built",
        symbol=stock.symbol,
        quarter=stock.quarter.label,
        rendered_facts=len(rendered_facts),
        unresolved=[item.role.value for item in unresolved],
        cross_source_confirmed=sum(
            1
            for fact in rendered_facts
            if fact.reconciliation_status is ReconciliationStatus.CROSS_SOURCE_CONFIRMED
        ),
    )
    return ReportBuild(update=update, unresolved=tuple(unresolved))


def render_report(report: StockReport, stock: StockConfig) -> str:
    """Build and render the source-verified markdown, failing closed with reasons.

    Raises :class:`ReportBuildError` if any required role could not be resolved to a
    sourced value, so no partial or un-sourced report is ever produced.
    """
    build = build_report(report, stock)
    if not build.renderable:
        reasons = "; ".join(f"{item.role.value}: {item.reason}" for item in build.unresolved)
        raise ReportBuildError(f"cannot render {stock.symbol} {stock.quarter.label}: {reasons}")
    return render_earnings_update(build.update)
