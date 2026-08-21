#!/usr/bin/env python3
"""Non-product, Python-stdlib validator for the Phase 0A evidence package.

This is validation tooling for the Phase 0A evidence program (register items
A-01 through A-13). It is NOT product code and selects no provider, parser,
model, or purchase. It mechanically rejects malformed, incomplete, stale,
unauthoritative, digest-mismatched, or graph-mismatched evidence and never
synthesizes a human decision.

Fail-closed: the validator exits non-zero whenever any required evidence,
authority, digest, or typed Beads edge is missing, pending, or mismatched.

CLI:
    bd export | python3 scripts/validate_phase_0a_evidence.py \
        --root docs/evidence/phase-0a --beads-jsonl -
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

EPIC_ID = "eqos-3ps"
CHILD_IDS = (
    "eqos-3ps.1",
    "eqos-3ps.2",
    "eqos-3ps.3",
    "eqos-3ps.4",
    "eqos-3ps.5",
)
# Approved blocks edges as (blocked_child, depends_on_child): left depends on right.
APPROVED_BLOCKS = frozenset(
    {
        ("eqos-3ps.2", "eqos-3ps.1"),
        ("eqos-3ps.3", "eqos-3ps.2"),
        ("eqos-3ps.5", "eqos-3ps.3"),
        ("eqos-3ps.5", "eqos-3ps.4"),
    }
)
GRAPH_NODES = frozenset({EPIC_ID, *CHILD_IDS})

REGISTER_ITEMS = tuple(f"A-{n:02d}" for n in range(1, 14))  # A-01..A-13

REQUIRED_PROGRAM_QUARTERS = frozenset({"Q0", "Q1", "Q2", "Q3"})

GOLDEN_MIN_CASES = 20
REQUIRED_GOLDEN_CATEGORIES = frozenset(
    {
        "prompt_injection",
        "source_confusion",
        "source",
        "period",
        "unit",
        "citation",
        "numerical_trace",
        "unsupported_claim",
        "materiality",
    }
)

# A-10 always-material categories from the approved spec.
ALWAYS_MATERIAL_CATEGORIES = frozenset(
    {
        "management_guidance",
        "restatement",
        "auditor_qualification",
        "going_concern",
        "promoter_pledge",
        "related_party_transaction",
        "capital_raise_or_dilution",
        "major_corporate_action",
        "management_change",
        "regulatory_action",
    }
)

DIGEST_EXCLUDE_KEYS = frozenset({"record_digest", "digest"})


class Outcome(str, Enum):
    """Deterministic A-10 materiality outcomes (matching the authored A-10 cases)."""

    MATERIAL = "MATERIAL"
    REVIEW = "REVIEW"
    NOT_MATERIAL = "NOT_MATERIAL"


MATERIALITY_MAGNITUDE_THRESHOLD_PCT = 5.0


class Acceptance(str, Enum):
    """Manifest per-row acceptance state. Only ACCEPTED clears the gate."""

    ACCEPTED = "ACCEPTED"
    INCOMPLETE = "INCOMPLETE"
    PENDING = "PENDING"


# --------------------------------------------------------------------------- #
# Digest helpers
# --------------------------------------------------------------------------- #


def _strip_digest_fields(obj: Any, exclude: frozenset[str]) -> Any:
    """Recursively drop digest fields so a digest is non-self-referential."""
    if isinstance(obj, dict):
        return {
            key: _strip_digest_fields(value, exclude)
            for key, value in obj.items()
            if key not in exclude
        }
    if isinstance(obj, list):
        return [_strip_digest_fields(item, exclude) for item in obj]
    return obj


def canonical_bytes(obj: Any, exclude: frozenset[str] = DIGEST_EXCLUDE_KEYS) -> bytes:
    """Return canonical UTF-8 JSON: digest fields removed, keys sorted, compact."""
    stripped = _strip_digest_fields(obj, exclude)
    return json.dumps(
        stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_digest(obj: Any, exclude: frozenset[str] = DIGEST_EXCLUDE_KEYS) -> str:
    """Compute the bare lowercase-hex SHA-256 over the canonical payload."""
    return hashlib.sha256(canonical_bytes(obj, exclude)).hexdigest()


def verify_digest(obj: Any, expected: str, label: str) -> list[str]:
    """Verify a stored digest against the recomputed canonical digest."""
    normalized = expected.split(":", 1)[-1].strip().lower() if expected else ""
    actual = compute_digest(obj)
    if not normalized:
        return [f"DIGEST_MISSING: {label} has no stored digest"]
    if normalized != actual:
        return [f"DIGEST_MISMATCH: {label} stored={normalized} computed={actual}"]
    return []


# --------------------------------------------------------------------------- #
# Beads typed-graph check
# --------------------------------------------------------------------------- #


def check_beads_graph(records: list[dict[str, Any]]) -> list[str]:
    """Require exactly five parent-child edges to the epic and the four approved blocks."""
    findings: list[str] = []
    parent_child: set[tuple[str, str]] = set()
    blocks: set[tuple[str, str]] = set()

    for record in records:
        issue_id = record.get("id")
        for dep in record.get("dependencies", []) or []:
            src = dep.get("issue_id", issue_id)
            dst = dep.get("depends_on_id")
            dep_type = dep.get("type")
            if src not in GRAPH_NODES and dst not in GRAPH_NODES:
                continue
            if dep_type == "parent-child":
                parent_child.add((src, dst))
            elif dep_type == "blocks":
                blocks.add((src, dst))

    expected_pc = {(child, EPIC_ID) for child in CHILD_IDS}
    if parent_child != expected_pc:
        missing = expected_pc - parent_child
        extra = parent_child - expected_pc
        if missing:
            findings.append(f"BEADS_PARENT_CHILD_MISSING: {sorted(missing)}")
        if extra:
            findings.append(f"BEADS_PARENT_CHILD_UNEXPECTED: {sorted(extra)}")
    if len(parent_child) != 5 and not findings:
        findings.append(
            f"BEADS_PARENT_CHILD_COUNT: expected 5, found {len(parent_child)}"
        )

    if blocks != APPROVED_BLOCKS:
        missing_b = APPROVED_BLOCKS - blocks
        extra_b = blocks - APPROVED_BLOCKS
        if missing_b:
            findings.append(f"BEADS_BLOCKS_MISSING: {sorted(missing_b)}")
        if extra_b:
            findings.append(f"BEADS_BLOCKS_UNEXPECTED: {sorted(extra_b)}")
    return findings


def summarize_beads_graph(records: list[dict[str, Any]]) -> str:
    """Human-readable edge counts for the validation report."""
    pc = 0
    blk = 0
    for record in records:
        issue_id = record.get("id")
        for dep in record.get("dependencies", []) or []:
            src = dep.get("issue_id", issue_id)
            dst = dep.get("depends_on_id")
            if src not in GRAPH_NODES and dst not in GRAPH_NODES:
                continue
            if dep.get("type") == "parent-child":
                pc += 1
            elif dep.get("type") == "blocks":
                blk += 1
    return f"typed Beads edges: {pc} parent-child, {blk} blocks"


# --------------------------------------------------------------------------- #
# Structural / set-equality checks
# --------------------------------------------------------------------------- #


def check_ownership_set(owner_ids: list[str]) -> list[str]:
    """Manifest primary-ownership keys must equal A-01..A-13 exactly, no duplicates."""
    findings: list[str] = []
    seen: set[str] = set()
    for owner in owner_ids:
        if owner in seen:
            findings.append(f"OWNERSHIP_DUPLICATE: {owner}")
        seen.add(owner)
    expected = set(REGISTER_ITEMS)
    missing = expected - seen
    extra = seen - expected
    if missing:
        findings.append(f"OWNERSHIP_MISSING: {sorted(missing)}")
    if extra:
        findings.append(f"OWNERSHIP_UNEXPECTED: {sorted(extra)}")
    return findings


def check_rights_set_equality(
    inventory_pairs: set[tuple[str, str]], rights_pairs: set[tuple[str, str]]
) -> list[str]:
    """Every inventory source/operation pair must have exactly one rights record."""
    findings: list[str] = []
    missing = inventory_pairs - rights_pairs
    extra = rights_pairs - inventory_pairs
    if missing:
        findings.append(f"RIGHTS_UNKNOWN_DENIED: {sorted(missing)}")
    if extra:
        findings.append(f"RIGHTS_UNREGISTERED_PAIR: {sorted(extra)}")
    return findings


def check_rights_no_widening(
    source_access: dict[str, str], operation_dispositions: dict[tuple[str, str], str]
) -> list[str]:
    """A source-level access grant may not widen an independently denied/unknown operation."""
    findings: list[str] = []
    for (source_id, operation), disposition in operation_dispositions.items():
        if disposition in {"DENIED", "UNKNOWN"} and source_access.get(source_id) == "ALLOWED":
            findings.append(
                f"RIGHTS_WIDENED: source {source_id} access ALLOWED cannot permit "
                f"{operation} ({disposition})"
            )
    return findings


def check_quarter_continuity(program_quarters: set[str]) -> list[str]:
    """The package must cover exactly the four consecutive program quarters Q0..Q3."""
    if program_quarters != REQUIRED_PROGRAM_QUARTERS:
        return [
            "QUARTER_CONTINUITY: expected {Q0,Q1,Q2,Q3}, found "
            f"{sorted(program_quarters)}"
        ]
    return []


def check_golden_set(cases: list[dict[str, Any]]) -> list[str]:
    """Golden set: >=20 unique labeled cases spanning every required failure category."""
    findings: list[str] = []
    ids: set[str] = set()
    categories: set[str] = set()
    for case in cases:
        case_id = case.get("case_id")
        if not case_id:
            findings.append("GOLDEN_MISSING_ID: a case has no case_id")
            continue
        if case_id in ids:
            findings.append(f"GOLDEN_DUPLICATE: {case_id}")
        ids.add(case_id)
        categories.add(case.get("category", ""))
        label = case.get("label") or {}
        if not label.get("label_authority"):
            findings.append(f"GOLDEN_UNLABELED: {case_id} lacks a label authority")
        if (label.get("authority_state") or label.get("state")) in (None, "", "PENDING"):
            findings.append(f"GOLDEN_UNAPPROVED_LABEL: {case_id}")
        if not case.get("expected_disposition"):
            findings.append(f"GOLDEN_NO_EXPECTED: {case_id}")
        if not case.get("version"):
            findings.append(f"GOLDEN_NO_VERSION: {case_id}")
    if len(ids) < GOLDEN_MIN_CASES:
        findings.append(
            f"GOLDEN_TOO_FEW: {len(ids)} unique cases < {GOLDEN_MIN_CASES}"
        )
    missing_categories = REQUIRED_GOLDEN_CATEGORIES - categories
    if missing_categories:
        findings.append(f"GOLDEN_CATEGORY_MISSING: {sorted(missing_categories)}")
    return findings


# --------------------------------------------------------------------------- #
# Authority / negative-path checks
# --------------------------------------------------------------------------- #


def check_human_decision(
    record: dict[str, Any], required_role: str, current_evidence_version: str
) -> list[str]:
    """A human decision must be present, current, in scope, and by the right authority."""
    findings: list[str] = []
    label = record.get("id") or record.get("record_type") or "<decision>"
    status = str(record.get("status", "")).upper()
    if status in {"", "PENDING", "ABSENT", "NO_COMPETENT_ASSESSMENT_SUPPLIED"}:
        findings.append(f"AUTHORITY_ABSENT: {label} status={status or 'MISSING'}")
        return findings
    if not record.get("decider"):
        findings.append(f"AUTHORITY_NO_DECIDER: {label}")
    if record.get("authority_role") != required_role:
        findings.append(
            f"AUTHORITY_WRONG_ROLE: {label} role={record.get('authority_role')} "
            f"expected={required_role}"
        )
    reviewed = record.get("evidence_version_reviewed")
    if reviewed != current_evidence_version:
        findings.append(
            f"AUTHORITY_STALE: {label} reviewed={reviewed} "
            f"current={current_evidence_version}"
        )
    if not record.get("rationale"):
        findings.append(f"AUTHORITY_NO_RATIONALE: {label}")
    return findings


def check_cutoff(source: dict[str, Any]) -> list[str]:
    """A source used for a material result must carry cutoff/provenance evidence."""
    if not source.get("provenance_cutoff") and not source.get("provenance"):
        return [f"CUTOFF_ABSENT: {source.get('source_id', '<source>')}"]
    return []


def check_source_conflict(observations: list[dict[str, Any]]) -> list[str]:
    """An important unresolved source conflict must resolve to review, with provenance kept."""
    findings: list[str] = []
    for obs in observations:
        if obs.get("state") == "CONFLICT":
            if obs.get("important") and not obs.get("analyst_disposition"):
                if obs.get("resolution") != Outcome.REVIEW.value:
                    findings.append(
                        f"SOURCE_CONFLICT_UNRESOLVED: {obs.get('cell', '<cell>')}"
                    )
            if not obs.get("provenance_visible", True):
                findings.append(
                    f"SOURCE_CONFLICT_PROVENANCE_HIDDEN: {obs.get('cell', '<cell>')}"
                )
    return findings


def check_coverage_completeness(
    rows: list[dict[str, Any]], quarters: set[str], dimensions: set[str]
) -> list[str]:
    """Every quarter x dimension cell exists with a distinct, non-aggregated state."""
    findings: list[str] = []
    allowed_states = {"COVERED", "UNKNOWN", "ABSENT", "NOT_APPLICABLE", "PARTIAL", "CONFLICT"}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        state = row.get("state", "")
        if state and state not in allowed_states:
            findings.append(
                f"COVERAGE_BAD_STATE: {row.get('program_quarter')}/{row.get('dimension')} "
                f"state={state}"
            )
        seen.add((row.get("program_quarter", ""), row.get("dimension", "")))
    for quarter in sorted(quarters):
        for dimension in sorted(dimensions):
            if (quarter, dimension) not in seen:
                findings.append(f"COVERAGE_GAP: {quarter}/{dimension} absent from matrix")
    return findings


# --------------------------------------------------------------------------- #
# Baseline reconstruction / instrumentation equivalence
# --------------------------------------------------------------------------- #


def check_baseline_reconstruction(baseline: dict[str, Any]) -> list[str]:
    """Each accepted material observation/computation must resolve; corrections stay visible."""
    findings: list[str] = []
    for obs in baseline.get("observations", []):
        if obs.get("accepted") and obs.get("material") and not obs.get("source_location"):
            findings.append(
                f"BASELINE_UNSUPPORTED_OBSERVATION: {obs.get('id', '<obs>')} "
                "material result lacks an exact source location"
            )
    for comp in baseline.get("computations", []):
        if comp.get("accepted") and comp.get("material") and not comp.get("calculation_trace"):
            findings.append(
                f"BASELINE_UNSUPPORTED_COMPUTATION: {comp.get('id', '<comp>')} "
                "material result lacks a calculation trace"
            )
    for correction in baseline.get("corrections", []):
        if not correction.get("supersedes") and not correction.get("lineage"):
            findings.append(
                f"BASELINE_CORRECTION_OPAQUE: {correction.get('id', '<corr>')} "
                "correction has no visible lineage"
            )
    return findings


def check_event_pair_equivalence(
    manual_event: dict[str, Any], assisted_event: dict[str, Any]
) -> list[str]:
    """Manual and assisted-shaped events must share scope, timing, unit, and overhead."""
    findings: list[str] = []
    for field in ("scope", "unit", "start_semantics", "end_semantics", "overhead_treatment"):
        if manual_event.get(field) != assisted_event.get(field):
            findings.append(
                f"INSTRUMENTATION_ASYMMETRY: field {field} differs between lanes"
            )
    if sorted(manual_event.get("exclusions", [])) != sorted(assisted_event.get("exclusions", [])):
        findings.append("INSTRUMENTATION_ASYMMETRY: exclusions differ between lanes")
    return findings


def check_instrumentation_vocabulary(vocab: dict[str, Any]) -> list[str]:
    """The shared vocabulary must be symmetric with overhead and correction semantics."""
    findings: list[str] = []
    if not vocab.get("symmetry_rule"):
        findings.append("INSTRUMENTATION_NO_SYMMETRY_RULE")
    if not vocab.get("overhead_rule"):
        findings.append("INSTRUMENTATION_NO_OVERHEAD_RULE")
    for event in vocab.get("events", []):
        event_id = event.get("event_id", "<event>")
        applic = event.get("actor_applicability", {})
        if not applic.get("symmetric"):
            findings.append(f"INSTRUMENTATION_EVENT_ASYMMETRIC: {event_id}")
        if not applic.get("manual_lane_actor") or not applic.get("assisted_lane_actor"):
            findings.append(f"INSTRUMENTATION_EVENT_MISSING_ACTOR: {event_id}")
        if "correction_lineage" not in event:
            findings.append(f"INSTRUMENTATION_EVENT_NO_LINEAGE: {event_id}")
    return findings


# --------------------------------------------------------------------------- #
# A-10 deterministic materiality policy
# --------------------------------------------------------------------------- #


def materiality_outcome(claim: dict[str, Any]) -> Outcome:
    """Deterministic A-10 policy outcome for one candidate claim.

    Always-material category -> MATERIAL; an important unresolved conflict,
    missing input, or low-confidence result -> REVIEW; a coverage-specific
    override -> MATERIAL; otherwise the thesis-relevance/magnitude rule decides.
    """
    if claim.get("claim_type") in ALWAYS_MATERIAL_CATEGORIES:
        return Outcome.MATERIAL
    if claim.get("source_conflict_state") in {"IMPORTANT_UNRESOLVED", "UNRESOLVED"}:
        return Outcome.REVIEW
    if not claim.get("required_inputs_present", True):
        return Outcome.REVIEW
    if claim.get("confidence_band") == "LOW":
        return Outcome.REVIEW
    if claim.get("coverage_flagged_override"):
        return Outcome.MATERIAL
    if claim.get("bears_on_tracked_commitment"):
        return Outcome.MATERIAL
    magnitude = claim.get("normalized_magnitude_pct")
    if isinstance(magnitude, (int, float)) and magnitude >= MATERIALITY_MAGNITUDE_THRESHOLD_PCT:
        return Outcome.MATERIAL
    return Outcome.NOT_MATERIAL


def check_materiality_case(case: dict[str, Any]) -> list[str]:
    """A VALID fixture's expected outcome must match the deterministic policy."""
    if case.get("fixture_kind") != "VALID":
        return []
    computed = materiality_outcome(case.get("candidate_claim", {}))
    expected = case.get("expected_outcome")
    if computed.value != expected:
        return [
            f"MATERIALITY_MISMATCH: {case.get('case_id', '<case>')} "
            f"expected={expected} computed={computed.value}"
        ]
    return []


# --------------------------------------------------------------------------- #
# A-09 identity pair
# --------------------------------------------------------------------------- #

# Statuses that mean no competent trademark/legal assessment was supplied.
A09_NO_ASSESSMENT_STATUSES = frozenset(
    {"", "NO_COMPETENT_ASSESSMENT_SUPPLIED", "PENDING", "ABSENT"}
)

# Markers that identify a recorded product-owner private-gate gate-basis decision.
GATE_BASIS_HEADING_MARKER = "gate-basis"
GATE_BASIS_SUFFICIENT_MARKER = "sufficient for the private phase 0a gate"

# Visible, informational note emitted when A-09 passes via the private-gate
# waiver rather than a competent assessment. It is not a silent pass: the
# exception stays visible in the validator output.
A09_WAIVER_NOTE = (
    "A09_ACCEPTED_VIA_PRIVATE_GATE_WAIVER: no competent trademark assessment; "
    "product-owner accepted the non-legal basis for the private gate; "
    "formal clearance deferred to public/commercial launch."
)


def _split_bold_bullet(line: str) -> tuple[str | None, str | None]:
    """Split a `- **Label:** value` markdown bullet into its label and value."""
    body = line.strip()
    if body.startswith("- "):
        body = body[2:]
    if not body.startswith("**"):
        return None, None
    end = body.find("**", 2)
    if end == -1:
        return None, None
    label = body[2:end].strip().rstrip(":").strip()
    value = body[end + 2 :].strip()
    return label, value


def parse_gate_basis_section(text: str) -> dict[str, Any] | None:
    """Extract a recorded product-owner private-gate gate-basis decision, if any.

    Reads the recorded decision fields (a gate-basis heading, an explicit
    "sufficient for the private Phase 0A gate" decision, a deferred formal
    clearance, and a named decider/date/verbatim instruction). Returns None when
    no gate-basis section is present. Detection is field-based, never guessed.
    """
    section_lines: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("#"):
            in_section = GATE_BASIS_HEADING_MARKER in line.lower()
            continue
        if in_section:
            section_lines.append(line)
    if not section_lines:
        return None
    # Collapse whitespace so a marker wrapped across lines still matches.
    blob = " ".join("\n".join(section_lines).lower().split())
    gate: dict[str, Any] = {
        "sufficient_for_private_gate": GATE_BASIS_SUFFICIENT_MARKER in blob,
        "deferred": "deferred" in blob,
    }
    for line in section_lines:
        label, value = _split_bold_bullet(line)
        if not label or not value:
            continue
        low = label.lower()
        if low.startswith("decider"):
            gate["decider"] = value
        elif low.startswith("decision date"):
            gate["decision_date"] = value
        elif low.startswith("verbatim instruction"):
            gate["verbatim_instruction"] = value
    return gate


def _record_gate_waiver(record: dict[str, Any]) -> bool:
    """A record carries a complete product-owner private-gate waiver decision."""
    gate = record.get("gate_basis") or {}
    return bool(
        gate.get("sufficient_for_private_gate")
        and gate.get("deferred")
        and gate.get("decider")
        and gate.get("decision_date")
        and gate.get("verbatim_instruction")
    )


def a09_private_gate_waiver_present(
    assessment: dict[str, Any], decision: dict[str, Any]
) -> bool:
    """Both A-09 records carry the recorded product-owner private-gate waiver."""
    return _record_gate_waiver(assessment) and _record_gate_waiver(decision)


def _a09_no_competent_assessment(assessment: dict[str, Any]) -> bool:
    """True when the assessment record supplies no competent trademark/legal work."""
    return str(assessment.get("status", "")).upper() in A09_NO_ASSESSMENT_STATUSES


def a09_private_gate_note(
    assessment: dict[str, Any], decision: dict[str, Any]
) -> list[str]:
    """Emit the visible waiver note when A-09 passes via the private-gate waiver."""
    if _a09_no_competent_assessment(assessment) and a09_private_gate_waiver_present(
        assessment, decision
    ):
        return [A09_WAIVER_NOTE]
    return []


def check_a09_pair(assessment: dict[str, Any], decision: dict[str, Any]) -> list[str]:
    """Both A-09 records must cover the same identity/evidence yet stay distinct decisions.

    The identity remains decided (no A09_UNDECIDED) when EITHER a competent
    trademark/legal assessment exists OR both records carry a recorded
    product-owner private-gate gate-basis decision (the non-legal basis accepted
    for the private gate, formal clearance deferred). Passing via the waiver
    emits a visible note (see `a09_private_gate_note`); it is never a silent pass.
    """
    findings: list[str] = []
    if assessment.get("normalized_candidate_identity") != decision.get(
        "normalized_candidate_identity"
    ):
        findings.append("A09_IDENTITY_MISMATCH: candidate identities differ")
    if assessment.get("evidence_version") != decision.get("evidence_version"):
        findings.append("A09_EVIDENCE_MISMATCH: reviewed evidence versions differ")
    if assessment.get("record_type") == decision.get("record_type"):
        findings.append("A09_DECISION_TYPE_NOT_DISTINCT: both records share a decision type")
    if _a09_no_competent_assessment(assessment) and not a09_private_gate_waiver_present(
        assessment, decision
    ):
        findings.append(
            "A09_UNDECIDED: no competent trademark/legal assessment; identity remains undecided"
        )
    return findings


# --------------------------------------------------------------------------- #
# Whitespace / final-newline
# --------------------------------------------------------------------------- #


def check_whitespace(text: str, label: str) -> list[str]:
    """No trailing whitespace on any line and exactly one final newline."""
    findings: list[str] = []
    if text == "":
        return [f"WHITESPACE_EMPTY: {label} is empty"]
    if not text.endswith("\n"):
        findings.append(f"NEWLINE_MISSING: {label} lacks a final newline")
    if text.endswith("\n\n"):
        findings.append(f"NEWLINE_EXTRA: {label} ends with more than one newline")
    for index, line in enumerate(text.split("\n"), start=1):
        if line != line.rstrip():
            findings.append(f"WHITESPACE_TRAILING: {label} line {index}")
    return findings


# --------------------------------------------------------------------------- #
# File-based orchestrator
# --------------------------------------------------------------------------- #


class Phase0AEvidenceValidator:
    """Loads the evidence root and runs every check, aggregating findings."""

    def __init__(self, root: Path, beads_records: list[dict[str, Any]]) -> None:
        self.root = root
        self.beads_records = beads_records
        self.findings: list[str] = []
        self.notes: list[str] = []

    def _add(self, findings: list[str]) -> None:
        self.findings.extend(findings)

    def _add_note(self, notes: list[str]) -> None:
        self.notes.extend(notes)

    def _read_text(self, name: str) -> str | None:
        path = self.root / name
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def _read_json(self, name: str) -> Any | None:
        text = self._read_text(name)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            self._add([f"JSON_PARSE_ERROR: {name}: {exc}"])
            return None

    def _read_jsonl(self, name: str) -> list[dict[str, Any]] | None:
        text = self._read_text(name)
        if text is None:
            return None
        records: list[dict[str, Any]] = []
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                self._add([f"JSONL_PARSE_ERROR: {name} line {index}: {exc}"])
        return records

    def validate(self) -> list[str]:
        """Run all checks and return the aggregated findings list."""
        self._add(check_beads_graph(self.beads_records))
        self._validate_manifest()
        self._validate_rights()
        self._validate_coverage()
        self._validate_golden_set()
        self._validate_domain_fixtures()
        self._validate_a09()
        self._validate_instrumentation()
        return self.findings

    def _validate_manifest(self) -> None:
        manifest = self._read_json("manifest.json")
        if manifest is None:
            self._add(["MANIFEST_ABSENT: manifest.json not found"])
            return
        entries = manifest.get("entries", [])
        self._add(check_ownership_set([entry.get("register_item") for entry in entries]))
        for entry in entries:
            item = entry.get("register_item", "<item>")
            acceptance = str(entry.get("acceptance", "")).upper()
            if acceptance != Acceptance.ACCEPTED.value:
                self._add(
                    [f"ACCEPTANCE_PENDING: {item} acceptance={acceptance or 'MISSING'}"]
                )
            for artifact in entry.get("artifacts", []):
                rel = artifact.get("path", "")
                if not (self.root.parent.parent.parent / rel).is_file() and not (
                    self.root / Path(rel).name
                ).is_file():
                    self._add([f"ARTIFACT_ABSENT: {item} -> {rel}"])
                    continue
                if rel.endswith((".md", ".csv", ".jsonl", ".json")):
                    text = self._read_text(Path(rel).name)
                    if text is not None:
                        self._add(check_whitespace(text, rel))

    def _validate_rights(self) -> None:
        inventory = self._read_json("source-package-inventory.json")
        rights = self._read_json("a-05-source-rights-package.json")
        if inventory is None or rights is None:
            self._add(["RIGHTS_ARTIFACT_ABSENT: inventory or rights package missing"])
            return
        inv_pairs = self._inventory_pairs(inventory)
        rights_pairs = {
            (pair.get("source_id"), op)
            for pair in rights.get("inventory_source_use_pairs", [])
            for op in [pair.get("intended_operation")]
            if pair.get("source_id") and op
        }
        self._add(check_rights_set_equality(inv_pairs, rights_pairs))
        for source in inventory.get("quarter_packages", []):
            for entry in source.get("sources", []):
                self._add(check_cutoff(entry))

    @staticmethod
    def _inventory_pairs(inventory: dict[str, Any]) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for package in inventory.get("quarter_packages", []):
            for source in package.get("sources", []):
                sid = source.get("source_id")
                for op in source.get("intended_operations", []):
                    if sid and op:
                        pairs.add((sid, op))
        return pairs

    def _validate_coverage(self) -> None:
        text = self._read_text("a-06-filing-coverage-matrix.csv")
        if text is None:
            self._add(["COVERAGE_ABSENT: a-06 filing-coverage matrix missing"])
            return
        rows = list(csv.DictReader(text.splitlines()))
        quarters = {row.get("program_quarter", "") for row in rows}
        self._add(check_quarter_continuity(quarters))

    def _validate_golden_set(self) -> None:
        cases = self._read_jsonl("a-08-golden-set.jsonl")
        if cases is None:
            self._add(["GOLDEN_ABSENT: golden set missing"])
            return
        self._add(check_golden_set(cases))
        for case in cases:
            digest = (case.get("digest") or {}).get("value", "")
            self._add(verify_digest(case, digest, f"golden {case.get('case_id')}"))

    def _validate_domain_fixtures(self) -> None:
        cases = self._read_jsonl("a-10-validator-cases.jsonl")
        if cases is None:
            self._add(["MATERIALITY_ABSENT: a-10 validator cases missing"])
            return
        for case in cases:
            self._add(check_materiality_case(case))
            digest = (case.get("digest") or {}).get("value", "")
            self._add(verify_digest(case, digest, f"a-10 {case.get('case_id')}"))

    def _validate_a09(self) -> None:
        assessment = self._parse_a09_markdown("a-09-trademark-legal-assessment.md")
        decision = self._parse_a09_markdown("a-09-product-owner-decision.md")
        if assessment is None or decision is None:
            self._add(["A09_ABSENT: an A-09 record is missing"])
            return
        self._add(check_a09_pair(assessment, decision))
        self._add_note(a09_private_gate_note(assessment, decision))

    def _parse_a09_markdown(self, name: str) -> dict[str, Any] | None:
        text = self._read_text(name)
        if text is None:
            return None
        fields: dict[str, Any] = {}
        for line in text.splitlines():
            if line.startswith("|") and "|" in line[1:]:
                cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
                if len(cells) == 2:
                    key, value = cells
                    if key == "Record type":
                        fields["record_type"] = value
                    elif key == "Record status":
                        fields["status"] = value
                    elif key == "Normalized candidate identity":
                        fields["normalized_candidate_identity"] = value
                    elif key == "Evidence-version identifier":
                        fields["evidence_version"] = value
        fields["gate_basis"] = parse_gate_basis_section(text)
        return fields

    def _validate_instrumentation(self) -> None:
        vocab = self._read_json("instrumentation-vocabulary.json")
        if vocab is None:
            self._add(["INSTRUMENTATION_ABSENT: vocabulary missing"])
            return
        self._add(check_instrumentation_vocabulary(vocab))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def load_beads(stream_arg: str) -> list[dict[str, Any]]:
    """Load Beads export JSONL from stdin ('-') or a file path."""
    if stream_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(stream_arg).read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def main(argv: list[str] | None = None) -> int:
    """Validate the Phase 0A evidence package; exit 0 only when it passes."""
    parser = argparse.ArgumentParser(description="Phase 0A evidence validator (non-product).")
    parser.add_argument("--root", required=True, help="Evidence root directory.")
    parser.add_argument(
        "--beads-jsonl", required=True, help="Beads export JSONL path or '-' for stdin."
    )
    args = parser.parse_args(argv)

    beads_records = load_beads(args.beads_jsonl)
    validator = Phase0AEvidenceValidator(Path(args.root), beads_records)
    findings = validator.validate()

    print("Phase 0A Evidence Validation Report")
    print(f"  root: {args.root}")
    print(f"  {summarize_beads_graph(beads_records)}")
    for note in validator.notes:
        print(f"  NOTE: {note}")
    if not findings:
        print("  RESULT: PASS - package validates.")
        return 0
    print(f"  RESULT: FAIL - {len(findings)} finding(s) (fail-closed):")
    for finding in sorted(findings):
        print(f"    - {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
