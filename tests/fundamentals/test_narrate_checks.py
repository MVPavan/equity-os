"""RESEARCH-3 S3 Task 1: the narrative guardrails that need no database.

Why: the model never states a number and code alone states a direction, so each refusal here stops
a draft smuggling either past the panel. Production names import inside tests, so this collects."""

from __future__ import annotations

from fractions import Fraction
from itertools import count
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from credibility_support import built, claim, entry, measured, registry, write_targets
from retained_support import REPO_ROOT

from fundamentals.ledger.credibility import NO_STATEMENT
from fundamentals.ledger.display import DisplayError, render_section
from fundamentals.ledger.numeral_scan import scan_section
from fundamentals.thesis.claude_client import ClaudeOpusClient

# U1-U6, literal: a sealed test takes nothing from an unsealed plan. One row per line, as its table.
# fmt: off
UPDATES = (
    ("open_questions", "(this pipeline drafts no analyst questions, so the list does not show that no others exist)", "(the model's questions are in `analyst_questions`, and this code-built list does not show that no others exist)"),  # noqa: E501
    ("thesis_impact", "The narrative impact is not drafted by this pipeline.", "The narrative impact is drafted by a model in `thesis_narrative`, as a labelled opinion."),  # noqa: E501
    ("management_credibility", "No overall credibility judgment, trend or thesis consequence is computed or drafted.", "This section computes no overall credibility judgment, trend or thesis consequence; `credibility_notes` holds code-built delivery trend rows and a labelled note on the thesis consequence."),  # noqa: E501
    ("not_performed", "- a judgment of management credibility: `management_credibility` holds only the mapped record, revision events and code-computed outcomes; no model explanation, trend or thesis consequence", "- an overall judgment of management credibility: `credibility_notes` adds code-built delivery trend rows and a labelled note on what the record means for the thesis, and gives no verdict on management"),  # noqa: E501
    ("not_performed", "- an earnings-driver analysis", "- a causal earnings-driver analysis: `drivers` states what the cited claims show, and causes stay NOT_ASSESSED"),  # noqa: E501
    ("not_performed", "- a narrative thesis-impact assessment", "- a thesis successor: `thesis_narrative` is report text and changes no canonical thesis"),  # noqa: E501
)
# fmt: on
# The two exact forms P8 leaves alone: no approved thesis (T1), no extracted guidance (W2).
NO_THESIS_BODY = "## thesis_impact\n\n{{e:computed}} UNRESOLVED: no approved thesis.\n\n"
NO_GUIDANCE_BODY = (
    f"## management_credibility\n\n{{{{e:computed}}}} {NO_STATEMENT}\n\n"
    "{{e:computed}} Retired entries:\n- none\n\n"
)
# Task 0's final proven invocation, spelled out (``isolation/r7/argv.txt``).
PROVEN_ARGV = [
    "claude", "-p", "PROMPT", "--output-format", "text", "--model", "claude-opus-5-5",
    "--tools", "", "--setting-sources", "", "--settings", '{"autoMemoryEnabled":false}',
    "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
    "--system-prompt", "You write report text from the data in the user's message.",
]  # fmt: skip
KEYS = ("drivers", "risk_notes", "credibility_notes", "thesis_narrative", "analyst_questions")
LABEL = "{{e:inferred}} "
GROWTH = "episode.revenue_growth.consolidated"
RISING = (("FY25", ("10",), 9), ("FY26", ("10",), 11))
Window = tuple[str, tuple[str, ...], int | None]


def _checks() -> ModuleType:
    from fundamentals.ledger import narrate_checks

    return narrate_checks


def _flow() -> ModuleType:
    from fundamentals.ledger import narrate

    return narrate


def _scan(text: str) -> tuple[str, ...]:
    from fundamentals.ledger.numeral_scan import scan_narrative

    return tuple(scan_narrative(text))


def _record(root: Path, period: str, *windows: Window) -> str:
    """A real record: each window's first statement in FY26_Q1's run, any later one and each
    filed actual (year-to-date while the window is open) in ``period``'s."""
    page = count(1)
    first, later, entries, actuals = [], [], [], []
    for window, lows, actual in windows:
        held = [
            claim(low=low, quote=f"growth of {low}% in {window}", page=next(page)) for low in lows
        ]
        entries += [entry(f"{window}-{chr(97 + at)}", item, window) for at, item in enumerate(held)]
        first.append(held[0])
        later += held[1:]
        if actual is not None:
            ytd = window == "FY26" and period != "FY26_Q4"
            actuals.append(measured(window, Fraction(actual), ytd=ytd))
    mapping = write_targets(root, *entries)
    prior = built(tuple(first), mapping, "FY26_Q1")
    made = built(tuple(later), mapping, period, prior, actuals=tuple(actuals), measures=registry())
    return str(made.body)


def _directions(body: str) -> set[str]:
    """The trends a record's rows state, ``NOT_ASSESSABLE`` aside."""
    return {row.trend.value for row in _checks().trend_rows(body)} - {"NOT_ASSESSABLE"}


def test_the_scan_refuses_what_smuggles_a_number_and_allows_the_rest() -> None:
    """Spec §4: digits outside dates and period labels, number words and decorated placeholders
    block, each naming what it found. Over-refusing costs a model call, so the exemptions and
    whole-word matching hold too."""
    for word in ("forty", "FORTY", "doubled", "percent", "bps"):
        assert any(word in reason for reason in _scan(f"{LABEL}it was {word}")), word
    refused = {
        "no one said so": "one",
        "a many-fold rise": "-fold",
        "amount:123": "123",
        "\n1. a numbered item": "1",
        "a footnote[^1]": "1",
        "sha256 abc123def456": "abc123def456",
        "row R6 is flagged": "R6",
        "PBT / revenue × 100": "100",
        "{{c:fact.revenue}} raw": "{{",
    }
    refused |= dict.fromkeys(
        ("-{{c:k|}} a", "{{c:k|}}x a", "amount:{{c:k|}} a", "{{c:k|}}% a"), "{{c:k|}}"
    )
    for text, token in refused.items():
        assert any(token in reason for reason in _scan(LABEL + text)), text
    for text in ("on 2026-03-31", "in FY26_Q2", "in Q3", "({{c:k|}})", "{{c:k|unit}}, so", "tone"):
        assert _scan(LABEL + text) == (), text


def test_a_style_digit_is_refused_by_the_real_render() -> None:
    """A style field is outside the scan: ``render_section`` is what refuses its digit."""
    held = claim()
    text = f"{LABEL}{{{{c:{held.claim_key}|x2}}}}."
    assert _scan(text) == ()
    with pytest.raises(DisplayError, match="x2"):
        render_section(text, (held,))


def test_parse_takes_only_the_five_keys_each_with_content() -> None:
    """P2: nothing else can enter a version. AX-5's reference-only note stays the panel's."""

    def answer(**over: str | None) -> str:
        bodies = dict.fromkeys(KEYS, LABEL + "A note.") | over
        return "".join(
            f"## {key}\n\n{text}\n\n" for key, text in bodies.items() if text is not None
        )

    for text, named in (
        (answer(drivers=None), "drivers"),
        (answer() + "## drivers\n\nAgain.\n\n", "drivers"),
        (answer(conclusions=LABEL + "Extra."), "conclusions"),
        (answer(risk_probe=LABEL + "Edited."), "risk_probe"),
        (answer(risk_notes="  \n"), "risk_notes"),
        (answer(risk_notes="{{e:inferred}} {{e:opinion}}"), "risk_notes"),
        (answer(risk_notes="{{e:inferred}} {{s:7|p1.b0.0:5}}"), "risk_notes"),
    ):
        with pytest.raises(ValueError, match=named):
            _checks().parse_draft(text)
    parsed = _checks().parse_draft(answer(risk_notes="{{e:inferred}} {{c:probe.R6|ref}}"))
    assert tuple(parsed) == KEYS and "{{c:probe.R6|ref}}" in parsed["risk_notes"]


@pytest.mark.parametrize(
    ("period", "windows", "direction"),
    [
        ("FY26_Q4", RISING, "RISING"),
        ("FY26_Q4", (("FY25", ("10",), 11), ("FY26", ("10",), 9)), "FALLING"),
        ("FY26_Q4", (("FY25", ("10",), 11), ("FY26", ("10",), 11)), "STEADY"),
        ("FY26_Q4", (("FY25", ("10", "10"), 9), ("FY26", ("12", "8"), 9)), "DIVERGED"),
        ("FY26_Q4", (("FY25", ("10", "10"), 11), ("FY26", ("8", "12"), 9)), "DIVERGED"),
        ("FY26_Q4", (("FY25", ("10", "10"), 9), ("FY26", ("5", "8"), 9)), "RISING"),
        ("FY26_Q2", (("FY25", ("10",), 11), ("FY26", ("10",), 11)), None),
        ("FY26_Q2", (("FY25", ("10",), 11), ("FY26", ("10",), 1)), None),
        ("FY26_Q4", (("FY24", ("10",), 9), ("FY26", ("10",), 11)), None),
        ("FY26_Q4", (("FY25", ("10",), 9), ("FY26", ("10",), None)), None),
        ("FY26_Q4", (("FY25", ("10",), None), ("FY26", ("10",), None)), None),
    ],
)
def test_a_trend_compares_completed_windows_endpoint_by_endpoint(
    tmp_path: Path, period: str, windows: tuple[Window, ...], direction: str | None
) -> None:
    """P3: a relaxed or raised target whose endpoints disagree is ``DIVERGED``, a revision whose
    endpoints agree can rise, and an interim, lone, gapped or unscored window states nothing."""
    wanted = {direction} if direction else set()
    assert _directions(_record(tmp_path, period, *windows)) == wanted


def test_an_interim_earlier_window_is_not_compared(tmp_path: Path) -> None:
    """The rule is total: an earlier interim outcome (edited, a build never writes it) stays out."""
    body = _record(tmp_path, "FY26_Q4", *RISING)
    assert _directions(body.replace("original MISSED", "original BEHIND", 1)) == set()


def test_a_row_shows_both_endpoints(tmp_path: Path) -> None:
    """The promise's move stays visible beside the trend that declines to state a direction."""
    body = _record(tmp_path, "FY26_Q4", ("FY25", ("10", "10"), 9), ("FY26", ("12", "8"), 9))
    checks = _checks()
    lines = checks.trend_lines(checks.trend_rows(body))
    assert any(all(word in s for word in ("MISSED", "ACHIEVED", "DIVERGED")) for s in lines)


def test_two_revisions_up_state_no_direction(tmp_path: Path) -> None:
    """Sol's ruling on Apar: a revision says a stated figure moved, never that delivery rose."""
    a, b, c = (claim(low=n, quote=f"guidance of {n} per metric ton", page=int(n)) for n in "579")
    held = (entry("A", a, "AMBIGUOUS"), entry("B", b, "AMBIGUOUS", same_as="A"))
    mapping = write_targets(tmp_path, *held, entry("C", c, "AMBIGUOUS", same_as="B"))
    first = built((b,), mapping, "FY26_Q2", built((a,), mapping, "FY26_Q1"))
    made = built((c,), mapping, "FY26_Q3", first)
    assert made.body.count("REVISED_UP") == 2 and _directions(made.body) == set()


def test_a_verdict_word_refuses_in_credibility_prose_whatever_the_row_says() -> None:
    """T4: directions live only in the code rows, so no scored row unlocks a word. Elsewhere only a
    sentence on credibility, management or guidance is read, so what moved stays sayable."""
    verdict = _checks().verdict_words
    for word in (
        "rising improving better stronger falling deteriorated worse weaker credible reliable "
        "trustworthy achieved delivered on_track beat missed conservative aggressive"
    ).split():
        said = word.replace("_", " ")
        assert verdict("credibility_notes", f"It looks {said} here."), word
        assert verdict("drivers", f"Management guidance looks {said} here."), word
    for text in (
        "The target was achieved {{c:episode.x.latest|ref}}.",
        "Credibility is rising {{c:episode.x.latest|ref}}.",
        "See the delivery trend rows.",
    ):
        assert verdict("credibility_notes", text), text
    assert verdict("credibility_notes", "The filed result fell short of the stated figure.") == ()
    assert verdict("drivers", "Revenue fell against a year earlier.") == ()
    assert verdict("drivers", "Margins improved against a year earlier.") == ()


def _row(check: str, status: str, shown: bool = True) -> str:
    """A probe row's literal shape in the stored body (v20)."""
    value = f": {{{{c:probe.{check}|}}}}" if shown else ""
    cited = check if shown else f"{check}.total_equity"
    head = f"- {{{{e:computed}}}} {check} A label (closing balances at 2025-09-30){value}"
    return f"{head}; {status} {{{{c:probe.{cited}|ref}}}}"


@pytest.mark.parametrize(
    ("status", "shape"),
    [
        ("FLAGGED by T", "trend"),
        ("FLAGGED by L, T", "trend"),
        ("FLAGGED by L", "limit"),
        ("FLAGGED (non-positive equity)", "guard"),
    ],
)
def test_the_r6_note_is_due_and_instructed_by_the_rule_that_fired(status: str, shape: str) -> None:
    """Duty 2: the note is due on a guard row with no ratio, and its instruction must not invent an
    explanation the row's own rules did not establish. Only the T shapes carry Sol's elements."""
    checks = _checks()
    others = (_row("R4", "FLAGGED by S, T"), _row("R1", "COMPUTED"))
    probe = "\n".join((*others, _row("R6", status, shape != "guard")))
    assert checks.notes_due(probe, "")["risk_notes"] == ("probe.R4", "probe.R6")
    said = checks.r6_instruction(probe)
    elements = ("increased borrowings relative to equity", "trend flag", "limit breach")
    assert all(phrase in said for phrase in (*elements, "funding or repayment")) is (
        shape == "trend"
    )
    assert ("does not establish" in said) is (shape == "limit")
    assert ("non-positive equity" in said) is (shape == "guard")
    assert checks.r6_instruction("\n".join(others)) is None


def test_notes_are_due_on_a_revision_a_miss_and_a_behind_row_only(tmp_path: Path) -> None:
    """Spec §4, v23's shape: and ``missing_notes`` reads a placeholder's key, not its style."""
    checks = _checks()
    revised = _record(tmp_path, "FY26_Q4", ("FY26", ("10", "12"), None))
    assert checks.notes_due("", revised)["credibility_notes"] == (f"{GROWTH}.FY26",)
    bad = _record(tmp_path, "FY26_Q2", ("FY25", ("10",), 9), ("FY26", ("10",), 1))
    due_bad = set(checks.notes_due("", bad)["credibility_notes"])
    assert due_bad == {f"{GROWTH}.FY25", f"{GROWTH}.FY26"}
    good = _record(tmp_path, "FY26_Q4", ("FY25", ("10",), 11))
    assert not any(checks.notes_due(_row("R1", "COMPUTED"), good).values())
    due = {"risk_notes": ("probe.R6",)}
    assert checks.missing_notes(due, {"risk_notes": LABEL + "{{c:probe.R4|ref}}"}) == ("probe.R6",)
    assert checks.missing_notes(due, {"risk_notes": LABEL + "{{c:probe.R6|ref}}"}) == ()


def test_code_built_text_passes_both_scans(tmp_path: Path) -> None:
    """Code-built lines face the same scans as the model's, so a disclosure can never refuse N+1."""
    checks = _checks()
    lines = checks.trend_lines(checks.trend_rows(_record(tmp_path, "FY26_Q4", *RISING)))
    for text in (checks.D1, checks.D2, checks.D3, checks.D4, *lines):
        labelled = f"{{{{e:computed}}}} {text}"
        assert _scan(labelled) == () and scan_section(labelled, resolves=lambda *_: True) == ()


def test_the_block_denies_an_assessment_only_when_none_exists(tmp_path: Path) -> None:
    """T2: ``STEADY`` and ``DIVERGED`` are assessments, so D2 would falsely deny them."""
    checks = _checks()
    rows = checks.trend_rows(_record(tmp_path, "FY26_Q4", *RISING))
    for trends, denies in (
        (("NOT_ASSESSABLE", "NOT_ASSESSABLE"), True),
        (("STEADY", "STEADY"), False),
        (("DIVERGED", "DIVERGED"), False),
        (("RISING", "NOT_ASSESSABLE"), False),
    ):
        pairs = zip(rows, trends, strict=True)
        made = [r.model_copy(update={"trend": checks.DeliveryTrend(t)}) for r, t in pairs]
        block = checks.trend_block(tuple(made))
        assert (checks.D2 in block) is denies and checks.D4 in block, trends
        assert all(line in block for line in checks.trend_lines(tuple(made))), trends
    assert "STEADY" in checks.D4 and "DIVERGED" in checks.D4


@pytest.mark.parametrize(
    ("exempt", "other"),
    [
        (NO_THESIS_BODY, NO_THESIS_BODY + "Other words."),
        (NO_GUIDANCE_BODY, NO_GUIDANCE_BODY.replace(NO_STATEMENT, "Other words.")),
        (NO_GUIDANCE_BODY, NO_GUIDANCE_BODY.replace(NO_STATEMENT, NO_STATEMENT * 2)),
    ],
)
def test_only_the_exact_form_is_exempt_from_a_disclosure_update(exempt: str, other: str) -> None:
    """P8, T1, W2: a section missing its ``before`` refuses unless exactly the honest form, which
    stays as it is. ``test_a_bundle_over_the_cap_refuses`` holds that this runs before the model."""
    key = exempt.split()[1]
    bodies: dict[str, str] = {}
    for section, before, _ in UPDATES:
        bodies[section] = f"{bodies.get(section, '')}{before}\n"
    updated = _flow().apply_disclosure_updates(bodies | {key: exempt})
    assert updated[key] == exempt
    assert all(after in updated[s] for s, _, after in UPDATES if s != key)
    with pytest.raises(_flow().NarrateRefusedError, match=key):
        _flow().apply_disclosure_updates(bodies | {key: other})


def test_the_configured_argv_is_the_proven_one(tmp_path: Path) -> None:
    """A17, P7: only the invocation Task 0 proved reaches the model, spelled out byte for byte. The
    API path bypasses the watchdog and an unbounded limit is no limit, so each refuses at load."""
    committed = REPO_ROOT / "config/narrate.yaml"
    config = _flow().load_narrate_config(committed)
    assert ClaudeOpusClient(config.claude).build_command("PROMPT") == PROVEN_ARGV
    bad_limits = ("max_span_chars", "max_total_bytes", "max_prompt_bytes", "max_response_bytes")
    for section, field, value in (
        ("claude", "use_api", True),
        ("claude", "model", None),
        ("claude", "timeout_seconds", 0),
        ("claude", "retries", -1),
        ("limits", "max_prompt_bytes", 131_073),
        *(("limits", name, 0) for name in bad_limits),
    ):
        held: dict[str, Any] = yaml.safe_load(committed.read_text(encoding="utf-8"))
        held[section][field] = value
        changed = tmp_path / "narrate.yaml"
        changed.write_text(yaml.safe_dump(held), encoding="utf-8")
        with pytest.raises(ValueError):
            _flow().load_narrate_config(changed)


def test_a_config_cannot_change_the_invocation(tmp_path: Path) -> None:
    """W1: ``--narrate-config`` cannot widen what Task 0 proved, however it edits the args."""
    committed = (REPO_ROOT / "config/narrate.yaml").read_text(encoding="utf-8")
    assert "extra_args" not in committed
    config = _flow().load_narrate_config(REPO_ROOT / "config/narrate.yaml")
    assert config.claude.extra_args == _flow().NARRATE_ISOLATION
    for args in ("[]", '["--tools", "Bash"]', '["--dangerously-skip-permissions"]'):
        changed = tmp_path / "narrate.yaml"
        changed.write_text(committed.replace("claude:\n", f"claude:\n  extra_args: {args}\n", 1))
        with pytest.raises(ValueError, match="extra_args"):
            _flow().load_narrate_config(changed)
