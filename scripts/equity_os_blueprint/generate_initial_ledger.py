#!/usr/bin/env python3
"""Generate the canonical initial Equity-OS blueprint component ledger."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTER_PATH = "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md"
DISPOSITION_PATH = "docs/blueprint/funda-third-order-review-disposition-report.md"
GOAL_PATH = "docs/goals/equity-os-blueprint-completion.md"
LEDGER_PATH = ROOT / "docs/goals/equity-os-blueprint-component-ledger.jsonl"
HUMAN_PATH = ROOT / "docs/goals/equity-os-blueprint-human-review-needed.md"
SNAPSHOT_AT = "2026-08-13T02:49:11Z"
ACTIVATION_AT = "2026-08-13T01:06:47Z"

AUTHORITY_RANK = {REGISTER_PATH: 2, DISPOSITION_PATH: 3}
EXPECTED_HASH = {
    REGISTER_PATH: "26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164",
    DISPOSITION_PATH: "a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738",
}

SPEC_CONTRACT = {
    "S01": ("Product identity, operating, and distribution boundary", "docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md", ["A-01", "A-09", "E-08"], ["T-4"]),
    "S02": ("Source rights, providers, and consensus-data policy", "docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md", ["A-05", "C-13"], ["T-4", "R-3"]),
    "S03": ("Optional external-tool dependency due diligence", "docs/specs/equity-os-s03-external-tool-due-diligence.md", ["E-06", "E-07"], ["6.7"]),
    "S04": ("Execution trust-domain boundary", "docs/specs/equity-os-s04-execution-trust-domain.md", ["E-09"], ["T-4", "6.7"]),
    "S05": ("Discovery-company vertical slice, manual baseline, and bootstrap thesis", "docs/specs/equity-os-s05-discovery-company-vertical-slice.md", ["A-02", "A-03", "A-11"], ["G-4", "M-1", "6.8"]),
    "S06": ("Output, materiality, and observable-falsifier contract", "docs/specs/equity-os-s06-output-materiality-falsifiers.md", ["A-04", "A-10"], ["G-1", "G-5", "R-4", "6.2"]),
    "S07": ("Golden set, failure taxonomy, and reviewer-bias controls", "docs/specs/equity-os-s07-golden-set-failure-reviewer-controls.md", ["A-08", "B-08", "B-13"], ["M-6", "M-9", "6.6"]),
    "S08": ("Success metrics, workflow budgets, and operating capacity", "docs/specs/equity-os-s08-success-metrics-budgets-capacity.md", ["A-07", "A-12", "A-13"], ["M-8", "T-1", "T-2"]),
    "S09": ("Filing ingestion, immutable documents, point-in-time capture, and conditional audio", "docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md", ["A-06", "B-09", "C-02", "C-14"], ["M-9", "R-2"]),
    "S10": ("Source-of-truth matrix, evidence packages, and record-retention policy", "docs/specs/equity-os-s10-source-of-truth-evidence-retention.md", ["B-03", "C-11"], ["T-3", "R-5"]),
    "S11": ("Run manifest, knowledge cutoff, and layered reproducibility", "docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md", ["C-09", "C-15", "C-16"], ["G-1", "M-4", "6.9"]),
    "S12": ("Observation/fact identity, revision, and schema evolution", "docs/specs/equity-os-s12-observation-fact-identity-schema.md", ["B-05", "B-10", "B-11", "C-03"], ["M-2"]),
    "S13": ("Claim schema, vocabulary registries, and evidence validation", "docs/specs/equity-os-s13-claim-schema-vocabulary-evidence.md", ["B-06", "B-12", "C-04"], ["G-5", "M-3", "6.2"]),
    "S14": ("Fixed earnings-review workflow and feedback rework", "docs/specs/equity-os-s14-earnings-review-workflow-rework.md", ["B-01", "B-02", "B-14"], ["M-5", "R-5"]),
    "S15": ("Human claim review, correction, supersession, and promotion", "docs/specs/equity-os-s15-human-review-correction-promotion.md", ["C-05", "C-10"], ["M-5", "M-6", "6.6"]),
    "S16": ("Minimum deterministic compute", "docs/specs/equity-os-s16-minimum-deterministic-compute.md", ["B-07", "C-08"], ["G-1", "6.9"]),
    "S17": ("Entity/security master, relationships, and corporate actions", "docs/specs/equity-os-s17-entity-security-master-actions.md", ["C-06", "C-07", "C-17"], ["M-7", "6.3"]),
    "S18": ("MVP universe, analyst-review economics, and results-season throughput", "docs/specs/equity-os-s18-universe-review-economics-throughput.md", ["B-04", "C-01", "C-12", "C-18"], ["G-2", "G-3", "G-4", "M-8", "6.1"]),
    "S19": ("MemoryStore interface and conditional promotion transaction", "docs/specs/equity-os-s19-memory-store-promotion.md", ["D-01", "D-03"], ["R-1", "6.4"]),
    "S20": ("Memory benchmark, GBrain due diligence, and adoption decision", "docs/specs/equity-os-s20-memory-benchmark-gbrain.md", ["D-02", "D-04", "D-05"], ["R-1", "6.4"]),
    "S21": ("Conditional model-grade financial compute", "docs/specs/equity-os-s21-conditional-model-grade-compute.md", ["E-01"], []),
    "S22": ("Conditional stress-test-company expansion", "docs/specs/equity-os-s22-conditional-stress-test-companies.md", ["E-02"], []),
    "S23": ("Conditional bull/bear and forensic-review evaluation", "docs/specs/equity-os-s23-conditional-bull-bear-forensic-review.md", ["E-03"], []),
    "S24": ("Conditional event monitoring", "docs/specs/equity-os-s24-conditional-event-monitoring.md", ["E-04"], []),
    "S25": ("Controlled quant validation and historical-replay leakage", "docs/specs/equity-os-s25-quant-validation-historical-leakage.md", ["E-05", "E-10"], ["M-4", "6.5"]),
}

PHASE_GATE_RELATED = {
    "0A": [
        ["A-01"], ["A-05"], ["A-02"], ["A-06"], ["A-10", "A-13"],
        ["A-04"], ["A-12"], ["A-08"],
    ],
    "0.5": [
        ["A-11"], ["A-03", "B-02"], ["A-03", "B-04"], ["B-04", "B-13"],
        ["B-03"], ["B-11", "B-12"], ["B-05", "B-06"], ["B-14"],
        ["B-09"], ["A-08", "B-08"],
    ],
    "1": [
        ["A-10", "C-04"], ["A-10", "C-04"], ["B-05", "C-03"], ["C-08"],
        ["C-15"], ["C-08", "C-16"], ["C-10"], ["B-04", "C-12"],
        ["C-01", "C-18"], ["A-07", "A-13"], ["D-02", "E-03", "E-05", "E-09", "C-11"],
    ],
    "2": [
        ["D-02", "D-05"], ["D-02"], ["D-03"], ["D-03"], ["D-05"], ["D-02", "D-05"],
    ],
}

DISPOSITION_SPEC = {
    "G-1": "S06", "G-2": "S18", "G-3": "S18", "G-4": "S05", "G-5": "S06",
    "M-1": "S05", "M-2": "S12", "M-3": "S13", "M-4": "S11", "M-5": "S14",
    "M-6": "S07", "M-7": "S17", "M-8": "S08", "M-9": "S07",
    "T-1": "S08", "T-2": "S08", "T-3": "S10", "T-4": "S01",
    "R-1": "S20", "R-2": "S09", "R-3": "S02", "R-4": "S06", "R-5": "S10",
    "6.1": "S18", "6.2": "S06", "6.3": "S17", "6.4": "S20", "6.5": "S25",
    "6.6": "S07", "6.7": "S03", "6.8": "S05", "6.9": "S11",
}

DISPOSITION_REGISTERS = {
    "G-1": ["A-04", "C-09", "C-16"], "G-2": ["B-04"], "G-3": ["B-04", "C-12"],
    "G-4": ["A-02", "A-03", "B-02"], "G-5": ["A-10", "C-04"],
    "M-1": ["A-11"], "M-2": ["B-05", "B-11", "C-03"], "M-3": ["B-06", "B-12"],
    "M-4": ["C-15", "E-10"], "M-5": ["B-01", "B-14", "C-10"],
    "M-6": ["A-08", "B-13"], "M-7": ["C-17"], "M-8": ["A-13", "C-18"],
    "M-9": ["A-08", "B-08"], "T-1": ["A-12"], "T-2": ["A-13"],
    "T-3": ["B-03"], "T-4": ["A-01", "E-08", "E-09"], "R-1": ["D-02"],
    "R-2": ["A-06"], "R-3": ["A-05"], "R-4": ["A-04"], "R-5": ["B-03", "B-01"],
    "6.1": ["B-04"], "6.2": ["A-10", "C-04"], "6.3": ["C-17"],
    "6.4": ["D-02", "D-05"], "6.5": ["E-10"], "6.6": ["B-13"],
    "6.7": ["E-06", "E-07", "E-09"], "6.8": ["A-02", "B-02"], "6.9": ["C-16"],
}

REGISTER_APPROVALS = {
    "A-01": [("PRODUCT_OWNER_DECISION", "Product owner")],
    "A-02": [("PRODUCT_OWNER_DECISION", "Product owner")],
    "A-03": [("ANALYST_ACCEPTANCE", "Responsible analyst")],
    "A-04": [("PRODUCT_OWNER_DECISION", "Product owner"), ("ANALYST_ACCEPTANCE", "Responsible analyst")],
    "A-05": [("DATA_RIGHTS_APPROVAL", "Data-rights authority")],
    "A-08": [("NAMED_OWNER_COMMITMENT", "Golden-set owner")],
    "A-09": [("LEGAL_REVIEW", "Competent trademark or legal reviewer")],
    "A-10": [("DOMAIN_EXPERT_ACCEPTANCE", "Equity-research domain expert")],
    "A-11": [("ANALYST_ACCEPTANCE", "Responsible analyst")],
    "A-12": [("BUDGET_APPROVAL", "Budget owner"), ("CAPACITY_COMMITMENT", "Capacity owner")],
    "A-13": [("PRODUCT_OWNER_DECISION", "Product owner")],
    "B-02": [("ANALYST_ACCEPTANCE", "Responsible analyst")],
    "B-03": [("DOMAIN_EXPERT_ACCEPTANCE", "Data-domain authority")],
    "B-07": [("DOMAIN_EXPERT_ACCEPTANCE", "Calculation-domain authority")],
    "B-12": [("DOMAIN_EXPERT_ACCEPTANCE", "Vocabulary authority")],
    "C-01": [("CAPACITY_COMMITMENT", "Capacity owner")],
    "C-10": [("MEMORY_PROMOTION", "Responsible analyst")],
    "C-12": [("ANALYST_ACCEPTANCE", "Responsible analyst")],
    "C-13": [("DATA_RIGHTS_APPROVAL", "Data-rights authority"), ("PRODUCT_OWNER_DECISION", "Product owner")],
    "C-17": [("DOMAIN_EXPERT_ACCEPTANCE", "Entity-data authority")],
    "C-18": [("CAPACITY_COMMITMENT", "Capacity owner")],
    "D-04": [("LEGAL_REVIEW", "Competent dependency-license reviewer")],
    "D-05": [("PRODUCT_OWNER_DECISION", "Product owner for memory adoption")],
    "E-06": [("LEGAL_REVIEW", "Competent dependency-license reviewer"), ("DATA_RIGHTS_APPROVAL", "Data-rights authority")],
    "E-07": [("LEGAL_REVIEW", "Competent dependency-license reviewer")],
    "E-08": [("LEGAL_REVIEW", "Competent legal reviewer"), ("REGULATORY_REVIEW", "Competent regulatory reviewer"), ("DISTRIBUTION_APPROVAL", "Distribution owner")],
    "E-09": [("EXECUTION_TRUST_DOMAIN_APPROVAL", "Execution-boundary owner")],
}

HUMAN_EVIDENCE = {
    "ANALYST_ACCEPTANCE": "ANALYST", "DOMAIN_EXPERT_ACCEPTANCE": "DOMAIN",
    "MEMORY_PROMOTION": "ANALYST", "PROVIDER_AUTHORIZATION": "PROVIDER",
    "DATA_RIGHTS_APPROVAL": "DATA_RIGHTS", "LEGAL_REVIEW": "LEGAL",
    "REGULATORY_REVIEW": "REGULATORY", "BUDGET_APPROVAL": "BUDGET",
    "CAPACITY_COMMITMENT": "CAPACITY", "NAMED_OWNER_COMMITMENT": "NAMED_OWNER",
    "PRODUCTION_APPROVAL": "PRODUCTION", "DISTRIBUTION_APPROVAL": "DISTRIBUTION",
    "SECURITY_EXCEPTION": "SECURITY", "EXTERNAL_COORDINATION_APPROVAL": "EXTERNAL_COORDINATION",
}


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def lines(path: str) -> list[str]:
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


def span_digest(path: str, start: int, end: int) -> str:
    value = "\n".join(lines(path)[start - 1:end]).strip(" \t\n\r\f\v")
    return hashlib.sha256(value.encode()).hexdigest()


def spec(spec_id: str | None) -> dict | None:
    if spec_id is None:
        return None
    title, path, _, _ = SPEC_CONTRACT[spec_id]
    return {"spec_id": spec_id, "title": title, "path": path}


def pending_review(review_type: str) -> dict:
    return {
        "review_type": review_type, "status": "PENDING", "reviewer": None,
        "model": None, "effort": None, "verdict": None, "timestamp": None,
        "evidence_ref_ids": [], "reviewed_input_sha256": None,
        "reviewed_inventory_sha256": None,
    }


def evidence_ref(component_id: str, suffix: str, path: str, scope: str, *, start: int | None = None, end: int | None = None) -> dict:
    ref_id = "EV-" + re.sub(r"[^A-Za-z0-9]+", "-", f"{component_id}-{suffix}").strip("-").upper()
    if start is None:
        digest_mode, digest = "FILE_BYTES", file_sha256(path)
    else:
        assert end is not None
        digest_mode, digest = "UTF8_LINE_SPAN", span_digest(path, start, end)
    return {
        "evidence_ref_id": ref_id, "path": path, "scope": scope,
        "digest_mode": digest_mode, "start_line": start, "end_line": end,
        "content_sha256": digest, "captured_at": SNAPSHOT_AT,
    }


def required_approval(component_id: str, index: int, approval_type: str, authority: str, scope: str) -> dict:
    return {
        "approval_id": f"APR-{component_id.upper()}-{index:02d}",
        "approval_type": approval_type, "required_authority": authority,
        "scope": scope, "status": "UNRESOLVED", "actor": None,
        "timestamp": None, "evidence_ref_ids": [], "matched_record_id": None,
    }


def metric(metric_id: str, value_type: str, pointer: str) -> dict:
    return {
        "metric_id": metric_id, "value_type": value_type,
        "source_kind": "EVIDENCE_JSON", "evidence_ref_id": None,
        "json_pointer": pointer, "register_ids": [], "valid_until": None,
    }


def predicate(register_id: str, component_id: str) -> dict:
    definitions: dict[str, tuple[str, list[dict]]] = {
        "C-14": ("AP-C14-OFFICIAL-AUDIO-NEEDED", [metric("MTR-C14-OFFICIAL-AUDIO-REQUIRED", "BOOLEAN", "/official_audio_transcription_required"), metric("MTR-C14-SOURCE-OFFICIAL", "BOOLEAN", "/official_audio_source_confirmed"), metric("MTR-C14-RIGHTS-CURRENT", "BOOLEAN", "/source_provider_rights_current")]),
        "D-02": ("AP-D02-CURRENT-SCALE-BENCHMARK-READY", [metric("MTR-D02-C05-ACCEPTED", "BOOLEAN", "/memory/c05_accepted"), metric("MTR-D02-D01-ACCEPTED", "BOOLEAN", "/memory/d01_accepted"), metric("MTR-D02-D04-ACTIVATED", "BOOLEAN", "/memory/d04_activated"), metric("MTR-D02-BENCHMARK-READY", "BOOLEAN", "/memory/benchmark_ready")]),
        "D-03": ("AP-D03-PROMOTION-TRANSACTION-NEED", [metric("MTR-D03-D01-SOURCE-STATUS", "STRING", "/memory_promotion/d01_source_status"), metric("MTR-D03-ATOMIC-TRANSACTION-REQUIRED", "BOOLEAN", "/memory_promotion/atomic_transaction_required")]),
        "D-04": ("AP-D04-GBRAIN-DUE-DILIGENCE-NEED", [metric("MTR-D04-GBRAIN-DUE-DILIGENCE-REQUIRED", "BOOLEAN", "/memory/gbrain_due_diligence_required")]),
        "D-05": ("AP-D05-GBRAIN-ADOPTION-DECISION-READY", [metric("MTR-D05-D02-COMPLETE", "BOOLEAN", "/memory/d02_complete"), metric("MTR-D05-D04-COMPLETE", "BOOLEAN", "/memory/d04_complete"), metric("MTR-D05-ADOPTION-DECISION-READY", "BOOLEAN", "/memory/adoption_decision_ready")]),
        "E-01": ("AP-E01-MODEL-GRADE-COMPUTE-NEED", [metric("MTR-E01-C08-SOURCE-STATUS", "STRING", "/model_grade_compute/c08_source_status"), metric("MTR-E01-ACTIVATION-RECOMMENDED", "BOOLEAN", "/model_grade_compute/activation_recommended"), metric("MTR-E01-INPUTS-AND-OWNERS-READY", "BOOLEAN", "/model_grade_compute/inputs_and_owners_ready"), metric("MTR-E01-CAPACITY-AND-BUDGET-READY", "BOOLEAN", "/model_grade_compute/capacity_and_budget_ready")]),
        "E-02": ("AP-E02-STRESS-TEST-EXPANSION-READY", [metric("MTR-E02-C01-ACCEPTED", "BOOLEAN", "/stress_test/c01_accepted"), metric("MTR-E02-ARCHETYPES-READY", "BOOLEAN", "/stress_test/mandatory_archetypes_ready"), metric("MTR-E02-CAPACITY-READY", "BOOLEAN", "/stress_test/capacity_ready")]),
        "E-03": ("AP-E03-CHALLENGE-EVALUATION-READY", [metric("MTR-E03-C04-C05-ACCEPTED", "BOOLEAN", "/challenge/c04_c05_accepted"), metric("MTR-E03-BASELINE-READY", "BOOLEAN", "/challenge/senior_reviewer_baseline_ready"), metric("MTR-E03-BUDGET-READY", "BOOLEAN", "/challenge/budget_ready")]),
        "E-04": ("AP-E04-EVENT-MONITORING-NEEDED", [metric("MTR-E04-MONITORING-NEEDED", "BOOLEAN", "/monitoring/needed"), metric("MTR-E04-SOURCES-RIGHTS-CURRENT", "BOOLEAN", "/monitoring/sources_rights_current"), metric("MTR-E04-OWNER-BUDGET-READY", "BOOLEAN", "/monitoring/owner_budget_ready")]),
        "E-05": ("AP-E05-CONTROLLED-QUANT-VALIDATION-READY", [metric("MTR-E05-PIT-DATA-READY", "BOOLEAN", "/quant/point_in_time_data_ready"), metric("MTR-E05-E10-ACTIVE", "BOOLEAN", "/quant/e10_active"), metric("MTR-E05-BUDGET-READY", "BOOLEAN", "/quant/budget_ready")]),
        "E-06": ("AP-E06-OPENBB-EVALUATION", [metric("MTR-E06-REQUEST-PROPOSED", "BOOLEAN", "/external_tool/e06/request_proposed"), metric("MTR-E06-A05-RIGHTS-READY", "BOOLEAN", "/external_tool/e06/a05_rights_ready")]),
        "E-07": ("AP-E07-REUSE-EVALUATION", [metric("MTR-E07-REQUEST-PROPOSED", "BOOLEAN", "/external_tool/e07/request_proposed")]),
        "E-08": ("AP-E08-INTENDED-DISTRIBUTION-MODE", [metric("MTR-E08-PUBLIC-PROPOSED", "BOOLEAN", "/distribution/public_distribution_proposed"), metric("MTR-E08-PAID-PROPOSED", "BOOLEAN", "/distribution/paid_distribution_proposed"), metric("MTR-E08-PERSONALIZED-PROPOSED", "BOOLEAN", "/distribution/personalization_proposed"), metric("MTR-E08-EXECUTION-LINKED-PROPOSED", "BOOLEAN", "/distribution/execution_linkage_proposed")]),
        "E-09": ("AP-E09-EXECUTION-TRUST-DOMAIN-NEEDED", [metric("MTR-E09-E08-ACCEPTED", "BOOLEAN", "/execution/e08_accepted"), metric("MTR-E09-EXECUTION-LINKAGE-PROPOSED", "BOOLEAN", "/execution/linkage_proposed")]),
        "E-10": ("AP-E10-HISTORICAL-REPLAY-POLICY-NEEDED", [metric("MTR-E10-C15-ACCEPTED", "BOOLEAN", "/historical_replay/c15_accepted"), metric("MTR-E10-REPLAY-PLANNED", "BOOLEAN", "/historical_replay/planned")]),
    }
    if register_id.startswith("PG-"):
        predicate_id = "AP-" + re.sub(r"[^A-Z0-9]+", "-", component_id.upper()).strip("-")
        metrics = [metric("MTR-" + re.sub(r"[^A-Z0-9]+", "-", component_id.upper()).strip("-") + "-READY", "BOOLEAN", f"/phase_gates/{component_id}/activation_ready")]
    else:
        predicate_id, metrics = definitions[register_id]
    op = "ANY" if register_id == "E-08" else "ALL"
    expression = {"op": op, "args": [{"op": "COMPARE", "metric_id": item["metric_id"], "comparator": "EQ", "expected": True if item["value_type"] == "BOOLEAN" else "Accepted"} for item in metrics]}
    return {"predicate_id": predicate_id, "expression": expression, "metrics": metrics, "result": "UNKNOWN", "evaluated_at": None, "evaluation_sha256": None}


def base_row(component_id: str, kind: str, source_path: str, anchor: str, start: int, end: int, title: str, acceptance: str, *, register_id: str | None = None, blueprint_phase: str | None = None, priority: str | None = None, activation_status: str | None = None, source_status: str | None = None, dependencies: list[str] | None = None, spec_id: str | None = None, disposition_refs: list[str] | None = None, scope_rule: str | None = None, related: list[str] | None = None, authority_effect: str | None = None, program_disposition: str = "REQUIRED_NOW", activation_predicate: dict | None = None, canonical_component_id: str | None = None) -> dict:
    alias = kind == "derivative_alias"
    source_ev = evidence_ref(component_id, "source", source_path, f"Exact authoritative source occurrence for {component_id}", start=start, end=end)
    row = {
        "component_id": component_id, "canonical_component_id": canonical_component_id,
        "kind": kind, "source_path": source_path, "source_anchor": anchor,
        "source_start_line": start, "source_end_line": end,
        "source_hash": file_sha256(source_path), "text_digest": span_digest(source_path, start, end),
        "authority_rank": AUTHORITY_RANK[source_path], "register_id": register_id,
        "source_title": title, "required_acceptance_text": acceptance,
        "blueprint_phase": blueprint_phase, "priority": priority,
        "activation_source_status": activation_status, "source_status": source_status,
        "dependencies": dependencies or [], "primary_spec": spec(spec_id),
        "disposition_refs": disposition_refs or [], "gate_refs": [],
        "activation_predicate": activation_predicate,
        "scope_derivation": None if alias else {
            "rule": scope_rule, "related_register_ids": related or [],
            "authority_effect": authority_effect,
            "derived_program_disposition": program_disposition,
            "semantic_review": None if kind == "register_row" else pending_review("SCOPE"),
        },
        "activation_record": None, "rejection_record": None,
        "program_disposition": program_disposition, "delivery_status": "INVENTORIED",
        "gate_result": "NOT_EVALUATED", "bead_ids": [], "roadmap_ref": None,
        "plan_refs": [], "implementation_refs": [], "tracked_work": [],
        "required_evidence": [], "evidence_refs": [source_ev],
        "evidence_inventory_review": None if alias else pending_review("EVIDENCE"),
        "verification_command": {"mode": "UNRESOLVED", "commands": [], "not_applicable_review": None},
        "verification_result": [], "verified_at": None, "required_approvals": [],
        "approval_records": [], "approval_inventory_review": None if alias else pending_review("APPROVAL"),
        "review_round": 0, "open_findings": [], "human_review_id": None,
        "security_exception_ids": [], "blocked_scope": [], "transition_history": [],
        "transition_history_sha256": None,
    }
    if not alias:
        row["required_evidence"].append({
            "evidence_id": f"REQ-{component_id.upper()}-ACCEPTANCE",
            "description": f"Current proof satisfying: {acceptance}",
            "scope": f"{component_id} acceptance and delivery scope",
            "evidence_type": "ARTIFACT", "proof_mode": "CONTENT_HASH",
            "status": "UNRESOLVED", "evidence_ref_ids": [], "approval_ids": [],
        })
    return row


def controlled_state(row: dict) -> dict:
    direct = {
        "component_id", "canonical_component_id", "kind", "source_path", "source_anchor",
        "source_start_line", "source_end_line", "source_hash", "text_digest", "authority_rank",
        "register_id", "source_title", "required_acceptance_text", "blueprint_phase", "priority",
        "activation_source_status", "source_status", "dependencies", "primary_spec", "disposition_refs",
        "gate_refs", "activation_predicate", "activation_record", "rejection_record", "program_disposition",
        "delivery_status", "gate_result", "bead_ids", "roadmap_ref", "plan_refs", "implementation_refs",
        "tracked_work", "human_review_id", "security_exception_ids", "blocked_scope",
    }
    state = {key: row[key] for key in direct}
    scope = row["scope_derivation"]
    state["scope_definition"] = None if scope is None else {key: scope[key] for key in ("rule", "related_register_ids", "authority_effect")}
    return state


def transition(row: dict, field: str, new_value: object, transition_type: str) -> None:
    history = row["transition_history"]
    old_value = None if field == "CONTROLLED_STATE" else row[field]
    previous = history[-1]["entry_sha256"] if history else None
    entry = {
        "transition_id": f"TR-{row['component_id'].upper()}-{len(history):03d}",
        "sequence": len(history), "transition_type": transition_type, "field": field,
        "actor": {"actor_id": "codex-ledger-bootstrap", "actor_type": "AGENT", "role": "LEDGER_BOOTSTRAP_AUTHOR"},
        "invoked_model": "gpt-5.6-sol", "timestamp": SNAPSHOT_AT,
        "old_value": old_value, "new_value": new_value,
        "evidence_ref_ids": [row["evidence_refs"][0]["evidence_ref_id"]],
        "human_resolution_decision_id": None, "human_resolution_sha256": None,
        "previous_entry_sha256": previous, "entry_sha256": None,
    }
    entry["entry_sha256"] = canonical_sha256({key: value for key, value in entry.items() if key != "entry_sha256"})
    history.append(entry)
    if field != "CONTROLLED_STATE":
        row[field] = new_value


def finalize_history(row: dict) -> None:
    row["transition_history_sha256"] = canonical_sha256([entry["entry_sha256"] for entry in row["transition_history"]])


def register_rows() -> list[dict]:
    owner_by_register = {register_id: spec_id for spec_id, (_, _, ids, _) in SPEC_CONTRACT.items() for register_id in ids}
    text = lines(REGISTER_PATH)
    phase_by_prefix = {"A": "0A", "B": "0.5", "C": "1", "D": "2", "E": "3+"}
    rows = []
    for line_number, line in enumerate(text, 1):
        match = re.match(r"^\|\s*([A-E]-\d{2})\s*\|", line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        register_id = match.group(1)
        dependencies = [] if cells[4] == "—" else [item.strip() for item in cells[4].split(",")]
        spec_id = owner_by_register[register_id]
        deferred = cells[5] == "Deferred"
        row = base_row(
            f"REG-{register_id}", "register_row", REGISTER_PATH, register_id,
            line_number, line_number, cells[2], cells[3], register_id=register_id,
            blueprint_phase=phase_by_prefix[register_id[0]], priority=cells[1],
            activation_status=cells[5], source_status=cells[5], dependencies=dependencies,
            spec_id=spec_id, disposition_refs=SPEC_CONTRACT[spec_id][3],
            scope_rule="REGISTER_STATUS",
            program_disposition="CONDITIONAL_UNACTIVATED" if deferred else "REQUIRED_NOW",
            activation_predicate=predicate(register_id, f"REG-{register_id}") if deferred else None,
        )
        approvals = list(REGISTER_APPROVALS.get(register_id, []))
        if deferred:
            approvals.insert(0, ("PRODUCT_OWNER_DECISION", "Product owner authorized to activate deferred blueprint scope"))
        approvals.insert(0, ("DELEGATED_ARTIFACT_APPROVAL", "Delegated fresh Sol xhigh specification reviewer"))
        for index, (approval_type, authority) in enumerate(approvals, 1):
            scope = f"{register_id} under {spec_id}: {cells[2]}"
            requirement = required_approval(row["component_id"], index, approval_type, authority, scope)
            row["required_approvals"].append(requirement)
            if approval_type == "DELEGATED_ARTIFACT_APPROVAL":
                row["required_evidence"].append({
                    "evidence_id": f"REQ-{row['component_id']}-SPEC-REVIEW", "description": "Persisted clean fresh Sol xhigh review of the current specification bytes", "scope": scope,
                    "evidence_type": "REVIEW", "proof_mode": "CONTENT_HASH", "status": "UNRESOLVED", "evidence_ref_ids": [], "approval_ids": [],
                })
            elif approval_type in HUMAN_EVIDENCE:
                row["required_evidence"].append({
                    "evidence_id": f"REQ-{row['component_id']}-{approval_type}", "description": f"Current {approval_type} evidence from {authority}", "scope": scope,
                    "evidence_type": HUMAN_EVIDENCE[approval_type], "proof_mode": "TYPED_APPROVAL", "status": "UNRESOLVED", "evidence_ref_ids": [], "approval_ids": [requirement["approval_id"]],
                })
        rows.append(row)
    assert len(rows) == 60
    return rows


def phase_gate_rows() -> list[dict]:
    text = lines(REGISTER_PATH)
    headings = {124: "0A", 135: "0.5", 148: "1", 162: "2"}
    phase = None
    ordinal = 0
    rows = []
    for line_number, line in enumerate(text, 1):
        if line_number in headings:
            phase, ordinal = headings[line_number], 0
        elif phase and line.startswith("- "):
            ordinal += 1
            related = PHASE_GATE_RELATED[phase][ordinal - 1]
            component_id = f"PG-{phase.replace('.', '')}-{ordinal:02d}"
            conditional = all(item in {"C-14", "D-02", "D-03", "D-04", "D-05", *(f"E-{i:02d}" for i in range(1, 11))} for item in related)
            row = base_row(
                component_id, "phase_gate_clause", REGISTER_PATH, f"F-{phase}-{ordinal:02d}",
                line_number, line_number, f"Phase {phase} gate clause {ordinal}", line[2:].rstrip(";."),
                blueprint_phase=phase, scope_rule="RELATED_REGISTER_SCOPE", related=related,
                program_disposition="CONDITIONAL_UNACTIVATED" if conditional else "REQUIRED_NOW",
                activation_predicate=predicate(f"PG-{phase}", component_id) if conditional else None,
            )
            rows.append(row)
        elif phase and (line_number > 169 or (line.startswith("### ") and line_number not in headings)):
            phase = None
    assert len(rows) == 35
    return rows


def bullet_rows(kind: str, start: int, end: int, prefix: str, specs: list[str | None], *, disposition_refs: list[str] | None = None) -> list[dict]:
    rows = []
    ordinal = 0
    for line_number in range(start, end + 1):
        line = lines(REGISTER_PATH)[line_number - 1]
        if not line.startswith("- "):
            continue
        ordinal += 1
        rows.append(base_row(
            f"{prefix}-{ordinal:02d}", kind, REGISTER_PATH, f"{prefix}-{ordinal:02d}",
            line_number, line_number, f"{prefix} clause {ordinal}", line[2:].rstrip(";."),
            spec_id=specs[ordinal - 1], disposition_refs=disposition_refs,
            scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL", program_disposition="REQUIRED_NOW",
        ))
    return rows


def disposition_rows() -> list[dict]:
    text = lines(DISPOSITION_PATH)
    found: list[tuple[str, int, str]] = []
    for number, line in enumerate(text, 1):
        match = re.match(r"^### ([GMTR]-\d+) — (.+)$", line)
        if match is None:
            match = re.match(r"^### (6\.\d+) (.+)$", line)
        if match:
            found.append((match.group(1), number, match.group(2)))
    assert [item[0] for item in found] == [*(f"G-{i}" for i in range(1, 6)), *(f"M-{i}" for i in range(1, 10)), *(f"T-{i}" for i in range(1, 5)), *(f"R-{i}" for i in range(1, 6)), *(f"6.{i}" for i in range(1, 10))]
    rows = []
    for index, (item_id, start, title) in enumerate(found):
        next_start = found[index + 1][1] if index + 1 < len(found) else 400
        end = next_start - 1
        for candidate in range(start + 1, next_start):
            if text[candidate - 1] == "---" or text[candidate - 1].startswith("## "):
                end = candidate - 1
                break
        while end > start and not text[end - 1].strip():
            end -= 1
        rejected = item_id == "R-1"
        row = base_row(
            f"DISP-{item_id.replace('.', '-')}", "disposition_item", DISPOSITION_PATH, item_id,
            start, end, title, "\n".join(text[start - 1:end]).strip(), spec_id=DISPOSITION_SPEC[item_id],
            disposition_refs=[item_id], scope_rule="AUTHORITATIVE_OCCURRENCE",
            related=DISPOSITION_REGISTERS[item_id], authority_effect="REJECTED_PROPOSAL" if rejected else "ACTIVE_CONTROL",
            program_disposition="REJECTED_ACCOUNTED" if rejected else "REQUIRED_NOW",
        )
        row["required_approvals"].append(required_approval(row["component_id"], 1, "DELEGATED_ARTIFACT_APPROVAL", "Delegated fresh Sol xhigh specification reviewer", f"{item_id} under {DISPOSITION_SPEC[item_id]}"))
        rows.append(row)
    return rows


def other_canonical_rows() -> list[dict]:
    rows = [
        base_row("AUTH-REG-001", "authority_clause", REGISTER_PATH, "AUTHORITY-RULE-001", 23, 23, "Register authority rule", lines(REGISTER_PATH)[22], scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL"),
        base_row("AUTH-DISP-001", "authority_clause", DISPOSITION_PATH, "AUTHORITY-RULE-001", 41, 41, "Disposition authority rule", lines(DISPOSITION_PATH)[40], scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL"),
    ]
    for ordinal, line_number in enumerate(range(451, 461), 1):
        line = lines(DISPOSITION_PATH)[line_number - 1]
        register_ids = re.findall(r"[A-E]-\d{2}", line)
        owner = None
        if register_ids:
            owner = next(spec_id for spec_id, (_, _, ids, _) in SPEC_CONTRACT.items() if register_ids[0] in ids)
        rows.append(base_row(f"SEQ-{ordinal:02d}", "sequence_clause", DISPOSITION_PATH, f"SEQUENCE-{ordinal:02d}", line_number, line_number, f"Recommended sequence step {ordinal}", line, spec_id=owner, scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL"))
    rows.append(base_row("SEQ-11", "sequence_clause", DISPOSITION_PATH, "SEQUENCE-RATIONALE", 462, 462, "Sequence rationale", lines(DISPOSITION_PATH)[461], scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL"))
    doc_lines = [468, 470, 471, 472, 473, 475]
    for ordinal, line_number in enumerate(doc_lines, 1):
        rows.append(base_row(f"DOC-{ordinal:02d}", "document_strategy_clause", DISPOSITION_PATH, f"DOCUMENT-STRATEGY-{ordinal:02d}", line_number, line_number, f"Document strategy clause {ordinal}", lines(DISPOSITION_PATH)[line_number - 1], scope_rule="PROGRAM_WIDE_ACTIVE_CONTROL"))
    return rows


def aliases(canonical_by_id: dict[str, dict]) -> list[dict]:
    alias_specs = [
        (16, 18, "AUTH-DISP-001"),
        (20, 20, "DISP-G-1"), (21, 21, "DISP-6-1"), (22, 22, "DISP-G-5"),
        (23, 23, "DISP-6-3"), (24, 24, "DISP-6-6"), (25, 25, "DISP-6-5"),
        (26, 26, "DISP-R-1"), (27, 27, "DISP-6-7"), (28, 28, "DISP-6-8"),
        (34, 34, "DISP-G-1"), (35, 35, "DISP-M-1"), (36, 36, "DISP-T-1"),
        (37, 37, "DISP-R-1"), (38, 38, "AUTH-DISP-001"), (39, 39, "DISP-R-1"),
        (408, 408, "DISP-G-5"), (409, 409, "DISP-M-1"), (410, 410, "DISP-T-1"),
        (411, 411, "DISP-T-2"), (412, 412, "DISP-R-3"), (413, 413, "DISP-R-2"),
        (414, 414, "DISP-G-1"), (418, 418, "DISP-G-4"), (419, 419, "DISP-M-2"),
        (420, 420, "DISP-M-3"), (421, 421, "DISP-M-6"), (422, 422, "DISP-M-5"),
        (423, 423, "DISP-G-2"), (427, 427, "DISP-M-4"), (428, 428, "DISP-G-1"),
        (429, 429, "DISP-M-7"), (430, 430, "DISP-M-8"), (431, 431, "DISP-G-5"),
        (432, 432, "DISP-G-3"), (436, 436, "DISP-R-1"), (437, 437, "DISP-6-4"),
        (438, 438, "DISP-R-1"), (442, 442, "DISP-6-5"), (443, 443, "DISP-M-4"),
        (481, 481, "AUTH-DISP-001"), (483, 483, "DISP-R-1"), (487, 487, "AUTH-DISP-001"),
    ]
    rows = []
    for ordinal, (start, end, target) in enumerate(alias_specs, 1):
        assert target in canonical_by_id
        rows.append(base_row(
            f"ALIAS-{ordinal:03d}", "derivative_alias", DISPOSITION_PATH, f"DERIVATIVE-ALIAS-{ordinal:03d}",
            start, end, f"Derivative restatement {ordinal}", "\n".join(lines(DISPOSITION_PATH)[start - 1:end]).strip(),
            program_disposition="DERIVATIVE_ALIAS", canonical_component_id=target,
        ))
    return rows


def attach_spec_and_work_state(rows: list[dict]) -> None:
    by_spec: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["primary_spec"] is not None:
            by_spec[row["primary_spec"]["spec_id"]].append(row)
            path = row["primary_spec"]["path"]
            row["evidence_refs"].append(evidence_ref(row["component_id"], "spec-draft", path, f"Current draft specification bytes for {row['component_id']}"))
            if not any(item["approval_type"] == "DELEGATED_ARTIFACT_APPROVAL" for item in row["required_approvals"]):
                index = len(row["required_approvals"]) + 1
                scope = f"{row['component_id']} under {row['primary_spec']['spec_id']}"
                row["required_approvals"].append(required_approval(
                    row["component_id"], index, "DELEGATED_ARTIFACT_APPROVAL",
                    "Delegated fresh Sol xhigh specification reviewer", scope,
                ))
                row["required_evidence"].append({
                    "evidence_id": f"REQ-{row['component_id']}-SPEC-REVIEW",
                    "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
                    "scope": scope, "evidence_type": "REVIEW",
                    "proof_mode": "CONTENT_HASH", "status": "UNRESOLVED",
                    "evidence_ref_ids": [], "approval_ids": [],
                })

    authority_owner = next(row for row in rows if row["component_id"] == "AUTH-REG-001")
    transition(authority_owner, "bead_ids", ["eqos-0xb"], "REFERENCE_APPEND")
    transition(authority_owner, "tracked_work", [{
        "work_ref_id": "WORK-SPEC-EPIC", "work_type": "BEAD", "work_role": "SPEC_EPIC",
        "spec_id": None, "source_ref": "eqos-0xb", "required": True, "content_sha256": None,
    }], "REFERENCE_APPEND")

    for spec_id in sorted(SPEC_CONTRACT):
        owned = sorted(by_spec[spec_id], key=lambda row: row["component_id"])
        assert owned
        work_owner = next((row for row in owned if row["kind"] == "register_row"), owned[0])
        bead_id = f"eqos-0xb.{int(spec_id[1:])}"
        transition(work_owner, "bead_ids", [bead_id], "REFERENCE_APPEND")
        transition(work_owner, "tracked_work", [{
            "work_ref_id": f"WORK-{spec_id}-TASK", "work_type": "BEAD", "work_role": "SPEC_TASK",
            "spec_id": spec_id, "source_ref": bead_id, "required": True, "content_sha256": None,
        }], "REFERENCE_APPEND")

    for row in rows:
        if row["primary_spec"] is not None:
            transition(row, "delivery_status", "SPEC_DRAFT", "STATE_TRANSITION")


def attach_gate_refs(rows: list[dict]) -> None:
    by_register: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["kind"] == "phase_gate_clause":
            for register_id in row["scope_derivation"]["related_register_ids"]:
                by_register[register_id].append(row["component_id"])
    for row in rows:
        if row["kind"] == "register_row":
            row["gate_refs"] = by_register[row["register_id"]]


def attach_rejection_record(rows: list[dict]) -> None:
    row = next(item for item in rows if item["component_id"] == "DISP-R-1")
    spec_ev = next(item for item in row["evidence_refs"] if item["evidence_ref_id"].endswith("SPEC-DRAFT"))
    source_ev = row["evidence_refs"][0]
    row["rejection_record"] = {
        "rejection_record_id": "REJ-DISP-R-1", "component_id": row["component_id"],
        "register_id": None, "scope": "R-1 proposal to cancel D-02",
        "authority": "Pinned third-order disposition report", "actor": "pinned-blueprint-authority",
        "timestamp": ACTIVATION_AT, "evidence_ref_ids": [source_ev["evidence_ref_id"], spec_ev["evidence_ref_id"]],
        "rationale": "The authority rejects cancellation of D-02 and retains a current-scale benchmark with future reevaluation triggers.",
        "no_implementation_evidence_ref_ids": [spec_ev["evidence_ref_id"]],
        "approval_record_id": None, "human_resolution_decision_id": None,
        "human_resolution_sha256": None,
    }
    row["required_evidence"] = [
        {"evidence_id": "REQ-DISP-R-1-AUTHORITY", "description": "Pinned authority rejects the proposal to cancel D-02", "scope": "R-1 rejection authority", "evidence_type": "SOURCE", "proof_mode": "CONTENT_HASH", "status": "SATISFIED", "evidence_ref_ids": [source_ev["evidence_ref_id"]], "approval_ids": []},
        {"evidence_id": "REQ-DISP-R-1-NO-IMPLEMENTATION", "description": "Current S20 draft preserves D-02 as dormant and contains no implementation claim", "scope": "R-1 current no-implementation proof", "evidence_type": "ARTIFACT", "proof_mode": "CONTENT_HASH", "status": "SATISFIED", "evidence_ref_ids": [spec_ev["evidence_ref_id"]], "approval_ids": []},
    ]


def generate() -> list[dict]:
    for path, expected in EXPECTED_HASH.items():
        actual = file_sha256(path)
        if actual != expected:
            raise SystemExit(f"authority hash mismatch: {path}: {actual}")
    for _, path, _, _ in SPEC_CONTRACT.values():
        if not (ROOT / path).is_file():
            raise SystemExit(f"missing exact spec: {path}")

    rows = register_rows() + phase_gate_rows()
    rows += bullet_rows("first_release_deferral", 175, 187, "DEF", ["S05", "S20", "S14", "S23", "S24", "S21", "S02", "S25", "S25", "S04", "S04", "S20", "S10"])
    assert sum(row["kind"] == "first_release_deferral" for row in rows) == 13
    rows += bullet_rows("scale_trigger", 197, 200, "SCALE-SQLITE", ["S10"] * 4, disposition_refs=["R-5"])
    rows += bullet_rows("scale_trigger", 204, 207, "SCALE-WORKFLOW", ["S14"] * 4, disposition_refs=["R-5"])
    rows += disposition_rows() + other_canonical_rows()
    attach_gate_refs(rows)
    canonical_by_id = {row["component_id"]: row for row in rows}
    rows += aliases(canonical_by_id)

    attach_spec_and_work_state(rows)
    attach_rejection_record(rows)

    for row in rows:
        initial = controlled_state(row)
        # The snapshot precedes live spec/work references and draft progression.
        initial["bead_ids"] = []
        initial["tracked_work"] = []
        initial["delivery_status"] = "INVENTORIED"
        row["transition_history"] = []
        transition(row, "CONTROLLED_STATE", initial, "ACTIVATION_SNAPSHOT")
        # Reapply live post-snapshot state in closed-field order.
        live = controlled_state(row)
        # controlled_state now still contains the live row, while transition() did not mutate it for snapshot.
        if live["bead_ids"]:
            value = live["bead_ids"]
            row["bead_ids"] = []
            transition(row, "bead_ids", value, "REFERENCE_APPEND")
        if live["tracked_work"]:
            value = live["tracked_work"]
            row["tracked_work"] = []
            transition(row, "tracked_work", value, "REFERENCE_APPEND")
        if live["delivery_status"] != "INVENTORIED":
            row["delivery_status"] = "INVENTORIED"
            transition(row, "delivery_status", live["delivery_status"], "STATE_TRANSITION")
        finalize_history(row)

    counts = defaultdict(int)
    for row in rows:
        counts[row["kind"]] += 1
    assert counts["register_row"] == 60
    assert counts["phase_gate_clause"] == 35
    assert counts["first_release_deferral"] == 13
    assert counts["scale_trigger"] == 8
    assert counts["disposition_item"] == 32
    return rows


def main() -> int:
    rows = generate()
    LEDGER_PATH.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    payload = {"schema_version": 1, "entries": [], "resolutions": []}
    human = """# Equity-OS Blueprint Human Review Needed

This is the sole canonical human-review artifact for the activated blueprint goal.
At ledger bootstrap, real delivery approvals remain explicitly unresolved in the
ledger, but no human decision is yet actionable: the immediate blockers are the
required fresh Sol xhigh content-bound inventory reviews. Canonical entries are
added only when one answerable competent-human decision becomes actionable.

<!-- BEGIN CANONICAL HUMAN REVIEW JSON -->
""" + json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + """
<!-- END CANONICAL HUMAN REVIEW JSON -->
"""
    HUMAN_PATH.write_text(human, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
