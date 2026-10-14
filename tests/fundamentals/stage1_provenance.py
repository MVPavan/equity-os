"""Stage 1 provenance against the frozen manifest: where each selected value was read."""

from __future__ import annotations

from stage1_e2e_support import SOURCES, Outcome, _column, _json, _name, row_key
from test_frozen_manifests import expanded_rows

from fundamentals.compare.run_models import ResultRow
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence_tier import EvidenceTier

DEFAULT_TIER = EvidenceTier.EQUIVALENCE_UNPROVEN.value


def provenance(outcome: Outcome, rows: tuple[ResultRow, ...] | None = None) -> list[str]:
    """Where the manifest records them: each selected first-party interpretation's capture and
    native locator (XBRL element and context, PDF page, label and column) and tier, and each
    row's applicability rule id."""
    run, repository = outcome.stage.run, outcome.stage.repository
    want = expanded_rows(run)
    chosen = {
        (row_key(run, row), _name(value)): value.interpretation_id
        for row in rows or outcome.rows
        if row_key(run, row) in want
        for value in row.source_values
        if value.source_role is SourceRole.FIRST_PARTY and value.interpretation_id is not None
    }
    found = {
        item.interpretation_id: item
        for item in repository.get_interpretations(sorted(set(chosen.values())))
    }
    cells = {
        cell.occurrence_id: cell
        for cell in repository.get_occurrences(
            sorted({item.occurrence_id for item in found.values() if item.occurrence_id})
        )
    }
    lines = []
    for (key, name), interpretation_id in sorted(chosen.items()):
        side, item = want[key].get(name) or {}, found[interpretation_id]
        tier = side.get("tier", DEFAULT_TIER)  # header.notation side: tier only if not UNPROVEN
        if side and tier != item.tier.value:
            lines.append(f"{key} {name} tier: want {tier} got {item.tier.value}")
        cell = cells.get(item.occurrence_id)
        if cell is None:
            continue
        src, anchor = SOURCES.get(cell.capture.blob_sha256), _json(cell.anchor)
        if src is None:
            lines.append(f"{key} {name} capture {cell.capture.blob_sha256} is no manifest source")
        elif "at" in side:
            got = (src, cell.native_context.get("local_name"), anchor.get("context_ref"))
            if got not in {(at["src"], at["c"], at["ctx"]) for at in side["at"]}:
                lines.append(f"{key} {name} at: want {side['at']} got {got}")
        elif "pg" in side:
            # header.notation pdf_locator: the label's tokens among the printed words; n its
            # top-down instance on the page
            label = set(side["label"].split())
            page = repository.list_capture_occurrences(cell.capture.capture_ref_id or 0)
            instances = sorted(
                {
                    _json(other.anchor)["line"]
                    for other in page
                    if _json(other.anchor).get("page") == anchor.get("page")
                    and label <= set(other.native_field.split())
                }
            )
            line = anchor.get("line")
            n = instances.index(line) + 1 if line in instances else None
            column = _column(src, anchor) if "column_x0" in anchor else None
            got = (src, anchor.get("page"), n, column)
            if got != (side["src"], side["pg"], side.get("n", 1), side["col"]):
                lines.append(f"{key} {name} locator: want {side} got {got} {cell.native_field}")
    lines += [
        f"{row_key(run, row)} rule: want {want[row_key(run, row)]['rule']} got "
        f"{row.applicability_rule_id}"
        for row in rows or outcome.rows
        if "rule" in want.get(row_key(run, row), {})
        and row.applicability_rule_id != want[row_key(run, row)]["rule"]
    ]
    return lines
