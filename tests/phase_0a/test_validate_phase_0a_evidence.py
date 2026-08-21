"""Unit and integration tests for the Phase 0A evidence validator.

All fixtures are minimal and synthetic: no real source content and no real
human decision are embedded. Tests assert fail-closed behavior on every
spec-required negative path plus the structural and integrated happy paths.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_phase_0a_evidence as validator  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# Digest
# --------------------------------------------------------------------------- #


class DigestTests(unittest.TestCase):
    def test_digest_is_non_self_referential(self) -> None:
        payload = {"b": 2, "a": 1, "digest": {"value": "ignored"}}
        digest = validator.compute_digest(payload)
        payload_no_digest = {"b": 2, "a": 1}
        self.assertEqual(digest, validator.compute_digest(payload_no_digest))

    def test_verify_digest_happy_and_mismatch(self) -> None:
        payload = {"case_id": "X", "digest": {"value": None}}
        good = validator.compute_digest(payload)
        self.assertEqual(validator.verify_digest(payload, good, "X"), [])
        self.assertTrue(validator.verify_digest(payload, "deadbeef", "X"))
        self.assertTrue(validator.verify_digest(payload, "", "X"))


# --------------------------------------------------------------------------- #
# Beads typed graph
# --------------------------------------------------------------------------- #


class BeadsGraphTests(unittest.TestCase):
    def test_valid_graph_has_no_findings(self) -> None:
        records = _load_jsonl(FIXTURES / "beads_valid.jsonl")
        self.assertEqual(validator.check_beads_graph(records), [])
        self.assertEqual(
            validator.summarize_beads_graph(records),
            "typed Beads edges: 5 parent-child, 4 blocks",
        )

    def test_extra_blocks_edge_is_rejected(self) -> None:
        records = _load_jsonl(FIXTURES / "beads_extra_block.jsonl")
        findings = validator.check_beads_graph(records)
        self.assertTrue(any("BEADS_BLOCKS_UNEXPECTED" in f for f in findings))

    def test_missing_parent_child_edge_is_rejected(self) -> None:
        records = _load_jsonl(FIXTURES / "beads_valid.jsonl")
        records = [r for r in records if r["id"] != "eqos-3ps.4"]
        # eqos-3ps.4 removed entirely -> its parent-child edge is gone.
        findings = validator.check_beads_graph(records)
        self.assertTrue(any("BEADS_PARENT_CHILD_MISSING" in f for f in findings))


# --------------------------------------------------------------------------- #
# Ownership set
# --------------------------------------------------------------------------- #


class OwnershipTests(unittest.TestCase):
    def test_exact_set_passes(self) -> None:
        self.assertEqual(
            validator.check_ownership_set(list(validator.REGISTER_ITEMS)), []
        )

    def test_duplicate_owner_rejected(self) -> None:
        ids = list(validator.REGISTER_ITEMS) + ["A-01"]
        findings = validator.check_ownership_set(ids)
        self.assertTrue(any("OWNERSHIP_DUPLICATE" in f for f in findings))

    def test_missing_and_extra_rejected(self) -> None:
        ids = [i for i in validator.REGISTER_ITEMS if i != "A-07"] + ["A-99"]
        findings = validator.check_ownership_set(ids)
        self.assertTrue(any("OWNERSHIP_MISSING" in f for f in findings))
        self.assertTrue(any("OWNERSHIP_UNEXPECTED" in f for f in findings))


# --------------------------------------------------------------------------- #
# Rights set equality + widening + cutoff
# --------------------------------------------------------------------------- #


class RightsTests(unittest.TestCase):
    def test_set_equality_passes(self) -> None:
        pairs = {("S1", "read"), ("S1", "cache")}
        self.assertEqual(validator.check_rights_set_equality(pairs, pairs), [])

    def test_unknown_operation_denied(self) -> None:
        inv = {("S1", "read"), ("S1", "cache")}
        rights = {("S1", "read")}
        findings = validator.check_rights_set_equality(inv, rights)
        self.assertTrue(any("RIGHTS_UNKNOWN_DENIED" in f for f in findings))

    def test_unregistered_fallback_rejected(self) -> None:
        inv = {("S1", "read")}
        rights = {("S1", "read"), ("S2", "read")}
        findings = validator.check_rights_set_equality(inv, rights)
        self.assertTrue(any("RIGHTS_UNREGISTERED_PAIR" in f for f in findings))

    def test_source_access_cannot_widen_denied_operation(self) -> None:
        findings = validator.check_rights_no_widening(
            {"S1": "ALLOWED"}, {("S1", "automation"): "DENIED"}
        )
        self.assertTrue(any("RIGHTS_WIDENED" in f for f in findings))

    def test_cutoff_absent_flagged(self) -> None:
        self.assertTrue(validator.check_cutoff({"source_id": "S1"}))
        self.assertEqual(
            validator.check_cutoff({"source_id": "S1", "provenance_cutoff": "2026-01-01"}),
            [],
        )


# --------------------------------------------------------------------------- #
# Quarter continuity + coverage
# --------------------------------------------------------------------------- #


class CoverageTests(unittest.TestCase):
    def test_four_quarter_continuity(self) -> None:
        self.assertEqual(
            validator.check_quarter_continuity({"Q0", "Q1", "Q2", "Q3"}), []
        )
        self.assertTrue(validator.check_quarter_continuity({"Q0", "Q1", "Q2"}))

    def test_incomplete_coverage_gap_flagged(self) -> None:
        rows = [
            {"program_quarter": "Q0", "dimension": "D1", "state": "COVERED"},
            {"program_quarter": "Q0", "dimension": "D2", "state": "UNKNOWN"},
        ]
        findings = validator.check_coverage_completeness(rows, {"Q0"}, {"D1", "D2", "D3"})
        self.assertTrue(any("COVERAGE_GAP" in f and "D3" in f for f in findings))

    def test_distinct_states_preserved(self) -> None:
        rows = [
            {"program_quarter": "Q0", "dimension": "D1", "state": "ABSENT"},
            {"program_quarter": "Q0", "dimension": "D2", "state": "NOT_APPLICABLE"},
        ]
        findings = validator.check_coverage_completeness(rows, {"Q0"}, {"D1", "D2"})
        self.assertEqual(findings, [])

    def test_bad_state_rejected(self) -> None:
        rows = [{"program_quarter": "Q0", "dimension": "D1", "state": "SCORE_0.9"}]
        findings = validator.check_coverage_completeness(rows, {"Q0"}, {"D1"})
        self.assertTrue(any("COVERAGE_BAD_STATE" in f for f in findings))


# --------------------------------------------------------------------------- #
# Golden set defects
# --------------------------------------------------------------------------- #


def _golden_case(case_id: str, category: str) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "expected_disposition": {"decision": "REJECT"},
        "label": {"label_authority": "expert", "authority_state": "APPROVED"},
        "version": "1.0.0",
    }


def _full_golden_set() -> list[dict]:
    cases = []
    categories = list(validator.REQUIRED_GOLDEN_CATEGORIES)
    for index in range(20):
        category = categories[index % len(categories)]
        cases.append(_golden_case(f"C-{index:03d}", category))
    return cases


class GoldenSetTests(unittest.TestCase):
    def test_valid_golden_set_passes(self) -> None:
        self.assertEqual(validator.check_golden_set(_full_golden_set()), [])

    def test_too_few_cases_rejected(self) -> None:
        findings = validator.check_golden_set(_full_golden_set()[:19])
        self.assertTrue(any("GOLDEN_TOO_FEW" in f for f in findings))

    def test_missing_category_rejected(self) -> None:
        cases = [_golden_case(f"C-{i:03d}", "prompt_injection") for i in range(20)]
        findings = validator.check_golden_set(cases)
        self.assertTrue(any("GOLDEN_CATEGORY_MISSING" in f for f in findings))

    def test_duplicate_and_unlabeled_rejected(self) -> None:
        cases = _full_golden_set()
        cases.append(_golden_case("C-000", "materiality"))  # duplicate id
        cases[1]["label"] = {"authority_state": "APPROVED"}  # no authority
        cases[2]["label"] = {"label_authority": "e", "authority_state": "PENDING"}
        findings = validator.check_golden_set(cases)
        self.assertTrue(any("GOLDEN_DUPLICATE" in f for f in findings))
        self.assertTrue(any("GOLDEN_UNLABELED" in f for f in findings))
        self.assertTrue(any("GOLDEN_UNAPPROVED_LABEL" in f for f in findings))


# --------------------------------------------------------------------------- #
# Authority / negative paths
# --------------------------------------------------------------------------- #


def _decision(**overrides: object) -> dict:
    base = {
        "id": "D-1",
        "status": "DECIDED",
        "decider": "named individual",
        "authority_role": "product_owner",
        "evidence_version_reviewed": "V1",
        "rationale": "documented rationale",
    }
    base.update(overrides)
    return base


class AuthorityTests(unittest.TestCase):
    def test_valid_decision_passes(self) -> None:
        self.assertEqual(
            validator.check_human_decision(_decision(), "product_owner", "V1"), []
        )

    def test_absent_decision_blocked(self) -> None:
        findings = validator.check_human_decision(
            _decision(status="PENDING"), "product_owner", "V1"
        )
        self.assertTrue(any("AUTHORITY_ABSENT" in f for f in findings))

    def test_stale_evidence_blocked(self) -> None:
        findings = validator.check_human_decision(
            _decision(evidence_version_reviewed="V0"), "product_owner", "V1"
        )
        self.assertTrue(any("AUTHORITY_STALE" in f for f in findings))

    def test_wrong_role_blocked(self) -> None:
        findings = validator.check_human_decision(
            _decision(authority_role="analyst"), "product_owner", "V1"
        )
        self.assertTrue(any("AUTHORITY_WRONG_ROLE" in f for f in findings))

    def test_missing_decider_or_rationale_blocked(self) -> None:
        findings = validator.check_human_decision(
            _decision(decider="", rationale=""), "product_owner", "V1"
        )
        self.assertTrue(any("AUTHORITY_NO_DECIDER" in f for f in findings))
        self.assertTrue(any("AUTHORITY_NO_RATIONALE" in f for f in findings))


class SourceConflictTests(unittest.TestCase):
    def test_important_unresolved_conflict_requires_review(self) -> None:
        obs = [{"cell": "Q0/revenue", "state": "CONFLICT", "important": True}]
        findings = validator.check_source_conflict(obs)
        self.assertTrue(any("SOURCE_CONFLICT_UNRESOLVED" in f for f in findings))

    def test_resolved_conflict_passes(self) -> None:
        obs = [
            {
                "cell": "Q0/revenue",
                "state": "CONFLICT",
                "important": True,
                "analyst_disposition": "kept structured source",
            }
        ]
        self.assertEqual(validator.check_source_conflict(obs), [])


# --------------------------------------------------------------------------- #
# Baseline reconstruction + instrumentation equivalence
# --------------------------------------------------------------------------- #


class BaselineTests(unittest.TestCase):
    def test_full_reconstruction_passes(self) -> None:
        baseline = {
            "observations": [
                {"id": "o1", "accepted": True, "material": True, "source_location": "p3"}
            ],
            "computations": [
                {"id": "c1", "accepted": True, "material": True, "calculation_trace": "a+b"}
            ],
            "corrections": [{"id": "x1", "supersedes": "o0"}],
        }
        self.assertEqual(validator.check_baseline_reconstruction(baseline), [])

    def test_material_observation_without_source_fails(self) -> None:
        baseline = {
            "observations": [{"id": "o1", "accepted": True, "material": True}],
        }
        findings = validator.check_baseline_reconstruction(baseline)
        self.assertTrue(any("BASELINE_UNSUPPORTED_OBSERVATION" in f for f in findings))

    def test_material_computation_without_trace_fails(self) -> None:
        baseline = {
            "computations": [{"id": "c1", "accepted": True, "material": True}],
        }
        findings = validator.check_baseline_reconstruction(baseline)
        self.assertTrue(any("BASELINE_UNSUPPORTED_COMPUTATION" in f for f in findings))

    def test_opaque_correction_fails(self) -> None:
        baseline = {"corrections": [{"id": "x1"}]}
        findings = validator.check_baseline_reconstruction(baseline)
        self.assertTrue(any("BASELINE_CORRECTION_OPAQUE" in f for f in findings))


class InstrumentationTests(unittest.TestCase):
    def test_equivalent_events_pass(self) -> None:
        event = {
            "scope": "one doc",
            "unit": "seconds",
            "start_semantics": "open",
            "end_semantics": "close",
            "overhead_treatment": "COUNTED",
            "exclusions": ["idle"],
        }
        self.assertEqual(validator.check_event_pair_equivalence(event, dict(event)), [])

    def test_asymmetric_events_fail(self) -> None:
        manual = {"scope": "one doc", "unit": "seconds", "exclusions": ["idle"]}
        assisted = {"scope": "one doc", "unit": "minutes", "exclusions": ["idle"]}
        findings = validator.check_event_pair_equivalence(manual, assisted)
        self.assertTrue(any("INSTRUMENTATION_ASYMMETRY" in f for f in findings))

    def test_vocabulary_structural_check(self) -> None:
        vocab = {
            "symmetry_rule": "same",
            "overhead_rule": "separate",
            "events": [
                {
                    "event_id": "reading",
                    "actor_applicability": {
                        "symmetric": True,
                        "manual_lane_actor": "ANALYST",
                        "assisted_lane_actor": "AGENT",
                    },
                    "correction_lineage": {},
                }
            ],
        }
        self.assertEqual(validator.check_instrumentation_vocabulary(vocab), [])
        broken = json.loads(json.dumps(vocab))
        broken["events"][0]["actor_applicability"]["symmetric"] = False
        self.assertTrue(validator.check_instrumentation_vocabulary(broken))


# --------------------------------------------------------------------------- #
# A-10 materiality outcomes
# --------------------------------------------------------------------------- #


class MaterialityTests(unittest.TestCase):
    def _claim(self, **overrides: object) -> dict:
        base = {
            "claim_type": "metric_change",
            "bears_on_tracked_commitment": False,
            "confidence_band": "HIGH",
            "coverage_flagged_override": False,
            "normalized_magnitude_pct": 0.3,
            "required_inputs_present": True,
            "source_conflict_state": "NONE",
        }
        base.update(overrides)
        return base

    def test_always_material_category(self) -> None:
        outcome = validator.materiality_outcome(self._claim(claim_type="restatement"))
        self.assertEqual(outcome, validator.Outcome.MATERIAL)

    def test_large_magnitude_material(self) -> None:
        outcome = validator.materiality_outcome(self._claim(normalized_magnitude_pct=7.5))
        self.assertEqual(outcome, validator.Outcome.MATERIAL)

    def test_small_magnitude_not_material(self) -> None:
        self.assertEqual(
            validator.materiality_outcome(self._claim(normalized_magnitude_pct=0.4)),
            validator.Outcome.NOT_MATERIAL,
        )

    def test_thesis_relevance_material(self) -> None:
        self.assertEqual(
            validator.materiality_outcome(self._claim(bears_on_tracked_commitment=True)),
            validator.Outcome.MATERIAL,
        )

    def test_conflict_missing_and_low_confidence_review(self) -> None:
        self.assertEqual(
            validator.materiality_outcome(
                self._claim(source_conflict_state="IMPORTANT_UNRESOLVED")
            ),
            validator.Outcome.REVIEW,
        )
        self.assertEqual(
            validator.materiality_outcome(self._claim(required_inputs_present=False)),
            validator.Outcome.REVIEW,
        )
        self.assertEqual(
            validator.materiality_outcome(self._claim(confidence_band="LOW")),
            validator.Outcome.REVIEW,
        )

    def test_coverage_override_material(self) -> None:
        self.assertEqual(
            validator.materiality_outcome(self._claim(coverage_flagged_override=True)),
            validator.Outcome.MATERIAL,
        )

    def test_defective_case_expected_outcome_flagged(self) -> None:
        case = {
            "case_id": "BAD",
            "fixture_kind": "VALID",
            "expected_outcome": "MATERIAL",
            "candidate_claim": self._claim(normalized_magnitude_pct=0.1),
        }
        findings = validator.check_materiality_case(case)
        self.assertTrue(any("MATERIALITY_MISMATCH" in f for f in findings))


# --------------------------------------------------------------------------- #
# A-09 identity pair
# --------------------------------------------------------------------------- #


class A09Tests(unittest.TestCase):
    def _pair(self) -> tuple[dict, dict]:
        assessment = {
            "record_type": "TRADEMARK_LEGAL_ASSESSMENT",
            "status": "ASSESSED",
            "normalized_candidate_identity": "Fundamentals",
            "evidence_version": "V1",
        }
        decision = {
            "record_type": "PRODUCT_OWNER_DECISION",
            "status": "SELECTED",
            "normalized_candidate_identity": "Fundamentals",
            "evidence_version": "V1",
        }
        return assessment, decision

    def test_valid_pair_passes(self) -> None:
        assessment, decision = self._pair()
        self.assertEqual(validator.check_a09_pair(assessment, decision), [])

    def test_identity_mismatch_flagged(self) -> None:
        assessment, decision = self._pair()
        decision["normalized_candidate_identity"] = "Funda"
        findings = validator.check_a09_pair(assessment, decision)
        self.assertTrue(any("A09_IDENTITY_MISMATCH" in f for f in findings))

    def test_same_decision_type_rejected(self) -> None:
        assessment, decision = self._pair()
        decision["record_type"] = "TRADEMARK_LEGAL_ASSESSMENT"
        findings = validator.check_a09_pair(assessment, decision)
        self.assertTrue(any("A09_DECISION_TYPE_NOT_DISTINCT" in f for f in findings))

    def test_absent_assessment_leaves_undecided(self) -> None:
        assessment, decision = self._pair()
        assessment["status"] = "NO_COMPETENT_ASSESSMENT_SUPPLIED"
        findings = validator.check_a09_pair(assessment, decision)
        self.assertTrue(any("A09_UNDECIDED" in f for f in findings))

    def _gate_basis(self) -> dict:
        return {
            "sufficient_for_private_gate": True,
            "deferred": True,
            "decider": "named product owner",
            "decision_date": "2026-08-21",
            "verbatim_instruction": "Approve all with defaults.",
        }

    def test_private_gate_waiver_passes_with_visible_note(self) -> None:
        assessment, decision = self._pair()
        assessment["status"] = "NO_COMPETENT_ASSESSMENT_SUPPLIED"
        assessment["gate_basis"] = self._gate_basis()
        decision["gate_basis"] = self._gate_basis()
        # No competent assessment, but a recorded waiver -> no A09_UNDECIDED.
        findings = validator.check_a09_pair(assessment, decision)
        self.assertFalse(any("A09_UNDECIDED" in f for f in findings))
        # The exception stays visible as an informational note.
        notes = validator.a09_private_gate_note(assessment, decision)
        self.assertTrue(any("A09_ACCEPTED_VIA_PRIVATE_GATE_WAIVER" in n for n in notes))

    def test_incomplete_waiver_still_undecided(self) -> None:
        assessment, decision = self._pair()
        assessment["status"] = "NO_COMPETENT_ASSESSMENT_SUPPLIED"
        gate = self._gate_basis()
        gate["deferred"] = False  # formal clearance not deferred -> incomplete waiver
        assessment["gate_basis"] = gate
        decision["gate_basis"] = gate
        findings = validator.check_a09_pair(assessment, decision)
        self.assertTrue(any("A09_UNDECIDED" in f for f in findings))
        self.assertEqual(validator.a09_private_gate_note(assessment, decision), [])

    def test_competent_assessment_needs_no_note(self) -> None:
        assessment, decision = self._pair()  # status ASSESSED -> competent
        self.assertEqual(validator.check_a09_pair(assessment, decision), [])
        self.assertEqual(validator.a09_private_gate_note(assessment, decision), [])


# --------------------------------------------------------------------------- #
# Whitespace
# --------------------------------------------------------------------------- #


class WhitespaceTests(unittest.TestCase):
    def test_clean_file_passes(self) -> None:
        text = (FIXTURES / "clean.txt").read_text()
        self.assertEqual(validator.check_whitespace(text, "clean.txt"), [])

    def test_trailing_and_missing_newline_flagged(self) -> None:
        text = (FIXTURES / "trailing_ws.txt").read_text()
        findings = validator.check_whitespace(text, "trailing_ws.txt")
        self.assertTrue(any("WHITESPACE_TRAILING" in f for f in findings))
        self.assertTrue(any("NEWLINE_MISSING" in f for f in findings))

    def test_extra_final_newline_flagged(self) -> None:
        findings = validator.check_whitespace("a\n\n", "x")
        self.assertTrue(any("NEWLINE_EXTRA" in f for f in findings))


# --------------------------------------------------------------------------- #
# Integrated file-based validator
# --------------------------------------------------------------------------- #


class IntegratedPackageBuilder:
    """Builds a minimal, fully synthetic, valid evidence package in a temp dir."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _write(self, name: str, text: str) -> None:
        if not text.endswith("\n"):
            text += "\n"
        (self.root / name).write_text(text, encoding="utf-8")

    def _write_json(self, name: str, obj: object) -> None:
        self._write(name, json.dumps(obj, indent=2, sort_keys=True))

    def _write_jsonl(self, name: str, rows: list[dict]) -> None:
        lines = [json.dumps(row, sort_keys=True) for row in rows]
        self._write(name, "\n".join(lines))

    def build(self) -> None:
        self._build_manifest()
        self._build_rights()
        self._build_coverage()
        self._build_golden()
        self._build_materiality()
        self._build_instrumentation()
        self._build_a09()
        self._build_placeholder_docs()

    def _build_manifest(self) -> None:
        entries = []
        artifact_map = {
            "A-01": ["a-01.md"],
            "A-02": ["a-02.md"],
            "A-03": ["a-03.md"],
            "A-04": ["a-04.md"],
            "A-05": ["a-05-source-rights-package.json"],
            "A-06": ["a-06-filing-coverage-matrix.csv"],
            "A-07": ["a-07.md"],
            "A-08": ["a-08-golden-set.jsonl"],
            "A-09": ["a-09-trademark-legal-assessment.md", "a-09-product-owner-decision.md"],
            "A-10": ["a-10-validator-cases.jsonl"],
            "A-11": ["a-11.md"],
            "A-12": ["a-12.md"],
            "A-13": ["a-13.md"],
        }
        for item in validator.REGISTER_ITEMS:
            entries.append(
                {
                    "register_item": item,
                    "acceptance": "ACCEPTED",
                    "artifacts": [
                        {"path": name, "version": "1.0.0", "digest": None}
                        for name in artifact_map[item]
                    ],
                }
            )
        self._write_json("manifest.json", {"entries": entries})

    def _build_rights(self) -> None:
        inventory = {
            "quarter_packages": [
                {
                    "program_quarter": q,
                    "sources": [
                        {
                            "source_id": f"SRC-{q}",
                            "intended_operations": ["read"],
                            "provenance_cutoff": "2026-01-01",
                        }
                    ],
                }
                for q in ("Q0", "Q1", "Q2", "Q3")
            ]
        }
        self._write_json("source-package-inventory.json", inventory)
        rights = {
            "inventory_source_use_pairs": [
                {"source_id": f"SRC-{q}", "intended_operation": "read"}
                for q in ("Q0", "Q1", "Q2", "Q3")
            ]
        }
        self._write_json("a-05-source-rights-package.json", rights)

    def _build_coverage(self) -> None:
        header = "program_quarter,dimension,state"
        rows = [
            f"{q},D1,COVERED" for q in ("Q0", "Q1", "Q2", "Q3")
        ]
        self._write("a-06-filing-coverage-matrix.csv", "\n".join([header, *rows]))

    def _build_golden(self) -> None:
        cases = []
        categories = sorted(validator.REQUIRED_GOLDEN_CATEGORIES)
        for index in range(20):
            case = {
                "case_id": f"G-{index:03d}",
                "category": categories[index % len(categories)],
                "expected_disposition": {"decision": "REJECT"},
                "label": {"label_authority": "expert", "authority_state": "APPROVED"},
                "version": "1.0.0",
                "digest": {"value": None},
            }
            case["digest"]["value"] = validator.compute_digest(case)
            cases.append(case)
        self._write_jsonl("a-08-golden-set.jsonl", cases)

    def _build_materiality(self) -> None:
        case = {
            "case_id": "M-001",
            "fixture_kind": "VALID",
            "expected_outcome": "MATERIAL",
            "candidate_claim": {
                "claim_type": "restatement",
                "bears_on_tracked_commitment": True,
                "confidence_band": "HIGH",
                "coverage_flagged_override": False,
                "normalized_magnitude_pct": None,
                "required_inputs_present": True,
                "source_conflict_state": "NONE",
            },
            "digest": {"value": None},
        }
        case["digest"]["value"] = validator.compute_digest(case)
        self._write_jsonl("a-10-validator-cases.jsonl", [case])

    def _build_instrumentation(self) -> None:
        vocab = {
            "symmetry_rule": "same",
            "overhead_rule": "separate",
            "events": [
                {
                    "event_id": "reading",
                    "actor_applicability": {
                        "symmetric": True,
                        "manual_lane_actor": "ANALYST",
                        "assisted_lane_actor": "AGENT",
                    },
                    "correction_lineage": {},
                }
            ],
        }
        self._write_json("instrumentation-vocabulary.json", vocab)

    def _build_a09(self) -> None:
        assessment = (
            "# A-09 Trademark Legal Assessment\n\n"
            "| Field | Value |\n| --- | --- |\n"
            "| Record type | `TRADEMARK_LEGAL_ASSESSMENT` |\n"
            "| Record status | `ASSESSED` |\n"
            "| Normalized candidate identity | `Fundamentals` |\n"
            "| Evidence-version identifier | `V1` |"
        )
        decision = (
            "# A-09 Product Owner Decision\n\n"
            "| Field | Value |\n| --- | --- |\n"
            "| Record type | `PRODUCT_OWNER_DECISION` |\n"
            "| Record status | `SELECTED` |\n"
            "| Normalized candidate identity | `Fundamentals` |\n"
            "| Evidence-version identifier | `V1` |"
        )
        self._write("a-09-trademark-legal-assessment.md", assessment)
        self._write("a-09-product-owner-decision.md", decision)

    def _build_placeholder_docs(self) -> None:
        for name in ("a-01", "a-02", "a-03", "a-04", "a-07", "a-11", "a-12", "a-13"):
            self._write(f"{name}.md", f"# Synthetic {name} placeholder")


class IntegratedValidatorTests(unittest.TestCase):
    def _records(self) -> list[dict]:
        return _load_jsonl(FIXTURES / "beads_valid.jsonl")

    def test_valid_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            IntegratedPackageBuilder(root).build()
            findings = validator.Phase0AEvidenceValidator(root, self._records()).validate()
            self.assertEqual(findings, [], msg=f"unexpected findings: {findings}")

    def test_pending_acceptance_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = IntegratedPackageBuilder(root)
            builder.build()
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["entries"][0]["acceptance"] = "PENDING"
            builder._write_json("manifest.json", manifest)
            findings = validator.Phase0AEvidenceValidator(root, self._records()).validate()
            self.assertTrue(any("ACCEPTANCE_PENDING" in f for f in findings))

    def test_missing_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            IntegratedPackageBuilder(root).build()
            (root / "a-08-golden-set.jsonl").unlink()
            findings = validator.Phase0AEvidenceValidator(root, self._records()).validate()
            self.assertTrue(any("ARTIFACT_ABSENT" in f or "GOLDEN_ABSENT" in f for f in findings))

    def test_tampered_golden_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = IntegratedPackageBuilder(root)
            builder.build()
            cases = _load_jsonl(root / "a-08-golden-set.jsonl")
            cases[0]["version"] = "9.9.9-tampered"  # invalidates stored digest
            builder._write_jsonl("a-08-golden-set.jsonl", cases)
            findings = validator.Phase0AEvidenceValidator(root, self._records()).validate()
            self.assertTrue(any("DIGEST_MISMATCH" in f for f in findings))


if __name__ == "__main__":
    unittest.main()
