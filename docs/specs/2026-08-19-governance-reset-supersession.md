# Governance Reset Supersession

Status: approved
Direction approved by: Current user, 2026-08-19 — “I approve the governance reset direction.”
Approved by: Current user, 2026-08-19 — “continue”, given directly in response to the exact-spec approval request for reviewed SHA-256 `88a9894050bc2937825a07e8fc6f6d79a31883b3a005b643de78cd49dc87b22b`.

## Problem Statement

Equity-OS has spent two to three weeks on a 213-row clause-and-alias ledger, triple inventory reviews, universally prerequisite specs, and recursive proof machinery while empirical Phase 0A work remains open. The approved product architecture remains sound, but the process delays the manual baseline and four-quarter vertical slice that should determine which contracts are necessary.

## Solution

After explicit approval of this exact specification, replace `docs/goals/equity-os-blueprint-completion.md` in place with a concise supersession and current-process contract. The active goal already names that canonical path, so the persistent goal and future agents continue reading one path. The replacement must visibly state that it supersedes the former file’s process and gating contract.

The switch changes governance mechanics only. The v2 decision register remains operational authority; the third-order disposition report remains its interpretation and audit trail; approved Architecture v2 remains the architecture of record. Product scope, every register gate, and every Deferred or Rejected control remain intact. Git history preserves the former 5,918-line goal and all tracked historical material. Genuinely untracked historical evidence may be added once, unchanged, in the switch commit.

## User Stories

1. As the product owner, I want Phase 0A evidence work to resume without closing dormant future-method work, so empirical discovery determines durable contracts.
2. As an analyst, I want all v2 gates and Deferred or Rejected controls preserved, so governance simplification cannot broaden product authority.
3. As an auditor, I want normal Git history to preserve the former process and evidence without creating another inventory system.
4. As an implementer, I want one current-phase index at the canonical goal path, so readiness is visible without reconstructing clause-level records.
5. As a reviewer, I want review depth determined by observable risk, so load-bearing integrated changes receive scrutiny without routine review loops.

## Implementation Decisions

### 1. Single-path authority switch

The switch is one narrowly staged Git commit made only after explicit current-user approval of this exact specification. It replaces `docs/goals/equity-os-blueprint-completion.md` in place; it does not create another current-authority selector or depend on an external goal-lifecycle operation.

The replacement goal contract must:

- state at its top that it supersedes the former goal’s process and gating contract while Git history preserves that former contract;
- identify the v2 decision register as the sole source of register decisions, statuses, dependencies, evidence requirements, and phase gates;
- retain the third-order disposition report and approved Architecture v2 HTML, companion brief, and approval evidence as continuing authority;
- preserve full product scope and state that no Deferred or Rejected item is active unless v2 and its required human authority explicitly activate it;
- contain the current-phase index defined below and the review policy in §5.

Working-tree edits are candidates only. The replacement becomes current when the normal switch commit records it. A failed commit creates no switch. A later defect blocks affected work and is corrected by a later visible commit; history is not rewritten.

### 2. Git-native historical preservation

The switch commit’s parent preserves the former canonical goal and tracked historical record. Existing ledgers, reviews, transitions, approvals, specs, Architecture artifacts, and fallback assets remain historical evidence at their existing paths. They are not readiness prerequisites unless the current contract or v2 makes a specific item relevant to current work.

Any genuinely untracked historical evidence needed for the audit record may be added unchanged in the switch commit. No historical artifact is reread merely to complete the switch. Ordinary Git tree and parent history bind the committed bytes.

### 3. Current-phase index

The replacement canonical goal contains one current-phase index with only these fields:

| Field | Content |
|---|---|
| `phase` | The one current blueprint phase. |
| `relevant_register_ids` | Only v2 IDs applicable to that phase’s current work. |
| `evidence_build_references` | Repository paths to active evidence and build contracts. |
| `human_decision_references` | Repository paths to applicable human decisions. |
| `blockers` | Explicit unresolved blockers, or `None`. |
| `next_gate` | The applicable v2 §F exit gate. |

The index does not reproduce register status, dependencies, acceptance text, disposition state, or Deferred or Rejected state. Those meanings live only in v2. Later-phase entries appear only when that phase becomes current. If the index conflicts with v2, v2 wins and affected work is blocked until a normal corrective commit updates the index.

### 4. Phase-scoped readiness and exits

- **Governance switch:** requires exact-spec approval, the self-checks in this specification, exactly one independent `HIGH` review of the final integrated switch bytes, any required current-user authority, and a normal commit.
- **Phase 0A evidence work:** may proceed when its relevant v2 prerequisites and human or rights decisions are satisfied. Historical process closure and dormant future-method work are not universal prerequisites.
- **Phase 0.5 product implementation:** requires the complete v2 Phase 0A exit gate, approved relevant build contracts, and continuing Architecture v2 approval.
- **Phase 1 and later:** require every preceding v2 §F gate, applicable row dependencies, and explicit activation authority. Dependency satisfaction alone never activates Deferred scope.

At each phase exit, create one small reviewed decision record mapping every applicable v2 §F clause to repository evidence paths and human decisions. The record does not copy register status or gate prose. Its Git commit binds its bytes. Missing, conflicting, or stale evidence blocks exit; no pass is inferred.

### 5. Risk-based review policy

Classify work by its highest matching risk before acceptance:

| Risk | Scope | Required review |
|---|---|---|
| `LOW` | Reversible work with no product behavior, authority, trust-boundary, persistence, or external-effect change. | Author self-check and relevant tests only. |
| `STANDARD` | Product behavior, persisted records, or cross-component interfaces not meeting `HIGH`. | Author self-check and relevant tests, plus one independent integrated review at slice or release acceptance. |
| `HIGH` | Governance or authority; architecture; distribution or execution boundaries; security, rights, external integrations, canonical schemas or migrations; human approval or memory promotion; phase gates; production release. | One independent review of exact integrated bytes, plus every required human authority. |

This existing independent review is the specification review; correcting its findings does not create another spec-review round. The future final switch diff receives exactly one independent `HIGH` review.

Architecture v2 is not reopened unless a proposed change alters its component boundaries, trust model, CAN/CANNOT contract, or first-release/later split. Review evidence never supplies product-owner, vocabulary-domain, legal, rights, analyst, security-exception, or production authority.

### 6. RC-2, RC-3, and RC-4 semantics

- **RC-2 — multi-artifact approval:** one combined approval may cover a declared complete set of specs or build artifacts. It identifies the complete sorted set by ID and canonical path; the referenced Git commit binds the exact bytes. The approved set must equal the declared scope: no subset, superset, duplicate, inferred, transitive, changed-byte, component-local, or duplicate per-spec approval qualifies.
- **RC-3 — vocabulary domain authority:** metric-registry and claim-predicate-registry additions require distinct typed `DOMAIN_EXPERT_ACCEPTANCE` from the competent Vocabulary authority. Process approval does not approve an entry; every addition still receives the entry-level approval required by S13.
- **RC-4 — product identity authority:** A-09 requires trademark or legal review and a separate typed `PRODUCT_OWNER_DECISION` for the exact product identity. Neither satisfies the other, and architecture, governance, or repository-operation approval satisfies neither.

## Success Criteria

- With exact-spec approval, the final switch changes the canonical goal path in place, visibly supersedes the former process, passes exactly one independent `HIGH` review, and commits only intended paths.
- Git parent history preserves tracked historical material; any necessary untracked historical evidence is added once and unchanged.
- The canonical goal’s current-phase index contains exactly the six fields in §3, while all statuses and Deferred or Rejected states remain only in v2.
- Phase 0A evidence work can proceed from relevant v2 prerequisites; Phase 0.5 and later work remains blocked by every applicable v2 gate and authority.
- RC-2 complete-set approval, RC-3 domain authority, RC-4 separate identity authorities, approved Architecture v2, and full product scope remain effective.

## Testing Decisions

Use focused structural checks and normal Git inspection:

1. Confirm the replacement goal contains the supersession statement, continuing authorities, current-phase index, and risk policy.
2. Confirm the index has exactly the six permitted fields and references only current-phase register IDs.
3. Confirm v2 remains the only source of statuses and Deferred or Rejected state, and representative readiness decisions preserve its gates.
4. Inspect the staged diff and paths, commit normally, then verify the committed canonical goal and its parent history.

The existing independent review at `docs/goals/reviews/equity-os-governance-reset-supersession-spec-review-r0.md` is the review evidence for this specification.

## Out of Scope

- Changing Architecture v2, product scope, register wording, status, dependencies, dispositions, gates, or any Deferred or Rejected control — rejected.
- Satisfying register evidence, human decisions, provider rights, legal review, or phase exits — deferred to their owning phase.
- Applying or completing the bespoke RC fallback transaction or its broad review refresh — rejected; its RC-2/3/4 authority corrections survive here.
- Treating all historical specs, reviews, ledgers, or dormant work as current-phase prerequisites — rejected.
- Selecting providers or tools, writing product code, or creating a roadmap or implementation plan under this specification — deferred until the applicable approvals and gates.

## Open Questions

None.

## Further Notes

Direction approval and exact-spec approval are separate human acts. The current user approved these exact reviewed bytes as recorded above; the switch is authorized, while the former canonical goal remains current until the normal switch commit records its replacement.
