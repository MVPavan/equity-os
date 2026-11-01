"""RESEARCH-3 S2 Tasks 1-2: rule H, revision events, outcomes and the section text (pure).

New production names are imported inside helpers, so this file collects before they exist.
Contract fixed here: a row is one line holding its episode's ``.original`` quote (and ``.latest``
with two or more statements), one outcome token per endpoint it shows, in endpoint order.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from credibility_support import (
    BLOB,
    CUT,
    D8,
    D9,
    DIGEST_SAMPLE,
    DISCLOSURES,
    ENDS,
    FY26,
    FY27,
    GROWTH,
    INTERIM,
    Q3_END,
    Q3_FILED,
    Q4_END,
    Q4_FILED,
    RECURRING,
    SPLIT,
    TOLERANCE,
    UNDATED,
    WHOLE,
    WRONG_WAY,
    A,
    B,
    _read,
    _tampered,
    built,
    by_key,
    chain,
    claim,
    correction,
    cred_module,
    direction,
    entry,
    event_of,
    faults,
    finish,
    gt_module,
    measured,
    outcomes,
    prepared,
    record_lines,
    registry,
    row,
    same_statement,
    unresolved,
    write_targets,
)

from fundamentals.extract.guidance_extractor import GuidanceRule, extract_guidance_claims
from fundamentals.ingest.pdf_source import LoadedPdf, PdfBlock, PdfPage
from fundamentals.ledger.display import PLACEHOLDER, render_section
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.ledger.run_draft import _Body
from fundamentals.ledger.run_traces import RunDraftError

_ROOT: list[Path] = []


@pytest.fixture(autouse=True)
def _temp_root(tmp_path: Path) -> None:
    _ROOT.append(tmp_path)


def targets(*entries: dict[str, Any]) -> Any:
    return write_targets(_ROOT[-1], *entries)


def stated(spec: str, **over: Any) -> Any:
    """A ``Statement`` of a point (``10``), a closed range (``9-11``) or a floor (``20+``)."""
    gt, suffix = gt_module(), "-plus" if spec.endswith("+") else ""
    low, _, high = spec.rstrip("+").partition("-")
    definition = over.pop("definition", "revenue_growth")
    held = claim(low=low, high=high or None, quote=f"growth of {low}%{suffix}", **over)
    fields = entry("X", held, definition=definition, same_as=None, supersedes=None)
    return cred_module().Statement(
        claim=held, entry=gt.TargetEntry(**{**fields, "reading": gt.Reading.COMMITMENT})
    )


def two(first: str, second: str) -> tuple[Any, ...]:
    """Two restatements of one FY26 promise and their mapping."""
    a = claim(low=first, quote=f"growth of {first}% in FY26", page=1)
    b = claim(low=second, quote=f"growth of {second}% in FY26", page=2)
    return a, b, targets(entry("A", a), entry("B", b))


@pytest.mark.parametrize(
    ("text", "filed_at", "stated_end", "window"),
    [
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
    ],
)
def test_a_window_follows_only_from_the_quotes_words(
    text: str, filed_at: datetime | None, stated_end: date, window: str
) -> None:
    """A3, A6, P3: year-on-year names a basis, a recurring rate names no one year, and a relative
    year holds only if filed inside the year it was stated for."""
    assert gt_module().derive_window(text, filed_at, stated_end, 3) == window


@pytest.mark.parametrize("fault", list(faults()))
def test_a_structurally_wrong_entry_refuses_at_load(fault: str) -> None:
    with pytest.raises(RunDraftError):
        targets(*faults()[fault])


def test_a_chain_resolves_to_its_live_entry() -> None:
    """The positive control for the cycle faults: the same links without the cycle still load."""
    held = targets(entry("A", A), entry("B", B, same_as="A"), entry("A2", A, supersedes="A"))
    assert held.live(A.claim_key, BLOB, A.citation.anchor).id == "A2"
    assert held.successor("A").id == "A2" and held.successor("A2") is None
    links = held.chain(held.entries["B"])
    assert links[0].id == "B" and links[-1].id == "A2" == held.root(held.entries["B"]).id


def test_the_entry_digest_pins_exactly_its_preimage() -> None:
    """R8: every sealed pin rests on this preimage; a field outside it could move a judgment."""
    gt = gt_module()
    sample = DIGEST_SAMPLE
    # One SHA-256 computed once with hashlib over the compact sorted JSON of exactly these fields.
    digest = "efe91d37297400b7bf74b3bacab140e34025231ea952a88bd8844f0679f848ff"
    held = gt.TargetEntry(**{**sample, "reading": gt.Reading.COMMITMENT})
    assert held.digest == digest
    for field in sample:
        value = gt.Reading.DESCRIPTIVE if field == "reading" else "changed"
        assert held.model_copy(update={field: value}).digest != digest, field


def test_a_pinned_entry_cannot_change_or_vanish() -> None:
    """A10, A13, P13: a config edit could rewrite sealed history. A superseded entry stays in the
    file and still verifies, and a link target in the pool is pinned like any statement."""
    gt = gt_module()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim(low="12", quote="growth of 12% or so", page=2)
    base, linked = entry("A", a, "AMBIGUOUS"), entry("B", b, "AMBIGUOUS", same_as="A")
    section = built((a, b), targets(base, linked), "FY26_Q2")
    pins = _read(section).pins
    with pytest.raises(RunDraftError, match="A"):
        gt.check_pins(targets({**base, "definition": "edited"}, linked), pins)
    with pytest.raises(RunDraftError, match="A"):
        gt.check_pins(targets(), pins)
    fixed = targets(base, linked, entry("A2", a, "AMBIGUOUS", supersedes="A", definition="new"))
    gt.check_pins(fixed, pins)
    correction(built((), fixed, "FY26_Q3", section).body, "A2", fixed.entries["A"].digest)


@pytest.mark.parametrize(
    ("before", "after", "better", "kind", "reason"),
    [
        ("10", "12", "HIGHER", "REVISED_UP", None),
        ("12", "10", "HIGHER", "REVISED_DOWN", None),
        ("12", "10", "LOWER", "REVISED_DOWN", None),  # a number's move, not good or bad
        ("9-11", "12-14", None, "REVISED_UP", None),
        ("30000", "35000-36000", None, "REVISED_UP", None),
        ("9-11", "8-12", None, "REVISED", "range widened"),
        ("9-11", "9.5-10.5", None, "REVISED", "range narrowed"),
        ("10", "9-11", None, "REVISED", "range widened"),
        ("9-11", "9-11", None, "REAFFIRMED", None),
        # Midpoints would call 18-22 → 20-plus "reaffirmed" when the floor rose.
        ("18-22", "20+", "HIGHER", "REVISED_UP", None),
        ("20+", "18-22", "HIGHER", "REVISED_DOWN", None),
        ("20", "25+", None, "REVISED_UP", None),
        ("18-22", "20+", None, "UNRESOLVED", "direction not registered"),
        ("18-22", "20+", "LOWER", "UNRESOLVED", WRONG_WAY),
        ("20+", "25+", "LOWER", "UNRESOLVED", WRONG_WAY),
    ],
)
def test_a_revision_states_how_the_promised_number_moved(
    before: str, after: str, better: str | None, kind: str, reason: str | None
) -> None:
    """A1, P5."""
    event = cred_module().revision(stated(before), stated(after), direction(better))
    assert (event.kind.value, event.reason) == (kind, reason)


@pytest.mark.parametrize(
    ("exact", "bound", "better", "met"),
    [
        ("9.50", "10", "HIGHER", True),  # the stored two-place figure would pass; see the row test
        ("11.5", "12", "HIGHER", True),  # half-even to twelve
        ("9.45", "9.5-10", "HIGHER", False),  # the statement's precision is one place
        ("5.4", "5", "LOWER", True),
        ("5.5", "5", "LOWER", False),
        ("7", "5-8", "LOWER", True),  # the upper bound binds
    ],
)
def test_a_verdict_rounds_the_exact_value_half_even_once(
    exact: str, bound: str, better: str, met: bool
) -> None:
    """OD-7, P4: the tolerance is the statement's own precision."""
    assert cred_module().compare(stated(bound), Fraction(exact), direction(better)) is met


@pytest.mark.parametrize(
    ("exact", "bound", "digits", "phrase", "outcome"),
    [
        (Fraction("9.495"), "10", "9.495000%", WHOLE, "MISSED"),  # rounding 9.50 would hit ten
        (Fraction(100, 3), "33", "33.333333%", CUT, "ACHIEVED"),
        (Fraction(-100, 3), "5", "-33.333333%", CUT, "MISSED"),
        (Fraction("10.5"), "11", "10.500000%", WHOLE, "MISSED"),  # half-even to ten
        (Fraction("10.5000001"), "11", "10.500000%", CUT, "ACHIEVED"),
    ],
)
def test_a_row_shows_the_actual_before_the_statements_rounding(
    exact: Fraction, bound: str, digits: str, phrase: str, outcome: str
) -> None:
    """A2, OD-7: 10.5 and 10.5000001 print alike yet earn different verdicts, so the phrase must
    say if digits follow."""
    held = claim(low=bound, quote=f"growth of {bound}% in FY26")
    actual = measured("FY26", exact)
    section = built(
        (held,), targets(entry("A", held)), "FY26_Q4", actuals=(actual,), measures=registry()
    )
    line = row(section.body, FY26)
    assert outcomes(line) == [outcome]
    assert digits in render_section(line, (*section.claims, actual[0]))
    assert phrase in line and ({WHOLE, CUT} - {phrase}).pop() not in line
    assert f"{{{{c:{actual[0].claim_key}|ref}}}}" in line and all(p in line for p in TOLERANCE)
    assert "{{e:computed}}" in line and "{{e:observed}}" in line


@pytest.mark.parametrize(
    ("latest", "period", "value", "ytd", "want"),
    [
        ("10", "FY26_Q4", Fraction("10.5"), False, ["MISSED", "ACHIEVED"]),
        ("8", "FY26_Q2", Fraction(10), True, ["BEHIND", "ON_TRACK"]),
    ],
    ids=["ended", "interim"],
)
def test_one_actual_is_judged_against_both_statements(
    latest: str, period: str, value: Fraction, ytd: bool, want: list[str]
) -> None:
    """A2, A12, OD-6: management can lower the bar and clear it, so both endpoints show side by
    side. Interim verdicts are inferences on an assumed pace, so that label is mandatory."""
    a, b, held = two("12", latest)
    first = built((a,), held, "FY26_Q1")
    actual = measured("FY26", value, ytd=ytd)
    section = built((b,), held, period, first, actuals=(actual,), measures=registry())
    line = row(section.body, FY26)
    assert outcomes(line) == want
    assert event_of(section.body, "B") == ("REVISED_DOWN", None)
    assert f"{{{{c:episode.{FY26}.original|" in line and f"{{{{c:episode.{FY26}.latest|" in line
    assert (INTERIM in line and "{{e:inferred}}" in line) is ytd


@pytest.mark.parametrize(
    ("state", "exact", "ytd"), [("ENDED", Fraction(1), None), ("OPEN", None, Fraction(1))]
)
def test_a_floor_on_a_lower_better_metric_is_never_scored(
    state: str, exact: Fraction | None, ytd: Fraction | None
) -> None:
    """R10: a floor is no ceiling, however low the actual."""
    cred = cred_module()
    held = registry(better="LOWER")[("revenue_growth", "consolidated")]
    window = cred.WindowState[state]
    got = cred.assess(stated("10+"), "FY26", held, window, exact, ytd, None)
    assert got == (cred.Outcome.UNRESOLVED, WRONG_WAY)


@pytest.mark.parametrize(
    ("quote", "window", "over", "measured_too", "reasons"),
    [
        ("on a 20%-plus CAGR", "MULTI_YEAR", {"window_text": "CAGR"}, True, ("not single-year",)),
        ("growth of 10% or so", "AMBIGUOUS", {}, True, ("window not established",)),
        # P6: naming only the window would hide that no filed measure exists either.
        ("growth of 10% or so", "AMBIGUOUS", {}, False, ("not established", "no filed measure")),
    ],
)
def test_an_unestablished_window_is_never_scored(
    quote: str, window: str, over: dict[str, str], measured_too: bool, reasons: tuple[str, ...]
) -> None:
    """A3, A4, P6: no single year to judge, even with a filed measure; every reason is named."""
    held = claim(quote=quote)
    mapping = targets(entry("A", held, window, **over))
    measures = registry() if measured_too else None
    line = row(built((held,), mapping, "FY26_Q4", measures=measures).body, f"{GROWTH}.{window}.A")
    unresolved(line, *reasons)
    assert measured_too is ("no filed measure" not in line)


def test_an_unmapped_statement_is_retained_with_its_reason(tmp_path: Path) -> None:
    """A missing file or entry is a row, not a lost quote or a refusal: a later mapping still sees
    its record line."""
    section = built((claim(),), gt_module().load_targets("NONE", tmp_path), "FY26_Q2")
    assert len(by_key(section)) == 2
    assert all(key.startswith(f"episode.{GROWTH}.UNMAPPED.") for key in by_key(section))
    unresolved(row(section.body, f"{GROWTH}.UNMAPPED"), "window not mapped")
    assert record_lines(section.body)[None]["stated"] == "FY26_Q2"


def test_fiscal_years_are_separate_episodes_from_one_transcript() -> None:
    """A5 (extraction and episode level only, C-8)."""
    text = "revenue growth 10% in FY26 and revenue growth 12% in FY27"
    page = PdfPage(page_number=1, text=text, words=(), blocks=(PdfBlock(number=1, text=text),))
    pdf = LoadedPdf(source_id="t", file_sha256=BLOB, page_count=1, pages=(page,))
    rules = tuple(
        GuidanceRule(metric="revenue_growth", pattern=rf"(\d+)% in {year}", horizon=year)
        for year in ("FY26", "FY27")
    )
    found = extract_guidance_claims(pdf, rules=rules, retrieved_at=datetime.now(UTC))
    assert [g.horizon for g in found] == ["FY26", "FY27"]
    held = tuple(
        claim(low=str(g.lower_bound), horizon=g.horizon, quote=g.source_quote, page=index)
        for index, g in enumerate(found)
    )
    mapping = targets(*(entry(c.horizon or "", c, c.horizon or "") for c in held))
    keys = by_key(built(held, mapping, "FY26_Q2")).keys()
    assert {f"episode.{FY26}.original", f"episode.{FY27}.original"} <= keys
    body = _Body()
    body.add("management_ledger", "- first", held[0])
    with pytest.raises(RunDraftError, match="duplicate claim key"):
        body.add("management_ledger", "- again", held[0])


def test_scopes_are_separate_episodes_and_neither_moves_the_other() -> None:
    """A7: a standalone promise is not met by a consolidated actual."""
    con = claim(page=1)
    alone = claim(low="20", scope="standalone", page=2, quote="growth of 20% in FY26")
    later = claim(low="22", scope="standalone", page=3, quote="growth of 22% in FY26")
    mapping = targets(entry("C", con), entry("S", alone), entry("T", later))
    actuals = (measured("FY26", Fraction(11)), measured("FY26", Fraction(21), scope="standalone"))
    first = built((con, alone), mapping, "FY26_Q2")
    measures = registry("consolidated", "standalone")
    second = built((later,), mapping, "FY26_Q4", first, actuals=actuals, measures=measures)
    held, standalone = by_key(second), "revenue_growth.standalone.FY26"
    assert same_statement(held[f"episode.{FY26}.latest"], con)
    assert same_statement(held[f"episode.{standalone}.original"], alone)
    assert same_statement(held[f"episode.{standalone}.latest"], later)
    assert outcomes(row(second.body, FY26)) == ["ACHIEVED"]
    assert outcomes(row(second.body, standalone)) == ["ACHIEVED", "MISSED"]


def test_multi_year_promises_stay_apart_unless_linked() -> None:
    """A8: only a reviewed link joins two "a year" quotes; neither ever gets an outcome (OD-5)."""
    a = claim(quote="growth of 10% a year", page=1)
    b = claim(low="12", quote="growth of 12% a year", page=2)
    apart = targets(entry("A", a, "MULTI_YEAR"), entry("B", b, "MULTI_YEAR"))
    section = built((b,), apart, "FY26_Q3", built((a,), apart, "FY26_Q2"), measures=registry())
    assert event_of(section.body, "B") == ("OPENED", None)
    assert f"episode.{GROWTH}.MULTI_YEAR.B.original" in by_key(section)
    linked = targets(entry("A", a, "MULTI_YEAR"), entry("B", b, "MULTI_YEAR", same_as="A"))
    section = built((b,), linked, "FY26_Q3", built((a,), linked, "FY26_Q2"), measures=registry())
    assert event_of(section.body, "B") == ("REVISED_UP", None)
    assert f"episode.{GROWTH}.MULTI_YEAR.B.original" not in by_key(section)
    unresolved(row(section.body, f"{GROWTH}.MULTI_YEAR.A"), "window not single-year")


@pytest.mark.parametrize(
    "changed", [{"constant": True}, {"unit": "INR per MT"}, {"definition": "excluding exports"}]
)
def test_a_revision_on_another_basis_has_no_direction(changed: dict[str, Any]) -> None:
    """A9: twelve on one basis is not "up" from ten on another."""
    event = cred_module().revision(stated("10"), stated("12", **changed), None)
    assert (event.kind.value, event.reason) == ("REVISED", "basis changed")


def test_a_basis_change_leaves_only_the_comparable_endpoint_scored() -> None:
    """A9: a constant-currency promise cannot be judged on a reported figure."""
    a = claim(constant=True, page=1)
    b = claim(low="12", page=2, quote="growth of 12% in FY26")
    mapping = targets(entry("A", a), entry("B", b))
    first = built((a,), mapping, "FY26_Q2")
    actual = measured("FY26", Fraction(13))
    section = built((b,), mapping, "FY26_Q4", first, actuals=(actual,), measures=registry())
    assert event_of(section.body, "B") == ("REVISED", "basis changed")
    line = row(section.body, FY26)
    assert outcomes(line) == ["UNRESOLVED", "ACHIEVED"]
    assert "promise basis differs from the filed measure" in line and "constant" in line


def test_a_correction_moves_the_quote_and_discloses_it_once() -> None:
    """A11: both interpretations show, the old episode says so once and is dropped, the quote moves
    to its new one, the old pin still verifies."""
    a = claim(quote=SPLIT)
    old = entry("A", a, window_text="in FY26")
    first = built((a,), targets(old), "FY26_Q2")
    fixed = targets(old, entry("A2", a, "MULTI_YEAR", supersedes="A", window_text="FY26 and FY27"))
    gt_module().check_pins(fixed, _read(first).pins)
    second = built((), fixed, "FY26_Q3", first, measures=registry())
    digests = (fixed.entries["A"].digest, fixed.entries["A2"].digest)
    correction(second.body, "A2", *digests, "FY26", "MULTI_YEAR", "revenue_growth")
    unresolved(row(second.body, FY26), "mapping corrected", "A2")
    assert same_statement(by_key(second)[f"episode.{GROWTH}.MULTI_YEAR.A2.original"], a)
    assert not [key for key in by_key(second) if f".{FY26}." in key]
    record = _read(second)
    assert record.retired == {"A": digests[0]} and record.pins["A2"] == digests[1]
    third = built((), fixed, "FY26_Q4", second, measures=registry())
    assert "mapping corrected" not in third.body
    assert re.search(rf"^- retired A sha256 {digests[0]} successor A2$", third.body, re.M)


def test_correcting_a_middle_statement_recomputes_its_neighbours() -> None:
    """R2: events are rebuilt, never read back. Moving the middle statement makes the third follow
    the first, so its event flips, while the moved quote keeps its whole contract."""
    a = claim(page=1)
    b = claim(low="12", quote="growth of 12% in FY26 or FY27", page=2)
    c = claim(low="11", quote="growth of 11% in FY26", page=3)
    entries = (entry("A", a), entry("B", b, window_text="FY26"), entry("C", c))
    held = targets(*entries)
    three = built((c,), held, "FY26_Q3", chain(a, b, held))
    assert event_of(three.body, "B") == ("REVISED_UP", None)
    assert event_of(three.body, "C") == ("REVISED_DOWN", None)
    assert f"episode.{FY26}.stated.B" in by_key(three)
    fixed = targets(*entries, entry("B2", b, "FY27", supersedes="B", window_text="FY27"))
    four = built((), fixed, "FY26_Q4", three)
    assert event_of(four.body, "C") == ("REVISED_UP", None)
    assert record_lines(four.body)["B2"]["stated"] == "FY26_Q2"
    assert same_statement(by_key(four)[f"episode.{FY27}.original"], b)
    assert f"episode.{FY26}.stated.B" not in by_key(four)
    correction(four.body, "B2", fixed.entries["B"].digest, fixed.entries["B2"].digest)


def test_a_definition_correction_turns_a_directional_event_into_a_basis_change() -> None:
    """R2: if the second quote promised another measure, "up" was never true."""
    a, b, held = two("10", "12")
    second = chain(a, b, held)
    assert event_of(second.body, "B") == ("REVISED_UP", None)
    fix = entry("B2", b, supersedes="B", definition="excluding exports")
    fixed = targets(entry("A", a), entry("B", b), fix)
    third = built((), fixed, "FY26_Q3", second)
    assert event_of(third.body, "B2") == ("REVISED", "basis changed")
    correction(third.body, "B2", "excluding exports", fixed.entries["B2"].digest)


def test_a_late_mapping_is_judged_at_its_statements_own_period() -> None:
    """R4, C-7: "this year" in a post-year-end Q4 call stays ambiguous for good; the later run's
    period must not make it FY27."""
    held = claim(quote="growth of 10% this year")
    filed = {BLOB: Q4_FILED}
    first = built((held,), targets(), "FY26_Q4", filed=filed)
    second = built((), targets(entry("A", held, "AMBIGUOUS")), "FY27_Q1", first, filed=filed)
    line = record_lines(second.body)["A"]
    assert (line["stated"], line["ended"]) == ("FY26_Q4", "2026-03-31")
    assert f"episode.{GROWTH}.AMBIGUOUS.A.original" in by_key(second)
    with pytest.raises(RunDraftError, match="A"):
        prepared((), targets(entry("A", held, "FY27")), "FY27_Q1", first, filed=filed)


@pytest.mark.parametrize("target", ["unedited", "edited", "superseded"])
def test_a_link_must_resolve_through_a_recorded_statement(target: str) -> None:
    """P13: a root decides a recorded episode, or an unpinned entry could rename history. A recorded
    link to a target outside the pool refuses whatever that target did."""
    cred = cred_module()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim(low="12", quote="growth of 12% or so", page=2)
    definition = "edited" if target == "edited" else "revenue_growth"
    fixes = [entry("A2", a, "AMBIGUOUS", supersedes="A")] if target == "superseded" else []
    mapping = targets(
        entry("A", a, "AMBIGUOUS", definition=definition),
        *fixes,
        entry("B", b, "AMBIGUOUS", same_as="A"),
    )
    recorded = cred.Recorded(
        claims=(b.model_copy(update={"claim_key": f"episode.{GROWTH}.AMBIGUOUS.B.original"}),),
        stated="FY26_Q2",
        stated_end=ENDS["FY26_Q2"],
        entry_id="B",
        digest=mapping.entries["B"].digest,
    )
    with pytest.raises(RunDraftError, match="A"):
        prepared((), mapping, "FY26_Q3", cred.Record(statements=(recorded,)))


def test_a_descriptive_quote_is_evidence_and_never_a_promise() -> None:
    """P14: a rule match cannot tell a promise from a description of progress. It keeps its record
    but earns no verdict, event or due window, whatever window it declares."""
    held = claim(page=1)
    other = claim(low="12", page=2, quote="growth of 12% in FY26")
    mapping = targets(entry("D", held, reading="DESCRIPTIVE"), entry("C", other))
    prep = prepared((held,), mapping, "FY26_Q4")
    assert ("revenue_growth", "consolidated", "FY26") not in prep.windows
    first = finish(prep, measures=registry())
    episode = f"{GROWTH}.DESCRIPTIVE.D"
    assert event_of(first.body, "D") == ("DESCRIBED", None)
    line = row(first.body, episode)
    unresolved(line, cred_module().REASON_DESCRIPTIVE)
    assert "no filed measure" not in line and "window not" not in line
    second = built((other,), mapping, "FY27_Q1", first, measures=registry())
    assert event_of(second.body, "C") == ("OPENED", None)  # no event against the description
    assert f"episode.{episode}.original" in by_key(second)


def test_correcting_a_commitment_to_descriptive_shows_both_readings() -> None:
    """P14 through the correction path."""
    a = claim(page=1)
    old = entry("A", a)
    first = built((a,), targets(old), "FY26_Q2")
    fixed = targets(old, entry("A2", a, reading="DESCRIPTIVE", supersedes="A"))
    second = built((), fixed, "FY26_Q3", first, measures=registry())
    correction(second.body, "A2", "COMMITMENT", "DESCRIPTIVE")
    assert f"episode.{GROWTH}.DESCRIPTIVE.A2.original" in by_key(second)
    assert "mapping corrected" in row(second.body, FY26)


@pytest.mark.parametrize(
    ("quote", "over"),
    [
        (None, {"quote": "growth of 10% in FY26, restated"}),
        (None, {"window": "FY27"}),
        ("growth of 10% or so", {"window": "FY26"}),  # A4, OD-9: an anchor cannot supply a year
    ],
)
def test_prepare_refuses_a_new_entry_that_disagrees_with_its_statement(
    quote: str | None, over: dict[str, Any]
) -> None:
    """F1: window_text ⊂ entry quote = claim quote = retained span is a window's evidence."""
    held = claim(quote=quote)
    with pytest.raises(RunDraftError, match="A"):
        prepared((held,), targets(entry("A", held, **over)), "FY26_Q2")


def test_prepare_refuses_to_lose_a_pin() -> None:
    """F1: a pin this build would not carry could later be edited unnoticed."""
    held = claim()
    mapping = targets(entry("A", held))
    with pytest.raises(RunDraftError, match="A"):
        prepared((), mapping, "FY26_Q2", same=built((held,), mapping, "FY26_Q2"))


@pytest.mark.parametrize("interim", [True, False], ids=["missing-comparator", "no-interim-rule"])
def test_an_open_window_without_an_interim_value_stays_unresolved(interim: bool) -> None:
    """A12: a missing comparator window, or no interim rule, must not read as behind."""
    held = claim()
    mapping = targets(entry("A", held))
    line = row(built((held,), mapping, "FY26_Q2", measures=registry(interim=interim)).body, FY26)
    unresolved(line, *(() if interim else ("no interim rule",)))
    assert INTERIM not in line


def test_both_endpoints_carry_and_the_original_never_moves() -> None:
    """A13: restatements only move ``.latest``; a carried statement keeps its originating period."""
    a, b, held = two("10", "12")
    carried = built((), held, "FY26_Q2", built((a,), held, "FY26_Q1"))
    third = built((), held, "FY26_Q4", built((b,), held, "FY26_Q3", carried))
    assert same_statement(by_key(carried)[f"episode.{FY26}.latest"], a)
    assert same_statement(by_key(third)[f"episode.{FY26}.original"], a)
    assert same_statement(by_key(third)[f"episode.{FY26}.latest"], b)
    lines = record_lines(third.body)
    assert (lines["A"]["stated"], lines["A"]["ended"]) == ("FY26_Q1", "2025-06-30")
    assert (lines["B"]["stated"], lines["B"]["ended"]) == ("FY26_Q3", "2025-12-31")


def test_an_ended_window_with_no_usable_actual_says_why() -> None:
    """A14, F5: the binder's reason passes through, or the row reads "not filed"; never a miss."""
    held = claim()
    mapping = targets(entry("A", held))
    reason = "filed value differs across admitted captures"
    key = "cred.revenue_growth.consolidated.FY26"
    plain = built((held,), mapping, "FY26_Q4", measures=registry())
    unresolved(row(plain.body, FY26), "actual not yet filed")
    held_back = built((held,), mapping, "FY26_Q4", unavailable={key: reason}, measures=registry())
    unresolved(row(held_back.body, FY26), reason)


@pytest.mark.parametrize("value", [Fraction(50), Fraction(1)], ids=["would-meet", "would-miss"])
def test_a_future_target_is_not_due_whatever_this_year_shows(value: Fraction) -> None:
    """A12, F2: this year's pace says nothing of next year's target; only its own first quarter
    opens the window."""
    held = claim(quote="growth of 10% in FY27")
    mapping = targets(entry("A", held, "FY27"))
    early = prepared((held,), mapping, "FY26_Q2")
    assert ("revenue_growth", "consolidated", "FY27") not in early.windows
    section = finish(early, measures=registry())
    unresolved(row(section.body, FY27), "not due: target year not started")
    assert not [key for key in by_key(section) if key.startswith("cred.")]
    later = prepared((), mapping, "FY27_Q1", section)
    state = later.windows[("revenue_growth", "consolidated", "FY27")]
    assert state is cred_module().WindowState.OPEN
    actual = measured("FY27", value, ytd=True)
    scored = finish(later, actuals=(actual,), measures=registry())
    assert outcomes(row(scored.body, FY27)) == ["ON_TRACK" if value > 10 else "BEHIND"]


@pytest.mark.parametrize(
    ("end", "state"),
    [
        (date(2025, 3, 31), "NOT_STARTED"),
        (date(2025, 4, 1), "OPEN"),
        (date(2025, 6, 30), "OPEN"),
        (date(2026, 3, 31), "ENDED"),
        (date(2026, 6, 30), "ENDED"),
    ],
)
def test_a_targets_window_state_turns_on_its_own_boundaries(end: date, state: str) -> None:
    """F2: an off-by-one here would score a whole year early or never close it."""
    cred = cred_module()
    assert cred.window_state("FY26", end, 3) is cred.WindowState[state]


def test_every_status_renders_labelled_digit_free_prose_with_every_disclosure() -> None:
    """Spec §1 rules 1, 5, S1 lesson 2: a digit outside a placeholder has no claim behind it, an
    unlabelled row blurs observed, computed and inferred, and both S1 rejections were an
    undisclosed absence or basis."""
    ended = claim(quote="growth of 10% in FY25", horizon="FY25", page=1)
    missed = claim(low="50", quote="growth of 50% in FY25", horizon="FY25", page=2)
    now = claim(low="12", quote="growth of 12% in FY26", horizon="FY26", page=3)
    lower = claim(low="9", high="11", quote="growth of 9% to 11% in FY26", horizon="FY26", page=4)
    multi = claim(quote="growth of 10% a year", page=5)
    described = claim("volume", quote="volume of 10% in FY26", page=6)
    mapping = targets(
        entry("E", ended, "FY25"),
        entry("EM", missed, "FY25"),
        entry("N", now),
        entry("L", lower),
        entry("M", multi, "MULTI_YEAR"),
        entry("D", described, reading="DESCRIPTIVE"),
    )
    first = built((ended, now, multi), mapping, "FY26_Q1")
    actuals = (measured("FY25", Fraction(100, 3)), measured("FY26", Fraction(10), ytd=True))
    section = built(
        (missed, lower, described), mapping, "FY26_Q2", first, actuals=actuals, measures=registry()
    )
    assert scan_section(section.body, resolves=lambda *_: True) == ()
    render_section(section.body, (*section.claims, *(held for held, _ in actuals)))
    assert {"ACHIEVED", "MISSED", "ON_TRACK", "BEHIND", "UNRESOLVED"} <= set(outcomes(section.body))
    assert section.body.startswith("## management_credibility\n")
    for line in section.body.splitlines():
        if line.startswith("- ") and PLACEHOLDER.search(line):
            assert "{{e:" in line, line
    text = " ".join(section.body.lower().split())
    assert all(fragment in text for fragment in DISCLOSURES)


@pytest.mark.parametrize("count", [1, 2], ids=["one-statement", "two-statements"])
def test_a_line_references_exactly_the_claims_it_shows(count: int) -> None:
    """F6: a one-statement episode shows ``.original`` only; its ``.latest`` is the same statement,
    referenced by the record line."""
    a, b, held = two("10", "12")
    section = chain(a, b, held) if count == 2 else built((a,), held, "FY26_Q1")
    for line in section.body.splitlines():
        found = PLACEHOLDER.findall(line)
        shown = {key for key, style in found if style != "ref"}
        if shown:
            assert {key for key, style in found if style == "ref"} == shown, line
    shows_latest = f"{{{{c:episode.{FY26}.latest|ref}}}}" in row(section.body, FY26)
    assert shows_latest is (count == 2)
    assert (".latest|ref" in record_lines(section.body)["A"].group(0)) is (count == 1)


def test_empty_and_unscorable_are_different_statements() -> None:
    """R14: "no quote extracted" and "quotes exist but none can be scored" are different facts."""
    empty = built((), targets(), "FY26_Q2")
    text = " ".join(empty.body.lower().split())
    assert D9 in text and "{{e:" in empty.body and D8 not in text and not empty.claims
    assert "retired entries:" in text and _read(empty).statements == ()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim("margin", quote="margin of 10% a year", page=2)
    mapping = targets(entry("A", a, "AMBIGUOUS"), entry("B", b, "MULTI_YEAR"))
    text = " ".join(built((a, b), mapping, "FY26_Q2").body.lower().split())
    assert D8 in text and D9 not in text
    tail = text[text.index(D8) :]
    assert all(
        r in tail for r in ("window not established", "window not single-year", "no filed measure")
    )


def test_a_record_that_does_not_parse_completely_refuses() -> None:
    """R8: the sealed record is the only memory of every pin, so a lenient parser could lose one."""
    a, b, held = two("10", "12")
    section = chain(a, b, held)
    assert _read(section).pins
    for name, tampered in _tampered(section.body).items():
        assert tampered != section.body, name
        with pytest.raises(RunDraftError):
            cred_module().read_record(tampered, section.claims)


def test_a_record_round_trips_and_a_legacy_head_is_empty() -> None:
    """R8: a build reads back whole, pins of every corrected ancestor included."""
    cred = cred_module()
    assert cred.read_record(None, ()) == cred.Record()
    a = claim(quote="growth of 10% in FY26 or FY27 or FY28")
    first = entry("A", a, window_text="FY26")
    second = entry("B", a, "FY27", supersedes="A", window_text="FY27")
    third = entry("C", a, "FY28", supersedes="B", window_text="FY28")
    one = built((a,), targets(first), "FY26_Q1")
    two_ = built((), targets(first, second), "FY26_Q2", one)
    mapping = targets(first, second, third)
    record = _read(built((), mapping, "FY26_Q3", two_))
    assert record.pins == {name: mapping.entries[name].digest for name in ("A", "B", "C")}
    assert set(record.retired) == {"A", "B"}
    (held,) = record.statements
    assert held.entry_id == "C" and held.digest == mapping.entries["C"].digest
    assert (held.stated, held.stated_end) == ("FY26_Q1", ENDS["FY26_Q1"])
    roles = {f"episode.{GROWTH}.FY28.{role}" for role in ("original", "latest")}
    assert {copy.claim_key for copy in held.claims} == roles
    assert all(same_statement(copy, a) for copy in held.claims)
