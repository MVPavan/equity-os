"""The ``management_credibility`` section: commitment episodes, revision events, outcomes (S2).

Each run rebuilds every episode and event from the previous-quarter head's recorded statements and
this run's transcript. ``prepare`` (before the first write) joins them to the reviewed mapping file,
``bind_credibility`` stores the actuals due, ``build`` renders. One sealed record line per statement
is the only memory of its pin and period, so ``read_record`` parses completely or refuses. Verdicts
and events come from code and cited claims, never a model.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import StrEnum
from fractions import Fraction
from itertools import pairwise

from pydantic import BaseModel, ConfigDict

from fundamentals.canon.formula import OperandValue
from fundamentals.canon.interval import truncate_value
from fundamentals.contracts.canonical import Basis
from fundamentals.contracts.comparative import ComparatorKind
from fundamentals.contracts.comparison import SelectionSource
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import NumericClaim, Rounding
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.provenance import Provenance
from fundamentals.contracts.role import FactRole
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.claim_check import CRORE, PERCENT
from fundamentals.ledger.display import EXACT_DIGITS, PLACEHOLDER
from fundamentals.ledger.falsifier_status import CREDIBILITY
from fundamentals.ledger.guidance_targets import (
    GUIDANCE_KEY,
    WINDOW_AMBIGUOUS,
    WINDOW_MULTI_YEAR,
    Reading,
    TargetEntry,
    Targets,
    derive_window,
    fiscal_span,
)
from fundamentals.ledger.import_mapping import QUOTE_STYLE, _slot, _valued, refs
from fundamentals.ledger.run_traces import CHANGE_PCT, RunDraftError, _Binder, cite
from fundamentals.output.earnings_update import EarningsUpdate

ACTUAL_KEY = "cred.{metric}.{scope}.{window}"
YTD = ".ytd"
EXACT_PLACES = 6
ACTUAL_WHOLE = "(all computed digits)"
ACTUAL_CUT = "(first six decimal places, cut and not rounded; more digits follow)"
TOLERANCE = (
    "rounded to the guidance's stated precision; the verdict rounds the exact computed value once"
)
INTERIM_RULE_LABEL = "seasonality not adjusted; year-to-date assumed representative"
REASON_DESCRIPTIVE = "the quote is read as descriptive, not a promise"
REASON_WRONG_WAY = "open bound in the wrong direction"
REASON_NO_DIRECTION = "direction not registered"
REASON_BASIS = "basis changed"
REASON_UNMAPPED = "window not mapped"
REASON_NO_MEASURE = "no filed measure"
REASON_NOT_DUE = "not due: target year not started"
REASON_NOT_FILED = "actual not yet filed"
REASON_NO_INTERIM = "no interim rule"
REASON_NO_YTD = "year-to-date or comparator window not filed"
REASON_BASE = "comparator revenue not positive or its uncertainty reaches zero"
REASON_DIFFERS = "filed value differs across admitted captures"
REASON_LEAP = "a leap day has no comparator"
REASON_WINDOW = {
    WINDOW_MULTI_YEAR: "window not single-year",
    WINDOW_AMBIGUOUS: "window not established",
}
PLUS = "plus"
_NONE = "- none"
COMPUTED, OBSERVED, INFERRED = "{{e:computed}}", "{{e:observed}}", "{{e:inferred}}"
_RETIRED_HEADER = f"{COMPUTED} Retired entries:"
_RECORD_LINE = re.compile(
    r"  - statement \((?:(?P<entry>[A-Za-z0-9_-]+) sha256 (?P<digest>[0-9a-f]{64})|unmapped)\) "
    r"stated (?P<stated>FY\d{2}_Q[1-4]) ended (?P<ended>\d{4}-\d{2}-\d{2}): "
    r"[A-Z_]+(?: \([^()\d]+\))? (?P<refs>\{\{c:[^|}]+\|ref\}\}(?: \{\{c:[^|}]+\|ref\}\})?)"
)
_RETIRED_LINE = re.compile(
    r"- retired (?P<entry>[A-Za-z0-9_-]+) sha256 (?P<digest>[0-9a-f]{64}) successor [A-Za-z0-9_-]+"
)
_ROLE = re.compile(r"\.(?:original|latest|stated\.[A-Za-z0-9_-]+)$")
DISCLOSURES = (
    "This section records stated guidance and code-computed comparisons. No overall credibility "
    "judgment, trend or thesis consequence is computed or drafted.",
    "Only quotes the run's extraction rules captured are tracked, and each rule keeps its first "
    "match, so this is not an inventory of management's commitments. Promises before this report "
    "chain's first period are absent. Whether a captured quote is a commitment is a reviewed "
    "reading of its context; a quote read as descriptive is kept as evidence and is never scored "
    "or compared as a promise.",
    "Each quote's reading, window, definition and restatement link come from a reviewed mapping "
    "file written after these calls were published, not from the filing. The record lines under "
    "each row name its entries and digests.",
    "Scope is the extracted guidance contract's field. Extraction labels every quote consolidated, "
    "so a metric naming a segment is identified by that name.",
    "Events compare a point, a range's midpoint, or a binding bound when one statement is "
    'open-ended. A qualifier such as "about" is ignored. Up and down state a number\'s move, not '
    "whether it is good or bad.",
    'An outcome needs a registered filed measure. "No filed measure" means this pipeline computes '
    "no comparable actual, not that the company files none.",
    "A quote with no single-year window cannot be scored achieved or missed, so its row stays "
    "unresolved.",
)
NO_OUTCOME = "No row in this version reaches an achieved, missed or interim outcome. Reasons: {}."
NO_STATEMENT = (
    "No guidance quote has been extracted in this report chain, so no commitment is tracked."
)
_Triple = tuple[str, str, str]
_Span = tuple[date, date]
_BASIS = {"metric", "scope", "unit", "currency", "constant_currency"}


class _Frozen(BaseModel):
    """An immutable value of this module."""

    model_config = ConfigDict(frozen=True)


class EventKind(StrEnum):
    """How a statement moved against the one before it in its episode."""

    OPENED = "OPENED"
    REVISED_UP = "REVISED_UP"
    REVISED_DOWN = "REVISED_DOWN"
    REVISED = "REVISED"
    REAFFIRMED = "REAFFIRMED"
    UNRESOLVED = "UNRESOLVED"
    DESCRIBED = "DESCRIBED"


class Outcome(StrEnum):
    """One endpoint's verdict."""

    ACHIEVED = "ACHIEVED"
    MISSED = "MISSED"
    ON_TRACK = "ON_TRACK"
    BEHIND = "BEHIND"
    UNRESOLVED = "UNRESOLVED"


class Better(StrEnum):
    """Which way a metric improves."""

    HIGHER = "HIGHER"
    LOWER = "LOWER"


class WindowState(StrEnum):
    """Where a run's period end falls against a target fiscal year."""

    NOT_STARTED = "NOT_STARTED"
    OPEN = "OPEN"
    ENDED = "ENDED"


class Event(_Frozen):
    """A revision event and why it has no direction, if so."""

    kind: EventKind
    reason: str | None = None


class Actual(_Frozen):
    """A registered filed measure: growth of ``numerator`` against the same window a year earlier
    and its basis; ``interim`` says the year-to-date rule applies."""

    numerator: str
    better: Better
    unit: str
    currency: str | None
    definition: str
    interim: bool


ACTUALS: dict[tuple[str, str], Actual] = {
    ("revenue_growth", "consolidated"): Actual(
        numerator="revenue_from_operations",
        better=Better.HIGHER,
        unit=PERCENT,
        currency=None,
        definition="revenue_growth",
        interim=True,
    )
}


class Statement(_Frozen):
    """A guidance claim and its live mapping entry (``None``: unmapped)."""

    claim: NumericClaim
    entry: TargetEntry | None


class Placed(Statement):
    """A statement in its episode, with its originating period."""

    episode: str
    stated: str
    stated_end: date


class Recorded(_Frozen):
    """One sealed record line: the claims it references, its period and pin."""

    claims: tuple[NumericClaim, ...]
    stated: str
    stated_end: date
    entry_id: str | None
    digest: str | None


class Record(_Frozen):
    """A version's sealed credibility record."""

    statements: tuple[Recorded, ...] = ()
    retired: Mapping[str, str] = {}

    @property
    def pins(self) -> dict[str, str]:
        """Every entry this version pinned, retired ones included."""
        held = {s.entry_id: s.digest for s in self.statements if s.entry_id and s.digest}
        return held | dict(self.retired)


class Prepared(_Frozen):
    """Everything a mapping or pool can fail, already checked: the statements in order, each
    correction since the previous quarter (old, live), the retired block (id to digest and
    successor), each episode a correction dropped (to the successor's id), the windows due and
    every blob the section rests on."""

    statements: tuple[Placed, ...]
    corrections: tuple[tuple[TargetEntry, TargetEntry], ...]
    retired: Mapping[str, tuple[str, str]]
    dropped: Mapping[str, str]
    windows: Mapping[_Triple, WindowState]
    blobs: frozenset[str]
    period_end: date
    month: int


class Built(_Frozen):
    """The section's episode claims and body."""

    claims: tuple[NumericClaim, ...]
    body: str


class CredibilityInputs(_Frozen):
    """What the draft's section is written from."""

    prepared: Prepared
    actuals: tuple[NumericClaim, ...]
    exact: Mapping[str, Fraction]
    unavailable: Mapping[str, str]


def _bounds(claim: NumericClaim) -> tuple[Fraction, Fraction]:
    """A guidance claim's exact bounds."""
    assert claim.lower_bound is not None and claim.upper_bound is not None
    return Fraction(claim.lower_bound), Fraction(claim.upper_bound)


def _is_open(claim: NumericClaim) -> bool:
    """Whether a statement is an open-ended ``plus`` promise."""
    return PLUS in claim.qualifiers


def _dated(entry: TargetEntry) -> bool:
    """Whether the entry promises one fiscal year."""
    return entry.reading is Reading.COMMITMENT and entry.window not in REASON_WINDOW


def _pair(claim: NumericClaim) -> tuple[str, str]:
    """A guidance claim's metric and scope."""
    return claim.metric or "", claim.scope or ""


def revision(before: Statement, after: Statement, better: Better | None) -> Event:
    """The event between two consecutive statements; direction names a number's move only."""
    old, new = before.claim, after.claim
    if _basis(before) != _basis(after):
        return Event(kind=EventKind.REVISED, reason=REASON_BASIS)
    (old_low, old_high), (new_low, new_high) = _bounds(old), _bounds(new)
    opened = _is_open(old) or _is_open(new)
    if opened and better is Better.LOWER:
        return Event(kind=EventKind.UNRESOLVED, reason=REASON_WRONG_WAY)
    if opened and better is None and (old_low != old_high or new_low != new_high):
        return Event(kind=EventKind.UNRESOLVED, reason=REASON_NO_DIRECTION)
    was, now = (old_low, new_low) if opened else (old_low + old_high, new_low + new_high)
    if now != was:
        return Event(kind=EventKind.REVISED_UP if now > was else EventKind.REVISED_DOWN)
    width, wider = old_high - old_low, new_high - new_low
    if opened or width == wider:
        return Event(kind=EventKind.REAFFIRMED)
    reason = "range widened" if wider > width else "range narrowed"
    return Event(kind=EventKind.REVISED, reason=reason)


def _basis(statement: Statement) -> tuple[object, ...]:
    """What two statements must share for a direction to mean anything."""
    entry = statement.entry
    return statement.claim.model_dump(include=_BASIS), None if entry is None else entry.definition


def compare(statement: Statement, exact: Fraction, better: Better) -> bool:
    """Whether ``exact``, rounded half-even once to the statement's precision, meets its binding
    bound."""
    low, high = _bounds(statement.claim)
    scale = 10**statement.claim.precision
    shown = Fraction(round(exact * scale), scale)
    return shown >= low if better is Better.HIGHER else shown <= high


def window_state(label: str, period_end: date, month: int) -> WindowState:
    """Where ``period_end`` falls against target year ``label``."""
    start, end = fiscal_span(label, month)
    if period_end < start:
        return WindowState.NOT_STARTED
    return WindowState.ENDED if period_end >= end else WindowState.OPEN


def assess(
    statement: Statement,
    window: str | None,
    actual: Actual | None,
    state: WindowState | None,
    exact: Fraction | None,
    ytd: Fraction | None,
    reason: str | None,
) -> tuple[Outcome, str | None]:
    """One endpoint's outcome, first match wins; ``reason`` says why the binder holds no value."""
    entry = statement.entry
    if entry is not None and entry.reading is Reading.DESCRIPTIVE:
        return Outcome.UNRESOLVED, REASON_DESCRIPTIVE
    named = [REASON_UNMAPPED] if entry is None else []
    named += [REASON_WINDOW[window]] if window in REASON_WINDOW else []
    if actual is None or named:
        named += [] if actual else [REASON_NO_MEASURE]
        return Outcome.UNRESOLVED, "; ".join(named)
    if actual.better is Better.LOWER and _is_open(statement.claim):
        return Outcome.UNRESOLVED, REASON_WRONG_WAY
    if differs := _differing(statement, actual):
        return Outcome.UNRESOLVED, f"promise basis differs from the filed measure: {differs}"
    if state is WindowState.NOT_STARTED:
        return Outcome.UNRESOLVED, REASON_NOT_DUE
    if state is WindowState.ENDED:
        if exact is None:
            return Outcome.UNRESOLVED, reason or REASON_NOT_FILED
        return (
            Outcome.ACHIEVED if compare(statement, exact, actual.better) else Outcome.MISSED
        ), None
    if not actual.interim:
        return Outcome.UNRESOLVED, REASON_NO_INTERIM
    if ytd is None:
        return Outcome.UNRESOLVED, reason or REASON_NO_YTD
    return (Outcome.ON_TRACK if compare(statement, ytd, actual.better) else Outcome.BEHIND), None


def _differing(statement: Statement, actual: Actual) -> str:
    """The basis fields where a promise differs from the filed measure."""
    claim, entry = statement.claim, statement.entry
    fields = (
        ("unit", claim.unit != actual.unit),
        ("currency", claim.currency != actual.currency),
        ("constant currency", bool(claim.constant_currency)),
        ("definition", entry is not None and entry.definition != actual.definition),
    )
    return ", ".join(name for name, differs in fields if differs)


def read_record(body: str | None, claims: Sequence[NumericClaim]) -> Record:
    """A version's record from its section body (``None``: a legacy head, empty); refuses anything
    but a complete parse naming every ``episode.*`` claim exactly once."""
    if body is None:
        return Record()
    lines = body.splitlines()
    if _RETIRED_HEADER not in lines:
        raise RunDraftError("credibility record has no retired block")
    split = lines.index(_RETIRED_HEADER)
    by_key = {c.claim_key: c for c in claims if c.claim_key.startswith("episode.")}
    statements = []
    for line in lines[:split]:
        stripped = line.strip()
        if stripped.startswith("- statement"):
            statements.append(_recorded(line, by_key))
        elif stripped.startswith("- retired"):
            raise RunDraftError(f"credibility retired line outside its block: {line}")
    retired = {}
    entries = [s.entry_id for s in statements if s.entry_id]
    for line in lines[split + 1 :]:
        if line and line != _NONE:
            match = _RETIRED_LINE.fullmatch(line)
            if match is None:
                raise RunDraftError(f"credibility retired line does not parse: {line}")
            retired[match["entry"]] = match["digest"]
            entries.append(match["entry"])
    named = [claim.claim_key for held in statements for claim in held.claims]
    if (
        len(set(entries)) < len(entries)
        or len(set(named)) < len(named)
        or set(named) != set(by_key)
    ):
        raise RunDraftError("credibility record repeats an entry, or does not name each claim once")
    return Record(statements=tuple(statements), retired=retired)


def _recorded(line: str, by_key: Mapping[str, NumericClaim]) -> Recorded:
    """One record line, refused unless it matches the grammar and names this version's claims."""
    match = _RECORD_LINE.fullmatch(line)
    keys = [] if match is None else [key for key, _ in PLACEHOLDER.findall(match["refs"])]
    if match is None or not set(keys) <= set(by_key):
        raise RunDraftError(f"credibility record line does not parse: {line}")
    return Recorded(
        claims=tuple(by_key[key] for key in keys),
        stated=match["stated"],
        stated_end=date.fromisoformat(match["ended"]),
        entry_id=match["entry"],
        digest=match["digest"],
    )


def _triple(claim: NumericClaim) -> _Triple:
    """The statement's identity: its ledger key, blob and anchor (an episode copy has the same)."""
    key = GUIDANCE_KEY.format(metric=claim.metric, horizon=claim.horizon, scope=claim.scope)
    return key, claim.citation.source_sha256 or "", claim.citation.anchor or ""


def _episode(claim: NumericClaim, entry: TargetEntry | None, targets: Targets) -> str:
    """The statement's episode id."""
    head = ".".join(_pair(claim))
    if entry is None:
        _, blob, anchor = _triple(claim)
        return f"{head}.UNMAPPED.{blob[:12]}.{anchor}"
    if entry.reading is Reading.DESCRIPTIVE:
        return f"{head}.{Reading.DESCRIPTIVE.value}.{entry.id}"
    if _dated(entry):
        return f"{head}.{entry.window}"
    return f"{head}.{entry.window}.{targets.root(entry).id}"


def prepare(
    stated_claims: Sequence[NumericClaim],
    record: Record,
    same_period: Record,
    targets: Targets,
    *,
    period: str,
    period_end: date | str,
    month: int,
    filed_at: Mapping[str, datetime],
    actual_blobs: frozenset[str],
) -> Prepared:
    """Join the pool to the mapping and check all of it, writing nothing. A statement keeps its
    recorded period; one new to the pool has this run's. A live entry not yet pinned is validated
    once, against its statement's own period; every entry on a statement's chain must name a pool
    statement; the pins carried must cover every pin read."""
    end = date.fromisoformat(str(period_end))
    pool = [(held.claims[0], held.stated, held.stated_end) for held in record.statements]
    known = {_triple(claim) for claim, _, _ in pool}
    pool += [(claim, period, end) for claim in stated_claims if _triple(claim) not in known]
    pool.sort(key=lambda item: (item[2], _triple(item[0])[0], _triple(item[0])[2]))
    triples = {_triple(claim) for claim, _, _ in pool}
    read = same_period.pins | record.pins
    placed = []
    for claim, stated, stated_end in pool:
        entry = targets.live(*_triple(claim))
        if entry is not None:
            filed = filed_at.get(_triple(claim)[1])
            found = derive_window(entry.window_text, filed, stated_end, month)
            if entry.quote != claim.citation.quote or (
                entry.id not in read and found != entry.window
            ):
                raise RunDraftError(
                    f"guidance target {entry.id}: not its statement's quote, or window "
                    f"{entry.window} where its words give {found}"
                )
            if absent := [e.id for e in targets.chain(entry) if e.triple not in triples]:
                raise RunDraftError(f"guidance targets {', '.join(absent)}: no recorded statement")
        episode = _episode(claim, entry, targets)
        placed.append(
            Placed(claim=claim, entry=entry, episode=episode, stated=stated, stated_end=stated_end)
        )
    gone = {i: s for i in sorted(read) if i in targets.entries and (s := targets.successor(i))}
    retired = {i: (targets.entries[i].digest, s.id) for i, s in gone.items()}
    pins = {p.entry.id: p.entry.digest for p in placed if p.entry} | {
        i: digest for i, (digest, _) in retired.items()
    }
    if lost := sorted(i for i, digest in read.items() if pins.get(i) != digest):
        raise RunDraftError(f"guidance targets {', '.join(lost)}: this build loses their pins")
    live = {
        i: new
        for i in gone
        if i not in record.retired and (new := targets.live(*targets.entries[i].triple))
    }
    built = {item.episode for item in placed}
    dropped: dict[str, str] = {}
    for held in (*record.statements, *same_period.statements):
        name = _ROLE.sub("", held.claims[0].claim_key.removeprefix("episode."))
        if held.entry_id in live and name not in built:
            dropped.setdefault(name, live[held.entry_id].id)
    windows = {}
    for item in placed:
        if item.entry is not None and _dated(item.entry):
            state = window_state(item.entry.window, end, month)
            if state is not WindowState.NOT_STARTED:
                windows[(*_pair(item.claim), item.entry.window)] = state
    return Prepared(
        statements=tuple(placed),
        corrections=tuple((targets.entries[i], new) for i, new in live.items()),
        retired=retired,
        dropped=dropped,
        windows=windows,
        blobs=frozenset(triple[1] for triple in triples) | actual_blobs,
        period_end=end,
        month=month,
    )


def build(
    prepared: Prepared,
    *,
    actuals: Sequence[NumericClaim],
    exact: Mapping[str, Fraction],
    unavailable: Mapping[str, str],
    registry: Mapping[tuple[str, str], Actual] = ACTUALS,
) -> Built:
    """The section's episode claims and body, every event and outcome computed here."""
    episodes: dict[str, list[Placed]] = {}
    for item in prepared.statements:
        episodes.setdefault(item.episode, []).append(item)
    by_key = {claim.claim_key: claim for claim in actuals}
    claims: list[NumericClaim] = []
    lines: list[str] = []
    results: list[tuple[Outcome, str | None]] = []
    for name, held in episodes.items():
        copies = _copies(name, held)
        claims += [copy for group in copies for copy in group]
        measure = registry.get(_pair(held[0].claim))
        judged, key = _judged(held, measure, prepared, exact, unavailable)
        results += judged
        lines.append(_row(name, held, judged, by_key.get(key), exact.get(key)))
        better = None if measure is None else measure.better
        lines += map(_record_line, held, _events(held, better), copies)
    for episode, successor in prepared.dropped.items():
        reason = f"mapping corrected: successor {successor}"
        results.append((Outcome.UNRESOLVED, reason))
        lines.append(f"- {COMPUTED} {episode}: {Outcome.UNRESOLVED.value} ({reason})")
    lines += [_correction(old, new) for old, new in prepared.corrections]
    paragraphs = [f"{COMPUTED} {NO_STATEMENT}"]
    if prepared.statements:
        paragraphs = [f"{COMPUTED} {' '.join(DISCLOSURES)}", "\n".join(lines)]
        if all(outcome is Outcome.UNRESOLVED for outcome, _ in results):
            named = (part for _, reason in results if reason for part in reason.split("; "))
            paragraphs.append(f"{COMPUTED} {NO_OUTCOME.format('; '.join(dict.fromkeys(named)))}")
    block = [
        f"- retired {id_} sha256 {digest} successor {successor}"
        for id_, (digest, successor) in prepared.retired.items()
    ]
    paragraphs.append("\n".join((_RETIRED_HEADER, *(block or [_NONE]))))
    body = f"## {CREDIBILITY}\n\n" + "".join(f"{paragraph}\n\n" for paragraph in paragraphs)
    return Built(claims=tuple(claims), body=body)


def built_from(inputs: CredibilityInputs) -> Built:
    """The section of a bound run."""
    return build(
        inputs.prepared, actuals=inputs.actuals, exact=inputs.exact, unavailable=inputs.unavailable
    )


def carried_actuals(claims: Sequence[NumericClaim]) -> tuple[NumericClaim, ...]:
    """A version's ended actuals, which a later run carries; a year-to-date value is recomputed."""
    prefix = ACTUAL_KEY.split("{", 1)[0]
    return tuple(c for c in claims if c.claim_key.startswith(prefix) and YTD not in c.claim_key)


def _copies(name: str, held: list[Placed]) -> list[tuple[NumericClaim, ...]]:
    """Each statement's claim copies: both endpoints of a lone statement, else its one role."""

    def copy(item: Placed, role: str) -> NumericClaim:
        update = {"claim_key": f"episode.{name}.{role}", "section_key": CREDIBILITY}
        return item.claim.model_copy(update=update)

    if len(held) == 1:
        return [(copy(held[0], "original"), copy(held[0], "latest"))]
    middle = [(copy(item, f"stated.{item.entry.id}"),) for item in held[1:-1] if item.entry]
    return [(copy(held[0], "original"),), *middle, (copy(held[-1], "latest"),)]


def _events(held: list[Placed], better: Better | None) -> list[Event]:
    """Each statement's event, recomputed on every build."""
    entry = held[0].entry
    descriptive = entry is not None and entry.reading is Reading.DESCRIPTIVE
    first = Event(kind=EventKind.DESCRIBED if descriptive else EventKind.OPENED)
    return [first, *(revision(a, b, better) for a, b in pairwise(held))]


def _judged(
    held: list[Placed],
    measure: Actual | None,
    prepared: Prepared,
    exact: Mapping[str, Fraction],
    unavailable: Mapping[str, str],
) -> tuple[list[tuple[Outcome, str | None]], str]:
    """Each endpoint's outcome, and the key of the actual the episode shows."""
    entry = held[0].entry
    window = None if entry is None else entry.window
    state, key = None, ""
    if entry is not None and _dated(entry):
        state = window_state(entry.window, prepared.period_end, prepared.month)
        metric, scope = _pair(held[0].claim)
        key = ACTUAL_KEY.format(metric=metric, scope=scope, window=window)
    shown = key + YTD if state is WindowState.OPEN else key
    values = exact.get(key), exact.get(key + YTD), unavailable.get(shown)
    ends = held[:1] if len(held) == 1 else [held[0], held[-1]]
    return [assess(end, window, measure, state, *values) for end in ends], shown


def _row(
    name: str,
    held: list[Placed],
    judged: list[tuple[Outcome, str | None]],
    actual: NumericClaim | None,
    value: Fraction | None,
) -> str:
    """An episode's one line: its quotes, the actual if any, then one outcome per endpoint."""
    roles = ["original"] if len(held) == 1 else ["original", "latest"]
    keys = [f"episode.{name}.{role}" for role in roles]
    quotes = "; ".join(
        f'{role} "{_slot(key, QUOTE_STYLE)}"' for role, key in zip(roles, keys, strict=True)
    )
    text = f"- {OBSERVED} {' '.join(_pair(held[0].claim))}: {quotes}"
    mark = COMPUTED
    if actual is not None and actual.value is not None and value is not None:
        interim = actual.claim_key.endswith(YTD)
        mark = INFERRED if interim else COMPUTED
        keys.append(actual.claim_key)
        phrase = ACTUAL_WHOLE if value == Fraction(actual.value) else ACTUAL_CUT
        text += f"; {mark} actual {_slot(actual.claim_key, 'unit')} {phrase}, {TOLERANCE}"
        text += f"; {INTERIM_RULE_LABEL}" if interim else ""
    verdicts = "; ".join(
        f"{role} {outcome.value}" + (f" ({reason})" if reason else "")
        for role, (outcome, reason) in zip(roles, judged, strict=True)
    )
    return f"{text}; {mark} {verdicts} {refs(keys)}"


def _record_line(item: Placed, event: Event, copies: tuple[NumericClaim, ...]) -> str:
    """The statement's sealed record line."""
    entry = item.entry
    pin = "unmapped" if entry is None else f"{entry.id} sha256 {entry.digest}"
    reason = f" ({event.reason})" if event.reason else ""
    return (
        f"  - statement ({pin}) stated {item.stated} ended {item.stated_end}: "
        f"{event.kind.value}{reason} {refs([copy.claim_key for copy in copies])}"
    )


def _correction(old: TargetEntry, new: TargetEntry) -> str:
    """A permanent line stating both interpretations of a corrected entry."""
    old_text, new_text = (
        f"{e.id} sha256 {e.digest} (window {e.window}, definition {e.definition}, "
        f"reading {e.reading.value})"
        for e in (old, new)
    )
    return f"- {COMPUTED} Mapping correction: {old_text} is replaced by {new_text}"


def _sources(update: EarningsUpdate) -> list[tuple[Provenance, SelectionSource]]:
    """Every admitted XBRL in the fixed order own, QoQ, YoY."""
    (own,) = (fact.sources[0] for fact in update.facts if fact.role is FactRole.PROFIT_BEFORE_TAX)
    comparators = {
        change.kind: change.prior_source
        for comparative in update.comparatives
        for change in (comparative.qoq, comparative.yoy)
        if change.prior_source is not None
    }
    historical = [
        (comparators[kind], SelectionSource.HISTORICAL_PACKAGE)
        for kind in (ComparatorKind.QOQ, ComparatorKind.YOY)
        if kind in comparators
    ]
    return [(own, SelectionSource.PACKAGE_AS_REPORTED), *historical]


def _spans(label: str, state: WindowState, prepared: Prepared) -> tuple[_Span, _Span] | None:
    """The window and its comparator a year earlier: a whole ended year, or the target year's
    start to the run's period end; a leap day has no comparator."""
    month, stop = prepared.month, prepared.period_end
    start, end = fiscal_span(label, month)
    if state is WindowState.ENDED:
        return (start, end), fiscal_span(f"FY{int(label[2:]) - 1:02d}", month)
    if (stop.month, stop.day) == (2, 29):
        return None
    return (start, stop), (start.replace(year=start.year - 1), stop.replace(year=stop.year - 1))


def _carried(repo: EvidenceRepository, claim: NumericClaim) -> tuple[NumericClaim, Fraction]:
    """A prior version's actual with the exact value of its stored trace."""
    assert claim.citation.calculation_trace_id is not None
    (stored,) = repo.get_calculation_traces([claim.citation.calculation_trace_id])
    assert stored.trace.exact_value is not None
    return claim, stored.trace.exact_value


def _computed(
    binder: _Binder,
    sources: list[tuple[Provenance, SelectionSource]],
    measure: Actual,
    name: str,
    scope: str,
    spans: tuple[_Span, _Span] | None,
    state: WindowState,
) -> tuple[NumericClaim, Fraction] | str | None:
    """A window's stored trace and claim, the reason there is none, or ``None`` when an operand
    is not filed. Each operand is sought in every admitted capture; the first of equal values is
    used, and values that differ, or an ineligible comparator, give a reason."""
    if spans is None:
        return REASON_LEAP
    update = {"basis": Basis(scope.upper()), "period": PeriodInterval.duration(*spans[0])}

    def filed(span: _Span) -> list[OperandValue]:
        key = binder.key(measure.numerator, CRORE)
        key = key.model_copy(update={**update, "period": PeriodInterval.duration(*span)})
        found = (binder.filed(source, key, how) for source, how in sources)
        return [held[1] for held in found if held is not None]

    now, then = filed(spans[0]), filed(spans[1])
    if len({held.value for held in now}) > 1 or len({held.value for held in then}) > 1:
        return REASON_DIFFERS
    if not now or not then:
        return None
    assert then[0].interval is not None
    if then[0].interval.lower <= 0:
        return REASON_BASE
    output = binder.key(name, PERCENT).model_copy(update=update)
    pair = ("current", now[0]), ("prior", then[0])
    result = binder.evaluate(name, CHANGE_PCT, output, pair)
    assert result.exact is not None
    claim = _valued(
        name,
        CREDIBILITY,
        truncate_value(result.exact, EXACT_PLACES),
        PERCENT,
        output,
        precision=EXACT_PLACES,
        rounding=Rounding.ROUND_HALF_EVEN,
    )
    kind = EpistemicClass.COMPUTED if state is WindowState.ENDED else EpistemicClass.INFERRED
    labelled = claim.model_copy(update={"qualifiers": (EXACT_DIGITS,), "epistemic_class": kind})
    return cite(labelled, calculation_trace_id=binder.store(name, result)), result.exact


def bind_credibility(
    repo: EvidenceRepository,
    update: EarningsUpdate,
    prepared: Prepared,
    prior_actuals: Sequence[NumericClaim],
    *,
    entity_id: int,
    versions: ConfigVersions,
    registry: Mapping[tuple[str, str], Actual] = ACTUALS,
) -> CredibilityInputs:
    """A stored trace and cited claim per registered window due, or a value carried with its
    citation and exact value, or a stated reason."""
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    binder = _Binder(repo, entity_id, start, end, versions)
    sources = _sources(update)
    carried = {claim.claim_key: claim for claim in prior_actuals}
    actuals: list[NumericClaim] = []
    exact: dict[str, Fraction] = {}
    unavailable: dict[str, str] = {}
    for (metric, scope, label), state in prepared.windows.items():
        measure = registry.get((metric, scope))
        ended = state is WindowState.ENDED
        if measure is None or not (ended or measure.interim):
            continue
        key = ACTUAL_KEY.format(metric=metric, scope=scope, window=label)
        name = key if ended else key + YTD
        spans = _spans(label, state, prepared)
        found = (
            _carried(repo, carried[key])
            if ended and key in carried
            else _computed(binder, sources, measure, name, scope, spans, state)
        )
        if isinstance(found, str):
            unavailable[name] = found
        elif found is not None:
            actuals.append(found[0])
            exact[name] = found[1]
    return CredibilityInputs(
        prepared=prepared, actuals=tuple(actuals), exact=exact, unavailable=unavailable
    )
