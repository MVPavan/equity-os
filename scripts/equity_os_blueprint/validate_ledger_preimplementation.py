#!/usr/bin/env python3
"""Generated verbatim from docs/goals/equity-os-blueprint-completion.md."""

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_LEDGER = "docs/goals/equity-os-blueprint-component-ledger.jsonl"

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", required=True)
parser.add_argument("--ledger-path")
parser.add_argument("--report-blockers", action="store_true")
args = parser.parse_args()
root = Path(args.repo_root).resolve()
path = Path(args.ledger_path or DEFAULT_LEDGER)
if not path.is_absolute():
    path = root / path
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
canonical = [row for row in rows if row["kind"] != "derivative_alias"]
assert canonical
by_id = {row["component_id"]: row for row in rows}
assert len(by_id) == len(rows)
validation_now = datetime.datetime.now(datetime.timezone.utc)

def parse_utc(value):
    assert isinstance(value, str)
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    )
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")

def normalized_human_review_id(value):
    """Closed r7 §3.2 human-review-link representation, as a sorted list."""
    if value is None:
        return []
    if isinstance(value, str):
        assert re.fullmatch(r"HR-\d{4}", value)
        return [value]
    assert isinstance(value, list) and len(value) >= 2
    assert all(re.fullmatch(r"HR-\d{4}", item) for item in value)
    assert value == sorted(set(value))
    return list(value)

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
    projection["human_review_id"] = normalized_human_review_id(
        row["human_review_id"]
    )
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
        "human_review_id": normalized_human_review_id(row["human_review_id"]),
        "security_exception_ids": row["security_exception_ids"],
    }

def review_state(row, review, review_type):
    """Return "COMPLETE", "PENDING", or "STALE" without ever waiving."""
    assert review["review_type"] == review_type
    if review["status"] == "PENDING":
        return "PENDING"
    assert review["status"] == "COMPLETE"
    if review["reviewed_input_sha256"] != digest(input_projection(row)):
        return "STALE"
    if review["reviewed_inventory_sha256"] != digest(
        inventory_projection(row, review_type)
    ):
        return "STALE"
    return "COMPLETE"

def current_complete(row, review, review_type):
    assert review_state(row, review, review_type) == "COMPLETE"

# r7 §3.2/§3.6 closed current no-implementation-proof predicate. Membership in
# rejection_record.no_implementation_evidence_ref_ids never establishes current
# proof by itself.
NO_IMPLEMENTATION_REQUIREMENT_MAP = {
    "DISP-R-1": ["REQ-DISP-R-1-NO-IMPLEMENTATION"],
}

def current_no_implementation_proof(row):
    record = row["rejection_record"]
    requirement_ids = NO_IMPLEMENTATION_REQUIREMENT_MAP.get(
        row["component_id"], []
    )
    if record is None or not requirement_ids:
        return True, []
    historical = list(record["no_implementation_evidence_ref_ids"])
    requirements = {
        item["evidence_id"]: item for item in row["required_evidence"]
    }
    assert set(requirement_ids) <= set(requirements)
    mapped = [requirements[item_id] for item_id in requirement_ids]
    evidence_by_id = {
        item["evidence_ref_id"]: item for item in row["evidence_refs"]
    }
    reasons = []
    covered = set()
    for item in mapped:
        covered |= set(item["evidence_ref_ids"])
    if not set(historical) <= covered:
        reasons.append("HISTORICAL_REFS_UNCOVERED")
    if any(item["status"] != "SATISFIED" for item in mapped):
        reasons.append("REQUIREMENT_UNRESOLVED")
    for ref_id in historical:
        reference = evidence_by_id.get(ref_id)
        if reference is None:
            reasons.append("HISTORICAL_REF_MISSING")
            continue
        target = root / reference["path"]
        if reference["digest_mode"] == "FILE_BYTES":
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
        else:
            target_lines = target.read_text(encoding="utf-8").splitlines()
            actual = hashlib.sha256(
                "\n".join(
                    target_lines[reference["start_line"] - 1:
                                 reference["end_line"]]
                ).strip(" \t\n\r\f\v").encode("utf-8")
            ).hexdigest()
        if actual != reference["content_sha256"]:
            reasons.append("HISTORICAL_REF_STALE")
    review = row["evidence_inventory_review"]
    review_ok = (
        isinstance(review, dict)
        and review["status"] == "COMPLETE"
        and review["verdict"] == "CLEAN"
        and review.get("role") == "REVIEWER"
        and review.get("role_binding_path") == "CONTEXT.md"
        and isinstance(review.get("model"), str) and review["model"].strip()
        and isinstance(review.get("effort"), str) and review["effort"].strip()
        and set(historical) <= set(review["evidence_ref_ids"])
        and review_state(row, review, "EVIDENCE") == "COMPLETE"
    )
    if review_ok:
        review_time = parse_utc(review["timestamp"])
        review_ok = all(
            review_time >= parse_utc(evidence_by_id[ref_id]["captured_at"])
            for ref_id in historical
        )
    if not review_ok:
        reasons.append("CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING")
    return not reasons, sorted(set(reasons))

pending_reviews = []
stale_reviews = []
for row in canonical:
    checks = [
        ("APPROVAL", row["approval_inventory_review"]),
        ("EVIDENCE", row["evidence_inventory_review"]),
    ]
    if row["kind"] != "register_row":
        checks.append(("SCOPE", row["scope_derivation"]["semantic_review"]))
    for review_type, review in checks:
        state = review_state(row, review, review_type)
        record = {
            "component_id": row["component_id"],
            "review_type": review_type,
            "review_id": row["component_id"] + "::" + review_type,
        }
        if state == "PENDING":
            pending_reviews.append(record)
        elif state == "STALE":
            stale_reviews.append(record)

unmet_no_implementation_proof = []
for row in canonical:
    if row["program_disposition"] != "REJECTED_ACCOUNTED":
        continue
    proven, reasons = current_no_implementation_proof(row)
    if proven:
        continue
    for requirement_id in NO_IMPLEMENTATION_REQUIREMENT_MAP.get(
        row["component_id"], []
    ):
        unmet_no_implementation_proof.append({
            "component_id": row["component_id"],
            "requirement_id": requirement_id,
            "historical_evidence_ref_ids": sorted(
                row["rejection_record"]["no_implementation_evidence_ref_ids"]
            ),
            "reason_codes": reasons,
        })

if args.report_blockers:
    ready = not (
        pending_reviews or stale_reviews or unmet_no_implementation_proof
    )
    report = {
        "gate": "preimplementation",
        "ready": ready,
        "ledger_path": str(path),
        "pending_reviews": pending_reviews,
        "stale_reviews": stale_reviews,
        "unmet_no_implementation_proof": unmet_no_implementation_proof,
    }
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    raise SystemExit(0 if ready else 2)

for row in canonical:
    current_complete(row, row["approval_inventory_review"], "APPROVAL")
    current_complete(row, row["evidence_inventory_review"], "EVIDENCE")
    if row["kind"] != "register_row":
        current_complete(row, row["scope_derivation"]["semantic_review"], "SCOPE")
    proven, reasons = current_no_implementation_proof(row)
    assert proven, (row["component_id"], reasons)
