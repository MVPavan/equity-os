"""Deterministic falsifier evaluation and analyst-facing markdown rendering."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from fundamentals.output.earnings_update import EarningsUpdate, anchor_label
from fundamentals.verify.metric_registry import (
    METRIC_REGISTRY_VERSION,
    MetricUnavailable,
    MetricValue,
    resolve_metric,
)
from fundamentals.verify.thesis_predicates import (
    PREDICATE_REGISTRY_VERSION,
    ApprovedThesis,
    FalsifierPredicate,
    PredicateOp,
)


class Disposition(StrEnum):
    """The possible outcomes of a deterministic falsifier evaluation."""

    WEAKENED = "WEAKENED"
    HELD = "HELD"
    UNRESOLVED = "UNRESOLVED"


class FalsifierEvaluation(BaseModel):
    """One analyst falsifier's evidence-bound result."""

    model_config = ConfigDict(frozen=True)

    falsifier_id: str
    statement: str
    metric_id: str
    op: PredicateOp
    threshold: Decimal | None = None
    band: tuple[Decimal, Decimal] | None = None
    observed: MetricValue | None
    disposition: Disposition
    reason: str | None = None


class ThesisImpact(BaseModel):
    """All falsifier outcomes for one thesis and earnings update."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    issuer_quarter: str
    thesis_version: str
    thesis_sha256: str
    metric_registry_version: str
    predicate_registry_version: str
    evaluations: tuple[FalsifierEvaluation, ...]
    counts: dict[Disposition, int]


def _predicate_holds(predicate: FalsifierPredicate, observed: MetricValue) -> bool:
    """Return whether a sourced metric triggers one registered predicate."""
    value = observed.value
    if predicate.op is PredicateOp.LT:
        assert predicate.threshold is not None
        return value < predicate.threshold
    if predicate.op is PredicateOp.LTE:
        assert predicate.threshold is not None
        return value <= predicate.threshold
    if predicate.op is PredicateOp.GT:
        assert predicate.threshold is not None
        return value > predicate.threshold
    if predicate.op is PredicateOp.GTE:
        assert predicate.threshold is not None
        return value >= predicate.threshold
    assert predicate.band is not None
    return value < predicate.band[0] or value > predicate.band[1]


def evaluate_thesis(update: EarningsUpdate, thesis: ApprovedThesis) -> ThesisImpact:
    """Evaluate every approved falsifier against one matching issuer update."""
    if update.nse_symbol != thesis.symbol:
        raise ValueError("thesis symbol does not match earnings update symbol")
    evaluations: list[FalsifierEvaluation] = []
    for falsifier in thesis.falsifiers:
        resolved = resolve_metric(update, falsifier.predicate.metric_id)
        if isinstance(resolved, MetricUnavailable):
            evaluations.append(
                FalsifierEvaluation(
                    falsifier_id=falsifier.falsifier_id,
                    statement=falsifier.statement,
                    metric_id=falsifier.predicate.metric_id,
                    op=falsifier.predicate.op,
                    threshold=falsifier.predicate.threshold,
                    band=falsifier.predicate.band,
                    observed=None,
                    disposition=Disposition.UNRESOLVED,
                    reason=resolved.reason,
                )
            )
            continue
        disposition = (
            Disposition.WEAKENED
            if _predicate_holds(falsifier.predicate, resolved)
            else Disposition.HELD
        )
        evaluations.append(
            FalsifierEvaluation(
                falsifier_id=falsifier.falsifier_id,
                statement=falsifier.statement,
                metric_id=falsifier.predicate.metric_id,
                op=falsifier.predicate.op,
                threshold=falsifier.predicate.threshold,
                band=falsifier.predicate.band,
                observed=resolved,
                disposition=disposition,
            )
        )
    counts = Counter(evaluation.disposition for evaluation in evaluations)
    return ThesisImpact(
        symbol=update.nse_symbol,
        issuer_quarter=update.issuer_quarter_label,
        thesis_version=thesis.version,
        thesis_sha256=thesis.content_sha256,
        metric_registry_version=METRIC_REGISTRY_VERSION,
        predicate_registry_version=PREDICATE_REGISTRY_VERSION,
        evaluations=tuple(evaluations),
        counts=dict(counts),
    )


def _table_cell(value: str) -> str:
    """Keep dynamic content inside one markdown table cell."""
    return " ".join(value.splitlines()).replace("|", r"\|")


def _rule(evaluation: FalsifierEvaluation) -> str:
    """Render one registered predicate in its analyst-readable form."""
    if evaluation.band is not None:
        return f"{evaluation.op} {evaluation.band[0]}..{evaluation.band[1]}"
    return f"{evaluation.op} {evaluation.threshold}"


def render_thesis_impact(impact: ThesisImpact) -> str:
    """Render the deterministic signal while reserving narrative for the analyst."""
    lines = [
        "## 6. thesis_impact",
        "",
        (
            "This deterministic falsifier signal is evidence-bound; the narrative remains "
            "analyst-authored."
        ),
        "",
        "| Disposition | Count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {disposition} | {impact.counts.get(disposition, 0)} |" for disposition in Disposition
    )
    lines.extend(
        (
            "",
            "## 7. observable_falsifiers",
            "",
            "| ID | Statement | Metric | Observed | Rule | Disposition | Sources |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        )
    )
    for evaluation in impact.evaluations:
        if evaluation.observed is None:
            observed = "—"
            sources = "—"
        else:
            observed = f"{evaluation.observed.value} {evaluation.observed.unit}"
            sources = "<br>".join(anchor_label(source) for source in evaluation.observed.sources)
        if evaluation.reason is not None:
            sources = f"{sources}<br>reason: {evaluation.reason}"
        lines.append(
            "| "
            f"{_table_cell(evaluation.falsifier_id)} | "
            f"{_table_cell(evaluation.statement)} | "
            f"{_table_cell(evaluation.metric_id)} | "
            f"{_table_cell(observed)} | "
            f"{_table_cell(_rule(evaluation))} | "
            f"{_table_cell(str(evaluation.disposition))} | "
            f"{_table_cell(sources)} |"
        )
    return "\n".join(lines) + "\n"
