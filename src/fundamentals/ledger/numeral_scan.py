"""Numeric-coverage and prose-label scans of a draft section (ledger spec §1 Rules; plan D9).

Narrative numbers come only from claim placeholders: any other numeral blocks unless it is
structural. Each paragraph carries an epistemic-class marker, and an observed one is backed by
a claim placeholder or a resolving location marker. Imports are exempt (the caller skips them).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import VersionState
from fundamentals.contracts.memory import SupportTarget
from fundamentals.ledger.display import PLACEHOLDER

CLASS_MARKER = re.compile(r"\{\{e:([^}]*)\}\}")
LOCATION_MARKER = re.compile(r"\{\{s:([^|}]*)\|([^}]*)\}\}")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_NOT_PROSE = re.compile(r"^(#.*|-{3,}|\s*)$")
_NUMERAL = re.compile(r"\d")
# run_draft.recall emits memory row IDs and the shared support-target IDs.
_ID_PREFIXES = frozenset(
    {"memory", *(target.value.removesuffix("_id") for target in SupportTarget)}
)
# Structural numerals (ledger spec §1), removed before the numeral search.
_STRUCTURAL = re.compile(
    "|".join(
        (
            r"^[ \t]*\d+[.)][ \t]",  # list numbering
            r"^#+[ \t]*\d+(?:\.\d+)*\.?",  # section ordinals
            r"\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?",  # dates
            r"\bFY\d{2,4}(?:_Q[1-4])?\b|\b[QH][1-4]\b",  # period labels
            r"\[\^\d+\]",  # footnote markers
            r"\bp\d+\.b\d+\.\d+:\d+\b",  # source-location coordinates
            # provenance hashes, never a number in scientific notation
            r"\b(?:hash|sha256|commit|digest)[ \t:=]+(?!\d+(?:\.\d+)?e[+-]?\d+\b)"
            r"(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,64}\b",
            r"\b(?:" + "|".join(sorted(_ID_PREFIXES)) + r"):[1-9]\d*\b",
            r"\b(?:run-\d+|F\d{1,2})\b",  # rendered identifiers
            r"(?:\bPBT / revenue|\(current − prior\) / prior) × 100\b",  # formulas
        )
    ),
    re.MULTILINE,
)
_CLASSES = frozenset(EpistemicClass)


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
