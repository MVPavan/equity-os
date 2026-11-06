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

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext
from enum import StrEnum
from typing import Final, assert_never

from pydantic import BaseModel, ConfigDict, Field

from equity_os.contracts.measurement.fact import ReconciliationStatus
from equity_os.contracts.measurement.provenance import Provenance, SourceAnchorType
from equity_os.contracts.measurement.role import FactRole as FactRole
from equity_os.contracts.verification.comparative import (
    PERCENT_CONTEXT_PRECISION,
    RUN_PERCENT_PLACES,
    TAXONOMY_DRIFT_PREFIX,
    ComparativeChange,
    ConceptComparative,
)
from equity_os.contracts.verification.vendor_first import LABEL_TEXT, AdmissionLabel, weakest
from equity_os.publication.checking.claim_check import UNITS
from equity_os.publication.drafting.management_ledger import LedgerStatus, ManagementLedger
from equity_os.storage.facts.fact_store import FactRef

_CRORE_UNIT = "INR crore"
_PERCENT = Decimal(1).scaleb(-RUN_PERCENT_PLACES)  # a run's percent change, as comparatives
_PER_SHARE_UNIT = "INR per share"
_PERCENT_UNIT: Final = "percent"
_SHA_PREFIX_LEN = 12
RETROSPECTIVE_LABEL: Final = (
    "Retrospective workflow demonstration: originals registered after the source cutoff were "
    "admitted as published by it; this cannot prove historical possession or absence of "
    "hindsight."
)


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
    FactRole.PROFIT_BEFORE_TAX: "Profit before tax (before share of associates/JV)",
    FactRole.PROFIT_FOR_PERIOD: "Profit for the period (PAT)",
    FactRole.BASIC_EPS: "EPS basic (₹)",
}


def anchor_label(provenance: Provenance) -> str:
    """Human-readable one-line description of a provenance anchor."""
    sha = provenance.file_sha256[:_SHA_PREFIX_LEN]
    if provenance.anchor_type is SourceAnchorType.PDF_SPAN:
        location = f"page {provenance.page}, block {provenance.block}, span {provenance.span}"
    elif provenance.anchor_type is SourceAnchorType.PDF_CELL:
        location = (
            f"page {provenance.page}, line {provenance.row_path}, "
            f"column {provenance.column_index} ({provenance.table_key})"
        )
    elif provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT:
        location = f"context {provenance.context_ref}"
    elif provenance.anchor_type is SourceAnchorType.JSON_ISLAND:
        location = (
            f"JSON island {provenance.island_id}, table {provenance.table_key}, "
            f"row {provenance.row_label}, column {provenance.column_label}"
        )
    elif provenance.anchor_type is SourceAnchorType.API_DOCUMENT:
        location = (
            f"API document {provenance.document_id}, key {provenance.table_key}, "
            f"row {provenance.row_label}, field {provenance.column_label}"
        )
    elif provenance.anchor_type in (SourceAnchorType.HTML_TABLE, SourceAnchorType.CSV_RECORD):
        kind = "HTML table" if provenance.anchor_type is SourceAnchorType.HTML_TABLE else "CSV"
        location = (
            f"{kind} {provenance.table_id}, row {provenance.row_path}, "
            f"column {provenance.column_index} ({provenance.column_label})"
        )
    elif provenance.anchor_type is SourceAnchorType.CONFIG_PIN:
        location = f"config pin {provenance.row_label}, field {provenance.column_label}"
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


class AdmittedFact(BaseModel):
    """A role's admitted and selected fact: its ref, base-unit value and precision, provenance,
    label, chosen interpretation and, for a vendor value, the other witness's."""

    model_config = ConfigDict(frozen=True)

    ref: FactRef
    value: Decimal
    decimals: int
    provenance: Provenance
    label: AdmissionLabel
    interpretation_id: int
    witness_interpretation_id: int | None


class RenderedFact(BaseModel):
    """One P&L fact ready to render, with every filed source anchor and, when admitted, the
    admitted fact its value is."""

    model_config = ConfigDict(frozen=True)

    role: FactRole
    concept_qname: str
    value: Decimal
    unit: str
    reconciliation_status: ReconciliationStatus
    sources: tuple[Provenance, ...]
    admitted: AdmittedFact | None = None


class RenderedGuidance(BaseModel):
    """One management-guidance range with its quote-anchored source."""

    model_config = ConfigDict(frozen=True)

    # None marks legacy label-based identity; canonical metrics are copied verbatim.
    metric: str | None = Field(default=None, pattern=r"\S")
    metric_label: str
    lower_bound: Decimal
    upper_bound: Decimal
    unit: str
    constant_currency: bool
    horizon: str
    quote: str
    source: Provenance


class RenderedCalculation(BaseModel):
    """One derived value, traced over already-sourced stored facts; ``operands`` are the roles
    it computes from, whose admitted facts' weakest label qualifies it."""

    model_config = ConfigDict(frozen=True)

    label: str
    result: str
    trace: str
    operands: tuple[FactRole, ...] = ()


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
    ledger: ManagementLedger | None = None
    # A run's contract (c) label and cutoffs; a retained generator twin has none and states
    # percent changes at 0.1.
    retrospective: bool | None = None
    source_cutoff: datetime | None = None
    derivation_cutoff: datetime | None = None
    percent_places: int = 1
    diagnostic_label: str | None = None
    # A role's QoQ prior the predecessor head admitted from the vendors (VENDOR-1 finding 3).
    predecessors: Mapping[FactRole, AdmittedFact] = {}


def _format_bounds(lower: Decimal, upper: Decimal) -> str:
    """Render a guidance range, collapsing a point commitment to one value."""
    return str(lower) if lower == upper else f"{lower}–{upper}"


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


def _qualifier(facts: Sequence[AdmittedFact | None]) -> str:
    """The admitted facts' weakest label as a trailing qualifier; none when none is admitted."""
    labels = [fact.label for fact in facts if fact is not None]
    return f" ({LABEL_TEXT[weakest(labels)]})" if labels else ""


def predecessor_change(
    change: ComparativeChange, current: Decimal, prior: AdmittedFact, unit: str
) -> ComparativeChange:
    """An available QoQ change against the predecessor head's admitted fact: its value in
    ``unit`` and file, the changes computed from it."""
    value = prior.value / (UNITS[unit][2] or 1)
    absolute, percent = current - value, change.percent_change
    if percent is not None:
        with localcontext(Context(prec=PERCENT_CONTEXT_PRECISION)):
            percent = (absolute / value * 100).quantize(_PERCENT, ROUND_HALF_EVEN)
    update = {"prior_value": value, "prior_source": prior.provenance}
    return change.model_copy(
        update=update | {"absolute_change": absolute, "percent_change": percent}
    )


def _render_change(
    comparative: ConceptComparative,
    change: ComparativeChange,
    notes: _Footnotes,
    places: int,
    current_markers: str,
    qualifier: str,
    prior_qualifier: str = "",
) -> tuple[str, str | None]:
    """Render one prior value and its traced changes, or its explicit failure reason; the
    current value is footnoted by ``current_markers``, the prior qualified by
    ``prior_qualifier`` and the change by ``qualifier``."""
    period = _comparator_period_label(change.period_start, change.period_end)
    if not change.available:
        return f"not available ({period}; {change.unavailable_reason})", None
    assert comparative.current_value is not None
    assert comparative.unit is not None
    assert change.prior_value is not None
    assert change.absolute_change is not None
    assert change.prior_source is not None

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
                rounded_percent = change.percent_change.quantize(Decimal(1).scaleb(-places))
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
    drift_note = (
        f" (taxonomy drift accepted: {change.taxonomy_drift.removeprefix(TAXONOMY_DRIFT_PREFIX)})"
        if change.taxonomy_drift
        else ""
    )
    return (
        f"{prior}{prior_marker}{prior_qualifier} ({period}); "
        f"Δ {delta}{endpoint_markers}; {percent}{qualifier}",
        f"{change.kind.value} {absolute_trace}{percent_trace}{drift_note}{qualifier}",
    )


def _render_comparatives(
    comparatives: Sequence[ConceptComparative],
    facts: Sequence[RenderedFact],
    notes: _Footnotes,
    *,
    attempted: bool,
    places: int,
    predecessors: Mapping[FactRole, AdmittedFact],
) -> list[str]:
    """Render the section-3 table over every configured material concept; a role's QoQ prior in
    ``predecessors`` is that admitted fact, with its file and label."""
    if not comparatives:
        if attempted:
            return ["No prior-period comparator filings were available for this report."]
        return [
            "Prior-period comparatives were not attempted for this single-issuer pipeline path."
        ]
    labels = {fact.concept_qname: _ROLE_LABELS[fact.role] for fact in facts}
    admitted = {fact.concept_qname: fact.admitted for fact in facts}
    priors = {fact.concept_qname: predecessors.get(fact.role) for fact in facts}
    lines = [
        "| P&L line | Current | QoQ prior / change | YoY prior / change |",
        "| --- | ---: | --- | --- |",
    ]
    traces: list[str] = []
    for comparative in comparatives:
        label = _escape_markdown_cell(
            labels.get(comparative.concept_qname, f"`{comparative.concept_qname}`")
        )
        fact = admitted.get(comparative.concept_qname)
        current_markers = (
            notes.markers(comparative.current_sources)
            if fact is None
            else notes.marker(fact.provenance)
        )
        qualifier = _qualifier([fact])
        if comparative.current_value is None or comparative.unit is None:
            current = f"not available ({comparative.current_unavailable_reason})"
        else:
            current = (
                f"{_format_value(comparative.current_value, comparative.unit)}"
                f"{current_markers}{qualifier}"
            )
        qoq, prior = comparative.qoq, priors.get(comparative.concept_qname)
        if prior is not None and qoq.available:
            assert comparative.current_value is not None and comparative.unit is not None
            qoq = predecessor_change(qoq, comparative.current_value, prior, comparative.unit)
        qoq_cell, qoq_trace = _render_change(
            comparative,
            qoq,
            notes,
            places,
            current_markers,
            _qualifier([fact, prior]),
            _qualifier([prior]),
        )
        yoy_cell, yoy_trace = _render_change(
            comparative, comparative.yoy, notes, places, current_markers, qualifier
        )
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
    cutoff = (
        f"Configured historical cutoff (not enforced): **{update.knowledge_cutoff}**."
        if update.diagnostic_label
        else f"Information cutoff: **{update.knowledge_cutoff}**; anything later is out of scope."
    )
    lines.append(
        f"Event under review: {update.issuer_name} {update.issuer_quarter_label} consolidated "
        f"results (issuer results PDF and NSE Ind AS XBRL), period "
        f"{update.period_start} → {update.period_end}. {cutoff}"
    )
    if update.diagnostic_label:
        lines.extend(["", update.diagnostic_label])
        acquired = {
            (source.source_id, source.retrieved_at.isoformat())
            for fact in update.facts
            for source in fact.sources
        }
        acquired.update(
            (change.prior_source.source_id, change.prior_source.retrieved_at.isoformat())
            for item in update.comparatives
            for change in (item.qoq, item.yoy)
            if change.prior_source is not None
        )
        lines.extend(f"Acquired: {source} at {at}." for source, at in sorted(acquired))
    lines.append("")
    if update.source_cutoff is not None and update.derivation_cutoff is not None:
        lines.append(
            f"Source cutoff: **{update.source_cutoff.isoformat()}**; derivation cutoff (run "
            f"completion): **{update.derivation_cutoff.isoformat()}**."
        )
        lines.append("")
    if update.retrospective:
        lines.append(RETROSPECTIVE_LABEL)
        lines.append("")

    lines.append("## 2. facts")
    lines.append("")
    lines.append("| P&L line | Value | XBRL concept | Reconciliation | Source |")
    lines.append("| --- | ---: | --- | --- | --- |")
    for role in REQUIRED_ROLES:
        fact = by_role[role]
        value = _format_value(fact.value, fact.unit)
        admitted = fact.admitted
        markers = (
            notes.markers(fact.sources)
            if admitted is None
            else f"{notes.marker(admitted.provenance)}{_qualifier([admitted])}"
        )
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
            places=update.percent_places,
            predecessors=update.predecessors,
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
    if update.ledger is not None:
        for entry in update.ledger.entries:
            unit = entry.unit if entry.unit == "%" else f" {entry.unit}"
            cc = " constant currency" if entry.constant_currency else ""
            markers = f"{notes.marker(entry.first.source)}{notes.marker(entry.latest.source)}"
            bounds = _format_bounds(entry.lower_bound, entry.upper_bound)
            line = (
                f"- {entry.metric} **{bounds}{unit}{cc}** "
                f"for {entry.horizon} — {entry.status.value} [FORECAST]{markers} — first quoted "
                f'{entry.first.issuer_quarter}: "{entry.first.quote}"'
            )
            if entry.status in (LedgerStatus.REAFFIRMED, LedgerStatus.MODIFIED):
                line += f'; restated {entry.latest.issuer_quarter}: "{entry.latest.quote}"'
            elif entry.status is LedgerStatus.CARRIED:
                line += f"; not restated in {update.ledger.updated_quarter}"
            if entry.status is LedgerStatus.MODIFIED and entry.history:
                previous = entry.history[-1]
                line += f" (was {_format_bounds(previous.lower_bound, previous.upper_bound)})"
            lines.append(line)
        lines.append("")
    elif update.guidance:
        lines.append(
            "Management commitments to track (each quote-anchored in the held transcript):"
        )
        lines.append("")
        for claim in update.guidance:
            cc = " constant currency" if claim.constant_currency else ""
            marker = notes.marker(claim.source)
            unit = claim.unit if claim.unit == "%" else f" {claim.unit}"
            lines.append(
                f"- {claim.metric_label} **{_format_bounds(claim.lower_bound, claim.upper_bound)}"
                f"{unit}{cc}** for {claim.horizon} "
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
            qualifier = _qualifier([by_role[role].admitted for role in calc.operands])
            lines.append(
                f"- **{calc.label}** = {calc.result}{qualifier}. [computed — trace: {calc.trace}]"
            )
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
