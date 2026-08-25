"""Inline-script collection for Tijori's shareholding break-up charts.

Beside the detailed table, the shareholding page renders one aggregate chart per
subcategory as an inline script rather than as data: a JavaScript array literal
assigned to ``chartData``, with the subcategory it belongs to assigned to
``subcategory`` in the same script::

    var subcategory = "overview";
    var chartData= [['Promoter', 52.9], ['Mutual Funds', 8.73], ...];

That is source text, not JSON — the literals are single-quoted — so it is read
with :func:`ast.literal_eval` under a strict shape gate rather than
``json.loads``. Two rules make that safe to point at an untrusted page:

* ``literal_eval`` evaluates no code, but it still parses arbitrary attacker-
  chosen syntax, so a literal longer than :data:`MAX_LITERAL_CHARS` is refused
  unparsed and its resource-exhaustion failure modes (deep nesting) are caught
  alongside the syntax ones;
* only a list of ``[str, number]`` pairs is accepted. Anything else — a dict, a
  three-element row, a nested list, a numeric label, a call expression — is
  refused as a whole and retained verbatim instead of being partially read.

A refusal is recorded on the break-up, never raised: the detailed table is the
page's authoritative payload, and a drifted chart script must not take it down.
That holds for every failure mode, including two scripts declaring disagreeing
charts for one subcategory — that break-up is refused with all of its competing
literals retained, while the table and every other chart are unaffected.
The typed contract, its anchors, and the shareholding artifact live in
:mod:`fundamentals.ingest.tijori_shareholding`, which re-exports what callers
need from here.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_common import (
    TIJORI_SOURCE_ID,
    TijoriIslandStatus,
    label_number_pairs,
)
from fundamentals.ingest.tijori_shareholding_table import TijoriShareholdingSchemaError

_LOGGER = structlog.get_logger(__name__)

# The anchor's table id names the script variable and the subcategory it was
# declared beside, so a value stays locatable without a DOM element id.
BREAKUP_TABLE_ID_PREFIX = "chartData"
BREAKUP_VALUE_LABEL = "value"
MAX_LITERAL_CHARS = 200_000

_SCRIPT_TAG = "script"
_TYPE_ATTRIBUTE = "type"
_JSON_CONTENT_TYPE = "application/json"
_PATH_SEPARATOR = "/"

# The assignment is captured whatever its right-hand side looks like, not only
# when it looks like an array. A script that declares chartData as something
# else is drift to record; matching only well-shaped literals would make it
# indistinguishable from a page that declares no chart at all.
_CHART_DATA_LITERAL = re.compile(r"\bvar\s+chartData\s*=\s*(.*?)\s*;", re.DOTALL)
_SUBCATEGORY_LITERAL = re.compile(r"""\bvar\s+subcategory\s*=\s*["']([^"']*)["']\s*;""")

_NO_SUBCATEGORY = "the script declares chartData but no subcategory to address it by"
_MULTIPLE_LITERALS = "the script declares {count} chartData literals; none of them is addressable"
_TOO_LONG = "the chartData literal is {length} characters, above the {limit} parse limit"
_UNREADABLE = "the chartData literal is not a readable Python/JS array literal: {error}"
_WRONG_SHAPE = "the chartData literal is not a list of [label, number] pairs: {detail}"
_CONFLICTING = (
    "{count} scripts declare disagreeing chartData for this subcategory; refusing to guess "
    "which one is authoritative"
)


class TijoriShareholdingBreakupError(TijoriShareholdingSchemaError):
    """Two break-up slices resolved to one anchor, which is an addressing bug."""


class TijoriShareholdingBreakupEntry(BaseModel):
    """One slice of a break-up chart: its label, its reading, and its lexeme."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: Decimal
    raw_text: str
    provenance: Provenance


class TijoriShareholdingBreakup(BaseModel):
    """One subcategory's aggregate break-up, as published in an inline script.

    ``status`` is ``PRESENT`` only when the literal satisfied the strict shape
    gate. ``UNPARSEABLE`` keeps the script that was on the page but could not be
    read: ``detail`` names why and ``raw_literals`` retains the source text
    verbatim, so drift is recorded rather than silently reported as an absent
    chart. An unreadable break-up carries no entries and no anchors, because a
    partially-read chart would misstate an ownership split.

    ``raw_literals`` is a list rather than one string because a break-up can be
    unreadable for having TOO MANY sources: when several scripts declare
    disagreeing charts for one subcategory, every competing literal is retained
    so the conflict can be inspected, rather than one being picked as the
    apparent truth.
    """

    model_config = ConfigDict(frozen=True)

    subcategory: str | None
    table_id: str | None
    status: TijoriIslandStatus
    entries: tuple[TijoriShareholdingBreakupEntry, ...] = ()
    detail: str | None = None
    raw_literals: tuple[str, ...] = ()

    @property
    def entry_count(self) -> int:
        """Number of readable slices this break-up carries."""
        return len(self.entries)


class _RawBreakup(BaseModel):
    """One subcategory's chart declarations, reduced to what addresses them.

    ``literals`` holds more than one entry only when several scripts declared
    DISAGREEING charts for the same subcategory; identical repeats have already
    collapsed to one by then.
    """

    model_config = ConfigDict(frozen=True)

    subcategory: str | None
    literals: tuple[str, ...]
    literal_count: int
    conflicting: bool = False


class _BreakupScriptCollector(HTMLParser):
    """Collect the body of every inline script that is not a JSON island.

    Entity conversion stays off: a script body is source text, and HTMLParser
    hands it back raw in CDATA mode either way. The Django JSON islands are
    skipped here because :mod:`fundamentals.ingest.tijori_page` already owns
    them and their bodies never declare these variables.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.bodies: list[str] = []
        self._collecting = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Begin collecting one inline script body."""
        if tag != _SCRIPT_TAG:
            return
        content_type = dict(attrs).get(_TYPE_ATTRIBUTE)
        if content_type is not None and content_type.strip().lower() == _JSON_CONTENT_TYPE:
            return
        self._collecting = True
        self._chunks = []

    def handle_data(self, data: str) -> None:
        """Accumulate the active script body."""
        if self._collecting:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Retain the completed script body."""
        if tag != _SCRIPT_TAG or not self._collecting:
            return
        self.bodies.append("".join(self._chunks))
        self._collecting = False
        self._chunks = []


def _raw_breakups(document: str) -> tuple[_RawBreakup, ...]:
    """Reduce every inline script that declares a chart to its two declarations.

    Pairing happens inside one script because that is how the page declares it:
    associating a literal with the nearest ``subcategory`` elsewhere in the
    document would be proximity guessing, and would silently mislabel a chart
    the day the template moves one of them.
    """
    collector = _BreakupScriptCollector()
    collector.feed(document)
    collector.close()
    found: list[_RawBreakup] = []
    for body in collector.bodies:
        literals = _CHART_DATA_LITERAL.findall(body)
        if not literals:
            continue
        subcategory_match = _SUBCATEGORY_LITERAL.search(body)
        subcategory = subcategory_match.group(1).strip() if subcategory_match else None
        found.append(
            _RawBreakup(
                subcategory=subcategory or None,
                literals=(literals[0],),
                literal_count=len(literals),
            )
        )
    return tuple(found)


def _pairs(literal: str) -> tuple[tuple[str, Decimal], ...] | str:
    """Read the literal as ``[label, number]`` pairs, or name why it is not that.

    Decoding is this surface's own concern — the literal is JavaScript source,
    not JSON — while the pair-shape gate is the one shared with the overview
    page's revenue-mix charts.
    """
    if len(literal) > MAX_LITERAL_CHARS:
        return _TOO_LONG.format(length=len(literal), limit=MAX_LITERAL_CHARS)
    try:
        parsed: Any = ast.literal_eval(literal)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError) as error:
        return _UNREADABLE.format(error=type(error).__name__)
    read = label_number_pairs(parsed)
    return _WRONG_SHAPE.format(detail=read) if isinstance(read, str) else read


def _anchor(
    *,
    table_id: str,
    row_path: str,
    column_index: int,
    content_sha256: str,
    source_url: str,
    retrieved_at: datetime,
) -> Provenance:
    """Anchor one break-up slice to the script variable it was declared in.

    The anchor is ``HTML_TABLE``: the value is re-found by fetching the page and
    reading a named location inside its rendered markup, which is exactly this
    retrieval procedure. It is not a ``JSON_ISLAND`` — there is no
    ``json_script`` block here — and calling it one would misdescribe how to get
    the value back.
    """
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=content_sha256,
        anchor_type=SourceAnchorType.HTML_TABLE,
        context_ref=f"{source_url}#{table_id}{_PATH_SEPARATOR}{row_path}",
        table_id=table_id,
        row_path=row_path,
        row_label=row_path,
        column_index=column_index,
        column_label=BREAKUP_VALUE_LABEL,
        retrieved_at=retrieved_at,
        first_seen_at=retrieved_at,
    )


def _collapse_repeats(raw_breakups: tuple[_RawBreakup, ...]) -> tuple[_RawBreakup, ...]:
    """Collapse identical repeats of one subcategory; mark disagreeing ones.

    Identical collapsing mirrors how the page family already treats a repeated
    JSON island: the template renders some blocks in two layout contexts, and
    byte-identical repeats carry no ambiguity.

    Two DIFFERENT charts claiming one subcategory genuinely cannot both be
    addressed as that subcategory, so neither is read — but that is a fact about
    ONE chart, not about the page. It is recorded on that break-up, with every
    competing literal retained, rather than raised: the detailed shareholding
    table is this page's authoritative payload and must survive any chart
    script, including a self-contradicting one.
    """
    occurrences = Counter(
        breakup.subcategory for breakup in raw_breakups if breakup.subcategory is not None
    )
    distinct: dict[str, list[str]] = {}
    for breakup in raw_breakups:
        if breakup.subcategory is None:
            continue
        literals = distinct.setdefault(breakup.subcategory, [])
        candidate = breakup.literals[0]
        if all(candidate.strip() != kept.strip() for kept in literals):
            literals.append(candidate)
    resolved: list[_RawBreakup] = []
    seen: set[str] = set()
    for breakup in raw_breakups:
        subcategory = breakup.subcategory
        if subcategory is None:
            resolved.append(breakup)
            continue
        if subcategory in seen:
            continue
        seen.add(subcategory)
        competing = tuple(distinct[subcategory])
        if len(competing) > 1:
            _LOGGER.warning(
                "tijori_shareholding_conflicting_breakup",
                subcategory=subcategory,
                declarations=len(competing),
            )
            resolved.append(
                _RawBreakup(
                    subcategory=subcategory,
                    literals=competing,
                    literal_count=breakup.literal_count,
                    conflicting=True,
                )
            )
            continue
        if occurrences[subcategory] > 1:
            _LOGGER.info(
                "tijori_shareholding_identical_breakup_collapsed",
                subcategory=subcategory,
                occurrences=occurrences[subcategory],
            )
        resolved.append(breakup)
    return tuple(resolved)


def _build_breakup(
    raw_breakup: _RawBreakup,
    *,
    content_sha256: str,
    source_url: str,
    retrieved_at: datetime,
) -> TijoriShareholdingBreakup:
    """Build one break-up, recording the reason when it could not be read.

    Every failure mode ends the same way: an ``UNPARSEABLE`` break-up carrying
    its reason and every source literal involved. None of them raises, so no
    chart script can take the detailed table down with it.
    """
    if raw_breakup.subcategory is None:
        detail = _NO_SUBCATEGORY
    elif raw_breakup.conflicting:
        detail = _CONFLICTING.format(count=len(raw_breakup.literals))
    elif raw_breakup.literal_count > 1:
        detail = _MULTIPLE_LITERALS.format(count=raw_breakup.literal_count)
    else:
        detail = None
    table_id = (
        None
        if raw_breakup.subcategory is None
        else f"{BREAKUP_TABLE_ID_PREFIX}:{raw_breakup.subcategory}"
    )
    read = _pairs(raw_breakup.literals[0]) if detail is None else detail
    if isinstance(read, str) or table_id is None:
        reason = read if isinstance(read, str) else detail
        _LOGGER.warning(
            "tijori_shareholding_breakup_unreadable",
            subcategory=raw_breakup.subcategory,
            detail=reason,
        )
        return TijoriShareholdingBreakup(
            subcategory=raw_breakup.subcategory,
            table_id=table_id,
            status=TijoriIslandStatus.UNPARSEABLE,
            detail=reason,
            raw_literals=raw_breakup.literals,
        )
    return TijoriShareholdingBreakup(
        subcategory=raw_breakup.subcategory,
        table_id=table_id,
        status=TijoriIslandStatus.PRESENT,
        entries=tuple(
            TijoriShareholdingBreakupEntry(
                label=label,
                value=value,
                raw_text=str(value),
                provenance=_anchor(
                    table_id=table_id,
                    # Nothing guarantees a chart labels its slices uniquely, so
                    # position leads the address and the label follows it.
                    row_path=f"{index}{_PATH_SEPARATOR}{label}",
                    column_index=index,
                    content_sha256=content_sha256,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                ),
            )
            for index, (label, value) in enumerate(read)
        ),
    )


def _reject_duplicate_anchors(breakups: tuple[TijoriShareholdingBreakup, ...]) -> None:
    """Fail loudly when two slices across all break-ups share one anchor.

    Repeats are already collapsed by subcategory and slices are addressed by
    position, so this is a backstop: it makes any future addressing change that
    collapses two distinct slices onto one anchor fatal rather than silent.
    """
    collisions = sorted(
        f"{table_id}/{row_path}"
        for (table_id, row_path), count in Counter(
            (entry.provenance.table_id, entry.provenance.row_path)
            for breakup in breakups
            for entry in breakup.entries
        ).items()
        if count > 1
    )
    if collisions:
        raise TijoriShareholdingBreakupError(
            f"tijori shareholding break-ups anchor two slices identically: {', '.join(collisions)}"
        )


def build_shareholding_breakups(
    document: str,
    *,
    content_sha256: str,
    source_url: str,
    retrieved_at: datetime,
) -> tuple[TijoriShareholdingBreakup, ...]:
    """Build every aggregate break-up the page's inline scripts declare."""
    breakups = tuple(
        _build_breakup(
            raw_breakup,
            content_sha256=content_sha256,
            source_url=source_url,
            retrieved_at=retrieved_at,
        )
        for raw_breakup in _collapse_repeats(_raw_breakups(document))
    )
    _reject_duplicate_anchors(breakups)
    if breakups:
        _LOGGER.info(
            "tijori_shareholding_breakups_parsed",
            subcategories=[breakup.subcategory for breakup in breakups],
            unreadable=[
                breakup.subcategory
                for breakup in breakups
                if breakup.status is not TijoriIslandStatus.PRESENT
            ],
        )
    return breakups
