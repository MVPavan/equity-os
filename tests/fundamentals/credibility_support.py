"""Builders both RESEARCH-3 S2 credibility test files use; new production names import lazily."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import Citation, CitationKind, NumericClaim, Rounding
from fundamentals.ledger.claim_check import quote_qualifiers
from fundamentals.ledger.import_mapping import _places

BLOB = "a" * 64
# The record line's grammar (plan Task 2), fully matching.
RECORD_LINE = re.compile(
    r"^  - statement \((?:(?P<entry>[A-Za-z0-9_-]+) sha256 (?P<digest>[0-9a-f]{64})|unmapped)\) "
    r"stated (?P<stated>FY\d{2}_Q[1-4]) ended (?P<ended>\d{4}-\d{2}-\d{2}): "
    r"(?P<event>[A-Z_]+)(?: \((?P<reason>[^()\d]+)\))?"
    r" \{\{c:[^|}]+\|ref\}\}(?: \{\{c:[^|}]+\|ref\}\})?$"
)
OUTCOME = re.compile(r"\b(ACHIEVED|MISSED|ON_TRACK|BEHIND|UNRESOLVED)\b")


def gt_module() -> ModuleType:
    from fundamentals.ledger import guidance_targets

    return guidance_targets


def cred_module() -> ModuleType:
    from fundamentals.ledger import credibility

    return credibility


def claim(
    metric: str = "revenue_growth",
    low: str = "10",
    high: str | None = None,
    *,
    horizon: str = "annual",
    scope: str = "consolidated",
    quote: str | None = None,
    page: int = 1,
    blob: str = BLOB,
    unit: str = "%",
    constant: bool = False,
) -> NumericClaim:
    """A guidance statement as ``run_draft._quote`` builds one."""
    top, text = high or low, quote or f"growth of {low}% in FY26"
    return NumericClaim(
        claim_key=f"ledger.{metric}.{horizon}.{scope}",
        section_key="management_ledger",
        citation=Citation(
            kind=CitationKind.SOURCE_QUOTE,
            source_sha256=blob,
            capture_ref_id=7,
            anchor=f"p{page}.b1.0:{len(text)}",
            quote=text,
        ),
        value_kind=ValueKind.PERCENTAGE,
        unit=unit,
        lower_bound=Decimal(low),
        upper_bound=Decimal(top),
        horizon=horizon,
        qualifiers=tuple(sorted(quote_qualifiers(text))),
        precision=max(_places(Decimal(low)), _places(Decimal(top))),
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.FORECAST,
        metric=metric,
        metric_label=f"{metric} guidance",
        scope=scope,
        constant_currency=constant,
    )


def entry(id_: str, stated: NumericClaim, window: str = "FY26", **over: Any) -> dict[str, Any]:
    """A mapping-file entry for a statement; ``window_text`` defaults to the whole quote."""
    cited = stated.citation
    fields = {"id": id_, "claim_key": stated.claim_key, "source_sha256": cited.source_sha256}
    fields |= {"anchor": cited.anchor, "quote": cited.quote, "window_text": cited.quote}
    return fields | {"window": window, "reading": "COMMITMENT", "definition": stated.metric} | over


def write_targets(root: Path, *entries: Mapping[str, Any]) -> Any:
    """The entries as ``root``'s mapping file for ``TEST``, loaded."""
    path = root / "config" / "guidance_targets" / "test.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": list(entries)}, allow_unicode=True), "utf-8")
    return gt_module().load_targets("TEST", root)


def measure(
    numerator: str = "revenue_from_operations",
    definition: str = "revenue_growth",
    *,
    better: str = "HIGHER",
    interim: bool = True,
) -> Any:
    cred = cred_module()
    return cred.Actual(
        numerator=numerator,
        better=cred.Better[better],
        unit="%",
        currency=None,
        definition=definition,
        interim=interim,
    )


def registry(*scopes: str, **over: Any) -> dict[Any, Any]:
    """The ``revenue_growth`` measure registered per scope (default consolidated)."""
    return {("revenue_growth", scope): measure(**over) for scope in scopes or ("consolidated",)}


def row(body: str, episode: str) -> str:
    """The episode's row: the first line naming it that is not a record line."""
    skip = ("- statement", "- retired")
    return next(s for s in body.splitlines() if episode in s and not s.lstrip().startswith(skip))


def outcomes(line: str) -> list[str]:
    return OUTCOME.findall(line)


def record_lines(body: str) -> dict[str | None, re.Match[str]]:
    """Every record line by its entry id (``None``: unmapped); each must match the grammar."""
    found = {}
    for line in body.splitlines():
        if line.lstrip().startswith("- statement"):
            match = RECORD_LINE.match(line)
            assert match is not None, line
            found[match["entry"]] = match
    return found


def event_of(body: str, entry_id: str) -> tuple[str, str | None]:
    match = record_lines(body)[entry_id]
    return match["event"], match["reason"]


def same_statement(copy: NumericClaim, stated: NumericClaim) -> bool:
    """Whether an episode claim is the guidance claim, only its key and section changed."""
    update = {"claim_key": stated.claim_key, "section_key": stated.section_key}
    return copy.model_copy(update=update) == stated
