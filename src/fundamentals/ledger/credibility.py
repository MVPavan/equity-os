"""The ``management_credibility`` section: commitment episodes, revision events, outcomes (S2).

Each run rebuilds every episode and event from the previous-quarter head's sealed record lines and
this run's transcript: ``prepare`` checks the mapping before the first write, ``bind_credibility``
stores the actuals due and renders through ``build``. Verdicts come from code, never a model.
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
from fundamentals.contracts.comparison import SelectionSource
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import NumericClaim, Rounding, VersionDraft
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.provenance import Provenance
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.claim_check import CRORE, PERCENT
from fundamentals.ledger.display import EXACT_DIGITS, PLACEHOLDER
from fundamentals.ledger.falsifier_status import CREDIBILITY
from fundamentals.ledger.guidance_targets import (
    GUIDANCE_KEY,
    UNDATED,
    Reading,
    TargetEntry,
    Targets,
    derive_window,
    fiscal_span,
)
from fundamentals.ledger.import_mapping import QUOTE_STYLE, _slot, _valued, refs
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.ledger.run_traces import CHANGE_PCT, RunDraftError, _Binder, admitted_xbrl, cite
from fundamentals.output.earnings_update import EarningsUpdate

ACTUAL_KEY = "cred.{metric}.{scope}.{window}"
YTD = ".ytd"
EXACT_PLACES = 6
ACTUAL_WHOLE = "(all computed digits)"
ACTUAL_CUT = "(first six decimal places, cut and not rounded; more digits follow)"
REASON_DESCRIPTIVE = "the quote is read as descriptive, not a promise"
REASON_WRONG_WAY = "open bound in the wrong direction"
_WIDENED, _NARROWED = "range widened", "range narrowed"
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
    """A registered filed measure: ``numerator``'s growth against the same window a year earlier."""

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
    """A guidance claim, its live mapping entry (``None``: unmapped) and originating period."""

    claim: NumericClaim
    entry: TargetEntry | None
    stated: str = ""
    stated_end: date = date.min


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
    """A run's checked pool: its episodes, what corrections changed, the windows due, its blobs."""

    episodes: Mapping[str, list[Statement]]
    corrections: tuple[tuple[TargetEntry, TargetEntry], ...]
    retired: tuple[str, ...]
    dropped: Mapping[str, str]
    windows: Mapping[_Triple, WindowState]
    blobs: frozenset[str]
    month: int


class Built(_Frozen):
    """The section's episode claims and body, and the actuals it was built from."""

    claims: tuple[NumericClaim, ...]
    body: str
    actuals: tuple[NumericClaim, ...]
    exact: Mapping[str, Fraction]
    unavailable: Mapping[str, str]


def _bounds(claim: NumericClaim) -> tuple[Fraction, Fraction]:
    """A guidance claim's exact bounds."""
    assert claim.lower_bound is not None and claim.upper_bound is not None
    return Fraction(claim.lower_bound), Fraction(claim.upper_bound)


def _dated(entry: TargetEntry) -> bool:
    """Whether the entry promises one fiscal year."""
    return entry.reading is Reading.COMMITMENT and entry.window not in UNDATED


def _pair(claim: NumericClaim) -> tuple[str, str]:
    """A guidance claim's metric and scope."""
    return claim.metric or "", claim.scope or ""


def _basis(statement: Statement) -> tuple[object, ...]:
    """What two statements must share for a direction to mean anything."""
    fields = {"metric", "scope", "unit", "currency", "constant_currency"}
    entry = statement.entry
    return statement.claim.model_dump(include=fields), entry and entry.definition


def revision(before: Statement, after: Statement, better: Better | None) -> Event:
    """The event between two consecutive statements; direction names a number's move only."""
    if _basis(before) != _basis(after):
        return Event(kind=EventKind.REVISED, reason="basis changed")
    old, new = before.claim, after.claim
    (old_low, old_high), (new_low, new_high) = _bounds(old), _bounds(new)
    old_open, new_open = "plus" in old.qualifiers, "plus" in new.qualifiers
    opened = old_open or new_open
    if opened and better is Better.LOWER:
        return Event(kind=EventKind.UNRESOLVED, reason=REASON_WRONG_WAY)
    if opened and better is None and (old_low != old_high or new_low != new_high):
        return Event(kind=EventKind.UNRESOLVED, reason="direction not registered")
    was, now = (old_low, new_low) if opened else (old_low + old_high, new_low + new_high)
    if now != was:
        return Event(kind=EventKind.REVISED_UP if now > was else EventKind.REVISED_DOWN)
    if old_open != new_open:
        return Event(kind=EventKind.REVISED, reason=_WIDENED if new_open else _NARROWED)
    width, wider = old_high - old_low, new_high - new_low
    if opened or width == wider:
        return Event(kind=EventKind.REAFFIRMED)
    return Event(kind=EventKind.REVISED, reason=_WIDENED if wider > width else _NARROWED)


def compare(statement: Statement, exact: Fraction, better: Better) -> bool:
    """Whether ``exact``, rounded half-even once to the statement's precision, meets its bound."""
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
    claim, entry = statement.claim, statement.entry
    if entry is not None and entry.reading is Reading.DESCRIPTIVE:
        return Outcome.UNRESOLVED, REASON_DESCRIPTIVE
    if entry is None or window in UNDATED or actual is None:
        named = ["window not mapped"] if entry is None else []
        named += [UNDATED[window]] if window in UNDATED else []
        named += [] if actual else ["no filed measure"]
        return Outcome.UNRESOLVED, "; ".join(named)
    if actual.better is Better.LOWER and "plus" in claim.qualifiers:
        return Outcome.UNRESOLVED, REASON_WRONG_WAY
    differs = {
        "unit": claim.unit != actual.unit,
        "currency": claim.currency != actual.currency,
        "constant currency": bool(claim.constant_currency),
        "definition": entry.definition != actual.definition,
    }
    if named := [name for name, differing in differs.items() if differing]:
        return (
            Outcome.UNRESOLVED,
            f"promise basis differs from the filed measure: {', '.join(named)}",
        )
    if state is WindowState.NOT_STARTED:
        return Outcome.UNRESOLVED, "not due: target year not started"
    ended = state is WindowState.ENDED
    if not ended and not actual.interim:
        return Outcome.UNRESOLVED, "no interim rule"
    value = exact if ended else ytd
    if value is None:
        missing = "actual not yet filed" if ended else "year-to-date or comparator window not filed"
        return Outcome.UNRESOLVED, reason or missing
    met, short = (Outcome.ACHIEVED, Outcome.MISSED) if ended else (Outcome.ON_TRACK, Outcome.BEHIND)
    return (met if compare(statement, value, actual.better) else short), None


def _parsed(pattern: re.Pattern[str], line: str) -> re.Match[str]:
    """``line`` fully matched, or a refusal."""
    match = pattern.fullmatch(line)
    if match is None:
        raise RunDraftError(f"credibility record line does not parse: {line}")
    return match


def read_record(body: str | None, claims: Sequence[NumericClaim]) -> Record:
    """A version's record (``None``: a legacy head, empty); refuses any incomplete parse."""
    if body is None:
        return Record()
    lines = body.splitlines()
    if _RETIRED_HEADER not in lines:
        raise RunDraftError("credibility record has no retired block")
    split = lines.index(_RETIRED_HEADER)
    marks = ("- statement", "- retired")
    found = [_parsed(_RECORD_LINE, s) for s in lines[:split] if s.strip().startswith(marks)]
    held = [_parsed(_RETIRED_LINE, s) for s in lines[split + 1 :] if s and s != _NONE]
    keys = [[key for key, _ in PLACEHOLDER.findall(match["refs"])] for match in found]
    named = [key for group in keys for key in group]
    entries = [match["entry"] for match in (*found, *held) if match["entry"]]
    by_key = {c.claim_key: c for c in claims if c.claim_key.startswith("episode.")}
    if len(set(entries)) < len(entries) or sorted(named) != sorted(by_key):
        raise RunDraftError("credibility record repeats an entry, or does not name each claim once")
    statements = tuple(
        Recorded(
            claims=tuple(by_key[key] for key in group),
            stated=match["stated"],
            stated_end=date.fromisoformat(match["ended"]),
            entry_id=match["entry"],
            digest=match["digest"],
        )
        for match, group in zip(found, keys, strict=True)
    )
    return Record(statements=statements, retired={m["entry"]: m["digest"] for m in held})


def version_record(version: VersionDraft) -> Record:
    """A stored version's credibility record (empty for a legacy version)."""
    body = next((s.body for s in version.sections if s.section_key == CREDIBILITY), None)
    return read_record(body, version.claims)


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


def _sealed_month(held: Recorded) -> int:
    """The fiscal-year-end month a record line's quarter label and period end fix."""
    return (held.stated_end.month + (4 - int(held.stated[-1])) * 3 - 1) % 12 + 1


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
    """Join the pool to the mapping and check all of it, writing nothing."""
    for held in (*record.statements, *same_period.statements):
        if (sealed := _sealed_month(held)) != month:
            raise RunDraftError(
                f"credibility statement stated {held.stated}: sealed on a fiscal year ending in "
                f"month {sealed}, this run's {month}; a calendar change cannot carry promises"
            )
    end = date.fromisoformat(str(period_end))
    pool = {_triple(s.claims[0]): (s.claims[0], s.stated, s.stated_end) for s in record.statements}
    for claim in stated_claims:
        pool.setdefault(_triple(claim), (claim, period, end))
    read = same_period.pins | record.pins
    episodes: dict[str, list[Statement]] = {}
    windows: dict[_Triple, WindowState] = {}
    pins: dict[str, str] = {}
    for triple in sorted(pool, key=lambda held: (pool[held][2], held[0], held[2])):
        claim, stated, stated_end = pool[triple]
        entry = targets.live(*triple)
        if entry is not None:
            pins[entry.id] = entry.digest
            found = derive_window(entry.window_text, filed_at.get(triple[1]), stated_end, month)
            if entry.quote != claim.citation.quote or (
                entry.id not in read and found != entry.window
            ):
                raise RunDraftError(
                    f"guidance target {entry.id}: not its statement's quote, or window "
                    f"{entry.window} where its words give {found}"
                )
            if absent := [e.id for e in targets.chain(entry) if e.triple not in pool]:
                raise RunDraftError(f"guidance targets {', '.join(absent)}: no recorded statement")
            if _dated(entry):
                state = window_state(entry.window, end, month)
                if state is not WindowState.NOT_STARTED:
                    windows[(*_pair(claim), entry.window)] = state
        placed = Statement(claim=claim, entry=entry, stated=stated, stated_end=stated_end)
        episodes.setdefault(_episode(claim, entry, targets), []).append(placed)
    gone = {i: s for i in sorted(read) if (s := targets.successor(i))}
    pins |= {i: targets.entries[i].digest for i in gone}
    if lost := sorted(i for i, digest in read.items() if pins.get(i) != digest):
        raise RunDraftError(f"guidance targets {', '.join(lost)}: this build loses their pins")
    live = {
        i: new
        for i in gone
        if i not in record.retired and (new := targets.live(*targets.entries[i].triple))
    }
    dropped: dict[str, str] = {}
    for held in (*record.statements, *same_period.statements):
        name = _ROLE.sub("", held.claims[0].claim_key.removeprefix("episode."))
        if held.entry_id in live and name not in episodes:
            dropped.setdefault(name, live[held.entry_id].id)
    ready = Prepared(
        episodes=episodes,
        corrections=tuple((targets.entries[i], new) for i, new in live.items()),
        retired=tuple(
            f"- retired {i} sha256 {targets.entries[i].digest} successor {new.id}"
            for i, new in gone.items()
        ),
        dropped=dropped,
        windows=windows,
        blobs=frozenset(triple[1] for triple in pool) | actual_blobs,
        month=month,
    )
    # The mapping's rendered text faces the version's scan and the next run's parse only after
    # upstream writes, so both run here. Actuals add no mapping-controlled text.
    built = build(ready, actuals=(), exact={}, unavailable={})
    read_record(built.body, built.claims)
    if states := scan_section(built.body, resolves=lambda *_: True):
        raise RunDraftError(f"guidance mapping renders an invalid section: {', '.join(states)}")
    return ready


def build(
    prepared: Prepared,
    *,
    actuals: tuple[NumericClaim, ...],
    exact: Mapping[str, Fraction],
    unavailable: Mapping[str, str],
    registry: Mapping[tuple[str, str], Actual] = ACTUALS,
) -> Built:
    """The section's episode claims and body, every event and outcome computed here."""
    by_key = {claim.claim_key: claim for claim in actuals}
    claims: list[NumericClaim] = []
    lines: list[str] = []
    results: list[tuple[Outcome, str | None]] = []
    for name, held in prepared.episodes.items():
        metric, scope = _pair(held[0].claim)
        entry, measure = held[0].entry, registry.get((metric, scope))
        window = None if entry is None else entry.window
        state, key = None, ""
        if entry is not None and _dated(entry):
            state = prepared.windows.get((metric, scope, entry.window), WindowState.NOT_STARTED)
            key = ACTUAL_KEY.format(metric=metric, scope=scope, window=window)
        shown = key + YTD if state is WindowState.OPEN else key
        values = exact.get(key), exact.get(key + YTD), unavailable.get(shown)
        ends = held[:1] if len(held) == 1 else [held[0], held[-1]]
        judged = [assess(end, window, measure, state, *values) for end in ends]
        results += judged
        lines.append(_row(name, held, judged, by_key.get(shown), exact.get(shown)))
        copies = _copies(name, held)
        claims += [copy for group in copies for copy in group]
        described = entry is not None and entry.reading is Reading.DESCRIPTIVE
        first = Event(kind=EventKind.DESCRIBED if described else EventKind.OPENED)
        better = None if measure is None else measure.better
        events = [first, *(revision(a, b, better) for a, b in pairwise(held))]
        lines += map(_record_line, held, events, copies)
    for episode, successor in prepared.dropped.items():
        reason = f"mapping corrected: successor {successor}"
        results.append((Outcome.UNRESOLVED, reason))
        lines.append(f"- {COMPUTED} {episode}: {Outcome.UNRESOLVED.value} ({reason})")
    lines += [_correction(old, new) for old, new in prepared.corrections]
    paragraphs = [f"{COMPUTED} {NO_STATEMENT}"]
    if prepared.episodes:
        paragraphs = [f"{COMPUTED} {' '.join(DISCLOSURES)}", "\n".join(lines)]
        if all(outcome is Outcome.UNRESOLVED for outcome, _ in results):
            named = (part for _, reason in results if reason for part in reason.split("; "))
            paragraphs.append(f"{COMPUTED} {NO_OUTCOME.format('; '.join(dict.fromkeys(named)))}")
    paragraphs.append("\n".join((_RETIRED_HEADER, *(prepared.retired or [_NONE]))))
    body = f"## {CREDIBILITY}\n\n" + "".join(f"{paragraph}\n\n" for paragraph in paragraphs)
    return Built(
        claims=tuple(claims), body=body, actuals=actuals, exact=exact, unavailable=unavailable
    )


def _copies(name: str, held: Sequence[Statement]) -> list[tuple[NumericClaim, ...]]:
    """Each statement's claim copies: both endpoints of a lone statement, else its one role."""

    def copy(item: Statement, role: str) -> NumericClaim:
        update = {"claim_key": f"episode.{name}.{role}", "section_key": CREDIBILITY}
        return item.claim.model_copy(update=update)

    if len(held) == 1:
        return [(copy(held[0], "original"), copy(held[0], "latest"))]
    middle = [(copy(item, f"stated.{item.entry.id}"),) for item in held[1:-1] if item.entry]
    return [(copy(held[0], "original"),), *middle, (copy(held[-1], "latest"),)]


def _row(
    name: str,
    held: Sequence[Statement],
    judged: Sequence[tuple[Outcome, str | None]],
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
        text += (
            f"; {mark} actual {_slot(actual.claim_key, 'unit')} {phrase}, rounded to the "
            "guidance's stated precision; the verdict rounds the exact computed value once"
        )
        text += "; seasonality not adjusted; year-to-date assumed representative" if interim else ""
    verdicts = "; ".join(
        f"{role} {outcome.value}" + (f" ({reason})" if reason else "")
        for role, (outcome, reason) in zip(roles, judged, strict=True)
    )
    return f"{text}; {mark} {verdicts} {refs(keys)}"


def _record_line(item: Statement, event: Event, copies: tuple[NumericClaim, ...]) -> str:
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


def _spans(label: str, ended: bool, stop: date, month: int) -> tuple[_Span, _Span] | None:
    """The window and its comparator a year earlier; a leap day has no comparator."""
    start, end = fiscal_span(label, month)
    if ended:
        return (start, end), fiscal_span(f"FY{int(label[2:]) - 1:02d}", month)
    if (stop.month, stop.day) == (2, 29):
        return None
    return (start, stop), (start.replace(year=start.year - 1), stop.replace(year=stop.year - 1))


def _computed(
    binder: _Binder,
    sources: Sequence[tuple[Provenance, SelectionSource]],
    measure: Actual,
    name: str,
    scope: str,
    spans: tuple[_Span, _Span] | None,
    ended: bool,
) -> tuple[NumericClaim, Fraction] | str | None:
    """A window's stored trace and claim, the reason there is none, or ``None`` when an operand
    is not filed. The first of equal values across admitted captures is used."""
    if spans is None:
        return "a leap day has no comparator"
    update = {"basis": Basis(scope.upper()), "period": PeriodInterval.duration(*spans[0])}

    def filed(span: _Span) -> list[OperandValue]:
        key = binder.key(measure.numerator, CRORE)
        key = key.model_copy(update={**update, "period": PeriodInterval.duration(*span)})
        found = (binder.filed(source, key, how) for source, how in sources)
        return [held[1] for held in found if held is not None]

    now, then = filed(spans[0]), filed(spans[1])
    if len({held.value for held in now}) > 1 or len({held.value for held in then}) > 1:
        return "filed value differs across admitted captures"
    if not now or not then:
        return None
    assert then[0].interval is not None
    if then[0].interval.lower <= 0:
        return "comparator revenue not positive or its uncertainty reaches zero"
    output = binder.key(name, PERCENT).model_copy(update=update)
    kind = EpistemicClass.COMPUTED if ended else EpistemicClass.INFERRED
    result = binder.evaluate(name, CHANGE_PCT, output, (("current", now[0]), ("prior", then[0])))
    assert result.exact is not None
    claim = _valued(
        name,
        CREDIBILITY,
        truncate_value(result.exact, EXACT_PLACES),
        PERCENT,
        output,
        precision=EXACT_PLACES,
        rounding=Rounding.ROUND_HALF_EVEN,
    ).model_copy(update={"qualifiers": (EXACT_DIGITS,), "epistemic_class": kind})
    return cite(claim, calculation_trace_id=binder.store(name, result)), result.exact


def _carried(repo: EvidenceRepository, claim: NumericClaim) -> tuple[NumericClaim, Fraction]:
    """A prior version's actual with the exact value of its stored trace."""
    assert claim.citation.calculation_trace_id is not None
    (stored,) = repo.get_calculation_traces([claim.citation.calculation_trace_id])
    assert stored.trace.exact_value is not None
    return claim, stored.trace.exact_value


def bind_credibility(
    repo: EvidenceRepository,
    update: EarningsUpdate,
    prepared: Prepared,
    prior_actuals: Sequence[NumericClaim],
    *,
    entity_id: int,
    versions: ConfigVersions,
    registry: Mapping[tuple[str, str], Actual] = ACTUALS,
    declared: Sequence[str] = (),
) -> Built:
    """A stored or carried actual per registered window due, or a reason, and the built section.
    ``declared`` names the run's comparator XBRLs, admitted even if no comparison could use one."""
    start, stop = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    binder = _Binder(repo, entity_id, start, stop, versions)
    own, comparators = admitted_xbrl(update)
    used = (source.file_sha256 for source, _ in comparators.values())
    sources = [(own, SelectionSource.PACKAGE_AS_REPORTED)]
    sources += [
        (own.model_copy(update={"file_sha256": blob}), SelectionSource.HISTORICAL_PACKAGE)
        for blob in dict.fromkeys((*declared, *used))
    ]
    carried = {claim.claim_key: claim for claim in prior_actuals}
    actuals: tuple[NumericClaim, ...] = ()
    exact: dict[str, Fraction] = {}
    unavailable: dict[str, str] = {}
    for (metric, scope, label), state in prepared.windows.items():
        measure = registry.get((metric, scope))
        ended = state is WindowState.ENDED
        if measure is None or not (ended or measure.interim):
            continue
        key = ACTUAL_KEY.format(metric=metric, scope=scope, window=label)
        name = key if ended else key + YTD
        spans = _spans(label, ended, stop, prepared.month)
        found = (
            _carried(repo, carried[key])
            if ended and key in carried
            else _computed(binder, sources, measure, name, scope, spans, ended)
        )
        if isinstance(found, str):
            unavailable[name] = found
        elif found is not None:
            actuals += (found[0],)
            exact[name] = found[1]
    return build(prepared, actuals=actuals, exact=exact, unavailable=unavailable, registry=registry)
