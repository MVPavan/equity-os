# Governance Reset Switch Implementation Plan

**Origin:** `docs/specs/2026-08-19-governance-reset-supersession.md`, approved SHA-256 `8ef1baa26825966fd7a3eddb1910a2621afe6c3004819ecba916699e63788702`; its independent spec review is `docs/goals/reviews/equity-os-governance-reset-supersession-spec-review-r0.md`.
**Goal:** Replace the canonical blueprint-completion goal in one reviewed, normally committed governance switch so Phase 0A evidence work can proceed under v2 without weakening any product, architecture, phase-gate, or Deferred/Rejected control.
**Out of scope:** Product code, provider/tool selection, register or Architecture v2 changes, Phase 0A evidence completion, phase exits, a roadmap/workstream, an archive manifest, a per-file digest system, and another plan or review artifact.
**Constraints:** The switch changes governance mechanics only.
**Constraints:** The v2 decision register remains operational authority; the third-order disposition report remains its interpretation and audit trail; approved Architecture v2 remains the architecture of record.
**Constraints:** Working-tree edits are candidates only. The replacement becomes current when the normal switch commit records it. A failed commit creates no switch.
**Constraints:** The future final switch diff receives exactly one independent `HIGH` review.
**Tracking:** Standalone task `eqos-fga`; do not create an epic, child Beads, roadmap, or workstream.

## File map

| Path | Responsibility |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | The only implementation file: replace the former 5,918-line process contract in place with the concise supersession and current-process contract. |
| `docs/specs/2026-08-19-governance-reset-supersession.md` | Read-only exact requirements and acceptance authority. |
| `docs/goals/reviews/equity-os-governance-reset-supersession-spec-review-r0.md` | Read-only record of the issues resolved by the approved spec; prevents reintroducing lifecycle duality, archive inventories, duplicate status ledgers, hash manifests, or review loops. |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | Read-only sole authority for register decisions, statuses, dependencies, evidence requirements, Deferred/Rejected state, and §F phase gates. |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | Read-only interpretation and audit trail subordinate to v2. |
| `docs/goals/architecture/equity-os-architecture-of-record-v2.html` | Read-only approved architecture of record. |
| `docs/goals/architecture/architecture-brief-v2.md` | Read-only companion brief, including the first-release/later split and sourcing constraints. |
| `docs/goals/architecture/equity-os-architecture-of-record-v2-review-r3.md` | Read-only clean independent Architecture v2 review. |

Beads `eqos-jce` and `eqos-9x8` are read-only decision evidence for Architecture v2 approval and the three-tier sourcing direction. They are referenced by ID through `bd show`; their generated storage is not hand-edited or staged as part of the switch.

### Task 1: Produce the canonical supersession candidate

Goal: `docs/goals/equity-os-blueprint-completion.md` is a concise current contract that visibly supersedes the former process while preserving every authority and safety boundary required by the approved spec.

Files:
- Create: None
- Modify: `docs/goals/equity-os-blueprint-completion.md`
- Test: `docs/specs/2026-08-19-governance-reset-supersession.md`, `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`, `docs/blueprint/funda-third-order-review-disposition-report.md`, `docs/goals/architecture/equity-os-architecture-of-record-v2.html`, `docs/goals/architecture/architecture-brief-v2.md`, `docs/goals/architecture/equity-os-architecture-of-record-v2-review-r3.md`

Interfaces:
- Consumes: the approved `GovernanceResetSupersession` Markdown contract; live Bead decisions `eqos-jce` and `eqos-9x8`; unchanged v2, disposition, and Architecture v2 authority documents.
- Produces: one `GovernanceResetContract` Markdown document at the existing canonical goal path.

Approach: Dispatch one bounded Implementer through Codex CLI using `gpt-5.6-terra` at `high` effort with `workspace-write`, ownership of only the canonical goal, and instructions to preserve all unrelated dirty-tree changes. Replace the file in place; do not edit its former machinery piecemeal. Put the supersession statement first, then name the continuing authority hierarchy and Git-native historical preservation. Preserve full product scope, v2 phase readiness/exits, Architecture v2 approval evidence, the risk matrix, and RC-2/RC-3/RC-4 semantics. Include exactly one Phase 0A index whose field names, in order, are `phase`, `relevant_register_ids`, `evidence_build_references`, `human_decision_references`, `blockers`, and `next_gate`; point to current repository evidence/decision records without copying v2 statuses, dependencies, acceptance text, gate prose, or Deferred/Rejected state. State that v2 wins on conflict and affected work blocks until a normal corrective commit. Do not create a selector, archive, manifest, validator, digest ledger, review report, or product artifact.

Verification: `git diff --check -- docs/goals/equity-os-blueprint-completion.md` exits 0; `git diff --name-only -- docs/goals/equity-os-blueprint-completion.md` prints exactly that path; the Implementer reports `DONE` with that single modified file and no commit.

Dependencies: None

Risks: `HIGH` because this replaces active governance authority. The edit is documentation-only but must be treated as one atomic candidate; no test-first call applies.

### Task 2: Run focused root verification and stage the exact candidate

Goal: The Orchestrator proves the candidate satisfies the approved spec, preserves all read-only authorities, and is the only path staged for the switch review.

Files:
- Create: None
- Modify: None
- Test: `docs/goals/equity-os-blueprint-completion.md` and every read-only path in the file map

Interfaces:
- Consumes: the Task 1 `GovernanceResetContract` and the pre-existing dirty-tree baseline.
- Produces: one `VerifiedSwitchCandidate`, defined as the explicitly staged canonical-goal blob plus recorded passing command outputs.

Approach: Verify locally at the repository root; do not accept the Implementer's report as proof. Confirm the approved spec hash, cold-read the complete replacement, check each success criterion and exclusion, and compare representative Phase 0A, Phase 0.5, later-phase, and Deferred-scope decisions to v2. Confirm linked paths and live Bead evidence exist. Do not overwrite or stage unrelated dirty content. Require an otherwise empty index, then stage only `docs/goals/equity-os-blueprint-completion.md`; if unrelated staged content exists, stop without altering it.

Verification: `sha256sum docs/specs/2026-08-19-governance-reset-supersession.md` prints `8ef1baa26825966fd7a3eddb1910a2621afe6c3004819ecba916699e63788702`; `git diff --check -- docs/goals/equity-os-blueprint-completion.md` exits 0; `python3 -c 'from pathlib import Path; import re; s=Path("docs/goals/equity-os-blueprint-completion.md").read_text(); a=s.index("## Current-phase index"); b=s.find("\n## ", a+3); q=s[a:] if b<0 else s[a:b]; assert re.findall(r"^\| `([^`]+)` \|", q, re.M)==["phase","relevant_register_ids","evidence_build_references","human_decision_references","blockers","next_gate"]'` exits 0; `git diff --exit-code -- docs/blueprint/funda-blueprint-implementation-decision-register-v2.md docs/blueprint/funda-third-order-review-disposition-report.md docs/goals/architecture/equity-os-architecture-of-record-v2.html docs/goals/architecture/architecture-brief-v2.md docs/goals/architecture/equity-os-architecture-of-record-v2-review-r3.md` prints no diff; `bd show eqos-jce`, `bd show eqos-9x8`, and `bd show eqos-fga` succeed; after explicit staging, `git diff --cached --name-only` prints exactly `docs/goals/equity-os-blueprint-completion.md`; `git status --short` shows no unrelated path staged or overwritten, and any tool-generated Beads interaction/export change remains unstaged and reported.

Dependencies: Task 1

Risks: A dirty worktree can make broad status checks misleading. Use path-scoped diffs, explicit staging, and the captured baseline; never clean, restore, or stage unrelated paths.

### Task 3: Obtain the single final integrated review

Goal: One independent Reviewer accepts the exact staged governance switch with no load-bearing requirement, authority, scope, or invariant finding.

Files:
- Create: None
- Modify: None
- Test: the staged `docs/goals/equity-os-blueprint-completion.md` diff against the approved spec, this plan, v2, the disposition report, Architecture v2, and repository invariants

Interfaces:
- Consumes: the Task 2 `VerifiedSwitchCandidate` and exact staged diff.
- Produces: one in-session `IntegratedReviewVerdict` containing Reviewer session metadata, model/effort evidence, reviewed staged scope, findings, and verdict; no repository review artifact.

Approach: Launch exactly one isolated Codex CLI Reviewer using `gpt-5.6-sol` at `high` effort with `read-only`, the `.codex/agents/spec-reviewer.toml` constraints, and `spec` review mode. Instruct it to inspect the exact staged diff once, test the approved spec's success criteria and exclusions, and report Critical/Important findings as load-bearing. Record its session ID, actual model/effort metadata, and verdict in the existing `eqos-fga` handoff/closure evidence, not a new file. Minor polish does not trigger another round.

Verification: the Codex CLI run completes successfully with live metadata showing `gpt-5.6-sol` and `high`; its `IntegratedReviewVerdict` is `COMPLIANT` or equivalent acceptance, names no Critical/Important finding, and confirms the staged path scope is exactly the canonical goal.

Dependencies: Task 2

Risks: `HIGH` governance review. A catalog entry, role file, or echoed model name is not runtime proof; use the completed CLI session metadata. One capacity/authentication retry is allowed, after which stop and report that the mandatory review is unavailable.

### Task 4: Apply one targeted remedy only if review is load-bearing

Goal: If Task 3 reports a Critical/Important finding, that finding alone is corrected and the exact corrected candidate receives one focused accepting re-review; otherwise this task is skipped.

Files:
- Create: None
- Modify: `docs/goals/equity-os-blueprint-completion.md` only when Task 3 has a load-bearing finding
- Test: the Task 3 finding list, corrected staged diff, and all Task 2 checks

Interfaces:
- Consumes: a load-bearing Task 3 `IntegratedReviewVerdict` and its exact finding list.
- Produces: one corrected `VerifiedSwitchCandidate` and one in-session `ReReviewVerdict`, or no output when Task 3 accepted.

Approach: Dispatch one `gpt-5.6-terra`/`high` targeted fix limited to the named finding and canonical goal. The Orchestrator reruns every Task 2 check and restages only the goal. Dispatch one `gpt-5.6-sol`/`high` read-only re-review limited to the finding and fix diff. Do not broaden scope, fix Minor observations, or start a second fix cycle. If any Critical/Important finding remains or new load-bearing breakage appears, stop with the switch uncommitted.

Verification: all Task 2 signals pass on the corrected bytes; the one `ReReviewVerdict` marks every load-bearing finding `ADDRESSED`, reports no new Critical/Important breakage, and live CLI metadata proves the required Sol-high route.

Dependencies: Task 3, only when Task 3 has a load-bearing finding

Risks: The remedy can silently become a redesign. Any required change outside the canonical goal or beyond the approved spec is a stop condition, not an expanded fix round.

### Task 5: Commit the switch and close the existing Bead

Goal: A normal commit makes the accepted canonical contract current, preserves the former goal in its parent, pushes the bounded switch, and closes `eqos-fga` with verification and review evidence.

Files:
- Create: None
- Modify: None; repository content is already staged from Task 2 or Task 4
- Test: the switch commit, its parent, remote/branch status, and live Bead `eqos-fga`

Interfaces:
- Consumes: the accepted final `VerifiedSwitchCandidate` plus the accepting `IntegratedReviewVerdict` or `ReReviewVerdict`.
- Produces: one normal `GovernanceSwitchCommit`, one bounded push, and closed Bead `eqos-fga` with the commit ID and evidence in its close reason.

Approach: Reconfirm the index contains only the canonical goal, commit normally without amend or history rewriting, then verify the committed tree and parent before pushing the current branch. Close `eqos-fga` only after the push succeeds, recording the focused checks and Reviewer session/verdict. Do not stage the plan, Beads exports, historical evidence, or any unrelated dirty path as part of the switch commit.

Verification: `git show --name-only --format= HEAD` prints exactly `docs/goals/equity-os-blueprint-completion.md`; `git show HEAD:docs/goals/equity-os-blueprint-completion.md` contains the reviewed supersession contract; `git show HEAD^:docs/goals/equity-os-blueprint-completion.md` contains the former `# Equity-OS Blueprint Completion Goal`; `git status --short` preserves only the known unrelated baseline; `git status --branch --short` shows no unpushed switch commit after the bounded push; `bd show eqos-fga` reports `CLOSED` with commit and review evidence.

Dependencies: Task 3 when accepted directly; otherwise Task 4

Risks: The commit is the authority switch. Any staged-path mismatch, post-review byte change, failed commit, failed push, or remaining load-bearing finding leaves `eqos-fga` open and the switch unclaimed.

## Task map to Bead `eqos-fga`

| Plan task | Bead acceptance covered |
|---|---|
| Task 1 | Canonical goal visibly supersedes the former process; six-field Phase 0A index, risk policy, v2/Architecture/full-scope/Deferred controls, and RC-2/3/4 semantics are present. |
| Task 2 | Focused structural checks pass and only the intended canonical goal is staged. |
| Task 3 | One final Sol-high integrated review accepts the exact candidate. |
| Task 4 | At most one load-bearing fix/re-review is permitted; unresolved load-bearing findings stop the switch. |
| Task 5 | Intended path is normally committed and pushed; `eqos-fga` closes with evidence. |

No child Beads are needed: these are dependent acceptance steps of one atomic governance switch, not independently deliverable work.

## Inline self-review

- **Spec coverage:** Tasks 1–5 cover the in-place switch, Git-native preservation, six-field index, phase readiness, risk review, RC-2/3/4, exact integrated review, normal commit, and Bead closure; every out-of-scope item stays excluded.
- **Placeholder scan:** No placeholder token, deferred implementation marker, unnamed validation, or cross-task shorthand appears.
- **Name/type consistency:** `GovernanceResetContract` → `VerifiedSwitchCandidate` → `IntegratedReviewVerdict`/conditional `ReReviewVerdict` → `GovernanceSwitchCommit` is consistent across every consumer and producer.
- **Gap-naming pass:** Dirty-tree isolation, runtime model proof, review-to-staged-byte binding, conditional fix cap, parent-history verification, failed-commit semantics, push failure, and Bead closure are explicitly handled; no archive, selector, extra review file, product code, roadmap, or per-file digest system is introduced.
- **Right-sizing:** A Reviewer can independently reject content production, root verification, integrated review, the conditional remedy, or commit activation; splitting the canonical-goal rewrite itself would create unsafe partial authority states, so Task 1 remains atomic.
