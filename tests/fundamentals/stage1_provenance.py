"""Stage 1 provenance against the frozen manifest: where each selected value was read."""

from __future__ import annotations

from typing import Any

from stage1_e2e_support import (
    BLOCKS,
    SOURCES,
    Outcome,
    _column,
    _json,
    _name,
    actual,
    diff,
    expected,
    row_key,
)
from test_frozen_manifests import expanded_rows

from fundamentals.compare.run_models import ResultRow
from fundamentals.contracts.canonical import Basis, ValueKind
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.observation import AccountingFramework

DEFAULT_TIER = EvidenceTier.EQUIVALENCE_UNPROVEN.value
VENDOR_ROLES = (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)


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
    lines = [
        f"{key} {name} interpretation {id_} is unknown"
        for (key, name), id_ in sorted(chosen.items())
        if id_ not in found
    ]
    for (key, name), interpretation_id in sorted(chosen.items()):
        if interpretation_id not in found:
            continue
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
    lines += _vendor_provenance(outcome, rows or outcome.rows)
    lines += [
        f"{row_key(run, row)} rule: want {want[row_key(run, row)]['rule']} got "
        f"{row.applicability_rule_id}"
        for row in rows or outcome.rows
        if "rule" in want.get(row_key(run, row), {})
        and row.applicability_rule_id != want[row_key(run, row)]["rule"]
    ]
    return lines


def _vendor_provenance(outcome: Outcome, rows: tuple[ResultRow, ...]) -> list[str]:
    """Each selected vendor interpretation, or each construction trace's operands, resolved to
    its manifest capture and native locator (Screener sec/row/col, Tijori tbl/row/col, Upstox
    block/item/col), its tier and its stored condition evidence; an unknown id fails."""
    run, repository = outcome.stage.run, outcome.stage.repository
    want = expanded_rows(run)
    lines = []
    for row in rows:
        key = row_key(run, row)
        filing = [
            proof
            for item in repository.get_interpretations(
                [
                    value.interpretation_id
                    for value in row.source_values
                    if value.source_role is SourceRole.FIRST_PARTY and value.interpretation_id
                ]
            )
            for proof in item.condition_evidence
        ]
        for value in row.source_values:
            if value.source_role not in VENDOR_ROLES or (
                value.interpretation_id is None and value.calculation_trace_id is None
            ):
                continue
            name = _name(value)
            side = want.get(key, {}).get("vendors", {}).get(name)
            if side is None:
                lines.append(f"{key} {name} has no manifest side")
                continue
            ids = [value.interpretation_id] if value.interpretation_id is not None else []
            if value.calculation_trace_id is not None:
                traces = repository.get_calculation_traces([value.calculation_trace_id])
                if not traces:
                    lines.append(f"{key} {name} trace {value.calculation_trace_id} is unknown")
                    continue
                (trace,) = traces
                if trace.trace.formula_id != side.get("construction"):
                    lines.append(
                        f"{key} {name} construction: want {side.get('construction')}"
                        f" got {trace.trace.formula_id}"
                    )
                ids = [o.interpretation_id for o in trace.trace.operands if o.interpretation_id]
            found = {item.interpretation_id: item for item in repository.get_interpretations(ids)}
            lines += [
                f"{key} {name} interpretation {id_} is unknown" for id_ in ids if id_ not in found
            ]
            for item in found.values():
                lines += _vendor_cell(
                    repository, key, name, side, item, filing, value.interpretation_id is not None
                )
    return lines


def _vendor_cell(
    repository: Any,
    key: str,
    name: str,
    side: dict[str, Any],
    item: Any,
    filing: list[Any],
    direct: bool,
) -> list[str]:
    """One vendor interpretation against its manifest side (a direct side: locator and tier).

    A tier the stored interpretation does not carry is a filing-scoped qualification (spec
    §2): it stands only on the selected filing's holding condition proofs."""
    lines = []
    tier, proofs = side.get("tier", DEFAULT_TIER), item.condition_evidence
    if direct and tier != item.tier.value:
        proofs = filing
        if (
            tier != EvidenceTier.EQUIVALENCE_DEMONSTRATED.value
            or not filing
            or not all(proof.holds for proof in filing)
        ):
            lines.append(f"{key} {name} tier: want {tier} got {item.tier.value}")
    evidence = [i for proof in proofs for i in proof.evidence_interpretation_ids]
    known = {other.interpretation_id for other in repository.get_interpretations(evidence)}
    lines += [f"{key} {name} condition evidence {i} is unknown" for i in evidence if i not in known]
    (cell,) = repository.get_occurrences([item.occurrence_id])
    src, anchor = SOURCES.get(cell.capture.blob_sha256), _json(cell.anchor)
    if src != side["src"]:
        lines.append(f"{key} {name} capture: want {side['src']} got {src}")
    if not direct:
        return lines
    if cell.capture.source_id == "tijori":
        got = {"tbl": anchor["table_key"], "row": anchor["row_key"]}
    elif cell.capture.source_id == "upstox":
        got = {
            "block": BLOCKS.get(anchor["table_key"], anchor["table_key"]),
            "item": anchor["row_label"],
        }
    else:
        got = {"sec": anchor["table_id"].split(":")[0], "row": anchor["row_path"].split(":", 1)[1]}
    got["col"] = anchor["column_label"]
    if got != {field: side.get(field) for field in got}:
        lines.append(f"{key} {name} locator: want {side} got {got}")
    return lines


def check_mutations_caught(outcome: Outcome) -> None:
    """The oracle catches a wrong key part and a relabelled or unknown vendor id."""
    # The whole measurement key is compared: entity, basis, framework and value kind.
    for field, wrong in (
        ("entity_id", outcome.stage.entity_id + 1),
        ("basis", Basis.STANDALONE),
        ("framework", AccountingFramework.IFRS),
        ("value_kind", ValueKind.COUNT),
    ):
        rekeyed = tuple(
            row.model_copy(update={"key": row.key.model_copy(update={field: wrong})})
            for row in outcome.rows
        )
        got = actual(outcome.stage.run, rekeyed, [])
        assert any(
            " key:" in line
            for line in diff(expected(outcome.stage.run, outcome.stage.entity_id), got)
        )
    # Every vendor id resolves to its manifest side: relabelled or unknown ids are caught.
    vendor_ids = [
        value.interpretation_id
        for row in outcome.rows
        for value in row.source_values
        if value.source_role in VENDOR_ROLES and value.interpretation_id
    ]
    for relabel in (
        dict(zip(vendor_ids, vendor_ids[1:] + vendor_ids[:1], strict=True)),
        dict.fromkeys(vendor_ids, 10**9),
    ):
        moved = tuple(
            row.model_copy(
                update={
                    "source_values": tuple(
                        value.model_copy(
                            update={"interpretation_id": relabel[value.interpretation_id]}
                        )
                        if value.interpretation_id in relabel and value.source_role in VENDOR_ROLES
                        else value
                        for value in row.source_values
                    )
                }
            )
            for row in outcome.rows
        )
        assert not vendor_ids or provenance(outcome, moved)
