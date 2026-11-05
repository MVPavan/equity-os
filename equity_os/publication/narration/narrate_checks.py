"""What ``ledger narrate`` checks and builds with no database (RESEARCH-3 S3 P2-P4)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from equity_os.analysis.lenses.credibility.credibility import COMPUTED, Outcome
from equity_os.analysis.lenses.thesis_tests.falsifier_status import NARRATIVE, NARRATIVE_ORDER
from equity_os.publication.approval.lifecycle import DecisionRefusedError
from equity_os.publication.checking.numeral_scan import (
    CLASS_MARKER,
    LOCATION_MARKER,
    narrative_prose,
)
from equity_os.publication.drafting.display import PLACEHOLDER

D1 = (
    "The sections above are the approved deterministic version this draft succeeds, with every "
    "claim unchanged; only the sentences that describe these notes were updated. The notes below "
    "were drafted by a model from the evidence bundle alone, which holds this version's claims and "
    "the quotes they cite, not the whole transcript: a cause management gave outside those quotes "
    "is absent, and absence here does not show that no cause exists. The model computes nothing: "
    "every number in these notes is a placeholder filled from a checked claim."
)
D2 = (
    "No metric and scope has a comparable completed-window assessment, so this record cannot show "
    "delivery rising or falling. A revision event states that a stated figure moved; it is neither "
    "an achievement nor better credibility."
)
D3 = (
    "Causes: NOT_ASSESSED. The evidence holds no management explanation of causes, so this section "
    "states what the cited claims show moved, not why."
)
D4 = (
    "A delivery trend compares completed outcomes of consecutive fiscal years for a single metric "
    "and scope, on the original and the latest promise; it is not a judgment of management. STEADY "
    "means each compared endpoint held its level. DIVERGED means the promise moved and the "
    "endpoints disagree, so no direction is stated. Interim outcomes stay out of it."
)
R6_TREND = (
    "The R6 note must say the flag identifies increased borrowings relative to equity, separate a "
    "trend flag from a limit breach, and name the unresolved funding or repayment question."
)
R6_LIMIT = (
    "The R6 note must say the value breached the approved limit, that this does not establish that "
    "borrowings rose relative to equity, and name the question the breach leaves open."
)
R6_GUARD = (
    "The R6 note must say that with non-positive equity no ratio or trend exists, say what that "
    "leaves unanswered, and state no movement in leverage."
)
RISK_NOTES, CREDIBILITY_NOTES = "risk_notes", "credibility_notes"
VERDICT_WORDS = (
    "rising",
    *"improv* better stronger falling deteriorat* worse weaker credible reliable".split(),
    *"trustworth* achiev* deliver* beat* missed conservative aggressive".split(),
    "on track",
)
_VERDICT = re.compile(rf"\b(?:{'|'.join(VERDICT_WORDS).replace('*', r'\w*')})\b", re.IGNORECASE)
_ON_CREDIBILITY = re.compile(r"credib|management|guidance", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|\n")
_KEY_LINE = re.compile(r"^## (\S+)[ \t]*$", re.MULTILINE)
_EPISODE_ROW = re.compile(
    r"^- \{\{e:observed\}\} (?P<metric>.+?) (?P<scope>\S*): original "
    r'"\{\{c:episode\.(?P<name>[^|}]+)\.original\|quote\}\}".*; \{\{e:\w+\}\} '
    r"original (?P<original>[A-Z_]+)(?: \(.*?\))?(?:; latest (?P<latest>[A-Z_]+)(?: \(.*?\))?)?"
    r"(?: \{\{c:[^|}]+\|ref\}\})+$"
)
_EVENT = re.compile(r"^  - statement .* ended \d{4}-\d{2}-\d{2}: ([A-Z_]+)")
_WINDOW = re.compile(r"\.FY(\d{2})$")
_FLAG = re.compile(r"^- \{\{e:computed\}\} (R\d+)\b.*; FLAGGED(?: by ([SLT, ]+))?", re.MULTILINE)
_LEVEL = {Outcome.MISSED: 0, Outcome.ACHIEVED: 1}


class DeliveryTrend(StrEnum):
    """How delivery moved against the previous completed fiscal year, if that can be said."""

    RISING = "RISING"
    FALLING = "FALLING"
    STEADY = "STEADY"
    DIVERGED = "DIVERGED"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


_DIRECTION = {1: DeliveryTrend.RISING, -1: DeliveryTrend.FALLING, 0: DeliveryTrend.STEADY}


class TrendRow(BaseModel):
    """One episode's row; a lone statement's latest outcome is its original."""

    model_config = ConfigDict(frozen=True)

    episode: str
    metric: str
    scope: str
    events: tuple[str, ...]
    original: Outcome
    latest: Outcome
    trend: DeliveryTrend = DeliveryTrend.NOT_ASSESSABLE


def parse_draft(text: str) -> Mapping[str, str]:
    """The five bodies in plan order; any other shape, or a body with no content, refuses."""
    preamble, *parts = _KEY_LINE.split(text)
    keys, bodies = parts[::2], dict(zip(parts[::2], parts[1::2], strict=True))
    wrong = {key for key in keys if key not in NARRATIVE or keys.count(key) > 1}
    wrong |= NARRATIVE - set(keys)
    bare = {key: LOCATION_MARKER.sub("", CLASS_MARKER.sub("", b)) for key, b in bodies.items()}
    wrong |= {key for key, body in bare.items() if not body.strip()}
    if preamble.strip() or wrong:
        raise DecisionRefusedError(f"the draft is not the five keys with content: {sorted(wrong)}")
    return {key: bodies[key].strip() for key in NARRATIVE_ORDER}


def _trend(now: TrendRow, rows: Mapping[str, TrendRow]) -> DeliveryTrend:
    """Each endpoint scored in both consecutive windows, compared on its own."""
    window = _WINDOW.search(now.episode)
    before = window and rows.get(_WINDOW.sub(f".FY{int(window[1]) - 1:02d}", now.episode))
    if not before:
        return DeliveryTrend.NOT_ASSESSABLE
    pairs = ((now.original, before.original), (now.latest, before.latest))
    moves = {_LEVEL[a] - _LEVEL[b] for a, b in pairs if a in _LEVEL and b in _LEVEL}
    if len(moves) > 1:
        return DeliveryTrend.DIVERGED
    return _DIRECTION[moves.pop()] if moves else DeliveryTrend.NOT_ASSESSABLE


def trend_rows(credibility_body: str) -> tuple[TrendRow, ...]:
    """One row per episode of N's unrendered section, compared with the fiscal year before."""
    found: dict[str, tuple[re.Match[str], list[str]]] = {}
    events: list[str] = []
    for line in credibility_body.splitlines():
        if row := _EPISODE_ROW.match(line):
            events = []
            found[row["name"]] = (row, events)
        elif event := _EVENT.match(line):
            events.append(event[1])
    rows = {
        name: TrendRow(
            episode=name,
            metric=row["metric"],
            scope=row["scope"],
            events=tuple(held),
            original=Outcome(row["original"]),
            latest=Outcome(row["latest"] or row["original"]),
        )
        for name, (row, held) in found.items()
    }
    return tuple(r.model_copy(update={"trend": _trend(r, rows)}) for r in rows.values())


def trend_lines(rows: tuple[TrendRow, ...]) -> tuple[str, ...]:
    """Each row as digit-free text, naming its episode through a ``ref``."""

    def why(row: TrendRow) -> str:
        if row.trend is not DeliveryTrend.NOT_ASSESSABLE:
            return ""
        interim = {Outcome.ON_TRACK, Outcome.BEHIND} & {row.original, row.latest}
        note = "interim, not a completed window" if interim else "no comparable completed windows"
        return f" ({note})"

    return tuple(
        f"{r.metric} {r.scope}: last event {r.events[-1] if r.events else 'none'}; original "
        f"{r.original.value}; latest {r.latest.value}; delivery trend {r.trend.value}{why(r)} "
        f"{{{{c:episode.{r.episode}.original|ref}}}}"
        for r in rows
    )


def trend_block(rows: tuple[TrendRow, ...]) -> str:
    """D4 and the rows, plus D2 only when no row holds an assessment; D2 alone with no rows."""
    lines = "\n".join(f"- {COMPUTED} {line}" for line in trend_lines(rows))
    parts = [f"{COMPUTED} {D4}", lines] if rows else []
    if all(row.trend is DeliveryTrend.NOT_ASSESSABLE for row in rows):
        parts.append(f"{COMPUTED} {D2}")
    return "\n\n".join(parts)


def verdict_words(section: str, text: str) -> tuple[str, ...]:
    """The verdict words in model text; outside ``credibility_notes``, sentences on it only."""
    return tuple(
        found.group()
        for sentence in _SENTENCE_END.split(narrative_prose(text))
        if section == CREDIBILITY_NOTES or _ON_CREDIBILITY.search(sentence)
        for found in _VERDICT.finditer(sentence)
    )


def notes_due(probe_body: str, credibility_body: str) -> Mapping[str, tuple[str, ...]]:
    """Each section's required key prefixes: flagged probes; revised, missed or behind episodes."""
    episodes = (
        f"episode.{row.episode}"
        for row in trend_rows(credibility_body)
        if {Outcome.MISSED, Outcome.BEHIND} & {row.original, row.latest}
        or any(event.startswith("REVISED") for event in row.events)
    )
    probes = tuple(f"probe.{check}" for check, _ in _FLAG.findall(probe_body))
    return {RISK_NOTES: probes, CREDIBILITY_NOTES: tuple(episodes)}


def r6_instruction(probe_body: str) -> str | None:
    """The note R6's own fired rules call for, or ``None`` when R6 is not flagged."""
    rules = dict(_FLAG.findall(probe_body)).get("R6")
    if rules is None:
        return None
    return R6_TREND if "T" in rules else R6_LIMIT if rules else R6_GUARD


def missing_notes(due: Mapping[str, tuple[str, ...]], bodies: Mapping[str, str]) -> tuple[str, ...]:
    """The due prefixes no placeholder of the section's model text names, whatever its style."""

    def named(section: str, prefix: str) -> bool:
        keys = (found[1] for found in PLACEHOLDER.finditer(bodies.get(section, "")))
        return any(key == prefix or key.startswith(f"{prefix}.") for key in keys)

    return tuple(p for section, held in due.items() for p in held if not named(section, p))


def bad_locations(text: str, citable: frozenset[tuple[str, str]]) -> tuple[str, ...]:
    """The location markers in ``text`` that are not citable locations of the bundle."""
    marks = LOCATION_MARKER.findall(text)
    return tuple(
        f"{capture}|{anchor}" for capture, anchor in marks if (capture, anchor) not in citable
    )


def excluded_refs(text: str, excluded: frozenset[str]) -> tuple[str, ...]:
    """The placeholders in ``text``, of any style, naming a claim whose span was left out."""
    return tuple(found[1] for found in PLACEHOLDER.finditer(text) if found[1] in excluded)
