"""Lossless mapping of the retained Apar sources onto ledger versions (ledger spec §1 Import;
plan D6, D7).

An earnings update's sections are its Markdown split at ``## `` lines. Each line that shows a
value is rebuilt from the JSON twin in the generator's line shape, with every value slot an
explicit ``{{c:<claim key>|<style>}}`` placeholder. The mapping is lossless or it raises
:class:`LosslessError`: the twin round-trips through the generator's typed model (no field the
model does not hold), the generator renders the twin to the Markdown bytes (every literal byte
comes from the twin), each rebuilt line renders to its bytes, and every twin value with no line
of its own (guidance, ledger anchors and history) is a verified alias of a claim. Every source
file is a blob of the hash-pinned retrieval manifest (its footnote shows the SHA-256 prefix).
Only :data:`UNMAPPED_FIELDS` map to nothing. Q0's YAML-only content follows its Markdown as
sections, its falsifier thresholds as self-cited ``POLICY`` claims. A source that does not parse
fails its version like any other loss.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import LEGACY_CONCEPTS
from fundamentals.contracts.canonical import Basis, ValueKind
from fundamentals.contracts.comparative import (
    TAXONOMY_DRIFT_PREFIX,
    ComparativeChange,
    ComparatorKind,
)
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    GuidanceContract,
    NumericClaim,
    ReportSection,
    Rounding,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.ledger.claim_check import CRORE, PER_SHARE, PERCENT, UNITS, quote_qualifiers
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
from fundamentals.output.management_ledger import (
    LedgerAnchor,
    LedgerEntry,
    LedgerRevision,
    LedgerStatus,
    ManagementLedger,
)

PREAMBLE = "preamble"
# An earnings update's own source files; its other import source is the management ledger.
UPDATE_FILES = ("earnings-update.md", "earnings-update.json")
HEADING = "## "
# The approved exception to "every twin field maps" (D3 phase review, finding 6): bookkeeping
# with no slot, alias or literal, kept byte-for-byte in the stored import source and never read.
# A report's ``retrieved_at`` is never an acquisition or first-seen time (D8: the manifest's is).
UNMAPPED_FIELDS = ("*.retrieved_at", "ledger.version", "comparatives_attempted")
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
ABS, PCT = "abs", "pct"
Q0 = "Q0"
# The generator's facts label (now, then) when the retained updates were rendered.
LABEL_THEN = (_ROLE_LABELS[FactRole.PROFIT_BEFORE_TAX], "Profit before tax")
_ORDINAL = re.compile(r"^\d+\.\s*")
_NON_WORD = re.compile(r"\W+")


class LosslessError(ValueError):
    """A source does not map losslessly; that version's import fails."""


class MappedVersion(BaseModel):
    """One version's content as mapped from its sources, before citations are looked up.

    ``bound`` is each quote claim's guidance contract from the management ledger, a source
    apart from the twin the claim maps from; ``ledger`` the twin's entries, the snapshot later
    quarters' history revisions are checked against.
    """

    model_config = ConfigDict(frozen=True)

    sections: tuple[ReportSection, ...]
    claims: tuple[NumericClaim, ...]
    cutoff: date
    qa_records: tuple[tuple[str, dict[str, int | str]], ...] = ()
    bound: tuple[tuple[str, GuidanceContract], ...] = ()
    ledger: tuple[LedgerEntry, ...] = ()


def map_earnings_update(
    md: bytes,
    twin: bytes,
    ledger: bytes,
    *,
    period: str,
    entity_id: int,
    mapped_quarters: Mapping[str, MappedVersion],
    retained: frozenset[str],
) -> MappedVersion:
    """Map one earnings update; ``ledger`` is the management ledger, ``mapped_quarters`` the
    earlier quarters' versions, whose claims the ledger anchors and history must alias, and
    ``retained`` the blob SHA-256s of the retrieval manifest."""
    with _parsing(period):
        text, raw = md.decode(), json.loads(twin)
        update = EarningsUpdate.model_validate(raw)
        managed = ManagementLedger.model_validate_json(ledger)
        results = [Decimal(calculation.result) for calculation in update.calculations]
        start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
        cutoff = date.fromisoformat(update.knowledge_cutoff)
    _require(json.loads(update.model_dump_json(exclude_unset=True)) == raw, period, "twin field")
    _require({s["file_sha256"] for s in _sources(raw)} <= retained, period, "source file")
    generated = render_earnings_update(update).replace(*LABEL_THEN)
    _require(generated == text, period, "the twin does not render to the Markdown")
    book = update.ledger
    _require(book is not None and book.updated_quarter == period, period, "ledger quarter")
    assert book is not None
    _require(book.symbol == update.nse_symbol, period, "ledger symbol")
    claims: dict[str, NumericClaim] = {}
    lines: list[str] = []
    notes = _Footnotes()
    facts = {fact.role: fact for fact in update.facts}
    labels = {role: _ROLE_LABELS[role].replace(*LABEL_THEN) for role in facts}
    for role in REQUIRED_ROLES:
        fact = facts[role]
        name = f"fact.{role.value}"
        _require(fact.unit in TABLE_STYLE, period, f"{name} unit")
        key = measurement_key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit, entity_id, start, end)
        claims[name] = _valued(name, "facts", fact.value, fact.unit, key, fact.sources[0])
        lines.append(
            f"| {labels[role]} | {_slot(name, TABLE_STYLE[fact.unit])} | `{fact.concept_qname}` "
            f"| {fact.reconciliation_status} | {notes.markers(fact.sources)} |\n"
        )
    traces: list[str] = []
    by_concept = {fact.concept_qname: fact for fact in update.facts}
    for comparative in update.comparatives:
        fact = by_concept[comparative.concept_qname]
        aliased = (comparative.current_value, comparative.unit)
        _require(aliased == (fact.value, fact.unit), period, "comparative alias")
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
    for number, (calculation, result) in enumerate(
        zip(update.calculations, results, strict=True), start=1
    ):
        name = f"calc.{number}"
        unit = next((u for s, u in CALC_UNITS.items() if calculation.label.endswith(s)), None)
        _require(unit is not None, period, f"{name} unit")
        assert unit is not None
        key = measurement_key(calculation.label, unit, entity_id, start, end)
        claims[name] = _valued(name, "calculations", result, unit, key)
        lines.append(
            f"- **{calculation.label}** = {_slot(name, '')}. "
            f"[computed — trace: {calculation.trace}]\n"
        )
    # Each entry's first and latest quote is its quarter's claim's citation. Each history
    # revision (the twin's; the management ledger's of this quarter) aliases its quarter's claim
    # with equal bounds and contract. A twin revision of this quarter records the entry carried
    # as it stands; of an earlier quarter, a snapshot an earlier mapped ledger held (never this
    # quarter's). The management ledger is the snapshot of its own quarter.
    known = {q: {c.claim_key: c for c in m.claims} for q, m in mapped_quarters.items()}
    known[period] = claims
    books = {q: m.ledger for q, m in mapped_quarters.items()}
    for entry in book.entries:
        for anchor in (entry.first, entry.latest):
            claim = _held(known, anchor.issuer_quarter, entry)
            cited = None if claim is None else claim.citation
            quoted = (anchor.source.file_sha256, _anchor(anchor), anchor.quote)
            held = cited is not None and (cited.source_sha256, cited.anchor, cited.quote) == quoted
            _require(held, period, f"{anchor.issuer_quarter} quote of {entry.claim_key}")
    held = managed.updated_quarter != period or managed.entries == book.entries
    _require(held, period, "management ledger is not this quarter's ledger")
    own = [(e, r) for e in book.entries for r in e.history]
    once = {(e.claim_key, r.issuer_quarter) for e, r in own}
    _require(len(once) == len(own), period, "a history records a quarter twice")
    revisions = own + [
        (e, r) for e in managed.entries for r in e.history if r.issuer_quarter == period
    ]
    for entry, revision in revisions:
        claim = _held(known, revision.issuer_quarter, entry)
        bounds = (revision.lower_bound, revision.upper_bound)
        held = claim is not None and (claim.lower_bound, claim.upper_bound) == bounds
        held = held and ((entry, revision) not in own or _snapshot(entry, revision, period, books))
        _require(held, period, f"{revision.issuer_quarter} revision of {entry.claim_key}")
    sections = _sections(_bind(text, lines, claims.values(), period))
    _require(narrative(sections, claims.values()) == md, period, "sections do not render")
    return MappedVersion(
        sections=tuple(sections),
        claims=tuple(claims.values()),
        cutoff=cutoff,
        qa_records=(
            ("cross_check", update.cross_check.model_dump()),
            ("cross_foot", update.cross_foot.model_dump()),
            ("sec_cross_check", {"note": update.sec_cross_check_note}),
        ),
        bound=tuple((k, c) for k, c in ledger_contracts(ledger).items() if k in claims),
        ledger=book.entries,
    )


def map_q0(md: bytes, twin: bytes, *, cutoff: date) -> MappedVersion:
    """Map the Q0 thesis: its Markdown sections, then one section per top-level YAML list in
    YAML order; every YAML scalar outside them is stated in the Markdown."""
    with _parsing(Q0):
        text, root = md.decode(), yaml.compose(twin.decode())
    _require(isinstance(root, yaml.MappingNode), Q0, "YAML root is not a mapping")
    tree = _lexemes(root)
    flat = " ".join(text.split())
    sections = _sections(text)
    claims: list[NumericClaim] = []
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
    return MappedVersion(sections=tuple(sections), claims=tuple(claims), cutoff=cutoff)


def _require(holds: bool, version: str, what: str) -> None:
    """Fail the version's import unless ``holds``."""
    if not holds:
        raise LosslessError(f"{version}: not lossless: {what}")


@contextmanager
def _parsing(version: str) -> Iterator[None]:
    """Fail the version's import when a source does not decode or parse."""
    try:
        yield
    except (ValueError, ArithmeticError, yaml.YAMLError) as failure:
        raise LosslessError(f"{version}: not lossless: does not parse: {failure}") from failure


def _sources(node: Any) -> Iterator[Mapping[str, Any]]:
    """Every provenance object (one with a ``file_sha256``) in a parsed twin."""
    if isinstance(node, dict):
        if "file_sha256" in node:
            yield node
        for value in node.values():
            yield from _sources(value)
    elif isinstance(node, list):
        for value in node:
            yield from _sources(value)


def _slot(claim_key: str, style: str) -> str:
    """A claim placeholder."""
    return f"{{{{c:{claim_key}|{style}}}}}"


def refs(keys: Sequence[str]) -> str:
    """The space-joined ``ref`` placeholders of ``keys``."""
    return " ".join(_slot(key, "ref") for key in keys)


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


def measurement_key(
    canonical_id: str, unit: str, entity_id: int, start: date, end: date
) -> MeasurementKey:
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


def change_key(key: MeasurementKey, kind: ComparatorKind, name: str) -> MeasurementKey:
    """A comparator change's computed key: the current key, ``<canonical_id>.<kind>.<name>``;
    the percent change is a dimensionless percentage."""
    percent = {"value_kind": ValueKind.PERCENTAGE, "currency": None} if name == PCT else {}
    canonical_id = f"{key.canonical_id}.{kind.value.lower()}.{name}"
    return key.model_copy(update={"canonical_id": canonical_id, **percent})


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
    key, unit, kind = current.measurement_key, current.unit, change.kind
    period = PeriodInterval.duration(change.period_start, change.period_end)
    return {
        f"{base}.prior": _valued(
            f"{base}.prior",
            "changes",
            prior,
            unit,
            key.model_copy(update={"period": period}),
            change.prior_source,
        ),
        f"{base}.abs": _valued(f"{base}.abs", "changes", delta, unit, change_key(key, kind, ABS)),
        f"{base}.pct": _valued(
            f"{base}.pct",
            "changes",
            percent,
            PERCENT,
            change_key(key, kind, PCT),
            precision=1,
            rounding=Rounding.ROUND_HALF_EVEN,
        ),
    }


def ledger_contracts(ledger: bytes) -> dict[str, GuidanceContract]:
    """Each management-ledger entry's guidance contract by its quote claim's key; a key whose
    entries disagree binds nothing (plan D4, M9)."""
    contracts: dict[str, set[GuidanceContract]] = {}
    for entry in ManagementLedger.model_validate_json(ledger).entries:
        contracts.setdefault(_ledger_key(entry), set()).add(_contract(entry))
    return {key: found.pop() for key, found in contracts.items() if len(found) == 1}


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


def _contract(guidance: LedgerEntry | NumericClaim) -> GuidanceContract:
    """A ledger entry's or quote claim's guidance contract."""
    return GuidanceContract.model_validate(guidance, from_attributes=True)


def _held(
    known: Mapping[str, Mapping[str, NumericClaim]], quarter: str, entry: LedgerEntry
) -> NumericClaim | None:
    """``quarter``'s claim under the entry's key, if it states the entry's guidance contract."""
    claim = known.get(quarter, {}).get(_ledger_key(entry))
    return claim if claim is not None and _contract(claim) == _contract(entry) else None


def _snapshot(
    entry: LedgerEntry,
    revision: LedgerRevision,
    version: str,
    books: Mapping[str, Iterable[LedgerEntry]],
) -> bool:
    """Whether the revision is a snapshot: of ``version``, the entry carried (its bounds are its
    claim's, checked by the caller); of an earlier quarter, an earlier ``books`` entry under its
    key with its bounds and status, in the revision's quarter or last quoted then."""
    if revision.issuer_quarter == version:
        return revision.status is entry.status is LedgerStatus.CARRIED
    snapshot = (entry.claim_key, revision.lower_bound, revision.upper_bound, revision.status)
    return any(
        revision.issuer_quarter in (quarter, held.latest.issuer_quarter)
        and (held.claim_key, held.lower_bound, held.upper_bound, held.status) == snapshot
        for quarter, entries in books.items()
        for held in entries
    )


def _anchor(quoted: LedgerAnchor) -> str:
    """A ledger quote's ``p<page>.b<block>.<span>`` anchor."""
    source = quoted.source
    return f"p{source.page}.b{source.block}.{source.span}"


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
            anchor=_anchor(latest),
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
