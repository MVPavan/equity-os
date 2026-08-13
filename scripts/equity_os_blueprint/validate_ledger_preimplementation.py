#!/usr/bin/env python3
"""Generated verbatim from docs/goals/equity-os-blueprint-completion.md."""

import hashlib
import json
from pathlib import Path

path = Path("docs/goals/equity-os-blueprint-component-ledger.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
canonical = [row for row in rows if row["kind"] != "derivative_alias"]
assert canonical

def digest(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def input_projection(row):
    scope = row["scope_derivation"]
    scope_without_review = {
        key: value for key, value in scope.items() if key != "semantic_review"
    }
    fields = {
        "component_id", "canonical_component_id", "kind", "source_path",
        "source_anchor", "source_start_line", "source_end_line", "source_hash",
        "text_digest", "authority_rank", "register_id", "source_title",
        "required_acceptance_text", "blueprint_phase", "priority",
        "activation_source_status", "source_status", "dependencies",
        "primary_spec", "disposition_refs", "gate_refs", "activation_predicate",
        "activation_record", "rejection_record", "program_disposition",
        "bead_ids", "roadmap_ref", "plan_refs", "implementation_refs",
        "tracked_work", "required_evidence", "evidence_refs",
        "verification_command", "required_approvals", "approval_records",
        "review_round", "open_findings", "human_review_id",
        "security_exception_ids", "blocked_scope", "transition_history_sha256",
    }
    projection = {field: row[field] for field in sorted(fields)}
    projection["scope_derivation"] = scope_without_review
    return projection

def inventory_projection(row, review_type):
    if review_type == "SCOPE":
        scope = row["scope_derivation"]
        return {
            "scope_derivation": {
                key: value for key, value in scope.items()
                if key != "semantic_review"
            },
            "disposition_refs": row["disposition_refs"],
            "gate_refs": row["gate_refs"],
            "activation_predicate": row["activation_predicate"],
            "related_register_ids": scope["related_register_ids"],
        }
    if review_type == "EVIDENCE":
        return {
            "required_evidence": row["required_evidence"],
            "evidence_refs": row["evidence_refs"],
            "verification_command": row["verification_command"],
        }
    assert review_type == "APPROVAL"
    return {
        "required_approvals": row["required_approvals"],
        "approval_records": row["approval_records"],
        "human_review_id": row["human_review_id"],
        "security_exception_ids": row["security_exception_ids"],
    }

def current_complete(row, review, review_type):
    assert review["review_type"] == review_type
    assert review["status"] == "COMPLETE"
    assert review["reviewed_input_sha256"] == digest(input_projection(row))
    assert review["reviewed_inventory_sha256"] == digest(
        inventory_projection(row, review_type)
    )

for row in canonical:
    current_complete(row, row["approval_inventory_review"], "APPROVAL")
    current_complete(row, row["evidence_inventory_review"], "EVIDENCE")
    if row["kind"] != "register_row":
        current_complete(row, row["scope_derivation"]["semantic_review"], "SCOPE")
