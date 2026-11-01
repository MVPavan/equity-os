"""RESEARCH-3 S2 Tasks 1-2: rule H, revision events, outcomes and the section text (pure).

A row tells a reader what management promised and what the filed figures show, so a verdict is a
function of cited claims and a reviewed mapping: a window comes only from the quote's words, an
event from two statements' numbers, an outcome from the exact value at the statement's precision,
and pins stop a config edit rewriting history. New production names are imported inside helpers,
so this file collects before they exist.

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
    ACTUAL,
    ASSESSED,
    BLOB,
    D8,
    D9,
    DISCLOSURES,
    ENDS,
    FY26,
    FY27,
    GROWTH,
    GUIDANCE,
    INTERIM,
    OPEN_ENDED,
    Q4_FILED,
    REVISIONS,
    ROW_ACTUALS,
    SAMPLE,
    SAMPLE_DIGEST,
    SECTION,
    SPLIT,
    TAMPER,
    TOLERANCE,
    TRUNCATIONS,
    VERDICTS,
    WINDOW_CASES,
    WINDOW_STATES,
    WRONG_WAY,
    A,
    B,
    _temp_root,
    built,
    by_key,
    claim,
    correction,
    cred_module,
    direction,
    entry,
    event_of,
    every_status,
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
    stated,
    targets,
    two,
    unresolved,
)

from fundamentals.extract.guidance_extractor import GuidanceRule, extract_guidance_claims
from fundamentals.ingest.pdf_source import LoadedPdf, PdfBlock, PdfPage
from fundamentals.ledger.display import PLACEHOLDER, render_section
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.ledger.run_draft import _Body
from fundamentals.ledger.run_traces import RunDraftError

__all__ = ["_temp_root"]


@pytest.mark.parametrize(("text", "filed_at", "stated_end", "window"), WINDOW_CASES)
def test_a_window_follows_only_from_the_quotes_words(
    text: str, filed_at: datetime | None, stated_end: date, window: str
) -> None:
    """A3, A6, P3: the wrong year is a false verdict. Year-on-year names a basis, a recurring rate
    names no one year, and a relative year holds only if filed inside the year it was stated for."""
    assert gt_module().derive_window(text, filed_at, stated_end, 3) == window


@pytest.mark.parametrize("fault", list(faults()))
def test_a_structurally_wrong_entry_refuses_at_load(fault: str) -> None:
    """A mapping decides what a quote is judged against. An ambiguous or cyclic one has no single
    meaning, and a link must join like with like after successors resolve."""
    with pytest.raises(RunDraftError):
        targets(*faults()[fault])


def test_a_missing_file_is_empty_and_a_chain_resolves_to_its_live_entry(tmp_path: Path) -> None:
    """No file means rows read "window not mapped", not a refusal; a cycle-free chain reaches the
    live successor, so ``same_as`` on a corrected entry follows the correction."""
    empty = gt_module().load_targets("NONE", tmp_path)
    assert dict(empty.entries) == {} and empty.live(A.claim_key, BLOB, "p1.b1.0:1") is None
    held = targets(entry("A", A), entry("B", B, same_as="A"), entry("A2", A, supersedes="A"))
    assert held.live(A.claim_key, BLOB, A.citation.anchor).id == "A2"
    assert held.successor("A").id == "A2" and held.successor("A2") is None
    chain = held.chain(held.entries["B"])
    assert chain[0].id == "B" and chain[-1].id == "A2" == held.root(held.entries["B"]).id


def test_the_entry_digest_pins_exactly_its_preimage() -> None:
    """R8: every sealed pin rests on this preimage. Dropping a field, escaping the quote or
    reordering keys would break history; a field outside it could move a judgment unpinned."""
    gt = gt_module()
    held = gt.TargetEntry(**{**SAMPLE, "reading": gt.Reading.COMMITMENT})
    assert held.digest == SAMPLE_DIGEST
    for field in SAMPLE:
        value = gt.Reading.DESCRIPTIVE if field == "reading" else "changed"
        assert held.model_copy(update={field: value}).digest != SAMPLE_DIGEST, field


def test_a_pinned_entry_cannot_change_or_vanish() -> None:
    """A10, A13: an edit or deletion of a used entry refuses, naming it, or a config edit could
    rewrite sealed history; a superseded entry stays in the file and still verifies."""
    gt = gt_module()
    held = targets(entry("A", A))
    pins = {"A": held.entries["A"].digest}
    gt.check_pins(held, pins)
    with pytest.raises(RunDraftError, match="A"):
        gt.check_pins(targets(entry("A", A, definition="edited")), pins)
    with pytest.raises(RunDraftError, match="A"):
        gt.check_pins(targets(), pins)
    gt.check_pins(targets(entry("A", A), entry("A2", A, supersedes="A")), pins)


@pytest.mark.parametrize(("before", "after", "better", "kind", "reason"), REVISIONS)
def test_a_revision_compares_points_and_midpoints(
    before: tuple[str, ...],
    after: tuple[str, ...],
    better: str | None,
    kind: str,
    reason: str | None,
) -> None:
    """A1: the event states how the promised number moved. A same midpoint with a different range
    is a real change with no direction, and direction ignores whether the move is good."""
    event = cred_module().revision(stated(*before), stated(*after), direction(better))
    assert (event.kind.value, event.reason) == (kind, reason)


@pytest.mark.parametrize(
    "changed",
    [{"constant": True}, {"unit": "INR per MT"}, {"definition": "excluding exports"}],
    ids=["constant-currency", "unit", "definition"],
)
def test_a_revision_on_another_basis_has_no_direction(changed: dict[str, Any]) -> None:
    """A9: twelve on one basis is not "up" from ten on another."""
    event = cred_module().revision(stated("10"), stated("12", **changed), None)
    assert (event.kind.value, event.reason) == ("REVISED", "basis changed")


@pytest.mark.parametrize(("before", "after", "better", "kind", "reason"), OPEN_ENDED)
def test_an_open_ended_promise_compares_on_the_binding_bound(
    before: tuple[str, str | None, bool],
    after: tuple[str, str | None, bool],
    better: str | None,
    kind: str,
    reason: str | None,
) -> None:
    """A1, P5: midpoints would call 18-22 → 20-plus "reaffirmed" when the floor rose. Both sides
    read the binding bound; a range needs a direction, and a floor on a lower-better metric binds
    nothing."""
    first, second = (stated(low, high, plus=plus) for low, high, plus in (before, after))
    event = cred_module().revision(first, second, direction(better))
    assert (event.kind.value, event.reason) == (kind, reason)


# Task 2 (b): the comparison and the unrounded actual ---------------------------------------------


@pytest.mark.parametrize(("exact", "bound", "better", "met"), VERDICTS)
def test_a_verdict_rounds_the_exact_value_half_even_once(
    exact: str, bound: tuple[str, ...], better: str, met: bool
) -> None:
    """OD-7, P4: the tolerance is the statement's own precision. Rounding the stored figure would
    turn 9.495 into 9.50 into ten, a miss into a hit."""
    assert cred_module().compare(stated(*bound), Fraction(exact), direction(better)) is met


@pytest.mark.parametrize(("value", "digits"), TRUNCATIONS)
def test_truncation_cuts_toward_zero_at_exact_places(value: Fraction, digits: str) -> None:
    """P4: a shown digit is never altered by rounding, on either side of zero."""
    from fundamentals.canon.interval import truncate_value

    shown = truncate_value(value, 6)
    assert str(shown) == digits and shown.as_tuple().exponent == -6


@pytest.mark.parametrize(
    ("exact", "bound", "digits", "whole", "outcome"),
    ROW_ACTUALS,
    ids=["binding-at-places", "non-terminating", "negative", "true-tie", "just-above-a-tie"],
)
def test_a_row_shows_the_actual_before_the_statements_rounding(
    exact: Fraction, bound: str, digits: str, whole: bool, outcome: str
) -> None:
    """A2, OD-7: the reader sees the figure before rounding and the rule that decided it. 10.5 and
    10.5000001 print alike yet earn different verdicts, so the phrase must say if digits follow."""
    cred = cred_module()
    held = claim(low=bound, quote=f"growth of {bound}% in FY26")
    actual, values = measured("FY26", exact)
    section = built(
        (held,),
        targets(entry("A", held)),
        "FY26_Q4",
        None,
        actual,
        exact=values,
        measures=registry(),
    )
    line = row(section.body, FY26)
    assert outcomes(line) == [outcome]
    assert digits in render_section(line, (*section.claims, actual))
    assert (cred.ACTUAL_WHOLE if whole else cred.ACTUAL_CUT) in line
    assert (cred.ACTUAL_CUT if whole else cred.ACTUAL_WHOLE) not in line
    assert f"{{{{c:{actual.claim_key}|ref}}}}" in line and all(p in line for p in TOLERANCE)
    assert "{{e:computed}}" in line and "{{e:observed}}" in line
    assert cred.ACTUAL_WHOLE == "(all computed digits)"
    assert cred.ACTUAL_CUT == "(first six decimal places, cut and not rounded; more digits follow)"


def test_one_actual_is_judged_against_both_statements() -> None:
    """A2: management can lower the bar and clear it. Both endpoints side by side keep the miss
    against the original promise beside the hit against the latest."""
    a, b, held = two("12", "10")
    actual, values = measured("FY26", Fraction("10.5"))
    first = built((a,), held, "FY26_Q2")
    section = built((b,), held, "FY26_Q4", first, actual, exact=values, measures=registry())
    line = row(section.body, FY26)
    assert outcomes(line) == ["MISSED", "ACHIEVED"]
    assert event_of(section.body, "B") == ("REVISED_DOWN", None)
    assert f"{{{{c:episode.{FY26}.original|" in line and f"{{{{c:episode.{FY26}.latest|" in line


@pytest.mark.parametrize(("state", "exact", "ytd", "plus", "better", "want"), ASSESSED)
def test_assess_reads_the_state_and_the_binding_bound(
    state: str, exact: Fraction | None, ytd: Fraction | None, plus: bool, better: str, want: str
) -> None:
    """R10: a floor on a lower-better metric is no ceiling, ended or interim. ``ON_TRACK`` and
    ``BEHIND`` exist only for an open window, ``ACHIEVED`` and ``MISSED`` for an ended one."""
    cred = cred_module()
    measure = registry(better=better)[("revenue_growth", "consolidated")]
    window = cred.WindowState[state]
    outcome, reason = cred.assess(
        stated("10", plus=plus), "FY26", measure, window, exact, ytd, None
    )
    assert outcome.value == want
    assert (reason is not None) is (want == "UNRESOLVED")
    if plus:
        assert reason == WRONG_WAY


# Task 2 (c)-(i): windows, episodes and basis -----------------------------------------------------


@pytest.mark.parametrize(
    ("quote", "window", "over", "reason"),
    [
        (
            "tracking on a 20%-plus CAGR",
            "MULTI_YEAR",
            {"window_text": "CAGR"},
            "window not single-year",
        ),
        ("growth of 10% or so", "AMBIGUOUS", {}, "window not established"),
    ],
    ids=["cagr-under-annual", "no-year"],
)
def test_an_unestablished_window_is_never_scored(
    quote: str, window: str, over: dict[str, str], reason: str
) -> None:
    """A3, A4: a CAGR or undated quote has no single year to judge, even with a filed measure, and
    each is its own episode so no date is invented."""
    held = claim(quote=quote)
    mapping = targets(entry("A", held, window, **over))
    section = built((held,), mapping, "FY26_Q4", measures=registry())
    line = row(section.body, f"{GROWTH}.{window}.A")
    unresolved(line, reason)
    assert "no filed measure" not in line


def test_every_reason_that_holds_is_named() -> None:
    """P6: naming only the window would hide that no filed measure exists either, so the reader
    would expect a verdict once a dated quote arrives."""
    held = claim(quote="growth of 10% or so")
    section = built((held,), targets(entry("A", held, "AMBIGUOUS")), "FY26_Q4")
    unresolved(
        row(section.body, f"{GROWTH}.AMBIGUOUS.A"), "window not established", "no filed measure"
    )


def test_an_anchor_cannot_supply_a_year() -> None:
    """A4, OD-9: FY26 on a quote stating no year is hindsight, refused at first use."""
    held = claim(quote="growth of 10% or so")
    with pytest.raises(RunDraftError, match="A"):
        prepared((held,), targets(entry("A", held, "FY26")), "FY26_Q4")


def test_an_unmapped_statement_is_retained_with_its_reason() -> None:
    """A missing entry is a row, not a lost quote: it keeps a record line under an ``UNMAPPED``
    episode, so a later mapping still sees it."""
    section = built((claim(),), targets(), "FY26_Q2")
    assert all(key.startswith(f"episode.{GROWTH}.UNMAPPED.") for key in by_key(section))
    assert len(by_key(section)) == 2
    unresolved(row(section.body, f"{GROWTH}.UNMAPPED"), "window not mapped")
    assert record_lines(section.body)[None]["stated"] == "FY26_Q2"


def test_fiscal_years_are_separate_episodes_from_one_transcript() -> None:
    """A5 (extraction and episode level only, C-8): one call stating two years' targets judges each
    against its own year, and a duplicate horizon cannot be silently merged."""
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
    section = built(held, mapping, "FY26_Q2")
    assert {f"episode.{FY26}.original", f"episode.{FY27}.original"} <= by_key(section).keys()
    body = _Body()
    body.add(GUIDANCE, "- first", held[0])
    with pytest.raises(RunDraftError, match="duplicate claim key"):
        body.add(GUIDANCE, "- again", held[0])


def test_scopes_are_separate_episodes_and_neither_moves_the_other() -> None:
    """A7: a standalone promise is not met by a consolidated actual, and a restated standalone
    target leaves the consolidated endpoints alone."""
    con = claim(page=1)
    alone = claim(low="20", scope="standalone", page=2, quote="growth of 20% in FY26")
    later = claim(low="22", scope="standalone", page=3, quote="growth of 22% in FY26")
    mapping = targets(entry("C", con), entry("S", alone), entry("T", later))
    one, exact_one = measured("FY26", Fraction(11))
    other, exact_other = measured("FY26", Fraction(21), scope="standalone")
    measures = registry("consolidated", "standalone")
    first = built((con, alone), mapping, "FY26_Q2")
    second = built(
        (later,),
        mapping,
        "FY26_Q4",
        first,
        one,
        other,
        exact=exact_one | exact_other,
        measures=measures,
    )
    held, standalone = by_key(second), "revenue_growth.standalone.FY26"
    assert same_statement(held[f"episode.{FY26}.original"], con)
    assert same_statement(held[f"episode.{FY26}.latest"], con)
    assert same_statement(held[f"episode.{standalone}.original"], alone)
    assert same_statement(held[f"episode.{standalone}.latest"], later)
    assert outcomes(row(second.body, FY26)) == ["ACHIEVED"]
    assert outcomes(row(second.body, standalone)) == ["ACHIEVED", "MISSED"]


def test_multi_year_promises_stay_apart_unless_linked() -> None:
    """A8: two "a year" quotes may be different promises, so only a reviewed link joins them and
    gives an event; neither ever gets an outcome (OD-5)."""
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


def test_a_basis_change_leaves_only_the_comparable_endpoint_scored() -> None:
    """A9: a constant-currency promise cannot be judged on a reported figure. The latest is scored,
    the original states why it is not, and the event carries no direction."""
    a = claim(constant=True, page=1)
    b = claim(low="12", page=2, quote="growth of 12% in FY26")
    mapping = targets(entry("A", a), entry("B", b))
    actual, values = measured("FY26", Fraction(13))
    first = built((a,), mapping, "FY26_Q2")
    section = built((b,), mapping, "FY26_Q4", first, actual, exact=values, measures=registry())
    assert event_of(section.body, "B") == ("REVISED", "basis changed")
    line = row(section.body, FY26)
    assert outcomes(line) == ["UNRESOLVED", "ACHIEVED"]
    assert "promise basis differs from the filed measure" in line and "constant" in line


def test_a_correction_moves_the_quote_and_discloses_it_once() -> None:
    """A11: a wrong mapping is corrected in the open. Both interpretations show, the old episode
    says so once and is dropped, the quote moves to its new one, the old pin still verifies."""
    gt, cred, a = gt_module(), cred_module(), claim(quote=SPLIT)
    old = entry("A", a, window_text="in FY26")
    first = built((a,), targets(old), "FY26_Q2")
    fixed = targets(old, entry("A2", a, "MULTI_YEAR", supersedes="A", window_text="FY26 and FY27"))
    gt.check_pins(fixed, cred.read_record(first.body, first.claims).pins)
    second = built((), fixed, "FY26_Q3", first, measures=registry())
    digests = (fixed.entries["A"].digest, fixed.entries["A2"].digest)
    correction(second.body, "A2", *digests, "FY26", "MULTI_YEAR", "revenue_growth")
    gone = row(second.body, FY26)
    unresolved(gone, "mapping corrected", "A2")
    assert same_statement(by_key(second)[f"episode.{GROWTH}.MULTI_YEAR.A2.original"], a)
    assert not [key for key in by_key(second) if f".{FY26}." in key]
    record = cred.read_record(second.body, second.claims)
    assert record.retired == {"A": digests[0]} and record.pins["A2"] == digests[1]
    third = built((), fixed, "FY26_Q4", second, measures=registry())
    assert "mapping corrected" not in third.body
    assert re.search(rf"^- retired A sha256 {digests[0]} successor A2$", third.body, re.M)


def test_a_rerun_restates_the_correction_of_the_version_it_replaces() -> None:
    """P9: pins also come from the same-period head, so a correction seen only there is disclosed,
    not lost because no previous-quarter head names it."""
    a = claim(quote=SPLIT)
    old = entry("A", a, window_text="in FY26")
    first = built((a,), targets(old), "FY26_Q2")
    fixed = targets(old, entry("A2", a, "MULTI_YEAR", supersedes="A", window_text="FY26 and FY27"))
    rerun = built((a,), fixed, "FY26_Q2", same=first)
    correction(rerun.body, "A2", fixed.entries["A"].digest, fixed.entries["A2"].digest)
    assert "mapping corrected" in row(rerun.body, FY26)


def test_correcting_a_middle_statement_recomputes_its_neighbours() -> None:
    """R2: events are rebuilt, never read back. Moving the middle statement makes the third follow
    the first, so its event flips, while the moved quote keeps its whole contract."""
    a = claim(page=1)
    b = claim(low="12", quote="growth of 12% in FY26 or FY27", page=2)
    c = claim(low="11", quote="growth of 11% in FY26", page=3)
    entries = (entry("A", a), entry("B", b, window_text="FY26"), entry("C", c))
    held = targets(*entries)
    three = built((c,), held, "FY26_Q3", built((b,), held, "FY26_Q2", built((a,), held, "FY26_Q1")))
    assert event_of(three.body, "B") == ("REVISED_UP", None)
    assert event_of(three.body, "C") == ("REVISED_DOWN", None)
    roles = {f"episode.{FY26}.{role}" for role in ("original", "stated.B", "latest")}
    assert roles <= by_key(three).keys()
    fixed = targets(*entries, entry("B2", b, "FY27", supersedes="B", window_text="FY27"))
    four = built((), fixed, "FY26_Q4", three)
    assert event_of(four.body, "C") == ("REVISED_UP", None)
    assert record_lines(four.body)["B2"]["stated"] == "FY26_Q2"
    assert same_statement(by_key(four)[f"episode.{FY27}.original"], b)
    assert f"episode.{FY26}.stated.B" not in by_key(four)
    correction(four.body, "B2", fixed.entries["B"].digest, fixed.entries["B2"].digest)


def test_a_definition_correction_turns_a_directional_event_into_a_basis_change() -> None:
    """R2: if the second quote promised another measure, "up" was never true. The new version says
    so and discloses why the event moved."""
    a, b, held = two("10", "12")
    entries = (entry("A", a), entry("B", b))
    second = built((b,), held, "FY26_Q2", built((a,), held, "FY26_Q1"))
    assert event_of(second.body, "B") == ("REVISED_UP", None)
    fixed = targets(*entries, entry("B2", b, supersedes="B", definition="excluding exports"))
    third = built((), fixed, "FY26_Q3", second)
    assert event_of(third.body, "B2") == ("REVISED", "basis changed")
    correction(third.body, "B2", "excluding exports", fixed.entries["B2"].digest)


def test_a_late_mapping_is_judged_at_its_statements_own_period() -> None:
    """R4, C-7: "this year" in a post-year-end Q4 call stays ambiguous for good. Mapping it later
    must not let the later run's period make it FY27, and declaring FY27 refuses."""
    held = claim(quote="growth of 10% this year")
    filed = {BLOB: Q4_FILED}
    first = built((held,), targets(), "FY26_Q4", filed_at=filed)
    second = built((), targets(entry("A", held, "AMBIGUOUS")), "FY27_Q1", first, filed_at=filed)
    line = record_lines(second.body)["A"]
    assert (line["stated"], line["ended"]) == ("FY26_Q4", "2026-03-31")
    assert f"episode.{GROWTH}.AMBIGUOUS.A.original" in by_key(second)
    with pytest.raises(RunDraftError, match="A"):
        prepared((), targets(entry("A", held, "FY27")), "FY27_Q1", first, filed_at=filed)


@pytest.mark.parametrize("target", ["unedited", "edited", "superseded"])
def test_a_link_must_resolve_through_a_recorded_statement(target: str) -> None:
    """P13: a root decides a recorded episode, so it must be a recorded, pinned statement, or an
    unpinned entry could rename history. A link outside the pool refuses whatever its target did."""
    cred = cred_module()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim(low="12", quote="growth of 12% or so", page=2)
    base = entry(
        "A", a, "AMBIGUOUS", definition="edited" if target == "edited" else "revenue_growth"
    )
    fixes = [entry("A2", a, "AMBIGUOUS", supersedes="A")] if target == "superseded" else []
    mapping = targets(base, *fixes, entry("B", b, "AMBIGUOUS", same_as="A"))
    copy = b.model_copy(update={"claim_key": f"episode.{GROWTH}.AMBIGUOUS.B.original"})
    recorded = cred.Recorded(
        claims=(copy,),
        stated="FY26_Q2",
        stated_end=ENDS["FY26_Q2"],
        entry_id="B",
        digest=mapping.entries["B"].digest,
    )
    with pytest.raises(RunDraftError, match="A"):
        cred.prepare(
            (),
            cred.Record(statements=(recorded,)),
            cred.Record(),
            mapping,
            period="FY26_Q3",
            period_end=ENDS["FY26_Q3"],
            month=3,
            filed_at={},
            actual_blobs=frozenset(),
        )


def test_a_link_inside_the_pool_is_pinned_like_any_statement() -> None:
    """P13's other half: with the target recorded, editing it refuses through its own pin, deleting
    it refuses at load, and superseding it renders the correction."""
    gt, cred = gt_module(), cred_module()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim(low="12", quote="growth of 12% or so", page=2)
    base, linked = entry("A", a, "AMBIGUOUS"), entry("B", b, "AMBIGUOUS", same_as="A")
    section = built((a, b), targets(base, linked), "FY26_Q2")
    pins = cred.read_record(section.body, section.claims).pins
    with pytest.raises(RunDraftError, match="A"):
        gt.check_pins(targets({**base, "definition": "edited"}, linked), pins)
    with pytest.raises(RunDraftError):
        targets(linked)
    fixed = targets(base, linked, entry("A2", a, "AMBIGUOUS", supersedes="A", definition="new"))
    correction(built((), fixed, "FY26_Q3", section).body, "A2", fixed.entries["A"].digest)


def test_a_descriptive_quote_is_evidence_and_never_a_promise() -> None:
    """P14: a rule match cannot tell a promise from a description of progress. A descriptive quote
    keeps its record but earns no verdict, event or due window, whatever window it declares."""
    cred = cred_module()
    held = claim(page=1)
    other = claim(low="12", page=2, quote="growth of 12% in FY26")
    mapping = targets(entry("D", held, reading="DESCRIPTIVE"), entry("C", other))
    prep = prepared((held,), mapping, "FY26_Q4")
    assert ("revenue_growth", "consolidated", "FY26") not in prep.windows
    first = finish(prep, measures=registry())
    episode = f"{GROWTH}.DESCRIPTIVE.D"
    assert event_of(first.body, "D") == ("DESCRIBED", None)
    line = row(first.body, episode)
    unresolved(line, cred.REASON_DESCRIPTIVE)
    assert "no filed measure" not in line and "window not" not in line
    second = built((other,), mapping, "FY27_Q1", first, measures=registry())
    assert event_of(second.body, "C") == ("OPENED", None)  # no event against the description
    assert f"episode.{episode}.original" in by_key(second)


def test_correcting_a_commitment_to_descriptive_shows_both_readings() -> None:
    """P14 through the correction path: the reader sees that a quote once tracked as a promise no
    longer is, and why it left its episode."""
    a = claim(page=1)
    old = entry("A", a)
    first = built((a,), targets(old), "FY26_Q2")
    fixed = targets(old, entry("A2", a, reading="DESCRIPTIVE", supersedes="A"))
    second = built((), fixed, "FY26_Q3", first, measures=registry())
    correction(second.body, "A2", "COMMITMENT", "DESCRIPTIVE")
    assert f"episode.{GROWTH}.DESCRIPTIVE.A2.original" in by_key(second)
    assert "mapping corrected" in row(second.body, FY26)


@pytest.mark.parametrize(
    "over",
    [{"quote": "growth of 10% in FY26, restated"}, {"window": "FY27"}],
    ids=["another-quote", "window-failing-first-use"],
)
def test_prepare_refuses_a_new_entry_that_disagrees_with_its_statement(
    over: dict[str, Any],
) -> None:
    """F1: window_text ⊂ entry quote = claim quote = retained span is what makes a window's
    evidence real. A broken link refuses in ``prepare``, before the run's first write."""
    held = claim()
    with pytest.raises(RunDraftError, match="A"):
        prepared((held,), targets(entry("A", held, **over)), "FY26_Q2")


def test_prepare_refuses_to_lose_a_pin() -> None:
    """F1: a pin this build would not carry could later be edited unnoticed, so a build whose pins
    are not a superset of the replaced head's refuses rather than writes."""
    held = claim()
    mapping = targets(entry("A", held))
    with pytest.raises(RunDraftError, match="A"):
        prepared((), mapping, "FY26_Q2", same=built((held,), mapping, "FY26_Q2"))


# Task 2 (k)-(m2): interim, carry, missing actuals, future targets --------------------------------


def test_interim_is_side_by_side_and_labelled() -> None:
    """A12, OD-6: after a downward revision one year-to-date value is behind the original and on
    track for the latest. Both are inferences on an assumed pace, so the label is mandatory."""
    a, b, held = two("12", "8")
    ytd, values = measured("FY26", Fraction(10), ytd=True)
    first = built((a,), held, "FY26_Q1")
    section = built((b,), held, "FY26_Q2", first, ytd, exact=values, measures=registry())
    line = row(section.body, FY26)
    assert outcomes(line) == ["BEHIND", "ON_TRACK"]
    assert event_of(section.body, "B") == ("REVISED_DOWN", None)
    assert (
        INTERIM in line and "{{e:inferred}}" in line and cred_module().INTERIM_RULE_LABEL == INTERIM
    )
    assert ytd.claim_key == "cred.revenue_growth.consolidated.FY26.ytd"


@pytest.mark.parametrize("interim", [True, False], ids=["missing-comparator", "no-interim-rule"])
def test_an_open_window_without_an_interim_value_stays_unresolved(interim: bool) -> None:
    """A12: a missing comparator window, or no interim rule, must not read as behind."""
    held = claim()
    section = built(
        (held,), targets(entry("A", held)), "FY26_Q2", measures=registry(interim=interim)
    )
    line = row(section.body, FY26)
    unresolved(line, *(() if interim else ("no interim rule",)))
    assert INTERIM not in line


def test_both_endpoints_carry_and_the_original_never_moves() -> None:
    """A13: the first promise is the yardstick, so restatements only move ``.latest``, and a carried
    statement keeps its originating period."""
    a, b, held = two("10", "12")
    carried = built((), held, "FY26_Q2", built((a,), held, "FY26_Q1"))
    third = built((), held, "FY26_Q4", built((b,), held, "FY26_Q3", carried))
    assert same_statement(by_key(carried)[f"episode.{FY26}.latest"], a)
    assert same_statement(by_key(third)[f"episode.{FY26}.original"], a)
    assert same_statement(by_key(third)[f"episode.{FY26}.latest"], b)
    lines = record_lines(third.body)
    assert (lines["A"]["stated"], lines["A"]["ended"]) == ("FY26_Q1", "2025-06-30")
    assert (lines["B"]["stated"], lines["B"]["ended"]) == ("FY26_Q3", "2025-12-31")


@pytest.mark.parametrize(
    ("reason", "held"),
    [
        ("actual not yet filed", False),
        ("filed value differs across admitted captures", True),
        ("comparator revenue not positive or its uncertainty reaches zero", True),
    ],
    ids=["not-filed", "captures-disagree", "undefined-growth"],
)
def test_an_ended_window_with_no_usable_actual_says_why(reason: str, held: bool) -> None:
    """A14, P11, F5: these causes have different follow-ups; none reads as a miss."""
    stated_claim = claim()
    section = built(
        (stated_claim,),
        targets(entry("A", stated_claim)),
        "FY26_Q4",
        unavailable={ACTUAL: reason} if held else {},
        measures=registry(),
    )
    unresolved(row(section.body, FY26), reason)


@pytest.mark.parametrize("value", [Fraction(50), Fraction(1)], ids=["would-meet", "would-miss"])
def test_a_future_target_is_not_due_whatever_this_year_shows(value: Fraction) -> None:
    """A12, F2: this year's pace says nothing of next year's target, so no interim actual is due and
    the row says why; the target's own first quarter reads its own months."""
    cred = cred_module()
    held = claim(quote="growth of 10% in FY27")
    mapping = targets(entry("A", held, "FY27"))
    early = prepared((held,), mapping, "FY26_Q2")
    assert ("revenue_growth", "consolidated", "FY27") not in early.windows
    ytd, values = measured("FY27", value, ytd=True)
    section = finish(early, exact=values, measures=registry())
    unresolved(row(section.body, FY27), "not due: target year not started")
    assert not [key for key in by_key(section) if key.startswith("cred.")]
    later = prepared((), mapping, "FY27_Q1", section)
    assert later.windows[("revenue_growth", "consolidated", "FY27")] is cred.WindowState.OPEN
    scored = finish(later, ytd, exact=values, measures=registry())
    assert outcomes(row(scored.body, FY27)) == ["ON_TRACK" if value > 10 else "BEHIND"]


@pytest.mark.parametrize(("label", "end", "state"), WINDOW_STATES)
def test_a_targets_window_state_turns_on_its_own_boundaries(
    label: str, end: date, state: str
) -> None:
    """F2: an off-by-one here would score a whole year early or never close it."""
    cred = cred_module()
    assert cred.window_state(label, end, 3) is cred.WindowState[state]


def test_nothing_reaches_prose_but_through_a_claim_and_every_row_is_labelled() -> None:
    """Spec §1 rules 1, 5: a digit outside a placeholder is a number no claim stands behind, and an
    unlabelled row blurs observed, computed and inferred. Rendering proves each one holds."""
    section, actuals = every_status()
    assert scan_section(section.body, resolves=lambda *_: True) == ()
    render_section(section.body, (*section.claims, *actuals))
    assert {"ACHIEVED", "MISSED", "ON_TRACK", "BEHIND", "UNRESOLVED"} <= set(outcomes(section.body))
    assert section.body.startswith(f"## {SECTION}\n")
    for line in section.body.splitlines():
        if line.startswith("- ") and PLACEHOLDER.search(line):
            assert "{{e:" in line, line


@pytest.mark.parametrize("count", [1, 2], ids=["one-statement", "two-statements"])
def test_a_line_references_exactly_the_claims_it_shows(count: int) -> None:
    """F6: a reader resolves every figure from the narrative. A one-statement episode shows
    ``.original`` only; its ``.latest`` is the same statement, referenced by the record line."""
    a, b, held = two("10", "12")
    section = built((a,), held, "FY26_Q1")
    if count == 2:
        section = built((b,), held, "FY26_Q2", section)
    for line in section.body.splitlines():
        found = PLACEHOLDER.findall(line)
        shown = {key for key, style in found if style != "ref"}
        if shown:
            assert {key for key, style in found if style == "ref"} == shown, line
    shows_latest = f"{{{{c:episode.{FY26}.latest|ref}}}}" in row(section.body, FY26)
    assert shows_latest is (count == 2)
    assert (".latest|ref" in record_lines(section.body)["A"].group(0)) is (count == 1)


def test_the_disclosures_state_every_limit() -> None:
    """S1 lesson 2: both S1 rejections were an undisclosed absence or basis, so each limit of this
    record is in the section itself."""
    body = " ".join(every_status()[0].body.lower().split())
    for fragment in DISCLOSURES:
        assert fragment in body, fragment


def test_empty_and_unscorable_are_different_statements() -> None:
    """R14: "no quote extracted" and "quotes exist but none can be scored" are different facts. An
    all-unresolved section renders its rows and each distinct reason; an empty one has none."""
    cred = cred_module()
    empty = built((), targets(), "FY26_Q2")
    text = " ".join(empty.body.lower().split())
    assert D9 in text and "{{e:" in empty.body and D8 not in text and not empty.claims
    assert "retired entries:" in text
    assert cred.read_record(empty.body, empty.claims).statements == ()
    a = claim(quote="growth of 10% or so", page=1)
    b = claim("margin", quote="margin of 10% a year", page=2)
    mapping = targets(entry("A", a, "AMBIGUOUS"), entry("B", b, "MULTI_YEAR"))
    text = " ".join(built((a, b), mapping, "FY26_Q2").body.lower().split())
    assert D8 in text and D9 not in text
    tail = text[text.index(D8) :]
    assert all(
        r in tail for r in ("window not established", "window not single-year", "no filed measure")
    )


@pytest.mark.parametrize("tamper", list(TAMPER))
def test_a_record_that_does_not_parse_completely_refuses(tamper: str) -> None:
    """R8: the sealed record is the only memory of every pin. A lenient parser could drop a
    statement and so its pin, so anything short of a complete parse refuses."""
    cred = cred_module()
    a, b, held = two("10", "12")
    section = built((b,), held, "FY26_Q2", built((a,), held, "FY26_Q1"))
    assert cred.read_record(section.body, section.claims).pins
    tampered = TAMPER[tamper](section.body)
    assert tampered != section.body, "the tamper missed"
    with pytest.raises(RunDraftError):
        cred.read_record(tampered, section.claims)


def test_a_record_round_trips_and_a_legacy_head_is_empty() -> None:
    """R8: the next run rests on what this one sealed, so a build reads back whole, pins of every
    corrected ancestor included; a head from before S2 simply has no record."""
    cred = cred_module()
    assert cred.read_record(None, ()) == cred.Record()
    a = claim(quote="growth of 10% in FY26 or FY27 or FY28")
    first = entry("A", a, window_text="FY26")
    second = entry("B", a, "FY27", supersedes="A", window_text="FY27")
    third = entry("C", a, "FY28", supersedes="B", window_text="FY28")
    one = built((a,), targets(first), "FY26_Q1")
    two_ = built((), targets(first, second), "FY26_Q2", one)
    mapping = targets(first, second, third)
    three = built((), mapping, "FY26_Q3", two_)
    record = cred.read_record(three.body, three.claims)
    assert record.pins == {name: mapping.entries[name].digest for name in ("A", "B", "C")}
    assert set(record.retired) == {"A", "B"}
    (held,) = record.statements
    assert held.entry_id == "C" and held.digest == mapping.entries["C"].digest
    assert (held.stated, held.stated_end) == ("FY26_Q1", ENDS["FY26_Q1"])
    roles = {f"episode.{GROWTH}.FY28.{role}" for role in ("original", "latest")}
    assert {copy.claim_key for copy in held.claims} == roles
    assert all(same_statement(copy, a) for copy in held.claims)
