"""Rule H: a stock's reviewed guidance mapping file and the window rule (RESEARCH-3 S2).

``config/analysis/guidance_targets/<symbol>.yaml`` holds one live entry per stated quote. A sealed
row pins
its digest, so a used entry can only be corrected by a ``supersedes`` entry, never edited.
"""

from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from equity_os.analysis.calculations.run_traces import RunDraftError
from equity_os.extraction.packages.capture_intake import NSE_WALL_ZONE

ROOT = Path(__file__).resolve().parents[4]
GUIDANCE_KEY = "ledger.{metric}.{horizon}.{scope}"  # as import_mapping keys a ledger entry
WINDOW_MULTI_YEAR, WINDOW_AMBIGUOUS = "MULTI_YEAR", "AMBIGUOUS"
UNDATED = {WINDOW_MULTI_YEAR: "window not single-year", WINDOW_AMBIGUOUS: "window not established"}
_DIGEST_FIELDS = set(
    "id claim_key source_sha256 anchor quote window_text window reading definition same_as "
    "supersedes".split()
)
# Year-on-year names a comparison basis, not a period, so it goes before any other wording is read.
_BASIS = re.compile(
    r"\byear[- ]on(?:[- ]year)?\b|\byoy\b|\by-o-y\b|\ba year (?:ago|earlier)\b", re.I
)
_RECURRING = re.compile(
    r"\bCAGR\b|\b(?:a|per|every|each) year\b|\bper annum\b|\bannually\b"
    r"|\b(?:\d+|two|three|four|five)[- ]years?\b",
    re.I,
)
_LABEL = re.compile(r"\bFY(?:20)?(\d{2})\b", re.I)
_THIS_YEAR = re.compile(r"\b(?:this|current) year\b", re.I)
_NEXT_YEAR = re.compile(r"\bnext year\b", re.I)


class Reading(StrEnum):
    """A reviewed judgment of the quote's context: a stated target, or anything short of one."""

    COMMITMENT = "COMMITMENT"
    DESCRIPTIVE = "DESCRIPTIVE"


class TargetEntry(BaseModel):
    """One mapped statement: its reviewed reading, window, definition and links."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    claim_key: str
    source_sha256: str
    anchor: str
    quote: str
    window_text: str
    window: str = Field(pattern=r"^(?:FY\d{2}|MULTI_YEAR|AMBIGUOUS)$")
    reading: Reading
    definition: str = Field(pattern=r"^[\w -]+$")  # shown in a correction line, so never markup
    same_as: str | None = None
    supersedes: str | None = None

    @model_validator(mode="after")
    def _window_text_in_quote(self) -> TargetEntry:
        """The window can only rest on the quote's own words."""
        if self.window_text not in self.quote:
            raise ValueError(f"{self.id}: window_text is not in the quote")
        return self

    @property
    def digest(self) -> str:
        """SHA-256 of the entry's fixed preimage, in compact sorted JSON."""
        fields = self.model_dump(mode="json", include=_DIGEST_FIELDS)
        text = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()

    @property
    def triple(self) -> tuple[str, str, str]:
        """The statement this entry maps."""
        return self.claim_key, self.source_sha256, self.anchor


class _Document(BaseModel):
    """A mapping file's envelope."""

    entries: tuple[TargetEntry, ...]


class Targets(BaseModel):
    """A loaded mapping file, its links resolved on demand."""

    model_config = ConfigDict(frozen=True)

    entries: Mapping[str, TargetEntry]

    def successor(self, entry_id: str) -> TargetEntry | None:
        """The entry correcting ``entry_id``, if any."""
        return next((e for e in self.entries.values() if e.supersedes == entry_id), None)

    def live(self, claim_key: str, sha256: str, anchor: str) -> TargetEntry | None:
        """The statement's entry that no other corrects."""
        triple = (claim_key, sha256, anchor)
        found = (e for e in self.entries.values() if e.triple == triple)
        return next((e for e in found if self.successor(e.id) is None), None)

    def chain(self, entry: TargetEntry) -> tuple[TargetEntry, ...]:
        """Every entry deciding ``entry``'s episode, successors and links alike; refuses a cycle."""
        walked = [entry]
        while True:
            current = walked[-1]
            following = self.successor(current.id) or (
                self.entries[current.same_as] if current.same_as else None
            )
            if following is None:
                return tuple(walked)
            if following in walked:
                raise RunDraftError(f"guidance target {following.id}: cycle in its links")
            walked.append(following)

    def root(self, entry: TargetEntry) -> TargetEntry:
        """The entry naming ``entry``'s episode: the last of its chain."""
        return self.chain(entry)[-1]


def load_targets(symbol: str, root: Path = ROOT) -> Targets:
    """``symbol``'s mapping file; empty when it has none, refused when structurally wrong."""
    path = root / "config" / "analysis/guidance_targets" / f"{symbol.lower()}.yaml"
    if not path.exists():
        return Targets(entries={})
    try:
        entries = _Document.model_validate(yaml.safe_load(path.read_text("utf-8"))).entries
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise RunDraftError(f"guidance targets of {symbol}: malformed YAML") from error
    except ValidationError as error:
        found = "; ".join(f"{e['loc']}: {e['msg']}" for e in error.errors())
        raise RunDraftError(f"guidance targets of {symbol}: {found}") from error
    targets = Targets(entries={entry.id: entry for entry in entries})
    if len(targets.entries) != len(entries):
        raise RunDraftError(f"guidance targets of {symbol}: duplicate id")
    _check_links(entries, targets)
    return targets


def _check_links(entries: Sequence[TargetEntry], targets: Targets) -> None:
    """Refuse a correction or link that does not hold, before and after successor resolution."""
    by_id, position = targets.entries, {entry.id: at for at, entry in enumerate(entries)}
    corrected = Counter(entry.supersedes for entry in entries if entry.supersedes)
    for entry in entries:
        old = by_id.get(entry.supersedes) if entry.supersedes else None
        if entry.supersedes and (
            old is None
            or old.triple != entry.triple
            or old.quote != entry.quote
            or corrected[entry.supersedes] > 1
        ):
            raise RunDraftError(f"guidance target {entry.id}: wrong supersedes")
        if entry.same_as and position.get(entry.same_as, len(entries)) >= position[entry.id]:
            raise RunDraftError(f"guidance target {entry.id}: same_as names no earlier entry")
    for entry in entries:
        targets.chain(entry)
    live = [entry for entry in entries if entry.id not in corrected]
    if repeated := [triple for triple, n in Counter(e.triple for e in live).items() if n > 1]:
        raise RunDraftError(f"guidance targets: several live entries on {repeated[0]}")
    for entry in live:
        target = targets.live(*by_id[entry.same_as].triple) if entry.same_as else None
        if target is not None and (
            (*_metric_scope(entry), entry.window) != (*_metric_scope(target), target.window)
            or Reading.DESCRIPTIVE in (entry.reading, target.reading)
        ):
            raise RunDraftError(f"guidance target {entry.id}: same_as restates no such promise")


def _metric_scope(entry: TargetEntry) -> tuple[str, str]:
    """The metric and scope in the entry's ledger key."""
    parts = entry.claim_key.split(".")
    return parts[1], parts[-1]


def check_pins(targets: Targets, pins: Mapping[str, str]) -> None:
    """Refuse when a pinned entry is gone or its digest differs: history cannot be rewritten."""
    for entry_id, digest in pins.items():
        entry = targets.entries.get(entry_id)
        if entry is None or entry.digest != digest:
            raise RunDraftError(
                f"guidance target {entry_id} is used by a sealed version and "
                f"{'is gone' if entry is None else 'changed'}; correct it with a supersedes entry"
            )


def fiscal_year(day: date, month: int) -> int:
    """The end year of the fiscal year holding ``day``, for a year ending in ``month``."""
    return day.year if day.month <= month else day.year + 1


def fiscal_span(label: str, month: int) -> tuple[date, date]:
    """First and last day of fiscal year ``FY<yy>``."""
    year = 2000 + int(label[2:])
    end = date(year, month, monthrange(year, month)[1])
    return (date(year - 1, month + 1, 1) if month < 12 else date(year, 1, 1)), end


def derive_window(text: str, filed_at: datetime | None, stated_end: date, month: int) -> str:
    """``FY<yy>``, ``MULTI_YEAR`` or ``AMBIGUOUS``, from the quote's words alone (plan P3)."""
    words = _BASIS.sub(" ", text)
    if _RECURRING.search(words):
        return WINDOW_MULTI_YEAR
    labels = {found.group(1) for found in _LABEL.finditer(words)}
    relative = [ahead for ahead, says in enumerate((_THIS_YEAR, _NEXT_YEAR)) if says.search(words)]
    if len(labels) > 1 or len(relative) > 1:
        return WINDOW_MULTI_YEAR
    if not relative:
        return f"FY{labels.pop()}" if labels else WINDOW_AMBIGUOUS
    if filed_at is None:
        return WINDOW_AMBIGUOUS
    reference = fiscal_year(filed_at.astimezone(NSE_WALL_ZONE).date(), month)
    if reference > fiscal_year(stated_end, month):
        return WINDOW_AMBIGUOUS
    year = f"{(reference + relative[0]) % 100:02d}"
    return WINDOW_MULTI_YEAR if labels - {year} else f"FY{year}"
