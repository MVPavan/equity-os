#!/usr/bin/env python3
"""Generated verbatim from docs/goals/equity-os-blueprint-completion.md."""

import argparse
import collections
import datetime
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

DEFAULT_LEDGER = "docs/goals/equity-os-blueprint-component-ledger.jsonl"
DEFAULT_HUMAN_REVIEW = "docs/goals/equity-os-blueprint-human-review-needed.md"

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", required=True)
parser.add_argument("--ledger-path")
parser.add_argument("--human-review-path")
parser.add_argument("--reconciliation-check", action="store_true")
parser.add_argument("--reconciliation-baseline-ledger-path")
parser.add_argument("--reconciliation-baseline-human-review-path")
args = parser.parse_args()
assert (args.ledger_path is None) == (args.human_review_path is None)
baseline_arguments = (
    args.reconciliation_baseline_ledger_path,
    args.reconciliation_baseline_human_review_path,
)
if args.reconciliation_check:
    assert all(baseline_arguments)
else:
    assert not any(baseline_arguments)

root = Path(args.repo_root).resolve()
validation_now = datetime.datetime.now(datetime.timezone.utc)

def selected_path(value, default):
    candidate = Path(value or default)
    return candidate if candidate.is_absolute() else root / candidate

ledger_path = selected_path(args.ledger_path, DEFAULT_LEDGER)
human_review_path = selected_path(args.human_review_path, DEFAULT_HUMAN_REVIEW)
assert ledger_path.is_file() and human_review_path.is_file()
assert ledger_path.resolve() != human_review_path.resolve()
lines = ledger_path.read_text(encoding="utf-8").splitlines()
assert lines and all(line.strip() for line in lines)
rows = [json.loads(line) for line in lines]

required = {
    "component_id", "canonical_component_id", "kind", "source_path",
    "source_anchor", "source_start_line", "source_end_line", "source_hash",
    "text_digest", "authority_rank", "source_title", "required_acceptance_text",
    "register_id", "blueprint_phase", "priority", "activation_source_status",
    "source_status", "dependencies", "primary_spec",
    "disposition_refs", "gate_refs", "activation_predicate",
    "scope_derivation", "activation_record", "rejection_record",
    "program_disposition", "delivery_status", "gate_result", "bead_ids",
    "roadmap_ref", "plan_refs", "implementation_refs", "tracked_work",
    "required_evidence",
    "evidence_refs", "evidence_inventory_review", "verification_command",
    "verification_result", "verified_at", "required_approvals", "approval_records",
    "approval_inventory_review", "review_round", "open_findings",
    "human_review_id", "security_exception_ids", "blocked_scope",
    "transition_history", "transition_history_sha256",
}
assert all(required <= row.keys() for row in rows)
by_id = {row["component_id"]: row for row in rows}
assert len(by_id) == len(rows)

def canonical_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def parse_utc_rfc3339(value):
    assert isinstance(value, str)
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value
    )
    parsed = datetime.datetime.fromisoformat(value[:-1] + "+00:00")
    assert parsed.tzinfo == datetime.timezone.utc
    return parsed

def repo_path(value, *, must_exist):
    assert isinstance(value, str) and value.strip()
    parsed = PurePosixPath(value)
    assert not parsed.is_absolute() and ".." not in parsed.parts
    candidate = (root / Path(*parsed.parts)).resolve()
    assert candidate.is_relative_to(root)
    if must_exist:
        assert candidate.exists()
    return candidate

canonical_kinds = {
    "register_row",
    "phase_gate_clause",
    "first_release_deferral",
    "scale_trigger",
    "disposition_item",
    "authority_clause",
    "sequence_clause",
    "document_strategy_clause",
}
alias_kind = "derivative_alias"
assert {row["kind"] for row in rows} <= canonical_kinds | {alias_kind}

source_statuses = {"Open", "In progress", "Accepted", "Deferred", "Rejected"}
program_dispositions = {
    "REQUIRED_NOW",
    "CONDITIONAL_UNACTIVATED",
    "CONDITIONAL_ACTIVATED",
    "REJECTED_ACCOUNTED",
    "DERIVATIVE_ALIAS",
}
delivery_statuses = {
    "INVENTORIED",
    "SPEC_DRAFT",
    "SPEC_APPROVED_DELEGATED",
    "PLANNED",
    "IMPLEMENTING",
    "REVIEW_BLOCKED",
    "VERIFICATION_BLOCKED",
    "EXTERNAL_EVIDENCE_BLOCKED",
    "VERIFIED",
}
gate_results = {
    "NOT_EVALUATED", "PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE_DORMANT"
}
assert all(row["program_disposition"] in program_dispositions for row in rows)
assert all(row["delivery_status"] in delivery_statuses for row in rows)
assert all(row["gate_result"] in gate_results for row in rows)

authority_paths = {
    "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
    "docs/blueprint/funda-third-order-review-disposition-report.md",
}
authority_rank_by_path = {
    "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md": 2,
    "docs/blueprint/funda-third-order-review-disposition-report.md": 3,
}
activation_authority_hashes = {
    "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md":
        "26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164",
    "docs/blueprint/funda-third-order-review-disposition-report.md":
        "a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738",
}
current_source_hashes = {
    source_path: hashlib.sha256(repo_path(source_path, must_exist=True).read_bytes()).hexdigest()
    for source_path in authority_paths
}
source_keys = []
source_spans = []
for row in rows:
    assert isinstance(row["component_id"], str) and row["component_id"].strip()
    source_path = row["source_path"]
    source_anchor = row["source_anchor"]
    assert isinstance(source_path, str) and source_path.strip()
    repo_path(source_path, must_exist=True)
    assert source_path in authority_paths
    assert isinstance(source_anchor, str) and source_anchor.strip()
    start = row["source_start_line"]
    end = row["source_end_line"]
    assert isinstance(start, int) and not isinstance(start, bool)
    assert isinstance(end, int) and not isinstance(end, bool)
    source_lines = repo_path(source_path, must_exist=True).read_text(
        encoding="utf-8"
    ).splitlines()
    assert 1 <= start <= end <= len(source_lines)
    assert row["source_hash"] == current_source_hashes[source_path]
    assert row["authority_rank"] == authority_rank_by_path[source_path]
    extracted = "\n".join(source_lines[start - 1:end]).strip(" \t\n\r\f\v")
    expected_text_digest = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
    assert row["text_digest"] == expected_text_digest
    source_keys.append((source_path, source_anchor))
    source_spans.append((source_path, start, end))
assert len(set(source_keys)) == len(source_keys)
assert len(set(source_spans)) == len(source_spans)

evidence_ref_fields = {
    "evidence_ref_id", "path", "scope", "digest_mode", "start_line",
    "end_line", "content_sha256", "captured_at",
}
UNRESOLVABLE_SPAN_DIAGNOSTIC = "UNRESOLVABLE_UTF8_LINE_SPAN"

def resolve_utf8_line_span(evidence, target_lines, owner):
    """Return the stripped span text, or exit 2 if the span is unresolvable.

    r7 §6.3 item 2 / §8.1: an out-of-range `UTF8_LINE_SPAN` target is a
    fail-closed diagnostic, never an uncaught traceback.
    """
    start, end = evidence["start_line"], evidence["end_line"]
    if not 1 <= start <= end <= len(target_lines):
        print(
            f"{UNRESOLVABLE_SPAN_DIAGNOSTIC}: owner={owner} "
            f"evidence_ref_id={evidence['evidence_ref_id']} "
            f"path={evidence['path']} requested_span={start}-{end} "
            f"target_line_count={len(target_lines)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return "\n".join(target_lines[start - 1:end]).strip(" \t\n\r\f\v")

evidence_by_id = {}
local_evidence_ids = {}
for row in rows:
    assert isinstance(row["evidence_refs"], list)
    local_ids = set()
    for evidence in row["evidence_refs"]:
        assert evidence_ref_fields <= evidence.keys()
        evidence_ref_id = evidence["evidence_ref_id"]
        assert isinstance(evidence_ref_id, str) and evidence_ref_id.strip()
        assert evidence_ref_id not in evidence_by_id
        target = repo_path(evidence["path"], must_exist=True)
        assert target not in {ledger_path.resolve(), human_review_path.resolve()}
        assert isinstance(evidence["scope"], str) and evidence["scope"].strip()
        assert parse_utc_rfc3339(evidence["captured_at"]) <= validation_now
        if evidence["digest_mode"] == "FILE_BYTES":
            assert evidence["start_line"] is None and evidence["end_line"] is None
            actual_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        else:
            assert evidence["digest_mode"] == "UTF8_LINE_SPAN"
            start, end = evidence["start_line"], evidence["end_line"]
            assert isinstance(start, int) and not isinstance(start, bool)
            assert isinstance(end, int) and not isinstance(end, bool)
            target_lines = target.read_text(encoding="utf-8").splitlines()
            extracted = resolve_utf8_line_span(
                evidence, target_lines, row["component_id"]
            )
            actual_digest = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
        assert evidence["content_sha256"] == actual_digest
        evidence_by_id[evidence_ref_id] = evidence
        local_ids.add(evidence_ref_id)
    local_evidence_ids[row["component_id"]] = local_ids

review_fields = {
    "review_type", "status", "reviewer", "model", "effort", "verdict",
    "timestamp", "evidence_ref_ids", "reviewed_input_sha256",
    "reviewed_inventory_sha256",
}
# r7 §3.8: `CONTEXT.md` "Agent roles (harness-wide)" is the single binding
# table. The goal restates no model binding, and no validator asserts a vendor
# model or effort constant anywhere.
REVIEW_ROLES = {"IMPLEMENTER", "ORCHESTRATOR", "REVIEWER"}
ROLE_BINDING_PATH = "CONTEXT.md"
role_binding_fields = {"role", "role_binding_path", "role_binding_sha256"}

def assert_reviewer_role_binding(review):
    """r7 §3.8 closed role binding for a COMPLETE review.

    `role_binding_sha256` is an immutable historical capture, deliberately not
    a declared evidence object: re-verifying it against current bytes would let
    an unrelated `CONTEXT.md` edit invalidate completed reviews.
    """
    assert review["role"] in REVIEW_ROLES
    assert review["role"] == "REVIEWER"
    assert review["role_binding_path"] == ROLE_BINDING_PATH
    assert re.fullmatch(r"[0-9a-f]{64}", review["role_binding_sha256"])
    assert isinstance(review["model"], str) and review["model"].strip()
    assert isinstance(review["effort"], str) and review["effort"].strip()

def review_input_projection(row):
    scope = row["scope_derivation"]
    scope_without_review = None
    if isinstance(scope, dict):
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
    projection["human_review_id"] = sorted(
        normalized_human_review_id(row["human_review_id"])
    )
    return projection

def review_inventory_projection(row, review_type):
    if review_type == "SCOPE":
        scope = row["scope_derivation"]
        assert isinstance(scope, dict)
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
        "human_review_id": sorted(normalized_human_review_id(row["human_review_id"])),
        "security_exception_ids": row["security_exception_ids"],
    }

def validate_inventory_review(row, review, review_type):
    assert isinstance(review, dict)
    # r7 §3.2 bullet 12: a PENDING review keeps exactly its existing key set;
    # a COMPLETE review carries exactly that key set plus the role binding.
    if review.get("status") == "COMPLETE":
        assert set(review) == review_fields | role_binding_fields
    else:
        assert set(review) == review_fields
    assert review["review_type"] == review_type
    assert review["status"] in {"PENDING", "COMPLETE"}
    assert isinstance(review["evidence_ref_ids"], list)
    assert set(review["evidence_ref_ids"]) <= local_evidence_ids[row["component_id"]]
    if review["status"] == "PENDING":
        for field in (
            "reviewer", "model", "effort", "verdict", "timestamp",
            "reviewed_input_sha256", "reviewed_inventory_sha256",
        ):
            assert review[field] is None
        assert review["evidence_ref_ids"] == []
    else:
        assert isinstance(review["reviewer"], str) and review["reviewer"].strip()
        assert_reviewer_role_binding(review)
        assert review["verdict"] == "CLEAN"
        timestamp = parse_utc_rfc3339(review["timestamp"])
        assert timestamp <= validation_now
        assert review["evidence_ref_ids"]
        assert all(
            timestamp >= parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"])
            for ref_id in review["evidence_ref_ids"]
        )
        assert review["reviewed_input_sha256"] == canonical_sha256(
            review_input_projection(row)
        )
        assert review["reviewed_inventory_sha256"] == canonical_sha256(
            review_inventory_projection(row, review_type)
        )

canonical_rows = [row for row in rows if row["kind"] in canonical_kinds]
aliases = [row for row in rows if row["kind"] == alias_kind]
counts = collections.Counter(row["kind"] for row in canonical_rows)
expected_kind_counts = {
    "register_row": 60,
    "phase_gate_clause": 35,
    "first_release_deferral": 13,
    "scale_trigger": 8,
    "disposition_item": 32,
    "authority_clause": 4,
    "sequence_clause": 11,
    "document_strategy_clause": 6,
}
for kind, expected in expected_kind_counts.items():
    assert counts[kind] == expected, (kind, counts[kind])
assert sum(expected_kind_counts.values()) == 169
assert len(canonical_rows) == 169
assert len(aliases) == 44
assert len(rows) == 213

expected_authority_clause_lines = {
    "AUTH-REG-001": (
        "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
        23,
    ),
    "AUTH-DISP-001": (
        "docs/blueprint/funda-third-order-review-disposition-report.md",
        41,
    ),
    "AUTH-REG-002": (
        "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
        193,
    ),
    "AUTH-REG-003": (
        "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
        209,
    ),
}
authority_rows = {
    row["component_id"]: row for row in canonical_rows
    if row["kind"] == "authority_clause"
}
assert set(authority_rows) == set(expected_authority_clause_lines)
for component_id, (path_value, line_number) in (
    expected_authority_clause_lines.items()
):
    authority_row = authority_rows[component_id]
    assert authority_row["source_path"] == path_value
    assert authority_row["source_start_line"] == line_number
    assert authority_row["source_end_line"] == line_number

# r7 §3.5.2: the five Phase-2 gates that remain CONDITIONAL_UNACTIVATED and
# therefore legitimately carry an activation predicate. PG-2-04 is deliberately
# absent (r7 §3.5.1).
PHASE2_CONDITIONAL_GATE_IDS = {
    "PG-2-01", "PG-2-02", "PG-2-03", "PG-2-05", "PG-2-06",
}


def alias_targets(value):
    """Closed r7 §3.2 alias-target representation."""
    if isinstance(value, str):
        assert value.strip()
        return [value]
    assert isinstance(value, list) and len(value) >= 2
    assert all(isinstance(item, str) and item.strip() for item in value)
    assert value == sorted(set(value))
    return list(value)


def normalized_human_review_id(value):
    """Closed r7 §3.2 human-review-link representation, as a set."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        assert re.fullmatch(r"HR-\d{4}", value)
        return frozenset({value})
    assert isinstance(value, list) and len(value) >= 2
    assert all(re.fullmatch(r"HR-\d{4}", item) for item in value)
    assert value == sorted(set(value))
    return frozenset(value)


for row in canonical_rows:
    assert row["canonical_component_id"] is None
    assert row["program_disposition"] != "DERIVATIVE_ALIAS"
    primary_spec = row["primary_spec"]
    if primary_spec is None:
        assert row["kind"] != "register_row"
    else:
        assert {"spec_id", "title", "path"} <= primary_spec.keys()
        assert re.fullmatch(r"S(?:0[1-9]|1\d|2[0-5])", primary_spec["spec_id"])
        assert isinstance(primary_spec["title"], str) and primary_spec["title"].strip()
        repo_path(primary_spec["path"], must_exist=False)

for row in aliases:
    target_id = row["canonical_component_id"]
    assert row["program_disposition"] == "DERIVATIVE_ALIAS"
    assert row["primary_spec"] is None
    assert row["activation_source_status"] is None
    assert row["source_status"] is None
    assert row["required_approvals"] == []
    assert row["approval_records"] == []
    assert row["approval_inventory_review"] is None
    assert row["scope_derivation"] is None
    assert row["activation_record"] is None
    assert row["rejection_record"] is None
    assert row["bead_ids"] == []
    assert row["roadmap_ref"] is None
    assert row["plan_refs"] == []
    assert row["implementation_refs"] == []
    assert row["tracked_work"] == []
    assert row["required_evidence"] == []
    assert row["evidence_inventory_review"] is None
    assert row["verification_command"] == {
        "mode": "UNRESOLVED", "commands": [], "not_applicable_review": None
    }
    assert row["verification_result"] == []
    assert row["verified_at"] is None
    assert row["delivery_status"] == "INVENTORIED"
    assert row["gate_result"] == "NOT_EVALUATED"
    assert row["human_review_id"] is None
    assert row["security_exception_ids"] == []
    assert row["blocked_scope"] == []
    targets = alias_targets(target_id)
    assert targets
    assert row["component_id"] not in targets
    assert all(item in by_id for item in targets)
    assert all(by_id[item]["kind"] in canonical_kinds for item in targets)

# Follow targets even though aliases must point directly to canonical objects;
# this makes a future relaxation fail closed instead of admitting a cycle.
for row in aliases:
    seen = {row["component_id"]}
    pending_targets = list(alias_targets(row["canonical_component_id"]))
    while pending_targets:
        target_id = pending_targets.pop()
        assert target_id in by_id and target_id not in seen
        seen.add(target_id)
        follow = by_id[target_id]["canonical_component_id"]
        if follow is not None:
            pending_targets.extend(alias_targets(follow))
        else:
            assert by_id[target_id]["kind"] in canonical_kinds

expected_ids = {
    *(f"A-{i:02d}" for i in range(1, 14)),
    *(f"B-{i:02d}" for i in range(1, 15)),
    *(f"C-{i:02d}" for i in range(1, 19)),
    *(f"D-{i:02d}" for i in range(1, 6)),
    *(f"E-{i:02d}" for i in range(1, 11)),
}
register_rows = [row for row in rows if row["kind"] == "register_row"]
owners = collections.Counter(row["register_id"] for row in register_rows)
assert set(owners) == expected_ids
assert all(count == 1 for count in owners.values())

register_authority = {}
register_text = repo_path(
    "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
    must_exist=True,
).read_text(encoding="utf-8")
phase_by_section = {"A": "0A", "B": "0.5", "C": "1", "D": "2", "E": "3+"}
for line_number, line in enumerate(register_text.splitlines(), 1):
    match = re.match(r"^\|\s*([A-E]-\d{2})\s*\|", line)
    if match:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 6 and cells[-1] in source_statuses
        register_id = match.group(1)
        assert register_id not in register_authority
        dependencies = [] if cells[4] == "—" else [
            item.strip() for item in cells[4].split(",")
        ]
        register_authority[register_id] = {
            "blueprint_phase": phase_by_section[register_id[0]],
            "priority": cells[1],
            "source_title": cells[2],
            "required_acceptance_text": cells[3],
            "dependencies": dependencies,
            "source_status": cells[5],
            "line_number": line_number,
        }
assert set(register_authority) == expected_ids

initial_deferred_ids = {
    "C-14", "D-02", "D-03", "D-04", "D-05",
    *(f"E-{i:02d}" for i in range(1, 11)),
}

for row in register_rows:
    register_id = row["register_id"]
    authority = register_authority[register_id]
    assert row["source_path"] == (
        "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
    )
    assert row["source_anchor"] == register_id
    assert row["source_start_line"] == row["source_end_line"] == authority["line_number"]
    assert row["authority_rank"] == 2
    assert row["blueprint_phase"] == authority["blueprint_phase"]
    assert row["priority"] == authority["priority"]
    assert row["source_title"] == authority["source_title"]
    assert row["required_acceptance_text"] == authority["required_acceptance_text"]
    assert row["dependencies"] == authority["dependencies"]
    expected_initial = "Deferred" if register_id in initial_deferred_ids else "Open"
    assert row["activation_source_status"] == expected_initial
    assert row["source_status"] == authority["source_status"]
for row in canonical_rows:
    if row["kind"] != "register_row":
        assert row["activation_source_status"] is None
        assert row["source_status"] is None
        assert row["register_id"] is None

activation_statuses = collections.Counter(
    row["activation_source_status"] for row in register_rows
)
assert activation_statuses == {"Open": 45, "Deferred": 15}
assert {row["primary_spec"]["spec_id"] for row in register_rows} == {
    f"S{i:02d}" for i in range(1, 26)
}

expected_owners = {
    "S01": {"A-01", "A-09", "E-08"},
    "S02": {"A-05", "C-13"},
    "S03": {"E-06", "E-07"},
    "S04": {"E-09"},
    "S05": {"A-02", "A-03", "A-11"},
    "S06": {"A-04", "A-10"},
    "S07": {"A-08", "B-08", "B-13"},
    "S08": {"A-07", "A-12", "A-13"},
    "S09": {"A-06", "B-09", "C-02", "C-14"},
    "S10": {"B-03", "C-11"},
    "S11": {"C-09", "C-15", "C-16"},
    "S12": {"B-05", "B-10", "B-11", "C-03"},
    "S13": {"B-06", "B-12", "C-04"},
    "S14": {"B-01", "B-02", "B-14"},
    "S15": {"C-05", "C-10"},
    "S16": {"B-07", "C-08"},
    "S17": {"C-06", "C-07", "C-17"},
    "S18": {"B-04", "C-01", "C-12", "C-18"},
    "S19": {"D-01", "D-03"},
    "S20": {"D-02", "D-04", "D-05"},
    "S21": {"E-01"},
    "S22": {"E-02"},
    "S23": {"E-03"},
    "S24": {"E-04"},
    "S25": {"E-05", "E-10"},
}
contract_text = repo_path(
    "docs/goals/equity-os-blueprint-completion.md", must_exist=True
).read_text(encoding="utf-8")
expected_spec_contract = {}
for line in contract_text.splitlines():
    if not re.match(r"^\| S(?:0[1-9]|1\d|2[0-5]) \|", line):
        continue
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    assert len(cells) == 5
    spec_id, title, path_cell, register_cell, _ = cells
    assert spec_id not in expected_spec_contract
    assert path_cell.startswith("`") and path_cell.endswith("`")
    path_value = path_cell[1:-1]
    repo_path(path_value, must_exist=False)
    register_ids = {item.strip() for item in register_cell.split(",")}
    expected_spec_contract[spec_id] = {
        "spec_id": spec_id, "title": title, "path": path_value,
        "register_ids": register_ids,
    }
assert set(expected_spec_contract) == set(expected_owners)
assert all(
    expected_spec_contract[spec_id]["register_ids"] == register_ids
    for spec_id, register_ids in expected_owners.items()
)
actual_owners = collections.defaultdict(set)
for row in register_rows:
    spec = row["primary_spec"]
    expected_spec = expected_spec_contract[spec["spec_id"]]
    assert spec == {
        "spec_id": expected_spec["spec_id"],
        "title": expected_spec["title"],
        "path": expected_spec["path"],
    }
    actual_owners[spec["spec_id"]].add(row["register_id"])
assert dict(actual_owners) == expected_owners

statuses_by_spec = collections.defaultdict(set)
for row in register_rows:
    statuses_by_spec[row["primary_spec"]["spec_id"]].add(
        row["activation_source_status"]
    )
mixed_specs = {
    spec_id
    for spec_id, statuses in statuses_by_spec.items()
    if "Deferred" in statuses and statuses - {"Deferred"}
}
dormant_only_specs = {
    spec_id
    for spec_id, statuses in statuses_by_spec.items()
    if statuses == {"Deferred"}
}
assert mixed_specs == {"S01", "S09", "S19"}
assert dormant_only_specs == {
    "S03", "S04", "S20", "S21", "S22", "S23", "S24", "S25"
}

tracked_work_fields = {
    "work_ref_id", "work_type", "work_role", "spec_id", "source_ref",
    "required", "content_sha256"
}
tracked_work_ids = set()
tracked_work_by_id = {}
artifact_work_state_by_ref = {}
artifact_work_children_by_ref = {}
for row in rows:
    assert isinstance(row["bead_ids"], list)
    assert len(set(row["bead_ids"])) == len(row["bead_ids"])
    assert all(isinstance(value, str) and value.strip() for value in row["bead_ids"])
    assert row["roadmap_ref"] is None or (
        isinstance(row["roadmap_ref"], str) and row["roadmap_ref"].strip()
    )
    assert isinstance(row["plan_refs"], list)
    assert len(set(row["plan_refs"])) == len(row["plan_refs"])
    assert all(isinstance(value, str) and value.strip() for value in row["plan_refs"])
    assert isinstance(row["tracked_work"], list)
    typed_sources = collections.Counter()
    required_sources = set()
    for work in row["tracked_work"]:
        assert isinstance(work, dict) and tracked_work_fields <= work.keys()
        work_ref_id = work["work_ref_id"]
        assert isinstance(work_ref_id, str) and work_ref_id.strip()
        assert work_ref_id not in tracked_work_ids
        tracked_work_ids.add(work_ref_id)
        tracked_work_by_id[work_ref_id] = work
        assert work["work_type"] in {"BEAD", "ROADMAP", "PLAN"}
        assert work["work_role"] in {
            "SPEC_EPIC", "SPEC_TASK", "PROGRAM_ROADMAP", "PHASE_PLAN",
            "IMPLEMENTATION_TASK", "OTHER_REQUIRED",
        }
        if work["work_role"] == "SPEC_TASK":
            assert re.fullmatch(r"S(?:0[1-9]|1\d|2[0-5])", work["spec_id"])
            assert work["work_type"] == "BEAD"
        else:
            assert work["spec_id"] is None
        if work["work_role"] == "SPEC_EPIC":
            assert work["work_type"] == "BEAD"
        if work["work_role"] == "PROGRAM_ROADMAP":
            assert work["work_type"] == "ROADMAP"
            assert work["source_ref"] == (
                "docs/workstreams/equity-os-blueprint-completion/roadmap.md"
            )
        assert isinstance(work["source_ref"], str) and work["source_ref"].strip()
        assert isinstance(work["required"], bool)
        key = (work["work_type"], work["source_ref"])
        typed_sources[key] += 1
        if work["required"]:
            required_sources.add(key)
        if work["work_type"] == "BEAD":
            assert work["content_sha256"] is None
        else:
            target = repo_path(work["source_ref"], must_exist=True)
            assert target.is_file()
            assert work["content_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
            marker_matches = re.findall(
                r"^<!-- equity-os-work-state: (\{.*\}) -->$",
                target.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
            assert len(marker_matches) == 1
            marker = json.loads(marker_matches[0])
            assert set(marker) == {
                "work_ref_id", "state", "required_work_ref_ids"
            }
            assert marker["work_ref_id"] == work_ref_id
            assert marker["state"] in {"DRAFT", "APPROVED", "ACTIVE", "COMPLETE"}
            assert isinstance(marker["required_work_ref_ids"], list)
            assert marker["required_work_ref_ids"] == sorted(
                set(marker["required_work_ref_ids"])
            )
            artifact_work_state_by_ref[work_ref_id] = marker["state"]
            artifact_work_children_by_ref[work_ref_id] = marker[
                "required_work_ref_ids"
            ]
    assert all(count == 1 for count in typed_sources.values())
    legacy_sources = {
        *(("BEAD", value) for value in row["bead_ids"]),
        *(("PLAN", value) for value in row["plan_refs"]),
    }
    if row["roadmap_ref"] is not None:
        legacy_sources.add(("ROADMAP", row["roadmap_ref"]))
    assert legacy_sources <= set(typed_sources)
    assert required_sources <= legacy_sources
assert all(
    set(child_ids) <= tracked_work_ids
    for child_ids in artifact_work_children_by_ref.values()
)
spec_task_sources = [
    work["source_ref"] for work in tracked_work_by_id.values()
    if work["work_role"] == "SPEC_TASK"
]
assert len(spec_task_sources) == len(set(spec_task_sources))

canonical_by_component_id = {
    row["component_id"]: row for row in canonical_rows
}
canonical_component_ids = set(canonical_by_component_id)
register_component_ids = {
    row["register_id"]: {row["component_id"]} for row in register_rows
}
register_owner_spec_by_id = {
    row["register_id"]: row["primary_spec"]["spec_id"] for row in register_rows
}
spec_component_ids = {
    spec_id: set() for spec_id in expected_spec_contract
}
bead_component_ids = collections.defaultdict(set)
for row in canonical_rows:
    component_id = row["component_id"]
    primary_spec = row["primary_spec"]
    if primary_spec is not None:
        spec_component_ids[primary_spec["spec_id"]].add(component_id)
    if row["kind"] != "register_row":
        for register_id in row["scope_derivation"]["related_register_ids"]:
            register_component_ids[register_id].add(component_id)
            spec_component_ids[register_owner_spec_by_id[register_id]].add(component_id)
    for bead_id in row["bead_ids"]:
        bead_component_ids[bead_id].add(component_id)
    for work in row["tracked_work"]:
        if work["work_type"] == "BEAD":
            bead_component_ids[work["source_ref"]].add(component_id)

validated_scope_bead_ids = set()

def validate_live_bead_id(bead_id):
    if bead_id in validated_scope_bead_ids:
        return
    completed = subprocess.run(
        ["bd", "--readonly", "show", "--json", bead_id],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0]["id"] == bead_id
    validated_scope_bead_ids.add(bead_id)

def normalize_human_scope(scope):
    direct_ids = set(scope["component_ids"])
    blocked_ids = set(scope["blocked_component_ids"])
    assert direct_ids <= set(by_id)
    assert blocked_ids <= set(by_id)
    assert direct_ids.isdisjoint(blocked_ids)

    register_ids = set(scope["register_ids"])
    assert register_ids <= set(register_component_ids)
    register_projection = set().union(
        *(register_component_ids[register_id] for register_id in register_ids)
    ) if register_ids else set()

    spec_ids = set(scope["spec_ids"])
    assert spec_ids <= set(spec_component_ids)
    spec_projection = set().union(
        *(spec_component_ids[spec_id] for spec_id in spec_ids)
    ) if spec_ids else set()

    bead_ids = set(scope["bead_ids"])
    assert bead_ids <= set(bead_component_ids)
    for bead_id in bead_ids:
        validate_live_bead_id(bead_id)
    bead_projection = set().union(
        *(bead_component_ids[bead_id] for bead_id in bead_ids)
    ) if bead_ids else set()

    nonblocked_projection = (
        direct_ids | register_projection | spec_projection | bead_projection
    )
    assert blocked_ids.isdisjoint(nonblocked_projection)
    projected = blocked_ids | nonblocked_projection
    assert projected
    assert projected <= set(by_id)
    return frozenset(projected)

approval_types = {
    "GOAL_OR_PROCESS_AUTHORIZATION",
    "DELEGATED_ARTIFACT_APPROVAL",
    "ANALYST_ACCEPTANCE",
    "DOMAIN_EXPERT_ACCEPTANCE",
    "PRODUCT_OWNER_DECISION",
    "MEMORY_PROMOTION",
    "PROVIDER_AUTHORIZATION",
    "DATA_RIGHTS_APPROVAL",
    "LEGAL_REVIEW",
    "REGULATORY_REVIEW",
    "BUDGET_APPROVAL",
    "CAPACITY_COMMITMENT",
    "NAMED_OWNER_COMMITMENT",
    "PRODUCTION_APPROVAL",
    "DISTRIBUTION_APPROVAL",
    "EXTERNAL_SERVICE_APPROVAL",
    "EXECUTION_TRUST_DOMAIN_APPROVAL",
    "SECURITY_EXCEPTION",
    "CREDENTIAL_ACCESS_APPROVAL",
    "PURCHASE_AUTHORIZATION",
    "EXTERNAL_COORDINATION_APPROVAL",
}

human_entries = {}
human_resolutions = {}
active_human_resolutions = {}
human_scope_components = {}

def validate_human_evidence(items, globally_seen_ids):
    assert isinstance(items, list)
    result = {}
    for evidence in items:
        assert isinstance(evidence, dict) and evidence_ref_fields <= evidence.keys()
        evidence_id = evidence["evidence_ref_id"]
        assert isinstance(evidence_id, str) and evidence_id.strip()
        assert evidence_id not in globally_seen_ids
        globally_seen_ids.add(evidence_id)
        target = repo_path(evidence["path"], must_exist=True)
        assert target not in {
            ledger_path.resolve(), human_review_path.resolve()
        }
        assert isinstance(evidence["scope"], str) and evidence["scope"].strip()
        assert parse_utc_rfc3339(evidence["captured_at"]) <= validation_now
        if evidence["digest_mode"] == "FILE_BYTES":
            assert evidence["start_line"] is None and evidence["end_line"] is None
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        else:
            assert evidence["digest_mode"] == "UTF8_LINE_SPAN"
            start, end = evidence["start_line"], evidence["end_line"]
            assert isinstance(start, int) and not isinstance(start, bool)
            assert isinstance(end, int) and not isinstance(end, bool)
            target_lines = target.read_text(encoding="utf-8").splitlines()
            normalized = resolve_utf8_line_span(
                evidence, target_lines, "HUMAN_REVIEW_PAYLOAD"
            )
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        assert evidence["content_sha256"] == digest
        result[evidence_id] = evidence
    return result

if True:
    human_text = human_review_path.read_text(encoding="utf-8")
    begin_marker = "<!-- BEGIN CANONICAL HUMAN REVIEW JSON -->"
    end_marker = "<!-- END CANONICAL HUMAN REVIEW JSON -->"
    assert human_text.count(begin_marker) == human_text.count(end_marker) == 1
    payload_text = human_text.split(begin_marker, 1)[1].split(end_marker, 1)[0].strip()
    if payload_text.startswith("```json") and payload_text.endswith("```"):
        payload_text = payload_text[len("```json"): -len("```")].strip()
    human_payload = json.loads(payload_text)
    assert set(human_payload) == {"schema_version", "entries", "resolutions"}
    assert human_payload["schema_version"] == 1
    assert isinstance(human_payload["entries"], list)
    assert isinstance(human_payload["resolutions"], list)
    human_evidence_ids = set()
    entry_fields = {
        "human_review_id", "entry_type", "scope", "question",
        "why_human_external", "recommendation", "safe_default", "evidence",
        "continuable_work", "decision_authority", "security_exception_detail",
        "blocking", "state", "resolution_decision_ids", "content_sha256",
    }
    scope_fields_human = {
        "component_ids", "register_ids", "spec_ids", "bead_ids",
        "blocked_component_ids", "scope_text",
    }
    entry_evidence_by_id = {}
    for entry in human_payload["entries"]:
        assert isinstance(entry, dict) and entry_fields <= entry.keys()
        entry_id = entry["human_review_id"]
        assert re.fullmatch(r"HR-\d{4}", entry_id)
        assert entry_id not in human_entries
        assert entry["entry_type"] in {"DECISION", "SECURITY_EXCEPTION"}
        assert isinstance(entry["scope"], dict)
        assert set(entry["scope"]) == scope_fields_human
        for field in (
            "component_ids", "register_ids", "spec_ids", "bead_ids",
            "blocked_component_ids",
        ):
            values = entry["scope"][field]
            assert isinstance(values, list) and values == sorted(set(values))
            assert all(isinstance(value, str) and value.strip() for value in values)
        assert isinstance(entry["scope"]["scope_text"], str)
        assert entry["scope"]["scope_text"].strip()
        human_scope_components[entry_id] = normalize_human_scope(entry["scope"])
        for field in (
            "question", "why_human_external", "recommendation", "safe_default",
        ):
            assert isinstance(entry[field], str) and entry[field].strip()
        assert isinstance(entry["continuable_work"], list)
        authority = entry["decision_authority"]
        assert set(authority) == {"approval_type", "authority", "competent_roles"}
        assert authority["approval_type"] in approval_types - {
            "DELEGATED_ARTIFACT_APPROVAL"
        }
        assert isinstance(authority["authority"], str) and authority["authority"].strip()
        assert isinstance(authority["competent_roles"], list)
        assert authority["competent_roles"]
        assert all(isinstance(role, str) and role.strip() for role in authority["competent_roles"])
        assert isinstance(entry["blocking"], bool)
        if entry["entry_type"] == "SECURITY_EXCEPTION":
            assert entry["blocking"] is True
            detail = entry["security_exception_detail"]
            assert isinstance(detail, dict)
            assert {
                "trust_boundary", "assets", "abuse_cases", "proposed_controls",
                "residual_risk", "security_tests",
            } <= detail.keys()
            assert isinstance(detail["trust_boundary"], str)
            assert detail["trust_boundary"].strip()
            assert isinstance(detail["residual_risk"], str)
            assert detail["residual_risk"].strip()
            for field in (
                "assets", "abuse_cases", "proposed_controls", "security_tests"
            ):
                assert isinstance(detail[field], list) and detail[field]
                assert all(
                    isinstance(value, str) and value.strip()
                    for value in detail[field]
                )
        else:
            assert entry["security_exception_detail"] is None
        assert isinstance(entry["resolution_decision_ids"], list)
        assert len(set(entry["resolution_decision_ids"])) == len(
            entry["resolution_decision_ids"]
        )
        entry_projection = {
            key: value for key, value in entry.items() if key != "content_sha256"
        }
        assert entry["content_sha256"] == canonical_sha256(entry_projection)
        local = validate_human_evidence(entry["evidence"], human_evidence_ids)
        entry_evidence_by_id[entry_id] = local
        human_entries[entry_id] = entry

    resolution_fields = {
        "decision_id", "sequence", "record_type", "human_review_id",
        "decision_type", "actor", "scope", "authority_basis", "timestamp",
        "evidence", "supersedes_decision_id", "revokes_decision_id",
        "entry_authority_sha256", "previous_resolution_sha256", "content_sha256",
    }
    decision_types = {
        "ACTIVATE_DEFERRED", "REJECT_COMPONENT", "REOPEN_ACCEPTED",
        "RECONCILE_AUTHORITY", "APPROVE_SECURITY_EXCEPTION",
        "DENY_SECURITY_EXCEPTION", "SATISFY_APPROVAL", "DENY_APPROVAL",
        "EXPIRE_APPROVAL",
    }
    active_by_entry = collections.defaultdict(set)
    all_by_entry = collections.defaultdict(list)
    previous_hash = None
    previous_resolution_time = None
    for expected_sequence, resolution in enumerate(human_payload["resolutions"]):
        assert isinstance(resolution, dict) and resolution_fields <= resolution.keys()
        decision_id = resolution["decision_id"]
        assert isinstance(decision_id, str) and decision_id.strip()
        assert decision_id not in human_resolutions
        assert resolution["sequence"] == expected_sequence
        assert resolution["previous_resolution_sha256"] == previous_hash
        projection = {
            key: value for key, value in resolution.items()
            if key != "content_sha256"
        }
        assert resolution["content_sha256"] == canonical_sha256(projection)
        previous_hash = resolution["content_sha256"]
        entry_id = resolution["human_review_id"]
        assert entry_id in human_entries
        entry = human_entries[entry_id]
        entry_authority_projection = {
            key: value for key, value in entry.items()
            if key not in {"state", "resolution_decision_ids", "content_sha256"}
        }
        assert resolution["entry_authority_sha256"] == canonical_sha256(
            entry_authority_projection
        )
        assert resolution["scope"] == entry["scope"]
        actor = resolution["actor"]
        assert set(actor) == {"identity_id", "display_name", "role", "actor_type"}
        assert actor["actor_type"] == "HUMAN"
        assert all(
            isinstance(actor[field], str) and actor[field].strip()
            for field in ("identity_id", "display_name", "role")
        )
        basis = resolution["authority_basis"]
        assert set(basis) == {"approval_type", "authority", "role", "evidence_ids"}
        entry_authority = entry["decision_authority"]
        assert basis["approval_type"] == entry_authority["approval_type"]
        assert basis["authority"] == entry_authority["authority"]
        assert basis["role"] == actor["role"]
        assert actor["role"] in entry_authority["competent_roles"]
        resolution_evidence = validate_human_evidence(
            resolution["evidence"], human_evidence_ids
        )
        available_authority_evidence = {
            **entry_evidence_by_id[entry_id], **resolution_evidence
        }
        assert isinstance(basis["evidence_ids"], list) and basis["evidence_ids"]
        assert set(basis["evidence_ids"]) <= set(available_authority_evidence)
        resolution_time = parse_utc_rfc3339(resolution["timestamp"])
        assert resolution_time <= validation_now
        if previous_resolution_time is not None:
            assert resolution_time >= previous_resolution_time
        previous_resolution_time = resolution_time
        assert all(
            resolution_time >= parse_utc_rfc3339(
                available_authority_evidence[evidence_id]["captured_at"]
            )
            for evidence_id in basis["evidence_ids"]
        )
        if resolution["record_type"] == "DECISION":
            assert resolution["decision_type"] in decision_types
            assert resolution["revokes_decision_id"] is None
            superseded = resolution["supersedes_decision_id"]
            if superseded is None:
                assert not active_by_entry[entry_id]
            else:
                assert superseded in active_by_entry[entry_id]
                active_by_entry[entry_id].remove(superseded)
            if entry["entry_type"] == "SECURITY_EXCEPTION":
                assert resolution["decision_type"] in {
                    "APPROVE_SECURITY_EXCEPTION", "DENY_SECURITY_EXCEPTION"
                }
            else:
                assert resolution["decision_type"] not in {
                    "APPROVE_SECURITY_EXCEPTION", "DENY_SECURITY_EXCEPTION"
                }
            active_by_entry[entry_id].add(decision_id)
        else:
            assert resolution["record_type"] == "REVOCATION"
            assert resolution["decision_type"] == "REVOKE"
            assert resolution["supersedes_decision_id"] is None
            revoked = resolution["revokes_decision_id"]
            assert revoked in active_by_entry[entry_id]
            active_by_entry[entry_id].remove(revoked)
        all_by_entry[entry_id].append(decision_id)
        human_resolutions[decision_id] = resolution

    for entry_id, entry in human_entries.items():
        active_ids = active_by_entry[entry_id]
        assert len(active_ids) <= 1
        expected_state = (
            "RESOLVED" if active_ids
            else "INVALIDATED" if all_by_entry[entry_id]
            else "OPEN_BLOCKING" if entry["blocking"]
            else "OPEN_NONBLOCKING"
        )
        assert entry["state"] == expected_state
        assert entry["resolution_decision_ids"] == all_by_entry[entry_id]
        for decision_id in active_ids:
            active_human_resolutions[decision_id] = human_resolutions[decision_id]

def canonical_resolution(decision_id, content_sha256, *, purposes, active=True):
    source = active_human_resolutions if active else human_resolutions
    assert isinstance(decision_id, str) and decision_id in source
    resolution = source[decision_id]
    assert resolution["content_sha256"] == content_sha256
    assert resolution["decision_type"] in purposes
    assert resolution["actor"]["actor_type"] == "HUMAN"
    return resolution

requirement_states = {"UNRESOLVED", "SATISFIED", "DENIED", "REVOKED", "EXPIRED"}
decision_for_state = {
    "SATISFIED": "APPROVED",
    "DENIED": "DENIED",
    "REVOKED": "REVOKED",
    "EXPIRED": "EXPIRED",
}
requirement_fields = {
    "approval_id", "approval_type", "required_authority", "scope", "status",
    "actor", "timestamp", "evidence_ref_ids", "matched_record_id",
}
record_fields = {
    "approval_record_id", "approval_type", "authority", "scope", "decision",
    "actor", "timestamp", "evidence_ref_ids", "authority_source",
    "human_review_id", "resolution_decision_id", "resolution_content_sha256",
}

records_by_id = {}
approval_resolution_ids = set()
for row in rows:
    assert isinstance(row["required_approvals"], list)
    assert isinstance(row["approval_records"], list)
    if row["kind"] != alias_kind:
        validate_inventory_review(row, row["approval_inventory_review"], "APPROVAL")
    for record in row["approval_records"]:
        assert record_fields <= record.keys()
        record_id = record["approval_record_id"]
        assert isinstance(record_id, str) and record_id.strip()
        assert record_id not in records_by_id
        assert record["approval_type"] in approval_types
        assert record["decision"] in set(decision_for_state.values())
        assert isinstance(record["authority"], str) and record["authority"].strip()
        assert isinstance(record["scope"], str) and record["scope"].strip()
        assert isinstance(record["actor"], str) and record["actor"].strip()
        assert parse_utc_rfc3339(record["timestamp"]) <= validation_now
        assert isinstance(record["evidence_ref_ids"], list)
        assert record["evidence_ref_ids"]
        assert set(record["evidence_ref_ids"]) <= local_evidence_ids[row["component_id"]]
        assert record["authority_source"] in {
            "DELEGATED_AUTOMATED", "HUMAN_RESOLUTION"
        }
        if record["authority_source"] == "DELEGATED_AUTOMATED":
            assert record["approval_type"] == "DELEGATED_ARTIFACT_APPROVAL"
            assert record["decision"] == "APPROVED"
            assert record["human_review_id"] is None
            assert record["resolution_decision_id"] is None
            assert record["resolution_content_sha256"] is None
        else:
            assert record["approval_type"] != "DELEGATED_ARTIFACT_APPROVAL"
            purposes_by_decision = {
                "APPROVED": {
                    "ACTIVATE_DEFERRED", "REJECT_COMPONENT", "REOPEN_ACCEPTED",
                    "RECONCILE_AUTHORITY", "APPROVE_SECURITY_EXCEPTION",
                    "SATISFY_APPROVAL",
                },
                "DENIED": {"DENY_SECURITY_EXCEPTION", "DENY_APPROVAL"},
                "REVOKED": {"REVOKE"},
                "EXPIRED": {"EXPIRE_APPROVAL"},
            }
            resolution = canonical_resolution(
                record["resolution_decision_id"],
                record["resolution_content_sha256"],
                purposes=purposes_by_decision[record["decision"]],
                active=record["decision"] not in {"REVOKED"},
            )
            resolution_id = resolution["decision_id"]
            assert resolution_id not in approval_resolution_ids
            approval_resolution_ids.add(resolution_id)
            assert record["human_review_id"] == resolution["human_review_id"]
            assert record["approval_type"] == resolution["authority_basis"]["approval_type"]
            assert record["authority"] == resolution["authority_basis"]["authority"]
            assert record["scope"] == resolution["scope"]["scope_text"]
            assert record["actor"] == resolution["actor"]["identity_id"]
            assert record["timestamp"] == resolution["timestamp"]
        records_by_id[record_id] = record

human_review_links = {
    row["component_id"]: normalized_human_review_id(row["human_review_id"])
    for row in rows
}
for row in rows:
    if row["kind"] == alias_kind:
        assert row["human_review_id"] is None
    for entry_id in human_review_links[row["component_id"]]:
        assert entry_id in human_entries
        assert human_entries[entry_id]["entry_type"] == "DECISION"
        assert row["component_id"] in human_scope_components[entry_id]
    assert isinstance(row["security_exception_ids"], list)
    assert len(set(row["security_exception_ids"])) == len(row["security_exception_ids"])
    for entry_id in row["security_exception_ids"]:
        assert entry_id in human_entries
        assert human_entries[entry_id]["entry_type"] == "SECURITY_EXCEPTION"
        assert row["component_id"] in human_scope_components[entry_id]

for entry_id, entry in human_entries.items():
    scoped_component_ids = human_scope_components[entry_id]
    if entry["entry_type"] == "DECISION":
        assert all(
            entry_id in human_review_links[component_id]
            for component_id in scoped_component_ids
            if component_id in canonical_by_component_id
        )
    else:
        assert entry["entry_type"] == "SECURITY_EXCEPTION"
        assert all(
            entry_id in canonical_by_component_id[component_id]["security_exception_ids"]
            for component_id in scoped_component_ids
            if component_id in canonical_by_component_id
        )

requirements_by_id = {}
matched_record_ids = set()
for row in rows:
    local_record_ids = {
        record["approval_record_id"] for record in row["approval_records"]
    }
    for requirement in row["required_approvals"]:
        assert requirement_fields <= requirement.keys()
        approval_id = requirement["approval_id"]
        assert isinstance(approval_id, str) and approval_id.strip()
        assert approval_id not in requirements_by_id
        requirements_by_id[approval_id] = requirement
        assert requirement["approval_type"] in approval_types
        assert requirement["status"] in requirement_states
        assert isinstance(requirement["required_authority"], str)
        assert requirement["required_authority"].strip()
        assert isinstance(requirement["scope"], str) and requirement["scope"].strip()

        if requirement["status"] == "UNRESOLVED":
            assert requirement["actor"] is None
            assert requirement["timestamp"] is None
            assert requirement["evidence_ref_ids"] == []
            assert requirement["matched_record_id"] is None
            continue

        record_id = requirement["matched_record_id"]
        assert isinstance(record_id, str) and record_id in local_record_ids
        assert record_id not in matched_record_ids
        matched_record_ids.add(record_id)
        record = records_by_id[record_id]
        assert record["decision"] == decision_for_state[requirement["status"]]
        assert record["approval_type"] == requirement["approval_type"]
        assert record["authority"] == requirement["required_authority"]
        assert record["scope"] == requirement["scope"]
        assert record["actor"] == requirement["actor"]
        assert record["timestamp"] == requirement["timestamp"]
        assert record["evidence_ref_ids"] == requirement["evidence_ref_ids"]

metric_fields = {
    "metric_id", "value_type", "source_kind", "evidence_ref_id",
    "json_pointer", "register_ids", "valid_until",
}
predicate_fields = {
    "predicate_id", "expression", "metrics", "result", "evaluated_at",
    "evaluation_sha256",
}

def typed_metric_value(value, value_type):
    if value_type == "BOOLEAN":
        assert isinstance(value, bool)
    elif value_type == "INTEGER":
        assert isinstance(value, int) and not isinstance(value, bool)
    elif value_type == "NUMBER":
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        assert math.isfinite(value)
    else:
        assert value_type == "STRING"
        assert isinstance(value, str)
    return value

def json_pointer(document, pointer):
    assert isinstance(pointer, str) and pointer.startswith("/")
    current = document
    for raw_token in pointer.split("/")[1:]:
        assert not re.search(r"~(?![01])", raw_token)
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            assert re.fullmatch(r"0|[1-9]\d*", token)
            current = current[int(token)]
        else:
            assert isinstance(current, dict) and token in current
            current = current[token]
    return current

def compare_metric(actual, comparator, expected, value_type):
    if comparator == "IN":
        assert isinstance(expected, list) and expected
        expected_values = [typed_metric_value(value, value_type) for value in expected]
        return actual in expected_values
    typed_metric_value(expected, value_type)
    if value_type in {"BOOLEAN", "STRING"}:
        assert comparator in {"EQ", "NE"}
    else:
        assert comparator in {"EQ", "NE", "GT", "GTE", "LT", "LTE"}
    if comparator == "EQ":
        return actual == expected
    if comparator == "NE":
        return actual != expected
    if comparator == "GT":
        return actual > expected
    if comparator == "GTE":
        return actual >= expected
    if comparator == "LT":
        return actual < expected
    assert comparator == "LTE"
    return actual <= expected

predicate_results_by_component = {}
predicate_digest_by_component = {}
predicate_evidence_by_component = {}
predicate_all_resolved_by_component = {}
now_utc = datetime.datetime.now(datetime.timezone.utc)
for row in canonical_rows:
    predicate = row["activation_predicate"]
    if predicate is None:
        continue
    assert isinstance(predicate, dict) and predicate_fields <= predicate.keys()
    assert re.fullmatch(
        r"AP-[A-Z0-9][A-Z0-9_-]{2,63}", predicate["predicate_id"]
    )
    assert isinstance(predicate["metrics"], list) and predicate["metrics"]
    metric_values = {}
    metric_types = {}
    digest_sources = {}
    predicate_evidence_ids = set()
    evidence_capture_times = []
    all_current = True
    for metric in predicate["metrics"]:
        assert isinstance(metric, dict) and metric_fields <= metric.keys()
        metric_id = metric["metric_id"]
        assert re.fullmatch(r"MTR-[A-Z0-9][A-Z0-9_-]{2,63}", metric_id)
        assert metric_id not in metric_values
        assert metric["value_type"] in {"BOOLEAN", "INTEGER", "NUMBER", "STRING"}
        metric_types[metric_id] = metric["value_type"]
        if metric["valid_until"] is not None:
            valid_until = parse_utc_rfc3339(metric["valid_until"])
            all_current = all_current and now_utc <= valid_until
        if metric["source_kind"] == "EVIDENCE_JSON":
            assert metric["register_ids"] == []
            assert isinstance(metric["json_pointer"], str)
            assert metric["json_pointer"].startswith("/")
            evidence_ref_id = metric["evidence_ref_id"]
            if evidence_ref_id is None:
                metric_values[metric_id] = None
                digest_sources[metric_id] = None
                continue
            assert evidence_ref_id in local_evidence_ids[row["component_id"]]
            evidence = evidence_by_id[evidence_ref_id]
            assert evidence["digest_mode"] == "FILE_BYTES"
            target = repo_path(evidence["path"], must_exist=True)
            document = json.loads(target.read_text(encoding="utf-8"))
            value = json_pointer(document, metric["json_pointer"])
            metric_values[metric_id] = typed_metric_value(value, metric["value_type"])
            digest_sources[metric_id] = evidence["content_sha256"]
            predicate_evidence_ids.add(evidence_ref_id)
            evidence_capture_times.append(parse_utc_rfc3339(evidence["captured_at"]))
        else:
            assert metric["source_kind"] == "REGISTER_STATUS"
            assert metric["value_type"] == "BOOLEAN"
            assert metric["evidence_ref_id"] is None
            assert metric["json_pointer"] is None
            assert isinstance(metric["register_ids"], list) and metric["register_ids"]
            assert len(set(metric["register_ids"])) == len(metric["register_ids"])
            assert set(metric["register_ids"]) <= expected_ids
            value = any(
                register_authority[register_id]["source_status"]
                in {"Open", "In progress", "Accepted"}
                for register_id in metric["register_ids"]
            )
            metric_values[metric_id] = value
            digest_sources[metric_id] = current_source_hashes[
                "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
            ]

    def evaluate(expression):
        assert isinstance(expression, dict) and isinstance(expression.get("op"), str)
        op = expression["op"]
        if op in {"ALL", "ANY"}:
            assert set(expression) == {"op", "args"}
            assert isinstance(expression["args"], list) and expression["args"]
            values = [evaluate(item) for item in expression["args"]]
            if op == "ALL":
                return False if False in values else None if None in values else True
            return True if True in values else None if None in values else False
        if op == "NOT":
            assert set(expression) == {"op", "arg"}
            value = evaluate(expression["arg"])
            return None if value is None else not value
        if op == "COMPARE_METRICS":
            assert set(expression) == {
                "op", "left_metric_id", "comparator", "right_metric_id"
            }
            left_id = expression["left_metric_id"]
            right_id = expression["right_metric_id"]
            assert left_id in metric_values and right_id in metric_values
            assert metric_types[left_id] == metric_types[right_id]
            comparator = expression["comparator"]
            if metric_types[left_id] in {"BOOLEAN", "STRING"}:
                assert comparator in {"EQ", "NE"}
            else:
                assert comparator in {"EQ", "NE", "GT", "GTE", "LT", "LTE"}
            left_value = metric_values[left_id]
            right_value = metric_values[right_id]
            if left_value is None or right_value is None:
                return None
            return compare_metric(
                left_value, comparator, right_value, metric_types[left_id]
            )
        assert op == "COMPARE" and set(expression) == {
            "op", "metric_id", "comparator", "expected"
        }
        metric_id = expression["metric_id"]
        assert metric_id in metric_values
        actual = metric_values[metric_id]
        if actual is None:
            return None
        return compare_metric(
            actual, expression["comparator"], expression["expected"],
            metric_types[metric_id],
        )

    evaluated = evaluate(predicate["expression"])
    result = {True: "TRUE", False: "FALSE", None: "UNKNOWN"}[evaluated]
    assert predicate["result"] == result
    all_resolved = all(value is not None for value in metric_values.values())
    if result == "UNKNOWN":
        assert predicate["evaluated_at"] is None
        assert predicate["evaluation_sha256"] is None
    else:
        evaluated_at = parse_utc_rfc3339(predicate["evaluated_at"])
        assert evaluated_at <= validation_now
        assert all(evaluated_at >= captured for captured in evidence_capture_times)
        assert all_current
        digest_input = {
            "predicate_id": predicate["predicate_id"],
            "expression": predicate["expression"],
            "metrics": predicate["metrics"],
            "resolved_values": metric_values,
            "digest_sources": digest_sources,
            "result": result,
            "evaluated_at": predicate["evaluated_at"],
        }
        assert predicate["evaluation_sha256"] == canonical_sha256(digest_input)
    predicate_results_by_component[row["component_id"]] = result
    predicate_digest_by_component[row["component_id"]] = predicate["evaluation_sha256"]
    predicate_evidence_by_component[row["component_id"]] = predicate_evidence_ids
    predicate_all_resolved_by_component[row["component_id"]] = all_resolved

register_by_id = {row["register_id"]: row for row in register_rows}
active_source_statuses = {"Open", "In progress", "Accepted"}

def derive_register_disposition(row):
    initial = row["activation_source_status"]
    current = row["source_status"]
    if current == "Rejected":
        return "REJECTED_ACCOUNTED"
    if initial in active_source_statuses:
        assert current in active_source_statuses
        return "REQUIRED_NOW"
    if initial == "Deferred":
        if current == "Deferred":
            return "CONDITIONAL_UNACTIVATED"
        assert current in active_source_statuses
        return "CONDITIONAL_ACTIVATED"
    assert initial == "Rejected" and current == "Rejected"
    return "REJECTED_ACCOUNTED"

register_dispositions = {
    row["register_id"]: derive_register_disposition(row) for row in register_rows
}

def aggregate_related(register_ids):
    assert isinstance(register_ids, list) and register_ids
    assert len(set(register_ids)) == len(register_ids)
    assert set(register_ids) <= expected_ids
    dispositions = {register_dispositions[item] for item in register_ids}
    if "REQUIRED_NOW" in dispositions:
        return "REQUIRED_NOW"
    if "CONDITIONAL_ACTIVATED" in dispositions:
        return "CONDITIONAL_ACTIVATED"
    if "CONDITIONAL_UNACTIVATED" in dispositions:
        return "CONDITIONAL_UNACTIVATED"
    assert dispositions == {"REJECTED_ACCOUNTED"}
    return "REJECTED_ACCOUNTED"

scope_fields = {
    "rule", "related_register_ids", "authority_effect",
    "derived_program_disposition", "semantic_review",
}
extra_scope_keys_by_kind = {
    "disposition_item": {"applicable_spec_ids"},
    "sequence_clause": {"source_register_ids", "applicable_spec_ids"},
}
spec_id_pattern = r"S(?:0[1-9]|1\d|2[0-5])"
required_rule_by_kind = {
    "phase_gate_clause": "RELATED_REGISTER_SCOPE",
    "first_release_deferral": "PROGRAM_WIDE_ACTIVE_CONTROL",
    "scale_trigger": "PROGRAM_WIDE_ACTIVE_CONTROL",
    "disposition_item": "AUTHORITATIVE_OCCURRENCE",
    "authority_clause": "PROGRAM_WIDE_ACTIVE_CONTROL",
    "sequence_clause": "PROGRAM_WIDE_ACTIVE_CONTROL",
    "document_strategy_clause": "PROGRAM_WIDE_ACTIVE_CONTROL",
}
derived_by_component_id = {}
for row in canonical_rows:
    derivation = row["scope_derivation"]
    assert isinstance(derivation, dict) and scope_fields <= derivation.keys()
    allowed_extra = extra_scope_keys_by_kind.get(row["kind"], set())
    assert set(derivation) == scope_fields | allowed_extra
    for key in allowed_extra:
        values = derivation[key]
        assert isinstance(values, list) and values == sorted(set(values))
        if key == "applicable_spec_ids":
            assert all(re.fullmatch(spec_id_pattern, item) for item in values)
        else:
            assert set(values) <= expected_ids
    if row["kind"] == "register_row":
        assert derivation["rule"] == "REGISTER_STATUS"
        assert derivation["related_register_ids"] == []
        assert derivation["authority_effect"] is None
        assert derivation["semantic_review"] is None
        derived = register_dispositions[row["register_id"]]
    else:
        if derivation["rule"] == "ACTIVE_NEGATIVE_CONTROL":
            assert row["kind"] == "phase_gate_clause"
        else:
            assert derivation["rule"] == required_rule_by_kind[row["kind"]]
        validate_inventory_review(row, derivation["semantic_review"], "SCOPE")
        related = derivation["related_register_ids"]
        if derivation["rule"] == "ACTIVE_NEGATIVE_CONTROL":
            assert related and len(set(related)) == len(related)
            assert set(related) <= expected_ids
            assert derivation["authority_effect"] is None
            assert row["activation_predicate"] is None
            derived = "REQUIRED_NOW"
        elif derivation["rule"] == "PROGRAM_WIDE_ACTIVE_CONTROL":
            assert related == [] and derivation["authority_effect"] is None
            derived = "REQUIRED_NOW"
        elif derivation["rule"] == "RELATED_REGISTER_SCOPE":
            assert derivation["authority_effect"] is None
            derived = aggregate_related(related)
        else:
            effect = derivation["authority_effect"]
            assert effect in {
                "ACTIVE_CONTROL", "REJECTED_PROPOSAL", "FOLLOW_RELATED_SCOPE"
            }
            if effect == "ACTIVE_CONTROL":
                derived = "REQUIRED_NOW"
            elif effect == "REJECTED_PROPOSAL":
                derived = "REJECTED_ACCOUNTED"
            else:
                derived = aggregate_related(related)
    assert derivation["derived_program_disposition"] == derived
    assert row["program_disposition"] == derived
    derived_by_component_id[row["component_id"]] = derived

for row in canonical_rows:
    component_id = row["component_id"]
    was_conditional_register = (
        row["kind"] == "register_row"
        and row["activation_source_status"] == "Deferred"
    )
    currently_conditional = derived_by_component_id[component_id] in {
        "CONDITIONAL_UNACTIVATED", "CONDITIONAL_ACTIVATED"
    }
    if was_conditional_register or currently_conditional:
        assert row["activation_predicate"] is not None
        assert component_id in predicate_results_by_component
    elif row["activation_predicate"] is not None:
        assert derived_by_component_id[component_id] == "REJECTED_ACCOUNTED"
    if derived_by_component_id[component_id] == "CONDITIONAL_ACTIVATED":
        assert predicate_results_by_component[component_id] == "TRUE"
        assert predicate_all_resolved_by_component[component_id]

activation_record_fields = {
    "activation_record_id", "decision", "component_id", "register_id", "scope",
    "activation_predicate_id", "activation_predicate_sha256", "authority",
    "actor", "timestamp", "evidence_ref_ids", "predicate_evidence_ref_ids",
    "approval_record_id", "human_resolution_decision_id",
    "human_resolution_sha256",
}
rejection_record_fields = {
    "rejection_record_id", "component_id", "register_id", "scope", "authority",
    "actor", "timestamp", "evidence_ref_ids", "rationale",
    "no_implementation_evidence_ref_ids", "approval_record_id",
    "human_resolution_decision_id", "human_resolution_sha256",
}
decision_approval_types = {
    "GOAL_OR_PROCESS_AUTHORIZATION", "PRODUCT_OWNER_DECISION"
}

def validate_decision_approval(row, record_id, *, record_evidence_ids, purpose):
    local_records = {
        record["approval_record_id"]: record for record in row["approval_records"]
    }
    assert isinstance(record_id, str) and record_id in local_records
    assert record_id in matched_record_ids
    record = local_records[record_id]
    assert record["decision"] == "APPROVED"
    assert record["approval_type"] in decision_approval_types
    assert record["authority_source"] == "HUMAN_RESOLUTION"
    assert set(record["evidence_ref_ids"]) <= set(record_evidence_ids)
    resolution = canonical_resolution(
        record["resolution_decision_id"], record["resolution_content_sha256"],
        purposes={purpose}, active=True,
    )
    return record, resolution

for row in canonical_rows:
    local_ids = local_evidence_ids[row["component_id"]]
    activation_record = row["activation_record"]
    activation_required = (
        row["kind"] == "register_row"
        and row["activation_source_status"] == "Deferred"
        and row["source_status"] in active_source_statuses
    )
    if activation_record is None:
        assert not activation_required
    else:
        assert row["kind"] == "register_row"
        assert row["activation_source_status"] == "Deferred"
        assert row["source_status"] != "Deferred"
        assert activation_record_fields <= activation_record.keys()
        assert activation_record["decision"] == "ACTIVATE_DEFERRED"
        assert activation_record["component_id"] == row["component_id"]
        assert activation_record["register_id"] == row["register_id"]
        predicate = row["activation_predicate"]
        assert activation_record["activation_predicate_id"] == predicate["predicate_id"]
        assert activation_record["activation_predicate_sha256"] == (
            predicate_digest_by_component[row["component_id"]]
        )
        assert predicate_results_by_component[row["component_id"]] == "TRUE"
        assert predicate_all_resolved_by_component[row["component_id"]]
        assert isinstance(activation_record["scope"], str)
        assert activation_record["scope"].strip()
        assert isinstance(activation_record["authority"], str)
        assert activation_record["authority"].strip()
        assert isinstance(activation_record["actor"], str)
        assert activation_record["actor"].strip()
        assert parse_utc_rfc3339(activation_record["timestamp"]) <= validation_now
        assert set(activation_record["evidence_ref_ids"]) <= local_ids
        assert activation_record["evidence_ref_ids"]
        assert set(activation_record["predicate_evidence_ref_ids"]) == (
            predicate_evidence_by_component[row["component_id"]]
        )
        assert set(activation_record["predicate_evidence_ref_ids"]) <= set(
            activation_record["evidence_ref_ids"]
        )
        record, resolution = validate_decision_approval(
            row,
            activation_record["approval_record_id"],
            record_evidence_ids=activation_record["evidence_ref_ids"],
            purpose="ACTIVATE_DEFERRED",
        )
        assert activation_record["human_resolution_decision_id"] == resolution["decision_id"]
        assert activation_record["human_resolution_sha256"] == resolution["content_sha256"]
        assert record["resolution_decision_id"] == resolution["decision_id"]
        assert record["evidence_ref_ids"] == activation_record["evidence_ref_ids"]
        for field in ("authority", "actor", "scope", "timestamp"):
            assert record[field] == activation_record[field]
        assert activation_record["authority"] == resolution["authority_basis"]["authority"]
        assert activation_record["actor"] == resolution["actor"]["identity_id"]
        assert activation_record["scope"] == resolution["scope"]["scope_text"]
        assert activation_record["timestamp"] == resolution["timestamp"]

    rejection_record = row["rejection_record"]
    rejected = derived_by_component_id[row["component_id"]] == "REJECTED_ACCOUNTED"
    assert (rejection_record is not None) == rejected
    if rejected:
        assert rejection_record_fields <= rejection_record.keys()
        assert rejection_record["component_id"] == row["component_id"]
        assert rejection_record["register_id"] == row["register_id"]
        for field in ("scope", "authority", "actor", "rationale"):
            assert isinstance(rejection_record[field], str)
            assert rejection_record[field].strip()
        assert parse_utc_rfc3339(rejection_record["timestamp"]) <= validation_now
        assert set(rejection_record["evidence_ref_ids"]) <= local_ids
        assert rejection_record["evidence_ref_ids"]
        assert set(rejection_record["no_implementation_evidence_ref_ids"]) <= set(
            rejection_record["evidence_ref_ids"]
        )
        assert rejection_record["no_implementation_evidence_ref_ids"]
        if row["kind"] == "register_row":
            assert row["source_status"] == "Rejected"
            record, resolution = validate_decision_approval(
                row,
                rejection_record["approval_record_id"],
                record_evidence_ids=rejection_record["evidence_ref_ids"],
                purpose="REJECT_COMPONENT",
            )
            assert rejection_record["human_resolution_decision_id"] == resolution["decision_id"]
            assert rejection_record["human_resolution_sha256"] == resolution["content_sha256"]
            assert record["resolution_decision_id"] == resolution["decision_id"]
            assert record["evidence_ref_ids"] == rejection_record["evidence_ref_ids"]
            for field in ("authority", "actor", "scope", "timestamp"):
                assert record[field] == rejection_record[field]
            assert rejection_record["authority"] == resolution["authority_basis"]["authority"]
            assert rejection_record["actor"] == resolution["actor"]["identity_id"]
            assert rejection_record["scope"] == resolution["scope"]["scope_text"]
            assert rejection_record["timestamp"] == resolution["timestamp"]
        else:
            derivation = row["scope_derivation"]
            assert (
                derivation["rule"] == "RELATED_REGISTER_SCOPE"
                or (
                    derivation["rule"] == "AUTHORITATIVE_OCCURRENCE"
                    and derivation["authority_effect"]
                    in {"REJECTED_PROPOSAL", "FOLLOW_RELATED_SCOPE"}
                )
            )
            assert rejection_record["approval_record_id"] is None
            assert rejection_record["human_resolution_decision_id"] is None
            assert rejection_record["human_resolution_sha256"] is None
        assert row["implementation_refs"] == []
        assert row["delivery_status"] not in {"PLANNED", "IMPLEMENTING", "VERIFIED"}

    if derived_by_component_id[row["component_id"]] == "CONDITIONAL_UNACTIVATED":
        assert row["implementation_refs"] == []
        assert row["delivery_status"] not in {"PLANNED", "IMPLEMENTING", "VERIFIED"}

controlled_direct_fields = {
    "component_id", "canonical_component_id", "kind", "source_path",
    "source_anchor", "source_start_line", "source_end_line", "source_hash",
    "text_digest", "authority_rank", "register_id", "source_title",
    "required_acceptance_text", "blueprint_phase", "priority",
    "activation_source_status", "source_status", "dependencies", "primary_spec",
    "disposition_refs", "gate_refs", "activation_predicate", "activation_record",
    "rejection_record", "program_disposition", "delivery_status", "gate_result",
    "bead_ids", "roadmap_ref", "plan_refs", "implementation_refs", "tracked_work",
    "human_review_id", "security_exception_ids", "blocked_scope",
}
controlled_fields = controlled_direct_fields | {"scope_definition"}
transition_fields = {
    "transition_id", "sequence", "transition_type", "field", "actor",
    "invoked_model", "timestamp", "old_value", "new_value",
    "evidence_ref_ids", "human_resolution_decision_id",
    "human_resolution_sha256", "previous_entry_sha256", "entry_sha256",
}
transition_types = {
    "ACTIVATION_SNAPSHOT", "STATE_TRANSITION", "AUTHORITY_RECONCILIATION",
    "STATUS_SOURCE_RECONCILIATION", "BLOCK", "UNBLOCK", "REFERENCE_APPEND",
}
blocked_delivery_states = {
    "REVIEW_BLOCKED", "VERIFICATION_BLOCKED", "EXTERNAL_EVIDENCE_BLOCKED"
}
delivery_progression = [
    "INVENTORIED", "SPEC_DRAFT", "SPEC_APPROVED_DELEGATED", "PLANNED",
    "IMPLEMENTING", "VERIFIED",
]

def controlled_state(row):
    state = {field: row[field] for field in controlled_direct_fields}
    scope = row["scope_derivation"]
    state["scope_definition"] = None if scope is None else {
        "rule": scope["rule"],
        "related_register_ids": scope["related_register_ids"],
        "authority_effect": scope["authority_effect"],
    }
    return state

def transition_resolution(entry, row, purposes):
    resolution = canonical_resolution(
        entry["human_resolution_decision_id"],
        entry["human_resolution_sha256"], purposes=purposes, active=True,
    )
    entry_id = resolution["human_review_id"]
    assert resolution["scope"] == human_entries[entry_id]["scope"]
    assert row["component_id"] in human_scope_components[entry_id]
    return resolution

activation_register_dispositions = {
    row["register_id"]: (
        "CONDITIONAL_UNACTIVATED"
        if row["activation_source_status"] == "Deferred"
        else "REQUIRED_NOW"
    )
    for row in register_rows
}

def activation_aggregate(register_ids):
    values = {activation_register_dispositions[item] for item in register_ids}
    return (
        "REQUIRED_NOW" if "REQUIRED_NOW" in values
        else "CONDITIONAL_UNACTIVATED"
    )

def activation_snapshot_disposition(state):
    if state["kind"] == alias_kind:
        return "DERIVATIVE_ALIAS"
    if state["kind"] == "register_row":
        return activation_register_dispositions[state["register_id"]]
    scope = state["scope_definition"]
    if scope["rule"] == "PROGRAM_WIDE_ACTIVE_CONTROL":
        return "REQUIRED_NOW"
    if scope["rule"] == "RELATED_REGISTER_SCOPE":
        return activation_aggregate(scope["related_register_ids"])
    assert scope["rule"] == "AUTHORITATIVE_OCCURRENCE"
    if scope["authority_effect"] == "ACTIVE_CONTROL":
        return "REQUIRED_NOW"
    if scope["authority_effect"] == "REJECTED_PROPOSAL":
        return "REJECTED_ACCOUNTED"
    assert scope["authority_effect"] == "FOLLOW_RELATED_SCOPE"
    return activation_aggregate(scope["related_register_ids"])

sequence_zero_reconciliation_ids = {
    "AUTH-REG-002", "AUTH-REG-003", "ALIAS-044",
}
authorized_delivery_reset = ("DEF-12", "SPEC_DRAFT", "INVENTORIED")
# r7 §7.2: an exact single-row manifest, not a kind-level or gate-level
# allowance. Only this row may move program_disposition at all.
disposition_exception_rows = {"PG-2-04"}
transition_ids = set()
source_status_transition_count = 0
status_source_reconciliation_count = 0
for row in rows:
    history = row["transition_history"]
    assert isinstance(history, list) and history
    previous_hash = None
    replay = None
    last_nonblocked_delivery = None
    activated_in_history = False
    for sequence, entry in enumerate(history):
        assert isinstance(entry, dict) and transition_fields <= entry.keys()
        assert entry["sequence"] == sequence
        assert isinstance(entry["transition_id"], str) and entry["transition_id"].strip()
        assert entry["transition_id"] not in transition_ids
        transition_ids.add(entry["transition_id"])
        assert entry["transition_type"] in transition_types
        actor = entry["actor"]
        assert set(actor) == {"actor_id", "actor_type", "role"}
        assert actor["actor_type"] in {"HUMAN", "AGENT", "SYSTEM"}
        assert all(
            isinstance(actor[field], str) and actor[field].strip()
            for field in ("actor_id", "role")
        )
        assert entry["invoked_model"] is None or (
            isinstance(entry["invoked_model"], str) and entry["invoked_model"].strip()
        )
        assert parse_utc_rfc3339(entry["timestamp"]) <= validation_now
        assert isinstance(entry["evidence_ref_ids"], list)
        assert entry["evidence_ref_ids"]
        assert set(entry["evidence_ref_ids"]) <= local_evidence_ids[row["component_id"]]
        assert entry["previous_entry_sha256"] == previous_hash
        entry_projection = {
            key: value for key, value in entry.items() if key != "entry_sha256"
        }
        assert entry["entry_sha256"] == canonical_sha256(entry_projection)
        previous_hash = entry["entry_sha256"]
        if sequence == 0:
            assert entry["field"] == "CONTROLLED_STATE"
            assert entry["old_value"] is None
            assert isinstance(entry["new_value"], dict)
            assert set(entry["new_value"]) == controlled_fields
            replay = entry["new_value"]
            if entry["transition_type"] == "AUTHORITY_RECONCILIATION":
                # r7 §3.2: a genuinely omitted post-activation component may
                # begin at sequence zero only under an active HR reconciliation.
                assert row["component_id"] in sequence_zero_reconciliation_ids
                transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
                assert replay["source_hash"] == current_source_hashes[
                    replay["source_path"]
                ]
                assert replay["delivery_status"] == "INVENTORIED"
                assert replay["gate_result"] == "NOT_EVALUATED"
                assert replay["activation_record"] is None
                assert replay["rejection_record"] is None
                if replay["delivery_status"] not in blocked_delivery_states:
                    last_nonblocked_delivery = replay["delivery_status"]
                continue
            assert entry["transition_type"] == "ACTIVATION_SNAPSHOT"
            assert entry["human_resolution_decision_id"] is None
            assert entry["human_resolution_sha256"] is None
            assert replay["source_hash"] == activation_authority_hashes[
                replay["source_path"]
            ]
            assert replay["program_disposition"] == activation_snapshot_disposition(replay)
            assert replay["delivery_status"] == "INVENTORIED"
            assert replay["gate_result"] == "NOT_EVALUATED"
            assert replay["activation_record"] is None
            if replay["kind"] == "register_row":
                assert replay["source_status"] == replay["activation_source_status"]
                assert replay["rejection_record"] is None
            elif replay["program_disposition"] != "REJECTED_ACCOUNTED":
                assert replay["rejection_record"] is None
            assert replay["bead_ids"] == []
            assert replay["roadmap_ref"] is None
            assert replay["plan_refs"] == []
            assert replay["implementation_refs"] == []
            assert replay["tracked_work"] == []
            assert replay["human_review_id"] is None
            assert replay["security_exception_ids"] == []
            assert replay["blocked_scope"] == []
            if replay["delivery_status"] not in blocked_delivery_states:
                last_nonblocked_delivery = replay["delivery_status"]
            continue

        field = entry["field"]
        assert field in controlled_fields
        assert entry["old_value"] == replay[field]
        old, new = entry["old_value"], entry["new_value"]
        assert old != new
        resolution_id = entry["human_resolution_decision_id"]
        resolution_hash = entry["human_resolution_sha256"]
        assert (resolution_id is None) == (resolution_hash is None)

        if field in {"component_id", "kind", "activation_source_status"}:
            raise AssertionError(f"immutable controlled field changed: {field}")
        elif field == "canonical_component_id":
            assert row["kind"] == alias_kind
            assert alias_targets(old) and alias_targets(new)
            assert entry["transition_type"] == "AUTHORITY_RECONCILIATION"
            transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
        elif (
            field == "source_hash"
            and replay["source_path"]
            == "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
        ) or (
            field == "text_digest"
            and replay["kind"] == "register_row"
            and replay["source_path"]
            == "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
        ):
            assert entry["transition_type"] == "STATUS_SOURCE_RECONCILIATION"
            assert resolution_id is None
            status_source_reconciliation_count += 1
        elif field in {
            "source_path", "source_anchor", "source_start_line", "source_end_line",
            "source_hash", "text_digest", "authority_rank", "register_id",
            "source_title", "required_acceptance_text", "blueprint_phase",
            "priority", "dependencies", "primary_spec", "disposition_refs",
            "gate_refs", "scope_definition",
        }:
            assert entry["transition_type"] == "AUTHORITY_RECONCILIATION"
            transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
        elif field == "activation_predicate":
            old_definition = None if old is None else {
                "predicate_id": old["predicate_id"], "expression": old["expression"],
                "metrics": old["metrics"],
            }
            new_definition = None if new is None else {
                "predicate_id": new["predicate_id"], "expression": new["expression"],
                "metrics": new["metrics"],
            }
            if old_definition != new_definition:
                assert entry["transition_type"] == "AUTHORITY_RECONCILIATION"
                transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
            else:
                assert entry["transition_type"] == "STATE_TRANSITION"
        elif field == "source_status":
            assert row["kind"] == "register_row"
            source_status_transition_count += 1
            legal = {
                ("Open", "In progress"), ("In progress", "Accepted"),
                ("Open", "Rejected"), ("In progress", "Rejected"),
                ("Deferred", "Open"), ("Deferred", "In progress"),
                ("Deferred", "Rejected"), ("Accepted", "Open"),
                ("Accepted", "Rejected"),
            }
            assert (old, new) in legal
            if old == "Deferred" and new in {"Open", "In progress"}:
                transition_resolution(entry, row, {"ACTIVATE_DEFERRED"})
                activated_in_history = True
            elif new == "Rejected":
                transition_resolution(entry, row, {"REJECT_COMPONENT"})
            elif old == "Accepted" and new == "Open":
                transition_resolution(entry, row, {"REOPEN_ACCEPTED"})
            else:
                assert resolution_id is None
        elif field == "program_disposition":
            legal = {
                ("CONDITIONAL_UNACTIVATED", "CONDITIONAL_ACTIVATED"),
                ("CONDITIONAL_UNACTIVATED", "REJECTED_ACCOUNTED"),
                ("CONDITIONAL_ACTIVATED", "REJECTED_ACCOUNTED"),
                ("REQUIRED_NOW", "REJECTED_ACCOUNTED"),
            }
            if (old, new) == ("CONDITIONAL_UNACTIVATED", "REQUIRED_NOW"):
                # r7 §3.2 bullet 9, all five conditions. Widening obligation
                # through a reconciled related-register scope: never available
                # to a register row, so it can never activate a Deferred
                # capability, and never compatible with a predicate or an
                # activation record.
                assert row["component_id"] in disposition_exception_rows
                assert row["kind"] != "register_row"
                assert entry["transition_type"] == "AUTHORITY_RECONCILIATION"
                transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
                assert row["program_disposition"] == new
                assert derived_by_component_id[row["component_id"]] == new
                assert row["activation_predicate"] is None
                assert row["activation_record"] is None
            else:
                assert (old, new) in legal
            if new == "CONDITIONAL_ACTIVATED":
                transition_resolution(entry, row, {"ACTIVATE_DEFERRED"})
            elif row["kind"] == "register_row":
                transition_resolution(entry, row, {"REJECT_COMPONENT"})
        elif field == "delivery_status":
            if new in blocked_delivery_states:
                assert old != "VERIFIED" and old not in blocked_delivery_states
                assert entry["transition_type"] == "BLOCK"
                last_nonblocked_delivery = old
            elif old in blocked_delivery_states:
                assert new == last_nonblocked_delivery
                assert entry["transition_type"] == "UNBLOCK"
            elif (
                entry["transition_type"] == "AUTHORITY_RECONCILIATION"
                and (row["component_id"], old, new) == authorized_delivery_reset
            ):
                # r7 §7.2: the only authorized backward delivery movement.
                transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
                last_nonblocked_delivery = new
            else:
                old_index = delivery_progression.index(old)
                new_index = delivery_progression.index(new)
                if row["primary_spec"] is None:
                    assert new_index > old_index
                else:
                    assert new_index == old_index + 1
                assert entry["transition_type"] == "STATE_TRANSITION"
                last_nonblocked_delivery = new
        elif field == "gate_result":
            legal = {
                ("NOT_EVALUATED", "PASS"), ("NOT_EVALUATED", "FAIL"),
                ("NOT_EVALUATED", "BLOCKED"),
                ("NOT_EVALUATED", "NOT_APPLICABLE_DORMANT"),
                ("FAIL", "NOT_EVALUATED"), ("BLOCKED", "NOT_EVALUATED"),
                ("NOT_APPLICABLE_DORMANT", "NOT_EVALUATED"),
            }
            assert (old, new) in legal
        elif field in {"activation_record", "rejection_record"}:
            assert old is None and isinstance(new, dict)
            purpose = (
                "ACTIVATE_DEFERRED" if field == "activation_record"
                else "REJECT_COMPONENT"
            )
            if row["kind"] == "register_row":
                transition_resolution(entry, row, {purpose})
            else:
                assert field == "rejection_record"
                assert resolution_id is None
        elif field in {
            "bead_ids", "plan_refs", "implementation_refs", "tracked_work",
            "security_exception_ids",
        }:
            assert isinstance(old, list) and isinstance(new, list)
            assert new[:len(old)] == old and len(new) > len(old)
            assert entry["transition_type"] == "REFERENCE_APPEND"
        elif field == "roadmap_ref":
            assert old is None and isinstance(new, str) and new.strip()
            assert entry["transition_type"] == "REFERENCE_APPEND"
        elif field == "blocked_scope":
            assert isinstance(old, list) and isinstance(new, list)
            if not old and new:
                assert entry["transition_type"] == "BLOCK"
            elif old and not new:
                assert entry["transition_type"] == "UNBLOCK"
            else:
                assert entry["transition_type"] == "STATE_TRANSITION"
        else:
            assert field == "human_review_id"
            old_links = normalized_human_review_id(old)
            new_links = normalized_human_review_id(new)
            # r7 §3.2: append-only link growth; removal or replacement fails.
            assert old_links < new_links
            assert new_links <= set(human_entries)
            if entry["transition_type"] == "AUTHORITY_RECONCILIATION":
                transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})
            else:
                assert old is None
                assert entry["transition_type"] == "REFERENCE_APPEND"
        replay = {**replay, field: new}

    assert replay == controlled_state(row)
    if activated_in_history:
        assert row["activation_record"] is not None
    assert row["transition_history_sha256"] == canonical_sha256(
        [entry["entry_sha256"] for entry in history]
    )
assert status_source_reconciliation_count == 0 or source_status_transition_count > 0

evidence_requirement_fields = {
    "evidence_id", "description", "scope", "evidence_type", "proof_mode",
    "status", "evidence_ref_ids", "approval_ids",
}
evidence_types = {
    "COMMAND_RESULT", "ARTIFACT", "SOURCE", "REVIEW", "ANALYST", "DOMAIN",
    "PROVIDER", "DATA_RIGHTS", "LEGAL", "REGULATORY", "BUDGET", "CAPACITY",
    "NAMED_OWNER", "PRODUCTION", "DISTRIBUTION", "SECURITY",
    "EXTERNAL_COORDINATION",
}
human_evidence_types = {
    "ANALYST", "DOMAIN", "PROVIDER", "DATA_RIGHTS", "LEGAL", "REGULATORY",
    "BUDGET", "CAPACITY", "NAMED_OWNER", "PRODUCTION", "DISTRIBUTION",
    "SECURITY", "EXTERNAL_COORDINATION",
}
evidence_requirement_ids = set()
evidence_requirements_by_row = {}
for row in rows:
    local_ids = local_evidence_ids[row["component_id"]]
    local_approval_requirements = {
        item["approval_id"]: item for item in row["required_approvals"]
    }
    assert isinstance(row["required_evidence"], list)
    local_requirements = []
    for item in row["required_evidence"]:
        assert evidence_requirement_fields <= item.keys()
        evidence_id = item["evidence_id"]
        assert isinstance(evidence_id, str) and evidence_id.strip()
        assert evidence_id not in evidence_requirement_ids
        evidence_requirement_ids.add(evidence_id)
        for field in ("description", "scope"):
            assert isinstance(item[field], str) and item[field].strip()
        assert item["evidence_type"] in evidence_types
        assert item["proof_mode"] in {"COMMAND", "CONTENT_HASH", "TYPED_APPROVAL"}
        assert item["status"] in {"UNRESOLVED", "SATISFIED"}
        assert isinstance(item["evidence_ref_ids"], list)
        assert set(item["evidence_ref_ids"]) <= local_ids
        assert isinstance(item["approval_ids"], list)
        assert set(item["approval_ids"]) <= set(local_approval_requirements)
        if item["evidence_type"] == "COMMAND_RESULT":
            assert item["proof_mode"] == "COMMAND"
        if item["evidence_type"] in human_evidence_types:
            assert item["proof_mode"] == "TYPED_APPROVAL"
        if item["proof_mode"] == "TYPED_APPROVAL":
            assert item["approval_ids"]
        else:
            assert item["approval_ids"] == []
        if item["status"] == "UNRESOLVED":
            assert item["evidence_ref_ids"] == []
        else:
            assert item["evidence_ref_ids"]
            if item["proof_mode"] == "TYPED_APPROVAL":
                for approval_id in item["approval_ids"]:
                    approval = local_approval_requirements[approval_id]
                    assert approval["status"] == "SATISFIED"
                    assert set(approval["evidence_ref_ids"]) <= set(
                        item["evidence_ref_ids"]
                    )
        local_requirements.append(item)
    evidence_requirements_by_row[row["component_id"]] = local_requirements
    if row["kind"] != alias_kind:
        validate_inventory_review(row, row["evidence_inventory_review"], "EVIDENCE")

command_fields = {
    "command_id", "argv", "cwd", "scope_ref_ids", "expected_exit_code",
    "command_sha256",
}
result_fields = {
    "verification_result_id", "command_id", "command_sha256", "scope_ref_ids",
    "scope_sha256", "component_state_sha256", "exit_code", "output_ref_ids",
    "output_sha256", "executed_at",
}
not_applicable_fields = {
    "status", "reviewer", "model", "effort", "verdict", "timestamp", "reason",
    "evidence_ref_ids", "component_state_sha256",
} | role_binding_fields
state_fields = (
    required
    - {
        "delivery_status", "gate_result", "verification_result", "verified_at",
        "transition_history",
    }
)

def component_state_sha256(row):
    projection = {field: row[field] for field in sorted(state_fields)}
    policy = row["verification_command"]
    na_review = policy.get("not_applicable_review")
    if isinstance(na_review, dict):
        na_review = {
            key: value
            for key, value in na_review.items()
            if key != "component_state_sha256"
        }
    projection["verification_command"] = {
        "mode": policy.get("mode"),
        "commands": policy.get("commands"),
        "not_applicable_review": na_review,
    }
    return canonical_sha256(projection)

def ref_set_sha256(ref_ids):
    assert isinstance(ref_ids, list) and ref_ids
    assert len(set(ref_ids)) == len(ref_ids)
    return canonical_sha256(
        [evidence_by_id[ref_id] for ref_id in sorted(ref_ids)]
    )

command_ids = set()
result_ids = set()
current_results_by_row = {}
for row in rows:
    policy = row["verification_command"]
    assert isinstance(policy, dict)
    assert {"mode", "commands", "not_applicable_review"} <= policy.keys()
    assert policy["mode"] in {"UNRESOLVED", "COMMANDS", "NOT_APPLICABLE"}
    assert isinstance(policy["commands"], list)
    assert isinstance(row["verification_result"], list)
    local_ids = local_evidence_ids[row["component_id"]]
    local_commands = {}
    for command in policy["commands"]:
        assert command_fields <= command.keys()
        command_id = command["command_id"]
        assert isinstance(command_id, str) and command_id.strip()
        assert command_id not in command_ids
        command_ids.add(command_id)
        assert isinstance(command["argv"], list) and command["argv"]
        assert all(isinstance(arg, str) and arg for arg in command["argv"])
        assert repo_path(command["cwd"], must_exist=True).is_dir()
        assert isinstance(command["scope_ref_ids"], list)
        assert command["scope_ref_ids"]
        assert set(command["scope_ref_ids"]) <= local_ids
        assert command["expected_exit_code"] == 0
        digest_input = {
            key: command[key] for key in command_fields - {"command_sha256"}
        }
        assert command["command_sha256"] == canonical_sha256(digest_input)
        local_commands[command_id] = command

    local_results = {}
    for result in row["verification_result"]:
        assert result_fields <= result.keys()
        result_id = result["verification_result_id"]
        assert isinstance(result_id, str) and result_id.strip()
        assert result_id not in result_ids
        result_ids.add(result_id)
        command_id = result["command_id"]
        assert command_id in local_commands and command_id not in local_results
        command = local_commands[command_id]
        assert result["command_sha256"] == command["command_sha256"]
        assert result["scope_ref_ids"] == command["scope_ref_ids"]
        assert result["scope_sha256"] == ref_set_sha256(result["scope_ref_ids"])
        assert result["component_state_sha256"] == component_state_sha256(row)
        assert isinstance(result["exit_code"], int)
        assert isinstance(result["output_ref_ids"], list)
        assert result["output_ref_ids"]
        assert set(result["output_ref_ids"]) <= local_ids
        assert result["output_sha256"] == ref_set_sha256(result["output_ref_ids"])
        executed_at = parse_utc_rfc3339(result["executed_at"])
        assert executed_at <= validation_now
        assert all(
            parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"]) >= executed_at
            for ref_id in result["output_ref_ids"]
        )
        local_results[command_id] = result
    current_results_by_row[row["component_id"]] = local_results

    if policy["mode"] == "UNRESOLVED":
        assert policy["commands"] == []
        assert policy["not_applicable_review"] is None
        assert row["verification_result"] == []
        assert row["verified_at"] is None
    elif policy["mode"] == "COMMANDS":
        assert policy["commands"]
        assert policy["not_applicable_review"] is None
    else:
        assert policy["commands"] == [] and row["verification_result"] == []
        review = policy["not_applicable_review"]
        assert isinstance(review, dict) and set(review) == not_applicable_fields
        assert review["status"] == "COMPLETE"
        assert isinstance(review["reviewer"], str) and review["reviewer"].strip()
        assert_reviewer_role_binding(review)
        assert review["verdict"] == "CLEAN"
        assert parse_utc_rfc3339(review["timestamp"]) <= validation_now
        assert isinstance(review["reason"], str) and review["reason"].strip()
        assert isinstance(review["evidence_ref_ids"], list)
        assert review["evidence_ref_ids"]
        assert set(review["evidence_ref_ids"]) <= local_ids
        assert review["component_state_sha256"] == component_state_sha256(row)

    if row["verified_at"] is not None:
        verified_at = parse_utc_rfc3339(row["verified_at"])
        assert verified_at <= validation_now
        if local_results:
            assert all(
                verified_at >= parse_utc_rfc3339(result["executed_at"])
                for result in local_results.values()
            )
            assert all(
                verified_at >= parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"])
                for result in local_results.values()
                for ref_id in result["output_ref_ids"]
            )
        if policy["mode"] == "NOT_APPLICABLE":
            assert verified_at >= parse_utc_rfc3339(
                policy["not_applicable_review"]["timestamp"]
            )

def assert_complete_proof(row):
    validate_inventory_review(row, row["approval_inventory_review"], "APPROVAL")
    validate_inventory_review(row, row["evidence_inventory_review"], "EVIDENCE")
    assert row["approval_inventory_review"]["status"] == "COMPLETE"
    assert row["evidence_inventory_review"]["status"] == "COMPLETE"
    if row["kind"] != "register_row":
        validate_inventory_review(
            row, row["scope_derivation"]["semantic_review"], "SCOPE"
        )
        assert row["scope_derivation"]["semantic_review"]["status"] == "COMPLETE"
    assert all(
        requirement["status"] == "SATISFIED"
        and requirement["matched_record_id"] is not None
        for requirement in row["required_approvals"]
    )
    evidence_requirements = evidence_requirements_by_row[row["component_id"]]
    assert all(
        item["status"] == "SATISFIED" and item["evidence_ref_ids"]
        for item in evidence_requirements
    )
    policy = row["verification_command"]
    results = current_results_by_row[row["component_id"]]
    if policy["mode"] == "COMMANDS":
        commands = {command["command_id"]: command for command in policy["commands"]}
        assert set(results) == set(commands)
        assert all(
            result["exit_code"] == commands[command_id]["expected_exit_code"] == 0
            for command_id, result in results.items()
        )
        output_ref_ids = {
            ref_id for result in results.values() for ref_id in result["output_ref_ids"]
        }
        assert all(
            set(item["evidence_ref_ids"]) <= output_ref_ids
            for item in evidence_requirements
            if item["proof_mode"] == "COMMAND"
        )
    else:
        assert policy["mode"] == "NOT_APPLICABLE"
        assert policy["not_applicable_review"]["status"] == "COMPLETE"
        assert all(
            item["proof_mode"] != "COMMAND" for item in evidence_requirements
        )
    assert row["verified_at"] is not None

for row in canonical_rows:
    if (
        row["delivery_status"] == "VERIFIED"
        or row["source_status"] == "Accepted"
        or row["gate_result"] == "PASS"
    ):
        assert_complete_proof(row)

# ---------------------------------------------------------------------------
# r7 §8.1 validator-owned manifests. None of these import generator constants;
# each value is transcribed from the reviewed r7 design.
# ---------------------------------------------------------------------------
EXPECTED_ALIAS_TARGETS = {
    "ALIAS-001": [
        "DISP-G-1", "DISP-G-2", "DISP-G-3", "DISP-G-4", "DISP-G-5",
        "DISP-M-1", "DISP-M-2", "DISP-M-3", "DISP-M-4", "DISP-M-5",
        "DISP-M-6", "DISP-M-7", "DISP-M-8", "DISP-M-9",
    ],
    "ALIAS-002": "DISP-G-1",
    "ALIAS-003": "DISP-6-1",
    "ALIAS-004": "DISP-G-5",
    "ALIAS-005": "DISP-6-3",
    "ALIAS-006": "DISP-6-6",
    "ALIAS-007": "DISP-6-5",
    "ALIAS-008": "DISP-R-1",
    "ALIAS-009": "DISP-6-7",
    "ALIAS-010": "DISP-6-8",
    "ALIAS-011": ["DISP-G-1", "DISP-G-2", "DISP-G-3", "DISP-G-4", "DISP-G-5"],
    "ALIAS-012": [
        "DISP-M-1", "DISP-M-2", "DISP-M-3", "DISP-M-4", "DISP-M-5",
        "DISP-M-6", "DISP-M-7", "DISP-M-8", "DISP-M-9",
    ],
    "ALIAS-013": ["DISP-T-1", "DISP-T-2", "DISP-T-3", "DISP-T-4"],
    "ALIAS-014": ["DISP-R-1", "DISP-R-2", "DISP-R-3", "DISP-R-4", "DISP-R-5"],
    "ALIAS-015": [
        "DISP-G-1", "DISP-G-2", "DISP-G-3", "DISP-G-4", "DISP-G-5",
        "DISP-M-1", "DISP-M-2", "DISP-M-3", "DISP-M-4", "DISP-M-5",
        "DISP-M-6", "DISP-M-7", "DISP-M-8", "DISP-M-9",
        "DISP-R-1", "DISP-R-2", "DISP-R-3", "DISP-R-4", "DISP-R-5",
        "DISP-T-1", "DISP-T-2", "DISP-T-3", "DISP-T-4",
    ],
    "ALIAS-016": "DISP-R-1",
    "ALIAS-017": "DISP-G-5",
    "ALIAS-018": "DISP-M-1",
    "ALIAS-019": "DISP-T-1",
    "ALIAS-020": "DISP-T-2",
    "ALIAS-021": "DISP-R-3",
    "ALIAS-022": "DISP-R-2",
    "ALIAS-023": "REG-A-04",
    "ALIAS-024": "DISP-G-4",
    "ALIAS-025": "DISP-M-2",
    "ALIAS-026": "DISP-M-3",
    "ALIAS-027": "DISP-M-6",
    "ALIAS-028": "DISP-M-5",
    "ALIAS-029": "DISP-G-2",
    "ALIAS-030": "DISP-M-4",
    "ALIAS-031": "DISP-G-1",
    "ALIAS-032": "DISP-M-7",
    "ALIAS-033": "DISP-M-8",
    "ALIAS-034": "DISP-G-5",
    "ALIAS-035": "DISP-G-3",
    "ALIAS-036": "DISP-R-1",
    "ALIAS-037": "DISP-6-4",
    "ALIAS-038": "DISP-R-1",
    "ALIAS-039": "DISP-6-5",
    "ALIAS-040": "DISP-M-4",
    "ALIAS-041": [
        "DISP-G-5", "DISP-M-1", "DISP-M-2", "DISP-M-4", "DISP-M-5",
        "DISP-M-6", "DISP-T-2",
    ],
    "ALIAS-042": "DISP-R-1",
    "ALIAS-043": [
        "DISP-6-4", "DISP-G-4", "DISP-M-1", "DISP-M-2", "DISP-M-4",
        "DISP-M-5", "DISP-R-1", "DISP-T-2", "DOC-02", "DOC-03",
    ],
    "ALIAS-044": "AUTH-REG-001",
}
assert {row["component_id"] for row in aliases} == set(EXPECTED_ALIAS_TARGETS)
for row in aliases:
    assert row["canonical_component_id"] == EXPECTED_ALIAS_TARGETS[
        row["component_id"]
    ]

EXPECTED_DISPOSITION_CROSSWALK = {
    "DISP-G-1": (["S06", "S11", "S16"], ["A-04", "C-08", "C-09", "C-16"]),
    "DISP-G-2": (["S18"], ["B-04"]),
    "DISP-G-3": (["S18"], ["B-04", "C-12"]),
    "DISP-G-4": (["S05", "S18"], ["A-02", "A-03", "B-02", "B-04", "B-13"]),
    "DISP-G-5": (["S06", "S13"], ["A-10", "C-04"]),
    "DISP-M-1": (["S05"], ["A-11"]),
    "DISP-M-2": (["S12"], ["B-05", "B-11", "C-03"]),
    "DISP-M-3": (["S13"], ["B-06", "B-12"]),
    "DISP-M-4": (["S11", "S25"], ["C-15", "E-10"]),
    "DISP-M-5": (["S14", "S15"], ["B-01", "B-14", "C-10"]),
    "DISP-M-6": (["S07", "S15"], ["A-08", "B-13", "C-10"]),
    "DISP-M-7": (["S17"], ["C-17"]),
    "DISP-M-8": (["S08", "S18"], ["A-13", "C-18"]),
    "DISP-M-9": (["S07", "S09"], ["A-08", "B-08"]),
    "DISP-T-1": (["S08"], ["A-12"]),
    "DISP-T-2": (["S08"], ["A-13"]),
    "DISP-T-3": (["S10"], ["B-03"]),
    "DISP-T-4": (["S01", "S02", "S04"], ["A-01", "E-08", "E-09"]),
    "DISP-R-1": (["S19", "S20"], ["D-02"]),
    "DISP-R-2": (["S09"], ["A-06"]),
    "DISP-R-3": (["S02"], ["A-05"]),
    "DISP-R-4": (["S06"], ["A-04"]),
    "DISP-R-5": (["S10", "S14"], ["B-01", "B-03"]),
    "DISP-6-1": (["S18"], ["B-04"]),
    "DISP-6-2": (["S06", "S13"], ["A-10", "C-04"]),
    "DISP-6-3": (["S17"], ["C-17"]),
    "DISP-6-4": (["S19", "S20"], ["D-02", "D-05"]),
    "DISP-6-5": (["S25"], ["E-10"]),
    "DISP-6-6": (["S07", "S15"], ["B-13", "C-10"]),
    "DISP-6-7": (["S03", "S04"], ["E-06", "E-07", "E-09"]),
    "DISP-6-8": (["S05"], ["A-02", "B-02"]),
    "DISP-6-9": (["S11", "S16"], ["C-08", "C-16"]),
}
disposition_rows = {
    row["component_id"]: row for row in canonical_rows
    if row["kind"] == "disposition_item"
}
assert set(disposition_rows) == set(EXPECTED_DISPOSITION_CROSSWALK)
for component_id, (spec_ids, register_ids) in (
    EXPECTED_DISPOSITION_CROSSWALK.items()
):
    disposition_row = disposition_rows[component_id]
    derivation = disposition_row["scope_derivation"]
    assert derivation["applicable_spec_ids"] == sorted(spec_ids)
    assert derivation["related_register_ids"] == register_ids
    if len(spec_ids) == 1:
        assert disposition_row["primary_spec"] is not None
        assert disposition_row["primary_spec"]["spec_id"] == spec_ids[0]
    else:
        assert disposition_row["primary_spec"] is None

EXPECTED_SEQUENCE_CROSSWALK = {
    "SEQ-01": (["A-01"], ["S01"]),
    "SEQ-02": (["A-05", "A-09"], ["S01", "S02"]),
    "SEQ-03": (["A-02", "A-06"], ["S05", "S09"]),
    "SEQ-04": (["A-10", "A-13"], ["S06", "S08"]),
    "SEQ-05": (["A-04"], ["S06"]),
    "SEQ-06": (["A-03", "A-11"], ["S05"]),
    "SEQ-07": (["A-04"], ["S06"]),
    "SEQ-08": (["B-11", "B-12"], ["S12", "S13"]),
    "SEQ-09": (["B-01", "B-14"], ["S14"]),
    "SEQ-10": (["B-02"], ["S14"]),
    "SEQ-11": ([], []),
}
sequence_rows = {
    row["component_id"]: row for row in canonical_rows
    if row["kind"] == "sequence_clause"
}
assert set(sequence_rows) == set(EXPECTED_SEQUENCE_CROSSWALK)
for component_id, (source_ids, spec_ids) in EXPECTED_SEQUENCE_CROSSWALK.items():
    sequence_row = sequence_rows[component_id]
    derivation = sequence_row["scope_derivation"]
    assert derivation["rule"] == "PROGRAM_WIDE_ACTIVE_CONTROL"
    assert derivation["related_register_ids"] == []
    assert derivation["authority_effect"] is None
    assert derivation["source_register_ids"] == sorted(source_ids)
    assert derivation["applicable_spec_ids"] == sorted(spec_ids)
    assert sequence_row["primary_spec"] is None
    assert sequence_row["program_disposition"] == "REQUIRED_NOW"

negative_control = by_id["PG-1-11"]
negative_derivation = negative_control["scope_derivation"]
assert negative_derivation["rule"] == "ACTIVE_NEGATIVE_CONTROL"
assert negative_derivation["related_register_ids"] == [
    "D-02", "D-05", "E-03", "E-05", "E-09"
]
assert negative_derivation["authority_effect"] is None
assert negative_derivation["derived_program_disposition"] == "REQUIRED_NOW"
assert negative_control["program_disposition"] == "REQUIRED_NOW"
assert negative_control["primary_spec"] is None
assert negative_control["activation_predicate"] is None
assert negative_control["source_start_line"] == 160
assert {
    row["component_id"] for row in canonical_rows
    if row["scope_derivation"]["rule"] == "ACTIVE_NEGATIVE_CONTROL"
} == {"PG-1-11"}

EXPECTED_PHASE2_POINTER_PREFIX = {
    gate_id: "/phase_gates/" + gate_id.lower().replace("-", "_")
    for gate_id in sorted(PHASE2_CONDITIONAL_GATE_IDS)
}
FORBIDDEN_PHASE2_FIELD_SUFFIXES = ("_ready", "_improved", "_acceptable")
for gate_id, pointer_prefix in EXPECTED_PHASE2_POINTER_PREFIX.items():
    gate_row = by_id[gate_id]
    predicate = gate_row["activation_predicate"]
    assert predicate is not None
    assert gate_row["program_disposition"] == "CONDITIONAL_UNACTIVATED"
    assert predicate["predicate_id"] == "AP-" + gate_id
    assert predicate["expression"]["op"] == "ALL"
    for metric in predicate["metrics"]:
        pointer = metric["json_pointer"]
        assert pointer.startswith(pointer_prefix + "/")
        field_name = pointer[len(pointer_prefix) + 1:]
        assert "/" not in field_name
        assert not field_name.endswith(FORBIDDEN_PHASE2_FIELD_SUFFIXES)
        assert metric["metric_id"] == (
            "MTR-" + gate_id + "-" + field_name.replace("_", "-").upper()
        )
    assert any(
        leaf["op"] == "COMPARE_METRICS"
        for leaf in predicate["expression"]["args"]
    ) or gate_id == "PG-2-03"

# r7 §3.5.1/§7.2: the single-row PG-2-04 outcome, owned here as an exact
# manifest rather than a kind-level or gate-level allowance.
PG_2_04_COMMAND_PROOF_SCOPE = (
    'PG-2-04 command proof: correction_test_result_id != "" and '
    "correction_cases_executed > 0 and correction_failure_count == 0 and "
    'deletion_test_result_id != "" and deletion_cases_executed > 0 and '
    "deletion_failure_count == 0 and "
    'backup_test_result_id != "" and backup_cases_executed > 0 and '
    "backup_failure_count == 0 and "
    'export_test_result_id != "" and export_cases_executed > 0 and '
    "export_failure_count == 0"
)
pg_2_04 = by_id["PG-2-04"]
pg_2_04_derivation = pg_2_04["scope_derivation"]
assert pg_2_04_derivation["rule"] == "RELATED_REGISTER_SCOPE"
assert pg_2_04_derivation["related_register_ids"] == ["D-01", "D-03"]
assert pg_2_04_derivation["authority_effect"] is None
assert pg_2_04_derivation["derived_program_disposition"] == "REQUIRED_NOW"
assert pg_2_04["program_disposition"] == "REQUIRED_NOW"
assert pg_2_04["primary_spec"] is None
assert pg_2_04["activation_predicate"] is None
assert pg_2_04["activation_record"] is None
assert pg_2_04["gate_result"] == "NOT_EVALUATED"
pg_2_04_command_proof = [
    item for item in pg_2_04["required_evidence"]
    if item["evidence_id"] == "REQ-PG-2-04-COMMAND-PROOF"
]
assert len(pg_2_04_command_proof) == 1
assert pg_2_04_command_proof[0]["scope"] == PG_2_04_COMMAND_PROOF_SCOPE
assert pg_2_04_command_proof[0]["status"] == "UNRESOLVED"
assert pg_2_04_command_proof[0]["evidence_ref_ids"] == []

# r7 §3.7 closed required-authority vocabulary. Introducing a second string for
# an authority that already has one is a permanent trap, so the map is owned
# here and every entry outside it is rejected.
REQUIRED_AUTHORITY_VOCABULARY = {
    "ANALYST_ACCEPTANCE": {"Responsible analyst"},
    "BUDGET_APPROVAL": {"Budget owner"},
    "CAPACITY_COMMITMENT": {"Capacity owner"},
    "DATA_RIGHTS_APPROVAL": {"Data-rights authority"},
    "DISTRIBUTION_APPROVAL": {"Distribution owner"},
    "DOMAIN_EXPERT_ACCEPTANCE": {
        "Calculation-domain authority", "Data-domain authority",
        "Entity-data authority", "Equity-research domain expert",
        "Vocabulary authority",
    },
    "EXECUTION_TRUST_DOMAIN_APPROVAL": {"Execution-boundary owner"},
    "LEGAL_REVIEW": {
        "Competent dependency-license reviewer", "Competent legal reviewer",
        "Competent trademark or legal reviewer",
    },
    "MEMORY_PROMOTION": {"Responsible analyst"},
    "NAMED_OWNER_COMMITMENT": {
        "Event-monitoring owner", "Golden-set owner",
        "Model-grade compute owner",
    },
    "PRODUCT_OWNER_DECISION": {
        "Product owner",
        "Product owner authorized to activate deferred blueprint scope",
        "Product owner for memory adoption",
    },
    "REGULATORY_REVIEW": {"Competent regulatory reviewer"},
}
AUTHORIZED_AUTHORITY_ADDITIONS = {
    ("NAMED_OWNER_COMMITMENT", "Event-monitoring owner"),
    ("NAMED_OWNER_COMMITMENT", "Model-grade compute owner"),
}
delegated_artifact_authorities = set()
for row in rows:
    for approval in row["required_approvals"]:
        approval_type = approval["approval_type"]
        authority = approval["required_authority"]
        if approval_type == "DELEGATED_ARTIFACT_APPROVAL":
            # The only process-role authority; its literal is deliberately not
            # pinned, but it must be one identical nonempty string everywhere.
            assert isinstance(authority, str) and authority.strip()
            delegated_artifact_authorities.add(authority)
            continue
        assert approval_type in REQUIRED_AUTHORITY_VOCABULARY, approval_type
        assert authority in REQUIRED_AUTHORITY_VOCABULARY[approval_type], (
            approval_type, authority
        )
assert len(delegated_artifact_authorities) == 1

EXPECTED_COMMAND_PROOF_COMPONENTS = {
    "REG-A-10", "REG-B-01", "REG-B-11", "REG-B-14", "REG-C-08",
    "REG-C-15", "REG-C-16", "REG-C-17", "REG-E-01", "REG-E-10",
    "PG-05-08", "PG-1-04", "PG-1-05", "PG-1-06", "PG-2-03", "PG-2-04",
    "DISP-G-1", "DISP-M-4", "DISP-M-5", "DISP-M-6", "DISP-M-7",
    "DISP-M-9", "DISP-6-6", "DISP-6-9", "SEQ-09",
}
actual_command_proof_components = {
    row["component_id"] for row in rows
    if any(
        item["evidence_type"] == "COMMAND_RESULT"
        for item in row["required_evidence"]
    )
}
assert actual_command_proof_components == EXPECTED_COMMAND_PROOF_COMPONENTS

for index in range(1, 5):
    assert by_id[f"SCALE-WORKFLOW-{index:02d}"]["disposition_refs"] == ["M-5"]
    assert by_id[f"SCALE-SQLITE-{index:02d}"]["disposition_refs"] == ["R-5"]
assert by_id["DEF-12"]["primary_spec"] is None
assert by_id["PG-2-04"]["scope_derivation"]["related_register_ids"] == [
    "D-01", "D-03"
]

gate_map = collections.defaultdict(set)
for row in canonical_rows:
    if row["kind"] == "phase_gate_clause":
        for register_id in row["scope_derivation"]["related_register_ids"]:
            gate_map[register_id].add(row["component_id"])
for row in register_rows:
    assert len(set(row["gate_refs"])) == len(row["gate_refs"])
    assert set(row["gate_refs"]) == gate_map.get(row["register_id"], set())

# ---------------------------------------------------------------------------
# r7 §3.2/§3.6 closed current no-implementation-proof predicate.
# ---------------------------------------------------------------------------
NO_IMPLEMENTATION_REQUIREMENT_MAP = {
    "DISP-R-1": ["REQ-DISP-R-1-NO-IMPLEMENTATION"],
}
# Immutable identity of the mapped DISP-R-1 proof requirement (A12).
EXPECTED_DISP_R1_REQUIREMENT_IDENTITY = {
    "approval_ids": [],
    "description": (
        "Current S20 draft preserves D-02 as dormant and contains no "
        "implementation claim"
    ),
    "evidence_id": "REQ-DISP-R-1-NO-IMPLEMENTATION",
    "evidence_type": "ARTIFACT",
    "proof_mode": "CONTENT_HASH",
    "scope": "R-1 current no-implementation proof",
}
DISP_R1_MUTABLE_FIELDS = {"status", "evidence_ref_ids"}  # move only together

def current_no_implementation_proof(row):
    """r7 §3.2 closed predicate. False is a valid structural state."""
    record = row["rejection_record"]
    if record is None:
        return True, []
    historical = list(record["no_implementation_evidence_ref_ids"])
    requirement_ids = NO_IMPLEMENTATION_REQUIREMENT_MAP.get(
        row["component_id"], []
    )
    if not requirement_ids:
        return True, []
    requirements = {
        item["evidence_id"]: item for item in row["required_evidence"]
    }
    assert set(requirement_ids) <= set(requirements)
    reasons = []
    mapped = [requirements[item_id] for item_id in requirement_ids]
    covered = set()
    for item in mapped:
        covered |= set(item["evidence_ref_ids"])
    if not set(historical) <= covered:
        reasons.append("HISTORICAL_REFS_UNCOVERED")
    if any(item["status"] != "SATISFIED" for item in mapped):
        reasons.append("REQUIREMENT_UNRESOLVED")
    review = row["evidence_inventory_review"]
    review_ok = (
        isinstance(review, dict)
        and review["status"] == "COMPLETE"
        and review["verdict"] == "CLEAN"
        and review.get("role") == "REVIEWER"
        and review.get("role_binding_path") == ROLE_BINDING_PATH
        and set(historical) <= set(review["evidence_ref_ids"])
    )
    if review_ok:
        review_time = parse_utc_rfc3339(review["timestamp"])
        review_ok = all(
            review_time >= parse_utc_rfc3339(
                evidence_by_id[ref_id]["captured_at"]
            )
            for ref_id in historical
        )
    if not review_ok:
        reasons.append("CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING")
    return not reasons, sorted(set(reasons))

unmet_no_implementation_proof = []
for row in canonical_rows:
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

disp_r1 = by_id["DISP-R-1"]
assert disp_r1["rejection_record"]["no_implementation_evidence_ref_ids"] == [
    "EV-DISP-R-1-SPEC-DRAFT"
]
# A12 closed two-state rule. r7 §3.6/§8.1 kept this post-state explicitly
# unproven with reason codes a digest refresh can never remove; that stays the
# only alternative to a fully evidenced current proof, and no third state exists.
disp_r1_requirement = next(item for item in disp_r1["required_evidence"] if item["evidence_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION")
assert {key: value for key, value in disp_r1_requirement.items() if key not in DISP_R1_MUTABLE_FIELDS} == EXPECTED_DISP_R1_REQUIREMENT_IDENTITY
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
disp_r1_unmet = [item for item in unmet_no_implementation_proof if item["component_id"] == "DISP-R-1"]
if disp_r1_requirement["status"] == "UNRESOLVED":
    assert disp_r1_proven is False and {"REQUIREMENT_UNRESOLVED", "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)
    assert any(item["requirement_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION" for item in disp_r1_unmet)
else:
    assert disp_r1_requirement["status"] == "SATISFIED" and disp_r1_proven is True and disp_r1_reasons == [] and not disp_r1_unmet
    assert set(disp_r1_requirement["evidence_ref_ids"]) >= set(disp_r1["rejection_record"]["no_implementation_evidence_ref_ids"])

# ---------------------------------------------------------------------------
# r7 §4 exact HR-0004 structured scope and reverse links.
# ---------------------------------------------------------------------------
EXPECTED_HR0004_SCOPE_DIGEST = (
    "bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894"
)
EXPECTED_PRIOR_HR_LINKS = {
    "HR-0001": {
        "DISP-6-2", "DISP-G-1", "DISP-G-5", "DISP-R-4", "REG-A-04",
        "REG-A-10", "SEQ-04", "SEQ-05", "SEQ-07",
    },
    "HR-0002": {"DISP-R-2", "REG-A-06", "REG-B-09", "REG-C-02", "REG-C-14"},
    "HR-0003": {
        "DEF-13", "DISP-R-5", "DISP-T-3", "REG-B-03", "REG-C-11",
        "SCALE-SQLITE-01", "SCALE-SQLITE-02", "SCALE-SQLITE-03",
        "SCALE-SQLITE-04",
    },
}
if "HR-0004" in human_entries:
    hr0004 = human_entries["HR-0004"]
    scope_ids = hr0004["scope"]["component_ids"]
    assert scope_ids == sorted(set(scope_ids))
    assert len(scope_ids) == 144
    assert canonical_sha256(scope_ids) == EXPECTED_HR0004_SCOPE_DIGEST
    assert hr0004["scope"]["register_ids"] == []
    assert hr0004["scope"]["spec_ids"] == []
    assert hr0004["scope"]["bead_ids"] == []
    assert hr0004["scope"]["blocked_component_ids"] == []
    assert hr0004["scope"]["scope_text"].strip()
    scope_set = set(scope_ids)
    scoped_aliases = {
        component_id for component_id in scope_set
        if by_id[component_id]["kind"] == alias_kind
    }
    assert len(scoped_aliases) == 10
    scoped_canonical = scope_set - scoped_aliases
    assert len(scoped_canonical) == 134
    for component_id in scoped_canonical:
        assert "HR-0004" in human_review_links[component_id]
    for component_id, links in human_review_links.items():
        if "HR-0004" in links:
            assert component_id in scoped_canonical
    for entry_id, expected_components in EXPECTED_PRIOR_HR_LINKS.items():
        for component_id in expected_components:
            assert human_review_links[component_id] == frozenset(
                {entry_id, "HR-0004"}
            )
    overlapping = {c for c, links in human_review_links.items() if len(links) > 1}
    hr0005 = human_entries.get("HR-0005")  # A12: the sole admissible addition
    amendment_overlap = {"DISP-R-1"} if hr0005 else set()
    assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values()) | amendment_overlap
    assert len(overlapping) == 23 + len(amendment_overlap)
    assert not hr0005 or (len(hr0005["resolution_decision_ids"]) == 1 and human_scope_components["HR-0005"] == frozenset({"DISP-R-1"}) and human_review_links["DISP-R-1"] == frozenset({"HR-0004", "HR-0005"}) and hr0005["entry_type"] == "DECISION" and hr0005["decision_authority"]["approval_type"] == "GOAL_OR_PROCESS_AUTHORIZATION" and [r["decision_id"] for r in human_resolutions.values() if r["human_review_id"] == "HR-0005"] == [r["decision_id"] for r in active_human_resolutions.values() if r["human_review_id"] == "HR-0005" and r["decision_type"] == "RECONCILE_AUTHORITY" and r["actor"]["actor_type"] == "HUMAN" and r["actor"]["role"] == "CURRENT_USER" and r["authority_basis"]["approval_type"] == "GOAL_OR_PROCESS_AUTHORIZATION"])
    for entry_id in ("HR-0001", "HR-0002", "HR-0003"):
        assert human_entries[entry_id]["state"] == "OPEN_BLOCKING"
        assert human_entries[entry_id]["resolution_decision_ids"] == []
    hr0004_resolutions = [
        resolution for resolution in human_resolutions.values()
        if resolution["human_review_id"] == "HR-0004"
    ]
    assert len(hr0004_resolutions) == 1
    assert hr0004_resolutions[0]["decision_type"] == "RECONCILE_AUTHORITY"
    assert hr0004_resolutions[0]["decision_id"] in active_human_resolutions
    assert hr0004_resolutions[0]["actor"]["actor_type"] == "HUMAN"
    assert hr0004_resolutions[0]["actor"]["role"] == "CURRENT_USER"
    assert hr0004["decision_authority"]["approval_type"] == (
        "GOAL_OR_PROCESS_AUTHORIZATION"
    )
    assert hr0004_resolutions[0]["authority_basis"]["approval_type"] == (
        "GOAL_OR_PROCESS_AUTHORIZATION"
    )

# ---------------------------------------------------------------------------
# r7 §8.1 permanent baseline transition-prefix manifest.
# ---------------------------------------------------------------------------
BASELINE_PREFIX_DIGEST = (
    "d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1"
)
BASELINE_PREFIX_LENGTHS = {
    "ALIAS-001": 1, "ALIAS-002": 1, "ALIAS-003": 1, "ALIAS-004": 1,
    "ALIAS-005": 1, "ALIAS-006": 1, "ALIAS-007": 1, "ALIAS-008": 1,
    "ALIAS-009": 1, "ALIAS-010": 1, "ALIAS-011": 1, "ALIAS-012": 1,
    "ALIAS-013": 1, "ALIAS-014": 1, "ALIAS-015": 1, "ALIAS-016": 1,
    "ALIAS-017": 1, "ALIAS-018": 1, "ALIAS-019": 1, "ALIAS-020": 1,
    "ALIAS-021": 1, "ALIAS-022": 1, "ALIAS-023": 1, "ALIAS-024": 1,
    "ALIAS-025": 1, "ALIAS-026": 1, "ALIAS-027": 1, "ALIAS-028": 1,
    "ALIAS-029": 1, "ALIAS-030": 1, "ALIAS-031": 1, "ALIAS-032": 1,
    "ALIAS-033": 1, "ALIAS-034": 1, "ALIAS-035": 1, "ALIAS-036": 1,
    "ALIAS-037": 1, "ALIAS-038": 1, "ALIAS-039": 1, "ALIAS-040": 1,
    "ALIAS-041": 1, "ALIAS-042": 1, "ALIAS-043": 1, "AUTH-DISP-001": 1,
    "AUTH-REG-001": 3, "DEF-01": 2, "DEF-02": 2, "DEF-03": 2, "DEF-04": 2,
    "DEF-05": 2, "DEF-06": 2, "DEF-07": 2, "DEF-08": 2, "DEF-09": 2,
    "DEF-10": 2, "DEF-11": 2, "DEF-12": 2, "DEF-13": 5, "DISP-6-1": 2,
    "DISP-6-2": 5, "DISP-6-3": 2, "DISP-6-4": 2, "DISP-6-5": 2, "DISP-6-6": 2,
    "DISP-6-7": 2, "DISP-6-8": 2, "DISP-6-9": 2, "DISP-G-1": 5, "DISP-G-2": 2,
    "DISP-G-3": 2, "DISP-G-4": 2, "DISP-G-5": 5, "DISP-M-1": 2, "DISP-M-2": 2,
    "DISP-M-3": 2, "DISP-M-4": 2, "DISP-M-5": 2, "DISP-M-6": 2, "DISP-M-7": 2,
    "DISP-M-8": 2, "DISP-M-9": 2, "DISP-R-1": 2, "DISP-R-2": 5, "DISP-R-3": 2,
    "DISP-R-4": 5, "DISP-R-5": 5, "DISP-T-1": 2, "DISP-T-2": 2, "DISP-T-3": 5,
    "DISP-T-4": 2, "DOC-01": 1, "DOC-02": 1, "DOC-03": 1, "DOC-04": 1,
    "DOC-05": 1, "DOC-06": 1, "PG-05-01": 1, "PG-05-02": 1, "PG-05-03": 1,
    "PG-05-04": 1, "PG-05-05": 1, "PG-05-06": 1, "PG-05-07": 1, "PG-05-08": 1,
    "PG-05-09": 1, "PG-05-10": 1, "PG-0A-01": 1, "PG-0A-02": 1, "PG-0A-03": 1,
    "PG-0A-04": 1, "PG-0A-05": 1, "PG-0A-06": 1, "PG-0A-07": 1, "PG-0A-08": 1,
    "PG-1-01": 1, "PG-1-02": 1, "PG-1-03": 1, "PG-1-04": 1, "PG-1-05": 1,
    "PG-1-06": 1, "PG-1-07": 1, "PG-1-08": 1, "PG-1-09": 1, "PG-1-10": 1,
    "PG-1-11": 1, "PG-2-01": 1, "PG-2-02": 1, "PG-2-03": 1, "PG-2-04": 1,
    "PG-2-05": 1, "PG-2-06": 1, "REG-A-01": 4, "REG-A-02": 4, "REG-A-03": 2,
    "REG-A-04": 7, "REG-A-05": 4, "REG-A-06": 7, "REG-A-07": 4, "REG-A-08": 4,
    "REG-A-09": 2, "REG-A-10": 5, "REG-A-11": 2, "REG-A-12": 2, "REG-A-13": 2,
    "REG-B-01": 4, "REG-B-02": 2, "REG-B-03": 7, "REG-B-04": 4, "REG-B-05": 4,
    "REG-B-06": 4, "REG-B-07": 4, "REG-B-08": 2, "REG-B-09": 5, "REG-B-10": 2,
    "REG-B-11": 2, "REG-B-12": 2, "REG-B-13": 2, "REG-B-14": 2, "REG-C-01": 2,
    "REG-C-02": 5, "REG-C-03": 2, "REG-C-04": 2, "REG-C-05": 4, "REG-C-06": 4,
    "REG-C-07": 2, "REG-C-08": 2, "REG-C-09": 4, "REG-C-10": 2, "REG-C-11": 5,
    "REG-C-12": 2, "REG-C-13": 2, "REG-C-14": 5, "REG-C-15": 2, "REG-C-16": 2,
    "REG-C-17": 2, "REG-C-18": 2, "REG-D-01": 4, "REG-D-02": 4, "REG-D-03": 2,
    "REG-D-04": 2, "REG-D-05": 2, "REG-E-01": 4, "REG-E-02": 4, "REG-E-03": 4,
    "REG-E-04": 4, "REG-E-05": 4, "REG-E-06": 4, "REG-E-07": 2, "REG-E-08": 2,
    "REG-E-09": 4, "REG-E-10": 2, "SCALE-SQLITE-01": 5, "SCALE-SQLITE-02": 5,
    "SCALE-SQLITE-03": 5, "SCALE-SQLITE-04": 5, "SCALE-WORKFLOW-01": 2,
    "SCALE-WORKFLOW-02": 2, "SCALE-WORKFLOW-03": 2, "SCALE-WORKFLOW-04": 2,
    "SEQ-01": 2, "SEQ-02": 2, "SEQ-03": 2, "SEQ-04": 5, "SEQ-05": 5,
    "SEQ-06": 2, "SEQ-07": 5, "SEQ-08": 2, "SEQ-09": 2, "SEQ-10": 2,
    "SEQ-11": 1,
}
assert len(BASELINE_PREFIX_LENGTHS) == 210
assert sum(BASELINE_PREFIX_LENGTHS.values()) == 454
assert set(BASELINE_PREFIX_LENGTHS) <= set(by_id)
assert set(by_id) - set(BASELINE_PREFIX_LENGTHS) == {
    "ALIAS-044", "AUTH-REG-002", "AUTH-REG-003"
}
baseline_prefix_projection = {}
for component_id, length in BASELINE_PREFIX_LENGTHS.items():
    history = by_id[component_id]["transition_history"]
    assert len(history) >= length
    baseline_prefix_projection[component_id] = history[:length]
assert canonical_sha256(baseline_prefix_projection) == BASELINE_PREFIX_DIGEST

# ---------------------------------------------------------------------------
# r7 §6.2/§8.1 transaction-only reconciliation mode.
# ---------------------------------------------------------------------------
if args.reconciliation_check:
    baseline_ledger_path = Path(args.reconciliation_baseline_ledger_path)
    baseline_human_path = Path(
        args.reconciliation_baseline_human_review_path
    )
    if not baseline_ledger_path.is_absolute():
        baseline_ledger_path = root / baseline_ledger_path
    if not baseline_human_path.is_absolute():
        baseline_human_path = root / baseline_human_path
    baseline_ledger_bytes = baseline_ledger_path.read_bytes()
    baseline_human_bytes = baseline_human_path.read_bytes()
    assert hashlib.sha256(baseline_ledger_bytes).hexdigest() == (
        "51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13"
    )
    assert hashlib.sha256(baseline_human_bytes).hexdigest() == (
        "54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702"
    )
    baseline_rows = [
        json.loads(line)
        for line in baseline_ledger_bytes.decode("utf-8").splitlines()
    ]
    baseline_by_id = {row["component_id"]: row for row in baseline_rows}
    assert len(baseline_by_id) == 210
    assert set(baseline_by_id) < set(by_id)
    assert set(by_id) - set(baseline_by_id) == {
        "ALIAS-044", "AUTH-REG-002", "AUTH-REG-003"
    }

    prefix_manifest = {
        component_id: len(row["transition_history"])
        for component_id, row in baseline_by_id.items()
    }
    assert prefix_manifest == BASELINE_PREFIX_LENGTHS
    baseline_projection = {
        component_id: row["transition_history"]
        for component_id, row in baseline_by_id.items()
    }
    assert canonical_sha256(baseline_projection) == BASELINE_PREFIX_DIGEST

    immutable_fields = (
        "source_path", "source_anchor", "source_start_line", "source_end_line",
        "authority_rank", "register_id", "source_title",
        "required_acceptance_text", "blueprint_phase", "priority",
        "dependencies", "activation_source_status", "source_status",
        "activation_record", "rejection_record", "gate_result",
        "verification_command", "verification_result", "verified_at",
        "open_findings", "blocked_scope", "security_exception_ids",
        "approval_records", "bead_ids", "roadmap_ref", "plan_refs",
        "implementation_refs", "tracked_work", "review_round",
    )
    evidence_only_targets = {
        "REG-A-01", "REG-A-02", "REG-A-03", "REG-A-04", "REG-A-05", "REG-A-06",
        "REG-A-08", "REG-A-09", "REG-A-11",
        "REG-B-02", "REG-B-03", "REG-B-04", "REG-B-05", "REG-B-07", "REG-B-08",
        "REG-B-09", "REG-B-10", "REG-B-13",
        "REG-C-01", "REG-C-02", "REG-C-03", "REG-C-05", "REG-C-06", "REG-C-07",
        "REG-C-10", "REG-C-12", "REG-C-13", "REG-C-18",
        "REG-D-02", "REG-D-04",
        "REG-E-06", "REG-E-07", "REG-E-08", "REG-E-09",
    }
    assert len(evidence_only_targets) == 34
    delivery_ordinal = {
        state: index for index, state in enumerate(delivery_progression)
    }
    for component_id, baseline_row in baseline_by_id.items():
        current_row = by_id[component_id]
        for field in immutable_fields:
            assert current_row[field] == baseline_row[field], (
                component_id, field
            )
        assert current_row["source_hash"] == baseline_row["source_hash"]
        assert current_row["text_digest"] == baseline_row["text_digest"]
        assert normalized_human_review_id(
            baseline_row["human_review_id"]
        ) <= human_review_links[component_id]
        if component_id in evidence_only_targets:
            for field in (
                "primary_spec", "disposition_refs", "gate_refs",
                "activation_predicate", "canonical_component_id",
                "required_approvals", "required_evidence", "delivery_status",
                "program_disposition",
            ):
                assert current_row[field] == baseline_row[field], (
                    component_id, field
                )
            assert current_row["scope_derivation"] == baseline_row[
                "scope_derivation"
            ]
        if component_id == "DEF-12":
            assert baseline_row["delivery_status"] == "SPEC_DRAFT"
            assert current_row["delivery_status"] == "INVENTORIED"
        else:
            baseline_state = baseline_row["delivery_status"]
            current_state = current_row["delivery_status"]
            if (
                baseline_state in delivery_ordinal
                and current_state in delivery_ordinal
            ):
                assert (
                    delivery_ordinal[current_state]
                    <= delivery_ordinal[baseline_state]
                ), component_id
            else:
                assert current_state == baseline_state, component_id

    baseline_human_text = baseline_human_bytes.decode("utf-8")
    baseline_payload_text = baseline_human_text.split(
        begin_marker, 1
    )[1].split(end_marker, 1)[0].strip()
    if baseline_payload_text.startswith("```json"):
        baseline_payload_text = baseline_payload_text[
            len("```json"): -len("```")
        ].strip()
    baseline_human_payload = json.loads(baseline_payload_text)
    baseline_entries = {
        entry["human_review_id"]: entry
        for entry in baseline_human_payload["entries"]
    }
    assert set(baseline_entries) == {"HR-0001", "HR-0002", "HR-0003"}
    assert baseline_human_payload["resolutions"] == []
    for entry_id, baseline_entry in baseline_entries.items():
        assert human_entries[entry_id] == baseline_entry
    assert set(human_entries) == set(baseline_entries) | {"HR-0004"}
    assert len(human_payload["resolutions"]) == 1

    register_state_counts = collections.Counter(
        row["source_status"] for row in register_rows
    )
    assert register_state_counts["Open"] == 45
    assert register_state_counts["Deferred"] == 15
    assert all(row["activation_record"] is None for row in rows)
    assert all(row["gate_result"] == "NOT_EVALUATED" for row in rows)
    assert all(row["verified_at"] is None for row in rows)
    assert all(row["verification_result"] == [] for row in rows)
    assert not matched_record_ids
    assert all(
        requirement["status"] == "UNRESOLVED"
        for row in rows
        for requirement in row["required_approvals"]
    )

    # r7 §3.2 bullet 11 / §8.1: every post-state (approval_type,
    # required_authority) pair must exist in the baseline ledger or be one of
    # §3.7's two authorized additions.
    baseline_authority_pairs = {
        (approval["approval_type"], approval["required_authority"])
        for row in baseline_rows
        for approval in row["required_approvals"]
    }
    for row in rows:
        for approval in row["required_approvals"]:
            pair = (approval["approval_type"], approval["required_authority"])
            assert (
                pair in baseline_authority_pairs
                or pair in AUTHORIZED_AUTHORITY_ADDITIONS
            ), pair

    # r7 §3.8: this transaction changes no ledger row for the role vocabulary,
    # so every inventory review is still PENDING and no review carries the
    # COMPLETE-only role keys.
    for row in rows:
        reviews = [
            row["approval_inventory_review"], row["evidence_inventory_review"]
        ]
        if isinstance(row["scope_derivation"], dict):
            reviews.append(row["scope_derivation"]["semantic_review"])
        for review in reviews:
            if review is None:
                continue
            assert review["status"] == "PENDING"
            assert not (role_binding_fields & set(review))
        assert row["verification_command"]["mode"] == "UNRESOLVED"
        assert row["verification_command"]["not_applicable_review"] is None

    # ---------------------------------------------------------------------
    # r7 §5.3/§8.1 structural reconciliation of the design/review bindings.
    # The question binds the review by digest; the reviewer model, effort, and
    # role-binding digest are compared between the review artifact and the
    # goal record only, because §5.2 cannot carry them.
    # ---------------------------------------------------------------------
    R7_DESIGN_RELPATH = (
        "docs/goals/reviews/ledger/"
        "equity-os-blueprint-ledger-remediation-design-r7.md"
    )
    R7_REVIEW_RELPATH = (
        "docs/goals/reviews/ledger/"
        "equity-os-blueprint-ledger-remediation-design-r7-review-r0.md"
    )
    GOAL_RELPATH = "docs/goals/equity-os-blueprint-completion.md"
    APPROVAL_HEADING = "## HR-0004 authority-reconciliation approval record"

    design_bytes = (root / R7_DESIGN_RELPATH).read_bytes()
    review_bytes = (root / R7_REVIEW_RELPATH).read_bytes()
    actual_design_sha256 = hashlib.sha256(design_bytes).hexdigest()
    actual_review_sha256 = hashlib.sha256(review_bytes).hexdigest()
    review_text = review_bytes.decode("utf-8")

    def unique_binding(text, pattern):
        found = re.findall(pattern, text, flags=re.MULTILINE)
        assert len(found) == 1, pattern
        return found[0]

    review_binding = {
        "design_path": unique_binding(
            review_text, r"^\| Reviewed design path \| `([^`]+)` \|$"
        ),
        "reviewed_input_sha256": unique_binding(
            review_text, r"^\| Reviewed-input SHA-256 \| `([0-9a-f]{64})` \|$"
        ),
        "role": unique_binding(
            review_text, r"^\| Reviewer role \| `([A-Z]+)` \|$"
        ),
        "model": unique_binding(
            review_text,
            r"^\| Reviewer model \(actually invoked\) \| `([^`]+)` \|$",
        ),
        "effort": unique_binding(
            review_text,
            r"^\| Reviewer effort \(actually invoked\) \| `([^`]+)` \|$",
        ),
        "role_binding_path": unique_binding(
            review_text, r"^\| `role_binding_path` \| `([^`]+)` \|$"
        ),
        "role_binding_sha256": unique_binding(
            review_text, r"^\| `role_binding_sha256` \| `([0-9a-f]{64})` \|$"
        ),
        "verdict": unique_binding(review_text, r"^Verdict: ([A-Z]+)$"),
    }
    assert review_binding["design_path"] == R7_DESIGN_RELPATH
    assert review_binding["reviewed_input_sha256"] == actual_design_sha256
    assert review_binding["verdict"] == "CLEAN"
    assert review_binding["role"] == "REVIEWER"
    assert review_binding["role_binding_path"] == ROLE_BINDING_PATH

    goal_text = (root / GOAL_RELPATH).read_text(encoding="utf-8")
    # Match the heading line itself; the same literal also appears inside this
    # embedded program, which the goal carries verbatim.
    heading_matches = list(re.finditer(
        "^" + re.escape(APPROVAL_HEADING) + "$", goal_text, flags=re.MULTILINE
    ))
    assert len(heading_matches) == 1
    # The record is followed by the preserved §"Activation record" section
    # (M-1: it is inserted before that heading, not appended at EOF), so the
    # record body ends at the next top-level heading.
    record_tail = goal_text[heading_matches[0].end():]
    next_heading = re.search(r"^## ", record_tail, flags=re.MULTILINE)
    record_text = (
        record_tail[:next_heading.start()] if next_heading else record_tail
    )
    record_fields = dict(
        re.findall(r"^\| ([^|]+?) \| `([^`]*)` \|$", record_text,
                   flags=re.MULTILINE)
    )
    question_blocks = re.findall(
        r"Exact completed decision question bytes as presented to the user:"
        r"\n\n```text\n(.*?)\n```",
        record_text,
        flags=re.DOTALL,
    )
    assert len(question_blocks) == 1
    question_text = question_blocks[0]

    assert record_fields["r7 design path"] == R7_DESIGN_RELPATH
    assert record_fields["r7 design SHA-256"] == actual_design_sha256
    assert record_fields["Independent review path"] == R7_REVIEW_RELPATH
    assert record_fields["Independent review SHA-256"] == actual_review_sha256
    assert record_fields["Review verdict"] == review_binding["verdict"]
    assert record_fields["Review reviewed-input SHA-256"] == (
        review_binding["reviewed_input_sha256"]
    )
    assert record_fields["Reviewer role"] == review_binding["role"]
    # Compared between the review artifact and the goal record only.
    assert record_fields["Reviewer model"] == review_binding["model"]
    assert record_fields["Reviewer effort"] == review_binding["effort"]
    assert record_fields["Reviewer role-binding path"] == (
        review_binding["role_binding_path"]
    )
    assert record_fields["Reviewer role-binding SHA-256"] == (
        review_binding["role_binding_sha256"]
    )
    assert record_fields["Exact 144-ID scope digest"] == (
        EXPECTED_HR0004_SCOPE_DIGEST
    )
    # r7 §5.1: "Byte-verbatim rendering is mandatory." The recorded question must
    # equal §5.2 rendered with exactly the two authorized substitutions and zero
    # other byte changes. Membership of the bound values is not that test: it
    # accepts appended, reordered, or reflowed bytes.
    R7_QUESTION_HEADING = "### 5.2 Exact decision question"
    design_text = design_bytes.decode("utf-8")
    assert design_text.count(R7_QUESTION_HEADING) == 1
    quoted_question_lines = []
    for quoted_line in design_text.split(
        R7_QUESTION_HEADING, 1
    )[1].splitlines():
        if quoted_line.startswith("> "):
            quoted_question_lines.append(quoted_line[2:])
        elif quoted_question_lines:
            break
    assert quoted_question_lines
    question_template = "\n".join(quoted_question_lines).strip()
    assert "<R7_SHA256>" in question_template
    assert "<R7_REVIEW_SHA256>" in question_template
    expected_question = question_template.replace(
        "<R7_SHA256>", actual_design_sha256
    ).replace("<R7_REVIEW_SHA256>", actual_review_sha256)
    assert "<R7_" not in expected_question
    assert question_text == expected_question, (
        "recorded question is not r7 5.2 rendered with exactly the two "
        "authorized substitutions"
    )
    # The five bound review values are carried by that exact rendering; they are
    # reasserted so a template edit that dropped one fails here too.
    for bound_value in (
        R7_DESIGN_RELPATH, actual_design_sha256, R7_REVIEW_RELPATH,
        actual_review_sha256, review_binding["verdict"], review_binding["role"],
        EXPECTED_HR0004_SCOPE_DIGEST,
    ):
        assert bound_value in question_text, bound_value

    # The recorded response bytes are exactly one block and are never empty.
    # Affirmativeness itself is decided by the migrator before any canonical
    # write (r7 §5.1): r7 §5.3 lists the reconciliation's compared fields and
    # the response is not among them, and the r7 §6.2 pre-approval rehearsal
    # necessarily builds a candidate from a provisional non-approval capture, so
    # asserting affirmativeness here would make that mandate unsatisfiable.
    response_blocks = re.findall(
        r"Exact user response bytes, verbatim and complete:\n\n"
        r"```text\n(.*?)\n```",
        record_text,
        flags=re.DOTALL,
    )
    assert len(response_blocks) == 1
    assert response_blocks[0].strip()
