"""Shared builders for the RESEARCH-3 S2 credibility tests; production names import lazily."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from prep2b_support import Pilot

from fundamentals.api.cli import PILOT_VERSIONS
from fundamentals.canon.interval import Interval
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.evidence import InterpretationStatus, RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import Citation, CitationKind, ClaimState, NumericClaim, Rounding
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import check_claim, quote_qualifiers
from fundamentals.ledger.import_mapping import _places

SECTION, GUIDANCE = "management_credibility", "management_ledger"
BLOB, OTHER = "a" * 64, "b" * 64
ENDS = {
    "FY26_Q1": date(2025, 6, 30),
    "FY26_Q2": date(2025, 9, 30),
    "FY26_Q3": date(2025, 12, 31),
    "FY26_Q4": date(2026, 3, 31),
    "FY27_Q1": date(2026, 6, 30),
}
GROWTH = "revenue_growth.consolidated"
FY26, FY27 = f"{GROWTH}.FY26", f"{GROWTH}.FY27"
# The record line's grammar (plan Task 2), fully matching.
RECORD_LINE = re.compile(
    r"^  - statement \((?:(?P<entry>[A-Za-z0-9_-]+) sha256 (?P<digest>[0-9a-f]{64})|unmapped)\) "
    r"stated (?P<stated>FY\d{2}_Q[1-4]) ended (?P<ended>\d{4}-\d{2}-\d{2}): "
    r"(?P<event>[A-Z_]+)(?: \((?P<reason>[^()\d]+)\))?"
    r" \{\{c:[^|}]+\|ref\}\}(?: \{\{c:[^|}]+\|ref\}\})?$"
)
OUTCOME = re.compile(r"\b(ACHIEVED|MISSED|ON_TRACK|BEHIND|UNRESOLVED)\b")
TOLERANCE = (
    "rounded to the guidance's stated precision",
    "the verdict rounds the exact computed value once",
)
INTERIM = "seasonality not adjusted; year-to-date assumed representative"
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
_ROOT: list[Path] = []


def gt_module() -> ModuleType:
    """The mapping module, imported only when a test runs."""
    from fundamentals.ledger import guidance_targets

    return guidance_targets


def cred_module() -> ModuleType:
    """The credibility module, imported only when a test runs."""
    from fundamentals.ledger import credibility

    return credibility


@pytest.fixture(autouse=True)
def _temp_root(tmp_path: Path) -> None:
    """Each test's mapping files go under its own temp root."""
    _ROOT.append(tmp_path)


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
        section_key=GUIDANCE,
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


def targets(*entries: Mapping[str, Any]) -> Any:
    """The entries loaded from this test's temp root."""
    return write_targets(_ROOT[-1], *entries)


def registry(*scopes: str, better: str = "HIGHER", interim: bool = True) -> dict[Any, Any]:
    """A registered percentage measure of ``revenue_growth`` per scope."""
    cred = cred_module()
    held = cred.Actual(
        numerator="revenue_from_operations",
        better=cred.Better[better],
        unit="%",
        currency=None,
        definition="revenue_growth",
        interim=interim,
    )
    return {("revenue_growth", scope): held for scope in scopes or ("consolidated",)}


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
        section_key=SECTION,
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


def prepared(stated: Any, mapping: Any, period: str, prior: Any = None, **kw: Any) -> Any:
    """``prepare`` of a run on the previous build (``same``: the same-period build)."""
    cred, same = cred_module(), kw.get("same")
    return cred.prepare(
        stated,
        cred.read_record(prior.body, prior.claims) if prior else cred.Record(),
        cred.read_record(same.body, same.claims) if same else cred.Record(),
        mapping,
        period=period,
        period_end=ENDS[period],
        month=3,
        filed_at=kw.get("filed_at") or {},
        actual_blobs=frozenset(),
    )


def finish(prep: Any, *actuals: NumericClaim, measures: Any = None, **kw: Any) -> Any:
    """``build`` of a prepared run."""
    return cred_module().build(
        prep,
        actuals=actuals,
        exact=kw.get("exact") or {},
        unavailable=kw.get("unavailable") or {},
        registry={} if measures is None else measures,
    )


def built(
    stated: Any, mapping: Any, period: str, prior: Any = None, *actuals: NumericClaim, **kw: Any
) -> Any:
    """One run's section: ``prepare`` then ``build``."""
    opts = {name: kw.pop(name) for name in ("same", "filed_at") if name in kw}
    return finish(prepared(stated, mapping, period, prior, **opts), *actuals, **kw)


def row(body: str, episode: str) -> str:
    """The episode's row: the first line naming it that is not a record line."""
    skip = ("- statement", "- retired")
    return next(s for s in body.splitlines() if episode in s and not s.lstrip().startswith(skip))


def outcomes(line: str) -> list[str]:
    """A row's outcome tokens in order."""
    return OUTCOME.findall(line)


def unresolved(line: str, *reasons: str) -> None:
    """The row is unresolved and names every reason."""
    assert set(outcomes(line)) == {"UNRESOLVED"}, line
    assert all(reason in line for reason in reasons), line


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
    """A statement's event and reason, as its record line holds them."""
    match = record_lines(body)[entry_id]
    return match["event"], match["reason"]


def by_key(section: Any) -> dict[str, NumericClaim]:
    """A build's claims by key."""
    return {held.claim_key: held for held in section.claims}


def same_statement(copy: NumericClaim, stated: NumericClaim) -> bool:
    """Whether an episode claim is the guidance claim, only its key and section changed."""
    update = {"claim_key": stated.claim_key, "section_key": stated.section_key}
    return copy.model_copy(update=update) == stated


def correction(body: str, *tokens: str) -> str:
    """The one non-record line naming every token."""
    skip = ("- statement", "- retired")
    (line,) = [
        text
        for text in body.splitlines()
        if all(token in text for token in tokens) and not text.lstrip().startswith(skip)
    ]
    return line


# Task 1: the window rule -------------------------------------------------------------------------

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


# Task 1: entries, digests and pins ---------------------------------------------------------------

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
        "successor-on-another-blob": (a, entry("A2", claim(blob=OTHER), supersedes="A")),
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


# One SHA-256 computed once with hashlib over the compact sorted JSON of exactly these fields.
SAMPLE_DIGEST = "efe91d37297400b7bf74b3bacab140e34025231ea952a88bd8844f0679f848ff"
SAMPLE = {
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


# Task 2 (a): revision events ---------------------------------------------------------------------


def stated(low: str, high: str | None = None, *, plus: bool = False, **over: Any) -> Any:
    """A ``Statement`` of a point, a closed range or an open-ended promise."""
    gt = gt_module()
    definition = over.pop("definition", "revenue_growth")
    held = claim(low=low, high=high, quote=f"growth of {low}%{'-plus' if plus else ''}", **over)
    fields = entry("X", held, definition=definition, same_as=None, supersedes=None)
    return cred_module().Statement(
        claim=held, entry=gt.TargetEntry(**{**fields, "reading": gt.Reading.COMMITMENT})
    )


def direction(better: str | None) -> Any:
    """The named direction, or none registered."""
    return None if better is None else cred_module().Better[better]


WRONG_WAY = "open bound in the wrong direction"


def two(first: str, second: str, window: str = "FY26") -> tuple[Any, ...]:
    """Two restatements of one fiscal-year promise and their mapping."""
    a = claim(low=first, quote=f"growth of {first}% in {window}", page=1)
    b = claim(low=second, quote=f"growth of {second}% in {window}", page=2)
    return a, b, targets(entry("A", a, window), entry("B", b, window))


# Task 2 (j): corrections and the rebuild ---------------------------------------------------------

SPLIT = "growth of 10% in FY26 and FY27"


ACTUAL = "cred.revenue_growth.consolidated.FY26"


# Task 2 (n)-(s): the section's text and record ---------------------------------------------------


def every_status() -> tuple[Any, tuple[NumericClaim, ...]]:
    """A section whose rows reach every outcome and most events and reasons."""
    ended = claim(quote="growth of 10% in FY25", horizon="FY25", page=1)
    missed = claim(low="50", quote="growth of 50% in FY25", horizon="FY25", page=2)
    now = claim(low="12", quote="growth of 12% in FY26", horizon="FY26", page=3)
    lower = claim(low="9", high="11", quote="growth of 9% to 11% in FY26", horizon="FY26", page=4)
    future = claim(quote="growth of 10% in FY27", horizon="FY27", page=5)
    multi = claim(quote="growth of 10% a year", page=6)
    amb = claim("margin", quote="margin of 10% or so", page=7)
    described = claim("volume", quote="volume of 10% in FY26", page=8)
    mapping = targets(
        entry("E", ended, "FY25"),
        entry("EM", missed, "FY25"),
        entry("N", now),
        entry("L", lower),
        entry("F", future, "FY27"),
        entry("M", multi, "MULTI_YEAR"),
        entry("AM", amb, "AMBIGUOUS"),
        entry("D", described, reading="DESCRIPTIVE"),
    )
    first = built((ended, now, multi, amb), mapping, "FY26_Q1")
    done, one = measured("FY25", Fraction(100, 3))
    ytd, other = measured("FY26", Fraction(10), ytd=True)
    stated_now = (missed, lower, future, described)
    section = built(
        stated_now, mapping, "FY26_Q2", first, done, ytd, exact=one | other, measures=registry()
    )
    return section, (done, ytd)


def _line_of(body: str, entry_id: str) -> str:
    """A statement's record line, with its newline."""
    return record_lines(body)[entry_id].group(0) + "\n"


def _after_b(body: str, make: Callable[[str], str]) -> str:
    """``body`` with a line built from B's record line added after it."""
    held = _line_of(body, "B")
    return body.replace(held, held + make(held))


def _as_z(line: str) -> str:
    """A record line under another entry id."""
    return line.replace("(B sha256", "(Z sha256")


TAMPER: dict[str, Callable[[str], str]] = {
    "malformed-line": lambda body: body.replace(" stated FY26_Q1", " stated FYxx", 1),
    "duplicate-entry": lambda body: _after_b(
        body, lambda _: _line_of(body, "A").replace("(A sha", "(B sha")
    ),
    "duplicate-claim": lambda body: _after_b(body, _as_z),
    "omitted-statement": lambda body: body.replace(_line_of(body, "B"), ""),
    "extra-line": lambda body: _after_b(body, lambda s: _as_z(s).replace(".latest|", ".absent|")),
    "malformed-retired": lambda body: body.replace("- none", "- retired A sha256 nothex", 1),
    "missing-header": lambda body: body.replace("Retired entries:", "Entries:", 1),
}


WINDOW_CASES = [
    *((text, None, Q4_END, "MULTI_YEAR") for text in RECURRING.split("|")),
    *((text, None, Q4_END, "AMBIGUOUS") for text in UNDATED.split("|")),
    ("20% year on year in FY27", None, Q4_END, "FY27"),
    ("FY26 revenue, in FY26 terms", None, Q4_END, "FY26"),
    ("growth this year", Q3_FILED, Q3_END, "FY26"),
    ("growth in the current year", Q3_FILED, Q3_END, "FY26"),
    ("growth next year", Q3_FILED, Q3_END, "FY27"),
    ("20% year on year this year", Q3_FILED, Q3_END, "FY26"),
    ("growth this year", Q4_FILED, Q4_END, "AMBIGUOUS"),
    ("growth next year", Q4_FILED, Q4_END, "AMBIGUOUS"),
    ("growth this year", None, Q3_END, "AMBIGUOUS"),
]


REVISIONS = [
    (("10",), ("12",), "HIGHER", "REVISED_UP", None),
    (("12",), ("10",), "HIGHER", "REVISED_DOWN", None),
    (("12",), ("10",), "LOWER", "REVISED_DOWN", None),  # a number's move, not good or bad
    (("9", "11"), ("12", "14"), None, "REVISED_UP", None),
    (("30000",), ("35000", "36000"), None, "REVISED_UP", None),
    (("9", "11"), ("8", "12"), None, "REVISED", "range widened"),
    (("9", "11"), ("9.5", "10.5"), None, "REVISED", "range narrowed"),
    (("10",), ("9", "11"), None, "REVISED", "range widened"),
    (("10",), ("10",), None, "REAFFIRMED", None),
    (("9", "11"), ("9", "11"), None, "REAFFIRMED", None),
]


OPEN_ENDED = [
    (("18", "22", False), ("20", None, True), "HIGHER", "REVISED_UP", None),
    (("20", None, True), ("18", "22", False), "HIGHER", "REVISED_DOWN", None),
    (("10", "15", False), ("15", None, True), "HIGHER", "REVISED_UP", None),
    (("20", None, False), ("25", None, True), None, "REVISED_UP", None),
    (("25", None, True), ("20", None, False), None, "REVISED_DOWN", None),
    (("18", "22", False), ("20", None, True), None, "UNRESOLVED", "direction not registered"),
    (("18", "22", False), ("20", None, True), "LOWER", "UNRESOLVED", WRONG_WAY),
    (("20", None, True), ("25", None, True), "LOWER", "UNRESOLVED", WRONG_WAY),
]


VERDICTS = [
    ("9.495", ("10",), "HIGHER", False),
    ("9.50", ("10",), "HIGHER", True),  # the stored two-place figure would pass
    ("10.5", ("11",), "HIGHER", False),  # half-even to ten
    ("10.5000001", ("11",), "HIGHER", True),
    ("11.5", ("12",), "HIGHER", True),  # half-even to twelve
    ("9.45", ("9.5", "10"), "HIGHER", False),  # the statement's precision is one place
    ("9.55", ("9.5", "10"), "HIGHER", True),
    ("5.4", ("5",), "LOWER", True),
    ("5.5", ("5",), "LOWER", False),
    ("7", ("5", "8"), "LOWER", True),  # the upper bound binds
    ("9", ("5", "8"), "LOWER", False),
]


ASSESSED = [
    ("ENDED", Fraction(9), None, False, "HIGHER", "MISSED"),
    ("ENDED", Fraction(10), None, False, "HIGHER", "ACHIEVED"),
    ("OPEN", None, Fraction(9), False, "HIGHER", "BEHIND"),
    ("OPEN", None, Fraction(10), False, "HIGHER", "ON_TRACK"),
    ("ENDED", Fraction(1), None, True, "LOWER", "UNRESOLVED"),
    ("OPEN", None, Fraction(1), True, "LOWER", "UNRESOLVED"),
    ("ENDED", None, None, False, "HIGHER", "UNRESOLVED"),
    ("OPEN", None, None, False, "HIGHER", "UNRESOLVED"),
]


TRUNCATIONS = [
    (Fraction("9.495"), "9.495000"),
    (Fraction(100, 3), "33.333333"),
    (Fraction(-100, 3), "-33.333333"),
    (Fraction("10.5000001"), "10.500000"),
]


ROW_ACTUALS = [
    (Fraction("9.495"), "10", "9.495000%", True, "MISSED"),
    (Fraction(100, 3), "33", "33.333333%", False, "ACHIEVED"),
    (Fraction(-100, 3), "5", "-33.333333%", False, "MISSED"),
    (Fraction("10.5"), "11", "10.500000%", True, "MISSED"),
    (Fraction("10.5000001"), "11", "10.500000%", False, "ACHIEVED"),
]


WINDOW_STATES = [
    ("FY27", date(2026, 3, 31), "NOT_STARTED"),
    ("FY27", date(2026, 6, 30), "OPEN"),
    ("FY26", date(2026, 3, 31), "ENDED"),
    ("FY26", date(2026, 6, 30), "ENDED"),
    ("FY26", date(2025, 3, 31), "NOT_STARTED"),
    ("FY26", date(2025, 4, 1), "OPEN"),
]


REVENUE = "revenue_from_operations"


def all_counts(pilot: Pilot) -> dict[str, int]:
    """Every ``eqos`` table's row count: a refusal must leave all of them unchanged."""
    tables = pilot.query("SELECT tablename FROM pg_tables WHERE schemaname = 'eqos'")
    return {name: int(pilot.query(f"SELECT count(*) FROM eqos.{name}")[0][0]) for (name,) in tables}


def seed(
    pilot: Pilot,
    blob: str,
    period: tuple[date, date],
    value: str,
    *,
    basis: Basis = Basis.CONSOLIDATED,
    canonical: str = REVENUE,
    interval: Interval | None = None,
    salt: str = "",
) -> int:
    """A mapped interpretation stored on the capture through the real repository, as a template
    copy; its id. The capture must be registered."""
    surface = SURFACE_OF[Representation.XBRL].value
    with pilot.pg_db.runtime_pool() as pool:
        repo = EvidenceRepository(pool)
        ((source_id,), *_) = pilot.query(
            "SELECT source_id FROM eqos.capture_refs WHERE blob_sha256 = %s AND surface = %s "
            "ORDER BY id",
            blob,
            surface,
        )
        capture = repo.find_capture_ref(source_id, surface, blob)
        template = next(
            item
            for item in repo.list_capture_interpretations(capture.capture_ref_id)
            if item.status is InterpretationStatus.MAPPED
            and item.key is not None
            and item.key.canonical_id == REVENUE
        )
        span = PeriodInterval.duration(*period)
        key = template.key.model_copy(
            update={"basis": basis, "period": span, "canonical_id": canonical}
        )
        (new_id,) = repo.reserve_interpretation_ids(1)
        label = f"{blob}{period}{basis}{canonical}{value}{salt}".encode()
        repo.put_interpretations(
            [
                template.model_copy(
                    update={
                        "interpretation_id": new_id,
                        "basis": basis,
                        "period": span,
                        "key": key,
                        "value": Decimal(value),
                        "interval": interval or Interval.exact(Decimal(value)),
                        "input_digest": hashlib.sha256(label).hexdigest(),
                        "recorded_at": repo.store_clock() + timedelta(microseconds=1),
                    }
                )
            ]
        )
    return int(new_id)


def direct(
    pilot: Pilot,
    update: Any,
    stated: tuple[NumericClaim, ...],
    entries: tuple[dict[str, Any], ...],
    measures: Mapping[Any, Any],
    *,
    period: str,
    prior_actuals: tuple[NumericClaim, ...] = (),
) -> tuple[Any, Any]:
    """``prepare``, the real ``bind_credibility`` on the store, and ``build``."""
    cred = cred_module()
    mapping = write_targets(pilot.tmp_path / "direct", *entries)
    prep = cred.prepare(
        stated,
        cred.Record(),
        cred.Record(),
        mapping,
        period=period,
        period_end=update.period_end,
        month=3,
        filed_at={},
        actual_blobs=frozenset(),
    )
    with pilot.pg_db.runtime_pool() as pool:
        inputs = cred.bind_credibility(
            EvidenceRepository(pool),
            update,
            prep,
            prior_actuals,
            entity_id=pilot.entity_id,
            versions=PILOT_VERSIONS,
            registry=measures,
        )
    section = cred.build(
        prep,
        actuals=inputs.actuals,
        exact=inputs.exact,
        unavailable=inputs.unavailable,
        registry=measures,
    )
    return inputs, section


def citation_state(pilot: Pilot, held: NumericClaim) -> ClaimState:
    """The real citation check of a computed claim."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        resolved = resolve_citation(
            conn.cursor(),
            held,
            entity_id=pilot.entity_id,
            overlay_position=datetime.now(UTC),
            run_ids=(),
            **pilot.sources(),
        )
    at = datetime.now(UTC) + timedelta(days=1)
    return check_claim(held, resolved, mode=RunMode.AS_KNOWN, cutoff=at, imported=False)


def operand_ids(pilot: Pilot, held: NumericClaim) -> set[int]:
    """The interpretations the claim's trace read."""
    rows = pilot.query(
        "SELECT interpretation_id FROM eqos.calculation_trace_operands "
        "WHERE calculation_trace_id = %s",
        held.citation.calculation_trace_id,
    )
    return {int(found) for (found,) in rows}


def trace_count(pilot: Pilot) -> int:
    """How many traces are stored."""
    return int(pilot.query("SELECT count(*) FROM eqos.calculation_traces")[0][0])


def traces_reading(pilot: Pilot, *ids: int) -> int:
    """How many traces read any of the interpretations."""
    return int(
        pilot.query(
            "SELECT count(*) FROM eqos.calculation_trace_operands "
            "WHERE interpretation_id = ANY(%s)",
            list(ids),
        )[0][0]
    )


def version_count(pilot: Pilot) -> int:
    """How many report versions exist."""
    return int(pilot.query("SELECT count(*) FROM eqos.report_versions")[0][0])
