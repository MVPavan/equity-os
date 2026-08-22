"""Deterministic prompt construction: only validated, sourced facts ever leave.

The prompt is assembled purely from a :class:`ValidatedFactSet`. It carries the
publicly disclosed, cross-verified figures (never any copyrighted source-document
text), lists conflicting/missing concepts as explicit *unknowns* the model must
not guess, and instructs the model to return judgment only — citing solely the
provided facts and introducing no new numbers. The instruction text is kept free
of numeric literals so that every number in the finished prompt is, by
construction, a validated fact (see ``verifier.known_numbers``).
"""

from __future__ import annotations

from fundamentals.thesis.contracts import (
    JudgmentSection,
    Unknown,
    UnknownReason,
    ValidatedFact,
    ValidatedFactSet,
)

_SINGLE_SOURCE_NOTE = " [SINGLE FIRST-PARTY SOURCE — weaker, treat with extra caution]"

_UNKNOWN_PHRASES: dict[UnknownReason, str] = {
    UnknownReason.CONFLICT: "sources disagree; value withheld pending human adjudication",
    UnknownReason.MISSING: "not reported by the available sources",
}

_ROLE_PREAMBLE = (
    "You are one of two independent equity analysts. Each of you drafts, without "
    "seeing the other's work, from the SAME validated facts below. A deterministic "
    "cross-verifier then compares your drafts and a human adjudicates only where you "
    "disagree. Your job is JUDGMENT, not measurement."
)

_FACTS_PREAMBLE = (
    "These are publicly disclosed figures, already cross-verified across independent "
    "first-party sources by a deterministic pipeline. Treat every value as fixed ground "
    "truth. These are the ONLY numbers you may cite."
)

_TASK_RULES = (
    "Rules (a violation is a red flag the cross-verifier will catch):\n"
    "- Cite ONLY the facts above. Introduce NO new numbers — no estimates, ratios, "
    "growth rates, price targets, multiples, historical figures, or peer numbers. If a "
    "number is not in the facts above, do not write it.\n"
    "- You supply drivers, thesis impact, observable falsifiers, key risks, and open "
    "questions. This is opinion, explicitly not fact.\n"
    "- Under needed_but_missing, name the data you would want but were not given "
    "(qualitatively, no numbers).\n"
    "- Be concise: short, self-contained points. Do not restate the numbers as a table."
)

_OUTPUT_INSTRUCTION = (
    "Return ONLY a single JSON object and nothing else — no prose before or after, no "
    "code fence. Use exactly these keys, each a list of short strings except stance:"
)

# A numeral-free JSON skeleton: placeholders only, so it adds no numbers to the prompt.
_OUTPUT_SKELETON = (
    '{"stance": "<one short phrase: constructive | cautious | neutral | mixed | '
    'negative>", '
    '"drivers": ["<point>"], '
    '"thesis_impact": ["<point>"], '
    '"observable_falsifiers": ["<point>"], '
    '"key_risks": ["<point>"], '
    '"open_questions": ["<point>"], '
    '"needed_but_missing": ["<point>"]}'
)

_SECTION_ORDER: tuple[JudgmentSection, ...] = (
    JudgmentSection.DRIVERS,
    JudgmentSection.THESIS_IMPACT,
    JudgmentSection.OBSERVABLE_FALSIFIERS,
    JudgmentSection.KEY_RISKS,
    JudgmentSection.OPEN_QUESTIONS,
    JudgmentSection.NEEDED_BUT_MISSING,
)


def _fact_line(fact: ValidatedFact) -> str:
    """Render one validated fact as a single numeral-controlled bullet."""
    agreed = ", ".join(fact.agreed_sources) or "n/a"
    corroborated = ", ".join(fact.corroborating_sources) or "none"
    note = _SINGLE_SOURCE_NOTE if fact.single_sourced else ""
    return (
        f"- {fact.label}: {fact.value} {fact.unit} "
        f"[status: {fact.status}; first-party sources: {agreed}; "
        f"corroborated by: {corroborated}]{note}"
    )


def _unknown_line(unknown: Unknown) -> str:
    """Render one unknown with a fixed, numeral-free explanation."""
    phrase = _UNKNOWN_PHRASES[unknown.reason]
    return f"- {unknown.label}: {phrase}"


def build_prompt(fact_set: ValidatedFactSet) -> str:
    """Build the single deterministic prompt from a validated fact set.

    Every number in the returned string is a validated fact value (or a structural
    date/period token); the instructions carry no numeric literals.
    """
    lines: list[str] = [_ROLE_PREAMBLE, ""]

    lines.append("## COMPANY")
    lines.append(f"Symbol: {fact_set.symbol}")
    if fact_set.name:
        lines.append(f"Name: {fact_set.name}")
    if fact_set.domain:
        lines.append(f"Domain: {fact_set.domain}")
    lines.append(f"Quarter under review: {fact_set.quarter}")
    if fact_set.period_start and fact_set.period_end:
        lines.append(f"Reporting period: {fact_set.period_start} to {fact_set.period_end}")
    currency = fact_set.currency or "n/a"
    lines.append(f"Basis: {fact_set.scope}, {fact_set.basis}, {currency}")
    lines.append("")

    lines.append("## VALIDATED FACTS (ground truth — the only numbers you may cite)")
    lines.append(_FACTS_PREAMBLE)
    lines.extend(_fact_line(fact) for fact in fact_set.facts)
    lines.append("")

    lines.append("## UNKNOWNS (do NOT guess or estimate these)")
    if fact_set.unknowns:
        lines.extend(_unknown_line(unknown) for unknown in fact_set.unknowns)
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## YOUR TASK")
    lines.append(_TASK_RULES)
    lines.append("")
    lines.append("## OUTPUT FORMAT")
    lines.append(_OUTPUT_INSTRUCTION)
    lines.append(_OUTPUT_SKELETON)

    return "\n".join(lines)
