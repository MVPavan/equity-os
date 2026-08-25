"""Public-seam tests for the RC-2/RC-3/RC-4 reconciliation transaction."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/equity_os_blueprint/reconcile_ledger_approval_contracts.py"


def load_module():
    """Load the transaction module through the same file path as its CLI."""
    spec = importlib.util.spec_from_file_location("reconcile_ledger", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestPreflightTests(unittest.TestCase):
    """The public manifest boundary fails closed before filesystem mutation."""

    def test_unresolved_placeholder_is_rejected(self) -> None:
        """A placeholder cannot be used as a canonical candidate digest."""
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            module = load_module()

            with self.assertRaisesRegex(module.ReconciliationError, "placeholder"):
                module.ensure_no_placeholders({"$placeholder": {"type": "DERIVED"}})


class CandidateBuilderTests(unittest.TestCase):
    """The deterministic candidate seam never writes canonical targets."""

    def test_builder_returns_exact_goal_and_structural_candidates(self) -> None:
        """The first two manifest targets are built in memory from live prestate."""
        module = load_module()
        manifest = (
            ROOT
            / "docs/goals/reviews/ledger/"
            "equity-os-blueprint-rc234-reconciliation-manifest-r1.json"
        )
        before = {
            path: (ROOT / path).read_bytes()
            for path in module.TARGET_ORDER[:2]
        }

        candidates = module.build_goal_and_structural_candidates(ROOT, manifest)

        self.assertEqual(set(candidates), set(module.TARGET_ORDER[:2]))
        self.assertTrue(candidates[module.TARGET_ORDER[0]].startswith(before[module.TARGET_ORDER[0]][:100]))
        self.assertNotEqual(candidates[module.TARGET_ORDER[0]], before[module.TARGET_ORDER[0]])
        self.assertNotEqual(candidates[module.TARGET_ORDER[1]], before[module.TARGET_ORDER[1]])
        self.assertEqual(
            {path: (ROOT / path).read_bytes() for path in module.TARGET_ORDER[:2]},
            before,
        )

    def test_candidate_extracts_to_the_exact_structural_bytes(self) -> None:
        """The real extractor reproduces the structural candidate from a disposable goal."""
        module = load_module()
        manifest = ROOT / (
            "docs/goals/reviews/ledger/"
            "equity-os-blueprint-rc234-reconciliation-manifest-r1.json"
        )
        candidates = module.build_goal_and_structural_candidates(ROOT, manifest)
        extractor = ROOT / "scripts/equity_os_blueprint/extract_goal_validators.py"

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            goal = workspace / "candidate-goal.md"
            structural = workspace / "structural.py"
            preimplementation = workspace / "preimplementation.py"
            terminal = workspace / "terminal.py"
            goal.write_bytes(candidates[module.TARGET_ORDER[0]])
            subprocess.run(
                [
                    "python3", str(extractor), "--goal-path", str(goal),
                    "--structural-output", str(structural),
                    "--preimplementation-output", str(preimplementation),
                    "--terminal-output", str(terminal),
                ],
                cwd=ROOT,
                check=True,
            )

            self.assertEqual(structural.read_bytes(), candidates[module.TARGET_ORDER[1]])
            self.assertEqual(
                hashlib.sha256(preimplementation.read_bytes()).hexdigest(),
                "f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013",
            )
            self.assertTrue(terminal.read_bytes())


class AuthorizationAndDynamicCandidateTests(unittest.TestCase):
    """Response-bound candidates are deterministic and never touch live targets."""

    def _bindings(self, module, manifest):
        """Use live hashes where available and explicit rehearsal values elsewhere."""
        static = module.build_goal_and_structural_candidates(ROOT, ROOT / module.R1_MANIFEST)
        bindings = {
            "question_issued_at": "2026-08-19T12:00:00Z",
            "validation_now": "2026-08-19T12:02:00Z",
            "goal_post_sha256": hashlib.sha256(static[module.TARGET_ORDER[0]]).hexdigest(),
            "structural_post_sha256": hashlib.sha256(static[module.TARGET_ORDER[1]]).hexdigest(),
            "evidence": {},
        }
        for item in manifest["human_review_construction"]["evidence_bindings"]:
            path = ROOT / item["path"]
            bindings["evidence"][item["evidence_ref_id"]] = {
                "path": item["path"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "NON_CANONICAL_STAND_IN:" + item["evidence_ref_id"],
                "role": "REVIEWER" if "REVIEW" in item["evidence_ref_id"] else "IMPLEMENTER",
                "model": "NON_CANONICAL_STAND_IN:model",
                "effort": "NON_CANONICAL_STAND_IN:effort",
                "verdict": "CLEAN",
                "reviewed_input_sha256": "NON_CANONICAL_STAND_IN:reviewed-input",
            }
        return bindings

    def test_authorization_renderer_and_response_validator_fail_closed(self) -> None:
        """Only the exact question, actor, affirmative answer, and UTC response pass."""
        module = load_module()
        manifest = module.load_manifest(ROOT / module.R1_MANIFEST)
        bindings = self._bindings(module, manifest)

        question = module.render_authorization_question(manifest, bindings, mode="rehearsal")
        self.assertEqual(question.count("<LEDGER_POST_SHA256>"), 1)
        self.assertEqual(question.count("<HUMAN_REVIEW_POST_SHA256>"), 1)
        self.assertNotIn("$placeholder", question)
        response = {
            "response_id": "rehearsal-0001",
            "question": question,
            "answer": module.EXACT_AFFIRMATIVE_ANSWER,
            "actor": {"identity_id": "user-123", "display_name": "Current User", "role": "CURRENT_USER"},
            "timestamp": "2026-08-19T12:01:00Z",
        }
        validated = module.validate_authenticated_response(response, question, bindings, mode="rehearsal")
        self.assertEqual(validated["actor"]["identity_id"], "user-123")
        with self.assertRaisesRegex(module.ReconciliationError, "answer"):
            module.validate_authenticated_response({**response, "answer": "yes"}, question, bindings, mode="rehearsal")
        with self.assertRaisesRegex(module.ReconciliationError, "replay"):
            module.validate_authenticated_response(response, question, bindings, mode="rehearsal", seen_response_ids={"rehearsal-0001"})

    def test_rehearsal_dynamic_candidates_preserve_canonical_prestate(self) -> None:
        """A response creates exactly the two dynamic candidates in memory."""
        module = load_module()
        manifest_path = ROOT / module.R1_MANIFEST
        manifest = module.load_manifest(manifest_path)
        bindings = self._bindings(module, manifest)
        question = module.render_authorization_question(manifest, bindings, mode="rehearsal")
        response = {
            "response_id": "rehearsal-0002",
            "question": question,
            "answer": module.EXACT_AFFIRMATIVE_ANSWER,
            "actor": {"identity_id": "user-123", "display_name": "Current User", "role": "CURRENT_USER"},
            "timestamp": "2026-08-19T12:01:00Z",
        }
        before = {path: (ROOT / path).read_bytes() for path in module.TARGET_ORDER[2:]}

        result = module.build_response_dependent_candidates(ROOT, manifest_path, bindings, response, mode="rehearsal")

        self.assertEqual(set(result.candidates), set(module.TARGET_ORDER[2:]))
        self.assertEqual(result.candidates[module.TARGET_ORDER[2]].count(b"\n"), 213)
        self.assertTrue(result.candidates[module.TARGET_ORDER[3]].endswith(b"\n"))
        self.assertEqual({path: (ROOT / path).read_bytes() for path in module.TARGET_ORDER[2:]}, before)
        self.assertEqual(set(result.authorization_outcomes), {"LEDGER_POST_SHA256", "HUMAN_REVIEW_POST_SHA256"})

    def test_dynamic_candidates_apply_exact_22_row_and_hr0006_contract(self) -> None:
        """The response changes only manifest rows and appends the closed HR pair."""
        module = load_module()
        manifest_path = ROOT / module.R1_MANIFEST
        manifest = module.load_manifest(manifest_path)
        bindings = self._bindings(module, manifest)
        question = module.render_authorization_question(manifest, bindings, mode="rehearsal")
        response = {
            "response_id": "rehearsal-0003", "question": question,
            "answer": module.EXACT_AFFIRMATIVE_ANSWER,
            "actor": {"identity_id": "user-123", "display_name": "Current User", "role": "CURRENT_USER"},
            "timestamp": "2026-08-19T12:01:00Z",
        }
        result = module.build_response_dependent_candidates(ROOT, manifest_path, bindings, response, mode="rehearsal")
        rows = [json.loads(line) for line in result.candidates[module.TARGET_ORDER[2]].splitlines()]
        expected = {item["component_id"]: item for item in manifest["components"]}
        affected = [row for row in rows if row["component_id"] in expected]
        self.assertEqual({row["component_id"] for row in affected}, set(manifest["transaction"]["affected_component_order"]))
        self.assertEqual(len(affected), 22)
        self.assertEqual(sum(len(row["transition_history"]) for row in rows), 649 + 22)
        self.assertTrue(all(row["transition_history"][-1]["transition_type"] == "AUTHORITY_RECONCILIATION" for row in affected))
        self.assertTrue(all(row["review_round"] == expected[row["component_id"]]["review_round_preserved"] for row in affected))
        self.assertEqual(sum(row["review_round"] == 4 for row in affected), 5)
        self.assertTrue(all(row["approval_inventory_review"]["status"] == "PENDING" for row in affected))
        self.assertTrue(all(row["evidence_inventory_review"]["status"] == "PENDING" for row in affected))
        human = result.candidates[module.TARGET_ORDER[3]].decode("utf-8")
        _, _, payload = module._human_payload_bounds(human)
        self.assertEqual(payload["entries"][-1]["human_review_id"], "HR-0006")
        self.assertEqual(payload["resolutions"][-1]["decision_id"], "HRD-0006-001")
        self.assertEqual(len(payload["entries"][-1]["evidence"]), 8)
        self.assertEqual(payload["entries"][-1]["scope"]["component_ids"], manifest["human_review_construction"]["sorted_component_scope"])

    def test_canonical_mode_rejects_rehearsal_bindings(self) -> None:
        """A labelled stand-in can never form a canonical authorization package."""
        module = load_module()
        manifest = module.load_manifest(ROOT / module.R1_MANIFEST)
        with self.assertRaisesRegex(module.ReconciliationError, "evidence binding"):
            module.render_authorization_question(manifest, self._bindings(module, manifest))


class TransactionTests(unittest.TestCase):
    """Preparation and replacement use isolated temporary repository replicas."""

    def test_prepare_writes_fsynced_journal_without_replacing_targets(self) -> None:
        """Prepare keeps all canonical preimages unchanged until execute."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            contents = {path: f"preimage:{path}\n".encode("utf-8") for path in (
                "docs/goals/equity-os-blueprint-completion.md",
                "scripts/equity_os_blueprint/validate_ledger_structural.py",
                "docs/goals/equity-os-blueprint-component-ledger.jsonl",
                "docs/goals/equity-os-blueprint-human-review-needed.md",
            )}
            targets = []
            for path, content in contents.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                os.chmod(target, 0o644)
                targets.append({"path": path, "sha256": __import__("hashlib").sha256(content).hexdigest(), "mode_octal": "0644"})
            subprocess.run(["git", "add", *contents], cwd=root, check=True)
            manifest = {
                "schema": "equity-os.rc234-reconciliation-manifest/v1",
                "prestate_bindings": {"canonical_targets": targets},
                "components": [{"component_id": f"C-{index}"} for index in range(22)],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            module = load_module()

            journal_path = module.prepare(root, manifest_path, {path: content.replace(b"preimage", b"candidate") for path, content in contents.items()}, rehearsal=True)

            self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
            self.assertEqual(module._load_json(journal_path)["state"], "PREPARED")

    def _isolated_transaction(self):
        """Create a real indexed repository with four literal preimages."""
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        contents = {
            path: f"preimage:{path}\n".encode("utf-8")
            for path in load_module().TARGET_ORDER
        }
        targets = []
        for path, content in contents.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            os.chmod(target, 0o644)
            targets.append({"path": path, "sha256": hashlib.sha256(content).hexdigest(), "mode_octal": "0644"})
        subprocess.run(["git", "add", *contents], cwd=root, check=True)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps({
            "schema": "equity-os.rc234-reconciliation-manifest/v1",
            "prestate_bindings": {"canonical_targets": targets},
            "components": [{"component_id": f"C-{index}"} for index in range(22)],
        }), encoding="utf-8")
        candidates = {path: content.replace(b"preimage", b"candidate") for path, content in contents.items()}
        return directory, root, manifest_path, contents, candidates

    def test_execute_commits_all_four_after_compare_and_swap(self) -> None:
        """A prepared isolated transaction reaches COMMITTED with exact candidates."""
        directory, root, manifest_path, contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            module.execute(root, manifest_path)
            self.assertEqual({path: (root / path).read_bytes() for path in contents}, candidates)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "COMMITTED")

    def test_fault_after_first_replacement_rolls_back_exact_preimages(self) -> None:
        """A crash after any first rename restores all bytes and modes in reverse order."""
        directory, root, manifest_path, contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            with self.assertRaises(KeyboardInterrupt):
                module.execute(root, manifest_path, fault_at="after:docs/goals/equity-os-blueprint-completion.md", fault=KeyboardInterrupt)
            self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "ROLLED_BACK")

    def test_recover_is_idempotent_and_nonterminal_journal_blocks_prepare(self) -> None:
        """Recovery follows only journaled preimages and can be safely re-run."""
        directory, root, manifest_path, contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            with self.assertRaisesRegex(module.ReconciliationError, "nonterminal journal"):
                module.prepare(root, manifest_path, candidates, rehearsal=True)
            module.recover(root)
            module.recover(root)
            self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "ROLLED_BACK")

    def test_all_declared_fault_boundaries_leave_prestate_or_recovery_required(self) -> None:
        """Every replacement boundary, postvalidation, and rollback fault is fail-closed."""
        module = load_module()
        boundaries = ["before:first", "postvalidation", *(f"after:{path}" for path in module.TARGET_ORDER)]
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                directory, root, manifest_path, contents, candidates = self._isolated_transaction()
                with directory:
                    module.prepare(root, manifest_path, candidates, rehearsal=True)
                    with self.assertRaises(SystemExit):
                        module.execute(root, manifest_path, fault_at=boundary, fault=SystemExit)
                    self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
                    self.assertEqual(module._load_json(module._journal_path(root))["state"], "ROLLED_BACK")
        directory, root, manifest_path, contents, candidates = self._isolated_transaction()
        with directory:
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            with self.assertRaises(KeyboardInterrupt):
                module.execute(root, manifest_path, fault_at={f"after:{module.TARGET_ORDER[0]}", f"rollback:{module.TARGET_ORDER[0]}"}, fault=KeyboardInterrupt)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "RECOVERY_REQUIRED")
            module.recover(root)
            self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "ROLLED_BACK")

    def test_cas_drift_preserves_the_concurrent_bytes(self) -> None:
        """A failed pre-replacement CAS never overwrites the concurrent target."""
        directory, root, manifest_path, contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            target = root / module.TARGET_ORDER[0]
            target.write_bytes(b"concurrent update\n")
            with self.assertRaisesRegex(module.ReconciliationError, "compare-and-swap"):
                module.execute(root, manifest_path)
            self.assertEqual(target.read_bytes(), b"concurrent update\n")
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "RECOVERY_REQUIRED")

    def test_dirty_path_byte_drift_blocks_commit_and_recovery_claim(self) -> None:
        """Identical porcelain status cannot conceal a changed unrelated dirty file."""
        directory, root, manifest_path, _contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            dirty = root / "notes.txt"
            dirty.write_text("first\n", encoding="utf-8")
            module.prepare(root, manifest_path, candidates, rehearsal=True)
            dirty.write_text("second\n", encoding="utf-8")
            with self.assertRaises(module.ReconciliationError):
                module.execute(root, manifest_path)
            self.assertEqual(module._load_json(module._journal_path(root))["state"], "RECOVERY_REQUIRED")

    def test_actual_sigint_and_sigterm_subprocesses_roll_back(self) -> None:
        """The CLI receives real OS termination signals inside the replacement window."""
        for signal_name in ("SIGINT", "SIGTERM"):
            with self.subTest(signal_name=signal_name):
                directory, root, manifest_path, contents, candidates = self._isolated_transaction()
                with directory:
                    module = load_module()
                    module.prepare(root, manifest_path, candidates, rehearsal=True)
                    result = subprocess.run([
                        "python3", str(MODULE_PATH), "execute", "--repo-root", str(root),
                        "--manifest", str(manifest_path), "--inject-signal-at",
                        f"after:{module.TARGET_ORDER[0]}", "--signal", signal_name,
                    ], capture_output=True, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual({path: (root / path).read_bytes() for path in contents}, contents)
                    self.assertEqual(module._load_json(module._journal_path(root))["state"], "ROLLED_BACK")

    def test_public_prepare_rejects_arbitrary_canonical_bytes(self) -> None:
        """Only the session-bound CLI can prepare a canonical journal."""
        directory, root, manifest_path, _contents, candidates = self._isolated_transaction()
        with directory:
            module = load_module()
            with self.assertRaisesRegex(module.ReconciliationError, "canonical prepare"):
                module.prepare(root, manifest_path, candidates)


if __name__ == "__main__":
    unittest.main()
