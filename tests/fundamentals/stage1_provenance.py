"""Stage 1 provenance against the frozen manifest: where each selected value was read."""

from __future__ import annotations

from typing import Any

import pytest
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
from fundamentals.contracts.canonical import Basis, Representation, ValueKind
from fundamentals.contracts.comparison import SourceRole
from fundamentals.contracts.evidence import InterpretationOrigin
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import ConditionPredicate

DEFAULT_TIER = EvidenceTier.EQUIVALENCE_UNPROVEN.value
DEMONSTRATED = EvidenceTier.EQUIVALENCE_DEMONSTRATED
VENDOR_ROLES = (SourceRole.INDEPENDENT_VENDOR, SourceRole.DIAGNOSTIC)


def provenance(outcome: Outcome, rows: tuple[ResultRow, ...] | None = None) -> list[str]:
    """Where the manifest records them: each selected first-party interpretation's capture and
    native locator (XBRL element and context, PDF page, label and column) and tier, and each
    row's applicability rule id."""
    run, repository = outcome.stage.run, outcome.stage.repository
    want = expanded_rows(run)
    keys = {row_key(run, row): row.key for row in rows or outcome.rows}
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
        if item.tier is DEMONSTRATED and not _qualified(
            outcome, rows or outcome.rows, keys[key], item, item
        ):
            lines.append(f"{key} {name} tier {item.tier.value} is not qualified")
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
            located = (src, anchor.get("page"), n, column)
            if located != (side["src"], side["pg"], side.get("n", 1), side["col"]):
                lines.append(f"{key} {name} locator: want {side} got {located} {cell.native_field}")
    lines += _vendor_provenance(outcome, rows or outcome.rows)
    # applicability.*_by_rule keys read '<rule id>[:] <note>'; a row's own rule overrides
    rules = {
        canonical: rule.split()[0].rstrip(":")
        for section in run.get("applicability", {}).values()
        for rule, canonicals in (section or {}).items()
        for canonical in canonicals or ()
    }
    lines += [
        f"{row_key(run, row)} rule: want {rule} got {row.applicability_rule_id}"
        for row in rows or outcome.rows
        if (rule := want.get(row_key(run, row), {}).get("rule", rules.get(row.key.canonical_id)))
        != row.applicability_rule_id
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
        filing = repository.get_interpretations(
            [
                value.interpretation_id
                for value in row.source_values
                if value.source_role is SourceRole.FIRST_PARTY and value.interpretation_id
            ]
        )
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
                    outcome,
                    rows,
                    row,
                    name,
                    side,
                    item,
                    filing,
                    value.interpretation_id is not None,
                )
    return lines


def _vendor_cell(
    outcome: Outcome,
    rows: tuple[ResultRow, ...],
    row: ResultRow,
    name: str,
    side: dict[str, Any],
    item: Any,
    filing: tuple[Any, ...],
    direct: bool,
) -> list[str]:
    """One vendor interpretation against its manifest side (a direct side: locator and tier).

    Spec §2 keeps known non-equivalence apart from unproven equivalence: the only tier the
    stored one may differ from is a DEMONSTRATED raised from a stored EQUIVALENCE_UNPROVEN,
    in the vendor entry's scope and on a selected filing's own re-proven conditions."""
    repository, key = outcome.stage.repository, row_key(outcome.stage.run, row)
    lines, tier = [], side.get("tier", DEFAULT_TIER)
    if direct and tier != item.tier.value:
        if (
            tier != DEMONSTRATED.value
            or item.tier is not EvidenceTier.EQUIVALENCE_UNPROVEN
            or not any(_qualified(outcome, rows, row.key, item, filed) for filed in filing)
        ):
            lines.append(f"{key} {name} tier: want {tier} got {item.tier.value}")
    if item.tier is DEMONSTRATED and not _qualified(outcome, rows, row.key, item, item):
        lines.append(f"{key} {name} tier {item.tier.value} is not qualified")
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


def _qualified(
    outcome: Outcome,
    rows: tuple[ResultRow, ...],
    key: MeasurementKey,
    item: Any,
    filed: Any,
) -> bool:
    """I15: ``item``'s DEMONSTRATED tier holds only inside its entry's qualification scope at the
    schema of ``filed`` (``item`` itself, or the filing a vendor side borrows from), each
    condition re-proven on the run's own selection: the evidence of ``filed``'s proof is the
    selected, directly filed XBRL value of the condition row at the same key, meeting the
    predicate as claimed."""
    entries = {entry.entry_id: entry for entry in outcome.stage.config.mapping_set.entries}
    entry, filed_entry = entries.get(item.mapping_entry_id), entries.get(filed.mapping_entry_id)
    scope = entry.qualification if entry else None
    if (
        entry is None
        or scope is None
        or filed_entry is None
        or filed_entry.schema_identity not in scope.schema_identities
        or entry.surface not in scope.surfaces
        or key.basis not in scope.bases
        or key.period.kind(3) not in scope.period_kinds  # every Stage 1 issuer: March year end
    ):
        return False
    proven = {proof.condition_id: proof for proof in filed.condition_evidence}
    checks = [(c, True) for c in scope.conditions] + [(c, False) for c in scope.exclusions]
    for condition, must_hold in checks:
        at = key.model_copy(update={"canonical_id": condition.canonical_id})
        selected = {
            value.interpretation_id
            for row in rows
            if row.key == at
            for value in row.source_values
            if value.source_role is SourceRole.FIRST_PARTY
        }
        proof = proven.get(condition.condition_id)
        ids = proof.evidence_interpretation_ids if proof else ()
        evidence = outcome.stage.repository.get_interpretations(list(ids))
        if (
            proof is None
            or proof.holds is not must_hold
            or len(evidence) != len(ids)
            or not all(
                other.origin is InterpretationOrigin.DIRECT
                and other.representation is Representation.XBRL
                and other.key == at
                and other.interpretation_id in selected
                and other.value is not None
                and ((other.value == 0) == (condition.predicate is ConditionPredicate.EQUALS_ZERO))
                is must_hold
                for other in evidence
            )
        ):
            return False
    return True


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
    # Sol re-review probes (spec §2, I15): a raised vendor tier stands only on a stored
    # EQUIVALENCE_UNPROVEN, and a condition proof only on the selected zero filed at its key.
    run, repository = outcome.stage.run, outcome.stage.repository
    want, read = expanded_rows(run), repository.get_interpretations
    selected = [
        (row_key(run, row), value)
        for row in outcome.rows
        for value in row.source_values
        if value.interpretation_id is not None
    ]
    raised = {
        value.interpretation_id
        for key, value in selected
        if value.source_role in VENDOR_ROLES
        and want.get(key, {}).get("vendors", {}).get(_name(value), {}).get("tier")
        == DEMONSTRATED.value
    }
    proven = {
        item.interpretation_id
        for item in read(
            [
                v.interpretation_id
                for _, v in selected
                if v.source_role is SourceRole.FIRST_PARTY and v.interpretation_id is not None
            ]
        )
        if item.condition_evidence
    }
    for ids, update in (
        (raised, lambda item: {"tier": EvidenceTier.RELATED_NOT_EQUIVALENT}),
        (
            proven,  # the proof cites the nonzero continuing PAT itself
            lambda item: {
                "condition_evidence": tuple(
                    proof.model_copy(
                        update={"evidence_interpretation_ids": (item.interpretation_id,)}
                    )
                    for proof in item.condition_evidence
                )
            },
        ),
    ):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                repository,
                "get_interpretations",
                lambda wanted, ids=ids, update=update: tuple(
                    item.model_copy(update=update(item)) if item.interpretation_id in ids else item
                    for item in read(wanted)
                ),
            )
            assert not ids or any(" tier" in line for line in provenance(outcome))
