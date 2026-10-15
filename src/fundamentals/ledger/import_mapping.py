"""Lossless mapping of the retained Apar sources onto ledger versions (ledger spec §1 Import;
plan D6, D7).

An earnings update's sections are its Markdown split at ``## `` lines. Each line that shows a
value is rebuilt from the JSON twin in the generator's line shape, with every value slot an
explicit ``{{c:<claim key>|<style>}}`` placeholder. The mapping is lossless or it raises
:class:`LosslessError`: the twin round-trips through the generator's typed model (no field the
model does not hold), the generator renders the twin to the Markdown bytes (every literal byte
comes from the twin), each rebuilt line renders to its bytes, and every twin value with no line
of its own (guidance, ledger history) is a verified alias of a claim. Q0's YAML-only content
follows its Markdown as sections, its falsifier thresholds as self-cited ``POLICY`` claims.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import LEGACY_CONCEPTS
from fundamentals.contracts.canonical import Basis, ValueKind
from fundamentals.contracts.comparative import TAXONOMY_DRIFT_PREFIX, ComparativeChange
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    GuidanceContract,
    NumericClaim,
    ReportSection,
    ResolvedCitation,
    Rounding,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.ledger.claim_check import quote_qualifiers
from fundamentals.ledger.display import narrative, render_section
from fundamentals.output.earnings_update import (
    _ROLE_LABELS,
    REQUIRED_ROLES,
    EarningsUpdate,
    _comparator_period_label,
    _Footnotes,
    _format_bounds,
    render_earnings_update,
)
from fundamentals.output.management_ledger import LedgerEntry, LedgerStatus, ManagementLedger

PREAMBLE = "preamble"
HEADING = "## "
CRORE, PER_SHARE, PERCENT = "INR crore", "INR per share", "%"
CURRENCY = "INR"
# Value kind, currency and scale of each value unit (legacy facts carry the same).
UNITS: Mapping[str, tuple[ValueKind, str | None, int | None]] = {
    CRORE: (ValueKind.CURRENCY_AMOUNT, CURRENCY, 10_000_000),
    PER_SHARE: (ValueKind.PER_SHARE_AMOUNT, CURRENCY, 1),
    PERCENT: (ValueKind.PERCENTAGE, None, None),
}
TABLE_STYLE = {CRORE: "group-intl,trim", PER_SHARE: ""}
BOUNDS_STYLE = "range-dash,unit,trim"
PERCENT_STYLE = "plus,unit"
QUOTE_STYLE = "quote"
CONTRACT_FIELDS = {"metric", "scope", "horizon", "unit", "constant_currency"}
CONTRACT_FIELDS |= {"lower_bound", "upper_bound"}
CALC_UNITS = {"(₹ crore)": CRORE, "(%)": PERCENT}
FALSIFIERS = "falsifiers"
FALSIFIER_FIELDS = frozenset({"falsifier_id", "statement", "predicate"})
PREDICATE_FIELDS = frozenset({"metric_id", "op", "threshold"})
PERCENT_METRIC = "_pct"
Q0 = "Q0"
# The generator's facts label (now, then) when the retained updates were rendered.
LABEL_THEN = (_ROLE_LABELS[FactRole.PROFIT_BEFORE_TAX], "Profit before tax")
_ORDINAL = re.compile(r"^\d+\.\s*")
_NON_WORD = re.compile(r"\W+")


class LosslessError(ValueError):
    """A source does not map losslessly; that version's import fails."""


class MappedVersion(BaseModel):
    """One version's content as mapped from its sources, before citations are looked up.

    ``bound`` holds what the import's claim check compares against for claims that cite their
    own source: a quote's parsed guidance contract, a self-cited policy's parsed source field.
    """

    model_config = ConfigDict(frozen=True)

    sections: tuple[ReportSection, ...]
    claims: tuple[NumericClaim, ...]
    cutoff: date
    qa_records: tuple[tuple[str, dict[str, int | str]], ...] = ()
    bound: tuple[tuple[str, ResolvedCitation], ...] = ()


def map_earnings_update(
    md: bytes,
    twin: bytes,
    ledger: bytes,
    *,
    period: str,
    entity_id: int,
    mapped_quarters: Mapping[str, MappedVersion],
) -> MappedVersion:
    """Map one earnings update; ``ledger`` is the management ledger and ``mapped_quarters`` the
    earlier quarters' versions, whose claims the ledger history must alias."""
    text, raw = md.decode(), json.loads(twin)
    update = EarningsUpdate.model_validate(raw)
    _require(json.loads(update.model_dump_json(exclude_unset=True)) == raw, period, "twin field")
    generated = render_earnings_update(update).replace(*LABEL_THEN)
    _require(generated == text, period, "the twin does not render to the Markdown")
    book = update.ledger
    _require(book is not None and book.updated_quarter == period, period, "ledger quarter")
    assert book is not None
    _require(book.symbol == update.nse_symbol, period, "ledger symbol")
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    claims: dict[str, NumericClaim] = {}
    lines: list[str] = []
    notes = _Footnotes()
    facts = {fact.role: fact for fact in update.facts}
    labels = {role: _ROLE_LABELS[role].replace(*LABEL_THEN) for role in facts}
    for role in REQUIRED_ROLES:
        fact = facts[role]
        name = f"fact.{role.value}"
        key = _key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit, entity_id, start, end)
        claims[name] = _valued(name, "facts", fact.value, fact.unit, key, fact.sources[0])
        lines.append(
            f"| {labels[role]} | {_slot(name, TABLE_STYLE[fact.unit])} | `{fact.concept_qname}` "
            f"| {fact.reconciliation_status} | {notes.markers(fact.sources)} |\n"
        )
    traces: list[str] = []
    by_concept = {fact.concept_qname: fact for fact in update.facts}
    for comparative in update.comparatives:
        fact = by_concept[comparative.concept_qname]
        _require(comparative.current_value == fact.value, period, "comparative alias")
        current, style = f"fact.{fact.role.value}", TABLE_STYLE[fact.unit]
        current_marks = notes.markers(comparative.current_sources)
        cells = []
        for change in (comparative.qoq, comparative.yoy):
            base = f"cmp.{fact.role.value}.{change.kind.value.lower()}"
            claims.update(_change_claims(base, change, claims[current], period))
            prior = change.prior_value
            traced = (f"{fact.value} - {prior}", f"({fact.value} - {prior}) / {prior} * 100")
            _require((change.absolute_trace, change.percent_trace) == traced, period, base)
            assert change.prior_source is not None
            prior_marks = notes.marker(change.prior_source)
            marks = current_marks + prior_marks
            label = _comparator_period_label(change.period_start, change.period_end)
            cells.append(
                f"{_slot(base + '.prior', style)}{prior_marks} ({label}); "
                f"Δ {_slot(base + '.abs', ','.join(filter(None, ('plus', style))))}{marks}; "
                f"{_slot(base + '.pct', PERCENT_STYLE)}{marks}"
            )
            drift = (change.taxonomy_drift or "").removeprefix(TAXONOMY_DRIFT_PREFIX)
            note = f" (taxonomy drift accepted: {drift})" if drift else ""
            now, then = _slot(current, ""), _slot(base + ".prior", "")
            traces.append(
                f"- {labels[fact.role]} {change.kind.value} trace: {now}{current_marks} − "
                f"{then}{prior_marks}; % trace: ({now}{current_marks} − {then}{prior_marks}) / "
                f"{then}{prior_marks} × 100{note}\n"
            )
        lines.append(
            f"| {labels[fact.role]} | {_slot(current, style)}{current_marks} | {cells[0]} "
            f"| {cells[1]} |\n"
        )
    lines += traces
    metric_labels = _guidance_aliases(update, book.entries, period)
    for entry in book.entries:
        name = _ledger_key(entry)
        _require(
            entry.claim_key == "|".join((entry.metric, entry.horizon, entry.scope)), period, name
        )
        claims[name], line = _ledger_entry(entry, metric_labels.get(name), notes, period)
        lines.append(line)
    for number, calculation in enumerate(update.calculations, start=1):
        name = f"calc.{number}"
        unit = next((u for s, u in CALC_UNITS.items() if calculation.label.endswith(s)), None)
        _require(unit is not None, period, f"{name} unit")
        assert unit is not None
        key = _key(calculation.label, unit, entity_id, start, end)
        claims[name] = _valued(name, "calculations", Decimal(calculation.result), unit, key)
        lines.append(
            f"- **{calculation.label}** = {_slot(name, '')}. "
            f"[computed — trace: {calculation.trace}]\n"
        )
    # Each history revision (the twin's; the management ledger's of this quarter) aliases its
    # quarter's claim with equal bounds; its status is the ledger's, not that quarter's line.
    known = {q: {c.claim_key: c for c in m.claims} for q, m in mapped_quarters.items()}
    known[period] = claims
    revisions = [(e, r) for e in book.entries for r in e.history]
    revisions += [
        (e, r)
        for e in ManagementLedger.model_validate_json(ledger).entries
        for r in e.history
        if r.issuer_quarter == period
    ]
    for entry, revision in revisions:
        claim = known.get(revision.issuer_quarter, {}).get(_ledger_key(entry))
        bounds = None if claim is None else (claim.lower_bound, claim.upper_bound)
        held = bounds == (revision.lower_bound, revision.upper_bound)
        _require(held, period, f"{revision.issuer_quarter} revision of {entry.claim_key}")
    sections = _sections(_bind(text, lines, claims.values(), period))
    _require(narrative(sections, claims.values()) == md, period, "sections do not render")
    return MappedVersion(
        sections=tuple(sections),
        claims=tuple(claims.values()),
        cutoff=date.fromisoformat(update.knowledge_cutoff),
        qa_records=(
            ("cross_check", update.cross_check.model_dump()),
            ("cross_foot", update.cross_foot.model_dump()),
            ("sec_cross_check", {"note": update.sec_cross_check_note}),
        ),
        bound=tuple((_ledger_key(e), _contract(e)) for e in book.entries),
    )


def map_q0(md: bytes, twin: bytes, *, cutoff: date) -> MappedVersion:
    """Map the Q0 thesis: its Markdown sections, then one section per top-level YAML list in
    YAML order; every YAML scalar outside them is stated in the Markdown."""
    text = md.decode()
    flat = " ".join(text.split())
    sections = _sections(text)
    claims: list[NumericClaim] = []
    tree = _lexemes(yaml.compose(twin.decode()))
    for name, value in tree.items():
        if isinstance(value, str):
            _require(" ".join(value.split()) in flat, Q0, f"{name} is not in the Markdown")
            continue
        _require(isinstance(value, list), Q0, name)
        items = [_falsifier(item, text, claims) if name == FALSIFIERS else item for item in value]
        _require(all(isinstance(item, str) for item in items), Q0, name)
        body = f"{HEADING}{name}\n\n" + "".join(f"- {item}\n" for item in items)
        sections.append(ReportSection(ordinal=len(sections), section_key=name, body=body))
    _require(narrative(sections, claims).startswith(md), Q0, "sections do not render")
    return MappedVersion(
        sections=tuple(sections),
        claims=tuple(claims),
        cutoff=cutoff,
        bound=tuple((c.claim_key, ResolvedCitation(value=c.value)) for c in claims),
    )


def _require(holds: bool, version: str, what: str) -> None:
    """Fail the version's import unless ``holds``."""
    if not holds:
        raise LosslessError(f"{version}: not lossless: {what}")


def _slot(claim_key: str, style: str) -> str:
    """A claim placeholder."""
    return f"{{{{c:{claim_key}|{style}}}}}"


def _bind(text: str, lines: list[str], claims: Iterable[NumericClaim], version: str) -> str:
    """The Markdown with each rebuilt line in place of the bytes it renders to."""
    held = text.splitlines(keepends=True)
    stored = tuple(claims)
    for line in lines:
        rendered = render_section(line, stored)
        _require(rendered in held, version, f"line does not rebuild: {rendered!r}")
        held[held.index(rendered)] = line
    return "".join(held)


def _sections(text: str) -> list[ReportSection]:
    """The text split before each ``## `` line; the first section is the preamble."""
    keys, bodies = [PREAMBLE], [""]
    for line in text.splitlines(keepends=True):
        if line.startswith(HEADING):
            title = _ORDINAL.sub("", line.removeprefix(HEADING).strip())
            keys.append(_NON_WORD.sub("_", title).strip("_").lower())
            bodies.append("")
        bodies[-1] += line
    return [
        ReportSection(ordinal=ordinal, section_key=key, body=body)
        for ordinal, (key, body) in enumerate(zip(keys, bodies, strict=True))
    ]


def _places(value: Decimal) -> int:
    """Fractional digits of a lexeme, as its Decimal keeps them."""
    exponent = value.as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def _key(canonical_id: str, unit: str, entity_id: int, start: date, end: date) -> MeasurementKey:
    """A consolidated Ind AS key, as the legacy translation builds a reported value's; a
    computed value's ``canonical_id`` names what it computes."""
    value_kind, currency, _ = UNITS[unit]
    return MeasurementKey(
        entity_id=entity_id,
        canonical_id=canonical_id,
        period=PeriodInterval.duration(start, end),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency=currency,
        value_kind=value_kind,
        dimensions=DimensionSet(),
    )


def _valued(
    name: str,
    section: str,
    value: Decimal,
    unit: str,
    key: MeasurementKey,
    source: Provenance | None = None,
    *,
    precision: int | None = None,
    rounding: Rounding = Rounding.ROUND_HALF_UP,
) -> NumericClaim:
    """A reported value (``FIGURE`` on its source file's fact, looked up at import) or, with no
    source, a computed one (``CALCULATION`` with no stored trace: unresolved, plan D6)."""
    value_kind, currency, scale = UNITS[unit]
    return NumericClaim(
        claim_key=name,
        section_key=section,
        citation=Citation(
            kind=CitationKind.CALCULATION if source is None else CitationKind.FIGURE,
            source_sha256=None if source is None else source.file_sha256,
        ),
        measurement_key=key,
        value_kind=value_kind,
        unit=unit,
        currency=currency,
        scale=scale,
        value=value,
        precision=_places(value) if precision is None else precision,
        rounding=rounding,
        epistemic_class=EpistemicClass.COMPUTED if source is None else EpistemicClass.OBSERVED,
        unresolved=True,
    )


def _change_claims(
    base: str, change: ComparativeChange, current: NumericClaim, version: str
) -> dict[str, NumericClaim]:
    """A comparator's prior (``FIGURE``), absolute and percent change (``CALCULATION``, the
    percent at the generator's 0.1 under half-even); an unavailable one has no line shape."""
    prior, delta, percent = change.prior_value, change.absolute_change, change.percent_change
    _require(None not in (prior, delta, percent, change.prior_source), version, f"{base} prior")
    assert prior is not None and delta is not None and percent is not None
    assert current.measurement_key is not None and current.unit is not None
    key, unit, kind = current.measurement_key, current.unit, change.kind.value.lower()
    period = PeriodInterval.duration(change.period_start, change.period_end)

    def computed(name: str, **update: Any) -> MeasurementKey:
        return key.model_copy(
            update={"canonical_id": f"{key.canonical_id}.{kind}.{name}", **update}
        )

    percent_key = computed("pct", value_kind=ValueKind.PERCENTAGE, currency=None)
    return {
        f"{base}.prior": _valued(
            f"{base}.prior",
            "changes",
            prior,
            unit,
            key.model_copy(update={"period": period}),
            change.prior_source,
        ),
        f"{base}.abs": _valued(f"{base}.abs", "changes", delta, unit, computed("abs")),
        f"{base}.pct": _valued(
            f"{base}.pct",
            "changes",
            percent,
            PERCENT,
            percent_key,
            precision=1,
            rounding=Rounding.ROUND_HALF_EVEN,
        ),
    }


def _ledger_key(entry: LedgerEntry) -> str:
    """A ledger entry's claim key."""
    return f"ledger.{entry.metric}.{entry.horizon}.{entry.scope}"


def _guidance_aliases(
    update: EarningsUpdate, entries: Iterable[LedgerEntry], version: str
) -> dict[str, str]:
    """Each guidance item's metric label by the one ledger entry it restates this quarter."""
    labels: dict[str, str] = {}
    for item in update.guidance:
        hits = [
            entry
            for entry in entries
            if entry.latest.issuer_quarter == version
            and item.metric in (None, entry.metric)
            and (item.quote, item.source, item.lower_bound, item.upper_bound)
            == (entry.latest.quote, entry.latest.source, entry.lower_bound, entry.upper_bound)
            and (item.unit, item.constant_currency, item.horizon)
            == (entry.unit, entry.constant_currency, entry.horizon)
        ]
        _require(len(hits) == 1, version, f"guidance {item.metric_label!r} has no single entry")
        labels[_ledger_key(hits[0])] = item.metric_label
    return labels


def _contract(entry: LedgerEntry) -> ResolvedCitation:
    """The parsed entry's guidance contract, which the import's claim check compares."""
    return ResolvedCitation(guidance=GuidanceContract.model_validate(entry, from_attributes=True))


def _ledger_entry(
    entry: LedgerEntry, metric_label: str | None, notes: _Footnotes, version: str
) -> tuple[NumericClaim, str]:
    """A ledger entry as a ``SOURCE_QUOTE`` claim on its latest quote (capture looked up at
    import; bounds at their lexemes' precision) and the generator's line, the bold bounds and
    the latest quote as slots."""
    name, latest, first, status = _ledger_key(entry), entry.latest, entry.first, entry.status
    source = latest.source
    _require(source.anchor_type is SourceAnchorType.PDF_SPAN, version, f"{name} anchor")
    _require(status is not LedgerStatus.NEW or first == latest, version, f"{name} first quote")
    claim = NumericClaim(
        claim_key=name,
        section_key="management_ledger",
        citation=Citation(
            kind=CitationKind.SOURCE_QUOTE,
            source_sha256=source.file_sha256,
            anchor=f"p{source.page}.b{source.block}.{source.span}",
            quote=latest.quote,
        ),
        value_kind=UNITS.get(entry.unit, (ValueKind.CURRENCY_AMOUNT,))[0],
        qualifiers=tuple(sorted(quote_qualifiers(latest.quote))),
        precision=max(_places(entry.lower_bound), _places(entry.upper_bound)),
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.FORECAST,
        metric_label=metric_label,
        unresolved=True,
        **entry.model_dump(include=CONTRACT_FIELDS),
    )
    quote = _slot(name, QUOTE_STYLE)
    constant = " constant currency" if entry.constant_currency else ""
    marks = notes.marker(first.source) + notes.marker(latest.source)
    line = (
        f"- {entry.metric} **{_slot(name, BOUNDS_STYLE)}{constant}** for {entry.horizon} — "
        f"{status.value} [FORECAST]{marks} — first quoted {first.issuer_quarter}: "
        f'"{quote if status is LedgerStatus.NEW else first.quote}"'
    )
    if status in (LedgerStatus.REAFFIRMED, LedgerStatus.MODIFIED):
        line += f'; restated {latest.issuer_quarter}: "{quote}"'
    elif status is LedgerStatus.CARRIED:
        line += f"; not restated in {version}"
    if status is LedgerStatus.MODIFIED and entry.history:
        previous = entry.history[-1]
        line += f" (was {_format_bounds(previous.lower_bound, previous.upper_bound)})"
    return claim, line + "\n"


def _lexemes(node: yaml.Node) -> Any:
    """A YAML node as nested dicts and lists of scalar source lexemes (``14.90`` stays text)."""
    if isinstance(node, yaml.MappingNode):
        return {key.value: _lexemes(value) for key, value in node.value}
    if isinstance(node, yaml.SequenceNode):
        return [_lexemes(item) for item in node.value]
    return node.value


def _falsifier(item: Any, text: str, claims: list[NumericClaim]) -> str:
    """A falsifier's section line; its threshold becomes a self-cited ``POLICY`` claim and its
    predicate must be the one the Markdown states."""
    _require(isinstance(item, dict) and item.keys() == FALSIFIER_FIELDS, Q0, "falsifier")
    predicate = item["predicate"]
    _require(isinstance(predicate, dict) and predicate.keys() == PREDICATE_FIELDS, Q0, "predicate")
    metric, threshold = predicate["metric_id"], predicate["threshold"]
    _require(f"`{metric} {predicate['op']} {threshold}`" in text, Q0, f"{metric} predicate")
    _require(metric.endswith(PERCENT_METRIC), Q0, f"{metric} unit")
    name, value = f"falsifier.{item['falsifier_id']}", Decimal(threshold)
    claims.append(
        NumericClaim(
            claim_key=name,
            section_key=FALSIFIERS,
            citation=Citation(kind=CitationKind.POLICY),
            value=value,
            value_kind=ValueKind.PERCENTAGE,
            unit=PERCENT,
            precision=_places(value),
            rounding=Rounding.ROUND_HALF_UP,
            epistemic_class=EpistemicClass.OPINION,
        )
    )
    return f"{item['falsifier_id']}: {item['statement']} ({_slot(name, '')})"
