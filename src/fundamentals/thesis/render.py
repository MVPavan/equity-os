"""Render a :class:`ThesisDocument` as non-authoritative, sourced markdown.

The document embeds, in order: the validated facts with their provenance anchors
(labelled OBSERVED), the unknowns withheld from the models, each model's judgment
(labelled OPINION), and the auto-generated cross-verification — unsourced-number
flags and the discrepancy/adjudication queue. A banner makes explicit that the
thesis is non-authoritative until a human adjudicates the queue (invariant 11).
"""

from __future__ import annotations

from datetime import datetime

from fundamentals.thesis.contracts import (
    CrossVerification,
    JudgmentSection,
    ThesisDocument,
    ThesisDocumentStatus,
    ThesisDraft,
    ValidatedFactSet,
)

_SECTION_TITLES: dict[JudgmentSection, str] = {
    JudgmentSection.DRIVERS: "Drivers",
    JudgmentSection.THESIS_IMPACT: "Thesis impact",
    JudgmentSection.OBSERVABLE_FALSIFIERS: "Observable falsifiers",
    JudgmentSection.KEY_RISKS: "Key risks",
    JudgmentSection.OPEN_QUESTIONS: "Open questions",
    JudgmentSection.NEEDED_BUT_MISSING: "Needed but missing",
}

_STATUS_BANNER: dict[ThesisDocumentStatus, str] = {
    ThesisDocumentStatus.OK: "Two independent model drafts were produced and cross-verified.",
    ThesisDocumentStatus.PARTIAL: (
        "Only ONE model draft was available; the other side is a recorded gap. "
        "Cross-model verification is incomplete."
    ),
    ThesisDocumentStatus.BLOCKED: (
        "BLOCKED — no model draft was produced. No thesis judgment is available."
    ),
}


def _cell(text: str) -> str:
    """Make text safe to place inside a markdown table cell."""
    return text.replace("|", r"\|").replace("\n", " ").strip()


def _facts_table(fact_set: ValidatedFactSet) -> list[str]:
    """Render the validated-facts table (values are OBSERVED ground truth)."""
    lines = [
        "| Fact | Value | Unit | Status | First-party sources | Corroborated |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for fact in fact_set.facts:
        flag = " ⚠ single-source" if fact.single_sourced else ""
        corroborated = ", ".join(fact.corroborating_sources) or "—"
        lines.append(
            f"| {_cell(fact.label)} | {_cell(fact.value)} | {_cell(fact.unit)} | "
            f"{_cell(fact.status)}{flag} | {_cell(', '.join(fact.agreed_sources))} | "
            f"{_cell(corroborated)} |"
        )
    return lines


def _facts_provenance(fact_set: ValidatedFactSet) -> list[str]:
    """Render each fact's per-source provenance anchors."""
    lines: list[str] = ["### Fact provenance (anchors)", ""]
    for fact in fact_set.facts:
        lines.append(f"- **{fact.label}** = {fact.value} {fact.unit} [OBSERVED]")
        for anchor in fact.anchors:
            lines.append(
                f"  - `{anchor.source_id}` ({anchor.source_class}) = {anchor.value} — "
                f"{anchor.description}"
            )
    return lines


def _unknowns(fact_set: ValidatedFactSet) -> list[str]:
    """Render the unknowns withheld from the models."""
    lines = ["## 2. Unknowns withheld from the models", ""]
    if not fact_set.unknowns:
        lines.append("None — every material concept reconciled to a retained value.")
        return lines
    lines.append("These were NOT given to the models (models were told not to guess them):")
    lines.append("")
    for unknown in fact_set.unknowns:
        lines.append(f"- **{unknown.label}** ({unknown.reason.value}) — {unknown.detail}")
    return lines


def _draft_block(draft: ThesisDraft) -> list[str]:
    """Render one model's judgment (opinion), or its raw text if unstructured."""
    stance = draft.stance or "(not stated)"
    lines = [f"### {draft.model_label} ({draft.client_name}) — stance: {stance} [OPINION]", ""]
    if not draft.parsed:
        lines.append("_Model did not return structured JSON; raw output preserved for review:_")
        lines.append("")
        lines.append("```")
        lines.append(draft.raw_text.strip())
        lines.append("```")
        return lines
    for section in JudgmentSection:
        points = draft.section_points(section)
        if not points:
            continue
        lines.append(f"**{_SECTION_TITLES[section]}**")
        lines.extend(f"- {point}" for point in points)
        lines.append("")
    return lines


def _model_drafts(doc: ThesisDocument) -> list[str]:
    """Render the judgment section for every usable draft."""
    lines = ["## 3. Model drafts — judgment only (OPINION, not fact)", ""]
    usable = [draft for draft in doc.drafts if draft.is_usable]
    if not usable:
        lines.append("No usable model drafts were produced.")
        return lines
    for draft in usable:
        lines.extend(_draft_block(draft))
    return lines


def _unsourced_section(cross: CrossVerification) -> list[str]:
    """Render the unsourced-number flags."""
    lines = ["### 4a. Unsourced-number flags", ""]
    if not cross.unsourced_claims:
        lines.append("None detected — no model introduced a number outside the validated fact set.")
        return lines
    lines.append("Numbers a model emitted that are NOT in the validated fact set — do not trust:")
    lines.append("")
    lines.append("| Model | Number | Section | Snippet |")
    lines.append("| --- | --- | --- | --- |")
    for claim in cross.unsourced_claims:
        lines.append(
            f"| {_cell(claim.model_label)} | {_cell(claim.number)} | {_cell(claim.section)} | "
            f"{_cell(claim.snippet)} |"
        )
    return lines


def _adjudication_section(cross: CrossVerification) -> list[str]:
    """Render the discrepancy / human-adjudication queue."""
    lines = ["### 4b. Discrepancy / adjudication queue", ""]
    if not cross.discrepancies:
        lines.append(
            "No material divergences detected by the deterministic diff. "
            "(Two models can share blind spots, so a light human glance is still advised.)"
        )
        return lines
    for index, discrepancy in enumerate(cross.discrepancies, start=1):
        lines.append(
            f"**{index}. [{discrepancy.kind.value}] {discrepancy.section}** — {discrepancy.detail}"
        )
        if discrepancy.model_a_points:
            lines.append(f"- {discrepancy.model_a_label}:")
            lines.extend(f"  - {point}" for point in discrepancy.model_a_points)
        if discrepancy.model_b_points:
            lines.append(f"- {discrepancy.model_b_label}:")
            lines.extend(f"  - {point}" for point in discrepancy.model_b_points)
        lines.append("")
    return lines


def _run_log(doc: ThesisDocument) -> list[str]:
    """Render the per-model run log, including recorded gaps."""
    lines = [
        "## 5. Model-run log",
        "",
        "| Model | Client | Status | Duration (s) | Note |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for draft in doc.drafts:
        note = draft.error or ("parsed JSON" if draft.parsed else "output present, unstructured")
        lines.append(
            f"| {_cell(draft.model_label)} | {_cell(draft.client_name)} | {draft.status.value} | "
            f"{draft.duration_seconds:.1f} | {_cell(note)} |"
        )
    return lines


def render_thesis_document(doc: ThesisDocument, *, generated_at: datetime | None = None) -> str:
    """Render the full non-authoritative thesis markdown for one stock-quarter."""
    fact_set = doc.fact_set
    cross = doc.cross_verification
    heading_name = fact_set.name or fact_set.symbol
    adjudication = "YES" if cross.adjudication_required else "NO"
    generated = generated_at.isoformat() if generated_at is not None else "(not recorded)"

    lines: list[str] = [
        f"# {heading_name} ({fact_set.symbol}) — {fact_set.quarter} — Cross-Verified Thesis",
        "",
        f"> **NON-AUTHORITATIVE DRAFT — status: {doc.status.value.upper()}.** "
        f"{_STATUS_BANNER[doc.status]} "
        "The facts are validated ground truth; the judgment is model opinion and is not "
        "canonical until a human adjudicates the queue below.",
        "",
        f"- Basis: {fact_set.scope}, {fact_set.basis}, {fact_set.currency or 'n/a'}",
    ]
    if fact_set.period_start and fact_set.period_end:
        lines.append(f"- Reporting period: {fact_set.period_start} → {fact_set.period_end}")
    lines.append(f"- Models run: {', '.join(draft.model_label for draft in doc.drafts) or 'none'}")
    lines.append(f"- Human adjudication required: **{adjudication}**")
    lines.append(f"- Generated at: {generated}")
    lines.append("")

    lines.append("## 1. Validated sourced facts (OBSERVED — ground truth)")
    lines.append("")
    lines.extend(_facts_table(fact_set))
    lines.append("")
    lines.extend(_facts_provenance(fact_set))
    lines.append("")

    lines.extend(_unknowns(fact_set))
    lines.append("")

    lines.extend(_model_drafts(doc))
    lines.append("")

    lines.append("## 4. Cross-verification (deterministic)")
    lines.append("")
    lines.extend(_unsourced_section(cross))
    lines.append("")
    lines.extend(_adjudication_section(cross))
    lines.append("")

    lines.extend(_run_log(doc))
    lines.append("")
    lines.append("---")
    lines.append(
        "_This document is a machine-generated draft. The numbers are cross-verified facts; "
        "the thesis is un-adjudicated model opinion. Do not treat any model-emitted number as "
        "authoritative — the deterministic pipeline is the only calculator._"
    )
    return "\n".join(lines)
