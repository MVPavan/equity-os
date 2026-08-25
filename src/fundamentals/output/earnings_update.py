"""Render the frozen 11-section A-04 earnings update as sourced markdown.

Every number in the fact and guidance sections is footnoted to the exact source
anchor (an issuer PDF page/block/span or an NSE XBRL context) of the stored,
provenance-bound value it came from. A missing *required* P&L fact does not
silently drop a line — it raises :class:`RenderError` and aborts the whole
render, honouring the product's fail-closed doctrine (roadmap §12).

This module renders; it does not verify. The pipeline is responsible for having
already cross-checked and cross-footed every fact it hands in. The interpretive
sections (§4, §6, §7, §8, §10) carry no pipeline-sourced numbers: the
deterministic pipeline does not synthesise analyst narrative, so those numeric
claims stay out of scope rather than being fabricated here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Context, Decimal, DecimalException, localcontext
from enum import StrEnum
from typing import Final, assert_never

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.comparative import (
    PERCENT_CONTEXT_PRECISION,
    ComparativeChange,
    ConceptComparative,
)
from fundamentals.contracts.fact import ReconciliationStatus
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole as FactRole

_CRORE_UNIT = "INR crore"
_PER_SHARE_UNIT = "INR per share"
_PERCENT_UNIT: Final = "percent"
_SHA_PREFIX_LEN = 12
_PERCENT_QUANTUM = Decimal("0.1")


class RenderError(RuntimeError):
    """Raised when a required fact is absent — the render fails closed."""


REQUIRED_ROLES: tuple[FactRole, ...] = (
    FactRole.REVENUE,
    FactRole.TOTAL_INCOME,
    FactRole.TOTAL_EXPENSES,
    FactRole.PROFIT_BEFORE_TAX,
    FactRole.PROFIT_FOR_PERIOD,
    FactRole.BASIC_EPS,
)

_ROLE_LABELS: dict[FactRole, str] = {
    FactRole.REVENUE: "Revenue from operations",
    FactRole.TOTAL_INCOME: "Total income",
    FactRole.TOTAL_EXPENSES: "Total expenses",
    FactRole.PROFIT_BEFORE_TAX: "Profit before tax",
    FactRole.PROFIT_FOR_PERIOD: "Profit for the period (PAT)",
    FactRole.BASIC_EPS: "EPS basic (₹)",
}


def anchor_label(provenance: Provenance) -> str:
    """Human-readable one-line description of a provenance anchor."""
    sha = provenance.file_sha256[:_SHA_PREFIX_LEN]
    if provenance.anchor_type is SourceAnchorType.PDF_SPAN:
        location = f"page {provenance.page}, block {provenance.block}, span {provenance.span}"
    elif provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT:
        location = f"context {provenance.context_ref}"
    elif provenance.anchor_type is SourceAnchorType.JSON_ISLAND:
        location = (
            f"JSON island {provenance.island_id}, table {provenance.table_key}, "
            f"row {provenance.row_label}, column {provenance.column_label}"
        )
    elif provenance.anchor_type is SourceAnchorType.HTML_TABLE:
        location = (
            f"HTML table {provenance.table_id}, row {provenance.row_path}, "
            f"column {provenance.column_index} ({provenance.column_label})"
        )
    else:
        assert_never(provenance.anchor_type)
    return f"{provenance.source_id}: {location} (file sha256 {sha}…)"


class VerificationState(StrEnum):
    """The only accepted rendered verification states — never a caller string."""

    PASS = "PASS"
    FAIL = "FAIL"


class VerificationOutcome(BaseModel):
    """A verification gate's result, derived from real pass/total counts.

    The rendered ``state`` is computed from the counts, so a caller cannot make
    the artifact claim ``PASS`` by supplying an arbitrary summary string.
    """

    model_config = ConfigDict(frozen=True)

    passed_count: int
    total_count: int

    @property
    def state(self) -> VerificationState:
        """PASS only when every counted gate actually passed (and at least one ran)."""
        if self.total_count > 0 and self.passed_count == self.total_count:
            return VerificationState.PASS
        return VerificationState.FAIL


class RenderedFact(BaseModel):
    """One P&L fact ready to render, with every backing source anchor."""

    model_config = ConfigDict(frozen=True)

    role: FactRole
    concept_qname: str
    value: Decimal
    unit: str
    reconciliation_status: ReconciliationStatus
    sources: tuple[Provenance, ...]


class RenderedGuidance(BaseModel):
    """One management-guidance range with its quote-anchored source."""

    model_config = ConfigDict(frozen=True)

    metric_label: str
    lower_bound: Decimal
    upper_bound: Decimal
    unit: str
    constant_currency: bool
    horizon: str
    quote: str
    source: Provenance


class RenderedCalculation(BaseModel):
    """One derived value, traced over already-sourced stored facts."""

    model_config = ConfigDict(frozen=True)

    label: str
    result: str
    trace: str


class EarningsUpdate(BaseModel):
    """All data the 11-section render needs, assembled by the pipeline."""

    model_config = ConfigDict(frozen=True)

    issuer_name: str
    nse_symbol: str
    issuer_quarter_label: str
    period_start: str
    period_end: str
    knowledge_cutoff: str
    facts: tuple[RenderedFact, ...]
    comparatives: tuple[ConceptComparative, ...] = ()
    comparatives_attempted: bool = False
    guidance: tuple[RenderedGuidance, ...]
    calculations: tuple[RenderedCalculation, ...]
    cross_check: VerificationOutcome
    cross_foot: VerificationOutcome
    sec_cross_check_note: str


def _format_value(value: Decimal, unit: str) -> str:
    """Format a crore value with grouping (preserving decimals), or EPS to 2 dp."""
    if unit == _PER_SHARE_UNIT:
        return f"{value:.2f}"
    if unit == _CRORE_UNIT:
        if value == value.to_integral_value():
            return f"{value.to_integral_value():,}"
        return f"{value.normalize():,}"
    return str(value)


def _format_signed(value: Decimal, unit: str) -> str:
    """Format a change with an explicit sign and the concept's presentation unit."""
    sign = "+" if value > 0 else ""
    return f"{sign}{_format_value(value, unit)}"


def _escape_markdown_cell(value: str) -> str:
    """Keep dynamic text inside one Markdown table cell."""
    return " ".join(value.splitlines()).replace("|", r"\|")


def _comparator_period_label(period_start: date, period_end: date) -> str:
    """Render an Indian fiscal-quarter label plus the comparator's exact dates."""
    quarter = ((period_end.month - 4) % 12) // 3 + 1
    fiscal_year_end = period_end.year + 1 if period_end.month >= 4 else period_end.year
    return (
        f"Q{quarter}FY{fiscal_year_end % 100:02d} "
        f"{period_start.isoformat()}..{period_end.isoformat()}"
    )


class _Footnotes:
    """Assigns stable ``[^n]`` markers to distinct provenance anchors."""

    def __init__(self) -> None:
        self._order: list[str] = []
        self._index: dict[str, int] = {}

    def marker(self, provenance: Provenance) -> str:
        """Return the footnote marker for a provenance, registering it once."""
        label = anchor_label(provenance)
        if label not in self._index:
            self._order.append(label)
            self._index[label] = len(self._order)
        return f"[^{self._index[label]}]"

    def markers(self, sources: Sequence[Provenance]) -> str:
        """Return the concatenated markers for a fact's backing sources."""
        return "".join(self.marker(source) for source in sources)

    def render(self) -> str:
        """Render the collected footnote definitions, in first-seen order."""
        lines = [f"[^{number}]: {label}" for number, label in enumerate(self._order, start=1)]
        return "\n".join(lines)


def _render_change(
    comparative: ConceptComparative,
    change: ComparativeChange,
    notes: _Footnotes,
) -> tuple[str, str | None]:
    """Render one prior value and its traced changes, or its explicit failure reason."""
    period = _comparator_period_label(change.period_start, change.period_end)
    if not change.available:
        return f"not available ({period}; {change.unavailable_reason})", None
    assert comparative.current_value is not None
    assert comparative.unit is not None
    assert change.prior_value is not None
    assert change.absolute_change is not None
    assert change.prior_source is not None

    current_markers = notes.markers(comparative.current_sources)
    prior_marker = notes.marker(change.prior_source)
    endpoint_markers = f"{current_markers}{prior_marker}"
    prior = _format_value(change.prior_value, comparative.unit)
    delta = _format_signed(change.absolute_change, comparative.unit)
    if change.percent_change is None:
        percent = f"n/a ({change.percent_unavailable_reason})"
        percent_trace = ""
    else:
        try:
            with localcontext(Context(prec=PERCENT_CONTEXT_PRECISION)):
                rounded_percent = change.percent_change.quantize(_PERCENT_QUANTUM)
                formatted_percent = _format_signed(rounded_percent, _PERCENT_UNIT)
        except DecimalException:
            percent = "n/a (percent cannot be represented safely)"
            percent_trace = ""
        else:
            percent = f"{formatted_percent}%{endpoint_markers}"
            percent_trace = (
                f"; % trace: ({comparative.current_value}{current_markers} − "
                f"{change.prior_value}{prior_marker}) / "
                f"{change.prior_value}{prior_marker} × 100"
            )
    absolute_trace = (
        f"trace: {comparative.current_value}{current_markers} − {change.prior_value}{prior_marker}"
    )
    return (
        f"{prior}{prior_marker} ({period}); Δ {delta}{endpoint_markers}; {percent}",
        f"{change.kind.value} {absolute_trace}{percent_trace}",
    )


def _render_comparatives(
    comparatives: Sequence[ConceptComparative],
    facts: Sequence[RenderedFact],
    notes: _Footnotes,
    *,
    attempted: bool,
) -> list[str]:
    """Render the section-3 table over every configured material concept."""
    if not comparatives:
        if attempted:
            return ["No prior-period comparator filings were available for this report."]
        return [
            "Prior-period comparatives were not attempted for this single-issuer pipeline path."
        ]
    labels = {fact.concept_qname: _ROLE_LABELS[fact.role] for fact in facts}
    lines = [
        "| P&L line | Current | QoQ prior / change | YoY prior / change |",
        "| --- | ---: | --- | --- |",
    ]
    traces: list[str] = []
    for comparative in comparatives:
        label = _escape_markdown_cell(
            labels.get(comparative.concept_qname, f"`{comparative.concept_qname}`")
        )
        if comparative.current_value is None or comparative.unit is None:
            current = f"not available ({comparative.current_unavailable_reason})"
        else:
            current = (
                f"{_format_value(comparative.current_value, comparative.unit)}"
                f"{notes.markers(comparative.current_sources)}"
            )
        qoq_cell, qoq_trace = _render_change(comparative, comparative.qoq, notes)
        yoy_cell, yoy_trace = _render_change(comparative, comparative.yoy, notes)
        lines.append(
            f"| {label} | {_escape_markdown_cell(current)} | "
            f"{_escape_markdown_cell(qoq_cell)} | {_escape_markdown_cell(yoy_cell)} |"
        )
        traces.extend(f"- {label} {trace}" for trace in (qoq_trace, yoy_trace) if trace is not None)
    if traces:
        lines.extend(("", "Computed traces:", "", *traces))
    return lines


def _require_all_roles(facts: Sequence[RenderedFact]) -> dict[FactRole, RenderedFact]:
    """Index facts by role, failing closed if any required role is absent.

    A required fact with no backing source anchor is also rejected: an un-sourced
    number must never render.
    """
    by_role = {fact.role: fact for fact in facts}
    missing = [role.value for role in REQUIRED_ROLES if role not in by_role]
    if missing:
        raise RenderError(
            f"cannot render Q1 update: required facts missing {sorted(missing)} "
            "(fail-closed — no un-sourced output is produced)"
        )
    unsourced = [role.value for role in REQUIRED_ROLES if not by_role[role].sources]
    if unsourced:
        raise RenderError(
            f"cannot render Q1 update: facts with no source anchor {sorted(unsourced)} "
            "(fail-closed — no un-sourced number may render)"
        )
    return by_role


def render_earnings_update(update: EarningsUpdate) -> str:
    """Render the 11-section sourced markdown, failing closed on missing facts."""
    by_role = _require_all_roles(update.facts)
    notes = _Footnotes()

    lines: list[str] = []
    lines.append(f"# {update.issuer_name} ({update.nse_symbol}) — {update.issuer_quarter_label}")
    lines.append("")
    lines.append(
        "*Source-verified earnings update. Basis: consolidated, Ind AS, ₹ crore. "
        "Every figure below is footnoted to its held-source anchor.*"
    )
    lines.append("")

    lines.append("## 1. event_and_cutoff")
    lines.append("")
    lines.append(
        f"Event under review: {update.issuer_name} {update.issuer_quarter_label} consolidated "
        f"results (issuer results PDF and NSE Ind AS XBRL), period "
        f"{update.period_start} → {update.period_end}. Information cutoff: "
        f"**{update.knowledge_cutoff}**; anything later is out of scope."
    )
    lines.append("")

    lines.append("## 2. facts")
    lines.append("")
    lines.append("| P&L line | Value | XBRL concept | Reconciliation | Source |")
    lines.append("| --- | ---: | --- | --- | --- |")
    for role in REQUIRED_ROLES:
        fact = by_role[role]
        value = _format_value(fact.value, fact.unit)
        markers = notes.markers(fact.sources)
        lines.append(
            f"| {_ROLE_LABELS[role]} | {value} | `{fact.concept_qname}` | "
            f"{fact.reconciliation_status} | {markers} |"
        )
    lines.append("")

    lines.append("## 3. changes")
    lines.append("")
    lines.extend(
        _render_comparatives(
            update.comparatives,
            update.facts,
            notes,
            attempted=update.comparatives_attempted,
        )
    )
    lines.append("")

    lines.append("## 4. drivers")
    lines.append("")
    lines.append(
        "Driver commentary is analyst-authored narrative and is intentionally not synthesised by "
        "the deterministic pipeline. See the calculations section for the sourced arithmetic that "
        "any driver reading must respect."
    )
    lines.append("")

    lines.append("## 5. management_ledger")
    lines.append("")
    if update.guidance:
        lines.append(
            "Management commitments to track (each quote-anchored in the held transcript):"
        )
        lines.append("")
        for claim in update.guidance:
            cc = " constant currency" if claim.constant_currency else ""
            marker = notes.marker(claim.source)
            lines.append(
                f"- {claim.metric_label} **{claim.lower_bound}–{claim.upper_bound}"
                f"{claim.unit}{cc}** for {claim.horizon} "
                f"[FORECAST]{marker} — quoted: “{claim.quote}”"
            )
        lines.append("")
    else:
        lines.append("No management-guidance ranges were extracted for this quarter.")
        lines.append("")

    lines.append("## 6. thesis_impact")
    lines.append("")
    lines.append(
        "Thesis impact is an analyst judgement, not a pipeline output; it is left to the analyst "
        "layer so no un-sourced interpretation enters this source-verified artifact."
    )
    lines.append("")

    lines.append("## 7. observable_falsifiers")
    lines.append("")
    lines.append(
        "Falsifiers are analyst-authored and tracked against the sourced facts and the "
        "management ledger above; they are not generated by the deterministic pipeline."
    )
    lines.append("")

    lines.append("## 8. open_questions")
    lines.append("")
    lines.append(
        "Open analytical questions are maintained by the analyst layer; the pipeline surfaces "
        "only what the held sources prove."
    )
    lines.append("")

    lines.append("## 9. calculations")
    lines.append("")
    if update.calculations:
        for calc in update.calculations:
            lines.append(f"- **{calc.label}** = {calc.result}. [computed — trace: {calc.trace}]")
        lines.append("")
    else:
        lines.append("No derived calculations for this quarter.")
        lines.append("")

    lines.append("## 10. non_canonical_memory_draft")
    lines.append("")
    lines.append(
        "**Non-canonical — never a source of truth.** A durable memory draft is an analyst "
        "artifact and is deliberately not emitted by this deterministic pipeline."
    )
    lines.append("")

    lines.append("## 11. approval_record")
    lines.append("")
    lines.append("| Verification gate | State |")
    lines.append("| --- | --- |")
    cross_check = update.cross_check
    cross_foot = update.cross_foot
    lines.append(
        f"| XBRL ↔ PDF cross-check (headline figures) | {cross_check.state} — "
        f"{cross_check.passed_count}/{cross_check.total_count} headline figures agree "
        "within decimals-derived tolerance |"
    )
    lines.append(
        f"| Cross-foot accounting identities | {cross_foot.state} — "
        f"{cross_foot.passed_count}/{cross_foot.total_count} identities hold at ±0 |"
    )
    lines.append(f"| SEC 20-F annual cross-check | {update.sec_cross_check_note} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### Sources")
    lines.append("")
    lines.append(notes.render())
    lines.append("")

    return "\n".join(lines)
