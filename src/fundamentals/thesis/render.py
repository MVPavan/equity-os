"""Render a :class:`ThesisDocument` as non-authoritative, sourced markdown.

The document embeds, in order: the validated facts with their provenance anchors
(labelled OBSERVED), the unknowns withheld from the models, each model's judgment
(labelled OPINION), and the auto-generated cross-verification — unsourced-number
flags and the discrepancy/adjudication queue. A banner makes explicit that the
thesis is non-authoritative until a human adjudicates the queue (invariant 11).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from fundamentals.thesis.adjudication import (
    AdjudicationEntry,
    AdjudicationStatus,
    normalize_queue_key,
)
from fundamentals.thesis.contracts import (
    CrossVerification,
    Discrepancy,
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
_ADJUDICATION_FLAG_PREFIX = "- Human adjudication required: **"
_ADJUDICATION_MANIFEST_PREFIX = "<!-- thesis-adjudication-manifest: "
_ADJUDICATION_MANIFEST_SUFFIX = " -->"
_UNSOURCED_HEADING = "### 4a. Unsourced-number flags"
_PERSISTED_QUEUE_HEADING = "### 4b. Discrepancy / adjudication queue"
_ADJUDICATED_HEADING = "### 4c. Adjudicated"
_SUPERSEDED_HEADING = "### 4d. Superseded"
_RUN_LOG_HEADING = "## 5. Model-run log"
_UNADJUDICATED_FOOTER = (
    "_This document is a machine-generated draft. The numbers are cross-verified facts; "
    "the thesis is un-adjudicated model opinion. Do not treat any model-emitted number as "
    "authoritative — the deterministic pipeline is the only calculator._"
)
_ADJUDICATED_FOOTER = (
    "_This document is a machine-generated draft. The numbers are cross-verified facts; "
    "the thesis includes recorded human adjudications but remains non-authoritative until "
    "separately promoted. The deterministic pipeline remains the only calculator._"
)


def _adjudication_manifest_line(cross: CrossVerification, *, stock: str, quarter: str) -> str:
    """Render machine-readable review state needed by the later apply command."""
    payload = json.dumps(
        {
            "quarter": normalize_queue_key(quarter),
            "stock": normalize_queue_key(stock),
            "unsourced_claims": bool(cross.unsourced_claims),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{_ADJUDICATION_MANIFEST_PREFIX}{payload}{_ADJUDICATION_MANIFEST_SUFFIX}"


def _adjudication_manifest(lines: Sequence[str]) -> tuple[str, str, bool]:
    """Parse the unique apply manifest, failing closed on missing or invalid state."""
    matches = [line for line in lines if line.startswith(_ADJUDICATION_MANIFEST_PREFIX)]
    if len(matches) != 1 or not matches[0].endswith(_ADJUDICATION_MANIFEST_SUFFIX):
        raise ValueError("thesis document must contain exactly one valid adjudication manifest")
    encoded = matches[0][len(_ADJUDICATION_MANIFEST_PREFIX) : -len(_ADJUDICATION_MANIFEST_SUFFIX)]
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError as error:
        raise ValueError("thesis document contains an invalid adjudication manifest") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != {"quarter", "stock", "unsourced_claims"}
        or not isinstance(payload["quarter"], str)
        or not isinstance(payload["stock"], str)
        or not isinstance(payload["unsourced_claims"], bool)
    ):
        raise ValueError("thesis document contains an invalid adjudication manifest")
    return payload["stock"], payload["quarter"], payload["unsourced_claims"]


def markdown_table_cell(text: str) -> str:
    """Make text safe to place inside a markdown table cell."""
    return " ".join(text.split()).replace("|", r"\|")


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
            f"| {markdown_table_cell(fact.label)} | {markdown_table_cell(fact.value)} | "
            f"{markdown_table_cell(fact.unit)} | {markdown_table_cell(fact.status)}{flag} | "
            f"{markdown_table_cell(', '.join(fact.agreed_sources))} | "
            f"{markdown_table_cell(corroborated)} |"
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
    lines = [_UNSOURCED_HEADING, ""]
    if not cross.unsourced_claims:
        lines.append("None detected — no model introduced a number outside the validated fact set.")
        return lines
    lines.append("Numbers a model emitted that are NOT in the validated fact set — do not trust:")
    lines.append("")
    lines.append("| Model | Number | Section | Snippet |")
    lines.append("| --- | --- | --- | --- |")
    for claim in cross.unsourced_claims:
        lines.append(
            f"| {markdown_table_cell(claim.model_label)} | "
            f"{markdown_table_cell(claim.number)} | {markdown_table_cell(claim.section)} | "
            f"{markdown_table_cell(claim.snippet)} |"
        )
    return lines


def _discrepancy_positions(discrepancy: Discrepancy) -> list[str]:
    """Render both original model positions for one discrepancy."""
    lines: list[str] = []
    if discrepancy.model_a_points:
        lines.append(f"- {discrepancy.model_a_label}:")
        lines.extend(f"  - {point}" for point in discrepancy.model_a_points)
    if discrepancy.model_b_points:
        lines.append(f"- {discrepancy.model_b_label}:")
        lines.extend(f"  - {point}" for point in discrepancy.model_b_points)
    return lines


def _adjudication_section(cross: CrossVerification) -> list[str]:
    """Render the discrepancy / human-adjudication queue."""
    lines = [_PERSISTED_QUEUE_HEADING, ""]
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
        lines.extend(_discrepancy_positions(discrepancy))
        lines.append("")
    return lines


def _open_adjudications(entries: Sequence[AdjudicationEntry]) -> list[str]:
    """Render the durable OPEN queue entries for one stock-quarter."""
    lines = [_PERSISTED_QUEUE_HEADING, ""]
    open_entries = [entry for entry in entries if entry.status is AdjudicationStatus.OPEN]
    if not open_entries:
        lines.append("No OPEN discrepancies remain for this stock-quarter.")
        return lines
    for index, entry in enumerate(open_entries, start=1):
        discrepancy = entry.discrepancy
        lines.append(
            f"**{index}. `{entry.id}` [{discrepancy.kind.value}] "
            f"{discrepancy.section}** — {discrepancy.detail}"
        )
        lines.extend(_discrepancy_positions(discrepancy))
        lines.append("")
    return lines


def _accepted_position(entry: AdjudicationEntry) -> list[str]:
    """Render the position selected by a human resolution."""
    discrepancy = entry.discrepancy
    if entry.status is AdjudicationStatus.ACCEPTED_A:
        lines = [f"- Accepted {discrepancy.model_a_label}:"]
        return lines + [f"  - {point}" for point in discrepancy.model_a_points]
    if entry.status is AdjudicationStatus.ACCEPTED_B:
        lines = [f"- Accepted {discrepancy.model_b_label}:"]
        return lines + [f"  - {point}" for point in discrepancy.model_b_points]
    if entry.status is AdjudicationStatus.MERGED:
        return ["- Accepted merged position:", *_discrepancy_positions(discrepancy)]
    return ["- Accepted position: none — both model positions were rejected."]


def _resolved_adjudications(entries: Sequence[AdjudicationEntry]) -> list[str]:
    """Render resolved entries without hiding their original discrepancy payload."""
    lines = [_ADJUDICATED_HEADING, ""]
    resolved = [
        entry
        for entry in entries
        if entry.status is not AdjudicationStatus.OPEN and not entry.superseded
    ]
    if not resolved:
        lines.append("None yet.")
        return lines
    for entry in resolved:
        discrepancy = entry.discrepancy
        lines.append(
            f"**`{entry.id}` [{discrepancy.kind.value}] {discrepancy.section}** — "
            f"{discrepancy.detail}"
        )
        lines.append(f"- Status: {entry.status.value}")
        lines.extend(_accepted_position(entry))
        if entry.status is AdjudicationStatus.REJECTED:
            lines.append("- Rejected positions retained for audit:")
            lines.extend(f"  {line}" for line in _discrepancy_positions(discrepancy))
        if entry.note is not None:
            lines.append(f"- Human note: {entry.note}")
        lines.append("")
    return lines


def _superseded_adjudications(entries: Sequence[AdjudicationEntry]) -> list[str]:
    """Render historical decisions over divergences absent from the current build."""
    lines = [_SUPERSEDED_HEADING, ""]
    superseded = [
        entry
        for entry in entries
        if entry.status is not AdjudicationStatus.OPEN and entry.superseded
    ]
    if not superseded:
        lines.append("None.")
        return lines
    lines.append(
        "These decisions remain in the audit trail but do not adjudicate the current build."
    )
    lines.append("")
    for entry in superseded:
        discrepancy = entry.discrepancy
        lines.append(
            f"**`{entry.id}` [{discrepancy.kind.value}] {discrepancy.section}** — "
            f"{discrepancy.detail}"
        )
        lines.append(f"- Historical status: {entry.status.value}")
        lines.extend(_accepted_position(entry))
        if entry.note is not None:
            lines.append(f"- Human note: {entry.note}")
        lines.append("")
    return lines


def _has_current_resolution(entries: Sequence[AdjudicationEntry]) -> bool:
    """Return whether a resolution adjudicates a divergence in the current build."""
    return any(
        entry.status is not AdjudicationStatus.OPEN and not entry.superseded for entry in entries
    )


def render_persisted_adjudication_sections(entries: Sequence[AdjudicationEntry]) -> str:
    """Render the OPEN and resolved sections from durable queue entries."""
    return "\n".join(
        [
            *_open_adjudications(entries),
            "",
            *_resolved_adjudications(entries),
            "",
            *_superseded_adjudications(entries),
        ]
    )


def _unique_line_index(lines: Sequence[str], marker: str, *, prefix: bool = False) -> int:
    """Return one structural marker index or fail closed on missing/duplicate anchors."""
    indexes = [
        index
        for index, line in enumerate(lines)
        if (line.startswith(marker) if prefix else line == marker)
    ]
    if len(indexes) != 1:
        raise ValueError(f"thesis document must contain exactly one {marker!r} marker")
    return indexes[0]


def apply_adjudications_to_markdown(markdown: str, entries: Sequence[AdjudicationEntry]) -> str:
    """Replace a rendered thesis's review sections without touching facts or drafts."""
    if not entries:
        raise ValueError("no adjudication entries match the requested stock-quarter")
    lines = markdown.splitlines()
    manifest_stock, manifest_quarter, has_unsourced_claims = _adjudication_manifest(lines)
    entry_keys = {
        (normalize_queue_key(entry.stock), normalize_queue_key(entry.quarter)) for entry in entries
    }
    if entry_keys != {(manifest_stock, manifest_quarter)}:
        raise ValueError("adjudication queue entries do not match the thesis document manifest")
    flag_index = _unique_line_index(lines, _ADJUDICATION_FLAG_PREFIX, prefix=True)
    queue_index = _unique_line_index(lines, _PERSISTED_QUEUE_HEADING)
    run_log_index = _unique_line_index(lines, _RUN_LOG_HEADING)
    if not flag_index < queue_index < run_log_index:
        raise ValueError("thesis document adjudication markers are out of order")

    required = (
        any(entry.status is AdjudicationStatus.OPEN for entry in entries) or has_unsourced_claims
    )
    lines[flag_index] = f"{_ADJUDICATION_FLAG_PREFIX}{'YES' if required else 'NO'}**"
    replacement = render_persisted_adjudication_sections(entries).splitlines()
    updated = [*lines[:queue_index], *replacement, "", *lines[run_log_index:]]
    terminal_newline = "\n" if markdown.endswith("\n") else ""
    rendered = "\n".join(updated) + terminal_newline
    if _has_current_resolution(entries) and not required:
        return rendered.replace(_UNADJUDICATED_FOOTER, _ADJUDICATED_FOOTER)
    return rendered


def _run_log(doc: ThesisDocument) -> list[str]:
    """Render the per-model run log, including recorded gaps."""
    lines = [
        _RUN_LOG_HEADING,
        "",
        "| Model | Client | Status | Duration (s) | Note |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for draft in doc.drafts:
        note = draft.error or ("parsed JSON" if draft.parsed else "output present, unstructured")
        lines.append(
            f"| {markdown_table_cell(draft.model_label)} | "
            f"{markdown_table_cell(draft.client_name)} | {draft.status.value} | "
            f"{draft.duration_seconds:.1f} | {markdown_table_cell(note)} |"
        )
    return lines


def render_thesis_document(
    doc: ThesisDocument,
    *,
    generated_at: datetime | None = None,
    adjudications: Sequence[AdjudicationEntry] | None = None,
) -> str:
    """Render the full non-authoritative thesis markdown for one stock-quarter."""
    fact_set = doc.fact_set
    cross = doc.cross_verification
    heading_name = fact_set.name or fact_set.symbol
    adjudication_required = (
        cross.adjudication_required
        if adjudications is None
        else any(entry.status is AdjudicationStatus.OPEN for entry in adjudications)
        or bool(cross.unsourced_claims)
    )
    adjudication = "YES" if adjudication_required else "NO"
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
    lines.append(
        _adjudication_manifest_line(
            cross,
            stock=fact_set.symbol,
            quarter=fact_set.quarter,
        )
    )
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
    if adjudications is None:
        lines.extend(_adjudication_section(cross))
    else:
        lines.extend(_open_adjudications(adjudications))
        lines.append("")
        lines.extend(_resolved_adjudications(adjudications))
        lines.append("")
        lines.extend(_superseded_adjudications(adjudications))
    lines.append("")

    lines.extend(_run_log(doc))
    lines.append("")
    lines.append("---")
    footer = (
        _ADJUDICATED_FOOTER
        if adjudications and _has_current_resolution(adjudications) and not adjudication_required
        else _UNADJUDICATED_FOOTER
    )
    lines.append(footer)
    return "\n".join(lines)
