"""Numeric-coverage and prose-label scans of a draft section (ledger spec §1 Rules; plan D9).

Narrative numbers come only from claim placeholders: any other numeral blocks unless it is
structural. Each paragraph carries an epistemic-class marker, and an observed one is backed by
a claim placeholder or a resolving location marker. Imports are exempt (the caller skips them).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from equity_os.contracts.measurement.guidance_claim import EpistemicClass
from equity_os.contracts.publication.ledger import VersionState
from equity_os.contracts.storage.memory import SupportTarget
from equity_os.publication.drafting.display import PLACEHOLDER

CLASS_MARKER = re.compile(r"\{\{e:([^}]*)\}\}")
LOCATION_MARKER = re.compile(r"\{\{s:([^|}]*)\|([^}]*)\}\}")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_NOT_PROSE = re.compile(r"^(#.*|-{3,}|\s*)$")
_NUMERAL = re.compile(r"\d")
# run_draft.recall emits memory row IDs and the shared support-target IDs.
_ID_PREFIXES = frozenset(
    {"memory", *(target.value.removesuffix("_id") for target in SupportTarget)}
)
_DATES = r"\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?"
_PERIODS = r"\bFY\d{2,4}(?:_Q[1-4])?\b|\b[QH][1-4]\b"
# Structural numerals (ledger spec §1), removed before the numeral search.
_STRUCTURAL = re.compile(
    "|".join(
        (
            r"^[ \t]*\d+[.)][ \t]",  # list numbering
            r"^#+[ \t]*\d+(?:\.\d+)*\.?",  # section ordinals
            _DATES,
            _PERIODS,
            r"\[\^\d+\]",  # footnote markers
            r"\bp\d+\.b\d+\.\d+:\d+\b",  # source-location coordinates
            # provenance hashes, never a number in scientific notation
            r"\b(?:hash|sha256|commit|digest)[ \t:=]+(?!\d+(?:\.\d+)?e[+-]?\d+\b)"
            r"(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,64}\b",
            r"\b(?:" + "|".join(sorted(_ID_PREFIXES)) + r"):[1-9]\d*\b",
            r"\b(?:run-\d+|[A-Z]\d{1,2})\b",  # rendered identifiers
            r"(?:\bPBT / revenue|\(current − prior\) / prior) × 100\b",  # formulas
        )
    ),
    re.MULTILINE,
)
_CLASSES = frozenset(EpistemicClass)
# Spec §4's narrative-mode scan: only dates and period labels are structural.
NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty "
    "ninety hundred thousand lakh crore million billion dozen twice thrice double doubled triple "
    "tripled halve halved percent bps"
).split() + ["per cent", "basis point", "basis points"]
_NARRATIVE_EXEMPT = re.compile(f"{_DATES}|{_PERIODS}", re.ASCII)
_WORDS = "|".join(NUMBER_WORDS)
_LEXICON = re.compile(rf"\b(?:(?:{_WORDS})(?:fold)?|(?:many|multi)fold)\b|-fold\b", re.IGNORECASE)
# One pass: removing one kind first could complete a marker of another around hidden text.
_MARKER = re.compile("|".join(m.pattern for m in (PLACEHOLDER, CLASS_MARKER, LOCATION_MARKER)))
_MAY_TOUCH = frozenset(" \t\r\n(),.;?")


def scan_section(text: str, *, resolves: Callable[[str, str], bool]) -> tuple[VersionState, ...]:
    """The version-level states one draft section raises, in enum order.

    ``resolves(capture_id, anchor)`` says whether a location marker resolves (D9).
    """
    found: set[VersionState] = set()
    bare = LOCATION_MARKER.sub(" ", CLASS_MARKER.sub(" ", PLACEHOLDER.sub(" ", text)))
    if _NUMERAL.search(_STRUCTURAL.sub(" ", bare)):
        found.add(VersionState.UNREGISTERED_NUMBER)
    for paragraph in _PARAGRAPH_BREAK.split(text):
        if all(_NOT_PROSE.match(line) for line in paragraph.splitlines()):
            continue
        classes = CLASS_MARKER.findall(paragraph)
        if not classes or not set(classes) <= _CLASSES:
            found.add(VersionState.UNLABELLED_PROSE)
        locations = LOCATION_MARKER.findall(paragraph)
        failing = any(not resolves(capture_id, anchor) for capture_id, anchor in locations)
        backed = PLACEHOLDER.search(paragraph) is not None or bool(locations)
        if failing or (EpistemicClass.OBSERVED in classes and not backed):
            found.add(VersionState.UNCITED_PROSE)
    return tuple(state for state in VersionState if state in found)


def narrative_prose(text: str) -> str:
    """``text`` with its markers out and each paragraph's whitespace one space; paragraphs stay."""
    return "\n\n".join(" ".join(p.split()) for p in _PARAGRAPH_BREAK.split(_MARKER.sub(" ", text)))


def scan_narrative(text: str) -> tuple[str, ...]:
    """Why a narrative section's text may hold a number of its own; empty when clean."""
    reasons = [
        f"placeholder touches other text: {found.group()}"
        for found in PLACEHOLDER.finditer(text)
        if not _MAY_TOUCH.issuperset(text[max(found.start() - 1, 0) : found.start()])
        or not _MAY_TOUCH.issuperset(text[found.end() : found.end() + 1])
    ]
    reasons += [f"class marker: {c}" for c in CLASS_MARKER.findall(text) if c not in _CLASSES]
    bare = narrative_prose(text)
    if "{{" in bare:
        reasons.append("a {{ marker is left unfilled")
    tokens = _NARRATIVE_EXEMPT.sub(" ", bare).split()
    reasons += [f"digit: {t}" for t in tokens if any(c.isnumeric() for c in t)]
    reasons += [f"number word: {found.group()}" for found in _LEXICON.finditer(bare)]
    return tuple(reasons)


def has_numeral(text: str) -> bool:
    """Whether raw text holds a Unicode numeric character or a number word; no date or period
    exemption (VENDOR-1 reading 5)."""
    return any(c.isnumeric() for c in text) or _LEXICON.search(text) is not None
