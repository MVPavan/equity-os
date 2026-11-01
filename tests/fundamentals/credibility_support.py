"""Builders both RESEARCH-3 S2 credibility test files use; new production names import lazily."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
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


ENDS = {
    "FY26_Q1": date(2025, 6, 30),
    "FY26_Q2": date(2025, 9, 30),
    "FY26_Q3": date(2025, 12, 31),
    "FY26_Q4": date(2026, 3, 31),
    "FY27_Q1": date(2026, 6, 30),
}
GROWTH = "revenue_growth.consolidated"
FY26, FY27 = f"{GROWTH}.FY26", f"{GROWTH}.FY27"
WHOLE = "(all computed digits)"
CUT = "(first six decimal places, cut and not rounded; more digits follow)"
TOLERANCE = (
    "rounded to the guidance's stated precision",
    "the verdict rounds the exact computed value once",
)
INTERIM = "seasonality not adjusted; year-to-date assumed representative"
WRONG_WAY = "open bound in the wrong direction"
# The content each disclosure must keep (plan "Report disclosures"; wording may tighten around it).
DISCLOSURES = (
    "no overall credibility judgment",
    "not an inventory of management's commitments",
    "before this report chain's first period are absent",
    "kept as evidence and is never scored",
    "reviewed mapping file",
    "after these calls were published",
    "extracted guidance contract",
    "labels every quote consolidated",
    "midpoint",
    "binding bound",
    '"about" is ignored',
    "not whether it is good or bad",
    "computes no comparable actual",
    "no single-year window",
)
D8 = "no row in this version reaches an achieved, missed or interim outcome. reasons:"
D9 = "no guidance quote has been extracted in this report chain"
SPLIT = "growth of 10% in FY26 and FY27"


def direction(better: str | None) -> Any:
    return None if better is None else cred_module().Better[better]


def measured(
    window: str, exact: Fraction, *, scope: str = "consolidated", ytd: bool = False
) -> tuple[NumericClaim, dict[str, Fraction]]:
    """A ``cred.*`` claim of the exact value's digits, and the exact value by its key."""
    from fundamentals.canon.interval import truncate_value
    from fundamentals.ledger.display import EXACT_DIGITS

    cred = cred_module()
    key = cred.ACTUAL_KEY.format(metric="revenue_growth", scope=scope, window=window)
    key += ".ytd" if ytd else ""
    held = NumericClaim(
        claim_key=key,
        section_key="management_credibility",
        citation=Citation(kind=CitationKind.CALCULATION, calculation_trace_id=9),
        value_kind=ValueKind.PERCENTAGE,
        unit="%",
        value=truncate_value(exact, cred.EXACT_PLACES),
        qualifiers=(EXACT_DIGITS,),
        precision=cred.EXACT_PLACES,
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.INFERRED if ytd else EpistemicClass.COMPUTED,
    )
    return held, {key: exact}


def _read(section: Any) -> Any:
    cred = cred_module()
    return cred.read_record(section.body, section.claims) if section else cred.Record()


def prepared(
    claims: Any,
    mapping: Any,
    period: str,
    prior: Any = None,
    *,
    same: Any = None,
    filed: Any = None,
) -> Any:
    """``prepare`` on the previous build or record (``same``: the same-period build)."""
    cred = cred_module()
    return cred.prepare(
        claims,
        prior if isinstance(prior, cred.Record) else _read(prior),
        _read(same),
        mapping,
        period=period,
        period_end=ENDS[period],
        month=3,
        filed_at=filed or {},
        actual_blobs=frozenset(),
    )


def finish(prep: Any, *, actuals: Any = (), unavailable: Any = None, measures: Any = None) -> Any:
    """``build`` of a prepared run; ``actuals`` are ``measured`` pairs."""
    return cred_module().build(
        prep,
        actuals=tuple(held for held, _ in actuals),
        exact={key: value for _, values in actuals for key, value in values.items()},
        unavailable=unavailable or {},
        registry={} if measures is None else measures,
    )


def built(
    claims: Any, mapping: Any, period: str, prior: Any = None, *, filed: Any = None, **kw: Any
) -> Any:
    return finish(prepared(claims, mapping, period, prior, filed=filed), **kw)


def chain(a: Any, b: Any, mapping: Any) -> Any:
    """Two statements in consecutive runs: A at FY26_Q1, then B at FY26_Q2."""
    return built((b,), mapping, "FY26_Q2", built((a,), mapping, "FY26_Q1"))


def unresolved(line: str, *reasons: str) -> None:
    assert set(outcomes(line)) == {"UNRESOLVED"}, line
    assert all(reason in line for reason in reasons), line


def by_key(section: Any) -> dict[str, NumericClaim]:
    return {held.claim_key: held for held in section.claims}


def correction(body: str, *tokens: str) -> None:
    """Exactly one non-record line names every token."""
    skip = ("- statement", "- retired")
    lines = [s for s in body.splitlines() if not s.lstrip().startswith(skip)]
    assert len([s for s in lines if all(token in s for token in tokens)]) == 1, tokens


Q3_END, Q4_END = ENDS["FY26_Q3"], ENDS["FY26_Q4"]
Q3_FILED = datetime(2026, 2, 4, tzinfo=UTC)  # the pinned manifest's FY26_Q3 transcript
Q4_FILED = datetime(2026, 6, 4, tzinfo=UTC)  # after FY26's year end
RECURRING = (
    "a 20% CAGR|growing by 25% a year|20% per year|20% every year|20% each year|20% per annum|"
    "20% annually|over three years|over a 5-year plan|year on year for the next three years|"
    "10% in FY26 and 12% in FY27"
)
UNDATED = (
    "20% year on year|guiding a growth of 25% year on|a 10% growth year-on-year on our|20% yoy|"
    "20% y-o-y|above a year ago|above a year earlier|guidance of 30,000 per metric ton"
)

A = claim(page=1)
B = claim(low="12", page=2)
METRIC = claim("margin", page=3, quote="margin of 10% in FY26")
SCOPE = claim(scope="standalone", page=4)
MULTI = claim(page=5, quote="growth of 10% a year")
MULTI_B = claim(low="12", page=6, quote="growth of 12% a year")
YEAR = claim(page=7, quote="growth of 10% in FY27")


def faults() -> dict[str, tuple[dict[str, Any], ...]]:
    """Mapping files that must refuse at load."""
    a, b, a2 = entry("A", A), entry("B", B), entry("A2", A, supersedes="A")
    linked, multi = {**b, "same_as": "A"}, entry("M", MULTI, "MULTI_YEAR")
    return {
        "duplicate-id": (a, entry("A", B)),
        "id-outside-the-alphabet": (entry("a b", A),),
        "unknown-window": (entry("A", A, "next decade"),),
        "unknown-reading": (entry("A", A, reading="PROMISE"),),
        "window-text-outside-quote": (entry("A", A, window_text="FY29"),),
        "two-live-on-one-triple": (a, entry("B", A)),
        "supersedes-unknown": (entry("A", A, supersedes="Z"),),
        "successor-of-another-statement": (a, entry("A2", B, supersedes="A")),
        "successor-with-another-quote": (a, {**a2, "quote": "growth of 10% in FY26 or so"}),
        "successor-on-another-blob": (a, entry("A2", claim(blob="b" * 64), supersedes="A")),
        "two-successors": (a, a2, entry("A3", A, supersedes="A")),
        "supersedes-cycle": (entry("A", A, supersedes="A2"), a2),
        "same-as-unknown": (entry("A", A, same_as="Z"),),
        "same-as-later": (entry("B", B, same_as="A"), a),
        "same-as-another-metric": (a, entry("O", METRIC, same_as="A")),
        "same-as-another-scope": (a, entry("O", SCOPE, same_as="A")),
        "same-as-another-class": (a, entry("M", MULTI, "MULTI_YEAR", same_as="A")),
        "same-as-another-year": (a, entry("Y", YEAR, "FY27", same_as="A")),
        "incompatible-after-resolution": (
            multi,
            entry("MB", MULTI_B, "MULTI_YEAR", same_as="M"),
            entry("M2", MULTI, "AMBIGUOUS", supersedes="M"),
        ),
        "cycle-through-a-successor": (a, linked, entry("A2", A, supersedes="A", same_as="B")),
        "self-link-after-resolution": (a, entry("A2", A, supersedes="A", same_as="A")),
        "descriptive-links": (a, entry("B", B, reading="DESCRIPTIVE", same_as="A")),
        "links-a-descriptive": (entry("A", A, reading="DESCRIPTIVE"), linked),
        "descriptive-after-resolution": (
            a,
            linked,
            entry("A2", A, reading="DESCRIPTIVE", supersedes="A"),
        ),
    }


DIGEST_SAMPLE = {
    "id": "sample-FY26_Q2",
    "claim_key": "ledger.revenue_growth.annual.consolidated",
    "source_sha256": BLOB,
    "anchor": "p1.b1.0:9",
    "quote": "₹ growth of 10% in FY26",
    "window_text": "FY26",
    "window": "FY26",
    "reading": "COMMITMENT",
    "definition": "revenue_growth",
    "same_as": None,
    "supersedes": None,
}


def _tampered(body: str) -> dict[str, str]:
    """``body`` broken each way a complete parse must refuse."""
    lines = record_lines(body)
    a, b = lines["A"].group(0) + "\n", lines["B"].group(0) + "\n"
    z = b.replace("(B sha256", "(Z sha256")
    return {
        "malformed-line": body.replace(" stated FY26_Q1", " stated FYxx", 1),
        "duplicate-entry": body.replace(b, b + a.replace("(A sha", "(B sha")),
        "duplicate-claim": body.replace(b, b + z),
        "omitted-statement": body.replace(b, ""),
        "extra-line": body.replace(b, b + z.replace(".latest|", ".absent|")),
        "malformed-retired": body.replace("- none", "- retired A sha256 nothex", 1),
        "missing-header": body.replace("Retired entries:", "Entries:", 1),
    }
